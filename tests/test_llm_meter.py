"""Tests for the cache/provider fields on ``LLMResult`` and the call meter (``core.llm``).

Hermetic: ``urllib.request.urlopen`` is monkeypatched with canned Anthropic/OpenAI payloads
carrying cache-usage fields — no network, no live model call. Mirrors the ``STAGES_LAST``
module-global pattern in ``scripts/ask.py``: a caller resets the meter, makes calls, reads
the snapshot.
"""
from __future__ import annotations

import json

import pytest

from life_agent.core import llm


class _FakeResp:
    """A minimal stand-in for the object ``with urllib.request.urlopen(req) as resp`` yields."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _anthropic_payload(**usage_overrides: int) -> bytes:
    usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    usage.update(usage_overrides)
    body = {
        "model": "claude-sonnet-4-6-20260101",
        "content": [{"type": "text", "text": "hi"}],
        "usage": usage,
    }
    return json.dumps(body).encode()


def _openai_payload(cached_tokens: int = 0) -> bytes:
    body = {
        "model": "gpt-5.1-2026-01-01",
        "choices": [{"message": {"content": "hi"}}],
        "usage": {
            "prompt_tokens": 80,
            "completion_tokens": 20,
            "prompt_tokens_details": {"cached_tokens": cached_tokens},
        },
    }
    return json.dumps(body).encode()


@pytest.fixture(autouse=True)
def _no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module fakes the HTTP layer — never touch gnome-keyring."""
    monkeypatch.setattr(llm, "secret", lambda name: "fake-key")


@pytest.fixture(autouse=True)
def _meter_off_by_default() -> None:
    """Guard against a prior test leaving the meter active (module-global chokepoint)."""
    llm._METER = None
    yield
    llm._METER = None


def test_anthropic_complete_parses_cache_fields_and_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm.urllib.request,
        "urlopen",
        lambda req, **kw: _FakeResp(
            _anthropic_payload(cache_read_input_tokens=30, cache_creation_input_tokens=10)
        ),
    )
    result = llm.anthropic_complete("sys", "user")
    assert result.provider == "anthropic"
    assert result.cache_read_tokens == 30
    assert result.cache_write_tokens == 10
    assert result.in_tokens == 100
    assert result.out_tokens == 50


def test_openai_complete_parses_cache_fields_and_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        llm.urllib.request,
        "urlopen",
        lambda req, **kw: _FakeResp(_openai_payload(cached_tokens=15)),
    )
    result = llm.openai_complete("sys", "user", model="gpt-5.1")
    assert result.provider == "openai"
    assert result.cache_read_tokens == 15
    assert result.cache_write_tokens == 0
    assert result.in_tokens == 80
    assert result.out_tokens == 20


def test_meter_inactive_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, **kw: _FakeResp(_anthropic_payload())
    )
    llm.anthropic_complete("sys", "user")
    # No reset_meter() call — meter_read() reports empty, doesn't blow up.
    assert llm.meter_read() == []


def test_reset_meter_collects_both_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([_anthropic_payload(), _openai_payload()])
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, **kw: _FakeResp(next(responses))
    )
    llm.reset_meter()
    llm.anthropic_complete("sys", "user")
    llm.openai_complete("sys", "user", model="gpt-5.1")
    results = llm.meter_read()
    assert len(results) == 2
    assert {r.provider for r in results} == {"anthropic", "openai"}


def test_meter_read_snapshots_then_stops_collecting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm.urllib.request, "urlopen", lambda req, **kw: _FakeResp(_anthropic_payload())
    )
    llm.reset_meter()
    llm.anthropic_complete("sys", "user")
    first = llm.meter_read()
    assert len(first) == 1

    llm.anthropic_complete("sys", "user")  # meter is inactive again post-read
    second = llm.meter_read()
    assert second == []


def test_llm_result_new_fields_are_additive_with_defaults() -> None:
    r = llm.LLMResult(text="x", in_tokens=1, out_tokens=1, seconds=0.1)
    assert r.served_model == ""
    assert r.cache_read_tokens == 0
    assert r.cache_write_tokens == 0
    assert r.provider == ""
