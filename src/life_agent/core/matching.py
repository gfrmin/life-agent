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
    return competing_value_count(value, quote_window(chunk_text, quote))


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

def quote_window(chunk_text: str, quote: str) -> str:
    """THE anchor window both §4.2 terms read: the extractor's own quote ± the frozen
    margin, located in the chunk. Falls back to the quote when it is not found in the
    chunk (a tokenization-divergent replay), and to the whole chunk when there is no
    quote — the ladder frozen with the competing-values detector. One definition, two
    consumers (§6.8): :func:`quote_scoped_competitors` and :func:`discriminating_terms`."""
    if quote:
        pos = chunk_text.find(quote)
        if pos >= 0:
            return chunk_text[max(0, pos - _QUOTE_MARGIN):
                              pos + len(quote) + _QUOTE_MARGIN]
        return quote
    return chunk_text


# ── The entity anchor (r09d D1) ─────────────────────────────────────────────────────────
# The r09c wire class: an observation carries a value but not the QUALIFIER saying what the
# value is of — a class-scoped question answered with the file-scoped row of the same table,
# a fax question answered with the telephone beside it. Both survive every aggregation rule
# because at the decide layer they are simply documents that disagree. The discriminating
# terms are computed FROM the channel (a question token some window carries and another does
# not), so the rule is relative by construction: no window separates them ⇒ nothing fires.
_ANCHOR_MIN_LEN = 3
# Grammar only. A word that could ever BE the qualifier ("number", "total", "rate") must
# never appear here — a stopword list that grows into content is how this rule goes wrong.
_ANCHOR_STOPWORDS = frozenset({
    "what", "whats", "which", "when", "where", "whose", "whom", "who", "why", "how",
    "does", "did", "done", "doing", "this", "that", "these", "those", "there", "then",
    "than", "from", "with", "without", "have", "has", "had", "been", "being", "was",
    "were", "are", "and", "the", "for", "its", "his", "her", "their", "our",
    "you", "your", "any", "all", "into", "onto", "about", "many", "much", "please",
    "according", "listed", "shown", "stated", "given", "say", "says", "said",
})


def anchor_window(chunk_text: str, quote: str) -> str:
    """The window the ENTITY ANCHOR reads: the whole document chunk, not the value's
    neighbourhood. Ruling 2026-08-24, on a $0 battery census — scoped to
    :func:`quote_window` the rule damped the GOLD on 26 of 42 firings and inverted the
    ranking on 12, because the qualifier that says what a value is OF (a subject in a
    header, a class label a table-width away) routinely sits outside ±120 while a rival
    document's copy happens to carry it. Document-scoped it is strictly harmful on one row
    at the same clean-firing count. The competition term KEEPS the narrow window: a
    competing value must be adjacent to compete, an anchor need not be."""
    return chunk_text


def _anchor_terms(question: str) -> list[str]:
    """The question's content tokens, first-seen order, deduped: casefolded FTS tokens of
    at least ``_ANCHOR_MIN_LEN`` characters that are not grammar."""
    out: list[str] = []
    for tok in tokenize(question):
        if len(tok) >= _ANCHOR_MIN_LEN and tok not in _ANCHOR_STOPWORDS and tok not in out:
            out.append(tok)
    return out


def discriminating_terms(question: str, windows: list[str]) -> tuple[str, ...]:
    """The question's content tokens that SEPARATE the channel: present in at least one
    observation's :func:`quote_window` and absent from at least one. A term every window
    carries discriminates nothing; a term no window carries discriminates nothing either.
    Pure and model-free — the count feeds ``lookup.anchor_factor``."""
    if len(windows) < 2:
        return ()
    token_sets = [set(tokenize(w)) for w in windows]
    return tuple(t for t in _anchor_terms(question)
                 if any(t in ts for ts in token_sets)
                 and not all(t in ts for ts in token_sets))


def anchor_score(window: str, terms: tuple[str, ...]) -> int:
    """How many discriminating ``terms`` this window carries, token-boundary (never a
    substring: a term does not match inside a longer token)."""
    tokens = set(tokenize(window))
    return sum(1 for t in terms if t in tokens)
