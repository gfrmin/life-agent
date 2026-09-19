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


# --- the pre-registered direction assertions (§7.2's expected-change mechanism) -----------
# A fixture whose ``expected_change.checkpoint`` names a landed checkpoint is compared under
# that checkpoint's registered direction instead of raw equality (r12 DIR-1/DIR-2). Each
# direction is TIGHT: every field it does not name stays under the standing classes, the
# named fields must match exactly, and the change must have HAPPENED — a fixture replaying
# unchanged fails the direction, because the checkpoint claims a move it did not make.

#: DIR-1 (r12): the one poster states the two M0 fields on every posted body.
_M2_APPEAR: dict[str, Any] = {"decision.regime": "full", "decision.policy": "all-to-date"}
#: DIR-1: the never-absent normalisation — an unpriced null becomes 0.0 (design §5.1).
_M2_NULL_TO_NUMBER: frozenset[str] = frozenset({"decision.cost_usd", "decision.latency_s"})


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _directed_m2_poster(expected: Mapping[str, Any],
                        actual: Mapping[str, Any]) -> list[FieldDiff]:
    """DIR-1 as amended (r12 amendment 1) — every fixture whose recorded body came from a
    pre-collapse poster: ``regime``/``policy`` appear at exactly full/all-to-date; the
    accounting keys the reach poster never posted appear at the one defaults (``run_id``
    exactly "answer-brain", ``instrument`` exactly the fixture's own recorded
    ``audit.instrument`` or ""); unpriced ``cost_usd``/``latency_s`` appear as (or go
    null→) numbers; everything else equal. A fixture recorded WITHOUT a body (a miss, a
    route-null narrative view — the loop committed no lookup decision) must replay
    without one: nothing to direct."""
    exp_body, act_body = expected.get("log_decision"), actual.get("log_decision")
    if not isinstance(exp_body, Mapping) or not isinstance(act_body, Mapping):
        return compare_outputs(expected, actual)
    audit = expected.get("audit")
    audit_instrument = (audit.get("instrument") if isinstance(audit, Mapping) else None) or ""
    appear = dict(_M2_APPEAR)
    appear["decision.run_id"] = "answer-brain"
    appear["decision.instrument"] = audit_instrument
    diffs: list[FieldDiff] = []
    for d in compare_body(exp_body, act_body, prefix="log_decision."):
        path = d.path.removeprefix("log_decision.")
        if path in appear and d.reason == "unexpected":
            if not values_equal(d.actual, appear[path]):
                diffs.append(FieldDiff(d.path, appear[path], d.actual, "value"))
            continue
        if path in _M2_NULL_TO_NUMBER and _is_number(d.actual) and (
                (d.reason == "type" and d.expected is None)
                or d.reason == "unexpected"):
            continue
        diffs.append(d)
    raw_dec = act_body.get("decision")
    act_dec: Mapping[str, Any] = raw_dec if isinstance(raw_dec, Mapping) else {}
    for path, want in _M2_APPEAR.items():
        if path.split(".", 1)[1] not in act_dec:
            diffs.append(FieldDiff(f"log_decision.{path}", want, None, "absent"))
    exp_rest = {k: v for k, v in expected.items() if k != "log_decision"}
    act_rest = {k: v for k, v in actual.items() if k != "log_decision"}
    return diffs + compare_outputs(exp_rest, act_rest)


#: DIR-2 (r12): the §6.5 unavailability record's output-level facts.
_M2_SEAM_APPEAR: dict[str, Any] = {"regime": "unavailable", "policy": "all-to-date"}


def _directed_m2_seam(expected: Mapping[str, Any], actual: Mapping[str, Any],
                      question: str) -> list[FieldDiff]:
    """DIR-2 — the seam fixture: the act stays abstain with its gate; the RECORD appears —
    ``regime: unavailable``, empty posterior, zeroed accounting, no decision id to bind."""
    skip = {"log_decision", *_M2_SEAM_APPEAR}
    diffs = compare_outputs({k: v for k, v in expected.items() if k not in skip},
                            {k: v for k, v in actual.items() if k not in skip})
    for key, want in _M2_SEAM_APPEAR.items():
        got = actual.get(key, _MISSING)
        if got is _MISSING:
            diffs.append(FieldDiff(key, want, None, "absent"))
        elif not values_equal(got, want):
            diffs.append(FieldDiff(key, want, got, "value"))
    required = {
        "question": question, "retrieval_keys": [],
        "decision": {"effector": "abstain", "credences": [], "candidates": [],
                     "p_none": 0.0, "eu": 0.0, "n_obs": 0, "n_indeterminate": 0,
                     "n_competing": 0, "instrument": "", "run_id": "answer-brain",
                     "cost_usd": 0.0, "latency_s": 0.0,
                     "regime": "unavailable", "policy": "all-to-date"},
    }
    body = actual.get("log_decision")
    if not isinstance(body, Mapping):
        diffs.append(FieldDiff("log_decision", "the §6.5 unavailability record",
                               body, "absent"))
    else:
        diffs += compare_body(required, body, prefix="log_decision.")
    return diffs


def compare_directed(expected: Mapping[str, Any], actual: Mapping[str, Any], *,
                     checkpoint: str, question: str) -> list[FieldDiff]:
    """Dispatch a fixture's pre-registered direction. An unknown checkpoint is a loud
    failure, never a silent equality fallback — the direction a fixture claims must be one
    the code registers."""
    if checkpoint == "M2":
        return _directed_m2_poster(expected, actual)
    if checkpoint == "M2/M5":
        return _directed_m2_seam(expected, actual, question)
    return [FieldDiff("expected_change.checkpoint", None, checkpoint, "unclassified")]


def _pre_collapse_poster_body(outputs: Mapping[str, Any]) -> bool:
    """The precise signature of a body a pre-collapse poster built (r12 amendment 1): the
    B-traces' bodies are shaped from their ``DecisionEvent``s and always carry ``regime``;
    only the two pre-M2 posters (the reach surface's and the CLI's) omit it."""
    body = outputs.get("log_decision")
    if not isinstance(body, Mapping):
        return False
    decision = body.get("decision")
    return isinstance(decision, Mapping) and "regime" not in decision



#: DIR-M5 (r15): the family leaves DECLARE their decision space — the recorded
#: silently-defaulted ``regime: "full"`` on a B-trace leaf body becomes the declared
#: ``terminals-only`` (the leaf ranks over T by the skin; §2.3); ``defaulted`` empties.
_M5_LEAF_REGIME: dict[str, Any] = {"regime": "terminals-only"}


def _b_trace_leaf_body(outputs: Mapping[str, Any]) -> bool:
    """The precise signature of a pre-M5 leaf-shaped output: the B-traces surface
    ``regime`` at the OUTPUT level (shaped from their ``DecisionEvent``), recorded as
    the pre-declaration default ``"full"``."""
    return outputs.get("regime") == "full"


def _directed_m5_leaf(expected: Mapping[str, Any],
                      actual: Mapping[str, Any]) -> list[FieldDiff]:
    """DIR-M5: ``regime`` moves full→terminals-only at the output level AND inside the
    ``log_decision.decision`` body; ``defaulted`` (when present) empties; everything
    else equal — and the change must have HAPPENED (an unchanged replay fails)."""
    diffs: list[FieldDiff] = []
    for d in compare_outputs(expected, actual):
        leaf = d.path.rsplit(".", 1)[-1]
        if leaf == "regime" and d.expected == "full":
            if d.actual != "terminals-only":
                diffs.append(FieldDiff(d.path, "terminals-only", d.actual, "value"))
            continue
        if leaf == "defaulted" and d.actual in ((), []):
            continue
        diffs.append(d)
    if actual.get("regime") == "full":
        diffs.append(FieldDiff("regime", "terminals-only", "full", "unmoved"))
    return diffs


def compare_fixture(fx: Any, actual: Mapping[str, Any]) -> list[FieldDiff]:
    """The one entry point the replay uses: directed where the fixture carries a
    pre-registered ``expected_change`` — or where its recorded body is a pre-collapse
    poster's (the A-loop capture, amendment 1) — raw equality everywhere else."""
    if fx.expected_change is not None:
        return compare_directed(fx.outputs, actual,
                                checkpoint=str(fx.expected_change.get("checkpoint")),
                                question=fx.question)
    if _pre_collapse_poster_body(fx.outputs):
        return _directed_m2_poster(fx.outputs, actual)
    if _b_trace_leaf_body(fx.outputs):
        return _directed_m5_leaf(fx.outputs, actual)
    return compare_outputs(fx.outputs, actual)
