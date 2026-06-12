"""The ledger→knowledge projection: ``fold(events)`` rendered as one document.

The mutable→knowledge mirror of ``project.py`` (system-design.md §5). The GTD
event ledger is the act layer's truth; this module projects its fold into a
markdown document at one stable declared path so the knowledge base can retrieve
it like any source — "what's next on my gtd list?" becomes an ordinary cited
answer, and the completions history makes "what did I complete last week?"
answerable.

Pure by construction: no clock, no randomness — every date comes from an event,
and the document is stamped with the ledger head it folds
(``as of event N · ledger sha256 <hash>``) so ask-time staleness is a cheap
comparison (the demand-led refresh in ``scripts/ask.py``). The fold itself is
``store.apply`` replayed into an in-memory projection — event semantics live in
one place.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

from life_agent.tasks import events as ev
from life_agent.tasks import store

# The projection is f(events, renderer): bump on ANY rendering change so the
# demand-led refresh re-projects and re-ingests exactly as for a ledger append.
RENDER_VERSION = 2

_STAMP_RE = re.compile(r"ledger sha256 ([0-9a-f]{64}) · render v(\d+)")

_PREAMBLE = (
    "The owner's GTD (Getting Things Done) task state — the to-do lists "
    "(inbox, next actions, scheduled, someday), today's focus, and the "
    "completed-task history — projected from the task event ledger."
)


def parse_stamp(text: str) -> tuple[str, int] | None:
    """The (ledger sha, render version) embedded in a state document, or None."""
    m = _STAMP_RE.search(text)
    return (m.group(1), int(m.group(2))) if m else None


def render(events: list[ev.Event], *, ledger_sha: str) -> str:
    """Render the fold of ``events`` as markdown. Pure: same events, same bytes."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        store.create_schema(conn)
        store.rebuild(conn, events)

        lines: list[str] = [
            "# GTD task state",
            "",
            _PREAMBLE,
            "",
            f"as of event {len(events)} · ledger sha256 {ledger_sha} · render v{RENDER_VERSION}",
            "",
            "## Current tasks",
        ]

        today = conn.execute(
            "SELECT * FROM tasks WHERE is_today = 1 AND completed_at IS NULL ORDER BY id"
        ).fetchall()
        if today:
            lines += ["", "### Today's focus"]
            lines += [f"- task {r['id']}: {r['text']}" for r in today]

        # "What's next?" is this document's reason to exist: the specific,
        # high-signal lists (#next, #scheduled, #someday) render before the
        # large unspecific #inbox, so the head chunk answers the question.
        # Task ids stay unbracketed — "[2]" reads as a citation marker
        # downstream (synthesis + citation guard).
        ordered = sorted(store.VALID_LISTS, key=lambda lst: lst == "inbox")
        for lst in ordered:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE list = ? AND completed_at IS NULL ORDER BY id",
                (lst,),
            ).fetchall()
            lines += ["", f"### #{lst} ({len(rows)})"]
            if not rows:
                lines.append("- (no tasks)")
            for r in rows:
                entry = f"- task {r['id']}: {r['text']}"
                if r["due_date"]:
                    entry += f" (due {r['due_date']})"
                if r["is_today"]:
                    entry += " ★ today"
                lines.append(entry)
    finally:
        conn.close()

    # History comes from the events themselves: the fold deletes dropped rows,
    # but a disposal is still a fact worth retrieving.
    texts = {
        e.identity: str(e.payload.get("text", e.identity))
        for e in events
        if e.type == "asserted"
    }
    verbs = {"done": "completed"}
    history = [
        f"- {e.tx_time[:10]} — {verbs.get(e.reason or '', 'deleted')}: "
        f"{texts.get(e.identity, e.identity)}"
        for e in events
        if e.type == "disposed"
    ]
    lines += ["", "## History (completions and disposals, newest first)"]
    lines += list(reversed(history)) if history else ["- (none)"]
    return "\n".join(lines) + "\n"


def write_state(ledger: Path, out: Path) -> str:
    """Project ``ledger`` to ``out`` (write only on change); return the ledger sha.

    A missing ledger is an empty GTD — still a valid (empty) state document, so
    the knowledge base never carries a stale one."""
    data = ledger.read_bytes() if ledger.exists() else b""
    sha = hashlib.sha256(data).hexdigest()
    text = render(ev.load(ledger), ledger_sha=sha)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not (out.exists() and out.read_text(encoding="utf-8") == text):
        out.write_text(text, encoding="utf-8")
    return sha
