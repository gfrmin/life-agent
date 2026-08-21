# r04 — tranche 2, checkpoint M1 (E-14 dies) — 2026-08-20

> **IN PROGRESS.** This report is being written as the checkpoint runs, not reconstructed
> afterwards. Sections appear in the order the work happened; nothing below is a plan.

## STATE

Master at `861ea1b` (O2, the priced baseline, merged and pushed). Baseline of record:
`$LIFE_AGENT_KB/eval/collapse-fixtures/m0-5`, **311 fixtures**, replaying 311/311.

## DONE 1 — the pre-registration the brief requires, before anything is deleted

The brief: *"The affected fixture ids are pre-registered in the report before the deletion
lands."* Measured over the baseline of record, read-only
(`~/.cache/life-agent/m1/cascade-census.py`). The cascade is detectable per fixture because
each tier is one extra `/retrieve` pass in the recorded wire.

| passes | fixtures | terminals |
|---|---|---|
| 0 | 1 | abstain (the route-declined case) |
| 1 — no cascade | 80 | report 34 · abstain 46 |
| 2 — tier 1 only | 1 | report 1 |
| 3 — both tiers | 22 | abstain 20 · report 1 · miss 1 |

**The cascade fired on 23 of 104 A-loop fixtures, and changed the terminal on exactly two.**
That gap is the important part: the grown view REPLACES the base one only when it reports, or
when the base had no candidates at all (`executor.py`, the
`if grown["effector"] == "report" or not view["candidates"]` rule). On the other 21 the
cascade ran, cost two extra retrieval passes, and the base view was kept — its only surviving
trace is the merged `edge_events` and `spend_usd`.

**Pre-registered at-risk set — the two terminals the cascade earned:**

| fixture | terminal | candidates | n_obs |
|---|---|---|---|
| `m0-5-aloop-q2-017` | report | 2 | 1 |
| `m0-5-aloop-q2-060` | report | 1 | 14 |

A 2-pass fixture ending outside the withhold set can only have got there by the grown view
replacing the base one, since the loop breaks at the top on a non-withhold effector — so the
inference from pass-count to "the cascade earned this" is sound rather than suggestive.

**The pre-registered direction** (design §7.2, brief): the priced lane reaches a terminal ⊇ the
cascade's. Concretely, and now falsifiably: **the priced lane must still reach `report` on
`q2-017` and `q2-060`.** Everywhere else the direction is satisfied trivially, because the
cascade changed nothing there.

## DONE 2 — R8's guard (rides this commit, ruled at M0.5's review)

`FX.existing_fixtures()` (`src/life_agent/collapse/fixture.py`) plus `--allow-existing` and a
refusal in the recorder. TDD, four RED witnessed before implementing:

* a directory holding fixtures is named as unsafe;
* an absent or empty one is safe;
* a lone `manifest.json` is unsafe — a run that died between publishing and being merged leaves
  exactly that shape, and the next run republishes it;
* a lone `snapshots/` is **safe** — `take_snapshot` re-copies the fold inputs every run, so
  refusing on it would refuse every legitimate re-record.

The guard runs **before the snapshot and before anything that can spend**, which is the whole
point: the recording is the expensive part and finding out afterwards is finding out too late.
Verified live — it refuses on the real 311-fixture baseline, and `--relabel-only` still works,
since that path needs the existing files. Suite 2505 passed (+4), ruff and mypy clean.

## DONE 3 — M1 cannot run as briefed, and the reason is structural

**The priced lane cannot replay against the baseline of record at all.**

M1's scope retires `LIFE_AGENT_GROW_LANE` — *"the priced lane is the lane"*. That lane calls
`GET /grow_menu` unconditionally (`executor.py`, `menu = get(f"{bridge}/grow_menu")["grow"] if
grow_lane else None`). The baseline of record contains **zero** `/grow_menu` exchanges across
all 311 fixtures; the recorded endpoint set is `/decide`, `/extract`, `/log_decision`,
`/narrative`, `/probe/corroborate`, `/probe/deliberate`, `/probe/recency`, `/probe/subject`,
`/retrieve`, `/route`, `/utility`. The cassette raises `CassetteMissError` on anything it never
saw, and a replay that cannot run is a FAILURE, never a skip.

The replay restores the flag from each fixture's recorded provenance
(`collapse_replay.py`, `AC.GROW_LANE = bool(fx.provenance.get("grow_lane"))`), so today every
A-loop fixture replays down the legacy path. Forcing it to the state M1 makes unconditional:

```
m0-5-aloop-q2-017  (recorded grow_lane=False)
   grow_lane=False → replayed, effector=report
   grow_lane=True  → CassetteMissError: no recorded http exchange for 'GET /grow_menu'
m0-5-aloop-q2-060  (recorded grow_lane=False)
   grow_lane=False → replayed, effector=report
   grow_lane=True  → CassetteMissError: no recorded http exchange for 'GET /grow_menu'
m0-5-aloop-q2-001  (recorded grow_lane=False)
   grow_lane=False → replayed, effector=report
   grow_lane=True  → CassetteMissError: no recorded http exchange for 'GET /grow_menu'
```

`q2-001` is the load-bearing row: the cascade never touched it. So this is **not** 23 cascade
fixtures failing a comparison — it is all 104 A-loop fixtures failing to execute, and not
because a decision changed but because the oracle is structurally blind to a lane it never
recorded. The brief's 7.2 asks for *"identical decisions everywhere the cascade did not fire"*;
that comparison cannot be run at all against this baseline.

This is R3's shallow-replay boundary and R7's declared-coverage point arriving together, on M1
rather than on M1.5 where R7 was scoped. It is the same sentence from a different angle: **the
fixture set pins the traces the recorder was told to run**, and nobody told it to run the lane
that survives.

### What M1 becomes

Replaying legacy-lane cassettes against priced-lane code cannot be made to work — the wire is
recorded per-request, so a code path that asks a different question of the bridge has nothing
to be served. The surviving lane needs its own pre-change record. So M1 splits its one
instrument into two:

1. **The direction** — a fixture-to-fixture terminal comparison, legacy vs priced, over the
   same 104 questions and the same pinned fold inputs. This is the shape M0.5's delta table
   already used, and it is where `q2-017` and `q2-060` are decided.
2. **The deletion** — replay the priced-lane fixtures, whose cassettes match the code path that
   survives. Deleting dead legacy code must leave them identical.

Recorded as `m0-5-growlane` (a separate checkpoint, not merged: the fixture ids and the
`checkpoint` field would collide, and the two sets are different baselines rather than two
halves of one). A-loop only — `LIFE_AGENT_GROW_LANE` reaches `EX.decide_via_loop` via
`AC.answer`, and only `drive_executor_loop` calls it; `drive_ask_poster` takes an
already-computed view and the B-* and seam traces never touch the executor. Verified by
reading the call graph, not assumed.

## DONE 4 — the priced-lane baseline, recorded

`ALLOW_SPEND=1 ~/.cache/life-agent/m1/record-growlane.sh` · checkpoint `m0-5-growlane` ·
104 questions, `A-loop` only · `PYTHONHASHSEED=0` pinned in the script, never inherited (R5) ·
HEAD `861ea1b` · transcript `~/.cache/life-agent/m1/record-growlane-20260820T214424.log`.

Ran a 5-question pilot first, for the reason the script's own header gives: the grow lane takes
different retrieval paths, so its derivations may be cold where the legacy lane's were warm.
The pilot cost $0.0239 and passed G3, which is what licensed the full run.

**G3, the kill this recording exists for** — if the fixtures do not carry `/grow_menu`, the run
did not take the lane it claims and the artefact is worthless:

```
== verified: 104 fixture(s), all stamped grow_lane=true, 103 /grow_menu exchange(s) recorded
```

103, not 104 — so the count was chased rather than accepted. The exception is
`aloop-q2-007`, and it is not a defect: that question routes to the narrative family
(`/route` ×1, `/narrative` ×1, 91 exchanges) and never enters the executor loop, so there is
no menu to fetch. Its legacy fixture is byte-for-byte the same shape — same 91 exchanges, same
two endpoints, same `abstain`, same declared classes. A fixture that never reaches the loop is
evidence about routing, not about the lane.

**The seal.** The four live surfaces are byte-identical before and after:

```
== seal held: 4 live surface(s) byte-identical before/after
```

That line is a compensator, not the script's own doing — see DEVIATIONS 1.

**Cost: $0.5709, measured.** Not estimated. Every `instrument`-seam exchange records
`cost_usd` in its response, so the cassette prices the run it recorded: 862 instrument
exchanges, all at engine `0.105.2`, no nulls and no zeros. Projected $0.44; the overrun is
the grow lane's extra retrieval going cold.

This also **supersedes a claim in r02's addendum** (B3), which said the recorder cannot state
its own spend and gave O2 an estimate of ~$0.05. The recorder cannot, but the *fixtures* can,
and by the same sum `m0-priced` reads **$0.0581** — so the estimate was sound and is now a
measurement. Recorded here as a compensating entry rather than an edit to r02.

## DONE 5 — the pre-registered direction: HOLDS

`lane-delta.py m0-5 m0-5-growlane`, comparing through `compare_outputs` — the declared
comparator, per §6.8, never a convenience oracle built for the occasion:

```
legacy m0-5: 311   priced m0-5-growlane: 104   shared: 104

identical under the declared comparator: 35/104
differing:                                69

terminal transitions (legacy → priced):
  abstain      → abstain       67
  report       → report        36
  miss         → miss           1

the pre-registered direction, on the at-risk set:
  aloop-q2-017: legacy=report  priced=report  OK
  aloop-q2-060: legacy=report  priced=report  OK

DIRECTION HOLDS
```

**No terminal moved anywhere** — not on the two the cascade earned, and not on the other 102.
The direction was registered as `⊇`, so a single `report → abstain` outside the at-risk set
would have been a violation to argue; there are none.

**Where the lanes do differ.** 69 of 104 differ under the comparator, on 488 field diffs, and
the shape of that is the substantive result:

| declared field | fixtures moved |
|---|---|
| `credences` / `decision.credences` | 68 |
| `p_none` / `decision.p_none` | 68 |
| `log_decision.retrieval_keys` | 60 |
| `decision.n_obs`, `decision.n_indeterminate` | 34 |
| `candidates` / `decision.candidates` | 32 |
| `decision.n_competing` | 18 |
| `eu` / `decision.eu` | 3 |

Every one of the 488 is `reason=value`. **None is `unclassified`, `absent` or `unexpected`** —
the priced lane introduces no field the fixture set has not already declared, so the field
classification carries across the lane change intact. That is worth stating plainly: the
surviving lane retrieves differently and lands a different posterior on two thirds of the
corpus, and still chooses the same action every time.

**A lane-visible difference the terminals would have hidden.** The transcript prints
`(expansion refused → raw-question fallback)` twice — `core/expansion.py:144`, the shared
refusal gate, attaching to `q2-060` and `q2-068`. It appears **zero** times across all three
prior recordings (`m0-5`, `m0-5-verify`, `o2/record-priced` — 104/104/105 questions). It cost
`q2-060` nothing (still `report`), but it is the priced lane taking a different retrieval path,
and it is named here rather than filed as noise. Consistent with `retrieval_keys` moving on 60.

Wire-level, the same story: the priced lane adds `/grow_menu` ×103 and `/log_gather` ×202
(neither exists in the legacy set), roughly doubles `/retrieve`, `/extract`, `/probe/subject`
and `/probe/recency` (148 → 238), and sends a request field the legacy lane never sent —
`allow_new`, on 67 of its 309 `/probe/corroborate` calls.

## DONE 6 — R6 / §6.9 re-checked on the full set, and the premise has changed

Two findings, both against the register's stated premise for deferring the fix.

**(a) The uncovered branch is still uncovered, and the grow lane did not close it.** All 309
`/probe/corroborate` calls in the priced set carry `reextract=True`, exactly as all 326 in the
legacy set do. The plain branch has **0 calls over 104 fixtures**. Recording the surviving
lane did not buy coverage here.

**(b) A gather-lane trace would not have been an oracle in the first place.** §6.9 defers the
fix because "no fixture exercises the gather lane", so a fix "would land with no oracle". But
`probe_corroborate` runs *inside the bridge*, and the fixture set tapes the bridge at the
`http` seam — `taps.py`'s own docstring: *"Replay therefore needs no daemon, no engine, no API
key and no corpus"*. Replay serves the recorded response; the function never executes. A
gather-lane trace would record `probe_corroborate`'s **answers**, so a change to the ordering
inside it would not be exercised on replay at all. The precondition cannot deliver what it was
imposed to deliver.

**And the source is real, not closed by R2.** R2's declared key landed in
`life_agent/core/retrieval.py:53-54` —
`key=lambda h: (-round(h.score, 9), h.artifact_cache_key, h.chunk_text)`. But
`probe_corroborate` imports `search` from **`pkm.retrieval`**, a different module, whose SQL
ends `ORDER BY scored.score DESC` (`src/pkm/retrieval.py:184`) with no tie-breaker. So its two
layers — a first-arrived dedup on a strict `>`, then a stable sort by raw score — sit on a
partially ordered input. Unfixed, and not fixed by inheritance.

**What this licenses:** a real oracle that needs no trace. `probe_corroborate`'s output must be
invariant under a permutation of `search`'s return order. That is hermetic, corpus-free, and
RED-able against the current code. Proposed as the discharge of R6 at this checkpoint —
recorded under DEVIATIONS 2, because the ruling said the trace comes first.

## DEVIATIONS

**1. A §6.7 instance in an M1 instrument I wrote — after writing §6.7.**
`record-growlane.sh:92` prints `"== live surfaces AFTER (every line must be identical to
BEFORE)"` and then compares nothing. The pilot "passed" it by eye, which is not a pass. *A gate
is a script, not a sentence* — and the register entry did not stop me writing the defect a
second time. Compensated, not excused: `~/.cache/life-agent/m1/seal-check.sh` extracts both
fingerprint blocks from a transcript and diffs them. Rehearsed both ways — clean on the pilot,
and refused a mutated copy (one digit changed in the AFTER block) with exit 1, so the gate can
actually fail. Run on the full transcript above.

Named honestly: the canary is also weaker than it reads. `find … -maxdepth 2 -type d` counts
cache *directories* at depth 2, so artifacts landing deeper would not move it. Known limit,
not fixed mid-run.

**2. §6.9's fix proposed without the trace the ruling required.** The ruling was "the trace
comes first"; the reason given was the absence of an oracle. DONE 6(b) is evidence that the
trace would not have been one. The pre-committed fallback (convert to a standing
known-and-uncovered entry) is available and is the conservative option; the permutation oracle
is the better one, and is what this checkpoint proposes to build. Flagged for the reviewer to
rule rather than settled here.



## DONE 7 — the deletion: E-13 and E-14 are gone, and the lane flag with them

TDD, RED witnessed at the assertion (not at a fixture running dry — the first attempt failed
with `IndexError: pop from empty list`, which is the harness giving out rather than the
behaviour speaking, so the tests were re-scripted until the failure was the claim itself):

```
E       assert False
E        +  where False = any(<generator ... test_the_priced_lane_is_the_only_lane ...>)
E       AssertionError: assert 3 == 1
E        +  where 3 = len([{'rerank': False}, {'rerank': True}, {'rerank': True, 'expand': True}])
```

Three retrieves — the cheap pass, then rerank, then rerank+expand. That is E-13 in the output
of its own execution. Both tests pass after the deletion.

**What died** (`src/life_agent/core/executor.py`, 723 → 664 lines):

| | |
|---|---|
| **E-14** | `_truth_likely_missing` — `p_none >= leader` used as control flow, deleted outright |
| **E-13** | the `for rr, ex in ((True, False), (True, True))` escalation and its adopt rule |
| lane flag | `grow_lane` off `decide_via_loop` and `run_pass`; three branches unconditional |
| `grow` / `rerank` | `decide_via_loop` parameters that existed only to disable the cascade |

**And at every call site:** `ask_client.GROW_LANE`, `ask.EXECUTOR_GROW_LANE`,
`eval_executor._GROW_LANE` and `eval_executor._GROW` (`ANSWER_BRAIN_GROW` — it disabled the
cascade, and there is no cascade to disable). `collapse_replay.py` no longer restores a lane
that no longer exists. `run_eval.py` and `run_fairfight.py` stop recording
`LIFE_AGENT_GROW_LANE` in `env_flags`: keeping it would be **false provenance**, implying a run
that could have differed. The config-surface line the design requires at this checkpoint is in
[`interaction-contract.md`](../../interaction-contract.md) — *a stale flag in an `.env` is
ignored*, the same wording `LIFE_AGENT_FALLBACK_LANE` earned on adoption.

**Nine tests deleted** because they pinned deleted behaviour, named rather than quietly
dropped: the two grow-cascade tests, the three `_truth_likely_missing` unit tests,
`test_grow_lane_off_keeps_the_legacy_cascade`, the two grow-escalation event tests (they pinned
`merged = [*view, *grown]`, which died with the cascade), and
`test_zero_candidates_without_grow_lane_stays_miss`.

**Two behaviour changes the deletion causes, neither of them the deletion itself.** Both are
now pinned by an exact assertion, never a loosened one:

1. **A miss carries the rescue walk's firing.** The priced lane walks the grow menu before
   conceding, so a question with zero groundable candidates ends `miss` with one non-minting
   `extract@…` edge event where the legacy lane short-circuited to an empty stream. The daemon
   is still never consulted — that is what `test_extract_miss_short_circuits` was really
   pinning, and it is renamed to say so.
2. **The M3 live path consults twice, not once.** When the engine rewrites a `report` to
   `abstain`, that withholding terminal now reaches the grow re-ask, and the seam consults on
   that tick too. The path is flag-gated and off by default; the count is pinned at exactly 2.

## DONE 8 — §6.9 discharged, by the oracle DONE 6 argued for

RED first, and the failure is the defect stated in one line — the same corpus, the same
scores, a different document surviving because of emission order:

```
E   At index 0 diff: {'artifact_cache_key': 'k1', 'chunk_text': 'the lessor is ACME', ...}
E                 != {'artifact_cache_key': 'k2', 'chunk_text': 'the lessor is ACME', ...}
E   At index 0 diff: {'artifact_cache_key': 'k1', 'chunk_text': 'alpha', ...}
E                 != {'artifact_cache_key': 'k3', 'chunk_text': 'charlie', ...}
```

Both layers, both live. The fix is **one** declared key used by the dedup and the sort alike —
`(-round(score, 9), artifact_cache_key, chunk_text)`, the same shape `core/retrieval.py`
already declares. A third test pins that score still dominates, so the tie-breaker cannot
become the ranking. `tests/test_probes.py`: 11 passed.

The register entry (§6.9) carries the resolution, including that the fix landed by a
**different** oracle than the ruling named, and why the named one could not have worked.

## DONE 9 — 7.1

```
2501 passed, 35 deselected in 169.08s
All checks passed!                        (ruff)
Success: no issues found in 214 source files   (mypy)
```

2505 → 2501 is 9 deleted, 5 added (2 for the deletion, 3 for §6.9) — arithmetic, not attrition.

## DONE 10 — 7.2: the deletion changes nothing on the surviving lane

```
104/104 fixtures replay identically          (m0-5-growlane, post-deletion code)
```

Every recorded view→decision pair on the priced lane reproduces under the declared comparator.
The cascade was deleted and the lane it was never on did not move — which is exactly the claim
M1 has to support, and the reason the priced baseline had to be recorded *before* the deletion
rather than argued about after it.

**The legacy cassettes are retired, not ignored.** The predicted failure, demonstrated rather
than asserted:

```
m0-5-aloop-q2-001: replay raised CassetteMissError: no recorded http exchange for 'GET /grow_menu'
```

Leaving 104 of those in the baseline of record would make `collapse_replay --checkpoint m0-5`
permanently red, and a 7.2 command that is *expected to fail* is not an instrument — it is a
habit of ignoring a red. So the baseline was **re-based** onto the surviving lane
(`~/.cache/life-agent/m1/rebase-baseline.sh`, $0, three gates: same question set with one
legacy and one priced fixture each · snapshots byte-identical across both runs · exactly one
fixture per (trace, question) after the swap). Nothing was deleted — the 104 retired cassettes
moved to `m0-5-legacy-aloop/` and the script prints its own undo.

```
311/311 fixtures replay identically          (the re-based baseline of record)
```

Composition after the re-base: A-loop 104 (all `grow_lane=true`), A-poster 104, B-lookup 101,
B-narrative 1, seam 1.

## DONE 11 — 7.3: the eval battery. **FAIL**, and the criterion is not renegotiated

`fire-run10.sh` (the run-9 recipe, `--gate --gate-executor --gate-loo --gate-replay
--judge-grade --corpus-pin full-2026-06-11`), archived as `gate-20260821T094545`.

| | run 9 | run 10 |
|---|---|---|
| verdict | PASS **0.938** | **FAIL 0.861** (gate ≥ 0.90) |
| Δ̄ | +0.390 [+0.032, +0.841] | +0.323 [−0.074, +0.787] |
| typed | 35 ✓ / **0 ✗** / 69 withheld | 36 ✓ / **1 ✗** / 67 withheld |
| withholding split | miss 2 · dispersed 67 | miss 2 · dispersed 65 |
| answer rate (typed / mono) | 0.34 / 0.97 | 0.36 / 0.97 |
| spend (typed / mono) | $4.10 / $39.01 | $3.28 / $39.01 |
| deliberate | 60/104 (warm 53) | 68/104 (warm 68) |

M1's pre-registration named two conditions: **wrong commits stay 0**, and P(Δ>δ) stays in the
run-7/run-9 band. Both are missed. The checkpoint does not pass 7.3, and nothing below is
offered to soften that — the sections that follow attribute the failure, they do not appeal it.

### The failure is one row

`scripts/gate_splice.py`, $0, deterministic arithmetic on the archived artefacts under the
production utility posterior. Both sanity pins reproduce their published verdicts exactly
before any counterfactual is read:

| variant | P(Δ>0.05) | verdict | Δ̄ | 90% interval |
|---|---|---|---|---|
| pin — run 10's own rows | 0.861 | FAIL | +0.323 | [−0.074, +0.787] |
| pin — run 9's own rows | 0.938 | PASS | +0.390 | [+0.032, +0.841] |
| run 10 with **q2-011 withheld** (run 9's terminal on that row) | **0.952** | **PASS** | **+0.410** | [+0.053, +0.857] |

One wrong commit is worth −0.087 in Δ̄ and −0.091 in P at n=104 and u_wrong = −8.9993.
Without it the run is the strongest in the series — better than run 9 — because the tree also
bought a *correct* commit elsewhere. So the reading is not "the typed arm got worse"; it is
"the typed arm converted two withholdings, and one of them was wrong."

### Run 10 is **not** M1's reading — four decision-path changes were in the tree

This is the finding that matters more than the verdict. The run was fired believing it isolated
M1. It did not. Between run 9's firing and run 10's, four changes landed on the decision path:

| # | change | landed | visible to 7.2? |
|---|---|---|---|
| 1 | **the null-read fail-open** (pre-registered for run 10; §14) | 2026-08-19 | no — bridge-side |
| 2 | **R2's declared order** on the primary retrieval path (`core/retrieval.py`) | 2026-08-20 | no — bridge-side |
| 3 | **§6.9's declared order** on the corroborate probe (`core/probes.py`) | 2026-08-21 | no — bridge-side |
| 4 | **M1's deletion** (E-13/E-14, the lane flag) | 2026-08-21 | yes — 104/104 and 311/311 |

Only the fourth is M1's, and only the fourth has an oracle. The other three are invisible to the
decision-equivalence instrument *by construction* — DONE 6 established why (the fixture set
tapes the bridge at the `http` seam, so replay serves recorded responses and never executes
bridge code), and that argument was used there to discharge §6.9's trace precondition. The same
property that made the precondition unmeetable makes these three changes unwitnessed.

An odd reading therefore cannot be attributed, which is precisely the conflation §8 gives M1.5
its own checkpoint to avoid. The report notes it as an instrument defect below rather than as
an excuse: the number is what it is.

### The instrument defect: a recipe-verbatim gate is not a tree-verbatim gate

`fire-run10.sh` carried a TREE gate. It asserted a clean worktree, that HEAD *lacks* E-14, and
that HEAD *has* §6.9's declared key — three assertions about the change under test, and **none**
about everything else. A gate that pins its command line and the presence of its own change,
but not the decision-path tree it runs against, cannot deliver an attributable reading; it will
silently price whatever else has landed. The fix is a positive statement, not another negative:
a gate run should record, and diff against the comparison run, the set of decision-path files
and their hashes. Registered as **§6.10**; the next run is the first to carry it.

### q2-011, diagnosed

The wrong commit is `q2-011`. Its posterior across the series (values are corpus data and stay
out of tree; the gold is a jurisdiction-and-year-prefixed serial reference id, and the
competitor is a same-shape id from a different year):

| run | terminal | candidates on the lattice | leader credence | p_none | n_obs | EU |
|---|---|---|---|---|---|---|
| 7 | ✓ report | 1 (the gold) | 0.916 | 0.084 | 5 | 0.176 |
| 8 | ✓ report | 1 (the gold) | 0.955 | 0.045 | 1 | 0.562 |
| 9 | · abstain | 1 (the gold) | 0.819 | 0.181 | 1 | 0.000 |
| 10 | ✗ report | **2** — a competitor leads, the gold demoted to 0.033 | **0.902** | 0.066 | 1 | 0.044 |

Not a threshold wobble. In run 10 **a second candidate entered the lattice and displaced the
gold**, which had been the sole candidate in all three prior runs, while `n_obs`, `n_competing`
and `n_indeterminate` were unchanged from run 9.

**What best explains it: change 1.** The null-read fail-open's pre-registration named this exact
failure mode in advance — *"restoring a channel the erasing contract had been suppressing can
surface a WRONG leader that clears the bar … this is the first change in the arc whose failure
mode is a wrong commit rather than a withholding, and the zero-wrong streak is what it puts at
stake."* The posterior signature fits it: the candidate set grows, the NONE mass collapses
(p_none 0.181 → 0.066 — the null re-read is no longer counted as evidence for NONE), and the
grounded observation count does not move. The aggregate fits its predictions too — dispersed
withholdings 67 → 65 (two conversions, one correct and one wrong), answer rate 0.34 → 0.36,
spend flat-to-down. Read on its own pre-registered terms, run 10 is that change's measurement,
and it measures a wrong commit.

**What is measured but does not explain it: changes 2 and 3.** Both were checked directly
against the corpus, read-only, $0
(`~/.cache/life-agent/m1/{q2011_retrieve_diff,q2011_probe_diff,q2011_mechanism}.py`):

| path | gold-carrying documents in the top-k | competitor's carriers |
|---|---|---|
| primary retrieval (R2's order, k=20) | 7 → **6** | 4 → 4 |
| corroborate probe (§6.9's order, k=20) | 9 → **8** | 4 → 4 |

Both declared orders cost the gold one distinct carrier and cost the competitor none. But **the
competitor is present under both orders** — retrieval order did not surface it, so it cannot be
what put a new candidate on the lattice. The mechanism of the carrier loss was isolated: of
q2-011's 59 deduped chunk texts, **20 are carried by more than one document**; the declared key
flips the *representing* document for 9 of them, and **2 of those 9 carry the gold**, at exact
score ties across their carriers. The text survives; the carrier identity changes. That is a
second-order effect on the same row's margin, and it is a real finding — if two documents carry
byte-identical text they are one attestation (§5), so which one represents it should be a no-op
downstream, and here it is not. It belongs to R6/§5 and needs its own checkpoint, not a patch
here.

### A fix considered, measured, and refused

The tempting move — choose a tie-break under which q2-011 comes out right — is overfitting to a
single borderline row and was ruled out before any number was looked at. The principled version
was to stop cutting inside a tie block at all, making the retrieved set invariant to *any*
tie-break rather than picking a favourable one. It was measured before it was proposed, over the
whole 104-question battery at k=20:

```
top-20 cut lands INSIDE a tie block: 9 of 104 (9%)
tie-block size at the cut: min 2  median 2  max 73
rows admitted if the whole block is kept: median 1, max 60  →  k would run 20..80
```

Cheap at the median, with a fat tail. It is refused anyway, on a stronger ground: **it would not
have saved q2-011.** That question's primary cut does not land in a tie (8.047630 vs 8.045824),
and the gold carrier it loses sits at rank 40 of 59 — far below the cut. The loss is the dedup
representative, not the cut. Measuring the proposed fix against the case it was invented for is
what killed it; proposing it first and measuring later would have shipped a change that fixed
nothing.

### What is claimed, and what is not

Claimed: run 10 fails both frozen criteria; the failure is one row; that row gained a wrong
leader; the tree carried four decision-path changes of which three are unwitnessed; the
best-supported cause is the pre-registered null-read fail-open, whose named risk this is.

Not claimed: that the cause is *proven*. Four changes in one tree cannot be separated by
argument, and this report does not try. Separating them costs gate runs, and which to run — and
whether the null-read fail-open takes the rollback its own pre-registration names — is a ruling,
not a decision to take here.

## DEVIATIONS (continued)

**3. Run 10 was fired as M1's reading and is not one.** The TREE gate I wrote checked that the
change under test was present and that the worktree was clean; it never checked that the
decision path was otherwise identical to run 9's. Three unrelated decision-path changes had
landed in the four days between the runs, two of them mine at M0.5/R2 and one merged from a
pre-registered branch. This is a defect in my own instrument, of the same family as DEVIATION 1
(§6.7) — the second time this checkpoint that a gate's *script* was the thing that needed
strengthening. Registered as §6.10 rather than fixed silently.

## REFUSED

- **No tie-break chosen to make q2-011 correct**, and no adjustment to δ, level, or the
  wrong-commit criterion. The pre-registration is the pre-registration.
- **No fix to the carrier-identity sensitivity here.** It is a real defect (§5's own principle
  says swapping the representative of a byte-identical attestation should be a no-op), but it is
  a different module and a different checkpoint, and bundling it is what produced this report.
- **No re-run fired.** Which separations to buy is a ruling; firing another priced run to chase
  an attribution before the reviewer has ruled would repeat the error this report documents.

## QUESTIONS

1. **Does the null-read fail-open take the rollback its own pre-registration names?** It
   pre-committed to "revert the commit — there is no env flag, and one must not be invented at
   read time", and its named risk has materialised. Against that: it also bought a correct
   commit, and one wrong row out of 104 is a thin basis for reverting a pre-registered change.
   The honest position is that its reading is contaminated by three other changes and it has not
   had a clean measurement.
2. **Which separated runs to buy, and in what order?** Cleanest is run 10's tree minus change 1
   (isolating R2+§6.9+M1), then minus 2 and 3. Each is ~$3–4 typed against the archived
   monolithic arm, which does not need re-firing.
3. **Does M1 pass on the strength of the splice?** With q2-011 withheld the tree reads 0.952 /
   +0.410 and M1's own oracle is 104/104 and 311/311. A defensible ruling is that M1 is green and
   the FAIL belongs to change 1. The counter-argument is that a splice is not a gate reading, and
   §6.7 says a gate is a script, not a sentence.
4. **Is the carrier-identity sensitivity in scope for R6, or does it need its own entry?**

## PROPOSED

Hold M1 at this report. Adopt §6.10 (the tree gate) so the next run is attributable at all, take
the ruling on Q1–Q3, and open the carrier-identity finding as its own register entry with
pre-registered criteria before anything is changed in `retrieval.py` or `probes.py`.

## RULINGS (owner, 2026-08-21 — taken on the QUESTIONS above, before any re-run)

1. **The null-read fail-open is HELD, not reverted.** Its pre-registered rollback clause
   presupposed a reading of *its* effect, and it has never had one — run 10 bundled it with three
   other decision-path changes. It also bought a correct commit. Measure it clean first; the
   rollback fires or is released on an attributable number.
2. **Buy one separated run.** Run 10's tree with the null-read change reverted, typed arm only
   against the archived monolithic arm (~$3–4). If that closes the attribution, no further runs
   are bought.
3. **M1 is HELD at this report.** The code stays landed — it is behaviour-preserving on the
   surviving lane, with 7.1 clean and 7.2 at 104/104 and 311/311 — but the checkpoint is not
   marked green until an attributable 7.3 exists. M1.5 does not open on a held checkpoint.
4. **The carrier-identity finding gets its own register entry and its own pre-registered
   criteria** before anything changes in `retrieval.py` or `probes.py`. It is not folded into R6
   and it is not patched here.
5. **Run 11's decision rule, frozen now and blind:** the null-read fail-open's rollback becomes
   permanent iff run 11 reads **wrong commits = 0 AND P(Δ>δ) ≥ 0.90** — the gate's own bar, both
   criteria, exactly M1's. Not a single sub-criterion, and not the behaviour of one row: reading
   one borderline row is how this checkpoint got into trouble.
6. **Pre-committed branch, blind:** if run 11 still fails with a wrong commit, the null-read
   change is exonerated and the ladder escalates to the next isolation (tree minus R2 and §6.9,
   ~$3–4). No re-diagnosis-by-argument at that point.
7. **§6.10 lands before run 11 fires.** Registering a rule and then not carrying it on the very
   next run is how a register rots — and the entry's own pin is the next gate run's report.
8. **The revert lives in a git worktree** (`run11-minus-nullread`, under the machine's standard
   worktrees root); master
   keeps the change until the reading rules on it. Nothing is reverted on the strength of a
   contaminated run.
