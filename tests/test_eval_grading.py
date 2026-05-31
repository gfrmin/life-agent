"""Unit tests for the answer-grounded eval grading logic (scripts/eval_grading.py).

Run in the pkm env (has pytest):
    uv run --project ../pkm python -m pytest ./tests/test_eval_grading.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_grading import (  # noqa: E402
    answer_matches,
    classify,
    tokenize,
)


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


# --- verdict classification ------------------------------------------------


def test_pass_when_answer_in_topk() -> None:
    v = classify(answer_in_topk=True, answer_in_corpus=True,
                 distractor_in_topk=False, mode_hint=None)
    assert v.verdict == "PASS"
    assert v.subject_confusion is False


def test_retrieval_miss_when_in_corpus_not_topk() -> None:
    v = classify(answer_in_topk=False, answer_in_corpus=True,
                 distractor_in_topk=False, mode_hint=None)
    assert v.verdict == "RETRIEVAL_MISS"


def test_absent_splits_by_mode_hint() -> None:
    assert classify(answer_in_topk=False, answer_in_corpus=False,
                    distractor_in_topk=False, mode_hint="coverage").verdict == "ABSENT_COVERAGE"
    assert classify(answer_in_topk=False, answer_in_corpus=False,
                    distractor_in_topk=False, mode_hint="extraction").verdict == "ABSENT_EXTRACTION"
    assert classify(answer_in_topk=False, answer_in_corpus=False,
                    distractor_in_topk=False, mode_hint=None).verdict == "ABSENT_UNSPECIFIED"


def test_subject_confusion_is_orthogonal_to_verdict() -> None:
    # PASS + confused (answer found AND distractor present)
    v = classify(answer_in_topk=True, answer_in_corpus=True,
                 distractor_in_topk=True, mode_hint=None)
    assert v.verdict == "PASS" and v.subject_confusion is True
    # MISS + confused
    v2 = classify(answer_in_topk=False, answer_in_corpus=True,
                  distractor_in_topk=True, mode_hint=None)
    assert v2.verdict == "RETRIEVAL_MISS" and v2.subject_confusion is True
