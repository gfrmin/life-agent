"""The loss-shape construct (r30 step 1, `docs/unification/reports/r30-units-lever.md`).

`core.answer_shape` holds the shape vocabulary the per-shape utility latents are named from.
"""
from __future__ import annotations

from life_agent.core import answer_shape as AS

# --- the vocabulary ------------------------------------------------------------------

def test_shapes_is_the_closed_vocabulary() -> None:
    assert frozenset({"exact", "quantity", "threshold", "set"}) == AS.SHAPES


def test_exact_is_the_anchor_and_the_default() -> None:
    assert AS.ANCHOR_SHAPE == "exact"
    assert AS.DEFAULT_SHAPE == "exact"


def test_scaled_shapes_excludes_the_anchor_and_is_deterministic() -> None:
    assert AS.SCALED_SHAPES == ("quantity", "set", "threshold")
    assert AS.ANCHOR_SHAPE not in AS.SCALED_SHAPES
