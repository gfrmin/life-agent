"""The utility posterior — utility as inference (bayesian-foundations §4.4/§10).

The agent holds a *belief* about the owner's preferences, never a table: gauge-pinned
(u(correct) = +1, u(abstain) = 0 — convention, since behaviour identifies utility only
up to positive affine transform), with the remaining latents (u_wrong, u_hedged, the
interruption cost λ_int, the per-claim attention cost κ_att) as grid-discretised
posteriors learned from evidence. Design commitments, all from the amended foundations:

- **Fold, not store**: the posterior is recomputed from the model file + the evidence
  streams at need; the only persistent state is the append-only evidence (elicitations
  now; decision-log joins from slice 2b). Event order is the canonical replay order.
- **τ is marginalised against its prior, never updated** — τ and U are non-identifiable
  from choice data in principle (Armstrong-Mindermann); the hierarchical τ-prior does
  the separating, permanently. v0 makes that literal: reaction likelihoods integrate
  over the τ-prior, so each observation is a clean one-dimensional update (the gauge
  pins kill most cross-latent coupling).
- **Learning is passive** (a stated action-set coarsening): evidence arrives from the
  owner's behaviour and owner-initiated elicitation; the agent never probes preferences
  until the governor can price the sequential value.
- **Bounds are stated support, not a grid**: each latent is a CONTINUOUS truncated Gaussian on a
  stated support ``[lo, hi]`` (a sign/range constraint, e.g. ``u_wrong ≤ 0``); the engine integrates
  over the support internally. Endpoint proximity is monitored and the remedy is widening the
  support, never renormalising. The bounded support discharges §0's bounded-utility dependence by
  construction.
- Conditioning runs through the credence skin (:mod:`life_agent.core.brain`): continuous
  ``truncated_gaussian`` (1-D) / ``truncated_mv_gaussian`` (coupled) states + declared kernels
  (``gaussian_known_var``, ``logistic_reaction``, ``linear_gaussian``, ``margin_reaction``) — one
  inference engine (L2), which owns all quadrature. The body declares data and reads moments
  (``mean``/``expect``/``marginal``); it builds no grid and no density vector (the discretisation
  antipattern, retired).

The model file (gauge + grids + priors) lives at ``$LIFE_AGENT_KB/utility/model.yaml``
(schema example: ``config/utility-model.example.yaml``); elicitations at
``$LIFE_AGENT_KB/utility/elicitations.jsonl``. Both are personal data (PRINCIPLES §12).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from life_agent.core.brain import Brain
from life_agent.core.decisions import POLICIES

FORMAT_VERSION = 1

# The gauge convention (§4.4). The model file restates it and load_model verifies the
# restatement — a silently different gauge would re-scale every learned latent.
GAUGE: dict[str, float] = {"u_correct": 1.0, "u_abstain": 0.0}

# The v0 latents (lookup-family scope). Growing this set is a model.yaml + code change,
# never a silent addition. lambda_usd (plan item C, 2026-08-08) is the $↔utility
# exchange rate — gauge units per USD, positive by domain (a rate, like tau: the grid
# floor is a constraint, not a preference). Its prior — N(1.0, 0.35) on [0, 8],
# TRUNCATED MEAN ≈ 1.002 (computed, not assumed; drift-gated in tests — the #67 review
# caught an N(1,1) draft whose truncated mean was 1.288, a silent 29% re-pricing) —
# encodes the months-operating $1 ≈ 1·u_correct convention within 0.2%, frozen BEFORE
# any elicitation; the owner's elicitations.jsonl line narrows it. Consumers: executor
# menu/grow pricing (usd x rate at the decide payload) and gate.realised_utility's
# -rate*cost_usd spend term (run-6, pre-registered in bayesian-foundations §14).
REQUIRED_LATENTS: tuple[str, ...] = ("u_wrong", "u_wrong_scoped", "u_hedged",
                                     "lambda_int", "kappa_att", "lambda_usd")

@dataclass(frozen=True)
class Grid:
    """An inclusive, evenly spaced grid — a stated truncation (§4.4)."""

    lo: float
    hi: float
    n: int

    def values(self) -> tuple[float, ...]:
        if self.n < 2 or self.hi <= self.lo:
            raise ValueError(f"degenerate grid: lo={self.lo} hi={self.hi} n={self.n}")
        step = (self.hi - self.lo) / (self.n - 1)
        return tuple(self.lo + i * step for i in range(self.n))


@dataclass(frozen=True)
class LatentSpec:
    name: str
    grid: Grid
    prior_mu: float
    prior_sigma: float


@dataclass(frozen=True)
class UtilityModel:
    format_version: int
    gauge: dict[str, float]
    latents: dict[str, LatentSpec]
    tau: LatentSpec
    # The narrative event-shape τ-prior (§4.4: τ keyed on event-shape so the lookup
    # threshold form and the raw narrative margin do not silently cross-weight). Falls
    # back to ``tau`` when the model file omits it (pre-narrative models).
    tau_narrative: LatentSpec
    endpoint_mass_warn: float


def _latent_spec(name: str, raw: dict[str, Any]) -> LatentSpec:
    grid = raw["grid"]
    prior = raw["prior"]
    if prior.get("type") != "gaussian":
        raise ValueError(f"latent {name!r}: only gaussian priors are declared in v0")
    return LatentSpec(
        name=name,
        grid=Grid(lo=float(grid["lo"]), hi=float(grid["hi"]), n=int(grid["n"])),
        prior_mu=float(prior["mu"]),
        prior_sigma=float(prior["sigma"]),
    )


def load_model(path: Path) -> UtilityModel:
    """Parse and validate the utility model. Loud on anything missing or off-gauge."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    gauge = {k: float(v) for k, v in raw["gauge"].items()}
    if gauge != GAUGE:
        raise ValueError(f"gauge mismatch: file says {gauge}, the convention is {GAUGE} "
                         "— the gauge is a convention, not an estimate (§4.4)")
    latents_raw = raw["latents"]
    missing = [name for name in REQUIRED_LATENTS if name not in latents_raw]
    if missing:
        raise ValueError(
            f"model is missing required latent(s): {missing} — copy the line(s) from "
            "config/utility-model.example.yaml into $LIFE_AGENT_KB/utility/model.yaml "
            "(additive and deploy-order-safe; a file without lambda_usd predates plan "
            "item C, 2026-08-08)")
    latents = {name: _latent_spec(name, latents_raw[name]) for name in REQUIRED_LATENTS}
    tau = _latent_spec("tau", raw["tau"])
    tau_narrative = (_latent_spec("tau_narrative", raw["tau_narrative"])
                     if "tau_narrative" in raw else tau)
    return UtilityModel(
        format_version=int(raw["format_version"]),
        gauge=gauge,
        latents=latents,
        tau=tau,
        tau_narrative=tau_narrative,
        endpoint_mass_warn=float(raw["endpoint_mass_warn"]),
    )


# Priors and likelihoods are declared CONTINUOUS and conditioned engine-side: a latent is a
# `truncated_gaussian` (1-D) or a `truncated_mv_gaussian` (coupled); an event ships a kernel spec
# (`gaussian_known_var`/`logistic_reaction`/`linear_gaussian`/`margin_reaction`). The host builds no
# grid and no density table — the engine owns the quadrature. (The retired host helpers
# `gaussian_weights`/`elicitation_log_density`/`reaction_probability` were the discretisation
# antipattern; see _kernel_for / _joint_kernel.)


# --- evidence (closed types; order is the canonical replay order) ------------------------

@dataclass(frozen=True)
class Elicitation:
    """§4.4 stream 1: a stated value, conditioning under a generous noise likelihood."""

    tx_time: str
    latent: str
    stated_value: float
    noise_sigma: float


@dataclass(frozen=True)
class Reaction:
    """§4.4 streams 2-5 in their common v0 shape: a binary owner reaction read as
    logistic choice evidence on one latent (τ marginalised). ``sign`` orients the
    latent (-1: more-negative utility makes reaction likelier, the correction shape);
    ``threshold`` is the stated effort bound. The single-latent (lookup) special case
    of :class:`MarginReaction` — frozen in this form, never re-folded (§4.4)."""

    tx_time: str
    latent: str
    reacted: bool
    sign: float
    threshold: float


@dataclass(frozen=True)
class MarginReaction:
    """§4.4/§7.1: a soft observation on the **sign of an EU-margin linear in several
    latents** — ``margin(x) = Σ coeffs[l]·x_l - offset``, with
    ``P(react=1|x) = Σ_τ w_τ·sigmoid(sign·margin/τ)``, τ drawn from ``tau_group``'s prior
    (event-shape keyed, §4.4). Carries the multi-latent narrative inclusion boundary
    (u_wrong, κ_att). The margin is **raw** (gauge units), so per-latent informativeness
    is ∂margin/∂x_l = coeffs[l] — the correct weighting, not normalised. ``coeffs`` is a
    tuple of (latent, coefficient) pairs, normalised to sorted order in ``__post_init__``:
    the fold is order-independent, but ``fold_version`` hashes the event verbatim, so a
    canonical order keeps the cache key deterministic across constructions."""

    tx_time: str
    coeffs: tuple[tuple[str, float], ...]
    offset: float
    reacted: bool
    sign: float
    tau_group: str = "narrative"

    def __post_init__(self) -> None:
        object.__setattr__(self, "coeffs", tuple(sorted(self.coeffs)))


Evidence = Elicitation | Reaction | MarginReaction


def load_elicitations(path: Path, model: UtilityModel) -> list[Elicitation]:
    """The elicitation evidence in file order. Missing file = zero elicitations — a
    working state (the prior carries v0). Unknown latent names are loud."""
    if not path.exists():
        return []
    events: list[Elicitation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        obj = json.loads(line)
        latent = str(obj["latent"])
        if latent not in model.latents:
            raise ValueError(f"elicitation names unknown latent {latent!r} "
                             f"(declared: {list(model.latents)})")
        events.append(Elicitation(
            tx_time=str(obj["tx_time"]), latent=latent,
            stated_value=float(obj["stated_value"]),
            noise_sigma=float(obj["noise_sigma"]),
        ))
    return events


# --- the posterior (a fold through the brain) --------------------------------------------

@dataclass(frozen=True)
class LatentPosterior:
    """A latent's posterior summary: the wire-read ``mean`` (the only causal input — it builds Ū)
    and ``variance`` (telemetry: the gate's MC + the support-clipping diagnostic), plus the support
    bounds ``lo, hi``. The full posterior shape lives engine-side; the body holds only summaries."""

    name: str
    mean: float
    variance: float
    lo: float
    hi: float

    @property
    def near_bound(self) -> bool:
        """The support-clipping monitor: the posterior mean sits within 1sigma of a support edge, so
        the stated bound [lo,hi] may be clipping the posterior — widen it (the continuous successor
        of the old grid-endpoint-mass warning, now that the engine owns the quadrature)."""
        import math as _m
        sd = _m.sqrt(max(self.variance, 0.0))
        return (self.mean - self.lo) < sd or (self.hi - self.mean) < sd


@dataclass(frozen=True)
class UtilityPosterior:
    gauge: dict[str, float]
    latents: dict[str, LatentPosterior]
    n_events: int
    fold_version: str
    policy: str

    def u_bar(self) -> dict[str, float]:
        """The posterior-mean utility — all a one-shot `optimise` needs (the collapse
        theorem, §4.4); width is consumed by the gate and, later, the governor."""
        return {**self.gauge, **{name: lp.mean for name, lp in self.latents.items()}}

    def endpoint_warnings(self, threshold: float) -> list[str]:
        """Support-clipping warnings: a latent whose posterior mean sits within 1sigma of a support
        edge may need a wider stated bound [lo,hi]. (``threshold`` is retained for the call
        signature; the continuous monitor uses the 1sigma proximity in ``near_bound``.)"""
        return [
            f"utility latent {name!r}: mean {lp.mean:.3f} is within 1sigma of its support "
            f"[{lp.lo}, {lp.hi}] — the stated bound may be clipping the posterior; widen it"
            for name, lp in self.latents.items() if lp.near_bound
        ]


def _check_policy(policy: str) -> None:
    # the vocabulary has ONE spelling — decisions.py's record schema declares it (a policy
    # swap is visible in the record); the fold validates membership and enforces the set.
    if policy not in POLICIES:
        raise ValueError(
            f"unknown evidence policy {policy!r}; declared policies: {sorted(POLICIES)}")


def fold_version(model: UtilityModel, events: list[Evidence], policy: str) -> str:
    """SHA-256 identity of (model, evidence-in-order, policy) — pins exactly which utility
    posterior valued a decision (recorded per decision, decisions.py). The policy name is
    part of the identity (Q-O5): a memo keyed by it can never serve one regime's U-bar to
    the other regime's caller."""
    _check_policy(policy)
    payload = {
        "model": asdict(model),
        "events": [{"kind": type(e).__name__, **asdict(e)} for e in events],
        "policy": policy,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _kernel_for(event: Evidence, model: UtilityModel) -> tuple[dict[str, Any], float]:
    """The (likelihood kernel, observation) pair for one single-latent event — a CONTINUOUS-domain
    kernel the engine evaluates/quadratures over the latent's support; no grid, no host densities.
    An Elicitation is a Gaussian obs (`gaussian_known_var` → NormalNormal); a Reaction is the
    τ-marginalised logistic (`logistic_reaction`, continuous τ from the model's `tau` prior)."""
    if isinstance(event, Elicitation):
        var = event.noise_sigma ** 2
        return {"type": "gaussian_known_var", "variance": var}, event.stated_value
    assert isinstance(event, Reaction)  # _fold_1d never routes a MarginReaction here
    tau = model.tau
    kernel = {"type": "logistic_reaction", "sign": event.sign, "threshold": event.threshold,
              "tau_mu": tau.prior_mu, "tau_sigma": tau.prior_sigma,
              "tau_lo": tau.grid.lo, "tau_hi": tau.grid.hi}
    return kernel, 1.0 if event.reacted else 0.0


def _event_latents(event: Evidence) -> frozenset[str]:
    """The latents an event's likelihood touches — one for Elicitation/Reaction, the
    whole coeff set for a MarginReaction (its margin couples them)."""
    if isinstance(event, MarginReaction):
        return frozenset(name for name, _ in event.coeffs)
    return frozenset({event.latent})


def _components(latents: dict[str, LatentSpec],
                events: list[Evidence]) -> list[frozenset[str]]:
    """Connected components of the latent co-occurrence graph (§4.4): two latents share a
    component iff some event's likelihood couples them. A latent touched by nothing is its
    own singleton (it keeps its prior). Order is deterministic (by least latent name)."""
    parent: dict[str, str] = {n: n for n in latents}

    def find(a: str) -> str:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for event in events:
        touched = sorted(_event_latents(event))
        for other in touched[1:]:
            parent[find(touched[0])] = find(other)

    groups: dict[str, set[str]] = {}
    for n in parent:
        groups.setdefault(find(n), set()).add(n)
    # Order by model position of each component's earliest latent, so the single-latent
    # fold order (hence the brain-call choreography) is byte-identical to v0.
    order = {name: i for i, name in enumerate(latents)}
    return sorted((frozenset(g) for g in groups.values()),
                  key=lambda c: min(order[n] for n in c))


def _fold_1d(brain: Brain, model: UtilityModel, name: str,
             events: list[Evidence]) -> LatentPosterior:
    """The single-latent fold: a CONTINUOUS truncated-Gaussian latent on its stated support
    [lo,hi], conditioned by each event's kernel in order. The engine quadratures the support
    internally — the body declares only {mu, sigma, lo, hi} and reads back mean + variance (no
    grid, no host density). The posterior mean is the only causal output (it builds Ū)."""
    spec = model.latents[name]
    state_id = brain.create_state({
        "type": "truncated_gaussian",
        "mu": spec.prior_mu, "sigma": spec.prior_sigma,
        "lo": spec.grid.lo, "hi": spec.grid.hi,
    })
    try:
        for event in events:
            kernel, observation = _kernel_for(event, model)
            brain.condition(state_id, kernel=kernel, observation=observation)
        m = brain.mean(state_id)
        # variance = E[(x-mean)^2] via the centered_power functional (a wire expect, no host fold)
        var = brain.expect(state_id, function={"type": "centered_power", "n": 2, "mu": m})
    finally:
        brain.destroy_state(state_id)
    return LatentPosterior(name=name, mean=m, variance=var, lo=spec.grid.lo, hi=spec.grid.hi)


def _joint_kernel(event: Evidence, names: list[str],
                  model: UtilityModel) -> tuple[dict[str, Any], float]:
    """The (kernel spec, observation) for one event over the COUPLED `names` (the component's
    sorted order = the mv latent's coordinate order). A single-latent event is a coefficient
    vector e_j; a MarginReaction's `Σ coeff·x - offset` couples them. Elicitation → a coordinate
    Gaussian (`linear_gaussian`, coeffs=e_j); reaction/margin → a `margin_reaction` over the linear
    functional. The engine integrates the box and τ — no host density table, no grid."""
    if isinstance(event, Elicitation):
        coeffs = [1.0 if n == event.latent else 0.0 for n in names]
        return ({"type": "linear_gaussian", "coeffs": coeffs,
                 "variance": event.noise_sigma ** 2}, event.stated_value)
    if isinstance(event, Reaction):
        coeffs = [1.0 if n == event.latent else 0.0 for n in names]
        tau = model.tau
        return ({"type": "margin_reaction", "coeffs": coeffs, "offset": 0.0,
                 "sign": event.sign, "threshold": event.threshold,
                 "tau_mu": tau.prior_mu, "tau_sigma": tau.prior_sigma,
                 "tau_lo": tau.grid.lo, "tau_hi": tau.grid.hi},
                1.0 if event.reacted else 0.0)
    # MarginReaction — the raw margin, event-shape τ
    tspec = model.tau_narrative if event.tau_group == "narrative" else model.tau
    coeff_map = dict(event.coeffs)
    coeffs = [coeff_map.get(n, 0.0) for n in names]
    return ({"type": "margin_reaction", "coeffs": coeffs, "offset": event.offset,
             "sign": event.sign, "threshold": 0.0,
             "tau_mu": tspec.prior_mu, "tau_sigma": tspec.prior_sigma,
             "tau_lo": tspec.grid.lo, "tau_hi": tspec.grid.hi},
            1.0 if event.reacted else 0.0)


def _fold_joint(brain: Brain, model: UtilityModel, comp: frozenset[str],
                events: list[Evidence]) -> dict[str, LatentPosterior]:
    """The multi-latent fold (§7.1): the coupled latents' joint posterior, computed ENGINE-SIDE as a
    `truncated_mv_gaussian` on the box ∏[lo,hi] (prior = independent truncated Gaussians —
    no invented correlation), conditioned by every event touching the component in order, then read
    back per-latent with `marginal`. The engine owns the joint grid and integrates the other
    coordinates over it — the body builds no grid, no density, and does no marginal arithmetic
    (Invariant 1). Coupling enters only through the margin-reaction likelihood."""
    names = sorted(comp)
    specs = [model.latents[n] for n in names]
    joint = brain.create_state({
        "type": "truncated_mv_gaussian",
        "mu": [s.prior_mu for s in specs],
        "sigma": [s.prior_sigma for s in specs],
        "lo": [s.grid.lo for s in specs],
        "hi": [s.grid.hi for s in specs],
    })
    out: dict[str, LatentPosterior] = {}
    try:
        for event in events:
            kernel, observation = _joint_kernel(event, names, model)
            brain.condition(joint, kernel=kernel, observation=observation)
        # Read each latent's marginal off the engine's OWN joint grid: `marginal(axis)` registers a
        # NEW scalar state (the engine sums out the other coords), which we read like a 1-D fold
        # — mean + centered_power variance — then destroy. No host marginal arithmetic.
        for j, name in enumerate(names):
            marg = brain.marginal(joint, axis=j)
            try:
                m = brain.mean(marg)
                v = brain.expect(marg, function={"type": "centered_power", "n": 2, "mu": m})
            finally:
                brain.destroy_state(marg)
            gspec = model.latents[name].grid
            out[name] = LatentPosterior(name=name, mean=m, variance=v, lo=gspec.lo, hi=gspec.hi)
    finally:
        brain.destroy_state(joint)
    return out


def posterior(brain: Brain, model: UtilityModel,
              events: list[Evidence], *, policy: str) -> UtilityPosterior:
    """fold(model prior, evidence) → the utility posterior, conditioned through the
    credence skin. Events are consumed in order (the canonical replay order). Latents a
    MarginReaction couples fold on a joint grid; independent latents fold 1-D — the
    connected components of the latent co-occurrence graph (§4.4). The gauge pins are
    never conditioned — they have no state to condition.

    ``policy`` is the regime indicator (Q-O5/D-8): it names a DECLARED conditioning set,
    enforced structurally — ``frozen-elicitations`` (the gate's blind regime: the model
    file + the committed elicitation set, nothing else) refuses any verdict-projected
    event; ``all-to-date`` (the decider's regime) accepts elicitations + the
    verdict→evidence projection. Two conditioning sets over one probability model; which
    set ranked a decision is part of that decision's record (§5.1)."""
    _check_policy(policy)
    if policy == "frozen-elicitations":
        for event in events:
            if not isinstance(event, Elicitation):
                raise ValueError(
                    f"frozen-elicitations refuses {type(event).__name__} evidence "
                    f"(tx_time={event.tx_time!r}): the blind regime folds the committed "
                    "elicitation set only — fold under policy=\'all-to-date\' instead")
    for event in events:
        for name in _event_latents(event):
            if name not in model.latents:
                raise ValueError(f"evidence names unknown latent {name!r}")

    latents: dict[str, LatentPosterior] = {}
    for comp in _components(model.latents, events):
        comp_events = [e for e in events if _event_latents(e) & comp]
        if len(comp) == 1 and not any(isinstance(e, MarginReaction) for e in comp_events):
            (name,) = tuple(comp)
            latents[name] = _fold_1d(brain, model, name, comp_events)
        else:
            latents.update(_fold_joint(brain, model, comp, comp_events))

    return UtilityPosterior(
        gauge=dict(model.gauge),
        latents=latents,
        n_events=len(events),
        fold_version=fold_version(model, events, policy),
        policy=policy,
    )
