"""Migration 0002 — normalise tags into ``source_tags``.

Implements the schema transition defined in SPEC v0.1.5 §5.1 and the
modelling rationale in §13.5:

  - drop the ``tags VARCHAR[]`` column on ``sources``;
  - add a ``source_tags(source_id, tag)`` many-to-many table with a
    foreign key back to ``sources`` and an index on ``tag`` for the
    "find all sources tagged X" query.

Any tag values present in ``sources.tags`` at migration time are
carried over into ``source_tags``, one row per ``(source_id, tag)``
pair. Empty or NULL tag arrays contribute no rows.

DuckDB specifics:

  - ``ALTER TABLE sources DROP COLUMN tags`` fails on a table that
    has incoming foreign keys (``source_paths.source_id`` references
    ``sources``). DuckDB's error is ``Dependency Error: Cannot alter
    entry "sources" because there are entries that depend on it``.
    The migration therefore uses a recreate-and-copy: snapshot
    ``sources`` and ``source_paths`` into temp tables, drop both
    (the dependent first, then the parent), recreate ``sources``
    without ``tags``, recreate ``source_paths`` with its FK, reload
    both from the snapshots, then create ``source_tags`` and
    populate it by ``UNNEST``-ing the snapshot's ``tags`` column.

  - The migration runner (``catalogue._apply_single``) wraps this
    function in a transaction; this module does not BEGIN/COMMIT.

Post-migration verification that the move solves the original
problem: ``UPDATE sources SET last_seen = ?`` on an FK-referenced
row succeeds (no LIST column in ``sources`` any more), and
``DELETE FROM source_tags WHERE source_id = ? ; INSERT INTO
source_tags VALUES ...`` is a clean implementation of declarative
tag overwrite on re-ingest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

SCHEMA_VERSION = 2


def apply(conn: duckdb.DuckDBPyConnection) -> None:
    """Normalise tags into ``source_tags`` via recreate-and-copy."""
    # 1. Snapshot existing FK-involved tables.
    conn.execute("CREATE TEMP TABLE _sources_old AS SELECT * FROM sources")
    conn.execute(
        "CREATE TEMP TABLE _source_paths_old AS SELECT * FROM source_paths"
    )

    # 2. Drop dependent first, then the parent.
    conn.execute("DROP TABLE source_paths")
    conn.execute("DROP TABLE sources")

    # 3. Recreate ``sources`` without ``tags``.
    conn.execute(
        """
        CREATE TABLE sources (
            source_id     VARCHAR PRIMARY KEY,
            current_path  VARCHAR NOT NULL,
            first_seen    TIMESTAMP NOT NULL,
            last_seen     TIMESTAMP NOT NULL,
            size_bytes    BIGINT NOT NULL,
            mime_type     VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO sources
        SELECT source_id, current_path, first_seen, last_seen,
               size_bytes, mime_type
        FROM _sources_old
        """
    )

    # 4. Recreate ``source_paths`` with its FK.
    conn.execute(
        """
        CREATE TABLE source_paths (
            source_id  VARCHAR NOT NULL,
            path       VARCHAR NOT NULL,
            seen_at    TIMESTAMP NOT NULL,
            PRIMARY KEY (source_id, path),
            FOREIGN KEY (source_id) REFERENCES sources(source_id)
        )
        """
    )
    conn.execute(
        "INSERT INTO source_paths SELECT * FROM _source_paths_old"
    )

    # 5. Create ``source_tags`` and index.
    conn.execute(
        """
        CREATE TABLE source_tags (
            source_id  VARCHAR NOT NULL,
            tag        VARCHAR NOT NULL,
            PRIMARY KEY (source_id, tag),
            FOREIGN KEY (source_id) REFERENCES sources(source_id)
        )
        """
    )
    conn.execute("CREATE INDEX idx_source_tags_tag ON source_tags(tag)")

    # 6. Carry over any existing tag data.
    conn.execute(
        """
        INSERT INTO source_tags (source_id, tag)
        SELECT source_id, UNNEST(tags)
        FROM _sources_old
        WHERE tags IS NOT NULL AND LEN(tags) > 0
        """
    )

    # 7. Drop snapshots.
    conn.execute("DROP TABLE _sources_old")
    conn.execute("DROP TABLE _source_paths_old")
