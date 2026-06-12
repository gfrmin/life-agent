"""Shared fixtures for life-agent's top-level test suite.

Hermetic by default: no test may read or write the live KB. ``ask.main()`` runs
the demand-led GTD refresh before connecting (interaction contract: act-layer
state), so any test that reaches it without this redirection would project and
re-ingest the owner's LIVE ledger into the live catalogue mid-suite — caught
exactly once, 2026-06-11, before this fixture existed. Tests that need real GTD
paths override these attributes themselves (see tests/test_ask_gtd_refresh.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import life_agent.core as C


@pytest.fixture(autouse=True)
def _hermetic_gtd_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(C, "TASKS_LEDGER", tmp_path / "hermetic-events.jsonl")
    monkeypatch.setattr(C, "TASKS_STATE", tmp_path / "hermetic-state.md")
