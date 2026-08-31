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
