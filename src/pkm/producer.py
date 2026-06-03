"""Producer-layer types (SPEC §7.1).

This module defines two types:

  - ``ProducerResult`` — a frozen dataclass describing the outcome
    of a single ``Producer.produce`` call. Consumed by
    ``pkm.cache.write_artifact``.

  - ``Producer`` — a ``typing.Protocol`` describing the shape and
    behavioural invariants a producer must satisfy. Three concrete
    producers (pandoc, docling, unstructured) land in Step 7; each
    will conform to this protocol structurally.

The protocol is ``@runtime_checkable`` so ``isinstance(p, Producer)``
gives a basic structural check. Semantic conformance (the five
behavioural invariants) is exercised in
``tests/test_producer_protocol.py`` with a positive TrivialProducer
and a negative, deliberately-broken producer per runtime-checkable
invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable


class ProducerError(Exception):
    """Base class for producer-layer problems surfaced at construction.

    Subclasses distinguish the two modes a producer can refuse to
    come up in: the installed tool's version disagrees with
    ``config.yaml`` (``ProducerVersionMismatchError``), or the tool
    could not be discovered at all (``ProducerDiscoveryError`` —
    missing binary, unparseable ``--version`` output, or similar).

    SPEC §14.5 makes these construction-time failures by contract:
    version drift is a correctness bug because cache keys depend on
    exact version strings.
    """


class ProducerVersionMismatchError(ProducerError):
    """The installed tool's version differs from the expected value.

    Raised by a producer's constructor when
    ``installed_version() != expected_version``. The message names
    both versions and states the remedy (edit config or install the
    matching version); no further work begins in that process.
    """

    def __init__(
        self, *, producer_name: str, expected: str, installed: str
    ) -> None:
        super().__init__(
            f"{producer_name} version mismatch: config.yaml expects "
            f"{expected!r}, installed is {installed!r}. edit config.yaml "
            f"or install the matching {producer_name} version."
        )
        self.producer_name = producer_name
        self.expected = expected
        self.installed = installed


class ProducerDiscoveryError(ProducerError):
    """The installed tool could not be discovered.

    Distinguishes "the tool is not there at all / its output is
    shaped differently than we expect" from "the tool is there, but
    the wrong version". Both are fatal at construction; keeping them
    as separate types avoids conflating "install something" with
    "edit the config version string".
    """


class ProducerConfigError(ProducerError):
    """The producer's ``config`` dict is malformed.

    Raised at constructor time when ``config.yaml`` supplies a key
    the producer does not recognise, omits a required key, or
    attaches a value of the wrong type to a known key. Validation
    is strict by design — silent coercion (e.g. ``"yes"`` → ``True``)
    would hide typos and change cache keys without the user's
    knowledge.
    """


@dataclass(frozen=True)
class ProducerResult:
    """The outcome of a single ``Producer.produce`` call (SPEC §7.1,
    §13.3, §14.7).

    Invariants by status:

      status == "success":
        - ``content`` is ``bytes`` (never ``str``, never ``None``).
        - ``content_type`` is a non-empty string (MIME type or
          producer-specific identifier such as
          ``"application/x-docling-json"``).
        - ``content_encoding`` is the declared encoding for text
          artifacts (e.g. ``"utf-8"``) or ``None`` for binary.
          There is no auto-detection at read time (§14.7); the
          declaration is authoritative.
        - ``error_message`` is ``None``.

      status == "failed":
        - ``content``, ``content_type``, ``content_encoding`` are
          all ``None``.
        - ``error_message`` is a non-empty string.

    ``producer_metadata`` is always a dict (possibly empty). It is
    written verbatim into ``meta.json`` and must be
    canonical-JSON-encodable. It is NOT part of the cache key.
    """

    status: Literal["success", "failed"]
    content: bytes | None
    content_type: str | None
    content_encoding: str | None
    error_message: str | None
    producer_metadata: dict[str, Any]


@runtime_checkable
class Producer(Protocol):
    """A named, versioned transformation from input bytes to an
    artifact (SPEC §2.2, §7.1).

    Identity invariants:

      - ``name`` is a stable identifier appearing in cache keys.
        Never rename in place; rename means a new producer.
      - ``version`` is the exact installed tool version (§14.5).
        Any change in behaviour MUST bump ``version``; the
        producer-version mismatch check at startup enforces that
        cache keys correspond to the running code.
      - ``handled_formats`` is the set of file extensions
        (lowercase, dot-prefixed, e.g. ``".pdf"``) this producer
        will attempt. The routing layer (§7.3) reads this class
        attribute without constructing the producer, so it MUST be
        available before ``__init__`` runs. Extensions outside
        this set produce a ``status="failed"`` result without
        invoking the underlying tool.

    Behavioural invariants of ``produce`` (SPEC §7.1 as of v0.1.2):

      1. ``content`` is ``bytes`` on success, never ``str`` and
         never auto-decoded. Text producers encode and record the
         encoding; consumers never guess (§14.7).

      2. ``produce`` never raises. Any failure is caught internally
         and returned as ``status="failed"`` with an
         ``error_message`` (§14.3 — failures are recorded, not lost).

      3. Deterministic given the same input *content* (identified
         by ``input_hash``) and the same ``config``. ``input_path``
         is an I/O handle, not part of the determinism contract
         (two machines with identical content at different paths
         MUST produce the same output). Non-deterministic
         producers (e.g., later LLM-backed ones) must make the
         randomness source appear in ``config``.

      4. ``input_path`` is immutable from the producer's view. The
         producer MUST NOT modify it or any other filesystem state
         outside its return value (§2.1 — sources are immutable).

      5. Configuration comes only from the ``config`` argument. No
         environment variables, no home-directory files, no
         side-channel inputs (§14.6 — no hidden state).

    The protocol is a ``typing.Protocol``, not an ABC — three
    concrete producers is the gate for extracting any further
    abstraction (CLAUDE.md).
    """

    name: str
    version: str
    handled_formats: frozenset[str]

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        """Transform one input into one artifact.

        Args:
            input_path: Absolute path to the source file. Read-only;
                the bytes there may be read but never modified.
            input_hash: 64-char lowercase SHA-256 hex of the bytes
                at ``input_path``, precomputed by the caller.
            config: Producer parameters from ``config.yaml``. Opaque
                to the framework; the producer owns its schema.

        Returns:
            A ``ProducerResult``. Never raises.
        """
        ...
