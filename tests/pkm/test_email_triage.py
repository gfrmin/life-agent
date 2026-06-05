"""Tests for the ``email_triage`` classifier transform (SPEC §18.8).

Hermetic: a fake ``ModelClient`` returns a canned category, so no Ollama call
happens. Covers the classify contract, the enum constraint (client-side
validation), producer-class dispatch (§18.2 — now three impls), and the
idempotency double-run (§6.2).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration, load_transform_declaration
from pkm.transform_run import run_transform
from pkm.transforms._shared import make_producer
from pkm.transforms.email_triage import EmailTriageProducer

_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pkm" / "examples" / "transforms" / "email_triage" / "v1"
)

_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["format_version", "category", "reason"],
    "properties": {
        "format_version": {"const": 1},
        "category": {
            "type": "string",
            "enum": [
                "personal_work", "transactional", "automated_alert",
                "newsletter_marketing", "status_report", "other",
            ],
        },
        "reason": {"type": "string"},
    },
}

_EMAIL = (
    "From: CI <ci@example.com>\nSubject: UP | build pipeline\n\n"
    "All steps completed successfully.\n- build_step 1322 ok\n"
)


class _FakeClient:
    engine_version = "fake-1"

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=10, output_tokens=5, latency_ms=1, cost_usd=0.0,
        )


class _FakePath:
    def __init__(self, text: str) -> None:
        self._b = text.encode("utf-8")

    def read_bytes(self) -> bytes:
        return self._b

    def __str__(self) -> str:
        return "<email>"


def _decl(*, provider: str = "ollama") -> TransformDeclaration:
    prompt_text = "Classify.\n---\n{text}\n---\n"
    return TransformDeclaration(
        name="email_triage", version="0.1.0",
        producer_class="pkm.transforms.email_triage.EmailTriageProducer",
        model_identity={
            "provider": provider, "model": "qwen2.5:7b-instruct",
            "inference_params": {"temperature": 0.0},
        },
        prompt_name="email_triage_v1", prompt_text=prompt_text,
        prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
        output_schema_name="email_triage_v1", output_schema=_OUTPUT_SCHEMA,
        policies=[], input_producer="email", input_required_status="success",
        declaration_hash=hashlib.sha256(b"email_triage-test-decl").hexdigest(),
    )


def _produce(output: dict[str, Any]) -> ProducerResult:
    producer = EmailTriageProducer(declaration=_decl(), model_client=_FakeClient(output))
    return producer.produce(_FakePath(_EMAIL), "h" * 64, {})


# --- the classify contract ----------------------------------------------------


def test_classifies_and_emits_category() -> None:
    result = _produce({"category": "status_report", "reason": "success digest"})
    assert result.status == "success"
    assert result.content is not None
    parsed = json.loads(result.content.decode("utf-8"))
    assert parsed["format_version"] == 1
    assert parsed["category"] == "status_report"
    assert parsed["reason"] == "success digest"


def test_format_version_injected_when_model_omits_it() -> None:
    producer = EmailTriageProducer(
        declaration=_decl(),
        model_client=_FakeClient({"category": "other", "reason": "x"}),
    )
    parsed = producer.parse_output(json.dumps({"category": "other", "reason": "x"}))
    assert parsed["format_version"] == 1


def test_category_outside_enum_fails_the_source() -> None:
    # Client-side jsonschema.validate enforces the canonical enum even though the
    # grammar would normally prevent it — a belt-and-braces guard.
    result = _produce({"category": "spam", "reason": "nope"})
    assert result.status == "failed"
    assert result.content is None
    assert "schema_validation_failed" in (result.error_message or "")


def test_no_grounding_step() -> None:
    # The classifier quotes nothing, so it has no post_validate override.
    assert EmailTriageProducer.post_validate is EmailTriageProducer.__mro__[1].post_validate


# --- dispatch (§18.2): now three transform producers --------------------------


def test_make_producer_dispatches_email_triage() -> None:
    producer = make_producer(_decl())
    assert isinstance(producer, EmailTriageProducer)
    assert producer.name == "email_triage"


# --- end-to-end via run_transform: idempotency double-run (§6.2) --------------


def _setup_email_root(root: Path) -> Config:
    import shutil

    for subdir in ("transforms", "prompts", "schemas"):
        (root / subdir).mkdir(exist_ok=True)
        for f in (_EXAMPLES_DIR / subdir).iterdir():
            if f.is_file():
                shutil.copy2(f, root / subdir / f.name)
    cfg_path = root / "config.yaml"
    cfg_path.write_text(f"root_dir: {root}\npolicies: {{}}\n", encoding="utf-8")

    source_content = _EMAIL.encode("utf-8")
    source_id = hashlib.sha256(source_content).hexdigest()
    (root / "sources").mkdir(exist_ok=True)
    (root / "sources" / "mail.eml").write_bytes(source_content)
    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, current_path, first_seen, last_seen, size_bytes) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
            [source_id, str(root / "sources" / "mail.eml"), len(source_content)],
        )
        email_ck = compute_cache_key(
            input_hash=source_id, producer_name="email",
            producer_version="1", producer_config={},
        )
        write_artifact(
            root, conn, cache_key=email_ck, input_hash=source_id,
            producer_name="email", producer_version="1", producer_config={},
            result=ProducerResult(
                status="success", content=source_content, content_type="text/plain",
                content_encoding="utf-8", error_message=None,
                producer_metadata={"completion": "complete"},
            ),
        )
    from pkm.config import load_config

    return load_config(cfg_path)


def _producer() -> EmailTriageProducer:
    return EmailTriageProducer(
        declaration=load_transform_declaration(_EXAMPLES_DIR, "email_triage"),
        model_client=_FakeClient({"category": "status_report", "reason": "digest"}),
    )


def test_run_transform_writes(migrated_root: Path) -> None:
    config = _setup_email_root(migrated_root)
    result = run_transform(
        migrated_root, config, "email_triage", producer_override=_producer(),
    )
    assert result.total_sources == 1
    assert result.succeeded == 1
    assert result.failed == 0


def test_run_transform_second_run_is_cache_hit(migrated_root: Path) -> None:
    config = _setup_email_root(migrated_root)
    run_transform(migrated_root, config, "email_triage", producer_override=_producer())
    result2 = run_transform(
        migrated_root, config, "email_triage", producer_override=_producer(),
    )
    assert result2.cache_hits == 1
    assert result2.succeeded == 0
    assert result2.failed == 0
