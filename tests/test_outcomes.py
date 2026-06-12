"""The calibration outcomes log (bayesian-foundations §8) — core machinery tests.

Hermetic: every test writes under tmp_path; the live KB is never touched. The log is
append-only JSONL whose file order is the canonical replay order (foundations §2: the
fold is order-defined), so round-trip tests assert order, not just content.

Run: uv run --project . python -m pytest tests/test_outcomes.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from life_agent.core import outcomes as O


def _event(**overrides: object) -> O.OutcomeEvent:
    base: dict = dict(
        tx_time="2026-06-12T10:00:00+00:00",
        run_id="eval-test",
        question_id="q-001",
        claim="42",
        construct="selection",
        grade="PASS",
        grader="eval_retrieval",
        instrument_identity={"producer_name": "pkm.retrieval.search",
                             "producer_config": {"k": 20}},
        lineage_keys=(),
        probability=None,
    )
    base.update(overrides)
    return O.OutcomeEvent(**base)  # type: ignore[arg-type]


# --- event validation (closed vocabularies — §18.8 discipline, self-applied) ----------

def test_unknown_grader_rejected() -> None:
    with pytest.raises(ValueError, match="grader"):
        _event(grader="vibes")


def test_grade_outside_grader_vocabulary_rejected() -> None:
    with pytest.raises(ValueError, match="grade"):
        _event(grade="HALLUCINATED")  # a synthesis grade, not a retrieval one


def test_probability_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="probability"):
        _event(probability=1.5)


def test_every_declared_grader_has_correct_grades_subset() -> None:
    # drift gate: CORRECT_GRADES must name only grades its grader can emit
    for grader, correct in O.CORRECT_GRADES.items():
        assert grader in O.GRADERS
        assert correct <= O.GRADERS[grader]


# --- append-only round trip ------------------------------------------------------------

def test_append_creates_parents_and_round_trips(tmp_path: Path) -> None:
    log = tmp_path / "calibration" / "outcomes.jsonl"
    e = _event()
    O.append(log, e)
    assert O.read(log) == [e]


def test_append_appends_never_truncates_and_order_is_preserved(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    first = _event(question_id="q-001")
    second = _event(question_id="q-002", grade="RETRIEVAL_MISS")
    O.append(log, first)
    O.append(log, second)
    assert O.read(log) == [first, second]
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_read_missing_file_is_empty(tmp_path: Path) -> None:
    assert O.read(tmp_path / "absent.jsonl") == []


def test_lines_are_canonical_json(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    O.append(log, _event())
    line = log.read_text(encoding="utf-8").splitlines()[0]
    obj = json.loads(line)
    assert obj["format_version"] == O.FORMAT_VERSION
    # canonical: sorted keys, compact separators
    assert line == json.dumps(obj, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":"))


def test_corrupt_line_fails_loudly(tmp_path: Path) -> None:
    log = tmp_path / "outcomes.jsonl"
    log.write_text('{"not": "an event"}\n', encoding="utf-8")
    with pytest.raises((KeyError, TypeError, ValueError)):
        O.read(log)


# --- proper scoring rules ---------------------------------------------------------------

def test_log_score_is_log_probability_of_realised_outcome() -> None:
    assert O.log_score(0.9, correct=True) == pytest.approx(math.log(0.9))
    assert O.log_score(0.9, correct=False) == pytest.approx(math.log(0.1))


def test_log_score_clamps_at_stated_epsilon() -> None:
    # p=1.0 on a wrong claim would be -inf; the stated clamp keeps it finite
    assert O.log_score(1.0, correct=False) == pytest.approx(math.log(O.SCORE_EPS))
    assert O.log_score(0.0, correct=True) == pytest.approx(math.log(O.SCORE_EPS))


def test_brier_score() -> None:
    assert O.brier_score(1.0, correct=True) == pytest.approx(0.0)
    assert O.brier_score(1.0, correct=False) == pytest.approx(1.0)
    assert O.brier_score(0.5, correct=True) == pytest.approx(0.25)


def test_summarize_scores() -> None:
    pairs = [(0.9, True), (0.8, False)]
    s = O.summarize_scores(pairs)
    assert s.n == 2
    assert s.mean_log == pytest.approx((math.log(0.9) + math.log(0.2)) / 2)
    assert s.mean_brier == pytest.approx(((0.1) ** 2 + (0.8) ** 2) / 2)


def test_summarize_scores_empty() -> None:
    s = O.summarize_scores([])
    assert s.n == 0 and s.mean_log is None and s.mean_brier is None


def test_reliability_bins() -> None:
    pairs = [(0.05, False), (0.15, False), (0.95, True), (0.85, True), (0.95, False)]
    bins = O.reliability_bins(pairs, n_bins=10)
    assert len(bins) == 10
    lo = bins[0]   # [0.0, 0.1)
    hi = bins[-1]  # [0.9, 1.0]
    assert lo.n == 1 and lo.frac_correct == pytest.approx(0.0)
    assert hi.n == 2 and hi.frac_correct == pytest.approx(0.5)
    assert hi.mean_p == pytest.approx(0.95)
    assert sum(b.n for b in bins) == len(pairs)


def test_scored_pairs_uses_grader_correctness_and_skips_unscored() -> None:
    events = [
        _event(probability=0.9),                                  # PASS -> correct
        _event(probability=0.7, grade="RETRIEVAL_MISS"),          # -> incorrect
        _event(probability=None),                                 # unscored: skipped
    ]
    assert O.scored_pairs(events) == [(0.9, True), (0.7, False)]
