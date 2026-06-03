"""DuckDB catalogue: connection handling and migration runner.

The catalogue is a derived index over the cache (SPEC §13.1) and
is rebuildable from cache contents via ``pkm rebuild-catalogue``. It
is never the sole source of truth for artifact data.

Schema changes are managed by explicit, numbered migrations in the
``migrations/`` subpackage. Each migration file is a Python module
named ``NNNN_description.py`` that defines:

  - ``SCHEMA_VERSION: int``  — the version this migration produces.
  - ``apply(conn)``          — a function that issues DDL (and
    optionally DML) against the open DuckDB connection.

The runner opens the transaction, calls ``apply``, and on success
inserts the corresponding ``schema_meta`` row before committing.
Before applying anything, it verifies that every previously-applied
migration file still exists on disk and still hashes to the value
recorded at apply time (SPEC §14.8). On mismatch the run aborts
loudly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import duckdb

logger = logging.getLogger(__name__)

MIGRATIONS_DIR: Path = Path(__file__).parent / "migrations"
"""The package's built-in migrations directory. Production code uses
this default; tests pass an override via ``run_migrations`` so they
can simulate edits without touching the shipped files."""

_MIGRATION_FILENAME_RE = re.compile(r"^(\d{4})_[A-Za-z0-9_]+\.py$")


# --- Exceptions ------------------------------------------------------------


class MigrationError(Exception):
    """Base class for migration-runner problems that abort the run."""


class MigrationHashMismatchError(MigrationError):
    """A previously-applied migration's on-disk hash no longer matches
    the value recorded in ``schema_meta``. Applied migrations are
    immutable (SPEC §14.8).
    """


class MigrationMissingError(MigrationError):
    """A migration recorded in ``schema_meta`` is no longer present on
    disk (SPEC §14.8).
    """


# --- Internal value types --------------------------------------------------


@dataclass(frozen=True)
class _MigrationFile:
    version: int
    filename: str
    path: Path
    file_hash: str


@dataclass(frozen=True)
class _AppliedMigration:
    version: int
    migration_id: str
    migration_hash: str
    applied_at: datetime


# --- Public API ------------------------------------------------------------


def catalogue_path(root: Path) -> Path:
    """Return the absolute path to the catalogue file inside a root."""
    return root / "catalogue.duckdb"


@contextmanager
def open_catalogue(root: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open the catalogue DuckDB file inside ``root``.

    Creates the file if it does not yet exist. Does NOT run migrations
    — callers that require a particular schema version must call
    ``run_migrations`` first, or verify the schema themselves. The
    connection is closed when the context manager exits.
    """
    path = catalogue_path(root)
    conn = duckdb.connect(str(path))
    try:
        yield conn
    finally:
        conn.close()


def run_migrations(
    root: Path,
    *,
    migrations_dir: Path | None = None,
    dry_run: bool = False,
) -> list[int]:
    """Apply pending migrations in order; idempotent.

    Before applying anything new, verifies that every
    previously-applied migration (per ``schema_meta``) still exists at
    its file path and still hashes to its recorded value. On mismatch,
    raises ``MigrationHashMismatchError`` or ``MigrationMissingError``
    and aborts without applying further migrations (SPEC §14.8).

    Args:
        root: Knowledge root directory. The catalogue file is created
            at ``<root>/catalogue.duckdb`` on first run (even in
            dry_run mode, so the result reflects the real starting
            state).
        migrations_dir: Override for the migrations source directory.
            Production callers pass ``None`` (defaulting to
            ``MIGRATIONS_DIR``). Tests may supply a copy.
        dry_run: If True, run integrity checks and compute the
            pending list, but do not apply any migration. Returned
            list is the versions that *would* be applied on a real
            run.

    Returns:
        The list of ``schema_version`` integers. When ``dry_run`` is
        False these were applied on this call, in application order.
        When True they are pending. Empty if nothing is pending.

    Raises:
        MigrationHashMismatchError: an applied migration's file on
            disk differs from its stored hash.
        MigrationMissingError: an applied migration's file is no
            longer present on disk.
        MigrationError: structural problems such as duplicate
            versions, malformed filenames, a migration missing an
            ``apply`` function, or non-monotonic version ordering.
    """
    mdir = migrations_dir if migrations_dir is not None else MIGRATIONS_DIR
    available = _discover_migrations(mdir)
    available_by_version = {m.version: m for m in available}

    applied_now: list[int] = []
    with open_catalogue(root) as conn:
        existing = _read_applied_migrations(conn)
        _verify_integrity(existing, available_by_version, mdir)

        applied_versions = {a.version for a in existing}
        pending = [m for m in available if m.version not in applied_versions]

        if existing and pending:
            max_applied = max(applied_versions)
            for p in pending:
                if p.version <= max_applied:
                    raise MigrationError(
                        f"migration {p.filename} has version {p.version} "
                        f"but the highest applied version is "
                        f"{max_applied}; migrations must be appended in "
                        f"strictly increasing order."
                    )

        if dry_run:
            return [m.version for m in pending]

        for m in pending:
            _apply_single(conn, m)
            applied_now.append(m.version)

    return applied_now


# --- Internal helpers -----------------------------------------------------


def _discover_migrations(migrations_dir: Path) -> list[_MigrationFile]:
    files: list[_MigrationFile] = []
    for path in sorted(migrations_dir.iterdir()):
        if not path.is_file() or path.suffix != ".py":
            continue
        m = _MIGRATION_FILENAME_RE.match(path.name)
        if m is None:
            continue
        files.append(
            _MigrationFile(
                version=int(m.group(1)),
                filename=path.name,
                path=path,
                file_hash=_hash_file(path),
            )
        )
    files.sort(key=lambda f: f.version)
    versions = [f.version for f in files]
    if len(set(versions)) != len(versions):
        raise MigrationError(
            f"duplicate migration versions in {migrations_dir}: {versions}"
        )
    return files


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_meta_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_name = 'schema_meta'"
    ).fetchone()
    return bool(row and row[0] > 0)


def _read_applied_migrations(
    conn: duckdb.DuckDBPyConnection,
) -> list[_AppliedMigration]:
    if not _schema_meta_exists(conn):
        return []
    rows = conn.execute(
        "SELECT schema_version, migration_id, migration_hash, applied_at "
        "FROM schema_meta ORDER BY schema_version"
    ).fetchall()
    return [
        _AppliedMigration(
            version=int(r[0]),
            migration_id=str(r[1]),
            migration_hash=str(r[2]),
            applied_at=r[3],
        )
        for r in rows
    ]


def _verify_integrity(
    applied: list[_AppliedMigration],
    available_by_version: dict[int, _MigrationFile],
    migrations_dir: Path,
) -> None:
    for a in applied:
        disk = available_by_version.get(a.version)
        if disk is None:
            raise MigrationMissingError(
                f"migration {a.migration_id} (schema version {a.version}) "
                f"is recorded in schema_meta as applied at {a.applied_at} "
                f"but is no longer present in {migrations_dir}. applied "
                f"migrations must remain in the source tree; restore the "
                f"file or add a new migration to supersede it."
            )
        if disk.filename != a.migration_id:
            raise MigrationError(
                f"schema version {a.version} was applied as "
                f"{a.migration_id!r} but the file at version {a.version} "
                f"is now {disk.filename!r}; renaming applied migrations "
                f"is not supported."
            )
        if disk.file_hash != a.migration_hash:
            raise MigrationHashMismatchError(
                f"migration {a.migration_id} has changed on disk since "
                f"it was applied at {a.applied_at}. stored hash: "
                f"{a.migration_hash}; current hash: {disk.file_hash}. "
                f"applied migrations are immutable — to change the "
                f"schema, add a new numbered migration rather than "
                f"editing this one."
            )


def _load_migration(m: _MigrationFile) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"pkm._loaded_migrations.{m.filename[:-3]}", m.path
    )
    if spec is None or spec.loader is None:
        raise MigrationError(f"cannot load migration module {m.path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_single(
    conn: duckdb.DuckDBPyConnection, m: _MigrationFile
) -> None:
    module = _load_migration(m)

    apply_fn = getattr(module, "apply", None)
    if apply_fn is None or not callable(apply_fn):
        raise MigrationError(
            f"migration {m.filename} has no callable apply(conn) function"
        )

    declared_version = getattr(module, "SCHEMA_VERSION", None)
    if declared_version != m.version:
        raise MigrationError(
            f"migration {m.filename} declares SCHEMA_VERSION="
            f"{declared_version!r} but its filename implies version "
            f"{m.version}"
        )

    applied_at = datetime.now(UTC).replace(tzinfo=None)
    conn.execute("BEGIN TRANSACTION")
    try:
        apply_fn(conn)
        conn.execute(
            "INSERT INTO schema_meta "
            "(schema_version, migration_id, migration_hash, applied_at) "
            "VALUES (?, ?, ?, ?)",
            [m.version, m.filename, m.file_hash, applied_at],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    logger.info(
        "applied migration %s (schema v%d)",
        m.filename,
        m.version,
        extra={
            "event": "migration_applied",
            "schema_version": m.version,
            "migration_id": m.filename,
            "migration_hash": m.file_hash,
        },
    )
