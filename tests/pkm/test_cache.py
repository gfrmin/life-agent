"""Contract tests for ``pkm.cache`` — content-addressed storage,
atomic write, idempotency, the three-point orphan sweep, and the
asymmetric-recovery policy (SPEC §6.2 at v0.1.4).

These tests fail on import at this commit because ``pkm.cache`` and
``pkm.producer`` do not yet exist. The next commit introduces both
modules and makes the tests pass.

Coverage map:

  §3          path derivation (``content_path_rel``, ``artifact_dir``)
  §6.1        idempotency of ``write_artifact``
  §6.2        atomic write ordering; orphan sweep at three
              interruption points; asymmetric-recovery on write and
              on read.
  §13.1       meta.json authoritativeness
  §13.3       failed artifacts still carry a cache row but no content
              file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pkm.cache import (
    LINEAGE_FORMAT_VERSION,
    META_FORMAT_VERSION,
    CacheInconsistencyError,
    CacheWriteOutcome,
    _hash_config,
    artifact_dir,
    content_file,
    content_path_rel,
    delete_artifact,
    lineage_file,
    meta_file,
    read_artifact,
    sweep_orphans,
    write_artifact,
)
from pkm.catalogue import open_catalogue
from pkm.hashing import canonical_json, compute_cache_key
from pkm.producer import ProducerResult

# --- Helpers ---------------------------------------------------------------

def _success(content: bytes = b"hello world") -> ProducerResult:
    return ProducerResult(
        status="success",
        content=content,
        content_type="text/plain",
        content_encoding="utf-8",
        error_message=None,
        producer_metadata={},
    )


def _failed(message: str = "pandoc exited non-zero") -> ProducerResult:
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=message,
        producer_metadata={},
    )


def _write(
    root: Path,
    *,
    input_hash: str = "a" * 64,
    producer_name: str = "pandoc",
    producer_version: str = "3.1.9",
    producer_config: dict | None = None,
    result: ProducerResult | None = None,
) -> tuple[str, CacheWriteOutcome]:
    producer_config = producer_config if producer_config is not None else {}
    result = result if result is not None else _success()
    cache_key = compute_cache_key(
        input_hash=input_hash,
        producer_name=producer_name,
        producer_version=producer_version,
        producer_config=producer_config,
    )
    with open_catalogue(root) as conn:
        outcome = write_artifact(
            root,
            conn,
            cache_key=cache_key,
            input_hash=input_hash,
            producer_name=producer_name,
            producer_version=producer_version,
            producer_config=producer_config,
            result=result,
        )
    return cache_key, outcome


# --- Path derivation -------------------------------------------------------

def test_content_path_rel_follows_two_then_sixty_two_layout() -> None:
    cache_key = "a" * 64
    assert content_path_rel(cache_key) == "aa/" + "a" * 62


def test_content_path_rel_rejects_malformed_keys() -> None:
    with pytest.raises(ValueError):
        content_path_rel("a" * 63)
    with pytest.raises(ValueError):
        content_path_rel("A" * 64)


def test_artifact_dir_is_under_cache(tmp_path: Path) -> None:
    cache_key = "b" * 64
    d = artifact_dir(tmp_path, cache_key)
    assert d == tmp_path / "cache" / "bb" / ("b" * 62)


# --- Write / read / idempotency -------------------------------------------

def test_write_produces_expected_layout_and_row(migrated_root: Path) -> None:
    """A fresh-root write produces <aa>/<bb...>/content and meta.json
    plus exactly one row in artifacts whose fields match the inputs.
    """
    cache_key, outcome = _write(migrated_root)
    assert outcome.wrote is True
    assert outcome.cache_key == cache_key

    assert content_file(migrated_root, cache_key).exists()
    assert meta_file(migrated_root, cache_key).exists()
    assert content_file(migrated_root, cache_key).read_bytes() == b"hello world"

    with open_catalogue(migrated_root) as conn:
        rows = conn.execute(
            "SELECT cache_key, input_hash, producer_name, producer_version, "
            "status, content_path FROM artifacts"
        ).fetchall()
    assert rows == [
        (
            cache_key,
            "a" * 64,
            "pandoc",
            "3.1.9",
            "success",
            content_path_rel(cache_key),
        )
    ]


def test_meta_json_carries_format_version_and_cache_key(migrated_root: Path) -> None:
    cache_key, _ = _write(migrated_root)
    meta_text = meta_file(migrated_root, cache_key).read_text(encoding="utf-8")
    meta = json.loads(meta_text)
    assert meta["format_version"] == META_FORMAT_VERSION
    assert meta["cache_key"] == cache_key
    assert meta["status"] == "success"
    assert meta["content_type"] == "text/plain"
    assert meta["content_encoding"] == "utf-8"
    assert meta["producer_name"] == "pandoc"
    assert meta["producer_version"] == "3.1.9"


def test_write_is_idempotent(migrated_root: Path) -> None:
    """Running the same write twice produces zero new writes on the
    second call, leaves both files byte-identical, and the catalogue
    has exactly one row.
    """
    cache_key, first = _write(migrated_root)
    original_content = content_file(migrated_root, cache_key).read_bytes()
    original_meta = meta_file(migrated_root, cache_key).read_bytes()

    cache_key2, second = _write(migrated_root)
    assert cache_key2 == cache_key
    assert first.wrote is True
    assert second.wrote is False

    assert content_file(migrated_root, cache_key).read_bytes() == original_content
    assert meta_file(migrated_root, cache_key).read_bytes() == original_meta

    with open_catalogue(migrated_root) as conn:
        n = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()
    assert n == (1,)


def test_read_artifact_round_trips_success(migrated_root: Path) -> None:
    cache_key, _ = _write(migrated_root, result=_success(b"payload-bytes"))
    with open_catalogue(migrated_root) as conn:
        entry = read_artifact(migrated_root, conn, cache_key)
    assert entry is not None
    assert entry.cache_key == cache_key
    assert entry.status == "success"
    assert entry.content == b"payload-bytes"
    assert entry.content_type == "text/plain"
    assert entry.content_encoding == "utf-8"
    assert entry.error_message is None


def test_read_artifact_returns_none_for_unknown_key(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        entry = read_artifact(migrated_root, conn, "0" * 64)
    assert entry is None


def test_failed_result_writes_no_content_file(migrated_root: Path) -> None:
    """A failed ProducerResult writes meta.json and a catalogue row
    (SPEC §14.3 — failures are recorded, not lost) but no content
    file.
    """
    cache_key, _ = _write(migrated_root, result=_failed("boom"))
    assert not content_file(migrated_root, cache_key).exists()
    assert meta_file(migrated_root, cache_key).exists()

    meta = json.loads(meta_file(migrated_root, cache_key).read_text(encoding="utf-8"))
    assert meta["status"] == "failed"
    assert meta["error_message"] == "boom"
    assert meta["content_type"] is None
    assert meta["size_bytes"] is None

    with open_catalogue(migrated_root) as conn:
        row = conn.execute(
            "SELECT status, size_bytes, error_message "
            "FROM artifacts WHERE cache_key = ?",
            [cache_key],
        ).fetchone()
    assert row == ("failed", None, "boom")


# --- Orphan sweep: three interruption points -----------------------------

def _orphan_dir(root: Path, cache_key: str) -> Path:
    d = artifact_dir(root, cache_key)
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_sweep_removes_orphan_with_content_only(migrated_root: Path) -> None:
    """Interruption point 1: content was written, meta.json never
    reached disk, no catalogue row ever inserted. Sweep removes the
    cache directory.
    """
    cache_key = "1" * 64
    d = _orphan_dir(migrated_root, cache_key)
    (d / "content").write_bytes(b"stranded")

    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)

    assert removed == [cache_key]
    assert not d.exists()


def test_sweep_removes_orphan_with_content_and_meta(migrated_root: Path) -> None:
    """Interruption point 2: both files on disk, catalogue row never
    inserted (process crashed between meta.json write and the
    INSERT). Sweep removes both files.
    """
    cache_key = "2" * 64
    d = _orphan_dir(migrated_root, cache_key)
    (d / "content").write_bytes(b"stranded")
    (d / "meta.json").write_text("{}", encoding="utf-8")

    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)

    assert removed == [cache_key]
    assert not d.exists()


def test_sweep_removes_orphan_with_meta_only(migrated_root: Path) -> None:
    """Interruption point 3: meta.json on disk (typical of a failed
    ProducerResult, which writes no content file) but no catalogue
    row. Sweep removes the stray meta.json (and its directory).
    """
    cache_key = "3" * 64
    d = _orphan_dir(migrated_root, cache_key)
    (d / "meta.json").write_text("{}", encoding="utf-8")

    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)

    assert removed == [cache_key]
    assert not d.exists()


def test_sweep_leaves_healthy_artifacts_untouched(migrated_root: Path) -> None:
    cache_key, _ = _write(migrated_root)
    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)
    assert removed == []
    assert content_file(migrated_root, cache_key).exists()
    assert meta_file(migrated_root, cache_key).exists()


def test_sweep_ignores_empty_cache_directories(migrated_root: Path) -> None:
    """An empty <aa>/<bb...>/ directory (no content, no meta.json) is
    not an orphan per SPEC §6.2 — the invariant is about files, not
    directories.
    """
    cache_key = "4" * 64
    d = _orphan_dir(migrated_root, cache_key)
    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)
    assert removed == []
    assert d.exists()


# --- Asymmetric recovery: row exists, files missing -----------------------

def test_write_refuses_when_row_exists_but_content_missing(
    migrated_root: Path,
) -> None:
    """SPEC §6.2 asymmetric recovery: refuse to write, log ERROR,
    defer to rebuild-catalogue.
    """
    cache_key, _ = _write(migrated_root)
    content_file(migrated_root, cache_key).unlink()

    with pytest.raises(CacheInconsistencyError) as excinfo:
        _write(migrated_root)
    msg = str(excinfo.value)
    assert cache_key in msg
    assert "content" in msg
    assert "rebuild-catalogue" in msg


def test_write_refuses_when_row_exists_but_meta_missing(
    migrated_root: Path,
) -> None:
    cache_key, _ = _write(migrated_root)
    meta_file(migrated_root, cache_key).unlink()

    with pytest.raises(CacheInconsistencyError) as excinfo:
        _write(migrated_root)
    msg = str(excinfo.value)
    assert cache_key in msg
    assert "meta.json" in msg
    assert "rebuild-catalogue" in msg


def test_read_raises_when_row_exists_but_content_missing(
    migrated_root: Path,
) -> None:
    cache_key, _ = _write(migrated_root)
    content_file(migrated_root, cache_key).unlink()

    with open_catalogue(migrated_root) as conn, pytest.raises(
        CacheInconsistencyError
    ):
        read_artifact(migrated_root, conn, cache_key)


# --- Cross-module consistency: producer_config_hash ----------------------

def test_hash_config_matches_the_recipe_used_in_compute_cache_key() -> None:
    """The ``producer_config_hash`` computed by ``cache._hash_config``
    MUST match the recipe used inside ``pkm.hashing.compute_cache_key``
    (both are SHA-256 of the canonical JSON form). A divergence would
    mean that two producers with identical configs receive different
    cache keys depending on which code path computed the hash — a
    silent correctness bug.

    Whitebox test of ``_hash_config``: the private member is imported
    deliberately to pin the cross-module invariant. If the two
    recipes are ever factored into a shared helper, this test
    becomes redundant and can be removed.
    """
    configs: list[dict] = [
        {},
        {"a": 1},
        {"ocr": True, "lang": "eng"},
        {"nested": {"deep": {"value": 42}}},
        {"unicode": "café → 🦀"},
        {"list": [1, 2, {"x": "y"}], "bool": True, "none": None},
    ]
    for config in configs:
        expected = hashlib.sha256(
            canonical_json(config).encode("utf-8")
        ).hexdigest()
        assert _hash_config(config) == expected, f"divergence on {config!r}"


def test_hash_config_is_order_insensitive() -> None:
    """``_hash_config`` collapses semantically equivalent configs
    (different key insertion order) to the same hash, because
    ``canonical_json`` sorts keys.
    """
    a = {"ocr": True, "lang": "eng"}
    b = {"lang": "eng", "ocr": True}
    assert _hash_config(a) == _hash_config(b)


# --- Transform artifacts (lineage + cache_key_schema_version) ---------------


_MODEL_IDENTITY = {"provider": "anthropic", "model": "claude-3-haiku", "version": "1"}
_PROMPT_HASH = "b" * 64


def _write_transform(
    root: Path,
    *,
    input_hash: str = "a" * 64,
    lineage: list[dict[str, str]] | None = None,
    result: ProducerResult | None = None,
) -> tuple[str, CacheWriteOutcome]:
    if lineage is None:
        lineage = [{"cache_key": "c" * 64, "role": "primary"}]
    result = result if result is not None else _success()
    cache_key = compute_cache_key(
        input_hash=input_hash,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity=_MODEL_IDENTITY,
        prompt_hash=_PROMPT_HASH,
    )
    with open_catalogue(root) as conn:
        outcome = write_artifact(
            root, conn,
            cache_key=cache_key, input_hash=input_hash,
            producer_name="entity_extraction", producer_version="0.1.0",
            producer_config={},
            result=result,
            lineage=lineage,
            cache_key_schema_version=2,
        )
    return cache_key, outcome


def test_transform_write_produces_lineage_json(migrated_root: Path) -> None:
    cache_key, outcome = _write_transform(migrated_root)
    assert outcome.wrote is True

    lf = lineage_file(migrated_root, cache_key)
    assert lf.exists()
    lineage = json.loads(lf.read_text(encoding="utf-8"))
    assert lineage["format_version"] == LINEAGE_FORMAT_VERSION
    assert len(lineage["inputs"]) == 1
    assert lineage["inputs"][0]["cache_key"] == "c" * 64
    assert lineage["inputs"][0]["role"] == "primary"


def test_transform_meta_includes_cache_key_schema_version(
    migrated_root: Path,
) -> None:
    cache_key, _ = _write_transform(migrated_root)
    meta = json.loads(meta_file(migrated_root, cache_key).read_text(encoding="utf-8"))
    assert meta["cache_key_schema_version"] == 2


def test_extractor_meta_omits_cache_key_schema_version(
    migrated_root: Path,
) -> None:
    cache_key, _ = _write(migrated_root)
    meta = json.loads(meta_file(migrated_root, cache_key).read_text(encoding="utf-8"))
    assert "cache_key_schema_version" not in meta


def test_transform_lineage_rows_in_catalogue(migrated_root: Path) -> None:
    lineage = [
        {"cache_key": "c" * 64, "role": "primary"},
        {"cache_key": "d" * 64, "role": "context"},
    ]
    cache_key, _ = _write_transform(migrated_root, lineage=lineage)

    with open_catalogue(migrated_root) as conn:
        rows = conn.execute(
            "SELECT input_cache_key, role FROM artifact_lineage "
            "WHERE artifact_cache_key = ? ORDER BY input_cache_key",
            [cache_key],
        ).fetchall()
    assert rows == [("c" * 64, "primary"), ("d" * 64, "context")]


def test_transform_write_is_idempotent(migrated_root: Path) -> None:
    _cache_key, first = _write_transform(migrated_root)
    _, second = _write_transform(migrated_root)
    assert first.wrote is True
    assert second.wrote is False

    with open_catalogue(migrated_root) as conn:
        n = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()
        lineage_n = conn.execute("SELECT COUNT(*) FROM artifact_lineage").fetchone()
    assert n == (1,)
    assert lineage_n == (1,)


def test_transform_requires_lineage(migrated_root: Path) -> None:
    cache_key = compute_cache_key(
        input_hash="a" * 64,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity=_MODEL_IDENTITY,
        prompt_hash=_PROMPT_HASH,
    )
    with open_catalogue(migrated_root) as conn, pytest.raises(
        ValueError, match=r"requires lineage"
    ):
        write_artifact(
            migrated_root, conn,
            cache_key=cache_key, input_hash="a" * 64,
            producer_name="entity_extraction", producer_version="0.1.0",
            producer_config={}, result=_success(),
            lineage=None, cache_key_schema_version=2,
        )


def test_require_files_detects_missing_lineage_for_transform(
    migrated_root: Path,
) -> None:
    cache_key, _ = _write_transform(migrated_root)
    lineage_file(migrated_root, cache_key).unlink()

    with pytest.raises(CacheInconsistencyError, match=r"lineage\.json"):
        _write_transform(migrated_root)


def test_delete_artifact_removes_lineage_rows(migrated_root: Path) -> None:
    cache_key, _ = _write_transform(migrated_root)

    with open_catalogue(migrated_root) as conn:
        deleted = delete_artifact(migrated_root, conn, cache_key)
    assert deleted is True

    with open_catalogue(migrated_root) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM artifact_lineage "
            "WHERE artifact_cache_key = ?", [cache_key],
        ).fetchone()
    assert n == (0,)


def test_sweep_removes_orphan_with_lineage(migrated_root: Path) -> None:
    """An orphan directory with content + lineage.json + meta.json
    (no catalogue row) is swept."""
    cache_key = "5" * 64
    d = artifact_dir(migrated_root, cache_key)
    d.mkdir(parents=True)
    (d / "content").write_bytes(b"data")
    (d / "lineage.json").write_text("{}", encoding="utf-8")
    (d / "meta.json").write_text("{}", encoding="utf-8")

    with open_catalogue(migrated_root) as conn:
        removed = sweep_orphans(migrated_root, conn)
    assert cache_key in removed
    assert not d.exists()
