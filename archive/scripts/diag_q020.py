#!/usr/bin/env python3
"""Throwaway: diagnose ONE confident-wrong — what did Opus assert, was the gold retrievable,
is it a hallucination-under-absence or a misread? Prints PII to the console (diagnosis only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches, chunk_matches_any
from probe_opus_answer import _ask_opus
from run_eval import load_questions

QID = sys.argv[1] if len(sys.argv) > 1 else "q-020"


def main() -> int:
    import duckdb
    import yaml

    q = next(x for x in load_questions() if x["id"] == QID)
    gold = q.get("answer", "")
    variants = q.get("answer_variants", [])
    print(f"== {QID}")
    print(f"  question: {q['question']}")
    print(f"  gold:     {gold!r}   variants={variants}")
    print(f"  subject:  {q.get('subject')}   notes/proof: {q.get('notes','')}")

    cfg = yaml.safe_load(Path("~/.config/life-agent/pkm.yaml").expanduser().read_text())
    conn = duckdb.connect(str(Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"))
    conn.execute("INSTALL fts; LOAD fts;")
    import ask
    terms = ask._expand_terms(q["question"], root=ask._pkm_root())
    query = ask.build_query(q["question"], terms)
    pool = ask._retrieve_set(conn, query, 200)
    rank = next((i + 1 for i, h in enumerate(pool)
                 if chunk_matches_any(gold, variants, [h["chunk_text"]])), None)
    print(f"\n  gold lexical rank in pool(200): {rank}   "
          f"(in top-20 Opus read: {rank and rank <= 20})")

    obj, _ = _ask_opus(q["question"], pool, model="claude-opus-4-8", k=20)
    val = obj.get("value")
    print(f"\n  OPUS said: value={val!r}  confidence={obj.get('confidence')}  "
          f"as_of={obj.get('as_of')}")
    print(f"  matches gold: {bool(val) and answer_matches(gold, variants, str(val))}")
    # is opus's value a chunk it read, and is the gold anywhere in the top-20?
    top20 = [h["chunk_text"] for h in pool[:20]]
    print(f"  gold present in the top-20 Opus read: {chunk_matches_any(gold, variants, top20)}")
    if val:
        here = [i + 1 for i, t in enumerate(top20) if answer_matches(str(val), [], t)]
        print(f"  opus's value appears in top-20 chunks at positions: {here}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
