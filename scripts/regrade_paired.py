#!/usr/bin/env python3
"""regrade_paired — re-grade a recorded gate archive by exact match (the MVP board's grader).

A gate run's ``paired-gate-*.jsonl`` carries each arm's graded outcome but not the answer it
graded. The answers are on disk: the typed arm's is the leader candidate of its logged
report decision (``calibration/decisions.jsonl``, joined by run id and question id), and the
oracle's is the replayed run's stored answer. This re-grades both with
``gate.realised_report`` (token-boundary exact match on the gold) and writes a new archive
beside the old one; actions, spend and withheld reasons are carried unchanged. Prints counts
only.

    uv run python scripts/regrade_paired.py PAIRED --run-id gate-20260826T083356 \\
        --replay $LIFE_AGENT_KB/eval/fairfight/ff-v2-delib-20260719 \\
        --questions $LIFE_AGENT_KB/eval/questions_v2.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_eval as RE

from life_agent.core import config as CFG
from life_agent.core import decisions as DEC
from life_agent.core import gate as GATE


def leader(decision: dict) -> str:
    ps = decision["posterior_summary"]
    c = ps["credences"]
    return str(ps["candidates"][max(range(len(c)), key=c.__getitem__)])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paired")
    ap.add_argument("--run-id", required=True, help="the gate run's id (decision-log prefix)")
    ap.add_argument("--replay", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--decisions", default=str(CFG.DECISIONS_LOG))
    a = ap.parse_args(argv)
    src = Path(a.paired)
    out = src.with_name(src.stem + "-exact.jsonl")
    questions = {str(q["id"]): q for q in RE.load_questions(a.questions)}
    replay = RE.load_replay_answers(Path(a.replay))
    last: dict[str, dict] = {}
    with Path(a.decisions).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                if str(d.get("run_id", "")).startswith(a.run_id):
                    last[d["question_id"]] = d
    tally: Counter[str] = Counter()
    lines = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        q = questions[row["question_id"]]
        gold, variants = q.get("answer", ""), q.get("answer_variants", [])
        typed = dict(row["typed"])
        if typed["action"] in GATE.ASSERT_ACTIONS:
            d = last.get(DEC.question_id(q["question"]))
            if d is None or d["chosen_action"] not in GATE.ASSERT_ACTIONS:
                raise SystemExit(f"{row['question_id']}: no logged report under {a.run_id}")
            typed["correct"] = GATE.realised_report([leader(d)], gold, variants)
        mono = dict(row["mono"])
        r = RE._replay_response(replay[row["question_id"]], q)
        if r.action != mono["action"]:
            raise SystemExit(f"{row['question_id']}: replay action {r.action} != archived "
                             f"{mono['action']}")
        mono["correct"] = r.correct
        for arm, resp in (("typed", typed), ("mono", mono)):
            tally[f"{arm}_{'declined' if resp['correct'] is None else resp['correct']}"] += 1
        lines.append(json.dumps({**row, "typed": typed, "mono": mono, "grading": "exact"}))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(" · ".join(f"{k} {v}" for k, v in sorted(tally.items()))
          + f" → {out.name} (sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
