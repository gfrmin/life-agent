#!/usr/bin/env python3
"""data_source_registry.py — one declarative registry for the local data roots
life-agent feeds into the pkm memory, plus a thin ``--report`` (census) view.

A single registry (``data-sources.yaml``) describes each local data root: where it
is, which adapter handles it (``kind``), which files to include, and whether it's
eligible for ingestion — replacing the earlier ad-hoc wiring (hardcoded corpus
scripts, per-script manifests, hand-copied entries in pkm's ``sources.yaml``).

It does NOT ingest — ``ingest_sources.py`` consumes this registry to stage files and
hand them to pkm. This file owns: loading/validating the registry, and reporting what
is on disk under each root (enumerated from **plocate**, the system file index, once
its prune list is configured to cover your data roots).

The registry is PII-bearing (real folder names reveal personal context), so the real
file lives OUTSIDE this public repo at ``$LIFE_AGENT_KB/config/data-sources.yaml``;
a fake example of the schema is ``config/data-sources.example.yaml``. Same split as
``mail_bridge.py`` / ``mail-corpus.example.yaml``.

Run from the repo root (has PyYAML, duckdb, and the pkm producers whose ``handled_formats``
define "ingestable today"):
    uv run --project . python scripts/data_source_registry.py --report
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

# What a root's absence MEANS. `enabled: false` used to carry this load alone, conflating
# three unrelated intents — "deliberately deferred corpus", "no producer for these types
# yet", and "this disk isn't plugged in" — and the third failed as a SystemExit that took
# every other root's ingest down with it. Splitting them is what lets the same registry
# describe a corpus that is only partly present on a given machine.
AVAILABILITY_REQUIRED = "required"   # absence is an error: this machine should have it
AVAILABILITY_OPTIONAL = "optional"   # absence is expected somewhere: skip it, say so
AVAILABILITY_DEFERRED = "deferred"   # never ingested anywhere (the census-only intent)
VALID_AVAILABILITY = frozenset(
    {AVAILABILITY_REQUIRED, AVAILABILITY_OPTIONAL, AVAILABILITY_DEFERRED})


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
    # Declared intent when the path is missing (see the AVAILABILITY_* constants). Defaults
    # to `required` for an enabled root and `deferred` for a disabled one, so a registry
    # written before this field behaves exactly as it did.
    availability: str = AVAILABILITY_REQUIRED

    def resolves(self) -> bool:
        """Is this root actually present on THIS machine right now? Note a root can
        resolve and still be a different corpus — `downloads` is a real directory on both
        boxes holding different files — so this answers presence, never equivalence."""
        return self.path.is_dir()


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
    enabled = bool(entry.get("enabled", True))
    availability = entry.get(
        "availability", AVAILABILITY_REQUIRED if enabled else AVAILABILITY_DEFERRED)
    if availability not in VALID_AVAILABILITY:
        raise RegistryError(
            f"roots[{i}] ({entry['id']}) has unknown availability {availability!r}; "
            f"expected one of {sorted(VALID_AVAILABILITY)}"
        )
    return Root(
        id=entry["id"],
        kind=kind,
        path=Path(entry["path"]).expanduser().absolute(),
        include=tuple(entry.get("include") or ()),
        exclude=tuple(entry.get("exclude") or ()),
        tags=tuple(entry.get("tags") or ()),
        enabled=enabled,
        staging_dir=Path(staging).expanduser().absolute() if staging else None,
        availability=availability,
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
# Ingest guard — never feed the agent's own memory back into the corpus
# --------------------------------------------------------------------------- #


def _within(path: Path | str, ancestors: tuple[str, ...]) -> bool:
    """True if ``path`` (symlinks resolved) equals or sits inside any ancestor
    realpath. Both sides are realpath'd so a symlinked root cannot slip past."""
    rp = os.path.realpath(path)
    return any(rp == a or rp.startswith(a.rstrip("/") + "/") for a in ancestors)


def forbidden_ingest_zones(pkm_config: Path | str | None = None) -> tuple[str, ...]:
    """Realpaths that must NEVER be ingested — the circular case where the agent
    would feed its own memory back into the corpus:

      * ``$LIFE_AGENT_KB`` — the knowledge base (eval gold answers, dogfood Q/A
        logs, FAILURES notes). Ingesting it lets retrieval surface its own past
        answers instead of the source documents, and pollutes provenance.
      * the pkm content store (``root_dir``) — the cache + catalogue (the extracted
        text itself). Re-ingesting the memory is doubly circular.

    Derived from the environment (or the given ``pkm_config``), so no machine path
    is baked into this public repo. The mail *staging* dir is a sibling of
    ``root_dir`` (not inside it), so legitimately-staged email is unaffected."""
    zones = [os.path.realpath(_kb_root())]
    store = _pkm_store_real(pkm_config)
    if store:
        zones.append(store)
    return tuple(dict.fromkeys(zones))  # de-dupe, preserve order


def assert_roots_ingestable(
    roots: tuple[Root, ...], *, pkm_config: Path | str | None = None
) -> None:
    """Fail-closed guard, called at the ingest boundary before any staging: raise
    if an *enabled* root resolves inside a forbidden zone. Census-only roots
    (``enabled: false``) are exempt — they are never ingested, so a disabled root
    may still point at the KB for inventory."""
    zones = forbidden_ingest_zones(pkm_config)
    bad = [(r.id, os.path.realpath(r.path)) for r in roots if r.enabled and _within(r.path, zones)]
    if bad:
        listing = ", ".join(f"{rid} ({rp})" for rid, rp in bad)
        raise RegistryError(
            "refusing to ingest root(s) inside a protected zone — the agent's own KB "
            f"or the pkm content store: {listing}. Feeding the memory back into the "
            "corpus is circular; move the root, or mark it `enabled: false` (census-only)."
        )


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
    from pkm.producers.docling import DoclingProducer
    from pkm.producers.email_producer import EmailProducer
    from pkm.producers.pandoc import PandocProducer
    from pkm.producers.tesseract import TesseractProducer
    from pkm.producers.unstructured import UnstructuredProducer

    mapping: dict[str, str] = {}
    for prod in (
        UnstructuredProducer, TesseractProducer, DoclingProducer, PandocProducer, EmailProducer,
    ):
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
    return not any(_pat_match(rel_posix, p) for p in exclude)


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
    # presence on THIS machine, so a census can be read without guessing whether a root
    # reported 0 files because it is empty or because it is not here
    resolves: bool = True
    availability: str = AVAILABILITY_REQUIRED


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
        resolves=root.resolves(),
        availability=root.availability,
    )


# --------------------------------------------------------------------------- #
# Discovery — the inverse of the census: sweep the whole data mount from plocate
# and surface the dirs that are NOT yet declared roots (so you can decide what is
# worth ingesting). The census audits *declared* roots; discovery finds the rest.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Candidate:
    """An undeclared top-level directory under the discovery root."""

    name: str  # path component directly under the discovery root ("." = loose files)
    files: int
    ingestable_files: int
    by_ext: dict[str, int]  # ingestable ext -> count, descending (the promote signal)
    samples: tuple[str, ...]  # up to 3 example ingestable paths


def discovery_root(roots: tuple[Root, ...], override: str | None) -> Path:
    """The directory to sweep. An explicit ``override`` wins; otherwise the
    common ancestor of every declared root's realpath (symlinks resolved), so the
    sweep covers exactly the mount the corpus already lives under — no hard-coded,
    machine-specific path."""
    if override:
        return Path(override).expanduser().absolute()
    if not roots:
        raise RegistryError("cannot infer a discovery root from an empty registry; pass a path")
    reals = [os.path.realpath(r.path) for r in roots]
    return Path(reals[0] if len(reals) == 1 else os.path.commonpath(reals))


def _covered(path: str, declared_reals: tuple[str, ...]) -> bool:
    """True if ``path`` lies inside any declared root's realpath. Coverage is by
    location, not by a root's include/exclude: discovery looks for entirely
    undeclared *areas*, not for filtered-out files within a known one."""
    return any(path == real or path.startswith(real + "/") for real in declared_reals)


def _plocate_under(root: Path) -> list[str]:
    """Raw plocate entries (files AND dirs, un-stat'd) under ``root``'s realpath.
    Anchored like ``plocate_paths`` but without the per-entry stat — the whole-mount
    sweep would otherwise pay millions of stats. We stat only the undeclared tail."""
    real = os.path.realpath(root)
    anchor = "^" + _regex_escape(real.rstrip("/")) + "/"
    proc = subprocess.run(
        ["plocate", "-0", "--regexp", anchor], capture_output=True, text=True, check=False
    )
    if proc.returncode not in (0, 1):
        raise RegistryError(f"plocate failed for discovery ({real}): {proc.stderr.strip()}")
    return [s for s in proc.stdout.split("\0") if s]


def bucket_undeclared(files: list[str], base: Path, fmt_map: dict[str, str]) -> list[Candidate]:
    """Group undeclared *files* by their first path component under ``base``,
    counting ingestable coverage per group. Pure (no I/O) — the caller supplies
    the already-enumerated file list, so this is what the tests drive."""
    groups: dict[str, list[str]] = {}
    for p in files:
        rel = os.path.relpath(p, base)
        parts = rel.split(os.sep)
        groups.setdefault(parts[0] if len(parts) > 1 else ".", []).append(p)

    candidates: list[Candidate] = []
    for name, paths in groups.items():
        by_ext: dict[str, int] = {}
        ingestable: list[str] = []
        for p in paths:
            ext, _producer, ok = classify(Path(p), fmt_map)
            if ok:
                ingestable.append(p)
                by_ext[ext] = by_ext.get(ext, 0) + 1
        by_ext = dict(sorted(by_ext.items(), key=lambda kv: (-kv[1], kv[0])))
        candidates.append(
            Candidate(name, len(paths), len(ingestable), by_ext, tuple(sorted(ingestable)[:3]))
        )
    candidates.sort(key=lambda c: (-c.ingestable_files, -c.files, c.name))
    return candidates


@dataclass(frozen=True)
class Discovery:
    root: Path
    candidates: tuple[Candidate, ...]
    total: int  # all plocate entries under root
    covered: int  # entries inside a declared root


def discover(
    registry: Registry, override: str | None, extra_covered: tuple[str, ...] = ()
) -> Discovery:
    """Sweep ``base`` and bucket the entries that fall under no declared root.

    Deliberately *stat-free*: a whole-mount sweep is millions of entries, and one
    ``stat`` each (just to drop directories) made it unusable. We classify
    ingestability from the path's extension instead — directories have no
    producer-bearing extension, so they fall out of the ingestable counts on their
    own; they only pad the raw path tally. ``extra_covered`` lets the caller mask
    non-source areas that live under ``base`` (e.g. the pkm content store itself)."""
    base = discovery_root(registry.roots, override)
    # A root covers both its source path and its staging dir (e.g. a maildir root's
    # .eml symlink tree lives under the pkm dir, not under the root's path).
    declared_reals = (
        tuple(
            os.path.realpath(p)
            for r in registry.roots
            for p in (r.path, r.staging_dir)
            if p is not None
        )
        + extra_covered
    )
    raw = _plocate_under(base)
    undeclared = [p for p in raw if not _covered(p, declared_reals)]
    candidates = bucket_undeclared(undeclared, base, ingestable_formats())
    return Discovery(base, tuple(candidates), len(raw), len(raw) - len(undeclared))


def _pkm_store_real(pkm_config: Path | str | None = None) -> str | None:
    """Realpath of the pkm content store (``root_dir`` in the pkm config) — the
    cache/catalogue, which sit under the same mount as the sources but are not
    themselves a corpus candidate. Uses ``pkm_config`` if given, else ``$PKM_CONFIG``.
    Best-effort: a missing/unreadable config returns ``None`` (nothing masked)."""
    cfg = str(pkm_config) if pkm_config else os.environ.get("PKM_CONFIG")
    if not cfg:
        return None
    try:
        data = yaml.safe_load(Path(cfg).expanduser().read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    root = data.get("root_dir") if isinstance(data, dict) else None
    return os.path.realpath(Path(root).expanduser()) if isinstance(root, str) else None


def _pkm_store_reals() -> tuple[str, ...]:
    """Tuple form used to mask the memory itself during ``discover``."""
    real = _pkm_store_real()
    return (real,) if real else ()


def render_discovery(d: Discovery) -> str:
    lines = [
        f"## discovery: {d.root}",
        f"  {d.total} indexed paths — {d.covered} under declared roots, "
        f"{d.total - d.covered} undeclared in {len(d.candidates)} dir(s)",
        "",
        "  undeclared dirs (ranked by ingestable files — candidates to declare):",
    ]
    for c in d.candidates:
        exts = ", ".join(f"{e or '(none)'}:{n}" for e, n in list(c.by_ext.items())[:8])
        hint = f"  ({exts})" if exts else "  (no ingestable types)"
        lines.append(
            f"    {c.name + '/':22} {c.files:>8,} paths, "
            f"{c.ingestable_files:>6,} ingestable{hint}"
        )
        for s in c.samples:
            lines.append(f"        e.g. {s}")
    if not d.candidates:
        lines.append("    (nothing undeclared — the whole mount is covered by declared roots)")
    return "\n".join(lines)


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
        if not summary.resolves:
            flag += f"  (NOT PRESENT here — availability={summary.availability})"
        pct = (100 * summary.ingestable_files / summary.files) if summary.files else 0.0
        lines.append(f"## {summary.root_id}{flag}")
        lines.append(
            f"  {summary.files} files, {_human(summary.bytes)}  |  "
            f"ingestable today: {summary.ingestable_files} ({pct:.0f}%), "
            f"{_human(summary.ingestable_bytes)}"
        )
        if summary.by_ext:
            top = ", ".join(
                f"{ext or '(none)'}:{n}" for ext, n in list(summary.by_ext.items())[:10]
            )
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
    ap.add_argument(
        "--discover",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="inverse of --report: sweep the mount (default: common ancestor of the "
        "declared roots; or PATH) and list the dirs NOT yet declared as roots",
    )
    ap.add_argument("--refresh", action="store_true", help="run `sudo updatedb` before reporting")
    ap.add_argument("--duckdb", type=Path, help="also dump inventory rows to this DuckDB file")
    args = ap.parse_args()

    try:
        registry = load_registry(args.registry)
    except RegistryError as e:
        raise SystemExit(str(e)) from e

    if args.refresh:
        subprocess.run(["sudo", "updatedb"], check=True)

    if args.discover is not None:
        print(render_discovery(discover(registry, args.discover or None, _pkm_store_reals())))
        return 0

    if not args.report:
        print(f"loaded {len(registry.roots)} root(s) from {args.registry}:")
        for r in registry.roots:
            state = "enabled" if r.enabled else "census-only"
            here = "present" if r.resolves() else "ABSENT"
            print(f"  {r.id:14} {r.kind:9} {state:11} {r.availability:9} "
                  f"{here:7} {r.path}")
        print("\nPass --report for an on-disk census.")
        return 0

    fmt_map = ingestable_formats()
    summaries: list[tuple[RootSummary, list[Row]]] = []
    all_rows: list[Row] = []
    for root in registry.roots:
        if root.kind != "filetree":
            print(
                f"# {root.id}: kind={root.kind} — summarized by its own adapter, skipped here",
                file=sys.stderr,
            )
            continue
        rows = rows_for_root(root, fmt_map)
        if not rows:
            # Distinguish the two zero-file causes. They used to print the same line, so an
            # unmounted disk read as an indexing problem and a machine missing half the
            # corpus looked like a machine with a stale plocate database.
            if not root.resolves():
                print(
                    f"# {root.id}: NOT PRESENT on this machine ({root.path}) "
                    f"[availability={root.availability}] — 0 files, not an index problem",
                    file=sys.stderr,
                )
            else:
                print(
                    f"# {root.id}: 0 files from plocate at {os.path.realpath(root.path)} — "
                    "the path exists, so this is an index question: is /mnt indexed? "
                    "(see plan Step 0)",
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
