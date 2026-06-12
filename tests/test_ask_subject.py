"""The D2 ask-path surface: the deterministic owner-possessive trigger, the
nothing-vanishes owner-filter footer, and the report composition with D1.

Same dependency-free style as tests/test_ask_temporal.py — the live
projection/verdict path is covered by tests/test_subject.py; here we pin the
trigger rule (an UNCHAINED first-person possessive: "my X" fires, "my
partner's X" does not — the subject-confusion pair), the footer rendering
(every partition set named), and that a temporal and a subject report
compose: both footers print, both target lists feed one /derive.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent.core.subject import SubjectView

# --- the trigger: unchained first-person possessive -------------------------- #


def test_owner_possessive_triggers() -> None:
    assert ask.owner_question("What is my Israeli ID number?")
    assert ask.owner_question("what is the owner's ID?")
    assert ask.owner_question("is this passport mine?")
    assert ask.owner_question("MY mortgage balance")  # case-insensitive


def test_relational_possessive_does_not_trigger() -> None:
    """'my partner's X' hands the subject to someone else — filtering for the
    owner would exclude exactly the right answer."""
    assert not ask.owner_question("What is my partner's Israeli ID number?")
    assert not ask.owner_question("my wife's passport number")
    assert not ask.owner_question("the owner's partner's visa")


def test_unpossessed_question_does_not_trigger() -> None:
    assert not ask.owner_question("history of Israel")
    assert not ask.owner_question("what invoices arrived last month?")
    assert not ask.owner_question("myopia treatment options")  # no word-boundary hit


# --- the footer: every partition set named ----------------------------------- #


def test_subject_footer_names_every_set() -> None:
    view = SubjectView(
        admitted=["a" * 64, "e" * 64, "f" * 64],
        excluded_other=[("b" * 64, "Other Person")],
        excluded_generic=["d" * 64],
        unclear=["e" * 64],
        underived=["f" * 64],
        remedies=["pkm derive doc_subject_pandoc --input " + "f" * 64],
    )
    name_of = {"b" * 64: "other.pdf", "d" * 64: "form.pdf",
               "e" * 64: "x.pdf", "f" * 64: "y.pdf"}
    footer = ask.subject_footer(view, name_of)
    assert "3 admitted" in footer
    assert "someone else's" in footer and "Other Person" in footer
    assert "other.pdf" in footer
    assert "generic/template" in footer and "form.pdf" in footer
    assert "unclear — kept" in footer and "x.pdf" in footer
    assert "not yet subject-derived — kept" in footer and "y.pdf" in footer
    assert "/derive" in footer and view.remedies[0] in footer


def test_subject_footer_quiet_when_all_admitted_cleanly() -> None:
    view = SubjectView(admitted=["a" * 64], excluded_other=[],
                       excluded_generic=[], unclear=[], underived=[],
                       remedies=[])
    assert ask.subject_footer(view, {}) == "owner filter: 1 admitted"


# --- composition: D1 and D2 reports merge, nothing displaces nothing --------- #


def test_ask_once_merges_temporal_and_subject_reports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_answer(conn: object, q: str, k: int, **kw: object) -> tuple:
        ask.TEMPORAL_LAST = ask.TemporalReport(
            footer="date filter: 1 admitted",
            targets=[("doc_date_pandoc", "a" * 64)])
        ask.SUBJECT_LAST = ask.TemporalReport(
            footer="owner filter: 1 admitted",
            targets=[("doc_subject_pandoc", "b" * 64)])
        return ("an answer", [], {})

    monkeypatch.setattr(ask, "answer", fake_answer)
    monkeypatch.setattr(ask, "capture", lambda *a, **k: None)
    targets = ask.ask_once(None, "q", 8)

    out = capsys.readouterr().out
    assert "date filter: 1 admitted" in out
    assert "owner filter: 1 admitted" in out
    assert targets == [("doc_date_pandoc", "a" * 64),
                       ("doc_subject_pandoc", "b" * 64)]
