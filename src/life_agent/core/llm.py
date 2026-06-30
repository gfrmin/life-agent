"""Metered LLM calls + secret lookup — the generic synthesis infra.

:func:`secret` reads gnome-keyring (never ``.env``); the completion helpers return an
:class:`LLMResult` carrying token counts + latency for cost accounting. This module is
deliberately free of eval-harness concerns (the blind-judge pin, citation rules, and
fixture loaders stay in ``scripts/comparison/_common.py``) — it is the substrate the
production memory path and any future faculty build on.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# Default synthesis model for production answers. Owned separately from the comparison
# harness's pinned ANSWER_MODEL — they coincide today but are free to diverge (the eval
# pin is frozen for reproducibility; the production default tracks the best model).
DEFAULT_ANSWER_MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.0


class LLMError(RuntimeError):
    """A cloud-completion failure (HTTP error from the provider). A normal, CATCHABLE
    exception — never ``SystemExit`` — so a long-lived service (the capability bridge) returns
    500 and stays up on a transient provider error (rate limit / over-quota) instead of the
    ``BaseException`` escaping ``except Exception`` and killing the process. Still fails loudly:
    uncaught, it prints a full traceback with the provider's message."""


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


@dataclass
class LLMResult:
    text: str
    in_tokens: int
    out_tokens: int
    seconds: float
    served_model: str = ""   # exact snapshot the provider served (reproducibility record)


def anthropic_complete(system: str, user: str, *, model: str = DEFAULT_ANSWER_MODEL,
                       max_tokens: int = 1024,
                       temperature: float | None = TEMPERATURE) -> LLMResult:
    """One Anthropic completion. ``temperature=None`` OMITS the field — required for models
    that reject it (Opus 4.8). Records the provider-served model snapshot for audit (an alias
    that silently rolls is then visible against the dated snapshot the cache keyed on)."""
    payload: dict[str, Any] = {
        "model": model, "max_tokens": max_tokens,
        "system": system, "messages": [{"role": "user", "content": user}],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-api-key": secret("ANTHROPIC_API_KEY"),
                 "anthropic-version": "2023-06-01"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise LLMError(f"Anthropic API {e.code}: {e.read().decode(errors='replace')}") from e
    dt = time.monotonic() - t0
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage", {})
    return LLMResult(text, u.get("input_tokens", 0), u.get("output_tokens", 0), dt,
                     served_model=str(data.get("model", model)))


def openai_complete(system: str, user: str, *, model: str,
                    max_tokens: int = 1024) -> LLMResult:
    """A cross-provider completion (used by the comparison harness's blind judge). Newer
    OpenAI models accept only the default temperature, so it is omitted."""
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
        raise LLMError(f"OpenAI API {e.code}: {e.read().decode(errors='replace')}") from e
    dt = time.monotonic() - t0
    msg = (data.get("choices") or [{}])[0].get("message", {})
    text = msg.get("content", "") or ""
    u = data.get("usage", {})
    return LLMResult(text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), dt,
                     served_model=data.get("model", model))
