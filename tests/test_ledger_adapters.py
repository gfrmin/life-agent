"""The §7 adapters + the harness re-pointed at the stream (design §8 C3-C4).

# PII-OK: synthetic — the ledger_kb fixture (tests/conftest.py)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from life_agent.ledger import adapters as AD
from life_agent.ledger import golden as G
from life_agent.ledger import migrate as M
from life_agent.ledger.store import LedgerStore
from pkm.rebuild import _iter_meta_files
from tests.conftest import LEDGER_MARKER

ALL = list(G.ARTEFACTS)


def _migrated(root: Path, p: G.Paths) -> LedgerStore:
    store = LedgerStore(root / "ledger")
    M.migrate(p, store, out=io.StringIO(), epoch="E0")
    return store


def test_all_fourteen_green_from_the_stream(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T1", p, kb=root, out=io.StringIO())      # snapshot: legacy stores
    store = _migrated(root, p)
    out = io.StringIO()
    ok, res = G.compare(ALL, "T1", p, kb=root, source="stream", store=store, out=out)
    text = out.getvalue()
    assert ok and all(res.values()), text
    assert text.startswith("stream   root=$LIFE_AGENT_KB/ledger epoch=E0 events={")
    assert "stream   answers: 3 decision-referenced keys, 1 on disk, 1 of those are pkm.artifact" \
        in text
    assert LEDGER_MARKER not in text
    # S8: the unseeded stream materialisation is scratch — gone after a green run
    assert not G.work_dir(G.golden_root(root) / "T1", "stream").exists()


def test_materialisation_is_the_existing_fold_over_records(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    store = _migrated(root, p)
    w = root / "scratch"
    sp = AD.materialise(store, w, p)
    # A2: events from the stream, sha from the legacy ledger (R1)
    assert sp.tasks_ledger != p.tasks_ledger and sp.state_sha_source == p.tasks_ledger
    assert G.a2_state_md(sp) == G.a2_state_md(p)
    # A10: keys from the stream's decisions, bytes from the real root (R5)
    assert sp.answers_root == p.pkm_root and sp.pkm_root == w / "pkm"
    assert G.a10_answers(sp) == G.a10_answers(p)
    # A11 (V8): the cache-shaped tree is walked by pkm's own _iter_meta_files
    assert [k for k, _ in _iter_meta_files(sp.pkm_root)] == ["a" * 64]  # type: ignore[arg-type]
    assert G.a11_pkm_index(sp) == G.a11_pkm_index(p)
    # A12: pkm.demand regrouped by timestamp[:10] == the legacy UTC-day file
    assert sorted(f.name for f in (w / "pkm" / "logs" / "demand").iterdir()) == ["2026-01-01.jsonl"]
    assert G.a12_demand(sp) == G.a12_demand(p)
    # every JSONL source: one canonical line per event, seq order
    lines = (w / "act.tasks.jsonl").read_text().splitlines()
    assert len(lines) == 4 and json.loads(lines[0])["type"] == "asserted"


def test_truncation_limits_and_changed_sources(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    store = _migrated(root, p)
    sp = AD.materialise(store, root / "s1", p, sources=("calibration.reactions",),
                        limits={"calibration.reactions": 2})
    assert len(sp.reactions.read_text().splitlines()) == 2
    assert AD.changed_sources(p, sp) == ("calibration.reactions",)
    assert AD.changed_sources(p, p) == ()


@pytest.mark.parametrize("seed", [s for s in G.SEEDS if G.SEEDS[s].category != "invariance"])
def test_each_kill_from_the_stream_copy(ledger_kb: tuple[Path, G.Paths], seed: str) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T1", p, kb=root, out=io.StringIO())
    store = _migrated(root, p)
    out = io.StringIO()
    ok, res = G.compare(ALL, "T1", p, kb=root, seed=seed, source="stream", store=store, out=out)
    text = out.getvalue()
    assert not ok, text
    for claimed in G.SEEDS[seed].must_kill:
        assert res[claimed] is False, (seed, claimed, text)
    assert "CLAIM MET" in text and LEDGER_MARKER not in text
    if seed != "substitute-artifact":
        assert "stream   re-migrated into work store:" in text      # the seed hit the stream copy
    else:
        assert "seed touched no stream source" in text
    if G.SEEDS[seed].exact:
        assert "[EXACT]" in text


def test_invariance_fixture_green_from_the_stream(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    G.snapshot(ALL, "T1", p, kb=root, out=io.StringIO())
    store = _migrated(root, p)
    out = io.StringIO()
    ok, _ = G.compare(ALL, "T1", p, kb=root, seed="unrouted-reaction", source="stream",
                      store=store, out=out)
    assert ok and "GREEN as required" in out.getvalue()


def test_cli_from_stream(ledger_kb: tuple[Path, G.Paths], monkeypatch: pytest.MonkeyPatch,
                         capsys: pytest.CaptureFixture[str]) -> None:
    root, p = ledger_kb
    monkeypatch.setattr(G.Paths, "from_config", classmethod(lambda cls: p))
    monkeypatch.setattr(G.config, "KB", root)
    _migrated(root, p)
    assert G.main(["snapshot", "all", "--t0", "T2"]) == 0
    assert G.main(["compare", "all", "--t0", "T2", "--from", "stream"]) == 0
    assert G.main(["compare", "all", "--t0", "T2", "--from", "stream",
                   "--seed-defect", "unrouted-claude-verdict"]) == 1
    assert LEDGER_MARKER not in capsys.readouterr().out


def test_crash_fixture_from_the_stream_torn_tail_then_sync_recovers_and_folds_identically(
        ledger_kb: tuple[Path, G.Paths]) -> None:
    """§9 crash fixture on the stream side: a segment with a torn last line, then the sweep
    (the legacy store is the recovery source) → dense seq, one manifest quarantine entry, the
    torn bytes untouched (S6), and every fold output identical to the T1 snapshot."""
    root, p = ledger_kb
    G.snapshot(ALL, "T1", p, kb=root, out=io.StringIO())
    store = _migrated(root, p)
    seg = store.segment_path("calibration.reactions")
    data = seg.read_bytes()
    cut = data.rfind(b"\n", 0, len(data) - 1) + 1          # start of the last line
    torn = data[:cut] + data[cut:cut + 40]                    # a crash mid-line, no newline
    seg.write_bytes(torn)
    assert store.parseable_count("calibration.reactions") == 3
    r = M.sync(p, store, sources=("calibration.reactions",), out=io.StringIO())[0]
    assert r.written == 1 and r.after == 4
    q = store.quarantine("calibration.reactions")
    assert len(q) == 1 and q[0].reason == "unterminated" and q[0].byte_offset == cut
    assert seg.read_bytes().startswith(torn + b"\n")         # never truncated (S6)
    assert [e.seq for e in store.read("calibration.reactions")] == [1, 2, 3, 4]
    ok, _ = G.compare(ALL, "T1", p, kb=root, source="stream", store=store, out=io.StringIO())
    assert ok
