"""The posterior-constants fit (scripts/fit_posterior.py), on synthetic states only."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import fit_posterior as FP  # noqa: E402

from life_agent.core import posterior as POST  # noqa: E402
from life_agent.core import seam as SEAM  # noqa: E402

BASE = POST.default_channel()
U_BAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0}


def _obs(reports: int, group: int) -> dict[str, float]:
    return {"reports": reports, "group": group, "authority": 1.0, "subject_factor": 1.0,
            "time_factor": 1.0, "competition_factor": 1.0}


def _state(reports: list[tuple[int, int]], *, truth: int, k: int = 3, rho: float = 0.6,
           qid: str = "q") -> FP.State:
    return FP.State(question_id=qid, k=k, observations=tuple(_obs(r, g) for r, g in reports),
                    rho=rho, applied=(), transforms=(), grow=None, truth=truth,
                    matches=(truth,) if truth != FP.NONE else ())


# PII-OK: synthetic candidate values and gold, no corpus content
def test_label_is_the_first_matching_candidate_or_none() -> None:
    assert FP.label(["alpha", "beta-7", "gamma"], "beta-7", []) == (1, (1,))
    assert FP.label(["beta-7", "x beta-7 y"], "beta-7", []) == (0, (0, 1))
    assert FP.label(["alpha", "gamma"], "beta-7", []) == (FP.NONE, ())
    assert FP.label([], "beta-7", []) == (FP.NONE, ())
    assert FP.label(["alpha"], "", []) == (FP.NONE, ())


def test_truth_prob_reads_the_candidate_or_none() -> None:
    right = _state([(1, 0), (1, 1)], truth=1)
    cred, p_none = POST.candidate_posterior(3, list(right.observations), 0.6, BASE)
    assert FP.truth_prob(right, BASE) == cred[1]
    none = replace(right, truth=FP.NONE, matches=())
    assert FP.truth_prob(none, BASE) == p_none


def test_score_of_a_state_with_no_candidate_is_a_certain_none() -> None:
    s = FP.State("q", 0, (), 0.5, (), (), None, FP.NONE, ())
    sc = FP.score([s], BASE)
    assert sc.truth_log == pytest.approx(0.0, abs=1e-5)
    assert sc.leader.n_scored == 0  # no leader to grade, as on the board


def test_ascend_finds_the_maximum_of_a_concave_objective() -> None:
    grids = {"beta_ancestry": FP.arange(0.0, 1.0, 0.05), "eta": FP.arange(0.5, 4.0, 0.1)}

    def objective(ch: POST.Channel) -> float:
        return -((ch.beta_ancestry - 0.6) ** 2) - (ch.eta - 2.0) ** 2

    best = FP.ascend(objective, BASE, ("beta_ancestry", "eta"), grids)
    assert best.beta_ancestry == pytest.approx(0.6) and best.eta == pytest.approx(2.0)
    assert best.beta_model == BASE.beta_model  # a parameter not free stays put


def test_eta_fit_follows_the_evidence() -> None:
    agreeing = [_state([(0, 0), (0, 1)], truth=0, qid=f"a{i}") for i in range(20)]
    misleading = [_state([(1, 0), (1, 1)], truth=0, qid=f"m{i}") for i in range(20)]
    assert FP.fit(agreeing, BASE, ("eta",)).eta > 3.0  # the score saturates near the top
    assert FP.fit(misleading, BASE, ("eta",)).eta == min(FP.GRIDS["eta"])


def test_flatness_shows_a_parameter_the_data_cannot_see() -> None:
    # one observation per state: nothing is tempered, so the betas cannot move the score
    states = [_state([(0, 0)], truth=0, qid=f"s{i}") for i in range(10)]
    flat = FP.flatness(states, BASE, ("beta_ancestry", "eta"))
    lo, hi = flat["beta_ancestry"]
    assert (lo, hi) == (min(FP.GRIDS["beta_ancestry"]), max(FP.GRIDS["beta_ancestry"]))
    assert flat["eta"][1] - flat["eta"][0] < hi - lo or flat["eta"][0] >= 0.5


def test_a_fit_never_scores_below_the_start_on_its_own_states() -> None:
    states = ([_state([(0, 0), (0, 1)], truth=0, qid=f"a{i}") for i in range(8)]
              + [_state([(2, 0)], truth=FP.NONE, qid=f"n{i}") for i in range(4)])
    objective = FP.truth_objective(states)
    best = FP.fit(states, BASE, ("beta_ancestry", "beta_model", "eta"))
    assert objective(best) >= objective(BASE)


def test_consequences_count_right_and_wrong_responds() -> None:
    sure_right = _state([(0, 0), (0, 1), (0, 2)], truth=0, k=1, rho=0.95, qid="r")
    sure_wrong = _state([(0, 0), (0, 1), (0, 2)], truth=FP.NONE, k=1, rho=0.95, qid="w")
    unsure = _state([], truth=0, k=2, qid="u")
    c = FP.consequences([sure_right, sure_wrong, unsure], BASE, U_BAR)
    assert c.responds == {0, 1} and c.right == {0} and c.wrong == {1}
    assert c.utility == pytest.approx((1.0 - 9.0) / 3)


def test_a_louder_channel_responds_where_the_baseline_declines() -> None:
    mid = [_state([(0, 0), (0, 1)], truth=0, k=2, rho=0.3, qid=f"m{i}") for i in range(3)]
    base = FP.consequences(mid, BASE, U_BAR)
    loud = FP.consequences(mid, replace(BASE, eta=3.0), U_BAR)
    assert not base.responds and len(loud.responds) == 3
    assert FP.flips(base, loud) == (3, 3, 0)
    assert FP.flips(loud, base) == (0, 0, 3)


def test_capture_keeps_the_last_evidence_stage_decide_and_skips_the_route() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    def inner(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        sent.append((url, payload))
        return {"act": payload.get("tag", "route")}

    def drive(question: str, k: int, *, post: Any, run_id: str) -> None:
        del question, k, run_id
        post("b/decide", {"stage": SEAM.STAGE_ROUTE, "lookup": True})
        post("b/decide", {"candidates": ["x"], "tag": "first"})
        post("b/log_decision", {"tag": "not a decide"})
        post("b/decide", {"candidates": ["x", "y"], "tag": "last"})

    got = FP.capture_one("question", 20, run_id="gate-x", inner_post=inner, drive=drive)
    assert got is not None and got[0]["tag"] == "last" and got[1] == {"act": "last"}

    def route_only(question: str, k: int, *, post: Any, run_id: str) -> None:
        del question, k, run_id
        post("b/decide", {"stage": SEAM.STAGE_ROUTE, "lookup": False})

    assert FP.capture_one("question", 20, run_id="gate-x", inner_post=inner,
                          drive=route_only) is None


def test_reproduction_compares_the_archived_leader() -> None:
    req: dict[str, Any] = {
        "candidates": ["x", "y"], "observations": [_obs(0, 0), _obs(0, 1)], "rho": 0.7,
        "applied_probes": [], "transforms": []}
    row = FP.capture_row({"id": "q1", "answer": "x"}, req, {}, set_name="s", run_id="gate-x",
                         censored=False)
    cred, _ = POST.candidate_posterior(2, req["observations"], 0.7)
    good = {"q1": {"typed": {"p1": max(cred), "leader_correct": True}}}
    bad = {"q1": {"typed": {"p1": max(cred) + 0.1, "leader_correct": False}}}
    assert FP.reproduction([row], good)["p1 match"] == 1
    off = FP.reproduction([row], bad)
    assert off["p1 differ"] == 1 and off["leader label differs"] == 1
    assert FP.reproduction([row], {})["no archive row"] == 1


def test_folds_partition_and_stratify_by_group() -> None:
    groups = ["g"] * 23 + ["o"] * 12
    f = FP.folds(groups, 5, seed=1)
    assert f == FP.folds(groups, 5, seed=1) and f != FP.folds(groups, 5, seed=2)
    assert set(f) == set(range(5))
    for g, n in (("g", 23), ("o", 12)):
        sizes = [sum(1 for x, y in zip(groups, f, strict=True) if x == g and y == k)
                 for k in range(5)]
        assert sum(sizes) == n and max(sizes) - min(sizes) <= 1


def test_cross_validated_channels_never_see_their_own_fold() -> None:
    # the misleading states sit in fold 0 only; its channel is fitted on the agreeing rest
    agreeing = [_state([(0, 0), (0, 1)], truth=0, qid=f"a{i}") for i in range(8)]
    misleading = [_state([(1, 0), (1, 1)], truth=0, qid="m")]
    fold_of = [1, 2, 3, 1, 2, 3, 1, 2, 0]
    chans = FP.cross_validate(agreeing + misleading, fold_of, BASE, ("eta",))
    assert chans[-1].eta > 3.0      # fitted without the misleading state
    assert chans[0].eta < chans[-1].eta  # fold 1's fit includes it, and is pulled down


def test_score_each_equals_score_for_one_channel() -> None:
    states = [_state([(0, 0), (0, 1)], truth=0, qid="a"),
              _state([(2, 0)], truth=FP.NONE, qid="b")]
    ch = replace(BASE, eta=1.5)
    one, each = FP.score(states, ch), FP.score_each(states, [ch, ch])
    assert one.truth_log == each.truth_log and one.leader == each.leader


def test_fit_g_has_an_interior_optimum_on_the_wide_grid() -> None:
    # a report that is right 3 times in 4 is well described by a finite A
    right = [_state([(0, 0)], truth=0, qid=f"r{i}", rho=0.6) for i in range(6)]
    wrong = [_state([(1, 0)], truth=0, qid=f"w{i}", rho=0.6) for i in range(2)]
    best = FP.fit(right + wrong, BASE, FP.FIT_G, FP.GRIDS_WIDE)
    assert best.a_alternatives in FP.WIDE_A and best.eta == 1.0
    assert best.beta_ancestry == BASE.beta_ancestry and best.p_none_prior == BASE.p_none_prior
    lo, hi = FP.flatness(right + wrong, best, FP.FIT_G, FP.GRIDS_WIDE)["a_alternatives"]
    assert lo <= best.a_alternatives <= hi


def test_consequences_carry_the_p1_of_each_response() -> None:
    sure = _state([(0, 0), (0, 1), (0, 2)], truth=0, k=1, rho=0.95, qid="r")
    c = FP.consequences([sure], BASE, U_BAR)
    cred, _ = POST.candidate_posterior(1, list(sure.observations), 0.95, BASE)
    assert c.p1 == {0: cred[0]}


def test_negatives_are_read_without_their_leaks(tmp_path: Path) -> None:
    import json

    def row(qid: str, **extra: Any) -> str:
        req = {"candidates": ["x"], "observations": [_obs(0, 0)], "rho": 0.6,
               "applied_probes": [], "transforms": []}
        return json.dumps({"question_id": qid, "truth": FP.NONE, "matches": [],
                           "request": req, **extra})

    path = tmp_path / "neg.jsonl"
    path.write_text("\n".join([row("a"), row("b", leak=True), row("c")]) + "\n")
    states, leaks = FP.read_negatives(path)
    assert [s.question_id for s in states] == ["a", "c"] and leaks == 1
    assert all(s.negative and s.truth == FP.NONE for s in states)


def test_the_weighted_objective_follows_the_weights() -> None:
    pos = _state([(0, 0), (0, 1)], truth=0, qid="p")
    neg = replace(_state([(0, 0), (0, 1)], truth=FP.NONE, qid="n"), negative=True)
    eta_hi = replace(BASE, eta=3.0)
    heavy_neg = FP.truth_objective(FP.reweighted([pos, neg], negative_weight=10.0))
    light_neg = FP.truth_objective(FP.reweighted([pos, neg], negative_weight=0.001))
    assert heavy_neg(eta_hi) < heavy_neg(BASE)     # confident evidence costs the negatives
    assert light_neg(eta_hi) > light_neg(BASE)     # and helps the positives
    plain = FP.truth_objective([pos, neg])
    assert plain(BASE) == pytest.approx((FP.truth_log(FP.truth_prob(pos, BASE))
                                         + FP.truth_log(FP.truth_prob(neg, BASE))) / 2)


def test_folds_by_question_keep_a_questions_states_together() -> None:
    ids = ["q1", "q2", "q3", "q4", "q1", "q3"]
    groups = ["g", "g", "g", "o", "g", "g"]
    f = FP.folds_by_question(ids, groups, 2, seed=3)
    assert f[0] == f[4] and f[2] == f[5] and set(f) <= {0, 1}
