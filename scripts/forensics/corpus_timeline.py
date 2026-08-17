#!/usr/bin/env python3
"""corpus_timeline.py — reconstruct when the retrieval universe last moved.

Read-only. Exists because §14's corpus-constancy claims ("the corpus digest held across
all firings") were operator memory: no gate report before run 6 ever carried a digest, so
the claim had no artifact behind it. This recovers the fact from the catalogue instead,
and is the command those §14 entries cite.

Two independent evidence streams:

  1. **The complete one.** ``max(produced_at)`` over artifacts that have chunks. Only
     chunked artifacts enter ``corpus_digest`` (`life_agent.core.corpus`), so this is the
     newest moment the retrieval universe *could* have changed — regardless of what else
     the store has been writing since. Ask-stage artifacts are never chunked by design
     (`core/corpus.py:11-12`), which is why the store's mtime moves while the corpus does
     not.
  2. **The corroborating one** (``--cache-timeline``, slower). ``retrieve``/``deliberate``
     cache keys embed the digest in ``StageKey.inputs`` (`core/derivations.py:148,313`),
     and pkm persists ``inputs`` into each artifact's ``meta.json``. So every cached
     derivation is an incidental timestamped record of the digest when it fired. Nobody
     designed this as provenance; it reads as provenance anyway.

This is forensic reconstruction, not an artifact property of past runs — see the §14
evidence-class note. It also cannot recover the *membership set* behind a past digest:
``artifact_chunks`` has no timestamp column. Digest identity is recoverable; digest
contents for past runs are not. Both gaps close from run 6, via the pinned manifest.

Run:  uv run --project . python scripts/forensics/corpus_timeline.py
      uv run --project . python scripts/forensics/corpus_timeline.py --root /home/g/Downloads
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import duckdb
import yaml

from life_agent.core.corpus import corpus_digest
from pkm.cache import artifact_dir

# Stages that key on the corpus digest, hence carry it in their cached meta.json.
_DIGEST_KEYED_STAGES = ("life_agent.ask.retrieve", "life_agent.ask.deliberate")


def catalogue_path(config: Path) -> Path:
    """The live catalogue, resolved the same way every eval path resolves it."""
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"


def store_root(config: Path) -> Path:
    return Path(yaml.safe_load(config.read_text(encoding="utf-8"))["root_dir"]).expanduser()


def freeze_point(conn: duckdb.DuckDBPyConnection) -> tuple[str, str, int, int]:
    """(newest, oldest, n_artifacts, n_chunks) over the *chunked* universe only.

    The join is the whole point: an artifact with no chunks is invisible to retrieval and
    to ``corpus_digest``, so its produced_at says nothing about the corpus.
    """
    newest, oldest = conn.execute(  # type: ignore[misc]
        "SELECT max(a.produced_at), min(a.produced_at) FROM artifacts a "
        "JOIN artifact_chunks ch ON ch.artifact_cache_key = a.cache_key"
    ).fetchone()
    n_artifacts, n_chunks = conn.execute(  # type: ignore[misc]
        "SELECT count(DISTINCT artifact_cache_key), count(*) FROM artifact_chunks"
    ).fetchone()
    return str(newest), str(oldest), n_artifacts, n_chunks


def since(conn: duckdb.DuckDBPyConnection, ts: str) -> list[tuple[str, int]]:
    """Producers that HAVE written since the freeze point — the ones that don't chunk."""
    return conn.execute(
        "SELECT producer_name, count(*) FROM artifacts WHERE produced_at > ? "
        "GROUP BY 1 ORDER BY 2 DESC",
        [ts],
    ).fetchall()


def root_share(conn: duckdb.DuckDBPyConnection, prefix: str) -> tuple[int, int, int, int]:
    """(root_artifacts, all_artifacts, root_chunks, all_chunks) for a path prefix.

    Reported as both shares because they diverge sharply: a root of heavily-chunked files
    (CSVs) can be a rounding error in artifacts and a quarter of what retrieval ranks over.
    §14's availability entry originally quoted only the artifact share.
    """
    r_art, r_chunks = conn.execute(  # type: ignore[misc]
        "SELECT count(DISTINCT ch.artifact_cache_key), count(*) FROM artifact_chunks ch "
        "JOIN artifacts a ON a.cache_key = ch.artifact_cache_key "
        "JOIN sources s ON s.source_id = a.input_hash "
        "WHERE s.current_path LIKE ? || '%'",
        [prefix],
    ).fetchone()
    t_art, t_chunks = conn.execute(  # type: ignore[misc]
        "SELECT count(DISTINCT artifact_cache_key), count(*) FROM artifact_chunks"
    ).fetchone()
    return r_art, t_art, r_chunks, t_chunks


def cache_timeline(conn: duckdb.DuckDBPyConnection, root: Path) -> list[tuple[str, str, str]]:
    """Digest transitions recorded incidentally in digest-keyed stages' meta.json.

    Returns (produced_at, digest, producer) for each *change*, oldest first. Unreadable or
    schema-surprising meta files are skipped: this is corroboration, and a partial read
    must never look like a transition.
    """
    rows = conn.execute(
        "SELECT cache_key, producer_name, produced_at FROM artifacts "
        f"WHERE producer_name IN ({','.join('?' * len(_DIGEST_KEYED_STAGES))}) "
        "AND status = 'success' ORDER BY produced_at",
        list(_DIGEST_KEYED_STAGES),
    ).fetchall()

    out: list[tuple[str, str, str]] = []
    seen: str | None = None
    for cache_key, producer, produced_at in rows:
        meta_file = artifact_dir(root, cache_key) / "meta.json"
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        inputs = (meta.get("producer_metadata") or {}).get("inputs") or {}
        digest = inputs.get("corpus")
        if not isinstance(digest, str) or digest == seen:
            continue
        seen = digest
        out.append((str(produced_at), digest, producer))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", default=os.environ.get("PKM_CONFIG"),
                    help="pkm config yaml (default: $PKM_CONFIG)")
    ap.add_argument("--root", help="report a path prefix's share of the retrieval universe")
    ap.add_argument("--cache-timeline", action="store_true",
                    help="corroborate from cached digest-keyed derivations (slower)")
    args = ap.parse_args()

    if not args.config:
        raise SystemExit("no pkm config: pass --config or set PKM_CONFIG")
    config = Path(args.config).expanduser()
    conn = duckdb.connect(str(catalogue_path(config)), read_only=True)

    newest, oldest, n_artifacts, n_chunks = freeze_point(conn)
    print("== the chunked universe (what corpus_digest hashes) ==")
    print(f"  live corpus_digest   {corpus_digest(conn)}")
    print(f"  artifacts / chunks   {n_artifacts} / {n_chunks}")
    print(f"  oldest chunked       {oldest}")
    print(f"  NEWEST chunked       {newest}   <- the corpus has not moved since this")

    later = since(conn, newest)
    if later:
        total = sum(n for _, n in later)
        print(f"\n== written since, but NOT chunked ({total} artifacts) ==")
        for producer, n in later:
            print(f"  {producer:36} {n}")
        print("  (none of these enter corpus_digest — core/corpus.py:11-12)")

    if args.root:
        r_art, t_art, r_chunks, t_chunks = root_share(conn, args.root)
        print(f"\n== share of the retrieval universe under {args.root} ==")
        print(f"  artifacts  {r_art} / {t_art} = {100 * r_art / t_art:.1f}%")
        print(f"  chunks     {r_chunks} / {t_chunks} = {100 * r_chunks / t_chunks:.1f}%")

    if args.cache_timeline:
        transitions = cache_timeline(conn, store_root(config))
        print(f"\n== digest transitions recorded in cached derivations ({len(transitions)}) ==")
        for produced_at, digest, producer in transitions:
            print(f"  {produced_at}  {digest[:16]}…  {producer}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
