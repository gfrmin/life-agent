"""The action faculty's projector: cached ``action_items`` → GTD inbox (M2).

A thin, idempotent bridge from immutable pkm artifacts into the mutable jarvis GTD
store. It reads terminal ``action_items`` artifacts (each grounded + cited by its
email's Message-ID via the lineage walk in ``read.py``) and files every not-yet-open
assertion **once** into the inbox.

The bridge state is a real **event ledger** (``events.py``), not a marker file: the
current task set is ``fold(ledger)`` — open ``Asserted`` events minus ``Disposed`` /
``Superseded`` ones. Filing appends an ``Asserted`` event; a human clearing the task
in jarvis is captured (non-invasively, by reading jarvis) as a ``Disposed`` event. So
"already handled" is a property of the log, keyed on a content+grounding **assertion
identity** (``events.assertion_identity``) — not a positional ``message_id#index`` — which
is what makes re-derivation after a prompt bump dedup instead of duplicating.

It owns no SQLite or HTTP of its own beyond a read-only disposal scan: the write is
jarvis in-process (``db.add_task``) and the nudge is jarvis's ``digest.send_telegram``.
"Policy" is deliberately tiny — everything → inbox — and lives here inline; richer
routing, if ever wanted, belongs in *more transforms* (SPEC §18.7), not here.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import life_agent.core as C
from life_agent.tasks import events
from life_agent.tasks.read import EmailActions, read_action_items

logger = logging.getLogger(__name__)

# Which email_triage categories (SPEC §18.8) become GTD tasks. This is the
# deterministic actionability policy the SPEC says lives in the consumer, not
# pkm — tune it here without re-running the model. An email with no triage
# verdict (None) is included (fail-open): the gate only *excludes* emails
# explicitly classified non-actionable.
ACTIONABLE_CATEGORIES = frozenset({"personal_work", "transactional"})

# The claim type for an action item — the first component of its assertion identity.
_CLAIM_TYPE = "task"


def _is_actionable(category: str | None) -> bool:
    return category is None or category in ACTIONABLE_CATEGORIES


@dataclass(frozen=True)
class Candidate:
    """One action item staged for the GTD inbox."""

    action_phrase: str
    source_quote: str
    message_id: str
    citation: str
    identity: str
    valid_time: str | None = None
    list_name: str = "inbox"

    def task_text(self) -> str:
        """The text written to jarvis: the action plus its source citation."""
        return f"{self.action_phrase} {self.citation}"


def to_candidates(emails: list[EmailActions]) -> list[Candidate]:
    """Flatten emails → inbox candidates (everything→inbox, cited, identity-keyed).

    The Message-ID is the email's (falling back to a content-addressed cache key); it
    is provenance/citation, *not* identity. Identity is the content+grounding hash, so
    the same action re-extracted from the same quote dedups regardless of its position
    or how it was reworded across runs.
    """
    out: list[Candidate] = []
    for ea in emails:
        mid = ea.message_id or ea.email_cache_key or ea.action_items_cache_key
        valid_time = ea.email_produced_at.isoformat() if ea.email_produced_at else None
        for item in ea.items:
            phrase = str(item.get("action_phrase", "")).strip()
            if not phrase:
                continue
            quote = str(item.get("source_quote", "")).strip()
            out.append(
                Candidate(
                    action_phrase=phrase,
                    source_quote=quote,
                    message_id=mid,
                    citation=f"[src:email {mid}]",
                    identity=events.assertion_identity(_CLAIM_TYPE, quote, phrase),
                    valid_time=valid_time,
                )
            )
    return out


@dataclass(frozen=True)
class ProjectReport:
    """Outcome of a ``project_action_items`` run."""

    total_emails: int  # actionable emails with items (post triage gate)
    total_items: int
    fresh: list[Candidate]
    filed: int
    notified: bool
    nonactionable_filtered: int = 0  # emails with items dropped by triage (§18.8)
    disposed: int = 0  # assertions closed this run because the human cleared them


def _file_one(candidate: Candidate, *, user_id: int, db_path: Path) -> None:
    """File one candidate into the jarvis GTD inbox (in-process write).

    ``db.DB_PATH`` is a module var read by ``get_db()``; point it at the configured
    store. ``init_db`` is idempotent (CREATE TABLE IF NOT EXISTS), so a fresh store is
    handled.
    """
    from jarvis import db

    db.DB_PATH = Path(db_path)
    db.init_db()
    db.add_task(user_id, candidate.task_text(), "inbox")


def _active_task_texts(db_path: Path, user_id: int) -> set[str]:
    """The texts of the user's *active* (not completed) jarvis tasks.

    Read-only — never mutates jarvis, never creates the db. Used to detect disposal:
    a filed assertion whose text is no longer here was deleted or completed.
    """
    if not Path(db_path).exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT text FROM tasks WHERE user_id = ? AND completed_at IS NULL", (user_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        return set()  # tasks table not created yet
    finally:
        conn.close()
    return {r[0] for r in rows}


def _capture_dispositions(
    log_events: list[events.Event], *, db_path: Path, user_id: int
) -> list[events.Event]:
    """``Disposed`` events for open assertions the human has cleared in jarvis.

    Non-invasive: the bot keeps mutating jarvis directly; we reconcile by reading it.
    An open assertion whose ``task_text`` is no longer in the active set was deleted or
    completed → a ``Disposed{reason: "cleared"}`` compensating entry. Distinguishing
    done-vs-wrong needs a prompt at disposal time (the bot) and is deferred — until
    then disposal is captured but its *reason* is coarse.
    """
    open_assertions = events.fold(log_events)
    if not open_assertions:
        return []
    active = _active_task_texts(db_path, user_id)
    return [
        events.disposed(identity, reason="cleared")
        for identity, oa in open_assertions.items()
        if (text := oa.payload.get("task_text")) and text not in active
    ]


def _notify(text: str, *, chat_id: int) -> bool:
    """Best-effort Telegram nudge, reusing jarvis's sender. False if unconfigured.

    jarvis's ``send_telegram`` reads ``TELEGRAM_TOKEN`` from the environment; we seed it
    from ``C.secret`` (env *or* gnome-keyring) so an ad-hoc run works without
    ``load_secrets_from_keyring``. Never raises — a notify failure must not fail the
    filing, which is the source of truth.
    """
    from jarvis.digest import send_telegram

    try:
        os.environ.setdefault("TELEGRAM_TOKEN", C.secret("TELEGRAM_TOKEN"))
    except SystemExit:
        return False  # no token in env or keyring — skip quietly
    try:
        send_telegram(chat_id, text)
        return True
    except Exception as e:  # network hiccup shouldn't fail the run
        logger.warning("telegram notify failed: %s", e)
        return False


def project_action_items(
    root: Path,
    *,
    db_path: Path,
    user_id: int,
    ledger: Path,
    commit: bool = True,
    notify: bool = True,
    limit: int | None = None,
    since: datetime | None = None,
) -> ProjectReport:
    """Read terminal ``action_items`` artifacts and file fresh assertions to the inbox.

    Idempotent: an assertion is filed at most once — ``fresh`` is the candidates whose
    identity is not already open in ``fold(ledger)``. When committing, the human's
    dispositions are captured first (so a cleared task is recorded and never resurrected),
    then each fresh candidate is filed and an ``Asserted`` event appended. With
    ``commit=False`` nothing is written — a dry run for inspecting the grounded candidates.
    """
    all_emails = read_action_items(root, limit=limit, since=since)
    emails = [ea for ea in all_emails if _is_actionable(ea.category)]
    filtered = len(all_emails) - len(emails)
    candidates = to_candidates(emails)

    log_events = events.load(ledger)
    disposed_events: list[events.Event] = []
    if commit:
        disposed_events = _capture_dispositions(log_events, db_path=db_path, user_id=user_id)
        if disposed_events:
            events.append(ledger, disposed_events)
            log_events = log_events + disposed_events

    # Suppress on *all* known identities (open or closed), not just open ones — a
    # disposed assertion is handled, not fresh, so it never resurrects.
    known = events.known_identities(log_events)
    fresh = [c for c in candidates if c.identity not in known]

    if not commit or not fresh:
        return ProjectReport(
            total_emails=len(emails),
            total_items=len(candidates),
            fresh=fresh,
            filed=0,
            notified=False,
            nonactionable_filtered=filtered,
            disposed=len(disposed_events),
        )

    new_events: list[events.Event] = []
    for c in fresh:
        _file_one(c, user_id=user_id, db_path=db_path)
        new_events.append(
            events.asserted(
                c.identity,
                payload={
                    "action_phrase": c.action_phrase,
                    "source_quote": c.source_quote,
                    "message_id": c.message_id,
                    "citation": c.citation,
                    "task_text": c.task_text(),
                    "list_name": c.list_name,
                },
                valid_time=c.valid_time,
            )
        )
    events.append(ledger, new_events)

    notified = False
    if notify:
        notified = _notify(
            f"📥 Added {len(fresh)} task(s) to your GTD inbox from email.", chat_id=user_id
        )

    return ProjectReport(
        total_emails=len(emails),
        total_items=len(candidates),
        fresh=fresh,
        filed=len(fresh),
        notified=notified,
        nonactionable_filtered=filtered,
        disposed=len(disposed_events),
    )
