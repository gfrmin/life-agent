"""Poison fixtures for the guard-shape rules — the CONSEQUENCES of r23's own findings.

r23 recorded six defects in its own fix work and drew no consequence from any of them
beyond prose. A report is a photograph. These fixtures are the film.

Two rules, both machine-checked on every CI run:

1. **A guard may not prove a call with a substring.** F10 was not one guard but a CLASS —
   `assert "<name>(" in inspect.getsource(X)` appeared nine more times after the one the
   adversary reported. A comment satisfies every one of them.
2. **A poison fixture must name the mutation that kills it.** A fixture that has never been
   shown to fail is exactly the decoration the ladder exists to detect, and the first
   version of r23's own oracle control passed its own mutation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TESTS = _ROOT / "tests"

# `assert "<something>(" in inspect.getsource(...)` / `... in <path>.read_text()` — proving
# a call by looking for its spelling in the source text.
# Anchored at the start of a stripped line, so prose QUOTING the pattern (this file, and
# _guard_ast.py's own docstring) is not mistaken for a use of it. Found by running the rule
# against the tree before believing it — r23's own lesson, applied here.
_SUBSTRING_PROOF = re.compile(
    r"^assert\s+[\"'][^\"']*[\"']\s+in\s+(?:inspect\.getsource|\S*\.read_text\(\))")

# This file quotes the pattern it forbids, and the r23 report is prose about it.
_EXEMPT = {"poison/test_guard_shape_poison.py"}


def test_poison_no_guard_proves_a_call_with_a_substring() -> None:
    """Rule 1. MUST FAIL when a guard proves a call by looking for its spelling in the
    source. Use `tests/_guard_ast.calls(obj, name)` instead: it resolves the call by AST, so
    a name in a comment or a docstring is not a call and cannot satisfy it. Killed by
    reintroducing `assert "leader_order(" in inspect.getsource(LK)`."""
    offenders: list[str] = []
    for py in _TESTS.rglob("*.py"):
        rel = py.relative_to(_TESTS).as_posix()
        if rel in _EXEMPT:
            continue
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if _SUBSTRING_PROOF.search(line.strip()):
                offenders.append(f"{rel}:{i}")
    assert not offenders, (
        f"guard(s) proving a call with a source substring: {offenders} — a COMMENT "
        f"satisfies a substring while the chain underneath is re-spelled to disagree "
        f"(r23 F10). Assert the call with _guard_ast.calls(), or assert the behaviour."
    )


# r25 (L8): the rule is a PURE FUNCTION over a parsed module, so it can be mutation-tested
# on synthetic input. As a census over the real tests/ tree it could only be tested by
# mutating the real tree — which is why its previous defect (concatenating the MODULE
# docstring, so every fixture in a file whose header carried a trigger phrase passed
# regardless of its own text) survived undetected.

_MUTATION_PHRASE = re.compile(r"\bF\d+\b|MUST FAIL|kills it|goes red|is the seed")


def fixtures_missing_mutation(source: str, label: str = "") -> list[str]:
    """Every `test_poison_*` in ``source`` whose OWN docstring names no mutation."""
    tree = ast.parse(source)
    out: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name.startswith("test_poison_")):
            continue
        if not _MUTATION_PHRASE.search(ast.get_docstring(node) or ""):
            out.append(f"{label}::{node.name}" if label else node.name)
    return out


def test_poison_the_mutation_rule_reads_the_fixtures_own_docstring() -> None:
    """L8. MUST FAIL if the rule consults anything but the fixture's own docstring. Killed
    by concatenating the module docstring — under that spelling the synthetic case below
    passes, because the module header carries a trigger phrase and the fixture does not."""
    synthetic = (
        '"""A module whose header says: each names the mutation that kills it."""\n'
        "def test_poison_named() -> None:\n"
        '    """MUST FAIL when x. Killed by y."""\n'
        "    pass\n"
        "def test_poison_unnamed() -> None:\n"
        '    """A fixture nobody has watched fail."""\n'
        "    pass\n")
    assert fixtures_missing_mutation(synthetic) == ["test_poison_unnamed"], (
        "the mutation rule accepted a fixture whose own docstring names no kill — it is "
        "reading the module docstring, so the census's universe is the FILE, not the "
        "fixture"
    )


def test_poison_every_fixture_names_the_mutation_that_kills_it() -> None:
    """Rule 2. MUST FAIL when a poison fixture names no kill. Every `test_poison_*` must
    say, in its OWN docstring, what planted violation makes it fail — a fixture nobody has
    watched fail is decoration, and its register row cannot honestly read `resolved`.
    Killed by adding a poison fixture whose docstring names no mutation."""
    missing: list[str] = []
    for py in (_TESTS / "poison").rglob("test_*.py"):
        missing += fixtures_missing_mutation(
            py.read_text(), py.relative_to(_TESTS).as_posix())
    assert not missing, (
        f"poison fixture(s) that do not name what kills them: {missing} — a fixture "
        f"nobody has watched fail proves nothing, and r23's own first oracle control "
        f"passed its own mutation"
    )
