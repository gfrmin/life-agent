"""The reach→know client (core/ask_client.py) — hermetic.

Jarvis's `question` intent routes to the SAME executor read-path the terminal uses
(interaction-contract: asking about your life is *know*, whatever transport carried it):
one call answers (decide_via_loop → render_view), logs the terminal decision through the
bridge's /log_decision (so the one-bit verdict folds through the existing reaction loop),
and returns the decision_id the in-chat verdict binds to. `react` posts the verdict and
names the fold fate in ask-live's own vocabulary — never implying every verdict counts.
"""
from __future__ import annotations

import hashlib
from typing import Any

from life_agent.core import ask_client as AC
from life_agent.core import executor as EX


def _fake_view(effector: str = "report") -> dict[str, Any]:
    return {"effector": effector, "asserted": ["P123"] if effector == "report" else [],
            "candidates": ["P123"], "credences": [0.92], "p_none": 0.05, "eu": 0.8,
            "n_obs": 2, "hits": [{"artifact_cache_key": "d0", "chunk_text": "No: P123"}],
            "route": {"construct": "passport number"}}


def test_answer_renders_and_binds_the_decision(monkeypatch: Any) -> None:
    posted: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: _fake_view())

    def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        posted.append((url, payload))
        assert url.endswith("/log_decision")
        return {"decision_id": "ab-cafe"}

    reply, decision_id = AC.answer("what is my passport number?",
                                   post=post, get=lambda u: {}, check_ready=False)
    assert "P123" in reply                       # the shared credence grammar rendering
    assert decision_id == "ab-cafe"              # the id the in-chat verdict binds to
    assert posted and posted[0][1]["decision"]["effector"] == "report"


def test_answer_narrative_or_miss_binds_nothing(monkeypatch: Any) -> None:
    view = _fake_view("miss")
    view["candidates"], view["credences"] = [], []
    monkeypatch.setattr(EX, "decide_via_loop", lambda *a, **k: view)
    reply, decision_id = AC.answer("q?", post=lambda u, p: {"decision_id": "x"},
                                   get=lambda u: {}, check_ready=False)
    assert decision_id is None                   # nothing foldable to bind
    assert reply                                 # still a named reply, never empty


def test_answer_wires_the_shared_shadow_mirror(monkeypatch: Any) -> None:
    # Jarvis's real traffic is a production caller of EX.decide_via_loop too — its post must
    # be shadow-wrapped through the SAME shared mirror scripts/ask.py installs, unconditionally.
    # The mirror's own behaviour (URL gating, fail-open, timeout, breaker, body shape) is
    # exercised once, directly, in tests/test_shadow_mirror.py — this is a wiring pin only.
    def bare_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True}

    wrap_calls: list[tuple[Any, str, str]] = []

    def sentinel_wrapped(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"sentinel": True}

    def fake_shadow_wrapped_post(post: Any, bridge: str, question_id: str) -> Any:
        wrap_calls.append((post, bridge, question_id))
        return sentinel_wrapped

    monkeypatch.setattr(AC.SM, "shadow_wrapped_post", fake_shadow_wrapped_post)

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _fake_view("miss")  # not a LOOKUP_ACTION_ORDER effector — no extra /log_decision

    monkeypatch.setattr(EX, "decide_via_loop", fake_decide_via_loop)
    AC.answer("what is my passport number?", post=bare_post, get=lambda u: {},
             check_ready=False)

    assert len(wrap_calls) == 1
    post_arg, bridge_arg, qid_arg = wrap_calls[0]
    assert post_arg is bare_post  # the real (unwrapped) transport goes in
    assert bridge_arg == AC.BRIDGE
    assert qid_arg == hashlib.sha256(b"what is my passport number?").hexdigest()[:16]
    assert captured["post"] is sentinel_wrapped  # decide_via_loop gets the WRAPPED post back


def test_answer_names_a_down_stack(monkeypatch: Any) -> None:
    monkeypatch.setattr(AC, "_ready", lambda: False)
    reply, decision_id = AC.answer("q?")
    assert "unavailable" in reply and decision_id is None


def test_post_surfaces_the_500_body(monkeypatch: Any) -> None:
    # The bridge RETURNS a seam failure's name in the 500 body (server.py: "visible to
    # the caller, never swallowed") — the PRODUCTION transport (jarvis → ask_client)
    # must carry it into the raised error, exactly like scripts/ask.py's _http_post
    # (review Major: the fix landed on one of three near-identical transports).
    import io
    import urllib.error
    import urllib.request

    import pytest

    def fake_urlopen(req: Any, timeout: int = 0) -> Any:
        raise urllib.error.HTTPError(
            "http://b/probe/corroborate", 500, "Internal Server Error", None,
            io.BytesIO(b'{"error": "ValueError: Invalid isoformat string"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError, match="isoformat"):
        AC._post("http://b/probe/corroborate", {"question": "q"})


def test_react_names_the_fold_fate() -> None:
    def post_folds(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert payload == {"decision_id": "ab-1", "valence": "good"}
        return {"valence": "good", "family": "lookup", "chosen_action": "abstain",
                "folds": True}

    assert "folds into the utility posterior" in AC.react("ab-1", "good", post=post_folds)

    def post_report(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"valence": "bad", "family": "lookup", "chosen_action": "report",
                "folds": False}

    assert "recorded — not folded" in AC.react("ab-1", "bad", post=post_report)


def test_react_failure_is_named_not_silent() -> None:
    def post_boom(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("connection refused")

    assert "not recorded" in AC.react("ab-1", "good", post=post_boom)


def test_answer_flag_on_wires_the_live_consult_and_skips_the_mirror(monkeypatch: Any) -> None:
    # M3 wiring pin (review finding): under LIFE_AGENT_MEMBRANE_LIVE the consult goes in
    # as `live` and the transport stays BARE (the live path records its own enact tick).
    monkeypatch.setattr(AC.CFG, "membrane_live", lambda: True)

    def sentinel_consult(payload: dict[str, Any], dec: dict[str, Any]) -> Any:
        return (dec, None)

    live_calls: list[tuple[str, str]] = []

    def fake_live_decide(bridge: str, question_id: str, **kw: Any) -> Any:
        live_calls.append((bridge, question_id))
        return sentinel_consult

    monkeypatch.setattr(AC.CRS, "live_decide", fake_live_decide)
    monkeypatch.setattr(
        AC.SM, "shadow_wrapped_post",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("mirror must stay off")))

    def bare_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True}

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return _fake_view("miss")

    monkeypatch.setattr(EX, "decide_via_loop", fake_decide_via_loop)
    AC.answer("what is my passport number?", post=bare_post, get=lambda u: {},
              check_ready=False)

    assert live_calls == [(AC.BRIDGE,
                           hashlib.sha256(b"what is my passport number?").hexdigest()[:16])]
    assert captured["live"] is sentinel_consult
    assert captured["post"] is bare_post
