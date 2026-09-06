"""ATM-Bench's evaluator, vendored at a pinned sha (r51b 2e). MIT (LICENSE-ATM-Bench) inside an
AGPL repo, notice kept; provenance and the one edit per file in SOURCE; pinned by
``tests/test_atm_vendored.py``. No vendored logic is edited — a behaviour change goes in a wrapper.

Public surface: ``detect_qtype(answer)`` (answer-typed: ``number`` / ``list_recall`` /
``open_end``), ``is_abstention(text)``, ``atm_number_match(gold, pred, question)``.
"""
from __future__ import annotations

from .abstention import ABSTENTION_PHRASES
from .matcher import deterministic_accuracy
from .normalizer import extract_reference_date, is_abstention, resolve_relative_dates
from .qtype_utils import QTYPE_LIST, QTYPE_NUMBER, QTYPE_OPEN, detect_qtype

UPSTREAM_SHA = "ef4e5dff1a47ec71213a06e359f02753defa8fb1"


def atm_number_match(gold: str, pred: str, question: str | None) -> bool:
    """The benchmark's own verdict on a ``number`` row: relative dates resolved against the
    question's "Today is …" anchor, parentheticals and currency breakdowns stripped, codes exact,
    then normalised comparison — ``deterministic_accuracy`` unchanged."""
    return bool(deterministic_accuracy(gold, pred, question))


__all__ = ["ABSTENTION_PHRASES", "QTYPE_LIST", "QTYPE_NUMBER", "QTYPE_OPEN", "UPSTREAM_SHA",
           "atm_number_match", "detect_qtype", "extract_reference_date", "is_abstention",
           "resolve_relative_dates"]
