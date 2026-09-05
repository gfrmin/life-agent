"""The honest verdict — owner ruling 2026-09-05 (`a3-regime-conferral`, `M-34`).

The A3 gate keeps its blind regime (`frozen-elicitations`): the anti-circularity guard stands,
because reactions are projected from verdicts on the very decision log the gate scores, and a
gate that folded them would grade a policy with a yardstick that policy's own outcomes moved.
The price of keeping it is that the gate PRICES under one Ū and SCORES under another (`M-33`),
and when the measured marginal reach falls strictly between the two break-evens the verdict's
sign belongs to the pairing, not to the policy. r49 sat exactly there — 24 marginal commits at
0.875, between 0.8369 and 0.9000 — and was quoted as a FAIL.

The ruling: such a reading is **INCONCLUSIVE**, neither PASS nor FAIL. It adopts nothing and it
does not advance the consecutive-FAIL stop rule; its remedy is evidence (a sharper `p1`, or the
two estimates of `u_wrong` converging), never a softer bar.

Pinned here: the closed verdict vocabulary; the rule (straddle ⇒ INCONCLUSIVE, otherwise the
arithmetic's PASS/FAIL); that a reading which declares no pairing SAYS so instead of
defaulting; and that the ONE report renderer cannot render without being told (r28: a default
is the vector).
"""
from __future__ import annotations

import pytest

from life_agent.core import gate as G
from life_agent.core import utility as UT

# The two regimes r49 actually spanned — utility posterior MEANS, which the shadow's own boot
# record already declares publishable (seven scalar utility means: no PII, no corpus content).
DEPLOYED = {"u_correct": 1.0, "u_wrong": -5.130990272278651}
BLIND = {"u_correct": 1.0, "u_wrong": -8.9993}
R49_REACH = 0.875  # 21 of 24 marginal commits correct


def _point(name: str, value: float) -> UT.LatentPosterior:
    return UT.LatentPosterior(name=name, mean=value, variance=0.0, lo=value, hi=value)


def _posterior(*, u_wrong: float) -> UT.UtilityPosterior:
    return UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": _point("u_wrong", u_wrong),
                 "u_hedged": _point("u_hedged", 0.3),
                 "lambda_int": _point("lambda_int", 0.5),
                 "kappa_att": _point("kappa_att", 0.05),
                 "lambda_usd": _point("lambda_usd", 0.0)},
        n_events=0, fold_version="test", policy="frozen-elicitations")


def _resp(action: str, correct: bool | None = None,
          withheld: str | None = None) -> G.RealisedResponse:
    return G.RealisedResponse(action=action, correct=correct, withheld=withheld, cost_usd=0.0)


def _pair(qid: str, typed: G.RealisedResponse, mono: G.RealisedResponse) -> G.PairedOutcome:
    return G.PairedOutcome(question_id=qid, answerable=True, typed=typed, mono=mono)


def _result(*, passing: bool) -> G.GateResult:
    """A gate arithmetic that PASSES (typed reports correct where the baseline withheld on
    every row: Δ = +1 in every draw) or FAILS (the mirror image: Δ = -1)."""
    typed, mono = ((_resp("report", True), _resp("abstain")) if passing
                   else (_resp("abstain"), _resp("report", True)))
    paired = [_pair(f"q{i}", typed, mono) for i in range(12)]
    res = G.delta_posterior(paired, _posterior(u_wrong=-2.0), oracle_p=0.9,
                            n_draws=1000, seed=1)
    assert res.passed is passing, "fixture premise: the arithmetic must be unambiguous"
    return res


def _pairing() -> G.RegimePairing:
    return G.regime_pairing(pricing_u_bar=DEPLOYED, pricing_policy="all-to-date",
                            scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")


# --- the vocabulary and the rule ---------------------------------------------------------

def test_the_verdict_vocabulary_is_closed_and_has_three_members() -> None:
    assert G.VERDICTS == ("PASS", "FAIL", "INCONCLUSIVE")


@pytest.mark.parametrize("passing", [True, False])
def test_a_straddling_reach_is_inconclusive_whatever_the_arithmetic_says(passing: bool) -> None:
    """r49's configuration. MUST FAIL if `verdict` reads `passed` while the pairing bites —
    that is precisely the FAIL r49 was not entitled to quote."""
    assert G.verdict(_result(passing=passing), pairing=_pairing(),
                     reach_rate=R49_REACH) == "INCONCLUSIVE"


@pytest.mark.parametrize("reach", [0.95, 0.50])
def test_a_reach_outside_the_pairing_yields_the_arithmetics_verdict(reach: float) -> None:
    assert G.verdict(_result(passing=True), pairing=_pairing(), reach_rate=reach) == "PASS"
    assert G.verdict(_result(passing=False), pairing=_pairing(), reach_rate=reach) == "FAIL"


def test_no_marginal_commit_means_the_pairing_cannot_bite() -> None:
    assert G.verdict(_result(passing=True), pairing=_pairing(), reach_rate=None) == "PASS"
    assert G.verdict(_result(passing=False), pairing=_pairing(), reach_rate=None) == "FAIL"


def test_the_break_evens_themselves_do_not_straddle() -> None:
    """Endpoints are exactly break-even under one regime; the sign is carried by the rest of
    the reading (the `straddles` contract, bound here at the verdict)."""
    p = _pairing()
    for edge in (p.pricing_break_even, p.scoring_break_even):
        assert G.verdict(_result(passing=False), pairing=p, reach_rate=edge) == "FAIL"


def test_a_coincident_pairing_never_straddles() -> None:
    same = G.regime_pairing(pricing_u_bar=BLIND, pricing_policy="frozen-elicitations",
                            scoring_u_bar=BLIND, scoring_policy="frozen-elicitations")
    assert G.verdict(_result(passing=False), pairing=same, reach_rate=R49_REACH) == "FAIL"


def test_an_undeclared_pairing_yields_the_arithmetics_verdict() -> None:
    assert G.verdict(_result(passing=True), pairing=None, reach_rate=None) == "PASS"
    assert G.verdict(_result(passing=False), pairing=None, reach_rate=None) == "FAIL"


# --- the marginal-commit table, declared once at the gate --------------------------------

def test_marginal_commits_are_typed_asserts_where_the_baseline_withheld() -> None:
    paired = [_pair("a", _resp("report", True), _resp("abstain")),
              _pair("b", _resp("report", False), _resp("abstain")),
              _pair("c", _resp("report", True), _resp("report", True)),      # shared commit
              _pair("d", _resp("abstain"), _resp("report", True)),           # the reverse cell
              _pair("e", _resp("abstain", withheld="miss"), _resp("abstain"))]
    m = G.marginal_commits(paired)
    assert (m.n, m.correct, m.reverse) == (2, 1, 1)
    assert m.rate == pytest.approx(0.5)
    assert m.as_record() == {"n": 2, "correct": 1, "rate": 0.5, "abstain_x_report": 1}


def test_marginal_commits_rate_is_none_when_nothing_is_marginal() -> None:
    m = G.marginal_commits([_pair("a", _resp("abstain"), _resp("abstain"))])
    assert (m.n, m.rate) == (0, None)


# --- the ONE report renderer ---------------------------------------------------------------

def _render(res: G.GateResult, *, pairing: G.RegimePairing | None,
            reach_rate: float | None) -> str:
    return G.render_report(res, run_id="gate-test", elapsed=0.0,
                           baseline="raw-deliberative-replay", pairing=pairing,
                           reach_rate=reach_rate)


def test_the_report_publishes_inconclusive_with_both_break_evens_and_the_reason() -> None:
    md = _render(_result(passing=False), pairing=_pairing(), reach_rate=R49_REACH)
    assert "## Verdict: **INCONCLUSIVE**" in md
    assert "**PASS**" not in md and "**FAIL**" not in md, "an inconclusive reading quotes no sign"
    assert "0.8369" in md and "0.9000" in md and "0.875" in md
    assert "pairing-sensitive" in md
    assert "consecutive" in md, "the report must say the stop rule does not advance"


def test_the_report_quotes_the_arithmetics_verdict_when_the_reach_is_clear() -> None:
    md = _render(_result(passing=True), pairing=_pairing(), reach_rate=0.95)
    assert "## Verdict: **PASS**" in md and "INCONCLUSIVE" not in md.split("## Verdict")[1][:40]
    assert "outside" in md, "the pairing block still publishes both break-evens (M-31)"


def test_a_report_without_a_declared_pairing_says_so() -> None:
    md = _render(_result(passing=True), pairing=None, reach_rate=None)
    assert "## Verdict: **PASS**" in md
    assert "not declared" in md.lower()


def test_a_report_cannot_render_without_naming_its_pairing() -> None:
    """r28: a default is the vector. A caller that has not thought about the regimes it spans
    must not be handed a PASS/FAIL that looks like every other one."""
    with pytest.raises(TypeError):
        G.render_report(_result(passing=True), run_id="gate-test", elapsed=0.0,
                        baseline="raw-deliberative-replay")   # type: ignore[call-arg]


def test_the_live_gate_declares_its_pairing_rather_than_passing_none() -> None:
    """run_eval's typed arm decides under the live Ū and its gate scores blind — the classic
    gate spans the pairing exactly as the A3 harness does. MUST FAIL if its one report call
    hands `pairing=None` (the r28 source-level guard, applied to the regime)."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts" / "run_eval.py").read_text(
        encoding="utf-8")
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", None) == "render_report"]
    assert len(calls) == 1, "run_eval renders exactly one gate report"
    kws = {k.arg: k.value for k in calls[0].keywords}
    assert isinstance(kws["pairing"], ast.Name) and kws["pairing"].id == "pairing", (
        "the live gate must declare the pairing it spans, never `None`")
    assert isinstance(kws["reach_rate"], ast.Attribute), (
        "the reach must come from the gate's own marginal table (`marginal.rate`)")
