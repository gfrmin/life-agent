"""Component 1 of the aggregate family — the recall term + generator registry.

``docs/aggregate-family-design.md`` §5 (recall estimated from periodic generators: a
generator's schedule declares the EXPECTED slots, so retrieving 9 of 12 is nine Bernoulli
successes and three failures — misses are observations, not absences) and §9 (the registry
contract: a schedule is a claim about the world; an uncited or malformed entry never
enters the denominator). Library-only at CP-B (r19): nothing on the decision path imports
this module — the family plumbing arrives at CP-D under its own pre-registration.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from life_agent.core.brain import Brain

CADENCES: frozenset[str] = frozenset({"monthly", "quarterly", "annual"})

# Deliberately not Beta(1, 1): uniform recall is a strong and false belief about
# retrieval, not a neutral one (§5). Weakly optimistic (mean 2/3 — on a covered scope a
# document is more often retrieved than not) and weak (strength 4.5 < one monthly scope's
# 12 slots, so a single scope overturns it). Frozen blind in r19.
_RECALL_PRIOR: tuple[float, float] = (3.0, 1.5)

_BERNOULLI: dict[str, str] = {"type": "bernoulli"}


@dataclass(frozen=True)
class Generator:
    """One declared periodic generator (§9 entry shape)."""

    generator_id: str
    kind: str
    cadence: str
    active_from: date
    active_to: date | None
    scope_keys: frozenset[str]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Scope:
    """The question-side binding: a scope key + a closed period."""

    key: str
    start: date
    end: date


@dataclass(frozen=True)
class RecallPosterior:
    """The recall term's wire-read moments + the named slot census. ``estimated=False``
    means no generator covered the scope: prior moments, zero conditions — the caller
    renders readout 2's unmodelled-recall sentence, never an interval no data touched."""

    mean: float
    variance: float
    estimated: bool
    n_slots: int
    n_hits: int
    expected: tuple[str, ...]
    hit: tuple[str, ...]
    missed: tuple[str, ...]
    extra_hits: tuple[str, ...]
    prior: tuple[float, float]


class RegistryError(Exception):
    """A registry entry failed validation or admissibility (§9) — always loud."""


@dataclass(frozen=True)
class LoadedRegistry:
    """Admissible entries + the sha256 of the registry file's bytes (§9 replay
    determinism — CP-D records the hash onto every decision record it conditions)."""

    entries: tuple[Generator, ...]
    content_hash: str


def _window(generator: Generator, scope: Scope) -> tuple[date, date] | None:
    lo = max(generator.active_from, scope.start)
    hi = min(generator.active_to, scope.end) if generator.active_to else scope.end
    return (lo, hi) if lo <= hi else None


def expected_slots(generator: Generator, scope: Scope) -> tuple[str, ...]:
    """Deterministic calendar enumeration (host arithmetic, not inference) over the
    intersection of the scope period with the generator's active window."""
    w = _window(generator, scope)
    if w is None:
        return ()
    lo, hi = w
    if generator.cadence == "monthly":
        n0, n1 = lo.year * 12 + lo.month - 1, hi.year * 12 + hi.month - 1
        return tuple(f"{n // 12}-{n % 12 + 1:02d}" for n in range(n0, n1 + 1))
    if generator.cadence == "quarterly":
        q0, q1 = lo.year * 4 + (lo.month - 1) // 3, hi.year * 4 + (hi.month - 1) // 3
        return tuple(f"{q // 4}-Q{q % 4 + 1}" for q in range(q0, q1 + 1))
    if generator.cadence == "annual":
        return tuple(str(y) for y in range(lo.year, hi.year + 1))
    raise RegistryError(
        f"{generator.generator_id}: unknown cadence {generator.cadence!r}")


def recall_posterior(brain: Brain, generators: Iterable[Generator], scope: Scope,
                     hits: Mapping[str, frozenset[str]]) -> RecallPosterior:
    """r = P(relevant document retrieved | relevant), one Beta state on the wire, one
    ``bernoulli`` condition per EXPECTED slot (1.0 hit / 0.0 miss), ``mean`` + a
    ``centered_power`` variance read, state destroyed. No host math (Invariant 1). A
    claimed hit outside the census is not a sample of r under the declared denominator —
    it is evidence about the schedule — so it is named in ``extra_hits``, never folded."""
    expected = tuple(f"{g.generator_id}:{s}"
                     for g in generators if scope.key in g.scope_keys
                     for s in expected_slots(g, scope))
    census = frozenset(expected)
    claimed = tuple(f"{gid}:{s}" for gid, slots in sorted(hits.items())
                    for s in sorted(slots))
    hit = tuple(s for s in expected if s in frozenset(claimed))
    extra = tuple(s for s in claimed if s not in census)
    a0, b0 = _RECALL_PRIOR
    sid = brain.create_state({"type": "beta", "alpha": a0, "beta": b0})
    try:
        for s in expected:
            brain.condition(sid, kernel=_BERNOULLI,
                            observation=1.0 if s in frozenset(hit) else 0.0)
        m = brain.mean(sid)
        v = brain.expect(sid, function={"type": "centered_power", "n": 2, "mu": m})
    finally:
        brain.destroy_state(sid)
    return RecallPosterior(
        mean=m, variance=v, estimated=bool(expected), n_slots=len(expected),
        n_hits=len(hit), expected=expected, hit=hit,
        missed=tuple(s for s in expected if s not in frozenset(hit)),
        extra_hits=extra, prior=_RECALL_PRIOR)


def _entry_date(value: Any, gid: str, field: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise RegistryError(f"{gid}: {field} {value!r} is not an ISO date") from e


def _entry(raw: Mapping[str, Any], evidence_root: Path) -> Generator:
    gid = str(raw.get("generator_id") or "<missing generator_id>")
    cadence = str(raw.get("cadence") or "")
    if cadence not in CADENCES:
        raise RegistryError(f"{gid}: unknown cadence {cadence!r} "
                            f"(closed vocabulary: {sorted(CADENCES)})")
    evidence = tuple(str(c) for c in raw.get("evidence") or ())
    if not evidence:
        raise RegistryError(f"{gid}: no evidence citations — an uncited schedule "
                            "never enters the denominator")
    for cite in evidence:
        if not (evidence_root / cite).exists():
            raise RegistryError(f"{gid}: evidence citation {cite!r} does not resolve "
                                f"under {evidence_root}")
    active_to = raw.get("active_to")
    return Generator(
        generator_id=gid, kind=str(raw.get("kind") or ""), cadence=cadence,
        active_from=_entry_date(raw.get("active_from"), gid, "active_from"),
        active_to=None if active_to is None else _entry_date(active_to, gid, "active_to"),
        scope_keys=frozenset(str(k) for k in raw.get("scope_keys") or ()),
        evidence=evidence)


def load_registry(path: Path, *, evidence_root: Path) -> LoadedRegistry:
    """Parse + validate the registry, resolving every evidence citation against
    ``evidence_root`` (admissibility, §9). Returns the entries with the file's content
    hash; every validation failure is a loud :class:`RegistryError` naming the entry."""
    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    return LoadedRegistry(
        entries=tuple(_entry(e, evidence_root) for e in data.get("generators") or ()),
        content_hash=hashlib.sha256(raw).hexdigest())


# ------------------------------------------------------------------------------------
# Component 3 (CP-C, r20): dedup-as-inference — design §7. Pairwise same-entity
# hypothesis comparison under a UNIFORM structure prior (the Occam preference lives in
# the marginal likelihood, never a tilted prior); the §5 clustering rule in `lookup`
# stays the proposal generator and is untouched (§6.8 scoping — one rule, two declared
# roles, no second implementation of either).

_H_ONE, _H_TWO = 1.0, 2.0

UNREADABLE = "unreadable"

# The declared observation model, frozen in r20's pre-registration: per covariate, the
# bucket vocabulary and P(bucket | one latent transaction) / P(bucket | two). `period`
# is the designed discriminator; `amount` is deliberately humble under two (recurring
# instruments repeat amounts by design); `entity`/`kind` are weak-when-same (within one
# scope most candidate pairs share both under either hypothesis). Byte-distinctness is
# recorded on pairs but NOT conditioned: the proposal generator only emits
# byte-distinct pairs, so it is selection-fixed here.
_PAIR_TABLES: dict[str, tuple[tuple[str, ...],
                              tuple[tuple[float, ...], tuple[float, ...]]]] = {
    "period": (("same", "adjacent", "other"),
               ((0.98, 0.01, 0.01), (0.15, 0.45, 0.40))),
    "amount": (("equal", "close", "different"),
               ((0.90, 0.05, 0.05), (0.20, 0.10, 0.70))),
    "entity": (("same", "different"), ((0.97, 0.03), (0.70, 0.30))),
    "kind": (("same", "different"), ((0.99, 0.01), (0.80, 0.20))),
}


@dataclass(frozen=True)
class PairCovariates:
    """One candidate pair's observed covariates, each a bucket from its closed
    vocabulary in :data:`_PAIR_TABLES` or :data:`UNREADABLE`."""

    period: str
    amount: str
    entity: str
    kind: str


@dataclass(frozen=True)
class SameEntityPosterior:
    """P(one latent transaction | pair) vs P(two), with the covariates that were
    conditioned and the unreadable ones named (skipped: an honest P(unreadable | h) is
    hypothesis-independent, so the bucket carries zero evidence)."""

    p_one: float
    p_two: float
    conditioned: tuple[str, ...]
    skipped: tuple[str, ...]


def same_entity_posterior(brain: Brain, cov: PairCovariates) -> SameEntityPosterior:
    """One categorical state over {one, two} on the wire, uniform prior, one
    ``tabular_log_density`` condition per READABLE covariate (the frozen tables are the
    declared observation model crossing the wire as data), ``weights`` read, state
    destroyed. No host math."""
    readable: list[tuple[str, int, tuple[str, ...],
                         tuple[tuple[float, ...], tuple[float, ...]]]] = []
    skipped: list[str] = []
    for name, (buckets, tables) in _PAIR_TABLES.items():
        bucket = getattr(cov, name)
        if bucket == UNREADABLE:
            skipped.append(name)
            continue
        if bucket not in buckets:
            raise ValueError(f"{name}: unknown bucket {bucket!r} "
                             f"(closed vocabulary: {buckets})")
        readable.append((name, buckets.index(bucket), buckets, tables))
    sid = brain.create_state({"type": "categorical",
                              "space": {"type": "finite",
                                        "values": [_H_ONE, _H_TWO]},
                              "log_weights": [0.0, 0.0]})
    try:
        for _, bi, buckets, (d_one, d_two) in readable:
            brain.condition(sid, kernel={
                "type": "tabular_log_density",
                "source_vals": [_H_ONE, _H_TWO],
                "target_vals": [float(i) for i in range(len(buckets))],
                "densities": [[math.log(p) for p in d_one],
                              [math.log(p) for p in d_two]],
            }, observation=float(bi))
        w = brain.weights(sid)
    finally:
        brain.destroy_state(sid)
    return SameEntityPosterior(p_one=w[0], p_two=w[1],
                               conditioned=tuple(n for n, _, _, _ in readable),
                               skipped=tuple(skipped))
