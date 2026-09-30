"""Calibration: is the decider's stated probability that its leader is right, right?

The event scored is `p1` — the probability the decider gave its leading candidate — against
whether that candidate matched the gold (exact match, `grading.realised_report`). It is taken
on every row that had at least one candidate, whatever the act was: an abstain still has a
leader and a `p1`. Rows with no candidate have no leader and are counted, not scored; rows
whose candidates all miss the gold are scored (the leader is wrong) and also counted as
truth-absent, because that is a proposer miss, not a miscalibrated posterior.

Two sources give the pairs: an archive written by `eval.run` (fields `p1`, `n_candidates`,
`leader_correct`, `truth_in_candidates` on the `typed` arm) and the decision log joined to a
question set (for an archive that predates the fields). Aggregates only — nothing here prints
a question, a candidate or a gold.

    uv run python -m eval.calibration --questions PATH --runs gate-2026
"""
from __future__ import annotations

import argparse
import os
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.grading import realised_report
from life_agent.core import decisions as DEC
from life_agent.core import outcomes as OUT


@dataclass(frozen=True)
class Reading:
    """One row's leader, read against its gold. ``p1`` / ``leader_correct`` are ``None``
    when there is no leader (or no credence to name one)."""

    n_candidates: int
    p1: float | None
    leader_correct: bool | None
    truth_in_candidates: bool


@dataclass(frozen=True)
class Pairs:
    """The scorable (p1, leader_correct) pairs and what was left out, by reason."""

    pairs: tuple[tuple[float, bool], ...] = ()
    n_no_candidate: int = 0
    n_truth_absent: int = 0
    n_skipped: int = 0     # decisions whose question is not in the set

    def __add__(self, other: Pairs) -> Pairs:
        return Pairs(self.pairs + other.pairs, self.n_no_candidate + other.n_no_candidate,
                     self.n_truth_absent + other.n_truth_absent,
                     self.n_skipped + other.n_skipped)


@dataclass(frozen=True)
class Calibration:
    n_scored: int
    mean_log: float | None
    ece: float | None
    bins: tuple[OUT.ReliabilityBin, ...]
    n_no_candidate: int
    n_truth_absent: int
    n_clamped: int         # pairs whose log score `outcomes.log_score` clamped on the wrong side
    n_skipped: int = 0


def read_leader(candidates: Sequence[Any], credences: Sequence[float], gold: str,
                variants: list[str]) -> Reading:
    """The leader (highest credence, ties to the earlier candidate: `decisions.leader_order`)
    graded against the gold. Credences that are not parallel to the candidates name no
    leader, so ``p1`` and ``leader_correct`` are ``None``."""
    values = [str(c) for c in candidates]
    truth = any(realised_report([v], gold, variants) for v in values)
    if not values or len(credences) != len(values):
        return Reading(len(values), None, None, truth)
    lead = DEC.leader_order(list(credences))[0]
    return Reading(len(values), float(credences[lead]),
                   realised_report([values[lead]], gold, variants), truth)


def tally(readings: Iterable[Reading], n_skipped: int = 0) -> Pairs:
    rs = list(readings)
    scored = tuple((r.p1, bool(r.leader_correct)) for r in rs
                   if r.n_candidates and r.p1 is not None)
    return Pairs(scored, n_no_candidate=sum(not r.n_candidates for r in rs),
                 n_truth_absent=sum(bool(r.n_candidates) and not r.truth_in_candidates
                                    for r in rs),
                 n_skipped=n_skipped)


def pairs_from_archive(rows: Iterable[Mapping[str, Any]]) -> Pairs:
    """From archive rows carrying the calibration fields on ``typed``; a row without them
    (an older archive) and a censored row contribute nothing."""
    readings = []
    for row in rows:
        t = row.get("typed") or {}
        if row.get("censored") or "n_candidates" not in t:
            continue
        readings.append(Reading(int(t["n_candidates"]), t.get("p1"), t.get("leader_correct"),
                                bool(t.get("truth_in_candidates"))))
    return tally(readings)


def pairs_from_decisions(decisions: Iterable[DEC.DecisionEvent],
                         questions: Sequence[Mapping[str, Any]]) -> Pairs:
    """Join decisions to questions on ``decisions.question_id`` of the question text and read
    each decision's leader from its posterior digest. A decision whose question is not in the
    set is skipped and counted."""
    by_id = {DEC.question_id(q["question"]): q for q in questions}
    readings, skipped = [], 0
    for d in decisions:
        q = by_id.get(d.question_id)
        if q is None:
            skipped += 1
            continue
        post = d.posterior_summary or {}
        readings.append(read_leader(post.get("candidates") or [], post.get("credences") or [],
                                    q.get("answer", ""), q.get("answer_variants") or []))
    return tally(readings, skipped)


def _clamped(p: float, correct: bool, eps: float = OUT.SCORE_EPS) -> bool:
    return p < eps if correct else p > 1.0 - eps


def calibrate(pairs: Pairs, *, n_bins: int = 10) -> Calibration:
    ps = list(pairs.pairs)
    s = OUT.summarize_scores(ps)
    return Calibration(n_scored=s.n, mean_log=s.mean_log, ece=OUT.ece(ps, n_bins=n_bins),
                       bins=tuple(OUT.reliability_bins(ps, n_bins=n_bins)),
                       n_no_candidate=pairs.n_no_candidate, n_truth_absent=pairs.n_truth_absent,
                       n_clamped=sum(_clamped(p, c) for p, c in ps), n_skipped=pairs.n_skipped)


def fmt_bins(cal: Calibration) -> list[str]:
    """Non-empty bins as ``lo-hi  n  mean p1  fraction right`` lines."""
    return [f"  [{b.lo:.1f}, {b.hi:.1f}{']' if b.hi >= 1.0 else ')'}  n={b.n:<4} "
            f"mean p1 {b.mean_p:.3f}  right {b.frac_correct:.3f}"
            for b in cal.bins if b.n and b.mean_p is not None and b.frac_correct is not None]


def _fmt(x: float | None, spec: str) -> str:
    return "—" if x is None else format(x, spec)


def main(argv: list[str] | None = None) -> int:
    from eval.run import load_questions

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--runs", required=True, help="decision-log run_id prefix")
    ap.add_argument("--log", default=None,
                    help="default: $LIFE_AGENT_KB/calibration/decisions.jsonl")
    a = ap.parse_args(argv)
    log = (Path(a.log) if a.log
           else Path(os.environ["LIFE_AGENT_KB"]) / "calibration" / "decisions.jsonl")
    questions = load_questions(a.questions)
    runs: dict[str, list[DEC.DecisionEvent]] = defaultdict(list)
    for d in DEC.read(log):
        if d.run_id.startswith(a.runs):
            runs[d.run_id].append(d)
    per_run = {rid: pairs_from_decisions(ds, questions) for rid, ds in sorted(runs.items())}
    pooled = sum(per_run.values(), Pairs())
    cal = calibrate(pooled)
    print(f"pooled over {len(per_run)} run(s): n scored {cal.n_scored}, mean log "
          f"{_fmt(cal.mean_log, '.4f')}, ECE {_fmt(cal.ece, '.4f')}, no-candidate "
          f"{cal.n_no_candidate}, truth-absent {cal.n_truth_absent}, clamped {cal.n_clamped}, "
          f"skipped {cal.n_skipped}")
    print("\n".join(fmt_bins(cal)))
    for rid, p in per_run.items():
        c = calibrate(p)
        print(f"{rid}  n={c.n_scored}  mean log {_fmt(c.mean_log, '.4f')}  "
              f"ECE {_fmt(c.ece, '.4f')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
