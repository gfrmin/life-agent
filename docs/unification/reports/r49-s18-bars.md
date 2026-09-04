# r49 — reading §18's bars: READING (in progress)

**Pre-registration**: `docs/unification/reports/r49-s18-bars-preregistration.md`, committed
`3c7a4cf` **before the harness ran** (`M-3`); **Amendment 1** (blind) `6c7e273`. Ten criteria
plus S11, S1/S3 KILL, six blind predictions, four consequence branches. **$0** (engine CPU on
the deployed binary). **Nothing deployed, enabled or swapped** (S10).

> **Status.** S1, S2, S3 and S11 are read. S4–S7 wait on the A3 harness run (`r49-gate`,
> a transient `systemd --user` unit — one fresh engine per question × 3 variants = 423 spawns).

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
| baseline | `eval/fairfight/ff-v2-baseline-m3off`, arm `baseline` |

## S4 · S5 · S6 · S7 — pending the A3 run

<!--PENDING-GATE-->

## S9 — PII

Aggregates, register ids, opaque hashes and float bars only; no question text, no candidate
string, no corpus value enters this report.

## S10 — nothing deployed, enabled or swapped

No `src/` change. Reading a bar is not enacting a migration: §18's terminus is §11's exit
criteria, and a swap needs its own pre-registration.
