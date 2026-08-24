# r09c — the per-document witness temper (A1 + A2, T2 removed)

**Opened 2026-08-24 by the rulings in
`docs/unification/conferrals/r09b-sweep-conferral.md`** (owner, interviewed): D then A —
the q2-071 gold audit first, then A1 (per-(document, value) witness collapse) + A2
(synthesised-confirm covariate cap), T2 dropped, T1 kept, the same sweep-first shape, run
14 only on a sweep pass under ruling 4's conjuncts verbatim at full delegation.

**This pre-registration is committed BEFORE any `src/` change on this branch.**

## STATE — what the wire and the gold audit established (all $0)

From r09b's sweep reading (`docs/unification/reports/r09b-tempered-join.md`) and the D
audit run after the rulings:

1. **q2-105 — in-document repetition inflation.** Twelve observations from ONE document,
   ONE reported value, identical/near-identical quotes: one attestation counted twelve
   times. Root cause located in THE §5 rule itself: `lookup.dedup_drop_rows` explicitly
   skips within-document duplicates (`len(docs) <= 1 → continue`) on the premise that
   "the per-document group already counts it once" — but the doc-keyed group mechanism
   counts them CORRELATED (single-rho coarsening), not ONCE: the twelve rode to 0.989.
2. **q2-071 — gold HOLDS; the conflict is not real.** The question asks for a class-level
   value in a coverage table; the gold's quote is the class row; both competitor quotes
   are the file-level and "(no function)" rows of such a table — the asked entity is
   absent from them. The class is wrong-row-of-a-multi-value-table (the run-8 q2-053/
   q2-090 precedent), amplified by a synthesised confirm minted at authority 1.0 /
   subject 1.0, above every grounded carrier (0.85 / 0.525). The run-9 competition temper
   cannot fire (different documents, no shared quote window).
3. **q2-018 — the tel/fax-pair class.** Run 13's decision row: a fax question, two
   candidates of the gold's own digit shape, the competitor committed at 0.926 with the
   gold at 0.037; n_obs 5, n_competing 3, n_indeterminate 12. Wire unreadable at $0 (cold
   by the pin's truncation).
4. **q2-019 — T1's class**, unreadable at $0 for the same reason; readable only priced.
5. **T2 measured 3 regressions / 0 repairs** and is REMOVED by ruling.
6. **Splice bounds for run 14** (pin reproduced 0.895/+0.424; artefact
   `$LIFE_AGENT_KB/eval/window/r09c-splice-bounds.md`): both readable rows flipped =
   **0.980 / +0.598** (the floor the sweep can certify); all four flipped = **1.000 /
   +0.771** (the ceiling). The floor scenario still FAILS ruling 4's zero-wrong-commit
   conjunct (the cold pair commits wrong), so the sweep is necessary, not sufficient —
   the cold pair is run 14's residual risk, held by the ruled FAIL branch (revert + STOP).

## D0 — branch and baseline

Branch `r09c-doc-witness` from the r09b head (JOIN + T1 + T2 + the sweep reading). First
src commit removes T2 and its tests (ruling 2); the r09 JOIN and T1 are retained verbatim.

## D1 — A1: the per-(document, value) witness collapse, inside THE one rule

Amend `lookup.dedup_drop_rows` (never a second implementation — §6.8): a first pass over
doc-keyed rows groups by `(doc_key, value_norm)` and keeps only the first-maximal-covariate
row per group — **one document attests one value once**. Value-only rows (`doc_key == ""`)
are untouched (synthesised observations are T2-territory and T2 is gone; S5 mints from
zero by design). The existing cross-document identical-quote-with-context pass runs
unchanged over the survivors. Every caller (base extraction, the wire JOIN, replay)
inherits the amendment through the one rule.

## D2 — A2: the synthesised-confirm covariate cap

The two mint sites in `bridge/server.py` that hard-code `authority: 1.0,
subject_factor: 1.0` for synthesised observations (the corroborate confirm and the
deliberate synthesis helper) are capped: each component at the per-component **max over
the standing channel's doc-keyed observations reporting the same `value_norm`**; if none,
the max over ALL doc-keyed channel observations; if the channel has no doc-keyed
observations at all, uncapped (the k=0 rescue mints from zero by design — S5 exemption).
**A re-read cannot outrank the channel it re-read.** `time_factor` is not capped (it is
already the caller-computed projection, not a minted constant).

## Criteria (frozen now)

- **C1 — TDD.** Every predicate watched RED first; suite, ruff, mypy green.
- **C2 — the sweep, before any spend.** The r09b C3 instrument verbatim (replay_audit
  deployed-only on run 13's meta/paired, fresh staging, drift acknowledged, $0):
  - **S1':** q2-105 AND q2-071 BOTH flip (withheld or correct).
  - **S2':** collateral — replayable rows correct in run 13 turned withheld — **≤ 5**
    (T2's three must return; A1/A2's own collateral is the new unknown).
  - **S3':** the run-10 blocking row (q2-011) stays repaired.
  - Any failure → **STOP and re-confer** (the named next option is the entity-anchor
    lever for the multi-value-table class); run 14 is not fired.
- **C3 — run 14** (only after C2 passes): the fire-run14 recipe with the tree gate
  updated for this branch, under **ruling 4's three conjuncts verbatim at full
  delegation, as enacted in run 13** (any wrong commit not in run 10's record fails):
  PASS ⇒ the §6.12 block closes and master deploys to live without a keypress; FAIL on
  any conjunct ⇒ the temper+JOIN revert and work STOPs for a ruling (with a conferral).
  The riders stay deferred until a PASS deploys.
- **C4 — PII.** Classes and counts in tree; artefacts to `$LIFE_AGENT_KB`.

## Blind predictions

1. **q2-105 flips to withheld** (A1 collapses 12 → 1; the gold is not on the lattice, so
   correct is unreachable; the deliberate re-mint arrives capped by A2).
2. **q2-071 is the honest coin-flip of this checkpoint:** A2 removes the amplifier, but
   whether a 2:1 grounded conflict at equal covariates still clears the report bar is
   unknown. If it reports, S1' fails and the STOP fires with the entity-anchor conferral.
3. The three T2 collateral rows (q2-002, q2-057, q2-087) return to correct; fidelity
   otherwise matches run 13's record except the intended flips.
4. A1's own collateral ≤ 2.
5. If run 14 fires: at or above the 0.980 floor on δ/level; the cold pair decides the
   wrong-commit conjunct — T1 covers q2-019's class; q2-018 (tel/fax) is reached by A1
   only if its competitor rides within-document repetition (n_indeterminate 12 hints it
   may). A FAIL there is the ruled revert + STOP, not a surprise.

**PENDING below this line: the T2 removal, A1, A2, the sweep, run 14.**
