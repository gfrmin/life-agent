#!/usr/bin/env python3
"""score_typed — the typed arm alone over a question set, for a set with no recorded oracle.

Drives every question through the executor surface (``ask.answer_via_executor``: the
bridge's host decider), grades the reply by exact match on the gold (the same
``run_eval._typed_response_executor`` the gate uses), and writes one JSONL row per question
under ``$LIFE_AGENT_KB/eval/typed/``. ``eval/score.py`` scores it as a ``typed`` set. A
question whose gold chunk is absent from this machine's catalogue is censored, as in the gate.

Point the run at a bridge with ``LIFE_AGENT_BRIDGE_URL``. Decisions carry a ``gate-`` run id,
so the production readout excludes them. Prints counts only.

    uv run python scripts/score_typed.py --questions $LIFE_AGENT_KB/eval/questions_generated.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask
import run_eval as RE

from life_agent.core import config as CFG


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--out", default=None, help="default: $LIFE_AGENT_KB/eval/typed/<run>.jsonl")
    a = ap.parse_args(argv)
    if not ask._executor_ready():
        print(f"REFUSED: the bridge at {ask.EXECUTOR_BRIDGE} is not ready", file=sys.stderr)
        return 2
    questions = RE.load_questions(a.questions)
    run_id = f"gate-typed-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    out = Path(a.out) if a.out else CFG.KB / "eval" / "typed" / f"{run_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = ask.connect()
    try:
        available = RE.gold_available(conn, questions)
    finally:
        conn.close()
    tally: Counter[str] = Counter()
    ask.EXECUTOR_RUN_ID = run_id
    try:
        with out.open("w", encoding="utf-8") as fh:
            for q in questions:
                qid = str(q["id"])
                ask.answer_via_executor(q["question"], a.k)
                view = ask.EXECUTOR_VIEW_LAST
                if view is None:
                    raise SystemExit(f"executor view missing for {qid} — the bridge went "
                                     "down mid-run; the reading is void")
                ok = available.get(qid, True)
                r = RE._typed_response_executor(view, q, available=ok)
                fh.write(json.dumps({
                    "question_id": qid, "answerable": bool(q.get("answerable", True)),
                    "run_id": run_id, "censored": not ok,
                    "typed": {"action": r.action, "correct": r.correct,
                              "cost_usd": r.cost_usd, "withheld": r.withheld,
                              "applied": list(r.applied),
                              "metered_usd": r.metered_usd}}) + "\n")
                fh.flush()
                tally["censored" if not ok else ("declined" if r.correct is None
                                                 else "right" if r.correct else "wrong")] += 1
    finally:
        ask.EXECUTOR_RUN_ID = None
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(" · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
          + f" → $LIFE_AGENT_KB/{out.relative_to(CFG.KB)} (sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
