# r50 — B: sharpen `p1` in the 70–90 band — READ: **S2 KILLs**, no engine run is bought

**2026-09-05 · $0 · no engine · tree `aab71eb` · window 250 ticks / 141 questions (r49's, unmoved).**
Pre-registration frozen `037b506` before any census or `src/` change
(`r50-band-sharpening-preregistration.md`). Instrument `scripts/membrane/band_census.py`
(14 tests, 8/8 mutations RED); record `$LIFE_AGENT_KB/eval/r50/census.json`.

> **Verdict.** None of the three frozen candidate families separates the 70–90 band. Every
> split model is *penalised* against the pooled one — Bayes factors **0.229 · 0.253 · 0.212**
> against a bar of 10 — so S2's KILL fires and, by the frozen branch, **B buys no engine run and
> closes as *not separable from recorded evidence*.** The direction the ruling and the
> pre-registration expected is visible (rows with a competitor are right less often: 0.731 vs
> 0.862) and is nowhere near evidence: at the observed rates the split needs about **seven
> times** the band's rows (≈385) to clear the bar, and the band accrues roughly **seven
> owner-verdict rows a month**. The binding constraint on any evidence-side lever for §18 is
> therefore the verdict supply, not the feature vocabulary.

## 1. What was asked

The owner's ruling of 2026-09-05 named B the substantive move: `r49`'s 70–90 leader-credence
band — 55 rows, realised correctness **0.800**, committed on every row at mean `p1` 0.863–0.873,
below both break-evens (0.8369 deployed, 0.9000 gate) — so a calibrated `p1` withholds it under
either regime. The pre-registration asked whether `p1` there is **sharpenable from evidence the
record already carries**: is there a declarable family whose cells split the band by realised
rate? Three candidates were frozen, each emittable on both shadow paths (`runner-up`, the
second-largest candidate credence; `leader-share`, the leader's share of the non-null mass;
`n-candidates-fine`, {1, 2, 3, 4plus}), with an X-only bucketing rule — tercile edges over the
whole keyed replay, rounded to two decimals, computed before any realised-correctness figure —
and a separation test: a cell with n ≥ 10 at or below 0.8369 and one with n ≥ 10 above it, and
a Beta(1,1) Beta-Binomial Bayes factor of split over pooled ≥ 10.

## 2. The census

Band membership was read through the harness's own `features_for` (`M-7`): 55 rows, exactly
`r49`'s. The edges were computed and printed from X alone before any y was read.

**Edges (X only, all 250 ticks).** `runner-up` terciles **(0, 0.03)** — 58% of recorded ticks
carry no runner-up at all and 70% carry one at or below 0.03 (ledger max 0.398);
`leader-share` terciles **(0.94, 1)**; `n-candidates-fine` cells 1 / 2 / 3 / 4plus by
declaration.

| candidate | cell | n | correct | rate | BF (split : pooled) | separates |
|---|---|---:|---:|---:|---:|---|
| `runner-up` | none | 29 | 25 | 0.862 | | |
| | 0to0.03 | 18 | 13 | 0.722 | | |
| | ge0.03 | 8 | 6 | 0.750 | **0.229** | **no** |
| `leader-share` | lt0.94 | 14 | 12 | 0.857 | | |
| | 0.94to1 | 15 | 10 | 0.667 | | |
| | ge1 | 26 | 22 | 0.846 | **0.253** | **no** |
| `n-candidates-fine` | 1 | 29 | 25 | 0.862 | | |
| | 2 | 6 | 5 | 0.833 | | |
| | 3 | 18 | 12 | 0.667 | | |
| | 4plus | 2 | 2 | 1.000 | **0.212** | **no** |

`runner-up` meets the *sides* clause — a 29-row cell at 0.862 above the break-even and an
18-row cell at 0.722 below it — and fails the *evidence* clause by a factor of forty. The other
two fail both. The live boot break-even at read time was 0.8369, equal to the frozen one.

**A disclosure on the bucketing rule.** With edges (0, 0.03), the `runner-up` cell `lt0` is
empty by construction — a value cannot be below zero — so the rule produced three populated
cells rather than four. The pre-registration anticipated a degenerate split as the thing the
rule guards against; here it is the rule's own first cell that is degenerate. Reported, not
repaired: the edges were frozen blind and the census stands on them.

## 3. What the KILL means, with two numbers it needs

**It is not a null on direction.** Collapsing the competitor cells, rows with any runner-up
are right **0.731** of the time (19/26) against **0.862** (25/29) without one — the pattern the
competing-values arc predicted. The Bayes factor of *that* two-cell split is **0.529**: still
below 1. A Beta(1,1) split model pays for its extra rate, and 55 rows cannot buy it back at a
0.13 gap.

**How much evidence the observed split would need.** Scaling every cell at its observed rate,
the three-cell split reaches BF ≥ 10 at **9×** (band n ≈ 495) and the two-cell split at **7×**
(band n ≈ 385). Those are the sizes at which the frozen criterion would have read *separates*
if the rates held — a statement about the instrument's power, not a re-read of the verdict.

**How fast the band grows.** The keyed replay's verdict-bearing ticks come from two sources.
Owner verdicts contribute **13** ticks in June and **57** in August (none yet in September),
of which **5 + 7 = 12** fall in the band. The remaining band rows come from the Claude verdict
channel (`core/claude_verdicts.py`, 180 verdicts, **dormant since 2026-07-22**). At ~7 band rows
a month from the owner alone, 385 rows is years away. So the constraint that binds every
evidence-side lever on §18's bar is the **verdict supply**: without a second verdict source
running, no family — these three or any other — can be shown to separate the band at the
frozen bar. `GD-23` already named that source as the re-opener of `OB-12`'s increment B; this
reading gives it a number.

## 4. Blind predictions, scored

| # | prediction | outcome |
|---|---|---|
| 1 | `runner-up` separates (S2 met) | **REFUTED** — sides met, evidence clause failed (BF 0.229) |
| 2 | `leader-share` adds nothing beyond F1; `n-candidates-fine` does not separate | **confirmed** (0.253, 0.212) |
| 3 | the trim is byte-identical (S3) | **untested** — no build was licensed |
| 4 | the engine follows the cells (S7) | **untested** — no run was bought |
| 5 | S5 still FAILs, likelier a straddle | **untested** |
| 6 | q2-019 is not rescued | **untested** as a run; the census cannot see it |

One prediction refuted, one confirmed, four untested by the KILL's own operation — the frozen
branch forbids buying the run that would have tested them.

## 5. Consequence enacted

- **No engine run is bought.** B closes as *not separable from recorded evidence*.
- **Nothing is built on the decision path.** `DecideSummary` gained the raw `runner_up_credence`
  field on both reducers (step (a), `84b40d4`) — a neutral field, not an indicator: the declared
  vocabulary, the handshake and the world digest are byte-untouched, verified by test. It stays,
  because it is the record the census reads and any successor census will read. The shadow's
  decide/gate records gain the key additively on the next natural restart.
- **The instrument stays in tree, tested, and dormant** — the house pattern (`corroborate_audit`,
  `carrier_audit`, `replace_audit`): it is the tool a successor re-runs the day the band has the
  rows, under the same frozen rule.
- **Nothing is deployed, enabled or swapped; `M-1` is not engaged; no bar is loosened.**

## 6. What remains — named, not opened

Each needs its own pre-registration; none is opened by this reading.

- **The verdict supply.** The only thing that moves the band toward ~385 rows on any useful
  clock is a second verdict source, and this repo has one built and dormant
  (`core/claude_verdicts.py`). Re-supplying it is `GD-23`'s named re-opener for `OB-12`
  increment B, and is now also the precondition for any evidence-side lever on §18's bar. It
  is a decision about how verdicts are minted — evidence policy — and goes through its own
  pre-registration with the §4.4 projection's rules re-read first.
- **The engine-side observation.** `r49`'s own S4 table shows the held-out `p1` pulled toward
  a common value in *both* directions — 0.863/0.873 against realised 0.800 in the band,
  0.862 against realised 1.000 in `ge90`, 0.646 against 0.696 below 0.5. That is the shape of a
  pooled guard prior, §17.6's remark measured on every cell, and it means the band could be
  withheld by the engine tracking its *existing* cell's rate more tightly, with no new family
  at all. It is a hypothesis about proplang's fold; if opened it is **filed as demand with this
  evidence attached** (`M-23`/`GD-14`), never edited from here.
- **The guard question** (`RULINGS` §5) is unchanged and still with the owner; nothing here
  touched a regime.
- **D is unsized.** Its sizing input was to be B's timestamped run; with none bought, the
  `M-32` marks have not yet recorded a gate run. The next gate run — whatever lever earns it —
  sizes D.
- **C's open legs** are unchanged: the boot record's policy name on the next natural restart;
  the baseline arm's spend re-record, priced.

## 7. Method notes

- **A consumer the eight-suite selection missed, caught by CI.** `r41`'s engine-replay
  instrument (`scripts/p0_engine_replay.py`) rebuilds a recorded summary and, by design,
  refuses to *default* an absent field — a reproduction must not invent an input. Every
  pre-r50 record lacks `runner_up_credence`, so it refused them all. Repaired without weakening
  the guarantee: only fields **without a declared default** are required (they are the ones that
  enter the tick), and the test proves the rebuilt tick is byte-identical with the field absent
  or present. Two mutations RED; the full suite (3 239) run before the fix was pushed — the
  lesson being that a new field on a shared type needs the whole suite, not the suites one
  remembers.

- The census ran once, on the committed tree, with the edges printed before the cells; the
  power figures in §3 were computed afterwards from the census artefact and are labelled as
  power, not as a reading.
- The `runner-up` edges say something about the ledger worth carrying: recorded runner-up
  credences are tiny almost everywhere (58% none, 70% ≤ 0.03, max 0.398). A competitor that the temper has
  already halved twice does not show up as a large second credence; it shows up as a smaller
  leader. Any successor family built on "the competitor's credence" inherits that.
