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
                             scoped_eu: float) -> dict[str, list[float]]:
    """The hand-written formula (per-candidate report_j + the flat scoped row) — the oracle. The
    MAP no longer enters here: `optimise` picks among report_j (the engine, not a host argmax)."""
    k = len(weights) - 1
    u_wrong = u_bar["u_wrong"]
    out = {f"report_{j}": [(u_bar["u_correct"] if i == j else u_wrong) for i in range(k)] + [u_wrong]
           for j in range(k)}
    out["hedge"] = [u_bar["u_hedged"]] * k + [u_wrong]
    out["ask_clarify"] = [LK._ORACLE_P * u_bar["u_correct"] - u_bar["lambda_int"]] * (k + 1)
    out["abstain"] = [u_bar["u_abstain"]] * (k + 1)
    out["report_scoped"] = [scoped_eu] * (k + 1)
    return out


def test_lookup_action_utilities_unchanged_by_derivation() -> None:
    for weights in ([0.7, 0.2, 0.1], [0.4, 0.6], [0.34, 0.33, 0.33], [1.0]):
        for scoped_eu in (-2.0, 0.0, 0.16):
            assert (LK.action_utilities(weights, UB, scoped_eu)
                    == _legacy_action_utilities(weights, UB, scoped_eu))


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

def _integrated_include_eu(a: float, b: float) -> float:
    """The narrative include action's EU over a cell Beta(a, b), the integrated model the wire
    `optimise{include, withhold}` runs: E_θ[θ·u_assert(θ)] − κ = (u_c−u_w)·E[θ²] + u_w·E[θ] − κ
    (the proper integral — NOT include_eu evaluated at the point E[θ])."""
    e1 = a / (a + b)
    e2 = a * (a + 1.0) / ((a + b) * (a + b + 1.0))
    return (UB["u_correct"] - UB["u_wrong"]) * e2 + UB["u_wrong"] * e1 - UB["kappa_att"]


def _exhaustive_best_subset(eus: list[float]) -> set[int]:
    """argmax over all 2ⁿ inclusion subsets of total EU = Σ_{i∈A} EU_i (withhold = u_abstain = 0)
    — the brute-force oracle the per-claim threshold (`optimise` on each cell Beta) must match."""
    best_eu = float("-inf")
    best: set[int] = set()
    n = len(eus)
    for r in range(n + 1):
        for combo in combinations(range(n), r):
            eu = sum(eus[i] for i in combo)
            if eu > best_eu:
                best_eu, best = eu, set(combo)
    return best


def test_per_claim_threshold_equals_powerset_argmax() -> None:
    # narrative decides each claim independently (per-claim `optimise{include,withhold}` on its
    # cell Beta); claims are independent and answer-utility additive, so the powerset optimum
    # factorises to the per-claim threshold {i : EU_i > 0}. This pins that separability on the
    # INTEGRATED EU (decide_claims' end-to-end inclusion is exercised in test_narrative).
    for cells in ([(9., 1.), (3., 2.), (1., 3.)],         # means 0.9 / 0.6 / 0.25
                  [(99., 1.), (1., 99.)],
                  [(5., 5.), (5., 5.), (5., 5.), (5., 5.)],
                  [(20., 1.), (8., 4.), (3., 4.), (1., 6.), (1., 30.)]):
        eus = [_integrated_include_eu(a, b) for a, b in cells]
        assert {i for i, e in enumerate(eus) if e > 0.0} == _exhaustive_best_subset(eus)
