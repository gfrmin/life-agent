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

## THE READING — the C2 sweep (2026-08-24, $0)

Built as pre-registered: T2 removed by ruling (`420b8ac`), then A1 inside THE §5 rule
(`0388b7e`) and A2 at both synthesis mint sites (`091baad`), every predicate watched RED
first; suite 2667, ruff green (one pre-existing mypy error in an unrelated runtime
`sys.path` import, verified pre-existing by stash and disclosed in the A2 commit). The
sweep ran `scripts/replay_audit.py` deployed-only on run 13's own meta/paired from this
tree, fresh staging pinned at the run's start, src drift acknowledged and stamped:
**63 rows replayed, 41 excluded cold**. The 9(d) render guard fired as in r07/r08/r09b
(one corpus value, len=1/numeric); the rows dump `$LIFE_AGENT_KB/eval/window/r09c-sweep.yaml`
is the artefact of record.

Graded against **run 13's own committed leader** (recovered per question from
`calibration/decisions.jsonl`, `posterior_summary.candidates[0]`), not against a string
matcher — see the disclosure below. **57 of 63 rows replay with the identical action and
leader**; five rows move; one of the five is an abstain→abstain leader change.

| criterion | frozen bar | read | verdict |
|---|---|---|---|
| S1' | q2-105 AND q2-071 BOTH flip (withheld or correct) | **neither** — q2-071 replays identically (same wrong leader, credence 0.936 → 0.939, n_obs 4 → 5); q2-105 is **excluded cold on this pass** and unreadable | **FAIL** |
| S2' | collateral (correct → withheld) ≤ 5 | 3 — and **none of the three is attributable to A1 or A2** (diagnostic 5) | PASS |
| S3' | the run-10 blocking row stays repaired | q2-011 replays identically, reporting the gold at n_obs 4 | PASS |

**S1' fails → the frozen consequence is enacted: run 14 is NOT fired; STOP and re-confer.**

### The wire diagnostics ($0, from the sweep's own warm staging)

1. **A2 fires exactly as designed, and is insufficient.** On q2-071 the wire now shows both
   synthesised confirms arriving at the grounded carriers' covariates (authority 0.85,
   subject 0.525) instead of 1.0 / 1.0: the amplifier named in the pre-registration is
   gone. The row still commits the competitor, marginally harder than before. Removing the
   amplifier does not remove the **count** — four competitor observations against one gold
   observation, every covariate identical.
2. **q2-071's carrier is a 2:1 GROUNDED majority, not the confirms.** Three grounded
   observations: one carries the gold, two carry the competitor. By the D audit the two
   competitor rows are a file-scoped and a remainder-scoped row for the same path, while
   the question asks for a **class-scoped** value and the gold is the class row. The three
   `doc_key`s resolve in the catalogue to **three genuinely distinct documents** (three
   separate pandoc artifacts, sizes 88 KB / 27 KB / 221 KB, 91 / 28 / 230 chunks) — so this
   is not a counting artefact: three independent documents really do disagree 2:1, because
   two of them answer a *different question about the same path*. `competition_factor` is
   1.0 on all three, so the run-9 competing-values temper is blind here by construction (no
   shared quote window across documents). Strike the confirms entirely and the competitor
   still leads 2:1. The observation carries no entity qualifier, so nothing downstream can
   tell a class-scoped value from a file-scoped one. This is the multi-value-table class
   (q2-053 / q2-090 precedent), and the **entity-anchor lever** named in the
   pre-registration is aimed at exactly it.

3. **A1 is UNMEASURED on this pass.** No replayable row shows the doc-keyed collapse
   signature, and the two rows dumped observation-by-observation carry no within-document
   duplicate pair. A1's target row is q2-105 — **cold on this pass**. The rule is landed,
   unit-tested and inert in this reading; nothing here is evidence for or against it.
4. **The readable set is not stable across passes.** Against r09b's sweep on the same
   record: **14 rows entered the replayable set and 14 left it** (§18.9 pass-order
   coldness, §6.13's standing residue). q2-009, q2-018, q2-019 and q2-046 became readable;
   q2-105 went cold. A criterion that names specific rows can therefore become unreadable
   between two passes of the same instrument — S1' half-failed for that reason, not on
   evidence. **Register this as a lesson: name a class and a bar, or pre-declare the
   consequence of a named row going cold.**
5. **The three collateral rows are S2's, not the temper's.** All three shrink at **S2 —
   the one replace site r09 left untouched by design** — and on two of them S2 replaces a
   five-observation channel with one, so the correct leader commits at n_obs 2 and falls
   under the report bar. Seven rows in the set show an S2 shrink. The JOIN makes S2's
   surviving replace *worse*, not better: everything upstream now accumulates into a
   channel that S2 then discards. **This corrects r09b's diagnostic 1**, which attributed
   all three of its collateral rows to T2: two of them (q2-002, q2-087) did return to
   correct once T2 was removed, but the third abstains here with T2 gone, so **T2's
   measured profile is 2 regressions / 0 repairs, not 3 / 0**. The ruling to drop T2 stands
   on the corrected numbers.
6. **Splice pricing of the unfired run 14** (`gate_splice.py`, pin reproduced 0.895 /
   +0.424): the tree as measured reads **0.939 PASS** on the frozen δ/level, and **0.975**
   if the cold row also flips — the δ/level bar is **no longer the blocker**. But q2-071
   and q2-018 (warm for the first time on this pass, and identical to the record) both
   still commit wrong, so **ruling 4's zero-wrong-commit conjunct fails in every variant**.
   The sweep again saved the spend and a wrong deploy.

### Predictions scored

P1 **unread** (q2-105 cold). P2 **CONFIRMED** — it named q2-071 as the coin-flip and named
"if it reports, S1' fails"; it reported. P3 **HALF** — two of the three T2 rows returned to
correct, the third did not (diagnostic 5), and two newly-warm rows moved instead. P4
**CONFIRMED with a correction** — collateral is 3 ≤ 5, but A1-attributable collateral is
**0**, not "≤ 2": A1 never fired here. P5 **unread** (no run 14); its pricing half is
answered by diagnostic 6.

### Disclosure — a defect in this reading, caught before the verdict

The first scoring pass graded the replay by normalised substring match against the gold and
its variants. That matcher **called q2-071 a repair**: the competitor's value is a substring
of the gold's (a leading-digit case), so the wrong leader graded as correct — the exact
shape of failure r05 warned about, and it would have flipped S1' from FAIL to a
half-PASS. The same matcher mis-graded two judge-graded superset rows the other way. It was
caught by the sanity check that compares the matcher against the record's own judge grade,
and the reading was redone against run 13's committed leader per question. Both quantities
are published above; no verdict was taken on the defective measure.

### Correction, published after the reading was first committed

The first version of diagnostic 2 asserted that the three carrying documents were three
**chunks of one table**, i.e. that the 2:1 majority was a counting artefact of chunk-level
`doc_key`s. That was checked against the catalogue afterwards and is **false**: each
`doc_key` resolves to a whole document (91, 28 and 230 chunks respectively, three separate
source artifacts). The diagnostic above is the corrected text; the verdict is unchanged
(S1' fails on q2-071 either way), but the *successor option* changes materially — a
correlation key that treats co-chunked rows as one document would have been a no-op here,
while the entity-anchor lever is aimed at the mechanism that is actually present. Published
rather than silently amended, per the r05 rule: an audit's measures get audited too.

### What the fail means

A2's hypothesis was **confirmed as a mechanism and refuted as a cure**: the covariate
inflation was real and is now gone, and the row it was supposed to rescue never depended on
it. What decides q2-071 is upstream of every aggregation rule in this checkpoint — the
extractor emits three rows of one table as three independent documents, two of them
answering a question about a different entity than the one asked. No dedup, cap or temper
downstream can distinguish them, because at the decide layer they are simply three
documents that disagree 2:1.

**Enacted:** run 14 not fired; this branch stays unmerged; master keeps the r09-reverted
state; the §6.12 block stands; nothing bought. The successor decision is conferred in
`docs/unification/conferrals/r09c-sweep-conferral.md`.

