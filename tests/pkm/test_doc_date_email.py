"""doc_date_email (SPEC §18.12) — deterministic Date-header projection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pkm.transform_declaration import TransformDeclaration
from pkm.transforms.doc_date_email import DocDateEmailProducer

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "pkm" / "examples"
    / "transforms" / "doc_date" / "v1" / "schemas" / "doc_date_v1.json"
)


def _producer() -> DocDateEmailProducer:
    decl = TransformDeclaration(
        name="doc_date_email", version="0.1.0",
        producer_class="pkm.transforms.doc_date_email.DocDateEmailProducer",
        model_identity={"provider": "deterministic",
                        "model": "stdlib-email-utils"},
        prompt_name="doc_date_email_v1",
        prompt_text="parse the Date header\n",
        prompt_hash="0" * 64,
        output_schema_name="doc_date_v1",
        output_schema=json.loads(_SCHEMA_PATH.read_text(encoding="utf-8")),
        policies=[], input_producer="email", input_required_status="success",
        declaration_hash="0" * 64,
    )
    return DocDateEmailProducer(declaration=decl)


def _produce(tmp_path: Path, content: bytes) -> dict[str, Any]:
    f = tmp_path / "email.txt"
    f.write_bytes(content)
    result = _producer().produce(f, "ab" * 32, {})
    assert result.status == "success", result.error_message
    assert result.content is not None
    parsed: dict[str, Any] = json.loads(result.content)
    return parsed


def test_parses_rfc2822_date(tmp_path: Path) -> None:
    out = _produce(tmp_path,
                   b"From: a@b.c\nDate: Tue, 03 Jun 2026 14:22:01 +0300\n"
                   b"Subject: x\n\nbody")
    assert out == {"format_version": 1, "date": "2026-06-03"}


def test_missing_date_header_is_null_success(tmp_path: Path) -> None:
    out = _produce(tmp_path, b"From: a@b.c\nSubject: x\n\nbody")
    assert out == {"format_version": 1, "date": None}


def test_unparseable_date_is_null_success(tmp_path: Path) -> None:
    out = _produce(tmp_path, b"Date: not a date at all\n\nbody")
    assert out == {"format_version": 1, "date": None}


def test_date_line_in_body_is_ignored(tmp_path: Path) -> None:
    """Only the header block (before the first blank line) is consulted."""
    out = _produce(tmp_path,
                   b"From: a@b.c\n\nDate: Tue, 03 Jun 2026 14:22:01 +0300")
    assert out == {"format_version": 1, "date": None}
