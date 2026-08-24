# Conferral — r09d's disposition, and what the spend freeze changes

**Status: the entity anchor is DONE** by its own pre-registered hard clause (reading:
`docs/unification/reports/r09d-entity-anchor.md`). Two questions remain: what happens to the
branch, and what the programme aims at when spend returns on **2026-09-01**.

## What the checkpoint leaves standing

- **D3, the S2 join — confirmed.** The one replace site r09 left untouched now joins; on its
  one readable target a correct commit came back and no row lost one. It is a decision-path
  change, so by standing practice it rides a gate run rather than merging on a $0 reading.
- **The anchor (D1/D2/D4) — retired.** Three trees, one invariant set of five harmful rows.
- **The blocking rows are untouched.** q2-018 and q2-071 still commit wrong; q2-071 and
  q2-105 were cold all pass. On the current stack (JOIN + T1 + A1 + A2 + D3), **run 14 would
  still fail ruling 4's zero-wrong-commit conjunct** — so queueing it buys a $40 FAIL.
- **The mechanism now has a name** (r09d's reading): on the rows that matter the gold's
  carrier is *terse* — a table row, a bare line — and the competitor's carrier is
  *discursive*. Anything that scores documents by how much question-vocabulary they contain
  will damp the terse carrier, which on this corpus is disproportionately the gold. That
  kills a whole family of decide-side levers, not just this one.

## Options

**A — revert the anchor, keep D3 on the branch, park until 2026-09-01 (recommended).** The
tree becomes exactly JOIN + T1 + A1 + A2 + D3. Nothing merges to master without a gate run.
When spend returns: warm the cold rows first (S1'' never got its data — 3 of 4 known-wrong
rows were cold), then decide about run 14 on evidence rather than on a coin-flip readable set.

**B — revert the anchor and merge D3 to master now.** D3 is measured and clean, and master is
blocked from deploying anyway. Breaks the practice that decision-path changes ride a run.

**C — park the whole branch untouched**, anchor included, as a record.

## What to aim at when spend returns

**1 — the extract-side entity field** (option B of the r09c conferral, deferred then). Carry
the qualifier on the observation *from the extractor* — the row label, the field name, the
subject the value belongs to — instead of inferring it from question-vocabulary overlap. It
is the one lever the terse-vs-discursive finding does **not** kill, because it reads what the
value IS, not how much text surrounds it. Cost: payload grows (the named unservable-fixture
class), the field needs its own grounding rule, and it is a bigger build than anything in
r09b–r09d.

**2 — nothing new; re-price run 14** once the cold rows are warm, and let the gate say
whether the standing stack is worth deploying at all.

## Recommendation

**A, then aim 1.** Park with a clean tree, warm the cold rows the moment access returns, and
pre-register the extract-side entity field as the next checkpoint — it is the only candidate
left that the r09d finding does not pre-emptively refute.

## Questions

1. **The branch:** A (revert the anchor, keep D3, park), B (revert and merge D3 now), or C
   (park untouched)?
2. **The next aim:** 1 (pre-register the extract-side entity field), 2 (warm and re-price run
   14 first, decide after), or both in that order?
