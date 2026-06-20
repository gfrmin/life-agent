#!/usr/bin/env python3
"""ask — the dogfood "ask anything" REPL over the LIVE pkm catalogue, with citations.

Phase-1 dogfood interface. One command -> an `ask> ` loop that, per question:
retrieves top-k chunks from the whole live corpus (BM25 FTS, Hebrew-aware), has the
pinned answer model synthesise a concise answer that cites [n] into those chunks, then
captures a one-key good/bad verdict into a dated session log under
$LIFE_AGENT_KB. The captured misses are the FAILURES-driven spec for what to build next.

This is pure composition of the comparison harness: it is `phase1_answer.answer_one`
minus the frozen-snapshot filter (dogfood asks over the whole corpus, not a pinned S)
and minus the per-question hand-written search_queries (the raw question IS the query —
an honest "ask anything" test that surfaces retrieval gaps as signal).

Run (from the repo root, for pkm.retrieval + duckdb). One-shot argv is the SAME line
grammar as the REPL (docs/interaction-contract.md):
    bin/ask-live                                   # interactive REPL
    bin/ask-live "what is my ID?"                  # answer once, prompt for a verdict
    bin/ask-live "/since 2026-01-01 what invoices?"  # temporal predicate, same grammar
    bin/ask-live "/tell My name is …"              # record an authoritative owner fact
    bin/ask-live --k 12 "what is my ID?"           # wider retrieval context
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
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
from typing import Any, TypeGuard, cast

import citation_guard as guard  # sibling script: deterministic citation-faithfulness gate
import duckdb
import yaml

# Shared infra (metered LLM call, secret lookup, source rendering, the resolved KB /
# PKM_CONFIG paths) lives in the installed life_agent package (see life-agent's pyproject).
import life_agent.core as C
from life_agent import owner
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import expansion as EXP
from life_agent.core import gather as GA
from life_agent.core import lookup as LK
from life_agent.core import narrative as N
from life_agent.core import outcomes as O
from life_agent.core import probes as P
from life_agent.core import reactions as R
from life_agent.core import subject as S
from life_agent.core import synthesis as SYN
from life_agent.core import temporal as T
from life_agent.core import temporal_intent as TI
from life_agent.core.retrieval import build_query, retrieve_set
from life_agent.tasks import events as ev
from life_agent.tasks import knowledge
from pkm.hashing import canonical_json

# The corpus-retrieval seam now lives in the package (life_agent.core.retrieval, imported above)
# so the answer-brain capability bridge reuses it without a src↛scripts import. ``build_query``
# is re-exported by that import; ``_retrieve_set`` keeps its private name (callers and tests
# monkeypatch ask._retrieve_set). Query expansion (_expand_terms, below) stays script-side.
_retrieve_set = retrieve_set

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
# Query expansion now lives in core (`life_agent.core.expansion`) so the answer-brain bridge
# and this
# REPL share ONE expander + ONE cache. These aliases keep ask.py's surface (and its cache key — the
# prompt template is byte-identical) unchanged; `_expand_terms` below stays the script-side wrapper.
EXPAND_MODEL = EXP.EXPAND_MODEL
EXPAND_SYSTEM = EXP.EXPAND_SYSTEM

# Reranking: BM25 ranks by surface-word overlap, so for ~8 of the eval's retrieval misses
# the gold sits at lexical rank 36-132 (probe_gold_rank) — buried below literary PDFs that
# share the question's words but not its fact. A listwise reranker reads a WIDE lexical pool
# and selects the chunks that actually carry the answer, pulling the buried gold into the
# top-k (measured: Sonnet rescued 7/8 with zero regression, ~20k input tokens/question).
# Sonnet (not the synthesis default) because it reads the whole pool and accepts temperature.
RERANK_MODEL = "claude-sonnet-4-6"
RERANK_POOL = 150  # lexical chunks fed to the reranker (covers the deepest addressable gold)
RERANK_SYSTEM = (
    "You are a retrieval reranker for a personal-assistant corpus (English AND Hebrew). "
    "Given a QUESTION and a numbered list of document SNIPPETS, identify the snippets most "
    "likely to contain the EXACT fact needed to answer it. Prefer the specific, current, "
    "authoritative source (an official record, a form, a bill) over generic or incidental "
    "mentions of the same words. Return ONLY a JSON array of the {k} most relevant snippet "
    "numbers, best first — no prose."
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
# The synthesis prompt + synthesizer now live in core (`life_agent.core.synthesis`) so the answer-
# brain bridge and this REPL share ONE synthesizer + ONE cache (the prompt is the cache key, kept
# byte-identical). The alias keeps ask.py's surface unchanged.
ANSWER_SYSTEM = SYN.ANSWER_SYSTEM


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


_clean_terms = EXP.clean_terms  # the canonical cleaner now lives in core.expansion


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

# The last answer's §18.9 stage cache keys ({"retrieve": ..., "synthesize": ...}; absent
# entries mean the stage never keyed — e.g. no synthesize on an abstention). Travels like
# TEMPORAL_LAST so answer()'s public 3-tuple stays unchanged; the eval harness reads it
# for outcome lineage attribution (bayesian-foundations §8 — the outcomes log).
STAGES_LAST: dict[str, str] = {}

# The last answer's lookup-family result (foundations §4), or None when the narrative
# path answered (not routed as a lookup, zero grounded observations, or a named
# fail-open). Travels like TEMPORAL_LAST; run_eval's --lookup grader consumes it.
LOOKUP_LAST: LK.LookupResult | None = None

# The last answer's narrative-family result (foundations §7), or None when the lookup
# path answered, the answer abstained pre-synthesis, or narrative scoring failed
# (named fail-open). run_eval's claim + coverage graders consume it.
NARRATIVE_LAST: N.NarrativeResult | None = None

# --- subject (D2): the owner filter + the same nothing-vanishes contract --- #
# A first-person possessive question ("my X") filters hits by projected
# doc_subject (SPEC §18.13) matched against the owner profile — consumer-side,
# the profile never enters pkm. Only determinate non-owner subjects and
# generic documents (templates, blank forms) are excluded, each named; an
# absent or unclear classification is indeterminate — KEPT and named (the D2
# gate). The report travels like TEMPORAL_LAST; /derive consumes both.
SUBJECT_LAST: TemporalReport | None = None

# The question's temporal SCOPE (present / historical / as_of / unscoped), classified once per
# question and SURFACED in the footer (it changes no decision yet — the scope-aware inclusion
# slice is gate-adjacent and frozen-blind). Travels like TEMPORAL_LAST; None when unresolved.
INTENT_LAST: TI.Scope | None = None
INTENT_FOOTER = "temporal scope: {scope}"

# The trigger: an UNCHAINED first-person possessive. "my X" fires; a
# relational possessive — "my partner's X" — hands the subject to someone
# else, where filtering for the owner would exclude exactly the right answer.
_OWNER_POSSESSIVE = re.compile(
    r"\b(?:my|mine|the owner'?s)\b(?!\s+\S+['’]s\b)",  # noqa: RUF001 — typographic apostrophe is deliberate
    re.IGNORECASE)


def owner_question(question: str) -> bool:
    """Pure: does the question ask about the owner's own things?"""
    return _OWNER_POSSESSIVE.search(question) is not None


# The ONE line grammar (docs/interaction-contract.md): identical in the REPL and in
# one-shot argv. Each entry is (form, meaning, example); the example is parsed by the
# drift-gate test, so an entry the parser stops accepting fails CI, not the owner.
GRAMMAR: tuple[tuple[str, str, str], ...] = (
    ("QUESTION", "cited answer over the live corpus",
     "what is my ID?"),
    ("/recent QUESTION", "rank dated sources newest-first (ranks only; excludes nothing)",
     "/recent any invoices?"),
    ("/since YYYY-MM-DD QUESTION", "only sources dated on/after (excluded are named)",
     "/since 2026-05-01 appointments"),
    ("/until YYYY-MM-DD QUESTION", "only sources dated on/before "
                                   "(combine with /since for a range)",
     "/until 2026-06-01 appointments"),
    ("/tell FACT", "record an authoritative owner fact",
     "/tell My name is Ada Lovelace"),
    ("/derive", "materialise the projections (doc_date, doc_subject) the last "
                 "answer named as underived",
     "/derive"),
    ("/react ID g|b", "verdict a past answer by its decision-id — a deferred "
                      "dogfood verdict (only abstain verdicts move the fold)",
     "/react 8af95b2f bad"),
    ("/q", "quit (also /quit, /exit, Ctrl-D)",
     "/q"),
)


def grammar_text() -> str:
    """Pure: the grammar table rendered for humans — the REPL banner, every usage
    error, and the --help epilog all print THIS, so they cannot disagree."""
    width = max(len(form) for form, _, _ in GRAMMAR)
    return "\n".join(f"  {form.ljust(width)}  {meaning}" for form, meaning, _ in GRAMMAR)


@dataclass(frozen=True)
class Parsed:
    """One parsed input line. ``kind`` dispatches; the rest is that kind's payload."""
    kind: str  # "ask" | "tell" | "derive" | "react" | "quit" | "empty" | "error"
    question: str = ""
    fact: str = ""
    since: _date | None = None
    until: _date | None = None
    recent: bool = False
    did: str = ""       # /react: the decision-id prefix to verdict
    valence: str = ""   # /react: the canonical verdict ("good" | "bad")
    error: str = ""


# /react takes a single bit — the same one-key verdict as the inline prompt, or its
# spelled-out form, normalised to the reactions.VALENCES vocabulary. No free text: the only
# expensive resource in the loop is the owner's prose, so we elicit only the bit.
_VALENCE_ALIASES: dict[str, str] = {"g": "good", "good": "good", "b": "bad", "bad": "bad"}


def _error(message: str) -> Parsed:
    return Parsed(kind="error", error=f"{message}\nthe grammar:\n{grammar_text()}")


def parse_line(line: str) -> Parsed:
    """Pure: parse one input line under the contract's composition rules.
    /since and /until are bounds (a range, each at most once); /recent is a ranking
    directive and stands alone (a bound already ranks newest-first — see
    life_agent.core.temporal.apply_temporal). Anything ambiguous or unknown is a
    loud ``error`` naming the rule — never silently reinterpreted (invariant 3)."""
    line = line.strip()
    if not line:
        return Parsed(kind="empty")
    if line in ("/q", "/quit", "/exit"):
        return Parsed(kind="quit")
    if line == "/derive":
        return Parsed(kind="derive")
    if line == "/tell" or line.startswith("/tell "):
        fact = line[len("/tell"):].strip()
        return Parsed(kind="tell", fact=fact) if fact else _error("usage: /tell FACT")
    if line == "/react" or line.startswith("/react "):
        parts = line[len("/react"):].strip().split()
        if len(parts) != 2:
            return _error("usage: /react DECISION_ID g|b")
        valence = _VALENCE_ALIASES.get(parts[1].lower())
        if valence is None:
            return _error(f"usage: /react DECISION_ID g|b "
                          f"(verdict must be g/b, got {parts[1]!r})")
        return Parsed(kind="react", did=parts[0], valence=valence)
    if not line.startswith("/"):
        return Parsed(kind="ask", question=line)

    tokens = line.split()
    since: _date | None = None
    until: _date | None = None
    recent = False
    i = 0
    while i < len(tokens) and tokens[i].startswith("/"):
        t = tokens[i]
        if t == "/recent":
            if recent:
                return _error("/recent may appear only once")
            recent = True
            i += 1
        elif t in ("/since", "/until"):
            if (t == "/since" and since) or (t == "/until" and until):
                return _error(f"{t} may appear only once — bounds form one range")
            if i + 1 >= len(tokens):
                return _error(f"usage: {t} YYYY-MM-DD QUESTION")
            try:
                bound = _date.fromisoformat(tokens[i + 1])
            except ValueError:
                return _error(f"usage: {t} YYYY-MM-DD QUESTION (got {tokens[i + 1]!r})")
            if t == "/since":
                since = bound
            else:
                until = bound
            i += 2
        else:
            return _error(f"unknown command {t!r}")
    if recent and (since or until):
        return _error("/recent with a bound is redundant — /since and /until already "
                      "rank newest-first; drop /recent")
    if since and until and since > until:
        return _error(f"empty range: /since {since} is after /until {until}")
    question = " ".join(tokens[i:])
    if not question:
        return _error("missing QUESTION after the temporal prefix")
    return Parsed(kind="ask", question=question, since=since, until=until, recent=recent)


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


def subject_footer(view: S.SubjectView, name_of: dict[str, str]) -> str:
    """Pure: render the total partition — every retrieved artifact is either
    admitted, someone else's (named with the subject as written), generic
    (template/blank — determinately nobody's), subject-unclear (KEPT), or
    underived (KEPT, with its remedy). Indeterminates are never dropped
    (the D2 coverage contract)."""
    def names(keys: list[str]) -> str:
        return ", ".join(name_of.get(k, k[:12] + "…") for k in keys)

    parts = [f"{len(view.admitted)} admitted"]
    if view.excluded_other:
        listed = ", ".join(
            f"{name_of.get(k, k[:12] + '…')} ({s})"
            for k, s in view.excluded_other)
        parts.append(f"{len(view.excluded_other)} someone else's ({listed})")
    if view.excluded_generic:
        parts.append(f"{len(view.excluded_generic)} generic/template "
                     f"({names(view.excluded_generic)})")
    if view.unclear:
        parts.append(f"{len(view.unclear)} subject unclear — kept "
                     f"({names(view.unclear)})")
    if view.underived:
        parts.append(f"{len(view.underived)} not yet subject-derived — kept "
                     f"({names(view.underived)})")
    footer = "owner filter: " + " · ".join(parts)
    if view.remedies:
        footer += ("\n  /derive to materialise, or run:\n    "
                   + "\n    ".join(view.remedies))
    return footer


def _apply_subject_to_hits(
    conn: duckdb.DuckDBPyConnection, root: Path | None,
    hits: list[dict[str, Any]], *, profile: str,
) -> tuple[list[dict[str, Any]], TemporalReport, dict[str, str]]:
    """Project + owner-filter the chunk hits by ARTIFACT subject. Chunks of
    one artifact share its fate; admitted chunks keep their retrieval order
    (the filter excludes, it does not rank). Fail-open at every seam, never
    silently: no pkm root or no profile disables the filter with an explicit
    notice; a failed owner-match verdict leaves that subject unclear (kept
    and named in the footer). The third return value maps each admitted
    artifact key to its partition state ("owner" | "unclear" | "underived")
    — the lookup family's §4.1 subject covariate (carried OUTSIDE the hit
    dicts, so the retrieval-set bytes stay untouched)."""
    if root is None:
        return hits, TemporalReport(
            footer="owner filter UNAVAILABLE (no pkm root) — showing all hits"), {}
    if not profile:
        return hits, TemporalReport(
            footer="owner filter UNAVAILABLE (no owner profile — "
                   "/tell who you are) — showing all hits"), {}
    keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    shits = S.project_subjects(conn, root, keys)
    verdicts: dict[str, str] = {}
    for subj in sorted({h.subject for h in shits
                        if h.state == "named" and h.subject}):
        try:
            verdicts[subj] = S.owner_verdict(root, subj, profile)
        except Exception as e:  # fail-open per subject: unclear, kept, named
            print(f"  owner match failed for {subj!r} ({e}) — kept as unclear")
    view = S.apply_owner_filter(shits, verdicts)
    name_of = {h["artifact_cache_key"]: Path(h["origin"]).name for h in hits}
    admitted = set(view.admitted)
    admitted_hits = [h for h in hits if h["artifact_cache_key"] in admitted]
    indeterminate = {**dict.fromkeys(view.unclear, "unclear"),
                     **dict.fromkeys(view.underived, "underived")}
    state_of = {k: indeterminate.get(k, "owner") for k in admitted}
    targets = []
    for remedy in view.remedies:  # "pkm derive <decl> --input <ck>"
        words = remedy.split()
        targets.append((words[2], words[4]))
    return admitted_hits, TemporalReport(
        footer=subject_footer(view, name_of), targets=targets), state_of


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


def _rerank_hits(question: str, pool: list[dict[str, Any]], k: int, *,
                 model: str = RERANK_MODEL) -> list[dict[str, Any]]:
    """Impure edge: a listwise reranker reads the wide lexical POOL and returns its top-k
    hits, reordered so the chunk that actually carries the answer leads. Fail-open — any
    error (API down, unparseable reply) returns the lexical top-k unchanged, so reranking
    can only improve recall, never break the path. The returned dicts are the pool's own
    (same artifact_cache_key / chunk_text / origin / score), so every downstream key and
    citation is unaffected. A short or garbled reply is backfilled from the lexical head, so
    the result is never fewer (or worse on the tail) than lexical retrieval alone."""
    if len(pool) <= k:
        return pool[:k]
    snippets = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:280].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool))
    user = f"QUESTION: {question}\n\nSNIPPETS:\n{snippets}"
    try:
        r = C.anthropic_complete(RERANK_SYSTEM.format(k=k), user, model=model, max_tokens=400)
    except SystemExit:
        return pool[:k]
    m = re.search(r"\[[\s\d,]*\]", r.text)
    picks = [int(n) for n in re.findall(r"\d+", m.group(0))] if m else []
    seen: set[int] = set()
    ordered: list[dict[str, Any]] = []
    for n in picks:  # reranker order first, valid + de-duplicated
        if 1 <= n <= len(pool) and n not in seen:
            seen.add(n)
            ordered.append(pool[n - 1])
    for i, h in enumerate(pool, 1):  # backfill from the lexical head to guarantee k
        if len(ordered) >= k:
            break
        if i not in seen:
            ordered.append(h)
    return ordered[:k]


def _cards_from_set(hits: list[dict[str, Any]],
                    dates: dict[str, str | None] | None = None
                    ) -> list[tuple[C.SourceCard, float]]:
    """Pure: render a retrieval set (live or replayed from cache) as numbered cards. ``dates``
    (artifact_cache_key → ISO doc_date) attaches each card's ``as_of`` for the temporal-scope
    render; omitted ⇒ undated (back-compat — the retrieve() convenience seam stays date-blind)."""
    return [(C.SourceCard(n=i + 1, text=h["chunk_text"].strip(), origin=h["origin"],
                          as_of=(dates.get(h["artifact_cache_key"]) if dates else None)),
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


def _typed_lookup_applies(lk: LK.LookupResult | None) -> TypeGuard[LK.LookupResult]:
    """The routing criterion (§9 no-hard-zeros): the lookup family answered iff it returned a
    result. It returns None in exactly two cases — the question was not classified as a typed
    lookup, or it produced zero grounded observations — and both are coverage failures, not
    abstentions: the narrative path covers what lookup can't, by design. Naming the predicate
    keeps the dispatch a stated rule, not a bare ``is not None`` at the call site. The
    ``TypeGuard`` lets the name narrow ``lk`` to a ``LookupResult`` for the type-checker exactly
    as the bare ``is not None`` did — wrapping it in a function must not cost that narrowing."""
    return lk is not None


def answer(conn: duckdb.DuckDBPyConnection, question: str,
           k: int, *, expand: bool = True,
           no_cache: bool = False,
           families: bool = True,
           gather: bool = False,
           rerank: bool = False,
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

    ``families=False`` is the **monolithic instrument** seam (the adoption-gate baseline,
    bayesian-foundations §8): skip the typed lookup route AND the narrative scorer, so the
    raw synthesize prose is returned — the pre-Bayesian answer the gate weighs the typed
    families against. Default ``True`` preserves the production path exactly.

    ``gather=True`` runs the lookup route through the **gather-augmented loop**
    (:func:`life_agent.core.gather.gather_answer`): re-retrieve corroboration on the top
    candidates, then re-weight by recency + whose-document before deciding. Default
    ``False`` keeps the single-pass production path; the adoption gate turns it on for the
    typed arm to measure it.

    ``rerank=True`` over-fetches a wide lexical pool and lets a listwise reranker
    (:func:`_rerank_hits`) pick the top-k — the recall lever for golds BM25 buried below
    word-overlapping noise (measured: rescues ~7/8 of the eval's addressable retrieval
    misses). Default ``False``. Returns (answer_text, cards, {card_n: score})."""
    global TEMPORAL_LAST, SUBJECT_LAST, STAGES_LAST, LOOKUP_LAST, NARRATIVE_LAST, INTENT_LAST
    TEMPORAL_LAST = None
    SUBJECT_LAST = None
    STAGES_LAST = {}
    LOOKUP_LAST = None
    NARRATIVE_LAST = None
    INTENT_LAST = None
    root = _pkm_root()
    profile = owner.load_profile()
    # temporal-scope intent (cached, question-only): surfaced + recorded, decision-neutral.
    # Gated on a live session (conn) — the cache-replay / eval path (conn=None) skips it, as the
    # keystone's date probe does. Fail-open and NAMED (interaction contract): a classifier failure
    # leaves no label, never a wrong one; the scope-aware inclusion that would USE it is the next,
    # gate-adjacent slice.
    if conn is not None and root is not None:
        try:
            INTENT_LAST = TI.intent_verdict(root, question)
        except Exception as e:  # noqa: BLE001 — fail-open by contract, reason printed
            print(f"  (temporal scope: unclassified — {e})")
    terms = _expand_terms(question, root=root, no_cache=no_cache) if expand else ""
    if terms:
        print(f"  ↳ expanded: {terms}")
    query = build_query(question, terms)

    # retrieve — deterministic given the corpus state, so keyed on its digest. With
    # rerank=True, over-fetch a wide pool and let a listwise reranker pick the top-k (the
    # recall lever for golds BM25 buried below word-overlapping noise); the reranked set is
    # computed fresh — its content differs from the lexical top-k, so the retrieve key would
    # not match — and the wider, content-keyed synthesize cache below still applies.
    hits: list[dict[str, Any]] | None = None
    rkey = None  # the reranked set is not recorded under a retrieve key (its content is the
    # reranker's, not a pure corpus+query function); synthesize lineage falls back to sources
    if rerank:
        pool = _retrieve_set(conn, query, RERANK_POOL)
        hits = _rerank_hits(question, pool, k)
        STAGES_LAST["rerank"] = f"{RERANK_MODEL}/{RERANK_POOL}->{k}"
    else:
        digest = _corpus_digest(conn) if root is not None else None
        rkey = D.retrieve_key(query, digest, k=k) if digest is not None else None
        if rkey is not None:
            STAGES_LAST["retrieve"] = rkey.cache_key
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

    # subject (D2): owner-filter the (possibly already date-filtered) hits by
    # projected doc_subject when the question is an unchained first-person
    # possessive. Same placement reasoning as temporal: BEFORE cards and the
    # synthesize key, so the admitted set IS the evidence. The predicates
    # compose — each footer names its own partition over what reached it; the
    # full retrieval set is already recorded above.
    subject_state_of: dict[str, str] = {}
    if owner_question(question):
        hits, sreport, subject_state_of = _apply_subject_to_hits(
            conn, root, hits, profile=profile)
        SUBJECT_LAST = sreport

    # attach each card's freshest doc_date (probe_recency adds the email-Date-header fallback
    # for the
    # un-projected sliver) so the narrative render surfaces "as of <date>" — the temporal-scope
    # keystone. Read-only; display only (the synthesize key hashes hits, not cards).
    card_dates = (P.probe_recency(conn, root, list(dict.fromkeys(
        h["artifact_cache_key"] for h in hits)))
        if conn is not None and root is not None and hits else None)
    pairs = _cards_from_set(hits, card_dates)
    cards = [c for c, _ in pairs]
    scores = {c.n: s for c, s in pairs}
    # Abstain on weak retrieval (subsumes the zero-hit case) unless the owner profile can answer
    # an identity question on its own. Returns the weak cards so the dogfood loop sees the misses.
    # No synthesize derivation is recorded for an abstention — it is a refusal, not an answer.
    if retrieval_is_weak(scores, floor=WEAK_SCORE_FLOOR, min_hits=MIN_STRONG_HITS) and not profile:
        return (ABSTENTION, cards, scores)

    # The lookup family (Ask v0, foundations §4): typed point-fact questions take the
    # Bayesian path — grounded per-hit observations → tempered mixture posterior → EU
    # response under the utility posterior — and its decision IS the answer. Routed
    # conservatively: a declined route or zero grounded observations falls to the
    # narrative path (the §9 no-hard-zeros routing), and any failure is fail-open and
    # NAMED (interaction contract), never silent.
    if families and root is not None:
        try:
            if gather:
                # the gather-augmented loop projects its OWN covariates over the
                # gathered union (recency + whose-document) — it does not reuse the
                # baseline covariates computed above.
                lk = GA.gather_answer(conn, root, question, hits, profile=profile,
                                      owner_scoped=owner_question(question))
            else:
                # §4.1 covariates, projected read-side and carried OUTSIDE the hit
                # dicts (the retrieval-set bytes — and every key hashed from them —
                # stay untouched): the owner-filter partition states from above, and
                # the doc_date projection (None = projected but undated/underived).
                hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
                date_of: dict[str, str | None] = {
                    d.artifact_cache_key:
                        (d.date.isoformat() if d.date is not None else None)
                    for d in T.project_dates(conn, root, hit_keys,
                                             caller="ask.lookup")}
                cov = LK.HitCovariates(subject_state=subject_state_of,
                                       doc_date=date_of)
                lk = LK.lookup_answer(root, question, hits, covariates=cov,
                                      scope=INTENT_LAST or "unscoped")
        except Exception as e:  # fail-open by contract, reason printed
            print(LK.GRAMMAR["fallthrough"].format(reason=f"failed: {e}"))
            lk = None
        if _typed_lookup_applies(lk):
            LOOKUP_LAST = lk
            STAGES_LAST["lookup_answer"] = lk.answer_cache_key
            return (lk.rendered, cards, scores)

    # synthesize — keyed on the retrieved CONTENT (early cutoff) and the profile hash; the
    # synthesizer lives in core.synthesis (shared with the bridge). The retrieval_set lineage is
    # ask-side (rerank has no retrieve key), threaded through as extra lineage.
    extra = [{"cache_key": rkey.cache_key, "role": "retrieval_set"}] if rkey else []
    text, scache, scached = SYN.synthesize(root, question, hits, profile, no_cache=no_cache,
                                           extra_lineage=extra)
    if root is not None:  # caching telemetry only when a cache is in play (root resolved)
        _count("synthesize", hit=scached)
    STAGES_LAST["synthesize"] = scache
    if not families:  # the monolithic instrument: raw synthesize prose, unscored
        return (text, cards, scores)
    return (_narrative_scored(root, question, text, cards,
                              scope=INTENT_LAST or "unscoped"), cards, scores)


def _narrative_scored(root: Path | None, question: str, text: str,
                      cards: list[C.SourceCard], *, scope: str = "unscoped") -> str:
    """The narrative family's scorer (foundations §7) over the synthesize proposal:
    parse → audit cells → population credences → per-claim EU decision → labeled
    render. Read-side policy — the proposal artifact and its keys are untouched —
    rerun on every call so scorer/fold movement re-scores cached prose. Any failure
    is fail-open and NAMED: the raw prose still reaches the owner, marked unscored
    (interaction contract — nothing silent)."""
    global NARRATIVE_LAST
    if root is None:
        return text
    try:
        # cast: the seam may be stubbed to None (the conftest hermetic fixture)
        nv = cast("N.NarrativeResult | None",
                  N.narrative_answer(root, question, text, cards, scope=scope,
                                     synthesize_cache_key=STAGES_LAST.get("synthesize")))
    except Exception as e:  # fail-open by contract, reason printed
        print(N.GRAMMAR["fallthrough"].format(reason=f"failed: {e}"))
        return text
    if nv is None:  # the disabled seam (hermetic tests stub the family to None)
        return text
    NARRATIVE_LAST = nv
    STAGES_LAST["narrative_answer"] = nv.answer_cache_key
    return nv.rendered


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
              scores: dict[int, float], verdict: str, *, when: str,
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
    """One-key good/bad verdict — a single bit, no free text (the only expensive resource in
    the loop is the owner's prose). Frictionless: `g`/`b` logs immediately; Enter skips. A
    citation-guard flag is logged regardless of verdict."""
    try:
        choice = input("[g]ood / [b]ad / Enter=next > ").strip().lower()
    except EOFError:
        print()
        return
    verdict = {"g": "GOOD", "b": "BAD"}.get(choice)
    if not verdict:
        return
    log = append_log(log_entry(question, text, cards, scores, verdict,
                               when=f"{datetime.now():%H:%M}",
                               unverified=_unverified_summary(audit)))
    print(f"→ logged {verdict} to {log}\n")
    _record_reaction(question, verdict)


def _record_reaction(question: str, verdict: str) -> None:
    """§4.4 reaction loop: record the verdict (one bit) as a structured reaction, joined to
    the decision it grades by ``decision_id`` (the answer's cache key). The producer
    (`reactions.load_reactions`) decides what folds — v0 conditions u(wrong) only on clean
    lookup abstain-verdicts; everything else is recorded, not folded. Fail-open and named:
    a calibration-log write must never break the dogfood loop."""
    decision_id = (LOOKUP_LAST.answer_cache_key if LOOKUP_LAST is not None
                   else NARRATIVE_LAST.answer_cache_key if NARRATIVE_LAST is not None
                   else "")
    try:
        R.append(C.REACTIONS_LOG, R.ReactionEvent(
            tx_time=O.now_iso(),
            question_id=hashlib.sha256(question.encode("utf-8")).hexdigest()[:16],
            decision_id=decision_id, kind="verdict",
            valence={"GOOD": "good", "BAD": "bad"}[verdict]))
    except Exception as e:  # fail-open by contract, reason printed
        print(f"  (reaction not recorded: {e})")


def react(did_prefix: str, valence: str,
          *, decisions_path: Path = C.DECISIONS_LOG,
          reactions_path: Path = C.REACTIONS_LOG) -> int:
    """Deferred dogfood verdict (interaction-contract `know` mode): bind a verdict the owner
    authors *now* to a decision recorded *earlier*, by content-addressed ``decision_id``
    prefix — no model recompute, so it grades the answer exactly as it stood. The prefix
    resolves git-style: a unique match is required; zero or several is a loud error naming the
    options (invariant 3), never a silent pick. On a match it appends the §4.4 ``ReactionEvent``
    the fold joins, copying the decision's own ``question_id`` for linkage. The verdict is one
    bit — good/bad, no free text (the owner's prose is the loop's only expensive resource).
    Returns 0 on success, 2 on a resolve error. The fold (`reactions.load_reactions`) still
    decides what *moves*: this only records the owner's verdict — a report decision is
    recorded-not-folded, named so here. (The owner authors the bit; this is transcription.)"""
    try:
        decisions = DEC.read(decisions_path)
    except Exception as e:
        print(f"cannot read the decisions log: {e}", file=sys.stderr)
        return 2
    ids = sorted({d.decision_id for d in decisions
                  if d.decision_id and d.decision_id.startswith(did_prefix)})
    if not ids:
        print(f"no decision matches id prefix {did_prefix!r} "
              f"({len(decisions)} decisions on file)", file=sys.stderr)
        return 2
    if len(ids) > 1:
        shown = ", ".join(i[:12] for i in ids[:8])
        print(f"ambiguous id prefix {did_prefix!r} matches {len(ids)} decisions: "
              f"{shown}{' …' if len(ids) > 8 else ''} — give more characters", file=sys.stderr)
        return 2
    did = ids[0]
    d = [dd for dd in decisions if dd.decision_id == did][-1]  # latest row; context shared
    try:
        R.append(reactions_path, R.ReactionEvent(
            tx_time=O.now_iso(), question_id=d.question_id, decision_id=did,
            kind="verdict", valence=valence))
    except Exception as e:
        print(f"verdict not recorded: {e}", file=sys.stderr)
        return 2
    folds = d.chosen_action == "abstain" and valence in ("good", "bad")
    fate = ("folds into the utility posterior on the next gate run" if folds
            else "recorded — not folded (only abstain verdicts move the fold)")
    print(f"→ {valence.upper()} on {d.family}/{d.chosen_action} {did[:12]} — {fate}")
    return 0


# --- one question, end to end --------------------------------------------- #
def ask_once(conn: duckdb.DuckDBPyConnection, question: str, k: int,
             *, expand: bool = True, no_cache: bool = False,
             since: _date | None = None, until: _date | None = None,
             recent: bool = False) -> list[tuple[str, str]]:
    """Answer + render + capture. Returns the derive targets the answer's
    reports named as underived (doc_date and doc_subject alike — empty when
    neither filter ran) so the REPL can offer `/derive`."""
    text, cards, scores = answer(conn, question, k, expand=expand,
                                 no_cache=no_cache, since=since, until=until,
                                 recent=recent)
    audit = guard.audit(text, cards)  # pure and cheap — recomputed, never cached
    reports = [r for r in (TEMPORAL_LAST, SUBJECT_LAST) if r is not None]
    footer_lines = [r.footer for r in reports if r.footer]
    if INTENT_LAST is not None:
        footer_lines.append(INTENT_FOOTER.format(scope=INTENT_LAST))
    render(text, cards, scores, audit, footer="\n".join(footer_lines))
    capture(question, text, cards, scores, audit)
    return [t for r in reports for t in r.targets]


# --- /derive: explicit, demand-driven materialisation ---------------------- #
def run_derive(targets: list[tuple[str, str]]) -> None:
    """Materialise the named projection targets via pkm.derive (SPEC §18.11).
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


# --- GTD: the act ledger's knowledge projection, refreshed on demand ------- #
# system-design.md §5: before a question is answered, if the GTD ledger has
# moved past its projected state document, re-project and re-ingest it — the
# degenerate (deterministic, near-zero-cost) case of derive-when-stale, so the
# decision is simply "always derive". Nothing silent: the outcome is printed
# from this single-source table (drift-gated in tests/test_ask_gtd_refresh.py).
REFRESH_NOTES: dict[str, str] = {
    "refreshed": "gtd state refreshed @ event {n}",
    "failed": "gtd state refresh failed ({error}) — answering over the corpus as-is",
}


def gtd_stale() -> bool:
    """Cheap staleness check — ledger bytes vs the stamp in the state doc.
    No ledger (GTD unused) is never stale; a missing or unstamped doc is."""
    if not C.TASKS_LEDGER.exists():
        return False
    try:
        sha = hashlib.sha256(C.TASKS_LEDGER.read_bytes()).hexdigest()
        text = C.TASKS_STATE.read_text(encoding="utf-8")
    except (OSError, ValueError):  # unreadable/corrupt (incl. UnicodeDecodeError) = stale
        return True
    return knowledge.parse_stamp(text) != (sha, knowledge.RENDER_VERSION)


def _ensure_declared(root: Path, state: Path) -> None:
    """Idempotently declare the state doc in the pkm manifest (SPEC §8.1)."""
    from pkm.ingest import sources_yaml_path

    manifest = sources_yaml_path(root)
    data: Any = None
    if manifest.exists():
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {"version": 1, "sources": []}
    sources = data.setdefault("sources", [])
    declared = str(state)
    if any(isinstance(e, dict) and e.get("path") == declared for e in sources):
        return
    sources.append({"path": declared, "tags": ["gtd", "tasks"]})
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _reingest_state(root: Path, state: Path) -> None:
    """ingest → extract → rebuild-index for the one state document.
    The porcelain order is load-bearing (interaction contract invariant 3:
    a chunk pass whose index is stale silently misses new content)."""
    from pkm.catalogue import open_catalogue
    from pkm.config import load_config as pkm_load_config
    from pkm.extract import extract as pkm_extract
    from pkm.ingest import ingest_sources
    from pkm.retrieval import build_fts_index

    _ensure_declared(root, state)
    ingest_sources(root, only_paths=[state])
    cfg = pkm_load_config(C.PKM_CONFIG)
    prefix = hashlib.sha256(state.read_bytes()).hexdigest()[:16]
    pkm_extract(root, cfg, source_prefix=prefix)
    with open_catalogue(root) as wconn:
        build_fts_index(wconn)


def ensure_gtd_fresh() -> None:
    """Project + re-ingest the GTD state when stale; quiet no-op when fresh.
    The CALLER must hold no read-only catalogue connection (a writer and a
    reader cannot coexist — same contract as run_derive). Fail-open: never
    raises; the outcome is printed (REFRESH_NOTES), never silent."""
    if not gtd_stale():
        return
    try:
        events = ev.load(C.TASKS_LEDGER)
        knowledge.write_state(C.TASKS_LEDGER, C.TASKS_STATE)
        root = _pkm_root()
        if root is None:
            raise FileNotFoundError(f"unresolvable pkm root (config: {C.PKM_CONFIG})")
        _reingest_state(root, C.TASKS_STATE)
        print(REFRESH_NOTES["refreshed"].format(n=len(events)))
    except Exception as e:  # fail-open by contract (mirror run_derive)
        # The stamp is the freshness oracle and write_state runs BEFORE the
        # re-ingest, so a failure here must un-stamp the doc: a stamped doc
        # whose ingest failed would read as fresh, the retry would never
        # happen, and every answer in the window would silently serve stale
        # catalogue state. Un-stamped, the next question retries and the
        # failure is re-named each time — degraded, never silent.
        with contextlib.suppress(OSError):
            C.TASKS_STATE.unlink(missing_ok=True)
        print(REFRESH_NOTES["failed"].format(error=e))


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
    print(f"ask anything about your life — the grammar:\n{grammar_text()}\n")
    derive_targets: list[tuple[str, str]] = []
    while True:
        try:
            line = input("ask> ")
        except EOFError:
            print()
            return
        p = parse_line(line)
        if p.kind == "empty":
            continue
        if p.kind == "quit":
            return
        if p.kind == "error":
            print(f"{p.error}\n")
            continue
        if p.kind == "tell":
            remember(p.fact)
            continue
        if p.kind == "react":
            react(p.did, p.valence)
            continue
        if p.kind == "derive":
            if not derive_targets:
                print("nothing to derive — ask a /recent or /since question first\n")
                continue
            # A reader and a writer cannot coexist (§18.9): close, write, reopen.
            conn.close()
            try:
                run_derive(derive_targets)
                derive_targets = []
            finally:
                try:
                    conn = connect()
                except duckdb.Error as e:
                    # An extraction grabbed the catalogue mid-derive: close with
                    # the named error (invariant 3), never a traceback.
                    if not _is_lock_error(str(e)):
                        raise
                    print("corpus locked by extraction — REPL closing; "
                          "rerun bin/ask-live in a moment")
                    return
            print()
            continue
        assert p.kind == "ask", p.kind  # parse_line's kind space is closed
        if gtd_stale():
            # Same reader/writer dance as /derive: close, refresh, reopen.
            conn.close()
            try:
                ensure_gtd_fresh()
            finally:
                try:
                    conn = connect()
                except duckdb.Error as e:
                    if not _is_lock_error(str(e)):
                        raise
                    print("corpus locked by extraction — REPL closing; "
                          "rerun bin/ask-live in a moment")
                    return
        derive_targets = ask_once(conn, p.question, k, expand=expand,
                                  no_cache=no_cache, since=p.since,
                                  until=p.until, recent=p.recent)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=f"the line grammar (REPL and one-shot):\n"
                                        f"{grammar_text()}")
    ap.add_argument("question", nargs="*",
                    help="one line in the grammar below; omit for the REPL")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"top-k retrieval context (default {DEFAULT_K})")
    ap.add_argument("--no-expand", action="store_true",
                    help="disable cheap-model query expansion (raw-question BM25 baseline)")
    ap.add_argument("--no-cache", action="store_true",
                    help="recompute every stage instead of replaying cached derivations "
                         "(recording stays write-once — existing derivations stand)")
    args = ap.parse_args(argv)
    expand = not args.no_expand

    # One-shot argv is the SAME grammar as a REPL line (invariant 1). The corpus-free
    # kinds are handled BEFORE any catalogue I/O: /tell works even while an extraction
    # holds the lock; a grammar error never costs a connection.
    p = parse_line(" ".join(args.question)) if args.question else None
    if p is not None and p.kind == "empty":
        p = None  # a blank argv question means the REPL, same as no question
    if p is not None:
        if p.kind == "error":
            print(p.error, file=sys.stderr)
            return 2
        if p.kind == "derive":
            print("/derive needs the targets a prior answer named — REPL only",
                  file=sys.stderr)
            return 2
        if p.kind == "tell":
            remember(p.fact)
            return 0
        if p.kind == "react":
            return react(p.did, p.valence)
        if p.kind == "quit":
            return 0

    # Opportunistic catalogue reconciliation (SPEC §18.9): insert the rows for any
    # file-first derivations recorded by earlier sessions, BEFORE our read-only connection
    # opens (a writer and a reader cannot coexist). A held lock just means next time.
    root = _pkm_root()
    if root is not None:
        # best-effort by contract; on any failure the files stay authoritative
        with contextlib.suppress(Exception):
            D.reconcile(root)

    # Demand-led GTD refresh (system-design.md §5), BEFORE the read-only
    # connection opens: a one-shot question and the REPL's first question both
    # see fresh act-layer state. Mid-REPL changes are caught per-question.
    ensure_gtd_fresh()

    try:
        conn = connect()
    except duckdb.Error as e:
        if _is_lock_error(str(e)):
            print("corpus locked by extraction, retry in a moment", file=sys.stderr)
            return 2
        raise

    if p is not None:
        ask_once(conn, p.question, args.k, expand=expand,
                 no_cache=args.no_cache, since=p.since, until=p.until,
                 recent=p.recent)
    else:
        repl(conn, args.k, expand=expand, no_cache=args.no_cache)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
