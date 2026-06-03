"""Stage A exit criterion: stub transform round-trip.

A StubTransformProducer returning hard-coded entity-extraction JSON
flows through the full pipeline: produce → write_artifact with lineage
→ cache hit on second run → read_artifact with lineage visible →
Phase 1 golden key preserved.

This test proves the substrate is complete: cache-key extension,
lineage storage, meta.json schema_version, catalogue migration,
and the transform producer orchestration all work together.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from pkm.cache import (
    lineage_file,
    meta_file,
    read_artifact,
    write_artifact,
)
from pkm.catalogue import open_catalogue
from pkm.hashing import compute_cache_key
from pkm.telemetry import TransformLogEntry, log_transform_execution
from pkm.transform import ModelResponse, TransformProducer

_ENTITY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["entities", "format_version"],
    "properties": {
        "format_version": {"const": 1},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "type"],
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string"},
                },
            },
        },
    },
}

_VALID_OUTPUT = {
    "format_version": 1,
    "entities": [
        {"text": "Alice", "type": "person"},
        {"text": "Acme Corp", "type": "organization"},
    ],
}


class StubTransformProducer(TransformProducer):
    name = "entity_extraction"
    version = "0.1.0"
    model_identity: ClassVar[dict[str, Any]] = {
        "provider": "stub",
        "model": "stub-model",
        "inference_params": {"temperature": 0.0},
    }
    prompt_name = "entity_extraction_v1"
    output_schema: ClassVar[dict[str, Any]] = _ENTITY_SCHEMA

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return f"Extract entities from: {input_content.decode()}"

    def call_model(self, prompt: str) -> ModelResponse:
        return ModelResponse(
            raw_text=json.dumps(_VALID_OUTPUT),
            input_tokens=150,
            output_tokens=75,
            latency_ms=300,
            cost_usd=0.002,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)


def test_stub_transform_full_round_trip(migrated_root: Path) -> None:
    """End-to-end: produce → write with lineage → cache hit → read."""
    root = migrated_root

    # 1. Produce the transform result.
    src = root / "test_doc.txt"
    src.write_text("Alice works at Acme Corp.", encoding="utf-8")
    input_hash = "a" * 64

    producer = StubTransformProducer()
    result = producer.produce(src, input_hash, {})
    assert result.status == "success"

    # 2. Compute cache key (schema_version=2).
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

    # 3. Write artifact with lineage.
    extractor_cache_key = "c" * 64
    lineage = [{"cache_key": extractor_cache_key, "role": "primary"}]

    with open_catalogue(root) as conn:
        outcome1 = write_artifact(
            root, conn,
            cache_key=cache_key,
            input_hash=input_hash,
            producer_name=producer.name,
            producer_version=producer.version,
            producer_config={},
            result=result,
            lineage=lineage,
            cache_key_schema_version=2,
        )
    assert outcome1.wrote is True

    # 4. Log telemetry.
    log_transform_execution(root, TransformLogEntry(
        timestamp="2026-04-26T12:00:00Z",
        transform_name=producer.name,
        transform_version=producer.version,
        cache_key=cache_key,
        input_cache_key=extractor_cache_key,
        model="stub-model",
        prompt_name=producer.prompt_name,
        status="success",
        error_message="",
        input_tokens=150,
        output_tokens=75,
        latency_ms=300,
        cost_usd=0.002,
        cache_hit=False,
    ))

    # 5. Cache hit on second run.
    with open_catalogue(root) as conn:
        outcome2 = write_artifact(
            root, conn,
            cache_key=cache_key,
            input_hash=input_hash,
            producer_name=producer.name,
            producer_version=producer.version,
            producer_config={},
            result=result,
            lineage=lineage,
            cache_key_schema_version=2,
        )
    assert outcome2.wrote is False

    # 6. Read artifact back and verify content + lineage.
    with open_catalogue(root) as conn:
        entry = read_artifact(root, conn, cache_key)
    assert entry is not None
    assert entry.status == "success"
    assert entry.content is not None
    parsed = json.loads(entry.content)
    assert parsed["entities"][0]["text"] == "Alice"
    assert parsed["entities"][1]["type"] == "organization"

    # 7. Lineage file present and correct.
    lf = lineage_file(root, cache_key)
    assert lf.exists()
    lineage_data = json.loads(lf.read_text(encoding="utf-8"))
    assert lineage_data["format_version"] == 1
    assert lineage_data["inputs"][0]["cache_key"] == extractor_cache_key

    # 8. meta.json records cache_key_schema_version.
    meta = json.loads(
        meta_file(root, cache_key).read_text(encoding="utf-8")
    )
    assert meta["cache_key_schema_version"] == 2
    assert meta["producer_metadata"]["prompt_name"] == "entity_extraction_v1"
    assert meta["producer_metadata"]["model_identity"]["model"] == "stub-model"

    # 9. Catalogue lineage rows present.
    with open_catalogue(root) as conn:
        rows = conn.execute(
            "SELECT input_cache_key, role FROM artifact_lineage "
            "WHERE artifact_cache_key = ?",
            [cache_key],
        ).fetchall()
    assert rows == [(extractor_cache_key, "primary")]

    # 10. Telemetry log exists.
    log_files = list((root / "logs" / "transforms").glob("*.jsonl"))
    assert len(log_files) == 1
    log_line = json.loads(
        log_files[0].read_text(encoding="utf-8").strip()
    )
    assert log_line["transform_name"] == "entity_extraction"
    assert log_line["cache_hit"] is False


def test_phase1_golden_key_preserved() -> None:
    """The v0.1.x golden cache key is byte-identical after all Phase 2
    changes.  This is the backward-compatibility anchor.
    """
    cache_key = compute_cache_key(
        input_hash="0" * 64,
        producer_name="pandoc",
        producer_version="3.1.9",
        producer_config={},
    )
    assert cache_key == (
        "92d68dd86f12140e5bb00e5b97bba4b37d1c9307ba17f272dcf76b560d41fd70"
    )


def test_schema_version_2_produces_different_key() -> None:
    """A v2 cache key (transform) is distinct from v1 with the same
    input_hash/producer/version/config — the schema_version
    discriminator makes them non-overlapping.
    """
    v1 = compute_cache_key(
        input_hash="a" * 64,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
    )
    v2 = compute_cache_key(
        input_hash="a" * 64,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity={"provider": "stub", "model": "stub"},
        prompt_hash="b" * 64,
    )
    assert v1 != v2
