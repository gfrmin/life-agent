"""The per-edge confidence calibration curve — the load-bearing gate defense.

A self-reported confidence ``c`` from an edge (a local extractor, a joint-read model) is
systematically overconfident, and worst exactly where the answer is WRONG — the only region a
zero-confident-wrong gate cares about. So the executor must never fold raw ``c`` as the
observation reliability; it folds ``calib_edge(c)`` — a monotone map learned from the owner's
graded outcomes, pessimistic where evidence is thin. These tests pin the properties the design
review requires: cold-start pessimism, overconfidence correction in the wrong region,
monotonicity, and convergence to empirical reliability with evidence.

    uv run --project . python -m pytest tests/test_calibration.py
"""
from __future__ import annotations

from itertools import pairwise

import pytest

from life_agent.core.calibration import (
    EdgeOutcome,
    Outcome,
    curve_for,
    fit_edge_curves,
    fit_reliability_curve,
)

# the pessimistic prior the executor seeds with (Beta(1,3) → mean 0.25): cold-start errs toward
# scope/abstain, evidence earns confidence.
PRIOR_MEAN = 1.0 / (1.0 + 3.0)


def _outcomes(pairs: list[tuple[float, bool]]) -> list[Outcome]:
    return [Outcome(confidence=c, correct=ok) for c, ok in pairs]


def test_cold_start_is_pessimistic() -> None:
    # no evidence: every confidence maps to the pessimistic prior, never the raw c
    curve = fit_reliability_curve([], prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    for c in (0.1, 0.5, 0.9, 0.99):
        assert curve.calibrate(c) == pytest.approx(PRIOR_MEAN)


def test_lowers_the_overconfident_wrong_region() -> None:
    # an edge that says c≈0.95 but is mostly WRONG there (the attribution class): the calibrated
    # reliability at 0.95 must be LOW — this is what stops the gate breach.
    outs = _outcomes([(0.95, False)] * 8 + [(0.95, True)] * 2)
    curve = fit_reliability_curve(outs, prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    assert curve.calibrate(0.95) < 0.4          # nowhere near the reported 0.95
    assert curve.calibrate(0.95) < 0.95         # explicitly: not the raw confidence


def test_is_monotone_nondecreasing() -> None:
    # higher self-reported confidence may not map to LOWER calibrated reliability (isotonic)
    outs = _outcomes([(0.2, False)] * 5 + [(0.5, False)] * 3 + [(0.5, True)] * 2
                     + [(0.9, True)] * 9 + [(0.9, False)])
    curve = fit_reliability_curve(outs, prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    grid = [i / 50 for i in range(51)]
    vals = [curve.calibrate(c) for c in grid]
    assert all(b >= a - 1e-9 for a, b in pairwise(vals))


def test_tracks_empirical_reliability_with_evidence() -> None:
    # a well-calibrated, well-evidenced edge: calibrate(c) ≈ the empirical hit-rate in that band
    # (within the pessimistic shrinkage), NOT pinned at the prior.
    outs = _outcomes([(0.9, True)] * 18 + [(0.9, False)] * 2)   # ~0.90 empirical at c=0.9
    curve = fit_reliability_curve(outs, prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    assert curve.calibrate(0.9) == pytest.approx(0.83, abs=0.07)   # shrunk from 0.90 toward prior
    assert curve.calibrate(0.9) > 0.6                              # but far above the prior


def test_sparse_evidence_stays_shrunk() -> None:
    # one lucky hit at high confidence must NOT yield reliability 1.0 — Beta shrinkage holds it down
    curve = fit_reliability_curve(_outcomes([(0.95, True)]),
                                  prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    assert curve.calibrate(0.95) == pytest.approx(2.0 / 5.0, abs=1e-6)   # (1+1)/(1+3+1)


# --- the per-edge fold (the calibration loop over the demand log) ------------


def test_fit_edge_curves_separates_the_overconfident_local_from_a_good_joint() -> None:
    records = (
        [EdgeOutcome("local", 0.95, False)] * 8 + [EdgeOutcome("local", 0.95, True)] * 2
        + [EdgeOutcome("joint", 0.9, True)] * 18 + [EdgeOutcome("joint", 0.9, False)] * 2)
    curves = fit_edge_curves(records, prior_alpha=1.0, prior_beta=3.0, n_bins=10)
    assert set(curves) == {"local", "joint"}
    assert curves["local"].calibrate(0.9) < 0.4    # the overconfident-wrong edge held down
    assert curves["joint"].calibrate(0.9) > 0.6     # the reliable edge earns its confidence


def test_curve_for_unseen_edge_is_the_pessimistic_prior() -> None:
    curves = fit_edge_curves([EdgeOutcome("local", 0.9, True)])
    assert curve_for(curves, "joint").calibrate(0.9) == pytest.approx(PRIOR_MEAN)
    assert curve_for(curves, "local") is curves["local"]


# --- the log fold (outcomes.jsonl → EdgeOutcomes — the first production wiring) ----------


def _outcome_base() -> dict:
    return dict(tx_time="t", run_id="r", question_id="q", claim="c",
                construct="rent", lineage_keys=())


def test_edge_outcomes_from_log_maps_grade_to_the_correct_bit(tmp_path) -> None:
    from life_agent.core import outcomes as O
    from life_agent.core.calibration import edge_outcomes_from_log

    log = tmp_path / "outcomes.jsonl"
    O.append(log, O.OutcomeEvent(**_outcome_base(), grade="CORRECT",
                                 grader="eval_lookup",
                                 instrument_identity={"edge": "deliberate@opus"},
                                 probability=0.9))
    O.append(log, O.OutcomeEvent(**_outcome_base(), grade="INCORRECT",
                                 grader="eval_lookup",
                                 instrument_identity={"edge": "deliberate@opus"},
                                 probability=0.8))
    assert edge_outcomes_from_log(log) == [
        EdgeOutcome("deliberate@opus", 0.9, True),
        EdgeOutcome("deliberate@opus", 0.8, False)]


def test_edge_outcomes_from_log_skips_unattributed_and_unpriced_rows(tmp_path) -> None:
    from life_agent.core import outcomes as O
    from life_agent.core.calibration import edge_outcomes_from_log

    log = tmp_path / "outcomes.jsonl"
    # no "edge" in the identity — a legacy row; never guessed into a namespace
    O.append(log, O.OutcomeEvent(**_outcome_base(), grade="CORRECT",
                                 grader="eval_lookup",
                                 instrument_identity={"producer_name": "x"},
                                 probability=0.9))
    # no probability — logged, not scored (the outcomes contract)
    O.append(log, O.OutcomeEvent(**_outcome_base(), grade="CORRECT",
                                 grader="eval_lookup",
                                 instrument_identity={"edge": "deliberate@opus"},
                                 probability=None))
    assert edge_outcomes_from_log(log) == []


def test_edge_outcomes_from_log_missing_file_is_cold_start(tmp_path) -> None:
    from life_agent.core.calibration import edge_outcomes_from_log

    assert edge_outcomes_from_log(tmp_path / "absent.jsonl") == []
