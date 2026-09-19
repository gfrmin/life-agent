# r36 — r34's C5: the reading. **FAIL on K3**, and the lever is reverted

Pre-registration: [`r36-c5-preregistration.md`](./r36-c5-preregistration.md), frozen before the
run fired. Run 21 = `gate-20260831T131641`, elapsed 1153.6s, typed spend **$0.19**.

## Verdict

| id | criterion | reading | |
|---|---|---|---|
| **K1** | zero NEW wrong commits vs run 20 | **0** — all three changed rows are abstain→report and **correct** | pass |
| **K2** | no named wrong-commit class worse | q2-090 unchanged (abstain both runs); no class worse | pass |
| **K3** | changed rows ⊆ {q2-027, q2-090} | **q2-046 and q2-049 also moved** | **FAIL — KILL** |
| **K4** | P(Δ>0.05) ≥ 0.90 | **0.969**, Δ̄ **+0.544** [+0.106, +1.029] — better than run 20's 0.959/+0.515 | pass |
| **K5** | leader ≥ run 20's on firing rows | q2-027 0.346 → 0.863 | pass |
| **K6** | conversions (recorded) | **3**, all correct | — |

**The run PASSES the gate and FAILS its own attribution conjunct.** Under `D-2` that is a FAIL:
the lever is reverted from the deploy path, this reading is published, and a successor
pre-registration opens.

## The lever is demonstrated — on exactly the row it was built for

q2-027's lattice in run 20 carried **two atoms at one declared key**:

| declared key | credence |
|---|---|
| `35814` | 0.346 |
| `35814` | 0.146 |
| `35814311443` | 0.104 |
| `3582008` | 0.104 |

In run 21 the duplicate is gone (k 4 → 3, no duplicate key), the leader reads **0.863** — across
the deployed bar p† = 0.8369 — and the answer is **correct**. That is the merge the census
predicted, doing the thing the arc was opened to do, priced and graded.

**And it is not enough.** K3 asked whether the census's firing surface was the *complete* account
of what the change does. It is not.

## Why K3 failed, and what it caught

The census enumerated the firing surface from **recorded wire** — the m5-base cassettes, frozen
on an older tree. It therefore reports the firings on the **recorded trajectories**, and a live
run re-derives its own. **The census's surface is a lower bound, not an enumeration**, and
nothing in r34 said so because r34 did not know it.

The two extra rows carry **no duplicate-key signature** in run 20 (q2-046 k=1; q2-049 k=4, all
distinct keys), so the lever cannot be what moved them. What is visible in the record: the
deliberate edge fired **38/104** in run 21 against **42/104** in run 20, and both rows lost
observations (q2-046 n_obs 6→5; q2-049 11→8) while their leaders rose. That is consistent with
fewer minted competitors, and with §6.13's standing wobble — but **this run cannot attribute it**,
because its tree carries r33 and #127 as well as r34. The pre-registration disclosed that
weakness before firing; K3 is the conjunct that made the disclosure bite instead of sliding by.

**No re-reading of K3 is offered.** It was frozen as a kill, two rows outside the set moved, and
a favourable headline is exactly the circumstance in which a frozen criterion must not be
renegotiated (`M-4`). r15's ruling stands as the precedent: a FAIL branch paying out is a
pre-registration working, not a setback.

## Enacted

- **The lever is reverted from master.** This also closes the exposure r36 opened on: the change
  was sitting in the deploy tree while the running bridge predated it, one restart from going
  live unmeasured. It is now out of the deploy path, and the stack restarts on a tree without it.
- The census (`scripts/join_census.py`), its tests and both reports **stay in tree** — the
  instrument is sound for what it measures, and what it measures is now documented as a bound.
- **r37 opens** with the successor's one job: a census that enumerates the firing surface **on
  the live trajectory** rather than on recorded wire, so K3's successor can be answered before a
  run rather than by one.

## Disclosed

1. **The run's tree carried three arcs** (r33, #127, r34). Disclosed in the pre-registration and
   accepted there; it is why K3 could fail without naming a cause.
2. **Three changed rows against a §6.13 wobble floor of 2** — the margin over the floor is one
   row, so even the direction of the two unexplained rows is weakly held.
3. **The live stack was stopped for the run** (it held the catalogue write-lock; a read-only run
   is VOID, the run-19 lesson) and restarted afterwards on the reverted tree.
