"""Thin wiring pin: scripts/eval_executor.py's `_post_for` installs the SAME shared
membrane-shadow mirror (`life_agent.core.shadow_mirror.shadow_wrapped_post`) scripts/ask.py's
production read-path installs, so an eval run mirrors the loop exactly like a live ask does.
The mirror's own behaviour is exercised once, directly, in tests/test_shadow_mirror.py. Only
`_post_for` is exercised here — `main()` needs a live corpus + services and is not
unit-tested (no existing tests/test_eval_executor.py; out of scope for this seam).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import eval_executor as EE


def test_post_for_wires_the_shared_shadow_mirror(monkeypatch: Any) -> None:
    wrap_calls: list[tuple[Any, str, str]] = []

    def sentinel_wrapped(url: str, body: dict[str, Any]) -> dict[str, Any] | None:
        return {"sentinel": True}

    def fake_shadow_wrapped_post(post: Any, bridge: str, question_id: str) -> Any:
        wrap_calls.append((post, bridge, question_id))
        return sentinel_wrapped

    monkeypatch.setattr(EE.SM, "shadow_wrapped_post", fake_shadow_wrapped_post)

    result = EE._post_for("what is my passport number?")

    assert result is sentinel_wrapped  # _post_for returns exactly what the shared wrapper built
    assert len(wrap_calls) == 1
    post_arg, bridge_arg, qid_arg = wrap_calls[0]
    assert post_arg is EE._post          # the real (unwrapped) transport goes in
    assert bridge_arg == EE.BRIDGE
    assert qid_arg == hashlib.sha256(b"what is my passport number?").hexdigest()[:16]


def test_flag_off_no_live_consult_and_the_mirror_stays_on(monkeypatch: Any) -> None:
    monkeypatch.setattr(EE.CFG, "membrane_live", lambda: False)
    assert EE._live_for("my passport?") is None
    # _post_for still wraps (the shadow mirror is the flag-off feed) — pinned by the
    # existing test above; this only pins the live arm's absence.


def test_flag_on_wires_the_live_consult_and_skips_the_mirror(monkeypatch: Any) -> None:
    monkeypatch.setattr(EE.CFG, "membrane_live", lambda: True)

    def sentinel_consult(payload: dict[str, Any], dec: dict[str, Any]) -> Any:
        return (dec, None)

    live_calls: list[tuple[str, str]] = []

    def fake_live_decide(bridge: str, question_id: str, **kw: Any) -> Any:
        live_calls.append((bridge, question_id))
        return sentinel_consult

    monkeypatch.setattr(EE.CRS, "live_decide", fake_live_decide)
    assert EE._live_for("my passport?") is sentinel_consult
    assert live_calls == [(EE.BRIDGE, hashlib.sha256(b"my passport?").hexdigest()[:16])]
    assert EE._post_for("my passport?") is EE._post  # bare — the mirror stays off
