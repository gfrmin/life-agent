# r46 leg B — the grid's precision: READING

Criteria T1–T6 and four branches frozen in
[`r46b-grid-precision-preregistration.md`](./r46b-grid-precision-preregistration.md) before
any `src/` change (`M-3`). Instrument: `scripts/membrane/grid_precision.py`. **$0** — engine
CPU on already-built binaries, no API call, no priced run.

**Branch 2 is enacted**: `world._GRID_LATTICE_BITS = 20`. `GD-15`'s conditional — inherited
from `r04-stocktake` §3(ii) and handed forward by `GD-17` — is **discharged**, and `M-24`
closed with it.

## Disclosure — the pre-registration's own mechanism claim was WRONG

Stated first because it is a correction to this leg's own frozen document, and the frozen
criteria were unaffected by it.

The pre-registration said the deployed grid is *"entirely non-dyadic — read as exact
rationals every value carries a factor of 5"*, and attributed the cost to those 5s
compounding. **Every IEEE double is dyadic.** Measured: the deployed grid's values have
denominators `2^57, 2^56, 2^54, …` — powers of two, every one. The correct mechanism is
**denominator BIT-LENGTH**, and the control identifies it beyond argument:

| lattice | max denominator bits | depth-100 CPU (2 reps) | ratio to deployed |
|---|---:|---:|---:|
| 2⁻⁸ | 8 | 20.96 / 20.34 | 0.20 / 0.21 |
| 2⁻¹⁴ | 14 | 20.23 / 19.65 | 0.26 / 0.25 |
| 2⁻¹⁷ | 17 | 22.60 / 23.01 | 0.29 / 0.30 |
| 2⁻²⁰ | 20 | 24.52 / 25.45 | 0.32 / 0.33 |
| 2⁻²⁴ | 24 | 29.01 / 29.36 | 0.38 / 0.38 |
| 2⁻³⁰ | 30 | 35.48 / 36.37 | 0.46 / 0.47 |
| 2⁻⁴⁰ | 40 | 50.05 / 50.24 | 0.65 / 0.65 |
| **2⁻⁵³** | **53** | **71.45 / 71.79** | **0.93 / 0.93** |
| deployed | 54–57 | 76.54 / 77.48 | 1.00 |

**Cost is monotone in the exponent, and 2⁻⁵³ lands back on the deployed cost.** The deployed
grid is simply the far end of one curve. Snapping does not make values dyadic — they already
are — **it makes them short**.

The decimal-rational reading was refuted by the leg's own first probe and the refutation was
misread at the time: a grid rounded to **3 dp** has small decimal denominators (≤ 10³) and
would be *cheap* under decimal parsing; it measured **slowest of all** (25.9 s at depth 60,
against the deployed 24.2 s), which is what a 53-bit double predicts. The right conclusion
was available then; the wrong description shipped in the pre-registration and is corrected
here rather than quietly dropped.

## T1 · T2 — the ratio, and how it moves with depth

Ratios are computed **within a run only** (deployed and candidates measured back to back),
because the deployed depth-250 baseline is not stable across runs — see deviation 4.

| depth | deployed CPU | best clearing lattice | ratio |
|---:|---:|---|---:|
| 25 | 5.65 / 6.05 s | — | **nothing clears** (0.59 – 0.77) |
| 60 | 23.79 / 24.36 s | 2⁻²⁰ | 0.46 / 0.45 |
| 100 | 77.02 / 77.45 s | 2⁻²⁰ | 0.32 / 0.33 |
| **250** (live boot depth) | **748.35 s** | **2⁻²⁰** | **0.30** |

**T1 MET** — 2⁻²⁰ clears the frozen ≤ 0.5× bar on two reps at each of two depths (60, 100).
**T2 MET** — depth 250, the checkpoint `GD-17` was interrupted before, is reached; the ratio
is reported at every depth. **For a fixed lattice the ratio improves with depth** (2⁻¹⁴:
0.77 → 0.36 → 0.26 → 0.14 across 25/60/100/250), which is the claim `GD-15` could not make
and `GD-17` predicted must be checked rather than extrapolated.

**Nothing clears at depth 25.** The lever needs depth to bite — precisely `GD-15`'s first
ground, which `GD-17` falsified for the depths we actually run at. Both readings are true at
their own depth, and that is why the criterion demanded more than one.

## T3 — and the sixteenths rule is REFUTED for this world

`r04-stocktake` §3(ii) named *the bench's "sixteenths" rule*. On this grid, sixteenths
**merge two rung pairs**: `n` falls 8 → 6, `min_gap` 0.0, so `models = n(17n−16)` would fall
**960 → 516**. That is not a placement hazard — it is a different hypothesis space wearing
this lever's clothes. **The frozen answer to the inherited conditional is therefore not
"apply sixteenths" but "sixteenths are inapplicable here, and a finer lattice is what the
measurement supports."** `GD-15`'s ground 2 was right, and for a stronger reason than it gave.

Every lattice from 2⁻⁸ to 2⁻⁵³ preserves `n = 8`, sort order, all gaps above `_GRID_COLLISION`,
and `models = 960` — verified on every engine boot in this leg.

## T4 — the `p1` displacement, by `W6`'s own method

`W6`'s reference: moving **one** rung by 7 × 10⁻³ produced a `p1` gap of **3.2 × 10⁻³** at 98
ticks, **growing monotonically** — `#19`'s signature. Here every rung moves, by far less:

| lattice | max displacement | `p1` gap at 14 / 42 / 98 ticks | growing? |
|---|---:|---|---|
| 2⁻¹⁴ | 2.8 × 10⁻⁵ | 4.7e-6 / 1.3e-6 / 3.7e-6 | **no** |
| **2⁻²⁰** | **4.6 × 10⁻⁷** | **3.1e-7 / 3.7e-7 / 3.4e-7** | **no** |
| 2⁻³⁰ | 3.1 × 10⁻¹⁰ | 1.1e-10 / 8.8e-11 / 5.4e-11 | no |

**T4 MET.** At the shipped lattice the gap is ~9 500× below `W6`'s and shows no growth over
the three tick counts `W6` itself used. **Three points cannot prove absence of a trend** —
what is established is the magnitude at 98 ticks and the absence of the monotone rise `W6`
saw at a displacement four orders larger.

## T5 — the leg that decides

**Zero differing actions over 428 distinct summaries** (605 recorded `/decide` exchanges from
the pinned m5-base corpus, reduced by the deployed `world.summary_from_payload`), at depth 60,
2⁻²⁰ against a baseline verified at **58 denominator bits**:

- `n_differing_actions`: **0**
- `p1_gap_max`: **3.41 × 10⁻⁷**; median 3.36 × 10⁻⁷ — a thousandth of `W6`'s scale
- boot CPU on the same population: 24.22 s → 10.99 s

## T6 — four mutations, each varying its own claim's dimension (`M-25`)

The snap made a no-op (T1's mechanism) → RED; a merge counted as no merge (T3) → RED; the
merge predicate hard-wired true (T3's other half) → RED; the boot snapshot truncated back to
its two-argument form (T2) → RED. Restore GREEN. Guards live in `tests/test_grid_precision.py`.

## What shipped, and the frozen clause it moved

`_GRID_LATTICE_BITS = 20` — **the finest lattice clearing T1 at two depths with two reps**,
which is what branch 2 froze (*"favouring smallest displacement over largest speedup"*).
2⁻²⁴ misses the bar at depth 60 (0.508 / 0.513) and so is not available, even though it is
finer; 2⁻⁸ is three times cheaper still and is **not** taken, because the frozen rule
prefers displacement.

`_snap_to_lattice` applies **after** selection, so `r44`'s two frozen clauses still decide
membership exactly as before, and it is **refused rather than allowed to merge**: the ladder
steps to a finer lattice, up to the double's own 53 bits where the snap is a no-op.
`_GRID_COLLISION` bounds a *fixed value* against a *crossing* and says nothing about two
crossings, which can be arbitrarily close — so the guard is load-bearing, not decoration.

**Two of `r44`'s tests were weakened, and this is the pre-registered consequence, not a
silent loosening.** *"A rung **at** the operating rate"* and *"a rung at every crossing"* were
exact-equality assertions; they now assert **within half a lattice step**, a tolerance
**derived** from `_GRID_LATTICE_BITS` rather than written as a constant, so re-declaring the
lattice moves the tests with it and a larger displacement fails rather than passes. The
justification is T4 and T5, not convenience.

## What it buys, stated without borrowing `GD-20`'s hazard

At the live boot depth of 250 the fold costs **748 s → 226 s**, saving **~8.7 minutes of
engine CPU per bridge restart**. **This does not reduce `GD-20`'s risk.** That hazard is the
credence skin's cold Julia precompile racing a 120 s ready-sentinel timeout, which happens
*before* any fold and is untouched by this change. A restart still costs what `GD-20` says it
costs; what shrinks is the wait between a healthy boot and a serving shadow.

## Deviations — six, all disclosed

1. **The pre-registration's mechanism claim was wrong** (above). Criteria unaffected.
2. **The instrument's boot snapshot was truncated.** A first pass copied
   `p0_engine_replay.py`'s two-argument `boot_snapshot` call, omitting `warm_vectors_dir` and
   the Claude verdict channel: **70** verdicts where the deployed bridge reaches **250**.
   Every "depth 250" row would have been a depth-70 row wearing the label, and T2 is a claim
   about depth 250. Caught before any reading; a drift test now pins the four-argument call.
3. **The `W6` leg re-spelled the wire.** It hand-rolled a `{"query": {"readouts": …}}`
   request; rewritten to fold with `observe_verdict` and read `p1` from `decide(...).readouts`.
4. **The deployed depth-250 baseline is not stable across runs**: 1102.82 s, 744.33 s,
   748.35 s — same depth, same grid, same binary, differing concurrent load. All ratios in
   this report are within-run. The 1102.82 s run is the one that reproduces `GD-17`'s ~19.5
   min live boot; the ~748 s runs are the same measurement on a quieter box.
5. **One `T5` run was void and was discarded rather than reported.** It started 50 seconds
   *after* `world.py` was edited, so its "deployed" baseline was already snapped and it was
   comparing the treatment against itself. Detected by process start time, killed, and re-run
   against a baseline verified at 58 bits. Registered as **`M-28`**.
6. **A long run was piped through `tail`**, which buffers and hid its progress for twenty
   minutes — the anti-pattern this repo's own operating manual names.

## Gates, and when this reaches the live wire

Suite **3 155 passed / 0 failed**; `ruff` clean; `mypy` clean on this leg's files. The two
`r44` clause tests were amended as above; four new guards were added and mutation-verified.

**It is merged, not yet on the wire.** The running shadow booted at 17:37 under the old grid
and keeps it until the bridge restarts. **No restart is taken for this** — `GD-20` measured a
restart as a real hazard, and an 8.7-minute fold saving is not a reason to spend it; the
change lands at the next restart that happens for its own reasons.

**No `M-14` boundary row is warranted, and that is a judgement with a number behind it.**
The grid keeps `n = 8` and `models = 960`, so the hypothesis space is the same size and
shape; rungs move by ≤ 4.8 × 10⁻⁷, which T4 measured as a ~3 × 10⁻⁷ effect on `p1` and T5 as
**zero** changed decisions over 428 summaries. `p1` either side of the change is a posterior
over the same space at the same resolution — unlike the 2 393 → 960 `models` change, which
did need one.

## Consequence

Branch 2 enacted. `GD-15`'s conditional is discharged and `M-24` closed on it: the antecedent
fired at `r44`, and the consequent is answered here — **not by applying the sixteenths rule,
which this world refutes, but by the finest lattice a frozen bar admits.** No §18 bar is read;
`M-1` is not engaged; the shadow stays off the decision path.
