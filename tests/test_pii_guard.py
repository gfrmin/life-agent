"""Unit tests for the structural PII guard (.githooks/pii_check.py).

The guard scans this very file, so PII-shaped *literals* would block its own
commit. Two techniques keep the file self-passing: checksum-valid IDs are built
at runtime via ``_valid_il_id`` (no shaped literal in source), and lines that
must embed another shape carry a trailing ``# PII-OK`` (which both tells the
guard to skip that source line and is a Python comment). All values are
synthetic.

Run in the pkm env:
    uv run --project ~/git/pkm python -m pytest ~/git/pkm/tests/test_pii_guard.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".githooks"))

from pii_check import (  # noqa: E402
    DEFAULT_ALLOWED_DOMAINS,
    il_id_valid,
    scan_text,
)

D = DEFAULT_ALLOWED_DOMAINS


def _valid_il_id(prefix8: str) -> str:
    """Solve the check digit so the result passes ``il_id_valid`` — constructed
    at runtime so no checksum-valid 9-digit literal appears in this source."""
    for d in "0123456789":
        if il_id_valid(prefix8 + d):
            return prefix8 + d
    raise AssertionError("no valid check digit")


# --- israeli-id checksum: real passes, synthetic fails --------------------


def test_il_checksum_separates_real_from_synthetic() -> None:
    assert not il_id_valid("123456789")  # the synthetic fixture used in tests
    assert not il_id_valid("050580156")  # 9 digits, invalid checksum
    assert il_id_valid(_valid_il_id("12345678"))  # a real-shaped id
    assert il_id_valid("0" * 9)  # trivial valid checksum, no literal in source
    assert not il_id_valid("12345")  # wrong length
    assert not il_id_valid("12345678a")  # non-digit


def test_scan_flags_checksum_valid_id_only() -> None:
    vid = _valid_il_id("87654321")
    hits = scan_text("t", vid, denylist=[], allowed_domains=D)
    assert any(f.kind.startswith("israeli-id") for f in hits)
    # a checksum-invalid 9-digit run is left alone
    assert scan_text("t", "ref 123456789 ok", denylist=[], allowed_domains=D) == []


# --- email allowlist ------------------------------------------------------


def test_email_allowlist() -> None:
    assert scan_text("t", "ping user@example.com please", denylist=[], allowed_domains=D) == []
    hits = scan_text("t", "ping user@evil.test please", denylist=[], allowed_domains=D)  # PII-OK
    assert any(f.kind.startswith("email") for f in hits)


# --- structured shapes ----------------------------------------------------


def test_passport_and_mobile_shapes() -> None:
    pp = scan_text("t", "passport AB1234567 issued", denylist=[], allowed_domains=D)  # PII-OK
    assert any(f.kind == "passport-shape" for f in pp)
    mob = scan_text("t", "call 0512345678 today", denylist=[], allowed_domains=D)  # PII-OK
    assert any(f.kind.startswith("israeli-mobile") for f in mob)


# --- private denylist (supplement for shapeless names/orgs) ---------------


def test_denylist_supplement_matches_unshaped_literal() -> None:
    deny = [re.compile("Zzyzx", re.IGNORECASE)]
    assert any(
        f.kind == "private-denylist"
        for f in scan_text("t", "the Zzyzx memo", denylist=deny, allowed_domains=D)
    )
    # without the list loaded, the shapeless word is not flagged
    assert scan_text("t", "the Zzyzx memo", denylist=[], allowed_domains=D) == []


# --- the PII-OK escape hatch ----------------------------------------------


def test_marker_suppresses_line() -> None:
    vid = _valid_il_id("11111111")
    assert scan_text("t", "id " + vid + " x # PII-OK", denylist=[], allowed_domains=D) == []
