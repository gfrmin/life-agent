# r49 — reading §18's bars: PRE-REGISTRATION

**Frozen before the harness runs** (`M-3`). Ten criteria (S1 and S3 carry KILL clauses), five
blind predictions, four consequence branches. Committed before any measurement.

## The question

§18 names three bars and rules the migration **gated-mandatory**: the bars pace the swap, a FAIL
means iterate, and *"a second consecutive FAIL on the same frozen criterion stops for an owner
ruling"*. They have been **readable but never read** since `GD-10` opened Arc C. This checkpoint
reads them.

**Which bars, precisely** (§18's list, un-loosened):

1. **The p3 commit bar** — §17.6's, but **era-matched**: `GD-21` rules that a commit-pricing bar
   *"must be read under the era-matched `u_bar`, never a fixed 0.897"*. Read from the boot row
   it is **0.837**, not §17.6's 0.899.
2. **The §8-class priced differential gate** (the harness's A3) against the credence baseline.
3. **The hard clause** (`M-1`): no lever ships while it makes a named wrong-commit class worse.

## Scope — this reads the BINARY world, and says so

Two of the six published preconditions bind a **categorical** bar, not this one: `r48`'s K-cap
(k ≤ 3, an unbounded *categorical* episode budget) and `r48`'s finding that the categorical
commit surface is empty for the same reason the binary one is. The §18 harness runs the
`said@1` binary world, whose episode budget is bounded. **A categorical §18 bar is a separate,
later question, gated on the K-cap** — it is not attempted here, and nothing in this reading may
be quoted about it.

The other four are disposed **by construction**, not by assertion, and S2/S3 verify it:

- **C3's gather constant** (`GD-16`) — the raw affordance is not the surface being priced. The
  harness prices through `LR.commits_respond`, the restricted argmax with `gather` deleted,
  which is `coarse._gather`'s own exhaustion rule.
- **`GD-18`'s mapped surface** — that restricted argmax *is* the mapped surface's commit branch.
- **`GD-21`'s bar drift** — the harness reads the boot Ū from the shadow log
  (`R.latest_boot_u_bar`); era-matching is structural, and `--u-bar-override` is
  reproduction-only and is **not** used.
- **Leg D's spec** (`GD-22`) — a categorical enablement requirement; `r47` built it; out of scope
  here per the paragraph above.

## Recon disclosure — what was already seen before this was frozen

`M-3` protects blindness, and blindness partly lost is disclosed, never pretended. Establishing
*which* instrument reads §18's bars required inspecting the live stream, and that inspection
revealed a headline quantity. Stated here so nothing below is presented as blind that is not:

- The live `enact` tap holds **555 rows**, every one `action: gather` (C3 holds on the live
  stream too). **138** carry `degraded: gather_exhausted` — the restricted argmax fired — and
  their mapped effectors are **abstain 135 · ask_clarify 2 · report 1**. Max recorded `p1`
  **0.8706074152883231**; 4 rows exceed 0.836894.
- **`GD-18`'s "the commit column is empty on every row ever recorded" is therefore already false
  as of this writing** — it has one row. `GD-18` said the ceiling was *empirical, not
  structural*, and the empirical fact has moved. **One row is below §6.13's wobble floor of 2**,
  so `GD-8`'s precedent binds: it may not be read as a benefit.
- The keyed replay reads **250 ticks / 141 questions** (§17.6 ran 193 / 84), the boot Ū is
  `u_wrong −5.13099 / u_abstain 0.0 / u_correct 1.0`, the effective commit bar is **0.837**
  against a full-menu bar of **0.9906339522695138**, and `LR.DEFAULT_ENGINE` is arm B.

None of this says what the **gate** reads. Predictions below are confined to quantities the
recon did not expose.

## Criteria (S1–S10; S1 and S3 carry KILLs)

- **S1 (KILL) — the corpus is pinned before any engine work.** The run is launched with
  `--expect-ticks 250 --expect-questions 141`; the harness refuses before probing if the keyed
  replay differs. A ledger that moved mid-checkpoint is a different corpus, and re-cutting the
  pre-registration is the only licensed response (`M-28`).
- **S2 — the era-matched bar, published beside the one it replaces.** Report the effective
  commit bar from the boot Ū, the full-menu bar, and §17.6's 0.899, together. No pass condition;
  publishing the substitution is the point.
- **S3 (KILL for quoting the bar as one number) — the commit rule has two spellings; verify they
  are one relation.** `LR.commits_respond` takes `max` over the non-`gather` actions;
  `coarse._gather` iterates `world.AFFORDANCES` from `abstain` with a strict `>`. Verify they
  agree on the commit predicate across `p1` on a dense grid at the boot Ū. **Any disagreement is
  an M6-class finding** — two declarations of one relation, the `_lattice_join` shape — published
  as such, with the bar then read on `coarse._gather`'s spelling (the deployed decision path).
- **S4 — A1/A2, the held-out policy, published whole.** Policy EU/q at Ū and under P(U) with its
  interval, commits/n, and per-bucket correctness, for FULL and both coarsened variants. **No
  pass condition** — it is the reading.
- **S5 — A3, the §8-class differential gate. THIS IS THE BAR.** P(Δ > 0.05) ≥ **0.90** against
  the credence baseline (`eval/fairfight/ff-v2-baseline-m3off`, arm `baseline`) on the joined
  questions, 20 000 draws at seed 8675309 — the harness's frozen defaults, unchanged. PASS/FAIL.
- **S6 — the hard clause (`M-1`).** Enumerate the engine arm's wrong commits on the joined set
  and compare against the baseline's. **A named wrong-commit class made worse blocks any ship
  regardless of S5**, and this checkpoint ships nothing either way.
- **S7 — the commit column, counted rather than assumed.** Report the gate's own commit count and
  the correctness of each commit. Below the §6.13 wobble floor of **2** the count is published
  **and may not be read as a benefit** (`GD-8`). This criterion has no pass condition; it exists
  so a non-empty column is not silently upgraded into evidence.
- **S8 — arms and trees pinned for the whole run** (`M-28`): engine path + sha256, repo HEAD and
  dirty state, boot Ū, corpus counts, recorded in the artefacts before the reading is believed.
- **S9 — PII-clean.** Aggregates, register ids and opaque hashes only; no question text, no
  candidate string, no corpus value in tree.
- **S10 — nothing is deployed, enabled or swapped.** Reading a bar is not enacting a migration:
  §18's terminus is §11's exit criteria, and a swap needs its own pre-registration. No `src/`
  decision-path change is made by this checkpoint.

## Blind predictions (reasoning only — the harness has not run)

1. **S3 finds the two spellings agree.** Both are strict-improvement argmaxes over the same
   `W.eu_by_action` dict; a divergence needs an exact tie, which the deployed Ū's constants make
   unlikely at grid resolution. Predicting agreement, and predicting that the check is still
   worth running because M6's `_lattice_join` had exactly this shape and survived on §-numbers.
2. **The gate commits on more than zero ticks but on few** — §17.6 committed **0/190** at bar
   0.899; the bar has moved 0.062 in the permissive direction and the ledger's recorded `p1`
   reaches 0.8706, so some ticks should now clear. I expect single digits, not tens.
3. **A3 FAILs.** The engine's policy will still abstain on the large majority against a baseline
   answering ~0.35 of the joined set, and a handful of new commits cannot carry Δ over 0.05 at
   90% posterior mass.
4. **If it FAILs it FAILs by abstention, not over-assertion** — §17.6's mode, not §17.5's — and
   the margin is **closer** than §17.6's Δ̄ −0.078 because the bar moved permissively.
5. **Cost is dominated by fold depth, not tick count** (`GD-17`): LOO probing at depth ≤ 250
   across three variants runs in tens of minutes to hours, and the run is launched as a transient
   `systemd --user` unit (run 16's registered lesson), never as an agent-session task.

## Consequence branches (frozen before the reading)

- **S5 PASSes and S6 is clean** → the first §18 bar is cleared. Publish; **nothing deploys on
  this reading alone** — §18's terminus is §11's exit criteria, which opens as the successor rung
  under its own pre-registration.
- **S5 FAILs** → §18's rule is *iterate, not park* — **except** that §17.6 (2026-08-17) already
  FAILed this same A3 criterion on both its arms, and no A3 read has passed since. A FAIL here is
  therefore the **second consecutive FAIL on the same frozen criterion, which §18 says stops for
  an owner ruling.** This reading is frozen strictly: **it STOPS, and a conferral document
  (evidence + options + prices) is prepared for the owner rather than a successor being opened
  unilaterally.** The register determines this fork; it is not a preference.
- **S3 finds a disagreement** → publish the M6-class defect, read the bar on `coarse._gather`'s
  spelling, and open the unification as a successor. It does not void S5.
- **S1 refuses** → the ledger moved; re-cut the pre-registration for the new window rather than
  reading over it. No engine work is bought.
- **In every branch**: nothing is deployed, `M-1` is not engaged by a reading, and no §18 bar is
  loosened — §17.6's rule (*a sharper `p1`, never a softer bar*) and `M-4` both forbid it.

## Scope, explicit

This does **not** re-open the utility gauge (`u_abstain` remains owner-only, priced in its own
conferral), does **not** enable or price the categorical world, does **not** file anything
upstream, and does **not** swap any seam. `M-1`'s hard clause is not engaged: no lever ships from
this checkpoint at all.
