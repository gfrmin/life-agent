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
import json
import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
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


# ------------------------------------------------------------------------------------
# Component 2 (CP-D phase 2, r21): the missing-mass composition — design §6, the r21
# prereg's frozen v0. Deterministic host composition of recorded observations (no
# invented likelihood); the only wire consult is component 3 on the proposal pairs.
# Currency mixtures are refused as per-currency subtotals (§4.3); the roll-up branch
# and the same-doc issuer fold are the §4.2 preference (the issuer's own fold is one
# authority-of-source observation; recognition mechanics were left to implementation
# by the prereg and are the deterministic rules below, disclosed in r21's RESULTS).

_COARSE_BASES = frozenset({"quarterly", "annual", "other"})
_BASIS_RANK = {"point_in_time": 0, "monthly": 0, "quarterly": 1, "annual": 2,
               "other": 3}


@dataclass(frozen=True)
class Addend:
    """One §18.14 line-item, carried with its document key for citation/dedup.
    ``flagged`` marks a majority-unlabelled carrier (priced, never dropped)."""

    doc_key: str
    kind: str
    basis: str
    as_of: str | None
    amount: float
    currency: str
    amount_raw: str
    label_raw: str | None
    entity: str | None
    flagged: bool


@dataclass(frozen=True)
class TotalPosterior:
    """One currency's composed total: the central-80% interval + point summary, with
    the full accounting readout 1 renders (named exclusions, dedup resolutions,
    imputed slots) and readout 2's unmodelled-recall flag."""

    currency: str
    point: float
    lo: float
    hi: float
    k: int
    s_obs: float
    imputed_slots: tuple[str, ...]
    basis_note: str
    excluded_kind: tuple[tuple[str, str], ...]
    excluded_basis: tuple[tuple[str, str], ...]
    dedup_resolutions: tuple[str, ...]
    unmodelled_recall: bool


def _month_index(iso: str) -> int:
    d = date.fromisoformat(iso)
    return d.year * 12 + d.month - 1


def pair_covariates(a: Addend, b: Addend) -> PairCovariates:
    """Deterministic addend-pair → covariate-bucket mapping for component 3."""
    if a.as_of is None or b.as_of is None:
        period = UNREADABLE
    else:
        months = abs(_month_index(a.as_of) - _month_index(b.as_of))
        period = "same" if months == 0 else ("adjacent" if months <= 3 else "other")
    if round(a.amount, 2) == round(b.amount, 2):
        amount = "equal"
    elif abs(a.amount - b.amount) <= 0.01 * max(abs(a.amount), abs(b.amount)):
        amount = "close"
    else:
        amount = "different"
    if a.entity is None or b.entity is None:
        entity = UNREADABLE
    else:
        entity = "same" if a.entity.casefold() == b.entity.casefold() else "different"
    kind = "same" if a.kind == b.kind else "different"
    return PairCovariates(period=period, amount=amount, entity=entity, kind=kind)


def _collapse_within_doc(group: list[Addend]) -> list[Addend]:
    # One value is one attestation within a document (the §5 within-doc analogue).
    seen: set[tuple[str, str, float, str | None]] = set()
    out = []
    for a in group:
        key = (a.doc_key, a.kind, round(a.amount, 2), a.as_of)
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def _issuer_fold(group: list[Addend]) -> tuple[list[Addend], str]:
    # Same-doc stated-total: within one (doc, as_of) cluster of ≥3 rows, a row equal
    # to the sum of the others is the issuer's own fold — keep it, demote the parts.
    by_cluster: dict[tuple[str, str | None], list[Addend]] = {}
    for a in group:
        by_cluster.setdefault((a.doc_key, a.as_of), []).append(a)
    out: list[Addend] = []
    note = ""
    for cluster in by_cluster.values():
        if len(cluster) >= 3:
            top = max(cluster, key=lambda a: a.amount)
            rest = [a for a in cluster if a is not top]
            if abs(top.amount - sum(a.amount for a in rest)) <= 0.01:
                out.append(top)
                note = (f"issuer-stated total row is the fold of {len(rest)} "
                        "constituent rows (same document)")
                continue
        out.extend(cluster)
    return out, note


def _dedup_pairs(brain: Brain, group: list[Addend]
                 ) -> tuple[list[Addend], tuple[str, ...]]:
    # Cross-doc equal-value pairs are the §5 proposal generator's uncollapsed
    # candidates; component 3 prices each — p_one > 0.5 means one latent
    # transaction, so the later attestation is dropped and the resolution named.
    ordered = sorted(group, key=lambda a: (a.as_of or "9999-99-99", a.doc_key))
    dropped: set[int] = set()
    resolutions: list[str] = []
    for i in range(len(ordered)):
        if i in dropped:
            continue
        for j in range(i + 1, len(ordered)):
            if j in dropped:
                continue
            a, b = ordered[i], ordered[j]
            if a.doc_key == b.doc_key or round(a.amount, 2) != round(b.amount, 2):
                continue
            post = same_entity_posterior(brain, pair_covariates(a, b))
            if post.p_one > 0.5:
                dropped.add(j)
                resolutions.append(
                    f"{a.doc_key}~{b.doc_key}: one latent transaction "
                    f"(p_one={post.p_one:.3f}) — counted once")
    return [a for i, a in enumerate(ordered) if i not in dropped], tuple(resolutions)


def _compose_one(brain: Brain, group: list[Addend], scope: Scope,
                 recall: RecallPosterior, currency: str,
                 excluded_kind: tuple[tuple[str, str], ...]) -> TotalPosterior:
    notes: list[str] = []
    group = _collapse_within_doc(group)
    group, fold_note = _issuer_fold(group)
    if fold_note:
        notes.append(fold_note)
    group, resolutions = _dedup_pairs(brain, group)

    candidates = [a for a in group
                  if a.basis in _COARSE_BASES
                  and a.as_of is not None
                  and date.fromisoformat(a.as_of) == scope.end]
    if len(candidates) == 1:
        v = candidates[0].amount
        notes.append("issuer roll-up at the scope end is the single observation; "
                     f"{len(group) - 1} finer rows are slot evidence")
        return TotalPosterior(
            currency=currency, point=v, lo=v, hi=v, k=1, s_obs=v,
            imputed_slots=(), basis_note="; ".join(notes),
            excluded_kind=excluded_kind, excluded_basis=(),
            dedup_resolutions=resolutions,
            unmodelled_recall=not recall.estimated)
    if len(candidates) >= 2:
        vals = ", ".join(f"{a.amount:.2f}" for a in candidates)
        notes.append(f"competing roll-up observations at the scope end ({vals}) — "
                     "summing the series instead")

    remaining = [a for a in group if a not in candidates]
    if remaining:
        finest = min(_BASIS_RANK.get(a.basis, 3) for a in remaining)
        summed = [a for a in remaining if _BASIS_RANK.get(a.basis, 3) == finest]
        excluded_basis = tuple((a.doc_key, a.basis) for a in remaining
                               if _BASIS_RANK.get(a.basis, 3) != finest)
    else:
        summed, excluded_basis = [], ()
    s_obs = sum(a.amount for a in summed)
    k = len(summed)

    lo = hi = point = s_obs
    imputed: tuple[str, ...] = ()
    if recall.estimated and recall.missed and summed:
        m = len(recall.missed)
        vals_sorted = sorted(a.amount for a in summed)
        mean_v = statistics.mean(vals_sorted)
        if len(vals_sorted) >= 2:
            q = statistics.quantiles(vals_sorted, n=10)
            q10, q90 = q[0], q[-1]
        else:
            q10 = q90 = vals_sorted[0]
        point, lo, hi = s_obs + m * mean_v, s_obs + m * q10, s_obs + m * q90
        imputed = recall.missed
        notes.append(f"{m} missed slot(s) imputed from the observed series "
                     "(exchangeability within the generator, a disclosed assumption)")
    return TotalPosterior(
        currency=currency, point=point, lo=lo, hi=hi, k=k, s_obs=s_obs,
        imputed_slots=imputed, basis_note="; ".join(notes),
        excluded_kind=excluded_kind, excluded_basis=excluded_basis,
        dedup_resolutions=resolutions,
        unmodelled_recall=not recall.estimated)


def compose_total(brain: Brain, addends: Iterable[Addend], scope: Scope, *,
                  target_kind: str, recall: RecallPosterior
                  ) -> list[TotalPosterior]:
    """The §4 refusals + component-3 dedup + the §6 v0 composition, one
    :class:`TotalPosterior` per currency (largest addend count first)."""
    pool = list(addends)
    on_kind = [a for a in pool if a.kind == target_kind]
    excluded_kind = tuple((a.doc_key, a.kind) for a in pool
                          if a.kind != target_kind)
    out = [
        _compose_one(brain, [a for a in on_kind if a.currency == c], scope,
                     recall, c, excluded_kind)
        for c in sorted({a.currency for a in on_kind})
    ]
    return sorted(out, key=lambda t: (-t.k, t.currency))


# ------------------------------------------------------------------------------------
# The read-side amounts projection — mirrors temporal.project_dates: §18.10 currency
# (max (produced_at, cache_key) per hit), §18.11 demand log, NEVER derives. Underived
# hits are named with their copy-pasteable remedy (the D2 coverage contract); the
# demand-led warm runs those remedies before a priced run, capped (r21 prereg).

AMOUNTS_PRODUCERS: tuple[str, ...] = tuple(
    f"extract_amounts_{p}" for p in ("docling", "pandoc", "tesseract", "email"))


@dataclass(frozen=True)
class AmountsHit:
    """One hit's amounts projection: ``amounts`` (items), ``empty`` (determinate
    no-amounts), ``unreadable`` (the named indeterminate), or ``underived`` (no
    projection yet — ``remedy`` is the exact pkm-derive command)."""

    artifact_cache_key: str
    state: str  # amounts | empty | unreadable | underived
    addends: tuple[Addend, ...]
    extractor: str
    remedy: str | None = None


def project_amounts(conn: Any, root: Path, hit_keys: list[str], *,
                    caller: str = "ask.aggregate") -> list[AmountsHit]:
    """Project the CURRENT extract_amounts artifact onto each hit, read-only."""
    import time as _time

    from pkm.cache import content_file
    from pkm.telemetry import DemandLogEntry, log_demand

    if not hit_keys:
        return []
    placeholders = ", ".join("?" for _ in hit_keys)
    extractor_of = dict(conn.execute(
        f"SELECT cache_key, producer_name FROM artifacts "
        f"WHERE cache_key IN ({placeholders})", hit_keys).fetchall())
    prod_ph = ", ".join("?" for _ in AMOUNTS_PRODUCERS)
    rows = conn.execute(
        f"SELECT l.input_cache_key, a.cache_key, a.produced_at "
        f"FROM artifact_lineage l "
        f"JOIN artifacts a ON a.cache_key = l.artifact_cache_key "
        f"WHERE l.input_cache_key IN ({placeholders}) "
        f"AND a.producer_name IN ({prod_ph}) AND a.status = 'success'",
        [*hit_keys, *AMOUNTS_PRODUCERS]).fetchall()
    current: dict[str, tuple[Any, str]] = {}
    for input_key, proj_key, produced_at in rows:
        candidate = (produced_at, proj_key)
        if input_key not in current or candidate > current[input_key]:
            current[input_key] = candidate

    def _demand(key: str, target: str, *, hit: bool, t0: float) -> None:
        log_demand(root, DemandLogEntry(
            timestamp=datetime.now(UTC).isoformat(), caller=caller,
            transform_name="extract_amounts", cache_key=target,
            input_cache_key=key, hit=hit, cost_usd=0.0,
            latency_ms=int((_time.monotonic() - t0) * 1000)))

    out: list[AmountsHit] = []
    for key in hit_keys:
        t0 = _time.monotonic()
        extractor = str(extractor_of.get(key, ""))
        projection = current.get(key)
        if projection is None:
            out.append(AmountsHit(
                key, "underived", (), extractor,
                remedy=f"pkm derive extract_amounts_{extractor} --input {key}"))
            _demand(key, "", hit=False, t0=t0)
            continue
        proj_key = projection[1]
        parsed = json.loads(content_file(root, proj_key).read_text(encoding="utf-8"))
        _demand(key, proj_key, hit=True, t0=t0)
        if parsed.get("unreadable"):
            out.append(AmountsHit(key, "unreadable", (), extractor))
            continue
        items = parsed.get("items") or []
        if not items:
            out.append(AmountsHit(key, "empty", (), extractor))
            continue
        flagged = bool(parsed.get("majority_unlabelled"))
        default = parsed.get("currency_default")
        addends = tuple(
            Addend(doc_key=key, kind=str(it.get("kind") or "other"),
                   basis=str(it.get("basis") or "other"),
                   as_of=it.get("as_of"),
                   amount=float(it["amount"]),
                   currency=str(it.get("currency") or default or ""),
                   amount_raw=str(it.get("amount_raw") or ""),
                   label_raw=it.get("label_raw"), entity=it.get("entity"),
                   flagged=flagged)
            for it in items)
        out.append(AmountsHit(key, "amounts", addends, extractor))
    return out


# ------------------------------------------------------------------------------------
# The second-stage router + the family body (CP-D phase 2, r21; design §8/§2). ONE
# body — terminals' declined path and the bridge's aggregate handler both call it.
# ROUTE_PROMPT (lookup admission) stays byte-identical; this classifier has its own
# prompt, closed schema and cache key, runs only on the DECLINED path, and defaults
# to narrative — it admits to aggregate only on a confident sum-shaped verdict that
# names a target kind (the asymmetric misroute posture: a sum-shaped answer to a
# non-sum question is the harmful direction).

ROUTE2_PROMPT = """\
Decide whether this question asks for a numeric TOTAL or COUNT computed over several
documents (an aggregate), or anything else (narrative).

Aggregate means: "how much in total", "what was my total X in period P", "how many Y".
A single value to look up, a list, a summary, a comparison, or a compound question is
NOT an aggregate.

If aggregate, also name:
- target_kind: the amount kind being totalled — one of income_gross, income_net, tax,
  deduction, balance, deposit, fee, invoice_total, payment, other. For narrative,
  answer "none".
- period_start / period_end: the question's period as YYYY-MM-DD dates, null if the
  question states none.

If in ANY doubt, answer narrative.

Question: {question}
"""

ROUTE2_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["family", "target_kind", "period_start", "period_end"],
    "properties": {
        "family": {"type": "string", "enum": ["aggregate", "narrative"]},
        # A nullable enum (enum + type union) is rejected by the structured-output
        # API (found live, r21 disclosure) — "none" is the sentinel, parsed as null.
        "target_kind": {"type": "string",
                        "enum": ["income_gross", "income_net", "tax", "deduction",
                                 "balance", "deposit", "fee", "invoice_total",
                                 "payment", "other", "none"]},
        "period_start": {"type": ["string", "null"]},
        "period_end": {"type": ["string", "null"]},
    },
}


@dataclass(frozen=True)
class AggregateRoute:
    """A confident sum-shaped verdict: the target kind + the stated period."""

    target_kind: str
    period_start: str | None
    period_end: str | None


def route_aggregate(root: Path, question: str, *,
                    client: Any | None = None,
                    meter: list[float] | None = None) -> AggregateRoute | None:
    """The cached second-stage verdict (design §8): AggregateRoute when this is a
    numeric-total aggregate, else None (the narrative path answers). Conservative by
    construction: ``aggregate`` without a target kind is not a confident sum shape
    and reads as narrative; a verdict outside the schema raises, never recorded."""
    from life_agent.core import derivations as D
    from life_agent.core import instrument as INSTR
    from life_agent.core.lookup import LOOKUP_MODEL

    if client is None:
        client = INSTR.instrument_client(LOOKUP_MODEL)
    key = D.aggregate_route_key(question, model=LOOKUP_MODEL,
                                prompt_template=ROUTE2_PROMPT,
                                engine_version=str(client.engine_version),
                                output_schema=ROUTE2_SCHEMA)
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        parsed = json.loads(cached.decode("utf-8"))
    else:
        response = client.complete(ROUTE2_PROMPT.replace("{question}", question),
                                   ROUTE2_SCHEMA)
        if meter is not None:
            meter.append(float(getattr(response, "cost_usd", 0.0) or 0.0))
        parsed = json.loads(response.raw_text)
        if parsed.get("family") not in ("aggregate", "narrative"):
            raise ValueError(f"aggregate_route emitted junk: {parsed!r}")
        D.record(root, key,
                 json.dumps({"format_version": 1, **parsed}, sort_keys=True,
                            ensure_ascii=False).encode("utf-8"),
                 lineage=[])
    kind = parsed.get("target_kind")
    if parsed.get("family") != "aggregate" or not kind or kind == "none":
        return None
    return AggregateRoute(target_kind=str(parsed["target_kind"]),
                          period_start=parsed.get("period_start"),
                          period_end=parsed.get("period_end"))


@dataclass(frozen=True)
class AggregateResult:
    """The family's answer: the per-currency totals + the full coverage accounting
    the render turns into design §2's four blocks. ``asserted`` carries the point
    and interval bounds as formatted strings (the grader's channel)."""

    question: str
    action: str  # report | abstain
    abstain_reason: str | None
    totals: tuple[TotalPosterior, ...]
    asserted: tuple[str, ...]
    recall: RecallPosterior
    n_docs: int
    unreadable_docs: tuple[str, ...]
    underived: tuple[tuple[str, str], ...]  # (doc key, remedy)
    excluded_period: tuple[tuple[str, str], ...]  # (doc key, as_of or "undated")
    registry_content_hash: str
    registry_note: str
    answer_cache_key: str


def _slot_name(cadence: str, iso: str) -> str:
    d = date.fromisoformat(iso)
    if cadence == "monthly":
        return f"{d.year}-{d.month:02d}"
    if cadence == "quarterly":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    return str(d.year)


def aggregate_answer(root: Path, conn: Any, question: str,
                     hits: list[dict[str, Any]], route: AggregateRoute, *,
                     brain: Brain, registry: LoadedRegistry | None,
                     registry_note: str = "",
                     decisions_path: Path | None = None,
                     run_id: str = "ask",
                     today: date | None = None) -> AggregateResult:
    """The ONE aggregate body (design §2): project §18.14 amounts over the hits
    (read-only — the demand-led warm runs the remedies, never this function), apply
    the period filter and the §4 refusals, price proposal pairs through component 3,
    compose the total (component 2), derive report/abstain, render, and record
    through the one recorder. The registry content hash rides the decision record
    (mechanics — recorded, never priced)."""
    from life_agent.core import decisions as DEC
    from life_agent.core import derivations as D
    from life_agent.core import lookup as LK
    from life_agent.core import outcomes as O
    from life_agent.core import recorder as REC
    from life_agent.core.config import DECISIONS_LOG

    scope_start = (date.fromisoformat(route.period_start) if route.period_start
                   else date(1970, 1, 1))
    scope_end = (date.fromisoformat(route.period_end) if route.period_end
                 else (today or date.today()))
    scope = Scope(key=route.target_kind, start=scope_start, end=scope_end)

    hit_keys = list(dict.fromkeys(h["artifact_cache_key"] for h in hits))
    projections = project_amounts(conn, root, hit_keys)
    unreadable = tuple(p.artifact_cache_key for p in projections
                       if p.state == "unreadable")
    underived = tuple((p.artifact_cache_key, p.remedy or "")
                      for p in projections if p.state == "underived")

    pool: list[Addend] = [a for p in projections for a in p.addends]
    in_period: list[Addend] = []
    excluded_period: list[tuple[str, str]] = []
    for a in pool:
        if a.kind != route.target_kind:
            in_period.append(a)  # off-kind: named by compose_total, not here
        elif a.as_of is None:
            excluded_period.append((a.doc_key, "undated"))
        elif scope_start <= date.fromisoformat(a.as_of) <= scope_end:
            in_period.append(a)
        else:
            excluded_period.append((a.doc_key, a.as_of))

    generators = tuple(registry.entries) if registry is not None else ()
    covering = [g for g in generators if scope.key in g.scope_keys]
    slot_hits = {
        g.generator_id: frozenset(
            _slot_name(g.cadence, a.as_of) for a in in_period
            if a.kind == route.target_kind and a.as_of is not None)
        for g in covering}
    recall = recall_posterior(brain, covering, scope, slot_hits)

    totals = tuple(compose_total(brain, in_period, scope,
                                 target_kind=route.target_kind, recall=recall))
    reported = tuple(t for t in totals if t.k > 0)
    if reported:
        action, reason = "report", None
        asserted = tuple(
            s for t in reported
            for s in (f"{t.point:,.2f}", f"{t.point:.2f}",
                      f"{t.lo:,.2f}", f"{t.hi:,.2f}"))
    else:
        action = "abstain"
        reason = DEC.withhold_reason(effector="miss", candidates=[])
        asserted = ()

    registry_hash = registry.content_hash if registry is not None else ""
    summary = {
        "totals": [{"currency": t.currency, "point": t.point, "lo": t.lo,
                    "hi": t.hi, "k": t.k, "s_obs": t.s_obs,
                    "imputed_slots": list(t.imputed_slots)} for t in totals],
        "n_docs": len(hit_keys), "unreadable": list(unreadable),
        "underived": [k for k, _ in underived],
        "recall": {"mean": recall.mean, "estimated": recall.estimated,
                   "n_slots": recall.n_slots, "n_hits": recall.n_hits,
                   "missed": list(recall.missed)},
        "abstain_reason": reason,
        "registry_content_hash": registry_hash,
        "decision_rule": "derived-v0 (report iff >=1 includable on-kind addend)",
    }
    content = json.dumps({"format_version": 1, "question": question,
                          "action": action, **summary},
                         sort_keys=True, ensure_ascii=False).encode("utf-8")
    akey = D.aggregate_answer_key(
        question, _sha_hex(content), registry_hash,
        {"target_kind": route.target_kind,
         "period": [scope_start.isoformat(), scope_end.isoformat()]})
    REC.record_local(
        root, akey, content, lineage=[],
        decisions_path=(decisions_path if decisions_path is not None
                        else DECISIONS_LOG),
        event=DEC.DecisionEvent(
            tx_time=O.now_iso(), run_id=run_id,
            question_id=DEC.question_id(question),
            family="aggregate", action_set=DEC.AGGREGATE_ACTION_ORDER,
            posterior_summary=summary,
            utility_fold_version="",  # v0: derived rule, not an EU fold (recorded)
            chosen_action=action, predicted_eu=0.0,
            regime="terminals-only", policy=LK.U_BAR_POLICY, defaulted=(),
            decision_id=akey.cache_key))
    return AggregateResult(
        question=question, action=action, abstain_reason=reason,
        totals=totals, asserted=asserted, recall=recall,
        n_docs=len(hit_keys), unreadable_docs=unreadable, underived=underived,
        excluded_period=tuple(excluded_period),
        registry_content_hash=registry_hash, registry_note=registry_note,
        answer_cache_key=akey.cache_key)


def _sha_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_aggregate(result: AggregateResult) -> str:
    """Design §2's four blocks — rendered always, report and abstain alike."""
    lines: list[str] = []
    if result.action == "report":
        for t in result.totals:
            if t.k == 0:
                continue
            lines.append(
                f"Total ({t.currency}): {t.point:,.2f} "
                f"[central 80%: {t.lo:,.2f} - {t.hi:,.2f}] "
                f"over {t.k} addend(s)")
    else:
        lines.append(f"Total: withheld ({result.abstain_reason}) — no readable "
                     "on-kind amounts in scope")
    cov = [f"Coverage: {result.n_docs} retrieved document(s)"]
    for t in result.totals:
        if t.excluded_kind:
            cov.append("excluded by kind: " + ", ".join(
                f"{k[:12]}… ({kind})" for k, kind in t.excluded_kind))
        if t.excluded_basis:
            cov.append("excluded by basis: " + ", ".join(
                f"{k[:12]}… ({b})" for k, b in t.excluded_basis))
        cov.extend(t.dedup_resolutions)
    if result.excluded_period:
        cov.append("excluded by period: " + ", ".join(
            f"{k[:12]}… ({p})" for k, p in result.excluded_period))
    if result.unreadable_docs:
        cov.append("unreadable (named): " + ", ".join(
            k[:12] + "…" for k in result.unreadable_docs))
    if result.underived:
        cov.append("underived (named): " + "; ".join(
            f"{k[:12]}… — {r}" for k, r in result.underived))
    lines.append("; ".join(cov))
    r = result.recall
    if r.estimated:
        missed = (" — missed: " + ", ".join(r.missed)) if r.missed else ""
        lines.append(f"Recall: generator-estimated r = {r.mean:.2f} "
                     f"({r.n_hits}/{r.n_slots} expected slots{missed})")
    else:
        lines.append("Recall: no known generator covers this scope — retrieval "
                     "recall is unmodelled here")
    basis = [t.basis_note for t in result.totals if t.basis_note]
    lines.append("Basis: " + ("; ".join(basis) if basis else "series sum"))
    if result.registry_note:
        lines.append(result.registry_note)
    return "\n".join(lines)
