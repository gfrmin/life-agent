"""Router laws. Every constant here is a PUBLISHED run-18 figure, cited to its report,
so a failure means either the code drifted or the published reading did."""

from __future__ import annotations

import pytest

from life_agent.core import gate as GATE
from life_agent.core import router as R

# Run-18 / r28 published values (docs/unification/reports/r28-delta-decomposition.md:131).
ORACLE_P = 95 / 101          # pi* accuracy on DELIVERED answers = 0.9406
ORACLE_COST = 0.3751         # pi* mean $/q
LAMBDA_USD = 1.3311          # r28 production posterior mean
U_WRONG = -8.9993            # r28 production posterior mean

UBAR = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": U_WRONG,
        "u_hedged": 0.5, "lambda_usd": LAMBDA_USD}


def _resp(action, correct=None, cost=0.0, withheld=None):
    return GATE.RealisedResponse(action=action, correct=correct, cost_usd=cost,
                                 withheld=withheld)


def _paired(qid, typed, mono, answerable=True):
    return GATE.PairedOutcome(question_id=qid, answerable=answerable, typed=typed,
                              mono=mono)


# --- the pricing identity ----------------------------------------------------------

def test_escalate_eu_is_u_assert_minus_spend():
    """The escalate row derives from the ONE assert atom; it is not a second rule."""
    eu = R.escalate_eu(UBAR, oracle_p=ORACLE_P, oracle_cost=ORACLE_COST)
    expected = (ORACLE_P * 1.0 + (1 - ORACLE_P) * U_WRONG) - LAMBDA_USD * ORACLE_COST
    assert eu == pytest.approx(expected)


def test_current_gauge_makes_escalation_lose_to_silence():
    """THE FINDING. Under the published gauge the system is correct never to consult a
    94%-accurate oracle: EU(escalate) < EU(abstain) = 0. If this test starts failing,
    the gauge moved and the routing objective became reachable."""
    eu = R.escalate_eu(UBAR, oracle_p=ORACLE_P, oracle_cost=ORACLE_COST)
    assert eu < UBAR["u_abstain"]
    assert eu == pytest.approx(-0.0933, abs=5e-4)


def test_breakeven_u_wrong_is_shallower_than_the_gauge_in_use():
    """-7.43 vs the -8.9993 in use: the deployed behaviour flips on a number that was
    asserted, not elicited, and the margin is ~21%."""
    be = R.breakeven_u_wrong(oracle_p=ORACLE_P, lambda_usd=LAMBDA_USD,
                             oracle_cost=ORACLE_COST)
    assert be == pytest.approx(-7.4285, abs=1e-3)
    assert U_WRONG < be, "gauge in use is deeper than break-even, so escalation loses"


def test_breakeven_lambda_usd_is_below_the_rate_in_use():
    """1.082 vs the 1.3311 in use. Either lever alone flips the routing decision."""
    be = R.breakeven_lambda_usd(oracle_p=ORACLE_P, u_wrong=U_WRONG,
                                oracle_cost=ORACLE_COST)
    assert be == pytest.approx(1.0823, abs=1e-3)
    assert LAMBDA_USD > be


def test_breakevens_agree_at_the_indifference_point():
    """Cross-check: pricing at either break-even must zero the same EU."""
    be_u = R.breakeven_u_wrong(oracle_p=ORACLE_P, lambda_usd=LAMBDA_USD,
                               oracle_cost=ORACLE_COST)
    at_u = R.escalate_eu({**UBAR, "u_wrong": be_u}, oracle_p=ORACLE_P,
                         oracle_cost=ORACLE_COST)
    be_l = R.breakeven_lambda_usd(oracle_p=ORACLE_P, u_wrong=U_WRONG,
                                  oracle_cost=ORACLE_COST)
    at_l = R.escalate_eu({**UBAR, "lambda_usd": be_l}, oracle_p=ORACLE_P,
                         oracle_cost=ORACLE_COST)
    assert at_u == pytest.approx(0.0, abs=1e-9)
    assert at_l == pytest.approx(0.0, abs=1e-9)


def test_escalate_row_is_flat_over_the_simplex():
    """Flat because the oracle does not read our candidate list — which is exactly why
    it can rescue a dispersed row."""
    row = R.escalate_row(UBAR, 3, oracle_p=ORACLE_P, oracle_cost=ORACLE_COST)
    assert len(row) == 4
    assert len(set(row)) == 1


def test_free_perfect_oracle_beats_abstain():
    """Sanity in the other direction: the row is not structurally pinned below zero."""
    assert R.escalate_eu(UBAR, oracle_p=1.0, oracle_cost=0.0) == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_escalate_eu_refuses_non_probabilities(bad):
    with pytest.raises(ValueError):
        R.escalate_eu(UBAR, oracle_p=bad, oracle_cost=0.1)


# --- recombination -----------------------------------------------------------------

def test_router_keeps_typed_when_typed_asserted():
    p = _paired("q1", _resp("report", correct=True, cost=0.004),
                _resp("report", correct=False, cost=0.375))
    assert R.route(p) == p.typed


def test_router_takes_the_oracle_when_typed_withheld():
    p = _paired("q2", _resp("abstain", withheld=GATE.WITHHELD_DISPERSED, cost=0.004),
                _resp("report", correct=True, cost=0.375))
    out = R.route(p)
    assert out.action == "report" and out.correct is True


def test_escalation_pays_both_arms():
    """DR-ROUTE-1: charging only the oracle would flatter the router by the price of the
    retrieval it discarded."""
    p = _paired("q3", _resp("abstain", withheld=GATE.WITHHELD_DISPERSED, cost=0.004),
                _resp("report", correct=True, cost=0.375))
    assert R.route(p).cost_usd == pytest.approx(0.379)


def test_censored_rows_pass_through_untouched():
    """A row the corpus cannot answer measures the corpus, not the policy; routing it
    would launder an availability gap into a router win."""
    p = _paired("q4", _resp("abstain", withheld=GATE.WITHHELD_UNAVAILABLE),
                _resp("report", correct=True, cost=0.375))
    assert p.censored()
    assert R.route(p) == p.typed


def test_route_all_preserves_ids_and_the_oracle_arm():
    rows = [_paired("a", _resp("report", correct=True), _resp("report", correct=True)),
            _paired("b", _resp("abstain", withheld=GATE.WITHHELD_MISS),
                    _resp("report", correct=False))]
    out = R.route_all(rows)
    assert [r.question_id for r in out] == ["a", "b"]
    assert [r.mono for r in out] == [r.mono for r in rows]


# --- the headline recombination ----------------------------------------------------

def test_run18_shaped_router_outdelivers_both_arms_at_a_fraction_of_oracle_spend():
    """Run-18-SHAPED, not run 18 itself: the 36/3 split on the dispersed rows is derived
    from r27:133-134's stated mean gap, not a directly published contingency. The real
    numbers come from `scripts/route_arm.py` against the archived artifacts. This test
    pins the ARITHMETIC of the claim so that, when the true split lands, only the inputs
    change.

    Both arms are pinned to their PUBLISHED marginals (typed 61/2/41, pi* 95/6/3) so the
    fixture cannot flatter either side; only the JOINT — how pi* does on the rows typed
    withheld — is the derived part, and it is the one thing route_arm.py will replace.
    """
    #        n, typed action,                       typed ok, mono action, mono ok
    spec = [
        # rows typed answered (63): pi* gets 57 right, 3 wrong, abstains on 3
        (57, "report", True, "report", True),
        (2, "report", True, "report", False),
        (2, "report", True, "abstain", None),
        (1, "report", False, "report", False),
        (1, "report", False, "abstain", None),
        # the 39 dispersed rows: pi* right on 36, wrong on 3 (r27:133-134)
        (36, "abstain", None, "report", True),
        (3, "abstain", None, "report", False),
        # the 2 miss rows
        (2, "abstain", None, "report", True),
    ]
    rows, i = [], 0
    for n, ta, tok, ma, mok in spec:
        for _ in range(n):
            i += 1
            t = _resp(ta, correct=tok, cost=0.0036,
                      withheld=None if ta == "report" else GATE.WITHHELD_DISPERSED)
            m = _resp(ma, correct=mok, cost=ORACLE_COST,
                      withheld=None if ma == "report" else GATE.WITHHELD_MISS)
            rows.append(_paired(f"q{i}", t, m))
    assert len(rows) == 104

    typed = R.summarise([r.typed for r in rows])
    oracle = R.summarise([r.mono for r in rows])
    router = R.summarise([R.route(r) for r in rows])

    # both arms reproduce their published contingencies
    assert (typed.correct, typed.wrong, typed.withheld) == (61, 2, 41)
    assert (oracle.correct, oracle.wrong, oracle.withheld) == (95, 6, 3)

    # the claim
    assert router.withheld == 0
    assert (router.correct, router.wrong) == (99, 5)
    assert router.correct > oracle.correct > typed.correct
    assert router.wrong < oracle.wrong
    assert router.precision > oracle.precision
    assert router.total_cost < 0.45 * oracle.total_cost


def test_summarise_precision_is_over_delivered_not_asked():
    s = R.summarise([_resp("report", correct=True), _resp("report", correct=False),
                     _resp("abstain", withheld=GATE.WITHHELD_MISS)])
    assert (s.n, s.delivered) == (3, 2)
    assert s.precision == pytest.approx(0.5)


def test_summarise_of_a_silent_arm_has_no_precision():
    s = R.summarise([_resp("abstain", withheld=GATE.WITHHELD_MISS)])
    assert s.delivered == 0 and s.precision == 0.0
