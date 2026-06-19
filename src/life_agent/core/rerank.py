"""Listwise rerank — the recall lever (Slice 4).

Over-fetch a wide lexical pool and let a cloud model surface the chunk that actually carries the
answer into the top-k. It grows neither the corpus nor K; it *reorders* a wide pool so a buried gold
reaches extraction (a recall action, not a VOI gather — discovery over a closed candidate set is
outside the daemon's net_voi; the enlarged/reordered evidence justifies itself on the next decide).
Fail-open: any error (API down, unparseable reply) returns the lexical top-k unchanged, so rerank
can only improve recall, never break the path. The returned dicts are the pool's own (same
artifact_cache_key / chunk_text / origin / score), so every downstream key and citation is intact.

Moved here from ``scripts/ask.py`` so the capability bridge can enact it as the body's recall action
(``/retrieve?rerank=true``) — the single source of the reranker, shared by ask-live and the bridge.
"""
from __future__ import annotations

import re
from typing import Any

from life_agent.core.llm import anthropic_complete

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


def rerank_hits(question: str, pool: list[dict[str, Any]], k: int, *,
                model: str = RERANK_MODEL) -> list[dict[str, Any]]:
    """The wide lexical ``pool`` reordered by a listwise reranker to its top-``k``. A short or
    garbled reply is backfilled from the lexical head, so the result is never fewer (or worse on the
    tail) than lexical retrieval alone."""
    if len(pool) <= k:
        return pool[:k]
    snippets = "\n".join(
        f"[{i + 1}] {h['chunk_text'][:280].strip().replace(chr(10), ' ')}"
        for i, h in enumerate(pool))
    user = f"QUESTION: {question}\n\nSNIPPETS:\n{snippets}"
    try:
        r = anthropic_complete(RERANK_SYSTEM.format(k=k), user, model=model, max_tokens=400,
                               temperature=None)
    except SystemExit:
        return pool[:k]
    except Exception:  # any seam failure (API, parse) is fail-open to lexical (recall never breaks)
        return pool[:k]
    m = re.search(r"\[[\s\d,]*\]", r.text)
    picks = [int(n) for n in re.findall(r"\d+", m.group(0))] if m else []
    seen: set[int] = set()
    ordered: list[dict[str, Any]] = []
    for n in picks:  # reranker order first, valid + de-duplicated
        if 1 <= n <= len(pool) and n not in seen:
            seen.add(n)
            ordered.append(pool[n - 1])
    for i, h in enumerate(pool, 1):  # backfill from the lexical head to guarantee k
        if len(ordered) >= k:
            break
        if i not in seen:
            ordered.append(h)
    return ordered[:k]
