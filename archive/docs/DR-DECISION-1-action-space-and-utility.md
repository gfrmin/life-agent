# DR-DECISION-1 — the decision problem, stated whole

**Status:** specification. No implementation.
**Supersedes:** `DR-ESCALATE-1-affordance.md`, `DR-LANE-1-classifier.md` (folded in as §4
and §6).
**Depends on:** `DR-UTILITY-1-graded-multiattribute.md` — its **§0 gauge table and OQ-0
are not restated here**; read them first. Open questions live in
`OPEN-QUESTIONS-utility.md`.
**Citation policy:** symbol first, line numbers are hints. Verified against local
`master` (life-agent, proplang) and branch `m3` (tannen) on 2026-09-05.
**Provenance:** `SESSION-RECORD-2026-09-05.md` — settled decisions D-1…D-12, the
corrections that produced this document (C-2, C-9 especially), the literature the claims
trace to (R-1…R-7), and the open questions.
**Amendments applied 2026-09-06** (owner-authorised; A-1…A-5, `SESSION-RECORD` §8): Chow
as an identity (§5.2.1); Bouchard (§4.1, §4.3); Zellinger design-choice record (§4.1);
`correct_premise` as a tenth family (§3.5, §7.6); **A-CAL / A-LANE / A-GRADE standing
assumptions (§2.1)**.
**Second literature pass applied 2026-09-06** (S-1…S-9, `SESSION-RECORD` §9): Bouchard
**corrected — the first record had it backwards** (§4.1, and the new open question at
§4.3.1); A-CAL's theorem cited (§2.1); novelty **withdrawn** for prefix dominance (§3.3),
`u_vague` (§5.2), `p_r` (§4.1) and VOI (§4.4). **Source tags [P]/[S]/[NF] are carried
through; no [S] has been upgraded to a settled fact.**

---

## 1. Why the action space and the utility are one document

**The diagnosis this overhaul rests on: the defect is a MISSING AFFORDANCE, not a
misspecified gauge.**

That correction came out of an independent audit against public master. Three earlier
turns of this work diagnosed the system as abstaining because `u_wrong` forbade
consulting an oracle. **Under either candidate estimate of `u_wrong` that diagnosis is
wrong, and for a reason that does not depend on OQ-0: there is no escalate action in the
action set to forbid.** The system does not decline to ask. It has no action with which
to ask.

Whether the action, once built, *fires today* is a separate and disputed question —
`EU(escalate)` is +0.1365 under the reaction-conditioned fold and −0.0933 under the
elicitation-only estimate. **The regime question was ruled 2026-09-05 (M-34/GD-29): the
gate keeps the elicitation-only value and quotes INCONCLUSIVE on a straddle.** For the
*decision layer* "one utility binds every decider" still applies, so the deciding number
and the gate's may legitimately differ — which is what M-34's "gate exempt by declaration"
means. **This document does not lean on either estimate.**

So the reason no utility function could express *"pay Claude"* is not that the utility
function was badly shaped. **The action was not in the space.** A preference over
options cannot be stated about an option that does not exist, and every attempt to fix
the gauge instead was working on the wrong object.

Two consequences that shape this document:

- The action space and the utility are specified **together, from scratch**, not as a
  diff. The current implementation appears only where it constrains what is buildable.
- Building the action **is not a bet on OQ-0.** Under the reaction-conditioned estimate it fires immediately;
  under the elicitation-only estimate it is the affordance that would carry the preference once OQ-1
  moves the number. Either way the action must exist first.

**The governing division, from the owner's correction of 2026-09-05:** *the host owns
preferences, the language owns inference* (`../../proplang/appendage-spec.md`). Which
actions exist, what they cost, and what is forbidden are host declarations. Which action
wins is inference. An earlier proposal to add an *oracle primitive to the language* was
withdrawn as a category error, and this spec is what replaced it.

**[OQ-0]** marks claims whose magnitude depends on which estimate is quoted. **The regime
was ruled 2026-09-05** (M-34/GD-29) — the gate quotes both and says INCONCLUSIVE on a
straddle — so these are now *reporting* instructions rather than open questions. Nothing
structural depends on them. The gauge table is in `DR-UTILITY-1` §0.

---

## 2. The decision problem

For one question `q` with posterior `P(ω)` over `ω ∈ {c_1..c_K, NONE}`:

```
choose  a ∈ Feasible(q)  maximising

  EU(a) = Σ_ω P(ω)·[ x(a,ω)·u_correct + (1 − x(a,ω))·u_err(a) ]
          − λ$·c$(a) − λt·ct(a) − λp·d(q,a)
```

Four commitments in that line, each argued below:

1. `x ∈ [0,1]` is **answer quality**, graded in L2, binary in L1, undefined in L3 where
   the escalate row is flat (§6).
2. `u_err` is **a property of the action's claim shape**, not a global constant (§5.2).
   This is the load-bearing change.
3. Costs are **three attributes, scalarised host-side** (§5.3).
4. `Feasible` is a **hard constraint set**, not a region of low utility (§5.4).

Continuation actions (`gather`, `ask`) do not fit this form and are specified separately
in §4.4 — they are valued by one-step lookahead, not by an outcome.

### 2.1 Standing assumptions

Named so they cannot be lost again. Each is a **precondition on the argmax**, not a
design choice, and each is currently **unestablished**.

**A-CAL — the posterior is calibrated.** `P(ω)` must mean what it says: among rows where
the leader credence is 0.85, about 85% must be right. The whole construction rests on
this and **nothing in these specs establishes it.**

Why it is load-bearing here specifically, and more so than in neighbouring work:
Mozannar & Sontag (2020) give the only known consistent surrogate loss for multiclass
learning-to-defer — they *train* a deferral policy and prove the surrogate consistent.
**We do the opposite: we compute EU from an explicit posterior and an explicit utility,
so we need no surrogate and no training — and we therefore have no learning-theoretic
guarantee about the policy we obtain.** The guarantee is traded for the calibration
assumption. That is a good trade only if the assumption holds.

It is also the assumption the commit bar is most sensitive to. The bar (§5.2.1) is a
*threshold on the posterior's value*, so miscalibration moves the operating point
directly — unlike a purely ordinal use, where monotone distortion would be harmless.

**A-CAL is the hypothesis of a theorem, not a hope.** Fumera, Roli & Giacinto (2000) show
**Chow's rule is optimal only against true posteriors** — with estimated posteriors it
does not give the optimal error–reject tradeoff. Since §5.2.1 establishes that our bar
*is* Chow's rule, A-CAL is precisely the condition under which our bar is the right bar.
**[S]** Their proposed remedy for partial failure is **class-specific thresholds** —
transported here, **per-lane bars**. The spec already conditions `p_r` on lane (§4.1) but
applies a single global commit bar; if calibration turns out to be lane-dependent (and
L1/L2/L3 have very different answer structures, so it plausibly is), the literature's fix
is to let the bar vary too. **Not adopted here** — it needs the calibration measurement
first — but it is the named next move if A-CAL fails partially rather than wholly.

Related and worth reading before the measurement: Herbei & Wegkamp (2006) prove the
plug-in rule (estimate posteriors, then threshold) is **consistent** — but consistency is
asymptotic and 104 rows is not asymptotic **[S]**.

**The alternative is to swap the assumption rather than establish it.** *No Need for
Learning to Defer? A Training-Free Deferral Framework … through Conformal Prediction*
(arXiv 2509.12573) obtains its guarantee from **conformal coverage rather than
calibration** — exchangeability instead of calibration, and distribution-free. That is
the closest published statement of this spec's own position (compute rather than train),
and it gets a guarantee where we currently have none. **Worth reading in full before
A-CAL is tested**, because if it applies it may be cheaper to adopt exchangeability than
to establish calibration. **[S]**

**What would establish it:** a reliability diagram and ECE over the recorded credences,
binned, with the 41 withheld rows included. Note the AURC re-cut
(`LITERATURE-AND-HARNESSES.md` §3) tests **discrimination, not calibration** — a good
ranking is necessary but not sufficient. Both are needed, and they are different
measurements. Neither has been run.

**A-LANE — lane assignment is correct.** §5.1's grading is conditioned on it and §6
gives the bars. Currently a regex at 0.74.

**A-GRADE — `x` is measurable for every action that carries it.** §5.1 assumes a grade
exists for sets, intervals, pointers and scoped claims. Only the interval grade is built
(`interval_options`, `decide.py:192`).

---

## 3. The action space

### 3.1 Today's space, and why it is not a limit

`AFFORDANCES` in `src/life_agent/membrane/world.py` declares four grid points
(`abstain`, `gather`, `ask`, `respond`) on **one writable name**. That is life-agent's
own choice, not a protocol limit: the menu is host-declared, `Menu = [(Name, Grid)]`
(`proplang/src/PropLang/Membrane.hs:80`), and no length check exists in `hello` or
`tick`. life-agent already publishes a K-dependent count on the same unmodified wire
(`act_grid_cat`, `src/life_agent/membrane/categorical.py`).

The deployed daemon's action set is built in the credence repo (`answer_brain.jl`,
`decision_fpa`) — **the binding constraint is that surface, not proplang.** Every action
below must land there or it changes nothing for the owner.

### 3.2 The specified space

Ten families. **Assert-at-a-shape are distinct actions, not one action carrying a
quality score** — the shape choice belongs in the argmax, which is the r30b precedent
where intervals entered as extra rows rather than as a second decision rule.

| # | Action | Yields | Cost | Feasible when |
|---|---|---|---|---|
| A1 | `point_j` (×K) | asserts `c_j` is the answer | ~0 | always |
| A2 | `set_m` (×K) | asserts "one of the top *m*" | ~0 | K ≥ 2 |
| A3 | `interval_ab` (≤8) | asserts a numeric range | ~0 | L2-quantity, ≥2 distinct numerics |
| A4 | `scoped_j` (×D) | asserts "as of date D, `c_j`" | ~0 | candidate `j` carries a date |
| A5 | `pointer` | ranked sources, no synthesised answer | ~0 | retrieval returned anything |
| A6 | `escalate_r` (×R) | an external answerer's answer | `$`, latency, disclosure | rung reachable **and** not barred (§5.4) |
| A7 | `gather_p` (×P) | more evidence, then re-decide | latency, sometimes `$` | probe applicable |
| A8 | `ask` | the owner's answer | owner's attention (`lambda_int`) | owner reachable |
| A9 | `abstain` | nothing | 0 | always |
| A10 | `correct_premise` | states that the question presupposes something false | ~0 | the premise detector fires (§3.5) |

A1, A3, A4, A7, A8, A9 exist in some form today. **A2 is respecified** (§3.3), **A5, A6
and A10 are new.**

### 3.5 A10 — correct-the-premise, and why it is an action rather than a lane

**Found by reading someone else's taxonomy.** AbstentionBench (arXiv 2506.09038) scores
six abstention scenarios, one of which is **False Premise**. A question whose premise is
false has, in the nine-family space above, **no lane and no action**: it is not
answerable, its withholding is not `dispersed`, and escalating it buys a confabulated
answer at full price. The right act is to *correct the premise*, and it was missing.

**It is an action, not a lane, and the reason matters.** Detecting a false premise
requires *evidence about the presupposition* — so it cannot be a lane assignment, since
§6 forbids lane assignment from reading any posterior or retrieval result. Putting it in
the action set keeps that discipline intact.

**It does not live on the answer simplex, and is feasibility-gated instead.** `P(ω)` is a
posterior over *candidate answers*; the premise's truth is a different proposition.
Two ways to admit it:

- *Enlarge the outcome space* to `{c_1..c_K, NONE} × {premise_ok, premise_false}` —
  correct, and it doubles the atom count and changes the daemon's simplex. **Rejected as
  disproportionate.**
- *Feasibility-gate it*, exactly as SEALED gates escalation (§5.4): a separate premise
  detector decides whether `correct_premise` is on the menu at all, and the row is valued
  against that detector's calibrated confidence `p_prem` as a **flat row** over ω. **This
  is the specified route.** §2's formula is unchanged.

The precedent is already in the spec: `p_r` for escalation rungs is likewise a scalar
reliability attached to an action whose value does not vary over our candidates.
`p_prem` inherits the same discipline as `p_r` (§4.1) — estimated, never a written
constant, and not updated by ungraded outcomes.

**Do not fold this into the NONE atom.** High NONE mass means *the answer is not among my
candidates*, which is fully consistent with a true premise and bad retrieval. Conflating
"I could not find it" with "the question is ill-posed" is exactly the error the NONE atom
exists to prevent.

### 3.3 Sets: why only K of the 2^K

A hedge over an arbitrary subset gives 2^K actions, which is the obvious reason not to
have them. It is unnecessary:

> **For a fixed size m, the top-m by credence dominates every other size-m set.**
> Quality `x` depends only on `m` (§5.1), so EU differs across same-size sets only
> through `P(gold ∈ S)`, which the top-m maximises by construction.

**This is a theorem with a name, not our argument.** Mortier, Wydmuch, Dembczyński,
Hüllermeier & Waegeman (2021, *DMKD* 35:1435–1469; arXiv 1906.08129) formalise set-valued
prediction as expected-utility maximisation over subsets and show that **for utilities
depending on set size and containment, the Bayes-optimal set is a prefix of the
posterior-sorted classes**, reducing 2^K to K. Del Coz, Díez & Bahamonde (2009, JMLR) did
the F_β case. **[S]** Cite Mortier; claim nothing.

**This also closes the uncertainty this section carried.** The worry was that grading sets
by F1 against a gold *set* would make `x` composition-dependent and break the collapse.
For a **single** gold label — which is our case — F1 against the predicted set is
`2/(m+1)` if contained and `0` otherwise: **size-only, so prefix dominance survives
under F1 exactly as under `1/m`.** It fails only for multi-label gold sets, which is a
different problem (Nguyen & Hüllermeier 2019, partial abstention in multilabel
classification).

So only the K **prefix sets** of the credence ordering need be enumerated. 2^K → K, with
no loss of optimality. This also disposes of the k-independent hedge (§7.3): a "set" is
now identified by its size, and size is what `x` prices.

### 3.4 Cardinality

Declared as grid points on **one writable name**, so the option space is **additive**.
The cartesian-product growth (`menuAssignments`, `Membrane.hs:110-113`) only bites
across *multiple* names — declaring each family as its own name would multiply. **Do not
do that.**

```
|A| ≤ 3K + 8 + R + P + 4          # +1 for A10 (§3.5)
     = 44   at K=8, R=4, P=4
```

Tractable: the daemon already scores K+1 atoms per row, and 43 rows is the same order as
today's `report_j × K` plus extras. Growth is linear in K. If K is unbounded, cap it —
the existing `MAX_INTERVAL_VALUES = 8` (`src/life_agent/core/decide.py:130`) is the
precedent.

---

## 4. The actions that are new or changed

### 4.1 Escalate — one action or a ladder?

**A ladder.** A single oracle at a single price is a point; "answerable at some price"
requires a frontier. Rungs are grid points on the same name, so the ladder costs nothing
in cardinality beyond R.

| rung | disclosure | `$` | latency | `p_r` |
|---|---|---|---|---|
| `E_local` | **none — on-machine** | ~0 | low–mid | learned |
| `E_fast` | yes | low | low | learned |
| `E_strong` | yes | mid | mid | learned |
| `E_sampled` | yes | high | high | learned |

The local rung matters for a reason that is **not** cost: it is the only escalation
feasible under the SEALED constraint (§5.4), because it discloses nothing. See §7.5 for
the accuracy it must clear to be worth having — the answer is demanding.

**The ladder is a known pattern, not a design of ours** — an LLM cascade in the
FrugalGPT sense (Chen, Zaharia & Zou 2023, arXiv 2305.05176). Two results from the
literature bear on it directly, and neither was in the first draft of this section.

**(i) Optimality conditions exist and we did not derive them.** Bouchard (2026), *Is
Escalation Worth It? A Decision-Theoretic Characterization of LLM Cascades* (arXiv
2605.06350), gives for k-model threshold cascades the first-order conditions under which
**a single shadow price λ equates decision-boundary expected escalation benefit to λ
times decision-boundary expected downstream cost** — equivalently, equalising marginal
quality-per-cost across active stage boundaries; and for two-model cascades, piecewise
concavity of the cost-quality frontier with reciprocal shadow prices linking the budget-
and quality-constrained formulations. **This spec sets rung prices by elicitation (OQ-8)
with no optimality theory. That is a gap, and Bouchard is where the theory is.**

**(ii) Structural cost caps the ladder — and the first draft of this amendment recorded
the result backwards.** It said "do not expand the rung set". Bouchard's headline is
stronger and points **the other way**: empirically, full fixed chains underperform the
pairwise envelope, and **a lightweight pre-generation router beats the best cascade on
four of five datasets, mainly because it avoids paying the cheap model on queries sent
directly upward** (arXiv 2605.06350, §6–7 **[P]**). The conclusion — cascade performance
is limited by *structural cost*, not by a shortage of intermediate stages — is therefore
an argument for **routing before paying the cheap stage**, not merely a caution about
rung count.

**This is a disagreement with §4.3, not a caveat on OQ-8. See §4.3.1.**

Transfer caveat, unchanged and still live: his cascades pay a cheap *model* before
escalating; ours pays *retrieval and extraction*. Whether those are the same structural
cost is unestablished. And the first-order conditions in (i) were **read only via
abstract and §6–7, not checked against his statement** — carry that forward rather than
laundering it.

**Design-choice record: abstain and escalate sit in one simultaneous argmax.** Where
abstention belongs in a cascade is contested. Zellinger, Liu & Thomson (2025), *Cost-Saving
LLM Cascades with Early Abstention* (arXiv 2502.09054), ask "whether abstention should
only be allowed at the final model or also at earlier models", arguing correlated error
patterns between small and large models make early abstention cost- and latency-saving.
This spec takes a **third position** — one simultaneous argmax over a flat escalate row
rather than a sequential cascade with per-stage abstention. It is defensible: a single
argmax cannot double-pay, and it needs no model of error correlation. **But it was
asserted rather than argued, and it is recorded here as a choice, with the comparison
owed.** If the ladder ever becomes sequential, this must be revisited first.

**Reliability is estimated, never asserted, and the mechanism has precedent.** No `p_r`
may be a written constant. Learning an expert's reliability *from the outcomes of the
calls actually made* is **online learning-to-defer under bandit feedback** — arXiv
2605.12340 (2026) requires "feedback only from the experts that are actually queried",
handles a dynamically varying expert pool and drifting reliability, and proves sublinear
regret; Expert-Agnostic L2D (arXiv 2502.10533) models expert accuracy with a **Bayesian
Beta-Binomial** and priors, which is what "the posterior earns `p_r` from outcomes" means
once written down. **[S] Precedent exists; withdraw any novelty claim.** What remains
distinctive is doing it *inside the same inference as the answer posterior* rather than in
a separate estimator — a placement, not an idea.
Contrast `_ORACLE_P = 0.9` (`src/life_agent/core/lookup.py:200`), a fixed prior for the
owner-as-oracle `ask` row — acceptable there, wrong for a machine oracle whose accuracy
is measurable. Preferred source: a guard on the writable name, so the posterior earns
`p_r` from outcomes (`proplang/membrane-wire.md:363-383`, growth measured at `:386`).
Fallback: held-out measurement carrying its own uncertainty.

**Update discipline:** an escalation whose outcome is never graded must not update
`p_r`. Silence is not evidence of success. `p_r` is conditioned on lane at minimum.

**Unavailability is feasibility, not utility.** An unreachable rung is removed from the
menu for that tick, never scored low — a low score invites the argmax to pick it when
everything else is worse. A failed attempt still pays its spend and latency, or retry is
free.

### 4.2 Pointer-to-source — the floor

*"I cannot answer this, but the answer is in these documents."* Ranked sources, no
synthesised answer. It is the floor because it is the only action available in **every**
cell: no oracle needed, nothing disclosed, works offline, and available in L3 where no
quality scalar exists.

It is gradeable, which is why it can be in the utility at all: it converts generation
into retrieval, and `x_ptr` is containment of the gold answer in the pointed set,
discounted by set size on the same self-penalising construction as §5.1. Its error mode
is `u_vague`, not `u_wrong` — a pointer that misses wasted time; it did not assert a
falsehood.

**Gated on OQ-4.** If the owner would not use pointers, the floor is imaginary and §7.4
becomes a genuine hole.

### 4.3 `/route` moves downstream of the posterior

Today `decide_via_loop` (`src/life_agent/core/executor.py:186`) posts to `/route`
(`:203`); a declined route goes to `/narrative` (`:205`) — rerank plus LLM synthesis,
returned verbatim. So *should our engine answer this, or should an LLM?* is decided
**before any posterior exists**, by the component with no evidence. That is the
escalation decision, made earlier and worse.

Under this spec `/route` is demoted to **lane classification** (§6) — a property of the
question, which legitimately precedes evidence — and the answer-vs-escalate choice moves
into the argmax.

Three consequences to register before building:

1. **The narrative lane becomes a rung**, not an unpriced bypass.
2. **Cost attribution changes — and this is a restatement of Bouchard's structural-cost
   result, not an observation of ours.** `/route`'s cost is not wire-carried today
   (`executor.py:229` notes this); evidence-gathering spend preceding the decision must
   be attributed or escalation looks cheaper than it is. Bouchard (2026) shows the
   stronger form: that pre-decision spend is the *binding constraint* on cascade
   performance, not a bookkeeping detail (§4.1(ii)). **Treat unattributed pre-decision
   cost as a correctness defect in the reading, not a rounding error.**
3. **Archived readings are not comparable across the change.** Every recorded run routed
   upstream. This needs a fresh baseline and a pre-registration, not a splice.

### 4.3.1 Does L3 skip retrieval? — an open design question, deliberately unanswered

**Bouchard's empirical result puts a question to this spec that the spec does not
answer.** §4.3 moves escalation *downstream* of the posterior, which means it comes
**after** retrieval and extraction have been paid for. But §6's lane classifier is
**question-only by construction** — it is forbidden from reading any posterior or
retrieval result — which makes it *already a pre-generation router in Bouchard's sense*.
So the machinery to route before paying is present; the spec simply does not use it.

Two answers, both coherent, and **the absence of one is the defect**:

| | If **yes**, L3 skips retrieval | If **no**, L3 pays retrieval then escalates |
|---|---|---|
| gains | avoids the structural cost Bouchard identifies as binding | keeps one uniform path; no second code route |
| **costs** | **`pointer` becomes unavailable on that path** — it is a *retrieval* action (§4.2), so skipping retrieval removes the floor action that closes the L3+SEALED cell (§7.4) | pays a cost his evidence says is the binding constraint |
| also | needs an exception written into §4.3 | needs a stated reason, plus the transfer caveat that retrieval ≠ a cheap model |

**The coupling in the "yes" column is the part worth noticing**: answering *yes* reopens
a dead cell this spec closed. `pointer` is what makes L3+SEALED non-empty, and it needs
retrieval to have run. So "skip retrieval on L3" is not a free optimisation — it trades
the floor action for the structural saving, on exactly the questions where escalation may
also be barred.

**Not answered here.** It needs either the transfer question settled (does retrieval cost
behave like his cheap-model cost?) or an owner ruling on whether the L3+SEALED cell may
be allowed to empty. Recorded as the open item it is.

### 4.4 Gather and ask are continuation actions

Structurally different: they yield evidence, not an answer.

```
EU(gather_p) = E[ max_{a'} EU(a') | evidence from p ] − λt·ct(p) − λ$·c$(p)
EU(ask)      = E[ max_{a'} EU(a') | owner's reply ]   − lambda_int
```

One-step lookahead, as today's `net_voi`. **This is standard value of information and
carries no novelty** — Lindley (1956), Howard (1966); Horvitz's cost-of-interruption line
prices exactly `lambda_int` and computes whether the expected-cost reduction exceeds the
cost of asking; Rao & Daumé (2018) rank clarification questions by expected VOI; arXiv
2605.07937 (2026) surveys clarification timing for long-horizon agents under the same
framing. `net_voi` should cite these and claim nothing. **[S]** **The cost of the lookahead now grows with the
action space** — |A| × P evaluations per decision. At |A| ≈ 44 and P = 4 this is fine;
it is noted because it was ~6 × 4 before and the growth is real (§8, R3).

---

## 5. The utility over that space

### 5.1 Quality `x`, per lane and shape

| lane | `x` | justification |
|---|---|---|
| **L1** point-fact | 1 if exact match else 0 | **binary is correct here** — no partial credit for a nearly-right passport number |
| **L2** metric | graded, per shape below | the answer carries a metric with a canonical ordering |
| **L3** open-ended | **undefined — not scored** | fit-to-need varies irreducibly; any scalar is invented, and an invented scalar in an argmax is what an optimiser exploits |

L2 shapes:

| action | `x` |
|---|---|
| `point_j` | 1 if `ω = c_j` else 0 |
| `set_m` | `1/m` if `gold ∈ top-m` else 0 (or F1 against a gold set) |
| `interval_ab` | Winkler `max(0, 1 − W/(2·|gold|))` — exists, `interval_options`, `decide.py:192` |
| `scoped_j` | truth of the record-claim, not the current value |
| `pointer` | containment in the pointed set, size-discounted |
| `escalate_r` | **flat at `p_r` across all ω** — the oracle is not reading our candidate list |
| `correct_premise` | **flat at `p_prem` across all ω** — a claim about the question, not about which candidate is true (§3.5) |

**The flatness of the escalate row is the whole reason escalation rescues a `dispersed`
row** (`WITHHELD_DISPERSED`, `src/life_agent/core/gate.py:99`): it is the only action
whose value does not depend on the posterior that failed to concentrate.

**Fit-to-need is never scored.** Length, verbosity, framing, whether to volunteer a
breakdown — these depend on the question, the moment and the person, none of which are
properties of the answer. They enter only as the *choice among shape actions*, which the
argmax makes, and never as a term in `x`.

### 5.2 `u_err` is a property of the claim, not a constant

| action | error cost | why |
|---|---|---|
| `point_j` | `u_wrong` | unqualified current-value claim — the anchor, at whichever Ū OQ-0 rules |
| `scoped_j` | `u_wrong_scoped` | a citable misread of a record, self-correcting |
| `set_m` / `interval` **containing** truth | `u_vague` | imprecise, not false |
| `set_m` / `interval` **excluding** truth | `u_wrong` | it is a false claim |
| `pointer` | `u_vague` | wasted the reader's time |
| `escalate_r` | `u_wrong` | we deliver the oracle's answer as ours — but see §8, R5 |
| `correct_premise` | `u_wrong` | telling the owner their question is ill-posed when it is not is a confident false claim about *them*, and appropriately expensive |
| `gather` / `ask` / `abstain` | n/a | no assertion |

`u_vague` is a new elicited latent (OQ-3). It is what makes partial credit viable, and
it must be elicited rather than defaulted — **and that argument has been made before, with
a uniqueness result attached.**

Zaffalon, Corani & Mauá (2012, *IJAR* 53:1282–1301) call `x = 1/m` **discounted accuracy**
and show, in a betting framework, that it is the **only** score satisfying a set of basic
properties for comparing determinate against indeterminate predictions. They then give its
defect: **a classifier that answers at random and one that always returns the full set have
the same expected discounted accuracy** — the "doctor random versus doctor vacuous"
argument — so a risk-averse decision-maker should prefer the vacuous one, and no
size-discount alone can express that. Their fix is **utility-discounted accuracy** (`u65`,
`u80`). **[S]**

**That is `u_vague`, ten years early, and §7.3's k-independent hedge is exactly their
doctor-vacuous failure.** Two consequences: cite them rather than claiming the
construction, and treat `u_vague` as **not optional** — discounted accuracy without it
cannot distinguish random from vacuous, which is the failure mode §5 exists to close.

#### 5.2.1 The commit bar is Chow's rule — an identity, not an analogy

The assert-vs-abstain threshold implied by §2 is `p* = |u_wrong| / (1 + |u_wrong|)`
(`gate.py:317`). **That is Chow's (1970) reject rule, exactly.** Chow gives the reject
threshold as `t = (Cr − Cc)/(Ce − Cc)`, rejecting when the maximum posterior falls below
`1 − t`. Substituting our gauge — `Cc = −u_correct = −1`, `Cr = −u_abstain = 0`,
`Ce = |u_wrong|`:

```
t     = (0 − (−1)) / (|u_w| − (−1)) = 1 / (1 + |u_w|)
1 − t = |u_w| / (1 + |u_w|)                            ← our bar, identically
```

**So §5's derivation is a restatement of a 1970 result, and 0.8369 and 0.9000 are Chow
thresholds.** Two consequences worth carrying:

- **No novelty is claimed for the bar**, and none should be. What is ours (if anything —
  `LITERATURE-AND-HARNESSES.md` §1.6) is the *shape-dependent* `u_err` of §5.2, which
  Chow does not have: reject-option theory carries a single error cost `Ce`.
- Chow's companion result — the monotone error–reject tradeoff — **is** the risk-coverage
  curve, which is why the AURC re-cut is not a new instrument but the standard reading of
  this same rule. See `LITERATURE-AND-HARNESSES.md` §3.

### 5.3 Costs — three attributes, scalarised host-side

| attribute | measured | rate | shape |
|---|---|---|---|
| money | **metered** spend, not imputed token pricing | `lambda_usd` | linear |
| time | `latency_s`, already recorded (`src/life_agent/core/decisions.py:179`) and priced **nowhere** | `lambda_time` (new) | linear to a patience cliff (OQ-2) |
| privacy | count of distinct SENSITIVE items newly crossing the boundary this session | `lambda_priv` (new) | linear **within class** |

Scalarisation is host-side because the wire carries one `Rational` and `Expr` has no
product sort. That is the correct division, not a workaround: **the host owns
preferences, the language owns inference** (`proplang/appendage-spec.md`).

### 5.4 Privacy is a constraint, not a price

Disclosure classes per corpus item: `OPEN` (free), `SENSITIVE` (costs `lambda_priv` per
newly disclosed item), `SEALED` (**hard constraint**).

A SEALED item makes every disclosing action **infeasible at any price**. Not a large
negative number — large negative numbers get traded away when the answer is valuable
enough, and for medical, financial or third-party-confidential material that trade must
not be available to an argmax.

**Enforced host-side by withholding the menu name for that tick.** Verified as the
supported mechanism: `policyPick` returns `Nothing` only for an empty candidate list
(`Membrane.hs:319-320`) — there are no feasibility masks and no per-action refusal
semantics — while publication toggles availability, not membership
(`membrane-wire.md:66-70`). The constraint therefore *must* live in the host, which is
also where it belongs conceptually.

### 5.5 Well-definedness

Three properties the space-plus-utility must have. Checked, with one qualification.

**No dead cells.** Every (lane × feasibility) combination has at least one action with a
defined value. The binding case is L3 + SEALED, where scoring is undefined and cloud
escalation is barred: `pointer`, `E_local`, `ask` and `abstain` all remain feasible.
*Qualification: this holds only if OQ-4 confirms pointers are useful and OQ-6 admits a
local rung; otherwise the cell reduces to `ask` and `abstain` — see §7.4.*

**A10 adds coverage rather than consuming it.** `correct_premise` is feasible in every
lane (a false premise is not a property of the answer shape) and discloses nothing — it
is a claim derived locally about the question, so it survives SEALED and survives an
oracle outage. It therefore **closes the false-premise cell without opening a new one**;
that cell previously had no action at all (§3.5).

**No action that can never win.** Each has a non-empty winning region:

| action | wins when |
|---|---|
| `point_j` | credence concentrates above the bar |
| `set_m` | mass spread over a small prefix, `p(NONE)` low |
| `interval` | near-agreeing numerics, `p(NONE)` low |
| `scoped_j` | record certain, currency uncertain |
| `pointer` | retrieval good, extraction poor, escalation barred or unaffordable |
| `escalate_r` | posterior dispersed, rung affordable and feasible |
| `gather_p` | VoI exceeds probe cost |
| `ask` | owner resolves cheaply, interruption acceptable |
| `correct_premise` | the premise detector fires with high `p_prem` **and** `p(NONE)` is high — the truth is not among our candidates *because there is no truth to find* |
| `abstain` | everything else is negative |

**No action that always wins.** `abstain` is pinned at 0 and any confident assert beats
it. `escalate_r` is flat and is beaten by a concentrated posterior. No row dominates
across all posteriors.

### 5.6 Invariants

Four constraints on any implementation of §3 + §5. Each has bitten before.

**One valuation atom.** Every row derives from `u_assert`
(`src/life_agent/core/decide.py:64`). No action invents its own arithmetic — the
existing r30b · C3 discipline, and the reason `interval_options` was built as extra rows
rather than a second decision rule.

**Both decide surfaces, or neither.** `action_utilities`
(`src/life_agent/core/lookup.py:940`) is **not** the deployed surface; the daemon's
action set is built in the credence repo (`answer_brain.jl`, `decision_fpa`), and
`report_scoped_j` already has no daemon counterpart. **An action added only to
`action_utilities` would measure nothing and change nothing for the owner.** Any
estimate assuming otherwise is wrong by roughly a factor of two.

**`escalate` is neither an assertion nor a withholding.** It delivers an answer, so it
does not belong in `WITHHOLD_ACTIONS` (`src/life_agent/core/gate.py:88`) — but adding it
to `ASSERT_ACTIONS` (`:87`) silently re-values every archived row, because that frozenset
is what `realised_utility` partitions on. **A third partition member is required, with an
explicit statement of what it does to archived readings.** I have not verified that the
gate's fold survives the addition; that check is a precondition, not a detail.

**Withheld reasons stay a closed vocabulary.** `WITHHELD_MISS` / `WITHHELD_DISPERSED` /
`WITHHELD_UNAVAILABLE` (`gate.py:98-100`) annotate abstentions. Escalation is not one of
them, and `pointer` is not one of them either — both deliver something.

---

## 6. The lane classifier (folded in — it conditions everything above)

The grading scheme in §5.1 is conditioned on the lane, so the classifier is load-bearing
and is currently a regex.

**The failure mode, stated first: misclassifying L3 as L1 means binary-grading an
ungradeable answer** — near-certain "wrong", then abstain. This is current behaviour,
because `DEFAULT_SHAPE = ANCHOR_SHAPE = EXACT`
(`src/life_agent/core/answer_shape.py:35-36`) makes `exact` a grab-bag, and the module's
own header records **0.74 agreement against a blind manual reference, disagreement
one-directional toward `exact`** (`answer_shape.py:6-7`). The known error pushes *into*
the worst class.

**Damage is asymmetric**, so the classifier must be:

| confusion | consequence | severity |
|---|---|---|
| L3 → L1 | ungradeable answer binary-graded → abstain | **worst, and invisible** |
| L2 → L1 | partial credit discarded | high |
| L1/L2 → L3 | escalates what we could answer for $0.0036 | moderate — costs money, and money is visible |

**Required inversion: unmatched → L3, not L1.** L1 must be *positively identified*,
never inherited as a default. Errors toward L3 cost money and show up in the spend;
errors toward L1 cost correctness and hide as appropriate-looking caution.

**Procedure.** (1) L2 iff positive evidence of a metric answer — `SPACE_RULES`
(`answer_shape.py:60`) detect quantity/threshold/set today and are a starting point.
(2) L1 iff positive evidence of a single unambiguous stored value. (3) Otherwise L3.
Ties: L1∧L2 → L2; anything ∧ L3 → L3 unless the L1/L2 evidence is positive and
unambiguous.

**Features permitted:** question text, declarable answer space, corpus-independent shape
priors. **Forbidden:** anything posterior-dependent (the lane selects the action space;
it must not be selected by the outcome), the gold answer, the eventual answer's form.

**Bars, pre-registered before the run:**

1. overall agreement ≥ **0.90**, and
2. **L3→L1 confusion ≤ 0.02 of all questions** — the binding bar. A classifier at 0.92
   overall with 8% L3→L1 is worse for this architecture than 0.88 overall with 1%.

**Measurement protocol.** Stratified sample of *real owner questions* — not the
104-question gate set, which r29 records is a census of the instrument rather than of
the owner's questions — including questions currently routed to narrative, since those
are the suspected L3 population. Blind manual labelling, two passes or two labellers, so
**human self-agreement is measured first as the ceiling**; if the owner cannot reproduce
their own labels at ≥0.90, the partition itself is in doubt and that is worth knowing
early. Report the **full 3×3 confusion matrix**, not a headline — a headline is what let
0.74-with-one-directional-error persist. Freeze reference-set hash, labeller, date and
classifier version.

`answer_shape.py` is not replaced: its four shapes remain the **grading** vocabulary
*within* L2. Lane decides whether and how to score; shape decides which metric.

---

## 7. The closure argument

The foundational claim under test: **Bayesian decision theory suffices, given the right
action space and utility.** Each known-bad case, worked.

### 7.1 The 41 abstentions

Median leader credence **0.3688**, `p(NONE) ≈ 0.26–0.41`. Under the new space:
`point_j` loses (0.37 is far below either bar). `set_m` loses — at m=3 with
`P(gold ∈ top-3) ≈ 0.6` and `u_vague = −0.2`, EU ≈ `0.6·0.20 + 0.4·(−5.131) = −1.93`.
`interval` likewise. **`escalate` wins, and only because it is flat** — its value is
untouched by the dispersion.

**[OQ-0]** Under the reaction-conditioned estimate, `EU(escalate) = +0.1365 > 0` and these rows route.
**Under the elicitation-only estimate it is −0.0933 and they do not** — they still abstain, and closing
them needs OQ-1. This is the one case where the ruling changes the outcome rather than
the magnitude.

### 7.2 The intervals that lost by 4.5–7 units

Partly closed, and correctly so. The gap was driven by the NONE atom paying the full
`u_wrong`; §5.2 charges `u_vague` when the interval *contains* the truth. But when
`p(NONE) = 0.3`, an interval with `x = 0.8` still scores
`0.7·0.76 + 0.3·(−5.131) = −1.01` and still loses.

That is the right behaviour: intervals become choosable **on their proper population**
— low `p(NONE)`, near-agreeing numerics, which is exactly the five rows r31 priced them
on — and correctly keep losing where the truth probably is not in our candidate set at
all, because there the right action is `escalate`. **The 4.5–7 gap is closed where it
should be and left open where it should be.**

### 7.3 The k-independent hedge

Closed. `out["hedge"] = [u_hedged] * k + [u_wrong]` (`lookup.py:968`) is independent of
k today, so hedging 2 and hedging 40 are both worth 0.4. Under §3.3 + §5.1 a set is
identified by its size and `x = 1/m`: a 40-way set scores `0.025`, giving
`0.025 + 0.975·u_vague < 0`. Vagueness is priced **inside** `x`, never as an external
penalty — the r30b · C1 discipline, of which the Winkler width term is the working
precedent.

### 7.4 SEALED + open-ended

L3 (unscored) ∧ SEALED (cloud rungs barred). Feasible: `pointer`, `E_local`, `ask`,
`abstain`. **The cell has actions** — conditional on OQ-4 (pointers useful) and OQ-6
(local rung admitted). If both are declined, the cell reduces to `ask` and `abstain`,
and *the most sensitive material gets the worst service*. That would be a real hole and
should be recorded as one rather than papered over.

### 7.5 Escalation at both gauges — and the local-rung cliff

A free oracle must still clear silence. Break-even accuracy for a zero-cost rung:

```
p·1 + (1−p)·u_wrong = 0   ⇒   p* = |u_wrong| / (1 + |u_wrong|)
  reaction-conditioned (−5.131):  p* = 0.837
  elicitation-only  (−8.9993): p* = 0.900
```

**A free local model below ~84% accuracy is worse than silence at any price.** Cost is
not what makes the local rung viable — accuracy is. This makes OQ-6 concrete: the
question is not "should we add a local model" but "do we have one above 84%?", and if
not, the SEALED escape hatch is `pointer` alone.

---

### 7.6 The false-premise case, and what A10 does to the rest of §7

Re-examined after adding `correct_premise` (§3.5). Three findings, one of them a genuine
unknown rather than a confirmation.

**It closes a cell that had nothing in it.** A question with a false premise previously
had no action: not answerable, its withholding is not `dispersed`, and escalating it buys
a confabulated answer at full price. With A10 the argmax has a positive-EU option when
`p_prem` is high, and — because A10 is flat over ω and locally derived — it is the one
new action available under **both** SEALED and oracle outage. §7.4's dead-cell
qualification is unchanged but its margin improves.

**It breaks none of the existing arguments, checked one by one.** §3.3's prefix-set
dominance concerns sets of *answer candidates*; A10 is not a set action, so the
2^K → K collapse is untouched. §5.5's "no action always wins" holds: A10 is flat, so any
concentrated posterior on a real answer beats it, and it is feasibility-gated so it is
absent from most menus. §7.2 and §7.3 do not reference it. Cardinality goes to ≤ 44.

**The genuine unknown: how many of the 41 are false-premise rows? Nobody has looked.**
The 39 `dispersed` rows have candidates, which makes a firing premise detector unusual
there but not impossible — a question can presuppose something false and still retrieve
plausible-looking candidates, which is precisely the case that produces a confident wrong
answer. **The 41 were never classified for premise validity**, so §7.1's claim that they
route to escalation is, strictly, a claim about a population that has not been checked for
this. Add premise-validity to the lane census (§10 step 2) — it costs one extra label per
question and it is the only way to find out whether A10 has any live population at all.

## 8. The residue — where this still does not close

The most valuable section. Six items.

**R1 — high-`p(NONE)` L2 questions with escalation barred.** Point, set and interval all
lose to the NONE mass; escalation is unavailable or SEALED-barred; if retrieval is also
poor, `pointer`'s `x` is low too. Result: `abstain`. **Genuinely unserved**, and no
utility refinement fixes it — the information is not there and cannot be fetched.

**R2 — the local-rung accuracy cliff (§7.5).** Privacy-constrained questions are served
by a *good* local model or not at all. Being free buys nothing.

**R3 — lookahead cost grows with the space.** `gather`/`ask` VoI is |A| × P evaluations,
up from roughly 6 × 4. Tractable at 43, but it grows linearly in K and the current
`net_voi` was written against a much smaller space.

**R4 — L3 grading is still needed for measurement, and now feeds back.** The decision
layer does not score L3, but evaluation must, to know whether an escalation was worth
its price. That grade updates `p_r` (§4.1). So **judge noise propagates into routing
policy** — a coupling that does not exist today and that the "decide without a scalar,
measure with a noisy one" argument does not fully cover.

**R5 — `u_err` for escalation is asserted, not derived.** §5.2 charges `u_wrong` when
the oracle is wrong, on the grounds that we deliver its answer as ours. But an
*attributed* answer ("the model says X, unverified") may harm less — closer to
`u_vague`. This single choice is what makes escalation lose under the elicitation-only estimate,
and it has not been elicited. **It should become an open question.**

**R7 — `p_prem` is a second unmeasured reliability, and its errors are expensive.**
`correct_premise` carries `u_wrong` (§5.2), because telling the owner their question is
ill-posed when it is not is a confident false claim about them. So a premise detector
firing wrongly is charged at the anchor rate — the harshest in the model — while
`p_prem` has **no data behind it at all**, less even than `p_r`, which at least has the
oracle's measured 95/101. Until the census in §7.6 establishes a population, A10 should
be specified but **not enabled**: an action with a punitive error cost and an unestimated
reliability is a liability, not an affordance.

**R6 — fit-to-need has no feedback channel.** The argmax picks a shape; if the owner
wanted a different form, nothing records it. Deliberately unscored (§5.1), but that
means the system cannot learn form preferences at all — a permanent limitation of the
scope reduction, accepted knowingly.

---

## 9. What provenance must survive an escalation (tannen)

**Repository note: tannen is private and outside any public-master audit.** Nothing in
this section has been independently re-verified. Expanded in
`../../tannen/SCOPE-under-routing.md`; citations checked against branch `m3`.

Escalation breaks the current guarantee. Today `citation.audit`
(`src/life_agent/core/citation.py:95`) verifies each value-bearing cited fact appears in
its source, giving *nothing is asserted that is not in the corpus*. An escalated answer
is produced by a model that saw a subset of the corpus and then reasoned — not
corpus-contained, so unverifiable that way, and with no artifact for the existing
artifact-level lineage (`src/pkm/migrations/0003_transform_substrate.py`) to describe.

Three new obligations:

1. **Disclosure record** — which items crossed, when, to which rung. Required to compute
   `d(q,a)` at all, and required for SEALED to be *auditable*. **A privacy constraint
   you cannot audit is not a constraint.**
2. **Answer origin** — engine or rung, per delivered answer. Without it no reading can
   attribute correctness or spend, and the router cannot be evaluated.
3. **Reliability evidence chain** — which graded outcomes updated which `p_r`. An
   estimate that cannot be traced to its evidence drifts optimistic unseen.

**What tannen must provide: exactly one thing — a content-addressed, append-only,
deletion-correct record of what crossed the boundary and what it produced.** The
disclosure ledger is one row per (question, rung, item-hash, timestamp, class): no
blobs, no floats, no text bodies. **It is the first data in this system that is natively
relational**, and it sits inside the eight operators (`src/tannen/kernel/ops.py`) with no
impedance mismatch. Routing therefore raises the bar above the DuckDB cheap path in
three specific ways — tamper-evidence, deletion-correctness under retraction (the record
of a disclosure must survive expunging the item), and decidable freshness of the
reliability chain via law descriptors (`src/tannen/laws/evidence.py`).

**What tannen must not attempt:** the pipeline substrate — producers take bytes, the
value domain has none; chunking is 1:N and `map_rows` is 1:1; embeddings need floats,
banned; `staleness.stale` (`src/pkm/staleness.py:76`) is a transitive closure with no
fixpoint operator; and LLM transforms need a capture layer that does not exist
(`Layer.CAPTURE = frozenset()` — *"nothing — oracles only (M4)"*,
`src/tannen/kernel/layers.py:29`). Nor should it model the oracle's *reasoning*
provenance: what the model did with disclosed content is not observable, and the honest
record stops at the boundary.

**Scope: ~7 weeks** (ledger schema, answer-origin, reliability chain, ingest seam, SEALED
audit query) against 25–40 for the substrate rewrite that remains not recommended.
Sequenced *after* the escalate affordance. Pipeline row-level lineage stays the cheap
1–2 week path, unchanged and independent. **Gated entirely on OQ-5** — if disclosure is
a cost the owner trades rather than a constraint, tamper-evidence is over-engineering.
And **RT-M3-01 is still open**: a `DeltaNode` names its code by string, so a trace hit
can serve a different computation's answer — an identity hole that should be closed
before this carries an audit artifact.

---

## 10. Sequence

Nothing here is authorised to be built.

0. **Calibration check and AURC re-cut, together — informative, not decisive.** Same
   data, same pass, **different measurements**. **104 rows is too few for E-AURC or AUGRC
   to carry a decision alone** (Traub et al., NeurIPS 2024; and report **AUGRC** beside
   E-AURC or expect the number challenged). It still goes first because it is cheap,
   gauge-independent, and can **falsify** A-CAL — a favourable reading settles nothing, an
   unfavourable one settles a great deal. The reliability diagram + ECE tests **A-CAL** (§2.1), on which the
   whole argmax depends; the risk-coverage curve tests *discrimination*, which is
   necessary but not sufficient. Both are gauge-independent, so both are readable while
   the successor OQ-0′ is unruled. Construction: `LITERATURE-AND-HARNESSES.md` §3. **Dependency: needs
   a gradeable MAP candidate on the 41 withheld rows**; if correctness was recorded only
   on asserted rows this costs a grading pass.
1. ~~**Rule OQ-0**~~ — **already ruled 2026-09-05 (M-34/GD-29)**; INCONCLUSIVE built. §7.1
   is readable under the ruled regime: quote both break-evens beside the reach, and say
   INCONCLUSIVE on a straddle rather than picking a side. The open successor **OQ-0′**
   (derive `u_wrong` from a risk target) is *not* a blocker for anything below.
2. **Lane census + classifier measurement** (§6), **plus a premise-validity label per
   question** (§7.6). Gauge-independent; the cheapest way to discover whether L2 is thin
   enough that most of §5.1 is unnecessary, and the only way to learn whether A10 has a
   live population at all. One extra label per question.
3. **Elicit OQ-3 (`u_vague`), OQ-4 (pointer), OQ-5 (privacy), OQ-6 (local rung), OQ-10
   (attributed-answer error cost).**
4. **Action space** (§3) on both decide surfaces, `abstain`-preserving. **A10 specified
   but not enabled** until step 2 gives `p_prem` a population (§8 R7).
5. **Escalate ladder + pointer floor** (§4.1, §4.2). **Do not expand the rung set before
   settling whether Bouchard's structural-cost result transfers** (§4.1(ii)).
6. **`/route` downstream** (§4.3) — fresh baseline, no splice.
7. Metering, `lambda_time`, privacy classes (§5.3, §5.4).
8. Provenance ledger (§9), if OQ-5 rules for a constraint.

**Why step 0 moved to the front.** It was step 3 in the first draft, on the reasoning
that OQ-0 gated everything. It does not gate calibration: **A-CAL is a precondition on
the argmax itself, so if it fails the gauge question is moot** — no threshold on an
uncalibrated posterior means what it says.
