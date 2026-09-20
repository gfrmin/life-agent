#!/usr/bin/env python3
"""fit_escalate_row — measure an escalation rung from its recorded verdicts.

One episode per question: the local posterior the act would escalate FROM (``p1``, the MAP
credence of that question's last recorded ``/decide``) and how the rung's recorded answer
was graded by exact match (``right`` / ``wrong`` / ``declined``). Those fit the two-component
mixture in :mod:`life_agent.core.outcome_mixture` — per leader state, what the rung ends in —
and the row is written to ``$LIFE_AGENT_KB/calibration/escalate_row.json``, which the bridge
reads at boot. Prints counts only.

**What the fit conditions on, and what it cannot see.** The rung answers independently of
our state, so its outcomes are not selected by our policy; ``p1`` comes from a run whose act
did not have this row, so re-fit after the act changes. The mixture is weakly identified
when a rung's success barely moves with ``p1`` — ``--report`` prints the rate by ``p1`` band
and the correlation, which is how you check that before trusting the two components.

    uv run python scripts/fit_escalate_row.py --paired PAIRED-EXACT.jsonl \\
        --run-id gate-20260920T022750 --rung 1
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from life_agent.core import config as CFG
from life_agent.core import decisions as DECS
from life_agent.core import escalate as ESC
from life_agent.core import outcome_mixture as MIX


def p1_by_question(log: Path, run_id: str, gold: dict) -> dict[str, float]:
    """The MAP credence of each question's LAST recorded decision in ``run_id`` — the state
    an escalation would be chosen from."""
    by_hash = {DECS.question_id(g["question"]): q for q, g in gold.items()}
    out: dict[str, float] = {}
    for line in log.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("run_id") != run_id:
            continue
        q = by_hash.get(r.get("question_id", ""))
        if q is None:
            continue
        credences = (r.get("posterior_summary") or {}).get("credences") or [0.0]
        out[q] = max(float(c) for c in credences)
    return out


def rung_outcomes(paired: Path) -> dict[str, str]:
    """The rung arm's graded outcome per question, from a gate archive's recorded answers."""
    out: dict[str, str] = {}
    for line in paired.open(encoding="utf-8"):
        d = json.loads(line)
        arm = d["mono"]
        out[d["question_id"]] = ("right" if arm.get("correct")
                                 else "declined" if arm["action"] != "report" else "wrong")
    return out


def report(episodes: list[tuple[float, str]]) -> None:
    """The rate by p1 band and the correlation — the identifiability check the module
    docstring asks for, printed before the fit is trusted."""
    print(f"{'p1 band':14s} {'n':>4s} {'right':>12s} {'wrong':>6s} {'decl':>5s}")
    for lo, hi in ((0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)):
        sub = [o for p, o in episodes if lo <= p < hi]
        c = Counter(sub)
        n = len(sub) or 1
        print(f"[{lo:.1f},{hi:.1f})     {len(sub):4d} {c['right']:5d} ({c['right'] / n:.3f}) "
              f"{c['wrong']:6d} {c['declined']:5d}")
    xs = [p for p, _ in episodes]
    ys = [1.0 if o == "right" else 0.0 for _, o in episodes]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    corr = num / den if den > 0 else 0.0
    print(f"corr(p1, rung right) = {corr:+.3f} over n={len(episodes)} "
          f"(±{1 / len(episodes) ** 0.5:.3f} at one standard error): the two components are "
          f"{'weakly' if abs(corr) < 2 / len(episodes) ** 0.5 else 'usefully'} identified")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paired", required=True, help="an exact-graded gate archive")
    ap.add_argument("--run-id", required=True, help="the run whose decisions carry p1")
    ap.add_argument("--rung", default="1")
    ap.add_argument("--questions", default=str(CFG.KB / "eval/questions_v2.yaml"))
    ap.add_argument("--out", default=str(CFG.KB / "calibration/escalate_row.json"))
    ap.add_argument("--dry-run", action="store_true", help="report and fit, write nothing")
    a = ap.parse_args(argv)
    if a.rung not in ESC.RUNGS:
        print(f"rung {a.rung!r} is not declared in pricing.ESCALATE_RUNGS {ESC.RUNGS}",
              file=sys.stderr)
        return 2
    gold = {q["id"]: q for q in
            yaml.safe_load(Path(a.questions).read_text(encoding="utf-8"))["questions"]}
    p1 = p1_by_question(CFG.DECISIONS_LOG, a.run_id, gold)
    outcomes = rung_outcomes(Path(a.paired))
    episodes = [(p1[q], outcomes[q]) for q in sorted(p1) if q in outcomes]
    if not episodes:
        print(f"no episodes: {len(p1)} decisions and {len(outcomes)} graded answers share "
              "no question", file=sys.stderr)
        return 2
    report(episodes)
    t_right, t_wrong = MIX.fit(episodes)
    row = {**MIX.as_u_bar(ESC.action(a.rung), t_right, t_wrong), "n": len(episodes)}
    print(f"rung {a.rung}: " + " · ".join(f"{k.split('_', 1)[1]} {v:.3f}"
                                          for k, v in row.items() if k != "n"))
    if a.dry_run:
        return 0
    out = Path(a.out)
    recorded = (json.loads(out.read_text(encoding="utf-8")) if out.is_file()
                else {"rungs": {}})
    recorded["rungs"][a.rung] = row
    recorded["source"] = {"paired": Path(a.paired).name, "run_id": a.run_id,
                          "prior": "Dirichlet(2,2,2) posterior mode, EM over the leader"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote rung {a.rung} → $LIFE_AGENT_KB/{out.relative_to(CFG.KB)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
