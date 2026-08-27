"""Poison fixtures for the upstream discard stages — r25.

K2 (r24) rewrote `_compose_one`'s last stage to keep both channels and left the two stages
before it discarding grounded observations, two of them silently. These require the
composition to FAIL when that happens. Each names, in its OWN docstring, the mutation that
kills it.
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

from life_agent.core.aggregate import _COARSE_BASES, compose_total


def _compose(addends, scope=DEPOSIT_SCOPE):
    (tp,) = compose_total(TabularBrain(), addends, scope, target_kind="deposit",
                          recall=_recall())
    return tp


# --- L1: the within-doc collapse ------------------------------------------------------

def test_poison_two_distinct_line_items_are_not_merged() -> None:
    """L1. MUST FAIL if `_collapse_within_doc` keys on (doc, kind, amount, as_of) alone.
    Two deposits of the same amount on the same day in one statement, against two different
    accounts, are two transactions — master reported 250 for a true 500, with k=1 and an
    empty note. Killed by dropping `entity`/`label_raw` from the collapse key."""
    tp = _compose([
        _addend(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=250.0,
                entity="acct-a"),
        _addend(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=250.0,
                entity="acct-b")])
    assert tp.s_obs == pytest.approx(500.0) and tp.k == 2, (
        f"two distinguishable line items collapsed to k={tp.k}, s_obs={tp.s_obs} — the "
        f"within-doc key ignores the fields that tell them apart, and the total halves"
    )


def test_poison_a_within_doc_collapse_is_never_silent() -> None:
    """L1. MUST FAIL if a genuine repeat attestation is dropped without a word. The
    cross-document sibling prices and names every drop; this one was a hard-coded
    p_one=1.0 that said nothing. Killed by removing the resolution note."""
    same = dict(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=250.0,
                entity="acct-a", label_raw="Deposit")
    tp = _compose([_addend(**same), _addend(**same)])
    assert tp.k == 1, "a byte-identical repeat attestation should still collapse"
    assert tp.dedup_resolutions, (
        "a within-doc observation was dropped and dedup_resolutions is empty — a silent "
        "drop is the defect, whether or not the drop is correct"
    )


# --- L2: the issuer fold --------------------------------------------------------------

def test_poison_the_issuer_fold_spans_both_readings() -> None:
    """L2. MUST FAIL if `top == sum(rest)` is treated as proof. Three deposits of
    300/100/200 in one document with no stated total are 600; master reported 300 and
    asserted the fold reading as fact. Killed by returning only the fold."""
    tp = _compose([
        _addend(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=300.0),
        _addend(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=100.0),
        _addend(doc_key="stmt", basis="monthly", as_of="2025-07-31", amount=200.0)])
    assert tp.point == pytest.approx(300.0), "the fold stays the likelier reading"
    assert tp.hi >= 600.0, (
        f"interval [{tp.lo}, {tp.hi}] excludes the sum-all reading 600.00 — an arithmetic "
        f"coincidence in a 3-row cluster is ordinary, and the fold is a hypothesis"
    )
    assert "reading" in tp.basis_note.lower() or "coincid" in tp.basis_note.lower(), (
        f"the fold is asserted as fact: {tp.basis_note!r}"
    )


# --- L3: nothing leaves unnamed -------------------------------------------------------

def test_poison_an_excluded_row_is_named_with_its_value() -> None:
    """L3. MUST FAIL if a grounded contradicting read vanishes. A roll-up dated one day
    before the scope end is not recognised as a channel and leaves via `excluded_basis`,
    outside the interval — master reported a zero-width 324 with a grounded 31937 in the
    pool and said nothing. Killed by dropping the exclusion note."""
    tp = _compose([_addend(doc_key="stmt", basis="other", as_of="2025-09-29",
                           amount=31937.0), *_series([7, 8, 9])])
    assert "31937" in tp.basis_note, (
        f"a grounded row was excluded from the sum and its value is nowhere in the note: "
        f"{tp.basis_note!r} — an unnamed contradicting read is invisible to the reader"
    )


# --- L5: the fixtures cover the class, not one literal --------------------------------

@pytest.mark.parametrize("basis", sorted(_COARSE_BASES))
def test_poison_the_join_fires_for_every_coarse_basis(basis: str) -> None:
    """L5. MUST FAIL for any member of `_COARSE_BASES` the join does not treat as a
    roll-up. The r24 fixtures all used `basis="other"`, so a branch keyed on a sibling
    value would have gone unseen. Killed by keying the join on one literal."""
    months = _series([7, 8, 9])
    tp = _compose([_addend(doc_key="stmt", basis=basis, as_of="2025-09-30",
                           amount=31937.0), *months])
    assert tp.k == 1 + len(months), (
        f"basis={basis!r} is in _COARSE_BASES but did not join: k={tp.k}"
    )


def test_coarse_bases_is_the_set_the_composition_reads() -> None:
    """Precision control: pins the declared set whole, so adding a basis without extending
    the fixtures above fails here rather than passing silently."""
    assert frozenset({"quarterly", "annual", "other"}) == _COARSE_BASES
