"""The loss-shape construct (r30 step 1, `docs/unification/reports/r30-units-lever.md`).

`core.answer_shape` is the ONE copy of r29's frozen classification rules (the r29 census
script that bound it is archived at J0). Pure, hermetic: no model call, no cache, no Brain.
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


# --- C1: the conservative default -----------------------------------------------------

def test_an_unmatched_question_classifies_exact() -> None:
    assert AS.answer_space("What is the reference code on the form?") == "exact"


def test_no_cue_words_stay_exact() -> None:
    for text in ("Who signed it?", "Where is the office?", "What colour is it?"):
        assert AS.answer_space(text) == "exact", text


# --- the frozen rules classify each non-default shape ----------------------------------

def test_threshold_cues_classify_threshold() -> None:
    assert AS.answer_space("Is the balance more than 500?") == "threshold"
    assert AS.answer_space("Was it under 500?") == "threshold"


def test_set_cues_classify_set() -> None:
    assert AS.answer_space("List the companies I have owned.") == "set"
    assert AS.answer_space("What are the properties associated with me?") == "set"


def test_quantity_cues_classify_quantity() -> None:
    assert AS.answer_space("How many accounts do I have?") == "quantity"
    assert AS.answer_space("What is the total across all documents?") == "quantity"


def test_precedence_order_is_threshold_set_quantity_exact() -> None:
    # a question carrying both a threshold cue and a quantity cue reads threshold first
    # (r29's frozen precedence, reused verbatim — SPACE_RULES's declared order).
    assert AS.answer_space("Is the total amount more than 500?") == "threshold"


def test_classify_is_case_insensitive_and_whitespace_normalised() -> None:
    assert AS.answer_space("  HOW   MANY   accounts?  ") == "quantity"
