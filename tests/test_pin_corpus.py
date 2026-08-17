"""Unit tests for corpus pinning (scripts/corpus/pin_corpus.py).

Hermetic: in-memory DuckDB standing in for the catalogue, tmp_path as the KB.

The properties that matter are (a) a manifest re-hashes to its own recorded digest — it is
identity, not a label — and (b) a pinned name is immutable, because every gate run that
cites a name is relying on it meaning one universe forever.

Run from the repo root:
    uv run --project . python -m pytest ./tests/test_pin_corpus.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from corpus import pin_corpus as P

from life_agent.core.corpus import corpus_digest


def _catalogue(chunks: list[tuple[str, int]]) -> duckdb.DuckDBPyConnection:
    """(artifact_cache_key, chunk_index) rows, plus the sibling tables the manifest reads."""
    conn = duckdb.connect(":memory:")
    conn.execute(
        "CREATE TABLE artifact_chunks (artifact_cache_key VARCHAR, chunk_index INTEGER)"
    )
    for key, idx in chunks:
        conn.execute("INSERT INTO artifact_chunks VALUES (?, ?)", [key, idx])
    conn.execute("CREATE TABLE sources (source_id VARCHAR)")
    conn.execute("INSERT INTO sources VALUES ('s1'), ('s2')")
    # Mirrors pkm migration 0001: the column is `schema_version`, not `version`.
    conn.execute(
        "CREATE TABLE schema_meta (schema_version INTEGER, migration_id VARCHAR)"
    )
    conn.execute(
        "INSERT INTO schema_meta VALUES (4, '0004_chunks_and_embeddings.py'), "
        "(5, '0005_chunk_surrogate_key.py')"
    )
    return conn


@pytest.fixture(autouse=True)
def _kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFE_AGENT_KB", str(tmp_path))


def _build(conn: duckdb.DuckDBPyConnection, tmp_path: Path, name: str = "v1") -> dict:
    fake_catalogue = tmp_path / "catalogue.duckdb"
    fake_catalogue.write_bytes(b"x" * 11)
    return P.build_manifest(conn, name=name, catalogue=fake_catalogue)


def test_manifest_rehashes_to_its_own_digest(tmp_path: Path) -> None:
    """The self-verification property: the recorded key list IS what corpus_digest hashes,
    so a manifest can be checked without the catalogue that produced it."""
    conn = _catalogue([("aaa", 0), ("aaa", 1), ("bbb", 0)])
    m = _build(conn, tmp_path)
    assert P.self_digest(m) == m["corpus_digest"] == corpus_digest(conn)
    assert (m["n_artifacts"], m["n_chunks"]) == (2, 3)
    assert m["artifacts"] == ["aaa", "bbb"]      # sorted distinct
    assert m["chunk_counts"] == [2, 1]           # index-aligned
    assert m["catalogue_schema_version"] == 5


def test_manifest_records_provenance_but_does_not_hash_it(tmp_path: Path) -> None:
    """A corpus is defined by its content, not by which box or path held it — so moving the
    store must not change the identity."""
    conn = _catalogue([("aaa", 0)])
    here = _build(conn, tmp_path)
    elsewhere = tmp_path / "moved" / "catalogue.duckdb"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(b"x" * 11)
    there = P.build_manifest(conn, name="v1", catalogue=elsewhere)
    assert here["catalogue_path"] != there["catalogue_path"]
    assert here["corpus_digest"] == there["corpus_digest"]


def test_pin_writes_then_refuses_to_repoint_the_name(tmp_path: Path, capsys) -> None:
    """A named version is immutable: re-pointing it would silently invalidate every run
    that cited the name."""
    conn = _catalogue([("aaa", 0)])
    P.manifest_dir().mkdir(parents=True)
    m = _build(conn, tmp_path, name="frozen")
    P.manifest_path("frozen").write_text(json.dumps(m), encoding="utf-8")

    grown = _catalogue([("aaa", 0), ("ccc", 0)])
    args = type("A", (), {"name": "frozen", "note": "",
                          "config": str(tmp_path / "pkm.yaml")})()
    (tmp_path / "pkm.yaml").write_text(f"root_dir: {tmp_path}\n", encoding="utf-8")
    monkey = P.duckdb.connect
    try:
        P.duckdb.connect = lambda *a, **k: grown  # type: ignore[assignment]
        with pytest.raises(SystemExit, match="already pinned to a DIFFERENT corpus"):
            P.cmd_pin(args)
    finally:
        P.duckdb.connect = monkey  # type: ignore[assignment]


def test_repinning_an_identical_corpus_is_a_no_op(tmp_path: Path) -> None:
    """Idempotent: re-running the pin after no corpus change must not error."""
    conn = _catalogue([("aaa", 0)])
    P.manifest_dir().mkdir(parents=True)
    m = _build(conn, tmp_path, name="frozen")
    P.manifest_path("frozen").write_text(json.dumps(m), encoding="utf-8")

    args = type("A", (), {"name": "frozen", "note": "",
                          "config": str(tmp_path / "pkm.yaml")})()
    (tmp_path / "pkm.yaml").write_text(f"root_dir: {tmp_path}\n", encoding="utf-8")
    monkey = P.duckdb.connect
    try:
        P.duckdb.connect = lambda *a, **k: conn  # type: ignore[assignment]
        assert P.cmd_pin(args) == 0
    finally:
        P.duckdb.connect = monkey  # type: ignore[assignment]


def test_key_diff_names_what_moved(tmp_path: Path) -> None:
    """The payoff a manifest buys over a bare digest: not just THAT it changed, but what."""
    a = _build(_catalogue([("aaa", 0), ("bbb", 0)]), tmp_path)
    b = _build(_catalogue([("bbb", 0), ("ccc", 0)]), tmp_path)
    assert P.key_diff(a, b) == (["ccc"], ["aaa"])


def test_a_moved_or_deleted_source_does_not_change_the_pin(tmp_path: Path) -> None:
    """Corpus identity is chunk-level. pkm has no tombstones (SPEC §13.2) and a move is a
    metadata event, so neither can move the digest — only ADDING chunked artifacts can."""
    conn = _catalogue([("aaa", 0), ("bbb", 0)])
    before = _build(conn, tmp_path)
    conn.execute("UPDATE sources SET source_id = 'relocated' WHERE source_id = 's1'")
    conn.execute("DELETE FROM sources WHERE source_id = 's2'")
    after = _build(conn, tmp_path)
    assert before["corpus_digest"] == after["corpus_digest"]
