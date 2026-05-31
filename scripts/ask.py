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

Run (in the pkm env, for pkm.retrieval + duckdb):
    bin/ask-live                      # interactive REPL
    bin/ask-live "what is my ID?"     # answer once, then prompt for a verdict
    bin/ask-live --k 12               # wider retrieval context
"""
from __future__ import annotations

import argparse
import re
import readline  # noqa: F401  -- enables line editing / history at the input() prompts
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import yaml

# Reuse the comparison harness (sibling dir): metered LLM call, secret lookup, citation
# instruction, source rendering, and the resolved KB / PKM_CONFIG paths.
sys.path.insert(0, str(Path(__file__).resolve().parent / "comparison"))
import _common as C  # noqa: E402

DEFAULT_K = 8  # matches phase1_answer.py's synthesis-context default

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


# --- retrieval over the LIVE corpus --------------------------------------- #
def connect() -> duckdb.DuckDBPyConnection:
    """Open the live catalogue read-only (so a running extraction never blocks us)
    and load FTS. Mirrors phase1_answer._connect()."""
    cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
    db = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


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


def retrieve(conn: duckdb.DuckDBPyConnection, question: str, k: int) -> list[tuple[C.SourceCard, float]]:
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


def answer(conn: duckdb.DuckDBPyConnection, question: str,
           k: int, *, expand: bool = True) -> tuple[str, list[C.SourceCard], dict[int, float]]:
    """Retrieve then synthesise a cited answer. Retrieval uses the question expanded with
    cheap-model keywords by default (``expand=False`` for the raw-question A/B baseline).
    Returns (answer_text, cards, {card_n: score})."""
    terms = _expand_terms(question) if expand else ""
    if terms:
        print(f"  ↳ expanded: {terms}")
    hits = retrieve(conn, build_query(question, terms), k)
    cards = [c for c, _ in hits]
    scores = {c.n: s for c, s in hits}
    if not cards:
        return ("No matching sources were retrieved from the corpus.", [], {})
    system = ("You are the owner's personal assistant. Answer ONLY from the numbered SOURCES. "
              + C.CITATION_INSTRUCTION)
    user = f"QUESTION: {question}\n\nSOURCES:\n{C.render_sources_block(cards)}"
    r = C.anthropic_complete(system, user, max_tokens=600)
    return (r.text.strip(), cards, scores)


# --- presentation --------------------------------------------------------- #
def _sources_inline(cards: list[C.SourceCard], scores: dict[int, float]) -> str:
    return ", ".join(f"{Path(c.origin).name}({scores.get(c.n, 0.0):.2f})" for c in cards)


def render(text: str, cards: list[C.SourceCard], scores: dict[int, float]) -> None:
    print(f"\n{text}\n")
    if cards:
        print("sources:")
        for c in cards:
            print(f"  [{c.n}] {Path(c.origin).name}  ({scores.get(c.n, 0.0):.2f})")
    print()


# --- feedback capture (the dogfood signal) -------------------------------- #
def log_entry(question: str, text: str, cards: list[C.SourceCard],
              scores: dict[int, float], verdict: str, note: str, *, when: str) -> str:
    """Render one dogfood log block. Pure (no I/O, no clock) so it is unit-tested."""
    lines = [
        f"## {when}  {verdict}",
        f"Q: {question}",
        f"A: {text}",
    ]
    if cards:
        lines.append(f"sources: {_sources_inline(cards, scores)}")
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


def capture(question: str, text: str, cards: list[C.SourceCard], scores: dict[int, float]) -> None:
    """One-key verdict (+ optional note). Frictionless: `g` logs immediately; `b`/`n`
    prompt for a note; Enter skips."""
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
                               when=f"{datetime.now():%H:%M}"))
    print(f"→ logged {verdict} to {log}\n")


# --- one question, end to end --------------------------------------------- #
def ask_once(conn: duckdb.DuckDBPyConnection, question: str, k: int, *, expand: bool = True) -> None:
    text, cards, scores = answer(conn, question, k, expand=expand)
    render(text, cards, scores)
    capture(question, text, cards, scores)


# --- REPL ----------------------------------------------------------------- #
def repl(conn: duckdb.DuckDBPyConnection, k: int, *, expand: bool = True) -> None:
    print("ask anything about your life — Ctrl-D or /q to quit\n")
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
        ask_once(conn, question, k, expand=expand)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="*", help="ask once non-interactively; omit for the REPL")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help=f"top-k retrieval context (default {DEFAULT_K})")
    ap.add_argument("--no-expand", action="store_true",
                    help="disable cheap-model query expansion (raw-question BM25 baseline)")
    args = ap.parse_args(argv)
    expand = not args.no_expand

    try:
        conn = connect()
    except duckdb.Error as e:
        msg = str(e).lower()
        if "lock" in msg or "conflict" in msg or "being used" in msg:
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
