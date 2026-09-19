# r48 — the E1 re-earn measurement: READING

**Pre-registration**: `docs/unification/reports/r48-reearn-measurement-preregistration.md`,
committed `8f167b1` **before the instrument ran** (`M-3`). Nine criteria, J1 KILL, five blind
predictions, three consequence branches. **Cost $0** (engine CPU on the deployed binary).
**Nothing deployed, nothing enabled** (J9).

**The reading in one paragraph.** `J1` **fires as a KILL** — three of 129 summaries never
returned an action — and its *stated ground* is refuted: the enablement is exercised, on 99.85%
of the recorded population; what failed is a wall-clock bound at k ≥ 12. On the leg that did
complete, **the E1 re-earn does not clear**: `gather` on all 126 completed episodes and on all
55 sweep steps, no flip anywhere. §16 finding 3's *unreachable-by-construction* argument is
nevertheless **void** — the θ ceiling now sits **above** the bar, by 1.2×10⁻⁸, because `r46`
leg B's lattice snap rounded the decisive rung up. That does not rescue the re-earn: the
admissible window for a flip is 1.2×10⁻⁸ wide. And the cost measurement **refutes a blind
prediction outright** — the enabled arm B is 2.3× to 145× *slower* than arm A despite a model
space 4.65× smaller, scaling as ~k⁴ where `models` is linear in k. §16 finding 4's owed K-cap
now has a number: **k ≤ 3**, covering 74.3% of recorded traffic.

## Method — what makes this a reading and not a re-derivation

§16 finding 3 settled the binder **analytically**: under the myopic-perfect-information
`gather` row, `respond_j` overtakes `gather` only above a crossing it computed in that era's
constants (`p_j > 0.9942`), against a θ ceiling of ~0.9. Two of those three terms have since
moved — #19 handed the ceiling to us (our declared grid's top rung reads **0.990634**) and the
Ū drifted (the deployed vs-abstain bar reads **0.836894**, `u_wrong` −5.13099).

Recomputing that inequality with today's constants is precisely what this instrument does
**not** do. `scripts/membrane/reearn_audit.py` carries **no EU arithmetic**: it calls
`categorical.decide_categorical` — the deployed episode `r47` built and the shadow supervisor
binds — and reads the engine's own chosen action. Pricing a constant through a
re-implementation of the rule that assembles it is `M-7`'s trap, and avoiding it is why
`GD-24` ordered `r47`'s build before this measurement.

Where this report *does* quote a crossing (§J3's gap), the utility rows are **read from the
deployed declaration** — `world.utility_by_action`, the single source `categorical.utility_said_cat`
builds its own rows from — and the result is then **checked against the engine's 126
independent choices**, which is the point: the arithmetic is a description of the engine's
behaviour, never a substitute for it.

## The corpus is a census, not a sample

The ledger's `cat` rows carry each episode's full `summary`, so the deployed `CatSummary` is
reconstructed **field for field from the record** rather than re-derived. **2 012 recorded
rows over 78 questions reduce to 129 distinct summaries** (k ranging 1–14); the episode is a
pure function of `(u_bar, summary)`, so replaying the distinct set covers every recorded row.
Nothing is dropped and no cap is applied; population statements are frequency-weighted by the
2 012.

Two baseline facts, stated in the pre-registration before the run and repeated here so they
are never mistaken for results: the recorded rows are **arm A, pre-enablement**, and **all
2 012 recorded actions are `gather`**.

## J1 (KILL) — the criterion FIRES, and its ground is refuted

**126 of 129 distinct summaries completed and decoded to a declared action; three did not.**
Weighted, that is **2 009 of 2 012 recorded rows (99.85%)** covered and 3 (0.15%) not.

| k | `n_obs` | weight | outcome | wall clock |
|---:|---:|---:|---|---:|
| 14 | 0 | 1 | `REF` — 300 s single-read timeout | 300.1 s |
| 14 | 19 | 1 | `REF` — 300 s single-read timeout | 300.1 s |
| 12 | 17 | 1 | `REF` — 300 s single-read timeout | 1 248.0 s |

The pre-registration froze the KILL's ground with it: *"it means `r47`'s enablement is not
exercised by the real corpus, and the reading stops."* **That ground is refuted by the
measurement.** The enablement is exercised — 126 episodes handshook, folded and returned a
declared action on the deployed enabled world, covering 99.85% of the recorded population. What
failed is a **wall-clock bound**, and `read_timeout_s` bounds a *single read*, not an episode.

The decisive row is **k = 14 at `n_obs` = 0**: an episode with *no observations at all* blew a
300 s read. The cost is therefore in the **model space and the handshake fold**, not in
evidence depth — `models` = 344 × 14 = **4 816** before a single observation is folded. That
also disposes of the k=12 group: three summaries share (k=12, `n_obs`=17) and differ in other
fields; two completed at ~60 minutes and one refused at 1 248 s, so the refusal is not a
function of `(k, n_obs)` alone but of how the same total work happens to fall across reads.

**J1 stands as fired.** It is not reinterpreted, and no consequence the criterion would have
blocked is taken. This is the `GD-16` shape — letter met, ground refuted — and the precedent
there binds: publish both, adopt neither. The re-read of `r47` that the KILL demands is
performed below and its finding is **not** the one the pre-registration guessed:

> **`r47`'s enablement is sound; its episode budget is unbounded.** Nothing in the build is
> wrong — the four items land, the wire is accepted, the fold runs. What is missing is the
> K-cap §16 finding 4 has owed since 2026-07-22, which J5 now prices.

Production's `cat_timeout_s` is **20 s**. These episodes blew a bound **15× more generous**.
That makes the K-cap a **hard precondition below k = 14**, not a recommendation.

## J2 — the action census, published whole

**`gather` on every completed episode.** No exceptions, at any k, at any evidence depth.

| action | distinct summaries | weighted rows |
|---|---:|---:|
| `gather` | 126 | 2 009 |
| `respond_j` | 0 | 0 |
| `ask` | 0 | 0 |
| `abstain` | 0 | 0 |
| *(no action returned)* | 3 | 3 |

This criterion had no pass condition by construction; it is the reading. `r45`'s C3 measured
the same constant on the binary world's deployed path and it now reproduces on the categorical
world's, on a census rather than a sample. **Blind prediction 1 is confirmed on every episode
that returned an action**; it named all 129, and three returned none.

## J3 — the binder, measured: NO FLIP, and §16's structural argument is VOID

**55 steps over k ∈ {1, 2, 3, 5, 10}, 11 steps each at `n_obs` = 0, 4, 8, … 40, zero refusals,
and `gather` on every single step.** No flip anywhere. The frozen reading is therefore the
maximum `p_argmax` attained and the gap beside it.

| k | steps | actions seen | flipped | max `p_argmax` |
|---:|---:|---|---|---|
| 1 | 11 | `gather` | no | 0.9834782159233146 |
| 2 | 11 | `gather` | no | 0.9834782159231634 |
| 3 | 11 | `gather` | no | 0.9834782159233146 |
| 5 | 11 | `gather` | no | 0.9834782159233146 |
| 10 | 11 | `gather` | no | 0.9834782159233146 |

**The sharpening is real, and it is K-independent.** §16 measured the engine's attainable `p1`
at **0.8918** from 40 verdicts under a θ ceiling of ~0.9; the same 40 observations now reach
**0.98348**. Four of the five k values agree to **all 16 digits**; k=2 alone differs, at the
13th. Only the zero-evidence prior separates the curves (≈ 1/(k+1), tracking `obs_arity`) —
`GD-22`'s K-independent θ codebook showing through into the posterior.

### The gap, and why one number bounds every k

`world.utility_by_action` is the deployed declaration both worlds price from. Read from it:
`gather` splits (−0.048057099794822, 0.951942900205178) and `respond` splits
(−5.130990272278651, 1.0). Because the split spans exactly 1.0, `EU(gather) = 0.951943 − p0`,
and `respond_j` wins iff

```
p_j  >  ( EU(gather)(p0) − u_wrong ) / ( u_correct − u_wrong )        [the crossing]
```

The crossing **falls** as `p0` rises, so it is not a single number per k — but `p_j ≤ 1 − p0`
always, and `1 − p0 > crossing(p0)` holds only for `p0 < 0.0093660477`, i.e. only for

```
p_argmax  >  0.9906339522695138   =   world.respond_threshold(u_bar)
```

(The two routes — solving `1 − p0 = crossing(p0)` and reading `respond_threshold` — agree to
**1 ULP**, 0.9906339522695139 vs 0.9906339522695138. Stated as agreement, not as an identity;
the same standard disclosure 3 applies to a coincidence that failed it.)

So the deployed binary bar is a **necessary condition at every k** (and exactly the bar at
k = 1, where `p_argmax = 1 − p0`). That is the same quantity §16 quoted as *"0.9942 even at the
feasibility limit"*, re-read under today's Ū.

```
necessary bar    world.respond_threshold(u_bar)   0.9906339522695138
attained at 40 observations                       0.9834782159233146
                                            gap = 0.0071557363461991486
```

Against §16's era (attainable 0.8918, bar 0.9942, gap 0.1024) the gap has closed **14.3×** and
has still **not closed**.

**The arithmetic is checked against the engine, not trusted.** On all 126 completed replay
episodes, `p_argmax ≤ crossing(p0)` — **zero** rows where the read rows predict `respond_j` and
the engine chose `gather`. The closest any recorded row came to its own crossing:

| k | `n_obs` | `p_argmax` | `p0` | crossing | gap | weight |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 18 | 0.9662325 | 0.033767 | 0.9866539 | 0.020421 | 8 |
| 1 | 14 | 0.9585710 | 0.041429 | 0.9854043 | 0.026833 | 4 |
| 1 | 12 | 0.9538642 | 0.046136 | 0.9846366 | 0.030772 | 4 |

Eleven distinct summaries (99 of 2 012 rows) clear the **vs-abstain** bar 0.836894 — the first
categorical evidence on the deployed Ū that respond beats abstain, matching §16 finding 2 — and
**every one of them still chose `gather`**. Nine of the eleven are k = 1, where "which code"
is not a question at all; the qualification matters and is not buried.

### The finding the pre-registration did not anticipate

§16 finding 3 held that `respond_j` is unreachable **BY CONSTRUCTION**, because "the θ grid caps
any atom's predictive mass at ~0.9" while the bar sat at 0.9942. **That structural argument is
now void.** The θ grid's top rung *exceeds* the bar:

```
θ grid top rung  world.theta_grid(u_bar)[-1]      0.9906339645385742
necessary bar    world.respond_threshold(u_bar)   0.9906339522695138
                                    top − bar = +1.226906043427789e-08
```

And the mechanism is undeclared. `theta_grid` seeds a rung at every `argmax_crossings` value;
`respond_threshold` returns the LAST of those crossings — so the top rung **is** the decisive
crossing. `r46` leg B then snapped every rung to the 2⁻²⁰ lattice for speed, and the snap
rounded **up**:

```
bar × 2^20 = 1038754.9871349577  ->  round  ->  1038755  ->  0.9906339645385742
```

At 1038754.4 it would have rounded down and `respond_j` would remain structurally impossible.
**Reachability now rests on a rounding direction in a lattice snap adopted for an unrelated
reason.** Registered as **`M-30`**.

This does NOT rescue the re-earn, and it must not be read as a lever. The admissible window is
`p_argmax ∈ (0.9906339522695138, 0.9906339645385742]` — **1.2×10⁻⁸ wide**, smaller than float
noise in the fold. The convergence is real but converges *into* that window: the gap to a row's
own crossing is exactly `0.836894 × (p0 − 0.0093660477)` — the coefficient being the vs-abstain
bar itself, a consequence of the perfect-information `gather` row — and at k = 1 it reads 0.0234
at 16 observations, 0.0088 at 32, 0.0060 at 40. Monotone, and asymptotically bounded away from
a flip by every practical measure.

What this changes is the *shape* of the refusal. §17.6's rule binds as before (a sharper `p1`,
never a softer bar), and the exit is now named precisely: **the bar itself must move — the
`gather` row's perfect-information bake-in, #15 / E3 — or rungs must exist above the crossing.
Accumulating evidence cannot get there.** This checkpoint proposes neither.

**Blind prediction 2 is confirmed** on both its clauses that were measurable (no flip; the
action never leaves `gather`). Its third clause — `p_argmax` "asymptoting near" the top rung —
is **not** established: at 40 observations the curve is still rising and 0.00716 short.

## J4 — §16 finding 5, answerable for the first time

#20's per-code readout is live on arm B, so `p0` IS P(y = 0) and R-D23's declared null-mass cap
of `1/(K−1)` is directly checkable. Across the 113 completed rows with a finite cap (k ≥ 2):

**Zero violations.** Observed `p0` spans 0.033767 – 0.465163.

| k | cap `1/(K−1)` | `p0` min | `p0` max | max `p0` / cap |
|---:|---:|---:|---:|---:|
| 2 | 1.000000 | 0.082965 | 0.258474 | 0.2585 |
| 3 | 0.500000 | 0.077062 | 0.242325 | 0.4847 |
| 5 | 0.250000 | 0.086260 | 0.163790 | 0.6552 |
| 8 | 0.142857 | 0.058145 | 0.108214 | 0.7575 |
| 10 | 0.111111 | 0.044906 | 0.088821 | 0.7994 |
| 11 | 0.100000 | 0.042288 | 0.081567 | 0.8157 |
| 12 | 0.090909 | 0.038764 | 0.072604 | 0.7986 |

**The cap holds, never binds, and tightens monotonically with k** — 0.26 of the cap at k=2
rising to 0.82 at k=11. §16 recorded this as unobservable; it is now measured, on the whole
recorded population. **Blind prediction 3 is half-confirmed**: its direction is right (loose at
small k, tight at large k), its hedge ("may bind at large k") did not happen anywhere within
the observed range.

## J5 — the cost, and the K-cap it forces

Per-episode wall clock on the deployed enabled world, against §16 finding 4's recorded arm A
medians:

| k | `models` B (344k) | `models` A (1601k) | median B | median A | B/A | max B | ≤ 20 s? | rows | cum. |
|---:|---:|---:|---:|---:|---:|---:|:--:|---:|---:|
| 1 | 344 | 1 601 | 165 ms | 71 ms | 2.3× | 0.9 s | **yes** | 895 | 44.5% |
| 2 | 688 | 3 202 | 670 ms | 189 ms | 3.5× | 1.8 s | **yes** | 390 | 63.9% |
| 3 | 1 032 | 4 803 | 5.0 s | 514 ms | 9.7× | 9.7 s | **yes** | 210 | **74.3%** |
| 4 | 1 376 | 6 404 | 10.9 s | — | — | 27.4 s | no | 90 | 78.8% |
| 5 | 1 720 | 8 005 | 29.6 s | 1.2 s | 24.7× | 66.7 s | no | 184 | 87.9% |
| 7 | 2 408 | 11 207 | 210.6 s | 2.8 s | 75.2× | 374.3 s | no | 74 | 94.2% |
| 10 | 3 440 | 16 010 | 1 000.1 s | 6.9 s | 144.9× | 1 550.4 s | no | 82 | 99.4% |
| 12 | 4 128 | 19 212 | 3 601.5 s | — | — | 3 619.8 s | no | 6 | 99.9% |

**Blind prediction 4 is REFUTED, and not marginally.** It predicted arm B *faster* than arm A
because the declared 8-rung θ grid gives a model space **4.65× smaller** (344k vs 1601·K). Arm B
is instead **2.3× to 145× slower**, and the ratio grows with k. So the model population is
**not** the cost driver: a log-log fit of median latency against k gives slope **4.11**, where
`models` is linear in k by construction.

The mechanism is **not measured here** and is named as a hypothesis only: `r44` added a clock
row that forces a **preposterior every decide** (`GD-17`: 297 ms vs 135 ms at negligible depth),
and a preposterior ranges over the act grid (3 + k rows) × the outcome space (k + 1 atoms) ×
`models` (344k) — cubic in k before any constant. Arm A's era predates that row. Confirming it
belongs to whoever builds the cap, under its own pre-registration.

**The K-cap, as a number.** Every observed episode at **k ≤ 3** completes inside production's
20 s `cat_timeout_s` (worst case 9.7 s); k = 4 exceeds it (27.4 s worst case) and by k = 5 the
*median* does. A cap at **k ≤ 3 covers 74.3% of recorded traffic**; k ≤ 5 would cover 87.9% but
blows the bound at the median. The remaining 25.7% needs a **named skip**, not a silent one —
§16 finding 4's own words. **A recommendation is all this criterion permits, and all it makes.**

## J6 — the arms and the trees, pinned for the whole run (`M-28`)

| what | value |
|---|---|
| engine (arm B, deployed) | `~/.local/bin/proplang-host` |
| engine sha256 | `71998f6556f53314affd089a41eff5eb2b5cd749e56661f702989f744b8cf3c6` |
| repo tree, both legs | `2fc075a` |
| enabled world | `life_agent.membrane.categorical`, the `r47` enablement (`GD-24`) |
| recorded arm (the corpus) | arm A, **pre-enablement** |

The instrument stamps `git_head` + `dirty` + engine sha into every leg's output. The **sweep**
leg ran `dirty=false`. The **replay** leg ran `dirty=true` — see disclosure 4.

## J7 — the battery, before any reading was believed

**Nine mutations, 9/9 RED**, re-run after both measurement legs had finished (so the tree was
free to move — `M-28`), instrument restored **byte-identical** (`git diff` empty) and 7/7 green
afterwards. They kill: the census losing its multiplicity (turning a census into a sample), the
census dropping rows, the `cat`-row filter, two fields of the record reconstruction, R-D23's
quoted cap constant, both frozen sweep parameters, and the monotone-support code generator.

## J8 — PII

`CatSummary` is numbers by construction (`k`, `obs_codes`, `n_obs`, `n_obs_unmapped`,
`daemon_map_index`, three booleans); `question_id` is an opaque hash and is never read by the
instrument; no question text and no candidate string enters this measurement at any point.

## J9 — nothing deployed, nothing enabled

No `src/` change of any kind. The categorical world remains env-gated OFF and byte-inert in
its absence. `M-1`'s hard clause is not engaged: no lever ships from this checkpoint.

## Blind predictions — scorecard

| # | prediction | outcome |
|---:|---|---|
| 1 | `gather` on all 129 | **confirmed** on all 126 that returned an action; 3 returned none |
| 2 | no flip within the bound, action never leaves `gather` | **confirmed**; its "asymptoting near the top rung" clause **not established** (still rising, 0.00716 short) |
| 3 | cap loose at small k, may bind at large k | **half** — direction right, never binds anywhere observed |
| 4 | arm B **faster** than arm A (smaller model space) | **REFUTED** — 2.3–145× *slower*, and the cost is ~k⁴ while `models` is k¹ |
| 5 | the re-earn does not clear; exit is #15 / E3 | **confirmed** |

## Disclosures

1. **A monitor filter that would have hidden the signal.** The live watch tested
   `$0 !~ /OK gather/`, but the instrument prints `OK  gather` with **two** spaces, so every
   `gather` row fired as a non-gather alert. Left unfixed, all 129 rows would have alerted and a
   genuine flip would have been indistinguishable from noise — exactly the signal J3 exists to
   detect. Rewritten to extract the field, **verified red-green on synthetic input** (gather
   silent, `respond_j` fires, `REF` fires) before re-arming. A defect in the monitoring layer,
   not the measurement; `r05`'s precedent is that instruments ship defects and the useful move
   is to publish them.
2. **Two runs interleaved in one append-mode log.** `sweep-final.log` held an earlier killed
   pass alongside the unit of record. Rather than discard it, the 33 overlapping steps were
   diffed: **byte-identical**, converting an artefact into an unplanned determinism control.
3. **A numerical curiosity tested and rejected.** `p_argmax(k=10, n=0)` appeared to equal
   `0.09 + p_argmax(k=1, n=0)/100`. It does not: 0.09534836530685424 vs 0.09534836530685425,
   off by 1 ULP, and the offset from `1/(k+1)` is non-monotone across k. Reported as a
   non-finding rather than dressed up.
4. **The replay leg ran on a dirty tree** (`dirty=true`). The dirt was **docs-only** — this
   report and the `M-30` register draft; `git diff` on `src/` and `scripts/` was empty
   throughout, and the sweep leg ran clean. `M-28`'s letter is met for the sweep and met in
   substance for the replay; recorded rather than glossed.
5. **Wall clock was contended.** Load on this 8-core box swung 2.55 → 17.75 during the run from
   *other* repos' sessions. Renicing mid-run was deliberately **not** done: `latency_ms` is
   recorded per episode, and a priority change would leave J5's series measured under two
   regimes. Absolute latencies are therefore an upper envelope; the **slope** (4.11) and
   `models` (deterministic, load-independent) carry the arm-A comparison. The three refusals are
   partly exposed to this — though the decisive k=14 / `n_obs`=0 row refused at box load 2.55,
   near idle.

## Consequence — enacted

- **J1 stands KILL**, its ground published as refuted (`GD-16` shape). Nothing the criterion
  would have gated is taken.
- The KILL's mandated **re-read of `r47`** is performed: the enablement is sound and exercised;
  the missing piece is the **episode budget**, which J5 prices at **k ≤ 3**.
- **The E1 re-earn is NOT cleared on this ledger under this Ū.** That conclusion rests on the
  sweep leg — 55/55 steps, zero refusals, no flip — and on J2's 126/126, not on the refused
  rows. The frozen no-flip branch is enacted: the refusal is published with the maximum
  `p_argmax` (0.98348) and the gap (0.00716) beside it.
- §17.6's rule binds: **a sharper `p1` or an engine-side change (#15 / E3), never a softer
  bar.** This checkpoint proposes neither.
- **`M-30` registered.** §16 finding 3's by-construction clause is corrected in
  `docs/membrane-shadow.md`; its primary attribution — the deliberately-overvalued information
  row — survives and is now confirmed **empirically** rather than analytically.
- **The §18 bars gain two preconditions** from this reading, on top of the four already
  published: the **K-cap** (no bar may be read on a world whose episode budget is unbounded),
  and the fact that the categorical commit surface is **empty for the same reason the binary
  one is** — `gather` dominates, not an insufficient `p1`.
