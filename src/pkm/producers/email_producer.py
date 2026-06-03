"""Email producer (SPEC §7.1, §7.2, §7.3 rule 5).

Parses RFC822 (`.eml`) messages with the Python stdlib ``email`` module and
renders a fixed-order header block plus the message body as ``text/plain``.
Module is named ``email_producer`` (not ``email``) to avoid shadowing the
stdlib package it imports.

Why a dedicated producer rather than Unstructured: ``.eml`` previously routed
to Unstructured, whose ``auto`` strategy stalls in-process on large,
attachment-heavy messages (it attempts to partition payloads it does not
need). This producer decodes **only ``text/*`` parts** — attachment
(``application/*``) payloads are never decoded — so even a 59 MB message
parses in milliseconds, and the email corpus is scoped to message *bodies*.

Invariants:

  - ``version`` is a hand-bumped logic version (``_VERSION``), not an external
    tool version: this producer has no external tool to query. The constructor
    still checks ``expected_version == _VERSION`` so config and code cannot
    drift. Per SPEC §14.5, any change to this producer's *output* (header
    set/order, body-part selection, HTML stripping) MUST bump ``_VERSION`` —
    the cache key depends on it and there is no installed-tool version to catch
    a forgotten bump. (CLAUDE.md review checklist enforces this at review.)

  - ``produce`` never raises (SPEC §7.1 invariant 2). A malformed message or a
    decode failure returns ``status="failed"`` with an ``error_message``.

  - Deterministic and path-independent (SPEC §7.1): fixed header order,
    charset-aware decode via ``email.policy.default``, no filename / timestamp /
    hostname in the output.

  - Body selection: prefer the message's ``text/plain`` part; else its
    ``text/html`` part stripped to text with BeautifulSoup. Only the body part
    is decoded (via ``get_content``); attachments are counted but never read.

Non-goals:

  - ``.msg`` (Outlook OLE) — a different binary format the stdlib cannot parse;
    it stays with Unstructured (SPEC §7.3 rule 3).
  - Attachment extraction — attachments are not decoded; attachment-as-source
    is a Phase-2 concern (SPEC §12).
"""

from __future__ import annotations

import email
import email.policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from pkm.producer import ProducerResult, ProducerVersionMismatchError

_VERSION = "1"
"""Producer-logic version (SPEC §14.5). Hand-bumped on ANY change to the
rendered output — header set or order, body-part selection, HTML stripping.
Part of the cache key; a forgotten bump silently mixes output formats."""

_HEADER_ORDER: tuple[str, ...] = (
    "From",
    "To",
    "Cc",
    "Date",
    "Subject",
    "Message-ID",
)
"""Fixed canonical header order for the rendered block (SPEC §7.2). Absent
headers are omitted. The order is fixed so output is deterministic; changing
it is a behavioural change requiring a ``_VERSION`` bump."""


class EmailProducer:
    """Producer parsing RFC822 ``.eml`` messages via the stdlib.

    Instantiate once per CLI invocation. The constructor verifies
    ``expected_version`` against the module's ``_VERSION`` and raises
    ``ProducerVersionMismatchError`` on mismatch (mirrors the other producers,
    though here both sides are in-repo).
    """

    name: str = "email"
    handled_formats: frozenset[str] = frozenset({".eml"})

    def __init__(self, expected_version: str) -> None:
        installed = installed_email_version()
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
        try:
            with input_path.open("rb") as fp:
                msg = email.message_from_binary_file(
                    fp, policy=email.policy.default
                )
            if not isinstance(msg, EmailMessage):  # pragma: no cover
                return _failed(
                    f"email producer parsed {input_path.name} as a legacy "
                    "Message, not an EmailMessage (policy mismatch)"
                )

            headers = _header_block(msg)
            body = _body_text(msg)
            content = (headers + "\n\n" + body).encode("utf-8")

            return ProducerResult(
                status="success",
                content=content,
                content_type="text/plain",
                content_encoding="utf-8",
                error_message=None,
                producer_metadata=_metadata(msg),
            )
        except Exception as e:  # never raises (SPEC §7.1)
            return _failed(
                f"email producer raised {type(e).__name__} on "
                f"{input_path.name}: {e}"
            )


def installed_email_version() -> str:
    """Return the producer-logic version. Pure stdlib: no external tool to
    query, so this is the module constant (SPEC §14.5)."""
    return _VERSION


def _header_value(msg: EmailMessage, name: str) -> str | None:
    """Decoded, single-line value for ``name``, or ``None`` if absent.
    ``policy.default`` decodes RFC2047 encoded-words; we collapse any residual
    newlines so each header stays on one line (deterministic, FTS-friendly)."""
    raw = msg[name]
    if raw is None:
        return None
    return str(raw).replace("\r", " ").replace("\n", " ").strip()


def _header_block(msg: EmailMessage) -> str:
    """Render the fixed-order header block, one header per line, omitting
    absent headers."""
    lines: list[str] = []
    for name in _HEADER_ORDER:
        value = _header_value(msg, name)
        if value:
            lines.append(f"{name}: {value}")
    return "\n".join(lines)


def _body_text(msg: EmailMessage) -> str:
    """Return the message body as text: the ``text/plain`` part if present,
    else the ``text/html`` part stripped to text. Only the body part is
    decoded — attachment payloads are never read."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    content_type = body.get_content_type()
    text = body.get_content()  # decodes charset + transfer-encoding
    if content_type == "text/html":
        return BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
    return text.strip("\n")


def _metadata(msg: EmailMessage) -> dict[str, Any]:
    """Structured headers + attachment count for ``meta.json`` (SPEC §13.1).
    Not part of the cache key, not chunked — available for Phase-2
    subject-provenance and debugging."""
    return {
        "from": _header_value(msg, "From"),
        "to": _header_value(msg, "To"),
        "cc": _header_value(msg, "Cc"),
        "subject": _header_value(msg, "Subject"),
        "date": _header_value(msg, "Date"),
        "message_id": _header_value(msg, "Message-ID"),
        "n_attachments": sum(1 for _ in msg.iter_attachments()),
    }


def _failed(error_message: str) -> ProducerResult:
    """Construct a ``ProducerResult`` for the failure case with all
    content-shaped fields nulled, per SPEC §7.1 invariants."""
    return ProducerResult(
        status="failed",
        content=None,
        content_type=None,
        content_encoding=None,
        error_message=error_message,
        producer_metadata={},
    )
