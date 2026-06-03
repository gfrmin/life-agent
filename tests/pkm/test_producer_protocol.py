"""Conformance tests for the ``Producer`` protocol (SPEC §7.1).

The protocol states five behavioural invariants. This file exercises
each one by:

  - A ``TrivialProducer`` (positive case) that satisfies all five.
    Asserted to pass ``isinstance(p, Producer)`` and to produce
    equal ``ProducerResult`` values across repeat calls with the
    same inputs.

  - A deliberately-broken producer per invariant (negative case).
    These demonstrate what a violation looks like and confirm the
    corresponding assertion on ``TrivialProducer`` isn't
    tautological.

Invariant 5 (reads nothing outside ``config``) cannot be directly
enforced by a structural ``Protocol``; Python does not sandbox
producer code. It is checked observationally — "output must not
change when an env var does" — with the understanding that full
enforcement is by code review, not by machinery.

This file is deliberately not a reusable conformance framework.
When pandoc, docling, and unstructured are implemented in Step 7,
each gets its own test file exercising its own behaviour. This
file pins the protocol itself.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from pkm.producer import Producer, ProducerResult

# --- Positive: a minimal conforming producer ------------------------------


class TrivialProducer:
    """Reads input_path's bytes and returns them verbatim. Exercises
    all five invariants trivially: output is a pure function of
    input content, exceptions are caught and returned as failures,
    the input file is never written to, and nothing outside
    ``config`` is consulted.
    """

    name = "trivial"
    version = "0.0.1"
    handled_formats = frozenset({".txt"})

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        try:
            content = input_path.read_bytes()
            return ProducerResult(
                status="success",
                content=content,
                content_type="application/octet-stream",
                content_encoding=None,
                error_message=None,
                producer_metadata={"bytes_read": len(content)},
            )
        except Exception as e:
            return ProducerResult(
                status="failed",
                content=None,
                content_type=None,
                content_encoding=None,
                error_message=f"{type(e).__name__}: {e}",
                producer_metadata={},
            )


@pytest.fixture
def sample_input(tmp_path: Path) -> Path:
    p = tmp_path / "input.txt"
    p.write_bytes(b"hello world")
    return p


def test_trivial_producer_satisfies_the_protocol() -> None:
    """Structural: TrivialProducer has name, version, and produce —
    the three names declared by the Protocol — so isinstance
    succeeds. Semantic conformance is the five tests below.
    """
    p = TrivialProducer()
    assert isinstance(p, Producer)
    assert p.name == "trivial"
    assert p.version == "0.0.1"


def test_object_missing_protocol_members_fails_isinstance() -> None:
    """A class missing name/version/produce fails isinstance.
    Proves the isinstance check isn't a blanket true.
    """

    class NotAProducer:
        pass

    assert not isinstance(NotAProducer(), Producer)


# --- Positive: TrivialProducer satisfies the five invariants -------------


def test_invariant_1_content_is_bytes_with_declared_encoding(
    sample_input: Path,
) -> None:
    """Invariant 1: content is bytes (never str) on success; encoding
    is declared explicitly or None for binary artifacts (§14.7).
    """
    r = TrivialProducer().produce(sample_input, "a" * 64, {})
    assert r.status == "success"
    assert isinstance(r.content, bytes)
    assert r.content_encoding is None


def test_invariant_2_exceptions_never_escape(tmp_path: Path) -> None:
    """Invariant 2: exceptions become failed results; produce()
    never raises. TrivialProducer catches and reports failures
    that happen during input read.
    """
    nonexistent = tmp_path / "does_not_exist"
    r = TrivialProducer().produce(nonexistent, "0" * 64, {})
    assert r.status == "failed"
    assert r.error_message is not None
    assert "FileNotFoundError" in r.error_message


def test_invariant_3_output_is_deterministic(sample_input: Path) -> None:
    """Invariant 3: same input content and config → same
    ProducerResult. TrivialProducer's output is a pure function of
    input bytes; repeat calls produce equal results.
    """
    p = TrivialProducer()
    r1 = p.produce(sample_input, "a" * 64, {})
    r2 = p.produce(sample_input, "a" * 64, {})
    assert r1 == r2


def test_invariant_4_input_is_not_modified(sample_input: Path) -> None:
    """Invariant 4: input_path is immutable to the producer.
    Compute the input's hash before and after produce() and assert
    byte-equality.
    """
    before = hashlib.sha256(sample_input.read_bytes()).hexdigest()
    TrivialProducer().produce(sample_input, "a" * 64, {})
    after = hashlib.sha256(sample_input.read_bytes()).hexdigest()
    assert before == after


def test_invariant_5_output_is_independent_of_environment(
    sample_input: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant 5 (observational): setting an env var must not
    change a conforming producer's output. This catches the most
    common leaky-config failure mode (a call to os.environ.get);
    full verification of 'reads nothing outside config' requires
    code review.
    """
    p = TrivialProducer()
    monkeypatch.setenv("PKM_LEAK_TEST", "foo")
    r1 = p.produce(sample_input, "a" * 64, {})
    monkeypatch.setenv("PKM_LEAK_TEST", "bar")
    r2 = p.produce(sample_input, "a" * 64, {})
    assert r1 == r2


# --- Negative: deliberately broken producers per invariant ---------------


class _StringReturningProducer:
    """Returns str instead of bytes (violates invariant 1)."""

    name = "broken-string"
    version = "0.0.1"

    def produce(
        self, input_path: Path, input_hash: str, config: dict[str, Any]
    ) -> ProducerResult:
        return ProducerResult(
            status="success",
            content="i am a string",  # type: ignore[arg-type]
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata={},
        )


def test_broken_str_content_is_detected(sample_input: Path) -> None:
    """Negative for invariant 1: a producer returning str instead
    of bytes would fail the ``isinstance(r.content, bytes)`` check
    applied to a conforming producer.
    """
    r = _StringReturningProducer().produce(sample_input, "a" * 64, {})
    assert not isinstance(r.content, bytes)
    assert isinstance(r.content, str)


class _RaisingProducer:
    """Exceptions escape produce() (violates invariant 2)."""

    name = "broken-raises"
    version = "0.0.1"

    def produce(
        self, input_path: Path, input_hash: str, config: dict[str, Any]
    ) -> ProducerResult:
        raise RuntimeError("should have been caught and returned as failed")


def test_broken_raising_producer_is_detected(sample_input: Path) -> None:
    """Negative for invariant 2: a producer that lets exceptions
    propagate fails the never-raises contract.
    """
    with pytest.raises(RuntimeError):
        _RaisingProducer().produce(sample_input, "a" * 64, {})


class _NondeterministicProducer:
    """Returns different bytes on each call (violates invariant 3)."""

    name = "broken-nondeterministic"
    version = "0.0.1"
    _counter = 0

    def produce(
        self, input_path: Path, input_hash: str, config: dict[str, Any]
    ) -> ProducerResult:
        type(self)._counter += 1
        return ProducerResult(
            status="success",
            content=f"call-{self._counter}".encode(),
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata={},
        )


def test_broken_nondeterministic_producer_is_detected(
    sample_input: Path,
) -> None:
    """Negative for invariant 3: output that changes across calls
    with equal inputs fails the determinism check.
    """
    p = _NondeterministicProducer()
    r1 = p.produce(sample_input, "a" * 64, {})
    r2 = p.produce(sample_input, "a" * 64, {})
    assert r1 != r2


class _MutatingProducer:
    """Modifies input_path (violates invariant 4)."""

    name = "broken-mutates"
    version = "0.0.1"

    def produce(
        self, input_path: Path, input_hash: str, config: dict[str, Any]
    ) -> ProducerResult:
        input_path.write_bytes(b"corrupted")
        return ProducerResult(
            status="success",
            content=b"ok",
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata={},
        )


def test_broken_mutating_producer_is_detected(sample_input: Path) -> None:
    """Negative for invariant 4: a producer that writes to
    input_path leaves observably different bytes behind.
    """
    before = sample_input.read_bytes()
    _MutatingProducer().produce(sample_input, "a" * 64, {})
    after = sample_input.read_bytes()
    assert before != after


class _EnvReadingProducer:
    """Reads os.environ (violates invariant 5, observationally).

    Structural Protocols cannot enforce "reads nothing outside
    config"; this test captures the observable consequence
    (env-dependent output) instead. Primary enforcement is code
    review.
    """

    name = "broken-env-reader"
    version = "0.0.1"

    def produce(
        self, input_path: Path, input_hash: str, config: dict[str, Any]
    ) -> ProducerResult:
        leak = os.environ.get("PKM_LEAK_TEST", "")
        return ProducerResult(
            status="success",
            content=f"leak={leak}".encode(),
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata={},
        )


def test_broken_env_reading_producer_is_detected(
    sample_input: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative for invariant 5 (observational): a producer whose
    output changes with the environment fails the
    env-independence check used on TrivialProducer.
    """
    p = _EnvReadingProducer()
    monkeypatch.setenv("PKM_LEAK_TEST", "foo")
    r1 = p.produce(sample_input, "a" * 64, {})
    monkeypatch.setenv("PKM_LEAK_TEST", "bar")
    r2 = p.produce(sample_input, "a" * 64, {})
    assert r1 != r2
