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

## AMENDMENT — before implementation, before any evidence

Made while reading the code to implement the frozen rule, with **no sweep run and no result
seen**. It narrows the rule; it does not widen it.

The rule says "BOTH mint sites". Only one of them has a carrier. The base channel mints one
observation **per chunk** (`lookup.observe_hits` — the single seam the base, `/extract` and the
dormant confirm probe all share), so `carrier(o)` is well defined there. The corroborate probe
does not: it mints through a **joint** read over all the hits' snippets at once and returns a
single observation mapped to a candidate index. There is no chunk that observation came from.

Defining one would mean inventing a rule at implementation time — exactly what the discipline
forbids — and the two available inventions are both bad: the union of all hits keys everything
(a no-op dressed as a rule), and "the chunk containing the value" is a new carrier definition
with its own failure modes.

**So E1 lands at `observe_hits` and is structurally inapplicable to the joint mint.** The
consequence is stated before the sweep: on the target row the competitor's extra observations
arrive from probe firings, and those are exactly the ones E1 cannot touch. **Prediction 1 is
therefore weaker than the census implied** — the base-side drop may not be enough to move the
commit, and if the row stays wrong with its base competitors dropped, that is a real result
about where the harm lives, not a failure to implement the rule.

## Reading

*(appended after the sweep; nothing above this line changes.)*

*(Read 2026-08-25, $0, in two steps whose order is disclosed. Step 1: `replay_audit.py` over
run 13's record on the parked tree + E1 (staging isolated, the spend-seam table sealed;
68/104 readable, 36 excluded cold). Step 2: a channel-harm census through the DEPLOYED rule —
a recorder wrapped the deployed `entity_key_filter` and the deployed `observe_hits` was driven
over all 104 questions on the warm staging cache. Step 1 was diffed first and showed the
repair; step 2 then flipped conjunct 1. Both are published. The sweep scorer prints r09d's
frozen labels; they are not criteria here and were read only as row lookups.)*

**VERDICT: conjunct 2 PASSES, conjunct 1 FAILS — E1 does NOT ship.** The frozen consequence
is enacted: E1 is reverted from the parked tree (history intact, this file stays), and the
tree of record returns to the pre-E1 head.

**Conjunct 2 — the repair is real, and it is the only thing E1 does at the decision layer.**
Against the r09e sweep (the same tree minus E1, same record, same staging recipe) the 66
common rows differ on **exactly one**: the entity-qualifier row. Every other common row is
byte-identical — action, leader, n_obs, credences, EU, trace. On the tree of record that row
still commits wrong (base 3 observations, two corroborate firings lift the wrong leader to
n_obs 5, report at 0.939). Under E1 the two non-keying observations drop at the base seam
(base 3 → 1, exactly the census's channel read), the corroborate firings then have nothing to
lift (three S1 joins add zero), the deliberate edge fires and adds a second observation, and
the commit is the gold at n_obs 2, credence 0.917 — **wrong → correct**, E1-attributable by
construction.

**Conjunct 1 — one channel harm, found only by reading the deployed rule.** The motivating
census necessarily re-implemented the rule (it ran before the implementation existed; its
docstring says so) — including the carrier mapping, where it resolved each observation's
chunk as the FIRST retrieval hit sharing its artifact cache key. The deployed implementation
plumbs the actual mint chunk positionally. Driven end-to-end over the same 104-question base
surface the bar was priced on, the deployed rule fires on **6** questions (census: 3) and
drops a gold observation on **one** — and the drop is an inversion: the question asks for a
coverage percentage for a named month in a named table; the gold's carrier is a *terse* reply
chunk that states the corrected percentage without restating the table-name identifier, while
the kept non-gold's carrier is a *discursive* chunk that restates both identifiers. The filter
leaves the base channel holding only the competitor. The census had read that row as
both-keyed/no-op — its first-hit-by-cache-key mapping assigned the gold a keying carrier it
does not have. Fourth instance this arc of the census-reimplementation class, and the first
that flips a verdict at a frozen bar.

**Why the sweep could not see it.** All three rows where the deployed rule diverges from the
census (the harm row and two clean firings) are cold-mid-loop on the sweep — readable at the
base seam, unreadable at the decision layer. The five predictions were decision-layer
statements and all five pass; the bar's first conjunct was channel-layer, and the layer gap
the pre-registration named is exactly where the harm sat.

**The mechanism is the arc's standing finding, now extended.** r09d established that levers
scoring carriers by question-vocabulary overlap damp the terse gold. E1 was exact and typed
and a hard filter — different on both axes that mattered there — and fails the same way: a
terse carrier omits qualifiers, so **any carrier-side requirement, fuzzy or exact, soft or
hard, damps terse golds**. The repair on the entity-qualifier row and the inversion on the
harm row are the same mechanism pointing in opposite directions. This closes the family, not
one lever.

**Predictions, scored:** 1 ✓ on the strong branch (correct, not merely withheld; the
amendment's stated weakening did not bite — the base-side drop alone moved the commit, so on
this row the harm lived at base, not in the probe mints). 2 ✓ with its mechanism (the
corroborate-tier row is byte-identical; both its carriers key). 3 ✓ (zero correct → wrong at
the decision layer). 4 ✓ (marginal decision-level collateral zero; the standing stack's own
two correct→withheld rows are byte-identical under E1). 5 ✓ and stronger than predicted
(every common row except the target is byte-identical, not just the identifier-free 62).
Five of five predictions pass and the lever still does not ship — the predictions were all at
the layer the sweep can see.

**The hard clause and the coldness clause.** No named class is made worse: corroborate-tier
byte-identical, warm-deliberate byte-identical (withheld on both trees), superset-confirm
cold on both passes and provably untouched (its question carries no identifier — a no-op by
construction), entity-qualifier repaired-then-reverted with the lever. The target row was
readable, so the coldness clause never triggered. Neither clause changes the verdict; the bar
does.

**The two newly readable rows, attributed honestly.** This pass reads 68 rows to r09e's 66;
both new ones are census repair-candidate rows, newly readable because the §18.9 warm-through
keeps growing the store pass over pass — not because of E1 — and absent from the marginal
read by construction. One serves the record's grade unchanged; the other converts the
record's withhold into a correct report (the filter drops five non-keying competitors at
base; the deliberate edge adds a second observation). Consistent with E1's mechanism, not
attributable on this evidence, and a withhold→answer conversion licenses nothing under the
frozen text.

**What the reading leaves.** (1) The entity-qualifier row returns to committing wrong on the
tree of record — r09e's read stands: two known-wrong rows commit wrong there, one is cold.
(2) Ruling 2 (the extract-side entity field stays retired) is *unaffected* by the census
defect: on the harm row the gold's chunk genuinely lacks the qualifier, so no extract-side
field could find it there — the retirement's premise fails only where the field would fail
too. (3) The deployed-rule harm census (`harm-census.json`, instrument in the KB window
directory) supersedes the motivating census for any future read of this family.

