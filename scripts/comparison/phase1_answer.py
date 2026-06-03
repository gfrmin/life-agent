#!/usr/bin/env python3
"""phase1_answer.py — the Phase-1 (retrieve) answerer (SPEC-comparison.md §3).

For each question: FTS over the live pkm catalogue, filter every hit to the pinned S manifest
(over-fetch then drop non-S), take the top-k chunks, and have the PINNED answer model synthesise
an answer that cites [n] into those chunks. Meters tokens / wall-clock / cache-hit. Differs from
Phase 0 ONLY in context assembly (top-k chunks vs whole wiki).

Run:  uv run --project . python scripts/comparison/phase1_answer.py [--k 8]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C

OVERFETCH = 300  # fetch this many live hits per query, THEN filter to S, then take top-k


def _connect():
    cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
    db = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db), read_only=True)
    conn.execute("INSTALL fts; LOAD fts;")
    return conn


def retrieve_s(conn, queries: list[str], s_paths: set[str], k: int) -> list[C.SourceCard]:
    """Union FTS over queries, filter to S, dedupe by chunk text, keep top-k by score."""
    from pkm.retrieval import search

    seen: dict[str, float] = {}
    best: dict[str, object] = {}
    for q in queries:
        for h in search(conn, q, k=OVERFETCH):
            if h.source_path not in s_paths:
                continue
            key = h.chunk_text
            if key not in seen or h.score > seen[key]:
                seen[key] = h.score
                best[key] = h
    top = sorted(best.values(), key=lambda h: h.score, reverse=True)[:k]
    return [C.SourceCard(n=i + 1, text=h.chunk_text.strip(), origin=h.source_path)
            for i, h in enumerate(top)]


def answer_one(conn, q: dict, s_paths: set[str], k: int) -> C.Answer:
    cards = retrieve_s(conn, q["search_queries"], s_paths, k)
    if not cards:
        return C.Answer("phase1", q["id"], "No matching sources were retrieved from the corpus.",
                        sources=[], cache_hit=True)
    system = ("You are the owner's personal assistant. Answer ONLY from the numbered SOURCES. "
              + C.CITATION_INSTRUCTION)
    user = f"QUESTION: {q['question']}\n\nSOURCES:\n{C.render_sources_block(cards)}"
    r = C.anthropic_complete(system, user, max_tokens=600)
    return C.Answer("phase1", q["id"], r.text.strip(), sources=cards,
                    in_tokens=r.in_tokens, out_tokens=r.out_tokens, seconds=r.seconds,
                    cache_hit=True)  # retrieval over an already-built index = warm cache


def _serialise(a: C.Answer) -> dict:
    d = dataclasses.asdict(a)
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--k", type=int, default=8, help="top-k chunks as synthesis context")
    args = ap.parse_args()

    questions = C.scored_questions()
    s_paths = C.snapshot_paths()
    conn = _connect()
    C.COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    out = C.COMPARISON_DIR / "phase1_answers.jsonl"

    answers = []
    for q in questions:
        a = answer_one(conn, q, s_paths, args.k)
        answers.append(a)
        print(f"  {a.question_id}: {len(a.sources)} src, {a.out_tokens} out tok, {a.seconds:.1f}s")
    out.write_text("\n".join(json.dumps(_serialise(a), ensure_ascii=False) for a in answers),
                   encoding="utf-8")
    tot_in = sum(a.in_tokens for a in answers)
    tot_out = sum(a.out_tokens for a in answers)
    print(f"\nwrote {out}  ({len(answers)} answers; {tot_in} in / {tot_out} out tokens, "
          f"{C.ANSWER_MODEL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
