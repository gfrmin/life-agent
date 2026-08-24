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

**PENDING below this line: the revert-of-the-revert, the temper commits, the sweep, run 14.**
