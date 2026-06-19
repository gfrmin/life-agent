"""The decision-weighted adoption gate's pure math (bayesian-foundations §8).

No IO, no skin: the utility posterior is constructed synthetically (it is just a frozen
dataclass of grid marginals), the paired outcomes are hand-built, and the Δ-posterior MC
is seeded — so the gate is a deterministic fold given its inputs. These tests pin the
realised-utility model, the two composed uncertainties (utility + the Bayesian
bootstrap), the verdict arithmetic, and the at-Ū diagnostics.

Run: uv run --project . python -m pytest tests/test_gate.py
"""
from __future__ import annotations

from life_agent.core import gate as G
from life_agent.core import utility as UT

# --- synthetic utility posteriors --------------------------------------------------------

def _point(name: str, value: float) -> UT.LatentPosterior:
    """A degenerate latent — all mass on one grid value (sampling is then exact)."""
    return UT.LatentPosterior(name=name, values=(value,), weights=(1.0,))


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


def _resp(action: str, correct: bool | None = None) -> G.RealisedResponse:
    return G.RealisedResponse(action=action, correct=correct)


def _pair(qid: str, typed: G.RealisedResponse, mono: G.RealisedResponse,
          answerable: bool = True) -> G.PairedOutcome:
    return G.PairedOutcome(question_id=qid, answerable=answerable, typed=typed, mono=mono)


# --- the realised-utility model (stated) -------------------------------------------------

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
    # a u_wrong spread straddling the materiality boundary ⇒ p_gt strictly interior,
    # NOT a point 0/1 — utility uncertainty is inside the gate.
    spread = UT.LatentPosterior(name="u_wrong", values=(-3.0, -0.0),
                                weights=(0.5, 0.5))
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
