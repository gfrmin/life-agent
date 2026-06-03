"""Tests for ``pkm.transform_declaration`` — YAML declaration loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkm.transform_declaration import TransformDeclaration, load_transform_declaration


def _write_declaration(root: Path) -> None:
    """Write a minimal, valid transform declaration to disk."""
    (root / "transforms").mkdir(exist_ok=True)
    (root / "prompts").mkdir(exist_ok=True)
    (root / "schemas").mkdir(exist_ok=True)

    (root / "prompts" / "entity_v1.txt").write_text(
        "Extract entities from the following text:\n{text}",
        encoding="utf-8",
    )
    (root / "schemas" / "entity_v1.json").write_text(
        json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["entities"],
            "properties": {"entities": {"type": "array"}},
        }),
        encoding="utf-8",
    )
    (root / "transforms" / "entity_extraction.yaml").write_text(
        """\
name: entity_extraction
version: "0.1.0"
producer_class: pkm.transforms.entity_extraction.EntityExtractionProducer
model:
  provider: anthropic
  model: claude-haiku-4-5
  inference_params:
    temperature: 0.0
    max_tokens: 4096
prompt:
  name: entity_v1
  file: prompts/entity_v1.txt
output_schema:
  name: entity_v1
  file: schemas/entity_v1.json
policies:
  - cost_gate
input:
  producer: pandoc
  required_status: success
""",
        encoding="utf-8",
    )


def test_load_declaration_round_trip(tmp_path: Path) -> None:
    _write_declaration(tmp_path)
    decl = load_transform_declaration(tmp_path, "entity_extraction")

    assert isinstance(decl, TransformDeclaration)
    assert decl.name == "entity_extraction"
    assert decl.version == "0.1.0"
    expected_class = (
        "pkm.transforms.entity_extraction.EntityExtractionProducer"
    )
    assert decl.producer_class == expected_class
    assert decl.model_identity["provider"] == "anthropic"
    assert decl.prompt_name == "entity_v1"
    assert "Extract entities" in decl.prompt_text
    assert len(decl.prompt_hash) == 64
    assert decl.output_schema_name == "entity_v1"
    assert decl.output_schema["type"] == "object"
    assert decl.policies == ["cost_gate"]
    assert decl.input_producer == "pandoc"
    assert decl.input_required_status == "success"
    assert len(decl.declaration_hash) == 64


def test_declaration_hash_changes_on_edit(tmp_path: Path) -> None:
    _write_declaration(tmp_path)
    decl1 = load_transform_declaration(tmp_path, "entity_extraction")

    yaml_path = tmp_path / "transforms" / "entity_extraction.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    yaml_path.write_text(text.replace("0.1.0", "0.2.0"), encoding="utf-8")
    decl2 = load_transform_declaration(tmp_path, "entity_extraction")

    assert decl1.declaration_hash != decl2.declaration_hash


def test_prompt_hash_changes_on_edit(tmp_path: Path) -> None:
    _write_declaration(tmp_path)
    decl1 = load_transform_declaration(tmp_path, "entity_extraction")

    prompt_path = tmp_path / "prompts" / "entity_v1.txt"
    prompt_path.write_text("Different prompt", encoding="utf-8")
    decl2 = load_transform_declaration(tmp_path, "entity_extraction")

    assert decl1.prompt_hash != decl2.prompt_hash


def test_missing_declaration_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_transform_declaration(tmp_path, "nonexistent")


def test_missing_prompt_file(tmp_path: Path) -> None:
    _write_declaration(tmp_path)
    (tmp_path / "prompts" / "entity_v1.txt").unlink()
    with pytest.raises(FileNotFoundError):
        load_transform_declaration(tmp_path, "entity_extraction")


def test_default_input_required_status(tmp_path: Path) -> None:
    _write_declaration(tmp_path)
    yaml_path = tmp_path / "transforms" / "entity_extraction.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    text = text.replace("input:\n  producer: pandoc\n  required_status: success\n", "")
    yaml_path.write_text(text, encoding="utf-8")

    decl = load_transform_declaration(tmp_path, "entity_extraction")
    assert decl.input_producer is None
    assert decl.input_required_status == "success"
