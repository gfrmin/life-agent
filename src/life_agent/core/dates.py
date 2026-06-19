"""Calendar-date parsing — the one canonical date normaliser.

Shared by the lookup family (candidate de-dup keys on the ISO date, so the same date written in
different formats collapses to one candidate — q-003) and the matcher (so a date asserted in one
format is graded equal to a gold written in another). A numeric D/M/Y parses only when day-vs-month
is FORCED (one of the first two components > 12); a fully ambiguous numeric date (both ≤ 12) stays
unparsed — keeping two such values separate is safer than risking a merge of two DIFFERENT dates.
"""
from __future__ import annotations

import re
from datetime import date

MONTH_NAMES: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def iso_or_none(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_date(value: str) -> str | None:
    """An ISO date string iff ``value`` is an UNAMBIGUOUS calendar date, else None."""
    v = " ".join(value.split())
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    if m:
        return iso_or_none(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})", v, re.IGNORECASE)
    if m and m[2].lower() in MONTH_NAMES:
        return iso_or_none(int(m[3]), MONTH_NAMES[m[2].lower()], int(m[1]))
    m = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", v, re.IGNORECASE)
    if m and m[1].lower() in MONTH_NAMES:
        return iso_or_none(int(m[3]), MONTH_NAMES[m[1].lower()], int(m[2]))
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", v)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if a > 12 and b <= 12:
            return iso_or_none(y, b, a)
        if b > 12 and a <= 12:
            return iso_or_none(y, a, b)
    return None
