#!/usr/bin/env python
"""Derive doc_subject + doc_date over the eval questions' retrieval slice (§4.1).

The lookup family's covariates consume these projections read-side; an underived
projection admits a hit as indeterminate, at the stated attenuation instead of the
verdict's. This script makes the demand explicit: for every eval question, resolve
the production retrieval set (expand + retrieve — identical to ask.py's path), find
hits whose doc_subject / doc_date projection is underived, and demand each via
``pkm derive <decl> --input <key>`` (cache-first and idempotent — a warm chain makes
zero model calls, so re-runs are free).

Run: uv run python scripts/derive_eval_slice.py [--dry-run] [--k 20]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask  # noqa: E402
from run_eval import load_questions  # noqa: E402

from life_agent.core import subject as S  # noqa: E402
from life_agent.core import temporal as T  # noqa: E402


def slice_keys(conn, root, questions: list[dict], k: int) -> list[str]:
    """The union of hit artifact keys over the eval questions' production queries."""
    keys: dict[str, None] = {}
    for q in questions:
        terms = ask._expand_terms(q["question"], root=root)
        query = ask.build_query(q["question"], terms)
        for h in ask._retrieve_set(conn, query, k):
            keys.setdefault(h["artifact_cache_key"])
        print(f"  {q['id']}: {len(keys)} cumulative artifacts")
    return list(keys)


def remedies_for(conn, root, keys: list[str]) -> list[tuple[str, str]]:
    """(declaration, input_key) pairs for every underived projection over the slice."""
    pairs: list[tuple[str, str]] = []
    skipped = 0
    for hit in S.project_subjects(conn, root, keys, caller="derive_eval_slice"):
        if hit.state != "underived":
            continue
        decl = S._DERIVE_DECL_BY_EXTRACTOR.get(hit.extractor)
        if decl is None:
            skipped += 1
            continue
        pairs.append((decl, hit.artifact_cache_key))
    for dated in T.project_dates(conn, root, keys, caller="derive_eval_slice"):
        if dated.state != "underived":
            continue
        decl = T._DERIVE_DECL_BY_EXTRACTOR.get(dated.extractor)
        if decl is None:
            skipped += 1
            continue
        pairs.append((decl, dated.artifact_cache_key))
    if skipped:
        print(f"  (skipped {skipped} underived hits with no declaration "
              f"for their extractor)")
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=20, help="top-k per query")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the pkm derive commands without running them")
    args = parser.parse_args()

    questions = load_questions()
    root = ask._pkm_root()
    if root is None:
        raise SystemExit("no pkm root — cannot derive")
    conn = ask.connect()

    print(f"Resolving the retrieval slice over {len(questions)} questions (k={args.k}) …")
    keys = slice_keys(conn, root, questions, args.k)
    print(f"{len(keys)} distinct artifacts in the slice")

    pairs = remedies_for(conn, root, keys)
    print(f"{len(pairs)} underived projections to demand")
    if args.dry_run:
        for decl, key in pairs:
            print(f"pkm derive {decl} --input {key}")
        return 0

    failures = 0
    for i, (decl, key) in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] pkm derive {decl} --input {key[:16]}…", flush=True)
        proc = subprocess.run(
            ["uv", "run", "pkm", "derive", decl, "--input", key,
             "--caller", "derive_eval_slice"],
            capture_output=True, text=True)
        if proc.returncode != 0:
            failures += 1
            print(f"  FAILED ({proc.returncode}): {proc.stderr.strip()[-300:]}")
    print(f"done: {len(pairs) - failures} derived, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
