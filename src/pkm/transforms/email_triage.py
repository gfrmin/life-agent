"""Email triage transform (SPEC §18.8).

A small, single-purpose **classifier**: consumes an ``email`` artifact and emits
one ``category`` (grammar-constrained to a fixed enum) plus a short ``reason``.
It does **not** extract anything and has no grounding step — it is a perspective
on *what kind* of email this is, nothing more.

It composes with ``action_items`` (§18.7): both run over ``email`` artifacts
independently; the action faculty files a task only when triage says the email is
one the owner must act on (the actionable-category policy lives in ``life_agent``,
not here — pkm classifies, the consumer decides). This is the deliberate split
the owner asked for: the weak local model only does the part it is good at
(categorise into a closed set), and the actionability judgement is deterministic.

Runs on the same local Ollama model as ``action_items`` by default (free, private).
"""

from __future__ import annotations

import json
from typing import Any

from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration
from pkm.transforms._shared import ModelClient, derive_api_schema, make_model_client


class EmailTriageProducer(TransformProducer):
    """Classify an email artifact into a single category (§18.8)."""

    name = "email_triage"
    version = "0.1.0"

    def __init__(
        self,
        *,
        declaration: TransformDeclaration,
        model_client: ModelClient | None = None,
    ) -> None:
        self.model_identity: dict[str, Any] = declaration.model_identity
        self.prompt_name = declaration.prompt_name
        self.output_schema: dict[str, Any] = declaration.output_schema
        self._prompt_template = declaration.prompt_text
        self._client: ModelClient = (
            model_client or make_model_client(declaration.model_identity)
        )
        self.engine_version: str = self._client.engine_version
        self._api_schema = derive_api_schema(declaration.output_schema)

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        text = input_content.decode("utf-8", errors="replace")
        return self._prompt_template.replace("{text}", text)

    def call_model(self, prompt: str) -> ModelResponse:
        return self._client.complete(prompt, self._api_schema)

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        # The model emits {category, reason}; inject format_version so the
        # canonical schema's const validates (§18, grammar kept minimal). The
        # category enum is enforced by ``jsonschema.validate`` in ``produce``.
        parsed: Any = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed.setdefault("format_version", 1)
        return parsed  # type: ignore[no-any-return]
