"""The trips faculty's resolved paths live under $LIFE_AGENT_KB, never in code."""
from __future__ import annotations

import importlib

import life_agent.core.config as config


def test_trips_paths_are_under_kb() -> None:
    assert config.TRIPS_LEDGER == config.KB / "trips" / "events.jsonl"
    assert config.TRIPS_DB_PATH.name == "trips.db"
    assert config.TRIPS_DB_PATH.parent == config.KB / "trips"


def test_extractor_path_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("KITINERARY_EXTRACTOR", "/opt/kitinerary")
    reloaded = importlib.reload(config)
    assert reloaded.KITINERARY_EXTRACTOR == "/opt/kitinerary"
    monkeypatch.delenv("KITINERARY_EXTRACTOR", raising=False)
    reloaded_default = importlib.reload(config)
    assert reloaded_default.KITINERARY_EXTRACTOR == "/usr/lib/kf6/kitinerary-extractor"
