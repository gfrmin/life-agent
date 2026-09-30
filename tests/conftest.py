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
def _hermetic_decisions_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The M2 driver's §6.5 unavailability record (and any leaf left unstubbed) appends to
    ``config.DECISIONS_LOG`` — which, un-redirected, is the owner's LIVE calibration
    ledger. Same rule as the GTD paths above: hermetic by default; a test that needs a
    real path overrides it itself."""
    from life_agent.core import config as CFG

    monkeypatch.setattr(CFG, "DECISIONS_LOG", tmp_path / "hermetic-decisions.jsonl")


@pytest.fixture(autouse=True)
def _hermetic_pkm_root(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory,
                       monkeypatch: pytest.MonkeyPatch) -> None:
    """The machine's pkm root is unreachable by default. The A0 reach (r00-lineage-writer)
    ran through ``PKM_CONFIG``'s DEFAULT path — ``~/.config/life-agent/pkm.yaml`` on the
    owner's box — so ``ask.main`` reconciled the LIVE root with no variable exported. All
    THREE routes are neutralised here (patching the innermost symbol alone is how this class
    recurs — reviewer ruling, r00 Q1): the ``PKM_CONFIG`` environment variable and the
    ``config.PKM_CONFIG`` constant point at a scratch config naming a scratch root (a
    per-test sibling of tmp_path — never inside it, so tests that enumerate tmp_path are
    untouched); ``config.pkm_root`` and ``ask._pkm_root`` return that root. Opt-in for a
    real-shaped root: a test's own patch (tmp roots, ``/fake/root``, ``None`` — as many do), or
    the ``llm``/``system`` markers (the opt-in live suites keep the machine's config)."""
    if request.node.get_closest_marker("llm") or request.node.get_closest_marker("system"):
        return
    import sys

    from life_agent.core import config as CFG

    scratch = tmp_path_factory.mktemp("hermetic-pkm")
    root = scratch / "root"
    cfg = scratch / "pkm.yaml"
    cfg.write_text(f"root_dir: {root}\nextractors: {{}}\n", encoding="utf-8")
    monkeypatch.setenv("PKM_CONFIG", str(cfg))
    monkeypatch.setattr(CFG, "PKM_CONFIG", cfg)
    monkeypatch.setattr(CFG, "pkm_root", lambda: root)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: root)


@pytest.fixture(autouse=True)
def _hermetic_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The executor is ask's one read-path, but it needs the live bridge; no hermetic test
    may reach for it. Stub readiness to False so ask deterministically reads the stack as
    down without a localhost probe. Tests of the executor path override this by name
    (tests/test_ask.py)."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import ask

    monkeypatch.setattr(ask, "_executor_ready", lambda: False)
