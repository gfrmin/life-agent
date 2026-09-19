# Session record — 2026-09-05

**What this is.** One working session in which the decision layer's specification was
overhauled, several earlier conclusions were reversed, and a number of claims were traced
to prior literature. Much of the reasoning existed only in a chat log; this is the durable
form.

**How to use it.** Every entry has a stable ID (`D-n` settled, `C-n` corrected, `R-n`
rediscovered, `O-n` open). Entries are one paragraph and a pointer, not a narrative — the
full argument lives in the linked spec. **Skim the index; follow one ID.**

**Status of everything here:** specification and analysis only. **No implementation was
written or authorised.** Nothing is committed; all documents are untracked.

---

## Index

| | |
|---|---|
| **§1 Settled** | D-1 host/language division · D-2 oracle primitive withdrawn · D-3 proplang 0h · D-4 universality is aesthetic · D-5 the routing thesis · D-6 L1/L2/L3 · D-7 score correctness never fit-to-need · D-8 action space overhaul · D-9 pointer-to-source floor · D-10 multi-attribute cost · D-11 privacy as constraint · D-12 tannen scope |
| **§2 Corrected** | **C-11 OQ-0 was already ruled** · C-1 elicited not asserted · C-2 missing affordance · C-3 OQ-0 malformed · C-4 option (d) dropped · C-5 AbstentionBench ID · C-6 unverified figures · C-7 line-number drift · C-8 committed baseline · C-9 fragmentation · C-10 bad test fixture |
| **§3 Rediscovered** | R-1 Chow · R-2 Madras · R-3 Mozannar/Sontag · R-4 FrugalGPT · **R-5 Bouchard — recorded backwards, corrected** · R-6 Zellinger · **R-7 revised: three of four withdrawn** · **§9 second pass 2026-09-06** |
| **§4 Open** | O-1 OQ-0 **+ option (c′)** · O-2 OQ-1..OQ-10 · O-3 governance · O-4/O-5 **applied** · **O-6 CLOSED** · O-7, O-8 · O-9 A-CAL · **O-10 does L3 skip retrieval?** |
| **§5 Next** | calibration+AURC → lane census → OQ-0 → escalate affordance |
| **§6 Removed** | branch, three modules, two husk DRs |
| **§7 Document map** | which file holds what |
| **§8 Applied** | A-1…A-5, what landed 2026-09-06 and what it cost |

---

## 1. Settled

### D-1 — The host owns preferences; the language owns inference
Which actions exist, what they cost, and what is forbidden are **host declarations**.
Which action wins is **inference**. This division governs every other decision here.
**Source:** owner's correction. **Full:** `../../proplang/appendage-spec.md`.

### D-2 — The oracle primitive is withdrawn as a category error
An earlier proposal added a terminal to proplang meaning "call an external service at
cost c". Wrong by construction: proplang is a Bayesian language with primitives, and a
host provides *appendages* over the wire. The language does not need to know an action
reaches the network any more than it needs to know `respond` reaches a human. **Source:**
owner. **Full:** `appendage-spec.md` §"The correction this records".

### D-3 — Escalation costs 0h of proplang change
Verified against the protocol: `Menu = [(Name, Grid)]` (`Membrane.hs:80`), declared at
`hello` (`Host.hs:255-257`), no length check anywhere. Cost is expressible today as
`Sub (Expect …) (C cost)` or as a namespace feature read by `get`. Prohibition is
per-tick name-withholding. Reliability is learnable via a guard. **The four-point
affordance grid at `world.py` `AFFORDANCES` is life-agent's own choice, not a protocol
limit.** Earlier estimate of 160h was wrong by the whole amount. **Full:**
`appendage-spec.md` §"Gaps, by locus of change".

### D-4 — Lam/App/Fix is a separate aesthetic goal, not on the routing critical path
Routing needs calibration, not expressiveness. Appendages are the reach mechanism and
they are host-side. Estimates, unchanged: `Lam`/`App` ≈ 1 week (de Bruijn + host closures
give capture-avoidance free); **`Fix` is a rewrite of the semantic core** — `evalx`'s
total signature becomes fuel-indexed across ~36 call sites, `Code` admission goes from
decidable to semi-decidable, `prodTable 9 → 12` invalidates every price literal in-tree —
**10–14 engineer-months.** Choose it deliberately or not at all.

### D-5 — The routing thesis
The system's purpose is **knowing when to invoke the oracle, not competing with it.**
π\* stops being an opponent and becomes a priced affordance. This reframing is what
exposed D-8, and it is the north star the specs are written against.

### D-6 — L1/L2/L3
L1 point-fact (binary grading is **correct**, not impoverished); L2 metric (graded); L3
open-ended (**not scored — escalate**). **Full:** `DR-DECISION-1` §3.0 rationale in
`DR-UTILITY-1`, procedure and bars in `DR-DECISION-1` §6.

### D-7 — Score correctness; never score fit-to-need
Correctness has a canonical ordering given a claim shape. Fit-to-need — length,
verbosity, framing — does not, because it depends on the question, the moment and the
person, none of which are properties of the answer. **Any scalar invented for it is
arbitrary, and arbitrary is what an optimiser exploits.** **Source:** owner's objection
("maybe a shorter answer is better than a longer one, maybe sometimes it's the other way
around"). This is the observation the whole scope reduction rests on.

### D-8 — The action space is overhauled, not patched
**Ten** action families (A10 added 2026-09-06, §8 A-4), with **assert-at-a-shape as
distinct actions** rather than one action carrying a quality score. Sets collapse
**2^K → K** by prefix dominance. Cardinality is **additive** (≤ 3K + 8 + R + P + 4 ≈ 44)
because everything is grid points
on **one writable name** — declaring each family as its own name would invoke the
cartesian product. **Full:** `DR-DECISION-1` §3.

### D-9 — Pointer-to-source is the floor action
*"I cannot answer, but the answer is in these documents."* Available in every lane,
requires no oracle, discloses nothing, works offline, and is **gradeable** — it converts
generation into retrieval. It is what removes the L3+SEALED dead cell. **Gated on OQ-4.**

### D-10 — Multi-attribute cost
Money (**metered**, not imputed), time (`latency_s` is already recorded and priced
nowhere), disclosure. Scalarised **host-side**, because the wire carries one `Rational`
and `Expr` has no product sort — and giving it one is a language change explicitly
refused (`appendage-spec.md` G5).

### D-11 — Privacy is a hard constraint, not a large negative
SEALED content makes disclosing actions **infeasible at any price**. The reason a large
negative fails: **it gets traded away when the answer is valuable enough**, and for
medical, financial or third-party-confidential material that trade must not be available
to an argmax. Enforced by withholding the menu name — verified as the only supported
mechanism, since `policyPick` returns `Nothing` only for an empty candidate list
(`Membrane.hs:319-320`) and there are no feasibility masks.

### D-12 — tannen: the boundary ledger, not the substrate
Routing raises the bar above the DuckDB cheap path in exactly three ways — tamper
evidence, deletion-correctness under retraction, decidable freshness of the reliability
chain. The disclosure ledger is **the first data in this system that is natively
relational**. ~7 weeks, against 25–40 for the substrate rewrite that remains not
recommended. **Gated entirely on OQ-5.** **Full:** `../../tannen/SCOPE-under-routing.md`.

---

## 2. Corrected — the audit trail

**This section matters more than §1.** Several corrections were the owner's, and the
record says which.

### C-11 — **OQ-0 was already ruled, and every document in this session said otherwise**
**The largest single error of the session, found 2026-09-06 by reading
`session-brief-zesty-fountain.md`** — a current, unrelated plan that flags it in its own
Part 5 as something to tell the owner.

**OQ-0 was ruled by owner interview on 2026-09-05** —
`docs/unification/conferrals/a3-regime-conferral.md`, `RULINGS` **M-34**, enacted
**GD-29**. *"The guard STANDS and is made honest"*: the A3 gate keeps
`frozen-elicitations`, "one utility" binds every **decider** with the gate exempt by
declaration, and the gate publishes **both break-evens beside the measured marginal
reach**, quoting **INCONCLUSIVE** when the reach falls strictly between them. It was
**built** — `core/gate.py` has `VERDICTS = ("PASS","FAIL","INCONCLUSIVE")`,
`RegimePairing.straddles`, and the straddle branch in `verdict()`. `RULINGS` §5 has had
nothing live since.

**That is option (d) of our own restatement** — the one an earlier turn congratulated
itself for *restoring* to the options list, not realising it had already been adopted and
shipped a day earlier.

**Root cause, and it is not a search failure.** Every OQ-0 analysis was built from
`s18-bar-conferral.md` (2026-09-04), which **poses** the question. The conferral that
**answers** it is one directory over, dated one day later, and was never opened. The
lesson generalises past this instance: **a conferral that states a question is not
evidence that the question is open.** Check for a successor before treating any conferral
as live.

**Corrected in:** `OPEN-QUESTIONS` (OQ-0 marked ruled, with the ruling quoted; (c′) and
the Kalai disagreement demoted to a new open successor **OQ-0′**), `DR-UTILITY-1` §0,
`DR-DECISION-1` §1/§10, `ORIENTATION`, `GLOSSARY`.

**What survives the correction:** the two-estimate table, the circularity and instability
objections, and the reasoning about why the question was hard — the gate now publishes
exactly that pair of break-evens, so the analysis describes the shipped behaviour.
**What does not:** every "unruled", "must be ruled first", and §10's step-1 gate on it.

### C-1 — `u_wrong` was elicited, not asserted — **owner's correction**
An external review claimed `u_wrong` and `lambda_usd` were "asserted, not elicited". Both
wrong: `u_wrong` was elicited 2026-06-18 as a 10:1 ratio dialled back from 20:1
(`config/utility-model.example.yaml:17-19`); `lambda_usd` was elicited 2026-08-09 with a
written contamination disclosure. **Genuinely unelicited:** `kappa_att`, `tau`,
`tau_narrative`, the six `*_scale_*` latents, `u_wrong_scoped`'s `noise_sigma`. The
`lambda_usd` elicitation is **unverifiable from public master** — `elicitations.jsonl` is
not in the repo. **Full:** `DR-UTILITY-1` §0.1.

### C-2 — Missing affordance, not misspecified gauge — **owner's public-master audit**
Three turns of analysis diagnosed the system as abstaining because `u_wrong` forbade
consulting an oracle. Wrong. **Under either candidate estimate there is no escalate action
in the action set to forbid.** The system does not decline to ask; it has no action with
which to ask. This is a missing-affordance defect needing no re-elicitation, and it
reorganised the entire specification.

### C-3 — OQ-0 was malformed, not merely leaning — **owner, extending their audit**
The specs asked "which Ū are these numbers quoted at?" and called −5.131 "the deployed
value, the one that describes the running system". Both errors. `s18-bar-conferral.md`
had **already ruled** that `u_wrong` is not a gauge but an **identified latent**: the two
values "were never two conventions to choose between; they are two estimates of one
quantity, and the choice between them is **epistemic**." The conferral calls that framing
**"a bad question, not a bad answer"** — and the specs reproduced it. Two independent
objections to the reaction-conditioned fold now recorded separately: **circularity**
(reactions project from verdicts on the log the gate scores; adopting it deletes
`frozen-elicitations`, an anti-circularity guard, and flips Δ −0.080 → +0.075) and
**instability** (−5.9395 → −8.8301 → −5.1310 across 20 boot records; in August the two
bars sat within 0.002). **The instability objection holds even if circularity were
resolved.** **Full:** `OPEN-QUESTIONS-utility.md` OQ-0.

### C-4 — Option (d) had been dropped from our own specs
The conferral's own recommendation — *keep blindness and report `inconclusive` when
measured reach straddles the two break-evens* — was in the record and the specs did not
carry it. It is the only sub-answer that changes what `r49` was entitled to conclude.
Restored as OQ-0 option (d).

### C-5 — AbstentionBench is arXiv **2506.09038**, not 2605.25850
The latter ID is a different paper (*TIAR: Trajectory-Informed Advantage Reweighting*).
Correct reference: Kirichenko, Ibrahim, Chaudhuri & Bell, NeurIPS 2025 D&B.

### C-6 — Two AbstentionBench figures could not be verified
The "31 subsets" count and the "82.3%" judge-vs-human agreement did not surface in this
pass. **Marked UNVERIFIED rather than repeated.** Do not quote until checked.

### C-7 — Line-number drift, and the policy that came from it
An independent audit against public master found three citations that had drifted
(`Sub`/`C` parse, `interval_options`, the wire's posterior-growth figure). **Policy
adopted: cite the symbol; treat the line number as a hint.** `parseSaidWith, Host.hs:593`
survives a refactor; a bare line range does not. 21 symbols were then re-verified against
the tree.

### C-8 — The committed-baseline rule exists because we broke it
`ORIENTATION.md` and `GLOSSARY.md` cited `core/router.py`, `scripts/route_arm.py` and
`tests/test_router.py` — **none of which were ever on master.** An entry-point document
citing a working copy is a defect. **Rule: entry-point documents cite what is pushed.**
Now stated in `ORIENTATION.md` §Conventions *with the reason*.

### C-9 — The overhaul was fragmented into increments — **owner's correction**
Three narrow documents (escalate affordance, lane classifier, tannen scope) were written
where one overhaul was agreed. The action space and the utility are **not separable**: a
preference cannot be stated about an option that does not exist. Consolidated into
`DR-DECISION-1`; two husks superseded (§6).

### C-10 — A test fixture overstated the oracle
During the brief implementation excursion, a synthetic fixture made π\* correct on every
row the typed arm answered, inflating its score. Caught by its own assertion. Rebuilt to
pin **both** arms to published marginals (61/2/41 and 95/6/3) so only the joint — how π\*
does on rows typed withheld — remains derived. The code was later removed (§6); the
lesson is recorded because the fixture design is reusable.

---

## 3. Rediscovered rather than invented

Verdicts and full argument: `LITERATURE-AND-HARNESSES.md` §1.

### R-1 — The commit bar is Chow's rule, exactly
Not an analogy — the same formula. Chow (1970) gives `t = (Cr−Cc)/(Ce−Cc)`; with our
gauge (`Cc = −1`, `Cr = 0`, `Ce = |u_wrong|`) that yields `1−t = |u_w|/(1+|u_w|)`, which
is `gate.py:317` identically. **0.8369 and 0.9000 are Chow thresholds.**

### R-2 — Escalation-as-action is learning-to-defer
Madras, Pitassi & Zemel (2018) "generalizes rejection learning by considering the effect
of other agents". Our framing is their framing; `p_r` is their model of the external
decision-maker's accuracy.

### R-3 — Mozannar & Sontag is *not* what we do, in either direction
They give the consistent surrogate loss for **training** a deferral policy. We **compute**
EU from an explicit posterior and utility — no training, no surrogate, no consistency
theorem needed. **The consequence is uncomfortable and should stay recorded: we therefore
have no learning-theoretic guarantee about the policy we get, and the whole construction
rests on the posterior being calibrated — which nothing in the specs establishes.**

### R-4 — The ladder is an LLM cascade
FrugalGPT (Chen, Zaharia & Zou 2023). Not a design choice of ours; a known pattern we
adopt. Describe it that way.

### R-5 — Bouchard (2026) proves what §4.1 asserts and what §4.3 only noticed
*Is Escalation Worth It? A Decision-Theoretic Characterization of LLM Cascades* (arXiv
2605.06350). Derives ladder optimality conditions we never did — a single shadow price λ
equalising marginal quality-per-cost across active stage boundaries; piecewise concavity
of the frontier. And our §4.3 note that pre-decision spend "must be attributed or
escalation looks cheaper than it is" is the weak form of his result: **cascade performance
is limited primarily by structural cost, because the cheap model is paid before any
escalation decision.** We found a bookkeeping hazard; he showed it caps the design — so
adding rungs may buy less than §4.1 implies.

### R-6 — Where abstention sits in a cascade is contested, and we picked a side silently
Zellinger, Liu & Thomson (2025, arXiv 2502.09054) ask whether abstention belongs only at
the final model or also at earlier ones. `DR-DECISION-1` puts abstain and escalate in
**one simultaneous argmax** — a third position, defensible, **but asserted rather than
argued.** Comparison owed.

### R-7 — Four items with no precedent found *in this pass*
Recorded as "not found", **not as novel**: the string-blind NONE-atom posterior;
shape-dependent `u_err` with `u_vague`; `p_r` learned via a guard on the writable name;
SEALED as feasibility rather than price. Each needs a targeted search before any public
claim. The top-m dominance result is standard but **its canonical citation is
outstanding**.

---

## 4. Open

### O-1 — **CLOSED 2026-09-05, discovered 2026-09-06.** OQ-0
Four options: (a) elicitation-only −8.9993; (b) reaction-conditioned −5.131;
(c) neither — a third basis required; (d) keep blindness, report `inconclusive` when reach
straddles the break-evens. Four admissibility conditions specified for (b). **The two
candidates straddle the −7.4285 break-even**, which is why this is load-bearing.
**Full:** `OPEN-QUESTIONS-utility.md` OQ-0.

### O-2 — OQ-1 … OQ-10
Willingness to pay · value of time · `u_vague` · are hedges/pointers useful · privacy
shape · local rung · re-basing `lambda_usd` · rung set · verbosity in the structured lane ·
**OQ-10 the error cost of an *attributed* answer**, which is what makes escalation lose
under the elicitation-only estimate and has never been elicited.

### O-3 — Governance: are external benchmarks admissible evidence? **Unruled, framed only**
Four options (inadmissible / corroboration-only / instrument-validation-only / fully
admissible with caveat). The framing worth carrying: distance runs *owner's questions →
gate set → public benchmark*, **but it cuts the other way too** — a public benchmark has
labels the owner did not make, and self-supplied labels are exactly what O-1 is stuck on.
**Full:** `LITERATURE-AND-HARNESSES.md` §4.

### O-4 — **APPLIED 2026-09-06.** Four amendments to `DR-DECISION-1`
Owner authorised direct editing; these are no longer pending. See §8 (A-1…A-5) for what
landed and what it cost. Retained here so the transition is legible rather than silently
deleted: the four were (i) Chow at §5.2.1; (ii) Bouchard at §4.1/§4.3; (iii) the
Zellinger design-choice record at §4.1; (iv) the False Premise gap (O-5).

### O-5 — **APPLIED 2026-09-06** as `correct_premise` (A10), *specified but not enabled*
Found by reading AbstentionBench's taxonomy. A question whose premise is false had **no
lane and no action** in `DR-DECISION-1` §3.2. Now specified at §3.5 as a tenth action
family, feasibility-gated by a premise detector rather than by enlarging the answer
simplex. **Deliberately not enabled**: it carries `u_wrong` while `p_prem` has no data
behind it at all (§8 R7), and nobody has checked whether any of the 41 withheld rows are
false-premise rows (§7.6). Enabling waits on the census.

### O-9 — **NEW.** A-CAL: the posterior is assumed calibrated, and nothing establishes it
Named as a standing assumption at `DR-DECISION-1` §2.1 so it cannot be lost again. The
argmax computes EU from `P(ω)`, so `P(ω)` must mean what it says; the commit bar is a
*threshold on the posterior's value*, which makes it maximally sensitive to
miscalibration. **This is the price of not training a deferral policy** (R-3): no
surrogate, no consistency theorem, and therefore no learning-theoretic guarantee — the
guarantee is traded for calibration. Established by a reliability diagram + ECE, which is
**not** the AURC re-cut; that tests discrimination. Both now sit at §10 step 0.

### O-10 — **NEW.** Does L3 skip retrieval?
Bouchard's empirical headline is that a **pre-generation router beats the best cascade on
four of five datasets**, by avoiding payment for the cheap stage on queries sent straight
up. §6's lane classifier is question-only and therefore already such a router; §4.3 puts
escalation *after* retrieval and extraction. So the machinery exists and the spec does not
use it. **Answering "yes" removes `pointer` from the L3 path** — it is a retrieval action —
**and so reopens the L3+SEALED cell that D-9 closed.** Recorded unanswered at
`DR-DECISION-1` §4.3.1; needs either the transfer question settled (does retrieval cost
behave like a cheap model's?) or an owner ruling on whether that cell may empty.

### O-6 — **CLOSED 2026-09-06.** Prefix-set dominance assumes size-only grading
The worry was that grading by F1 against a gold *set* would make `x` composition-dependent
and break the collapse. **It does not, for our case.** For a *single* gold label, F1
against the predicted set is `2/(m+1)` if contained and 0 otherwise — **size-only** — so
prefix dominance survives under F1 exactly as under `1/m`. It fails only for multi-label
gold sets, which is a different problem (Nguyen & Hüllermeier 2019). The canonical theorem
is Mortier et al. 2021; Del Coz 2009 did the F_β case. **Closed.**

### O-7 — The third action partition is an unverified precondition
`escalate` is neither an assertion nor a withholding. Adding it to `ASSERT_ACTIONS`
(`gate.py:87`) silently re-values every archived row. **It has not been verified that the
gate's fold survives a third partition member.**

### O-8 — The lane census may show L2 is thin
If most real questions are L1 or L3, the graded-utility machinery serves a small slice and
the escalate affordance carries nearly all the value. **This is the cheapest way to
discover that half the programme is unnecessary**, which is why it is second in §5.

---

## 5. Next, in order

| | Action | Why this position |
|---|---|---|
| 0 | **Calibration check — reliability diagram + ECE** | Tests **A-CAL** (O-9), the precondition on the argmax itself. **Not the same measurement as AURC**, which tests discrimination. Same data, same pass — run together. If A-CAL fails, O-1 is moot: no threshold on an uncalibrated posterior means what it says. |
| 1 | **AURC re-cut of the existing 104 rows** | **Gauge-independent** — asks whether the leader credence is a good *ranking*, which is orthogonal to O-1. If the ranking is good, O-1 chooses an operating point on a good curve; if poor, no bar helps and the dispute is moot. No new data. **Dependency: needs a gradeable MAP candidate on the 41 withheld rows.** If correctness was only recorded on asserted rows, this costs a grading pass and is not free. Construction: `LITERATURE-AND-HARNESSES.md` §3. |
| 2 | **Lane census + classifier measurement, plus a premise-validity label** | Also gauge-independent; O-8 may retire much of the programme, and the premise label is the only way to learn whether A10 has a live population (`DR-DECISION-1` §7.6). Bars 0.90 overall / **≤0.02 L3→L1**, pre-registered, full 3×3 confusion matrix, human self-agreement measured first as the ceiling. |
| 3 | **Rule OQ-0** | A ruling, not an elicitation. Everything in §7 of `DR-DECISION-1` is quoted against it. |
| 4 | **Specify the escalate affordance** | Stands under **every** O-1 option — building the action is not a bet on the ruling; only *claiming it fires* is. |

---

## 6. Removed, and why

| Artifact | Why |
|---|---|
| branch `routing/escalate-arm`, commit `0d1b7bc` | Implementation begun before the specification was signed off. Owner: *"otherwise we're building on sand again."* |
| `src/life_agent/core/router.py` | Same. Also carried the C-1 wording error in a docstring. |
| `tests/test_router.py` | Same. 17 tests, all passing; the fixture lesson is preserved at C-10. |
| `scripts/route_arm.py` | Imported `core/router`; dead once that was removed. |
| `docs/DR-ESCALATE-1-affordance.md` | Superseded by `DR-DECISION-1` §3–§4 (C-9). Husk retains a banner. |
| `docs/DR-LANE-1-classifier.md` | Superseded by `DR-DECISION-1` §6 (C-9). Husk retains a banner. |

**Note on absences:** the deletions are the owner's to execute. This agent could not
`unlink` inside the mount, so some of these may still be present on disk as untracked
files at the time of reading.

---

## 7. Document map

| File | Holds |
|---|---|
| `DR-DECISION-1-action-space-and-utility.md` | **The spec.** Action space + utility stated whole; closure argument; residue; lane classifier (§6); provenance (§9) |
| `DR-UTILITY-1-graded-multiattribute.md` | **The record.** OQ-0 gauge table, §0.1 errata, L1/L2/L3 rationale |
| `OPEN-QUESTIONS-utility.md` | OQ-0 … OQ-10 |
| `LITERATURE-AND-HARNESSES.md` | Claim-by-claim literature map, harness survey, AURC construction, governance framing |
| `SESSION-RECORD-2026-09-05.md` | This file |
| `ORIENTATION.md` / `GLOSSARY.md` | Entry point and vocabulary |
| `../../proplang/appendage-spec.md` | D-1 … D-4: the host/language division, 0h, universality |
| `../../tannen/SCOPE-under-routing.md` | D-12: provenance surviving an escalation. **Private repo — outside any public-master audit** |

---

## 8. Applied 2026-09-06 — what landed, and what it cost

The owner authorised direct editing of the specs ("I meant update any files you want").
O-4 and O-5 moved from pending to applied. Recorded rather than deleted, so the audit
trail survives.

| | Amendment | Where | Cost |
|---|---|---|---|
| **A-1** | **Chow as an identity, not an analogy.** The commit bar `p* = \|u_w\|/(1+\|u_w\|)` **is** Chow's (1970) reject rule under our gauge, derived in place. No novelty is claimed for the bar; what may be ours is the *shape-dependent* `u_err`, which reject-option theory does not have. | `DR-DECISION-1` §5.2.1 | None. Strictly a correction of attribution. |
| **A-2** | **Bouchard on the ladder.** Optimality conditions exist (single shadow price λ equalising marginal quality-per-cost across stage boundaries) and we never derived them; **structural cost caps the ladder**, so adding rungs buys less than §4.1 implied. | `DR-DECISION-1` §4.1(i)(ii), §4.3 pt 2 | **Real.** §10 step 5 now says do not expand the rung set (OQ-8) until it is settled whether his result transfers — his cascades pay a cheap *model* pre-escalation, ours pays *retrieval and extraction*. |
| **A-3** | **Zellinger design-choice record.** Simultaneous argmax over a flat escalate row, rather than a sequential cascade with per-stage abstention, is a **third position** — defensible, but asserted rather than argued. | `DR-DECISION-1` §4.1 | A comparison owed. Must be revisited first if the ladder ever becomes sequential. |
| **A-4** | **`correct_premise` (A10) as a tenth action family.** Feasibility-gated by a premise detector, flat over ω, `u_err = u_wrong`. Deliberately *not* folded into the NONE atom — "I could not find it" and "the question is ill-posed" are different, and conflating them is the error NONE exists to prevent. | `DR-DECISION-1` §3.2, §3.5, §5.1, §5.2, §5.5, §7.6, §8 R7 | Cardinality → ≤44. **Specified but not enabled**: `u_wrong` error cost against a `p_prem` with no data at all. Adds one label to the census. |
| **A-5** | **A-CAL / A-LANE / A-GRADE named as standing assumptions.** The calibration the whole argmax rests on was going unstated; it is now a named precondition with a stated test. | `DR-DECISION-1` §2.1; `ORIENTATION.md`; O-9 | **The largest.** Reordered §10 — calibration + AURC moved to step 0, ahead of the OQ-0 ruling, because **A-CAL is a precondition on the argmax itself: if it fails, the gauge dispute is moot.** |

### What the enlarged action space broke, and what it did not

**Did not break:** §3.3's prefix-set dominance (about *answer candidate* sets; A10 is not
a set action, so 2^K → K is untouched); §5.5's "no action always wins" (A10 is flat, so a
concentrated posterior beats it, and it is feasibility-gated off most menus); §7.2 and
§7.3 (no reference to it). **Improved:** §7.4's L3+SEALED margin — A10 discloses nothing
and is locally derived, so it survives both SEALED and an oracle outage.

**The one genuine break — and it is an evidence gap, not a logic error.** §7.1 claims the
41 withheld rows route to escalation. **Nobody has classified those rows for premise
validity.** A question can presuppose something false *and* retrieve plausible candidates
— precisely the case that produces a confident wrong answer — so a firing premise detector
among the 39 `dispersed` rows is unusual but not impossible. §7.1's claim is therefore
about a population that has not been checked for this. Hence the extra census label
(§10 step 2). Until then, A10 has **no established population**, which is the second
reason it is specified rather than enabled.

---

## 9. Second literature pass — 2026-09-06

Source: `LITERATURE-REPORT-utility-2026-09-06` (owner-supplied; ~15 queries, **3 primary
sources read in full**: AbstentionBench v1, Bouchard abstract + §6–7, CRAG scoring). Its
tagging is carried into the specs verbatim: **[P]** primary read · **[S]** secondary /
abstract only · **[NF]** searched, not found. **No [S] has been upgraded to a settled
fact anywhere in this pass.**

### What it changed

| | Change | Where |
|---|---|---|
| **S-1** | **OQ-0 gains option (c′)** — the *bounded-improvement* model (Pietraszek 2005; Geifman & El-Yaniv SGR). Fix a **target selective risk**, maximise coverage, elicit no reject cost; by the **Franc & Průša (2019) equivalence** the implied `u_wrong` is *derived*. Converts OQ-0 from "which estimate of a latent" to "which observable do you want to bound". | `OPEN-QUESTIONS` OQ-0 |
| **S-2** | **OQ-0 gains a named disagreement.** Kalai et al. 2025 **[P]** propose a stated per-task threshold `t` with penalty `t/(1−t)`; **at t=0.9 that is exactly 9.0**, so the elicitation-only estimate coincides with the OpenAI convention to four figures. They argue it is a **policy parameter to state**, contradicting the conferral's **identified latent**. Both defensible; the ruling must pick a side. | `OPEN-QUESTIONS` OQ-0 |
| **S-3** | **R-5 was recorded backwards.** Bouchard's headline is that a **pre-generation router beats the best cascade on 4/5 datasets** by not paying the cheap stage. That is a *disagreement* with §4.3, not a caveat on OQ-8. | `DR-DECISION-1` §4.1, §4.3.1; **O-10** |
| **S-4** | **A-CAL gets its theorem.** Fumera, Roli & Giacinto (2000): Chow's rule is optimal **only against true posteriors**; remedy for partial failure is **class-specific thresholds** → per-lane bars. Conformal deferral (2509.12573) is the assumption-swap alternative — exchangeability instead of calibration, distribution-free. | `DR-DECISION-1` §2.1 |
| **S-5** | **Three novelty claims withdrawn, O-6 closed.** Prefix dominance = Mortier et al. 2021. `x = 1/m` = Zaffalon et al. 2012 *discounted accuracy*, with a **uniqueness result** and the **doctor-random-vs-doctor-vacuous** argument — which *is* §7.3's k-independent hedge, and makes `u_vague` **not optional**. `p_r` from queried-expert outcomes = online L2D under bandit feedback + EA-L2D Beta-Binomial. §4.4 = standard VOI. | `DR-DECISION-1` §3.3, §4.1, §4.4, §5.2; `LIT` §1.6 |
| **S-6** | **Figures corrected.** AbstentionBench judge is **88%** (v1 §3.4), not 82.3%; **20** datasets; "31 subsets" does not appear in v1. **[P]** | `LIT` §2.2 |
| **S-7** | **AURC needs a companion and cannot decide alone.** Traub et al. (NeurIPS 2024): selective risk is unsuitable for aggregation across thresholds → report **AUGRC** beside E-AURC. And **104 rows is too few for either to carry a decision** — §10 step 0 is *informative, not decisive*. | `LIT` §3; `DR-DECISION-1` §10 |
| **S-8** | **Two blocked items unblocked.** AbstentionBench's **False Premise subsets (FalseQA, (QA)², KUQ, CoCoNot)** give `p_prem` data now — the missing probability behind A10. **ATM-Bench** (2603.01990): ~4 years of personal data, 1,038 human QA with gold evidence, abstention items — the closest public corpus to a personal store. | `LIT` §2.2b–2.2c |
| **S-9** | **OQ-8 has a method.** Zellinger & Thomson 2025 Markov-copula threshold tuning from ~300 examples. Not a substitute for Bouchard's conditions; it tunes thresholds given a chain, and assumes calibrated stage confidences, so it inherits A-CAL. | `OPEN-QUESTIONS` OQ-8 |

### What the pass makes us *less* sure of

Recorded because a literature pass that only increases confidence has not been read
properly.

- **R-7's "shape-dependent `u_err`" was weaker than claimed twice over.** The first pass
  said reject-option theory carries a single error cost. True of Chow; **false of the L2D
  line** — Mao et al. 2024 give H-consistency bounds for *general* cost functions, and
  Verma & Nalisnick 2022 give calibrated deferral probabilities. And Zaffalon 2012 had the
  partial-credit argument in 2012.
- **A-CAL now has a named alternative that may be cheaper than satisfying it.** If
  conformal deferral applies, swapping calibration for exchangeability buys a
  distribution-free guarantee where we currently have none. That would be a change of
  foundation, not a refinement.
- **The measurement layer has an impossibility result waiting.** No continuous scoring
  rule over imprecise forecasts is simultaneously strictly proper, calibrated and
  non-dominated (2503.16395). It does not bite the decision layer, which scores *actions* —
  but it bites the moment AURC/ECE is extended to score sets and intervals *as forecasts*.
- **Every published convention pins `u_abstain = 0` with `u_correct` positive**, and the
  published ratio range is 1:1 (CRAG) to 9:1 (Kalai at t=0.9) to 8:1 (Wu et al.). **Both
  our candidate estimates sit inside it.** Reassuring about the gauge's *shape*; it says
  nothing about which estimate is right, and it slightly weakens the framing of OQ-0 as
  unusual.

### Where the pass is thin — carried forward, not laundered

Bouchard's first-order conditions were **not** checked against his statement (abstract +
§6–7 only). **Franc & Průša, Zaffalon 2012, Mortier 2021, Fumera 2000 and 2605.12340 were
read from abstracts and citing papers, not in full** — and Franc & Průša in particular
**should be read before (c′) is ruled**, since (c′)'s claim to *dissolve* OQ-0 rather than
merely add to it rests entirely on the strength of that equivalence. No search was run on
hierarchical/temporal abstention for `scoped_j`, on provenance ledgers for escalated
answers (tannen §9), or on metered-spend accounting in routers. The privacy-routing
precedent is production folklore plus one AAAI paper.
