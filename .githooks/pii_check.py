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
# The corpus is Israel AND Hong Kong; only the Israeli shapes were covered, so an HK
# tel/fax pair and an honorific-prefixed name reached a public commit before being
# scrubbed (2026-08-18). These three close that gap, each written for PRECISION — a
# noisy guard gets disabled, and a disabled guard is what let the leak through.
# HK subscriber numbers are 8 digits opening 2/3/5/6/9, usually written as two
# space-separated 4-digit groups with an optional +852 country code; the alnum
# look-around keeps them out of hashes.
_HK_PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"\+?852[-\s]?[23569]\d{3}[-\s]?\d{4}"      # with country code, separator optional
    r"|[23569]\d{3}[-\s]\d{4}"                  # bare: a separator is REQUIRED, so an
    r")(?![A-Za-z0-9])")                        # 8-digit date (20190812) is not a phone
# HKID: one or two letters, six digits, parenthesised check character.
_HKID_RE = re.compile(r"\b[A-Z]{1,2}\d{6}\(\s*[0-9A]\s*\)")
# An honorific followed by capitalised words is a person, named. It cannot catch a bare
# name (structurally indistinguishable from any capitalised phrase — that is what the
# private denylist and review are for), but it does catch the form real documents use.
_HONORIFIC_NAME_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][A-Za-z'\u2019-]*"
    r"(?:[,\s]+[A-Z][A-Za-z'\u2019-]*){0,3}")
# --- r23 (F6): seven shapes CLAUDE.md forbids by name that had NO rule at all. Each is
# CONTEXT-ANCHORED on purpose: a bare 8-digit run collides with dates (20190812) and a bare
# [A-Z]\d{7} collides with hashes, so an unanchored rule is noise, and a noisy guard gets
# disabled — which is what let the 2026-08-18 leak through. Every one ships with a poison
# fixture proving it kills a synthetic violation (P2).
_CONTACT_WORD = r"(?:tel|telephone|phone|fax|mobile|cell)"
# The filler real documents put between the keyword and the value.
_LABEL_GAP = r"(?:\s*(?:no|num|number|nr|ref|#)\.?)?[^A-Za-z0-9]{0,6}"
# Bare 8-digit HK subscriber number with NO separator, admitted only next to a contact word.
_HK_PHONE_BARE_RE = re.compile(
    _CONTACT_WORD + r"[^0-9A-Za-z]{0,8}(?<![A-Za-z0-9])[23569]\d{7}(?![A-Za-z0-9])", re.I)
# IL mobile written with TWO separators (05x-xxx-xxxx), the common human form.
_IL_MOBILE_SPLIT_RE = re.compile(
    r"(?<![A-Za-z0-9])05\d[-\s]\d{3}[-\s]\d{4}(?![A-Za-z0-9])")
# IL mobile in international form (+972-5x-xxx-xxxx / +972 5x xxxxxxx).
_IL_MOBILE_INTL_RE = re.compile(
    r"\+972[-\s]?5\d[-\s]?\d{3}[-\s]?\d{4}(?![A-Za-z0-9])")
# Passport with a SINGLE letter prefix, admitted only next to the word passport.
_PASSPORT_ONE_LETTER_RE = re.compile(
    r"passport" + _LABEL_GAP + r"\b[A-Z]\d{7}\b", re.I)
# A grouped account number, admitted only next to an account word.
_ACCOUNT_RE = re.compile(
    r"(?:account|acct\.?|a/c)" + _LABEL_GAP +
    r"(?<![A-Za-z0-9])\d{1,4}[-\s]\d{2,6}[-\s]\d{4,8}(?![A-Za-z0-9])", re.I)
# A document reference of the PREFIX/YEAR/SERIAL form real invoices and files use.
_DOC_REF_RE = re.compile(r"\b[A-Z]{2,6}/(?:19|20)\d{2}/\d{3,8}\b")
# An email with the separator obfuscated — [at] / (at) / " at " — which _EMAIL_RE cannot
# see because it requires a literal @.
# BRACKETED forms only. A bare " at " matched ordinary English prose ("looked at
# docs.md") — 8 false positives on this tree when it was tried, so it is not admitted.
_OBFUSCATED_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+\s*(?:\[\s*at\s*\]|\(\s*at\s*\))\s*"
    r"(?:[A-Za-z0-9-]+\s*(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\.)\s*)+[A-Za-z]{2,}\b", re.I)

# --- r23 (F13): owner-specific literals, scoped to `src/`. CLAUDE.md: "no owner-specific
# absolute paths, hostnames, or ids hard-coded in src/ — they belong in config/env".
# A tailnet name is unambiguous. A 9-digit id is admitted only as an integer literal bound
# to an identity-shaped name, because a bare 9-digit run appears in src docstrings as an
# illustrative example (verified against the tree before this rule landed).
_TAILNET_HOST_RE = re.compile(r"\b[a-z0-9-]+\.tail[0-9a-f]{4,}\.ts\.net\b", re.I)
_OWNER_ID_LITERAL_RE = re.compile(
    r"\b\w*(?:user|owner|chat|account|telegram)\w*_?id\w*\s*[:=]\s*\(?\s*\d{7,}", re.I)

# A filesystem-path literal worth checking. Home-relative (tilde-rooted, >=1 path
# segment — inherently personal) OR absolute (slash-rooted, >=2 path segments). The
# 2-segment floor for absolute paths skips the noise of single-name HTTP routes,
# REPL commands and glob fragments (a leading-slash dotname) which reveal nothing
# personal. The look-behind drops URL schemes, plain relative, dot-relative, and
# placeholder-rooted docs like `<root>/sources/...` (the slash follows a `>`).
_PATH_RE = re.compile(
    r"(?<![:\w@~./>\-])"
    r"(?:~/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*"
    r"|/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+)"
)


def _path_allowed(p: str, allow: tuple[str, ...]) -> bool:
    return any(p == a or p.startswith(a.rstrip("/") + "/") for a in allow)


# r23 (F7), WITHDRAWN as a shape: an allowlisted root does exempt every segment beneath
# it, but a personal-name segment and an ordinary kebab-case slug are structurally
# identical (`chan-tai-man` vs `life-agent`) — a shape rule fired on 20 legitimate paths
# on this tree. Names are the private denylist's job (see _HONORIFIC_NAME_RE's note), and
# the denylist already scans the whole line, path included. What was missing is that the
# CI leg runs with an EMPTY denylist and said nothing; it now says so. The residual gap is
# recorded in docs/guards.md as known-and-uncovered, in English, not papered over with a
# noisy rule.


# Machine-generated dependency lockfiles: hashes/sizes/URLs only.
# r23 (F5): declared by EXACT REPO-RELATIVE PATH, never by basename. `_skip` matched
# `os.path.basename`, so any file named `uv.lock` — `tests/fixtures/uv.lock`,
# `docs/poetry.lock` — was exempt anywhere in the tree, forever. Lockfiles are also NOT
# prose-free: a trailing TOML comment survives every `uv run`, which is how a full contact
# record rode into the tracked tree past a green gate.
_SKIP_PATHS = frozenset({"uv.lock"})

# Files whose bytes are legitimately binary. r23 (F4): a NUL byte outside this set is a
# REFUSAL, never a silent skip — binary-detection used as a skip is indistinguishable from
# a clean scan, and one NUL byte took five findings to zero. Verified against the tree: the
# only tracked binaries are pdf/pptx extractor fixtures.
_BINARY_SUFFIXES = frozenset({
    ".pdf", ".pptx", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".zip", ".gz", ".duckdb", ".db", ".bin", ".lockb", ".pyc",
})


def skipped_paths(names: list[str]) -> list[str]:
    """The subset of ``names`` declared skippable, by exact repo-relative path."""
    return [n for n in names if n in _SKIP_PATHS]


def announce_skips(names: list[str]) -> None:
    """r25 (L6): every skip is REPORTED. Adding one tracked prose file to `_SKIP_PATHS`
    exempted the repository's README from the guard with the whole gate green, and nothing
    said a word — the property the F5 fixture's own message already claimed ("a skipped
    file is reported, never silent") and which was never implemented."""
    skipped = skipped_paths(names)
    if skipped:
        sys.stderr.write(f"pii_check: skipped {len(skipped)} declared path(s): "
                         f"{', '.join(sorted(skipped))}\n")


def read_text_or_refuse(name: str, raw: bytes) -> str | None:
    """Decode ``raw``. ``None`` for a declared-binary path; **raises** for a NUL byte
    anywhere else. A binary blob in a text tree is a refusal, not a pass."""
    if os.path.splitext(name)[1].lower() in _BINARY_SUFFIXES:
        return None
    if b"\x00" in raw:
        raise ValueError(
            f"pii_check: {name} contains a NUL byte and was NOT scanned — a binary blob "
            f"in a text tree is a refusal, not a pass"
        )
    return raw.decode("utf-8", errors="replace")


def _skip(name: str) -> bool:
    return name in _SKIP_PATHS


def il_id_valid(s: str) -> bool:
    """True if ``s`` is a 9-digit string whose Israeli-ID check digit is valid.

    Algorithm: weight digits by 1,2,1,2,…; replace any product ≥10 by the sum
    of its two digits (== product - 9); the grand total must be 0 (mod 10).
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
    in_src: bool = False,
) -> list[Finding]:
    """Return every PII shape / denylist hit in ``text``. Pure; no IO."""
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        # K3 (D-d): the marker used to `continue` here, skipping EVERY check including the
        # private denylist — so a line marked synthetic was never tested against the layer
        # that knows real values, and `PII-OK` became a way to launder one in. It happened:
        # a real host name under a synthetic tailnet suffix, marked and committed, invisible
        # to the guard for exactly this reason.
        #
        # The marker's job is to permit a SYNTHETIC value that has a REAL SHAPE. A synthetic
        # value cannot contain a real name, so there is no legitimate use that the denylist
        # would break. It now suppresses shape findings only; the name layer always runs.
        marked = MARKER in line
        for pat in denylist:
            if pat.search(line):
                out.append(Finding(path, lineno, "private-denylist"
                                   + (" (a PII-OK line is NOT exempt from the name layer)"
                                      if marked else "")))
                break
        if marked:
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
        if _HK_PHONE_RE.search(line):
            out.append(Finding(path, lineno, "hk-phone-shape"))
        if _HKID_RE.search(line):
            out.append(Finding(path, lineno, "hkid-shape"))
        if _HONORIFIC_NAME_RE.search(line):
            out.append(Finding(path, lineno, "personal-name (honorific)"))
        # r23 (F6): the seven shapes that had no rule. Labels reuse the existing kind
        # where the shape is the same thing written differently, so a reader sees one
        # vocabulary, not two.
        if _HK_PHONE_BARE_RE.search(line):
            out.append(Finding(path, lineno, "hk-phone-shape"))
        if _IL_MOBILE_SPLIT_RE.search(line) or _IL_MOBILE_INTL_RE.search(line):
            out.append(Finding(path, lineno, "israeli-mobile-shape"))
        if _PASSPORT_ONE_LETTER_RE.search(line):
            out.append(Finding(path, lineno, "passport-shape"))
        if _ACCOUNT_RE.search(line):
            out.append(Finding(path, lineno, "account-number-shape"))
        if _DOC_REF_RE.search(line):
            out.append(Finding(path, lineno, "document-ref-shape"))
        if _OBFUSCATED_EMAIL_RE.search(line):
            out.append(Finding(path, lineno, "email (obfuscated separator)"))
        # r23 (F13) / K3 (S2): owner-specific literals. The tailnet hostname rule was
        # scoped to `src/`, on the reading that a hostname in prose is documentation. It is
        # not — CLAUDE.md forbids owner-specific values "including in docs prose, §14 ledger
        # entries, commit messages, and test fixtures", and 25 occurrences of two host names
        # had accumulated across reports, conferrals, a design doc and one poison fixture
        # with the hook armed the whole time, because nothing looked outside `src/`. A
        # hostname is PII wherever it appears, so this rule is now tree-wide.
        #
        # The ID rule stays `src/`-scoped: it matches an identity-shaped *binding*
        # (`owner_id = 1234567`), which outside src is someone quoting code, and widening it
        # is a separate change with its own false-positive question.
        if _TAILNET_HOST_RE.search(line):
            out.append(Finding(path, lineno, "owner-specific host (belongs in config/env)"))
        if in_src and _OWNER_ID_LITERAL_RE.search(line):
            out.append(Finding(path, lineno, "owner-specific literal (belongs in config/env)"))
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


_GENERIC_ROOTS = frozenset(
    {"/home", "/Users", "/mnt", "/media", "/var", "/usr", "/", "~"}  # PII-OK
)

# Standard XDG base dirs. When $LIFE_AGENT_KB lives under one of these, that base is
# generic (shared by many apps), NOT a private data mount — so the "data mount = KB
# parent" heuristic must not forbid it, else it blocks another app's XDG paths. (A
# genuinely private mount, by contrast, has a non-XDG parent that stays forbidden.)
_XDG_BASES = frozenset({"~/.local/share", "~/.local/state", "~/.config", "~/.cache"})  # PII-OK


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
        parent = os.path.dirname(b)  # the data mount = the KB's parent …
        tilde = ("~" + parent[len(home):]) if home and parent.startswith(home + "/") else parent
        if tilde not in _XDG_BASES:  # … unless that parent is a generic XDG base
            cands.add(parent)
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
    return read_text_or_refuse(path, raw)


def _read_disk(path: str) -> str | None:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except (OSError, IsADirectoryError):
        return None
    return read_text_or_refuse(path, raw)


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


def _cat_blob(sha: str, name: str = "") -> str | None:
    raw = subprocess.run(
        ["git", "cat-file", "-p", sha], capture_output=True, check=False
    ).stdout
    # The PATH decides whether a NUL is legitimate (r23/F4), so callers pass it; a bare
    # sha has no suffix and would refuse every binary blob in a pushed range.
    return read_text_or_refuse(name or sha, raw)


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
            text = _cat_blob(blobsha, path)
            if text is not None:
                out.append((path, text))
    return out


def gather_paths(paths: list[str]) -> list[tuple[str, str]]:
    announce_skips(paths)  # r25 (L6): a skipped file is reported, never silent
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
        # r23 (F6): the CI leg runs with an EMPTY name layer. A check pointed at nothing
        # cannot tell "clean" from "not looking", so it says which half did not run rather
        # than printing a bare pass.
        denylist: list[re.Pattern[str]] = []
        sys.stderr.write(
            "pii_check: --shapes-only — shapes + email allowlist ONLY; the private "
            "name layer not run (no denylist). A clean result here is not a clean "
            "result for names.\n"
        )
    else:
        loaded = load_denylist(kb_root())
        if loaded is None:
            sys.stderr.write(
                f"pii_check: denylist missing at {kb_root()}/pii-patterns.txt — "  # PII-OK
                "refusing to scan blind. Set LIFE_AGENT_KB, or pass --shapes-only.\n"
            )
            return 2
        denylist = loaded

    try:
        if "--staged" in args:
            files = gather_staged()
        elif "--prepush" in args:
            files = gather_prepush(sys.stdin.read())
        elif paths:
            files = gather_paths(paths)
        else:
            files = gather_tracked()
    except ValueError as e:  # r23 (F4): an unscannable blob is a refusal, never a pass
        sys.stderr.write(f"{e}\n")
        return 2

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
                in_src=path.startswith("src/"),
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
