"""The ``extract@<model>`` edge — whole-document, subject-aware joint extraction.

The per-chunk local extractor (``lookup.observe_hits``) reads one chunk at a time and so cannot
tell WHOSE value a number is: in a document that names several people it mis-attributes (it
assigned a relative's passport to the owner). This edge hands a cloud model the ORDERED
chunk-set as one document and asks for a single value with a CALIBRATED confidence and an
as-of date — so it can read attribution across the whole context and withhold when the value
belongs to someone else. It is the executor's costlier extraction edge; the executor runs it by
VOI, picking the model tier (``claude-haiku-…`` / ``-sonnet-…`` / ``-opus-…``) as the cost knob.

Everything-on-ledger (system-design §3): the edge is a content-addressed node, key-before-call
(``derivations.joint_extract_key``), so a re-ask of a committed question costs zero tokens. The
**model must be a dated snapshot, never an alias** — LLM APIs are non-stationary; the key pins
the snapshot and the served model is recorded for audit.

The returned ``confidence`` is the model's SELF-REPORT — overconfident, worst when wrong. It is
NEVER folded as a reliability directly: the executor maps it through the per-edge calibration
curve (``core.calibration``) before it reaches ``decide``.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.core import derivations as D
from life_agent.core.llm import LLMResult, anthropic_complete

JOINT_SYSTEM = (
    "You answer a question about the OWNER's life STRICTLY from the provided documents. The "
    "owner asks in the first person ('my'); the documents are the owner's own (English AND "
    "Hebrew). Read ALL the documents together and return ONLY a JSON object: "
    '{"value": <the exact answer string, or null if the documents do not contain it>, '
    '"confidence": <your CALIBRATED probability 0..1 that value is the correct CURRENT answer>, '
    '"as_of": <ISO date the value is valid as-of, or null>}. '
    "ATTRIBUTION IS CRITICAL: a document may mention OTHER people (a relative, a colleague, "
    "another party in an email thread — e.g. a thread asking about a family member's passport "
    "number, or a contact's address). A value that belongs to someone ELSE is NOT the owner's "
    "answer — return null rather than assign another person's value to the owner. Only return a "
    "value the documents attribute to the OWNER. "
    "Be honest and calibrated: if the documents are stale, ambiguous, weakly supported, or you "
    "cannot tell WHOSE value it is, LOWER the confidence; a confidently WRONG answer is far "
    "worse than admitting uncertainty. Never guess a value not in the documents — return null. "
    "No prose."
)

_SNIPPET_CHARS = 400
# the completion seam — injectable for tests; default omits temperature (Opus rejects it)
CompleteFn = Callable[[str, str, str, int], LLMResult]


@dataclass(frozen=True)
class JointResult:
    """One joint extraction: the candidate value, the model's self-reported confidence (to be
    calibrated before use), its as-of date, and the cost (zero on a cache hit)."""

    value: str | None
    confidence: float
    as_of: str | None
    cache_key: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    served_model: str = ""


def _default_complete(system: str, user: str, model: str, max_tokens: int) -> LLMResult:
    return anthropic_complete(system, user, model=model, max_tokens=max_tokens,
                              temperature=None)


def _snippets(hits: list[dict[str, Any]], k: int) -> list[str]:
    return [str(h["chunk_text"])[:_SNIPPET_CHARS].strip().replace("\n", " ")
            for h in hits[:k]]


def _parse(text: str) -> dict[str, Any]:
    """Defensive parse of the model's JSON object (fail-safe: a garbled reply ⇒ a null value
    at zero confidence — a withhold, never a confident guess)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        obj = {}
    raw = obj.get("value")
    value = str(raw).strip() if raw not in (None, "") else None
    confidence = float(obj.get("confidence") or 0.0) if value else 0.0
    as_of = obj.get("as_of")
    return {"value": value, "confidence": confidence,
            "as_of": str(as_of) if as_of else None}


def extract_joint(root: Path | None, question: str, hits: list[dict[str, Any]], *,
                  model: str, k: int = 20, max_tokens: int = 400,
                  complete: CompleteFn | None = None) -> JointResult:
    """Read the top-k hits as one document and return one calibrated candidate (cache-first).
    ``model`` MUST be a dated snapshot. The chunk-set hash keys on exactly the ordered snippets
    the model reads (the early-cutoff hinge), so a reranked-but-identical pool replays."""
    do_complete = complete or _default_complete
    pool = hits[:k]
    snippets = _snippets(pool, k)
    chunk_set_sha = D.content_hash(
        json.dumps({"chunks": snippets}, ensure_ascii=False).encode("utf-8"))
    key = D.joint_extract_key(question, chunk_set_sha, model=model,
                              prompt_template=JOINT_SYSTEM, engine_version=D.ENGINE_VERSION,
                              output_schema=D.JOINT_EXTRACT_OUTPUT_SCHEMA)
    if root is not None:
        cached = D.lookup(root, key.cache_key)
        if cached is not None:
            p = json.loads(cached.decode("utf-8"))
            return JointResult(p["value"], p["confidence"], p["as_of"],
                               cache_key=key.cache_key)
    user = "QUESTION: {q}\n\nDOCUMENTS:\n{docs}".format(
        q=question, docs="\n".join(f"[{i + 1}] {s}" for i, s in enumerate(snippets)))
    res = do_complete(JOINT_SYSTEM, user, model, max_tokens)
    parsed = _parse(res.text)
    if root is not None:
        D.record(root, key,
                 json.dumps(parsed, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                 lineage=[{"cache_key": str(h["artifact_cache_key"]), "role": "joint_source"}
                          for h in pool],
                 metadata={"in_tokens": res.in_tokens, "out_tokens": res.out_tokens,
                           "served_model": res.served_model})
    return JointResult(parsed["value"], parsed["confidence"], parsed["as_of"],
                       cache_key=key.cache_key, in_tokens=res.in_tokens,
                       out_tokens=res.out_tokens, served_model=res.served_model)
