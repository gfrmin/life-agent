"""Tests for ``pkm.producers.unstructured`` — the Unstructured
extractor (SPEC §7.1, §7.2).

Fixture strategy: a committed ``.pptx`` (a format only Unstructured
handles among the doc producers) plus a committed ``.eml`` kept only
as a byte source for the path-independence check — ``.eml`` itself
moved to the dedicated ``email`` producer in v0.5.0 and is no longer
in Unstructured's supported set. Failure-path fixtures are generated
in ``tmp_path``.

Producer fixture is module-scoped (same pattern as Docling). The
first ``produce`` call initialises NLTK data on demand; sharing
the instance keeps the test file's wall-clock modest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkm.producer import (
    Producer,
    ProducerConfigError,
    ProducerVersionMismatchError,
)
from pkm.producers.unstructured import (
    UnstructuredProducer,
    installed_unstructured_version,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "unstructured"


@pytest.fixture(scope="module")
def unstructured_version() -> str:
    return installed_unstructured_version()


@pytest.fixture(scope="module")
def producer(unstructured_version: str) -> UnstructuredProducer:
    return UnstructuredProducer(
        expected_version=unstructured_version,
        config={"strategy": "auto"},
    )


@pytest.fixture
def unsupported_file(tmp_path: Path) -> Path:
    path = tmp_path / "thing.xyz"
    path.write_bytes(b"extension outside the supported set\n")
    return path


# --- Construction: version and config -----------------------------------


def test_construction_succeeds_with_matching_version(
    unstructured_version: str,
) -> None:
    p = UnstructuredProducer(
        expected_version=unstructured_version,
        config={"strategy": "auto"},
    )
    assert p.name == "unstructured"
    assert p.version == unstructured_version


def test_construction_raises_on_version_mismatch(
    unstructured_version: str,
) -> None:
    wrong = "0.0.0"
    assert wrong != unstructured_version
    with pytest.raises(ProducerVersionMismatchError) as excinfo:
        UnstructuredProducer(
            expected_version=wrong,
            config={"strategy": "auto"},
        )
    assert excinfo.value.producer_name == "unstructured"
    assert excinfo.value.expected == wrong
    assert excinfo.value.installed == unstructured_version


def test_construction_rejects_missing_strategy(
    unstructured_version: str,
) -> None:
    with pytest.raises(ProducerConfigError, match="missing required keys"):
        UnstructuredProducer(
            expected_version=unstructured_version, config={}
        )


def test_construction_rejects_unknown_key(
    unstructured_version: str,
) -> None:
    with pytest.raises(ProducerConfigError, match="unknown keys"):
        UnstructuredProducer(
            expected_version=unstructured_version,
            config={"strategy": "auto", "bogus": 1},
        )


def test_construction_rejects_non_str_strategy(
    unstructured_version: str,
) -> None:
    with pytest.raises(ProducerConfigError, match="must be a str"):
        UnstructuredProducer(
            expected_version=unstructured_version,
            config={"strategy": 1},
        )


def test_construction_rejects_unknown_strategy_value(
    unstructured_version: str,
) -> None:
    with pytest.raises(ProducerConfigError, match="is unknown"):
        UnstructuredProducer(
            expected_version=unstructured_version,
            config={"strategy": "ultra"},
        )


@pytest.mark.parametrize(
    "strategy", ["auto", "fast", "hi_res", "ocr_only"]
)
def test_construction_accepts_all_documented_strategies(
    unstructured_version: str, strategy: str,
) -> None:
    """All four documented strategy values are accepted at
    construction. The producer does not opinionate on which is
    sensible — the user's config.yaml and the routing layer do."""
    UnstructuredProducer(
        expected_version=unstructured_version,
        config={"strategy": strategy},
    )


def test_unstructured_producer_satisfies_producer_protocol(
    producer: UnstructuredProducer,
) -> None:
    assert isinstance(producer, Producer)


# --- Conversion: success paths ------------------------------------------


def test_eml_is_no_longer_supported(
    producer: UnstructuredProducer,
) -> None:
    """v0.5.0: `.eml` moved to the dedicated `email` producer. Unstructured
    no longer claims it — `produce()` rejects it as an unsupported extension,
    and routing (test_routing.py) sends `.eml` to `email` instead."""
    eml = _FIXTURES / "sample.eml"
    result = producer.produce(eml, "a" * 64, {})
    assert ".eml" not in UnstructuredProducer.handled_formats
    assert result.status == "failed"
    assert result.content is None
    assert "supported" in (result.error_message or "").lower()


def test_converts_pptx(producer: UnstructuredProducer) -> None:
    pptx = _FIXTURES / "sample.pptx"
    result = producer.produce(pptx, "a" * 64, {})
    assert result.status == "success"
    assert result.content is not None
    elements = json.loads(result.content)
    assert len(elements) >= 3  # at minimum one per slide


def test_cache_key_is_path_independent(tmp_path: Path) -> None:
    """SPEC §7.1 (v0.1.8): the cache key depends on input *content*,
    not input_path. Two paths carrying byte-identical content MUST
    produce the same cache key, because the input hash
    (``sha256(content_bytes)``) is path-independent by construction
    and the cache key is derived from it plus the producer identity
    and config.

    This test is trivially satisfied by ``compute_cache_key`` as
    implemented — but writing it down ensures a future refactor
    that tried to mix path information into the key (e.g., to
    "improve locality") would red-light immediately.
    """
    import hashlib

    from pkm.hashing import compute_cache_key

    src = _FIXTURES / "sample.eml"
    alt = tmp_path / "different-name.eml"
    alt.write_bytes(src.read_bytes())

    src_hash = hashlib.sha256(src.read_bytes()).hexdigest()
    alt_hash = hashlib.sha256(alt.read_bytes()).hexdigest()
    assert src_hash == alt_hash, "fixture sanity: bytes should match"

    key_src = compute_cache_key(
        input_hash=src_hash,
        producer_name="unstructured",
        producer_version="test",
        producer_config={"strategy": "auto"},
    )
    key_alt = compute_cache_key(
        input_hash=alt_hash,
        producer_name="unstructured",
        producer_version="test",
        producer_config={"strategy": "auto"},
    )
    assert key_src == key_alt


def test_element_ids_are_path_independent(
    producer: UnstructuredProducer, tmp_path: Path,
) -> None:
    """Separate from cache-key path-independence: Unstructured's
    default ``Element.id_to_hash`` bakes ``metadata.filename`` into
    every ``element_id``. Downstream consumers that key on those
    IDs would observe the same content under different paths as
    different content. The producer nulls ``filename``,
    ``file_directory``, ``last_modified`` and recomputes IDs before
    serialising.

    This test pins that fix at the ID level — the concern per SPEC
    §7.1 at v0.1.8 is not byte-equality of the whole output (that's
    no longer required), but rather that content-derived
    identifiers in the output are path-independent. Compares the
    set of ``element_id`` values from two runs on the same content
    at different paths; they must be identical."""
    import json

    src = _FIXTURES / "sample.pptx"
    alt = tmp_path / "different-name.pptx"
    alt.write_bytes(src.read_bytes())

    r_src = producer.produce(src, "a" * 64, {})
    r_alt = producer.produce(alt, "a" * 64, {})
    assert r_src.status == "success"
    assert r_alt.status == "success"
    assert r_src.content is not None and r_alt.content is not None

    ids_src = {e["element_id"] for e in json.loads(r_src.content)}
    ids_alt = {e["element_id"] for e in json.loads(r_alt.content)}
    assert ids_src == ids_alt, (
        "element_ids differ across paths — path-dependent metadata "
        "has leaked into the ID hashes"
    )


# --- Failure paths ------------------------------------------------------


def test_unsupported_extension_is_recorded_as_failed(
    producer: UnstructuredProducer, unsupported_file: Path,
) -> None:
    result = producer.produce(unsupported_file, "a" * 64, {})
    assert result.status == "failed"
    assert result.content is None
    assert result.content_type is None
    assert result.error_message is not None
    assert ".xyz" in result.error_message
    assert "supported" in result.error_message.lower()


def test_produce_wraps_internal_exceptions_without_raising(
    producer: UnstructuredProducer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pin the "never raises" invariant directly: monkeypatch the
    internal partition call to raise a specific exception and
    confirm produce returns failed rather than propagating."""
    src = _FIXTURES / "sample.pptx"

    def _boom(_self: object, _input_path: Path) -> list[object]:
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr(
        UnstructuredProducer, "_partition", _boom, raising=True
    )
    result = producer.produce(src, "a" * 64, {})
    assert result.status == "failed"
    assert result.error_message is not None
    assert "RuntimeError" in result.error_message
    assert "simulated internal failure" in result.error_message
