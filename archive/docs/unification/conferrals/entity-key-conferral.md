# Conferral — the entity key: what the payload already carries, and the readability wall

**Status:** open, awaiting an owner ruling. Written 2026-08-25, after the $0 census below and
before any `src/` change. Prices queue item 3 of the r09d disposition ("pre-register the
**extract-side entity field**") against a cheaper alternative the census surfaced.

## Why this document

The r09d disposition froze a three-item queue for 2026-09-01: (1) warm the cold rows and
re-read the sweep, (2) re-price run 14 on the warmed record, (3) pre-register the extract-side
entity field. Item 3 assumed the qualifier that separates the gold's carrier from the
competitor's is **not** in the payload today and must be minted by the extractor — a change
that grows the payload (the named unservable-fixture class) and needs its own grounding rule.

A $0 census run before writing this document says that assumption is **wrong in the cheap
direction**: on the rows where such a qualifier exists at all, it is **already carried**. That
makes a decide-side rule the cheaper candidate and item 3 largely unnecessary. The same census
also found the constraint that now governs everything: **the rows that would prove it are the
rows that cannot be read without spend.**

## What was measured

Instrument: `entity_key_census.py` (kept with the arc's artefacts under
`$LIFE_AGENT_KB/eval/window/`), run against the **tree of record** — the parked
`r09d-entity-anchor` branch — over the 104-question set, warm cache, `RefusingClient`, **$0**.

The rule was written into the instrument's docstring **before it ran**:

> **E1.** `ids(question)` = identifier-like tokens only — CamelCase (≥2 humps), snake_case,
> filename-with-extension, ALLCAPS — never ordinary English words. `key_hit(o)` = **every** id
> in `ids(question)` occurs verbatim in the observation's carrier. Applied as a **hard filter**
> (drop the observations that do not key, if any observation keys), never as a soft factor.
> Carriers measured: the observation's own **quote** (what the wire carries today) and its
> whole **chunk** (what the extractor sees).

This is deliberately *not* the r09d anchor. That lever scored documents by **vocabulary
overlap** and was refuted at $0 across three variants. E1 is an **exact, typed** key applied as
a filter. The distinction is the whole hypothesis.

**Disclosed limitation, stated before the numbers:** unlike the r09d censuses, this one models
a **proposed** rule — there is no deployed constant for it to read end-to-end, so the standing
"read the deployed rule, never re-implement it" discipline cannot apply here. And it measures
the **channel**, not the decision: the layer gap between them is real and is exactly what r06's
28% floor turned out to be.

## What it read

| | quote carrier | chunk carrier |
|---|---|---|
| questions with no identifier token at all (rule inapplicable) | 62 | 62 |
| repair candidates (a non-gold dropped, a gold kept) | 2 | **3** |
| harms (a gold observation dropped) | 2 | **0** |
| no-op | 37 | 38 |
| quiet / cold | 1 / 0 | 1 / 0 |

Three things follow.

1. **The key is inapplicable to 60% of the corpus by construction.** 62 of 104 questions carry
   no identifier-like token, so E1 can never fire on them. Whatever it is worth, it is worth it
   on a minority.
2. **The chunk is the right carrier, and the quote is not.** Both of the quote-scope harms are
   **all-gold channels** — every observation is a gold variant, so the filter removes redundant
   witnesses rather than changing a leader. At chunk scope they vanish entirely: the redundant
   gold witnesses live in chunks that *do* carry the ids, just not inside their quote spans.
3. **The extract-side field is not needed for this mechanism.** The qualifier is already in the
   chunk, which the decide path holds at mint time. Item 3's payload growth, its new grounding
   rule and its corpus re-extraction all buy something the wire already has.

### The three chunk-scope repair candidates, at the decision layer

Read from run 13's own decision rows (`gate-20260824T144002`), $0:

| row | run 13's action | leader | what E1 would do |
|---|---|---|---|
| a known **wrong commit** | reported at p≈0.94 | not the gold | drops **both** non-gold observations |
| an **abstain** | withheld, p_none≈0.22 | the gold, at 0.667 | drops a non-gold; the gold's share rises |
| an already-correct row | reported at p≈0.98 | the gold | drops a non-gold; no change of leader |

That is the best profile any lever has shown in this arc: one named wrong-commit row addressed,
one withhold→answer conversion, zero channel harms. **It is also unreadable.**

## The readability wall — the finding that governs the ruling

The $0 sweep replays only the questions whose deliberate edge is already cached; a cold one is
excluded **by name** so the instrument cannot spend. On the tree of record that set is 58 of
104. Intersecting it with E1:

- E1-applicable **and** readable at $0: **23** of 41.
- Of E1's three repair candidates, **one** is readable — the row that is *already correct*.
  The wrong-commit row and the abstain row are **both cold**.
- Of the four known wrong commits, **one** is readable; three are cold.

So building E1 now and sweeping it at $0 would measure ~nothing that matters, and would repeat
r09d's INCONCLUSIVE reading exactly — the failure that the disposition's own coldness clause
was written to prevent. **Coldness, not design, is the binding constraint.**

Two facts that price the way out, both checked rather than assumed:

- The deliberate cache key is `(question, corpus digest, model, prompt, max_turns)`. It does
  **not** depend on our tree, so a warmed row **stays** warm across tempers. Warming is a
  one-time purchase, not a per-iteration toll.
- Run 6's nine cold deliberates cost $10.87 — about **$1.2 a row**. Warming the six rows that
  matter (the four known wrong commits plus E1's two cold candidates) is therefore ≈ **$7**;
  warming all 46 excluded rows is ≈ **$55**, more than a gate run.

Run 6's incident applies to any warming: a blind decline must never be cached as evidence. The
guard at `deliberate.answer` exists; warming must run with the full daemon+bridge stack up and
each reply verified to be an answer, not a decline.

## Options

**A — targeted warm (~$7), then read.** After 2026-09-01, warm the deliberate cache for the six
rows that matter with the full stack up, then re-read the $0 sweep on the tree of record. This
answers the standing question run 13 left open (does the parked tree still commit those four
rows wrong?), and it makes every later $0 sweep decisive on the rows that decide. E1 is
pre-registered and built only after that. *Risk:* $7 buys a reading, not a fix; the four rows
may all still commit wrong, which is information but not progress.

**B — fire run 14 as-is (~$2–16 by the script's own banner).** The gates are armed and rehearsed
on the parked tree. Predicted to **FAIL** the zero-new-wrong-commits conjunct: nothing measured
on the r09b or r09c trees flipped any of the four, and D3's effect on three of them was never
readable. It would buy the Δ reading and warm rows as a side effect. *Risk:* a run fired
against its own prediction, and the FAIL branch stops work for another ruling.

**C — build E1 now, defer its reading.** Zero spend today; the code parks beside D3 until a warm
makes it readable. *Risk:* this is building blind, which is what r09b/r09c/r09d each did — three
for three refuted. The census is channel-level evidence only.

**D — park the deploy arc.** Spend nothing, ship nothing, move to other roadmap work until
there is a reason to spend. *Risk:* the §6.12 block stays shut indefinitely and the parked D3
rots against a moving tree.

## Recommendation

**A**, and retire item 3. Targeted warming is the highest information per dollar available:
it is a one-time $7, it converts the whole $0 sweep apparatus from inconclusive to decisive,
and it answers a question that is already blocking (whether the tree of record still commits
the four rows wrong) *before* any further lever is built. E1 is the strongest candidate this
arc has produced, but on this evidence it is a channel result, and the r09d lesson is that a
channel result is not a reason to ship.

The standing hard clause carries into whatever is pre-registered next: **no lever ships while
it makes a named wrong-commit class worse.**

## Questions

1. **Which option** — A (targeted warm ≈$7, then read), B (fire run 14 as-is), C (build E1 now
   and defer the reading), or D (park the arc)?
2. **Does the extract-side entity field retire** from the queue, given the qualifier is already
   carried in the chunk — or does it stay as a fallback if the decide-side key reads badly?
3. **If E1 is eventually pre-registered, what is its bar?** Zero channel harms *and* at least
   one wrong-commit repair on the sweep, or is a withhold→correct conversion (reach) enough on
   its own?

---

## RULINGS (owner, interviewed 2026-08-25)

1. **Option A** — targeted warm, then read. Not B (fire run 14 as-is), not C (build E1 blind),
   not D (park).
2. **The extract-side entity field RETIRES** from the queue. The qualifier is already carried
   in the chunk; if a decide-side key later reads badly for a reason that is specifically about
   extraction, it re-opens under its own pre-registration.
3. **E1's bar, if it is pre-registered: zero channel harms AND at least one wrong-commit
   repair on the sweep.** A withhold→answer conversion alone does not license shipping — the
   block that keeps master undeployed is a wrong-commit block, not a reach block.

### Corrections to this document's own evidence, found while enacting ruling 1

Published rather than amended in place, per the r09c precedent.

1. **The warming price basis above is wrong.** The wall is **not** the deliberate edge: every
   named row preflights **warm** on the deliberate key (checked through the deployed preflight,
   `replay_audit.deliberate_is_warm`, $0). The exclusions the sweep reports are a **§18.9
   derivation going cold mid-loop** — a probe fetching chunks this tree has never extracted,
   which is the r08 top-k footprint M1.5 named. Those are haiku-class extractions, not $1.2
   opus deliberates, so the ~$7 estimate is an overestimate of unknown but smaller size.
2. **The named row set is five, not six** — the four known wrong commits plus the entity key's
   two cold candidates, of which one is already among the four.
3. **Three of the five already serve at $0.** The rehearsal found only two rows still cold; the
   other three warmed since r09d read, which is the §18.9 warm-through's pass-order dependence
   working in our favour for once. Ruling 1's action is therefore much smaller than priced —
   and a $0 sweep on the tree of record became possible immediately, without waiting for
   2026-09-01. It was started as soon as the rehearsal read.
4. **A defect in the replay's $0 contract, found by the rehearsal and fixed.** `deps.client`
   covers only the seams the bridge threads a client through; `core/subject` and
   `core/temporal_intent` build their own on a cache miss, and — the seam that actually fired —
   `core/joint_extract` calls `anthropic_complete` **directly** from the corroborate probe. The
   replay was no-spend for exactly as long as some earlier refusal kept firing. Every published
   reading remains $0 **in fact** (nothing was ever billed); what was missing was the
   guarantee. Fixed by consuming `collapse/drive._SPEND_SEAMS` — the table the recorder already
   owns, written after M0 found this same hole — rather than keeping a second copy of the list.
   `deliberate.answer` is deliberately excluded: criterion 3 preflights that edge per question,
   and sealing it would refuse the warm cached deliberates the replay depends on.

### Artefacts

- `$LIFE_AGENT_KB/eval/gate-outside-option/warm-rows.sh` + `warm_rows.py` — ruling 1's
  instrument, prepared and **rehearsed at $0** (`WARM_DRY_RUN=1`), tree-gated to the parked
  tree of record, budget-capped, and acceptance-tested by a second refusing pass: a row counts
  as warmed only when the $0 replay can serve it.
- `$LIFE_AGENT_KB/eval/window/e1-*` — the census, its two carrier variants and their logs.
- The spend-seam fix rides the tree of record under TDD (RED watched on both tests).

The account's usage limit was **re-verified live on 2026-08-25** rather than inherited: access
returns 2026-09-01 00:00 UTC. Ruling 1's priced step waits for that date; its $0 half did not.
