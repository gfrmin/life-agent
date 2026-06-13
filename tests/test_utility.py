"""The utility posterior (bayesian-foundations §4.4/§10 as amended) — utility.py.

Hermetic strata:
1. Pure parts numerically: model loading, gaussian grid priors, likelihood vectors
   (elicitation gaussian; reaction logistic with τ marginalised against its prior),
   endpoint-mass monitoring, Ū extraction, fold_version determinism.
2. The fold's RPC choreography over a scripted transport: one categorical state per
   latent (never the gauge pins), conditioning in tx order with the exact densities the
   pure functions produce, weights read, states destroyed.
3. ``@pytest.mark.system``: the live Julia fold against an independent Python reference
   (prior x likelihood, normalised) — the real numerical check.

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


# --- priors and likelihoods (pure) -------------------------------------------------------

def test_gaussian_weights_normalised_and_peaked_at_mu() -> None:
    vals = U.Grid(lo=-4.0, hi=4.0, n=9).values()
    w = U.gaussian_weights(vals, mu=0.0, sigma=1.0)
    assert sum(w) == pytest.approx(1.0)
    assert max(w) == w[vals.index(0.0)]
    assert w[0] == pytest.approx(w[-1])  # symmetric


def test_elicitation_log_density_peaks_at_stated_value() -> None:
    vals = (-10.0, -8.0, -6.0, -4.0)
    ld = U.elicitation_log_density(vals, stated_value=-8.0, sigma=2.0)
    assert max(ld) == ld[1]
    # exact gaussian log-density shape
    expected = -0.5 * ((-4.0 - -8.0) / 2.0) ** 2 - math.log(2.0 * math.sqrt(2 * math.pi))
    assert ld[3] == pytest.approx(expected)


def test_reaction_probability_is_tau_mixture_and_monotone() -> None:
    vals = (-6.0, -2.0, 0.0)
    taus = (0.5, 2.0)
    tau_w = (0.25, 0.75)
    p = U.reaction_probability(vals, taus, tau_w, sign=-1.0, threshold=0.0)
    # hand-computed mixture at x=-2: 0.25*sigmoid(2/0.5) + 0.75*sigmoid(2/2)
    expected = 0.25 / (1 + math.exp(-4.0)) + 0.75 / (1 + math.exp(-1.0))
    assert p[1] == pytest.approx(expected)
    # sign=-1: more-negative utility ⇒ higher reaction probability
    assert p[0] > p[1] > p[2]


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
        elif method == "weights":
            n = 0  # length must match the grid of whichever state — scripted uniform
            n = len(self._grid_for(req["params"]["state_id"]))
            result = {"weights": [1.0 / n] * n}
        else:
            result = "ok"
        return json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": result})

    def close(self) -> None:
        pass

    def _grid_for(self, state_id: str) -> list[float]:
        # the nth create_state call produced state id "s_n"
        creates = [r for r in self.sent if r["method"] == "create_state"]
        idx = int(state_id.split("_")[1]) - 1
        vals: list[float] = creates[idx]["params"]["space"]["values"]
        return vals


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
    # one categorical per latent — never for the gauge pins, never for τ
    assert len(creates) == len(U.REQUIRED_LATENTS)
    assert all(r["params"]["type"] == "categorical" for r in creates)
    assert len(destroys) == len(creates)
    # three conditions total, in tx order within each latent
    assert len(conditions) == 3
    # the u_wrong elicitation kernel carries the exact pure-function densities
    k0 = conditions[0]["params"]["kernel"]
    grid = model.latents["u_wrong"].grid.values()
    expected = U.elicitation_log_density(grid, stated_value=-8.0, sigma=2.0)
    assert k0["type"] == "tabular_log_density"
    assert k0["target_vals"] == [-8.0]
    assert [row[0] for row in k0["densities"]] == pytest.approx(list(expected))
    assert conditions[0]["params"]["observation"] == -8.0
    # the reaction kernel: two observation columns, P(react|x) from the τ-mixture
    k1 = conditions[1]["params"]["kernel"]
    assert k1["target_vals"] == [0.0, 1.0]
    tau_vals = model.tau.grid.values()
    tau_w = U.gaussian_weights(tau_vals, model.tau.prior_mu, model.tau.prior_sigma)
    p1 = U.reaction_probability(grid, tau_vals, tau_w, sign=-1.0, threshold=0.0)
    assert [row[1] for row in k1["densities"]] == pytest.approx(
        [math.log(p) for p in p1])
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
    lp = U.LatentPosterior(name="u_wrong", values=(-2.0, -1.0, 0.0),
                           weights=(0.5, 0.4, 0.1))
    post = U.UtilityPosterior(gauge=model.gauge, latents={"u_wrong": lp},
                              n_events=0, fold_version="0" * 64)
    warned = post.endpoint_warnings(threshold=0.01)
    assert warned and "u_wrong" in warned[0] and "widen" in warned[0]
    assert lp.endpoint_mass == pytest.approx(0.6)
    assert lp.mean == pytest.approx(0.5 * -2.0 + 0.4 * -1.0 + 0.1 * 0.0)


# --- live: the skin's fold against an independent Python reference -----------------------

@pytest.mark.system
def test_live_fold_matches_reference_and_moves_u_wrong_correctly(
        model: U.UtilityModel) -> None:
    repo = Path(B.CREDENCE_REPO)
    if not (repo / "apps/skin/server.jl").exists():
        pytest.skip(f"credence repo not found at {repo}")
    events: list[U.Evidence] = [
        U.Elicitation(tx_time="t1", latent="u_wrong", stated_value=-8.0, noise_sigma=2.0),
        U.Reaction(tx_time="t2", latent="u_wrong", reacted=True, sign=-1.0, threshold=0.0),
    ]
    with B.Brain.spawn() as b:
        b.initialize()
        post = U.posterior(b, model, events)

    spec = model.latents["u_wrong"]
    grid = spec.grid.values()
    prior_mean = sum(w * x for w, x in zip(
        U.gaussian_weights(grid, spec.prior_mu, spec.prior_sigma), grid, strict=True))
    # the verdict-shaped evidence must move Ū(u_wrong) down (the plan's smoke assertion)
    assert post.latents["u_wrong"].mean < prior_mean

    # independent reference: prior x elicitation-likelihood x reaction-likelihood
    ref = list(U.gaussian_weights(grid, spec.prior_mu, spec.prior_sigma))
    lik1 = [math.exp(ld) for ld in
            U.elicitation_log_density(grid, stated_value=-8.0, sigma=2.0)]
    tau_vals = model.tau.grid.values()
    tau_w = U.gaussian_weights(tau_vals, model.tau.prior_mu, model.tau.prior_sigma)
    lik2 = U.reaction_probability(grid, tau_vals, tau_w, sign=-1.0, threshold=0.0)
    ref = [r * l1 * l2 for r, l1, l2 in zip(ref, lik1, lik2, strict=True)]
    z = sum(ref)
    ref = [r / z for r in ref]
    assert list(post.latents["u_wrong"].weights) == pytest.approx(ref, abs=1e-9)


@pytest.mark.system
def test_live_reaction_loop_good_on_abstain_lowers_u_wrong(
        model: U.UtilityModel, tmp_path: Path) -> None:
    """The §4.4 loop end to end through the real skin: a good-on-abstain verdict, joined
    to its decision by decision_id, produces a Reaction that lowers Ū(u_wrong) — the
    owner's behaviour, not a fabricated number, moving the belief."""
    repo = Path(B.CREDENCE_REPO)
    if not (repo / "apps/skin/server.jl").exists():
        pytest.skip(f"credence repo not found at {repo}")
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
        post = U.posterior(b, model, list(events))
    spec = model.latents["u_wrong"]
    grid = spec.grid.values()
    prior_mean = sum(w * x for w, x in zip(
        U.gaussian_weights(grid, spec.prior_mu, spec.prior_sigma), grid, strict=True))
    assert post.latents["u_wrong"].mean < prior_mean


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
    nuw = model.latents["u_wrong"].grid.n
    nka = model.latents["kappa_att"].grid.n
    sizes = [len(c["params"]["space"]["values"]) for c in creates]
    # one JOINT categorical of size |u_wrong|*|κ_att|, plus 1-D states for the two
    # untouched latents — and NO standalone u_wrong / κ_att state
    assert sizes.count(nuw * nka) == 1
    assert len(creates) == 3 and nuw not in sizes and nka not in sizes
    # both coupled latents get a normalised marginal of the right length (a readout)
    assert len(post.latents["u_wrong"].weights) == nuw
    assert len(post.latents["kappa_att"].weights) == nka
    assert sum(post.latents["kappa_att"].weights) == pytest.approx(1.0)


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
    nuw = model.latents["u_wrong"].grid.n
    nka = model.latents["kappa_att"].grid.n
    sizes = [len(c["params"]["space"]["values"]) for c in creates]
    assert nuw * nka in sizes and nuw not in sizes  # u_wrong absorbed into the joint
    joint_idx = next(i for i, c in enumerate(creates)
                     if len(c["params"]["space"]["values"]) == nuw * nka)
    joint_id = f"s_{joint_idx + 1}"  # SeqTransport assigns ids in create order
    # both events condition the SAME joint state
    assert sum(1 for c in conditions if c["params"]["state_id"] == joint_id) == 2


@pytest.mark.system
def test_live_narrative_good_on_abstain_moves_both_latents(model: U.UtilityModel) -> None:
    """The §7.1 joint fold end to end through the real skin: a good-on-abstain verdict
    ("right to withhold") is a low-margin observation, pushing u(wrong) DOWN and κ_att UP
    jointly; the untouched latents stay at their prior."""
    repo = Path(B.CREDENCE_REPO)
    if not (repo / "apps/skin/server.jl").exists():
        pytest.skip(f"credence repo not found at {repo}")
    with B.Brain.spawn() as b:
        b.initialize()
        post = U.posterior(b, model, [_margin_good(0.6)])

    def prior_mean(name: str) -> float:
        s = model.latents[name]
        g = s.grid.values()
        return sum(w * x for w, x in zip(
            U.gaussian_weights(g, s.prior_mu, s.prior_sigma), g, strict=True))

    assert post.latents["u_wrong"].mean < prior_mean("u_wrong")
    assert post.latents["kappa_att"].mean > prior_mean("kappa_att")
    assert post.latents["u_hedged"].mean == pytest.approx(prior_mean("u_hedged"))
