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


@pytest.fixture(autouse=True)
def _hermetic_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test routes through the lookup family unless it asks to: the router would
    call the live local model and the family would spawn the Julia skin. Tests of the
    family itself bind the real functions by name at import time (tests/test_lookup.py),
    which this attribute patch deliberately does not reach."""
    from life_agent.core import lookup as LK

    monkeypatch.setattr(LK, "lookup_answer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _hermetic_narrative(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same reasoning for the narrative family (it spawns the Julia skin for Ū and
    appends to the live decision log): stubbed to None — ask.answer's disabled seam —
    unless the test binds the real functions by name (tests/test_narrative.py)."""
    from life_agent.core import narrative as N

    monkeypatch.setattr(N, "narrative_answer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _hermetic_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The executor (credence answer-brain daemon) is ask's DEFAULT read-path, but it needs the
    live daemon/bridge; no hermetic test may reach for it. Stub readiness to False so ask
    deterministically takes the in-process fallback (the prior default) without a localhost
    probe. Tests of the executor path override this by name (tests/test_ask.py)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
