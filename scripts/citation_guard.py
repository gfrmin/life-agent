"""citation_guard.py — re-export shim over :mod:`life_agent.core.citation`.

The deterministic citation audit moved into core (slice 3 — the narrative family
scores its parsed claims with the same instrument). This shim keeps every existing
script/test import working; the implementation lives in one place.
"""
from __future__ import annotations

from life_agent.core.citation import (
    CitationAudit,
    audit,
    extract_citations,
    value_spans,
)

__all__ = ["CitationAudit", "audit", "extract_citations", "value_spans"]
