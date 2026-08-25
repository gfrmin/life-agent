# Bayesian foundations — the epistemics of the knowledge layer, and Ask derived as inference

> **Status: ADOPTED (2026-06-12, owner-approved).** Deliberated the same day through the
> owner's frozen-layer practice: self-review → second-expert confer via pixel6 (four
> passes to convergence — findings and dispositions in §14) → owner approval, given with
> one rider, binding: **§14's open questions are a live ledger of what we still don't
> know, each answered empirically** — every entry names the evidence that decides it and
> the stage where that evidence first exists. The §13 governance deltas are applied; the
> build slices are unblocked.
>
> **Amendment (2026-06-12, owner-directed; conferred same day, residuals folded — §14):
> §4.4 and §10 — utility as inference, one utility.** The utility function becomes a
> posterior learned from the owner's behaviour (elicitation demoted to evidence), and
> metareasoning is denominated in that one utility — the agent has none of its own.
> Owner approval gates the slice-2 build.
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
free: this invariant keeps EU well-defined only under **bounded utilities** — discharged
in v0 by construction (§4.4: the grid-discretised utility posterior bounds U outright);
if stage 7's goals faculty (§12) introduces unbounded utilities, a maximally wide error
model no longer yields a finite, comparable EU, and the invariant must be revisited
together with it.

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
  `optimise(posterior, {report, hedge, ask-clarify, abstain}, utility)` under the §4.4
  utility posterior's mean (utility is itself a learned belief about the owner — §4.4).
  Whether the whole construction works is an empirical question answered by measurement
  (§8 — decision-weighted gates, proper-scoring diagnostics), never by fiat.

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
   `optimise` under a relevance/attention utility (the attention cost κ_att is a §4.4
   latent). Named approximation, per §0's own rule: per-claim selection is the marginal,
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

**4.4 Utility v0 — the utility posterior (owner directive, 2026-06-12).** The round-2
disposition drew the line at "utilities are preferences and may be elicited as
constants". The owner overrode it, completing the reviewer's original finding rather
than refining it: the *truth* is the owner's preferences — normative authority stays
his — but the **agent's representation of them is a belief about him**, and beliefs may
not be point-pinned. So the utility function is a latent like any other: a posterior,
learned chiefly by observing behaviour, with elicitation demoted from definition to
**evidence**.

**Not imitation.** "Learn my utility from my behaviour" is not "predict what I would
do". Behaviour is *noisy evidence of* preference, read through a rationality temperature
τ: the owner usually chooses what he prefers — not always (tired, rushed, options
unseen). Inference inverts that channel to recover the *why*; the agent then applies the
why with **its own information and options** — sometimes doing what the owner wouldn't
have done but would endorse (it knows its two sources conflict; he doesn't). Where
information, options, and deliberateness coincide, the EU-maximising action *is* what he
would do: that special case is the training signal, never the target. (Revealed
preference / inverse decision theory — deliberately not behavioural cloning, which fails
exactly where the agent's action sets stop resembling the owner's history.)

**The collapse theorem, stated so deference is honest.** For a one-shot decision,
expected utility under utility uncertainty collapses to EU under the posterior mean:
max_a E_U[EU_a(U)] = max_a EU_a(Ū). Posterior *width* does not make a myopic decision
cautious — claiming it does would smuggle in a non-vNM risk posture over U, declined.
Where width genuinely matters, exactly: (i) the **value of learning U**, which is
dominantly *sequential* — a preference answer conditions every future decision, so its
worth is priced by the governor (§12 stage 6), never by any one response; (ii) the
**gate** (§8 — adoption integrates over P(U)). v0 caution comes from conservative prior
*means*, stated as such.

**Utility learning is passive until the governor — a stated action-set coarsening.**
The §3 response set contains ask-clarify *about V*; it deliberately does not contain
ask-about-U. Precision about why, because the obvious argument is wrong: the collapse
theorem does *not* zero the myopic VOI of a preference-ask — ask-then-decide is
available within one episode, and E_answer[max_a EU_a(Ū_answer)] ≥ max_a EU_a(Ū),
strictly whenever an answer could flip the action. The honest grounds are different:
(a) a preference answer's value is overwhelmingly sequential — it is shared across all
future decisions — so pricing it inside one response *misprices* it, and correct
pricing needs the governor's horizon; (b) U-width is rarely pivotal for a single lookup
(V-width is — that is why the question was asked), so the myopic component alone seldom
clears λ_int. Excluding ask-about-U from the myopic action set is therefore a **named
approximation** (an action-set coarsening, per §0's own rule), revisited when the
governor lands. Until then utility learning is **passive only**: streams 2–6 as
behaviour arrives, plus owner-initiated elicitation (stream 1) — which is also why the
verdict-stream evidence rate is the right §14 worry.

**Gauge.** Behaviour identifies utility only up to positive affine transform, so two
pins are convention, never estimate: u(correct report) = +1, u(abstain) = 0. The
latents, learned in those units (v0 lookup scope): u(wrong report), u(hedged report),
the interruption cost λ_int, the per-claim attention cost κ_att (it prices rendering
inclusion, §3), and τ (hierarchical — how noisily behaviour reflects preference).
Priors are soft-signed — u(wrong) holds its mass below zero with no hard truncation
(§9's no-hard-zeros, self-applied: evidence could reveal a regime where the owner
prefers a wrong guess to silence, and the model must be able to say so). Priors and
gauge live at `$LIFE_AGENT_KB/utility/model.yaml`, versioned (values are personal data,
PRINCIPLES §12).

**Evidence streams — preference instruments under the §2 contract** (each an
observation model with an error model, like every other edge):

1. **Elicitation as evidence**: a stated number or ratio conditions the posterior under
   a generous noise likelihood (`$LIFE_AGENT_KB/utility/elicitations.jsonl`,
   append-only). Zero elicitations is a working state — the prior carries v0 and
   behaviour does the rest.
2. **ask-live verdicts** (the existing g/b capture): a logistic likelihood on the
   realised response's utility.
3. **Owner corrections** (§8 grader 3): effort-bounded evidence on |u(wrong)| — he
   corrects when the error mattered.
4. **Clarify-ask reactions** (answered / ignored / latency): logit choice evidence on
   λ_int — joining the oracle-reliability and availability latents already held as wide
   priors for pricing the ask (Beta on "did the answer resolve V"; availability with
   context covariates as successors).
5. **Re-asks after an abstention**: evidence the abstention under-delivered.
6. **GTD disposals** (§12 stage 4's filing governor): the same machinery, later.

All are discrete-choice (random-utility) observations, and the conditioning route exists
in the skin today: grid-discretised latents (a product of categoricals) conditioned
through `tabular_log_density` kernels, `plackett_luce` where the observation is a choice
among ranked options — no new Julia. **A grid is a truncation**, so the soft-sign claim
above is stated exactly: no hard zero *within* bounds chosen wide enough that endpoint
mass stays negligible, with endpoint mass monitored — mass piling at an edge means the
grid is clipping the posterior, and the remedy is widening, never renormalising. The
finite grid is also what *discharges* §0's bounded-utility dependence: U is bounded by
construction, not by assertion.

**Identification, honestly.** The **preference-evidence selection channel** is M2 on
this stream: the owner reacts only to what the policy chose to surface — named now, with
its promotion trigger and the grounds for deferring it stated in the reaction loop below.
**τ and U are non-identifiable from choice data in principle** (Armstrong–Mindermann)
*in generic IRL, where the rationality model is unobserved*: there no volume of behaviour
separates "he prefers this" from "he errs this way", and the hierarchical τ-prior does the
separating. The reaction loop below is **not** generic IRL — its cut-points are
**exogenous**: the agent's own credence `p` sets each verdict's threshold `−p/(1−p)`, not
the owner's preference, and exogenous cut-point variation is exactly what separates slope
(τ) from location (u(wrong)). So the τ-prior does *permanent* separating work only in the
**clustered-threshold regime** (all `p` alike → all thresholds alike → only a bound on
u(wrong)); with `p` *spread*, the verdicts bracket u(wrong) and recover τ from the curve.
Threshold spread is therefore an identification lever the design can engineer — do not
clamp the lookup family to a narrow credence band. Corrections are partially observed (he
corrects the errors he *sees*); preferences drift and depend on context — non-stationarity
and context covariates are §12 stage 7's, with the trigger stated: systematic disagreement
between the posterior's predictions and fresh behaviour.

**The reaction loop — the concrete mechanism (v0: the verdict stream).** Streams 2–6
share one shape, because *every agent action is already a logged EU choice and the
owner's reaction to it is a discrete-choice observation about U*. The loop is a fold,
parallel to the outcomes and decision logs:

    reactions.jsonl  ⋈(question_id)  decisions.jsonl  →  Reaction events  →  the posterior fold

- **The reaction log** — the calibration leg's third append-only log beside outcomes and
  decisions, `$LIFE_AGENT_KB/calibration/reactions.jsonl`, under the same discipline (file
  order is the canonical replay order; a closed `kind`/`valence` vocabulary raises on junk;
  durable append; unbackfillable, so it lands now). One line is
  `(tx_time, question_id, decision_id, kind, valence)`; v0 carries `kind = verdict`,
  `valence ∈ {good, bad}` from the ask-live g/b capture. **The verdict is one bit** — no
  free-text note. The loop's only expensive resource is the owner's prose, so it is never
  elicited: cheap auto-measurement (the decision, its held-back candidates, the posterior) is
  unconstrained and already logged, and only the *elicitation* is rationed. A richer signal
  (e.g. the which-claim disambiguator below) must therefore be auto-derived or elicited
  cheaply (a bit per claim), never typed — so the earlier nullable-`reason` slot was retired
  (the append-only reader drops the legacy key). The vocabulary grows by edit as the later
  streams land (`correction`, `reask`, `clarify_reaction`, `disposal`).
  **The join is on a per-decision `decision_id`, not `question_id`.** `question_id =
  sha(question)` is not unique across runs (re-asks are stream 5, designed in), and a
  within-session re-ask is itself a *new* decision — new retrieval, new posterior, new `p` —
  that must carry a different id, because the verdict binds to the exact decision whose `p`
  and action set its threshold. `run_id` is the wrong field to overload: it is per-*run* on
  the eval path (one id across a run's questions), so making it per-decision on the ask-live
  path would give one field two cardinalities depending on who wrote it — the
  silent-contract divergence the discipline disowns. So the decision log mints a
  **per-decision `decision_id`** (the answer's §18.9 cache key serves — content-addressed,
  so two *truly identical* decisions coalesce to one id and one threshold, which is correct),
  the verdict carries it, and the join is on it. Unbackfillable *on the decision side*: a
  decision logged without it orphans the scarce early reactions forever, so it lands before
  the first reaction. (Latency-delta and lineage keys stay *off* the row — both fall out of
  the join and the two `tx_time`s.) **Supersession, not accumulation:** the owner may revise
  a verdict (`good` then `bad`) or fire two valences on one answer; the order-defined fold
  takes the **latest verdict per `(decision_id, kind)`** (last-write-wins), so one decision
  contributes one threshold observation — the "disjoint, not double-counted" guarantee the
  sign table rests on holds *at the fold*, not merely per appended row.

- **The reading is inverse decision theory, not a label.** A verdict alone is valence; it
  becomes evidence only against *the decision it grades* — what the agent chose, and at
  what credence. For a lookup decision the agent reported iff
  `EU(report) = p·u(correct) + (1−p)·u(wrong) > 0` (and beat hedge/clarify), where `p` is
  the MAP candidate's posterior weight recorded in the decision's posterior summary. So
  the report/abstain boundary sits at a **credence-implied indifference point**,
  `u(wrong)*(p) = −p/(1−p)`, and each verdict is a *soft (τ-smoothed) threshold
  observation on `u(wrong)` located there*, oriented by (verdict, action):

  | verdict | action @ credence p | reads as | moves u(wrong) |
  |---|---|---|---|
  | **bad** | report | the confident report was unwelcome/wrong | **below −p/(1−p)** (the "confidently-wrong is a no-no" signal) |
  | good | report | reporting at p was endorsed | above −p/(1−p) (corroborates) |
  | **good** | abstain | "glad you didn't guess" — a report would have been net-negative | **below −p/(1−p)** |
  | bad | abstain | "I wanted an answer" — silence under-delivered | above −p/(1−p) |

  Each row is one `Reaction(latent="u_wrong", sign, threshold)` through the existing
  `reaction_probability` kernel, the threshold computed from `p` — the sign table above is
  exact (a verdict on an abstention cannot co-fire with its opposite, so the two
  "u(wrong)-up/down" pressures are disjoint, not double-counted). **But the report rows
  (1–2) are contaminated and the abstain rows (3–4) are clean, and the difference is
  load-bearing.** A `bad` on a *report* can mean (a) wrong value, (b) right value / wrong
  *subject*, or (c) "I didn't want a report at all" — readings (b) and (c) belong to *other
  latents* (the subject instrument's construct validity; λ_int / relevance), and **τ cannot
  launder them onto u(wrong)**: τ tempers magnitude on the modelled axis, it does not
  reassign attribution across latents. Worse, the contamination is **signed and
  gate-favourable** — (b) and (c) both push u(wrong) more negative, which makes the typed
  family abstain more and the gate's Δ rise, so a fold fed raw report-verdicts would
  manufacture *adoption-direction* evidence out of misread verdicts (the
  observation-model-from-messages hazard). The abstain rows carry no such *cross-latent*
  confound: nothing was reported, so there is no wrong value or wrong subject to mistake for
  a preference — a `good`/`bad` on an abstention is **dominantly** "should you have
  guessed?", which *is* a u(wrong) observation. (Two precisions the confer drew: the
  politeness/noise on any `good` verdict is *within-latent*, exactly what τ absorbs, whereas
  the report rows' defect was *cross-latent*, which τ cannot touch; and the abstain rows'
  faint residual is an abstain-over-*clarify* λ_int signal, second-order, disambiguated by
  the `reason` slot if it bites.) **So v0 conditions the utility fold on the clean abstain
  rows only.**
  Report-verdicts are recorded but not folded until each is routed through the §8 grader-3
  attribution (a wrong-subject `bad` is then an *instrument-failure outcome*, not a u(wrong)
  threshold — excluding it is correct, not lossy); that attribution is the named successor,
  and the `reason` slot is what makes its routing decidable, so that approximation stays
  *falsifiable* on the real rows. Identification does not wait on it — the clean
  abstain-verdicts already bracket u(wrong) through the spread of `−p/(1−p)` across
  questions (next paragraph). Hedge/clarify verdicts (rare; → u(hedged), λ_int) are the
  same shape, later; the **narrative family is multi-latent** — its boundary couples
  u(wrong) and κ_att, folded jointly (§7.1, built 2026-06-14). A verdict whose question never logged a decision (a weak-retrieval
  abstention asserts nothing) joins nothing and is held **unrouted** — never mis-assigned,
  the §8 grader-3 humility reused at the values layer.

- **The fold extends, it does not change.** The utility posterior already folds
  `Evidence = Elicitation | Reaction` and already version-stamps the whole event list, so
  the producer adds the joined `Reaction`s to the same fold; a new verdict moves the
  fold-version, and the ask path and the §8 gate re-read demand-led. Conditioning is the
  skin's existing `tabular_log_density` over the grid latents — no new Julia. Learning
  stays **passive** (above): the agent conditions on verdicts the owner volunteers through
  the frictionless g/b prompt (one bit, no free text); it never probes preferences. The
  human-facing surface is untouched — the verdict simply also emits a structured line.

- **The kernel generalises to a margin functional (narrative, 2026-06-14).** A `Reaction`
  is, in full, a soft observation on the **sign of the EU-margin of the action the owner
  reacted to**: `margin(x) = Σ_l coeffs[l]·x_l − offset`, with
  `P(react=1|x) = Σ_τ w_τ·sigmoid(sign·margin/τ)`. Lookup is the single-latent special case
  (`coeffs={u_wrong:1}`, `offset = threshold`) — its existing form and already-folded
  evidence are **frozen, never re-folded**; the functional is *additive* for the multi-latent
  families. Two commitments fall out and are load-bearing. (i) **Raw, not normalised** — the
  margin is the EU difference in gauge units, so the per-latent informativeness of a verdict
  is automatically `∂EU/∂x_l` (the margin's gradient), the correct weighting: a narrative
  verdict at `p=0.5` genuinely says *less* about u(wrong) (slope `p(1−p)=0.25`) because the
  reliance-squared structure down-weights it there. Normalising by `‖coeffs‖` would erase that;
  normalising by the u(wrong) coefficient (lookup's `−p/(1−p)`) is worse — it blows κ_att's
  coefficient up at extreme `p`. Lookup's threshold form is itself the mild (frozen, ≈1.7× at
  mid-`p`) misspecification — *not* the target to match. (ii) **τ is keyed on event-shape**
  (single-latent-lookup vs joint-narrative), so the two forms' scales never silently
  cross-weight; the hierarchical τ-prior groups on shape. Conditioning is still the skin's
  `tabular_log_density`; multi-latent margins condition a **joint block** — the connected
  components of the latent co-occurrence graph (a latent pair sharing any likelihood term
  shares one joint categorical over the product grid; the product prior is independent — no
  invented correlation; **marginalise to 1-D only at readout, never persist the marginals**,
  or a later event loses the induced correlation and the fold silently reverts to the wrong
  collapse-then-recondition order).

**Resource arguments.** Money, latency, and the owner's attention are *arguments of
this one utility function* — there is no second, agent-owned objective that values them
(§10). λ_int and κ_att are the first two such arguments; compute cost joins when the
governor does.

**Explicitly v0 of the goals/utility faculty (PRINCIPLES §15), not its resolution** —
stage 7 *extends* the posterior (context-dependence, goal structure, drift). It no
longer "replaces a table", because there is no table to replace: there is a belief,
already learning.

**4.5 The pipeline** (every stage §18.9 file-first, content-addressed, demand-logged —
the binding invariant of system-design §3 holds unchanged): typed-lookup router →
retrieve (selection recorded) → demand observations per hit → condition in credence
(§11) → `optimise` (response and per-claim inclusion, §3, under the §4.4 posterior
mean) → render + conformance audit → the decision logged (§8 — never unlogged).

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

**7.1 The narrative reaction fold — (u(wrong), κ_att) jointly (built 2026-06-14, conferred).**
The §4.4 verdict stream folds narrative answers, but the boundary it inverts is multi-latent.
Each claim is included iff `EU(include|p) = p·(p·u(correct) + (1−p)·u(wrong)) − κ_att > 0`
(the reliance-linear labeled-claim model; κ_att the per-claim attention cost), so under the
gauge the **inclusion margin** of a claim at credence `p` is

    g(U) = p·(1−p)·u(wrong) − κ_att + p²        — LINEAR in (u(wrong), κ_att): a *line*.

A narrative `ALL_WITHHELD` abstention (claims proposed, all withheld — *not* `NO_CLAIMS`, a
proposal failure) reacted to at the marginal claim's credence `p_max` is therefore a soft
observation on `sign g(U)`, emitted as `Reaction(coeffs={u_wrong: p_max(1−p_max),
kappa_att: −1}, offset=−p_max², sign=−1, reacted=(valence=="good"))`. This is **κ_att's only
evidence stream** (no other v0 family's decision touches it — temporarily: aggregate/thread
will feed it later). Identification is *lookup pins u(wrong) → the narrative lines pin κ_att*
in the decision-pivotal band (`θ(p)=p(1−p)u(wrong)+p²` spans ≈`[−1.04, 0.06]` at u(wrong)≈−5,
exactly where κ_att flips include/withhold), from the **spread of `p_max`**; κ_att inherits
u(wrong)'s residual width (bounded by `p(1−p)·sd ≤ 0.25·sd`), which the joint fold propagates
correctly. The plug-in alternative (κ_att fixed at its prior) is *actively wrong*: the cut-point
depends on κ_att, so it injects κ_att's error into u(wrong), the gate-pivotal latent.

**The cleanliness inverts from lookup — the load-bearing finding (confer, 2026-06-14).** In
lookup both abstain valences were clean and the *report* rows were deferred. Narrative
`ALL_WITHHELD` proposed claims, so the valences are asymmetric: `good` ("right to withhold the
set") is clean and **one-directional** (pushes the margin down — u(wrong)↓, κ_att↑); `bad`
("I wanted an answer") is contaminated (coverage: the proposer may have missed the wanted claim,
so `p_max` understates it; which-claim: the owner may have wanted a *lower*-credence proposed
claim, so `p_max` is the wrong cut-point; relevance the uniform κ_att doesn't model) and pushes
the margin **up**. So folding the clean valence only — the lookup instinct — is **one-directional
evidence that runs the posterior to the grid edge** (κ_att→top, u(wrong)→bottom), concluding
"abstention is always right" and **passing the gate spuriously**. The contaminated `bad` rows are
therefore the **only counter-pressure** and are structurally essential: **v0 folds both valences.**
The contamination is **anti-gate-favourable** (a spurious `bad` pushes the margin up, making typed
abstain *less* and look more like the monolith, lowering Δ), so its risk is not gate-gaming but
**utility-corruption** (κ_att driven spuriously low → chronic over-inclusion downstream) — which is
why the `bad` rows are cleaned even though they cannot compromise the gate's pass-integrity.

**Cleaning — what ships and what is owed evidence first.** Two cleanings, separated (owner,
2026-06-14): (1) **mandatory in v0 — coverage-gate the `bad` rows.** Fold a `bad`-on-`ALL_WITHHELD`
as counter-pressure only when that question's coverage posterior mean (§7 move 3) clears a stated
bar; below it the "I wanted an answer" is more likely a proposal-recall failure than a utility
complaint, and folding it corrupts κ_att. The `good` rows are **ungated** (endorsing withholding the
*shown* set is valid regardless of what was missed). This filters the *contaminated* `bad` rows
while keeping the genuine counter-pressure, so no runaway; the §4.4 endpoint-mass monitor on the
joint marginals is the detectable backstop if the bar is mis-tuned. (2) **deferred — the which-claim
residual.** A closed-vocabulary reaction reason (which-claim / wanted-more / wanted-more-certain) is
the *successor*, not v0 — because, unlike lookup's destroyed-if-unlogged reason slot, the **free-text
reason is already captured on narrative `bad`**, so the evidence is retained; the which-claim κ_att
mis-location is **bounded** (within the θ-band), **anti-gate-favourable** (no adoption-integrity
risk), and **reversible** (re-parse the retained reasons + refold when the vocab lands). **Promotion
trigger (stated now):** a measured which-claim rate in the retained free-text reasons above a stated
bar, or a gate false-negative diagnosed to which-claim. `NO_CLAIMS` abstentions (no `p_max`) and
narrative *report*-verdicts (the lookup-report attribution successor) are recorded-not-folded.

**The reliance form is fixed, and priced.** `EU(include|p)` bakes in reliance-linear `r(p)=p`;
reliance and u(wrong) are confounded in the margin (both scale the wrong-claim term), so inclusion
verdicts alone cannot separate the *form* — that needs an act-on-a-claim stream (GTD disposals,
corrections, claim-citing re-asks) that does not exist yet. So `r(p)=p` is fixed for v0 and the
reliance-measurement stream named as successor — but the misspecification is **not benign**:
over-reliance (`r>p`, the default human failure with confident-looking output) makes wrong claims
hurt more than the line predicts, pushing u(wrong)↓/κ_att↑, both **gate-favourable** (a model-form
error masquerading as a utility update). Priced by the §14 reliance-sensitivity band on the gate.

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

**The decision log — the fourth stream, same arithmetic.** Owner reactions are readable
as *choices* (§4.4's preference evidence) only against the decision context, which
nothing else records: what the agent chose, among which actions, under which posterior.
`$LIFE_AGENT_KB/calibration/decisions.jsonl` — append-only and order-defined like the
outcomes log — records every EU decision: (tx_time, question_id, family, action_set,
posterior summary, utility_fold_version, chosen_action, predicted_eu). Reactions join by
question_id (verdicts, corrections, re-asks). **No EU decision is ever made unlogged** —
the log lands with the first decision it must witness (§12 stage 1 slice 2), by the same
option-value derivation as above. It also feeds §10's accounting.

**The reaction log — where this leg closes the gate, and the two firewalls it needs.** The
join of owner reactions onto those decisions (`$LIFE_AGENT_KB/calibration/reactions.jsonl`,
the §4.4 reaction loop) is the channel through which the gate actually moves: the first §8
gate run failed at P(Δ>δ)=0.848 not because the typed families lose but because `u(wrong)`
was a wide *prior* with no behaviour behind it, and the verdict stream is the genuine new
evidence that narrows it. Conditioning on post-cutoff reactions and re-reading is the live
ledger working as intended — but the blind-comparison discipline needs **two** firewalls
here, and the temporal cutoff is only one.

- **The real firewall is passivity, not the cutoff.** The cutoff is temporal (`tx_time >
  cutoff`); the threat is *informational* — the owner now knows the gate failed at 0.848
  and which direction moves it, so a verdict-generating process *run in order to* move the
  gate (priming "bad" on confident-wrong reports because adoption is wanted) contaminates
  the stream with the result even with every timestamp post-cutoff. The word "seeding" is
  the tell. So verdicts must be **byproducts of ordinary use**, not a gate-directed marking
  session; and if a dedicated pass is ever unavoidable, the owner verdicts **blind to the
  producing family and blind to the current gate reading**. (Note the v0 fold uses only the
  clean abstain rows, §4.4 — which also blunts this: "glad you didn't guess" is harder to
  fake toward adoption than a hunt for reports to mark wrong.)
- **The re-read uses an always-valid criterion, to avoid optional stopping.** Demand-led
  re-reads against a fixed `P(Δ>δ) ≥ 0.90`, taken however often verdicts arrive, will cross
  0.90 on fluctuation if you look enough — the same sin as a confident-wrong answer scoring
  at max, which the eval discipline already disowns. A pre-committed increment (re-read
  after `k` folded verdicts, `k` fixed in advance) closes it, and is valid even though `k`
  is chosen knowing the gate failed — the bar δ/level was frozen blind at the gate build,
  and a schedule blind to its own future data cannot select a favourable fluctuation or
  force the direction of movement (that is set by whether the owner's abstain-verdicts run
  `good` or `bad`). But pre-committed-`k` is brittle for a ledger whose purpose is
  *continuous* re-reading — one shot, then restart the firewall, and "`k` then `k′`" is
  optional stopping by the back door. So the **primary** criterion is always-valid: a
  confidence sequence / e-process, which licenses a look after *every* folded verdict, as
  often as wanted, with no optional-stopping penalty and **no `k` to choose**.

Both hold for the typed-vs-monolithic gate and for every later adoption gate. Movement is
then attributable to a changed fold-version under a pre-registered look, never to a hand
moved on the prior or an opportune glance.

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
first runs. From per-question utility outcomes under the §4.4 utility posterior we hold
a posterior over the EU gap Δ = EU(typed) − EU(monolithic); the gate is **P(Δ > δ) at or
above a stated level, integrated over P(U)**, with the materiality margin δ and the
level frozen in the gate's definition — never a point "≥" on two noisy means. The disagreement
region — questions where the two policies choose different actions (tails, abstentions,
confident errors) — is examined explicitly, since a system can lose on mean log score
yet win exactly where the action changes, and a raw-score gate would reject it wrongly.
A decision-weighted gate puts the utility model *inside* the gate, where a timid one
(abstention priced high) passes by abstaining everywhere — and reliability diagrams
cannot catch that, since they only score claims actually made. Three defenses, none of
them a bright line: the **utility prior and the preference-evidence cutoff are frozen
before any gate result is seen** (the blind-comparison discipline, extended from the
retired table to the posterior's inputs); the gap posterior **integrates over the §4.4
utility posterior** — adoption is a choice under utility uncertainty, and the former
"stated range of plausible tables" is no longer an ad-hoc band but P(U) itself, which
**resolves the §14 open question on the range's width** (the width is now
evidence-driven); and the **answer rate is published** as a named diagnostic.
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
expected value. **Priced in whose utility? The owner's — the agent has none of its own
(owner-supplied derivation, 2026-06-12).** Metareasoning is not a second decision
theory: it is the same EU maximisation with the action set enlarged to *think more*,
*call a tool*, *derive*, *ask the owner* — each resource cost charged against the §4.4
utility, each information benefit priced by VOI denominated in the same. The supporting
distinctions, each load-bearing:

- **Constraints are not preferences** (bounded optimality, Russell–Subramanian). How
  much compute exists, how fast the model runs, how many tokens fit — facts about the
  world bounding the feasible programs. The *valuation* of spending them lives in the
  owner's utility; a limit does not become a preference because it binds. The
  commensurability fork, stated: a *soft* cost (the owner would pay more for better) is
  an argument of his utility; a *hard* cost (a fixed budget) is a constraint on the
  feasible set — constrained EU maximisation either way, never an agent utility.
- **Apparent agent-goals reduce.** Instrumental subgoals — gather information, don't
  crash, keep the ability to act — are instrumental to the owner's utility, never
  terminal (Omohundro's drives are what an unconstrained maximiser *acquires*, not what
  this design *wants*). And under utility *uncertainty* (§4.4) the agent does not
  terminally value its own continuation — the off-switch property. Routing cost and
  time through the owner's utility is therefore **the safety property, not hygiene**:
  an agent with its own terminal utility for compute or continuation is exactly the
  misaligned one.
- **The cost proxy is an instrument.** A bounded agent cannot evaluate the owner's full
  utility per micro-decision — that is what bounded means — so it carries a model of
  "expected owner-cost of this compute / latency / interruption": operationally an
  internal cost term, conceptually a **proxy for the resource-arguments of the owner's
  utility**, calibrated against it. When proxy and owner disagree, recalibrate to the
  owner — never split the difference. A drifted proxy is Goodhart on the cost model
  (the metareasoning-level twin of an overconfident posterior); in this document's own
  terms it is an edge with an error model, graded against outcomes like every other
  (§2, §8). One more honesty, named like its world-side analogue: the proxy's grading
  *reference* is the λ_int/κ_att posterior, not an observable — it inherits that
  posterior's miscalibration, and proxy-vs-posterior grading cannot catch
  posterior-vs-owner drift. The cost proxy is only as good as the utility posterior it
  approximates; the owner-side graders (§8 grader 3 and the §4.4 choice streams) are
  what move the reference itself.
- **The regress terminates without an agent utility.** Deliberating about whether to
  deliberate is cut by amortisation: compile an approximately bounded-optimal policy
  offline, query it online — and the offline training objective is *still the owner's
  utility*. "All the way up" ends in a compiled approximation to bounded optimality
  with respect to one utility; no intrinsic objective is ever introduced.
- **The stage-6 failure mode, named now because it would be silent.** A governor
  scheduling derive / audit / ask / act against a separate "system efficiency" or
  "minimise compute" objective has quietly installed a second master — economising
  compute the owner would gladly spend, interrupting to save latency he doesn't value.
  The governor's VOI is denominated in the owner's utility, resource costs included
  (§12 stage 6's gate says so). Single-principal keeps it clean: one utility to be
  steward of, no aggregation — "whose cost?" always has the same answer.

The questions "which transforms do we want to run?" and "when?" decompose:

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
| **1 — Ask v0** | Slice 0: outcomes log + scoring-rule eval (first — the t=0 option-value argument, §8) — *landed*. Slice 1: the credence seam (§11) — *landed*. Slice 2: lookup family (§4) + the utility posterior v0 + the decision log (§4.4, §8). Slice 3: narrative subsumption (§7) | §8 gate (decision-weighted, Bayesian comparison): P(EU gap > stated margin) ≥ stated level integrated over P(U), disagreement region examined; log-score/Brier diagnostics + reliability diagrams published; double-run idempotency; pytest/ruff/mypy green | believing = computing, for point facts; honest abstention; the owner's preferences become a belief |
| **2 — Aggregate family** | recall term + completeness priors, missing-mass posterior, dedup-as-inference (§5); subsumes D3 | the spending question answered as a posterior with both coverage readouts; structure prior resolves a real duplicate pair | Occam appearance 1; M2 in full |
| **3 — Thread family** | `assemble` SPEC amendment (engine §10), `thread_state` instrument (§6); subsumes D4 | "awaiting reply?" green with membership-recall term; reclassification budget honoured (engine §11 D4) | the last fixed-pipeline failure family |
| **4 — Standing EU decisions #2–#3** | email→GTD filing governor (file/skip/ask on `optimise`+`voi`; beliefs conditioned on ledger disposal outcomes — `commands.complete`/`delete` dispose with reasons `done`/`dropped`; disposals are §4.4 choice evidence, consumed by the same utility machinery; includes wiring the absent `mail-to-tasks` timer) · VOI-scheduled audit sampling (§8) | filing decisions logged with posteriors; ask-rate falls as posteriors sharpen; audit VOI beats stratified on calibration-per-audit | acting joins the move; λ_int gets dense evidence (engine §13's placeholder, retired) |
| **5 — Structure learning** | `program_space` complexity priors over schemas/taxonomies (§9 appearance 3) | a schema revision proposed by posterior, validated on the eval corpus | the hypothesis-space distribution; Occam in full |
| **6 — The unified VOI governor (L3)** | one queue over derive / audit / ask / act — now permitted (≥3 concrete EU implementations: §4.4 response, stage-4 filing, stage-4 audits) and calibratable (cost + demand + outcomes + decisions, §10) | governor decisions beat demand-only scheduling on measured **owner** utility, resource costs included — never a separate "efficiency" objective (§10's second-master failure mode) | *scheduled by value of information* — the asymptote's verb |
| **7 — Goals/utility + bounded action** | the full goals/utility faculty (extends the §4.4 posterior: context-dependence, goal structure, drift; PRINCIPLES §15) → outward write-actions (email drafts, calendar) under ask/proceed/block; the spine decision lands here, unchanged | no autonomous write-action before the utility model (PRINCIPLES §3) — the standing constraint | acting in the world; the loop closes at L4→L0 |

Stages 2–7 are dependency-ordered, not timed; each is independently valuable; gates are
eval-gated per the amended PRINCIPLES §9. Re-prioritisation within the order is itself
the §7 EU calculation once stage 1's calibration data exists.

**Re-grounded 2026-06-28 (PRINCIPLES §16, the executor unification).** Stage 6 is not a deferred
governor. The executor — one argmax-EU over the terminal responses **and** the transformations,
on credence — *is* the agent (PRINCIPLES §1), built now and conservative-first as its own data
loop (it calibrates by running, so there is no build-vs-calibrate ordering to wait out). The
stages above are then the **faculties and decisions the executor ranges over** — lookup /
aggregate / thread are families in its decision space; filing and audits are further actions;
the transforms (retrieve / rerank / gather / extract / derive / route) are the rest — not a
sequence that culminates in a separately-built governor. What stays true: outward write-actions
(stage 7) wait on the utility model (§3), and *which* faculty to deepen next is itself the
executor's EU call.

**The write-action line, drawn now because stage 6 will lean on it.** Stage 4's filing
governor writes the GTD ledger under the v0 utility posterior, which sits next to "no
autonomous write-action before the utility model" (PRINCIPLES §3, stage 7's gate). The
line is **internal bookkeeping vs outward action**: a ledger append is
act-layer-internal — append-only, reversible by a later event, surfaced for owner triage
in reach — so it runs under the v0 posterior; outward actions (email, calendar —
anything a third party can observe, or that appending cannot undo) wait for stage 7's
full faculty. The stage-6 governor inherits this line as stated, not as folklore.

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

> **Commit shas in this section were remapped on 2026-08-18.** Corpus PII had reached
> the public repo's history; removing it required a `git-filter-repo
> --sensitive-data-removal` rewrite, which renamed 417 of 528 commits. Every
> life-agent sha cited below was re-resolved through filter-repo's `commit-map` and
> now names the same *content* under its new identity — no reading, run, or
> disposition changed. A clone taken before that date will not find these shas; the
> pre-rewrite bundle is archived out of tree. Shas belonging to the credence repo
> (the run-9 pin among them) are unaffected and unchanged.

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

**The §4.4 override (owner, 2026-06-12) — utility as inference.** The round-2 refinement
("utilities are preferences and may remain elicited constants") is superseded by owner
directive: *"treat [utility] as an uncertain function too and model it, learning about
it by observing my behaviour."* The agent's representation of the owner's preferences is
a belief about him, so the utility function becomes a posterior learned chiefly from
choice observations, with elicitation demoted to noisy evidence (§4.4 as amended). The
round-2 reviewer's original finding — constants where latents belong, applied to the
utility table itself — stands completed rather than refined; the disposition record
remains honest about which way that argument finally went. Same directive, second
derivation, also owner-supplied: **metareasoning is denominated in the one utility; the
agent has none of its own** (§10 as amended — constraints vs preferences, the cost proxy
as an instrument, the amortisation cut of the regress, the stage-6 second-master failure
mode). Resolved by this amendment: the open question on the gate's table range — the
range *is* P(U) (§8). New unbackfillable stream declared: the decision log (§8).

**The amendment confer (2026-06-12) — findings and dispositions.** Four residuals on
the new material, all folded: (1) the myopic action set must exclude ask-about-U —
ACCEPTED as a stated action-set coarsening (§4.4), with the reviewer's lemma corrected
in place: the collapse theorem does *not* zero the myopic VOI of ask-then-decide
(E[max] ≥ max E, strictly when an answer could flip the action); the exclusion stands
on sequential dominance and the rarely-pivotal-per-lookup argument instead, and
pre-governor utility learning is declared **passive only**. (2) τ/U non-identifiability
is in-principle, not small-n — ACCEPTED (Armstrong–Mindermann); the ledger entry now
measures prior adequacy, never data sufficiency. (3) the grid is a hard truncation
contra the soft-sign claim — ACCEPTED; stated exactly (bounds wide, endpoint mass
monitored, widen never renormalise), and noted as what discharges §0's bounded-utility
dependence by construction. (4) the cost proxy's grading reference is the utility
posterior, not ground truth — ACCEPTED and named (§10): the proxy inherits the
posterior's miscalibration; the owner-side graders move the reference itself.

**The reaction-loop confer (2026-06-13) — findings and dispositions.** The §4.4 reaction
loop (learning u(wrong) from verdicts) was conferred before build; the four-row sign table
was confirmed correct (no sign error, no double-count). Five concerns returned, all folded
above: (1) **two schema fields must land now** — `run_id` on the decision-side join
(`question_id` is not unique across runs; re-asks are designed in) and a nullable
free-text `reason` on `bad` (the one unreconstructable disambiguator; without it the
report-row approximation is permanently unfalsifiable) — ACCEPTED; latency-delta and
lineage keys correctly omitted (reconstructable from the join). (2) the mapping was **too
clever** — collapsing wrong-value / wrong-subject / didn't-want-report onto one u(wrong)
threshold is cross-latent contamination τ cannot launder, and it is signed *gate-favourable*
— ACCEPTED: v0 folds the **clean abstain rows only**; report-verdicts are recorded but
attribution-gated (§8 grader-3) and kept falsifiable by the reason slot. (3) identification
is **regime-dependent on threshold spread**, not the permanent τ/U degeneracy the draft
asserted (the cut-points are exogenous) — ACCEPTED: the τ claim softened, the §14 worry
reframed to bracketing verdicts, the recovery check made to sweep dispersion. (4) the
selection caveat holds but on **V-width-dominates-U-width** grounds, not low N, with a
stated promotion trigger and the retrieval-coverage coupling named — ACCEPTED. (5) the
blind-comparison firewall is **passivity, not the temporal cutoff** (the owner now knows
the gate result, so verdicts must be ordinary-use byproducts / blind-if-dedicated), and
demand-led re-reads are **optional stopping** — ACCEPTED: §8 gains both firewalls
(byproduct-of-use; a pre-committed evidence increment, never a fixed threshold re-checked).

**The reaction-loop confer, round 2 (2026-06-13) — the dispositioned design re-conferred.**
All five round-1 dispositions verified faithful; the sign table unchanged. The crux —
does "abstain rows only" trade contamination for an *identification* failure? — resolved
**for the conservative cut**, the worry inverted: under the prior the abstain band
`p ∈ [floor, 0.833]` spans thresholds `[0, −5]` (not a cluster), the gate is pivotal near
u(wrong) ≈ −0.72 (`p ≈ 0.42`, inside the retained band), and the discarded report rows sit
below −5 where the gate is insensitive — so the cut keeps the gate-pivotal rows and drops
the irrelevant deep-negative ones. The proposed un-correction (fold report rows through the
*built* `doc_subject` check) was **rejected**: it buys deep-region resolution the gate
doesn't need and still ships reading (c) "didn't-want-report" (λ_int, signed
gate-favourable) — a partial clean is worse than a clean defer. Four fixes folded: (i) a
**supersession rule** (latest verdict per `(decision_id, kind)`) against double-counting
revised verdicts; (ii) a dedicated **`decision_id`** rather than overloading `run_id` (per-
*run* on the eval path — a silent-contract divergence); (iii) "purely" → **"dominantly"** on
abstain cleanliness (within-latent politeness vs the cross-latent leak); (iv) the
**always-valid criterion** (confidence sequence / e-process) promoted to the primary
re-read, retiring the `k`-choice. The one named weak regime (bimodal retrieval) is the
retrieval-coverage coupling, not a fold defect.

**The narrative joint-fold confer (2026-06-14) — findings and dispositions.** §7.1 (folding
the narrative family — verdicts learning (u(wrong), κ_att) **jointly**) was conferred before
build. The joint fold, the connected-component factorisation, and the margin-functional
generalisation were endorsed; seven concerns returned. (1) **τ-scale** — do *not* normalise;
the raw EU-margin's varying steepness *is* the correct per-latent informativeness (`∂EU/∂x`),
τ keyed on event-shape — ACCEPTED (lookup's threshold-normalisation reframed as the mild frozen
misspecification, not the target to match). (2)+(6) **the cleanliness inverts** — narrative's
clean `good`-on-`ALL_WITHHELD` rows are one-directional, so folding clean-only runs the posterior
to the grid edge and passes the gate *spuriously*; the contaminated `bad` rows are the only
counter-pressure, structurally essential — ACCEPTED: v0 folds **both** valences, the contamination
anti-gate-favourable (utility-corruption, not gate-gaming). (3) **κ_att identifies** in the
decision-pivotal θ-band conditional on lookup pinning u(wrong), from `p_max` spread — ACCEPTED
(the recovery sweep checks `p_max` mass at the vertex ≈0.42). (4) **the joint fold** is the
connected components of the latent co-occurrence graph; marginalise only at readout — ACCEPTED.
(5) **reliance-linear** is forced (separating reliance from u(wrong) needs an act-on-a-claim
stream) but unsafe in the over-reliance (gate-favourable) direction — ACCEPTED: priced by a
reliance-sensitivity gate band, not merely a named successor. (7) **joint over plug-in** (the
plug-in injects κ_att's error into u(wrong)) — ACCEPTED. The one disposition the **owner revised**
(2026-06-14): the confer bundled coverage-gating + a closed-vocab reaction reason as the v0
`bad`-row clean; the owner **split** them — the runaway dies with fold-both + coverage-gating
alone (both **mandatory**), and the closed-vocab is the *deferred* which-claim residual clean,
safe to defer because the free-text reason is **already retained** (the mis-location is bounded,
anti-gate-favourable, reversible by refold), with a stated promotion trigger. The reviewer
concurred on re-read: "load-bearing in v1" was true of the coverage gate, overstated for the vocab.

**Counterarguments, recorded with answers:**

- *"This is confidence decoration on a working pipeline — complexity without new
  answers."* The open failure families are precisely failures of uncalibrated implicit
  inference: conflicting evidence resolved by rank (F2), aggregates silently bounded by
  recall (F1), abstention thresholds unprincipled (engine §13). And the claim is
  falsifiable by construction: if stage 1's decision-weighted gate (§8) shows the typed
  family does not beat the monolithic instrument, that result is published and the
  design answers for it. **It did, on the first run (2026-06-13): the gate returned
  FAIL — not because typed loses (its mean gap is large and positive) but because the
  bar is not cleared at the stated level; the result is published, the design answers
  for it, and the two evidence streams that would flip it are named (ledger below).**
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
- **The gate's table range (§8) — RESOLVED 2026-06-12** by the §4.4 amendment: the
  "range of plausible tables" is the utility posterior P(U) itself; its width is
  evidence-driven, not a stated band. (Evidence: the owner's utility-as-inference
  directive; the §14 override record.)
- **Adoption of the typed families (§8/§12 stage 1) — OPEN, first reading
  2026-06-13.** The decision-weighted gate is built (`life_agent.core.gate`,
  `run_eval --gate` → `$LIFE_AGENT_KB/eval/gate/`) and ran over the 21-question slice
  with the **frozen** utility prior (no elicitations yet, so P(U) is the pure prior:
  u_wrong ~ N(−5, 4)) and δ = 0.05, level = 0.90, both frozen blind in the module.
  Reading: **FAIL** at P(Δ > δ) = **0.848** (< 0.90), with Δ̄ = **+2.23** per question
  [90% interval −1.19, +6.09]. The mean strongly favours typed — but the gate is not a
  point test on the mean: the interval crosses zero because (a) u_wrong is only a wide
  prior and (b) the corpus is 21 questions (the Bayesian bootstrap carries that). The
  diagnostic that names the crux: typed answer rate **0.11** vs monolithic **1.00**,
  disagreement region **19/21** (all *typed-abstains × monolithic-reports*) — typed wins
  there *only* insofar as a wrong report is costly (it concedes −u_correct on the ~8
  questions the monolithic answers correctly and typed abstains). So the gate did
  exactly what §8 demands: a timid policy (11% answer rate) did **not** auto-pass. The
  result is honestly conservative — gold-token-containment grading penalises the
  monolithic on fuzzy questions it may answer well, which only inflates the typed gap,
  yet the gate still fails. *Decided by* two named streams, either of which flips it:
  (1) **narrowing P(U)** — elicited or revealed evidence that wrong answers are as
  costly as the prior believes lifts P(Δ > δ) toward the level (the ~16% upper-tail mass
  of u_wrong near zero is what the 0.848 leaves on the table); *first evidence:* the
  elicitation stream + stage-1 decision-log/verdict joins (§4.4). (2) **raising the
  typed answer rate** — retrieval coverage so the narrative family reports instead of
  blanket-abstaining, turning conceded −u_correct into earned +u_correct; *first
  evidence:* the retrieval-coverage work (the q-002/q-014 point-fact class). The gate
  re-runs deterministically (seeded), but the re-read is **pre-committed** — after `k`
  newly folded verdicts, or an always-valid criterion, never an opportune glance — and
  the verdicts must be **ordinary-use byproducts**, not a gate-directed marking session
  (§8's two firewalls; reaction-loop confer 2026-06-13). Lever (2) was *attempted and
  refuted* on 2026-06-13: both mechanical answer-rate levers (subject decoupling, RRF
  retrieval fusion) either dispersed the lookup posterior or manufactured a confident-wrong
  report — the answer rate is the owner's confident-wrong aversion working, so lever (1),
  the §4.4 reaction loop, is the live path.
- **τ-prior adequacy (§4.4) — regime-dependent, per the reaction-loop confer.** τ and U
  are non-identifiable from choice data *in generic IRL* (Armstrong–Mindermann); but the
  reaction loop's cut-points are **exogenous** (the agent's credence `p` sets each
  threshold), so the τ-prior does *permanent* separating work only in the
  clustered-threshold regime — with `p` spread, exogenous cut-point variation separates τ
  from u(wrong). The unknown is therefore two-fold: whether the τ-prior is *defensible*
  where it does bind (clustered `p`), and whether ordinary use yields enough threshold
  *spread* to lean on identification instead. *Decided by* prior-sensitivity analysis (vary
  the τ-prior, measure posterior movement) **and** the dispersion sweep in the recovery
  check below. *First evidence:* stage 1 (decision log + verdict joins).
- **The preference-evidence selection channel (§4.4) — caveat now, on the confer's
  grounds.** The owner verdicts only what the policy surfaced (M2 on this stream). The
  confer corrected the *grounds* for deferring it to a caveat: not "low N" but the §4.4
  V-width-dominates-U-width separation — the low answer rate is a retrieval-coverage
  artefact (dispersed posteriors), not a pessimistic u(wrong), so the policy-choice ⟂
  u(wrong) confound is weak and pure IRL's absorbing-timid-basin trap does not bite.
  **Promotion trigger:** carry it as a modelled term once the answer rate rises enough that
  report/abstain is decided where U-width *is* pivotal. **Coupling, named:** the loop cannot
  leave the timid basin by itself — what licenses more reporting (hence the report-verdict
  stream) is retrieval coverage (gate stream 2) sharpening `p`; v0's clean abstain-verdict
  signal is *not* so gated (p spreads across abstentions), the report-verdict stream is.
  *Decided by* divergence between posteriors conditioned on policy-surfaced vs
  owner-initiated evidence. *First evidence:* stage 1, sharpening at stage 4.
- **Preference drift / context-dependence trigger (§4.4).** Unknown: when the
  stationary-utility assumption breaks. *Decided by* systematic disagreement between the
  posterior's behaviour predictions and fresh choices (the stated stage-7 trigger).
  *First evidence:* whenever the decision log is mature enough to test predictions —
  stage 4 realistically.
- **The reaction loop's identification + evidence rate (§4.4) — reframed by the confer.**
  The verdict stream *identifies* (not merely bounds) u(wrong), but the identifying
  variation is the **spread of `−p/(1−p)` across reacted-to decisions**, not the verdict
  count: clustered credences return only a bound, spread credences bracket u(wrong) and
  recover τ from the slope. So the worry is the rate of **bracketing** verdicts (a
  report→bad and an abstain→bad at nearby thresholds beat fifty clustered ones), not
  verdicts-per-month. The abstain-only cut is *well-placed*, not merely clean (confer round
  2): under the prior the agent abstains across `p ∈ [floor, 0.833]` → thresholds spanning
  `[0, −5]`, and the gate is pivotal near u(wrong) ≈ −0.72 (the monolithic's ~0.42 accuracy
  on the disagreement set), i.e. `p ≈ 0.42`, an ordinary abstain credence *inside* the
  retained band — while the discarded report rows sit below −5, the region the gate is
  insensitive to. *Decided by* a recovery check that **sweeps threshold dispersion over the
  abstain-reachable range** — synthetic verdicts at a known u(wrong) across the `−p/(1−p)`
  band the abstain-only fold can actually produce, conditioned on the realised
  `p`-distribution of real abstentions (not an idealised uniform spread, or it certifies
  identification using cut-points the fold can never generate) — plus the always-valid gate
  re-read (§8). The one genuinely weak regime is **bimodal retrieval** (abstentions cluster
  near `p ≈ 0.1`, thresholds near −0.11, short of the pivot); no fold strategy rescues it
  (report rows at `p ≈ 0.95` sit even further, near −19), so it is the retrieval-coverage
  coupling, fixed only by better retrieval. *First evidence:* stage 1.
- **Narrative κ_att identification (§7.1) — OPEN, first evidence stage 1.** Unknown: whether
  ordinary use yields enough `p_max` spread to *identify* κ_att (not merely bound it) in the
  decision-pivotal θ-band, given κ_att inherits u(wrong)'s residual width (`≤ 0.25·sd`).
  *Decided by* the recovery sweep over the abstain-reachable `p_max` range (checking mass at the
  vertex ≈0.42 — the mediocre-proposals failure) plus the joint marginals' live endpoint mass.
  *First evidence:* stage 1 narrative abstain-verdicts.
- **Reliance-form misspecification (§7.1) — OPEN, priced not deferred.** Unknown: whether the
  fixed `r(p)=p` biases the gate — over-reliance pushes u(wrong)↓/κ_att↑, gate-favourable (a
  model-form error masquerading as a utility update). *Decided by* the §8 gate run under a
  **reliance-form band** (`r=p`, `r=1`, `r=1{p>p₀}`): robust across the band ⇒ safe to adopt on;
  a flip ⇒ reliance is gate-pivotal and narrative evidence may not be adopted until the
  reliance-measurement stream (GTD disposals / corrections / claim-citing re-asks) exists.
  *First evidence:* the next gate run after narrative verdicts accrue.
- **The narrative which-claim residual (§7.1) — OPEN, owner-deferred 2026-06-14 with a stated
  trigger.** Unknown: the rate at which a `bad`-on-`ALL_WITHHELD` is about a *different* proposed
  claim than `p_max` (mis-locating κ_att within the θ-band — bounded, anti-gate-favourable,
  reversible). *Decided by* the measured which-claim rate in the **retained free-text reasons** on
  narrative `bad` rows. **Promotion trigger:** that rate above a stated bar, or a gate
  false-negative diagnosed to which-claim → build the closed-vocab reaction reason, re-parse the
  retained reasons, refold. *First evidence:* stage 1.
- **Cost-proxy calibration cadence (§10).** Unknown: how often the learned
  owner-cost proxy must be re-graded against outcomes before drift (Goodhart on the
  cost model) becomes material. *Decided by* proxy-vs-outcome divergence in the
  decision log. *First evidence:* stage 6's first compiled policy (the proxy exists
  only then; named now so its grading stream is designed in, not bolted on).
- **The skin's batch throughput (§11).** Unknown: per-question subprocess vs pooled
  daemon. *Decided by* latency measured at stage 1; promoted per §11 if it demands.
- **The deliberative instrument's self-report signal (§2/§7 — added 2026-08-06, OPEN).**
  The promoted A1b arm (`core/deliberate.py`; declared: construct = the corpus-decided
  answer, cited; class = monolithic; calibration route = the outcomes log's per-edge
  curve, `core/calibration.py`) emits a self-reported CREDENCE consumed only as an
  observable signal into `P(correct | signals)` — never as the posterior (M3). Unknown,
  twice over: (1) whether the self-report is *informative* (does the fitted reliability
  curve separate its bins, or is the signal flat?) and *stationary* across model bumps
  (instrument identity keys on the model, so a bump cold-starts — is the accrual rate
  enough?); (2) whether the edge's EU on the live stream clears the **Δ2 outside-option
  gate** — the §8 criterion unchanged (δ/level frozen) with the comparator re-pointed at
  the owner's real alternative, the raw deliberative arm replayed from the stored
  fair-fight run (`run_eval --gate --gate-replay`; owner decision 2026-08-06 — the old
  gauge prices abstention at zero, which silently priced the owner's fallback at zero;
  the replay arm is the cheap honest correction, not a gauge re-pin). *Decided by* the
  per-bin reliability curve narrowing from outcomes attributed to `deliberate@<model>`
  (`calibration.edge_outcomes_from_log` keeps only rows whose `instrument_identity`
  names its `edge` — **no writer emits that key yet**: the attributed-outcome writer is
  itself the named first work item of this entry, and until it lands the ask path
  passes `curves=None`, so every declared constant stands and the calibrated regime is
  dormant, not silently degraded), and the Δ2 gate reading. *First evidence:* the
  attributed-outcome writer + the first Δ2 gate run + the first flag-on live decisions
  (`LIFE_AGENT_DELIBERATE=1`; flag-off at merge). **First Δ2 reading (2026-08-06,
  run gate-20260806T072244, flag OFF — today's typed policy vs the replay): FAIL at
  P(Δ>0.05) = 0.002, Δ̄ = −1.058 [−1.678, −0.529] — the shipped policy is ≈1
  correct-answer-equivalent per question WORSE than the owner's outside option.** Answer
  rate 0.21 vs 0.97; the loss is both legs: 80 abstain×report pairs at −0.375/q (reach
  the outside option has and the policy hands back) and 19 report×report pairs at
  −3.684/q (typed asserting wrong where the reference asserts right — u_wrong doing the
  arithmetic). This is the quantified motivation for the flag: the MVP passes when the
  calibrated shell keeps ~the reference's reach while cutting its confident-wrongs, and
  cannot pass from the typed-only basin. Priors frozen blind and cited: menu
  seed rho 0.92 (= ff-v2's 96/104 correct over all questions; conditional on asserting,
  96/101 = 0.950) **re-priced at offer time
  to what the enactment fold can deliver** (the daemon must never buy a probe at a rho
  the body cannot cash — 0.5 cap cold, the curve's value once evidence exists); cost
  0.38 (= the run's mean $0.375/question, `cost_status: estimated`, in the tier rows'
  approximate-dollars-as-gauge-utility convention — the true $↔utility exchange rate
  is an owner elicitation, open); cold-start curve Beta(1,3).
  **Second Δ2 reading (2026-08-06, run gate-20260806T101513 — flag ON, u_wrong PINNED at
  −9, the first elicitation line, σ=0.5): FAIL at P(Δ>0.05) = 0.010, Δ̄ = −0.644
  [−1.046, −0.194].** Answer rate 0.13 vs 0.97; report×report −2.143/q (14 pairs, was
  −3.684/q over 19). Three findings the rerun surfaced, each named:
  (1) **The gate's typed arm does not carry the edge.** `gate_paired_outcomes` runs
  `ask.answer(conn, gather=True)` — the derivation-path family decide — while the
  deliberative transform sits on the *executor* menu (`decide_via_loop`), the live
  ask-live/jarvis surface. All 104 in-gate decisions logged empty `instrument` and zero
  deliberate spend: **Δ2-with-the-edge is still unmeasured**; measuring it means either
  running the gate's typed arm through the executor surface or offering the edge to the
  family decide. The flag-on/flag-off delta above is therefore the PIN's effect (plus
  §18.9-warm replay drift), not the edge's.
  (2) **The pin moved the production assert bar back to the declared 10:1.** Identical
  warm posteriors decided differently across the two runs (leader 0.8588: report →
  abstain): pre-pin, the decide-side fold (prior + the live reaction stream) had let
  u_wrong drift to ≈−6 (assert bar ≈0.857) — the one-bit reactions had quietly relaxed
  the declared aversion; the σ=0.5 elicitation dominates the fold and restores ≈−8.8
  (bar ≈0.90), flipping the 0.85–0.90 credence band: 4 wrong reports killed at the price
  of 2 correct reports and 3 hedges. The first reading's ~8 wrong reports were partly
  this drift's doing. (Also disclosed: q2-014's abstain→correct-report flip rode 2 extra
  observations recorded by the same-day live smoke's corroborate by-products — demand-led
  cache warming, not a policy change.)
  (3) **First flag-on live decision (executor surface, the real deployment shape):** the
  daemon SCHEDULED the deliberate probe on a typed-abstain question; enactment cost
  $0.310 / 21.7 s cold and $0.00 / 0.0 s on the warm re-ask (§18.9 replay verified
  live); the self-report conditioned at the 0.5 cold cap could not lift a 0.763 leader
  over the ≈0.90 bar — abstain held, v2 accounting (instrument/cost/latency) on the
  ledger. The dormant-regime prediction held exactly: the attributed-outcome writer
  stays this entry's first work item, now with a live decision demonstrating why.
  **The writer + the gate-arm unification landed (2026-08-06, one build — findings (1)
  and (3) above are one gap seen from two sides: the gate couldn't see the edge, and
  the edge had no evidence stream; the executor gate arm is both the measurement and
  the harvest).** What landed: the View surfaces the edge's RAW proposal
  (`instrument_value`/`instrument_confidence`/`instrument_lineage`), the bridge names
  the §18.9 `cache_key` on every cached reply, `eval_edge` joins the closed grader
  vocabulary, `run_eval` gains `edge_outcome` (grades the proposal against gold on the
  shared token-boundary scale, **independent of the committed act** — an in-gate
  abstain still yields the edge's observation; that is the curve's construct,
  P(proposal correct | self-report)) and `--gate-executor` (typed arm =
  `answer_via_executor`, the surface the menu lives on; loud services precondition; a
  mid-run down stack voids the reading; in-gate decisions tagged with the run_id).
  Evidence hygiene, stated: outcomes buffer during the run and append after it (the
  in-run curve fold never conditions on its own run's rows); warm replays dedup on
  §18.9 lineage (one artifact, one observation); declines/errors write nothing (no
  value to grade — a disclosed v0 coarsening). **Review Critical, caught pre-merge and
  fixed (verified by execution):** the regime boundary was GLOBAL — the first
  deliberate outcome row would have made the fold non-None and collapsed the three
  corroborate tiers (no writer of their own) from 0.80/0.90/0.95 to the 0.25 cold
  start, prod-wide and permanently, the moment run 3 wrote its first row. The fix
  makes the boundary PER-EDGE (§2: each edge declares its own error model, never
  pooled): an edge with no attributed rows keeps its declared fallback; within a
  measured edge the §16 pessimism stands (absent confidence folds at the most
  pessimistic bin; unobserved bins cold-start at Beta(1,3)). Two earlier pins of the
  global switch ("curves supplied but edge unseen ⇒ 0.25") were artifacts and are
  superseded by the per-edge tests. **Planned next, in order:** run 3 = the
  cold harvest (`--gate --gate-replay … --gate-executor`, flag on: ~90 typed-abstain
  questions × ~$0.31–0.37 ≈ $30–35, ~40 min — its value is the outcome rows; decisions
  won't flip at the 0.5 cold cap), then run 4 = the first Δ2-with-the-edge READING on
  leave-one-question-out curve folds (the p3_gate grouped-LOO precedent — curves fit
  on the gated questions themselves would be §17.4's in-sample leakage re-enacted).
  **Run 4's harness landed ahead of the harvest (2026-08-06, `--gate-loo`):** the
  held-out discipline is mechanical, not procedural — `gate_paired_outcomes(loo=True)`
  sets a per-question hold-out (`ask.EXECUTOR_HOLD_OUT_QUESTION_ID`, the
  `EXECUTOR_RUN_ID` pattern) and the executor arm's per-question curve fold excludes
  that question's own rows at the one admission point
  (`edge_outcomes_from_log(exclude_question_ids=…)`, keyed on the log's own
  `question_id` attribution — exact for the `eval_edge` stream, which only gate runs
  write: live traffic has no gold to grade against, so that stream has no
  cross-surface leakage axis today; a future edge-attributed writer must stamp the
  eval id spelling or the exclusion cannot see its rows, named at the admission
  point). Scope, stated honestly (review findings, PR #58): the held-out discipline
  covers the **edge-curve channel** — the bridge-process extractor-rho
  (`/extract`'s pooled reliability mean, folded from audit/eval_lookup rows) is a
  second log→decision channel out of the hold-out's reach (today a pooled scalar
  over v1-id rows only: nil exposure for run 4, disclosed not defended), and the
  reading presupposes `LIFE_AGENT_MEMBRANE_LIVE` stays unset (a live membrane's
  verdict world is per-question in-sample evidence LOO cannot reach — currently
  contained). Preconditions loud: `--gate-loo` refuses without `--gate-executor`
  (the only arm that folds curves) AND without `LIFE_AGENT_DELIBERATE=1` in the
  gate's own process (flag-off the executor folds no curves at all — the run would
  have published the held-out label over a total no-op; review Major, refused
  mechanically); the family arm raises rather than wearing the held-out label over
  a no-op; the hold-out clears even on a voided run. The report names the
  discipline and its evidence base (pre-run attributed row count), and a vacuous
  LOO (zero rows — run 3 not yet harvested) is disclosed in the report itself,
  never read as a held-out result. Run 4 = rerun the run-3 command + `--gate-loo`
  (deliberate edges §18.9-warm ⇒ ~$0 **if the corpus digest hasn't moved** — the
  mail timers move it; a moved digest makes run 4 cold-priced, still a valid
  reading, just paid; fresh rows dedup to zero on lineage, so the reading adds no
  double-counted evidence).
  **Run 3 — the cold harvest (2026-08-07, run gate-20260807T125917, flag ON, pin
  held): FAIL at P(Δ>0.05) = 0.065, Δ̄ = −0.297 [−0.592, +0.095] — the interval
  crosses zero for the first time.** Answer rate 0.19 vs 0.97 (executor arm; the
  earlier 0.13 was the family arm, so only executor-arm readings compare
  like-for-like from here). The harvest surprise: at the 0.5 cold cap the priced
  menu scheduled deliberate on **14/104, not the ~90 estimated** — $5.27, not
  $30–35; the cap doesn't just keep a bought signal from flipping a decide, it
  prices most purchases below abstain in the first place. The 14 attributed rows
  (13 correct / 1 incorrect; mean Brier 0.0184) are the first curve food for
  `deliberate@claude-opus-4-8`.
  **Run 4 — the first Δ2-with-the-edge reading, held-out (2026-08-07, run
  gate-20260807T202838, grouped-LOO curves over the 14 pre-run rows): FAIL at
  P(Δ>0.05) = 0.092, Δ̄ = −0.239 [−0.533, +0.154].** The signature finding: **typed
  answer rate = correct-report rate = 0.25 — all 26 asserts correct, zero wrongs.**
  The report×report cell prices at 0.000, so the whole deficit is the 75
  abstain×report pairs at −0.333/q (the replay there: 70 correct + 5
  confident-wrong = +0.333/q under Ū's u_wrong ≈ −9 — abstaining past the replay's
  5 wrongs saves 45 gauge points and forfeits 70 corrects). With 14 rows of food
  the menu fired 45/104 (24 warm; $8.93 ≈ $0.43/cold call), and the run-3→run-4
  movement (rate 0.19→0.25 — net +6 asserts, 8 gained and 2 lost, churn not
  monotone growth — Δ̄ −0.297→−0.239, P 0.065→0.092) is the calibration flywheel
  turning — held-out by construction (the edge-curve channel) this time, since each
  question's decide conditioned on curves folded without its own rows
  (§17.4/§17.5's lesson applied before the claim, not after). 30 new rows appended
  (28 correct / 2 incorrect, Brier 0.0464) → 44 for the next fold; 45 fires but 44
  evidence-accounted — q2-024's cold fire, the run's costliest single call at
  $0.76, declined and wrote nothing (the disclosed v0 coarsening, priced here). The road to PASS, priced at
  current precision: one converted abstain (typed joins the replay's correct
  report) is worth +1/104 ≈ +0.010 Δ̄; one new confident-wrong costs ≈ −9/104 ≈
  −0.087 — nine conversions erased. Lifting the MEAN to parity-plus-δ needs ≈30
  net conversions (typed rate ≈0.54) at held zero-wrong precision — and the gate
  is a 0.90 mass bar, not a mean bar, so the true count sits further out by the
  interval's width. The levers remain this entry's two, with the flywheel now the
  mechanism for the second. Evidence hygiene, disclosed:
  run 4's first firing was killed externally pre-flush — the buffered append held
  (zero outcome rows from the dead run) while the v2 per-decision accounting rode
  through the kill: its 8 fires sit on the decisions ledger (run_id
  gate-20260807T132948 — 5 warm replays + 3 cold calls, $1.20), so no spend went
  unrecorded. Run 4's 24 warm hits reconcile exactly on that ledger: run 3's 14
  (deduped on lineage to zero new evidence) + the killed firing's 3 + 7
  pre-harvest artifacts (1 rides the live smoke's answer-brain row; 6 whose
  creating call left no decision row — surfaces that post no /log_decision by
  design, eval_executor's isolation-by-not-writing — each $0 at re-read and graded fresh
  on lineage, so double-counted evidence is excluded either way). The corpus
  digest held across all firings — **verified 2026-08-17** (it was an
  out-of-band operator check when written): the newest chunked artifact dates
  to 2026-06-11T20:24:55, two months before runs 3/4/5, so the retrieval
  universe was frozen at `03d1b09c498ec912…` throughout. See the correction at
  the run-5 attribution below, which struck the contradicting claim.

  **Run-6 Δ semantics — PRE-REGISTERED 2026-08-09, blind (before run 5 fired;
  owner ratified the split 2026-08-08: run 5 keeps the runs-3/4 Δ definition,
  the changes below bind from run 6).** Two changes, frozen here:
  (1) **The spend term.** Δ's per-question utility gains −λ_usd·cost_usd on BOTH
  arms and every action (money burned is burned whether the act reported or
  abstained): the typed arm's cost is the view's TOTAL metered spend (`spend_usd`
  — the deliberate edge AND the corroborate/rescue/re-extract tiers, each priced
  from its actual tokens bridge-side; §18.9 warm replays are $0 by construction),
  the replay arm's is the ff run's recorded per-question `usage.estimated_cost_usd`
  (the outside option pays for its calls too — pricing only the typed arm's spend
  would bias Δ pro-baseline, and only deliberate's would bias it pro-typed, the
  #67 review's finding). λ_usd (gauge units per USD) is a REQUIRED latent with
  prior N(1.0, 0.35) truncated to [0, 8] — truncated mean ≈ 1.002, the
  months-operating $1 ≈ 1·u_correct authoring convention within 0.2% (computed,
  not assumed: an N(1,1) draft's truncated mean was 1.288, a silent 29%
  re-pricing the review caught; the example-yaml prior is drift-gated in tests) —
  frozen before any elicitation; the owner's elicitation line narrows it and the
  gate samples its marginal like every latent. Disclosed side effects: the sixth
  latent shifts the seeded MC RNG stream, so post-merge gates are a NEW
  seed-stream — cross-merge comparability runs through the published artifacts
  (paired.jsonl now carries cost_usd per arm precisely so the fold stays
  replayable), never seed-replay; and a paired row lacking the latent in its
  utility sample prices spend at exactly zero, which is how pre-run-6 artifacts
  replay unchanged. The decide-path twin lands with the same merge: menu rows and
  grow actuators stay authored in USD and convert at u_bar's λ_usd at the decide
  payload (legacy $1 ≈ 1-gauge when the latent is absent).
  (2) **Judge grading, conditional.** Run 5 carries the cross-provider modal-of-3
  correctness judge SHADOW-ONLY (§ the judge-verdicts cache; grading unchanged,
  the disagreement table published in the gate report). Iff the hand audit of
  that table clears — the judge rescues real matcher misses without minting
  false credits — run 6 adopts judge grading for the gate arms (the eval_edge
  curve rows adopt LAST, separately, they move live behaviour); if the audit
  does not clear, run 6 stays matcher-graded and says so. Either way the run-5
  addendum records the audit verbatim.
  **Run 5 — the warm fold + the first extract@ harvest (2026-08-09, run
  gate-20260809T102018, master 2660b72 — the refusal gate, the tier writers and
  the judge shadow aboard; runs-3/4 Δ definition, per the split above): FAIL at
  P(Δ>0.05) = 0.098, Δ̄ = −0.230 [−0.525, +0.163].** Typed answer rate =
  correct-report rate = 0.26 (27/104) — zero wrongs, third consecutive executor
  reading. The disagreement region is 76/104 (75 abstain×report at −0.333/q + 1
  report×abstain at +1.000); the agreement set (26 report×report, 2
  abstain×abstain) prices at 0.000. The report×abstain is **q2-083 — a re-gain,
  not novel reach**: run 3 converted it, run 4 lost it (one of run 4's own "2
  lost" churn), run 5 wins it back (the replay abstains there). The
  run-4→run-5 console diff is exactly that one action — no other churn — and Δ̄
  moved +0.009, almost exactly run 4's priced +0.010/conversion. Attribution,
  honest: q2-083 has no deliberate rows in any run — its conversion rode the
  three corroborate tiers agreeing on the same claim (self-reports 0.55–0.85),
  which the LOO curve bank (44 pre-run rows, all deliberate@claude-opus-4-8)
  could not have touched; ~~between the runs both the master code (#61–#65) and
  the corpus digest moved, so the lever is not isolated~~ — and a question that
  flips run 3 → run 4 → run 5 on unchanged gate semantics is boundary churn,
  not a channel win. **CORRECTED 2026-08-17 — the corpus did NOT move between
  the runs; the struck clause was false.** The newest *chunked* artifact in the
  store was produced **2026-06-11T20:24:55**, while runs 3/4/5 fired
  2026-08-06/07/09. Everything written to the store since 12 June is
  `life_agent.ask.*` plus the `doc_subject`/`doc_date` projections, none of
  which are chunkable by design (`core/corpus.py:11-12`) — which is exactly why
  the store's mtime kept moving while the retrieval universe stood still. So
  the master code (#61–#65) was the **only** moving lever across runs 3→5, and
  this correction *removes* a confound rather than adding one: the three
  readings are a controlled series on one frozen corpus, digest
  `03d1b09c498ec912…` throughout. The q2-083 boundary-churn verdict is
  unaffected — it rests on q2-083 having no deliberate rows in any run, which
  never depended on the corpus claim. Reproduce with
  `python scripts/forensics/corpus_timeline.py`. **Evidence class:** forensic
  reconstruction from the catalogue, *not* an artifact property of runs 3–5 —
  those published no corpus identity and never will; and while the digest's
  *identity* is recoverable this way, the *membership set* behind any past
  digest is not (`artifact_chunks` has no timestamp column). Both gaps close
  from run 6 on. **The curve-channel flywheel produced no measured
  conversion this round.** The #56 refusal gate earns no reach credit either —
  q2-093/q2-096 (the named refusal class) were already correct-reports in
  pre-fix run 4; the fix ran live on the executor arm (the shared
  `usable_terms` gate sits inside `core/expansion.expand_terms`, applied on
  both the cached and fresh paths, with `ask.py`'s `_expand_terms` the
  counter-instrumented wrapper) but the printed refusal counter instruments
  only the family-arm ask path, which gate-executor runs never exercise —
  hygiene verified present, effect on this corpus nil. Deliberate fired 50/104
  (46 warm) at $1.71 total (run 4: 45 fires, 24 warm, $8.93) — the §18.9 cache
  amortizing exactly as designed. **The harvest: 217 rows appended (82
  extract@claude-opus-4-8 + 67 extract@claude-sonnet-4-6 + 60
  extract@claude-haiku-4-5 + 8 deliberate; 67 warm dupes deduped on lineage) —
  the first attributed evidence the corroborate tiers have ever produced.**
  Accuracy at their self-reports: opus 71/82 (0.87), sonnet 53/67 (0.79), haiku
  50/60 (0.83); the 8 new deliberate rows ran 5/3 (cumulative deliberate bank:
  52 rows, 46 correct); batch proper scores mean_log −0.390, Brier 0.120. The
  bank for run 6's LOO folds is 261 rows across four edges — run 6 is the first
  reading where the tiers' declared 0.80/0.90/0.95 constants earn out into
  measured per-edge curves. Artifact hygiene, the full loss disclosed: the
  fixed-path report.md/paired.jsonl are the NEXT run's clobber victims, and the
  manual archive ritual was missed twice — **runs 3 AND 4 both lost their
  report and paired.jsonl** (only the flagoff run 1 and run 5 are archived;
  runs 3/4 survive in the outcomes/decisions ledgers and their consoles, now
  copied durably to `eval/gate-outside-option/console-gate-<run_id>.log` for
  runs 2–5 — they previously lived only on tmpfs, one reboot from gone, and
  they are the sole per-question action record for runs 3/4, so the
  one-action-diff claim above is checkable against them). Archiving is now
  MECHANICAL, not a ritual: `run_eval.archive_gate_artifacts` copies both
  artifacts to run-id-suffixed names inside the gate run itself (after the
  judge append, so the archive carries the full report; landed with this
  reading's PR, tested) — the run-6 replayability invariant no longer hangs on
  an operator remembering a step missed 2 of 3 times.
  **The judge-shadow audit (registration (2) above, resolved): 412/412 judged
  (judge pin gpt-5.1, modal-of-3, verdicts cached under judge-bound keys), 0
  unjudged, 405 agree, 7 disagreements — all seven on the mono arm; zero on
  typed asserts, typed hedges, or edge rows** (the zero-wrong typed claim now
  has cross-provider corroboration). The seven, hand-audited: (a) **suspected
  GOLD errors — 2:** q2-018 and q2-105 each assert a fax number that
  contradicts gold while quoting the gold digits as the adjacent tel field —
  but checked against the primary sources, **each candidate is faithful to its
  cited file**: `pdm_accessgovhk.csv`'s header runs fax-BEFORE-tel and its
  Mong Kok row carries a DIFFERENT number in the fax column; the q2-105 CSV
  (`accessgovhk_1749223971.csv`) runs tel-before-fax and its Audit Commission
  row likewise differs in the fax column. Both golds equal the row's TEL value — the
  factory gold looks tel/fax-swapped on both. Verdicts on these two are
  gold-conditional: the matcher's CORRECT is right-for-the-wrong-reason (a
  token match on the tel digits), the judge's INCORRECT is right against
  frozen gold and wrong against the source. **Named pre-run-6 action:
  re-verify and correct these two golds via a disclosed corpus change** —
  under corrected gold both graders pass these candidates and the items leave
  the table. (b) **matcher false credit, judge right — 1:** q2-021 asserts
  page 120 against gold 119, matched only on "page-119 footer" in its own
  citation prose (gold-conditional too — the source PDF was not at its
  declared path to re-verify — but no source-level refutation exists, so gold
  stands). (c) **real rescues, matcher false negatives — 2:** q2-026
  ("Thursday 23rd March 2017", a variant gap) and q2-048 ("West, D. B.
  (2001)" vs "West, 2001", a citation-format gap). (d) **judge false negatives
  — 2:** q2-035, where the candidate asserts gold 718348 verbatim then adds
  "corroborated as 0718348" — re-judged out-of-band three fresh times (no
  cache read or write): False/True/False, a stable near-boundary failure on
  corroboration-shaped candidates, not vote noise; and q2-028, where gold is
  the deictic "yesterday" and the candidate quotes it faithfully while
  resolving both dates — the judge's strict reading is defensible, the audit
  grades the candidate correct. **Ruling under the frozen criterion — the
  rescues are real (2/2) and no false credits were minted (0): the audit
  CLEARS. Run 6 adopts judge grading for the gate arms; eval_edge curve rows
  stay matcher-graded (adopt last, separately, as registered).** The table's
  chief yield was (a): two suspected gold errors the matcher alone could never
  have surfaced. Named residual, priced: the judge's conservative mode removes
  true credits at measured incidence **2/412 ≈ 0.5%** (q2-035 and q2-028 —
  both on the mono arm, and that direction is gate-FAVOURABLE: one
  matcher-correct mono report judged wrong hands typed a spurious ≈ +10/104 Δ̄
  swing at Ū). So run 6 keeps publishing the judge-vs-matcher disagreement
  table and **its reading must name any judge-flipped rows on EITHER arm
  before the Δ is trusted** — typed asserts are corroboration-shaped, exactly
  the judge's measured false-negative shape, and a spurious first typed
  confident-wrong would cost ≈ −10/104 Δ̄ plus the zero-wrong record.
  Counterfactual (not a reading): had judge grading governed run 5 against
  frozen gold, mono flips down 5 (q2-018/021/028/035/105) and up 2 (the
  rescues) = **96→93, net −3** — of which only q2-021's removal is an audited
  true correction; q2-018/q2-105 are the suspected gold errors and
  q2-035/q2-028 the judge's own false negatives. Typed is untouched either
  way. Road to PASS unchanged (≈30 net conversions at held zero-wrong
  precision), but the reach lever now has two measured channels: the
  deliberate curve food and, from run 6, the corroborate tiers running
  calibrated.

  **The lambda_usd elicitation (2026-08-09, RESOLVED — with a disclosure).**
  Asked the registered question ("how many marginal correct answers is $1
  worth?"), the owner first requested a sensitivity exploration — "choose 3
  reasonable values that explore a good range of functionality" — so a
  counterfactual re-pricing sweep ran BEFORE his number: the production
  `gate.delta_posterior` (run-6 #67 spend semantics) over run 5's frozen
  realised actions, mono costs exact per replay row ($39.01 total), typed
  costs the console total ($1.71) allocated uniformly (per-question split not
  persisted pre-#67; second-order). Artifact + deterministic script:
  `$LIFE_AGENT_KB/eval/gate-outside-option/lambda-sensitivity-20260809{.md,-sweep.py}`
  (replay requires the repo at the #68 merge `edc3ef5` plus the 2026-08-09 KB
  posterior state — the script pins these and takes `LIFE_AGENT_REPO` from the
  environment); the cost=0 sanity pin lands at 0.097/−0.232 vs the published
  run-5 reading 0.098/−0.230 — draw-stream jitter only (the new latent shifts
  the MC sample stream, not any utility at cost 0). Landmarks on those frozen
  actions: Δ̄ slope +0.3587 per unit λ (the $39.01-vs-$1.71 asymmetry), sign
  flip at λ≈0.65, the outside option's own EU/q negative beyond λ≈1.3, the
  0.90-mass bar at λ≈1.5 pinned. **Disclosure: the elicitation was therefore
  made AFTER the owner saw the λ↔verdict map.** The introspective framing (the
  number answers what a marginal correct answer is worth, not which verdict it
  buys) was stated to him alongside the map; the risk is named, not nulled.
  **His statement: `stated_value = 1.5`, `noise_sigma = 0.25`** (he chose a
  tighter σ than the 0.5 u_wrong precedent — the map showed one σ=0.5 line
  cannot move the fold far from the N(1.0, 0.35) prior). Folded through the
  production posterior: **lambda_usd = 1.331 ± 0.203** — the frozen prior
  still pulls the stated 1.5 down by 0.17; disclosed, not corrected
  (re-freezing the prior after seeing readings would be tuning). Counterfactual
  at his folded posterior (not a reading): run 5's frozen actions price to
  Δ̄ = +0.245 [−0.076, +0.646], P(Δ>0.05) = 0.808 — still FAIL, just under the
  bar — with the outside option's EU/q at −0.009 **at the folded rate 1.331**,
  effectively break-even; at his literal stated 1.5 (pinned) the artifact's
  table reads −0.072/q, distinctly negative. Ledger mechanics: the elicitation
  line appends to `$LIFE_AGENT_KB/utility/elicitations.jsonl` only once the
  **deployed prod code** carries the latent — the pre-#67 `load_elicitations`
  raises on an unknown latent, so a premature append crashes every prod
  utility fold. The session's pull-watcher is detect-only and session-scoped
  (it polls the prod master ref, which can move for reasons short of a #67
  deploy); the append step re-verifies `lambda_usd` in the deployed
  `utility.py` before writing, and a dead session just leaves the append
  outstanding. Run 6 cannot silently absorb that: **added guard, registered
  blind before any priced reading — run 6's report must name the lambda_usd
  posterior it folded; a prior-only fold (1.002 ± 0.347, the line never
  landed) VOIDS the priced reading** rather than passing it off as elicited.
  All other run-6 pre-registrations stand unchanged; once the line lands, the
  spend term runs on the elicited fold (1.331 ± 0.203), not the bare prior.

- **Corpus availability as a Δ confound (§8) — added 2026-08-15, REGISTERED BLIND before
  any run-6 reading.** Unknown until now: what the gate does when the corpus differs
  across machines. The arms are **not symmetric** under it — the typed arm runs live
  against the running box's catalogue while the replay arm is a frozen full-corpus
  recording (`_replay_response`), so every availability gap lands as `abstain × report ✓`
  at −0.333/q and biases Δ **pro-baseline** by a per-machine amount. Nothing recorded it:
  no gate report has ever carried the corpus digest, so "the corpus digest held across all
  firings" was an out-of-band operator check, not an artifact property. Measured extent on
  the current corpus: 238 sources / 230 chunked artifacts (~~1.8% of 12 984~~) sit under
  `<downloads>`, a root whose *content differs per machine* (139 files on thinkpad,
  425 on steel), and 16 of the 104 eval questions cite provenance under it. Three changes,
  frozen here, binding from run 6:
  **MAGNITUDE CORRECTED 2026-08-17, before any run-6 reading — the registered figure
  understated the exposure 13×.** "1.8% of 12 984" is the *artifact* share; measured by what
  retrieval actually ranks over, this root is **126 090 of 529 788 chunks = 23.8%** of the
  retrieval universe (its CSVs chunk heavily: 86 `.csv` of the 238 sources). The censoring
  rule below is unaffected — still zero rows on the run-6 corpus, re-verified at the same
  date — but the sentence as registered misdescribed how much of the corpus rides on a
  machine-local root, which is the whole point of the entry. Reproduce with
  `python scripts/forensics/corpus_timeline.py --root <downloads>`.
  (1) **Corpus provenance is published.** Every gate report carries the `corpus_digest`,
  the resolved/absent root list, and the count of chunked artifacts whose root is
  unresolvable. Pure measurement, no Δ effect — a reading whose corpus is unrecorded is
  not replayable, which is the same invariant `paired.jsonl`'s per-arm costs already serve.
  (2) **The withholding taxonomy is published.** The paired row records *why* the typed arm
  withheld: `miss` (no posterior ever existed — zero grounded observations, the daemon not
  consulted), `dispersed` (a posterior existed and lost the EU argmax), or `unavailable`
  (see 3). Run 5's 70 `abstain × report ✓` rows were undifferentiated between these, which
  is precisely why the reach lever has had no direction; the executor distinguishes them
  already and the gate discarded the distinction. No Δ effect: the bucket defaults to the
  value reproducing today's Δ byte-for-byte (the `lambda_usd` precedent).
  (3) **`unavailable` rows are CENSORED from Δ** — excluded from the per-question gap and
  from the Bayesian bootstrap's weights, while still folded into the published diagnostics
  and named in the report. A question whose gold evidence is absent from the running
  catalogue measures nothing about the typed policy; pricing its abstention as a policy
  failure is the bias named above. The predicate is gold-side and exact: censor iff the
  question's `provenance` evidence is absent from this catalogue. **Disclosed blind, before
  any priced reading: on the run-6 corpus this censors ZERO rows — 104/104 gold provenance
  chunks resolve** (verified 2026-08-15 against `artifact_chunks`), so run 6's Δ is
  untouched by (3) and the rule is a forward guarantee, not a re-pricing. **Added guard:
  run 6's report must name its censored count; a run censoring a nonzero number of rows
  whose reading does not name them VOIDS the reading.** Distinct from `answerable=False`,
  which does **not** censor — it is read once (the reported rates) while its rows still
  carry a gap term and a bootstrap weight; reusing it as the censor would silently
  re-price every archived run, so the censor is a separate flag.
  ~~Named residual, priced: the provenance handle today is the **surrogate** `chunk_id`
  (migration `0005`), comparable across machines only because this catalogue is a byte-copy
  of steel's. On an independently-chunked box the predicate needs the content-addressed
  `artifact_cache_key` (the `artifact_chunks` join column, and what `corpus_digest` itself
  hashes) — named as the fix, not yet landed. Until it is, the censoring rule is sound only
  on catalogues sharing a chunking lineage, and a run on a re-chunked corpus must say so.~~
  **RESIDUAL DISCHARGED 2026-08-17 — REGISTERED BLIND, before any run-6 reading.** The
  content-addressed handle now rides in the gold and decides the predicate. Three parts:
  (a) the factory emits `artifact_cache_key` + `chunk_index` (the `artifact_chunks` PRIMARY
  KEY, migration `0004`) alongside `chunk_id`, at `format_version: 2`; (b) the existing
  corpus was backfilled by a 1:1 catalogue lookup — no model call, no re-verification, no
  re-sampling — under a guard that **aborts the write on any change outside `provenance`**,
  and 104/104 resolved; (c) `gold_available` prefers the pair and falls back to `chunk_id`
  **per question**, so a partly-backfilled corpus degrades one row at a time.
  *Why now, not later:* `pkm rebuild-catalogue` (SPEC §13.1, the recovery path) re-issues the
  `chunk_id` sequence, after which every id in the corpus still resolves to *some* chunk —
  the wrong one. Silent, unbounded corruption of the single field this censoring rule keys
  on. The surrogate is kept as a convenience handle, never as the decider.
  **Disclosed blind, before any priced reading: the new predicate censors ZERO rows on the
  run-6 corpus — 104/104, unchanged from the surrogate predicate** (verified 2026-08-17
  against `artifact_chunks`). So the switch cannot have moved run 6's Δ. Had it censored a
  nonzero count, that count would be stated here, before the run, not after.
  **Question-corpus freeze for run 6** (the rewrite necessarily moved the hash, so it is
  pinned here rather than assumed): `questions_v2.yaml`
  sha256 `c57d8c0c43014cad…`, was `7a569a0ba7f6230f…` (`.bak` retained). The diff is
  provenance-only across all 104 questions, mechanically checked, and adds exactly
  `{artifact_cache_key, chunk_index}`.
  §12's stage order is unchanged by this entry; it is gate-instrument work under stage 1.

- **P(U) elicitation sprint (2026-08-17, DISCLOSED BLIND — before any run-6 reading; the
  §8 "narrow P(U)" lever, exercised).** Asked the three remaining first-order latents'
  registered questions with their gauge stated (correct = +1, abstain = 0, the owner's own
  u_wrong = −9); the owner stated: **u_hedged = 0.4 · lambda_int = 1.0 ·
  u_wrong_scoped = −2.0** — each the frozen prior's mean, i.e. the statements *confirm*
  the priors rather than move them, and their effect is pure narrowing. `noise_sigma = 0.5`
  on all three is the u_wrong precedent's default, not owner-stated — disclosed as such,
  owner-revisable by a superseding line. `kappa_att` remains prior-only (second-order;
  not asked). Lines appended to `elicitations.jsonl` (`.bak-20260817` retained) after
  verifying the deployed `load_elicitations` accepts all three latents; fold loads clean.
  Blindness: stated before run 6 fired and without any per-question λ↔verdict map — the
  after-map risk the lambda_usd entry names does not arise here. Run 6's report names the
  elicitations file hash via `run_meta.json`, so the reading self-identifies which P(U)
  it integrated.

- **Instrument migration — local Ollama deprecated (2026-08-17, owner directive;
  REGISTERED BLIND before any run-6 reading; owner chose migrate-first over
  run-6-first, knowing the comparability cost).** The four cached ask instruments
  (`lookup_route`, `lookup_extract`, `owner_match`, `temporal_intent`) and the eight
  LLM transform declarations (`email_triage`, `action_items`, `doc_date_*`,
  `doc_subject_*`) move from `ollama/qwen2.5:7b-instruct` (local) to
  `anthropic/claude-haiku-4-5-20251001`, through the same `make_model_client` seam
  `entity_extraction` already uses; jarvis's NLU moves with them. One identity builder
  now owns the four keys (`derivations.instrument_identity`) so the change is one
  deliberate edit. Consequences, priced and disclosed:
  (a) **Run 6 measures a NEW typed instrument.** Runs 3–5 (one frozen corpus, one
  instrument) end as a controlled series; run 6's Δ movement confounds the reach work
  with the instrument change, and its reading must attribute accordingly. The
  registered run-6 semantics (judge grading, spend, censoring) are unchanged.
  (b) **Cold caches.** ~7,891 local-keyed cached artifacts (6,879 `lookup_extract` +
  route/subject/intent/transform verdicts) are orphaned by the identity change —
  deliberate: pointing the old identity at a different runtime would have replayed
  them silently as if the instrument had not changed. §18.9 warm-replay economics
  restart from zero; the answer-stage artifacts (schema-1, model-free) survive.
  (c) **Curves.** The tier edges (`extract@claude-*`, deliberate) were already cloud
  and keep their 261-row bank; the BASE extract instrument changes under an unchanged
  declared reliability — conservative under a strictly stronger model, recalibrated
  from the outcomes stream as before.
  (d) **Spend.** Base instrument calls are now cloud-priced, so NEW metering lands
  with the migration: `/extract` and `/probe/subject` replies carry the cache-miss
  `cost_usd`, folded into the view's `spend_usd` — the §8 spend term prices them on
  the typed arm from run 6 on (an unmetered base call would ride at $0 while the
  replay arm is fully priced — the #67 asymmetry re-created). `/route`'s cost is not
  wire-carried (its null reply cannot carry a field): one small cached call per
  question, de minimis, named here rather than silently absent. `temporal_intent` is
  ask-surface display, not on the gate path.
  (e) The corpus and retrieval are untouched (FTS only; the embedding column was
  never populated — see the ROADMAP correction of the same date).

- **Run 6 — the first positive Δ̄ (2026-08-17, run `gate-20260817T132417`, branch
  `feat/fallback-lane` @ `dbd7931`; every run-6 pre-registration in force: judge grading
  for the arms, the λ_usd spend term on both arms, availability censoring, corpus pin
  `full-2026-06-11` MATCHED, the NEW cloud instruments per the migration entry above):
  FAIL at P(Δ>0.05) = 0.678, Δ̄ = +0.180 [−0.244, +0.661].** Guards: λ_usd folded at
  **1.3311** (the elicited fold — the prior-only void guard passes); censored **0**; the
  judge flipped **5 rows, all on the mono arm** (q2-021/028/035 CORRECT→INCORRECT, q2-026/048
  INCORRECT→CORRECT — exactly the five the run-5 shadow audit named, no new flips, none on
  the typed arm), so Δ is trusted per the registration. Series: 0.002 → 0.010 → 0.065 →
  0.092 → 0.098 → **0.678**; Δ̄ −1.058 → −0.644 → −0.297 → −0.239 → −0.230 → **+0.180**.
  **Typed answer rate 0.47 (49/104: 47 correct reports + 2 wrong)** vs 0.26 in run 5;
  monolithic 0.97 (95 ✓ / 6 ✗ / 3 abstain). Withheld: **miss 18 · dispersed 37** — the
  first differentiated reach reading (run 5's 70 were one bucket): a third of the
  withholdings never had a posterior (retrieval reach), two thirds had one and lost the
  argmax (threshold/evidence). Disagreement 54/104: `abstain × report` **53** at −0.056/q
  (down from 75 at −0.333/q — the spend term now prices the baseline's $39.01 against
  typed's $16.03, so an abstain against a costly correct report is nearly break-even),
  `report × report` 48 at +0.401, `report × abstain` 1 at +1.576.
  **The two wrongs end the zero-wrong streak: q2-053 and q2-105.** q2-105 is one of the two
  golds *corrected* on 2026-08-14 (fax vs tel column order) — the typed arm asserted the
  pre-correction value, which the corrected gold now grades wrong; whether that is a true
  instrument error or a stale cached observation from the local-Ollama era is the first
  thing the run-7 attribution must settle (its extract cache is post-migration by
  construction, so the value came from the *new* instrument — a real miss). q2-053 is a
  fresh confident-wrong to audit.
  **Attribution — honest and split three ways.** Run 6 changed three things at once against
  the run 3–5 series (owner's call: migrate-first): (i) the instrument (haiku for qwen — the
  answer-rate jump 0.26→0.47 is the largest single move and is the instrument's), (ii) judge
  grading (net −3 on the mono arm, as the run-5 counterfactual computed: 96→93), (iii) the
  spend term (prices the baseline's outside-option cost for the first time; the
  `abstain × report` cell's per-question cost fell from −0.333 to −0.056). Which of the
  three carried the sign change is NOT separable from this run; the run-5 replay under (ii)+
  (iii) alone (its frozen actions, re-priced) is the deterministic counterfactual that
  isolates (i), and it is the named next computation — from the archived artifacts, no
  spend. **What survives without attribution:** the interval still crosses zero, so the gate
  is not passed; the reach lever now has a *direction* (18 miss vs 37 dispersed); the
  typed policy asserted twice wrongly on the new instrument, so its calibration on the base
  extract edge is the second thing to read (the eval_edge rows landed: 124 written).
  Spend: typed $16.03 (deliberate fired 43/104, warm 33; base instruments now metered),
  mono $39.01 replay-recorded. Elapsed 5397 s. **The first execution voided at question 27
  on a bridge wedge** (a hung-up client mid-`/narrative`, the single-threaded server stuck
  writing to a dead socket); its 39 salvaged edge rows were kept, the bridge hardened
  (`_respond` survives a broken pipe; the narrative path has its own 900 s budget), and the
  re-fire replayed the first 26 questions warm. The reading is the re-fire.

- **Run-5 attribution counterfactual — DONE (2026-08-17, the run-6 entry's named next
  computation; `scripts/gate_splice.py`, archived report
  `$LIFE_AGENT_KB/eval/gate-outside-option/counterfactual-run5-judged-priced-20260817.md`).
  Not a reading:** deterministic arithmetic on archived artifacts under the run-6 posterior
  (the harness first reproduces run 6 byte-for-byte from its own paired rows — the pin —
  then splices arms). Run 5's frozen typed actions (27 ✓ / 0 ✗ / 77 abstain, realised
  spend $1.71 exact from the decisions log) against run 6's mono grades (the identical
  replay, judge-graded, corrected golds) with both arms priced at the folded λ = 1.3311:
  **P(Δ>0.05) = 0.905, Δ̄ = +0.343 [−0.009, +0.786]** — the frozen bar, cleared, by the
  qwen-era arm. The ladder: 0.097/−0.232 (matcher, cost 0 — run 5 as published) →
  +judge 0.196/−0.135 (mono 96 → 95 net under the corrected golds; the run-6 entry's
  "96 → 93" was pre-correction arithmetic) → +spend 0.812/+0.245 → +both 0.905/+0.343.
  Run 6's live arm read 0.678/+0.180: **the typed-arm changes cost Δ̄ −0.163**, decomposed
  exactly at Ū — corrects 27 → 47 **+0.192**, two confident-wrongs (q2-053, q2-105) at
  u_wrong −9 **−0.173**, spend $1.71 → $16.03 **−0.183**. So run 6's sign change was
  carried by grading and pricing, not by the instrument; the instrument bought reach
  (0.26 → 0.47) and returned two thirds of it in wrongs and spend. **Spend anatomy:** $10.87
  of run 6's $16.03 is nine COLD deliberate probes (opus, $0.90–$1.43 each), and **every
  cold deliberate in runs 5 and 6 (13/13, $12.58) ended in abstain at p_none 0.50** — its
  conversions are all warm replays; the daemon buys it at the menu's declared USD 0.38 (the
  ff-v2 mean $/question) against a realised ~$1.21 at cold: the C2 priced-vs-enacted
  divergence, on the cost side. $13.10 of the typed spend fell on questions that still
  abstained. **Caveat, stated:** the typed-arm delta bundles instrument + live menu
  re-pricing (#67) + the 300-row curves; these artifacts cannot split it further, and the
  run-5 arm cannot be re-fired (local Ollama deprecated) — the counterfactual re-orders
  work, it does not pass anything. **Re-ordered next:** (1) the two confident-wrongs'
  audit — each is −0.087/q of Δ̄, the largest per-question lever on the board; (2)
  deliberate's cold-call pricing (cost AND rho — a $10.87 line that converted nothing);
  (3) reach for the 18 misses.

- **The two confident-wrongs, audited (2026-08-17) — neither is what the run-6 entry
  guessed.** **q2-053 was a stale gold, not an instrument miss.** The corpus holds Jim's
  report (29 Mar 2026: "Partial coverage in Sep 2025 (74.2%)") AND Guy's reply in the same
  thread the next day ("Sep 2025 is now at 97%"). The question is a current-value question;
  the typed arm asserted the newest attestation at 0.945 — exactly the SPEC §15.4 currency
  rule the `doc_date`/`era_split` covariates exist for. Runs 3–5 "got it right" only because
  the qwen-era extractor garbled the competitor into `go97%`, so 74.2% never had a rival.
  Corrected 2026-08-17 (the third disclosed gold change; `questions_v2.yaml.bak-20260817`):
  gold 97%, provenance moved to the superseding chunk (`e192b6ca…`, chunk 0). Run 6 stands
  as read; under the corrected gold it re-grades to typed 48 ✓ / 1 ✗ and **0.811 / +0.275
  [−0.111, +0.733]** (`counterfactual-run6-q053-corrected-20260817.md`, a footnote, not a
  reading). **q2-105 is a real coin flip stated at 0.93** — the chunk lists two unlabeled
  numbers (one row: an honorific-prefixed name, then the fax and tel in that order; the header is 113
  chunks away) and a CACHED opus deliberate read (from `gate-20260807T202838`; the deliberate
  key is (corpus, question, model) — independent of the base instrument, so the run-6 entry's
  "the value came from the new instrument" was wrong) picked the tel; run 5 abstained on the
  same read only because its thinner deliberate curve (44 rows) trusted the 0.93 less than
  run 6's (300 rows) did. The right behaviour on that chunk is hedge/corroborate; the
  reliability curve is the mechanism that learns it — **and it could not**: the 08-14 gold
  correction left that deliberate row, and four extract rows for q2-105 plus three for
  q2-018, graded CORRECT in the outcomes log (the writer dedups on §18.9 lineage, so a firing
  is never re-graded), all high-confidence "hits" the curves' top bins were fed. **Fix,
  append-only:** `calibration.edge_outcomes_from_log` now folds the LATEST row per (edge,
  lineage) — supersession, in the superseded row's place; lineage-less rows keep folding as
  before — and `scripts/regrade_edge_rows.py` re-grades the named questions' rows against
  the current gold with the writer's own matcher and appends superseding rows
  (`signals.regrade_of` / `superseded_grade` / `reason`; dry-run by default; idempotent).
  Applied 2026-08-17 (`outcomes.jsonl.bak-20260817`): **10 rows superseded** — 8
  CORRECT→INCORRECT (q2-018 ×3, q2-105 ×5: deliberate@opus 0.97 ×2, extract@haiku 0.92–0.95
  ×3, sonnet 0.85, opus 0.83–0.90) and q2-053's pair swapped (opus "97%" 0.95 → CORRECT,
  sonnet "74.2%" 0.85 → INCORRECT). Curve food in force: deliberate@opus 44/52 (was 46),
  extract@haiku 75/95 (78), sonnet 115/144 (117), opus 113/133 (114). The gate report now
  names rows *in force* beside rows logged. Run 7's LOO curves condition on this — the
  top-bin pessimism these eight rows buy is the calibration doing what §8 says it should.
  **Net for the reach reading:** of run 6's two wrongs, one dissolves (gold), one stands as an
  instrument-overconfidence the curves now see; the −0.173 wrongs term of the attribution is
  really −0.087, and the counterfactual's "run 6 minus the instrument" gap narrows from
  −0.163 to −0.076 (still negative: spend).

- **Run 6's cold deliberates were an instrument failure, cached as evidence (found
  2026-08-17, same audit).** All nine cold deliberate probes in run 6 (and three more in
  the voided first execution — twelve records, ~$14) declined NOT_IN_CORPUS with **zero
  tool calls**: the pkm MCP server never registered in the CLI session. Cause: the run
  launcher exported `LIFE_AGENT_KB` but not `PKM_CONFIG` (which lives in `.env`); the
  bridge's `_deliberate_cfg` read the raw env — unlike the rest of the bridge, which
  resolves `config.PKM_CONFIG` with its `~/.config/life-agent/pkm.yaml` default — and wrote
  `pkm --config "" serve` into the MCP config, which crashes on start (`IsADirectoryError`).
  Opus spent 82–183 s and $0.90–1.43 per call explaining it had no tools, and the bridge
  recorded the declines as `status=ok` ("a warm NOT_IN_CORPUS is valid evidence") — frozen
  absence for those questions under this corpus digest, replayed at $0 forever. **The
  contract already said it: "one empty search is not evidence of absence"; no search at
  all is less.** Fixed at three seams: `deliberate.answer` classifies a decline with zero
  tool calls as `status="error"` (retried once like any failure, never recorded) and
  `record_answer` refuses one; the bridge cfg resolves `config.PKM_CONFIG` and refuses an
  unresolvable one loudly; `run_eval --gate-executor` refuses before spend when deliberate
  is on and PKM_CONFIG does not resolve. The twelve poisoned records were voided through
  pkm's own removal path (`scripts/void_deliberate_poison.py`, manifest
  `deliberate-void-20260817T080054.json`; 67 → 55 deliberate records). **Pricing was never
  the problem:** across the 55 valid records the realised cost is mean $0.427 / median
  $0.364 against the menu's 0.38 — the "cost-side C2 divergence" named in the
  counterfactual entry above is withdrawn (its archived report carries the addendum). Run
  5's four cold calls ($0.31–0.59) were real reads that abstained. **What this does to the
  run-6 reading:** its typed arm ran with a broken deliberate rescue on every cold question
  — $10.87 of its $16.03 bought nothing by construction (−0.139/q of the −0.183 spend term),
  and nine `dispersed` withholdings never had the read the policy paid for. Run 6 stands as
  read (a reading is what happened); its interpretation is now: grading + spend carried the
  sign, the instrument bought reach, and the deliberate edge was absent. **Run 7 is the
  first reading with judge grading + the spend term + a working deliberate rescue + the
  three corrected golds + the regraded curve food, all at once — pre-registered here as
  the same recipe (`fire-run6.sh` with `PKM_CONFIG` exported), no other change.**

- **The 18 misses were the router, not retrieval — ROUTE_PROMPT v2 registered for run 8
  (2026-08-17, blind: run 7 was in flight on the old prompt when this was measured and
  written; run 7 is unaffected).** Audit of run 6's 18 `miss` withholdings: the gold chunk
  is in the FTS top-20 for **all 18** (rank 1 for 9, ≤ 4 for 15; the answer text verbatim
  in the gold chunk for 16) — retrieval reach is not the problem. **17 of the 18 never
  reached extraction: the haiku router answered `lookup: false`** ("What does GERT stand
  for?", "How many boys were named Eliran in 1990?", "Who appoints the external
  adjudicator?", "What is the prize amount per STA voucher?"), so the executor took the
  route-None narrative path and withheld; the 18th (q2-094) was routed and extracted
  `found:false` on the gold chunk. New instrument: `scripts/route_audit.py` — the router's
  confusion matrix on two labelled sets, the factory corpus (104, all positive by
  construction) and a separately hand-labelled mixed set (`$KB/eval/route-audit.yaml`: 40
  items, 19 positive NOT from the factory, 21 negative in the shapes the owner types —
  lists, aggregates, summaries, comparisons, multi-value asks — labelled by the prompt's
  own rule). **Current prompt: factory FN 17/104 (0.163), mixed FN 1/19, FP 0/21** — the
  router is fine on personal-record shapes and fails on document-content point facts
  (papers, theses, statistics, code); the "read off a *personal* document" wording is the
  defect. Iterated blind to the gate (four candidates, each measured on both sets, cents):
  v2 (broadened document kinds) FN 3 / FP 5 — over-admits lists and aggregates; v3
  (exclusions first, then inclusion) FN 10 / FP 1 — "total" over-triggers the aggregate
  rule on listed totals; **v4 (a listed total is one value): factory FN 1/104 (0.010 —
  q2-007, "how many … and at what price", two values by the rule), mixed FN 0/19, FP 1/21
  ("when did my father die and where" — admitted despite the rule naming it; not tuned
  away, over-fitting the labelled sample is the bias to avoid).** Landed as
  `lookup.ROUTE_PROMPT` (drift-gated on its document-kind vocabulary); the landed string
  re-audited as itself (`route-audit-20260817{,-landed}.md`) — same matrices — and its
  verdicts are already cached under the live key family, so run 8 re-routes at $0.
  **Pre-registration for run 8:** the run-7 recipe + this router; expected effect: up to
  16 more questions typed-eligible with the gold chunk at rank ≤ 4 for 13 — the answer
  rate is the diagnostic to watch, and any new confident-wrong on the newly-admitted
  questions is the first thing to audit (a route FP that asserts is exactly the u_wrong
  the router's narrowness was buying). The FP side is the named risk: a list/aggregate
  question admitted to the typed path extracts one value from many; the mixed set says
  1/21, and the `report_scoped`/hedge acts and the narrative fallback lane still exist
  behind it.

- **OPEN — the base extractor's ρ pools across models (found 2026-08-17).**
  `lookup.extract_instrument_hash()` is the prompt hash only, so `_extractor_outcomes`
  (the Beta(4,4) the bridge's `/extract` returns as the base ρ) conditions the HAIKU base
  extractor on the 23 `eval_lookup` rows graded on the qwen-era instrument (7/23 correct;
  posterior mean ≈ 0.36) — §2 says per-instrument, and the migration entry above says the
  model changed. Meanwhile the base firings write no `eval_edge` rows (only the tiers,
  rescue, re-extract and deliberate do), so nothing about the haiku base extractor is ever
  measured. Two ways out, both live-behaviour changes, so registered here and NOT bundled
  into run 8: (a) fold the model identity into the hash — the base ρ falls back to the
  Beta(4,4) prior mean 0.5 until haiku `eval_lookup` rows exist (only `run_eval --lookup`
  writes them), i.e. LESS pessimistic than today at first; (b) the cleaner design — the
  base extract firing becomes an attributed edge (`extract@<model>` per hit, the same
  namespace the corroborate tier already earns; the extract schema would need a
  self-report to condition on) and the base ρ reads through the per-edge curve like every
  other firing. Decide after run 7/8: if the newly-admitted questions (router v2) produce
  base-only confident-wrongs, (b) is the fix; if they abstain at the base and pay for
  tiers, (a)'s prior mean is not the risk it looks like.

- **Run 7 — the first PASS (2026-08-17, run `gate-20260817T160244`, master @ `b0147bf`,
  clean; the run-6 recipe verbatim with `PKM_CONFIG` exported — judge grading, λ_usd spend
  on both arms, availability censoring, corpus pin `full-2026-06-11` MATCHED, LOO curves,
  the three corrected golds and the regraded curve food in force): P(Δ>0.05) = 0.945,
  Δ̄ = +0.429 [+0.040, +0.884].** Guards: λ_usd folded 1.3311 (elicited); censored 0; the
  judge flipped **5 rows, all mono, the same five as run 6** (q2-021/028/035 C→I,
  q2-026/048 I→C), none typed — Δ trusted per the registration. Series: 0.002 → 0.010 →
  0.065 → 0.092 → 0.098 → 0.678 → **0.945**; Δ̄ −1.058 → … → +0.180 → **+0.429**. Typed
  **50 ✓ / 1 ✗ / 53 withheld** (answer rate 0.49; the one wrong is q2-105 — the cached opus
  coin-flip audited above, still asserting at 0.93 because its regraded curve row folds
  held-out for its own question, as LOO must) vs mono 95 ✓ / 6 ✗ / 3 abstain (0.97).
  Withheld **miss 18 · dispersed 35**. Spend typed **$5.56** (deliberate fired 39/104,
  warm 30, nine real cold reads) vs mono $39.01. Disagreement 52/104: `abstain × report`
  51 at **+0.200/q** (run 6: −0.056 — the failed deliberates' spend is gone from these
  rows), `report × report` 50 at +0.636, `report × abstain` 1 at +1.619. Elapsed 2007 s.
  **Against run 6, only what the audits fixed moved:** typed 47 ✓/2 ✗ → 50 ✓/1 ✗ (q2-053
  ✗→✓ by the corrected gold; two `dispersed`→✓ conversions from a deliberate that now
  reads; 53 abstains unchanged), spend −$10.47; mono identical. The counterfactual chain
  predicts it: run 6 under the corrected gold read 0.811/+0.275; removing the $10.87 of
  blind-decline spend is worth ≈ +0.14/q at the folded λ. **Not a new instrument, a
  repaired one.** (Report note: "495 in force (434 logged)" counted in-force rows after
  this run's 71 were appended — pre-run it was 424 in force of 434 logged; fixed in
  `run_eval` for the next run.) **What a PASS is and is not.** §8's bar is cleared at
  the frozen δ/level, on the pre-registered recipe, with every guard named above holding.
  It is one reading with the interval's lower end at +0.040 — just under δ — on the same
  104 questions the whole series has read; the reach diagnostics stand as they are (18
  route refusals, 35 dispersed with the gold leading under the bar in most). Adoption is
  the owner's rider (§13, §14 header): the consequences the code names — the uncalibrated
  fallback lane retired, the deliberate row un-gated at `ask.py`, typed as the silent
  default — are applied on the owner's adoption, not on this line. **Run 8 stays
  registered** (router v2 — the 17 route refusals) as the first reading past the bar
  with a materially different arm; a pass that survives it is worth more than this one.

- **Run 8 — router v2's reading: FAIL at P(Δ>0.05) = 0.857, Δ̄ = +0.344 [−0.109, +0.841]
  (2026-08-17, run `gate-20260817T164427`, master @ `d35b00c`, clean; the run-7 recipe
  verbatim, the ONLY code change ROUTE_PROMPT v2 as registered).** Guards all hold: pin
  MATCHED, λ folded 1.3311, censored 0, judge flipped the same five mono rows, none typed.
  Series: … → 0.678 → 0.945 → **0.857**. Typed **56 ✓ / 3 ✗ / 45 withheld** (answer rate
  0.49 → **0.57**, the series' highest), withheld **miss 18 → 2 · dispersed 43**, spend
  **$3.25** (deliberate 47/104, warm 43). **The router did exactly what was registered:**
  the 16 newly-admitted questions read 6 ✓ (q2-032/038/046/048/074/082) · 10 dispersed ·
  **0 wrong** — the named FP risk did not materialize on the admitted population; the two
  residual misses are q2-007 (v4's one known FN, two values by the rule) and q2-094
  (routed, extraction `found:false` on the gold chunk). **What failed the reading is two
  NEW confident-wrongs on questions routed identically in runs 6–7:** q2-053 flipped ✓→✗
  (the posterior now leads with the superseded 74.2% at 0.90 where run 7 led with the
  corrected-gold 97% at 0.94) and q2-090 flipped dispersed→✗ (asserted $1,234,567 at 0.93
  from a chunk carrying BOTH figures — the tiers graded the gold $7,654,321 C at 0.72–0.85
  and the competitor too; run 7's disagreeing deliberate forced the abstain, run 8's decide
  settled on the wrong leader). Their route verdicts are byte-identical under v2 and the
  construct wording maps to the same half-life — the only moving part is the **LOO curve
  fold, which grew by run 7's 71 edge rows** and re-priced the menu/conditioning, changing
  which transforms fired. **Named finding: the gate arm is not run-to-run deterministic,
  because the curve food grows between runs** — a same-recipe rerun of run 7 would also
  have differed. That is the §8 loop working as designed (decisions condition on
  accumulated evidence), but it means single-question flips near the bar are partly
  evidence-path variance, and it makes the pass/fail oscillation 0.945/0.857 read as ONE
  system straddling the bar, not a regression introduced by the router. With three wrongs
  at u_wrong −9, each is −0.087/q: remove the two new ones and this run reads above run 7.
  **What the pair of readings says together:** the reach levers work (miss 18 → 2, answer
  rate 0.57, spend $3.25) and the binding constraint is now **wrong-leader commits on
  multi-value/two-era chunks** — q2-090's two-figure chunk and q2-053's two-era pair are
  the same shape as q2-105's two-number row: the posterior trusts a single confident read
  over in-chunk competition. Named next lever, in order: (1) the **competing-values
  temper** — when the evidence set itself contains a second value graded plausible (or a
  two-figure chunk), the commit bar should feel it (this is §4.2's indeterminacy/competition
  term, under-weighted at the terminal); (2) then corroboration on sub-bar leaders (the 43
  dispersed, gold leading in most). Adoption stance unchanged: run 7's PASS stands as the
  first, run 8 does not revoke it (different arm), and the owner's rider decides — but the
  honest summary for that decision is "the system straddles the bar; the wrong-commit class
  is identified and unfixed."

- **The wrong-commit class is in-chunk competition the record cannot see — competing-values
  temper registered for run 9 (2026-08-17; the sweep saw the golds, disclosed below; the
  (detector, factor) choice frozen on criteria stated before results were read).** Run 8's
  three ✗ are one shape and two of them were INVISIBLE to the archive: q2-053 committed the
  superseded 74.2% at 0.8997 (runner-up, the corrected gold 97%, at 0.033); q2-090 asserted
  $1,234,567 at 0.926 SINGLE-CANDIDATE — the gold $7,654,321 sits in the same chunk and
  `posterior_summary` carries only the candidate list, so the record says nothing; q2-105
  asserted the row's TEL at 0.927, single-candidate, the gold fax in the same
  row. Root cause is structural: `EXTRACT_SCHEMA` returns ONE value per chunk, so in-chunk
  competition never leaves the extractor — no downstream term can see it. **The mechanism**
  (doctrine-constrained: §4.4's collapse theorem forbids caution via utility width, and
  `decide`'s no-host-argmax contract forbids a veto, so the temper is observation-likelihood
  side): a pure host-side detector (`matching.quote_scoped_competitors` — a distinct
  same-shape numeric span, percent class included, within ±120 chars of the extractor's own
  grounded quote) sets a per-observation `competition_factor = 1/2` (cap FROZEN at 1),
  multiplied into r exactly where authority is, on BOTH commit sites (host
  `lookup_posterior` group covariate; daemon `observation_densities`, credence `f474e70`,
  wire default 1.0 = temper off for a version-skewed pair; parity-by-identity test:
  factor 0.5 ≡ authority halved). Post-extraction and consumer-side over the raw cached
  record — the §18.9 extraction cache and the rho evidence pool are untouched; warm
  replays re-detect. A tempered leader lands below the emergent bar, and the daemon's
  `below_bar` trigger re-opens the VOI ladder — run 7's q2-090 abstain-via-deliberate is
  the precedent that the flip is a floor, not a ceiling. **New instrument:**
  `scripts/temper_audit.py` — all 104 run-8 rows (59 commits + 45 withheld) joined back to
  their evidence chunks at $0 and zero model calls (extract-cache proof 97 — a warm §18.9
  hit for (question, chunk) is deterministic proof run 8 extracted that chunk; deliberate
  tool-calls 3, catalogue containment 1, both flagged; unrecovered q2-047 + no-decision
  q2-007/q2-094, named). Detector sweep D1 whole-chunk / D2 ±400-window / D3 quote-scoped
  (D3 added AFTER D1/D2's collateral was read — a post-look candidate, disclosed) × caps
  1–3, tempered p by exact k=1 single-obs channel inversion (the analytic odds scaling
  under-tempers; exact flips ⊇ analytic). All candidates flip 3/3 wrongs; collateral among
  the 56 ✓ is the discriminator: D1 33–34, D2 28, **D3 21 — frozen (minimal collateral,
  weakest sufficient temper)**. The empirical population check supports the mechanism:
  commits with competition fired read ~24✓/27 ≈ 0.89 realised accuracy at stated ~0.92 —
  under the 0.899 bar, so the temper is roughly the calibration correction, not a blunt
  penalty. **Counterfactual** (`gate_splice`, run-8 pin 0.857/+0.344 reproduced;
  `counterfactual-run8-temper-20260817.md`): floor (24 flips → dispersed, spend kept)
  **0.945 PASS, Δ̄ +0.401 [+0.043, +0.851]**, answer rate 0.57 → 0.34; no-recovery stress
  (+$0.45/flip, nothing recovered) 0.799/+0.262. The true run-9 reading sits between: live
  flips re-open the ladder and deliberate recovers some collateral as corrects (at spend).
  **Blindness:** the golds for all 104 questions are known to the sweep and D3 was added
  post-look; the choice is frozen on the pre-stated criteria and run 9's fresh firing is
  the test. **Honesty on q2-053:** its competition is CROSS-document (74.2% and 97% a day
  apart in one thread) — the in-chunk detector fires on it incidentally (other percents in
  the report chunk), but the class is supersession, not in-chunk competition; the
  within-days case is structurally outside `era_split`'s half-life test and stays OPEN
  (remedy: a supersession signal, e.g. reply-quotes-original). **Also landed with this
  change (replayability fix):** both `posterior_summary` writers now record
  `n_indeterminate` + `n_competing` (the bridge path dropped the former; run 8's
  single-candidate blindness is what forced this sweep to re-join chunks), and the join's
  correction-shape guard now delegates to the same shared span detector (comma-grouped
  figures are one shape, not three fragments). **Amended before firing (same day): the
  join channel inherits the temper.** The first draft left corroborate/deliberate join
  observations at implicit factor 1.0; walking the run-9 prediction for q2-105 exposed
  that as wrong — run 8's q2-105 commit WAS a warm deliberate confirm of the tel from the
  same fax/tel row (`instrument: deliberate@…`, $0), so an untempered join would re-commit
  exactly what the temper withheld. §2's lineage rule decides it: competition is a
  property of the corpus row, not the instrument — a whole-doc re-read of the same
  competed row shares the pick ambiguity (q2-105's opus deliberate DID pick the wrong
  column: 1/1 on the only measurement). The body now posts `candidate_competition` (each
  candidate's base-observation factor) with the join calls and the join observation
  carries it; a minted new candidate reads 1.0, and run 7's disagree⇒abstain contract is
  untouched. Consequence, named: same-doc re-reads can no longer rescue a competed
  leader past the bar alone — rescue needs independent-document corroboration or a
  disagreeing/new-value read, so run 9's answer rate should sit near the counterfactual
  floor's 0.34 and q2-105 is predicted dispersed, not wrong.

- **Run 9 — the temper's reading: PASS at P(Δ>0.05) = 0.938, Δ̄ = +0.390 [+0.032, +0.841]
  (2026-08-17, run `gate-20260817T195737`, master @ `efce4e6`, credence @ `f474e70`,
  clean; the run-8 recipe verbatim + the registered temper as the only decision-path
  change).** Guards all hold: pin MATCHED, λ_usd folded 1.3311, censored 0, judge flipped
  the SAME five mono rows as run 8 (q2-021/026/028/035/048), none typed; curves held out
  over 611 pre-run rows in force (621 logged); pin banked (`gate_splice --pin` reproduces
  0.938/+0.390). Series: 0.002 → 0.010 → 0.065 → 0.092 → 0.098 → 0.678 → 0.945 → 0.857 →
  **0.938 — the second PASS.** Typed **35 ✓ / 0 ✗ / 69 withheld** (miss 2 · dispersed 67),
  answer rate 0.57 → 0.34 with correct-report rate = answer rate — **zero wrong commits,
  the first run in the series where every typed assert is correct.** Spend $4.10
  (deliberate 60/104, warm 53) vs mono $39.01. **Every registered prediction held, some
  exactly:** the counterfactual floor said 0.945/+0.401/rate 0.34 — the live run read
  0.938/+0.390/0.34; q2-053, q2-090, q2-105 all dispersed (the wrong-commit class closed);
  all 21 predicted collateral corrects dispersed and NONE recovered via same-doc re-reads
  (the join-inheritance consequence, as amended pre-firing) — the 35 asserts are exactly
  run 8's 56 ✓ minus the sweep's 21, i.e. the off-gate sweep predicted the live assert
  set perfectly; the competition field fired on 43/102 decide rows (27 of run 8's commits
  plus dispersed-set rows, consistent with the sweep). The pre-fire smoke (q2-105
  off-gate: abstain, `n_competing 9`, $0) is in the decisions log. **What the reading
  says:** the temper converts the wrong-commit class into withholding at the price of
  reach — Δ's positive mean is now carried by u_wrong avoidance plus the spend gap, and
  the honest cost is the answer rate (0.34, floor-shaped, because the only rescue the
  temper permits is independent-document corroboration or a disagreeing/new-value read —
  same-doc confirms inherit the ambiguity). Named next lever (unchanged in kind,
  sharpened in target): reach on the 67 dispersed — (a) corroboration on sub-bar gold
  leaders across INDEPENDENT documents (the only path the temper leaves open, and the
  run-8 reading's lever 2), (b) the 19-question n_obs=0 retrieval-failure cluster the
  sweep separated from the near-miss cluster. Adoption stance: two PASSes (runs 7, 9) of
  the last three at the frozen bar, and run 9's arm never wrong-commits; the owner's
  rider (§13) decides — the honest summary is now "passes the bar with zero wrongs at
  answer rate 0.34; reach is the remaining cost, and it is priced, not hidden."
  **Pre-registration for run 9:** the run-8 recipe verbatim (`fire-run9.sh` — with a
  stale-stack kill: fire-run8.sh reuses a listening daemon via the `/ready` short-circuit,
  which would silently run the un-tempered code) + the temper as the only decision-path
  change (life-agent `f68dced`+`1cebc87` + the join-inheritance amendment commit,
  credence `f474e70`). Expected effect: the
  in-chunk wrong-commit class stops committing (floor: → dispersed; ceiling: deliberate
  recovers the gold); predicted floor reading 0.945/+0.401. Diagnostics to watch: typed
  wrong count (the headline), the competition field's fire count vs the sweep's 27
  competed commits, dispersed count (45 + collateral − recoveries), spend (re-opened
  ladders; envelope $5–8 vs run 8's $3.25). Named risk: collateral tempering of
  legitimately-committed multi-number answers (21/56 in the sweep — the answer-rate cost
  is the price of the wrong-commit class) and spend growth; fallback — a tempered question
  lands withheld, never wrong-committed, and the narrative lane exists behind the typed
  path.

- **§13 adoption rider — RESOLVED (2026-08-17, owner interviewed, master @ the commit
  carrying this entry).** On the evidence of two PASSes at the frozen bar (run 7 0.945,
  run 9 0.938) with run 9's arm never wrong-committing, the owner adopted, with three
  explicit choices: **(1) typed is the default** answer path (it already was the
  read-path default with a named down-stack fallback; the adoption makes it the *silent*
  default in the contract's sense — no pending-gate caveats). **(2) Honest withhold
  only:** the uncalibrated dual-lane fallback is **removed**, not just left off — its own
  registration (interaction contract, *know*) named removal-on-adoption as its destiny.
  A typed withholding renders the named reason and held-back candidates, nothing else;
  `LIFE_AGENT_FALLBACK_LANE`, `config.fallback_lane_enabled`, the two GRAMMAR templates,
  the executor lane render, and the gate's disarm machinery are all deleted (a stale flag
  in someone's `.env` is ignored). **(3) The deliberate edge is always-on:** the arm the
  gate measured and the owner adopted IS the deliberate-on arm, so running the daily path
  without it would be an unmeasured configuration wearing the gate's evidence.
  `config.deliberate_enabled()` now defaults on; `LIFE_AGENT_DELIBERATE=0` is the
  rollback lever (the only disabling value); the daemon's EU pricing remains the spend
  governor, and the run-6 PKM_CONFIG guards (bridge per-call + gate preflight) hold
  unchanged. Rejected alternatives, for the record: a labeled mono fallback and
  fallback-on-request (both offered; the owner chose the pure contract), a replication
  run 10 before adoption, and a spend-capped deliberate. Sequencing decided in the same
  interview: two $0 ceiling audits before the next build — (a) rescuability of the 67
  dispersed (does an independent second document carrying the gold value exist per
  question?), (b) the 19-question n_obs=0 cluster (query-building failure vs corpus
  absence) — then MVP M-0 (the Telegram ask intent) as the next build, because it makes
  the adopted arm reach the owner and starts accruing *live* decision/outcome rows (the
  distribution that matters post-adoption is the owner's real questions, not the q2
  benchmark's); the eval lever between (a) and (b) is picked afterwards on the audited
  ceilings.

- **Reach-audit reading (same day, `scripts/reach_audit.py`, $0 deterministic, criteria
  frozen in its docstring before results):** over run 9's 69 withheld questions —
  **rescuable-retrieved 40 · rescuable-unretrieved 17 · single-doc 12 · gold-absent 0**
  (classes in the gate's own grading currency, `matching.answer_matches`; the counts are
  optimistic ceilings — token containment of a common gold value inflates `docs`, e.g.
  3,438 artifacts "carry" one gold — but the *class* only needs one true independent
  carrier, and the buildable class additionally requires it inside the deterministic
  top-20). The n_obs=0 cluster (19 rows incl. the 2 unlogged misses) read
  **retrieved-not-extracted 19 / not-retrieved 0 / absent 0** — so the "retrieval-failure
  cluster" name was WRONG and is retired: every one of the 19 already had a gold-bearing
  chunk inside the top-k; the loss is extraction/observation-side (the one-value-per-chunk
  extractor and the grounding gates), not query-side. Under the frozen rule the lever
  choice is decided, not judged: **independent-document corroboration, buildable ceiling
  40/69** (retrieval lever ceiling 0; a retrieval change would add at most 17 more
  rescuables later). single-doc 12 stays the temper's standing price; gold-absent 0 means
  nothing withheld is unanswerable on this corpus. Artifacts:
  `$LIFE_AGENT_KB/eval/reach-audit-20260817.{md,yaml}`. First pass of the audit shipped a
  broken decisions join (qid vs content-addressed hash — every row read as unlogged) and
  was corrected and re-run before any reading; disclosed here because the class counts
  happened to be join-independent and identical across both runs.

- **confirm_indep — the corroborate audit's NEGATIVE reading (2026-08-18,
  `scripts/corroborate_audit.py`, live haiku, $0.06): the frozen criteria REFUSE the
  wiring, and the reach audit's 40-ceiling is retired as carrier-count inflation.**
  The mechanism was built first (commit `6050657`, phases 1–3 of the registered plan):
  a value-targeted independent confirm instrument (`lookup.confirm_hits` +
  `CONFIRM_PROMPT`, cached under `lookup_confirm_key` with the target value in the key
  inputs), a production `/probe/confirm` bridge endpoint (supporter exclusion via a
  warm `observe_hits` replay that also reproduces the wire group order; each grounded
  confirm is a REAL observation on its own artifact with its OWN quote-window
  competition factor — §2's corpus-row rule, deliberately not the same-doc
  inheritance; forwarded copies killed by `dedup_correlated` at the one seam), and an
  off-gate audit that drives that exact handler over run 9's 69 withheld, m∈{1,2,3},
  reading criteria frozen in the docstring before results (wire iff zero wrong-rescue
  flips AND predicted rescues ≥ 5; m = smallest within 0.9× of m=3; analytic-append
  prediction mode disclosed as optimistic). **The reading: rescue-class 6 ·
  wrong-rescue 3 · no-confirm 58 · no-leader 2 (the n_obs=0 rows, named excluded);
  predicted flips at frozen m=2: rescues 3 (q2-043, q2-059, q2-093), wrong-rescue
  flips 1 — NO-GO on both criteria.** What actually bound: the instrument grounded 63
  confirms, and **48/63 were dropped by the §5 correlated-copy guard** — the corpus's
  "independent" gold carriers are overwhelmingly forwarded/quoted email-chain copies
  of ONE underlying attestation (q2-039's nine carriers are all `>>`-quoted re-sends
  of the same Oxford line; q2-105's lone carrier is a re-send of the same signature
  row). The reach audit's `rescuable-retrieved 40` counted those copies as independent
  documents; the measured true-independence ceiling is ~6 questions — **under the
  reach audit's own "a ceiling under ~10 is not worth building pre-dogfood" line, so
  the two frozen rules now agree.** The wrong-rescue flip is a named defect class
  caught pre-production: q2-019's leader is a TRUNCATION of its gold (the gold is a
  three-token personal name; the leader is its two-token suffix — values withheld,
  this repo is public), and chunks carrying the FULL name "confirm" the partial value,
  because token containment cannot tell a value from its own extension;
  q2-002/q2-006 are the same class without the flip. Registered follow-ups IF this lever is revisited (never a
  silent retry): (a) a strict-span guard — refuse a confirm whose matched span
  extends beyond the target's tokens (the q2-019 class, computable host-side, $0);
  (b) the sonnet-tier sweep the tier criterion names. Disposition: the instrument,
  endpoint, and audit stay in-tree, tested and DORMANT (nothing on the decision path
  calls `/probe/confirm`; no menu row was added — the run-10 pre-registration never
  happened, per the no-go). What the evidence now points at, in order: the
  extraction-side n_obs=0 class (19/19 retrieved-not-extracted — the one-value-per-
  chunk extractor, the largest measured class), and live dogfood on the deployed
  adopted arm (the owner's real distribution — both audits' remaining eval-lever
  ceilings are under the build bar). Artifacts:
  `$LIFE_AGENT_KB/eval/corroborate-audit-20260818.{md,yaml}` (+ the synthetic paired
  files, unread — the splice is only licensed by a GO).

- **The n_obs=0 cluster is DECISION-SIDE, not extraction-side — the replace contract
  erases a grounded channel (2026-08-18, `scripts/extraction_audit.py`, $0, zero model
  calls). The cluster's name has now been wrong twice; this entry retires the second
  name and records what the evidence actually shows.** The audit was built to ask which
  extraction defect lost the 19 (criteria frozen in its docstring: classes
  declined/picked-other/ungrounded/grounded/no-cache-record; build bar = DELIVERED
  REACH ≥ 10 questions, counted in questions whose commit would change — the
  confirm_indep lesson written in as a rule; and, because the run's own median leader
  credence at n_obs=1, K=1 is **0.861 over 51 rows, below the 0.8997 commit bar**, a
  rescue counts only with ≥2 independent fixable artifacts). Its literal reading:
  declined 25 · picked-other 24 · ungrounded 1 · no-cache-record 1 — delivered reach
  **4** (q2-004, q2-006, q2-083, q2-105), far under the bar, so no extraction lever is
  a build. **But the frozen `grounded` anomaly class — registered as "an anomaly by
  construction, NAMED, never silently dropped" — read 69**, and that is what broke the
  cluster open: 69 gold-bearing chunks across these questions carry a CACHED extraction
  that found the gold and passes the grounding gate, all written 2026-08-17 12:00–16:00
  (runs 6–8), i.e. warm and available to run 9. Extraction did not fail. Reading the
  run-9 decision rows directly settles it: **17 of the 19 carry K ≥ 1 candidates with
  n_obs = 0 and credences that are EXACTLY uniform at p_none 0.5 — the untouched prior**
  (q2-083: candidate `$0`, the gold, alone at 0.5; q2-025: four candidates at 0.125,
  the gold among them). Candidates can only be minted from grounded observations
  (`candidates_from(observations)` at `/extract`), so observations existed at extract
  time and were gone at decide time; the only code paths that empty the observation
  vector while keeping the candidate lattice are the three replace branches
  (corroborate tier / deliberate / re_extract_strong), and `tests/test_executor.py`
  already pins that signature exactly — a corroborate reply of `{"observations": [],
  "value": None}` yields a re-decide whose payload carries the candidates with
  `observations == []`. **Gold is already among the candidates in 14 of the 19.**
  Attribution, and an instrumentation gap named: 5 rows record
  `instrument: deliberate@claude-opus-4-8` (whose contract explicitly collapses the
  channel on an empty-ok reply); the other 12 record `instrument: ""` because a
  corroborate TIER firing never sets the decision record's instrument field — from the
  log alone you cannot tell which probe erased the channel, and run 9's warm tier
  replays were lineage-deduped out of the fresh edge-outcome rows, so the edge stream
  does not carry them either. **What this means:** the single largest named cause of
  lost reach in run 9 is not retrieval (ceiling 0), not extraction (delivered reach 4),
  and not the temper's single-doc price (12) — it is **17 questions whose grounded
  evidence a probe discarded**, 14 of them with the gold already on the lattice. The
  suspected over-strong inference is precise and doctrinally shaped: the code treats
  "the re-read NAMED NOTHING" identically to "the re-read DISAGREED", but a null read
  from a lossy whole-document instrument is absence of evidence, not evidence of
  absence — and the fail-open precedent already exists one branch away (a deliberate
  INFRASTRUCTURE failure keeps the channel). **Not built, not measured, deliberately:**
  the counterfactual (warm-replay each of the 17 with the null-read branch retiring
  fail-open instead of replacing, then re-decide) needs the live stack and must carry
  its own frozen criteria and pre-registration before any run 10 — run 7's
  disagree⇒abstain contract stays untouched either way, since a null read is not a
  disagreement. None of this disturbs run 9's PASS or the §13 adoption: the erasure is
  conservative (it withholds, never wrong-commits). Artifacts:
  `$LIFE_AGENT_KB/eval/extraction-audit-20260818.{md,yaml}`.

- **Pre-registration for run 10 — the null-read fail-open (2026-08-18, written and
  committed BEFORE the run, branch `fix/null-read-failopen`).** *Defect:* the previous
  entry's reading — 17 of run 9's 69 withholdings are a grounded channel a
  replace-branch probe erased, the gold still on the lattice in 14, the posterior sitting
  at exactly its flat prior. *Mechanism (the only decision-path change):* the bridge now
  classifies its own empty channel and the body reads that classification. `/probe/corroborate`
  returns `read ∈ {confirm, disagree, null}`: **`null`** = the joint named NO value —
  a lossy whole-document read over 400-char snippets declining to answer, which is
  absence of evidence about the per-chunk observations already grounded; **`disagree`** =
  it named a value that would not join the lattice (outside the set, ambiguously
  contained, or correction-shaped) — evidence AGAINST the leader. On `null` the executor
  retires the probe **fail-open** and the grounded channel stands (the treatment the
  deliberate branch already gives an infrastructure failure); on `disagree` it replaces
  exactly as before, so **run 7's disagree⇒abstain contract is untouched by
  construction**. A bridge predating the field sends no `read`, and the body falls back
  to replace — version skew degrades to the previously MEASURED contract, never to an
  unmeasured one. *Scope, and why it is not all 17:* the change covers the joint re-read
  sites only (the corroborate tiers and `re_extract_strong`). **The deliberate edge is
  deliberately NOT changed** — its empty-ok reply is a whole-corpus agentic search
  reporting NOT_IN_CORPUS, which IS evidence for NONE, unlike a re-read of the same 20
  chunks; 5 of the 17 rows are deliberate-attributed and are expected to stay withheld.
  The remaining 12 record `instrument: ""` because a tier firing writes no instrument to
  the decision record, so **the exact tier/deliberate split is unprovable from the log
  until the attribution gap closes** — that is registered here as a limitation of the
  prediction, not a claim. *Frozen constants, unchanged:* δ = 0.05, level = 0.90, the
  same utility posterior and judge grading; run 9's recipe verbatim otherwise (credence
  pin `f474e70` untouched — no Julia change). *Predictions:* (1) run 9's 35 asserts are
  unchanged, since the change can only fire where a null read fired; (2) up to 12
  withholdings regain a channel, and each COMMITS only if its restored posterior clears
  the bar on its own — the pre-collapse credence is not recorded anywhere, so the
  conversion rate is genuinely unknown and run 10 is the measurement; (3) answer rate
  rises from 0.34; (4) spend is ~flat (the same probes fire, nothing new is bought).
  *Named risk, stated plainly:* restoring a channel the erasing contract had been
  suppressing can surface a WRONG leader that clears the bar — this is the first change
  in the arc whose failure mode is a wrong commit rather than a withholding, and the
  zero-wrong streak (runs 9) is what it puts at stake. *Diagnostics to read:* typed wrong
  count (the headline), the count of null reads that fired, how many of the 17 changed
  action, answer rate, spend. *Rollback:* revert the commit — there is no env flag, and
  one must not be invented at read time.

- **Run 10 — the null-read fail-open's reading, contaminated: FAIL at P(Δ>0.05) = 0.861,
  Δ̄ = +0.323 [−0.074, +0.787]** (2026-08-21, `gate-20260821T094545`; typed 36 ✓ / **1 ✗** /
  67 withheld, miss 2 · dispersed 65, answer rate 0.36 at $3.28 vs mono 0.97 at $39.01;
  deliberate 68/104, warm 68; LOO curves over 737 rows). The zero-wrong streak ends at one row,
  and both frozen criteria are missed. *The failure is a single question.* `gate_splice.py`
  ($0, both sanity pins reproducing their published verdicts first): the same run with that one
  row withheld reads **0.952 / +0.410 [+0.053, +0.857] — PASS**, stronger than run 9, because
  the tree also converted a withholding *correctly*. So the arm did not get worse; it converted
  two withholdings (dispersed 67 → 65) and one of them was wrong, which at u_wrong = −8.9993
  is worth −0.087 in Δ̄. *The predictions held in aggregate:* answer rate rose from 0.34 as
  predicted, spend was flat-to-down, and the conversion count sits inside the "up to 12"
  envelope — but the pre-registration's **named risk materialised on the first run that could
  express it**: a restored channel surfaced a wrong leader that cleared the bar. The row's
  posterior signature is the change's own: the candidate set grew from one (the gold, sole
  candidate in runs 7–9) to two with a same-shape competitor leading at 0.902 and the gold
  demoted to 0.033, while p_none collapsed 0.181 → 0.066 and the grounded observation count did
  not move. *What this run CANNOT say, and the reason it is filed as contaminated:* four
  decision-path changes were in the tree, not one — the null-read fail-open (08-19), R2's
  declared retrieval order (08-20), §6.9's declared probe order (08-21) and tranche-2 M1's
  executor deletion (08-21) — and **three of the four are structurally invisible to the
  decision-equivalence oracle**, because the fixture set tapes the bridge at the `http` seam and
  replay never executes bridge code. Attribution by argument is therefore refused. Two of the
  three were nonetheless measured directly against the corpus ($0, read-only): both declared
  orders cost the gold one distinct carrying document on that question (primary 7→6, probe 9→8)
  and cost the competitor none — but the competitor is retrieved under *both* orders, so neither
  order put it on the lattice; they moved the margin, not the candidate set. The carrier loss
  has its own mechanism worth recording: 20 of the question's 59 deduped chunk texts are carried
  by more than one document, the declared key flips which document *represents* 9 of them, and
  2 of those carry the gold at exact score ties — byte-identical text, different carrier. If two
  documents carry identical text they are one attestation (§5), so that swap should be a
  downstream no-op and it is not. **What decides the open part:** separated gate runs, cheapest
  first — run 10's tree minus the null-read change isolates it against the archived monolithic
  arm at ~$3–4, with no re-firing of the mono side. Whether the fail-open takes the rollback its
  own pre-registration names is not settled by this run and is not settled here. Registered with
  it: **§6.10 of the collapse design — a gate run must pin its tree, not just its recipe**; the
  fire script asserted the presence of the change under test and nothing about the rest of the
  decision path, which is why a priced run was spent without buying an attributable reading.

- **Pre-registration for run 11 — the null-read fail-open, isolated (2026-08-21, written and
  committed BEFORE the run).** *Why:* run 10's reading is contaminated — four decision-path
  changes in one tree, three of them invisible to the 7.2 oracle — so neither the fail-open's
  own pre-registered rollback nor its exoneration can fire on it. This run buys the isolation.
  *The only change:* run 10's tree with the null-read fail-open reverted, fired from a worktree
  so master keeps the change until the reading rules on it. Everything else is byte-identical to
  run 10: same recipe, same corpus pin `full-2026-06-11`, same frozen δ = 0.05 and level = 0.90,
  same utility posterior and judge grading, same credence pin, and the monolithic arm is the
  ARCHIVED one — it is not re-fired, so the comparator cannot drift. The tree difference is
  exactly one revert, and §6.10's tree pin records it rather than asserting it.
  *Frozen decision rule (owner, blind, before firing):* the fail-open's rollback becomes
  **permanent iff run 11 reads wrong commits = 0 AND P(Δ>δ) ≥ 0.90** — the gate's own bar, both
  criteria, exactly what M1 was held to. Explicitly NOT a single sub-criterion, and explicitly
  NOT the behaviour of one row: reading one borderline row is what put the previous checkpoint
  in trouble. *Pre-committed branch, blind:* if run 11 still fails with a wrong commit, the
  fail-open is **exonerated** and the ladder escalates to the next isolation (tree minus R2's and
  §6.9's declared orders, ~$3–4) — no re-diagnosis by argument at that point. *Predictions:*
  (1) q2-011 returns to a withholding, since the second candidate that displaced the gold is the
  signature of a restored channel; (2) typed asserts fall from 37 toward run 9's 35, and the
  answer rate from 0.36 toward 0.34; (3) spend is flat-to-down — nothing new is bought and the
  deliberate cache is warm; (4) the two declared-order changes and M1's deletion remain in the
  tree, so any residual difference from run 9 is theirs. *Named risk:* if run 11 passes, the
  fail-open is convicted on one wrong row out of 104 — a thin basis for reverting a
  pre-registered change, and the entry records that thinness rather than hiding it; the
  conviction is of the CHANGE's cost/benefit at this corpus size, not of its reasoning.
  *Diagnostics to read:* wrong-commit count (the headline), P(Δ>δ), q2-011's terminal and
  candidate-set size, answer rate, spend, and §6.10's tree diff against run 10.

- **Run 11 — the null-read fail-open, isolated and EXONERATED: FAIL at P(Δ>0.05) = 0.880,
  Δ̄ = +0.343 [−0.057, +0.810]** (2026-08-21, `gate-20260821T190058`; typed 36 ✓ / **1 ✗** /
  67 withheld, miss 2 · dispersed 65, answer rate 0.36 at $1.73 vs mono 0.97 at $39.01;
  deliberate 68/104, warm 67; LOO curves over 784 rows). Run 10 with the fail-open reverted
  and nothing else changed but §6.10's tree pin. Against run 10 (0.861, +0.323, 36 ✓ / 1 ✗ /
  67, answer rate 0.36) the reading is **materially unchanged**, and the single wrong commit
  is the same question. The frozen rule required wrong = 0 AND P ≥ 0.90 for the rollback to
  become permanent; neither holds, so **the pre-committed branch fires: the fail-open is
  exonerated, its rollback does NOT fire, and master keeps it.** Its own prediction (1) —
  that the row would return to a withholding — is falsified. *§6.10's first live use:* the
  report carried the tree diff, naming two decision-logic files (the revert) and one harness
  file (the pin itself), which is exactly what moved.
  **Two findings the isolation surfaced, neither of them the fail-open.**
  *(a) Runs 7, 8 and 9 all fired the LEGACY cascade lane.* The gate arm's lane flag defaulted
  off and no fire script ever set it — recorded in each run's own `env_flags` as an empty
  string, and visible only because the recording was retired at M1 as false provenance. Run 10
  is therefore the first gate run ever to use the priced lane, so tranche-2 M1's deletion did
  not merely remove dead code from the gate's path: it **switched the arm's lane**. The 104/104
  equivalence replay proved the deletion does not perturb the priced lane; it never spoke to
  legacy-versus-priced, and the checkpoint's own report says so. This was unnoticed for four
  runs.
  *(b) The cause of the wrong commit is §6.9's declared probe order, and the earlier
  exoneration of it was wrong.* The M0.5 recordings are LIVE runs and pin their trees, which
  gives a controlled comparison with the lane held at priced and R2, the corpus, the golds and
  the utility fold all constant: at `861ea1b` (priced lane, R2 present, fail-open present,
  **§6.9 absent**) the row carries ONE candidate — the gold — and abstains; at run 10 and again
  at run 11 (**§6.9 present**) it carries two, a same-shape competitor leads, and it commits
  wrong. The legacy-lane recording abstains with one candidate too, so the lane is not the
  discriminator either. *The reasoning error, recorded because it is repeatable:* §6.9 was
  exonerated on the finding that the competitor is retrieved under BOTH orders, hence the
  reorder could not have put it on the lattice. That conflates retrieved with extracted — the
  probe's top-k is what the extractor reads, so a different set of chunks yields different
  observations and a candidate can enter without the underlying search returning anything new.
  The measurement that should have carried the inference was already in hand: §6.9's order costs
  this question one gold-carrying document in the probe's top-k (9 → 8) and costs the competitor
  none. **What decides it:** run 12, §6.9 reverted alone — a narrowing of run 11's pre-committed
  escalation (which named R2 *and* §6.9), justified by R2 being held constant across the
  controlled comparison above and recorded here rather than taken silently.
  *Limitation, stated:* each run appends its outcomes, so the LOO curve fold grows between runs
  (737 → 784 rows here); the series has always had this and it is not controlled.

- **Pre-registration for run 12 — §6.9's declared probe order, isolated (2026-08-21, written
  and committed BEFORE the run).** *The only change:* run 11's tree with §6.9's declared key
  reverted in `probe_corroborate` and nothing else — the fail-open is restored to master (run
  11 exonerated it), M1's deletion and R2's order stay. Same recipe, corpus pin, δ = 0.05,
  level = 0.90, utility posterior, judge grading and credence pin `f474e70`; the monolithic arm
  is the archived one and is not re-fired. §6.10's tree diff will name the change.
  *Frozen decision rule, blind:* §6.9's key is convicted as the mover of the wrong commit iff
  run 12 reads **wrong commits = 0 AND P(Δ>δ) ≥ 0.90** — the same bar runs 10 and 11 were held
  to. If the row still commits wrong, §6.9 is exonerated too and the remaining suspects are
  R2's order and M1's lane switch, which the controlled comparison could not separate because
  both were present in every wrong run.
  *Stated in advance, because it governs what a PASS may be read to mean:* reverting §6.9
  restores a nondeterministic order, so a pass would convict the declared key as **the thing
  that moved this row on this corpus** — never as wrong, and never as an argument for keeping
  arrival order. The old order is a different ticket in the same lottery; runs 7 and 8 won it
  and run 10 lost it. **A pass therefore does NOT license reverting §6.9 as the fix.** The fix
  it licenses is the carrier-identity work already registered for its own checkpoint: byte-
  identical text carried by several documents, where which document represents it changes the
  posterior — measured on this question at 20 of 59 deduped chunk texts multi-carried, the
  representative flipping for 9, two of those carrying the gold at exact score ties.
  *Predictions:* (1) the row returns to a withholding with one candidate on the lattice, as in
  the `861ea1b` recording; (2) wrong commits go to 0; (3) answer rate stays near 0.36 — the
  reorder moves one row, not the arm's reach; (4) spend flat.
  *Named risk:* a pass here is a conviction on one row out of 104, and the run cannot tell
  whether other rows moved in compensating directions; the answer-rate and disagreement
  diagnostics are the check on that.

- **Run 12 — §6.9's declared probe order, isolated and CONVICTED: PASS at P(Δ>0.05) = 0.964,
  Δ̄ = +0.434 [+0.076, +0.883]** (2026-08-21, `gate-20260821T194120`; typed 36 ✓ / **0 ✗** /
  68 withheld, miss 2 · dispersed 66, answer rate 0.35 at $1.36 vs mono 0.97 at $39.01;
  deliberate 67/104, warm 67). Run 11's tree with §6.9's declared key backed out and nothing
  else — the fail-open restored, M1's deletion and R2's order in place; §6.10's diff named the
  three decision-logic files that moved. The frozen rule required wrong = 0 AND P ≥ 0.90, and
  **both hold: §6.9's key is convicted as what moved the wrong commit.** All four predictions
  held except the parenthetical in (1) — see below. **This is the best reading in the series**
  (run 7 0.945, run 9 0.938), and the first PASS on the priced lane.
  **What §6.9 actually did, which is not what the conviction sounds like.** The posterior
  records across the isolation put the *same wrong leader* on top in runs 10, 11 AND 12: the
  competitor leads at 0.902 / 0.901 / 0.810 with the gold demoted to 0.03–0.06 in all three.
  So the declared key did not add the candidate and did not swap the leader — it **concentrated
  the posterior** (p_none 0.126 → 0.066) enough to carry an already-wrong leader from EU 0 to
  EU +0.044, a hair over the commit bar. On the priced lane this question is wrong-leader
  dominant in **every** configuration measured; run 12 passes because the arm *withholds* on a
  wrong leader, which is the right action and not knowledge of the gold. The single-candidate
  gold-led posterior belongs to run 9's LEGACY lane and has not been seen since. **What
  protects the arm here is dispersion, and the thing deciding how much dispersion survives is
  an arbitrary choice of which document represents a duplicated chunk** — the carrier-identity
  defect, now with a priced demonstration of what it costs.
  *A correction to the previous entry, and the third of this investigation.* The "controlled
  comparison" drawn from the M0.5 live recordings was weaker than it was presented: its
  pre-§6.9 arm is a SINGLE draw from a nondeterministic order, so it was one ticket in the
  lottery, not a control — which is why it showed one candidate where run 12 shows two on the
  same order. The conclusion is carried by the direct isolation (run 11 → run 12, one change,
  1 wrong → 0 and FAIL → PASS), not by that comparison. *The pattern is worth naming because
  it recurred:* every attribution in this arc drawn from indirect evidence was wrong (the
  fail-open, then the lane, then the cassette 2×2), and every one drawn from a single-change
  isolation was right. Four decision-path changes bundled into one run cost three runs and
  three retractions to unpick.
  *What this does NOT license, as pre-registered before the run:* reverting §6.9. The
  measurement branch does not merge. The old order is nondeterministic and merely a luckier
  ticket on this corpus — runs 7 and 8 won it, run 10 lost it. Master therefore still carries
  the configuration that produces the wrong commit, knowingly, until the carrier-identity
  checkpoint fixes the root cause; **the arc is not deployed, so nothing live is affected, and
  it should not be deployed before that checkpoint closes.**

- **Carrier identity — the checkpoint opened, criteria frozen BEFORE the instrument reads
  (2026-08-22, r04 RULING 4; register entry design §6.11; instrument
  `scripts/carrier_audit.py`, $0).** The defect run 12 exposed: `retrieve_set` dedupes the
  over-fetched hits by chunk text and keeps ONE, and that survivor's artifact becomes the
  text's carrier for the whole decision — it sets the §4.1 covariate AND the document
  partition `lookup_posterior` groups by, so it decides how much of the evidence is treated
  as correlated. Byte-identical text scores identically, so R2's declared key resolves the
  tie on the lexicographically smaller content hash: a coin flip frozen, not resolved. The
  same duplicate-witness question is already answered by a *substantive* rule one layer down
  — §5's `dedup_correlated` keeps the max-covariate document — and that rule never gets to
  run on the carriers the dedup already discarded.
  *Why this is a checkpoint and not a patch:* run 12 convicted §6.9's declared key of
  carrying an already-wrong leader over the commit bar by concentrating the posterior, which
  is the same mechanism one layer over. A declared total order buys reproducibility, not a
  right answer; where the tie is between witnesses of the same content the decision must not
  depend on the choice at all. So the fix under test is **invariance**, and the rule that
  implements it is named in advance (the §5 max-covariate representative lifted one layer up,
  declared key within equal covariate) so it cannot be tuned to the reading.
  *Frozen criteria* (full text in the instrument's docstring, which predates its first run):
  exposure is reported and is never a bar on its own (the corroborate lesson — a ceiling
  counted in artifacts is not reach); **BUILD** iff load-bearing exposure ≥ 5 questions AND
  regressions ≤ repairs; **REFUSE** iff regressions > repairs; **PRICE a gate run** iff
  delivered reach ≥ 1, else the fix lands on a hermetic permutation-invariance test with no
  run bought. Below 5 this entry converts to a standing known-and-uncovered source, §6.9's
  own fallback shape.
  *Predictions, blind:* (1) multi-carriage is the corpus's commonest shape and will cover a
  large fraction of top-k texts; (2) essentially all of it is decided by the content hash,
  because identical text scores identically; (3) covariate divergence will be far rarer than
  multi-carriage and concentrated in `doc_date` — a re-filed copy differs in date, rarely in
  authority class; (4) delivered reach at the lookup layer will be single digits; (5) the
  adversarial worst-carrier bound will be materially larger than the named rule's effect,
  and is diagnostic only.
  *Named risks, and which way they point.* The audit decides at the **lookup layer**, not the
  executor's — rerank/gather/deliberate sit above it and are out of scope because they spend,
  so a change measured here need not survive the menu. An uncached owner verdict degrades a
  carrier's subject state to `unclear` exactly as the live probe does, flattening subject
  divergence. And the over-fetch window can truncate a carrier list. **All three biases point
  the same way — toward under-detection** — so a BUILD reading is safe against them and a
  NO-GO reading is the provisional one, to be reported as such rather than as a clean
  negative. *Disclosed, and it earned its keep:* a three-question `--only` smoke test ran
  before the battery. It found **two measurement bugs in the instrument** and one blind spot,
  all fixed before the reading and none of them a criterion change. (1) Divergence was
  computed on the carrier's provenance *identity*, which includes the origin path — but two
  email copies at different paths share an authority class, so it reported divergence where
  the weight is bit-identical: it **over-stated** load-bearing exposure. It now compares the
  factor triple the posterior actually reads. (2) The partition was compared as a *set* of
  artifact keys, but `lookup_posterior` groups by the *assignment* text → document; two
  assignments can share a key set and group differently, so it **under-stated** the change.
  It now compares the assignment. (3) The blind spot: with equal covariates the
  covariate-adversarial permutation is a no-op, because `max` over a declared-order list
  returns the same first element — so wherever the carriers' factor triples tie, the
  arbitrariness that survives is not the WEIGHT but the GROUPING, and nothing measured it.
  Two grouping-adversarial permutations were added (max-independence and max-correlation over
  the carrier sets) as **diagnostic bounds only**, never candidate rules — a rule chosen to
  maximise apparent independence is the saturation §5 exists to prevent. The named rule of
  criterion 4 is unchanged, and this is the reason it is worth saying out loud: the
  pre-registered fix **cannot** repair the grouping wherever covariates tie, so a small
  delivered-reach reading will not by itself acquit the defect.

- **Carrier identity — the reading: BUILD on exposure, the named fix REFUTED as a no-op, and
  the wrong commit turns out not to be carrier identity at all (2026-08-22,
  `scripts/carrier_audit.py` over run 10, $0; report r05).** Surface (a), the arm's cheap
  first pass, 102 questions: 57 of 2040 deduped texts multi-carried, **57 of 57 decided by
  the content hash alone**, **zero** covariate divergence, **17** questions whose carriers
  admit a different document partition, delivered reach **0**. Criterion 7 reads **BUILD**
  (17 ≥ 5, regressions 0 ≤ repairs 0) with **no gate run bought** (reach 0).
  **The pre-registered fix is refuted by its own audit:** carriers of byte-identical text
  never differ in authority class, subject state or date-projection status on this corpus, so
  argmax-covariate always returns the declared-key first element. The amended
  pre-registration predicted exactly that. What is arbitrary is the **grouping**, and it is
  priced: on q2-059 the gold leads in every arm, the deployed assignment *hedges* it at 0.683
  and a max-independence assignment *reports* it at 0.975 (EU 0.369 → 0.755) — while on
  q2-011 the same permutation lowers the gold (0.985 → 0.961). One permutation helps one
  question and hurts another, which is why it is a bound and never a rule.
  *Predictions scored:* (1) falsified — multi-carriage is 2.8% of texts at this layer, not the
  commonest shape; (2) held exactly; (3) held in direction, empty in content — zero divergence
  instances; (4) held; (5) falsified as stated — the covariate-adversarial bound is 0 and the
  bound that bites is the grouping one, added after the smoke test.
  **The instrument had FOUR defects and three were in its measures**, each of which would have
  produced a confident number: divergence read off the carrier's provenance path rather than
  the factor triple (over-stating); the partition compared as a key set rather than the
  text→document assignment (under-stating); the covariate-adversarial permutation being a
  no-op wherever factor triples tie, so grouping arbitrariness went unmeasured; and — found
  after the first reading and disclosed in r05's chronology — criterion 3's partition clause
  implemented as *"does the named rule move it"* when the frozen text asks *"do the carriers
  disagree on it"*, rule-independent like its two siblings. Correcting the fourth flips
  surface (a) from NO-GO to BUILD; both quantities are published. *The rule this earns:* an
  audit that runs is not an audit that measures the thing its criteria name — and the
  instrument was written before its tests, which is how three of the four survived to a
  reading.
  **The redirection, which matters more than the verdict.** Run 10's single wrong commit is
  q2-011, and the audit's base arm answers it CORRECTLY — 5 grounded observations over 4
  documents, one candidate (the gold) at 0.985 — **invariant under every carrier permutation
  measured**. The run's own decision row says why: the committing view carries
  `instrument: deliberate@<opus>` with **n_obs = 1** and 10 indeterminates, the competitor at
  0.902 and the gold demoted to 0.033. The recorded wire agrees independently — on the M0.5
  baseline the base `/decide` returns a SINGLE candidate and the two-candidate shape appears
  only after the gather steps. So **the wrong leader is introduced above the base pass, by a
  replace branch discarding a grounded channel** — the class §14 already registered as the
  n_obs=0 cluster's suspected mechanism and marked NOT yet measured, here at n_obs=1 on the
  one row that failed a gate. This does not overturn run 12: §6.9's key remains the *marginal*
  cause of the commit (p_none 0.126 → 0.066; the run-10 row records 0.066). It identifies the
  cause of the wrong *leader*, which the ladder could not. **And it refutes the premise of the
  standing deployment block** — "do not deploy until the carrier-identity checkpoint fixes the
  root cause" — because carrier identity is measurably not this row's root cause. The block
  may still be right; it needs re-deciding on its own terms, and that is the owner's call
  because the owner set it.
  **Surface (b), the corroborate probe** — added to scope before (a) was read, on a mechanism
  the code states outright (`_fresh_hits` drops a hit whose carrier is already held, so where
  the carriers straddle the held set the choice decides whether the corroboration EXISTS):
  37 straddling texts in 17 questions, load-bearing 17, **BUILD**, no run bought. And the
  split that matters: **37 of 37 straddles fall on the conservative side.** The declared key is
  the same function on both surfaces and the carrier scores tie, so the probe re-picks the
  carrier the base pass already picked and the straddle is always resolved by DROPPING the hit
  — any alternative would add a second copy of text already in hand as independent
  corroboration, which is the saturation §5 exists to prevent. The consistency of the declared
  key is doing load-bearing work that "an arbitrary tie-break" undersells, and any fix must
  preserve it.
  *Honest bound:* the audit decides at the lookup layer, which agrees with the arm's terminal
  on 70 of 102 questions; surface (b)'s decision proxy covers 65 of 101 (36 questions hold a
  chunk the run never extracted, each named, none warmed). The redirection does not rest on that agreement but on the evidence
  COUNT (5 grounded observations versus 1), which is not a host-versus-daemon modelling
  difference — both consume the same observation set.

- **The rulings r05's reading forced (owner, 2026-08-22).** Four, taken before r06 opened.
  (1) **The deployment block is kept and RE-POINTED at the replace branch (§6.12)** — its
  premise was refuted, but the tree it blocks still commits a row wrongly, which is what the
  block was for; a register entry whose stated reason is known-false is worse than none.
  (2) **BUILD licenses known-and-uncovered, not a fix** — §6.11 records the grouping bound in
  both directions and the 37/37 cross-surface conservatism, retires its named fix as refuted,
  and writes **no decision-path code**; a future carrier-set grouping design does not inherit
  that BUILD. (3) **M1 is ACCEPTED and closed** (r04 RULING 3 released): the hold's live
  hypothesis was that the deletion carried 7.3's failure, and run 12 refutes it directly — the
  deletion was in that tree and read 0.964 with zero wrong commits — with r05's DONE 4
  redirecting the remaining failure to a mechanism M1 never touched. M1.5 (the coverage census,
  R7) is unblocked. (4) **r06 is scoped to EVERY replace/override site**, not to the registered
  NULL-as-disagreement hypothesis alone, on r05's own lesson: an instrument written around the
  presumed fix measures the fix, not the defect.

- **The replace branch — the checkpoint opened, criteria frozen BEFORE the instrument reads
  (2026-08-22, register §6.12, report r06, instrument `scripts/replace_audit.py`).** The
  mechanism r05 named and no run has measured: at five sites the executor's enactment loop lets
  a probe's reply REPLACE the grounded channel (`obs`/`rho`/`era`) instead of joining it. The
  entry enumerates the five from the code — the `corroborate_*` tiers, the two retrieval grows,
  the `deliberate` edge, in-loop `re_extract_strong`, and the k=0 rescue walk — with their
  guards, and names the asymmetry that makes this readable: **S1 and S4 retire fail-open on a
  null read; S3 (deliberate) has no null-read guard at all** and collapses the channel on an
  empty ok reply by design. The population is run 10 (`gate-20260821T094545`), whose one wrong
  commit fired S3 at n_obs = 1 over a five-observation grounded channel, plus the registered
  n_obs=0 cluster (17 of 19 rows at exactly uniform credences, gold still on the lattice in 14).

  *The criteria, frozen (the instrument's docstring is the authority; this is the mirror):*
  **C1 exposure** — per site, the number of run-10 questions on which it fired AND took the
  replace branch; exposure 0 is reported as *untaken*, never as *clean*. **C2 channel loss** —
  per firing, n_obs of the grounded channel before against n_obs of the committed posterior; a
  firing with loss ≤ 0 is not a discard. **C3 delivered reach** — the counterfactual is
  **RETIRE-NOT-REPLACE** (the probe retires fail-open and the grounded channel stands: exactly
  the treatment S1 and S4 already give a null read, generalised, so it is a deployable rule and
  not an invented one); reach is the number of questions whose committed action differs.
  **C4 the split** — every reach row classified against the run's own gold as REPAIR (a wrong
  commit becomes right, or becomes an honest withholding), REGRESSION (a right commit becomes
  wrong or becomes a withholding) or NEUTRAL; reach is published as the triple, never as a
  total. *Completed before any reading (the frozen text left a gap):* the withholding→commit
  direction is unnamed above, so it is fixed now rather than after a result — a withholding
  that becomes a CORRECT commit is a REPAIR, a withholding that becomes a WRONG commit is a
  REGRESSION. Both arms must be gradeable for a row to be classified; an ungradeable row is
  named, never bucketed. **C5 conservatism** — for each disagreement, which side the DEPLOYED rule falls on,
  both directions counted. **C6 the asymmetry** — how many S3 firings carried a reply the
  S1/S4 guard would have retired on, and what each did to the channel; 0 in the records means
  the asymmetry is structural-only on this corpus, and that is a finding to state, not to omit.
  *Amended before any reading (a feasibility fact, not a result):* the eval writer emits an
  edge-outcome row only when the firing carried BOTH a value and a self-report, so a reply that
  named nothing leaves no row — C6 is therefore read off a **conjunction** of the run's own
  records: the terminal decision row's `instrument` field is set only by the deliberate branch
  (the `extract@` siblings go through `_edge_event`, which never touches it), so
  `instrument` naming deliberate WITH no `deliberate@` outcome row for that question AND a
  terminal `n_obs` of 0 over a base channel with `n_obs` > 0 is the signature of S3 collapsing
  a grounded channel on an empty ok reply. That conjunction is also, by construction, the
  signature the registered **n_obs=0 cluster** was described by (candidates at exactly uniform
  credences), so C6 doubles as the first test of whether that cluster IS S3.
  **C7 the verdict, applied mechanically per site** — reach ≥ 1 with repairs > regressions ⇒
  **BUILD the retire-not-replace guard for that site AND buy one isolated gate run under
  §6.10**; reach ≥ 1 with repairs ≤ regressions ⇒ **REFUSE**, the deployed rule is not worse,
  record the bound; reach 0 with exposure ≥ 5 ⇒ **known-and-uncovered** (the §6.11 precedent),
  no code; exposure < 5 ⇒ **NO-GO**, too few load-bearing questions to read. The bar of 5 is
  inherited from r05 deliberately, so the two checkpoints are comparable. **C8 the instrument's
  own limits, published not averaged** — (a) only ONE of the two arms is recomputed. The
  **deployed** arm is READ from the run's own terminal decision row (its `chosen_action`, and
  its leader as the argmax over the recorded candidates/credences), never re-derived — so
  r05's 70-of-102 layer gap applies to the counterfactual arm alone. That gap is bounded by a
  **direct control** rather than inherited: on every question where NO edge fired, the terminal
  IS the base channel, so audit-base-versus-recorded-terminal on those rows measures the layer
  agreement on this very run, and it is published as a rate with the disagreeing rows named.
  Both arms are graded by the SAME matcher; where that matcher disagrees with the run's judge
  grade on the deployed arm, the row is flagged and never silently kept; (b) the JOIN counterfactual (pool base + probe observations under §5
  dedup) is **not read here** — the probe's observations are not in the records and reading
  them needs a live bridge replay; it is named as the escalation, not silently dropped; (c) any
  question whose base channel cannot be recomputed without spend is EXCLUDED BY NAME.
  **C9 no decision-path code** — nothing under `src/` changes in this checkpoint; a commit gate
  refuses if `src/` is dirty.

  *Blind predictions, recorded before the read:* (1) S3 shows the largest channel loss per
  firing, because it is the only site with no null-read guard. (2) The run-10 wrong commit is
  an S3 firing with loss ≥ 3. (3) Total exposure across the five sites is ≥ 20 on 102
  questions. (4) S3's delivered reach is ≥ 1 and its repairs exceed its regressions.
  (5) S2 has exposure > 0 but delivered reach 0 — its `changed` guard already refuses the
  empty case.

  *Named risks, recorded before the read:* the instrument mirrors the loop's branch conditions,
  and a mis-mirror produces a confident wrong number — which is exactly how r05 shipped three
  measure defects, so the mirror is tested against the real predicates (`_null_read`,
  `_GROW_RETRIEVE`, the guard expressions) and not hand-copied. **Retire-not-replace is a
  bound, not presumptively a better rule:** retiring a probe that legitimately corrects a wrong
  grounded channel is a regression, and C4 exists to see it. And the 70/102 layer agreement
  means up to a third of rows are read at a layer the arm did not use — C8(a) is what keeps
  that from being averaged away. **This entry supersedes the n_obs=0 cluster's suspected
  mechanism as the thing to measure**: the suspicion (a NULL re-read treated as a DISAGREEMENT)
  is one branch of one site, and r06 reads all five rather than confirming it.

- **The replace branch — the reading: the criteria buy four sites and the instrument's own
  control says only one of them delivered anything (2026-08-22, `scripts/replace_audit.py`
  over run 10, $0; report r06).** 102 questions, 2 excluded by name. Exposure: **S3 (the
  deliberate edge) 68**, S1 (the corroborate tiers) 26, S4/S5 12, S2 **unreadable** (it emits
  no attributed edge event, so its exposure is unmeasured, never zero). 27 questions show a
  positive channel loss, 59 grounded observations discarded in total. Delivered reach **23 of
  the 73 questions where a site fired** — repairs 12, regressions 11, deployed rule
  conservative on 13 and aggressive on 9. Criterion 8, applied mechanically, reads
  **BUILD+PRICE on S1, S3, S4 and S5**.
  **And criterion 9(a)'s control is what the entry is actually for.** On 29 questions NO site
  fired, so retire-not-replace is provably a no-op — yet the two arms differ on 8 of them.
  That is a **28% noise floor**, and against it: S1 delivers 11 reach where the floor predicts
  7.2 (**excess +3.8 rows**), S4/S5 4 where it predicts 3.3 (+0.7), and **S3 delivers 19 where
  the floor predicts 18.8 — an excess of +0.2 rows.** The site with the missing guard, the
  site that took run 10's wrong commit, has delivered nothing this instrument can distinguish
  from its own layer gap. The frozen criterion buys it a run anyway, and it is left standing:
  renegotiating a criterion after its numbers is the failure this programme exists to avoid.
  **The witness is repaired, and that is the result to act on.** On run 10's wrong-commit row
  the deployed arm reports at **n_obs = 1** on the competitor; the counterfactual reports at
  **n_obs = 5 over 4 documents** on the gold, a channel loss of 4, classified a REPAIR. Retiring
  the replace fixes the row the deployment block is pointed at. What the records cannot say is
  WHICH site did it: four fired on that question (the `extract@<opus>` spelling is shared by
  S1's opus tier, S4 and S5, and the deliberate firing is recorded only in the decision row's
  `instrument` field), and no ordering between the two record streams exists.
  **Criterion 7 retires a suspicion §14 has carried since 2026-08-18.** The S3-collapse
  signature fires on exactly **1** question — and that one has a graded `deliberate@` row in
  another run, so a cross-run dedup explains its absence here. **Zero rows survive as genuine
  null-read collapses**, so the S1/S4-vs-S3 asymmetry is structural-only on this corpus's
  records, and the empty-ok collapse is **not** what produced the n_obs=0 cluster.
  *Predictions scored:* (1) **falsified** — S1 discards 0.81 observations per firing, S3 only
  0.50; (2) held — the wrong-commit row is a loss-4 firing with S3 among its sites; (3) held —
  S3's exposure alone is 68; (4) held as stated and **empty in content**, since S3's excess over
  the floor is +0.2 rows; (5) unresolved, exactly as pre-registered (S2 is unreadable here).
  **The instrument shipped three defects in its own measures and a fourth in an
  interpretation, all four caught before a verdict was published.** (i) Exposure read off the
  attributed-edge stream alone, so S3 read as *untaken* on the one question it decided — the
  stream is not a record of firings (found in a 3-question smoke test). (ii) The control set
  keyed on the same stream, so 68 of its 76 "control" rows had S3 fire and the floor read
  56/76 against a true control set of 29 (found in the first full reading; both quantities
  published). (iii) A rate-against-rate label calling 27.9% "above" 27.6%, replaced by excess
  in rows, where a wash looks like one. (iv) `run_eval` dedups edge rows against the WHOLE
  prior log's §18.9 lineage, so a warm replay leaves no row either — absence of a row is not
  evidence of a null read, and criterion 7's count is published as an upper bound split by
  cross-run gradeability. *What was different this time:* the tests were written first, the
  criteria were **committed before the instrument read anything** (a commit gate refused unless
  the report still said *pending*), and every load-bearing predicate was verified RED by
  mutation — eight of them — before the read rather than after.
  *Honest bounds:* only the counterfactual arm is recomputed (the deployed arm is read from the
  run's own terminal decision row), the 28% floor is that arm's measured layer gap on this very
  run, matcher-versus-judge flips on the deployed arm are 0, and the JOIN counterfactual is not
  read here — the probe's observations are not in the records.

- **r07 READ (2026-08-22 pass 1, three arms, 67 of 104; 2026-08-23 pass 2, deployed only, 73
  of 104; $0 across every pass; report `docs/unification/reports/r07-recorded-replay.md`, THE
  READING).** Fidelity 66/67 and 72/73 with the SAME divergent row both times; the no-site
  control reads 9/9 and the 7 of r06's 8 disagreeing control rows that replayed all agree with
  the record — **the 28% floor was the decide layer** (prediction 1 CONFIRMED at 100%).
  Attribution from the payload: S1 ×10 and S2 ×9 named; the mandated double run withholds 7 of
  S2's rows, leaving **S1 ×10 + S2 ×2 confirmed; S3/S4/S5 discard nothing on any replayed
  row**. A grounded channel was zeroed on 7 questions (S1 on 6, S3 on 1); on run 10's blocking
  row S1's first corroborate tier zeroes the five-observation grounded base and the deliberate
  edge re-mints the one-observation competitor — stable across the double run. **The harm
  rides the DISAGREE path retire-not-replace cannot see: the enacted RETIRE arm reads 0
  repairs / 1 regression on 40 rows, while the JOIN upper bound reads 10 repairs / 2
  regressions on 66** (prediction 2 REFUTED — the blind guess ran the other way). Every site
  KNOWN-AND-UNCOVERED under the frozen bar of 5 with the floor at 0%; **nothing bought**;
  r06's criterion 8 untouched (owner ruling). Predictions 3 and 4 CONFIRMED (S4 exposure 34 <
  S1-opus 44; 11 unstable questions besides the §6.13 witness); prediction 5 scored nothing as
  declared, and its rehearsal-informed expectation was wrong in mechanism. En route, two
  findings now registered: **§6.13 at commit granularity** — across three draws at fixed
  corpus and fixed `src/`, 14 of 104 questions wobble in committed n_obs (one in firing order)
  and 22 flap between readable and cold — and the **§18.9 warm-through** (a $0 replay records
  composed derivations into the live store; 31 during these passes; write-once and
  key-deterministic so the store is undamaged, but coldness is pass-order-dependent and
  "cold-mid-loop = divergence" is retired to a weaker claim). Deviations 7–11 disclosed in the
  report. The deployable question this leaves is a correlation key on the wire so a §5-deduped
  JOIN becomes readable — decision-path code, its own frozen pre-registration, not this
  checkpoint's.

- **r07 PRE-REGISTRATION — the recorded replay (opened 2026-08-22 on r06's QUESTION 2, owner
  ruling "start r07"; register §6.12; instrument `scripts/replay_audit.py`; criteria frozen in
  its docstring and committed BEFORE it reads).** r06 read the replace branch from a gate run's
  own records and named three things it could not reach: which site fired FIRST, what the
  probes OBSERVED, and why its reconstruction disagreed with the recorded terminal on 28% of
  the rows where its counterfactual was provably a no-op. This checkpoint replays run 10's
  questions through the **deployed** path — `core/executor.run_pass` and
  `bridge/server.dispatch` unmodified, the credence daemon live, a recording transport between
  them — at $0.
  *The method's one real idea:* the counterfactual is **enacted, not reconstructed**. The
  transport rewrites a replace-site reply into the shape the deployed code ALREADY retires on
  (a null read at S1/S4, a non-ok status at S3, a withheld mint at S5), so RETIRE-NOT-REPLACE
  runs through the real executor and the real daemon and the guard under test is
  `executor._null_read` itself. JOIN has no branch in the deployed code and is therefore
  the one quantity computed rather than enacted. **Criterion 7(b) was amended before any
  reading, on a structural fact:** §5's dedup keys on an observation's QUOTE, and a joint
  re-read's observation has none — `/extract` returns abstract observations by design (the body
  is string-blind) and the corroborate handler synthesises one abstract observation mapping the
  re-read value to a candidate index. The guard that makes joining safe therefore cannot be
  applied to the thing being joined, and a §5-deduped JOIN is unreadable by any instrument that
  stays off the decision path. That is a finding about §6.12's alternative rather than a
  shortfall of this checkpoint. What is read instead is the UPPER BOUND — pooling with no dedup,
  the most favourable case joining could ever have.
  *The pin (§6.10), verified before any question runs and a mismatch REFUSED by name:* `src/`
  at HEAD byte-identical to run 10's pinned sha (**it is** — r05 and r06 both changed nothing
  under `src/`, so master IS run 10's decision path); the live corpus digest equal to run 10's
  (**it is**); the utility elicitations sha equal to run 10's (**it is**); the outcomes and
  gather-outcome logs truncated to run 10's `created_at` — correct because `run_eval` appends a
  run's edge rows AFTER the run, so no question in run 10 conditioned on run 10's own rows;
  curves folded leave-one-question-out as `gate.loo` records; and the transform menu assembled
  the way the deployed caller assembles it. That last clause is not bookkeeping:
  `DELIBERATE_TRANSFORM` is **not** in `DEFAULT_TRANSFORMS`, and a rehearsal that took the
  default lost the deliberate firing entirely and drew the opposite conclusion about which site
  discarded the channel. Disclosed here because it happened before the criteria were frozen.
  *Blind predictions, with the one that is not blind declared:* (1) fidelity is >= 90% on the
  rows where r06's reconstruction disagreed with the record — i.e. the 28% floor is mostly the
  decide LAYER, `core/lookup`'s decide standing in for the daemon's; (2) JOIN delivers strictly
  fewer reach rows than RETIRE; (3) S4's exposure is strictly less than S1's opus-tier exposure
  once the `extract@<opus>` ambiguity class is resolved by payload; (4) at least one question
  besides the §6.13 witness proves unstable across the mandated double run; (5) **NOT BLIND —
  informed by a one-question rehearsal:** on run 10's wrong-commit row the attributed discarder
  is S3, which takes the channel from 5 observations to 1, and S4 then mints the competitor
  that leads. It is recorded as an expectation rather than a prediction and scores nothing.
  *Named risks:* the daemon is a live process and nothing here pins its internals, so any
  residual gap lands in the fidelity control and bounds every claim; a derivation that goes
  cold mid-loop means run 10 never made that call, which is evidence of divergence rather than
  a mere exclusion, and eviction is the named alternative; and §6.13's sampler makes at least
  one question's retrieval a lottery, so the read runs twice and unstable questions carry no
  attribution. **The reading is PENDING at the time this entry is committed.**

- **The rulings r07's reading forced (owner, 2026-08-23, interviewed).** Four questions, each
  with a recommended branch and its alternatives priced; the owner took the recommended branch
  on all four (`r07-recorded-replay.md`, RULINGS, has the full width). (1) The
  JOIN-with-a-correlation-key fix **OPENS** as checkpoint **r09**: the §5 dedup key (the
  quote) goes on the wire so a §5-deduped JOIN is computable at the replace sites — frozen
  pre-registration before any `src/` change, then TDD. (2) **Pulled FORWARD**: r09 runs
  immediately after M1.5 rather than riding M6's E-7 slot (E-7 becomes verify-only; the m0-5
  baseline is re-recorded and O2 re-prepared after it lands). (3) **§6.13 is repaired FIRST**
  as checkpoint **r08** — own pre-registration, verified at $0 by a multi-draw replay read —
  so run 13's reading is not taken against a 14-of-104 commit-wobble floor and r09's Δ is
  attributable to the JOIN alone. (4) **Run 13's outcome branches frozen at full
  delegation**: PASS = the gate's frozen δ/level (0.05 / 0.90, §6.1 — unchanged) ∧ the
  blocking row repaired ∧ zero new wrong commits → the §6.12 deployment block closes and
  master deploys to live without a further keypress; FAIL on any conjunct → the JOIN reverts
  from the deploy path, the reading publishes append-only, and work STOPS for a ruling. The
  cap stands: r07 was the last pure-diagnosis checkpoint; anomalies en route are disclosure
  items, never a new diagnostic arc. Sequencing under the standing delegation: **r08 → M1.5 →
  r09 → run 13** (the census records its fixtures on the deterministic tree).

- **A declared total order cannot restore determinism when the tie block is larger than the
  over-fetch window (2026-08-22, register §6.13, found by r06's idempotency double-run, $0).**
  Two identical invocations of the same $0 audit disagreed: one question flapped in and out of
  the exclusion set, moving a site's exposure by one row. The cause is not the audit.
  `core/retrieval.retrieve_set` imposes R2's declared total order on the rows the over-fetch
  RETURNED, and pkm's FTS ends `ORDER BY score DESC` with a `LIMIT` — so which of a tied
  population those rows are is decided before the declared key ever runs. §14's "quantising
  takes both to zero" was measured at k=80, an over-fetch of 320. At the arm's own k=20 the
  window is 80 rows, and on **1 of 104** questions those 80 carry five distinct quantised
  scores with **73 of them sharing one**: the top-20 is four stable hits plus sixteen drawn
  from a tie block bigger than the window. Five consecutive calls returned five different chunk
  sets differing by half the top-20; the other 103 questions are stable across three calls each
  (0 chunks of symmetric difference). A tail, not a regime — but a live one, and everything
  keyed on the retrieval set is a lottery with it on that question. Invisible to 7.2 (the
  fixture set tapes the derivation cache and never executes `retrieve_set`) and invisible to a
  gate run (one question, and a run reports a decision, never the draw behind it): it took an
  audit that ran the same read twice on purpose. Candidate fixes named, none adopted:
  over-fetch until the score strictly drops below the cut; push the tie-break into the SQL; or
  declare the saturated window and refuse to decide on it. Registered as a standing
  known-and-uncovered source with a measured incidence and a named witness.

- **§6.13 REPAIRED — the window is no longer the sampler (r08, 2026-08-23/24,
  `docs/unification/reports/r08-window-determinism.md`, $0).** Fix (b) of the three named
  candidates, frozen blind in r08's pre-registration and landed under TDD (`src/pkm/
  retrieval.py`, SPEC 0.18.2): the declared total order goes into the SQL before `LIMIT`, so
  the engine cuts a declared prefix. The baseline first reproduced the defect and decomposed
  it — the window layer is order-unstable on 75/74/75 and set-unstable on 15/14/28 questions
  per surface while the decision layer is stable on 103 of 104, the sole exception the
  witness (r06's 1-of-104, replicated cross-process). Post-fix: zero draw-unstable questions
  everywhere at both layers; the decision-visible top-k changed on exactly one question at
  one surface (the witness at base) — §5 dedup absorbs the other 16 straddles, so straddling
  predicts eligibility to change, not change; three replay draws read committed-action
  wobble 0, firing-order wobble 0, n_obs wobble 2 with retrieval-attributable component 0 —
  run 13's commit-wobble floor is 2, not 14, and both residue rows are named (monotone n_obs
  accumulation, the §18.9 warm-through's signature; per the cap a disclosure, not a
  diagnosis). Predictions: 2 and 4 confirmed, 3 refuted (17 straddling at base, not ≤5), 1
  half (pool window instability is the largest, not the smallest), 5 refuted as an equality
  but confirmed as a containment. Two deviations disclosed en route: C5's frozen
  "instrument unmodified" clause contradicted the instrument's own §6.10 pin on the fixed
  tree (resolved by an explicit `--acknowledge-src-drift` that names the one expected tree
  and stamps the drift into every pin note), and the draws' render-stage 9(d) guard fired as
  in r07 (the rows dumps are the artefact of record). The saturation census (17/15/30) is
  the standing arbitrariness record.

- **r09 — the §5-deduped JOIN is on the decision path; the replace branch is retired at the
  probe sites (2026-08-24, `docs/unification/reports/r09-deduped-join.md`, $0, register
  §6.12).** Ruling 1 enacted under its own frozen pre-registration (committed before any
  `src/` change): the §5 dedup key rides every wire observation (quote, doc_key, and
  value_norm — the third field C2's identity forced in TDD, disclosed as the checkpoint's
  D1 amendment), stripped before every decide post so the brain stays string-blind; the
  executor hands its standing channel to every S1/S3/S4/S5 probe and the bridge returns the
  §5-deduped pool computed by THE deployed rule (`lookup.dedup_drop_rows`, extracted from
  `dedup_correlated` so the clustering exists once; groups re-derived from doc_key — the r07
  bound's group-0 collision is dead). Semantics adopted are the bound's, named not smuggled:
  a disagree no longer erases the grounded channel, the deliberate empty-ok collapse is
  retired, the single-rho coarsening stands, the null-read guard stays, S2 is untouched.
  **Finding en route: the deployed JOIN is provably idempotent over the raw pool on today's
  wire shapes** (the base arrives §5-deduped from `observe_hits`; synthesised probe
  observations are value-only) — so r07's JOIN upper bound (10 repairs / 2 regressions on
  66) is run 13's expected read, not a ceiling. 7.2 on this tree: every non-probe-firing
  fixture replays byte-identically (216/311 + 9/104 + 2/2); the 95 probe-firing fixtures
  are unservable because the payload grew — the named class, why ruling 2 re-records the
  baseline. Three deviations disclosed (the D1 third field; a process slip rebuilt and
  re-verified; prediction 1's instrument-blindness — the direction clause rides run 13).
  The §6.12 deployment block STANDS until run 13's PASS.

- **Run 13 (2026-08-24, `gate-20260824T144002`, the ruled reading of the JOIN): FAIL on two
  of ruling 4's three conjuncts — P(Δ>0.05)=0.895 (< 0.90 by 0.005) and four new wrong
  commits — with the BLOCKING-ROW conjunct PASSED (run 10's wrong commit reads correct).**
  Δ̄ +0.424 [−0.070, +0.941], the series' best mean; typed 70 ✓ / 4 ✗ / 30 withheld, answer
  rate 0.71 (from 0.34–0.57), $0.58 typed spend (deliberate 29/104 all warm). All four
  wrong rows were run-10 DISPERSALS — the JOIN converts dispersals in both directions, and
  dispersal was the protection (run 12's own analysis, now priced). Two of the four are
  standing named classes: the superset-confirm defect (the corroborate audit's q2-019) and
  run 8's warm-deliberate confirm (q2-105). Ruling 4's FAIL branch enacted verbatim: the
  JOIN's code commits reverted from master (docs stay, append-only), the reverted tree
  green at the pre-r09 count, the §6.12 block STANDS, work STOPPED for an owner ruling.
  The decidable question the reading leaves: re-open r09 with a temper for the two named
  wrong-commit classes under a new pre-registration, or park the JOIN.

- **The tempered-JOIN arc — r09b / r09c / r09d, three sweep-gated iterations, all $0, none
  fired (2026-08-24/25).** Ruling: re-open with a temper. Each iteration pre-registered its
  criteria before any `src/` change, read them on a $0 replay of run 13's own record, and
  STOPPED on its own frozen consequence. **r09b** (T1 strict-span + T2 synthesised-stack
  collapse): S1 FAIL, 0 of 4 wrong rows flipped; the wire refuted the stacking diagnosis and
  T2 measured 2 regressions / 0 repairs (corrected from 3 by r09c). **r09c** (A1 per-document
  witness collapse in THE §5 rule + A2 synthesised-confirm covariate cap, T2 dropped by
  ruling): S1' FAIL — **A2 fires exactly as designed and the row never depended on it**; the
  competitor is carried by two of three genuinely distinct documents that answer a
  file-scoped and a remainder-scoped question while the question asks a class-scoped one.
  A1 was unmeasured (its target row cold). **r09d** (entity anchor + the S2 join): S1''
  INCONCLUSIVE under its own pre-declared coldness clause (1 of 4 known-wrong rows readable),
  and the mandated second pass was **interrupted by an account-level API usage limit —
  access returns 2026-09-01**, which also blocks run 14 outright. The checkpoint was then
  read where it was measurable: a $0 battery census of the DEPLOYED rule. Three trees —
  ±120 window, document-scoped, post-dedup terms — moved the totals (50/33/10 → 42/22/5 →
  39/19/5 firings/gold-damps/harmful) and **left one invariant set of five harmful rows**.
  The hard clause (zero inversions on a named wrong-commit class) failed on all three, so
  the anchor is **DONE** by its own pre-registration and reverted from the branch.
  **What the arc actually established:** on the rows that matter the gold's carrier is
  *terse* — a table row, a bare line — and the competitor's is *discursive*, so any lever
  scoring documents by question-vocabulary overlap damps the gold. That refutes a whole
  family of decide-side levers, not one. **Surviving:** D3, the S2 join (the one replace
  site r09 left untouched now joins — a correct commit recovered, none lost), parked
  unmerged pending a gate run. **Registered en route:** a criterion that names specific rows
  can go unreadable between two passes of the same instrument (14 rows in / 14 out), so name
  a class and a bar and pre-declare the consequence of a named row going cold; and *a census
  must read the deployed rule end-to-end, never re-implement the constant it prices* — the
  r05 class, three instances in this arc, the newest signature being byte-identical numbers
  before and after a change.

- **r09e + the entity-key conferral + r10 — the tree of record read, one ruling enacted, one
  lever refused by its own bar (2026-08-25, all $0,
  `docs/unification/reports/{r09e-tree-of-record,r10-entity-key}.md`,
  `docs/unification/conferrals/entity-key-conferral.md`).** r09e replayed run 13's record on
  the parked tree itself: 66/104 readable (the §18.9 warm-through grows the readable set pass
  over pass — 58 → 66 → 68 across three passes); two of run 13's four wrong rows still commit
  wrong, one is repaired to withheld, one is cold, so **a gate run on this tree fails a
  zero-wrong conjunct as-is — measured, not predicted**; the two decision-level collaterals
  attribute to the temper stack, not D3 (five-row isolation on the A2 head). The conferral's
  rulings: warm-then-read (~the priced half now shrunk to one row); the **extract-side entity
  field RETIRES**; E1's bar frozen blind — zero channel harms AND ≥1 wrong-commit repair,
  with a withhold→answer conversion licensing nothing. **r10 built E1** (exact typed
  identifier filter at the base mint; pre-registered, then amended before implementation when
  the code showed only one mint site has a carrier) and the read REFUSED it: the sweep's
  marginal diff against r09e is **exactly one row** — the entity-qualifier row, wrong →
  correct at the strong branch, the first lever to repair it, with every other common row
  byte-identical (all five predictions pass) — but a channel-harm census driven through the
  **deployed** rule (a recorder on the deployed filter, the deployed `observe_hits`, all 104
  questions) found the rule fires on 6 questions where the motivating census read 3, and on
  one it **drops the gold and keeps the competitor** — an inversion the census had misread
  as both-keyed/no-op through its re-implemented first-hit-by-cache-key carrier mapping. The
  census-reimplementation class thus takes its fourth instance this arc and its first
  verdict-flip at a frozen bar; the harm sat precisely in the sweep's blind spot (all three
  census/deployed divergence rows are cold-mid-loop — readable at the base seam, unreadable
  at the decision layer; the predictions were all decision-layer). Consequence enacted: E1
  reverted from the parked chain, tree-identical to the pre-E1 head, suite green. **The
  terse-carrier finding is now a closed family, not a lesson about one lever: exact or
  fuzzy, hard or soft, any carrier-side requirement damps the terse gold, because terse
  carriers omit qualifiers.** What remains for the block: the parked tree carries two
  standing wrong commits (corroborate-tier; entity-qualifier, its one repairer refused) and
  master carries the un-repaired blocking row — the run-14 conferral must pick a tree and
  freeze the wrong-commit conjunct against that measured landscape.

- **Run 14 — the gate PASSES and the §6.12 deployment block CLOSES (2026-08-25,
  `gate-20260825T102725`; typed arm $0.69 live, mono archived at $39.01; the ruled tail of
  `docs/unification/conferrals/run14-conferral.md`, option A at full delegation).** The
  pre-fire tail ran as ruled, same day as the cap raise. (1) *The warm pass* (~$0.09 of the
  $5 cap) found and fixed a warm-instrument defect: the first firing warmed the DEPLOYED
  trajectory's frontier, which the $0 replay lane never visits, because `rerank_hits` is
  uncached with fail-open — under the refusing client the rerank's raise is swallowed and
  the lexical top-k returned, so the replay lane deterministically takes the lexical branch
  wherever the deployed daemon scheduled `retrieve_rerank` and the rerank moved the window
  (per-pass call tapes: probe ≡ accept byte-identical; the priced pass diverges at the
  second /retrieve with 16 of 20 chunk hashes differing). The fix makes the priced pass a
  hybrid — deployed client at every §18.9-recorded seam (instrument client, joint_extract,
  expansion), refusal kept at every unrecorded one (rerank, raw llm) — trajectory parity
  with the acceptance pass, verified RED→GREEN live. **The same mechanism names r07's one
  persistently fidelity-divergent row**: the $0 replay's "deployed" arm is the deployed arm
  *modulo the rerank lane*. Disclosure, not a new arc (the cap stands); it does not touch
  run 14 itself, which prices the deployed arm live. Full artefact:
  `eval/gate-outside-option/run14-warm-disclosure.md` (KB). (2) *The $0 re-read* of run 13's
  record on the warmed parked tree (68/104 readable, fidelity 64/68, r06 control 1/1, zero
  discarders): zero new wrong commits; both readable run-13 wrongs (superset-confirm,
  warm-deliberate) convert to withheld. (3) *The refreshed splice*, registered before
  firing: PASS 0.977 / Δ̄ +0.583 [+0.147, +1.063]. **The live run: PASS on all four frozen
  conjuncts — P(Δ>0.05)=0.907 (≥ 0.90 at the frozen δ/level), Δ̄ +0.421 [−0.046, +0.920];
  the run-10 blocking row commits correct (the block's own class, repaired on the tree that
  ships); zero NEW wrong commits — the three wrongs are all run-13 rows (corroborate-tier,
  entity-qualifier, warm-deliberate); no named class worse — the superset-confirm row
  converts wrong → withheld.** Typed 60 ✓ + 2 ✓hedge / 3 ✗ / 39 withheld (miss 2 ·
  dispersed 37), answer rate 0.62 vs mono 0.97, correct-report 0.60 vs 0.91; judge grading
  flipped 5 mono rows, 0 typed. The live 0.907 sits under the registered 0.977: the gap is
  the warm-deliberate row reporting wrong live where the warmed re-read had it withheld — a
  carried run-13 row (not NEW by the frozen baseline), disclosed rather than renegotiated,
  and consistent with §6.13's standing residue (the warm-through's monotone accumulation
  names live-vs-replay divergence on warm-deliberate rows as the expected wobble class).
  **Ruling 4's PASS branch ENACTED, no further keypress: the §6.12 block is CLOSED; the
  parked tree (`r10-entity-key` post-E1-revert) is merged to master src-tree-identical;
  master deploys to live (`bin/ask-live` / jarvis).** What ships that run 13 did not have:
  the §5-deduped JOIN at S1/S3/S4/S5 with the correlation key on the wire, T1's strict-span
  guard, A1's per-document witness collapse, A2's synthesised-confirm covariate cap, and
  D3 (S2 joins). The two standing wrongs ride in production, priced and published; the hard
  clause (no lever ships while it makes a named wrong-commit class worse) binds every
  successor, including the proplang graduation path (ruling 5).

- **Four unordered sources on the decision path — the cache was doing the work of determinism
  (2026-08-19/20, tranche-2 M0/M0.5, `scripts/collapse_replay.py` + the M0.5 probes, $0
  deterministic).** The decision-equivalence instrument built at M0 found two ties resolved by
  an unordered source, both pre-dating this arc. (1) `lookup.dedup_correlated` broke its
  equal-covariate tie with `max()` over a *set* of artefact keys, so which duplicate document
  survived — and with it which observations reached the posterior, which candidates existed,
  and in what order — depended on the interpreter's per-process string hash seed: **25 of 102
  recorded fixtures (24.5%) decide differently across seeds 0–4** (18 at a single seed). (2)
  `core/retrieval.py:retrieve_set` preserved pkm's FTS order, which is nondeterministic among
  tied BM25 scores *within a single process*: over the 104-question battery at k=80, **87
  questions (84%) return a different ORDER and 45 (43%) a different SET between three
  identical calls**; 88 carry ties, 742 tied hits in total. (3) The BM25 **scores themselves**
  are not reproducible: DuckDB sums a term's contributions in a parallelism-dependent order, so
  two identical calls on an unchanged corpus return the same hits at scores differing by 1–2
  ulp (18 of 80 hits on a measured question; largest delta 3.6e-15). A key whose leading term
  is the raw score therefore cannot be a total order *however good its tie-breakers* — the
  near-tie is decided by whichever draw the engine made. With (2)'s ordering alone, 48
  questions still returned a different order and 22 a different set; quantising the leading
  term takes both to **zero**. Found at M0.5, deliberately left unfixed under that brief's
  one-change instruction and carried as a named question, then ruled in at review and landed as
  the checkpoint's second commit. (4) `probes.probe_corroborate`
  (`src/life_agent/core/probes.py`) carries *both* pre-M0.5 layers in one function — a dedup
  keeping the first-arrived candidate on a strict `>`, then a raw-score sort with no
  tie-breakers at all — and is live whenever the gather lane runs. Found at M0.5 while
  auditing the fix's blast radius and deliberately NOT fixed under the same one-change rule;
  at review it was sequenced to M1 *behind* a recorded gather-lane trace, because **no fixture
  exercises that lane** and a change to the decision path with no oracle is a hope, not a fix
  (module-collapse-design §6.9 carries the disposition and its pre-committed fallback).
  **What kept the ledger comparable
  was the §18.9 cache, not the code.** The retrieval stage is keyed on (query, corpus digest,
  k) and the answer stage on its content hash, so the first run to compute a stage froze one
  arbitrary draw and every later run was served it. Comparability therefore held exactly as
  long as the cache entry survived, and any recomputation — a new question, a corpus-digest
  change, a different k, a version bump, or a cache loss (the 2026-08-18 orphan sweep is the
  worked example) — silently re-rolled it. The decisions were never a function of the corpus
  alone. It also explains the cold derivations M0 saw on re-runs: an unstable order is an
  unstable key. *Fixed at M0.5* by declaring a total order at each site — first-seen at equal
  covariate; `(-round(score, 9), artifact_cache_key, chunk_text)` for retrieval — with the seed
  sweep, the retrieval probe, and a per-hit score-equality check across identical calls as the
  kills. The quantisation resolves ties without manufacturing them: the census is unchanged at
  88 questions and 742 tied hits before and after, and a test pins that a difference above the
  quantum still decides the rank against the declared key's preference. *What it does not fix:* the readings already in this
  ledger, which stand as recorded with this entry as their caveat. Runs after M0.5 are the
  first whose evidence sets are reproducible by construction rather than by cache residency.
