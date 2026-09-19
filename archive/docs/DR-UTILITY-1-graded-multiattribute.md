# DR-UTILITY-1 — graded answer quality and multi-attribute cost

**Status:** specification. No implementation. Supersedes nothing; extends the gauge.
**Role of this document.** `DR-DECISION-1-action-space-and-utility.md` is **the spec** —
the action space and utility stated whole, and the thing to build from. This document is
**the record**: the §0 gauge ambiguity and its consequences, the §0.1 errata, and the
L1/L2/L3 rationale that DR-DECISION-1 references rather than restates. Read DR-DECISION-1
to know what to do; read this to know why, and what went wrong on the way.
**Open questions this spec deliberately does not answer:** `OPEN-QUESTIONS-utility.md`.
**Vocabulary:** `GLOSSARY.md`.
**Provenance:** `SESSION-RECORD-2026-09-05.md` — in particular C-1 (the elicitation
erratum) and C-3 (why OQ-0 was malformed, not merely leaning).

## 0. Which Ū are these numbers quoted at? — READ FIRST

**This document's first version quoted every headline number at `u_wrong = −9`
without saying so, while the reaction-conditioned fold sits at `−5.131` and
`docs/unification/conferrals/s18-bar-conferral.md` asks precisely which Ū the §18 bar
should be quoted at. (It was **answered the next day** — see the correction below — which
this document also missed.)** So this spec picked a side of an open ruling
silently — the exact failure it was written to criticise. Recorded here rather than
repaired quietly.

Every number in §1 and §4 is stated at **both** candidate values. **Neither is presented
as the default**: −5.131 is the *reaction-conditioned* fold, which `r49b` shows is both
circular (reactions project from verdicts on the log the gate scores) and unstable
(−5.9395 → −8.8301 → −5.1310 across 20 boot records). Calling it "the deployed value" — as earlier drafts of this
document did — inherits a choice rather than making it. **[CORRECTED 2026-09-06]** **OQ-0 was RULED 2026-09-05** (`conferrals/a3-regime-conferral.md`, `RULINGS` M-34, enacted GD-29): the guard stands and is made honest — the gate keeps `frozen-elicitations`, publishes both break-evens beside the measured reach, and quotes **INCONCLUSIVE** when the reach falls strictly between them. `VERDICTS` and `RegimePairing.straddles` are **built** in `core/gate.py`. The open successor is **OQ-0′** — whether `u_wrong` should be *derived from a risk target* instead. The two-estimate table below is still the right
reading of *why* it was hard, and the gate now publishes exactly that pair.

The two gauges, with everything else held at run-18 values (oracle p = 95/101 =
0.9406 at $0.3751, `lambda_usd` = 1.3311):

| | reaction-conditioned fold (−5.131) | elicitation-only (−8.9993) |
|---|---|---|
| commit bar `\|u_w\|/(1+\|u_w\|)` | **0.8369** | 0.9000 |
| ledger max credence 0.8706 | **clears the bar** | does not clear |
| `u_assert(0.9406)` | **+0.6358** | +0.4060 |
| EU(escalate) vs abstain = 0 | **+0.1365 — escalation WINS** | −0.0933 — escalation loses |
| willingness to pay at p = 0.9406 | **$0.478** (oracle costs $0.375) | $0.305 |
| break-even `lambda_usd` | **1.695** (in use 1.3311 — clears) | 1.082 (does not clear) |

The break-even `u_wrong` of **−7.4285** is unchanged; what changes is which side of it
the estimate falls on — and the two candidates **straddle** it, which is why the basis
question is load-bearing rather than cosmetic. One refinement in the other direction: the **$0.75 ceiling for a
perfect oracle is gauge-independent** — at p = 1 the wrong-term vanishes and the
ceiling is `1/lambda_usd`. So OQ-7 governs the ceiling and OQ-0 governs everything at
p < 1.

**The substantive consequence, and it does not depend on OQ-0:** under *either*
estimate there is **no escalate action in the action set at all**. The affordance is
absent, not out-priced. That is a missing-affordance defect and it needs no
re-elicitation to fix. What OQ-0 decides is only whether the action, once built, fires
today. See §7 and `OPEN-QUESTIONS-utility.md` OQ-0.

## 0.1 Two errata

The external review of 2026-09-05 stated that `u_wrong` and `lambda_usd` were
"asserted, not elicited". **That is wrong and the record should say so:**

- `u_wrong` **was elicited** (2026-06-18, stated as a 10:1 ratio, dialled back from
  20:1). It is not a default someone forgot to set.
- `lambda_usd` **was reportedly elicited** (2026-08-09, 1.5 ± 0.25, folded to
  1.331 ± 0.203) with a contamination disclosure — the elicitation made *after* the
  owner saw the λ↔verdict map. **Unverifiable from public master:** `elicitations.jsonl`
  is not in the repository, so this claim rests on a working-copy artifact and should
  not be cited as established until it is.

The files that carried the incorrect wording (`core/router.py`, `tests/test_router.py`,
branch `routing/escalate-arm`) are being deleted as an incorrect artifact, so the
erratum needs no code change — but the same wording reached `docs/ORIENTATION.md`,
which **is** an entry-point document, and is corrected there.

Genuinely unelicited: `kappa_att`, `tau`, `tau_narrative`, the six `*_scale_*` shape
latents, and `u_wrong_scoped`'s `noise_sigma`.

## 1. The defect

The owner's argument: *every question is answerable at some finite price, so silence
should not dominate unconditionally — there must exist a willingness to pay above
which consulting an external model beats staying silent.*

The argument is correct, and **whether the current model already satisfies it depends
entirely on OQ-0** (§0). A willingness-to-pay point exists at both gauges; whether it
sits above or below the oracle's $0.375 is what the choice of estimate decides:

```
u_assert(p) = p·u_correct + (1−p)·u_wrong          # oracle p = 0.9406, run 18
  at u_wrong = −5.131 (reaction-conditioned):  0.6358  →  WTP $0.478  >  $0.375   ✓ escalate wins
  at u_wrong = −8.9993 (elicitation-only): 0.4060  →  WTP $0.305  <  $0.375   ✗ escalate loses
```

The ceiling for a *perfect* oracle is `1/lambda_usd = $0.75` at either gauge — the
model will not pay more than 75¢ for any answer however valuable, and that ceiling is
a function of `lambda_usd` alone (OQ-7), not of the gauge.

**Under either estimate the escalate action does not exist**, so the missing-affordance
defect stands regardless. What the estimates disagree about is narrower: under the
reaction-conditioned fold the preference to pay already exists and needs only an
affordance; under the elicitation-only value the preference itself would also have to
move (OQ-1). Same first step, different second one — which is why OQ-0 is prior but not
blocking. **Post-ruling:** M-34 keeps the gate on the elicitation-only value and quotes
INCONCLUSIVE on a straddle, so the honest reading of §7.1 is *inconclusive at the reach we
have*, not a claim either way.

The two structural impoverishments:

**D1 — one oracle at one price.** There is no cost-quality frontier. `_ORACLE_P = 0.9`
(`lookup.py:200`) is a single constant for a single consultation. Nothing expresses
*spend more, get a better answer*, which is exactly what "answerable at some price"
requires.

**D2 — binary grading is applied to answers that admit degrees.** Note the careful
wording. The original framing of this defect ("answer quality is binary") was wrong,
and the owner's objection of 2026-09-05 is what corrects it:

> "Answer quality isn't binary at all, in my opinion? Maybe a shorter answer is better
> than a longer one, maybe sometimes it's the other way around?"

That is right, and it forces a split this spec is built around (§3.1). Binary grading
is **correct** for a point fact — there is no partial credit for a nearly-right
passport number. It is **wrong** for anything carrying a metric: quantities, dates,
intervals, sets, aggregates. And for open-ended answers, *no scalar is correct at all*,
because the thing that varies is fit to a need that the answer alone does not contain.

The concrete damage is confined to the middle case: intervals lost by 4.5–7 gauge
units, 0 of 2,835 narrative cells cleared break-even, and partial credit is dead
everywhere it should have been alive.

A third fact frames both, and it is **gauge-conditioned**: the ledger's maximum
recorded credence is **0.8706** over 6,654 rows. Under the reaction-conditioned estimate
the commit bar is **0.8369 and that ceiling clears it** — the system can and does commit.
Under the elicitation-only estimate the bar is 0.9000 and the ceiling never reaches it. "The deployed system
has never once committed a report" was asserted in the first version of this document
and **is true only under the elicitation-only estimate**; it is withdrawn as an unconditional
claim.

## 2. What already exists (build on it, do not rebuild)

- **The graded pattern is proven.** `u_assert`'s `p_correct` is already a real number,
  and three callers pass non-0/1 values: `realised_aggregate(...)` (Winkler),
  `oracle_p`, and narrative's `θ·tf`. `RealisedResponse.x: float | None` (`gate.py:125`)
  already carries a continuous grade into `realised_utility` (`gate.py:196-202`).
- **`interval_options` is the working template.** `x = max(0, 1 − W/(2·|gold|))`
  (`decide.py:192`, grade at `:134-154`), with width paid *inside* the score — "there is no external
  width penalty, and adding one would be a second rule (r30b · C1)".
- **Six shape-scale latents exist and are inert** — `voi_scale_*`, `regret_scale_*`,
  N(1.0, 0.35), never activated, with a 314/314 byte-identical replay proving they are
  a no-op. This is the designed opt-in path; use it rather than adding new plumbing.
- **`shaped_u_bar` does NOT grade.** It affinely rescales the two endpoints of a still
  binary loss (`decide.py:71-103`). Do not mistake it for partial credit.

So this spec is a **generalisation of an existing, tested pattern**, not new machinery.

## 3. Specification

### 3.0 Two dimensions, and why only one of them is scoreable

An answer is judged on two independent things:

- **Correctness / precision** — how close the claim is to the truth. Given a claim
  *shape*, this has a canonical ordering: exact match for a point, Winkler for an
  interval, F1 for a set, containment for a range.
- **Fit to need** — length, verbosity, framing, whether to volunteer a breakdown,
  whether to lead with the caveat. There is **no universal ordering here**, and the
  owner is right that there cannot be: a short answer is better sometimes and worse
  other times, and which holds depends on the question, the moment, and the person —
  none of which are properties of the answer. Any scalar invented for it will be
  arbitrary and, being arbitrary, gameable.

The design consequence: **score correctness, never fit-to-need.** Where fit-to-need
does not vary, scoring is complete and rigorous. Where it does vary, scoring is a
fiction and the honest action is to escalate rather than to invent a number.

This partitions questions into three lanes, and the partition is the spec's backbone:

| lane | example | fit-to-need varies? | grade |
|---|---|---|---|
| **L1 point-fact** | "my policy number" | no — one string is the answer | **binary, and that is correct** |
| **L2 metric** | quantity, date, interval, threshold, set, aggregate | mostly no — question shape fixes answer shape; what varies is *precision* | **graded (§3.1)** |
| **L3 open-ended** | "what should I do about X", "summarise my situation" | yes, irreducibly | **do not score — escalate (§3.4)** |

L1 needs no work: binary is already right. L2 is where every recorded partial-credit
failure lives, and where this spec does its work. L3 is the scope reduction.

### 3.1 Graded quality for L2, with a shape-dependent error cost

Replace the binary valuation with:

```
u(a, ω) = x(a, ω)·u_correct  +  (1 − x(a, ω))·u_err(shape(a))
```

`x ∈ [0,1]` is the answer's quality in world-state ω. The claim is false in ω iff
x = 0. **`u_err` is a property of the claim's shape, not a global constant** — this is
the load-bearing change, and it generalises the existing `u_wrong_scoped` insight
("a citable misread, not the catastrophic current-value wrong").

| claim shape | x(a, ω) | u_err |
|---|---|---|
| point value | 1 if exact match else 0 | `u_wrong` — unchanged anchor, at whichever Ū OQ-0 rules |
| scoped ("as of D, V") | as today | `u_wrong_scoped` (−2) — exists |
| interval | Winkler `max(0, 1 − W/(2·\|gold\|))` — exists | **`u_vague`** (new) when the interval contains the truth; `u_wrong` when it excludes it |
| set / hedge | F1 or 1/\|S\| against gold set | **`u_vague`** when gold ∈ S; `u_wrong` when gold ∉ S |
| pointer-to-source | owner-set constant < 1 (OQ-4) | `u_vague` |

`u_vague`: a new elicited latent, small and negative, the cost of an answer that is
*imprecise but not false*. Its value is OQ-3. Suggested support `[-1.5, 0.2]` — but
the number must be elicited, not defaulted. `u_wrong` was elicited (§0.1); what went
undecided was *which folded Ū to quote it at*, and that ambiguity is what OQ-0 closes.

**Worked check (gauge-independent — no wrong-term appears), 3-way hedge containing the
truth**, `u_vague = −0.2`:
`x = 1/3` → `0.333 + 0.667·(−0.2) = +0.20`. Beats silence. Under today's model the
same hedge is worth a flat `u_hedged = 0.4` regardless of set size — see §5.

### 3.2 Multi-attribute cost

```
EU(a) = u_graded(a) − λ$·c$(a) − λt·ct(a) − λp·d(a)     subject to  a ∈ Feasible(q)
```

| attribute | measured by | rate | shape |
|---|---|---|---|
| money | metered API spend (**not** imputed token pricing — r28 V3) | `lambda_usd` | linear |
| time | `latency_s`, already on `DecisionEvent` (`decisions.py:179`), **recorded today and priced nowhere** | `lambda_time` (new) | linear to a patience threshold, steeper after — OQ-2 |
| privacy | count of distinct SENSITIVE corpus items whose content would newly cross the machine boundary this session | `lambda_priv` (new) | linear **within a class**; see below |

**Privacy is not a price for the top class.** Each corpus item carries a disclosure
class:

- `OPEN` — no cost.
- `SENSITIVE` — costs `lambda_priv` per newly disclosed item. Novelty matters: you do
  not pay twice to disclose the same fact in one session.
- `SEALED` — **a hard constraint, not a large negative number.** Any action that would
  transmit SEALED content is infeasible at any price.

The rationale is precisely that large negative numbers get traded away when the answer
is valuable enough, and for medical, financial or third-party-confidential material
that trade must not be available to an argmax. This is the one place the model is
deliberately **not** a scalar utility.

**Where the constraint is enforced:** host-side, by withholding the menu name from
that tick. Verified against the protocol — `policyPick` returns `Nothing` only for an
empty candidate list (`Membrane.hs:319-320`); there are no feasibility masks and no
refusal semantics for actions. Per-tick name publication is the supported mechanism
(`membrane-wire.md:66-70`). The constraint therefore belongs to the host, which is
also where it belongs conceptually.

**Scalarisation happens host-side.** The wire carries one `Rational`; `Expr` has no
product sort, and giving it one is a language change this spec explicitly refuses
(see `proplang/appendage-spec.md` §G5). The host owns preferences; the language owns
inference.

### 3.3 The escalation ladder

D1's fix. Not one oracle — a frontier, declared as one menu name with several grid
points, each with its own price and its own learned reliability:

| rung | example | c$ | ct | expected p |
|---|---|---|---|---|
| E0 | no escalation | 0 | 0 | — |
| E1 | small model, single sample | low | low | learned |
| E2 | strong model, single sample | mid | mid | learned |
| E3 | strong model, extended sampling / self-consistency | high | high | learned |
| E4 | ask the owner (`ask_clarify`, exists) | 0 | `lambda_int` | `_ORACLE_P` |
| E5 | human research | — | — | OQ-5 |

Reliability per rung should be **learned, not declared**: put a guard on the writable
name and let the posterior earn it (`membrane-wire.md:363-383` records measured
posterior growth 9.09e-3 → 1.02e-1 for exactly this construction). Declared kernels
would need a protocol change *and* a ruling; learned ones need neither.

With a ladder, "answerable at some price" becomes an argmax over rungs rather than a
yes/no on a single option — and the $0.305 willingness-to-pay stops being a cliff.

### 3.4 The scope reduction: do not solve general answer quality

**Claim: a rigorous graded utility is needed only over L2. For L3 the correct move is
to escalate, not to score.**

The argument: a utility function exists to rank actions. Ranking requires an ordering.
In L3 the ordering over answers is not a property of the answers, so any scalar the
system computes is invented. An invented scalar in an argmax does not produce good
judgement — it produces confident optimisation of the wrong thing, and it is precisely
the surface an optimiser will exploit. Escalation, by contrast, needs no quality score
at all: the escalate row is **flat over the simplex** because the oracle's value does
not depend on our candidate set. It is rankable without grading the answer.

This makes the structured-lane focus **load-bearing rather than convenient**. It is not
that structured questions are a good place to start; it is that they are the questions
for which a decision-theoretic treatment is *well-posed*.

Note the scope reduction applies to the **decision layer only**. The **measurement**
layer still needs open-ended grading — you cannot tell whether an escalation was worth
its price without judging the answer it bought. The existing blinded modal-of-3 LLM
judge covers this and should stay. Deciding without a scalar, and measuring with a
noisy one, is a coherent position: the judge's noise degrades an estimate, whereas an
invented scalar inside the argmax degrades behaviour.

### 3.5 What the reduction costs — the honest accounting

**Residual cases where L2 is real but fit-to-need still varies.** The collapse is
strong, not total. Three named exceptions, all handled by *enumerating shape options
and grading each*, which is the `interval_options` pattern generalised — form becomes
another priced row, not a free-text choice:

1. **Near-boundary threshold.** "Did I spend over €5k?" with truth €5,010. A bare
   "yes" is correct and misleading. Needs a `value+bound` shape ("yes — €5,010").
2. **Large sets.** Three doctors: list them. Forty: a list is the wrong form and the
   answer is a count plus a characterisation. Form is *size-dependent*, so the shape
   option set must include `count+characterisation`.
3. **Volunteered decomposition.** "How much on X?" — bare total, or total plus the
   three invoices behind it. Largely absorbed by the citation channel, which already
   attaches sources independently of the answer, but the choice to *volunteer* is a
   genuine residue.

**Open-ended classes where always-escalate is unacceptable.** Three, and the third is
a real hole:

1. **Oracle unavailable** (offline, outage, rate limit). The system degrades to "I
   cannot help right now" — a real regression for a local-first personal store, whose
   whole point is that the data is on the machine. Availability becomes network-bound.
2. **Below willingness-to-pay.** Abstain. Acceptable, and now visible as a price
   rather than hidden in a gauge.
3. **Barred by the SEALED constraint.** This is the sharp one: an open-ended question
   over SEALED content can be neither graded nor escalated, so **it has no action at
   all.** By construction, the most sensitive material gets the worst service.

**The fallback that closes (3), and it is the best result in this spec:
pointer-to-source.** "I cannot answer this, but the answer is in these three
documents." It converts an open-ended *generation* problem into a *retrieval* problem —
and retrieval is gradeable, by exactly the machinery L2 already needs. It requires no
oracle, discloses nothing, and works offline.

So pointer-to-source is not a consolation prize; it is the universal floor action, and
it should be available in every lane. A system that always either answers, points, or
prices its silence has no dead cells.

Remaining open: whether a **local model rung (E0.5)** should sit below E1 to serve
SEALED open-ended questions with a degraded on-machine answer — OQ-6.

**Is the reduction too clean?** One way it is: the hard problem does not vanish, it
becomes a *dependency*. Usefulness on L3 is then bounded by willingness-to-pay,
network availability and the privacy constraint, none of which are capabilities you
can build. That is a fair trade only if L3 is a minority of real questions — which
brings the classifier into scope, below.

**The classifier is now load-bearing and is currently weak.** `answer_shape.py` is a
regex whose measured agreement with a blind manual reference is **0.74, with
disagreement one-directional toward `exact`** — and `exact` is the default, a grab-bag
holding both L1 point facts and L3 open-ended questions. On the gate set only 22 of 104
are classified quantity/threshold/set. Under this spec, misclassifying L3 as L1 means
binary-grading an ungradeable answer, which is the current failure. **Re-deriving the
lane classifier (L1/L2/L3, not the current four shapes) is a precondition for the scope
reduction, and its accuracy should be measured before anything downstream is built.**

## 4. What this does to the known cases

All figures below are stated at **both** gauges per §0.

**The 41 abstentions — escalation fixes these, graded quality does not.** The dispersed
rows have high `p(NONE)`: the truth may not be in the candidate set at all. Under any
quality measure, asserting into that mass is correctly penalised. The escalate row is
the only action whose value **does not depend on our candidate set**, which is exactly
why it is flat over the simplex. But note the median leader credence on the abstained
population is **0.3688** — far below either bar — so most of the 41 abstain correctly
at either gauge. Dispersion is real; escalation is the fix for it, not re-gauging.

**EU(escalate) vs abstain = 0:** **+0.1365 under the reaction-conditioned estimate (escalation already
wins at today's $0.375)**; −0.0933 under the elicitation-only estimate, needing a rung under
$0.305 or a re-based `lambda_usd`. The metering fix (§3.2) may move `lambda_usd` more
than any elicitation does: under a flat-rate plan the marginal dollar is ≈0 until the
cap.

**The intervals that lost by 4.5–7 units — graded quality fixes these, at either
gauge.** With `p(NONE) ∈ [0.26, 0.41]` the NONE atom alone contributes **−1.3 to −2.1
under the reaction-conditioned estimate** and −2.3 to −3.7 under the elicitation-only estimate, before anything else
is counted. §3.1 charges `u_vague` instead of the full wrong-cost when an interval
*contains* the truth, which is most of the recorded gap either way. Prediction:
intervals become choosable on the rows r31 priced them on.

**The break-evens** (`u_wrong` = −7.4285, `lambda_usd` = 1.082 under the elicitation-only estimate
/ 1.695 under the reaction-conditioned estimate) are the deliverable, not thresholds to clear. Note the
deployed gauge sits *shallower* than the −7.4285 break-even and the elicitation gauge
*deeper* — the two straddle it, which is precisely why the question was
load-bearing rather than cosmetic.

**The break-evens** (`u_wrong = −7.43`, `lambda_usd = 1.082`) should be **reported as
the deliverable**, not treated as thresholds to clear. The right output of a gate run
is the curve, not a point verdict — that is what makes a load-bearing constant visible
before it becomes load-bearing.

## 5. Anti-gaming

**Principle: informativeness is priced *inside* x, never as an external penalty.**
That is r30b C1, already doctrine here, and the Winkler width term is the working
implementation.

Under §3.1, always-hedge is not a winning strategy because a vaguer answer has a lower
`x` *by the definition of the score*: a 3-way hedge scores 1/3, a 40-way hedge scores
0.025 and lands at `0.025 + 0.975·(−0.2) = −0.170` — below silence.

**The gaming surface exists today, before any graded measure.**
`out["hedge"] = [u_hedged] * k + [u_wrong]` (`lookup.py:968`) is **independent of k**:
hedging 2 candidates and hedging 40 are both worth 0.4. The reason nobody has noticed
is that the gauge over-abstains so hard nothing reaches the hedge region. Fixing the
abstention pathology without fixing this would open the hole rather than create it —
the u_abstain conferral already records that pricing silence at −0.149 buys
`ask_clarify` long before −0.982 buys `report`, i.e. mass moves into the hedge/ask
region *first*, where nothing penalises vagueness at all.

**Therefore: §3.1's set/hedge scoring is a precondition for any move on the abstention
gauge, not a follow-up to it.**

## 6. Deployment warning — read before costing any of this

`lookup.action_utilities` is **not the deployed decide surface.** The gate's typed arm
runs through `executor` → the credence daemon, whose action set is built in
`../credence/apps/answer-brain/brain/answer_brain.jl` (`decision_fpa`:
`report_j × K`, `hedge`, `ask_clarify`, `abstain`). `report_scoped_j` already has no
daemon counterpart.

A graded-quality lever built only in this repo **would measure nothing and change
nothing for the owner.** Every item in §3 must land in both surfaces, or in the daemon
alone. Any estimate that assumes otherwise is wrong by roughly a factor of two.

## 7. Sequence

Nothing here is authorised to be built. This is the order the work would take *if*
signed off, listed so the dependencies are visible during review.

**Re-sequenced after the OQ-0 finding.** The first version put "elicit the open
questions" at step 1 on the reasoning that escalation was out-priced and therefore
needed a re-gauge to become rational. Under the reaction-conditioned estimate it is **already rational
(+0.1365)** and the blocker is a missing affordance. So elicitation is no longer
uniformly prior — only the *ruling* is.

0. **Rule OQ-0** — which Ū these numbers are quoted at. A ruling, not an elicitation:
   cheap, and every figure below is unreadable without it.
1. **Re-derive the lane classifier** (L1/L2/L3) and measure its accuracy. Independent
   of the gauge entirely; the scope reduction rests on it and the current regex is 0.74
   (§3.5).
2. **Specify the escalate affordance.** If OQ-0 rules for the deployed Ū, this needs
   **no elicitation at all** — the preference already exists and has nowhere to act.
   Safe to precede §3.1 because escalation draws mass out of `abstain`, not into
   `hedge`: under the reaction-conditioned estimate a 70%-containment hedge scores `0.7·0.4 +
   0.3·(−5.131) = −1.26`, losing to both abstain (0) and escalate (+0.14), so the
   k-independent hedge hole (§5) is not opened by this step.
3. Elicit OQ-3 (`u_vague`) and OQ-4, then §3.1 set/hedge scoring — still a precondition
   for any move on the **abstention gauge** (§5), which is now a separate and less
   urgent question than it looked.
4. §3.5 pointer-to-source as the floor action in every lane.
5. §3.3 ladder, rungs E1/E2 only, reliability learned rather than declared.
6. §3.2 metering (money real, not imputed) + `lambda_time`.
7. §3.2 privacy classes + the SEALED constraint.
8. Re-run the gate reporting **curves over the ruled range**, not point verdicts.

Sequencing note: 0 → 2 is the routing objective and is now the cheap half. 1 → 4 is the
L2/L3 partition and its floor. If OQ-0 rules for the elicitation Ū instead, step 2
reverts to requiring OQ-1 first and the original ordering stands.
