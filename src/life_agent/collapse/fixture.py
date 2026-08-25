"""The decision-equivalence fixture — schema, field classes, and on-disk layout.

The instrument ``docs/module-collapse-design.md`` §7.2 adds: a recorded corpus of
*view → decision* pairs at the pure-function boundary, replayed through old and new paths at
every checkpoint of the module collapse. The design names the directory; this module is the
schema the M0 implementation phase defines.

**Where fixtures live.** ``$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>/`` — out of
tree, beside the eval artefacts (M0-S1). They carry question text and corpus-derived bytes
and therefore may never enter this repository (CLAUDE.md: public, PII-free).

**The field-class rule** (§7.2's signed pre-M0 addition). Every field of the ``/log_decision``
body is declared, once, here:

* :data:`VALUE_COMPARED` — compared by value (floats at :data:`FLOAT_TOL`);
* :data:`RUNTIME_MEASURED` — compared by **presence and type only**, never value, because the
  quantity is measured at run time rather than tabled (a replay that takes longer, or that
  realises a warm price, has not changed a decision).

A field in NEITHER class is a mismatch (``unclassified``), never a silent pass: a field the
collapse adds must be classified at the checkpoint that adds it. A field may move from
measured to value-compared at a checkpoint, **never the other way** (never-silently-weaken,
tranche 1 §9) — a loosening is a design revision the owner signs.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1

# Floats agree to this absolute tolerance (§7.2's stated comparator precision).
FLOAT_TOL = 1e-9

# --- the field-class list (§7.2) ---------------------------------------------------------

#: Compared by value. ``decision.*`` paths are fields of the body's ``decision`` object;
#: ``regime`` and ``policy`` are the two M0 adds (§5.1, §2.3, §3.1).
VALUE_COMPARED: frozenset[str] = frozenset({
    "question",
    "retrieval_keys",
    "decision.effector",
    "decision.credences",
    "decision.candidates",
    "decision.p_none",
    "decision.eu",
    "decision.n_obs",
    "decision.n_indeterminate",
    "decision.n_competing",
    "decision.instrument",
    "decision.run_id",
    "decision.regime",
    "decision.policy",
})

#: Compared by presence and type only — measured at run time, never tabled.
RUNTIME_MEASURED: frozenset[str] = frozenset({
    "decision.latency_s",
    "decision.cost_usd",
})

#: The fixture's own outputs, outside the posted body: the act itself.
OUTPUT_VALUE_COMPARED: frozenset[str] = frozenset({
    "effector", "asserted", "candidates", "credences", "p_none", "eu", "gate",
    # facts about ANY decision, whether or not it reached the poster (§2.3, §3.1)
    "regime", "policy",
})

#: Recorded for audit, never compared — label views (D-4) and provenance. Comparing a render
#: would make a cosmetic string a behaviour change.
OUTPUT_RECORDED_ONLY: frozenset[str] = frozenset({"audit"})

# --- traces ------------------------------------------------------------------------------

#: The recorded traces. ``A-loop`` is the executor path (daemon up); ``A-poster`` is the
#: body one of the two pre-collapse posters builds from a view (Q-O6's asymmetry — the two
#: die into one at M2); ``B-lookup`` / ``B-narrative`` are the in-process families (the
#: terminals-only regime's leaves); ``seam`` is a commit with no engine available (§6.5).
TRACES: frozenset[str] = frozenset({"A-loop", "A-poster", "B-lookup", "B-narrative", "seam"})

#: The terminal types coverage must reach (Q9's condition + the withholding vocabulary).
#: ``report(claims)`` is the narrative terminal, named as the design names it.
TERMINAL_TYPES: tuple[str, ...] = (
    "report", "report_scoped", "hedge", "ask_clarify", "abstain", "miss", "report(claims)",
)

#: The non-terminal classes the M0 brief pre-states. Listed here so :func:`coverage` reports
#: them whether or not any fixture carries one — a class nobody reached must be as visible as
#: a class everybody did.
DECLARED_CLASSES: tuple[str, ...] = (
    "outcome:committed", "outcome:withheld", "outcome:dispersed", "outcome:miss",
    "posterior:two-equal-credences",   # the tie-break kill (§7.5, pre-registered kill 1)
    "posterior:n_obs=0",               # the E-7 replace-branch cluster
    "regime:full", "regime:terminals-only", "regime:unavailable",
    "policy:all-to-date", "policy:frozen-elicitations",
    "gate:executor_down",
)


@dataclass(frozen=True)
class Exchange:
    """One recorded request/response at a tapped seam.

    ``seam`` is ``skin`` (the credence engine's JSON-RPC wire), ``http`` (the bridge/daemon
    wire), ``instrument`` (a cache-missing model call) or ``cache`` (a §18.9 derivation
    read). ``request`` is the canonical request; ``response`` the verbatim reply.
    """

    seam: str
    request: dict[str, Any]
    response: Any


@dataclass(frozen=True)
class Fixture:
    """One recorded view → decision pair.

    ``inputs`` holds §7.2's ranked-over inputs (candidates, observations with their
    covariates, the carried reliability, u_bar, era_split, owner_scoped, applied probes,
    menu, sensors) as recorded — the audit trail for *why* a decision was what it was.
    ``outputs`` holds the committed act and the full ``/log_decision`` body.

    ``expected_change`` is set only where the design INTENDS a difference at a named
    checkpoint: the comparator then asserts the pre-registered direction instead of
    equality (§7.2).
    """

    fixture_id: str
    checkpoint: str
    trace: str
    classes: tuple[str, ...]
    question: str
    question_id: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    wire: tuple[Exchange, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    expected_change: dict[str, Any] | None = None
    format_version: int = FORMAT_VERSION

    def __post_init__(self) -> None:
        if self.trace not in TRACES:
            raise ValueError(f"unknown trace {self.trace!r} (declared: {sorted(TRACES)})")


def to_json(fx: Fixture) -> str:
    payload = asdict(fx)
    payload["classes"] = list(fx.classes)
    payload["wire"] = [asdict(e) for e in fx.wire]
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=1)


def from_json(text: str) -> Fixture:
    obj = json.loads(text)
    obj["classes"] = tuple(obj.get("classes", ()))
    obj["wire"] = tuple(Exchange(**e) for e in obj.get("wire", ()))
    return Fixture(**obj)


def write(directory: Path, fx: Fixture) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{fx.fixture_id}.json"
    path.write_text(to_json(fx), encoding="utf-8")
    return path


def existing_fixtures(directory: Path) -> list[str]:
    """The fixture-set files already in a checkpoint directory, in name order — empty when it
    is safe to record into (R8, M0.5's r03 A6).

    A recording writes one file per fixture and then GLOBS the directory to build its manifest,
    so recording into a directory that already holds fixtures publishes a manifest describing a
    MIXTURE of two runs while presenting as a whole artefact. The shape that produces it is a
    partial failure: an aborted recording leaves its predecessors behind and says nothing.

    ``snapshots/`` is deliberately NOT counted: ``take_snapshot`` re-copies the fold inputs on
    every run, so its presence is not evidence of a stale fixture, and refusing on it would
    refuse every legitimate re-record. ``manifest.json`` IS counted — a run that died between
    publishing its manifest and being merged leaves exactly that, and the next run republishes
    it.
    """
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.glob("*.json"))


def read_all(directory: Path) -> list[Fixture]:
    """Every fixture in the checkpoint directory, in id order. A malformed fixture RAISES —
    a bisection oracle that silently skips a fixture is not an oracle."""
    return [from_json(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.json")) if p.name != "manifest.json"]


def coverage(fixtures: Iterable[Fixture]) -> dict[str, list[str]]:
    """Which declared classes the recorded set reaches, and which it does not — the
    pre-stated coverage condition (§7.2 Q9, the brief's "no fixture class may be silently
    absent"). Returns ``{class: [fixture ids]}`` including EMPTY lists for absent classes,
    so the report can name every hole."""
    fxs = list(fixtures)
    out: dict[str, list[str]] = {}
    for terminal in TERMINAL_TYPES:
        out[f"terminal:{terminal}"] = sorted(
            f.fixture_id for f in fxs if f"terminal:{terminal}" in f.classes)
    for trace in sorted(TRACES):
        out[f"trace:{trace}"] = sorted(f.fixture_id for f in fxs if f.trace == trace)
    for declared in DECLARED_CLASSES:
        out[declared] = sorted(f.fixture_id for f in fxs if declared in f.classes)
    undeclared = {c for f in fxs for c in f.classes if not c.startswith("terminal:")}
    for c in sorted(undeclared):
        out[c] = sorted(f.fixture_id for f in fxs if c in f.classes)
    return out


def manifest(checkpoint: str, fixtures: Iterable[Fixture],
             provenance: Mapping[str, Any]) -> dict[str, Any]:
    """The checkpoint's manifest: what was recorded, from which tree, under which field
    classes. Written beside the fixtures; quoted by the checkpoint's report."""
    fxs = list(fixtures)
    return {
        "format_version": FORMAT_VERSION,
        "checkpoint": checkpoint,
        "n_fixtures": len(fxs),
        "fixture_ids": sorted(f.fixture_id for f in fxs),
        "field_classes": {
            "value_compared": sorted(VALUE_COMPARED),
            "runtime_measured": sorted(RUNTIME_MEASURED),
            "float_tolerance": FLOAT_TOL,
        },
        "coverage": coverage(fxs),
        # derived from the recorded wire, never asserted (the merged_from lesson): the sum
        # of every instrument-seam reply's cost_usd across the set's fixtures
        "spent_usd": round(sum(
            float(x.response.get("cost_usd") or 0.0)
            for f in fxs for x in f.wire
            if x.seam == "instrument" and isinstance(x.response, dict)), 4),
        "provenance": dict(provenance),
    }
