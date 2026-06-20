"""life_agent.core.temporal_intent — the question's temporal-scope reading (cached §18.9).

The verdict is a cached local-model classification keyed on the question alone: the same
question never calls the model twice; the prompt template + version are in the key, so a prompt
change invalidates exactly these verdicts. A scope outside the enum fails loudly and is NEVER
frozen (miss-path parity). v0 surfaces + records; it changes no decision.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from life_agent.core.temporal_intent import INTENT_SCHEMA, intent_verdict
from pkm.catalogue import run_migrations
from pkm.transform import ModelResponse


@pytest.fixture
def migrated_root(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    (tmp_path / "logs").mkdir()
    run_migrations(tmp_path)
    return tmp_path


class _FakeClient:
    engine_version = "fake-1"

    def __init__(self, scope: str) -> None:
        self._scope = scope
        self.calls = 0

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.calls += 1
        return ModelResponse(raw_text=json.dumps({"scope": self._scope}),
                             input_tokens=1, output_tokens=1, latency_ms=1,
                             cost_usd=0.0)


def test_intent_verdict_is_cached(migrated_root: Path) -> None:
    client = _FakeClient("present")
    v1 = intent_verdict(migrated_root, "what is my bank?", client=client)
    v2 = intent_verdict(migrated_root, "what is my bank?", client=client)
    assert (v1, v2) == ("present", "present")
    assert client.calls == 1  # second call replayed from the cache


def test_intent_verdict_keys_on_the_question(migrated_root: Path) -> None:
    client = _FakeClient("present")
    intent_verdict(migrated_root, "what is my bank?", client=client)
    intent_verdict(migrated_root, "what was my bank in 2022?", client=client)
    assert client.calls == 2  # distinct questions → distinct keys


def test_intent_verdict_junk_fails_loudly_and_is_not_cached(migrated_root: Path) -> None:
    bad = _FakeClient("recently")               # not in the enum
    with pytest.raises(ValueError, match="recently"):
        intent_verdict(migrated_root, "q?", client=bad)
    # Never frozen: a good client afterwards gets a fresh call, not a replay.
    good = _FakeClient("historical")
    assert intent_verdict(migrated_root, "q?", client=good) == "historical"


def test_intent_schema_is_the_four_way_partition() -> None:
    assert INTENT_SCHEMA["properties"]["scope"]["enum"] == [
        "present", "historical", "as_of", "unscoped"]
