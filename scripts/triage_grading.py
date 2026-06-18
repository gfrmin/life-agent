"""Pure triage classifier for the answer baseline (no IO, no DB, no model).

The retrieval eval (``eval_grading.classify``) grades ONE channel — was the true
value in the admitted evidence? The adoption gate grades the decision. Neither says
*why* a question the agent could have answered went unanswered. This classifier
crosses the two channels to bucket every question by the lever that would fix it —
the retrieval roadmap (owner directive, 2026-06-18).

The metric that matters: correct-answer rate at ZERO confident-wrong. So the buckets:

    SCOPED           — a report_scoped: a TRUE time-scoped claim ("as of <date>, X") when the
                       current value was uncertain (scoped-claims design). A real answer, never
                       a confident-wrong; below CORRECT (it is not the current value) and above
                       a withholding (it answered). The oracle confirms the record attests it.
    CORRECT          — asserted (report/hedge) a value matching the gold.
    CONFIDENT_WRONG  — asserted a wrong value (cause=wrong_value) or a wrong-subject
                       distractor (cause=distractor). The cardinal sin; the hard
                       gate is that this count stays 0.
    RIGHTLY_WITHHELD — withheld, and the truth was not cleanly available:
                         cause=unanswerable  — no gold value exists; or
                         cause=coverage_gap  — gold exists in the world but is not in
                                               the corpus (an ingestion gap, not a
                                               retrieval one).
    WRONGLY_WITHHELD — withheld though the truth WAS retrievable. The answer-rate
                       loss, bucketed by where the truth was lost:
                         cause=retrieval_miss  — gold in corpus, not in top-k;
                         cause=extraction_miss — gold in a top-k chunk, not surfaced
                                                 as a candidate;
                         cause=pooling_loss    — gold surfaced as a candidate but lost
                                                 the posterior (the recency/pooling
                                                 failure; the mobile-number class).

``needs_judgment`` flags rows where a token-boundary match is not the whole story and
the Opus oracle must adjudicate: every assertion (genuinely right/wrong, or an unlisted
variant / stale-but-grounded?) and every pooling_loss (genuine ambiguity, or a
recoverable answer the decision layer wrongly withheld?).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Triage:
    """One question's triage: the bucket, its cause, and whether the oracle adjudicates."""

    bucket: str  # CORRECT | CONFIDENT_WRONG | RIGHTLY_WITHHELD | WRONGLY_WITHHELD
    cause: str | None  # see module docstring (None only for CORRECT)
    needs_judgment: bool  # True where the Opus oracle must adjudicate the row


def triage(
    *,
    answerable: bool,
    asserted: bool,
    asserted_correct: bool,
    asserted_distractor: bool,
    gold_in_candidates: bool,
    gold_in_topk: bool,
    gold_in_corpus: bool,
    scoped: bool = False,
    asserted_verdict: str | None = None,
) -> Triage:
    """Cross the retrieval and decision channels into one bucket + cause.

    Precedence is scoped-first, then asserted: a ``report_scoped`` is a TRUE time-scoped claim
    about the record (scoped-claims design), so it is never the cardinal sin — its own SCOPED
    bucket, the oracle confirming the record genuinely attests it. An unqualified assertion is
    then either right or the cardinal sin, regardless of where retrieval landed (a
    confident-wrong over a retrieval miss is still a confident-wrong). Withholdings split by
    whether the truth was reachable and, if so, where in the pipeline it was lost.
    """
    if scoped:
        # the agent qualified the value with its as-of date — an honest non-answer to a
        # current-value question (not correct, but not the sin: it never claims currency).
        return Triage("SCOPED", "as_of_record", needs_judgment=True)
    if asserted:
        # the owner's temporal verdict (when present) is authoritative and needs no oracle.
        if asserted_verdict == "correct" or (asserted_verdict is None and asserted_correct):
            return Triage("CORRECT", None, needs_judgment=asserted_verdict is None)
        # a PLAINLY-asserted value that is not the current answer is a confident-wrong — even
        # if it was true once (owner: "a stale answer is still wrong"). cause=stale_value tags
        # the recency/scoping-fixable kind (truth recoverable by date) apart from a hard wrong;
        # both count against the hard gate. Only the scoped rendering above escapes.
        cause = ("stale_value" if asserted_verdict == "stale"
                 else "distractor" if asserted_distractor else "wrong_value")
        return Triage("CONFIDENT_WRONG", cause, needs_judgment=asserted_verdict is None)

    # withheld (abstain / ask_clarify / no family asserted)
    if not answerable:
        return Triage("RIGHTLY_WITHHELD", "unanswerable", needs_judgment=False)
    if not gold_in_corpus:
        return Triage("RIGHTLY_WITHHELD", "coverage_gap", needs_judgment=False)
    if not gold_in_topk:
        return Triage("WRONGLY_WITHHELD", "retrieval_miss", needs_judgment=False)
    if not gold_in_candidates:
        return Triage("WRONGLY_WITHHELD", "extraction_miss", needs_judgment=False)
    return Triage("WRONGLY_WITHHELD", "pooling_loss", needs_judgment=True)
