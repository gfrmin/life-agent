"""The narrative family — slice 3 of Ask v0 (bayesian-foundations §7).

No path outside the paradigm: the free-form synthesis LLM becomes a **proposal
distribution** — it proposes claims, it scores nothing. The synthesize instrument and
its cache keys are untouched; everything here is read-side policy over its output
(the grounding-gate precedent: scorer surgery re-scores every answer, never orphans
the proposal). Three moves, each stated:

1. **Claim decomposition (deterministic).** The rendered answer is parsed at citation
   boundaries (:func:`life_agent.core.citation.extract_citations` — claim boundaries
   ARE citation boundaries in v0). Each claim is audited by the deterministic citation
   instrument into one of three cells: ``verified`` (a value span token-contained in a
   cited card), ``unsupported`` (value spans + citations, none support), or
   ``unverifiable`` (no value spans, or no citations — the deterministic check is
   silent).

2. **Population calibration.** P(claim correct | audit cell) is a per-cell Beta fold
   of the claim-level outcomes stream (grader ``eval_claim``), filtered on the EXACT
   current instrument identity (§2 — generator model + synthesize version + parse
   version; a change starts the new instrument at its prior). Cells with no evidence
   stay at their stated wide priors — out-of-distribution honesty by construction.
   v0 conditions on the audit cell only; retrieval strength and question shape are
   named §7 signals deferred until the stream can support them. Disclosed (M2 on the
   grading channel): eval claim grading reaches only gold/distractor-bearing claims,
   so the ``unverifiable`` cell is expected to stay near its prior until the owner
   graders (verdicts, corrections) deepen it.

3. **The proposal-coverage term (the open-world tail, §7 move 3).** A Beta posterior
   on P(a true relevant claim is proposed at all), conditioned on ``eval_coverage``
   events (a proposer miss is an observable event — §8 grader 1, instrumented in
   run_eval). v0 renders it in the footer (named, never silent) and logs it with the
   decision; it does not modify per-claim EU (one claim's correctness is independent
   of other claims having been missed) — its EU coupling arrives with the aggregate
   family (§5).

The response is an EU decision per claim (M4) under the utility posterior mean, with
the **reliance-linear labeled-claim model** (stated): every included claim renders
WITH its credence label, the owner's reliance on a labeled claim is proportional to
the label, and conditional on reliance the outcome is the crisp u_correct / u_wrong;
κ_att is the per-claim attention cost (load-bearing here for the first time) —

    EU(include | p) = p · (p·u_correct + (1-p)·u_wrong) - κ_att,   EU(withhold) = 0.

At p = 1 this recovers the crisp report EU; a p = 0.5 label carries near-zero
information value and is dominated by its attention cost. Whether a wrong labeled
claim really costs reliance-scaled u_wrong is an empirical question the decision log
plus owner reactions adjudicate (§4.4) — it is a stated mapping, not a new latent.
The answer action is ``report`` iff any claim clears inclusion, else ``abstain``
(closed reasons); honest consequence at the stated priors and current Ū: narrative
answers ABSTAIN until the evidence stream deepens — §7's "wide priors hedge until
evidence narrows them", not a defect to soften.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import llm as LLM
from life_agent.core import outcomes as O
from life_agent.core.citation import SourceLike, extract_citations, value_spans
from life_agent.core.decide import u_assert
from life_agent.core.matching import answer_matches

# --- stated scorer parameters (priors; the claim-level stream moves them — §2/§7) -------
# Per-cell Beta priors for P(claim correct | audit cell). Wide on purpose: the lookup
# family's refuted Beta(17,3) taught that fiat trust burns (construct validity — a
# verified span can be the wrong subject's value); the cells earn trust from evidence.
_CELL_PRIORS: dict[str, tuple[float, float]] = {
    "verified": (3.0, 2.0),      # containment passed; construct validity unproven
    "unsupported": (1.0, 3.0),   # the cited source lacks the value — but the gate
                                 # has known false positives (the RTL lesson)
    "unverifiable": (2.0, 2.0),  # the deterministic instrument is silent
}
# P(a true relevant claim is proposed at all) — the open-world tail's prior. Wide:
# "this may be incomplete" until eval_coverage evidence narrows it.
_COVERAGE_PRIOR: tuple[float, float] = (2.0, 2.0)

# Closed abstention reasons (the credence grammar — interaction contract).
REASON_NO_CLAIMS = "no claims proposed"
REASON_ALL_WITHHELD = "all claims below the inclusion threshold"

# One grammar table for every rendered string (drift-gated; interaction contract).
GRAMMAR: dict[str, str] = {
    "claim": "- {text} {cites}— credence {p:.3f}",
    "withheld": "({n} claims withheld: EU below inclusion at the utility posterior)",
    "abstain": "No answer asserted ({reason}).",
    "footer": ("narrative: {n_proposed} claims proposed → {n_included} included"
               " · coverage {cov:.3f} (n={n_cov})"
               " · decision {action} (EU {eu:.2f})"),
    "fallthrough": "(narrative: {reason} — unscored prose)",
}

_ACTION_ORDER: tuple[str, ...] = DEC.NARRATIVE_ACTION_ORDER


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Claim:
    """One proposed claim, scored: parsed text, citations, its audit cell, the
    population credence of that cell, and its inclusion decision."""

    text: str
    cites: tuple[int, ...]
    cell: str
    credence: float
    included: bool
    eu_include: float


@dataclass(frozen=True)
class NarrativeResult:
    """The narrative family's answer: the scored claim set + the decision."""

    question: str
    action: str                  # report | abstain
    eu: float
    abstain_reason: str          # '' when action == report
    claims: tuple[Claim, ...]    # posterior order (descending credence)
    coverage: tuple[float, float]   # Beta (a, b) of the proposal-coverage tail
    coverage_n: int                 # observed coverage events behind it
    cell_posteriors: dict[str, tuple[float, float]]
    utility_fold_version: str
    answer_cache_key: str
    rendered: str


def instrument_identity() -> dict[str, Any]:
    """The exact instrument identity claim-level outcomes carry and the population
    fold filters on (§2): the generator (synthesize model + version) AND the parse
    version — surgery on either starts a new posterior at the priors, never pooling
    evidence about a superseded instrument."""
    return {"producer_name": "life_agent.ask.synthesize",
            "producer_version": D.SYNTHESIZE_VERSION,
            "model": LLM.DEFAULT_ANSWER_MODEL,
            "narrative_version": D.NARRATIVE_ANSWER_VERSION}


# --- move 1: deterministic claim parse + audit cells ------------------------------------

def parse_claims(text: str) -> list[tuple[str, tuple[int, ...]]]:
    """The proposal set: (claim text, cited card numbers) at citation boundaries.
    Spans with no word content are dropped (separators, stray markup), nothing else —
    the parse is deliberately dumb and deterministic."""
    claims: list[tuple[str, tuple[int, ...]]] = []
    for span, cites in extract_citations(text):
        stripped = span.strip(" \t\n-•*")
        if not any(ch.isalnum() for ch in stripped):
            continue
        claims.append((stripped, tuple(sorted(cites))))
    return claims


def audit_cell(claim_text: str, cites: tuple[int, ...],
               cards_by_n: Mapping[int, str]) -> str:
    """The deterministic citation instrument's verdict for one claim:
    ``verified`` / ``unsupported`` / ``unverifiable`` (see module docstring).
    A dangling citation (no such card) supports nothing."""
    values = value_spans(claim_text)
    if not values or not cites:
        return "unverifiable"
    for n in cites:
        chunk = cards_by_n.get(n)
        if chunk is not None and any(answer_matches(v, [], chunk) for v in values):
            return "verified"
    return "unsupported"


# --- move 2 + 3: the population and coverage folds (closed-form Beta) --------------------

def population_posteriors(outcomes_path: Path = config.OUTCOMES_LOG
                          ) -> dict[str, tuple[float, float]]:
    """P(claim correct | audit cell): per-cell Beta — stated prior + the claim-level
    evidence carrying the CURRENT instrument identity. An event with an audit cell
    outside the partition raises: within one narrative version cells are closed by
    construction, so junk is a code bug surfacing, never silent weight."""
    current = instrument_identity()
    post = dict(_CELL_PRIORS)
    for event in O.read(outcomes_path):
        if event.grader != "eval_claim":
            continue
        if event.instrument_identity != current:
            continue
        cell = (event.signals or {}).get("audit_cell")
        if cell not in post:
            raise ValueError(f"audit cell outside the partition: {cell!r}")
        a, b = post[cell]
        if event.grade in O.CORRECT_GRADES["eval_claim"]:
            a += 1.0
        else:
            b += 1.0
        post[cell] = (a, b)
    return post


def coverage_posterior(outcomes_path: Path = config.OUTCOMES_LOG
                       ) -> tuple[tuple[float, float], int]:
    """The open-world tail: Beta posterior on P(a true relevant claim is proposed),
    conditioned on the eval_coverage events for the current instrument. Returns
    ((a, b), n observed events)."""
    current = instrument_identity()
    a, b = _COVERAGE_PRIOR
    n = 0
    for event in O.read(outcomes_path):
        if event.grader != "eval_coverage":
            continue
        if event.instrument_identity != current:
            continue
        n += 1
        if event.grade in O.CORRECT_GRADES["eval_coverage"]:
            a += 1.0
        else:
            b += 1.0
    return (a, b), n


# --- the verdict → cell learning loop (the owner IS the gold) ----------------------------

def owner_claim_outcomes(result: "NarrativeResult", question_id: str,
                         verdicts: Mapping[int, bool], *, run_id: str = "dogfood",
                         ) -> list[O.OutcomeEvent]:
    """Turn the owner's per-claim verdicts into ``eval_claim`` outcomes — the live twin of
    ``run_eval.narrative_claim_outcome`` with the owner standing in for the gold. ``verdicts``
    maps a claim index → True(correct) / False(incorrect); ONLY verdicted claims emit (DISCLOSED
    selection — an unjudged claim leaves its cell at the current posterior, never a silent vote).
    The events carry the claim's audit cell + asserted credence + the CURRENT instrument identity,
    so ``population_posteriors`` re-folds the named cell on the next answer — closing the learning
    loop the offline grader left open. Crucially, a grounded-but-stale claim verdicted INCORRECT
    LOWERS its (verified) cell: the owner teaches that grounded ≠ current-correct."""
    events: list[O.OutcomeEvent] = []
    for i, c in enumerate(result.claims):
        if i not in verdicts:
            continue
        events.append(O.OutcomeEvent(
            tx_time=O.now_iso(), run_id=run_id, question_id=question_id,
            claim=c.text[:200], construct="claim",
            grade="CORRECT" if verdicts[i] else "INCORRECT", grader="eval_claim",
            instrument_identity=instrument_identity(),
            lineage_keys=(result.answer_cache_key,),
            probability=c.credence,
            signals={"audit_cell": c.cell, "included": c.included}))
    return events


def record_owner_verdicts(result: "NarrativeResult", question_id: str,
                          verdicts: Mapping[int, bool], *, run_id: str = "dogfood",
                          outcomes_path: Path = config.OUTCOMES_LOG) -> int:
    """Append the owner's per-claim verdicts as ``eval_claim`` outcomes (the cell-learning fold).
    Returns the number of outcomes written. Idempotent only by content-addressed reuse upstream —
    callers dedupe by not re-judging the same answer."""
    events = owner_claim_outcomes(result, question_id, verdicts, run_id=run_id)
    for e in events:
        O.append(outcomes_path, e)
    return len(events)


# --- M4: the per-claim inclusion decision under Ū ----------------------------------------

def include_eu(p: float, u_bar: Mapping[str, float]) -> float:
    """The reliance-linear labeled-claim EU (stated model — module docstring):
    ``EU(include | p) = p·u_assert(p) - κ_att`` — the reliance ``p`` scales the assertion
    atom :func:`life_agent.core.decide.u_assert`, minus the per-claim attention cost.
    Withholding is the per-claim abstention at the gauge zero; the inclusion threshold
    ``include_eu(p) > u_abstain`` is the exact powerset argmax under claim independence
    (the separability proof in :mod:`life_agent.core.decide`)."""
    return p * u_assert(p, u_bar) - u_bar["kappa_att"]


def decide_claims(scored: list[tuple[str, tuple[int, ...], str, float]],
                  u_bar: Mapping[str, float]
                  ) -> tuple[tuple[Claim, ...], str, float, str]:
    """Per-claim inclusion under Ū; the answer action is ``report`` iff any claim
    clears (EU(report) = Σ included EU — the empty sum IS the abstain gauge). The per-claim
    threshold is the exact argmax over the 2ⁿ inclusion subsets — claims are independent and
    answer utility additive, so the powerset optimum factorises (the separability proof in
    :mod:`life_agent.core.decide`).
    Returns (claims in posterior order, action, eu, abstain_reason)."""
    claims = []
    for text, cites, cell, p in scored:
        eu_i = include_eu(p, u_bar)
        claims.append(Claim(text=text, cites=cites, cell=cell, credence=p,
                            included=eu_i > u_bar["u_abstain"], eu_include=eu_i))
    claims.sort(key=lambda c: c.credence, reverse=True)
    included = [c for c in claims if c.included]
    if not claims:
        return tuple(claims), "abstain", u_bar["u_abstain"], REASON_NO_CLAIMS
    if not included:
        return tuple(claims), "abstain", u_bar["u_abstain"], REASON_ALL_WITHHELD
    return tuple(claims), "report", sum(c.eu_include for c in included), ""


# --- render (deterministic — the render IS the claim set) --------------------------------

def render(result: NarrativeResult) -> str:
    """The credence grammar (interaction contract): included claims in posterior
    order, each with its credence and citations; withheld claims counted; the
    coverage tail and the decision named in the footer — nothing silent."""
    lines: list[str] = []
    if result.action == "report":
        for c in result.claims:
            if not c.included:
                continue
            cites = "".join(f"[{n}]" for n in c.cites)
            lines.append(GRAMMAR["claim"].format(
                text=" ".join(c.text.split()), cites=f"{cites} " if cites else "",
                p=c.credence))
        n_withheld = sum(1 for c in result.claims if not c.included)
        if n_withheld:
            lines.append(GRAMMAR["withheld"].format(n=n_withheld))
    else:
        lines.append(GRAMMAR["abstain"].format(reason=result.abstain_reason))
    a, b = result.coverage
    footer = GRAMMAR["footer"].format(
        n_proposed=len(result.claims),
        n_included=sum(1 for c in result.claims if c.included),
        cov=a / (a + b), n_cov=result.coverage_n,
        action=result.action, eu=result.eu)
    return "\n".join(lines) + f"\n\n{footer}"


# --- the family, end to end ---------------------------------------------------------------

def narrative_answer(root: Path, question: str, text: str,
                     cards: Iterable[SourceLike], *,
                     u_bar: Mapping[str, float] | None = None,
                     utility_fold_version: str | None = None,
                     outcomes_path: Path | None = None,
                     decisions_path: Path | None = None,
                     synthesize_cache_key: str | None = None,
                     run_id: str = "ask") -> NarrativeResult:
    """Score the synthesize proposal end-to-end: parse → audit cells → population
    credences → per-claim EU decision → answer artifact (§18.9) → decision logged
    (no EU decision is ever made unlogged) → labeled render. Pure given its inputs
    except the folds (outcomes log) and the two appends."""
    if u_bar is None or utility_fold_version is None:
        from life_agent.core import lookup as LK
        b = LK.shared_brain()
        u_bar, utility_fold_version = LK.current_u_bar(b)

    opath = outcomes_path if outcomes_path is not None else config.OUTCOMES_LOG
    cards_by_n = {c.n: c.text for c in cards}
    parsed = parse_claims(text)
    cells = population_posteriors(opath)
    scored = []
    for claim_text, cites in parsed:
        cell = audit_cell(claim_text, cites, cards_by_n)
        a, b_ = cells[cell]
        scored.append((claim_text, cites, cell, a / (a + b_)))
    claims, action, eu, reason = decide_claims(scored, u_bar)
    coverage, coverage_n = coverage_posterior(opath)

    # the answer artifact (§18.9): the scored claim set + decision inputs, lineage to
    # the proposal. The folds are decision inputs, so the exact (a, b) state enters
    # both the key (params) and the recorded content (auditability).
    params = {"cells": {k: list(v) for k, v in sorted(cells.items())},
              "coverage": list(coverage),
              "kappa_att": u_bar["kappa_att"], "u_wrong": u_bar["u_wrong"],
              "instrument": instrument_identity()}
    claims_hash = _sha(json.dumps([{"text": t, "cites": list(c)} for t, c in parsed],
                                  sort_keys=True, ensure_ascii=False))
    akey = D.narrative_answer_key(question, claims_hash, utility_fold_version, params)
    content = json.dumps({
        "format_version": 1, "question": question, "action": action, "eu": eu,
        "abstain_reason": reason,
        "claims": [{"text": c.text, "cites": list(c.cites), "cell": c.cell,
                    "credence": c.credence, "included": c.included} for c in claims],
        "coverage": list(coverage), "coverage_n": coverage_n,
        "cell_posteriors": {k: list(v) for k, v in sorted(cells.items())},
        "utility_fold_version": utility_fold_version,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    lineage = ([{"cache_key": synthesize_cache_key, "role": "proposal"}]
               if synthesize_cache_key else [])
    D.record(root, akey, content, lineage=lineage)

    result = NarrativeResult(
        question=question, action=action, eu=eu, abstain_reason=reason,
        claims=claims, coverage=coverage, coverage_n=coverage_n,
        cell_posteriors=cells, utility_fold_version=utility_fold_version,
        answer_cache_key=akey.cache_key, rendered="")
    result = _with_render(result)

    DEC.append(decisions_path if decisions_path is not None else config.DECISIONS_LOG,
               DEC.DecisionEvent(
                   tx_time=O.now_iso(), run_id=run_id,
                   question_id=_sha(question)[:16],
                   family="narrative",
                   action_set=_ACTION_ORDER,
                   posterior_summary={
                       "n_proposed": len(claims),
                       "n_included": sum(1 for c in claims if c.included),
                       # §7.1 inversion cut-point: p_max = the marginal (best proposed)
                       # claim's credence, sorted first; None when no claim was proposed
                       # (NO_CLAIMS — a coverage failure, not a foldable utility call).
                       "marginal_credence": (claims[0].credence if claims else None),
                       "abstain_reason": reason,
                       "cells": {k: list(v) for k, v in sorted(cells.items())},
                       "coverage": list(coverage), "coverage_n": coverage_n,
                   },
                   utility_fold_version=utility_fold_version,
                   chosen_action=action, predicted_eu=eu,
                   decision_id=akey.cache_key))
    return result


def _with_render(result: NarrativeResult) -> NarrativeResult:
    import dataclasses

    return dataclasses.replace(result, rendered=render(result))
