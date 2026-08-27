"""Poison fixtures for the composition's join — r24 (K2).

These require the composition to FAIL when a grounded channel is discarded. Each names the
mutation that kills it (register row 19).

Helpers come from `test_aggregate` rather than being re-implemented here: a fixture that
restates the constants it prices cannot see a defect in them (r22 entry 1).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_aggregate import (
    DEPOSIT_SCOPE,
    TabularBrain,
    _addend,
    _recall,
    _series,
)

from life_agent.core.aggregate import compose_total

_ROLLUP = 31937.0


def _compose(addends):
    (tp,) = compose_total(TabularBrain(), addends, DEPOSIT_SCOPE,
                          target_kind="deposit", recall=_recall())
    return tp


def test_poison_a_rollup_does_not_erase_the_series() -> None:
    """J1/J5. MUST FAIL if the replace branch returns. A single scope-end roll-up used to
    become THE observation with `k=1` and a zero-width interval, discarding a grounded
    three-document monthly series — the class r06-r09 closed, reintroduced by design.
    Killed by restoring the `if len(candidates) == 1:` early return."""
    months = _series([7, 8, 9])
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                           amount=_ROLLUP), *months])
    assert tp.k == 1 + len(months), (
        f"the composition kept {tp.k} observation(s) where {1 + len(months)} were grounded "
        f"({len(months)} monthly rows + 1 issuer roll-up) — a replace branch is discarding "
        f"a grounded channel"
    )


def test_poison_the_interval_spans_a_disagreement() -> None:
    """J2. MUST FAIL if either read falls outside the reported interval. Killed by
    returning a zero-width interval at the roll-up."""
    months = _series([7, 8, 9])
    series_sum = sum(a.amount for a in months)
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                           amount=_ROLLUP), *months])
    assert tp.lo <= min(_ROLLUP, series_sum) and tp.hi >= max(_ROLLUP, series_sum), (
        f"interval [{tp.lo}, {tp.hi}] excludes one of the two channel reads "
        f"(issuer {_ROLLUP:.2f}, series {series_sum:.2f}) — disagreement is information, "
        f"not a tiebreak"
    )


def test_poison_a_disagreement_is_named() -> None:
    """J4. MUST FAIL if the channels differ and the note says nothing. Killed by dropping
    the disagreement note."""
    months = _series([7, 8, 9])
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                           amount=_ROLLUP), *months])
    note = tp.basis_note.lower()
    assert any(w in note for w in ("disagree", "differ", "gap")), (
        f"the two channels disagree and the basis note does not say so: "
        f"{tp.basis_note!r} — silence about a disagreement is the defect, not the width"
    )


def test_poison_agreement_is_not_padded() -> None:
    """J3. MUST FAIL if the join manufactures width where the channels agree. Killed by
    widening unconditionally."""
    months = _series([7, 8, 9])
    agreed = sum(a.amount for a in months)
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                           amount=agreed), *months])
    assert tp.lo == tp.hi == tp.point == pytest.approx(agreed), (
        f"the channels agree at {agreed:.2f} but the interval is [{tp.lo}, {tp.hi}] with "
        f"point {tp.point} — the join padded an agreement, and Winkler prices that width"
    )


def test_a_rollup_with_no_series_is_still_a_point() -> None:
    """Precision control (no mutation by construction): the join must not invent a series
    that is not there."""
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-30",
                           amount=_ROLLUP)])
    assert tp.point == pytest.approx(_ROLLUP) and tp.k == 1


def test_a_series_with_no_rollup_is_unchanged() -> None:
    """Precision control: with no roll-up present the series path is exactly as before."""
    months = _series([7, 8, 9])
    tp = _compose(months)
    assert tp.k == len(months)
    assert tp.s_obs == pytest.approx(sum(a.amount for a in months))
