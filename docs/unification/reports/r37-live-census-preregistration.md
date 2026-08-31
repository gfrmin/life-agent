# r37 — the live firing census: PRE-REGISTRATION

Opened by `D-2`'s FAIL branch, enacted at
[`r36-c5-reading.md`](./r36-c5-reading.md). **Committed before any `src/` change** (`M-3`).

## The one job

r36 killed r34's lever on **K3**, an attribution conjunct, for a reason that is a finding
about instruments rather than about the lever:

> The census enumerated the firing surface from **recorded wire** — m5-base cassettes frozen on
> an older tree — so it reports firings on the *recorded* trajectories, while a live run
> re-derives its own. **The census's surface is a lower bound, not an enumeration.**

r37's job is to replace that bound with a measurement: **enumerate where the value-join would
fire on a LIVE trajectory**, so a successor's K3 can be frozen against a measured surface
instead of an inferred one.

This is `M-7` one level up. r34 obeyed "read the deployed rule, never re-implement it" — and
still read it over the wrong *population*. Reading the deployed rule on recorded inputs is not
reading the deployed run.

## The instrument — a side-by-side tap, zero decide-path effect

`bridge/server._lattice_join` gains an **observation-only tap**, off by default and enabled by
one env flag:

- The **decision is always the deployed predicate's** (`_norm_value` on the current tree).
  Nothing about the argmax changes, on or off. This is the whole safety argument and it is
  pinned by a test.
- When the flag is on, the tap records, per call: the value, the candidate lattice, the
  deployed verdict `(idx, minted)`, **and the verdict the declared key WOULD give** — the
  counterfactual — to a side log outside `calibration/`.
- The log is a diagnostic stream, **recorded and never folded** (`M-14`): no `decision_id`, no
  credence, no writer into the calibration path.

One priced run with the tap on then yields the **complete live firing surface** — every call
where the two predicates disagree — for the price of a single typed arm (~$0.20), on the
reverted tree, with the lever not in force.

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **L1** | With the flag OFF, the tap is inert: the run's decisions are **byte-identical** to a run without it, and no side log is written. Verified by the m5-base replay reading its standing 288/314 with the same 26 named artefacts. | **KILL** |
| **L2** | With the flag ON, the **actions are still identical** to flag-OFF — the tap observes and never decides. Verified on the same replay. | **KILL** |
| **L3** | The live surface is a **superset** of the recorded-wire surface on the questions both cover. If a firing the cassettes found is absent live, the two instruments disagree about the deployed rule and neither can be trusted. | **KILL** |
| **L4** | The live surface is **reported with its size**, and the run fails if it is empty — the `G-3` universe clause, applied to r37's own instrument. | **KILL** |
| **L5** | Every predicate load-bearing on L1–L4 is verified **RED by mutation** before the read. | **KILL** |

## What r37 does NOT do

**It does not re-land the lever.** r37 produces a measured surface and nothing else. Re-landing
is a successor with its own pre-registration, whose K3 is frozen against **this** surface —
and which must also account for what r36 could not: the run-21 tree carried r33 and #127, so
the two unexplained rows (q2-046, q2-049) have no attributed cause. A successor that re-lands
on a tree carrying only the lever is the isolation the ladder wants, and r37's surface is the
precondition for stating its prediction.

## Registered expectation

The live surface is **larger** than the recorded one (2 questions). If it comes back equal, the
recorded-wire limitation is not what killed K3, and r36's stated cause is wrong — which would
itself be the finding, and is why L3 is a kill in both directions.

## Cost

One typed arm, ~$0.20, plus $0 replays.
