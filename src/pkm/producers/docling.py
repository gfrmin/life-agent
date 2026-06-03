"""Docling producer (SPEC §7.1, §7.2).

Docling is a Python library (not a subprocess) that extracts
document structure using ML models: DocLayNet for page layout and
TableFormer for tables. It shines on PDFs with non-trivial layout
where Pandoc either cannot help (image-only PDFs) or produces
flat text that loses the structure.

This producer is architecturally unlike the Pandoc one:

  - Version check reads ``importlib.metadata.version("docling")``,
    which is fast and in-process. Docling does not expose
    ``docling.__version__``.

  - The ``DocumentConverter`` and the ``docling`` submodule imports
    are lazy — deferred to the first ``produce`` call. Importing
    ``docling.document_converter`` at top level costs ~3 s because
    it eagerly pulls the ML stack; doing it lazily keeps
    ``import pkm.producers.docling`` cheap for CLI paths that
    instantiate the producer but never call it.

  - On first actual use the ML models are downloaded and cached in
    ``~/.cache/docling/`` (or wherever Docling itself decides).
    That cache is Docling's concern, not pkm's — it is a tool
    dependency in the same sense as the Pandoc binary, and it does
    not violate SPEC §14.6's "no hidden state" because it is the
    third-party tool's state, not ours. Documented here so future
    readers aren't surprised by GBs of weights in their home dir.

Config schema (validated strictly at construction):

    {"ocr": bool, "table_structure": bool}

Both keys are required; unknown keys and non-bool values raise
``ProducerConfigError`` with a message naming the offending key.
No silent coercion — ``"yes"``, ``1``, or ``0`` all fail fast.

Output (on success):

  - ``content`` is the ``DoclingDocument`` serialised to JSON bytes
    (UTF-8). Preserves layout, tables, and structure — downstream
    transforms can inspect the document as data. If a consumer
    wants plain text, ``docling_core.types.doc.DoclingDocument``
    round-trips from JSON.
  - ``content_type`` is ``application/x-docling-json`` (producer-
    specific identifier, permitted by SPEC §7.1).
  - ``content_encoding`` is ``utf-8``.
  - ``producer_metadata["docling_schema_version"]`` records the
    schema version of the serialised document (Docling has its own
    schema version independent of the producer's). Not in the
    cache key — a schema bump that matters is a producer version
    bump.
  - ``producer_metadata["completion"]`` records whether the
    extraction ran to completion:

      * ``"complete"``        — ``ConversionStatus.SUCCESS``.
      * ``"partial_timeout"`` — ``PARTIAL_SUCCESS`` with no
        per-error detail. This is the diagnostic signature of
        Docling's internal ``document_timeout`` firing: the
        pipeline abandons layout analysis and serialises whatever
        state it has, but ``result.errors`` is empty because no
        per-page failures occurred. The `warnings` field will
        also be empty in this case; ``completion`` is how a
        consumer tells this apart from a fully-successful run.
      * ``"partial_other"``   — ``PARTIAL_SUCCESS`` with populated
        ``result.errors`` (e.g., per-page load failures). The
        detail is copied to ``warnings``.

    Consumers reading older cached artifacts that predate this
    key MUST treat its absence as ``"complete"`` — those
    artifacts were genuinely successful; they simply don't
    self-describe the completion state.

Timeout: 300 s per document. Docling on a layout-heavy PDF with
OCR can take a minute or two; 5 minutes is the "pathological, kill
it" ceiling.

MemoryError is caught explicitly (rare at personal scale but
possible on multi-hundred-page court exhibits). No memory
accounting — just record the failure and let routing decide.

Non-goals: No Tesseract fallback; no chaining to Pandoc; no retry.
The routing layer (§7.3, Step 7f) decides what to do when Docling
fails.
"""

from __future__ import annotations

import logging
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
    from docling.document_converter import DocumentConverter

# Silence PIL's INFO-level logger. Docling's PDF pipeline uses PIL
# (Pillow) internally for image handling and PIL emits "Corrupt JPEG
# data: N extraneous bytes before marker 0x??" lines to the root
# logger whenever it encounters a PDF with mildly off-spec embedded
# JPEGs (common in invoice-style PDFs). The extractions succeed, so
# these are diagnostic noise that doesn't belong in the JSONL event
# log. Set at module import time for the same reason Unstructured's
# logger is muted in producers/unstructured.py: once a wrapper
# producer's library verbosity is identified as noise, silence it at
# the module level — one library at a time, on demand.
logging.getLogger("PIL").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".docx", ".pptx", ".html", ".htm", ".md", ".markdown"}
)
"""Extensions this producer will attempt. Pandoc handles most of
these too; Docling's value is layout preservation (PDF) and
uniform JSON output across formats. Routing (§7.3) decides which
producer to call first."""

_REQUIRED_CONFIG_KEYS: frozenset[str] = frozenset({"ocr", "table_structure"})
"""All config keys are both required and bool. Strict schema; no
defaults inside the producer — SPEC §14.5 requires exact-value
agreement between config and behaviour."""

_TIMEOUT_SECONDS = 300
"""Per-document timeout, passed into Docling's
``PdfPipelineOptions.document_timeout``.

This ceiling is load-bearing for **memory**, not for time. Docling's
working set grows the longer its pipeline runs on a single document,
and a DocumentConverter reused across sources (the normal ``pkm
extract`` pattern) accumulates state between calls. On a pathological
PDF, letting the pipeline run longer does not produce a fuller
extraction — it produces a larger resident set that eventually trips
the OS OOM killer, which SIGKILLs the process without any Python-
catchable signal (see SPEC §7.1 on uncatchable failure modes).

300 s happens to be the value we pass AND the value Docling's own
pipeline uses for ``document_timeout`` — our producer does not wrap
Docling in a Python-side timeout separately. When the pipeline hits
the limit, Docling emits a WARNING to its own logger, returns
``ConversionStatus.PARTIAL_SUCCESS``, and serialises whatever state
it has built so far. The producer surfaces this as
``status="success"`` with ``producer_metadata.completion
= "partial_timeout"`` (see ``completion`` above).

Future readers tempted to raise this value because "300 s isn't
enough time for big PDFs": don't. The 306 s outlier in the Step 7h
real-corpus run was memory-bound; the Step 7h diagnostic confirmed
that a third consecutive run on the same 12 MB PDF OOM-killed the
process at ~24 GB RSS. A bigger time budget makes the OOM path more
reliable, not the extraction fuller."""


class DoclingProducer:
    """Producer wrapping the Docling Python library.

    Instantiate once per CLI invocation. The constructor verifies
    the installed Docling package version and validates the config
    dict's shape; both failures raise at construction time.

    The underlying ``DocumentConverter`` is built lazily on the
    first ``produce`` call (not at construction) so that importing
    ``docling.document_converter`` — which is slow — happens only
    when extraction is actually about to run.
    """

    name: str = "docling"
    handled_formats: frozenset[str] = _SUPPORTED_EXTENSIONS

    def __init__(
        self, expected_version: str, config: dict[str, Any]
    ) -> None:
        installed = installed_docling_version()
        if installed != expected_version:
            raise ProducerVersionMismatchError(
                producer_name=self.name,
                expected=expected_version,
                installed=installed,
            )
        self.version: str = installed
        self._config: dict[str, bool] = _validate_config(config)
        self._converter: DocumentConverter | None = None

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        ext = input_path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return _failed(
                f"docling producer does not support {ext!r} files; "
                f"supported extensions are {sorted(_SUPPORTED_EXTENSIONS)}"
            )

        # Pre-flight: encrypted PDFs cannot be decrypted by Docling
        # without the password, and Docling surfaces such cases as a
        # bare ConversionStatus.FAILURE with empty result.errors —
        # the same empty-errors signature as the partial_timeout
        # case above, making the catalogue entry uncategorisable
        # without opening the file. pikepdf.Pdf.open() raises
        # PasswordError immediately on an encrypted header without
        # reading content; cheap enough to run unconditionally on
        # every PDF. Non-PDF formats (docx, pptx, html, md) are
        # skipped — encryption is a PDF concern here.
        if ext == ".pdf":
            import pikepdf

            try:
                with pikepdf.open(input_path):
                    pass
            except pikepdf.PasswordError:
                return _failed(
                    f"PDF is encrypted (no password support) on "
                    f"{input_path.name}"
                )
            except Exception:
                # Other pikepdf errors (corrupt PDF, truncated,
                # etc.) fall through to Docling: its pipeline has
                # richer error messages for non-encryption failure
                # modes.
                pass

        try:
            converter = self._get_converter()
        except Exception as e:
            return _failed(
                f"docling converter setup failed: {type(e).__name__}: {e}"
            )

        try:
            result = converter.convert(input_path, raises_on_error=False)
        except MemoryError as e:
            return _failed(
                f"docling ran out of memory on {input_path.name}: {e}"
            )
        except Exception as e:
            return _failed(
                f"docling conversion raised "
                f"{type(e).__name__} on {input_path.name}: {e}"
            )

        from docling.datamodel.base_models import ConversionStatus

        if result.status not in (
            ConversionStatus.SUCCESS,
            ConversionStatus.PARTIAL_SUCCESS,
        ):
            errors = "; ".join(str(e) for e in (result.errors or []))
            return _failed(
                f"docling conversion status={result.status.name}"
                f"{': ' + errors if errors else ''}"
            )

        document = result.document
        content = document.model_dump_json(by_alias=True).encode("utf-8")

        metadata: dict[str, Any] = {
            "docling_schema_version": document.version,
            "conversion_status": result.status.name,
        }
        if result.status == ConversionStatus.SUCCESS:
            metadata["completion"] = "complete"
        elif result.status == ConversionStatus.PARTIAL_SUCCESS:
            warnings = [str(e) for e in (result.errors or [])]
            metadata["warnings"] = warnings
            # Empty errors + PARTIAL_SUCCESS is the signature of
            # Docling's internal document_timeout. Distinguish it from
            # per-page failure cases so consumers don't conflate them.
            metadata["completion"] = (
                "partial_other" if warnings else "partial_timeout"
            )

        return ProducerResult(
            status="success",
            content=content,
            content_type="application/x-docling-json",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata=metadata,
        )

    def _get_converter(self) -> DocumentConverter:
        """Lazy-construct the underlying DocumentConverter.

        Deferred so ``import pkm.producers.docling`` does not pull
        the docling ML stack (~3 s cold import). First invocation
        pays that cost; subsequent invocations reuse the instance.
        """
        if self._converter is not None:
            return self._converter

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
        )

        pdf_options = PdfPipelineOptions(
            do_ocr=self._config["ocr"],
            do_table_structure=self._config["table_structure"],
            document_timeout=float(_TIMEOUT_SECONDS),
        )
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            }
        )
        return self._converter


def installed_docling_version() -> str:
    """Return the exact installed Docling version string.

    Uses ``importlib.metadata`` (fast, no import of docling itself).
    Docling does not expose ``docling.__version__``, so this is the
    only reliable way to ask.

    Raises:
        ProducerDiscoveryError: the ``docling`` distribution is not
            installed. A docling producer without the docling package
            is a misconfiguration we want to catch loudly.
    """
    try:
        return _package_version("docling")
    except PackageNotFoundError as e:
        raise ProducerDiscoveryError(
            "the docling package is not installed. install it "
            "(`uv add docling`) or remove the docling producer from "
            "config.yaml."
        ) from e


def _validate_config(config: dict[str, Any]) -> dict[str, bool]:
    """Strictly validate the producer config dict (§14.5).

    Required keys: ``ocr``, ``table_structure``. Both must be
    ``bool``. Anything else — missing, extra, wrong-type — raises
    ``ProducerConfigError`` with a message that names the offender.
    """
    keys = set(config.keys())
    missing = _REQUIRED_CONFIG_KEYS - keys
    if missing:
        raise ProducerConfigError(
            f"docling config is missing required keys "
            f"{sorted(missing)}; got {sorted(keys)}"
        )
    unknown = keys - _REQUIRED_CONFIG_KEYS
    if unknown:
        raise ProducerConfigError(
            f"docling config has unknown keys {sorted(unknown)}; "
            f"only {sorted(_REQUIRED_CONFIG_KEYS)} are supported"
        )
    for key in _REQUIRED_CONFIG_KEYS:
        value = config[key]
        if not isinstance(value, bool):
            raise ProducerConfigError(
                f"docling config key {key!r} must be a bool, got "
                f"{type(value).__name__} ({value!r})"
            )
    return {"ocr": config["ocr"], "table_structure": config["table_structure"]}


def _failed(error_message: str) -> ProducerResult:
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=error_message,
        producer_metadata={},
    )
