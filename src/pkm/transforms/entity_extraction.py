"""Entity extraction transform producer (SPEC v0.2.0 §19-§20).

Concrete ``TransformProducer`` that sends extracted text through
Anthropic Haiku 4.5 for named-entity recognition.  Output conforms
to the ``entity_extraction_v1`` JSON schema (§19.3).

Uses Anthropic's Structured Outputs (``output_config``) to constrain
model output to a derived schema.  The canonical schema
(``schemas/entity_extraction_v1.json``) retains all constraints
for client-side ``jsonschema`` validation; the transmitted schema
has unsupported properties stripped by ``_strip_unsupported_for_api``.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from typing import Any

import anthropic

from pkm.policy import CostEstimate
from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration

logger = logging.getLogger(__name__)

_HAIKU_INPUT_PRICE_PER_MTOK = 0.80
_HAIKU_OUTPUT_PRICE_PER_MTOK = 4.00

_CHARS_PER_TOKEN = 4

_UNSUPPORTED_KEYS: frozenset[str] = frozenset({
    "$schema",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf",
    "minLength", "maxLength",
    "maxItems", "uniqueItems",
    "oneOf", "not",
    "if", "then", "else",
    "prefixItems",
})


def _strip_unsupported_for_api(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *schema* safe to send to Anthropic's API.

    Removes JSON Schema keywords the API doesn't support, and adds
    ``additionalProperties: false`` to every ``object`` type (required
    by the API).  The canonical schema retains the full constraints
    for client-side validation.
    """
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _UNSUPPORTED_KEYS:
            continue
        if key == "minItems" and isinstance(value, int) and value > 1:
            continue
        if isinstance(value, dict):
            out[key] = _strip_unsupported_for_api(value)
        elif isinstance(value, list):
            out[key] = [
                _strip_unsupported_for_api(item)
                if isinstance(item, dict) else item
                for item in value
            ]
        else:
            out[key] = value

    if out.get("type") == "object" and "additionalProperties" not in out:
        out["additionalProperties"] = False

    return out


def _compute_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * _HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000
        + output_tokens * _HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    )


def estimate_cost(
    declaration: TransformDeclaration,
    input_sizes: list[int],
) -> CostEstimate:
    """Estimate the total cost of running entity extraction.

    Token counts are approximated from character counts.  Output
    allowance uses ``max_tokens`` from the model identity.  The
    estimate is deliberately conservative (overestimates).
    """
    prompt_tokens = len(declaration.prompt_text) // _CHARS_PER_TOKEN
    max_output = declaration.model_identity.get(
        "inference_params", {},
    ).get("max_tokens", 4096)

    total = 0.0
    for size in input_sizes:
        input_toks = prompt_tokens + size // _CHARS_PER_TOKEN
        total += _compute_cost(input_toks, max_output)

    per_source = total / len(input_sizes) if input_sizes else 0.0
    return CostEstimate(
        total_usd=total,
        per_source_usd=per_source,
        source_count=len(input_sizes),
    )


_SPAN_SEARCH_WINDOW = 10


def _correct_span(
    text: str, entity_text: str, reported_start: int,
) -> tuple[int, int] | None:
    """Search for *entity_text* near *reported_start* and return corrected span.

    First searches within ``_SPAN_SEARCH_WINDOW`` characters of
    the reported position.  If that misses, falls back to a global
    ``str.find`` — LLMs frequently report wildly wrong offsets for
    structured or long documents while still producing correct entity
    text.  Returns ``None`` only when the text is absent entirely.
    """
    search_start = max(0, reported_start - _SPAN_SEARCH_WINDOW)
    search_end = min(
        len(text), reported_start + len(entity_text) + _SPAN_SEARCH_WINDOW,
    )
    window = text[search_start:search_end]
    idx = window.find(entity_text)
    if idx >= 0:
        corrected_start = search_start + idx
        return corrected_start, corrected_start + len(entity_text)

    global_idx = text.find(entity_text)
    if global_idx >= 0:
        return global_idx, global_idx + len(entity_text)

    return None


class EntityExtractionProducer(TransformProducer):
    """Named-entity extraction via Anthropic Haiku 4.5.

    Uses Structured Outputs (``output_config``) to constrain the
    model's response to the transmitted schema.  Client-side
    ``jsonschema`` validation against the canonical schema enforces
    constraints the API doesn't support (e.g. numeric ranges).
    """

    name = "entity_extraction"
    version = "0.4.0"

    def __init__(
        self,
        *,
        declaration: TransformDeclaration,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.model_identity: dict[str, Any] = declaration.model_identity
        self.prompt_name = declaration.prompt_name
        self.output_schema: dict[str, Any] = declaration.output_schema
        self.engine_version: str = anthropic.__version__
        self._prompt_template = declaration.prompt_text
        self._model = declaration.model_identity["model"]
        self._inference_params = declaration.model_identity.get(
            "inference_params", {},
        )
        self._client = client or anthropic.Anthropic()
        self._api_schema = _strip_unsupported_for_api(
            copy.deepcopy(declaration.output_schema),
        )

    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        text = input_content.decode("utf-8", errors="replace")
        return self._prompt_template.replace("{text}", text)

    def call_model(self, prompt: str) -> ModelResponse:
        t0 = time.monotonic()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._inference_params.get("max_tokens", 4096),
            temperature=self._inference_params.get("temperature", 0.0),
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": self._api_schema,
                },
            },
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        raw_text: str = response.content[0].text  # type: ignore[union-attr]
        input_tokens: int = response.usage.input_tokens
        output_tokens: int = response.usage.output_tokens
        cost_usd = _compute_cost(input_tokens, output_tokens)

        return ModelResponse(
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        return json.loads(raw_output)  # type: ignore[no-any-return]

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        """Strict span validation (SPEC §20.2).

        Every entity's span must resolve to the correct text in the
        source.  Near-miss spans are corrected via ``_correct_span``;
        any entity whose text cannot be located at all fails the
        entire source.  No partial outputs, no filtering.
        """
        text = input_content.decode("utf-8", errors="replace")
        text_len = len(text)

        for i, entity in enumerate(parsed.get("entities", [])):
            span = entity.get("span", {})
            start = span.get("start", 0)
            end = span.get("end", 0)
            expected = entity.get("text", "")

            span_ok = (
                0 <= start < end <= text_len
                and text[start:end] == expected
            )
            if span_ok:
                continue

            corrected = _correct_span(text, expected, start)
            if corrected is not None:
                logger.debug(
                    "entity[%d]: corrected span [%d:%d] -> [%d:%d] "
                    "for %r",
                    i, start, end, corrected[0], corrected[1], expected,
                )
                span["start"] = corrected[0]
                span["end"] = corrected[1]
                continue

            raise ValueError(
                f"entity[{i}]: unresolvable span for "
                f"{expected!r} (reported [{start}:{end}])"
            )
