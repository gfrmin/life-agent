"""Cost pricing table for :class:`life_agent.core.llm.LLMResult` — pure, no I/O.

Prices are USD per Mtok (million tokens), longest-prefix keyed so a provider's exact served
snapshot (e.g. a dated Anthropic string) still resolves to its family's price. Verified
2026-07-11 against the ``claude-api`` skill (Anthropic models, skill cache dated 2026-06-24)
and a live web search (OpenAI ``gpt-5.1``, raised 2026-07-02) — not hand-recalled. Anthropic's
cache read/write rates aren't in the skill's per-model table; they follow its documented
multipliers (cache read ~0.1x input, cache write at the default 5-minute TTL ~1.25x input).
Local Ollama models (``qwen*`` prefix) cost nothing — the request never leaves the box.

Bump :data:`PRICING_VERSION` whenever a price changes, so a cost total computed against an
older version can be told apart from one computed against the current table.
"""
from __future__ import annotations

from dataclasses import dataclass

from life_agent.core.llm import LLMResult

PRICING_VERSION = 1


@dataclass(frozen=True)
class ModelPrice:
    """USD per Mtok (million tokens) for one token kind each."""

    input: float
    output: float
    cache_read: float
    cache_write: float


PRICE_TABLE: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(input=5.00, output=25.00, cache_read=0.50, cache_write=6.25),
    "claude-sonnet-4-6": ModelPrice(input=3.00, output=15.00, cache_read=0.30, cache_write=3.75),
    "claude-haiku-4-5": ModelPrice(input=1.00, output=5.00, cache_read=0.10, cache_write=1.25),
    # gpt-5.1: OpenAI doesn't charge a write premium (first-use cache writes bill at the
    # ordinary input rate) — life_agent.core.llm.openai_complete never populates
    # cache_write_tokens for an OpenAI call, so this entry is a documented ceiling, not an
    # observed cost.
    "gpt-5.1": ModelPrice(input=1.25, output=10.00, cache_read=0.125, cache_write=1.25),
    # Local Ollama models never leave the box — free by construction, not a placeholder.
    "qwen": ModelPrice(0.0, 0.0, 0.0, 0.0),
}


def price_of(served_model: str) -> ModelPrice | None:
    """Longest :data:`PRICE_TABLE` prefix matching ``served_model``, else ``None``.

    ``None`` means the model is unpriced — the caller should record ``cost_status="partial"``
    rather than silently reporting a zero or fabricated cost.
    """
    match: str | None = None
    for prefix in PRICE_TABLE:
        if served_model.startswith(prefix) and (match is None or len(prefix) > len(match)):
            match = prefix
    return PRICE_TABLE[match] if match is not None else None


def cost_usd(r: LLMResult) -> float | None:
    """The USD cost of one :class:`LLMResult`, or ``None`` if its model is unpriced."""
    price = price_of(r.served_model)
    if price is None:
        return None
    return (
        r.in_tokens * price.input
        + r.out_tokens * price.output
        + r.cache_read_tokens * price.cache_read
        + r.cache_write_tokens * price.cache_write
    ) / 1_000_000
