"""Tesseract OCR producer (SPEC v0.3.1 §7.2, §7.3).

Subprocess-wraps the ``tesseract`` binary. Handles:

  - Image formats (``.jpg``, ``.jpeg``, ``.png``, ``.tif``, ``.tiff``,
    ``.bmp``) — direct OCR, one Tesseract call per file.
  - PDFs — rasterised via ``pdftoppm -r 300`` then OCR'd page-by-page.
    Used as a fallback when Docling succeeded but extracted zero text
    (``empty_succeeded`` routing, SPEC §7.3). Whole-document granularity:
    a single page failure returns ``status="failed"`` for the whole PDF.

Invariants:

  - Version check is the first thing the constructor does (SPEC §14.5).
    A mismatch raises ``ProducerVersionMismatchError`` before any
    ``produce`` call runs.

  - ``produce`` never raises (SPEC §7.1 invariant 2). Subprocess
    failures, timeouts, and non-zero exits all return
    ``ProducerResult(status="failed", error_message=...)``.

  - Output is prefixed with ``SOURCE: <path>\\n\\n`` so that it
    matches the format written by ``scripts/needle.sh``'s OCR cache.
    This allows direct comparison for baseline verification.

  - Config ``{languages, psm, oem}`` is part of the producer config
    dict and therefore part of the cache key (SPEC §4.2). Different
    language packs, page segmentation modes, or engine modes yield
    different cache keys.

Non-goals:

  - No image preprocessing (deskew, contrast, upscale). A failed OCR
    is recorded as a failed artifact; preprocessing is a future concern
    noted in FAILURES.md.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pkm.producer import (
    ProducerDiscoveryError,
    ProducerResult,
    ProducerVersionMismatchError,
)

_VERSION_LINE_RE = re.compile(r"^tesseract\s+(\S+)")
"""Matches the first line of ``tesseract --version`` output, e.g.
``tesseract 5.5.2``. The rest (leptonica version, compiler flags)
varies across builds and is intentionally ignored."""

_TIMEOUT_SECONDS = 120
"""Per-document timeout. Generous to allow large scans on slower hardware."""

_DISCOVERY_TIMEOUT_SECONDS = 10
"""Timeout for the one-shot ``tesseract --version`` call at construction."""


class TesseractProducer:
    """Producer wrapping the ``tesseract`` binary (SPEC v0.1.11 §7.2).

    Instantiate once per CLI invocation. The constructor verifies the
    installed Tesseract version against ``expected_version`` and raises
    ``ProducerVersionMismatchError`` on mismatch.
    """

    name: str = "tesseract"
    handled_formats: frozenset[str] = frozenset(
        {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".pdf"}
    )

    def __init__(self, expected_version: str) -> None:
        installed = installed_tesseract_version()
        if installed != expected_version:
            raise ProducerVersionMismatchError(
                producer_name=self.name,
                expected=expected_version,
                installed=installed,
            )
        self.version: str = installed

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        """Run Tesseract OCR on ``input_path`` and return the text.

        Never raises. All failures (non-zero exit, timeout, missing
        file) are returned as ``status="failed"`` with a message.

        The output content is prefixed with ``SOURCE: <path>\\n\\n``
        to match ``needle.sh``'s OCR cache format.

        PDFs are rasterised with ``pdftoppm`` before OCR. Processing is
        whole-document: a single-page failure fails the entire artifact.
        """
        if input_path.suffix.lower() == ".pdf":
            return self._produce_pdf(input_path, config)
        return self._produce_image(input_path, config)

    def _produce_image(
        self, input_path: Path, config: dict[str, Any]
    ) -> ProducerResult:
        languages = config.get("languages", "heb+eng")
        psm = config.get("psm", 3)
        oem = config.get("oem", 3)

        try:
            completed = subprocess.run(
                [
                    "tesseract",
                    str(input_path),
                    "stdout",
                    "-l", str(languages),
                    "--psm", str(psm),
                    "--oem", str(oem),
                ],
                capture_output=True,
                text=False,
                check=False,
                timeout=_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _failed(
                f"tesseract exceeded the {_TIMEOUT_SECONDS}s timeout on "
                f"{input_path.name}"
            )

        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()

        if completed.returncode != 0:
            return _failed(
                f"tesseract exited {completed.returncode} on "
                f"{input_path.name}: "
                f"{stderr_text or '<no stderr output>'}"
            )

        prefix = f"SOURCE: {input_path}\n\n".encode()
        content = prefix + completed.stdout

        metadata: dict[str, Any] = {}
        if stderr_text:
            metadata["warnings"] = stderr_text

        return ProducerResult(
            status="success",
            content=content,
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata=metadata,
        )

    def _produce_pdf(
        self, input_path: Path, config: dict[str, Any]
    ) -> ProducerResult:
        languages = config.get("languages", "heb+eng")
        psm = config.get("psm", 3)
        oem = config.get("oem", 3)

        with tempfile.TemporaryDirectory() as tmpdir:
            page_prefix = str(Path(tmpdir) / "page")

            try:
                raster = subprocess.run(
                    ["pdftoppm", "-r", "300", str(input_path), page_prefix],
                    capture_output=True,
                    check=False,
                    timeout=_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return _failed(
                    f"pdftoppm exceeded the {_TIMEOUT_SECONDS}s timeout on "
                    f"{input_path.name}"
                )

            if raster.returncode != 0:
                stderr = raster.stderr.decode("utf-8", errors="replace").strip()
                return _failed(
                    f"pdftoppm exited {raster.returncode} on "
                    f"{input_path.name}: "
                    f"{stderr or '<no stderr output>'}"
                )

            page_images = sorted(Path(tmpdir).glob("page-*.ppm"))
            if not page_images:
                return _failed(
                    f"pdftoppm produced no pages for {input_path.name}"
                )

            page_texts: list[bytes] = []
            all_warnings: list[str] = []

            for page_img in page_images:
                try:
                    completed = subprocess.run(
                        [
                            "tesseract",
                            str(page_img),
                            "stdout",
                            "-l", str(languages),
                            "--psm", str(psm),
                            "--oem", str(oem),
                        ],
                        capture_output=True,
                        text=False,
                        check=False,
                        timeout=_TIMEOUT_SECONDS,
                    )
                except subprocess.TimeoutExpired:
                    return _failed(
                        f"tesseract exceeded the {_TIMEOUT_SECONDS}s timeout "
                        f"on page {page_img.name} of {input_path.name}"
                    )

                if completed.returncode != 0:
                    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
                    return _failed(
                        f"tesseract exited {completed.returncode} on page "
                        f"{page_img.name} of {input_path.name}: "
                        f"{stderr or '<no stderr output>'}"
                    )

                stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
                if stderr_text:
                    all_warnings.append(f"{page_img.name}: {stderr_text}")
                page_texts.append(completed.stdout)

        sep = b"\n--- page %d ---\n"
        body = b"".join(
            (sep % (i + 1)) + text for i, text in enumerate(page_texts)
        )
        prefix = f"SOURCE: {input_path}\n\n".encode()
        content = prefix + body

        metadata: dict[str, Any] = {}
        if all_warnings:
            metadata["warnings"] = "\n".join(all_warnings)

        return ProducerResult(
            status="success",
            content=content,
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata=metadata,
        )


def installed_tesseract_version() -> str:
    """Return the exact installed Tesseract version string.

    Parses the first line of ``tesseract --version`` with
    ``^tesseract\\s+(\\S+)``. The first line is stable across
    versions; subsequent lines carry compiler and library info that
    differs across packagers.

    Raises:
        ProducerDiscoveryError: ``tesseract`` cannot be run or its
            ``--version`` first line does not match the expected shape.
    """
    try:
        completed = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DISCOVERY_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        raise ProducerDiscoveryError(
            "tesseract binary not found on PATH. Install tesseract or add "
            "it to PATH before configuring a tesseract producer."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ProducerDiscoveryError(
            f"tesseract --version timed out after {_DISCOVERY_TIMEOUT_SECONDS}s"
        ) from e

    if completed.returncode != 0:
        raise ProducerDiscoveryError(
            f"tesseract --version exited {completed.returncode}: "
            f"{completed.stderr.strip() or '<no stderr output>'}"
        )

    # tesseract prints version to stdout (verified on 5.5.2)
    output = completed.stdout
    lines = output.splitlines()
    if not lines:
        raise ProducerDiscoveryError("tesseract --version produced no output")

    match = _VERSION_LINE_RE.match(lines[0].strip())
    if match is None:
        raise ProducerDiscoveryError(
            f"tesseract --version first line is unparseable: {lines[0]!r}"
        )

    return match.group(1)


def _failed(error_message: str) -> ProducerResult:
    """Construct a ``ProducerResult`` for the failure case."""
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=error_message,
        producer_metadata={},
    )
