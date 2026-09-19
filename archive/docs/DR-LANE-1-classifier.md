> **SUPERSEDED by `DR-DECISION-1-action-space-and-utility.md`** (2026-09-05).
> The action space and the utility over it are not separable — a preference cannot be
> stated about an option that does not exist — so this document was folded into the
> consolidated decision-problem spec as §6 (the lane classifier and its measurement protocol). Kept only for its
> working; read DR-DECISION-1 instead.

# DR-LANE-1 — the L1/L2/L3 lane classifier

**Status:** specification. No implementation.
**Depends on:** `DR-UTILITY-1-graded-multiattribute.md` §3.0 (the lane partition).
**Gauge-independent.** Nothing here changes under either OQ-0 ruling — the lanes are a
property of questions, not of preferences. This spec is safe to act on immediately.

## 1. Why this is load-bearing

`DR-UTILITY-1` reduces scope by refusing to score open-ended answer quality: grade L1
and L2, escalate L3. That reduction is only sound if questions are assigned to lanes
correctly. **The classifier is the load-bearing component of the whole utility
re-specification, and it is currently a regex.**

| lane | what it is | grading |
|---|---|---|
| **L1 point-fact** | one unambiguous value is the answer | binary exact match — **correct, not impoverished** |
| **L2 metric** | answer carries a metric: quantity, date, interval, threshold, set, aggregate | graded (`DR-UTILITY-1` §3.1) |
| **L3 open-ended** | fit-to-need varies irreducibly | **do not score — escalate** |

## 2. The failure mode, stated first

**Misclassifying L3 as L1 means binary-grading an ungradeable answer.** The system
scores a rich, context-dependent answer as right-or-wrong against one gold string,
almost always scores it wrong, and abstains. This is not hypothetical — it is the
current behaviour, because:

- `DEFAULT_SHAPE = EXACT` and `ANCHOR_SHAPE = EXACT` (`answer_shape.py:35-36`): every
  unmatched question falls into `exact`.
- The module's own header records agreement of **0.74 against a blind manual reference,
  with disagreement one-directional toward `exact`** (`answer_shape.py:6-7`).

So the default class is a grab-bag holding both L1 and L3, and the classifier's known
error pushes *into* it. Under `DR-UTILITY-1` that is the worst available direction.

Ranked by damage:

| confusion | consequence | severity |
|---|---|---|
| **L3 → L1** | ungradeable answer binary-graded, near-certain wrong, abstain | **worst** |
| L2 → L1 | partial credit discarded; intervals/sets never offered | high |
| L1 → L3 | escalates a question we could answer for $0.0036 | moderate — costs money, not correctness |
| L2 → L3 | as above, plus loses the exact-reasoner advantage | moderate |
| L1/L2 → L2/L1 | wrong grade shape; usually recoverable | low |

**Design consequence: the classifier must be asymmetric.** Errors toward L3 cost money;
errors toward L1 cost correctness and are invisible (they surface as abstentions, which
look like appropriate caution). **Specify a bias toward L3 on uncertainty**, which is
the reverse of the current bias.

## 3. Decision procedure

Three-stage, first match wins, with an explicit abstention:

1. **L2 detection — positive evidence required.** A question is L2 iff its answer
   carries a metric with a defined ordering: a quantity with units, a date or range, a
   comparison/threshold, a set, or an aggregate. Existing `SPACE_RULES`
   (`answer_shape.py:60`) already detect quantity / threshold / set and are a starting
   point, not the finished article.
2. **L1 detection — positive evidence required.** A question is L1 iff a single
   unambiguous value answers it *and* that value is the kind of thing the corpus stores
   verbatim: identifiers, names, dates-as-facts, statuses. **L1 must be positively
   identified, never inherited as a default.** This is the single most important change
   from the current design.
3. **Otherwise L3.** The residual class is open-ended, and it is where uncertainty
   lands by construction.

**Required inversion:** today unmatched → `exact` (L1-ish). Under this spec unmatched →
**L3**. The default class flips from the one that silently mis-grades to the one that
costs money and is visible in the spend.

### 3.1 Observable features the classifier may use

Permitted, in order of preference:

- **The question text.** Lexical and syntactic form: interrogative type, comparators,
  units, plurality, quantifiers, temporal expressions.
- **The question's answer *space*, where declarable independent of the corpus** — e.g.
  "how many" admits a count whatever the corpus holds.
- **Corpus-independent shape priors** learned from labelled questions.

**Forbidden:**

- **Anything posterior-dependent.** The classifier runs before evidence and must not
  read a credence, a candidate set, or a retrieval result. This preserves the existing
  posterior-blind coarsening discipline (`decide.py` interval construction, r30b) — the
  lane selects the action space; it must not be selected *by* the outcome.
- **The gold answer.** Obvious, but it is the easy way to get a flattering accuracy
  number, and it must be excluded explicitly in the measurement protocol (§5).
- **The eventual answer's length or form.** That is fit-to-need, which
  `DR-UTILITY-1` §3.0 establishes is not a property of the answer.

### 3.2 Adjudicating disagreement

The current rules are a fixed first-match precedence (threshold > set > quantity >
exact). Under three lanes:

- **L1 and L2 both fire** → **L2**. A metric answer graded binary loses partial credit;
  a point fact graded by a metric with a degenerate one-element ordering is harmless.
- **Any lane and L3 both fire** → **L3**, unless the L1/L2 evidence is *positive and
  unambiguous* per §3. Asymmetric, per §2.
- **Nothing fires** → **L3**.
- **Rules disagree with each other within a lane** → record the conflict as a
  measurement observation. Do not silently resolve by precedence and then report clean
  accuracy; precedence conflicts are exactly where the 0.74 lives.

## 4. Accuracy bar before the lane split is trustworthy

The split is trustworthy when both hold:

1. **Overall agreement ≥ 0.90** against the blind manual reference (§5).
2. **L3 → L1 confusion ≤ 0.02** of all questions. This is the asymmetric bar and it is
   the binding one: the overall number can look fine while the one damaging confusion
   is concentrated in it.

Rationale for the second bar rather than a single headline: at 0.74 overall with
one-directional error toward the default class, the headline number is not informative
about the failure that matters. A classifier at 0.92 overall with 8% L3→L1 is worse for
this architecture than one at 0.88 overall with 1% L3→L1.

**If the bar is not met**, the honest fallbacks in order: (a) widen L3 until it is —
which costs escalation spend and is measurable; (b) route the ambiguous residue to
pointer-to-source (`DR-ESCALATE-1` §5.1), which is safe in every lane; (c) do not ship
the lane split, and say so.

## 5. Measurement protocol

The owner will want the number before anything is built on it. Specify the measurement
so it can be run first.

**Reference set.** A stratified sample of real owner questions, **not** the 104-question
gate set alone — that set is a census of the instrument, not of the owner's questions,
and r29 already records the concern. Include questions the current system routes to
narrative, since those are exactly the suspected L3 population.

**Labelling.** Blind manual labelling into L1/L2/L3 by the owner, without seeing the
classifier's output and without seeing any system answer. Two passes separated in time,
or two labellers, so that **human self-agreement is measured first** — it is the ceiling
on any classifier score, and if the owner cannot reproduce their own labels at ≥0.90 the
lane partition itself is in doubt and that is a finding worth having early.

**Metrics reported, all of them, always:**

- Overall agreement.
- **The full 3×3 confusion matrix.** A headline number alone is what allowed 0.74 with
  one-directional error to persist.
- L3→L1 rate specifically, against the 0.02 bar.
- Per-lane support counts — a lane with 3 examples supports no conclusion.
- Human self-agreement, as the ceiling.

**Pre-registration.** Bars fixed before the run (§4), following existing practice. A bar
adjusted after seeing the matrix is not a bar.

**Frozen artifact.** Reference set hash, labeller, date, and classifier version recorded
with the result, so the number can be re-derived.

## 6. Relationship to `answer_shape.py`

`answer_shape.py` is not replaced. Its four shapes (`SHAPES`, `answer_shape.py:30`)
remain the **grading** vocabulary within L2 — quantity, threshold, set — and drive
`shaped_u_bar` (`decide.py:71`) and `interval_options` (`decide.py:192`).

The lane classifier is a **new, coarser layer above it**: lane decides *whether and how
to score*; shape decides *which metric* within L2. Two consequences:

- `EXACT` stops being a default and becomes a positive L1 label. `DEFAULT_SHAPE`
  (`answer_shape.py:36`) must change or the grab-bag survives under a new name.
- The six inert `*_scale_*` latents (`DR-UTILITY-1` §2) are L2-internal and unaffected.

## 7. Uncertainty in this spec

- **Whether L1 can be positively identified from question text alone.** "What is my
  policy number" is clearly L1; "what did the insurer say about the claim" may be L1,
  L2 or L3 depending on what the corpus holds — which §3.1 forbids the classifier from
  consulting. If positive L1 detection turns out to require corpus access, the
  posterior-blind constraint and the L1 lane are in tension and **the constraint should
  win**, with L1 shrinking accordingly.
- **Whether 0.90 / 0.02 are the right bars.** They are proposed, not derived. The
  derivation would price a lane error in gauge units and set the bar where the expected
  loss crosses a threshold — doable once OQ-0 and OQ-3 are ruled, and preferable.
- **Whether the owner's real question distribution has enough L2 to matter.** If most
  real questions are L1 or L3, the graded-utility work in `DR-UTILITY-1` §3.1 serves a
  thin slice and the escalate affordance carries almost all the value. **The census in
  §5 answers this and should be read before committing to the L2 grading work** — it is
  the cheapest way to find out that half this programme is unnecessary.
