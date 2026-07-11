"""world.py — the answer-domain world (proplang-govhost's handshake declaration).

Task 2 of the membrane-shadow feature (Task 1: :mod:`life_agent.membrane.client`, the
generic JSON-lines transport). This module is pure data/functions: it declares the
world the host sends the decider on the handshake line (namespace, guards, menu,
utility — ``membrane-wire.md`` §2), and the canonical per-tick feature encoding
(:func:`shadow_features`) both the live executor loop and the decision-log replay path
reduce to via one shared :class:`DecideSummary`. Nothing here spawns a process or reads
a file — the shadow supervisor (a later task) is the caller that does.

The four affordances are the executor's own action vocabulary, folded to the world's
binary predicate y = "asserting now would be correct" (bayesian-foundations §8):
``respond`` fires the report/report_scoped/hedge assert-shaped actions, ``abstain``
the status-quo withhold, ``ask`` the daemon's own interrupt-cost affordance, ``gather``
the recall-growth affordance (core/gather_outcomes.py's grow menu). ``AFFORDANCES``
listing order is NORMATIVE on the wire (membrane-wire.md §2: argmaxEU ties resolve
first-listed) — gather, then ask, then abstain, then respond: at exact indifference the
world prefers to gather, then ask, before it abstains or commits, mirroring the wire
spec's own ``ask, block, proceed`` ordering (R1, HOSTS_PLAN 8.1).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

# --- the affordance vocabulary (menu ids are world-owned, stable, positive) --------------

AFFORDANCES: tuple[tuple[str, int], ...] = (
    ("gather", 4), ("ask", 3), ("abstain", 2), ("respond", 1),
)
MENU_IDS: list[int] = [mid for _, mid in AFFORDANCES]
ID_TO_ACTION: dict[int, str] = {mid: name for name, mid in AFFORDANCES}
_ID_FOR: dict[str, int] = {name: mid for name, mid in AFFORDANCES}

UTILITY_FORMS: tuple[str, ...] = ("table@1", "latent@1")

# Documented posture: the internal "think" act winning a tick maps to the world's abstain
# affordance (a non-answer, never a silent default) — the adapter's one fixed reading of
# membrane-wire.md §3's "the driver reports it honestly if it wins".
THINK_POSTURE = "abstain"


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
    """The canonical per-tick feature encoding: ``{"t": t}`` plus one-hot indicators,
    bucketed per :func:`indicator_names`. Absent names read 0.0 on the wire (dormancy is
    free — membrane-wire.md §4), so a bucket that doesn't apply (an unknown
    ``leader_credence``/``p_none``, or a False flag) is simply omitted rather than
    emitted at 0.0."""
    feats: dict[str, float] = {"t": t}
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


def utility_rows(u_bar: Mapping[str, float]) -> list[dict[str, object]]:
    """The ``table@1`` step table over y = "asserting now would be correct"
    (membrane-wire.md §2/§5): one ``{"fire": <menu id>, "u": [u(y=0), u(y=1)]}`` row per
    affordance, plus the one required ``internal: "think"`` row at a dominated sentinel
    (re-derived from the real rows themselves — strictly below every entry of every row, so
    it is worse at EVERY p1 by construction; never tuned, never hand-checked per call).
    ``u_wrong``/``lambda_int``/``kappa_att`` are the real
    :meth:`life_agent.core.utility.UtilityPosterior.u_bar` keys (verified against
    ``core/utility.py``'s ``REQUIRED_LATENTS`` + ``bridge/server.py``'s ``/utility``
    handler); ``u_correct``/``u_abstain`` are its gauge constants (``utility.GAUGE`` — 1.0
    and 0.0, fixed by the gauge, read here rather than re-spelled so the table and every
    threshold derived from it (:func:`respond_threshold`) speak one utility). The ``.get``
    fallbacks are this world's declared defaults when no posterior is available.

    **The information actions are priced as MYOPIC PERFECT INFORMATION** — ``gather`` and
    ``ask`` are worth ``[u_abstain - cost, u_correct - cost]``, i.e. having gathered (or
    asked), you then take the CORRECT act: withhold when y=0, respond when y=1. This is the
    credence-governor's own declared convention for its ``ask`` row (its HOSTS_PLAN register
    item 8.4: "u(ask,·) = -q bakes 'a resolved ask makes the correct act free'"),
    transposed to this world's gauge, where the correct act is worth ``u_correct`` rather
    than 0.

    **FLAG — this OVERVALUES information, deliberately and namedly.** A real gather round
    does not guarantee the correct act: it grows recall, and the executor may still be
    wrong or still withhold. The alternative — the pure-cost rows this table shipped with
    (``gather → [-g, -g]``, ``ask → [-q, -q]``) — is not a conservative choice but a
    degenerate one: both rows are then CONSTANT in y, so ``EU(gather) = -g < 0 =
    EU(abstain)`` at every p1 and abstain strictly dominates the entire information menu,
    which can therefore never fire. A menu whose whole point is effort allocation cannot
    price effort at pure cost. So the bake-in stays, it is declared here and in
    ``docs/membrane-shadow.md`` (register item 5), and the gap between it and reality is
    exactly what the shadow's differential MEASURES — it is never to be tuned away to make
    an action distribution look better. Owner-re-decidable."""
    u_correct = float(u_bar.get("u_correct", 1.0))
    u_abstain = float(u_bar.get("u_abstain", 0.0))
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    g = abs(float(u_bar.get("kappa_att", 0.02)))
    real: list[dict[str, object]] = [
        {"fire": _ID_FOR["gather"], "u": [u_abstain - g, u_correct - g]},
        {"fire": _ID_FOR["ask"], "u": [u_abstain - q, u_correct - q]},
        {"fire": _ID_FOR["abstain"], "u": [u_abstain, u_abstain]},
        {"fire": _ID_FOR["respond"], "u": [u_wrong, u_correct]},
    ]
    sentinel = min(float(v) for r in real for v in cast("list[float]", r["u"])) - 1.0
    return [*real, {"internal": "think", "u": [sentinel, sentinel]}]


def utility_by_action(u_bar: Mapping[str, float]) -> dict[str, tuple[float, float]]:
    """``{affordance: (u(y=0), u(y=1))}`` off :func:`utility_rows` — the one place anything
    downstream (EU arithmetic, thresholds, the report's realized loss) reads the table's
    numbers, so no consumer ever re-spells them."""
    pairs: dict[str, tuple[float, float]] = {}
    for row in utility_rows(u_bar):
        fire = row.get("fire")
        if isinstance(fire, int):  # the internal "think" sentinel is not an affordance
            u0, u1 = (float(x) for x in cast("list[float]", row["u"]))
            pairs[ID_TO_ACTION[fire]] = (u0, u1)
    return pairs


def eu_by_action(u_bar: Mapping[str, float], p1: float) -> dict[str, float]:
    """``{affordance: EU}`` at credence ``p1`` = P(y=1): ``EU = (1-p1)·u(y=0) + p1·u(y=1)``.
    The frozen engine does this arithmetic itself over the declared table; this is the same
    arithmetic host-side, so the report can name WHICH action the world's own utility
    prefers at a given p1 — and at which p1 it changes its mind — without asking the
    engine."""
    return {a: (1.0 - p1) * u0 + p1 * u1 for a, (u0, u1) in utility_by_action(u_bar).items()}


def argmax_action(u_bar: Mapping[str, float], p1: float) -> str:
    """The affordance this world's utility fires at ``p1`` — argmaxEU with ties resolved
    FIRST-LISTED in :data:`AFFORDANCES` order (the wire's own rule), so this predicts the
    frozen chooser rather than merely scoring it."""
    eus = eu_by_action(u_bar, p1)
    return min(enumerate(AFFORDANCES), key=lambda it: (-eus[it[1][0]], it[0]))[1][0]


def respond_threshold(u_bar: Mapping[str, float]) -> float | None:
    """The p1 above which ``respond`` STRICTLY wins the whole menu — the honest reachability
    bar for the assert affordance, and the number the demand ledger tests against the
    engine's attainable p1.

    NOT merely respond-vs-abstain: the engine argmaxes over EVERY row, so respond must also
    outbid the information actions, which under the perfect-information bake-in
    (:func:`utility_rows`) are worth more than abstain at any p1 above their own cost. Each
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


def latent_utility_decl(u_bar: Mapping[str, float]) -> dict[str, object]:
    """The ``latent@1`` utility block (membrane-wire.md §6.1): a priced sentence over
    (action, outcome) rather than a constants table. ``theta_ask`` is the sole residual
    (v0 scope — the ask affordance's interrupt-cost exchange rate), FIRST in
    ``residuals`` so it name-keys the charge ``theta_ask``. Its grid must be strictly
    positive and strictly ascending with ``grid[0] == q`` (the floor) for ANY real
    ``lambda_int`` posterior mean — not only the wire spec's golden-example floor (0.05),
    which is safely below its fixed 0.1/0.2/0.4 points but the example utility model's
    real prior (mu=1.0) is not. So the three points above the floor are declared as
    FIXED OFFSETS (+0.1, +0.2, +0.4) rather than absolute grid points: this keeps
    strict ascent for any non-negative floor by construction, at the cost of the grid no
    longer being byte-identical to the golden example once ``q`` exceeds 0.05. The floor
    is additionally clamped to a tiny positive epsilon so a exactly-zero posterior mean
    (measure-zero, but not excluded by the model's stated support) never violates the
    wire's "grids are POSITIVE by rule" (§6.1, the charity restriction)."""
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    floor = max(q, 1e-6)
    grid = [floor, floor + 0.1, floor + 0.2, floor + 0.4]
    return {
        "form": "latent@1",
        "said": ["var", 1],
        "residuals": [{"name": "theta_ask", "grid": grid}],
        "tau": {"points": [0.5, 1, 2], "weights": [0.5, 0.3, 0.2]},
        "price": "tick-price",
        "gauge": {"zero": "status-quo", "scale": "answer-utility"},
    }


def handshake_decl(u_bar: Mapping[str, float], *, utility_form: str = "table@1") -> dict[str, Any]:
    """The full handshake line (membrane-wire.md §2): namespace = ``["t"] +
    indicator_names()``, one singleton ``[0.5]``-grid guard per indicator, the menu in
    :data:`AFFORDANCES` order (NORMATIVE — argmaxEU ties resolve first-listed), the
    utility block dispatched by ``utility_form``, and an all-false ``echo`` (epoch-1
    restriction, §2). Raises :class:`ValueError` on an undeclared ``utility_form``."""
    if utility_form not in UTILITY_FORMS:
        raise ValueError(
            f"unknown utility form {utility_form!r} (declared: {list(UTILITY_FORMS)})"
        )
    names = indicator_names()
    menu = [{"id": mid, "name": name, "slots": []} for name, mid in AFFORDANCES]
    utility: dict[str, object]
    if utility_form == "table@1":
        utility = {"form": "table@1", "rows": utility_rows(u_bar)}
    else:
        utility = latent_utility_decl(u_bar)
    return {
        "membrane": 1,
        "world": {
            "namespace": ["t", *names],
            "guards": [{"name": n, "grid": [0.5]} for n in names],
            "menu": menu,
            "utility": utility,
            "echo": {"last_action": False, "tick": False, "ticks_spent_thinking": False},
        },
    }
