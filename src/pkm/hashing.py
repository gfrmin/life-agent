"""Canonicalisation and cache-key construction.

This module is the single source of truth for every hash in the
system (SPEC §4.3). No other code path is permitted to construct
cache keys or canonicalise data for hashing — it all flows through
``canonical_json`` and ``compute_cache_key``.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

_VALID_SCHEMA_VERSIONS = frozenset({1, 2, 3})

EMPTY_HASH = hashlib.sha256(b"").hexdigest()


def canonical_json(obj: Any) -> str:
    """Canonicalise a value to its one-and-only JSON string, for hashing.

    Per SPEC §4.1 the canonical form is::

        json.dumps(obj, sort_keys=True, separators=(',', ':'),
                   ensure_ascii=False)

    Any deviation is a correctness bug: it changes cache keys and
    silently fragments the cache.

    Args:
        obj: A JSON-serialisable value composed of dict, list, str,
            int, float, bool, and None only. No bytes, no datetime,
            no custom classes — the canonical form must be exactly
            reproducible by any stdlib consumer.

    Returns:
        The canonical JSON string. Stable across Python versions, OS
        and locales. ``ensure_ascii=False`` is deliberate so non-ASCII
        strings appear as their UTF-8 characters rather than
        ``\\uXXXX`` escapes; this keeps the canonicalisation aligned
        with the on-disk encoding.

    Raises:
        TypeError: if ``obj`` contains a value ``json.dumps`` cannot
            encode. Custom encoders are NOT registered — unencodable
            values are a caller bug and must surface loudly.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_model_identity_hash(model_identity: dict[str, Any]) -> str:
    """SHA-256 hex of the canonical-JSON form of a model identity dict."""
    return hashlib.sha256(
        canonical_json(model_identity).encode("utf-8")
    ).hexdigest()


def compute_cache_key(
    input_hash: str,
    producer_name: str,
    producer_version: str,
    producer_config: dict[str, Any],
    *,
    schema_version: int = 1,
    model_identity: dict[str, Any] | None = None,
    prompt_hash: str | None = None,
    engine_version: str | None = None,
    prompt_template_hash: str | None = None,
    output_schema: dict[str, Any] | None = None,
) -> str:
    """Compute the cache key for an artifact — the ONE function that
    constructs cache keys anywhere in the system (SPEC §4.3).

    ``schema_version`` selects the payload format (monotonic format
    discriminator, SPEC v0.2.0 §17.1 / v0.3.0 §29):

    - **1** (v0.1.x extractors): 5-field payload; all transform/
      hardened kwargs must be ``None``.
    - **2** (v0.2.0 transforms): adds ``model_identity_hash`` and
      ``prompt_hash`` (hash of the *rendered* prompt). Both
      ``model_identity`` and ``prompt_hash`` required; the v0.3.0
      hardened kwargs must be ``None``.
    - **3** (v0.3.0 hardened transforms, SPEC v0.3.0 §29): adds
      ``model_identity_hash``, ``engine_version``,
      ``prompt_template_hash`` (the *template*, not the rendered
      prompt — the binding is the input, already in ``input_hash``),
      and ``output_schema_hash``. Requires ``model_identity``,
      ``engine_version``, ``prompt_template_hash``, and
      ``output_schema``; ``prompt_hash`` must be ``None``.

    The default is 1 so existing v0.1.x call sites are unchanged.
    Adding ``schema_version: 3`` leaves the 1 and 2 payloads
    byte-identical — existing extractor and legacy-transform keys are
    unaffected. The validation backstop catches any mismatch between
    ``schema_version`` and the provided kwargs.

    Returns:
        64-character lowercase SHA-256 hex.

    Raises:
        ValueError: if ``input_hash``, ``prompt_hash``, or
            ``prompt_template_hash`` is not 64 lowercase hex; if
            ``schema_version`` is unsupported; if the kwargs don't
            match the schema_version contract.
        TypeError: if ``producer_config``, ``model_identity``, or
            ``output_schema`` is not canonical-JSON-encodable.
    """
    if not _HEX64_RE.match(input_hash):
        raise ValueError(
            f"input_hash must be exactly 64 lowercase hex characters, "
            f"got {input_hash!r}"
        )

    if schema_version not in _VALID_SCHEMA_VERSIONS:
        raise ValueError(
            f"schema_version must be one of {sorted(_VALID_SCHEMA_VERSIONS)}, "
            f"got {schema_version!r}"
        )

    _v3_fields = (engine_version, prompt_template_hash, output_schema)

    if schema_version == 1:
        if (
            model_identity is not None
            or prompt_hash is not None
            or any(f is not None for f in _v3_fields)
        ):
            raise ValueError(
                "schema_version 1 does not accept model_identity, "
                "prompt_hash, or any hardened transform field — all "
                "must be None for v0.1.x extractors"
            )
    elif schema_version == 2:
        if model_identity is None or prompt_hash is None:
            raise ValueError(
                "schema_version 2 requires both model_identity and "
                "prompt_hash — neither may be None for transforms"
            )
        if not _HEX64_RE.match(prompt_hash):
            raise ValueError(
                f"prompt_hash must be exactly 64 lowercase hex characters, "
                f"got {prompt_hash!r}"
            )
        if any(f is not None for f in _v3_fields):
            raise ValueError(
                "schema_version 2 does not accept the v0.3.0 hardened "
                "fields (engine_version, prompt_template_hash, "
                "output_schema) — use schema_version 3"
            )
    else:  # schema_version == 3
        if (
            model_identity is None
            or engine_version is None
            or prompt_template_hash is None
            or output_schema is None
        ):
            raise ValueError(
                "schema_version 3 requires model_identity, "
                "engine_version, prompt_template_hash, and "
                "output_schema — none may be None for hardened transforms"
            )
        if prompt_hash is not None:
            raise ValueError(
                "schema_version 3 does not accept prompt_hash — it uses "
                "prompt_template_hash (the binding is the input, already "
                "in input_hash)"
            )
        if not _HEX64_RE.match(prompt_template_hash):
            raise ValueError(
                f"prompt_template_hash must be exactly 64 lowercase hex "
                f"characters, got {prompt_template_hash!r}"
            )

    producer_config_hash = hashlib.sha256(
        canonical_json(producer_config).encode("utf-8")
    ).hexdigest()

    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "input_hash": input_hash,
        "producer_name": producer_name,
        "producer_version": producer_version,
        "producer_config_hash": producer_config_hash,
    }

    if schema_version == 2:
        assert model_identity is not None  # guaranteed by validation
        assert prompt_hash is not None
        payload["model_identity_hash"] = compute_model_identity_hash(
            model_identity
        )
        payload["prompt_hash"] = prompt_hash
    elif schema_version == 3:
        assert model_identity is not None  # guaranteed by validation
        assert output_schema is not None
        payload["model_identity_hash"] = compute_model_identity_hash(
            model_identity
        )
        payload["engine_version"] = engine_version
        payload["prompt_template_hash"] = prompt_template_hash
        payload["output_schema_hash"] = hashlib.sha256(
            canonical_json(output_schema).encode("utf-8")
        ).hexdigest()

    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
