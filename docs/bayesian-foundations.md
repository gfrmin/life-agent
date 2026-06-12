# Bayesian foundations — the epistemics of the knowledge layer, and Ask derived as inference

> **Status: ADOPTED (2026-06-12, owner-approved).** Deliberated the same day through the
> owner's frozen-layer practice: self-review → second-expert confer via pixel6 (four
> passes to convergence — findings and dispositions in §14) → owner approval, given with
> one rider, binding: **§14's open questions are a live ledger of what we still don't
> know, each answered empirically** — every entry names the evidence that decides it and
> the stage where that evidence first exists. The §13 governance deltas are applied; the
> build slices are unblocked.
> This document is the deliberation record for an expensive-to-reverse choice: the
> probabilistic semantics of the knowledge layer. It composes with
> [`system-design.md`](./system-design.md) (the L0–L4 loop) and
> [`derivation-engine-design.md`](./derivation-engine-design.md) (the derivation leg);
> it amends their sequencing (§13) and contradicts neither's mechanism. Every in-tree
> claim verified against the working tree on 2026-06-12.

## 0. The directive, and what this document is

Owner directive (2026-06-12, verbatim in substance): *Bayesianism from the ground up, so
Ask v0 is as formally optimal as possible given real-world constraints; hard things that
are indisputably correct rather than building pragmatically; we can start everything over
if necessary; get the knowledge layer right first — including metareasoning and the
distribution over hypothesis space (Occam's razor).*

What this document does:

1. Gives the knowledge layer its **probabilistic semantics**: every derivation edge is a
   measurement instrument with an error model; every answer is a claim set with a
   posterior; nothing in the answer path stands outside the paradigm.
2. **Derives Ask** from the decision-theoretic axioms (the same three credence is built
   on: beliefs are probability measures, learning is conditioning, action maximises
   expected utility) instead of designing it — so each component is a *consequence*, and
   each approximation is a named, justified move.
3. Fixes the **roadmap to the asymptote** (PRINCIPLES §16) so the ultimate goal and the
   path — including Occam's trajectory — stay pinned (§12).

**What "indisputably correct" can honestly mean.** The exact posterior over a life given
terabytes of bytes is intractable; *absolute* optimality is not on offer. The strongest
achievable standard — adopted here as binding — is:

- **optimality relative to a stated model**: every modelling choice is written down,
  versioned, and auditable;
- **every approximation is a stated coarsening, channel model, or prior** — v0's named
  approximations are M1, M2, and M3's proposal-coverage gap (§1, §7); M4 is the exact
  decision rule, not an approximation;
- **calibration is measured, not assumed**: posteriors are scored with proper scoring
  rules against the eval corpus, adoption decisions are priced as decisions (§8), and
  the model answers to the score.

**The anti-heuristic rule — derived, not posited.** A heuristic is an action proposed
without an error model. Such an action has no computable expected utility, so an agent
that chooses by EU over its modelled action set never selects one — *and the choice set
is never empty*, because abstention is always available and modelled. That availability
is what makes the rule bite: it is a theorem of the decision rule, not a deontic
side-constraint bolted onto it. The honest boundary case: if every modelled action were
dominated by an unmodelled one, strict decision theory says take the unmodelled action —
but judging that domination already requires modelling it, however crudely. So the
invariant this document actually enforces is: **no action enters the answer path's choice
set without an error model — possibly a maximally wide one.** The remedy for a tempting
shortcut is never prohibition but pricing: give it the widest stated prior and let EU
decide (the same move as §9's no-hard-zeros rule). One dependence named now, while it is
free: this invariant keeps EU well-defined only under **bounded utilities** — true of
the v0 table (§4.4); if stage 7's goals faculty (§12) introduces unbounded utilities, a
maximally wide error model no longer yields a finite, comparable EU, and the invariant
must be revisited together with it.

## 1. The generative model, and the four named moves

There is a latent world-state **W** — the facts of the owner's life (identities, amounts,
dates, obligations, thread states). Sources are evidence *generated from* W: a bank
renders statements because transactions happened; a clinic emails because an appointment
exists. A question names a **query variable V = f(W)**. The formally correct system
computes **P(V | evidence)** and *acts on that posterior* — report, hedge, ask a
clarifying question, or abstain — by maximising expected utility.

Everything else is reached through four named moves. They are not homogeneous — and
saying so is part of the guarantee: **M1 and M2 are genuine approximations** (a
coarsening and a channel model); **M3 is an architectural commitment** whose
approximation content is the proposal-coverage gap (§7); **M4 is the exact decision
rule**, the one thing not being approximated:

- **M1 — Condition on statistics, not bytes.** Conditioning on transform outputs o(d)
  rather than raw documents is conditioning on a coarsening σ(o) ⊆ σ(D): legitimate
  Bayesian inference, weaker only in stated ways (information not captured by the
  projections is not used). The instruments and their error models are §2.
- **M2 — Model the selection channel.** Retrieval selects *which* evidence is conditioned
  on. The selection process is part of the model: for point lookups a weak term, for
  aggregates the dominant uncertainty — a recall term with priors, sharpened where
  generators are known (§5). The engine design's "retrieval recall is uncertifiable"
  caveat becomes a *term in the posterior*, not a disclaimer.
- **M3 — The LLM proposes; it never infers at question time.** For formalised question
  families, inference is conditioning + expectation over instrument observations —
  deterministic given the artifacts. LLMs appear in exactly three roles: cached
  per-document instruments (M1), claim **proposal** (§7 — proposals need no calibration
  for what they propose, only the scorer does), and rendering (§3 — itself a modelled
  instrument, not an exemption). M3's approximation content is the
  **proposal-coverage gap**: the proposal distribution's *recall* over true claims is a
  selection channel — the narrative twin of M2 — and carries its own term in the
  claim-set posterior (§7). The current pipeline's `synthesize` stage, which performs
  implicit uncalibrated inference at the last step, is the one component this document
  retires (by subsumption, §7 — not by deletion).
- **M4 — Respond by expected utility; measure calibration.** The response is
  `optimise(posterior, {report, hedge, ask-clarify, abstain}, utility)` over an explicit
  v0 utility table (§4.4). Whether the whole construction works is an empirical question
  answered by measurement (§8 — decision-weighted gates, proper-scoring diagnostics),
  never by fiat.

## 2. Instruments — the epistemic contract on every edge

**A transform is a measurement instrument pointed at a latent variable.** In credence's
vocabulary it *is* a `Kernel` (`../credence/src/kernels.jl`): a conditional distribution
P(output | input content, instrument). Its output is an **observation**, never the fact.
This makes a three-level separation precise:

| Level | What it asserts | Where it lives |
|---|---|---|
| the artifact | "instrument I emitted o from content c" — a bitwise, content-addressed fact | pkm (exists; SPEC-PRINCIPLES §4 already refuses truth claims — pkm is the instruments' **observation log**, unchanged by this design) |
| the error model | P(o \| true value v, I) | **new** — this document's §2, held agent-side |
| the posterior | P(v \| o, error model, prior) | **new** — Ask v0's output type (§3–§4) |

**Instrument identity is exact, for free.** The schema-3 cache key
(`compute_cache_key`, `src/pkm/hashing.py` — the one key function, SPEC §4.3) pins
`producer_name`, `producer_version`,
`producer_config_hash`, `model_identity_hash`, `engine_version`,
`prompt_template_hash`, `output_schema_hash`. The key minus `input_hash` *is* the
instrument's identity. Every observation is therefore attributable to a precise
instrument version — reliability posteriors never bleed across a prompt or model bump.
Most systems cannot do this; content-addressing gives it to us at zero cost.

**The contract.** Every edge in the derivation DAG — LLM *and deterministic* — declares:

1. **Construct**: which latent variable it measures (e.g. `doc_date` measures *the
   email's sent date*, not the event date a question may want — see error modes below).
2. **Error-model class**, one of:
   - **δ-after-audit** — deterministic code (parsers, folds, filters, `citation_guard`).
     Determinism buys *reproducibility, not truth*: the uncertainty is epistemic, over
     the code's correctness on the input class. Prior concentrated by tests + review;
     posterior driven to ~1 by audit observations; a found bug is fixed, the version
     bumps, the **new instrument identity** starts from an informed prior.
   - **grounded-extraction** — `quote_is_grounded` (whitespace-normalised verbatim
     resolution; an ungrounded quote fails the whole source, per
     `src/pkm/transforms/action_items.py`) deterministically *eliminates the
     fabrication mode*; residual errors are enumerable (wrong quote selected, quote
     misread).
   - **confusion-matrix** — closed-enum classification (§18.8 pattern:
     `email_triage`, `doc_subject`). The error model is a finite confusion matrix;
     conjugate (Dirichlet rows — credence `DirichletPrevision`).
   - **monolithic** — free-form generation (the narrative proposal instrument, §7).
     Population-calibrated only; the widest class.
3. **Calibration route**: which outcome stream (§8) grades it, and the stated prior.

This answers "how do we trust derivations?": **we never trust; we hold posteriors that
audit evidence moves.** Grounding and closed enums are hereby *formally justified* as
error-model surgery — they are the design moves that make instruments calibratable at
all.

**Two error modes, distinguished because attribution differs.** *Code correctness* — the
function does not do what it claims (a parser bug); caught by spot-check audits against
source bytes; attributed to the instrument. *Construct validity* — the function does
exactly what it claims, but what it claims is not what the question needs; caught by
end-to-end scoring; attributed to the question family's model (fix: a different
instrument or a new construct, not a "fix" to a correct function).

**Lineage composition.** An answer's reliability composes along its lineage edges; the
engine design's weakest-link readout (engine §9.4) becomes literal posterior arithmetic.
The exact statement of independence is **given parents in the lineage DAG**: two
observations are conditionally independent given the artifacts they were computed from —
so a shared ancestor (two edges reading the same wrong OCR artifact have perfectly
correlated errors, whatever their models) enters the arithmetic once, as the DAG records
it, never double-counted as corroboration. Content-addressing pays again: the dependence
structure *is* the lineage walk. v0 approximates full DAG-aware arithmetic with
**conservative likelihood tempering**, keyed on the two readable dependence signals —
shared ancestor artifacts in the lineage, and shared `model_identity_hash` (the same
local model running several transforms induces correlated errors even across distinct
inputs) — the composed likelihood product tempered by a stated exponent that carries its
own prior, updatable as calibration data accrues. Pinning independence at 1.0 would be a
hidden hard prior — overconfidence by design, the exact turtle §14 disowns. The full
shared-model hierarchical hyperprior (conjugate) remains the named successor; what is
not permitted is deferring every correction while shipping the unmodified independence
posterior.

**The verifier regress, cut explicitly.** Scorers are code too (`citation_guard`,
`quote_is_grounded`, the audit harness). The regress terminates by declaration: small,
audited verifiers receive strong δ-after-audit priors justified by review + tests. That
is an honest prior statement, not a dodge — and it is itself revisable by audit.

**Belief state is a fold, not a store — and the fold is order-defined.** Reliability
posteriors are *derived*: posterior = fold(outcomes log) through `condition`, recomputed
(or cached) at need. The only persistent state is the append-only outcomes log (§8) —
the same shape as PRINCIPLES §7: truth is the fold; no mutable side-store can drift. One
subtlety stated now rather than discovered later: with a *fixed* temper the fold
commutes, but the learned tempering exponent above makes updates order-dependent — the
temper applied at step t depends on the posterior running at t — so the posterior is a
function of the log's **order**, not merely its contents. The append order (tx_time) is
therefore part of the semantics: the canonical replay order, deterministic because the
log is append-only and single-writer. Same observations in a different order would be a
different posterior — by stated design, not by accident.

## 3. Answers — claim sets with posteriors

**Every answer is a set of atomic claims, each carrying a posterior and provenance.**
The unification: paths differ only in **claim provenance** and **likelihood tightness**,
never in kind.

- **Plan-derived claims** (typed families, §4–§6): produced by executing the family's
  model over instrument observations. Tight, decomposable likelihoods; per-component
  calibration.
- **LLM-proposed claims** (narrative, §7): the monolithic instrument proposes; the same
  scoring machinery disposes. Wide, population-calibrated likelihoods.

**Rendering is an instrument, not an exemption.** The posterior + provenance is the
answer; prose is its presentation — but ordering, emphasis, omission, and juxtaposition
can typeset a *true claim set into a false gestalt*, so the renderer carries the same
edge contract as every other instrument rather than standing outside the paradigm it
serves. Four parts:

1. **Inclusion is a decision, not a compliance rule.** Which claims appear is per-claim
   `optimise` under a relevance/attention utility (the attention cost lives in the §4.4
   table). Named approximation, per §0's own rule: per-claim selection is the marginal,
   greedy form of what is exactly a *joint* subset selection — claim redundancy and
   synergy break additivity — adopted in v0 under a stated additive-utility assumption,
   with joint selection the successor if redundant claim sets show up in outcomes. Every
   omission carries its EU reason, and non-silence falls out of the decision instead of
   being policed onto it: withheld claims are named in aggregate ("n claims withheld:
   low relevance") per the §13 grammar.
2. **Structure.** The interaction-contract grammar (§13) is the near-gestalt-preserving
   skeleton: claims rendered with their credences, exclusions and indeterminates named,
   ordering fixed by the claim set (posterior order, not rhetorical order) — nothing
   silent, nothing mumbled. LLM paraphrase is confined to within claim boundaries.
3. **Conformance check.** The existing deterministic citation audit
   (`scripts/citation_guard.py`, pure and recomputed per render, never cached — run on
   the rendered text exactly as `scripts/ask.py` does today) audits the rendered text
   against the *decided-to-render* set, in both directions: no claim introduced, no
   decided claim dropped. It checks the renderer's fidelity to a decision already
   priced — an instrument-error check inside the paradigm, never the inclusion policy
   itself.
4. **Residual error model.** What the decision, structure, and conformance cannot catch
   (emphasis, juxtaposition) is a **presentation-error** term: population-class, graded
   by owner-correction outcomes attributed to rendering (§8, grader 3), exactly like any
   other monolithic instrument.

**The response is a decision** (M4): `optimise` over {report the MAP claim set with its
credence · hedge (report the mixture when no value dominates) · ask a clarifying
question (priced by `voi` against the interruption cost) · abstain (named reason)}.

## 4. The lookup family — built first (owner-selected)

V is a point fact ("what is my Israeli ID?", "when is the X appointment?").

**4.1 The model.** Retrieval (the selection channel, recorded) yields evidence documents.
For each hit, instrument observations are demanded — `pkm derive` for declared constructs
(`doc_date`, `doc_subject`, …); a **question-parameterised grounded-extraction
derivation** through the §18.9 seam for ad-hoc constructs (cached, content-addressed,
grounded like `action_items`; it is a life_agent-side derivation because its prompt binds
the question — pkm transforms stay question-free). Each observation o_i of candidate
value v_i carries:

- ρ_i — the probability the observation is *correct*, from the instrument's reliability
  posterior (§2) — for grounded extraction, the post-surgery residual;
- a_i — **source authority**: P(the document's assertion equals W's value | doc class).
  v0: declared authority classes per source kind (institutional document > transactional
  email > personal note > draft/template), a stated prior, calibrated later from
  outcomes; the D2 `doc_subject` filter and `doc_date` projection enter here as
  covariates (a document about someone else, or from the wrong era, supports a different
  variable — construct validity, not noise).

**4.2 The posterior.** A noisy-channel mixture over candidate values plus an explicit
"none of the retrieved" component: P(V = v | obs) ∝ P(v) · Π_i P(o_i | V = v, ρ_i, a_i) —
**with the product composed under §2's lineage rule, never naively**. The per-hit
observations typically come from *one* instrument (the question-parameterised extractor:
identical `model_identity_hash` and `prompt_template_hash`, only `input_hash` varying),
so a plain product would write repeated prompting of a single model as independent
corroboration — exactly the correlation §2 tempers, live in the family built first. The
temper keys on shared instrument identity *and* shared evidence ancestry (two hits
descending from one forwarded original corroborate less than two independent sources;
the lineage walk exposes the common-ancestor `input_hash`). One systematic bias in the
one extractor — a date format it misreads — makes every o_i correlated-wrong; tempering
is what keeps that posterior wide instead of confidently wrong.
Conflicting evidence yields a **mixture, never an arbitrary pick** — two documents
disagreeing is a modelled event (one is stale, one mis-extracted, or the construct is
time-indexed; `doc_date` is the covariate that lets recency enter the likelihood rather
than a rank heuristic). Documents whose projection is absent or unclear contribute
through the indeterminacy term — the coverage contract's *indeterminate* set (engine §5)
re-derived as "the instrument returned ⊥", a likelihood statement instead of a footnote.

**4.3 The selection term for lookup.** Weak by argument: a point fact is present-or-not
in the retrieved set; missing evidence widens the "none of the retrieved" mass rather
than biasing among candidates. The posterior's honest output for a dispersed mixture is
exactly the abstain/hedge decision. (For aggregates the term dominates — §5.)

**4.4 Utility v0 — preferences as constants, beliefs as priors.** The line is
principled: **utilities are preferences and may be elicited as constants** — they are
the owner's to set, not the world's to reveal; **beliefs about the world may not be
point-pinned**. The preference side is the explicit owner-set table under
`$LIFE_AGENT_KB` (values are personal data, PRINCIPLES §12): u(correct report), u(wrong
report), u(abstain), u(hedged report), u(interruption | owner state), and a per-claim
attention cost (it prices rendering inclusion, §3). Versioned; consulted via `optimise`. The belief side of pricing a clarifying ask is held as **wide
priors over latents, not constants**: owner-as-oracle reliability (a Beta prior,
conditioned on clarify-interaction outcomes — did the answer in fact resolve V?) and
owner availability (a latent with a wide prior; context covariates — hour, focus state —
are named successors, not v0 machinery). Provisional-as-wide-prior, not
provisional-as-constant: `voi` prices the ask in expectation over these latents.
**Explicitly v0 of the goals/utility faculty (PRINCIPLES §15), not its resolution** —
the faculty's real design lands at §12 stage 7.

**4.5 The pipeline** (every stage §18.9 file-first, content-addressed, demand-logged —
the binding invariant of system-design §3 holds unchanged): typed-lookup router →
retrieve (selection recorded) → demand observations per hit → condition in credence
(§11) → `optimise` (response and per-claim inclusion, §3) → render + conformance audit.

## 5. The aggregate family — derived now, built second

V = Σ g(W) over a latent set ("how much did I spend last year?"). Subsumes old D3: the
planner/operators (template router, `filter`/`agg`) are built as this family's machinery
— re-derived, not duplicated; the deterministic operators survive as δ-after-audit
instruments inside the model. Three components the lookup family does not have:

1. **The selection/recall term (M2, now dominant).** P(relevant document retrieved |
   relevant) with a prior; the retrieved-set denominator (engine §5's composition rule)
   becomes the *observed* count in a capture model rather than the answer's silent
   ceiling. **Completeness priors from known generators**: periodic sources (bank
   statements, payslips) make gaps *detectable* — a missing month is an observation
   about recall, not an unknowable. The registry of generators is small, declared, and
   itself evidence-backed.
2. **The missing-mass posterior.** The answer is P(total | observed addends, recall
   term): a credible interval honestly wider than the summed extractions, reported with
   both readouts (extraction coverage within the retrieved set; recall bounding the
   whole) — the engine §5 contract upgraded from prose caveat to posterior.
3. **Dedup as inference.** "Are these two invoices the same transaction?" is hypothesis
   comparison over latent entity structure with a structure prior — **Occam's first
   formal appearance** (§9): fewer latent entities are preferred exactly insofar as they
   predict the observations. Subsumes CRM open decision #4 (alias dedup) — recorded in
   `crm-architecture-decisions.md` when this lands.

## 6. The thread family — sketch (built third)

Subsumes old D4. `assemble` (deterministic multi-input, the one SPEC shape change — the
engine §10 amendment proceeds unchanged) and `thread_state` are instruments; **membership
recall is the same M2 selection term** in different dress (engine §5's "structural twin"
observation, now literally the same model component). "Awaiting reply?" is a posterior
over a thread-state variable with the member-count and membership-recall terms explicit.

## 7. Narrative subsumption — no path outside the paradigm

Questions outside the formalised families are answered inside the same paradigm, by three
moves:

1. **Claim decomposition; proposal/scorer split.** The synthesis LLM becomes a
   **proposal distribution**: it proposes atomic claims; it scores nothing. A proposal
   distribution requires no calibration — only the scorer does (guess-and-verify is
   exact when the verifier is sound; here the verifier is itself a calibrated instrument,
   so the result is a posterior, not a verdict). Each proposed claim is scored by the
   common machinery: the deterministic citation audit (exists today —
   `scripts/citation_guard.py`), instrument reliabilities of the cited artifacts, source
   authority.
2. **Population calibration for the residue.** Claims surviving no deterministic check
   carry the monolithic instrument's error model: P(correct | observable signals —
   retrieval strength, audit outcome, question shape), calibrated on the eval corpus
   (§8), with a hierarchical prior so out-of-distribution questions get honestly *wider*
   credences, never misplaced confidence.
3. **The proposal-coverage term — M3's approximation content, named and load-bearing.**
   A proposal distribution needs no calibration for *what it proposes*; its **recall**
   over true claims is another matter. An unmodelled selection channel is exactly the
   defect M2 exists to prevent, and the narrative path gets no exemption: the claim-set
   posterior carries a "claims not proposed" component — the twin of §4.2's "none of
   the retrieved". This term is the system's *only* defense of §9's no-hard-zeros rule
   (excluded hypotheses route here, so global open support lives or dies on it), and it
   must therefore be a proper **open-world tail** — missing-mass machinery of the §5(2)
   kind over the unproposed claim space — never a finite residual bucket that
   renormalisation can starve. Its estimation route is named now because no evidence
   stream can be backfilled: graders match labeled answers against proposals *at claim
   level*, so a proposer miss is an observable event in the outcomes log (§8 grader 1,
   instrumented in slices 0 and 3), with owner corrections the grader of last resort.
   Wide coverage priors mean narrative answers honestly hedge toward "this may be
   incomplete" until evidence narrows them.

The old pipeline therefore ceases to exist *as a separate paradigm* on the day slice 3
lands: it is the widest instrument inside this one, and the EU layer is free to abstain
on its wide credences. **Which family to formalise next is itself an EU calculation**:
demand (plan-key frequency, D0 logs) × the monolithic instrument's calibrated error on
that question shape = the expected gain of formalisation. Even roadmap prioritisation is
decision-theoretic (§12).

## 8. Calibration — the empirical leg

**The outcomes log** — the third evidence stream, append-only. Its primacy (slice 0,
before anything else) is not a constitutional carve-out but **the frame's first output**,
and the derivation runs through option value, not instantaneous VOI (an empty log's
immediate VOI is near zero — the naive reading gets the sign wrong): the decision is
*when to start logging*; delay destroys evidence irreversibly (a stream, unlike a model,
cannot be backfilled); and the option value of the stream is greatest while uncertainty
about our own calibration is maximal — which is exactly t = 0. Irreversibility × maximal
self-uncertainty × negligible cost: the EU calculation does itself:

    $LIFE_AGENT_KB/calibration/outcomes.jsonl
    (tx_time, instrument_identity {schema-3 key components}, construct, claim,
     grade, grader, question_id, lineage_keys, format_version)

Three graders feed it:

1. **The eval harness** — `scripts/run_eval.py` (answer-grounded; modes
   PASS/RETRIEVAL_MISS/ABSENT_*; the `--synthesis` judge) extended to (a) score
   posteriors with **proper scoring rules** (log score primary — proper and local; Brier
   secondary; reliability diagrams per family), (b) write outcomes with per-claim
   lineage attribution (answers already record §18.9 stages; the lineage walk exists),
   and (c) match labeled answers against proposed claim sets *at claim level*, so a
   proposer miss is an observable outcome — the estimation route for the
   proposal-coverage term (§7(3)), without which it is declared but unestimable.
2. **Spot-check audits** — sampled verification of instrument outputs against source
   bytes. v0 policy: stratified by instrument × construct, stated in config — with the
   strata deliberately **overweighting the monolithic instrument**: §9's open-world
   guarantee rests on the system's *least-calibratable* component (residue questions
   yield the least ground truth), so the most outcome budget flows there, inverting the
   instinct to spend it on the typed families. VOI-scheduled selection is a named
   successor (§12 stage 4) — metareasoning eating its own tail, properly — and will
   re-derive exactly that inversion (audit VOI is highest where posteriors are widest
   and load-bearing).
3. **Owner corrections** — a wrong fact flagged in any reach surface becomes an outcome
   event (the grader of last resort and the only one that catches construct drift in the
   wild). One flag, several possible causes — instrument error, proposal-coverage miss,
   the inclusion decision, presentation, construct drift — so **attribution is itself
   inference, never a label**, and it runs in two stages, each inside the contract.
   First the **matcher**: pairing a free-form correction ("no, it's Tuesday") with the
   claim it contradicts is an inference with its own error model, not a deterministic
   route — and it sits at the root of the calibration leg, where a mis-match poisons
   the very reliability posteriors calibration exists to protect. The matcher is
   therefore declared an instrument (§2, grounded-extraction class: it must quote the
   correction and cite the claim id it pairs with; a correction it cannot ground stays
   an *unrouted* outcome held at answer level, never mis-assigned), with its own
   reliability posterior and audit stratum — no exempt edge writes the one stream that
   grounds everything. Then the **routing**, deterministic given a grounded match: in
   the claim set but wrong → instrument or construct; absent from the proposals →
   coverage; proposed but withheld → the inclusion decision answers for it; decided but
   misrendered → presentation. The residual ambiguity (instrument vs construct) is held
   as a soft posterior over the lineage edges — mass spread where indeterminate, never
   assigned by fiat on the system's only in-the-wild grader.

Conjugate updates throughout (Beta for binary correctness, Dirichlet for confusion
matrices) so small-n behaves honestly: priors stated, posteriors wide until evidence
arrives. **The gate for Ask v0** (§12 stage 1) is **decision-weighted, because adoption
is an action, not a hypothesis test — and the comparison is itself Bayesian**, because
two corpus-mean EUs are noisy estimates and the corpus is sparsest exactly when the gate
first runs. From per-question utility outcomes under the v0 table (§4.4) we hold a
posterior over the EU gap Δ = EU(typed) − EU(monolithic); the gate is **P(Δ > δ) at or
above a stated level**, with the materiality margin δ and the level frozen in the gate's
definition alongside the table — never a point "≥" on two noisy means. The disagreement
region — questions where the two policies choose different actions (tails, abstentions,
confident errors) — is examined explicitly, since a system can lose on mean log score
yet win exactly where the action changes, and a raw-score gate would reject it wrongly.
A decision-weighted gate puts the utility table *inside* the gate, where a timid table
(abstention priced high) passes by abstaining everywhere — and reliability diagrams
cannot catch that, since they only score claims actually made. Three defenses, none of
them a bright line: the table is **frozen before any gate result is seen** (the
blind-comparison discipline extended to the table itself); the gap posterior is reported
across a **stated range of plausible tables**, with adoption expected to hold across the
range rather than at one point (adoption is a choice under utility uncertainty; the
range's width is itself a stated choice — an open question, §14); and the **answer rate
is published** as a named diagnostic.
A hard answer-rate floor is declined on this document's own grounds — a structural
constraint where a priced quantity belongs. Log score (proper and local) and Brier
remain the published diagnostics, with reliability diagrams per family, under
`$LIFE_AGENT_KB/eval/` — the blind-comparison discipline (`SPEC-comparison.md`
precedent) applied to ourselves again.

## 9. Occam's razor — where simplicity formally lives

Three appearances, in order of arrival:

1. **Structure priors over latent entities** (§5 dedup): fewer entities preferred
   exactly insofar as they predict observations. Arrives with the aggregate family.
2. **Structure-BMA over feature relevance** in decision models (which covariates drive
   an outcome) — credence's sparse structure-BMA, proven in credence-pi. Arrives with
   the standing EU decisions (§12 stage 4).
3. **Complexity priors over schema/taxonomy space** — the full form: which projections
   *should exist at all* is a posterior over schema programs, complexity-weighted
   (credence `program_space`: `Grammar`, `enumerate_programs`, complexity prior),
   scored by predictive success on the calibration corpus. This is engine §13's "organic
   taxonomy emergence" escape hatch, given its formal home. **Trigger**: a calibration
   corpus rich enough to score schemas, plus demand evidence of taxonomy misfit
   (recurring construct-validity failures, §2).

Until then, **Occam v0 is procedural and stated as a prior choice, not an omission**:
smallest closed enum that supports the demanded predicate; AND-only predicate slots
(engine §8's fence); reuse measured by node-key demand (engine §9.3). The procedural
rules stand in for the mode of the formal prior we cannot yet compute — with one rule
that keeps the narrowness honest: **no hard zeros at the system level**. An instrument
or family may be narrow (AND-only puts zero mass on OR-hypotheses *within the typed
family*), but only because a wider instrument carries the residual mass: a query the
typed plan cannot express routes to the proposal path (§7), whose monolithic instrument
is precisely the ε-mass over the typed family's excluded hypothesis space, and the miss
is logged as demand evidence for extending the family. What the rule buys must be stated
exactly: **non-overconfidence, not coverage**. The proposer's recall is finite (§7(3)),
so a question whose true claim neither the typed family nor the proposer generates can
still go unanswered — but the truth never takes a hard zero: its mass flows to the
open-world tail, and the EU layer abstains or hedges instead of confidently erring.
"Never falsely confident by construction", not "always answerable". A structural
exclusion is a coverage statement about one instrument, never a prior over the answer
path. This rule and §7(3) are one mechanism, and the dependence
is load-bearing: no-hard-zeros holds *only while* the proposal path's coverage term
keeps true open support — which is why that term is specified as an open-world tail and
its grading instrumented before anything else is built (§7, §8).

## 10. Metareasoning — which transforms to run, and when

Russell–Wefald (already cited at engine §0): a computation is an action priced by its
expected value. The questions "which transforms do we want to run?" and "when?" decompose:

- **Which exist** (define): instruments earn existence by a demanded hypothesis family
  (§1) and a calibratable error model (§2); they earn retention by reuse (node-key
  demand) and calibration (posterior not degrading). `entity_extraction` — the one
  in-tree transform with no current family — is re-justified or shelved under this
  contract when slice 2 lands.
- **When they run** (execute): **demand-led lazy scheduling is the optimal v0 policy
  under the stated cost model** — derivation cost is paid at most once (content-addressed
  cache), value realises only when a question (later: a decision) consumes the result, so
  computing without demand has zero expected value unless latency matters; prefetch/sweep
  is justified only when batch cost < expected demand × latency saving — which is the
  governor's calculation, deferred with it.
- **The accounting locked now, by the frame's own arithmetic** (§8: an evidence stream's
  option value is greatest at t = 0, and it cannot be backfilled): cost + reuse (D0 demand logs,
  plan-key vs node-key, landed) and correctness (the §8 outcomes log, slice 0). The
  governor (§12 stage 6) consumes all three; PRINCIPLES §16's "deliberately last" stands.

## 11. The credence seam

`src/life_agent/core/brain.py`: a thin client over credence's **skin** — JSON-RPC 2.0
over stdio (`julia --project=$CREDENCE_REPO $CREDENCE_REPO/apps/skin/server.jl`;
protocol: `../credence/apps/skin/protocol.md`; `create_state` / `condition` / `expect` /
`call_dsl`; opaque state handles; conjugate families incl. beta, categorical, dirichlet,
product, mixture, program_space). Language-neutral, so it passes the PRINCIPLES §5 seam
diagnostic; zero new Python dependencies; Julia start-up (~seconds) is acceptable for
timer/batch/REPL use; promotion to an always-on HTTP daemon (credence-pi shape,
Tailscale-only per PRINCIPLES §13) is named for the always-on phase, behind the same
client API. Hermetic tests stub the subprocess.

The mapping (the L2 functor, engine §0, now concrete):

| life-agent concept | credence object |
|---|---|
| transform / operator / verifier (an edge) | `Kernel` (+ declared likelihood family) |
| instrument reliability | `BetaPrevision` / `DirichletPrevision` (conjugate) |
| belief over V | `Prevision` over the construct's `Space` |
| conditioning on an observation / outcome | `condition` (the only learning mechanism) |
| answer credence, expectations | `expect` |
| response choice (report/hedge/ask/abstain) | `optimise` over the action space |
| clarifying-question pricing | `voi` |
| structure priors / schema learning (§9) | structure-BMA / `program_space` |

## 12. Roadmap — from here to the asymptote

The asymptote (PRINCIPLES §16) is unchanged: *believing, computing, and acting are the
same move, scheduled by value of information, over an immutable log whose only invariant
is that truth is the fold.* What changes is the middle of the geodesic: confidence is no
longer an annotation added later but the output type of Ask, built now. Each stage names
its gate and what part of the asymptote it discharges.

| Stage | Builds | Gate | Asymptote part discharged |
|---|---|---|---|
| **0** | This document conferred (pixel6) + owner-adopted; §13 deltas applied | owner approval | the constitution |
| **1 — Ask v0** | Slice 0: outcomes log + scoring-rule eval (first — the t=0 option-value argument, §8). Slice 1: the credence seam (§11). Slice 2: lookup family (§4). Slice 3: narrative subsumption (§7) | §8 gate (decision-weighted, Bayesian comparison): P(EU gap > stated margin) ≥ stated level across the table range, disagreement region examined; log-score/Brier diagnostics + reliability diagrams published; double-run idempotency; pytest/ruff/mypy green | believing = computing, for point facts; honest abstention |
| **2 — Aggregate family** | recall term + completeness priors, missing-mass posterior, dedup-as-inference (§5); subsumes D3 | the spending question answered as a posterior with both coverage readouts; structure prior resolves a real duplicate pair | Occam appearance 1; M2 in full |
| **3 — Thread family** | `assemble` SPEC amendment (engine §10), `thread_state` instrument (§6); subsumes D4 | "awaiting reply?" green with membership-recall term; reclassification budget honoured (engine §11 D4) | the last fixed-pipeline failure family |
| **4 — Standing EU decisions #2–#3** | email→GTD filing governor (file/skip/ask on `optimise`+`voi`; beliefs conditioned on ledger disposal outcomes — `commands.complete`/`delete` dispose with reasons `done`/`dropped`; includes wiring the absent `mail-to-tasks` timer) · VOI-scheduled audit sampling (§8) | filing decisions logged with posteriors; ask-rate falls as posteriors sharpen; audit VOI beats stratified on calibration-per-audit | acting joins the move; the interruption cost gets measured (engine §13's placeholder, retired) |
| **5 — Structure learning** | `program_space` complexity priors over schemas/taxonomies (§9 appearance 3) | a schema revision proposed by posterior, validated on the eval corpus | the hypothesis-space distribution; Occam in full |
| **6 — The unified VOI governor (L3)** | one queue over derive / audit / ask / act — now permitted (≥3 concrete EU implementations: §4.4 response, stage-4 filing, stage-4 audits) and calibratable (cost + demand + outcomes, §10) | governor decisions beat demand-only scheduling on measured utility | *scheduled by value of information* — the asymptote's verb |
| **7 — Goals/utility + bounded action** | the real goals/utility faculty (replaces the v0 table; PRINCIPLES §15) → outward write-actions (email drafts, calendar) under ask/proceed/block; the spine decision lands here, unchanged | no autonomous write-action before the utility model (PRINCIPLES §3) — the standing constraint | acting in the world; the loop closes at L4→L0 |

Stages 2–7 are dependency-ordered, not timed; each is independently valuable; gates are
eval-gated per the amended PRINCIPLES §9. Re-prioritisation within the order is itself
the §7 EU calculation once stage 1's calibration data exists.

**The write-action line, drawn now because stage 6 will lean on it.** Stage 4's filing
governor writes the GTD ledger under the v0 utility table, which sits next to "no
autonomous write-action before the utility model" (PRINCIPLES §3, stage 7's gate). The
line is **internal bookkeeping vs outward action**: a ledger append is
act-layer-internal — append-only, reversible by a later event, surfaced for owner triage
in reach — so it runs under the v0 table; outward actions (email, calendar — anything a
third party can observe, or that appending cannot undo) wait for stage 7's real utility
model. The stage-6 governor inherits this line as stated, not as folklore.

## 13. Governance deltas (applied on adoption, not before)

- **PRINCIPLES §16**: the geodesic's middle leg re-scoped — *query-with-confidence* is
  not a successor annotation but the Bayesian re-derivation of Ask, executing now; the
  VOI governor remains deliberately last. §14 gains the adoption line for this document.
- **ROADMAP / system-design.md**: Phase 1.6's D3–D4 re-scoped as Ask v0's aggregate and
  thread families (§5–§6); the component map's `../credence` row flips from "reference
  material; unwired" to "wired — the skin seam (§11)".
- **interaction-contract.md**: one new section — the credence-rendering grammar
  (credence named, hedges, abstention reasons, posterior intervals, withheld-claim
  counts with their EU reasons (§3); one grammar, every surface).
- **`docs/crm-architecture-decisions.md`**: decision #4 (alias dedup) resolved by
  §5(3) — dedup as inference — when stage 2 lands.
- **pkm SPEC: untouched.** pkm core, producers, transforms, the GTD ledger, and reach
  are unchanged by Ask v0. All new artifacts (claim sets, posteriors, plans) are §18.9
  external derivations with new content types, excluded from chunking as today. The one
  later SPEC change remains engine §10's `assemble` (stage 3).

## 14. Recorded counterarguments and open questions

**The confer round (second expert, 2026-06-12) — findings and dispositions.** The
review's diagnosis was accepted in full: six instances of one defect — *a decision
encoded as a structural constraint rather than a priced, updatable quantity* — plus a
re-taxonomy of the four moves and one vindication. All dispositions are folded into the
sections they name: the anti-heuristic rule derived rather than posited (§0);
shared-model lineage independence replaced by stated likelihood tempering (§2); the
adoption gate made decision-weighted (§8, §12); the renderer given the full edge
contract (§3); structural exclusions bounded by the system-level no-hard-zeros rule
(§9); oracle and availability constants replaced by wide priors over latents (§4.4);
the proposal-coverage gap named as M3's approximation content (§1, §7); slice-0 primacy
restated as the frame's first output (§8, §10). One refinement adopted over the review's
letter: **utilities are preferences and may remain elicited constants — only beliefs
about the world are barred from being point-pinned** (§4.4). Untouched, per the review:
the credence seam, M2-as-posterior, calibration-as-logging, the falsifiable spirit.

**The confer round, second pass (2026-06-12) — findings and dispositions.** Two further
reviews of the revised draft. The first opened with the meta-point that a reviewer is an
instrument, not an oracle — agreed and recorded; dispositions are argued findings, and
this pass declines one sub-remedy to hold that posterior. Accepted: rendering
*inclusion* re-derived as a per-claim `optimise` decision under an attention utility,
the guard re-scoped to conformance against the decided set (§3); the §9/§7(3) coupling
stated as load-bearing, the coverage term specified as an open-world tail with its
claim-level grading instrumentation named before build (§7, §8, §9); lineage tempering
keyed on shared ancestry as well as shared model, with exact DAG-aware composition
named (§2) — and the temper **run against the flagship family it had skipped**: §4.2's
product now composes under §2's rule, not naively; the fold declared order-defined once
the temper is learned (§2); §9's guarantee weakened to what it actually buys —
non-overconfidence, not coverage; wild owner-corrections given credit assignment as
inference over the lineage, never a label (§8); slice-0 primacy re-derived through
option value, since an empty log's instantaneous VOI is near zero (§8, §10); the gate's
utility table frozen blind, EU reported across a stated table range, answer rate
published (§8); the audit budget inverted toward the monolithic instrument (§8); the
bounded-utility dependence of the §0 invariant named (§0); the internal-vs-outward
write-action line drawn for stage 4 and inherited by stage 6 (§12). Declined, on this
document's own grounds: a hard answer-rate floor — a structural constraint where a
priced quantity belongs (§8's three defenses are the priced alternative).

**The confer round, final pass (2026-06-12) — convergence.** The reviewer's verdict,
recorded with its reasoning adopted: the findings form a converging series (six
structural, six self-application, then two refinements and two nitpicks), and the VOI of
a further full round has dropped below its cost — review ends by the document's own
arithmetic; what remains is open-questions territory, decided by evidence. The two final
refinements, accepted: the gate's *comparison* made Bayesian — a posterior over the EU
gap with a stated materiality margin and level, never a point inequality on two noisy
corpus means; the objective had been converted two rounds earlier, the comparison had
not (§8, §12) — and the owner-correction matcher declared an instrument
(grounded-extraction class) rather than an exempt deterministic route at the root of the
calibration leg (§8). The two nitpicks, folded: per-claim inclusion named as the
marginal approximation to joint subset selection (§3); the table range's width added to
the open questions below. The declined answer-rate floor was endorsed in this pass.

**Counterarguments, recorded with answers:**

- *"This is confidence decoration on a working pipeline — complexity without new
  answers."* The open failure families are precisely failures of uncalibrated implicit
  inference: conflicting evidence resolved by rank (F2), aggregates silently bounded by
  recall (F1), abstention thresholds unprincipled (engine §13). And the claim is
  falsifiable by construction: if stage 1's decision-weighted gate (§8) shows the typed
  family does not beat the monolithic instrument, that result is published and the
  design answers for it.
- *"The error models are themselves models — turtles all the way down."* Yes, and the
  regress is cut explicitly (§2: audited-code priors) and empirically (§8: end-to-end
  scoring catches mis-modelling wherever it hides). The alternative — implicit total
  trust in every edge — is the same turtle stack with the priors hidden at 1.0.
- *"Julia in the loop is operational weight."* One subprocess behind a §5 seam, stdlib
  JSON-RPC, no Python deps; the heaviest alternative (in-process juliacall) was
  rejected *because* it fails the seam test.

**Open questions — the ledger of what we don't know** (owner's adoption rider,
2026-06-12, binding): every entry names the evidence that will decide it and the stage
where that evidence first exists; an entry without a named evidence stream may not stay
on this list. Answers land here by amendment, citing their evidence.

- **Source-authority priors (§4.1).** Unknown: how fast outcomes move the v0 class
  lattice, and whether authority is per-sender rather than per-kind. *Decided by* lookup
  outcomes attributed to authority covariates. *First evidence:* stage 1 (slice 0 log +
  slice 2 answers).
- **Lineage dependence (§2).** Unknown: the tempering exponent's posterior, and the
  calibration volume at which the shared-model hierarchical hyperprior earns its
  complexity. *Decided by* audit outcomes on shared-model / shared-ancestor lineages
  compared with independent ones. *First evidence:* stage 1 audits (§8 grader 2).
- **Proposal-coverage data rate (§7(3)).** Unknown: whether proposer-miss events accrue
  fast enough to narrow the coverage prior — the tail is load-bearing (§9), and residue
  questions yield the least ground truth. *Decided by* the claim-level miss count in the
  outcomes log. *First evidence:* stage 1. If starved, the priced response is shifting
  more audit budget to the monolithic stratum (§8), not a redesign.
- **Utility elicitation (§4.4).** Unknown: direct numbers vs revealed preference.
  *Decided by* stage 4's filing governor — the first revealed-preference stream —
  checked against the elicited table's predictions.
- **Temporal indexing of constructs (§4.2).** Unknown: when "current value" semantics
  needs valid-time inference rather than the recency covariate. *Decided by* corrections
  where the cited document was right *for its era* — recurring construct-validity
  failures of that shape are the trigger. *First evidence:* stage 1 outcomes.
- **The gate's table range (§8).** Unknown: the width of "plausible", a stated choice
  doing quiet work. *Decided by* stage 4's revealed-preference data. Until then: stated
  and frozen with the gate.
- **The skin's batch throughput (§11).** Unknown: per-question subprocess vs pooled
  daemon. *Decided by* latency measured at stage 1; promoted per §11 if it demands.
