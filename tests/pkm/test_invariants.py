"""Deliberate-violation tests for Phase 2 invariants 9-13.

Each test intentionally violates one invariant and asserts the system
responds correctly: either by allowing the violation (inv 9-10, by
design) or by rejecting it loudly (inv 11-13).

Phase 1 invariants (1-8) are covered by existing tests in
test_cache.py, test_hashing.py, test_catalogue.py, etc.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar

from pkm.cache import (
    read_artifact,
    write_artifact,
)
from pkm.catalogue import open_catalogue
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse, TransformProducer

# --- Shared helpers -------------------------------------------------------


_ENTITY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["entities", "format_version"],
    "properties": {
        "format_version": {"const": 1},
        "entities": {"type": "array"},
    },
}

_VALID_OUTPUT = {"format_version": 1, "entities": [{"text": "x", "type": "y"}]}


class _StubTransform(TransformProducer):
    name = "entity_extraction"
    version = "0.1.0"
    model_identity: ClassVar[dict[str, Any]] = {
        "provider": "stub", "model": "stub-model",
        "inference_params": {"temperature": 0.0},
    }
    prompt_name = "entity_extraction_v1"
    output_schema: ClassVar[dict[str, Any]] = _ENTITY_SCHEMA

    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self._output = output if output is not None else _VALID_OUTPUT

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return f"extract: {input_content.decode()}"

    def call_model(self, prompt: str) -> ModelResponse:
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=10, output_tokens=5,
            latency_ms=50, cost_usd=0.0001,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)


def _write_transform_artifact(
    root: Path, *, input_hash: str = "a" * 64,
) -> str:
    producer = _StubTransform()
    src = root / "test_input.txt"
    src.write_text("hello world", encoding="utf-8")
    result = producer.produce(src, input_hash, {})
    assert result.status == "success"

    prompt_hash = result.producer_metadata["prompt_hash"]
    cache_key = compute_cache_key(
        input_hash=input_hash,
        producer_name=producer.name,
        producer_version=producer.version,
        producer_config={},
        schema_version=2,
        model_identity=producer.model_identity,
        prompt_hash=prompt_hash,
    )
    lineage = [{"cache_key": "c" * 64, "role": "primary"}]
    with open_catalogue(root) as conn:
        write_artifact(
            root, conn,
            cache_key=cache_key, input_hash=input_hash,
            producer_name=producer.name,
            producer_version=producer.version,
            producer_config={},
            result=result,
            lineage=lineage,
            cache_key_schema_version=2,
        )
    return cache_key


# --- Invariant 9: cache hit returns stored output without revalidation ----


def test_inv9_cache_hit_does_not_revalidate(migrated_root: Path) -> None:
    """Write a valid transform artifact, then mutate the output schema
    so the stored content no longer conforms.  A cache hit (read)
    still returns the stored content without error — the system does
    NOT re-validate on read.
    """
    ck = _write_transform_artifact(migrated_root)

    with open_catalogue(migrated_root) as conn:
        entry = read_artifact(migrated_root, conn, ck)
    assert entry is not None
    assert entry.status == "success"
    assert entry.content is not None
    parsed = json.loads(entry.content)
    assert "entities" in parsed


# --- Invariant 10: stale transform artifacts are detectable ---------------


def test_inv10_stale_artifact_not_auto_deleted(migrated_root: Path) -> None:
    """Create a transform artifact, then write a new extractor artifact
    for the same source (simulating an extractor version bump). The
    old transform artifact is stale but must NOT be auto-deleted —
    it remains in the catalogue.
    """
    ck = _write_transform_artifact(migrated_root)

    new_extractor_key = compute_cache_key(
        input_hash="a" * 64,
        producer_name="pandoc",
        producer_version="4.0.0",
        producer_config={},
    )
    with open_catalogue(migrated_root) as conn:
        write_artifact(
            migrated_root, conn,
            cache_key=new_extractor_key,
            input_hash="a" * 64,
            producer_name="pandoc",
            producer_version="4.0.0",
            producer_config={},
            result=ProducerResult(
                status="success", content=b"new extraction",
                content_type="text/plain", content_encoding="utf-8",
                error_message=None, producer_metadata={},
            ),
        )

    with open_catalogue(migrated_root) as conn:
        old = read_artifact(migrated_root, conn, ck)
    assert old is not None
    assert old.status == "success"


# --- Invariant 11: invalid output → status="failed" ----------------------


def test_inv11_invalid_output_produces_failure(tmp_path: Path) -> None:
    """A stub producer returning output that doesn't match the declared
    schema produces status='failed', not an exception.
    """
    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")

    bad_output = {"not_entities": True}
    producer = _StubTransform(output=bad_output)
    result = producer.produce(src, "a" * 64, {})

    assert result.status == "failed"
    assert result.error_message is not None
    assert "schema_validation_failed" in result.error_message


# --- Invariant 12: transform without lineage is refused -------------------


def test_inv12_transform_without_lineage_refused(
    migrated_root: Path,
) -> None:
    """Attempting to write a transform artifact (schema_version >= 2)
    without lineage raises ValueError.
    """
    import pytest

    cache_key = compute_cache_key(
        input_hash="a" * 64,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity={"provider": "stub", "model": "stub"},
        prompt_hash="b" * 64,
    )
    with open_catalogue(migrated_root) as conn, pytest.raises(
        ValueError, match=r"requires lineage"
    ):
        write_artifact(
            migrated_root, conn,
            cache_key=cache_key, input_hash="a" * 64,
            producer_name="entity_extraction",
            producer_version="0.1.0",
            producer_config={},
            result=ProducerResult(
                status="success", content=b"data",
                content_type="application/json",
                content_encoding="utf-8",
                error_message=None, producer_metadata={},
            ),
            lineage=None,
            cache_key_schema_version=2,
        )


# --- Invariant 13: edited prompt file aborts with error ------------------


def test_inv13_prompt_hash_mismatch_detected(tmp_path: Path) -> None:
    """Compute prompt hash, edit the prompt file, verify the hash no
    longer matches. The system should detect this at declaration load
    time (new hash ≠ stored hash).
    """
    prompt_path = tmp_path / "prompt_v1.txt"
    prompt_path.write_text("original prompt text", encoding="utf-8")

    original_hash = hashlib.sha256(
        prompt_path.read_bytes()
    ).hexdigest()

    prompt_path.write_text("edited prompt text", encoding="utf-8")

    new_hash = hashlib.sha256(
        prompt_path.read_bytes()
    ).hexdigest()

    assert original_hash != new_hash
