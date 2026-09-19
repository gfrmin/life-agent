# r50 — B: sharpen `p1` in the 70–90 band — PRE-REGISTRATION

**Frozen before any census, build or engine work** (`M-3`). Eleven criteria (S1 and S2 carry
KILL clauses), six blind predictions, five consequence branches. Committed before any
measurement; every frozen clause is re-read against the artefact it names before it is applied.

## The question

`r49` read §18's first bar and it FAILed (`GD-26`), and the owner's ruling of 2026-09-05
(`conferrals/s18-bar-conferral.md` RULING; `r49b`, `GD-27`) named the successor: **B is the
substantive move** — a sharper `p1`, never a softer bar (§17.6). The defect has an address
(`r49` S4, FULL): the **70–90 leader-credence band**, 55 rows (15 in `70to80`, 40 in `80to90`),
realised correctness **0.800** in both, committed on **every** row at mean `p1` 0.863–0.873,
against break-evens **0.8369** (the deployed boot Ū) and **0.9000** (the gate's blind
posterior). Calibrated, the band withholds under either regime — which is why the ruling calls
B regime-independent, and why the open guard question (`RULINGS` §5: *does the A3 gate keep its
blind regime?*) gates nothing in this checkpoint except the label a straddling verdict carries.

**Is `p1` in that band sharpenable from evidence the record already carries?** Concretely: is
there a declarable indicator family whose cells split the band by realised correctness, so that
the engine's posterior differs *inside* the band — and, if so, does the engine follow the cells
when the family is declared?

## Scope — one lattice change, read on the binary world, at the standing regime

- **The lever is a declaration, not a bar.** B adds ONE indicator family to `world.py`'s
  vocabulary (the single source both `shadow_features` and `indicator_names` build from) and
  drops the families `r49` measured dead — `flags` (0/250 firings, three of seventeen indicators
  never fire) — and inert — `n-candidates` and `n-obs` (zero action changes on 238 ticks once
  `leader-credence` + `p-none` are present; 960 models against 456 for byte-identical decisions).
  The trim is §10's retention test applied (bayesian-foundations §10: instruments earn retention
  by reuse and calibration). Break-evens, Ū, the commit rule and the gate's δ/level are untouched.
- **The regime is the standing one.** The gate scores at `frozen-elicitations`; the `M-33`
  preflight declares both regimes and both break-evens before any engine spawns; the post-run
  pairing line and `a3_meta`'s marginal-commit table say whether the pairing bit. **Nothing is
  re-read at the softer regime while the guard question is open** (§17.6, `M-4`).
- **Binary world only** (`said@1`), as `r49`. No categorical bar is quoted.
- **Nothing deploys.** `M-1` binds independently: q2-019 committed wrong in `r49` and is a named
  class (superset-confirm). A PASS here is recorded, not enacted (S10).

## The fork, and how it is settled

Two mechanisms could sharpen `p1` in the band. **The census decides between them at $0, before
any `src/` change**; neither is chosen by preference:

- **Host-side — a family that SEPARATES the band.** The record carries, on every lookup-family
  decision, the candidate credences, `p_none`, `n_obs` and the candidate count; only the first
  two families built from them carry signal today. A new family whose cells split the 55 rows by
  realised rate gives the engine something to condition on inside the band.
- **Engine-side — the guard prior.** §17.6 named the engine's bucket belief as *"shrunk below
  the bucket's empirical rate by its guard prior"*. If the census finds the band **is** separable
  by realised rate but the held-out `p1` does not follow the cells once the family is declared,
  the lever is the engine's, and it is **filed as demand** on proplang (`M-23`/`GD-14`) — never
  edited from here.

## Recon disclosure — what was already seen before this was frozen

`M-3` protects blindness; blindness partly lost is disclosed. Everything below is in `r49`'s
published reading and nothing beyond it has been inspected:

- The per-bucket table (S4): `lt50` 46 rows / 0.696 · `50-70` 68 / 0.647 · `70-80` 15 / 0.800 ·
  `80-90` 40 / 0.800 · `ge90` 69 / 1.000, with mean `p1` 0.863–0.873 in the band.
- The covariate census: `flags` 0/250; `n-candidates` and `n-obs` fire but move no action;
  `leader-credence+p-none` reproduces FULL byte-for-byte on the paired file.
- The wrong set (S6): membrane 5 wrongs (q2-002, q2-018, q2-019, q2-040, q2-082), baseline 2
  (q2-018, q2-040); the three new ones are all marginal-reach rows.
- The keyed replay's window was 250 ticks / 141 questions at the boot Ū `u_wrong −5.13099`.

**Not inspected:** any candidate feature's distribution, any per-cell correctness, any row-level
field beyond what `r49` printed. The decision log's **key schema** (which fields exist) was read
to freeze the candidate list; **no values were read**.

## The candidate families — frozen list, frozen bucketing rule

Three candidates, each computable on BOTH paths the shadow reduces to (`summary_from_payload`
for live `/decide` traffic, `summary_from_decision_event` for the replay) from fields both carry
(`credences`, `p_none`, `candidates`). Anything only one path carries is excluded, because a
family the live mirror cannot emit is a family the deployed shadow cannot learn.

| id | feature (per tick) | rationale |
|---|---|---|
| **F1 `runner-up`** | the second-largest candidate credence; 0 when fewer than two candidates | the competing-values arc (runs 8–9, r09b–d): wrong commits ride a competitor — a leader at 0.8 with a runner-up at 0.15 is a different state from a leader at 0.8 alone |
| **F2 `leader-share`** | `leader / (1 − p_none)` when `p_none < 1`, else the leader | how much of the *non-null* mass the leader holds; the two existing families carry leader and `p_none` as independent one-hots and cannot form their ratio |
| **F3 `n-candidates-fine`** | the candidate count capped at 4: {1, 2, 3, 4plus} | the existing family lumps `2plus`; a refinement is the cheapest test of whether it was the lumping, not the signal, that made `n-candidates` inert |

**Bucketing rule (frozen; depends on X only, never on y).** Each candidate's cell edges are the
**terciles of the feature over the whole keyed replay** (all 250 ticks, not the band), rounded to
two decimals and published **before** any realised-correctness figure is computed; a value that
is structurally zero (F1 with one candidate) forms its own cell. The edges are then fixed for the
build — the census may not move them after seeing y. This is the one rule that keeps the edges
blind and still guards against a degenerate split (all rows in one cell).

## Criteria (S1–S11; S1 and S2 carry KILLs)

- **S1 (KILL) — the corpus is pinned before any engine work.** The gate run is launched with
  `--expect-ticks` / `--expect-questions` equal to the counts the census read. If the window
  still reads **250 / 141**, `r49`'s `leader-credence+p-none` variant IS the trimmed lattice's
  control reading and is not re-run; if it has moved, the control variant runs in the same
  invocation as B's (`M-28`: one tree, one corpus, one run). A window that moves *between* the
  census and the run refuses the run.
- **S2 (KILL) — the census: does any candidate separate the band?** Over the 55 band rows
  (`leader-credence` in `70to80` ∪ `80to90` by `world._credence_bucket`, read through the
  harness's own `features_for` — `M-7`), for each candidate report n and realised rate per cell.
  A candidate **separates** iff (a) at least one cell with **n ≥ 10** has realised rate **≤
  0.8369** and at least one with n ≥ 10 has rate **> 0.8369** (the deployed break-even — the
  side that decides commit-vs-withhold at the priced regime), and (b) the Beta(1,1)
  Beta-Binomial marginal likelihood of the split model over the pooled model gives a Bayes
  factor **≥ 10**. **If no candidate separates, B buys no engine run** — the band is not
  separable by the fields the record carries, and the next candidate needs its own
  pre-registration. If more than one separates, the one with the largest Bayes factor is built;
  the others are published, not built (one lever per reading).
- **S3 — the trim is a documented no-op before B is added.** With the family added and the
  three families dropped, `handshake_for`/`features_for` over `leader-credence+p-none` must
  reproduce `r49`'s variant byte-for-byte on the replay tick bodies (the indicator vocabulary is
  read from `world.py`'s bucket tuples, never re-spelled). Verified by test before any run.
- **S4 — TDD and mutation.** Tests first (RED for the expected reason), the one declaration in
  `world.py` (`DecideSummary` gains the field; both reducers fill it; `shadow_features` emits
  it; `indicator_names` declares it), the harness's `FAMILY_NAMES` reads it. A mutation battery
  over the new declaration with a hash-verified restore between mutations; every mutation RED.
- **S5 — A3, the §8-class differential gate, at the standing regime. THIS IS THE BAR.**
  P(Δ > 0.05) ≥ **0.90** against `eval/fairfight/ff-v2-baseline-m3off` arm `baseline`, 20 000
  draws at seed 8675309 — the harness's frozen defaults. The `M-33` preflight printed; the
  post-run pairing line and `a3_meta.marginal_commits` published. **A straddle** (the marginal
  rate inside `[0.8369, 0.9000]`) is reported **pairing-sensitive** and no PASS/FAIL is quoted
  as a reading of the policy until the guard question resolves.
- **S6 — the hard clause (`M-1`).** The named classes — superset-confirm (q2-019),
  warm-deliberate (q2-105) — and `r49`'s wrong set, enumerated against `r49`'s arm and the
  baseline. **No named class worse than `r49`'s arm**, regardless of S5. This checkpoint ships
  nothing either way.
- **S7 — did the engine follow the cells?** For the built candidate's low cell(s) (realised rate
  ≤ 0.8369 in the census), report the held-out `p1` distribution and the commit fraction at the
  standing regime. **The engine follows** iff the low cell's held-out commit fraction falls by
  at least **half** relative to `r49`'s (which committed on every band row). This is the criterion
  that settles the fork: separable-and-followed is host-side success; separable-and-not-followed
  is the engine's guard prior, and goes upstream as demand.
- **S8 — blast radius, named.** Every action that differs from `r49`'s `leader-credence+p-none`
  arm on the joined set is listed by bucket. Differences outside the band that the trim does not
  explain (S3) are the family's own effect and are published as such; below §6.13's wobble floor
  of **2** they may not be read as a benefit (`GD-8`).
- **S9 — arms and trees pinned for the whole run** (`M-28`): engine path + sha256, repo HEAD
  and dirty state, boot Ū, corpus counts, the census edges, in the artefacts. `M-32`'s phase
  marks and `phases.json` are the run's cost record; the run is a transient `systemd --user`
  unit, never an agent-session task.
- **S10 — nothing is deployed, enabled or swapped.** The live shadow keeps its running
  declaration until the next *natural* bridge restart (`GD-20`/`M-27`); even then, B rides that
  restart only if S5 PASSed, S6 is clean AND the guard question is answered. A PASS here is
  recorded, not enacted.
- **S11 — PII-clean.** Aggregates, register ids and opaque hashes only; no question text, no
  candidate string, no corpus value in tree.

## Blind predictions (reasoning only — no census has run)

1. **F1 `runner-up` separates the band** (S2 met), with the low-rate cell being the one with a
   non-trivial runner-up — the competing-values arc found the wrong commits in exactly that
   configuration, and r09b–d found the harmful rows carry a discursive competitor against a
   terse gold.
2. **F2 does not separate beyond what F1 already does** (it is a re-expression of leader and
   `p_none`, both of which the engine already sees), and **F3 does not separate** — the census
   already found the candidate count inert, and finer lumps do not create signal that coarser
   lumps hid.
3. **S3 holds** (the trim is byte-identical) — `r49` measured exactly this on the paired file.
4. **The engine follows the cells** (S7 met): the low cell's held-out commit fraction falls by
   more than half. Stated with the least confidence of the six — §17.6's shrinkage remark is
   the standing reason it might not.
5. **S5 still FAILs at the standing regime**, with Δ̄ moved positive and the marginal-commit
   rate above `r49`'s 0.875 (the family withholds wrongs faster than it withholds rights), but
   P(Δ > 0.05) well short of 0.90: at `r49`'s interval width (≈0.7 wide) a mean that clears
   0.05 by 0.9 of the mass would need to sit near +0.4, and no single-band lever moves it there.
   **A marginal rate inside `[0.8369, 0.9000]` — a straddle — is likelier than a clean side.**
6. **q2-019 is NOT rescued** — its defect is a truncated leader confirmed by a superset, not a
   competitor, so F1 has no purchase on it; it stays a wrong commit and **S6 blocks any ship as
   today**. This is a prediction about the class, not a criterion.

## Consequence branches (frozen before the reading)

- **S2 KILLs (no candidate separates)** → publish the census with every cell; **no engine run
  is bought**; B closes as *not separable from recorded evidence* and the next lever (a new
  sensor, or the engine's prior) needs its own pre-registration. Nothing else changes.
- **S5 PASSes, S6 clean, no straddle** → the first §18 bar is cleared **on the record only**.
  Nothing deploys: S10 holds until the guard question is answered, and `M-1` still blocks on
  q2-019 unless S6 finds it withheld. The next rung is §11's exit criteria under its own
  pre-registration.
- **S5 FAILs and S7 met (engine followed)** → B worked as calibration and the bar is still not
  cleared. This is the **third** consecutive A3 FAIL on one frozen criterion: **STOP for an
  owner ruling with a conferral document** — the ruling of 2026-09-05 licensed one iteration,
  not a series. No successor is opened unilaterally.
- **S5 FAILs and S7 not met (engine did not follow a separable band)** → the fork resolves
  engine-side: **file the demand on proplang** (`M-23`/`GD-14`), with the census cells and the
  held-out `p1` per cell as the evidence, and STOP for the same ruling. The family stays
  declared in tree (it is correct and cheap) but nothing rides a restart.
- **Straddle** (S5's marginal rate inside the two break-evens) → the verdict is published as
  **pairing-sensitive**, not as PASS or FAIL; S6/S7/S8 are still read and published; the
  guard question's answer converts the label. Nothing opens.
- **In every branch**: no bar is loosened (`M-4`), nothing deploys, `M-1` is not engaged by a
  reading.

## Scope, explicit

This does **not** touch the utility model, the gauge, the commit rule, the gate's δ/level, or
the regime the gate scores at; does **not** enable or price the categorical world; does **not**
build the parallel harness (D is sized from this run's `phases.json`, afterwards); does **not**
re-record the baseline arm's spend (C's open priced leg, its own small pre-registration); and
does **not** edit proplang. If the engine-side branch fires, an issue is filed as demand and
nothing more.
