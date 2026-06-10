"""Demand-driven derivation (SPEC §18.11) — ``pkm.derive``.

Hermetic: counting stub producers, no model. Seeding mirrors
``tests/pkm/test_transform_chaining.py``. The D0 gate is
``test_derive_warm_makes_zero_model_calls``.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config, load_config
from pkm.derive import derive
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform import ModelResponse, TransformProducer

_RAW = b"From: dana@example.com\r\nSubject: Lease\r\n\r\nPay the deposit.\r\n"
_BODY = b"Pay the deposit."

_UPPER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["format_version", "text"],
    "properties": {"format_version": {"const": 1}, "text": {"type": "string"}},
    "additionalProperties": False,
}
_LEN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["format_version", "n"],
    "properties": {"format_version": {"const": 1}, "n": {"type": "integer"}},
    "additionalProperties": False,
}


class _UpperProducer(TransformProducer):
    """Counting stub: JSON-uppercases its input text."""

    name = "t_upper"
    version = "0.1.0"
    prompt_name = "t_upper_v1"
    engine_version = "test-v1"

    def __init__(self) -> None:
        self.model_identity = {
            "provider": "ollama", "model": "test-model",
            "inference_params": {"temperature": 0.0},
        }
        self.output_schema = _UPPER_SCHEMA
        self.calls = 0

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return input_content.decode("utf-8")

    def call_model(self, prompt: str) -> ModelResponse:
        self.calls += 1
        return ModelResponse(
            raw_text=json.dumps({"format_version": 1, "text": prompt.upper()}),
            input_tokens=1, output_tokens=1, latency_ms=0, cost_usd=0.0,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)  # type: ignore[no-any-return]


class _LenProducer(TransformProducer):
    """Counting stub: length of the upstream ``t_upper`` text."""

    name = "t_len"
    version = "0.1.0"
    prompt_name = "t_len_v1"
    engine_version = "test-v1"

    def __init__(self) -> None:
        self.model_identity = {
            "provider": "ollama", "model": "test-model",
            "inference_params": {"temperature": 0.0},
        }
        self.output_schema = _LEN_SCHEMA
        self.calls = 0

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        return input_content.decode("utf-8")

    def call_model(self, prompt: str) -> ModelResponse:
        self.calls += 1
        data = json.loads(prompt)
        return ModelResponse(
            raw_text=json.dumps({"format_version": 1, "n": len(data["text"])}),
            input_tokens=1, output_tokens=1, latency_ms=0, cost_usd=0.0,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)  # type: ignore[no-any-return]


def _write_decl(
    root: Path, name: str, *, input_producer: str,
    schema: dict[str, Any], role: str = "source_text",
    policies: str = "[]",
) -> None:
    for d in ("transforms", "prompts", "schemas"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "prompts" / f"{name}_v1.txt").write_text(
        f"{name} prompt\n", encoding="utf-8",
    )
    (root / "schemas" / f"{name}_v1.json").write_text(
        json.dumps(schema), encoding="utf-8",
    )
    (root / "transforms" / f"{name}.yaml").write_text(
        f"name: {name}\n"
        "version: 0.1.0\n"
        f"producer_class: tests.derive.{name}\n"
        "model:\n"
        "  provider: ollama\n"
        "  model: test-model\n"
        "  inference_params: {temperature: 0}\n"
        "prompt:\n"
        f"  name: {name}_v1\n"
        f"  file: prompts/{name}_v1.txt\n"
        "output_schema:\n"
        f"  name: {name}_v1\n"
        f"  file: schemas/{name}_v1.json\n"
        f"policies: {policies}\n"
        "input:\n"
        f"  producer: {input_producer}\n"
        f"  role: {role}\n"
        "  required_status: success\n",
        encoding="utf-8",
    )


def _seed_email(
    root: Path, *, version: str = "1", body: bytes = _BODY,
) -> tuple[str, str]:
    """Source row + email artifact. Returns ``(source_id, email_cache_key)``."""
    source_id = hashlib.sha256(_RAW).hexdigest()
    sp = root / "sources" / "lease.eml"
    sp.parent.mkdir(exist_ok=True)
    sp.write_bytes(_RAW)
    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, current_path, first_seen, last_seen, size_bytes) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
            [source_id, str(sp), len(_RAW)],
        )
        ck = compute_cache_key(
            input_hash=source_id, producer_name="email",
            producer_version=version, producer_config={},
        )
        write_artifact(
            root, conn, cache_key=ck, input_hash=source_id,
            producer_name="email", producer_version=version, producer_config={},
            result=ProducerResult(
                status="success", content=body, content_type="text/plain",
                content_encoding="utf-8", error_message=None,
                producer_metadata={}),
        )
    return source_id, ck


def _config(root: Path) -> Config:
    p = root / "config.yaml"
    p.write_text(f"root_dir: {root}\npolicies: {{}}\n", encoding="utf-8")
    return load_config(p)


def _chain_root(root: Path) -> None:
    _write_decl(root, "t_upper", input_producer="email", schema=_UPPER_SCHEMA)
    _write_decl(root, "t_len", input_producer="t_upper",
                schema=_LEN_SCHEMA, role="upper_text")


def _overrides() -> tuple[_UpperProducer, _LenProducer, dict[str, TransformProducer]]:
    up, ln = _UpperProducer(), _LenProducer()
    return up, ln, {"t_upper": up, "t_len": ln}


def test_derive_cold_materialises_chain(migrated_root: Path) -> None:
    root = migrated_root
    source_id, email_ck = _seed_email(root)
    _chain_root(root)
    config = _config(root)
    up, ln, ov = _overrides()

    result = derive(root, config, "t_len", source_id=source_id,
                    producer_overrides=ov)

    assert result.status == "success"
    assert [(n.transform_name, n.hit) for n in result.nodes] == [
        ("t_upper", False), ("t_len", False),
    ]
    assert (up.calls, ln.calls) == (1, 1)
    assert result.target_cache_key == result.nodes[1].cache_key

    # Lineage: t_upper ← email artifact, t_len ← t_upper, declared roles.
    with open_catalogue(root) as conn:
        edges = {
            a: (i, r) for a, i, r in conn.execute(
                "SELECT artifact_cache_key, input_cache_key, role "
                "FROM artifact_lineage").fetchall()
        }
    assert edges[result.nodes[0].cache_key] == (email_ck, "source_text")
    assert edges[result.nodes[1].cache_key] == (
        result.nodes[0].cache_key, "upper_text",
    )


def test_derive_warm_makes_zero_model_calls(migrated_root: Path) -> None:
    """THE D0 gate: a warm derive performs zero model calls, writes nothing,
    and the demand log proves it (two misses then two hits)."""
    root = migrated_root
    source_id, _ = _seed_email(root)
    _chain_root(root)
    config = _config(root)

    _, _, ov1 = _overrides()
    r1 = derive(root, config, "t_len", source_id=source_id,
                producer_overrides=ov1)

    with open_catalogue(root) as conn:
        n_before = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]

    up2, ln2, ov2 = _overrides()
    r2 = derive(root, config, "t_len", source_id=source_id,
                producer_overrides=ov2)

    assert r2.status == "success"
    assert all(n.hit for n in r2.nodes)
    assert (up2.calls, ln2.calls) == (0, 0)
    assert r2.target_cache_key == r1.target_cache_key
    with open_catalogue(root) as conn:
        n_after = conn.execute("SELECT count(*) FROM artifacts").fetchone()[0]
    assert n_after == n_before  # idempotent: second derive wrote nothing

    log_files = sorted((root / "logs" / "demand").iterdir())
    entries = [json.loads(line)
               for f in log_files for line in f.read_text("utf-8").splitlines()]
    assert [e["hit"] for e in entries] == [False, False, True, True]
    assert {e["caller"] for e in entries} == {"cli"}


def test_derive_missing_leaf_fails_loudly(migrated_root: Path) -> None:
    root = migrated_root
    _chain_root(root)          # declarations exist, but no email artifact
    config = _config(root)
    up, ln, ov = _overrides()

    result = derive(root, config, "t_len",
                    source_id="ab" * 32, producer_overrides=ov)

    assert result.status == "failed"
    assert "pkm extract" in (result.error_message or "")
    assert (up.calls, ln.calls) == (0, 0)


def test_derive_rebinds_to_current_leaf_and_rederives_suffix(
    migrated_root: Path,
) -> None:
    """§18.10 current-binding: superseding the leaf rederives exactly the
    suffix on next demand; old artifacts remain (append-only)."""
    root = migrated_root
    source_id, _ = _seed_email(root)
    _chain_root(root)
    config = _config(root)

    _, _, ov1 = _overrides()
    r1 = derive(root, config, "t_len", source_id=source_id,
                producer_overrides=ov1)

    time.sleep(0.01)  # strictly later produced_at for the superseding leaf
    _seed_email(root, version="2", body=b"Pay the deposit NOW.")

    up2, ln2, ov2 = _overrides()
    r2 = derive(root, config, "t_len", source_id=source_id,
                producer_overrides=ov2)

    assert r2.status == "success"
    assert [n.hit for n in r2.nodes] == [False, False]   # stale suffix reran
    assert (up2.calls, ln2.calls) == (1, 1)
    assert r2.target_cache_key != r1.target_cache_key
    with open_catalogue(root) as conn:
        n = conn.execute(
            "SELECT count(*) FROM artifacts WHERE producer_name IN "
            "('t_upper', 't_len')").fetchone()[0]
    assert n == 4  # two generations, nothing deleted


def test_derive_explicit_input_key_pins(migrated_root: Path) -> None:
    root = migrated_root
    _, email_ck = _seed_email(root)
    _chain_root(root)
    config = _config(root)
    up, _, ov = _overrides()

    result = derive(root, config, "t_upper",
                    input_cache_key=email_ck, producer_overrides=ov)

    assert result.status == "success"
    assert up.calls == 1
    assert result.nodes[0].input_cache_key == email_ck
