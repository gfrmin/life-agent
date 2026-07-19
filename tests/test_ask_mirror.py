"""Thin wiring pin: scripts/ask.py's `answer_via_executor` installs the shared
membrane-shadow mirror (`life_agent.core.shadow_mirror.shadow_wrapped_post`) for every real
decide tick. The mirror's own behaviour — URL gating, the None-response skip, fail-open,
the short mirror timeout, the one-strike breaker, body shape, request/response identity —
is exercised once, directly, in tests/test_shadow_mirror.py; this file only proves ask.py
wires the real transport through it, unconditionally, with the right (bridge, question_id).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask


def test_answer_via_executor_wires_the_shared_shadow_mirror(monkeypatch: Any) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)

    wrap_calls: list[tuple[Any, str, str]] = []

    def sentinel_wrapped(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"sentinel": True}

    def fake_shadow_wrapped_post(post: Any, bridge: str, question_id: str) -> Any:
        wrap_calls.append((post, bridge, question_id))
        return sentinel_wrapped

    monkeypatch.setattr(ask.SM, "shadow_wrapped_post", fake_shadow_wrapped_post)

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": [],
                "route": {"construct": "passport number"}}

    monkeypatch.setattr(ask.EX, "decide_via_loop", fake_decide_via_loop)
    ask.answer_via_executor("my passport?", 20)

    assert len(wrap_calls) == 1  # exactly one shadow_wrapped_post construction, per call
    post_arg, bridge_arg, qid_arg = wrap_calls[0]
    assert post_arg is ask._http_post           # the real (unwrapped) transport goes in
    assert bridge_arg == ask.EXECUTOR_BRIDGE
    assert qid_arg == hashlib.sha256(b"my passport?").hexdigest()[:16]
    assert captured["post"] is sentinel_wrapped  # decide_via_loop gets the WRAPPED post back


def test_answer_via_executor_flag_off_passes_no_live_consult(monkeypatch: Any) -> None:
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    monkeypatch.setattr(ask.CFG, "membrane_live", lambda: False)
    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None}

    monkeypatch.setattr(ask.EX, "decide_via_loop", fake_decide_via_loop)
    ask.answer_via_executor("my passport?", 20)
    assert captured["live"] is None  # today's behaviour — the daemon decides


def test_answer_via_executor_flag_on_wires_the_live_consult_and_skips_the_mirror(
    monkeypatch: Any,
) -> None:
    # M3 wiring pin (review finding): under the flag, decide_via_loop must get the
    # coarse.live_decide consult AND the BARE transport — the decide mirror stays off
    # (the live path records its own enact tick; a wrapped post would consult the one
    # engine twice per tick).
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    monkeypatch.setattr(ask.CFG, "membrane_live", lambda: True)

    def sentinel_consult(payload: dict[str, Any], dec: dict[str, Any]) -> Any:
        return (dec, None)

    live_calls: list[tuple[str, str]] = []

    def fake_live_decide(bridge: str, question_id: str, **kw: Any) -> Any:
        live_calls.append((bridge, question_id))
        return sentinel_consult

    monkeypatch.setattr(ask.CRS, "live_decide", fake_live_decide)

    def forbidden_wrap(*a: Any, **kw: Any) -> Any:
        raise AssertionError("shadow_wrapped_post must not be constructed under the flag")

    monkeypatch.setattr(ask.SM, "shadow_wrapped_post", forbidden_wrap)

    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None}

    monkeypatch.setattr(ask.EX, "decide_via_loop", fake_decide_via_loop)
    ask.answer_via_executor("my passport?", 20)

    assert live_calls == [(ask.EXECUTOR_BRIDGE,
                           hashlib.sha256(b"my passport?").hexdigest()[:16])]
    assert captured["live"] is sentinel_consult
    assert captured["post"] is ask._http_post  # the bare transport — no mirror wrap
