# r32 — the commit-bar reading: RESULTS

**VERDICT: PRICED.** Criteria, sites and the three-branch consequence were frozen in
[`r32-bar-reading-preregistration.md`](./r32-bar-reading-preregistration.md) and committed
(PR #125) before the instrument existed. Instrument: `scripts/bar_audit.py`, pinned by
`tests/test_bar_audit.py` (16 tests) with every load-bearing predicate verified RED by
mutation before the read was believed. **$0** — no ask was re-run, nothing was bought,
nothing was built.

## C1 — reproduction: 3/3 on all three conjuncts

Each boundary row re-priced from its own recorded posterior, through the deployed rule, under
the utility posterior folded over exactly the evidence that existed when the row was written.

| leader credence | recorded | reproduced | recorded EU | reproduced EU | fold version |
|---:|---|---|---:|---:|---|
| 0.9432 | report | report | +0.615331 | +0.615331 | MATCH |
| **0.8747** | **report** | **report** | +0.152321 | +0.152321 | MATCH |
| 0.8282 | abstain | abstain | +0.000000 | +0.000000 | MATCH |

The fold-version hash matching on 3/3 is what makes this a reading rather than an estimate:
the instrument is holding the *same* Ū that priced the row, not a reconstruction of one.

## C3 — the empirical bar: p† = 0.8522, and all three rows are on the right side of it

The deployed regret latent at those rows is **u_wrong = −5.7673** against a gauge of
u_correct = +1, u_abstain = 0. Chow's rule at that trade-off puts the indifference point at
**p† = 0.8522**, not 0.90. A report at 0.8747 is 0.022 above the deployed bar, not 0.025
below a real one.

## C2 — every attenuation candidate named in advance, and refuted

| candidate | reading |
|---|---|
| an r30 units-lever scale attenuating regret | **NONE opted in** — so `shaped_u_bar` is the identity for *every* answer shape, which closes this route whatever shape the rows carried |
| a scoped substitution winning the argmax | **NO** — the winner is `report_j`, not `report_scoped_j` |
| a fold-version mismatch | **NO** — 3/3 match |
| a defaulted latent | **NONE** — the rows' `defaulted` lists are empty |

Nothing attenuates the declared regret term. The 0.875 report is **priced, not leaked.**

## The finding: the bar moved, and the reaction stream is what moved it

The same deployed fold over four nested evidence sets:

| evidence | u_wrong | p† | n |
|---|---:|---:|---:|
| model prior only | −9.0000 | **0.9000** | 0 |
| + the owner's elicitations | −8.9993 | 0.9000 | 5 |
| + reactions, as the rows were priced | −5.7673 | **0.8522** | 49 |
| + reactions, today | −5.1310 | **0.8369** | 55 |

The declared 10:1 exchange rate reproduces **exactly** 0.9000 at the prior — the docstring's
"today's uniform 0.90 bar" is right about the *model* and stale about the *deployment*. The
elicitations move it by 0.0007. **50 of the 55 folded events are reactions**, and they are the
whole movement.

This is the §4.4 reaction loop working as designed — utility is a learned belief about the
owner, and "you should have answered" is precisely the evidence that lowers regret. But it has
a consequence the measurement did not anticipate: **the exit measurement moved the bar it was
measuring.** The class ledger was collected under a bar that fell from 0.900 to 0.837 while it
was being collected, and it fell because dogfood reacts `bad` to silence far more often than
`good` (round 8 alone: six bad, two good). The drift is monotone by construction, and its only
brake is a wrong commit — which has not happened in 69 asks. **Registered as a standing risk,
not a defect.**

## What the drift bought, and what it did not

Census of the deployed decision log since 2026-08-29: **152 readable lookup rows** (82 report /
70 abstain). Four sit in the band the drift opened — admitted by p† = 0.8522, refused by the
declared 0.90:

| leader | action | verdict |
|---:|---|---|
| 0.8677 | report | good |
| 0.8747 | report | good |
| 0.8925 | report | good |
| 0.8981 | report | unreacted |

**Zero bad verdicts among them.** The bar's fall bought four answers and cost no known wrong
commit.

**And this resolves the C question.** Among the window's 70 abstained rows the *highest* leader
credence is **0.8282** — below p†, so the bar is not sitting on top of a queue of nearly-good
answers. The median abstained leader is **0.3688**, and only **2 of 70** sit within 0.05 below
the bar. So a bar move is an upper bound of ~2 rescues, while the mass of the abstain
population is nowhere near any bar in the argument.

**C is a dispersion problem, not a threshold problem** — which is the norm class's story
arrived at from the other side. Merging split spellings raises a leader; lowering the bar does
not reach where the leaders actually are.

## Consequence, enacted per the frozen C6

- **PRICED** → C's 13 instances are the bar working as declared. Conferral 2's ruling 2
  resolves: **C gets no lever**, and the question was a preference question whose premise is
  now measured — the deployed bar is *already* more permissive than the declared one, and the
  C population does not live near either bar.
- **p† = 0.8522** (0.8369 today) is published as the empirical bar.
- **Nothing was built.** No `src/` change. The round-8 record is untouched.

## Deviations and defects, disclosed

1. **The pre-registration contradicts itself.** Its scope line says "no `src/` change is in
   scope"; its C6 PRICED branch says the stale docstring "is corrected". Conservative branch
   taken — **no `src/` change was made under r32** — and the docstring correction
   (`core/decide.shaped_u_bar`, which calls 0.90 "today's" bar when today's bar is 0.8369) is
   **queued with conferral 2's ruling-3 work**, not smuggled in here. This is the third
   instance of the standing lesson that a frozen clause must be re-read against the artefact it
   names before it is applied.
2. **The instrument computes one thing host-side**: the expectation over a tabular preference,
   which the engine would otherwise do. Every *constant* is imported from `src`. The
   re-implementation cannot pass silently wrong because C1 requires the reproduced EU to equal
   the recorded `predicted_eu` — it does, on 3/3, to full recorded precision.
3. **The census window is by date, not by round.** It is the deployed log since 2026-08-29 and
   includes owner traffic outside the dogfood rounds; the measurement's 69 asks are a subset.
   Stated as what it is rather than narrowed to the rounds, because the bar question is about
   the deployment, not the instrument.
4. **One band row is unreacted**, so "zero bad among four" rests on three verdicts and one
   silence.
