"""Tests for ask.py's demand-led GTD refresh (system-design.md §5).

Before each question, the ask path checks whether the GTD ledger has moved past
its knowledge projection; if so it re-projects, re-ingests the one state
document, and says so (nothing silent). Hermetic: the pkm re-ingest is
monkeypatched — the porcelain sequence itself is exercised live in the Phase-1
verification gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ask

from life_agent.tasks import events as ev
from life_agent.tasks import knowledge


@pytest.fixture()
def gtd_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    ledger = tmp_path / "events.jsonl"
    state = tmp_path / "state.md"
    monkeypatch.setattr(ask.C, "TASKS_LEDGER", ledger)
    monkeypatch.setattr(ask.C, "TASKS_STATE", state)
    return ledger, state


def _seed_ledger(ledger: Path) -> None:
    ev.append(
        ledger,
        [ev.asserted("id-1", {"user_id": 1, "text": "buy milk"}, tx_time="2026-06-01T10:00:00")],
    )


# --- gtd_stale: the cheap check -------------------------------------------- #


def test_no_ledger_is_never_stale(gtd_paths: tuple[Path, Path]) -> None:
    assert ask.gtd_stale() is False


def test_ledger_without_state_doc_is_stale(gtd_paths: tuple[Path, Path]) -> None:
    ledger, _ = gtd_paths
    _seed_ledger(ledger)
    assert ask.gtd_stale() is True


def test_projected_state_is_fresh_until_ledger_moves(
    gtd_paths: tuple[Path, Path],
) -> None:
    ledger, state = gtd_paths
    _seed_ledger(ledger)
    knowledge.write_state(ledger, state)
    assert ask.gtd_stale() is False
    ev.append(ledger, [ev.disposed("id-1", "done", tx_time="2026-06-02T09:00:00")])
    assert ask.gtd_stale() is True


def test_old_render_version_is_stale(
    gtd_paths: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The projection is f(events, renderer): a renderer bump invalidates the
    state doc exactly like a ledger append."""
    ledger, state = gtd_paths
    _seed_ledger(ledger)
    knowledge.write_state(ledger, state)
    assert ask.gtd_stale() is False
    monkeypatch.setattr(knowledge, "RENDER_VERSION", knowledge.RENDER_VERSION + 1)
    assert ask.gtd_stale() is True


# --- ensure_gtd_fresh: project + re-ingest + say so ------------------------ #


def test_refresh_projects_and_reingests(
    gtd_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger, state = gtd_paths
    _seed_ledger(ledger)
    calls: list[Path] = []
    monkeypatch.setattr(ask, "_reingest_state", lambda root, p: calls.append(p))
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))

    ask.ensure_gtd_fresh()

    assert calls == [state]
    assert knowledge.parse_stamp(state.read_text(encoding="utf-8")) is not None
    out = capsys.readouterr().out
    assert ask.REFRESH_NOTES["refreshed"].format(n=1) in out
    # Fresh now: a second call is a quiet no-op (no re-ingest, no output).
    ask.ensure_gtd_fresh()
    assert calls == [state]
    assert capsys.readouterr().out == ""


def test_refresh_failure_is_fail_open_and_named(
    gtd_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger, _ = gtd_paths
    _seed_ledger(ledger)

    def boom(root: Path, p: Path) -> None:
        raise RuntimeError("catalogue locked")

    monkeypatch.setattr(ask, "_reingest_state", boom)
    monkeypatch.setattr(ask, "_pkm_root", lambda: Path("/fake/root"))

    ask.ensure_gtd_fresh()  # must not raise

    out = capsys.readouterr().out
    assert "catalogue locked" in out
    assert ask.REFRESH_NOTES["failed"].split("{")[0] in out


def test_refresh_without_pkm_root_is_fail_open(
    gtd_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger, _ = gtd_paths
    _seed_ledger(ledger)
    monkeypatch.setattr(ask, "_pkm_root", lambda: None)

    ask.ensure_gtd_fresh()  # must not raise

    assert ask.REFRESH_NOTES["failed"].split("{")[0] in capsys.readouterr().out


# --- drift gate: the note table is rendered, never ad-hoc ------------------ #


def test_refresh_notes_render() -> None:
    assert set(ask.REFRESH_NOTES) == {"refreshed", "failed"}
    assert "42" in ask.REFRESH_NOTES["refreshed"].format(n=42)
    assert "oops" in ask.REFRESH_NOTES["failed"].format(error="oops")
