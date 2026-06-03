"""Rebuild the ``artifacts`` catalogue table from cache meta.json
files (SPEC §5.3 at v0.1.2, §13.1).

``rebuild_artifacts`` walks ``<root>/cache/<aa>/<bb...>/`` directories,
reads each ``meta.json``, and rewrites the ``artifacts`` table from
scratch. The meta.json files are the authoritative record of
artifact provenance (SPEC §13.1); the table is a derived index
over them.

Does NOT rebuild ``sources`` or ``source_paths`` — those carry
observational data (paths, timestamps, tags) that cannot be
recovered from the cache alone. After rebuild, the user runs
``pkm ingest`` to repopulate source metadata.

Order of operations:

  1. Walk the cache. For each directory with a readable,
     parseable ``meta.json`` whose recorded ``cache_key`` matches
     the directory name, accumulate a prospective row. Malformed
     or mismatched entries are logged as WARNING and skipped.

  2. If ``dry_run=True``: return counts only; catalogue is
     untouched.

  3. Open a DuckDB transaction: ``DELETE FROM artifacts`` then
     ``INSERT`` each prospective row. Commit. On exception, roll
     back — no partial rebuild is ever visible.

  4. Sweep orphans (SPEC §6.2). Dirs whose meta.json was skipped
     in step 1, or that had no meta.json at all, now have no
     catalogue row and are removed.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pkm.cache import cache_dir, content_path_rel, sweep_orphans
from pkm.catalogue import open_catalogue

logger = logging.getLogger(__name__)

_AA_PATTERN = re.compile(r"^[0-9a-f]{2}$")
_BB_PATTERN = re.compile(r"^[0-9a-f]{62}$")

_EXPECTED_META_FORMAT_VERSION = 1


class LineageCorruptionError(Exception):
    """meta.json has transform-specific fields (``model_identity`` or
    ``prompt_hash`` in ``producer_metadata``) but no
    ``cache_key_schema_version``. This is a corruption signal — the
    two must always appear together (SPEC v0.2.0 §17.1).
    """


@dataclass(frozen=True)
class RebuildResult:
    """Outcome of a ``rebuild_artifacts`` call.

    Attributes:
        scanned: Number of cache directories whose ``meta.json`` was
            attempted (successfully or not).
        inserted: Rows written to the ``artifacts`` table. Zero if
            ``dry_run=True`` even when ``scanned > 0``.
        lineage_inserted: Rows written to ``artifact_lineage``.
        skipped: Cache keys whose ``meta.json`` was unreadable,
            malformed, format-incompatible, or whose recorded
            ``cache_key`` did not match the directory.
        swept: Cache keys whose directories were removed by the
            post-rebuild orphan sweep.
    """

    scanned: int
    inserted: int
    lineage_inserted: int = 0
    skipped: list[str] = field(default_factory=list)
    swept: list[str] = field(default_factory=list)


def rebuild_artifacts(
    root: Path,
    *,
    dry_run: bool = False,
) -> RebuildResult:
    """Rebuild the artifacts table from cache meta.json files.

    Args:
        root: Knowledge root. Must contain a migrated catalogue
            (``catalogue.duckdb`` with the v1 schema). The caller
            is responsible for running ``pkm migrate`` first if
            the schema might be missing or out of date.
        dry_run: If True, scan and parse meta.json files but write
            nothing; the catalogue is unchanged and no orphans are
            swept.

    Returns:
        ``RebuildResult`` with counts and the lists of skipped /
        swept cache keys.
    """
    scanned = 0
    rows: list[tuple[Any, ...]] = []
    lineage_rows: list[tuple[str, str, str]] = []
    skipped: list[str] = []

    for cache_key, meta_path in _iter_meta_files(root):
        scanned += 1
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            _check_meta_consistency(cache_key, meta)
            row = _meta_to_row(cache_key, meta)
            rows.append(row)
            lineage_rows.extend(
                _read_lineage(cache_key, meta_path.parent)
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
            TypeError,
            LineageCorruptionError,
        ) as e:
            logger.warning(
                "skipped cache entry %s during rebuild (%s: %s)",
                cache_key[:12],
                type(e).__name__,
                e,
                extra={
                    "event": "rebuild_skipped",
                    "cache_key": cache_key,
                    "reason": f"{type(e).__name__}: {e}",
                },
            )
            skipped.append(cache_key)

    if dry_run:
        logger.info(
            "rebuild dry-run: would insert %d of %d scanned, %d skipped",
            len(rows),
            scanned,
            len(skipped),
            extra={
                "event": "rebuild_dry_run",
                "scanned": scanned,
                "would_insert": len(rows),
                "skipped": len(skipped),
            },
        )
        return RebuildResult(
            scanned=scanned,
            inserted=0,
            lineage_inserted=0,
            skipped=skipped,
            swept=[],
        )

    with open_catalogue(root) as conn:
        # DuckDB FK checks are statement-level within a transaction,
        # so clear the child table before beginning the main rebuild
        # transaction.  artifact_lineage is a derived index anyway.
        conn.execute("DELETE FROM artifact_lineage")
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("DELETE FROM artifacts")
            for row in rows:
                conn.execute(
                    "INSERT INTO artifacts "
                    "(cache_key, input_hash, producer_name, producer_version, "
                    " producer_config_hash, status, produced_at, size_bytes, "
                    " error_message, content_type, content_encoding, "
                    " content_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    list(row),
                )
            for lr in lineage_rows:
                conn.execute(
                    "INSERT INTO artifact_lineage "
                    "(artifact_cache_key, input_cache_key, role) "
                    "VALUES (?, ?, ?)",
                    list(lr),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        swept = sweep_orphans(root, conn)

    logger.info(
        "rebuild complete: scanned %d, inserted %d, lineage %d, "
        "skipped %d, swept %d",
        scanned,
        len(rows),
        len(lineage_rows),
        len(skipped),
        len(swept),
        extra={
            "event": "rebuild_complete",
            "scanned": scanned,
            "inserted": len(rows),
            "lineage_inserted": len(lineage_rows),
            "skipped": len(skipped),
            "swept": len(swept),
        },
    )

    return RebuildResult(
        scanned=scanned,
        inserted=len(rows),
        lineage_inserted=len(lineage_rows),
        skipped=skipped,
        swept=swept,
    )


# --- Internal helpers -----------------------------------------------------


def _iter_meta_files(root: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(cache_key, meta_json_path)`` for every cache
    directory that contains a ``meta.json`` file. Directories
    without meta.json are skipped here (they become orphans in the
    post-rebuild sweep).
    """
    cdir = cache_dir(root)
    if not cdir.exists():
        return
    for aa in sorted(cdir.iterdir()):
        if not aa.is_dir() or not _AA_PATTERN.match(aa.name):
            continue
        for bb in sorted(aa.iterdir()):
            if not bb.is_dir() or not _BB_PATTERN.match(bb.name):
                continue
            meta_path = bb / "meta.json"
            if meta_path.is_file():
                yield aa.name + bb.name, meta_path


def _meta_to_row(cache_key: str, meta: dict[str, Any]) -> tuple[Any, ...]:
    """Convert a parsed meta.json dict into the tuple of values for
    an ``artifacts`` row insert. Raises on any structural problem
    (missing required field, unsupported format version,
    cache_key mismatch); the caller treats the raise as "skip".
    """
    if meta.get("format_version") != _EXPECTED_META_FORMAT_VERSION:
        raise ValueError(
            f"unsupported meta.json format_version "
            f"{meta.get('format_version')!r}; this build supports "
            f"{_EXPECTED_META_FORMAT_VERSION}"
        )
    if meta.get("cache_key") != cache_key:
        raise ValueError(
            f"meta.json cache_key {meta.get('cache_key')!r} does not "
            f"match directory name {cache_key!r}"
        )

    produced_at = datetime.fromisoformat(meta["produced_at"])

    return (
        cache_key,
        meta["input_hash"],
        meta["producer_name"],
        meta["producer_version"],
        meta["producer_config_hash"],
        meta["status"],
        produced_at,
        meta.get("size_bytes"),
        meta.get("error_message"),
        meta.get("content_type"),
        meta.get("content_encoding"),
        content_path_rel(cache_key),
    )


def _check_meta_consistency(cache_key: str, meta: dict[str, Any]) -> None:
    """Detect corruption: transform-specific fields without schema version.

    If ``producer_metadata`` contains ``model_identity`` or
    ``prompt_hash`` but the top-level ``cache_key_schema_version`` is
    absent, the meta.json is internally inconsistent — the two must
    always appear together.
    """
    pm = meta.get("producer_metadata", {})
    has_transform_fields = (
        "model_identity" in pm or "prompt_hash" in pm
    )
    has_schema_version = "cache_key_schema_version" in meta
    if has_transform_fields and not has_schema_version:
        raise LineageCorruptionError(
            f"meta.json for {cache_key} has model_identity or prompt_hash "
            f"in producer_metadata but no cache_key_schema_version field — "
            f"this is a corruption signal"
        )


def _read_lineage(
    cache_key: str, artifact_directory: Path,
) -> list[tuple[str, str, str]]:
    """Read ``lineage.json`` from a cache directory and return rows
    for the ``artifact_lineage`` table. Returns an empty list if
    no lineage.json exists (v0.1.x extractor artifacts).
    """
    lineage_path = artifact_directory / "lineage.json"
    if not lineage_path.is_file():
        return []
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    return [
        (cache_key, entry["cache_key"], entry["role"])
        for entry in lineage.get("inputs", [])
    ]
