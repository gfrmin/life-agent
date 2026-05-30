#!/usr/bin/env python3
"""pin_snapshot.py — freeze the comparison corpus S (SPEC-comparison.md §1).

S is a *tractable complete slice* of the live pkm catalogue, bounded by content-defined
rules (NOT by the eval questions). The concrete rules — source roots, mail window, pkm paths —
are **machine-specific identifiers and live OUT of the repo**, in
`$LIFE_AGENT_KB/config/comparison-corpus.yaml`. This script holds no real paths.

Both Phase 0 (wiki compile) and Phase 1 (retrieval) read S in full. This script:
  1. selects the S files from pkm's live sources.yaml + the mail-staging tree (date-filtered),
  2. writes a content-addressed manifest `snapshot_S.json` ({path, sha256, bytes}),
  3. materialises a mail-window staging dir (symlinks) so Phase 1 can ingest S as a pkm catalogue,
  4. writes `comparison_sources.yaml` (pkm sources.yaml shape) for that catalogue build.

Outputs (manifest, staging) hold/point at PII and live under $LIFE_AGENT_KB.

Run:  uv run --project ~/git/pkm python scripts/comparison/pin_snapshot.py
"""
from __future__ import annotations

import email.utils
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

KB = Path(os.environ.get("LIFE_AGENT_KB", str(Path.home() / "yo/life-agent-kb")))
CORPUS_CONFIG = KB / "config" / "comparison-corpus.yaml"
OUT_DIR = KB / "eval"
STAGING_DIR = KB / "comparison" / "mail-window"  # symlinks to in-window .eml, for the pkm catalogue


def _load_corpus_rules() -> dict:
    """S-selection rules (machine-specific paths/window) from the out-of-tree config."""
    if not CORPUS_CONFIG.exists():
        raise SystemExit(
            f"corpus config not found: {CORPUS_CONFIG}\n"
            "It holds machine-specific paths (PII) and lives in $LIFE_AGENT_KB, not the repo."
        )
    cfg = yaml.safe_load(CORPUS_CONFIG.read_text(encoding="utf-8")) or {}
    for key in ("live_sources", "mail_staging", "doc_roots", "mail_year"):
        if key not in cfg:
            raise SystemExit(f"{CORPUS_CONFIG}: missing required key {key!r}")
    return cfg


def _sha256(path: Path) -> tuple[str, int]:
    """sha256 + byte length of a file's *content* (following symlinks)."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _email_year(eml: Path) -> int | None:
    """Parse the Date: header year of a .eml file (robust to encodings)."""
    try:
        head = eml.read_bytes()[:8192].decode("utf-8", "replace")
    except OSError:
        return None
    m = re.search(r"^Date:\s*(.+)$", head, re.MULTILINE | re.IGNORECASE)
    if not m:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(m.group(1).strip())
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    return dt.year


def select_doc_sources(live_sources: Path, doc_roots: list[str]) -> list[Path]:
    """Per-file doc sources from the live sources.yaml under the S doc roots."""
    data = yaml.safe_load(live_sources.read_text(encoding="utf-8")) or {}
    out: list[Path] = []
    for s in data.get("sources", []):
        p = str(s.get("path", ""))
        if any(root in p for root in doc_roots):
            fp = Path(p)
            if fp.is_file():
                out.append(fp)
    return sorted(set(out))


def select_window_mail(mail_staging: Path, year: int) -> list[Path]:
    """All staged .eml whose Date header falls in the mail-window year."""
    out: list[Path] = []
    for eml in mail_staging.rglob("*.eml"):
        if _email_year(eml) == year:
            out.append(eml)
    return sorted(out)


def stage_mail(emls: list[Path]) -> Path:
    """Symlink the selected .eml into a flat staging dir for the comparison catalogue."""
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    for old in STAGING_DIR.glob("*.eml"):
        old.unlink()
    for eml in emls:
        link = STAGING_DIR / eml.name
        target = eml.resolve()  # mail-staging entries are themselves symlinks into the maildir
        try:
            link.symlink_to(target)
        except FileExistsError:
            link.unlink()
            link.symlink_to(target)
    return STAGING_DIR


def main() -> int:
    rules = _load_corpus_rules()
    live_sources = Path(rules["live_sources"]).expanduser()
    mail_staging = Path(rules["mail_staging"]).expanduser()
    doc_roots = list(rules["doc_roots"])
    mail_year = int(rules["mail_year"])

    docs = select_doc_sources(live_sources, doc_roots)
    print(f"doc sources under S roots: {len(docs)}")
    emls = select_window_mail(mail_staging, mail_year)
    print(f"mail dated {mail_year}: {len(emls)}")
    staging = stage_mail(emls)

    manifest = []
    for p in [*docs, *emls]:
        try:
            digest, n = _sha256(p)
        except OSError as e:
            print(f"  skip (unreadable): {p} ({e})")
            continue
        manifest.append({"path": str(p), "sha256": digest, "bytes": n})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snap = OUT_DIR / "snapshot_S.json"
    snap.write_text(
        json.dumps(
            {
                "pinned_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rules": {"doc_roots": doc_roots, "mail_year": mail_year},
                "n_files": len(manifest),
                "total_bytes": sum(m["bytes"] for m in manifest),
                "files": manifest,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {snap}  ({len(manifest)} files, {sum(m['bytes'] for m in manifest)/1e6:.1f} MB)")

    # pkm sources.yaml for the Phase-1 comparison catalogue: doc files one-per-entry,
    # plus the mail-window staging dir as one recursive entry.
    sources = [{"path": str(p)} for p in docs]
    sources.append({"path": str(staging), "recursive": True, "tags": ["email"]})
    comp_sources = OUT_DIR / "comparison_sources.yaml"
    comp_sources.write_text(
        "# Generated by pin_snapshot.py — the Phase-1 comparison catalogue source set (S).\n"
        + yaml.safe_dump({"version": 1, "sources": sources}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"wrote {comp_sources}  ({len(sources)} entries; {len(docs)} docs + 1 mail dir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
