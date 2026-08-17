#!/usr/bin/env python3
"""pin_corpus.py — name and freeze a corpus version (foundations §8/§14).

A **corpus version** is an immutable named manifest whose re-hash *is* ``corpus_digest``.
It is not a copy of the store. The pkm cache is content-addressed and monotone — nothing
reaps artifacts (SPEC §13.2), a file move is a metadata event, and only *adding* chunked
artifacts moves the digest — so version *n+1* is a strict superset of *n*. Copying 2.8 GB
to express "the same bytes plus a few hundred more" is redundancy, not identity. The
manifest is ~1 MB and says exactly what a copy would have proved.

It **verifies itself**: recomputing ``sha256(canonical_json({artifacts, chunks}))`` over the
recorded key list must reproduce the recorded digest, because that list is precisely what
``corpus_digest`` hashes.

Why this exists: the §8 gate compares Δ across runs, and that comparison is only meaningful
if the runs saw the same retrieval universe. Until now nothing recorded which universe a run
saw — "the corpus digest held across all firings" was an operator check, not an artifact
property (see the §14 correction, and ``scripts/forensics/corpus_timeline.py`` for the
reconstruction). ``verify`` makes it checkable *before* a run spends money.

Distinct from ``scripts/comparison/pin_snapshot.py``, which pins **source files**
({path, sha256, bytes}) for the Phase-0/Phase-1 comparison study. This pins the **chunked
universe** retrieval actually ranks over. Orthogonal; do not unify.

Manifests live at ``$LIFE_AGENT_KB/eval/corpus/<name>.json`` — beside the artefact they
serve, next to ``eval/gate/`` and the existing ``eval/snapshot_S.json``.

Run:  uv run --project . python scripts/corpus/pin_corpus.py pin --name full-2026-06-11
      uv run --project . python scripts/corpus/pin_corpus.py verify --name full-2026-06-11
      uv run --project . python scripts/corpus/pin_corpus.py diff A B
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

from life_agent.core.corpus import corpus_digest

FORMAT_VERSION = 1


def kb_root() -> Path:
    return Path(os.environ.get("LIFE_AGENT_KB", str(Path.home() / ".life-agent/kb")))


def manifest_dir() -> Path:
    return kb_root() / "eval" / "corpus"


def manifest_path(name: str) -> Path:
    return manifest_dir() / f"{name}.json"


def catalogue_path(config: Path) -> Path:
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"


def build_manifest(conn: duckdb.DuckDBPyConnection, *, name: str, catalogue: Path,
                   note: str = "") -> dict[str, Any]:
    """The chunked universe, in the exact shape ``corpus_digest`` hashes."""
    rows = conn.execute(
        "SELECT artifact_cache_key, count(*) FROM artifact_chunks "
        "GROUP BY 1 ORDER BY 1"
    ).fetchall()
    keys = [str(k) for k, _ in rows]
    counts = [int(n) for _, n in rows]
    (n_sources,) = conn.execute("SELECT count(*) FROM sources").fetchone()  # type: ignore[misc]
    (schema_version,) = conn.execute(  # type: ignore[misc]
        "SELECT max(schema_version) FROM schema_meta"
    ).fetchone()
    stat = catalogue.stat()
    return {
        "format_version": FORMAT_VERSION,
        "name": name,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_digest": corpus_digest(conn),
        "n_artifacts": len(keys),
        "n_chunks": sum(counts),
        "artifacts": keys,
        "chunk_counts": counts,
        # Where it was pinned from. Diagnostic only — none of this is hashed, because the
        # corpus is defined by its content, not by which box or path held it.
        "pkm_root_realpath": str(catalogue.parent.resolve()),
        "catalogue_path": str(catalogue),
        "catalogue_size_bytes": stat.st_size,
        "catalogue_mtime": datetime.fromtimestamp(stat.st_mtime, UTC)
                                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
        # A re-chunk under a new migration changes chunk identity without necessarily
        # changing the artifact set, so the schema version belongs in the identity record.
        "catalogue_schema_version": schema_version,
        "n_sources": n_sources,
        "note": note,
    }


def self_digest(manifest: dict[str, Any]) -> str:
    """Recompute the digest from the manifest alone — the self-verification property."""
    import hashlib

    from pkm.hashing import canonical_json

    payload = canonical_json(
        {"artifacts": list(manifest["artifacts"]), "chunks": int(manifest["n_chunks"])}
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_manifest(name: str) -> dict[str, Any]:
    path = manifest_path(name)
    if not path.exists():
        raise SystemExit(f"no such corpus pin: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def key_diff(a: dict[str, Any], b: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(added_in_b, removed_in_b) over the artifact key sets."""
    sa, sb = set(a["artifacts"]), set(b["artifacts"])
    return sorted(sb - sa), sorted(sa - sb)


def cmd_pin(args: argparse.Namespace) -> int:
    catalogue = catalogue_path(Path(args.config).expanduser())
    conn = duckdb.connect(str(catalogue), read_only=True)
    manifest = build_manifest(conn, name=args.name, catalogue=catalogue, note=args.note or "")

    if self_digest(manifest) != manifest["corpus_digest"]:
        raise SystemExit("REFUSED: manifest does not re-hash to its own digest")

    path = manifest_path(args.name)
    if path.exists():
        existing = load_manifest(args.name)
        if existing["corpus_digest"] == manifest["corpus_digest"]:
            print(f"already pinned, digest unchanged: {path}")
            return 0
        # A named version is immutable — that is the entire point. Re-pointing a name at a
        # different universe would silently invalidate every run that cited it.
        raise SystemExit(
            f"REFUSED: {args.name} is already pinned to a DIFFERENT corpus\n"
            f"  pinned: {existing['corpus_digest']}\n"
            f"  live:   {manifest['corpus_digest']}\n"
            "A corpus name is immutable. Pin the new state under a new name."
        )

    manifest_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"pinned {args.name}")
    print(f"  digest    {manifest['corpus_digest']}")
    print(f"  artifacts {manifest['n_artifacts']}  chunks {manifest['n_chunks']}")
    print(f"  wrote     {path}  ({path.stat().st_size / 1e6:.2f} MB)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.name)
    if self_digest(manifest) != manifest["corpus_digest"]:
        print(f"CORRUPT: {args.name} does not re-hash to its recorded digest")
        return 2

    conn = duckdb.connect(str(catalogue_path(Path(args.config).expanduser())), read_only=True)
    live = corpus_digest(conn)
    if live == manifest["corpus_digest"]:
        print(f"MATCH  {args.name}  {live}")
        print(f"  {manifest['n_artifacts']} artifacts / {manifest['n_chunks']} chunks")
        return 0

    live_manifest = build_manifest(conn, name="<live>", catalogue=Path("."))
    added, removed = key_diff(manifest, live_manifest)
    print(f"MISMATCH  {args.name}")
    print(f"  pinned {manifest['corpus_digest']}")
    print(f"  live   {live}")
    print(f"  +{len(added)} artifacts added, -{len(removed)} removed since the pin")
    for k in added[:5]:
        print(f"    + {k}")
    for k in removed[:5]:
        print(f"    - {k}")
    return 2


def cmd_diff(args: argparse.Namespace) -> int:
    a, b = load_manifest(args.a), load_manifest(args.b)
    added, removed = key_diff(a, b)
    print(f"{args.a} -> {args.b}")
    print(f"  {a['corpus_digest'][:16]}… -> {b['corpus_digest'][:16]}…")
    print(f"  artifacts {a['n_artifacts']} -> {b['n_artifacts']}  "
          f"(+{len(added)} / -{len(removed)})")
    print(f"  chunks    {a['n_chunks']} -> {b['n_chunks']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", default=os.environ.get("PKM_CONFIG"),
                    help="pkm config yaml (default: $PKM_CONFIG)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pin", help="freeze the live corpus under a name")
    p.add_argument("--name", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_pin)

    v = sub.add_parser("verify", help="compare a pin against the live corpus")
    v.add_argument("--name", required=True)
    v.set_defaults(fn=cmd_verify)

    d = sub.add_parser("diff", help="compare two pins")
    d.add_argument("a")
    d.add_argument("b")
    d.set_defaults(fn=cmd_diff)

    args = ap.parse_args()
    if args.cmd in ("pin", "verify") and not args.config:
        raise SystemExit("no pkm config: pass --config or set PKM_CONFIG")
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
