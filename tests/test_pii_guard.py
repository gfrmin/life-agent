"""Unit tests for the structural PII guard (.githooks/pii_check.py).

The guard scans this very file, so PII-shaped *literals* would block its own
commit. Two techniques keep the file self-passing: checksum-valid IDs are built
at runtime via ``_valid_il_id`` (no shaped literal in source), and lines that
must embed another shape carry a trailing ``# PII-OK`` (which both tells the
guard to skip that source line and is a Python comment). All values are
synthetic.

Run in the pkm env:
    uv run --project ../pkm python -m pytest tests/test_pii_guard.py
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


# --- personal filesystem paths (layered: env backstop + placeholder allowlist) ---


def test_forbidden_prefixes_from_env(monkeypatch) -> None:
    from pii_check import load_forbidden_prefixes

    monkeypatch.setenv("HOME", "/home/zz")  # PII-OK
    monkeypatch.setenv("LIFE_AGENT_KB", "/home/zz/yo/kb")  # PII-OK
    pref = load_forbidden_prefixes()
    assert "/home/zz" in pref  # home  # PII-OK
    assert "/home/zz/yo" in pref  # data mount (kb parent)  # PII-OK
    assert "~/yo/kb" in pref  # tilde form  # PII-OK
    # generic roots are never forbidden outright (they would over-match)
    assert "/home" not in pref and "/mnt" not in pref and "~" not in pref  # PII-OK


_ALLOW = ("/data", "/tmp", "~/.config", "~/.life-agent")
_FORB = ("/mnt/zz", "/home/zz")  # PII-OK


def test_path_allowlist_flags_non_placeholder_roots() -> None:
    f = scan_text("t", "cd /opt/zz/proj/x", denylist=[], allowed_domains=D,  # PII-OK
                  path_allow=_ALLOW, forbidden_prefixes=())
    assert any(x.kind.startswith("personal-path") for x in f)
    # placeholder roots, relative paths and URLs are clean
    for ok in ("see /data/notes/a.md", "edit ~/.config/app", "go ../pkm now",
               "url https://github.com/org/repo here"):
        assert scan_text("t", ok, denylist=[], allowed_domains=D,
                         path_allow=_ALLOW, forbidden_prefixes=()) == []


def test_path_machine_prefix_backstop() -> None:
    f = scan_text("t", "ls /mnt/zz/projects/secret", denylist=[], allowed_domains=D,  # PII-OK
                  path_allow=("/mnt",), forbidden_prefixes=_FORB)  # PII-OK
    assert any(x.kind == "personal-path (machine prefix)" for x in f)


def test_path_ignores_single_segment_abs_and_globs() -> None:
    # single-name absolute tokens (routes, REPL cmds, glob fragments) reveal nothing
    for ok in ("POST /sensor then /signals", "glob **/.git/** and **/node_modules/**",
               "type /quit to exit", "version 3 not /3 here"):
        assert scan_text("t", ok, denylist=[], allowed_domains=D,
                         path_allow=("/data",), forbidden_prefixes=()) == []
    # a single-segment HOME path IS personal and is flagged
    f = scan_text("t", "cd ~/proj now", denylist=[], allowed_domains=D,  # PII-OK
                  path_allow=("~/.config",), forbidden_prefixes=())
    assert any(x.kind.startswith("personal-path") for x in f)
