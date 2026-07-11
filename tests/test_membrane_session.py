"""Hermetic tests for the membrane session (life_agent.membrane.session).

No wire, no subprocess: `_FakeClient` is a scripted transport — an object with a
`.request(obj) -> dict` method that records every request and pops canned replies off a
list, matching `MembraneClient`'s surface without importing it (Task 3's session only
ever calls `client.request(dict) -> dict`). These pin: boot's two-segment replay order
+ not-ok/error handshake raising; decide leaving `_t` unmoved and relaying readouts
verbatim (the choice-relay discipline, membrane-wire.md §6.4); the verdict double-feed
(latent@1: two ticks same `t`; table@1: one tick), `_t` advancing by exactly one either
way; outcome dedup by event_id across boot and live, and table@1's outcome tick being
an ordinary untagged evidence tick (NOT inert — the one deliberate divergence from the
credence-governor precedent, whose table@1 has no outcome channel at all); the internal
`think` choice mapping to `world.THINK_POSTURE` with `raw_internal=True`; any
`{"error": ...}` reply raising; and the `verdict_y` evidence-mapping table.
"""
from __future__ import annotations

import pytest

from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneError
from life_agent.membrane.session import MembraneSession, ShadowChoice, verdict_y

HANDSHAKE_OK: dict[str, object] = {"ok": True, "proto": 1, "models": 100, "namespace_bits": 5.0}


class _FakeClient:
    """Scripted membrane transport: records every request, pops canned replies in
    order. No `MembraneClient`, no subprocess — `MembraneSession` only ever calls
    `.request(dict) -> dict`."""

    def __init__(self, replies: list[dict[str, object]]) -> None:
        self.replies = list(replies)
        self.sent: list[dict[str, object]] = []

    def request(self, obj: dict[str, object]) -> dict[str, object]:
        self.sent.append(obj)
        return self.replies.pop(0)


def _summary(**kw: object) -> W.DecideSummary:
    defaults: dict[str, object] = dict(
        n_candidates=1, leader_credence=0.9, p_none=0.05, n_obs=1,
        era_split=False, owner_scoped=False, grow_pass=False,
    )
    defaults.update(kw)
    return W.DecideSummary(**defaults)  # type: ignore[arg-type]


def _make(
    replies: list[dict[str, object]], **kw: object
) -> tuple[_FakeClient, MembraneSession]:
    client = _FakeClient(replies)
    sess = MembraneSession(client, u_bar={}, log=lambda _m: None, **kw)  # type: ignore[arg-type]
    return client, sess


def _tick_body(sent: dict[str, object]) -> dict[str, object]:
    body = sent["tick"]
    assert isinstance(body, dict)
    return body


# --- boot(): handshake + two-segment replay ------------------------------------------


def test_boot_sends_the_declared_handshake_line() -> None:
    client, sess = _make([HANDSHAKE_OK])
    sess.boot()
    assert client.sent == [W.handshake_decl({}, utility_form="table@1")]


def test_boot_keeps_the_reply_dict_as_engine() -> None:
    _client, sess = _make([HANDSHAKE_OK])
    sess.boot()
    assert sess.engine == HANDSHAKE_OK


def test_boot_raises_on_not_ok_handshake() -> None:
    _client, sess = _make([{"ok": False}])
    with pytest.raises(MembraneError):
        sess.boot()


def test_boot_raises_on_error_handshake_reply() -> None:
    _client, sess = _make([{"error": "bad-world"}])
    with pytest.raises(MembraneError):
        sess.boot()


def test_boot_replays_verdicts_then_outcomes_in_arrival_order() -> None:
    s1, s2, s3 = _summary(n_obs=1), _summary(n_obs=2), _summary(n_obs=3)
    client, sess = _make([
        HANDSHAKE_OK,
        {"observed": 1},  # verdict s1
        {"observed": 0},  # verdict s2 (arrival order: s1 before s2)
        {"observed": 1},  # outcome s3
    ])
    sess.boot(
        verdict_replay=[(s1, 1), (s2, 0)],
        outcome_replay=[("ev-3", s3, 1)],
    )
    assert len(client.sent) == 4
    assert _tick_body(client.sent[1])["features"]["n-obs=1to2"] == 1.0  # type: ignore[index]
    assert _tick_body(client.sent[1])["evidence"] == 1
    assert _tick_body(client.sent[2])["evidence"] == 0
    assert _tick_body(client.sent[3])["evidence"] == 1
    assert "ev-3" in sess.seen_outcomes


def test_engine_and_seen_outcomes_default_before_boot() -> None:
    _client, sess = _make([])
    assert sess.engine == {}
    assert sess.seen_outcomes == set()


# --- decide(): does not advance _t, pure choice-relay ---------------------------------


def test_decide_sends_declared_menu_features_and_no_per_tick_utility_key() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"choice": {"fire": 1, "slots": {}}}])
    sess.boot()
    sess.decide(s)
    tick = _tick_body(client.sent[1])
    assert tick["menu"] == W.MENU_IDS
    assert "utility" not in tick
    assert tick["features"] == W.shadow_features(s, 0.0)


def test_decide_leaves_t_unmoved_across_calls() -> None:
    s = _summary()
    client, sess = _make([
        HANDSHAKE_OK,
        {"choice": {"fire": 1, "slots": {}}},
        {"choice": {"fire": 1, "slots": {}}},
    ])
    sess.boot()
    sess.decide(s)
    sess.decide(s)
    assert _tick_body(client.sent[1])["features"]["t"] == 0.0  # type: ignore[index]
    assert _tick_body(client.sent[2])["features"]["t"] == 0.0  # type: ignore[index]


def test_decide_returns_readouts_verbatim_minus_choice() -> None:
    s = _summary()
    _client, sess = _make([
        HANDSHAKE_OK,
        {"choice": {"fire": 1, "slots": {}}, "p1": 0.8, "entropy_bits": 1.2},
    ])
    sess.boot()
    choice = sess.decide(s)
    assert choice == ShadowChoice(
        action="respond", raw_internal=False, readouts={"p1": 0.8, "entropy_bits": 1.2}
    )


def test_decide_is_a_pure_choice_relay_readouts_never_affect_the_action() -> None:
    # membrane-wire.md §6.4: two replies differing ONLY in observability scalars must
    # yield the identical action — the adapter branches on "choice", nothing else.
    s = _summary()
    _client, sess = _make([
        HANDSHAKE_OK,
        {"choice": {"fire": 2, "slots": {}}, "p1": 0.9, "entropy_bits": 1.0},
        {"choice": {"fire": 2, "slots": {}}, "p1": 0.1, "entropy_bits": 9.0},
    ])
    sess.boot()
    c1 = sess.decide(s)
    c2 = sess.decide(s)
    assert c1.action == c2.action == "abstain"
    assert c1.readouts != c2.readouts


def test_decide_maps_every_fire_id_to_its_declared_action() -> None:
    s = _summary()
    for action, mid in W.AFFORDANCES:
        _client, sess = _make([HANDSHAKE_OK, {"choice": {"fire": mid, "slots": {}}}])
        sess.boot()
        choice = sess.decide(s)
        assert choice.action == action
        assert choice.raw_internal is False


def test_decide_unknown_fire_id_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"choice": {"fire": 99, "slots": {}}}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


def test_decide_internal_think_maps_to_think_posture_with_raw_internal_flag() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"choice": {"internal": "think"}}])
    sess.boot()
    choice = sess.decide(s)
    assert choice.action == W.THINK_POSTURE == "abstain"
    assert choice.raw_internal is True


def test_decide_error_reply_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"error": "impossible-evidence"}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


def test_decide_malformed_reply_without_choice_or_error_raises() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"ok": True}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


# --- observe_verdict(): the double-feed rule -------------------------------------------


def test_observe_verdict_single_untagged_tick_on_table_and_advances_t_once() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 0}, {"choice": {"fire": 1, "slots": {}}}])
    sess.boot()
    sess.observe_verdict(s, 0)
    assert len(client.sent) == 2  # handshake + one evidence tick
    tick = _tick_body(client.sent[1])
    assert "stream" not in tick
    assert tick["evidence"] == 0
    sess.decide(s)
    assert _tick_body(client.sent[2])["features"]["t"] == 1.0  # type: ignore[index]


def test_observe_verdict_double_feeds_on_latent_same_t_then_advances_once() -> None:
    s = _summary()
    client, sess = _make(
        [HANDSHAKE_OK, {"observed": 1}, {"observed": 1}, {"choice": {"fire": 1, "slots": {}}}],
        utility_form="latent@1",
    )
    sess.boot()
    sess.observe_verdict(s, 1)
    assert len(client.sent) == 3  # handshake + two evidence ticks
    untagged, verdict_tagged = _tick_body(client.sent[1]), _tick_body(client.sent[2])
    assert "stream" not in untagged
    assert verdict_tagged["stream"] == "verdict"
    assert untagged["evidence"] == verdict_tagged["evidence"] == 1
    assert untagged["features"]["t"] == verdict_tagged["features"]["t"] == 0.0  # type: ignore[index]
    sess.decide(s)
    assert _tick_body(client.sent[3])["features"]["t"] == 1.0  # type: ignore[index]


def test_observe_verdict_error_reply_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"error": "impossible-evidence"}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.observe_verdict(s, 1)


# --- observe_outcome(): stream tag by form, dedup by event_id -------------------------


def test_observe_outcome_table_sends_a_single_untagged_evidence_tick() -> None:
    # the deliberate divergence from the credence-governor precedent: table@1 outcome
    # evidence is an ordinary untagged tick, never inert.
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 1}, {"choice": {"fire": 1, "slots": {}}}])
    sess.boot()
    sess.observe_outcome("ev-1", s, 1)
    assert len(client.sent) == 2
    tick = _tick_body(client.sent[1])
    assert "stream" not in tick
    assert tick["evidence"] == 1
    sess.decide(s)
    assert _tick_body(client.sent[2])["features"]["t"] == 1.0  # type: ignore[index]


def test_observe_outcome_latent_sends_a_single_stream_tagged_tick() -> None:
    s = _summary()
    client, sess = _make(
        [HANDSHAKE_OK, {"observed": 1}, {"choice": {"fire": 1, "slots": {}}}],
        utility_form="latent@1",
    )
    sess.boot()
    sess.observe_outcome("ev-1", s, 1)
    assert len(client.sent) == 2
    tick = _tick_body(client.sent[1])
    assert tick["stream"] == "outcome"
    sess.decide(s)
    assert _tick_body(client.sent[2])["features"]["t"] == 1.0  # type: ignore[index]


def test_observe_outcome_dedups_by_event_id_after_a_live_call() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 1}])
    sess.boot()
    sess.observe_outcome("ev-1", s, 1)
    n_sent = len(client.sent)
    sess.observe_outcome("ev-1", s, 1)  # duplicate: must not touch the wire
    assert len(client.sent) == n_sent


def test_observe_outcome_dedups_across_boot_replay_and_a_live_call() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 1}])
    sess.boot(outcome_replay=[("ev-1", s, 1)])
    assert "ev-1" in sess.seen_outcomes
    n_sent = len(client.sent)
    sess.observe_outcome("ev-1", s, 1)  # already seen at boot: must not touch the wire
    assert len(client.sent) == n_sent


def test_observe_outcome_error_reply_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"error": "impossible-evidence"}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.observe_outcome("ev-1", s, 1)


# --- construction guard -----------------------------------------------------------------


def test_unknown_utility_form_raises_value_error_at_construction() -> None:
    with pytest.raises(ValueError):
        MembraneSession(_FakeClient([]), u_bar={}, utility_form="bogus@1")  # type: ignore[arg-type]


# --- verdict_y(): the evidence-mapping table --------------------------------------------


@pytest.mark.parametrize("action,valence,expected", [
    ("report", "good", 1), ("report", "bad", 0),
    ("report_scoped", "good", 1), ("report_scoped", "bad", 0),
    ("abstain", "good", 0), ("abstain", "bad", 1),
    ("hedge", "good", None), ("hedge", "bad", None),
    ("ask_clarify", "good", None), ("ask_clarify", "bad", None),
    ("gather", "good", None), ("respond", "good", None),
    ("report", "weird", None), ("abstain", "", None),
    ("unknown", "unknown", None),
])
def test_verdict_y_table(action: str, valence: str, expected: int | None) -> None:
    assert verdict_y(action, valence) == expected
