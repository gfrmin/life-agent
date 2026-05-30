#!/usr/bin/env python3
"""_common.py — shared harness utilities for the Phase 0 vs Phase 1 comparison.

Pinned models (SPEC-comparison.md §4, §6), secret lookup, metered LLM calls for both the
answerer (Anthropic Sonnet) and the cross-provider judge (Google Gemini), fixture/snapshot
loaders, and the citation-shape normalisation that both answer paths share so the blind can't
leak the system from citation form. No PII in this file.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# --- pinned snapshots (SPEC §4, §6) --------------------------------------- #
ANSWER_MODEL = "claude-sonnet-4-6"   # both Phase 0 and Phase 1 answer with this
# Judge: cross-provider (different family from the answerer) is the requirement. Gemini was the
# nominal pin but its key has zero credits (429); OpenAI was the pre-approved alternate. Independence
# property preserved. The exact served snapshot is captured per-call into the run record.
JUDGE_MODEL = "gpt-5.1"
TEMPERATURE = 0.0
JUDGE_N = 3                          # N=3 modal per dimension

KB = Path(os.environ.get("LIFE_AGENT_KB", str(Path.home() / "yo/life-agent-kb")))
COMPARISON_DIR = KB / "eval" / "comparison"   # all run outputs (PII) land here


# --- secrets -------------------------------------------------------------- #
def secret(name: str) -> str:
    key = os.environ.get(name)
    if key:
        return key
    out = subprocess.run(
        ["secret-tool", "lookup", "service", "env", "key", name],
        capture_output=True, text=True, check=False,
    )
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip()
    raise SystemExit(f"{name} not found in env or gnome-keyring")


# --- metered LLM calls ---------------------------------------------------- #
@dataclass
class LLMResult:
    text: str
    in_tokens: int
    out_tokens: int
    seconds: float
    served_model: str = ""   # exact snapshot the provider served (for the reproducibility record)


def anthropic_complete(system: str, user: str, *, model: str = ANSWER_MODEL,
                       max_tokens: int = 1024) -> LLMResult:
    body = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": TEMPERATURE,
        "system": system, "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": secret("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Anthropic API {e.code}: {e.read().decode(errors='replace')}")
    dt = time.monotonic() - t0
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage", {})
    return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0), dt)


def openai_complete(system: str, user: str, *, model: str = JUDGE_MODEL,
                    max_tokens: int = 1024) -> LLMResult:
    """The cross-provider judge call. Newer OpenAI models accept only the default temperature,
    so it is omitted (judge determinism is approximated by N=3 modal, SPEC §6)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_completion_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {secret('OPENAI_API_KEY')}"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenAI API {e.code}: {e.read().decode(errors='replace')}")
    dt = time.monotonic() - t0
    msg = (data.get("choices") or [{}])[0].get("message", {})
    text = msg.get("content", "") or ""
    u = data.get("usage", {})
    return LLMResult(text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), dt,
                     served_model=data.get("model", model))


def judge_complete(system: str, user: str, **kw) -> LLMResult:
    """The blind judge (cross-provider). Indirection so the judge provider is a single pin."""
    return openai_complete(system, user, **kw)


# --- fixtures + snapshot -------------------------------------------------- #
def load_questions() -> list[dict]:
    fixture = KB / "eval" / "questions_v1.jsonl"
    if not fixture.exists():
        raise SystemExit(f"frozen fixture not found: {fixture} (PII; lives in $LIFE_AGENT_KB)")
    return [json.loads(l) for l in fixture.read_text(encoding="utf-8").splitlines() if l.strip()]


def scored_questions() -> list[dict]:
    """Frozen questions excluding the retired q-019 (SPEC §10)."""
    return [q for q in load_questions() if not q.get("retired")]


def snapshot_paths() -> set[str]:
    snap = KB / "eval" / "snapshot_S.json"
    if not snap.exists():
        raise SystemExit(f"pinned snapshot not found: {snap} (run pin_snapshot.py)")
    data = json.loads(snap.read_text(encoding="utf-8"))
    return {f["path"] for f in data["files"]}


# --- citation-shape normalisation (SPEC §6) ------------------------------- #
@dataclass
class SourceCard:
    """One numbered source shown to a system and (later) to the judge in a SHARED neutral
    form [n], so citation shape cannot reveal which system produced the answer."""
    n: int
    text: str            # the actual cited text (chunk for Phase 1; wiki page for Phase 0)
    origin: str = ""     # provenance kept for the harness only; NEVER shown to the blind judge


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


CITATION_INSTRUCTION = (
    "Cite using bracketed source numbers like [1] or [2], referring ONLY to the numbered "
    "SOURCES provided below. Put the citation immediately after each fact it supports. If the "
    "answer is not in the SOURCES, say so plainly and name what would be needed — do NOT guess. "
    "Watch for identity confusion: the documents contain other people's IDs/policies too; assert "
    "a value only if it is the subject the question asks about. Be concise."
)


def render_sources_block(cards: list[SourceCard]) -> str:
    return "\n\n".join(f"[{c.n}] {c.text}" for c in cards)
