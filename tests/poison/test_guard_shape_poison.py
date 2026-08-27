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
    """Rule 1. Use `tests/_guard_ast.calls(obj, name)` instead: it resolves the call by
    AST, so a name in a comment or a docstring is not a call and cannot satisfy it."""
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


def test_poison_every_fixture_names_the_mutation_that_kills_it() -> None:
    """Rule 2. Every test under tests/poison/ must say, in its docstring, what planted
    violation makes it fail. A fixture nobody has watched fail is decoration, and its
    register row cannot honestly read `resolved`."""
    missing: list[str] = []
    for py in (_TESTS / "poison").rglob("test_*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            # Scoped to `test_poison_*`: the precision controls beside them (a rule must
            # NOT fire on legitimate content) are a different and equally necessary
            # category, and they have no mutation by construction.
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("test_poison_")):
                continue
            doc = (ast.get_docstring(node) or "") + (ast.get_docstring(tree) or "")
            # the docstring must reference a finding id (F<n>) or say what kills it
            if not re.search(r"\bF\d+\b|MUST FAIL|kills it|goes red|is the seed", doc):
                missing.append(f"{py.relative_to(_TESTS).as_posix()}::{node.name}")
    assert not missing, (
        f"poison fixture(s) that do not name what kills them: {missing} — a fixture "
        f"nobody has watched fail proves nothing, and r23's own first oracle control "
        f"passed its own mutation"
    )
