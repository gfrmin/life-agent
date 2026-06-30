"""Cloud-completion error handling (life_agent.core.llm) — hermetic, no network.

The bridge is a long-lived service: a cloud error (e.g. an over-quota 400) must surface as a
CATCHABLE exception so the request handler returns 500 and the service stays up — never a
``SystemExit`` (a ``BaseException`` that escapes ``except Exception`` and kills the process).
These tests pin that contract by faking ``urlopen`` to raise an HTTPError.

Run: uv run --project . python -m pytest tests/test_llm.py
"""
from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from life_agent.core import llm as LLM


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.anthropic.com/v1/messages", code,
                                  "err", {}, io.BytesIO(body))


def test_anthropic_complete_raises_catchable_llmerror_on_http_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> object:
        raise _http_error(400, b'{"error":"usage limit"}')

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(LLM, "secret", lambda name: "fake-key")
    with pytest.raises(LLM.LLMError) as ei:
        LLM.anthropic_complete("system", "user")
    assert "400" in str(ei.value)
    # the load-bearing property: a service can catch it (Exception), it does NOT kill the process.
    assert isinstance(ei.value, Exception)
    assert not isinstance(ei.value, SystemExit)


def test_openai_complete_raises_catchable_llmerror_on_http_error(
        monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> object:
        raise _http_error(429, b'{"error":"rate limit"}')

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(LLM, "secret", lambda name: "fake-key")
    with pytest.raises(LLM.LLMError):
        LLM.openai_complete("system", "user", model="gpt-x")
