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
