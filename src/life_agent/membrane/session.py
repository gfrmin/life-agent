"""session.py — the membrane session (Task 3 of the membrane-shadow feature).

Task 1 (:mod:`life_agent.membrane.client`) is the generic wire transport; Task 2
(:mod:`life_agent.membrane.world`) is the answer-domain world (features, menu,
utility). A `MembraneSession` is the one booted world: it drives the handshake, then
decide/verdict/outcome ticks over an injected client, holding the evidence-stream clock
(`_t`) and the outcome dedup set. It knows nothing about queues, respawn, or how many
sessions run at once — that is Task 4's supervisor. No threading here.

Ported from the credence-governor's proven `MembraneSession`
(`packages/governor_core/credence_governor_core/membrane.py:327-521`), re-targeted at
the re-derived wire (one `said@1` form; the table@1/latent@1 split and its stream-tagged
double-feed are historical): every verdict/outcome is one untagged evidence tick,
because the declared utility sentence already prices y = "asserting now would be
correct" for every affordance.

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
    ACT_NAME,
    UTILITY_FORMS,
    VALUE_TO_ACTION,
    DecideSummary,
    handshake_decl,
    shadow_features,
)


@dataclass(frozen=True)
class ShadowChoice:
    """One decide() outcome: `action` is the world affordance name decoded from the
    reply's full assignment (`{"act": {"act": <grid value>}}` — the internal think act
    died with the step-5 wire, so `raw_internal` is always False and is kept only for
    the shadow record's stable shape), and `readouts` is the reply's observability-only
    scalars (p1, entropy_bits, ...) — telemetry, never branched on."""

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
        utility_form: str = "said@1",
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
        self._log = log
        self.engine: dict[str, object] = {}
        self.seen_outcomes: set[str] = set()
        # the evidence-stream index (module docstring's t-convention): a decision tick
        # reads it without moving it; an evidence tick reads it, then advances by one.
        self._t = 0

    @property
    def t(self) -> int:
        """The evidence-stream index, read-only (Task 4's shadow supervisor records the
        `t` a tick was sent at; nothing outside this class ever advances it)."""
        return self._t

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
        """Features + the menu (the one writable name), at the CURRENT `_t` — a decision
        tick never advances it. No per-tick `utility` key: the sentence is declared once
        at the handshake (module docstring). The reply's choice is the FULL ASSIGNMENT
        `{"act": {"act": <grid value>}}` (the step-5 encoding — fire/slots and the
        internal think act died with the old wire); an undeclared value is a wire
        error, never a silent default."""
        reply = self._tick({"features": shadow_features(s, float(self._t)),
                            "menu": [ACT_NAME]})
        readouts = {k: v for k, v in reply.items() if k != "act"}
        assignment = reply.get("act")
        if isinstance(assignment, dict) and ACT_NAME in assignment:
            raw = assignment[ACT_NAME]
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                action = VALUE_TO_ACTION.get(float(raw))
                if action is not None:
                    return ShadowChoice(action=action, raw_internal=False,
                                        readouts=readouts)
            raise MembraneError(f"undeclared act value in reply: {assignment!r}")
        raise MembraneError(f"malformed choice in reply: {reply!r}")

    def observe_verdict(self, s: DecideSummary, y: int) -> None:
        """One human verdict: a single untagged evidence tick (the `stream`-tagged
        double-feed was latent@1 machinery — historical with the old wire). `_t` then
        advances by exactly one."""
        self._tick({"features": shadow_features(s, float(self._t)), "evidence": int(y)})
        self._t += 1

    def observe_outcome(self, event_id: str, s: DecideSummary, y: int) -> None:
        """One grounded outcome, deduped by `event_id` across boot replay and every
        live call (the session-held `seen_outcomes` set): a single untagged evidence
        tick — the ``said@1`` utility already prices y = "asserting now would be
        correct" for every affordance, so an outcome is ordinary evidence. `_t`
        advances by one."""
        if event_id in self.seen_outcomes:
            return
        self.seen_outcomes.add(event_id)
        self._tick({"features": shadow_features(s, float(self._t)), "evidence": int(y)})
        self._t += 1
