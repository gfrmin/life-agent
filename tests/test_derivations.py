"""life_agent.core.derivations — file-first ask-stage derivations (pkm SPEC §18.9).

Hermetic: tmp knowledge roots, no LLM, no live catalogue. Covers the key contract
(determinism + exact invalidation per input), the file-first write (write-once,
pkm-shaped meta/lineage files, pending queue), and catalogue reconciliation
(idempotent row inserts preserving produced_at; lock/absence degrades to a no-op).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.core import derivations as D
from pkm.cache import content_file, lineage_file, meta_file
from pkm.catalogue import open_catalogue, run_migrations

Q = "how do i make money"


def _expand_key(question: str = Q, *, model: str = "claude-haiku-4-5-20251001",
                template: str = "EXPAND PROMPT") -> D.StageKey:
    return D.expand_key(question, model=model, prompt_template=template,
                        temperature=0.0, max_tokens=120)


def _synth_key(question: str = Q, rs_hash: str = "c" * 64, profile_hash: str = "d" * 64,
               *, template: str = "ANSWER PROMPT") -> D.StageKey:
    return D.synthesize_key(question, rs_hash, profile_hash,
                            model="claude-sonnet-4-6", prompt_template=template,
                            temperature=0.0, max_tokens=600)


# --- key contract: determinism + exact invalidation ------------------------- #

def test_keys_are_deterministic() -> None:
    assert _expand_key().cache_key == _expand_key().cache_key
    assert _synth_key().cache_key == _synth_key().cache_key
    assert (D.retrieve_key("q terms", "e" * 64, k=8).cache_key
            == D.retrieve_key("q terms", "e" * 64, k=8).cache_key)


def test_expand_key_sensitivity() -> None:
    base = _expand_key().cache_key
    assert _expand_key(question="other?").cache_key != base
    assert _expand_key(model="claude-haiku-9").cache_key != base
    assert _expand_key(template="DIFFERENT PROMPT").cache_key != base


def test_retrieve_key_sensitivity() -> None:
    base = D.retrieve_key("q terms", "e" * 64, k=8).cache_key
    assert D.retrieve_key("q OTHER", "e" * 64, k=8).cache_key != base   # query changed
    assert D.retrieve_key("q terms", "f" * 64, k=8).cache_key != base   # corpus changed
    assert D.retrieve_key("q terms", "e" * 64, k=12).cache_key != base  # k changed


def test_synthesize_key_sensitivity_is_exact() -> None:
    base = _synth_key().cache_key
    assert _synth_key(question="other?").cache_key != base
    assert _synth_key(rs_hash="9" * 64).cache_key != base       # different evidence
    assert _synth_key(profile_hash="8" * 64).cache_key != base  # owner taught a fact
    assert _synth_key(template="NEW PROMPT").cache_key != base
    # and nothing else: same inputs replay the same key (early cutoff depends on this)
    assert _synth_key().cache_key == base


def test_stage_content_types_are_distinct_and_never_chunkable() -> None:
    from pkm.chunking import CHUNKABLE_CONTENT_TYPES

    stage_types = {D.CONTENT_TYPE_EXPAND, D.CONTENT_TYPE_RETRIEVAL_SET, D.CONTENT_TYPE_ANSWER}
    assert len(stage_types) == 3
    # the SPEC §18.9 retrieval gate: ask artifacts must be invisible to chunking/FTS
    assert not stage_types & CHUNKABLE_CONTENT_TYPES


# --- file-first record / lookup --------------------------------------------- #

def test_record_then_lookup_roundtrip(tmp_path: Path) -> None:
    key = _expand_key()
    assert D.lookup(tmp_path, key.cache_key) is None
    assert D.record(tmp_path, key, b"income salary invoice", lineage=[]) is True
    assert D.lookup(tmp_path, key.cache_key) == b"income salary invoice"


def test_record_is_write_once(tmp_path: Path) -> None:
    key = _expand_key()
    assert D.record(tmp_path, key, b"first", lineage=[]) is True
    assert D.record(tmp_path, key, b"second", lineage=[]) is False
    assert D.lookup(tmp_path, key.cache_key) == b"first"  # the recorded derivation stands
    queue = (tmp_path / "external" / "pending.txt").read_text()
    assert queue.split() == [key.cache_key]  # queued exactly once


def test_record_writes_pkm_shaped_meta_and_lineage(tmp_path: Path) -> None:
    key = _synth_key()
    lineage = [{"cache_key": "1" * 64, "role": "retrieval_set"},
               {"cache_key": "2" * 64, "role": "source"}]
    D.record(tmp_path, key, b"the answer [1]", lineage=lineage,
             metadata={"served_model": ""})

    meta = json.loads(meta_file(tmp_path, key.cache_key).read_text())
    assert meta["producer_name"] == "life_agent.ask.synthesize"
    assert meta["status"] == "success"
    assert meta["input_hash"] == key.input_hash
    assert meta["content_type"] == D.CONTENT_TYPE_ANSWER
    assert meta["cache_key_schema_version"] == 3
    assert meta["size_bytes"] == len(b"the answer [1]")
    # provenance stays jq-inspectable: the pre-hash inputs are in the meta
    assert meta["producer_metadata"]["inputs"] == {
        "profile": "d" * 64, "question": Q, "retrieval_set": "c" * 64}

    lin = json.loads(lineage_file(tmp_path, key.cache_key).read_text())
    assert lin == {"format_version": 1, "inputs": lineage}


def test_record_refuses_duplicate_lineage_inputs_and_writes_nothing(tmp_path: Path) -> None:
    """§18.4/§18.9 enforced at the seam: the catalogue's ``artifact_lineage`` key is
    (artifact, input), so a repeated input can never be registered — refuse it where the
    file would be written (a writer bug surfaces in that writer's tests, not in a sweep two
    months later). Nothing is written: no directory, no queue line."""
    key = _synth_key()
    dup = [{"cache_key": "1" * 64, "role": "retrieval_set"},
           {"cache_key": "2" * 64, "role": "source"},
           {"cache_key": "2" * 64, "role": "source"}]           # the same input twice
    with pytest.raises(ValueError, match="duplicate lineage input"):
        D.record(tmp_path, key, b"the answer [1]", lineage=dup)
    assert not meta_file(tmp_path, key.cache_key).parent.exists()   # no directory at all
    assert not (tmp_path / "external" / "pending.txt").exists()      # no queue line
    assert D.lookup(tmp_path, key.cache_key) is None
    # the same input under two ROLES is still one (artifact, input) key — refused too
    two_roles = [{"cache_key": "2" * 64, "role": "source"},
                 {"cache_key": "2" * 64, "role": "retrieval_set"}]
    with pytest.raises(ValueError, match="duplicate lineage input"):
        D.record(tmp_path, key, b"the answer [1]", lineage=two_roles)
    assert not meta_file(tmp_path, key.cache_key).parent.exists()


def test_lookup_misses_on_half_written_artifact(tmp_path: Path) -> None:
    # meta.json is the commit marker: content without meta must read as a miss
    key = _expand_key()
    cf = content_file(tmp_path, key.cache_key)
    cf.parent.mkdir(parents=True)
    cf.write_bytes(b"orphan content")
    assert D.lookup(tmp_path, key.cache_key) is None


# --- catalogue reconciliation ------------------------------------------------ #

@pytest.fixture
def migrated(tmp_path: Path) -> Path:
    (tmp_path / "cache").mkdir()
    run_migrations(tmp_path)
    return tmp_path


def test_reconcile_inserts_rows_and_drains_queue(migrated: Path) -> None:
    key = _synth_key()
    lineage = [{"cache_key": "1" * 64, "role": "retrieval_set"}]
    D.record(migrated, key, b"answer", lineage=lineage)
    recorded_meta = json.loads(meta_file(migrated, key.cache_key).read_text())

    assert D.reconcile(migrated) == 1

    with open_catalogue(migrated) as conn:
        row = conn.execute(
            "SELECT producer_name, status, content_type, produced_at "
            "FROM artifacts WHERE cache_key = ?", [key.cache_key]).fetchone()
        assert row is not None
        assert row[0] == "life_agent.ask.synthesize"
        assert row[1] == "success"
        assert row[2] == D.CONTENT_TYPE_ANSWER
        assert row[3].isoformat() == recorded_meta["produced_at"]  # produced_at preserved
        edges = conn.execute(
            "SELECT input_cache_key, role FROM artifact_lineage "
            "WHERE artifact_cache_key = ?", [key.cache_key]).fetchall()
        assert edges == [("1" * 64, "retrieval_set")]

    assert (migrated / "external" / "pending.txt").read_text() == ""
    assert D.reconcile(migrated) == 0  # drained queue: nothing to do


def test_reconcile_is_idempotent_when_row_exists(migrated: Path) -> None:
    key = _expand_key()
    D.record(migrated, key, b"terms", lineage=[])
    assert D.reconcile(migrated) == 1
    # re-queue the same key (e.g. a lost rewrite race): row exists, key is dropped
    queue = migrated / "external" / "pending.txt"
    queue.write_text(key.cache_key + "\n")
    assert D.reconcile(migrated) == 0
    assert queue.read_text() == ""
    with open_catalogue(migrated) as conn:
        (n,) = conn.execute("SELECT count(*) FROM artifacts WHERE cache_key = ?",
                            [key.cache_key]).fetchone()
        assert n == 1


def test_reconcile_noop_without_catalogue(tmp_path: Path) -> None:
    key = _expand_key()
    D.record(tmp_path, key, b"terms", lineage=[])
    assert D.reconcile(tmp_path) == 0
    # queue intact: the files stay authoritative until a catalogue appears
    assert (tmp_path / "external" / "pending.txt").read_text().split() == [key.cache_key]
    assert not (tmp_path / "catalogue.duckdb").exists()  # reconcile must not create one


def test_reconcile_keeps_half_written_keys_queued(migrated: Path) -> None:
    ghost = "f" * 64  # queued but no files on disk (mid-write by another process)
    queue = migrated / "external"
    queue.mkdir()
    (queue / "pending.txt").write_text(ghost + "\n")
    assert D.reconcile(migrated) == 0
    assert (queue / "pending.txt").read_text().split() == [ghost]


def test_reconcile_walk_reaches_sources_via_lineage(migrated: Path) -> None:
    """The provenance the north star demands: answer → retrieval set → cited cards,
    walkable in SQL once reconciled."""
    rs_key = D.retrieve_key("q terms", "e" * 64, k=8)
    card = "9" * 64
    D.record(migrated, rs_key, b'{"hits": []}',
             lineage=[{"cache_key": card, "role": "retrieved"}])
    ans_key = _synth_key(rs_hash=D.content_hash(b'{"hits": []}'))
    D.record(migrated, ans_key, b"answer",
             lineage=[{"cache_key": rs_key.cache_key, "role": "retrieval_set"},
                      {"cache_key": card, "role": "source"}])
    assert D.reconcile(migrated) == 2

    with open_catalogue(migrated) as conn:
        hop1 = {r[0] for r in conn.execute(
            "SELECT input_cache_key FROM artifact_lineage WHERE artifact_cache_key = ?",
            [ans_key.cache_key]).fetchall()}
        assert hop1 == {rs_key.cache_key, card}
        hop2 = {r[0] for r in conn.execute(
            "SELECT input_cache_key FROM artifact_lineage WHERE artifact_cache_key = ?",
            [rs_key.cache_key]).fetchall()}
        assert hop2 == {card}


# --- confirm key (value-targeted independent confirmation — §14 confirm_indep) ---------- #

def _confirm_key(question: str = "what is the fee?", chunk: str = "c" * 64,
                 value: str = "1,234,567") -> D.StageKey:
    return D.lookup_confirm_key(
        question, chunk, value, model="claude-haiku-4-5-20251001",
        prompt_template="P", engine_version="e/1",
        output_schema={"type": "object"})


def test_lookup_confirm_key_sensitivity() -> None:
    base = _confirm_key().cache_key
    assert _confirm_key().cache_key == base                      # deterministic
    assert _confirm_key(question="other?").cache_key != base
    assert _confirm_key(chunk="d" * 64).cache_key != base
    # two target values over ONE chunk must never share a cache cell
    assert _confirm_key(value="7,654,321").cache_key != base
    # and the confirm namespace is disjoint from the extract namespace over the
    # same (question, chunk) — different producer + prompt identity
    ek = D.lookup_extract_key("what is the fee?", "c" * 64,
                              model="claude-haiku-4-5-20251001", prompt_template="P",
                              engine_version="e/1", output_schema={"type": "object"})
    assert ek.cache_key != base
