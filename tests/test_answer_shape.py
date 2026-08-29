"""The loss-shape construct (r30 step 1, `docs/unification/reports/r30-units-lever.md`).

`core.answer_shape` is the ONE copy of r29's frozen classification rules — the census
script (`scripts/answer_shape_census.py`) imports from here rather than holding a second
copy (C2), so the decision-path classifier and the audited r29 instrument can never drift
apart. Pure, hermetic: no model call, no cache, no Brain.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from life_agent.core import answer_shape as AS

_CENSUS_SRC = Path(__file__).resolve().parent.parent / "scripts" / "answer_shape_census.py"


def _load_census():
    spec = importlib.util.spec_from_file_location("answer_shape_census", _CENSUS_SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["answer_shape_census"] = mod
    spec.loader.exec_module(mod)
    return mod


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


# --- C2: one rule table, never retyped --------------------------------------------------

def test_the_census_script_imports_the_same_rule_table_object() -> None:
    census = _load_census()
    # object identity, not mere equality: a reverted census script that redefines its own
    # SPACE_RULES tuple breaks this immediately, even if the values still happened to match.
    assert census.SPACE_RULES is AS.SPACE_RULES
    assert census.DEFAULT_SPACE is AS.DEFAULT_SHAPE
    assert census.answer_space is AS.answer_space
    assert census.normalise is AS.normalise
