#!/usr/bin/env python3
"""data_source_registry.py — one declarative registry for the local data roots
life-agent feeds into the pkm memory, plus a thin ``--report`` (census) view.

Today the corpus is wired ad-hoc: ``build_corpus.sh`` hardcodes a few source
paths, ``mail_bridge.py`` carries its own manifest, and every source is hand-copied
into pkm's ``sources.yaml``. This module replaces that with a single registry
(``data-sources.yaml``) describing each root: where it is, which adapter handles it
(``kind``), which files to include, and whether it's eligible for ingestion.

It does NOT ingest — ``ingest_sources.py`` consumes this registry to stage files and
hand them to pkm. This file owns: loading/validating the registry, and reporting what
is on disk under each root (enumerated from **plocate**, the system file index, once
its prune list is configured to cover your data roots).

The registry is PII-bearing (real folder names reveal personal context), so the real
file lives OUTSIDE this public repo at ``$LIFE_AGENT_KB/config/data-sources.yaml``;
a fake example of the schema is ``config/data-sources.example.yaml``. Same split as
``mail_bridge.py`` / ``mail-corpus.example.yaml``.

Run in the pkm env (has PyYAML, duckdb, and the pkm producers whose ``handled_formats``
define "ingestable today"):
    uv run --project ~/git/pkm python scripts/data_source_registry.py --report
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REGISTRY_VERSION = 1
VALID_KINDS = frozenset({"filetree", "maildir"})


# --------------------------------------------------------------------------- #
# Registry model + loading (fail-fast, mirroring mail_bridge.load_manifest)
# --------------------------------------------------------------------------- #


class RegistryError(Exception):
    """The registry file is absent, malformed, or internally invalid."""


@dataclass(frozen=True)
class Root:
    id: str
    kind: str
    path: Path  # declared path (expanduser + absolute; symlinks NOT resolved)
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    tags: tuple[str, ...]
    enabled: bool
    staging_dir: Path | None


@dataclass(frozen=True)
class Registry:
    version: int
    roots: tuple[Root, ...]


def _kb_root() -> Path:
    """Resolve $LIFE_AGENT_KB, defaulting to ~/.life-agent/kb (same convention
    as mail_bridge.py and scripts/run_eval.py)."""
    env = os.environ.get("LIFE_AGENT_KB")
    return Path(env).expanduser() if env else Path.home() / ".life-agent/kb"


def default_registry_path() -> Path:
    return _kb_root() / "config/data-sources.yaml"


def _coerce_root(i: int, entry: object) -> Root:
    if not isinstance(entry, dict):
        raise RegistryError(f"roots[{i}] is not a mapping")
    for key in ("id", "kind", "path"):
        if not isinstance(entry.get(key), str):
            raise RegistryError(f"roots[{i}] missing required string field {key!r}")
    kind = entry["kind"]
    if kind not in VALID_KINDS:
        raise RegistryError(
            f"roots[{i}] ({entry['id']}) has unknown kind {kind!r}; "
            f"expected one of {sorted(VALID_KINDS)}"
        )
    staging = entry.get("staging_dir")
    return Root(
        id=entry["id"],
        kind=kind,
        path=Path(entry["path"]).expanduser().absolute(),
        include=tuple(entry.get("include") or ()),
        exclude=tuple(entry.get("exclude") or ()),
        tags=tuple(entry.get("tags") or ()),
        enabled=bool(entry.get("enabled", True)),
        staging_dir=Path(staging).expanduser().absolute() if staging else None,
    )


def load_registry(path: Path) -> Registry:
    """Load and validate the registry, failing fast (it is the single source of
    truth for what gets ingested — never run on a degraded/empty set)."""
    if not path.exists():
        raise RegistryError(
            f"registry not found: {path}\n"
            "It holds your real data roots and lives in $LIFE_AGENT_KB, outside "
            "this public repo. See config/data-sources.example.yaml for the schema."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != REGISTRY_VERSION:
        raise RegistryError(f"registry {path} must be a mapping with `version: {REGISTRY_VERSION}`")
    roots_raw = data.get("roots")
    if not isinstance(roots_raw, list) or not roots_raw:
        raise RegistryError(f"registry {path} must have a non-empty `roots` list")
    roots = tuple(_coerce_root(i, e) for i, e in enumerate(roots_raw))
    ids = [r.id for r in roots]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        raise RegistryError(f"registry {path} has duplicate root id(s): {sorted(dupes)}")
    return Registry(version=data["version"], roots=roots)


# --------------------------------------------------------------------------- #
# Producer coverage — reuse pkm's real handled_formats (capability, not a guess)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def ingestable_formats() -> dict[str, str]:
    """``ext -> representative producer name`` from pkm's actual producers. An
    extension absent from this map has no pkm producer today (not ingestable).

    Iterated low-to-high preference so the more representative producer wins a
    shared extension (e.g. ``.pdf`` -> docling, images -> tesseract, ``.md`` ->
    pandoc, ``.eml`` -> email)."""
    from pkm.producers.docling import DoclingProducer  # type: ignore[import-untyped]
    from pkm.producers.email_producer import EmailProducer  # type: ignore[import-untyped]
    from pkm.producers.pandoc import PandocProducer  # type: ignore[import-untyped]
    from pkm.producers.tesseract import TesseractProducer  # type: ignore[import-untyped]
    from pkm.producers.unstructured import UnstructuredProducer  # type: ignore[import-untyped]

    mapping: dict[str, str] = {}
    for prod in (UnstructuredProducer, TesseractProducer, DoclingProducer, PandocProducer, EmailProducer):
        name = prod.__name__.removesuffix("Producer").lower()
        for ext in prod.handled_formats:
            mapping[ext.lower()] = name
    return mapping


def classify(path: Path, fmt_map: dict[str, str]) -> tuple[str, str | None, bool]:
    """Return ``(extension, producer_or_None, ingestable)`` for a path."""
    ext = path.suffix.lower()
    producer = fmt_map.get(ext)
    return ext, producer, producer is not None


# --------------------------------------------------------------------------- #
# Enumeration — from plocate (the system index), filtered by the root's globs
# --------------------------------------------------------------------------- #


def _pat_match(rel_posix: str, pat: str) -> bool:
    """fnmatch with a gitignore-style ``**/`` prefix meaning "zero or more
    directories" — so ``**/*.md`` matches both ``a.md`` and ``sub/a.md``.
    (Plain fnmatch ``*`` already spans ``/``, so ``*.md`` alone also works.)"""
    if fnmatch.fnmatch(rel_posix, pat):
        return True
    return pat.startswith("**/") and fnmatch.fnmatch(rel_posix, pat[3:])


def _matches(rel_posix: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Include/exclude over the path relative to the root. Empty ``include``
    means "all"."""
    if include and not any(_pat_match(rel_posix, p) for p in include):
        return False
    if any(_pat_match(rel_posix, p) for p in exclude):
        return False
    return True


def plocate_paths(root: Root) -> list[Path]:
    """Enumerate files under ``root`` from plocate, applying include/exclude.

    plocate stores REAL paths, so we anchor the regex at the root's realpath (a
    declared symlinked root resolves to its real mount path). Returns regular
    files only (directories and broken entries dropped)."""
    real = os.path.realpath(root.path)
    anchor = "^" + _regex_escape(real.rstrip("/")) + "/"
    proc = subprocess.run(
        ["plocate", "-0", "--regexp", anchor],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode not in (0, 1):  # 1 = no matches, not an error
        raise RegistryError(
            f"plocate failed for {root.id} ({real}): {proc.stderr.strip()}"
        )
    out: list[Path] = []
    for raw in proc.stdout.split("\0"):
        if not raw:
            continue
        p = Path(raw)
        rel = os.path.relpath(raw, real)
        if not _matches(Path(rel).as_posix(), root.include, root.exclude):
            continue
        try:
            if p.is_file():  # one stat; drops dirs and dangling entries
                out.append(p)
        except OSError:
            continue
    return out


def _regex_escape(s: str) -> str:
    """Escape a literal path for plocate's POSIX-ERE ``--regexp``."""
    import re

    return re.escape(s)


# --------------------------------------------------------------------------- #
# Census rows + aggregation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Row:
    root_id: str
    path: str
    ext: str
    size_bytes: int
    producer: str | None
    ingestable: bool


def rows_for_root(root: Root, fmt_map: dict[str, str]) -> list[Row]:
    rows: list[Row] = []
    for p in plocate_paths(root):
        ext, producer, ingestable = classify(p, fmt_map)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        rows.append(Row(root.id, str(p), ext, size, producer, ingestable))
    return rows


@dataclass(frozen=True)
class RootSummary:
    root_id: str
    enabled: bool
    files: int
    bytes: int
    ingestable_files: int
    ingestable_bytes: int
    by_ext: dict[str, int]  # ext -> count, descending


def aggregate(root: Root, rows: list[Row]) -> RootSummary:
    by_ext: dict[str, int] = {}
    for r in rows:
        by_ext[r.ext] = by_ext.get(r.ext, 0) + 1
    by_ext = dict(sorted(by_ext.items(), key=lambda kv: (-kv[1], kv[0])))
    ing = [r for r in rows if r.ingestable]
    return RootSummary(
        root_id=root.id,
        enabled=root.enabled,
        files=len(rows),
        bytes=sum(r.size_bytes for r in rows),
        ingestable_files=len(ing),
        ingestable_bytes=sum(r.size_bytes for r in ing),
        by_ext=by_ext,
    )


# --------------------------------------------------------------------------- #
# Report rendering + optional duckdb dump
# --------------------------------------------------------------------------- #


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "K", "M", "G", "T"):
        if f < 1024 or unit == "T":
            return f"{f:.0f}{unit}" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}T"


def render_report(summaries: list[tuple[RootSummary, list[Row]]]) -> str:
    lines: list[str] = []
    for summary, rows in summaries:
        flag = "" if summary.enabled else "  (census-only — never ingested)"
        pct = (100 * summary.ingestable_files / summary.files) if summary.files else 0.0
        lines.append(f"## {summary.root_id}{flag}")
        lines.append(
            f"  {summary.files} files, {_human(summary.bytes)}  |  "
            f"ingestable today: {summary.ingestable_files} ({pct:.0f}%), "
            f"{_human(summary.ingestable_bytes)}"
        )
        if summary.by_ext:
            top = ", ".join(f"{ext or '(none)'}:{n}" for ext, n in list(summary.by_ext.items())[:10])
            lines.append(f"  by type: {top}")
        not_ing = sorted({r.ext or "(none)" for r in rows if not r.ingestable})
        if not_ing:
            lines.append(f"  no producer yet: {', '.join(not_ing[:15])}")
        for sample in rows[:3]:
            lines.append(f"    e.g. {sample.path}")
        lines.append("")
    return "\n".join(lines)


def dump_duckdb(path: Path, rows: list[Row]) -> None:
    import duckdb

    con = duckdb.connect(str(path))
    try:
        con.execute("DROP TABLE IF EXISTS inventory")
        con.execute(
            "CREATE TABLE inventory (root_id VARCHAR, path VARCHAR, ext VARCHAR, "
            "size_bytes BIGINT, producer VARCHAR, ingestable BOOLEAN)"
        )
        con.executemany(
            "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?)",
            [(r.root_id, r.path, r.ext, r.size_bytes, r.producer, r.ingestable) for r in rows],
        )
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--registry",
        type=Path,
        default=default_registry_path(),
        help="registry file (default: $LIFE_AGENT_KB/config/data-sources.yaml)",
    )
    ap.add_argument("--report", action="store_true", help="census: what is on disk under each root")
    ap.add_argument("--refresh", action="store_true", help="run `sudo updatedb` before reporting")
    ap.add_argument("--duckdb", type=Path, help="also dump inventory rows to this DuckDB file")
    args = ap.parse_args()

    try:
        registry = load_registry(args.registry)
    except RegistryError as e:
        raise SystemExit(str(e))

    if not args.report:
        print(f"loaded {len(registry.roots)} root(s) from {args.registry}:")
        for r in registry.roots:
            state = "enabled" if r.enabled else "census-only"
            print(f"  {r.id:14} {r.kind:9} {state:11} {r.path}")
        print("\nPass --report for an on-disk census.")
        return 0

    if args.refresh:
        subprocess.run(["sudo", "updatedb"], check=True)

    fmt_map = ingestable_formats()
    summaries: list[tuple[RootSummary, list[Row]]] = []
    all_rows: list[Row] = []
    for root in registry.roots:
        if root.kind != "filetree":
            print(f"# {root.id}: kind={root.kind} — summarized by its own adapter, skipped here", file=sys.stderr)
            continue
        rows = rows_for_root(root, fmt_map)
        if not rows:
            print(
                f"# {root.id}: 0 files from plocate at {os.path.realpath(root.path)} — "
                "is /mnt indexed? (see plan Step 0)",
                file=sys.stderr,
            )
        all_rows.extend(rows)
        summaries.append((aggregate(root, rows), rows))

    print(render_report(summaries))
    if args.duckdb:
        dump_duckdb(args.duckdb, all_rows)
        print(f"wrote {len(all_rows)} rows to {args.duckdb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
