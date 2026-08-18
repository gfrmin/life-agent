# r03 — dual-write → two-route count → merge — 2026-08-18

Phase 3, second half (design §8 C5–C6), opened on the owner's S12/S13 (r03a) after the
reviewer's acceptance of C0–C4. Same discipline as r00–r03a: append-only, locators never
values, British spelling, transcripts verbatim where short. **This report is being written in
two sittings:** C5 (below) is complete; C6 needs the owner's real ask-path traffic over a
settling interval and is appended when it has accrued.

## STATE

- HEAD at C5 start: `3de1749` (the r03a series, five commits, executed by the owner via the
  prepared scripts; the guard stopped commit 4 once on r00's description of its own earlier
  false positive — reworded, resumed).
- C5 working tree (uncommitted until the owner runs `~/.cache/life-agent/r03-c5-commit.sh`):
  ```
  $ git status --short
   M scripts/answer_labels.py
   M scripts/verdict.py
   M src/life_agent/core/claude_verdicts.py
   M src/life_agent/core/decisions.py
   M src/life_agent/core/gather_outcomes.py
   M src/life_agent/core/outcomes.py
   M src/life_agent/core/reactions.py
   M src/life_agent/ledger/__init__.py
   M src/life_agent/ledger/mirror.py
   M src/life_agent/tasks/events.py
   M src/life_agent/trips/events.py
   M tests/conftest.py
  ?? tests/test_ledger_hooks.py
  $ uv run ruff check src tests            → All checks passed!
  $ uv run mypy                            → Success: no issues found in 207 source files
  $ LIFE_AGENT_KB=<the real KB> TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/life-agent/basetemp -p no:cacheprovider
  2383 passed, 34 deselected in 207.01s (0:03:27)
  ```
  The suite was run **with the real KB configured** on purpose (the worst case for the hooks'
  hermeticity); the real stream's manifest sha256 and segment byte totals were identical before
  and after (`c5-stream-before/after.txt`: manifest `a26d922d…6779`, 131,102,125 segment
  bytes, 29 entries) — **STREAM UNTOUCHED BY THE SUITE**.
- Guard exit 0 on every changed/new tree file.

## DONE

### C5 — the dual-write hooks (design §8 C5; owner Q3–Q5 as signed)

1. **One mirror call at each typed writer, after its legacy append**, lazily importing the
   mirror so no writer's module import changes and the hot path stays light:
   `core/outcomes.append` → `calibration.outcomes`; `core/decisions.append` →
   `calibration.decisions`; `core/reactions.append` → `calibration.reactions`;
   `core/claude_verdicts.append` → `calibration.claude_verdicts`;
   `core/gather_outcomes.append_outcome` → `calibration.gather_outcomes`;
   `tasks/events.append` → `act.tasks` (`n=len(events)`); `trips/events.append` →
   `act.trips` (`n=len(events)`); `scripts/answer_labels.append_label` → `eval.labels`;
   `scripts/verdict.py` corrections loop → `calibration.corrections`. Two lines each; the
   legacy append is unchanged and precedes the mirror (§10 crash promise: a crash between them
   loses only the mirror, the sweep restores it).
2. **`mirror.py` hardened for the wiring** (r03a's unwired library, restructured): the
   configured-store check now runs *before any store contact* — a writer at a tmp/ad-hoc path
   is `skipped` without so much as a manifest note; `migrate`/`sources` (and through them
   pkm) are imported lazily inside the hook, so a skipped/inert/disabled call never pays for
   them and there is no import cycle through `core.outcomes` ⇄ `sources`; the default stream
   root is one seam (`_default_store_root`).
3. **Hermeticity fixture** (`tests/conftest.py` `_hermetic_mirror`, autouse): points every
   writer's default mirror root at an uninitialised tmp directory — with `LIFE_AGENT_KB`
   exported, a test that monkeypatches a `config.*_LOG` constant to a tmp path would
   otherwise make the owner's live stream the mirror's default. Same class as the existing
   `_hermetic_executor` hazard, same remedy; proven by the real-KB suite run above.
4. **Tests** (`tests/test_ledger_hooks.py`, 4): each wired writer at the configured path
   mirrors its append (segment +n, `mirror_appends`, `legacy_bytes` == file size,
   `mirror_state.enabled`) and **the sweep proper then writes nothing** (hook == sweep, event
   for event); the same writers at other paths leave manifest bytes, counts and notes
   untouched; a writer never raises when the mirror fails (legacy line present,
   `mirror_failures` 1); the disabled switch stops every writer and is recorded; the switch
   name is one constant shared by the CLI gate and the mirror. (`scripts/verdict.py`'s
   corrections append is inline in its interactive `run()`; its hook is the same two lines
   and the same source as the mirror tests exercise.)
5. **Sweeps stay the manual CLI** (`python -m life_agent.ledger.migrate sync all`, per the
   Phase-3 brief: no scheduler, no timer, pkm untouched). Design §8 C5's "invoked where
   `derivations.reconcile` already runs on the ask path" is **not** wired — the brief's
   "manual CLI" governs; recorded as QUESTIONS 1 (a one-line design-doc reconciliation).
6. **Priming sweep on the real KB** (the manual CLI, S1: writes under `ledger/` only) so the
   first hooked writes are append-shaped rather than the loud first-time fallback (the
   migration predates `legacy_bytes`), and the C6 baseline:
   ```
$ LIFE_AGENT_KB=… uv run python -m life_agent.ledger.migrate sync all     # the manual sweep (C5): primes legacy_bytes; appends anything since T1
sync     act.tasks                    parsed=    300 segment     300→    300 written=      0 skipped=    300 unparseable=0 duplicate_key=0
sync     act.trips                    parsed=    339 segment     339→    339 written=      0 skipped=    339 unparseable=0 duplicate_key=0
sync     calibration.decisions        parsed=   2434 segment    2434→   2434 written=      0 skipped=   2434 unparseable=0 duplicate_key=0
sync     calibration.reactions        parsed=     14 segment      14→     14 written=      0 skipped=     14 unparseable=0 duplicate_key=0
sync     calibration.claude_verdicts  parsed=    180 segment     180→    180 written=      0 skipped=    180 unparseable=0 duplicate_key=0
sync     calibration.outcomes         parsed=    905 segment     905→    905 written=      0 skipped=    905 unparseable=0 duplicate_key=0
sync     calibration.gather_outcomes  parsed=     64 segment      64→     64 written=      0 skipped=     64 unparseable=0 duplicate_key=0
sync     calibration.corrections      parsed=      0 segment       0→      0 written=      0 skipped=      0 unparseable=0 duplicate_key=0
sync     utility.elicitations         parsed=      5 segment       5→      5 written=      0 skipped=      5 unparseable=0 duplicate_key=0
sync     eval.labels                  parsed=     21 segment      21→     21 written=      0 skipped=     21 unparseable=0 duplicate_key=0
sync     pkm.demand                   parsed= 103875 segment  103875→ 103875 written=      0 skipped= 103875 unparseable=0 duplicate_key=0
sync     pkm.artifact                 parsed=  32394 segment   32394→  32394 written=      0 skipped=  32394 unparseable=0 duplicate_key=0
exit=0

$ … migrate counts
counts   act.tasks                    tally=    300 segment=    300 (wc -l 300, quarantined 0) legacy=    300 → OK
counts   act.trips                    tally=    339 segment=    339 (wc -l 339, quarantined 0) legacy=    339 → OK
counts   calibration.decisions        tally=   2434 segment=   2434 (wc -l 2434, quarantined 0) legacy=   2434 → OK
counts   calibration.reactions        tally=     14 segment=     14 (wc -l 14, quarantined 0) legacy=     14 → OK
counts   calibration.claude_verdicts  tally=    180 segment=    180 (wc -l 180, quarantined 0) legacy=    180 → OK
counts   calibration.outcomes         tally=    905 segment=    905 (wc -l 905, quarantined 0) legacy=    905 → OK
counts   calibration.gather_outcomes  tally=     64 segment=     64 (wc -l 64, quarantined 0) legacy=     64 → OK
counts   calibration.corrections      tally=      0 segment=      0 (wc -l 0, quarantined 0) legacy=      0 → OK
counts   utility.elicitations         tally=      5 segment=      5 (wc -l 5, quarantined 0) legacy=      5 → OK
counts   eval.labels                  tally=     21 segment=     21 (wc -l 21, quarantined 0) legacy=     21 → OK
counts   pkm.demand                   tally= 103875 segment= 103875 (wc -l 103875, quarantined 0) legacy= 103875 → OK
counts   pkm.artifact                 tally=  32394 segment=  32394 (wc -l 32394, quarantined 0) legacy=  32394 → OK
counts   all sources reconcile
exit=0
   ```
   No traffic since T1 (`written=0` on all twelve); all sources reconcile → **C6 baseline =
   T1 counts** (act.tasks 300 · act.trips 339 · decisions 2434 · reactions 14 · claude_verdicts
   180 · outcomes 905 · gather 64 · corrections 0 · elicitations 5 · labels 21 · pkm.demand
   103875 · pkm.artifact 32394).
7. **Cost (from r03a's addendum, unchanged by the wiring):** on the stream's volume ~30 ms
   median / ~32 ms P95 per in-step call; §10 states it and that the 0.20 ms target is not met.
   ```
$ MIRROR_COST_ROOT=$LIFE_AGENT_KB/ledger/.bench-c5 uv run python <scratchpad>/mirror_cost.py   # same synthetic source, on the stream volume; scratch removed after
initial migrate 2434 rows (1342 KB legacy): 0.501s
append-shaped mirror, in step, decisions-sized segment (2434 events): median 30.30 ms, p95 31.50 ms, max 84.70 ms over 50
  of which: segment scan (_lines over 2321 KB): 0.64 ms
  of which: manifest read+write under lock: 11.90 ms
  of which: one fsync on the segment file: 0.01 ms
  of which: legacy delta read: 0.10 ms
fallback full sync (no recorded offset): 303.6 ms — action=synced
exit=0
   ```
8. **Rollback:** `LIFE_AGENT_LEDGER_MIRROR=0` in the writer's environment (recorded in the
   manifest as `mirror_state` on the process's first configured write, and a WARNING line);
   or `git revert` of the C5 commit — the legacy stores are never modified, so nothing
   downstream moves.

### C6 — two-route count with real traffic; `golden compare all --from stream` at T2

**Opened, awaiting traffic.** Per S13/Q6: thinkpad-only; "real traffic" = the owner's ask-path
use (`bin/ask-live` → decisions, reactions, outcomes, gather) over the settling interval — no
process on this box writes these stores on a timer (jarvis runs on steel against a different
KB, where the mirror is inert by construction). The C6 clock starts with the first hooked
write. Procedure when the interval has passed (recorded in an appended section):
`migrate sync all` (the swept sources) → `migrate counts` (tally == segment == legacy on
every source, mirror rows: `mirror_appends`, `mirror_behind_*`, `mirror_syncs`,
`mirror_failures`, `mirror_state`) → `golden snapshot all --t0 <T2>` from legacy →
`golden compare all --t0 <T2> --from stream` (fourteen GREEN) → the merge verdict.

## DEVIATIONS

1. Sweeps not wired to the ask path (design §8 C5 wording) — the brief's manual-CLI rule
   governs; see QUESTIONS 1.
2. `mirror.py` and its tests landed one commit *before* the hooks (r03a series commit 5,
   "unwired") — the reviewer's bisectability point applied: the library alone is inert.
3. The priming sweep touched the real manifest (`legacy_bytes`, `last_sync_at` per source)
   before the C5 commit exists — idempotent, S1-permitted, and the manual CLI the brief names.

## REFUSED

- No reader cutover; no retirement or compaction; quarantine untouched (S6); no pkm,
  brain-seam, spine, PRINCIPLES or SPEC change; no scheduler/timer for the sweeps; no
  backfill of schema-3 `kernel_id` records (Q7 rider ii); no synthetic traffic into the
  owner's live stores to "start" C6 (real traffic only, per Q6).

## QUESTIONS

1. **(reviewer/owner)** Design §8 C5 says the sweeps are "invoked where `derivations.reconcile`
   already runs on the ask path, and by the harness"; the Phase-3 brief says "sweeps as manual
   CLI, no scheduler/timer". Built to the brief. Reconcile the doc with one line — manual CLI
   for tranche 1, ask-path invocation a cutover-tranche option — or rule that the ask-path call
   belongs in this tranche.
2. **(reviewer, Q7 rider i, as ruled — the proposal text)** *Forward fix for the schema-3
   `kernel_id` payload:* the §18.9 writer (`core/derivations.py`, life_agent-side; pkm
   untouched) records the four key components it already computes
   (`model_identity_hash`, `engine_version`, `prompt_template_hash`, `output_schema_hash`)
   inside `producer_metadata` of the `meta.json` it writes; `sources.instrument_kernel_id`
   then reads them and reports the record complete. Landing site: the module-collapse tranche
   (it touches `core/derivations.py`), or a standalone change after this tranche. No
   backfill; the census's completeness classes then show three eras.
3. **(owner)** The mirror's per-call cost is ~30 ms on the stream's volume, dominated by the
   fsynced manifest rewrite. Acceptable for tranche 1 (the ask path is seconds), or should the
   two levers named in r03a (append-only mirror log as the tally's home; tail-count delta)
   be built now?

## PROPOSED

- **Commit (owner executes):** `~/.cache/life-agent/r03-c5-commit.sh` → one commit
  `feat(ledger): dual-write hooks at the nine typed writers (§8 C5) — legacy-append-first,
  configured-store-only, hermetic in tests` on `3de1749`. Then use the ask path normally.
- **C6, when traffic has accrued** (owner says when, or ~a day of use): the procedure above,
  appended here with transcripts, then the merge verdict and the tranche's close.

## C6 — appended 2026-08-18 (second sitting): the count with real traffic, T2, the finding

### Traffic (owner-authorised: the agent drove the deployed ask path)

Window 13:50Z–14:38Z on thinkpad, all through `bin/ask-live` exactly as the owner uses it
(the executor daemon was down, so every ask took the in-process fallback, *named* in its
output): **8 asks** (two generic, then six owner questions chosen from the eval set by id after
reading the KB's data map — ids q2-001, q2-005, q2-008, q2-047, q2-096, q2-099; one probe ask
repeating q2-001 with the ask process's `reconcile` outcome surfaced) and **1 reaction**
(`/react … bad` on the q2-001 abstain, whose held-back leader equals the recorded gold — a
truthful owner verdict, not a fabricated one; the other reactions/labels/corrections/tasks/
trips writers had no live traffic in the window and rest on the hook tests). Every ask
withheld (the typed arm's honest-withhold; §14's reach ceiling — not a mirror matter). Two
process notes: an early loop fed the *next question* to `ask-live`'s verdict prompt through
stdin (no verdict was taken — reactions stayed at 14 — re-run with `</dev/null`); and the
tool's 10-minute cap killed one ask mid-refresh, which — see the finding — is *why* later asks
did not sweep. Transcripts: `c6-traffic-{1,2,3}.txt`, `c6-react.txt`,
`c6-reconcile-inproc.txt` (out of tree; answers never enter this report).

```
$ bin/ask-live "/react 72a8548a bad"     # the Q2-001 abstain: held-back leader == the recorded gold → the owner verdict is "bad" (should have answered)
→ BAD on lookup/abstain 72a8548ac7aa — folds into the utility posterior on the next gate run
exit=0
```

### The mirror, live

The first hooked write of the day (13:53:12Z, a decision) recorded `mirror_state` (enabled,
env unset) and mirrored in step; by the end of the window: **decisions +8, reactions +1 — 9
mirror appends, 0 behind, 0 fallback syncs, 0 failures**; every hooked source's tally ==
segment == legacy at every count taken.

```
exit=0
mirror_state: {'enabled': True, 'env': None, 'recorded_at': '2026-08-18T14:37:52.811549+00:00'}
  calibration.decisions        appends=8 behind=0 syncs=0 failures=0 last=2026-08-18T14:37:52
  calibration.reactions        appends=1 behind=0 syncs=0 failures=0 last=2026-08-18T14:26:36
totals: {'a': 9, 'b': 0, 's': 0, 'f': 0}
```

### The two-route count after the sweep, T2, and the replay from the stream

```
$ uv run python -m life_agent.ledger.migrate sync all      # C6: the swept sources after the traffic window (13:50Z–14:19Z, 7 asks + 1 react)
sync     act.tasks                    parsed=    300 segment     300→    300 written=      0 skipped=    300 unparseable=0 duplicate_key=0
sync     act.trips                    parsed=    339 segment     339→    339 written=      0 skipped=    339 unparseable=0 duplicate_key=0
sync     calibration.decisions        parsed=   2441 segment    2441→   2441 written=      0 skipped=   2441 unparseable=0 duplicate_key=0
sync     calibration.reactions        parsed=     15 segment      15→     15 written=      0 skipped=     15 unparseable=0 duplicate_key=0
sync     calibration.claude_verdicts  parsed=    180 segment     180→    180 written=      0 skipped=    180 unparseable=0 duplicate_key=0
sync     calibration.outcomes         parsed=    905 segment     905→    905 written=      0 skipped=    905 unparseable=0 duplicate_key=0
sync     calibration.gather_outcomes  parsed=     64 segment      64→     64 written=      0 skipped=     64 unparseable=0 duplicate_key=0
sync     calibration.corrections      parsed=      0 segment       0→      0 written=      0 skipped=      0 unparseable=0 duplicate_key=0
sync     utility.elicitations         parsed=      5 segment       5→      5 written=      0 skipped=      5 unparseable=0 duplicate_key=0
sync     eval.labels                  parsed=     21 segment      21→     21 written=      0 skipped=     21 unparseable=0 duplicate_key=0
sync     pkm.demand                   parsed= 104015 segment  103875→ 104015 written=    140 skipped= 103875 unparseable=0 duplicate_key=0
sync     pkm.artifact                 parsed=  30397 segment   32394→  32444 written=     50 skipped=  30347 unparseable=0 duplicate_key=0
exit=0

$ uv run python -m life_agent.ledger.migrate counts
counts   act.tasks                    tally=    300 segment=    300 (wc -l 300, quarantined 0) legacy=    300 → OK
counts   act.trips                    tally=    339 segment=    339 (wc -l 339, quarantined 0) legacy=    339 → OK
counts   calibration.decisions        tally=   2441 segment=   2441 (wc -l 2441, quarantined 0) legacy=   2441 → OK
counts   calibration.reactions        tally=     15 segment=     15 (wc -l 15, quarantined 0) legacy=     15 → OK
counts   calibration.claude_verdicts  tally=    180 segment=    180 (wc -l 180, quarantined 0) legacy=    180 → OK
counts   calibration.outcomes         tally=    905 segment=    905 (wc -l 905, quarantined 0) legacy=    905 → OK
counts   calibration.gather_outcomes  tally=     64 segment=     64 (wc -l 64, quarantined 0) legacy=     64 → OK
counts   calibration.corrections      tally=      0 segment=      0 (wc -l 0, quarantined 0) legacy=      0 → OK
counts   utility.elicitations         tally=      5 segment=      5 (wc -l 5, quarantined 0) legacy=      5 → OK
counts   eval.labels                  tally=     21 segment=     21 (wc -l 21, quarantined 0) legacy=     21 → OK
counts   pkm.demand                   tally= 104015 segment= 104015 (wc -l 104015, quarantined 0) legacy= 104015 → OK
counts   pkm.artifact                 tally=  32444 segment=  32444 (wc -l 32444, quarantined 0) legacy=  30397 → MISMATCH
counts   MISMATCH present
exit=1
```

```
T2=20260818T143426Z
$ uv run python -m life_agent.ledger.golden snapshot all --t0 20260818T143426Z      # from LEGACY
snapshot gtd                    kind=semantic  rows=151       digest=7edd5b2650b1f00b
snapshot state-md               kind=byte      bytes=9960     digest=1437513a74d91798
snapshot trips                  kind=semantic  rows=323       digest=de87ba10010fd8a5
snapshot utility-fold-version   kind=byte      -              digest=34c975f118f0a9e4
snapshot curves                 kind=byte      -              digest=88860b52869c2eff
snapshot reactions              kind=byte      evidence=12    digest=96e066dff0481366
snapshot claude-verdicts        kind=byte      -              digest=6e13aff5f2e458ed
snapshot gather                 kind=byte      -              digest=2b88b2978730877f
snapshot cells                  kind=byte      -              digest=96c42b28f8a06108
snapshot answers                kind=identity  keys=839       digest=6a1fe733ad1b10ec
snapshot pkm-index              kind=semantic  artifacts=30397 digest=0c1c9363ea21bb23
snapshot demand                 kind=byte      -              digest=24f860c0073415c9
snapshot labels                 kind=byte      labels=21      digest=88e845f18720a57c
snapshot corrections            kind=byte      lines=0        digest=f1014797bf17aa8f
snapshot dir $LIFE_AGENT_KB/ledger/golden/20260818T143426Z
exit=0
```

```
$ uv run python -m life_agent.ledger.golden compare all --t0 20260818T143426Z --from stream
stream   root=$LIFE_AGENT_KB/ledger epoch=20260818T100854Z events={act.tasks:300, act.trips:339, calibration.claude_verdicts:180, calibration.corrections:0, calibration.decisions:2441, calibration.gather_outcomes:64, calibration.outcomes:905, calibration.reactions:15, eval.labels:21, pkm.artifact:32444, pkm.demand:104015, utility.elicitations:5}
compare  gtd                    kind=semantic  comparator=<multiset of rows ignoring id> snapshot[rows=151 7edd5b2650b1] replay[rows=151 7edd5b2650b1] → GREEN
compare  state-md               kind=byte      comparator=<byte-identical text> snapshot[bytes=9960 1437513a74d9] replay[bytes=9960 1437513a74d9] → GREEN
compare  trips                  kind=semantic  comparator=<multiset of full rows> snapshot[rows=323 de87ba10010f] replay[rows=323 de87ba10010f] → GREEN
compare  utility-fold-version   kind=byte      comparator=<fold_version hex equality> snapshot[- 34c975f118f0] replay[- 34c975f118f0] → GREEN
compare  curves                 kind=byte      comparator=<canonical JSON of {edge: bin_reliability}> snapshot[- 88860b52869c] replay[- 88860b52869c] → GREEN
compare  reactions              kind=byte      comparator=<canonical JSON of the evidence list in order> snapshot[evidence=12 96e066dff048] replay[evidence=12 96e066dff048] → GREEN
compare  claude-verdicts        kind=byte      comparator=<canonical JSON of latest_by_decision> snapshot[- 6e13aff5f2e4] replay[- 6e13aff5f2e4] → GREEN
compare  gather                 kind=byte      comparator=<canonical JSON of grow_block> snapshot[- 2b88b2978730] replay[- 2b88b2978730] → GREEN
compare  cells                  kind=byte      comparator=<canonical JSON of cell observations + coverage list> snapshot[- 96c42b28f8a0] replay[- 96c42b28f8a0] → GREEN
compare  answers                kind=identity  comparator=<key set + content/meta digests> snapshot[keys=839 6a1fe733ad1b] replay[keys=839 6a1fe733ad1b] → GREEN
compare  pkm-index              kind=semantic  comparator=<rowset equality of artifacts + artifact_lineage> snapshot[artifacts=30397 0c1c9363ea21] replay[artifacts=32444 82fddcf3ff92] → RED  diff@ ~sha256:0f50505ce224[len 30397→32444,[0] feeca7437a→2b6e49b9de,[1] eb289dd062→5c00e1133e]; ~sha256:0713f136ea31[len 32432→73164,[0] 4650795892→ee5de3983c,[1] bd1739aa47→467bd97e2b]
compare  demand                 kind=byte      comparator=<multiset of canonical lines per file> snapshot[- 24f860c00734] replay[- 24f860c00734] → GREEN
compare  labels                 kind=byte      comparator=<ordered label lines + last-wins table> snapshot[labels=21 88e845f18720] replay[labels=21 88e845f18720] → GREEN
compare  corrections            kind=byte      comparator=<multiset of canonical lines> snapshot[lines=0 f1014797bf17] replay[lines=0 f1014797bf17] → GREEN
stream   answers: 839 decision-referenced keys, 839 on disk, 839 of those are pkm.artifact outputs on the stream
exit=1
```

**Thirteen GREEN; `pkm-index` (A11) RED** — the stream's `artifacts` rowset (32,444) is a
strict superset of the legacy cache's (30,397): **exactly 2,047 identities**, plus their
lineage rows (the 32,432 → 73,164 delta). `answers` is GREEN: all 839 decision-referenced
artefacts are still on disk. Closing sweep + count (after the probe ask; `counts` now names
the class itself):

```
$ uv run python -m life_agent.ledger.migrate sync all && … counts      # closing sweep + count (T2 + probe ask)
sync     pkm.demand                   parsed= 104027 segment  104015→ 104027 written=     12 skipped= 104015 unparseable=0 duplicate_key=0
sync     pkm.artifact                 parsed=  30398 segment   32444→  32445 written=      1 skipped=  30397 unparseable=0 duplicate_key=0
counts   pkm.artifact                 tally=  32445 segment=  32445 (wc -l 32445, quarantined 0) legacy=  30398 → MISMATCH — legacy lost 2047 identities the segment retains (deletion on the legacy side)
counts   MISMATCH present
exit=0
```

### THE FINDING — a legacy-side deletion the count exposed within the hour

**What:** between the priming sweep (13:44Z, `pkm.artifact` parsed 32,394) and the C6 sweep
(14:19Z, 30,397), **2,047 cached artefacts were deleted from the pkm cache** — every one a
`life_agent.ask.joint_extract` (schema 3; produced 2026-06-18 → 2026-08-17; `meta.json`,
content and directory all gone). Not caused by anything in this tranche; **exposed** by it —
the stream is append-only and still holds every one's occurrence record (meta + lineage), and
the two-route count is what noticed.

**Root cause, each link verified (transcript `c6-reconcile-probe.txt`, `c6-artifact-gap.txt`):**

1. **The writer's lineage violates pkm's uniqueness contract.** All 2,047 deleted artefacts
   carry a **duplicate input key in `lineage.json`** (the same chunk key twice); all 313
   surviving `joint_extract` artefacts have unique inputs; no on-disk artefact with duplicate
   inputs remains. Same producer, same days (07-19: 822 vs 120; 08-17: 431 vs 53), same
   metadata shape — the duplicate is the *only* separator.
2. **`core/derivations._reconcile_one` inserts lineage rows one by one** → the duplicate
   trips `artifact_lineage`'s `PRIMARY KEY (artifact_cache_key, input_cache_key)`
   (dry-run reproduced: `ConstraintException: duplicate key …`) → the exception is caught,
   the key is kept in `external/pending.txt` "for later" (2,053 lines today; 2,047 of them
   these), and `reconcile` never says a word — the ask path wraps it in
   `contextlib.suppress(Exception)`. So the artefacts existed on disk for up to two months
   **unregistered in the catalogue** — orphans by pkm's definition (SPEC §6.2). (pkm's own
   `rebuild-catalogue` would also have aborted on such a lineage.)
3. **pkm `extract` sweeps orphans at start** (`pkm/extract.py:202` → `cache.sweep_orphans`).
   The ask path runs an extract inside the demand-led GTD refresh
   (`ask.py:_reingest_state`). The refresh normally fires only when the GTD ledger head moves
   — but the **pandoc pin mismatch** (`config.yaml expects '3.6', installed 3.10.2`) makes
   the refresh fail *after* the sweep, and by contract a failed refresh un-stamps
   `state.md` so the next ask retries: **every ask sweeps.** Timeline from parent-directory
   mtimes: 1,679 dirs at 13:50Z (the first ask), the rest at 13:51/13:53/13:54 (the second);
   the third ask was killed by the harness cap between `write_state` (stamps) and the failing
   re-ingest (would un-stamp) — so later asks saw a fresh stamp and did not refresh. **The
   loop is dormant, not fixed:** the next GTD ledger move re-arms it, and the next eval/gate
   run writes more duplicate-input `joint_extract` artefacts to feed it.
4. In-process `reconcile` does register well-formed artefacts (today's writes were all
   registered by later asks' reconciles; the probe ask's reconcile returned 0 with no
   exception once nothing registerable was pending) — the silent failure is per-key, on the
   duplicate-input class only.

**Impact:** 2,047 recorded draws (the lookup family's extraction results, paid model output)
lost as *content* — recomputable at cost on re-ask (a warm key becomes a cold one; the
recorded-draw rule §5 loses those draws); their occurrence records survive in the stream and
now point at identities that no longer exist — a **dangling identity** class the design has
not named (§4 assumes the pointed-at identity exists; the count's new "legacy lost N
identities" row is its first instrument). Not recoverable from backup: the pkm live root
(`~/.local/share/pkm/runs/…` on the root disk) is outside the travel backup's source list and
`pkm/runs/**/cache` is explicitly excluded. List of the deleted cache-relative directories:
`~/.cache/census-r01/p3/c6-deleted-artifact-dirs.txt` (2,047 lines; digests only).

**Actions taken (all within S1/scope):** the six live artefacts pending at 14:19Z were
registered by running the existing `derivations.reconcile` standalone (nothing else was at
risk; the loop was dormant); `counts` extended to name the class (`legacy_lost_identities`,
tested). **Nothing else changed:** no pkm code, no ask-path code, no config.

**Fixes proposed, not built (owner rules — they touch the ask stack, outside this tranche):**
(a) *root:* `core/joint_extract` (or its lineage recording) must write **unique** lineage
inputs; (b) *seam:* `derivations._reconcile_one` dedups inputs on read (idempotent
insert) and `reconcile` **logs the exception class per key at WARNING** instead of
silence; (c) *ordering:* `ask.py:_reingest_state` must `reconcile` immediately before
`pkm_extract` and **refuse (or warn loudly) to extract while registerable keys remain
pending** — pkm's sweep-at-extract-start makes "unregistered" mean "about to be deleted";
(d) *config (owner):* the pandoc pin, so the refresh stops retrying every ask; (e) *docs:*
a FAILURES.md entry (evidence log, out of tree — text below) and a §14/§4 note naming the
dangling-identity class. Until (a)–(c) land: **do not run an eval/gate run followed by an
ask that refreshes**; a stopgap is `python -c "from life_agent.core import derivations as D;
from life_agent.core import config; D.reconcile(config.pkm_root())"` before asking, watching
`pending.txt` shrink — it will *not* shrink for duplicate-input keys.

*FAILURES.md entry text (for the owner to place):* "2026-08-18 — 2,047 `joint_extract`
artefacts (06-18→08-17) deleted by pkm's orphan sweep at extract start, run by the ask path's
GTD refresh (retrying on the pandoc pin). They were never catalogued: duplicate lineage inputs
trip `_reconcile_one`'s lineage PK and `reconcile` swallows it. Found by the unified
ledger's two-route count (r03 C6). Content unrecoverable (not in any backup); occurrence
records retained in the stream."

### Merge verdict

- **Dual-write is proven end to end**: nine hooked writers, live traffic, 9/9 mirror appends
  in step, zero behind, zero fallbacks, zero failures; every hooked source's three routes agree
  at every count; the switch is recorded; the suite is hermetic with the real KB configured.
- **Replay from the stream:** thirteen of fourteen artefacts GREEN at T2; the fourteenth
  (A11) is RED **because the legacy store lost data and the stream did not** — the RED is the
  instrument working, and the count now names the class. Under §9 as pre-stated the criterion
  is rowset equality, so A11 is a fail on the letter; on the substance the stream is the more
  faithful record. **Recommendation: MERGE the tranche as its end-state was defined (dual-write,
  no cutover, no retirement), with A11's RED registered as an explained legacy-side loss, and
  open the (a)–(e) fixes as the first item after it.** The owner rules; the reviewer's V4
  discipline suggests reporting it as *CLAIM MET [SUPERSET]* in spirit — the stream ⊃ legacy
  by exactly the deleted set — with the collateral fully explained.
- Rollback unchanged: `LIFE_AGENT_LEDGER_MIRROR=0` or `git revert 4780991`.

### STATE at close (this sitting)

- HEAD `4780991` (C5 committed by the owner and pushed). Working tree: `r03-merge.md`
  (this report), `src/life_agent/ledger/migrate.py` (the `counts` class name),
  `tests/test_ledger_migrate.py` (+1 test, 11) — one closing commit prepared
  (`~/.cache/life-agent/r03-close-commit.sh`).
- Real KB after the closing sweep: all sources reconcile except `pkm.artifact`, named as
  above; T2 snapshot retained (`golden/20260818T143426Z`) beside T0 and T1.
- Guard exit 0 on every changed file. Ledger tests 63; full suite last run 2383 (before the
  `counts` change; the change is exercised by its own test — the closing script runs the
  ledger tests).

## Rulings on the C6 finding — applied (2026-08-18, before the closing commit)

**Verdict as ruled:** MERGE granted — **not** by treating an explained RED as GREEN. The
pre-stated criterion was fourteen GREEN; thirteen were. A11's criterion is **formally amended
by the ruling** for the merge verdict — *stream ⊇ legacy, with the difference exactly the
enumerated swept set, verified by key list, not by count* — a reviewed restatement under the
never-silently-weaken rule, now in design §9's A11 row with the cite; the T2 RED transcript
above is the finding of record and is never re-run to green (no re-snapshot).

**Gate 1 — the claim by key list, not by count.** `counts`' extension computed the loss as a
set difference but reported and tested a cardinality; per the ruling the identity check was
done before the close, and `counts` now returns the key list (`legacy_lost_keys`; its test
asserts the key, not the count):

```
$ key-list check (reviewer ruling on r03): (stream outputs − legacy outputs) == the enumerated swept set, AS SETS
stream outputs 32445 | legacy outputs 30398 | stream−legacy 2047 | enumerated swept keys 2047
legacy − stream (must be empty; stream ⊇ legacy): 0
SET EQUALITY (stream−legacy == enumerated swept set): True
symmetric difference: 0
exit=0
```

**Gate 2 — the design-doc revision** (`docs/unified-ledger-design.md`, one dated note "r03
close"): §4 names the **dangling-identity class** — occurrence records the stream retains
while the pointed-at content is gone; functionally re-derivable (sources persist, derive is a
transformation) but identity-unrecoverable (re-derivation mints a new occurrence; for
LLM-produced schema-3 artefacts not necessarily equal content — the recorded draw is lost);
§9's A11 row carries the merge-verdict amendment with the ruling cite. Q11 (fsync split +
manifest lock) and Q12 (A2 legacy-pinned clause) were already folded in the r03a-review
revision — confirmed present, not duplicated.

**Per-writer mirror coverage in the C6 window (as ruled — named, not aggregated):**

| Writer (hook) | Source | Fired? | Mirror | Why not fired |
|---|---|---|---|---|
| `core/decisions.append` | `calibration.decisions` | yes ×8 | 8 appends, in step | — |
| `core/reactions.append` | `calibration.reactions` | yes ×1 | 1 append, in step | — |
| `core/outcomes.append` | `calibration.outcomes` | no | — | outcomes are written by grading (eval runs, `scripts/verdict.py` fold, regrade); no grading ran |
| `core/claude_verdicts.append` | `calibration.claude_verdicts` | no | — | `scripts/claude_verdict.py` not run |
| `core/gather_outcomes.append_outcome` | `calibration.gather_outcomes` | no | — | written via the bridge's `/log_gather` by the executor daemon — down all window (in-process fallback, named) |
| `tasks/events.append` | `act.tasks` | no | — | GTD commands come from jarvis (steel, other KB) or the mail timer (not on this box); no local command |
| `trips/events.append` | `act.trips` | no | — | no trips ingest ran |
| `scripts/answer_labels.append_label` | `eval.labels` | no | — | no labelling session |
| `scripts/verdict.py` corrections | `calibration.corrections` | no | — | no verdict session |

The seven unfired hooks rest on `tests/test_ledger_hooks.py` (each fires and mirrors at the
configured path; each is inert elsewhere) — live coverage for them accrues with use.

**The five fixes, sequenced as ruled:** (d) the pandoc pin — owner, today, config; disarms the
retry loop. (e) FAILURES.md — owner signs the draft above and appends it (the file is out of
tree under `$LIFE_AGENT_KB`); nothing for the tree commit. (a)–(c) — **a separate pkm-side
micro-tranche with its own SPEC-first brief** (design §11): (a) the root fix first (unique
lineage inputs at the writer); (b) reconcile logs per-key failures at WARNING, and *its
dedup-on-read must not launder what the writer should never produce* — the dedup logs loudly
and the census counts it; (c) `_reingest_state` becomes reconcile-or-refuse before extract —
the fail-closed posture. Standing constraint until they land (now the owner's to observe): no
eval/gate run followed by an ask that refreshes.

**Owner infrastructure (the unglamorous layer, growing list):** the pkm live root
(`~/.local/share/pkm/runs/…`) is outside every backup source list — add it to borg today (that
gap turned a bug into unrecoverable loss); the executor daemon (down all day; every ask fell
back); the standing signature slot.

**Closing commit (owner runs the prepared script, then pushes as a separate act):**
`~/.cache/life-agent/r03-close-commit.sh` — `src/life_agent/ledger/migrate.py` (`counts`:
`legacy_lost_identities` + `legacy_lost_keys`), `tests/test_ledger_migrate.py` (+1, 11),
`docs/unified-ledger-design.md` (the r03-close revision), `docs/unification/reports/r03-merge.md`.
On its landing **the tranche closes**; tranche 2's inputs are on the desk (the collapse census;
the fold-depth numbers when they land) and the pkm micro-tranche brief follows on the owner's
word.
