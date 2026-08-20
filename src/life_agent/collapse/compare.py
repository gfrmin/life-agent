"""The comparator (module-collapse-design.md §7.2): identical chosen action AND identical
``/log_decision`` body, field by field, under the declared field classes.

Exit-1-on-any-mismatch is the caller's (``scripts/collapse_replay.py``); this module is pure:
two recorded objects in, a list of :class:`FieldDiff` out.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from life_agent.collapse.fixture import (
    FLOAT_TOL,
    OUTPUT_RECORDED_ONLY,
    OUTPUT_VALUE_COMPARED,
    RUNTIME_MEASURED,
    VALUE_COMPARED,
)


@dataclass(frozen=True)
class FieldDiff:
    """One field on which replay disagreed with the record.

    ``reason``: ``value`` (compared and different) · ``absent`` (recorded, not replayed) ·
    ``unexpected`` (replayed, never recorded) · ``type`` (a runtime-measured field changed
    kind) · ``unclassified`` (a field in neither declared class — it must be classified at
    the checkpoint that adds it, never absorbed silently).
    """

    path: str
    expected: Any
    actual: Any
    reason: str


_MISSING = object()


def _type_name(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "str"
    if isinstance(v, (list, tuple)):
        return "list"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def values_equal(a: Any, b: Any, *, tol: float = FLOAT_TOL) -> bool:
    """Value equality with the comparator's float tolerance, elementwise into lists and
    objects. ``True``/``1`` are NOT equal — a bool is its own kind."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(values_equal(x, y, tol=tol)
                                        for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(values_equal(a[k], b[k], tol=tol) for k in a)
    return bool(a == b)


def _flatten(body: Mapping[str, Any]) -> dict[str, Any]:
    """The body's dotted paths — top level plus the ``decision`` object, which is the only
    nested one the poster's contract defines (server.py:776-841)."""
    flat: dict[str, Any] = {}
    for k, v in body.items():
        if k == "decision" and isinstance(v, Mapping):
            for dk, dv in v.items():
                flat[f"decision.{dk}"] = dv
        else:
            flat[k] = v
    return flat


def compare_body(expected: Mapping[str, Any], actual: Mapping[str, Any], *,
                 prefix: str = "") -> list[FieldDiff]:
    """Field-by-field over the ``/log_decision`` body under the declared classes."""
    exp, act = _flatten(expected), _flatten(actual)
    diffs: list[FieldDiff] = []
    for path in sorted(set(exp) | set(act)):
        e, a = exp.get(path, _MISSING), act.get(path, _MISSING)
        out = f"{prefix}{path}"
        if path not in VALUE_COMPARED and path not in RUNTIME_MEASURED:
            diffs.append(FieldDiff(out, None if e is _MISSING else e,
                                   None if a is _MISSING else a, "unclassified"))
            continue
        if e is _MISSING or a is _MISSING:
            diffs.append(FieldDiff(out, None if e is _MISSING else e,
                                   None if a is _MISSING else a,
                                   "unexpected" if e is _MISSING else "absent"))
            continue
        if path in RUNTIME_MEASURED:
            # measured, not tabled: presence and kind, never value
            if _type_name(e) != _type_name(a):
                diffs.append(FieldDiff(out, e, a, "type"))
            continue
        if not values_equal(e, a):
            diffs.append(FieldDiff(out, e, a, "value"))
    return diffs


def compare_outputs(expected: Mapping[str, Any],
                    actual: Mapping[str, Any]) -> list[FieldDiff]:
    """The fixture's outputs: the committed act, then the posted body (when one exists).

    A fixture whose decision never reaches the poster (a miss, a narrative view, a down
    stack — §6.5) still pins the act and, where one fired, the declared gate.
    """
    diffs: list[FieldDiff] = []
    for path in sorted(set(expected) | set(actual)):
        if path in OUTPUT_RECORDED_ONLY:
            continue
        e, a = expected.get(path, _MISSING), actual.get(path, _MISSING)
        if path == "log_decision":
            eb = None if e is _MISSING else e
            ab = None if a is _MISSING else a
            if eb is None and ab is None:
                continue
            if eb is None or ab is None:
                diffs.append(FieldDiff(path, eb, ab,
                                       "unexpected" if eb is None else "absent"))
                continue
            diffs.extend(compare_body(eb, ab, prefix="log_decision."))
            continue
        if path not in OUTPUT_VALUE_COMPARED:
            diffs.append(FieldDiff(path, None if e is _MISSING else e,
                                   None if a is _MISSING else a, "unclassified"))
            continue
        if e is _MISSING or a is _MISSING:
            diffs.append(FieldDiff(path, None if e is _MISSING else e,
                                   None if a is _MISSING else a,
                                   "unexpected" if e is _MISSING else "absent"))
            continue
        if not values_equal(e, a):
            diffs.append(FieldDiff(path, e, a, "value"))
    return diffs


def render_diffs(fixture_id: str, diffs: list[FieldDiff]) -> str:
    """One line per field — the diff §7.2 requires the comparator to print."""
    if not diffs:
        return f"{fixture_id}: ok"
    lines = [f"{fixture_id}: {len(diffs)} field(s) differ"]
    lines += [f"    {d.path:<44} [{d.reason}] recorded={d.expected!r} replayed={d.actual!r}"
              for d in diffs]
    return "\n".join(lines)
