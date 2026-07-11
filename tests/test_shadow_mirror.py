"""Hermetic tests for the shared membrane-shadow mirror (life_agent.core.shadow_mirror) —
the ONE implementation of the seam that fans every real `/decide` tick out to the shadow's
`/decide-support`, off the answer path. Every production caller of
`executor.decide_via_loop` (scripts/ask.py, scripts/eval_executor.py,
src/life_agent/core/ask_client.py) installs `shadow_wrapped_post` from here — see each
caller's own test file for a thin wiring-only pin, not a re-test of this logic.

Fail-open by contract: a mirror POST failure must never touch the real answer the executor
already has in hand, and — the mirror leg's own short timeout plus one-strike breaker below
— must never delay it beyond a small, bounded cost per question.
"""
from __future__ import annotations

import inspect
from typing import Any

from life_agent.core import shadow_mirror as SM

B = "http://bridge"


# --- shadow_wrapped_post: the wrapper every production caller installs ----------------- #

def test_wrapper_forwards_and_returns_real_response_even_when_mirror_raises() -> None:
    real_calls: list[str] = []
    mirror_calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        real_calls.append(url)
        return {"effector": "report", "credences": [0.9]}

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        raise RuntimeError("shadow unreachable")

    wrapped = SM.shadow_wrapped_post(post, B, "q-1", mirror_post=mirror_post)
    resp = wrapped("http://daemon/decide", {"candidates": ["P123"]})

    assert resp == {"effector": "report", "credences": [0.9]}  # the real answer, untouched
    assert real_calls == ["http://daemon/decide"]
    assert mirror_calls == [f"{B}/decide-support"]  # mirror still attempted


def test_wrapper_fires_mirror_only_on_decide_urls() -> None:
    mirror_calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True}

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        return {"ok": True}

    wrapped = SM.shadow_wrapped_post(post, B, "q-1", mirror_post=mirror_post)
    for url in ("http://bridge/route", "http://bridge/retrieve", "http://bridge/extract",
               "http://bridge/probe/subject", "http://daemon/utility", "http://bridge/narrative"):
        mirror_calls.clear()
        wrapped(url, {})
        assert mirror_calls == []  # no /decide-support call for a non-/decide URL


def test_wrapper_skips_mirror_on_none_response() -> None:
    mirror_calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return None  # the executor's own down/failure shape

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        return {"ok": True}

    wrapped = SM.shadow_wrapped_post(post, B, "q-1", mirror_post=mirror_post)
    resp = wrapped("http://daemon/decide", {"x": 1})
    assert resp is None
    assert mirror_calls == []  # nothing to mirror


def test_wrapper_mirrors_body_shape_question_id_payload_dec() -> None:
    mirror_calls: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"effector": "report", "credences": [0.9]}

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append((url, body))
        return {"ok": True}

    wrapped = SM.shadow_wrapped_post(post, B, "q-77", mirror_post=mirror_post)
    req_body = {"candidates": ["P123"], "rho": 0.7}
    wrapped("http://daemon/decide", req_body)

    mirror_url, mirror_body = mirror_calls[-1]
    assert mirror_url == f"{B}/decide-support"
    assert mirror_body == {"question_id": "q-77", "payload": req_body,
                           "dec": {"effector": "report", "credences": [0.9]}}


def test_wrapper_does_not_mutate_request_or_response() -> None:
    req = {"candidates": ["a"], "nested": {"x": 1}}
    req_snapshot = {"candidates": ["a"], "nested": {"x": 1}}
    resp_obj = {"effector": "report"}

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return resp_obj

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"ok": True}

    wrapped = SM.shadow_wrapped_post(post, B, "q-1", mirror_post=mirror_post)
    out = wrapped("http://daemon/decide", req)

    assert req == req_snapshot          # the real request body is untouched
    assert out is resp_obj              # the real response is returned by identity, not a copy


def test_wrapper_propagates_a_real_leg_failure_before_ever_mirroring() -> None:
    mirror_calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        raise ConnectionError("daemon down")

    def mirror_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        return {"ok": True}

    wrapped = SM.shadow_wrapped_post(post, B, "q-1", mirror_post=mirror_post)
    raised = False
    try:
        wrapped("http://daemon/decide", {})
    except ConnectionError:
        raised = True
    assert raised
    assert mirror_calls == []  # never reached the mirror — nothing to mirror


# --- one-strike circuit breaker ---------------------------------------------------------- #

def test_circuit_breaker_trips_after_first_mirror_failure_and_stays_tripped() -> None:
    mirror_calls: list[str] = []

    def real_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"effector": "report"}

    def raising_mirror(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        raise TimeoutError("mirror wedged")

    wrapped = SM.shadow_wrapped_post(real_post, B, "q-1", mirror_post=raising_mirror)

    for _ in range(3):  # three decide ticks — e.g. grow escalation re-deciding
        resp = wrapped("http://daemon/decide", {"x": 1})
        assert resp == {"effector": "report"}  # every real tick still unaffected

    assert len(mirror_calls) == 1  # one strike: never retried after the first failure


def test_circuit_breaker_is_scoped_per_wrapped_post() -> None:
    # A fresh wrapped post (a new question) gets its own breaker — a prior question's
    # tripped mirror must not silently disable the next one's.
    def real_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"effector": "report"}

    def raising_mirror(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        raise TimeoutError("mirror wedged")

    tripped_wrapped = SM.shadow_wrapped_post(real_post, B, "q-1", mirror_post=raising_mirror)
    tripped_wrapped("http://daemon/decide", {})

    mirror_calls: list[str] = []

    def counting_mirror(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        mirror_calls.append(url)
        return {"ok": True}

    fresh_wrapped = SM.shadow_wrapped_post(real_post, B, "q-2", mirror_post=counting_mirror)
    fresh_wrapped("http://daemon/decide", {})

    assert mirror_calls == [f"{B}/decide-support"]  # the new wrapper still mirrors


# --- mirror_decide: the standalone fan-out, exercised directly -------------------------- #

def test_mirror_decide_swallows_all_exceptions_and_reports_failure() -> None:
    def raising_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        raise RuntimeError("boom")

    ok = SM.mirror_decide(raising_post, B, "q-1", "http://daemon/decide", {},
                          {"effector": "report"})  # must not raise
    assert ok is False  # the wrapper's breaker relies on this signal


def test_mirror_decide_posts_expected_shape() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, body))
        return {"ok": True}

    ok = SM.mirror_decide(post, B, "q-9", "http://daemon/decide", {"a": 1}, {"b": 2})
    assert ok is True
    assert calls == [(f"{B}/decide-support",
                      {"question_id": "q-9", "payload": {"a": 1}, "dec": {"b": 2}})]


def test_mirror_decide_no_call_on_non_decide_url() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return {}

    ok = SM.mirror_decide(post, B, "q-1", "http://bridge/route", {}, {"x": 1})
    assert calls == []
    assert ok is True  # nothing to mirror is not a failure


def test_mirror_decide_no_call_on_none_response() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return {}

    ok = SM.mirror_decide(post, B, "q-1", "http://daemon/decide", {}, None)
    assert calls == []
    assert ok is True


# --- the mirror leg's own short timeout, separate from the real leg's ------------------- #

class _FakeUrlopenResp:
    def read(self) -> bytes:
        return b"{}"

    def __enter__(self) -> _FakeUrlopenResp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_default_mirror_poster_is_bounded_and_strictly_shorter_than_a_real_legs_300s(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeUrlopenResp:
        captured["timeout"] = timeout
        return _FakeUrlopenResp()

    monkeypatch.setattr(SM.urllib.request, "urlopen", fake_urlopen)
    SM._default_mirror_post(f"{B}/decide-support", {"a": 1})

    assert captured["timeout"] == SM.MIRROR_TIMEOUT_S
    assert SM.MIRROR_TIMEOUT_S < 300  # strictly shorter than every real-leg poster's timeout


def test_shadow_wrapped_post_with_default_mirror_poster_uses_the_short_timeout(
    monkeypatch: Any,
) -> None:
    # End-to-end through the wrapper (not the poster in isolation): proves a wrapped post
    # built WITHOUT overriding mirror_post — exactly how every production caller builds it —
    # still bounds the mirror leg to MIRROR_TIMEOUT_S, promptly, never the real leg's 300s.
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float | None = None) -> _FakeUrlopenResp:
        captured["timeout"] = timeout
        return _FakeUrlopenResp()

    monkeypatch.setattr(SM.urllib.request, "urlopen", fake_urlopen)

    def real_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"effector": "report"}  # the real leg never touches urllib in this test

    wrapped = SM.shadow_wrapped_post(real_post, B, "q-1")  # default mirror_post, unwired
    wrapped("http://daemon/decide", {})

    assert captured["timeout"] == SM.MIRROR_TIMEOUT_S


def test_shadow_wrapped_post_defaults_to_the_short_timeout_mirror_poster() -> None:
    # Regression gate: someone re-wiring the default mirror_post back to a 300s poster (e.g.
    # accidentally passing the real leg's own `post`) breaks this.
    sig = inspect.signature(SM.shadow_wrapped_post)
    assert sig.parameters["mirror_post"].default is SM._default_mirror_post
