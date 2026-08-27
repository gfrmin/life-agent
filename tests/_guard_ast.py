"""Shared AST helpers for guards that must assert a CALL, not a source substring.

r23's F10 found `assert "withhold_reason" in <file>.read_text()` — a substring a COMMENT
satisfies, while the chain underneath is re-spelled to disagree. That was not one guard but
a CLASS: nine more assertions of the same shape were in the tree. These helpers exist so the
honest form is the easy one.
"""
from __future__ import annotations

import ast
import inspect
from typing import Any


def called_names(obj: Any) -> set[str]:
    """Every function/attribute name CALLED inside ``obj``'s source.

    ``obj`` may be a module, class or function. Resolution is syntactic (an AST walk), which
    is what distinguishes it from a substring match: a name in a comment or a docstring is
    not a call and does not appear here.
    """
    tree = ast.parse(inspect.getsource(obj))
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute):
            out.add(f.attr)
        elif isinstance(f, ast.Name):
            out.add(f.id)
    return out


def calls(obj: Any, name: str) -> bool:
    """True when ``obj``'s source contains a CALL to ``name`` (bare or dotted)."""
    return name in called_names(obj)
