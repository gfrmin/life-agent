# r30b — the claim space: interval claims inside the argmax — PRE-REGISTRATION (2026-08-29)

> **This document is the pre-registration. It is committed BEFORE any `src/` change; git
> history is the proof.** r30b is move 1 of the roadmap approved 2026-08-29 (the plan file
> `session-brief-zesty-fountain.md`, "assess how close we are to our goal"): the last lever
> arc on the critical path to Stage 4, the MVP exit test.

## STATE

- master `456dd54` (r30 merged, PR #114 — the units lever ships as a documented no-op:
  `core/answer_shape.py` + `core/decide.shaped_u_bar`, six optional per-shape scales at 1.0).
- The mandate: the owner's r30/r30b split — **one decision-path lever per gate reading**
  (the run-10 isolation-ladder lesson). r30 carried steps 1–2 (units). r30b carries **step
  3 only** (the claim space); step 4 is scoped out below.
- What r30b is FOR, in one line: r29 measured that the agent abstains on **8 of 8** computed
  questions and **18 of 19** quantity questions, and r28 measured that only 4% of run 18's
  adoption margin is answers. A `quantity` question whose evidence disperses over near-agreeing
  numeric candidates has **no action in the action set that is both honest and useful** —
  the crisp report is 0-1 wrong, so the argmax correctly withholds. This checkpoint adds one.

## Scope: step 3 only — and why step 4 does not land here

The approved plan already carries this deviation for approval, and it was approved: **step 4
(the quantity-parameterised "extract k more" experiment) is OUT.** Two reasons, both standing:

1. r29's **rider 2** froze a harm term as a *precondition* on any grow-prior refit, not a
   refinement. "Extract k more" is a grow actuator; pricing it is a grow-prior question, and
   the gather-outcome stream it would refit against is still contaminated (r29's rider 1: run
   17's 292 rows at recovered-rate 0.432 vs 0.069/0.048, pooled permanently, no policy
   segmentation).
2. It would put a **second decision-path lever** on one gate reading — the exact confound the
   owner's r30/r30b split exists to prevent.

Step 4 moves to the grow-priors / hand-priced-VOI arc with the rest of that family (foundations
§14; proplang migration E3). This is disclosure, not abandonment.

## The finding that re-shapes this checkpoint (read before any `src/` edit)

The approved plan named the build site as `lookup.action_utilities` — "the one decide surface".
**There are two, and the plan named the one the gate does not read.** Verified, not recalled:

- `$LIFE_AGENT_KB/eval/gate-outside-option/run_meta-gate-20260826T083356.json` (run 18) records
  `gate.typed_arm = "executor"`. Every gate run since run 10 is on this lane, and `scripts/ask.py`
  makes it the **default live read path**; the in-process family is the down-branch.
- The executor lane's argmax is **not in this repo**. `core/executor.py`'s `_decide` posts to
  the credence answer-brain daemon (`SEAM.DaemonDecide` → `POST {daemon}/decide`), and the
  terminal action set is built in `../credence/apps/answer-brain/brain/answer_brain.jl`
  (`decision_fpa`): `report_j × K`, `hedge`, `ask_clarify`, `abstain`. No client-supplied
  terminal row exists on that wire today.
- Precedent that this asymmetry is real and already load-bearing: `report_scoped_j` exists in
  `lookup.action_utilities` and **has no daemon counterpart** — `run_eval._typed_response_executor`
  says so in its own docstring ("`report_scoped` never reaches here today").

**Consequence.** A lever built only in `lookup.action_utilities` would be invisible to r31 and
absent from the deployed path — it would measure nothing and change nothing for the owner.
r30b therefore lands on **both** decide surfaces, from **one** declaration in this repo.

## Design — the interval claim

### D1 · The claim and its loss

An **interval claim** `[lo, hi]` asserts that the quantity lies in that range. Its correctness
is not 0-1: it is the r21-frozen Winkler grade `x = realised_aggregate(lo, hi, g)` against the
true value `g`. Its utility row over the K+1 hypothesis atoms is `report_j`'s shape generalised:

    U(interval[lo,hi], atom j) = u_assert(x_j, Ū),  x_j = realised_aggregate(lo, hi, g_j)
    U(interval[lo,hi], atom j) = u_assert(0, Ū) = u_wrong   when candidate j is not numeric
    U(interval[lo,hi], NONE)   = u_wrong

Nothing new is invented: `u_assert` is the one atom (`core/decide.py`), `realised_aggregate` is
r21's already-frozen rule, and the row is tabular over the same atoms every other action ranks.

**A crisp `report_j` is NOT the degenerate case of this row** (a point interval still pays the
2/α miss term against a *nearby* candidate, where `report_j` pays flat `u_wrong`). The two
losses coexist and the engine picks between them. That is the lever.

### D2 · Shape gate

Interval rows exist **iff** `answer_shape.answer_space(question) == "quantity"` **and** ≥2
distinct candidate values parse numeric. Every other question's action set is byte-identical
to today's — the r30 conservative-default discipline carried forward.

### D3 · Proposal set, and its declared cap

Contiguous ranges over the sorted **distinct** numeric candidate values: `[v_(a), v_(b)]` for
every `a < b`. Degenerate ranges (`a == b`) are **excluded** — that claim is `report_j`'s, and
pricing one claim under two losses would confound r31's attribution. Count = `m(m-1)/2`.
Capped at `m ≤ 8` distinct values (28 rows), taking the 8 highest-credence values; **the cap is
logged when it binds, never silent** (the no-silent-caps discipline).

### D4 · One declaration, two lanes

`core/decide.py` — already the home of `u_assert` and `shaped_u_bar` — gains `interval_options`,
the ONE construction of the rows. Both lanes bind it:

- **terminals-only lane:** rows enter `lookup.action_utilities`, ranked by the skin's `optimise`.
- **executor/daemon lane:** rows ride a new optional `/decide` request field
  `extra_actions: [{name, values}]`; the daemon appends each as a `Tabular` row to `(order, fpa)`
  and `optimise` ranks it. **The daemon computes no utility** — Invariant 1 preserved, and the
  Winkler constant is never re-spelled in Julia (the standing lesson: *a census must read the
  deployed rule end-to-end, never re-implement the constant it prices*).

`realised_aggregate` and its two frozen constants **move to `core/decide.py`**; `core/gate.py`
binds them (a drift-gated binding, the `LK.extractor_reliability` / `NR.population_posteriors`
pattern from M3). This is forced: `gate` already imports `decide`, so `decide` cannot import
`gate`. Grading-side and decision-side become the same object.

### D5 · The response vocabulary is UNCHANGED

An interval is a `report` — the same speech act at a different precision — **not** a new action.
Wire names `interval_<a>_<b>` map back to `effector: "report"` plus the claim's `[lo, hi]`.
So `DEC.ACTIONS`, `LOOKUP_ACTION_ORDER`, `gate.ASSERT_ACTIONS`, the bridge's `_TERMINAL_ACTIONS`
and the gate's action space are all untouched, and r21's already-frozen grading branch
(`run_eval:638-650` — `action="report"` carrying the Winkler `x`) receives it with **no change**.
(`report_scoped` earned a name because it is a different act with its own loss `u_wrong_scoped`;
precision is not a different act.)

### D6 · What the record carries

- Executor `View` gains `aggregate: {"totals": [{"lo", "hi", "point"}], "claim": "interval"}`
  — the r21 shape `scripts/aggregate_eval.py` already reads — **present only when an interval
  was chosen**, so every existing view is byte-identical.
- `LookupResult` gains `interval: tuple[float, float] | None = None`; the §18.9 answer content
  gains an `"interval"` key **only when one was chosen** (a key added unconditionally would move
  every recorded artefact's bytes for nothing).
- The §18.9 **params/cache key are not extended** — the decision is always computed
  (`decide_and_record` has no cache short-circuit; verified), so no warm artefact can mask the
  lever, and extending params would cold-start every warm answer for no information.

### D7 · Render grammar (interaction contract)

`lookup.GRAMMAR` gains ONE string, `report_interval`, rendering the endpoints as the **original
candidate display strings** (never a reformatted float — no invented precision or currency) with
the claim's **coverage credence** `p = Σ_{j : lo ≤ g_j ≤ hi} w_j`. Coverage is display and record
only, never a decision input (Invariant 1: no host argmax on weights). `docs/interaction-contract.md`
gains the row in the credence-rendering table in the same commit as the string.

### D8 · Riders carried

- `scripts/aggregate_eval.py --arm` is **deleted** (it posts `/route_family` and `/aggregate`,
  endpoints K1 removed — it can only 404); `--warm` is kept, unchanged, because r31's Pop B needs
  it. Its private `_numeric` and `run_eval._numeric_gold` are **bound** to the one parser
  (`answer_shape.numeric_value`) rather than left as a second and third copy; the regex is
  transcribed verbatim, so grading is byte-identical by construction (C7 checks it).
- **§6.10 gap, disclosed and fixed here:** `run_meta.decision_path_tree` pins only life-agent
  paths, so a daemon change is invisible to a gate run's own pin. r30b records the credence
  repo's git sha in the pin (null + a stated reason when the checkout is not resolvable). Without
  it, r31 could not attribute its own reading to the tree that produced it.
- `GETTING_STARTED.md`'s "remaining items" list is stale on all three entries — corrected in this
  PR as a doc-currency edit, no new claims.

## Frozen criteria

| | Criterion |
|---|---|
| **C1** | **Width pays INSIDE the action.** No external width penalty exists; the only width sensitivity is inside `realised_aggregate`. On a fixture where a tight interval covers the leader mass, the argmax is NOT the widest proposal. RED under the mutation `x_j := 1.0 if lo <= g_j <= hi else 0.0` (0-1 containment), under which the widest proposal weakly dominates every narrower one. |
| **C2** | **No interval rows off-shape.** A question that does not classify `quantity`, or that has <2 distinct numeric candidates, produces an action set byte-identical to pre-r30b — on BOTH lanes. RED under a mutation that drops the shape gate. |
| **C3** | **One declaration, two lanes.** `lookup.action_utilities` and the `/decide` `extra_actions` payload are built from the SAME `decide.interval_options` call; the daemon supplies no utility arithmetic of its own. RED under a mutation that re-implements a row at either site. |
| **C4** | **One loss.** `gate.realised_aggregate` IS `decide.realised_aggregate` (identity, not a copy), and `_WINKLER_ALPHA`/`_WINKLER_SCALE` have one home. RED under a mutation that forks either constant. |
| **C5** | **The response vocabulary does not grow.** `DEC.ACTIONS`, `DEC.LOOKUP_ACTION_ORDER`, `gate.ASSERT_ACTIONS`/`WITHHOLD_ACTIONS` and the bridge's `_TERMINAL_ACTIONS` are unchanged; an interval decision logs and grades as `report`. RED under a mutation that adds an action name. |
| **C6** | **The interval-excludes-gold wrong-commit class is counted from birth.** Every reading in this report publishes it per class beside the totals. **Hard clause** (owner ruling): no lever ships while it makes a named wrong-commit class worse. |
| **C7** | **One numeric parser.** `answer_shape.numeric_value` is the only numeric parse on the decision path AND in `run_eval`/`aggregate_eval` grading; a table of cases asserts the bound functions agree with the pre-r30b regex exactly. RED under a mutation that diverges them. |
| **C8** | **Coverage credence is display-only.** No branch selects an action by reading `credences`/coverage. RED under a mutation that picks the interval by a host comparison. |
| **C9** | Δ under `shaped_u_bar` is not comparable to Δ under flat units; any reading publishes which utility produced it, and both when both exist (carried from r30/C9). |
| **C10** | **G2 replay = ATTRIBUTED DELTA, not pure equality.** This lever moves the argmax by design; a pre-registration promising 314/314 equality would be falsified by its own success. Every changed fixture must (i) classify `quantity` AND (ii) carry ≥2 distinct numeric candidates. A delta outside that population is a defect that blocks the checkpoint. The changed set must equal the set the off-gate sweep predicts (run-9 discipline, at $0). |
| **C11** | PII: no question text, corpus value, gold, or owner identifier enters the tree — test fixtures use synthetic quantities marked `# PII-OK: synthetic <what>`. |
| **C12** | **Merge ≠ deploy.** r30b changes the argmax, so the live deploy gates on r31's reading (the run-14 precedent). Merging this PR does not deploy it. |

## Verification plan

1. TDD, red-first, on every new behaviour; C1–C8 each demonstrated RED by its named mutation
   and restored — transcript in the RESULTS section of this document.
2. `TMPDIR=~/.cache/tmp uv run pytest -m "not llm and not system"` + `ruff check .` +
   `uv run mypy` — counts pasted, not summarised.
3. `uv run python .githooks/pii_check.py` exit 0 with the private name layer live.
4. `PYTHONHASHSEED=0 uv run python scripts/collapse_replay.py --checkpoint m5-base` —
   deltas **attributed and direction-asserted** per C10, reproduced twice against the §6.13
   commit-wobble floor (2).
5. The credence-side change carries its own Julia tests in that repo
   (`apps/answer-brain/tests/julia/`), red-first, in a branch merged by PR there.
6. **$0 throughout.** No priced run is bought by this checkpoint; r31a is the evidence pack and
   r31 is the priced reading.

## Gates

**G1** suite + ruff + mypy, both repos · **G2** `collapse_replay --checkpoint m5-base` under C10 ·
**G3** the $0 off-gate sweep (r31a) — no priced run fires until its predicted assert set is on
the record.

---

# r30b — RESULTS (2026-08-29, $0)

> Read against the criteria frozen above, committed at `84d105e` before any `src/` change.
> **Nothing is deployed by this checkpoint (C12).** No priced run was bought.

## What landed

**One declaration, two decide surfaces.** `core/decide.py` — already the home of the assert
atom `u_assert` and r30's `shaped_u_bar` — gains the `quantity` shape's loss and its claim
space: `realised_aggregate` (moved, not copied — `core/gate.py` now BINDS it), `IntervalOption`,
and `interval_options`, which builds one tabular row per interval proposal over the same K+1
atoms every other action ranks. Both surfaces bind that one construction:

- **terminals-only lane** — the rows enter `lookup.action_utilities`; `lookup.decide` maps an
  `interval_a_b` winner to `("report", eu, None, option)`.
- **executor/daemon lane** — the rows ride a new optional `/decide` field `extra_actions`
  (`[{name, act, values}]`); `executor.run_pass` maps the winner back the same way and lands the
  claim in the r21 `aggregate.totals` shape the frozen grader already reads.

**The daemon change is generic, not aggregate-specific** (credence
`apps/answer-brain`, PR alongside): body-priced terminal rows, ranked by the same `optimise`
call, with the engine doing no arithmetic on them. That asymmetry is the point — the Winkler
grade is declared once, on the side that also grades it, so the agent can never be graded on a
loss it did not decide under. `act` names the SPEECH ACT a row belongs to, so the transform
registry's eligibility predicates (the owner-scoped attribution guard, the §2-A rescue gate)
keep asking "did this commit?" rather than matching a wire name; VOI is priced over the same
action set the terminal decision is taken over, extras included.

**The response vocabulary did not grow** (C5). An interval is a `report` at a lower precision,
so `DEC.ACTIONS`, `LOOKUP_ACTION_ORDER`, `gate.ASSERT_ACTIONS` and the bridge's
`_TERMINAL_ACTIONS` are untouched, and r21's frozen grading branch received the claim with no
change at all.

## The finding — the pinned corpus can barely exhibit this lever

Measured off the m5-base fixtures' own recorded candidate sets, on both lanes:

| | count |
|---|---|
| pinned questions | 104 |
| classify `quantity` | 19 |
| …of which carry **≥2 distinct numeric candidates** | **5** |
| …carry exactly one distinct numeric candidate | 13 |
| …carry none | 1 |

**The lever can fire on 5 of 104 questions**, identically on the A-loop and B-lookup lanes
(`q2-004`, `q2-029`, `q2-056`, `q2-059`, `q2-090`). On 14 of the 19 quantity questions there is
no range to claim, because the evidence never produced two different numbers.

This is the plan's defect 1 measured rather than argued, and it binds r31: against the §6.13
commit-wobble floor of 2, a 5-row population is not a reading. **r31's Pop B — the 15 computed
questions of `$LIFE_AGENT_KB/eval/aggregate-questions.yaml`, run through `run_eval`'s gate
machinery as its own pinned series — is a precondition for reading this lever, not an
enhancement to a reading that would otherwise stand.**

## Gates

**G1.** `TMPDIR=~/.cache/tmp uv run pytest -m "not llm and not system" -q` → **2998 passed,
35 deselected** (250s). `ruff check .` → all checks passed. `uv run mypy` → **no issues in 229
source files**. `.githooks/pii_check.py` → **exit 0** with the private name layer live.
Credence side: `test_extra_actions.jl` 18 checks, plus all five existing suites unmodified
(69 · 79 · 14 · 12 · 16).

*Harness note, disclosed:* an earlier run of the same suite reported one failure in
`test_m7_register.py::test_d4_the_leader_order_is_one_view`. It was self-inflicted — three of
this session's own verification runs were rewriting the same `src/` files concurrently (the
mutation pass mutates in place), and that test reads source. Re-run serialized with nothing
else touching the tree, the suite is green; the counts above are from that run, not the racing
one.

**G2 — the replay, under C10's attributed-delta criterion.** `PYTHONHASHSEED=0
scripts/collapse_replay.py --checkpoint m5-base`, two draws, plus the same command on master:

| tree | compared | errored |
|---|---|---|
| master `456dd54` (baseline) | 293/314 | 21 |
| r30b, draw 1 | 288/314 | 26 |
| r30b, draw 2 | 288/314 | 26 (**byte-identical errored set**) |

The 21 are carried, not new: every one is an A-loop fixture missing `GET /utility?shape=…`, the
**r30** wire-only artefact a pre-r30 cassette cannot contain, and the baseline run reproduces
exactly that set on master. The 5 new ones are all B-lookup fixtures whose recorded `optimise`
request now carries `interval_*` rows.

**The changed set is predicted exactly.** Applying the declared gate — `quantity` ∧ ≥2 distinct
numeric candidates — to every fixture's own recorded candidate set predicts the replay's changed
set on **104/104** fixtures, in both directions: all 5 changed fixtures satisfy both conjuncts,
and all 99 unchanged ones fail at least one. Zero deltas outside the declared population, so
C10 is met as frozen, with the direction asserted rather than asserted-by-absence.

**Mutation transcript — every frozen criterion demonstrated RED by its named mutation, then
restored** (nine mutations, plus the build-once mutation under disclosure 8):

| | mutation | test driven RED |
|---|---|---|
| C1 | width pays inside the action → 0-1 containment | `test_width_pays_inside_the_action_so_the_widest_does_not_dominate` |
| C2 | drop the shape gate | `test_no_interval_rows_off_shape` |
| C3a | lookup re-derives a row instead of placing it | `test_action_utilities_carries_the_options_verbatim` |
| C3b | the wire re-derives the rows the in-process lane ranks | `test_the_daemon_receives_the_same_rows_the_in_process_lane_ranks` |
| C4 | fork the Winkler constant in the grader | `test_the_winkler_constants_have_one_home` |
| C5 | grow the response vocabulary | `test_the_response_vocabulary_does_not_grow` |
| C6 | the wrong-commit class stops being expressible | `test_the_interval_excludes_gold_class_is_visible_from_birth` |
| C7 | the grader keeps a second numeric parser | `test_numeric_value_is_the_only_parser_the_graders_use` |
| C8 | coverage becomes an argmax instead of a sum | `test_the_coverage_credence_is_the_covered_mass` |

The credence-side change was verified RED the same way, by reverting the two source files and
re-running its suite (`MethodError: no method matching decision_fpa(...; extra=...)`).

## Deviations and disclosures

1. **The build site was re-scoped before any `src/` change**, for the reason recorded in the
   pre-registration above: the approved plan named `lookup.action_utilities` as "the one decide
   surface", and the gate's typed arm plus the deployed read path both decide in the credence
   daemon instead. Disclosed in the frozen document, not after the fact.
2. **TDD order was not clean on the credence side.** The Julia tests were written after the
   Julia implementation and their RED state established retroactively, by reverting the
   implementation and re-running. The Python side was red-first throughout. Recorded as a
   deviation rather than presented as compliance.
3. **`voi_gather` now prices over the extended action set.** This is a deliberate behaviour
   change on the gather lane: VOI is the expected gain in `value`, and `value` must be taken
   over the action set the terminal decision is taken over, or a probe is priced against a
   decision the agent is not solving. `provisional_leader` is deliberately NOT extended — it
   answers "which candidate would you report if forced", which remains a `report_j` question.
4. **A capability check was added that the pre-registration did not name.** A daemon predating
   `extra_actions` ignores the key silently, so the body would price rows nothing ranks and a
   gate run would measure the pre-r30b action set while believing otherwise. The daemon now
   echoes `n_extra_actions` and the executor **raises** when it sent rows and got no echo. This
   is an addition beyond the frozen scope, made because silent degradation is the one failure a
   gate reading cannot survive; it is disclosed here rather than folded in quietly.
5. **`aggregate.totals[].point` is the interval midpoint** — a record/display field only. In
   r21's shape it was the composed total's point estimate; nothing reads it to decide.
6. **The proposal grid is capped** at `MAX_INTERVAL_VALUES = 8` distinct values (28 rows),
   coarsened by evenly spaced order statistics keeping both endpoints. The coarsening is
   posterior-blind by construction (`interval_options` never receives a credence), and when it
   binds every option built off the coarsened grid carries `grid_coarsened`, which the recorded
   claim carries too — a bound cap nothing records would read as "these were all the proposals
   there were". The cap did not bind anywhere in this checkpoint's data: the largest observed
   candidate set is 4 distinct numeric values.
7. **§6.10 rider landed:** `run_meta.json` now carries `decider_git` — the answer-brain
   daemon's tree, located by `CREDENCE_DIR`, with an unlocatable checkout recorded as a stated
   reason rather than an absent key. Without it r31 could not attribute its own reading to the
   tree that produced its decisions.
8. **A defect this checkpoint's own tests caught, disclosed rather than quietly fixed.** The
   first implementation built the interval rows ONCE, before the executor's decide loop. But
   the loop can MINT a candidate mid-question (`re_extract_strong` naming a new value), and a
   row spans the K+1 atoms of the posterior it is ranked against — so the second decide would
   have posted rows spanning the wrong space, and a live daemon would have refused them by the
   length check the credence side deliberately fails loud on. Found by writing the test for
   "the rows track a candidate the loop mints", which was RED against the build-once
   implementation and is kept as a mutation-verified guard. The rows are now rebuilt per
   decide from the current candidate list.
9. `GETTING_STARTED.md`'s status paragraph was three items stale (it still described the
   collapse ladder as remaining work and pointed at `questions.yaml`); corrected as
   doc-currency, no new claims.

## What this checkpoint does NOT claim

It does not claim the lever helps. It builds it, proves it is one declaration ranked by one
argmax on both surfaces, and measures that the pinned corpus can exercise it on 5 rows. Whether
it earns its place is r31's question, on the two populations the roadmap names — and by C12,
merging this does not deploy it.

**Next:** r31a (the $0 evidence pack — splice, both-utilities reading, off-gate sweep), then
Conferral 1, then r31.
