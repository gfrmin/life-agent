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

**PENDING below this line: D1, D2, D3, the sweep, run 14.**
