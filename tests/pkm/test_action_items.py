"""Tests for the ``action_items`` transform and the provider seam (SPEC §18).

Stage A is hermetic: a fake ``ModelClient`` returns canned JSON, so no Ollama or
Anthropic call happens. The grounding contract (§18.5), the dispatch (§18.2),
the provider seam (§18.3), and the idempotency double-run (§6.2 / CLAUDE.md) are
all exercised without a live model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration
from pkm.transform_run import run_transform
from pkm.transforms._shared import (
    AnthropicClient,
    OllamaClient,
    derive_api_schema,
    estimate_cost,
    make_model_client,
    make_producer,
    normalise_ws,
    quote_is_grounded,
)
from pkm.transforms.action_items import ActionItemsProducer

_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pkm" / "examples" / "transforms" / "action_items" / "v1"
)

_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["format_version", "action_items"],
    "properties": {
        "format_version": {"const": 1},
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_phrase", "source_quote"],
                "properties": {
                    "action_phrase": {"type": "string"},
                    "source_quote": {"type": "string"},
                },
            },
        },
    },
}


def _decl(
    *, provider: str = "ollama", model: str = "qwen2.5:7b-instruct",
) -> TransformDeclaration:
    prompt_text = "Extract action items.\n---\n{text}\n---\n"
    return TransformDeclaration(
        name="action_items",
        version="0.1.0",
        producer_class="pkm.transforms.action_items.ActionItemsProducer",
        model_identity={
            "provider": provider,
            "model": model,
            "inference_params": {"temperature": 0.0},
        },
        prompt_name="action_items_v1",
        prompt_text=prompt_text,
        prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
        output_schema_name="action_items_v1",
        output_schema=_OUTPUT_SCHEMA,
        policies=[],
        input_producer="email",
        input_required_status="success",
        declaration_hash=hashlib.sha256(b"action_items-test-decl").hexdigest(),
    )


class _FakeClient:
    """A ModelClient that returns a fixed output, regardless of prompt."""

    engine_version = "fake-1"

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            cost_usd=0.0,
        )


_EMAIL = (
    "From: Dana <dana@example.com>\n"
    "Subject: Lease\n\n"
    "Hi, please send the signed lease agreement back by Friday, and don't forget\n"
    "to call the city office about the parking permit before it expires."
)


# --- _shared: pure helpers ----------------------------------------------------


def test_normalise_ws_collapses_runs() -> None:
    assert normalise_ws("a\n  b\tc ") == "a b c"


def test_quote_is_grounded_truth_table() -> None:
    src = "please send the signed lease\nby Friday"
    # exact substring
    assert quote_is_grounded("please send the signed lease", src)
    # spans a line wrap (newline rendered as a space) -> the §18.5 case
    assert quote_is_grounded("signed lease by Friday", src)
    # absent
    assert not quote_is_grounded("wire the deposit", src)
    # empty quote is never grounded
    assert not quote_is_grounded("", src)
    assert not quote_is_grounded("   ", src)


def test_derive_api_schema_drops_format_version_and_closes_objects() -> None:
    api = derive_api_schema(_OUTPUT_SCHEMA)
    assert "format_version" not in api["properties"]
    assert "format_version" not in api["required"]
    assert api["additionalProperties"] is False
    assert "$schema" not in api


def test_estimate_cost_ollama_is_zero() -> None:
    est = estimate_cost(_decl(provider="ollama"), [1000, 2000, 3000])
    assert est.total_usd == 0.0
    assert est.source_count == 3


def test_estimate_cost_anthropic_is_positive() -> None:
    est = estimate_cost(_decl(provider="anthropic"), [1000, 2000])
    assert est.total_usd > 0.0


# --- _shared: the provider seam (§18.3) ---------------------------------------


def test_make_model_client_dispatch_ollama() -> None:
    client = make_model_client(_decl(provider="ollama").model_identity)
    assert isinstance(client, OllamaClient)
    assert client.engine_version == "ollama-chat-v1"


def test_make_model_client_dispatch_anthropic() -> None:
    client = make_model_client(
        _decl(provider="anthropic").model_identity,
        anthropic_client=object(),  # avoids constructing a real SDK client
    )
    assert isinstance(client, AnthropicClient)


def test_make_model_client_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown transform provider"):
        make_model_client({"provider": "groq", "model": "x"})


# --- _shared: dispatch on producer_class (§18.2) ------------------------------


def test_make_producer_dispatches_action_items() -> None:
    producer = make_producer(_decl())
    assert isinstance(producer, ActionItemsProducer)
    assert producer.name == "action_items"


def test_make_producer_dispatches_entity_extraction(monkeypatch) -> None:
    # entity_extraction constructs a real Anthropic client; a dummy key keeps
    # construction offline (no network at construction time).
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-real")
    from pkm.transform_declaration import load_transform_declaration

    ee_examples = (
        Path(__file__).resolve().parents[2] / "docs" / "pkm" / "examples"
        / "transforms" / "entity_extraction" / "v1"
    )
    decl = load_transform_declaration(ee_examples, "entity_extraction")
    producer = make_producer(decl)
    assert producer.name == "entity_extraction"


def test_make_producer_unknown_class_raises() -> None:
    bad = _decl()
    bad = TransformDeclaration(**{**bad.__dict__, "producer_class": "pkm.nope.Nope"})
    with pytest.raises(ValueError, match="unknown producer_class"):
        make_producer(bad)


# --- the producer: grounding contract (§18.5) ---------------------------------


def _produce(output: dict[str, Any], email: str = _EMAIL) -> ProducerResult:
    producer = ActionItemsProducer(
        declaration=_decl(), model_client=_FakeClient(output),
    )
    return producer.produce(_FakePath(email), "h" * 64, {})


class _FakePath:
    """A stand-in for input_path whose read_bytes() returns the email."""

    def __init__(self, text: str) -> None:
        self._b = text.encode("utf-8")

    def read_bytes(self) -> bytes:
        return self._b

    def __str__(self) -> str:
        return "<email>"


def test_grounded_items_succeed() -> None:
    out = {
        "action_items": [
            {
                "action_phrase": "Send the signed lease by Friday",
                "source_quote": "please send the signed lease agreement back by Friday",
            },
        ],
    }
    result = _produce(out)
    assert result.status == "success"
    assert result.content is not None
    parsed = json.loads(result.content.decode("utf-8"))
    assert parsed["format_version"] == 1
    assert len(parsed["action_items"]) == 1


def test_quote_spanning_a_line_wrap_is_grounded() -> None:
    # "Friday, and don't forget to call" crosses the email's hard line wrap;
    # exact str.find would reject it, whitespace-normalised containment accepts.
    out = {
        "action_items": [
            {
                "action_phrase": "Call the city office",
                "source_quote": "don't forget to call the city office",
            },
        ],
    }
    result = _produce(out)
    assert result.status == "success"


def test_ungrounded_quote_fails_the_source() -> None:
    out = {
        "action_items": [
            {
                "action_phrase": "Wire the deposit",
                "source_quote": "wire the deposit to the landlord today",  # not in email
            },
        ],
    }
    result = _produce(out)
    assert result.status == "failed"
    assert result.content is None
    assert "not grounded" in (result.error_message or "")


def test_empty_action_items_is_success() -> None:
    # Restraint: an informational email yields no actions, which is success.
    result = _produce({"action_items": []})
    assert result.status == "success"
    parsed = json.loads(result.content.decode("utf-8"))
    assert parsed["action_items"] == []


def test_format_version_injected_when_model_omits_it() -> None:
    producer = ActionItemsProducer(
        declaration=_decl(),
        model_client=_FakeClient({"action_items": []}),
    )
    parsed = producer.parse_output(json.dumps({"action_items": []}))
    assert parsed["format_version"] == 1


# --- end-to-end via run_transform: idempotency double-run (§6.2) --------------


def _setup_email_root(root: Path) -> Config:
    """Stage the action_items declaration + one email artifact in *root*."""
    import shutil

    for subdir in ("transforms", "prompts", "schemas"):
        (root / subdir).mkdir(exist_ok=True)
        src = _EXAMPLES_DIR / subdir
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, root / subdir / f.name)

    cfg_path = root / "config.yaml"
    cfg_path.write_text(f"root_dir: {root}\npolicies: {{}}\n", encoding="utf-8")

    source_content = _EMAIL.encode("utf-8")
    source_id = hashlib.sha256(source_content).hexdigest()
    source_path = root / "sources" / "mail_0001.eml"
    source_path.write_bytes(source_content)

    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, current_path, first_seen, last_seen, size_bytes) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
            [source_id, str(source_path), len(source_content)],
        )
        conn.execute(
            "INSERT OR IGNORE INTO source_paths (source_id, path, seen_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            [source_id, str(source_path)],
        )
        email_ck = compute_cache_key(
            input_hash=source_id,
            producer_name="email",
            producer_version="1",
            producer_config={},
        )
        write_artifact(
            root, conn,
            cache_key=email_ck,
            input_hash=source_id,
            producer_name="email",
            producer_version="1",
            producer_config={},
            result=ProducerResult(
                status="success",
                content=source_content,
                content_type="text/plain",
                content_encoding="utf-8",
                error_message=None,
                producer_metadata={
                    "completion": "complete",
                    "message_id": "<lease-001@example.com>",
                },
            ),
        )

    from pkm.config import load_config

    return load_config(cfg_path)


def _action_items_producer() -> ActionItemsProducer:
    out = {
        "action_items": [
            {
                "action_phrase": "Send the signed lease by Friday",
                "source_quote": "please send the signed lease agreement back by Friday",
            },
        ],
    }
    # Loaded from disk so the run uses the shipped declaration's identity.
    return ActionItemsProducer(
        declaration=load_transform_declaration_for_test(),
        model_client=_FakeClient(out),
    )


def load_transform_declaration_for_test() -> TransformDeclaration:
    from pkm.transform_declaration import load_transform_declaration

    return load_transform_declaration(_EXAMPLES_DIR, "action_items")


def test_run_transform_grounds_and_writes(migrated_root: Path) -> None:
    config = _setup_email_root(migrated_root)
    result = run_transform(
        migrated_root, config, "action_items",
        producer_override=_action_items_producer(),
    )
    assert result.total_sources == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert not result.blocked


def test_run_transform_second_run_is_cache_hit(migrated_root: Path) -> None:
    config = _setup_email_root(migrated_root)
    run_transform(
        migrated_root, config, "action_items",
        producer_override=_action_items_producer(),
    )
    result2 = run_transform(
        migrated_root, config, "action_items",
        producer_override=_action_items_producer(),
    )
    assert result2.cache_hits == 1
    assert result2.succeeded == 0
    assert result2.failed == 0


def test_run_transform_records_lineage_to_email(migrated_root: Path) -> None:
    config = _setup_email_root(migrated_root)
    run_transform(
        migrated_root, config, "action_items",
        producer_override=_action_items_producer(),
    )
    with open_catalogue(migrated_root) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM artifact_lineage WHERE role = 'source_text'",
        ).fetchone()
    assert row is not None and row[0] == 1
