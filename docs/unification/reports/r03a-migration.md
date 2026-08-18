# r03a — migration → adapters → stream-green — 2026-08-18

Phase 3 of the ledger-unification tranche 1, checkpoints **C0–C4** (design §8), stopped at the
mandatory mid-phase STOP before any live writer is touched. Owner signatures **S7–S10** and
reviewer rulings **V4–V8** are in force and cited below; the tranche refusal list stands as
amended by S1. Delivered: the design-doc §9 revision (V4/V5/V8), the harness additions (the
fifth kill, the `EXACT`/`SUPERSET` verdict flag, the S8 work-directory lifecycle, the
`--from stream` route, the S7 Julia run), the per-source legacy parsers, the migration writer /
sweeps / two-route counts, the §7 adapters, and — on the real stores — a migrated unified
stream under `$LIFE_AGENT_KB/ledger/` from which **all fourteen §9 artefacts replay green**,
the **R3 comparison proper green** through the pinned skin, and **all five kills + both
fixtures re-demonstrated from the stream**. **No dual-write hook exists; no live writer
touches the stream; no scheduler is installed** (C5 opens only on review of this report).
Not committed (S9's precondition was not met at session start — DEVIATIONS 1); the checkpoint
series is prepared (PROPOSED). **STOP** after this report.

## STATE

(Transcripts throughout use `$LIFE_AGENT_KB`, `$REPO`, `$HOME`, `$WORKTREES` in place of the machine's absolute paths — V6.)

```
$ git rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git status --short
 M tests/conftest.py
?? docs/research/
?? docs/unification/
?? docs/unified-ledger-design.md
?? src/life_agent/ledger/
?? tests/test_ledger_adapters.py
?? tests/test_ledger_golden.py
?? tests/test_ledger_migrate.py
?? tests/test_ledger_store.py
$ git worktree list
$REPO                                         873860a [master]
$HOME/.cache/life-agent-census/wt              873860a (detached HEAD)
$WORKTREES/life-agent/null-read-failopen      04e8a71 [fix/null-read-failopen]
$ uv run ruff check src tests
All checks passed!
$ uv run mypy
Success: no issues found in 206 source files
$ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/life-agent/basetemp -p no:cacheprovider
..............................................................           [100%]
2366 passed, 34 deselected in 148.01s (0:02:28)
exit=0
$ df -h /tmp
tmpfs           7.7G  2.3G  5.5G  30% /tmp
```

The one earlier full-suite run of this session showed **1 failed / 2364 passed** — a
`FileNotFoundError` inside pytest's basetemp cleanup for
`test_ledger_adapters.py::test_each_kill_from_the_stream_copy[reorder-tasks]`, caused by an
ad-hoc `pytest` I ran concurrently on the **same** `--basetemp` (the collision also raised
`FileExistsError` on my side); the test passes in isolation (`8 passed in 2.76s`) and the clean
re-run above is 2366 passed with nothing else running. Recorded, not hidden.

**S9's precondition was NOT met** at session start: HEAD is still `873860a` and the Phase-0/1/2
deliverables are untracked (`git status` above). I did not commit (the standing rule is
owner-commits-on-request); the work sits atop the uncommitted files and the series is
re-stated in PROPOSED (DEVIATIONS 1). `git worktree list` shows a detached read-only worktree
at `~/.cache/life-agent-census/wt` (873860a) registered by the parallel read-only census
session — not mine to remove.

**S10 — owner file relocation, executed** (byte-identical; `docs/research/` created — a
subdirectory of `docs/`, not a top-level directory):

```
$ sha256sum docs/2026-08-agent-litsweep-dispositions.m
036d74cb92164740a99828b9632f4bd98bd73e4cf816f3cb38ce1c6e955f7b80  docs/2026-08-agent-litsweep-dispositions.m
$ mkdir -p docs/research && mv -n docs/2026-08-agent-litsweep-dispositions.m docs/research/2026-08-agent-litsweep-dispositions.md
$ sha256sum docs/research/2026-08-agent-litsweep-dispositions.md
036d74cb92164740a99828b9632f4bd98bd73e4cf816f3cb38ce1c6e955f7b80  docs/research/2026-08-agent-litsweep-dispositions.md
$ ls docs/2026-08-agent-litsweep-dispositions.m
ls: cannot access 'docs/2026-08-agent-litsweep-dispositions.m': No such file or directory
```

**KB writes this phase (S1 — all under `$LIFE_AGENT_KB/ledger/`):** the twelve segments +
`MANIFEST.json` (+ per-segment `.lock` files and `.MANIFEST.lock`), `census/20260818T100824Z.json`
(the C0 dry-run manifest), the T1 golden snapshot `golden/20260818T101402Z/`, and transient
`golden/<T>/work/…` directories that the harness removed on completion (S8). Nothing else in
the KB was written; the legacy stores are byte-identical to T0 (DONE 3). `du -sh ledger/`:
231 M — segments ≈125 M (`pkm.demand` 70 M, `pkm.artifact` 57 M, the rest < 4 M) + two golden
snapshots of 53 M each (the `du` line in DONE 5 reads 126 M for `ledger/` because that
invocation had already counted the golden directories listed before it).

## DONE

### 0. Pre-C0 — design §9 revision (V4/V5/V8) and the harness additions, with the V5 red run

`docs/unified-ledger-design.md`: one dated revision note under Status; §9 gains kill **5**
(unrouted Claude verdict — must kill A7, exactly A7), the **verdict-line semantics** paragraph
(V4: `CLAIM MET`/`MISSED` + `EXACT`/`SUPERSET`; a `SUPERSET` obliges a per-collateral
explanation; unexplained collateral is a finding), and the **A11 same-function contract**
paragraph (V8). No criterion weakened.

`golden.py` in the same checkpoint: `seed_unrouted_claude_verdict` (`Seed(..., exact=True)`),
the V4 flag on every verdict line (`[EXACT]` / `[SUPERSET collateral=[…]]`; an `exact` seed
turns collateral into a MISS), the S8 lifecycle (`work_dir`, `_remove_work` — refuses any path
that is not `…/golden/<T>/work/<name>`; removed on a claimed kill / green fixture / green
stream run, retained otherwise), `Paths` moved to `paths.py` with `state_sha_source` (R1's
sha source made explicit for Phase 3), and A11 brought to `rebuild_artifacts`' exact skip
semantics (`_check_meta_consistency` + `_read_lineage` inside the same `try`, catching
`LineageCorruptionError` — V8; no meta on the real cache is affected: `pkm-index` stayed
GREEN below). Tests: `test_v5_unrouted_claude_verdict_kills_exactly_a7`,
`test_v4_verdict_line_flags_exact_or_superset`,
`test_s8_work_dir_removed_on_claimed_kill_and_retained_otherwise` (asserts snapshots and legacy
files are byte-equal across the deletion path and that a non-work path is refused).

**The V5 red run, recorded now (not deferred to C4), against T0 on the real KB** — CLAIM MET
`[EXACT]`, and `pkm-index` GREEN with the amended A11:

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect unrouted-claude-verdict
seed     unrouted-claude-verdict (kill-5 unrouted-verdict); §9 must kill: exactly claude-verdicts
compare  gtd                    kind=semantic  comparator=<multiset of rows ignoring id> snapshot[rows=151 7edd5b2650b1] replay[rows=151 7edd5b2650b1] → GREEN
compare  state-md               kind=byte      comparator=<byte-identical text> snapshot[bytes=9960 1437513a74d9] replay[bytes=9960 1437513a74d9] → GREEN
compare  trips                  kind=semantic  comparator=<multiset of full rows> snapshot[rows=323 de87ba10010f] replay[rows=323 de87ba10010f] → GREEN
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 912f2b646bef] replay[- 912f2b646bef] → GREEN
compare  curves                 kind=byte      comparator=<canonical JSON of {edge: bin_reliability}> snapshot[- 88860b52869c] replay[- 88860b52869c] → GREEN
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=11 29144d76b72c] replay[evidence=11 29144d76b72c] → GREEN
compare  claude-verdicts        kind=byte      comparator=<canonical JSON of latest_by_decision> snapshot[- 6e13aff5f2e4] replay[- 6e311a5471b5] → RED  diff@ ~sha256:5e1e2bcac305[+ab-00000000000000000000000000000000]
compare  gather                 kind=byte      comparator=<canonical JSON of grow_block> snapshot[- 2b88b2978730] replay[- 2b88b2978730] → GREEN
compare  cells                  kind=byte      comparator=<canonical JSON of cell observations + coverage list> snapshot[- 96c42b28f8a0] replay[- 96c42b28f8a0] → GREEN
compare  answers                kind=identity  comparator=<key set + content/meta digests> snapshot[keys=832 5fa6dcf822d5] replay[keys=832 5fa6dcf822d5] → GREEN
compare  pkm-index              kind=semantic  comparator=<rowset equality of artifacts + artifact_lineage> snapshot[artifacts=32394 3f0df1fedc02] replay[artifacts=32394 3f0df1fedc02] → GREEN
compare  demand                 kind=byte      comparator=<multiset of canonical lines per file> snapshot[- 65fcfbdced12] replay[- 65fcfbdced12] → GREEN
compare  labels                 kind=byte      comparator=<ordered label lines + last-wins table> snapshot[labels=21 88e845f18720] replay[labels=21 88e845f18720] → GREEN
compare  corrections            kind=byte      comparator=<multiset of canonical lines> snapshot[lines=0 f1014797bf17] replay[lines=0 f1014797bf17] → GREEN
verdict  killed=['claude-verdicts'] claimed=['claude-verdicts'] CLAIM MET [EXACT]
exit=1
```

The unrouted-*reaction* invariance fixture stays green beside it (the routing-gated join vs
routing-blind map pair, V5); non-GREEN lines only:

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T085659Z --seed-defect unrouted-reaction
seed     unrouted-reaction (invariance); §9 must kill: (invariance: must stay green)
verdict  invariance fixture: GREEN as required
exit=0
```

**S8 applied to the Phase-2 leftovers.** `golden/20260818T085659Z/work/` still held the seven
Phase-2 seed copies (69 M). Rather than delete by hand, each seed was re-run against T0
restricted to its claimed artefact so the harness's own S8 path removed them on completion:

```
$ golden compare curves --t0 20260818T085659Z --seed-defect drop-edge-outcome
verdict  killed=['curves'] claimed=['curves'] CLAIM MET [EXACT]
$ golden compare gtd --t0 20260818T085659Z --seed-defect drop-task-disposed
verdict  killed=['gtd'] claimed=['gtd'] CLAIM MET [EXACT]
$ golden compare reactions --t0 20260818T085659Z --seed-defect reorder-reactions
verdict  killed=['reactions'] claimed=['reactions'] CLAIM MET [EXACT]
$ golden compare gtd --t0 20260818T085659Z --seed-defect reorder-tasks
verdict  killed=['gtd'] claimed=['gtd'] CLAIM MET [EXACT]
$ golden compare reactions --t0 20260818T085659Z --seed-defect retarget-reaction
verdict  killed=['reactions'] claimed=['reactions'] CLAIM MET [EXACT]
$ golden compare answers --t0 20260818T085659Z --seed-defect substitute-artifact
verdict  killed=['answers'] claimed=['answers'] CLAIM MET [EXACT]
$ golden compare reactions --t0 20260818T085659Z --seed-defect substitute-decision
verdict  killed=['reactions'] claimed=['reactions'] CLAIM MET [EXACT]
$ ls $LIFE_AGENT_KB/ledger/golden/20260818T085659Z/work/
(exit=0)
53M	$LIFE_AGENT_KB/ledger/golden/20260818T085659Z
```

### 1. C0 — the migration census (read-only)

`python -m life_agent.ledger.migrate census --write …` (`sources.scan` per source: parsed /
unparseable / duplicate-key (reviewer Q8) / blank counts + diagnostics; the typed acceptance
"parseable" is the **legacy reader's own constructor** — `TEV._from_json` / `REV._from_json` /
`O._from_line` / `DEC._from_line` / `RX._from_line` / `CV.from_line`; any JSON object for
gather / corrections / labels / demand; a `meta.json` (+ parseable or absent `lineage.json`)
for `pkm.artifact`). Written to `$LIFE_AGENT_KB/ledger/census/20260818T100824Z.json`:

```
$ uv run python -m life_agent.ledger.migrate census --write $LIFE_AGENT_KB/ledger/census/20260818T100824Z.json
census   act.tasks                    parsed=    300 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"naive19": 85, "naive26": 215} exists=true
census   act.trips                    parsed=    339 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"naive19": 339} exists=true
census   calibration.decisions        parsed=   2434 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware": 2434} exists=true
census   calibration.reactions        parsed=     14 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware": 14} exists=true
census   calibration.claude_verdicts  parsed=    180 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware": 180} exists=true
census   calibration.outcomes         parsed=    905 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware": 905} exists=true
census   calibration.gather_outcomes  parsed=     64 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware": 64} exists=true
census   calibration.corrections      parsed=      0 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={} exists=false
census   utility.elicitations         parsed=      5 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"aware-Z": 5} exists=true
census   eval.labels                  parsed=     21 unparseable=  0 duplicate_key=  0 blank=  0 stamp_shapes={"none": 21} exists=true
census   pkm.demand                   parsed= 103875 unparseable=  0 duplicate_key=  0 blank=  0 files=25 file_day_mismatch=0
census   pkm.artifact                 parsed=  32394 unparseable=  0 duplicate_key=  0 blank=  0 meta_json_files=32394 kernel_payload={"schema1:complete": 15061, "schema2:complete": 2293, "schema3:partial": 15040} produced_at_shapes={"naive19": 1, "naive26": 32393}
census   written 20260818T100824Z.json

real	0m6.751s
user	0m6.069s
sys	0m0.649s
exit=0
```

**Two-route reconciliation with r02's T0 counts (+ live growth since):** parsed counts equal
T0 on every source — `act.tasks` 300, `act.trips` 339, `calibration.decisions` 2434, `reactions`
14, `claude_verdicts` 180, `outcomes` 905, `gather_outcomes` 64, `corrections` absent (0),
`utility.elicitations` 5, `eval.labels` 21, `pkm.demand` 103,875 (25 files), `pkm.artifact` 32,394
— **delta 0 per source** (no live growth on this machine between T0 and C0; the harness's
`golden counts` run immediately before C0 agrees line for line). Zero unparseable, zero
duplicate-key, zero blank lines in every source. Diagnostics the envelope rules rest on:
`act.tasks` stamps naive (19- and 26-char), `act.trips` naive, every calibration log aware
(`+00:00`), `utility.elicitations` aware in `Z` form, `eval.labels` carries **no** stamp,
`pkm.demand` timestamps aware with `timestamp[:10] == file day` for all 103,875 lines
(`file_day_mismatch=0`), `pkm.artifact` `produced_at` naive (32,393 with microseconds, 1
without). **Finding:** the `pkm.artifact` kernel payload is fully recoverable from `meta.json`
for schema 1 (15,061) and schema 2 (2,293) but **partial for every schema-3 record (15,040)** —
the §18.9 records life_agent writes record `inputs` and metrics in `producer_metadata`, not
the key components (`model_identity`, `engine_version`, `prompt_template_hash`,
`output_schema_hash`); DEVIATIONS 6, QUESTIONS 7.

### 2. C1 — the schema/store, as amended this phase

The Phase-2 package (`schema.py`, `store.py`) is unchanged in contract; `store.py` gains
`append_many(source_id, events, verify_prefix)` — one lock, one physical scan, one `fsync` per
batch (the durability promise holds for every event whose append returned; a crash mid-batch
loses only an unfsynced tail, which the torn-tail protocol + the idempotent re-run cover), with
the occupied prefix verified by `event_id` (all of it with `verify_prefix`, else the last
occupied ordinal — the cheap alignment spot-check the live mirror will use); `event_ids()`,
`outputs()`; and a **manifest lock** (`.MANIFEST.lock`) around every `MANIFEST.json`
read-modify-write (`set_epoch`, `record_source_counts`, `_add_quarantine`, the new
`bump_tally`) — a finding of this phase: the segment lock alone does not cover the manifest,
so two live writers on different sources could lose each other's update in C5 (DEVIATIONS 12).
`append(event)` now delegates to `append_many` (per-line fsync as before). Tests: the nine
Phase-2 store tests unchanged and green; the migrate/adapter tests below exercise
`append_many` on every source.

### 3. C2 — the migration writer, `act.tasks` first, then the eleven, in the design's order

`sources.py`: one pure parser per source in the §2 canonical order (file order; UTC-day file
then line for `pkm.demand`; `(produced_at, cache_key)` for `pkm.artifact` — realised as
lexicographic order on the verbatim stamp then the key, DEVIATIONS 5), each record already
carrying its §2 envelope (`author`, `kernel_id`, `inputs`, `output`, `recorded_draw`,
`tx_time_raw` verbatim, `tx_time` derived per the source's declared clock or `None`).
`migrate.py`: `migrate` = `sync` = *append every legacy record not yet on the segment, in
canonical order, dedup by event identity* — differing only in prefix verification;
`pkm.artifact` dedups by `output` (one occurrence per identity, R5 — DEVIATIONS 8). Unparseable
and duplicate-key lines are not events; their counts land in `MANIFEST.json` per source.

```
$ uv run python -m life_agent.ledger.migrate migrate all
migrate  act.tasks                    parsed=    300 segment       0→    300 written=    300 skipped=      0 unparseable=0 duplicate_key=0
migrate  act.trips                    parsed=    339 segment       0→    339 written=    339 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.decisions        parsed=   2434 segment       0→   2434 written=   2434 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.reactions        parsed=     14 segment       0→     14 written=     14 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.claude_verdicts  parsed=    180 segment       0→    180 written=    180 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.outcomes         parsed=    905 segment       0→    905 written=    905 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.gather_outcomes  parsed=     64 segment       0→     64 written=     64 skipped=      0 unparseable=0 duplicate_key=0
migrate  calibration.corrections      parsed=      0 segment       0→      0 written=      0 skipped=      0 unparseable=0 duplicate_key=0
migrate  utility.elicitations         parsed=      5 segment       0→      5 written=      5 skipped=      0 unparseable=0 duplicate_key=0
migrate  eval.labels                  parsed=     21 segment       0→     21 written=     21 skipped=      0 unparseable=0 duplicate_key=0
migrate  pkm.demand                   parsed= 103875 segment       0→ 103875 written= 103875 skipped=      0 unparseable=0 duplicate_key=0
migrate  pkm.artifact                 parsed=  32394 segment       0→  32394 written=  32394 skipped=      0 unparseable=0 duplicate_key=0

real	0m16.155s
user	0m11.529s
sys	0m0.878s
exit=0
$ wc -l $LIFE_AGENT_KB/ledger/*.jsonl
      300 $LIFE_AGENT_KB/ledger/act.tasks.jsonl
      339 $LIFE_AGENT_KB/ledger/act.trips.jsonl
      180 $LIFE_AGENT_KB/ledger/calibration.claude_verdicts.jsonl
     2434 $LIFE_AGENT_KB/ledger/calibration.decisions.jsonl
       64 $LIFE_AGENT_KB/ledger/calibration.gather_outcomes.jsonl
      905 $LIFE_AGENT_KB/ledger/calibration.outcomes.jsonl
       14 $LIFE_AGENT_KB/ledger/calibration.reactions.jsonl
       21 $LIFE_AGENT_KB/ledger/eval.labels.jsonl
    32394 $LIFE_AGENT_KB/ledger/pkm.artifact.jsonl
   103875 $LIFE_AGENT_KB/ledger/pkm.demand.jsonl
        5 $LIFE_AGENT_KB/ledger/utility.elicitations.jsonl
   140531 total
$ jq .epoch,.sources[\"act.tasks\"] MANIFEST.json
"20260818T100854Z"
{
  "blank": 0,
  "duplicate_key": 0,
  "last_migrate_at": "2026-08-18T10:08:55.141862+00:00",
  "parsed": 300,
  "unparseable": 0,
  "writer_tally": 300
}
[]
```

**Idempotent re-run (a no-op), the two-route count per source (writer tally == segment
`wc -l` == C0 parsed count), and legacy byte-equality against the T0 manifest's sha256s:**

```
$ uv run python -m life_agent.ledger.migrate migrate all   # re-run: must be a no-op
migrate  act.tasks                    parsed=    300 segment     300→    300 written=      0 skipped=    300 unparseable=0 duplicate_key=0
migrate  act.trips                    parsed=    339 segment     339→    339 written=      0 skipped=    339 unparseable=0 duplicate_key=0
migrate  calibration.decisions        parsed=   2434 segment    2434→   2434 written=      0 skipped=   2434 unparseable=0 duplicate_key=0
migrate  calibration.reactions        parsed=     14 segment      14→     14 written=      0 skipped=     14 unparseable=0 duplicate_key=0
migrate  calibration.claude_verdicts  parsed=    180 segment     180→    180 written=      0 skipped=    180 unparseable=0 duplicate_key=0
migrate  calibration.outcomes         parsed=    905 segment     905→    905 written=      0 skipped=    905 unparseable=0 duplicate_key=0
migrate  calibration.gather_outcomes  parsed=     64 segment      64→     64 written=      0 skipped=     64 unparseable=0 duplicate_key=0
migrate  calibration.corrections      parsed=      0 segment       0→      0 written=      0 skipped=      0 unparseable=0 duplicate_key=0
migrate  utility.elicitations         parsed=      5 segment       5→      5 written=      0 skipped=      5 unparseable=0 duplicate_key=0
migrate  eval.labels                  parsed=     21 segment      21→     21 written=      0 skipped=     21 unparseable=0 duplicate_key=0
migrate  pkm.demand                   parsed= 103875 segment  103875→ 103875 written=      0 skipped= 103875 unparseable=0 duplicate_key=0
migrate  pkm.artifact                 parsed=  32394 segment   32394→  32394 written=      0 skipped=  32394 unparseable=0 duplicate_key=0
exit=0
$ uv run python -m life_agent.ledger.migrate counts --baseline $LIFE_AGENT_KB/ledger/census/20260818T100824Z.json
counts   act.tasks                    tally=    300 segment=    300 (wc -l 300, quarantined 0) legacy=    300 c0=300 growth=0 → OK
counts   act.trips                    tally=    339 segment=    339 (wc -l 339, quarantined 0) legacy=    339 c0=339 growth=0 → OK
counts   calibration.decisions        tally=   2434 segment=   2434 (wc -l 2434, quarantined 0) legacy=   2434 c0=2434 growth=0 → OK
counts   calibration.reactions        tally=     14 segment=     14 (wc -l 14, quarantined 0) legacy=     14 c0=14 growth=0 → OK
counts   calibration.claude_verdicts  tally=    180 segment=    180 (wc -l 180, quarantined 0) legacy=    180 c0=180 growth=0 → OK
counts   calibration.outcomes         tally=    905 segment=    905 (wc -l 905, quarantined 0) legacy=    905 c0=905 growth=0 → OK
counts   calibration.gather_outcomes  tally=     64 segment=     64 (wc -l 64, quarantined 0) legacy=     64 c0=64 growth=0 → OK
counts   calibration.corrections      tally=      0 segment=      0 (wc -l 0, quarantined 0) legacy=      0 c0=0 growth=0 → OK
counts   utility.elicitations         tally=      5 segment=      5 (wc -l 5, quarantined 0) legacy=      5 c0=5 growth=0 → OK
counts   eval.labels                  tally=     21 segment=     21 (wc -l 21, quarantined 0) legacy=     21 c0=21 growth=0 → OK
counts   pkm.demand                   tally= 103875 segment= 103875 (wc -l 103875, quarantined 0) legacy= 103875 c0=103875 growth=0 → OK
counts   pkm.artifact                 tally=  32394 segment=  32394 (wc -l 32394, quarantined 0) legacy=  32394 c0=32394 growth=0 → OK
counts   all sources reconcile
exit=0
$ legacy files byte-equal to the T0 golden manifest sha256s?
act.tasks                    sha256 5be77e9209d6f26c… == T0
act.trips                    sha256 774df20be14a06d2… == T0
calibration.outcomes         sha256 9187b5732dfd0af2… == T0
calibration.decisions        sha256 e9498cb59397f8aa… == T0
calibration.reactions        sha256 374fe1d475d2e78a… == T0
calibration.claude_verdicts  sha256 c224281ce09df5c6… == T0
calibration.gather_outcomes  sha256 93d7bcff0d0d5da0… == T0
calibration.corrections      absent (T0: exists=False)
utility.elicitations         sha256 710ed2a9feff3131… == T0
eval.labels                  sha256 0067de3e53b663a8… == T0
all legacy JSONL stores byte-identical to T0: True
```

### 4. C3 — the §7 adapters

`adapters.py` realises §7 literally — `A(stream) := legacy_fold([e.record for e in stream if
e.source_id ∈ S] in seq order)`: for each source the segment's records are **materialised**
(record verbatim, one canonical line per event, `seq` order) into a legacy-shaped file under
`golden/<T>/work/…`, and the harness's unchanged artefact functions run over a `Paths` pointing
at them. Nothing re-implements a fold. The three exceptions are the design's own: **A2** — the
stamp's sha is over the dual-written legacy ledger's bytes (`state_sha_source` stays legacy,
R1) while the events come from the stream; **A10** — the stream carries identities, never
bytes (R5): keys from the stream's `calibration.decisions`, content/meta read-replayed from the
real pkm root under each identity, plus a stream check printed by the harness (every referenced
key on disk is a `pkm.artifact` output on the stream); **A11/A12** — `pkm.artifact` records
are materialised as a **cache-shaped tree** via pkm's own `meta_file`/`lineage_file` path
functions so `_iter_meta_files` / `_check_meta_consistency` / `_meta_to_row` / `_read_lineage`
run **unchanged** over the stream (V8 — the same functions, the same skips, the same
`produced_at` rendering, by construction); `pkm.demand` records into
`logs/demand/<timestamp[:10]>.jsonl` (the C0 invariant). Tests:
`test_materialisation_is_the_existing_fold_over_records` (A2/A10/A11/A12 equalities on the
synthetic KB), `test_truncation_limits_and_changed_sources`.

### 5. C4 — the harness re-pointed at the stream

**Fresh T1 snapshot from the legacy stores** (`snapshot all --t0 20260818T101402Z`; digests
identical to T0's — no live growth):

```
$ uv run python -m life_agent.ledger.golden snapshot all --t0 20260818T101402Z
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
snapshot dir $LIFE_AGENT_KB/ledger/golden/20260818T101402Z

real	0m7.395s
user	0m6.073s
sys	0m0.690s
exit=0
```

**All fourteen artefacts GREEN from the stream** (`compare all --from stream`; the header
names the store root, epoch and per-source event counts; the last line is the A10 stream
check — 832 / 832 decision-referenced keys are `pkm.artifact` outputs on the stream):

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream
stream   root=$LIFE_AGENT_KB/ledger epoch=20260818T100854Z events={act.tasks:300, act.trips:339, calibration.claude_verdicts:180, calibration.corrections:0, calibration.decisions:2434, calibration.gather_outcomes:64, calibration.outcomes:905, calibration.reactions:14, eval.labels:21, pkm.artifact:32394, pkm.demand:103875, utility.elicitations:5}
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
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream

real	0m32.174s
user	0m15.485s
sys	0m4.539s
exit=0
```

**A4b under S7 — the R3 comparison proper (parity leg 2).** One `docker run` of the pinned skin
(digest and `PROTOCOL_MAJOR` verbatim below): the stream's utility evidence — truncated to
T0's recorded per-source counts (r02 DONE 1: elicitations 5, reactions 14, decisions 2434; a
no-op here since the stream equals T0, stated regardless) — folded through the skin and
compared against the **stored** T0 `utility-posterior.json`. GREEN: `fold_version`,
`n_events`, `u_bar` and the per-latent params equal:

```
$ uv run python -m life_agent.ledger.golden julia-run --t0 20260818T085659Z --from stream
julia    image=ghcr.io/gfrmin/credence-skin@sha256:90143895001d20b4abee7f5354ba87950545f5b1990eea0269293091a7c57f72 protocol_major=1
stream   root=$LIFE_AGENT_KB/ledger epoch=20260818T100854Z events={act.tasks:300, act.trips:339, calibration.claude_verdicts:180, calibration.corrections:0, calibration.decisions:2434, calibration.gather_outcomes:64, calibration.outcomes:905, calibration.reactions:14, eval.labels:21, pkm.artifact:32394, pkm.demand:103875, utility.elicitations:5} truncated_to={"calibration.decisions": 2434, "calibration.reactions": 14, "utility.elicitations": 5}
julia    evidence truncated to T0 counts {"calibration.decisions": 2434, "calibration.reactions": 14, "utility.elicitations": 5} (r02 DONE 1) so the evidence set matches the stored datum
julia    server={"methods": ["initialize", "shutdown", "create_state", "destroy_state", "snapshot_state", "restore_state", "condition", "condition_on_event", "weights", "mean", "expect", "optimise", "value", "marginal", "read_params", "draw", "enumerate", "perturb_grammar", "add_programs", "sync_prune", "sync_truncate", "top_grammars", "belief_summary", "condition_and_prune", "eu_interact", "call_dsl", "factor", "replace_factor", "n_factors", "structure_bma", "structure_observe", "structure_decide", "routing_init", "routing_decide", "routing_escalate", "routing_outcome", "routing_belief", "destroy_routing"], "protocol": "1.12", "version": "0.1.0"}
compare  utility-posterior      kind=julia     comparator=<exact equality of u_bar and per-latent params> stored[fold_version=70d72c6a0b6aa23b n_events=16 u_bar={"kappa_att": 0.03387855333671105, "lambda_int": 1.0000000000000078, "lambda_usd": 1.3310810811034355, "u_abstain": 0.0, "u_correct": 1.0, "u_hedged": 0.3997510335985348, "u_wrong": -8.830114182620882, "u_wrong_scoped": -2.000000000292678}] replay[fold_version=70d72c6a0b6aa23b n_events=16 u_bar={"kappa_att": 0.03387855333671105, "lambda_int": 1.0000000000000078, "lambda_usd": 1.3310810811034355, "u_abstain": 0.0, "u_correct": 1.0, "u_hedged": 0.3997510335985348, "u_wrong": -8.830114182620882, "u_wrong_scoped": -2.000000000292678}] → GREEN
note     the R3 comparison proper: stream fold vs the stored T0 datum (parity leg 2)

real	1m27.240s
user	0m0.775s
sys	0m0.267s
exit=0
```

**All five kills + both fixtures from the stream (V4 flags).** A seed on the stream route is
applied to the materialised copy, the affected sources are **re-migrated into a work store**
(the writer + segments round trip under the defect — the `stream   re-migrated…` line names
them and their counts) and materialised back, so the folds read a genuinely defective stream
copy; `substitute-artifact` touches artefact bytes only (no stream source; stated by the
harness). Non-GREEN lines only; every kill **CLAIM MET [EXACT]** — no collateral anywhere,
so no per-collateral explanation is owed; the invariance fixture GREEN as required:

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect reorder-reactions
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.reactions=14
seed     reorder-reactions (kill-1 reorder); §9 must kill: reactions, utility-fold-version
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 912f2b646bef] replay[- cc1cf7e08af7] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→ad7bc4e4c5]
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=11 29144d76b72c] replay[evidence=11 f1e29525caac] → RED  diff@ ~sha256:ee8250fb76e0[[0] 027826753e→85a1b21db3,[1] 85a1b21db3→027826753e]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['utility-fold-version', 'reactions'] claimed=['reactions', 'utility-fold-version'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect reorder-tasks
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: act.tasks=300
seed     reorder-tasks (kill-1 reorder); §9 must kill: gtd, state-md
compare  gtd                    kind=semantic  comparator=<multiset of rows ignoring id> snapshot[rows=151 7edd5b2650b1] replay[rows=151 00b3b2ca6d1c] → RED  diff@ ~sha256:bc51e9e65d79[[26] ba6ff9463f→080ad87b7d]
compare  state-md               kind=byte      comparator=<byte-identical text> snapshot[bytes=9960 1437513a74d9] replay[bytes=9961 76f696618eb3] → RED  diff@ ~sha256:982d9e3eb996[cac3d1d2d5→6f98d87555]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['gtd', 'state-md'] claimed=['gtd', 'state-md'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect drop-task-disposed
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: act.tasks=299
seed     drop-task-disposed (kill-2 drop); §9 must kill: gtd, state-md
compare  gtd                    kind=semantic  comparator=<multiset of rows ignoring id> snapshot[rows=151 7edd5b2650b1] replay[rows=152 10d4e73c54d2] → RED  diff@ ~sha256:bc51e9e65d79[len 151→152,[86] fc04b255fd→ecff65b276,[87] 0a36f0bf55→fc04b255fd]
compare  state-md               kind=byte      comparator=<byte-identical text> snapshot[bytes=9960 1437513a74d9] replay[bytes=9945 483336516d58] → RED  diff@ ~sha256:982d9e3eb996[cac3d1d2d5→e34313d4cb]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['gtd', 'state-md'] claimed=['gtd', 'state-md'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect drop-edge-outcome
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.outcomes=904
seed     drop-edge-outcome (kill-2 drop); §9 must kill: curves
compare  curves                 kind=byte      comparator=<canonical JSON of {edge: bin_reliability}> snapshot[- 88860b52869c] replay[- a15f44104310] → RED  diff@ ~sha256:ba27dd05387c[~sha256:437197a015ef[[9] 4e42f64b33→d8ac0159dc]]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['curves'] claimed=['curves'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect substitute-artifact
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   seed touched no stream source (artefact bytes only) — no re-migration
seed     substitute-artifact (kill-3 substitute); §9 must kill: answers
compare  answers                kind=identity  comparator=<key set + content/meta digests> snapshot[keys=832 5fa6dcf822d5] replay[keys=832 f1df99c4a8ee] → RED  diff@ ~sha256:48a53f0774c8[~0018599a76432bc4b58e3216ad6aba72bf5437cddd64590e6038ca1ae021988b[~sha256:656484a17acd[d08507bf67→9f83256235]]]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['answers'] claimed=['answers'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect substitute-decision
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.decisions=2434
seed     substitute-decision (kill-3 substitute); §9 must kill: utility-fold-version, reactions
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 912f2b646bef] replay[- f7e1003fcf08] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→6d216b3356]
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=11 29144d76b72c] replay[evidence=11 4b341ac628a1] → RED  diff@ ~sha256:ee8250fb76e0[[2] 4bef705ef2→a99a2fbf78]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['utility-fold-version', 'reactions'] claimed=['utility-fold-version', 'reactions'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect retarget-reaction
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.reactions=14
seed     retarget-reaction (kill-4 retarget); §9 must kill: reactions, utility-fold-version
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 912f2b646bef] replay[- ca98e6f83d31] → RED  diff@ ~sha256:ac94fc5687c3[7adf362ee4→479bfe0213]; ~sha256:9a3b074b5040[b17ef6d19c→e629fa6598]
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=11 29144d76b72c] replay[evidence=10 cfc4c752bcee] → RED  diff@ ~sha256:ee8250fb76e0[len 11→10,[0] 027826753e→85a1b21db3,[1] 85a1b21db3→4bef705ef2]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['utility-fold-version', 'reactions'] claimed=['reactions', 'utility-fold-version'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect unrouted-claude-verdict
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.claude_verdicts=181
seed     unrouted-claude-verdict (kill-5 unrouted-verdict); §9 must kill: exactly claude-verdicts
compare  claude-verdicts        kind=byte      comparator=<canonical JSON of latest_by_decision> snapshot[- 6e13aff5f2e4] replay[- 6e311a5471b5] → RED  diff@ ~sha256:5e1e2bcac305[+ab-00000000000000000000000000000000]
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  killed=['claude-verdicts'] claimed=['claude-verdicts'] CLAIM MET [EXACT]
exit=1
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T101402Z --from stream --seed-defect unrouted-reaction
stream   root=$LIFE_AGENT_KB/ledger (events as above)
stream   re-migrated into work store: calibration.reactions=15
seed     unrouted-reaction (invariance); §9 must kill: (invariance: must stay green)
stream   answers: 832 decision-referenced keys, 832 on disk, 832 of those are pkm.artifact outputs on the stream
verdict  invariance fixture: GREEN as required
exit=0
```

Note on A2 from the stream: its sha component is legacy-pinned (R1), so the reorder/drop kills
are carried by the rendered **body** (9960 → 9961 / 9945 bytes) — the criterion still fires
without the sha's help.

**Crash fixture on the stream side (§9), on a COPY of the real `calibration.reactions` segment
under the S1 subtree; the legacy log is the recovery source** — the torn tail is quarantined
(offset, length, reason, hex prefix), the segment never truncated (S6), the sweep re-appends the
missing event at the torn ordinal with the identical `event_id`, `seq` dense, and A6 from the
recovered copy equals the T1 snapshot; the work copy removed on completion (S8):

```
$ uv run python - <<EOF   # crash fixture on a COPY of the real reactions segment under golden/20260818T101402Z/work/crash/ (S1); the legacy log is the recovery source
torn copy   : 8667→8085 bytes, last physical line unterminated (37 bytes)
reader loud : calibration.reactions.jsonl: physical line 14 at byte 8048: unterminated tail (open the writer to quarantine it)
parseable   : 13 next_seq: 14
sync        : written=1 skipped=13 after=14
quarantine  : segment=calibration.reactions.jsonl byte_offset=8048 length=37 reason=unterminated bytes_hex=7b22617574686f72223a226f…
segment     : starts with torn+'\n' = True | bytes untouched (S6)
read        : seq [1, 2, 3] … [13, 14] | event_ids equal the real segment's: True
A6 from the recovered copy == T1 snapshot: True
work removed (S8): True
exit=0
```

The same fixture is a test on the synthetic KB
(`test_crash_fixture_from_the_stream_torn_tail_then_sync_recovers_and_folds_identically`).

**State after C4 — S8 (all `work/` empty), the census dir, and the counts still reconcile:**

```
$ find $LIFE_AGENT_KB/ledger -maxdepth 3 -type d | sort
$LIFE_AGENT_KB/ledger
$LIFE_AGENT_KB/ledger/census
$LIFE_AGENT_KB/ledger/golden
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z
$LIFE_AGENT_KB/ledger/golden/20260818T085659Z/work
$LIFE_AGENT_KB/ledger/golden/20260818T101402Z
$LIFE_AGENT_KB/ledger/golden/20260818T101402Z/work
$ du -sh $LIFE_AGENT_KB/ledger/golden/* $LIFE_AGENT_KB/ledger
53M	$LIFE_AGENT_KB/ledger/golden/20260818T085659Z
53M	$LIFE_AGENT_KB/ledger/golden/20260818T101402Z
126M	$LIFE_AGENT_KB/ledger
$ uv run python -m life_agent.ledger.migrate counts --baseline $LIFE_AGENT_KB/ledger/census/20260818T100824Z.json
counts   all sources reconcile
exit=0
```

### 6. The mirror's cost, measured (§10 "measured in Phase 3, not assumed") — a C5 input

On a **synthetic** decisions-sized source (2,434 rows of the same shape, smaller rows than
the real log — no owner data copied outside the KB), the *sync-shaped* mirror (parse the whole
legacy file, scan the segment, one append + fsync, manifest rewrite):

```
$ uv run python - <<EOF   # synthetic decisions-sized source: mirror-cost order of magnitude (§10 "measured in Phase 3")
initial migrate 2434 rows: 0.292s
mirror-shaped sync (parse legacy 1334 KB + segment scan + 1 fsync + manifest rewrite): median 194.9 ms, max 302.7 ms over 20
of which legacy parse alone: 126.3 ms for 2454 rows
of which segment scan alone: 4.5 ms
exit=0
```

Reading: a mirror that re-parses the legacy store per append costs ~0.2 s on the decisions
log (the legacy parse dominates; the segment scan is ~5 ms) — tolerable on the ask path
(seconds) but not "negligible". C5's mirror should therefore be **append-shaped**: a cheap
alignment check (the legacy store's line count against the segment's parseable count plus the
manifest's non-event counts), append the just-written record at `next_seq`, one fsync, the
tally bumped under the manifest lock; fall back to the full sync only when the check shows the
mirror behind (a missed mirror after a crash), and be loud when it shows the legacy store
*shorter* (rewritten). QUESTIONS 3–4 ask for the owner's signature on that shape and on the
failure posture before C5 opens.

### 7. Test evidence for this phase

49 ledger tests (`tests/test_ledger_store.py` 9, `tests/test_ledger_golden.py` 16,
`tests/test_ledger_migrate.py` 10, `tests/test_ledger_adapters.py` 14), all on the synthetic
`ledger_kb` fixture now shared from `tests/conftest.py`; the whole suite 2366 passed (STATE).
Highlights: census counts vs harness counts; unparseable / duplicate-key / blank lines are
non-events with locators; envelope rules per source; UTC annotation per clock;
`instrument_kernel_id` namespace + completeness; migrate → re-run no-op → legacy untouched →
counts reconcile; sync appends the tail and is loud on a rewritten prefix (both verification
modes); the `pkm.artifact` sweep dedups by identity; CLI smoke incl. the S1 refusal of
`census --write` outside `ledger/` and the `LIFE_AGENT_LEDGER_MIRROR=0` rollback switch; all
fourteen green from the stream + the A10 stream check + S8; materialisation equalities;
every kill from the stream copy (V4 flags, V5 exact) + the invariance fixture + the crash
fixture; CLI `--from stream`.

## DEVIATIONS

1. **S9 not met at session start** — HEAD `873860a`, the r02 commits not executed. Not
   committed by me (owner-commits-on-request stands); worked atop the uncommitted files.
   Consequence: the prepared series is re-cut over the *final* file states (PROPOSED) rather
   than "atop the three r02 commits".
2. **`Paths` moved** from `golden.py` to `paths.py` (+ `state_sha_source`) so `sources`,
   `migrate`, `adapters` and `golden` share it — a restructure of an uncommitted Phase-2 file.
3. **A11's legacy function amended for `rebuild_artifacts` fidelity** (V8): `_check_meta_consistency`
   and `_read_lineage` inside the same `try`, `LineageCorruptionError` caught. No criterion
   changed; the real cache has no affected meta (`pkm-index` GREEN before and after).
4. **Adapters realised by materialisation.** §7 says "a thin function over `store.read` and
   the existing fold"; the design's A11 wording ("applied to the stream's `record.meta` /
   `record.lineage`") is realised via a cache-shaped tree so `_read_lineage` can be *called*
   rather than paraphrased. Flagged for the reviewer (QUESTIONS 8).
5. **`pkm.artifact` canonical order** is lexicographic on the verbatim `produced_at` string
   then the key; a missing stamp sorts first as `""`. Equal to chronological order for the
   stamps present (all naive ISO with a common 19-char prefix; C0 shapes).
6. **`kernel_id` for schema-3 `pkm.artifact` records is a recorded-subset digest** — the
   design's premise that the schema-3 payload is recomputable from `meta.json` alone is false
   for the 15,040 §18.9 records; the digest covers `schema_version, producer_name,
   producer_version, producer_config_hash` (+ `model_identity_hash` when `producer_metadata`
   carries `model_identity`); the manifest/census records the completeness classes.
   `kernel_id` is derived (never hashed into `event_id`), so nothing identity-bearing depends
   on it. Ruling requested (QUESTIONS 7).
7. **A12's file grouping** from the stream is `timestamp[:10]` (the record carries no file
   name); C0 verified the invariant on every line and records `file_day_mismatch` per census.
8. **`pkm.artifact` sweep dedups by output identity, not ordinal** (set-shaped, R5): a new
   artefact whose `produced_at` sorts before an old one is appended after it, never conflicts;
   re-migration verifies by key. Tested. QUESTIONS 10.
9. **`eval.labels` has no stamp** → `tx_time_raw=""`, `tx_time=None`; `utility.elicitations`'
   `Z` stamps → `tx_time` in `+00:00` form (the verbatim `Z` string kept in `tx_time_raw`).
10. **Parseability = the legacy reader's constructor**; `utility.elicitations` is checked
    structurally only (latent names are validated against `model.yaml`, a config input, by the
    fold — not by the writer).
11. **`append_many` fsyncs once per batch** (single-event `append` fsyncs per line as before);
    the durability promise is restated in §10 terms in the C1 paragraph. QUESTIONS 11.
12. **Manifest lock added** (`.MANIFEST.lock`) — a store finding fixed pre-C5 (DONE 2).
13. **Seeds from the stream = the writer round trip** (materialise → seed → re-migrate into a
    work store → materialise → fold). QUESTIONS 9.
14. **Stream compare costs ~32 s** (materialising 32,394 metas + the A11 walk); acceptable for
    the harness; the S8 lifecycle keeps the KB free of the copies.
15. **S8 applied retroactively** to the Phase-2 leftovers by re-running each seed against T0 on
    its claimed artefact (DONE 0) — the harness's own deletion path, no hand deletion.
16. **Mirror-cost measurement is synthetic-shaped** (no owner data left the KB).
17. **One suite run had a basetemp-collision failure** (STATE) — recorded with the clean re-run.
18. **`docs/research/` created** for S10 (a `docs/` subdirectory).
19. **`ledger/census/`** is a new subdirectory under `ledger/` for the C0 dry-run manifests
    (S1-compliant); `census --write` refuses any path outside `ledger/`.

## REFUSED

- No dual-write hook, no live writer touched, no scheduler/timer, no reader cutover, no
  retirement, no compaction; the quarantine list is append-only (S6).
- No pkm code, SPEC, PRINCIPLES, brain-seam or spine change; the design doc changed only per
  the brief's pre-C0 instruction (§9 + a dated revision note); Appendix A stays proposals.
- No KB write outside `$LIFE_AGENT_KB/ledger/` (S1); no KB read beyond the legacy stores, the
  utility model and the pkm cache/demand files (read-only).
- No commit, no push; the census worktree registration left to its owner.
- The old T0 `work/` leftovers were not hand-deleted (S8's mechanism removed them).

## QUESTIONS

**Owner signature:**

1. **Commits.** S9 said the r02 commits would be executed before this session; they were not.
   Sign one of: (a) I execute the prepared series (PROPOSED) now, at this STOP; (b) the owner
   executes it; (c) leave for the tranche end.
2. **Snapshot retention.** `golden/20260818T085659Z/` (T0, holds the S3 Julia datum) and
   `golden/20260818T101402Z/` (T1), 53 M each — keep both (T0 is the parity datum's home)?
3. **C5 mirror shape** (DONE 6): append-shaped (cheap alignment check + `next_seq` append +
   fsync + tally under the manifest lock; full sync only when behind; loud when the legacy
   store is shorter) — recommended — vs sync-shaped (~0.2 s per decisions append). Sign.
4. **Mirror failure posture on the live path.** After a successful legacy append, a mirror
   failure (KB unwritable, conflict) either (a) logs at WARNING and returns — the legacy write
   is durable, the sweep/`migrate` re-run recovers, the two-route count detects — or (b)
   raises into the caller's command (loud, but the user-facing command fails after its truth
   was recorded). Recommended: (a) plus the C6 count as the detector. Sign — this touches the
   interaction contract.
5. **`LIFE_AGENT_LEDGER_MIRROR=0`** as the rollback switch for the mirror + sweeps
   (default on): acceptable name and semantics?
6. **What counts as "real traffic" for C6 on this machine** — `jarvis` runs on steel with its
   own KB (a different `$LIFE_AGENT_KB` root there), so the tasks writer will not fire
   here; the thinkpad writers are the ask path (decisions/outcomes/reactions via
   `scripts/ask.py`/the bridge), `claude_verdict`, `answer_labels`, `verdict.py`. Does C6 run on
   thinkpad only, or must the dual-write also be deployed to steel (a code deploy — the KB
   there has its own legacy stores and would need its own C0–C2)? Owner directs.

**Reviewer ruling:**

7. **DEVIATIONS 6** — the recorded-subset `kernel_id` for schema-3 §18.9 records: acceptable as
   tranche 1's instrument identity (derived, namespace-tagged, recomputable from `record`), or
   must the §18.9 writer start recording the payload components in `producer_metadata` (a
   life_agent change to `core/derivations.record` — proposal only, out of this tranche)?
8. **DEVIATIONS 4** — materialisation as the §7 mechanism (the existing fold, literally; V8
   satisfied by construction for A11): accepted as the standing realisation?
9. **DEVIATIONS 13** — seeds from the stream via the writer round trip: accepted as "against
   the stream copy"?
10. **DEVIATIONS 8** — identity-keyed sweep for `pkm.artifact` (R5): accepted?
11. **DEVIATIONS 11–12** — batch fsync in `append_many` and the manifest lock: accepted as §10
    amendments (one line each, to be folded into the design doc at r03)?
12. **A2's stream kill is body-borne** (the sha is legacy-pinned by R1) — a note for the
    cutover tranche's byte-vs-semantic decision; nothing to rule now unless the reviewer wants
    the sha component named as legacy-only in §9.
13. **V6 locators** — the `substitute-artifact` diff prints one full 64-hex cache key (a hash,
    passed through by the locator policy): confirm that is within V6.

## PROPOSED

**Prepared checkpoint series** (each green on the whole suite, bisectable, one move; not
executed — QUESTIONS 1). Because `golden.py` imports `adapters.py` and the shared test fixture
lives with the harness, the series is cut by import order:

1. `feat(ledger): unified event schema + segment store (§10: torn tail, manifest lock, batch append)`
   — `src/life_agent/ledger/{__init__,schema,store,paths}.py`, `tests/test_ledger_store.py`.
2. `feat(ledger): legacy parsers + migration writer/sweeps/two-route counts (§8 C0–C2) and the §7 adapters (C3)`
   — `src/life_agent/ledger/{sources,migrate,adapters}.py` (library only; green — no test
   depends on it alone).
3. `feat(ledger): golden-replay harness (§9) — kills 1–5 with V4 flags, S8 lifecycle, --from stream, S7 julia-run; all ledger tests`
   — `src/life_agent/ledger/golden.py`, `tests/conftest.py` (`ledger_kb`),
   `tests/test_ledger_{golden,migrate,adapters}.py`.
4. `docs(unification): design doc (rev. V4/V5/V8) + r00–r03a; S10 relocation`
   — `docs/unified-ledger-design.md`, `docs/unification/reports/{r00-census,r01-design,r02-harness,r03a-migration}.md`,
   `docs/research/2026-08-agent-litsweep-dispositions.md`.

**On review of this report (and signatures on Q1–Q6, rulings on Q7–Q13): open C5** — the
append-shaped mirror (one call at each of the nine typed writers, legacy-append-first, under
the §10 per-segment lock — the reactions segment lock is shared by the bridge and `ask.py` by
construction), the three sweeps as manual CLI (`migrate sync …`, already in place — no
scheduler), the mirror's env rollback, and its measured cost; then **C6** — the two-route count
after a settling interval with real traffic (per Q6) plus one `golden compare all --from
stream` at a fresh T2 — and `r03-merge.md`. **STOP.**

## Addendum D applied — 2026-08-18

**Authority.** Owner signature **S11** (addendum brief, received at the r03a gate): three
verified-citation documentation edits, dictated verbatim; the S10 boundary applies (no
status-header change, no edit beyond those named, no code, no §9 criterion, no schema).
Applied as a discrete step *after* the C0–C4 record above; nothing here enters DONE 0–7.
**C5 remains gated on the reviewer's r03a review — this addendum does not open it.**
Provenance for every figure below is the owner's verify-before-cite memo (2026-08-18);
this session did not itself re-verify any figure against the papers.

### D1 — `docs/unified-ledger-design.md` §10 (two sentences) + one revision note

- **(a)** Anchor `preprint figure, unverified` (§10 "Order-of-magnitude target" bullet): matched
  **EXACT**, one occurrence; the bullet's OpenHands clause replaced by the dictated text
  (0.20 ms median / 0.31 ms P95 per-event persist latency, Table 3, arXiv:2511.03690v2, 433
  SWE-Bench Verified conversations, production LocalFileStore path, **verified 2026-08-18**).
- **(b)** Anchor `warning against heavy in-path verification` (same bullet): matched **EXACT**;
  the SSGM clause replaced by the dictated reframing (arXiv:2603.11768v2; latency–safety
  trade-off, §1 contribution 4; Write Validation / Read Filtering gates, Principles 1–2). The
  writer-verifies-vocabulary-and-shape-only clause that follows is unchanged.
- The two clauses share one bullet, so both replacements were made as one exact-anchor
  `str_replace` over the whole bullet (fitting: line-wrapping to the document's column width
  only; wording as dictated). Locator after: `docs/unified-ledger-design.md` §10, the
  "Order-of-magnitude target" bullet.
- **Revision note** appended as a third `> **Revision 2026-08-18 (Addendum D, owner signature
  S11 — verified-citation upgrades):**` paragraph in the Status block, after the Phase-3
  pre-C0 note, naming both edits and the memo. The Status line itself is untouched.

### D2 — `docs/research/2026-08-agent-litsweep-dispositions.md` (three rows, S11)

- **(a) §3 SSGM row:** Verdict `INPUT` → `INPUT (verified)`; Destination cell replaced by the
  dictated text (trade-off citation; ADDITIONALLY Principle 4 Reversible Reconciliation as
  supporting prior art for design-doc §0; "conceptual paper … pattern and trade-off taxonomy
  only"). Anchor EXACT (whole row line, one occurrence).
- **(b) §3 OpenHands row:** dictated text appended to the Destination cell (Table 3 verbatim;
  "under 20 ms" prose vs the crash-recovery row's 32.1 ms max; 61 % failure reduction weighted
  as a co-location result). Anchor EXACT (cell tail `verify before quoting |`). The row's
  **Verdict cell was not named by D2(b) and is unchanged (`INPUT + VERIFY`)** — see the note
  below.
- **(c) §4 Contract2Tool row:** dictated text appended to the caveat text (Destination cell:
  abstract figures 0.980 vs 0.990, tools 100→1, tokens 26,172→2,528; third caveat, synthetic
  benchmark + self-published registry, no independent replication as of 2026-08-18). Anchor
  EXACT (cell tail `for load-bearing claims |`).
- **Status header untouched:** the file's first seven lines (H1 + Status blockquote) are
  byte-identical before and after (sha256 of `sed -n 1,7p`: `91477786…96ba2` both sides).

### D3 — new file `docs/research/register-openclaw-governor.md`

Created with the dictated H1, one status header line
(`> **Status: owner-signed (S11, 2026-08-18) — queued for the governor integration tranche.**`
— the repository's standard blockquote form), and the R-GOV-1 paragraph verbatim (fail-open
`before_agent_finalize`, 15 s default budget; consequences (i)–(iv); `BeforeAgentFinalizeRetry`;
Codex-native Stop hooks). No other content.

### Transcript

```
$ sha256sum <before>
dbfcf910f237699a58347c2bb7b1ed1407346d062abe6b76d4e9a2445961eef5  docs/unified-ledger-design.md
036d74cb92164740a99828b9632f4bd98bd73e4cf816f3cb38ce1c6e955f7b80  docs/research/2026-08-agent-litsweep-dispositions.md
$ uv run python <scratchpad>/apply_addD.py      # exact-anchor replacements, count asserted == 1
D1(a)+(b): EXACT anchor, replaced 1 in docs/unified-ledger-design.md
D1 revision note: EXACT anchor, replaced 1 in docs/unified-ledger-design.md
D2(a): EXACT anchor, replaced 1 in docs/research/2026-08-agent-litsweep-dispositions.md
D2(b): EXACT anchor, replaced 1 in docs/research/2026-08-agent-litsweep-dispositions.md
D2(c): EXACT anchor, replaced 1 in docs/research/2026-08-agent-litsweep-dispositions.md
done
$ sha256sum <after>
11f6c4074388e404bbccbbc4dbbe34375ea773b871384c9e970efff470f84f99  docs/unified-ledger-design.md
f1f1a5fa17f35d5e1f61e622ac8de5808d3e6966dc669ec8a579a6d7c12b6e17  docs/research/2026-08-agent-litsweep-dispositions.md
0cff3f0a9cd5db25bcf1cccd8975780e753d781981bc39cfe6b9b4c63c72df7c  docs/research/register-openclaw-governor.md
$ uv run python .githooks/pii_check.py --shapes-only docs/unified-ledger-design.md docs/research/2026-08-agent-litsweep-dispositions.md docs/research/register-openclaw-governor.md
exit=0
```

The apply script lives in the session scratchpad (not in tree); its five anchors and
replacements are the texts quoted in this section.

### Not edited — named for the owner (REFUSED applies; S11 is verbatim)

1. **Dispositions §6 item 4** (the Phase-1 injection text) still reads "(marked 'preprint
   figure, unverified') OpenHands' reported sub-millisecond per-event persistence … cite SSGM
   (arXiv:2603.11768) as the warning against heavy in-path verification. No figure is quoted
   as fact until verified against the final PDF." Addendum D does not name §6; it now
   contradicts §3's verified rows. Left verbatim. **Q14 (owner):** bring §6.4 into line, or is
   §6 frozen as the historical injection the Phase-1 agent received?
2. **OpenHands row Verdict cell** `INPUT + VERIFY` — D2(b) named the destination cell only. Left.
   (The SSGM row's verdict *was* named and changed.) **Q15 (owner):** should it read
   `INPUT (verified)` too?
3. Design doc §0 and §5 cite OpenHands as `arXiv:2511.03690` (no version suffix; §5 says "rev.
   Apr 2026") — not named; unchanged.

### An observation the owner should see (no edit; bears on C5)

§10 now states the target as **0.20 ms median / 0.31 ms P95** and retains the pre-existing
clause "an fsync per line is within it on this disk; measured in Phase 3, not assumed". What
Phase 3 actually measured (DONE 7, `mirror-cost`) is the **sync-shaped** mirror on a
decisions-sized synthetic source: **median 194.9 ms** (126.3 ms of it legacy parse; segment
scan 4.5 ms; one fsync + manifest rewrite the remainder) — three orders of magnitude above the
now-verified target — and the per-line fsync alone was **not** isolated. So the "measured in
Phase 3" clause is true only of a mirror shape this report recommends against (QUESTIONS 3).
Not edited (S11 verbatim; the clause pre-dates D1). **For C5:** the append-shaped mirror must be
timed per call and recorded in r03 against the 0.20/0.31 ms figure explicitly, so the verified
number is never read as a met target.

### State change found while applying: HEAD rewritten; the working-tree fixture lost and restored

- **HEAD is now `1ea9df8`** (STATE above recorded `873860a`). `git reflog`:
  `HEAD@{0}: reset: moving to origin/master`; `git diff --stat 873860a origin/master` is
  **empty** — identical trees, rewritten commit objects (the six most recent subjects are
  identical). The reset discarded this session's one *tracked-file* modification —
  `tests/conftest.py` (the `ledger_kb` fixture + `LEDGER_MARKER`, which
  `tests/test_ledger_{golden,adapters,migrate}.py` import). Every untracked file
  (`src/life_agent/ledger/`, the four ledger test files, the docs) survived. The S10 source
  file was never tracked at either HEAD (`git ls-tree` empty), so it was not resurrected —
  S10 stands.
- **Restored from the session transcript**, not re-authored: the fixture block as read back
  at 09:47Z (before the 10:05Z move out of `test_ledger_golden.py`; only appends *after* the
  block happened in between), then the 10:05Z transformation replayed (`kb`→`ledger_kb`,
  `MARKER`→`LEDGER_MARKER`, the header + imports), then the 10:07Z demand-timestamp edit,
  then `ruff check --fix` as originally.
- **Verification:** ruff clean on `conftest.py` + the four ledger test files; shapes guard on
  `conftest.py` exit 0;
  ```
  $ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q tests/test_ledger_store.py tests/test_ledger_golden.py tests/test_ledger_migrate.py tests/test_ledger_adapters.py --basetemp=$HOME/.cache/life-agent/basetemp-adhoc -p no:cacheprovider
.................................................                        [100%]
49 passed in 8.54s
exit=0
  ```
  (matches DONE 7's 49.) mypy: see the line appended below.
- **S9 status is unchanged (unmet):** `1ea9df8` carries none of the r02/r03a files. The
  PROPOSED series is unchanged in content and paths; its base is now `1ea9df8`.
- `git stash list` shows one pre-existing stash (`pre-sync WIP 2026-08-02/03 …`) — not this
  session's; untouched.

### Prepared commit (not executed — owner commits on request)

`docs(research): verified-citation upgrades + governor register entry` — files:
`docs/unified-ledger-design.md` (two sentences + revision note),
`docs/research/2026-08-agent-litsweep-dispositions.md` (three rows),
`docs/research/register-openclaw-governor.md` (new). Docs-only; guard exit 0 on all three.
**Sequencing (S9 consequence):** the first two files are still untracked, so this commit is
bisectable only *after* PROPOSED commit 4 (which first adds them) — i.e. as commit **5** of the
series; the alternative is to fold D into commit 4. Owner's call (Q1 already asks for the
series' execution). Command, for the owner:
`git add docs/unified-ledger-design.md docs/research/2026-08-agent-litsweep-dispositions.md docs/research/register-openclaw-governor.md && git commit -m 'docs(research): verified-citation upgrades + governor register entry'`.

**STOP** (unchanged): waiting on the r03a review.

mypy after the restoration: `$ uv run mypy` → `Success: no issues found in 206 source files` (exit 0).

## r03a review received — rulings applied; C5 prepared, not opened — 2026-08-18

**Review verdict (relayed by the owner):** C0–C4 accepted; reviewer rulings Q7–Q13 issued;
recommendations on owner Q1–Q6; C5 opens on the owner's signatures. **As of this section the
owner's signatures on Q1–Q6 have not been given** (the recommendations are the reviewer's), so
**no live writer has been touched and nothing is committed.** Everything below is the work that
does not depend on those signatures.

### Reviewer rulings Q7–Q13 — applied to the design doc (one dated revision note)

| Ruling | Applied where | What |
|---|---|---|
| Q7 | §4 "Completeness" paragraph | accepted for tranche 1; forward fix (the §18.9 writer recording the key components) is a *queued proposal* with named landing sites, not built; **no backfill** of existing schema-3 records — identity permanence; new records start a third completeness era |
| Q8 | §7 "Realisation" paragraph | materialisation is the adapters' standing realisation (the stronger V8 reading); incremental production adapters are a cutover-tranche question, not a debt |
| Q9 | revision note only | accepted, no text change |
| Q10 | §4 "Segment order after sweeps" | `pkm.artifact` physical order may diverge from canonical after sweeps; harmless because §3's invariant is record-computable ordering keys, not file order |
| Q11 | §10 "Append" bullet + new "Manifest lock" bullet | the **durability split** stated: per-line for live appends, per-batch for migration and sweeps (`append_many`), one code path and prefix check; the manifest lock recorded as a Phase-3 finding |
| Q12 | §9 A2 row | the sha component named **legacy-pinned by R1** (`Paths.state_sha_source`, both routes, never from the stream) |
| Q13 | §11 new bullet | the standing **locator policy**: digests, hashes and keys pass; record field values do not |

Transcript: `apply_r03a_rulings.py` (scratchpad; six exact anchors, each count-asserted 1) →
`revision note: ok / §4 Q7/Q10: ok / §7 Q8: ok / §9 A2 Q12: ok / §10 Q11: ok / §11 Q13: ok`;
guard exit 0. Q7 rider (i)'s proposal text will be drafted in r03's QUESTIONS, as ruled.

### Addendum D — already delivered

The review's "Addendum D has not yet been delivered" pre-dates the previous appended section:
D1–D3 are applied, recorded above, and prepared as the fifth docs commit (or folded into
series commit 4 — owner's call, as stated there).

### C5 prepared to the reviewer-recommended shape — built, tested, **unwired**

Because Q3–Q5's recommendations coincide with this report's own QUESTIONS 3–5, the mirror
library was built to that shape so that C5's live-writer step is one call per writer once
signed. **Nothing calls it yet.** New/changed, all under `src/life_agent/ledger/` (+ tests):

- `mirror.py` (NEW) — `after_legacy_append(source_id, legacy_path, *, n=1, store=None, paths=None) -> MirrorResult`,
  the one call a writer makes after its legacy append. **Append-shaped (Q3):** the manifest
  row carries `legacy_bytes` (the byte length the last sweep/mirror consumed); a call reads
  only the legacy file's *delta*, parses it with the SAME parser the sweep uses
  (`sources.parse_line`, factored out of `_scan_jsonl` for exactly this — a mirrored line and
  a swept line are one event by construction, verified by a sweep-is-no-op test), and appends
  at the next dense ordinals under the segment lock (one line, one fsync). **Loud when
  behind:** a delta longer than the caller's own `n` is a WARNING naming the count and is
  counted (`mirror_behind_events`, `mirror_behind_calls`); the delta is not trusted (no
  recorded offset; a non-event line in it; a legacy file shorter than the offset; an
  unterminated tail; > 512 lines) → **fallback to the full sweep** (`migrate.sync_source`),
  WARNING with the reason, `mirror_syncs` counted. **Fail-open, counted (Q4a as refined):**
  never raises into a writer; every failure is a WARNING (source + exception class, never a
  value) and `mirror_failures` + `last_mirror_failure_at` on the manifest row, so C6's
  two-route read surfaces it structurally. **Recorded switch (Q5 as refined):**
  `LIFE_AGENT_LEDGER_MIRROR=0` disables; the first call per process logs the state (INFO
  enabled / WARNING disabled) and records `mirror_state {enabled, env, recorded_at}` in the
  manifest, so a disabled mirror reads as *disabled*, never as loss. **Configured store only:**
  a writer appending anywhere but the configured legacy path is `skipped` — nothing but the
  owner's live stores can reach the owner's stream (writer tests with tmp paths stay inert
  once wired). **Uninitialised stream** (no `MANIFEST.json`) → `inert`, one WARNING per
  process, nothing created. Swept sources offered to the mirror → `failed` (surfaced, not
  raised).
- `sources.py` — `parse_line(source_id, line, *, ordinal, locator) -> (Parsed|None, status)`
  is now THE JSONL line parser; `_scan_jsonl` calls it and records `legacy_bytes` (the byte
  length actually read) in `Scan.extras`.
- `migrate.py` — `sync_source` records `legacy_bytes` on the manifest row for JSONL sources.
- `store.py` — `update_source(source_id, *, set, add)` (one manifest RMW: overwrite fields +
  increment counters) and `set_note(key, value)` (top-level manifest note; refuses
  `sources/quarantine/format_version/epoch`); `bump_tally` now delegates to it; `_Line` is a
  `NamedTuple` and `_lines` carries a `(size, mtime_ns)`-keyed cache (never stale — every
  append grows the file; only ever over-fresh under a concurrent writer) so one append no
  longer scans the segment three times. No semantic change; the 9 store tests + torn-tail
  fixtures are unchanged and green.
- `paths.py` — `Paths.from_config(resolve_pkm=False)` skips the `PKM_CONFIG` YAML read (the
  mirror needs only the JSONL paths and must not pay a file read per call).
- `tests/test_ledger_mirror.py` (NEW, 13 tests): offset recorded by migration; in-step append
  == the sweep's event (sweep no-op after) + announce-once + manifest bookkeeping; batch `n`;
  behind → loud, counted, caught up; noop; no-offset → full sweep then append-shaped again;
  non-event in delta → sweep, counted not mirrored; unterminated tail not trusted; disabled →
  recorded, writes nothing; inert without a stream (one WARNING); non-configured path skipped;
  fail-open counted + swept source surfaced; `parse_line` == the scan parser. Marker never in
  log output.
- `__init__.py` untouched (its "no live writer touches the stream" sentence is still true);
  its module list gains `mirror` in the wiring commit.

**Not done (gated):** the nine writer hooks (§8 C5 list; note the labels writer is
`scripts/answer_labels.py:append_label`, not `core/`), the sweeps' call site on the ask path,
C6. **Assumption stated:** if the owner signs Q3/Q4/Q5 differently from the recommendations,
`mirror.py` + its tests are the only speculative files and are discarded or reshaped.

### Measured cost (the §10 clause corrected)

```
$ uv run python <scratchpad>/mirror_cost.py   # synthetic decisions-sized source, ~/.cache only
initial migrate 2434 rows (1342 KB legacy): 0.548s
append-shaped mirror, in step, decisions-sized segment (2434 events): median 41.07 ms, p95 60.24 ms, max 120.62 ms over 50
  of which: segment scan (_lines over 2321 KB): 8.89 ms
  of which: manifest read+write under lock: 5.48 ms
  of which: one fsync on the segment file: 0.06 ms
  of which: legacy delta read: 0.08 ms
fallback full sync (no recorded offset): 378.8 ms — action=synced
exit=0
$ fsync probe: 30 × (write 1 KB dirty + fsync) — median per fsync
KB ledger/ (the stream's volume)         median 0.72 ms  p95 1.31 ms
~/.cache (root disk, where measured)     median 4.32 ms  p95 4.41 ms
exit=0

$ MIRROR_COST_ROOT=$LIFE_AGENT_KB/ledger/.bench-c5 uv run python <scratchpad>/mirror_cost.py   # same synthetic source, on the stream volume; scratch removed after
initial migrate 2434 rows (1342 KB legacy): 0.501s
append-shaped mirror, in step, decisions-sized segment (2434 events): median 30.30 ms, p95 31.50 ms, max 84.70 ms over 50
  of which: segment scan (_lines over 2321 KB): 0.64 ms
  of which: manifest read+write under lock: 11.90 ms
  of which: one fsync on the segment file: 0.01 ms
  of which: legacy delta read: 0.10 ms
fallback full sync (no recorded offset): 303.6 ms — action=synced
exit=0

$ uv run python <scratchpad>/mirror_cost.py   # FINAL code (scan cache + NamedTuple lines), ~/.cache root disk
initial migrate 2434 rows (1342 KB legacy): 0.451s
append-shaped mirror, in step, decisions-sized segment (2434 events): median 17.71 ms, p95 19.73 ms, max 54.66 ms over 50
  of which: segment scan (_lines over 2321 KB): 0.69 ms
  of which: manifest read+write under lock: 5.30 ms
  of which: one fsync on the segment file: 0.07 ms
  of which: legacy delta read: 0.10 ms
fallback full sync (no recorded offset): 300.7 ms — action=synced
exit=0
```

Reading: on the **stream's own volume** the append-shaped mirror costs **~30 ms median /
~32 ms P95 per call in step** (a decisions-sized segment); the fsynced temp-file +
`os.replace` manifest write is ~12 ms of it (that volume appends cheaply — 0.7 ms per dirty
fsync — and renames expensively), one whole-segment scan ~3–5 ms, the segment fsync ~1 ms;
the fallback sweep ~0.3 s. On the root disk 18 ms (dirty fsync 4.3 ms, cheaper renames). The
verified OpenHands figure (0.20 ms median / 0.31 ms P95) is a persist-step number and is
**not met — by two orders of magnitude** — by any design that fsyncs a rewritten manifest per
line; §10's unmeasured "an fsync per line is within it on this disk" (my Phase-1 sentence) is
therefore **replaced by the measured figures**, in the same revision note. Levers if the owner
wants it lower, **queued for r03, not built:** (i) an append-only mirror log
(`ledger/.mirror-log.jsonl`: one small line per call, append + fsync ≈ 0.7 ms here) as the
tally's home instead of a manifest rewrite — arguably a *better* first route (every mirror
write with its seq range) — with the manifest bumped only by sweeps; (ii) the delta by
tail-count of the legacy file (`bytes.count(b"\\n")`, ~0.3 ms on 1.3 MB) instead of a recorded
offset, removing the per-call `legacy_bytes` write. Together they would take the call to
~5–8 ms; the target would still not be met (the segment scan is the density check).

KB contact for the measurement (S1): a 30-line fsync probe file created and unlinked under
`$LIFE_AGENT_KB/ledger/` (`.fsync-probe.tmp`), and the synthetic benchmark's scratch root at
`$LIFE_AGENT_KB/ledger/.bench-c5/` (its own store; removed by the script; `ls -a` shows none
left). No segment, manifest, snapshot or legacy file was read or written.

### STATE after this section

```
$ uv run ruff check src tests            → All checks passed!
$ uv run mypy                            → Success: no issues found in 207 source files
$ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/life-agent/basetemp -p no:cacheprovider
2379 passed, 34 deselected in 229.92s (0:03:49)
```
(2366 before + 13 mirror tests.) Guard exit 0 on every new/changed tree file. HEAD `1ea9df8`;
nothing committed; the reviewer's Q1 note stands — C5's writer hooks are not applied atop
uncommitted checkpoints.

### Prepared series, re-cut (owner executes, or signs (a) naming the messages)

1–4 as PROPOSED (unchanged; base `1ea9df8`); **5** `docs(research): verified-citation upgrades + governor register entry`
(Addendum D; or fold into 4); **6** `feat(ledger): live mirror (§8 C5) — append-shaped, fail-open counted, recorded switch; unwired`
— `src/life_agent/ledger/mirror.py`, the `sources/migrate/store/paths` amendments above,
`tests/test_ledger_mirror.py`; and the reviewer-ruling doc edits ride commit 4's file. Then,
on Q1–Q6 signed: **7** the writer hooks (C5 proper) → C6 → `r03-merge.md`.

**Waiting on the owner:** signatures Q1 (b, or a naming the messages), Q2, Q3 (append-shaped),
Q4 (a + `mirror_failures`), Q5 (recorded state), Q6 (thinkpad-only); Q14–Q15 from the
Addendum D section. **STOP.**

### Owner signatures — 2026-08-18 (post-review)

The owner approved the reviewer's recommendations as drafted in the section above:
**S12 — Q1 by option (b):** the owner executes the prepared five-commit series (the script
`~/.cache/life-agent/r03a-commit-series.sh`, prepared by the agent, base `1ea9df8`, each prefix
verified green in a scratch worktree — c1 9 · c2 9 · c3 49 · c5 62 ledger tests — then
removed); Addendum D folded into the docs commit (4). **S13:** Q2 keep T0 (indefinite) and T1
(to tranche end); Q3 append-shaped; Q4 (a) fail-open + `mirror_failures` in the manifest; Q5
`LIFE_AGENT_LEDGER_MIRROR=0`, state recorded (log line + manifest note); Q6 thinkpad-only C6,
"real traffic" = the owner's ask-path use over the settling interval. Q14 and Q15 (no
recommendation was made): the conservative reading is taken — dispositions §6.4 stays as the
historical injection and the OpenHands row's Verdict cell stays `INPUT + VERIFY`; both are
one-line edits if the owner later prefers otherwise. **C5 opens when the series has landed**
(HEAD to be recorded in r03).

Series execution note (owner ran the script; commits 1–3 landed as `eee0094`, `da3d76d`,
`809226d`): the armed pre-commit guard blocked commit 4 on `r00-census.md` — the line
*describing* the guard's own earlier false positive (an elided path in backticks) now trips the
hardened shape rule. Reworded with no semantic change (no value was ever present); commits 4–5
resumed via `~/.cache/life-agent/r03a-commit-series-resume.sh`.
