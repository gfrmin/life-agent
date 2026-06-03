"""Tests for ``pkm.transform`` — TransformProducer base class.

Exercises the orchestration pipeline (render → call → parse → validate)
via a stub subclass that returns hard-coded JSON.  No real LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from pkm.hashing import canonical_json
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
        {"text": "London", "type": "location"},
    ],
}


class StubTransformProducer(TransformProducer):
    """Hard-coded transform for testing the orchestration pipeline."""

    name = "entity_extraction"
    version = "0.1.0"
    model_identity: ClassVar[dict[str, Any]] = {
        "provider": "stub",
        "model": "stub-model",
        "inference_params": {"temperature": 0.0},
    }
    prompt_name = "entity_extraction_v1"
    output_schema: ClassVar[dict[str, Any]] = _ENTITY_SCHEMA

    def __init__(
        self, *, output: dict[str, Any] | None = None, error: str | None = None,
    ) -> None:
        self._output = output if output is not None else _VALID_OUTPUT
        self._error = error

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return f"Extract entities from: {input_content.decode()}"

    def call_model(self, prompt: str) -> ModelResponse:
        if self._error:
            raise RuntimeError(self._error)
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=100,
            output_tokens=50,
            latency_ms=250,
            cost_usd=0.001,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)


def test_stub_produce_succeeds(tmp_path: Path) -> None:
    src = tmp_path / "doc.txt"
    src.write_text("Alice went to London.", encoding="utf-8")

    producer = StubTransformProducer()
    result = producer.produce(src, "a" * 64, {})

    assert result.status == "success"
    assert result.content is not None
    parsed = json.loads(result.content)
    assert parsed["entities"][0]["text"] == "Alice"
    assert result.content_type == "application/json"
    assert result.content_encoding == "utf-8"
    assert result.error_message is None


def test_produce_content_is_canonical_json(tmp_path: Path) -> None:
    src = tmp_path / "doc.txt"
    src.write_text("hi", encoding="utf-8")

    producer = StubTransformProducer()
    result = producer.produce(src, "a" * 64, {})

    assert result.content is not None
    assert result.content == canonical_json(_VALID_OUTPUT).encode("utf-8")


def test_produce_captures_metadata(tmp_path: Path) -> None:
    src = tmp_path / "doc.txt"
    src.write_text("hi", encoding="utf-8")

    producer = StubTransformProducer()
    result = producer.produce(src, "a" * 64, {})

    md = result.producer_metadata
    assert md["completion"] == "complete"
    assert md["model_identity"] == producer.model_identity
    assert md["prompt_name"] == "entity_extraction_v1"
    assert md["input_tokens"] == 100
    assert md["output_tokens"] == 50
    assert md["latency_ms"] == 250
    assert md["cost_usd"] == 0.001
    assert isinstance(md["prompt_hash"], str)
    assert len(md["prompt_hash"]) == 64


def test_produce_schema_validation_failure(tmp_path: Path) -> None:
    """Invalid output against declared schema → status='failed'."""
    src = tmp_path / "doc.txt"
    src.write_text("hi", encoding="utf-8")

    bad_output = {"wrong_key": "no entities"}
    producer = StubTransformProducer(output=bad_output)
    result = producer.produce(src, "a" * 64, {})

    assert result.status == "failed"
    assert result.content is None
    assert result.error_message is not None
    assert "schema_validation_failed" in result.error_message


def test_produce_model_error_becomes_failed(tmp_path: Path) -> None:
    """Model API error → status='failed', not a raised exception."""
    src = tmp_path / "doc.txt"
    src.write_text("hi", encoding="utf-8")

    producer = StubTransformProducer(error="API rate limit exceeded")
    result = producer.produce(src, "a" * 64, {})

    assert result.status == "failed"
    assert "RuntimeError" in result.error_message  # type: ignore[operator]
    assert "rate limit" in result.error_message  # type: ignore[operator]


def test_produce_never_raises(tmp_path: Path) -> None:
    """Even with a completely broken subclass, produce returns a result."""
    src = tmp_path / "doc.txt"
    src.write_text("hi", encoding="utf-8")

    class BrokenProducer(TransformProducer):
        name = "broken"
        version = "0.0.1"
        model_identity: ClassVar[dict[str, Any]] = {}
        prompt_name = "test"
        output_schema: ClassVar[dict[str, Any]] = {}

        def render_prompt(
            self, input_content: bytes, input_metadata: dict[str, Any],
        ) -> str:
            raise TypeError("render broke")

        def call_model(self, prompt: str) -> ModelResponse:
            raise NotImplementedError

        def parse_output(self, raw_output: str) -> dict[str, Any]:
            raise NotImplementedError

    result = BrokenProducer().produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert "TypeError" in result.error_message  # type: ignore[operator]
