"""Drift gates + derivation-identity guards for the unified decision skeleton (core/decide).

These pin the decision-seam unification (plan 2026-06-14): the shared correctness atom
``u_assert`` is the byte-identical source of both families' EU formulas (a behaviour-preserving
refactor — the regression oracles below reproduce the pre-refactor arithmetic), the action
vocabulary is single-sourced with *principled* per-family subsets, and narrative's per-claim
threshold is provably the powerset argmax (separability).

Run: uv run --project . python -m pytest tests/test_decide.py
"""
from __future__ import annotations

from itertools import combinations

import pytest

from life_agent.core import decisions as DEC
from life_agent.core import gate as G
from life_agent.core import lookup as LK
from life_agent.core import narrative as N
from life_agent.core.decide import u_assert

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


# --- behaviour preservation: both families derive byte-identically from u_assert ------------

def _legacy_action_utilities(weights: list[float], u_bar: dict[str, float],
                             p_attested: float) -> dict[str, list[float]]:
    """The hand-written formula (u_correct/u_wrong + the flat scoped row) — the oracle."""
    k = len(weights) - 1
    j_star = max(range(k), key=lambda j: weights[j]) if k else None
    u_wrong = u_bar["u_wrong"]
    report = [(u_bar["u_correct"] if j == j_star else u_wrong) for j in range(k)]
    report.append(u_wrong)
    hedge = [u_bar["u_hedged"]] * k + [u_wrong]
    ask = [LK._ORACLE_P * u_bar["u_correct"] - u_bar["lambda_int"]] * (k + 1)
    abstain = [u_bar["u_abstain"]] * (k + 1)
    scoped_eu = p_attested * u_bar["u_hedged"] + (1.0 - p_attested) * u_bar["u_wrong_scoped"]
    return {"report": report, "report_scoped": [scoped_eu] * (k + 1),
            "hedge": hedge, "ask_clarify": ask, "abstain": abstain}


def test_lookup_action_utilities_unchanged_by_derivation() -> None:
    for weights in ([0.7, 0.2, 0.1], [0.4, 0.6], [0.34, 0.33, 0.33], [1.0]):
        for p_att in (0.0, 0.5, 0.9):
            assert (LK.action_utilities(weights, UB, p_att)
                    == _legacy_action_utilities(weights, UB, p_att))


def test_narrative_include_eu_unchanged_by_derivation() -> None:
    for p in (0.0, 0.1, 0.5, 0.75, 0.9, 0.999):
        legacy = p * (p * UB["u_correct"] + (1.0 - p) * UB["u_wrong"]) - UB["kappa_att"]
        assert N.include_eu(p, UB) == pytest.approx(legacy)


# --- the single action vocabulary: principled per-family subsets ----------------------------

def test_family_action_orders_are_subsets_of_the_vocabulary() -> None:
    assert frozenset(DEC.LOOKUP_ACTION_ORDER) <= DEC.ACTIONS
    assert frozenset(DEC.NARRATIVE_ACTION_ORDER) <= DEC.ACTIONS


def test_lookup_minus_narrative_is_exactly_the_deferred_actions() -> None:
    # narrative's restriction is principled — it lacks exactly hedge, ask_clarify, and
    # report_scoped (the deferred recency/u_hedged + clarify + scoped-claim moves), nothing else.
    assert (frozenset(DEC.LOOKUP_ACTION_ORDER) - frozenset(DEC.NARRATIVE_ACTION_ORDER)
            == frozenset({"hedge", "ask_clarify", "report_scoped"}))


def test_families_import_the_vocabulary_never_redeclare() -> None:
    assert LK._ACTION_ORDER == DEC.LOOKUP_ACTION_ORDER
    assert N._ACTION_ORDER == DEC.NARRATIVE_ACTION_ORDER


def test_gate_partition_is_the_same_single_vocabulary() -> None:
    # gate.py's assert/withhold partition (the utility-sign cut) must cover ACTIONS exactly —
    # the unenforced coincidence at gate.py:76-78, now drift-gated.
    assert G.ASSERT_ACTIONS | G.WITHHOLD_ACTIONS == DEC.ACTIONS
    assert G.ASSERT_ACTIONS.isdisjoint(G.WITHHOLD_ACTIONS)


# --- separability: narrative's per-claim threshold IS the powerset argmax --------------------

def _exhaustive_best_subset(ps: list[float]) -> set[int]:
    """argmax over all 2ⁿ inclusion subsets of total EU = Σ_{i∈A} include_eu(p_i)
    (withhold = u_abstain = 0) — the brute-force oracle the per-claim threshold must match."""
    best_eu = float("-inf")
    best: set[int] = set()
    n = len(ps)
    for r in range(n + 1):
        for combo in combinations(range(n), r):
            eu = sum(N.include_eu(ps[i], UB) for i in combo)
            if eu > best_eu:
                best_eu, best = eu, set(combo)
    return best


def test_decide_claims_threshold_equals_powerset_argmax() -> None:
    for ps in ([0.9, 0.6, 0.3], [0.99, 0.01], [0.5, 0.5, 0.5, 0.5],
               [0.95, 0.8, 0.55, 0.2, 0.05]):
        scored = [(f"c{i}", (), "verified", p, None) for i, p in enumerate(ps)]
        claims, _action, _eu, _reason = N.decide_claims(scored, UB)
        included = {int(c.text[1:]) for c in claims if c.included}
        assert included == _exhaustive_best_subset(ps)
