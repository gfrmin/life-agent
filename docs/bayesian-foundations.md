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
  `(tx_time, question_id, decision_id, kind, valence, reason)`; v0 carries `kind = verdict`,
  `valence ∈ {good, bad, note}` from the existing ask-live g/b/n capture, plus a **nullable
  `reason`** — the free-text note `capture` already prompts for on `bad`/`note`. The reason
  is the *one disambiguator that cannot be reconstructed after the fact* (it resolves the
  contamination below); it is opt-in and one keystroke, so logging it breaches no
  passivity, and the slot lands now even mostly empty. The vocabulary grows by edit as the
  later streams land (`correction`, `reask`, `clarify_reaction`, `disposal`).
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
  the unchanged, frictionless g/b/n prompt; it never probes preferences. The
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
