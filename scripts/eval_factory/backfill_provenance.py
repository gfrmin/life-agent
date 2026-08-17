#!/usr/bin/env python3
"""backfill_provenance.py — add the content-addressed chunk handle to an existing corpus.

Questions written before factory ``format_version: 2`` cite their gold chunk only by
``chunk_id`` — a **surrogate sequence** (pkm migration 0005). ``pkm rebuild-catalogue``,
the SPEC §13.1 recovery path, re-issues that sequence: afterwards every ``chunk_id`` in
the corpus still resolves to *some* chunk, just the wrong one. Silent, unbounded
corruption of the one field §14's censoring rule keys on. This closes that by recording
``(artifact_cache_key, chunk_index)`` — the ``artifact_chunks`` PRIMARY KEY (migration
0004), and exactly what ``corpus_digest`` hashes.

The join is 1:1 and total: ``chunk_id`` is unique, the pair is the PK. So this is a pure
lookup, not a re-derivation — no model call, no re-verification, no re-sampling.

**The rewrite is additive and mechanically checked.** ``chunk_id`` is kept. Every field
outside ``provenance`` is compared before/after and any difference aborts the write. The
gate's blind discipline requires being able to say "the question set did not move"; this
makes that a checked property rather than a promise. A ``.bak`` is written first, and
re-running is a no-op on already-backfilled questions.

Run:  uv run --project . python scripts/eval_factory/backfill_provenance.py \
          --questions "$LIFE_AGENT_KB/eval/questions_v2.yaml"
      (add --write to apply; default is a dry run)
"""
from __future__ import annotations

import argparse
import copy
import os
import shutil
from pathlib import Path
from typing import Any

import duckdb
import yaml

# Everything outside `provenance` is frozen. Listed positively rather than as
# "not provenance" so a future key added to a question is caught by review, not silently
# waved through as unfrozen.
FROZEN_KEYS = ("id", "question", "subject", "answer", "answer_variants", "notes", "audit")


def catalogue_path(config: Path) -> Path:
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"


def resolve_handles(
    conn: duckdb.DuckDBPyConnection, chunk_ids: list[int]
) -> dict[int, tuple[str, int]]:
    """chunk_id -> (artifact_cache_key, chunk_index) for the ids that still resolve."""
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT chunk_id, artifact_cache_key, chunk_index FROM artifact_chunks "
        f"WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    return {int(cid): (str(key), int(idx)) for cid, key, idx in rows}


def frozen_view(question: dict[str, Any]) -> dict[str, Any]:
    """The part of a question this script must not touch."""
    return {k: question.get(k) for k in FROZEN_KEYS}


def backfill(
    corpus: dict[str, Any], handles: dict[int, tuple[str, int]]
) -> tuple[dict[str, Any], int, list[str]]:
    """Return (new_corpus, n_filled, unresolved_ids). Purely additive."""
    out = copy.deepcopy(corpus)
    filled = 0
    unresolved: list[str] = []
    for q in out.get("questions", []):
        prov = q.get("provenance")
        if not isinstance(prov, dict):
            continue
        if prov.get("artifact_cache_key") is not None:
            continue  # already backfilled — idempotent
        chunk_id = prov.get("chunk_id")
        handle = handles.get(int(chunk_id)) if isinstance(chunk_id, int) else None
        if handle is None:
            unresolved.append(str(q.get("id")))
            continue
        prov["artifact_cache_key"], prov["chunk_index"] = handle
        filled += 1
    return out, filled, unresolved


def assert_provenance_only(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Abort unless the diff is confined to `provenance`. This is the blind-discipline guard."""
    qs_before, qs_after = before.get("questions", []), after.get("questions", [])
    if len(qs_before) != len(qs_after):
        raise SystemExit(f"REFUSED: question count changed {len(qs_before)} -> {len(qs_after)}")
    for b, a in zip(qs_before, qs_after, strict=True):
        if frozen_view(b) != frozen_view(a):
            raise SystemExit(f"REFUSED: non-provenance change in question {b.get('id')!r}")
        for key, value in (b.get("provenance") or {}).items():
            if (a.get("provenance") or {}).get(key) != value:
                raise SystemExit(
                    f"REFUSED: existing provenance key {key!r} changed in {b.get('id')!r} "
                    "— this script may only ADD keys"
                )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--questions", required=True, help="corpus yaml to backfill")
    ap.add_argument("--config", default=os.environ.get("PKM_CONFIG"),
                    help="pkm config yaml (default: $PKM_CONFIG)")
    ap.add_argument("--write", action="store_true", help="apply (default: dry run)")
    args = ap.parse_args()

    if not args.config:
        raise SystemExit("no pkm config: pass --config or set PKM_CONFIG")
    path = Path(args.questions).expanduser()
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))

    questions = corpus.get("questions") or []
    chunk_ids = [
        q["provenance"]["chunk_id"] for q in questions
        if isinstance(q.get("provenance"), dict)
        and isinstance(q["provenance"].get("chunk_id"), int)
    ]
    conn = duckdb.connect(str(catalogue_path(Path(args.config).expanduser())), read_only=True)
    handles = resolve_handles(conn, chunk_ids)

    out, filled, unresolved = backfill(corpus, handles)
    assert_provenance_only(corpus, out)

    print(f"questions            {len(questions)}")
    print(f"cite a chunk_id      {len(chunk_ids)}")
    print(f"resolved in catalogue{len(handles):>6}")
    print(f"backfilled           {filled}")
    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)}): {', '.join(unresolved)}")
        print("  (left without the pair; consumers fall back to chunk_id per-question)")

    if not args.write:
        print("\ndry run — pass --write to apply")
        return 0

    if filled:
        # format_version tracks the provenance shape; a backfilled corpus IS v2.
        out["format_version"] = 2
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text(
            yaml.safe_dump(out, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        print(f"\nwrote {path}  (backup: {backup})")
    else:
        print("\nnothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
