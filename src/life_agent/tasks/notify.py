"""Optional outbound Telegram nudge after filing tasks (M2).

Best-effort: if no ``TELEGRAM_TOKEN`` is available (env or gnome-keyring) the
notify is silently skipped — the task filing itself is the source of truth. Uses
the same chat id as the GTD bot (the owner's Telegram user id).
"""

from __future__ import annotations

import json
import logging
import urllib.request

import life_agent.core as C

logger = logging.getLogger(__name__)


def maybe_notify(text: str, *, chat_id: int) -> bool:
    """Send *text* to *chat_id* on Telegram. Returns False (no-op) if unconfigured."""
    try:
        token = C.secret("TELEGRAM_TOKEN")
    except SystemExit:
        return False  # no token in env or keyring — skip quietly
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:  # network hiccup shouldn't fail the run
        logger.warning("telegram notify failed: %s", e)
        return False
