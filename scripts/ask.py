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
import os
import re
import readline  # noqa: F401  -- enables line editing / history at the input() prompts
import sys
from datetime import datetime
from pathlib import Path

import citation_guard as guard  # sibling script: deterministic citation-faithfulness gate
import duckdb
import yaml

# Shared infra (metered LLM call, secret lookup, source rendering, the resolved KB /
# PKM_CONFIG paths) lives in the installed life_agent package (see life-agent's pyproject).
import life_agent.core as C
from life_agent import owner

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
def connect() -> duckdb.DuckDBPyConnection:
    """Open the live catalogue read-only (so a running extraction never blocks us)
    and load FTS. Mirrors phase1_answer._connect()."""
    cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
    db = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


def _is_lock_error(msg: str) -> bool:
    """True if a DuckDB error message means the catalogue is held by another process (a running
    extraction). Pure, so it's unit-tested in place of an un-reproducible live lock."""
    m = msg.lower()
    return "lock" in m or "conflict" in m or "being used" in m


def _clean_terms(raw: str) -> str:
    """Pure: flatten an LLM expansion reply to a clean space-separated term string.
    Drops bullets/commas/quotes/newlines; keeps Unicode word chars (so Hebrew survives)."""
    return " ".join(re.sub(r"[^\w]+", " ", raw, flags=re.UNICODE).split())


def build_query(question: str, terms: str) -> str:
    """Pure: combine the raw question with expansion terms into one disjunctive BM25
    query. The original words are ALWAYS retained, so expansion can only *add* recall —
    a question that already hit on a rare literal term keeps its hit. Empty terms
    (expansion failed/disabled) leaves the raw-question search unchanged."""
    return f"{question} {terms}".strip() if terms else question


def _expand_terms(question: str, *, model: str = EXPAND_MODEL) -> str:
    """Impure edge: ask a cheap model for extra BM25 keywords. Returns a space-joined
    term string, or '' on any failure (caller falls back to the raw question — expansion
    must never break the REPL)."""
    try:
        r = C.anthropic_complete(EXPAND_SYSTEM, question, model=model, max_tokens=120)
    except SystemExit:
        return ""
    return _clean_terms(r.text)


def retrieve(conn: duckdb.DuckDBPyConnection, question: str,
             k: int) -> list[tuple[C.SourceCard, float]]:
    """FTS the given query over the whole corpus; dedupe by chunk text keeping the best
    score; return the top-k as (numbered SourceCard, score) pairs. No snapshot filter."""
    from pkm.retrieval import search

    best: dict[str, object] = {}
    for h in search(conn, question, k=k * 4):  # over-fetch, then dedupe down to k
        prev = best.get(h.chunk_text)
        if prev is None or h.score > prev.score:  # type: ignore[attr-defined]
            best[h.chunk_text] = h
    top = sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]
    return [(C.SourceCard(n=i + 1, text=h.chunk_text.strip(), origin=h.source_path), h.score)
            for i, h in enumerate(top)]


def retrieval_is_weak(scores: dict[int, float], *, floor: float, min_hits: int) -> bool:
    """Pure: True when fewer than ``min_hits`` retrieved chunks cleared ``floor``. Empty scores
    (zero retrieval) are weak by definition. The confabulation guard for the synthesis step."""
    return sum(1 for s in scores.values() if s >= floor) < min_hits


def answer(conn: duckdb.DuckDBPyConnection, question: str,
           k: int, *, expand: bool = True) -> tuple[str, list[C.SourceCard], dict[int, float]]:
    """Retrieve then synthesise a cited answer. The authoritative owner profile (who "I"/"my"
    is) is prepended as an OWNER block so the model never mistakes a relative's document for the
    owner's. Retrieval uses the question expanded with cheap-model keywords by default
    (``expand=False`` for the raw-question A/B baseline).
    Returns (answer_text, cards, {card_n: score})."""
    profile = owner.load_profile()
    terms = _expand_terms(question) if expand else ""
    if terms:
        print(f"  ↳ expanded: {terms}")
    hits = retrieve(conn, build_query(question, terms), k)
    cards = [c for c, _ in hits]
    scores = {c.n: s for c, s in hits}
    # Abstain on weak retrieval (subsumes the zero-hit case) unless the owner profile can answer
    # an identity question on its own. Returns the weak cards so the dogfood loop sees the misses.
    if retrieval_is_weak(scores, floor=WEAK_SCORE_FLOOR, min_hits=MIN_STRONG_HITS) and not profile:
        return (ABSTENTION, cards, scores)
    blocks = []
    if profile:
        blocks.append(f'OWNER (authoritative — who "I"/"my" refers to):\n{profile}')
    blocks.append(f"SOURCES:\n{C.render_sources_block(cards) if cards else '(none retrieved)'}")
    user = f"QUESTION: {question}\n\n" + "\n\n".join(blocks)
    r = C.anthropic_complete(ANSWER_SYSTEM, user, max_tokens=600)
    return (r.text.strip(), cards, scores)


# --- presentation --------------------------------------------------------- #
def _sources_inline(cards: list[C.SourceCard], scores: dict[int, float]) -> str:
    return ", ".join(f"{Path(c.origin).name}({scores.get(c.n, 0.0):.2f})" for c in cards)


def render(text: str, cards: list[C.SourceCard], scores: dict[int, float],
           audit: guard.CitationAudit | None = None) -> None:
    print(f"\n{text}\n")
    if cards:
        print("sources:")
        for c in cards:
            print(f"  [{c.n}] {Path(c.origin).name}  ({scores.get(c.n, 0.0):.2f})")
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
             *, expand: bool = True) -> None:
    text, cards, scores = answer(conn, question, k, expand=expand)
    audit = guard.audit(text, cards)
    render(text, cards, scores, audit)
    capture(question, text, cards, scores, audit)


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
def repl(conn: duckdb.DuckDBPyConnection, k: int, *, expand: bool = True) -> None:
    print("ask anything about your life — '/i <fact>' to teach me about you, "
          "Ctrl-D or /q to quit\n")
    while True:
        try:
            question = input("ask> ").strip()
        except EOFError:
            print()
            return
        if not question:
            continue
        if question in ("/q", "/quit", "/exit"):
            return
        if question.startswith(("/i ", "/me ")):
            remember(question.split(" ", 1)[1])
            continue
        ask_once(conn, question, k, expand=expand)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="*", help="ask once non-interactively; omit for the REPL")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help=f"top-k retrieval context (default {DEFAULT_K})")
    ap.add_argument("--no-expand", action="store_true",
                    help="disable cheap-model query expansion (raw-question BM25 baseline)")
    ap.add_argument("--tell", metavar="FACT",
                    help="record an authoritative owner fact (e.g. 'My name is …') and exit")
    args = ap.parse_args(argv)
    expand = not args.no_expand

    # Teaching is corpus-free: it works even while an extraction holds the catalogue lock.
    if args.tell:
        remember(args.tell)
        return 0

    try:
        conn = connect()
    except duckdb.Error as e:
        if _is_lock_error(str(e)):
            print("corpus locked by extraction, retry in a moment", file=sys.stderr)
            return 2
        raise

    if args.question:
        ask_once(conn, " ".join(args.question), args.k, expand=expand)
    else:
        repl(conn, args.k, expand=expand)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
