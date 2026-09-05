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
            # E-5 (M4): every model carries the exchange rate; 0.0 keeps these tests'
            # pinned numbers (no priced rows ride through this fixture)
            "lambda_usd": _point("lambda_usd", 0.0),
        },
        n_events=0, fold_version="test", policy="frozen-elicitations",
    )


def _resp(action: str, correct: bool | None = None,
          withheld: str | None = None, cost_usd: float = 0.0) -> G.RealisedResponse:
    return G.RealisedResponse(action=action, correct=correct, withheld=withheld,
                              cost_usd=cost_usd)


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


def test_realised_utility_without_the_rate_latent_fails_loud() -> None:
    # E-5 (M4, r14): the run-5 comparability pin RETIRED — lambda_usd is REQUIRED of
    # every model (load_model fails loud without it), so a u vector lacking it can only
    # be a hand-built or archived pre-elicitation artefact; pricing it silently at zero
    # was the two-defaults defect. Loud, never quietly unpriced.
    u = {"u_correct": 1.0, "u_wrong": -2.0, "u_abstain": 0.0, "u_hedged": 0.3,
         "u_wrong_scoped": -1.0, "lambda_int": 0.5}
    priced = G.RealisedResponse(action="report", correct=True, cost_usd=0.4)
    with pytest.raises(KeyError, match="lambda_usd"):
        G.realised_utility(priced, u, oracle_p=0.9)
    assert G.RealisedResponse(action="report", correct=True).cost_usd == 0.0


def test_realised_utility_recovers_the_gauge_and_latents() -> None:
    u = {"lambda_usd": 0.0, "u_correct": 1.0, "u_abstain": 0.0, "u_wrong": -2.0, "u_hedged": 0.3,
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
                 "kappa_att": _point("kappa_att", 0.05),
                 "lambda_usd": _point("lambda_usd", 0.0)},
        n_events=2, fold_version="spread", policy="frozen-elicitations")
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
                         run_id="gate-test", elapsed=1.0, baseline="monolithic",
                         pairing=None, reach_rate=None)
    assert "censored from Δ: 1" in md
    assert "Δ was computed over 1 question(s)" in md


def test_report_discloses_zero_censoring_when_reasons_are_recorded() -> None:
    # "0 censored" is itself the disclosure — a block that appeared only when censoring
    # bit would make its absence ambiguous (nothing censored? or not checked?).
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain", withheld=G.WITHHELD_MISS), _resp("report", True)),
              _pair("b", _resp("report", True), _resp("report", True))]
    md = G.render_report(G.delta_posterior(paired, post, oracle_p=0.9, n_draws=500, seed=3),
                         run_id="gate-test", elapsed=1.0, baseline="monolithic",
                         pairing=None, reach_rate=None)
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
    md = G.render_report(res, run_id="gate-test", elapsed=1.0, baseline="monolithic",
                         pairing=None, reach_rate=None)
    assert "PASS" in md or "FAIL" in md
    assert "P(Δ" in md and "0.05" in md         # materiality named
    assert "answer rate" in md.lower()
    assert "disagreement" in md.lower()
    assert "frozen" in md.lower()               # the blind-comparison note


# --- r27: the report must name the baseline arm it ACTUALLY ran against -----------------
# `render_report` hard-coded "monolithic" in its title and in both diagnostic labels while
# the baseline arm is chosen by the caller. Every gate report in the §14 series since run 6
# ran against the raw-deliberative replay — Claude Code with corpus access, the owner's own
# outside option — and every one of them was TITLED as a comparison against the monolithic
# single-call instrument. The paired rows carried the right tag the whole time; only the
# prose lied, and the prose is what gets quoted.

def test_the_report_names_the_baseline_arm_it_ran_against() -> None:
    """r27. MUST FAIL if the report can name a baseline the run did not use. Killed by
    restoring the hard-coded 'monolithic' in the title or either rate label."""
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain"), _resp("report", False)),
              _pair("b", _resp("report", True), _resp("report", True))]
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=2000, seed=9)

    md = G.render_report(res, run_id="gate-test", elapsed=1.0,
                         baseline="raw-deliberative-replay", pairing=None, reach_rate=None)
    assert "raw-deliberative-replay" in md, "the report did not name its baseline arm"
    assert "monolithic" not in md.lower(), (
        "the report names 'monolithic' while running against a different arm — the label "
        "is what gets quoted into the ledger, and this one was quoted for twelve runs")


def test_the_monolithic_baseline_is_still_named_when_it_is_the_one_used() -> None:
    """r27, the discriminating half (row 23): the fix must name the arm, not delete the
    word. A renderer that never says 'monolithic' would pass the test above while being
    just as wrong on a monolithic run. Killed by hard-coding any single arm name."""
    post = _posterior(u_wrong=-2.0)
    paired = [_pair("a", _resp("abstain"), _resp("report", False))]
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=500, seed=9)
    md = G.render_report(res, run_id="gate-test", elapsed=1.0, baseline="monolithic",
                         pairing=None, reach_rate=None)
    assert "monolithic" in md.lower()


# --- r28: the Δ decomposition -----------------------------------------------------------
# The §8 headline is a single number and twelve runs have been read from it. Recomputed on
# run 18's own rows at the elicited latents, Δ reads +0.577 as run and +0.014 with the
# baseline arm's spend uncharged: the entire margin is the price term, and the arms are
# level on delivered answers. A report that publishes only the total cannot show that, so
# every reading since run 6 has been unable to separate an answer-quality effect from a
# price effect. These tests pin the split.
#
# The decomposition is exact rather than approximate: `realised_utility` is affine in the
# sampled latents given the actions, so Δ = Δ_answers + lambda_usd·(c̄_mono - c̄_typed)
# holds per draw and therefore at Ū.

def _decomposition_fixture() -> tuple[list[G.PairedOutcome], UT.UtilityPosterior]:
    """Three rows, one of them CENSORED, with spend on every arm. Built so that the
    included-set mean (5.70) differs from the all-rows mean (3.80) — the row set is
    therefore observable, and a decomposition computed over the wrong one fails the
    identity rather than passing quietly."""
    post = UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": _point("u_wrong", -2.0),
                 "u_hedged": _point("u_hedged", 0.3),
                 "lambda_int": _point("lambda_int", 0.5),
                 "kappa_att": _point("kappa_att", 0.05),
                 "lambda_usd": _point("lambda_usd", 2.0)},
        n_events=0, fold_version="test", policy="frozen-elicitations")
    paired = [
        # censored: this machine's catalogue cannot answer it, so Δ never sees it
        _pair("a", _resp("abstain", withheld=G.WITHHELD_UNAVAILABLE, cost_usd=0.5),
              _resp("report", True, cost_usd=1.0)),
        _pair("b", _resp("report", True, cost_usd=0.1),
              _resp("report", False, cost_usd=2.0)),
        _pair("c", _resp("abstain", withheld=G.WITHHELD_DISPERSED, cost_usd=0.2),
              _resp("report", True, cost_usd=3.0)),
    ]
    return paired, post


def test_decomposition_terms_are_each_independently_correct() -> None:
    """r28 C2. Three pins, each against a hand-computed value, so an error in ANY one term
    fails — a single identity assertion would pass with two compensating errors.

    Included rows are b and c (a is censored).
      spend:   typed (0.1+0.2)/2 = 0.15   mono (2.0+3.0)/2 = 2.50
               Δ_spend = lambda_usd·(2.50 - 0.15) = 2.0 · 2.35 = 4.70
      answers: b  typed +1.0, mono -2.0 → +3.0
               c  typed  0.0, mono +1.0 → -1.0
               Δ_answers = (3.0 - 1.0)/2 = 1.00
      total:   5.70

    MUST FAIL on a wrong sign in the spend term, on using one arm's cost for both, and on
    computing any term over all three rows instead of the two Δ actually folds.
    """
    paired, post = _decomposition_fixture()
    d = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=200, seed=1).diagnostics
    assert d.typed_arm is not None and d.mono_arm is not None
    assert d.typed_arm.mean_spend_usd == pytest.approx(0.15)
    assert d.mono_arm.mean_spend_usd == pytest.approx(2.50)
    assert d.delta_spend == pytest.approx(4.70)
    assert d.delta_answers == pytest.approx(1.00)
    assert d.included_mean_d == pytest.approx(5.70)


def test_decomposition_is_folded_over_the_rows_delta_folds() -> None:
    """r28 C1, the discriminating half. The split must be computed over the SAME rows Δ is
    computed over — post-censoring. Diagnostics deliberately fold every row elsewhere, so
    reusing that set here is the natural mistake. MUST FAIL if any term is folded over all
    three rows: the all-rows gap is 3.80 against the included set's 5.70."""
    paired, post = _decomposition_fixture()
    d = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=200, seed=1).diagnostics
    assert d.overall_mean_d == pytest.approx(3.80), "the all-rows diagnostic moved"
    assert d.included_mean_d == pytest.approx(5.70)
    assert d.included_mean_d != d.overall_mean_d
    assert d.delta_answers is not None and d.delta_spend is not None
    assert d.delta_answers + d.delta_spend == pytest.approx(d.included_mean_d)


def test_arm_summaries_count_outcomes_over_the_included_rows() -> None:
    """r28 C1: each arm's correct / wrong / abstain counts, published beside the split so a
    reader can see WHICH arm the answer term came from. Included rows b and c: typed reports
    once (correct) and abstains once; the baseline reports twice, one right one wrong.
    MUST FAIL if the counts fold the censored row or read the wrong arm."""
    paired, post = _decomposition_fixture()
    d = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=200, seed=1).diagnostics
    assert d.typed_arm is not None and d.mono_arm is not None
    assert (d.typed_arm.n_correct, d.typed_arm.n_wrong, d.typed_arm.n_abstain) == (1, 0, 1)
    assert (d.mono_arm.n_correct, d.mono_arm.n_wrong, d.mono_arm.n_abstain) == (1, 1, 0)


def test_the_answer_term_is_the_deployed_rule_with_the_rate_zeroed() -> None:
    """r28: the standing lesson — a census reads the deployed rule end to end, never
    re-implements the constant it prices. Δ_answers must be `realised_utility` valued at
    lambda_usd = 0, so a change to the deployed utility model reaches it automatically.
    Pinned by construction: a second spelling of the answer term would not track a change
    to u_hedged, which no other assertion in this file exercises through the split.
    MUST FAIL if the answer term is written out separately from realised_utility."""
    post = UT.UtilityPosterior(
        gauge={"u_correct": 1.0, "u_abstain": 0.0},
        latents={"u_wrong": _point("u_wrong", -2.0),
                 "u_hedged": _point("u_hedged", 0.75),   # the tracked latent
                 "lambda_int": _point("lambda_int", 0.5),
                 "kappa_att": _point("kappa_att", 0.05),
                 "lambda_usd": _point("lambda_usd", 2.0)},
        n_events=0, fold_version="test", policy="frozen-elicitations")
    paired = [_pair("h", _resp("hedge", True, cost_usd=0.1),
                    _resp("abstain", withheld=None, cost_usd=0.6))]
    d = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=200, seed=1).diagnostics
    # answers: typed hedge-correct = u_hedged = 0.75, mono abstain = 0.0 → +0.75
    assert d.delta_answers == pytest.approx(0.75)
    # spend: 2.0 * (0.6 - 0.1) = 1.0
    assert d.delta_spend == pytest.approx(1.0)


def test_the_report_publishes_the_decomposition() -> None:
    """r28 C1. The split is what a reader quotes; a Diagnostics field nobody renders is not
    published. MUST FAIL if the decomposition block is dropped from the report."""
    paired, post = _decomposition_fixture()
    res = G.delta_posterior(paired, post, oracle_p=0.9, n_draws=200, seed=1)
    md = G.render_report(res, run_id="gate-test", elapsed=1.0,
                         baseline="raw-deliberative-replay", pairing=None, reach_rate=None)
    low = md.lower()
    assert "answers" in low and "spend" in low
    assert "+4.700" in md or "4.700" in md, "the spend term is not in the report"
    assert "1.000" in md, "the answer term is not in the report"
    assert "$" in md, "the arms' realised dollars are not published"


def test_a_report_cannot_render_without_naming_its_baseline() -> None:
    """r28 C3, structural. K4 fixed the VALUE at the one call site it looked at and left
    the "monolithic" default in place; two further instruments — `scripts/gate_splice.py`
    and `scripts/membrane/p3_gate.py` — were still rendering through that default, so the
    r27 defect survived in both. Removing the default kills the class rather than censusing
    for it. MUST FAIL if any default is restored."""
    post = _posterior(u_wrong=-2.0)
    res = G.delta_posterior([_pair("a", _resp("report", True), _resp("abstain"))],
                            post, oracle_p=0.9, n_draws=200, seed=1)
    with pytest.raises(TypeError, match="baseline"):
        G.render_report(res, run_id="gate-test", elapsed=1.0)   # type: ignore[call-arg]
