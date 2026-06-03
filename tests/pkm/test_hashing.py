"""Contract tests for ``pkm.hashing``.

These tests are the keel of the system: every cache key, every
producer config hash, and every canonicalised payload that ever gets
written to ``meta.json`` or to the catalogue flows through the two
functions exercised here. They are deliberately written BEFORE the
implementation exists so the contract is fixed first and the
implementation conforms to it, not the other way around.

Correspondence to SPEC:

- Test 1  → SPEC §4.1 (canonicalisation invariants).
- Test 1b → SPEC §4.1 (``ensure_ascii=False`` detail — the subtle
  bit most likely to silently drift via misreading).
- Test 2  → SPEC §4.2, §4.3, §14.4 (single hashing function,
  input isolation, full 64-char lowercase hex output).
"""

from __future__ import annotations

import json
import re

import pytest

from pkm.hashing import canonical_json, compute_cache_key

HEX64 = re.compile(r"^[0-9a-f]{64}$")


# --- Test 1 -----------------------------------------------------------------

def test_canonical_json_is_order_insensitive_and_deterministic() -> None:
    """``canonical_json`` is stable under dict key reordering, across
    repeat calls, and rejects non-JSON values with ``TypeError`` rather
    than silently coercing them.
    """
    # Dict key order does not affect output.
    assert (
        canonical_json({"b": 1, "a": 2})
        == canonical_json({"a": 2, "b": 1})
        == '{"a":2,"b":1}'
    )

    # Nested dicts are also sorted.
    nested_a = {"z": {"b": 1, "a": 2}, "a": []}
    nested_b = {"a": [], "z": {"a": 2, "b": 1}}
    assert canonical_json(nested_a) == canonical_json(nested_b)

    # Lists preserve their own order — only dict keys are sorted.
    assert canonical_json([3, 1, 2]) == "[3,1,2]"
    assert canonical_json([3, 1, 2]) != canonical_json([1, 2, 3])

    # No whitespace between separators — tightest possible form.
    assert canonical_json({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'

    # Idempotent across many calls.
    obj = {"x": 1, "y": [1, 2, {"a": True, "b": None}]}
    first = canonical_json(obj)
    for _ in range(10):
        assert canonical_json(obj) == first

    # Non-JSON-serialisable inputs raise TypeError — no silent fallback,
    # no custom encoder registration. These are caller bugs.
    with pytest.raises(TypeError):
        canonical_json({"k": {1, 2, 3}})  # set is not JSON
    with pytest.raises(TypeError):
        canonical_json({"k": b"bytes"})   # bytes is not JSON
    with pytest.raises(TypeError):
        canonical_json(object())          # arbitrary object


# --- Test 1b ----------------------------------------------------------------

def test_canonical_json_preserves_utf8_for_non_ascii() -> None:
    """Non-ASCII strings are emitted as their UTF-8 characters, not as
    ``\\uXXXX`` escapes (SPEC §4.1, ``ensure_ascii=False``).

    This is the subtle bit of the canonicalisation most likely to
    silently drift from the spec via a misreading. A drift here would
    silently fragment the cache across any machine that interpreted the
    ensure_ascii flag differently.
    """
    obj = {"k": "café", "arrow": "→", "emoji": "🦀"}
    serialised = canonical_json(obj)

    # Literal UTF-8 characters appear in the output.
    assert "café" in serialised
    assert "→" in serialised
    assert "🦀" in serialised

    # ASCII-escaped equivalents must NOT appear. The crab emoji
    # U+1F980 sits outside the BMP, so its escaped form would use a
    # UTF-16 surrogate pair; both halves must be absent.
    assert "\\u00e9" not in serialised
    assert "\\u2192" not in serialised
    assert "\\ud83e" not in serialised
    assert "\\udd80" not in serialised

    # Exact expected form for the simple case.
    assert canonical_json({"k": "café"}) == '{"k":"café"}'

    # Round-trip via json.loads returns the original mapping with
    # identical code points.
    round_tripped = json.loads(serialised)
    assert round_tripped == obj


# --- Test 2 -----------------------------------------------------------------

def test_compute_cache_key_is_deterministic_and_input_isolated() -> None:
    """``compute_cache_key`` is the single hashing function (SPEC §4.3).
    It is deterministic, isolates each input, returns 64-char lowercase
    hex (SPEC §14.4), and validates its inputs.
    """
    valid_hash = "a" * 64
    base = dict(
        input_hash=valid_hash,
        producer_name="pandoc",
        producer_version="3.1.9",
        producer_config={"ocr": True, "lang": "eng"},
    )

    key = compute_cache_key(**base)

    # Shape: 64 lowercase hex characters, always.
    assert len(key) == 64
    assert HEX64.match(key), f"cache key is not lowercase hex: {key!r}"

    # Deterministic across repeat calls.
    for _ in range(5):
        assert compute_cache_key(**base) == key

    # Perturbing any one argument produces a different key.
    assert compute_cache_key(**{**base, "input_hash": "b" * 64}) != key
    assert compute_cache_key(**{**base, "producer_name": "docling"}) != key
    assert compute_cache_key(**{**base, "producer_version": "3.1.10"}) != key
    assert (
        compute_cache_key(
            **{**base, "producer_config": {"ocr": False, "lang": "eng"}}
        )
        != key
    )

    # producer_config key order must collapse via canonicalisation:
    # semantically identical config → identical key.
    reordered = {"lang": "eng", "ocr": True}
    assert compute_cache_key(**{**base, "producer_config": reordered}) == key

    # Empty config is a valid input and produces a valid-shape key.
    empty_key = compute_cache_key(
        input_hash=valid_hash,
        producer_name="pandoc",
        producer_version="3.1.9",
        producer_config={},
    )
    assert HEX64.match(empty_key)
    assert empty_key != key  # different config → different key

    # Golden key — pins the exact algorithm. If this changes, the
    # cache key format has changed and every existing cache entry
    # is invalidated. Regenerate only by deliberate decision, with
    # a SPEC version bump (the schema_version field inside the key
    # exists for exactly this purpose, SPEC §4.2).
    assert compute_cache_key(
        input_hash="0" * 64,
        producer_name="pandoc",
        producer_version="3.1.9",
        producer_config={},
    ) == "92d68dd86f12140e5bb00e5b97bba4b37d1c9307ba17f272dcf76b560d41fd70"

    # input_hash must be exactly 64 lowercase hex chars.
    for bad in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, "", "not-a-hash"):
        with pytest.raises(ValueError):
            compute_cache_key(**{**base, "input_hash": bad})

    # Non-JSON-serialisable producer_config raises TypeError (surfaced
    # from canonical_json). It is a caller bug, not something the
    # hashing module silently accommodates.
    with pytest.raises(TypeError):
        compute_cache_key(**{**base, "producer_config": {"bad": {1, 2, 3}}})


# --- Test 3 -----------------------------------------------------------------

def test_schema_version_2_cache_key() -> None:
    """schema_version 2 (transforms) produces a different key from
    schema_version 1, even with the same base fields. The v2 payload
    includes ``model_identity_hash`` and ``prompt_hash``.

    SPEC v0.2.0 §17.1: the two formats are non-overlapping by
    construction.
    """
    valid_hash = "a" * 64
    model_identity = {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "inference_params": {"temperature": 0.0, "max_tokens": 4096},
    }
    prompt_hash = "b" * 64
    base_v2 = dict(
        input_hash=valid_hash,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={"schema": "entity_extraction_v1"},
        schema_version=2,
        model_identity=model_identity,
        prompt_hash=prompt_hash,
    )

    key = compute_cache_key(**base_v2)

    # Shape: 64 lowercase hex.
    assert len(key) == 64
    assert HEX64.match(key)

    # Deterministic.
    for _ in range(5):
        assert compute_cache_key(**base_v2) == key

    # Different from schema_version 1 with same base fields.
    key_v1 = compute_cache_key(
        input_hash=valid_hash,
        producer_name="entity_extraction",
        producer_version="0.1.0",
        producer_config={"schema": "entity_extraction_v1"},
    )
    assert key != key_v1

    # Perturbing model_identity produces a different key.
    changed_model = {**model_identity, "model": "claude-sonnet-4-6"}
    assert compute_cache_key(**{**base_v2, "model_identity": changed_model}) != key

    # Perturbing prompt_hash produces a different key.
    assert compute_cache_key(**{**base_v2, "prompt_hash": "c" * 64}) != key

    # model_identity key order collapses via canonicalisation.
    reordered_model = {
        "model": "claude-haiku-4-5",
        "inference_params": {"max_tokens": 4096, "temperature": 0.0},
        "provider": "anthropic",
    }
    assert compute_cache_key(**{**base_v2, "model_identity": reordered_model}) == key

    # Golden key for v2 — pins the algorithm. If this changes, every
    # existing transform cache entry is invalidated.
    assert compute_cache_key(
        input_hash="0" * 64,
        producer_name="test",
        producer_version="0.1.0",
        producer_config={},
        schema_version=2,
        model_identity={"provider": "stub", "model": "stub"},
        prompt_hash="0" * 64,
    ) == "9277a58a0cf91e6292da4aaa744e4bb44c90da30f4377d1c1e721c3e9148db7c"


# --- Test 4 -----------------------------------------------------------------

def test_schema_version_validation() -> None:
    """schema_version discriminator enforces that v1 and v2 payloads
    use the correct combination of arguments.
    """
    valid_hash = "a" * 64
    model_identity = {"provider": "stub", "model": "stub"}

    # v1 rejects model_identity.
    with pytest.raises(ValueError, match=r"schema_version.*1"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="pandoc",
            producer_version="3.1.9",
            producer_config={},
            schema_version=1,
            model_identity=model_identity,
        )

    # v1 rejects prompt_hash.
    with pytest.raises(ValueError, match=r"schema_version.*1"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="pandoc",
            producer_version="3.1.9",
            producer_config={},
            schema_version=1,
            prompt_hash=valid_hash,
        )

    # v2 requires model_identity — missing raises.
    with pytest.raises(ValueError, match=r"schema_version.*2"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=2,
            prompt_hash=valid_hash,
        )

    # v2 requires prompt_hash — missing raises.
    with pytest.raises(ValueError, match=r"schema_version.*2"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=2,
            model_identity=model_identity,
        )

    # v2 rejects the v0.3.0 hardened fields.
    with pytest.raises(ValueError, match=r"schema_version 2"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=2,
            model_identity=model_identity,
            prompt_hash=valid_hash,
            engine_version="0.97.0",
        )

    # v3 requires all four hardened inputs — missing any raises.
    _v3_required = (
        "model_identity", "engine_version", "prompt_template_hash", "output_schema",
    )
    for missing in _v3_required:
        kwargs = dict(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=3,
            model_identity=model_identity,
            engine_version="0.97.0",
            prompt_template_hash=valid_hash,
            output_schema={"type": "object"},
        )
        del kwargs[missing]
        with pytest.raises(ValueError, match=r"schema_version 3"):
            compute_cache_key(**kwargs)  # type: ignore[arg-type]

    # v3 rejects prompt_hash (it uses prompt_template_hash).
    with pytest.raises(ValueError, match=r"schema_version 3"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=3,
            model_identity=model_identity,
            engine_version="0.97.0",
            prompt_template_hash=valid_hash,
            output_schema={"type": "object"},
            prompt_hash=valid_hash,
        )

    # v3 prompt_template_hash must be 64 lowercase hex.
    with pytest.raises(ValueError, match=r"prompt_template_hash"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=3,
            model_identity=model_identity,
            engine_version="0.97.0",
            prompt_template_hash="not-hex",
            output_schema={"type": "object"},
        )

    # Unsupported schema_version raises.
    with pytest.raises(ValueError, match=r"schema_version"):
        compute_cache_key(
            input_hash=valid_hash,
            producer_name="test",
            producer_version="0.1.0",
            producer_config={},
            schema_version=99,
        )


# --- Test 4b ----------------------------------------------------------------

def test_schema_version_3_hardened_cache_key() -> None:
    """schema_version 3 (SPEC v0.3.0 §29) hardens the transform key with
    ``engine_version``, ``prompt_template_hash`` (the template, not the
    rendered prompt), and ``output_schema_hash``. Each is part of the
    event identity (PRINCIPLES §2): changing any of them is a different
    event and MUST change the key.
    """
    valid_hash = "a" * 64
    model_identity = {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "inference_params": {"temperature": 0.0, "max_tokens": 4096},
    }
    output_schema = {
        "type": "object",
        "required": ["entities"],
        "properties": {"entities": {"type": "array"}},
    }
    base_v3 = dict(
        input_hash=valid_hash,
        producer_name="entity_extraction",
        producer_version="0.4.0",
        producer_config={},
        schema_version=3,
        model_identity=model_identity,
        engine_version="0.97.0",
        prompt_template_hash="b" * 64,
        output_schema=output_schema,
    )

    key = compute_cache_key(**base_v3)
    assert len(key) == 64 and HEX64.match(key)

    # Deterministic; identical resolution agrees.
    for _ in range(5):
        assert compute_cache_key(**base_v3) == key

    # Distinct from schema_version 1 and 2 with the same base fields.
    key_v1 = compute_cache_key(
        input_hash=valid_hash,
        producer_name="entity_extraction",
        producer_version="0.4.0",
        producer_config={},
    )
    key_v2 = compute_cache_key(
        input_hash=valid_hash,
        producer_name="entity_extraction",
        producer_version="0.4.0",
        producer_config={},
        schema_version=2,
        model_identity=model_identity,
        prompt_hash="b" * 64,
    )
    assert key != key_v1
    assert key != key_v2

    # Each hardened input independently changes the key.
    assert compute_cache_key(**{**base_v3, "engine_version": "0.98.0"}) != key
    assert compute_cache_key(**{**base_v3, "prompt_template_hash": "c" * 64}) != key
    changed_schema = {**output_schema, "additionalProperties": False}
    assert compute_cache_key(**{**base_v3, "output_schema": changed_schema}) != key
    other_model = {**model_identity, "model": "x"}
    assert compute_cache_key(**{**base_v3, "model_identity": other_model}) != key
    # input change flows through input_hash (the binding lives there).
    assert compute_cache_key(**{**base_v3, "input_hash": "d" * 64}) != key

    # output_schema key order collapses via canonicalisation.
    reordered_schema = {
        "properties": {"entities": {"type": "array"}},
        "required": ["entities"],
        "type": "object",
    }
    assert compute_cache_key(**{**base_v3, "output_schema": reordered_schema}) == key

    # Golden key — pins the v3 algorithm. Regenerate only by deliberate
    # decision with a SPEC bump (the schema_version discriminator exists
    # for exactly this, SPEC v0.3.0 §29.2).
    assert compute_cache_key(
        input_hash="0" * 64,
        producer_name="test",
        producer_version="0.1.0",
        producer_config={},
        schema_version=3,
        model_identity={"provider": "stub", "model": "stub"},
        engine_version="0.0.0",
        prompt_template_hash="0" * 64,
        output_schema={"type": "object"},
    ) == "4f06b22e18425f40975096c9cf9eff7511bf170ac68797cf760b085f99618fd5"


# --- Test 5 -----------------------------------------------------------------

def test_compute_model_identity_hash() -> None:
    """``compute_model_identity_hash`` is deterministic and order-
    insensitive, matching the canonical-JSON rule.
    """
    from pkm.hashing import compute_model_identity_hash

    model_a = {
        "provider": "anthropic",
        "model": "claude-haiku-4-5",
        "inference_params": {"temperature": 0.0, "max_tokens": 4096},
    }
    model_b = {
        "model": "claude-haiku-4-5",
        "inference_params": {"max_tokens": 4096, "temperature": 0.0},
        "provider": "anthropic",
    }

    hash_a = compute_model_identity_hash(model_a)
    hash_b = compute_model_identity_hash(model_b)

    assert HEX64.match(hash_a)
    assert hash_a == hash_b

    # Different model → different hash.
    model_c = {**model_a, "model": "claude-sonnet-4-6"}
    assert compute_model_identity_hash(model_c) != hash_a
