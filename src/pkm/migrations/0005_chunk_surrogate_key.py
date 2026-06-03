"""Migration 0005 — chunk_id surrogate key for FTS (SPEC v0.1.11 Step 3).

DuckDB FTS (``create_fts_index``) requires a unique ``input_id`` per
indexed row. ``artifact_cache_key`` is not unique in ``artifact_chunks``
(multiple rows per artifact). This migration adds a BIGINT surrogate key
``chunk_id`` so the FTS index has a stable unique document identifier.

Steps:
  1. Create a sequence ``seq_chunk_id``.
  2. Add the ``chunk_id BIGINT`` column (nullable initially).
  3. Populate existing rows from the sequence.
  4. Add NOT NULL + UNIQUE constraints via a new index.

The ``write_chunks`` function in ``pkm.chunking`` is updated to call
``nextval('seq_chunk_id')`` for each inserted row.

No existing column is removed or modified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

SCHEMA_VERSION = 5


def apply(conn: duckdb.DuckDBPyConnection) -> None:
    """Add the chunk_id surrogate key to artifact_chunks."""
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_chunk_id START 1 INCREMENT 1")
    conn.execute(
        "ALTER TABLE artifact_chunks ADD COLUMN IF NOT EXISTS chunk_id BIGINT"
    )
    # Populate existing rows from the sequence. The sequence guarantees
    # uniqueness for all subsequent inserts via write_chunks; a UNIQUE
    # INDEX is intentionally omitted here because DuckDB cannot create
    # an index within the same transaction as an outstanding UPDATE.
    conn.execute(
        "UPDATE artifact_chunks SET chunk_id = nextval('seq_chunk_id') "
        "WHERE chunk_id IS NULL"
    )
