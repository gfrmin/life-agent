"""The email→GTD projector: cached ``action_items`` → the GTD inbox.

A thin, idempotent *producer* of events into the agent's one task ledger
(``life_agent.tasks.events``). It reads terminal ``action_items`` artifacts (each grounded
+ cited by its email's Message-ID via the lineage walk in ``read.py``) and files every
not-yet-known assertion **once**, through the command layer (``commands.add``), as an
``Asserted(origin="email")`` event. The read-model updates as a fold; a task the human later
clears in Telegram becomes a first-class ``Disposed`` event (no capture/diff) — so "already
handled" is just membership in the ledger's known identities, keyed on a content+grounding
**assertion identity** (not a positional ``message_id#index``).

Everything → inbox; that tiny policy lives here inline. Richer routing, if ever wanted,
belongs in *more transforms* (SPEC §18.7), not here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from life_agent.reach import telegram
from life_agent.tasks import commands, events, store
from life_agent.tasks.read import EmailActions, read_action_items

logger = logging.getLogger(__name__)

# Which email_triage categories (SPEC §18.8) become GTD tasks — the deterministic
# actionability policy that lives in the consumer, not pkm. None (untriaged) is included
# (fail-open): the gate only *excludes* emails explicitly classified non-actionable.
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
        """The text filed as a task: the action plus its source citation."""
        return f"{self.action_phrase} {self.citation}"


def to_candidates(emails: list[EmailActions]) -> list[Candidate]:
    """Flatten emails → inbox candidates (everything→inbox, cited, identity-keyed).

    The Message-ID is the email's (falling back to a content-addressed cache key); it is
    provenance/citation, *not* identity. Identity is the content+grounding hash, so the same
    action re-extracted from the same quote dedups regardless of position or rewording.
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


def _notify(text: str, *, chat_id: int) -> bool:
    """Best-effort Telegram nudge via the reach transport. Never raises.

    A notify failure (no token configured → ``SystemExit`` from ``secret``, or a network
    hiccup) must not fail the filing, which is the source of truth.
    """
    try:
        telegram.send_message(chat_id, text)
        return True
    except SystemExit:
        return False  # no TELEGRAM_TOKEN in env or keyring — skip quietly
    except Exception as e:
        logger.warning("telegram notify failed: %s", e)
        return False


def project_action_items(
    root: Path,
    *,
    user_id: int,
    commit: bool = True,
    notify: bool = True,
    limit: int | None = None,
    since: datetime | None = None,
) -> ProjectReport:
    """Read terminal ``action_items`` artifacts and file fresh assertions to the inbox.

    Idempotent: an assertion is filed at most once — ``fresh`` is the candidates whose
    identity is not already *known* to the ledger (open or disposed), so a re-derivation
    never duplicates and a cleared task never resurrects. Each fresh candidate is filed via
    ``commands.add`` (append ``Asserted(origin="email")`` → fold the read-model). With
    ``commit=False`` nothing is written — a dry run for inspecting the grounded candidates.
    """
    all_emails = read_action_items(root, limit=limit, since=since)
    emails = [ea for ea in all_emails if _is_actionable(ea.category)]
    filtered = len(all_emails) - len(emails)
    candidates = to_candidates(emails)

    known = events.known_identities(events.load(commands.LEDGER_PATH))
    fresh = [c for c in candidates if c.identity not in known]

    if not commit or not fresh:
        return ProjectReport(
            total_emails=len(emails),
            total_items=len(candidates),
            fresh=fresh,
            filed=0,
            notified=False,
            nonactionable_filtered=filtered,
        )

    store.init_db()
    for c in fresh:
        commands.add(
            user_id,
            c.task_text(),
            identity=c.identity,
            origin="email",
            valid_time=c.valid_time,
        )

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
    )
