"""Contract tests for ``pkm.catalogue``.

These tests pin the migration runner's behaviour before the module
exists. They establish:

- A fresh root migrates cleanly to schema v1 (SPEC §5.1).
- Running migrations twice is a proven no-op (SPEC §6.1 idempotency,
  generalised to schema state).
- Editing an applied migration after the fact is detected and
  rejected loudly (SPEC §14.8 migration hash verification).
- Deleting an applied migration file is detected and rejected loudly
  (same paragraph).

Also exercises the default ``migrations_dir`` path (via the production
module) so the tests cover what ``pkm migrate`` will actually do, not
only a synthetic in-tmp copy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pkm.catalogue import (
    MIGRATIONS_DIR,
    MigrationHashMismatchError,
    MigrationMissingError,
    open_catalogue,
    run_migrations,
)

# --- Fresh root ------------------------------------------------------------

def test_fresh_root_migrates_to_current_schema(tmp_root: Path) -> None:
    """A fresh knowledge root with no catalogue.duckdb is migrated
    through the full migration set: schema_meta records every
    migration that ran, and every table declared by any migration is
    present. Written to be robust to new migrations landing — asserts
    the current set rather than a specific version.
    """
    applied = run_migrations(tmp_root)
    assert applied == [1, 2, 3, 4, 5]

    with open_catalogue(tmp_root) as conn:
        rows = conn.execute(
            "SELECT schema_version, migration_id FROM schema_meta "
            "ORDER BY schema_version"
        ).fetchall()
        assert rows == [
            (1, "0001_initial_schema.py"),
            (2, "0002_normalise_tags.py"),
            (3, "0003_transform_substrate.py"),
            (4, "0004_chunks_and_embeddings.py"),
            (5, "0005_chunk_surrogate_key.py"),
        ]

        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        assert {
            "schema_meta",
            "sources",
            "source_paths",
            "source_tags",
            "artifacts",
            "artifact_lineage",
            "pending_approvals",
            "approval_sources",
            "approval_samples",
            "approval_reasons",
            "artifact_chunks",
        } <= tables

        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT index_name FROM duckdb_indexes() "
                "WHERE schema_name = 'main'"
            ).fetchall()
        }
        assert {
            "idx_artifacts_input",
            "idx_artifacts_producer",
            "idx_artifacts_status",
            "idx_source_tags_tag",
            "idx_lineage_input",
            "idx_chunks_cache_key",
        } <= indexes


# --- Migration 0004: chunks + embeddings -----------------------------------

def test_migration_0004_chunks_table_shape(tmp_root: Path) -> None:
    """``artifact_chunks`` stores a 768-dim embedding (SPEC v0.3.0 §31),
    keyed by (artifact_cache_key, chunk_index), FK to ``artifacts``. A NULL
    embedding is permitted — chunking and embedding land as separate steps.
    """
    run_migrations(tmp_root)
    with open_catalogue(tmp_root) as conn:
        cols = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'artifact_chunks'"
            ).fetchall()
        }
        # 768-dim fixed-size array (DuckDB reports e.g. FLOAT[768]).
        assert "768" in cols["embedding"]

        # FK requires the parent artifact to exist first.
        conn.execute(
            "INSERT INTO artifacts (cache_key, input_hash, producer_name, "
            "producer_version, producer_config_hash, status, produced_at, "
            "content_path) VALUES ('k0', 'h0', 'p', '1', 'c', 'success', "
            "now(), '/x')"
        )
        # A chunk with a NULL embedding is valid.
        conn.execute(
            "INSERT INTO artifact_chunks (artifact_cache_key, chunk_index, "
            "chunk_text, source_origin) VALUES ('k0', 0, 'hello', 'ocr')"
        )
        embedding, origin = conn.execute(
            "SELECT embedding, source_origin FROM artifact_chunks"
        ).fetchone()
        assert embedding is None
        assert origin == "ocr"


# --- Idempotency -----------------------------------------------------------

def test_second_run_is_a_proven_no_op(tmp_root: Path) -> None:
    """Running migrations twice writes zero new schema_meta rows on the
    second pass and leaves every original ``applied_at`` timestamp
    untouched. This is the same idempotency discipline as the cache,
    expressed for schema state.
    """
    applied_first = run_migrations(tmp_root)
    assert applied_first == [1, 2, 3, 4, 5]

    with open_catalogue(tmp_root) as conn:
        first_snapshot = conn.execute(
            "SELECT schema_version, migration_id, migration_hash, applied_at "
            "FROM schema_meta ORDER BY schema_version"
        ).fetchall()
    assert len(first_snapshot) == 5

    applied_second = run_migrations(tmp_root)
    assert applied_second == []

    with open_catalogue(tmp_root) as conn:
        second_snapshot = conn.execute(
            "SELECT schema_version, migration_id, migration_hash, applied_at "
            "FROM schema_meta ORDER BY schema_version"
        ).fetchall()
    assert second_snapshot == first_snapshot


# --- Hash verification ------------------------------------------------------

def test_edited_applied_migration_fails_loudly(tmp_root: Path) -> None:
    """If a migration file is edited after it has been applied, the
    next run MUST raise ``MigrationHashMismatchError`` with a message that
    identifies the migration and states that applied migrations are
    immutable.
    """
    custom_dir = tmp_root / "custom_migrations"
    shutil.copytree(MIGRATIONS_DIR, custom_dir)

    run_migrations(tmp_root, migrations_dir=custom_dir)

    # Append content so the file still parses but the hash differs.
    migration = custom_dir / "0001_initial_schema.py"
    migration.write_text(
        migration.read_text() + "\n# edit made after the migration was applied\n"
    )

    with pytest.raises(MigrationHashMismatchError) as excinfo:
        run_migrations(tmp_root, migrations_dir=custom_dir)

    msg = str(excinfo.value)
    assert "0001_initial_schema.py" in msg
    assert "immutable" in msg.lower() or "new" in msg.lower()


def test_missing_applied_migration_fails_loudly(tmp_root: Path) -> None:
    """If a migration file has been deleted from disk but a row still
    references it in ``schema_meta``, the next run MUST raise
    ``MigrationMissingError`` with a message identifying the migration.
    """
    custom_dir = tmp_root / "custom_migrations"
    shutil.copytree(MIGRATIONS_DIR, custom_dir)

    run_migrations(tmp_root, migrations_dir=custom_dir)

    (custom_dir / "0001_initial_schema.py").unlink()

    with pytest.raises(MigrationMissingError) as excinfo:
        run_migrations(tmp_root, migrations_dir=custom_dir)
    assert "0001_initial_schema.py" in str(excinfo.value)


# --- Fresh root, no catalogue_file ----------------------------------------

def test_no_catalogue_file_before_migrate(tmp_root: Path) -> None:
    """The fixture deliberately does not create catalogue.duckdb.
    Confirm the fixture shape holds before migrate runs, so any future
    regression in the tmp_root fixture surfaces here.
    """
    assert not (tmp_root / "catalogue.duckdb").exists()
    run_migrations(tmp_root)
    assert (tmp_root / "catalogue.duckdb").exists()
