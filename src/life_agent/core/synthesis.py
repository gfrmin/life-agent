"""Cited-answer synthesis — the narrative family's proposal stage.

The owner asks a question that is NOT a single point-fact lookup (a list, an aggregate, a compound
"when and where") — the typed router declines it. The narrative family answers it: synthesize a
concise CITED answer over the retrieved sources, then `core.narrative.narrative_answer` audits each
claim against its cited card and includes it only if grounded AND EU-positive (so an ungrounded or
weak claim is dropped — gate-safe by construction). This module is the proposal stage, lifted from
`scripts/ask.py::answer` so the answer-brain bridge and the ask REPL share ONE synthesizer + ONE
cache (the cache key hashes the retrieval-set content + the owner-profile hash + the prompt, all kept
byte-identical here — a divergence would orphan recorded syntheses).
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pkm.hashing import canonical_json

import life_agent.core as C
from life_agent.core import derivations as D

ANSWER_SYSTEM = (
    "You are the owner's personal assistant, answering questions about the owner's own life. "
    "You are given an OWNER block (authoritative facts about who the owner is — names, IDs) and "
    "numbered SOURCES (chunks retrieved from the owner's documents). Answer from these; put a "
    "bracketed source number like [1] immediately after each fact a SOURCE supports. If the answer "
    "is in neither, say so plainly and name what would be needed — do not guess.\n"
    "Rules specific to a personal corpus:\n"
    "1. Read every question in the first person about the owner. 'How do I make money' means "
    "'what are my sources of income, per my records' — NOT a request for generic advice.\n"
    "2. The OWNER block is the authority on the owner's identity: answer 'what is my name / my ID "
    "/ my phone' from it directly. Use it to judge whose document a SOURCE is — a SOURCE whose "
    "subject is a person or ID the OWNER block identifies as someone ELSE (a partner, a family "
    "member) is NOT the owner's; never assert another person's name or ID as the owner's.\n"
    "3. Otherwise attribute documents to the owner by default: a contract they signed, their tax "
    "certificate, their CV, an offer addressed to them all describe the owner even when they don't "
    "repeat the owner's name on every line. The exception is a document that positively identifies "
    "a DIFFERENT person as its subject. Be concise."
)


def cards_from_hits(hits: Sequence[dict[str, Any]]) -> list[C.SourceCard]:
    """Pure: number a retrieval set as cited source cards (mirrors ask.py `_cards_from_set`)."""
    return [C.SourceCard(n=i + 1, text=h["chunk_text"].strip(), origin=h["origin"])
            for i, h in enumerate(hits)]


def set_content(hits: Sequence[dict[str, Any]]) -> bytes:
    """Pure: the canonical bytes of a retrieval set — what the synthesize key hashes (the
    early-cutoff hinge: equal evidence ⇒ equal hash). Byte-identical to ask.py `_set_content`."""
    return canonical_json({"format_version": 1, "hits": list(hits)}).encode("utf-8")


def synthesize(root: Path | None, question: str, hits: Sequence[dict[str, Any]], profile: str, *,
               no_cache: bool = False,
               extra_lineage: Sequence[dict[str, str]] = ()) -> tuple[str, str, bool]:
    """Synthesize a cited answer over the retrieved sources. Returns ``(text, cache_key, cached)``
    (``cached`` = served from the derivation cache). Content-addressed (key = retrieval-set content +
    profile hash + prompt + model). Fail-open: the caller decides what to do with the prose; the
    narrative scorer audits it downstream."""
    cards = cards_from_hits(hits)
    skey = D.synthesize_key(question, D.content_hash(set_content(hits)),
                            D.content_hash(profile.encode("utf-8")),
                            model=C.DEFAULT_ANSWER_MODEL, prompt_template=ANSWER_SYSTEM,
                            temperature=C.TEMPERATURE, max_tokens=600)
    if root is not None and not no_cache:
        cached = D.lookup(root, skey.cache_key)
        if cached is not None:
            return cached.decode("utf-8"), skey.cache_key, True
    blocks = []
    if profile:
        blocks.append(f'OWNER (authoritative — who "I"/"my" refers to):\n{profile}')
    blocks.append(f"SOURCES:\n{C.render_sources_block(cards) if cards else '(none retrieved)'}")
    user = f"QUESTION: {question}\n\n" + "\n\n".join(blocks)
    r = C.anthropic_complete(ANSWER_SYSTEM, user, max_tokens=600)
    text = r.text.strip()
    if root is not None:
        lineage = list(extra_lineage) + [{"cache_key": ck, "role": "source"} for ck in
                  dict.fromkeys(h["artifact_cache_key"] for h in hits)]
        D.record(root, skey, text.encode("utf-8"), lineage=lineage,
                 metadata={"in_tokens": r.in_tokens, "out_tokens": r.out_tokens,
                           "seconds": round(r.seconds, 3)})
    return text, skey.cache_key, False
