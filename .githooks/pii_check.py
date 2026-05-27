#!/usr/bin/env python3
"""Structural PII guard for this *public* repository.

The repo enforces an **allowlist of safe shapes**: tracked text may only contain
data shaped like obviously-synthetic test data. Anything shaped like real
personal data is rejected:

  * an email whose domain is not in the allowlist (`@example.{com,org,net}` plus
    `.githooks/pii-allow.txt`);
  * a 9-digit run that *passes* the Israeli-ID checksum (synthetic test IDs are
    chosen to fail it, e.g. ``123456789``, so they pass the guard untouched);
  * a passport shape (two letters then seven digits) or an Israeli mobile.

A small **private denylist** (names / employers / domains — things with no
detectable shape) supplements the shapes. It is loaded from
``$LIFE_AGENT_KB/pii-patterns.txt`` and is *never* stored in this repo.

This catches *novel* PII by construction, unlike a denylist of known values.

Output never echoes a matched value (the guard also runs in public CI logs);
it reports ``path:line: <kind>`` only. A line containing the marker ``PII-OK``
is exempt — use sparingly, for deliberate, reviewed false positives.

Modes
-----
  (default)      shapes + email allowlist + private denylist.  Fail-closed:
                 if the denylist file is missing, refuse to scan (exit 2).
  --shapes-only  shapes + email allowlist only; no private file needed.  Used
                 by CI, which has no access to ``$LIFE_AGENT_KB``.

Inputs (pick one)
-----------------
  --staged       scan the staged blobs                              (pre-commit)
  --prepush      read ref updates on stdin, scan the pushed blobs   (pre-push)
  PATH...        scan explicit paths from the working tree          (manual)
  (none)         scan every tracked file in the working tree        (manual/CI)

Exit: 0 clean · 1 PII found · 2 misuse (denylist missing in default mode).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

MARKER = "PII-OK"
DEFAULT_ALLOWED_DOMAINS = frozenset({"example.com", "example.org", "example.net"})

# Require an alphabetic TLD (≥2 letters): real email domains never end in a
# numeric label, so this skips `package@1.2.3` version strings without missing
# any real address.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})\b")
# 9-digit / mobile runs must be a standalone token, not part of a longer
# alphanumeric blob (e.g. a sha256 hash in a lockfile) — hence the alnum-aware
# look-around rather than a digit-only one.
_NINE_DIGITS_RE = re.compile(r"(?<![A-Za-z0-9])\d{9}(?![A-Za-z0-9])")
_PASSPORT_RE = re.compile(r"\b[A-Z]{2}\d{7}\b")
_IL_MOBILE_RE = re.compile(r"(?<![A-Za-z0-9])05\d[-\s]?\d{7}(?![A-Za-z0-9])")

# Machine-generated dependency lockfiles: hashes/sizes/URLs only, no prose and
# no possible personal data. Scanning them is pure false-positive noise.
_SKIP_BASENAMES = frozenset(
    {
        "uv.lock",
        "poetry.lock",
        "Cargo.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lockb",
        "Pipfile.lock",
        "composer.lock",
    }
)


def _skip(name: str) -> bool:
    return os.path.basename(name) in _SKIP_BASENAMES


def il_id_valid(s: str) -> bool:
    """True if ``s`` is a 9-digit string whose Israeli-ID check digit is valid.

    Algorithm: weight digits by 1,2,1,2,…; replace any product ≥10 by the sum
    of its two digits (== product − 9); the grand total must be ≡ 0 (mod 10).
    Synthetic fixtures are deliberately chosen to *fail* this, so they pass the
    guard; real IDs pass the checksum and are therefore flagged.
    """
    if len(s) != 9 or not s.isdigit():
        return False
    total = 0
    for i, ch in enumerate(s):
        product = int(ch) * (1 if i % 2 == 0 else 2)
        total += product if product < 10 else product - 9
    return total % 10 == 0


@dataclass(frozen=True)
class Finding:
    """One offending location. ``kind`` names the rule; the value is never kept,
    so neither logs nor public CI output can re-leak it."""

    path: str
    lineno: int
    kind: str


def scan_text(
    path: str,
    text: str,
    *,
    denylist: list[re.Pattern[str]],
    allowed_domains: frozenset[str],
) -> list[Finding]:
    """Return every PII shape / denylist hit in ``text``. Pure; no IO."""
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if MARKER in line:
            continue
        for m in _EMAIL_RE.finditer(line):
            if m.group(1).lower() not in allowed_domains:
                out.append(Finding(path, lineno, "email (non-allowlisted domain)"))
        for m in _NINE_DIGITS_RE.finditer(line):
            if il_id_valid(m.group(0)):
                out.append(Finding(path, lineno, "israeli-id (checksum-valid)"))
        if _PASSPORT_RE.search(line):
            out.append(Finding(path, lineno, "passport-shape"))
        if _IL_MOBILE_RE.search(line):
            out.append(Finding(path, lineno, "israeli-mobile-shape"))
        for pat in denylist:
            if pat.search(line):
                out.append(Finding(path, lineno, "private-denylist"))
                break
    return out


# --- environment / config loading ----------------------------------------


def kb_root() -> str:
    """The knowledge-base root. Owner sets ``LIFE_AGENT_KB``; public default is
    ``~/.life-agent/kb`` (see README) — never a machine-specific path in tree."""
    return os.environ.get("LIFE_AGENT_KB") or os.path.expanduser("~/.life-agent/kb")


def load_denylist(kb: str) -> list[re.Pattern[str]] | None:
    """Compile ``$LIFE_AGENT_KB/pii-patterns.txt`` (one regex per line, blanks /
    ``#`` comments skipped). Returns ``None`` if the file is absent (fail-closed
    signal for the caller)."""
    path = os.path.join(kb, "pii-patterns.txt")
    if not os.path.isfile(path):
        return None
    pats: list[re.Pattern[str]] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line and not line.lstrip().startswith("#"):
                pats.append(re.compile(line, re.IGNORECASE))
    return pats


def load_allowed_domains(repo_root: str) -> frozenset[str]:
    """Default safe domains plus any in the committed ``.githooks/pii-allow.txt``
    (public-safe extras like ``github.com``). The file holds no PII."""
    extra: set[str] = set()
    path = os.path.join(repo_root, ".githooks", "pii-allow.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip().lower()
                if line and not line.startswith("#"):
                    extra.add(line)
    return DEFAULT_ALLOWED_DOMAINS | frozenset(extra)


# --- git plumbing: produce (path, text) pairs to scan ---------------------


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _blob(ref: str, path: str) -> str | None:
    """Decode a blob; return None for binary (NUL-containing) content."""
    raw = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, check=False
    ).stdout
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def _read_disk(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except (OSError, IsADirectoryError):
        return None
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def gather_staged() -> list[tuple[str, str]]:
    names = _git(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
    ).split("\0")
    out = []
    for name in filter(None, names):
        if _skip(name):
            continue
        text = _blob("", name)  # 'git show :name' = the staged index blob
        if text is not None:
            out.append((name, text))
    return out


def _rev_exists(sha: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True
        ).returncode
        == 0
    )


def gather_prepush(stdin: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in stdin.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        _lref, lsha, _rref, rsha = parts
        if lsha.startswith("0000000000"):
            continue  # branch deletion
        # New branch, or a force-push whose old remote tip is no longer in our
        # object store (e.g. after a history rewrite): scan the whole tip tree
        # rather than a diff that would error against a missing rev.
        if rsha.startswith("0000000000") or not _rev_exists(rsha):
            names = _git(["ls-tree", "-r", "--name-only", lsha]).splitlines()
        else:
            names = _git(["diff", "--name-only", rsha, lsha]).splitlines()
        for name in names:
            if _skip(name):
                continue
            key = (lsha, name)
            if key in seen:
                continue
            seen.add(key)
            text = _blob(lsha, name)
            if text is not None:
                out.append((f"{lsha[:8]}:{name}", text))
    return out


def gather_paths(paths: list[str]) -> list[tuple[str, str]]:
    out = []
    for p in paths:
        if _skip(p):
            continue
        text = _read_disk(p)
        if text is not None:
            out.append((p, text))
    return out


def gather_tracked() -> list[tuple[str, str]]:
    names = _git(["ls-files", "-z"]).split("\0")
    return gather_paths([n for n in names if n])


# --- entry point ----------------------------------------------------------


def main(argv: list[str]) -> int:
    args = set(a for a in argv if a.startswith("--"))
    paths = [a for a in argv if not a.startswith("--")]
    shapes_only = "--shapes-only" in args

    repo_root = _git(["rev-parse", "--show-toplevel"]).strip()
    allowed_domains = load_allowed_domains(repo_root)

    if shapes_only:
        denylist: list[re.Pattern[str]] = []
    else:
        loaded = load_denylist(kb_root())
        if loaded is None:
            sys.stderr.write(
                f"pii_check: denylist missing at {kb_root()}/pii-patterns.txt — "
                "refusing to scan blind. Set LIFE_AGENT_KB, or pass --shapes-only.\n"
            )
            return 2
        denylist = loaded

    if "--staged" in args:
        files = gather_staged()
    elif "--prepush" in args:
        files = gather_prepush(sys.stdin.read())
    elif paths:
        files = gather_paths(paths)
    else:
        files = gather_tracked()

    findings: list[Finding] = []
    for path, text in files:
        findings.extend(
            scan_text(path, text, denylist=denylist, allowed_domains=allowed_domains)
        )

    if findings:
        sys.stderr.write("pii_check BLOCKED — possible PII (values withheld):\n")
        for f in findings:
            sys.stderr.write(f"  {f.path}:{f.lineno}: {f.kind}\n")
        sys.stderr.write(
            "Fix the data (use synthetic, checksum-invalid values), or mark the "
            "line with  # PII-OK  if it is a reviewed false positive.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
