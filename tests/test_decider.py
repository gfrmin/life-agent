"""The one decider (core/decider.py + core/decide.bayes_act): the posterior is local, the act
is its expected-utility maximum under the declared rows, and nothing else ranks."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import decide as DEC
from life_agent.core import decider as DCD
from life_agent.core import gather_row as GR
from life_agent.core import posterior as POST


def _gather(right_if_right: float, wrong_if_right: float = 0.0, right_if_wrong: float = 0.0,
            wrong_if_wrong: float = 0.0) -> dict[str, float]:
    """A gather row: the sequence's chances of ending right / wrong per leader state."""
    return GR.as_u_bar({"right": right_if_right, "wrong": wrong_if_right},
                       {"right": right_if_wrong, "wrong": wrong_if_wrong})


_U = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, "lambda_int": 1.0,
      "kappa_att": 0.02, **_gather(0.1), DEC.ASK_RECOVERY_KEY: 0.5}

_OBS = [{"reports": 1, "group": 0, "authority": 1.0, "subject_factor": 1.0,
         "time_factor": 1.0, "competition_factor": 1.0},
        {"reports": 1, "group": 1, "authority": 1.0, "subject_factor": 1.0,
         "time_factor": 1.0, "competition_factor": 1.0}]


def _payload(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "question_id": "q1", "candidates": ["x", "y"], "observations": _OBS, "rho": 0.8,
        "applied_probes": [], "era_split": False, "owner_scoped": False,
        "transforms": [{"probe": "corroborate_a", "kind": "voi", "cost": 0.004}]}
    base.update(kw)
    return base


# --- the act -----------------------------------------------------------------------------

def test_the_bayes_act_is_the_row_argmax_at_p1() -> None:
    assert DEC.bayes_act(_U, 0.99) == "respond"
    assert DEC.bayes_act(_U, 0.5) == "gather"  # a cheap read that sometimes recovers
    assert DEC.bayes_act(_U, 0.5, gather_open=False) == "abstain"
    bar = DEC.respond_threshold(_U)
    assert bar is not None and 0.8 < bar < 0.95
    assert DEC.bayes_act(_U, bar - 1e-6) != "respond"
    assert DEC.bayes_act(_U, bar + 1e-6) == "respond"


def test_gather_is_ranked_only_while_open_and_pays_its_price() -> None:
    u = {**_U, **_gather(0.9), "kappa_att": 0.0}
    assert DEC.bayes_act(u, 0.6) == "gather"
    assert DEC.bayes_act(u, 0.6, gather_open=False) == "abstain"
    assert DEC.bayes_act(u, 0.6, gather_cost=10.0) == "abstain"


def test_ties_resolve_to_the_first_listed_action() -> None:
    u = {"u_correct": 0.0, "u_abstain": 0.0, "u_wrong": 0.0, "lambda_int": 0.0,
         "kappa_att": 0.0}
    assert DEC.bayes_act(u, 0.3) == DEC.ACTIONS[0] == "abstain"


def test_p_correct_is_the_map_credence() -> None:
    assert DEC.p_correct([0.2, 0.7, 0.1]) == 0.7
    assert DEC.p_correct([]) == 0.0


def test_no_information_act_is_priced_as_perfect_information() -> None:
    """Perfect information is an upper bound: unmeasured, the ask reads the Beta(1, 1) mean
    and the gather row its Dirichlet prior mean, so neither is worth u_correct when asserting
    would be right."""
    rows = DEC.utility_by_action({"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0,
                                  "lambda_int": 0.0, "kappa_att": 0.0})
    assert rows["ask"][1] == DEC.PRIOR_RECOVERY < 1.0
    assert rows["gather"] == pytest.approx(((1.0 - 9.0) / 3.0, (1.0 - 9.0) / 3.0))


def test_the_gather_row_prices_its_fitted_outcomes_at_the_owner_utilities() -> None:
    u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, "kappa_att": 0.05,
         **_gather(0.9, 0.02, 0.2, 0.05)}
    wrong, right = DEC.utility_by_action(u)["gather"]
    assert right == pytest.approx(0.9 - 9.0 * 0.02 - 0.05)
    assert wrong == pytest.approx(0.2 - 9.0 * 0.05 - 0.05)


def test_the_gather_row_fit_recovers_its_generating_outcomes() -> None:
    import random

    rng = random.Random(7)
    t_r = {"right": 0.9, "wrong": 0.03, "declined": 0.07}
    t_w = {"right": 0.2, "wrong": 0.05, "declined": 0.75}
    eps = []
    for _ in range(4000):
        p1 = rng.random()
        t = t_r if rng.random() < p1 else t_w
        x = rng.random()
        eps.append((p1, "right" if x < t["right"] else
                    "wrong" if x < t["right"] + t["wrong"] else "declined"))
    f_r, f_w = GR.fit(eps)
    for o in GR.OUTCOMES:
        assert f_r[o] == pytest.approx(t_r[o], abs=0.04)
        assert f_w[o] == pytest.approx(t_w[o], abs=0.04)


def test_an_absent_fit_reads_the_prior(tmp_path: Path) -> None:
    assert GR.load(tmp_path / "none.json") == GR.PRIOR


# --- the decider -------------------------------------------------------------------------

def test_the_posterior_is_local_and_the_act_is_its_argmax() -> None:
    view = DCD.decide(_payload(), _U)
    credences, p_none = POST.candidate_posterior(2, _OBS, 0.8)
    assert view["credences"] == credences and view["p_none"] == p_none
    assert view["p1"] == max(credences)
    assert view["act"] == DEC.bayes_act(_U, view["p1"], gather_open=True, gather_cost=0.004)
    assert view["eu"] == pytest.approx(
        DEC.eu_by_action(_U, view["p1"])[view["act"]]
        - (0.004 if view["act"] == "gather" else 0.0))


def test_a_certain_leader_is_reported_and_an_uncertain_one_withheld() -> None:
    sure = DCD.decide(_payload(observations=_OBS * 4, rho=0.95), _U)
    assert (sure["effector"], sure["value"]) == ("report", "y")
    unsure = DCD.decide(_payload(observations=[], transforms=[]), _U)
    assert unsure["effector"] == "abstain" and unsure["p1"] < 0.5


def test_gather_closes_when_every_option_is_applied() -> None:
    u = {**_U, "u_wrong": -100.0, **_gather(0.9), "kappa_att": 0.0}
    open_ = DCD.decide(_payload(), u)
    closed = DCD.decide(_payload(applied_probes=["corroborate_a"]), u)
    assert open_["effector"] == "gather" and open_["probe"] == "corroborate_a"
    assert closed["effector"] != "gather"


def test_the_handle_reads_u_bar_per_decision() -> None:
    reads: list[int] = []

    def u_bar() -> dict[str, float]:
        reads.append(1)
        return _U

    d = DCD.Decider(u_bar)
    d.decide("q1", _payload())
    d.decide("q1", _payload())
    assert reads == [1, 1] and d.status() == {"kind": "host"}


# --- the drift gate: nothing else ranks --------------------------------------------------

def _calls(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == name) or (
                    isinstance(f, ast.Attribute) and f.attr == name):
                return True
    return False


def test_only_the_decider_takes_the_act() -> None:
    """Rule 2: `bayes_act` is CALLED (by AST, not spelling) from core/decider.py and nowhere
    else in the package; `argmax_action`, its unpriced alias, only from core/decide.py's own
    thresholds."""
    root = Path(__file__).resolve().parents[1] / "src" / "life_agent"
    trees = {str(p.relative_to(root)): ast.parse(p.read_text(encoding="utf-8"))
             for p in root.rglob("*.py")}
    assert {f for f, t in trees.items() if _calls(t, "bayes_act")} == {
        "core/decide.py", "core/decider.py"}
    assert {f for f, t in trees.items() if _calls(t, "argmax_action")} == {"core/decide.py"}
