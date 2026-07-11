"""session.py — the membrane session (Task 3 of the membrane-shadow feature).

Task 1 (:mod:`life_agent.membrane.client`) is the generic wire transport; Task 2
(:mod:`life_agent.membrane.world`) is the answer-domain world (features, menu,
utility). A `MembraneSession` is the one booted world: it drives the handshake, then
decide/verdict/outcome ticks over an injected client, holding the evidence-stream clock
(`_t`) and the outcome dedup set. It knows nothing about queues, respawn, or how many
sessions run at once — that is Task 4's supervisor. No threading here.

Ported from the credence-governor's proven `MembraneSession`
(`packages/governor_core/credence_governor_core/membrane.py:327-521`), with one
deliberate divergence named at :func:`MembraneSession.observe_outcome`: the governor's
table@1 form has no outcome channel at all (epoch-1 waste-only), while this world's
table@1 utility already prices y = "asserting now would be correct" for every
affordance, so a table@1 outcome is fed as an ordinary untagged evidence tick rather
than being inert.

The t-convention (carried over unchanged): `t` is the EVIDENCE-STREAM INDEX, not wall
time — one step per conditioned verdict/outcome. A decision tick sends the CURRENT
index and does not move it (membrane-wire.md §3: "THE AGENT DOES NOT MOVE"); an
evidence tick sends that same index and then advances it by one, so replay order and
live arrival order coincide (§3, register item 8.2). Decision replies carry
observability-only readouts (p1, entropy_bits, and on latent@1 residual_mean/
sensitivity); this session is a pure choice-relay over them — `ShadowChoice.readouts`
exists for telemetry only and is never read back into control flow (§6.4,
HOSTS_PLAN 8.12(b)).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .client import MembraneClient, MembraneError
from .world import (
    ID_TO_ACTION,
    MENU_IDS,
    THINK_POSTURE,
    UTILITY_FORMS,
    DecideSummary,
    handshake_decl,
    shadow_features,
)


@dataclass(frozen=True)
class ShadowChoice:
    """One decide() outcome: `action` is the world affordance name (or
    `world.THINK_POSTURE` when the internal act won), `raw_internal` names that case
    honestly, and `readouts` is the reply's observability-only scalars (p1,
    entropy_bits, ...) — telemetry, never branched on."""

    action: str
    raw_internal: bool
    readouts: dict[str, object]


# The evidence-mapping table (module-level, pure): the executor's chosen action + the
# owner's one-bit verdict valence -> y = "asserting now would have been correct".
# hedge/ask_clarify/gather/respond-under-other-valences, and any unrecognised pair, are
# a named exclusion — ambiguous is not evidence.
_VERDICT_Y: dict[tuple[str, str], int] = {
    ("report", "good"): 1, ("report", "bad"): 0,
    ("report_scoped", "good"): 1, ("report_scoped", "bad"): 0,
    ("abstain", "good"): 0, ("abstain", "bad"): 1,
}


def verdict_y(chosen_action: str, valence: str) -> int | None:
    """`None` for any (action, valence) pair outside the declared table."""
    return _VERDICT_Y.get((chosen_action, valence))


class MembraneSession:
    """One booted world, driving decide/verdict/outcome ticks over `client`."""

    def __init__(
        self,
        client: MembraneClient,
        *,
        u_bar: Mapping[str, float],
        utility_form: str = "table@1",
        log: Callable[[str], None] = print,
    ) -> None:
        if utility_form not in UTILITY_FORMS:
            raise ValueError(
                f"unknown membrane utility form {utility_form!r} "
                f"(declared: {list(UTILITY_FORMS)})"
            )
        self.client = client
        self._u_bar = u_bar
        self.utility_form = utility_form
        self._latent = utility_form == "latent@1"
        self._log = log
        self.engine: dict[str, object] = {}
        self.seen_outcomes: set[str] = set()
        # the evidence-stream index (module docstring's t-convention): a decision tick
        # reads it without moving it; an evidence tick reads it, then advances by one.
        self._t = 0

    def boot(
        self,
        *,
        verdict_replay: Iterable[tuple[DecideSummary, int]] = (),
        outcome_replay: Iterable[tuple[str, DecideSummary, int]] = (),
    ) -> None:
        """Handshake (raise on refusal), then verdict evidence in arrival order, then
        outcome evidence in arrival order (event-id deduped, the same path a live call
        uses) — the declared two-segment boot. No warm-counts file exists yet, so this
        is per-tick replay only."""
        reply = self.client.request(handshake_decl(self._u_bar, utility_form=self.utility_form))
        if "error" in reply:
            raise MembraneError(str(reply["error"]))
        if not reply.get("ok"):
            raise MembraneError(f"membrane handshake refused: {reply!r}")
        self.engine = reply
        for s, y in verdict_replay:
            self.observe_verdict(s, y)
        for event_id, s, y in outcome_replay:
            self.observe_outcome(event_id, s, y)

    def _tick(self, msg: dict[str, object]) -> dict[str, object]:
        reply = self.client.request({"tick": msg})
        if "error" in reply:
            raise MembraneError(str(reply["error"]))
        return reply

    def decide(self, s: DecideSummary) -> ShadowChoice:
        """Features + the declared menu, at the CURRENT `_t` — a decision tick never
        advances it. No per-tick `utility` key: the table is declared once at the
        handshake (module docstring)."""
        reply = self._tick({"features": shadow_features(s, float(self._t)), "menu": MENU_IDS})
        readouts = {k: v for k, v in reply.items() if k != "choice"}
        choice = reply.get("choice")
        if isinstance(choice, dict) and "fire" in choice:
            action = ID_TO_ACTION.get(int(choice["fire"]))
            if action is None:
                raise MembraneError(f"undeclared affordance in reply: {choice!r}")
            return ShadowChoice(action=action, raw_internal=False, readouts=readouts)
        if isinstance(choice, dict) and choice.get("internal") == "think":
            self._log(
                f"life-agent: membrane chose the internal think act; "
                f"posture={THINK_POSTURE}"
            )
            return ShadowChoice(action=THINK_POSTURE, raw_internal=True, readouts=readouts)
        raise MembraneError(f"malformed choice in reply: {reply!r}")

    def observe_verdict(self, s: DecideSummary, y: int) -> None:
        """One human verdict. table@1: a single untagged evidence tick. latent@1: the
        double-feed — an untagged tick (world-report role) then a `stream: "verdict"`
        tick (owner-response role), both at the SAME `t` (one event, two disjoint
        agents). Either way `_t` then advances by exactly one."""
        feats = shadow_features(s, float(self._t))
        ev = int(y)
        self._tick({"features": feats, "evidence": ev})
        if self._latent:
            self._tick({"stream": "verdict", "features": feats, "evidence": ev})
        self._t += 1

    def observe_outcome(self, event_id: str, s: DecideSummary, y: int) -> None:
        """One grounded outcome, deduped by `event_id` across boot replay and every
        live call (the session-held `seen_outcomes` set). latent@1: a single
        `stream: "outcome"` tick (the responder-free evidence). table@1: a single
        untagged evidence tick — NOT inert (module docstring's divergence from the
        credence-governor precedent). Either way `_t` advances by one."""
        if event_id in self.seen_outcomes:
            return
        self.seen_outcomes.add(event_id)
        feats = shadow_features(s, float(self._t))
        ev = int(y)
        if self._latent:
            self._tick({"stream": "outcome", "features": feats, "evidence": ev})
        else:
            self._tick({"features": feats, "evidence": ev})
        self._t += 1
