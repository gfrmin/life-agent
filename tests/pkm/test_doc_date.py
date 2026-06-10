"""Tests for the ``doc_date`` LLM transform (SPEC §18.12).

Hermetic: a fake ``ModelClient`` returns canned dates — no Ollama call.
Covers the projection contract (date / null), the real-date post-validation
(a pattern-valid but impossible date fails loudly and is never cached), the
input cap, producer-class dispatch, and example-declaration loading.
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
from pkm.transforms.doc_date import _MAX_INPUT_CHARS, DocDateProducer

_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pkm" / "examples" / "transforms" / "doc_date" / "v1"
)

_SCHEMA: dict[str, Any] = json.loads(
    (_EXAMPLES_DIR / "schemas" / "doc_date_v1.json").read_text(encoding="utf-8")
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
    prompt_text = "Primary date?\n---\n{text}\n---\n"
    return TransformDeclaration(
        name=f"doc_date_{input_producer}", version="0.1.0",
        producer_class="pkm.transforms.doc_date.DocDateProducer",
        model_identity={
            "provider": "ollama", "model": "qwen2.5:7b-instruct",
            "inference_params": {"temperature": 0.0},
        },
        prompt_name="doc_date_v1", prompt_text=prompt_text,
        prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
        output_schema_name="doc_date_v1", output_schema=_SCHEMA,
        policies=[], input_producer=input_producer,
        input_required_status="success",
        declaration_hash="0" * 64,
    )


def _produce(tmp_path: Path, text: str, output: dict[str, Any]) -> Any:
    f = tmp_path / "doc.txt"
    f.write_text(text, encoding="utf-8")
    producer = DocDateProducer(declaration=_decl(),
                               model_client=_FakeClient(output))
    return producer.produce(f, "ab" * 32, {})


def test_projects_a_date(tmp_path: Path) -> None:
    result = _produce(tmp_path, "Invoice issued 1 May 2026",
                      {"date": "2026-05-01"})
    assert result.status == "success", result.error_message
    assert json.loads(result.content) == {"format_version": 1,
                                          "date": "2026-05-01"}


def test_null_date_is_a_success(tmp_path: Path) -> None:
    result = _produce(tmp_path, "Undated scribble", {"date": None})
    assert result.status == "success", result.error_message
    assert json.loads(result.content) == {"format_version": 1, "date": None}


def test_impossible_date_fails_loudly(tmp_path: Path) -> None:
    """Pattern-valid but not a real date: post_validate rejects (never cached)."""
    result = _produce(tmp_path, "x", {"date": "2026-13-45"})
    assert result.status == "failed"
    assert "2026-13-45" in (result.error_message or "")


def test_long_input_is_capped_at_the_head(tmp_path: Path) -> None:
    """Dates lead documents: the prompt carries the HEAD of long texts, bounded."""
    head = "Issued 2026-05-01. "
    text = head + ("z" * (3 * _MAX_INPUT_CHARS))
    f = tmp_path / "doc.txt"
    f.write_text(text, encoding="utf-8")
    client = _FakeClient({"date": "2026-05-01"})
    producer = DocDateProducer(declaration=_decl(), model_client=client)
    result = producer.produce(f, "ab" * 32, {})
    assert result.status == "success"
    prompt = client.prompts[0]
    assert head in prompt
    assert len(prompt) < _MAX_INPUT_CHARS + 200  # template overhead only


def test_make_producer_dispatches_both_doc_date_classes(tmp_path: Path) -> None:
    decl = _decl()
    producer = make_producer(decl)
    assert isinstance(producer, DocDateProducer)

    from pkm.transforms.doc_date_email import DocDateEmailProducer
    email_decl = TransformDeclaration(
        name="doc_date_email", version="0.1.0",
        producer_class="pkm.transforms.doc_date_email.DocDateEmailProducer",
        model_identity={"provider": "deterministic",
                        "model": "stdlib-email-utils"},
        prompt_name="doc_date_email_v1", prompt_text="p\n",
        prompt_hash="0" * 64,
        output_schema_name="doc_date_v1", output_schema=_SCHEMA,
        policies=[], input_producer="email", input_required_status="success",
        declaration_hash="0" * 64,
    )
    assert isinstance(make_producer(email_decl), DocDateEmailProducer)


def test_example_declarations_load(tmp_path: Path) -> None:
    """Every shipped doc_date example declaration loads against a root seeded
    by copying the example tree — yaml ↔ producer_class ↔ schema wiring."""
    for sub in ("transforms", "prompts", "schemas"):
        shutil.copytree(_EXAMPLES_DIR / sub, tmp_path / sub)
    for name in ("doc_date_email", "doc_date_docling",
                 "doc_date_pandoc", "doc_date_tesseract"):
        decl = load_transform_declaration(tmp_path, name)
        assert decl.output_schema == _SCHEMA
        producer = make_producer(decl) if name != "doc_date_email" else None
        if producer is not None:
            assert producer.name == "doc_date"
