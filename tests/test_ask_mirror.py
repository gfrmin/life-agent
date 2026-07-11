"""Hermetic tests for the ask mirror (scripts/ask.py) — the seam that fans every real
`/decide` tick out to the membrane shadow's `/decide-support`, off the answer path.

Fail-open by contract: a mirror POST failure must never touch the real answer the executor
already has in hand. Hermetic — no live bridge/daemon; a scripted ``post`` fake stands in for
the transport `EX.decide_via_loop` injects (PRINCIPLES §5).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

B = "http://bridge"


# --- _shadow_wrapped_post: the wrapper every production caller installs ---------------- #

def test_wrapper_forwards_and_returns_real_response_even_when_mirror_raises() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        if url.endswith("/decide-support"):
            raise RuntimeError("shadow unreachable")
        return {"effector": "report", "credences": [0.9]}

    wrapped = ask._shadow_wrapped_post(post, B, "q-1")
    resp = wrapped("http://daemon/decide", {"candidates": ["P123"]})

    assert resp == {"effector": "report", "credences": [0.9]}  # the real answer, untouched
    assert calls == ["http://daemon/decide", f"{B}/decide-support"]  # mirror still attempted


def test_wrapper_fires_mirror_only_on_decide_urls() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return {"ok": True}

    wrapped = ask._shadow_wrapped_post(post, B, "q-1")
    for url in ("http://bridge/route", "http://bridge/retrieve", "http://bridge/extract",
               "http://bridge/probe/subject", "http://daemon/utility", "http://bridge/narrative"):
        calls.clear()
        wrapped(url, {})
        assert calls == [url]  # no follow-up /decide-support call


def test_wrapper_skips_mirror_on_none_response() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return None  # the executor's own down/failure shape

    wrapped = ask._shadow_wrapped_post(post, B, "q-1")
    resp = wrapped("http://daemon/decide", {"x": 1})
    assert resp is None
    assert calls == ["http://daemon/decide"]  # nothing to mirror


def test_wrapper_mirrors_body_shape_question_id_payload_dec() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, body))
        if url.endswith("/decide"):
            return {"effector": "report", "credences": [0.9]}
        return {"ok": True}

    wrapped = ask._shadow_wrapped_post(post, B, "q-77")
    req_body = {"candidates": ["P123"], "rho": 0.7}
    wrapped("http://daemon/decide", req_body)

    mirror_url, mirror_body = calls[-1]
    assert mirror_url == f"{B}/decide-support"
    assert mirror_body == {"question_id": "q-77", "payload": req_body,
                           "dec": {"effector": "report", "credences": [0.9]}}


def test_wrapper_does_not_mutate_request_or_response() -> None:
    req = {"candidates": ["a"], "nested": {"x": 1}}
    req_snapshot = {"candidates": ["a"], "nested": {"x": 1}}
    resp_obj = {"effector": "report"}

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return resp_obj if url.endswith("/decide") else {"ok": True}

    wrapped = ask._shadow_wrapped_post(post, B, "q-1")
    out = wrapped("http://daemon/decide", req)

    assert req == req_snapshot          # the real request body is untouched
    assert out is resp_obj              # the real response is returned by identity, not a copy


def test_wrapper_propagates_a_real_leg_failure_before_ever_mirroring() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        raise ConnectionError("daemon down")

    wrapped = ask._shadow_wrapped_post(post, B, "q-1")
    raised = False
    try:
        wrapped("http://daemon/decide", {})
    except ConnectionError:
        raised = True
    assert raised
    assert calls == ["http://daemon/decide"]  # never reached the mirror — nothing to mirror


# --- _mirror_decide: the standalone fan-out, exercised directly ------------------------ #

def test_mirror_decide_swallows_all_exceptions() -> None:
    def raising_post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        raise RuntimeError("boom")

    ask._mirror_decide(raising_post, B, "q-1", "http://daemon/decide", {},
                       {"effector": "report"})  # must not raise


def test_mirror_decide_posts_expected_shape() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, body))
        return {"ok": True}

    ask._mirror_decide(post, B, "q-9", "http://daemon/decide", {"a": 1}, {"b": 2})
    assert calls == [(f"{B}/decide-support",
                      {"question_id": "q-9", "payload": {"a": 1}, "dec": {"b": 2}})]


def test_mirror_decide_no_call_on_non_decide_url() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return {}

    ask._mirror_decide(post, B, "q-1", "http://bridge/route", {}, {"x": 1})
    assert calls == []


def test_mirror_decide_no_call_on_none_response() -> None:
    calls: list[str] = []

    def post(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        calls.append(url)
        return {}

    ask._mirror_decide(post, B, "q-1", "http://daemon/decide", {}, None)
    assert calls == []


# --- answer_via_executor: production wiring --------------------------------------------- #

def test_answer_via_executor_wires_the_shadow_wrapped_post(monkeypatch: Any) -> None:
    # The production caller must pass a SHADOW-WRAPPED post to decide_via_loop, unconditionally
    # — not the bare transport — so every live decide tick feeds the shadow.
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_http_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, payload))
        return {"effector": "report"} if url.endswith("/decide") else {"ok": True}

    monkeypatch.setattr(ask, "_http_post", fake_http_post)
    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        # Exercise the injected post exactly as the real loop would for one /decide tick.
        kwargs["post"](f"{ask.EXECUTOR_DAEMON}/decide", {"candidates": ["P123"]})
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": [],
                "route": {"construct": "passport number"}}

    monkeypatch.setattr(ask.EX, "decide_via_loop", fake_decide_via_loop)
    ask.answer_via_executor("my passport?", 20)

    assert captured["post"] is not fake_http_post  # wrapped, never the bare transport
    urls = [u for u, _ in calls]
    assert urls == [f"{ask.EXECUTOR_DAEMON}/decide", f"{ask.EXECUTOR_BRIDGE}/decide-support"]
    mirror_body = calls[-1][1]
    assert mirror_body["payload"] == {"candidates": ["P123"]}
    assert mirror_body["dec"] == {"effector": "report"}
    assert mirror_body["question_id"] == hashlib.sha256(b"my passport?").hexdigest()[:16]
