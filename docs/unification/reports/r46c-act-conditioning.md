# r46 leg C — act-conditioning: READING

Criteria K1–K10, three arrangements, five blind predictions and three consequence branches
frozen in
[`r46c-act-conditioning-preregistration.md`](./r46c-act-conditioning-preregistration.md)
before any `src/` change and before any engine probe of this leg ran (`M-3`). Instrument:
`scripts/membrane/act_conditioning.py` (+ `tests/test_act_conditioning.py`). **$0** — engine
CPU on the already-built binaries (arm A `1d008643…`, arm B `71998f65…`), no API call, no
priced run, no restart. Measurement tree pinned `9af0be0…`, clean (`M-28`: every leg's run
stamp records the head, dirty state and the instrument mtimes against its process start).

## The question, and the answer

r45 handed forward: **"can one world both condition on the act and choose it, and if not,
what two-world arrangement is admissible?"** — with leg A's sharpened target bound to it: the
p1 ceiling, not the affordance constant, is what blocks a commit-pricing §18 bar.

**Answer: YES — the *mirrored* arrangement does both.** r45 A4 concluded "the act-conditioned
world **cannot decide**, having no writable name left" — but that held only because r45 put
`act` *itself* into the guard, emptying the menu. The admissible arrangement adds a **separate,
non-writable** name `act-taken` (the recorded historical act) as a guard on the discriminating
grid, and **keeps `act` in the menu**. That world conditions its outcome belief on `act-taken`
(K3) and still chooses an act from the menu (K4) — one world, both jobs. r45's dichotomy was an
artefact of collapsing the two names into one.

**What it does NOT do is lift the commit ceiling.** On the real recorded stream the historical
act carries almost no information about the reaction outcome, so conditioning moves the fold's
`p1` by a median of **1.2 × 10⁻⁵** and lifts **zero** rows over the commit bar that the pooled
fold had not already cleared (K5). Act-conditioning is real and it is inert for this purpose —
the same shape r45's C3 found for the act's role in the backfill.

## Disclosure — instrument defects found and corrected before any verdict

Stated first (`M-4`, `M-25`, the r45-A3 precedent applied to this instrument).

1. **A git-checkout mutation harness wiped the uncommitted instrument rewrite.** The K7
   battery restores each mutation with `git checkout -- <file>`; run against an **uncommitted**
   rewrite, its final restore reverted the file to the last commit, silently discarding the
   rewrite — the prior commit then captured only the test change. Caught by re-reading the
   committed tree (`grep`), re-applied, and **committed before the battery re-ran**. Registered
   as a method note: never run a git-checkout mutation harness over uncommitted work.
2. **Three metrics read a door-refused decide, and the M-25 control could not express its
   own alternative.** On arm B a decide missing a declared name is refused (§ below), so the
   first spellings of K3, K4 and the K2 control — which drove a *plain* (menu-only) decide —
   came back spuriously null on arm B. Worse, the first M-25 inertness control folded a
   **constant-act** stream, which cannot teach conditioning at all: the exact r45-A3 defect
   (a control that cannot represent the alternative it is meant to detect), reproduced in this
   instrument. Corrected to a **teach** stream (act-taken correlated with y) read through the
   **conditional** readout, which supplies `act-taken` and so passes both arms' doors. The
   corrected M-25 control comes back distinct=4 with a real gap (K2 below).
3. **A machine-local engine path was staged and the PII guard caught it.** Arm A lives in a
   worktree under `$HOME`; the default was removed and `--arm-a` made required for the
   both-arm legs (the run stamp records what was passed).

## K1 — admissibility, both arms, every reply read whole

18 cells (3 arrangements × 2 arms × {handshake, evidence, decide}); the mirrored decide
measured twice (with and without the new name — the P4 door fork). `models` moves with the
declaration exactly as r42's enumerator predicts:

| arrangement | arm A `models` | arm B `models` | evidence tick | decide |
|---|---:|---:|---|---|
| shipped | 2393 | 960 | admitted | admitted |
| mirrored (`act-taken` guard added, menu kept) | 2609 | 1128 | admitted | **arm B: REFUSED without `act-taken`; admitted with it** |
| observer (`act` → guard, menu emptied) | 2609 | 1128 | admitted | admitted, but `act = {}` (no choice) |

**The door rule, quoted verbatim** (`M-22`, arm B, mirrored, plain decide):

```
{"error": "tick refused: missing declared ["act-taken"]"}
```

reaching the client as `MembraneError: unparsable reply line: …` — HEAD's refusal line is the
invalid JSON r45 A5 documented; our client repair surfaces it as a legible `MembraneError`, not
a bare `JSONDecodeError`. **P1 confirmed**: both arrangements are wire-admissible at handshake
and on evidence ticks, on both arms — the collision is name-level, as predicted. **P4's door
fork resolves to REFUSED on arm B, admitted on arm A**: arm B enforces "every declared name
covered" on a *decide*, arm A does not — the same arm asymmetry r45 A1 measured. The
consequence is load-bearing: on the deployed engine a mirrored-world decision **must assert a
value for `act-taken`**, which for a fresh decision is a fiction — so the natural object is the
**conditional readout** `p1 | act-taken = v`, not a single "plain" decision.

## K2 — the inertness null, and a control that can actually fail it

| arm | A0: distinct `p1` over four one-point-menu acts | M-25 control (teach → conditional readout, discriminating grid) |
|---|---|---|
| A | **1** (0.504935, all four) | distinct **4** — {1: 0.862, 2: 0.862, 3: 0.137, 4: 0.137} |
| B | **1** (0.390145, all four) | distinct **4** — {1: 0.954, 2: 0.954, 3: 0.061, 4: 0.061} |

**K2 met.** A0 reproduces r45 A2's inertness null on the tree of record (a single-point menu
act never feeds the fold). The M-25 control varies the **act** axis on the discriminating grid
and comes back RED with a real gap that tracks the teach's own split (act ≤ 2 → high, act > 2 →
low) — the alternative the null denies is expressible, so distinct=1 in A0 is a real null, not
a blind instrument.

## K3 — conditioning EXISTS on `act-taken` (P2 confirmed)

Two teach streams that disagree on what `act-taken` predicts (hi: act ≤ 2 → y=1; lo: the same
stream, y flipped), then the conditional `p1` at a fixed query act:

| arm | `p1` after hi teach | `p1` after lo teach | act-identical control (hi folded twice) |
|---|---:|---:|---|
| A | 0.862016 | 0.137984 | byte-identical |
| B | 0.953826 | 0.060871 | byte-identical |

**K3 met.** The two act-distinct streams give distinct `p1` on both arms; the act-identical
control is byte-identical. The fold **conditions on `act-taken`** — #15's missing engine-side
capability (`P(outcome | action, context)`) recovered **seam-side**, because `act-taken` is a
*non-writable* name that legitimately receives evidence. Arm B conditions harder than arm A
(gap 0.893 vs 0.724 at these teach extremes), the same arm ordering r45 A4 measured.

## K4 — selection stays act-unconditional (P3 confirmed)

| arm | chosen act | reply `p1` | `argmax_action(u_bar, p1)` | contract holds |
|---|---|---:|---|---|
| A | gather | 0.501762 | gather | ✓ |
| B | gather | 0.820825 | gather | ✓ |

**K4 met.** Wherever a decide is served, the chosen act equals `argmax_action` at that reply's
own `p1`. Conditioning on `act-taken` does **not** leak into the candidate ranking: the mirrored
world learns `P(y | act-taken)` and still argmaxes the menu independently. This is exactly #15
read forward — a guard differentiates the *outcome belief*, never the *candidate selection* —
and it is why the mirrored world is a coherent "condition and choose" world rather than a
contradiction: the two names do two disjoint jobs.

## K5 — the ceiling, and the bar it must be read against

A prequential fold of the joined verdict universe (`boot_snapshot`'s verdict join with the K9
act field — the SAME join the deployed boot replays), arm B, each row's decide probed **before**
its evidence folds. **$0** (engine CPU, no API). Cost: mirrored pass **1 102 s** wall, pooled
pass **399 s** wall on a box under the owner's own load; the run stamp pins the tree `9af0be0`
clean for the whole run (`M-28`).

**The universe (K6): 250 rows** (decisions ⋈ reactions/verdicts), **0 skipped, 0 refused** —
every conditional probe carries `act-taken` and so clears arm B's door.

**The bar is 0.8369, and it is NOT leg A's 0.897015 — because the bar drifts with reactions.**
The commit bar located by bisecting the deployed `coarse.map_action` under the **live boot
`u_bar`** (`u_wrong = −5.130990`) is **0.836894** — exactly r32's deployed p†. Leg A's
0.897015 came from the **corpus fixtures**' elicited `u_bar` (`u_wrong = −8.710`), and §17.6's
0.899 from the `−8.83` early era. The shadow's boot `u_bar` has run `−8.83` (bar 0.898) →
`−5.94` (0.856) → **`−5.13` (0.8369)** across its 20 boots — the r32 finding that the commit
bar is a moving quantity, seen here directly. So **a §18 bar must be read under the era-matched
`u_bar`, never a fixed 0.897** — and `respond_threshold` for the raw menu is a different number
still (0.9906), published beside but not the target.

| ceiling | value | gap to bar (0.8369) |
|---|---:|---:|
| pooled (deployed world) | **0.862188** | **−0.02529** (exceeds) |
| mirrored conditional `max_v` | **0.862257** | **−0.02536** (exceeds) |

**Both ceilings EXCEED the bar, and 180 of 250 pooled rows clear it.** Under the deployed
(drifted) bar the `p1` ceiling is **not** what an empty commit column is waiting on — 72% of
rows already sit above it. My pooled ceiling 0.862188 reproduces leg A's own new-era ledger max
0.8621 (same `u_bar` era), so this is the same quantity leg A measured, read against the correct
bar.

**Conditioning adds essentially nothing.** The conditional ceiling exceeds the pooled by
**7 × 10⁻⁵** (P5's "at or above" direction confirmed, and only just); per-row the conditional
spread `max_v − min_v of p1|act-taken` is median **1.2 × 10⁻⁵**, max **8.6 × 10⁻⁴**; the
act-value maximising `p1` is `respond` on 241 of 250 rows (a faint "a commit was taken" prior),
`abstain` on the other 9. **Conditioning lifts 0 of 250 rows over the bar that the pooled fold
did not already clear.** On the real stream the recorded act is near-uninformative about the
reaction outcome — the synthetic teach swung `p1` 0.954 ↔ 0.061 (K3), the real act-taken swings
it by ~10⁻⁵.

## Consequence — branch 1's letter met, its ground refuted (the GD-16 shape)

The frozen branch 1 reads: *"Some admissible arrangement conditions AND its recorded-stream
ceiling reaches the mapped commit bar on ≥ 1 row → act-conditioning is a named candidate lever."*
Its **letter is met** — the mirrored conditional ceiling (0.8622) reaches the bar (0.8369) on
180 rows. But its **ground is refuted**: the *pooled* ceiling reaches the bar too, conditioning
adds 7 × 10⁻⁵ and lifts zero rows, so act-conditioning is **causally inert** with respect to
crossing the bar — exactly the shape r45's C3 hit, where a qualifying quantity turned out not to
carry the thing the criterion was written to detect. Neither frozen branch anticipated the fact
that dissolves the disjunction: **the bar had drifted below the ceiling.** Both readings are put
on the record; neither is softened to make the other comfortable (`M-4`). The decision this
forces is recorded as **`GD-21`**.

**Enacted:**

- **Act-conditioning is NOT opened as a successor lever.** It is real (K3) and reachable
  (K1), but inert for the commit ceiling (K5: +7 × 10⁻⁵, 0 rows lifted). Naming it a "candidate
  lever" would be false to the measurement.
- **Leg A's sharpened target is CORRECTED, and a new question is named for the §18 bar.**
  *"The p1 ceiling, not the affordance constant, blocks a commit-pricing bar"* held under the
  corpus bar (0.897) and is **false under the deployed bar (0.8369)**: the engine's fold `p1`
  clears the deployed bar on 180/250 rows, so the ceiling is not the blocker. **What K5 does NOT
  settle** is why the mapped surface's commit column is nonetheless empty under the deployed bar
  — K5 folds and probes `p1`, it does not re-run `coarse.map_action`'s affordance path over the
  live stream. Leg A's standing explanation (the affordance is `gather` 6 654/6 654, so the
  exhausted branch that reads `p1` is rarely reached) is *inferred* here, not re-measured, and
  the deployed bar sitting **below** the ceiling opens exactly the question leg A's 0.897 hid:
  **would some exhausted-gather rows now flip to a commit under the era-matched bar?** That needs
  a mapped-surface pass under the deployed `u_bar` — a leg-A-style census, not this fold — and it
  is handed to whichever checkpoint reads the §18 bar, with the affordance and the gauge (not the
  `p1` ceiling) as the standing candidates for the blocker.
- **Leg D proceeds** (the categorical twin, its own pre-registration).
- **`M-1` is not engaged; nothing is deployed; `GD-16`'s rider is carried** — act-conditioning
  is now measured reachable and real, so any future deployment of the mirrored declaration
  inherits `GD-16`'s re-read; but there is no lever here to deploy.

## K7 — seven mutations, each varying its own claim's dimension (`M-25`)

All RED then GREEN, verified against the **committed** instrument: mirrored_decl's guard row
dropped; act_value re-spelling the projection; observer_tick keeping the menu; ceiling_pass
folding before it probes (moved the fold ahead of the probe decides, not merely ahead of the
p1 read); ceiling_pass silently dropping an unmapped row; locate_commit_bar returning a
constant instead of the deployed rule's true flip; base_decl deviating from the deployed
declaration. Guards live in `tests/test_act_conditioning.py`.

## K9 — the one permitted `src/` change

`BootSnapshot.verdict_actions`: each replay row's recorded `chosen_action`, **index-aligned**
with `verdict_replay`, collected at both append sites (owner and Claude segments) of the *same*
join — so the ceiling leg reads the act off the join it already trusts, never a re-implemented
one (the r45-C3 / `M-7` class). Additive; TDD, both tests RED first; the alignment mutation
(drop the Claude-segment append) verified RED before restore. Nothing else in `src/` changed;
no wire, no declaration, no unit, no restart (K9 met).

## Verdict

| id | criterion | verdict |
|---|---|---|
| **K1** | admissibility both arms, replies whole, refusals quoted | **PASS** — 18 cells; P1 confirmed; the door refusal quoted verbatim |
| **K2** | A0 null (distinct=1) ∧ M-25 control RED on the act axis | **PASS** — 1/1 and distinct=4 with a real gap, both arms |
| **K3** | conditioning existence | **PASS** — distinct streams differ, identical control byte-identical, both arms (P2) |
| **K4** | selection = argmax at the reply's p1 | **PASS** — holds both arms; conditioning does not reach selection (P3) |
| **K5** | the prequential ceiling and its gap to the commit bar | **READ** — pooled 0.862188, conditional 0.862257, both **above** the 0.8369 bar; conditioning +7×10⁻⁵, 0 rows lifted. Branch 1 letter met / ground refuted → `GD-21` |
| **K6** | every universe named with its size at read time | **PASS** — 250 joined rows, 0 skipped, 0 refused, at the stamped read |
| **K7** | every load-bearing predicate RED by mutation, each on its own axis | **PASS** — seven, all RED→GREEN on the committed tree |
| **K8** | costs published; the tree pinned for the whole run | **PASS** — every leg stamped clean at 9af0be0; mirrored 1102 s / pooled 399 s wall, $0 engine CPU |
| **K9** | observation-only; the one additive `src/` change under TDD | **PASS** — `verdict_actions` additive, no wire/restart |
| **K10** | `GD-16`'s rider carried; nothing filed upstream | **PASS** — see below |

## K10 — the standing conditions this leg does NOT discharge

`GD-16`'s rider is live and named: *"if act-conditioning lands, the act stops being inert, C3's
premise becomes live, and GD-16 must be re-read before any further backfill."* **This leg lands
nothing** — the shadow's declaration is unchanged, `act-taken` exists only inside the
instrument. But the leg has now *measured* that act-conditioning is reachable and real, so any
successor that deploys the mirrored declaration inherits `GD-16`'s re-read as a precondition of
its first backfill. `M-23`: nothing is filed upstream — #15 is the engine-side twin and is
already open; this leg's finding is that #15's capability is **recoverable seam-side without an
engine change**, handed forward with its locus, not filed as a new demand.
