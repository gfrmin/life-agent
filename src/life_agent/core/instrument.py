"""The cached-instrument model client — one constructor for route/extract/subject/intent.

Local Ollama was deprecated 2026-08-17 (owner directive; bayesian-foundations §14
registration): the four cached ask instruments run on the same Anthropic seam the pkm
``entity_extraction`` transform already uses (``make_model_client`` → Structured
Outputs). The identity that keys their caches is owned by
:func:`life_agent.core.derivations.instrument_identity` — this module only constructs
the client for a cache MISS; a warm replay never touches it.

The API key resolves env-then-keyring (:func:`life_agent.core.llm.secret`), so the
bridge and jarvis processes need no exported environment.
"""
from __future__ import annotations

from typing import Any

from life_agent.core import derivations as D

# The instruments' model — the repo's dated haiku pin (core/expansion.py precedent).
# Changing it is a deliberate instrument change: it re-keys every verdict cache and
# must be disclosed in the §14 ledger before a gate reading.
INSTRUMENT_MODEL = "claude-haiku-4-5-20251001"


def instrument_client(model: str = INSTRUMENT_MODEL) -> Any:
    """A schema-constrained client for the cached instruments (cache-miss path only)."""
    import anthropic

    from life_agent.core import llm
    from pkm.transforms._shared import make_model_client

    return make_model_client(
        D.instrument_identity(model),
        anthropic_client=anthropic.Anthropic(api_key=llm.secret("ANTHROPIC_API_KEY")),
    )
