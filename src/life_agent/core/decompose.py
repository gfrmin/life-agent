"""Decompose — split a question into the labeled single-value fields it asks for.

Foundations §5 (the owner's ruling: *transformations flow from questions*). A question may
ask for several distinct point facts at once ("my mortgage — lender, amount, and end date"
asks three); the single-value extractor can return only ONE value, so a compound question
necessarily drops or confuses fields. Decompose splits the question into its labeled
single-value sub-questions, so each becomes its OWN candidate set + posterior, decided
per-field by the daemon (no pooling, no ``slots>1`` route-fork). The slots flow from the
QUESTION — not a declared per-construct vocabulary — so a one-value question is the degenerate
one-field case and the single-value read-path is preserved exactly.

A cached local-model verdict, the :func:`life_agent.core.lookup.route_question` pattern: keyed
on the question alone (§18.9), recorded once, replayed free. The parse is **consumer-side**
over the RAW recorded reply (the ``observe_hits`` grounding-gate precedent): a blank
sub-question is dropped, and an empty / junk decomposition degrades to the whole-question field
(§9 no-hard-zeros) — a bad verdict never drops the question, it falls back to single-field.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.core import derivations as D
from life_agent.core.lookup import LOOKUP_MODEL

DECOMPOSE_PROMPT = """\
A question may ask for SEVERAL distinct factual values at once, or for just one. Split it
into the separate single-value questions it asks. Each part must ask for exactly ONE value.

CRITICAL: each sub-question must be FULLY self-contained — restate the shared TOPIC (the
specific thing the values belong to), not just "my". When one part of the question names a
topic and another part asks for an attribute of that same topic, REPEAT the topic in the
attribute's sub-question, so a sub-question is never more ambiguous than the original. A
sub-question that loses the topic ("what is my member number?" instead of "what is my HMO
member number?") would match the wrong record — never do this.

Examples:
- "What is my mortgage — lender, amount, and end date?"
  three values: "What is the lender of my mortgage?", "What is the amount of my mortgage?",
  "When does my mortgage end?"
- "What HMO am I a member of and what is my member number?"
  two values: "What HMO am I a member of?", "What is my HMO member number?"
  (the second REPEATS "HMO" — the member number belongs to the HMO named in the first part)
- "When did my father die and where?"
  two values: "When did my father die?", "Where did my father die?"
- "What is my passport number?"
  one value: "What is my passport number?"

QUESTION: {question}

Reply with JSON only — one entry per single value the question asks for (a single-value
question gives exactly one entry):
{"fields": [{"label": "<2-4 word name of the value>", \
"question": "<fully self-contained single-value question, with the shared topic restated>"}]}
"""

DECOMPOSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["fields"],
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "question"],
                "properties": {"label": {"type": "string"},
                               "question": {"type": "string"}},
            },
        },
    },
}


@dataclass(frozen=True)
class Field:
    """One labeled single-value field a question asks for (foundations §5).

    ``question`` is the self-contained single-value sub-question that routes, retrieves,
    extracts, and decides on its own; ``label`` names the field for the assembled render."""

    label: str
    question: str


def _client() -> Any:
    from pkm.transforms._shared import make_model_client

    return make_model_client({
        "provider": "ollama", "model": LOOKUP_MODEL,
        "inference_params": {"temperature": 0.0},
    })


def _fields_from(parsed: dict[str, Any], question: str) -> list[Field]:
    """The consumer-side parse over the raw recorded reply: keep each well-formed labeled
    field (non-blank sub-question; label defaults to the sub-question), and degrade to the
    whole-question single field when the reply names none (§9 — never drop the question)."""
    fields: list[Field] = []
    for f in parsed.get("fields") or []:
        if not isinstance(f, dict):
            continue
        sub_q = str(f.get("question") or "").strip()
        if not sub_q:
            continue
        label = str(f.get("label") or "").strip() or sub_q
        fields.append(Field(label=label, question=sub_q))
    return fields or [Field(label=question, question=question)]


def decompose_question(root: Path, question: str, *,
                       client: Any | None = None) -> list[Field]:
    """The labeled single-value fields ``question`` asks for, cached per question. One field
    for a single-value question (the read-path-preserving degenerate case); N for a compound
    one. A misdecomposition degrades to the whole-question field — never silence (§9)."""
    if client is None:
        client = _client()
    key = D.lookup_decompose_key(question, model=LOOKUP_MODEL,
                                 prompt_template=DECOMPOSE_PROMPT,
                                 engine_version=str(client.engine_version),
                                 output_schema=DECOMPOSE_SCHEMA)
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        parsed = json.loads(cached.decode("utf-8"))
    else:
        response = client.complete(DECOMPOSE_PROMPT.replace("{question}", question),
                                   DECOMPOSE_SCHEMA)
        parsed = json.loads(response.raw_text)
        if not isinstance(parsed.get("fields"), list):
            raise ValueError(f"lookup_decompose emitted junk: {parsed!r}")
        D.record(root, key,
                 json.dumps({"format_version": 1, "fields": parsed["fields"]},
                            sort_keys=True, ensure_ascii=False).encode("utf-8"),
                 lineage=[])
    return _fields_from(parsed, question)
