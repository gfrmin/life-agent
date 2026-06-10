"""doc_date_email — deterministic Date-header projection (SPEC §18.12).

Consumes an ``email`` artifact (the §7.2 rendered header block + body) and
emits ``{format_version: 1, date: "YYYY-MM-DD" | null}``. ``null`` is a
SUCCESS — the document determinately lacks a parseable Date header — and is
the indeterminate marker for temporal consumers (they name it, never drop it).
No model, no network: the producer pipeline's ``call_model`` is a pure parse.
"""

from __future__ import annotations

import json
from email.utils import parsedate_to_datetime
from typing import Any

from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration

ENGINE_VERSION = "stdlib-email-utils/1"
"""Runtime identity for the schema-3 cache key (SPEC §18.4): the "engine" is
the stdlib parser, hand-versioned — bump on any behavioural change to it."""


class DocDateEmailProducer(TransformProducer):
    """Parse the rendered email's ``Date:`` header into an ISO date."""

    name = "doc_date_email"
    version = "0.1.0"
    engine_version = ENGINE_VERSION

    def __init__(self, *, declaration: TransformDeclaration) -> None:
        self.model_identity: dict[str, Any] = declaration.model_identity
        self.prompt_name = declaration.prompt_name
        self.output_schema: dict[str, Any] = declaration.output_schema

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        # The "prompt" is the header block: everything before the first blank
        # line of the §7.2 rendering. Body lines must not be consulted.
        text = input_content.decode("utf-8", errors="replace")
        return text.split("\n\n", 1)[0]

    def call_model(self, prompt: str) -> ModelResponse:
        date = _parse_date_header(prompt)
        return ModelResponse(
            raw_text=json.dumps({"format_version": 1, "date": date}),
            input_tokens=0, output_tokens=0, latency_ms=0, cost_usd=0.0,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        parsed: dict[str, Any] = json.loads(raw_output)
        return parsed


def _parse_date_header(header_block: str) -> str | None:
    """ISO date from the block's ``Date:`` line, or None when absent or
    unparseable (both are determinate "no date" outcomes, not failures)."""
    for line in header_block.splitlines():
        if line.startswith("Date: "):
            try:
                return parsedate_to_datetime(line[len("Date: "):]).date().isoformat()
            except (ValueError, TypeError):
                return None
    return None
