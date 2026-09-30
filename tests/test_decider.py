"""The one decider (core/decider.py + core/decide.bayes_act): the posterior is local, the act
is its expected-utility maximum under the declared rows, and nothing else ranks."""
from __future__ import annotations

import ast
import random
from pathlib import Path
from typing import Any

import pytest

from life_agent.core import decide as DEC
from life_agent.core import decider as DCD
from life_agent.core import enact as EN
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
        "applied_probes": [],
        "transforms": [{"probe": "corroborate_a", "kind": "voi", "cost": 0.004}]}
    base.update(kw)
    return base


# --- the act -----------------------------------------------------------------------------

_OPEN = [("corroborate_a", 0.0)]


def _act(u: dict[str, float], p1: float, gathers: list[tuple[str, float]] = _OPEN) -> str:
    return DEC.bayes_act(u, [p1], gathers).action


def test_the_bayes_act_is_the_row_argmax_at_p1() -> None:
    assert _act(_U, 0.99) == "respond"
    assert _act(_U, 0.5) == "gather"  # a cheap read that sometimes recovers
    assert _act(_U, 0.5, []) == "abstain"
    bar = DEC.respond_threshold(_U)
    assert bar is not None and 0.8 < bar < 0.95
    assert _act(_U, bar - 1e-6) != "respond"
    assert _act(_U, bar + 1e-6) == "respond"


def test_gather_is_ranked_only_while_open_and_pays_its_price() -> None:
    u = {**_U, **_gather(0.9), "kappa_att": 0.0}
    assert _act(u, 0.6) == "gather"
    assert _act(u, 0.6, []) == "abstain"
    assert _act(u, 0.6, [("corroborate_a", 10.0)]) == "abstain"


def test_ties_resolve_to_the_first_listed_action() -> None:
    u = {"u_correct": 0.0, "u_abstain": 0.0, "u_wrong": 0.0, "lambda_int": 0.0,
         "kappa_att": 0.0}
    assert _act(u, 0.3) == DEC.ACTIONS[0] == "abstain"


def test_every_choice_is_a_row_listed_in_tie_break_order() -> None:
    rows = DEC.options(_U, [0.2, 0.7], [("a", 0.01), ("b", 0.02)])
    assert [(o.action, o.target) for o in rows] == [
        ("abstain", None), ("gather", "a"), ("gather", "b"), ("ask", None),
        ("respond", 0), ("respond", 1)]
    assert rows[1].eu - rows[2].eu == pytest.approx(0.01)


def test_the_cheapest_probe_and_the_leading_candidate_win_their_ties_by_position() -> None:
    u = {**_U, **_gather(0.9), "kappa_att": 0.0}
    won = DEC.bayes_act(u, [0.3, 0.3], [("a", 0.01), ("b", 0.01), ("c", 0.02)])
    assert (won.action, won.target) == ("gather", "a")
    won = DEC.bayes_act(u, [0.3, 0.95, 0.95])
    assert (won.action, won.target) == ("respond", 1)
    assert DEC.bayes_act(u, []).action in {"abstain", "ask"}


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


def test_with_no_fit_and_no_shipped_row_the_prior_stands(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GR, "EXAMPLE", tmp_path / "also-none.json")
    assert GR.load(tmp_path / "none.json") == {}
    assert GR.at_step(_U, 2) == _U


# --- The shipped row: a KB with no fit must still be able to gather (J3) ---------------
# Measured on the synthetic sample corpus before this existed: 14 questions, 14 declines,
# ZERO gathers applied. Under the uniform prior a gather is as likely to mislead as to
# help, so the act never buys one, the posterior never concentrates, and the system
# declines everything it is ever asked. A decider that cannot start is not a safer one.

def test_a_kb_with_no_fit_falls_back_to_the_shipped_row(tmp_path: Path) -> None:
    """Killed by returning {} for an unfitted KB — which is what shipped a decliner."""
    loaded = GR.load(tmp_path / "absent.json")
    assert loaded, "an unfitted KB got no gather row at all"
    assert all(GR.step_key(k, 0) in loaded for k in GR.KEYS)


def test_the_shipped_row_makes_gathering_worth_something() -> None:
    """The property, not the file's presence: it must say a gather helps a right leader
    more than it helps a wrong one, and more than it corrupts a right one. Killed by
    shipping the uniform prior under another name."""
    row = GR.at_step(GR.load(Path("/absent")), 0)
    assert row["gather_right_if_right"] > row["gather_right_if_wrong"]
    assert row["gather_right_if_right"] > row["gather_wrong_if_right"]


def test_a_fitted_kb_is_never_shadowed_by_the_shipped_row(tmp_path: Path) -> None:
    """The discriminating control: your own measurement always wins."""
    import json as _json
    fit = tmp_path / "gather_row.json"
    fit.write_text(_json.dumps({"steps": {"0": dict.fromkeys(GR.KEYS, 0.5)}}),
                   encoding="utf-8")
    assert GR.load(fit) == {GR.step_key(k, 0): 0.5 for k in GR.KEYS}


def test_the_decider_prices_gather_at_the_step_it_is_on(tmp_path: Path) -> None:
    """Returns fall with every gather already applied: the row for the current step, and the
    last fitted step beyond it."""
    import json

    rows = {"0": _gather(0.9, 0.02, 0.2, 0.05), "1": _gather(0.5, 0.05, 0.05, 0.04),
            "3": _gather(0.1, 0.02, 0.02, 0.01)}
    path = tmp_path / "gather_row.json"
    path.write_text(json.dumps({"steps": rows}), encoding="utf-8")
    fitted = {**_U, **GR.load(path)}
    assert GR.at_step(fitted, 0)["gather_right_if_right"] == 0.9
    assert GR.at_step(fitted, 2)["gather_right_if_right"] == 0.5   # step 2 unfitted: step 1
    assert GR.at_step(fitted, 7)["gather_right_if_right"] == 0.1   # capped at MAX_STEP
    split = [{**_OBS[0], "reports": 0}, _OBS[1]]                   # p1 0.48
    first = DCD.decide(_payload(observations=split), fitted)
    later = DCD.decide(_payload(observations=split, applied_probes=["x", "y", "z"]), fitted)
    assert first["effector"] == "gather" and later["effector"] != "gather"


# --- the decider -------------------------------------------------------------------------

def test_the_posterior_is_local_and_the_act_is_its_argmax() -> None:
    view = DCD.decide(_payload(), _U)
    credences, p_none = POST.candidate_posterior(2, _OBS, 0.8)
    assert view["credences"] == credences and view["p_none"] == p_none
    assert view["p1"] == max(credences)
    option = DEC.bayes_act(_U, credences, [("corroborate_a", 0.004)])
    assert view["act"] == option.action and view["eu"] == option.eu
    assert view["eu"] == pytest.approx(
        DEC.eu_by_action(_U, view["p1"])[view["act"]]
        - (0.004 if view["act"] == "gather" else 0.0))


def test_a_state_with_no_candidate_is_decided_at_p1_zero() -> None:
    # No candidate: the posterior is NONE with certainty, p1 = 0, and the rows are abstain,
    # one gather per open probe, and ask — there is nothing to respond with.
    view = DCD.decide(_payload(candidates=[], observations=[]), _U)
    assert view["credences"] == [] and view["p_none"] == pytest.approx(1.0)
    assert view["p1"] == 0.0 and view["value"] is None
    assert view["effector"] == "abstain"            # the prior row: gathering is not worth it
    assert [o.action for o in DEC.options(_U, [], [("p", 0.1)])] == ["abstain", "gather", "ask"]
    worth = DCD.decide(_payload(candidates=[], observations=[]),
                       {**_U, **_gather(0.9, right_if_wrong=0.6), "u_wrong": -1.0})
    assert (worth["effector"], worth["probe"]) == ("gather", "corroborate_a")


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
    else in the package, and so is `choose`, the one function holding the `max` (the route
    stage ranks through it too); `argmax_action`, the unpriced alias, only from
    core/decide.py's own thresholds."""
    root = Path(__file__).resolve().parents[1] / "src" / "life_agent"
    trees = {str(p.relative_to(root)): ast.parse(p.read_text(encoding="utf-8"))
             for p in root.rglob("*.py")}
    assert {f for f, t in trees.items() if _calls(t, "bayes_act")} == {
        "core/decide.py", "core/decider.py"}
    assert {f for f, t in trees.items() if _calls(t, "choose")} == {
        "core/decide.py", "core/decider.py"}
    assert {f for f, t in trees.items() if _calls(t, "argmax_action")} == {"core/decide.py"}
    # nor does the enactment choose anything: it lists options and maps the winner
    assert not {n for n in ("max", "min", "sorted") if _calls(trees["core/enact.py"], n)}


# --- every choice is a row: the equivalence with the rule it replaced --------------------

def _old_bayes_act(u_bar: dict[str, float], p1: float, gather_open: bool,
                   gather_cost: float) -> str:
    """REFERENCE (the rule this change replaced): the act over the four actions, gather
    priced at the cheapest open probe."""
    eus = DEC.eu_by_action(u_bar, p1)
    eus["gather"] -= float(gather_cost)
    ranked = [a for a in DEC.ACTIONS if a != "gather" or gather_open]
    return max(ranked, key=lambda a: (eus[a], -DEC.ACTIONS.index(a)))


def _old_decide(payload: dict[str, Any], u_bar: dict[str, float],
                credences: list[float]) -> tuple[str, str | None, int | None, float]:
    """REFERENCE: (act, probe, candidate index, eu) as the old decider and enact chose them:
    cheapest open probe by a stable sort over the rows, first-max credence."""
    applied = {str(a) for a in payload["applied_probes"]}
    rows = [t for t in payload["transforms"] if t.get("kind") == "voi"]
    rows += payload["grow"]["actuators"]
    open_: list[str] = []
    for r in sorted(rows, key=lambda r: float(r.get("cost") or 0.0)):
        probe = str(r.get("probe") or "")
        if probe and probe not in applied and probe not in open_:
            open_.append(probe)
    cost = (min(float(r.get("cost") or 0.0) for r in rows if str(r.get("probe")) == open_[0])
            if open_ else 0.0)
    p1 = DEC.p_correct(credences)
    u = GR.at_step(u_bar, len(payload["applied_probes"]))
    act = _old_bayes_act(u, p1, bool(open_), cost)
    eu = DEC.eu_by_action(u, p1)[act] - (cost if act == "gather" else 0.0)
    if act == "respond":
        return act, None, max(range(len(credences)), key=lambda j: credences[j]), eu
    return act, (open_[0] if act == "gather" else None), None, eu


_POOL = ["p0", "p1", "p2", "p3"]
_COSTS = [0.0, 0.004, 0.004, 0.01, 0.02, 0.05]  # repeats and zero: equal-cost ties


def _draw(rng: random.Random) -> tuple[dict[str, Any], dict[str, float], list[float]]:
    u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -rng.uniform(1.5, 20.0),
         "lambda_int": rng.uniform(0.0, 0.5), "kappa_att": rng.uniform(0.0, 0.05),
         DEC.ASK_RECOVERY_KEY: rng.uniform(0.0, 1.0)}
    right = rng.uniform(0.0, 1.0)
    u.update(_gather(right, rng.uniform(0.0, 1.0 - right)))
    n = rng.randint(0, 5)
    if rng.random() < 0.5:  # a coarse grid: exact ties between candidates
        cuts = [rng.randint(0, 8) for _ in range(n)]
        while sum(cuts) > 8:
            cuts[rng.randrange(n)] //= 2
        credences = [c / 8 for c in cuts]
    else:
        w = [rng.random() for _ in range(n)]
        total = rng.uniform(0.0, 1.0) / (sum(w) or 1.0)
        credences = [x * total for x in w]

    def row(kind: str) -> dict[str, Any]:
        return {"probe": rng.choice(_POOL), "kind": kind, "cost": rng.choice(_COSTS)}

    payload = {"candidates": [f"c{j}" for j in range(n)],
               "applied_probes": rng.sample(_POOL, rng.randint(0, 3)),
               "transforms": [row(rng.choice(["voi", "voi", "guard"]))
                              for _ in range(rng.randint(0, 3))],
               "grow": {"actuators": [row("voi") for _ in range(rng.randint(0, 2))]}}
    return payload, u, credences


def test_every_choice_a_row_is_the_rule_it_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    """5,000 seeded draws — candidates 0-5 (grid credences, so exact ties), probes 0-5 rows
    from a pool of four (duplicated probes, equal and zero costs), varied applied probes and
    utilities: the same act, probe, candidate and (exact ==) EU as the old rule."""
    rng = random.Random(20260930)
    draw: dict[str, list[float]] = {}
    monkeypatch.setattr(DCD.POST, "candidate_posterior",
                        lambda n, obs, rho: (draw["c"], 0.0))
    seen: set[tuple[str, bool]] = set()
    for i in range(5000):
        payload, u, credences = _draw(rng)
        draw["c"] = credences
        old = _old_decide(payload, u, credences)
        payload = {**payload, "observations": [], "rho": 0.8}
        view = DCD.decide(payload, u)
        cands = payload["candidates"]
        new = (view["act"], view["probe"],
               cands.index(view["value"]) if view["value"] is not None else None, view["eu"])
        assert new == old, f"draw {i}: {payload=} {u=} {credences=}: new {new} != old {old}"
        seen.add((new[0], new[2] not in (None, 0)))
    assert {a for a, _ in seen} == set(DEC.ACTIONS) and ("respond", True) in seen


def test_the_equivalence_holds_on_named_ties() -> None:
    u = {**_U, **_gather(0.9), "kappa_att": 0.0}
    tied = {"candidates": ["x", "y"], "applied_probes": [], "observations": [], "rho": 0.8,
            "transforms": [{"probe": "b", "kind": "voi", "cost": 0.01},
                           {"probe": "a", "kind": "voi", "cost": 0.01}],
            "grow": {"actuators": [{"probe": "b", "cost": 0.005}]}}
    # b's cheapest row is the grow row, so b (0.005) beats a (0.01)
    assert _old_decide(tied, u, [0.3, 0.3])[:2] == ("gather", "b")
    # a probe whose cheapest row comes LATER than a rival's equal-cost row lists after it
    tied2 = {**tied, "transforms": [{"probe": "a", "kind": "voi", "cost": 0.02},
                                    {"probe": "b", "kind": "voi", "cost": 0.01}],
             "grow": {"actuators": [{"probe": "a", "cost": 0.01}]}}
    assert _old_decide(tied2, u, [0.3, 0.3])[:2] == ("gather", "b")
    assert [p for p, _ in EN.gather_options(tied2)] == ["b", "a"]
    for payload, cr in ((tied, [0.3, 0.3]), (tied2, [0.3, 0.3]), (tied, [0.5, 0.5]),
                        ({**tied, "applied_probes": ["a", "b"]}, [0.95, 0.95])):
        credences = cr
        old = _old_decide(payload, u, credences)
        opt = DEC.bayes_act(GR.at_step(u, len(payload["applied_probes"])), credences,
                            EN.gather_options(payload))
        assert (opt.action, opt.eu) == (old[0], old[3])
        assert opt.target == (old[1] if opt.action == "gather" else old[2])
