"""The migration writer / sweeps (design §8 C0-C2, C5-C6) over the synthetic KB.

# PII-OK: synthetic — every value is invented (see tests/conftest.py ledger_kb)."""
from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from life_agent.ledger import golden as G
from life_agent.ledger import migrate as M
from life_agent.ledger import sources as SRC
from life_agent.ledger.store import LedgerConflictError, LedgerStore
from pkm.cache import meta_file
from tests.conftest import LEDGER_MARKER

ALL = SRC.MIGRATION_ORDER


def _store(root: Path) -> LedgerStore:
    return LedgerStore(root / "ledger")


def test_census_counts_agree_with_the_harness_counts(ledger_kb: tuple[Path, G.Paths]) -> None:
    _root, p = ledger_kb
    out = io.StringIO()
    c = M.census(p, out=out)
    harness = G.counts(p)
    for sid, row in c["sources"].items():
        assert row["unparseable"] == 0 and row["duplicate_key"] == 0, sid
        if sid == "pkm.artifact":
            assert row["parsed"] == harness["pkm.artifact"]["meta_json_files"] == 1
        elif sid == "pkm.demand":
            assert row["parsed"] == harness["pkm.demand"]["lines"] == 1
            assert row["file_day_mismatch"] == 0
        else:
            assert row["parsed"] == harness[sid].get("parsed", 0), sid
    assert LEDGER_MARKER not in out.getvalue()


def test_census_flags_unparseable_and_duplicate_key_lines_as_non_events(
        ledger_kb: tuple[Path, G.Paths]) -> None:
    _root, p = ledger_kb
    with p.labels.open("a", encoding="utf-8") as fh:
        fh.write("\n")                                    # blank: skipped by every reader
        fh.write("{not json\n")                           # unparseable
        fh.write('{"question_id": "q-9", "question_id": "q-8", "value": "v", '
                 '"verdict": "correct"}\n')                # duplicate key
    sc = SRC.scan("eval.labels", p)
    assert len(sc.parsed) == 2 and sc.unparseable == 1 and sc.duplicate_key == 1 and sc.blank == 1
    assert sc.unparseable_locators == ("labels.jsonl:4", "labels.jsonl:5:duplicate_key")
    # a tasks line the legacy reader would skip is unparseable here too
    with p.tasks_ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "asserted"}) + "\n")   # no identity → TEV._from_json None
    sc = SRC.scan("act.tasks", p)
    assert len(sc.parsed) == 4 and sc.unparseable == 1


def test_envelope_rules_per_source(ledger_kb: tuple[Path, G.Paths]) -> None:
    _root, p = ledger_kb
    tasks = SRC.scan("act.tasks", p).parsed
    assert [t.author for t in tasks] == ["owner", "owner", "owner", "owner"]
    assert tasks[0].kernel_id == "owner:command" and tasks[0].tx_time is None   # naive local
    assert tasks[0].recorded_draw == {"kind": "uuid", "ref": tasks[0].output}   # new_identity()
    assert tasks[1].recorded_draw is None                                        # amended
    trips = SRC.scan("act.trips", p).parsed
    assert trips[0].author == "world" and trips[0].kernel_id == "trips.ingest:kayak-api"
    assert trips[0].inputs == ("s1",) and trips[0].output == "res-1"
    dec = SRC.scan("calibration.decisions", p).parsed
    assert dec[0].author == "agent" and dec[0].kernel_id == "decide:lookup"
    assert dec[0].output == "a" * 64 and dec[0].tx_time == "2026-01-01T00:00:01+00:00"
    rx = SRC.scan("calibration.reactions", p).parsed
    assert rx[0].author == "owner" and rx[0].inputs == ("a" * 64,)
    oc = SRC.scan("calibration.outcomes", p).parsed
    assert oc[0].kernel_id.startswith("grader:eval_edge:sha256:") and oc[0].inputs == ("l1",)
    lab = SRC.scan("eval.labels", p).parsed
    assert lab[0].tx_time_raw == "" and lab[0].tx_time is None and lab[0].author == "owner"
    el = SRC.scan("utility.elicitations", p).parsed
    assert el[0].kernel_id == "owner:elicitation"
    art = SRC.scan("pkm.artifact", p).parsed
    assert art[0].author == "agent" and art[0].kernel_id.startswith("instrument:sha256:")
    assert art[0].output == "a" * 64 and set(art[0].inputs) == {"d" * 64, "e" * 64}
    assert art[0].recorded_draw == {"kind": "content", "ref": "a" * 64}
    assert art[0].tx_time == "2026-01-01T00:00:00+00:00"                        # naive UTC
    dem = SRC.scan("pkm.demand", p).parsed
    assert dem[0].kernel_id == "derive:doc_date" and dem[0].inputs == ("e" * 64,)
    assert dem[0].output == ""


def test_utc_annotation_per_clock() -> None:
    assert SRC.utc_annotation("2026-01-01T00:00:00", "naive-local") is None
    assert SRC.utc_annotation("2026-01-01T00:00:00", "naive-utc") == "2026-01-01T00:00:00+00:00"
    assert SRC.utc_annotation("2026-01-01T00:00:00Z", "aware") == "2026-01-01T00:00:00+00:00"
    assert SRC.utc_annotation("2026-01-01T02:00:00+02:00", "aware") == "2026-01-01T00:00:00+00:00"
    assert SRC.utc_annotation("2026-01-01T00:00:00", "aware") is None    # unexpected naive
    assert SRC.utc_annotation("", "aware") is None and SRC.utc_annotation("x", "aware") is None


def test_instrument_kernel_id_namespace_and_completeness() -> None:
    base = {"producer_name": "p", "producer_version": "1", "producer_config_hash": "c" * 64}
    k1, ok1 = SRC.instrument_kernel_id({**base})
    assert k1.startswith("instrument:sha256:") and ok1
    k2, ok2 = SRC.instrument_kernel_id({**base, "cache_key_schema_version": 2,
                                        "producer_metadata": {"model_identity": {"m": 1},
                                                              "prompt_hash": "a" * 64}})
    assert ok2 and k2 != k1
    k3, ok3 = SRC.instrument_kernel_id({**base, "cache_key_schema_version": 3,
                                        "producer_metadata": {"inputs": {}}})
    assert not ok3 and k3 not in (k1, k2)      # the §18.9 shape: recorded-subset digest


def test_migrate_all_then_rerun_is_a_noop_and_legacy_untouched(
        ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    before = {n: f.read_bytes() for n, f in p.legacy_files().items()}
    store = _store(root)
    out = io.StringIO()
    res = M.migrate(p, store, out=out, epoch="E0")
    assert store.manifest()["epoch"] == "E0"
    for r in res:
        assert r.written == r.parsed and r.after == r.parsed and r.skipped == 0, r
        assert store.parseable_count(r.source_id) == r.parsed
    assert LEDGER_MARKER not in out.getvalue()
    res2 = M.migrate(p, store, out=io.StringIO(), epoch="E1")
    assert all(r.written == 0 and r.skipped == r.parsed for r in res2)
    assert store.manifest()["epoch"] == "E0"                        # set once
    assert {n: f.read_bytes() for n, f in p.legacy_files().items()} == before
    m = store.manifest()["sources"]
    assert m["act.tasks"]["parsed"] == 4 and m["act.tasks"]["writer_tally"] == 4
    # the two-route counts reconcile
    c = M.counts(p, store, out=io.StringIO())
    assert c["ok"] and all(r["writer_tally"] == r["segment_parseable"] == r["legacy_parsed"]
                           for r in c["sources"].values())


def test_sync_appends_the_legacy_tail_and_is_loud_on_a_rewritten_prefix(
        ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    store = _store(root)
    M.migrate(p, store, sources=("eval.labels",), out=io.StringIO(), epoch="E0")
    with p.labels.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"question_id": "q-002", "value": "v", "verdict": "wrong"}) + "\n")
    r = M.sync(p, store, sources=("eval.labels",), out=io.StringIO())[0]
    assert r.before == 2 and r.written == 1 and r.after == 3
    ev = store.read("eval.labels")
    assert [e.seq for e in ev] == [1, 2, 3] and ev[-1].record["question_id"] == "q-002"
    # a legacy store whose prefix disagrees with the stream (rewritten, not appended): loud
    lines = p.labels.read_text(encoding="utf-8").splitlines()
    lines[0] = json.dumps({"question_id": "q-001", "value": "changed", "verdict": "wrong"})
    p.labels.write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")
    with pytest.raises(LedgerConflictError):
        M.migrate(p, store, sources=("eval.labels",), out=io.StringIO())
    # sync checks the last occupied ordinal only — a rewrite there is loud too
    lines[-1] = json.dumps({"question_id": "q-002", "value": "changed", "verdict": "wrong"})
    p.labels.write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")
    with pytest.raises(LedgerConflictError):
        M.sync(p, store, sources=("eval.labels",), out=io.StringIO())


def test_pkm_artifact_sweep_dedups_by_identity(ledger_kb: tuple[Path, G.Paths]) -> None:
    root, p = ledger_kb
    store = _store(root)
    M.migrate(p, store, sources=("pkm.artifact",), out=io.StringIO(), epoch="E0")
    assert store.parseable_count("pkm.artifact") == 1
    # a new artefact with an EARLIER produced_at: appended after (sweep order), never conflicts
    assert p.pkm_root is not None
    key = "9" * 64
    meta_file(p.pkm_root, key).parent.mkdir(parents=True)
    meta_file(p.pkm_root, key).write_text(json.dumps({
        "format_version": 1, "cache_key": key, "input_hash": "1" * 64,
        "producer_name": "email", "producer_version": "1", "producer_config_hash": "2" * 64,
        "status": "success", "produced_at": "2025-01-01T00:00:00", "size_bytes": 1,
        "error_message": None, "content_type": "text/plain", "content_encoding": "utf-8",
        "producer_metadata": {}}), encoding="utf-8")
    r = M.sync(p, store, sources=("pkm.artifact",), out=io.StringIO())[0]
    assert r.written == 1 and r.skipped == 1 and r.after == 2
    ev = store.read("pkm.artifact")
    assert ev[1].output == key and ev[1].seq == 2 and ev[1].recorded_draw is None   # schema 1
    r = M.sync(p, store, sources=("pkm.artifact",), out=io.StringIO())[0]
    assert r.written == 0


def test_cli_smoke_census_migrate_counts(ledger_kb: tuple[Path, G.Paths],
                                        monkeypatch: pytest.MonkeyPatch,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    root, p = ledger_kb
    monkeypatch.setattr(M.Paths, "from_config", classmethod(lambda cls: p))
    monkeypatch.setattr(M.config, "KB", root)
    assert M.main(["census", "--write", str(root / "ledger" / "census.json")]) == 0
    assert (root / "ledger" / "census.json").exists()
    assert M.main(["migrate", "act.tasks"]) == 0
    assert M.main(["sync", "all"]) == 0
    assert M.main(["counts", "--baseline", str(root / "ledger" / "census.json")]) == 0
    monkeypatch.setenv(M.MIRROR_ENV, "0")
    assert M.main(["sync", "all"]) == 2
    out = capsys.readouterr().out
    assert LEDGER_MARKER not in out and "all sources reconcile" in out
    # census --write outside $LIFE_AGENT_KB/ledger/ is refused (S1)
    with pytest.raises(SystemExit):
        M.main(["census", "--write", str(root / "elsewhere.json")])


def test_paths_state_sha_source_defaults_to_the_ledger(ledger_kb: tuple[Path, G.Paths]) -> None:
    _root, p = ledger_kb
    a = G.a2_state_md(p)
    b = G.a2_state_md(replace(p, state_sha_source=p.tasks_ledger))
    assert a == b
