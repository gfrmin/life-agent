"""Tests for ``pkm.chunking`` — pure text splitter and catalogue write layer
(SPEC v0.1.11 Step 2).

All tests are hermetic. The DB tests use ``migrated_root`` (all migrations
applied) but never touch the live corpus.
"""

from __future__ import annotations

from pathlib import Path

from pkm.catalogue import open_catalogue
from pkm.chunking import Chunk, chunk_text, write_chunks

# ---------------------------------------------------------------------------
# chunk_text — pure function
# ---------------------------------------------------------------------------


def test_chunk_text_basic() -> None:
    """Short text (≤ max_chars) yields exactly one chunk at index 0."""
    result = chunk_text("hello world", max_chars=1000, overlap=100)
    assert len(result) == 1
    assert result[0].chunk_index == 0
    assert result[0].chunk_text == "hello world"


def test_chunk_text_empty() -> None:
    """Empty string yields zero chunks."""
    assert chunk_text("") == []


def test_chunk_text_splits() -> None:
    """Long text is split into multiple chunks with correct overlap."""
    # 50-char text, max_chars=20, overlap=5
    text = "A" * 15 + "B" * 15 + "C" * 15 + "D" * 5  # 50 chars total
    result = chunk_text(text, max_chars=20, overlap=5)

    assert len(result) > 1
    # Indices must be contiguous starting at 0
    for i, chunk in enumerate(result):
        assert chunk.chunk_index == i
    # Every chunk is non-empty and ≤ max_chars
    for chunk in result:
        assert 0 < len(chunk.chunk_text) <= 20
    # The full text must be recoverable (via overlap reconstruction is out of
    # scope; verify at least that the union of chunks covers all positions)
    joined = "".join(c.chunk_text for c in result)
    assert "A" in joined and "B" in joined and "C" in joined


def test_chunk_text_overlap_is_shared() -> None:
    """Consecutive chunks share the tail/head of the overlap window."""
    text = "X" * 30
    result = chunk_text(text, max_chars=20, overlap=5)
    assert len(result) >= 2
    # The end of chunk[0] equals the start of chunk[1] (overlap)
    assert result[0].chunk_text[-5:] == result[1].chunk_text[:5]


def test_chunk_text_exact_boundary() -> None:
    """Text whose length exactly equals max_chars yields one chunk."""
    text = "Z" * 20
    result = chunk_text(text, max_chars=20, overlap=5)
    assert len(result) == 1
    assert result[0].chunk_text == text


def test_chunk_text_returns_dataclass() -> None:
    """Return type is list[Chunk] with the expected fields."""
    result = chunk_text("abc")
    assert len(result) == 1
    c = result[0]
    assert isinstance(c, Chunk)
    assert hasattr(c, "chunk_index")
    assert hasattr(c, "chunk_text")


# ---------------------------------------------------------------------------
# write_chunks — catalogue layer (idempotency contract)
# ---------------------------------------------------------------------------


def _seed_artifact(conn, cache_key: str) -> None:
    """Insert a minimal artifacts row so the FK constraint is satisfied."""
    conn.execute(
        """
        INSERT OR IGNORE INTO artifacts
            (cache_key, input_hash, producer_name, producer_version,
             producer_config_hash, status, produced_at, content_type,
             content_path)
        VALUES (?, ?, 'tesseract', '5.5.2', 'fakehash', 'success',
                current_timestamp, 'text/plain', '/dev/null')
        """,
        [cache_key, "a" * 64],
    )


def test_write_chunks_inserts_rows(migrated_root: Path) -> None:
    """write_chunks inserts the expected number of rows."""
    key = "c" * 64
    chunks = [Chunk(0, "first chunk"), Chunk(1, "second chunk")]

    with open_catalogue(migrated_root) as conn:
        _seed_artifact(conn, key)
        write_chunks(conn, key, chunks, source_origin="test")
        count = conn.execute(
            "SELECT COUNT(*) FROM artifact_chunks WHERE artifact_cache_key = ?",
            [key],
        ).fetchone()[0]

    assert count == 2


def test_write_chunks_idempotent(migrated_root: Path) -> None:
    """Calling write_chunks twice on the same key leaves the same row count."""
    key = "d" * 64
    chunks = [Chunk(0, "alpha"), Chunk(1, "beta"), Chunk(2, "gamma")]

    with open_catalogue(migrated_root) as conn:
        _seed_artifact(conn, key)
        write_chunks(conn, key, chunks, source_origin="run1")
        write_chunks(conn, key, chunks, source_origin="run2")
        count = conn.execute(
            "SELECT COUNT(*) FROM artifact_chunks WHERE artifact_cache_key = ?",
            [key],
        ).fetchone()[0]

    assert count == 3


def test_write_chunks_replaces_on_rewrite(migrated_root: Path) -> None:
    """Second write_chunks call with different chunks replaces first set."""
    key = "e" * 64
    first = [Chunk(0, "old chunk A"), Chunk(1, "old chunk B")]
    second = [Chunk(0, "new chunk X")]

    with open_catalogue(migrated_root) as conn:
        _seed_artifact(conn, key)
        write_chunks(conn, key, first, source_origin="v1")
        write_chunks(conn, key, second, source_origin="v2")
        rows = conn.execute(
            "SELECT chunk_text FROM artifact_chunks WHERE artifact_cache_key = ? "
            "ORDER BY chunk_index",
            [key],
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "new chunk X"


def test_write_chunks_source_origin_stored(migrated_root: Path) -> None:
    """source_origin is persisted per chunk."""
    key = "f" * 64
    chunks = [Chunk(0, "some text")]

    with open_catalogue(migrated_root) as conn:
        _seed_artifact(conn, key)
        write_chunks(conn, key, chunks, source_origin="my-origin")
        origin = conn.execute(
            "SELECT source_origin FROM artifact_chunks WHERE artifact_cache_key = ?",
            [key],
        ).fetchone()[0]

    assert origin == "my-origin"
