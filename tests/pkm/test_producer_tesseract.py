"""Tests for ``pkm.producers.tesseract`` -- the Tesseract OCR extractor
(SPEC v0.1.11 SS7.2).

All tests are hermetic: subprocess calls are mocked. No real Tesseract
binary is invoked. The live-Tesseract path is exercised separately by
manual verification (see plan Step 1d).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pkm.hashing import compute_cache_key
from pkm.producer import ProducerDiscoveryError, ProducerVersionMismatchError
from pkm.producers.tesseract import TesseractProducer

_FAKE_VERSION = "5.5.2"
_FAKE_INPUT_HASH = "a" * 64  # 64-char hex, valid for compute_cache_key

_DEFAULT_CONFIG: dict = {"languages": "heb+eng", "psm": 3, "oem": 3}

# Hebrew "teudah zahut" (identity card) + ID number.
_HEBREW_SAMPLE = "תעודת זהות 123456789\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_version_mock(version: str = _FAKE_VERSION) -> MagicMock:
    """Mock result for ``tesseract --version`` (text=True => strings)."""
    m = MagicMock()
    m.stdout = f"tesseract {version}\n leptonica-1.87.0\n"
    m.stderr = ""
    m.returncode = 0
    return m


def _make_ocr_mock(
    stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0
) -> MagicMock:
    """Mock result for the actual OCR call (text=False => bytes)."""
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construction_succeeds_with_matching_version() -> None:
    with patch("subprocess.run", return_value=_make_version_mock()) as mock_run:
        p = TesseractProducer(expected_version=_FAKE_VERSION)
    assert p.name == "tesseract"
    assert p.version == _FAKE_VERSION
    mock_run.assert_called_once()


def test_construction_raises_on_version_mismatch() -> None:
    wrong = "99.99.99"
    with (
        patch("subprocess.run", return_value=_make_version_mock()),
        pytest.raises(ProducerVersionMismatchError) as excinfo,
    ):
        TesseractProducer(expected_version=wrong)
    err = excinfo.value
    assert err.expected == wrong
    assert err.installed == _FAKE_VERSION
    assert err.producer_name == "tesseract"


def test_construction_raises_on_missing_binary() -> None:
    with (
        patch("subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(ProducerDiscoveryError, match="tesseract"),
    ):
        TesseractProducer(expected_version=_FAKE_VERSION)


def test_construction_raises_on_version_timeout() -> None:
    with (
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("tesseract", 10),
        ),
        pytest.raises(ProducerDiscoveryError, match="timed out"),
    ):
        TesseractProducer(expected_version=_FAKE_VERSION)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_produce_success_returns_utf8_text(tmp_path: Path) -> None:
    img = tmp_path / "id.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # minimal JPEG magic bytes

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_version_mock(),
            _make_ocr_mock(stdout=_HEBREW_SAMPLE.encode("utf-8")),
        ]
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(img, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "success"
    assert result.content_type == "text/plain"
    assert result.content_encoding == "utf-8"
    assert result.error_message is None
    assert isinstance(result.content, bytes)

    text = result.content.decode("utf-8")
    # Hebrew "teudah zahut" and the ID number must be in output
    assert "תעודת זהות" in text
    assert "123456789" in text


def test_produce_success_prefixes_source_path(tmp_path: Path) -> None:
    """Output must start with 'SOURCE: <path>' to match needle.sh OCR cache."""
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_version_mock(),
            _make_ocr_mock(stdout=b"some text\n"),
        ]
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(img, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.content is not None
    assert result.content.startswith(f"SOURCE: {img}\n\n".encode())


# ---------------------------------------------------------------------------
# Failure paths -- produce() must never raise
# ---------------------------------------------------------------------------


def test_produce_nonzero_exit_returns_failed(tmp_path: Path) -> None:
    img = tmp_path / "bad.jpg"
    img.write_bytes(b"\xff\xd8\xff")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_version_mock(),
            _make_ocr_mock(stderr=b"Error during processing.\n", returncode=1),
        ]
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(img, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "failed"
    assert result.content is None
    assert result.content_type is None
    assert result.error_message is not None
    assert "1" in result.error_message  # returncode mentioned


def test_produce_timeout_returns_failed(tmp_path: Path) -> None:
    img = tmp_path / "slow.tif"
    img.write_bytes(b"II*\x00")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_version_mock(),
            subprocess.TimeoutExpired("tesseract", 120),
        ]
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(img, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "failed"
    assert result.content is None
    assert result.error_message is not None
    assert "timeout" in result.error_message.lower()


def test_produce_never_raises_on_missing_file(tmp_path: Path) -> None:
    """Even a file that vanishes between routing and produce must not raise."""
    ghost = tmp_path / "ghost.jpg"
    # not created on disk

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_version_mock(),
            _make_ocr_mock(stderr=b"Could not open file.\n", returncode=1),
        ]
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(ghost, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "failed"


# ---------------------------------------------------------------------------
# Cache-key contracts
# ---------------------------------------------------------------------------


def test_config_languages_affects_cache_key() -> None:
    """Changing `languages` must yield a different cache key."""
    key_heb = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "heb+eng", "psm": 3, "oem": 3},
    )
    key_eng = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "eng", "psm": 3, "oem": 3},
    )
    assert key_heb != key_eng


def test_config_psm_affects_cache_key() -> None:
    """Changing `psm` must yield a different cache key."""
    key_a = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "heb+eng", "psm": 3, "oem": 3},
    )
    key_b = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "heb+eng", "psm": 6, "oem": 3},
    )
    assert key_a != key_b


def test_config_oem_affects_cache_key() -> None:
    """Changing `oem` must yield a different cache key."""
    key_a = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "heb+eng", "psm": 3, "oem": 3},
    )
    key_b = compute_cache_key(
        _FAKE_INPUT_HASH, "tesseract", _FAKE_VERSION,
        {"languages": "heb+eng", "psm": 3, "oem": 1},
    )
    assert key_a != key_b


def test_cache_key_is_path_independent() -> None:
    """Cache key depends on input_hash (content), not input_path (SPEC SS7.1)."""
    content_hash = "b" * 64
    key_a = compute_cache_key(
        content_hash, "tesseract", _FAKE_VERSION, _DEFAULT_CONFIG
    )
    key_b = compute_cache_key(
        content_hash, "tesseract", _FAKE_VERSION, _DEFAULT_CONFIG
    )
    assert key_a == key_b

    # Different content hash => different key (path doesn't matter)
    different_hash = "c" * 64
    key_c = compute_cache_key(
        different_hash, "tesseract", _FAKE_VERSION, _DEFAULT_CONFIG
    )
    assert key_a != key_c


# ---------------------------------------------------------------------------
# PDF support (SPEC v0.3.1 §7.3)
# ---------------------------------------------------------------------------


def _make_pdftoppm_mock(returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = b""
    m.stderr = b""
    m.returncode = returncode
    return m


def test_produce_pdf_success(tmp_path: Path) -> None:
    """PDF rasterised to two pages, each OCR'd; text concatenated with separator."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    page1_text = b"page one text\n"
    page2_text = b"page two text\n"

    def fake_run(cmd, **kwargs):
        if cmd[0] == "tesseract" and cmd[1] == "--version":
            return _make_version_mock()
        if cmd[0] == "pdftoppm":
            # Write two fake .ppm files so the producer finds them
            prefix = Path(cmd[-1])
            (prefix.parent / "page-01.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            (prefix.parent / "page-02.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            return _make_pdftoppm_mock()
        if cmd[0] == "tesseract":
            page = cmd[1]
            if "page-01" in page:
                return _make_ocr_mock(stdout=page1_text)
            return _make_ocr_mock(stdout=page2_text)
        raise ValueError(f"unexpected command: {cmd}")

    with patch("subprocess.run", side_effect=fake_run):
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(pdf, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "success"
    assert result.content_type == "text/plain"
    assert result.content is not None
    text = result.content.decode("utf-8", errors="replace")
    assert "page one text" in text
    assert "page two text" in text
    assert "--- page 1 ---" in text
    assert "--- page 2 ---" in text
    assert text.startswith(f"SOURCE: {pdf}")


def test_produce_pdf_pdftoppm_fails(tmp_path: Path) -> None:
    """pdftoppm non-zero exit returns status=failed, never raises."""
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "tesseract" and cmd[1] == "--version":
            return _make_version_mock()
        if cmd[0] == "pdftoppm":
            return _make_pdftoppm_mock(returncode=1)
        raise ValueError(f"unexpected command: {cmd}")

    with patch("subprocess.run", side_effect=fake_run):
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(pdf, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "failed"
    assert result.content is None
    assert result.error_message is not None
    assert "pdftoppm" in result.error_message


def test_produce_pdf_tesseract_page_fails(tmp_path: Path) -> None:
    """Single page OCR failure fails the whole PDF (whole-document granularity)."""
    pdf = tmp_path / "partial.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_run(cmd, **kwargs):
        if cmd[0] == "tesseract" and cmd[1] == "--version":
            return _make_version_mock()
        if cmd[0] == "pdftoppm":
            prefix = Path(cmd[-1])
            (prefix.parent / "page-01.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            (prefix.parent / "page-02.ppm").write_bytes(b"P6\n1 1\n255\n\x00\x00\x00")
            return _make_pdftoppm_mock()
        if cmd[0] == "tesseract":
            page = cmd[1]
            if "page-01" in page:
                return _make_ocr_mock(stdout=b"page one ok\n")
            # page-02 fails
            return _make_ocr_mock(stderr=b"Error\n", returncode=1)
        raise ValueError(f"unexpected command: {cmd}")

    with patch("subprocess.run", side_effect=fake_run):
        p = TesseractProducer(expected_version=_FAKE_VERSION)
        result = p.produce(pdf, _FAKE_INPUT_HASH, _DEFAULT_CONFIG)

    assert result.status == "failed"
    assert result.content is None
    assert result.error_message is not None


def test_cache_key_pdf_is_path_independent() -> None:
    """PDF cache key depends on input_hash (bytes), not input_path."""
    content_hash = "d" * 64
    key_a = compute_cache_key(content_hash, "tesseract", _FAKE_VERSION, _DEFAULT_CONFIG)
    key_b = compute_cache_key(content_hash, "tesseract", _FAKE_VERSION, _DEFAULT_CONFIG)
    assert key_a == key_b
