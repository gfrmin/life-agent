"""Action-item extraction transform (SPEC §18.6).

Consumes an ``email`` artifact and emits grounded action items — concrete
to-dos the recipient must personally do, each with a verbatim ``source_quote``
that resolves in the email under §18.5 whitespace-normalised containment. An
ungrounded quote fails the whole source (no partial output, §14.3), so a weaker
local model loses recall but cannot emit a hallucinated action.

Runs on the declaration-pinned model (Anthropic haiku since the 2026-08-17
local-Ollama deprecation); the
provider/model is a one-line knob in the declaration (`model:`). The model-facing
schema and the LLM call are supplied by the provider seam in ``_shared``.
"""

from __future__ import annotations

import json
from typing import Any

from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration
from pkm.transforms._shared import (
    ModelClient,
    derive_api_schema,
    make_model_client,
    quote_is_grounded,
)


class ActionItemsProducer(TransformProducer):
    """Grounded action-item extraction over an email artifact (§18.6)."""

    name = "action_items"
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
        # The model is not asked to emit format_version (§18 keeps the grammar
        # minimal); inject it so the canonical schema's const validates.
        parsed: Any = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed.setdefault("format_version", 1)
        return parsed  # type: ignore[no-any-return]

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        """Ground every ``source_quote`` against the email (SPEC §18.5).

        Whitespace-normalised containment: a quote that does not resolve in the
        email body fails the entire source. No filtering, no partial output.
        """
        text = input_content.decode("utf-8", errors="replace")
        for i, item in enumerate(parsed.get("action_items", [])):
            quote = item.get("source_quote", "")
            if not quote_is_grounded(quote, text):
                raise ValueError(
                    f"action_items[{i}]: source_quote not grounded "
                    f"in the email: {quote!r}"
                )
