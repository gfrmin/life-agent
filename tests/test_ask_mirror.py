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




def test_answer_via_executor_always_shadow_wraps(monkeypatch: Any) -> None:
    """M5 (r15): the M3 live lane died — the executor path always mirrors through
    the shadow-wrapped transport and decide_via_loop takes no consult at all."""
    monkeypatch.setattr(ask, "_executor_ready", lambda: True)
    wrapped_calls: list[str] = []

    def fake_wrap(post: Any, bridge: str, question_id: str) -> Any:
        wrapped_calls.append(question_id)
        return post

    monkeypatch.setattr(ask.AC.SM, "shadow_wrapped_post", fake_wrap)
    captured: dict[str, Any] = {}

    def fake_decide_via_loop(question: str, k: int, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"effector": "miss", "asserted": [], "candidates": [], "credences": [],
                "p_none": None, "eu": None, "n_obs": 0, "hits": [], "route": None}

    monkeypatch.setattr(ask.AC.EX, "decide_via_loop", fake_decide_via_loop)
    ask.answer_via_executor("my passport?", 20)
    assert wrapped_calls, "the shadow mirror must always be constructed"
    assert "live" not in captured
