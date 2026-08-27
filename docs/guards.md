# The guard register

> Opened at K1 (r22), 2026-08-27. Append-only in spirit: a state may change, but a
> retired guard keeps its row with the reason.

A guard is a check whose job is to catch a violation. Ordinary behaviour tests are not
guards and are out of scope here — this register covers the checks that stand between a
mistake and a green build.

## The ladder

| state | meaning |
|---|---|
| **unenforced** | no guard names this property at all |
| **instrumented** | a guard names it, but no planted violation has ever been shown to kill it |
| **resolved** | a planted violation has been *demonstrated* to fail the guard, for the intended reason, with the transcript recorded — and the guard runs in an un-bypassable job |

**A gate that has never killed a planted defect is decoration.** Reading a check tells you
what it does on the input you imagine while reading it, and nothing about the inputs you do
not imagine — which is the whole population it exists to cover. The only evidence that a
guard still works is a violation someone planted, watching it die.

Almost all guard code anywhere is *instrumented* and gets called done. This register exists
so that the difference between "has a checker" and "is checked" stays visible.

## The register

CI (`.github/workflows/ci.yml`) runs on every push to `master` and every PR — an
un-bypassable job on a host the builder does not control, which is the precondition for any
row below to reach *resolved*.

| # | Guard | What it claims | State | Evidence |
|---|---|---|---|---|
| 1 | `AMOUNTS_PRODUCERS` names the deployed producer (`test_aggregate.py`) | the amounts projection filters on the name pkm actually writes | **resolved** | r22: restoring the declaration-namespace tuple fails both tests with their named markers |
| 2 | K1 deletion re-listing (`test_k1_family_deletion.py`) | no deleted aggregate-family symbol resolves anywhere in `src/`, `scripts/`, `tests/` | **resolved** | r22: reintroducing `AGGREGATE_ACTION_ORDER` fails naming the symbol and the file |
| 3 | The offer-set pin (`test_k1_family_deletion.py`) | the daemon's ranked act set is unchanged, so no priced run is owed | **resolved** | r22: adding one menu row fails with "K1 moved the argmax and owes a priced gate run" |
| 4 | The §6 register re-listing (`test_m7_register.py`) | every §6 named exception has a live artefact pin | **resolved** | r17: a fake `6.99` entry and a mangled needle both fail |
| 5 | The replay oracle (`scripts/collapse_replay.py`, `m5-base`) | a host change does not move a recorded decision | **instrumented** | fires on real changes; **no planted decision-path defect has ever been replayed against it**, and r06 measured three of four decision-path changes as invisible to it by construction |
| 6 | The one-recorder leaf census (`test_m5_absorption.py`) | only the declared family leaves write through the recorder | **instrumented** | has now fired on a real change in both directions (a writer added at r21, removed at K1) — real changes, not planted ones |
| 7 | The price-table pin (`test_pricing_table.py`) | every priced constant that ranks an action has one home | **instrumented** | — |
| 8 | The gate tree pin (`test_gate_tree_pin.py`, §6.10) | a gate run pins its tree, not just its recipe | **instrumented** | built after run 10 fired a recipe against a drifted tree |
| 9 | The §3.3 declaration stamps (`test_m6_declaration.py`) | each observation-model clause has one declaration with one home | **instrumented** | — |
| 10 | Action/family partition invariants (`test_decide.py`, `test_decisions.py`) | the action vocabulary is one closed set and the family orders are subsets | **instrumented** | — |
| 11 | The act-committing seam census (`test_seam.py`) | one function commits acts | **instrumented** | — |
| 12 | The instrument's own integrity (`test_collapse_record.py`) | the replay recorder does not lie about what it recorded | **instrumented** | — |
| 13 | PII guard (`.githooks/pii_check.py`, pre-commit + pre-push + CI `--shapes-only`) | no corpus PII reaches the public tree | **instrumented** | the hook refuses without `LIFE_AGENT_KB`, which is fail-closed; `git commit --no-verify` walks past the local hooks, and the CI leg is shapes-only |
| 14 | Fresh-clone smoke (`scripts/smoke-fresh-clone.sh`) | a stranger can clone and get cited retrieval with no API key | **instrumented** | — |
| 15 | `ruff` / `mypy` | lint and types | **instrumented** | a linter is not a compiler and neither is a test |
| 16 | The adoption gate's frozen conjuncts (`core/gate.py`) | δ and level are frozen blind before a run reads | **instrumented** | frozen-blind by process; nothing mechanically prevents a conjunct being restated after a read |

Twelve of sixteen rows read *instrumented*. That is the honest state, and it is the number
this programme exists to move.

## Known and uncovered

These are written in English on purpose. There is no coverage metric for an attack surface
— the denominator is the set of violations someone thought of, and that set is not
enumerable. Folding these into a count would make the count look better and the tree no
safer.

1. **The gate's universe is smaller than the population it stands for.** The adoption gate
   reads **104 authored questions**. The live surfaces have already asked **186 distinct
   questions** (`ask`/`jarvis`) plus **91** more through `answer-brain`. Nothing measures
   the overlap, and no guard would notice if the corpus and the real asks diverged
   completely. This is the dominant defect class — a checker whose universe is derived from
   somewhere other than the thing being checked — sitting inside this programme's own
   instrument. Owner ruling 2026-08-27: record it here *and* widen the corpus from real
   asks, tracking the authored-vs-asked fraction as it moves.
2. **Row 5's blind spot is measured, not suspected.** r06 established that three of four
   decision-path changes in run 10's tree were invisible to the replay oracle by
   construction. A 314/314 pure-equality replay is fully compatible with a decision-path
   change the oracle cannot see.
3. **Row 13 is bypassable locally.** `git commit --no-verify` and `git push --no-verify`
   walk past the pre-commit and pre-push hooks. The CI leg runs `--shapes-only` over the
   tracked tree, so it is the real floor; the hooks are convenience, not enforcement.
4. **One fixture per guard is not a fraction of anything.** Each resolved row above proves
   the guard has the one tooth its seed was shaped for. Every other behaviour of that guard
   is weakenable exactly as before.
5. **No positive control.** Nothing in CI proves the harness can speak. A green test step is
   currently indistinguishable from a test step that ran nothing. (Planned: a deliberately
   failing planted test required to go red as the first step.)
6. **Two wrong-commit rows ride in production**, priced and published (runs 13–18). They are
   disclosed, not guarded.

## Entry 1 in full — why it is entry 1

`core/aggregate.AMOUNTS_PRODUCERS` filtered `artifacts.producer_name` on four strings from
the *declaration* namespace (`extract_amounts_<extractor>`). pkm records `producer_name` as
the producer *class's* name, and all four declarations map to one class, so the filter could
never match anything. `project_amounts` reported every hit as `underived`, permanently, and
the remedy it printed produced the very artifact the filter then missed — a closed loop.

Thirty-seven tests covered that module and all of them passed, because the fixtures inserted
the suffixed names themselves. **The test's universe was derived from the same wrong constant
as the code, so it was structurally incapable of catching this.** The guard now reads the
name off the deployed producer class instead of restating it.

The general form, worth keeping in front of anyone writing a guard here: *the checker's
universe is derived from somewhere other than the thing being checked, and the gap between
them is invisible to both.* It is close to undetectable by review, because when you read a
check you supply the universe from your own head, and your head supplies the cases the check
already handles.
