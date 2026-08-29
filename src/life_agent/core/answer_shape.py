"""The loss-shape construct (bayesian-foundations, r30 step 1 — "the answer is a claim
about a quantity, and utility is a loss over (claim, truth)").

r29 (`docs/unification/reports/r29-answer-shape-census.md`) classified 250 questions by
answer SPACE — `exact` · `quantity` · `threshold` · `set` — under rules frozen before the
census read, and measured the rules' own error against a blind manual reference (agreement
0.74, disagreement one-directional toward `exact`). This module is the ONE copy of those
rules: `scripts/answer_shape_census.py` imports from here rather than holding a second
copy, so the decision-path classifier that `core.decide.shaped_u_bar` prices against and
the audited r29 instrument can never drift apart (C2).

Pure and cheap — a regex predicate over the question text, no model call, no cache, in the
same family as `terminals.owner_question` — not a pkm §2-contract instrument (there is no
model call here to make caching worth its complexity; disclosed deviation from the
original plan's "cached instrument" language, `docs/unification/reports/r30-units-lever.md`).

Conservative default **unknown → `exact`** (C1/C3): a question the rules do not recognise
gets today's 0-1 loss unchanged, never a wider one.
"""
from __future__ import annotations

import re

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
# tuple, never retyped, so the latent vocabulary and the classifier vocabulary cannot
# drift apart either.
SCALED_SHAPES: tuple[str, ...] = tuple(sorted(SHAPES - {ANCHOR_SHAPE}))


def normalise(text: str) -> str:
    """Lowercase, whitespace-collapsed — the one normalisation r29's census used."""
    return re.sub(r"\s+", " ", str(text).strip().lower())


# r29's frozen rules (docs/unification/reports/r29-answer-shape-census.md), transcribed
# once. Ordered; first match wins; no match falls to DEFAULT_SHAPE. Editing a pattern here
# is a new checkpoint, not a fix (r29's own discipline, carried forward).
_COMPARATORS: tuple[str, ...] = (
    r"\bmore than\b", r"\bless than\b", r"\bat least\b", r"\bat most\b",
    r"\bexceed(s|ed|ing)?\b", r"\bgreater than\b", r"\bhigher than\b", r"\blower than\b",
    r"\bover\s+\d", r"\bunder\s+\d", r"\babove\s+\d", r"\bbelow\s+\d",
)
_YES_NO = r"^(did|is|was|were|does|do|has|have|had|are|am|will|can)\b"

SPACE_RULES: list[tuple[str, list[str]]] = [
    (THRESHOLD, list(_COMPARATORS)),
    (SET, [r"\blist\b", r"\bwhich ones\b", r"\ball of the\b", r"\bwhat are the\b",
           r"\bwho are the\b", r"\bname the\b", r"\benumerate\b", r"\bevery\s+\w+s\b"]),
    (QUANTITY, [r"\bhow many\b", r"\bhow much\b", r"\btotal\b", r"\bsum\b", r"\baverage\b",
                r"\bmean of\b", r"\bcount of\b", r"\bnumber of\b", r"\bamount\b",
                r"\bbalances?\b", r"\baggregate\b"]),
]


def answer_space(text: str) -> str:
    """The question's answer shape — first SPACE_RULES pattern to match, in the frozen
    precedence order threshold > set > quantity > exact; DEFAULT_SHAPE on no match."""
    t = normalise(text)
    for label, patterns in SPACE_RULES:
        if any(re.search(p, t) for p in patterns):
            return label
        if label == THRESHOLD and re.search(_YES_NO, t) and re.search(r"\d", t):
            return THRESHOLD
    return DEFAULT_SHAPE
