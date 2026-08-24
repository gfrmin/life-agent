# Conferral — what happens to the JOIN after run 13 (2026-08-24)

> **Status: for owner ruling. Work is STOPPED** — ruling 4's FAIL branch is enacted
> (the JOIN's code commits reverted, PR #78, master `ca0d9fa`; the §6.12 deployment
> block stands). This document fixes the evidence, the options and their prices, and the
> questions; the rulings will be recorded back into it append-only.

## 1. What forced this conferral

Run 13 (`gate-20260824T144002`, master = run-10 lineage + r08 + r09, §6.10 pin naming
exactly that delta; credence code-identical to the run-9 pin) read **FAIL on two of ruling
4's three conjuncts**:

| conjunct | frozen bar | read | verdict |
|---|---|---|---|
| (a) gate | P(Δ>0.05) ≥ 0.90, δ/level unchanged | **0.895** | FAIL by 0.005 |
| (b) blocking row repaired | run 10's wrong commit not wrong | report / **correct** | **PASS** |
| (c) zero new wrong commits | 0 | **4** (q2-018, q2-019, q2-071, q2-105) | FAIL |

Beside the conjuncts: Δ̄ **+0.424** [−0.070, +0.941] — the strongest mean of the series;
typed 70 ✓ / 4 ✗ / 30 withheld (miss 2 · dispersed 28); answer rate **0.71** against runs
9–12's 0.34–0.57; typed spend $0.58 (deliberate 29/104, all warm — the r09 idempotence
finding confirmed live). The judge flipped 5 mono rows on regrade (standard).

## 2. The mechanism, named

All four wrong rows were **run-10 dispersed withholdings**. The JOIN converts dispersals in
both directions — ~35 became correct asserts, four became confident-wrong at u_wrong ≈ −9 —
and dispersal was the protection (run 12's own analysis, now priced). Two of the four are
standing named classes:

- **q2-019 — the superset-confirm class** (a shorter personal-name candidate confirmed
  inside a longer gold): the corroborate audit's named defect; its fix (a strict-span guard
  on containment confirms) was **registered as a follow-up** when `confirm_hits` was
  refused (2026-08-18).
- **q2-105 — the warm-deliberate-confirm class** (run 8's row): a warm deliberate confirm
  of a competed value carried over the bar; the §4.2 competition lineage priced it in run
  9's temper, and the JOIN's pooled channel re-admits it.
- q2-018 and q2-071: named, not diagnosed (the cap — anomalies are disclosure items).

## 3. The splice ladder ($0, run 13's own archive; the pin reproduces 0.895 / +0.424)

Counterfactuals re-dispersing wrong rows — i.e. modelling a PERFECT temper with zero
collateral (artefacts: `$LIFE_AGENT_KB/eval/gate-outside-option/splice-run13-*.md`):

| counterfactual | P(Δ>0.05) | Δ̄ | verdict |
|---|---|---|---|
| any ONE of the four re-dispersed | 0.948–0.949 | +0.511 | PASS (marginal) |
| **the two NAMED classes re-dispersed** | **0.980** | **+0.598** | **PASS** |
| all four re-dispersed | 1.000 | +0.771 | PASS |

Readings: the gate failed by exactly one wrong row's worth; a temper catching only the two
named classes clears the bar with margin; a single-class temper (0.949) sits a hair over
the bar under a standing noise floor (§6.13's commit-wobble floor of 2, and five judge
coin-flips this run) — fragile. **Caveat, stated:** a real temper has collateral — run 9's
competing-values temper cost 21 collateral withholdings — so an off-gate sweep with frozen
criteria (the `temper_audit` pattern, which predicted run 9's assert set perfectly) must
price collateral before any re-fire.

## 4. What survives the revert

The r09 pre-registration, implementation record and reading (append-only); the finding that
the deployed JOIN is idempotent over the raw pool on today's wire shapes — so a re-landed
JOIN needs a **temper**, not a better dedup; the fire-run13 recipe (tree gate + code-identity
credence gate); and conjunct (b): the JOIN demonstrably repairs the blocking row the §6.12
block exists for.

## 5. Options

**A — r09b: the JOIN + a temper for the two named classes** *(recommended)*. New frozen
pre-registration BEFORE any src change; temper candidates named now: (a1) the strict-span
guard on containment confirms (the registered follow-up — kills q2-019's class), (a2)
dispersal preservation on joined confirms of competed values (q2-105's class — e.g. the
joined confirm inherits the base channel's competition posture rather than adding an
independent witness). Off-gate sweep first with frozen collateral criteria; then run 14
(~$1–4 typed vs the archived mono arm) under the same three frozen conjuncts at full
delegation. Risk: overfitting the temper to four rows (r05's lesson — measure the fix
against the class, not the case); mitigation: the sweep + frozen criteria + the splice's
prediction (0.980) registered blind as run 14's expectation.

**B — park the JOIN.** Master stays reverted; the §6.12 block stays open (master still
carries the blocking-row wrong commit); reach stays 0.34–0.57; the collapse programme
(M2+) continues under the block. No further spend; the block has no closing path named.

**C — re-rule the gate structure** (accept 0.895, or move δ/level). Named cost: §6.1/§8
froze δ/level precisely so no reading can tune them; re-ruling after seeing 0.895 spends
the gate's credibility. Listed for completeness, not recommended.

**D — narrowest variant of A:** temper only the superset-confirm class (its fix already
registered). Splice says PASS at ~0.949 — over the bar by less than the standing noise
floor. Fragile; folded into A as its first temper rather than standing alone.

## 6. Questions for ruling

1. **Open r09b** (option A), park (B), or re-rule the gate (C)?
2. If A: temper scope — **both named classes** (recommended) or the superset-confirm class
   alone (D)?
3. If A: run 14's outcome branches — the same three conjuncts at full delegation, with the
   splice's 0.980 registered blind as the expectation (recommended), or return to a
   keypress?
4. The riders (m0-5 re-record + O2 re-preparation): stay deferred until a PASS deploys
   (recommended), or run now?
