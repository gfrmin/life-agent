"""The utility posterior (bayesian-foundations §4.4/§10 as amended) — utility.py.

Hermetic strata:
1. Pure parts: model loading, grid/gauge validation, endpoint-mass monitoring (`near_bound`),
   Ū extraction, fold_version determinism.
2. The fold's numbers: against a dense independent quadrature of the continuous model, in the
   directions evidence must move it, and on coupled components.
3. The replay pin: every recorded proplang-shadow boot's Ū, re-folded from the evidence that
   existed at that boot (needs the owner's KB).

Run: uv run --project . python -m pytest tests/test_utility.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import yaml

from life_agent.core import answer_shape as AS
from life_agent.core import utility as U

MODEL_YAML = """\
format_version: 1
gauge:
  u_correct: 1.0
  u_abstain: 0.0
latents:
  u_wrong:    {grid: {lo: -10.0, hi: 0.0, n: 11}, prior: {type: gaussian, mu: -4.0, sigma: 3.0}}
  u_wrong_scoped: {grid: {lo: -6.0, hi: 0.0, n: 9}, prior: {type: gaussian, mu: -2.0, sigma: 1.0}}
  u_hedged:   {grid: {lo: -1.0, hi: 1.0, n: 5},  prior: {type: gaussian, mu: 0.4, sigma: 0.4}}
  lambda_int: {grid: {lo: -0.5, hi: 4.0, n: 10}, prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
  kappa_att:  {grid: {lo: -0.2, hi: 1.0, n: 7},  prior: {type: gaussian, mu: 0.05, sigma: 0.1}}
  lambda_usd: {grid: {lo: 0.0, hi: 8.0, n: 9},   prior: {type: gaussian, mu: 1.0, sigma: 1.0}}
tau:
  grid: {lo: 0.5, hi: 2.0, n: 4}
  prior: {type: gaussian, mu: 1.0, sigma: 0.5}
endpoint_mass_warn: 0.01
"""


@pytest.fixture
def model(tmp_path: Path) -> U.UtilityModel:
    p = tmp_path / "model.yaml"
    p.write_text(MODEL_YAML, encoding="utf-8")
    return U.load_model(p)


# --- model loading -----------------------------------------------------------------------

def test_load_model_parses_gauge_latents_and_tau(model: U.UtilityModel) -> None:
    assert model.gauge == {"u_correct": 1.0, "u_abstain": 0.0}
    assert set(model.latents) == set(U.REQUIRED_LATENTS)
    assert model.latents["u_wrong"].grid.n == 11
    assert model.tau.grid.values()[0] == pytest.approx(0.5)


def test_lambda_usd_is_a_required_latent_with_a_positive_domain(
        model: U.UtilityModel) -> None:
    # the $↔utility exchange rate (plan item C): gauge units per USD, a LATENT the
    # owner elicits — never a constant invented in a menu row. Positive by domain
    # (a rate, like tau): the grid floor is a constraint, not a preference.
    assert "lambda_usd" in U.REQUIRED_LATENTS
    assert model.latents["lambda_usd"].grid.lo >= 0.0


def test_example_lambda_usd_prior_encodes_the_convention() -> None:
    # PR #67 review: N(1,1) truncated to [0,8] has mean ≈1.288 — NOT the $1≈1-gauge
    # convention the comments claimed, a silent ~29% re-pricing on deploy with zero
    # elicitations. Drift gate: the shipped example prior's TRUNCATED mean must sit
    # within 1% of the convention (the truncation shift is computed, not assumed).
    import yaml as _yaml

    example = Path(__file__).resolve().parent.parent / "config/utility-model.example.yaml"
    spec = _yaml.safe_load(example.read_text(encoding="utf-8"))["latents"]["lambda_usd"]
    mu, sigma = float(spec["prior"]["mu"]), float(spec["prior"]["sigma"])
    lo, hi = float(spec["grid"]["lo"]), float(spec["grid"]["hi"])
    phi = lambda z: math.exp(-z * z / 2) / math.sqrt(2 * math.pi)  # noqa: E731
    cdf = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))  # noqa: E731
    a, b = (lo - mu) / sigma, (hi - mu) / sigma
    trunc_mean = mu + sigma * (phi(a) - phi(b)) / (cdf(b) - cdf(a))
    assert abs(trunc_mean - 1.0) < 0.01, trunc_mean


def test_missing_latent_error_names_the_remedy(tmp_path: Path) -> None:
    # PR #67 review: a pre-lambda_usd model.yaml (second machine, backup restore) must
    # fail LOUDLY — but the error names the one-line fix, never just the lack.
    p = tmp_path / "model.yaml"
    p.write_text(MODEL_YAML.replace(
        "  lambda_usd: {grid: {lo: 0.0, hi: 8.0, n: 9},   "
        "prior: {type: gaussian, mu: 1.0, sigma: 1.0}}\n", ""), encoding="utf-8")
    with pytest.raises(ValueError, match=r"utility-model\.example\.yaml"):
        U.load_model(p)


def test_load_model_missing_latent_is_loud(tmp_path: Path) -> None:
    p = tmp_path / "model.yaml"
    p.write_text(MODEL_YAML.replace("u_hedged", "u_hedge_typo"), encoding="utf-8")
    with pytest.raises(ValueError, match="u_hedged"):
        U.load_model(p)


def test_load_model_wrong_gauge_is_loud(tmp_path: Path) -> None:
    p = tmp_path / "model.yaml"
    p.write_text(MODEL_YAML.replace("u_correct: 1.0", "u_correct: 2.0"), encoding="utf-8")
    with pytest.raises(ValueError, match="gauge"):
        U.load_model(p)


def test_grid_values_are_inclusive_and_evenly_spaced() -> None:
    g = U.Grid(lo=-1.0, hi=1.0, n=5)
    assert g.values() == (-1.0, -0.5, 0.0, 0.5, 1.0)


# --- r30 step 2: the six OPTIONAL per-shape utility-scale latents -------------------------
# docs/unification/reports/r30-units-lever.md — an optional latent block (the tau_narrative
# precedent), not REQUIRED_LATENTS: an owner model file that omits them still loads, and
# shaped_u_bar defaults the missing scale to 1.0 (core/decide.py).

def test_shape_latent_names_names_exactly_the_six_optional_latents() -> None:
    expected = tuple(f"{kind}_scale_{shape}" for shape in AS.SCALED_SHAPES
                     for kind in ("voi", "regret"))
    assert expected == U.SHAPE_LATENT_NAMES
    assert len(U.SHAPE_LATENT_NAMES) == 2 * len(AS.SCALED_SHAPES)


def test_a_model_file_omitting_the_six_latents_still_loads(model: U.UtilityModel) -> None:
    # the MODEL_YAML fixture above declares none of them — every existing fixture in this
    # repo is in this state today, and load_model must not require them (C4/C10's no-op).
    assert set(model.latents) == set(U.REQUIRED_LATENTS)
    assert not (set(U.SHAPE_LATENT_NAMES) & set(model.latents))


def test_a_declared_shape_latent_is_parsed_like_any_other(tmp_path: Path) -> None:
    p = tmp_path / "model.yaml"
    extra_latent = ("  voi_scale_quantity: {grid: {lo: 0.0, hi: 4.0, n: 9}, "
                    "prior: {type: gaussian, mu: 1.0, sigma: 0.3}}\n")
    yaml_text = MODEL_YAML.replace(
        "  lambda_usd: {grid: {lo: 0.0, hi: 8.0, n: 9},   "
        "prior: {type: gaussian, mu: 1.0, sigma: 1.0}}\n",
        "  lambda_usd: {grid: {lo: 0.0, hi: 8.0, n: 9},   "
        "prior: {type: gaussian, mu: 1.0, sigma: 1.0}}\n" + extra_latent)
    p.write_text(yaml_text, encoding="utf-8")
    model = U.load_model(p)
    assert set(model.latents) == set(U.REQUIRED_LATENTS) | {"voi_scale_quantity"}
    spec = model.latents["voi_scale_quantity"]
    assert spec.grid.lo == 0.0 and spec.grid.hi == 4.0 and spec.prior_mu == 1.0


def test_undeclared_shape_latents_are_absent_from_u_bar(model: U.UtilityModel) -> None:
    post = U.posterior(model, [], policy="all-to-date")
    assert not (set(U.SHAPE_LATENT_NAMES) & set(post.u_bar()))


# --- C6: the six latents' frozen priors (config/utility-model-shape-scales.example.yaml) --
# NOT merged into config/utility-model.example.yaml (disclosed deviation,
# docs/unification/reports/r30-units-lever.md RESULTS) — that file is copied wholesale by
# tests/conftest.py's ledger_kb fixture and used as the template for the owner's real
# deployed file, so declaring all six there would move pinned ledger golden hashes and the
# owner's live fold_version for no reason. This file freezes the numbers without activating
# them anywhere.

def test_shape_scale_priors_file_names_exactly_the_six_optional_latents() -> None:
    example = (Path(__file__).resolve().parent.parent
              / "config/utility-model-shape-scales.example.yaml")
    spec = yaml.safe_load(example.read_text(encoding="utf-8"))["latents"]
    assert set(spec) == set(U.SHAPE_LATENT_NAMES)


def test_shape_scale_priors_are_computed_at_the_anchors_own_value() -> None:
    # each TRUNCATED mean sits within 1% of 1.0 (computed, not assumed — the #67-review
    # lesson that first caught a silent 29% re-pricing in lambda_usd's own prior).
    example = (Path(__file__).resolve().parent.parent
              / "config/utility-model-shape-scales.example.yaml")
    spec = yaml.safe_load(example.read_text(encoding="utf-8"))["latents"]
    phi = lambda z: math.exp(-z * z / 2) / math.sqrt(2 * math.pi)  # noqa: E731
    cdf = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))  # noqa: E731
    for name, raw in spec.items():
        mu, sigma = float(raw["prior"]["mu"]), float(raw["prior"]["sigma"])
        lo, hi = float(raw["grid"]["lo"]), float(raw["grid"]["hi"])
        a, b = (lo - mu) / sigma, (hi - mu) / sigma
        trunc_mean = mu + sigma * (phi(a) - phi(b)) / (cdf(b) - cdf(a))
        assert abs(trunc_mean - 1.0) < 0.01, (name, trunc_mean)


def test_shape_scale_priors_parse_through_load_model_like_any_other_latent(
        tmp_path: Path) -> None:
    example = (Path(__file__).resolve().parent.parent
              / "config/utility-model-shape-scales.example.yaml")
    extra = "\n".join(f"  {name}: {yaml.safe_dump(raw, default_flow_style=True).strip()}"
                      for name, raw in yaml.safe_load(
                          example.read_text(encoding="utf-8"))["latents"].items())
    p = tmp_path / "model.yaml"
    p.write_text(MODEL_YAML.replace("tau:\n", extra + "\ntau:\n"), encoding="utf-8")
    model = U.load_model(p)
    assert set(model.latents) == set(U.REQUIRED_LATENTS) | set(U.SHAPE_LATENT_NAMES)


# (The host helpers gaussian_weights/elicitation_log_density/reaction_probability were the
# discretisation antipattern and were retired in Phase B — priors/likelihoods are now declared
# continuous and conditioned engine-side; see test_fold_choreography and the live folds below.)


# --- evidence loading --------------------------------------------------------------------

def test_load_elicitations_missing_file_is_a_working_state(
        tmp_path: Path, model: U.UtilityModel) -> None:
    assert U.load_elicitations(tmp_path / "absent.jsonl", model) == []


def test_load_elicitations_round_trip_and_bad_latent_loud(
        tmp_path: Path, model: U.UtilityModel) -> None:
    p = tmp_path / "elicitations.jsonl"
    rows = [
        {"tx_time": "2026-06-12T10:00:00+00:00", "latent": "u_wrong",
         "stated_value": -8.0, "noise_sigma": 2.0},
        {"tx_time": "2026-06-12T11:00:00+00:00", "latent": "lambda_int",
         "stated_value": 0.5, "noise_sigma": 1.0},
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    events = U.load_elicitations(p, model)
    assert [e.latent for e in events] == ["u_wrong", "lambda_int"]  # order preserved

    p.write_text(json.dumps({**rows[0], "latent": "u_wramg"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="u_wramg"):
        U.load_elicitations(p, model)


# --- the fold ------------------------------------------------------------------------------

def test_the_fold_partitions_by_latent_and_keeps_untouched_priors(
        model: U.UtilityModel) -> None:
    events: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
        U.Elicitation(tx_time="t3", latent="lambda_int", stated_value=0.5, noise_sigma=1.0),
    ]
    prior = U.posterior(model, [], policy="all-to-date")
    post = U.posterior(model, events, policy="all-to-date")
    assert set(post.latents) == set(U.REQUIRED_LATENTS)
    assert post.u_bar()["u_correct"] == 1.0 and post.u_bar()["u_abstain"] == 0.0
    assert post.n_events == 3 and len(post.fold_version) == 64
    assert post.latents["u_wrong"].mean < prior.latents["u_wrong"].mean
    assert post.latents["lambda_int"].mean < prior.latents["lambda_int"].mean
    for name in ("u_hedged", "kappa_att", "lambda_usd", "u_wrong_scoped"):
        assert post.latents[name] == prior.latents[name]


def test_fold_version_changes_with_events(model: U.UtilityModel) -> None:
    e1 = [U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0,
                        noise_sigma=2.0)]
    v0 = U.fold_version(model, [], "all-to-date")
    v1 = U.fold_version(model, list(e1), "all-to-date")
    assert v0 != v1
    assert v1 == U.fold_version(model, list(e1), "all-to-date")  # deterministic
    assert len(v0) == 64


def test_endpoint_warnings(model: U.UtilityModel) -> None:
    # a latent whose posterior mean sits within 1sigma of a support bound warns
    near = U.LatentPosterior(name="u_wrong", mean=-0.3, variance=1.0, lo=-10.0, hi=0.0)
    post = U.UtilityPosterior(gauge=model.gauge, latents={"u_wrong": near},
                              n_events=0, fold_version="0" * 64,
                              policy="all-to-date")
    warned = post.endpoint_warnings(threshold=0.01)
    assert warned and "u_wrong" in warned[0] and "widen" in warned[0]
    assert near.near_bound                      # mean -0.3 is within 1sigma (=1.0) of hi=0
    # a latent well within its support (tight variance, centred) does NOT warn
    inner = U.LatentPosterior(name="u_hedged", mean=0.0, variance=0.01, lo=-1.0, hi=1.0)
    assert not inner.near_bound
    inner_post = U.UtilityPosterior(gauge=model.gauge, latents={"u_hedged": inner},
                                    n_events=0, fold_version="0" * 64,
                                    policy="all-to-date")
    assert inner_post.endpoint_warnings(threshold=0.01) == []


# --- the fold against an independent dense reference ---------------------------------------

def _ref_uwrong_moments(spec: U.LatentSpec, tau: U.LatentSpec, *, stated: float,
                        noise_sigma: float, sign: float, threshold: float) -> tuple[float, float]:
    """An independent dense quadrature of the continuous u_wrong model — truncated-normal prior x
    Gaussian elicitation x tau-marginalised logistic reaction — on a 40k-point grid the fold's
    64-point grid must converge to (the same 32-point tau marginalisation)."""
    lo, hi, nx, n_tau = spec.grid.lo, spec.grid.hi, 40001, 32
    tstep = (tau.grid.hi - tau.grid.lo) / n_tau

    def react_logp1(x: float) -> float:  # P(react=1 | x) marginalising τ
        p1 = z = 0.0
        for k in range(1, n_tau + 1):
            t = tau.grid.lo + (k - 0.5) * tstep
            w = math.exp(-0.5 * ((t - tau.prior_mu) / tau.prior_sigma) ** 2)
            z += w
            p1 += w / (1.0 + math.exp(-(sign * x - threshold) / t))
        return math.log(max(p1 / z, 1e-300))

    xs = [lo + (k - 0.5) * (hi - lo) / nx for k in range(1, nx + 1)]
    lw = [(-0.5 * ((x - spec.prior_mu) / spec.prior_sigma) ** 2)          # truncated-normal prior
          + (-0.5 * (stated - x) ** 2 / noise_sigma ** 2)                 # gaussian elicitation
          + react_logp1(x) for x in xs]                                   # continuous-τ reaction
    m = max(lw)
    ws = [math.exp(v - m) for v in lw]
    z = sum(ws)
    mean = sum(x * w for x, w in zip(xs, ws, strict=True)) / z
    var = sum((x - mean) ** 2 * w for x, w in zip(xs, ws, strict=True)) / z
    return mean, var


def test_the_fold_matches_a_dense_reference_and_moves_u_wrong_down(
        model: U.UtilityModel) -> None:
    events: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
    ]
    prior = U.posterior(model, [], policy="all-to-date")
    post = U.posterior(model, events, policy="all-to-date")

    uw = post.latents["u_wrong"]
    assert uw.mean < prior.latents["u_wrong"].mean
    ref_mean, ref_var = _ref_uwrong_moments(
        model.latents["u_wrong"], model.tau, stated=-8.0, noise_sigma=2.0, sign=-1.0, threshold=0.0)
    assert uw.mean == pytest.approx(ref_mean, abs=1e-2)
    assert uw.variance == pytest.approx(ref_var, abs=1e-2)


def test_the_reaction_loop_good_on_abstain_lowers_u_wrong(
        model: U.UtilityModel, tmp_path: Path) -> None:
    """The §4.4 loop end to end: a good-on-abstain verdict, joined to its decision by
    decision_id, produces a Reaction that lowers Ū(u_wrong)."""
    from life_agent.core import decisions as DEC
    from life_agent.core import reactions as R

    dpath, rpath = tmp_path / "decisions.jsonl", tmp_path / "reactions.jsonl"
    DEC.append(dpath, DEC.DecisionEvent(
        tx_time="t", run_id="ask", question_id="q", family="lookup",
        action_set=("report", "hedge", "ask_clarify", "abstain"),
        posterior_summary={"credences": [0.3, 0.7]}, utility_fold_version="fv",
        chosen_action="abstain", predicted_eu=0.0, decision_id="d1"))
    R.append(rpath, R.ReactionEvent(tx_time="t", question_id="q", decision_id="d1",
                                    kind="verdict", valence="good"))
    events = R.load_reactions(rpath, dpath)
    assert len(events) == 1  # the producer folds the clean abstain row

    prior = U.posterior(model, [], policy="all-to-date")
    post = U.posterior(model, list(events), policy="all-to-date")
    assert post.latents["u_wrong"].mean < prior.latents["u_wrong"].mean


# --- the narrative joint fold: (u_wrong, κ_att) coupled (§7.1) --------------------------

def _margin_good(p: float) -> U.MarginReaction:
    """A good-on-ALL_WITHHELD narrative verdict's MarginReaction at credence p."""
    return U.MarginReaction(
        tx_time="t1", coeffs=(("kappa_att", -1.0), ("u_wrong", p * (1 - p))),
        offset=-(p ** 2), reacted=True, sign=-1.0, tau_group="narrative")


def test_lookup_and_narrative_u_wrong_share_one_joint(model: U.UtilityModel) -> None:
    # a lookup Reaction on u_wrong and a narrative MarginReaction co-occur u_wrong, so they
    # fold as ONE component — never u_wrong 1-D then a separate narrative joint
    events: list[U.Evidence] = [
        U.Reaction(tx_time="t1", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.5),
        _margin_good(0.6),
    ]
    comps = U._components(model.latents, events)
    assert frozenset({"u_wrong", "kappa_att"}) in comps
    assert all(len(c) == 1 for c in comps if "u_wrong" not in c)


def test_narrative_good_on_abstain_moves_both_latents(model: U.UtilityModel) -> None:
    """The §7.1 joint fold: a good-on-abstain verdict ("right to withhold") is a low-margin
    observation, pushing u(wrong) DOWN and κ_att UP jointly; the untouched latents stay at
    their prior."""
    prior = U.posterior(model, [], policy="all-to-date")
    post = U.posterior(model, [_margin_good(0.6)], policy="all-to-date")
    assert post.latents["u_wrong"].mean < prior.latents["u_wrong"].mean
    assert post.latents["kappa_att"].mean > prior.latents["kappa_att"].mean
    # u_hedged is UNCOUPLED → its own 1-D fold; it stays at its prior
    assert post.latents["u_hedged"].mean == pytest.approx(prior.latents["u_hedged"].mean)


def test_lookup_u_wrong_marginal_is_invariant_when_pulled_into_a_joint(
        model: U.UtilityModel) -> None:
    """A margin reaction flat in u(wrong) (coeff 0) pulls it into the {u_wrong, κ_att} joint,
    but the joint factorises (independent prior, lookup likelihood flat in κ_att), and the 1-D
    grid and the joint's u_wrong axis are the same 64 midpoints — so the marginalised u(wrong)
    equals the 1-D fold to machine precision."""
    lookup = U.Reaction(tx_time="t", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.5)
    flat = U.MarginReaction(tx_time="t", coeffs=(("kappa_att", -1.0), ("u_wrong", 0.0)),
                            offset=0.0, reacted=True, sign=-1.0, tau_group="narrative")
    one_d = U.posterior(model, [lookup], policy="all-to-date")
    joint = U.posterior(model, [lookup, flat], policy="all-to-date")
    uw_1d, uw_joint = one_d.latents["u_wrong"], joint.latents["u_wrong"]
    assert uw_joint.mean == pytest.approx(uw_1d.mean, abs=1e-9)
    assert uw_joint.variance == pytest.approx(uw_1d.variance, abs=1e-9)
    assert uw_joint.variance == pytest.approx(uw_1d.variance, abs=1e-6)


# --- Q-O5/D-8: the one entry point names its evidence policy (r13, M3) -------------------

def test_posterior_requires_a_policy(model: U.UtilityModel) -> None:
    # the regime indicator is a required keyword — no old spelling survives (design §3.1)
    with pytest.raises(TypeError):
        U.posterior(model, [])  # type: ignore[call-arg]


def test_frozen_elicitations_refuses_the_projection(model: U.UtilityModel) -> None:
    # the policy names a declared CONDITIONING SET, enforced structurally: the gate's
    # blind regime cannot fold a verdict-projected event (the §7.5 policy-swap defect
    # dies at the fold itself, not at a caller's discipline)
    ev: list[U.Evidence] = [U.Reaction(tx_time="t1", latent="u_wrong", reacted=True,
                                       sign=-1.0, threshold=0.0)]
    with pytest.raises(ValueError, match="frozen-elicitations"):
        U.posterior(model, ev, policy="frozen-elicitations")


def test_all_to_date_accepts_the_projection_and_stamps_the_policy(
        model: U.UtilityModel) -> None:
    ev: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
    ]
    post = U.posterior(model, ev, policy="all-to-date")
    assert post.policy == "all-to-date"
    assert post.fold_version == U.fold_version(model, ev, "all-to-date")


def test_an_unknown_policy_is_refused(model: U.UtilityModel) -> None:
    with pytest.raises(ValueError, match="policy"):
        U.posterior(model, [], policy="everything")


def test_fold_version_covers_the_policy(model: U.UtilityModel) -> None:
    # one memo can never serve one regime's Ū to the other's caller (design §3.1)
    e1 = [U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0,
                        noise_sigma=2.0)]
    va = U.fold_version(model, list(e1), "all-to-date")
    vf = U.fold_version(model, list(e1), "frozen-elicitations")
    assert va != vf and len(va) == 64 and len(vf) == 64
    assert va == U.fold_version(model, list(e1), "all-to-date")  # deterministic


def test_fold_version_requires_the_policy(model: U.UtilityModel) -> None:
    with pytest.raises(TypeError):
        U.fold_version(model, [])  # type: ignore[call-arg]


# --- the replay pin: every recorded boot's Ū -----------------------------------------------

# The proplang shadow logged Ū at each of its 23 boots (2026-07-18 → 2026-09-12), folded by
# the credence skin. Re-folding the evidence that existed at each boot must reproduce it; the
# boots span three evidence sets (11, 12-13 and 55 events). Julia's exp/log round differently
# from libm in the last ulp, so the tolerance is the measured residue (4.4e-16 relative).
_MODEL_SHA = "b4fdc98741e4c1d92bab8f3a03c7ce412e70a02f6f2bb0160da5f71af7860cd4"
_ELICITATIONS_SHA = "710ed2a9feff31316bb5a1fb2c629e7587dd633e10c37d5f64025340634f45b2"
_BOOT_REL_TOL = 1e-15


def test_the_fold_replays_every_recorded_boot_u_bar() -> None:
    import hashlib
    import os
    from datetime import UTC, datetime

    from life_agent.core import reactions as R

    kb = Path(os.environ.get("LIFE_AGENT_KB") or "/nonexistent")
    shadow = kb / "membrane" / "shadow.jsonl"
    model_path, elicit = kb / "utility" / "model.yaml", kb / "utility" / "elicitations.jsonl"
    if not (shadow.is_file() and model_path.is_file()):
        pytest.skip("needs the owner's KB ($LIFE_AGENT_KB with membrane/shadow.jsonl and "
                    "utility/model.yaml); owner data, not buildable")
    for path, sha in ((model_path, _MODEL_SHA), (elicit, _ELICITATIONS_SHA)):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, (
            f"{path.name} changed since the boots were recorded; re-pin deliberately")
    model = U.load_model(model_path)
    events: list[U.Evidence] = [
        *U.load_elicitations(elicit, model),
        *R.load_reactions(kb / "calibration" / "reactions.jsonl",
                          kb / "calibration" / "decisions.jsonl")]
    boots = [row for row in map(json.loads, shadow.read_text(encoding="utf-8").splitlines())
             if row.get("kind") == "boot" and row.get("u_bar")]
    assert len(boots) >= 23
    folds: dict[int, dict[str, float]] = {}
    for boot in boots:
        at = datetime.fromtimestamp(boot["ts"], UTC).isoformat()
        seen = [e for e in events if str(e.tx_time) <= at]
        if len(seen) not in folds:
            folds[len(seen)] = U.posterior(model, seen, policy="all-to-date").u_bar()
        got = folds[len(seen)]
        for name, want in boot["u_bar"].items():
            assert abs(got[name] - want) <= _BOOT_REL_TOL * max(1.0, abs(want)), (at, name)
    assert len(folds) >= 3
