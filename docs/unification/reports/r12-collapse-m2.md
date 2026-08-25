# r12 — collapse M2: the one poster (Q-O6) — PRE-REGISTRATION (2026-08-25)

> The §8 checkpoint after M1.5: **one driver function; `AC.answer`/`answer_via_executor`
> become thin delegating shims; the family leaves return their decision; the driver records
> once; A-3/D-10 die; S-1's unavailability path unified (B-2/A-1)**
> (`docs/module-collapse-design.md` §8 M2 row, §5.1, §6.5).
> **This document is the pre-registration. It is committed before any `src/` edit on this
> branch; git history is the proof.** Gates and directions frozen here are not renegotiable
> at read time; a FAIL on any frozen gate is a STOP for an owner ruling (the completion
> plan's keypress map).

## STATE

- master `6911eba` (Stage 0 closed: m2-base recorded — r11; the proplang mandate registered
  — §18). Suite 2671 green (35 deselected), ruff green, mypy: one pre-existing note in
  `scripts/replay_audit.py:694` (not this checkpoint's; disclosed).
- 7.2 baseline: **m2-base, 314/314 replay identically** on this tree (r11's transcript).
- The oracle from here: `scripts/collapse_replay.py --checkpoint m2-base` (design §8,
  baseline-of-record note).
- The inherited observation (M1.5, r05-collapse-m1-5): 0 of 104 priced A-loop rows stamp
  `regime`/`policy`; the seam path's record carries `regime: None`; "M2's poster owns it".

## The mandate, exactly

Three rows, one function (design §5.1):

1. **One driver.** `ASK.answer_via_executor` (`scripts/ask.py:982`) and `AC.answer`
   (`core/ask_client.py:109`) become one function with one `/log_decision` body. The two
   become **thin delegating shims for exactly one checkpoint** (M2→M3), then deleted.
2. **One poster body.** The union `BR._log_decision` already accepts, **plus `regime` and
   `policy` stated** — *no accounting field is optional on the poster's side*: a firing
   that ran unpriced records `cost_usd: 0.0` with its instrument, never an absent key.
   Today `AC:143-149` posts none of the accounting fields — the reach surface's decisions
   are unpriced in the ledger. **The pre-registered record change: absent keys → present
   with `0.0`/`""`.**
3. **One recorder.** `D.record` (§18.9 answer node) and `DEC.append` are the leaves' side
   effects today (`LK.decide_and_record:1163-1191`, `NR.narrative_answer:510-538`); after
   M2 the one recorder performs them and the leaves' own write calls are dead code
   (removed at M3). The `decision_id = akey.cache_key` rule preserved verbatim.
4. **S-1 unified (B-2/A-1).** `AC.answer`'s seam-less DOWN bypass (`AC:118-119`) dies:
   both surfaces commit `SEAM.commit(None, gates=(GATE_EXECUTOR_DOWN,))`, mirror the gate,
   and **record the §6.5 unavailability event** — a RECORD carrying `regime: unavailable`
   with no `decision_id`, never a foldable abstain verdict.

## The design, frozen

**D1 — the one recorder, `src/life_agent/core/recorder.py` (new).** Imports only
`decisions`/`derivations`/`outcomes`/`config` (no cycle: `lookup`, `narrative`,
`ask_client` and `scripts/ask.py` all import it).

- `body(...) → dict` — the ONE `/log_decision` body. Every key always present:
  `effector, credences, candidates, p_none (None→0.0), eu (None→0.0), n_obs,
  n_indeterminate, n_competing, instrument (None→""), cost_usd (None→0.0),
  latency_s (None→0.0), run_id (None→"answer-brain"), regime, policy`.
- `record_via_bridge(post, bridge, question, retrieval_keys, body) → decision_id | None`
  — the trace-A transport; fail-open contract preserved at the shims (a calibration write
  never breaks the answer).
- `record_local(...)` — the family leaves' tail: `D.record(root, akey, content, lineage)`
  then `DEC.append(path, event)`, **byte-identical to the events the leaves write today**
  (the leaves' v2 defaults — `cost_usd: None` etc. — are preserved on the local events;
  the §5.1 never-absent normalisation binds the *posted* body. Normalising the leaf events
  is deferred to the checkpoint that declares their regime — M5 — and said here so it is a
  decision, not a drift).
- `record_unavailable(question, *, run_id=None, decisions_path=None)` — the §6.5 event,
  appended **locally** (the stack is down by definition; the bridge cannot be assumed
  reachable; the client and the ledger share the box by deployment):
  `DecisionEvent(family="lookup" (the endpoint's own constant — the down-record fires on
  the lookup read-path's driver, before any route), action_set=LOOKUP_ACTION_ORDER,
  chosen_action="abstain", posterior_summary={candidates: [], credences: [], p_none: 0.0,
  n_obs: 0, n_indeterminate: 0, n_competing: 0}, utility_fold_version="" (no fold ran),
  predicted_eu=0.0, decision_id="" (no verdict can ever bind), instrument="",
  cost_usd=0.0, latency_s=0.0, regime="unavailable" (stated),
  policy=POLICY_DEFAULT with defaulted=("policy",) (no fold ran — the writer cannot state
  it), run_id=run_id or "answer-brain")`. Returns no decision_id. Fold-safety: no
  reaction can join `decision_id=""` (schema docstring: "Empty only on pre-reaction-loop
  lines, which no verdict joins") — **pinned by a test**, plus a guard test that
  `/log_reaction` refuses an empty `decision_id`.

**D2 — the one driver, in `core/ask_client.py`.** `drive(question, k, *, post=None,
get=None, run_id=None, check_ready=True) → DriveResult(view | None, decision_id | None,
down: bool)`:

- ready check (the two `/ready` probes — `ASK._executor_ready` ≡ `AC._ready`, verified
  identical semantics) → on down: `SEAM.commit(None, gates=(GATE_EXECUTOR_DOWN,))`,
  assert abstain, `SM.mirror_gate(...)`, `recorder.record_unavailable(...)`,
  `DriveResult(None, None, down=True)`.
- up: `question_id` → membrane live/shadow wiring (unchanged) → menu/curves (the shared
  `_menu` shape — one copy) → `EX.decide_via_loop(...)` (the loop is untouched at M2) →
  **post iff the loop committed a lookup-family terminal** (`route is not None and
  effector in DEC.LOOKUP_ACTION_ORDER and credences`) — the *condition* survives as the
  driver's single post-what-the-seam-committed rule; what DIES is its duplication in two
  posters (A-3/D-10). A miss commits no decision (no posterior, no seam commit — `EX:377`
  returns before `/decide`); a route-null question's decision is the narrative family's
  and is recorded by that leaf. **M2 changes no case of *which* decisions are recorded**
  — only the body's shape and who writes.
- the posted body: `recorder.body(view fields..., instrument=view.instrument or "",
  cost_usd=view.cost_usd (None→0.0), latency_s=view.latency_s (None→0.0),
  run_id=run_id or "answer-brain", regime="full" (stated — the daemon decided),
  policy="all-to-date" (stated — `current_u_bar` folds everything to date;
  "frozen-elicitations" becomes stateable at M3's `posterior(policy=…)`, never here)`.

**D3 — the shims (one checkpoint, deleted at M3).**

- `AC.answer(question, k, *, post, get, check_ready) → (rendered, decision_id)` — calls
  `drive`; on down returns `(DOWN, None)` verbatim (interaction contract strings
  untouched). jarvis (`reach/jarvis.py:230,268`) is unchanged.
- `ASK.answer_via_executor(question, k) → (text, cards, scores)` — calls `drive` with
  `run_id=EXECUTOR_RUN_ID`; keeps its `*_LAST` globals, cards/scores derivation, and the
  `EXECUTOR_DOWN` string verbatim. `ASK._log_executor_decision` dies into the driver.
- `LK.decide_and_record` / `NR.narrative_answer`: signatures unchanged; their write tails
  become `recorder.record_local(...)` with byte-identical content/lineage/event. Callers
  (`LK.lookup_answer`, `GA.gather_answer`, `BR._narrative`, the collapse drive functions)
  unchanged.

**D4 — the expected-change comparator (§7.2's own mechanism, landed with this
checkpoint).** `collapse_replay`/`compare` gain direction-assertion: a fixture whose
`expected_change.checkpoint` names M2 is compared under its **named direction spec**
(registered in code, keyed by checkpoint) instead of raw equality. The spec is *tight*:
every field not named by the direction stays value/type-equal; the named fields must match
exactly. A wrong or missing directed field FAILS (RED-verified by tests before the src
change lands: a body with `regime: "terminals-only"`, a body missing `regime`, and an
unnamed extra field must each fail). Never-silently-weaken: the direction was
pre-registered into the fixtures at record time (r11); this lands the machine form.

## The pre-registered record changes (directions, machine form)

**DIR-1 — the 104 A-poster fixtures** (`expected_change.checkpoint == "M2"`):

- `log_decision.decision.regime` — absent → present, exactly `"full"`.
- `log_decision.decision.policy` — absent → present, exactly `"all-to-date"`.
- `log_decision.decision.cost_usd` — null → number allowed (the never-absent
  normalisation); number → number unchanged in kind.
- `log_decision.decision.latency_s` — null → number allowed; same rule.
- Every other field (body and outputs): unchanged under the standing field classes.

**DIR-2 — the seam fixture** (`expected_change.checkpoint == "M2/M5"`; the record half
lands NOW, at M2):

- `effector` stays `"abstain"`; `gate` stays `"executor_down"` (nothing but abstain is
  enactable against a down stack — the act does not change; the *record* does).
- outputs `regime` — absent → present, exactly `"unavailable"`; outputs `policy` — absent
  → present, exactly `"all-to-date"` (the defaulted disclosure rides the event, in the
  recorded-only audit).
- `log_decision` — `null` → the §6.5 body: `decision.regime == "unavailable"`,
  `decision.effector == "abstain"`, `decision.credences == []`,
  `decision.candidates == []`, `decision.p_none == 0.0`, `decision.eu == 0.0`,
  `decision.n_obs == 0`, `decision.instrument == ""`, `decision.cost_usd == 0.0` (number),
  `decision.latency_s == 0.0` (number), `decision.run_id` present.
- **no decision_id**: the replay's outputs must carry no bound decision id (the event's
  `decision_id` is `""`; nothing is returned to bind a verdict to).

**DIR-0 — everything else is equality.** The 104 A-loop, 104 B-lookup and 1 B-narrative
fixtures must replay **byte-identical** (the loop is untouched; the leaves' events are
reproduced byte-identically through the recorder; the in-process leaves do NOT stamp
`regime` at M2 — the terminals-only regime is *declared at M5* (§8 M5 row), and stamping
it while the `--legacy` *choice* still exists (B-1, dies at M5) would record a choice as a
fact, violating §2.3).

## Gates, frozen (a FAIL on any is a STOP)

- **G1 — 7.1:** `uv run pytest -q` green (temp under `~/.cache`), plus this checkpoint's
  new tests; `uv run ruff check .` and `uv run mypy` no worse than STATE.
- **G2 — 7.2:** `PYTHONHASHSEED=0 uv run python scripts/collapse_replay.py --checkpoint
  m2-base` exit 0: 209 fixtures equal (DIR-0), 104 pass DIR-1, 1 passes DIR-2 — the
  transcript is the report's artefact.
- **G3 — 7.4:** the golden harness A-rows for the decision-derived artefacts and
  `pkm.artifact` (`python -m life_agent.ledger.golden snapshot/replay/compare` + `counts`,
  the C6 row) run **before and after** the src change at the same T0 discipline: compare
  green both sides, counts unchanged by replay. Plus the one-write-per-decision pins:
  one driven decision → exactly one `/log_decision` post (trace A); one leaf decision →
  exactly one `DEC.append` + one `D.record` (trace B); the §6.5 down path → exactly one
  local append and nothing on any other store (all hermetic tests).
- **G4 — the hard clause:** no named wrong-commit class worse — M2 is
  behaviour-preserving on *what is decided* (G2 asserts effector equality on all 314);
  the record change is the pre-registered shape delta only.
- **G5 — PII:** the new module and tests carry no corpus values; the armed hooks run on
  every commit (`LIFE_AGENT_KB` exported).

## Predictions (registered before implementation)

- P1: all 209 DIR-0 fixtures replay byte-identical on the first green build.
- P2: all 104 A-poster fixtures pass DIR-1 with `regime/policy` the only new keys and
  `cost_usd/latency_s` the only kind changes.
- P3: the seam fixture passes DIR-2; the unavailability event appends locally with
  `decision_id=""` and no verdict can bind to it (the reaction-guard test).
- P4: golden compare green before and after; C6 counts move only by the suite's own
  staged writes (i.e. not at all on the live stores).
- P5: no live calibration surface changes during the checkpoint (everything hermetic;
  fingerprint check before/after the gate run).

## Deviations

Cap-the-arc: anything unexpected en route is a disclosure item in this report's final
form, never a new diagnostic arc. Rollback: revert the branch (one PR).

## AMENDMENT 1 (2026-08-25, blind — before any gate run; committed before the gates)

Found by reading `collapse/drive.py` during implementation, not by running anything:
**`drive_executor_loop` (the A-loop trace) drives `AC.answer` and captures the posted
`/log_decision` body into its outputs** — so the A-loop fixtures recorded the reach
poster's REDUCED body too, and the §5.1 record change reaches them exactly as it reaches
the A-poster trace. Two corrections, both scope, neither semantic:

1. **DIR-1's scope** was drawn as "the 104 A-poster fixtures". Corrected definition: DIR-1
   applies to **every fixture whose recorded `log_decision.decision` lacks the `regime`
   key** — the precise signature of a body produced by a pre-collapse poster (the
   B-traces' bodies are shaped from their `DecisionEvent`s and already carry both keys).
   That is: the 104 A-poster fixtures AND the A-loop fixtures that posted. The appear-set
   is extended for keys the reach poster never posted at all:
   `run_id` appears at exactly `"answer-brain"` (the one default — the shim passes no
   run id, deterministically); `instrument` appears at exactly the fixture's own recorded
   `audit.instrument` (or `""` where that is null) — the value the loop realised, recorded
   at m2-base record time; `cost_usd`/`latency_s` appear as numbers (runtime-measured:
   presence and kind, never value). `regime`/`policy` unchanged: exactly
   `"full"`/`"all-to-date"`. Everything else stays under the standing classes. A fixture
   whose recorded body is `null` (miss / route-null) must replay `null` — equality.
2. **The replay drive serves `/log_decision` canned** (`{"decision_id": "replayed"}`)
   instead of consulting the cassette: the poster's reply feeds no decision (the id is
   audit-only), the posted BODY is what the comparator pins, and without this every
   poster-shape checkpoint would cassette-miss on its own pre-registered change (the
   cassette matches request shape exactly). The m2-base cassettes' now-unconsulted
   `/log_decision` exchanges surface as "unused exchange" notes — expected, disclosed.
   The same canning applies at record from M2 on (the A-poster trace already records its
   poster hermetically; the bridge endpoint's own validation is pinned by
   `tests/test_bridge_server.py`).

P1/P2 restated to match: **P1** — the 104 B-lookup + 1 B-narrative fixtures replay
byte-identical; A-loop fixtures with a `null` body replay byte-identical. **P2** — every
fixture with a recorded pre-collapse poster body (A-poster + posting A-loop) passes DIR-1
as amended. P3–P5 unchanged.
## RESULTS (read 2026-08-25, appended after the gates ran — nothing above this line changed)

Execution was four TDD phases on branch `collapse-m2`, in the pre-registered order:
(1) the directed comparator (`collapse/compare.py`: DIR-1 as amended, DIR-2, the
`compare_fixture` dispatch — 35 comparator tests), (2) the one recorder
(`core/recorder.py` + `tests/test_recorder.py`, including the leaf-drift gate that bans
`DEC.append(` from the family leaves' source), (3) the one driver + shims
(`ask_client.drive`/`post_decision`, `scripts/ask.py` reduced to shims,
`_log_executor_decision` deleted, the hermetic `DECISIONS_LOG` conftest guard), (4) the
replay drive (`collapse/drive.py`: canned `/log_decision`, the poster driven through
`AC.post_decision`, the seam trace driven through `AC.drive(ready=False)` reading the
§6.5 event from a swapped sink).

### Gate readings

- **G1 — GREEN.** `pytest -m 'not llm and not system'`: **2705 passed, 35 deselected**
  (the growth over the pre-M2 tree is this checkpoint's own new tests). `ruff
  check .`: all checks passed. `mypy`: no issues in 220 source files. (Seven ruff
  findings and one mypy narrowing arose en route on new code and were fixed before the
  gate reading — disclosure D1.)
- **G2 — GREEN, twice.** `collapse_replay --checkpoint m2-base`: **314/314 fixtures
  replay identically** — run once when implementation went green
  (`~/.cache/life-agent/m2/replay-20260825T153531.log`) and again on the final tree
  after every lint/type fix (`replay-final-*.log`). 105 fixtures direction-ASSERTED.
  Populations: 104 A-loop + 104 B-lookup + 1 B-narrative + 104 A-poster + 1 seam; the
  105 ASSERTED lines are the annotation-carried fixtures (poster + seam), and DIR-1
  additionally dispatched on the A-loop bodies by the amended signature — 102 with-body +
  2 null on each of A-poster and A-loop — the amendment's scope correction was load-bearing on all 102 posting A-loop
  fixtures.
- **G3 — GREEN.** The 7.4 golden harness on both legs: before-leg on the pre-M2 tree
  (worktree at `6911eba`), after-leg on this branch. All five decision-derived artefacts
  (utility-fold-version, curves, reactions, answers, pkm-index) compare **exit=0** on
  both legs; the C6 counts blocks are identical between the legs (nothing wrote the live
  stores). Log: `~/.cache/life-agent/m2/golden-20260825T203222.log`. G3-hermetic: the
  one-write-per-decision pins are unit tests (bridge posts exactly once; trace-B exactly
  one `DEC.append` + one `D.record`; the §6.5 path exactly one local append).
- **G4 — GREEN (by G2).** Effector equality holds on all 314 — M2 changed no case of
  what is decided, so no named wrong-commit class can have moved.
- **G5 — GREEN.** No corpus values in the new module or tests; the armed PII hooks ran
  on every commit with `LIFE_AGENT_KB` exported.

### Predictions vs readings

- **P1 (as amended) — CONFIRMED.** 104 B-lookup + 1 B-narrative byte-identical; the 2+2
  null-body A-fixtures byte-identical.
- **P2 (as amended) — CONFIRMED.** All 204 pre-collapse poster bodies pass DIR-1:
  `regime`/`policy`/`run_id`/`instrument` the only appearances, `cost_usd`/`latency_s`
  the only kind changes.
- **P3 — CONFIRMED.** The seam fixture passes DIR-2; the §6.5 event appends locally with
  `decision_id=""`; `test_log_reaction_refuses_an_empty_decision_id` pins that no
  verdict can bind to it (400).
- **P4 — CONFIRMED.** Golden green on both legs; counts identical between legs.
- **P5 — CONFIRMED.** Live calibration fingerprints byte-identical to r11's before and
  after the gate runs (`e598b…`/`1d558…`/`b3b7d…`).

### Disclosures (cap-the-arc: items, not arcs)

- **D1 — lint/type fixes after green, before the gate reading.** Seven ruff findings
  (import sorts, an unused variable, a `__slots__` sort) and one mypy narrowing in
  `compare.py`, all in this checkpoint's new code; G2 was re-run on the final tree after
  them (green, identically).
- **D2 — unused-exchange cassette notes.** The m2-base A-trace cassettes carry
  `/log_decision` exchanges replay no longer consults (served canned per Amendment 1);
  `--verbose` surfaces them as notes, not failures. They retire at the next baseline
  re-record.
- **D3 — a pre-existing wart, out of scope.** `BR._narrative` does not pass
  `deps.decisions_path` through, so the narrative leaf's ledger append lands on the
  config default rather than an injected path. Unchanged by M2 (the moved write is
  byte-identical); noted for M3, whose fold-entry unification touches that seam.
- **D4 — the G3 harness ran three times to get one complete reading.** Attempt 1 was
  killed externally mid-before-leg (3/5 artefacts green at the kill). Attempt 2 stalled
  for 30+ minutes: an unrelated session's recursive grep over the KB volume's maildir had
  been saturating the USB disk's 2-tag request queue for 4.5 hours (every yo IO starved in
  `blk_mq_get_tag`); the reader was killed, the disk moved to the BFQ scheduler with a
  real queue depth (udev-persisted — a machine fix, not a repo change), and the same
  invocation then completed as the reading above. Environment interference, not a gate
  signal: the artefact comparisons are content-addressed and unaffected by when they run.

### Verdict

**M2 is DONE**: one poster (`ask_client.post_decision`), one recorder
(`core.recorder`), one unavailability record (§6.5, locally appended, unfoldable), the
family leaves write through the one recorder, and `scripts/ask.py`'s
`answer_via_executor`/`_edge_curves` are thin shims that die at M3. The record change is
exactly the pre-registered shape delta. The ladder proceeds to **M3 — the one fold entry
point** under its own pre-registration.
