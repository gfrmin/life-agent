"""Pure line-grammar of the ask REPL (the interaction contract).

Same dependency-free style as tests/test_ask.py: here we pin the ONE line grammar
(identical in REPL and one-shot argv) — nothing silent,
nothing arbitrary.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

# --- the line grammar: plain asks ------------------------------------------- #


def test_plain_question_is_an_ask() -> None:
    p = ask.parse_line("what is my ID?")
    assert p.kind == "ask"
    assert p.question == "what is my ID?"


def test_empty_line_is_empty() -> None:
    assert ask.parse_line("   ").kind == "empty"


# --- unknown commands -------------------------------------------------------- #


def test_unknown_slash_command_is_an_error_naming_the_grammar() -> None:
    # The silent-typo bug: '/sinc …' must never be asked as a literal question.
    p = ask.parse_line("/sinc 2026-01-01 dentist")
    assert p.kind == "error"
    assert "/sinc" in p.error
    assert "/tell FACT" in p.error  # the grammar is named
    assert ask.parse_line("/since 2026-01-01 dentist").kind == "error"  # removed with the scoping


# --- teaching, quitting -------------------------------------------- #


def test_tell_carries_the_fact() -> None:
    p = ask.parse_line("/tell My name is Ada Lovelace")
    assert p.kind == "tell"
    assert p.fact == "My name is Ada Lovelace"


def test_tell_without_a_fact_is_an_error() -> None:
    assert ask.parse_line("/tell").kind == "error"


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
