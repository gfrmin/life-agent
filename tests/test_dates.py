"""The canonical calendar-date normaliser + the matcher's date-awareness (the q-003 grader fix).

All values here are SYNTHETIC (no owner PII): a worked example date is 25 December 1999.

    uv run --project . python -m pytest tests/test_dates.py
"""
from __future__ import annotations

from life_agent.core.dates import parse_date
from life_agent.core.matching import answer_matches


def test_parse_date_canonicalises_common_formats() -> None:
    for v in ("25/12/1999", "25 December 1999", "December 25, 1999", "25th Dec 1999",
              "1999-12-25", "25-12-1999"):
        assert parse_date(v) == "1999-12-25", v


def test_parse_date_leaves_ambiguous_or_non_dates_unparsed() -> None:
    assert parse_date("05/06/1999") is None       # both ≤ 12 ⇒ day-vs-month ambiguous ⇒ unparsed
    assert parse_date("25 December") is None       # no year
    assert parse_date("not a date") is None
    assert parse_date("12345") is None             # a bare number is not a date


def test_matcher_grades_a_date_across_formats() -> None:
    # q-003-class: the daemon reports "25 December 1999"; the gold is "25/12/1999" — same date, ≡.
    assert answer_matches("25/12/1999", [], "25 December 1999")
    assert answer_matches("25 December 1999", [], "25/12/1999")


def test_matcher_does_not_loosen_non_dates_or_documents() -> None:
    # token-boundary for non-dates is unchanged (no substring false positives)
    assert not answer_matches("777", [], "the code was 4777 today")
    # a date value is NOT matched inside a long document by the date path (parse_date(doc) is None);
    # the in-document case still relies on token containment …
    assert not answer_matches("25/12/1999", [], "the meeting was on 1 January 2000 in Tel Aviv")
    # … which still works when the date is literally present.
    assert answer_matches("25 December 1999", [], "dated 25 December 1999 at the office")
