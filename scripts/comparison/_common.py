#!/usr/bin/env python3
"""_common.py — shared harness utilities for the Phase 0 vs Phase 1 comparison.

The generic infra (metered LLM calls, secret lookup, source-card rendering, the resolved
KB / PKM_CONFIG paths) now lives in :mod:`life_agent.core` and is re-exported here, so the
frozen comparison scripts keep their ``C.<name>`` call sites unchanged. What remains in this
file is *comparison-specific*: the pinned answerer/judge models, the citation-shape rule that
keeps the blind fair, and the fixture/snapshot loaders. No PII in this file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# Generic infra now lives in the installed life_agent package (see life-agent's pyproject).
from life_agent.core import (  # re-exported below for the frozen comparison call sites
    KB,
    PKM_CONFIG,
    TEMPERATURE,
    LLMResult,
    SourceCard,
    anthropic_complete,
    openai_complete,
    render_sources_block,
    secret,
)

__all__ = [  # the surface the comparison scripts reach via `import _common as C`
    "ANSWER_MODEL",
    "CITATION_INSTRUCTION",
    "COMPARISON_DIR",
    "JUDGE_MODEL",
    "JUDGE_N",
    "KB",
    "PKM_CONFIG",
    "TEMPERATURE",
    "Answer",
    "LLMResult",
    "SourceCard",
    "anthropic_complete",
    "judge_complete",
    "load_questions",
    "openai_complete",
    "render_sources_block",
    "scored_questions",
    "secret",
    "snapshot_paths",
]

# --- pinned snapshots (SPEC-comparison.md §4, §6) ------------------------- #
# The comparison's answerer is pinned here, owned separately from core.DEFAULT_ANSWER_MODEL
# (they coincide today; the eval pin is frozen for reproducibility while the production
# default is free to track the best model). The harness calls anthropic_complete with this
# value's literal as its default, so behaviour is unchanged.
ANSWER_MODEL = "claude-sonnet-4-6"
# Judge: cross-provider (different family from the answerer) is the requirement. Gemini was the
# nominal pin but its key has zero credits (429); OpenAI was the pre-approved alternate.
# Independence property preserved. The exact served snapshot is captured per-call into the run
# record.
JUDGE_MODEL = "gpt-5.1"
JUDGE_N = 3                          # N=3 modal per dimension

COMPARISON_DIR = KB / "eval" / "comparison"   # all run outputs (PII) land here


def judge_complete(system: str, user: str, **kw) -> LLMResult:
    """The blind judge (cross-provider). Indirection so the judge provider is a single pin."""
    kw.setdefault("model", JUDGE_MODEL)
    return openai_complete(system, user, **kw)


# --- fixtures + snapshot -------------------------------------------------- #
def load_questions() -> list[dict]:
    fixture = KB / "eval" / "questions_v1.jsonl"
    if not fixture.exists():
        raise SystemExit(f"frozen fixture not found: {fixture} (PII; lives in $LIFE_AGENT_KB)")
    return [json.loads(ln) for ln in fixture.read_text(encoding="utf-8").splitlines() if ln.strip()]


def scored_questions() -> list[dict]:
    """Frozen questions excluding the retired q-019 (SPEC §10)."""
    return [q for q in load_questions() if not q.get("retired")]


def snapshot_paths() -> set[str]:
    snap = KB / "eval" / "snapshot_S.json"
    if not snap.exists():
        raise SystemExit(f"pinned snapshot not found: {snap} (run pin_snapshot.py)")
    data = json.loads(snap.read_text(encoding="utf-8"))
    return {f["path"] for f in data["files"]}


# --- comparison answer record -------------------------------------------- #
@dataclass
class Answer:
    system: str                       # 'phase0' | 'phase1' — harness-only label
    question_id: str
    text: str                         # answer body with [n] citation markers
    sources: list[SourceCard] = field(default_factory=list)
    in_tokens: int = 0
    out_tokens: int = 0
    seconds: float = 0.0
    cache_hit: bool | None = None     # Phase 1 only


# --- citation-shape normalisation (SPEC §6) ------------------------------- #
CITATION_INSTRUCTION = (
    "Cite using bracketed source numbers like [1] or [2], referring ONLY to the numbered "
    "SOURCES provided below. Put the citation immediately after each fact it supports. If the "
    "answer is not in the SOURCES, say so plainly and name what would be needed — do NOT guess. "
    "Watch for identity confusion: the documents contain other people's IDs/policies too; assert "
    "a value only if it is the subject the question asks about. Be concise."
)
