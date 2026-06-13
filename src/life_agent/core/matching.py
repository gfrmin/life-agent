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
    contiguous token run. Token-boundary, not substring."""
    chunk_tokens = tokenize(chunk_text)
    for candidate in [answer, *variants]:
        cand_tokens = tokenize(candidate)
        if cand_tokens and _is_contiguous_sublist(cand_tokens, chunk_tokens):
            return True
    return False


def chunk_matches_any(answer: str, variants: list[str], chunks: list[str]) -> bool:
    """True if any chunk in ``chunks`` contains the answer (token-boundary)."""
    return any(answer_matches(answer, variants, c) for c in chunks)
