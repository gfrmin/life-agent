# Conferral — the r09b sweep failed its own S1: what carries the wrong rows, and what now?

**Date:** 2026-08-24. **Status: RULING REQUIRED.** Requested by the frozen consequence of
r09b's C3 ("any failure → STOP and re-confer; run 14 is not fired") — enacted.

## Context

r09b (rulings 2026-08-24, `docs/unification/conferrals/run13-join-conferral.md`) restored
the r09 JOIN and added two tempers for run 13's four wrong rows: **T1** (strict-span guard
on containment confirms — the q2-019 superset-confirm class) and **T2** (nested-dependence
collapse of stacked same-candidate synthesised confirms — the diagnosed carrier of all
four). Both landed under TDD on the `r09b-tempered-join` branch (suite 2660 green). The
pre-registered C3 sweep — `scripts/replay_audit.py` deployed-only on run 13's own record,
$0, drift acknowledged — has now read:

| criterion | frozen bar | read | verdict |
|---|---|---|---|
| S1 | all four wrong rows flip | **0 of 4** (2 cold-unreadable, 2 unchanged) | **FAIL** |
| S2 | collateral ≤ 10 | 3 | PASS |
| S3 | blocking row stays repaired | yes (n_obs 5, the gold) | PASS |

Run 14 was **not** fired. The r09b branch is unmerged; master keeps the r09-reverted
state; the §6.12 deployment block stands. Full reading:
`docs/unification/reports/r09b-tempered-join.md`.

## Evidence — what the wire actually shows ($0 diagnostics, sweep's own warm staging)

The temper executed (3 rows differ from the record). The fail is a mis-target, and the
pre-registration's diagnosis is refuted:

1. **T2's signature lives on the CORRECT rows.** The stacked-synthesised-confirm pattern
   appears on the three collateral rows (q2-002, q2-057, q2-087), where the stack was
   reinforcing the right answer; T2 collapses it and each correct report drops to abstain.
   T2's total measured effect: 3 regressions, 0 repairs.
2. **q2-105 — in-document repetition inflation.** The competitor is carried by twelve
   observations from ONE document, ONE reported value, identical/near-identical quotes:
   one attestation counted twelve times (boilerplate/page-repetition). §5's exact-quote
   key cannot collapse the near-duplicate variants; T2 (synthesised-only) never touches
   document-carried rows. The committing view's n_obs 13 = these 12 + the deliberate
   re-mint. This is the corroborate audit's carrier-count-inflation class, now observed
   INSIDE a single document.
3. **q2-071 — a grounded 2:1 conflict amplified by covariate inflation.** One grounded
   observation carries the gold, two carry the competitor (three distinct documents), and
   one synthesised confirm of the competitor is minted at authority 1.0 / subject 1.0 —
   ABOVE the grounded carriers' 0.85 / 0.525. A re-read confirm outranks everything it
   re-read. The run-9 competition temper cannot fire here (different documents — no shared
   quote window), and time_factor is uniform across the carriers, so the date projection
   does not separate them.
4. **q2-018, q2-019 — cold by the pin's construction.** Their derivations were minted
   DURING run 13; criterion 2 truncates staging at the run's start, so a second pass over
   warmed staging leaves both cold. T1's effect on q2-019 is structurally unreadable at
   $0 — only a priced run reads it. q2-018's mechanism remains unread.
5. **Splice pricing of the unfired run 14** (pin reproduced 0.895/+0.424; artefact
   `~/.cache/life-agent/r09b/splice-sweep-evidence.md`):

   | scenario | P(Δ>0.05) | Δ̄ | ruling-4 verdict |
   |---|---|---|---|
   | temper as measured (collateral enacted, colds unfixed) | 0.879 | +0.395 | FAIL — worse than run 13 |
   | + T1 fixes q2-019 live | 0.940 | +0.482 | FAIL — 3 wrong commits remain |
   | + q2-018 also flips | 0.976 | +0.569 | FAIL — 2 wrong commits remain |

   Every scenario keeps q2-071 + q2-105 as wrong commits, so **the zero-wrong-commit
   conjunct fails regardless of the δ/level read**. The binding constraint is those two
   rows, and the sweep saved both the spend and a wrong deploy.

## Options

**A. Open r09c — re-target the temper at the two named wire mechanisms.** Keep T1
(unfalsified; targets q2-019's class; readable only priced). **Drop T2** (measured effect
is pure harm). Add, under a new pre-registration with the same sweep-first shape:
- **A1 — per-(document, value) witness collapse:** one document attests one value once;
  near-duplicate same-doc same-value observations collapse to the best-covariate one.
  Targets q2-105's class directly (12 → 1 witness; the 0.989 concentration cannot
  survive). The principled reading of §5's own rule at document granularity.
- **A2 — synthesised-confirm covariate cap:** a confirm minted from re-reading carries at
  most the max covariate of the grounded observations it re-read. Targets q2-071's
  amplifier. Whether capping alone flips that row to withheld is genuinely uncertain (the
  grounded 2:1 conflict remains).
- Cost: $0 sweep, then run 14 at ~$1–4 only on a sweep PASS. Risk: q2-071 may still
  commit wrong (splice shows any surviving wrong pair caps run 14 at FAIL on the
  conjuncts); the colds stay unreadable until the priced run.

**B. Park.** Keep the branch unmerged (docs merged, code parked, as r09), block stands,
return to the module-collapse programme (M2 the poster). The wrong-commit lever waits for
a mechanism that reaches q2-071's class.

**C. Re-freeze run 14's conjuncts (owner-only).** Keep δ/level; relax "zero new wrong
commits" to "none outside named standing classes" (in-document repetition; grounded
conflict). Splice prices this at 0.940–0.976 PASS. This deliberately weakens the deploy
bar — the same two rows master already knowingly carries would ride into live.

**D. Gold-audit q2-071 first ($0).** The row is a grounded 2:1 conflict; the q2-053
precedent (stale in-corpus gold, corrected and disclosed) says check the gold before
building around it. If the gold is stale, q2-071 reclassifies and A's reach improves; if
it holds, the conflict is real and only withholding can serve it.

## Recommendation

**D then A (A1 + A2, T2 dropped, T1 kept), sweep-gated exactly as before.** D is free and
decides A's expected reach; A1 is the only fix in the set that provably reaches a wrong
row's mechanism (q2-105's twelve-fold witness cannot survive it); A2 is cheap and
principled (a re-read cannot outrank its sources) even if its flip is uncertain. B remains
the honest fallback if the owner prefers to stop paying for this lever now — nothing in
the sweep contradicts run 13's Δ̄ +0.424, and the block is doing its job. C is not
recommended while a targeted $0 iteration remains untried.

## Questions

1. **Successor:** open r09c as scoped (D + A1 + A2, T2 dropped, T1 kept)? Or park (B), or
   re-freeze the conjuncts (C)?
2. **T2:** confirm dropping it (measured: 3 regressions, 0 repairs)?
3. **Run 14 branches:** on an r09c sweep PASS, do ruling 4's three conjuncts verbatim at
   full delegation still govern (PASS ⇒ block closes + master deploys live, no keypress;
   FAIL ⇒ revert + STOP)?
4. **If B (park):** where does the programme point next — M2 (the poster) per
   module-collapse §8, or another checkpoint?

## RULINGS

**Taken 2026-08-24 (owner, interviewed against this document), all on the recommended
branch:**

1. **Successor: D then A — r09c OPENS.** The q2-071 gold audit runs first ($0, the q2-053
   stale-gold precedent); then r09c under a new pre-registration: **A1** (per-(document,
   value) witness collapse — one document attests one value once) + **A2** (synthesised-
   confirm covariate cap at the max of its grounded sources), with the same sweep-first
   shape — a $0 replay sweep on run 13's record with frozen criteria before any spend.
2. **T2 is DROPPED** (measured: 3 regressions, 0 repairs); **T1 is KEPT** (unfalsified;
   its class is readable only in a priced run).
3. **Run 14's outcome branches carry over verbatim from ruling 4 at full delegation:**
   PASS (frozen δ/level ∧ blocking row repaired ∧ zero new wrong commits) ⇒ the §6.12
   block closes and master deploys to live without a keypress; FAIL on any conjunct ⇒
   revert + STOP for a ruling (with a conferral).
