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
from datetime import date
from pathlib import Path
from typing import Any

from life_agent.core import config
from life_agent.core import decisions as DEC
from life_agent.core import derivations as D
from life_agent.core import llm as LLM
from life_agent.core import outcomes as O
from life_agent.core import recorder as REC
from life_agent.core import reliability as REL
from life_agent.core import seam as SEAM
from life_agent.core.brain import Brain
from life_agent.core.citation import SourceLike, extract_citations, value_spans
from life_agent.core.decide import u_assert
from life_agent.core.matching import answer_matches

# --- stated scorer parameters (priors; the claim-level stream moves them — §2/§7) -------
# Per-cell Beta priors for P(claim correct | audit cell). Wide on purpose: the lookup
# family's refuted Beta(17,3) taught that fiat trust burns (construct validity — a
# verified span can be the wrong subject's value); the cells earn trust from evidence.
# the closed audit partition; each cell's prior lives in the ONE reliability table
# (core/reliability.PRIORS — D-2, r13/M3), bound here so the partition keeps its name
# [§3.3 · N-1] the claim cells — the claims' observation model.
_CELLS: tuple[str, ...] = ("verified", "unsupported", "unverifiable")
_CELL_PRIORS: dict[str, tuple[float, float]] = {
    cell: REL.PRIORS[("eval_claim", cell)] for cell in _CELLS}
# P(a true relevant claim is proposed at all) — the open-world tail's prior. Wide:
# "this may be incomplete" until eval_coverage evidence narrows it.
_COVERAGE_PRIOR: tuple[float, float] = (2.0, 2.0)

# The audit-outcome likelihood: a Bernoulli on the cell-correctness θ (1 = correct, 0 = wrong).
# Every cell/coverage Beta is conditioned on these OVER THE WIRE — never a host `a += 1` fold
# (Invariant 1: the one learning mechanism is `condition`, even though conjugacy is exact).
_BERNOULLI: dict[str, str] = {"type": "bernoulli"}


def _beta_ab(spec: Mapping[str, Any]) -> tuple[float, float]:
    """(alpha, β) from a `read_params` Beta spec — relayed as a parameterisation, never folded."""
    return float(spec["alpha"]), float(spec["beta"])

# Closed abstention reasons (the credence grammar — interaction contract).
REASON_NO_CLAIMS = "no claims proposed"
REASON_ALL_WITHHELD = "all claims below the inclusion threshold"

# One grammar table for every rendered string (drift-gated; interaction contract).
GRAMMAR: dict[str, str] = {
    "claim": "- {text} {cites}— credence {p:.3f}{asof}",
    "as_of": ", as of {date}",   # the temporal-scope suffix; empty when the claim is undated
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
    as_of: str | None = None   # freshest doc_date among the claim's cited cards (ISO), or None
                               # when none is dated — the temporal-scope render + the outcome tag


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

def _cell_observations(outcomes_path: Path) -> dict[str, list[float]]:
    """Tally the claim-level audit outcomes per cell (1 = correct, 0 = wrong), filtered on the
    CURRENT instrument identity (§2). Pure data-reading — the Bernoulli stream the wire folds;
    no belief arithmetic. An event with a cell outside the partition raises (cells are closed)."""
    current = instrument_identity()
    by_cell: dict[str, list[float]] = {cell: [] for cell in _CELL_PRIORS}
    for event in O.read(outcomes_path):
        if event.grader != "eval_claim" or event.instrument_identity != current:
            continue
        cell = (event.signals or {}).get("audit_cell")
        if cell not in by_cell:
            raise ValueError(f"audit cell outside the partition: {cell!r}")
        by_cell[cell].append(1.0 if event.grade in O.CORRECT_GRADES["eval_claim"] else 0.0)
    return by_cell


def population_posteriors(brain: Brain, outcomes_path: Path = config.OUTCOMES_LOG
                          ) -> dict[str, tuple[float, float]]:
    """P(claim correct | audit cell): per-cell Beta (alpha, β), the stated prior CONDITIONED OVER
    THE WIRE on the cell's audit outcomes — never a host `a += 1` fold (Invariant 1). The body
    tallies the Bernoulli stream (data), conditions each cell's Beta through `condition`, and
    reads the exact posterior params back via `read_params`. Returns {cell: (alpha, β)} — the same
    shape as the priors, so cells with no evidence stay at their stated wide priors."""
    by_cell = _cell_observations(outcomes_path)
    post: dict[str, tuple[float, float]] = {}
    for cell in _CELL_PRIORS:
        post[cell] = REL.reliability(brain, "eval_claim", cell, by_cell[cell])
    return post


def coverage_posterior(brain: Brain, outcomes_path: Path = config.OUTCOMES_LOG
                       ) -> tuple[tuple[float, float], int]:
    """The open-world tail: Beta posterior on P(a true relevant claim is proposed), the prior
    CONDITIONED OVER THE WIRE on the eval_coverage events for the current instrument (no host
    `a += 1`). Returns ((alpha, β), n observed events)."""
    current = instrument_identity()
    obs = [1.0 if e.grade in O.CORRECT_GRADES["eval_coverage"] else 0.0
           for e in O.read(outcomes_path)
           if e.grader == "eval_coverage" and e.instrument_identity == current]
    sid = brain.create_state(
        {"type": "beta", "alpha": _COVERAGE_PRIOR[0], "beta": _COVERAGE_PRIOR[1]})
    try:
        for o in obs:
            brain.condition(sid, kernel=_BERNOULLI, observation=o)
        return _beta_ab(brain.read_params(sid)), len(obs)
    finally:
        brain.destroy_state(sid)


# --- the verdict → cell learning loop (the owner IS the gold) ----------------------------

def owner_claim_outcomes(result: NarrativeResult, question_id: str,
                         verdicts: Mapping[int, bool], *, run_id: str = "dogfood",
                         ) -> list[O.OutcomeEvent]:
    """Turn the owner's per-claim verdicts into ``eval_claim`` outcomes — the live twin of
    ``run_eval.narrative_claim_outcome`` with the owner standing in for the gold. ``verdicts``
    maps a claim index → True(correct) / False(incorrect); ONLY verdicted claims emit (DISCLOSED
    selection — an unjudged claim leaves its cell at the current posterior, never a silent vote).
    The events carry the claim's audit cell + asserted credence + the CURRENT instrument identity,
    so ``population_posteriors`` re-folds the named cell on the next answer — closing the learning
    loop the offline grader left open. Crucially, a grounded-but-stale claim verdicted INCORRECT
    LOWERS its (verified) cell: the owner teaches that grounded ≠ current-correct. The event also
    carries the claim's ``claim_as_of`` signal — recorded so a later slice can SEPARATE a
    stale-INCORRECT from a never-true-INCORRECT; the current per-cell fold still reads only the
    audit cell (the keystone is fold-neutral)."""
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
            signals={"audit_cell": c.cell, "included": c.included,
                     "claim_as_of": c.as_of}))
    return events


def record_owner_verdicts(result: NarrativeResult, question_id: str,
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
    """The reliance-linear labeled-claim EU, the STATED MODEL (module docstring):
    ``EU(include | p) = p·u_assert(p) - κ_att`` — the reliance ``p`` scales the assertion
    atom :func:`life_agent.core.decide.u_assert`, minus the per-claim attention cost.

    Reference formula + test oracle: the DECISION runs this exact model OVER THE WIRE via
    :func:`_claim_pref` — ``optimise{include, withhold}`` on the cell Beta, whose include
    functional :func:`_include_fn` is the *integrated* form ``E_θ[include_eu(θ·tf)]`` over the
    posterior (the proper model — not this point estimate at ``p = E[θ]``; the integral keeps
    the ``Var(θ)·(u_c-u_w)`` term). This pure function is not on the decision path."""
    return p * u_assert(p, u_bar) - u_bar["kappa_att"]


def _include_fn(u_bar: Mapping[str, float], tf: float) -> dict[str, Any]:
    """The include action's functional: the EXACT integrated claim-EU over the cell Beta,
    ``E_θ[(θ·tf)·u_assert(θ·tf)] - κ = (u_c-u_w)·tf²·E[θ²] + u_w·tf·E[θ] - κ`` — a
    `centered_power` (E[θ²]) + `identity` (E[θ]) LinearCombination. ``tf`` is the staleness
    factor (1.0 unscoped); it scales the utility coefficients (preference data), NOT a credence
    (so the staleness decay is the proper integral, never a host multiply on a belief value)."""
    u_c, u_w, kappa = u_bar["u_correct"], u_bar["u_wrong"], u_bar["kappa_att"]
    return {"type": "linear_combination",
            "terms": [[(u_c - u_w) * tf * tf, {"type": "centered_power", "n": 2}],
                      [u_w * tf, {"type": "identity"}]],
            "offset": -kappa}


def _claim_pref(u_bar: Mapping[str, float], tf: float) -> dict[str, Any]:
    """The per-claim ``optimise`` preference: include (the integrated EU) vs withhold (the gauge
    zero ``u_abstain``). The engine picks — the body never compares EUs."""
    return {"type": "functional_per_action", "actions": {
        "include": _include_fn(u_bar, tf),
        "withhold": {"type": "linear_combination", "terms": [], "offset": u_bar["u_abstain"]},
    }}


# functional_per_action ignores the action space; a placeholder keeps the protocol shape.
_CLAIM_ACTIONS: dict[str, Any] = {"type": "finite", "values": [0.0, 1.0]}


def freshest_as_of(cites: tuple[int, ...],
                   as_of_by_n: Mapping[int, str | None]) -> str | None:
    """The freshest (max ISO) doc_date among a claim's CITED cards, or None when none is dated.
    ISO date strings order chronologically under lexicographic max — a present-intent reader can
    see at a glance whether the cited evidence is current or stale (the keystone of
    temporal scope)."""
    dated = [d for n in cites if (d := as_of_by_n.get(n)) is not None]
    return max(dated) if dated else None


def decide_claims(brain: Brain,
                  scored: list[tuple[str, tuple[int, ...], str, str | None, float]],
                  cells_ab: Mapping[str, tuple[float, float]],
                  u_bar: Mapping[str, float]
                  ) -> tuple[tuple[Claim, ...], str, float, str]:
    """Per-claim inclusion under Ū, decided OVER THE WIRE: each claim's include/withhold is the
    engine's ``optimise{include, withhold}`` on its cell Beta (the integrated include-EU via
    `centered_power`, the staleness factor ``tf`` scaling the utility coefficients), committed
    through the ONE act seam (:func:`life_agent.core.seam.commit` — roadmap M0) — never a
    host EU compare. The answer action is ``report`` iff any claim clears (the per-claim
    threshold is the exact powerset argmax under claim independence — the separability proof in
    :mod:`life_agent.core.decide`). Each scored tuple is (text, cites, cell, as_of, tf); ``as_of``
    is display + outcome tag (it does NOT enter the EU — keystone decision-neutral; staleness
    enters only through ``tf``). Returns (claims in posterior order, action, eu, abstain_reason)."""
    cell_states: dict[str, str] = {}
    claims: list[Claim] = []
    try:
        for text, cites, cell, as_of, tf in scored:
            sid = cell_states.get(cell)
            if sid is None:
                a, b = cells_ab[cell]
                sid = brain.create_state({"type": "beta", "alpha": a, "beta": b})
                cell_states[cell] = sid
            action = SEAM.commit(SEAM.SkinOptimise(
                brain=brain, state_id=sid, actions=_CLAIM_ACTIONS,
                preference=_claim_pref(u_bar, tf))).action
            eu_i = brain.expect(sid, function=_include_fn(u_bar, tf))  # recorded include-EU
            credence = brain.mean(sid) * tf  # display (staleness-decayed); decision was `action`
            claims.append(Claim(text=text, cites=cites, cell=cell, credence=credence,
                                included=(action == "include"), eu_include=eu_i, as_of=as_of))
    finally:
        for sid in cell_states.values():
            brain.destroy_state(sid)
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
            asof = GRAMMAR["as_of"].format(date=c.as_of) if c.as_of else ""
            lines.append(GRAMMAR["claim"].format(
                text=" ".join(c.text.split()), cites=f"{cites} " if cites else "",
                p=c.credence, asof=asof))
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

def scope_decay(credence: float, as_of: str | None, claim_text: str, scope: str,
                *, today: date | None = None) -> float:
    """[§3.3 · N-4] the claims' time covariate — the claim-side branch of D-14. The
    present-intent staleness decay (temporal-scope slice 3) — GATE-SAFE: it only ever
    LOWERS a credence, so it can add abstention but never a new confident-wrong. Applies ONLY to
    a present-scope question and ONLY to a DATED claim (an undated claim is a derivation gap, not
    evidence of staleness — never penalise recall, [[verdict-rule-truth-relevance]]); a non-present
    scope leaves the cell credence untouched. The decay is the lookup family's own
    :func:`life_agent.core.lookup.time_factor` at the claim's volatility half-life — a recent
    ``as_of`` → factor ≈ 1; an old one → < 1."""
    if scope != "present" or as_of is None:
        return credence
    from life_agent.core import lookup as LK
    from life_agent.core import volatility as VOL
    return credence * LK.time_factor(as_of, time_indexed=True, today=today,
                                     half_life_years=VOL.half_life(claim_text))


def scope_decay_factor(as_of: str | None, claim_text: str, scope: str,
                       *, today: date | None = None) -> float:
    """The staleness factor ``tf ∈ (0, 1]`` (= ``scope_decay(1.0, …)``): the present-scope DATED
    claim's volatility time_factor, else 1.0. It scales the include-EU functional coefficients
    (``tf²`` on E[θ²], ``tf`` on E[θ]) — the EXACT integral of ``include_eu(θ·tf)`` over the cell
    Beta — so the staleness decay is the proper integral, never a host multiply on a belief
    value. Gate-safe: ``tf ≤ 1`` only ever LOWERS the effective credence."""
    return scope_decay(1.0, as_of, claim_text, scope, today=today)


def narrative_answer(root: Path, question: str, text: str,
                     cards: Iterable[SourceLike], *,
                     scope: str = "unscoped",
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
    from life_agent.core import answer_shape as AS
    from life_agent.core import lookup as LK
    # the wire holds every cell/coverage Beta; the body conditions + decides through it
    b = LK.shared_brain()
    if u_bar is None or utility_fold_version is None:
        # r30 (C5): this question's own answer shape prices its own decision — never a
        # separate rescoring, always through current_u_bar's one seam.
        u_bar, utility_fold_version, _policy = LK.current_u_bar(
            b, shape=AS.answer_space(question))

    opath = outcomes_path if outcomes_path is not None else config.OUTCOMES_LOG
    cards = list(cards)
    cards_by_n = {c.n: c.text for c in cards}
    # the card's doc_date (None when the card type or the projection is dateless — a card need only
    # satisfy SourceLike, which carries no date, so read it optionally and degrade to undated)
    as_of_by_n = {c.n: getattr(c, "as_of", None) for c in cards}
    parsed = parse_claims(text)
    cells = population_posteriors(b, opath)  # {cell: (alpha, β)} — wire-conditioned, no host fold
    scored = []
    for claim_text, cites in parsed:
        cell = audit_cell(claim_text, cites, cards_by_n)
        as_of = freshest_as_of(cites, as_of_by_n)
        # scope-aware inclusion: a present-intent question decays a DATED stale claim toward the
        # bar via tf (gate-safe — tf ≤ 1 only lowers it); tf scales the EU functional engine-side,
        # never a host multiply. tf = 1.0 unscoped/undated; the raw cell (alpha, β) stays
        # recoverable.
        tf = scope_decay_factor(as_of, claim_text, scope)
        scored.append((claim_text, cites, cell, as_of, tf))
    claims, action, eu, reason = decide_claims(b, scored, cells, u_bar)
    coverage, coverage_n = coverage_posterior(b, opath)

    # the answer artifact (§18.9): the scored claim set + decision inputs, lineage to
    # the proposal. The folds are decision inputs, so the exact (a, b) state enters
    # both the key (params) and the recorded content (auditability).
    params = {"cells": {k: list(v) for k, v in sorted(cells.items())},
              "coverage": list(coverage),
              "kappa_att": u_bar["kappa_att"], "u_wrong": u_bar["u_wrong"],
              # a decision input (the present-intent decay) — new scope ⇒ new artifact
              "scope": scope,
              "instrument": instrument_identity()}
    claims_hash = _sha(json.dumps([{"text": t, "cites": list(c)} for t, c in parsed],
                                  sort_keys=True, ensure_ascii=False))
    akey = D.narrative_answer_key(question, claims_hash, utility_fold_version, params)
    content = json.dumps({
        "format_version": 1, "question": question, "action": action, "eu": eu,
        "abstain_reason": reason, "scope": scope,
        "claims": [{"text": c.text, "cites": list(c.cites), "cell": c.cell,
                    "credence": c.credence, "included": c.included} for c in claims],
        "coverage": list(coverage), "coverage_n": coverage_n,
        "cell_posteriors": {k: list(v) for k, v in sorted(cells.items())},
        "utility_fold_version": utility_fold_version,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    lineage = ([{"cache_key": synthesize_cache_key, "role": "proposal"}]
               if synthesize_cache_key else [])
    result = NarrativeResult(
        question=question, action=action, eu=eu, abstain_reason=reason,
        claims=claims, coverage=coverage, coverage_n=coverage_n,
        cell_posteriors=cells, utility_fold_version=utility_fold_version,
        answer_cache_key=akey.cache_key, rendered="")
    result = _with_render(result)

    # M2 (design §5.1): the decision's two records are the ONE recorder's.
    REC.record_local(
        root, akey, content, lineage=lineage,
        decisions_path=(decisions_path if decisions_path is not None
                        else config.DECISIONS_LOG),
        event=DEC.DecisionEvent(
                   tx_time=O.now_iso(), run_id=run_id,
                   question_id=DEC.question_id(question),
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
                   # M5 (r15, §2.3): the narrative leaf's per-claim ranking is the
                   # skin's — terminals-only, DECLARED (see lookup's twin comment).
                   regime="terminals-only", policy=LK.U_BAR_POLICY, defaulted=(),
                   decision_id=akey.cache_key))
    return result


def _with_render(result: NarrativeResult) -> NarrativeResult:
    import dataclasses

    return dataclasses.replace(result, rendered=render(result))
