"""jarvis — the GTD task faculty (the "hands"), absorbed into the monorepo.

A small, single-user GTD task store (SQLite) with a Telegram bot (inbound NLU
via a local Ollama model) and a daily digest (outbound). Vendored from the
standalone ``gfrmin/jarvis-lite`` repo (now archived); history lives there.

``life_agent`` writes tasks by importing ``jarvis.db`` in-process — the seam is
a function call, not a cross-repo SQLite write or an MCP round-trip. (There is no
MCP server: a future cross-language spine can re-add one from git history.)
"""

from __future__ import annotations

from jarvis import db as db

__all__ = ["db"]
