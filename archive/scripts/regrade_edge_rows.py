#!/usr/bin/env python3
"""Re-grade logged eval_edge rows after a gold correction — append-only (§8/§14).

A gold correction (q2-018/q2-105 on 2026-08-14, q2-053 on 2026-08-17) changes the truth
of firings the outcomes log has ALREADY graded, and the log cannot be edited: it is
append-only, and the gate writer dedups on §18.9 lineage so the same firing is never
graded twice. Left alone, the stale rows stay reliability-curve food forever (five
CORRECT rows for a fax number that was the tel). This tool re-grades every eval_edge row
of the named questions against the CURRENT gold with the same token-boundary matcher the
writer used, and for each row whose grade moved appends a superseding row — same edge,
lineage, probability and claim; corrected grade; ``signals.regrade_of`` naming the
superseded row's tx_time and ``signals.reason`` the correction. ``calibration.
edge_outcomes_from_log`` folds the latest row per (edge, lineage). Rows without lineage
cannot be superseded and are NAMED, never silently skipped. Dry-run by default.

Usage:
  uv run python scripts/regrade_edge_rows.py --question q2-053 --reason "..." [--apply]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_grading import answer_matches
from run_eval import load_questions

import life_agent.core.outcomes as O
from life_agent.core import OUTCOMES_LOG


def latest_per_lineage(events: list[O.OutcomeEvent]) -> list[O.OutcomeEvent]:
    """The rows still in force: the latest per (edge, lineage key); lineage-less rows all
    kept — the same rule ``calibration.edge_outcomes_from_log`` folds by."""
    rows: list[O.OutcomeEvent] = []
    slot: dict[tuple[str, str], int] = {}
    for ev in events:
        edge = str(ev.instrument_identity.get("edge") or "")
        keys = [(edge, k) for k in ev.lineage_keys]
        hit = next((slot[k] for k in keys if k in slot), None)
        if hit is None:
            rows.append(ev)
            for k in keys:
                slot[k] = len(rows) - 1
        else:
            rows[hit] = ev
            for k in keys:
                slot[k] = hit
    return rows


def plan_regrades(events: list[O.OutcomeEvent], questions: dict[str, dict], *,
                  reason: str, run_id: str) -> tuple[list[O.OutcomeEvent], list[O.OutcomeEvent]]:
    """Pure: ``(to_append, unfixable)`` for the eval_edge rows of ``questions`` (id → record).
    A row is re-graded by ``answer_matches(gold, variants, claim)`` — the writer's own
    scale (run_eval.edge_outcome). Only rows whose grade MOVES produce a superseding row;
    a moved row without lineage is unfixable (nothing to supersede by) and is returned
    for naming."""
    to_append: list[O.OutcomeEvent] = []
    unfixable: list[O.OutcomeEvent] = []
    in_force = latest_per_lineage([ev for ev in events if ev.grader == "eval_edge"
                                   and ev.question_id in questions])
    for ev in in_force:
        q = questions[ev.question_id]
        gold = str(q.get("answer") or "")
        if not gold:
            continue
        correct = answer_matches(gold, list(q.get("answer_variants", [])), ev.claim)
        grade = "CORRECT" if correct else "INCORRECT"
        if grade == ev.grade:
            continue
        if not ev.lineage_keys:
            unfixable.append(ev)
            continue
        to_append.append(O.OutcomeEvent(
            tx_time=O.now_iso(), run_id=run_id, question_id=ev.question_id,
            claim=ev.claim, construct=ev.construct, grade=grade, grader="eval_edge",
            instrument_identity=dict(ev.instrument_identity),
            lineage_keys=tuple(ev.lineage_keys), probability=ev.probability,
            signals={**(ev.signals or {}), "regrade_of": ev.tx_time,
                     "superseded_grade": ev.grade, "reason": reason}))
    return to_append, unfixable


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--question", action="append", required=True, metavar="ID")
    ap.add_argument("--reason", required=True,
                    help="the correction being applied (goes on every superseding row)")
    ap.add_argument("--questions", type=Path, default=None)
    ap.add_argument("--log", type=Path, default=OUTCOMES_LOG)
    ap.add_argument("--run-id", default=None,
                    help="run_id stamped on the superseding rows (default regrade-<date>)")
    ap.add_argument("--apply", action="store_true", help="append (default: dry-run)")
    args = ap.parse_args(argv)

    qs = {str(q["id"]): q for q in
          (load_questions(args.questions) if args.questions else load_questions())}
    missing = [i for i in args.question if i not in qs]
    if missing:
        ap.error(f"unknown question id(s): {missing}")
    target = {i: qs[i] for i in args.question}
    run_id = args.run_id or f"regrade-{O.now_iso()[:10]}"
    events = O.read(args.log)
    to_append, unfixable = plan_regrades(events, target, reason=args.reason, run_id=run_id)

    print(f"{len(events)} events read; {len(to_append)} row(s) to supersede, "
          f"{len(unfixable)} moved-but-unfixable (no lineage)")
    for ev in to_append:
        print(f"  {ev.question_id} {ev.instrument_identity.get('edge')} "
              f"{(ev.signals or {})['superseded_grade']}→{ev.grade} p={ev.probability} "
              f"claim={ev.claim[:40]!r} (of {(ev.signals or {})['regrade_of']})")
    for ev in unfixable:
        print(f"  UNFIXABLE {ev.question_id} {ev.instrument_identity.get('edge')} "
              f"{ev.grade} p={ev.probability} claim={ev.claim[:40]!r} — no lineage")
    if not args.apply:
        print("dry-run: nothing written (pass --apply)")
        return 0
    for ev in to_append:
        O.append(args.log, ev)
    print(f"appended {len(to_append)} row(s) to {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
