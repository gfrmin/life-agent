"""The route state (ruling 6): attempting a question is a row of the one argmax, priced from the
router's verdict by a measured row (core/route_row.py, core/decide.route_options)."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from life_agent.core import decide as DEC
from life_agent.core import decider as DCD
from life_agent.core import pricing as PRC
from life_agent.core import recorder as REC
from life_agent.core import route_row as RR
from life_agent.core import seam as SEAM

_SHIPPED = RR.load(Path("/absent"))
_GAUGES = (-9.0, -5.13)


def _u(u_wrong: float = -9.0, lambda_usd: float = 1.5, **row: float) -> dict[str, float]:
    return {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": u_wrong, **_SHIPPED, **row,
            RR.PRICE_KEY: PRC.FIRST_PASS_USD * lambda_usd}


def _act(u: dict[str, float], lookup: bool) -> str:
    return DEC.choose(DEC.route_options(u, lookup)).action


# --- the rows -------------------------------------------------------------------------------

@pytest.mark.parametrize("u_wrong", _GAUGES)
def test_under_the_shipped_row_accepted_is_attempted_and_rejected_declined(
        u_wrong: float) -> None:
    u = _u(u_wrong)
    assert _act(u, True) == "attempt"
    assert _act(u, False) == "abstain"


def test_the_rows_are_abstain_then_attempt_at_the_stated_formula() -> None:
    u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, RR.q_key(True): 0.8,
         RR.q_key(False): 0.1, RR.RIGHT_KEY: 0.5, RR.WRONG_KEY: 0.02,
         RR.WRONG_OTHER_KEY: 0.03, RR.PRICE_KEY: 0.04}
    rows = DEC.route_options(u, True)
    assert [(o.action, o.target) for o in rows] == [("abstain", None), ("attempt", None)]
    v_lookup, v_other = 0.5 - 9.0 * 0.02, -9.0 * 0.03
    assert rows[0].eu == 0.0
    assert rows[1].eu == pytest.approx(0.8 * v_lookup + 0.2 * v_other - 0.04)
    assert DEC.route_options(u, False)[1].eu == pytest.approx(
        0.1 * v_lookup + 0.9 * v_other - 0.04)


def test_a_rejection_the_row_distrusts_is_attempted() -> None:
    # the router's verdict is an observation: where rejections are usually wrong (q@reject
    # high) attempting beats declining, at either gauge
    for u_wrong in _GAUGES:
        assert _act(_u(u_wrong, **{RR.q_key(False): 0.9}), False) == "attempt"
    assert _act(_u(**{RR.q_key(False): 0.05}), False) == "abstain"


def test_an_acceptance_the_row_distrusts_is_declined() -> None:
    assert _act(_u(**{RR.q_key(True): 0.05}), True) == "abstain"


def test_an_exact_tie_goes_to_abstain() -> None:
    u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0, RR.q_key(True): 0.7,
         RR.RIGHT_KEY: 0.0, RR.WRONG_KEY: 0.0, RR.WRONG_OTHER_KEY: 0.0, RR.PRICE_KEY: 0.0}
    rows = DEC.route_options(u, True)
    assert rows[0].eu == rows[1].eu == 0.0
    assert DEC.choose(rows).action == "abstain" == DEC.ROUTE_ACTIONS[0]


def test_the_price_of_the_first_pass_counts_against_attempting() -> None:
    cheap, dear = _u(), {**_u(), RR.PRICE_KEY: 5.0}
    assert DEC.route_options(dear, True)[1].eu == pytest.approx(
        DEC.route_options(cheap, True)[1].eu - (5.0 - float(cheap[RR.PRICE_KEY])))
    assert _act(dear, True) == "abstain"


def test_an_attempt_at_a_question_with_no_span_answer_is_never_right() -> None:
    # q = 0: only V_other is left; with w_other = 0 the attempt is worth exactly -price
    u = _u(**{RR.q_key(False): 0.0, RR.WRONG_OTHER_KEY: 0.0})
    assert DEC.route_options(u, False)[1].eu == pytest.approx(-float(u[RR.PRICE_KEY]))


# --- the prior and the shipped row -----------------------------------------------------------

def test_with_no_fit_and_no_shipped_row_the_prior_declines_everything(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RR, "EXAMPLE", tmp_path / "also-none.json")
    assert RR.load(tmp_path / "none.json") == {}
    bare = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -9.0}
    assert [_act(bare, v) for v in (True, False)] == ["abstain", "abstain"]
    assert DEC.route_options(bare, True)[1].eu == pytest.approx(-2.8333, abs=1e-3)


def test_a_kb_with_no_fit_starts_from_the_shipped_row_and_a_fitted_one_wins(
        tmp_path: Path) -> None:
    assert RR.load(tmp_path / "absent.json") == _SHIPPED and set(_SHIPPED) == set(RR.KEYS)
    fit = tmp_path / "route_row.json"
    fit.write_text(json.dumps({"row": dict.fromkeys(RR.KEYS, 0.25)}), encoding="utf-8")
    assert RR.load(fit) == dict.fromkeys(RR.KEYS, 0.25)


def test_the_shipped_row_is_the_documented_fit() -> None:
    assert _SHIPPED[RR.q_key(True)] > 0.9 > 0.1 > _SHIPPED[RR.q_key(False)]
    assert _SHIPPED[RR.WRONG_OTHER_KEY] == _SHIPPED[RR.WRONG_KEY]   # the stated assumption


def test_the_estimators() -> None:
    assert RR.beta_mean(0, 21) == pytest.approx(1 / 23)
    got = RR.dirichlet_means({"right": 133, "wrong": 4, "declined": 174})
    assert sum(got.values()) == pytest.approx(1.0)
    assert got["wrong"] == pytest.approx(6 / 317)


# --- the decider's route stage ---------------------------------------------------------------

def _request(lookup: bool, price: float = 0.02) -> dict[str, object]:
    return {"stage": SEAM.STAGE_ROUTE, "question_id": "q1", "lookup": lookup, "price": price}


def test_the_decider_ranks_the_route_stage_and_the_view_names_the_effector() -> None:
    u = {k: v for k, v in _u().items() if k != RR.PRICE_KEY}
    attempt, decline = DCD.decide(_request(True), u), DCD.decide(_request(False), u)
    assert (attempt["effector"], attempt["act"]) == ("attempt", "attempt")
    assert (decline["effector"], decline["act"], decline["eu"]) == ("abstain", "abstain", 0.0)
    assert attempt["stage"] == decline["stage"] == SEAM.STAGE_ROUTE
    # the request's price is the row's price: dear enough, an accepted question is declined
    assert DCD.decide(_request(True, price=50.0), u)["effector"] == "abstain"
    assert attempt["eu"] == pytest.approx(DEC.route_options(
        {**u, RR.PRICE_KEY: 0.02}, True)[1].eu)


def test_the_handle_dispatches_on_the_stage() -> None:
    d = DCD.Decider(lambda: {k: v for k, v in _u().items() if k != RR.PRICE_KEY})
    assert d.decide("q1", _request(True))["effector"] == "attempt"


# --- one code path: the extracted argmax is the rule it was extracted from ---------------------

def test_choose_over_options_is_the_previous_bayes_act() -> None:
    rng = random.Random(20260930)
    grid = [c / 8 for c in range(9)]
    for _ in range(2000):
        u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -rng.uniform(1.5, 20.0),
             "lambda_int": rng.uniform(0.0, 0.5), "kappa_att": rng.uniform(0.0, 0.05),
             DEC.ASK_RECOVERY_KEY: rng.uniform(0.0, 1.0),
             **{k: rng.uniform(0.0, 0.5) for k in _SHIPPED if k.startswith("route")}}
        u.update(dict(zip(("gather_right_if_right", "gather_wrong_if_right"),
                          (rng.random() * 0.5, rng.random() * 0.5), strict=True)))
        n = rng.randint(0, 5)
        credences = [rng.choice(grid) / max(n, 1) for _ in range(n)]
        gathers = [(f"p{j}", rng.choice([0.0, 0.004, 0.02])) for j in range(rng.randint(0, 3))]
        rows = DEC.options(u, credences, gathers)
        previous = max(rows, key=lambda o: o.eu)   # the inline rule bayes_act was
        assert DEC.choose(rows) is previous
        assert DEC.bayes_act(u, credences, gathers) == previous


# --- the record ------------------------------------------------------------------------------

def test_a_route_decline_is_recorded_write_once_and_stays_out_of_the_fold(
        tmp_path: Path) -> None:
    from life_agent.core import decisions as DECS
    from life_agent.core import reactions as RX

    path = tmp_path / "decisions.jsonl"
    did = REC.record_route("q?", lookup=False, kind="list", eu=0.0, decisions_path=path)
    (row,) = DECS.read(path)
    assert row.decision_id == did and did.startswith("ab-")
    assert (row.regime, row.chosen_action, row.origin) == ("route", "abstain", "declined")
    assert row.posterior_summary["route"] == {"lookup": False, "kind": "list"}
    assert not RX.can_fold(row)
    # never the id of a miss on the same question
    assert did != REC.record_miss("q?", retrieval_keys=[], decisions_path=path)
