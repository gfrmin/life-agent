"""Drift gates for core/decide's correctness atom and the recorded action vocabulary.

``u_assert`` is the one correctness utility (the gate's break-even reads it); the recorded
action vocabulary is single-sourced with per-family subsets.

Run: uv run --project . python -m pytest tests/test_decide.py
"""
from __future__ import annotations

import pytest

from life_agent.core import decisions as DEC
from life_agent.core.decide import u_assert

# A representative Ū (gauge + the action-pricing latents); values mirror the family tests.
UB: dict[str, float] = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.0,
                        "lambda_int": 1.0, "kappa_att": 0.05}


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
    # narrative's restriction is principled — it lacks exactly ask_clarify and cite (the
    # clarify and partial-answer moves), nothing else.
    assert (frozenset(DEC.LOOKUP_ACTION_ORDER) - frozenset(DEC.NARRATIVE_ACTION_ORDER)
            == frozenset({"ask_clarify", "cite"}))
