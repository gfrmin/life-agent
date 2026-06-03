"""Tests for ``pkm.producers.email_producer`` — the RFC822 (.eml) extractor
(SPEC v0.5.0 §7.2). Pure stdlib parsing, so no mocking: tests build real .eml
bytes and parse them.
"""

from __future__ import annotations

import time
from email.message import EmailMessage
from pathlib import Path

import pytest

from pkm.producer import ProducerVersionMismatchError
from pkm.producers.email_producer import EmailProducer

_VERSION = "1"
_HASH = "a" * 64  # valid 64-char hex input_hash


def _producer() -> EmailProducer:
    return EmailProducer(expected_version=_VERSION)


def _base(msg: EmailMessage) -> EmailMessage:
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Date"] = "Mon, 18 May 2026 13:38:40 -0400"
    msg["Subject"] = "Quarterly report"
    msg["Message-ID"] = "<abc123@example.com>"
    return msg


def _write(tmp_path: Path, data: bytes, name: str = "m.eml") -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


# --- construction / formats ----------------------------------------------


def test_construction_rejects_version_mismatch() -> None:
    with pytest.raises(ProducerVersionMismatchError):
        EmailProducer(expected_version="2")


def test_handled_formats_is_eml_only() -> None:
    assert EmailProducer.handled_formats == frozenset({".eml"})
    assert EmailProducer.name == "email"


# --- rendering ------------------------------------------------------------


def test_renders_headers_one_per_line_then_body(tmp_path: Path) -> None:
    m = _base(EmailMessage())
    m.set_content("This is the plain body.")
    r = _producer().produce(_write(tmp_path, m.as_bytes()), _HASH, {})

    assert r.status == "success"
    assert r.content_type == "text/plain"
    assert r.content_encoding == "utf-8"
    text = r.content.decode("utf-8")
    # one header per line, fixed order, From first
    assert text.startswith("From: alice@example.com\n")
    assert "\nTo: bob@example.com\n" in text
    assert "\nSubject: Quarterly report\n" in text
    assert "\nMessage-ID: <abc123@example.com>" in text
    # blank line then body
    assert "\n\nThis is the plain body." in text
    # metadata mirrors headers + attachment count
    assert r.producer_metadata["from"] == "alice@example.com"
    assert r.producer_metadata["subject"] == "Quarterly report"
    assert r.producer_metadata["n_attachments"] == 0


def test_absent_optional_header_is_omitted(tmp_path: Path) -> None:
    m = EmailMessage()
    m["From"] = "x@example.com"
    m["Subject"] = "No cc here"
    m.set_content("body")
    text = _producer().produce(_write(tmp_path, m.as_bytes()), _HASH, {}).content.decode()
    assert "Cc:" not in text
    assert "To:" not in text  # absent → omitted, not an empty line


def test_multipart_alternative_prefers_plain(tmp_path: Path) -> None:
    m = _base(EmailMessage())
    m.set_content("PLAIN_MARKER body")
    m.add_alternative("<html><body><p>HTML_MARKER</p></body></html>", subtype="html")
    text = _producer().produce(_write(tmp_path, m.as_bytes()), _HASH, {}).content.decode()
    assert "PLAIN_MARKER" in text
    assert "HTML_MARKER" not in text  # plain preferred over html


def test_html_only_body_is_stripped(tmp_path: Path) -> None:
    m = _base(EmailMessage())
    m.set_content("<html><body><p>Hello <b>World</b></p></body></html>", subtype="html")
    text = _producer().produce(_write(tmp_path, m.as_bytes()), _HASH, {}).content.decode()
    assert "Hello" in text and "World" in text
    assert "<p>" not in text and "<b>" not in text  # tags stripped


def test_hebrew_quoted_printable_decodes(tmp_path: Path) -> None:
    hebrew = "תעודת זהות 123456789"
    m = _base(EmailMessage())
    m.set_content(hebrew, subtype="plain", cte="quoted-printable")
    raw = m.as_bytes()
    assert b"=D7" in raw  # confirm it really is quoted-printable on the wire
    text = _producer().produce(_write(tmp_path, raw), _HASH, {}).content.decode()
    assert hebrew in text


# --- the stall regression: attachments are not decoded --------------------


def test_large_attachment_not_decoded_and_fast(tmp_path: Path) -> None:
    m = _base(EmailMessage())
    m.set_content("small body MARKER")
    big = b"\x00" * (8 * 1024 * 1024)  # 8 MB attachment payload
    m.add_attachment(big, maintype="application", subtype="pdf", filename="big.pdf")
    path = _write(tmp_path, m.as_bytes())  # ~11 MB on the wire (base64)

    t0 = time.monotonic()
    r = _producer().produce(path, _HASH, {})
    elapsed = time.monotonic() - t0

    assert r.status == "success"
    assert "MARKER" in r.content.decode()
    # the attachment payload never appears in the output
    assert len(r.content) < 10_000
    assert r.producer_metadata["n_attachments"] == 1
    assert elapsed < 5.0  # not the in-process stall (was minutes on Unstructured)


# --- never-raises / failure path ------------------------------------------


def test_missing_file_returns_failed_not_raises(tmp_path: Path) -> None:
    r = _producer().produce(tmp_path / "nope.eml", _HASH, {})
    assert r.status == "failed"
    assert r.content is None
    assert r.error_message


def test_garbage_input_does_not_raise(tmp_path: Path) -> None:
    path = _write(tmp_path, b"\xff\x00 not an email at all \x80\x81\n\n???")
    r = _producer().produce(path, _HASH, {})  # must not raise
    assert r.status in ("success", "failed")


def test_message_with_no_body(tmp_path: Path) -> None:
    # headers only, no body part
    raw = b"From: x@example.com\r\nSubject: empty\r\n\r\n"
    r = _producer().produce(_write(tmp_path, raw), _HASH, {})
    assert r.status == "success"
    assert "From: x@example.com" in r.content.decode()


# --- determinism / path independence --------------------------------------


def test_output_is_path_independent(tmp_path: Path) -> None:
    m = _base(EmailMessage())
    m.set_content("identical body")
    data = m.as_bytes()
    p1 = _write(tmp_path, data, "a.eml")
    sub = tmp_path / "deep" / "nested"
    sub.mkdir(parents=True)
    p2 = sub / "b.eml"
    p2.write_bytes(data)

    prod = _producer()
    r1 = prod.produce(p1, _HASH, {})
    r2 = prod.produce(p2, _HASH, {})
    assert r1.content == r2.content  # output depends on bytes, not path
