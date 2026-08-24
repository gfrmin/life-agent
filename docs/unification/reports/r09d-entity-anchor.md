# r09d — the entity anchor (decide-side), with S2 joined

**Opened 2026-08-24 by the rulings in
`docs/unification/conferrals/r09c-sweep-conferral.md`** (owner, interviewed): option A —
the decide-side entity anchor, **no wire and no extract change**; A1 + A2 kept and
declared; the S2 join bundled (option E); run 14 under ruling 4's conjuncts verbatim at
full delegation.

**This pre-registration is committed BEFORE any `src/` change on this branch.**

## STATE — what r09c's wire established (all $0)

1. **Both blocking rows are one class: the observation carries a value but not the
   qualifier that says what the value is OF.** q2-071 — two of three *genuinely distinct*
   documents (verified in the catalogue) carry a file-scoped and a remainder-scoped value
   for the same path while the question asks a class-scoped one; the gold is the class row
   in the third. q2-018 — a fax question answered with the adjacent telephone value.
   Nothing downstream can separate them: at the decide layer they are documents that
   disagree, and the competitor wins on count.
2. **This is not an aggregation defect.** A2 removed the covariate amplifier (confirms now
   arrive at the grounded carriers' 0.85 / 0.525) and the row commits the competitor
   anyway; strike every synthesised confirm and the competitor still leads 2:1.
3. **Run 9's competing-values temper is blind to it by construction** — it scans *within*
   one extractor quote window, and these competitors live in different documents, so
   `competition_factor` is 1.0 on every carrier.
4. **The δ/level bar is no longer the blocker.** r09c as measured prices at 0.939 (0.975
   with the cold row); ruling 4's zero-wrong-commit conjunct is what fails.
5. **S2 is the one replace site r09's JOIN left untouched**, and the JOIN made it worse:
   everything upstream now accumulates into a channel S2 discards. Seven readable rows
   shrink at S2; on two of them a five-observation channel becomes one and a correct
   leader falls under the report bar.
6. **The readable set is not stable across passes** (14 in / 14 out between two passes of
   the same instrument on the same record). Criteria below therefore name a **class and a
   bar**, and pre-declare the consequence of a named row going cold — the r09c lesson.

## Design (frozen before any code)

**D0.** Branch from r09c's head. A1, A2, T1 and the JOIN are all retained (ruling 2); T2
stays removed. The first `src/` commit on this branch is D1.

**D1 — the detector (`core/matching.py`, pure and model-free).** A question's
**discriminating terms** are its content tokens (lowercased, length ≥ 4, stopwords out)
that appear in **at least one** observation's quote window and are **absent from at least
one** — discriminating by construction, computed from the channel, never from a model. The
quote window is run 9's own (quote ± the frozen margin, located in the chunk); the slice is
factored out of `quote_scoped_competitors` into one helper so there is a single window
definition (§6.8).

**D2 — the factor (`core/lookup.py`).** Each observation scores the **count** of
discriminating terms its window carries. Observations **strictly below the channel maximum**
are damped by the frozen 1/2 — the same factor and cap as the competition term, applied once,
never compounding per term. Folded into the existing `competition_factor` transport at the
two mint sites (`observe_hits`, `confirm_hits`), so **the wire payload is unchanged in shape
and no fixture becomes unservable**; `n_competing` keeps its meaning, and the field's
docstring becomes the §4.2 reliability temper (competition ∧ anchor). Conservative by
construction: **no discriminating term ⇒ every observation ties at the maximum ⇒ nothing is
damped.**

**D3 — the bundle (`core/executor.py`).** S2 adopts the same §5-deduped JOIN as S1/S3/S4/S5,
so a second gather round can no longer discard an accumulated channel.

## Criteria (frozen now)

- **C1 — TDD.** Every predicate watched RED first; suite, ruff green (the one pre-existing
  mypy error in an unrelated runtime `sys.path` import stays disclosed, not fixed).
- **C2 — the sweep, before any spend** (the r09b/r09c instrument verbatim: replay_audit
  deployed-only on run 13's meta/paired, fresh staging, drift acknowledged, $0):
  - **S1'' (the class, not a row):** **every** row run 13 committed **wrong** that is
    **readable on the pass** must flip to withheld or correct.
    **Coldness clause, pre-declared:** if fewer than **3** of the four known wrong rows
    (q2-018, q2-019, q2-071, q2-105) are readable, the sweep is **INCONCLUSIVE** — run one
    further pass; if it is still inconclusive, **STOP and confer**. An inconclusive sweep
    never fires run 14.
  - **S2'':** collateral — rows run 13 committed correct that now withhold or commit
    wrong — **≤ 5**.
  - **S3'':** the run-10 blocking row (q2-011) stays repaired **if readable**; cold ⇒
    unread, not a failure.
  - **S4'' (the bundle):** no readable row loses a correct commit at an S2 shrink, and
    q2-009 and q2-046 return to correct **if readable**.
  - Any failure → **STOP and re-confer**; run 14 is not fired.
- **C3 — run 14** (only after C2 passes): the fire-run14 recipe with the tree gate updated
  for this branch, under **ruling 4's three conjuncts verbatim at full delegation, as
  enacted in run 13** (any wrong commit not in run 10's record fails): PASS ⇒ the §6.12
  block closes and master deploys to live without a keypress; FAIL on any conjunct ⇒ the
  deploy-path changes revert and work STOPs for a ruling, with a conferral. The riders
  (m0-5 re-record, O2) stay deferred until a PASS deploys.
- **C4 — PII.** Classes and counts in tree; artefacts to `$LIFE_AGENT_KB`.

## Blind predictions

1. **q2-071 flips.** Its gold's window carries the class term the question names and the two
   competitor windows do not, so the competitors damp to 1/2 and the 2:1 grounded majority
   becomes 1 × 1.0 vs 2 × 0.5 — a tie on weight, which should disperse rather than commit.
   Withheld is the expected outcome, correct the lucky one.
2. **q2-018 flips too** — the fax/telephone pair is the same shape and the asked qualifier
   is a question token that sits in one window and not the other.
3. **Collateral lands at 3–6, i.e. S2'' is the criterion most at risk**, and its dominant
   source is single-witness rows whose one window happens to miss a question token that
   another candidate's window carries.
4. **The S2 join returns q2-009 and q2-046 to correct if they are readable, and raises the
   answer rate**; it fixes no wrong commit, so it cannot carry C2 alone.
5. **If run 14 fires it reads at or above 0.939**, and the wrong-commit conjunct is decided
   by whichever of the four wrong rows is cold — the coldness clause exists because that is
   now the dominant risk, not the lever.

## THE READING — the C2 sweep (2026-08-24, $0)

Built as pre-registered: D1 the detector with one shared window definition (`95e110c`), D2
the factor at both mint sites (`023de39`), D3 the S2 join (`af8112e`); every predicate
watched RED first, suite 2685 and ruff green. The sweep ran the r09b/r09c instrument
verbatim, deployed-only on run 13's own meta/paired, fresh staging, drift acknowledged and
stamped. Pass 1: **58 rows readable, 46 cold**; the rows dump
`$LIFE_AGENT_KB/eval/window/r09d-sweep.yaml` is the artefact of record. Graded against run
13's own committed leader, per r09c's rule.

| criterion | frozen bar | read | verdict |
|---|---|---|---|
| S1'' | every readable run-13 wrong row flips; **< 3 of the four readable ⇒ INCONCLUSIVE, run one further pass** | **1 of 4 readable** (q2-018, still wrong; q2-019, q2-071, q2-105 all cold) | **INCONCLUSIVE** |
| S2'' | collateral ≤ 5 | **2** (q2-046, q2-057) | PASS |
| S3'' | blocking row stays repaired if readable | q2-011 reports the gold | PASS |
| S4'' | q2-009 and q2-046 return to correct if readable | q2-009 **returned**; q2-046 did **not** | **FAIL** |

**The pre-declared second pass could not run.** It was launched immediately and stopped at
row 12 on an **account-level API usage limit — access returns 2026-09-01 00:00 UTC**. Cold
rows can only be warmed by real model calls, so no further pass can improve the readable set
before that date, and **run 14 (~$40) is externally blocked regardless of any sweep result**.
The frozen chain therefore terminates where it was written to: still inconclusive ⇒
**STOP and confer**; run 14 not fired.

### The lever's own reading — a $0 census, and it refutes the frozen window

The criteria could not resolve S1'', so the checkpoint was read where it *is* measurable:
across the whole battery, on the warm channel, how often does the anchor fire and **which
side does it damp**? (`anchor_census.py` / `window_census.py`, both $0, RefusingClient — no
model call, cold questions skipped.)

| window | fires | damps the gold | **damps the gold while a non-gold stays at 1.0** | clean firings |
|---|---|---|---|---|
| **±120 quote window (as built, frozen in D2)** | 42 | 26 | **12** | 16 |
| ±600 local | 43 | 26 | 10 | 17 |
| **whole chunk (document-scoped)** | 28 | 13 | **1** | 15 |

**The frozen window choice is refuted.** As built, the rule damps the gold on 26 of its 42
firings and *inverts the ranking direction* on 12 — while a document-scoped window keeps
essentially the same clean firings (15 vs 16) and is strictly harmful on **one**. The
mechanism is exact, from the wire: on q2-057 the discriminating terms are five tokens of the
document's subject; the gold's ±120 window carries the value but **none** of them (score 0,
damped to 1/2) while a competitor's window happens to carry all five (score 5, undamped).
**A value-adjacency window cannot carry a document-level qualifier** — run 9's window is
right for competing values, which must be adjacent, and wrong for the entity anchor, which
need not be.

### What else the wire settled ($0)

1. **q2-046 is not the temper's collateral and never was S2's.** Its single grounded
   observation is damped by the **pre-existing competition term** (n_comp = 12), not by the
   anchor — which does not fire there at all (no discriminating terms on a one-observation
   channel). S4'' named it because **r09c mis-attributed all three of its collateral rows to
   S2**; the wire now shows S2 was responsible for q2-009 alone, which duly returned to
   correct once S2 joined. The r09c reading's diagnostic 5 is corrected here.
2. **The "S2 shrink" census is not a valid measure of D3.** It reads what a *site returned*,
   not what the executor kept — post-join the site legitimately returns a small payload while
   the channel grows (q2-057: site reply 4, committed channel 9). Nine rows still "shrink" by
   that measure with the join in place; the measure, not the join, is what that number is
   about.
3. **The anchor never fires on q2-018** under either window: the fax/telephone class produces
   no discriminating term in that channel. Prediction 2 is refuted with a mechanism.

### Predictions scored

P1 **unread** (q2-071 cold). P2 **REFUTED** — the anchor does not fire on q2-018 at all.
P3 **REFUTED in both halves** — collateral read 2, below the predicted 3–6, and the criterion
that failed was S4'', not S2''. P4 **HALF** — q2-009 returned to correct as predicted;
q2-046 did not, because it was never S2's row. P5 **unread**, and now externally blocked.

### Disclosures

- **Deviation:** the pre-declared second pass was interrupted by the API usage limit, not by
  a decision. It is reported as interrupted, never as read.
- The stalled pass was left retrying against an account limit for ~8 minutes before it was
  killed; nothing was written from it.
- A wait-loop used to watch the sweeps matched **its own** command line in `pgrep`, so pass 1
  was reported as "still running" for ~13 minutes after it had finished cleanly. No result
  depends on it; corrected by matching the interpreter, not the pattern.
- The census's gold test is a normalised-equality-or-token-containment match, not the judge;
  the 12 strictly-harmful rows are the set that matters and each is named in the artefact.

### What the checkpoint means

D3 is **confirmed** on its one readable target (q2-009 returned to correct; no row lost a
correct commit to the join). D1's detector is sound and D2's *placement* is sound — the
defect is one frozen constant: the **window**. That is not a lever failure, it is a scope
error found by a $0 census that cost nothing and would have cost ~$40 to find at the gate.

**Enacted:** run 14 not fired; this branch stays unmerged; master keeps the r09-reverted
state; the §6.12 block stands; nothing bought. The successor decision is conferred in
`docs/unification/conferrals/r09d-window-conferral.md`.


## ADDENDUM — the rescope, and a census that was measuring itself (2026-08-24, $0)

Ruling 1 landed under TDD (`ee7de62`): `matching.anchor_window` names the choice in one
place, both mint sites read it, the competition term keeps run 9's ±120. Suite 2687, ruff
green.

**Then the acceptance census returned the same numbers as before the change — 42 / 26 / 12,
byte for byte.** The census was re-implementing the window instead of reading the deployed
one, so it was blind to the very constant it existed to price. Rewritten to measure the
deployed rule end-to-end (mint the channel through `observe_hits`, compare each
observation's FINAL factor against the competition term alone: a final below the base IS the
anchor firing, whatever window the code chose), and run on both trees:

| tree | fires | damps the gold | **strictly harmful (raw)** | clean firings |
|---|---|---|---|---|
| pre-rescope, ±120 quote window (`af8112e`) | 50 | 33 | **10** | 17 |
| rescoped, document-scoped (`ee7de62`) | 42 | 22 | **5** | 20 |

**The rescope's direction is confirmed and its magnitude was overstated.** Harm halves
(10 → 5) and clean firings rise (17 → 20) — but the "strictly harmful on 1" that justified
ruling 1 came from the blind census and was never a deployed measure. Published rather than
quietly restated.

**All five remaining rows were then inspected by hand**, because a bar of ≤ 2 cannot be read
off a measure this coarse:

| row | reading | genuine? |
|---|---|---|
| multi-value-table class (run-8 named) | the **gold is damped to 1/4** while the competing value stays at its base — ranking inverted | **YES** |
| a location question | the **gold is damped** while a vacuous non-answer stays at 1.0 | **YES** |
| a vesting-period question | a gold phrasing is damped, but another gold witness and a non-gold both sit at the same base | marginal |
| an antibody-titre question | the damped value is gold-EQUIVALENT phrasing; three undamped witnesses are also gold phrasings (the judge graded this class correct) | no — census artefact |
| a channel-id question | the gold's leading witness is undamped at 1.0; only a second copy is damped | no — census artefact |

**Verified: 2 genuine inversions, 1 marginal, 2 false positives of the census's gold test.**
The frozen bar (strictly-harmful ≤ 2, clean firings ≥ 15) therefore reads **met on the strict
count (2 ≤ 2) and missed on the inclusive one (3 > 2)**, with clean firings 20 ≥ 15 either
way. A bar that lands exactly on an interpretation boundary is a ruling, not a reading —
conferred rather than resolved here.

Decision-relevant beside it: one of the two genuine inversions is the **run-8 named
wrong-commit class**, so on that row the anchor as it stands would push a known-bad
commit further the wrong way.

**Standing lesson, registered:** *a census must read the deployed rule end-to-end, never
re-implement the constant it is pricing.* This is the third instance of the r05 class in
this arc (the carrier audit's measures, r09c's substring grader, and now this), and the
first that produced identical before/after numbers — the signature to watch for.
