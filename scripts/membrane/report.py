#!/usr/bin/env python3
"""``scripts/membrane/report.py`` — the membrane shadow's differential + demand report.

Reads ``life_agent.membrane.shadow.MembraneShadow``'s append-only shadow log (kinds
``boot``/``respawn``/``decide``/``gate``/``evidence``/``stats`` — see that module's docstring for
the exact record shapes; this file reads them, never re-derives them) and, optionally, a
fair-fight run directory's ``baseline`` arm outcomes (``life_agent.fairfight.records
.OutcomeVector`` — the SAME executor ``/decide`` loop the shadow mirrors, per
``scripts/fairfight/run_fairfight.py``'s ``path="executor"`` baseline config and
``shadow.boot_snapshot``'s own precedent for this exact run-dir shape). Writes
``report.json`` + ``report.md`` under ``--out-dir``.

**What the log carries about the submit-path counters** (named once, here, rather than
at each call site): the three submit-path counters (``drops``/``skips``/
``submit_errors``) and each form's ``dead_drops`` never write their OWN per-event log
row (shadow.py's own module docstring) — but their running totals ARE periodically
snapshotted into ``kind: "stats"`` rows (every ``shadow._STATS_EVERY`` processed queue
items, plus one final row at ``close()``). This report reads the LAST such row
(:func:`latest_stats_record`) and reports the real counters from it. A log with no
``stats`` row at all (one written before this field existed, or a shadow that never
processed enough items to flush one and was never cleanly closed) has genuinely no way
to recover them — every place this report would otherwise report a bare zero for one of
those counters instead says so explicitly, rather than printing a fabricated 0.

Report structure:

    0. ``global_counters``  — drops/skips/submit_errors, which are PROCESS-GLOBAL totals
                              (one queue, one submit path, every form) and so are reported
                              exactly once, never repeated under each form's heading.
    1. ``per_form_stats``   — ticks, action distribution, raw_internal, respawns, latency,
                              and ``dead_drops`` (the one genuinely per-form counter).
    1b. ``world_policy``    — what each form's DECLARED utility fires at each credence,
                              derived from the u_bar its OWN boot record persisted.
    2. ``differential``     — the real (incumbent) action vs the shadow's would-action,
                              mapped through a NAMED legend, per form; every disagreement
                              enumerated (never only aggregated — the §8.5 discipline) and
                              EU-priced under the form's own boot u_bar (M2 advisory).
    2b. ``gates``           — seam gate pre-emptions (`kind: "gate"`): where the host
                              abstained before any engine saw the question, and what the
                              engine would have done instead (M2 advisory).
    2c. ``enactments``      — live enactments (`kind: "enact"`, M3): ticks where the
                              engine's coarse act WAS the committed act, counted by engine
                              action, daemon->enacted transition, and named degradation.
    3. ``grounded``         — (only with ``--vectors``) the join's own arithmetic, then
                              contingency tables + realized loss per decision, against the
                              fair-fight baseline arm. The two sides speak DIFFERENT id
                              namespaces (mirror ids vs corpus ids) and are bridged
                              explicitly (:class:`Baseline`); an empty join is reported as
                              an empty join, never as a small sample.
    4. ``demand_ledger``    — named limitations, each with whether it actually ``fires`` on
                              this run, its count, and the boundary it demands. Every
                              utility-dependent threshold is DERIVED from the boot-recorded
                              u_bar — never a hard-coded constant (a hard-coded 0.9 is what
                              made this ledger publish a false claim once already).
    5. ``provenance``       — binary sha256 + world digest + forms, from boot records.

Pure functions over record lists; I/O only at ``load_shadow_records``/
``load_baseline_vectors`` (reads) and ``main`` (writes) — mirrors ``scripts/dominance/``'s
own split. No wall-clock field anywhere in the report body: given the same shadow log
and the same (optional) vectors dir, ``build_report`` returns byte-identical output —
the brief's "reproducible from its named inputs".
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: self-import below

from life_agent.core import claude_verdicts as CV
from life_agent.core import config as C
from life_agent.fairfight import records as REC
from life_agent.membrane import shadow as SH
from life_agent.membrane import world as W

# --- loading: fail-open reads (the edge) --------------------------------------------------


def _read_jsonl_fail_open(path: Path) -> list[dict[str, Any]]:
    """Every parseable JSON-object line, file order. A missing file is empty; a
    malformed line is skipped, never raised on — the same fail-open discipline
    ``shadow.boot_snapshot``'s own readers already use for this exact log."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def load_shadow_records(shadow_log: Path) -> list[dict[str, Any]]:
    """Every ``event_type: "membrane-shadow"`` row in the shadow log, file order (the
    canonical arrival/replay order — nothing here re-sorts)."""
    return [
        r for r in _read_jsonl_fail_open(shadow_log) if r.get("event_type") == "membrane-shadow"
    ]


@dataclass(frozen=True)
class Baseline:
    """One fair-fight run's baseline-arm outcomes, RE-KEYED into the shadow's own id
    namespace, plus the arithmetic of that re-keying.

    The two namespaces (named once, here, and bridged in exactly one place —
    ``shadow.warm_question_id_map``): an ``OutcomeVector.question_id`` is the CORPUS id
    (``q-001``); a shadow decide record's ``question_id`` is the MIRROR id
    (``core.decisions.question_id`` — sha256 of the question TEXT). Joining them directly
    yields zero rows ALWAYS, and a zero join then reads as "not enough data yet" — the
    exact "print a number that means unknown" failure this project forbids. So the rows
    are re-keyed by mirror id up front, and ``note`` names it loudly whenever nothing
    could be mapped."""

    by_mirror_id: dict[str, dict[str, Any]]
    n_rows: int          # rows read off the baseline arm's vectors.jsonl
    n_scored: int        # after records.scored (the infra-failure filter)
    id_map_size: int     # corpus->mirror mappings the run's questions file yielded
    n_unmapped: int      # scored rows whose corpus id had no mapping
    note: str = ""


def load_baseline_vectors(run_dir: Path) -> Baseline:
    """One fair-fight run's ``baseline`` arm — the arm this shadow actually mirrors
    (``run_fairfight.py``'s ``ask.answer_via_executor(path="executor")``, the same
    ``/decide`` loop ``core/shadow_mirror.py`` fans out to ``/decide-support``; also the
    exact run-dir shape ``shadow.boot_snapshot`` already reads warm outcomes from) —
    re-keyed onto the shadow's mirror ids (see :class:`Baseline`). Rows are validated
    through ``records.from_json`` (raises loudly on a malformed row — the same discipline
    ``scripts/dominance/run_dominance.py``'s ``_load_arm_vectors`` already uses, never
    silently skewing a downstream rate) and filtered through ``records.scored`` (the one
    canonical infra-failure filter). A missing file yields an empty join population, not
    an error (an optional flag pointing at a run that hasn't produced a baseline arm yet
    is a valid, reportable state)."""
    path = run_dir / "arms" / "baseline" / "vectors.jsonl"
    if not path.exists():
        return Baseline(by_mirror_id={}, n_rows=0, n_scored=0, id_map_size=0, n_unmapped=0,
                        note=f"no baseline arm at {path} — nothing to join against.")
    rows: list[REC.OutcomeVector] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(REC.from_json(json.loads(line)))
    scored = list(REC.scored(rows))
    id_map = SH.warm_question_id_map(run_dir)

    by_mirror_id: dict[str, dict[str, Any]] = {}
    unmapped = 0
    for v in scored:
        mirror_id = id_map.get(v.question_id)
        if mirror_id is None:
            unmapped += 1
            continue
        by_mirror_id[mirror_id] = REC.to_json(v)  # latest row per question wins
    note = ""
    if scored and not by_mirror_id:
        note = (
            f"0 of {len(scored)} scored baseline rows could be mapped into the shadow's id "
            f"namespace — the run's run_meta.json -> questions_path yielded {len(id_map)} "
            f"corpus->mirror mappings. Vector question_ids are CORPUS ids (q-001); shadow "
            f"decide records key on MIRROR ids (sha256(question text)[:16]). Every grounded "
            f"table below is therefore EMPTY BY CONSTRUCTION, not under-powered."
        )
    elif unmapped:
        note = (f"{unmapped} of {len(scored)} scored baseline rows had no corpus->mirror "
                f"mapping (questions file yielded {len(id_map)} ids) and are excluded.")
    return Baseline(by_mirror_id=by_mirror_id, n_rows=len(rows), n_scored=len(scored),
                    id_map_size=len(id_map), n_unmapped=unmapped, note=note)


# --- record slicing helpers ----------------------------------------------------------------


def _of_kind(records: list[dict[str, Any]], kind: str, form: str) -> list[dict[str, Any]]:
    return [r for r in records if r.get("kind") == kind and r.get("form") == form]


def declared_forms(records: list[dict[str, Any]]) -> list[str]:
    """The declared form list, in declared order — read off any boot record's own
    ``forms`` field (every boot record carries the FULL declared list, per
    ``shadow._write_boot_record``). Falls back to the sorted union of every record's
    own ``form`` field when the log has no boot record at all (e.g. a truncated log)."""
    for r in records:
        forms = r.get("forms")
        if r.get("kind") == "boot" and isinstance(forms, list):
            return [str(f) for f in forms]
    return sorted({str(r["form"]) for r in records if isinstance(r.get("form"), str)})


def latest_stats_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The LAST ``kind: "stats"`` row in the log (file order — arrival/write order,
    nothing here re-sorts), or ``None`` if the log has none (an older log that predates
    this field, or a shadow that never processed ``shadow._STATS_EVERY`` items and was
    never cleanly closed). Each row carries ``MembraneShadow.stats()``'s full payload
    verbatim, so the LAST one is simply the most up-to-date snapshot of those counters
    this run ever flushed."""
    stats_rows = [r for r in records if r.get("kind") == "stats"]
    return stats_rows[-1] if stats_rows else None


def _latest_boot_n_source_records(records: list[dict[str, Any]], form: str) -> int | None:
    """``BootSnapshot.n_source_records`` off ``form``'s most recent boot record (a
    respawn re-snapshots, so the LATEST boot — not the first — is the current reading).
    ``None`` for a form with no boot record, or one written before this field existed."""
    boots = _of_kind(records, "boot", form)
    if not boots:
        return None
    n = boots[-1].get("n_source_records")
    return int(n) if isinstance(n, int) else None


def latest_boot_u_bar(records: list[dict[str, Any]], form: str) -> dict[str, float] | None:
    """The REAL utility posterior means ``form``'s most recent boot declared its world
    under (``shadow._write_boot_record``'s ``u_bar`` field) — ``None`` for a form with no
    boot record, or one written before that field existed.

    Everything downstream that needs the world's numbers (the realized-loss table, the
    respond-reachability threshold) reads them from HERE and refuses to proceed without
    them. It used to fall back to ``world.utility_by_action``' declared DEFAULTS, which are not
    what any live shadow ever ran under — the live ``u_wrong`` is around -5.9, not -9.0 —
    so the report scored losses under a table the shadow never used and published a
    reachability claim that was an artifact of a fallback constant."""
    boots = _of_kind(records, "boot", form)
    if not boots:
        return None
    u_bar = boots[-1].get("u_bar")
    if not isinstance(u_bar, dict) or not u_bar:
        return None
    try:
        return {str(k): float(v) for k, v in u_bar.items()}
    except (TypeError, ValueError):
        return None


def latest_boot_warm(records: list[dict[str, Any]], form: str) -> dict[str, Any] | None:
    """``BootSnapshot.warm`` (a ``shadow.WarmJoin``) off ``form``'s most recent boot — the
    warm fair-fight join's own read-vs-joined arithmetic, including its loud note when a
    non-empty vector file joined ZERO rows. ``None`` when the boot ran without a warm
    vectors dir, or predates the field."""
    boots = _of_kind(records, "boot", form)
    if not boots:
        return None
    warm = boots[-1].get("warm")
    return warm if isinstance(warm, dict) else None


def _p1(record: dict[str, Any]) -> float | None:
    readouts = record.get("readouts")
    if not isinstance(readouts, dict):
        return None
    p1 = readouts.get("p1")
    return float(p1) if isinstance(p1, int | float) else None


def _percentile(values: Sequence[float], pct: float) -> float | None:
    """Nearest-rank percentile (no interpolation — deterministic, hand-verifiable)."""
    if not values:
        return None
    s = sorted(values)
    idx = min(len(s) - 1, max(0, math.ceil(pct / 100.0 * len(s)) - 1))
    return s[idx]


# --- 1. per-form stats -----------------------------------------------------------------


_UNPERSISTED_COUNTERS_NOTE = (
    "not observable — this shadow log has no kind:\"stats\" row (it predates that "
    "field, or the shadow never processed shadow._STATS_EVERY items and was never "
    "cleanly closed). drops/skips/submit_errors/dead_drops are periodically snapshotted "
    "into kind:\"stats\" rows by a running shadow (see shadow.py's module docstring); "
    "read them from the live daemon (e.g. the bridge's /ready) instead."
)

# `MembraneShadow.stats()` reports drops/skips/submit_errors as PROCESS-GLOBAL totals (one
# queue, one submit path, shared by every form) and only `dead_drops` per form. Rendering the
# three globals under each form's heading — as this report used to — invites a reader at the
# default `table@1,latent@1` deployment to double-count every one of them. They are reported
# ONCE, in their own section, labelled process-global.
GLOBAL_COUNTER_NAMES: tuple[str, ...] = ("drops", "skips", "submit_errors")


def global_counters(stats_record: dict[str, Any] | None) -> dict[str, Any]:
    """The process-global submit-path counters, ONCE — off the log's last ``kind: "stats"``
    row (``stats()``'s payload, verbatim). ``observable: false`` (never a fabricated 0) when
    the log carries no such row."""
    if stats_record is None:
        return {"observable": False, "note": _UNPERSISTED_COUNTERS_NOTE}
    values = {name: stats_record.get(name) for name in GLOBAL_COUNTER_NAMES}
    if not all(isinstance(v, int) for v in values.values()):
        return {"observable": False, "note": _UNPERSISTED_COUNTERS_NOTE}
    return {
        "observable": True, **values, "as_of_ts": stats_record.get("ts"),
        "queue_depth": stats_record.get("queue_depth"),
        "scope": ("PROCESS-GLOBAL: one queue and one submit path serve every form, so these "
                  "three are totals across all forms — never per-form. Only dead_drops "
                  "(reported per form) is form-scoped."),
    }


def _form_dead_drops(stats_record: dict[str, Any] | None, form: str) -> int | None:
    """``dead_drops`` for ``form`` — the one genuinely per-form counter (items that reached
    the worker while THIS form was dead). ``None`` if unobservable."""
    if stats_record is None:
        return None
    forms = stats_record.get("forms")
    entry = forms.get(form) if isinstance(forms, dict) else None
    if not isinstance(entry, dict):
        return None
    dead_drops = entry.get("dead_drops")
    return dead_drops if isinstance(dead_drops, int) else None


def form_stats(
    records: list[dict[str, Any]], form: str, *, stats_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decides = _of_kind(records, "decide", form)
    evidences = _of_kind(records, "evidence", form)
    respawns = _of_kind(records, "respawn", form)
    n = len(decides)
    counts = Counter(str(r.get("action")) for r in decides)
    action_distribution = {
        name: {"n": counts.get(name, 0), "of": n} for name, _ in W.AFFORDANCES
    }
    raw_internal = sum(1 for r in decides if r.get("raw_internal") is True)
    latencies = [
        float(r["latency_ms"]) for r in decides if isinstance(r.get("latency_ms"), int | float)
    ]
    dead_drops = _form_dead_drops(stats_record, form)
    note = (
        f"dead_drops={dead_drops} (observed at the shadow log's last kind:\"stats\" row, "
        f"ts={stats_record.get('ts') if stats_record else None}); "
        "drops/skips/submit_errors are process-global — see the global counters section"
    ) if dead_drops is not None else _UNPERSISTED_COUNTERS_NOTE
    return {
        "n_decide_ticks": n,
        "n_evidence_ticks": len(evidences),
        "ticks_total": n + len(evidences),
        "action_distribution": action_distribution,
        "raw_internal": {"n": raw_internal, "of": n},
        "respawn_attempts": len(respawns),
        "decide_latency_ms": {
            "p50": _percentile(latencies, 50.0),
            "p95": _percentile(latencies, 95.0),
            "n": len(latencies),
        },
        "dead_drops": dead_drops,
        "dead_drops_note": note,
    }


# --- 2. the differential vs the incumbent -----------------------------------------------

# The executor's effector vocabulary folded onto the world's four affordances — the ONE
# source is life_agent.membrane.world.REAL_TO_MEMBRANE (M3's live mapping reads the same
# dict, so the report and the enactment path cannot drift). A NAMED, printed legend —
# never a silent guess.
REAL_TO_MEMBRANE: dict[str, str] = W.REAL_TO_MEMBRANE

LEGEND_LINES: tuple[str, ...] = (
    "report|report_scoped|hedge -> respond",
    "abstain|miss -> abstain",
    "ask_clarify -> ask",
    "gather -> gather",
)

# hedge is assert-shaped (core/gate.py's ASSERT_ACTIONS = {report, report_scoped, hedge})
# but names candidates rather than committing to one — closer to "respond" than to a
# genuine withhold, but not the same act as a confident report. A declared modelling
# choice, flagged rather than silently folded (brief's own instruction).
HEDGE_MODELLING_CHOICE = (
    'hedge -> respond is a declared modelling choice: hedge is assert-shaped '
    '(core/gate.py\'s ASSERT_ACTIONS = {report, report_scoped, hedge}) but names '
    'candidates rather than committing to one value — closer to "respond" than to a '
    'genuine withhold, but not the same act as a confident report.'
)


def map_real_effector(real_effector: object) -> str | None:
    """``None`` for any effector string outside the declared table — an unrecognised
    real action is counted and named (see :func:`differential`'s
    ``n_unmapped_real_effector``), never silently guessed at."""
    if not isinstance(real_effector, str):
        return None
    return REAL_TO_MEMBRANE.get(real_effector)


def _eu_delta(u_bar: Mapping[str, float] | None, p1: float | None,
              would: object, real_mapped: str) -> float | None:
    """The engine's own pricing of one disagreement (M2 advisory): EU(would) - EU(real),
    both under the form's boot-declared utility at the tick's own p1 — the EU the engine
    believes the incumbent's choice left on the table, in ITS world. ``None`` whenever the
    inputs to that claim are missing (no boot u_bar, no p1 readout, an action outside the
    affordance menu) — unpriceable is named, never guessed."""
    if u_bar is None or p1 is None or not isinstance(would, str):
        return None
    eus = W.eu_by_action(u_bar, p1)
    if would not in eus or real_mapped not in eus:
        return None
    return round(eus[would] - eus[real_mapped], 4)


def differential(records: list[dict[str, Any]], form: str,
                 u_bar: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Real (legend-mapped) vs would (the shadow's own ``action``) over EVERY decide
    tick for ``form`` — not only terminal ticks: every real ``/decide`` call is mirrored
    (Task 6), so every one is a real comparison point. A tick whose ``real_effector``
    falls outside :data:`REAL_TO_MEMBRANE` is excluded from the agreement rate (there is
    no real action to agree or disagree with) but tallied by name in
    ``n_unmapped_real_effector`` — never silently dropped from view.

    With ``u_bar`` (the form's boot-declared posterior), each disagreement additionally
    carries ``eu_delta`` (:func:`_eu_delta`) and ``disagreement_eu_by_class`` aggregates
    them per ``real->would`` class — the M2 advisory ledger's {agree?, EU delta} fields.
    ``priced_n`` counts the rows the sum actually covers; a class whose every row was
    unpriceable reports ``eu_delta_sum: None``, not 0.0."""
    decides = _of_kind(records, "decide", form)
    unmapped: Counter[str] = Counter()
    per_real: dict[str, dict[str, int]] = {}
    disagreements: list[dict[str, Any]] = []
    n_mapped = 0
    n_agree = 0
    for r in decides:
        real_raw = r.get("real_effector")
        mapped = map_real_effector(real_raw)
        if mapped is None:
            unmapped[str(real_raw)] += 1
            continue
        n_mapped += 1
        would = r.get("action")
        bucket = per_real.setdefault(mapped, {"n": 0, "agree": 0})
        bucket["n"] += 1
        if would == mapped:
            n_agree += 1
            bucket["agree"] += 1
        else:
            disagreements.append({
                "question_id": r.get("question_id"), "t": r.get("t"),
                "real": real_raw, "real_mapped": mapped, "would": would,
                "p1": _p1(r), "summary": r.get("summary"),
                "eu_delta": _eu_delta(u_bar, _p1(r), would, mapped),
            })
    agreement_per_real_action = {
        action: {
            "n": v["n"], "agree": v["agree"],
            "rate": round(v["agree"] / v["n"], 4) if v["n"] else None,
        }
        for action, v in sorted(per_real.items())
    }
    by_class: dict[str, dict[str, Any]] = {}
    for d in disagreements:
        cls = f"{d['real_mapped']}->{d['would']}"
        cell = by_class.setdefault(cls, {"n": 0, "priced_n": 0, "eu_delta_sum": None})
        cell["n"] += 1
        if d["eu_delta"] is not None:
            cell["priced_n"] += 1
            cell["eu_delta_sum"] = round((cell["eu_delta_sum"] or 0.0) + d["eu_delta"], 4)
    return {
        "n_mapped": n_mapped,
        "n_unmapped_real_effector": dict(sorted(unmapped.items())),
        "agreement_overall": {
            "n": n_mapped, "agree": n_agree,
            "rate": round(n_agree / n_mapped, 4) if n_mapped else None,
        },
        "agreement_per_real_action": agreement_per_real_action,
        "disagreements": disagreements,
        "disagreement_eu_by_class": dict(sorted(by_class.items())),
    }


GATE_NOTE = (
    "Seam gate pre-emptions (M2 advisory): the host committed abstain by declared policy "
    "BEFORE any engine saw the question (register §11 i-4/i-5 — the engine may abstain, "
    "the host may not refuse). Each row is what the engine, consulted under the faithful "
    "empty-evidence context, would have done instead. A `would` other than abstain is "
    "M3's preview: coarse-menu-live hands exactly this tick to the engine."
)


def gate_advisory(records: list[dict[str, Any]], form: str) -> dict[str, Any]:
    """`kind: "gate"` rows for ``form``, reduced per gate name x the engine's would-action
    — the M2 coverage the decide differential structurally cannot have (a gated question
    never reaches `/decide`, so no decide tick exists to disagree with)."""
    gates = _of_kind(records, "gate", form)
    by_gate: dict[str, dict[str, Any]] = {}
    for r in gates:
        cell = by_gate.setdefault(str(r.get("gate")), {"n": 0, "would": Counter()})
        cell["n"] += 1
        cell["would"][str(r.get("action"))] += 1
    return {
        "n": len(gates),
        "by_gate": {g: {"n": c["n"], "would": dict(sorted(c["would"].items()))}
                    for g, c in sorted(by_gate.items())},
        "note": GATE_NOTE,
    }


ENACT_NOTE = (
    "Live enactments (kind: enact) are M3 ticks where the ENGINE's coarse act WAS the "
    "committed act (flag LIFE_AGENT_MEMBRANE_LIVE=1): action = the engine's affordance, "
    "real_effector = the effector the host enacted under the named transitional rules "
    "(respond -> host-MAP value; gather -> cheapest unapplied voi transform, exhausted "
    "-> restricted argmax at the engine's own p1), daemon_effector = what credence "
    "would have done. They are enactments, not would-vs-did shadow ticks, so they never "
    "enter the differential."
)


def enactment(records: list[dict[str, Any]], form: str) -> dict[str, Any]:
    """The M3 live-enactment ledger for one form: every `kind: "enact"` row counted by
    the engine's coarse action, by the full daemon->enacted transition, and by named
    degradation. Empty (n=0) whenever the flag has never been on — the section then says
    so rather than vanishing."""
    rows = _of_kind(records, "enact", form)
    by_action: Counter[str] = Counter(str(r.get("action")) for r in rows)
    by_transition: Counter[str] = Counter(
        f"{r.get('daemon_effector')}->{r.get('real_effector')}" for r in rows)
    degraded: Counter[str] = Counter(
        str(r["degraded"]) for r in rows if r.get("degraded") is not None)
    return {"n": len(rows), "by_engine_action": dict(by_action),
            "by_transition": dict(by_transition), "degraded": dict(degraded),
            "note": ENACT_NOTE}


# --- 2b. the enact realised-EU detector (contain-live-over-assertion plan, P1) ------------
#
# `enactment()` above only COUNTS transitions. Under the live flag the engine's coarse act
# is the committed act, so a `report` the daemon would have withheld can be a confident-wrong
# and nothing on the ledger says so. This detector prices the TERMINAL enact per question
# against a per-question correctness label (the Claude verdict channel) using the world's own
# `utility_by_action`, so realised loss is visible on the ledger rather than in a plan. The
# abstain baseline earns 0, so realised EU IS the delta vs having withheld — a negative total
# is a live path that lost EU against simply abstaining.

ENACT_EU_NOTE = (
    "realised utility of the TERMINAL enacted act per question, priced at the Claude-verdict "
    "correctness label via world.utility_by_action (report/report_scoped/hedge -> respond; "
    "abstain -> 0). The abstain baseline earns 0, so realised_eu_total is the delta vs having "
    "withheld: negative means the live path lost EU against abstaining. over_assertion counts "
    "the wrong asserts the daemon would have withheld (daemon withheld, engine asserted, y=0) "
    "— the confident-wrongs M3 introduces. Owner reactions on reports are a future label "
    "source; v1 uses the purpose-built Claude verdict (the 'asserting the leader is correct' "
    "bit) only."
)


def load_correctness_labels(claude_verdicts_path: Path) -> dict[str, int]:
    """``question_id -> correct bit`` from the Claude verdict channel, latest verdict per
    question (file order = replay order). Missing/unreadable file -> ``{}`` (fail-open, the
    edge convention): the detector then reports 0 labelled rather than raising."""
    labels: dict[str, int] = {}
    try:
        events = CV.read(claude_verdicts_path)
    except Exception:
        return {}
    for e in events:
        labels[e.question_id] = CV.y(e)
    return labels


def realised_utility(
    u_bar: Mapping[str, float], effector: object, y: int,
) -> float | None:
    """Realised utility of a committed ``effector`` at outcome ``y`` in {0,1}, read from the
    world's ONE utility source (:func:`life_agent.membrane.world.utility_by_action`) so it
    cannot drift from the engine's own pricing. ``None`` for an effector outside the declared
    map (:func:`map_real_effector`) — an unrecognised committed act is named, never guessed."""
    aff = map_real_effector(effector)
    if aff is None:
        return None
    u0, u1 = W.utility_by_action(u_bar)[aff]
    return u1 if y else u0


def terminal_enact_per_question(
    records: list[dict[str, Any]], form: str,
) -> dict[str, dict[str, Any]]:
    """The LAST ``kind: "enact"`` row per ``question_id`` for ``form``, file order — the
    terminal commit of a multi-consult episode (the same last-occurrence rule
    :func:`terminal_decide_per_question` uses for decide ticks)."""
    out: dict[str, dict[str, Any]] = {}
    for r in _of_kind(records, "enact", form):
        qid = r.get("question_id")
        if isinstance(qid, str):
            out[qid] = r
    return out


def enact_realised_eu(
    records: list[dict[str, Any]], form: str,
    labels: Mapping[str, int], u_bar: Mapping[str, float] | None,
) -> dict[str, Any]:
    """Price the terminal enact stream for ``form`` against the correctness ``labels``.

    Refuses to derive without a ``u_bar`` (an old boot that never persisted the posterior —
    the same discipline :func:`differential`/:func:`realized_loss` keep): reports the counts
    and a note, no EU. Otherwise returns realised EU vs the abstain baseline (0), the
    correct/wrong assert split, and the ``over_assertion`` cell (daemon withheld, engine
    asserted, outcome wrong)."""
    terminal = terminal_enact_per_question(records, form)
    n_terminal = len(terminal)
    labelled = {qid: r for qid, r in terminal.items() if qid in labels}
    if u_bar is None:
        return {"n_terminal": n_terminal, "n_labelled": len(labelled),
                "note": "no u_bar on the boot record; realised EU not derived. " + ENACT_EU_NOTE}

    realised_total = 0.0
    n_priced = correct_asserts = wrong_asserts = 0
    over_n = 0
    over_cost = 0.0
    for qid, r in labelled.items():
        y = int(labels[qid])
        real_aff = map_real_effector(r.get("real_effector"))
        util = realised_utility(u_bar, r.get("real_effector"), y)
        if real_aff is None or util is None:
            continue  # a terminal effector outside the map — counted via n_labelled - n_priced
        n_priced += 1
        realised_total += util
        if real_aff == "respond":
            if y:
                correct_asserts += 1
            else:
                wrong_asserts += 1
            daemon_aff = map_real_effector(r.get("daemon_effector"))
            if daemon_aff is not None and daemon_aff != "respond" and y == 0:
                over_n += 1
                over_cost += util
    return {
        "n_terminal": n_terminal,
        "n_labelled": len(labelled),
        "n_priced": n_priced,
        "realised_eu_total": realised_total,
        "realised_eu_per_q": (realised_total / n_priced) if n_priced else 0.0,
        "abstain_baseline_eu": 0.0,
        "eu_vs_abstain": realised_total,
        "asserts": {"correct": correct_asserts, "wrong": wrong_asserts},
        "over_assertion": {"n": over_n, "cost": over_cost},
        "note": ENACT_EU_NOTE,
    }


# --- 3. grounded joins (only with --vectors) --------------------------------------------


def terminal_decide_per_question(
    records: list[dict[str, Any]], form: str,
) -> dict[str, dict[str, Any]]:
    """The LAST decide record per ``question_id`` for ``form``, file order. A question
    with several gather rounds has several decide records for the same form; only its
    most recent one represents the incumbent's FINAL action on that question — the one
    comparable against a single grounded outcome. File order is arrival order (the
    worker drains one queue item at a time), so "last occurrence" is well-defined."""
    out: dict[str, dict[str, Any]] = {}
    for r in _of_kind(records, "decide", form):
        qid = r.get("question_id")
        if isinstance(qid, str):
            out[qid] = r
    return out


_MISS_CAUSE = "retrieval_miss"
MISS_DEFINITION_NOTE = (
    'bucket == "WRONGLY_WITHHELD" and cause == "retrieval_miss" — the narrowest reading '
    'of "a miss growing recall breadth could fix" (scripts/triage_grading.py\'s own '
    'vocabulary): extraction_miss/pooling_loss are excluded, since those are lost at a '
    'LATER pipeline stage (the extract/decide step) that widening retrieval cannot reach.'
)


def _joined_rows(
    terminal: Mapping[str, dict[str, Any]], vectors: Mapping[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Both sides key on the MIRROR id (``core.decisions.question_id``): the shadow's decide
    records natively, the baseline vectors after :func:`load_baseline_vectors` re-keys them
    out of the corpus-id namespace. Joining the raw namespaces yields zero rows always —
    see :class:`Baseline`."""
    return [(terminal[qid], vectors[qid]) for qid in terminal if qid in vectors]


def join_diagnostics(
    terminal: Mapping[str, dict[str, Any]], baseline: Baseline,
) -> dict[str, Any]:
    """Why the grounded tables have the population they have — and, when that population is
    EMPTY, whether that means "no overlap yet" or "the join is broken". A zero join is
    stated as a zero join, never left to be read off a table of zeros or (worse) narrated
    as a small sample by :func:`n_min_honesty`."""
    n_joined = len(_joined_rows(terminal, baseline.by_mirror_id))
    note = baseline.note
    if not note and terminal and baseline.by_mirror_id and n_joined == 0:
        note = (
            f"0 of {len(baseline.by_mirror_id)} mapped baseline rows joined against "
            f"{len(terminal)} shadow-observed questions — both sides are in the mirror-id "
            "namespace, so this is a DISJOINT CORPUS (the shadow never saw the questions "
            "this run graded), not a broken join and not a small sample."
        )
    return {
        "n_shadow_questions": len(terminal),
        "baseline_rows_read": baseline.n_rows,
        "baseline_rows_scored": baseline.n_scored,
        "corpus_to_mirror_id_map_size": baseline.id_map_size,
        "baseline_rows_unmapped": baseline.n_unmapped,
        "baseline_rows_mapped": len(baseline.by_mirror_id),
        "n_joined": n_joined,
        "note": note or (f"{n_joined} of {len(baseline.by_mirror_id)} mapped baseline rows "
                         "joined to a shadow-observed question."),
    }


def contingency_tables(
    terminal: Mapping[str, dict[str, Any]], vectors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    joined = _joined_rows(terminal, vectors)

    def _table(
        would: Callable[[dict[str, Any]], bool], actual: Callable[[dict[str, Any]], bool],
    ) -> dict[str, int]:
        tt = sum(1 for r, v in joined if would(r) and actual(v))
        tf = sum(1 for r, v in joined if would(r) and not actual(v))
        ft = sum(1 for r, v in joined if not would(r) and actual(v))
        ff = sum(1 for r, v in joined if not would(r) and not actual(v))
        return {
            "would_and_actual": tt, "would_and_not_actual": tf,
            "not_would_and_actual": ft, "not_would_and_not_actual": ff, "n": len(joined),
        }

    return {
        "n_joined": len(joined),
        "would_abstain_x_actual_wrong": _table(
            lambda r: r.get("action") == "abstain",
            lambda v: v.get("bucket") == "CONFIDENT_WRONG",
        ),
        "would_gather_x_actual_miss": _table(
            lambda r: r.get("action") == "gather",
            lambda v: v.get("bucket") == "WRONGLY_WITHHELD" and v.get("cause") == _MISS_CAUSE,
        ),
        "miss_definition": MISS_DEFINITION_NOTE,
    }


DECISIVE_DEFINITION_NOTE = (
    "vector.asserted is True (mirrors shadow.boot_snapshot's own warm-outcome-replay "
    "convention: y is grounded only where the baseline arm actually asserted, "
    "y = 1 if asserted_correct else 0 — never imputed for a withheld question, since "
    "there is no fact-of-the-matter about what a withheld question's assertion "
    "would have been)."
)


def utility_table_by_action(u_bar: Mapping[str, float]) -> dict[str, list[float]]:
    """``{action: [u(y=0), u(y=1)]}`` for a GIVEN utility posterior, off
    ``world.utility_by_action`` (the world's own reading of its own table — never a second
    copy of the numbers here).

    ``u_bar`` is REQUIRED. It used to default to the world's fallback table (u_wrong=-9.0),
    which no live shadow has ever decided under — scoring a realized loss under it
    overstates every wrong assert by ~50% against the real posterior (u_wrong ≈ -5.9).
    Callers pass the u_bar the boot record persisted, or do not score at all."""
    return {a: [u0, u1] for a, (u0, u1) in W.utility_by_action(u_bar).items()}


UNSCORABLE_NO_U_BAR = (
    "NOT SCORED — this form's boot record carries no u_bar (a log written before the shadow "
    "persisted it). Realized loss is only meaningful under the utility the shadow actually "
    "decided under; scoring it under world.utility_by_action's fallback defaults (u_wrong=-9.0) "
    "would report a loss no live run ever incurred. Re-run the shadow to get a boot record "
    "with u_bar, then re-run this report."
)


def realized_loss(
    terminal: Mapping[str, dict[str, Any]], vectors: Mapping[str, dict[str, Any]],
    *, u_bar: Mapping[str, float] | None, boot_world_digest: str | None = None,
) -> dict[str, Any]:
    """Realized loss per decision — ``-table[action][y]`` — for BOTH the incumbent's real
    action and the shadow's would-action, on the DECISIVE joined population (see
    :data:`DECISIVE_DEFINITION_NOTE`), scored under ``u_bar`` — which must be the utility
    posterior that form's boot record actually recorded (:func:`latest_boot_u_bar`).

    ``u_bar=None`` REFUSES to score (:data:`UNSCORABLE_NO_U_BAR`) rather than falling back
    to defaults: an unscored row is a known unknown; a row scored under a table the shadow
    never used is a fabricated number wearing a real one's clothes."""
    joined = _joined_rows(terminal, vectors)
    decisive = [(r, v) for r, v in joined if v.get("asserted") is True]
    if u_bar is None:
        return {
            "scored": False, "reason": UNSCORABLE_NO_U_BAR,
            "n_joined": len(joined), "n_decisive": len(decisive),
            "boot_world_digest": boot_world_digest,
        }
    table = utility_table_by_action(u_bar)

    real_losses: list[float] = []
    would_losses: list[float] = []
    n_real_unmapped = 0
    n_would_unrecognized = 0
    timestamps: list[float] = []
    for r, v in decisive:
        y = 1 if v.get("asserted_correct") else 0
        real_mapped = map_real_effector(r.get("real_effector"))
        if real_mapped is not None and real_mapped in table:
            real_losses.append(-table[real_mapped][y])
        else:
            n_real_unmapped += 1
        would = r.get("action")
        if isinstance(would, str) and would in table:
            would_losses.append(-table[would][y])
        else:
            n_would_unrecognized += 1
        ts = r.get("ts")
        if isinstance(ts, int | float):
            timestamps.append(float(ts))

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    window = None
    if timestamps:
        window = {
            "from": datetime.fromtimestamp(min(timestamps), tz=UTC).isoformat(),
            "to": datetime.fromtimestamp(max(timestamps), tz=UTC).isoformat(),
        }

    return {
        "scored": True,
        "n_joined": len(joined), "n_decisive": len(decisive),
        "n_real_unmapped_excluded": n_real_unmapped,
        "n_would_unrecognized_excluded": n_would_unrecognized,
        "window": window,
        "real_policy": {"mean_loss": _mean(real_losses), "n": len(real_losses)},
        "would_policy": {"mean_loss": _mean(would_losses), "n": len(would_losses)},
        "utility_table_used": table,
        "u_bar_used": dict(u_bar),
        "scored_under_boot_u_bar": True,
        "decisive_definition": DECISIVE_DEFINITION_NOTE,
        "boot_world_digest": boot_world_digest,
    }


# --- n_min honesty: the credence-governor's registered exit-from-shadow bar ------------

# A SIBLING project's (credence-governor) own registered bar for ITS OWN membrane
# shadow (docs/governance-roadmap.md + docs/rd14-registration-draft.md, R-D14,
# author-signed 2026-07-11: exit-from-shadow bar_waste=0.05%, n_min=1000, rolling 30
# days). life-agent has not registered a bar of its own; this is cited as the only
# registered n_min precedent in this ecosystem, not a life-agent-binding threshold.
GOVERNOR_N_MIN = 1000
GOVERNOR_N_MIN_WINDOW = "rolling 30 days"
GOVERNOR_N_MIN_SOURCE = (
    "credence-governor docs/governance-roadmap.md + docs/rd14-registration-draft.md "
    "(R-D14, author-signed 2026-07-11): exit-from-shadow bar_waste=0.05%, n_min=1000, "
    "rolling 30 days. A sibling project's registered bar for its OWN membrane shadow — "
    "cited as the only registered n_min precedent in this ecosystem; life-agent has not "
    "registered a bar of its own."
)


def n_min_honesty(n: int) -> dict[str, Any]:
    clears = n >= GOVERNOR_N_MIN
    if clears:
        note = f"n={n} clears the registered n_min={GOVERNOR_N_MIN}."
    elif n == 0:
        note = (
            "n=0 — NOTHING joined. This is an EMPTY population, not an under-powered one: "
            "read the join diagnostics above before reading it as 'not enough data yet'. "
            f"(The registered n_min={GOVERNOR_N_MIN} is not the reason there is no reading.)"
        )
    else:
        note = (f"n={n} is BELOW the registered n_min={GOVERNOR_N_MIN} — directional only, "
                "not a registered reading.")
    return {
        "n": n, "n_min": GOVERNOR_N_MIN, "window": GOVERNOR_N_MIN_WINDOW,
        "clears": clears, "source": GOVERNOR_N_MIN_SOURCE, "note": note,
    }


# --- 4. the demand ledger ----------------------------------------------------------------

# The FROZEN ENGINE's own attainable credence ceiling — a property of the binary, not of any
# utility: its internal grid (host-governor/WireU.hs's `ubarGridU`, the thetaPoints-shaped
# linear grid) tops out at 0.9, and 40 consecutive y=1 verdicts on one fixed feature context
# asymptote p1 at 0.8918 without ever reaching it (tests/test_membrane_live.py, live against
# the real binary). This is what a utility-derived respond threshold gets compared AGAINST.
ENGINE_P1_CEILING = 0.9
ENGINE_P1_OBSERVED_ASYMPTOTE = 0.8918
_P1_CEILING_EPS = 1e-9


def _respond_reachability(records: list[dict[str, Any]], form: str) -> dict[str, Any]:
    """Can ``respond`` fire at all, for this form, under the utility its boot ACTUALLY
    declared? Every number here is derived — none is a constant.

    Two thresholds, because they answer two different questions and only one of them binds:

    * ``threshold_vs_abstain`` = ``(u_abstain - u_wrong)/(u_correct - u_wrong)`` — the
      classic "is asserting better than saying nothing" bar. At the world's fallback
      u_wrong=-9.0 that is 0.9000, which is exactly the engine's ceiling — the coincidence
      that made "respond is unreachable" look like a property of the system when it was a
      property of a default constant. At the live posterior (u_wrong ≈ -5.9) it is ≈0.856,
      which the engine's own asymptote (0.8918) CLEARS.
    * ``threshold_whole_menu`` (:func:`world.respond_threshold`) — the bar that actually
      binds, because the engine argmaxes over the WHOLE menu: respond must also outbid
      ``gather``/``ask``, which are priced as myopic perfect information (world.utility_by_action'
      declared bake-in). ``binding_competitor`` names which row sets it.

    ``fires`` is True only when the binding threshold genuinely exceeds what the engine can
    attain — and it is corroborated, never contradicted, by the observed ticks (a form that
    was actually SEEN to respond is reported as reachable whatever the arithmetic says)."""
    decides = _of_kind(records, "decide", form)
    p1s = [p1 for r in decides if (p1 := _p1(r)) is not None]
    n_respond = sum(1 for r in decides if r.get("action") == "respond")
    max_p1 = max(p1s) if p1s else None
    u_bar = latest_boot_u_bar(records, form)
    out: dict[str, Any] = {
        "n_decide_ticks": len(decides),
        "n_respond_chosen": n_respond,
        "max_p1_observed": max_p1,
        "engine_p1_ceiling": ENGINE_P1_CEILING,
        "u_bar_source": "boot record" if u_bar is not None else None,
    }
    if u_bar is None:
        out["fires"] = None
        out["note"] = (
            "no u_bar in this form's boot record — the respond threshold is a FUNCTION of "
            "the utility posterior and cannot be derived without it. Not asserted either way."
        )
        return out

    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    vs_abstain = (u_abstain - u_wrong) / (u_correct - u_wrong)
    whole_menu = W.respond_threshold(u_bar)
    eus_at_ceiling = W.eu_by_action(u_bar, ENGINE_P1_CEILING)
    competitor = max(
        (a for a in eus_at_ceiling if a != "respond"), key=lambda a: eus_at_ceiling[a],
    )
    # ticks where the engine's credence was as high as it goes and respond STILL lost —
    # the empirical corroboration (a tick that DID respond is excluded by construction).
    maxed_out = sum(
        1 for r in decides
        if (p1 := _p1(r)) is not None and p1 >= ENGINE_P1_CEILING - _P1_CEILING_EPS
        and r.get("action") != "respond"
    )
    reachable = (
        n_respond > 0
        or (whole_menu is not None and whole_menu < ENGINE_P1_CEILING - _P1_CEILING_EPS)
    )
    out.update({
        "threshold_vs_abstain": round(vs_abstain, 6),
        "threshold_whole_menu": round(whole_menu, 6) if whole_menu is not None else None,
        "binding_competitor": competitor,
        "argmax_at_engine_ceiling": W.argmax_action(u_bar, ENGINE_P1_CEILING),
        "eu_at_engine_ceiling": {a: round(v, 6) for a, v in eus_at_ceiling.items()},
        "n_ticks_at_ceiling_without_responding": maxed_out,
        "fires": not reachable,
    })
    return out


def demand_ledger(records: list[dict[str, Any]], forms: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    total_ticks = sum(len(_of_kind(records, "decide", f)) for f in forms)

    # V/R: is respond reachable at all, under the utility each form actually booted with?
    per_form_respond = {f: _respond_reachability(records, f) for f in forms}
    firing = [f for f, e in per_form_respond.items() if e.get("fires") is True]
    unknown = [f for f, e in per_form_respond.items() if e.get("fires") is None]
    reachable = [f for f, e in per_form_respond.items() if e.get("fires") is False]
    if firing:
        note = (
            f"FIRES for {firing}: respond cannot win the argmax at any credence the frozen "
            f"engine can attain (its grid ceilings at p1={ENGINE_P1_CEILING}; 40 y=1 verdicts "
            f"asymptote at {ENGINE_P1_OBSERVED_ASYMPTOTE}, live-verified). The binding bar is "
            "threshold_whole_menu, NOT threshold_vs_abstain — the engine argmaxes over the "
            "whole menu, so respond must outbid gather/ask, which world.utility_by_action prices "
            "as myopic perfect information (a DECLARED overvaluation of information; see the "
            "register, item 5). Read the two thresholds together: where threshold_vs_abstain "
            "is cleared but threshold_whole_menu is not, the demand is on OUR OWN information "
            "pricing as much as on the engine's refine lattice, and it is honest to say so."
        )
    elif reachable and not unknown:
        note = (
            f"DOES NOT FIRE: respond is REACHABLE for {reachable} under the utility that form "
            f"actually booted with — its whole-menu threshold sits below the engine's "
            f"attainable p1. The Boundary V/R demand is NOT evidenced by this run. (It fired "
            "historically only under the world's fallback u_wrong=-9.0, which no live shadow "
            "ever ran under.)"
        )
    else:
        note = (
            f"NOT DETERMINED for {unknown}: no boot-record u_bar, so the threshold — a "
            "function of the utility posterior, not a constant — cannot be derived. No claim "
            "is made either way."
        )
    entries.append({
        "name": "respond_unreachable_p1_ceiling",
        "boundary_demanded": "proplang Boundary V/R (the refine lattice)",
        "fires": bool(firing),
        "count": sum(e.get("n_ticks_at_ceiling_without_responding", 0) or 0
                     for e in per_form_respond.values()),
        "of": total_ticks,
        "per_form": per_form_respond,
        "note": note,
    })

    # ask can never fire while the interrupt cost dwarfs the gather cost — a life-agent-side
    # consequence of WHERE the two exchange rates are sourced, surfaced rather than buried.
    ask_per_form: dict[str, Any] = {}
    for f in forms:
        u_bar = latest_boot_u_bar(records, f)
        if u_bar is None:
            ask_per_form[f] = {"dominated": None, "reason": "no boot-record u_bar"}
            continue
        pairs = W.utility_by_action(u_bar)
        (g0, g1), (a0, a1) = pairs["gather"], pairs["ask"]
        dominated = g0 >= a0 and g1 >= a1
        ask_per_form[f] = {
            "dominated": dominated,
            "q_lambda_int": round(abs(float(u_bar.get("lambda_int", 0.0))), 6),
            "g_kappa_att": round(abs(float(u_bar.get("kappa_att", 0.0))), 6),
            "n_ask_chosen": sum(
                1 for r in _of_kind(records, "decide", f) if r.get("action") == "ask"),
        }
    entries.append({
        "name": "ask_dominated_by_gather",
        "boundary_demanded": ("none on the engine side — a life-agent utility-SOURCING flag "
                              "(register item 6): a dedicated interrupt/effort latent, rather "
                              "than repurposing lambda_int/kappa_att"),
        "fires": any(v.get("dominated") is True for v in ask_per_form.values()),
        "count": sum(v.get("n_ask_chosen", 0) or 0 for v in ask_per_form.values()),
        "of": total_ticks,
        "per_form": ask_per_form,
        "note": (
            "gather and ask carry the SAME payoff shape (both priced as myopic perfect "
            "information) and differ only by their cost, so whenever q=|lambda_int| >= "
            "g=|kappa_att| the gather row dominates the ask row POINTWISE and ask can never "
            "win at any p1 — no credence, no evidence, no boundary changes that. At the live "
            "posterior q~1.0 (an interrupt costs about as much as a correct answer is worth) "
            "against g~0.03, so ask is dead by ~30x. count = ticks that nonetheless chose ask "
            "(expected: 0)."
        ),
    })

    # latent@1 action-degeneracy: the said payload can't express a stake-bearing sentence.
    if "latent@1" in forms:
        decides = _of_kind(records, "decide", "latent@1")
        n_insensitive = sum(
            1 for r in decides if (r.get("readouts") or {}).get("sensitivity") is False
        )
        distinct_actions = sorted({str(r.get("action")) for r in decides if r.get("action")})
        entries.append({
            "name": "latent_action_degenerate",
            "boundary_demanded": "pSaid growth (Phase-3 demand)",
            "fires": n_insensitive > 0,
            "count": n_insensitive, "of": len(decides),
            "distinct_actions_observed": distinct_actions,
            "note": (
                '"sensitivity": false ticks on latent@1 — the said payload ["var", 1] '
                "cannot express a stake-bearing sentence, so the engine reports the "
                "tick as action-insensitive. distinct_actions_observed near-singleton "
                "corroborates constant-action degeneracy."
            ),
        })
    else:
        entries.append({
            "name": "latent_action_degenerate",
            "boundary_demanded": "pSaid growth (Phase-3 demand)",
            "fires": False,
            "count": 0, "of": 0,
            "note": 'form "latent@1" was not run in this log — nothing to measure.',
        })

    # K-ary candidate sets inexpressible on the binary evidence wire.
    canonical_form = forms[0] if forms else None
    if canonical_form is not None:
        decides = _of_kind(records, "decide", canonical_form)
        n_kary = sum(
            1 for r in decides
            if isinstance(r.get("summary"), dict)
            and int(r["summary"].get("n_candidates") or 0) >= 2
        )
        entries.append({
            "name": "kary_candidates_inexpressible",
            "boundary_demanded": "increment A (options-as-data)",
            "fires": n_kary > 0,
            "count": n_kary, "of": len(decides),
            "note": (
                f'ticks with summary.n_candidates >= 2, counted on form '
                f'"{canonical_form}" only — the DecideSummary is computed once per '
                "live tick and shared verbatim across every form (shadow.py's "
                "submit_decide), so counting on more than one form would double-count "
                "the same real ticks."
            ),
        })
    else:
        entries.append({
            "name": "kary_candidates_inexpressible",
            "boundary_demanded": "increment A (options-as-data)",
            "fires": False,
            "count": 0, "of": 0, "note": "no decide ticks in this log.",
        })

    # Cold-start feature-insensitivity.
    per_form_cold: dict[str, dict[str, int]] = {}
    total_cold = 0
    per_form_source_records: dict[str, int | None] = {}
    per_form_warm: dict[str, dict[str, Any] | None] = {}
    for f in forms:
        decides = _of_kind(records, "decide", f)
        n_cold = sum(1 for r in decides if _p1(r) == 0.5)
        per_form_cold[f] = {"n": n_cold, "of": len(decides)}
        total_cold += n_cold
        per_form_source_records[f] = _latest_boot_n_source_records(records, f)
        per_form_warm[f] = latest_boot_warm(records, f)
    entries.append({
        "name": "cold_start_feature_insensitivity",
        "boundary_demanded": "the warm-corpus size is the binding constraint",
        "fires": total_cold > 0,
        "count": total_cold, "of": total_ticks, "per_form": per_form_cold,
        "boot_snapshot_n_source_records": per_form_source_records,
        "boot_snapshot_warm_join": per_form_warm,
        "note": (
            "boot_snapshot_n_source_records is the REAL BootSnapshot.n_source_records each "
            "form's most recent kind:\"boot\" row persisted: the VERDICT-source rows "
            "(decisions + reactions) that (re)boot's snapshot read, before join/exclusion "
            "filtering — null for a form with no boot record, or one written before the "
            "field existed. It deliberately EXCLUDES the warm fair-fight rows, which are "
            "accounted separately in boot_snapshot_warm_join (rows read vs rows actually "
            "joined, with a loud note when a non-empty vector file joined ZERO rows): a warm "
            "row that cannot join teaches the shadow nothing and must never pad a published "
            "warm-corpus size. count/per_form above remain a SECONDARY, corroborating signal: "
            "p1==0.5 (uninformative) decide ticks, a directly observable proxy for the "
            "cold-start plateau still being in effect."
        ),
    })

    return entries


# --- the world's own policy, published (what the declared utility does at each credence) ---


_POLICY_GRID: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0)


def world_policy(records: list[dict[str, Any]], forms: list[str]) -> dict[str, Any]:
    """What each form's DECLARED utility would fire at a given credence — the policy the
    shadow is actually running, published rather than left to be inferred from a tick
    histogram. Derived from the boot record's own u_bar (never a default), through
    ``world.argmax_action`` (argmaxEU, first-listed ties — the wire's own rule), so a reader
    can see the p1 regions each affordance owns and check any observed tick against them."""
    out: dict[str, Any] = {}
    for f in forms:
        u_bar = latest_boot_u_bar(records, f)
        if u_bar is None:
            out[f] = {"u_bar": None,
                      "note": "no boot-record u_bar — this form's policy is not derivable."}
            continue
        out[f] = {
            "u_bar": u_bar,
            "utility_table": utility_table_by_action(u_bar),
            "argmax_by_p1": {str(p): W.argmax_action(u_bar, p) for p in _POLICY_GRID},
            "note": (
                "argmax_by_p1 is this world's OWN utility arithmetic (world.argmax_action) "
                "over the boot-recorded u_bar — the same table the frozen engine argmaxes. "
                "Information actions are priced as myopic perfect information (utility_by_action's "
                "declared bake-in), which is why gather owns most of the interior."
            ),
        }
    return out


# --- 5. provenance -------------------------------------------------------------------------


def provenance(records: list[dict[str, Any]], forms: list[str]) -> dict[str, Any]:
    """One entry per form: every DISTINCT (binary_sha256, world_digest) identity its
    boot records ever declared, oldest first — never silently collapsed to "the last
    one" when a respawn changed identity mid-run (a live-posterior u_bar can drift the
    world_digest between boots); ``drifted`` names when more than one occurred."""
    out: dict[str, Any] = {}
    for f in forms:
        boots = _of_kind(records, "boot", f)
        seen: set[tuple[Any, Any]] = set()
        distinct: list[dict[str, Any]] = []
        for b in boots:
            key = (b.get("binary_sha256"), b.get("world_digest"))
            if key in seen:
                continue
            seen.add(key)
            distinct.append({
                "binary_sha256": b.get("binary_sha256"),
                "world_digest": b.get("world_digest"),
                "engine": b.get("engine"),
                "forms": b.get("forms"),
                "respawn_count": b.get("respawn_count"),
                "first_seen_ts": b.get("ts"),
            })
        out[f] = {
            "n_boot_records": len(boots),
            "distinct_identities": distinct,
            "drifted": len(distinct) > 1,
        }
    return out


def _latest_boot_world_digest(records: list[dict[str, Any]], form: str) -> str | None:
    boots = _of_kind(records, "boot", form)
    if not boots:
        return None
    digest = boots[-1].get("world_digest")
    return str(digest) if isinstance(digest, str) else None


# --- assembling the report -----------------------------------------------------------------


def build_report(
    records: list[dict[str, Any]], baseline: Baseline | None = None,
    labels: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """The pure core: every section, over the given record list and (optional) baseline
    arm. No wall-clock field — given the same inputs this is byte-reproducible.

    ``labels`` (``question_id -> correct bit``, from :func:`load_correctness_labels`) enables
    the enact realised-EU detector (P1): passed None, that section is None and the report is
    byte-for-byte what it was before the detector landed."""
    forms = declared_forms(records)
    stats_record = latest_stats_record(records)

    per_form_stats = {f: form_stats(records, f, stats_record=stats_record) for f in forms}
    differential_by_form = {
        f: differential(records, f, u_bar=latest_boot_u_bar(records, f)) for f in forms
    }
    gates_by_form = {f: gate_advisory(records, f) for f in forms}
    provenance_by_form = provenance(records, forms)

    grounded_by_form: dict[str, Any] | None = None
    if baseline is not None:
        grounded_by_form = {}
        for f in forms:
            terminal = terminal_decide_per_question(records, f)
            cont = contingency_tables(terminal, baseline.by_mirror_id)
            grounded_by_form[f] = {
                "join": join_diagnostics(terminal, baseline),
                "contingency": cont,
                "realized_loss": realized_loss(
                    terminal, baseline.by_mirror_id,
                    u_bar=latest_boot_u_bar(records, f),
                    boot_world_digest=_latest_boot_world_digest(records, f),
                ),
                "n_min_honesty": n_min_honesty(cont["n_joined"]),
            }

    return {
        "forms_declared": forms,
        "legend": {
            "map": dict(REAL_TO_MEMBRANE), "lines": list(LEGEND_LINES),
            "hedge_modelling_choice": HEDGE_MODELLING_CHOICE,
        },
        "global_counters": global_counters(stats_record),
        "per_form_stats": per_form_stats,
        "world_policy": world_policy(records, forms),
        "differential": differential_by_form,
        "gates": gates_by_form,
        "enactments": {f: enactment(records, f) for f in forms},
        "enact_realised_eu": (
            None if labels is None
            else {f: enact_realised_eu(records, f, labels, latest_boot_u_bar(records, f))
                  for f in forms}
        ),
        "grounded": grounded_by_form,
        "demand_ledger": demand_ledger(records, forms),
        "provenance": provenance_by_form,
    }


# --- rendering: report.md -------------------------------------------------------------------


def _fmt_fraction(n: int, of: int) -> str:
    pct = f" ({100.0 * n / of:.1f}%)" if of else ""
    return f"{n}/{of}{pct}"


def _md_global_counters(gc: dict[str, Any]) -> list[str]:
    lines = ["## 0. Submit-path counters (PROCESS-GLOBAL, reported once)", ""]
    if not gc.get("observable"):
        lines += [f"_{gc['note']}_", ""]
        return lines
    lines.append(
        f"- drops={gc['drops']} · skips={gc['skips']} · submit_errors={gc['submit_errors']} "
        f"· queue_depth={gc['queue_depth']} (as of the log's last kind:\"stats\" row, "
        f"ts={gc['as_of_ts']})"
    )
    lines += [f"- {gc['scope']}", ""]
    return lines


def _md_per_form_stats(form: str, stats: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    lines.append(f"- decide ticks: {stats['n_decide_ticks']}")
    lines.append(f"- evidence ticks: {stats['n_evidence_ticks']}")
    lines.append(f"- ticks total: {stats['ticks_total']}")
    lines.append(f"- respawn attempts: {stats['respawn_attempts']}")
    ri = stats["raw_internal"]
    lines.append(f"- raw_internal (the internal think act won): {_fmt_fraction(ri['n'], ri['of'])}")
    lines.append("- action distribution:")
    for action, v in stats["action_distribution"].items():
        lines.append(f"  - {action}: {_fmt_fraction(v['n'], v['of'])}")
    lat = stats["decide_latency_ms"]
    lines.append(f"- decide latency: p50={lat['p50']} ms, p95={lat['p95']} ms (n={lat['n']})")
    lines.append(f"- dead_drops (this form only): {stats['dead_drops_note']}")
    lines.append("")
    return lines


def _md_world_policy(form: str, p: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    if p.get("u_bar") is None:
        lines += [f"_{p['note']}_", ""]
        return lines
    lines.append(f"- u_bar (boot-recorded, the utility the shadow actually decided under): "
                 f"{p['u_bar']}")
    lines.append(f"- utility table (action -> [u(y=0), u(y=1)]): {p['utility_table']}")
    lines.append("- would-fire by credence (argmaxEU, first-listed ties):")
    for p1, action in p["argmax_by_p1"].items():
        lines.append(f"  - p1={p1}: {action}")
    lines.append(f"- note: {p['note']}")
    lines.append("")
    return lines


def _md_differential(form: str, diff: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    ov = diff["agreement_overall"]
    lines.append(f"- agreement overall: {_fmt_fraction(ov['agree'], ov['n'])}")
    if diff["n_unmapped_real_effector"]:
        lines.append(
            f"- unmapped real effectors (excluded from agreement): "
            f"{diff['n_unmapped_real_effector']}"
        )
    lines.append("- agreement per real action:")
    for action, v in diff["agreement_per_real_action"].items():
        lines.append(f"  - {action}: {_fmt_fraction(v['agree'], v['n'])}")
    dis = diff["disagreements"]
    lines.append("")
    lines.append(f"#### Disagreements ({len(dis)} enumerated)")
    lines.append("")
    if dis:
        lines.append("| question_id | t | real | real_mapped | would | p1 | eu_delta |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in dis:
            lines.append(
                f"| {d['question_id']} | {d['t']} | {d['real']} | {d['real_mapped']} | "
                f"{d['would']} | {d['p1']} | {d.get('eu_delta')} |"
            )
        by_class = diff.get("disagreement_eu_by_class") or {}
        if by_class:
            lines.append("")
            lines.append("Engine EU delta by class (EU(would) - EU(real), the form's own "
                         "boot u_bar at each tick's p1; unpriceable rows named, never 0):")
            lines.append("")
            for cls, cell in by_class.items():
                lines.append(
                    f"- `{cls}`: n={cell['n']}, priced={cell['priced_n']}, "
                    f"Σ eu_delta={cell['eu_delta_sum']}"
                )
    else:
        lines.append("_none._")
    lines.append("")
    return lines


def _md_gates(form: str, g: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    if not g["n"]:
        lines += ["_No gate rows: no seam gate pre-emption reached the shadow._", ""]
        return lines
    lines.append(f"- gate pre-emptions observed: {g['n']}")
    for gate, cell in g["by_gate"].items():
        would = ", ".join(f"{a}: {n}" for a, n in cell["would"].items())
        lines.append(f"  - `{gate}`: n={cell['n']} — engine would: {would}")
    lines += ["", f"_{g['note']}_", ""]
    return lines


def _md_enactment(form: str, e: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    if not e["n"]:
        lines += ["_No enact rows: the live flag (LIFE_AGENT_MEMBRANE_LIVE) has not "
                  "produced a tick in this log._", ""]
        return lines
    lines.append(f"- live enactments: {e['n']}")
    by_action = ", ".join(f"{a}: {n}" for a, n in sorted(e["by_engine_action"].items()))
    lines.append(f"  - by engine action: {by_action}")
    for tr, n in sorted(e["by_transition"].items()):
        lines.append(f"  - `{tr}`: {n}")
    if e["degraded"]:
        deg = ", ".join(f"{k}: {n}" for k, n in sorted(e["degraded"].items()))
        lines.append(f"  - degradations: {deg}")
    lines += ["", f"_{e['note']}_", ""]
    return lines


def _md_enact_realised_eu(form: str, e: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    if "realised_eu_total" not in e:
        lines += [f"- terminal enact rows: {e['n_terminal']} (labelled: {e['n_labelled']})",
                  f"_{e['note']}_", ""]
        return lines
    over = e["over_assertion"]
    lines += [
        f"- terminal enact rows: {e['n_terminal']} (labelled {e['n_labelled']}, "
        f"priced {e['n_priced']})",
        f"- **realised EU vs abstaining: {e['eu_vs_abstain']:+.2f} total, "
        f"{e['realised_eu_per_q']:+.3f}/question** "
        f"(abstain baseline earns 0 — negative means the live path lost EU)",
        f"- asserts: {e['asserts']['correct']} correct, {e['asserts']['wrong']} wrong",
        f"- **over-assertion (daemon withheld, engine asserted, wrong): {over['n']} "
        f"(realised cost {over['cost']:+.2f})**",
        "", f"_{e['note']}_", "",
    ]
    return lines


def _md_contingency_table(name: str, table: dict[str, int]) -> list[str]:
    return [
        f"- {name} (n={table['n']}):",
        f"  - would & actual: {table['would_and_actual']}",
        f"  - would & not actual: {table['would_and_not_actual']}",
        f"  - not would & actual: {table['not_would_and_actual']}",
        f"  - not would & not actual: {table['not_would_and_not_actual']}",
    ]


def _md_grounded(form: str, g: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    j = g["join"]
    lines.append(f"**Join: {j['n_joined']} rows.** {j['note']}")
    lines.append("")
    lines.append(
        f"- shadow-observed questions: {j['n_shadow_questions']} · baseline rows read: "
        f"{j['baseline_rows_read']} (scored: {j['baseline_rows_scored']}, mapped into the "
        f"mirror-id namespace: {j['baseline_rows_mapped']}, unmapped: "
        f"{j['baseline_rows_unmapped']}, corpus->mirror map size: "
        f"{j['corpus_to_mirror_id_map_size']})"
    )
    lines.append("")
    cont = g["contingency"]
    lines += _md_contingency_table(
        "would-abstain x actual-wrong", cont["would_abstain_x_actual_wrong"],
    )
    lines += _md_contingency_table(
        "would-gather x actual-miss", cont["would_gather_x_actual_miss"],
    )
    lines.append(f"- miss definition: {cont['miss_definition']}")
    lines.append("")
    rl = g["realized_loss"]
    if not rl.get("scored"):
        lines.append(f"- realized loss: **{rl['reason']}**")
        lines.append("")
    else:
        lines.append(f"- decisive definition: {rl['decisive_definition']}")
        lines.append(f"- n joined={rl['n_joined']}, n decisive={rl['n_decisive']}")
        if rl["window"]:
            lines.append(f"- window: {rl['window']['from']} .. {rl['window']['to']}")
        real_p, would_p = rl["real_policy"], rl["would_policy"]
        lines.append(f"- real policy mean loss: {real_p['mean_loss']} (n={real_p['n']})")
        lines.append(f"- would policy mean loss: {would_p['mean_loss']} (n={would_p['n']})")
        lines.append(f"- utility table used: {rl['utility_table_used']}")
        lines.append(
            "- scored under the boot-recorded u_bar (the utility this form actually decided "
            f"under, NOT the world's fallback defaults): {rl['scored_under_boot_u_bar']} — "
            f"u_bar={rl['u_bar_used']}, boot world_digest={rl['boot_world_digest']}"
        )
        lines.append("")
    nm = g["n_min_honesty"]
    lines.append(f"- n_min honesty: {nm['note']} (n_min={nm['n_min']}, window={nm['window']})")
    lines.append(f"  - source: {nm['source']}")
    lines.append("")
    return lines


def _md_demand_ledger(entries: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for e in entries:
        lines.append(f"### {e['name']}")
        lines.append("")
        if "fires" in e:
            lines.append(f"- **fires: {e['fires']}** (does this run actually evidence the demand?)")
        lines.append(f"- count: {_fmt_fraction(e['count'], e['of'])}")
        lines.append(f"- boundary demanded: {e['boundary_demanded']}")
        if "per_form" in e:
            lines.append(f"- per form: {e['per_form']}")
        if "boot_snapshot_warm_join" in e:
            lines.append(f"- boot snapshot warm join per form: {e['boot_snapshot_warm_join']}")
        if "boot_snapshot_n_source_records" in e:
            lines.append(
                f"- boot snapshot n_source_records per form: "
                f"{e['boot_snapshot_n_source_records']}"
            )
        if "distinct_actions_observed" in e:
            lines.append(f"- distinct actions observed: {e['distinct_actions_observed']}")
        lines.append(f"- note: {e['note']}")
        lines.append("")
    return lines


def _md_provenance(form: str, p: dict[str, Any]) -> list[str]:
    lines = [f"### {form}", ""]
    lines.append(f"- boot records: {p['n_boot_records']}")
    lines.append(f"- drifted (>1 distinct binary/world identity across boots): {p['drifted']}")
    for ident in p["distinct_identities"]:
        lines.append(
            f"  - binary_sha256={ident['binary_sha256']} world_digest={ident['world_digest']} "
            f"engine={ident['engine']} forms={ident['forms']} "
            f"respawn_count={ident['respawn_count']}"
        )
    lines.append("")
    return lines


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Membrane shadow — differential + demand report", ""]
    lines.append(f"Forms declared: {', '.join(report['forms_declared']) or '(none)'}")
    lines.append("")

    lines += _md_global_counters(report["global_counters"])

    lines += ["## 1. Per-form stats", ""]
    for form, stats in report["per_form_stats"].items():
        lines += _md_per_form_stats(form, stats)

    lines += ["## 1b. The world's declared policy (from each boot's own u_bar)", ""]
    for form, p in report["world_policy"].items():
        lines += _md_world_policy(form, p)

    lines += ["## 2. Differential vs the incumbent", ""]
    lines.append("Legend (a named modelling choice, printed verbatim):")
    lines.append("")
    for line in report["legend"]["lines"]:
        lines.append(f"- `{line}`")
    lines.append("")
    lines.append(f"_{report['legend']['hedge_modelling_choice']}_")
    lines.append("")
    for form, diff in report["differential"].items():
        lines += _md_differential(form, diff)

    lines += ["## 2b. Seam gate pre-emptions (M2 advisory)", ""]
    for form, g in report["gates"].items():
        lines += _md_gates(form, g)

    lines += ["## 2c. Live enactments (M3 — the coarse menu live)", ""]
    for form, e in report.get("enactments", {}).items():
        lines += _md_enactment(form, e)

    lines += ["## 2d. Enact realised EU (priced vs the Claude verdict labels)", ""]
    if report.get("enact_realised_eu") is None:
        lines += ["_Not run: pass `--verdicts <claude_verdicts.jsonl>` to price the enact "
                  "stream against correctness labels._", ""]
    else:
        for form, e in report["enact_realised_eu"].items():
            lines += _md_enact_realised_eu(form, e)

    lines += ["## 3. Grounded joins", ""]
    if report["grounded"] is None:
        lines.append("_Not run: pass `--vectors <fairfight run dir>` to enable this section._")
        lines.append("")
    else:
        for form, g in report["grounded"].items():
            lines += _md_grounded(form, g)

    lines += ["## 4. Demand ledger", ""]
    lines += _md_demand_ledger(report["demand_ledger"])

    lines += ["## 5. Provenance", ""]
    for form, p in report["provenance"].items():
        lines += _md_provenance(form, p)

    return "\n".join(lines) + "\n"


# --- CLI -------------------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shadow-log", default=str(C.membrane_shadow_log()),
        help="the membrane shadow's append-only JSONL log (default: the configured path)",
    )
    parser.add_argument(
        "--vectors", default=None,
        help="a fair-fight run directory (optional; enables the grounded-join section)",
    )
    parser.add_argument(
        "--verdicts", nargs="?", default=None, const=str(C.CLAUDE_VERDICTS_LOG),
        help="Claude verdict log to price the enact stream against (bare flag uses the "
             "configured path; enables §2d, the enact realised-EU detector)",
    )
    parser.add_argument(
        "--out-dir", default=str(C.membrane_dir()),
        help="where to write report.json + report.md (default: the membrane KB subtree)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    records = load_shadow_records(Path(args.shadow_log))
    baseline = load_baseline_vectors(Path(args.vectors)) if args.vectors else None
    labels = load_correctness_labels(Path(args.verdicts)) if args.verdicts else None
    report = build_report(records, baseline, labels=labels)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "report.md").write_text(render_md(report), encoding="utf-8")

    n_decide = sum(s["n_decide_ticks"] for s in report["per_form_stats"].values())
    print(
        f"membrane report -> {out_dir} "
        f"(forms={report['forms_declared']}, decide_ticks={n_decide}, "
        f"grounded={'yes' if report['grounded'] is not None else 'no'})"
    )
    # A grounded section whose join is EMPTY is the one result a reader must not have to dig
    # for — it is the difference between "no signal yet" and "this report is measuring
    # nothing". Said here, on stdout, as well as in the report body.
    for form, g in (report["grounded"] or {}).items():
        if g["join"]["n_joined"] == 0:
            print(f"  !! {form}: grounded join is EMPTY — {g['join']['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
