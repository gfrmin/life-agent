"""Listwise rerank — the recall lever (Slice 4).

Over-fetch a wide lexical pool and let a cloud model surface the chunk that actually carries the
answer into the top-k. It grows neither the corpus nor K; it *reorders* a wide pool so a buried gold
reaches extraction (a recall action, not a VOI gather — discovery over a closed candidate set is
outside the daemon's net_voi; the enlarged/reordered evidence justifies itself on the next decide).
Fail-open: any error (API down, unparseable reply) returns the lexical top-k unchanged, so rerank
can only improve recall, never break the path. The returned dicts are the pool's own (same
artifact_cache_key / chunk_text / origin / score), so every downstream key and citation is intact.

The bridge enacts it as the body's recall action (``/retrieve?rerank=true``). Each rerank is a
content-addressed derivation (``derivations.rerank_key``: the question and the exact snippets
read), sampled at temperature 0 and recorded, so a re-ask reorders identically, costs nothing,
and every re-read keyed on the reranked chunk set replays with it. :func:`rerank` returns the
call's spend so the caller meters it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from life_agent.core import derivations as D
from life_agent.core import pricing as PRC
from life_agent.core.llm import TEMPERATURE, anthropic_complete

RERANK_MODEL = "claude-sonnet-4-6"
RERANK_POOL = 150  # lexical chunks fed to the reranker (covers the deepest addressable gold)
RERANK_SYSTEM = (
    "You are a retrieval reranker for a personal-assistant corpus (English AND Hebrew). "
    "Given a QUESTION and a numbered list of document SNIPPETS, identify the snippets most "
    "likely to contain the EXACT fact needed to answer it. Prefer the specific, current, "
    "authoritative source (an official record, a form, a bill) over generic or incidental "
    "mentions of the same words. Return ONLY a JSON array of the {k} most relevant snippet "
    "numbers, best first — no prose."
)


MAX_TOKENS = 400


def _order(pool: list[dict[str, Any]], picks: list[int], k: int) -> list[dict[str, Any]]:
    """The reranker's valid, de-duplicated picks first, backfilled from the lexical head."""
    seen: set[int] = set()
    ordered: list[dict[str, Any]] = []
    for n in picks:
        if 1 <= n <= len(pool) and n not in seen:
            seen.add(n)
            ordered.append(pool[n - 1])
    for i, h in enumerate(pool, 1):
        if len(ordered) >= k:
            break
        if i not in seen:
            ordered.append(h)
    return ordered[:k]


def rerank(question: str, pool: list[dict[str, Any]], k: int, *, root: Path | None = None,
           model: str = RERANK_MODEL) -> tuple[list[dict[str, Any]], float]:
    """``(the pool's top-k reordered, the spend in USD)``. A recorded rerank replays at $0;
    a failure is the lexical top-k at $0 and is not recorded."""
    if len(pool) <= k:
        return pool[:k], 0.0
    snippets = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:280].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool))
    system = RERANK_SYSTEM.format(k=k)
    key = D.rerank_key(question, D.content_hash(snippets.encode("utf-8")), k=k, model=model,
                       prompt_template=RERANK_SYSTEM, temperature=TEMPERATURE,
                       max_tokens=MAX_TOKENS)
    if root is not None:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            return _order(pool, json.loads(cached)["picks"], k), 0.0
    user = f"QUESTION: {question}\n\nSNIPPETS:\n{snippets}"
    try:
        r = anthropic_complete(system, user, model=model, max_tokens=MAX_TOKENS,
                               temperature=TEMPERATURE)
    except (SystemExit, Exception):  # fail-open to lexical: recall never breaks the path
        return pool[:k], 0.0
    m = re.search(r"\[[\s\d,]*\]", r.text)
    picks = [int(n) for n in re.findall(r"\d+", m.group(0))] if m else []
    cost = PRC.cost_usd(r) or 0.0
    if root is not None:
        D.record(root, key, json.dumps({"picks": picks}).encode("utf-8"),
                 lineage=[{"cache_key": c, "role": "rerank_source"}
                          for c in dict.fromkeys(str(h["artifact_cache_key"]) for h in pool)],
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens,
                           "served_model": r.served_model})
    return _order(pool, picks, k), cost


def rerank_hits(question: str, pool: list[dict[str, Any]], k: int, *,
                root: Path | None = None, model: str = RERANK_MODEL) -> list[dict[str, Any]]:
    """:func:`rerank`'s hits alone."""
    return rerank(question, pool, k, root=root, model=model)[0]
