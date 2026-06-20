"""Temporal-intent classification — the temporal-scope stage's reading of the question.

The owner's correctness is indexed to the question's temporal scope (the staleness thread,
[[correctness-presupposes-knowable-truth]]): "what is my bank?" reads the PRESENT; "what was my
bank in 2022?" reads a specific past (AS-OF); "which banks have I ever used?" reads the whole
HISTORY. The same evidence answers each differently. This module classifies that scope from the
question ALONE — a grammar-constrained local-model verdict, cached file-first per question (the
§18.9 derivations seam), mirroring :func:`life_agent.core.subject.owner_verdict` and
:func:`life_agent.core.lookup.route_question` (the route model already emits a `time_indexed`
bit, but never the question's scope — that is what this adds).

v0 SURFACES and RECORDS the verdict (the temporal footer, the dogfood stream); it changes no
decision yet. Scope-aware inclusion is the next slice and is gate-adjacent — frozen-blind: the
up-conversion of a *current* claim above the assert bar must come from calibrated verdicts, never
recency fiat. A verdict the model cannot settle is ``unscoped`` — the indeterminate, never a
silent scope pick.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from life_agent.core import derivations as D

# Same local model as the route/subject verdicts (the 8 GB card's working model); cached, so the
# call count is bounded by distinct questions, not by askings.
INTENT_MODEL = "qwen2.5:7b-instruct"

INTENT_PROMPT = """\
You classify the TEMPORAL SCOPE of a question the owner asks about their own life.

QUESTION: {question}

Which reading does the question ask for?
- "present": the owner's CURRENT state now (e.g. "what is my bank?", "where do I live?").
- "historical": the owner's WHOLE history / ever (e.g. "which banks have I ever used?").
- "as_of": the state AT A SPECIFIC named past time or event (e.g. "what was my bank in 2022?",
  "my address when I signed the lease?").
- "unscoped": no temporal scope is implied, or the fact does not change (e.g. "what is my
  passport number?", "my date of birth?").

Reply with JSON only: {"scope": "present"} or {"scope": "historical"} or {"scope": "as_of"} or
{"scope": "unscoped"}.
"""

INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["scope"],
    "properties": {
        "scope": {"type": "string",
                  "enum": ["present", "historical", "as_of", "unscoped"]},
    },
}

Scope = Literal["present", "historical", "as_of", "unscoped"]
_SCOPES = ("present", "historical", "as_of", "unscoped")


def _as_scope(value: object) -> Scope:
    if value not in _SCOPES:
        raise ValueError(f"temporal_intent emitted a scope outside the enum: {value!r}")
    return value  # type: ignore[return-value]


def intent_verdict(root: Path, question: str, *, client: Any | None = None) -> Scope:
    """Classify the question's temporal scope — cached, local, loud. A replayed verdict is
    deterministic per question; only a cache miss calls the model. A scope outside the enum
    raises and is NEVER recorded (§18.11 miss-path parity: junk must not be frozen)."""
    if client is None:
        from pkm.transforms._shared import make_model_client

        client = make_model_client({
            "provider": "ollama", "model": INTENT_MODEL,
            "inference_params": {"temperature": 0.0},
        })
    key = D.temporal_intent_key(
        question, model=INTENT_MODEL, prompt_template=INTENT_PROMPT,
        engine_version=str(client.engine_version), output_schema=INTENT_SCHEMA,
    )
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        return _as_scope(json.loads(cached.decode("utf-8"))["scope"])

    prompt = INTENT_PROMPT.replace("{question}", question)
    response = client.complete(prompt, INTENT_SCHEMA)
    scope = _as_scope(json.loads(response.raw_text).get("scope"))
    D.record(
        root, key,
        json.dumps({"format_version": 1, "scope": scope},
                   sort_keys=True, ensure_ascii=False).encode("utf-8"),
        lineage=[],
    )
    return scope
