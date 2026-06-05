"""Resolved, env-derived paths shared across life-agent.

``LIFE_AGENT_KB`` and ``PKM_CONFIG`` point at out-of-tree, machine-specific locations (the
knowledge base + the pkm catalogue config). Set them once per shell from ``.env``. No PII,
no secrets here — secrets come from gnome-keyring via :func:`life_agent.core.llm.secret`.
"""
from __future__ import annotations

import os
from pathlib import Path

KB = Path(os.environ.get("LIFE_AGENT_KB", str(Path.home() / ".life-agent/kb")))
PKM_CONFIG = Path(os.environ.get("PKM_CONFIG", "~/.config/life-agent/pkm.yaml")).expanduser()

# --- M2 email→GTD (the action faculty) ---
# The in-tree jarvis GTD store; defaults under the KB (outside the repo), matching
# jarvis.db's own default. The owner's Telegram id is NOT stored here — it's a
# personal id resolved at write time from JARVIS_USER_ID (env / gnome-keyring).
JARVIS_DB_PATH = Path(
    os.environ.get("JARVIS_DB_PATH", str(KB / "jarvis" / "jarvis.db"))
).expanduser()
# Process-once ledger of (message_id#index) keys already filed as tasks.
TASKS_LEDGER = KB / "tasks" / "seen-message-ids.jsonl"
