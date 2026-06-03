"""Pandoc producer (SPEC §7.1, §7.2).

Subprocess-wraps the ``pandoc`` binary. Phase 1 scope: convert
common input formats to UTF-8 plain text via ``--to plain``. Output
format is fixed; structured-output (e.g. markdown) is a future
producer version (bump ``version`` in config to invalidate).

Invariants:

  - Version check is the first thing the constructor does (SPEC
    §14.5). A mismatch raises ``ProducerVersionMismatchError``
    before any ``produce`` call runs. The startup check is cheap;
    a cache key derived from a stale ``version`` string is a
    correctness bug we want to catch before any extractions.

  - ``produce`` never raises (SPEC §7.1 invariant 2). Subprocess
    failures, timeouts, and unsupported extensions all return
    ``ProducerResult(status="failed", error_message=...)``.

  - Input format is chosen via an explicit ``--from`` flag whose
    value comes from a hardcoded extension map (see
    ``_EXTENSION_MAP``). This removes Pandoc's version-dependent
    "guess the format" logic from the cache key's derivation —
    identical config + identical content must produce identical
    output across installations.

  - Pandoc's stderr is captured. If Pandoc exits non-zero, stderr
    becomes the ``error_message``. If Pandoc exits zero but
    produced stderr output (warnings about unusual characters or
    fallback conversions), that text is placed in
    ``producer_metadata["warnings"]`` — the content itself is the
    conversion output, not a mixed success/diagnostic blob.

  - Output content type is ``text/plain`` and encoding is ``utf-8``
    on success. Phase 1 doesn't exercise other content types from
    this producer.

Non-goals:

  - No ``.doc`` (legacy binary Word). Pandoc only reads ``.docx``.
    Legacy ``.doc`` files are routed elsewhere by §7.3; attempting
    to pre-convert them inside this producer is the wrong layer.

  - No retry on failure. A Pandoc failure is cached per SPEC §14.3
    and surfaces to the user via the catalogue. Retries at this
    layer would mask real problems.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from pkm.producer import (
    ProducerDiscoveryError,
    ProducerResult,
    ProducerVersionMismatchError,
)

_VERSION_LINE_RE = re.compile(r"^pandoc (\S+)$")
"""Pattern matching the first line of ``pandoc --version`` output.
Subsequent lines (Haskell compiler info, feature flags) vary across
builds and are intentionally ignored."""

_EXTENSION_MAP: dict[str, str] = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "markdown",
    ".html": "html",
    ".htm": "html",
    ".docx": "docx",
    ".odt": "odt",
    ".org": "org",
    ".rst": "rst",
    ".tex": "latex",
    ".rtf": "rtf",
    ".epub": "epub",
}
"""Extension → Pandoc ``--from`` value. Hardcoded because this is
producer behaviour, not configuration: putting it in config would
allow different users' caches to diverge under the same producer
``name`` and ``version``, which is a content-addressing lie.
Mutating an existing entry's value is a behavioural change and
must bump ``version``. Adding a new key is purely additive — no
pre-existing cache entry was ever written for a previously-
unhandled extension, so there is nothing to invalidate."""

_TIMEOUT_SECONDS = 60
"""Per-document timeout. Generous — tune down if real-corpus runs
show it being too permissive in failure cases."""

_DISCOVERY_TIMEOUT_SECONDS = 10
"""Timeout for the one-shot ``pandoc --version`` call at
construction."""


class PandocProducer:
    """Producer wrapping the ``pandoc`` binary.

    Instantiate once per CLI invocation. The constructor verifies
    the installed Pandoc version against ``expected_version`` and
    raises ``ProducerVersionMismatchError`` on mismatch.
    """

    name: str = "pandoc"
    handled_formats: frozenset[str] = frozenset(_EXTENSION_MAP)

    def __init__(self, expected_version: str) -> None:
        installed = installed_pandoc_version()
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
        ext = input_path.suffix.lower()
        pandoc_from = _EXTENSION_MAP.get(ext)
        if pandoc_from is None:
            return _failed(
                f"pandoc producer does not support {ext!r} files; "
                f"supported extensions are {sorted(_EXTENSION_MAP)}"
            )

        try:
            completed = subprocess.run(
                [
                    "pandoc",
                    "--from",
                    pandoc_from,
                    "--to",
                    "plain",
                    str(input_path),
                ],
                capture_output=True,
                text=False,
                check=False,
                timeout=_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return _failed(
                f"pandoc exceeded the {_TIMEOUT_SECONDS}s timeout on "
                f"{input_path.name}"
            )

        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()

        if completed.returncode != 0:
            return _failed(
                f"pandoc exited {completed.returncode}: "
                f"{stderr_text or '<no stderr output>'}"
            )

        metadata: dict[str, Any] = {}
        if stderr_text:
            metadata["warnings"] = stderr_text

        return ProducerResult(
            status="success",
            content=completed.stdout,
            content_type="text/plain",
            content_encoding="utf-8",
            error_message=None,
            producer_metadata=metadata,
        )


def installed_pandoc_version() -> str:
    """Return the exact installed Pandoc version string.

    Parses the first line of ``pandoc --version`` with
    ``^pandoc (\\S+)$``. The first line is stable across Pandoc
    major versions; subsequent lines carry Haskell compiler info
    that differs across packagers.

    Raises:
        ProducerDiscoveryError: ``pandoc`` cannot be run (missing
            binary, permission denied, timeout at discovery) or its
            ``--version`` first line does not match the expected
            shape. A Pandoc with unparseable output is a Pandoc we
            do not trust with extractions.
    """
    try:
        completed = subprocess.run(
            ["pandoc", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DISCOVERY_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        raise ProducerDiscoveryError(
            "pandoc binary not found on PATH. install pandoc or add "
            "it to PATH before configuring a pandoc producer."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ProducerDiscoveryError(
            f"pandoc --version timed out after "
            f"{_DISCOVERY_TIMEOUT_SECONDS}s"
        ) from e

    if completed.returncode != 0:
        raise ProducerDiscoveryError(
            f"pandoc --version exited {completed.returncode}: "
            f"{completed.stderr.strip() or '<no stderr output>'}"
        )

    lines = completed.stdout.splitlines()
    if not lines:
        raise ProducerDiscoveryError(
            "pandoc --version produced no output"
        )

    match = _VERSION_LINE_RE.match(lines[0])
    if match is None:
        raise ProducerDiscoveryError(
            f"pandoc --version first line is unparseable: {lines[0]!r}"
        )

    return match.group(1)


def _failed(error_message: str) -> ProducerResult:
    """Construct a ``ProducerResult`` for the failure case with all
    content-shaped fields nulled, per SPEC §7.1 invariants.
    """
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=error_message,
        producer_metadata={},
    )
