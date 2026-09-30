"""The loss-shape construct (bayesian-foundations, r30 step 1 — "the answer is a claim
about a quantity, and utility is a loss over (claim, truth)").

Each question has an answer SPACE — `exact` · `quantity` · `threshold` · `set` — and
:func:`life_agent.core.decide.shaped_u_bar` prices a shape by scaling ``u_correct`` /
``u_wrong`` with the owner's per-shape latents. This module holds the vocabulary (the
one list `core.utility` names those latents from). No live path classifies a question
into a shape: every decision runs at ``DEFAULT_SHAPE``.
"""
from __future__ import annotations

# --- the vocabulary --------------------------------------------------------------------

EXACT = "exact"
QUANTITY = "quantity"
THRESHOLD = "threshold"
SET = "set"
SHAPES: frozenset[str] = frozenset({EXACT, QUANTITY, THRESHOLD, SET})

# The anchor: u_correct=1/u_wrong pass through core.decide.shaped_u_bar unscaled for this
# shape — today's §4.4 convention, unchanged. Also the conservative default (C1/C3): an
# unmatched question reads as the shape under which today's design is adequate.
ANCHOR_SHAPE: str = EXACT
DEFAULT_SHAPE: str = EXACT

# Every non-anchor shape, in a deterministic (sorted) order — the two per-shape utility
# latents in core.utility (voi_scale_<shape>/regret_scale_<shape>) are named from this
# tuple, never retyped, so the latent vocabulary cannot drift from it.
SCALED_SHAPES: tuple[str, ...] = tuple(sorted(SHAPES - {ANCHOR_SHAPE}))


