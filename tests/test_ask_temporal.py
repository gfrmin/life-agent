"""Pure line-grammar of the ask REPL (the interaction contract) + the D1 footer.

Same dependency-free style as tests/test_ask.py — the live projection path is
covered by tests/test_temporal.py; here we pin the ONE line grammar (identical
in REPL and one-shot argv, docs/interaction-contract.md), its composition
rules (nothing silent, nothing arbitrary), and the nothing-vanishes rendering.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent.core.temporal import TemporalView

# --- the line grammar: plain asks ------------------------------------------- #


def test_plain_question_is_an_untemporal_ask() -> None:
    p = ask.parse_line("what is my ID?")
    assert p.kind == "ask"
    assert (p.question, p.since, p.until, p.recent) == ("what is my ID?", None, None, False)


def test_empty_line_is_empty() -> None:
    assert ask.parse_line("   ").kind == "empty"


# --- temporal prefixes ------------------------------------------------------- #


def test_recent_prefix_ranks_only() -> None:
    p = ask.parse_line("/recent any invoices?")
    assert p.kind == "ask"
    assert (p.question, p.since, p.until, p.recent) == ("any invoices?", None, None, True)


def test_since_prefix() -> None:
    p = ask.parse_line("/since 2026-05-01 appointments")
    assert p.kind == "ask"
    assert p.question == "appointments"
    assert p.since == date(2026, 5, 1)
    assert p.until is None and p.recent is False


def test_until_prefix() -> None:
    p = ask.parse_line("/until 2026-06-01 appointments")
    assert p.kind == "ask"
    assert p.question == "appointments"
    assert p.until == date(2026, 6, 1)
    assert p.since is None and p.recent is False


def test_since_and_until_compose_into_a_range() -> None:
    p = ask.parse_line("/since 2026-01-01 /until 2026-03-31 what invoices?")
    assert p.kind == "ask"
    assert p.question == "what invoices?"
    assert (p.since, p.until) == (date(2026, 1, 1), date(2026, 3, 31))


def test_bounds_compose_in_either_order() -> None:
    p = ask.parse_line("/until 2026-03-31 /since 2026-01-01 what invoices?")
    assert p.kind == "ask"
    assert (p.since, p.until) == (date(2026, 1, 1), date(2026, 3, 31))


def test_single_day_range_is_valid() -> None:
    p = ask.parse_line("/since 2026-05-01 /until 2026-05-01 anything?")
    assert p.kind == "ask"


# --- composition errors: rejected with the rule, never silently resolved ----- #


def test_bad_date_is_a_loud_error() -> None:
    p = ask.parse_line("/since soon dentist")
    assert p.kind == "error"
    assert "YYYY-MM-DD" in p.error


def test_duplicate_bound_is_an_error() -> None:
    p = ask.parse_line("/since 2026-01-01 /since 2026-02-01 q")
    assert p.kind == "error"
    assert "once" in p.error


def test_recent_with_a_bound_is_an_error_naming_the_rule() -> None:
    p = ask.parse_line("/recent /since 2026-01-01 q")
    assert p.kind == "error"
    assert "newest-first" in p.error  # the rule, spelled out


def test_empty_range_is_an_error() -> None:
    p = ask.parse_line("/since 2026-06-01 /until 2026-01-01 q")
    assert p.kind == "error"
    assert "empty range" in p.error


def test_unknown_slash_command_is_an_error_naming_the_grammar() -> None:
    # The silent-typo bug: '/sinc …' must never be asked as a literal question.
    p = ask.parse_line("/sinc 2026-01-01 dentist")
    assert p.kind == "error"
    assert "/sinc" in p.error
    assert "/since YYYY-MM-DD QUESTION" in p.error  # the grammar is named


def test_temporal_prefix_without_a_question_is_an_error() -> None:
    assert ask.parse_line("/recent").kind == "error"
    assert ask.parse_line("/since 2026-01-01").kind == "error"


# --- teaching, deriving, quitting -------------------------------------------- #


def test_tell_carries_the_fact() -> None:
    p = ask.parse_line("/tell My name is Ada Lovelace")
    assert p.kind == "tell"
    assert p.fact == "My name is Ada Lovelace"


def test_tell_without_a_fact_is_an_error() -> None:
    assert ask.parse_line("/tell").kind == "error"


def test_derive_is_recognised() -> None:
    assert ask.parse_line("/derive").kind == "derive"


def test_quit_forms_all_quit() -> None:
    # The contract's one named exception: /q, /quit, /exit (and EOF) all quit.
    for form in ("/q", "/quit", "/exit"):
        assert ask.parse_line(form).kind == "quit", form


# --- drift gates: the GRAMMAR table is enforced, not aspirational ------------ #


def test_every_grammar_example_parses_without_error() -> None:
    for form, _meaning, example in ask.GRAMMAR:
        p = ask.parse_line(example)
        assert p.kind != "error", f"{form}: example {example!r} -> {p.error}"


def test_grammar_text_renders_every_form_and_meaning() -> None:
    text = ask.grammar_text()
    for form, meaning, _example in ask.GRAMMAR:
        assert form in text
        assert meaning in text


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


# --- /derive: fail-open, never crashes the REPL ------------------------------ #


def test_repl_derive_reconnect_lock_exits_gracefully(
    monkeypatch, capsys,  # type: ignore[no-untyped-def]
) -> None:
    """The /derive reconnect can hit a catalogue lock (an extraction started
    mid-derive). The REPL must close with the named error, never a traceback."""
    import builtins
    from types import SimpleNamespace

    import duckdb

    lines = iter(["/recent any invoices?", "/derive"])
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(lines))
    monkeypatch.setattr(ask, "ask_once",
                        lambda *a, **k: [("doc_date_pandoc", "ff" * 32)])
    monkeypatch.setattr(ask, "run_derive", lambda targets: None)

    def locked() -> None:
        raise duckdb.Error("Could not set lock on file: Conflicting lock")

    monkeypatch.setattr(ask, "connect", locked)
    ask.repl(SimpleNamespace(close=lambda: None), k=8)  # returns, never raises

    assert "corpus locked" in capsys.readouterr().out


def test_run_derive_fail_open_on_any_error(
    monkeypatch, capsys,  # type: ignore[no-untyped-def]
) -> None:
    """A derive that raises (non-lock) prints and moves on — the docstring's
    'nothing crashes the REPL' contract — and later targets still run."""
    import pkm.config
    import pkm.derive

    monkeypatch.setattr(pkm.config, "load_config",
                        lambda _: type("Cfg", (), {"root_dir": Path("/x")})())
    calls: list[str] = []

    def boom(_root, _cfg, decl, **_kw):  # type: ignore[no-untyped-def]
        calls.append(decl)
        raise RuntimeError("model offline")

    monkeypatch.setattr(pkm.derive, "derive", boom)
    ask.run_derive([("doc_date_pandoc", "dd" * 32),
                    ("doc_date_docling", "ee" * 32)])

    out = capsys.readouterr().out
    assert calls == ["doc_date_pandoc", "doc_date_docling"]  # second still ran
    assert out.count("derive failed") == 2
