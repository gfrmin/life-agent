"""The grader: the token-boundary matcher and ``eval.grading``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import grading as G
from life_agent.core import decisions as DEC
from life_agent.core.matching import answer_matches, tokenize

# --- tokenization ---------------------------------------------------------


def test_tokenize_splits_on_nonalphanumeric_and_casefolds() -> None:
    assert tokenize("NIS 50,000") == ["nis", "50", "000"]
    assert tokenize("2099-12-31") == ["2099", "12", "31"]
    assert tokenize("user@example.com") == ["user", "example", "com"]


def test_tokenize_keeps_hebrew() -> None:
    assert tokenize("תעודת זהות") == ["תעודת", "זהות"]


# --- token-boundary matching (false-positive guards) ----------------------


def test_matches_exact_token() -> None:
    assert answer_matches("123456789", [], "my id is 123456789 ok")


def test_does_not_match_inside_longer_number() -> None:
    # the whole point: substring would falsely match; token-boundary must not
    assert not answer_matches("123456789", [], "ref 1123456789 trailing")
    assert not answer_matches("123456789", [], "1234567891 extra")


def test_amount_matches_via_variant_not_inside_other_number() -> None:
    # "50,000" tokenizes to [50,000]; matches "NIS 50,000" but not "150000"
    assert answer_matches("50,000", ["50000"], "salary NIS 50,000 gross")
    assert not answer_matches("50,000", ["50000"], "loan 150000 total")


def test_multi_token_answer_must_be_contiguous() -> None:
    assert answer_matches("2099-12-31", [], "ends 2099-12-31.")
    # same tokens but not contiguous -> no match
    assert not answer_matches("acme corp", [], "slice corp and global inc")
    assert answer_matches("acme corp", [], "at Acme Corp Ltd")


def test_variant_forms() -> None:
    assert answer_matches("123456789", ["0123456789"], "examplecare member 0123456789")


# --- eval.grading ---------------------------------------------------------


def test_realised_report_token_boundary() -> None:
    # 123456789 does NOT match inside 1123456789  # PII-OK: synthetic digit runs
    assert G.realised_report(["your id is 123456789"], "123456789", [])
    assert not G.realised_report(["your id is 1123456789"], "123456789", [])
    assert G.realised_report(["expires 14/08/2031"], "2031-08-14", ["14/08/2031"])
    # an unanswerable question (empty gold) is never a correct report
    assert not G.realised_report(["anything at all"], "", [])


def test_withheld_reason_is_a_closed_set_and_assertions_cannot_carry_one() -> None:
    with pytest.raises(ValueError):
        G.RealisedResponse(action="abstain", withheld="unavailble")  # typo
    with pytest.raises(ValueError):
        G.RealisedResponse(action="report", correct=True, withheld="miss")
    with pytest.raises(ValueError):
        G.RealisedResponse(action="guess")


def test_the_partition_covers_the_recorded_action_vocabulary() -> None:
    assert G.ASSERT_ACTIONS | G.WITHHOLD_ACTIONS | G.CITE_ACTIONS == DEC.ACTIONS
    assert G.ASSERT_ACTIONS.isdisjoint(G.WITHHOLD_ACTIONS)
    assert G.CITE_ACTIONS.isdisjoint(G.ASSERT_ACTIONS | G.WITHHOLD_ACTIONS)


def test_a_cite_is_graded_right_or_wrong_and_names_its_document() -> None:
    right = G.RealisedResponse(action="cite", correct=True, cited="k1")
    assert (right.correct, right.cited, right.withheld) == (True, "k1", None)
    assert G.RealisedResponse(action="cite", correct=False, cited="k2").correct is False
    with pytest.raises(ValueError):
        G.RealisedResponse(action="cite", correct=None, cited="k1")   # not graded
    with pytest.raises(ValueError):
        G.RealisedResponse(action="cite", correct=True)               # names nothing
    with pytest.raises(ValueError):
        G.RealisedResponse(action="cite", correct=True, cited="k1", withheld="miss")
    with pytest.raises(ValueError):
        G.RealisedResponse(action="report", correct=True, cited="k1")
