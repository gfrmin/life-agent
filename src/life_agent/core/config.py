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
# The ledger's knowledge projection (tasks/knowledge.py): fold(TASKS_LEDGER) rendered as one
# markdown document at a stable declared path, ingested into pkm so the ask path retrieves GTD
# state like any source. Derived, stamped with the ledger head; safe to delete and re-render.
TASKS_STATE = KB / "tasks" / "state.md"
# The legacy pre-event-sourcing store. The migration reads it **read-only** (the new system
# never writes it), so it stays untouched as a natural pre-cutover snapshot. See
# scripts/migrate_jarvis_to_events.py.
JARVIS_DB_PATH = Path(
    os.environ.get("JARVIS_DB_PATH", str(KB / "jarvis" / "jarvis.db"))
).expanduser()

# --- Calibration (the Bayesian foundations' empirical leg) ---
# The outcomes log (bayesian-foundations §8): append-only third evidence stream — graded
# outcomes attributed to instrument identities. It cannot be backfilled, and its append
# order is the canonical replay order (the fold is order-defined, foundations §2). The
# claims it records are personal data, hence under $LIFE_AGENT_KB (PRINCIPLES §12).
OUTCOMES_LOG = KB / "calibration" / "outcomes.jsonl"
# The decision log (foundations §8): every EU decision's context — without it, owner
# reactions are not readable as choices. Append-only, order-defined, unbackfillable;
# no EU decision is ever made unlogged.
DECISIONS_LOG = KB / "calibration" / "decisions.jsonl"

# --- The utility posterior (foundations §4.4 — utility as inference) ---
# Gauge pins + grid priors (owner-editable; schema example in
# config/utility-model.example.yaml) and the append-only elicitation evidence
# (statements condition the posterior — evidence, never definition). Personal data.
UTILITY_MODEL = KB / "utility" / "model.yaml"
UTILITY_ELICITATIONS = KB / "utility" / "elicitations.jsonl"
