#!/usr/bin/env python3
"""The carrier census (r33 A5, conferral 2 §3.1) — sweep spellings, exclude substrings.

Four rounds of the Stage-4 measurement took carrier censuses from ONE spelling of one
string; round 8 mis-stated two of its own nine golds that way (a "carrier" that was a
substring inside a longer number; a missed second carrier under another spelling). The
manifest rule this tool enacts: **a census sweeps every supplied spelling AND excludes
substring hits** — and it reports how the DEPLOYED candidate rule groups those spellings,
imported from ``core.lookup``, never re-implemented (the standing lesson: a census must
read the deployed rule end-to-end; its fifth instance was minted by exactly that copy).

    uv run python scripts/carrier_census.py --db /path/to/catalogue.duckdb \
        "2,378 kWh" "2378"            # PII-OK: synthetic meter figures

Read-only. Prints per-spelling carrier counts, the union, substring-only documents
(named, never silently dropped), and the engine's spelling groups — one group per
deployed candidate key, so a census can SEE when the engine splits what the owner reads
as one value. ``--context`` conjoins a required second substring (the mining idiom).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from life_agent.core import lookup as LK  # noqa: E402

#: The deployed candidate-identity rule — a BINDING (the census reads the engine's own
#: grouping; a second spelling of this rule is how round 10's audit flipped a verdict).
engine_key = LK._candidate_key


def standalone(text: str, spelling: str) -> bool:
    """True iff ``spelling`` occurs OUTSIDE any longer alphanumeric token — a value
    embedded in a longer number/word (the coordinate-array class) is not a carrier."""
    pat = r"(?<![0-9A-Za-z])" + re.escape(spelling) + r"(?![0-9A-Za-z])"
    return re.search(pat, text) is not None


def engine_groups(spellings: Sequence[str]) -> dict[str, list[str]]:
    """The spellings grouped by the DEPLOYED candidate key: >1 group = the engine reads
    these as different candidates (the norm-class split, made visible at mining time)."""
    out: dict[str, list[str]] = {}
    for s in spellings:
        out.setdefault(engine_key(s), []).append(s)
    return out


def census(conn: Any, spellings: Sequence[str], *,
           context: str | None = None) -> dict[str, Any]:
    """Doc-level carriers of ANY spelling (word-boundary), per-spelling counts, and the
    substring-only documents. ``context`` conjoins a required plain substring."""
    per: dict[str, set[str]] = {}
    substring_only: set[str] = set()
    for s in spellings:
        rows: Iterable[tuple[str, str]] = conn.execute(
            "SELECT artifact_cache_key, chunk_text FROM artifact_chunks "
            "WHERE chunk_text LIKE ?", [f"%{s}%"]).fetchall()
        docs: set[str] = set()
        for key, text in rows:
            if context is not None and context not in text:
                continue
            if standalone(text, s):
                docs.add(key)
            else:
                substring_only.add(key)
        per[s] = docs
    carriers: set[str] = set().union(*per.values()) if per else set()
    return {"per_spelling": per, "carriers": carriers,
            "substring_only": substring_only - carriers,
            "groups": engine_groups(spellings)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="catalogue.duckdb (opened read-only)")
    ap.add_argument("--context", default=None,
                    help="require this plain substring in the same chunk")
    ap.add_argument("spellings", nargs="+")
    args = ap.parse_args()

    import duckdb
    conn = duckdb.connect(args.db, read_only=True)
    try:
        out = census(conn, args.spellings, context=args.context)
    finally:
        conn.close()

    print(f"carrier census — {len(args.spellings)} spelling(s), "
          f"union {len(out['carriers'])} carrier document(s)")
    for s, docs in out["per_spelling"].items():
        print(f"  {s!r}: {len(docs)} document(s)")
    if out["substring_only"]:
        print(f"  substring-only (EXCLUDED, {len(out['substring_only'])} doc(s)): "
              + ", ".join(sorted(out["substring_only"])))
    print("engine groups (deployed candidate key):")
    for key, members in out["groups"].items():
        tag = "" if len(out["groups"]) == 1 else "  <- the engine SPLITS these spellings"
        print(f"  {key}: {members!r}")
    if len(out["groups"]) > 1:
        print("  NOTE: >1 group — the engine reads these spellings as DIFFERENT "
              "candidates (the norm class); a census that assumes one is wrong.")
    print("union carriers: " + (", ".join(sorted(out["carriers"])) or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
