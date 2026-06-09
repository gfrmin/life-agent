"""Numbered source cards + their neutral rendering, shared by every answer path.

A :class:`SourceCard` is one retrieved chunk shown to the model as ``[n] text``; ``origin``
is provenance kept for display/logging. The rendering is deliberately citation-shape neutral
so the blind comparison harness can reuse it without leaking which system produced an answer.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SourceCard:
    n: int
    text: str            # the cited text (a retrieved chunk)
    origin: str = ""     # provenance for the harness/display only; never shown to a blind judge


def render_sources_block(cards: list[SourceCard]) -> str:
    return "\n\n".join(f"[{c.n}] {c.text}" for c in cards)
