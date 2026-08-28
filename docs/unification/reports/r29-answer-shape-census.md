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
