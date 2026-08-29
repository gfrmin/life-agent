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
