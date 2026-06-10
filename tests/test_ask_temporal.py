"""Pure temporal helpers of the ask REPL (D1): command parsing + footer.

Same dependency-free style as tests/test_ask.py — the live projection path is
covered by tests/test_temporal.py; here we pin the REPL grammar and the
nothing-vanishes rendering contract.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent.core.temporal import TemporalView

# --- /recent and /since parsing -------------------------------------------- #


def test_plain_question_has_no_temporal() -> None:
    q, since, until, recent = ask.parse_temporal_command("what is my ID?")
    assert (q, since, until, recent) == ("what is my ID?", None, None, False)


def test_recent_prefix() -> None:
    q, since, until, recent = ask.parse_temporal_command("/recent any invoices?")
    assert (q, since, until, recent) == ("any invoices?", None, None, True)


def test_since_prefix() -> None:
    q, since, until, recent = ask.parse_temporal_command(
        "/since 2026-05-01 appointments")
    assert q == "appointments"
    assert since == date(2026, 5, 1)
    assert until is None
    assert recent is False


def test_since_with_bad_date_is_not_swallowed() -> None:
    q, since, until, recent = ask.parse_temporal_command("/since soon dentist")
    # An unparseable date must not silently become an untemporal question:
    # the whole line is returned unchanged so the REPL can complain.
    assert (q, since, until, recent) == ("/since soon dentist", None, None, False)


# --- footer: nothing vanishes ----------------------------------------------- #


def _view() -> TemporalView:
    return TemporalView(
        admitted=["aa" * 32],
        excluded=[("bb" * 32, date(2020, 3, 1))],
        undated=["cc" * 32],
        underived=["dd" * 32],
        remedies=[f"pkm derive doc_date_pandoc --input {'dd' * 32}"],
    )


def _names() -> dict[str, str]:
    return {"aa" * 32: "lease.eml", "bb" * 32: "report.pdf",
            "cc" * 32: "scan.png", "dd" * 32: "notes.txt"}


def test_footer_names_every_partition() -> None:
    footer = ask.temporal_footer(_view(), _names())
    assert "1 admitted" in footer
    assert "report.pdf (2020-03-01)" in footer          # excluded, with date
    assert "scan.png" in footer                          # undated, named
    assert "notes.txt" in footer                         # underived, named
    assert f"pkm derive doc_date_pandoc --input {'dd' * 32}" in footer
    assert "/derive" in footer                           # the REPL remedy hint


def test_footer_empty_view_is_quiet() -> None:
    view = TemporalView(admitted=["aa" * 32], excluded=[], undated=[],
                        underived=[], remedies=[])
    footer = ask.temporal_footer(view, _names())
    assert "1 admitted" in footer
    assert "excluded" not in footer
    assert "derive" not in footer
