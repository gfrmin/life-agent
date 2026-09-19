"""r51b X7 — `scripts/membrane/u_wrong_curve.py`: the `u_wrong` sensitivity curve.

Re-scores one held-out run at each grid point of the identified latent `u_wrong` — the commit
policy recomputed at the new bar, the A3 pairing rebuilt, Δ by the Bayesian bootstrap at that
FIXED utility — and reports, per point, the implied commit bar, coverage and selective risk
(the bounded-improvement reading OQ-0' (c') asks for). A sensitivity deliverable, never a
verdict (`M-4`): every atom is the gate's own (`M-7`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "scripts")

import membrane.lattice_replay as LR
import membrane.p3_gate as P3
import membrane.u_wrong_curve as UW

from life_agent.core import decisions as DEC
from life_agent.core import gate as GATE

# `lambda_int` priced high so `ask` never outbids `respond`: the break-even IS the effective
# bar on this fixture (a cheap ask is tested separately)
BASE = {"u_correct": 1.0, "u_wrong": -5.131, "u_abstain": 0.0, "u_hedged": 0.3,
        "u_wrong_scoped": -0.5, "lambda_int": 5.0, "lambda_usd": 0.0}
CHEAP_ASK = {**BASE, "lambda_int": 0.1}


def _rows(p1s: list[float], ys: list[int]) -> list[P3.HeldoutTick]:
    return [P3.HeldoutTick(f"q{i}", 0.9, p, y, respond=LR.commits_respond(BASE, p))
            for i, (p, y) in enumerate(zip(p1s, ys, strict=True))]


def test_grid_is_the_pre_registered_one() -> None:
    assert UW.GRID == (-1.0, -4.0, -5.131, -7.4285, -9.0, -12.0)


def test_u_bar_at_replaces_only_u_wrong() -> None:
    u = UW.u_bar_at(BASE, -9.0)
    assert u["u_wrong"] == -9.0
    assert {k: v for k, v in u.items() if k != "u_wrong"} == {k: v for k, v in BASE.items()
                                                              if k != "u_wrong"}


def test_implied_bar_is_the_gates_break_even() -> None:
    for uw in UW.GRID:
        u = UW.u_bar_at(BASE, uw)
        assert UW.implied_bar(u) == GATE.break_even(u)
        assert UW.implied_bar(u) == pytest.approx(abs(uw) / (1 + abs(uw)))


def test_policy_at_recomputes_commits_and_coverage_falls_as_the_penalty_grows() -> None:
    rows = _rows([0.55, 0.75, 0.85, 0.92, 0.97], [1, 1, 0, 1, 1])
    cov = [UW.coverage_and_risk(UW.policy_at(rows, UW.u_bar_at(BASE, uw)))["coverage"]
           for uw in UW.GRID]
    assert cov == sorted(cov, reverse=True)          # non-increasing in |u_wrong|
    assert cov[0] > cov[-1]
    at_minus_one = UW.policy_at(rows, UW.u_bar_at(BASE, -1.0))
    assert [r.respond for r in at_minus_one] == [True] * 5      # bar 0.5: everything commits


def test_effective_bar_is_the_harness_commit_bar_and_exceeds_the_break_even_under_a_cheap_ask(
        ) -> None:
    for uw in UW.GRID:
        u = UW.u_bar_at(BASE, uw)
        assert UW.effective_bar(u) == P3.commit_bar_for(u)
        assert UW.effective_bar(u) == pytest.approx(UW.implied_bar(u), abs=0.0015)  # 1/1000 grid
        cheap = UW.u_bar_at(CHEAP_ASK, uw)
        assert UW.effective_bar(cheap) > UW.implied_bar(cheap) + 0.05   # ask holds the bar up
    rows = _rows([0.55, 0.75, 0.85, 0.92, 0.97], [1, 1, 0, 1, 1])
    at = UW.policy_at(rows, UW.u_bar_at(CHEAP_ASK, -1.0))
    assert [r.respond for r in at] == [False, False, False, True, True]   # the engine's rule


def test_selective_risk_is_the_wrong_rate_among_covered_rows() -> None:
    rows = [P3.HeldoutTick("a", 0.9, 0.9, 1, True), P3.HeldoutTick("b", 0.9, 0.9, 0, True),
            P3.HeldoutTick("c", 0.9, 0.6, 0, False)]
    out = UW.coverage_and_risk(rows)
    assert out == {"n_ticks": 3, "n_covered": 2, "coverage": pytest.approx(2 / 3),
                   "selective_risk": pytest.approx(0.5)}
    assert UW.coverage_and_risk([rows[2]])["selective_risk"] is None


def test_delta_at_u_is_the_bootstrap_at_a_fixed_utility() -> None:
    paired = [GATE.PairedOutcome(f"q{i}", True, GATE.RealisedResponse("report", correct=True),
                                 GATE.RealisedResponse("abstain")) for i in range(6)]
    d = UW.delta_at_u(paired, BASE, oracle_p=0.9, draws=400, seed=7)
    assert d["delta_mean"] == pytest.approx(1.0) and d["p_delta_gt"] == 1.0
    assert d["delta_lo"] == pytest.approx(1.0) and d["delta_hi"] == pytest.approx(1.0)
    mirror = paired + [GATE.PairedOutcome(f"m{i}", True, GATE.RealisedResponse("abstain"),
                                          GATE.RealisedResponse("report", correct=True))
                       for i in range(6)]
    m = UW.delta_at_u(mirror, BASE, oracle_p=0.9, draws=2000, seed=7)
    assert abs(m["delta_mean"]) < 0.1 and 0.3 < m["p_delta_gt"] < 0.7


def _join_fixture() -> tuple[list[P3.HeldoutTick], dict[str, str], list[dict]]:
    texts = [f"question {i}?" for i in range(5)]
    rows = [P3.HeldoutTick(DEC.question_id(t), 0.9, p, y, respond=LR.commits_respond(BASE, p))
            for t, p, y in zip(texts, [0.55, 0.75, 0.85, 0.92, 0.97], [1, 1, 0, 1, 1],
                               strict=True)]
    h2q = {DEC.question_id(t): f"atm-q{i}" for i, t in enumerate(texts)}
    baseline = [{"question_id": f"atm-q{i}", "answerable": True, "asserted": i % 2 == 0,
                 "asserted_correct": i % 2 == 0, "bucket": "x"} for i in range(5)]
    return rows, h2q, baseline


def test_curve_point_at_the_runs_own_u_bar_reproduces_the_paired_acts_and_marginal_table(
        ) -> None:
    rows, h2q, baseline = _join_fixture()
    point = UW.curve_point(rows, BASE, h2q, baseline, oracle_p=0.9, draws=400, seed=7)
    acts = P3.question_acts(rows)
    paired, _, _ = P3.build_paired(acts, h2q, baseline)
    assert point["marginal_commits"] == GATE.marginal_commits(paired).as_record()
    assert point["typed_acts"] == {q: (a.action, a.correct) for q, a in
                                   ((h2q[h], a) for h, a in acts.items())}
    assert point["u_wrong"] == BASE["u_wrong"] and point["n_joined"] == 5
    assert set(point) >= {"implied_bar", "effective_bar", "coverage", "selective_risk",
                          "p_delta_gt",
                          "delta_mean", "delta_lo", "delta_hi", "marginal_commits"}


def test_main_writes_the_curve_record_and_report(tmp_path: Path) -> None:
    rows, h2q, baseline = _join_fixture()
    out = tmp_path / "p3"
    P3.write_heldout_rows(out, "FULL", rows)
    (out / "a3_meta-FULL.json").write_text(json.dumps(
        {"regimes": {"pricing": {"u_bar": BASE}}}), encoding="utf-8")
    qfile = tmp_path / "questions.yaml"
    import yaml
    inv = {v: k for k, v in h2q.items()}
    qs = [{"id": qid, "question": f"question {qid[-1]}?"} for qid in inv]
    qfile.write_text(yaml.safe_dump({"questions": qs}), encoding="utf-8")
    run = tmp_path / "ff"
    (run / "arms" / "baseline").mkdir(parents=True)
    (run / "arms" / "baseline" / "vectors.jsonl").write_text(
        "".join(json.dumps(b) + "\n" for b in baseline), encoding="utf-8")
    rc = UW.main(["--out", str(out), "--variant", "FULL", "--questions-v2", str(qfile),
                  "--baseline-run", str(run), "--draws", "200", "--seed", "3"])
    assert rc == 0
    rec = json.loads((out / "u_wrong_curve-FULL.json").read_text(encoding="utf-8"))
    assert [p["u_wrong"] for p in rec["points"]] == list(UW.GRID)
    assert rec["base_u_bar"] == BASE and rec["variant"] == "FULL"
    md = (out / "u_wrong_curve-FULL.md").read_text(encoding="utf-8")
    assert "never a verdict" in md and "-5.131" in md
