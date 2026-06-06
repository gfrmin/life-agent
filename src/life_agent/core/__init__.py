"""life_agent.core — shared infrastructure for the memory layer.

Metered LLM calls, secret lookup, env-derived config paths, and source-card rendering.
This is the substrate the retrieval/synthesis (memory) path is built on; it carries no
eval-harness or agent-loop concerns.
"""
from __future__ import annotations

from life_agent.core.config import GTD_DB_PATH, JARVIS_DB_PATH, KB, PKM_CONFIG, TASKS_LEDGER
from life_agent.core.llm import (
    DEFAULT_ANSWER_MODEL,
    TEMPERATURE,
    LLMResult,
    anthropic_complete,
    openai_complete,
    secret,
)
from life_agent.core.sources import SourceCard, render_sources_block

__all__ = [
    "DEFAULT_ANSWER_MODEL",
    "GTD_DB_PATH",
    "JARVIS_DB_PATH",
    "KB",
    "PKM_CONFIG",
    "TASKS_LEDGER",
    "TEMPERATURE",
    "LLMResult",
    "SourceCard",
    "anthropic_complete",
    "openai_complete",
    "render_sources_block",
    "secret",
]
