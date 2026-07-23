"""life_agent.core — shared infrastructure for the memory layer.

Metered LLM calls, secret lookup, env-derived config paths, and source-card rendering.
This is the substrate the retrieval/synthesis (memory) path is built on; it carries no
eval-harness or agent-loop concerns.
"""
from __future__ import annotations

from life_agent.core.config import (
    DECISIONS_LOG,
    GTD_DB_PATH,
    JARVIS_DB_PATH,
    KB,
    KITINERARY_EXTRACTOR,
    OUTCOMES_LOG,
    PKM_CONFIG,
    REACTIONS_LOG,
    TASKS_LEDGER,
    TASKS_STATE,
    TRIPS_DB_PATH,
    TRIPS_LEDGER,
    UTILITY_ELICITATIONS,
    UTILITY_MODEL,
)
from life_agent.core.llm import (
    DEFAULT_ANSWER_MODEL,
    TEMPERATURE,
    LLMResult,
    anthropic_complete,
    meter_read,
    openai_complete,
    reset_meter,
    secret,
)
from life_agent.core.pricing import PRICE_TABLE, PRICING_VERSION, ModelPrice, cost_usd, price_of
from life_agent.core.sources import SourceCard, render_sources_block

__all__ = [
    "DECISIONS_LOG",
    "DEFAULT_ANSWER_MODEL",
    "GTD_DB_PATH",
    "JARVIS_DB_PATH",
    "KB",
    "KITINERARY_EXTRACTOR",
    "OUTCOMES_LOG",
    "PKM_CONFIG",
    "PRICE_TABLE",
    "PRICING_VERSION",
    "REACTIONS_LOG",
    "TASKS_LEDGER",
    "TASKS_STATE",
    "TEMPERATURE",
    "TRIPS_DB_PATH",
    "TRIPS_LEDGER",
    "UTILITY_ELICITATIONS",
    "UTILITY_MODEL",
    "LLMResult",
    "ModelPrice",
    "SourceCard",
    "anthropic_complete",
    "cost_usd",
    "meter_read",
    "openai_complete",
    "price_of",
    "render_sources_block",
    "reset_meter",
    "secret",
]
