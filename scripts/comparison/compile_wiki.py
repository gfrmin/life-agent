#!/usr/bin/env python3
"""compile_wiki.py — the Phase-0 wiki compiler (SPEC-comparison.md §2).

Authors a wiki for the Phase-0 system from exactly S, with the PINNED answer model. Because S
exceeds one context, the compile is topic-sharded **map-reduce**:
  map    — each shard of source texts → terse owner-fact notes (with source filenames),
  reduce — all notes → a small set of `wiki/*.md` topical pages (the `docs/kb-schema.md` style).

Compiled-once-and-frozen, NOT bit-reproducible (temp-0 ≠ deterministic on a hosted API) — that
asymmetry is a finding (§7c). The compile is metered; its cost is itself a divergence datum (§7d).
Source text is reassembled from the live catalogue's chunks, filtered to the pinned S manifest.

Run:  uv run --project ~/git/pkm python scripts/comparison/compile_wiki.py
Outputs (PII) → $LIFE_AGENT_KB/eval/comparison/wiki/ + compile_meta.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

WIKI_DIR = C.COMPARISON_DIR / "wiki"
PER_SOURCE_CHARS = 5000      # cap per source so the compile cost stays bounded
SHARD_CHARS = 28_000         # ~7k tokens/shard — small enough that dense shards don't drop facts

# Fixed topical pages for the reduce. Sharding the reduce by topic (not one all-pages call)
# prevents the output-token truncation that dropped finances/employment/health on the first run.
TOPICS = [
    ("identity", "identity: national/tax IDs, dates of birth, passports, phone, addresses"),
    ("family", "family members and relationships, births, deaths"),
    ("finances", "bank accounts and numbers, tax IDs, balances"),
    ("property", "home address, property, mortgage (lender, loan number, amount, end date)"),
    ("employment", "employers, job titles, salary, start dates"),
    ("health", "HMO/health-fund membership, insurance policies and numbers, premiums, medical"),
    ("immigration", "visas, citizenship, immigration status (owner and partner)"),
    ("companies", "companies owned, registration/EIN numbers, jurisdictions"),
    ("expenses", "recurring expenses, subscriptions, cloud/SaaS invoices and their amounts/totals"),
]


def source_texts(conn, s_paths: set[str]) -> dict[str, str]:
    """Reassemble per-source extracted text (ordered chunks) for the S sources."""
    rows = conn.execute(
        """
        SELECT s.current_path AS path, ac.chunk_index AS idx, ac.chunk_text AS txt
        FROM artifact_chunks ac
        JOIN artifacts a ON ac.artifact_cache_key = a.cache_key
        JOIN sources  s ON a.input_hash = s.source_id
        WHERE a.status = 'success'
        ORDER BY s.current_path, ac.chunk_index
        """
    ).fetchall()
    by_path: dict[str, list[str]] = {}
    for path, _idx, txt in rows:
        if path in s_paths:
            by_path.setdefault(path, []).append(txt or "")
    return {p: ("\n".join(parts))[:PER_SOURCE_CHARS] for p, parts in by_path.items()}


def shard(texts: dict[str, str]) -> list[list[tuple[str, str]]]:
    """Group (filename, text) into shards under SHARD_CHARS."""
    shards: list[list[tuple[str, str]]] = []
    cur: list[tuple[str, str]] = []
    size = 0
    for path in sorted(texts):
        name = Path(path).name
        t = texts[path]
        if size + len(t) > SHARD_CHARS and cur:
            shards.append(cur)
            cur, size = [], 0
        cur.append((name, t))
        size += len(t)
    if cur:
        shards.append(cur)
    return shards


MAP_SYSTEM = (
    "You are compiling a personal knowledge wiki about the owner (and immediate family) from their "
    "documents. From the SOURCES below, extract only durable, factual statements about the owner's "
    "life — identity, family, finances, property, employment, health, immigration, companies, and "
    "any recurring expenses or accounts. Write terse bullet notes; after each, append the source "
    "filename in parentheses. Note distinct people's identifiers separately (the owner's documents "
    "contain other people's IDs too). Omit boilerplate. If a source has nothing durable, skip it."
)
REDUCE_TOPIC_SYSTEM = (
    "You are authoring ONE page of a personal-life wiki from the fact-notes below. Write the page for "
    "the requested TOPIC only: pull every relevant fact from the notes into clean deduplicated "
    "Markdown, preserving specific values (numbers, dates, amounts, account/policy/ID numbers) EXACTLY "
    "as written, and keeping the (source filename) citations. Keep distinct people's identifiers "
    "clearly attributed (the owner vs others). For an expenses/invoices topic, list each invoice and "
    "compute the total if the notes contain the line items. If the notes contain nothing for this "
    "topic, reply with exactly NONE."
)


def main() -> int:
    reduce_only = "--reduce-only" in sys.argv  # re-author pages from cached map_notes (no map re-run)
    notes_cache = C.COMPARISON_DIR / "map_notes.txt"
    in_tok = out_tok = 0
    secs = 0.0

    if reduce_only and notes_cache.exists():
        all_notes = notes_cache.read_text(encoding="utf-8")
        n_sources = json.loads((C.COMPARISON_DIR / "compile_meta.json").read_text())["n_sources"]
        print(f"reduce-only: re-authoring from cached map_notes ({len(all_notes)} chars)")
    else:
        cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
        conn = duckdb.connect(str(Path(cfg["root_dir"]).expanduser() / "catalogue.duckdb"), read_only=True)
        s_paths = C.snapshot_paths()
        texts = source_texts(conn, s_paths)
        n_sources = len(texts)
        print(f"S sources with extracted text: {len(texts)} / {len(s_paths)} pinned")
        shards = shard(texts)
        print(f"map shards: {len(shards)}")
        notes: list[str] = []
        for i, sh in enumerate(shards):
            block = "\n\n".join(f"### {name}\n{txt}" for name, txt in sh)
            r = C.anthropic_complete(MAP_SYSTEM, f"SOURCES:\n{block}", max_tokens=3000)
            notes.append(r.text)
            in_tok += r.in_tokens; out_tok += r.out_tokens; secs += r.seconds
            print(f"  map {i+1}/{len(shards)}: {len(sh)} src -> {r.out_tokens} note tok")
        all_notes = "\n".join(notes)
        notes_cache.write_text(all_notes, encoding="utf-8")  # reduce re-runnable

    # Topic-sharded reduce: one page per topic, no all-pages truncation.
    pages: dict[str, str] = {}
    for slug, desc in TOPICS:
        r = C.anthropic_complete(REDUCE_TOPIC_SYSTEM,
                                 f"TOPIC: {desc}\n\nFACT-NOTES:\n{all_notes}", max_tokens=4000)
        in_tok += r.in_tokens; out_tok += r.out_tokens; secs += r.seconds
        body = r.text.strip()
        if body and body.upper() != "NONE":
            pages[f"{slug}.md"] = body
        print(f"  reduce[{slug}]: {r.out_tokens} tok{' (empty)' if not pages.get(slug+'.md') else ''}")
    print(f"  -> {len(pages)} wiki pages")

    if WIKI_DIR.exists():
        for old in WIKI_DIR.glob("*.md"):
            old.unlink()
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    for slug, body in pages.items():
        (WIKI_DIR / slug).write_text(body + "\n", encoding="utf-8")

    if reduce_only:
        prior = json.loads((C.COMPARISON_DIR / "compile_meta.json").read_text())
        n_shards_val = prior.get("n_shards", 0)
        in_tok += prior.get("in_tokens", 0); out_tok += prior.get("out_tokens", 0)
        note = ("compiled-once-and-frozen; NOT bit-reproducible (SPEC §2/§7c). Cost includes a "
                "discarded first reduce (the truncation-fix re-run) — an upper bound on the compile.")
    else:
        n_shards_val = len(shards)
        note = "compiled-once-and-frozen; NOT bit-reproducible (SPEC §2/§7c)"
    meta = {
        "model": C.ANSWER_MODEL, "n_sources": n_sources, "n_shards": n_shards_val,
        "n_pages": len(pages), "in_tokens": in_tok, "out_tokens": out_tok,
        "wall_seconds": round(secs, 1), "note": note,
    }
    (C.COMPARISON_DIR / "compile_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nwrote {len(pages)} pages to {WIKI_DIR}")
    print(f"COMPILE COST: {in_tok} in + {out_tok} out tokens, {secs:.0f}s  (a divergence datum, §7d)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
