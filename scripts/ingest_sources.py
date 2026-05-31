#!/usr/bin/env python3
"""ingest_sources.py — promote the declarative data-source registry into pkm.

Reads ``data-sources.yaml`` (see data_source_registry.py), and for each *enabled*
root materialises it into pkm's ``sources.yaml`` and runs ``pkm ingest``. This is
the step that replaces the manual "copy the printed snippet, then run pkm ingest"
dance that ``mail_bridge.py`` ends with.

Two adapters, dispatched on ``kind``:

  - **filetree** — enumerate the included files (current on-disk state, not the
    nightly plocate index) and emit one per-file ``sources.yaml`` entry each, with
    the root's tags. Matches the existing per-file corpus convention and records the
    real declared path (no symlink indirection — real files already carry their
    extension, which is all pkm's router needs).
  - **maildir** — Maildir messages have no extension, so reuse ``mail_bridge.py``'s
    folder discovery + ``.eml`` symlinking to build a staging tree, then emit a single
    ``recursive`` directory entry pointing at it.

New entries are **merged** into pkm's existing ``sources.yaml`` (deduped by path,
tags unioned) — never clobbering the curated corpus. ``--dry-run`` prints the merged
manifest and skips both the write and ``pkm ingest``.

Run in the pkm env:
    uv run --project ~/git/pkm python scripts/ingest_sources.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mail_bridge  # noqa: E402  (reuse its Maildir discovery + linking)
from data_source_registry import (  # noqa: E402
    Registry,
    RegistryError,
    Root,
    _kb_root,
    _matches,
    _pat_match,
    default_registry_path,
    load_registry,
)

PKM_DIR = Path("~/git/pkm").expanduser()
DEFAULT_PKM_CONFIG = Path(os.environ.get("PKM_CONFIG", "~/.config/life-agent/pkm.yaml")).expanduser()
SOURCES_MANIFEST_VERSION = 1


# --------------------------------------------------------------------------- #
# Adapters: registry root -> sources.yaml entries
# --------------------------------------------------------------------------- #


def _prune_patterns(exclude: tuple[str, ...]) -> tuple[str, ...]:
    """Directory-prune patterns derived from excludes that end in ``/**`` (which
    exclude a whole subtree): ``**/.git/**`` -> ``**/.git``, ``git/**`` -> ``git``.
    A non-subtree exclude (e.g. ``**/._*``, a per-file glob) yields nothing."""
    return tuple(p[:-3] for p in exclude if p.endswith("/**"))


def enumerate_filetree(root: Root) -> list[Path]:
    """Included regular files under ``root.path`` (current state, via os.walk).
    Symlinked subdirectories are not descended (pkm doesn't traverse them either).

    Excluded subtrees are *pruned* from the walk rather than filtered after the
    fact, so a root like ``archive/`` does not pay to crawl every ``.git`` object
    tree or cloned-repo it then discards (the result is identical either way)."""
    base = root.path
    if not base.is_dir():
        raise RegistryError(f"{root.id}: path is not a directory: {base}")
    prune = _prune_patterns(root.exclude)
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        if prune:
            dirnames[:] = [
                d
                for d in dirnames
                if not any(
                    _pat_match(Path(os.path.relpath(Path(dirpath) / d, base)).as_posix(), pp)
                    for pp in prune
                )
            ]
        for name in filenames:
            p = Path(dirpath) / name
            rel = Path(os.path.relpath(p, base)).as_posix()
            if _matches(rel, root.include, root.exclude) and p.is_file():
                out.append(p)
    return sorted(out)


def _staging_dir(root: Root) -> Path:
    return root.staging_dir or (_kb_root() / "staging" / root.id)


def build_maildir_staging(root: Root, *, dry_run: bool) -> Path:
    """Reuse mail_bridge to symlink the included Maildir folders as a ``.eml`` tree.
    Returns the staging directory to register with pkm."""
    maildir_root = root.path
    if not maildir_root.is_dir():
        raise RegistryError(f"{root.id}: maildir path is not a directory: {maildir_root}")
    staging = _staging_dir(root)
    folders = mail_bridge.discover_folders(maildir_root, list(root.include), list(root.exclude))
    linked = unchanged = 0
    for folder in folders:
        a, b = mail_bridge.link_folder(folder, maildir_root, staging, dry_run=dry_run)
        linked += a
        unchanged += b
    print(
        f"  {root.id}: {len(folders)} folder(s), +{linked} linked, {unchanged} unchanged "
        f"-> {staging}"
    )
    return staging


def entries_for_root(root: Root, *, dry_run: bool) -> list[dict]:
    """sources.yaml entries for one enabled root."""
    if root.kind == "filetree":
        files = enumerate_filetree(root)
        print(f"  {root.id}: {len(files)} file(s) under {root.path}")
        return [_entry(str(p), root.tags) for p in files]
    if root.kind == "maildir":
        staging = build_maildir_staging(root, dry_run=dry_run)
        entry = _entry(str(staging), root.tags)
        entry["recursive"] = True
        return [entry]
    raise RegistryError(f"{root.id}: unknown kind {root.kind!r}")


def _entry(path: str, tags: tuple[str, ...]) -> dict:
    entry: dict = {"path": path}
    if tags:
        entry["tags"] = list(tags)
    return entry


# --------------------------------------------------------------------------- #
# Merge into pkm's existing sources.yaml (dedupe by path, union tags)
# --------------------------------------------------------------------------- #


def merge_entries(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge ``new`` into ``existing``, keyed by ``path``. Tags are unioned;
    ``recursive`` is preserved if set on either side. Order: existing first
    (stable), then any genuinely-new paths."""
    by_path: dict[str, dict] = {}
    order: list[str] = []
    for e in [*existing, *new]:
        path = e["path"]
        if path not in by_path:
            by_path[path] = {"path": path}
            order.append(path)
        merged = by_path[path]
        tags = sorted({*merged.get("tags", []), *e.get("tags", [])})
        if tags:
            merged["tags"] = tags
        if e.get("recursive") or merged.get("recursive"):
            merged["recursive"] = True
    return [by_path[p] for p in order]


def _load_existing(sources_yaml: Path) -> list[dict]:
    if not sources_yaml.exists():
        return []
    data = yaml.safe_load(sources_yaml.read_text(encoding="utf-8")) or {}
    return list(data.get("sources") or [])


def _pkm_root(pkm_config: Path) -> Path:
    data = yaml.safe_load(pkm_config.read_text(encoding="utf-8"))
    root = data.get("root_dir")
    if not isinstance(root, str):
        raise RegistryError(f"pkm config {pkm_config} has no string root_dir")
    return Path(root).expanduser()


def _write_sources(sources_yaml: Path, entries: list[dict]) -> None:
    sources_yaml.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Managed in part by life-agent/scripts/ingest_sources.py from the\n"
        "# declarative data-sources registry. Existing entries are preserved.\n"
    )
    body = yaml.safe_dump(
        {"version": SOURCES_MANIFEST_VERSION, "sources": entries},
        sort_keys=False,
        allow_unicode=True,
    )
    tmp = sources_yaml.with_suffix(".yaml.tmp")
    tmp.write_text(header + body, encoding="utf-8")
    tmp.replace(sources_yaml)  # atomic


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=default_registry_path())
    ap.add_argument("--pkm-config", type=Path, default=DEFAULT_PKM_CONFIG)
    ap.add_argument("--dry-run", action="store_true", help="print merged sources.yaml; don't write or ingest")
    ap.add_argument("--no-ingest", action="store_true", help="stage + write sources.yaml but skip `pkm ingest`")
    ap.add_argument("--extract", action="store_true", help="after ingest, run `pkm extract` (run producers)")
    ap.add_argument("--chunk", action="store_true", help="after extract, run `pkm chunk --backfill` (index for search)")
    args = ap.parse_args()

    try:
        registry: Registry = load_registry(args.registry)
        pkm_root = _pkm_root(args.pkm_config)
        sources_yaml = pkm_root / "sources" / "sources.yaml"

        enabled = [r for r in registry.roots if r.enabled]
        print(f"promoting {len(enabled)} enabled root(s) into {sources_yaml}:")
        new_entries: list[dict] = []
        for root in enabled:
            new_entries.extend(entries_for_root(root, dry_run=args.dry_run))

        existing = _load_existing(sources_yaml)
        merged = merge_entries(existing, new_entries)
        added = len(merged) - len(existing)
        print(f"\n{len(existing)} existing + {len(new_entries)} generated -> {len(merged)} merged ({added} new path(s))")
    except (RegistryError, OSError) as e:
        raise SystemExit(f"error: {e}")

    if args.dry_run:
        print("\n--- merged sources.yaml (dry-run) ---")
        print(yaml.safe_dump({"version": SOURCES_MANIFEST_VERSION, "sources": merged}, sort_keys=False, allow_unicode=True))
        return 0

    _write_sources(sources_yaml, merged)
    print(f"wrote {sources_yaml}")

    if args.no_ingest:
        print("skipping `pkm ingest` (--no-ingest)")
        return 0

    # Register → (optionally) extract → (optionally) chunk. `ingest` alone only
    # registers sources; `--extract`/`--chunk` complete the searchable promote.
    stages: list[list[str]] = [["ingest"]]
    if args.extract:
        stages.append(["extract"])
    if args.chunk:
        stages.append(["chunk", "--backfill"])

    for stage in stages:
        print(f"running `pkm {' '.join(stage)}`...")
        proc = subprocess.run(
            ["uv", "run", "--project", str(PKM_DIR), "pkm", "--config", str(args.pkm_config), *stage],
            check=False,
        )
        if proc.returncode != 0:
            return proc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
