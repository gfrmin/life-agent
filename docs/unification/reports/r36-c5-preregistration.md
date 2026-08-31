# r36 — r34's C5: the priced reading. PRE-REGISTRATION

**Committed before the run fires** (`M-3`). r34's `C5` was left OPEN by
[`r34-value-join.md`](./r34-value-join.md); this closes it.

## Why this run exists, and why now

r34's lever — `_lattice_join` binding the declared candidate identity — is **merged into
master and sitting in the deploy tree**, but the running bridge process predates it (started
08:42, merged 11:43 HKT). So an **unmeasured decide-path change is one restart away from
live**, and the run-14 precedent (*merge ≠ deploy*) plus `M-1` say it must not get there
before its measurement. The census proved the merge *correct on every firing* (C1-identity
0/5 violations, C2 5/5) but proved **nothing about any decision**, and the replay
structurally cannot: `_lattice_join` runs bridge-side behind frozen `http` exchanges.

## What this run compares, stated honestly

**Run 21 (this run) vs run 20** (`gate-20260830T012730`, PASS 0.959 / +0.515). Run 20's tree
predates **both** r33 and r34, so this run reads **two arcs together**. That is a weaker
isolation than the ladder prefers (the run-10 lesson), and it is accepted here for one
reason, stated before the run: **r33's own replay read delta ZERO** (its errored sets were
element-identical on both trees), and **r34's census names its entire firing surface as two
questions**. The combination therefore yields a *sharp* prediction rather than a muddy one —
and K3 below makes that prediction a kill.

## Frozen conjuncts

| id | criterion | kill? |
|---|---|---|
| **K1** | **Zero NEW wrong commits**, baselined on run 20's typed arm — a wrong commit is NEW iff the row was not wrong there. Class-based and prospective. | **KILL** |
| **K2** | **No named wrong-commit class worse than run 20** — the standing hard clause (`M-1`). q2-090 is a named curve-evolution wrong-leader row **and is in the lever's firing surface**, so this conjunct is the reason the run exists. | **KILL** |
| **K3** | The rows whose action differs from run 20 are a **SUBSET of {q2-027, q2-090}** — the census's complete firing surface. A row outside it moving means the change is not what the census says it is, and the census is the whole basis for shipping. | **KILL** |
| **K4** | **P(Δ > 0.05) ≥ 0.90** under the production Ū, δ/level unchanged (§6.1). | **KILL** |
| **K5** | On any firing row whose action changes, the committed leader's credence is **≥** run 20's. A merge that LOWERS a leader contradicts the coarsening argument. | **KILL** |
| **K6** | Conversions abstain→report on a gold: **recorded, not a kill.** | — |

## Registered expectation, written before the run

**PASS at ≈0.959, Δ̄ ≈ +0.515, with at most two rows changed and plausibly zero.** The
naive-merge arithmetic in r34 crossed the deployed bar p† = 0.8369 on **none** of the six
live signature rows, so **"correct but inert" remains the most likely outcome** and is an
acceptable one (the r30b precedent). A PASS with zero changed rows ships the unification on
its correctness, not on a reach claim, and the report will say so in those words.

## Consequence

`D-2`'s standing defaults, with one addition specific to this run: **on PASS the lever is
cleared for live** and the bridge is restarted deliberately rather than drifting live on the
next incidental restart. **On FAIL the lever is reverted from master**, which also removes
the restart exposure.

## Cost

Run 20's typed arm cost $0.24; the baseline arm is a recorded replay. Expected ≤ $2.
