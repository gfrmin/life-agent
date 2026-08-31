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

---

## Amendment 1 — L1/L2's verifier, added blind before the build (2026-08-31)

Recorded in full at [`DECISIONS.md` `GD-7`](../DECISIONS.md). **The criteria above are
unchanged**; what follows is added to their verification, prospectively and in public (`M-4`),
before any `src/` change.

L1 and L2 name the m5-base replay as their verifier. Re-read against the artefact it names
(`M-3`), `scripts/collapse_replay.py` is hermetic and serves `/probe/deliberate` and
`/probe/corroborate` from cassettes — the very fact that forced `scripts/join_census.py` to
exist — so **it never enters `_lattice_join` and cannot distinguish tap-on from tap-off there.**
As frozen, L1/L2 would pass vacuously.

> **Added verifier (L1, L2).** The m5-base replay is retained as the host-side check (288/314,
> the same 26 named artefacts). It is joined by a **paired equivalence over the census
> population**: every `(value, candidates, allow_new)` triple recoverable from the 314 fixtures
> is put through `engine_join` with the flag ON and with it OFF, and every returned
> `(idx, minted)` must be **byte-identical**. The size of that population is reported with the
> result, and an empty population fails the check (`G-3`).

## Amendment 2 — the isolation arm, declared before the run (2026-08-31)

r37's priced run fires on the **reverted** tree, which is run 21's tree minus the lever **and
nothing else** — r33 and #127 are in both. It is therefore also the isolation arm run 21 could
not provide, at no additional cost, and the following is registered **before** it fires:

- **If q2-046 and q2-049 read as they did in run 21**, the lever did not move them; K3's
  failure was the recorded-wire census's blindness, as `r36-c5-reading.md` states.
- **If either moves back to its run-20 reading**, the lever *did* move it and r36's stated
  cause is incomplete. That is a finding against r36, published as such.

This is a **registered expectation, not a criterion** — it adds no kill to L1–L5. It is
declared here so the successor's K3 can cite an attribution rather than an inference.
