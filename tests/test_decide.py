"""Drift gates for core/decide's correctness atom, the recorded action vocabulary, and the
per-shape utility units.

``u_assert`` is the one correctness utility (the gate's break-even reads it); the recorded
action vocabulary is single-sourced with per-family subsets; ``shaped_u_bar`` is the one
place a per-shape scale applies.

Run: uv run --project . python -m pytest tests/test_decide.py
"""
from __future__ import annotations

import pytest

from life_agent.core import answer_shape as AS
from life_agent.core import decisions as DEC
from life_agent.core import gate as G
from life_agent.core.decide import shaped_u_bar, u_assert

# A representative Ū (gauge + the action-pricing latents); values mirror the family tests.
UB: dict[str, float] = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.0,
                        "u_wrong_scoped": -2.0, "u_hedged": 0.4, "lambda_int": 1.0,
                        "kappa_att": 0.05}


# --- the atom -------------------------------------------------------------------------------

def test_u_assert_pins_the_gauge_endpoints() -> None:
    assert u_assert(1.0, UB) == UB["u_correct"]   # a correct report is worth u_correct
    assert u_assert(0.0, UB) == UB["u_wrong"]     # a wrong report is worth u_wrong


def test_u_assert_is_linear_in_reliance() -> None:
    assert u_assert(0.5, UB) == pytest.approx(0.5 * (UB["u_correct"] + UB["u_wrong"]))
    assert u_assert(0.25, UB) == pytest.approx(0.25 * UB["u_correct"] + 0.75 * UB["u_wrong"])


# --- the single action vocabulary: principled per-family subsets ----------------------------

def test_family_action_orders_are_subsets_of_the_vocabulary() -> None:
    assert frozenset(DEC.LOOKUP_ACTION_ORDER) <= DEC.ACTIONS
    assert frozenset(DEC.NARRATIVE_ACTION_ORDER) <= DEC.ACTIONS

def test_lookup_minus_narrative_is_exactly_the_deferred_actions() -> None:
    # narrative's restriction is principled — it lacks exactly hedge, ask_clarify, and
    # report_scoped (the deferred recency/u_hedged + clarify + scoped-claim moves), nothing else.
    assert (frozenset(DEC.LOOKUP_ACTION_ORDER) - frozenset(DEC.NARRATIVE_ACTION_ORDER)
            == frozenset({"hedge", "ask_clarify", "report_scoped"}))


def test_gate_partition_is_the_same_single_vocabulary() -> None:
    # gate.py's assert/withhold partition (the utility-sign cut) must cover ACTIONS exactly —
    # the unenforced coincidence at gate.py:76-78, now drift-gated.
    assert G.ASSERT_ACTIONS | G.WITHHOLD_ACTIONS == DEC.ACTIONS
    assert G.ASSERT_ACTIONS.isdisjoint(G.WITHHOLD_ACTIONS)


# --- r30 step 2: question-dependent utility units (shaped_u_bar) ----------------------------
# docs/unification/reports/r30-units-lever.md — the ONE place a per-shape scale applies (C5's
# drift gate: every current_u_bar caller routes Ū through this function, never re-implements
# the scale arithmetic itself).

def test_shaped_u_bar_at_the_anchor_shape_is_the_identity() -> None:
    # C3: exact is the anchor — u_correct/u_wrong pass through UNSCALED, today's convention.
    out = shaped_u_bar(UB, AS.ANCHOR_SHAPE)
    assert out == UB


def test_shaped_u_bar_defaults_undeclared_scales_to_one() -> None:
    # C4: a u_bar carrying none of the six optional latents (every fixture and the owner's
    # live model file today) must reproduce the SAME u_correct/u_wrong for every shape —
    # the no-op-by-construction claim G2's replay checks.
    for shape in AS.SCALED_SHAPES:
        out = shaped_u_bar(UB, shape)
        assert out["u_correct"] == UB["u_correct"]
        assert out["u_wrong"] == UB["u_wrong"]


def test_shaped_u_bar_applies_declared_scales() -> None:
    scaled = {**UB, "voi_scale_quantity": 0.5, "regret_scale_quantity": 2.0}
    out = shaped_u_bar(scaled, "quantity")
    assert out["u_correct"] == pytest.approx(scaled["u_correct"] * 0.5)
    assert out["u_wrong"] == pytest.approx(scaled["u_wrong"] * 2.0)


def test_shaped_u_bar_only_touches_u_correct_and_u_wrong() -> None:
    scaled = {**UB, "voi_scale_set": 3.0, "regret_scale_set": 4.0}
    out = shaped_u_bar(scaled, "set")
    untouched = set(scaled) - {"u_correct", "u_wrong"}
    assert {k: out[k] for k in untouched} == {k: scaled[k] for k in untouched}


def test_shaped_u_bar_a_shape_scale_never_leaks_into_another_shape() -> None:
    scaled = {**UB, "voi_scale_quantity": 5.0, "regret_scale_quantity": 5.0}
    out = shaped_u_bar(scaled, "threshold")  # only quantity's scales are declared
    assert out["u_correct"] == UB["u_correct"]
    assert out["u_wrong"] == UB["u_wrong"]


def test_shaped_u_bar_rejects_an_unknown_shape() -> None:
    with pytest.raises(ValueError, match="answer shape"):
        shaped_u_bar(UB, "paragraph")
