# r10 — the entity key (E1), PRE-REGISTRATION

**Status:** PRE-REGISTERED 2026-08-25, before any `src/` change. This file is committed first;
the implementation follows it in history, and the reading is appended after the sweep runs. The
bar below was frozen by the owner in ruling 3 of the entity-key conferral **before** any
evidence about whether the lever clears it.

## The hypothesis, stated so it can be wrong

On rows where the question names an entity, the gold's carrier states that entity and the
competitor's carrier does not. An **exact, typed** identifier key — not vocabulary overlap —
should therefore separate them.

This is the fourth lever aimed at the same block. The three before it were refuted, and the
r09d refutation is what shapes this one: **any rule that scores documents by question-vocabulary
overlap damps the gold on this corpus**, because the gold's carrier is terse (a table row, a
bare line) and the competitor's is discursive. E1 differs on both axes that mattered there — it
is exact rather than fuzzy, and a filter rather than a factor — so if it fails, it fails for a
different reason and that reason is worth knowing.

## The rule (frozen; it must land exactly as written here)

```
ids(question)  identifier-like tokens ONLY: CamelCase (>=2 humps), snake_case,
               filename-with-extension, ALLCAPS. Never ordinary English words.
carrier(o)     the CHUNK the observation was minted from (not the quote span).
key_hit(o)     EVERY id in ids(question) occurs verbatim in carrier(o).
filter         if any observation key_hits, DROP the ones that do not; else no-op.
sites          BOTH mint sites — the base channel and the probe-side mint. Base-only is
               provably insufficient: on the row this targets, the competitor's extra
               observations arrive from probe firings, not from the base.
```

The $0 census that motivated it read, at chunk scope over 104 questions: **3 repair
candidates, 0 channel harms, 38 no-op, and 62 questions with no identifier at all** — so the
rule is inapplicable to 60% of the corpus by construction, and the quote-scoped variant is
strictly worse (2 harms, both all-gold channels). Those numbers are channel-level. The layer
gap to commits is real; that is what this sweep is for.

## The bar (owner, ruling 3 — not renegotiable at read time)

**SHIP only if BOTH hold on the $0 sweep of run 13's record, on the tree of record:**

1. **Zero channel harms** — no question where a gold observation is dropped by the filter.
2. **At least one wrong-commit repair** — a row run 13 committed wrong becomes correct or
   withheld.

A withhold→answer conversion **does not** license shipping on its own: the block that keeps
master undeployed is a wrong-commit block, not a reach block.

**Hard clause, standing:** no lever ships while it makes a **named** wrong-commit class worse.
The named classes are the corroborate-tier row, the entity-qualifier row, the warm-deliberate
row and the superset-confirm row.

**Coldness clause, pre-declared (r09d's lesson):** the entity-qualifier row is the row this
lever targets and it is readable today. If it is **not** readable on the sweep pass, the read
is **INCONCLUSIVE** — run one further pass; if it is still not readable, **STOP and confer**.
No verdict is taken from a pass that cannot see the target row.

## Predictions (scored honestly in the reading, whichever way they fall)

1. The entity-qualifier row stops committing wrong (correct or withheld).
2. The corroborate-tier row is **unchanged** — both its carriers key, so the filter is a no-op
   there.
3. Zero rows move correct → wrong.
4. Decision-level collateral (correct → withheld) does not exceed the standing stack's own two.
5. The 62 identifier-free questions are byte-identical to the tree of record's rows.

## What a PASS licenses, stated now so it cannot inflate later

Meeting the bar licenses **keeping the lever on the tree of record**. It does **not** license
firing run 14: r09e measured two rows still committing wrong, and E1 targets one of them. Run
14 remains a separate decision, under its own frozen conjuncts, once the remaining named
classes are addressed or priced.

## Reading

*(appended after the sweep; nothing above this line changes.)*
