"""Tests for ``pkm.transforms.entity_extraction``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from pkm.policy import CostEstimate
from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration
from pkm.transforms.entity_extraction import (
    EntityExtractionProducer,
    _strip_unsupported_for_api,
    estimate_cost,
)

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
                "required": ["text", "type", "span"],
                "properties": {
                    "text": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "person", "organization", "location",
                            "date", "money", "other",
                        ],
                    },
                    "span": {
                        "type": "object",
                        "required": ["start", "end"],
                        "properties": {
                            "start": {"type": "integer", "minimum": 0},
                            "end": {"type": "integer", "minimum": 0},
                        },
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
            },
        },
    },
}

_PROMPT_TEMPLATE = "Extract entities from:\n---\n{text}\n---"


def _make_declaration(**overrides: Any) -> TransformDeclaration:
    defaults: dict[str, Any] = {
        "name": "entity_extraction",
        "version": "0.2.0",
        "producer_class": "pkm.transforms.entity_extraction.EntityExtractionProducer",
        "model_identity": {
            "provider": "anthropic",
            "model": "claude-haiku-4-5",
            "inference_params": {"temperature": 0.0, "max_tokens": 4096},
        },
        "prompt_name": "entity_extraction_v1",
        "prompt_text": _PROMPT_TEMPLATE,
        "prompt_hash": "a" * 64,
        "output_schema_name": "entity_extraction_v1",
        "output_schema": _ENTITY_SCHEMA,
        "policies": ["cost_gate", "sensitive_doc_gate"],
        "input_producer": "pandoc",
        "input_required_status": "success",
        "declaration_hash": "b" * 64,
    }
    defaults.update(overrides)
    return TransformDeclaration(**defaults)


@dataclass
class _MockUsage:
    input_tokens: int = 150
    output_tokens: int = 75


@dataclass
class _MockTextBlock:
    text: str = ""
    type: str = "text"


@dataclass
class _MockResponse:
    content: list[_MockTextBlock]
    usage: _MockUsage


def _make_mock_client(output: dict[str, Any]) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = _MockResponse(
        content=[_MockTextBlock(text=json.dumps(output))],
        usage=_MockUsage(input_tokens=150, output_tokens=75),
    )
    return client


def _valid_output_for(text: str) -> dict[str, Any]:
    """Build a valid entity extraction output with correct spans."""
    return {
        "format_version": 1,
        "entities": [
            {
                "text": "Alice",
                "type": "person",
                "span": {"start": text.index("Alice"), "end": text.index("Alice") + 5},
                "confidence": 0.95,
            },
        ],
    }


# --- _strip_unsupported_for_api -----------------------------------------


def test_strip_removes_numeric_constraints() -> None:
    schema: dict[str, Any] = {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "exclusiveMinimum": -1,
        "exclusiveMaximum": 2,
        "multipleOf": 0.1,
    }
    result = _strip_unsupported_for_api(schema)
    assert "minimum" not in result
    assert "maximum" not in result
    assert "exclusiveMinimum" not in result
    assert "exclusiveMaximum" not in result
    assert "multipleOf" not in result
    assert result["type"] == "number"


def test_strip_removes_string_constraints() -> None:
    schema: dict[str, Any] = {
        "type": "string",
        "minLength": 1,
        "maxLength": 100,
    }
    result = _strip_unsupported_for_api(schema)
    assert "minLength" not in result
    assert "maxLength" not in result


def test_strip_removes_schema_keyword() -> None:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {},
    }
    result = _strip_unsupported_for_api(schema)
    assert "$schema" not in result


def test_strip_recurses_into_nested_objects() -> None:
    result = _strip_unsupported_for_api(_ENTITY_SCHEMA)
    span_props = (
        result["properties"]["entities"]["items"]
        ["properties"]["span"]["properties"]
    )
    assert "minimum" not in span_props["start"]
    assert "minimum" not in span_props["end"]

    conf = (
        result["properties"]["entities"]["items"]
        ["properties"]["confidence"]
    )
    assert "minimum" not in conf
    assert "maximum" not in conf


def test_strip_adds_additional_properties_false() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
        },
    }
    result = _strip_unsupported_for_api(schema)
    assert result["additionalProperties"] is False


def test_strip_preserves_existing_additional_properties() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": True,
    }
    result = _strip_unsupported_for_api(schema)
    assert result["additionalProperties"] is True


def test_strip_preserves_allowed_keys() -> None:
    result = _strip_unsupported_for_api(_ENTITY_SCHEMA)
    assert result["type"] == "object"
    assert "entities" in result["required"]
    assert result["properties"]["format_version"]["const"] == 1
    items = result["properties"]["entities"]["items"]
    assert items["properties"]["type"]["enum"] == [
        "person", "organization", "location",
        "date", "money", "other",
    ]


def test_strip_handles_deeply_nested_schema() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "a": {
                "type": "object",
                "properties": {
                    "b": {
                        "type": "object",
                        "properties": {
                            "c": {
                                "type": "integer",
                                "minimum": 0,
                            },
                        },
                    },
                },
            },
        },
    }
    result = _strip_unsupported_for_api(schema)
    c = result["properties"]["a"]["properties"]["b"]["properties"]["c"]
    assert "minimum" not in c
    assert c["type"] == "integer"


def test_strip_removes_max_items() -> None:
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 10,
        "uniqueItems": True,
    }
    result = _strip_unsupported_for_api(schema)
    assert "maxItems" not in result
    assert "uniqueItems" not in result


def test_strip_keeps_min_items_zero_or_one() -> None:
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
    }
    result = _strip_unsupported_for_api(schema)
    assert result["minItems"] == 1


def test_strip_removes_min_items_above_one() -> None:
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 5,
    }
    result = _strip_unsupported_for_api(schema)
    assert "minItems" not in result


# --- render_prompt -------------------------------------------------------


def test_render_prompt_substitutes_text() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    prompt = producer.render_prompt(
        b"Hello Alice", {"input_hash": "x" * 64},
    )
    assert "Hello Alice" in prompt
    assert "{text}" not in prompt


# --- call_model ----------------------------------------------------------


def test_call_model_returns_model_response() -> None:
    output = {"format_version": 1, "entities": []}
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )
    response = producer.call_model("test prompt")

    assert isinstance(response, ModelResponse)
    assert response.input_tokens == 150
    assert response.output_tokens == 75
    assert response.cost_usd > 0
    client.messages.create.assert_called_once()


def test_call_model_includes_output_config() -> None:
    output = {"format_version": 1, "entities": []}
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )
    producer.call_model("test prompt")

    call_kwargs = client.messages.create.call_args
    oc = call_kwargs.kwargs.get("output_config") or call_kwargs[1].get(
        "output_config",
    )
    assert oc is not None
    assert oc["format"]["type"] == "json_schema"
    api_schema = oc["format"]["schema"]
    assert "$schema" not in api_schema
    span_start = (
        api_schema["properties"]["entities"]["items"]
        ["properties"]["span"]["properties"]["start"]
    )
    assert "minimum" not in span_start


# --- parse_output --------------------------------------------------------


def test_parse_output_handles_clean_json() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    raw = '{"format_version": 1, "entities": []}'
    result = producer.parse_output(raw)
    assert result == {"format_version": 1, "entities": []}


def test_parse_output_rejects_malformed_json() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    with pytest.raises(json.JSONDecodeError):
        producer.parse_output("not json at all")


# --- post_validate -------------------------------------------------------


def test_post_validate_accepts_valid_spans() -> None:
    text = "Alice works at Acme Corp."
    output = _valid_output_for(text)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    producer.post_validate(output, text.encode())


def test_post_validate_fails_span_out_of_range() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    parsed = {
        "format_version": 1,
        "entities": [
            {"text": "X", "type": "person", "span": {"start": 0, "end": 999}},
        ],
    }
    with pytest.raises(ValueError, match="unresolvable span"):
        producer.post_validate(parsed, b"short")


def test_post_validate_fails_span_text_mismatch() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    parsed = {
        "format_version": 1,
        "entities": [
            {"text": "Bob", "type": "person", "span": {"start": 0, "end": 5}},
        ],
    }
    with pytest.raises(ValueError, match="unresolvable span"):
        producer.post_validate(parsed, b"Alice works here")


def test_post_validate_fails_start_ge_end() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    parsed = {
        "format_version": 1,
        "entities": [
            {"text": "X", "type": "person", "span": {"start": 5, "end": 5}},
        ],
    }
    with pytest.raises(ValueError, match="unresolvable span"):
        producer.post_validate(parsed, b"Hello World")


def test_post_validate_corrects_near_miss_span() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    text = "Alice Johnson works at Acme Corp in London."
    parsed = {
        "format_version": 1,
        "entities": [
            {
                "text": "Acme Corp",
                "type": "organization",
                "span": {"start": 24, "end": 33},
            },
        ],
    }
    producer.post_validate(parsed, text.encode())
    assert parsed["entities"][0]["span"]["start"] == 23
    assert parsed["entities"][0]["span"]["end"] == 32


def test_post_validate_corrects_wildly_off_span() -> None:
    """Global fallback finds entity text when offset is far from correct."""
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    text = "The CEO Maria Santos reported revenue of $4.2 billion."
    parsed = {
        "format_version": 1,
        "entities": [
            {
                "text": "Maria Santos",
                "type": "person",
                "span": {"start": 200, "end": 212},
            },
        ],
    }
    producer.post_validate(parsed, text.encode())
    assert parsed["entities"][0]["span"]["start"] == 8
    assert parsed["entities"][0]["span"]["end"] == 20


def test_post_validate_one_bad_span_fails_whole_source() -> None:
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=MagicMock(),
    )
    text = "Alice Johnson works at Acme Corp."
    parsed = {
        "format_version": 1,
        "entities": [
            {
                "text": "Alice Johnson",
                "type": "person",
                "span": {"start": 0, "end": 13},
                "confidence": 0.9,
            },
            {
                "text": "Nonexistent Name",
                "type": "person",
                "span": {"start": 50, "end": 67},
                "confidence": 0.8,
            },
            {
                "text": "Acme Corp",
                "type": "organization",
                "span": {"start": 23, "end": 32},
                "confidence": 0.85,
            },
        ],
    }
    with pytest.raises(ValueError, match=r"unresolvable span.*Nonexistent"):
        producer.post_validate(parsed, text.encode())


# --- client-side validation catches API-unenforced constraints -----------


def test_client_side_validation_catches_confidence_out_of_range(
    tmp_path: Path,
) -> None:
    """The API doesn't enforce minimum/maximum on confidence, but
    client-side jsonschema validation against the canonical schema does.
    """
    text = "Alice works here"
    src = tmp_path / "doc.txt"
    src.write_text(text, encoding="utf-8")

    output = {
        "format_version": 1,
        "entities": [
            {
                "text": "Alice",
                "type": "person",
                "span": {"start": 0, "end": 5},
                "confidence": 1.5,
            },
        ],
    }
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )

    result = producer.produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert "schema_validation_failed" in (result.error_message or "")


def test_client_side_validation_catches_negative_span(
    tmp_path: Path,
) -> None:
    """The canonical schema has minimum: 0 on span fields; the API
    schema has that stripped.  Client-side validation catches it.
    """
    text = "Alice works here"
    src = tmp_path / "doc.txt"
    src.write_text(text, encoding="utf-8")

    output = {
        "format_version": 1,
        "entities": [
            {
                "text": "Alice",
                "type": "person",
                "span": {"start": -1, "end": 5},
                "confidence": 0.9,
            },
        ],
    }
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )

    result = producer.produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert "schema_validation_failed" in (result.error_message or "")


# --- produce end-to-end -------------------------------------------------


def test_produce_end_to_end_success(tmp_path: Path) -> None:
    text = "Alice works at Acme Corp."
    src = tmp_path / "doc.txt"
    src.write_text(text, encoding="utf-8")

    output = _valid_output_for(text)
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )

    result = producer.produce(src, "a" * 64, {})
    assert result.status == "success"
    assert result.content is not None
    parsed = json.loads(result.content)
    assert parsed["entities"][0]["text"] == "Alice"
    assert result.producer_metadata["prompt_name"] == "entity_extraction_v1"


def test_produce_schema_validation_failure(tmp_path: Path) -> None:
    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")

    bad_output = {"no_format_version": True}
    client = _make_mock_client(bad_output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )

    result = producer.produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert "schema_validation_failed" in (result.error_message or "")


def test_produce_fails_on_unresolvable_span(tmp_path: Path) -> None:
    text = "Alice works here"
    src = tmp_path / "doc.txt"
    src.write_text(text, encoding="utf-8")

    output = {
        "format_version": 1,
        "entities": [
            {
                "text": "Bob",
                "type": "person",
                "span": {"start": 0, "end": 3},
            },
        ],
    }
    client = _make_mock_client(output)
    decl = _make_declaration()
    producer = EntityExtractionProducer(
        declaration=decl, client=client,
    )

    result = producer.produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert "unresolvable span" in (result.error_message or "")


# --- cost estimator ------------------------------------------------------


def test_estimate_cost_returns_positive() -> None:
    decl = _make_declaration()
    estimate = estimate_cost(decl, [1000, 2000, 3000])
    assert isinstance(estimate, CostEstimate)
    assert estimate.total_usd > 0
    assert estimate.per_source_usd > 0
    assert estimate.source_count == 3


def test_estimate_cost_scales_with_input_size() -> None:
    decl = _make_declaration()
    small = estimate_cost(decl, [100])
    large = estimate_cost(decl, [100_000])
    assert large.total_usd > small.total_usd
