"""The decision-weighted adoption gate's pure math (bayesian-foundations §8).

No IO, no skin: the utility posterior is constructed synthetically (it is just a frozen
dataclass of grid marginals), the paired outcomes are hand-built, and the Δ-posterior MC
is seeded — so the gate is a deterministic fold given its inputs. These tests pin the
realised-utility model, the two composed uncertainties (utility + the Bayesian
bootstrap), the verdict arithmetic, and the at-Ū diagnostics.

Run: uv run --project . python -m pytest tests/test_gate.py
"""
from __future__ import annotations

import pytest

from life_agent.core import gate as G
from life_agent.core import utility as UT

# --- synthetic utility posteriors --------------------------------------------------------

def _point(name: str, value: float) -> UT.LatentPosterior:
    """A degenerate latent — zero variance pinned at one value (sampling is then exact:
    gauss(value, 0) clamped to [value, value] = value)."""
    return UT.LatentPosterior(name=name, mean=value, variance=0.0, lo=value, hi=value)


def _posterior(*, u_wrong: float, u_hedged: float = 0.3, lambda_int: float = 0.5,
               kappa_att: float = 0.05) -> UT.UtilityPosterior:
    return UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={
            "u_wrong": _point("u_wrong", u_wrong),
            "u_hedged": _point("u_hedged", u_hedged),
            "lambda_int": _point("lambda_int", lambda_int),
            "kappa_att": _point("kappa_att", kappa_att),
        },
        n_events=0, fold_version="test",
    )


def _resp(action: str, correct: bool | None = None,
          withheld: str | None = None) -> G.RealisedResponse:
    return G.RealisedResponse(action=action, correct=correct, withheld=withheld)


def _pair(qid: str, typed: G.RealisedResponse, mono: G.RealisedResponse,
          answerable: bool = True) -> G.PairedOutcome:
    return G.PairedOutcome(question_id=qid, answerable=answerable, typed=typed, mono=mono)


# --- the realised-utility model (stated) -------------------------------------------------

def test_realised_utility_prices_realised_spend_under_lambda_usd() -> None:
    # run-6 semantics (pre-registered in the run-5 §14 addendum): each arm's REALISED
    # per-question spend enters Δ as -lambda_usd*cost_usd, on every action — money
    # spent is spent whether the act reported or abstained.
    u = {"u_correct": 1.0, "u_wrong": -2.0, "u_abstain": 0.0, "u_hedged": 0.3,
         "u_wrong_scoped": -1.0, "lambda_int": 0.5, "lambda_usd": 2.0}
    ok = G.RealisedResponse(action="report", correct=True, cost_usd=0.4)
    assert G.realised_utility(ok, u, oracle_p=0.9) == 1.0 - 0.8
    ab = G.RealisedResponse(action="abstain", cost_usd=0.1)
    assert G.realised_utility(ab, u, oracle_p=0.9) == 0.0 - 0.2


def test_realised_utility_without_the_rate_latent_is_byte_identical() -> None:
    # the run-5-comparability pin: a utility sample from a model that lacks lambda_usd
    # (every run before the elicitation channel) prices spend at exactly zero — the old
    # Δ, byte for byte, cost fields present or not.
    u = {"u_correct": 1.0, "u_wrong": -2.0, "u_abstain": 0.0, "u_hedged": 0.3,
         "u_wrong_scoped": -1.0, "lambda_int": 0.5}
    priced = G.RealisedResponse(action="report", correct=True, cost_usd=0.4)
    assert G.realised_utility(priced, u, oracle_p=0.9) == 1.0
    assert G.RealisedResponse(action="report", correct=True).cost_usd == 0.0


def test_realised_utility_recovers_the_gauge_and_latents() -> None:
    u = {"u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -2.0, "u_hedged": 0.3,
         "lambda_int": 0.5}
    assert G.realised_utility(_resp("report", True), u, oracle_p=0.9) == 1.0
    assert G.realised_utility(_resp("report", False), u, oracle_p=0.9) == -2.0
    assert G.realised_utility(_resp("abstain"), u, oracle_p=0.9) == 0.0
    assert G.realised_utility(_resp("hedge", True), u, oracle_p=0.9) == 0.3
    assert G.realised_utility(_resp("hedge", False), u, oracle_p=0.9) == -2.0
    # ask_clarify is priced by the owner-oracle prior against the interruption cost
    assert G.realised_utility(_resp("ask_clarify"), u, oracle_p=0.9) == 0.9 * 1.0 - 0.5


def test_realised_report_token_boundary() -> None:
    # the shared FTS matcher: 123456789 does NOT match inside 1123456789
    assert G.realised_report(["your id is 123456789"], "123456789", [])
    assert not G.realised_report(["your id is 1123456789"], "123456789", [])
    assert G.realised_report(["expires 14/08/2031"], "2031-08-14", ["14/08/2031"])
    # an unanswerable question (empty gold) is never a correct report
    assert not G.realised_report(["anything at all"], "", [])


# --- the Δ posterior: the two composed uncertainties -------------------------------------

def test_delta_mean_tracks_sample_mean_under_point_utility() -> None:
    # under a point-mass U the gaps are fixed (d = [0, +2]); the Bayesian bootstrap still
    # carries corpus uncertainty, so Δ_draw = 2·w_b ~ Uniform(0, 2). The MEAN converges
    # to the sample mean (1.0), but at Ū the diagnostic gap is exact.
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("report", True), _resp("report", True)),     # d = 1-1 = 0
              _pair("b", _resp("abstain"), _resp("report", False))]          # d = 0-(-2) = +2
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=4000, seed=1)
    assert abs(res.delta_mean - 1.0) < 0.05               # MC, not a spike
    assert abs(res.diagnostics.overall_mean_d - 1.0) < 1e-9   # at-Ū is exact
    # P(Δ > 0.05) = P(2·w_b > 0.05) = P(w_b > 0.025) ≈ 0.975 — clears the 0.90 gate
    assert res.p_delta_gt > 0.9 and res.passed


def test_gate_hinges_on_u_wrong_the_decision_weighted_property() -> None:
    # typed abstains where monolithic reports-wrong: the gap's sign is u_wrong's.
    paired = [_pair("a", _resp("abstain"), _resp("report", False)) for _ in range(8)]
    costly = G.delta_posterior(paired, _posterior(u_wrong=-2.0), oracle_p=0.9,
                               n_draws=4000, seed=2)
    cheap = G.delta_posterior(paired, _posterior(u_wrong=-0.01), oracle_p=0.9,
                              n_draws=4000, seed=2)
    assert costly.passed and costly.delta_mean > 1.5    # abstaining beats wrong reports
    assert not cheap.passed and cheap.delta_mean < 0.05  # wrong is ~free ⇒ no material gap


def test_bootstrap_widens_the_interval_with_dispersed_gaps() -> None:
    # mixed per-question gaps ⇒ the Bayesian bootstrap carries real corpus uncertainty:
    # the central interval must be non-degenerate.
    post = _posterior(u_wrong=-1.0)
    paired = [_pair("a", _resp("report", True), _resp("abstain")),       # d = +1
              _pair("b", _resp("abstain"), _resp("report", True)),       # d = -1
              _pair("c", _resp("report", True), _resp("report", False)), # d = +2
              _pair("d", _resp("abstain"), _resp("abstain"))]            # d = 0
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=8000, seed=3)
    assert res.delta_hi - res.delta_lo > 0.3
    assert res.delta_lo < res.delta_mean < res.delta_hi


def test_seed_makes_the_fold_deterministic() -> None:
    post = _posterior(u_wrong=-1.5)
    paired = [_pair("a", _resp("report", True), _resp("report", False)),
              _pair("b", _resp("abstain"), _resp("report", False))]
    a = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=3000, seed=42)
    b = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=3000, seed=42)
    assert a.p_delta_gt == b.p_delta_gt and a.delta_mean == b.delta_mean


def test_utility_uncertainty_propagates_into_p_gt() -> None:
    # a u_wrong spread straddling the materiality boundary ⇒ p_gt strictly interior, NOT a point
    # 0/1 — utility uncertainty is inside the gate. d = -u_wrong for this pair, so the boundary
    # d > δ=0.05 is u_wrong < -0.05; a Gaussian centred at the boundary puts ~half the mass clear.
    spread = UT.LatentPosterior(name="u_wrong", mean=-0.05, variance=1.0, lo=-3.0, hi=0.0)
    post = UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": spread, "u_hedged": _point("u_hedged", 0.3),
                 "lambda_int": _point("lambda_int", 0.5),
                 "kappa_att": _point("kappa_att", 0.05)},
        n_events=2, fold_version="spread")
    paired = [_pair("a", _resp("abstain"), _resp("report", False))]  # d = -u_wrong ∈ {3, 0}
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=8000, seed=7)
    assert 0.3 < res.p_delta_gt < 0.7   # ~half the U-mass clears δ


# --- diagnostics: the disagreement region + answer rates --------------------------------

def test_disagreement_region_and_answer_rates() -> None:
    post = _posterior(u_wrong=-1.0)
    paired = [
        _pair("a", _resp("report", True), _resp("report", True)),    # agree (both assert)
        _pair("b", _resp("abstain"), _resp("report", False)),        # DISagree
        _pair("c", _resp("report", True), _resp("abstain")),         # DISagree
        _pair("d", _resp("abstain"), _resp("abstain")),              # agree (both withhold)
        _pair("u", _resp("abstain"), _resp("report", False), answerable=False),  # unanswerable
    ]
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=2000, seed=5)
    d = res.diagnostics
    assert d.n == 5 and d.n_answerable == 4
    # disagree = asserts(typed) != asserts(mono): b (abstain/report), c (report/abstain),
    # u (abstain/report) — three, the unanswerable counts too
    assert d.disagreement_n == 3
    # answer rate = asserts on answerable / answerable. typed asserts a,c ⇒ 2/4;
    # mono asserts a,b on answerable (c,d abstain; u excluded) ⇒ 2/4
    assert d.typed_answer_rate == 0.5
    assert d.mono_answer_rate == 0.5
    # correct-report rate on answerable: typed a,c correct ⇒ 2/4; mono only a ⇒ 1/4
    assert d.typed_correct_rate == 0.5
    assert d.mono_correct_rate == 0.25
    # the action-pair contingency keys are (typed, mono)
    assert d.action_pairs[("report", "report")].n == 1
    assert d.action_pairs[("abstain", "report")].n == 2  # b and u


def test_empty_corpus_is_honest() -> None:
    res = G.delta_posterior([], _posterior(u_wrong=-1.0), oracle_p=0.9,
                            n_draws=100, seed=1)
    assert res.diagnostics.n == 0 and not res.passed
    assert res.diagnostics.typed_answer_rate is None


# --- availability censoring (foundations §14, registered blind before run 6) --------------

def test_no_censored_rows_is_byte_identical_to_the_uncensored_delta() -> None:
    # THE comparability pin, the lambda_usd precedent applied to this registration: the
    # censoring machinery must be provably inert on a corpus that censors nothing —
    # otherwise landing it silently re-prices run 6 against runs 3-5.
    post = _posterior(u_wrong=-2.0)
    bare = [_pair("a", _resp("abstain"), _resp("report", True)),
            _pair("b", _resp("report", True), _resp("report", False)),
            _pair("c", _resp("abstain"), _resp("abstain"))]
    # the same rows, now carrying withholding reasons — annotation only, nothing censored
    tagged = [_pair("a", _resp("abstain", withheld=G.WITHHELD_MISS), _resp("report", True)),
              _pair("b", _resp("report", True), _resp("report", False)),
              _pair("c", _resp("abstain", withheld=G.WITHHELD_DISPERSED), _resp("abstain"))]
    a = G.delta_posterior(bare, post, oracle_p=0.9, n_draws=2000, seed=11)
    b = G.delta_posterior(tagged, post, oracle_p=0.9, n_draws=2000, seed=11)
    assert (a.delta_mean, a.delta_lo, a.delta_hi, a.p_delta_gt) == \
           (b.delta_mean, b.delta_lo, b.delta_hi, b.p_delta_gt)
    assert b.diagnostics.n_censored == 0
    assert b.diagnostics.withheld_reasons == {G.WITHHELD_MISS: 1, G.WITHHELD_DISPERSED: 1}


def test_censored_rows_leave_delta_but_stay_in_diagnostics() -> None:
    # an unavailable row measures the CORPUS, not the policy: it must not weigh on Δ, and
    # it must still be visible — censoring that hid the row would be indistinguishable
    # from a corpus that never had the question.
    post = _posterior(u_wrong=-2.0)
    keep = [_pair("a", _resp("report", True), _resp("report", True)),
            _pair("b", _resp("report", True), _resp("report", True))]
    plus_censored = [
        *keep,
        _pair("z", _resp("abstain", withheld=G.WITHHELD_UNAVAILABLE), _resp("report", True))]
    a = G.delta_posterior(keep, post, oracle_p=0.9, n_draws=2000, seed=7)
    b = G.delta_posterior(plus_censored, post, oracle_p=0.9, n_draws=2000, seed=7)
    # Δ is computed over the SAME two rows, so the whole posterior is identical
    assert (a.delta_mean, a.delta_lo, a.delta_hi) == (b.delta_mean, b.delta_lo, b.delta_hi)
    # ...while the diagnostics still see all three, and name the removed bias
    assert b.diagnostics.n == 3 and b.diagnostics.n_censored == 1
    assert b.diagnostics.censored_mean_d is not None and b.diagnostics.censored_mean_d < 0
    assert ("abstain", "report") in b.diagnostics.action_pairs


def test_a_fully_censored_corpus_fails_rather_than_looking_normal() -> None:
    # the guard tests the INCLUDED rows: a box that can answer nothing has no evidence,
    # and must say so — silently returning a well-formed zero-Δ result would read as a
    # measured tie between the arms.
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain", withheld=G.WITHHELD_UNAVAILABLE),
                    _resp("report", True))]
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=100, seed=1)
    assert not res.passed and res.n_draws == 0
    assert res.diagnostics.n == 1 and res.diagnostics.n_censored == 1


def test_withheld_reason_is_a_closed_set_and_assertions_cannot_carry_one() -> None:
    # the reason is a claim about the decision; an unknown one is a typo that would
    # silently never censor, and an asserting action has nothing to withhold.
    with pytest.raises(ValueError):
        G.RealisedResponse(action="abstain", withheld="unavailble")  # typo
    with pytest.raises(ValueError):
        G.RealisedResponse(action="report", correct=True, withheld=G.WITHHELD_MISS)


def test_report_publishes_what_delta_was_computed_over() -> None:
    # the disclosure the §14 registration demands: if the published n and the published Δ
    # disagree about which rows counted, the reading is not auditable.
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("report", True), _resp("report", True)),
              _pair("z", _resp("abstain", withheld=G.WITHHELD_UNAVAILABLE),
                    _resp("report", True))]
    md = G.render_report(G.delta_posterior(paired, post, oracle_p=0.9, n_draws=500, seed=3),
                         run_id="gate-test", elapsed=1.0)
    assert "censored from Δ: 1" in md
    assert "Δ was computed over 1 question(s)" in md


def test_report_discloses_zero_censoring_when_reasons_are_recorded() -> None:
    # "0 censored" is itself the disclosure — a block that appeared only when censoring
    # bit would make its absence ambiguous (nothing censored? or not checked?).
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain", withheld=G.WITHHELD_MISS), _resp("report", True)),
              _pair("b", _resp("report", True), _resp("report", True))]
    md = G.render_report(G.delta_posterior(paired, post, oracle_p=0.9, n_draws=500, seed=3),
                         run_id="gate-test", elapsed=1.0)
    assert "censored from Δ: 0" in md and "miss 1" in md


# --- the frozen-blind constants (drift gate) --------------------------------------------

def test_gate_constants_are_frozen() -> None:
    # δ and the level are frozen in the gate's definition BEFORE any result is seen
    # (§8 blind-comparison discipline). A change here is a deliberate re-statement.
    assert G.MATERIALITY_DELTA == 0.05
    assert G.GATE_LEVEL == 0.90
    assert frozenset({"report", "report_scoped", "hedge"}) == G.ASSERT_ACTIONS
    assert frozenset({"abstain", "ask_clarify"}) == G.WITHHOLD_ACTIONS


def test_render_report_names_the_verdict_and_diagnostics() -> None:
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain"), _resp("report", False)),
              _pair("b", _resp("report", True), _resp("report", True))]
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=2000, seed=9)
    md = G.render_report(res, run_id="gate-test", elapsed=1.0)
    assert "PASS" in md or "FAIL" in md
    assert "P(Δ" in md and "0.05" in md         # materiality named
    assert "answer rate" in md.lower()
    assert "disagreement" in md.lower()
    assert "frozen" in md.lower()               # the blind-comparison note
