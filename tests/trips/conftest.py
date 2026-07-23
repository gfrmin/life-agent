# tests/trips/conftest.py
"""Isolate every trips test to a tmp ledger + tmp db (mirrors tests/test_tasks.py::temp_gtd)."""
from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.trips import commands, store


@pytest.fixture(autouse=True)
def temp_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "trips.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()
