"""Deterministic, latency-free citation faithfulness — the claim parse + value audit.

Moved from ``scripts/citation_guard.py`` (which re-exports) so the narrative family
(foundations §7) can score the claims it parses with the SAME deterministic
instrument the answer-time guard uses. After synthesis, verify that every
*value-bearing* claim (one that asserts an ID, number, date, amount, or proper noun)
cites a SOURCE whose text actually contains that value — using the token-boundary
matcher the eval trusts (:mod:`life_agent.core.matching`). This catches the dangerous
failure mode (a confident value cited to a chunk that does not support it, e.g. a
family member's ID asserted as the owner's) with **zero extra LLM calls**.

Scope, stated honestly: this checks *verbatim* facts only — the things a wrong
citation most damages. Paraphrased/synthesised prose is NOT verified here; that is
measured by the eval's LLM judge (``run_eval.py --synthesis``) and, per claim, by the
narrative family's population credences. The guard *flags* (does not delete)
unverified claims, so a false positive costs a spurious "⚠ unverified" note, never a
mangled answer — and a real miss stays visible for the dogfood loop.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from life_agent.core.matching import answer_matches

# One or more consecutive citation markers, e.g. "[1]" or " [1][2]".
_CITE_GROUP_RE = re.compile(r"(?:\s*\[\d+\])+")
_CITE_NUM_RE = re.compile(r"\[(\d+)\]")
# A verifiable value span: a digit run (kept only if it carries >=4 digits — IDs, years,
# amounts, dates) or a multi-word proper noun (names/orgs; >=2 capitalised words, which skips
# sentence-initial single words like "Your"/"The").
_DIGIT_RUN_RE = re.compile(r"\d[\d,.:/\-]*\d")
_PROPER_NOUN_RE = re.compile(r"[A-Z][\w'’.\-]*(?:\s+[A-Z][\w'’.\-]*)+")  # noqa: RUF001  curly apostrophe in names


class SourceLike(Protocol):
    """Anything with a card number and text — the audit's source contract."""

    @property
    def n(self) -> int: ...

    @property
    def text(self) -> str: ...


@dataclass(frozen=True)
class CitationAudit:
    """Verdict of a citation audit. ``ok`` means nothing to flag."""

    dangling: tuple[int, ...]                  # [n] markers with no matching source card
    unsupported: tuple[tuple[str, int], ...]   # (claim snippet, n): card n lacks the claim's value

    @property
    def ok(self) -> bool:
        return not self.dangling and not self.unsupported

    def footer(self) -> str:
        """A one-block human-readable warning, or '' when clean."""
        if self.ok:
            return ""
        lines = ["⚠ unverified:"]
        for claim, n in self.unsupported:
            lines.append(f"  - [{n}] does not support: “{claim}”")
        if self.dangling:
            dangling = ", ".join(f"[{n}]" for n in self.dangling)
            lines.append(f"  - dangling citation(s) with no source: {dangling}")
        return "\n".join(lines)


def value_spans(claim: str) -> list[str]:
    """Verbatim 'facts' worth verifying in a claim: digit runs (>=4 digits) + multi-word
    proper nouns. Returned as raw substrings so the token-boundary matcher tokenises them the
    same way it tokenises the source chunk."""
    spans = [s for s in _DIGIT_RUN_RE.findall(claim) if sum(ch.isdigit() for ch in s) >= 4]
    spans += _PROPER_NOUN_RE.findall(claim)
    return spans


def extract_citations(text: str) -> list[tuple[str, set[int]]]:
    """Segment ``text`` into (claim, {n,...}) pairs: each citation group is attributed to the
    text span that immediately precedes it. A trailing uncited span gets an empty set."""
    out: list[tuple[str, set[int]]] = []
    last = 0
    for m in _CITE_GROUP_RE.finditer(text):
        out.append((text[last:m.start()], {int(x) for x in _CITE_NUM_RE.findall(m.group())}))
        last = m.end()
    tail = text[last:]
    if tail.strip():
        out.append((tail, set()))
    return out


def audit(answer: str, cards: Iterable[SourceLike]) -> CitationAudit:
    """Verify each ``[n]`` points at a card whose text contains a verbatim value from the claim
    it trails. ``cards`` is any sequence of objects with ``.n`` and ``.text``. Pure; no I/O.

    A citation is *supported* if at least one of its claim's value spans appears (token-boundary)
    in the cited card — lenient on purpose, to keep false positives (spurious warnings) low."""
    by_n: dict[int, str] = {c.n: c.text for c in cards}
    dangling: list[int] = []
    unsupported: list[tuple[str, int]] = []
    for claim, markers in extract_citations(answer):
        values = value_spans(claim)
        for n in sorted(markers):
            if n not in by_n:
                dangling.append(n)
            elif values and not any(answer_matches(v, [], by_n[n]) for v in values):
                unsupported.append((claim.strip()[:80], n))
    return CitationAudit(dangling=tuple(dict.fromkeys(dangling)), unsupported=tuple(unsupported))
