# r02-collapse — M0, the instrument — 2026-08-19

The first checkpoint of tranche 2 (the module collapse), built to the M0 session brief
against the design of record (`docs/module-collapse-design.md` at `5852e30`, signed Q1 (α),
Q3, Q6, Q8, Q10 with the two pre-M0 additions folded). M0 builds the behaviour-preservation
instrument and records the pre-collapse truth; **nothing on the decision path changes** —
every code change is additive (recorder taps, tests, one accepting surface).

Three things the reviewer should read before the section list. **The instrument works and is
hermetic**: replay needs no daemon, no credence engine, no API key and no corpus, because
the engine wire, the model calls and the §18.9 cache reads all ride in the fixture. **It
found two real defects on its first run**, both the same class — a tie resolved by an
unordered source: the duplicate-dedup tie-break is hash-order dependent (17.6% of the
battery reaches a different posterior for no reason but the interpreter's hash seed), and
tied BM25 scores come back from DuckDB in nondeterministic order, so two runs of one query
over one catalogue do not always retrieve the same set (§ DONE 7, both measured). And **I spent
money I said I would not, and
wrote three live stores I said I would not** — disclosed in full at DEVIATIONS 1, with the
seal that now makes those claims enforceable rather than asserted.

The baseline is therefore **partial and honestly so**: the traces that cost nothing are
recorded; the traces that require the priced lane are prepared as an owner-executed run.
**STOP** after this report; M1 is briefed from its review.

## STATE

```
$ git rev-parse HEAD
5852e30e5f85650476801c6fc9f434fc7c3aa1ed   # 5852e30 (master, pushed) — the design of record
$ git status --short
 M src/life_agent/bridge/server.py       M tests/test_brain.py
 M src/life_agent/core/decisions.py      M tests/test_bridge_server.py
 M src/life_agent/core/lookup.py         M tests/test_decisions.py
?? src/life_agent/collapse/             ?? tests/test_collapse_compare.py
?? scripts/collapse_record.py           ?? tests/test_collapse_record.py
?? scripts/collapse_replay.py           ?? tests/test_collapse_taps.py
$ env -u LIFE_AGENT_KB TMPDIR=$HOME/.cache/… uv run pytest -q --basetemp=… -p no:cacheprovider
2492 passed, 35 deselected in 147.68s (0:02:27)
exit=0
$ uv run ruff check src tests scripts
All checks passed!
$ LIFE_AGENT_KB=<kb> python3 .githooks/pii_check.py <every new and changed file>
guard exit=0
$ PYTHONHASHSEED=0 uv run python scripts/collapse_replay.py --checkpoint m0
102/102 fixtures replay identically
exit=0
$ curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8799/ready
200        # the answer-brain daemon, up for this checkpoint
```

New code: 1,208 lines under `src/life_agent/collapse/` + `scripts/collapse_{record,replay}.py`
(571), 713 lines of tests across three new files, plus the additive edits to `decisions.py`
(+58), `lookup.py` (+15) and `bridge/server.py`. Suite delta is entirely the new tests.

**The engines.** Credence skin: the pinned image
`ghcr.io/gfrmin/credence-skin@sha256:9014389500…c57f72`, protocol 1.12 — the digest matches
`brain._SKIN_PINNED` exactly, so the wire-shape checks are against what production uses.
Daemon: the julia answer-brain, up throughout.

**The recorded baseline.** `$LIFE_AGENT_KB/eval/collapse-fixtures/m0/` — 102 fixtures, 9.8 MB,
recorded from **this tree** (`tree_sha 5852e30…`) at `k=20`, deliberate on, grow lane off,
`PYTHONHASHSEED=0`, `allow_spend=false`, against snapshots of the five KB fold inputs.
**3 named absences** (a §18.9 derivation cold under the no-spend seal: q2-036, q2-043,
q2-095). Fixture counts by class, from `manifest.json`:

| class | fixtures | | class | fixtures |
|---|---:|---|---|---:|
| `trace:B-lookup` | 101 | | `outcome:committed` | 40 |
| `trace:seam` | 1 | | `outcome:withheld` | 62 |
| `terminal:report` | 40 | | `outcome:dispersed` | 58 |
| `terminal:abstain` | 59 | | `outcome:miss` | 3 |
| `terminal:hedge` | 1 | | **`posterior:two-equal-credences`** | **18** |
| `terminal:miss` | 2 | | `regime:full` · `policy:all-to-date` | 99 · 99 |
| `gate:executor_down` | 1 | | | |

**Coverage holes, named** (`coverage()` reports every declared class, empty ones included):
`terminal:report_scoped`, `terminal:ask_clarify`, `terminal:report(claims)`,
`trace:A-loop`, `trace:A-poster`, `trace:B-narrative`, `posterior:n_obs=0`,
`regime:terminals-only`, `regime:unavailable`, `policy:frozen-elicitations`.

Six of those close with the priced run (DEVIATIONS 2). Two close only when the collapse
reaches them and are holes *by construction* at M0, which is the honest reading rather than a
gap: `regime:terminals-only` and `regime:unavailable` are values **nothing writes yet** —
they are what M2/M5 make true, and the `seam` fixture carries their pre-registered direction.
`policy:frozen-elicitations` likewise is written by nothing until M3. Files touched: the
twelve above plus this report. Not committed — the prepared script is
`~/.cache/life-agent/r02-collapse-m0-commit.sh` (`SIGN_M0=1`; one commit; owner executes;
push separate). **Rehearsed** in a throwaway worktree (S12): guard 0, `2492 passed`, ruff
clean, `102/102 fixtures replay identically`, then one commit of 17 files
(+3,282 / −2); transcript at `~/.cache/life-agent/collapse-m0/rehearsal.txt`.

## DONE

### 1. The fixture recorder, and the schema this phase defines

`src/life_agent/collapse/` — four modules, none of them imported by the decision path
(drift-gated, `tests/test_collapse_record.py`):

| module | what it is |
|---|---|
| `fixture.py` | the schema, the **field-class list**, the on-disk layout, `coverage()`, `manifest()` |
| `taps.py` | the four recording/replaying seams + the `Cassette` |
| `compare.py` | the comparator (pure: two recorded objects in, a list of `FieldDiff` out) |
| `drive.py` | one driver per trace, run by BOTH record and replay, plus the `sealed()` clamp |

**The schema.** One JSON file per fixture under
`$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>/` (M0-S1), plus a `manifest.json` and a
`snapshots/` directory:

```
fixture_id · checkpoint · trace · classes[] · question · question_id
inputs{}      the §7.2 ranked-over inputs, as recorded (hits, scope, k, run_id, the view …)
outputs{}     effector · asserted · candidates · credences · p_none · eu · gate ·
              regime · policy · log_decision{} (the full posted body) · audit{}
wire[]        the recorded seams, in order: {seam, request, response}
provenance{}  tree sha · recorded_at · skin image + protocol · engine_version ·
              snapshot shas · k · deliberate · grow_lane · PYTHONHASHSEED
expected_change   null, or {checkpoint, direction} where the design INTENDS a difference
```

**Five traces**, because the pre-collapse system does not have one decision path — it has the
two the design's §2.2 spends its table on, plus the two posters Q-O6 collapses into one:

| trace | what it pins | replayed by driving |
|---|---|---|
| `A-loop` | the executor path: the loop enacts the daemon's schedule, the reach surface posts | `ask_client.answer(post=…, get=…)` |
| `A-poster` | the OTHER pre-collapse poster (the CLI surface's), from a recorded view | `ask._log_executor_decision` |
| `B-lookup` | the in-process lookup leaf end to end: route → observe (the grounding gate) → posterior → EU decision → recorded answer + logged decision | `lookup.lookup_answer` |
| `B-narrative` | the `report(claims)` terminal's CONTENT — which claims the leaf included, at which credences (ruling Q9's coverage condition) | `narrative.narrative_answer` |
| `seam` | a commit with no engine available (§6.5) | `seam.commit(None, gates=…)` |

**Four tapped seams**, chosen as the boundary between the host (what the collapse moves) and
what the host does not compute: the credence engine's JSON-RPC wire, the bridge/daemon wire,
a cache-MISSING model call, and a §18.9 derivation read. The `Cassette` serves them back by
request — exact key first, then a **unique** numeric near-match within 1e-9 (a re-derived
float differing in the last ulp is not a behaviour change; an AMBIGUOUS near-match stays a
miss, because two exchanges that cannot be told apart cannot be replayed honestly). Identical
requests are a FIFO queue, so `create_state` answers a new state id per call.

Two design points worth the reviewer's eye. **The bridge runs in-process** (`server.dispatch`
against a `BridgeDeps` this phase builds), not over HTTP, so its own leaves — extraction's
grounding gate, the narrative leaf, the posterior build — sit INSIDE the recorded envelope
rather than behind an opaque socket; only the daemon stays a separate process, as the design
says it is. And **the KB folds are snapshotted per checkpoint** (`utility/model.yaml`,
`utility/elicitations.jsonl`, `calibration/{reactions,decisions,outcomes}.jsonl`): they grow
with every run, so a fixture that read them live would decay into unreplayability within a
day. Replaying over the snapshot also puts the utility fold itself under the comparator —
which is what M3 moves.

### 2. Coverage, pre-stated — and every hole named

`fixture.coverage()` returns **every declared class including the empty ones**, so a hole
cannot be silent; `manifest.json` publishes it and the recorder prints it. What the M0 set
reaches is at STATE; what it does not, and why, is DEVIATIONS 2.

### 3. `scripts/collapse_replay.py --checkpoint <id>`

Exit 0 iff every fixture replays to the same decision under the declared classes; exit 1 on
any mismatch, one line per differing field. A replay that cannot RUN is a failure, never a
skip. `--only` replays one fixture, `--verbose` prints the cassette notes (near-matches
served; exchanges replay never asked for — not failures, but the sort of thing a checkpoint's
report should say aloud). It refuses outright if the fixtures were recorded at a different
`PYTHONHASHSEED` than the replaying process (DONE 7).

**The comparator, per §7.2's signed field-class rule.** Every field of the `/log_decision`
body is declared exactly once:

* **value-compared** — `question`, `retrieval_keys`, and `decision.{effector, credences,
  candidates, p_none, eu, n_obs, n_indeterminate, n_competing, instrument, run_id, regime,
  policy}`; floats at 1e-9, credences in the one leader-first label view.
* **runtime-measured** — `decision.latency_s`, `decision.cost_usd`: compared by **presence
  and type only, never value**.
* **neither** → the diff reason is `unclassified`, which is a MISMATCH. A field the collapse
  adds must be classified at the checkpoint that adds it, never absorbed by a permissive
  comparator. The `audit` block is recorded and never compared (the render is a label view,
  D-4; comparing it would make a cosmetic string a behaviour change).

A field may move from measured to value-compared at a checkpoint, never the other way
(never-silently-weaken).

### 4. The `brain.value` wire-shape test (§2.5, ruling Q-R4)

`tests/test_brain.py::test_value_is_pinned_like_optimise_as_the_voi_wire_shape` pins
`value(state_id, actions, preference) -> float` with the preference shape the decision path
actually builds (the `functional_per_action` map `lookup.action_utilities` produces), and
asserts the request envelope carries exactly `{state_id, actions, preference}`. Deleting
`Brain.value` fails it. **The claim is therefore earned, not promised: §2.5's dormant-keep
stands and §6.4's condition is met.**

### 5. The Q4 / §6.3b procedure, executed — and the answer is not the binary the ruling assumed

The pre-committed procedure: draws exposed on the wire → `GATE._sample_u` becomes register
debt §6.3b with a short retirement path; not exposed → it stays inside §6.1's exception.
Checked against the **pinned production image**, not the dev tree:

```
skin image (pinned): ghcr.io/gfrmin/credence-skin@sha256:9014389500…c57f72
engine protocol: 1.12  version: 0.1.0
host surface: Brain has draw? False
engine methods (38): [… 'destroy_state', 'draw', 'enumerate', 'eu_interact', 'expect' …]
draw served by the engine: True
draw(beta)                    -> {"value": 0.2134855788792336}
draw(truncated_mv_gaussian)   -> BrainError: [-32603] MethodError: no method matching
                                 draw(::MvQuadraturePrevision)
draw(truncated_gaussian)      -> BrainError: [-32603] MethodError: no method matching
                                 draw(::TruncatedGaussianPrevision)
```

The verb is served and works on conjugate measures — and has **no method for either measure
the utility posterior actually folds into**: `truncated_gaussian` (an independent latent,
`utility._fold_1d`) or `truncated_mv_gaussian` (a coupled component, `utility._fold_joint`).
So P(U) **cannot** be sampled over the wire today, and `_sample_u`'s host moment-Gaussian
approximation is not a debt with a short retirement path — there is no path without a
cross-repo engine change.

**Decided, per the pre-committed procedure: G-3 stays inside §6.1's exception**, on the
"not exposed" branch read at the level that matters (the measure, not the verb). Left in as a
**tripwire** rather than a note: `test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures`
(system-marked, run live at M0 and green) asserts the two `MethodError`s. **If it ever fails
because a draw SUCCEEDED, the engine has gained the capability and the ruling flips** —
register §6.3b, add a `Brain.draw` wrapper, sample on the wire, delete G-3's coverage from
§6.1. The refinement is disclosed as QUESTIONS R1: the ruling's binary did not anticipate a
verb that exists but is unimplemented for the shape in question.

### 6. `/log_decision` accepts `regime` and `policy`, with honest defaults

Additive on the bridge (`_regime_and_policy`, `server.py`); the poster does not change (that
is M2). `DecisionEvent` is **v3**: `regime` (`full` | `terminals-only` | `unavailable`),
`policy` (`all-to-date` | `frozen-elicitations`), and `defaulted` — the names of the fields
the writer did not state. Both vocabularies are closed and fail at construction, the same
discipline `family` and `action_set` already carry; a value outside either is a 400 and
nothing is written.

`unavailable` is a REGIME and deliberately not an action: §6.5's point is that when no
optimiser is reachable there is no ranking to be inside of, and keeping the case out of
`ACTIONS` is what stops it folding as an abstain verdict (reactions §4.4 folds abstains as
utility evidence).

**`defaulted` defaults to "stated neither".** A v1/v2 line, and every family leaf until M2
folds their writes into the one poster, therefore *discloses its silence* rather than
claiming a regime it never declared — and no leaf had to be touched at M0 to make that true.
(The first cut had `_from_line` coerce a missing key to `()`, which turned silence into a
claim; caught by its own test, fixed, and the test now pins the legacy line.)

### 7. Instrument integrity — and the two defects the instrument found

The brief's gate-quality doctrine applied to the gate-builder: self-kill, contamination, and
determinism, each with its evidence — and, because the determinism check is what surfaced
them, the two findings that came out of it.

**Self-kill.** A comparator that has never failed is a green that cannot fail. Corrupting one
field of a recorded fixture and replaying it:

```
$ cp $KB/eval/collapse-fixtures/m0/m0-blookup-q2-001.json /tmp/…/m0-selfkill/
$ python - <<'PY'   # flip ONE field: decision.n_obs
…
$ uv run python scripts/collapse_replay.py --checkpoint m0 --fixtures …/m0-selfkill
m0-blookup-q2-001: 1 field(s) differ
    log_decision.decision.n_obs                  [value] recorded=2 replayed=1

0/1 fixtures replay identically  ·  mismatched: m0-blookup-q2-001
exit=1
```

The comparator's own kill list is unit-tested besides (`tests/test_collapse_compare.py`):
the swapped tie-break (M-10, two equal credences, pre-registered kill 1), an optional
accounting field (Q-O6 regressed), a policy swap, a regime swap, a changed value field, an
unclassified field, and the runtime-measured class in both directions (value ignored;
presence and type required).

**Recording must not contaminate the live ledgers — routed, not marked.** `drive.sealed()`
redirects every write off the live stores rather than tagging it afterwards: §18.9 records go
to a staging root, and `decisions.append` / `outcomes.append` are **sunk** to staging files.
Sinking the append (rather than the configured path) is load-bearing — see DEVIATIONS 1.
Evidence, four live fingerprints across a sealed run:

```
== live surfaces BEFORE                     == live surfaces AFTER
  calibration/decisions.jsonl   8e7ecfb5      calibration/decisions.jsonl   8e7ecfb5
  ledger/calibration.decisions  47228cb5      ledger/calibration.decisions  47228cb5
  pkm external/pending.txt      134810 B      pkm external/pending.txt      134810 B
  pkm cache directories         30682         pkm cache directories         30682
```

**Finding 1 of 2 — the duplicate-dedup tie-break (new; not caused by the collapse).**
`lookup.dedup_correlated` collapses a duplicate-quote cluster spanning several documents to
the max-covariate document, and breaks a **tie** with `max()` over a `set` of artefact keys
(`src/life_agent/core/lookup.py:806`). Set iteration order over strings depends on the
interpreter's per-process hash seed, so **which duplicate document survives — and therefore
which observations reach the posterior, which candidates exist, and in what order — varies
between two runs of the same code on the same corpus.** Measured directly:

```
$ for seed in 0 1 2 3 4; do PYTHONHASHSEED=$seed collapse_replay --only m0-blookup-q2-002; done
seed=0  1/1 fixtures replay identically
seed=1  1/1 fixtures replay identically
seed=2  0/1 fixtures replay identically  ·  errored: m0-blookup-q2-002
seed=3  0/1 fixtures replay identically  ·  errored: m0-blookup-q2-002
seed=4  0/1 fixtures replay identically  ·  errored: m0-blookup-q2-002

  (the error is a cassette MISS: the host asks the engine to condition a group whose
   reported candidate indices differ, because a different duplicate document survived)
```

Incidence over the recorded battery, replaying a seed-0 baseline at another seed:

```
$ PYTHONHASHSEED=2 collapse_replay --checkpoint m0   # a seed-0 baseline, other seed
84/102 fixtures replay identically  ·  errored: 18 fixtures

  18 / 102 = 17.6% of the recorded battery reaches a different posterior for no reason
  other than the interpreter's hash seed.
```

This is stronger than the semantic-determinism contract allows: it is not two encodings of
one answer, it is two different observation sets. It also means a gate reading's Δ is
seed-dependent for the affected fraction of the battery. **Not fixed here** — a tie-break is
decision-path behaviour, and the brief makes that a QUESTIONS item rather than a judgement
call (PROPOSED names M6 as its home, since D-11…D-15 are exactly "one function each" for
this class). Mitigated instead where it belongs, in the instrument: the seed is pinned,
recorded in every fixture's provenance, and the replayer **refuses** a seed mismatch rather
than comparing two different runs and calling it a regression.

**Finding 2 of 2 — retrieval order among tied scores. Determinism of recording: the
brief's criterion is NOT met, and the reason is this finding.** The criterion was "record one
fixture class twice; byte-identical, or every
differing field is on the signed runtime-measured list". Recording the same three questions
twice, at the same pinned seed:

```
$ collapse_record --ids q2-001,q2-011,q2-078 --traces B-lookup   (twice, same seed)
  m0-blookup-q2-001.json         differ in inputs
  m0-blookup-q2-011.json         differ in outputs, wire, inputs
  m0-blookup-q2-078.json         differ in inputs
```

The differing field is `inputs.hits` — the retrieval set — and where it differs the decision
can differ with it. Traced to the bottom:

```
$ search(conn, query, k=80) three times IN ONE PROCESS
n returned per call:      [80, 80, 80]
same SET of artefacts:    True
same ORDER:               False
first divergence at rank 1: ('ca7b9752', 31.960842) vs ('60a446e1', 31.960842)
distinct scores in the 80: 67          # i.e. 13 ties
```

**Tied BM25 scores come back from DuckDB's FTS in nondeterministic order.**
`retrieval.retrieve_set` over-fetches `4k`, dedupes by chunk text keeping the best score, and
takes the top-k with a *stable* sort — so tied rows keep whatever order the scan produced,
and **where a tie straddles the top-k cut, the retrieved SET changes between two runs of the
same query on the same catalogue**. Consequences beyond this checkpoint: every derivation
keyed on the retrieval set (synthesize; the executor's joint-extract chunk-set sha) can miss
on a re-run of a question already answered — which is precisely why so many of the priced
lane's derivations were found cold — and two gate runs over one corpus do not necessarily
rank over the same evidence.

So the honest statement is a distinction the brief's criterion did not draw:

* **replay is deterministic** — 102/102, because the fixture carries the view it was
  recorded with, which is exactly what §7.2 says a fixture is;
* **recording is not** — because retrieval upstream of the fixture is not. A fixture is a
  faithful record of ONE run, not a canonical function of its question.

That is sufficient for the instrument's purpose (the comparator compares decisions *given the
same view*), and it is not sufficient for anyone who assumed two recordings would agree. Both
findings here are the same class — **a tie resolved by an unordered source** — and they are
proposed together.

**Daemon status.** Up throughout (`GET :8799/ready` → 200, the julia answer-brain daemon
started for this checkpoint). The credence engine is the pinned image, spawned per run. The
`A-loop` trace nevertheless is not in the recorded set — for the reason at DEVIATIONS 2,
which is spend, not availability.

## DEVIATIONS

**1. I spent money I said I would not, and wrote three live stores I said I would not.**
The first baseline attempt (aborted after 6 questions) recorded `A-loop` against the live
stack under a no-spend claim that was false. I had gated `BridgeDeps.client` — the
schema-constrained instrument — and believed that was the model seam. It is one of six:
`joint_extract`, `rerank`, `expansion` and `synthesis` each reach Anthropic through their own
**import-bound** binding (`from life_agent.core.llm import anthropic_complete`), and
`/probe/deliberate` runs the agentic edge; none of them passes through `deps.client`. And
`derivations.record` takes the root as an *argument*, so the bridge's own handlers wrote the
LIVE pkm cache while I was tapping the caller's side.

Measured consequences, all evidence out of tree:

| what | amount | detail |
|---|---|---|
| spend | **≈ $0.58** | 24 `joint_extract` calls (haiku 7 / sonnet 9 / opus 8; 39,674 in-tok, 1,682 out-tok ⇒ $0.151 at `PRICE_TABLE` v1) · 1 `synthesize` (6,363 / 51 ⇒ ≤ $0.020, priced at sonnet as a ceiling — its served model is not in the metadata) · **1 cold `deliberate` whose own record carries `cost_usd` 0.410** |
| live pkm root | **27 artefacts** | ordinary content-addressed §18.9 derivations, write-once, the same keys a live ask would have produced; queued in `external/pending.txt` exactly as any ask's are, so the next reconcile registers them |
| live unified stream | **1 row** | `ledger/calibration.decisions.jsonl` seq 2443, family `narrative`, stamped `run_id: "ask"` |

The one leaked row is the instructive one. The bridge's `/narrative` handler appends its
decision with **no path argument**, so it fell through to `config.DECISIONS_LOG` — which my
first cut had redirected to the checkpoint's *snapshot* — and the C5 dual-write recognised
that as the configured path and mirrored it onto the owner's stream. The legacy
`calibration/decisions.jsonl` did **not** gain it (2,442 lines, sha unchanged), so
`stream − legacy` gained exactly one key. Note for the tranche-1 witnesses: A5's criteria
(i)/(ii)/(iii) are all taken *inside* the witness run, so a baseline already containing this
row does not break them — but r00/r03's description of the difference set is one member out
of date. Remediation is QUESTIONS O1; I did not touch an append-only stream unilaterally.

Fixed by `drive.sealed()`, which makes both claims enforceable instead of asserted: it names
every spend seam **by binding site** (checked against reality by a test, so a rename cannot
silently drop one), redirects `derivations.record` under staging, and **sinks** the decision
and outcome appends. Sinking rather than path-redirection is the lesson: a pathless writer
falls through to config, and sinking is also what makes the C5 mirror's own "not the
configured path" guard fire. Seven tests pin it, one of which reproduces the `/narrative`
fall-through exactly. The fingerprints at DONE 7 are the verification.

**2. The baseline is partial: `A-loop`, `A-poster` and `B-narrative` are not recorded.**
Not availability — the daemon was up. Cost. The executor path's decisions **are** the priced
lane: the daemon schedules corroborate / re-extract / deliberate probes, and their §18.9
derivations are cold for the current retrieval sets, so recording what the deployed arm
decides means paying for it (the aborted run's own numbers are the estimate: ~$0.10–0.15 a
question amortised, a full battery ≈ **$4–8**, next to run 9's own $4.10). Under the standing
discipline that is an owner-executed act, so it is prepared rather than taken:
`~/.cache/life-agent/collapse-m0-record-priced.sh` (`ALLOW_SPEND=1`, refuses without it,
prints the four live fingerprints before and after, writes to the `m0-priced` fixture set
beside this one).
The consequence for coverage: the priced-lane terminals, `report(claims)`, and the classes
that only the executor path reaches are holes in the M0 set, named at STATE.

**3. `B-lookup` fixtures use the cheap retrieval pass and EMPTY covariates.** Hits come from
`/retrieve` with `rerank=False, expand=False` (pure DuckDB, hence free — the grow lane is the
priced one), and `HitCovariates()` is empty, where `ask.answer` would project `doc_subject`
and `doc_date` first. Both are §7.2 **inputs**, not decisions, so the fixture still pins the
leaf as a function of what it was given; what it does not pin is ask.answer's covariate
projection policy. Worth closing before M5 (QUESTIONS O3).

**4. `A-loop` drives `ask_client.answer`, and the CLI surface's poster is pinned separately.**
`ask.answer_via_executor` binds its transport at module level, so it is not injectable; its
poster — the one that carries the §10 accounting fields the reach surface omits, which is
precisely Q-O6's asymmetry — is pinned as the `A-poster` trace from a recorded view. The two
together are what M2 turns into one function.

**5. `lookup.set_shared_brain` is new** — an additive instrument seam on a decision-path
module, needed because `narrative_answer` reaches the skin through `shared_brain()` rather
than a parameter. Two drift gates: only `collapse/drive.py` and `lookup.py` itself may name
it, and nothing outside `collapse/` may import the instrument.

**6. `DecisionEvent` is v3** (three fields, `FORMAT_VERSION` 2 → 3). A record change, not a
decision change: v1/v2 lines replay at the declared defaults and disclose that they stated
nothing.

**7. `k` defaults to 20 in the recorder** — the eval recipe's k, not ask's 8, so recorded
chunk sets hit warm derivations.

## REFUSED

* **7.3 (the eval battery) was not run.** M0 touches no decision path; §8's M0 row asks for
  7.1 and 7.2's baseline only. Running it would also have been a gate reading, which is not
  this checkpoint's to take.
* **Nothing in the collapse's path was changed** — E-14 stands, the cascade stands, the two
  posters stand, `gather_answer` stands. M0 is additive by construction.
* **Neither tie finding was fixed** (DONE 7): both are decision-path behaviour, and the brief
  makes a non-additive change a QUESTIONS item rather than a judgement call. Mitigated in the
  instrument (seed pinned and enforced), registered here, proposed for M1/M6.
* **The leaked stream row was not removed or rewritten** — append-only, and the owner's.
* **The live pkm root was not reconciled.** The 27 artefacts sit queued exactly as any ask's
  do; forcing a catalogue write to tidy my own mess is not mine to take, and the standing
  reconcile-or-refuse discipline picks them up on the next extract.
* **The priced baseline was not recorded by me** (DEVIATIONS 2).
* **The tranche-1 witnesses were not run.** The verified archive name
  (`travel-thinkpad-2026-08-19_16-37-53`) arrived during this session and unblocks
  `b2-live-witness.sh` and `a5-witness.sh`, then Q4/Q7 — all owner-executed, and all outside
  this brief.

## QUESTIONS

**Owner.**

* **O1 — the leaked ledger row.** Leave it documented here, or append a compensating record
  naming seq 2443 as instrument-origin (the C6 precedent: `void_deliberate_poison.py` wrote a
  void manifest for exactly this class)? I recommend the compensating record — the row is
  stamped `run_id: "ask"` and is otherwise indistinguishable from live traffic — and I have
  not written one.
* **O2 — sanction the priced baseline?** ≈ $4–8, script prepared, fingerprints printed either
  side. Without it, M1's `7.2` runs against B-trace fixtures only, which is *not* enough to
  see E-14 die: the cascade lives in the executor loop.
* **O3 — `B-lookup` covariates** (DEVIATIONS 3): extend the fixtures with the real
  `doc_subject`/`doc_date` projections before M5, or accept the narrower pin?

**Reviewer.**

* **R1 — the Q4 refinement.** The pre-committed binary did not anticipate a verb that exists
  but has no method for the measure in question. Executed as the "not exposed" branch, with a
  tripwire that flips it. Confirm the reading.
* **R2 — `defaulted` defaults to "stated neither"**, so the family leaves disclose their
  silence without being touched at M0. Confirm.
* **R3 — shallow replay for `A-loop`.** The cassette records the bridge's internal traffic
  too, but replay serves the bridge's *replies* and re-runs only the loop's host; the
  bridge's leaves are pinned by their own B-trace fixtures. Sufficient, or should A-loop
  replay re-run the bridge in-process (deep) from M1?
* **R4 — `cost_usd` is wholly runtime-measured** in the field-class list, where §7.2 says "on
  warm hits and wherever the price is realised at runtime". That is the wider reading;
  tightening it later is permitted, loosening is not, so it is the safe direction — but it is
  a choice, not a transcription.

## PROPOSED

**M1, as the design states it: E-14 dies** (with E-13; `LIFE_AGENT_GROW_LANE` retires and
gets its one config-doc line), instruments 7.1 + 7.2 with the pre-registered *direction* on
cascade fixtures + **7.3** (wrong commits must stay 0, answer rate reported, filed in the §14
ledger like runs 1–9).

Two things M1's brief should settle first, both consequences of this checkpoint:

1. **The priced baseline (O2)** — without `A-loop` fixtures there is nothing for the cascade's
   pre-registered direction to be asserted against.
2. **The two tie findings (DONE 7)**, which are one class and should be fixed as one: give
   every tie a declared total order. `dedup_correlated`'s survivor becomes the first-seen
   document at equal covariate (a two-line change), and `retrieve_set` sorts by
   `(-score, artifact_cache_key, chunk_text)` rather than relying on the scan's order. Either
   before M1 — with the baseline re-recorded, which also stops the priced lane's derivations
   going cold on every re-run — or carried on the pinned seed with a declared home at M6
   (D-11…D-15 are exactly "one function each" for this class). Neither is urgent for the
   *collapse's* correctness; both are live, measured non-reproducibility in the deployed
   decision path, and the §14 ledger is where that belongs. My recommendation is to fix them
   before the priced baseline is paid for, so it is recorded once against a reproducible path.

**STOP.**

## ADDENDUM — O2, the priced baseline (2026-08-20)

O2 was sanctioned and run after M0.5 settled retrieval, which is the order this report
recommended ("fix them before the priced baseline is paid for, so it is recorded once against
a reproducible path"). Recorded at `08d0f70`, seed 0, merged into the baseline of record.
This section is append-only; the figures below are the instrument's, not estimates, except
where explicitly labelled.

### B1 — what ran, and what it left behind

`A-loop`, `A-poster`, `B-narrative` over the 104-question battery, `--allow-spend`, the
deliberate edge on. **209 fixtures, zero named absences** — the three `WouldSpendError`
absences the free run recorded stay in the manifest as that run's, correctly, since they were
its absences and not this one's.

The seal held. All four live surfaces are byte-identical either side, which is the whole
claim `drive.sealed` makes:

```
== live surfaces BEFORE          == live surfaces AFTER
  decisions.jsonl  8e7ecfb5…       decisions.jsonl  8e7ecfb5…
  ledger/…decisions 47228cb5…      ledger/…decisions 47228cb5…
  pkm external/pending.txt 134810   pkm external/pending.txt 134810
  pkm cache directories 30682       pkm cache directories 30682
```

pkm's own transform telemetry has **no entry for the day**, which corroborates it from the
other side: the §18.9 derivations went to staging and the live root was never written.

### B2 — the merge, and the coverage it bought

102 → **311 fixtures**, and **311/311 replay identically**. Four declared coverage holes
close: `trace:A-loop`, `trace:A-poster`, `trace:B-narrative`, `posterior:n_obs=0`. Six remain
and are named in the manifest: `terminal:report_scoped`, `terminal:ask_clarify`,
`terminal:report(claims)`, `regime:terminals-only`, `regime:unavailable`,
`policy:frozen-elicitations`.

`posterior:n_obs=0` closing is worth a line of its own: 14 A-loop fixtures carry it. That
cluster is a live §14 open question whose measurement is pre-registered but not yet taken, and
it now has an oracle it did not have this morning — a probe that erases a grounded channel
would move these fixtures.

**`trace:B-narrative` "closes" on a single fixture, out of 104 questions.** The narrative leaf
is only recorded where the driver actually reached it, and it reached it once. The coverage
check cannot tell 1 from 104 — it reports a class as covered when the class is non-empty. This
is precisely the structural point M1.5 is scoped around (R7): *coverage is a declared quantity,
not an emergent one*, and "covered" is a weaker statement than it reads. M1.5 should treat
`trace:B-narrative` as a hole with one fixture in it, not as a closed row.

### B3 — what it cost, and the fact that the instrument cannot say

The script's own estimate was $4–8, from run 9's battery. The run made **87 live model calls**,
all of one prompt class (single-value extraction), across 15 of 104 questions. Every one of the
**82 `/probe/deliberate` calls was served warm** from §18.9 — the deliberate edge fired
throughout and paid nothing, because runs 6–9 had already computed those derivations against
the retrieval sets R2 made reproducible. Estimated spend from the recorded prompt sizes is
**≈ $0.05** (41k input, 2k output tokens; ~$0.75 had they all been opus-tier).

That figure is an *estimate*, and the reason it has to be is a gap in the instrument worth
naming: **the recorder does not meter spend at all.** No fixture carries a cost field; the
§7.2 field-class list has `cost_usd` as runtime-measured, but nothing writes it on this path;
pkm's telemetry correctly saw nothing because the writes were sunk. So the priced baseline
cannot state its own price from its own artefacts — the number above is reconstructed from
prompt lengths in the recorded wire, at an assumed tokens-per-character and an assumed tier.
This is §6.7's shape again (a claim nothing executes), and the cheap fix belongs with M1's
recorder work: sum the metered spend the instrument seam already returns, and stamp it on the
manifest. *Recommended, not taken here* — this checkpoint is closed.

The practical consequence for the programme is the pleasant one: a priced re-record against a
settled retrieval costs cents, not dollars, so re-recording the baseline is no longer an
expensive act. That changes what is affordable at M1.

### B4 — R6 re-checked against the new evidence, and it stands

The merged baseline now contains **326 `/probe/corroborate` calls**. A reader could reasonably
conclude the fourth unordered source (§6.9) is covered after all. It is not: **all 326 take the
handler's `reextract` branch**, which calls the joint extractor and never touches
`P.probe_corroborate`. The plain branch — the one carrying the two unordered ties — is reached
from the gather lane and from this endpoint only when `reextract` is falsy, and it was called
**zero** times. §6.9's disposition is unchanged and its premise is now verified rather than
asserted: the *endpoint* is exercised 326 times, the *function* not once.

### B5 — the merged manifest described only half its own set

`FX.manifest` carries one `provenance` block, so after the merge it read `tree_sha 986faf7`,
`allow_spend=false` over a set that is two-thirds `08d0f70`, `allow_spend=true`. Every fixture
stamps its own provenance and those are intact (102 + 209, verified by grouping the files), so
nothing was lost — but a manifest that summarises a two-recording set with one recording's
stamp is a claim its own directory contradicts, and the manifest is what a report quotes.
Fixed additively, without touching the fixture format: `provenance.merged_from` now lists each
constituent recording, **derived from the fixtures rather than asserted**, with a guard that
refuses if the set spans more than one hash seed and a check that the parts sum to
`n_fixtures`. Replay re-run after the edit: 311/311.

### B6 — provenance wart, stated rather than papered over

The priced fixtures stamp `tree_sha 08d0f70`; the free ones stamp `986faf7`. The two recording
trees are **byte-identical in `src/`, `tests/` and `scripts/`** — `git diff 986faf7 08d0f70`
touches five files, of which the two code files are R2's and were present as uncommitted
worktree state when the free half was recorded, and the other three are documentation. So the
differing stamp is a documentation delta, not a code one, and the merged set is a single-tree
recording in every sense the oracle cares about. Stated here so that a future bisection reading
two `tree_sha` values in one directory does not treat it as a finding.

### B7 — deviations

1. **A convenience oracle, again.** Splitting the corroborate calls by branch, I keyed on a
   `path` field the wire does not have (it records `url` and `payload`), and got "0 plain, 0
   reextract" — a clean, symmetric, entirely false answer. It was caught only because it
   contradicted a count of 326 taken moments earlier by different means. Same class as the
   addendum's A10.1 and now covered by §6.8: a reading produced outside the declared comparator
   is a defect even when it looks tidy. The corrected split is B4's.
2. **The merge was invoked once before the recording finished** and refused on its "no staged
   fixtures" gate, which is the gate working. Noted because the refusal is evidence: the gates
   were written before the sequence was run, not after it went wrong.
3. **`stamp-merged-provenance.sh` is a new instrument** written after the merge, not rehearsed
   beforehand, because the defect it fixes was only visible in the merged artefact. It is
   idempotent and its effect was verified by re-running the replay. Disclosed rather than
   presented as part of the planned sequence.

### B8 — O2, answered

**Sanctioned, run, and cheaper than estimated by two orders of magnitude.** M1's `7.2` now has
104 `A-loop` fixtures to assert the cascade's pre-registered direction against, which is what
this report said the checkpoint could not proceed without.

**STOP.** M1 opens on the brief, with the three amendments M0.5's second review names.
