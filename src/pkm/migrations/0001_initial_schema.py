"""Initial catalogue schema — SPEC §5.1 at v0.1.3.

Creates the four v1 tables and the three artifacts indexes:

  - schema_meta   — log of applied migrations (§5.1, §14.8)
  - sources       — one row per SHA-256-identified source file
  - source_paths  — historical record of paths where each source
                    was observed
  - artifacts     — one row per cache entry

The enclosing ``run_migrations`` harness opens the transaction and
inserts the schema_meta row for this migration after ``apply`` returns.
This module issues DDL only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

SCHEMA_VERSION = 1


def apply(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the v1 catalogue schema. DDL only; the runner handles
    transactions and the schema_meta row insert.
    """
    conn.execute(
        """
        CREATE TABLE schema_meta (
            schema_version INTEGER PRIMARY KEY,
            migration_id   VARCHAR NOT NULL,
            migration_hash VARCHAR NOT NULL,
            applied_at     TIMESTAMP NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sources (
            source_id     VARCHAR PRIMARY KEY,
            current_path  VARCHAR NOT NULL,
            first_seen    TIMESTAMP NOT NULL,
            last_seen     TIMESTAMP NOT NULL,
            size_bytes    BIGINT NOT NULL,
            mime_type     VARCHAR,
            tags          VARCHAR[]
        )
        """
    )
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
        """
        CREATE TABLE artifacts (
            cache_key             VARCHAR PRIMARY KEY,
            input_hash            VARCHAR NOT NULL,
            producer_name         VARCHAR NOT NULL,
            producer_version      VARCHAR NOT NULL,
            producer_config_hash  VARCHAR NOT NULL,
            status                VARCHAR NOT NULL,
            produced_at           TIMESTAMP NOT NULL,
            size_bytes            BIGINT,
            error_message         VARCHAR,
            content_type          VARCHAR,
            content_encoding      VARCHAR,
            content_path          VARCHAR NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX idx_artifacts_input ON artifacts(input_hash)")
    conn.execute(
        "CREATE INDEX idx_artifacts_producer "
        "ON artifacts(producer_name, producer_version)"
    )
    conn.execute("CREATE INDEX idx_artifacts_status ON artifacts(status)")
