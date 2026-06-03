"""Content-addressed cache layer (SPEC §3, §6, §13.1, §14.7).

The cache is an append-only store under ``<root>/cache/``. Each
artifact lives at ``<root>/cache/<aa>/<bb...>/``, where ``<aa>`` is
the first two characters of the cache key and ``<bb...>`` is the
remaining sixty-two, and the directory contains exactly two files:

  - ``content``    : the artifact bytes, written verbatim.
  - ``meta.json``  : the authoritative metadata record
                     (SPEC §13.1). Carries ``format_version``,
                     ``cache_key``, producer identity, producer
                     config (verbatim and hashed), status,
                     timestamps, content type / encoding, size,
                     error message, and any producer_metadata.

Write ordering (SPEC §6.2):

  1. Write ``content`` (skipped for failed artifacts — they have
     no bytes to store but still get a meta.json + catalogue row
     so the failure is cached per SPEC §14.3).
  2. Write ``meta.json``.
  3. Begin a DuckDB transaction, insert the ``artifacts`` row,
     commit.

The filesystem and the DuckDB catalogue cannot share a single
transaction, so the visible invariant ("no row without files, no
files without a row on next run") is upheld by ordering plus an
explicit ``sweep_orphans`` pass that runs at the start of every
``pkm extract`` and every ``pkm rebuild-catalogue`` invocation.

Asymmetric recovery (SPEC §6.2 at v0.1.4):

  If the catalogue holds a row for a cache key but the
  corresponding ``content`` or ``meta.json`` is missing on disk,
  ``write_artifact`` and ``read_artifact`` abort with
  ``CacheInconsistencyError``. They do NOT produce new bytes for
  that cache key — silently re-writing would overwrite a data-loss
  signal with output we cannot verify. The user's remedy is
  ``pkm rebuild-catalogue``, which reconciles the catalogue back to
  the filesystem.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb

from pkm.hashing import canonical_json
from pkm.producer import ProducerResult

logger = logging.getLogger(__name__)

META_FORMAT_VERSION: int = 1
"""Version for the meta.json JSON format, bumped when its shape
changes (SPEC §14.8)."""

_CACHE_KEY_RE = re.compile(r"^[0-9a-f]{64}$")
_AA_RE = re.compile(r"^[0-9a-f]{2}$")
_BB_RE = re.compile(r"^[0-9a-f]{62}$")


# --- Exceptions ------------------------------------------------------------


class CacheError(Exception):
    """Base class for cache-layer problems."""


class CacheInconsistencyError(CacheError):
    """The catalogue has a row for a cache key but the cache files
    are missing from disk (SPEC §6.2 asymmetric recovery).
    """


# --- Value types -----------------------------------------------------------


@dataclass(frozen=True)
class CacheWriteOutcome:
    """Return value of ``write_artifact``."""

    cache_key: str
    wrote: bool  # False iff the artifact was already present (idempotent hit)


@dataclass(frozen=True)
class CacheEntry:
    """A single artifact read back from the cache via
    ``read_artifact``. Combines data from the catalogue row and from
    meta.json (the authoritative record per SPEC §13.1).
    """

    cache_key: str
    input_hash: str
    producer_name: str
    producer_version: str
    producer_config: dict[str, Any]
    producer_config_hash: str
    status: Literal["success", "failed"]
    produced_at: datetime
    size_bytes: int | None
    content_type: str | None
    content_encoding: str | None
    error_message: str | None
    producer_metadata: dict[str, Any]
    content: bytes | None
    content_path: str


# --- Path derivation -------------------------------------------------------


def cache_dir(root: Path) -> Path:
    """The ``<root>/cache/`` directory (may not yet exist)."""
    return root / "cache"


def content_path_rel(cache_key: str) -> str:
    """Return ``<aa>/<bb...>`` for the cache key — the value stored
    in ``artifacts.content_path`` (SPEC §5.1, resolved ambiguity).
    """
    _validate_cache_key(cache_key)
    return f"{cache_key[:2]}/{cache_key[2:]}"


def artifact_dir(root: Path, cache_key: str) -> Path:
    """Absolute directory for the artifact of ``cache_key``:
    ``<root>/cache/<aa>/<bb...>/``.
    """
    _validate_cache_key(cache_key)
    return cache_dir(root) / cache_key[:2] / cache_key[2:]


def content_file(root: Path, cache_key: str) -> Path:
    return artifact_dir(root, cache_key) / "content"


def meta_file(root: Path, cache_key: str) -> Path:
    return artifact_dir(root, cache_key) / "meta.json"


def lineage_file(root: Path, cache_key: str) -> Path:
    return artifact_dir(root, cache_key) / "lineage.json"


def _validate_cache_key(cache_key: str) -> None:
    if not _CACHE_KEY_RE.match(cache_key):
        raise ValueError(
            f"cache_key must be exactly 64 lowercase hex characters, "
            f"got {cache_key!r}"
        )


# --- Write ----------------------------------------------------------------


LINEAGE_FORMAT_VERSION: int = 1
"""Version for lineage.json (SPEC v0.2.0 §18.3)."""


def write_artifact(
    root: Path,
    conn: duckdb.DuckDBPyConnection,
    *,
    cache_key: str,
    input_hash: str,
    producer_name: str,
    producer_version: str,
    producer_config: Mapping[str, Any],
    result: ProducerResult,
    lineage: list[dict[str, str]] | None = None,
    cache_key_schema_version: int = 1,
) -> CacheWriteOutcome:
    """Atomically write an artifact and its catalogue row.

    Idempotent: if the cache key already has a row AND all expected
    files are on disk, returns immediately with ``wrote=False``. If
    the row exists but files are missing, raises
    ``CacheInconsistencyError`` (§6.2 asymmetric recovery).

    Write order (§6.2, extended by v0.2.0 §18.4):
        content → lineage.json → meta.json → BEGIN; INSERT; COMMIT.

    Args:
        root: Knowledge root directory.
        conn: Open catalogue connection (caller manages lifetime).
        cache_key: Precomputed 64-hex cache key.
        input_hash: 64-hex SHA-256 of the input content.
        producer_name, producer_version: Producer identity.
        producer_config: Producer parameters.
        result: The producer's outcome.
        lineage: For transform artifacts, a list of
            ``{"cache_key": ..., "role": ...}`` dicts recording
            which input artifacts contributed. Required for
            ``cache_key_schema_version >= 2``.
        cache_key_schema_version: 1 for v0.1.x extractors (default),
            2 for v0.2.0 transforms.

    Returns:
        CacheWriteOutcome with ``wrote=True`` on first write,
        ``wrote=False`` on idempotent hit.

    Raises:
        CacheInconsistencyError: catalogue row exists but cache
            files are missing.
        ValueError: malformed ``cache_key``, or mismatched
            ``lineage`` / ``cache_key_schema_version``.
    """
    _validate_cache_key(cache_key)

    if cache_key_schema_version >= 2 and lineage is None:
        raise ValueError(
            "cache_key_schema_version >= 2 (transform) requires lineage"
        )

    # Idempotency / asymmetric-recovery guard.
    if _row_exists(conn, cache_key):
        _require_files_present(root, cache_key)
        return CacheWriteOutcome(cache_key=cache_key, wrote=False)

    if result.status == "success":
        if result.content is None:
            raise ValueError(
                "ProducerResult.status='success' but content is None"
            )
        content_bytes: bytes | None = result.content
        size_bytes: int | None = len(result.content)
    else:
        content_bytes = None
        size_bytes = None

    config_dict: dict[str, Any] = dict(producer_config)
    producer_config_hash = _hash_config(config_dict)
    produced_at = datetime.now(UTC).replace(tzinfo=None)

    adir = artifact_dir(root, cache_key)
    adir.mkdir(parents=True, exist_ok=True)

    # Stage 1: content (skipped for failed results).
    if content_bytes is not None:
        (adir / "content").write_bytes(content_bytes)

    # Stage 2: lineage.json (transform artifacts only, §18.4).
    if lineage is not None:
        lineage_obj = {
            "format_version": LINEAGE_FORMAT_VERSION,
            "inputs": lineage,
        }
        (adir / "lineage.json").write_text(
            json.dumps(lineage_obj, indent=2, sort_keys=True,
                       ensure_ascii=False),
            encoding="utf-8",
        )

    # Stage 3: meta.json.
    meta_obj: dict[str, Any] = {
        "format_version": META_FORMAT_VERSION,
        "cache_key": cache_key,
        "input_hash": input_hash,
        "producer_name": producer_name,
        "producer_version": producer_version,
        "producer_config": config_dict,
        "producer_config_hash": producer_config_hash,
        "status": result.status,
        "produced_at": produced_at.isoformat(),
        "size_bytes": size_bytes,
        "error_message": result.error_message,
        "content_type": result.content_type,
        "content_encoding": result.content_encoding,
        "producer_metadata": dict(result.producer_metadata),
    }
    if cache_key_schema_version >= 2:
        meta_obj["cache_key_schema_version"] = cache_key_schema_version
    (adir / "meta.json").write_text(
        json.dumps(meta_obj, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    # Stage 4: catalogue rows in one transaction.
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            "INSERT INTO artifacts "
            "(cache_key, input_hash, producer_name, producer_version, "
            " producer_config_hash, status, produced_at, size_bytes, "
            " error_message, content_type, content_encoding, content_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                cache_key,
                input_hash,
                producer_name,
                producer_version,
                producer_config_hash,
                result.status,
                produced_at,
                size_bytes,
                result.error_message,
                result.content_type,
                result.content_encoding,
                content_path_rel(cache_key),
            ],
        )
        if lineage is not None:
            for entry in lineage:
                conn.execute(
                    "INSERT INTO artifact_lineage "
                    "(artifact_cache_key, input_cache_key, role) "
                    "VALUES (?, ?, ?)",
                    [cache_key, entry["cache_key"], entry["role"]],
                )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    logger.info(
        "wrote %s artifact for %s via %s@%s",
        result.status,
        input_hash[:12],
        producer_name,
        producer_version,
        extra={
            "event": "cache_written",
            "cache_key": cache_key,
            "input_hash": input_hash,
            "producer_name": producer_name,
            "producer_version": producer_version,
            "producer_config_hash": producer_config_hash,
            "status": result.status,
        },
    )

    return CacheWriteOutcome(cache_key=cache_key, wrote=True)


# --- Read -----------------------------------------------------------------


def read_artifact(
    root: Path,
    conn: duckdb.DuckDBPyConnection,
    cache_key: str,
) -> CacheEntry | None:
    """Read an artifact by cache key. Returns ``None`` if the
    catalogue has no row for it. Raises ``CacheInconsistencyError``
    if the row exists but files are missing (§6.2).
    """
    _validate_cache_key(cache_key)

    row = _fetch_artifacts_row(conn, cache_key)
    if row is None:
        return None

    _require_files_present(root, cache_key)

    meta = json.loads(meta_file(root, cache_key).read_text(encoding="utf-8"))

    if row["status"] == "success":
        content: bytes | None = content_file(root, cache_key).read_bytes()
    else:
        content = None

    return CacheEntry(
        cache_key=cache_key,
        input_hash=row["input_hash"],
        producer_name=row["producer_name"],
        producer_version=row["producer_version"],
        producer_config=meta.get("producer_config", {}),
        producer_config_hash=row["producer_config_hash"],
        status=row["status"],
        produced_at=row["produced_at"],
        size_bytes=row["size_bytes"],
        content_type=row["content_type"],
        content_encoding=row["content_encoding"],
        error_message=row["error_message"],
        producer_metadata=meta.get("producer_metadata", {}),
        content=content,
        content_path=row["content_path"],
    )


# --- Delete --------------------------------------------------------------


def delete_artifact(
    root: Path,
    conn: duckdb.DuckDBPyConnection,
    cache_key: str,
) -> bool:
    """Remove an artifact's cache files and catalogue row.

    Used by ``pkm extract --retry-failed`` (SPEC §14.3) to clear a
    cached failure before re-running the producer: ``write_artifact``
    is idempotent and would short-circuit on the existing row, so a
    retry must start from a clean slate. This is the only way an
    artifact is removed from the catalogue during normal operation —
    the sweep removes orphaned files, but this function removes the
    row-plus-files atomically in the intended order (files first,
    then row, so that an interrupted call leaves at worst a cache
    directory for the next sweep to collect).

    Args:
        root: Knowledge root.
        conn: Open catalogue connection.
        cache_key: The artifact to remove.

    Returns:
        True if a row existed and was deleted, False if the cache
        key was unknown to the catalogue (and no file action was
        taken).
    """
    _validate_cache_key(cache_key)
    if not _row_exists(conn, cache_key):
        return False

    adir = artifact_dir(root, cache_key)
    if adir.exists():
        shutil.rmtree(adir)

    # DuckDB FK checks are statement-level within a transaction, so
    # deleting lineage rows and the artifact row in the same
    # transaction fails.  Delete lineage first (derived index,
    # rebuildable), then the artifact row.
    conn.execute(
        "DELETE FROM artifact_lineage WHERE artifact_cache_key = ?",
        [cache_key],
    )
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            "DELETE FROM artifacts WHERE cache_key = ?", [cache_key]
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    logger.info(
        "deleted cached artifact %s",
        cache_key[:12],
        extra={"event": "cache_deleted", "cache_key": cache_key},
    )
    return True


# --- Orphan sweep ---------------------------------------------------------


def sweep_orphans(
    root: Path, conn: duckdb.DuckDBPyConnection
) -> list[str]:
    """Remove orphan cache directories and return the cache keys
    removed (SPEC §6.2).

    A cache directory ``<root>/cache/<aa>/<bb...>/`` is an orphan iff
    it contains a ``content`` and/or ``meta.json`` file AND no row in
    ``artifacts`` has ``cache_key`` equal to ``<aa><bb...>``. Empty
    directories are not touched — the invariant is about files, not
    directories.

    Must be called at the start of every ``pkm extract`` and every
    ``pkm rebuild-catalogue`` invocation.
    """
    cdir = cache_dir(root)
    if not cdir.exists():
        return []

    known_keys = {
        row[0]
        for row in conn.execute("SELECT cache_key FROM artifacts").fetchall()
    }

    removed: list[str] = []
    for aa in sorted(cdir.iterdir()):
        if not aa.is_dir() or not _AA_RE.match(aa.name):
            continue
        for bb in sorted(aa.iterdir()):
            if not bb.is_dir() or not _BB_RE.match(bb.name):
                continue
            cache_key = aa.name + bb.name
            if cache_key in known_keys:
                continue

            files = [f for f in bb.iterdir() if f.is_file()]
            if not files:
                # Empty directory — not an orphan per §6.2.
                continue

            contained = sorted(f.name for f in files)
            shutil.rmtree(bb)
            removed.append(cache_key)
            logger.warning(
                "removed orphan cache dir %s (contained %s)",
                cache_key[:12],
                ", ".join(contained),
                extra={
                    "event": "orphan_removed",
                    "cache_key": cache_key,
                    "contained": contained,
                },
            )
    return removed


# --- Internal helpers -----------------------------------------------------


def _hash_config(producer_config: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical JSON form of the producer config.
    Matches the ``producer_config_hash`` construction used inside
    ``compute_cache_key`` (SPEC §4.2).
    """
    return hashlib.sha256(
        canonical_json(dict(producer_config)).encode("utf-8")
    ).hexdigest()


def _row_exists(conn: duckdb.DuckDBPyConnection, cache_key: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM artifacts WHERE cache_key = ?", [cache_key]
    ).fetchone()
    return row is not None


def _fetch_artifacts_row(
    conn: duckdb.DuckDBPyConnection, cache_key: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT input_hash, producer_name, producer_version, "
        "producer_config_hash, status, produced_at, size_bytes, "
        "error_message, content_type, content_encoding, content_path "
        "FROM artifacts WHERE cache_key = ?",
        [cache_key],
    ).fetchone()
    if row is None:
        return None
    return {
        "input_hash": row[0],
        "producer_name": row[1],
        "producer_version": row[2],
        "producer_config_hash": row[3],
        "status": row[4],
        "produced_at": row[5],
        "size_bytes": row[6],
        "error_message": row[7],
        "content_type": row[8],
        "content_encoding": row[9],
        "content_path": row[10],
    }


def _require_files_present(root: Path, cache_key: str) -> None:
    """Raise ``CacheInconsistencyError`` if expected files are missing
    for ``cache_key`` (SPEC §6.2 asymmetric recovery).

    Expected files depend on artifact type:
      - v0.1.x extractors: ``content`` (success only) + ``meta.json``
      - v0.2.0 transforms (``cache_key_schema_version >= 2``):
        ``content`` (success only) + ``lineage.json`` + ``meta.json``
    """
    adir = artifact_dir(root, cache_key)
    meta_missing = not (adir / "meta.json").exists()

    if meta_missing:
        content_missing = not (adir / "content").exists()
        _raise_inconsistency(adir, cache_key, content_missing, True)

    meta = json.loads((adir / "meta.json").read_text(encoding="utf-8"))
    content_missing = (
        meta.get("status") == "success"
        and not (adir / "content").exists()
    )
    if content_missing:
        _raise_inconsistency(adir, cache_key, True, False)

    if (
        meta.get("cache_key_schema_version", 1) >= 2
        and not (adir / "lineage.json").exists()
    ):
        _raise_inconsistency_lineage(adir, cache_key)


def _raise_inconsistency(
    adir: Path,
    cache_key: str,
    content_missing: bool,
    meta_missing: bool,
) -> None:
    missing: list[str] = []
    if content_missing:
        missing.append("content")
    if meta_missing:
        missing.append("meta.json")
    logger.error(
        "cache inconsistency at %s: catalogue row exists but %s missing",
        cache_key[:12],
        ", ".join(missing),
        extra={
            "event": "cache_inconsistency",
            "cache_key": cache_key,
            "missing": missing,
            "artifact_dir": str(adir),
        },
    )
    raise CacheInconsistencyError(
        f"catalogue has a row for cache_key {cache_key} but "
        f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} "
        f"missing on disk at {adir}. run `pkm rebuild-catalogue` to "
        f"reconcile."
    )


def _raise_inconsistency_lineage(adir: Path, cache_key: str) -> None:
    logger.error(
        "cache inconsistency at %s: transform artifact missing lineage.json",
        cache_key[:12],
        extra={
            "event": "cache_inconsistency",
            "cache_key": cache_key,
            "missing": ["lineage.json"],
            "artifact_dir": str(adir),
        },
    )
    raise CacheInconsistencyError(
        f"catalogue has a row for cache_key {cache_key} and meta.json "
        f"indicates cache_key_schema_version >= 2 (transform) but "
        f"lineage.json is missing on disk at {adir}. run "
        f"`pkm rebuild-catalogue` to reconcile."
    )
