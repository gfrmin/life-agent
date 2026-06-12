"""Tests for the ``doc_subject`` LLM transform (SPEC §18.13).

Hermetic: a fake ``ModelClient`` returns canned classifications — no Ollama
call. Covers the projection contract (person / organisation / generic), the
shape post-validation (subject non-null exactly when the kind names an
entity; violations fail loudly and are never cached), the input cap, and
example-declaration loading.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration, load_transform_declaration
from pkm.transforms._shared import make_producer
from pkm.transforms.doc_subject import _MAX_INPUT_CHARS, DocSubjectProducer

_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pkm" / "examples" / "transforms" / "doc_subject" / "v1"
)

_SCHEMA: dict[str, Any] = json.loads(
    (_EXAMPLES_DIR / "schemas" / "doc_subject_v1.json").read_text(encoding="utf-8")
)


class _FakeClient:
    engine_version = "fake-1"

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output
        self.prompts: list[str] = []

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=10, output_tokens=5, latency_ms=1, cost_usd=0.0,
        )


def _decl(*, input_producer: str = "docling") -> TransformDeclaration:
    prompt_text = "Who is this about?\n---\n{text}\n---\n"
    return TransformDeclaration(
        name=f"doc_subject_{input_producer}", version="0.1.0",
        producer_class="pkm.transforms.doc_subject.DocSubjectProducer",
        model_identity={
            "provider": "ollama", "model": "qwen2.5:7b-instruct",
            "inference_params": {"temperature": 0.0},
        },
        prompt_name="doc_subject_v1", prompt_text=prompt_text,
        prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
        output_schema_name="doc_subject_v1", output_schema=_SCHEMA,
        policies=[], input_producer=input_producer,
        input_required_status="success",
        declaration_hash="0" * 64,
    )


def _produce(tmp_path: Path, text: str, output: dict[str, Any]) -> Any:
    f = tmp_path / "doc.txt"
    f.write_text(text, encoding="utf-8")
    producer = DocSubjectProducer(declaration=_decl(),
                                  model_client=_FakeClient(output))
    return producer.produce(f, "ab" * 32, {})


def test_projects_a_person_subject(tmp_path: Path) -> None:
    result = _produce(tmp_path, "Payslip for J. Example, May 2026",
                      {"subject_kind": "person", "subject": "J. Example"})
    assert result.status == "success", result.error_message
    assert json.loads(result.content) == {
        "format_version": 1, "subject_kind": "person", "subject": "J. Example",
    }


def test_projects_an_organisation_subject(tmp_path: Path) -> None:
    result = _produce(
        tmp_path, "Form 5472 — Example Holdings LLC",
        {"subject_kind": "organisation", "subject": "Example Holdings LLC"},
    )
    assert result.status == "success", result.error_message
    assert json.loads(result.content)["subject_kind"] == "organisation"


def test_generic_is_a_success_with_null_subject(tmp_path: Path) -> None:
    """A blank template is determinately about nobody — a success, not a
    failure (the §18.12 null-date analogue)."""
    result = _produce(tmp_path, "Form B-1: ___ fill in your name ___",
                      {"subject_kind": "generic", "subject": None})
    assert result.status == "success", result.error_message
    assert json.loads(result.content) == {
        "format_version": 1, "subject_kind": "generic", "subject": None,
    }


def test_named_kind_with_null_subject_fails_loudly(tmp_path: Path) -> None:
    """person/organisation MUST carry a name; a shape violation is never cached."""
    result = _produce(tmp_path, "x", {"subject_kind": "person", "subject": None})
    assert result.status == "failed"
    assert "person" in (result.error_message or "")


def test_generic_with_a_subject_fails_loudly(tmp_path: Path) -> None:
    result = _produce(tmp_path, "x",
                      {"subject_kind": "generic", "subject": "J. Example"})
    assert result.status == "failed"
    assert "generic" in (result.error_message or "")


def test_long_input_is_capped_at_the_head(tmp_path: Path) -> None:
    """Subjects lead documents (letterheads, headers): the prompt carries the
    HEAD of long texts, bounded."""
    head = "ID card of J. Example. "
    text = head + ("z" * (3 * _MAX_INPUT_CHARS))
    f = tmp_path / "doc.txt"
    f.write_text(text, encoding="utf-8")
    client = _FakeClient({"subject_kind": "person", "subject": "J. Example"})
    producer = DocSubjectProducer(declaration=_decl(), model_client=client)
    result = producer.produce(f, "ab" * 32, {})
    assert result.status == "success"
    prompt = client.prompts[0]
    assert head in prompt
    assert len(prompt) < _MAX_INPUT_CHARS + 700  # template overhead only


def test_example_declarations_load(tmp_path: Path) -> None:
    """Every shipped doc_subject example declaration loads against a root
    seeded by copying the example tree — yaml ↔ producer_class ↔ schema wiring."""
    for sub in ("transforms", "prompts", "schemas"):
        shutil.copytree(_EXAMPLES_DIR / sub, tmp_path / sub)
    for name in ("doc_subject_docling", "doc_subject_pandoc",
                 "doc_subject_tesseract", "doc_subject_email"):
        decl = load_transform_declaration(tmp_path, name)
        assert decl.output_schema == _SCHEMA
        producer = make_producer(decl)
        assert isinstance(producer, DocSubjectProducer)
        assert producer.name == "doc_subject"
