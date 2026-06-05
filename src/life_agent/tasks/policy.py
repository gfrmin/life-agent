"""GTD policy: turn extracted action items into inbox candidates (M2).

Deliberately minimal and conservative: **every** candidate goes to the GTD
**inbox** for the human to triage — never auto-scheduled, never auto-tagged. Each
candidate carries a `[src:email <Message-ID>]` citation and a process-once dedup
key (`<message_id>#<index>`). The Message-ID is the email's; if an email lacks one
we fall back to its content-addressed cache key (still stable and unique).
"""

from __future__ import annotations

from dataclasses import dataclass

from life_agent.tasks.read import EmailActions


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
    """Flatten emails → inbox candidates, preserving per-email item order."""
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
