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
    OUTCOMES_LOG,
    PKM_CONFIG,
    REACTIONS_LOG,
    TASKS_LEDGER,
    TASKS_STATE,
    UTILITY_ELICITATIONS,
    UTILITY_MODEL,
)
from life_agent.core.llm import (
    DEFAULT_ANSWER_MODEL,
    TEMPERATURE,
    LLMError,
    LLMResult,
    anthropic_complete,
    openai_complete,
    secret,
)
from life_agent.core.sources import SourceCard, render_sources_block

__all__ = [
    "DECISIONS_LOG",
    "DEFAULT_ANSWER_MODEL",
    "GTD_DB_PATH",
    "JARVIS_DB_PATH",
    "KB",
    "OUTCOMES_LOG",
    "PKM_CONFIG",
    "REACTIONS_LOG",
    "TASKS_LEDGER",
    "TASKS_STATE",
    "TEMPERATURE",
    "UTILITY_ELICITATIONS",
    "UTILITY_MODEL",
    "LLMError",
    "LLMResult",
    "SourceCard",
    "anthropic_complete",
    "openai_complete",
    "render_sources_block",
    "secret",
]
