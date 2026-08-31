"""r39 — the B-class audit's own guards. Every load-bearing predicate is B4's mutation target.

The instrument BINDS `narrative.include_eu`; it never re-derives the algebra (`M-7`, six
instances — r34 priced a merge by summing credences and read it 0.493 where the rule reads
0.863).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import b_class_audit as BA

from life_agent.core import narrative as NARR

U_BAR = {"u_correct": 1.0, "u_wrong": -10.0, "u_abstain": 0.0, "kappa_att": 0.0}


def test_the_audit_binds_the_deployed_eu() -> None:
    """M-7: the constant it prices is imported, never re-spelled."""
    assert BA.include_eu is NARR.include_eu


def test_the_population_is_narrative_rows_only(tmp_path: Path) -> None:
    """B1's universe. A lookup row in the B population would price the wrong decision."""
    p = tmp_path / "decisions.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in [
        {"family": "narrative", "posterior_summary": {"n_proposed": 3, "n_included": 0}},
        {"family": "lookup", "posterior_summary": {}},
        {"family": "narrative", "posterior_summary": {"n_proposed": 1, "n_included": 1}},
    ]), encoding="utf-8")
    assert len(BA.narrative_rows(p)) == 2


def test_breakeven_is_the_reliance_where_the_deployed_eu_crosses_zero() -> None:
    """B2. The number is found by bisecting the IMPORTED EU, so it cannot drift from the rule."""
    p = BA.breakeven_reliance(U_BAR)
    assert p is not None
    assert BA.include_eu(p - 1e-6, U_BAR) < 0 <= BA.include_eu(p + 1e-6, U_BAR)


def test_breakeven_is_none_when_no_reliance_can_clear_it() -> None:
    """A cost so large that even certainty loses. The audit must say 'none', not return 1.0."""
    assert BA.breakeven_reliance({**U_BAR, "kappa_att": 99.0}) is None


def test_kappa_for_inverts_the_same_eu() -> None:
    """B3, the kappa arm: the kappa at which p breaks even, from the same functional."""
    k = BA.kappa_for(0.95, U_BAR)
    assert BA.include_eu(0.95, {**U_BAR, "kappa_att": k}) == pytest.approx(0.0, abs=1e-9)


def test_u_wrong_for_inverts_the_same_eu() -> None:
    """B3, the exchange-rate arm."""
    uw = BA.u_wrong_for(0.60, U_BAR)
    assert uw is not None
    assert BA.include_eu(0.60, {**U_BAR, "u_wrong": uw}) == pytest.approx(0.0, abs=1e-6)


def test_observed_cells_are_real_betas_not_composed_ones() -> None:
    """The defect this replaced: a per-cell ``(max(a), max(b))`` composes a Beta from two
    different rows and describes no decision. Every returned triple must be one a row wrote."""
    rows = [{"posterior_summary": {"cells": {"verified": [7.0, 4.0], "unsupported": [3.0, 3.0]}}},
            {"posterior_summary": {"cells": {"verified": [9.0, 2.0]}}}]
    got = BA.observed_cells(rows)
    assert set(got) == {("verified", 7.0, 4.0), ("unsupported", 3.0, 3.0), ("verified", 9.0, 2.0)}
    assert ("verified", 9.0, 4.0) not in got, "that Beta never occurred"


def test_the_audit_prices_with_the_deployed_functional_not_the_point_estimate() -> None:
    """`narrative.include_eu` says in its own docstring that it is NOT on the decision path.
    The engine optimises the INTEGRATED form over the cell Beta, and the two differ by the
    variance term — which is positive, so the point estimate UNDER-states inclusion."""
    assert BA.include_fn is NARR._include_fn
    a, b = 6.0, 2.0
    point = BA.include_eu(a / (a + b), U_BAR)
    integrated = BA.integrated_eu(a, b, U_BAR)
    assert integrated > point, "the variance term favours inclusion; a point read is not the rule"


def test_the_integrated_eu_uses_the_functionals_own_terms() -> None:
    """M-7: the coefficients come from `_include_fn`, so a change there moves this."""
    a, b = 6.0, 2.0
    fn = NARR._include_fn(U_BAR, 1.0)
    e1, e2 = a / (a + b), a * (a + 1) / ((a + b) * (a + b + 1))
    want = fn["offset"] + sum(c * (e2 if t["type"] == "centered_power" else e1)
                              for c, t in fn["terms"])
    assert BA.integrated_eu(a, b, U_BAR) == pytest.approx(want)


def test_the_withheld_reason_is_the_declared_constant() -> None:
    """The audit keys the B class on narrative's OWN declared reason string, not a copy."""
    assert BA.REASON is NARR.REASON_ALL_WITHHELD
