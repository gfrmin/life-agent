"""Unit tests for the deterministic citation-faithfulness guard (scripts/citation_guard.py).

Run: uv run --project . python -m pytest tests/test_citation_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import citation_guard as cg


def _card(n: int, text: str):
    return SimpleNamespace(n=n, text=text)


def test_supported_id_citation_is_clean() -> None:
    a = cg.audit("Your Israeli ID is 123456789 [1].", [_card(1, "ID number 123456789 issued 2009")])
    assert a.ok
    assert a.footer() == ""


def test_unsupported_id_is_flagged() -> None:
    # the 2026-06-02 failure shape: a different person's ID asserted as the owner's
    a = cg.audit("Your Israeli ID is 222222222 [1].", [_card(1, "owner ID 123456789 confirmed")])
    assert not a.ok
    assert a.unsupported[0][1] == 1


def test_token_boundary_not_substring() -> None:
    # 123456789 must NOT count as present inside 1123456789 (reuses answer_matches' boundary)
    a = cg.audit("The number is 123456789 [1].", [_card(1, "code 1123456789 here")])
    assert not a.ok


def test_dangling_marker_when_no_such_card() -> None:
    a = cg.audit("Something asserted [9].", [_card(1, "x")])
    assert a.dangling == (9,)


def test_multi_citation_sentence_each_supported() -> None:
    a = cg.audit(
        "Spend was 1200 [1] and tax 3400 [2].",
        [_card(1, "invoice total 1200 usd"), _card(2, "tax of 3400 paid")],
    )
    assert a.ok


def test_proper_noun_supported_vs_unsupported() -> None:
    ok = cg.audit("Your manager is Hai Le [1].", [_card(1, "regards, Hai Le (manager)")])
    assert ok.ok
    bad = cg.audit("Your manager is Hai Le [1].", [_card(1, "no name in this chunk")])
    assert not bad.ok


def test_prose_without_values_not_gated() -> None:
    # a claim with no verifiable value span is left to the eval judge, never hard-flagged
    a = cg.audit("This appears relevant to your question [1].", [_card(1, "unrelated text")])
    assert a.ok


def test_uncited_value_not_flagged() -> None:
    # owner-profile facts arrive uncited; the guard only audits *cited* claims
    a = cg.audit("Your name is Ada Lovelace.", [_card(1, "irrelevant")])
    assert a.ok


def test_footer_summarises_problems() -> None:
    a = cg.audit("ID 222222222 [1].", [_card(1, "owner 123456789")])
    f = a.footer()
    assert "⚠ unverified" in f and "[1]" in f
