# r02 — golden-replay harness — 2026-08-18

Phase 2 of the ledger-unification tranche 1: the golden-replay harness under
`src/life_agent/ledger/`, built and run **against the legacy stores first** (design §9), with
the segment store's §10 crash protocol built and demonstrated on synthetic segments. Owner
signatures S1–S6 and the reviewer's torn-tail correction are in force and cited below. No
§7 adapter and no migration writer exists yet (Phase 3); no dual-write hook is installed;
nothing parses a legacy store into a `UnifiedEvent`. Two-file rule of Phase 1 lifted for
this phase: the deliverables are the harness code + tests and this report. Not committed;
the commit series is prepared (PROPOSED). **STOP** after this report.

**S6 on the record, superseding one line of the r01 addendum.** The r01 addendum said the
"never truncation" choice was honoured physically and that "if the reviewer intended
physical removal-after-quarantine, that is a one-line change". S6 (quarantine permanence:
no path removes, rewrites or compacts quarantined bytes within this tranche) **supersedes
that line**: the implemented protocol — torn bytes stay in the segment, newline-terminated,
quarantine logical via manifest-listed byte ranges, `seq` = ordinal among parseable lines —
is the adopted form (the reviewer's own correction, carried verbatim in the Phase-2 brief),
and the store has no removal path at all (`store.py` — the manifest's `quarantine` list is
append-only; tests below assert it).

## STATE

```
$ git rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git status --short
?? docs/2026-08-agent-litsweep-dispositions.m   # not mine (r00 addendum 2); untouched
?? docs/unification/                              # r00, r01, r02
?? docs/unified-ledger-design.md                  # Phase 1 (adopted, uncommitted)
?? src/life_agent/ledger/                         # NEW: __init__.py schema.py store.py golden.py
?? tests/test_ledger_golden.py                    # NEW
?? tests/test_ledger_store.py                     # NEW
$ uv run ruff check src tests
All checks passed!
$ uv run mypy
Success: no issues found in 202 source files
$ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/life-agent/basetemp -p no:cacheprovider
2338 passed, 34 deselected in 135.63s (0:02:15)
exit=0
$ uv run python .githooks/pii_check.py --shapes-only src/life_agent/ledger/*.py tests/test_ledger_store.py tests/test_ledger_golden.py
exit=0
$ df -h /tmp
tmpfs           7.7G  2.3G  5.5G  29% /tmp
```

2338 = 2317 (r01 baseline) + 21 new (`test_ledger_store.py` 9, `test_ledger_golden.py` 12).
`--basetemp` is pinned to `~/.cache/life-agent/basetemp` (R9 / S2) — outside tree and KB. **The
`/tmp` quota has been cleared by the owner since r01** (29 % used now vs 80 % over-quota); the
pin stays regardless (test scratch never belongs in the KB). Files touched: the four package
files, two test files, this report. Nothing under `src/pkm`, `PRINCIPLES.md`, any SPEC, the
design doc, or `src/life_agent/core`.

**KB writes (S1) — exactly one subtree.** T0 = `20260818T085659Z`.

```
$ find $LIFE_AGENT_KB/ledger -maxdepth 3 | sort
$LIFE_AGENT_KB/ledger
$LIFE_AGENT_KB/ledger/golden
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z/{answers,cells,claude-verdicts,corrections,curves,demand,gather,gtd,labels,pkm-index,reactions,state-md,trips,utility-fold-version,utility-posterior}.json
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z/manifest.json
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z/work         # seeded working copies (see DEVIATIONS 5)
$ du -sh $LIFE_AGENT_KB/ledger/golden/*
69M	$LIFE_AGENT_KB/ledger/golden/20260818T085659Z
```

No live segment exists (none is created this phase); the crash fixtures ran on synthetic
segments under `~/.cache/life-agent/basetemp/crash-demo` and `tmp_path`.

## DONE

### The harness (design §9), as built

`src/life_agent/ledger/`: `schema.py` (`UnifiedEvent`, closed `source_id`/`author`/kernel
namespaces, canonical serialisation, `event_id = sha256(source_id, seq, record)` — S2/R11);
`store.py` (`LedgerStore`: one segment per source, `flock` per segment, whole-line append +
`flush` + `fsync`, the torn-tail protocol, loud reads outside quarantine, dense-`seq`
verification, idempotent re-append, temp+rename manifest); `golden.py` (A1–A14 as pure
functions `Paths -> comparator object`, `snapshot / replay / compare / julia-run / counts`, the
eight seeds, PII-safe locator diffs). CLI exactly as §9 states it:

```
uv run python -m life_agent.ledger.golden snapshot [all|<artefact>] --t0 <T0>
uv run python -m life_agent.ledger.golden replay   [all|<artefact>]
uv run python -m life_agent.ledger.golden compare  [all|<artefact>] --t0 <T0> [--seed-defect <name>]
uv run python -m life_agent.ledger.golden julia-run --t0 <T0>
uv run python -m life_agent.ledger.golden counts
```

Every `compare` line prints: kind, the comparator's name, snapshot and replay sizes and
digests, `GREEN`/`RED`, and on RED the first differing **locators** — hex ids pass through,
any other key is redacted to a digest, values are never printed (transcripts land in this
public repo). Exit code is 1 on any RED.

### 1. Two-route counts (T0)

```
$ uv run python -m life_agent.ledger.golden counts
act.tasks                  raw_newlines=300   nonempty=300   parsed=300
act.trips                  raw_newlines=339   nonempty=339   parsed=339
calibration.claude_verdicts raw_newlines=180  nonempty=180   parsed=180
calibration.corrections    exists=false
calibration.decisions      raw_newlines=2434  nonempty=2434  parsed=2434
calibration.gather_outcomes raw_newlines=64   nonempty=64    parsed=64
calibration.outcomes       raw_newlines=905   nonempty=905   parsed=905
calibration.reactions      raw_newlines=14    nonempty=14    parsed=14
eval.labels                raw_newlines=21    nonempty=21    parsed=21
utility.elicitations       raw_newlines=5     nonempty=5     parsed=5
pkm.artifact               meta_json_files=32394
pkm.demand                 lines=103875
```

(Verbatim JSON in the run log; condensed here one source per line. Per-file `sha256`s are in
`manifest.json`.) Route (i) the reader's parsed count and route (ii) the raw line count agree
on every source: **no unparseable and no blank lines in any legacy store at T0** — the C0
manifest counts for Phase 3 will be zero for every JSONL source. `calibration.corrections`
does not exist yet (A14 snapshot = 0 lines).

### 2. Green baseline — snapshot → compare, all fourteen artefacts

```
$ uv run python -m life_agent.ledger.golden snapshot all --t0 20260818T085659Z
snapshot gtd                    kind=semantic  rows=151       digest=7edd5b2650b1f00b
snapshot state-md               kind=byte      bytes=9960     digest=1437513a74d91798
snapshot trips                  kind=semantic  rows=323       digest=de87ba10010fd8a5
snapshot utility-fold-version   kind=byte      -              digest=912f2b646befcc20
snapshot curves                 kind=byte      -              digest=88860b52869c2eff
snapshot reactions              kind=byte      evidence=11    digest=29144d76b72c6220
snapshot claude-verdicts        kind=byte      -              digest=6e13aff5f2e458ed
snapshot gather                 kind=byte      -              digest=2b88b2978730877f
snapshot cells                  kind=byte      -              digest=96c42b28f8a06108
snapshot answers                kind=identity  keys=832       digest=5fa6dcf822d5891c
snapshot pkm-index              kind=semantic  artifacts=32394 digest=3f0df1fedc026802
snapshot demand                 kind=byte      -              digest=65fcfbdced12fc1c
snapshot labels                 kind=byte      labels=21      digest=88e845f18720a57c
snapshot corrections            kind=byte      lines=0        digest=f1014797bf17aa8f
snapshot dir $LIFE_AGENT_KB/ledger/golden/20260818T085659Z
real	0m13.315s
exit=0
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z
compare  gtd                    kind=semantic  comparator=<multiset of rows ignoring id> snapshot[rows=151 7edd5b2650b1] replay[rows=151 7edd5b2650b1] → GREEN
compare  state-md               kind=byte      comparator=<byte-identical text> snapshot[bytes=9960 1437513a74d9] replay[bytes=9960 1437513a74d9] → GREEN
compare  trips                  kind=semantic  comparator=<multiset of full rows> snapshot[rows=323 de87ba10010f] replay[rows=323 de87ba10010f] → GREEN
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 912f2b646bef] replay[- 912f2b646bef] → GREEN
compare  curves                 kind=byte      comparator=<canonical JSON of {edge: bin_reliability}> snapshot[- 88860b52869c] replay[- 88860b52869c] → GREEN
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=11 29144d76b72c] replay[evidence=11 29144d76b72c] → GREEN
compare  claude-verdicts        kind=byte      comparator=<canonical JSON of latest_by_decision> snapshot[- 6e13aff5f2e4] replay[- 6e13aff5f2e4] → GREEN
compare  gather                 kind=byte      comparator=<canonical JSON of grow_block> snapshot[- 2b88b2978730] replay[- 2b88b2978730] → GREEN
compare  cells                  kind=byte      comparator=<canonical JSON of cell observations + coverage list> snapshot[- 96c42b28f8a0] replay[- 96c42b28f8a0] → GREEN
compare  answers                kind=identity  comparator=<key set + content/meta digests> snapshot[keys=832 5fa6dcf822d5] replay[keys=832 5fa6dcf822d5] → GREEN
compare  pkm-index              kind=semantic  comparator=<rowset equality of artifacts + artifact_lineage> snapshot[artifacts=32394 3f0df1fedc02] replay[artifacts=32394 3f0df1fedc02] → GREEN
compare  demand                 kind=byte      comparator=<multiset of canonical lines per file> snapshot[- 65fcfbdced12] replay[- 65fcfbdced12] → GREEN
compare  labels                 kind=byte      comparator=<ordered label lines + last-wins table> snapshot[labels=21 88e845f18720] replay[labels=21 88e845f18720] → GREEN
compare  corrections            kind=byte      comparator=<multiset of canonical lines> snapshot[lines=0 f1014797bf17] replay[lines=0 f1014797bf17] → GREEN
real	0m8.781s
exit=0
```

Per-artefact mapping to §9: A1 `gtd` semantic (R2/S4, columns `identity, user_id, text,
list, due_date, is_today, origin, created_at, completed_at`, `id` ignored); A2 `state-md` byte
(R1, sha over the ledger's bytes); A3 `trips` semantic (R10); A4a `utility-fold-version` byte
(R3); A5 `curves`; A6 `reactions`; A7 `claude-verdicts`; A8 `gather`; A9 `cells`; A10
`answers` identity+digests (R5; 832 decision-referenced keys, all present on disk); A11
`pkm-index` semantic (32 394 `artifacts` rows, 73 055 lineage rows — the numbers the
substitute-artifact first run exposed, below); A12 `demand` (R6; 103 875 lines across the
UTC-day files); A13 `labels`; A14 `corrections`.

### 3. A4b — the single Julia run (S3), digest and protocol verbatim

```
$ uv run python -m life_agent.ledger.golden julia-run --t0 20260818T085659Z
julia    image=ghcr.io/gfrmin/credence-skin@sha256:90143895001d20b4abee7f5354ba87950545f5b1990eea0269293091a7c57f72 protocol_major=1
julia    server={"methods": ["initialize", "shutdown", "create_state", "destroy_state", "snapshot_state", "restore_state", "condition", "condition_on_event", "weights", "mean", "expect", "optimise", "value", "marginal", "read_params", "draw", "enumerate", "perturb_grammar", "add_programs", "sync_prune", "sync_truncate", "top_grammars", "belief_summary", "condition_and_prune", "eu_interact", "call_dsl", "factor", "replace_factor", "n_factors", "structure_bma", "structure_observe", "structure_decide", "routing_init", "routing_decide", "routing_escalate", "routing_outcome", "routing_belief", "destroy_routing"], "protocol": "1.12", "version": "0.1.0"}
compare  utility-posterior      kind=julia     comparator=<exact equality of u_bar and per-latent params> fold_version=70d72c6a0b6aa23b n_events=16 u_bar={"kappa_att": 0.03387855333671105, "lambda_int": 1.0000000000000078, "lambda_usd": 1.3310810811034355, "u_abstain": 0.0, "u_correct": 1.0, "u_hedged": 0.3997510335985348, "u_wrong": -8.830114182620882, "u_wrong_scoped": -2.000000000292678} → GREEN
note     this snapshot is the first credence→proplang parity datum (R3)
real	1m18.742s
exit=0
```

One `docker run` (podman-emulated) of the pinned image; the skin's `initialize` reply is
recorded above (protocol 1.12, server version 0.1.0). Snapshot and replay were both computed
*inside that one session* (`julia_run` in `golden.py`) — see DEVIATIONS 3 for why the
Phase-2 comparison is degenerate by construction and where the datum bites. The stored
`utility-posterior.json` (u_bar + per-latent `mean/variance/lo/hi`, `fold_version`
`70d72c6a…`, `n_events` 16 = 5 elicitations + 11 folded reactions) is **the first
credence→proplang parity datum**, labelled as such in the transcript. `fold_version` here
equals A4a's stored value (the `912f…` in the A4a compare line is the digest of the whole
comparator object, not the fold_version).

### 4. The four kill categories — red transcripts and the criteria killed

Run against the T0 snapshot; GREEN rows filtered from the transcript for brevity, the seed
line, every RED row and the verdict line kept verbatim. Locators only: `~sha256:…` is a
redacted key, `[i]` a list index, `a→b` snapshot→replay digests.

**Kill 1 — reordered per-source event.**

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect reorder-reactions
seed     reorder-reactions (kill-1 reorder); §9 must kill: reactions, utility-fold-version
compare  utility-fold-version   … snapshot[- 912f2b646bef] replay[- cc1cf7e08af7] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→ad7bc4e4c5]
compare  reactions              … snapshot[evidence=11 29144d76b72c] replay[evidence=11 f1e29525caac] → RED  diff@ ~sha256:ee8250fb76e0[[0] 027826753e→85a1b21db3,[1] 85a1b21db3→027826753e]
verdict  killed=['utility-fold-version', 'reactions'] claimed=['reactions', 'utility-fold-version'] CLAIM MET
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect reorder-tasks
seed     reorder-tasks (kill-1 reorder); §9 must kill: gtd, state-md
compare  gtd                    … snapshot[rows=151 7edd5b2650b1] replay[rows=151 00b3b2ca6d1c] → RED  diff@ ~sha256:bc51e9e65d79[[26] ba6ff9463f→080ad87b7d]
compare  state-md               … snapshot[bytes=9960 1437513a74d9] replay[bytes=9961 516e2f886eee] → RED  diff@ ~sha256:982d9e3eb996[cac3d1d2d5→37172ac368]
verdict  killed=['gtd', 'state-md'] claimed=['gtd', 'state-md'] CLAIM MET
exit=1
```

The reactions swap exchanged the two verdicts of one folded decision (different valences —
`latest per (decision_id, kind)` flips), moving the folded evidence at positions 0/1 and the
`fold_version`. The tasks swap exchanged the first two events of one identity (an `amended`
now precedes its `asserted`), which changes one read-model row (`[26]`) and one byte of the
rendered state document.

**Kill 2 — dropped event.**

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect drop-task-disposed
seed     drop-task-disposed (kill-2 drop); §9 must kill: gtd, state-md
compare  gtd                    … snapshot[rows=151 7edd5b2650b1] replay[rows=152 10d4e73c54d2] → RED  diff@ ~sha256:bc51e9e65d79[len 151→152,[86] fc04b255fd→ecff65b276,[87] 0a36f0bf55→fc04b255fd]
compare  state-md               … snapshot[bytes=9960 1437513a74d9] replay[bytes=9945 1b90cd57b3f7] → RED  diff@ ~sha256:982d9e3eb996[cac3d1d2d5→0234dabd25]
verdict  killed=['gtd', 'state-md'] claimed=['gtd', 'state-md'] CLAIM MET
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect drop-edge-outcome
seed     drop-edge-outcome (kill-2 drop); §9 must kill: curves
compare  curves                 … snapshot[- 88860b52869c] replay[- a15f44104310] → RED  diff@ ~sha256:ba27dd05387c[~sha256:437197a015ef[[9] 4e42f64b33→d8ac0159dc]]
verdict  killed=['curves'] claimed=['curves'] CLAIM MET
exit=1
```

The dropped disposal resurrects one task (151→152 rows); the dropped last `eval_edge` row
(in force by construction — the latest for its lineage) moves one edge's top bin (`[9]`).

**Kill 3 — substituted draw.** *First run — a finding (harness, not criterion):*

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect substitute-artifact
seed     substitute-artifact (kill-3 substitute); §9 must kill: answers
compare  answers                … snapshot[keys=832 5fa6dcf822d5] replay[keys=832 f1df99c4a8ee] → RED  diff@ ~sha256:48a53f0774c8[~0018599a76432bc4b58e3216ad6aba72bf5437cddd64590e6038ca1ae021988b[~sha256:656484a17acd[d08507bf67→9f83256235]]]
compare  pkm-index              … snapshot[artifacts=32394 3f0df1fedc02] replay[artifacts=832 10cce0d2cb28] → RED  diff@ ~sha256:0f50505ce224[len 32394→832,…]; ~sha256:0713f136ea31[len 73055→1429,…]
compare  demand                 … snapshot[- 65fcfbdced12] replay[- a366d5315457] → RED  diff@ ~sha256:3d7db37d08f9[-sha256:086913304a59,-sha256:d48f38e4911d,-sha256:450124f9f4ad]
verdict  killed=['answers', 'pkm-index', 'demand'] claimed=['answers'] CLAIM MET
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect substitute-decision
seed substitute-decision: joined decision has no credences — cannot seed
exit=1
```

Two discrepancies, both in the **seeding mechanism**, neither in a criterion: (i) the artefact
seed redirected the whole `pkm_root` at a work copy holding only the 832 referenced artefact
directories, so A11 (32 394→832 rows) and A12 (no demand files in the copy) went red as
*collateral* — the claim was met but the kill was wider than claimed; (ii) the decision seed
assumed the first folded reaction joins a *lookup* decision (`credences`), but it joins a
*narrative* one (`marginal_credence`), so it refused to seed. Fixed in `golden.py`: `Paths`
gains `answers_root` (A10 reads it; defaults to `pkm_root`) and only that is redirected; the
decision seed handles both families. *Re-run, transcript:*

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect substitute-artifact
seed     substitute-artifact (kill-3 substitute); §9 must kill: answers
compare  answers                … snapshot[keys=832 5fa6dcf822d5] replay[keys=832 f1df99c4a8ee] → RED  diff@ ~sha256:48a53f0774c8[~0018599a76432bc4b58e3216ad6aba72bf5437cddd64590e6038ca1ae021988b[~sha256:656484a17acd[d08507bf67→9f83256235]]]
verdict  killed=['answers'] claimed=['answers'] CLAIM MET
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect substitute-decision
seed     substitute-decision (kill-3 substitute); §9 must kill: utility-fold-version, reactions
compare  utility-fold-version   … snapshot[- 912f2b646bef] replay[- f7e1003fcf08] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→6d216b3356]
compare  reactions              … snapshot[evidence=11 29144d76b72c] replay[evidence=11 4b341ac628a1] → RED  diff@ ~sha256:ee8250fb76e0[[2] 4bef705ef2→a99a2fbf78]
verdict  killed=['utility-fold-version', 'reactions'] claimed=['utility-fold-version', 'reactions'] CLAIM MET
exit=1
```

One flipped byte in one referenced artefact's content changes exactly that key's
`content_sha256` (the pointed-at hex key is printed — it is an artefact identity, not a
value); one halved `marginal_credence` moves one folded `MarginReaction` (`[2]`) and the
`fold_version`.

**Kill 4 — cross-source `decision_id` retarget.**

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect retarget-reaction
seed     retarget-reaction (kill-4 retarget); §9 must kill: reactions, utility-fold-version
compare  utility-fold-version   … snapshot[- 912f2b646bef] replay[- ca98e6f83d31] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→479bfe0213]; ~sha256:9a3b074b5040[b17ef6d19c→e629fa6598]
compare  reactions              … snapshot[evidence=11 29144d76b72c] replay[evidence=10 cfc4c752bcee] → RED  diff@ ~sha256:ee8250fb76e0[len 11→10,[0] 027826753e→85a1b21db3,[1] 85a1b21db3→4bef705ef2]
verdict  killed=['utility-fold-version', 'reactions'] claimed=['reactions', 'utility-fold-version'] CLAIM MET
exit=1
```

Repointing one folded reaction at a different existing decision drops one folded evidence
row (11→10; the target decision was already carrying a later verdict) and moves the
`fold_version` — the join is alarmed where it must alarm.

**Summary of claims vs kills:** eight seeded runs; every §9 "must kill" met; one seed killed
wider than claimed on its first run (harness collateral, fixed, re-run exact) and one could
not seed on its first run (harness assumption, fixed, re-run exact). No criterion was
strengthened or weakened.

### 5. The pinned-invariance fixture — green

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect unrouted-reaction
seed     unrouted-reaction (invariance); §9 must kill: (invariance: must stay green)
verdict  invariance fixture: GREEN as required
exit=0
```

An appended reaction whose `decision_id` (`ab-` + 32 zeros) matches no decision leaves every
one of the fourteen artefacts identical — the join is inert where it must be inert.
Classified as invariance, not kill (`Seed.category == "invariance"`; the harness asserts
all-green rather than a kill).

### 6. The crash fixtures — the §10 torn-tail protocol on synthetic segments

Unit tests (`tests/test_ledger_store.py`, 9 tests, all green): torn unterminated tail →
quarantined (manifest entry with segment, byte offset, length, bytes hex, detected-at,
reason), newline-terminated, segment bytes untouched, ordinal reused, `event_id` equal to
the canonical line's, reader loud before the writer opens and silent inside the quarantined
range after, idempotent re-append; terminated-but-unparseable tail quarantined too; two
successive tears → two permanent entries, additive manifest writes preserve them (S6);
foreign `source_id` in a segment is a read error; unlisted garbage is loud. Demonstration
transcript on a synthetic segment (`~/.cache/life-agent/basetemp/crash-demo`, R9):

```
after crash : bytes=775 tail=b'{"author":"owner","event_id":"6'
reader loud : calibration.reactions.jsonl: physical line 3 at byte 744: unterminated tail (open the writer to quarantine it)
parseable   : 2 next_seq: 3
append seq 3: True
manifest quarantine entry: {"byte_offset": 744, "bytes_hex": "7b22617574686f72223a226f...", "detected_at": "2026-08-18T09:02:37.416076+00:00", "length": 31, "reason": "unterminated", "segment": "calibration.reactions.jsonl"}
segment     : starts with before+torn+'\n' = True | bytes untouched (S6)
read        : [1, 2, 3] | event_id[3] == canonical: True
re-append 3 : False (idempotent, dedup on event_id)
MANIFEST.json: {"epoch": null, "format_version": 1, "sources": {}} quarantine_entries=1
```

### 7. Test evidence for the harness itself

`tests/test_ledger_golden.py` (12 tests) drives the harness over a **fully synthetic KB**
(tasks/trips ledgers, decisions/reactions/outcomes/Claude-verdict/gather/corrections/labels
logs, the example utility model, one synthetic §18.9 artefact and one demand line): baseline
green and no record value in the output (a marker string planted in a task text, a label
value and a correction claim must never appear); every non-invariance seed kills exactly its
`must_kill` set (`CLAIM MET`); the invariance seed stays green; the two-route counts agree;
**seeds never touch the legacy files** (byte-equal before/after every seed); CLI smoke.

## DEVIATIONS

1. **"Print its comparator inputs"** (Phase-2 item 1) is realised as **PII-safe locators**
   (kind, comparator name, sizes, digests, first differing keys with non-id keys redacted to
   digests). Printing the inputs themselves would put record values (task text, answers)
   into transcripts that land in the public repo. The full inputs are on disk in the
   snapshot files under `$LIFE_AGENT_KB/ledger/golden/<T0>/`. Flagged for the reviewer
   (QUESTIONS 6).
2. **A13 labels — comparator restated.** §9 says "canonical JSON of `verdict(labels, q, v)`
   over every `(question_id, value)`"; `scripts/answer_labels.verdict` depends on the
   scripts-path module `eval_grading` (token-containment matcher), which `src/` cannot import
   cleanly. The harness stores the ordered label lines **plus** the last-wins verdict per
   `(question_id, norm(value))` with the exact-norm key. Strictly stronger than stated (any
   change `verdict()` could observe changes the ordered list), not weaker; flagged (Q7).
3. **A4b in Phase 2 is degenerate by construction.** Snapshot and replay are both computed
   from the legacy stores inside one skin session, so GREEN there says only "the fold is
   deterministic within a session". The datum that matters is the stored
   `utility-posterior.json`; Phase 3's replay of the stream through the skin against it is
   the R3 comparison proper (and requires a second `docker run` — QUESTIONS 1).
4. **A10 stores digests, not bytes.** §9 says content and `meta.json` "equal on disk"; the
   harness compares `sha256` of each (equivalent for equality) so the snapshot holds no
   answer bytes. A11 is computed by the same pure functions `rebuild_artifacts` uses
   (`_iter_meta_files`, `_meta_to_row`, `_read_lineage`), skipping the same malformed metas
   it would skip; the live catalogue is never opened. A9 stores the raw per-cell observation
   lists and coverage list (the Bernoulli conditioning is exchangeable, so the lists are the
   sufficient input); the Beta parameters are not recomputed (that needs the skin).
5. **Working copies of real ledgers under `golden/<T0>/work/<seed>/`** — the seeds copy the
   affected legacy files (and, for the artefact seed, the 832 referenced artefact directories)
   into the S1 subtree and mutate the copies; the legacy stores are untouched (tested). 69 MB
   sits there now. Whether `work/` should be removed after each run is QUESTIONS 2.
6. **Two harness findings, stated as such** (DONE 4): the substitute-artifact seed's collateral
   kill of A11/A12 and the substitute-decision seed's narrative-join refusal. Both were
   defects of the seeding mechanism; both fixed; both first-run transcripts kept above. No
   criterion changed.
7. **A4b runs also went to `~/.cache/life-agent/basetemp`?** No — only the crash demo and
   pytest scratch live there; the Julia run wrote only `utility-posterior.json` under the KB.
8. **`created_at`** stays in A1's comparator (S4); the reorder/drop kills confirm it is
   fold-determined (rows moved with events, never with wall-clock).
9. Commit series prepared, **not committed** (owner commits on request): see PROPOSED.

## REFUSED

- No §7 adapters, no migration writer, no dual-write hook, no live segment (Phase 3).
- No pkm code, SPEC, PRINCIPLES, brain-seam, or design-doc change.
- No KB write outside `$LIFE_AGENT_KB/ledger/golden/<T0>/` (S1); no KB read beyond
  read-only replay of the legacy stores (+ the utility model, a config input).
- No push; no commit.
- The `docs/2026-08-agent-litsweep-dispositions.m` file left untouched (not mine).

## QUESTIONS

**Owner signature:**

1. **Phase 3's Julia run.** S3 authorised one `docker run` "for the A4b golden comparison
   only"; that run has been spent on the snapshot side. The Phase-3 comparison (stream fold
   → skin → compare against `utility-posterior.json`) needs one more. Authorise it now, or
   at r03?
2. **`golden/<T0>/work/`** — the seeded working copies (real ledgers, mutated) under the S1
   subtree: keep (audit trail of the kill runs), or have the harness remove them at the end
   of each seeded compare (a scratch deletion, not a ledger deletion)?
3. **Commit series** (prepared, uncommitted; the Phase-0/1 deliverables are also still
   untracked): see PROPOSED — sign to commit, or leave for the tranche end.

**Reviewer ruling:**

4. **Kill breadth.** Is "killed a superset of the claim" (the first substitute-artifact run)
   acceptable as a passing kill, or must the kill set equal the claim exactly (as the fixed
   seed now does)? The harness's `CLAIM MET` accepts supersets; the transcript shows both.
5. **The invariance fixture's strength.** One unrouted reaction is seeded; should the fixture
   also seed an unrouted Claude verdict (A7's `latest_by_decision` would *change* — it keys on
   `decision_id` regardless of routing — so that is not an invariance for A7; it would need
   to be a kill of A7 or excluded from the fixture)?
6. **DEVIATIONS 1** — locators in lieu of printed inputs: acceptable as the standing form?
7. **DEVIATIONS 2** — the A13 restatement (ordered lines + exact-norm last-wins) accepted as
   the pre-stated comparator going forward?
8. **A11's row form.** The rowset compares `_meta_to_row` tuples with `produced_at` rendered
   `str(datetime)`; Phase 3's adapter must produce the identical rendering from
   `record.meta.produced_at` — a formatting contract worth stating in §9 now (one line) so
   the Phase-3 comparison cannot go red on a timestamp spelling.

## PROPOSED

Prepared commit series (bisectable; each green on the whole suite; not executed):

1. `feat(ledger): unified event schema + segment store with the §10 durability contract` —
   `src/life_agent/ledger/{__init__,schema,store}.py`, `tests/test_ledger_store.py`.
2. `feat(ledger): golden-replay harness (§9) — snapshot/replay/compare, seeds, julia-run, counts` —
   `src/life_agent/ledger/golden.py`, `tests/test_ledger_golden.py`.
3. `docs(unification): design doc + r00–r02` — `docs/unified-ledger-design.md`,
   `docs/unification/reports/{r00-census,r01-design,r02-harness}.md`.

On review of r02 (and rulings on Q1–Q8): open Phase 3 — the migration writer (C0–C2 in the
design's order, `act.tasks` first), the §7 adapters (C3), harness re-pointed at the stream
(C4, incl. the second Julia run if authorised), dual-write hooks + sweeps (C5), two-route
count (C6), `r03-merge.md`. STOP.
