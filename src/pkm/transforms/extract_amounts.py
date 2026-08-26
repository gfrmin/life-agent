"""extract_amounts — grounded typed line-item amounts (SPEC §18.14).

Consumes a text-extractor or email artifact (one declaration per input producer, all
dispatching here: the projection is a function of content, not of which extractor
produced it) and emits the document's salient labelled amounts as a bounded list of
typed line-items — the observation instrument of the consumer-side aggregate family.

The §18.5 grounding gate is the anti-hallucination guarantee, split by duty
(probe-calibrated): every ``amount_raw`` MUST ground verbatim (whitespace-normalised
containment) or the whole source fails — never cached as success; ``label_raw`` grounds
when present and is the quality discriminator (amount grounding alone survives OCR glyph
soup; label grounding does not). ``majority_unlabelled`` is derived here, never trusted
from the model — it flags the artifact for consumers to price, not to drop. An empty
``items`` is a determinate success; ``unreadable: true`` is the named indeterminate and
requires empty items.
"""

from __future__ import annotations

import json
import math
from typing import Any

from pkm.transform import ModelResponse, TransformProducer
from pkm.transform_declaration import TransformDeclaration
from pkm.transforms._shared import (
    ModelClient,
    derive_api_schema,
    make_model_client,
    quote_is_grounded,
)

_MAX_INPUT_CHARS = 20000
"""Head-cap on the text given to the model. Amounts spread through a financial document
(table rows, totals lines), so the cap is generous; it bounds per-call cost on the
Anthropic seam. Grounding is checked against the FULL source — an amount beyond the cap
cannot be emitted (the model never saw it), so the cap loses recall, never soundness.
Part of the producer's logic — changing it bumps ``version``."""


class ExtractAmountsProducer(TransformProducer):
    """Grounded typed line-item amount extraction (§18.14)."""

    name = "extract_amounts"
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
        # Inject format_version (§18.8 minimal-grammar pattern), apply the
        # currency_default fallback, and DERIVE majority_unlabelled — the flag is a
        # projection of the items, never the model's own claim.
        parsed: Any = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed.setdefault("format_version", 1)
            items = parsed.get("items")
            if isinstance(items, list):
                default = parsed.get("currency_default")
                for it in items:
                    if isinstance(it, dict) and it.get("currency") is None and default:
                        it["currency"] = default
                unlabelled = sum(1 for it in items
                                 if isinstance(it, dict)
                                 and it.get("label_raw") is None)
                parsed["majority_unlabelled"] = unlabelled * 2 > len(items)
        return parsed  # type: ignore[no-any-return]

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        """The §18.5 gate + §18.14 internal consistency. A violation cached forever is
        the §18.11 failure mode — fail loudly, never cache."""
        text = input_content.decode("utf-8", errors="replace")
        items = parsed.get("items", [])
        if parsed.get("unreadable") and items:
            raise ValueError(
                "unreadable: true requires items: [] — an unreadable document "
                "has no groundable amounts"
            )
        for i, item in enumerate(items):
            amount_raw = item.get("amount_raw", "")
            if not quote_is_grounded(amount_raw, text):
                raise ValueError(
                    f"items[{i}]: amount_raw not grounded in the source: "
                    f"{amount_raw!r}"
                )
            label_raw = item.get("label_raw")
            if label_raw is not None and not quote_is_grounded(label_raw, text):
                raise ValueError(
                    f"items[{i}]: label_raw not grounded in the source: "
                    f"{label_raw!r}"
                )
            if item.get("currency") is None:
                raise ValueError(
                    f"items[{i}]: no currency and no currency_default — an "
                    "amount without a currency is unusable"
                )
            amount = item.get("amount")
            if not isinstance(amount, (int, float)) or not math.isfinite(amount):
                raise ValueError(f"items[{i}]: amount {amount!r} is not finite")
