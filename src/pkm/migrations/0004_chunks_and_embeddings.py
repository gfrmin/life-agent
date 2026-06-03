"""Migration 0004 — chunks + embeddings substrate (SPEC v0.3.0 §33).

Adds the storage shape for the retrieval substrate:

  - ``artifact_chunks``: per-derivation chunks with text, an optional
    768-dim embedding (SPEC v0.3.0 §31, ``nomic-embed-text`` via local
    Ollama), and a free-form ``source_origin`` provenance label. A
    derived table (mirrors 0003's ``artifact_lineage`` philosophy), not
    columns on ``artifacts``. ``embedding`` is nullable so chunking and
    embedding can land as separate steps.

No existing table is modified. The HNSW (``vss``) index over
``embedding`` is created at retrieval-build time, not here — it is
rebuildable and gated on ``hnsw_enable_experimental_persistence``.

The migration runner wraps this in a transaction; this module does
not BEGIN/COMMIT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

SCHEMA_VERSION = 4


def apply(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the chunks + embeddings table."""
    conn.execute(
        """
        CREATE TABLE artifact_chunks (
            artifact_cache_key  VARCHAR    NOT NULL,
            chunk_index         INTEGER    NOT NULL,
            chunk_text          VARCHAR    NOT NULL,
            embedding           FLOAT[768],
            source_origin       VARCHAR,
            PRIMARY KEY (artifact_cache_key, chunk_index),
            FOREIGN KEY (artifact_cache_key) REFERENCES artifacts(cache_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_chunks_cache_key ON artifact_chunks(artifact_cache_key)"
    )
