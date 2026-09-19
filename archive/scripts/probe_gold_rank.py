#!/usr/bin/env python3
"""Where does the gold rank in a WIDE lexical pool? — the reranker precondition probe.

The triage harness records ``gold_in_topk`` over the final k cards, but not how deep the
gold sits in the lexical ranking. That depth is the precondition for a reranker: a reranker
can only rescue a retrieval_miss whose gold is somewhere in the over-fetch pool. So this
probe — ZERO model cost, pure FTS — runs the production query (expansion + build_query) for
each question and reports the gold's best rank in a wide deduped pool, partitioning the
retrieval_miss class into:

    rank <= k          already retrieved (not a miss at this depth)
    k < rank <= POOL   reranker-addressable — a smarter ranker over the pool could promote it
    rank > POOL       beyond lexical reach — only semantic retrieval (or it is a coverage gap)

Cross-references the current $LIFE_AGENT_KB/eval/triage/triage.jsonl buckets. Prints only
ids + ranks (no gold / question text) so no PII enters the console.

    uv run --project . python scripts/probe_gold_rank.py [--config PATH] [--k N] [--pool N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import chunk_matches_any
from run_eval import _kb_root, load_questions


def _gold_rank(pool: list[dict], gold: str, variants: list[str]) -> int | None:
    """1-based rank of the first pool chunk that carries the gold value, or None."""
    for i, h in enumerate(pool):
        if chunk_matches_any(gold, variants, [h["chunk_text"]]):
            return i + 1
    return None


def _band(rank: int | None, k: int, pool_n: int) -> str:
    if rank is None:
        return f">{pool_n}"
    if rank <= k:
        return f"<={k}"
    return f"{k}<·<={pool_n}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "PKM_CONFIG", str(Path("~/.config/life-agent/pkm.yaml").expanduser())))
    parser.add_argument("--k", type=int, default=20, help="production top-k cutoff")
    parser.add_argument("--pool", type=int, default=200, help="wide pool depth to probe")
    args = parser.parse_args()

    import duckdb
    import yaml

    questions = load_questions()
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    db_path = Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("INSTALL fts; LOAD fts;")

    import ask

    triage_path = _kb_root() / "eval" / "triage" / "triage.jsonl"
    buckets: dict[str, str] = {}
    causes: dict[str, str] = {}
    if triage_path.exists():
        for line in triage_path.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            buckets[p["id"]] = p["bucket"]
            causes[p["id"]] = p.get("cause") or ""

    print(f"Probing gold lexical rank (k={args.k}, pool={args.pool}) over "
          f"{len(questions)} questions …\n")
    print(f"{'id':<8} {'bucket':<17} {'cause':<15} {'rank':>6}  band")
    band_counts: Counter[str] = Counter()
    rmiss_bands: Counter[str] = Counter()
    for q in questions:
        gold = q.get("answer", "")
        if not gold:
            continue
        variants = q.get("answer_variants", [])
        terms = ask._expand_terms(q["question"], root=ask._pkm_root())
        query = ask.build_query(q["question"], terms)
        pool = ask._retrieve_set(conn, query, args.pool)
        rank = _gold_rank(pool, gold, variants)
        band = _band(rank, args.k, args.pool)
        band_counts[band] += 1
        bucket = buckets.get(q["id"], "?")
        cause = causes.get(q["id"], "")
        if cause == "retrieval_miss":
            rmiss_bands[band] += 1
        rank_s = str(rank) if rank is not None else "—"
        print(f"{q['id']:<8} {bucket:<17} {cause:<15} {rank_s:>6}  {band}")

    print("\nBands (all answerable): "
          + " · ".join(f"{b}={c}" for b, c in sorted(band_counts.items())))
    if rmiss_bands:
        print("retrieval_miss only:    "
              + " · ".join(f"{b}={c}" for b, c in sorted(rmiss_bands.items())))
        addressable = sum(c for b, c in rmiss_bands.items() if b.startswith(f"{args.k}<"))
        print(f"\n→ reranker-addressable retrieval_misses (gold in pool, ranked out of "
              f"top-{args.k}): {addressable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
