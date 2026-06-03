"""Pure grading logic for the answer-grounded eval (no IO, no DB).

Separated from run_eval.py so it is trivially unit-testable. Two concerns:

1. **Token-boundary matching** — does a chunk contain the answer? Tokenize both
   with the SAME Unicode rule the pkm FTS index uses (split on non-alphanumeric
   runs, casefold) and check the answer's tokens are a *contiguous sublist* of
   the chunk's tokens. Anchoring on the FTS tokenization means the matcher and
   the retrieval layer share one tokenization contract, and it avoids substring
   false positives (`123456789` does NOT match inside `1123456789`; `50000`
   does NOT match inside `150000`).

2. **Verdict classification** — PASS / RETRIEVAL_MISS / ABSENT(_COVERAGE|
   _EXTRACTION), with SUBJECT_CONFUSION reported as an *orthogonal* flag (a
   question can be PASS+confused or MISS+confused; it is never a verdict).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


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


@dataclass(frozen=True)
class Verdict:
    """The grade for one question. ``verdict`` is the retrieval outcome;
    ``subject_confusion`` is orthogonal (a separate reported dimension)."""

    verdict: str  # PASS | RETRIEVAL_MISS | ABSENT_COVERAGE | ABSENT_EXTRACTION | ABSENT_UNSPECIFIED
    subject_confusion: bool


def classify(
    *,
    answer_in_topk: bool,
    answer_in_corpus: bool,
    distractor_in_topk: bool,
    mode_hint: str | None,
) -> Verdict:
    """Map the three retrieval booleans + ``mode_hint`` to a verdict.

    - answer in top-k                       -> PASS
    - answer in corpus but not top-k        -> RETRIEVAL_MISS
    - answer nowhere in corpus              -> ABSENT_{COVERAGE|EXTRACTION|UNSPECIFIED}
      (the reason — not-ingested vs OCR-destroyed — is the question's mode_hint)

    SUBJECT_CONFUSION is set whenever a distractor is retrieved in top-k,
    independent of the verdict above.
    """
    if answer_in_topk:
        verdict = "PASS"
    elif answer_in_corpus:
        verdict = "RETRIEVAL_MISS"
    else:
        suffix = {"coverage": "COVERAGE", "extraction": "EXTRACTION"}.get(
            mode_hint or "", "UNSPECIFIED"
        )
        verdict = f"ABSENT_{suffix}"
    return Verdict(verdict=verdict, subject_confusion=distractor_in_topk)
