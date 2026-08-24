"""Token-boundary matching — the one tokenization contract shared with the FTS index.

Moved from ``scripts/eval_grading.py`` (which re-exports) so core modules — the
citation audit and the narrative family's claim grading — can use the SAME matcher
the eval trusts without importing from scripts. Tokenize both sides with the rule
the pkm FTS index uses (runs of Unicode letters/digits, casefolded) and check the
needle's tokens form a *contiguous sublist* of the haystack's. Anchoring on the FTS
tokenization avoids substring false positives (``123456789`` does NOT match inside
``1123456789``; ``50000`` does NOT match inside ``150000``).
"""
from __future__ import annotations

import re

from life_agent.core.dates import parse_date

# `[^\W_]+` = runs of Unicode letters/digits (excluding underscore), which
# mirrors the FTS tokeniser's `ignore='[^\p{L}\p{N}]+'`. casefold() lowercases
# (no-op for Hebrew). This is the shared tokenization contract.
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Split text into FTS-compatible tokens (Unicode alphanumerics, casefolded)."""
    return _TOKEN_RE.findall(text.casefold())


def _is_contiguous_sublist(needle: list[str], haystack: list[str]) -> bool:
    """True if ``needle`` appears as a contiguous run within ``haystack``."""
    if not needle:
        return False
    n = len(needle)
    return any(haystack[i: i + n] == needle for i in range(len(haystack) - n + 1))


def answer_matches(answer: str, variants: list[str], chunk_text: str) -> bool:
    """True if ``answer`` (or any of ``variants``) appears in ``chunk_text`` as a
    contiguous token run. Token-boundary, not substring.

    Date-aware: when ``chunk_text`` IS itself a calendar date, a candidate naming the SAME date in
    another format matches (``25 December 1999`` ≡ ``25/12/1999`` — the grader was undercounting
    correct date answers on format alone). ``parse_date`` returns None for a document chunk, so the
    value-in-document case is unchanged — this only loosens value-vs-value comparison."""
    chunk_tokens = tokenize(chunk_text)
    chunk_date = parse_date(chunk_text)
    for candidate in [answer, *variants]:
        cand_tokens = tokenize(candidate)
        if cand_tokens and _is_contiguous_sublist(cand_tokens, chunk_tokens):
            return True
        if chunk_date is not None and parse_date(candidate) == chunk_date:
            return True
    return False


def chunk_matches_any(answer: str, variants: list[str], chunks: list[str]) -> bool:
    """True if any chunk in ``chunks`` contains the answer (token-boundary)."""
    return any(answer_matches(answer, variants, c) for c in chunks)


# ── The competing-values detector (§4.2's competition term, measured at the source) ──────
# A maximal digit run with commas/dots joining digits: "$1,234,567" is ONE 7-digit span,
# never three comma-split fragments (the FTS tokenizer above splits on commas — that rule
# is for containment matching, not for shape). Spaces break spans, so adjacent spreadsheet
# columns never merge into one shape.
_NUM_SPAN_RE = re.compile(r"\d(?:[\d,.]*\d)?")


def numeric_spans(text: str) -> list[str]:
    """Maximal numeric spans of ``text``, in order (digits joined by ``,``/``.`` only)."""
    return _NUM_SPAN_RE.findall(text)


def _span_canon(span: str) -> str:
    """Identity of a span: its digits, leading zeros stripped (mirrors the §4.2 candidate
    canon) — format variants of one number never read as two values."""
    digits = "".join(ch for ch in span if ch.isdigit())
    return digits.lstrip("0") or "0"


def _span_classes(text: str) -> dict[str, set[str]]:
    """Map span canon → its shape classes in ``text``. A span immediately followed by
    ``%`` is class ``"percent"`` (percents compete across digit counts — 74.2% vs 97%);
    otherwise its class is its digit count."""
    classes: dict[str, set[str]] = {}
    for m in _NUM_SPAN_RE.finditer(text):
        span = m.group(0)
        end = m.end()
        cls = "percent" if end < len(text) and text[end] == "%" else str(
            sum(ch.isdigit() for ch in span))
        classes.setdefault(_span_canon(span), set()).add(cls)
    return classes


_QUOTE_MARGIN = 120


def quote_scoped_competitors(value: str, chunk_text: str, quote: str) -> int:
    """The FROZEN live detector (sweep 2026-08-17, D3/cap1): competitors within the
    extractor's own grounded quote ±120 chars of its position in the chunk — the anchor
    the extractor disambiguated by. A same-shape value INSIDE the anchor (the fax beside
    the tel it was asked for) is the dangerous shape; same-shape values in other rows are
    what the quote already resolved. Whole-chunk scanning measured 24-32/56 collateral on
    the run-8 corrects; quote-scoped measured 18/56 with the same 3/3 wrong flips."""
    if quote:
        pos = chunk_text.find(quote)
        if pos >= 0:
            return competing_value_count(
                value, chunk_text[max(0, pos - _QUOTE_MARGIN):
                                  pos + len(quote) + _QUOTE_MARGIN])
        return competing_value_count(value, quote)
    return competing_value_count(value, chunk_text)


def competing_value_count(value: str, chunk_text: str) -> int:
    """Distinct values in ``chunk_text`` that COMPETE with ``value``: same shape class
    (digit count, or the percent class), different canon. Repeats and format variants of
    the value itself never compete; a digit-free value has no shape and never trips.
    Pure and model-free — the count feeds ``lookup.competition_factor``, the §4.2
    competition term the terminal was under-weighting (foundations §14, 2026-08-17)."""
    value_classes = _span_classes(value)
    if not value_classes:
        return 0
    own_canons = set(value_classes)
    own_shapes = set().union(*value_classes.values())
    return sum(1 for canon, shapes in _span_classes(chunk_text).items()
               if canon not in own_canons and shapes & own_shapes)


# --- r10 D1: the entity key's detector ------------------------------------------------------

# Identifier-like shapes ONLY, in the order the $0 census that priced the rule collected them.
# Ordinary English words are deliberately unreachable: the r09d anchor scored documents by
# question-vocabulary overlap and was refuted across three variants, so a key that could pick
# up "coverage" or "statement" would be that lever wearing a different hat.
_IDENTIFIER_PATTERNS = (
    re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|md|json|ya?ml|sql|jl|toml|csv|pdf|docx?|xlsx?)\b"),
    re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b"),      # CamelCase, >= 2 humps
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),          # snake_case
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),                     # ALLCAPS ids
)


def identifier_terms(text: str) -> list[str]:
    """The tokens in ``text`` that NAME something, in census order, first occurrence wins.

    A filename's snake_case stem comes back as its own term. That is what the census did and
    it is harmless under E1's ALL contract — a chunk carrying the filename carries the stem —
    but it is load-bearing for reproducing the census's numbers, so it is kept deliberately
    rather than tidied away.
    """
    found: list[str] = []
    for pattern in _IDENTIFIER_PATTERNS:
        for match in pattern.findall(text):
            if match not in found:
                found.append(match)
    return found
