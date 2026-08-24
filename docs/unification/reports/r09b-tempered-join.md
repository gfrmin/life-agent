# r09b — the tempered JOIN — PRE-REGISTRATION (2026-08-24)

> **Opened by the run-13 conferral's RULINGS (owner, 2026-08-24):** the JOIN re-lands with
> a temper for both named wrong-commit classes, under this frozen pre-registration
> (committed before any `src/` change on this branch — history is the proof), an off-gate
> collateral sweep before any spend, then run 14 under ruling 4's three conjuncts verbatim
> at full delegation. The splice's **0.980** is registered blind as run 14's expectation.

## STATE

- master `8927b4a` (run 13 read FAIL; the r09 JOIN reverted by PR #78; the conferral +
  rulings committed). Suite 2638, ruff, mypy green on the reverted tree.
- Design-time evidence ($0, run 13's own decision records, classes only): **all four wrong
  rows share one signature — committed n_obs inflated by STACKED SYNTHESISED CONFIRMS.**
  The warm-deliberate row committed at n_obs 13 with 12 same-shape competitors; the fax row
  at n_obs 5 over K=2; both no-competition rows at n_obs 4–5 with K≤2. Each corroborate
  tier and the deliberate edge re-reads the SAME documents, yet under the r09 JOIN each
  joined confirm counted as an independent witness — the nested dependence the old replace
  contract encoded ("same docs — nested dependence") and the JOIN discarded. The
  superset-confirm row adds a second defect: its confirms should not have existed at all
  (a containment match at a token boundary that is not an ENTITY boundary).

## The design, frozen

**D0 — the JOIN returns.** The r09 code commits are restored verbatim (a revert of the
revert), then tempered. Everything r09's pre-registration froze (D1–D4) stands unchanged.

**D1 — temper T1, the strict-span guard (the superset-confirm class).** A containment
confirm (corroborate's unique-containment branch and `_join_deliberate_value`'s alike) is
REFUSED when the matched candidate span is not at an ENTITY boundary in the read value: the
token immediately adjacent to the matched span (either side) has the same token class as
the candidate's own tokens (name-shaped beside name tokens, digit-group beside digit
tokens). A shorter personal-name candidate contained inside a longer name, or a shorter
digit-run inside a longer number, keeps the conservative no-observation contract — exactly
the class the corroborate audit registered when `confirm_hits` was refused. Exact
containment of the full value is untouched; `_competing_value_shape` (a same-shaped
competitor BESIDE the match) is untouched and complementary.

**D2 — temper T2, the nested-dependence collapse (the warm-deliberate class, and the
stacking signature generally).** At the join, synthesised observations — those with no
document identity (`doc_key` empty) — reporting the SAME candidate collapse to ONE witness
(the max-covariate one, first-maximal on ties). Rationale: the tiers and the deliberate
edge are re-reads of the same retrieved documents, not independent attestations; a re-read
cannot corroborate itself. Synthesised observations of DIFFERENT candidates all survive
(disagreement is signal). This is a SECOND named rule applied at the join, beside §5's
quote rule — not folded into `dedup_drop_rows` (one rule per phenomenon; §6.8 cuts both
ways). Document-carrying observations are untouched.

**D3 — nothing else moves.** The gate's δ/level, the null-read guard, S2, the single-rho
coarsening, the wire key — all exactly as r09 froze them.

## Frozen criteria

- **C1 — TDD.** Every temper predicate watched RED before its code; full suite, ruff,
  clean-cache mypy green at every commit.
- **C2 — the tempers' unit contracts.** T1: the four containment shapes (entity-boundary
  refusal left and right, exact-value acceptance, non-adjacent acceptance) each pinned by a
  synthetic-shape test. T2: same-candidate synthesised confirms collapse to one; different-
  candidate ones survive; document-carrying observations never collapse under T2.
- **C3 — the off-gate sweep, before any spend.** `scripts/replay_audit.py` deployed-only on
  **run 13's own meta/paired** (`gate-20260824T144002`), $0, warm, from the r09b tree with
  the src drift acknowledged; cold rows named. Hard sweep criteria, all frozen now:
  - **S1:** every one of the four wrong rows flips (withheld or correct).
  - **S2:** collateral — replayable rows correct in run 13 that the tempered tree turns
    withheld — **≤ 10**.
  - **S3:** the run-10 blocking row stays repaired.
  Any failure → STOP and re-confer; run 14 is not fired.
- **C4 — run 14** (only after C3 passes): the fire-run13 recipe with the temper assertions
  added to its tree gate, ~$1–4 vs the archived mono arm, under **ruling 4's three
  conjuncts verbatim at full delegation** — PASS ⇒ the §6.12 block closes and master
  deploys to live without a keypress; FAIL on any conjunct ⇒ the temper+JOIN revert and
  work STOPs for a ruling. The riders stay deferred until a PASS deploys.
- **C5 — PII.** Classes and counts in tree; artefacts to `$LIFE_AGENT_KB`.

## Blind predictions

1. The sweep flips all four wrong rows and reads collateral ≤ 5 — T2 removes only stacked
   re-read witnesses, which decide a commit only where the base alone could not.
2. The blocking row survives both tempers (its five witnesses are document-carrying).
3. Run 14 reads **≥ 0.95** (the splice's 0.980 minus real-temper friction), with zero new
   wrong commits and the blocking row repaired — PASS on all three conjuncts.
4. Answer rate lands between run 13's 0.71 and run 9–12's 0.34–0.57, nearer the former:
   T2 costs only commits that stacked confirms alone carried.
5. No §18.9 re-derivation: both tempers act after the derivation layer (T1 in the
   synthesis branch, T2 in the join), so the sweep runs fully warm on run 13's store.

## THE READING — the C3 sweep (2026-08-24, $0)

Built as pre-registered: D0 the revert-of-the-revert (the r09 JOIN restored verbatim,
`94ada13`), then T1 + T2 under TDD, every predicate watched RED first (`38f0f2d`); suite
2660, ruff, mypy green. The sweep ran `scripts/replay_audit.py` deployed-only on run 13's
own meta/paired from this tree (src drift acknowledged and stamped), fresh staging pinned at
the run's start: **63 rows replayed, 41 excluded cold** (§18.9 pass-order coldness). The
9(d) render guard fired as in r07/r08 (one corpus value, len=1/numeric); the rows dump
`$LIFE_AGENT_KB/eval/window/r09b-sweep.yaml` is the artefact of record.

| criterion | frozen bar | read | verdict |
|---|---|---|---|
| S1 | every one of the four wrong rows flips | **0 of 4** — q2-018, q2-019 excluded cold; q2-071, q2-105 replay with the same wrong leaders at unchanged n_obs | **FAIL** |
| S2 | collateral (correct → withheld) ≤ 10 | 3 (q2-002, q2-057, q2-087 — all correct → abstain) | PASS |
| S3 | the run-10 blocking row stays repaired | q2-011 reports the gold at n_obs 5 | PASS |

**S1 fails → the frozen consequence is enacted: run 14 is NOT fired; STOP and re-confer.**
The temper demonstrably executed — three rows differ from the record — so the fail is
substantive, not an inert instrument.

### The wire diagnostics ($0, from the sweep's own warm staging)

1. **T2's target signature lives on the CORRECT rows.** The three collateral rows are the
   full-cascade traces where tiers + deliberate each mint a same-candidate synthesised
   confirm; T2 collapses the stack and the correct report drops to abstain. T2's measured
   effect is 3 regressions, 0 repairs.
2. **q2-105 is in-document repetition, not stacking.** The competitor arrives as twelve
   observations from ONE document reporting ONE value with identical or near-identical
   quotes — a single attestation counted twelve times (the boilerplate/page-repetition
   class). §5's exact-quote key cannot collapse the near-duplicate variants, and T2
   (synthesised-only) never touches document-carried rows. n_obs 13 = these 12 + the
   deliberate re-mint.
3. **q2-071 is a grounded 2:1 conflict amplified by a covariate-inflated confirm.** Three
   observations over three documents — one carries the gold, two the competitor — plus one
   synthesised confirm of the competitor minted at authority 1.0 / subject 1.0, ABOVE the
   grounded carriers' 0.85 / 0.525: the re-read outranks everything it re-read. The run-9
   competition temper cannot fire (the values sit in different documents — no shared quote
   window; competition_factor 1.0 on every row). time_factor is uniform, so the date
   projection does not separate the carriers.
4. **The two cold rows are cold by the pin's own construction.** Their derivations were
   minted DURING run 13, and criterion 2 truncates the staging at the run's start — a
   second pass over the warmed staging leaves both cold. T1's effect on q2-019 (its named
   class) is structurally unreadable at $0; only a priced run reads it.
5. **Splice pricing of the unfired run 14** (gate_splice on modified paired, pin reproduced
   0.895/+0.424): the temper as measured (collateral enacted, colds unfixed) reads
   **0.879 FAIL — worse than run 13**; + T1 fixing q2-019 reads 0.940; + q2-018 too reads
   0.976 — but every scenario keeps ≥ 2 wrong commits, so **ruling 4's zero-wrong-commit
   conjunct fails in all of them**. The sweep saved the spend and a wrong deploy.

### Predictions scored

P1 **REFUTED** (0 of 4 flip; the collateral half read 3 ≤ 5). P2 **CONFIRMED** (the
blocking row's document-carried witnesses survive both tempers). P3/P4 **unread** (no run
14). P5 **CONFIRMED** (the sweep ran fully warm; the 41 cold rows are pin-truncation
coldness, not re-derivation).

### What the fail means

The pre-registration's STATE diagnosis is **REFUTED**: the decision-row signature (n_obs,
n_competing) cannot distinguish document-carried from synthesised observations, and on the
wire the four wrong rows are NOT the stacked-synthesised-confirm class — the stacking
signature belongs to rows the tree gets right. This is the carrier-audit lesson recurring
at the design stage: the temper was aimed at the signature the decision rows could show,
not the mechanism the wire records. The wire now names two real mechanisms — in-document
repetition inflation (q2-105) and synthesised-confirm covariate inflation over a grounded
conflict (q2-071) — neither of which T1/T2 addresses.

**Enacted:** run 14 not fired; this branch stays unmerged; master keeps the r09-reverted
state; the §6.12 block stands. The successor decision is conferred in
`docs/unification/conferrals/r09b-sweep-conferral.md`.
