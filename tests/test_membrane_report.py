"""Hermetic tests for ``scripts/membrane/report.py`` — the differential + demand report.

Every fixture is synthetic (public repo, PRINCIPLES §12): question ids ``q-001`` etc.,
paths under ``tmp_path`` — never real corpus content. Shadow-log records are built as
plain dicts matching ``life_agent.membrane.shadow``'s ACTUAL written shapes (verified
against ``shadow.py`` and ``tests/test_membrane_shadow.py`` directly, not assumed from
the brief); ``OutcomeVector`` rows are built through the real dataclass (the same
``_vector`` idiom ``tests/test_dominance.py`` already uses) so every fixture obeys the
record's own vocabulary checks.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_membrane_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from membrane import report as R

from life_agent.core import decisions as DEC
from life_agent.fairfight import records as REC

# The REAL utility posterior means (GET :8798/utility, 2026-07-11) — seven scalars, no owner
# data. Fixtures declare THIS by default, not world.utility_rows' fallbacks: the reaction loop
# has already narrowed u_wrong from -9.0 to about -5.94, which moves every utility-derived
# threshold in the report, and a suite that only ever exercised the defaults is precisely why
# a false demand claim survived to the deliverable.
LIVE_U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -5.9395, "u_wrong_scoped": -2.0827,
    "u_hedged": 0.3964, "lambda_int": 1.0009, "kappa_att": 0.0344,
}
# the world's fallback table — what a shadow would run under only if its posterior were unread
DEFAULT_U_BAR: dict[str, float] = {
    "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, "lambda_int": 0.1, "kappa_att": 0.02,
}
_MISSING_U_BAR: Any = object()  # sentinel: "not passed" vs an explicit None (an old log)

# The two id namespaces, kept apart on purpose (this is the join the report used to get wrong):
#   * QUESTIONS maps a CORPUS id (what an OutcomeVector carries) to the question TEXT;
#   * DEC.question_id(text) is the MIRROR id (what every shadow decide record carries).
# No test below may fabricate the same id on both sides — the bridge must be exercised.
QUESTIONS: dict[str, str] = {
    "q-001": "What colour is the shed?",
    "q-002": "When does the permit expire?",
    "q-003": "Who signed the lease?",
    "q-004": "How many keys are there?",
}


def mirror(corpus_id: str) -> str:
    """The mirror id a live decide record would carry for that corpus question."""
    return DEC.question_id(QUESTIONS[corpus_id])


# --- fixture builders ------------------------------------------------------------------


def _summary(**overrides: Any) -> dict[str, Any]:
    base = {
        "n_candidates": 1, "leader_credence": 0.8, "p_none": 0.1, "n_obs": 2,
        "era_split": False, "owner_scoped": False, "grow_pass": False,
    }
    base.update(overrides)
    return base


def _boot(form: str, *, ts: float = 100.0, binary_sha256: str = "abc123",
          world_digest: str = "digest-1", respawn_count: int = 0,
          forms: list[str] | None = None, n_source_records: int = 0,
          u_bar: dict[str, float] | None = _MISSING_U_BAR,
          warm: dict[str, Any] | None = None) -> dict[str, Any]:
    """A `kind: "boot"` row. `u_bar` defaults to the LIVE posterior (below) rather than to
    the world's fallback defaults, deliberately: every utility-derived number in the report
    is a FUNCTION of this, and a fixture that only ever declared the defaults is how a
    threshold got shipped as the constant 0.9. Pass `u_bar=None` for an OLD log (written
    before the shadow persisted it) — the report must then REFUSE to derive, not fall back."""
    row: dict[str, Any] = {
        "event_type": "membrane-shadow", "kind": "boot", "ts": ts, "form": form,
        "engine": {"ok": True, "proto": 1, "models": 40, "namespace_bits": 6},
        "binary_sha256": binary_sha256, "forms": forms or [form],
        "world_digest": world_digest, "respawn_count": respawn_count,
        "n_source_records": n_source_records, "warm": warm,
    }
    resolved = LIVE_U_BAR if u_bar is _MISSING_U_BAR else u_bar
    if resolved is not None:
        row["u_bar"] = dict(resolved)
    return row


def _respawn(form: str, *, ts: float = 100.0, respawn_count: int = 1) -> dict[str, Any]:
    return {
        "event_type": "membrane-shadow", "kind": "respawn", "ts": ts, "form": form,
        "error": "boom", "respawn_count": respawn_count, "max_respawns": 3,
        "permanent": False,
    }


def _stats(
    *, ts: float = 100.0, drops: int = 0, skips: int = 0, submit_errors: int = 0,
    queue_depth: int = 0, snapshot_records: int = 0,
    forms: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A `kind: "stats"` row shaped exactly like `MembraneShadow._write_stats_record`'s
    own output: `event_type`/`kind`/`ts` plus `stats()`'s full payload spread in."""
    return {
        "event_type": "membrane-shadow", "kind": "stats", "ts": ts,
        "forms": forms or {}, "drops": drops, "skips": skips,
        "submit_errors": submit_errors, "queue_depth": queue_depth,
        "snapshot_records": snapshot_records,
    }


def _decide(
    *, form: str, question_id: str, action: str, real_effector: str, t: int = 0,
    ts: float = 100.0, raw_internal: bool = False, latency_ms: float = 10.0,
    p1: float | None = 0.7, sensitivity: bool | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    readouts: dict[str, Any] = {}
    if p1 is not None:
        readouts["p1"] = p1
    if sensitivity is not None:
        readouts["sensitivity"] = sensitivity
    return {
        "event_type": "membrane-shadow", "kind": "decide", "ts": ts,
        "question_id": question_id, "form": form, "action": action,
        "raw_internal": raw_internal, "real_effector": real_effector,
        "latency_ms": latency_ms, "readouts": readouts,
        "summary": summary if summary is not None else _summary(), "t": t,
    }


def _evidence(form: str, *, ts: float = 100.0, t: int = 0) -> dict[str, Any]:
    return {
        "event_type": "membrane-shadow", "kind": "evidence", "ts": ts,
        "stream": "verdict", "decision_id": "dec-1", "y": 1, "form": form, "t": t,
    }


def _vector(**overrides: Any) -> dict[str, Any]:
    """One OutcomeVector row, JSON-safe — built through the real dataclass (the
    ``tests/test_dominance.py`` idiom), for the ``baseline`` arm."""
    base: dict[str, Any] = dict(
        format_version=REC.FORMAT_VERSION, run_id="run-test", arm="baseline",
        question_id="q-001", answerable=True,
        faithfulness=None, completeness=None, citation_fidelity=None,
        bucket="CORRECT", cause=None, asserted=True, asserted_correct=True,
        asserted_distractor=False, hallucinated=None, declined=False,
        correct_abstention=False, over_abstention=False,
        gold_in_topk=True, gold_in_corpus=True, gold_in_candidates=True,
        distractor_in_topk=False, n_retrieved=5,
        probability=None, p_none=None, p_none_correct=None, brier=None,
        cost_usd=0.01, cost_status="measured", in_tokens=100, out_tokens=50,
        cache_read_tokens=0, cache_write_tokens=0, latency_s=1.0,
        model_tier_mix={},
        gather_rounds=None, asks_issued=0, tool_calls=None, think_ticks=None,
        answer_sha256="a" * 64, answer_chars=10, lineage_keys=(), status="ok", notes="",
    )
    base.update(overrides)
    return REC.to_json(REC.OutcomeVector(**base))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _write_baseline_run(run_dir: Path, vectors: list[dict[str, Any]],
                        *, questions: dict[str, str] | None = None) -> None:
    """A fair-fight run dir exactly as ``run_fairfight.py`` writes the parts this report
    reads: the baseline arm's vectors (CORPUS ids) plus the ``run_meta.json`` →
    ``questions_path`` indirection that is the ONLY thing relating those ids to the mirror
    ids the shadow's own records carry. Omitting the questions file (``questions={}``) is a
    real, testable state — a run whose questions file is gone — not a fixture shortcut."""
    _write_jsonl(run_dir / "arms" / "baseline" / "vectors.jsonl", vectors)
    qs = QUESTIONS if questions is None else questions
    questions_path = run_dir / "questions.yaml"
    run_dir.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        "questions:\n" + "".join(
            f'  - id: {qid}\n    question: "{text}"\n' for qid, text in qs.items()
        ),
        encoding="utf-8",
    )
    (run_dir / "run_meta.json").write_text(
        json.dumps({"questions_path": str(questions_path)}), encoding="utf-8",
    )


# --- load_shadow_records / load_baseline_vectors ----------------------------------------


def test_load_shadow_records_skips_malformed_and_non_membrane_lines(tmp_path: Path) -> None:
    path = tmp_path / "shadow.jsonl"
    path.write_text(
        json.dumps(_boot("said@1")) + "\n"
        "not json at all\n"
        + json.dumps({"event_type": "something-else", "kind": "boot"}) + "\n"
        + json.dumps(_decide(form="said@1", question_id="q-001", action="respond",
                              real_effector="report")) + "\n",
        encoding="utf-8",
    )
    records = R.load_shadow_records(path)
    assert len(records) == 2
    assert {r["kind"] for r in records} == {"boot", "decide"}


def test_load_shadow_records_missing_file_is_empty(tmp_path: Path) -> None:
    assert R.load_shadow_records(tmp_path / "nope.jsonl") == []


def test_load_baseline_vectors_reads_baseline_arm_and_rekeys_onto_mirror_ids(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [
        _vector(question_id="q-001", status="ok"),
        _vector(question_id="q-002", status="timeout"),  # excluded: infra failure
    ])
    # a non-baseline arm must never leak into the join population
    _write_jsonl(run_dir / "arms" / "competitor" / "vectors.jsonl",
                 [_vector(question_id="q-003", arm="competitor")])
    baseline = R.load_baseline_vectors(run_dir)
    # keyed by MIRROR id — the namespace the shadow's own decide records live in
    assert set(baseline.by_mirror_id) == {mirror("q-001")}
    assert baseline.by_mirror_id[mirror("q-001")]["question_id"] == "q-001"  # row keeps its id
    assert baseline.n_rows == 2
    assert baseline.n_scored == 1
    assert baseline.id_map_size == len(QUESTIONS)
    assert baseline.n_unmapped == 0


def test_load_baseline_vectors_names_an_unmappable_corpus_loudly(tmp_path: Path) -> None:
    """A run whose questions file no longer maps its corpus ids can produce NO join at all.
    That must be stated, not left to be read off a table of zeros."""
    run_dir = tmp_path / "run-2"
    _write_baseline_run(run_dir, [_vector(question_id="q-001", status="ok")], questions={})
    baseline = R.load_baseline_vectors(run_dir)
    assert baseline.by_mirror_id == {}
    assert baseline.n_scored == 1
    assert baseline.n_unmapped == 1
    assert "0 of 1 scored baseline rows could be mapped" in baseline.note
    assert "EMPTY BY CONSTRUCTION, not under-powered" in baseline.note


def test_load_baseline_vectors_missing_run_dir_is_empty(tmp_path: Path) -> None:
    baseline = R.load_baseline_vectors(tmp_path / "no-such-run")
    assert baseline.by_mirror_id == {}
    assert baseline.n_rows == 0
    assert "nothing to join against" in baseline.note


# --- declared_forms ----------------------------------------------------------------------


def test_declared_forms_from_boot_record() -> None:
    records = [_boot("latent@1", forms=["said@1", "latent@1"])]
    assert R.declared_forms(records) == ["said@1", "latent@1"]


def test_declared_forms_falls_back_to_form_field_union() -> None:
    records = [_decide(form="said@1", question_id="q-001", action="respond",
                        real_effector="report")]
    assert R.declared_forms(records) == ["said@1"]


# --- legend mapping ------------------------------------------------------------------------


def test_map_real_effector_legend() -> None:
    assert R.map_real_effector("report") == "respond"
    assert R.map_real_effector("report_scoped") == "respond"
    assert R.map_real_effector("hedge") == "respond"
    assert R.map_real_effector("abstain") == "abstain"
    assert R.map_real_effector("miss") == "abstain"
    assert R.map_real_effector("ask_clarify") == "ask"
    assert R.map_real_effector("gather") == "gather"


def test_map_real_effector_unknown_is_none() -> None:
    assert R.map_real_effector("something-new") is None
    assert R.map_real_effector(None) is None


# --- form_stats ----------------------------------------------------------------------------


def test_form_stats_counts_action_distribution_and_percentiles() -> None:
    records = [
        _decide(form="said@1", question_id="q-001", action="respond",
                real_effector="report", latency_ms=10.0),
        _decide(form="said@1", question_id="q-002", action="respond",
                real_effector="report", latency_ms=20.0),
        _decide(form="said@1", question_id="q-003", action="abstain",
                real_effector="abstain", latency_ms=30.0, raw_internal=True),
        _decide(form="said@1", question_id="q-004", action="abstain",
                real_effector="abstain", latency_ms=40.0),
        _evidence("said@1"),
        _respawn("said@1"),
    ]
    stats = R.form_stats(records, "said@1")
    assert stats["n_decide_ticks"] == 4
    assert stats["n_evidence_ticks"] == 1
    assert stats["ticks_total"] == 5
    assert stats["respawn_attempts"] == 1
    assert stats["raw_internal"] == {"n": 1, "of": 4}
    assert stats["action_distribution"]["respond"] == {"n": 2, "of": 4}
    assert stats["action_distribution"]["abstain"] == {"n": 2, "of": 4}
    assert stats["action_distribution"]["ask"] == {"n": 0, "of": 4}
    assert stats["action_distribution"]["gather"] == {"n": 0, "of": 4}
    # nearest-rank percentile of [10, 20, 30, 40]: p50 -> idx ceil(0.5*4)-1=1 -> 20
    # p95 -> idx ceil(0.95*4)-1=3 -> 40
    assert stats["decide_latency_ms"] == {"p50": 20.0, "p95": 40.0, "n": 4}
    # no stats_record given (the default) -> the honest not-observable note, never zeros.
    assert stats["dead_drops"] is None
    assert "never" in stats["dead_drops_note"]


def test_form_stats_empty_form_has_no_denominator_crash() -> None:
    stats = R.form_stats([], "said@1")
    assert stats["n_decide_ticks"] == 0
    assert stats["decide_latency_ms"] == {"p50": None, "p95": None, "n": 0}
    assert stats["raw_internal"] == {"n": 0, "of": 0}


# --- form_stats: real counters when a kind:"stats" record is present -----------------------


def test_form_stats_reports_only_its_own_per_form_counter_dead_drops() -> None:
    """I2: `stats()` reports drops/skips/submit_errors as PROCESS-GLOBAL totals (one queue,
    one submit path, every form) — copying them into each form's block made a reader at the
    default two-form deployment double-count all three. Only dead_drops is per-form."""
    records = [
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    stats_row = _stats(
        drops=3, skips=1, submit_errors=2,
        forms={"said@1": {"alive": True, "respawns": 0, "ticks": 5, "dead_drops": 7}},
    )
    stats = R.form_stats(records, "said@1", stats_record=stats_row)
    assert stats["dead_drops"] == 7
    assert "drops" not in stats and "skips" not in stats and "submit_errors" not in stats
    assert "process-global" in stats["dead_drops_note"]


def test_global_counters_are_reported_once_and_labelled_global() -> None:
    stats_row = _stats(drops=3, skips=1, submit_errors=2, queue_depth=4,
                       forms={"said@1": {"dead_drops": 7}, "latent@1": {"dead_drops": 0}})
    gc = R.global_counters(stats_row)
    assert gc["observable"] is True
    assert (gc["drops"], gc["skips"], gc["submit_errors"]) == (3, 1, 2)
    assert "PROCESS-GLOBAL" in gc["scope"]


def test_global_counters_without_a_stats_record_are_not_observable_never_zero() -> None:
    gc = R.global_counters(None)
    assert gc["observable"] is False
    assert "not observable" in gc["note"]
    assert "drops" not in gc  # never a fabricated 0


def test_form_stats_falls_back_to_the_honest_note_without_a_stats_record() -> None:
    records = [
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    stats = R.form_stats(records, "said@1", stats_record=None)
    assert stats["dead_drops"] is None
    assert "not observable" in stats["dead_drops_note"]


def test_form_stats_falls_back_when_stats_record_has_no_entry_for_this_form() -> None:
    # a stats row exists, but this form isn't in its "forms" map (e.g. a log from a run
    # that declared a different form set) -> honest fallback, never a fabricated zero.
    records = [
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    stats_row = _stats(drops=1, skips=0, submit_errors=0, forms={"latent@1": {"dead_drops": 0}})
    stats = R.form_stats(records, "said@1", stats_record=stats_row)
    assert stats["dead_drops"] is None
    assert "not observable" in stats["dead_drops_note"]


# --- latest_stats_record ---------------------------------------------------------------


def test_latest_stats_record_returns_the_last_one() -> None:
    records = [_stats(ts=1.0, drops=1), _stats(ts=2.0, drops=2), _boot("said@1")]
    row = R.latest_stats_record(records)
    assert row is not None
    assert row["drops"] == 2


def test_latest_stats_record_none_when_absent() -> None:
    records = [_boot("said@1"), _decide(form="said@1", question_id="q-001",
                                          action="respond", real_effector="report")]
    assert R.latest_stats_record(records) is None


# --- differential --------------------------------------------------------------------------


def test_differential_agreement_and_disagreement_enumeration() -> None:
    records = [
        # agree: real=report -> respond, would=respond
        _decide(form="said@1", question_id="q-001", action="respond",
                real_effector="report", t=0, p1=0.95),
        # disagree: real=abstain -> abstain, would=gather
        _decide(form="said@1", question_id="q-002", action="gather",
                real_effector="abstain", t=1, p1=0.3),
        # agree: real=gather -> gather, would=gather
        _decide(form="said@1", question_id="q-003", action="gather",
                real_effector="gather", t=2, p1=0.4),
        # disagree: real=ask_clarify -> ask, would=respond
        _decide(form="said@1", question_id="q-004", action="respond",
                real_effector="ask_clarify", t=3, p1=0.91),
    ]
    diff = R.differential(records, "said@1")
    assert diff["n_mapped"] == 4
    assert diff["agreement_overall"] == {"n": 4, "agree": 2, "rate": 0.5}
    assert diff["agreement_per_real_action"]["abstain"] == {"n": 1, "agree": 0, "rate": 0.0}
    assert diff["agreement_per_real_action"]["gather"] == {"n": 1, "agree": 1, "rate": 1.0}
    assert diff["agreement_per_real_action"]["ask"] == {"n": 1, "agree": 0, "rate": 0.0}
    assert diff["agreement_per_real_action"]["respond"] == {"n": 1, "agree": 1, "rate": 1.0}

    disagreements = {d["question_id"]: d for d in diff["disagreements"]}
    assert set(disagreements) == {"q-002", "q-004"}
    d2 = disagreements["q-002"]
    assert d2["t"] == 1
    assert d2["real"] == "abstain"
    assert d2["real_mapped"] == "abstain"
    assert d2["would"] == "gather"
    assert d2["p1"] == 0.3
    assert d2["summary"] == _summary()


def test_differential_unmapped_real_effector_named_and_excluded() -> None:
    records = [
        _decide(form="said@1", question_id="q-001", action="respond",
                real_effector="mystery_effector", t=0),
        _decide(form="said@1", question_id="q-002", action="respond",
                real_effector="report", t=1),
    ]
    diff = R.differential(records, "said@1")
    assert diff["n_mapped"] == 1  # the mystery effector is excluded from the denominator
    assert diff["n_unmapped_real_effector"] == {"mystery_effector": 1}
    assert diff["agreement_overall"] == {"n": 1, "agree": 1, "rate": 1.0}
    assert diff["disagreements"] == []  # never silently promoted to a disagreement either


def test_differential_no_ticks_rate_is_none() -> None:
    diff = R.differential([], "said@1")
    assert diff["agreement_overall"] == {"n": 0, "agree": 0, "rate": None}


# --- contingency tables ----------------------------------------------------------------


def test_contingency_would_abstain_x_actual_wrong() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="abstain",
                          real_effector="abstain"),
        mirror("q-002"): _decide(form="said@1", question_id=mirror("q-002"), action="respond",
                          real_effector="report"),
        mirror("q-003"): _decide(form="said@1", question_id=mirror("q-003"), action="abstain",
                          real_effector="abstain"),
    }
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", bucket="CONFIDENT_WRONG", cause="wrong_value",
                          asserted=True, asserted_correct=False),
        mirror("q-002"): _vector(question_id="q-002", bucket="CORRECT"),
        mirror("q-003"): _vector(question_id="q-003", bucket="CORRECT"),
    }
    cont = R.contingency_tables(terminal, vectors)
    assert cont["n_joined"] == 3
    table = cont["would_abstain_x_actual_wrong"]
    # q-001: would-abstain & actual-wrong; q-002: not-abstain & not-wrong;
    # q-003: would-abstain & not-wrong (a false-positive caution)
    assert table == {
        "would_and_actual": 1, "would_and_not_actual": 1,
        "not_would_and_actual": 0, "not_would_and_not_actual": 1, "n": 3,
    }


def test_contingency_would_gather_x_actual_miss_narrow_cause() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="gather",
                          real_effector="abstain"),
        mirror("q-002"): _decide(form="said@1", question_id=mirror("q-002"), action="respond",
                          real_effector="report"),
    }
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", bucket="WRONGLY_WITHHELD",
                          cause="retrieval_miss", asserted=False, asserted_correct=False),
        mirror("q-002"): _vector(question_id="q-002", bucket="CORRECT"),
    }
    cont = R.contingency_tables(terminal, vectors)
    table = cont["would_gather_x_actual_miss"]
    assert table["would_and_actual"] == 1
    assert table["n"] == 2


def test_contingency_miss_excludes_extraction_and_pooling_loss() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="gather",
                          real_effector="abstain"),
    }
    # WRONGLY_WITHHELD but NOT retrieval_miss: must not count as "actual-miss" for the
    # narrow would-gather contingency (extraction/pooling losses aren't fixed by
    # widening retrieval breadth).
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", bucket="WRONGLY_WITHHELD",
                          cause="extraction_miss", asserted=False, asserted_correct=False),
    }
    cont = R.contingency_tables(terminal, vectors)
    table = cont["would_gather_x_actual_miss"]
    assert table["would_and_actual"] == 0
    assert table["would_and_not_actual"] == 1


# --- realized loss -------------------------------------------------------------------------


def test_utility_table_by_action_is_the_given_posterior_not_a_default() -> None:
    table = R.utility_table_by_action(DEFAULT_U_BAR)
    assert table["respond"] == [-9.0, 1.0]
    assert table["abstain"] == [0.0, 0.0]
    assert table["gather"] == [-0.02, 0.98]   # myopic perfect information, not a pure cost
    assert table["ask"] == [-0.1, 0.9]
    assert "think" not in table  # the internal sentinel row has no "fire" key

    live = R.utility_table_by_action(LIVE_U_BAR)
    assert live["respond"] == [-5.9395, 1.0]  # the SAME action, a materially different table
    assert live != table


def test_realized_loss_arithmetic_precise_under_the_declared_u_bar() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="abstain",
                          real_effector="report"),
        mirror("q-002"): _decide(form="said@1", question_id=mirror("q-002"), action="respond",
                          real_effector="report"),
    }
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", bucket="CONFIDENT_WRONG",
                          asserted=True, asserted_correct=False),
        mirror("q-002"): _vector(question_id="q-002", bucket="CORRECT",
                          asserted=True, asserted_correct=True),
    }
    rl = R.realized_loss(terminal, vectors, u_bar=DEFAULT_U_BAR)
    # real losses: q-001 loss(respond, y=0)=9.0 ; q-002 loss(respond, y=1)=-1.0 -> mean 4.0
    assert rl["real_policy"]["mean_loss"] == 4.0
    # would losses: q-001 loss(abstain, y=0)=0.0 ; q-002 loss(respond, y=1)=-1.0 -> mean -0.5
    assert rl["would_policy"]["mean_loss"] == -0.5

    # I1: the SAME rows under the LIVE posterior cost materially less — a wrong assert is
    # -5.9395, not -9.0. Scoring under the default overstated it by ~50%, against a table no
    # live shadow ever decided under.
    live = R.realized_loss(terminal, vectors, u_bar=LIVE_U_BAR)
    assert live["real_policy"]["mean_loss"] == round((5.9395 + -1.0) / 2, 4)
    assert live["real_policy"]["mean_loss"] < rl["real_policy"]["mean_loss"]
    assert live["scored_under_boot_u_bar"] is True
    assert live["u_bar_used"] == LIVE_U_BAR


def test_realized_loss_refuses_to_score_without_a_boot_u_bar() -> None:
    """I1: an older log has no u_bar in its boot record. Scoring it under the world's
    fallback table would publish a loss the run never incurred, so the report REFUSES and
    says why — a known unknown, never a fabricated number."""
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                          real_effector="report"),
    }
    vectors = {mirror("q-001"): _vector(question_id="q-001", asserted=True,
                                        asserted_correct=False)}
    rl = R.realized_loss(terminal, vectors, u_bar=None)
    assert rl["scored"] is False
    assert "NOT SCORED" in rl["reason"]
    assert rl["n_decisive"] == 1  # the population is still named — only the scoring refuses
    assert "real_policy" not in rl


def test_realized_loss_excludes_non_decisive_rows() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="abstain",
                          real_effector="abstain"),
    }
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", bucket="RIGHTLY_WITHHELD",
                          cause="unanswerable", asserted=False, asserted_correct=False),
    }
    rl = R.realized_loss(terminal, vectors, u_bar=LIVE_U_BAR)
    assert rl["n_joined"] == 1
    assert rl["n_decisive"] == 0
    assert rl["real_policy"] == {"mean_loss": None, "n": 0}


def test_realized_loss_window_from_timestamps() -> None:
    terminal = {
        mirror("q-001"): _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                          real_effector="report", ts=1000.0),
        mirror("q-002"): _decide(form="said@1", question_id=mirror("q-002"), action="respond",
                          real_effector="report", ts=2000.0),
    }
    vectors = {
        mirror("q-001"): _vector(question_id="q-001", asserted=True, asserted_correct=True),
        mirror("q-002"): _vector(question_id="q-002", asserted=True, asserted_correct=True),
    }
    rl = R.realized_loss(terminal, vectors, u_bar=LIVE_U_BAR)
    assert rl["window"]["from"] < rl["window"]["to"]


# --- n_min honesty -------------------------------------------------------------------------


def test_n_min_honesty_below_bar_named() -> None:
    result = R.n_min_honesty(21)
    assert result["clears"] is False
    assert result["n_min"] == 1000
    assert "BELOW" in result["note"]


def test_n_min_honesty_clears_bar() -> None:
    result = R.n_min_honesty(1500)
    assert result["clears"] is True
    assert "clears" in result["note"]


# --- demand ledger -------------------------------------------------------------------------


def _respond_entry(records: list[dict[str, Any]], forms: list[str]) -> dict[str, Any]:
    ledger = {e["name"]: e for e in R.demand_ledger(records, forms)}
    return ledger["respond_unreachable_p1_ceiling"]


def test_demand_ledger_respond_threshold_is_derived_from_the_boot_u_bar_not_hardcoded() -> None:
    """C3, the headline: the entry used to test p1 against a hard-coded ``P1_CEILING = 0.9``
    and narrate it as "respond needs p1 > 0.9 under the world's declared default
    u_wrong=-9.0" — a claim about a CONSTANT, published as a claim about the system. The
    threshold is a function of the utility posterior, so it is derived from the u_bar the
    boot record actually persisted."""
    records = [
        _boot("said@1", u_bar=LIVE_U_BAR),
        _decide(form="said@1", question_id=mirror("q-001"), action="gather",
                real_effector="gather", p1=0.89),
    ]
    entry = _respond_entry(records, ["said@1"])
    per_form = entry["per_form"]["said@1"]
    assert per_form["u_bar_source"] == "boot record"
    # vs abstain: (0 - -5.9395)/(1 - -5.9395) = 0.8559 — BELOW the engine's own asymptote
    # (0.8918), so "respond can't beat silence" is simply FALSE under the live posterior.
    assert per_form["threshold_vs_abstain"] == pytest.approx(0.8559, abs=1e-4)
    assert per_form["threshold_vs_abstain"] < R.ENGINE_P1_OBSERVED_ASYMPTOTE
    # ...but the engine argmaxes the WHOLE menu, and gather (priced as myopic perfect
    # information) outbids respond until p1 > 0.9942 — above the engine's 0.9 grid ceiling.
    # So the demand still fires, for a DIFFERENT and honestly-named reason.
    assert per_form["threshold_whole_menu"] == pytest.approx(0.9942, abs=1e-4)
    assert per_form["binding_competitor"] == "gather"
    assert per_form["argmax_at_engine_ceiling"] == "gather"
    assert per_form["fires"] is True
    assert entry["fires"] is True


def test_demand_ledger_respond_does_not_fire_when_it_is_actually_reachable() -> None:
    """The entry must be able to NOT fire. With a mild u_wrong the whole-menu threshold drops
    below the engine's ceiling, and the report says so instead of repeating the demand."""
    mild = {**LIVE_U_BAR, "u_wrong": -0.05, "kappa_att": 0.001}
    records = [
        _boot("said@1", u_bar=mild),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report", p1=0.88),
    ]
    entry = _respond_entry(records, ["said@1"])
    assert entry["per_form"]["said@1"]["fires"] is False
    assert entry["fires"] is False
    assert "DOES NOT FIRE" in entry["note"]
    assert "REACHABLE" in entry["note"]


def test_demand_ledger_respond_observed_respond_tick_overrides_the_arithmetic() -> None:
    """If the shadow was actually SEEN to respond, it is reachable — whatever any threshold
    says. Observation beats derivation; and a tick that responded is never counted into a
    "respond couldn't fire" tally."""
    records = [
        _boot("said@1", u_bar=LIVE_U_BAR),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report", p1=0.9),
    ]
    per_form = _respond_entry(records, ["said@1"])["per_form"]["said@1"]
    assert per_form["n_respond_chosen"] == 1
    assert per_form["n_ticks_at_ceiling_without_responding"] == 0
    assert per_form["fires"] is False


def test_demand_ledger_respond_without_a_boot_u_bar_asserts_nothing() -> None:
    records = [
        _boot("said@1", u_bar=None),  # an old log
        _decide(form="said@1", question_id=mirror("q-001"), action="abstain",
                real_effector="abstain", p1=0.9),
    ]
    entry = _respond_entry(records, ["said@1"])
    assert entry["per_form"]["said@1"]["fires"] is None
    assert entry["fires"] is False  # a demand is never claimed on absent evidence
    assert "NOT DETERMINED" in entry["note"]


def test_demand_ledger_ask_is_dominated_by_gather_under_the_live_posterior() -> None:
    """A finding the fixed world made visible: ask and gather have the same payoff shape and
    differ only by cost, so q=|lambda_int| ~ 1.0 against g=|kappa_att| ~ 0.03 makes ask
    unfirable at ANY credence — a consequence of where the exchange rates are sourced."""
    records = [
        _boot("said@1", u_bar=LIVE_U_BAR),
        _decide(form="said@1", question_id=mirror("q-001"), action="gather",
                real_effector="gather", p1=0.5),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1"])}
    entry = ledger["ask_dominated_by_gather"]
    assert entry["fires"] is True
    assert entry["per_form"]["said@1"]["dominated"] is True
    assert entry["count"] == 0  # no tick chose ask, as predicted


def test_demand_ledger_latent_degenerate_when_present() -> None:
    records = [
        _decide(form="latent@1", question_id="q-001", action="abstain",
                real_effector="abstain", sensitivity=False),
        _decide(form="latent@1", question_id="q-002", action="abstain",
                real_effector="abstain", sensitivity=False),
        _decide(form="latent@1", question_id="q-003", action="respond",
                real_effector="report", sensitivity=True),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["latent@1"])}
    entry = ledger["latent_action_degenerate"]
    assert entry["count"] == 2
    assert entry["of"] == 3
    assert entry["distinct_actions_observed"] == ["abstain", "respond"]


def test_demand_ledger_latent_absent_form_named_not_run() -> None:
    ledger = {e["name"]: e for e in R.demand_ledger([], ["said@1"])}
    entry = ledger["latent_action_degenerate"]
    assert entry["count"] == 0
    assert "not run" in entry["note"]


def test_demand_ledger_kary_candidates_counted_once_across_forms() -> None:
    # the SAME live tick (identical summary) shadowed on two forms — must count once,
    # not twice (deduped to the canonical/first-declared form).
    shared_summary = _summary(n_candidates=3)
    records = [
        _decide(form="said@1", question_id="q-001", action="respond",
                real_effector="report", summary=shared_summary),
        _decide(form="latent@1", question_id="q-001", action="respond",
                real_effector="report", summary=shared_summary),
        _decide(form="said@1", question_id="q-002", action="respond",
                real_effector="report", summary=_summary(n_candidates=1)),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1", "latent@1"])}
    entry = ledger["kary_candidates_inexpressible"]
    assert entry["count"] == 1  # only q-001, counted once (on said@1, the canonical form)
    assert entry["of"] == 2  # said@1 has 2 decide ticks


def test_demand_ledger_cold_start_p1_exactly_half() -> None:
    records = [
        _decide(form="said@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.5),
        _decide(form="said@1", question_id="q-002", action="abstain",
                real_effector="abstain", p1=0.51),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1"])}
    entry = ledger["cold_start_feature_insensitivity"]
    assert entry["count"] == 1  # the p1==0.5 secondary/corroborating signal, unchanged


def test_demand_ledger_cold_start_reports_real_n_source_records_from_the_boot_record() -> None:
    # Task 7 review, fix 1: the brief's actual ask (BootSnapshot.n_source_records) is now
    # persisted in the boot record, so the report reads the REAL count — no more
    # "DEVIATION FROM THE BRIEF" substitution.
    records = [
        _boot("said@1", n_source_records=250),
        _decide(form="said@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.5),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1"])}
    entry = ledger["cold_start_feature_insensitivity"]
    assert entry["boot_snapshot_n_source_records"] == {"said@1": 250}
    assert "DEVIATION FROM THE BRIEF" not in entry["note"]


def test_demand_ledger_cold_start_n_source_records_none_without_a_boot_record() -> None:
    # An older log (predates this field) or a form that never wrote a boot record: named
    # honestly as unknown, never fabricated as 0.
    records = [
        _decide(form="said@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.5),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1"])}
    entry = ledger["cold_start_feature_insensitivity"]
    assert entry["boot_snapshot_n_source_records"] == {"said@1": None}


def test_demand_ledger_cold_start_n_source_records_uses_the_latest_boot_per_form() -> None:
    # A respawned form's LATEST boot record wins, not its first (a respawn re-snapshots).
    records = [
        _boot("said@1", ts=100.0, n_source_records=0),
        _boot("said@1", ts=200.0, n_source_records=99),
        _decide(form="said@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.5),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["said@1"])}
    entry = ledger["cold_start_feature_insensitivity"]
    assert entry["boot_snapshot_n_source_records"] == {"said@1": 99}


def test_demand_ledger_no_forms_is_empty_but_safe() -> None:
    ledger = R.demand_ledger([], [])
    names = {e["name"] for e in ledger}
    assert names == {
        "respond_unreachable_p1_ceiling", "ask_dominated_by_gather",
        "latent_action_degenerate", "kary_candidates_inexpressible",
        "cold_start_feature_insensitivity",
    }
    assert all(e["fires"] is False for e in ledger)  # no records => no demand is claimed


# --- provenance ----------------------------------------------------------------------------


def test_provenance_single_identity_not_drifted() -> None:
    records = [
        _boot("said@1", world_digest="digest-1", ts=100.0),
        _boot("said@1", world_digest="digest-1", ts=200.0),  # a same-identity respawn
    ]
    prov = R.provenance(records, ["said@1"])["said@1"]
    assert prov["n_boot_records"] == 2
    assert prov["drifted"] is False
    assert len(prov["distinct_identities"]) == 1


def test_provenance_distinct_identities_flagged_drifted() -> None:
    records = [
        _boot("said@1", world_digest="digest-1", ts=100.0),
        _boot("said@1", world_digest="digest-2", ts=200.0),  # a live-posterior drift
    ]
    prov = R.provenance(records, ["said@1"])["said@1"]
    assert prov["drifted"] is True
    assert len(prov["distinct_identities"]) == 2


def test_provenance_no_boot_records() -> None:
    prov = R.provenance([], ["said@1"])["said@1"]
    assert prov["n_boot_records"] == 0
    assert prov["distinct_identities"] == []
    assert prov["drifted"] is False


# --- build_report / render_md end-to-end --------------------------------------------------


def test_build_report_without_vectors_has_no_grounded_section() -> None:
    records = [
        _boot("said@1"),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, None)
    assert report["forms_declared"] == ["said@1"]
    assert report["grounded"] is None
    assert "said@1" in report["per_form_stats"]
    assert "said@1" in report["differential"]
    assert len(report["demand_ledger"]) == 5
    # no kind:"stats" row in this log -> the honest not-observable note, never zeros.
    assert report["global_counters"]["observable"] is False
    assert report["per_form_stats"]["said@1"]["dead_drops"] is None


def test_build_report_renders_the_global_counters_once_not_per_form() -> None:
    records = [
        _boot("said@1", forms=["said@1", "latent@1"]),
        _boot("latent@1", forms=["said@1", "latent@1"]),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
        _decide(form="latent@1", question_id=mirror("q-001"), action="gather",
                real_effector="report"),
        _stats(drops=4, skips=1, submit_errors=0,
               forms={"said@1": {"dead_drops": 2}, "latent@1": {"dead_drops": 3}}),
    ]
    report = R.build_report(records, None)
    assert report["global_counters"]["drops"] == 4  # once, not once per form
    assert report["per_form_stats"]["said@1"]["dead_drops"] == 2
    assert report["per_form_stats"]["latent@1"]["dead_drops"] == 3
    md = R.render_md(report)
    assert md.count("drops=4") == 1


def test_build_report_grounded_join_bridges_the_two_id_namespaces(tmp_path: Path) -> None:
    """C1 end-to-end, through the REAL derivations on both sides: the shadow's decide record
    carries the MIRROR id (sha256 of the question text); the baseline vector carries the
    CORPUS id (q-001); and only the run's questions file relates them. The join used to be
    structurally impossible — always 0 rows — and the report narrated that as "n=0 is below
    n_min=1000", i.e. as a small sample."""
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [
        _vector(question_id="q-001", asserted=True, asserted_correct=True),
    ])
    records = [
        _boot("said@1", u_bar=LIVE_U_BAR),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, R.load_baseline_vectors(run_dir))
    g = report["grounded"]["said@1"]
    assert g["join"]["n_joined"] == 1
    assert g["contingency"]["n_joined"] == 1
    assert g["realized_loss"]["n_decisive"] == 1
    assert g["realized_loss"]["scored_under_boot_u_bar"] is True
    assert g["realized_loss"]["u_bar_used"] == LIVE_U_BAR  # NOT the world's defaults
    assert g["n_min_honesty"]["clears"] is False


def test_build_report_grounded_empty_join_is_named_not_narrated_as_a_small_sample(
    tmp_path: Path,
) -> None:
    """The exact failure mode: a shadow that saw DIFFERENT questions than the run graded
    joins nothing. That must read as an empty join, not as an under-powered one."""
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [
        _vector(question_id="q-001", asserted=True, asserted_correct=True),
    ])
    records = [
        _boot("said@1", u_bar=LIVE_U_BAR),
        _decide(form="said@1", question_id=mirror("q-004"),  # a question this run never graded
                action="respond", real_effector="report"),
    ]
    report = R.build_report(records, R.load_baseline_vectors(run_dir))
    g = report["grounded"]["said@1"]
    assert g["join"]["n_joined"] == 0
    assert "DISJOINT CORPUS" in g["join"]["note"]
    assert "not a small sample" in g["join"]["note"]
    assert "EMPTY population" in g["n_min_honesty"]["note"]
    assert "NOTHING joined" in g["n_min_honesty"]["note"]


def test_build_report_grounded_refuses_realized_loss_on_a_log_without_u_bar(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [
        _vector(question_id="q-001", asserted=True, asserted_correct=False),
    ])
    records = [
        _boot("said@1", u_bar=None),  # an older log
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, R.load_baseline_vectors(run_dir))
    rl = report["grounded"]["said@1"]["realized_loss"]
    assert rl["scored"] is False
    assert "NOT SCORED" in rl["reason"]


def test_build_report_world_policy_publishes_the_p1_regions(tmp_path: Path) -> None:
    records = [_boot("said@1", u_bar=LIVE_U_BAR)]
    policy = R.build_report(records, None)["world_policy"]["said@1"]
    assert policy["u_bar"] == LIVE_U_BAR
    # under the live posterior: abstain only at the very bottom, gather across the interior,
    # respond only above ~0.994 (which the engine's 0.9 grid cannot reach)
    assert policy["argmax_by_p1"]["0.0"] == "abstain"
    assert policy["argmax_by_p1"]["0.5"] == "gather"
    assert policy["argmax_by_p1"]["0.9"] == "gather"
    assert policy["argmax_by_p1"]["1.0"] == "respond"


def test_build_report_is_reproducible_no_wallclock_field() -> None:
    records = [_boot("said@1"), _decide(form="said@1", question_id=mirror("q-001"),
                                          action="respond", real_effector="report")]
    r1 = R.build_report(records, None)
    r2 = R.build_report(records, None)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_render_md_has_section_headers() -> None:
    records = [
        _boot("said@1"),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, None)
    md = R.render_md(report)
    assert "# Membrane shadow — differential + demand report" in md
    assert "## 1. Per-form stats" in md
    assert "## 2. Differential vs the incumbent" in md
    assert "## 3. Grounded joins" in md
    assert "## 4. Demand ledger" in md
    assert "## 5. Provenance" in md
    assert "### said@1" in md
    assert "Not run: pass `--vectors" in md


def test_render_md_grounded_section_present_when_given(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [_vector(question_id="q-001", asserted=True,
                                          asserted_correct=True)])
    records = [
        _boot("said@1"),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, R.load_baseline_vectors(run_dir))
    md = R.render_md(report)
    assert "n_min honesty" in md
    assert "**Join: 1 rows.**" in md


# --- CLI (main) ------------------------------------------------------------------------


def test_main_writes_report_json_and_md(tmp_path: Path, capsys: Any) -> None:
    shadow_log = tmp_path / "shadow.jsonl"
    _write_jsonl(shadow_log, [
        _boot("said@1"),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ])
    out_dir = tmp_path / "out"
    rc = R.main(["--shadow-log", str(shadow_log), "--out-dir", str(out_dir)])
    assert rc == 0
    report_json = json.loads((out_dir / "report.json").read_text())
    assert report_json["forms_declared"] == ["said@1"]
    assert report_json["grounded"] is None
    md_text = (out_dir / "report.md").read_text()
    assert "Membrane shadow" in md_text
    captured = capsys.readouterr()
    assert "membrane report ->" in captured.out


def test_main_with_vectors_enables_grounded(tmp_path: Path) -> None:
    shadow_log = tmp_path / "shadow.jsonl"
    _write_jsonl(shadow_log, [
        _boot("said@1"),
        _decide(form="said@1", question_id=mirror("q-001"), action="respond",
                real_effector="report"),
    ])
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [_vector(question_id="q-001", asserted=True,
                                          asserted_correct=True)])
    out_dir = tmp_path / "out"
    rc = R.main([
        "--shadow-log", str(shadow_log), "--vectors", str(run_dir), "--out-dir", str(out_dir),
    ])
    assert rc == 0
    report_json = json.loads((out_dir / "report.json").read_text())
    assert report_json["grounded"] is not None


def test_main_default_paths_use_config(monkeypatch: Any, tmp_path: Path) -> None:
    """`--shadow-log`/`--out-dir` default to the configured membrane paths."""
    from life_agent.core import config as C

    kb = tmp_path / "kb"
    monkeypatch.setattr(C, "KB", kb)
    args = R._parse_args([])
    assert args.shadow_log == str(kb / "membrane" / "shadow.jsonl")
    assert args.out_dir == str(kb / "membrane")


# --- M2 advisory: engine EU delta on disagreements + gate pre-emption rows ---------------


def _gate(*, form: str, question_id: str, gate: str, action: str, t: int = 0,
          ts: float = 100.0, p1: float | None = 0.4) -> dict[str, Any]:
    """A `kind: "gate"` row shaped exactly like `MembraneShadow._tick_gate`'s output."""
    readouts: dict[str, Any] = {}
    if p1 is not None:
        readouts["p1"] = p1
    return {
        "event_type": "membrane-shadow", "kind": "gate", "ts": ts,
        "question_id": question_id, "gate": gate, "form": form, "action": action,
        "real_effector": "abstain", "latency_ms": 5.0, "readouts": readouts,
        "summary": _summary(n_candidates=0, leader_credence=None, p_none=None, n_obs=0),
        "t": t,
    }


_EU_U_BAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -4.0,
             "lambda_int": 0.1, "kappa_att": 0.02}


def test_differential_disagreement_rows_carry_engine_eu_delta() -> None:
    records = [
        # disagree at p1=0.3: real=abstain (EU 0), would=gather (EU -0.02 + 0.3 = 0.28)
        _decide(form="said@1", question_id="q-002", action="gather",
                real_effector="abstain", t=1, p1=0.3),
        # disagree at p1=0.91: real=ask_clarify -> ask (EU 0.81), would=respond (EU 0.55)
        _decide(form="said@1", question_id="q-004", action="respond",
                real_effector="ask_clarify", t=3, p1=0.91),
        # disagree with NO p1 readout: unpriceable, named, never guessed
        _decide(form="said@1", question_id="q-005", action="gather",
                real_effector="abstain", t=4, p1=None),
    ]
    diff = R.differential(records, "said@1", u_bar=_EU_U_BAR)
    by_q = {d["question_id"]: d for d in diff["disagreements"]}
    assert by_q["q-002"]["eu_delta"] == 0.28
    assert by_q["q-004"]["eu_delta"] == -0.26
    assert by_q["q-005"]["eu_delta"] is None
    classes = diff["disagreement_eu_by_class"]
    assert classes["abstain->gather"] == {"n": 2, "priced_n": 1, "eu_delta_sum": 0.28}
    assert classes["ask->respond"] == {"n": 1, "priced_n": 1, "eu_delta_sum": -0.26}


def test_differential_without_u_bar_prices_nothing() -> None:
    records = [
        _decide(form="said@1", question_id="q-002", action="gather",
                real_effector="abstain", t=1, p1=0.3),
    ]
    diff = R.differential(records, "said@1")
    assert diff["disagreements"][0]["eu_delta"] is None
    assert diff["disagreement_eu_by_class"]["abstain->gather"] == {
        "n": 1, "priced_n": 0, "eu_delta_sum": None,
    }


def test_gate_advisory_counts_by_gate_and_engine_would_action() -> None:
    records = [
        _gate(form="said@1", question_id="q-001", gate="weak_retrieval", action="gather"),
        _gate(form="said@1", question_id="q-002", gate="weak_retrieval", action="gather"),
        _gate(form="said@1", question_id="q-003", gate="weak_retrieval", action="abstain"),
        _gate(form="said@1", question_id="q-004", gate="executor_down", action="abstain"),
        _gate(form="other@1", question_id="q-005", gate="weak_retrieval", action="gather"),
    ]
    g = R.gate_advisory(records, "said@1")
    assert g["n"] == 4  # the other form's row is not this form's
    assert g["by_gate"]["weak_retrieval"] == {"n": 3, "would": {"abstain": 1, "gather": 2}}
    assert g["by_gate"]["executor_down"] == {"n": 1, "would": {"abstain": 1}}
    assert "pre-empt" in g["note"]  # the i-4 debt is named, not implied


def test_gate_advisory_empty_is_zero_not_a_crash() -> None:
    g = R.gate_advisory([], "said@1")
    assert g["n"] == 0
    assert g["by_gate"] == {}


def test_build_report_includes_gates_and_priced_disagreements() -> None:
    records = [
        _boot("said@1", u_bar=dict(_EU_U_BAR)),
        _decide(form="said@1", question_id="q-002", action="gather",
                real_effector="abstain", t=1, p1=0.3),
        _gate(form="said@1", question_id="q-009", gate="weak_retrieval", action="gather"),
    ]
    report = R.build_report(records)
    assert report["gates"]["said@1"]["n"] == 1
    # the differential is priced under the form's OWN boot u_bar, not a default
    assert report["differential"]["said@1"]["disagreements"][0]["eu_delta"] == 0.28
