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
- **The grid is a truncation, stated**: no hard zero *within* bounds chosen wide enough
  that endpoint mass stays negligible; endpoint mass is monitored and the remedy is
  widening, never renormalising. The finite grid also discharges §0's bounded-utility
  dependence by construction.
- Conditioning runs through the credence skin (:mod:`life_agent.core.brain`):
  categorical states + ``tabular_log_density`` kernels — one inference engine (L2),
  so later structured inference inherits the seam. Likelihood *vectors* are computed
  here (pure, unit-tested); the multiply-and-normalise is credence's.

The model file (gauge + grids + priors) lives at ``$LIFE_AGENT_KB/utility/model.yaml``
(schema example: ``config/utility-model.example.yaml``); elicitations at
``$LIFE_AGENT_KB/utility/elicitations.jsonl``. Both are personal data (PRINCIPLES §12).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from life_agent.core.brain import Brain

FORMAT_VERSION = 1

# The gauge convention (§4.4). The model file restates it and load_model verifies the
# restatement — a silently different gauge would re-scale every learned latent.
GAUGE: dict[str, float] = {"u_correct": 1.0, "u_abstain": 0.0}

# The v0 latents (lookup-family scope). Growing this set is a model.yaml + code change,
# never a silent addition.
REQUIRED_LATENTS: tuple[str, ...] = ("u_wrong", "u_hedged", "lambda_int", "kappa_att")

# Probability floor inside log() — the stated finite-arithmetic convention (the
# likelihood twin of outcomes.SCORE_EPS).
_PROB_EPS = 1e-12


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
        raise ValueError(f"model is missing required latent(s): {missing}")
    latents = {name: _latent_spec(name, latents_raw[name]) for name in REQUIRED_LATENTS}
    tau = _latent_spec("tau", raw["tau"])
    return UtilityModel(
        format_version=int(raw["format_version"]),
        gauge=gauge,
        latents=latents,
        tau=tau,
        endpoint_mass_warn=float(raw["endpoint_mass_warn"]),
    )


# --- priors and likelihood vectors (pure) ------------------------------------------------

def gaussian_weights(values: tuple[float, ...], mu: float,
                     sigma: float) -> tuple[float, ...]:
    """A gaussian discretised onto the grid, normalised — the stated prior shape."""
    raw = [math.exp(-0.5 * ((x - mu) / sigma) ** 2) for x in values]
    z = sum(raw)
    return tuple(r / z for r in raw)


def elicitation_log_density(values: tuple[float, ...], stated_value: float,
                            sigma: float) -> tuple[float, ...]:
    """log P(stated | latent = x) per grid point — a stated, generous noise model:
    elicitation is evidence, never definition (§4.4 stream 1)."""
    const = -math.log(sigma * math.sqrt(2 * math.pi))
    return tuple(-0.5 * ((stated_value - x) / sigma) ** 2 + const for x in values)


def reaction_probability(values: tuple[float, ...], tau_values: tuple[float, ...],
                         tau_weights: tuple[float, ...], *, sign: float,
                         threshold: float) -> tuple[float, ...]:
    """P(react = 1 | latent = x), the logistic choice model marginalised over the
    τ-prior: sum_t w_t * sigmoid((sign*x - threshold) / t). Covers the binary reaction shapes
    of §4.4 streams 2-5 (verdicts, corrections, re-asks)."""
    out: list[float] = []
    for x in values:
        p = sum(w / (1.0 + math.exp(-(sign * x - threshold) / t))
                for t, w in zip(tau_values, tau_weights, strict=True))
        out.append(p)
    return tuple(out)


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
    ``threshold`` is the stated effort bound."""

    tx_time: str
    latent: str
    reacted: bool
    sign: float
    threshold: float


Evidence = Elicitation | Reaction


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
    name: str
    values: tuple[float, ...]
    weights: tuple[float, ...]

    @property
    def mean(self) -> float:
        return sum(w * x for w, x in zip(self.weights, self.values, strict=True))

    @property
    def endpoint_mass(self) -> float:
        """Mass on the grid's edges — the truncation monitor (§4.4: widen, never
        renormalise)."""
        return self.weights[0] + self.weights[-1]


@dataclass(frozen=True)
class UtilityPosterior:
    gauge: dict[str, float]
    latents: dict[str, LatentPosterior]
    n_events: int
    fold_version: str

    def u_bar(self) -> dict[str, float]:
        """The posterior-mean utility — all a one-shot `optimise` needs (the collapse
        theorem, §4.4); width is consumed by the gate and, later, the governor."""
        return {**self.gauge, **{name: lp.mean for name, lp in self.latents.items()}}

    def endpoint_warnings(self, threshold: float) -> list[str]:
        """Truncation warnings: a latent piling mass at a grid edge needs a wider grid."""
        return [
            f"utility latent {name!r} holds {lp.endpoint_mass:.3f} mass at its grid "
            f"endpoints (> {threshold}) — the grid is clipping the posterior; widen it"
            for name, lp in self.latents.items() if lp.endpoint_mass > threshold
        ]


def fold_version(model: UtilityModel, events: list[Evidence]) -> str:
    """SHA-256 identity of (model, evidence-in-order) — pins exactly which utility
    posterior valued a decision (recorded per decision, decisions.py)."""
    payload = {
        "model": asdict(model),
        "events": [{"kind": type(e).__name__, **asdict(e)} for e in events],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _kernel_for(event: Evidence, values: tuple[float, ...],
                model: UtilityModel) -> tuple[dict[str, Any], float]:
    """The (tabular_log_density kernel, observation) pair for one evidence event."""
    if isinstance(event, Elicitation):
        ld = elicitation_log_density(values, stated_value=event.stated_value,
                                     sigma=event.noise_sigma)
        kernel = {"type": "tabular_log_density",
                  "source_vals": list(values),
                  "target_vals": [event.stated_value],
                  "densities": [[d] for d in ld]}
        return kernel, event.stated_value
    tau_values = model.tau.grid.values()
    tau_weights = gaussian_weights(tau_values, model.tau.prior_mu, model.tau.prior_sigma)
    p1 = reaction_probability(values, tau_values, tau_weights,
                              sign=event.sign, threshold=event.threshold)
    densities = [[math.log(max(1.0 - p, _PROB_EPS)), math.log(max(p, _PROB_EPS))]
                 for p in p1]
    kernel = {"type": "tabular_log_density",
              "source_vals": list(values),
              "target_vals": [0.0, 1.0],
              "densities": densities}
    return kernel, 1.0 if event.reacted else 0.0


def posterior(brain: Brain, model: UtilityModel,
              events: list[Evidence]) -> UtilityPosterior:
    """fold(model prior, evidence) → the utility posterior, conditioned through the
    credence skin. Events are consumed in the given order (the canonical replay order);
    the gauge pins are never conditioned — they have no state to condition."""
    by_latent: dict[str, list[Evidence]] = {name: [] for name in model.latents}
    for event in events:
        if event.latent not in by_latent:
            raise ValueError(f"evidence names unknown latent {event.latent!r}")
        by_latent[event.latent].append(event)

    latents: dict[str, LatentPosterior] = {}
    for name, spec in model.latents.items():
        values = spec.grid.values()
        prior = gaussian_weights(values, spec.prior_mu, spec.prior_sigma)
        state_id = brain.create_state({
            "type": "categorical",
            "space": {"type": "finite", "values": list(values)},
            "log_weights": [math.log(max(w, _PROB_EPS)) for w in prior],
        })
        try:
            for event in by_latent[name]:
                kernel, observation = _kernel_for(event, values, model)
                brain.condition(state_id, kernel=kernel, observation=observation)
            weights = tuple(brain.weights(state_id))
        finally:
            brain.destroy_state(state_id)
        latents[name] = LatentPosterior(name=name, values=values, weights=weights)

    return UtilityPosterior(
        gauge=dict(model.gauge),
        latents=latents,
        n_events=len(events),
        fold_version=fold_version(model, events),
    )
