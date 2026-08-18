"""The C5 dual-write hooks at the typed writers (design §8 C5): each writer mirrors its append
onto the stream when — and only when — it writes the CONFIGURED legacy store; a writer at any
other path (every other test in this suite) never touches a stream, not even its manifest.

# PII-OK: synthetic — the ledger_kb fixture (tests/conftest.py)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from life_agent.core import claude_verdicts as CV
from life_agent.core import decisions as DEC
from life_agent.core import gather_outcomes as GO
from life_agent.core import outcomes as O
from life_agent.core import reactions as RX
from life_agent.ledger import migrate as MIG
from life_agent.ledger import mirror as M
from life_agent.ledger.golden import Paths
from life_agent.ledger.store import LedgerStore
from life_agent.tasks import events as TEV
from life_agent.trips import events as REV
from tests.conftest import _decision, _edge_outcome, _reaction

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import answer_labels


def _writers(p: Paths) -> list[tuple[str, int, object]]:
    """(source_id, lines appended, thunk) for eight of the nine writers — `scripts/verdict.py`'s
    corrections append is inline in its interactive `run()` and is exercised by the mirror tests
    (same hook, same source)."""
    t = TEV.new_identity()
    return [
        ("calibration.outcomes", 1, lambda: O.append(
            p.outcomes, _edge_outcome("CORRECT", 0.7, "l9", "2026-01-02T00:00:00+00:00"))),
        ("calibration.decisions", 1, lambda: DEC.append(
            p.decisions, _decision("9" * 64, "abstain", [0.5], "2026-01-02T00:00:00+00:00"))),
        ("calibration.reactions", 1, lambda: RX.append(
            p.reactions, _reaction("9" * 64, "good", "2026-01-02T00:00:00+00:00"))),
        ("calibration.claude_verdicts", 1, lambda: CV.append(
            p.claude_verdicts, CV.ClaudeVerdictEvent(
                tx_time="2026-01-02T00:00:00+00:00", question_id="0" * 16, decision_id="9" * 64,
                dimensions={"correct": 1, "complete": 0, "grounded": 1}))),
        ("calibration.gather_outcomes", 1, lambda: GO.append_outcome(
            p.gather_outcomes, str(GO.GROW_ACTUATORS[0]["probe"]),
            {"extracted": "some", "p_none": "lo", "indeterminate": "none"}, recovered=False)),
        ("act.tasks", 2, lambda: TEV.append(p.tasks_ledger, [
            TEV.asserted(t, {"user_id": 1, "text": "hooked", "list": "inbox", "origin": "human"},
                         tx_time="2026-01-02T00:00:00"),
            TEV.disposed(t, "done", tx_time="2026-01-02T00:00:01")])),
        ("act.trips", 1, lambda: REV.append(p.trips_ledger, [REV.observed(
            "res-9", {"@type": "FlightReservation", "reservationNumber": "ZZ997"},
            fidelity="manual", source_id="s9", received_at="2026-01-02T00:00:00",
            tx_time="2026-01-02T00:00:00")])),
        ("eval.labels", 1, lambda: answer_labels.append_label(
            p.labels, "q-009", "v", "correct", "")),
    ]


@pytest.fixture
def wired(ledger_kb: tuple[Path, Paths], monkeypatch: pytest.MonkeyPatch,
          ) -> tuple[Path, Paths, LedgerStore]:
    """The synthetic KB becomes THE configured KB: the mirror's default store root → root/ledger
    (re-pointing the seam conftest's `_hermetic_mirror` isolates) and `Paths.from_config` → the
    fixture's paths (the configured legacy stores)."""
    root, p = ledger_kb
    store = LedgerStore(root / "ledger")
    MIG.migrate(p, store, out=io.StringIO(), epoch="T")
    monkeypatch.setattr(M, "_default_store_root", lambda: root / "ledger")
    monkeypatch.setattr(Paths, "from_config", classmethod(lambda cls, **kw: p))
    M._reset_process_state()
    return root, p, store


def test_each_wired_writer_mirrors_its_append_at_the_configured_path(
        wired: tuple[Path, Paths, LedgerStore]) -> None:
    _root, p, store = wired
    for sid, n, write in _writers(p):
        before = store.parseable_count(sid)
        write()
        after = store.parseable_count(sid)
        assert after == before + n, (sid, before, after)
        row = store.manifest()["sources"][sid]
        assert row["mirror_appends"] >= n
        assert row["legacy_bytes"] == p.legacy_file(sid).stat().st_size
    assert store.manifest()["mirror_state"]["enabled"] is True
    # and the sweep proper finds nothing to add anywhere: hook == sweep, event for event
    for r in MIG.sync(p, store, sources=tuple(s for s, _, _ in _writers(p)), out=io.StringIO()):
        assert r.written == 0, r


def test_writers_at_other_paths_never_touch_the_stream(
        wired: tuple[Path, Paths, LedgerStore], tmp_path: Path) -> None:
    """Every other test in this suite writes tmp paths through these writers: none may reach
    the configured stream — no segment growth, no manifest write, no `mirror_state` note."""
    _root, p, store = wired
    manifest_before = store.manifest_path.read_bytes()
    counts_before = {sid: store.parseable_count(sid) for sid, _, _ in _writers(p)}
    other = tmp_path / "elsewhere"
    other.mkdir()
    q = Paths(tasks_ledger=other / "t.jsonl", trips_ledger=other / "r.jsonl",
              outcomes=other / "o.jsonl", decisions=other / "d.jsonl", reactions=other / "x.jsonl",
              claude_verdicts=other / "c.jsonl", gather_outcomes=other / "g.jsonl",
              corrections=other / "k.jsonl", elicitations=other / "e.jsonl",
              utility_model=other / "m.yaml", labels=other / "l.jsonl", pkm_root=None)
    for _sid, _n, write in _writers(q):
        write()
    assert store.manifest_path.read_bytes() == manifest_before
    assert {sid: store.parseable_count(sid) for sid, _, _ in _writers(p)} == counts_before
    assert "mirror_state" not in store.manifest()


def test_a_writer_never_raises_when_the_mirror_fails(
        wired: tuple[Path, Paths, LedgerStore], monkeypatch: pytest.MonkeyPatch) -> None:
    _root, p, store = wired

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("mirror down")
    monkeypatch.setattr(M, "_mirror", boom)
    O.append(p.outcomes, _edge_outcome("CORRECT", 0.7, "l8", "2026-01-02T00:00:00+00:00"))
    assert O.read(p.outcomes)[-1].lineage_keys == ("l8",)          # the legacy append happened
    assert store.manifest()["sources"]["calibration.outcomes"]["mirror_failures"] == 1


def test_disabled_switch_stops_every_writer_from_mirroring(
        wired: tuple[Path, Paths, LedgerStore], monkeypatch: pytest.MonkeyPatch) -> None:
    _root, p, store = wired
    monkeypatch.setenv(M.MIRROR_ENV, "0")
    counts_before = {sid: store.parseable_count(sid) for sid, _, _ in _writers(p)}
    for _sid, _n, write in _writers(p):
        write()
    assert {sid: store.parseable_count(sid) for sid, _, _ in _writers(p)} == counts_before
    assert store.manifest()["mirror_state"]["enabled"] is False
    # the rollback switch is one name, shared by the CLI gate and the mirror
    assert M.MIRROR_ENV == MIG.MIRROR_ENV == "LIFE_AGENT_LEDGER_MIRROR"
