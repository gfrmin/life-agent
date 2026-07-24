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


def test_notmuch_binary_defaults_and_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("NOTMUCH_BINARY", "/opt/notmuch")
    reloaded = importlib.reload(config)
    assert reloaded.NOTMUCH_BINARY == "/opt/notmuch"
    monkeypatch.delenv("NOTMUCH_BINARY", raising=False)
    assert importlib.reload(config).NOTMUCH_BINARY == "notmuch"


def test_data_sources_absent_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATA_SOURCES", tmp_path / "nope.yaml")
    assert config.data_sources() == {}


def test_data_sources_reads_yaml(tmp_path, monkeypatch) -> None:
    f = tmp_path / "data-sources.yaml"
    f.write_text("trips:\n  ingest:\n    query: 'folder:Trips'\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert config.data_sources()["trips"]["ingest"]["query"] == "folder:Trips"


def test_data_sources_non_mapping_yaml_returns_empty(tmp_path, monkeypatch) -> None:
    f = tmp_path / "data-sources.yaml"
    f.write_text("- just\n- a\n- list\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert config.data_sources() == {}


def test_data_sources_default_is_the_existing_registry_path() -> None:
    # Same file scripts/data_source_registry.default_registry_path() resolves, so the query
    # and the source roots share one registry (loader ignores the extra `trips:` key).
    assert config.DATA_SOURCES == config.KB / "config" / "data-sources.yaml"
