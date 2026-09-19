#!/usr/bin/env python3
"""Void cached deliberate records that are instrument failures dressed as declines.

A deliberate record whose ``declined`` is true and whose ``tool_calls`` is zero never
touched the corpus — the pkm MCP tools were not used at all (run 6, 2026-08-17: the pkm
MCP server failed to register and opus wrote NOT_IN_CORPUS nine times at ~$1.2 each).
``deliberate.answer`` now classifies such a result as ``status="error"`` and
``record_answer`` refuses it, but the records written before that guard replay as
frozen evidence of absence for their questions under this corpus digest. Voiding them
uses pkm's own sanctioned removal (``pkm.cache.delete_artifact`` — the ``--retry-failed``
path: files first, then the catalogue row) and writes a manifest beside the gate
archives so the removal is disclosed, never silent. Dry-run by default; needs a
read-write catalogue handle, so stop the bridge first.

Usage:
  uv run python scripts/void_deliberate_poison.py [--root DIR] [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import life_agent.core.derivations as D
from life_agent.core import config as LCFG
from pkm.cache import content_file, meta_file


def poisoned_records(root: Path) -> list[dict]:
    """Every deliberate record with ``declined`` and zero ``tool_calls`` — a scan of the
    §18.9 store's meta.json files (the catalogue is not consulted: the files are the
    truth, and a half-reconciled row must not hide a poisoned artifact)."""
    out: list[dict] = []
    for mf in sorted(root.glob("cache/*/*/meta.json")):
        try:
            meta = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("producer_name") != "life_agent.ask.deliberate":
            continue
        key = str(meta["cache_key"])
        cf = content_file(root, key)
        if not cf.exists():
            continue
        try:
            c = json.loads(cf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if c.get("declined") and int(c.get("tool_calls") or 0) == 0:
            out.append({"cache_key": key, "produced_at": meta.get("produced_at"),
                        "question": c.get("question"), "model": c.get("model"),
                        "cost_usd": c.get("cost_usd"),
                        "text_head": str(c.get("text") or "")[:160]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=None,
                    help="pkm knowledge root (default: config.pkm_root())")
    ap.add_argument("--manifest-dir", type=Path,
                    default=LCFG.KB / "eval" / "gate-outside-option")
    ap.add_argument("--apply", action="store_true", help="delete (default: dry-run)")
    args = ap.parse_args(argv)
    root = args.root or LCFG.pkm_root()
    if root is None:
        print("REFUSED: no pkm root (PKM_CONFIG unresolvable)")
        return 2

    rows = poisoned_records(root)
    print(f"{len(rows)} poisoned deliberate record(s) under {root}")
    for r in rows:
        print(f"  {r['cache_key'][:12]} {r['produced_at']} ${r['cost_usd']} "
              f"{str(r['question'])[:60]!r}")
    if not rows:
        return 0
    if not args.apply:
        print("dry-run: nothing removed (pass --apply; stop the bridge first — the "
              "catalogue needs a read-write handle)")
        return 0

    import duckdb

    from pkm.cache import delete_artifact
    conn = duckdb.connect(str(root / "catalogue.duckdb"))
    removed: list[dict] = []
    try:
        for r in rows:
            key = r["cache_key"]
            had_row = delete_artifact(root, conn, key)
            if not had_row:
                # unknown to the catalogue (pending reconciliation) — remove the files
                # the same way, so the key reads as a miss either way
                adir = meta_file(root, key).parent
                if adir.exists():
                    import shutil
                    shutil.rmtree(adir)
            removed.append({**r, "catalogue_row": had_row})
    finally:
        conn.close()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.manifest_dir / f"deliberate-void-{stamp}.json"
    manifest.write_text(json.dumps({
        "voided_at": datetime.now(UTC).isoformat(), "root": str(root),
        "reason": "blind declines (0 tool calls): the pkm MCP server was not "
                  "reachable in the deliberate CLI session — instrument failure "
                  "recorded as evidence of absence; see bayesian-foundations §14 "
                  "(2026-08-17)",
        "records": removed}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"removed {len(removed)} record(s); manifest {manifest}")
    for r in removed:
        assert D.lookup(root, r["cache_key"]) is None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
