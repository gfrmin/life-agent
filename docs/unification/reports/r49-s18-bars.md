# r49 — reading §18's bars: **FAIL**, and the second consecutive FAIL on A3

**Pre-registration**: `docs/unification/reports/r49-s18-bars-preregistration.md`, committed
`3c7a4cf` **before the harness ran** (`M-3`); **Amendment 1** (blind) `6c7e273`. Ten criteria
plus S11, S1/S3 KILL, six blind predictions, four consequence branches. **$0** (engine CPU on
the deployed binary). **Nothing deployed, enabled or swapped** (S10).

> **Status: COMPLETE.** All eleven criteria are read. **S5 FAILs on all three variants** — best
> reading P(Δ>0.05) = **0.301** against the frozen 0.90 bar, Δ̄ **−0.081** [−0.482, +0.205] — and
> **S6 finds a named wrong-commit class made worse** (q2-019, the superset-confirm row), which
> blocks a ship on its own. §17.6 FAILed this same A3 criterion on 2026-08-17 and no A3 read has
> passed since, so the frozen consequence is the **second-consecutive-FAIL** branch: **this STOPS
> for an owner ruling** and a conferral document is prepared rather than a successor opened.
> Two findings sit under the verdict: the point Δ **changes sign with the utility gauge**
> (`GD-21`'s drift decides it), and **`p-none` alone carries the whole policy** — nine of the
> seventeen declared indicators change no action anywhere, three of them never fire at all.

## The correction that comes first: `GD-18` STANDS, and my own recon was wrong

The frozen pre-registration's recon disclosure asserted that `GD-18`'s *"the commit column is
empty on every row ever recorded"* **was already false**. **It is not, and the claim is
withdrawn** (Amendment 1, frozen blind before the amended measurement).

`M-26` — *a column's meaning can depend on the row's kind* — fired on this checkpoint's own
author. The 555 `kind: "enact"` rows I read are the **M3 live lane's**, written 2026-07-20 →
2026-07-22 and **deleted by M5** (`4e5debd`); their known defect is precisely that the writer
*"recorded an agreement pass-through and a probe selection identically"*. A "net −84 commits"
figure derived from them was computed and **discarded before it reached any criterion**.

The `r46` leg A tap writes `mapped_*` onto **`kind: "decide"`** rows, and exactly **one** exists
(2026-09-02T17:38:38): `mapped_effector: gather`, `mapped_echo: false`, `mapped_degraded: null`,
`p1 = 0.8621320287400522`. The tap is not broken — the bridge is up and `gate` rows arrived
today; **only one mirrored decide has occurred since the tap landed**, so the live stream cannot
support a mapped-surface census. That single row is itself the mechanism in miniature: `p1`
**above** the deployed bar, mapped to `gather` anyway, because an unapplied VOI transform
pre-empts the argmax.

## S3 (KILL) — the commit rule has two spellings, and they are one relation

`LR.commits_respond` takes `max` over the non-`gather` actions; `coarse._gather` iterates
`world.AFFORDANCES` from `abstain` with a strict `>`. Over a **200 001-point** grid on [0, 1] at
the boot Ū: **0 disagreements**, both flipping at the bit-identical
**0.8368942119315517**, their iteration orders coinciding (`AFFORDANCES` order == `eu_by_action`
key order). **Blind prediction 1 confirmed**; the KILL does not fire. The check was worth
running anyway: M6's `_lattice_join` was exactly this shape — two declarations of one relation —
and survived on §-numbers.

## S2 — the era-matched bar, published beside the one it replaces

| bar | value | provenance |
|---|---:|---|
| §17.6's commit bar | 0.899 | boot Ū of 2026-08-17 (`u_wrong` −8.83) — **era-stamped, not current** |
| leg A / `GD-18`'s | 0.897020 | the **m5-base fixtures'** elicited Ū (`u_wrong` −8.710) |
| **deployed commit bar** | **0.8368942119315517** | the boot row's Ū (`u_wrong` −5.130990) — `GD-21`'s required reading |
| full-menu respond bar | 0.9906339522695138 | `world.respond_threshold` — includes `gather`; `r48`'s necessary bar |

## S11 — `GD-21`'s handed census: YES, and by a wide margin

`GD-21` handed this checkpoint one question: *"whether the deployed bar flips any
exhausted-gather row to a commit."* Run over leg A's population — the **605 recorded `/decide`
exchanges across 102 m5-base fixtures** — with leg A's deployed rule bound, not restated, and
**one further declared substitution**: the payload's `u_bar` replaced by the deployed boot Ū.

**116 of 605 exchanges (19.2%) reach `_gather`'s exhausted argmax**; the other 489 carry an
unapplied VOI transform and never get there. Among those 116 the terminal act is the step
function leg A described, and it flips at the bar:

| Ū in the payload | commit bar | commits at the ledger max `p1` = 0.8706074 |
|---|---:|---:|
| **CONTROL** — the fixtures' own (leg A's read) | 0.897020 | **0 / 116** |
| **SUBSTITUTED** — the deployed boot Ū (`GD-21`'s) | 0.836900 | **116 / 116** |

The control **reproduces leg A exactly** (0 commits at every swept `p1` up to the ledger
ceiling, committing only at 0.897020 — above anything ever recorded), which is what makes the
treatment attributable: the arms differ by the substitution alone and flip at exactly the
predicted threshold.

**The second factor, measured rather than assumed.** Across the whole ledger, **1 276 of 6 873**
rows carrying a `p1` exceed the deployed bar (**18.6%**; 1 130 of 3 898 `decide` rows = 29.0%),
and **0 of 6 873** exceed the fixture bar. Max recorded `p1` **0.8706074320569814**.

**The two factors are NOT multiplied.** The fixtures carry no engine `p1` and the live rows
carry no fixture payload, so the joint distribution is not observable from either population.
The one row where both are observed together — the leg A tap's single decide — has `p1` above
the bar and was pre-empted into `gather`. Stated as the open quantity it is.

**What this settles.** `GD-18`'s scope sentence — *a §18 bar on this surface "may not be read as
evidence about a commit… because its commit column is empty on every row ever recorded"* —
rests on a bar `GD-21` retired. At the era-matched bar the column is **not** empty in principle:
every exhausted row commits once `p1` clears 0.8369, and 18.6% of recorded `p1` does. `GD-18`'s
own hedge was exact and is what survives: the ceiling is **empirical, not structural**.

**Blind prediction 6 is REFUTED.** It said "non-zero but single-digit", expecting pre-emption to
remove most of the window. Pre-emption is real (489 of 605 never reach the argmax) but it acts
*before* the population is formed, not inside it: among rows that do reach the argmax the commit
is unanimous, 116 not single digits.

## S1 — the corpus is pinned

Launched with `--expect-ticks 250 --expect-questions 141`; the harness refuses before any engine
work if the keyed replay differs. §17.6 ran **193 ticks / 84 questions**, so this is a **larger,
different corpus** and its numbers are not directly comparable to §17.6's — recorded here, not
discovered in the reading.

## S8 — arms and trees, pinned for the whole run (`M-28`)

| what | value |
|---|---|
| engine (arm B, deployed) | `~/.local/bin/proplang-host` |
| engine sha256 | `71998f6556f53314affd089a41eff5eb2b5cd749e56661f702989f744b8cf3c6` |
| repo tree | `6c7e273` (branch `r49-s18-bars`) |
| boot Ū | `u_wrong` −5.130990272278651 · `u_abstain` 0.0 · `u_correct` 1.0 |
| corpus | 250 keyed ticks / 141 questions; S11's population 605 exchanges / 102 fixtures |
| baseline | `eval/fairfight/ff-v2-baseline-m3off`, arm `baseline` (`ask.answer_via_executor`, 104 rows, life-agent `45c7212`, recorded 2026-07-19) |
| harness | `scripts/membrane/p3_gate.py`, frozen for the run — 3 variants × 141 questions = 423 engine spawns |
| artefacts | `$LIFE_AGENT_KB/eval/p3-r49/` (`a1_a2.json`, `a3_gate-*.md`, `a3_meta-*.json`, `a3_paired-*.jsonl`); run log `~/.cache/r49/gate.log` |

**`M-28` disclosure.** Two commits landed on the branch *while* the run was in flight —
`980eb6b` (the partial reading) and `c97a032` (the ROADMAP/CLAUDE.md tails). Both are
**docs-only**: `git diff --name-only 6c7e273 c97a032 -- src scripts` returns **0 files**, so the
tree the 423 engine spawns imported is byte-identical to the pinned one for the whole 14 hours.
Recorded because `M-28` is about the middle of a run, not only its launch.

**A read-time re-pin of S1.** The covariate census in S4 re-read the ledger *after* the run and
returned **250 ticks / 141 questions** — the same window the harness refused to run without. The
corpus did not move under the measurement.

## S4 — the held-out policy, per variant (the reading; there is no pass condition)

Grouped leave-one-out over the pinned corpus: one fresh engine per question, trained on the
other 140 questions' ticks, priced on that question's own. 238 of the 250 keyed ticks carry a
`leader_credence` and are probe-eligible; the other 12 are not scored.

**The break-even identity — which is where this whole reading turns.** Under a utility with
`u_correct = 1`, a committed answer pays `p·1 + (1−p)·u_wrong`, zero at `p* = −u_wrong /
(1 − u_wrong)`. The deployed boot Ū's `u_wrong` = −5.130990272278651 gives **p\* = 0.836894** —
which *is* the commit bar, by construction. Any bucket whose realised correctness is 0.80 is a
loss of −0.226/question no matter what `p1` the engine assigns it. The identity, not the
engine, sets what the policy must clear.

### FULL — families `n-candidates`, `leader-credence`, `p-none`, `n-obs`, `flags` (17 indicators)

| | value |
|---|---:|
| policy EU/q @Ū | **+0.2747** |
| respond-all @Ū | −0.2623 |
| abstain-all | 0 |
| P(U) EU/q | **−0.0500** [−0.1181, +0.0167] |
| `p1` spread | 0.5968 |
| responded | 188 / 238 |

| leader bucket | n | correct | mean `p1` | respond | EU/q |
|---|---:|---:|---:|---:|---:|
| <50 | 46 | 0.696 | 0.6462 | 27 | +0.320 |
| 50–70 | 68 | 0.647 | 0.6236 | 37 | −0.087 |
| 70–80 | 15 | 0.800 | 0.8632 | 15 | −0.226 |
| 80–90 | 40 | 0.800 | 0.8730 | 40 | −0.226 |
| ≥90 | 69 | 1.000 | 0.8619 | 69 | +1.000 |

The policy beats both null policies at the deployed Ū, and the shape is legible: it earns in the
top bucket (69 rows, perfect), it earns by *withholding* 19 of 46 in the bottom bucket, and it
gives back −0.226 apiece on the 55 rows in 70–90 where it commits on everything at a realised
0.800 — just under the 0.837 it needs. Under the utility **posterior**, the same policy reads
−0.0500 with an interval straddling zero.

### leader-credence-only (5 indicators) — the degenerate coarsening

| | value |
|---|---:|
| policy EU/q @Ū | **−0.2623** — *identical to respond-all* |
| P(U) EU/q | **−1.0577** [−1.2246, −0.8944] |
| `p1` spread | 0.1239 |
| responded | 238 / 238 |

| leader bucket | n | correct | mean `p1` | respond | EU/q |
|---|---:|---:|---:|---:|---:|
| <50 | 46 | 0.696 | 0.8584 | 46 | −0.866 |
| 50–70 | 68 | 0.647 | 0.8584 | 68 | −1.164 |
| 70–80 | 15 | 0.800 | 0.8584 | 15 | −0.226 |
| 80–90 | 40 | 0.800 | 0.8584 | 40 | −0.226 |
| ≥90 | 69 | 1.000 | 0.9805 | 69 | +1.000 |

`mean p1` is **0.8584 in four of the five buckets, to four decimals** — the coarsening leaves the
engine one number for everything but the top bucket, and that number sits above the bar, so the
policy commits on all 238 and *is* respond-all. **The covariate lattice is not decoration on a
bar-clearing engine: strip it and the policy has nothing left to withhold with.**

### leader-credence+p-none (8 indicators) — identical to FULL, to eight decimals

Every published quantity is **identical to FULL**: same 188/238, same per-bucket counts, same
policy EU/q to 16 digits, and `a3_paired-FULL.jsonl` is **byte-identical** to
`a3_paired-leader-credence+p-none.jsonl`. The sole difference anywhere is `mean_p1`, at the
**eighth decimal** (e.g. 0.6461723452854478 vs 0.6461723274798832).

So the nine extra indicators — `n-candidates` ×3, `n-obs` ×3, `flags` ×3 — move `p1` by ~10⁻⁸
and change **no action on any of 238 ticks**. A read-side census of the same pinned corpus
(the harness's own `features_for`, not a re-implementation — `M-7`) says why in part and
deepens the finding in the rest:

| family | fires on | ever-firing indicators | modal cell |
|---|---:|---:|---|
| `n-candidates` | 250/250 | 3/3 | `=1` 0.532 |
| `leader-credence` | 238/250 | 5/5 | `=ge90` 0.276 |
| `p-none` | 238/250 | 3/3 | `=lt20` 0.504 |
| `n-obs` | 250/250 | 3/3 | `=1to2` 0.532 |
| `flags` (`era-split`, `owner-scoped`, `grow-pass`) | **0/250** | **0/3** | — |

**Three of the seventeen declared indicators never fire at all** — the whole `flags` family is
dead on this corpus, and it still costs model space (960 models for FULL vs 456 for
`leader-credence+p-none` vs 288 for `leader-credence` alone, measured by handshake). The other
two families are the more interesting result: `n-candidates` and `n-obs` both vary
substantially and still move **zero** actions once `leader-credence` and `p-none` are present.
**`p-none` is the family that creates the policy**; it is the difference between respond-all and
188/238. (The census re-read the ledger at read time and returned **250 ticks / 141 questions** —
S1's window, unmoved across the whole 14-hour run.)

## S5 (THE BAR) — **FAIL**, on all three variants

| variant | verdict | P(Δ > 0.05) | Δ̄ | 90% interval | answer rate (membrane · baseline) | disagreement |
|---|---|---:|---:|---|---|---:|
| FULL | **FAIL** | **0.301** | −0.081 | [−0.482, +0.205] | 0.67 · 0.35 | 24/75 |
| leader-credence+p-none | **FAIL** | **0.301** | −0.081 | [−0.482, +0.205] | 0.67 · 0.35 | 24/75 |
| leader-credence-only | **FAIL** | **0.000** | −1.479 | [−2.297, −0.765] | 1.00 · 0.35 | 49/75 |

Gate ≥ 0.90 at δ = 0.05, 20 000 draws, seed 8675309, against `eval/fairfight/ff-v2-baseline-m3off`
arm `baseline` — the harness's frozen defaults, unchanged. Joined 75 questions (membrane-only 55
live/non-v2 ids; baseline-only 29).

**The failure has an unusually simple shape, and it is not the shape that was predicted.** On the
best variant:

| membrane × baseline | n | mean Δ at gate Ū |
|---|---:|---:|
| report × abstain | 24 | −0.250 |
| report × report | 26 | +0.000 |
| abstain × abstain | 25 | +0.000 |
| **abstain × report** | **0** | — |

The membrane arm's report set **strictly contains** the baseline's: there is not one question
where the baseline commits and the membrane withholds. On the 26 shared commits the two arms
never disagree about correctness. **The entire differential is 24 marginal commits, 21 right and
3 wrong — 0.875.** Nothing else in the join contributes anything.

### Disclosure 1 — the verdict is set by *which* Ū prices it, and the reach falls between the two

The held-out policy commits under the **deployed boot Ū** (`u_wrong` −5.130990, break-even
**0.836894** — the bar it was measured at, `GD-21`'s required reading). The A3 gate prices under
the **utility posterior** whose mean the gate itself prints: `u_wrong` **−8.9993**, break-even
**0.899993**. The marginal reach's realised correctness is **0.875**, which sits *between the two
break-evens*. Arithmetic on the gate's own published action table (its report states the realised
utility is affine in the latents given the actions, so this is restatement, not re-derivation):

| gauge | break-even | marginal 24 rows | EU membrane | EU baseline | point gap |
|---|---:|---:|---:|---:|---:|
| gate Ū (`u_wrong` −8.9993) | 0.899993 | −0.2499/q | +0.0000 | +0.0800 | **−0.0800** |
| deployed boot Ū (`u_wrong` −5.130990) | 0.836894 | +0.2336/q | +0.2579 | +0.1832 | **+0.0748** |

**The point gap changes sign with the gauge.** This is stated as exactly what it is: the *point*
at-Ū gap, not a gate reading — no MC over a posterior centred on the boot Ū was run, and **no
claim is made that the gate would PASS at the deployed Ū.** What is established is that this
FAIL is not a property of the engine alone. `GD-21`'s bar drift is not a footnote to this
checkpoint; on these numbers it is the verdict.

### Disclosure 2 — Δ_spend is 0.000 structurally, and cannot be repaired from the record

Both arms price at $0.0000: `Δ_answers = −0.080 · Δ_spend = 0.000`. The membrane arm genuinely
spends nothing — it is an offline policy over already-recorded ticks. The baseline's zero is a
**gap in the artefact**: all **104/104** rows of `ff-v2-baseline-m3off` carry `cost_usd: null`
with `cost_status: "partial"`, and their token counters (`in_tokens`, `out_tokens`,
`cache_*_tokens`, `asks_issued`) are **all zero with an empty `model_tier_mix`** — so unlike
r28's π\*, this arm's spend is not merely unpriced but **unimputable**. r28 found 96% of run 18's
adoption margin lived in the price term; here that term is absent by construction, and its
direction would favour the membrane arm (the baseline is a live executor lane, the membrane arm
is a replay). **Bounded honestly, and the first bound I wrote was wrong.** At the recorded
`lambda_usd` = 1.33108, a mean spend difference of only **$0.0376/question** ($3.91 over 104
questions) moves Δ by a full δ = 0.05 — and era-contemporary priced runs sit *at* that scale, not
below it (run 6/7's typed arm $5.56/104 = $0.053/q; run 9 $0.039/q; run 10 $0.032/q). So the
missing term is **potentially material to Δ̄**, in the membrane arm's favour, and the earlier
draft's "fractions of a cent" was an unchecked extrapolation from the *post-M4* runs (run 18's
$0.0036/q), three pricing eras after this baseline was recorded. What it is **not** is plausibly
decisive for the verdict: a +0.05 shift moves Δ̄ from −0.081 to ≈ −0.03 with the interval carried
along (today's 90% upper end is +0.205), which does not put 0.90 of the posterior above +0.05.
Stated as it is — **unmeasured, plausibly worth about one δ, and not enough to carry the bar** —
and this reading does not lean on it in either direction.

## S6 — the hard clause (`M-1`): a named wrong-commit class **is** made worse

| arm | commits | correct | wrong | wrong rows |
|---|---:|---:|---:|---|
| membrane (FULL / lc+p-none) | 50 | 45 | 5 | q2-002, **q2-018**, **q2-019**, **q2-040**, q2-082 |
| baseline | 26 | 24 | 2 | **q2-018**, **q2-040** |
| membrane (leader-credence-only) | 75 | 57 | 18 | the 5 above + 13 more |

The membrane's wrong set **strictly contains** the baseline's — the two shared wrongs (q2-018,
q2-040) are inherited identically, and the three new ones (q2-002, **q2-019**, q2-082) are all in
the marginal-reach block where the baseline abstains.

**q2-019 is a named class.** It is the truncated-leader **superset-confirm** row: the defect that
made `corroborate_audit` a NO-GO, one of run 13's four wrong commits, and a row that run 14
converted **wrong → withheld** — still its disposition in the newest gate record (`gate-20260831T195752`, run 23: `typed.action = abstain`), verified for this report rather than carried. This checkpoint's
held-out policy commits it **wrong**. Under `M-1`'s hard clause that blocks a ship on its own,
independently of S5. It does not bind anything today — **this checkpoint ships nothing in either
branch, by its own pre-registration** — but it is recorded as a second, independent reason the
answer is no, and as a live constraint on any successor that proposes this policy as a lever.

## S7 — commit count and per-commit correctness

The membrane arm commits **24 more times than the baseline** on the joined set — far above
§6.13's wobble floor of 2, so `GD-8`'s "may not be read as a benefit" caveat does not bite and
the count is readable. It is readable as a **cost**: those 24 commits are 21 correct and 3 wrong
(0.875), worth **−0.250/question at the gate's gauge** and **+0.234/question at the deployed
one**. Per-commit correctness across the whole membrane arm is 45/50 = 0.900; the baseline's is
24/26 = 0.923 on 26 commits. The coarsened arm commits on all 75 at 57/75 = 0.760 and loses
−1.48/question.

## Blind predictions, scored

| # | prediction | outcome |
|---|---|---|
| 1 | S3 finds the two commit-rule spellings agree | **CONFIRMED** (published in the partial reading) |
| 2 | commits on more than zero ticks but **single digits, not tens** | **REFUTED, and by two orders** — 188 of 238 probe ticks commit; 50 of 75 joined questions report |
| 3 | A3 FAILs | **CONFIRMED in the letter, its ground REFUTED** — it said the failure would come from the engine "still abstaining on the large majority" with "a handful of new commits"; the engine abstains on a third and makes 24 new commits. The `GD-16` shape again |
| 4 | it fails **by abstention, not over-assertion**, at a margin **closer** than §17.6's −0.078 | **REFUTED on both halves.** It fails purely by over-assertion — there are **zero** abstain×report rows, so abstention contributes exactly nothing to Δ. And Δ̄ −0.081 is marginally *worse* than −0.078, not closer (the magnitudes are within 0.003, so the level was well predicted; the sign of the movement was not) |
| 5 | cost dominated by **fold depth**, not tick count; hours; transient unit | **letter met, ground untested.** 14h02m as a transient `systemd --user` unit, as required. But depth (~249 train ticks) and tick count (250) were held *fixed* across the three variants while cost moved ~4×; what varied was **model space** (960 / 456 / 288). `GD-17`'s depth finding is not contradicted — it simply was not the axis this run varied |

## Cost, and one thing the instrument could not tell me

`r49-gate.service`: **14h 01m 54.716s wall, 13h 35m 06.727s CPU** (96.8% of one core — the
harness is serial), 96.3 MB peak, 423 engine spawns, **$0** (local engine, no model calls).

Per-variant cost attribution is **unavailable**: the harness does not timestamp its own phase
boundaries and its stdout carries no clock, so the only directly measured rate is the third
variant's tail — 28 spawns between two wall-clock observations at 21:31:42 and 22:40:13 =
**146.8 s/spawn** — which extrapolates to ~5h45m for that variant and leaves ~8h17m for the
other two, jointly and not separably. That gap is registered as **`M-31`**, and it is not
cosmetic: the successor plan for a bar read of this size is a **parallel harness** (the 423
spawns are independent by construction — one fresh engine per question, no shared state), and
sizing it needs per-arm costs this run cannot supply.

## The consequence, enacted exactly as frozen

The pre-registration's S5-FAIL branch reads, verbatim: *§18's rule is iterate, not park — except
that §17.6 (2026-08-17) already FAILed this same A3 criterion on both its arms, and no A3 read
has passed since. A FAIL here is therefore the second consecutive FAIL on the same frozen
criterion, which §18 says stops for an owner ruling.*

**It stops.** A conferral document — `docs/unification/conferrals/s18-bar-conferral.md` — is
prepared with the evidence, the options and their prices. **No successor rung is opened
unilaterally**, `M-1` is not engaged (nothing ships), no bar is loosened (§17.6's rule — *a
sharper `p1`, never a softer bar* — and `M-4` both forbid it), and nothing is deployed, enabled
or swapped.

## S9 — PII

Aggregates, register ids, opaque hashes and float bars only; no question text, no candidate
string, no corpus value enters this report.

## S10 — nothing deployed, enabled or swapped

No `src/` change. Reading a bar is not enacting a migration: §18's terminus is §11's exit
criteria, and a swap needs its own pre-registration.
