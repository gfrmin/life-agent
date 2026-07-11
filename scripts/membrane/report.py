#!/usr/bin/env python3
"""``scripts/membrane/report.py`` — the membrane shadow's differential + demand report.

Reads ``life_agent.membrane.shadow.MembraneShadow``'s append-only shadow log (kinds
``boot``/``respawn``/``decide``/``evidence`` — see that module's docstring for the exact
record shapes; this file reads them, never re-derives them) and, optionally, a
fair-fight run directory's ``baseline`` arm outcomes (``life_agent.fairfight.records
.OutcomeVector`` — the SAME executor ``/decide`` loop the shadow mirrors, per
``scripts/fairfight/run_fairfight.py``'s ``path="executor"`` baseline config and
``shadow.boot_snapshot``'s own precedent for this exact run-dir shape). Writes
``report.json`` + ``report.md`` under ``--out-dir``.

**What the log does NOT carry** (named once, here, rather than at each call site): the
three submit-path counters (``drops``/``skips``/``submit_errors``) and each form's
``dead_drops`` are, by shadow.py's own module docstring, "deliberately never persisted
as their own log rows" — visible only via the live ``MembraneShadow.stats()`` API. An
offline, log-only report cannot recover them; every place this report would otherwise
report a bare zero for one of those counters instead says so explicitly.

Report structure (five top-level sections, matching the brief's own enumeration):

    1. ``per_form_stats``   — ticks, action distribution, raw_internal, respawns, latency.
    2. ``differential``     — the real (incumbent) action vs the shadow's would-action,
                              mapped through a NAMED legend, per form; every disagreement
                              enumerated (never only aggregated — the §8.5 discipline).
    3. ``grounded``         — (only with ``--vectors``) contingency tables + realized loss
                              per decision, joined to the fair-fight baseline arm.
    4. ``demand_ledger``    — named limitations actually hit this run, each with its count
                              and the boundary it demands.
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/: self-import below

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


def load_baseline_vectors(run_dir: Path) -> dict[str, dict[str, Any]]:
    """``{question_id: OutcomeVector-JSON row}`` for one fair-fight run's ``baseline``
    arm — the arm this shadow actually mirrors (``run_fairfight.py``'s
    ``ask.answer_via_executor(path="executor")``, the same ``/decide`` loop
    ``core/shadow_mirror.py`` fans out to ``/decide-support``; also the exact run-dir
    shape ``shadow.boot_snapshot`` already reads warm outcomes from). Rows are
    validated through ``records.from_json`` (raises loudly on a malformed row — the
    same discipline ``scripts/dominance/run_dominance.py``'s ``_load_arm_vectors``
    already uses, never silently skewing a downstream rate) and filtered through
    ``records.scored`` (the one canonical infra-failure filter). A missing file yields
    an empty join population, not an error (an optional flag pointing at a run that
    hasn't produced a baseline arm yet is a valid, reportable state)."""
    path = run_dir / "arms" / "baseline" / "vectors.jsonl"
    if not path.exists():
        return {}
    rows: list[REC.OutcomeVector] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(REC.from_json(json.loads(line)))
    by_question: dict[str, dict[str, Any]] = {}
    for v in REC.scored(rows):
        by_question[v.question_id] = REC.to_json(v)  # latest row per question_id wins
    return by_question


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
    "not observable from the persisted shadow log — shadow.py's own module docstring: "
    "drops/skips/submit_errors and each form's dead_drops are counted only via the live "
    "MembraneShadow.stats() API and are deliberately never written as a log row. Read "
    "them from the live daemon (e.g. the bridge's /ready) instead."
)


def form_stats(records: list[dict[str, Any]], form: str) -> dict[str, Any]:
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
        "drops_skips_dead_drops": _UNPERSISTED_COUNTERS_NOTE,
    }


# --- 2. the differential vs the incumbent -----------------------------------------------

# The executor's own effector vocabulary (core/executor.py's `_WITHHOLD`, core/gate.py's
# `ASSERT_ACTIONS`/`WITHHOLD_ACTIONS`, and the daemon-scheduled "gather" steer) mapped
# onto the world's four affordances. A NAMED, printed legend — never a silent guess.
REAL_TO_MEMBRANE: dict[str, str] = {
    "report": "respond", "report_scoped": "respond", "hedge": "respond",
    "abstain": "abstain", "miss": "abstain",
    "ask_clarify": "ask",
    "gather": "gather",
}

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


def differential(records: list[dict[str, Any]], form: str) -> dict[str, Any]:
    """Real (legend-mapped) vs would (the shadow's own ``action``) over EVERY decide
    tick for ``form`` — not only terminal ticks: every real ``/decide`` call is mirrored
    (Task 6), so every one is a real comparison point. A tick whose ``real_effector``
    falls outside :data:`REAL_TO_MEMBRANE` is excluded from the agreement rate (there is
    no real action to agree or disagree with) but tallied by name in
    ``n_unmapped_real_effector`` — never silently dropped from view."""
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
            })
    agreement_per_real_action = {
        action: {
            "n": v["n"], "agree": v["agree"],
            "rate": round(v["agree"] / v["n"], 4) if v["n"] else None,
        }
        for action, v in sorted(per_real.items())
    }
    return {
        "n_mapped": n_mapped,
        "n_unmapped_real_effector": dict(sorted(unmapped.items())),
        "agreement_overall": {
            "n": n_mapped, "agree": n_agree,
            "rate": round(n_agree / n_mapped, 4) if n_mapped else None,
        },
        "agreement_per_real_action": agreement_per_real_action,
        "disagreements": disagreements,
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
    return [(terminal[qid], vectors[qid]) for qid in terminal if qid in vectors]


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


def utility_table_by_action(u_bar: Mapping[str, float] | None = None) -> dict[str, list[float]]:
    """``{action: [u(y=0), u(y=1)]}`` off ``world.utility_rows`` — defaults to the
    world's DECLARED default table (``u_bar={}``: u_wrong=-9.0, lambda_int=0.1,
    kappa_att=0.02) since an offline report has no access to a live posterior. See
    :func:`realized_loss`'s ``default_table_matches_boot`` for whether that default was
    actually what was live for a given form's boot."""
    rows = W.utility_rows(dict(u_bar or {}))
    table: dict[str, list[float]] = {}
    for r in rows:
        fire = r.get("fire")
        u = r.get("u")
        if not isinstance(fire, int) or not isinstance(u, list):
            continue  # the "internal": "think" sentinel row has no "fire" key
        table[W.ID_TO_ACTION[fire]] = [float(x) for x in u]
    return table


def realized_loss(
    terminal: Mapping[str, dict[str, Any]], vectors: Mapping[str, dict[str, Any]],
    *, boot_world_digest: str | None = None,
) -> dict[str, Any]:
    """Realized loss per decision — ``-table[action][y]`` — for BOTH the incumbent's
    real action and the shadow's would-action, on the DECISIVE joined population (see
    :data:`DECISIVE_DEFINITION_NOTE`). ``boot_world_digest`` (a form's boot record
    ``world_digest``, if known) lets a reader check whether the declared default table
    this function scores under is what was actually live for that form's run."""
    joined = _joined_rows(terminal, vectors)
    decisive = [(r, v) for r, v in joined if v.get("asserted") is True]
    table = utility_table_by_action()

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
        "n_joined": len(joined), "n_decisive": len(decisive),
        "n_real_unmapped_excluded": n_real_unmapped,
        "n_would_unrecognized_excluded": n_would_unrecognized,
        "window": window,
        "real_policy": {"mean_loss": _mean(real_losses), "n": len(real_losses)},
        "would_policy": {"mean_loss": _mean(would_losses), "n": len(would_losses)},
        "utility_table_used": table,
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
    note = (
        f"n={n} clears the registered n_min={GOVERNOR_N_MIN}."
        if clears else
        f"n={n} is BELOW the registered n_min={GOVERNOR_N_MIN} — directional only, "
        "not a registered reading."
    )
    return {
        "n": n, "n_min": GOVERNOR_N_MIN, "window": GOVERNOR_N_MIN_WINDOW,
        "clears": clears, "source": GOVERNOR_N_MIN_SOURCE, "note": note,
    }


# --- 4. the demand ledger ----------------------------------------------------------------

P1_CEILING = 0.9
_P1_CEILING_EPS = 1e-9


def demand_ledger(records: list[dict[str, Any]], forms: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    # V/R: respond structurally unreachable at the frozen grid ceiling.
    per_form_ceiling: dict[str, dict[str, int]] = {}
    total_ceiling = 0
    total_ticks = 0
    for f in forms:
        decides = _of_kind(records, "decide", f)
        hit = sum(
            1 for r in decides
            if (p1 := _p1(r)) is not None and p1 >= P1_CEILING - _P1_CEILING_EPS
        )
        per_form_ceiling[f] = {"n": hit, "of": len(decides)}
        total_ceiling += hit
        total_ticks += len(decides)
    entries.append({
        "name": "respond_unreachable_p1_ceiling",
        "boundary_demanded": "proplang Boundary V/R (the refine lattice)",
        "count": total_ceiling, "of": total_ticks, "per_form": per_form_ceiling,
        "note": (
            "respond needs p1 > 0.9 strictly (EU(respond) = 10*p1 - 9 under the world's "
            "declared default u_wrong=-9.0/u_correct=1.0); the grid's ceiling is 0.9, "
            "where EU(respond) ties EU(abstain)=0 and abstain wins by first-listed "
            "order (world.AFFORDANCES) — verified live against the real binary. "
            "Counted: decide ticks where the shadow's p1 hit the ceiling."
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
            "count": 0, "of": 0, "note": "no decide ticks in this log.",
        })

    # Cold-start feature-insensitivity.
    per_form_cold: dict[str, dict[str, int]] = {}
    total_cold = 0
    for f in forms:
        decides = _of_kind(records, "decide", f)
        n_cold = sum(1 for r in decides if _p1(r) == 0.5)
        per_form_cold[f] = {"n": n_cold, "of": len(decides)}
        total_cold += n_cold
    entries.append({
        "name": "cold_start_feature_insensitivity",
        "boundary_demanded": "the warm-corpus size is the binding constraint",
        "count": total_cold, "of": total_ticks, "per_form": per_form_cold,
        "note": (
            "p1 == 0.5 (uninformative) ticks — the cold-start plateau. DEVIATION FROM "
            "THE BRIEF, NAMED: the brief asks to report the actual number of warm "
            "evidence rows the boot snapshot found (BootSnapshot.n_source_records); "
            "that count is exposed only via the live "
            "MembraneShadow.stats()['snapshot_records'] and is never written into a "
            "boot log row (shadow.py's _write_boot_record does not persist it), so an "
            "offline log-only report cannot recover it. Reported instead: the count of "
            "p1==0.5 ticks, a directly observable proxy for the cold-start plateau "
            "still being in effect."
        ),
    })

    return entries


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
    records: list[dict[str, Any]], baseline_vectors: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The pure core: every section, over the given record list and (optional) baseline
    vectors. No wall-clock field — given the same inputs this is byte-reproducible."""
    forms = declared_forms(records)

    per_form_stats = {f: form_stats(records, f) for f in forms}
    differential_by_form = {f: differential(records, f) for f in forms}
    provenance_by_form = provenance(records, forms)

    grounded_by_form: dict[str, Any] | None = None
    if baseline_vectors is not None:
        grounded_by_form = {}
        for f in forms:
            terminal = terminal_decide_per_question(records, f)
            cont = contingency_tables(terminal, baseline_vectors)
            digest = _latest_boot_world_digest(records, f)
            default_digest = SH.world_digest({}, utility_form=f) if f in W.UTILITY_FORMS else None
            grounded_by_form[f] = {
                "contingency": cont,
                "realized_loss": realized_loss(
                    terminal, baseline_vectors, boot_world_digest=digest,
                ),
                "n_min_honesty": n_min_honesty(cont["n_joined"]),
                "default_table_matches_boot": (
                    digest is not None and default_digest is not None and digest == default_digest
                ),
            }

    return {
        "forms_declared": forms,
        "legend": {
            "map": dict(REAL_TO_MEMBRANE), "lines": list(LEGEND_LINES),
            "hedge_modelling_choice": HEDGE_MODELLING_CHOICE,
        },
        "per_form_stats": per_form_stats,
        "differential": differential_by_form,
        "grounded": grounded_by_form,
        "demand_ledger": demand_ledger(records, forms),
        "provenance": provenance_by_form,
    }


# --- rendering: report.md -------------------------------------------------------------------


def _fmt_fraction(n: int, of: int) -> str:
    pct = f" ({100.0 * n / of:.1f}%)" if of else ""
    return f"{n}/{of}{pct}"


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
    lines.append(f"- drops/skips/dead_drops: {stats['drops_skips_dead_drops']}")
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
        lines.append("| question_id | t | real | real_mapped | would | p1 |")
        lines.append("|---|---|---|---|---|---|")
        for d in dis:
            lines.append(
                f"| {d['question_id']} | {d['t']} | {d['real']} | {d['real_mapped']} | "
                f"{d['would']} | {d['p1']} |"
            )
    else:
        lines.append("_none._")
    lines.append("")
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
    cont = g["contingency"]
    lines.append(
        f"- n joined (terminal decide tick <-> baseline vector, by question_id): "
        f"{cont['n_joined']}"
    )
    lines += _md_contingency_table(
        "would-abstain x actual-wrong", cont["would_abstain_x_actual_wrong"],
    )
    lines += _md_contingency_table(
        "would-gather x actual-miss", cont["would_gather_x_actual_miss"],
    )
    lines.append(f"- miss definition: {cont['miss_definition']}")
    lines.append("")
    rl = g["realized_loss"]
    lines.append(f"- decisive definition: {rl['decisive_definition']}")
    lines.append(f"- n joined={rl['n_joined']}, n decisive={rl['n_decisive']}")
    if rl["window"]:
        lines.append(f"- window: {rl['window']['from']} .. {rl['window']['to']}")
    real_p, would_p = rl["real_policy"], rl["would_policy"]
    lines.append(f"- real policy mean loss: {real_p['mean_loss']} (n={real_p['n']})")
    lines.append(f"- would policy mean loss: {would_p['mean_loss']} (n={would_p['n']})")
    lines.append(f"- utility table used: {rl['utility_table_used']}")
    lines.append(
        f"- default table matches this form's boot world_digest: "
        f"{g['default_table_matches_boot']}"
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
        lines.append(f"- count: {_fmt_fraction(e['count'], e['of'])}")
        lines.append(f"- boundary demanded: {e['boundary_demanded']}")
        if "per_form" in e:
            lines.append(f"- per form: {e['per_form']}")
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

    lines += ["## 1. Per-form stats", ""]
    for form, stats in report["per_form_stats"].items():
        lines += _md_per_form_stats(form, stats)

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
        "--out-dir", default=str(C.membrane_dir()),
        help="where to write report.json + report.md (default: the membrane KB subtree)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    records = load_shadow_records(Path(args.shadow_log))
    baseline_vectors = load_baseline_vectors(Path(args.vectors)) if args.vectors else None
    report = build_report(records, baseline_vectors)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
