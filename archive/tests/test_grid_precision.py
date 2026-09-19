"""Hermetic guards for `scripts/membrane/grid_precision.py` (r46 leg B).

No engine, no subprocess: the pure surfaces only — the lattice snap, the grid-identity
check `T3` decides on, and the drift test that pins the instrument's boot snapshot to the
DEPLOYED one. The engine-driven legs are measurements, not assertions, and live in the
report.

Fixture values are synthetic (public repo, PRINCIPLES §12) — no owner data.
"""
from __future__ import annotations

import ast
import sys
from fractions import Fraction
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from membrane.grid_precision import dyadic, grid_identity  # noqa: E402

# PII-OK: synthetic grid, the SHAPE of a theta grid (two close rungs, two endpoints)
_GRID = [0.048057099794822, 0.05, 0.18, 0.339, 0.857, 0.864, 0.95, 0.9906339522695138]


def test_snapping_makes_every_denominator_exactly_k_bits_or_fewer() -> None:
    """The lever's mechanism, pinned: cost tracks the dyadic denominator's BIT LENGTH, and
    snapping is what bounds it. An IEEE double is already dyadic — the deployed grid's
    values are 54-57 bit — so the snap does not make values dyadic, it makes them SHORT."""
    for k in (8, 14, 24, 30):
        for value in dyadic(_GRID, k):
            assert Fraction(value).denominator.bit_length() - 1 <= k
    for value in _GRID:  # the premise the above rests on
        denominator = Fraction(value).denominator
        assert denominator & (denominator - 1) == 0, "an IEEE double is always dyadic"


def test_grid_identity_rejects_a_lattice_that_merges_rungs() -> None:
    """T3's kill. Sixteenths do not merely place a rung near-but-not-at a threshold — on
    this grid they MERGE two pairs, collapsing n from 8 to 6, which changes the hypothesis
    space (`models = n(17n-16)`) and so is a different lever wearing this one's clothes."""
    coarse = grid_identity(_GRID, dyadic(_GRID, 4))
    assert coarse["n_after"] < coarse["n_before"]
    assert coarse["no_merge"] is False


@pytest.mark.parametrize("k", [8, 11, 14, 24, 30])
def test_grid_identity_accepts_lattices_that_preserve_the_grid(k: int) -> None:
    ident = grid_identity(_GRID, dyadic(_GRID, k))
    assert ident["n_after"] == ident["n_before"] == len(_GRID)
    assert ident["sorted"] is True
    assert ident["no_merge"] is True


def test_displacement_shrinks_monotonically_with_the_lattice_exponent() -> None:
    displacements = [grid_identity(_GRID, dyadic(_GRID, k))["max_displacement"]
                     for k in (4, 8, 14, 24, 30)]
    assert displacements == sorted(displacements, reverse=True)


def test_the_instrument_binds_the_bridge_s_own_boot_snapshot() -> None:
    """A DRIFT test for the defect that nearly voided `T2`.

    A first pass copied `p0_engine_replay.py`'s two-argument `boot_snapshot` call, which
    omits `warm_vectors_dir` and the Claude verdict channel. That snapshot holds 70
    verdicts where the deployed one reaches 250 — so every "depth 250" row would have been
    a depth-70 row wearing the label. The instrument must pass what
    `bridge/server.py` passes: both positional logs, the warm-vectors dir, AND
    `claude_verdicts_path`."""
    source = (REPO / "scripts" / "membrane" / "grid_precision.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "boot_snapshot"]
    assert len(calls) == 1, "one snapshot declaration, or the drift this test exists for"
    call = calls[0]
    assert len(call.args) == 3, "decisions, reactions AND warm_vectors_dir"
    assert {kw.arg for kw in call.keywords} == {"claude_verdicts_path"}
    assert not any(isinstance(a, ast.Constant) and a.value is None for a in call.args), (
        "a None argument is the truncation this test exists to catch"
    )
