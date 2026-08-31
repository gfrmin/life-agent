# r39 — the B class (narrative inclusion): READING

Pre-registration: [`r39-b-class-preregistration.md`](./r39-b-class-preregistration.md),
committed before the instrument existed (`M-3`). Instrument: `scripts/b_class_audit.py`.
**$0. Nothing bought, no `src/` change, and — by the criteria's own frozen consequence — no
lever opens.**

## Verdict

**B is C.** The constant that kills narrative inclusion is **`u_wrong`**, the declared
exchange rate, whose break-even reliance is **0.8999** — the declared `p* = 0.90` to four
decimals. It is not `κ_att` and it is not the cell calibration. Conferral 2's candidate 2
(*"narrative inclusion calibration … a per-cell recalibration is the registered §7 path"*) is
**mis-scoped**: recalibrating cells cannot reach a threshold set by the utility gauge.
`A-3` already governs this — *"C is a dispersion problem, not a threshold problem; bar-move
levers are closed"* — and it governs B for the same reason.

## The readings

**B1 — the population, named.** 945 narrative decision rows, **every one** with
`n_proposed > 0`; **851** carry `abstain_reason = "all claims below the inclusion threshold"`;
**9** ever included a claim. 2 835 `(row, cell)` Betas recorded. Deployed Ū, read off run 23's
own gate report: `u_correct +1.0000 · u_wrong −8.9993 · κ_att +0.0518 · u_abstain 0`.

**B2 — the break-even, from the deployed rule.** Reliance **0.905713**. With `κ_att` set to
zero it is **0.899993**.

> **`κ_att` contributes +0.0057 of a 0.9057 threshold — 0.6% of it.** The other 99.4% is
> `−u_w/(1−u_w) = 8.9993/9.9993 = 0.8999`, which is the exchange rate and nothing else.

Against that, the **best integrated claim-EU over all 2 835 recorded cells is −0.9684**
(`unverifiable`, Beta(6,2), E[θ] = 0.75). **0 of 2 835 clear inclusion.**

**B3 — the three constants, separated.** Holding the other two deployed, and taking the best
cell the system ever recorded (E[θ] = 0.75):

| constant | would have to become | deployed | binds? |
|---|---:|---:|:--:|
| `κ_att` | ≤ **−1.1249** | +0.0518 | **yes** |
| `u_wrong` | ≥ **−2.7237** | −8.9993 | **yes** |
| cell `E[θ]` | ≥ **0.9057** | 0.7500 best observed | **yes** |

All three bind, but they are not equally reachable, and that is the separation. `κ_att` would
have to go **negative** — the agent paid to add claims, which is not a calibration, it is a
different objective. The cells would have to reach 0.91 when the population's honest measured
reliability is 0.50–0.75. `u_wrong` would have to soften from −9.0 to −2.7, a **3.3× change in
the owner's declared exchange rate**. Only the third is a coherent quantity to move, and moving
it is a change to the objective — §5 residue, not a lever.

**B5 — the natural experiment already in the record.** The **9** rows that ever included a
claim carry **exactly one** `utility_fold_version`, and it is **not** among the population's
three commonest. They decided under a *different utility posterior*. Change the exchange rate
and inclusion happens; hold it and nothing does. The attribution is not inferred — the system
has already run both arms on itself.

## The system is not malfunctioning

The cells are population-calibrated from the `eval_claim` stream at **0.50–0.75**: a proposed
claim is right about two-thirds of the time. At a 9:1 exchange rate a claim that is right
two-thirds of the time has **negative** expected utility. Withholding all of them is the
correct action under the stated objective.

So B is not 9 instances of a defect. It is 9 instances of *the owner's declared exchange rate
being enforced*, in a family whose evidence never reaches the bar that rate implies. It joins
C as the second face of the one open question the register already records as §5 residue: the
gauge fixes `u_abstain = 0`, so the utility model cannot represent the cost of **not**
answering, and every "the bar refused a good answer" class reduces to that.

## Two defects in this instrument, both found before the verdict

Published, per r05's standing lesson.

**(1) A composed Beta that never occurred.** The first `cell_means` returned `(max(a), max(b))`
per cell — the largest `a` from one row and the largest `b` from another, describing no
decision. Replaced by `observed_cells`, which returns only Betas a row actually wrote; the
guard pins that a composed pair is absent.

**(2) The audit priced with a function the module says is not the rule — `M-7`, seventh
instance.** B2 was frozen as *"bind `narrative._include_fn` / `narrative.include_eu`"*, and I
bound the second. `narrative.include_eu`'s own docstring says it plainly: *"This pure function
is not on the decision path."* The engine optimises the **integrated** form over the cell Beta,
which keeps the `Var(θ)·(u_c−u_w)` term — positive, so it *favours* inclusion. On the best cell
the point estimate reads **−1.1767** and the deployed rule reads **−0.9684**.

The direction of the verdict is unchanged, but the defect was not harmless: the point model
made the **9 including rows unexplainable**, and chasing that discrepancy is what exposed it.
An instrument that cannot explain the exceptions in its own population is not yet reading the
rule. Both are fixed, and B4's ladder re-run at **10/10 RED** after the fix.

## Consequence — enacted as frozen

The pre-registration's second branch, verbatim: *"If `u_wrong`'s break-even is the binding
constant → B is C, candidate 2 is mis-scoped, `A-3` already governs it, and no lever opens.
r39 publishes that, updates the register, and the queue advances to Arc C (proplang)."*

**No lever opens. The queue advances to Arc C.** `A-1`'s "levers from the Stage-4 measurement
first" is now spent: C is closed by `A-3`, norm is closed by r38 (built, measured, deployed),
and B is closed here as C's second face. What remains of the measurement's classes —
pollution (retrieval, 7), computed (4), E (1) — are not decide-layer equivalence and were
never in ruling 4's arc.
