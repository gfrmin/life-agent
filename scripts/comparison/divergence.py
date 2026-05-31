#!/usr/bin/env python3
"""divergence.py — the engineering-property metrics (SPEC-comparison.md §7).

(a) Novel-query cost  — per-query input-token cost: Phase 0 re-stuffs the whole wiki every query;
    Phase 1 sends only top-k chunks. Measured from the recorded answer metering.
(c) Reproducibility   — re-run Phase-1 retrieval and confirm it returns byte-identical chunk sets
    (content-addressed determinism). Phase 0's compile is not bit-reproducible (§7c), stated.
(b) Incremental update — structural cost with measured anchors: Phase 0 has no incremental path (a
    source edit forces a recompile — anchor = the measured compile cost); Phase 1 re-ingests only the
    changed content-addressed object, leaving the other ~953 as cache hits (0 API tokens).

Run:  uv run --project ../pkm python scripts/comparison/divergence.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402
import phase1_answer as P1  # noqa: E402


def _read_jsonl(name: str) -> dict[str, dict]:
    rows = [json.loads(l) for l in (C.COMPARISON_DIR / name).read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["question_id"]: r for r in rows}


def novel_query_cost(p0: dict, p1: dict) -> dict:
    a0 = [r["in_tokens"] for r in p0.values() if r["in_tokens"]]
    a1 = [r["in_tokens"] for r in p1.values() if r["in_tokens"]]
    m0 = round(sum(a0) / len(a0)) if a0 else 0
    m1 = round(sum(a1) / len(a1)) if a1 else 0
    # order-N specifically (the divergence bucket)
    return {"phase0_avg_in": m0, "phase1_avg_in": m1,
            "ratio": round(m0 / m1, 1) if m1 else None}


def reproducibility(p1: dict) -> dict:
    """Re-run Phase-1 retrieval; confirm identical chunk sets vs the recorded run."""
    conn = P1._connect()
    s_paths = C.snapshot_paths()
    qs = {q["id"]: q for q in C.scored_questions()}
    identical = mismatched = 0
    for qid, rec in p1.items():
        cards = P1.retrieve_S(conn, qs[qid]["search_queries"], s_paths, 8)
        now = [c.text for c in cards]
        was = [c["text"] for c in rec["sources"]]
        if now == was:
            identical += 1
        else:
            mismatched += 1
    return {"phase1_deterministic": mismatched == 0,
            "identical": identical, "mismatched": mismatched,
            "phase0_note": "compile NOT bit-reproducible (temp-0 on hosted API, §7c)"}


def incremental_update(compile_meta: dict) -> dict:
    ctot = (compile_meta.get("in_tokens", 0) + compile_meta.get("out_tokens", 0))
    return {
        "phase0_note": f"no incremental path — a source edit forces recompile ≈ {ctot} tokens "
                       f"({compile_meta.get('wall_seconds')}s) for the whole wiki",
        "phase1_note": "re-ingest only the changed content-addressed object; the other "
                       f"~{compile_meta.get('n_sources', 0) - 1} objects stay cache hits "
                       "(0 API tokens; local re-embed only)",
    }


def main() -> int:
    p0 = _read_jsonl("phase0_answers.jsonl")
    p1 = _read_jsonl("phase1_answers.jsonl")
    compile_meta = json.loads((C.COMPARISON_DIR / "compile_meta.json").read_text(encoding="utf-8"))

    out = {
        "novel_query_cost": novel_query_cost(p0, p1),
        "reproducibility": reproducibility(p1),
        "incremental_update": incremental_update(compile_meta),
        "ceilings": {
            "phase0_corpus_size_ceiling": "full S (~345k chunks) is uncompilable (§7d)",
            "phase1_recall_ceiling": "fixed k=8 cannot widen recall within a wide aggregation query (§7e)",
        },
    }
    (C.COMPARISON_DIR / "divergence.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
