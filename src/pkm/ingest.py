"""Source manifest ingestion (SPEC §8, §13.2, §13.4, §13.5).

Reads ``<root>/sources/sources.yaml``, hashes each referenced file's
byte content, and maintains the ``sources``, ``source_paths``, and
``source_tags`` tables. Directory entries with ``recursive: true``
are expanded to their contained files; symlinked subdirectories are
not traversed (loop avoidance).

Invariants:

  - A source is identified by the SHA-256 of its content (SPEC §2.1).
    Two files with byte-identical content share a single
    ``source_id`` and each path becomes a separate row in
    ``source_paths``.
  - The path recorded in ``current_path`` / ``source_paths`` is the
    *declared* path: ``os.path.abspath`` of the ``~``-expanded manifest
    entry, with symlinks left intact (SPEC §8.2, §13.6). A symlinked
    entry therefore keeps its own name and extension, which routing
    depends on; ``resolve(strict=True)`` is used only as the existence
    gate, never as the stored value.
  - Tags are many-to-many per §13.5 and live in ``source_tags``, one
    row per ``(source_id, tag)`` pair. On each ingest the tag set
    for a source is refreshed to exactly match ``sources.yaml`` —
    the manifest is declarative, so removing a tag from yaml
    removes it from the catalogue. The refresh is implemented as
    ``DELETE FROM source_tags WHERE source_id = ?`` followed by a
    fresh ``INSERT`` of the current set, inside the same transaction
    as any ``sources`` update.
  - ``first_seen`` is immutable once set; ``last_seen`` bumps on
    every successful observation (SPEC §8.2 explicitly requires
    this). Idempotency is therefore framed in terms of row counts:
    a second run adds no new ``sources`` and no new ``source_paths``
    rows, and the net ``source_tags`` set is unchanged.
  - Unreadable entries produce a WARNING and are skipped (§13.4).
    Ingest never halts on a bad manifest entry; subsequent entries
    are processed normally.

Manifest-level problems (file missing, malformed YAML, unsupported
version, non-mapping top-level) raise ``IngestError`` — these are
"fix the yaml" conditions, distinct from per-entry skippable ones.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from pkm.catalogue import open_catalogue

logger = logging.getLogger(__name__)

MANIFEST_VERSION: int = 1
"""The manifest ``version`` field this build accepts (SPEC §8.1).
Bumped only when the manifest shape changes."""

_HASH_CHUNK_SIZE = 64 * 1024


class IngestError(Exception):
    """Raised when ``sources.yaml`` is missing, unparseable, or fails
    structural validation. Distinct from per-entry unreadable paths,
    which are WARNING-logged and skipped per SPEC §13.4.
    """


@dataclass(frozen=True)
class IngestResult:
    """Outcome of an ``ingest_sources`` call.

    Attributes:
        scanned: File-level entries considered, including both those
            ingested and those skipped. For a directory entry with
            ``recursive: true`` this counts each contained file; for
            a single-file entry it is one.
        ingested: File-level entries successfully processed (hashed
            and reflected in the catalogue). Equal to
            ``scanned - len(skipped)``.
        new_sources: Rows inserted into ``sources`` (brand-new
            ``source_id`` values).
        new_paths: Rows inserted into ``source_paths`` (new
            ``(source_id, path)`` pairs).
        skipped: Raw manifest paths that could not be processed per
            §13.4. Preserves the original yaml string for user-facing
            reports.
    """

    scanned: int
    ingested: int
    new_sources: int
    new_paths: int
    skipped: list[str] = field(default_factory=list)


def sources_yaml_path(root: Path) -> Path:
    """Return the default manifest path inside ``root``: SPEC §3 puts
    it at ``<root>/sources/sources.yaml``."""
    return root / "sources" / "sources.yaml"


def ingest_sources(
    root: Path,
    *,
    sources_yaml: Path | None = None,
    only_paths: list[Path] | None = None,
) -> IngestResult:
    """Ingest sources from ``<root>/sources/sources.yaml`` (or an
    explicit override) into the catalogue.

    For each file-level entry — expanded from ``recursive: true``
    directories when present — hash the content, insert a ``sources``
    row if the ``source_id`` is new, otherwise update ``last_seen``
    and ``current_path``. Refresh the source's tag set in
    ``source_tags`` to match the current manifest (DELETE all rows
    for this ``source_id``, then INSERT one row per declared tag).
    Insert a ``source_paths`` row when the ``(source_id, path)`` pair
    has not been seen before; existing pairs keep their original
    ``seen_at``.

    Unreadable entries (missing file, permission denied, broken
    symlink, directory without ``recursive: true``, malformed tags,
    hash failure) are WARNING-logged and collected into
    ``IngestResult.skipped``. They never abort the run (§13.4).

    Args:
        root: Knowledge root. Must have a migrated catalogue.
        sources_yaml: Optional override for the manifest path.
            Defaults to ``sources_yaml_path(root)``.
        only_paths: Optional restriction (SPEC §8.2): register only the
            manifest entries whose declared path is in this list —
            per-path semantics identical to a full sweep, nothing else
            is hashed or touched. For re-registering a single evolving
            source without sweeping the whole manifest.

    Returns:
        IngestResult with counts and the list of skipped yaml paths.

    Raises:
        IngestError: manifest missing, not valid YAML, unsupported
            version, wrong top-level shape, or an individual entry
            missing a string ``path`` field.
    """
    path = sources_yaml if sources_yaml is not None else sources_yaml_path(root)
    entries = _load_manifest(path)
    restrict: set[str] | None = (
        {os.path.abspath(os.path.expanduser(str(p))) for p in only_paths}
        if only_paths is not None
        else None
    )

    skipped: list[str] = []
    ingested = 0
    new_sources = 0
    new_paths = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    with open_catalogue(root) as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            for file_path, raw_path, tags in _iter_entries(entries, skipped):
                if restrict is not None and str(file_path) not in restrict:
                    continue
                try:
                    sid, size = _hash_and_size(file_path)
                except OSError as e:
                    _log_and_skip(skipped, raw_path, f"hash failed: {e}")
                    continue

                path_str = str(file_path)
                mime = mimetypes.guess_type(file_path.name)[0]
                if _source_exists(conn, sid):
                    conn.execute(
                        "UPDATE sources SET current_path = ?, last_seen = ? "
                        "WHERE source_id = ?",
                        [path_str, now, sid],
                    )
                    logger.info(
                        "re-observed %s at %s",
                        sid[:12],
                        path_str,
                        extra={
                            "event": "source_re_seen",
                            "source_id": sid,
                            "path": path_str,
                        },
                    )
                else:
                    conn.execute(
                        "INSERT INTO sources "
                        "(source_id, current_path, first_seen, last_seen, "
                        " size_bytes, mime_type) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [sid, path_str, now, now, size, mime],
                    )
                    new_sources += 1
                    logger.info(
                        "ingested %s (%d bytes) as %s",
                        path_str,
                        size,
                        sid[:12],
                        extra={
                            "event": "source_ingested",
                            "source_id": sid,
                            "path": path_str,
                            "size_bytes": size,
                        },
                    )
                _replace_tags(conn, sid, tags)
                ingested += 1

                if not _source_path_exists(conn, sid, path_str):
                    conn.execute(
                        "INSERT INTO source_paths (source_id, path, seen_at) "
                        "VALUES (?, ?, ?)",
                        [sid, path_str, now],
                    )
                    new_paths += 1
                    logger.info(
                        "recorded new path %s for %s",
                        path_str,
                        sid[:12],
                        extra={
                            "event": "source_path_added",
                            "source_id": sid,
                            "path": path_str,
                        },
                    )

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    scanned = ingested + len(skipped)
    logger.info(
        "ingest complete: scanned %d, %d new sources, %d new paths, %d skipped",
        scanned,
        new_sources,
        new_paths,
        len(skipped),
        extra={
            "event": "ingest_complete",
            "scanned": scanned,
            "ingested": ingested,
            "new_sources": new_sources,
            "new_paths": new_paths,
            "skipped": len(skipped),
        },
    )

    return IngestResult(
        scanned=scanned,
        ingested=ingested,
        new_sources=new_sources,
        new_paths=new_paths,
        skipped=skipped,
    )


# --- Manifest loading -----------------------------------------------------


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise IngestError(
            f"sources manifest not found at {path}. create it or pass "
            f"an explicit sources_yaml path."
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise IngestError(
            f"sources manifest at {path} is not valid YAML: {e}"
        ) from e

    if raw is None:
        raise IngestError(f"sources manifest at {path} is empty")
    if not isinstance(raw, dict):
        raise IngestError(
            f"sources manifest at {path} must be a YAML mapping at "
            f"the top level; got {type(raw).__name__}"
        )

    version = raw.get("version")
    if version != MANIFEST_VERSION:
        raise IngestError(
            f"sources manifest version {version!r} at {path} is "
            f"unsupported; this build supports version {MANIFEST_VERSION}"
        )

    sources_raw = raw.get("sources")
    if sources_raw is None:
        return []
    if not isinstance(sources_raw, list):
        raise IngestError(
            f"sources manifest at {path} must have a list under "
            f"`sources`; got {type(sources_raw).__name__}"
        )

    for i, entry in enumerate(sources_raw):
        if not isinstance(entry, dict):
            raise IngestError(
                f"entry {i} in sources manifest is not a mapping"
            )
        if not isinstance(entry.get("path"), str):
            raise IngestError(
                f"entry {i} in sources manifest must have a string "
                f"`path` field"
            )

    return sources_raw


# --- Path expansion -------------------------------------------------------


def _iter_entries(
    entries: Iterable[dict[str, Any]],
    skipped: list[str],
) -> Iterator[tuple[Path, str, list[str]]]:
    """Yield ``(resolved_path, raw_yaml_path, tags)`` for every
    file-level source. Paths that cannot be processed per §13.4 are
    appended to ``skipped`` using the original yaml string.
    """
    for entry in entries:
        yield from _expand_entry(entry, skipped)


def _expand_entry(
    entry: dict[str, Any],
    skipped: list[str],
) -> Iterator[tuple[Path, str, list[str]]]:
    raw_path = str(entry["path"])
    tags_raw = entry.get("tags") or []
    if not isinstance(tags_raw, list) or not all(
        isinstance(t, str) for t in tags_raw
    ):
        _log_and_skip(skipped, raw_path, "tags must be a list of strings")
        return
    tags: list[str] = list(tags_raw)
    recursive = bool(entry.get("recursive", False))

    # Store the path as DECLARED (SPEC §8.2, §13.6): make it absolute and
    # lexically normalise `.`/`..` via os.path.abspath, but do NOT
    # dereference symlinks — a symlinked leaf keeps its own name and
    # extension, which §7.3 routing depends on. resolve(strict=True) is
    # used ONLY as the existence/readability gate (§13.4); its canonical
    # result is discarded. Hashing reads through symlinks, so source_id
    # is unaffected by how the file was named or reached.
    declared = Path(os.path.abspath(Path(raw_path).expanduser()))
    try:
        declared.resolve(strict=True)
    except OSError as e:
        _log_and_skip(skipped, raw_path, f"path does not resolve: {e}")
        return

    if declared.is_dir():
        if not recursive:
            _log_and_skip(
                skipped, raw_path,
                "path is a directory but `recursive: true` not set",
            )
            return
        # rglob in Python 3.13 defaults recurse_symlinks=False, so
        # symlinked subdirectories are not traversed. Leaf symlink
        # *files* are still enumerated by their own name, so their
        # extension is preserved.
        for p in sorted(declared.rglob("*")):
            if p.is_file():
                yield p, str(p), list(tags)
    elif declared.is_file():
        yield declared, raw_path, tags
    else:
        # Device, socket, etc.
        _log_and_skip(
            skipped, raw_path, "not a regular file or directory"
        )


# --- Hashing --------------------------------------------------------------


def _hash_and_size(path: Path) -> tuple[str, int]:
    """Stream-hash ``path`` with SHA-256, returning ``(hex, size)``.
    Streaming keeps memory use bounded for large files."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


# --- Catalogue helpers ----------------------------------------------------


def _source_exists(
    conn: duckdb.DuckDBPyConnection, source_id: str
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sources WHERE source_id = ?", [source_id]
    ).fetchone()
    return row is not None


def _source_path_exists(
    conn: duckdb.DuckDBPyConnection, source_id: str, path: str
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM source_paths WHERE source_id = ? AND path = ?",
        [source_id, path],
    ).fetchone()
    return row is not None


def _replace_tags(
    conn: duckdb.DuckDBPyConnection,
    source_id: str,
    tags: list[str],
) -> None:
    """Refresh the tag set for a source to exactly ``tags`` (SPEC §13.5).

    DELETE all existing rows for this ``source_id``, then INSERT one
    row per tag. Called for both new and existing sources — for new
    sources the DELETE is a no-op, which keeps the code path uniform
    and avoids a special case.
    """
    conn.execute("DELETE FROM source_tags WHERE source_id = ?", [source_id])
    for tag in tags:
        conn.execute(
            "INSERT INTO source_tags (source_id, tag) VALUES (?, ?)",
            [source_id, tag],
        )


# --- Logging --------------------------------------------------------------


def _log_and_skip(skipped: list[str], path: str, reason: str) -> None:
    logger.warning(
        "skipped %s (%s)",
        path,
        reason,
        extra={"event": "ingest_skipped", "path": path, "reason": reason},
    )
    skipped.append(path)
