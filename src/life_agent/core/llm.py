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


# Bounded: against a LOCKED keyring (post-boot/resume under linger) secret-tool blocks
# forever on an unlock prompt no service can answer — a hung unit systemd reports as
# healthy. A bounded lookup exits loudly instead, so Restart=on-failure and the watchdog
# see a failed unit rather than nothing.
_SECRET_TOOL_TIMEOUT_S = 10.0


def secret(name: str) -> str:
    key = os.environ.get(name)
    if key:
        return key
    try:
        out = subprocess.run(
            ["secret-tool", "lookup", "service", "env", "key", name],
            capture_output=True, text=True, check=False, timeout=_SECRET_TOOL_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"secret-tool lookup for {name} timed out after {_SECRET_TOOL_TIMEOUT_S:.0f}s"
            " — the gnome-keyring is likely locked (boot/resume under linger);"
            f" unlock it or set {name} in the environment"
        ) from None
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
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    provider: str = ""       # "anthropic" | "openai"


# Module-global chokepoint mirroring scripts/ask.py's STAGES_LAST pattern: a caller resets
# the meter, makes calls, reads the snapshot. None means "not collecting" — cost metering is
# opt-in per call site, never a background cost to callers that don't ask for it.
_METER: list[LLMResult] | None = None


def reset_meter() -> None:
    """Start collecting every ``*_complete`` call's :class:`LLMResult` into the meter."""
    global _METER
    _METER = []


def meter_read() -> list[LLMResult]:
    """Return the collected results and stop collecting (chokepoint reset to inactive)."""
    global _METER
    collected = _METER or []
    _METER = None
    return collected


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
        raise SystemExit(f"Anthropic API {e.code}: {e.read().decode(errors='replace')}") from e
    dt = time.monotonic() - t0
    text = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    u = data.get("usage", {})
    result = LLMResult(
        text, u.get("input_tokens", 0), u.get("output_tokens", 0), dt,
        served_model=str(data.get("model", model)),
        cache_read_tokens=u.get("cache_read_input_tokens", 0),
        cache_write_tokens=u.get("cache_creation_input_tokens", 0),
        provider="anthropic",
    )
    if _METER is not None:
        _METER.append(result)
    return result


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
        raise SystemExit(f"OpenAI API {e.code}: {e.read().decode(errors='replace')}") from e
    dt = time.monotonic() - t0
    msg = (data.get("choices") or [{}])[0].get("message", {})
    text = msg.get("content", "") or ""
    u = data.get("usage", {})
    cached_tokens = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    result = LLMResult(
        text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), dt,
        served_model=data.get("model", model),
        cache_read_tokens=cached_tokens,
        cache_write_tokens=0,  # OpenAI charges no cache-write premium; nothing to record
        provider="openai",
    )
    if _METER is not None:
        _METER.append(result)
    return result
