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
| 0 | Harness positive control (`tests/poison/harness_control.py` + CI) | the test runner can report a REAL failure — exit 1 AND the named test id in the report | **resolved** | K2-6 defeated the previous form: exit 4 (missing file) and 5 (nothing collected) both read as "went red", so the control could be deleted and CI still recorded it spoke. Now all three codes are distinguished |
| 1 | The recorded producer name is pinned (`tests/poison/test_oracle_poison.py`) | the amounts projection matches the name the catalogue actually holds | **resolved** | renaming `ExtractAmountsProducer.name` |
| 2 | K1 deletion re-listing (`test_k1_family_deletion.py`) | no deleted aggregate-family *name* resolves in the tree | **instrumented** | reintroducing `AGGREGATE_ACTION_ORDER` kills it — but it is a NAME census and cannot see the same mechanism renamed (F2). Row 2b is what covers that. |
| 2b | Dispatch question-consumers (`tests/poison/test_dispatch_poison.py`) | only a declared set of calls may consume the question on the dispatch path | **resolved** | adding `pipeline_verdict(question)` and gating the typed path on it |
| 2c | The bridge endpoint set | no undeclared endpoint serves | **resolved** | adding `POST /pipeline` |
| 3 | The priced offer set, frozen whole | the daemon ranks the same acts at the same prices | **resolved** | setting every menu row's `cost` to `0.0` |
| 4 | The §6 register re-listing (`test_m7_register.py`) + the no-vacuous-needle rule | every §6 entry pins a specific clause of a live artefact | **resolved** | restoring an existence-only (`""`) needle |
| 5 | The replay oracle (`scripts/collapse_replay.py`, `m5-base`) | a host change does not move a recorded decision | **instrumented** | its *comparator* and its *non-zero exit* are now both controlled (row 5b), but its **coverage** is not: r06 measured three of four decision-path changes as invisible to it by construction, and the adversary got 314/314 with two live decision-path defects in the tree |
| 5b | The oracle's own control (`tests/poison/test_oracle_poison.py`) | a planted mismatch in a real fixture set reaches `main`'s EXIT CODE — comparator, loop and exit driven end to end | **resolved** | K3 D-a: the two previous controls drove the comparator in isolation and `main` at a *missing directory* (three checks before the compare loop), so `diffs = []` inside the loop left both green and printed `314/314`. Now killed by each of `diffs = []`, `if diffs:` → `pass`, and `bad = len(errored)` |
| 6 | The one-recorder census (`test_m5_absorption.py`) | only the declared family leaves write through the recorder | **resolved** | a bare `from ...recorder import record_local` (a third spelling) |
| 7 | The price-table pin (`test_pricing_table.py`) | every priced constant that ranks an action has one home | **instrumented** | — not attacked |
| 8 | The gate tree pin (`test_gate_tree_pin.py`, §6.10) | a gate run pins its tree, not just its recipe | **instrumented** | — not attacked |
| 9 | The §3.3 declaration stamps (`test_m6_declaration.py`) | each observation-model clause has one declaration with one home | **instrumented** | — not attacked |
| 10 | Action/family partition invariants (`test_decide.py`, `test_decisions.py`) | the action vocabulary is one closed set | **instrumented** | — not attacked |
| 11 | The act-committing seam census (`test_seam.py`) | one function commits acts | **resolved** | a file named `seam.py` elsewhere under `src/life_agent`, calling `.optimise(` |
| 12 | The instrument's own integrity (`test_collapse_record.py`) | the replay recorder does not lie about what it recorded | **instrumented** | — not attacked |
| 13 | PII guard — NUL refusal, per-path skips, seven added shapes, owner literals, tree-wide host shapes, and a marker that exempts shapes ONLY | no corpus PII reaches the public tree | **resolved** (six ways) | a NUL byte; a lockfile basename at an arbitrary path; each of seven shapes removed individually; the src-scoped ID rule removed; K3 S2: re-scoping the host shape back to `src/` (25 occurrences of two owner host names had accumulated across reports, conferrals, a design doc and a poison fixture with the hook armed, because nothing looked outside `src/`); K3 D-d: restoring the marker's unconditional `continue`, which made `PII-OK` an unreviewed kill switch over the *private name* layer too — a synthetic value has a real shape by design and can never contain a real name |
| 14 | Fresh-clone smoke (`smoke-fresh-clone.sh`) | a stranger can clone and get cited retrieval with no API key | **instrumented** | — not attacked |
| 15 | `ruff` / `mypy` | lint and types | **instrumented** | a linter is not a compiler and neither is a test |
| 16 | The adoption gate's frozen conjuncts (`core/gate.py`) | δ and level are frozen blind before a run reads | **instrumented** | — not attacked; nothing mechanically prevents a conjunct being restated after a read |
| 18 | No guard proves a call with a substring (`tests/poison/test_guard_shape_poison.py`) | the F10 class, not just its one instance | **resolved** | reintroducing `assert "leader_order(" in inspect.getsource(LK)` |
| 19 | Every poison fixture names its mutation, in its OWN docstring | a fixture nobody has watched fail is decoration | **resolved** | K2-8 defeated the previous form (it concatenated the MODULE docstring). The rule is now a pure function over synthetic source, so restoring the concatenation is itself killable |
| 20 | `_SKIP_PATHS` is pinned whole and every skip announced | a skip exempts a whole tracked file from every rule | **resolved** | K2-16: adding `README.md` to the set exempted the front page with the gate green |
| 21 | The upstream discard stages join (`tests/poison/test_upstream_join_poison.py`) | no grounded observation leaves the composition silently | **resolved** | narrowing the within-doc key; dropping the fold's alternative reading; dropping the excluded-row note |
| 17 | D-5: the withhold reason is one derivation (`test_m5_absorption.py`) | the render's wording is the one the derivation selects | **resolved** | re-spelling the chain to disagree while keeping the token in a comment |
| 22 | No census takes a whole MODULE as its universe (`tests/poison/test_census_universe_poison.py`) | a guard's universe is the code path that runs, not the file it lives in | **resolved** | K3 D-c, demonstrated not argued: with the bridge handler re-spelled to a divergent `sorted(...)` and the call moved to a never-called helper, `G.calls(BR, "leader_order")` still returned `True`. The rule is a pure function over synthetic source; killed by restricting it to ALL-CAPS aliases, which makes its universe a naming convention rather than the argument |
| 23 | Every control DISCRIMINATES (`tests/poison/test_census_universe_poison.py`) | a control tells a gate that rejected the violation from one that rejects everything, or was never reached | **resolved** | K3 D-b: `assert r.returncode is not None` is true of every subprocess that completed, so the leg it "controlled" could be deleted outright with the control green. Killed by restoring that shape as a test's sole assertion; the rule itself is killed by either discarded widening (bare truthiness, or `is None`) |
| 24 | The tree runs on any box (`tests/poison/test_portability_poison.py`) | every wrapper resolves THIS repo from an empty HOME; no unit names one machine's filesystem | **resolved** | K3 C8. Wrappers: symlinked into a scratch dir and run with a sandbox HOME, killed by re-spelling any root line as `$HOME/git/life-agent`. Units: killed by a hard-coded box path, by an ExecStart naming a renamed wrapper, and by a unit that stops declaring a repo ExecStart at all. The rule is killed by a home-prefix grep and by dropping its directive scoping |
| 25 | The production readout reports its own window and staleness (`scripts/production_readout.py`) | a standing watch that stopped running is visible IN the readout | **instrumented** | the readout now says STALE, but **nothing reads the readout** — see known-and-uncovered 7. A planted stale stream produces the word; no job fails on it |

<!-- COUNT: recomputed by tests/test_guard_register.py — edit the rows, not this line. -->
**18 rows resolved, 11 instrumented.** The register opened at four and twelve, and three of
those four were then defeated — so the honest reading is that this is the first time any of
these numbers has been earned rather than assumed.

This sentence used to be maintained by hand, and it had drifted twice: it read *"thirteen
resolved, nine instrumented"* while the rows below said fifteen and ten, and the report that
last touched it said sixteen and nine. Three numbers, one register. A count derived from
somewhere other than the thing counted is this register's own entry 1, so K3 made the count
a guard: `tests/test_guard_register.py` recomputes it from the rows and fails on the
sentence.

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

11. **The units' half of the portability check is a spelling census, and says so.** The
   wrappers are driven end to end against a sandbox `HOME` (row 24), but `systemd` is the
   deployed reader of a unit file and cannot be invoked offline against a fake home, so
   nothing here expands `%h` the way the deployed reader would. The unit rule reads the
   file; only the wrapper half reads behaviour.
12. **Nothing reads the production readout.** Row 25 makes a stopped watch visible *in* the
   readout — a covered window, a newest-row age, the word STALE — but no job asserts on any
   of it. A stale readout is visible to whoever opens the file, which is the same failure
   mode one layer up. Making a watch's silence loud is a different milestone from making it
   fail a build.
13. **Two of the three `leader_order` sites are call-pinned, not behaviourally driven.** K3
   scoped all three from whole-module censuses to the named deployed function (row 22), and
   the declaration's own ordering is asserted on values. But only the bridge site was shown
   to diverge under a planted re-spelling; `lookup.decide_and_record` and
   `executor.render_view` are pinned by a *scoped call census*, which proves the call is on
   the deployed function's body and not that the emitted order matches. A behavioural driver
   for those two is not written.
14. **No record carries a deployment origin.** `run_id` is the same literal for all live
   traffic on every box, and a decision row has no decision id, so two deployments'
   calibration streams are indistinguishable in kind as well as unmergeable in principle.
   The readout unions roots and reports each root's row count (row 25), which is the honest
   read-side half; the record-format half is out of K3's scope by construction — it moves
   the replay fixtures, and C11 froze those at pure equality.

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
