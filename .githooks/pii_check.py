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
  * a filesystem path under a non-placeholder root (tracked text must use
    ``/data``, ``/tmp``, ``~/.config`` … — see ``.githooks/pii-path-allow.txt``);
    real machine prefixes (``$HOME`` / the ``$LIFE_AGENT_KB`` mount) are derived
    from the environment and rejected outright. A *bare* personal folder name with
    no path (e.g. a project dir on its own) has no shape and stays the denylist's job.

A small **private denylist** (names / employers / domains — things with no
detectable shape) supplements the shapes. It is loaded from
``$LIFE_AGENT_KB/pii-patterns.txt`` and is *never* stored in this repo.

This catches *novel* PII by construction, unlike a denylist of known values.

Output never echoes a matched value (it could end up in a log); it reports
``path:line: <kind>`` only. A line containing the marker ``PII-OK`` is exempt —
use sparingly, for deliberate, reviewed false positives.

This is the *whole* gate — there is no server-side CI backstop (solo repo) — so
the hooks run at both commit and push, and pre-push scans every blob in every
pushed commit, not just the net diff.

Modes
-----
  (default)      shapes + email allowlist + private denylist.  Fail-closed:
                 if the denylist file is missing, refuse to scan (exit 2).
  --shapes-only  shapes + email allowlist only; no private file needed. For an
                 ad-hoc scan when ``$LIFE_AGENT_KB`` is unavailable.

Inputs (pick one)
-----------------
  --staged       scan the staged blobs                              (pre-commit)
  --prepush      read ref updates on stdin, scan the pushed blobs   (pre-push)
  PATH...        scan explicit paths from the working tree          (manual)
  (none)         scan every tracked file in the working tree        (manual)

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
# A filesystem-path literal worth checking. Home-relative (tilde-rooted, >=1 path
# segment — inherently personal) OR absolute (slash-rooted, >=2 path segments). The
# 2-segment floor for absolute paths skips the noise of single-name HTTP routes,
# REPL commands and glob fragments (a leading-slash dotname) which reveal nothing
# personal. The look-behind drops URL schemes, plain relative, and dot-relative.
_PATH_RE = re.compile(
    r"(?<![:\w@~./\-])"
    r"(?:~/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*"
    r"|/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+)"
)


def _path_allowed(p: str, allow: tuple[str, ...]) -> bool:
    return any(p == a or p.startswith(a.rstrip("/") + "/") for a in allow)

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
    path_allow: tuple[str, ...] = (),
    forbidden_prefixes: tuple[str, ...] = (),
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
        for m in _PATH_RE.finditer(line):
            p = m.group(0)
            if any(p == fp or p.startswith(fp.rstrip("/") + "/") for fp in forbidden_prefixes):
                out.append(Finding(path, lineno, "personal-path (machine prefix)"))
            elif not _path_allowed(p, path_allow):
                out.append(Finding(path, lineno, "personal-path (non-placeholder root)"))
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


def load_path_allow(repo_root: str) -> tuple[str, ...]:
    """Allowed placeholder / system path roots, from committed
    ``.githooks/pii-path-allow.txt`` (no PII — public-safe). A tracked filesystem
    path whose prefix is not one of these is flagged."""
    out: list[str] = []
    path = os.path.join(repo_root, ".githooks", "pii-path-allow.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line and not line.startswith("#"):
                    out.append(line)
    return tuple(out)


_GENERIC_ROOTS = frozenset({"/home", "/Users", "/mnt", "/media", "/var", "/usr", "/", "~"})  # PII-OK


def load_forbidden_prefixes() -> tuple[str, ...]:
    """Real machine paths to forbid outright, derived live from ``$HOME`` /
    ``$LIFE_AGENT_KB`` so no personal path is ever stored in this committed file.
    Empty if the environment is unset (Layer-1 allowlist still applies). Generic /
    too-short roots are dropped so the prefixes never over-match."""
    cands: set[str] = set()
    home = os.environ.get("HOME", "")
    kb = os.environ.get("LIFE_AGENT_KB", "")
    for base in filter(None, (home, kb)):
        cands.add(base)
        cands.add(os.path.realpath(base))
    for b in ({kb, os.path.realpath(kb)} if kb else set()):
        cands.add(os.path.dirname(b))  # the data mount = the KB's parent
    if home:
        for c in list(cands):
            if c.startswith(home + "/"):
                cands.add("~" + c[len(home):])  # tilde form of a home-rooted prefix
    return tuple(sorted(
        p
        for p in cands
        if p and len(p) >= 5 and p.rstrip("/") not in _GENERIC_ROOTS
    ))


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


def _is_ancestor(a: str, b: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode
        == 0
    )


def _cat_blob(sha: str) -> str | None:
    raw = subprocess.run(
        ["git", "cat-file", "-p", sha], capture_output=True, check=False
    ).stdout
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", errors="replace")


def _introduced_blobs(rsha: str, lsha: str) -> list[tuple[str, str]]:
    """(blob_sha, path) for every file added/modified by each commit in the
    pushed range. Scanning per-commit (not the net diff) means PII committed and
    then removed *within the same push* is still caught."""
    pairs: list[tuple[str, str]] = []
    for commit in _git(["rev-list", f"{rsha}..{lsha}"]).split():
        raw = _git(["diff-tree", "--no-commit-id", "--no-renames", "-r", commit])
        for line in raw.splitlines():
            if not line.startswith(":"):
                continue
            meta, _, path = line.partition("\t")
            fields = meta.split()
            if len(fields) < 4 or fields[3].startswith("0000000"):
                continue  # malformed or a deletion (no post-image to scan)
            pairs.append((fields[3], path))
    return pairs


def _tip_blobs(lsha: str) -> list[tuple[str, str]]:
    """(blob_sha, path) for every blob in lsha's tree — the full published
    snapshot. Used when there is no remote baseline (a new branch, or a
    force-push after a history rewrite): scan the curated current state rather
    than pre-convention historical blobs. History-level real-PII cleanliness for
    a rewrite is assured separately (the rewrite itself + a full-history grep of
    the private patterns), not by re-validating old synthetic fixtures here."""
    pairs: list[tuple[str, str]] = []
    for entry in _git(["ls-tree", "-r", lsha]).splitlines():
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if len(fields) >= 3 and fields[1] == "blob":
            pairs.append((fields[2], path))
    return pairs


def gather_prepush(stdin: str) -> list[tuple[str, str]]:
    """Scan the content being published. With a known remote baseline, scan
    every blob introduced by every commit in the range (so PII added then
    removed within the same push is still caught); otherwise (new branch or
    post-rewrite force-push) scan the curated tip snapshot. Deduplicated by blob
    id. This is the whole gate — no server-side CI — paired with the structural
    rules in SPEC §14.9."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in stdin.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        _lref, lsha, _rref, rsha = parts
        if lsha.startswith("0000000000"):
            continue  # branch deletion
        # Incremental scan only for a true fast-forward (remote tip is an
        # ancestor). New branch, missing baseline, or a divergent force-push
        # (history rewrite) → scan the curated tip snapshot instead.
        if (
            rsha.startswith("0000000000")
            or not _rev_exists(rsha)
            or not _is_ancestor(rsha, lsha)
        ):
            pairs = _tip_blobs(lsha)
        else:
            pairs = _introduced_blobs(rsha, lsha)
        for blobsha, path in pairs:
            if blobsha in seen:
                continue
            seen.add(blobsha)
            if _skip(path):
                continue
            text = _cat_blob(blobsha)
            if text is not None:
                out.append((path, text))
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
    path_allow = load_path_allow(repo_root)
    forbidden = load_forbidden_prefixes()

    if shapes_only:
        denylist: list[re.Pattern[str]] = []
    else:
        loaded = load_denylist(kb_root())
        if loaded is None:
            sys.stderr.write(
                f"pii_check: denylist missing at {kb_root()}/pii-patterns.txt — "  # PII-OK
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
            scan_text(
                path,
                text,
                denylist=denylist,
                allowed_domains=allowed_domains,
                path_allow=path_allow,
                forbidden_prefixes=forbidden,
            )
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
