"""doc_subject — grammar-constrained local-model subject projection (SPEC §18.13).

Consumes a text-extractor or email artifact (one declaration per input
producer, all dispatching here: the projection is a function of content, not
of which extractor produced it) and emits
``{format_version: 1, subject_kind: "person"|"organisation"|"generic",
subject: string|null}`` — who or what the document is primarily about, with
the name copied as written (any language; matching is consumer-side policy,
identity never enters pkm).

``generic`` is a determinate "about no specific entity" (blank forms,
templates, reference material) — the §18.12 null-date analogue, a success.
``post_validate`` enforces the shape's internal consistency: a named kind
must carry a name, ``generic`` must not — a violation cached forever is
exactly the §18.11 failure mode (fail loudly, never cache).
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
)

_MAX_INPUT_CHARS = 6000
"""Head-cap on the text given to the model. A document's subject leads it
(ID-card headers, payslip names, letterheads); capping bounds latency on the
8 GB local model. Part of the producer's logic — changing it bumps ``version``."""

_NAMED_KINDS = ("person", "organisation")


class DocSubjectProducer(TransformProducer):
    """Project one primary subject from a text artifact (§18.13)."""

    name = "doc_subject"
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
        # The model emits {subject_kind, subject}; inject format_version so the
        # canonical schema's const validates (the §18.8 pattern — grammar kept
        # minimal).
        parsed: Any = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed.setdefault("format_version", 1)
        return parsed  # type: ignore[no-any-return]

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        kind = parsed.get("subject_kind")
        subject = parsed.get("subject")
        if kind in _NAMED_KINDS and not subject:
            raise ValueError(
                f"doc_subject emitted subject_kind {kind!r} without a subject "
                f"name — a named kind must carry the name as written"
            )
        if kind == "generic" and subject is not None:
            raise ValueError(
                f"doc_subject emitted subject_kind 'generic' with subject "
                f"{subject!r} — generic means no specific entity"
            )
