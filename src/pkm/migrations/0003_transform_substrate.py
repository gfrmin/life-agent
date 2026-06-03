"""Migration 0003 — Phase 2 transform substrate tables.

Adds the catalogue tables required by SPEC v0.2.0:

  - ``artifact_lineage``: derived index recording which input cache
    keys contributed to each transform artifact. Rebuildable from
    ``lineage.json`` files in the cache, same as ``artifacts`` is
    rebuildable from ``meta.json``.

  - ``pending_approvals``: HITL approval records for gated transform
    runs (§22.4).

  - ``approval_sources``: per-approval list of source IDs included
    in the run.

  - ``approval_samples``: cache keys of sample outputs computed
    before approval (§22.5).

  - ``approval_reasons``: policy reasons that triggered the approval
    requirement.

No existing tables are modified. The ``artifacts`` table is shared
by v0.1.x extractors and v0.2.0 transforms without schema changes.

The migration runner wraps this in a transaction; this module does
not BEGIN/COMMIT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

SCHEMA_VERSION = 3


def apply(conn: duckdb.DuckDBPyConnection) -> None:
    """Create Phase 2 transform substrate tables."""
    conn.execute(
        """
        CREATE TABLE artifact_lineage (
            artifact_cache_key  VARCHAR NOT NULL,
            input_cache_key     VARCHAR NOT NULL,
            role                VARCHAR NOT NULL,
            PRIMARY KEY (artifact_cache_key, input_cache_key),
            FOREIGN KEY (artifact_cache_key) REFERENCES artifacts(cache_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_lineage_input ON artifact_lineage(input_cache_key)"
    )

    conn.execute(
        """
        CREATE TABLE pending_approvals (
            approval_id                VARCHAR PRIMARY KEY,
            transform_name             VARCHAR NOT NULL,
            transform_declaration_hash VARCHAR NOT NULL,
            cost_estimate_usd          DOUBLE,
            source_count               INTEGER NOT NULL,
            status                     VARCHAR NOT NULL,
            created_at                 TIMESTAMP NOT NULL,
            decided_at                 TIMESTAMP,
            rejection_reason           VARCHAR,
            schema_version             INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE approval_sources (
            approval_id  VARCHAR NOT NULL,
            source_id    VARCHAR NOT NULL,
            PRIMARY KEY (approval_id, source_id),
            FOREIGN KEY (approval_id)
                REFERENCES pending_approvals(approval_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE approval_samples (
            approval_id  VARCHAR NOT NULL,
            cache_key    VARCHAR NOT NULL,
            PRIMARY KEY (approval_id, cache_key),
            FOREIGN KEY (approval_id)
                REFERENCES pending_approvals(approval_id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE approval_reasons (
            approval_id  VARCHAR NOT NULL,
            policy_name  VARCHAR NOT NULL,
            reason       VARCHAR NOT NULL,
            PRIMARY KEY (approval_id, policy_name),
            FOREIGN KEY (approval_id)
                REFERENCES pending_approvals(approval_id)
        )
        """
    )
