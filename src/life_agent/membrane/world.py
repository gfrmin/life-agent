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
from typing import Any

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
    (always worse than every real row, including the worst-case respond-wrong, by
    construction — never tuned, never hand-checked per call). ``u_wrong``/``lambda_int``/
    ``kappa_att`` are the real :meth:`life_agent.core.utility.UtilityPosterior.u_bar`
    keys (verified against ``core/utility.py``'s ``REQUIRED_LATENTS`` +
    ``bridge/server.py``'s ``/utility`` handler); the ``.get`` fallbacks are this world's
    declared defaults when no posterior is available."""
    u_wrong = float(u_bar.get("u_wrong", -9.0))
    q = abs(float(u_bar.get("lambda_int", 0.1)))
    g = abs(float(u_bar.get("kappa_att", 0.02)))
    sentinel = -(1.0 + abs(u_wrong) + q + g + 1.0)
    rows: list[dict[str, object]] = [
        {"fire": _ID_FOR["gather"], "u": [-g, -g]},
        {"fire": _ID_FOR["ask"], "u": [-q, -q]},
        {"fire": _ID_FOR["abstain"], "u": [0.0, 0.0]},
        {"fire": _ID_FOR["respond"], "u": [u_wrong, 1.0]},
        {"internal": "think", "u": [sentinel, sentinel]},
    ]
    return rows


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
