"""The utility posterior (bayesian-foundations §4.4/§10 as amended) — utility.py.

Hermetic strata:
1. Pure parts: model loading, grid/gauge validation, endpoint-mass monitoring (`near_bound`),
   Ū extraction, fold_version determinism.
2. The fold's RPC choreography over a scripted transport: one CONTINUOUS `truncated_gaussian`
   per uncoupled latent (and a single `truncated_mv_gaussian` for a coupled component),
   conditioning in tx order through declared kernels (gaussian_known_var / logistic_reaction /
   linear_gaussian / margin_reaction), reading moments via mean/expect/marginal — no host grid.
3. ``@pytest.mark.system``: the live Julia fold against an independent Python quadrature of the
   continuous model (truncated-normal prior x elicitation x continuous-τ reaction) — the real
   numerical check.

Run: uv run --project . python -m pytest tests/test_utility.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from life_agent.core import brain as B
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


# --- the fold: RPC choreography over a scripted transport --------------------------------

class SeqTransport:
    """Replies per method with scripted results; records every request."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self._n_states = 0
        self._n_marg = 0

    def send(self, line: str) -> None:
        self.sent.append(json.loads(line))

    def recv(self) -> str:
        req = self.sent[-1]
        method = req["method"]
        if method == "create_state":
            self._n_states += 1
            result: object = {"state_id": f"s_{self._n_states}"}
        elif method == "condition":
            result = {"state_id": req["params"]["state_id"], "log_marginal": -0.1}
        elif method == "marginal":
            # a coordinate marginal of the joint → a NEW scalar state the fold reads with
            # mean/expect (its own id namespace so create-order `s_n` mapping stays clean).
            self._n_marg += 1
            result = {"state_id": f"m_{self._n_marg}"}
        elif method == "mean":
            result = {"mean": -1.0}   # scripted (choreography asserts the RPC seq, not the value)
        elif method == "expect":
            result = {"value": 2.0}   # scripted variance (centered_power E[(x-mean)^2])
        else:
            result = "ok"
        return json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result})

    def close(self) -> None:
        pass


def test_fold_choreography_partitions_by_latent_and_orders_events(
        model: U.UtilityModel) -> None:
    t = SeqTransport()
    b = B.Brain(t)
    events: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
        U.Elicitation(tx_time="t3", latent="lambda_int", stated_value=0.5, noise_sigma=1.0),
    ]
    post = U.posterior(b, model, events)

    creates = [r for r in t.sent if r["method"] == "create_state"]
    conditions = [r for r in t.sent if r["method"] == "condition"]
    destroys = [r for r in t.sent if r["method"] == "destroy_state"]
    # one CONTINUOUS truncated_gaussian per latent — never for the gauge pins, never for τ
    assert len(creates) == len(U.REQUIRED_LATENTS)
    assert all(r["params"]["type"] == "truncated_gaussian" for r in creates)
    assert len(destroys) == len(creates)
    # three conditions total, in tx order within each latent
    assert len(conditions) == 3
    # the u_wrong elicitation kernel is a Gaussian observation (gaussian_known_var → NormalNormal);
    # the body declares only the noise variance, no host density grid.
    k0 = conditions[0]["params"]["kernel"]
    assert k0 == {"type": "gaussian_known_var", "variance": 4.0}   # noise_sigma=2 ⇒ variance 4
    assert conditions[0]["params"]["observation"] == -8.0
    # the reaction kernel is the continuous-τ logistic_reaction — only (sign, threshold, τ-prior),
    # NO τ-grid; the engine integrates τ and x internally.
    k1 = conditions[1]["params"]["kernel"]
    assert k1["type"] == "logistic_reaction" and k1["sign"] == -1.0 and k1["threshold"] == 0.0
    assert (k1["tau_mu"] == model.tau.prior_mu and k1["tau_sigma"] == model.tau.prior_sigma
            and k1["tau_lo"] == model.tau.grid.lo and k1["tau_hi"] == model.tau.grid.hi)
    assert conditions[1]["params"]["observation"] == 1.0

    # posterior carries every latent, gauge pins intact, fold version stamped
    assert set(post.latents) == set(U.REQUIRED_LATENTS)
    assert post.u_bar()["u_correct"] == 1.0 and post.u_bar()["u_abstain"] == 0.0
    assert post.n_events == 3
    assert len(post.fold_version) == 64


def test_fold_version_changes_with_events(model: U.UtilityModel) -> None:
    e1 = [U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0,
                        noise_sigma=2.0)]
    v0 = U.fold_version(model, [])
    v1 = U.fold_version(model, list(e1))
    assert v0 != v1
    assert v1 == U.fold_version(model, list(e1))  # deterministic
    assert len(v0) == 64


def test_endpoint_warnings(model: U.UtilityModel) -> None:
    # a latent whose posterior mean sits within 1sigma of a support bound warns
    near = U.LatentPosterior(name="u_wrong", mean=-0.3, variance=1.0, lo=-10.0, hi=0.0)
    post = U.UtilityPosterior(gauge=model.gauge, latents={"u_wrong": near},
                              n_events=0, fold_version="0" * 64)
    warned = post.endpoint_warnings(threshold=0.01)
    assert warned and "u_wrong" in warned[0] and "widen" in warned[0]
    assert near.near_bound                      # mean -0.3 is within 1sigma (=1.0) of hi=0
    # a latent well within its support (tight variance, centred) does NOT warn
    inner = U.LatentPosterior(name="u_hedged", mean=0.0, variance=0.01, lo=-1.0, hi=1.0)
    assert not inner.near_bound
    inner_post = U.UtilityPosterior(gauge=model.gauge, latents={"u_hedged": inner},
                                    n_events=0, fold_version="0" * 64)
    assert inner_post.endpoint_warnings(threshold=0.01) == []


# --- live: the skin's fold against an independent Python reference -----------------------

def _ref_uwrong_moments(spec: U.LatentSpec, tau: U.LatentSpec, *, stated: float,
                        noise_sigma: float, sign: float, threshold: float) -> tuple[float, float]:
    """A STRICT independent host oracle for the continuous u_wrong fold: a dense quadrature of the
    declared model — TruncatedNormal(spec) prior x gaussian_known_var elicitation x continuous-τ
    logistic reaction — over the support [lo,hi]. Mirrors the engine model EXACTLY (the same
    32-pt τ marginalisation; a 40k-pt x grid the engine's 64-pt grid must converge to). This is a
    test oracle, not host belief arithmetic: it never feeds a decision."""
    lo, hi, nx, n_tau = spec.grid.lo, spec.grid.hi, 40001, 32
    tstep = (tau.grid.hi - tau.grid.lo) / n_tau

    def react_logp1(x: float) -> float:  # P(react=1 | x) marginalising τ — the engine's form
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


@pytest.mark.system
def test_live_fold_matches_reference_and_moves_u_wrong_correctly(
        model: U.UtilityModel) -> None:
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
    events: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
    ]
    with B.Brain.spawn() as b:
        b.initialize()
        prior = U.posterior(b, model, [])          # the engine's own prior fold — the baseline
        post = U.posterior(b, model, events)

    uw = post.latents["u_wrong"]
    # the verdict-shaped evidence must move Ū(u_wrong) down vs the engine's prior fold
    assert uw.mean < prior.latents["u_wrong"].mean
    # strict independent reference: the engine's 64-pt quadrature must converge to a dense host one
    ref_mean, ref_var = _ref_uwrong_moments(
        model.latents["u_wrong"], model.tau, stated=-8.0, noise_sigma=2.0, sign=-1.0, threshold=0.0)
    assert uw.mean == pytest.approx(ref_mean, abs=1e-2)
    assert uw.variance == pytest.approx(ref_var, abs=1e-2)


@pytest.mark.system
def test_live_reaction_loop_good_on_abstain_lowers_u_wrong(
        model: U.UtilityModel, tmp_path: Path) -> None:
    """The §4.4 loop end to end through the real skin: a good-on-abstain verdict, joined
    to its decision by decision_id, produces a Reaction that lowers Ū(u_wrong) — the
    owner's behaviour, not a fabricated number, moving the belief."""
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
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

    with B.Brain.spawn() as b:
        b.initialize()
        prior = U.posterior(b, model, [])          # the engine's own prior fold — the baseline
        post = U.posterior(b, model, list(events))
    assert post.latents["u_wrong"].mean < prior.latents["u_wrong"].mean


# --- the narrative joint fold: (u_wrong, κ_att) coupled (§7.1) --------------------------

def _margin_good(p: float) -> U.MarginReaction:
    """A good-on-ALL_WITHHELD narrative verdict's MarginReaction at credence p."""
    return U.MarginReaction(
        tx_time="t1", coeffs=(("kappa_att", -1.0), ("u_wrong", p * (1 - p))),
        offset=-(p ** 2), reacted=True, sign=-1.0, tau_group="narrative")


def test_margin_reaction_folds_on_one_joint_grid(model: U.UtilityModel) -> None:
    t = SeqTransport()
    post = U.posterior(B.Brain(t), model, [_margin_good(0.6)])
    creates = [r for r in t.sent if r["method"] == "create_state"]
    conditions = [r for r in t.sent if r["method"] == "condition"]
    marginals = [r for r in t.sent if r["method"] == "marginal"]
    # one JOINT `truncated_mv_gaussian` over the two coupled latents {u_wrong, κ_att} — the engine
    # owns the joint grid, the body declares only continuous data; the three untouched latents
    # (u_wrong_scoped, u_hedged, lambda_int) are 1-D `truncated_gaussian`s. NO host grid anywhere.
    mv = [c for c in creates if c["params"]["type"] == "truncated_mv_gaussian"]
    trunc = [c for c in creates if c["params"]["type"] == "truncated_gaussian"]
    assert len(creates) == 4 and len(mv) == 1 and len(trunc) == 3
    assert len(mv[0]["params"]["mu"]) == 2  # exactly the two coupled latents, no others
    # the margin couples them via a `margin_reaction` kernel carrying a length-2 coefficient vector
    jk = conditions[0]["params"]["kernel"]
    assert jk["type"] == "margin_reaction" and len(jk["coeffs"]) == 2
    # each coupled latent is read back with a `marginal` (one per coordinate) — no host arithmetic
    assert len(marginals) == 2 and {m["params"]["axis"] for m in marginals} == {0, 1}
    # the readout flows through to the posterior (scripted mean/variance from the wire)
    uw, ka = post.latents["u_wrong"], post.latents["kappa_att"]
    assert uw.mean == -1.0 and uw.variance == 2.0 and uw.lo == model.latents["u_wrong"].grid.lo
    assert ka.mean == -1.0 and ka.lo == model.latents["kappa_att"].grid.lo


def test_lookup_and_narrative_u_wrong_share_one_joint(model: U.UtilityModel) -> None:
    # a lookup Reaction on u_wrong and a narrative MarginReaction co-occur u_wrong, so they
    # fold on ONE joint grid — never u_wrong 1-D then narrative joint (the interleave error)
    t = SeqTransport()
    events: list[U.Evidence] = [
        U.Reaction(tx_time="t1", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.5),
        _margin_good(0.6),
    ]
    U.posterior(B.Brain(t), model, events)
    creates = [r for r in t.sent if r["method"] == "create_state"]
    conditions = [r for r in t.sent if r["method"] == "condition"]
    # u_wrong is absorbed into ONE joint `truncated_mv_gaussian` with κ_att — never a standalone
    # u_wrong 1-D state then a separate narrative joint (the interleave error). Exactly one mv joint
    # (the 2 coupled latents) + 3 one-dimensional truncated_gaussians (the uncoupled latents).
    mv = [c for c in creates if c["params"]["type"] == "truncated_mv_gaussian"]
    trunc = [c for c in creates if c["params"]["type"] == "truncated_gaussian"]
    assert len(mv) == 1 and len(mv[0]["params"]["mu"]) == 2 and len(trunc) == 3
    joint_idx = next(i for i, c in enumerate(creates)
                     if c["params"]["type"] == "truncated_mv_gaussian")
    joint_id = f"s_{joint_idx + 1}"  # SeqTransport assigns create-state ids in create order
    # both events (lookup Reaction + narrative MarginReaction) condition the SAME joint state
    assert sum(1 for c in conditions if c["params"]["state_id"] == joint_id) == 2


@pytest.mark.system
def test_live_narrative_good_on_abstain_moves_both_latents(model: U.UtilityModel) -> None:
    """The §7.1 joint fold end to end through the real skin: a good-on-abstain verdict
    ("right to withhold") is a low-margin observation, pushing u(wrong) DOWN and κ_att UP
    jointly; the untouched latents stay at their prior."""
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
    with B.Brain.spawn() as b:
        b.initialize()
        prior = U.posterior(b, model, [])          # the engine's continuous prior fold
        post = U.posterior(b, model, [_margin_good(0.6)])

    # Both prior and posterior are now CONTINUOUS engine folds: the coupled latents' joint is a
    # `truncated_mv_gaussian` whose per-coordinate marginal (n_per=64 at d=2) equals the 1-D
    # truncated prior (n=64). So baseline directly against the engine prior fold — no host grid,
    # no representation split (Phase B retired `_fold_joint`'s host grid).
    assert post.latents["u_wrong"].mean < prior.latents["u_wrong"].mean
    assert post.latents["kappa_att"].mean > prior.latents["kappa_att"].mean
    # u_hedged is UNCOUPLED → its own 1-D fold; it stays at its prior
    assert post.latents["u_hedged"].mean == pytest.approx(prior.latents["u_hedged"].mean)


@pytest.mark.system
def test_lookup_u_wrong_marginal_is_invariant_when_pulled_into_a_joint(
        model: U.UtilityModel) -> None:
    """A margin reaction flat in u(wrong) (coeff 0) structurally pulls it into the {u_wrong, κ_att}
    joint, but — independent prior product, lookup likelihood flat in κ_att — the joint factorises,
    so the marginalised u(wrong) equals the 1-D fold. Now that BOTH paths are the engine's
    continuous quadrature on the SAME u_wrong grid (the 1-D `truncated_gaussian` and the mv joint's
    u_wrong axis are both the 64-pt midpoint grid over [lo,hi]), and the flat margin depends only on
    κ_att (so it factors out of the u_wrong marginal, up to a constant that cancels),
    the marginalised u(wrong) equals the 1-D fold to machine precision."""
    if not (B._DEV_REPO or B._DEV_SERVER):
        pytest.skip("set $CREDENCE_REPO or $CREDENCE_SKIN_SERVER to spawn a dev engine")
    lookup = U.Reaction(tx_time="t", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.5)
    flat = U.MarginReaction(tx_time="t", coeffs=(("kappa_att", -1.0), ("u_wrong", 0.0)),
                            offset=0.0, reacted=True, sign=-1.0, tau_group="narrative")
    with B.Brain.spawn() as b:
        b.initialize()
        one_d = U.posterior(b, model, [lookup])
        joint = U.posterior(b, model, [lookup, flat])
    uw_1d, uw_joint = one_d.latents["u_wrong"], joint.latents["u_wrong"]
    assert uw_joint.mean == pytest.approx(uw_1d.mean, abs=1e-9)
    assert uw_joint.variance == pytest.approx(uw_1d.variance, abs=1e-9)
    assert uw_joint.variance == pytest.approx(uw_1d.variance, abs=1e-6)
