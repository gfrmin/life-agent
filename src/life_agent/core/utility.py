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
  stated support ``[lo, hi]`` (a sign/range constraint, e.g. ``u_wrong ≤ 0``), integrated over
  that support. Endpoint proximity is monitored and the remedy is widening the
  support, never renormalising. The bounded support discharges §0's bounded-utility dependence by
  construction.
- Conditioning is local quadrature (the section above ``_fold``): each latent is a
  continuous truncated Gaussian on its stated support, integrated on a grid the support fixes;
  coupled latents share a product grid. Elicitations read a latent through a Gaussian; reactions
  through the tau-marginalised logistic choice, on one latent or on a raw EU margin.

The model file (gauge + grids + priors) lives at ``$LIFE_AGENT_KB/utility/model.yaml``
(schema example: ``config/utility-model.example.yaml``); elicitations at
``$LIFE_AGENT_KB/utility/elicitations.jsonl``. Both are personal data (PRINCIPLES §12).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from life_agent.core import answer_shape as AS
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

# r30 (`docs/unification/reports/r30-units-lever.md`): the six OPTIONAL per-shape utility
# scale latents — `voi_scale_<shape>`/`regret_scale_<shape>` for each of
# `answer_shape.SCALED_SHAPES` (never retyped here — the shape vocabulary has one
# spelling). Deliberately NOT in REQUIRED_LATENTS: unlike lambda_usd, which the gate's
# spend term needs unconditionally, these six default to 1.0 in `decide.shaped_u_bar`
# when absent, so a model file may opt a shape in without every other model file (every
# test fixture, the owner's live deployed copy) being forced to declare it the day this
# merges — the `tau_narrative` precedent, not the `lambda_usd` one.
SHAPE_LATENT_NAMES: tuple[str, ...] = tuple(
    f"{kind}_scale_{shape}" for shape in AS.SCALED_SHAPES for kind in ("voi", "regret"))

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
    # r30: each optional shape-scale latent parses through the SAME generic path iff the
    # owner's file declares it — absent ones simply never enter `model.latents`, and
    # `decide.shaped_u_bar` supplies their 1.0 default at read time (never here).
    for name in SHAPE_LATENT_NAMES:
        if name in latents_raw:
            latents[name] = _latent_spec(name, latents_raw[name])
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


# --- the posterior (a fold of the evidence) --------------------------------------------

@dataclass(frozen=True)
class LatentPosterior:
    """A latent's posterior summary: the wire-read ``mean`` (the only causal input — it builds Ū)
    and ``variance`` (telemetry: the gate's MC + the support-clipping diagnostic), plus the support
    bounds ``lo, hi``."""

    name: str
    mean: float
    variance: float
    lo: float
    hi: float

    @property
    def near_bound(self) -> bool:
        """The support-clipping monitor: the posterior mean sits within 1sigma of a support edge, so
        the stated bound [lo,hi] may be clipping the posterior — widen it."""
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
    # Order by model position of each component's earliest latent (deterministic).
    order = {name: i for i, name in enumerate(latents)}
    return sorted((frozenset(g) for g in groups.values()),
                  key=lambda c: min(order[n] for n in c))


# --- the quadrature (the engine's arithmetic, now local) ----------------------------------
# Each latent is a truncated Gaussian on its stated support, integrated on a midpoint grid
# the support fixes: 64 points in 1-D; a coupled component of d latents shares a product grid
# of floor(65536^(1/d)) points per axis (capped at 64). A reaction integrates its choice
# temperature tau on 32 midpoints of tau's support. The grids are computation, not model:
# the declared model stays continuous. Log weights are renormalised after every event.

_GRID_1D = 64
_MV_POINT_BUDGET = 65536
_TAU_POINTS = 32
_FLOOR = 1e-300


def _midpoints(lo: float, hi: float, n: int) -> list[float]:
    return [lo + (k - 0.5) * (hi - lo) / n for k in range(1, n + 1)]


def _points_per_axis(d: int) -> int:
    return min(64, max(1, int(_MV_POINT_BUDGET ** (1 / d))))


def _product(axes: list[list[float]]) -> list[tuple[float, ...]]:
    """Every point of the product grid, last axis fastest."""
    return [tuple(p) for p in itertools.product(*axes)]


def _normalised(log_w: list[float]) -> list[float]:
    top = max(log_w)
    log_total = top + math.log(sum(math.exp(x - top) for x in log_w))
    return [x - log_total for x in log_w]


def _weights(log_w: list[float]) -> list[float]:
    top = max(log_w)
    w = [math.exp(x - top) for x in log_w]
    total = sum(w)
    return [x / total for x in w]


def _p_react(g: float, tau: LatentSpec) -> float:
    """P(react = 1 | feature g) = E_tau[sigmoid(g / tau)], tau ~ N(mu, sigma) on its support."""
    p1 = z = 0.0
    for t in _midpoints(tau.grid.lo, tau.grid.hi, _TAU_POINTS):
        w = math.exp(-0.5 * ((t - tau.prior_mu) / tau.prior_sigma) ** 2)
        z += w
        p1 += w / (1.0 + math.exp(-g / t))
    return p1 / z


def _react_ll(p1: float, reacted: bool) -> float:
    return math.log(max(p1 if reacted else 1.0 - p1, _FLOOR))


def _log_likelihood(event: Evidence, names: list[str],
                    model: UtilityModel) -> Callable[[Sequence[float]], float]:
    """The event's log-likelihood at a point of the component's latents (``names`` order).
    An elicitation is a Gaussian reading of one latent; a reaction is the tau-marginalised
    logistic choice on one latent against its threshold; a margin reaction is the same
    choice on the raw margin ``Σ coeff·x - offset`` (event-shape tau)."""
    if isinstance(event, Elicitation):
        j, var = names.index(event.latent), event.noise_sigma ** 2
        return lambda x: -0.5 * (event.stated_value - x[j]) ** 2 / var
    if isinstance(event, Reaction):
        j = names.index(event.latent)
        return lambda x: _react_ll(
            _p_react(event.sign * x[j] - event.threshold, model.tau), event.reacted)
    tau = model.tau_narrative if event.tau_group == "narrative" else model.tau
    coeff = dict(event.coeffs)
    cs = [coeff.get(n, 0.0) for n in names]

    def margin_ll(x: Sequence[float]) -> float:
        margin = 0.0
        for c, xi in zip(cs, x, strict=True):
            margin += c * xi
        return _react_ll(_p_react(event.sign * (margin - event.offset), tau), event.reacted)
    return margin_ll


def _moments(grid: Sequence[float], log_w: list[float]) -> tuple[float, float]:
    w = _weights(log_w)
    mean = 0.0
    for wi, x in zip(w, grid, strict=True):
        mean += wi * x
    var = 0.0
    for wi, x in zip(w, grid, strict=True):
        var += wi * (x - mean) ** 2
    return mean, var


def _fold(model: UtilityModel, comp: frozenset[str],
          events: list[Evidence]) -> dict[str, LatentPosterior]:
    """One connected component's posterior, read back per latent as mean and variance. The
    prior is independent truncated Gaussians (no invented correlation); coupling enters only
    through a margin reaction's likelihood. A lone latent is the d = 1 case on 64 points."""
    names = sorted(comp)
    specs = [model.latents[n] for n in names]
    n_axis = _GRID_1D if len(names) == 1 else _points_per_axis(len(names))
    axes = [_midpoints(s.grid.lo, s.grid.hi, n_axis) for s in specs]
    points = _product(axes)
    log_w = []
    for x in points:
        lw = 0.0
        for xi, s in zip(x, specs, strict=True):
            lw += -0.5 * ((xi - s.prior_mu) / s.prior_sigma) ** 2
        log_w.append(lw)
    if len(names) > 1:
        log_w = _normalised(log_w)
    for event in events:
        ll = _log_likelihood(event, names, model)
        log_w = _normalised([w + ll(x) for w, x in zip(log_w, points, strict=True)])
    if len(names) == 1:
        marginals = [log_w]
    else:
        w = _weights(log_w)
        stride = [math.prod(len(a) for a in axes[j + 1:]) for j in range(len(axes))]
        marginals = []
        for j, axis in enumerate(axes):
            mass = [0.0] * len(axis)
            for flat, wi in enumerate(w):
                mass[(flat // stride[j]) % len(axis)] += wi
            marginals.append(_normalised([math.log(max(m, _FLOOR)) for m in mass]))
    out: dict[str, LatentPosterior] = {}
    for name, spec, axis, marginal in zip(names, specs, axes, marginals, strict=True):
        mean, var = _moments(axis, marginal)
        out[name] = LatentPosterior(name=name, mean=mean, variance=var,
                                    lo=spec.grid.lo, hi=spec.grid.hi)
    return out


def posterior(model: UtilityModel, events: list[Evidence], *,
              policy: str) -> UtilityPosterior:
    """fold(model prior, evidence) → the utility posterior. Events are consumed in order (the
    canonical replay order). Latents a MarginReaction couples fold on a joint grid; independent
    latents fold 1-D — the
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
        latents.update(_fold(model, comp, [e for e in events if _event_latents(e) & comp]))

    return UtilityPosterior(
        gauge=dict(model.gauge),
        latents=latents,
        n_events=len(events),
        fold_version=fold_version(model, events, policy),
        policy=policy,
    )
