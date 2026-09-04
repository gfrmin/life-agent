# DECISIONS — the governance decision log

**What this is.** Append-only. Every fork that [`RULINGS.md`](./RULINGS.md) does not determine,
that $0 evidence does not settle, and that is not in the §5 residue, is **decided here and
published** rather than escalated. It is the mechanism that replaces the interview (RULINGS
`D-3`).

**Why a log and not a question.** `core/utility.py` states the design commitment: *"Learning is
passive — evidence arrives from the owner's behaviour and owner-initiated elicitation; the agent
never probes preferences until the governor can price the sequential value."* Asking the owner
to break every tie is preference-probing by another name. The system's own answer to acting
under uncertainty is to decide, publish the credence, and learn from the reaction — so
governance decisions run on the same discipline as the decisions the system makes for a living.

**Reading a reaction.** **Silence is assent.** An objection reopens the entry; if it establishes
a rule it becomes a `RULINGS.md` row in the same commit. Entries land **with the
pre-registration, before the work**, so an objection arrives while it is still cheap.

**Not folded.** These reactions are evidence about governance, not about `u_wrong`. Per
RULINGS `M-14` (the r29 stream-contamination finding, applied prospectively as r33's RC-1 rider)
this stream is **never folded into the utility posterior**. It has no `decision_id`, no
credence, and no writer into `calibration/`.

**Schema.** `GD-n · date · the fork · decided · why · alternatives rejected · reaction`.

---

## GD-1 · 2026-08-31 · Arc 0's own shape

**The fork.** The owner asked to reduce reliance on their keypresses to "the absolute
irreducible minimum". Build the autonomy layer by proposing it and asking for ratification of
each piece, or build it and publish it?

**Decided.** Built and published: the register (`RULINGS.md`), this log, the consequence
defaults (`D-2`), and the readout line. No per-piece ratification.

**Why.** Asking the owner to ratify each part of a mechanism whose purpose is to stop asking is
self-defeating. The owner's instruction is itself the authority, and the plan carrying all five
pieces was approved as a whole. Everything here is reversible in one commit, and the readout
line makes it visible weekly whether the delegation is working.

**Alternatives rejected.** *Per-piece ratification* — self-defeating, as above. *A narrower
register only, deferring the log* — leaves the "what do I do with a fork the register misses?"
question unanswered, which is the case that actually generates keypresses.

**Reaction.** *(open)*

---

## GD-2 · 2026-08-31 · what measures the norm lever

**The fork.** The gate corpus cannot see r34's lever — 1 of 104 pinned questions carries the
signature, against §6.13's commit-wobble floor of 2. Buy a paired live re-ask, extend the eval
corpus first, or ship on the unification argument at $0?

**Decided.** Paired dogfood re-ask as the primary reading; the gate run demoted to a no-harm
regression whose blindness to the lever is stated up front.

**Why.** Determined by standing rules rather than preference, which is why it is logged here and
not asked: `M-2` puts $0 evidence before priced runs and then requires a measurement; `D-5`
retires budget as a consideration; and `r29-answer-shape-census` already found the gate set is a
census of the eval instrument, never of the owner's questions — so extending it would measure
the instrument again.

**Alternatives rejected.** *Extend the eval corpus first* — a corpus-construction arc ahead of
any lever, against a set r29 already characterised as unrepresentative. *$0 only* — ships a
decide-path change on argument rather than measurement, against `M-2`.

**Reaction.** Put to the owner on 2026-08-31 before this log existed; the owner took this
branch. Recorded as the last interview of its class, and as GD-2's confirmation.

---

## GD-3 · 2026-08-31 · escalating U-1 and U-2 rather than deciding them

**The fork.** The register's first census found two of conferral 1's rulings were carried to
conferral 2 and never addressed: `U-1` (the completion-audit definition, which conferral 1 said
"must be settled before the proplang ladder opens") and `U-2` (K5, the guard-layer method).
Decide them under `D-3`, or escalate?

**Decided.** **Escalate** — both are §5 residue and go to the owner, once, at the point the
queue reaches them rather than as an interruption now.

**Why.** `U-1` asks what "complete" means for this system, and `U-2` asks what standard of proof
the guard layer must meet. Both are statements about what the system is *for*, which `M-15` and
the §5 residue rule put beyond what evidence can settle. Deciding them under `D-3` would be the
autonomy layer overreaching on its first day.

**Alternatives rejected.** *Decide both under D-3* — overreach, per above. *Raise them
immediately* — `U-1` blocks Arc C, which is two places away; raising it now would interrupt r34
for a decision that is not yet due, against `A-10`'s sequencing.

**Reaction.** *(open — due before Arc C opens)*

---

## GD-4 · 2026-08-31 · reviewing PRs #130 and #131 before merging them

**The fork.** The owner's standing instruction (`D-6`) permits merging a green PR after a
positive review with no blockers. Both PRs were authored in this session. Does a self-review
satisfy "a review actually taken"?

**Decided.** Yes, but only as an adversarial pass with recorded findings — not a green-CI
rubber stamp. The review targeted the two things most likely to bite on a decide-path change
and recorded what it found:

- **`_candidate_key`'s date branch is conservative** — `_parse_date` declines ambiguous forms
  (`05/08/2019` → `None`), so no bare number or slash-date can collapse onto a date key.
- **The confident-wrong boundary holds** — values with different significant digits still
  never merge (`Ref 99887` does not join `99,887.00`).
- **The one genuine widening is the intended one** — `12345 kg` now joins `Invoice 12345` at
  the join site, which is exactly what `candidates_from` already does with that pair. The join
  site was the outlier; that is the change's whole argument, and it is recorded rather than
  glossed.

**Why not escalate.** `D-6` is explicit, all three conjuncts are met, and the residue is
changes to the objective — which this is not.

**Alternatives rejected.** *Merge on green CI alone* — `D-6` names a review as a conjunct, and
reading it as "green is enough" would weaken a standing ruling by interpretation. *Ask the
owner to review* — the instruction exists precisely to stop that.

**Reaction.** *(open)*

---

## GD-5 · 2026-08-31 · the register's own first census was wrong, and the correction is published

**The fork.** `RULINGS.md` §4 claimed `U-1` (the completion-audit definition) was wholly
unsettled and blocked Arc C. Preparing the unblocking interview showed that **`r27` (K4) had
resolved the stage map on 2026-08-28** and `ROADMAP.md` carried the resolved table. Correct the
entry silently, or publish the error?

**Decided.** Published — in the register, in `r35`'s §0, and to the owner before the interview
was put, because the wrong claim had already been reported to them.

**Why.** `M-4` forbids silently weakening a frozen claim, and the same discipline binds a claim
that turns out too strong. The failure was `M-7` in miniature and on day one, by the instrument
built to prevent it: the census read conferral 1's carry-forward and Conferral 2's silence, and
inferred the state of a third source it never opened. A register whose errors are edited out is
worth less than one whose errors are visible.

**Alternatives rejected.** *Correct in place* — leaves no record that the register can be wrong
in this specific way, which is the reusable part. *Leave it and let the rulings supersede it* —
a knowingly false row is worse than no row (`r05` ruling 1's reasoning, applied to this
register).

**Reaction.** *(open)*

---

## GD-6 · 2026-08-31 · what the completion audit reads, given `G-2` defined it

**The fork.** `G-2` defines the audit as "a $0 reconciliation of the four disagreements `r26`
recorded, read against this register". Three of the four are discharged by the rulings taken in
the same sitting. Does the audit still get written, or is it absorbed?

**Decided.** Written as its own report (`r35-completion-audit.md`), including the one
disagreement the rulings do NOT discharge — what Stage 0 consisted of — which is resolved on the
evidence: `ROADMAP.md:219` says "**this** doc-currency sweep", and the deictic makes the rider
the roadmap revision that names it, self-discharging when written.

**Why.** `G-2` freezes a consequence on the audit reading ("once it reads, Arc C opens"). A
consequence that fires on an artefact nobody wrote is a consequence that fires on nothing. It
also names what the audit does **not** close — Stage 4's question about `u_abstain = 0` — so
that "the programme is closed" is never read as "the question is answered".

**Alternatives rejected.** *Absorb it into the rulings* — leaves `G-2`'s trigger undefined.
*Reconstruct DONE item 1's wording* — would manufacture an authority no text carries; the
referent is attested and the quotation is not, so the audit records it as unrecoverable.

**Reaction.** *(open)*

## GD-7 · 2026-08-31 · r37's L1/L2 name a verifier that cannot see what they verify

**The fork.** r37's pre-registration freezes L1 and L2 — the tap is inert with the flag off,
and observes-never-decides with it on — and names **one** verifier for both: *"verified by the
m5-base replay reading its standing 288/314 with the same 26 named artefacts."*

Re-read against the artefact it names (`M-3`), that clause does not hold.
`scripts/collapse_replay.py` is hermetic and serves `/probe/deliberate` and
`/probe/corroborate` from recorded cassettes — **which is the exact fact that forced
`scripts/join_census.py` to exist** (r34 pre-registration §2b). The replay therefore never
enters `_lattice_join` at all, and cannot distinguish tap-on from tap-off at that site. As
frozen, L1 and L2 would pass **vacuously**: green for a reason unrelated to the claim.

**Decided.** The criteria are **not weakened and not re-scoped**. A second verifier is added,
blind, prospectively and in public (`M-4`), before the tap is built:

> The m5-base replay is retained as the host-side check (288/314, the same 26). It is joined by
> a **paired equivalence over the census population**: every `(value, candidates, allow_new)`
> triple recoverable from the 314 fixtures is put through `engine_join` with the flag ON and
> with it OFF, and every returned `(idx, minted)` must be **byte-identical**.

**Why.** That population is the one r34 was actually read on, so the check runs on real inputs
rather than invented ones, and it exercises the one code path the replay structurally cannot
reach. A kill criterion that cannot fail is not a kill criterion — `G-3`'s universe clause
("a guard must name the universe it checked") applied to r37's own pre-registration rather than
to its instrument.

**Alternatives rejected.** *Leave L1/L2 as frozen and note the limitation in the report* — that
is `M-4`-compliant on its face and still ships a vacuous kill; the whole point of freezing a
criterion is that it can fire. *Replace the replay verifier* — the replay does check something
real (no host-side breakage from the new import and the new config constant), and removing a
check while adding one is a re-scope, not an amendment. *Defer to the successor's
pre-registration* — the amendment must be blind, and after the read it is not.

**A note on where this came from.** r36's K3 killed r34 on a clause whose population had never
been re-read against the instrument that produced it. This is the same failure mode, caught one
step earlier because the re-read is now a step.

**Reaction.** *(open)*

## GD-8 · 2026-08-31 · whether to re-land a lever whose measured benefit is one row

**The fork.** r37 measured the value-join lever's entire effect on the 104 gate questions, on a
tree differing by the lever alone: **exactly one row, q2-027, abstain → correct report.**
§6.13's commit-wobble floor is **2**. So the lever's benefit sits *below the floor at which a
row count is a reading at all*. Does it ship?

**Decided. r38 opens and re-lands it** — under criteria frozen first, and with the benefit
published as sub-floor.

**Why.** The lever is not a tuning knob whose value is its row count; it is a **defect repair**.
`bridge/server._lattice_join` is stamped `[§3.3 · D-11/BR-2]` as M6's ONE declaration of the
value-join, and it tests identity with `_norm_value` while `candidates_from`, `render`,
`era_split`, the S2 grow join and the confirm probe all use `_candidate_key`. Two declarations
of one relation, numbered under different clauses — the thing M6 exists to forbid, surviving
because the two carry different §-numbers. It is a **monotone coarsening** (`_candidate_key`
falls back to `_norm_value`), so its risk surface is enumerable, and r37 enumerated it live.
The row count is corroboration, not the case.

**What is published alongside it, so no later reader mistakes the claim.** *The lever's
measured benefit is at or below the wobble floor.* "+1 correct row" is **not** a statistical
result and must never be quoted as one. Two independent draws (runs 21 and 22) agree on which
row and in which direction, which is what a structural change should look like; it is not a
power calculation.

**What still binds.** `M-1`'s hard clause is untouched: K1/K2 kill on any new wrong commit or
any named class made worse, and those criteria do not care how small the benefit is. If the
lever harms anything, it does not ship, defect repair or not.

**Alternatives rejected.** *Park it as measured-dormant (`A-7`'s r30b pattern)* — r30b's
interval lever was a new claim in the action set that lost the argmax; this is an existing
declaration disagreeing with itself, which dormancy does not fix. *Widen the lever until the
benefit clears the floor* — that is `B2`, scoped out at r34 for breaching the confident-wrong
boundary, and chasing a row count is the wrong reason to reopen it. *Drop it* — leaves two
declarations of candidate identity in tree, with the defect pinned live by a test that will
outlive anyone's memory of why.

**Reaction.** *(open)*

## GD-9 · 2026-08-31 · what follows the Stage-4 lever arc

**The fork.** `A-1` says *"levers from the Stage-4 measurement first, then proplang"*, while
conferral 2's ruling 4 scoped *the next arc* narrowly to the **decide-layer equivalence
problem** — C + norm, half of all classified misses. With C closed (`A-3`) and norm closed and
deployed (r38), does another Stage-4 class open a lever, or does the queue advance to Arc C?

**Decided by $0 evidence, not by preference.** r39 read the one remaining decide-layer
candidate on conferral 2's table — B, narrative inclusion, 9 instances — and it **closes as
C's second face**: the binding constant is `u_wrong`, not `κ_att` and not the cell
calibration. So the equivalence arc is spent, and **the queue advances to Arc C (proplang)**.

**Why this is not a judgement call dressed as evidence.** The consequence was frozen in r39's
pre-registration *before* the instrument existed, in both directions: a calibration finding
would have opened a successor lever under `M-1`'s hard clause; a threshold finding opens
nothing. The read came back threshold, so nothing opens. The remaining Stage-4 classes —
pollution (retrieval, 7), computed (4), E (1) — are not decide-layer equivalence and were
never inside ruling 4's arc; they remain available as their own pre-registered work whenever
evidence calls for them, which is `A-10`'s continuous-sequencing rule, not a queue position.

**Alternatives rejected.** *Open a B lever anyway* — it would have to move `κ_att` negative or
the exchange rate 3.3×, and the second is a change to the objective (§5 residue), not a lever.
*Open a pollution/retrieval arc first* — nothing rules it ahead of a gated-mandatory migration,
and `A-2` makes proplang mandatory-but-deferred, which stops being a reason to defer once the
thing it was deferred behind is finished.

**Reaction.** *(open)*

## GD-10 · 2026-08-31 · Arc C opens on preconditions, not on E1

**The fork.** `GD-9` advanced the queue to Arc C. membrane-shadow §17.6 names the re-earn path
— E1, a per-candidate posterior the engine can sharpen — so the obvious first step is E1 work.
Is it?

**Decided: no. Arc C opens on P0 (the engine, pinned and provenanced) and P1 (accrual restored,
the gap declared), and reaches E1 only after.** Recorded in
[`r40-arc-c-preconditions.md`](../reports/r40-arc-c-preconditions.md).

**Why — measured, not argued.** On this machine: **no `proplang-host` binary exists at all**;
the shadow is **disabled** (no `MEMBRANE_COMMAND` anywhere); and it **stopped accruing
2026-08-10**, twenty-one days ago, against §18's standing *"the shadow keeps accruing."* The
proplang tree has moved `1a0cea7` → `94fd4eb`. Every bar §18 freezes reads against a shadow
ledger; there is currently no engine to produce one. E1 asks filed as proplang issues would
target a binary nobody here can run, and their effect would be unmeasurable.

**What is deliberately left open.** *Why* the stream stops on 2026-08-10 is **not**
established. The tempting explanation — the production role moving to this machine — is
contradicted by the dates (the move was 2026-08-30). Recorded as an open question rather than
inferred, because inferring a cause from an adjacent fact is precisely what r36 got wrong and
r39 got wrong in a different register.

**Alternatives rejected.** *File the E1 issues now and restore the engine later* — the issues
are public and permanent (§11), and filing an engine ask you cannot measure the effect of wastes
someone else's attention, not just mine. *Rebuild the binary as part of this stocktake* —
installing an engine and re-enabling a shadow are changes to a live machine; they belong inside
P0/P1 with pins and byte-compat checks recorded, not as a side effect of looking. *Treat the
21-day hole as a nuisance and pool across it* — `M-14` and r29 both forbid it: a stream whose
generating policy changed mid-way is segmented or excluded, never silently pooled.

**Reaction.** *(open)*

## GD-11 · 2026-08-31 · the world-declaration repair is four items, and P1 moves behind item 3

**The fork.** r41 closed naming one successor — *"the world-declaration repair"* — and P1
(restoring shadow accrual) behind it. Before writing that pre-registration, `M-20` says verify
the claim it stands on. The claim was **"`hello` needs `codebooks.theta`"**, read from engine
source.

**What decided it.** [`r42`](./reports/r42-engine-door.md), $0, against the two engine binaries
r41 already built. The claim is true and incomplete: HEAD's door differs in **four** ways, and
only the first was named. Ticks now require full namespace coverage; **evidence ticks are
refused outright** for want of the writable name; and HEAD **parses the declared utility
sentence, validates it, and then decides as though it were absent** — byte-identical replies
with the utility block present and removed, `abstain` (the option-space head) under four
different `u_bar`s where arm A tracks the host prediction on all four.

**Decision.**

1. The successor's pre-registration covers **four items**, not one. Items 1–2 are
   backwards-compatible (arm A ignores `codebooks`, and accepts a full-coverage tick with a
   byte-identical reply), so they can be verified *before* the swap; items 3–4 cannot.
2. **P1 is re-sequenced behind item 3, not item 1.** Restoring accrual against HEAD would
   accrue nothing — every evidence tick is refused. Item 3 is not plumbing: an evidence tick
   that must name an act is a full experience tuple, and what act a recorded verdict is claimed
   to have been taken under is a modelling choice.
3. **Item 4 is a precondition for the §18 bars, not a curiosity.** A bar read in this state
   compares arm A's utility-driven policy against a **constant `abstain`** and books the gap to
   the migration. The whole shadow rests on the engine acting on the declared utility; measured,
   it does not. `M-18` one level up: pin what the comparison arm decides *with*, not only which
   tree it is on.
4. **Nothing is built, installed or enabled by this.** r42 is a re-scope.

**Rejected alternative — ship the one-line fix now.** Declaring `codebooks.theta` alone is
measured to yield a green handshake (`ok: true`), silently refused evidence, a belief pinned at
the prior, and a **constant `abstain` policy**. Green lights over a dead engine. The tempting
version of this is `theta: [0.5]`, which handshakes at `models: 1` and `entropy_bits: 0.0`.
That is precisely the tail-end convenience declined at the close of P0, and it is now declined
with numbers rather than on principle.

**Sharpened after the first reading.** Item 4 was characterised further at $0: `cgrid` is
eliminated as the mechanism, `chooseEU` is confirmed to be running (an empty option list would
emit no `act` key at all), and the insensitivity is **extreme** — arm B still picks `abstain`
where abstain is worth −100 and respond +25. So item 4 is not a tie-break convention or a
near-tie: on this world at HEAD the declared utility does not enter selection at all. The
mechanism is then pinned behaviourally: permuting the **menu grid** shows arm B returns the
**first grid point in every case** (abstain / respond / ask / gather as each is placed at the
head) while arm A returns `respond` throughout. So HEAD fires the option-space head — the
structural `wait` — irrespective of the declared utility, which is the policy `Host.hs`
documents for a world that declared *no* utility. Three candidate mechanisms eliminated
(`cgrid`, an empty option list, the atom codebook via `obs_arity`); the code path is not
identified, and one Haskell-level reading is the successor's first step — after which it also
decides whether to file upstream.

**Standing under.** `D-2` defaults, no keypress: this is scope, not objective. Registered
alongside it: `M-22` (read every reply, not the last one), earned by r42's own instrument.

## GD-12 · 2026-09-01 · item 4 was ours, and the clock row is the repair

**The fork.** `GD-11` made item 4 — HEAD parsing our declared utility and then deciding as
though it were absent — a **precondition for every §18 bar**, and left the code path
unidentified. r42 closed naming the successor's first call: read it at source, then decide
whether to file upstream.

**Decided: branch 1 of r43's frozen three. The defect is in our world declaration, and no
upstream issue is filed.** Recorded in
[`r43-selection-contract.md`](./reports/r43-selection-contract.md).

**What decided it, measured on both engine arms at $0.** HEAD's `Membrane.chooseEU` folds the
option list pairwise and builds **one** environment, from the *challenger*, so both sides of
every comparison read the same utility row and per-action **levels** never enter — only the
beliefs can differ. Our world's beliefs cannot: `act` is one of exactly **two** names in a
19-name namespace whose value does not move the predictive (the other is `t`), because
`handshake_decl` declares guard rows only for the indicators, and fragments enumerate over the
guard grids. Every option therefore ties and the option-space head fires — which is precisely
r42's table.

`Host.hs` routes to `chooseEU` **only when no `clock` is declared**; with one it calls
`pickWire`, the substitution route. Declaring a clock row makes arm B track the host's own
`argmax_action` on **5 of 5** cases, **three of whose winners are not the head** — so the
control r42 lacked is now in the table. Measured minimality: the **clock row alone** restores
utility-driven selection; the **act guard row** is a second, independent repair, without which
the belief can never acquire act structure.

**Why no issue is filed — the case collapsed rather than strengthened.** The engine has already
registered this exact behaviour as **`OB-24`** ("under the shipped `chooseEU` fold both sides of
every comparison are served the CHALLENGER's assignment, so action-dependent utilities degenerate
to ties"), pinned by a passing oracle row, with the substitution route named as the remedy and
the migration deliberately deferred. Filing would have reported the maintainer's own registered
obligation back to them. `GD-10` declined to file an ask whose effect could not be measured;
this is the sharper form — **an unread one wastes the same attention.**

**Also settled, and it tightens `GD-11` item 3.** The writable name may **never** appear in a
tick's features (`feature/assignment collision`, both arms), so the only satisfiable evidence
tick carries a **menu** and the fold conditions on the act the *engine* picks. A replay can pin
the act only by declaring a one-point menu grid, which a mixed-act verdict stream cannot use in
one session. Unrepaired, this composes with item 4 into a **lock**: the engine always chooses the
head, so it only ever conditions on the head, so the beliefs never acquire act structure, so the
head keeps winning. `GD-11`'s H2 is confirmed, and repairing item 4 is a precondition for item 3
being worth anything.

**Rejected alternatives.** *File anyway, to be safe* — `OB-24` makes it noise, and the register
is public and permanent. *Land the two declared rows now* — r43 makes no `src/` change by
construction; the repair search was **not** pre-named, so it carries no frozen prediction and
r44 must freeze it properly first (`M-3`). *Treat C1's wrong named act as a refutation* — its
frozen escape clause required the belief separation be **measured**, and it was: byte-identical
predictives across all four acts, 16 readouts. The mechanism the prediction came from is
confirmed; the act it named is not. Both are published (`M-4`).

**Reaction.** *(open)*

## GD-13 · 2026-09-01 · what r44 buys, what it costs, and what it leaves

**The fork.** `GD-12` said the repair is a declaration change and named four items. Building it
raised three choices the register does not determine: which theta grid, whether to accept the
clock's cost, and how much of the door to repair in one reading.

**Decided, and read at [`r44-world-declaration.md`](./reports/r44-world-declaration.md).**

1. **The grid is a declared rule, not a number.** Rungs at the measured operating rate, at every
   `argmax_action` crossing, at the recorded shadow's p05/median/p95, and at the endpoints —
   because the engine's `#19` records a false clear caused by *placement*, and a rule is the only
   thing that survives the utility posterior moving. It yields n = 8 and `models = 960` today;
   the rule is what is frozen, never the numbers. Rejected: fitting arm A's 2393 (r42: two
   enumerators, a reference and never a target) and the tempting `theta: [0.5]` (`models: 1`, an
   engine that cannot learn).
2. **The clock's cost is accepted and published, not engineered around.** `Host.hs` reaches the
   substituting chooser only through the clock, and `thinkValue` takes its preposterior branch
   whenever `batch ≥ 1`, which the wire **enforces** — so a utility that decides costs
   **297 ms per decide against 135 ms**, ≈2.2×, structurally. Rejected: leaving the clock off to
   stay fast, which is r42's measured state — a green handshake over a constant `abstain`.
3. **Items 3 and the `act` guard row are scoped OUT, to r45.** Item 3 is a modelling question
   (the act can never be a tick feature, so the engine picks what the fold conditions on) and the
   guard row is the one row r43 measured as **not** free on the control. Bundling either would put
   two levers on one reading — the r30b precedent. P1 stays blocked behind item 3, as `GD-11`
   ruled.

**W6's result is left standing rather than acted on.** The at-rung/near-rung gap grows with data
as `#19` warns, but the *near* grid ends closer to the truth, because the rate rung sits 7 × 10⁻³
from the p95 rung and the posterior spreads across the pair. Re-tuning the collision threshold to
merge them would be tuning to a result the rule was frozen to precede (`M-4`). Registered for a
successor: **the placement lever is the grid's local density, not one rung** — and at these
magnitudes no false clear is reachable on this world, which is why nothing changed.

**Found en route and deliberately not built** (`M-6`): `membrane.categorical` — the E1 stage-1
world — carries all three of the same defects, disabled today but exactly the world §17.6's
re-earn path runs on. Its menu grid is per-question, so its grid under r44's rule is per-`K`;
r45's pre-registration must say whether the two worlds share one declaration of the rule or two.

**Reaction.** *(open)*

## GD-14 · 2026-09-01 · filing the demand upstream anyway, against `GD-12`

**The fork.** `GD-12` decided **no upstream issue is filed**, and `M-23` recorded the lesson
that earned it: the engine already carried r43's finding as `OB-24`, with the remedy named and
the migration deliberately deferred, so filing would have handed the maintainer their own
obligation back. The owner directed the opposite — *"create issue for proplang anyway as it
might cancel deferral based on demand."*

**Decided: filed as [proplang#24](https://github.com/gfrmin/proplang/issues/24), labelled
`enhancement`, in the repo's own established `Demand for …` genre (#9, #11, #12, #13, #14).**
`GD-12`'s reading is untouched — r43 measured what it measured and its verdict stands. What is
superseded is only its *consequence*, and on a distinction `GD-12` did not draw.

**Why the owner is right and `GD-12` was reasoning about the wrong quantity.** `M-23` answers
"is this finding new to them?" — it was not, so a *diagnosis* issue would have been noise.
`OB-24` is not merely a record of the mechanism, though: it is a **ruled deferral**, and a
deferral is a judgement about **demand** — the one input a downstream consumer can supply that
the counterparty's register cannot derive for itself. Reading their register tells you whether
to report the defect. It tells you nothing about whether to report that someone is blocked on
its remedy. The issue is therefore framed as a demand and not a diagnosis: it asks nothing
about the ruling (it agrees with it), states our cost in measured numbers, and offers
*"confirm the boundary"* as a complete answer.

**What it carries, all measured, none of it new work.** A minimal harness-free repro built for
the filing — a five-line world whose `said@1` utility is **constant in `y`** and differs only by
action, so no belief, evidence or learning is involved: HEAD returns the menu head (`act 1`,
worth 10) clockless and the declared argmax (`act 2`, worth 100) with a clock, while the
pre-trampoline control returns `act 2` either way. Both costs from `GD-13` (297 ms vs 135 ms;
`batch: 0` verified refused as `bad hello`, so the preposterior is not opt-out-able). The
composition with **#15** — that issue names the declared-utility route as the fallback for the
learned one, and on a clockless world that fallback is closed too. And a documentation note:
§2's `menu` bullet describes substitution semantics, and only thirty-odd lines on does the
OPTIONAL `clock` bullet quietly withdraw them for the clockless case.

**Alternatives rejected.** *Hold `GD-12` and wait for the named boundary* — the owner's point is
that the boundary is not fixed, and an unstated demand cannot move it. *File a diagnosis of the
mechanism* — that is exactly what `M-23` forbids, and the issue deliberately cites `OB-24` as
settled rather than re-deriving it. *Ask for the `batch: 0` escape hatch* — recorded in the
issue as the shape we would otherwise have asked for, explicitly **not** proposed, because it
contradicts §2's availability-from-pricing law and the trampoline's termination argument, and
we are not positioned to price that against their register.

**What does not change.** `A-2` still binds: the fix is engine work, never a softened bar. r45's
scope is unchanged — the workaround is landed and working, so nothing here blocks. If the answer
is "wait for the boundary", we hold the clock and its 2.2× and record the price.

**Reaction.** *(open)*

## GD-15 · 2026-09-01 · r44 fired a registered conditional and did not discharge it

**The fork.** `r04-stocktake` §3(ii) answered the fold-depth bench's owner-question Q3 with a
conditional: *"No grid values are declared on today's wire … **if the swap discretises**, the
bench's 'sixteenths' rule applies from day one, and P3's 100× lever is avoidable by
declaration."* **`r44` discretised** — HEAD's door requires `codebooks.theta`, so the grid is no
longer optional — and the rule it froze emits crossings and quantiles at full double precision:
`0.05 0.1 0.18 0.339 0.857 0.864 0.95 0.9888888888888889`, carrying **49–56-bit denominators**.
That is the bench's own P3 regime, whose grid is the non-dyadic `{0.1,0.3,0.5,0.7,0.9}` and whose
measured rate is *"~107 bits per weight per fold vs ~4–8 for sixteenths"* — **13–100×** on how
fast a session's belief state grows. The antecedent came true and nothing discharged the
consequent, because the sentence was never read at the moment it started to bind.

**Decided: correct the register now; price the lever in r45; change no rule today.** Three
things settle it, and all three were checked rather than assumed.

1. **Depth is the multiplier, and depth is small.** The streams P1 would replay are 3 867
   decisions / 71 reactions / 6 683 shadow rows. The bench's own P1 curve reads `α_raw` **0.36 at
   10³** → 1.09 at 10⁴ → 1.47 at 3.9·10⁴: below ~10³ folds cost is `c0`-dominated and nearly
   flat. The lever is real and is very likely not yet biting.
2. **The fix contradicts a frozen rule, so it is not free.** `r44` froze *a rung **at** the
   measured operating rate* and *a crossing always survives the collision*. Snapping 0.857 to
   55/64 = 0.859375 breaks both by construction, and a rung near-but-not-at the operating rate is
   exactly engine `#19`'s false-clear hazard — which `r44`'s own W6 measured as real, with the
   gap **growing** under data (0.0014 → 0.0027 → 0.0032). **Sixteenths and placement pull
   opposite ways**; that conflict is a measurement, not a preference.
3. **`M-4` forbids the reflex, not the repair.** Applying a pre-existing, independently
   registered rule is not tuning to a result — but deciding *between two registered rules* on a
   citation, with no number for our own world, would be. So the branch that re-declares is
   available to r45 and is closed to today.

**Scoped to r45** (`M-6` — an anomaly found en route is a disclosure in its finder and an item in
its successor), which already owns P1 and the `membrane.categorical` twin whose grid is
per-question and therefore per-`K`, inheriting the same lever. r45's pre-registration must carry,
frozen before any `src/` change: the dyadic lattice, the bar, a $0 depth sweep to ~4·10³ folds on
the already-built binaries, and a decision-equality leg on the pinned 104 through
`scripts/membrane/lattice_replay.py` (which binds `theta_grid`, so it moves with the rule and
cannot silently disagree).

**Alternatives rejected.** *Snap the grid now* — a change to a frozen rule on a citation rather
than a measurement, against a clause its own reading tested. *Treat it as a new arc* — `M-6`; it
is one item in the checkpoint that already owns the rung it depends on. *Re-run the bench's
P2@10⁴* — r04 recommended against it (its Q6) and that reasoning is unchanged: our folds are
rebuilt per ask at depth ≤ ~10³, not one always-on 10⁴ session. *Say nothing until r45* — the
premise is false in the register **now**, and a false premise there is precisely what `M-20`
exists to stop.

**Registered alongside:** `M-24` — a conditional in the register is a trigger you own.

**Reaction.** *(open)*

## GD-16 · 2026-09-01 · the backfill folds pooled, against C3's letter, because C3's ground is refuted

**The fork.** r45 froze C3: *"Option 2 is admissible only if the engine's chosen act matches
the recorded act on ≥ 95% of a sample of ≥ 100 replayed decide rows. Below that it is
disqualified as a corruption and said to be one."* Measured: **0/250**. Option 2 fails its
bar by the widest margin available. But r45's A2 measured, on both arms and with the
mutation control RED, that **the act never enters the fold at all** — four pinned acts give a
byte-identical `p1`. So the criterion disqualifies option 2 *as a corruption*, and there is
no corruption: options 1 and 2 produce the same posterior over the same rows.

**Decided: the backfill folds POOLED (option 2's shape), and C3 stands recorded as FAIL.**
Both halves are on the record; neither is softened to make the other comfortable.

**Why.** Applying C3's letter would force option 1, and option 1 **cannot do P1's job**: one
session per act is one belief per act (two here — `abstain` 162, `respond` 88 under
`world.REAL_TO_MEMBRANE`), while the live shadow is a single session that must decide
against a single belief. C3's letter would therefore buy nothing real and lose the pooled
fold, on the strength of a quantity A2 proved causally inert. Pooled is also the *historical*
shape: `session.boot()` has always replayed one session with the full menu, so every row
already in `shadow.jsonl` was produced this way. Restoring accrual pooled reproduces the
recorded semantics exactly; segmenting would depart from them.

**What would reverse this.** The inertness is the whole ground, and it is contingent on the
declaration. **If r46's `act` guard row lands** — r45's A4 measured that `act` as a guard on
a *discriminating* grid, with `act` removed from the menu, makes the fold condition on it
(arm B gap +3.37 bits) — then the act stops being inert, C3's premise becomes live, and
**this decision must be re-read before any further backfill.** Recorded as a standing
condition on r46, not as a footnote.

**Alternatives rejected.** *Follow C3's letter and segment* — buys a criterion's form at the
cost of its purpose, and delivers no restored belief. *Declare C3 satisfied on the grounds
that inertness makes agreement irrelevant* — that is renegotiating a frozen bar after seeing
the number, which is the one thing pre-registration exists to prevent; C3 reads FAIL and says
so. *Take branch 2 (publish the stream as unfoldable and accrue live-only)* — false on the
measurement: the stream folds, and the C3 run folded all 250 rows to prove it.

**Reaction.** *(open)*

## GD-17 · 2026-09-01 · the fold-depth lever is measured, it bites, and the rule still does not change today

**The fork.** `GD-15` held the grid-precision lever open on three grounds and scoped it to r46.
Its **first ground is now falsified by measurement**: *"Depth is the multiplier, and depth is
small … below ~10³ folds cost is `c0`-dominated and nearly flat. The lever is real and is very
likely not yet biting."* P1 landed, the live shadow booted on a **250**-row replay, and a single
mirrored decide costs **~20 s wall / 6.8 s engine CPU** where `r44` measured **297 ms**. A false
premise standing in the register is exactly what `M-20` exists to stop, so the correction is
published whether or not the rule moves.

**What was measured, and why it attributes.** One session, one process, one box, one binary, one
declared world, folded incrementally with a decide timed at each checkpoint — sound because a
decide provably does not advance the evidence index (`session.py:157`; confirmed live, `t = 250`
across four probes). Engine **CPU** (`utime + stime`), not wall clock, because the box was at load
~14–19 on 8 cores throughout, from the owner's own work rather than the shadow's. **`r44`'s 297 ms reproduces at depth 0**, so the bench is confirmed and
**depth is the only variable that changed**.

| fold depth | decide, engine CPU | decide, wall | note |
|---|---|---|---|
| 0 | **0.280 s** | 0.449 s | `r44`'s 297 ms reproduced |
| 25 | **0.640 s** | 0.773 s | 2.3× |
| 100 | **4.440 s** | 6.526 s | 15.9× |
| 250 (live) | **6.77 s** | 18.8–21.4 s (n=4) | the deployed shadow |

**One point is missing and is disclosed rather than interpolated.** The sweep's own depth-250
checkpoint was **not reached** — the run was interrupted during the 100 → 250 fold — so the
250 row above is the *live* shadow's measurement, taken in a different process. It is the
operationally relevant number and it is a real measurement, but it is not the sweep's own
fourth point, so the sweep establishes **monotone, steep growth over 0 → 100** and the live
figure establishes the **cost now being paid**; neither on its own establishes the shape
between 100 and 250. Note the live 250 point (6.77 s) sits *below* a naive extrapolation from
100, which is a hint that growth decelerates — **a hint, not a finding**, and precisely the
quantity r46's sweep should settle.

**Decided: publish the number, correct `GD-15`'s first ground, change no rule today, and hand r46
the quantity it was told to go and find.** The other two grounds are untouched and still bind:
sixteenths contradicts two clauses `r44` froze (a rung **at** the operating rate; a crossing
survives the collision), and `M-4` still forbids choosing between two registered rules on a
citation. What has changed is that r46 no longer has to *predict* the depth at which the lever
bites — it is past, and the cost is on the table.

**The shadow stays enabled.** C9's frozen consequence is branch 1, and turning the shadow off
after it passed would be renegotiating a frozen conjunct on a cost the criterion did not price.
The cost is bounded where it matters: `submit_decide` is enqueue-only against a bounded queue and
never on the decision path, so **no user-facing reply waits on this** — the cost lands on the
shadow's own worker, and overflow is counted as drops rather than backpressure. Two operational
facts are published rather than discovered later: a bridge restart re-pays the **whole** boot fold
(~19.5 min wall / 17.5 min CPU for 250 rows) before the shadow serves anything, and both costs
grow with the streams. If either proves disruptive the rollback is three steps and restores the
recorded pre-state exactly (`M-19`): remove the installed binary, remove the
`LIFE_AGENT_MEMBRANE_COMMAND` line from the deployed `.env`, restart the bridge. Stated
here in full because the session's launcher script is a scratch artefact, not something a
later reader of this register can be sent to look for.

**Alternatives rejected.** *Snap the grid to sixteenths now* — `GD-15`'s grounds 2 and 3 are
unmoved by this measurement, and it is r46's frozen scope; acting now would be the reflex `M-4`
names. *Disable the shadow to save the CPU* — renegotiates a frozen consequence on a criterion
that passed, and P1 would be unrestored again with nothing learned. *Report the wall-clock number
alone* — it is contaminated by a load the shadow did not cause, and would have overstated the
lever by roughly 3×. *Leave `GD-15` uncorrected until r46 reads* — its first ground is now false
in the register, and `M-20` binds.

**Reaction.** *(open)*

## GD-18 · 2026-09-02 · the §18 bar's surface is declared, and a commit is outside its range

**The fork.** `r45` registered a precondition without resolving it: *"which surface a §18 bar
reads, and what that surface's distribution actually is, are now preconditions for reading
it."* `r46` leg A measured both, and the answer forces a declaration rather than a preference.

**Decided: the surface is the MAPPED one, and any bar written on it must state that a commit
is outside its range.** Three measurements settle it, all $0 and all published in
[`r46-readable-surface.md`](./reports/r46-readable-surface.md).

1. **The raw affordance is disqualified on measurement, not on taste.** All **6 654**
   action-bearing rows in the shadow ledger record `gather` (16:28 HKT, 2026-09-02) — across
   both engine arms, all four row kinds, and the whole life of the stream. `r45` measured this
   on 250 replayed rows and 4 live decides; it holds on the census. A bar reading it compares
   two constants.
2. **The mapped surface qualifies.** Over the 605 recorded `/decide` exchanges in m5-base it
   takes 2 distinct effectors, differs from the deployed daemon's act on **118 of 605**, and
   on **all 118** the engine contributed the difference (the agreement branch did not fire).
   The echo fraction is 0.636 against the 0.95 bar Branch A′ would have needed.
3. **But its commit branch has never once been reached.** The terminal act is a step
   function of `p1` with one threshold at **0.897015** — `|u_wrong|/(u_correct+|u_wrong|)`,
   sitting there because **`u_abstain = 0`**, the residue `r35` §3 records as owner-only —
   and the engine has never crossed it: **0 of 6 654 rows, max 0.8706**. The branch exists
   and would fire; nothing has reached it. The ceiling is **empirical, not structural**, and
   the two readings license different successors, which is why the distinction is drawn here
   rather than left to the looser "cannot commit".

**Why this is a decision and not just a reading.** (2) alone would license "read a §18 bar on
the mapped surface" and (3) alone would license "read no bar at all". Taken together they
license a **scoped** bar, and scoping it is a choice about what the evidence may be used for.
The scope: a §18 bar on this surface prices the **gather-versus-withhold** margin and **may
not be read as evidence about a commit** — not because the surface cannot express one, but
because its commit column is empty on every row ever recorded. A bar that omits that sentence
will be read as evidence about a decision it never observed.

**Attribution — §17.6 found the near-miss first** (*"those same ticks' engine posteriors sit
between 0.856 and 0.899"*, on 193 ticks at a bar of 0.899). What r46 adds is extent and
surface: it holds over the entire ledger, both engine arms, and on the mapped surface too. So
§17.6's *"the fix is always a sharper `p1`, never a softer bar"* is unchanged and now carries
its distance — **0.0264** at the ledger ceiling, **0.0349** in the new era.

**Alternatives rejected.** *Read a bar on the raw affordance* — it is a constant; this is the
`r43`/`GD-12` failure with a different constant substituted. *Declare no readable surface and
stop* — false, and it would have retired a surface that carries engine signal on 118 rows.
*Widen the bar to admit the commit* — §18's own clause forbids it (*"the fix is always a
sharper `p1`, never a softer bar"*), and it is `M-4`'s prohibited move besides. *Fix
`u_abstain` to move the threshold* — the residue is **owner-only** (`r35` §3, PRINCIPLES'
objective class); moving the gauge to make a measurement come out is the one thing §2's
delegation does not cover.

**Registered alongside:** `M-26` — a column's meaning can depend on the row's kind.

**Reaction.** *(open)*

## GD-19 · 2026-09-02 · the measurement-tree tags are NOT pushed — the guard is right

**The fork.** `tree/run11-minus-nullread` (`78810dd`) and `tree/run12-minus-69` (`81baf7f`)
pin the two isolation trees of the run-10 ladder. They exist locally and have never been
pushed, because the armed pre-push PII guard refuses them. This was carried for several
checkpoints as *"an owner keypress — needs `--no-verify` against the guard"*, on the
assumption that the guard was firing on already-public content.

**Measured, and the assumption is false.** A dry-run push reports **18 flagged lines across
six files**. Re-scanning the same files at `master` returns **clean**, so the content was
remediated after those commits. Line by line, the two files split cleanly:

- **`tests/test_lookup.py`** (4 hits, `passport-shape`): the same values **are** still at
  `master`, which simply carries four more `# PII-OK` markers (12 vs 8). Reviewed synthetic
  false positives, already public — pushing republishes nothing new.
- **`docs/bayesian-foundations.md`, `docs/unification/reports/r02-collapse-m0.md`,
  `r03-merge.md`, `r03a-migration.md`, `tests/test_gate_replay.py`** (14 hits): the flagged
  content is **absent from `master`**. It was deliberately removed from a public repository.

**Decided: the tags are not pushed, and the carried "owner keypress" is withdrawn — this is
not an override the owner should be asked for.** Pushing them would republish, to
`github.com/gfrmin/life-agent`, content that was taken out of it. `CLAUDE.md`'s constraint is
unconditional and names commit messages and test fixtures explicitly; a `--no-verify` here is
not a judgement call about tooling, it is the thing the constraint forbids. The guard is doing
its job, and the earlier framing — "the owner's override" — mislabelled a refusal as a
preference.

**What the tags were for is served anyway.** Their purpose is `M-11`/§6.10 pinning: naming the
tree a reading was taken on. `RULINGS.md` `M-16` already names both branches and requires them
to live in worktrees and never merge; the SHAs are added to that entry in this commit, so the
pin is durable **in the register**, which is the artefact a future session actually reads.
Durability of the objects themselves is a backup question, not a remote question, and the
repo is inside the machine's borg stream.

**Alternatives rejected.** *Push with `--no-verify`* — republishes removed PII; refused above.
*Rewrite the tagged trees to remediate them* — they are measurement trees whose whole value is
being byte-exact records of what decided a reading (`M-11`); editing them destroys the thing
they pin. *Push only `tests/test_lookup.py`'s tree* — not a thing; a tag names a whole tree.
*Leave it carried as an owner keypress* — it was never the owner's call, and leaving a
refusable action on the owner's desk invites the override.

**The second carried item closes with it, as a non-issue.** The same list carried *"the
machine hostname at commit `347ce7e`"* as an owner call. Checked rather than inherited:
`347ce7e` is already an ancestor of `master` (so already public), its commit message carries
no hostname, and **neither of this fleet's two machine names appears in any tracked file at
`master`** — `src/`, docs prose and fixtures alike. (Stated as the check that was actually
run: a scan for the two known names over `git ls-files`, not a general hostname detector.)
There is nothing to remove and nothing to decide. Recorded here so a future
session does not re-open it; had it been real, the remedy would have been a public-history
rewrite, which is why it was worth five minutes to establish that it is not.

**Registered alongside:** nothing new — this is `M-20` applied twice to inherited claims of
our own ("the guard is firing on already-public content"; "there is a hostname at `347ce7e`").
Both were carried across several checkpoints as owner keypresses; **one dry run and one grep
falsified both.** Neither was ever the owner's call.

**Reaction.** *(open)*

## GD-20 · 2026-09-02 · a bridge restart can permanently kill the shadow, and it nearly did

**The fork.** `r46` leg A merged an observation-only tap that only writes after a bridge
restart, so the deploy tree was restarted to make it live. **The restart killed the shadow**,
and the failure is the exact one `r45` C8 spent a checkpoint diagnosing: a clean-looking
service with a silently dead form.

**What happened, to the second.** The credence skin runs as a **fresh podman container per
respawn**, so each attempt starts with a cold Julia depot and precompiles from scratch.

| time | event |
|---|---|
| 16:57:51 | restart; old form dies (`membrane driver closed the wire (EOF)` — expected) |
| 16:59:57 · 17:02:58 · 17:05:58 | three respawns, each `skin process did not emit ready sentinel within 120.0s` |
| 17:08:51 | *"87 dependencies successfully precompiled in **112 seconds**"* |
| **17:08:58** | **4th respawn times out → `permanent: true`; the form is dead** |
| **17:09:01** | the skin emits `{"status":"ready"}` — **three seconds too late** |

`STARTUP_TIMEOUT = 120.0` (`core/brain.py:60`) against a measured cold start of **~122 s**
(112 s precompile + ~10 s boot, plus an image pull). `max_respawns = 3` with a 60 s backoff
exhausts the ladder in ~9 minutes while precompilation is still running, so **every** attempt
fails for the same reason and the form dies permanently. A second restart, with the depot now
warm, booted cleanly: 0 respawns, ready sentinel immediately, boot row at **17:38** — ~20 min,
matching `GD-17`'s ~19.5 min fold. The tap's first live row confirms it end to end
(`action: gather`, `real_effector: abstain`, `mapped_effector: gather`, `mapped_echo: false`,
`mapped_probe` set) — the corpus finding reproduced on the deployed path.

**Decided: publish the measurement, change no constant today, and name the hazard.** The
tempting one-line fix — raise `STARTUP_TIMEOUT` — is **refused on a real cost, not on
caution**: `core/brain.py` is the credence skin seam the **live ask path** also spawns lazily
(`bridge/server.py`: *"the credence skin spawns on first `/utility`"*), so a longer timeout
makes a genuinely-broken skin block a live ask for longer. Trading a live-path stall against
an off-path accrual, on one observation, is exactly the move `M-4` and `M-6` exist to stop.

**The remedies, named with their trade-offs so a successor need not re-derive them.**

1. **Persist the skin container's Julia depot** (a volume, in the credence repo's own
   packaging). The
   *correct* fix — it removes the cold precompile rather than tolerating it, and touches no
   timeout. Out of this repo entirely; a different repo's change.
2. **Make `STARTUP_TIMEOUT` per-caller** — long for the shadow's respawn, unchanged for the
   live seam. Right shape, needs its own pre-registration because it splits a constant two
   surfaces currently share.
3. **Raise it globally.** Cheapest, and the one with the live-path cost above. Not taken.

**The cheap protective follow-up, recommended and not built here:** nothing detects a
permanently dead form. `r45` C8 established that the shadow stayed dead **three weeks**
unnoticed. `scripts/production_readout.py` already runs weekly; a single line reading the
newest `kind: "respawn"` row for `permanent: true` would have caught both that outage and
this one. This is detection, not repair, and it is independent of all three remedies above.

**Registered alongside:** `M-27` — restarting a service is a measurement, not a formality.

**Reaction.** *(open)*

## GD-21 · 2026-09-03 · act-conditioning is real but inert for the commit ceiling, and the bar it would clear has drifted below the ceiling anyway

**The fork.** `r46` leg C (`docs/unification/reports/r46c-act-conditioning.md`, $0) asked r45's
question — can one world both condition on the act and choose it — and, with leg A's sharpened
target, whether act-conditioning lifts the `p1` ceiling over the §18 commit-pricing bar. The
frozen consequence branch 1 said: an admissible arrangement that conditions AND whose ceiling
reaches the bar on ≥1 row makes act-conditioning a **named candidate lever**.

**Measured.** The mirrored arrangement (a non-writable `act-taken` guard on the discriminating
grid, `act` kept in the menu) **does both**: it conditions (K3, the fold's `p1` swings
0.954 ↔ 0.061 under a synthetic teach, both arms) and it chooses (K4, `chosen = argmax_action`
at the reply's own `p1`). So r45 A4's *"the act-conditioned world cannot decide"* was an
artefact of collapsing `act` into the guard; the two-name arrangement dissolves it. Branch 1's
**letter is met** — the mirrored conditional ceiling (0.862257) reaches the located commit bar
(0.836894) on 180 of 250 rows.

**Decided: branch 1's letter is recorded met AND its ground refuted; act-conditioning is NOT
opened as a lever.** Both on the record, neither softened (`M-4`). Two facts refute the ground:

1. **Conditioning is causally inert for the ceiling.** The *pooled* (unconditional) ceiling
   already reaches the bar (0.862188 > 0.836894); conditioning adds **7 × 10⁻⁵** and lifts
   **0 of 250 rows** over the bar. Per-row the conditional spread from `act-taken` is median
   **1.2 × 10⁻⁵** — on the real recorded stream the historical act is near-uninformative about
   the reaction outcome, unlike the synthetic teach. Naming act-conditioning a "candidate
   lever" would be false to the measurement. This is `GD-16`'s shape: a criterion's qualifying
   quantity turns out not to carry the thing the criterion was written to detect.
2. **The bar had drifted below the ceiling.** The commit bar is not a constant: it is
   `|u_wrong| / (u_correct + |u_wrong|)` and `u_wrong` is learned from reactions (r32). The
   shadow's boot `u_bar` has run `−8.83` (bar 0.898) → `−5.94` (0.856) → `−5.13` (0.8369)
   across 20 boots; leg C reads the **live** 0.8369, r32's deployed p†. Leg A's 0.897015 was
   the **corpus fixtures**' elicited `u_bar` (`u_wrong = −8.710`), a different number. Under the
   deployed bar 180/250 rows clear the ceiling, so the ceiling is not the blocker.

**What this corrects, and what it leaves open.** Leg A's sharpened target — *"the p1
ceiling, not the affordance constant, blocks a commit-pricing bar"* — held under the corpus bar
and is **false under the deployed bar**: the fold `p1` clears it on 180/250 rows. What K5 does
**not** settle is why the mapped surface's commit column is nonetheless empty under the deployed
bar — K5 folds and probes `p1`, it does not re-run `coarse.map_action` over the live stream;
leg A's affordance explanation (`gather` 6 654/6 654) is inferred here, not re-measured. **A §18
commit-pricing bar must therefore be read under the era-matched `u_bar`, never a fixed 0.897**,
and it must settle by a mapped-surface census whether the deployed bar flips any exhausted-gather
row to a commit — with the affordance and the gauge, not the `p1` ceiling, as the standing
candidates for the blocker.

**What would reverse this.** If a future stream carried a recorded act that genuinely predicts
the reaction outcome (per-row conditional spread ≫ 10⁻⁵), conditioning would move the ceiling
and this decision re-opens under its own pre-registration. And `GD-16`'s rider is carried: act-
conditioning is now measured reachable and real, so any deployment of the mirrored declaration
inherits `GD-16`'s re-read before its first backfill — though there is no lever here to deploy.

**Not filed upstream (`M-23`).** #15 is the engine-side twin and is open; leg C's finding is
that #15's capability is **recoverable seam-side without an engine change** (a non-writable
mirror name receives evidence and conditions the outcome belief). Handed forward with its
locus, not filed as new demand.

**Alternatives rejected.** *Follow branch 1's letter and name act-conditioning a lever* —
renegotiates nothing but reports a lever that moves the ceiling by 10⁻⁵. *Declare branch 2
("ceiling stays under the bar everywhere")* — false on the measurement: the ceiling **exceeds**
the deployed bar; the honest statement is that it does so without conditioning's help. *Escalate
to the owner* — this is a $0 reading that a fork the register and evidence decide (`D-3`), not a
change to the objective.

**Registered alongside:** `M-29` — never run a git-checkout mutation harness over uncommitted
work (leg C's own §Disclosure 1: the K7 battery's per-mutation `git checkout` reverted the
uncommitted instrument rewrite before it was committed; caught by re-reading the committed tree,
re-applied, and committed before the battery re-ran).

**Reaction.** *(open)*

## GD-22 · 2026-09-03 · the two worlds share ONE grid rule — and GD-13's "per-K" was a category error

**The fork.** `GD-13` carried the obligation: *do the binary and categorical (E1 stage-1)
worlds share one declaration of r44's grid rule, or two?* — with the worry that *"[the twin's]
grid under r44's rule is per-`K`."* `r46` leg D (`docs/unification/reports/r46d-categorical-twin.md`,
$0, both arms) measured it.

**Decided: ONE rule, one declaration — the categorical world binds r44's `theta_grid(u_bar)`
unchanged, because the θ codebook is K-INDEPENDENT.** Measured on arm B (HEAD): with the SAME 8-rung
grid the model count reads 688 / 1032 / 1720 for k = 2 / 3 / 5 — exactly `344·k`, i.e. it scales
with `obs_arity` (the candidate/outcome dimension), NOT with any change to the θ grid. `GD-13`'s
"per-`K`" conflated two objects: the **menu** grid (`act_grid_cat(k)`, genuinely per-`K` and
already correct) and the **θ** codebook (K-independent — it parametrises the channel rate, keyed
on `u_bar`). There is nothing to split. This is the `GD-16` shape: the carried premise's
conclusion (one rule) survives while its stated mechanism (per-`K`, two applications) is refuted —
the twin's utility admits **no crossings at all** (`respond_j` is code-conditional, `(= y (- act
RESPOND_BASE))`, not scalar-`p1`-linear), so `argmax_crossings` cannot even be applied to it and a
per-`K` θ grid was never on the table.

**r45's three source claims measured true, and one is broader than r45 named.** (1) Arm B cannot
handshake the twin as-is — **confirmed** (`bad hello`; codebooks is the single item that clears it);
but arm A handshakes it with no codebooks at all, so "cannot handshake at HEAD" is a property of
**arm B**, not the twin — r45's phrasing corrected. (2) The clock defect is real — without it the
twin fires the menu head over a constant act; with it, selection tracks the utility (gather) — r43 /
`OB-24` transferred whole. (3) The evidence-tick defect is real and has **two halves** on arm B: the
menu-less `act` (r45's naming) AND the **dormant indicator names** `cat_features` omits on its
"dormancy is free" assumption — the same `shadow_features` defect r45 A4/B5 fixed for the binary
world, still live in the twin. The full-coverage repair clears arm B and is a byte-identical no-op
on arm A.

**What a categorical enablement (E1 / §17.6) must carry — SPECIFIED, not built.** Four items:
(1) `codebooks.theta = theta_grid(u_bar)` unchanged; (2) a `clock` row; (3) a menu-bearing tick;
(4) full indicator coverage on every tick (`cat_features` must emit every declared name, dormant
0.0). Leg D builds and enables **none** of them — the categorical world stays env-disabled, no
`src/` change, nothing deployed. `M-1` is not engaged; `GD-13`'s rider is carried (an enabled twin
inherits `GD-16`'s re-read before its first backfill).

**Alternatives rejected.** *Declare two rules* — false on the measurement: the twin binds the
binary grid unchanged and its per-`K` growth is `obs_arity`, not θ. *Build the four fixes and enable
the twin here* — that is E1 / §17.6's job under its own pre-registration; bundling a build into a
$0 diagnosis is the r30b error. *Escalate to the owner* — a $0 reading a fork the register and
evidence decide (`D-3`), not a change to the objective.

**Disclosed (both fixed before any verdict, `r05`):** the instrument's first draft reused one
session across handshakes (a handshake is once-per-session — the reuse read as a spurious refusal),
and first sent `cat_features` (dormant-omitting, so the arm-B decide was refused, nulling K5). Both
caught by the run's own output, fixed, and the instrument re-committed before the K7 battery
(`M-29`).

**Reaction.** *(open)*

## GD-23 · 2026-09-03 · the E1 design doc is salvaged, not rebased — and six of its eight engine dependencies have closed

**The fork.** `GD-10`'s ladder reaches §17.6's E1 re-earn after `r46`. Its governing design —
`docs/candidates/e1-categorical-outcome.md`, owner-approved 2026-07-21 and named as governing
by `docs/membrane-shadow.md` §15 — **did not exist on master**: it was stranded on
`feat/e1-design`, leaving §15's link broken since the branch was paused. How to recover it:
salvage the file, or rebase/restart the branch?

**Decided: salvage the doc onto master with a third dated re-ground section, and retire the
branch.** `feat/e1-design` sat 2 commits ahead and **521 behind**, and both of its commits are
that one file — the branch's only unique bytes are the doc itself. Rebasing 521 commits to
carry one document buys nothing a `git show` does not; restarting the design discards an
owner-approved artefact for staleness that is enumerable and can be stated in place, which is
what the doc's own dated-re-ground convention exists for. The branch is deleted (local and
origin) with its content fully on master. Preservation is exact: §§1–6 are byte-identical to
the approved 2026-07-21 record (verified by diff) and §7 states what moved under it.

**The retired branch's provenance, pinned before the ref goes** — `M-16`'s discipline: the two
commits were never merged, so deleting the ref makes them unreachable even though their content
is on master. `451f940` *docs(e1): categorical-outcome deliberation doc — paused for pixel6
conferral* (2026-07-20); `ac4f8c2` *docs(e1): re-ground against proplang HEAD 1a0cea7*
(2026-07-21). **Only `feat/e1-design` is retired under this decision.** The repo's other
unmerged branches are deliberately left alone: several carry commits that are not on master and
may be the measurement trees `GD-19` kept unpushed and `M-16` pins, and a branch ref costs
nothing beside destroying a pinned reference.

**The re-ground's own finding: §3's "not landed" list is materially stale.** Read live
(read-only `gh`, the proplang repo is never edited from here), six of the eight named issues
have closed, three of them load-bearing. **#20** (per-code readout) **shipped** — and,
checked rather than assumed (`M-7`, one $0 probe on the deployed arm B binary), it is **live
here**: every categorical reply carries `p0`, `argmax_code`, `p_argmax`, `p_codes[]` and
`entropy_bits`. So §16 finding 5's "R-D23 cap-binding is UNOBSERVABLE" is answerable at last
(`p0` *is* P(y=0)), and §4.4's named observability gap closes. **#21** (the
null-mass cap) closed at the `OB-19` heir boundary, the minority-cell tie broken by declared
`breadth` pairs. **#19** closed with the θ ceiling **changing owner rather than dissolving** —
θ is now REQUIRED hello data priced by mention mass (finiteness remains), which is precisely
why leg D's item 1 exists; read under the deployed boot Ū, our declared grid's top rung is
**0.990634**, neither the doc's engine-frozen 0.9 nor the 0.95 endpoint. And **#11** closed
`OB-12` as DISCHARGED with increment **B out on measurement** (`n_inv = 0`) — while naming the
one thing that could re-open it, a second verdict source. This repo **has one built and
dormant**: `core/claude_verdicts.py` (membrane-shadow §17), 180 verdicts, **none written since
2026-07-22** — a supply as code and one fold, not as a running stream, so re-opening B means
restarting and pricing it, not pointing at the file. §4.1's bad-verdict exclusion stands, and
the demand would be ours to file rather than theirs to derive (`M-23`; `GD-14`'s rider).
**#10** also closed against our stated position: it ruled **bounded option 3** — K at tick 0
with a **reserved unallocated tail**, priced from tick 0 — where §5.4(c) had said the
bounded-reserved-tail "is not needed on our account". Session-per-question is unaffected; the
tail's pricing is a cost `r47` must declare deliberately.

**What is deliberately NOT concluded.** Whether §16 finding 3's gather binder still binds. Two
of its three terms have moved (the ceiling and the Ū) while `r45`'s C3 measured the pathology
standing in the binary world at v2; the categorical crossing needs the engine under today's Ū.
That is `r48`'s measurement, and this decision records it as open in both directions rather
than inferring it from arithmetic — §17.6's own lesson about a Ū that moved under a reading.

**Consequence.** Docs-only; no `src/` change, nothing deployed, `M-1` not engaged. The forward
rungs are published in `ROADMAP.md` 3h and `CLAUDE.md`: **r47** (the four-item enablement at
HEAD, pre-registered, shadow-only) → **r48** (the re-earn measurement, replay-first) → the
**§18 bar read** (priced, own pre-registration). A `D-3` fork — the register and $0 evidence
decide it, no objective changes.

**Reaction.** *(open)*

## GD-24 · 2026-09-03 · build the enablement before measuring the binder — and the categorical world now speaks the enabled wire

**The fork.** `GD-23` opened §17.6's E1 re-earn with two rungs published: `r47` (land `GD-22`'s
four-item enablement) then `r48` (measure the re-earn). The cheaper-looking alternative is the
reverse — measure the binder first on an instrument, and build only if it has loosened, so a
refused reading costs no `src/` change. Which order?

**Decided: BUILD FIRST, on two registered lessons, and the reason is frozen in the
pre-registration rather than argued after the fact.** `M-7` — a census must read the deployed
rule end to end and never re-implement the constant it prices; four instances, one of which
flipped a verdict at a frozen bar. An instrument that re-implemented the episode (session
lifecycle, t-convention, timeout bound, act decoding) to price the binder would be exactly that
trap, and the binder is an argmax over utility rows the episode itself assembles. And `r30b` —
a lever built only in-process is invisible to the measurement that matters and absent from the
deployed path. So the four items land in `categorical.py`, the ONE declaration the shadow
supervisor binds, and `r48` measures through it.

**`r47` is READ and all ten frozen criteria PASS** (`docs/unification/reports/r47-categorical-enablement.md`,
$0). Arm B (HEAD) accepts the deployed episode end to end at k ∈ {2,3,5} — `models` 688 / 1032 /
1720, reproducing leg D's `344·k` exactly — while the pre-enablement episode is refused at the
handshake (`bad hello`); arm A still completes; the binary world is byte-untouched, the shared
objects BOUND rather than copied; 4/4 mutations RED. **Nothing is deployed or enabled**: the
world stays env-disabled and byte-inert, and `M-1` is not engaged.

**Two corrections the run made, recorded because they are the useful part.** A blind prediction
was **refuted**: it named which *tick* item would bite first, but arm B refuses at the
**handshake**, so no tick is sent and neither tick item can bite — codebooks gates everything.
And a test drafted for this build **asserted an invented requirement** (that the clock name must
be a namespace member); an existing assertion refuted it against the deployed binary world,
which keeps `think` out of its 19-name namespace in the exact shape `r44` verified at arm B
across 59 battery cases. `M-7` in test form, caught by the suite that already existed. The
namespace change was reverted and the test now pins the deployed shape on both worlds.

**Consequence.** `r48` opens under its own pre-registration (`M-3`) and measures through the
deployed runner: does `respond_j` clear its bars under today's Ū, and what does §16 finding 4's
minute-scale episode cost demand as a K-cap or episode budget **before** any live enablement.
Every act observed during `r47` was `gather`; under criterion C9 that is a **disclosure for
`r48`, not a finding here**. A `D-3` fork — the register and $0 evidence decide it, no objective
change.

**Reaction.** *(open)*

## GD-25 · 2026-09-04 · the E1 re-earn does not clear — and the KILL that fired names a cost defect, not a build defect

**The fork.** `r48`'s pre-registration froze nine criteria with **J1 as a KILL** and three
consequence branches. Two branches fired at once: J1 (three of 129 summaries returned no
action) and the predicted no-flip branch. A KILL whose stated ground is refuted by the same
measurement that fired it is not self-executing, and the register does determine it — `GD-16`
settled this exact shape (letter met, ground refuted) for C3. A `D-3` fork: register + $0
evidence decide it, no objective change, nothing escalated.

**The decision.** **J1 stands as fired and is not reinterpreted.** Its ground —
*"`r47`'s enablement is not exercised by the real corpus"* — is published as **refuted**: 126
episodes handshook, folded and returned a declared action on the deployed enabled world,
covering **2 009 of 2 012 recorded rows (99.85%)**. The KILL's mandated re-read of `r47` is
performed and its finding is the opposite of the guess: **the enablement is sound; the episode
budget is unbounded.** Nothing the criterion would have gated is taken — and nothing was
pending, since J9 already forbade every adoption this checkpoint could have made.

**The reading.** **The E1 re-earn is NOT cleared on this ledger under this Ū.** `gather` on all
126 completed replay episodes and on all 55 sweep steps (k ∈ {1,2,3,5,10} × 11 evidence depths),
no flip anywhere. Forty observations reach `p_argmax` **0.98348** against a necessary bar of
**0.99063** — a gap of **0.00716**, closed **14.3×** from §16's era (0.8918 vs 0.9942) and still
open. The sharpening is **K-independent** to 16 digits; only the zero-evidence prior (≈1/(k+1))
separates the curves. Eleven summaries clear the **vs-abstain** bar 0.836894 — nine of them the
degenerate k=1 — and every one still chose `gather`. §17.6's rule binds unchanged: **a sharper
`p1` or an engine-side change (#15 / E3), never a softer bar**, and this checkpoint proposes
neither.

**Three corrections, all published rather than absorbed.**

1. **§16 finding 3's *by-construction* clause is VOID** (`M-30`). #19 handed us the θ ceiling
   and `r46` leg B's 2⁻²⁰ lattice snap rounded the decisive rung **up**, so the ceiling
   (0.9906339645385742) now sits **1.2×10⁻⁸ above** the bar (0.9906339522695138) rather than
   ~0.09 below it. `respond_j` is no longer structurally excluded — it is excluded by a window
   1.2×10⁻⁸ wide. Leg B's own verification was honest and complete on the rows it checked (428
   summaries, zero differing actions); the boundary it moved is one no episode visits. Finding
   3's **primary** attribution — the deliberately-overvalued information row — stands, and is
   now empirical rather than analytic.
2. **Blind prediction 4 is REFUTED.** It expected arm B *faster* than arm A on a 4.65× smaller
   model space; arm B is **2.3× to 145× slower**, with median latency scaling as **~k⁴** while
   `models` is linear in k. The model population is not the cost driver. A mechanism is named
   (`r44`'s clock forces a preposterior over (3+k) acts × (k+1) atoms × 344k models) and
   explicitly **not measured** here.
3. **§16 finding 5 is answered** — #20's readout makes `p0` observable, and R-D23's `1/(K−1)`
   cap shows **zero violations** across 113 rows, tightening monotonically with k (0.26 of the
   cap at k=2 → 0.82 at k=11) without ever binding.

**Consequence.** §16 finding 4's owed **K-cap now has a number: k ≤ 3**, the largest cap under
which every observed episode finishes inside production's 20 s `cat_timeout_s` — covering
**74.3%** of recorded traffic, with the other 25.7% requiring a *named* skip. It is a
**recommendation and a precondition**, not an enablement: nothing is deployed, the world stays
env-gated OFF and byte-inert, no `src/` change is made, and `M-1` is not engaged. The **§18
bars gain two preconditions** on top of the four already published — (a) no bar may be read on a
world whose episode budget is unbounded, and (b) the categorical commit surface is empty for the
**same** reason the binary one is, `gather` dominating rather than an insufficient `p1`. Building
the cap, and any move on #15 / E3, each need their own pre-registration.

**Reaction.** *(open)*
