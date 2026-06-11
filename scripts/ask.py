#!/usr/bin/env python3
"""ask — the dogfood "ask anything" REPL over the LIVE pkm catalogue, with citations.

Phase-1 dogfood interface. One command -> an `ask> ` loop that, per question:
retrieves top-k chunks from the whole live corpus (BM25 FTS, Hebrew-aware), has the
pinned answer model synthesise a concise answer that cites [n] into those chunks, then
captures a one-key verdict (+ optional note) into a dated session log under
$LIFE_AGENT_KB. The captured misses are the FAILURES-driven spec for what to build next.

This is pure composition of the comparison harness: it is `phase1_answer.answer_one`
minus the frozen-snapshot filter (dogfood asks over the whole corpus, not a pinned S)
and minus the per-question hand-written search_queries (the raw question IS the query —
an honest "ask anything" test that surfaces retrieval gaps as signal).

Run (from the repo root, for pkm.retrieval + duckdb):
    bin/ask-live                      # interactive REPL
    bin/ask-live "what is my ID?"     # answer once, then prompt for a verdict
    bin/ask-live --k 12               # wider retrieval context
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import readline  # noqa: F401  -- enables line editing / history at the input() prompts
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any

import citation_guard as guard  # sibling script: deterministic citation-faithfulness gate
import duckdb
import yaml

# Shared infra (metered LLM call, secret lookup, source rendering, the resolved KB /
# PKM_CONFIG paths) lives in the installed life_agent package (see life-agent's pyproject).
import life_agent.core as C
from life_agent import owner
from life_agent.core import derivations as D
from life_agent.core import temporal as T
from pkm.hashing import canonical_json

DEFAULT_K = 8  # matches phase1_answer.py's synthesis-context default

# Abstention floor (§reliability): refuse to synthesise when retrieval is too weak, rather than
# confabulate from topically-adjacent-but-wrong chunks. Conservative defaults (fire only on
# genuinely weak retrieval); tune from the eval BM25 score distribution via these env vars.
WEAK_SCORE_FLOOR = float(os.environ.get("LIFE_AGENT_SCORE_FLOOR", "4.0"))
MIN_STRONG_HITS = int(os.environ.get("LIFE_AGENT_MIN_HITS", "1"))
ABSTENTION = (
    "I don't have a strong enough source in your corpus to answer that confidently — retrieval "
    "surfaced nothing above the relevance floor. I'd rather say so than guess; the weak matches "
    "below are shown only so you can see what was near."
)

# Query expansion: a cheap model rewrites the natural-language question into concrete
# BM25 keywords. The dogfood loop showed FTS fails on vocabulary mismatch — "how do i
# make money" / "what is my employment status" miss the answer doc that "am i a
# contractor?" finds, because only the last shares surface words with the document.
# Expansion bridges the question's words to the documents' words. Light reasoning, so a
# cheap model (Haiku); synthesis stays on the pinned ANSWER_MODEL.
EXPAND_MODEL = "claude-haiku-4-5-20251001"
EXPAND_SYSTEM = (
    "You expand a personal-assistant question into keywords for a bag-of-words (BM25) "
    "search over the owner's personal documents, which are in English AND Hebrew. The "
    "owner asks in natural language but the documents use concrete domain vocabulary "
    "(an income question is answered by a doc that says 'invoice', 'salary', 'Contractor', "
    "'עוסק מורשה' — never the phrase 'make money'). Output ONLY a space-separated list of "
    "8-15 concrete search terms: synonyms, the specific nouns such documents contain, and "
    "their Hebrew equivalents. No punctuation, no numbering, no explanation. "
    "Example — 'how do i make money' -> income salary invoice contractor self-employed "
    "freelance fee earnings employer עוסק מורשה משכורת חשבונית."
)

# Synthesis prompt. Deliberately NOT the comparison harness's CITATION_INSTRUCTION (in
# scripts/comparison/_common.py): that is a frozen eval artifact, hardened against
# identity-confusion for blind grading — it demands a value be asserted "only if it is the
# subject the question asks about". In the dogfood loop that backfired: the model disowned the
# owner's OWN un-name-stamped documents (a contract they signed, their tax certificate) and read
# "how do i make money" as a request for generic advice. So this prompt reads questions in the
# first person and attributes the corpus to the owner by default.
#
# But that default *over*-corrected on 2026-06-02: "what is my name?" returned a family member's
# health report (a partner's name + ID) as the owner's. The fix is the OWNER block — authoritative
# identity facts (see life_agent.owner) injected by answer() — which this prompt treats as the
# authority on whose document a SOURCE is, so a partner's/relative's name or ID is never asserted
# as the owner's. (The OWNER block may be empty; the rules then degrade to the old behaviour.)
ANSWER_SYSTEM = (
    "You are the owner's personal assistant, answering questions about the owner's own life. "
    "You are given an OWNER block (authoritative facts about who the owner is — names, IDs) and "
    "numbered SOURCES (chunks retrieved from the owner's documents). Answer from these; put a "
    "bracketed source number like [1] immediately after each fact a SOURCE supports. If the answer "
    "is in neither, say so plainly and name what would be needed — do not guess.\n"
    "Rules specific to a personal corpus:\n"
    "1. Read every question in the first person about the owner. 'How do I make money' means "
    "'what are my sources of income, per my records' — NOT a request for generic advice.\n"
    "2. The OWNER block is the authority on the owner's identity: answer 'what is my name / my ID "
    "/ my phone' from it directly. Use it to judge whose document a SOURCE is — a SOURCE whose "
    "subject is a person or ID the OWNER block identifies as someone ELSE (a partner, a family "
    "member) is NOT the owner's; never assert another person's name or ID as the owner's.\n"
    "3. Otherwise attribute documents to the owner by default: a contract they signed, their tax "
    "certificate, their CV, an offer addressed to them all describe the owner even when they don't "
    "repeat the owner's name on every line. The exception is a document that positively identifies "
    "a DIFFERENT person as its subject. Be concise."
)


# --- retrieval over the LIVE corpus --------------------------------------- #
def _pkm_root() -> Path | None:
    """The pkm knowledge root, or None when unresolvable. None disables derivation
    caching only (fail open) — answering itself goes through connect(), which raises."""
    try:
        cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
        return Path(cfg["root_dir"]).expanduser()
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return None


def connect() -> duckdb.DuckDBPyConnection:
    """Open the live catalogue read-only (so a running extraction never blocks us)
    and load FTS. Mirrors phase1_answer._connect()."""
    root = _pkm_root()
    if root is None:
        raise FileNotFoundError(f"unresolvable pkm root (config: {C.PKM_CONFIG})")
    conn = duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


# --- the cached derivation DAG (pkm SPEC §18.9) ----------------------------- #
# Each ask is a DAG of content-addressed stages — expand → retrieve → synthesize —
# recorded file-first into the pkm cache (life_agent.core.derivations). Re-asking an
# unchanged question against an unchanged corpus replays every stage from cache at zero
# marginal cost; a changed input invalidates exactly the stages downstream of it (the
# synthesize key hashes the retrieved CONTENT, so corpus growth that retrieves the same
# evidence still replays the answer — early cutoff). Caching is strictly fail-open:
# no resolvable root / no digest / a lock just means a fresh computation, never a failure.
CACHE_STATS: dict[str, int] = defaultdict(int)


def _count(stage: str, *, hit: bool) -> None:
    CACHE_STATS[f"{stage}.{'hit' if hit else 'miss'}"] += 1


def reset_cache_stats() -> None:
    CACHE_STATS.clear()


def cache_stats() -> dict[str, int]:
    """A copy of the per-stage hit/miss counters (consumed by run_eval's report)."""
    return dict(CACHE_STATS)


def _corpus_digest(conn: duckdb.DuckDBPyConnection) -> str | None:
    """corpus_digest, fail-open: None (caching off for this question) on any failure —
    the cache must never break answering."""
    from life_agent.core.corpus import corpus_digest

    try:
        return corpus_digest(conn)
    except Exception:
        return None


def _is_lock_error(msg: str) -> bool:
    """True if a DuckDB error message means the catalogue is held by another process (a running
    extraction). Pure, so it's unit-tested in place of an un-reproducible live lock."""
    m = msg.lower()
    return "lock" in m or "conflict" in m or "being used" in m


def _clean_terms(raw: str) -> str:
    """Pure: flatten an LLM expansion reply to a clean space-separated term string.
    Drops bullets/commas/quotes/newlines; keeps Unicode word chars (so Hebrew survives)."""
    return " ".join(re.sub(r"[^\w]+", " ", raw, flags=re.UNICODE).split())


# --- temporal (D1): /recent · /since · the nothing-vanishes footer --------- #
# The ask path is READ-ONLY (§18.9), so temporal answers PROJECT current
# doc_date artifacts (SPEC §18.12) over the hits and never derive in-band;
# underived hits are named with their remedy and `/derive` materialises them
# explicitly (closing the read connection around the write). The report of the
# most recent temporal answer travels via TEMPORAL_LAST (the CACHE_STATS
# pattern) so answer()'s public 3-tuple stays unchanged for run_eval/tests.
@dataclass(frozen=True)
class TemporalReport:
    footer: str                                   # '' when nothing to say
    targets: list[tuple[str, str]] = field(default_factory=list)
    # targets: (declaration name, input artifact cache key) for /derive


TEMPORAL_LAST: TemporalReport | None = None


def parse_temporal_command(
    line: str,
) -> tuple[str, _date | None, _date | None, bool]:
    """Pure: split a REPL line into (question, since, until, recent).
    `/recent q` and `/since YYYY-MM-DD q` are the two temporal forms; an
    unparseable /since date returns the line unchanged (the REPL complains
    rather than silently asking an untemporal question)."""
    if line.startswith("/recent "):
        return line[len("/recent "):].strip(), None, None, True
    if line.startswith("/since "):
        rest = line[len("/since "):].strip()
        head, _, q = rest.partition(" ")
        try:
            return q.strip(), _date.fromisoformat(head), None, False
        except ValueError:
            return line, None, None, False
    return line, None, None, False


def temporal_footer(view: T.TemporalView, name_of: dict[str, str]) -> str:
    """Pure: render the total partition — every retrieved artifact is either
    admitted, excluded (with the date that failed), undated, or underived
    with its remedy. Nothing vanishes silently (the D1 coverage contract)."""
    def names(keys: list[str]) -> str:
        return ", ".join(name_of.get(k, k[:12] + "…") for k in keys)

    parts = [f"{len(view.admitted)} admitted"]
    if view.excluded:
        listed = ", ".join(
            f"{name_of.get(k, k[:12] + '…')} ({d.isoformat()})"
            for k, d in view.excluded)
        parts.append(f"{len(view.excluded)} excluded by date ({listed})")
    if view.undated:
        parts.append(f"{len(view.undated)} no extractable date "
                     f"({names(view.undated)})")
    if view.underived:
        parts.append(f"{len(view.underived)} not yet date-derived "
                     f"({names(view.underived)})")
    footer = "date filter: " + " · ".join(parts)
    if view.remedies:
        footer += ("\n  /derive to materialise, or run:\n    "
                   + "\n    ".join(view.remedies))
    return footer


def _apply_temporal_to_hits(
    conn: duckdb.DuckDBPyConnection, root: Path | None,
    hits: list[dict[str, Any]], *, since: _date | None, until: _date | None,
    recent: bool,
) -> tuple[list[dict[str, Any]], TemporalReport]:
    """Project + filter the chunk hits by ARTIFACT date. Chunks of one
    artifact share its fate; admitted chunks keep admitted-artifact order
    (newest first). Fail-open: an unresolvable root disables the filter with
    an explicit notice, never silently."""
    if root is None:
        return hits, TemporalReport(
            footer="date filter UNAVAILABLE (no pkm root) — showing all hits")
    keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    view = T.apply_temporal(
        T.project_dates(conn, root, keys),
        since=since, until=until, recent=recent)
    name_of = {h["artifact_cache_key"]: Path(h["origin"]).name for h in hits}
    rank = {k: i for i, k in enumerate(view.admitted)}
    admitted_hits = sorted(
        (h for h in hits if h["artifact_cache_key"] in rank),
        key=lambda h: rank[h["artifact_cache_key"]])
    targets = []
    for remedy in view.remedies:  # "pkm derive <decl> --input <ck>"
        words = remedy.split()
        targets.append((words[2], words[4]))
    return admitted_hits, TemporalReport(
        footer=temporal_footer(view, name_of), targets=targets)


def build_query(question: str, terms: str) -> str:
    """Pure: combine the raw question with expansion terms into one disjunctive BM25
    query. The original words are ALWAYS retained, so expansion can only *add* recall —
    a question that already hit on a rare literal term keeps its hit. Empty terms
    (expansion failed/disabled) leaves the raw-question search unchanged."""
    return f"{question} {terms}".strip() if terms else question


def _expand_terms(question: str, *, model: str = EXPAND_MODEL,
                  root: Path | None = None, no_cache: bool = False) -> str:
    """Impure edge: ask a cheap model for extra BM25 keywords. Returns a space-joined
    term string, or '' on any failure (caller falls back to the raw question — expansion
    must never break the REPL).

    Cached derivation (corpus-independent: keyed on question + model + prompt template
    only, so corpus growth never invalidates it). The RAW model reply is what is recorded;
    ``_clean_terms`` is applied post-cache, so a cleanup tweak changes behaviour without
    orphaning recorded expansions. Failures are never recorded."""
    key = D.expand_key(question, model=model, prompt_template=EXPAND_SYSTEM,
                       temperature=C.TEMPERATURE, max_tokens=120)
    if root is not None and not no_cache:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            _count("expand", hit=True)
            return _clean_terms(cached.decode("utf-8"))
    try:
        r = C.anthropic_complete(EXPAND_SYSTEM, question, model=model, max_tokens=120)
    except SystemExit:
        return ""
    if root is not None:
        _count("expand", hit=False)
        D.record(root, key, r.text.encode("utf-8"), lineage=[],
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens})
    return _clean_terms(r.text)


def _retrieve_set(conn: duckdb.DuckDBPyConnection, question: str, k: int) -> list[dict[str, Any]]:
    """FTS the given query over the whole corpus; dedupe by chunk text keeping the best
    score; return the top-k as plain dicts — the cacheable retrieval-set content, carrying
    each hit's artifact cache key for lineage. No snapshot filter."""
    from pkm.retrieval import SearchResult, search

    best: dict[str, SearchResult] = {}
    for h in search(conn, question, k=k * 4):  # over-fetch, then dedupe down to k
        prev = best.get(h.chunk_text)
        if prev is None or h.score > prev.score:
            best[h.chunk_text] = h
    top = sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]
    return [{"artifact_cache_key": h.artifact_cache_key, "chunk_text": h.chunk_text,
             "score": h.score, "origin": h.source_path} for h in top]


def _cards_from_set(hits: list[dict[str, Any]]) -> list[tuple[C.SourceCard, float]]:
    """Pure: render a retrieval set (live or replayed from cache) as numbered cards."""
    return [(C.SourceCard(n=i + 1, text=h["chunk_text"].strip(), origin=h["origin"]),
             h["score"]) for i, h in enumerate(hits)]


def _set_content(hits: list[dict[str, Any]]) -> bytes:
    """Pure: the canonical bytes of a retrieval set — what gets recorded, and what the
    synthesize key hashes (the early-cutoff hinge: equal evidence ⇒ equal hash, whatever
    the corpus digest did)."""
    return canonical_json({"format_version": 1, "hits": hits}).encode("utf-8")


def retrieve(conn: duckdb.DuckDBPyConnection, question: str,
             k: int) -> list[tuple[C.SourceCard, float]]:
    """FTS query → top-k (numbered SourceCard, score) pairs. Composition of the two
    halves above; kept as the uncached convenience seam."""
    return _cards_from_set(_retrieve_set(conn, question, k))


def retrieval_is_weak(scores: dict[int, float], *, floor: float, min_hits: int) -> bool:
    """Pure: True when fewer than ``min_hits`` retrieved chunks cleared ``floor``. Empty scores
    (zero retrieval) are weak by definition. The confabulation guard for the synthesis step."""
    return sum(1 for s in scores.values() if s >= floor) < min_hits


def answer(conn: duckdb.DuckDBPyConnection, question: str,
           k: int, *, expand: bool = True,
           no_cache: bool = False,
           since: _date | None = None, until: _date | None = None,
           recent: bool = False) -> tuple[str, list[C.SourceCard], dict[int, float]]:
    """Retrieve then synthesise a cited answer. The authoritative owner profile (who "I"/"my"
    is) is prepended as an OWNER block so the model never mistakes a relative's document for the
    owner's. Retrieval uses the question expanded with cheap-model keywords by default
    (``expand=False`` for the raw-question A/B baseline).

    Every stage is a cached, content-addressed derivation (SPEC §18.9): expand keyed on the
    question; retrieve keyed on (query, corpus digest, k); synthesize keyed on (question,
    retrieval-set content hash, owner-profile hash). ``no_cache`` recomputes every stage
    (recording stays write-once, so existing derivations stand). Caching is fail-open.
    Returns (answer_text, cards, {card_n: score})."""
    global TEMPORAL_LAST
    TEMPORAL_LAST = None
    root = _pkm_root()
    profile = owner.load_profile()
    terms = _expand_terms(question, root=root, no_cache=no_cache) if expand else ""
    if terms:
        print(f"  ↳ expanded: {terms}")
    query = build_query(question, terms)

    # retrieve — deterministic given the corpus state, so keyed on its digest
    digest = _corpus_digest(conn) if root is not None else None
    rkey = D.retrieve_key(query, digest, k=k) if digest is not None else None
    hits: list[dict[str, Any]] | None = None
    if root is not None and rkey is not None and not no_cache:
        cached = D.lookup(root, rkey.cache_key)
        if cached is not None:
            _count("retrieve", hit=True)
            hits = json.loads(cached.decode("utf-8"))["hits"]
    if hits is None:
        hits = _retrieve_set(conn, query, k)
        if root is not None and rkey is not None:
            _count("retrieve", hit=False)
            lineage = [{"cache_key": ck, "role": "retrieved"}
                       for ck in dict.fromkeys(h["artifact_cache_key"] for h in hits)]
            D.record(root, rkey, _set_content(hits), lineage=lineage)

    # temporal (D1): filter/rank the hits by projected doc_date BEFORE cards
    # and the synthesize key — the admitted set IS the evidence, so the key's
    # early-cutoff hinge hashes exactly what synthesis sees. The full retrieval
    # set was already recorded above (retrieval is a corpus+query function;
    # the date predicate is consumer-side policy).
    if since is not None or until is not None or recent:
        hits, report = _apply_temporal_to_hits(
            conn, root, hits, since=since, until=until, recent=recent)
        TEMPORAL_LAST = report

    pairs = _cards_from_set(hits)
    cards = [c for c, _ in pairs]
    scores = {c.n: s for c, s in pairs}
    # Abstain on weak retrieval (subsumes the zero-hit case) unless the owner profile can answer
    # an identity question on its own. Returns the weak cards so the dogfood loop sees the misses.
    # No synthesize derivation is recorded for an abstention — it is a refusal, not an answer.
    if retrieval_is_weak(scores, floor=WEAK_SCORE_FLOOR, min_hits=MIN_STRONG_HITS) and not profile:
        return (ABSTENTION, cards, scores)

    # synthesize — keyed on the retrieved CONTENT (early cutoff) and the profile hash
    skey = D.synthesize_key(question, D.content_hash(_set_content(hits)),
                            D.content_hash(profile.encode("utf-8")),
                            model=C.DEFAULT_ANSWER_MODEL, prompt_template=ANSWER_SYSTEM,
                            temperature=C.TEMPERATURE, max_tokens=600)
    if root is not None and not no_cache:
        cached = D.lookup(root, skey.cache_key)
        if cached is not None:
            _count("synthesize", hit=True)
            return (cached.decode("utf-8"), cards, scores)

    blocks = []
    if profile:
        blocks.append(f'OWNER (authoritative — who "I"/"my" refers to):\n{profile}')
    blocks.append(f"SOURCES:\n{C.render_sources_block(cards) if cards else '(none retrieved)'}")
    user = f"QUESTION: {question}\n\n" + "\n\n".join(blocks)
    r = C.anthropic_complete(ANSWER_SYSTEM, user, max_tokens=600)
    text = r.text.strip()
    if root is not None:
        _count("synthesize", hit=False)
        lineage = ([{"cache_key": rkey.cache_key, "role": "retrieval_set"}] if rkey else [])
        lineage += [{"cache_key": ck, "role": "source"}
                    for ck in dict.fromkeys(h["artifact_cache_key"] for h in hits)]
        D.record(root, skey, text.encode("utf-8"), lineage=lineage,
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens,
                           "seconds": round(r.seconds, 3)})
    return (text, cards, scores)


# --- presentation --------------------------------------------------------- #
def _sources_inline(cards: list[C.SourceCard], scores: dict[int, float]) -> str:
    return ", ".join(f"{Path(c.origin).name}({scores.get(c.n, 0.0):.2f})" for c in cards)


def render(text: str, cards: list[C.SourceCard], scores: dict[int, float],
           audit: guard.CitationAudit | None = None, footer: str = "") -> None:
    print(f"\n{text}\n")
    if cards:
        print("sources:")
        for c in cards:
            print(f"  [{c.n}] {Path(c.origin).name}  ({scores.get(c.n, 0.0):.2f})")
    if footer:
        print(footer)  # temporal partition: nothing vanishes silently (D1)
    if audit is not None and not audit.ok:
        print(audit.footer())  # ⚠ unverified: a cited fact wasn't found in its source
    print()


# --- feedback capture (the dogfood signal) -------------------------------- #
def log_entry(question: str, text: str, cards: list[C.SourceCard],
              scores: dict[int, float], verdict: str, note: str, *, when: str,
              unverified: str = "") -> str:
    """Render one dogfood log block. Pure (no I/O, no clock) so it is unit-tested."""
    lines = [
        f"## {when}  {verdict}",
        f"Q: {question}",
        f"A: {text}",
    ]
    if cards:
        lines.append(f"sources: {_sources_inline(cards, scores)}")
    if unverified:  # citation-guard flagged a cited fact not present in its source
        lines.append(f"unverified: {unverified}")
    if note:
        lines.append(f"note: {note}")
    return "\n".join(lines) + "\n"


def append_log(entry: str) -> Path:
    """Append a block to today's dated dogfood log under $LIFE_AGENT_KB (never the repo).
    Writes the session header once when the file is first created."""
    log = C.KB / "eval" / f"dogfood-{datetime.now():%Y-%m-%d}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    new = not log.exists()
    with log.open("a", encoding="utf-8") as fh:
        if new:
            fh.write(f"# Dogfood session {datetime.now():%Y-%m-%d}\n\n")
        fh.write(entry + "\n")
    return log


def _unverified_summary(audit: guard.CitationAudit | None) -> str:
    """Compact one-line summary of a citation audit for the dogfood log ('' when clean)."""
    if audit is None or audit.ok:
        return ""
    parts = [f"[{n}] {claim}" for claim, n in audit.unsupported]
    if audit.dangling:
        parts.append("dangling " + ",".join(f"[{n}]" for n in audit.dangling))
    return "; ".join(parts)


def capture(question: str, text: str, cards: list[C.SourceCard], scores: dict[int, float],
            audit: guard.CitationAudit | None = None) -> None:
    """One-key verdict (+ optional note). Frictionless: `g` logs immediately; `b`/`n`
    prompt for a note; Enter skips. A citation-guard flag is logged regardless of verdict."""
    try:
        choice = input("[g]ood / [b]ad / [n]ote / Enter=next > ").strip().lower()
    except EOFError:
        print()
        return
    verdict = {"g": "GOOD", "b": "BAD", "n": "NOTE"}.get(choice)
    if not verdict:
        return
    note = ""
    if verdict in ("BAD", "NOTE"):
        try:
            note = input("note> ").strip()
        except EOFError:
            print()
    log = append_log(log_entry(question, text, cards, scores, verdict, note,
                               when=f"{datetime.now():%H:%M}",
                               unverified=_unverified_summary(audit)))
    print(f"→ logged {verdict} to {log}\n")


# --- one question, end to end --------------------------------------------- #
def ask_once(conn: duckdb.DuckDBPyConnection, question: str, k: int,
             *, expand: bool = True, no_cache: bool = False,
             since: _date | None = None, until: _date | None = None,
             recent: bool = False) -> list[tuple[str, str]]:
    """Answer + render + capture. Returns the temporal report's derive targets
    (empty when untemporal) so the REPL can offer `/derive`."""
    text, cards, scores = answer(conn, question, k, expand=expand,
                                 no_cache=no_cache, since=since, until=until,
                                 recent=recent)
    audit = guard.audit(text, cards)  # pure and cheap — recomputed, never cached
    report = TEMPORAL_LAST
    render(text, cards, scores, audit,
           footer=report.footer if report is not None else "")
    capture(question, text, cards, scores, audit)
    return report.targets if report is not None else []


# --- /derive: explicit, demand-driven materialisation ---------------------- #
def run_derive(targets: list[tuple[str, str]]) -> None:
    """Materialise the named doc_date targets via pkm.derive (SPEC §18.11).
    The CALLER must have closed any read-only catalogue connection first — a
    reader and a writer cannot coexist on the DuckDB file. Fail-open: a held
    lock (an extraction running) prints and returns; nothing crashes the REPL."""
    from pkm.config import load_config as pkm_load_config
    from pkm.derive import derive as pkm_derive

    try:
        cfg = pkm_load_config(C.PKM_CONFIG)
    except Exception as e:
        print(f"derive unavailable (pkm config: {e})")
        return
    for decl, input_key in targets:
        try:
            result = pkm_derive(cfg.root_dir, cfg, decl,
                                input_cache_key=input_key,
                                caller="ask.derive")
        except duckdb.Error as e:
            if _is_lock_error(str(e)):
                print("corpus locked by extraction — try /derive again in a moment")
                return
            print(f"derive failed  {decl}: {e}")
            continue
        except Exception as e:
            print(f"derive failed  {decl}: {e}")
            continue
        if result.status == "success":
            print(f"derived  {decl}  {result.target_cache_key}")
        else:
            print(f"{result.status}  {decl}: "
                  f"{result.error_message or result.approval_id}")


# --- teaching: opportunistically record an authoritative owner fact ------- #
def remember(fact: str) -> None:
    """Append an owner-told fact ('My name is …') to the owner profile. This is identity
    ground truth, not corpus evidence — it is injected into every future answer, never ingested
    into pkm. Empty facts are ignored."""
    fact = fact.strip()
    if not fact:
        return
    path = owner.append_fact(fact, when=f"{datetime.now():%Y-%m-%d %H:%M}")
    print(f"→ remembered (owner profile: {path})\n")


# --- REPL ----------------------------------------------------------------- #
def repl(conn: duckdb.DuckDBPyConnection, k: int, *, expand: bool = True,
         no_cache: bool = False) -> None:
    print("ask anything about your life — '/i <fact>' to teach me about you, "
          "'/recent <q>' or '/since YYYY-MM-DD <q>' for date-filtered answers, "
          "'/derive' to materialise missing dates, Ctrl-D or /q to quit\n")
    derive_targets: list[tuple[str, str]] = []
    while True:
        try:
            line = input("ask> ").strip()
        except EOFError:
            print()
            return
        if not line:
            continue
        if line in ("/q", "/quit", "/exit"):
            return
        if line.startswith(("/i ", "/me ")):
            remember(line.split(" ", 1)[1])
            continue
        if line == "/derive":
            if not derive_targets:
                print("nothing to derive — ask a /recent or /since question first\n")
                continue
            # A reader and a writer cannot coexist (§18.9): close, write, reopen.
            conn.close()
            try:
                run_derive(derive_targets)
                derive_targets = []
            finally:
                conn = connect()
            print()
            continue
        question, since, until, recent = parse_temporal_command(line)
        if question == line and line.startswith("/since "):
            print("usage: /since YYYY-MM-DD <question>\n")
            continue
        derive_targets = ask_once(conn, question, k, expand=expand,
                                  no_cache=no_cache, since=since,
                                  until=until, recent=recent)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="*", help="ask once non-interactively; omit for the REPL")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"top-k retrieval context (default {DEFAULT_K})")
    ap.add_argument("--no-expand", action="store_true",
                    help="disable cheap-model query expansion (raw-question BM25 baseline)")
    ap.add_argument("--no-cache", action="store_true",
                    help="recompute every stage instead of replaying cached derivations "
                         "(recording stays write-once — existing derivations stand)")
    ap.add_argument("--tell", metavar="FACT",
                    help="record an authoritative owner fact (e.g. 'My name is …') and exit")
    ap.add_argument("--since", type=_date.fromisoformat, metavar="YYYY-MM-DD",
                    help="only sources dated on/after this date (others are named, not dropped)")
    ap.add_argument("--until", type=_date.fromisoformat, metavar="YYYY-MM-DD",
                    help="only sources dated on/before this date")
    ap.add_argument("--recent", action="store_true",
                    help="rank dated sources newest-first (nothing excluded)")
    args = ap.parse_args(argv)
    expand = not args.no_expand

    # Teaching is corpus-free: it works even while an extraction holds the catalogue lock.
    if args.tell:
        remember(args.tell)
        return 0

    # Opportunistic catalogue reconciliation (SPEC §18.9): insert the rows for any
    # file-first derivations recorded by earlier sessions, BEFORE our read-only connection
    # opens (a writer and a reader cannot coexist). A held lock just means next time.
    root = _pkm_root()
    if root is not None:
        # best-effort by contract; on any failure the files stay authoritative
        with contextlib.suppress(Exception):
            D.reconcile(root)

    try:
        conn = connect()
    except duckdb.Error as e:
        if _is_lock_error(str(e)):
            print("corpus locked by extraction, retry in a moment", file=sys.stderr)
            return 2
        raise

    if args.question:
        ask_once(conn, " ".join(args.question), args.k, expand=expand,
                 no_cache=args.no_cache, since=args.since, until=args.until,
                 recent=args.recent)
    else:
        repl(conn, args.k, expand=expand, no_cache=args.no_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
