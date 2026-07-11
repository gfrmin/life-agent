"""Hermetic test that scripts/eval_executor.py's EX.decide_via_loop caller feeds the
membrane shadow too — the SAME wrapper (scripts/ask.py's `_shadow_wrapped_post`)
scripts/ask.py's production read-path installs, so an eval run mirrors the loop exactly like
a live ask does. Only `_post_for` is exercised here — `main()` needs a live corpus + services
and is not unit-tested (no existing tests/test_eval_executor.py; out of scope for this seam).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask
import eval_executor as EE


def test_post_for_wraps_the_bare_transport(monkeypatch: Any) -> None:
    assert EE._post_for("q?") is not EE._post  # never the bare transport, unconditionally


def test_post_for_mirrors_a_decide_tick(monkeypatch: Any) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_post(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        calls.append((url, payload))
        return {"effector": "report"} if url.endswith("/decide") else {"ok": True}

    monkeypatch.setattr(EE, "_post", fake_post)
    wrapped = EE._post_for("what is my passport number?")
    wrapped(f"{EE.DAEMON}/decide", {"candidates": ["P123"]})

    urls = [u for u, _ in calls]
    assert urls == [f"{EE.DAEMON}/decide", f"{EE.BRIDGE}/decide-support"]
    mirror_body = calls[-1][1]
    assert mirror_body["payload"] == {"candidates": ["P123"]}
    assert mirror_body["dec"] == {"effector": "report"}
    assert mirror_body["question_id"] == hashlib.sha256(
        b"what is my passport number?").hexdigest()[:16]


def test_post_for_shares_asks_own_wrapper() -> None:
    # eval_executor imports the SAME scripts/ask.py wrapper (no re-implementation) — the
    # brief's "route it through the same wrapper (import from ask)".
    assert EE.ask is ask
