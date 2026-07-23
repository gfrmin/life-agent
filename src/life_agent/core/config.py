"""Resolved, env-derived paths shared across life-agent.

``LIFE_AGENT_KB`` and ``PKM_CONFIG`` point at out-of-tree, machine-specific locations (the
knowledge base + the pkm catalogue config). Set them once per shell from ``.env``. No PII,
no secrets here — secrets come from gnome-keyring via :func:`life_agent.core.llm.secret`.
"""
from __future__ import annotations

import os
import shlex
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

# --- Trips (the itinerary faculty) ---
# Append-only event ledger (Observed/Superseded/Cancelled/Amended) — THE source of truth
# for reservations, keyed on a content-derived reservation identity (not vendor eventId).
# The timeline is a fold of it. See life_agent/trips/events.py.
TRIPS_LEDGER = Path(
    os.environ.get("TRIPS_LEDGER", str(KB / "trips" / "events.jsonl"))
).expanduser()
# The trips read-model: a materialised SQLite projection of fold(TRIPS_LEDGER) — rebuildable,
# derived (NOT truth; safe to delete and rebuild). No PII: reservation content lives under KB.
TRIPS_DB_PATH = Path(os.environ.get("TRIPS_DB_PATH", str(KB / "trips" / "trips.db"))).expanduser()
# The kitinerary extractor binary — an installed system tool wrapped as a producer (the
# extraction seam). Default is the KF6 install path; override per-machine via the env var.
KITINERARY_EXTRACTOR = os.environ.get("KITINERARY_EXTRACTOR", "/usr/lib/kf6/kitinerary-extractor")

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
# The reaction log (foundations §4.4 reaction loop): owner verdicts on the agent's
# decisions, joined to DECISIONS_LOG by decision_id. The calibration leg's third
# append-only log; the utility posterior folds the clean abstain-verdicts from it.
REACTIONS_LOG = KB / "calibration" / "reactions.jsonl"
# The Claude verdict log (owner-authorized 2026-07-22): deliberative verdicts issued
# in-session on the owner's behalf, overrulable by any owner reaction on the same
# decision_id (core/claude_verdicts.py). Joins DECISIONS_LOG by decision_id; feeds the
# membrane's verdict evidence ONLY — never the utility posterior (P(U) stays
# owner-preference-only by construction).
CLAUDE_VERDICTS_LOG = KB / "calibration" / "claude_verdicts.jsonl"
# The gather-outcome log (ask-as-connection §4 caveat 2): one row per enacted grow
# actuator — the structure-observe stream the daemon's gather structure-BMA warm-seeds
# from (core/gather_outcomes.py). The calibration leg's fourth append-only log.
GATHER_OUTCOMES_LOG = KB / "calibration" / "gather_outcomes.jsonl"

# --- The utility posterior (foundations §4.4 — utility as inference) ---
# Gauge pins + grid priors (owner-editable; schema example in
# config/utility-model.example.yaml) and the append-only elicitation evidence
# (statements condition the posterior — evidence, never definition). Personal data.
UTILITY_MODEL = KB / "utility" / "model.yaml"
UTILITY_ELICITATIONS = KB / "utility" / "elicitations.jsonl"

# --- Membrane shadow (membrane-shadow feature, Task 5) ---
# The shadow supervisor (life_agent.membrane.shadow.MembraneShadow) runs the frozen
# proplang-host decider beside the production bridge, off the SAME live traffic,
# never on the decision path itself. Its env-name constants live here (not in
# life_agent.membrane.client, which independently defines the identical two names for
# its own from_env() — core never imports the membrane package, so the two are
# deliberately duplicated, the same choice JARVIS_USER_ID already makes across
# reach/ modules). Presence of LIFE_AGENT_MEMBRANE_COMMAND is the enable/disable switch:
# its absence is the default, so a machine with no membrane engine configured sees ZERO
# behaviour change on the bridge.
MEMBRANE_COMMAND_ENV = "LIFE_AGENT_MEMBRANE_COMMAND"
MEMBRANE_UTILITY_ENV = "LIFE_AGENT_MEMBRANE_UTILITY"
MEMBRANE_READ_TIMEOUT_ENV = "LIFE_AGENT_MEMBRANE_READ_TIMEOUT"
MEMBRANE_WARM_VECTORS_ENV = "LIFE_AGENT_MEMBRANE_WARM_VECTORS"
MEMBRANE_LIVE_ENV = "LIFE_AGENT_MEMBRANE_LIVE"
MEMBRANE_CAT_ENV = "LIFE_AGENT_MEMBRANE_CAT"

MEMBRANE_DEFAULT_UTILITY_FORMS = "said@1"
MEMBRANE_DEFAULT_READ_TIMEOUT_S = 300.0


def membrane_dir() -> Path:
    """The shadow's own subtree — currently just its append-only log."""
    return KB / "membrane"


def membrane_shadow_log() -> Path:
    """The shadow's append-only record (boot/respawn/decide/evidence rows) — see
    life_agent.membrane.shadow's module docstring."""
    return membrane_dir() / "shadow.jsonl"


def membrane_command() -> list[str] | None:
    """The proplang-host launch argv, shell-split — ``None`` when unset, which is
    the shadow's enable/disable switch (the bridge constructs a MembraneShadow iff this
    is not None)."""
    raw = os.environ.get(MEMBRANE_COMMAND_ENV)
    return shlex.split(raw) if raw else None


def membrane_utility_forms() -> tuple[str, ...]:
    """Every declared utility form to run side by side, comma-separated
    (default: just ``said@1``, the re-derived wire's one form) —
    life_agent.membrane.world.UTILITY_FORMS is the declared
    vocabulary, and ``ShadowConfig.__post_init__`` validates membership against it, raising
    on an unknown form before anything is spawned (the bridge then serves with the membrane
    disabled). This function itself only splits the env var: it never validates, so a typo
    surfaces at construction, named, rather than here."""
    raw = os.environ.get(MEMBRANE_UTILITY_ENV, MEMBRANE_DEFAULT_UTILITY_FORMS)
    return tuple(f.strip() for f in raw.split(",") if f.strip())


def membrane_read_timeout_s() -> float:
    return float(os.environ.get(MEMBRANE_READ_TIMEOUT_ENV, MEMBRANE_DEFAULT_READ_TIMEOUT_S))


def membrane_live() -> bool:
    """M3 — the coarse menu live: ``"1"`` re-points the executor read-path's coarse act
    at the proplang engine (the seam's ``DaemonDecide.live`` consult through the
    bridge's ``/decide-live``). Anything else — including absence, the default — is
    byte-for-byte the credence daemon's decision. Rollback is unsetting this."""
    return os.environ.get(MEMBRANE_LIVE_ENV) == "1"


def membrane_categorical() -> bool:
    """E1 stage 1 — the categorical shadow mirror: ``"1"`` runs the obs_arity = K+1
    world (life_agent.membrane.categorical, one fresh engine session per decide tick)
    beside the binary form, SHADOW-ONLY — it writes ``kind: "cat"`` rows and never
    touches the decision path. Anything else — including absence, the default — is
    byte-inert. Rollback is unsetting this."""
    return os.environ.get(MEMBRANE_CAT_ENV) == "1"


def membrane_warm_vectors_dir() -> Path | None:
    """A fair-fight run directory to seed outcome replay from (boot_snapshot's optional
    third argument) — ``None`` when unset (no warm outcomes, verdict replay only)."""
    raw = os.environ.get(MEMBRANE_WARM_VECTORS_ENV)
    return Path(raw).expanduser() if raw else None
