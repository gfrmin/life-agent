# r46 leg B — the grid's precision: PRE-REGISTRATION

`GD-15` registered the fork and scoped it forward; `GD-17` measured its first ground false and
handed the quantity on. This leg discharges it. **Committed before any `src/` change**
(`M-3`).

## Disclosure — the mechanism probe, run BEFORE any criterion below was written

Stated first so it cannot be tuned to. All of it is $0, on the deployed binary
(`71998f65…`, arm B), through the deployed `MembraneSession`/`MembraneClient`/`handshake_decl`
(`M-7` — the grid was varied by patching `world.theta_grid`, never by re-spelling the wire).

**1. The deployed grid is entirely non-dyadic.** On the recorded `u_bar`: `n = 8`,
`models = n(17n−16) = 960` — matching the live boot row exactly. Read as exact rationals from
their decimal spellings, every value carries a factor of 5: `0.05 = 1/20`, `0.18 = 9/50`,
`0.339 = 339/1000`, `0.857 = 857/1000`, and the two crossings are full-precision doubles.
Not one is a dyadic rational.

**2. Fold cost at depth 60, identical `n` and `models`, two independent reps:**

| grid | rep 1 | rep 2 | JSON chars | max displacement |
|---|---:|---:|---:|---:|
| **deployed (mixed)** | **24.88 s** | **25.16 s** | 81 | — |
| dyadic 2⁻⁴ | 6.90 s | 6.92 s | 59 | 3.1 × 10⁻² |
| dyadic 2⁻⁶ | 7.59 s | 7.88 s | 71 | 7.8 × 10⁻³ |
| dyadic 2⁻⁸ | 8.52 s | 8.96 s | 95 | 2.0 × 10⁻³ |
| dyadic 2⁻¹¹ | 9.50 s | 10.03 s | 114 | 2.4 × 10⁻⁴ |
| dyadic 2⁻¹⁴ | 10.15 s | 9.74 s | 135 | 3.1 × 10⁻⁵ |

**Every dyadic grid is 2.5–3.6× cheaper than the deployed one**, reproducibly. Within the
dyadic family cost grows mildly with resolution (6.9 → ~10 s from 2⁻⁴ to 2⁻¹⁴); the deployed
grid sits far off that trend.

**3. It is not wire size, and the numbers say so in the wrong direction.** The *shortest*
JSON among earlier variants (all values at 3 dp, 53 chars) was the **slowest** measured
(25.9 s), and the 135-char 2⁻¹⁴ grid is 2.5× faster. Cost tracks **dyadic representability**,
not characters — the signature of exact rational arithmetic, where a denominator carrying a
factor of 5 compounds under repeated conditioning and a power of two does not.

**4. What this does and does not do to `GD-15`'s ground 2.** Ground 2 is that sixteenths
contradict two clauses `r44` froze — a rung **at** the operating rate, and a crossing
surviving the collision — and reintroduce `#19`'s placement hazard. **A first draft of this
pre-registration argued the conflict dissolves because a 2⁻¹¹ snap moves every value by less
than the rule's own `_GRID_COLLISION` of 5 × 10⁻⁴. That argument is wrong and is recorded
here rather than deleted:** the collision threshold answers *"are these two rungs one rung?"*,
not *"is this rung at the crossing?"*, and `r44` amendment 1 admitted crossings at **full
precision** precisely because *"a threshold rounded to 3 dp is a rung near the crossing rather
than at it"*. Any snap makes every rung near-but-not-at. What is true is narrower and must be
**measured, not extrapolated**: the displacement is 29× smaller at 2⁻¹¹ (2.4 × 10⁻⁴) and 230×
smaller at 2⁻¹⁴ (3.1 × 10⁻⁵) than the 7 × 10⁻³ displacement `W6` actually tested, and `W6`
found even that produced only a 3.2 × 10⁻³ `p1` gap with *"no false clear reachable on this
world at this data volume"*. But `W6` moved **one** rung; a snap moves **all eight**, and
`W6`'s own conclusion was that *"the placement lever is the grid's local density, not one
rung"*. **So the effect of a whole-grid snap on local density is exactly what this leg has to
measure, and no ground-2 relief is claimed in advance.**

## The one job

**Price the grid's precision on this world, and decide whether to re-declare it — on a
measured `p1` displacement and a decision-equality read, never on the speedup alone.**

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **T1** | **The speedup reproduces.** At identical `n` and `models`, a dyadic grid folds at **≤ 0.5×** the deployed grid's engine CPU, on ≥ 2 independent reps at ≥ 2 depths. Engine CPU (`utime+stime`), never wall clock — the box is loaded (`GD-17`'s rule). | **KILL** |
| **T2** | **The depth sweep reaches 250**, the checkpoint `GD-17` was interrupted before and explicitly handed forward, and the ratio is reported **at each depth** — the claim is about the ratio's behaviour with depth, not one point. | **KILL** |
| **T3** | **Grid identity is preserved**: the snapped grid keeps `n = 8`, the same sort order, no two rungs merged (all gaps > `_GRID_COLLISION`), and `models` unchanged at 960. A speedup bought by shrinking the hypothesis space is not this lever. | **KILL** |
| **T4** | **The `p1` displacement is measured by `W6`'s own method** — same stream, same tick counts, deployed grid vs snapped — and reported at each tick count, **with its trend**. `W6`'s 3.2 × 10⁻³ at 98 ticks is the reference scale. Extrapolating from displacement size instead of measuring is a fail. | **KILL** |
| **T5** | **Decision equality on the pinned 104**: actions under both grids, reported as a count of differing rows and each row named. This is the leg that decides, not T1. | **KILL** |
| **T6** | Every predicate load-bearing on T1–T5 is **RED by mutation** before the read, each mutation varying **the dimension its claim is about** (`M-25`) — a T3 mutation must alter the grid's identity, not its precision. | **KILL** |

## Consequence — frozen, four branches

- **Branch 1 — no reproducible speedup (T1 fails).** The lever does not exist on this world.
  Publish; keep the grid exactly as frozen; `GD-15`'s conditional is **discharged as measured
  and empty**, which is a complete answer to `M-24`.
- **Branch 2 — speedup ∧ zero differing decisions ∧ `p1` displacement below `W6`'s measured
  3.2 × 10⁻³ scale.** Re-declare `theta_grid` on the **finest** dyadic lattice that clears T1
  (favouring smallest displacement over largest speedup — the opposite of optimising for the
  headline). `GD-15`'s sixteenths conditional is then discharged **by a finer lattice than
  sixteenths**, which is why ground 2's conflict does not arise; the discharge is recorded
  against `M-24`.
- **Branch 3 — speedup ∧ any differing decision.** **Do not ship.** Decide on `#19`'s hazard
  as `GD-15` ground 2 requires, not on the byte count or the seconds: name the rows, measure
  whether the displacement moved a rung across a consumer threshold, and hand the successor a
  frozen question. A 2.5× fold speedup does not buy one changed decision.
- **Branch 4 — speedup ∧ zero differing decisions ∧ displacement at or above `W6`'s scale.**
  Publish and **hold**: the decision-equality read is on 104 rows at today's data volume, and
  `W6` established the gap **grows with data**. Re-declaring on a null that is known to decay
  is the false-clear `#19` names. Hand forward with the number.

`M-1` is not engaged in any branch: the shadow is off the decision path and nothing here can
reach a commit.

## Registered expectation

**Branch 2**, at 2⁻¹⁴ or finer. The reasons are in disclosure 4, and so is the reason it might
be wrong: the whole-grid snap perturbs local density, which `W6` named as the real lever, and
no measurement of that yet exists. **If the expectation fails it will most likely fail at T5
or T4, not T1** — the speedup is already measured; what is not measured is whether it is free.

## Cost

**$0.** No priced run, no API call. Engine CPU on already-built binaries.
