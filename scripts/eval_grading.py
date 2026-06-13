"""Pure grading logic for the answer-grounded eval (no IO, no DB).

Separated from run_eval.py so it is trivially unit-testable. Two concerns:

1. **Token-boundary matching** — does a chunk contain the answer? Lives in
   :mod:`life_agent.core.matching` (re-exported here): one tokenization contract
   shared by the FTS index, the eval, the citation audit, and the narrative
   family's claim grading.

2. **Verdict classification** — PASS / RETRIEVAL_MISS / ABSENT(_COVERAGE|
   _EXTRACTION), with SUBJECT_CONFUSION reported as an *orthogonal* flag (a
   question can be PASS+confused or MISS+confused; it is never a verdict).
"""

from __future__ import annotations

from dataclasses import dataclass

# The matcher moved to core (slice 3 — the citation audit and the narrative family's
# claim grading share it); re-exported here so eval imports stay stable.
from life_agent.core.matching import (  # noqa: F401  (re-exports)
    answer_matches,
    chunk_matches_any,
    tokenize,
)


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
