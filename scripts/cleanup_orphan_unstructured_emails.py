#!/usr/bin/env python3
"""Delete orphaned ``unstructured`` artifacts for email sources after the
pkm v0.5.0 migration to the dedicated ``email`` producer.

Before v0.5.0, ``.eml`` routed to ``unstructured``. After, it routes to
``email``, which re-extracts each message under a NEW cache key. The old
``unstructured`` artifacts for those sources are now orphans: stale, and their
chunks would double-count email content in the FTS index. This one-time script
removes them — chunks first (``artifact_chunks`` has no cascade), then the
artifact via ``cache.delete_artifact`` (which also removes the cache files).

Operational and KB-specific (it mutates the live catalogue), so it lives in
life-agent, not pkm. **DRY-RUN by default** — pass ``--apply`` to delete.
Idempotent: re-running after a clean reports 0.

Run in the pkm env (for the pkm package + DuckDB):
    uv run --project ~/git/pkm python \
        scripts/cleanup_orphan_unstructured_emails.py \
        --config ~/yo/pkm/live/config.yaml [--apply]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from pkm.cache import delete_artifact
from pkm.catalogue import open_catalogue

_QUERY = """
    SELECT a.cache_key
    FROM artifacts a
    JOIN source_tags t ON t.source_id = a.input_hash
    WHERE a.producer_name = 'unstructured' AND t.tag = 'email'
    ORDER BY a.cache_key
"""


def _root(config_path: Path) -> Path:
    cfg = yaml.safe_load(config_path.expanduser().read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, type=Path, help="pkm config.yaml")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually delete (default: dry-run, no mutation)",
    )
    args = ap.parse_args()
    root = _root(args.config)

    with open_catalogue(root) as conn:
        keys = [r[0] for r in conn.execute(_QUERY).fetchall()]
        n_chunks = 0
        if keys:
            placeholders = ",".join("?" * len(keys))
            (n_chunks,) = conn.execute(
                "SELECT count(*) FROM artifact_chunks "
                f"WHERE artifact_cache_key IN ({placeholders})",
                keys,
            ).fetchone()

        print(
            f"orphan unstructured-email artifacts: {len(keys)} "
            f"({n_chunks} chunks)"
        )
        if not keys:
            print("nothing to clean.")
            return 0

        if not args.apply:
            for k in keys[:5]:
                print(f"  would delete {k[:12]}…")
            if len(keys) > 5:
                print(f"  … and {len(keys) - 5} more")
            print("DRY RUN — nothing deleted. Re-run with --apply to delete.")
            return 0

        deleted = 0
        for k in keys:
            # Chunks first (no FK cascade), in their own transaction.
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(
                    "DELETE FROM artifact_chunks WHERE artifact_cache_key = ?",
                    [k],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            # delete_artifact runs its own transaction for lineage + row + files.
            delete_artifact(root, conn, k)
            deleted += 1
        print(f"deleted {deleted} orphan artifacts + their chunks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
