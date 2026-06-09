"""Owner profile — the authoritative ground truth about *who the owner is*.

Distinct from the pkm corpus (which holds *evidence the owner has*): this is who "I"/"my"
refers to. It is injected into **every** synthesis answer as always-on context so that
retrieved documents about *other* people — a partner's health report, a co-signer's ID — are
not mistaken for the owner's. It is not retrieved or BM25-ranked; it is the lens through which
the retrieved SOURCES are read.

Architectural placement (decided deliberately): owner-truth lives **life-agent-side**, not in
pkm. Putting "my name is X" into the content-addressed corpus would make it just one more
rankable chunk competing with a family member's document — it would not fix identity confusion.
So the profile is a small markdown file under ``$LIFE_AGENT_KB`` (out of the public repo, out of
pkm). The owner extends it opportunistically — ``ask-live --tell "My name is …"`` or ``/i …`` in
the REPL — which appends here.
"""
from __future__ import annotations

from pathlib import Path

from life_agent.core import KB

# Authoritative owner profile. Seeded by hand and grown by `--tell` / `/i`.
# Module-level so tests can repoint it at a tmp path.
PROFILE = KB / "owner.md"

_TOLD_HEADING = "## Told by the owner"


def load_profile() -> str:
    """The owner profile text, or '' if none exists yet. Missing profile degrades gracefully —
    the answer path stays functional, just without the identity lens."""
    try:
        return PROFILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def append_fact(fact: str, *, when: str) -> Path:
    """Append one owner-told fact as a timestamped bullet under the '## Told by the owner'
    section (created once, on first use). Appends in place; writes only under $LIFE_AGENT_KB.
    Returns the profile path."""
    fact = fact.strip()
    existing = load_profile()
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE.open("a", encoding="utf-8") as fh:
        if _TOLD_HEADING not in existing:
            # blank line before the heading only when seeded prose precedes it
            sep = "\n" if existing else ""
            fh.write(f"{sep}{_TOLD_HEADING}\n\n")
        fh.write(f"- {fact}  _(told {when})_\n")
    return PROFILE
