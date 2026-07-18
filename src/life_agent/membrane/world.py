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
            "utility": {"form": "said@1", "said": utility_said(u_bar)},
        },
    }
