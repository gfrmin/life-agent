# Open questions — utility re-specification

Value judgements only the owner can make. Listed rather than defaulted, because a
buried default is how a number becomes load-bearing without anyone deciding it should
be — which is what happened to the **basis for estimating `u_wrong`** (OQ-0), though not,
as an earlier draft claimed, to `u_wrong` itself, which was elicited.

Each has: what is being asked, why it matters mechanically, and what happens if it
stays unanswered. **OQ-0 was RULED 2026-09-05 (M-34/GD-29) — see below. Its successor OQ-0′ is open.**

---

## OQ-0 — **RULED 2026-09-05.** Is a reaction-conditioned fold an admissible basis?

> ### ⚠ THIS QUESTION WAS ALREADY ANSWERED, AND THIS DOCUMENT DID NOT KNOW IT
>
> **Ruled by the owner, by interview, on 2026-09-05** —
> `docs/unification/conferrals/a3-regime-conferral.md`, registered `RULINGS` **M-34**,
> enacted **GD-29**. `RULINGS` §5 has had **nothing live** since.
>
> **The ruling: "the guard STANDS and is made honest."** The A3 gate keeps
> `frozen-elicitations` — the anti-circularity guard — and *"one utility" binds every
> **decider**, the gate exempt by declaration*. The gate publishes **both break-evens
> beside the measured marginal reach** and quotes **INCONCLUSIVE**, neither PASS nor
> FAIL, when the reach falls strictly between them. *"INCONCLUSIVE adopts nothing and
> does not advance the consecutive-FAIL stop rule; its remedy is evidence — a sharper
> `p1`, or the two estimates of `u_wrong` converging — never a softer bar."*
>
> **That is option (d) below, and it was not merely recommended — it was adopted and
> built.** `core/gate.py` carries `VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")` (:407),
> `RegimePairing.straddles` (:345) and the straddle branch (:383, :449). It shipped.
>
> **How this document got it wrong.** Everything below was written across 2026-09-05/06
> from the `s18-bar-conferral.md` of 2026-09-04, which *poses* the question. The
> `a3-regime-conferral.md` that *answers* it was never read. The error was caught by
> `session-brief-zesty-fountain.md`, which flags it in its own Part 5 as something to
> tell the owner. **Recorded rather than quietly patched, because "we leaned without
> saying so" has now happened three times and the pattern is the finding.**
>
> **What survives:** the analysis below is a correct account of *why the question was
> hard*, and (a)/(b)/(d) are the options as the conferral put them. **What does not:**
> every "unruled", "must be ruled first", and any sequencing that gates on it.
> **(c′) and the Kalai disagreement are not options on this question** — it is closed —
> they are a **successor question, OQ-0′ below.**

### The question as it stood before the ruling (retained for the reasoning)


**This question was previously stated wrong here, and the conferral had already said so.**
Earlier drafts asked "which Ū are the specs quoted at?" and called −5.131 "the deployed
value, the one that describes the running system". Both are errors:

- `s18-bar-conferral.md` rules that **`u_wrong` is not a gauge**. The affine gauge is the
  two pins (`u_correct = +1`, `u_abstain = 0`); once pinned, `u_wrong` is an *identified
  latent*. So −8.9993 and −5.131 "were never two conventions to choose between; they are
  **two estimates of one quantity**, and the choice between them is **epistemic**."
  Framing it as a gauge choice is what the conferral calls **"a bad question, not a bad
  answer"** — it routes an evidence question into the conventional bucket and asks the
  owner for a keypress on something the constitution assigns to evidence.
- Calling −5.131 "deployed" and letting that carry normative weight is **a choice being
  inherited rather than made**. It is the *reaction-conditioned* fold. It is not more
  honest for being live.

### The real question, and it is not binary

`r49b` re-posed it and that framing stands: **does the A3 gate keep its blind regime?**
Four admissible answers, not two:

| | basis | what it costs you |
|---|---|---|
| **(a)** | **elicitation-only, −8.9993** | Blind and non-circular, but the decision layer and the gate then read different numbers — *a second master* |
| **(b)** | **reaction-conditioned fold, −5.131** | Consistent across layers, but **circular** and **unstable** (below) |
| **(c)** | **neither — a third basis is required** | Was empty when written; **(c′) now names it** |
| **(c′)** | **rule a target selective risk; derive `u_wrong`** | See below. **Candidate to dissolve the question rather than answer it** — pending one primary read |
| **(d)** | **keep blindness, report `inconclusive` when reach straddles the two break-evens** | The conferral's own recommendation, and the only sub-answer that changes what `r49` was entitled to conclude |

Option (d) was in the record and these specs did not carry it. That is the omission this
restatement repairs.

---

## OQ-0′ — **SUCCESSOR, OPEN.** Should `u_wrong` be *derived from a risk target* rather than estimated?

**OQ-0 settled the gate's regime; it did not settle where the number comes from.** M-34
keeps the gate blind at `frozen-elicitations` and names INCONCLUSIVE as the honest verdict
when the two estimates straddle the reach — and the ruling says its remedy is *"a sharper
`p1`, or the two estimates of `u_wrong` converging"*. **That is an invitation to a third
basis, and the second literature pass found one.** This question is what the material
below actually bears on, now that the regime question is closed.

### (c′) — the bounded-improvement model

**There are two classical models of selective classification, not one.** Alongside
Chow's *cost* model there is the **bounded-improvement** model (Pietraszek 2005), in
which **no reject cost is elicited at all**: you fix a target risk and maximise coverage,
or fix coverage and minimise risk. Geifman & El-Yaniv (2017, arXiv 1705.08500) give SGR,
which returns a selective classifier with a high-probability guarantee on selective risk
for a stated target. **Franc & Průša (2019) establish the equivalence of the two models.**

If that equivalence holds as stated, then ruling a **target selective risk** — *"no more
than 3% of asserted answers may be wrong"* — **derives** `u_wrong` rather than eliciting
or folding it. OQ-0 stops being *"which estimate of a latent"* and becomes *"which
observable do you want to bound"*, which is better-posed: a selective-risk target is
directly checkable against the ledger, where neither candidate estimate is.

**Why this is listed as a candidate and not simply as the answer.** It would not be a
fifth position alongside (a)/(b)/(d) — it would **dissolve** the choice between them,
because a bounded observable is neither elicited nor reaction-folded and so inherits
neither the circularity nor the instability. That is a strong claim, and the evidence for
it is currently **[S] — Franc & Průša is cited from abstract and citing papers, not read
in full.** The report that surfaced it says explicitly that it *"should be read before
OQ-0 (c′) is offered as an option."* **Do not rule (c′) before that read.** If the
equivalence is weaker or more conditional than the abstract implies, (c′) degrades to a
fourth option rather than a dissolution.

**Distribution-free variant:** conformal abstention (Yadkori et al. 2024, arXiv
2405.01563) makes the same move without a calibration assumption — relevant because it
also bears on A-CAL (`DR-DECISION-1` §2.1).

### A live disagreement OQ-0′ must name rather than settle

**The conferral's "identified latent" position is not the only defensible one, and we
have now leaned twice.**

Kalai, Nachum et al. (2025, arXiv 2509.04664) **[P — primary source read]** argue that
evaluation leaderboards penalise abstention, and propose that each task **state a
confidence threshold `t` up front** with a wrong-answer penalty of `t/(1−t)`, so the
optimal policy answers only above `t`. **At `t = 0.9` that penalty is exactly 9.0** — the
elicitation-only estimate coincides with the OpenAI 0.9-threshold convention to four
figures. They argue the *ideal* penalty would reflect real-world harm, but that this is
impractical because harm is specific to problem, application and user group, **so the
threshold should be stated as policy even if somewhat arbitrary.**

That is a published argument that `u_wrong` is a **policy parameter to be ruled**, which
directly contradicts `s18-bar-conferral.md`'s finding that it is an **identified latent
to be estimated**. Both are defensible:

| | position | consequence if adopted |
|---|---|---|
| conferral | identified latent; the choice is **epistemic** | (a) vs (b) is a question about evidence; a third estimate is progress |
| Kalai et al. | policy parameter; the choice is a **stated convention** | (a) vs (b) is a category error — you *declare* it, and −9 is already a defensible declaration |

**A ruling on OQ-0′ must pick a side explicitly.** Note the two interact: under Kalai's
framing (c′) is natural (bounding an observable *is* stating a policy); under the
conferral's it is a genuinely new estimator and needs the Franc–Průša read to be
admissible. **And note M-34 already leans:** by keeping the gate blind and treating
convergence of the two estimates as the remedy, it treats `u_wrong` as a *quantity that
could converge* — i.e. the conferral's epistemic reading, not Kalai's policy reading.
Adopting (c′) would be consistent with that; adopting Kalai's framing would revisit M-34.

### Two independent objections to (b)

**Circularity.** Reactions are projected from verdicts on the very decision log the gate
scores, so a fold conditioned on them **is not independent of what it evaluates**.
`r49b` puts it at its sharpest: implementing the consistency rule literally deletes
`frozen-elicitations`, "a **structurally enforced anti-circularity guard**", and "the
rule designed to prevent result-picking would, on today's numbers, deliver it" — it
flips `r49`'s point Δ from −0.080 to +0.075.

**Instability, which disqualifies (b) on its own.** The fold tracks **non-monotonically:
−5.9395 → −8.8301 → −5.1310 across 20 boot records**, and *in August the deployed bar sat
within 0.002 of the gate's*. A quantity that swings across the whole disputed range
between boots is not a "deployed value" in any sense that supports quoting a headline
against it. **This objection holds even if the circularity were fully resolved**, and it
is the one these specs were most at risk of talking past.

### What would make a reaction-conditioned fold admissible

If (b) is to be recoverable, all four:

1. **Disjointness.** Reactions drawn from a log partition the gate does not score —
   temporal split, held-out questions, or both. Anything less is (b) restated.
2. **A replacement guard.** `frozen-elicitations` may be retired only against an
   equivalent structural guard, never deleted for consistency's sake.
3. **A stability criterion, declared in advance.** A bound on across-boot variance, or a
   smoothing/lag rule making the fold a stable estimate rather than a snapshot. The
   −5.94/−8.83/−5.13 series must be inside the declared bound before the fold is quoted.
4. **Pre-registration of any verdict flip.** If adopting the fold changes a live verdict,
   that must be registered *before* the fold is read, not discovered after.

### What survives in `DR-DECISION-1` §7 if the answer is (c) or (d)

Most of it. The gauge-dependence is narrower than the earlier framing implied:

- **Unreadable:** §7.1's conclusion that the 41 abstentions route today. Its sign is
  `EU(escalate) ≷ 0` and that is exactly what is disputed. **No claim that the 41 route
  should be made under (c) or (d).**
- **Survives unchanged:** §3 (the action space is structure, not preference); §6 (lanes
  are a property of questions); §7.2 (intervals close on their proper population at
  *both* candidate values, −1.3 to −2.1 and −2.3 to −3.7 — the argument is the sign of
  the NONE term, not its size); §7.3 (the `x = 1/m` construction is gauge-independent);
  §7.4 (SEALED is feasibility, not utility); §5.4, §5.6, §9 entirely.
- **Strengthened:** the instruction to report **break-even curves rather than point
  verdicts**. Under (c) or (d) that stops being good practice and becomes the only
  defensible output.
- **Sequencing:** §10 step 2 — specify the escalate affordance — **still stands under
  every option.** Under (a) it is the carrier for a preference OQ-1 may later move; under
  (b) it fires now; under (c)/(d) it is what a resolved basis would act through. Building
  the affordance is not a bet on this question. Only *claiming it fires* is.

**Historical note (the answer to this was M-34):** before the ruling, every escalation
number was quoted against a contested and non-stationary estimate. The ruling's remedy is
to quote **both** and say INCONCLUSIVE on a straddle.

---

## OQ-1 — Willingness to pay for an answer you would otherwise not get

**Ask:** For a question the system would otherwise be silent on, what would you pay
for a correct answer? Give a number in dollars, and the point where you would rather
have silence.

**Why it matters:** this number pins the escalation decision jointly with `u_wrong`, so
**OQ-0 comes first**. At the oracle's measured 94%, willingness to pay is **$0.478 under
the reaction-conditioned estimate** (above the $0.375 oracle) and **$0.305 under the
elicitation estimate** (below it) — the two straddle the price, which is why the basis
question is not cosmetic. The ceiling for a *perfect* answer is **$0.75 under either**,
depending on `lambda_usd` alone (OQ-7). Answering OQ-1 directly is also the cleanest
route out of OQ-0: an indifference price elicited *now*, blind to both estimates, is a
third basis that neither inherits the circularity nor the instability.

**Sharper form, which is easier to answer than a ratio:** *at what price would you
rather pay the model than get silence?* Answering that pins `u_wrong` by indifference,
and is a better elicitation than the 10:1 ratio question of 2026-06-18 because it asks
about the decision actually faced.

**If unanswered:** the ceiling stays an accident, and every escalation reading is a
reading of that accident.

---

## OQ-2 — The value of time

**Ask:** (a) What is an hour of your waiting worth, in dollars? (b) Is the cost linear,
or is there a cliff — a latency past which the answer stops being useful at all?
(c) Does it differ when you are asking interactively vs when a background job asks?

**Why it matters:** `latency_s` is already recorded on every `DecisionEvent`
(`decisions.py:179`) and priced **nowhere**. The escalation ladder's upper rungs
(extended sampling, multi-sample) trade time for accuracy, and without a rate the
argmax cannot see the trade.

**If unanswered:** the ladder collapses to a money-only ordering and will pick slow
rungs that you would have refused.

---

## OQ-3 — `u_vague`: the cost of an imprecise but not false answer

**Ask:** "It is one of these three" or "between €4k and €6k", where the truth is inside
the range — how does that compare to (a) silence, and (b) a confidently wrong exact
answer?

**Why it matters:** this is the load-bearing new latent. Today an interval that
contains the truth is charged the same full wrong-cost as a flatly false claim at the
NONE atom — worth −1.3 to −2.1 under the reaction-conditioned estimate, −2.3 to −3.7 under the elicitation-only estimate,
and most of the 4.5–7 gauge-unit gap by which intervals lost either way. Ranking
alone is nearly enough: if imprecise-but-containing sits closer to silence than to
wrong, partial credit becomes viable.

**If unanswered:** partial credit stays dead, and §3.1 cannot be specified numerically.

---

## OQ-4 — Are hedged answers actually useful to you?

**Ask:** Honestly — is "it is one of these three" useful, or is it noise you would
rather not receive? Does the answer change with set size (3 vs 10 vs 40)? And is
**pointer-to-source** — "I cannot answer, but it is in these three documents" — more
or less useful to you than a hedge?

**Why it matters:** `DR-UTILITY-1` §3.5 proposes pointer-to-source as the universal
floor action, including for questions barred from escalation by privacy. If you would
not use it, that floor is imaginary and the SEALED + open-ended class genuinely has no
action.

**If unanswered:** the floor is designed on an assumption about your preferences.

---

## OQ-5 — The privacy constraint's shape

**Ask:**
1. Is there material that must **never** leave the machine at any price? If yes, name
   the classes (medical? financial? third-party confidences? legal?).
2. Is the boundary per-item, per-source, or per-topic?
3. For everything not in that class, is disclosure a **cost you would trade** against a
   better answer, or a second constraint?
4. Does a disclosure already made this session make the next one free, or does each
   disclosure cost again?

**Why it matters:** `DR-UTILITY-1` §3.2 specifies SEALED as a **hard constraint, not a
large negative number**, precisely because a large negative number gets traded away
when the answer is valuable enough. That is a design commitment made on your behalf and
it should be yours. The mechanism is verified as available — the host withholds the
menu name for that tick — but the policy is not a technical question.

**If unanswered:** nothing privacy-aware can be built, and the current system discloses
by default with no accounting.

---

## OQ-6 — A local model rung?

**Ask:** Should there be an on-machine rung below the cloud rungs — worse answers, zero
disclosure, zero marginal cost — to serve questions barred by OQ-5's constraint?

**Why it matters:** it is the only candidate action for **SEALED + open-ended**
questions other than pointer-to-source. Without it that class is served by pointing at
documents or not at all.

**If unanswered:** default is no local rung, and SEALED open-ended questions get
pointer-to-source only.

---

## OQ-7 — Re-basing `lambda_usd` on the real constraint

**Ask:** Under a flat-rate plan the marginal dollar is ≈0 until the cap, at which point
it is effectively infinite. Is the binding constraint a **usage window** rather than a
dollar? Should spend be priced against that instead?

**Why it matters:** this was offered on 2026-08-28 and **declined**. It is raised once
more because the routing objective changes the stakes: under adoption framing the
imputed rate only distorted a verdict; under routing it directly determines whether the
system is *allowed to ask for help*. r28 V3 records that the $39.01 "is not money that
left an account". `lambda_usd` may also move more from metering than from any
elicitation.

**If unanswered:** the escalation decision continues to be driven by an imputed price
under a plan where that price is not paid. Declining again is a legitimate answer, and
should be recorded as a decision rather than left as a default.

---

## OQ-8 — Which rungs exist on the ladder?

**Ask:** Which concrete escalation options do you want available, and are you willing
to have the system choose among them without asking? Candidate rungs: small model /
strong model / strong model with extended sampling / ask you / a human researcher.

**Why it matters:** §3.3's ladder is the fix for "one oracle at one price". The rung
set is a product decision, and the "ask you" rung (`ask_clarify`, which exists and is
priced by `lambda_int` = 1.0, elicited) competes directly with the paid rungs.

**A data-driven method exists for the thresholds, if not for the rung set.** Zellinger &
Thomson (2025, arXiv 2501.09345), *Rational tuning of LLM cascades*, fit a **Markov-copula
model of joint calibrated confidences across stages, tunable from ~300 examples** **[S]**.
It is **not** a substitute for Bouchard's first-order conditions (`DR-DECISION-1` §4.1) —
it tunes thresholds given a chain rather than telling you the chain is the right shape —
and it assumes *calibrated* stage confidences, so it inherits A-CAL.

**If unanswered:** the ladder is specified but not instantiable.

---

## OQ-9 — Verbosity in the structured lane

**Ask:** For a quantity question, do you want the bare number, or the number with its
decomposition? For a near-boundary threshold ("over €5k?" when the truth is €5,010),
do you want "yes" or "yes — €5,010"? For a 40-element set, a list or a count plus a
characterisation?

**Why it matters:** `DR-UTILITY-1` §3.5 names these as the three residual cases where
fit-to-need survives inside the gradeable lane. The proposal is to enumerate the shape
options and let the argmax pick, which works only if each option has a defined value to
you.

**If unanswered:** the structured lane ships one form per question shape, which will be
wrong in the near-boundary and large-set cases.

---

## OQ-10 — the error cost of an *attributed* answer

**Ask:** if the system relays an external model's answer and labels it as such ("the
model says X, unverified"), and X is wrong — is that as costly to you as the system
asserting X in its own voice?

**Why it matters:** `DR-DECISION-1` §5.2 charges escalation the full `u_wrong`, on the
grounds that a delivered answer is a delivered answer. The same question now arises a
second time for `correct_premise` (§3.5), which is also charged `u_wrong` — telling the
owner their question is ill-posed when it is not. **If an attributed answer is cheaper
than an asserted one, both rows move.** That single unelicited choice is
what makes escalation lose under the elicitation-only estimate. If an attributed answer is closer to
`u_vague`, escalation clears at both gauges and OQ-0 stops being decisive for §7.1.

**If unanswered:** the most consequential term in the escalation decision stays
asserted — the exact failure OQ-0 records.
