# r29 — the answer-shape census — PRE-REGISTRATION (2026-08-28)

> **This document is the pre-registration. It is committed BEFORE the instrument exists and
> before any label is produced; git history is the proof.** r29 is a $0 read. It adopts
> nothing, moves no decision path, and changes no file under `src/`.

## STATE

- master `fb89f07` (r28 merged: the gate publishes `Δ = Δ_answers + Δ_spend`; the baseline
  argument is required, so no report can render without naming its arm). Suite 2894 passed /
  35 deselected; ruff + mypy clean; replay 314/314 pure equality on `m5-base`.
- **The mandate.** The plan of 2026-08-28 proposes re-deriving the answer as *a claim about a
  quantity* valued by a loss whose shape is a property of the question. That is a foundations
  change: it opens §4.4's gauge and §5's claim space, both owner-adopted. r29 exists so the
  size of that change is bought with evidence rather than asserted — and so it can be
  **rescoped or stopped** before any `src/` edit.
- **What provoked it.** Three structural gaps were verified in tree this session: the claim
  space holds only verbatim extracted candidates; the utility is 0-1 over exact match, so for
  a quantity that must be *computed* P(exact) ≈ 0 and the 0.90 bar is unreachable at any
  price; and no transform carries a quantity parameter, so marginal-VOI-against-marginal-cost
  has no continuum to optimise over. Each is a claim about the *design*. Whether any of them
  binds depends on the *questions*, which is what this census reads.

## The three reads

### Read 1 — the answer-shape census

Two axes, each a closed vocabulary, classified **from question text alone** (the gold answer
is deliberately NOT an input, so one rule serves both populations):

- **answer space** — `exact` · `quantity` · `threshold` · `set`
- **truth provenance** — `verbatim` (the answer stands as a span in some document) ·
  `computed` (it must be derived: summed, counted, compared or combined across documents)

The axes are orthogonal and both are load-bearing. `quantity ∧ verbatim` is a recorded
figure: today's 0-1 loss is *attainable* there, merely wasteful (a near-miss scores zero).
`quantity ∧ computed` is the class where the loss is *structurally unreachable*, and the
frozen consequence below turns on it.

**Two populations, read separately.** The harvested real asks (250) and the gate set (104).
These are not independent: the gate set was **constructed** from corpus facts chosen to be
answerable, so it cannot be evidence about the shape of the owner's questions — it is a
census of the *eval instrument*, reported for contrast only. The owner-origin population is
the harvest minus every ask whose normalised text matches a gate question.

### Read 2 — the structural-abstention prediction

**Prediction, stated before the read:** questions classified `computed` abstain at a rate at
or above 0.95, AND materially above the `verbatim` rate. Mechanism: P(exact match) ≈ 0 for a
figure no document carries, so no evidence budget clears a 0.90 bar. Refuted if either
conjunct fails. Published either way. Population: the decided owner-origin asks.

### Read 3 — separating the two candidate causes of run 17's collapse

Run 17 (`gate-20260826T025059`) enacted A2's every-terminal grow offer and read FAIL
0.743 / +0.238, answer rate 0.62 → 0.49, dispersed 37 → 51. Run 18 reverted the enactment and
reproduced run 16. Two candidates:

- **(a) hand-priced VOI** — the grow actuators' hand-set cold Beta priors over-value a
  re-read, so the argmax buys gathers that do not pay.
- **(b) flat utility units** — `preference` is built from a flat `u_bar` with `u_correct = 1`
  for every question, so gathering can look worthwhile where answering is not.

**(a) is directly measurable at $0** against the gather-outcome stream, which records one row
per enacted grow with its context vector and a `recovered` flag: cold prior mean vs warm
posterior mean vs realised rate, per probe and per context. **(b) is not separable at $0** —
it would need the engine re-run under rescaled units, which is neither free nor readable from
records. r29 therefore publishes (a)'s magnitude and the flip set's spend signature, and
**states explicitly what it cannot settle**. Sufficiency is out of scope for this read.

## Frozen criteria

| | Criterion |
|---|---|
| **C1** | **r29 adopts nothing.** No file under `src/` changes on this branch. Verified by `git diff --stat master -- src/` empty at the read, printed in the report. |
| **C2** | **Criteria before labels.** This pre-registration — criteria, rule table, sample plan, frozen consequence — is committed before the instrument exists and before any label is produced. The report's chronology names the commits in order. |
| **C3** | **Conservative default.** An unmatched question classifies `exact` + `verbatim` — the shape under which today's design is *adequate*. The census is therefore biased toward "the generalisation is niche"; any finding of `quantity`/`threshold`/`set` or `computed` survives that bias. RED under a mutation defaulting to `quantity` + `computed`. |
| **C4** | **Contamination named.** The harvest is split into eval-derived and owner-origin by normalised-text match against the gate set, and every headline count is published on the owner-origin subset separately. A census reporting only the pooled number FAILS this criterion. |
| **C5** | **Measured, not assumed, classifier accuracy.** A blind manual reference on a seeded stratified sample of 50 questions (25 gate + 25 owner-origin, `random.Random(29)` over sorted ids) is produced BEFORE the classifier runs on real data. Per-axis agreement and the direction of every disagreement are published. **If agreement on either axis is below 0.80, that axis's counts are published as bounds, not point estimates.** |
| **C6** | **Read 2's prediction is falsifiable and pre-stated** (above), and is published whichever way it reads. |
| **C7** | **Read 3 reads the deployed constants end to end.** The grow priors come from `life_agent.core.pricing.GROW_ACTUATORS` by import and the warm fold from `life_agent.core.gather_outcomes.warm_counts` — never a retyped number. RED under a mutation that retypes a prior. (r05's lesson; r10's carrier mapping is the instance that flipped a verdict.) |
| **C8** | **No confounding a flip with a rate.** The run-17-vs-run-18 comparison publishes the per-row flip set computed from the two paired archives alongside the aggregate answer-rate change. |
| **C9** | **PII.** No question text, gold answer, corpus value, personal name, identifier or owner-specific path enters the tree. Classes, counts and generic examples only. `pii_check.py` exit 0 with the private name layer live. |
| **C10** | **G2 — the 314-fixture replay, pure equality on `m5-base`.** r29 touches no decision path, so anything but 314/314 is a defect in r29. |
| **C11** | **Reproduced twice.** The census runs twice; every published count identical. A count that moves is the instrument, not the finding. |

## The classification rules, frozen

Question text is lowercased and whitespace-collapsed. Rules are ordered; the first match
wins; no match falls to the conservative default (C3).

**Axis 1 — answer space**, in precedence order `threshold` → `set` → `quantity` → `exact`:

1. `threshold` — a comparator against a magnitude: `more than`, `less than`, `at least`,
   `at most`, `over`/`under` before a number, `exceed`, `above`/`below` before a number,
   `greater than`, `higher than`, `lower than`, or an interrogative-initial yes/no form
   (`did`/`is`/`was`/`were`/`does`/`do`/`has`/`have` …) carrying a numeric token.
2. `set` — an enumeration is asked for: `list`, `which ones`, `all of the`, `what are the`,
   `who are the`, `name the`, `enumerate`, `every` before a plural noun.
3. `quantity` — the answer is a magnitude: `how many`, `how much`, `total`, `sum`, `average`,
   `mean of`, `count of`, `number of`, `amount`, `balance`, `aggregate`.
4. `exact` — default.

**Axis 2 — truth provenance**, `computed` iff an explicit aggregation or multi-source marker
is present, else `verbatim` (the conservative default):

`across all` · `across my` · `across every` · `in total` · `total of` · `total across` ·
`sum of` · `added up` · `add up` · `combined` · `altogether` · `on average` · `average of` ·
`overall total` · `how many … (do i have|have i)` · `each of my` · `all of my … (combined|
together|total)`.

A bare `total` adjacent to a recorded field (e.g. a figure a document states) does **not**
mark `computed` — that is the conservative default doing its work, and it is the reason axis
2 is not a restatement of axis 1.

**Known limits, stated in advance.** These are lexical rules over question surface form. They
cannot see whether a corpus actually carries the figure; `verbatim` here means *the question
does not demand a derivation*, not *the answer was found*. C5 measures what this costs.

## Frozen consequence

Read on the **owner-origin** population, `exact ∧ verbatim` as the fraction of classified
questions:

- **≥ 0.85 → RESCOPE.** The generalisation is niche. r30 reduces to feature-indexed
  cost-of-wrong plus question-dependent VOI units; precision-parameterised claims and the
  quantity-parameterised experiment are dropped from its scope.
- **< 0.85 and read 2's prediction holds → PROCEED** with r30 as the plan describes.
- **< 0.85 and read 2's prediction is refuted → STOP for an owner ruling.** The structural
  story would be wrong: the shapes are there but abstention is not explained by them, and the
  plan's premise needs re-derivation before anything is built.

## Gates

**G1** `uv run pytest -m "not llm and not system"` (`TMPDIR=~/.cache/tmp`) + `ruff check .` +
`mypy` · **G2** `PYTHONHASHSEED=0 scripts/collapse_replay.py --checkpoint m5-base`, 314/314 ·
**G3** the census reproduced twice, counts identical · **G4** every criterion whose mutation
is expressible demonstrated RED then restored; any criterion whose mutation cannot be
expressed is disclosed as such rather than claimed.

---

# RESULTS (read 2026-08-28, $0, nothing adopted)

> Chronology, for C2: the pre-registration above is commit `3d075b9`. The blind manual
> reference (50 labels, digest `4fb00490…`) was written next, before `scripts/answer_shape_census.py`
> existed. The instrument was then built under TDD (RED first: a collection error, the module
> absent) and only then pointed at the records. Nothing above this line was edited after the
> instrument ran.

**Verdict: the frozen consequence's middle branch — PROCEED with r30 as the plan describes.**
Owner-origin `exact ∧ verbatim` reads **0.753**, under the 0.85 bar, and read 2's prediction
holds. Both hold under the classifier's own measured bias, which runs one way only.

## Read 1 — the census

**The harvest is 42% eval corpus.** All 104 gate questions appear verbatim in the 250-row
harvest of "real asks", so the owner-origin population is exactly 146. This is not an estimate:
the match is textual and total. Any reading of "what does the owner ask?" taken off the pooled
file would have been reading the eval instrument back to itself for two-fifths of its evidence.

| population | n | exact | quantity | threshold | set | verbatim | computed | `exact ∧ verbatim` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gate set | 104 | 82 | 19 | 1 | 2 | 104 | 0 | 82 (**0.79**) |
| owner-origin | 146 | 110 | 29 | 0 | 7 | 136 | 10 | 110 (**0.75**) |

The gate set carries **zero** `computed` questions. That is not a fact about the corpus; it is
a fact about how the gate set was built — from corpus spans chosen because they are
answerable. It is reported for contrast and must never be read as evidence about the owner's
questions (C4).

**C5 — measured agreement, and the bias runs one way.** Against the blind manual reference:

| axis | agreement | flagged | direction of every disagreement |
|---|---|---|---|
| answer space | 37/50 = **0.74** | **BOUNDS-ONLY** | 11 of 13 are *X → exact* (quantity 5 · set 4 · threshold 2); 2 run the other way |
| truth provenance | 40/50 = **0.80** | not flagged (bar is `< 0.80`) | **10 of 10 are `computed` → `verbatim`** |

The direction matters more than the rate. On provenance the classifier **never once**
over-called `computed`: its 10 is a floor, not an estimate. On answer space it under-calls
non-`exact` 11 times against 2 the other way. So **0.753 is an upper bound** on owner-origin
`exact ∧ verbatim`, exactly as C3's conservative default was designed to guarantee. The blind
manual reference puts the same quantity at **12/25 = 0.48** on the owner sample. The frozen
0.85 bar is cleared with room under either figure, which is why the verdict does not turn on
the classifier's accuracy.

## Read 2 — the structural-abstention prediction: CONFIRMED, on a small sample

Owner-origin, decided rows only (61 of 146 carry no recorded action and are counted, not
dropped):

| class | n | abstained | rate |
|---|---:|---:|---:|
| `computed` | 8 | 8 | **1.00** |
| `verbatim` | 77 | 48 | 0.62 |
| by space — `exact` | 63 | 35 | 0.56 |
| by space — `quantity` | 19 | 18 | **0.95** |
| by space — `set` | 3 | 3 | **1.00** |
| by space — `threshold` | 0 | — | — |

Both pre-stated conjuncts hold: the rate is at 0.95 (it is 1.00) and it is materially above
the `verbatim` rate. Under the `verbatim` rate as null, P(all 8 abstain) = **0.023**.

**Disclosed against the finding:** n = 8. The 95% one-sided Clopper–Pearson lower bound on the
`computed` abstention rate is **0.688** — the sample cannot exclude a true rate as low as 0.69,
which would not clear the pre-stated 0.95 as a *bound*. The prediction is confirmed on the
point estimate and on the comparison, not on the bound. The by-space gradient (0.56 → 0.95 →
1.00) is the more robust half of the read, and it says the same thing: **abstention tracks
answer shape**, and it does so most sharply exactly where the claim space cannot represent the
answer.

## Read 3 — run 17's collapse: candidate (a) refuted, (b) unrefuted, and a third cause found

**The flip set (C8).** Run 17 against run 18 on the same 104 rows, censored dropped:

| | run 17 (A2 enacted) | run 18 (latch restored) |
|---|---:|---:|
| asserts | 51 | 63 |
| answer rate | 0.490 | 0.606 |
| mean spend / question | **$0.0433** | $0.0036 |

17 rows flip: **report → abstain 14**, report → hedge 1, abstain → hedge 1, abstain → report 1.
Run 17 paid **12× more** for **12 fewer answers**. On the 17 flipped rows it spent $0.0203
against run 18's $0.0013 — *below* its own per-question average, so the harm is diffuse, not
concentrated in the heaviest spenders.

**Candidate (a) — the hand-set cold priors — is REFUTED as the operative cause.** Read against
the fold run 17's decisions actually saw (every row written before the run began):

| probe | cost | cold prior mean | realised, pre-run-17 | warm posterior at run 17 | prior weight | g / cost |
|---|---:|---:|---:|---:|---:|---:|
| `retrieve_rerank` | 0.004 | 0.300 | 17/390 = 0.044 | **0.050** | 2.5% | **12.5×** |
| `retrieve_expand` | 0.006 | 0.350 | 14/382 = 0.037 | **0.045** | 2.6% | 7.4× |
| `re_extract_strong` | 0.020 | 0.400 | 16/378 = 0.042 | **0.052** | 2.6% | 2.6× |

By run 17 the stream held ~380 rows per probe, so the declared cold prior (strength 10) carried
**2.5–2.6%** of each fold and the daemon's `g` was ≈ 0.05, not 0.35. Per context the same
holds where it matters: 269 of run 17's 292 enactments fell in the three well-populated
contexts, prior weight 2.3–4.3%. The prior was not what scheduled those gathers.

**The priors are nevertheless wrong — in level and in order.** They sit 6.9× / 9.6× / 9.5×
above the realised rates, and their *ranking is inverted*: the table prices the most expensive
actuator (`re_extract_strong`, 5× the cheapest) as the most likely to recover, and it is in
fact the least. A cold start on this table buys the worst actuator first. That is a real defect
with a real price; it simply was not the one that fired at run 17.

**Candidate (b) — flat units — is consistent with the record and unrefuted.** With `g` ≈ 0.05
against an actuator cost of 0.004 utility units, and `u_correct ≡ 1` for **every** question,
gathering pays by 2.6–12.5× everywhere. That is the flat gauge's exact signature: one trigger,
uniform across questions, indifferent to what an answer is worth. **It is not isolated** — that
would need the engine re-run under rescaled units, which is neither free nor readable from
records, and r29 does not claim it (the pre-registration said so before the read).

**The third cause, which neither candidate named: the gather-outcome proxy is one-sided, and
the stream is now contaminated by a policy that no longer exists.**

| stream segment | rows | recovered | rate |
|---|---:|---:|---:|
| before run 16 | 1019 | 38 | 0.037 |
| run 16 — withhold-only latch | 131 | 9 | 0.069 |
| **run 17 — A2's every-terminal offer** | **292** | **126** | **0.432** |
| run 18 — latch restored | 126 | 6 | 0.048 |

Two things follow. First, `recovered = (evidence changed) ∧ (final effector == report)` cannot
express harm: a grow that *destroys* a report and one that was merely useless both record
`False`, and — under an every-terminal offer — a grow after a terminal that was already going
to report records `True`. The rate tracks the A2 enactment exactly (0.069 → **0.432** → 0.048);
the stream carries no terminal field, so the mechanism is inferred from A2's semantics rather
than measured, and is stated as an inference.

Second, the stream is **append-only with no run or policy segmentation**, so those 292 rows are
permanent. The pooled realised rate now reads **0.1133**; excluding run 17's rows it reads
**0.0411**. One reverted policy's single run inflates the quantity by **2.8×** — and that
quantity is precisely what the plan's r30 proposes to ground the grow priors in. Grounding them
on the stream as it stands would teach the agent that gathering works three times better than
it does, using evidence from a policy the owner ruled out.

`gather_outcomes.py` states its own safety argument: a `g` learned from this proxy "can at
worst over-try gathers, never mis-report, because reporting stays the exact app-side
threshold". The threshold did hold. Run 17 falsifies the consequence anyway: over-trying
gathers cost **14 correct reports**, because the bought evidence joins the channel (r09
semantics) and disperses the posterior *before* the unchanged threshold is applied to it. The
protection was never the threshold; it was the report-economy latch that stopped the gather
from happening.

## Criterion verdicts

| | verdict |
|---|---|
| **C1** adopts nothing | **MET** — `git diff --stat master -- src/` empty; the branch adds one script, one test file, this report |
| **C2** criteria before labels | **MET** — prereg `3d075b9`, then the manual reference, then the instrument |
| **C3** conservative default | **MET** — and load-bearing: the measured bias runs one way, which is what makes 0.753 an upper bound. RED under M1 |
| **C4** contamination named | **MET** — 104 of 250 eval-derived; every headline published on the owner subset. RED under M4 |
| **C5** measured accuracy | **MET, with a disclosure** — space 0.74 flagged BOUNDS-ONLY; provenance lands on **exactly** 0.80 and so is not flagged, one disagreement from being so. RED under M5 |
| **C6** falsifiable prediction | **MET** — stated before the read, confirmed on the point estimate, its bound published against it |
| **C7** deployed constants | **MET** — `PRC.GROW_ACTUATORS` imported, the fold cross-checked against `GO.warm_counts`. RED under M2 and M3 |
| **C8** flip beside rate | **MET** — 17 flips published beside 51-vs-63 asserts and both answer rates |
| **C9** PII | **MET** — `pii_check.py` exit 0 with the private name layer live; no question text, gold, value, id or path in tree |
| **C10** G2 | **MET** — 314/314 pure equality on `m5-base` |
| **C11** reproduced twice | **MET** — passes 1 and 2 byte-identical (`ef37de68…`); a third pass after the lint fixes is identical again |

## Deviations, disclosed

1. **The window defect that inverted read 3, caught before the verdict.** The first pass placed
   each gate run's window by parsing its `run_id` — which carries **local** time, while
   `created_at` is UTC. Every run landed 8 hours from its own rows, and the instrument reported
   that **run 17 wrote zero gather outcomes**: the exact opposite of the truth, which is that
   run 17 wrote the largest single block in the stream. It was caught by noticing that rows
   existed on run days but never inside a run window. Fixed, pinned by a named test, and RED
   under M6. This is the r05/r10 lesson recurring in a new place: *the instrument re-derived a
   quantity the records already carried*, and got it wrong.
2. **The window attribution is an extension beyond C7's frozen text**, added after the first
   reading in response to (1). C7 asked for the cold prior, the warm posterior at the stream
   head, and the realised rate; the per-run split is more than that, and it is what changed the
   verdict on candidate (a). Named as an extension rather than folded in silently.
3. **The first real-data run crashed at the write** — tuple keys in the direction tallies made
   the whole result unserialisable. A census that cannot write its own record is not a read;
   pinned by a serialisability test rather than fixed in place.
4. **The manual reference is not perfectly blind.** ~36 questions were read while the frozen
   rule table was being designed; **7 of those fall inside the 50-question C5 sample**. The
   priming can only have pulled the manual labels *toward* the rules, i.e. toward agreement,
   so the measured 0.74 / 0.80 are if anything optimistic — which strengthens rather than
   weakens the "0.753 is an upper bound" conclusion.
5. **`threshold` is effectively invisible to the frozen rules**: 1 hit in 104 gate questions,
   0 in 146 owner asks, against 2 in the manual reference's 25-question owner sample. The
   frozen comparator list wants a numeric token, and the owner's comparison questions
   ("how do these two compare?") carry none. Named, not fixed — the rules were frozen.

## What this read does NOT settle

- **Whether (b) caused run 17.** Consistent, unrefuted, and the only candidate left standing
  is not the same as isolated. Isolation needs the engine re-run under rescaled units.
- **Whether `computed` questions abstain at ~1.00 in general.** n = 8, bound 0.69.
- **Whether the answer would be *right* if the shapes were representable.** The census reads
  what is asked and what was decided, never whether a wider claim space would have been
  correct. That is r30's question and r31's price.

## Consequence, as frozen

`0.753 < 0.85` and read 2's prediction holds ⇒ **PROCEED with r30 as the plan describes.**
Three riders the read attaches, none of them renegotiations:

1. **r30 step 4 ("ground the grow priors in the gather-outcome stream") must not read the
   stream as it stands.** Run 17's 292 rows are a reverted policy's evidence and inflate the
   realised rate 2.8×. Either segment the stream by policy, or exclude that window, and say
   which — before the priors are refit.
2. **A one-sided proxy cannot price a two-sided decision.** No refit of `g` on `recovered`
   would have prevented run 17, because `recovered` has no way to say "this gather cost an
   answer". Whatever r30 builds for the quantity-parameterised experiment needs a harm term.
3. **The grow price table's ordering is inverted against realised recovery** and is worth
   fixing on its own evidence, independent of the units work — but under the standing hard
   clause it ships only with its wrong-commit classes published.
