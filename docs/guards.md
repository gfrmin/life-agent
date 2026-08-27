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
row below to reach *resolved*. Its **first** test step is a deliberately failing positive
control the job requires to go red, so a green from it comes from a harness that has just
proved it can speak.

Every *resolved* row below names the mutation that was demonstrated to kill it; the
transcripts are in `unification/reports/r23-k1-g4-adversary.md`.

| # | Guard | What it claims | State | Killed by |
|---|---|---|---|---|
| 0 | Harness positive control (`tests/poison/harness_control.py` + CI) | the test runner can report a failure at all | **resolved** | it IS the seed; the job fails if it passes |
| 1 | The recorded producer name is pinned (`tests/poison/test_oracle_poison.py`) | the amounts projection matches the name the catalogue actually holds | **resolved** | renaming `ExtractAmountsProducer.name` |
| 2 | K1 deletion re-listing (`test_k1_family_deletion.py`) | no deleted aggregate-family *name* resolves in the tree | **instrumented** | reintroducing `AGGREGATE_ACTION_ORDER` kills it — but it is a NAME census and cannot see the same mechanism renamed (F2). Row 2b is what covers that. |
| 2b | Dispatch question-consumers (`tests/poison/test_dispatch_poison.py`) | only a declared set of calls may consume the question on the dispatch path | **resolved** | adding `pipeline_verdict(question)` and gating the typed path on it |
| 2c | The bridge endpoint set | no undeclared endpoint serves | **resolved** | adding `POST /pipeline` |
| 3 | The priced offer set, frozen whole | the daemon ranks the same acts at the same prices | **resolved** | setting every menu row's `cost` to `0.0` |
| 4 | The §6 register re-listing (`test_m7_register.py`) + the no-vacuous-needle rule | every §6 entry pins a specific clause of a live artefact | **resolved** | restoring an existence-only (`""`) needle |
| 5 | The replay oracle (`scripts/collapse_replay.py`, `m5-base`) | a host change does not move a recorded decision | **instrumented** | its *comparator* and its *non-zero exit* are now both controlled (row 5b), but its **coverage** is not: r06 measured three of four decision-path changes as invisible to it by construction, and the adversary got 314/314 with two live decision-path defects in the tree |
| 5b | The oracle's own control (`tests/poison/test_oracle_poison.py`) | the comparator finds a planted mismatch, and `main` can exit non-zero | **resolved** | making `main` `return 0` unconditionally |
| 6 | The one-recorder census (`test_m5_absorption.py`) | only the declared family leaves write through the recorder | **resolved** | a bare `from ...recorder import record_local` (a third spelling) |
| 7 | The price-table pin (`test_pricing_table.py`) | every priced constant that ranks an action has one home | **instrumented** | — not attacked |
| 8 | The gate tree pin (`test_gate_tree_pin.py`, §6.10) | a gate run pins its tree, not just its recipe | **instrumented** | — not attacked |
| 9 | The §3.3 declaration stamps (`test_m6_declaration.py`) | each observation-model clause has one declaration with one home | **instrumented** | — not attacked |
| 10 | Action/family partition invariants (`test_decide.py`, `test_decisions.py`) | the action vocabulary is one closed set | **instrumented** | — not attacked |
| 11 | The act-committing seam census (`test_seam.py`) | one function commits acts | **resolved** | a file named `seam.py` elsewhere under `src/life_agent`, calling `.optimise(` |
| 12 | The instrument's own integrity (`test_collapse_record.py`) | the replay recorder does not lie about what it recorded | **instrumented** | — not attacked |
| 13 | PII guard — NUL refusal, per-path skips, seven added shapes, src-scoped owner literals | no corpus PII reaches the public tree | **resolved** (four ways) | a NUL byte; a lockfile basename at an arbitrary path; each of seven shapes removed individually; the src-scoped rule removed |
| 14 | Fresh-clone smoke (`smoke-fresh-clone.sh`) | a stranger can clone and get cited retrieval with no API key | **instrumented** | — not attacked |
| 15 | `ruff` / `mypy` | lint and types | **instrumented** | a linter is not a compiler and neither is a test |
| 16 | The adoption gate's frozen conjuncts (`core/gate.py`) | δ and level are frozen blind before a run reads | **instrumented** | — not attacked; nothing mechanically prevents a conjunct being restated after a read |
| 18 | No guard proves a call with a substring (`tests/poison/test_guard_shape_poison.py`) | the F10 class, not just its one instance | **resolved** | reintroducing `assert "leader_order(" in inspect.getsource(LK)` |
| 19 | Every poison fixture names its mutation | a fixture nobody has watched fail is decoration | **resolved** | adding a poison fixture whose docstring names no kill |
| 17 | D-5: the withhold reason is one derivation (`test_m5_absorption.py`) | the render's wording is the one the derivation selects | **resolved** | re-spelling the chain to disagree while keeping the token in a comment |

**Thirteen rows resolved, nine instrumented.** The register opened at four and twelve, and
three of those four were then defeated — so the honest reading is that this is the first
time any of these numbers has been earned rather than assumed.

## Known and uncovered

Written in English on purpose. There is no coverage metric for an attack surface — the
denominator is the set of violations someone thought of, and that set is not enumerable.
Folding these into a count would make the count look better and the tree no safer.

1. **A personal-name segment under an allowlisted path root cannot be caught by a shape.**
   `_path_allowed` exempts every segment beneath an allowed root. A shape rule for personal
   segments was written, tried, and **withdrawn**: a personal name and an ordinary
   kebab-case slug are structurally identical (`chan-tai-man` vs `life-agent`), and it fired
   on 20 legitimate paths in this tree. Names are the private denylist's job — which means:
2. **The CI leg runs with an empty name layer.** `--shapes-only` sets `denylist = []`, so
   the private-name half does not run in CI at all. It now *says so* on every invocation
   instead of printing a bare pass, but saying so is not catching. A clean CI PII result is
   a clean result **for shapes only**.
3. **The local PII hooks are bypassable.** `git commit --no-verify` and `git push
   --no-verify` walk past pre-commit and pre-push. The CI leg is the real floor.
4. **The replay oracle's coverage is unmeasured.** Its comparator and its exit path are now
   controlled, but nothing measures which decision-path branch sites any fixture reaches.
   r06 measured three of four decision-path changes as invisible to it by construction, and
   the G4 adversary obtained **314/314 pure equality with two live decision-path defects in
   the tree**. A pure-equality replay is not evidence that the decision path is unchanged.
5. **Six of the adversary's findings were arguable, not reproduced, and are NOT converted**
   (r23 P7 — an argument is not evidence and does not earn a fixture): the offer-set pin's
   second assertion is an identity against its own source; `test_only_the_seam_posts_decide`
   matches a literal `/decide` and any computed URL evades it; the K1 name census walks only
   `*.py` under `src`/`scripts`/`tests`, so `bin/`, `config/`, `packaging/` and a root-level
   `conftest.py` are outside its universe; the census regex misses dynamically constructed
   names; the `PII-OK` marker is a per-line kill switch with no review trail and no cap; and
   the frozen-conjunct row is self-describing.
6. **Six register rows were never attacked** (7, 8, 9, 10, 12, 14). Their *instrumented*
   state reflects the adversary's budget, not their strength — and not their weakness.
7. **F10 was a class, and eight further instances were found after r23 shipped.** The
   adversary named two siblings; a census found nine `assert "<name>(" in
   inspect.getsource(...)` assertions in total. All are converted to AST call resolution
   (`tests/_guard_ast.py`) and rows 18/19 stop new ones appearing. The general lesson —
   **a finding is a class until proven a singleton** — is why r23's own disclosures were
   re-read for consequences rather than left as prose.
8. **One fixture per guard is not a fraction of anything.** Each resolved row proves the
   guard has the one tooth its seed was shaped for; every other behaviour of that guard is
   weakenable exactly as before.
9. **The gate's universe is smaller than the population it stands for.** The adoption gate
   reads **104 authored questions**; the live surfaces have asked **186 distinct** ones
   (`ask`/`jarvis`) plus **91** through `answer-brain`, with the overlap unmeasured. Owner
   ruling 2026-08-27: record it here *and* widen the corpus from real asks.
10. **Two wrong-commit rows ride in production**, priced and published (runs 13–18).
   Disclosed, not guarded.

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
