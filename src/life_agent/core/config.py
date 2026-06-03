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
