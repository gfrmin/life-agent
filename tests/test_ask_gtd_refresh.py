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


def test_gtd_stale_on_unreadable_state_doc(gtd_paths: tuple[Path, Path]) -> None:
    """A corrupt state doc is stale, never an exception — gtd_stale() is called
    outside the fail-open try in the REPL loop, so it must not raise."""
    ledger, state = gtd_paths
    _seed_ledger(ledger)
    state.write_bytes(b"\xff\xfe not utf-8 \xff")
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
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: Path("/fake/root"))

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
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: Path("/fake/root"))

    ask.ensure_gtd_fresh()  # must not raise

    out = capsys.readouterr().out
    assert "catalogue locked" in out
    assert ask.REFRESH_NOTES["failed"].split("{")[0] in out


def test_failed_refresh_stays_stale_and_retries(
    gtd_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The stamp is the freshness oracle, and write_state runs BEFORE the
    re-ingest — so a failed ingest must un-stamp, or the stamped doc masks the
    failure: gtd_stale() would report fresh, the retry would never happen, and
    every answer in the window would silently serve stale catalogue state."""
    ledger, _ = gtd_paths
    _seed_ledger(ledger)
    calls: list[Path] = []

    def boom(root: Path, p: Path) -> None:
        calls.append(p)
        raise RuntimeError("catalogue locked")

    monkeypatch.setattr(ask, "_reingest_state", boom)
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: Path("/fake/root"))

    ask.ensure_gtd_fresh()
    assert ask.gtd_stale() is True  # the failure is not masked by the stamp
    ask.ensure_gtd_fresh()  # ...so the next question retries and re-names it
    assert len(calls) == 2
    assert capsys.readouterr().out.count("catalogue locked") == 2


def test_refresh_without_pkm_root_is_fail_open(
    gtd_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger, _ = gtd_paths
    _seed_ledger(ledger)
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: None)

    ask.ensure_gtd_fresh()  # must not raise

    assert ask.REFRESH_NOTES["failed"].split("{")[0] in capsys.readouterr().out


# --- reconcile-or-refuse: the re-ingest never extracts over an unregistered artefact -- #
# pkm's extract sweeps every file-complete artefact without a catalogue row at start (SPEC
# §6.2) — the r03 loss. So the refresh registers what is registerable first, and if any
# registerable key is still pending it does NOT extract: a named line, un-stamped, retried.


def _pkm_tmp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from pkm.catalogue import run_migrations
    root = tmp_path / "pkm"
    (root / "cache").mkdir(parents=True)
    run_migrations(root)
    cfg = tmp_path / "pkm.yaml"
    cfg.write_text(f"root_dir: {root}\nextractors: {{}}\n", encoding="utf-8")
    monkeypatch.setattr(ask.C, "PKM_CONFIG", cfg)
    monkeypatch.setattr(ask.TERM, "_pkm_root", lambda: root)
    return root


def _fake_extract(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("pkm.extract.extract", lambda root, cfg, **kw: calls.append(kw))
    return calls


def test_refresh_reconciles_before_it_extracts(
    gtd_paths: tuple[Path, Path], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    from life_agent.core import derivations as D
    from pkm.catalogue import open_catalogue
    ledger, _state = gtd_paths
    _seed_ledger(ledger)
    root = _pkm_tmp_root(tmp_path, monkeypatch)
    key = D.expand_key("q", model="m-2026", prompt_template="P", temperature=0.0, max_tokens=9)
    D.record(root, key, b"terms", lineage=[])          # recorded file-first, row lagging
    extracts = _fake_extract(monkeypatch)

    ask.ensure_gtd_fresh()

    assert len(extracts) == 1                            # nothing registerable was pending …
    with open_catalogue(root) as conn:                   # … because it was registered FIRST
        assert conn.execute("SELECT count(*) FROM artifacts WHERE cache_key = ?",
                            [key.cache_key]).fetchone()[0] == 1
    assert (root / "external" / "pending.txt").read_text() == ""
    assert ask.REFRESH_NOTES["refreshed"].format(n=1) in capsys.readouterr().out


def test_refresh_refuses_to_extract_while_a_registerable_key_is_pending(
    gtd_paths: tuple[Path, Path], tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    from life_agent.core import derivations as D
    ledger, _state = gtd_paths
    _seed_ledger(ledger)
    root = _pkm_tmp_root(tmp_path, monkeypatch)
    key = D.expand_key("q", model="m-2026", prompt_template="P", temperature=0.0, max_tokens=9)
    D.record(root, key, b"terms", lineage=[])
    # the reconciler could not register it (the writer lock held by a running extraction, a
    # schema-less catalogue …): the key stays queued with its meta.json on disk
    monkeypatch.setattr(ask.D, "reconcile", lambda root: D.ReconcileCounts())
    extracts = _fake_extract(monkeypatch)

    ask.ensure_gtd_fresh()

    assert extracts == []                                # never reached the sweep
    out = capsys.readouterr().out
    assert ask.REFRESH_NOTES["blocked"].format(n=1) in out
    assert ask.REFRESH_NOTES["failed"].split("{")[0] not in out
    assert ask.gtd_stale() is True                       # un-stamped: the next ask retries
    assert (root / "external" / "pending.txt").read_text().split() == [key.cache_key]


# --- drift gate: the note table is rendered, never ad-hoc ------------------ #


def test_refresh_notes_render() -> None:
    assert set(ask.REFRESH_NOTES) == {"refreshed", "failed", "blocked"}
    assert "42" in ask.REFRESH_NOTES["refreshed"].format(n=42)
    assert "oops" in ask.REFRESH_NOTES["failed"].format(error="oops")
    assert "7" in ask.REFRESH_NOTES["blocked"].format(n=7)
