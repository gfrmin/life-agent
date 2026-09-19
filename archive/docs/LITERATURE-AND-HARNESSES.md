# Literature map, harness survey, and the AURC re-cut

**Status:** analysis. No implementation. Companion to `DR-DECISION-1-action-space-and-utility.md`.
**Superseded in part by the deeper pass of 2026-09-06** (`LITERATURE-REPORT-utility-2026-09-06`,
in uploads). Corrections from it are marked **[R2]** inline. That report's tagging is
carried through: **[P]** primary source read, **[S]** secondary/abstract only, **[NF]** no
precedent found. **Do not upgrade an [S] to a settled fact.**
**Provenance:** `SESSION-RECORD-2026-09-05.md` §3 (R-1…R-7) summarises these findings by
ID; §4 O-3 carries the governance question this document frames but does not rule.

---

## 0. One citation correction

**AbstentionBench is arXiv 2506.09038, not 2605.25850.** The latter ID is a different
paper — *TIAR: Trajectory-Informed Advantage Reweighting for LLM Abstention Learning*.
The correct reference is Kirichenko, Ibrahim, Chaudhuri & Bell, *AbstentionBench:
Reasoning LLMs Fail on Unanswerable Questions*, NeurIPS 2025 Datasets & Benchmarks.

---

## 1. Claim-by-claim map

Verdicts: **PROVEN** (established result, we restate it), **SPECIAL CASE** (an instance
of something general), **REDISCOVERY** (we found it independently; someone proved it
better), **CONTESTED** (live disagreement in the literature), **OURS** (no precedent
found *in this pass* — not a novelty claim).

### 1.1 PROVEN ELSEWHERE — and one is an exact identity

**The commit bar is Chow's rule, exactly.** `gate.py:317` derives
`p* = |u_wrong| / (1 + |u_wrong|)`. Chow (1970) gives the reject threshold as
`t = (Cr − Cc)/(Ce − Cc)` and rejects when the maximum posterior falls below `1 − t`.
Substituting our gauge — `Cc = −u_correct = −1`, `Cr = −u_abstain = 0`,
`Ce = |u_wrong|`:

```
t     = (0 − (−1)) / (|u_w| − (−1)) = 1/(1 + |u_w|)
1 − t = |u_w| / (1 + |u_w|)                          ← our bar, identically
```

So 0.8369 and 0.9000 are Chow thresholds. This is not an analogy; it is the same
formula, and the specs should cite it. Chow also gives the monotone error–reject
tradeoff, which is the risk-coverage curve of §3 below.

**Escalation as an action is learning-to-defer.** Madras, Pitassi & Zemel (2018)
"generalizes rejection learning by considering the effect of other agents in the
decision-making process". That is precisely our move from `abstain` to `escalate_r`, and
their model of the external decision-maker's accuracy is our `p_r`. **Our framing is
their framing.**

### 1.2 REDISCOVERY — the most useful finding in this pass

**Bouchard (2026), *Is Escalation Worth It? A Decision-Theoretic Characterization of LLM
Cascades* (arXiv 2605.06350), covers §4.1 and proves two things DR-DECISION-1 asserts or
misses.**

- **Ladder optimality conditions, which we never derived.** For k-model threshold
  cascades he derives first-order conditions under which a single shadow price λ equates
  decision-boundary expected escalation benefit to λ times decision-boundary expected
  downstream cost — equivalently, equalising marginal quality-per-cost across active
  stage boundaries. For two-model cascades he establishes piecewise concavity of the
  cost-quality frontier with reciprocal shadow prices linking the budget- and
  quality-constrained formulations. **DR-DECISION-1 §4.1 specifies a ladder with no
  optimality theory at all. This is the single largest gap in that section.**
- **[R2 — this was recorded backwards.]** The first pass read the structural-cost result
  as "do not expand the rung set". His headline is stronger and points **the other way**:
  full fixed chains underperform the pairwise envelope, and **a lightweight pre-generation
  router beats the best cascade on four of five datasets, mainly because it avoids paying
  the cheap model on queries sent directly upward** (§6–7, **[P]**). So it is an argument
  for **routing before paying the cheap stage** — a *disagreement* with `DR-DECISION-1`
  §4.3, which puts escalation after retrieval and extraction, not a caveat on OQ-8. The
  spec now carries this as an open design question at §4.3.1 (*does L3 skip retrieval?*),
  with the coupling that answering "yes" removes `pointer` from that path and reopens the
  L3+SEALED cell. **Bouchard's first-order conditions were read only via abstract and
  §6–7 and were not checked against his statement.**

### 1.3 SPECIAL CASE

- **The ladder itself** is an LLM cascade — Chen, Zaharia & Zou (2023), FrugalGPT
  (arXiv 2305.05176), one of whose three strategies is exactly "LLM cascade… learns
  which combinations of LLMs to use for different queries". Not novel; we should stop
  describing it as a design choice and start describing it as a known pattern we adopt.
- **Top-m dominance (§3.3) — [R2] the citation is no longer outstanding.** Mortier,
  Wydmuch, Dembczyński, Hüllermeier & Waegeman (2021, *DMKD* 35:1435–1469; arXiv
  1906.08129) prove that for utilities depending on **set size and containment** the
  Bayes-optimal set is a **prefix of the posterior-sorted classes**, 2^K → K; Del Coz,
  Díez & Bahamonde (2009, JMLR) did the F_β case. **[S]** This also **closes O-6**:
  single-gold F1 is `2/(m+1)` if contained and 0 otherwise — size-only — so prefix
  dominance survives under F1. It fails only for multi-label gold sets, a different
  problem (Nguyen & Hüllermeier 2019).
- **The risk-coverage re-cut (§3)** is the standard selective-prediction form, and is
  Chow's error–reject tradeoff under a modern name.

### 1.4 CONTESTED — a live question our design answers by assumption

**Where abstention sits in a cascade is an open design question, and we picked a side
silently.** Zellinger, Liu & Thomson (2025), *Cost-Saving LLM Cascades with Early
Abstention* (arXiv 2502.09054), pose exactly this: "whether abstention should only be
allowed at the final model or also at earlier models", arguing that correlated error
patterns between small and large models make early abstention cost- and latency-saving.

DR-DECISION-1 puts `abstain` and `escalate_r` in **one simultaneous argmax** rather than
a sequential cascade with per-stage abstention. That is a third position, and it is
defensible — a single argmax over a flat escalate row cannot double-pay, and needs no
correlation model. **But the spec asserts it rather than defending it, and this paper is
the comparison it owes.** Add to §4.1 as an explicit design-choice record.

### 1.5 What is NOT their framing, and where we have no guarantee

**Mozannar & Sontag (2020)** (ICML) give "the only known consistent (surrogate) loss
function for multiclass learning to defer", via a reduction to cost-sensitive learning
resembling cross-entropy under a softmax parameterisation. **This is not what we do, in
either direction:**

- They *train* a deferral policy end-to-end and prove the surrogate is consistent.
- We *compute* EU from an explicit posterior and an explicit utility. No training, no
  surrogate, no consistency theorem needed — but equally, **no learning-theoretic
  guarantee about the policy we get**, because we never fit one.

**[R2] One qualifier the first pass got wrong in our favour.** It claimed "reject-option
theory carries a single error cost". True of Chow; **no longer true of the L2D line** —
Mao et al. (2024, arXiv 2407.13732) give H-consistency bounds for **general cost
functions**, and Verma & Nalisnick (2022, arXiv 2202.03673) give a one-vs-all surrogate
yielding *calibrated* deferral probabilities. So shape-dependent costs are less
distinctive than §1.6 claimed. **[S]** Note also that L2D training assumes precomputed
costs for **every** expert on the training set (the full-information assumption) —
life-agent has neither that data nor a use for it, which is a real reason the training
route is unavailable rather than merely unchosen.

The honest statement: ours is the decision-theoretic object their surrogate is designed
to approximate when the utility is unknown. We have the utility (that is the whole
project), so the surrogate is unnecessary — *provided the posterior is calibrated*,
which is the assumption doing all the work and which nothing in our specs establishes.

### 1.6 OURS — no precedent found in this pass

**[R2 — three of the four now have precedents. Verdicts revised.]** The deeper pass found
homes for most of these. What survives is the *assembly*, and that is a fairer claim than
four separate ones were.

| Item | Revised verdict | Nearest precedent |
|---|---|---|
| String-blind NONE-atom posterior | **precedent for the atom, not the combination** | Open-set recognition's explicit "other" class (OpenMax; survey 1811.08581); SQuAD 2.0's null-answer score as a first-class candidate. *Flat-escalate-over-a-simplex-with-NONE* **[NF]** |
| Shape-dependent `u_err` with `u_vague` | **precedent, strong — withdraw** | Zaffalon–Corani–Mauá 2012 utility-discounted accuracy; Mortier 2021 general utilities over sets; Winkler 1972; Nguyen–Hüllermeier 2019. Possibly ours: charging `u_vague` vs `u_wrong` **by containment, inside one argmax alongside point claims** |
| `p_r` learned via a guard | **precedent — withdraw** | Online L2D under bandit feedback (2605.12340); EA-L2D Beta-Binomial (2502.10533). Ours: the *placement* — same inference as the answer posterior |
| SEALED as feasibility | **precedent in practice, thin in theory** | "Sensitivity constraints override all other routing factors" is the stated production pattern; PRISM (AAAI-26, 2511.22788) is the *priced* soft-gating version; workload-constrained L2D (2403.06906) treats capacity as constraint. A **hard feasibility mask inside a deferral argmax** **[NF]** as a theoretical object |
| Top-m prefix dominance | **theorem exists — withdraw** | Mortier et al. 2021; Del Coz 2009 |
| `gather`/`ask` VOI (§4.4) | **standard — withdraw entirely** | Lindley 1956; Howard 1966; Horvitz cost-of-interruption; Rao & Daumé 2018; 2605.07937 |

**The residual claim, and it is a fair one:** no precedent found for the *assembly* — one
argmax over point / set / interval / pointer / escalate / abstain, with a NONE atom,
shape-dependent error costs, outcome-learned rung reliability, and a feasibility mask.
Claim the assembly, cite the components.

*(Original table retained below for the audit trail.)*

**Stated as "not found", not as "novel".** Each needs a proper search before any claim.

| Claim | § | Why it looks distinct |
|---|---|---|
| **String-blind NONE-atom posterior** | §5.1 | Cascade and deferral work routes on a *confidence scalar*. We route on a posterior with an explicit out-of-set atom, so "the truth is not in my candidate set" is a first-class outcome rather than low confidence. The flatness of the escalate row over that simplex is what makes it rescue dispersed rows. |
| **Shape-dependent `u_err` with `u_vague`** | §5.2 | Reject-option theory has one error cost (`Ce` in Chow). Ours varies by claim shape — an imprecise-but-containing interval is not a false point claim. |
| **`p_r` learned via a guard on the writable name** | §4.1 | Cascades estimate router confidence from held-out data or a trained scorer. Posterior-earning reliability from the act's own outcome stream, inside the same inference, is not a pattern I found. |
| **SEALED as feasibility, not price** | §5.4 | The deferral literature *prices* deferral. A hard constraint that removes the action from the menu — because a large negative would be traded away — is a different object. |

---

## 2. Harness survey

### 2.1 RouterBench — validates the ladder, cannot validate the posterior

arXiv 2403.12031. **Verified:** 405k+ inference outcomes, 64 tasks, 11 LLMs, cost–quality
analytic framework with **AIQ (Average Improvement in Quality)** and convex-hull
comparison; routers are evaluated against archived outcomes without running inference.

**Drop-in for the §2 argmax? Partially, and the limit is structural.**

AIQ is exactly the curve-not-verdict deliverable `DR-UTILITY-1` §4 asks for, and the
archived-outcome method is the same recombination logic. But RouterBench has per-model
per-query quality scores and **no candidate sets, no retrieval, no posterior**. To run our
argmax you must synthesise `P(ω)`.

**Assessment of the synthesis — sound but bounded, not fatal:**

- **Inter-model agreement as a concentration proxy: unsound for our purpose.** Agreement
  measures *model consensus*; our posterior measures *evidence support*. These come apart
  exactly where the thesis lives — a `dispersed` row has retrieved evidence that fails to
  concentrate, which has no analogue in a corpus-free benchmark.
- **Models-as-candidates, NONE = all-wrong: sound, and the one I would use.** Definable,
  honest, and it gives a real out-of-set atom. But NONE mass then measures *the model
  pool*, not the corpus — so it tests the argmax's machinery, not the quantity our NONE
  atom is supposed to represent.

**Verdict:** RouterBench can establish that the ladder and the cost-quality reporting
work, and can produce an AIQ curve comparable to published routers. It **cannot**
establish anything about the NONE atom, the lane split, `u_vague`, or SEALED — it has no
corpus, no retrieval, and no privacy dimension. Bounded but real: it tests §4.1, not §5.1
or §6.

### 2.2 AbstentionBench — a public referent for the L3 boundary, and a hole it exposes

arXiv **2506.09038**, NeurIPS 2025 D&B. **Verified:** 20 datasets (3 new underspecified
reasoning challenges) over **6 abstention scenarios** — Answer Unknown, False Premise,
Stale, Subjective, Underspecified Context, Underspecified Intent — with human-validated
LLM judges (Llama 3.1 8B Instruct). **Headline finding:** abstention remains unsolved for
frontier models, **scale has almost no effect**, and **reasoning fine-tuning *hurts*
abstention**, producing overconfident models that rarely abstain.

**[R2 — resolved against the primary source (v1 read in full).]** The judge agrees with
human annotation at **88%** (v1 §3.4), **not 82.3%**. The dataset count is **20** (17 + 3
new). **"31 subsets" does not appear in v1** and should not be quoted. **[P]**

**Drop-in? No.** It evaluates *a model's* abstention, not *a router's* action choice.
Using it means collapsing our action space onto {answer, abstain}, which discards
`hedge`, `interval`, `pointer` and every rung — i.e. it tests the one binary distinction
our spec spends its length arguing against.

**What it would establish:** a public reference for the L3 boundary with labels we did
not make — the one thing our own gate set structurally cannot provide (§4). And its judge
is a validated comparator for our modal-of-3 judge, whose agreement is unpublished.

**What it would not:** anything about cost, routing, or the ladder. There is no cost
dimension.

**The hole it exposes, which is the more valuable output.** Its six scenarios do not map
cleanly onto L1/L2/L3. *Answer Unknown* and *Stale* are cases where **NONE is genuinely
the truth** — our posterior represents this, but our lane taxonomy does not distinguish
it. *Subjective* and *Underspecified Intent* sit in L3. But **False Premise has no lane
and no action at all**: a question whose premise is false is not answerable, not
abstainable-for-dispersion, and not usefully escalated — the right act is to *correct the
premise*, which is nowhere in §3.2's nine families. **That is a genuine gap in
DR-DECISION-1, found by reading someone else's taxonomy, and it should be recorded as
such.**

Its scale/reasoning finding also bears directly on the ladder: if abstention quality does
not improve with model strength, `p_r` for upper rungs may not dominate lower ones on the
questions where abstention is the right act — which weakens the monotone-ladder
assumption in §4.1.

### 2.2b [R2] ATM-Bench — the closest public corpus to a personal store

arXiv 2603.01990 (Mar 2026, on HuggingFace). ~4 years of one person's data: **6,741
emails, 3,759 images, 533 videos; 1,038 human-written QA pairs with gold evidence**; a
`-Hard` subset averaging 6.3 evidence items per question. **[S]**

**[CORRECTION 2026-09-06 — the abstention leg was overstated here.]** The first pass wrote
"explicit abstention (ABS) items" from an **[S]** summary. `session-brief-zesty-fountain.md`
read the primary sources and found **unanswerable items are 0.3% — about 3 questions** —
and dropped the abstention leg on that basis. Two further corrections worth carrying: the
**data** licence is **CC-BY-NC 4.0** (code is MIT), and QA records carry **no type field**,
so any number/list/open-ended split must be derived by our own classifier. **Do not plan an
abstention read on ATM-Bench.**

**Why it matters more than the other two:** it is the only public corpus shaped like the
thing life-agent actually is. It can test `citation.audit` against gold evidence,
retrieval reach on a personal store, and abstention behaviour on a personal distribution —
none of which RouterBench or AbstentionBench can. The email-only subset is text-only,
which matches the current pipeline.

**What it cannot test:** cost. No price axis, no spend, so nothing about the ladder,
`lambda_usd`, or Δ.

### 2.2c [R2] `p_prem` has a data source now — this unblocks A10

**AbstentionBench's False Premise subsets — FalseQA, (QA)², KUQ, CoCoNot — are labelled
false-premise questions.** `DR-DECISION-1` §3.5 specifies `correct_premise` (A10) but §8
R7 keeps it **disabled** because `p_prem` has no data behind it at all while the action
carries `u_wrong`. **These subsets are that data.** They give a public, externally
labelled population on which a premise detector's reliability can be estimated before the
action is ever enabled on the owner's corpus — which is the right order, since the
alternative was estimating it from a population nobody had checked.

**Caveat:** they are someone else's distribution, so this establishes `p_prem` for
*public* false-premise questions, not for the owner's. It is a prior, not a posterior. The
§10 step 2 premise-validity label on real owner questions is still needed to know whether
A10 has a live population *here*.

### 2.2d [R2] The structural finding: a benchmark protocol needs two harnesses

**No public corpus has both a price axis and a NONE atom.** RouterBench has cost and no
NONE; ATM-Bench has NONE and gold evidence and no cost. And **none has privacy classes or
metered spend on a personal store**, so SEALED and `lambda_priv` stay internal — they
cannot be externally validated at all.

Consequence for O-3 (the governance question): an external-benchmark protocol is not one
decision but **two**, on different corpora, testing different halves of the spec. That
makes option **C** (admissible for instrument-validation only) more tractable than it
looked, because the split is already forced by the data.

### 2.3 Others located this pass

| Work | Relevance |
|---|---|
| UCCI: *Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing* (arXiv 2605.18796) | Calibration + cost-optimal routing — closest to our "the posterior must be calibrated" assumption (§1.5) |
| *Efficiently Deploying LLMs with Controlled Risk* (arXiv 2410.02173) | Risk-controlled deployment; abstention under guarantees |
| *Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey* (arXiv 2603.04445) | Survey — the right entry point for a proper search |
| *Agreement-Based Cascading* (arXiv 2407.02348) | The inter-model-agreement proxy §2.1 rejects, developed properly |
| *Cascaded Language Models for Cost-Effective Human–AI Decision-Making* (arXiv 2506.11887) | Human as a cascade stage — our `ask` rung |

**A proper search should start from the 2603.04445 survey.** This pass was breadth-first
and certainly incomplete.

---

## 3. The internal re-cut: 104 rows as a risk-coverage curve

**No new data. No inference. It re-expresses run 18 in the standard selective-prediction
form, and it is gauge-independent — which makes it the one substantive reading available
while the estimate's basis (OQ-0′) is unsettled.**

### 3.1 Why it is worth doing

Today the 104 rows are reported as one contingency at one threshold. A risk-coverage
curve reports the *whole* threshold sweep, so it answers a question the contingency
cannot: **is the leader credence a good ranking, independent of where the bar sits?**

That is orthogonal to OQ-0. If the ranking is good, the −5.131/−8.9993 dispute is about
choosing an operating point on a good curve. If the ranking is poor, **no bar helps and
the dispute is moot** — which would be the most decision-relevant thing anyone has
learned about the gauge question.

### 3.2 Construction

Inputs, all already recorded: per-question leader credence `p1` for **all 104 rows
including the 41 withheld** (the r32 reading quotes a median leader of 0.3688 over the
abstained population, so these are logged), and per-question correctness of the answer
that *would* have been asserted — the weight-MAP candidate — for every row, including
rows where nothing was asserted. **That second input is the one to check exists**; if
correctness was only graded on asserted rows, the withheld rows need grading before the
curve can be drawn, and that is a real cost.

Then:

```
sort rows by p1 descending
for τ over the sorted p1 values:
    answered(τ) = { rows with p1 ≥ τ }
    coverage(τ) = |answered(τ)| / 104
    risk(τ)     = |{ r ∈ answered(τ) : MAP(r) wrong }| / |answered(τ)|
AURC   = mean over the sorted prefix of risk at each coverage level
E-AURC = AURC − AURC_optimal          # optimal = all correct ranked above all incorrect
```

Report **E-AURC**, not raw AURC: excess-AURC normalises out the base error rate and is
the standard comparable form.

**[R2] Report AUGRC alongside it, and expect the number to be challenged otherwise.**
Traub et al. (NeurIPS 2024, *Overcoming Common Flaws in the Evaluation of Selective
Classification Systems*) argue **selective risk is unsuitable for aggregation across
thresholds** and propose the **AUGRC** (area under the generalised risk-coverage curve) as
the replacement. Reporting E-AURC alone invites exactly that objection. **[S]**

**[R2] And 104 rows is too few for either number to carry a decision alone.** This is a
real demotion of §10 step 0, which the sequencing now reflects: the calibration and
risk-coverage pass is **informative, not decisive**. It still goes first — it is cheap,
gauge-independent, and can *falsify* A-CAL — but a favourable reading does not settle
anything on its own. Related: Herbei & Wegkamp's plug-in consistency is **asymptotic**,
and 104 rows is not asymptotic.

**One warning if the scoring layer is ever extended.** Impossibility results (Seidenfeld
et al. 2012; Mayo-Wilson & Wheeler 2015; Schoenfield 2017, summarised in arXiv 2503.16395)
show **no continuous scoring rule over imprecise forecasts can be simultaneously strictly
proper, calibrated and non-dominated**. This does **not** bite the decision layer, which
scores *actions*. It bites only if AURC/ECE is extended to score set and interval outputs
*as forecasts*. Keep those two uses separate. **[S]**

### 3.3 What lands on the curve

Two operating points, both already known:

| policy | coverage | risk |
|---|---|---|
| typed at today's bar | 63/104 = **0.606** | 2/63 = **0.032** |
| π\* | 101/104 = **0.971** | 6/101 = **0.059** |

The two candidate bars (0.8369, 0.9000) are two more points on the *same* typed curve.
**Plotting them is the clearest possible statement of what OQ-0 is choosing between** —
and if they sit close together on a flat region, the ruling matters less than the
argument around it suggests.

### 3.4 What it does and does not establish

**Does:** whether typed's credence ranks well; where the two candidate bars sit; a
number (E-AURC) directly comparable to the selective-prediction literature; a public-form
restatement that needs no acceptance of `u_wrong`.

**Does not:** anything about cost — risk-coverage has no price axis, so it cannot speak
to escalation, the ladder, or Δ. Pair it with AIQ (§2.1) for that, or extend to a
cost-coverage curve, which is a different construction and should not be conflated.

---

## 4. Governance: are external benchmarks admissible evidence? (framing only)

**Not ruled here. This is the owner's call; what follows is the option set and the
consequences.**

### 4.1 The distance argument, and the argument that cuts the other way

r29 records the 104-question set as **a census of the instrument, not of the owner's
questions**. A public benchmark is one step further removed — a census of *someone
else's* instrument, on someone else's distribution:

```
owner's real questions  →  the 104-row gate set  →  a public benchmark
        target                  known proxy              proxy for a proxy
```

But distance is not the only axis. A public benchmark has **labels the owner did not
make**, which is the one property the gate set can never have — and the circularity that
OQ-0 is currently stuck on is precisely a problem of self-supplied labels. **The two
axes trade against each other, and the ruling is about which matters for which claim
type**, not about admitting or excluding wholesale.

### 4.2 Options

| | Rule | Consequence |
|---|---|---|
| **A** | **Inadmissible in a sitting.** Sanity check only, outside the ruling process. | Strongest anti-circularity, cleanest constitution. But forgoes the only external check on the judge and on §6's classifier — whose 0.90 / ≤0.02 bars currently have **no external referent whatever** and were, as the spec admits, proposed rather than derived. |
| **B** | **Admissible as corroboration, never as the deciding evidence.** | Cheap and low-risk. Also nearly weightless: a reading that cannot change a verdict rarely changes behaviour either, and it risks becoming decoration that makes the process look externally validated when it is not. |
| **C** | **Admissible for instrument-validation claims only** — judge agreement, classifier accuracy, calibration — **never for adoption claims.** | Tracks the actual asymmetry: instruments should generalise, preferences should not. Costs a bright line, since "is the classifier good" and "should I adopt this" are separated by a judgement call that will itself need a rule. |
| **D** | **Fully admissible with a declared distribution-shift caveat.** | Maximum external evidence, and imports a distribution the owner did not choose into a gate whose entire purpose is one person's utility. The caveat does the work, and caveats degrade. |

### 4.3 What a ruling should probably also settle

- Whether an external number may set a **bar** (§6's 0.90 / 0.02) as opposed to merely
  reporting alongside one. These are different powers and A–D do not separate them.
- Whether **AIQ or E-AURC as a reporting format** is itself external-benchmark evidence,
  or just a unit. Adopting a metric is not the same as adopting a dataset, and the
  §3 re-cut needs no external data at all — it may well fall outside whatever is ruled.

---

## 5. What this changes in `DR-DECISION-1`

Four concrete amendments, not yet applied:

1. **§5.1 / the bar** should cite **Chow (1970)** and state the identity. It is not our
   result.
2. **§4.1** should cite **Bouchard (2026)** for the ladder's optimality conditions, and
   **§4.3 point 2 should be downgraded** from an observation to a restatement of his
   structural-cost result — with the consequence that adding rungs may buy less than the
   section implies.
3. **§4.1** should record the simultaneous-argmax-versus-early-abstention choice as a
   **design decision with a comparison owed** to Zellinger et al. (2025), not an
   assumption.
4. **§3.2** should record the **False Premise gap**: a question with a false premise has
   no lane and no action, and correcting the premise is a tenth action family that does
   not exist.

## 6. Where I am uncertain

- **The top-m dominance citation is outstanding.** The result is standard; I could not
  attach it to a canonical source in this pass.
- **The four "OURS" items are unsearched, not novel.** Each needs a targeted search
  before any claim is made in public.
- **The AURC re-cut assumes withheld rows carry a gradeable MAP candidate.** If
  correctness was only recorded on asserted rows, the curve costs a grading pass and is
  not free.
- **Bouchard's structural-cost result may not transfer.** His cascades pay a cheap
  *model* before escalating; ours pays *retrieval and extraction*. Whether that is the
  same structural cost, or a cheaper one, determines whether conclusion 2 above is a
  real constraint here or an analogy.

---

## Sources

- Chow, C.K. (1970). On optimum recognition error and reject tradeoff. *IEEE Trans. Inf. Theory* 16(1):41–46. https://dblp.org/rec/journals/tit/Chow70.html
- Madras, Pitassi & Zemel (2018). Predict Responsibly: Improving Fairness and Accuracy by Learning to Defer. NeurIPS. https://arxiv.org/abs/1711.06664
- Mozannar & Sontag (2020). Consistent Estimators for Learning to Defer to an Expert. ICML. https://proceedings.mlr.press/v119/mozannar20b.html
- Chen, Zaharia & Zou (2023). FrugalGPT. https://arxiv.org/abs/2305.05176
- Bouchard (2026). Is Escalation Worth It? A Decision-Theoretic Characterization of LLM Cascades. https://arxiv.org/abs/2605.06350
- Zellinger, Liu & Thomson (2025). Cost-Saving LLM Cascades with Early Abstention. https://arxiv.org/abs/2502.09054
- Hu et al. (2024). RouterBench: A Benchmark for Multi-LLM Routing System. https://arxiv.org/abs/2403.12031
- Kirichenko, Ibrahim, Chaudhuri & Bell (2025). AbstentionBench. NeurIPS D&B. https://arxiv.org/abs/2506.09038
- Dynamic Model Routing and Cascading: A Survey. https://arxiv.org/pdf/2603.04445
- UCCI: Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing. https://arxiv.org/html/2605.18796
