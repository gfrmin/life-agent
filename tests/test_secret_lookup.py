"""Tests for ``core.llm.secret`` — the env/keyring resolution seam.

In their own file: ``test_llm_meter.py`` autouse-stubs ``llm.secret`` for every test,
and these tests need the real one.
"""
from __future__ import annotations

import pytest

from life_agent.core import llm

# --- secret(): the keyring lookup must fail loudly, never hang -------------------------
#
# 2026-08-30: production jarvis hung 15+ minutes on a `secret-tool lookup` against a
# post-resume LOCKED gnome-keyring — secret-tool blocks forever waiting for an unlock
# prompt that never comes under systemd. A bounded lookup turns that hang into a failed
# unit, which systemd restarts and the watchdog can page on.

def test_secret_lookup_times_out_loudly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object,
) -> None:
    import time as _time
    from pathlib import Path

    fake = Path(str(tmp_path)) / "secret-tool"
    fake.write_text("#!/bin/sh\nexec /usr/bin/sleep 3\n")  # absolute: PATH is stripped below  # PII-OK: /usr/bin is a system path (PATH is stripped in this test)
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("LLM_TEST_TIMEOUT_KEY", raising=False)
    monkeypatch.setattr(llm, "_SECRET_TOOL_TIMEOUT_S", 0.3)
    t0 = _time.monotonic()
    with pytest.raises(SystemExit) as exc:
        llm.secret("LLM_TEST_TIMEOUT_KEY")
    assert _time.monotonic() - t0 < 2.5  # bounded: the hang class is the defect
    assert "locked" in str(exc.value).lower()  # the message must name the likely cause


def test_secret_env_still_wins_over_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TEST_TIMEOUT_KEY", "from-env")
    assert llm.secret("LLM_TEST_TIMEOUT_KEY") == "from-env"
