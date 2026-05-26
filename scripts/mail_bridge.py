#!/usr/bin/env python3
"""mail_bridge.py — expose curated Maildir folders to the pkm corpus as ``.eml`` symlinks.

pkm routes by file extension and already extracts ``.eml`` via Unstructured (SPEC §7.3),
but a Maildir stores raw RFC822 messages with **no** extension. This bridge symlinks the
messages in the curated ``include`` folders into a staging directory as ``<name>.eml``,
mirroring the folder structure. pkm (>= v0.4.0, which stores the *declared* path and no
longer dereferences symlinks) then ingests the staging tree with zero Maildir knowledge.

**Curation — which folders are worth indexing — lives here, in life-agent, not in pkm.**
The pkm substrate stays a boring ``extension -> producer`` pipeline; everything that knows
about Maildir, ``cur/new/tmp``, ``.notmuch``, or "jira mail is noise" lives in this script
and its manifest.

The curation manifest is PII-bearing (real folder names can reveal personal context) and
therefore lives OUTSIDE this public repo, at ``$LIFE_AGENT_KB/config/mail-corpus.yaml``.
A fake example of the schema is at ``config/mail-corpus.example.yaml``.

This script ONLY builds the symlink tree (and can prune dangling links). Registering the
staging dir as a pkm source and running ``pkm ingest/extract/rebuild-index`` is a separate,
explicit step (it prints the manifest snippet to use).

Usage (run in any env with PyYAML, e.g. ``uv run --project ~/git/pkm python``):
    python scripts/mail_bridge.py [--manifest PATH] [--prune] [--dry-run]
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path

import yaml


def _kb_root() -> Path:
    """Resolve $LIFE_AGENT_KB (the out-of-tree knowledge base), defaulting to
    ~/yo/life-agent-kb — same convention as scripts/run_phase1_eval.py."""
    env = os.environ.get("LIFE_AGENT_KB")
    return Path(env).expanduser() if env else Path.home() / "yo/life-agent-kb"


def load_manifest(path: Path) -> dict:
    """Load the curation manifest, failing fast if absent (it holds PII and is
    not in this repo) or malformed — never run on a degraded/empty set."""
    if not path.exists():
        raise SystemExit(
            f"manifest not found: {path}\n"
            "It holds your real folder selections and lives in $LIFE_AGENT_KB, "
            "outside this public repo.\n"
            "See config/mail-corpus.example.yaml for the schema."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise SystemExit(f"manifest {path} must be a mapping with `version: 1`")
    for key in ("maildir_root", "staging_dir", "include"):
        if key not in data:
            raise SystemExit(f"manifest {path} missing required key: {key!r}")
    return data


def discover_folders(
    maildir_root: Path, include: list[str], exclude: list[str]
) -> list[Path]:
    """Return the absolute Maildir folder dirs (those containing a ``cur/``) at
    or below each ``include`` entry, minus any whose path relative to
    ``maildir_root`` matches an ``exclude`` glob (e.g. ``Archive/*/git``).

    A Maildir "folder" is any directory with a ``cur/`` child; folders nest as
    real subdirectories here, so ``include: [Archive]`` would also pull in
    ``Archive/slice`` etc. (and ``Archive``'s own ``cur/``). Prefer listing
    specific high-signal folders over a noisy parent.
    """
    folders: list[Path] = []
    seen: set[Path] = set()
    for entry in include:
        base = maildir_root / entry
        if not base.is_dir():
            print(f"  ! include {entry!r} is not a dir under {maildir_root}; skipping")
            continue
        candidates = [base, *(d for d in base.rglob("*") if d.is_dir())]
        for d in candidates:
            if not (d / "cur").is_dir():
                continue
            rel = d.relative_to(maildir_root).as_posix()
            if any(fnmatch.fnmatch(rel, pat) for pat in exclude):
                continue
            if d not in seen:
                seen.add(d)
                folders.append(d)
    return sorted(folders)


def link_folder(
    folder: Path, maildir_root: Path, staging_dir: Path, *, dry_run: bool
) -> tuple[int, int]:
    """Symlink every message in ``folder/{cur,new}`` into the staging tree as
    ``<name>.eml``, mirroring the folder's path relative to ``maildir_root``.
    The symlink target is the real Maildir path, so ``readlink`` recovers full
    provenance. Returns ``(linked, unchanged)``."""
    dest_dir = staging_dir / folder.relative_to(maildir_root)
    linked = unchanged = 0
    for sub in ("cur", "new"):
        src_dir = folder / sub
        if not src_dir.is_dir():
            continue
        for msg in sorted(src_dir.iterdir()):
            if not msg.is_file():
                continue
            link = dest_dir / (msg.name + ".eml")
            if link.is_symlink() and os.readlink(link) == str(msg):
                unchanged += 1
                continue
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if link.is_symlink() or link.exists():
                    link.unlink()
                link.symlink_to(msg)
            linked += 1
    return linked, unchanged


def prune_broken(staging_dir: Path, *, dry_run: bool) -> int:
    """Remove dangling staging symlinks (mbsync renamed/removed the source on a
    flag change). pkm skips broken symlinks anyway (SPEC §13.4), but pruning
    keeps the staging tree honest."""
    if not staging_dir.exists():
        return 0
    n = 0
    for p in staging_dir.rglob("*"):
        if p.is_symlink() and not p.exists():  # exists() follows the link
            if not dry_run:
                p.unlink()
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--manifest",
        type=Path,
        default=_kb_root() / "config/mail-corpus.yaml",
        help="curation manifest (default: $LIFE_AGENT_KB/config/mail-corpus.yaml)",
    )
    ap.add_argument(
        "--prune",
        action="store_true",
        help="remove dangling staging symlinks before linking",
    )
    ap.add_argument("--dry-run", action="store_true", help="report, don't touch the fs")
    args = ap.parse_args()

    m = load_manifest(args.manifest)
    maildir_root = Path(m["maildir_root"]).expanduser()
    staging_dir = Path(m["staging_dir"]).expanduser()
    include = list(m["include"])
    exclude = list(m.get("exclude") or [])

    if not maildir_root.is_dir():
        raise SystemExit(f"maildir_root does not exist: {maildir_root}")

    suffix = " (DRY RUN)" if args.dry_run else ""
    print(f"manifest:     {args.manifest}")
    print(f"maildir_root: {maildir_root}")
    print(f"staging_dir:  {staging_dir}{suffix}")
    print(f"include={include} exclude={exclude}")

    if args.prune:
        pruned = prune_broken(staging_dir, dry_run=args.dry_run)
        print(f"pruned {pruned} dangling symlink(s)")

    folders = discover_folders(maildir_root, include, exclude)
    print(f"{len(folders)} folder(s) to bridge:")
    total_linked = total_unchanged = 0
    for f in folders:
        linked, unchanged = link_folder(
            f, maildir_root, staging_dir, dry_run=args.dry_run
        )
        total_linked += linked
        total_unchanged += unchanged
        print(f"  {f.relative_to(maildir_root)}: +{linked} linked, {unchanged} unchanged")
    print(
        f"done: {total_linked} linked, {total_unchanged} unchanged "
        f"across {len(folders)} folder(s)"
    )

    print("\nRegister the staging tree with pkm (separate step), e.g.:")
    print(
        f"  version: 1\n  sources:\n    - path: {str(staging_dir)!r}\n"
        f"      recursive: true\n      tags: [email]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
