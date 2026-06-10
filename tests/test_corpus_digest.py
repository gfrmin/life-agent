"""corpus_digest — the identity of what FTS retrieval can see (life_agent.core.corpus).

Hermetic: an in-memory DuckDB with a minimal ``artifact_chunks`` table; no LLM, no live
catalogue. The digest is the corpus half of the cached-ask keys, so its contract is
load-bearing: equal corpora must hash equal (insertion-order independent), and any change
to the chunk set must change the hash.
"""
from __future__ import annotations

import duckdb
import pytest

from life_agent.core.corpus import corpus_digest

KEY_A = "a" * 64
KEY_B = "b" * 64


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect(":memory:")
    c.execute(
        "CREATE TABLE artifact_chunks ("
        " chunk_id INTEGER, artifact_cache_key VARCHAR,"
        " chunk_text VARCHAR, source_origin VARCHAR)"
    )
    return c


def _insert(c: duckdb.DuckDBPyConnection, chunk_id: int, key: str, text: str) -> None:
    c.execute("INSERT INTO artifact_chunks VALUES (?, ?, ?, ?)", [chunk_id, key, text, "live"])


def test_digest_is_64_hex_and_deterministic(conn: duckdb.DuckDBPyConnection) -> None:
    _insert(conn, 1, KEY_A, "x")
    d1, d2 = corpus_digest(conn), corpus_digest(conn)
    assert d1 == d2
    assert len(d1) == 64 and all(ch in "0123456789abcdef" for ch in d1)


def test_digest_is_insertion_order_independent(conn: duckdb.DuckDBPyConnection) -> None:
    _insert(conn, 1, KEY_B, "x")
    _insert(conn, 2, KEY_A, "y")
    d_ba = corpus_digest(conn)

    other = duckdb.connect(":memory:")
    other.execute(
        "CREATE TABLE artifact_chunks ("
        " chunk_id INTEGER, artifact_cache_key VARCHAR,"
        " chunk_text VARCHAR, source_origin VARCHAR)"
    )
    _insert(other, 2, KEY_A, "y")
    _insert(other, 1, KEY_B, "x")
    assert corpus_digest(other) == d_ba


def test_digest_changes_when_an_artifact_is_added(conn: duckdb.DuckDBPyConnection) -> None:
    _insert(conn, 1, KEY_A, "x")
    before = corpus_digest(conn)
    _insert(conn, 2, KEY_B, "y")
    assert corpus_digest(conn) != before


def test_digest_changes_when_chunk_count_changes_same_artifacts(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    # a re-chunk of the SAME artifact set must still change the digest (chunk count term)
    _insert(conn, 1, KEY_A, "x")
    before = corpus_digest(conn)
    _insert(conn, 2, KEY_A, "x continued")
    assert corpus_digest(conn) != before


def test_digest_of_empty_corpus_is_stable(conn: duckdb.DuckDBPyConnection) -> None:
    assert corpus_digest(conn) == corpus_digest(conn)
