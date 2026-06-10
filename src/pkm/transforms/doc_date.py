"""doc_date — grammar-constrained local-model date projection (SPEC §18.12).

Consumes a text-extractor artifact (docling/pandoc/tesseract — one declaration
per input producer, all dispatching here: the projection is a function of
content, not of which extractor produced it) and emits
``{format_version: 1, date: "YYYY-MM-DD" | null}`` — the document's own
primary date, or ``null`` when none is determinable (the indeterminate marker
for temporal consumers; a success, not a failure).

``post_validate`` rejects a non-null date that is not a real calendar date:
the schema's pattern admits ``2026-13-45``, and a wrong date silently cached
forever is exactly the §18.11 failure mode (fail loudly, never cache).
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration
from pkm.transforms._shared import (
    ModelClient,
    derive_api_schema,
    make_model_client,
)

_MAX_INPUT_CHARS = 6000
"""Head-cap on the text given to the model. A document's primary date leads it
(letterheads, invoice headers, report covers); capping bounds latency on the
8 GB local model. Part of the producer's logic — changing it bumps ``version``."""


class DocDateProducer(TransformProducer):
    """Project one primary date from a text artifact (§18.12)."""

    name = "doc_date"
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
        return self._prompt_template.replace("{text}", text[:_MAX_INPUT_CHARS])

    def call_model(self, prompt: str) -> ModelResponse:
        return self._client.complete(prompt, self._api_schema)

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        # The model emits {date}; inject format_version so the canonical
        # schema's const validates (the §18.8 pattern — grammar kept minimal).
        parsed: Any = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed.setdefault("format_version", 1)
        return parsed  # type: ignore[no-any-return]

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        date = parsed.get("date")
        if date is None:
            return
        try:
            datetime.date.fromisoformat(date)
        except ValueError as e:
            raise ValueError(
                f"doc_date emitted a non-calendar date {date!r}: {e}"
            ) from e
