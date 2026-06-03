"""Unstructured producer (SPEC §7.1, §7.2).

Unstructured is the broadest and messiest of the Phase 1 extractors:
it handles the long tail of formats (``.msg``, ``.pptx``, ``.xlsx``,
awkward HTML) where the others don't fit. Per-format accuracy is lower
than a specialist tool, but coverage is the value. (``.eml`` moved to
the dedicated ``email`` producer in v0.5.0 — Unstructured's ``auto``
strategy stalled on large attachment-heavy messages.)

Architecture choices:

  - Version check reads ``importlib.metadata.version("unstructured")``.
    We do not pin the transitive tools unstructured discovers at
    runtime (libmagic, tesseract, poppler for PDFs); pkm pins
    unstructured's own version and trusts its lower-level
    resolution. Documented because it's a real deviation from the
    exact-version discipline we apply to pandoc and docling's own
    versions.

  - Lazy import of ``unstructured.partition.auto``. The module is
    fairly heavy (NLTK, spaCy in some paths, various format
    backends), so imports are deferred to first actual use.

  - ``unstructured`` logs prolifically at INFO (model loads,
    element detection counts, heuristics). The module sets its
    logger's level to WARNING at import time so only genuine
    problems appear in pkm's JSONL event log. DEBUG and INFO
    events from unstructured are suppressed; WARNING and ERROR
    still flow through.

Config schema (strictly validated):

    {"strategy": "auto" | "fast" | "hi_res" | "ocr_only"}

Required key: ``strategy``. Unknown keys and values outside the
allowed set raise ``ProducerConfigError`` with the offender named.
The default at the config-file level is ``auto`` (resolves to
``fast`` most of the time); ``hi_res`` duplicates Docling's value
and is not recommended unless the user explicitly wants two
layout-aware extractors running on their PDFs.

Output (on success):

  - ``content`` is the JSON serialisation of the list of
    ``Element`` objects, encoded as UTF-8 bytes.
  - ``content_type`` is ``application/x-unstructured-json``.
  - ``content_encoding`` is ``utf-8``.

**Cache-purity fix:** Unstructured's default JSON includes
metadata fields that leak filesystem state — ``filename``,
``file_directory``, ``last_modified`` — making identical byte
content at different paths produce different JSON. These fields
are stripped to ``None`` before serialisation so the cached bytes
are a pure function of the input content plus config (SPEC §7.1).

Timeout: 180 s per document. Enforced with a
``ThreadPoolExecutor`` + ``future.result(timeout=...)``. On
timeout the future is abandoned (Python cannot kill a thread
running C extension code); for a short-lived CLI process the
orphaned thread dies with the process, which is tolerable.

Failure handling is broad by design: unstructured raises
non-specific ``Exception`` in various failure modes (corrupted
email, missing libmagic, format-detection disagreements), and its
error taxonomy is too unstable to pin. Any exception from the
partition call becomes ``status="failed"`` with the exception
type and message in ``error_message``.

Non-goals: no ``hi_res`` default, no chaining, no retry.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pkm.producer import (
    ProducerConfigError,
    ProducerDiscoveryError,
    ProducerResult,
    ProducerVersionMismatchError,
)

if TYPE_CHECKING:
    from unstructured.documents.elements import Element

# Silence unstructured's own logger. It logs prolifically at INFO
# about model loading, element detection counts, and internal
# heuristics — diagnostic noise that would flood pkm's JSONL event
# log. WARNING and ERROR events still surface normally.
logging.getLogger("unstructured").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Email: .eml has a dedicated `email` producer since v0.5.0;
        # .msg (Outlook OLE) stays here — the stdlib email module
        # cannot parse it.
        ".msg",
        # Presentations
        ".pptx",
        ".ppt",
        # Spreadsheets
        ".xlsx",
        ".xls",
        ".csv",
        ".tsv",
        # Documents (fallback; Pandoc/Docling usually preferred)
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".epub",
        # Web
        ".html",
        ".htm",
        # PDFs (fallback for docs Docling can't handle)
        ".pdf",
        # Plain
        ".txt",
        ".md",
    }
)

_ALLOWED_STRATEGIES: frozenset[str] = frozenset(
    {"auto", "fast", "hi_res", "ocr_only"}
)
"""The four strategies documented by unstructured. Anything outside
this set is a typo or a new value we have not considered; reject
with a clear error rather than passing through to unstructured."""

_REQUIRED_CONFIG_KEYS: frozenset[str] = frozenset({"strategy"})

_TIMEOUT_SECONDS = 180
"""Per-document timeout. Between Pandoc (60 s) and Docling (300 s).
Enforced via ``ThreadPoolExecutor.submit`` + ``future.result``;
pathological documents still terminate, median cases are well
within bounds."""

_METADATA_FIELDS_TO_STRIP: tuple[str, ...] = (
    "filename",
    "file_directory",
    "last_modified",
)
"""Metadata fields that leak filesystem state into the serialised
output. Nulled before ``elements_to_json`` so identical content at
different paths produces identical cached bytes (SPEC §7.1).
``filetype`` and content-derived fields (``languages``, ``sent_*``,
``subject``) are kept — they're content-dependent and useful."""


class UnstructuredProducer:
    """Producer wrapping the ``unstructured`` partitioning library.

    Instantiate once per CLI invocation. Constructor validates the
    installed package version and config shape; ``produce`` is
    total (never raises).
    """

    name: str = "unstructured"
    handled_formats: frozenset[str] = _SUPPORTED_EXTENSIONS

    def __init__(
        self, expected_version: str, config: dict[str, Any]
    ) -> None:
        installed = installed_unstructured_version()
        if installed != expected_version:
            raise ProducerVersionMismatchError(
                producer_name=self.name,
                expected=expected_version,
                installed=installed,
            )
        self.version: str = installed
        self._config: dict[str, str] = _validate_config(config)

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        ext = input_path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return _failed(
                f"unstructured producer does not support {ext!r} files; "
                f"supported extensions are {sorted(_SUPPORTED_EXTENSIONS)}"
            )

        try:
            elements = self._partition_with_timeout(input_path)
        except FuturesTimeoutError:
            return _failed(
                f"unstructured exceeded the {_TIMEOUT_SECONDS}s "
                f"timeout on {input_path.name}"
            )
        except MemoryError as e:
            return _failed(
                f"unstructured ran out of memory on "
                f"{input_path.name}: {e}"
            )
        except Exception as e:
            # Unstructured raises non-specific Exception in various
            # failure modes; catch broadly per the module docstring.
            return _failed(
                f"unstructured raised {type(e).__name__} on "
                f"{input_path.name}: {e}"
            )

        try:
            content = _serialise_elements(elements)
        except Exception as e:
            return _failed(
                f"unstructured JSON serialisation failed: "
                f"{type(e).__name__}: {e}"
            )

        return ProducerResult(
            status="success",
            content=content,
            content_type="application/x-unstructured-json",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata={
                "element_count": len(elements),
                "strategy": self._config["strategy"],
            },
        )

    def _partition_with_timeout(
        self, input_path: Path
    ) -> list[Element]:
        """Run ``partition`` in a worker thread with a hard timeout.

        The thread may outlive the timeout (Python cannot interrupt
        thread-local C code), but for a short-lived CLI process this
        is acceptable; the orphaned thread dies at process exit.
        """
        with ThreadPoolExecutor(max_workers=1) as exe:
            future = exe.submit(self._partition, input_path)
            return future.result(timeout=_TIMEOUT_SECONDS)

    def _partition(self, input_path: Path) -> list[Element]:
        from unstructured.partition.auto import partition

        return partition(
            filename=str(input_path),
            strategy=self._config["strategy"],
        )


def installed_unstructured_version() -> str:
    """Return the exact installed ``unstructured`` package version.

    Raises:
        ProducerDiscoveryError: ``unstructured`` is not installed.
    """
    try:
        return _package_version("unstructured")
    except PackageNotFoundError as e:
        raise ProducerDiscoveryError(
            "the unstructured package is not installed. install it "
            "(`uv add unstructured`) or remove the unstructured "
            "producer from config.yaml."
        ) from e


def _validate_config(config: dict[str, Any]) -> dict[str, str]:
    keys = set(config.keys())
    missing = _REQUIRED_CONFIG_KEYS - keys
    if missing:
        raise ProducerConfigError(
            f"unstructured config is missing required keys "
            f"{sorted(missing)}; got {sorted(keys)}"
        )
    unknown = keys - _REQUIRED_CONFIG_KEYS
    if unknown:
        raise ProducerConfigError(
            f"unstructured config has unknown keys {sorted(unknown)}; "
            f"only {sorted(_REQUIRED_CONFIG_KEYS)} are supported"
        )
    strategy = config["strategy"]
    if not isinstance(strategy, str):
        raise ProducerConfigError(
            f"unstructured config key 'strategy' must be a str, got "
            f"{type(strategy).__name__} ({strategy!r})"
        )
    if strategy not in _ALLOWED_STRATEGIES:
        raise ProducerConfigError(
            f"unstructured config 'strategy' value {strategy!r} is "
            f"unknown; allowed values are {sorted(_ALLOWED_STRATEGIES)}"
        )
    return {"strategy": strategy}


def _serialise_elements(elements: list[Element]) -> bytes:
    """Serialise a list of ``Element`` objects to JSON bytes with
    path-dependent metadata stripped (SPEC §7.1 determinism).

    Two steps are necessary, not just one:

      1. Null the path-dependent metadata fields themselves.
      2. Recompute each element's ``element_id``. Unstructured
         bakes ``metadata.filename`` into the ID hash (see
         ``Element.id_to_hash``), so merely stripping the filename
         from the output metadata would leave path-derived IDs
         behind. Re-running ``assign_and_map_hash_ids`` after
         nulling recomputes IDs with ``filename=None``, making the
         serialised bytes a pure function of input content.
    """
    from unstructured.documents.elements import assign_and_map_hash_ids
    from unstructured.staging.base import elements_to_json

    for element in elements:
        metadata = getattr(element, "metadata", None)
        if metadata is None:
            continue
        for field in _METADATA_FIELDS_TO_STRIP:
            if hasattr(metadata, field):
                setattr(metadata, field, None)

    assign_and_map_hash_ids(elements)

    json_str = elements_to_json(elements)
    return json_str.encode("utf-8")


def _failed(error_message: str) -> ProducerResult:
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=error_message,
        producer_metadata={},
    )
