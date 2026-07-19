"""Hermetic tests for the membrane session (life_agent.membrane.session).

No wire, no subprocess: `_FakeClient` is a scripted transport — an object with a
`.request(obj) -> dict` method that records every request and pops canned replies off a
list, matching `MembraneClient`'s surface without importing it (Task 3's session only
ever calls `client.request(dict) -> dict`). These pin: boot's `said@1` handshake +
two-segment replay order + not-ok/error handshake raising; decide leaving `_t` unmoved
and relaying readouts verbatim (the choice-relay discipline, membrane-wire.md §6.4); the
re-derived wire's ONE untagged evidence tick per verdict/outcome (the table@1/latent@1
stream-tagged double-feed is historical), `_t` advancing by exactly one; outcome dedup by
event_id across boot and live; the full-assignment `{"act": {"act": <grid value>}}`
choice decode (int and float accepted, bool rejected, an undeclared value raising); and
the `verdict_y` evidence-mapping table.
"""
from __future__ import annotations

import pytest

from life_agent.membrane import world as W
from life_agent.membrane.client import MembraneError
from life_agent.membrane.session import MembraneSession, ShadowChoice, verdict_y

HANDSHAKE_OK: dict[str, object] = {"ok": True, "proto": 1, "models": 100, "namespace_bits": 5.0}

# every affordance's grid value, by name — the reply encoding `{"act": {"act": <value>}}`.
_V = dict(W.AFFORDANCES)


def _act(name: str) -> dict[str, object]:
    """A well-formed decide reply choosing affordance `name`."""
    return {"act": {"act": _V[name]}}


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
    assert client.sent == [W.handshake_decl({}, utility_form="said@1")]


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
    client, sess = _make([HANDSHAKE_OK, _act("respond")])
    sess.boot()
    sess.decide(s)
    tick = _tick_body(client.sent[1])
    assert tick["menu"] == [W.ACT_NAME]  # the one writable name
    assert "utility" not in tick         # the sentence is declared once, at the handshake
    assert tick["features"] == W.shadow_features(s, 0.0)


def test_decide_leaves_t_unmoved_across_calls() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, _act("respond"), _act("respond")])
    sess.boot()
    sess.decide(s)
    sess.decide(s)
    assert _tick_body(client.sent[1])["features"]["t"] == 0.0  # type: ignore[index]
    assert _tick_body(client.sent[2])["features"]["t"] == 0.0  # type: ignore[index]


def test_decide_returns_readouts_verbatim_minus_the_act_key() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {**_act("respond"), "p1": 0.8, "entropy_bits": 1.2}])
    sess.boot()
    choice = sess.decide(s)
    assert choice == ShadowChoice(
        action="respond", raw_internal=False, readouts={"p1": 0.8, "entropy_bits": 1.2}
    )


def test_decide_is_a_pure_choice_relay_readouts_never_affect_the_action() -> None:
    # membrane-wire.md §6.4: two replies differing ONLY in observability scalars must
    # yield the identical action — the adapter branches on "act", nothing else.
    s = _summary()
    _client, sess = _make([
        HANDSHAKE_OK,
        {**_act("abstain"), "p1": 0.9, "entropy_bits": 1.0},
        {**_act("abstain"), "p1": 0.1, "entropy_bits": 9.0},
    ])
    sess.boot()
    c1 = sess.decide(s)
    c2 = sess.decide(s)
    assert c1.action == c2.action == "abstain"
    assert c1.readouts != c2.readouts


def test_decide_maps_every_declared_value_to_its_action() -> None:
    s = _summary()
    for action, value in W.AFFORDANCES:
        _client, sess = _make([HANDSHAKE_OK, {"act": {"act": value}}])
        sess.boot()
        choice = sess.decide(s)
        assert choice.action == action
        assert choice.raw_internal is False


def test_decide_accepts_int_and_float_act_values_but_rejects_bool() -> None:
    s = _summary()
    gather = _V["gather"]  # 2.0
    for raw in (int(gather), float(gather)):
        _client, sess = _make([HANDSHAKE_OK, {"act": {"act": raw}}])
        sess.boot()
        assert sess.decide(s).action == "gather"
    # a bool is not a grid value, even though `True == 1` numerically.
    _client, sess = _make([HANDSHAKE_OK, {"act": {"act": True}}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


def test_decide_undeclared_act_value_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"act": {"act": 9}}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


def test_decide_error_reply_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"error": "impossible-evidence"}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


@pytest.mark.parametrize("reply", [
    {"ok": True},                 # no act key at all
    {"act": "not-a-dict"},        # act present but not an assignment dict
    {"act": {}},                  # assignment dict without the writable name
])
def test_decide_malformed_reply_raises(reply: dict[str, object]) -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, reply])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.decide(s)


# --- observe_verdict(): one untagged evidence tick ------------------------------------


def test_observe_verdict_single_untagged_tick_and_advances_t_once() -> None:
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 0}, _act("respond")])
    sess.boot()
    sess.observe_verdict(s, 0)
    assert len(client.sent) == 2  # handshake + one evidence tick
    tick = _tick_body(client.sent[1])
    assert "stream" not in tick   # the stream-tagged double-feed was latent@1 machinery
    assert tick["evidence"] == 0
    sess.decide(s)
    assert _tick_body(client.sent[2])["features"]["t"] == 1.0  # type: ignore[index]


def test_observe_verdict_error_reply_raises_membrane_error() -> None:
    s = _summary()
    _client, sess = _make([HANDSHAKE_OK, {"error": "impossible-evidence"}])
    sess.boot()
    with pytest.raises(MembraneError):
        sess.observe_verdict(s, 1)


# --- observe_outcome(): one untagged evidence tick, dedup by event_id -----------------


def test_observe_outcome_sends_a_single_untagged_evidence_tick() -> None:
    # the ``said@1`` utility already prices y for every affordance, so an outcome is
    # ordinary evidence — one untagged tick, never inert, never stream-tagged.
    s = _summary()
    client, sess = _make([HANDSHAKE_OK, {"observed": 1}, _act("respond")])
    sess.boot()
    sess.observe_outcome("ev-1", s, 1)
    assert len(client.sent) == 2
    tick = _tick_body(client.sent[1])
    assert "stream" not in tick
    assert tick["evidence"] == 1
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
