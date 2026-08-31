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
