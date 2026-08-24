# Conferral — after r09c's sweep: what actually decides the two blocking rows

**Status: work is STOPPED at the frozen C2 consequence.** r09c's sweep read **S1' FAIL**
(`docs/unification/reports/r09c-doc-witness-temper.md`), so run 14 was not fired and
nothing was bought. This document is the evidence base for the successor ruling.

## What r09c established (all $0)

The C2 sweep replayed run 13's own record on the r09c tree: 63 rows readable, 41 cold,
**57 of 63 identical in action and leader**.

| criterion | bar | read | verdict |
|---|---|---|---|
| S1' | q2-105 **and** q2-071 both flip | neither: q2-071 identical (0.936 → 0.939), q2-105 **cold this pass** | **FAIL** |
| S2' | collateral ≤ 5 | 3 — none of them A1's or A2's | PASS |
| S3' | blocking row stays repaired | q2-011 identical, reports the gold | PASS |

**A2 worked and did not matter.** The wire shows the synthesised confirms now arriving at
the grounded carriers' covariates (0.85 / 0.525) instead of 1.0 / 1.0 — the amplifier the
pre-registration named is gone — and the row commits the competitor anyway. **A1 never
fired**: no readable row carries a within-document duplicate, and its target row is the one
that went cold.

**Both blocking rows are one class, and it is not an aggregation defect.** q2-071's
competitor is carried by **two of three genuinely distinct documents** (three separate
artifacts — verified in the catalogue after a first, wrong "three chunks of one table"
reading, corrected in the report): they report a **file-scoped** and a
**remainder-scoped** value for the same path, while the question asks a **class-scoped**
one. q2-018 is the same shape in a different dress: a fax question answered with the
adjacent telephone value. In both cases the observation carries **the value but not the
qualifier that says what the value is of** — so no dedup, cap or temper downstream can
separate them, and the competitor wins on count.

**Run 14, priced (`gate_splice.py`, pin reproduced 0.895 / +0.424):**

| variant | P(Δ>0.05) | Δ̄ | note |
|---|---|---|---|
| run 13 (the pin) | 0.895 FAIL | +0.424 | what master reads today |
| r09c as measured | **0.939 PASS** | +0.482 | the tree the sweep just read |
| r09c + the cold row flipping | **0.975 PASS** | +0.569 | optimistic bound |

**The δ/level bar is no longer the blocker.** Ruling 4's *zero-wrong-commit* conjunct is:
q2-071 and q2-018 both still commit wrong (q2-018 readable for the first time on this
pass), and q2-105 is unreadable. A gate run now would cost ~$40 and fail on that conjunct.

**One finding outside the criteria (disclosure, not a new arc):** the three collateral rows
all shrink at **S2**, the single replace site r09's JOIN left untouched — on two of them S2
replaces a five-observation channel with one, and a correct leader falls under the report
bar. Seven readable rows show an S2 shrink. The JOIN makes S2 *worse*, because everything
upstream now accumulates into a channel S2 then discards. This also corrects r09b's
diagnostic 1: T2's measured profile is **2 regressions / 0 repairs**, not 3 / 0 — the
ruling to drop T2 stands on the corrected numbers.

**Also registered:** the readable set is **not stable across passes** — 14 rows entered and
14 left between r09b's sweep and r09c's on the same record (§18.9 pass-order coldness). A
criterion naming specific rows can go unreadable between passes; S1' half-failed for that
reason rather than on evidence.

## Options

**A — r09d, the decide-side entity anchor (recommended).** No wire or extract change: a
matching-side rule in the shape of run 9's competing-values temper. When the question names
an entity and **some** competing observation's quote window carries that entity while others
do not, damp the ones that do not. Conservative by construction — if no observation carries
the anchor, nothing changes. Addresses **both** blocking rows (class-vs-file scope;
fax-vs-telephone) and the standing q2-053 / q2-090 class.
*Cost:* one build session + a $0 sweep; run 14 (~$40) only on a sweep pass.
*Risk:* entity tokens that appear in a different language or phrasing than the question
(the corpus is multilingual) — mitigated by damping rather than excluding, and by firing
only where a competitor *does* carry the anchor.

**B — r09d', the extract-side entity field.** Carry a qualifier/anchor field on the
observation itself from the extractor. Stronger and more general than A; also the more
invasive change: the payload grows, so the 95-fixture unservable class recurs, and the
anchor is model-produced text needing its own grounding rule.
*Cost:* larger build, fixture re-record, $0 sweep, then ~$40.
*Risk:* a new ungrounded field on the decision path.

**C — park.** Stop here: the JOIN and the temper stay unmerged, the §6.12 block stands,
master keeps the r09-reverted state. *Cost:* $0. *Consequence:* nothing deploys, and the
0.939 reading stays unbanked.

**D — re-freeze run 14's conjuncts and fire now.** Exempt the named legacy wrong rows
(all three are run-10 dispersals that run 13 converted) and fire at the measured 0.939.
*Cost:* ~$40, deploys on PASS. *Risk:* deploys a tree that knowingly commits at least two
wrong answers — which is what the conjunct exists to prevent.

**E — fix S2 (bundle, not a substitute).** Extend the JOIN to S2 so a second gather round
cannot discard an accumulated channel. Recovers 2 correct commits and touches 5 more rows,
but **cannot unblock run 14** — it does not fix a wrong commit. Only worth bundling with A
or B.

## Recommendation

**A, with E bundled, under a fresh pre-registration** — and A1 + A2 kept on the branch
(A2 is measured-correct-but-insufficient; A1 is landed, unit-tested and inert here, so it
is honest to keep it and say so). A is the only option aimed at the mechanism the wire
actually shows, it is decide-side and therefore cheap and sweep-testable at $0, and it
reaches both blocking rows. E is nearly free once A is being built and buys back the answer
rate the JOIN currently loses at S2.

## Questions

1. **Successor lever:** A (decide-side entity anchor), B (extract-side entity field), C
   (park), or D (re-freeze the conjuncts and fire now)?
2. **A1 + A2:** keep them on the branch, or revert them with the rest of the temper?
3. **S2 (option E):** bundle into the next checkpoint, or leave it for later?
4. **Run 14's conjuncts:** ruling 4 verbatim again, or amended?
