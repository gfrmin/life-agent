"""Transform composition / chaining (SPEC §18.7).

Proves a transform can consume **another transform's** output — the substrate
honestly composes (`email → action_items → item_count`). The seed is realistic:
the `action_items` artifact's ``input_hash`` is the hash of the *email artifact's
content* (the body text), **not** the source id, so the old source-anchored
resolver (`FROM sources JOIN artifacts ON input_hash = source_id`) would drop it
— this test is red until `_find_eligible_sources` is generalised (§18.7) and the
lineage ``role`` is taken from the declaration's ``input.role`` (§18.4).

Hermetic: a trivial in-test ``TransformProducer`` (a generic "count the items"
perspective) stands in for a real model, injected via ``producer_override``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config, load_config
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration
from pkm.transform_run import _EligibleSource, _find_eligible_sources, run_transform

# Realistic two-layer seed: a raw email source, an `email` extractor artifact
# whose CONTENT is the extracted body (distinct bytes from the raw source), and
# an `action_items` transform artifact over that body.
_RAW_EMAIL = (
    b"From: dana@example.com\r\nSubject: Lease\r\n\r\n"
    b"Please pay the deposit by Friday.\r\n"
)
_BODY = b"Please pay the deposit by Friday."  # email artifact content != raw source
_ITEMS = [{"action_phrase": "Pay the deposit", "source_quote": "pay the deposit"}]

_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["format_version", "n_items"],
    "properties": {
        "format_version": {"const": 1},
        "n_items": {"type": "integer"},
    },
    "additionalProperties": False,
}


class _ItemCountProducer(TransformProducer):
    """A generic, single-purpose transform: count the items in its input.

    Demonstrates chaining without a model — its input is the upstream
    ``action_items`` artifact's JSON; its output is a derived perspective.
    """

    name = "item_count"
    version = "0.1.0"
    prompt_name = "item_count_v1"
    engine_version = "test-item-count-v1"

    def __init__(self) -> None:
        self.model_identity = {
            "provider": "ollama", "model": "test-model",
            "inference_params": {"temperature": 0.0},
        }
        self.output_schema = _OUTPUT_SCHEMA

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return input_content.decode("utf-8")

    def call_model(self, prompt: str) -> ModelResponse:
        data = json.loads(prompt)
        n = len(data.get("action_items", []))
        return ModelResponse(
            raw_text=json.dumps({"format_version": 1, "n_items": n}),
            input_tokens=1, output_tokens=1, latency_ms=0, cost_usd=0.0,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)


def _decl(*, producer: str, role: str = "source_text") -> TransformDeclaration:
    """A minimal declaration for a direct ``_find_eligible_sources`` call."""
    return TransformDeclaration(
        name="item_count",
        version="0.1.0",
        producer_class="tests.item_count.ItemCountProducer",
        model_identity={"provider": "ollama", "model": "test-model"},
        prompt_name="item_count_v1",
        prompt_text="Count the items.\n",
        prompt_hash=hashlib.sha256(b"Count the items.\n").hexdigest(),
        output_schema_name="item_count_v1",
        output_schema=_OUTPUT_SCHEMA,
        policies=[],
        input_producer=producer,
        input_role=role,
        input_required_status="success",
        declaration_hash=hashlib.sha256(b"item_count-test-decl").hexdigest(),
    )


def _seed_chain(root: Path) -> tuple[str, str, str, str]:
    """Seed source → email artifact → action_items artifact.

    Returns ``(source_id, source_path, email_ck, action_items_ck)``.
    """
    (root / "sources").mkdir(parents=True, exist_ok=True)
    source_id = hashlib.sha256(_RAW_EMAIL).hexdigest()
    source_path = root / "sources" / "lease.eml"
    source_path.write_bytes(_RAW_EMAIL)

    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, current_path, first_seen, last_seen, size_bytes) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
            [source_id, str(source_path), len(_RAW_EMAIL)],
        )
        conn.execute(
            "INSERT OR IGNORE INTO source_tags (source_id, tag) VALUES (?, ?)",
            [source_id, "mail"],
        )

        email_ck = compute_cache_key(
            input_hash=source_id, producer_name="email",
            producer_version="1", producer_config={},
        )
        write_artifact(
            root, conn, cache_key=email_ck, input_hash=source_id,
            producer_name="email", producer_version="1", producer_config={},
            result=ProducerResult(
                status="success", content=_BODY, content_type="text/plain",
                content_encoding="utf-8", error_message=None,
                producer_metadata={
                    "completion": "complete",
                    "message_id": "<lease-1@example.com>", "subject": "Lease",
                },
            ),
        )

        # The transform's input is the email artifact CONTENT, so its input_hash
        # is sha256(body) — NOT the source id. This is what the old resolver dropped.
        ai_input_hash = hashlib.sha256(_BODY).hexdigest()
        assert ai_input_hash != source_id  # guard the realism of the seed
        ai_content = json.dumps(
            {"format_version": 1, "action_items": _ITEMS}
        ).encode("utf-8")
        ai_ck = compute_cache_key(
            input_hash=ai_input_hash, producer_name="action_items",
            producer_version="0.1.0", producer_config={},
        )
        write_artifact(
            root, conn, cache_key=ai_ck, input_hash=ai_input_hash,
            producer_name="action_items", producer_version="0.1.0",
            producer_config={},
            result=ProducerResult(
                status="success", content=ai_content,
                content_type="application/json", content_encoding="utf-8",
                error_message=None,
                producer_metadata={"completion": "complete"},
            ),
            lineage=[{"cache_key": email_ck, "role": "source_text"}],
        )

    return source_id, str(source_path), email_ck, ai_ck


def _write_item_count_declaration(root: Path) -> Config:
    """Write the chained transform's declaration files + a minimal config."""
    for d in ("transforms", "prompts", "schemas"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "prompts" / "item_count_v1.txt").write_text(
        "Count the action items.\n", encoding="utf-8",
    )
    (root / "schemas" / "item_count_v1.json").write_text(
        json.dumps(_OUTPUT_SCHEMA), encoding="utf-8",
    )
    (root / "transforms" / "item_count.yaml").write_text(
        "name: item_count\n"
        "version: 0.1.0\n"
        "producer_class: tests.item_count.ItemCountProducer\n"
        "model:\n"
        "  provider: ollama\n"
        "  model: test-model\n"
        "  inference_params: {temperature: 0}\n"
        "prompt:\n"
        "  name: item_count_v1\n"
        "  file: prompts/item_count_v1.txt\n"
        "output_schema:\n"
        "  name: item_count_v1\n"
        "  file: schemas/item_count_v1.json\n"
        "policies: []\n"
        "input:\n"
        "  producer: action_items\n"
        "  role: extracted_actions\n"
        "  required_status: success\n",
        encoding="utf-8",
    )
    cfg_path = root / "config.yaml"
    cfg_path.write_text(f"root_dir: {root}\npolicies: {{}}\n", encoding="utf-8")
    return load_config(cfg_path)


# --- the chain runs end to end -------------------------------------------------


def test_transform_consumes_another_transforms_output(migrated_root: Path) -> None:
    root = migrated_root
    _source_id, _path, _email_ck, ai_ck = _seed_chain(root)
    config = _write_item_count_declaration(root)

    result = run_transform(
        root, config, "item_count", producer_override=_ItemCountProducer(),
    )

    # The action_items artifact was found as an eligible input (chaining works).
    assert result.total_sources == 1
    assert result.succeeded == 1
    assert result.failed == 0

    # The chain edge is recorded with the DECLARED role, pointing at the
    # upstream action_items artifact (not its source).
    with open_catalogue(root) as conn:
        rows = conn.execute(
            "SELECT artifact_cache_key, role FROM artifact_lineage "
            "WHERE input_cache_key = ?",
            [ai_ck],
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][1] == "extracted_actions"


def test_chained_transform_is_idempotent(migrated_root: Path) -> None:
    root = migrated_root
    _seed_chain(root)
    config = _write_item_count_declaration(root)

    run_transform(root, config, "item_count", producer_override=_ItemCountProducer())
    result2 = run_transform(
        root, config, "item_count", producer_override=_ItemCountProducer(),
    )

    assert result2.cache_hits == 1
    assert result2.succeeded == 0
    assert result2.failed == 0


# --- regression: primary resolution unchanged; transform-input resolves --------


def test_find_eligible_sources_primary_unchanged_and_transform_input(
    migrated_root: Path,
) -> None:
    root = migrated_root
    source_id, source_path, email_ck, ai_ck = _seed_chain(root)

    with open_catalogue(root) as conn:
        primary = _find_eligible_sources(conn, _decl(producer="email"))
        chained = _find_eligible_sources(
            conn, _decl(producer="action_items", role="extracted_actions"),
        )

    # Primary (email) input is unchanged: it still carries full source identity.
    assert len(primary) == 1
    (p,) = primary
    assert p == _EligibleSource(
        source_id=source_id,
        current_path=source_path,
        tags=frozenset({"mail"}),
        extractor_cache_key=email_ck,
    )

    # Transform-output input now resolves: no source row, so source-derived
    # fields are empty and identity falls back to the input artifact's cache_key.
    assert len(chained) == 1
    (c,) = chained
    assert c.extractor_cache_key == ai_ck
    assert c.source_id == ai_ck
    assert c.current_path == ""
    assert c.tags == frozenset()
