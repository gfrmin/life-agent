"""categorical.py — the E1 categorical shadow world (stage 1 of the E1 ladder).

The binary world (:mod:`life_agent.membrane.world`) folds every question to one latent
y = "asserting now would be correct". This module declares the CATEGORICAL outcome the
E1 design adopts (docs/candidates/e1-categorical-outcome.md §4, against proplang's
landed W3 wire): ``obs_arity = K + 1`` where atoms 1..K are the tick's candidates **in
candidate order** and **atom 0 is the wire's own NULL emission** (NONE), acts are
value-indexed (``respond_j`` per candidate), and observations are code-valued evidence
ticks — an extraction hit supporting candidate j is ``evidence: j``, at machine speed,
which is what makes the verdict-starved binary p1 stop binding.

**Session-per-question** (OB-11: K is fixed per episode at tick 0 — the sanctioned
shape): every consult runs ONE FRESH ENGINE SESSION — handshake with this tick's K,
this question's own code-valued evidence ticks, one decide, shutdown. Cross-question
learning is deliberately absent here (the E1 two-layer split, §5.1: shared channel
parameters arrive later via a warm-counts file — a named B4 companion, not stage 1).

**Shadow-only**: nothing in this module touches the decision path. The shadow
supervisor (:mod:`life_agent.membrane.shadow`) mirrors live decide traffic through
:func:`run_categorical` when its ``categorical`` flag is on (default off = byte-inert)
and logs ``kind: "cat"`` rows; the ledger's question — does ``respond_j`` ever clear
its whole-menu bar under the wire's θ ceiling (0.9), with y the PREDICTIVE NEXT
OBSERVATION, not a latent truth — is answered offline from those rows (§4.3, the same
register-§7 discipline the binary world went through).

The reduction is PII-clean by construction: a :class:`CatSummary` carries only numbers
(K, codes, counts, flags) — never a candidate string. The bridge's abstract-observation
boundary (:mod:`life_agent.bridge.observations`) already did the string→index
normalisation; ``reports`` (the 0-based candidate index) becomes code ``reports + 1``.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from . import world as W
from .client import MembraneClient, MembraneError
from .world import _FLAG_FAMILIES, _OBS_BUCKETS, ACT_NAME, _obs_bucket

# The value-indexed act grid: abstain, gather, ask keep the binary world's grid values
# (1.0, 2.0, 3.0 — grid order normative, wait/abstain first, ties first-listed), then
# respond_j sits at RESPOND_BASE + j. So respond_1 = 4.0 (the binary world's old
# ``respond`` point) and the sentence recovers j as ``(get act) - RESPOND_BASE``.
_INFO_ACTS: tuple[tuple[str, float], ...] = (
    ("abstain", 1.0), ("gather", 2.0), ("ask", 3.0),
)
RESPOND_BASE = 3.0


@dataclass(frozen=True)
class CatSummary:
    """One decide tick reduced to the categorical world's inputs — numbers only.

    ``obs_codes`` is one code per MAPPABLE grounded observation, in arrival order:
    ``reports + 1`` (1-based; atom 0 = NONE is never emitted by extraction).
    ``n_obs_unmapped`` counts the named exclusions (a ``reports`` missing, boolean, or
    out of range) — ambiguous is not evidence, mirroring ``session._VERDICT_Y``.
    ``daemon_map_index`` is the 0-based argmax of the daemon's credences (None when it
    returned none) — carried so a ``kind: "cat"`` row can say, per tick, whether the
    engine's ``respond_j`` names the same candidate the daemon's posterior leads with
    (the M5 question, measured before anything depends on it)."""

    k: int
    obs_codes: tuple[int, ...]
    n_obs: int
    n_obs_unmapped: int
    daemon_map_index: int | None
    era_split: bool
    owner_scoped: bool
    grow_pass: bool


@dataclass(frozen=True)
class CatChoice:
    """One categorical decide: ``action`` is ``abstain``/``gather``/``ask``/
    ``respond_<j>``; ``j`` is the 1-based candidate index for a respond (else None);
    ``readouts`` the reply's observability-only scalars (p1, entropy_bits — NOTE: on the
    landed wire p1 is the predictive mass of ATOM 1 only; no per-code readout exists
    yet, the §5.4(d) issue); ``engine`` the handshake reply (models grows with K)."""

    action: str
    j: int | None
    readouts: dict[str, Any]
    engine: dict[str, Any]


def summary_from_payload_cat(
    payload: dict[str, Any], dec: dict[str, Any],
) -> CatSummary | None:
    """Reduce one live ``/decide`` call to the categorical inputs, or ``None`` when the
    tick has no candidates — a 0-candidate consult has no ``respond_j`` to measure and
    no lawful arity (the wire's floor is 2), so it is a NAMED SKIP, counted by the
    caller, never a degraded declaration."""
    candidates = payload.get("candidates") or []
    k = len(candidates)
    if k == 0:
        return None
    observations = payload.get("observations") or []
    codes: list[int] = []
    unmapped = 0
    for o in observations:
        r = o.get("reports") if isinstance(o, dict) else None
        if isinstance(r, int) and not isinstance(r, bool) and 0 <= r < k:
            codes.append(r + 1)
        else:
            unmapped += 1
    credences = dec.get("credences") or []
    daemon_map_index = (
        max(range(len(credences)), key=credences.__getitem__) if credences else None
    )
    return CatSummary(
        k=k,
        obs_codes=tuple(codes),
        n_obs=len(observations),
        n_obs_unmapped=unmapped,
        daemon_map_index=daemon_map_index,
        era_split=bool(payload.get("era_split", False)),
        owner_scoped=bool(payload.get("owner_scoped", False)),
        grow_pass=payload.get("grow") is not None,
    )


# --- the contextual feature vocabulary (E1 §4.4: features shrink to the genuinely -------
# --- contextual — the posterior the binary indicators summarized becomes engine-native) --


def cat_indicator_names() -> list[str]:
    """The categorical world's indicator names: n-obs buckets + the three flags —
    built from the SAME bucket tuples :func:`world.indicator_names` uses (one source,
    no drift). The candidate/credence/p-none families are deliberately absent: that
    posterior is what the engine now holds natively."""
    names = [f"n-obs={b}" for b in _OBS_BUCKETS]
    names += [f"{fam}=1" for fam in _FLAG_FAMILIES]
    return names


def cat_features(s: CatSummary, t: float) -> dict[str, float]:
    """The per-tick feature encoding: ``{"t": t}`` plus the applicable indicators
    (absent names read 0.0 on the wire — dormancy is free, same as
    :func:`world.shadow_features`)."""
    feats: dict[str, float] = {"t": t}
    feats[f"n-obs={_obs_bucket(s.n_obs)}"] = 1.0
    if s.era_split:
        feats["era-split=1"] = 1.0
    if s.owner_scoped:
        feats["owner-scoped=1"] = 1.0
    if s.grow_pass:
        feats["grow-pass=1"] = 1.0
    return feats


# --- the utility sentence (E1 §4.3, inside the shipped grammar) --------------------------


def utility_said_cat(u_bar: Mapping[str, float]) -> list[object]:
    """The categorical ``said@1`` sentence. Rows are BUILT from
    :func:`world.utility_by_action`'s pairs (one source — the binary and categorical
    worlds price the same owner utility):

    - ``abstain``: constant ``u_abstain`` (gauge — the doc defers a y=0-distinguishing
      abstain row as a u_bar question);
    - ``gather``/``ask``: the myopic perfect-information rows, categorically translated
      — having gathered you take the correct act, so y=0 (the channel would next report
      NONE) is worth the abstain side minus cost, any candidate code the correct side
      minus cost. The binary world's declared overvaluation carries over UNCHANGED
      (register item 5: never tuned away, measured instead);
    - ``respond_j`` (grid value RESPOND_BASE + j): ``u_correct`` iff the outcome equals
      the act's own candidate code — ``(= y (- (get act) RESPOND_BASE))`` — else
      ``u_wrong``. One arm covers every j; y here is the PREDICTIVE NEXT OBSERVATION
      (§4.3's honest semantics note).

    Uses only ``if = - c var get`` — well inside even the pre-W4 subset."""
    pairs = W.utility_by_action(u_bar)
    u_abstain = pairs["abstain"][0]
    g0, g1 = pairs["gather"]
    a0, a1 = pairs["ask"]
    u_wrong, u_correct = pairs["respond"]
    y: list[object] = ["var", 1]
    act: list[object] = ["get", ACT_NAME]

    def const(v: float) -> list[object]:
        return ["c", float(v)]

    def zero_split(u_none: float, u_some: float) -> list[object]:
        return ["if", ["=", y, const(0.0)], const(u_none), const(u_some)]

    respond_arm: list[object] = [
        "if", ["=", y, ["-", act, const(RESPOND_BASE)]],
        const(u_correct), const(u_wrong),
    ]
    return ["if", ["=", act, const(1.0)], const(u_abstain),
            ["if", ["=", act, const(2.0)], zero_split(g0, g1),
             ["if", ["=", act, const(3.0)], zero_split(a0, a1), respond_arm]]]


# --- the handshake declaration -----------------------------------------------------------


def act_grid_cat(k: int) -> list[float]:
    """``[abstain, gather, ask, respond_1..respond_K]`` grid values — order normative,
    wait (abstain) first, K-dependent length (per-episode data, K-at-tick-0)."""
    return [v for _, v in _INFO_ACTS] + [RESPOND_BASE + j for j in range(1, k + 1)]


def value_to_action_cat(v: float, k: int) -> tuple[str, int | None] | None:
    """Decode one act grid value: ``(action, j)`` with j the 1-based candidate index
    for a respond (None otherwise); ``None`` for anything off the declared grid — the
    caller treats that as a wire error, never a silent default."""
    for name, gv in _INFO_ACTS:
        if v == gv:
            return (name, None)
    j = v - RESPOND_BASE
    if j == int(j) and 1 <= int(j) <= k:
        return (f"respond_{int(j)}", int(j))
    return None


def handshake_decl_cat(u_bar: Mapping[str, float], k: int) -> dict[str, Any]:
    """The categorical handshake (membrane-wire.md §2 + the W3 ``obs_arity`` key):
    ``obs_arity = k + 1`` (atom 0 = NULL, atoms 1..k the candidates in candidate
    order), the reduced contextual namespace/guards, the value-indexed menu, and the
    §4.3 utility sentence. Raises :class:`ValueError` on ``k < 1`` (a 0-candidate tick
    is the caller's named skip, not a declaration)."""
    if k < 1:
        raise ValueError(f"categorical world needs at least one candidate (k={k})")
    names = cat_indicator_names()
    return {
        "membrane": 1,
        "world": {
            "namespace": ["t", *names, ACT_NAME],
            "guards": [{"name": n, "grid": [0.5]} for n in names],
            "menu": [{"name": ACT_NAME, "grid": act_grid_cat(k)}],
            "obs_arity": k + 1,
            "utility": {"form": "said@1", "said": utility_said_cat(u_bar)},
        },
    }


# --- the session runner: one fresh engine episode per tick -------------------------------


class _Client(Protocol):
    def request(self, obj: dict[str, object]) -> dict[str, object]: ...
    def shutdown(self) -> None: ...


def decide_categorical(
    client: _Client, u_bar: Mapping[str, float], s: CatSummary,
) -> CatChoice:
    """One categorical episode over an already-spawned client: handshake (raise on
    refusal), one evidence tick per code in arrival order (t advancing 0..n-1 — the
    binary session's t-convention verbatim), then ONE decide tick at t = n. The reply's
    act value decodes through :func:`value_to_action_cat`; anything undeclared raises
    :class:`MembraneError`. The caller owns the client's shutdown."""
    reply = client.request(handshake_decl_cat(u_bar, s.k))
    if "error" in reply:
        raise MembraneError(str(reply["error"]))
    if not reply.get("ok"):
        raise MembraneError(f"categorical handshake refused: {reply!r}")
    engine = dict(reply)
    t = 0
    for code in s.obs_codes:
        ev = client.request(
            {"tick": {"features": cat_features(s, float(t)), "evidence": int(code)}}
        )
        if "error" in ev:
            raise MembraneError(str(ev["error"]))
        t += 1
    dec = client.request(
        {"tick": {"features": cat_features(s, float(t)), "menu": [ACT_NAME]}}
    )
    if "error" in dec:
        raise MembraneError(str(dec["error"]))
    readouts = {key: v for key, v in dec.items() if key != "act"}
    assignment = dec.get("act")
    if isinstance(assignment, dict) and ACT_NAME in assignment:
        raw = assignment[ACT_NAME]
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            decoded = value_to_action_cat(float(raw), s.k)
            if decoded is not None:
                action, j = decoded
                return CatChoice(action=action, j=j, readouts=readouts, engine=engine)
        raise MembraneError(f"undeclared categorical act value: {assignment!r}")
    raise MembraneError(f"malformed categorical choice in reply: {dec!r}")


SpawnFn = Callable[..., Any]


def run_categorical(
    command: list[str],
    u_bar: Mapping[str, float],
    s: CatSummary,
    *,
    read_timeout_s: float = 300.0,
    spawn: SpawnFn | None = None,
) -> CatChoice:
    """Spawn one engine process, run :func:`decide_categorical`, and ALWAYS shut the
    client down (suppressed — a shadow's own cleanup must never raise past the real
    failure). This is the shadow supervisor's injectable entry (``cat_runner``)."""
    spawn_fn: SpawnFn = spawn if spawn is not None else MembraneClient.spawn
    client = spawn_fn(command, read_timeout_s=read_timeout_s)
    try:
        return decide_categorical(client, u_bar, s)
    finally:
        with contextlib.suppress(Exception):
            client.shutdown()
