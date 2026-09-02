# r46 leg A — the readable surface: PRE-REGISTRATION

Opened by `r45-evidence-path`'s third correction to membrane-shadow §18, which registered
the precondition this leg discharges:

> **Which surface a §18 bar reads, and what that surface's distribution actually is, are
> now preconditions for reading it** — registered here rather than discovered mid-run.

**Committed before any `src/` change** (`M-3`). `M-2` licenses the ordering: a $0 reading
that is a precondition for a class opens before the lever for that class.

## Disclosure — the motivating census, taken BEFORE any criterion below was written

Everything in this section was measured first and is stated so it cannot be tuned to. It
was read from the deployed writers in `src/` and from `git show` of the deleted one, never
inferred from field names (`M-7`).

1. **The raw affordance is a constant over the entire stream.** All **6 628** rows carrying
   an `action` — every `decide` (3 765), `gate` (296), `enact` (555) and `cat` (2 012) row
   in the shadow ledger — record `gather`. Across both engine arms, all four row kinds, and
   the whole life of the stream. r45 measured this on 250 replayed rows and on 4 live
   decides; it holds on the census.
2. **`real_effector` names two different quantities depending on `kind`, and the field name
   discloses neither.** On `decide` it is `dec.get("effector")` — what the *deployed daemon*
   did. On `gate` it is the literal `"abstain"`. On `cat` it is the decide item's value,
   again the daemon's. On `enact` — written by the lane deleted at M5 — it is
   `mapped.get("effector")`, the **engine's mapped act**, with the daemon's carried
   separately as `daemon_effector`. An instrument that reads `real_effector` across kinds
   silently compares the engine against itself on 555 rows and the daemon against itself on
   the other 6 073.
3. **The mapped surface has had no writer since M5.** `coarse.map_action` has **zero call
   sites in `src/`** — only `tests/test_membrane_coarse.py` and `tests/test_m5_absorption.py`
   reference it. `2d9c356` added the `enact` writer; `4e5debd` (M5 P-I) removed it. So all
   555 `enact` rows are pre-M5, arm A, on the 2 393-model world, and **nothing on the
   current tree can write another one.**
4. **Historically that surface did vary** — the 555 rows carry four distinct mapped
   effectors (`gather` 417, `abstain` 135, `ask_clarify` 2, `report` 1) against a daemon
   distribution of `gather` 336 / `report` 85 / `abstain` 134, with `degraded` reading
   `gather_exhausted` on 138 and `None` on 417. **This is the hedge that matters: it is
   old-era, arm-A, pre-M5 evidence about a writer that no longer exists.** It is a reason
   to expect variation, not a measurement of today's.

**So r45's precondition is not merely unsatisfied — it is unsatisfiable as instrumented.**
The one surface that could carry a §18 bar is the one nothing writes.

## The one job

**Restore a writer for the mapped surface, prove it changes nothing, and publish what that
surface's distribution actually is.** No §18 bar is read in this leg.

## The instrument — an observation-only tap, additive by construction

The r37 pattern, one level in: the shadow worker's `_tick_decide` calls the **deployed**
`coarse.map_action` with the deployed payload and daemon view, and records the result as
new keys on the decide row it already writes.

- **The deployed rule is imported, never re-implemented** (`M-7`). `_DecideItem` carries the
  `payload` and `dec` objects it was submitted with; the tap passes them, the engine's own
  `choice.action` and `choice.readouts`, straight into `map_action`.
- **The agreement branch is read from the rule's own behaviour, not re-derived.**
  `map_action` returns the *identical* `dec` object on agreement and a fresh dict on every
  other branch, so `mapped is dec` **is** the agreement predicate. A test pins that identity
  as a declared contract rather than an accident.
- **Four new keys, on `kind: "decide"` only**: `mapped_effector`, `mapped_degraded`,
  `mapped_echo`, `mapped_probe`. No existing key changes meaning or value. Nothing is
  written to `calibration/`; this is a diagnostic stream, **recorded and never folded**
  (`M-14`).
- **Fail-open.** `map_action` asserts on an undeclared action and can raise on a malformed
  view. Any raise is caught, counted in `stats()`, and the decide row is still written
  without the mapped keys — never a dead form, never a dropped row (the `_tick_cat`
  precedent).
- **The decision path is untouched, on or off.** `submit_decide` is already enqueue-only and
  off the decision path; the tap runs in the worker thread behind it.

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **S1** | **Additive.** Every pre-existing key on every row kind is byte-identical with and without the tap — `action`, `real_effector`, `readouts`, `summary`, `t`, `raw_internal`, `form`, `question_id`, `kind`, `latency_ms` excepted as timing. Only the four new keys appear, and only on `decide`. | **KILL** |
| **S2** | **Off the decision path.** The deployed answers are byte-identical with and without the tap: the m5-base replay reads its standing **288/314 with the same 26 named artefacts**. | **KILL** |
| **S3** | **Fail-open.** An injected raise inside `map_action` is caught, counted, and leaves the form alive and the decide row written. Verified by injection, not by inspection. | **KILL** |
| **S4** | **The read is reported with its size**, and this leg FAILS if the tap wrote zero rows (`G-3`'s universe clause). The population is named, and any bound on it is published, not implied. | **KILL** |
| **S5** | Every predicate load-bearing on S1–S4 is verified **RED by mutation** before the read, and each mutation varies **the dimension its claim is about** (`M-25`) — an S1 mutation must alter a pre-existing key, not merely a new one. | **KILL** |
| **S6** | **The echo fraction is published.** For each row the tap must state whether the engine contributed anything (`mapped_echo`). A surface that varies only because it passes the daemon's own effector through is a surface that carries no engine signal, and the two are indistinguishable in the aggregate distribution alone. | **KILL** |

## Consequence — frozen before the read, three branches and one sub-branch

- **Branch A — the mapped surface varies AND carries engine signal** (≥2 distinct
  `mapped_effector` values over the read population, and `mapped_echo` false on ≥1 row where
  the mapped effector differs from the daemon's). The §18 precondition is **satisfiable on
  the mapped surface**; the surface a §18 bar reads is declared to be that one, and the
  ladder proceeds to the bar with the distribution published beside it.
- **Branch A′ — the surface varies but is (near-)all echo** (`mapped_echo` true on every row
  where the mapped and daemon effectors differ, or the echo fraction ≥ 0.95). The surface
  varies *because the daemon varies*. It is **not** a satisfied precondition: a bar reading
  it would compare the deployed policy against itself on the rows that move. Publish, and
  the ladder's next rung becomes the instrument question, not the bar.
- **Branch B — the mapped surface is a constant.** The precondition is **not satisfiable
  from the shadow as instrumented**. Publish; read no bar; the next rung is "what instrument
  could carry a bar", stated as such.
- **Branch C — the tap cannot be made inert** (any of S1/S2/S3 fails). **Revert the tap**,
  publish the reason, and the mapped surface stays unreadable. No §18 bar is read.

In every branch, **no §18 bar is read in this leg** and no lever ships. `M-1` is not engaged
because nothing here can reach a commit decision.

## Registered expectation

**Branch A.** The structural reason is that `action` is pinned at `gather`, so the agreement
branch fires exactly when the daemon itself gathered — and the daemon's effector varies
(old-era decide rows: `gather` 2 711 / `abstain` 837 / `report` 213). On the ~24% of rows
where the daemon did not gather, `_gather` must either select an unapplied VOI probe or
degrade, and neither is an echo.

**What would make that wrong, stated now:** the echo fraction is the live risk (Branch A′),
and it is not predictable from the old-era rows, because the deleted writer never recorded
which branch fired — `real_effector: "gather", degraded: None` covers *both* an agreement
pass-through and a probe selection, indistinguishably. **That ambiguity in the historical
record is precisely why `mapped_echo` is a frozen criterion and not a nice-to-have.**

## Population and bound — declared before the read

The tap accrues from live traffic, which is thin (4 decides in the new era). The reading's
population is therefore the **m5-base replay through the bridge with the shadow live** — the
pinned corpus, driving real payloads and daemon views through `submit_decide` at $0.

Fold depth makes this slow, not expensive: `GD-17` measured ~20 s wall per mirrored decide
at depth 250 plus a ~19.5 min boot fold. **Frozen budget: a 4-hour wall-clock cap.** If the
cap binds, the read is a declared prefix of the corpus in its natural order, its size is
published as a bound under S4, and the leg reports a *subsample*, never a census. Choosing
the prefix after seeing the distribution is forbidden.

## What this leg does NOT do

It does not read a §18 bar; it does not touch the world declaration, the theta grid, or the
categorical twin; it does not re-open the M3 live lane — `map_action`'s output is **recorded
and never enacted**, and the deleted enactment stays deleted. The other three r46 items
(act-conditioning as r45 reframes it, `GD-15`'s grid precision with its number, the
categorical twin) keep their own pre-registrations (`M-3`; bundling two levers on one
reading is the r30b mistake).

## Cost

**$0.** No priced run. Wall-clock only, capped above.
