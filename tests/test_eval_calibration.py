"""`eval.calibration`: the leader's `p1` against whether the leader matched the gold. Every
value here is synthetic (PII-OK: synthetic questions, golds and candidates)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import calibration as C
from life_agent.core import decisions as DEC


def test_bins_ece_and_log_score_from_known_pairs() -> None:
    # two in [0.9, 1.0] (one right, one wrong), two in [0.1, 0.2) (both wrong)
    pairs = C.Pairs(((0.9, True), (0.95, False), (0.1, False), (0.15, False)))
    cal = C.calibrate(pairs)
    assert cal.n_scored == 4
    live = {(b.lo, b.n, round(b.mean_p, 3), b.frac_correct) for b in cal.bins if b.n}
    assert live == {(0.1, 2, 0.125, 0.0), (0.9, 2, 0.925, 0.5)}
    # ECE = 2/4 |0.125-0| + 2/4 |0.925-0.5|
    assert cal.ece == pytest.approx(0.5 * 0.125 + 0.5 * 0.425)
    want = (math.log(0.9) + math.log(0.05) + math.log(0.9) + math.log(0.85)) / 4
    assert cal.mean_log == pytest.approx(want)
    assert cal.n_clamped == 0


def test_no_pairs_is_honest_none() -> None:
    cal = C.calibrate(C.Pairs(n_no_candidate=3))
    assert (cal.n_scored, cal.mean_log, cal.ece, cal.n_no_candidate) == (0, None, None, 3)


def test_a_certain_wrong_leader_is_counted_as_clamped() -> None:
    # p = 1 on a wrong leader and p = 0 on a right one are clamped; p = 1 on a right one is not
    cal = C.calibrate(C.Pairs(((1.0, False), (0.0, True), (1.0, True), (0.5, True))))
    assert cal.n_clamped == 2
    assert cal.mean_log is not None and math.isfinite(cal.mean_log)


def test_the_leader_is_the_highest_credence_ties_to_the_earlier() -> None:
    r = C.read_leader(["A1", "B2", "C3"], [0.2, 0.5, 0.3], "B2", [])
    assert (r.n_candidates, r.p1, r.leader_correct, r.truth_in_candidates) == (3, 0.5, True, True)
    tie = C.read_leader(["A1", "B2"], [0.4, 0.4], "B2", [])
    assert (tie.leader_correct, tie.truth_in_candidates) == (False, True)   # A1 leads the tie


def test_a_variant_of_the_gold_counts_and_a_missing_truth_is_named() -> None:
    assert C.read_leader(["ref 7"], [0.6], "7", ["ref 7"]).leader_correct is True
    miss = C.read_leader(["X9"], [0.7], "Y1", [])
    assert (miss.leader_correct, miss.truth_in_candidates) == (False, False)


def test_credences_not_parallel_to_candidates_name_no_leader() -> None:
    r = C.read_leader(["A1", "B2"], [], "A1", [])
    assert (r.p1, r.leader_correct, r.truth_in_candidates) == (None, None, True)
    assert C.tally([r]).pairs == ()


def test_tally_counts_no_candidate_and_truth_absent_and_scores_the_latter() -> None:
    rows = [C.read_leader(["A1"], [0.9], "A1", []),        # right
            C.read_leader(["X9", "Z3"], [0.6, 0.2], "Y1", []),   # truth absent, leader wrong
            C.read_leader([], [], "A1", [])]               # no candidate
    p = C.tally(rows)
    assert p.pairs == ((0.9, True), (0.6, False))
    assert (p.n_no_candidate, p.n_truth_absent) == (1, 1)


def test_archive_rows_without_the_fields_or_censored_contribute_nothing() -> None:
    rows = [{"typed": {"action": "report", "correct": True}},              # old archive
            {"censored": True, "typed": {"n_candidates": 1, "p1": 0.9, "leader_correct": True,
                                         "truth_in_candidates": True}},
            {"typed": {"n_candidates": 2, "p1": 0.7, "leader_correct": False,
                       "truth_in_candidates": True}},
            {"typed": {"n_candidates": 0, "p1": None, "leader_correct": None,
                       "truth_in_candidates": False}}]
    p = C.pairs_from_archive(rows)
    assert p.pairs == ((0.7, False),) and p.n_no_candidate == 1 and p.n_truth_absent == 0


def _decision(question: str, candidates: list[str], credences: list[float]) -> DEC.DecisionEvent:
    return DEC.DecisionEvent(
        tx_time="2026-01-01T00:00:00+00:00", run_id="gate-synthetic",
        question_id=DEC.question_id(question), family="lookup", action_set=("abstain",),
        posterior_summary={"candidates": candidates, "credences": credences},
        utility_fold_version="v", chosen_action="abstain", predicted_eu=0.0)


def test_the_decision_log_joins_to_questions_on_the_hashed_text() -> None:
    qs = [{"question": "what is the synthetic id?", "answer": "AB12", "answer_variants": []},
          {"question": "when is the synthetic date?", "answer": "3 May", "answer_variants": []},
          {"question": "who is the synthetic person?", "answer": "Zed", "answer_variants": []}]
    ds = [_decision(qs[0]["question"], ["AB12", "CD34"], [0.3, 0.6]),   # leader CD34: wrong
          _decision(qs[1]["question"], ["3 May"], [0.8]),               # right
          _decision(qs[2]["question"], [], []),                         # no candidate
          _decision("a question outside the set?", ["Q"], [0.9])]       # skipped
    p = C.pairs_from_decisions(ds, qs)
    assert p.pairs == ((0.6, False), (0.8, True))
    assert (p.n_no_candidate, p.n_truth_absent, p.n_skipped) == (1, 0, 1)


def test_pooling_adds_pairs_and_counts() -> None:
    a = C.Pairs(((0.5, True),), 1, 0, 2)
    b = C.Pairs(((0.6, False),), 0, 1, 0)
    assert a + b == C.Pairs(((0.5, True), (0.6, False)), 1, 1, 2)
