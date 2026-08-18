"""The live mirror (design §8 C5, §10) over the synthetic KB — append-shaped, loud when behind,
fail-open and counted, recorded switch, configured-store-only. NOT wired to any writer here:
these tests call the hook the way a writer will, after its own legacy append.

# PII-OK: synthetic — the ledger_kb fixture (tests/conftest.py)."""
from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from life_agent.core import reactions as RX
from life_agent.ledger import migrate as MIG
from life_agent.ledger import mirror as M
from life_agent.ledger import sources as SRC
from life_agent.ledger.golden import Paths
from life_agent.ledger.store import LedgerStore
from life_agent.tasks import events as TEV
from tests.conftest import LEDGER_MARKER, _reaction

MARKER = LEDGER_MARKER


@pytest.fixture
def migrated(ledger_kb: tuple[Path, Paths]) -> tuple[Path, Paths, LedgerStore]:
    root, p = ledger_kb
    store = LedgerStore(root / "ledger")
    MIG.migrate(p, store, out=io.StringIO(), epoch="T")
    M._reset_process_state()
    return root, p, store


def _react(p: Paths, i: int) -> None:
    RX.append(p.reactions, _reaction("d" * 64, "good", f"2026-01-02T00:00:{i:02d}+00:00"))


def _row(store: LedgerStore, sid: str) -> dict:
    return store.manifest()["sources"][sid]


def test_migration_records_the_legacy_offset(migrated: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = migrated
    for sid, f in p.legacy_files().items():
        if f.exists():
            assert _row(store, sid)["legacy_bytes"] == f.stat().st_size, sid


def test_append_shaped_in_step_is_the_same_event_the_sweep_would_write(
        migrated: tuple[Path, Paths, LedgerStore], caplog: pytest.LogCaptureFixture) -> None:
    _root, p, store = migrated
    before = store.parseable_count("calibration.reactions")
    tally0 = _row(store, "calibration.reactions")["writer_tally"]
    _react(p, 1)
    with caplog.at_level(logging.INFO, logger="life_agent.ledger.mirror"):
        r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert (r.action, r.written, r.behind) == ("appended", 1, 0)
    assert store.parseable_count("calibration.reactions") == before + 1
    # the sweep proper finds nothing to do: mirrored line == swept line by construction
    s = MIG.sync_source("calibration.reactions", p, store, verify_prefix=True, mode="sync")
    assert (s.written, s.skipped) == (0, before + 1)
    row = _row(store, "calibration.reactions")
    assert row["writer_tally"] == tally0 + 1 and row["mirror_appends"] == 1
    assert row["legacy_bytes"] == p.reactions.stat().st_size
    # the switch state was announced once and recorded (owner Q5)
    assert store.manifest()["mirror_state"]["enabled"] is True
    assert sum("ledger mirror: enabled" in m for m in caplog.messages) == 1
    assert MARKER not in caplog.text
    # a second in-step append does not re-announce
    _react(p, 2)
    r2 = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r2.action == "appended" and r2.detail == f"seq {before + 2}..{before + 2}"
    assert sum("ledger mirror: enabled" in m for m in caplog.messages) == 1


def test_batch_append_with_n(migrated: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = migrated
    before = store.parseable_count("act.tasks")
    t = TEV.new_identity()
    evs = [TEV.asserted(t, {"user_id": 1, "text": "three", "list": "inbox", "origin": "human"},
                        tx_time="2026-01-02T00:00:00"),
           TEV.amended(t, {"list": "next"}, tx_time="2026-01-02T00:00:01"),
           TEV.disposed(t, "done", tx_time="2026-01-02T00:00:02")]
    TEV.append(p.tasks_ledger, evs)
    r = M.after_legacy_append("act.tasks", p.tasks_ledger, n=len(evs), store=store, paths=p)
    assert (r.action, r.written, r.behind) == ("appended", 3, 0)
    assert [e.seq for e in store.read("act.tasks")][-3:] == [before + 1, before + 2, before + 3]


def test_behind_is_loud_counted_and_caught_up(
        migrated: tuple[Path, Paths, LedgerStore], caplog: pytest.LogCaptureFixture) -> None:
    _root, p, store = migrated
    before = store.parseable_count("calibration.reactions")
    _react(p, 1)      # two appends nobody mirrored (a hook-less writer, a crash, an interval)
    _react(p, 2)
    _react(p, 3)      # this one is mirrored
    with caplog.at_level(logging.WARNING, logger="life_agent.ledger.mirror"):
        r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert (r.action, r.written, r.behind) == ("behind", 3, 2)
    assert store.parseable_count("calibration.reactions") == before + 3
    assert any("BEHIND by 2" in m for m in caplog.messages)
    row = _row(store, "calibration.reactions")
    assert row["mirror_behind_events"] == 2 and row["mirror_behind_calls"] == 1
    assert MARKER not in caplog.text


def test_noop_when_already_mirrored(migrated: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = migrated
    r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "noop" and r.written == 0


def test_no_recorded_offset_falls_back_to_the_full_sweep(
        migrated: tuple[Path, Paths, LedgerStore], caplog: pytest.LogCaptureFixture) -> None:
    _root, p, store = migrated
    m = store.manifest()
    del m["sources"]["calibration.reactions"]["legacy_bytes"]      # an older manifest
    store._write_manifest(m)
    _react(p, 1)
    with caplog.at_level(logging.WARNING, logger="life_agent.ledger.mirror"):
        r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "synced" and r.written == 1
    assert any("full sync" in msg and "no recorded legacy offset" in msg for msg in caplog.messages)
    row = _row(store, "calibration.reactions")
    assert row["mirror_syncs"] == 1 and row["legacy_bytes"] == p.reactions.stat().st_size
    _react(p, 2)      # and the next call is append-shaped again
    assert M.after_legacy_append("calibration.reactions", p.reactions,
                                 store=store, paths=p).action == "appended"


def test_non_event_line_in_the_delta_falls_back_and_is_counted_not_mirrored(
        migrated: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = migrated
    before = store.parseable_count("calibration.reactions")
    with p.reactions.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    _react(p, 1)
    r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "synced" and r.written == 1
    assert store.parseable_count("calibration.reactions") == before + 1
    assert _row(store, "calibration.reactions")["unparseable"] == 1


def test_unterminated_legacy_tail_is_not_trusted(migrated: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = migrated
    with p.reactions.open("a", encoding="utf-8") as fh:
        fh.write('{"partial": ')       # a writer mid-line, or a torn legacy tail
    assert M._delta(p.reactions, _row(store, "calibration.reactions")["legacy_bytes"]) is None
    r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "synced"      # the sweep decides; nothing raised


def test_disabled_switch_is_recorded_and_writes_nothing(
        migrated: tuple[Path, Paths, LedgerStore], monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    _root, p, store = migrated
    monkeypatch.setenv(M.MIRROR_ENV, "0")
    before = store.parseable_count("calibration.reactions")
    _react(p, 1)
    with caplog.at_level(logging.WARNING, logger="life_agent.ledger.mirror"):
        r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "disabled"
    assert store.parseable_count("calibration.reactions") == before
    st = store.manifest()["mirror_state"]
    assert st["enabled"] is False and st["env"] == "0"
    assert any("ledger mirror: disabled" in m for m in caplog.messages)


def test_inert_without_an_initialised_stream(ledger_kb: tuple[Path, Paths],
                                             caplog: pytest.LogCaptureFixture) -> None:
    root, p = ledger_kb
    M._reset_process_state()
    store = LedgerStore(root / "no-stream")
    with caplog.at_level(logging.WARNING, logger="life_agent.ledger.mirror"):
        r1 = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
        r2 = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r1.action == r2.action == "inert"
    assert not (root / "no-stream").exists()
    assert sum("not initialised" in m for m in caplog.messages) == 1


def test_only_the_configured_legacy_store_is_mirrored(
        migrated: tuple[Path, Paths, LedgerStore], tmp_path: Path) -> None:
    _root, p, store = migrated
    other = tmp_path / "elsewhere.jsonl"
    RX.append(other, _reaction("e" * 64, "good", "2026-01-02T00:00:00+00:00"))
    before = store.parseable_count("calibration.reactions")
    r = M.after_legacy_append("calibration.reactions", other, store=store, paths=p)
    assert r.action == "skipped" and store.parseable_count("calibration.reactions") == before


def test_fail_open_is_counted_and_never_raises(
        migrated: tuple[Path, Paths, LedgerStore], monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture) -> None:
    _root, p, store = migrated
    _react(p, 1)

    def boom(*a: object, **k: object) -> tuple[int, int]:
        raise RuntimeError("disk says no")
    monkeypatch.setattr(LedgerStore, "append_many", boom)
    with caplog.at_level(logging.WARNING, logger="life_agent.ledger.mirror"):
        r = M.after_legacy_append("calibration.reactions", p.reactions, store=store, paths=p)
    assert r.action == "failed" and "RuntimeError" in r.detail
    row = _row(store, "calibration.reactions")
    assert row["mirror_failures"] == 1 and "last_mirror_failure_at" in row
    assert any("failed" in m for m in caplog.messages)
    # a swept source offered to the mirror is a programming error — surfaced, not raised
    r2 = M.after_legacy_append("pkm.demand", p.reactions, store=store, paths=p)
    assert r2.action == "failed" and "not a mirrored source" in r2.detail


def test_parse_line_is_the_scan_parser(ledger_kb: tuple[Path, Paths]) -> None:
    """The mirror parses with the SAME function the sweep uses (no re-implementation)."""
    _root, p = ledger_kb
    sc = SRC.scan("calibration.reactions", p)
    lines = p.reactions.read_text(encoding="utf-8").splitlines()
    for rec in sc.parsed:
        line = lines[int(rec.locator.split(":")[1]) - 1]
        again, status = SRC.parse_line("calibration.reactions", line,
                                       ordinal=rec.ordinal, locator=rec.locator)
        assert status == "ok" and again == rec
    assert SRC.parse_line("calibration.reactions", "", ordinal=1, locator="x")[1] == "blank"
    assert SRC.parse_line("calibration.reactions", "{", ordinal=1, locator="x")[1] == "unparseable"
    assert SRC.parse_line("calibration.reactions", '{"a": 1, "a": 2}',
                          ordinal=1, locator="x")[1] == "duplicate_key"
