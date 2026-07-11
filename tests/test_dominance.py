"""Unit tests for the dominance analysis package (``scripts/dominance/``).

Hermetic: no real fair-fight run, no LLM, no network. Every test builds synthetic
``OutcomeVector`` rows via ``life_agent.fairfight.records`` (the same validated
construction path production code uses) or hand-built cell/point dicts. The
end-to-end test drives ``run_dominance.run`` over a ``tmp_path`` run directory with two
synthetic arms.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_dominance.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from dominance import loss_triage as LT
from dominance import pareto as PA
from dominance import profiles as PR
from dominance import run_dominance as RD
from dominance import utility as U
from dominance import winmap as W

from life_agent.fairfight import records as REC

BALANCED = PR.PRESETS["balanced"]  # reward=1.0 lam=1.0 q=0.02 harm=1.0 w_time=0.014


def _vector(**overrides: Any) -> dict[str, Any]:
    """One ``OutcomeVector`` row, JSON-safe (``records.to_json`` shape) — built through
    the real dataclass so every fixture obeys the record's own vocabulary checks."""
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


# --- profiles.py: drift gate ----------------------------------------------------------


def test_presets_frozen() -> None:
    assert {
        "cost-saver": PR.Profile(reward=0.02, lam=0.25, q=0.05, harm=1.0, w_time=0.002),
        "balanced": PR.Profile(reward=1.0, lam=1.0, q=0.02, harm=1.0, w_time=0.014),
        "quality-first": PR.Profile(reward=5.0, lam=2.0, q=0.1, harm=2.0, w_time=0.014),
        "speed-first": PR.Profile(reward=1.0, lam=1.0, q=0.5, harm=1.0, w_time=0.05),
    } == PR.PRESETS


def test_personas_frozen() -> None:
    assert {
        "indie-hacker": PR.Profile(reward=0.02, lam=0.25, q=0.02, harm=0.25, w_time=0.002),
        "startup-balanced": PR.Profile(reward=1.0, lam=1.0, q=0.02, harm=1.0, w_time=0.014),
        "regulated-enterprise": PR.Profile(reward=2.0, lam=2.0, q=0.02, harm=2.5, w_time=0.014),
        "fintech-safety": PR.Profile(reward=5.0, lam=2.0, q=0.02, harm=3.0, w_time=0.014),
        "quality-research": PR.Profile(reward=5.0, lam=2.0, q=0.02, harm=2.0, w_time=0.014),
    } == PR.PERSONAS


def test_realistic_region_frozen() -> None:
    assert PR.REALISTIC_REGION == {
        "harm": (0.5, 3.0),
        "lam": (0.25, 4.0),
        "weighting": "uniform",
        "sensitivity": "persona",
        "excludes": "harm < 0.25",
    }


def test_in_realistic_region_membership() -> None:
    in_region = {
        name for name, p in {**PR.PRESETS, **PR.PERSONAS}.items() if PR.in_realistic_region(p)
    }
    assert in_region == {
        "cost-saver", "balanced", "quality-first", "speed-first",
        "startup-balanced", "regulated-enterprise", "fintech-safety", "quality-research",
    }
    assert "indie-hacker" not in in_region  # harm=0.25 < the region's 0.5 floor


# --- utility.py: question_utility, one term at a time ----------------------------------


def test_question_utility_correct_reward_term() -> None:
    v = _vector(bucket="CORRECT", asks_issued=0, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(1.0)


def test_question_utility_confident_wrong_harm_term() -> None:
    v = _vector(bucket="CONFIDENT_WRONG", asks_issued=0, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(-1.0)


def test_question_utility_wrongly_withheld_lam_reward_term() -> None:
    v = _vector(bucket="WRONGLY_WITHHELD", asks_issued=0, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(-1.0)  # -lam·reward = -1·1


def test_question_utility_rightly_withheld_and_scoped_are_neutral() -> None:
    for bucket in ("RIGHTLY_WITHHELD", "SCOPED"):
        v = _vector(bucket=bucket, asks_issued=0, latency_s=0.0, cost_usd=None)
        assert U.question_utility(BALANCED, v) == pytest.approx(0.0)


def test_question_utility_ask_penalty_term() -> None:
    v = _vector(bucket="RIGHTLY_WITHHELD", asks_issued=1, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(-0.02)
    v2 = _vector(bucket="RIGHTLY_WITHHELD", asks_issued=3, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v2) == pytest.approx(-0.02)  # indicator, not a count


def test_question_utility_latency_term() -> None:
    v = _vector(bucket="RIGHTLY_WITHHELD", asks_issued=0, latency_s=2.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(-0.028)  # -0.014·2


def test_question_utility_cost_term() -> None:
    v = _vector(bucket="RIGHTLY_WITHHELD", asks_issued=0, latency_s=0.0, cost_usd=0.05)
    assert U.question_utility(BALANCED, v) == pytest.approx(-0.05)


def test_question_utility_cost_none_treated_as_zero() -> None:
    v = _vector(bucket="RIGHTLY_WITHHELD", asks_issued=0, latency_s=0.0, cost_usd=None)
    assert U.question_utility(BALANCED, v) == pytest.approx(0.0)


def test_question_utility_all_terms_combined() -> None:
    v = _vector(bucket="CORRECT", asks_issued=1, latency_s=2.0, cost_usd=0.1)
    expected = 1.0 - 0.02 - 0.014 * 2.0 - 0.1
    assert U.question_utility(BALANCED, v) == pytest.approx(expected)


def test_welfare_sums_question_utility() -> None:
    vs = [
        _vector(question_id="q-1", bucket="CORRECT", asks_issued=0, latency_s=0.0, cost_usd=None),
        _vector(question_id="q-2", bucket="CONFIDENT_WRONG", asks_issued=0, latency_s=0.0,
                cost_usd=None),
    ]
    assert U.welfare(BALANCED, vs) == pytest.approx(0.0)  # +1.0 (correct) - 1.0 (harm)


# --- winmap.py: the copied tie-band verdict ---------------------------------------------


def test_verdict_win_just_outside_band() -> None:
    scale = 100.0
    band = max(W.EPS_ABS, W.EPS_REL * scale)  # 0.5
    assert W._verdict(band + 1e-6, scale) == "win"


def test_verdict_tie_at_and_just_inside_band() -> None:
    scale = 100.0
    band = max(W.EPS_ABS, W.EPS_REL * scale)
    assert W._verdict(band, scale) == "tie"  # boundary itself: not strictly > band
    assert W._verdict(band - 1e-6, scale) == "tie"


def test_verdict_loss_just_outside_band() -> None:
    scale = 100.0
    band = max(W.EPS_ABS, W.EPS_REL * scale)
    assert W._verdict(-(band + 1e-6), scale) == "loss"


def test_verdict_tie_just_inside_negative_band() -> None:
    scale = 100.0
    band = max(W.EPS_ABS, W.EPS_REL * scale)
    assert W._verdict(-(band - 1e-6), scale) == "tie"


def test_verdict_uses_eps_abs_floor_at_tiny_scale() -> None:
    scale = 1e-12  # EPS_REL·scale << EPS_ABS: the floor is EPS_ABS
    assert max(W.EPS_ABS, W.EPS_REL * scale) == W.EPS_ABS
    assert W._verdict(W.EPS_ABS * 2, scale) == "win"
    assert W._verdict(W.EPS_ABS / 2, scale) == "tie"


def test_build_cells_scenario_filtering_and_cell_source() -> None:
    arms = {
        "x": [
            _vector(question_id="q-1", answerable=True, bucket="CORRECT", cost_status="measured"),
            _vector(question_id="q-2", answerable=False, bucket="CORRECT", cost_status="estimated"),
        ],
        "y": [
            _vector(question_id="q-1", answerable=True, bucket="CONFIDENT_WRONG",
                    cost_status="measured"),
            _vector(question_id="q-2", answerable=False, bucket="CONFIDENT_WRONG",
                    cost_status="measured"),
        ],
    }
    cells = W.build_cells(arms, {"balanced": BALANCED})
    by_key = {(c["arm_a"], c["arm_b"], c["scenario"]): c for c in cells}
    assert by_key[("x", "y", "answerable")]["n_questions"] == 1
    assert by_key[("x", "y", "unanswerable")]["n_questions"] == 1
    assert by_key[("x", "y", "all")]["n_questions"] == 2
    # "all" touches q-2, whose x-row is cost_status=estimated -> the cell is modelled.
    assert by_key[("x", "y", "all")]["cell_source"] == "modelled"
    # "answerable" only touches q-1, both measured -> measured.
    assert by_key[("x", "y", "answerable")]["cell_source"] == "measured"
    # ordered pairs: (y, x) exists too, with the verdict flipped.
    assert ("y", "x", "all") in by_key
    assert by_key[("x", "y", "all")]["verdict"] != by_key[("y", "x", "all")]["verdict"]


def test_build_cells_hard_fails_on_mismatched_scored_question_id_sets() -> None:
    # final-review MINOR: an asymmetric infra failure between two arms (one answered
    # q-2, the other's q-2 row was excluded as scored — simulated here directly with
    # disjoint question sets) makes a welfare/frontier/loss comparison meaningless; this
    # must raise loudly, not silently compute a comparison over mismatched populations.
    arms = {
        "x": [_vector(question_id="q-1", bucket="CORRECT"),
              _vector(question_id="q-2", bucket="CORRECT")],
        "y": [_vector(question_id="q-1", bucket="CORRECT")],  # missing q-2
    }
    with pytest.raises(ValueError, match="DIFFERENT scored question_id sets"):
        W.build_cells(arms, {"balanced": BALANCED})


def test_pair_tally_splits_measured_and_modelled() -> None:
    cells = [
        {"arm_a": "x", "arm_b": "y", "verdict": "win", "cell_source": "measured"},
        {"arm_a": "x", "arm_b": "y", "verdict": "loss", "cell_source": "modelled"},
    ]
    t = W.pair_tally(cells)[("x", "y")]
    assert t["overall"]["n"] == 2
    assert t["measured"] == {"n": 1, "win": 1, "tie": 0, "loss": 0,
                              "weak_dominance": 1.0, "strict_win": 1.0}
    assert t["modelled"] == {"n": 1, "win": 0, "tie": 0, "loss": 1,
                              "weak_dominance": 0.0, "strict_win": 0.0}


def test_region_dominance_filters_scenario_and_profile_membership() -> None:
    cells = [
        {"arm_a": "x", "arm_b": "y", "profile": "balanced", "scenario": "all", "verdict": "win"},
        {"arm_a": "x", "arm_b": "y", "profile": "indie-hacker", "scenario": "all",
         "verdict": "loss"},
        {"arm_a": "x", "arm_b": "y", "profile": "balanced", "scenario": "answerable",
         "verdict": "loss"},
    ]
    result = W.region_dominance(cells, {"balanced"}, scenario="all")
    assert result[("x", "y")] == {"n": 1, "win": 1, "tie": 0, "loss": 0,
                                   "weak_dominance": 1.0, "strict_win": 1.0}


# --- pareto.py: frontier on hand-built points -------------------------------------------


def test_frontier_dominated_point_excluded() -> None:
    points = {"a": (0.5, -1.0, -1.0, -1.0), "b": (0.9, -0.5, -0.5, -0.5)}  # b dominates a
    assert PA.frontier(points) == {"b"}


def test_frontier_non_dominated_tradeoff_keeps_both() -> None:
    points = {"a": (0.9, -2.0, -1.0, -1.0), "b": (0.5, -0.5, -1.0, -1.0)}  # tradeoff
    assert PA.frontier(points) == {"a", "b"}


def test_frontier_tie_on_all_axes_keeps_both() -> None:
    points = {"a": (0.5, -1.0, -1.0, -1.0), "b": (0.5, -1.0, -1.0, -1.0)}
    assert PA.frontier(points) == {"a", "b"}


def test_frontier_three_arms_one_dominated() -> None:
    points = {
        "a": (0.9, -1.0, -1.0, -1.0),
        "b": (0.5, -2.0, -2.0, -2.0),  # dominated by both a and c
        "c": (0.9, -1.0, -0.5, -1.0),  # weakly dominates a (equal 3 axes, strictly > latency)
    }
    frontier = PA.frontier(points)
    assert frontier == {"c"}


def test_build_point_cost_missing_and_attention_fallback() -> None:
    vs = [
        _vector(question_id="q-1", bucket="CORRECT", cost_usd=0.1, latency_s=1.0,
                asks_issued=1, gather_rounds=2, tool_calls=None),
        _vector(question_id="q-2", bucket="CONFIDENT_WRONG", cost_usd=None, latency_s=3.0,
                asks_issued=0, gather_rounds=None, tool_calls=4),
    ]
    point, n_missing = PA.build_point(vs)
    correct_rate, neg_cost, neg_latency, neg_attention = point
    assert correct_rate == pytest.approx(0.5)
    assert neg_cost == pytest.approx(-0.1)  # only q-1's cost counted
    assert n_missing == 1  # q-2's cost_usd is None — reported, not silently zeroed
    assert neg_latency == pytest.approx(-2.0)  # mean(1.0, 3.0)
    # q-1: asks(1) + gather_rounds(2) = 3; q-2: asks(0) + tool_calls(4, gather is None) = 4
    assert neg_attention == pytest.approx(-7.0)


# --- loss_triage.py: top-5 ordering + hard-fail + zero-loss flag ------------------------


def test_triage_loss_cell_top5_ordering_and_truncation() -> None:
    cell = {"arm_a": "a", "arm_b": "b", "profile": "balanced", "scenario": "all"}
    costs = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]  # 6 questions, only top 5 |delta| kept
    rows_a = [
        _vector(question_id=f"q-{i}", bucket="RIGHTLY_WITHHELD", cost_usd=c,
                asks_issued=0, latency_s=0.0)
        for i, c in enumerate(costs, start=1)
    ]
    rows_b = [
        _vector(question_id=f"q-{i}", bucket="RIGHTLY_WITHHELD", cost_usd=None,
                asks_issued=0, latency_s=0.0)
        for i in range(1, 7)
    ]
    top5 = LT.triage_loss_cell(cell, rows_a, rows_b)
    assert [r["question_id"] for r in top5] == ["q-6", "q-5", "q-4", "q-3", "q-2"]
    assert top5[0]["delta_utility"] == pytest.approx(-0.06)
    assert top5[0]["arm_a_cost_usd"] == pytest.approx(0.06)
    assert top5[0]["arm_b_cost_usd"] is None


def test_triage_loss_cell_hard_fails_on_zero_contributing_questions() -> None:
    cell = {"arm_a": "a", "arm_b": "b", "profile": "balanced", "scenario": "all"}
    rows_a = [_vector(question_id="q-1")]
    rows_b = [_vector(question_id="q-2")]  # disjoint question_ids -> zero overlap
    with pytest.raises(ValueError, match="zero contributing questions"):
        LT.triage_loss_cell(cell, rows_a, rows_b)


def test_build_loss_report_zero_losses_flag() -> None:
    cells = [
        {"arm_a": "a", "arm_b": "b", "profile": "balanced", "scenario": "all", "verdict": "win"},
    ]
    sections, zero_losses = LT.build_loss_report(cells, {"a": [], "b": []})
    assert sections == []
    assert zero_losses is True
    md = LT.loss_map_md(sections, zero_losses)
    assert LT.ZERO_LOSS_FLAG in md


def test_build_loss_report_hard_fails_when_loss_cell_has_no_questions() -> None:
    cells = [
        {"arm_a": "a", "arm_b": "b", "profile": "balanced", "scenario": "all", "verdict": "loss"},
    ]
    with pytest.raises(ValueError, match="zero contributing questions"):
        LT.build_loss_report(cells, {"a": [], "b": []})


def test_loss_map_md_renders_sections_when_not_empty() -> None:
    cell = {"arm_a": "a", "arm_b": "b", "profile": "balanced", "scenario": "all",
            "verdict": "loss", "welfare_a": -1.0, "welfare_b": 0.0, "regret": -1.0,
            "cell_source": "measured", "n_questions": 1}
    top_questions = [{
        "question_id": "q-1", "delta_utility": -1.0,
        "arm_a_bucket": "CONFIDENT_WRONG", "arm_a_cost_usd": 0.01, "arm_a_latency_s": 1.0,
        "arm_b_bucket": "CORRECT", "arm_b_cost_usd": 0.02, "arm_b_latency_s": 2.0,
    }]
    md = LT.loss_map_md([{"cell": cell, "top_questions": top_questions}], False)
    assert "a vs b" in md
    assert "q-1" in md
    assert LT.ZERO_LOSS_FLAG not in md


# --- run_dominance.py: end-to-end over a tmp run dir -------------------------------------


def _write_arm_vectors(
    run_dir: Path, arm: str, bucket: str, cost: float, latency: float,
    *, extra_rows: list[dict[str, Any]] | None = None,
) -> None:
    path = run_dir / "arms" / arm / "vectors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    questions = [("q-1", True), ("q-2", True), ("q-3", False), ("q-4", False)]
    with path.open("w", encoding="utf-8") as f:
        for qid, answerable in questions:
            row = _vector(question_id=qid, answerable=answerable, arm=arm, bucket=bucket,
                          cost_usd=cost, latency_s=latency, cost_status="measured")
            f.write(json.dumps(row) + "\n")
        for row in extra_rows or []:
            f.write(json.dumps(row) + "\n")


def test_run_dominance_end_to_end(tmp_path: Path) -> None:
    run_dir = tmp_path / "ff-test-run"
    _write_arm_vectors(run_dir, "inprocess", "CORRECT", 0.01, 0.5)
    _write_arm_vectors(run_dir, "competitor", "CONFIDENT_WRONG", 0.02, 1.0)

    result = RD.run(run_dir)

    out_dir = run_dir / "dominance"
    assert result["out_dir"] == out_dir
    assert result["arms"] == ["competitor", "inprocess"]
    assert result["frontier"] == ["inprocess"]  # strictly better on every axis
    assert result["zero_losses"] is False
    for name in ("cells.json", "frontier.json", "LOSS_MAP.md", "summary.md"):
        assert (out_dir / name).exists()

    # final-review CRITICAL-2: cells.json is now a headline+cells object, not a bare list.
    cells_payload = json.loads((out_dir / "cells.json").read_text())
    assert cells_payload["n_excluded_infra"] == {"inprocess": 0, "competitor": 0}
    assert cells_payload["n_total"] == {"inprocess": 4, "competitor": 4}
    cells = cells_payload["cells"]
    assert len(cells) == 2 * len(W.all_profiles()) * len(W.SCENARIOS)  # 2 ordered pairs
    loss_cells = [c for c in cells if c["verdict"] == "loss"]
    assert loss_cells  # competitor loses to inprocess on every profile/scenario
    assert all(c["arm_a"] == "competitor" and c["arm_b"] == "inprocess" for c in loss_cells)

    frontier_json = json.loads((out_dir / "frontier.json").read_text())
    assert frontier_json["frontier"] == ["inprocess"]
    assert frontier_json["n_missing_cost"] == {"inprocess": 0, "competitor": 0}

    loss_map = (out_dir / "LOSS_MAP.md").read_text()
    assert "inprocess" in loss_map and "competitor" in loss_map
    assert LT.ZERO_LOSS_FLAG not in loss_map

    summary = (out_dir / "summary.md").read_text()
    assert U.FORMULA in summary
    assert "inprocess" in summary and "competitor" in summary
    assert "**[frontier]**" in summary
    assert "Excluded rows" in summary
    # final-review IMPORTANT-5 item 2: the attention-axis note under the frontier.
    assert "Attention = asks_issued" in summary
    assert "gather_tiers" in summary and "search" in summary


def test_run_dominance_requires_at_least_two_arms(tmp_path: Path) -> None:
    run_dir = tmp_path / "ff-one-arm"
    _write_arm_vectors(run_dir, "inprocess", "CORRECT", 0.01, 0.5)
    with pytest.raises(SystemExit, match="needs >=2 arms"):
        RD.run(run_dir)


# --- final-review CRITICAL-2: infra-failed rows never reach a scored population --------


def test_run_dominance_excludes_infra_failed_rows_from_frontier_cells_and_loss(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "ff-infra-test"
    # A CONFIDENT_WRONG row with status="error" on the inprocess arm — if it leaked into
    # the scored population, it would drag inprocess's correct_rate down and could even
    # flip which arm wins some cells. It must be excluded entirely.
    infra_row = _vector(
        question_id="q-infra", answerable=True, arm="inprocess", bucket="CONFIDENT_WRONG",
        cost_usd=99.0, latency_s=99.0, cost_status="measured", status="error")
    _write_arm_vectors(run_dir, "inprocess", "CORRECT", 0.01, 0.5, extra_rows=[infra_row])
    _write_arm_vectors(run_dir, "competitor", "CONFIDENT_WRONG", 0.02, 1.0)

    result = RD.run(run_dir)
    assert result["n_excluded_infra"] == {"inprocess": 1, "competitor": 0}

    out_dir = run_dir / "dominance"
    cells_payload = json.loads((out_dir / "cells.json").read_text())
    assert cells_payload["n_excluded_infra"] == {"inprocess": 1, "competitor": 0}
    assert cells_payload["n_total"] == {"inprocess": 5, "competitor": 4}
    # every cell's n_questions reflects the SCORED population (4), never the 5 total —
    # the infra row's bucket/cost/latency never reach a welfare sum.
    assert all(c["n_questions"] == 4 for c in cells_payload["cells"] if c["scenario"] == "all")

    frontier_json = json.loads((out_dir / "frontier.json").read_text())
    # inprocess's correct_rate is still 1.0 (4/4 scored CORRECT) — the infra row's
    # CONFIDENT_WRONG bucket and $99/99s never dragged it down.
    assert frontier_json["points"]["inprocess"][0] == pytest.approx(1.0)

    summary = (out_dir / "summary.md").read_text()
    assert "`inprocess`: 1 excluded of 5 total (4 scored)" in summary


def test_run_dominance_all_infra_failed_rows_for_one_arm_yields_empty_scored_population(
    tmp_path: Path,
) -> None:
    # An edge case worth naming explicitly: every row for an arm is infra-failed -> its
    # scored population is EMPTY. This must not crash the frontier/cells computation
    # (build_point/build_cells both handle n=0 -> correct_rate=0.0, and an empty arm's
    # question_id set trivially matches another empty arm's — but here the OTHER arm is
    # non-empty, so build_cells' mismatch guard (MINOR fix) fires; asserting THAT is the
    # point of this test, not a happy path.
    run_dir = tmp_path / "ff-all-infra-test"
    all_error_rows = [
        _vector(question_id=f"q-{i}", answerable=True, arm="inprocess", bucket="CORRECT",
               cost_usd=0.01, latency_s=0.5, cost_status="measured", status="error")
        for i in range(1, 4)
    ]
    path = run_dir / "arms" / "inprocess" / "vectors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in all_error_rows), encoding="utf-8")
    _write_arm_vectors(run_dir, "competitor", "CORRECT", 0.02, 1.0)

    with pytest.raises(ValueError, match="DIFFERENT scored question_id sets"):
        RD.run(run_dir)
