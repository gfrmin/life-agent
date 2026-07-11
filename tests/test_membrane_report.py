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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from membrane import report as R

from life_agent.fairfight import records as REC

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
          forms: list[str] | None = None) -> dict[str, Any]:
    return {
        "event_type": "membrane-shadow", "kind": "boot", "ts": ts, "form": form,
        "engine": {"ok": True, "proto": 1, "models": 40, "namespace_bits": 6},
        "binary_sha256": binary_sha256, "forms": forms or [form],
        "world_digest": world_digest, "respawn_count": respawn_count,
    }


def _respawn(form: str, *, ts: float = 100.0, respawn_count: int = 1) -> dict[str, Any]:
    return {
        "event_type": "membrane-shadow", "kind": "respawn", "ts": ts, "form": form,
        "error": "boom", "respawn_count": respawn_count, "max_respawns": 3,
        "permanent": False,
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


def _write_baseline_run(run_dir: Path, vectors: list[dict[str, Any]]) -> None:
    _write_jsonl(run_dir / "arms" / "baseline" / "vectors.jsonl", vectors)


# --- load_shadow_records / load_baseline_vectors ----------------------------------------


def test_load_shadow_records_skips_malformed_and_non_membrane_lines(tmp_path: Path) -> None:
    path = tmp_path / "shadow.jsonl"
    path.write_text(
        json.dumps(_boot("table@1")) + "\n"
        "not json at all\n"
        + json.dumps({"event_type": "something-else", "kind": "boot"}) + "\n"
        + json.dumps(_decide(form="table@1", question_id="q-001", action="respond",
                              real_effector="report")) + "\n",
        encoding="utf-8",
    )
    records = R.load_shadow_records(path)
    assert len(records) == 2
    assert {r["kind"] for r in records} == {"boot", "decide"}


def test_load_shadow_records_missing_file_is_empty(tmp_path: Path) -> None:
    assert R.load_shadow_records(tmp_path / "nope.jsonl") == []


def test_load_baseline_vectors_reads_baseline_arm_and_filters_scored(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    _write_baseline_run(run_dir, [
        _vector(question_id="q-001", status="ok"),
        _vector(question_id="q-002", status="timeout"),  # excluded: infra failure
    ])
    # a non-baseline arm must never leak into the join population
    _write_jsonl(run_dir / "arms" / "competitor" / "vectors.jsonl",
                 [_vector(question_id="q-003", arm="competitor")])
    vectors = R.load_baseline_vectors(run_dir)
    assert set(vectors) == {"q-001"}


def test_load_baseline_vectors_missing_run_dir_is_empty(tmp_path: Path) -> None:
    assert R.load_baseline_vectors(tmp_path / "no-such-run") == {}


# --- declared_forms ----------------------------------------------------------------------


def test_declared_forms_from_boot_record() -> None:
    records = [_boot("latent@1", forms=["table@1", "latent@1"])]
    assert R.declared_forms(records) == ["table@1", "latent@1"]


def test_declared_forms_falls_back_to_form_field_union() -> None:
    records = [_decide(form="table@1", question_id="q-001", action="respond",
                        real_effector="report")]
    assert R.declared_forms(records) == ["table@1"]


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
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report", latency_ms=10.0),
        _decide(form="table@1", question_id="q-002", action="respond",
                real_effector="report", latency_ms=20.0),
        _decide(form="table@1", question_id="q-003", action="abstain",
                real_effector="abstain", latency_ms=30.0, raw_internal=True),
        _decide(form="table@1", question_id="q-004", action="abstain",
                real_effector="abstain", latency_ms=40.0),
        _evidence("table@1"),
        _respawn("table@1"),
    ]
    stats = R.form_stats(records, "table@1")
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
    assert "never" in stats["drops_skips_dead_drops"]


def test_form_stats_empty_form_has_no_denominator_crash() -> None:
    stats = R.form_stats([], "table@1")
    assert stats["n_decide_ticks"] == 0
    assert stats["decide_latency_ms"] == {"p50": None, "p95": None, "n": 0}
    assert stats["raw_internal"] == {"n": 0, "of": 0}


# --- differential --------------------------------------------------------------------------


def test_differential_agreement_and_disagreement_enumeration() -> None:
    records = [
        # agree: real=report -> respond, would=respond
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report", t=0, p1=0.95),
        # disagree: real=abstain -> abstain, would=gather
        _decide(form="table@1", question_id="q-002", action="gather",
                real_effector="abstain", t=1, p1=0.3),
        # agree: real=gather -> gather, would=gather
        _decide(form="table@1", question_id="q-003", action="gather",
                real_effector="gather", t=2, p1=0.4),
        # disagree: real=ask_clarify -> ask, would=respond
        _decide(form="table@1", question_id="q-004", action="respond",
                real_effector="ask_clarify", t=3, p1=0.91),
    ]
    diff = R.differential(records, "table@1")
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
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="mystery_effector", t=0),
        _decide(form="table@1", question_id="q-002", action="respond",
                real_effector="report", t=1),
    ]
    diff = R.differential(records, "table@1")
    assert diff["n_mapped"] == 1  # the mystery effector is excluded from the denominator
    assert diff["n_unmapped_real_effector"] == {"mystery_effector": 1}
    assert diff["agreement_overall"] == {"n": 1, "agree": 1, "rate": 1.0}
    assert diff["disagreements"] == []  # never silently promoted to a disagreement either


def test_differential_no_ticks_rate_is_none() -> None:
    diff = R.differential([], "table@1")
    assert diff["agreement_overall"] == {"n": 0, "agree": 0, "rate": None}


# --- contingency tables ----------------------------------------------------------------


def test_contingency_would_abstain_x_actual_wrong() -> None:
    terminal = {
        "q-001": _decide(form="table@1", question_id="q-001", action="abstain",
                          real_effector="abstain"),
        "q-002": _decide(form="table@1", question_id="q-002", action="respond",
                          real_effector="report"),
        "q-003": _decide(form="table@1", question_id="q-003", action="abstain",
                          real_effector="abstain"),
    }
    vectors = {
        "q-001": _vector(question_id="q-001", bucket="CONFIDENT_WRONG", cause="wrong_value",
                          asserted=True, asserted_correct=False),
        "q-002": _vector(question_id="q-002", bucket="CORRECT"),
        "q-003": _vector(question_id="q-003", bucket="CORRECT"),
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
        "q-001": _decide(form="table@1", question_id="q-001", action="gather",
                          real_effector="abstain"),
        "q-002": _decide(form="table@1", question_id="q-002", action="respond",
                          real_effector="report"),
    }
    vectors = {
        "q-001": _vector(question_id="q-001", bucket="WRONGLY_WITHHELD",
                          cause="retrieval_miss", asserted=False, asserted_correct=False),
        "q-002": _vector(question_id="q-002", bucket="CORRECT"),
    }
    cont = R.contingency_tables(terminal, vectors)
    table = cont["would_gather_x_actual_miss"]
    assert table["would_and_actual"] == 1
    assert table["n"] == 2


def test_contingency_miss_excludes_extraction_and_pooling_loss() -> None:
    terminal = {
        "q-001": _decide(form="table@1", question_id="q-001", action="gather",
                          real_effector="abstain"),
    }
    # WRONGLY_WITHHELD but NOT retrieval_miss: must not count as "actual-miss" for the
    # narrow would-gather contingency (extraction/pooling losses aren't fixed by
    # widening retrieval breadth).
    vectors = {
        "q-001": _vector(question_id="q-001", bucket="WRONGLY_WITHHELD",
                          cause="extraction_miss", asserted=False, asserted_correct=False),
    }
    cont = R.contingency_tables(terminal, vectors)
    table = cont["would_gather_x_actual_miss"]
    assert table["would_and_actual"] == 0
    assert table["would_and_not_actual"] == 1


# --- realized loss -------------------------------------------------------------------------


def test_utility_table_by_action_matches_world_defaults() -> None:
    table = R.utility_table_by_action()
    assert table["gather"] == [-0.02, -0.02]
    assert table["ask"] == [-0.1, -0.1]
    assert table["abstain"] == [0.0, 0.0]
    assert table["respond"] == [-9.0, 1.0]
    assert "think" not in table  # the internal sentinel row has no "fire" key


def test_realized_loss_arithmetic_precise() -> None:
    terminal = {
        "q-001": _decide(form="table@1", question_id="q-001", action="abstain",
                          real_effector="report"),
        "q-002": _decide(form="table@1", question_id="q-002", action="respond",
                          real_effector="report"),
    }
    vectors = {
        "q-001": _vector(question_id="q-001", bucket="CONFIDENT_WRONG",
                          asserted=True, asserted_correct=False),
        "q-002": _vector(question_id="q-002", bucket="CORRECT",
                          asserted=True, asserted_correct=True),
    }
    rl = R.realized_loss(terminal, vectors)
    # real losses: q-001 loss(respond, y=0)=9.0 ; q-002 loss(respond, y=1)=-1.0 -> mean 4.0
    assert rl["real_policy"]["mean_loss"] == 4.0
    # would losses: q-001 loss(abstain, y=0)=0.0 ; q-002 loss(respond, y=1)=-1.0 -> mean -0.5
    assert rl["would_policy"]["mean_loss"] == -0.5


def test_realized_loss_excludes_non_decisive_rows() -> None:
    terminal = {
        "q-001": _decide(form="table@1", question_id="q-001", action="abstain",
                          real_effector="abstain"),
    }
    vectors = {
        "q-001": _vector(question_id="q-001", bucket="RIGHTLY_WITHHELD", cause="unanswerable",
                          asserted=False, asserted_correct=False),
    }
    rl = R.realized_loss(terminal, vectors)
    assert rl["n_joined"] == 1
    assert rl["n_decisive"] == 0
    assert rl["real_policy"] == {"mean_loss": None, "n": 0}


def test_realized_loss_window_from_timestamps() -> None:
    terminal = {
        "q-001": _decide(form="table@1", question_id="q-001", action="respond",
                          real_effector="report", ts=1000.0),
        "q-002": _decide(form="table@1", question_id="q-002", action="respond",
                          real_effector="report", ts=2000.0),
    }
    vectors = {
        "q-001": _vector(question_id="q-001", asserted=True, asserted_correct=True),
        "q-002": _vector(question_id="q-002", asserted=True, asserted_correct=True),
    }
    rl = R.realized_loss(terminal, vectors)
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


def test_demand_ledger_p1_ceiling_counted_at_exactly_0_9() -> None:
    records = [
        _decide(form="table@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.9),
        _decide(form="table@1", question_id="q-002", action="abstain",
                real_effector="abstain", p1=0.89),
        _decide(form="table@1", question_id="q-003", action="abstain",
                real_effector="abstain", p1=None),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["table@1"])}
    entry = ledger["respond_unreachable_p1_ceiling"]
    assert entry["count"] == 1
    assert entry["of"] == 3
    assert entry["per_form"]["table@1"] == {"n": 1, "of": 3}


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
    ledger = {e["name"]: e for e in R.demand_ledger([], ["table@1"])}
    entry = ledger["latent_action_degenerate"]
    assert entry["count"] == 0
    assert "not run" in entry["note"]


def test_demand_ledger_kary_candidates_counted_once_across_forms() -> None:
    # the SAME live tick (identical summary) shadowed on two forms — must count once,
    # not twice (deduped to the canonical/first-declared form).
    shared_summary = _summary(n_candidates=3)
    records = [
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report", summary=shared_summary),
        _decide(form="latent@1", question_id="q-001", action="respond",
                real_effector="report", summary=shared_summary),
        _decide(form="table@1", question_id="q-002", action="respond",
                real_effector="report", summary=_summary(n_candidates=1)),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["table@1", "latent@1"])}
    entry = ledger["kary_candidates_inexpressible"]
    assert entry["count"] == 1  # only q-001, counted once (on table@1, the canonical form)
    assert entry["of"] == 2  # table@1 has 2 decide ticks


def test_demand_ledger_cold_start_p1_exactly_half() -> None:
    records = [
        _decide(form="table@1", question_id="q-001", action="abstain",
                real_effector="abstain", p1=0.5),
        _decide(form="table@1", question_id="q-002", action="abstain",
                real_effector="abstain", p1=0.51),
    ]
    ledger = {e["name"]: e for e in R.demand_ledger(records, ["table@1"])}
    entry = ledger["cold_start_feature_insensitivity"]
    assert entry["count"] == 1
    assert "not persist" in entry["note"] or "never" in entry["note"]


def test_demand_ledger_no_forms_is_empty_but_safe() -> None:
    ledger = R.demand_ledger([], [])
    names = {e["name"] for e in ledger}
    assert names == {
        "respond_unreachable_p1_ceiling", "latent_action_degenerate",
        "kary_candidates_inexpressible", "cold_start_feature_insensitivity",
    }


# --- provenance ----------------------------------------------------------------------------


def test_provenance_single_identity_not_drifted() -> None:
    records = [
        _boot("table@1", world_digest="digest-1", ts=100.0),
        _boot("table@1", world_digest="digest-1", ts=200.0),  # a same-identity respawn
    ]
    prov = R.provenance(records, ["table@1"])["table@1"]
    assert prov["n_boot_records"] == 2
    assert prov["drifted"] is False
    assert len(prov["distinct_identities"]) == 1


def test_provenance_distinct_identities_flagged_drifted() -> None:
    records = [
        _boot("table@1", world_digest="digest-1", ts=100.0),
        _boot("table@1", world_digest="digest-2", ts=200.0),  # a live-posterior drift
    ]
    prov = R.provenance(records, ["table@1"])["table@1"]
    assert prov["drifted"] is True
    assert len(prov["distinct_identities"]) == 2


def test_provenance_no_boot_records() -> None:
    prov = R.provenance([], ["table@1"])["table@1"]
    assert prov["n_boot_records"] == 0
    assert prov["distinct_identities"] == []
    assert prov["drifted"] is False


# --- build_report / render_md end-to-end --------------------------------------------------


def test_build_report_without_vectors_has_no_grounded_section() -> None:
    records = [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report"),
    ]
    report = R.build_report(records, None)
    assert report["forms_declared"] == ["table@1"]
    assert report["grounded"] is None
    assert "table@1" in report["per_form_stats"]
    assert "table@1" in report["differential"]
    assert len(report["demand_ledger"]) == 4


def test_build_report_with_vectors_has_grounded_section() -> None:
    records = [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report"),
    ]
    vectors = {
        "q-001": _vector(question_id="q-001", asserted=True, asserted_correct=True),
    }
    report = R.build_report(records, vectors)
    assert report["grounded"] is not None
    g = report["grounded"]["table@1"]
    assert g["contingency"]["n_joined"] == 1
    assert g["realized_loss"]["n_decisive"] == 1
    assert g["n_min_honesty"]["clears"] is False


def test_build_report_is_reproducible_no_wallclock_field() -> None:
    records = [_boot("table@1"), _decide(form="table@1", question_id="q-001",
                                          action="respond", real_effector="report")]
    r1 = R.build_report(records, None)
    r2 = R.build_report(records, None)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


def test_render_md_has_section_headers() -> None:
    records = [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
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
    assert "### table@1" in md
    assert "Not run: pass `--vectors" in md


def test_render_md_grounded_section_present_when_given() -> None:
    records = [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report"),
    ]
    vectors = {"q-001": _vector(question_id="q-001", asserted=True, asserted_correct=True)}
    report = R.build_report(records, vectors)
    md = R.render_md(report)
    assert "n_min honesty" in md


# --- CLI (main) ------------------------------------------------------------------------


def test_main_writes_report_json_and_md(tmp_path: Path, capsys: Any) -> None:
    shadow_log = tmp_path / "shadow.jsonl"
    _write_jsonl(shadow_log, [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
                real_effector="report"),
    ])
    out_dir = tmp_path / "out"
    rc = R.main(["--shadow-log", str(shadow_log), "--out-dir", str(out_dir)])
    assert rc == 0
    report_json = json.loads((out_dir / "report.json").read_text())
    assert report_json["forms_declared"] == ["table@1"]
    assert report_json["grounded"] is None
    md_text = (out_dir / "report.md").read_text()
    assert "Membrane shadow" in md_text
    captured = capsys.readouterr()
    assert "membrane report ->" in captured.out


def test_main_with_vectors_enables_grounded(tmp_path: Path) -> None:
    shadow_log = tmp_path / "shadow.jsonl"
    _write_jsonl(shadow_log, [
        _boot("table@1"),
        _decide(form="table@1", question_id="q-001", action="respond",
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
