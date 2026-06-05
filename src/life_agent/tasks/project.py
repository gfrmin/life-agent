"""The action faculty's projector: cached ``action_items`` → GTD inbox (M2).

A thin, idempotent bridge from immutable pkm artifacts into the mutable jarvis
GTD store. It reads terminal ``action_items`` artifacts (each grounded + cited by
its email's Message-ID via the lineage walk in ``read.py``) and files every
not-yet-seen item **once** into the inbox — process-once via a ledger, so a task
the owner later clears never returns.

It owns no SQLite or HTTP of its own: the write is jarvis in-process
(``db.add_task``) and the nudge is jarvis's ``digest.send_telegram``. "Policy" is
deliberately tiny — everything → inbox, never auto-scheduled — and lives here
inline rather than as its own module; richer routing, if ever wanted, belongs in
*more transforms* (SPEC §18.7), not in imperative code here.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import life_agent.core as C
from life_agent.tasks import dedup
from life_agent.tasks.read import EmailActions, read_action_items

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candidate:
    """One action item staged for the GTD inbox."""

    action_phrase: str
    source_quote: str
    message_id: str
    citation: str
    dedup_key: str
    list_name: str = "inbox"

    def task_text(self) -> str:
        """The text written to jarvis: the action plus its source citation."""
        return f"{self.action_phrase} {self.citation}"


def to_candidates(emails: list[EmailActions]) -> list[Candidate]:
    """Flatten emails → inbox candidates (everything→inbox, cited, dedup-keyed).

    The Message-ID is the email's; if an email lacks one we fall back to its
    content-addressed cache key (still stable and unique).
    """
    out: list[Candidate] = []
    for ea in emails:
        mid = ea.message_id or ea.email_cache_key or ea.action_items_cache_key
        for i, item in enumerate(ea.items):
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
                    dedup_key=f"{mid}#{i}",
                )
            )
    return out


@dataclass(frozen=True)
class ProjectReport:
    """Outcome of a ``project_action_items`` run."""

    total_emails: int
    total_items: int
    fresh: list[Candidate]
    filed: int
    notified: bool


def _file_one(candidate: Candidate, *, user_id: int, db_path: Path) -> None:
    """File one candidate into the jarvis GTD inbox (in-process write).

    ``db.DB_PATH`` is a module var read by ``get_db()``; point it at the
    configured store. ``init_db`` is idempotent (CREATE TABLE IF NOT EXISTS),
    so a fresh store is handled.
    """
    from jarvis import db

    db.DB_PATH = Path(db_path)
    db.init_db()
    db.add_task(user_id, candidate.task_text(), "inbox")


def _notify(text: str, *, chat_id: int) -> bool:
    """Best-effort Telegram nudge, reusing jarvis's sender. False if unconfigured.

    jarvis's ``send_telegram`` reads ``TELEGRAM_TOKEN`` from the environment; we
    seed it from ``C.secret`` (env *or* gnome-keyring) so an ad-hoc run works
    without ``load_secrets_from_keyring``. Never raises — a notify failure must
    not fail the filing, which is the source of truth.
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
    """Read terminal ``action_items`` artifacts and file fresh items to the inbox.

    Idempotent: each item is filed at most once (process-once via *ledger*). With
    ``commit=False`` nothing is written — a dry run for inspecting the grounded
    candidates. ``user_id`` is only used when committing/notifying.
    """
    emails = read_action_items(root, limit=limit, since=since)
    candidates = to_candidates(emails)
    seen = dedup.load_seen(ledger)
    fresh = [c for c in candidates if c.dedup_key not in seen]

    if not commit or not fresh:
        return ProjectReport(
            total_emails=len(emails), total_items=len(candidates),
            fresh=fresh, filed=0, notified=False,
        )

    for c in fresh:
        _file_one(c, user_id=user_id, db_path=db_path)
    dedup.append_seen(
        ledger,
        [{"dedup_key": c.dedup_key, "message_id": c.message_id} for c in fresh],
    )

    notified = False
    if notify:
        notified = _notify(
            f"📥 Added {len(fresh)} task(s) to your GTD inbox from email.",
            chat_id=user_id,
        )

    return ProjectReport(
        total_emails=len(emails), total_items=len(candidates),
        fresh=fresh, filed=len(fresh), notified=notified,
    )
