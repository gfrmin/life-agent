"""world.py — the answer-domain world (the ``proplang-host`` handshake declaration).

Task 2 of the membrane-shadow feature (Task 1: :mod:`life_agent.membrane.client`, the
generic JSON-lines transport), re-targeted at the RE-DERIVED engine (proplang steps
3-10, 2026-07): the ``proplang-govhost`` executable and its ``table@1``/``latent@1``
utility forms are retired; conformance binds to ``membrane-wire.md`` sections 1-3 as
amended (step-8: UTILITY IS A SENTENCE), never to a GHC artifact. This module is pure
data/functions: the handshake world (namespace, guards, a names+grids menu, a
``said@1`` utility sentence) and the canonical per-tick feature encoding
(:func:`shadow_features`) both the live executor loop and the decision-log replay path
reduce to via one shared :class:`DecideSummary`. Nothing here spawns a process or reads
a file — the shadow supervisor is the caller that does.

The action vocabulary is ONE writable name, ``act``, whose grid VALUES encode the
executor's four affordances folded to the world's binary predicate y = "asserting now
would be correct" (bayesian-foundations §8): ``respond`` fires the
report/report_scoped/hedge assert-shaped actions, ``abstain`` the status-quo withhold,
``ask`` the daemon's interrupt-cost affordance, ``gather`` the recall-growth
affordance. Grid order is NORMATIVE on the wire: ``wait`` is every name at its grid's
FIRST point and argmaxEU ties resolve first-listed (membrane-wire.md §2, CL-3) — so
``abstain`` sits first (the safe structural wait; the v1 gather-wins-ties posture died
with the id/slots menu), then gather, ask, respond.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# --- the affordance vocabulary (ONE writable name; grid values are world-owned) ----------

ACT_NAME = "act"
# (affordance, grid value) in GRID ORDER — normative: first point = wait = the safe
# abstain (ties resolve first-listed on the wire, and wait keeps ties by construction).
AFFORDANCES: tuple[tuple[str, float], ...] = (
    ("abstain", 1.0), ("gather", 2.0), ("ask", 3.0), ("respond", 4.0),
)
ACT_GRID: list[float] = [v for _, v in AFFORDANCES]
VALUE_TO_ACTION: dict[float, str] = {v: name for name, v in AFFORDANCES}
_VALUE_FOR: dict[str, float] = {name: v for name, v in AFFORDANCES}

# The one utility form the re-derived wire accepts: the priced sentence (step-8 —
# ``assign@1`` died on its printed date; ``table@1``/``latent@1`` are the OLD roadmap's
# record, binding on nothing current). The internal "think" sentinel died at step 5 with
# the id/slots menu, so no think posture exists to map.
UTILITY_FORMS: tuple[str, ...] = ("said@1",)

# The executor's own effector vocabulary (core/executor.py's `_WITHHOLD`, core/gate.py's
# `ASSERT_ACTIONS`/`WITHHOLD_ACTIONS`, the daemon-scheduled "gather" steer, and the
# zero-observation "miss") folded onto this world's four affordances. ONE source: the
# offline report (`scripts/membrane/report.py`) and the M3 live mapping
# (:mod:`life_agent.membrane.coarse`) both read this dict — a hand-copy in either place
# is exactly the drift the report's own legend warns against. `hedge -> respond` is a
# declared modelling choice (assert-shaped but uncommitted — the report prints the
# caveat beside its copy of the legend).
REAL_TO_MEMBRANE: dict[str, str] = {
    "report": "respond", "report_scoped": "respond", "hedge": "respond",
    "abstain": "abstain", "miss": "abstain",
    "ask_clarify": "ask",
    "gather": "gather",
}


# --- DecideSummary: the one canonical context both the live and warm paths reduce to -----


@dataclass(frozen=True)
class DecideSummary:
    """Everything :func:`shadow_features` needs, independent of which path produced it:
    the live executor loop (:func:`summary_from_payload`, reading ``core/executor.py``'s
    ``/decide`` request/reply pair) or the decision log's replay shape
    (:func:`summary_from_decision_event`, reading a :class:`life_agent.core.decisions.DecisionEvent`
    as a plain dict)."""

    n_candidates: int
    leader_credence: float | None
    p_none: float | None
    n_obs: int
    era_split: bool
    owner_scoped: bool
    grow_pass: bool


def summary_from_payload(payload: dict[str, Any], dec: dict[str, Any]) -> DecideSummary:
    """Reduce one live ``/decide`` call: ``payload`` is the request body
    (``core/executor.py``'s ``_decide`` closure — ``candidates``, ``observations``,
    ``era_split``, ``owner_scoped``, and, only on a daemon-priced grow re-ask,
    ``sensors``/``grow``); ``dec`` is the daemon's reply (``credences``, ``p_none``).
    ``leader_credence`` is the MAP candidate's credence (``max(dec["credences"])`` — the
    daemon returns credences in candidate order, not weight-sorted, so the leader is the
    max, not index 0, matching ``executor.render_view``'s reordering)."""
    candidates = payload.get("candidates") or []
    observations = payload.get("observations") or []
    credences = dec.get("credences") or []
    return DecideSummary(
        n_candidates=len(candidates),
        leader_credence=max(credences) if credences else None,
        p_none=dec.get("p_none"),
        n_obs=len(observations),
        era_split=bool(payload.get("era_split", False)),
        owner_scoped=bool(payload.get("owner_scoped", False)),
        grow_pass=payload.get("grow") is not None,
    )


def summary_from_decision_event(event: dict[str, Any]) -> DecideSummary:
    """Reduce one logged decision (``life_agent.core.decisions.DecisionEvent``, read as a
    plain dict — e.g. off ``json.loads`` of a decisions.jsonl line) via its
    ``posterior_summary``. The three live-only flags (``era_split``, ``owner_scoped``,
    ``grow_pass``) are not recorded in either family's ``posterior_summary``
    (``core/lookup.py``/``core/narrative.py``) and always read ``False`` here — the warm
    path never claims a live-only signal it doesn't have. The lookup family's
    ``posterior_summary`` carries ``candidates``/``credences``/``p_none``/``n_obs``
    directly; the narrative family's does not (it carries ``n_proposed``/
    ``marginal_credence`` instead), so those degrade to "no candidates known" (0 / None /
    None / 0) rather than raising — a documented reduction, not a bug in either shape."""
    ps = event.get("posterior_summary") or {}
    candidates = ps.get("candidates") or []
    credences = ps.get("credences") or []
    return DecideSummary(
        n_candidates=len(candidates),
        leader_credence=max(credences) if credences else None,
        p_none=ps.get("p_none"),
        n_obs=int(ps.get("n_obs") or 0),
        era_split=False,
        owner_scoped=False,
        grow_pass=False,
    )


# --- the shadow-feature vocabulary (single source: both indicator_names() and ------------
# --- shadow_features() build off these bucket tuples, so they cannot drift) --------------

_CANDIDATES_BUCKETS: tuple[str, ...] = ("0", "1", "2plus")
_CREDENCE_BUCKETS: tuple[str, ...] = ("lt50", "50to70", "70to80", "80to90", "ge90")
_P_NONE_BUCKETS: tuple[str, ...] = ("lt20", "20to50", "ge50")
_OBS_BUCKETS: tuple[str, ...] = ("0", "1to2", "3plus")
_FLAG_FAMILIES: tuple[str, ...] = ("era-split", "owner-scoped", "grow-pass")


# [§3.3 · M-9] feature bucketing — the sensor vocabulary of g and of the world
# (model inputs, never control flow).
def _candidates_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n == 1:
        return "1"
    return "2plus"


def _credence_bucket(v: float) -> str:
    if v < 0.5:
        return "lt50"
    if v < 0.7:
        return "50to70"
    if v < 0.8:
        return "70to80"
    if v < 0.9:
        return "80to90"
    return "ge90"


def _p_none_bucket(v: float) -> str:
    if v < 0.2:
        return "lt20"
    if v < 0.5:
        return "20to50"
    return "ge50"


def _obs_bucket(n: int) -> str:
    if n == 0:
        return "0"
    if n <= 2:
        return "1to2"
    return "3plus"


def indicator_names() -> list[str]:
    """Every possible ``shadow_features`` indicator name, stable order (excludes ``t``,
    which is a scalar guard, not a one-hot family). This is the namespace/guards source
    :func:`handshake_decl` declares — one list, never restated."""
    names = [f"n-candidates={b}" for b in _CANDIDATES_BUCKETS]
    names += [f"leader-credence={b}" for b in _CREDENCE_BUCKETS]
    names += [f"p-none={b}" for b in _P_NONE_BUCKETS]
    names += [f"n-obs={b}" for b in _OBS_BUCKETS]
    names += [f"{fam}=1" for fam in _FLAG_FAMILIES]
    return names


def shadow_features(s: DecideSummary, t: float) -> dict[str, float]:
    """The canonical per-tick feature encoding: ``{"t": t}`` plus EVERY declared indicator,
    the applicable ones at 1.0 and the rest at 0.0.

    **r44 item 2 — the dormancy contract is dead.** The wire once defaulted absent names to
    0.0 (membrane-wire.md §4), so an inapplicable bucket could simply be omitted. The
    engine's door (`Eval.mkEnvIn`) now requires the declared namespace covered EXACTLY:
    missing names, undeclared names and duplicates are three named refusals. Measured free
    on the control (r42: a full-coverage tick answers byte-identically).

    The one name never emitted is the writable ``act``: r43 measured that padding it in is
    refused (`feature/assignment collision`, on both arms), so the tick covers
    ``namespace - menu names`` and the menu assignment supplies the rest."""
    feats: dict[str, float] = {n: 0.0 for n in indicator_names()}
    feats["t"] = t
    feats[f"n-candidates={_candidates_bucket(s.n_candidates)}"] = 1.0
    if s.leader_credence is not None:
        feats[f"leader-credence={_credence_bucket(s.leader_credence)}"] = 1.0
    if s.p_none is not None:
        feats[f"p-none={_p_none_bucket(s.p_none)}"] = 1.0
    feats[f"n-obs={_obs_bucket(s.n_obs)}"] = 1.0
    if s.era_split:
        feats["era-split=1"] = 1.0
    if s.owner_scoped:
        feats["owner-scoped=1"] = 1.0
    if s.grow_pass:
        feats["grow-pass=1"] = 1.0
    return feats


# --- the utility declaration ----------------------------------------------------------


def utility_by_action(u_bar: Mapping[str, float]) -> dict[str, tuple[float, float]]:
    """``{affordance: (u(y=0), u(y=1))}`` — THE one source of this world's utility
    numbers: the ``said@1`` sentence (:func:`utility_said`) is BUILT from these pairs and
    every host-side consumer (EU arithmetic, thresholds, the report's realized loss)
    reads them here, so the wire declaration and the host arithmetic cannot drift.

    ``u_wrong``/``lambda_int``/``kappa_att`` are the real
    :meth:`life_agent.core.utility.UtilityPosterior.u_bar` keys (verified against
    ``core/utility.py``'s ``REQUIRED_LATENTS`` + ``bridge/server.py``'s ``/utility``
    handler); ``u_correct``/``u_abstain`` are its gauge constants. The ``.get``
    fallbacks are this world's declared defaults when no posterior is available.

    **The information actions are priced as MYOPIC PERFECT INFORMATION** — ``gather``
    and ``ask`` are worth ``[u_abstain - cost, u_correct - cost]``: having gathered (or
    asked), you then take the CORRECT act. **FLAG — this OVERVALUES information,
    deliberately and namedly** (register item 5): the pure-cost alternative is constant
    in y and can never fire, and the gap between this bake-in and reality is exactly
    what the shadow's differential MEASURES — never to be tuned away. The re-derived
    engine prices actions as E[dU] over its own learned transition model (step-8);
    whether that dissolves the v1 gather-bar pathology (respond's bar 0.994 vs the
    engine p1 ceiling) is an EMPIRICAL question the v2 shadow answers. Owner-re-decidable."""
    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    g = abs(float(u_bar.get("kappa_att", 0.02)))
    return {
        "abstain": (u_abstain, u_abstain),
        "gather": (u_abstain - g, u_correct - g),
        "ask": (u_abstain - q, u_correct - q),
        "respond": (u_wrong, u_correct),
    }


def _lin(u0: float, u1: float) -> list[object]:
    """``u0 + var1 * (u1 - u0)`` in the priced grammar — the (y=0, y=1) pair as a
    sentence linear in the outcome residue ``["var", 1]``."""
    return ["+", ["c", u0], ["*", ["var", 1], ["c", u1 - u0]]]


def utility_said(u_bar: Mapping[str, float]) -> list[object]:
    """The ``said@1`` utility sentence (membrane-wire.md §2 as amended at step-8:
    UTILITY IS A SENTENCE, evaluated at the tick's features): nested
    ``if (= (get act) (c <grid value>))`` branches over :data:`AFFORDANCES`, each arm
    the affordance's (u0, u1) pair linear in the outcome residue. Actions are features
    on the re-derived wire, so the sentence reads the CHOSEN act through
    ``["get", "act"]`` — the assignment under evaluation binds it. Built from
    :func:`utility_by_action`, never re-spelled, so the declaration and the host
    arithmetic share one source. Uses only the wire's accepted subset
    (``parseSaid``: var, c, +, -, *, get, if, >, =) — verified against the built engine in the
    B0 spike (2026-07-19)."""
    pairs = utility_by_action(u_bar)
    names_in_grid_order = [name for name, _ in AFFORDANCES]
    # innermost arm = the LAST affordance (no trailing test needed: the engine only
    # evaluates the sentence at declared grid points).
    last = names_in_grid_order[-1]
    expr: list[object] = _lin(*pairs[last])
    for name in reversed(names_in_grid_order[:-1]):
        expr = ["if", ["=", ["get", ACT_NAME], ["c", _VALUE_FOR[name]]],
                _lin(*pairs[name]), expr]
    return expr


def eu_by_action(u_bar: Mapping[str, float], p1: float) -> dict[str, float]:
    """``{affordance: EU}`` at credence ``p1`` = P(y=1): ``EU = (1-p1)·u(y=0) + p1·u(y=1)``.
    The frozen engine does this arithmetic itself over the declared table; this is the same
    arithmetic host-side, so the report can name WHICH action the world's own utility
    prefers at a given p1 — and at which p1 it changes its mind — without asking the
    engine."""
    return {a: (1.0 - p1) * u0 + p1 * u1 for a, (u0, u1) in utility_by_action(u_bar).items()}


def argmax_action(u_bar: Mapping[str, float], p1: float) -> str:
    """The affordance this world's utility fires at ``p1`` — argmaxEU with ties resolved
    FIRST-LISTED in :data:`AFFORDANCES` (= grid) order, the wire's own rule (wait — the
    grid's first point, abstain — keeps ties), so this predicts the engine's chooser
    rather than merely scoring it."""
    eus = eu_by_action(u_bar, p1)
    return min(enumerate(AFFORDANCES), key=lambda it: (-eus[it[1][0]], it[0]))[1][0]


def respond_threshold(u_bar: Mapping[str, float]) -> float | None:
    """The p1 above which ``respond`` STRICTLY wins the whole menu — the honest reachability
    bar for the assert affordance, and the number the demand ledger tests against the
    engine's attainable p1.

    NOT merely respond-vs-abstain: the engine argmaxes over EVERY row, so respond must also
    outbid the information actions, which under the perfect-information bake-in
    (:func:`utility_by_action`) are worth more than abstain at any p1 above their own cost. Each
    row's EU is linear in p1 and respond's slope (``u_correct - u_wrong``) is the steepest
    (since ``u_wrong < u_abstain``), so respond overtakes each competitor at exactly one
    crossing and the binding bar is the LAST of them.

    ``None`` when respond can never overtake some row however high p1 goes (a competitor
    rising at least as fast — only under a degenerate u_bar): a reachability statement, not
    an error."""
    pairs = utility_by_action(u_bar)
    r0, r1 = pairs["respond"]
    thresholds: list[float] = []
    for action, (a0, a1) in pairs.items():
        if action == "respond":
            continue
        denom = (r1 - r0) - (a1 - a0)
        if denom <= 0:
            return None
        thresholds.append((a0 - r0) / denom)
    return max(thresholds) if thresholds else None


# --- r44 item 1: the emission codebook's grid (E3 — the grid IS the hypothesis space) --

# The measured operating rate of this world's predicate y = "asserting now would be
# correct": the y=1 frequency over the reaction stream joined to the decision log through
# `core.reactions.VERDICT_Y`, deduplicated on `decision_id` (latest reaction wins — the
# supersession rule r41 read). Read once, 2026-09-01: 60 of 70 declared-y reactions, zero
# unmapped. FROZEN-BLIND — a rung's PLACEMENT is the lever the engine repo's #19 record
# warns about (a rung near but not at the rate lets the posterior settle on the KL-nearest
# rung and false-clear a consumer threshold, with error that GROWS under data), so this is
# re-measured deliberately and never nudged to make a reading come out.
OPERATING_RATE: float = 0.857

# The recorded shadow's own predictive, p05 / median / p95 over 6 610 `readouts.p1` rows
# (`$LIFE_AGENT_KB/membrane/shadow.jsonl`, read 2026-09-01). These say where the belief
# actually lives, which is where resolution is worth paying for.
_SHADOW_P1_QUANTILES: tuple[float, ...] = (0.180, 0.339, 0.864)

# Endpoints, so the family can represent a near-certain world in either direction.
_GRID_ENDPOINTS: tuple[float, ...] = (0.05, 0.95)

# Two rungs closer than this are one rung; a CROSSING always survives the collision
# (r44 amendment 1 — rounding a rung off the crossing is exactly #19's hazard).
_GRID_COLLISION: float = 5e-4

# The lattice every rung is snapped to (r46 leg B). The engine's fold cost scales with the
# theta values' DYADIC DENOMINATOR BIT-LENGTH — an IEEE double is already dyadic, so an
# unsnapped rung costs its full 54-57 bits, and snapping to 2**-k costs k. Measured at depth
# 250, the live boot depth: 744 s of engine CPU unsnapped against 284 s at 2**-30, and the
# whole curve is monotone in k with 2**-53 landing back on the unsnapped cost (0.93x) — which
# is the control that identifies the mechanism. 20 is the FINEST lattice clearing r46 leg B's
# frozen >=2x bar on two depths at two reps each (0.46/0.45 at depth 60, 0.32/0.33 at 100);
# 2**-24 misses it at depth 60 (0.508/0.513). Displacement at 2**-20 is <= 4.8e-7, against
# the 7e-3 that r44's own W6 measured as producing a 3.2e-3 p1 gap with no false clear
# reachable. Read the report before changing this number.
_GRID_LATTICE_BITS: int = 20


def argmax_crossings(u_bar: Mapping[str, float]) -> list[float]:
    """The p1 values in (0, 1) at which :func:`argmax_action` changes its mind — this
    world's consumer thresholds, derived from the declared rows rather than assumed.

    Every row is linear in p1, so a pair crosses at most once; the pair's crossing counts
    only where the WHOLE argmax changes there (a crossing between two dominated rows is
    not a threshold). Returned at full precision."""
    rows = list(utility_by_action(u_bar).values())
    out: list[float] = []
    for i, (a0, a1) in enumerate(rows):
        for b0, b1 in rows[i + 1:]:
            denom = (a1 - a0) - (b1 - b0)
            if denom == 0.0:
                continue
            p = (b0 - a0) / denom
            eps = 1e-6
            if not 0.0 + eps < p < 1.0 - eps:
                continue
            if argmax_action(u_bar, p - eps) != argmax_action(u_bar, p + eps):
                out.append(p)
    return sorted(set(out))


def theta_grid(u_bar: Mapping[str, float]) -> list[float]:
    """The emission codebook's parameter grid — REQUIRED by the wire since the engine made
    the codebook world data (`Host.hs`: `codebooks.theta`, a bare non-empty array).

    The grid is the hypothesis space, and its SIZE is priced quadratically (r42 measured
    `models = n(17n - 16)` exactly for n = 1..16), so it is chosen by a declared rule and
    never fitted to a world count: the union of the measured :data:`OPERATING_RATE`, every
    :func:`argmax_crossings` threshold, the recorded shadow's p05/median/p95, and the
    endpoints. Crossings enter at full precision and win any collision within
    :data:`_GRID_COLLISION`.

    **r46 leg B amendment: every surviving rung is then snapped to
    :data:`_GRID_LATTICE_BITS`** (:func:`_snap_to_lattice`). Selection is untouched — the
    snap changes representation only — and it is refused rather than allowed to merge two
    rungs."""
    fixed = sorted({*_SHADOW_P1_QUANTILES, *_GRID_ENDPOINTS, OPERATING_RATE})
    grid = list(argmax_crossings(u_bar))
    for x in fixed:
        if 0.0 < x < 1.0 and all(abs(x - g) > _GRID_COLLISION for g in grid):
            grid.append(x)
    return _snap_to_lattice(sorted(grid))


def _snap_to_lattice(grid: list[float]) -> list[float]:
    """Every rung on the coarsest lattice that preserves the grid (r46 leg B).

    Selection has already happened: this only changes each surviving rung's REPRESENTATION,
    never which rungs survive, so `r44`'s two frozen clauses — a rung at the measured
    operating rate, a crossing surviving the collision — still decide membership exactly as
    before.

    **The fallback ladder is not defensive dressing.** `_GRID_COLLISION` bounds the distance
    between a *fixed* value and a *crossing*; it says nothing about two crossings, which can
    be arbitrarily close. A snap that merged two rungs would silently shrink the hypothesis
    space (`models = n(17n-16)`), turning a representation change into a different lever —
    which is exactly what sixteenths do here (n 8 -> 6). So the snap is REFUSED whenever it
    would merge, and the next finer lattice is tried, up to the double's own 53 bits where
    snapping is a no-op. Monotone and total: the result is never coarser than declared and
    never changes `n`."""
    for bits in range(_GRID_LATTICE_BITS, 54):
        snapped = [round(x * (2 ** bits)) / (2 ** bits) for x in grid]
        if len(set(snapped)) == len(grid) and snapped == sorted(snapped):
            return snapped
    return grid


# --- r44 item 4: the clock row (the seam that routes selection to the substitution route)

# `Host.hs` reaches the substituting chooser (`pickWire`/`policyPick`, which evaluates each
# candidate's utility row under ITS OWN assignment) only when a clock is declared; without
# one it uses `chooseEU`, whose two comparands share the challenger's environment, so
# per-action LEVELS never enter and the option space's head always fires. That is the
# engine's own registered `OB-24`, and r43 measured it end to end on this world.
CLOCK_NAME = "think"
CLOCK_BATCH = 1


def clock_price(u_bar: Mapping[str, float]) -> float:
    """`think` is NOT an affordance this world models — it exists only because the clock row
    is the seam to the substituting chooser. Its price is therefore DERIVED to make it
    unreachable under this world's own utility rather than raised until it stops firing:
    `pickWire` ranks the think row at `thinkValue - price`, and `thinkValue` is bounded above
    by the best achievable row value, so a price one unit beyond the utility's full span puts
    the think row strictly below the worst row EU at every belief."""
    values = [v for pair in utility_by_action(u_bar).values() for v in pair]
    return (max(values) - min(values)) + 1.0


def handshake_decl(u_bar: Mapping[str, float], *, utility_form: str = "said@1") -> dict[str, Any]:
    """The full handshake line (membrane-wire.md §2 as amended through step-10):
    ``namespace`` = ``["t"] + indicator_names() + [ACT_NAME]`` (RIDER 2: every writable
    name is a namespace member, and membership is immutable), one singleton
    ``[0.5]``-grid guard per indicator, the menu as the ONE writable name with its grid
    (names+grids — the step-5 shape; grid order normative, wait first), and the utility
    as a ``said@1`` sentence. The tick features (``shadow_features``) and the writable
    name are DISJOINT by construction (ruling D-b2) — indicators are ``family=value``
    strings and ``t``, never ``act``. No ``echo`` block: it died with the step-5 wire.
    Raises :class:`ValueError` on an undeclared ``utility_form``."""
    if utility_form not in UTILITY_FORMS:
        raise ValueError(
            f"unknown utility form {utility_form!r} (declared: {list(UTILITY_FORMS)})"
        )
    names = indicator_names()
    return {
        "membrane": 1,
        "world": {
            "namespace": ["t", *names, ACT_NAME],
            "guards": [{"name": n, "grid": [0.5]} for n in names],
            "menu": [{"name": ACT_NAME, "grid": list(ACT_GRID)}],
            "codebooks": {"theta": theta_grid(u_bar)},
            "clock": [{"name": CLOCK_NAME, "price": clock_price(u_bar),
                       "batch": CLOCK_BATCH}],
            "utility": {"form": "said@1", "said": utility_said(u_bar)},
        },
    }
