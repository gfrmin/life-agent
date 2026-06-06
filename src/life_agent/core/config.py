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

# --- GTD (the agent's act layer) ---
# Append-only event ledger (Asserted/Disposed/Superseded/Amended) — THE source of truth for
# tasks, keyed on a content+grounding assertion identity (not message_id#index). The task list
# is a fold of it. See life_agent/tasks/events.py.
TASKS_LEDGER = KB / "tasks" / "events.jsonl"
# The GTD read-model: a materialised SQLite projection of fold(TASKS_LEDGER) — a rebuildable,
# derived view (NOT the truth; safe to delete and rebuild). The owner's Telegram id is NOT
# stored here — it's resolved at write time from JARVIS_USER_ID (env / gnome-keyring).
GTD_DB_PATH = Path(os.environ.get("GTD_DB_PATH", str(KB / "tasks" / "gtd.db"))).expanduser()
# The legacy pre-event-sourcing store. The migration reads it **read-only** (the new system
# never writes it), so it stays untouched as a natural pre-cutover snapshot. See
# scripts/migrate_jarvis_to_events.py.
JARVIS_DB_PATH = Path(
    os.environ.get("JARVIS_DB_PATH", str(KB / "jarvis" / "jarvis.db"))
).expanduser()
