"""Tests for ``pkm.rebuild`` — reconstructing the artifacts table
from cache meta.json files (SPEC §5.3, §13.1).
"""

from __future__ import annotations

import json
from pathlib import Path

from pkm.cache import artifact_dir, meta_file, write_artifact
from pkm.catalogue import open_catalogue
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.rebuild import RebuildResult, rebuild_artifacts


def _success(content: bytes = b"hi") -> ProducerResult:
    return ProducerResult(
        status="success",
        content=content,
        content_type="text/plain",
        content_encoding="utf-8",
        error_message=None,
        producer_metadata={},
    )


def _failed() -> ProducerResult:
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message="boom",
        producer_metadata={},
    )


def _write_artifact(
    root: Path,
    *,
    producer_name: str = "pandoc",
    producer_config: dict | None = None,
    result: ProducerResult | None = None,
) -> str:
    producer_config = producer_config if producer_config is not None else {}
    result = result if result is not None else _success()
    cache_key = compute_cache_key(
        input_hash="a" * 64,
        producer_name=producer_name,
        producer_version="3.1.9",
        producer_config=producer_config,
    )
    with open_catalogue(root) as conn:
        write_artifact(
            root, conn,
            cache_key=cache_key, input_hash="a" * 64,
            producer_name=producer_name, producer_version="3.1.9",
            producer_config=producer_config, result=result,
        )
    return cache_key


def _drop_artifacts(root: Path) -> None:
    with open_catalogue(root) as conn:
        conn.execute("DELETE FROM artifact_lineage")
        conn.execute("DELETE FROM artifacts")


def test_rebuild_reconstructs_table_after_catalogue_loss(
    migrated_root: Path,
) -> None:
    """Write an artifact, drop the row as if the catalogue were lost,
    rebuild, verify the row is restored from meta.json."""
    ck = _write_artifact(migrated_root)
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert isinstance(result, RebuildResult)
    assert result.scanned == 1
    assert result.inserted == 1
    assert result.skipped == []
    assert result.swept == []

    with open_catalogue(migrated_root) as conn:
        rows = conn.execute(
            "SELECT cache_key, input_hash, producer_name, producer_version, "
            "status FROM artifacts"
        ).fetchall()
    assert rows == [(ck, "a" * 64, "pandoc", "3.1.9", "success")]


def test_rebuild_handles_failed_artifacts(migrated_root: Path) -> None:
    ck = _write_artifact(migrated_root, result=_failed())
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 1
    assert result.skipped == []

    with open_catalogue(migrated_root) as conn:
        row = conn.execute(
            "SELECT status, error_message, size_bytes FROM artifacts "
            "WHERE cache_key = ?",
            [ck],
        ).fetchone()
    assert row == ("failed", "boom", None)


def test_rebuild_dry_run_does_not_modify(migrated_root: Path) -> None:
    _write_artifact(migrated_root)
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root, dry_run=True)
    assert result.scanned == 1
    assert result.inserted == 0

    with open_catalogue(migrated_root) as conn:
        n = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    assert n == 0


def test_rebuild_skips_unparseable_meta_and_sweeps_the_directory(
    migrated_root: Path,
) -> None:
    ck = _write_artifact(migrated_root)
    meta_file(migrated_root, ck).write_text("{{broken-json", encoding="utf-8")
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.scanned == 1
    assert result.inserted == 0
    assert ck in result.skipped
    assert ck in result.swept
    assert not artifact_dir(migrated_root, ck).exists()


def test_rebuild_skips_cache_key_mismatch(migrated_root: Path) -> None:
    ck = _write_artifact(migrated_root)
    meta_path = meta_file(migrated_root, ck)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["cache_key"] = "f" * 64
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 0
    assert ck in result.skipped


def test_rebuild_skips_unsupported_format_version(
    migrated_root: Path,
) -> None:
    ck = _write_artifact(migrated_root)
    meta_path = meta_file(migrated_root, ck)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["format_version"] = 99
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 0
    assert ck in result.skipped


def test_rebuild_sweeps_orphans_without_meta_json(
    migrated_root: Path,
) -> None:
    """A cache directory with only a content file (no meta.json) is
    not in _iter_meta_files, so it's NOT in result.skipped — but
    after rebuild completes, it has no catalogue row and the sweep
    removes it.
    """
    ck_valid = _write_artifact(migrated_root)

    orphan_ck = "2" * 64
    orphan_dir = artifact_dir(migrated_root, orphan_ck)
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "content").write_bytes(b"orphan bytes")

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 1
    assert orphan_ck not in result.skipped
    assert orphan_ck in result.swept
    assert not orphan_dir.exists()
    # The valid artifact survives.
    assert artifact_dir(migrated_root, ck_valid).exists()


def test_rebuild_on_empty_cache(migrated_root: Path) -> None:
    result = rebuild_artifacts(migrated_root)
    assert result.scanned == 0
    assert result.inserted == 0
    assert result.lineage_inserted == 0
    assert result.skipped == []
    assert result.swept == []


# --- Transform artifact rebuild (lineage) ----------------------------------

_MODEL_IDENTITY = {"provider": "anthropic", "model": "claude-3-haiku", "version": "1"}
_PROMPT_HASH = "b" * 64


def _write_transform_artifact(
    root: Path,
    *,
    lineage: list[dict[str, str]] | None = None,
) -> str:
    if lineage is None:
        lineage = [{"cache_key": "c" * 64, "role": "primary"}]
    cache_key = compute_cache_key(
        input_hash="a" * 64,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity=_MODEL_IDENTITY,
        prompt_hash=_PROMPT_HASH,
    )
    with open_catalogue(root) as conn:
        write_artifact(
            root, conn,
            cache_key=cache_key, input_hash="a" * 64,
            producer_name="entity_extraction", producer_version="0.1.0",
            producer_config={}, result=_success(),
            lineage=lineage,
            cache_key_schema_version=2,
        )
    return cache_key


def test_rebuild_reconstructs_lineage(migrated_root: Path) -> None:
    lineage = [
        {"cache_key": "c" * 64, "role": "primary"},
        {"cache_key": "d" * 64, "role": "context"},
    ]
    ck = _write_transform_artifact(migrated_root, lineage=lineage)
    _drop_artifacts(migrated_root)
    with open_catalogue(migrated_root) as conn:
        conn.execute("DELETE FROM artifact_lineage")

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 1
    assert result.lineage_inserted == 2

    with open_catalogue(migrated_root) as conn:
        rows = conn.execute(
            "SELECT input_cache_key, role FROM artifact_lineage "
            "WHERE artifact_cache_key = ? ORDER BY input_cache_key",
            [ck],
        ).fetchall()
    assert rows == [("c" * 64, "primary"), ("d" * 64, "context")]


def test_rebuild_with_extractor_has_zero_lineage(migrated_root: Path) -> None:
    _write_artifact(migrated_root)
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 1
    assert result.lineage_inserted == 0


def test_rebuild_corruption_model_identity_without_schema_version(
    migrated_root: Path,
) -> None:
    """meta.json with model_identity in producer_metadata but no
    cache_key_schema_version is a corruption signal — rebuild must
    skip and report it."""
    ck = _write_artifact(migrated_root)
    meta_path = meta_file(migrated_root, ck)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["producer_metadata"]["model_identity"] = {"provider": "test"}
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 0
    assert ck in result.skipped


def test_rebuild_corruption_prompt_hash_without_schema_version(
    migrated_root: Path,
) -> None:
    ck = _write_artifact(migrated_root)
    meta_path = meta_file(migrated_root, ck)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["producer_metadata"]["prompt_hash"] = "x" * 64
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    _drop_artifacts(migrated_root)

    result = rebuild_artifacts(migrated_root)
    assert result.inserted == 0
    assert ck in result.skipped
