"""r32 — the commit-bar reading's instrument, predicate by predicate.

Every test here pins a LOAD-BEARING predicate of ``scripts/bar_audit.py`` (r32's
pre-registration, criterion C5: verified RED by mutation before the read is believed).
Hermetic: synthetic Ū and synthetic rows only, no corpus values, no engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import bar_audit as BA

# PII-OK: synthetic utility model — the declared prior's shape, no owner value.
# lambda_int is set so the oracle row is dominated: these tests are about the
# report-vs-abstain trade-off, and TestOracleRow pins ask_clarify separately.
U_DECLARED = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0,
              "u_hedged": -1.0, "lambda_int": 2.0}


def _row(lead: float, p_none: float, action: str, eu: float) -> dict:
    return {"decision_id": "ab-" + "0" * 16, "chosen_action": action, "family": "lookup",
            "predicted_eu": eu, "tx_time": "2026-08-30T12:00:00+00:00",
            "utility_fold_version": "deadbeef", "policy": "all-to-date",
            "posterior_summary": {"candidates": ["x"], "credences": [lead],
                                  "n_obs": 1, "p_none": p_none}}


class TestAtomProbs:
    def test_credences_then_none(self) -> None:
        assert BA.atom_probs(_row(0.75, 0.25, "report", 0.0)) == [0.75, 0.25]

    def test_refuses_a_distribution_that_does_not_sum_to_one(self) -> None:
        with pytest.raises(BA.UnreadableRowError):
            BA.atom_probs(_row(0.75, 0.10, "report", 0.0))

    def test_refuses_a_row_with_no_posterior(self) -> None:
        row = _row(0.75, 0.25, "report", 0.0)
        row["posterior_summary"] = {}
        with pytest.raises(BA.UnreadableRowError):
            BA.atom_probs(row)


class TestIndifferencePoint:
    def test_the_declared_prior_puts_the_bar_at_exactly_0_90(self) -> None:
        # u_assert(p) = 0 at p = 0.9 when u_wrong = -9 against u_correct = 1: this is the
        # 10:1 exchange rate the owner declared, and the docstring's "uniform 0.90 bar".
        assert BA.indifference_point(U_DECLARED) == pytest.approx(0.90, abs=1e-9)

    def test_a_softer_regret_latent_lowers_the_bar(self) -> None:
        softer = {**U_DECLARED, "u_wrong": -4.0}
        assert BA.indifference_point(softer) == pytest.approx(0.80, abs=1e-9)
        assert BA.indifference_point(softer) < BA.indifference_point(U_DECLARED)

    def test_it_inverts_the_deployed_atom_not_a_formula(self) -> None:
        # whatever p† is, the DEPLOYED u_assert must sit at the gauge zero there.
        from life_agent.core.decide import u_assert
        for u_wrong in (-9.0, -5.7, -2.0, -1.0):
            u_bar = {**U_DECLARED, "u_wrong": u_wrong}
            p = BA.indifference_point(u_bar)
            assert u_assert(p, u_bar) == pytest.approx(u_bar["u_abstain"], abs=1e-9)


class TestReprice:
    def test_report_beats_abstain_above_the_bar(self) -> None:
        eus = BA.reprice([0.95, 0.05], U_DECLARED)
        assert eus["report_0"] > eus["abstain"]
        assert BA.argmax_action(eus) == "report"

    def test_abstain_wins_below_the_bar(self) -> None:
        eus = BA.reprice([0.85, 0.15], U_DECLARED)
        assert eus["report_0"] < eus["abstain"]
        assert BA.argmax_action(eus) == "abstain"

    def test_report_eu_is_the_deployed_atom_at_the_leader(self) -> None:
        from life_agent.core.decide import u_assert
        probs = [0.8747, 0.1253]
        eus = BA.reprice(probs, U_DECLARED)
        assert eus["report_0"] == pytest.approx(u_assert(probs[0], U_DECLARED), abs=1e-12)

    def test_argmax_maps_report_j_to_the_recorded_vocabulary(self) -> None:
        # a two-candidate row where the SECOND atom leads: the winner is still "report".
        eus = BA.reprice([0.05, 0.94, 0.01], U_DECLARED)
        assert BA.argmax_action(eus) == "report"


class TestOracleRow:
    def test_ask_clarify_is_priced_from_the_deployed_oracle_constant(self) -> None:
        from life_agent.core.lookup import _ORACLE_P

        eus = BA.reprice([0.5, 0.5], U_DECLARED)
        expected = _ORACLE_P * U_DECLARED["u_correct"] - U_DECLARED["lambda_int"]
        assert eus["ask_clarify"] == pytest.approx(expected, abs=1e-12)

    def test_a_cheap_oracle_can_outrank_both_report_and_abstain(self) -> None:
        cheap = {**U_DECLARED, "lambda_int": 0.5}
        eus = BA.reprice([0.85, 0.15], cheap)
        assert BA.argmax_action(eus) == "ask_clarify"


class TestConsistency:
    def test_a_report_below_the_bar_is_flagged(self) -> None:
        row = _row(0.80, 0.20, "report", 0.0)
        assert BA.consistent_with_bar(row, 0.8522) is False

    def test_an_abstain_below_the_bar_is_consistent(self) -> None:
        row = _row(0.80, 0.20, "abstain", 0.0)
        assert BA.consistent_with_bar(row, 0.8522) is True

    def test_a_report_above_the_bar_is_consistent(self) -> None:
        row = _row(0.90, 0.10, "report", 0.0)
        assert BA.consistent_with_bar(row, 0.8522) is True

    def test_an_abstain_above_the_bar_is_flagged(self) -> None:
        row = _row(0.90, 0.10, "abstain", 0.0)
        assert BA.consistent_with_bar(row, 0.8522) is False
