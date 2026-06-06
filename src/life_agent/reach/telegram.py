"""Telegram transport — the dumb pipe. Poll updates, send messages. Nothing else.

Knows only the Telegram Bot API: it has no idea what a task or a GTD list is. The token is
read lazily (env or gnome-keyring via ``life_agent.core.secret``) so importing this module is
side-effect-free and testable.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from life_agent.core import secret

_POLL_TIMEOUT = 30


def _api() -> str:
    return f"https://api.telegram.org/bot{secret('TELEGRAM_TOKEN')}"


def telegram_request(method: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_api()}/{method}"
    data = json.dumps(params or {}).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=_POLL_TIMEOUT + 10) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")
    return result.get("result")


def send_message(chat_id: int, text: str) -> None:
    telegram_request("sendMessage", {"chat_id": chat_id, "text": text})


def send_chat_action(chat_id: int, action: str = "typing") -> None:
    telegram_request("sendChatAction", {"chat_id": chat_id, "action": action})


def poll_updates(offset: int, timeout: int = _POLL_TIMEOUT) -> list[dict[str, Any]]:
    updates = telegram_request(
        "getUpdates",
        {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
    )
    return updates or []
