#!/usr/bin/env python3
"""make_golden — a golden set generated from the corpus, with answers known by construction.

Samples chunks from the live catalogue (one per document), asks a cheap model for the
verbatim point facts each holds (an ID, date, number, name, reference, amount) and a
self-contained question per fact, and keeps a fact only when its answer stands verbatim in
the chunk it came from. The kept rows are written in the eval question schema to
``$LIFE_AGENT_KB/eval/questions_generated.yaml``; ``scripts/score_typed.py`` answers them
through the executor and ``eval/score.py`` scores the result by exact match (set
``generated``).

Owner data never leaves the KB: this prints counts only.

    uv run python scripts/make_golden.py --n 300            # sample 300 documents
    uv run python scripts/make_golden.py --n 20 --dry-run   # counts, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml

from life_agent.core import config as CFG
from life_agent.core import pricing as PRC
from life_agent.core.llm import LLMResult, anthropic_complete

MODEL = "claude-haiku-4-5-20251001"
MAX_ANSWER_CHARS = 60
MIN_CHUNK_CHARS, MAX_CHUNK_CHARS = 200, 4000
SYSTEM = (
    "You read one excerpt from a person's own documents (mail, forms, bills, records). "
    "Extract at most 2 VERBATIM POINT FACTS the person might later ask about: an ID or "
    "reference number, a date, an amount or number, a name, an address line, an account "
    "or policy number. For each, write the question the person would ask to get it back. "
    "Rules: the answer is copied character for character from the excerpt; the question "
    "is self-contained (it names the document, organisation or event, never 'this "
    "document' or 'the excerpt'); the question pins the specific document — its sender, "
    "date, subject or counterparty — so that no other document in a large personal "
    "archive (other invoices, other years, other policies) answers it differently; the "
    "question does not contain the answer. Skip boilerplate (page numbers, legal text, "
    "marketing, generic contact details of large companies). Reply with JSON only: "
    '{"facts": [{"question": "...", "answer": "..."}]} — or {"facts": []} when the '
    "excerpt holds no such fact."
)
PROMPT_SHA = hashlib.sha256(SYSTEM.encode("utf-8")).hexdigest()[:16]

Complete = Callable[[str, str], LLMResult]


def parse_facts(text: str) -> list[dict[str, str]]:
    """The model's JSON reply → its facts; an unparseable reply is no facts."""
    m = re.search(r"\{.*\}", text, re.S)
    if m is None:
        return []
    try:
        facts = json.loads(m.group(0)).get("facts") or []
    except (json.JSONDecodeError, AttributeError):
        return []
    return [{"question": str(f["question"]).strip(), "answer": str(f["answer"]).strip()}
            for f in facts if isinstance(f, dict) and "question" in f and "answer" in f]


def reject_reason(fact: dict[str, str], chunk_text: str) -> str | None:
    """Why a proposed fact is not a golden row, or None to keep it. The answer is known by
    construction only when it stands verbatim in its source chunk."""
    q, a = fact["question"], fact["answer"]
    if not a or not q:
        return "empty"
    if len(a) > MAX_ANSWER_CHARS:
        return "long_answer"
    if a not in chunk_text:
        return "not_verbatim"
    if a.casefold() in q.casefold():
        return "answer_in_question"
    if not re.search(r"[0-9A-Za-z֐-׿]", a):
        return "no_content"
    return None


def sample_chunks(conn: Any, n: int, seed: int) -> list[tuple[str, int, str]]:
    """``n`` chunks from distinct documents, reproducible under ``seed``."""
    rows = conn.execute(
        f"""
        SELECT artifact_cache_key, chunk_index, chunk_text FROM (
            SELECT *, row_number() OVER (PARTITION BY artifact_cache_key
                                         ORDER BY hash(chunk_index + {int(seed)})) AS r
            FROM artifact_chunks
            WHERE length(chunk_text) BETWEEN {MIN_CHUNK_CHARS} AND {MAX_CHUNK_CHARS})
        WHERE r = 1
        ORDER BY hash(artifact_cache_key || '{int(seed)}')
        LIMIT {int(n)}
        """).fetchall()
    return [(str(k), int(i), str(t)) for k, i, t in rows]


def generate(chunks: Sequence[tuple[str, int, str]], complete: Complete,
             *, budget_usd: float) -> tuple[list[dict[str, Any]], Counter[str], float]:
    """Golden rows from sampled chunks; stops at the budget. Returns (rows, counts, spend).

    A question asked of two documents with different answers has no one right answer, so
    every copy is dropped (``ambiguous``); a repeat with the same answer is one row."""
    kept: list[tuple[dict[str, str], str, int]] = []
    counts: Counter[str] = Counter()
    spend = 0.0
    for key, idx, text in chunks:
        if spend >= budget_usd:
            counts["budget_stop"] += 1
            break
        r = complete(SYSTEM, text)
        spend += PRC.cost_usd(r) or 0.0
        counts["chunks"] += 1
        for fact in parse_facts(r.text):
            counts["proposed"] += 1
            why = reject_reason(fact, text)
            if why is not None:
                counts[f"rejected_{why}"] += 1
                continue
            kept.append((fact, key, idx))
    answers: dict[str, set[str]] = {}
    for fact, _, _ in kept:
        answers.setdefault(fact["question"].casefold(), set()).add(fact["answer"])
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact, key, idx in kept:
        q = fact["question"].casefold()
        if len(answers[q]) > 1:
            counts["rejected_ambiguous"] += 1
            continue
        if q in seen:
            counts["rejected_duplicate"] += 1
            continue
        seen.add(q)
        rows.append({
            "id": f"g-{len(rows) + 1:04d}", "question": fact["question"],
            "answer": fact["answer"], "answer_variants": [], "answerable": True,
            "subject": "n/a",
            "provenance": {"artifact_cache_key": key, "chunk_index": idx},
            "generator": {"model": MODEL, "prompt_sha": PROMPT_SHA}})
        counts["kept"] += 1
    return rows, counts, spend


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=300, help="documents to sample")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--budget-usd", type=float, default=3.0)
    ap.add_argument("--out", default=None,
                    help="default: $LIFE_AGENT_KB/eval/questions_generated.yaml")
    ap.add_argument("--dry-run", action="store_true", help="counts only, write nothing")
    a = ap.parse_args(argv)
    out = Path(a.out) if a.out else CFG.KB / "eval" / "questions_generated.yaml"
    if out.exists() and not a.dry_run:
        print(f"refusing to overwrite {out.name}: a pinned set's bytes must not move "
              "(pass --out for a new file)", file=sys.stderr)
        return 2

    from life_agent.core import terminals as TERM

    conn = TERM.connect()
    try:
        chunks = sample_chunks(conn, a.n, a.seed)
    finally:
        conn.close()
    rows, counts, spend = generate(
        chunks, lambda s, u: anthropic_complete(s, u, model=MODEL, max_tokens=400,
                                                temperature=0.0),
        budget_usd=a.budget_usd)
    print(f"sampled {len(chunks)} documents · " + " · ".join(
        f"{k} {v}" for k, v in sorted(counts.items())) + f" · spend ${spend:.2f}")
    if a.dry_run:
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"questions": rows}, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {len(rows)} questions → $LIFE_AGENT_KB/{out.relative_to(CFG.KB)} "
          f"(sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
