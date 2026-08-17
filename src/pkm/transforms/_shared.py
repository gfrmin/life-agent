"""Shared transform substrate: the provider seam + pure helpers (SPEC §18).

§18.3 — the **provider seam**. ``make_model_client(model_identity)`` dispatches
on the declared ``provider`` field to a concrete client exposing
``complete(prompt, schema) -> ModelResponse``, constrained to the output schema:

- ``ollama`` — a local model via Ollama's native chat endpoint
  (``http://localhost:11434/api/chat``) with grammar-constrained decoding
  (``format: <schema>``); ``cost_usd = 0``. The default for ``action_items``.
- ``anthropic`` — Structured Outputs (``output_config``) over the Anthropic API,
  metered with per-MTok pricing.

The ``_strip_unsupported_for_api`` sanitiser and the Haiku pricing are duplicated
from ``entity_extraction`` deliberately: per ``CLAUDE.md`` ("premature abstraction
is worse than duplication") the landed ``entity_extraction`` transform — which has
live cached artifacts — is left untouched rather than refactored onto this seam.

§18.5 — the whitespace-normalised grounding predicate used by prose-quote
transforms (``action_items``) lives here as the contract helper.
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
import urllib.request
from typing import Any, Protocol

from pkm.policy import CostEstimate
from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration

# --- API-schema sanitiser (duplicated from entity_extraction; see module doc) --

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


def strip_unsupported_for_api(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *schema* safe to send to a constrained-decoding API.

    Removes JSON Schema keywords the providers' grammars don't support and adds
    ``additionalProperties: false`` to every ``object`` type. The canonical
    schema retains the full constraints for client-side ``jsonschema``
    validation in ``TransformProducer.produce``.
    """
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _UNSUPPORTED_KEYS:
            continue
        if key == "minItems" and isinstance(value, int) and value > 1:
            continue
        if isinstance(value, dict):
            out[key] = strip_unsupported_for_api(value)
        elif isinstance(value, list):
            out[key] = [
                strip_unsupported_for_api(item)
                if isinstance(item, dict) else item
                for item in value
            ]
        else:
            out[key] = value

    if out.get("type") == "object" and "additionalProperties" not in out:
        out["additionalProperties"] = False

    return out


# --- whitespace-normalised grounding (SPEC §18.5) -----------------------------


def normalise_ws(text: str) -> str:
    """Collapse runs of whitespace to a single space and strip the ends.

    The basis of §18.5 whitespace-normalised containment: a line-wrapped source
    (notably ``email``) renders a source newline as a space in the model's copy,
    so an exact substring check false-rejects faithful quotes.
    """
    return re.sub(r"\s+", " ", text).strip()


def quote_is_grounded(quote: str, source_text: str) -> bool:
    """True iff *quote* appears in *source_text* under whitespace normalisation.

    Proves the quoted words appear contiguously and in order in the source while
    tolerating line-wrap differences. An empty quote is never grounded.
    """
    nq = normalise_ws(quote)
    return bool(nq) and nq in normalise_ws(source_text)


# --- pricing ------------------------------------------------------------------

_HAIKU_INPUT_PRICE_PER_MTOK = 0.80
_HAIKU_OUTPUT_PRICE_PER_MTOK = 4.00
_CHARS_PER_TOKEN = 4


def _anthropic_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * _HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000
        + output_tokens * _HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    )


def estimate_cost(
    declaration: TransformDeclaration,
    input_sizes: list[int],
) -> CostEstimate:
    """Provider-aware cost estimate (SPEC §18.3).

    ``ollama`` is local and free → zero. ``anthropic`` is estimated from
    character counts at Haiku pricing (deliberately conservative). Used by
    ``transform_run`` to drive the cost gate before any model call.
    """
    n = len(input_sizes)
    if declaration.model_identity.get("provider") == "ollama":
        return CostEstimate(total_usd=0.0, per_source_usd=0.0, source_count=n)

    prompt_tokens = len(declaration.prompt_text) // _CHARS_PER_TOKEN
    max_output = declaration.model_identity.get(
        "inference_params", {},
    ).get("max_tokens", 4096)

    total = 0.0
    for size in input_sizes:
        input_toks = prompt_tokens + size // _CHARS_PER_TOKEN
        total += _anthropic_cost(input_toks, max_output)

    per_source = total / n if n else 0.0
    return CostEstimate(
        total_usd=total, per_source_usd=per_source, source_count=n,
    )


# --- the provider seam (SPEC §18.3) -------------------------------------------

# Engine identity for the Ollama call path: there is no client SDK to read a
# version from, and temperature-0 is not bitwise-deterministic, so we pin a
# constant (the cache-key stability comes from the pinned model tag in
# model_identity). Bump this only on a breaking change to the call format.
_OLLAMA_ENGINE_VERSION = "ollama-chat-v1"
_OLLAMA_TIMEOUT_S = 180


class ModelClient(Protocol):
    """A constrained-decoding chat completion over one backend."""

    engine_version: str

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        ...


class OllamaClient:
    """Local model via Ollama's native chat endpoint (cost 0)."""

    def __init__(
        self,
        model: str,
        inference_params: dict[str, Any],
        *,
        url: str | None = None,
    ) -> None:
        self._model = model
        self._params = inference_params
        base = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self._url = base.rstrip("/")
        self.engine_version = _OLLAMA_ENGINE_VERSION

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": {"temperature": self._params.get("temperature", 0.0)},
        }
        endpoint = f"{self._url}/api/chat"  # PII-OK: HTTP endpoint, not a fs path
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=_OLLAMA_TIMEOUT_S) as resp:
            out = json.loads(resp.read())
        latency_ms = int((time.monotonic() - t0) * 1000)
        return ModelResponse(
            raw_text=out["message"]["content"],
            input_tokens=int(out.get("prompt_eval_count", 0)),
            output_tokens=int(out.get("eval_count", 0)),
            latency_ms=latency_ms,
            cost_usd=0.0,
        )


def _strict_objects(schema: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy ``schema`` with ``additionalProperties: false`` on every ``object``
    node that does not set it. The Anthropic Structured Outputs API *requires* closed
    objects; declarations authored for grammar-constrained backends omit the field.
    Wire-dialect adaptation only: the DECLARED schema stays the cache-key identity
    (``output_schema_hash`` hashes what was authored), and closing objects is strictly
    tighter than what every declaration already intends."""
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            out = {k: walk(v) for k, v in node.items()}
            if out.get("type") == "object" and "additionalProperties" not in out:
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    strict: dict[str, Any] = walk(schema)
    return strict


class AnthropicClient:
    """Cloud model via the Anthropic API with Structured Outputs (metered)."""

    def __init__(
        self,
        model: str,
        inference_params: dict[str, Any],
        *,
        client: Any | None = None,
    ) -> None:
        import anthropic

        self._model = model
        self._params = inference_params
        self._client = client or anthropic.Anthropic()
        self.engine_version = anthropic.__version__

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        t0 = time.monotonic()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._params.get("max_tokens", 4096),
            temperature=self._params.get("temperature", 0.0),
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": _strict_objects(schema)}},
        )
        latency_ms = int((time.monotonic() - t0) * 1000)
        raw_text: str = response.content[0].text  # type: ignore[union-attr]
        input_tokens = int(response.usage.input_tokens)
        output_tokens = int(response.usage.output_tokens)
        return ModelResponse(
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_usd=_anthropic_cost(input_tokens, output_tokens),
        )


def make_model_client(
    model_identity: dict[str, Any],
    *,
    anthropic_client: Any | None = None,
) -> ModelClient:
    """Dispatch on ``model_identity['provider']`` (SPEC §18.3).

    Explicit two-branch lookup; raises on an unknown provider rather than
    guessing. ``anthropic_client`` is a test seam for the cloud path.
    """
    provider = model_identity.get("provider")
    model = model_identity["model"]
    params = model_identity.get("inference_params", {})
    if provider == "ollama":
        return OllamaClient(model, params)
    if provider == "anthropic":
        return AnthropicClient(model, params, client=anthropic_client)
    raise ValueError(
        f"unknown transform provider: {provider!r} (known: 'ollama', 'anthropic')"
    )


def make_producer(declaration: TransformDeclaration) -> Any:
    """Dispatch on ``declaration.producer_class`` (SPEC §18.2).

    An explicit, closed lookup over a declared field — the bounded exception to
    §12 (no plugin discovery, no ``importlib`` of arbitrary paths). Adding a
    transform extends this table by one entry.
    """
    # Imported lazily to avoid an import cycle (the producers import this module).
    from pkm.transforms.action_items import ActionItemsProducer
    from pkm.transforms.doc_date import DocDateProducer
    from pkm.transforms.doc_date_email import DocDateEmailProducer
    from pkm.transforms.doc_subject import DocSubjectProducer
    from pkm.transforms.email_triage import EmailTriageProducer
    from pkm.transforms.entity_extraction import EntityExtractionProducer

    table = {
        "pkm.transforms.entity_extraction.EntityExtractionProducer":
            EntityExtractionProducer,
        "pkm.transforms.action_items.ActionItemsProducer":
            ActionItemsProducer,
        "pkm.transforms.email_triage.EmailTriageProducer":
            EmailTriageProducer,
        "pkm.transforms.doc_date.DocDateProducer":
            DocDateProducer,
        "pkm.transforms.doc_date_email.DocDateEmailProducer":
            DocDateEmailProducer,
        "pkm.transforms.doc_subject.DocSubjectProducer":
            DocSubjectProducer,
    }
    cls = table.get(declaration.producer_class)
    if cls is None:
        raise ValueError(
            f"unknown producer_class {declaration.producer_class!r} "
            f"(known: {sorted(table)})"
        )
    return cls(declaration=declaration)


def derive_api_schema(output_schema: dict[str, Any]) -> dict[str, Any]:
    """Build the model-facing schema from the canonical output schema.

    Drops ``format_version`` (injected post-parse, not the model's job) and
    strips keywords the providers' grammars reject. The full canonical schema —
    including the ``format_version`` const — is still enforced client-side by
    ``TransformProducer.produce``'s ``jsonschema.validate``.
    """
    schema = copy.deepcopy(output_schema)
    props = schema.get("properties")
    if isinstance(props, dict):
        props.pop("format_version", None)
    if isinstance(schema.get("required"), list):
        schema["required"] = [
            r for r in schema["required"] if r != "format_version"
        ]
    return strip_unsupported_for_api(schema)
