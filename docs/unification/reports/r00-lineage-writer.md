# r00 — lineage-writer (pkm lineage micro-tranche, Phase A) — 2026-08-19

Phase A of the pkm lineage micro-tranche: the writer, the seam, the reconciler, the caller —
life_agent-side, no SPEC change. The operative brief is
[`r04-stocktake.md`](./r04-stocktake.md) **Appendix A, verbatim**, signed on 2026-08-19 by the
owner's opening document (quoted in §Opening below). Same discipline as r00–r04: append-only,
locators never values, British spelling, transcripts verbatim where short, commits by
owner-executed prepared scripts (S12). **STOP after this report** — Phase B opens on its review
and on the committed SPEC text (S-L2).

## Opening — the signed brief (verbatim extracts, for a self-standing report)

The owner's opening document, 2026-08-19: *"The operative brief is r04-stocktake.md Appendix A,
verbatim … This document opens it: it carries the owner's signatures, the reviewer's rulings,
and four deltas. Where this document and Appendix A conflict, this document wins and the
conflict is recorded in the report's DEVIATIONS."*

- **S-L1 — signed.** *"Phase A is authorised as drafted. Phase B opens only after the r00 STOP
  is reviewed and S-L2's SPEC text is committed under the SPEC's own amendment rule."*
- **S-L2 — signed: Option A plus the §18.9 rider**, both exactly as drafted in Appendix A B1.
  *"Deletion never follows from index lag."*
- **S-L3 — signed as ruled: drop-with-WARNING plus the `dead` count.** Reviewer rider, binding:
  *"the WARNING names the key and states that the stream retains the occurrence record … Test
  asserts both parts of the message shape (locator form, never content)."*
- **S-L4 — signed.** Reports `r00-lineage-writer.md` (this) and `r01-lineage-sweep.md`
  (Phase B); convention `rNN-<tag>-<phase>.md` within a tagged tranche.
- **Reviewer rulings folded in:** (1) A0 is the first commit of Phase A; until its
  before/after-mtime proof lands, the interim constraint binds (suite runs without
  `LIFE_AGENT_KB` exported) — the proof run is the first suite run with it exported since the
  constraint was imposed, to be said so in the transcript; (2) A3's dedup-on-read doctrine
  stands: loud, per-key, counted in `migrate counts` via `lineage_duplicate_inputs`; (3) no
  re-derivation of the 2,047; (4) commits by owner-executed scripts, one script per STOP,
  commit and push separate acts.
- **Preconditions:** the pandoc pin (owner item (d)) — *"If still mismatched: Phases A0–A4
  proceed regardless … but A5's live witness does not run"*; the backup finding gates B2's
  live witness (not Phase A); the standing constraint (no eval/gate run followed by a
  refreshing ask) remains in force until lifted per A5 or B3.

## STATE

- **HEAD `b8f014d`** (= `origin/master`), not `f4d1ab0`: three PRs merged since the r04
  stock-take (`#70` fix/null-read-failopen — `e4bb311`; `#71` fix/dangling-shas-post-rewrite —
  `100dd5e`; `#72` fix/shadow-test-record-waits — `2bb6ead`). None touches this tranche's
  files; `src/life_agent/core/lookup.py` changed on three comment lines only (a sha re-resolve),
  so every `lookup.py` locator in Appendix A still holds (`:593-597`, `:1110-1112` before this
  tranche's edits). `docs/unification/reports/r04-stocktake.md` is still untracked — its
  prepared commit script (`~/.cache/life-agent/r04-stocktake-commit.sh`, base `f4d1ab0`) is
  superseded: the r00 series script below commits it as its sixth commit.
- **The pandoc pin (precondition):** `PKM_CONFIG` (`~/.config/life-agent/pkm.yaml`)
  `extractors.pandoc.version: "3.6"`; `pandoc --version` → `pandoc 3.10.2`. **MISMATCHED →
  A5 does not run** (per the opening document). Owner item (d) stands.
- **Backup (precondition for B2 only):** not re-audited here; r04 owner Q1 stands.
- **Working tree at the STOP** (uncommitted until the owner runs the series script):
  ```
  $ git status --short
   M docs/interaction-contract.md
   M scripts/ask.py
   M src/life_agent/core/derivations.py
   M src/life_agent/core/joint_extract.py
   M src/life_agent/core/lookup.py
   M src/life_agent/ledger/migrate.py
   M src/life_agent/ledger/sources.py
   M tests/conftest.py                      (added by the post-review Q1/Q2 follow-on, below)
   M tests/test_ask.py
   M tests/test_ask_gtd_refresh.py
   M tests/test_derivations.py
   M tests/test_joint_extract.py
   M tests/test_ledger_migrate.py
   M tests/test_lookup.py
  ?? docs/unification/reports/r00-lineage-writer.md
  ?? docs/unification/reports/r04-stocktake.md
  ```
- **Suite / ruff / mypy at the tip** (`LIFE_AGENT_KB` exported — see A0's proof for why that is
  now safe; `TMPDIR`/`--basetemp` under `~/.cache`, `-p no:cacheprovider`):
  ```
  $ uv run pytest -q ...
  2401 passed, 34 deselected in 138.67s (0:02:18)        exit=0
  (live root after: catalogue.duckdb and external/pending.txt mtimes unchanged at 06:07:11 / 06:08:54;
   files newer than the run's marker under the pkm root + the KB: 0)
  $ uv run ruff check src tests scripts   → All checks passed!
  $ uv run mypy                           → Success: no issues found in 207 source files
  ```
- **Bisectability:** every intermediate tree of the series (T1…T5, §DONE/Commit series) was
  checked out in a disposable detached worktree
  (`lineage-r00-bisect`, under the sanctioned worktrees directory; removed after) and is green on the
  targeted set (the eight test files the tranche touches or exercises) + full ruff + full mypy:
  ```
  T1 9ccb08a5: 155 passed   T2 926a6d3d: 158 passed   T3 442e43d6: 159 passed
  T4 90ffe67a: 163 passed   T5 a5b625b9: 166 passed
  T1…T5: ruff=All checks passed!  mypy=Success: no issues found in 207 source files
  ```
- **PII guard:** exit 0 on every changed file, per file (`.githooks/pii_check.py <file>` with
  `LIFE_AGENT_KB`) and in staged mode over the whole series (`--staged` → exit 0).
- **Live-root / KB touches this session, all disclosed:** (i) two full-suite runs with
  `LIFE_AGENT_KB` exported (A0's proof and the tip run) — **zero** files newer than a marker
  under the pkm root and under the KB after each; (ii) `python -m life_agent.ledger.migrate
  counts` (read-only; exit 1 = the known `pkm.artifact` MISMATCH); (iii) **no** eval/gate run,
  **no** ask — the standing constraint held (`calibration.decisions` legacy 2,442, unchanged
  from r04). Nothing else read or written under `$LIFE_AGENT_KB` or the pkm root.
- **A finding about the interim constraint itself (A0's RED):** the suite's reach into the
  live pkm root did **not** depend on `LIFE_AGENT_KB` — it ran through `PKM_CONFIG`'s
  *default* path (`core/config.py:15` → `~/.config/life-agent/pkm.yaml`, which exists on this
  machine) → `ask._pkm_root()` → `D.reconcile(root)` at `scripts/ask.py:1515-1519` (now
  `:1544-1547`). So "run pytest without `LIFE_AGENT_KB`" (r04's operational note; the opening
  document's ruling 1) never covered it: the r04 suite run that rewrote the live
  `pending.txt` was such a run. A0 closes the reach regardless of either variable; the
  hermetic RED transcript below is the proof of the mechanism.

## DONE

### A0 — the suite cannot reach the live root

**RED (hermetic — no live root involved).** A throwaway `PKM_CONFIG` pointing at a throwaway
root holding an empty `catalogue.duckdb` and an `external/pending.txt` with one synthetic key
(`f`×64); `LIFE_AGENT_KB` unset; the one test, alone:
```
$ PKM_CONFIG=<scratch>/a0/pkm.yaml uv run pytest -q ... tests/test_ask.py::test_main_returns_2_on_locked_corpus
== before
2026-08-19 09:19:41.175738268 +0800 <scratch>/a0/root/external/pending.txt
2026-08-19 09:19:41.458525976 +0800 <scratch>/a0/root/catalogue.duckdb
1 passed in 0.17s
== after
2026-08-19 09:19:55.179309665 +0800 <scratch>/a0/root/external/pending.txt      ← REWRITTEN by the test
2026-08-19 09:19:41.458525976 +0800 <scratch>/a0/root/catalogue.duckdb
== newer than marker: <scratch>/a0/root/external, <scratch>/a0/root/external/pending.txt
```
**GREEN.** `tests/test_ask.py:152-158` now patches `ask._pkm_root` to `None` like its
neighbours (`:175`, `:225`) — one line (`:156`). Re-run of the hermetic witness: `pending.txt`
mtime unchanged, `find -newer marker` → nothing. The other `ask.main` callers in the file
(`/tell`, the grammar errors, `/derive`, the removed flags) all return before the reconcile
line — the audit in r04 STATE stands.

**PROOF (the brief's acceptance): the full suite with `LIFE_AGENT_KB` exported — the FIRST
such run since the interim constraint was imposed** (default `PKM_CONFIG`; live root
`~/.local/share/pkm/live` → `runs/phase1/full-2026-04-22`):
```
== before (2026-08-19T09:20:35+08:00; marker touched then)
<root>/catalogue.duckdb        mtime 2026-08-19 06:07:11.48 +0800   (size ~981 MB)
<root>/external/pending.txt    mtime 2026-08-19 06:08:54.18 +0800   2047 lines   (no catalogue.duckdb.wal)
$ LIFE_AGENT_KB=<kb> uv run pytest -q --basetemp=~/.cache/life-agent/basetemp-lineage -p no:cacheprovider
2390 passed, 34 deselected in 215.37s (0:03:35)        exit=0
== after (2026-08-19T09:24:46+08:00)
<root>/catalogue.duckdb        mtime 2026-08-19 06:07:11.48 +0800   (size unchanged)
<root>/external/pending.txt    mtime 2026-08-19 06:08:54.18 +0800   2047 lines   (no catalogue.duckdb.wal)
== files newer than marker under pkm root: 0
== files newer than marker under KB:       0
```
(The 06:07/06:08 mtimes are r04's disclosed suite-run writes — the last time anything touched
these files.) The tip run repeats the proof (§STATE). Transcripts:
`~/.cache/life-agent/lineage-r00/a0-{red,proof}.txt`.

### A1 — the writer records unique lineage inputs; every lineage site audited

**`core/joint_extract.py`** — RED: `tests/test_joint_extract.py:79`
`test_lineage_inputs_are_unique_first_occurrence_order` (a four-hit pool with one artefact
twice) failed with four lineage entries, the repeated key at index 2. GREEN: the record call
(`:120-127`) now takes `dict.fromkeys(str(h["artifact_cache_key"]) for h in pool)` — the idiom
already at `core/synthesis.py:85-86` and `scripts/ask.py:732-733`; first-occurrence order
preserved. `6 passed`.

**`core/lookup.py:1110-1112` — settled by a test, as the brief required: duplicates were
POSSIBLE.** `tests/test_lookup.py:731` `test_lookup_answer_lineage_inputs_are_unique`,
parametrised `same-artefact` / `other-artefact`: two hits with identical chunk text share
one extract key (`observe_hits` keys on the chunk sha, not the artefact — `:594-597`), so two
observations carry one `obs_cache_key`; a value-only quote keeps both through
`dedup_correlated` (`:799-806`: value-only quotes never collapse). RED: both variants failed —
the answer's lineage named the observation twice. GREEN: `:1113-1115` now takes
`dict.fromkeys(o.obs_cache_key for o in observations)`. `test_lookup.py` + `test_gather.py` +
`test_joint_extract.py`: `70 passed`.

**Audit table — every `derivations.record` caller in the tree** (`grep -rn "D\.record("
src scripts`; 14 sites; verdicts by reading, and by test where the brief said so):

| site (post-edit locator) | lineage passed | verdict |
|---|---|---|
| `core/joint_extract.py:120` | one per pool hit → **unique** (this tranche) | was possible → fixed; test `test_joint_extract.py:79` |
| `core/lookup.py:1113` (`decide_and_record`) | one per observation → **unique** (this tranche) | was possible (identical chunk text ⇒ shared extract key) → fixed; test `test_lookup.py:731` (both variants) |
| `core/lookup.py:562` (route) | `[]` | structurally impossible |
| `core/lookup.py:612` (extract) | one entry (the hit) | structurally impossible (single) |
| `core/lookup.py:718` (confirm) | one entry (the hit) | structurally impossible (single) |
| `core/narrative.py:510` | 0 or 1 entry (the proposal key, `:508-509`) | structurally impossible |
| `core/synthesis.py:87` | `extra_lineage` (≤ 1 retrieval-set *derivation* key, `scripts/ask.py:830`) + `dict.fromkeys(hits)` (`:85-86`) | already deduplicated; the extra entry is a derivation key, distinct from source-artefact keys by construction |
| `scripts/ask.py:734` (retrieval set) | `dict.fromkeys(hits)` (`:732-733`) | already deduplicated |
| `scripts/ask.py:562` (expand) | `[]` | structurally impossible |
| `core/expansion.py:171` | `[]` | structurally impossible |
| `core/deliberate.py:391` | `[]` | structurally impossible |
| `core/temporal_intent.py:85` | `[]` | structurally impossible |
| `core/subject.py:208` | `[]` | structurally impossible |
| `scripts/route_audit.py:51` | `[]` | structurally impossible |

No `record` caller exists under `src/life_agent/bridge` or `src/pkm` (pkm's own writer is
`cache.write_artifact` — Phase B's B2). After A2 (below) the seam refuses a duplicate from
*any* caller, so the two "possible" rows are now doubly closed: unique at the writer, refused
at the seam.

### A2 — the seam refuses

RED: `tests/test_derivations.py:119`
`test_record_refuses_duplicate_lineage_inputs_and_writes_nothing` — `DID NOT RAISE`. GREEN:
`derivations.record` (`:455-`) validates first — before the write-once check, before any
file — and raises `ValueError("duplicate lineage input(s) for <key>: …")` (`:468-471`);
`duplicate_lineage_inputs(lineage)` (`:436-446`) is the role-blind check (the catalogue key
is `(artifact, input)`; the same key under two roles is refused too — asserted). The test
asserts **nothing was written**: no artefact directory, no `external/pending.txt`, `lookup`
misses. `19 passed` in the file at that step.

### A3 — the reconciler is loud and counted; the census counts the laundered class

**`derivations.reconcile` → `ReconcileCounts`** (`:516-532`, frozen dataclass: `inserted ·
present · retry · dead · malformed · deduplicated`) — the return type changed from `int`
(callers: `scripts/ask.py:1546` ignores it; the six existing tests read `.inserted`; A4 uses
`pending_registerable`, below). Per class (`:558-581`):
- `inserted` — row inserted (with `deduplicated` additionally counted when the on-disk
  lineage needed the repair below);
- `present` — row already there: dropped from the queue, silently (idempotent, as before);
- `dead` (**S-L3**) — `meta.json` gone: **dropped**, one WARNING per key: *"reconcile: dead key
  `<key>` dropped — its meta.json no longer exists (the artefact was removed); the stream
  retains the occurrence record"* — the reviewer's rider, both halves asserted by shape
  (`tests/test_derivations.py:237`). Grounding, beyond the signature: `record` appends the queue
  line **after** `meta.json` (`:499-503` follow `:497`), so a queued key without a meta can
  never be mid-write — the former test's rationale ("mid-write by another process") was
  excluded by the writer's own ordering (DEVIATIONS 2);
- `malformed` — unparseable/incomplete meta or lineage (`ValueError` incl. JSON errors,
  `KeyError`, `TypeError`): kept queued, WARNING naming key + exception class
  (`test_derivations.py:309`);
- `retry` — everything else (a schema-less or locked catalogue): kept queued, WARNING
  *"reconcile: `<ExceptionClass>` for `<key>` — kept queued (retry later)"* — class and key,
  never content (`test_derivations.py:284` asserts the content string is absent).
- Absent catalogue / held writer lock → all-zero counts, queue intact (unchanged contract).

**Dedup-on-read, loud** (`_reconcile_one`, `:604-`): an on-disk lineage that repeats an input
(the pre-fix writer's output — exactly the 2,047's shape) is registered with one lineage row
per input, first occurrence kept, and WARNs *"reconcile: lineage of `<key>` repeats N
input(s) (M duplicate entries) — registered with one row per input; the writer should never
have produced this"* (`test_derivations.py:255`: one artifacts row, two lineage rows from four
entries, the WARNING names key and count; idempotent — re-queued it is `present`, no second
warning). Such an artefact is therefore **registerable again** — the class that rolled back
for two months now reconciles on the next ask, visibly.

**The ledger census** (`src/life_agent/ledger/sources.py:377-` `_scan_artifacts`): a new
extra `lineage_duplicate_inputs` (`:386`, `:411-416`, `:433`) = artefacts whose on-disk
`lineage.json` repeats a key; the envelope still collapses (`:226`, unchanged — `inputs` is a
set of identities) but the collapse is now a number. `migrate counts` prints it for
`pkm.artifact` and carries it in its result row (`ledger/migrate.py:193-197`);
`tests/test_ledger_migrate.py:234` asserts scan extra, envelope collapse, result row, and the
printed `lineage_duplicate_inputs=1`. **Transcript on the live KB (read-only):**
```
$ LIFE_AGENT_KB=<kb> uv run python -m life_agent.ledger.migrate counts
counts   pkm.artifact                 tally=  32445 segment=  32445 (wc -l 32445, quarantined 0) legacy=  30398 → MISMATCH — legacy lost 2047 identities the segment retains (deletion on the legacy side) lineage_duplicate_inputs=0
counts   MISMATCH present                                                                    (exit 1; 23.4 s)
```
(the other eleven sources OK, unchanged from r04.) `lineage_duplicate_inputs=0` today is the
expected reading: the artefacts that carried duplicates are exactly the 2,047 the sweep
removed; every survivor reconciled, so had none. The number exists now for the next one.

Idempotency double-runs (writer side): dead-key drop → second pass all-zero
(`test_derivations.py:237`); dedup-on-read → re-queued key is `present`, no insert, no warning
(`:255`); the queue rewrite unchanged (`test_reconcile_is_idempotent_when_row_exists`).

### A4 — the caller: reconcile-or-refuse

`scripts/ask.py:_reingest_state` (`:1358-1381`) now calls `D.reconcile(root)` **immediately
before** `pkm_extract` (`:1374`, `:1378`) and then asks `D.pending_registerable(root)`
(`core/derivations.py:593-602`: queued keys whose `meta.json` exists — a pure read, asserted
not to rewrite the queue, `test_derivations.py:375`); if any remain it raises
`_RefreshBlockedError(n)` (`:1314-1320`) and **never reaches the extract**. `ensure_gtd_fresh`
catches it first (`:1398-1403`): un-stamps the state doc (the next ask retries after another
reconcile) and prints the new `REFRESH_NOTES["blocked"]` (`:1308-1310`): *"gtd state refresh
blocked: {n} recorded derivation(s) still awaiting catalogue reconciliation — not extracting
(an extract sweeps unregistered artefacts); answering over the corpus as-is"* — drift-gated
with the table (`tests/test_ask_gtd_refresh.py:250`, the set is now
`{refreshed, failed, blocked}`).

Tests (`tests/test_ask_gtd_refresh.py:199`, `:222`) drive `ensure_gtd_fresh` with the REAL
`_reingest_state` over a real migrated tmp pkm root (real `ingest_sources`, real
`build_fts_index`, a tmp `PKM_CONFIG`) and a fake `pkm.extract.extract` — the brief's "with a
fake extract": (i) a recorded-but-unregistered derivation is registered **before** the
extract runs (row present, queue empty, extract called once, `refreshed` printed); (ii) with
the reconciler unable to register it (stubbed to all-zero counts — the held-writer-lock case)
the extract is **not** called, the `blocked` line prints with the count, `failed` does not,
`gtd_stale()` is True (un-stamped), the key stays queued. RED for both was exactly the wrong
behaviour (extract ran; row absent). `12 passed` in the file; the whole `test_ask*` +
`test_derivations` set `68 passed`.

`docs/interaction-contract.md:100-108` — one sentence added to the Act-layer-state paragraph
naming the refusal and its line (the contract governs every reply string; DEVIATIONS 1).

The startup reconcile at `scripts/ask.py:1544-1547` (`contextlib.suppress(Exception)` around
`D.reconcile`) is unchanged: `reconcile` itself no longer raises per key (it counts and WARNs),
so the suppress now only hides a failure *of the pass itself* (an unreadable queue) —
QUESTIONS 2.

### A5 — the operating constraint's first witness: NOT RUN

Per the opening document's precondition: the pandoc pin is still mismatched (`3.6` vs
`3.10.2`, §STATE), so a witness taken now would measure the pin's fail-and-retry, not the fix.
Phases A0–A4 ran no live extract. **The standing constraint (no eval/gate run followed by a
refreshing ask) remains in force.** A5 runs on the owner's word once (d) is done — as an
addendum to this report or inside Phase B, the owner's call (QUESTIONS 5).

### Verification checklist (the brief's pre-stated acceptance)

| acceptance | evidence |
|---|---|
| A0 before/after mtimes unchanged | §A0 PROOF (two full-suite runs, zero newer files) |
| A1 test green + audit table complete | §A1 (14 rows, two settled by test) |
| A2 refusal test (nothing written) | `test_derivations.py:119` |
| A3 WARNING + one-row test; census count visible in `migrate counts` (transcript); dead-key per S-L3 | `test_derivations.py:255`, `:237`; §A3 transcript |
| A4 two tests | `test_ask_gtd_refresh.py:199`, `:222` |
| suite green, ruff, mypy | §STATE (tip) + bisect (T1…T5) |
| guard exit 0 on every changed file | §STATE |
| TDD at every unit boundary | every item above records its RED before its GREEN |
| idempotency double-runs on writer-side changes | §A3 |

### Commit series — for the owner (S12): `~/.cache/life-agent/r00-lineage-writer-commit.sh`

Seven commits on `b8f014d`, one conceptual move each, built from the reviewed **tree objects**
(`~/.cache/life-agent/lineage-r00/patches/trees.txt`; the per-item patches
`01-a0 … 05-a4.patch` alongside, and `build_trees.sh` regenerates both from the working tree
+ the saved intermediate states if the object db ever loses them):
```
T0=0dfe77e5  (HEAD b8f014d's tree)
T1=9ccb08a5  A0  tests/test_ask.py
T2=926a6d3d  A1  core/joint_extract.py, core/lookup.py, tests/test_joint_extract.py, tests/test_lookup.py
T3=442e43d6  A2  core/derivations.py, tests/test_derivations.py
T4=90ffe67a  A3  core/derivations.py, tests/test_derivations.py, ledger/sources.py, ledger/migrate.py, tests/test_ledger_migrate.py
T5=a5b625b9  A4  core/derivations.py, tests/test_derivations.py, scripts/ask.py, tests/test_ask_gtd_refresh.py, docs/interaction-contract.md
     + docs r04-stocktake.md ; + docs r00-lineage-writer.md
```
The script's preflight refuses unless: on `master` at `b8f014d`, index empty, `LIFE_AGENT_KB`
a directory (the armed hook needs it), all six trees present, and the working tree on the
series' files **equals T5** (so what is committed is exactly what was tested — the trees the
bisect check ran). Each step `git checkout <tree> -- <files> && git add && git commit`
(hooks run); after the fifth it asserts `HEAD^{tree} == T5`. Not pushed — push is a separate
act. **Rehearsed** in the disposable worktree (DEVIATIONS 5):
```
preflight ok: master @ b8f014d, working tree == T5
committed <sha>  9ccb08a5  test(ask): … (lineage A0)
committed <sha>  926a6d3d  fix(ask): … (lineage A1)
committed <sha>  442e43d6  fix(derivations): … (lineage A2)
committed <sha>  90ffe67a  feat(derivations): … (lineage A3)
committed <sha>  a5b625b9  fix(ask): … (lineage A4)
tree invariant ok: HEAD^{tree} == T5
committed <sha>  docs r04
committed <sha>  docs r00
working tree clean
```

## DEVIATIONS

1. **`docs/interaction-contract.md` amended** (one sentence in the Act-layer-state paragraph,
   `:102-107`) — not named in Appendix A, but the contract governs every human-facing reply
   string and A4 adds one; the amendment is the minimum that keeps the contract true. Not on
   the refusal list.
2. **A test replaced, not only added:** `test_reconcile_keeps_half_written_keys_queued`
   (old `tests/test_derivations.py:207-213`) asserted the pre-S-L3 behaviour under a rationale
   ("mid-write by another process") that `record`'s write order excludes (queue line after
   `meta.json`). Replaced by `test_reconcile_drops_a_dead_key_loudly_naming_the_stream`
   (`:237`). Every other existing reconcile test kept, with `== N` → `.inserted == N`.
3. **Return type of `reconcile` changed** (`int` → `ReconcileCounts`) and a **`deduplicated`**
   counter added beyond the brief's five named classes — the reconcile-time count of the
   laundered class, complementing the census's on-disk count (the doctrine: a visible number,
   never a silent repair). Two small helpers added (`duplicate_lineage_inputs`,
   `pending_registerable`) — narrowings both reused twice; no other new concept.
4. **The r04 commit script is superseded** (its base `f4d1ab0` moved under it): r04 is
   committed as the sixth commit of the r00 series. Its Appendix A heading still reads
   "(unsigned)" — left as reviewed (append-only); this report records the signature.
5. **A disposable detached worktree** (`lineage-r00-bisect`, under the sanctioned
   worktrees directory) was used (i) to check out each intermediate tree for the bisect
   verification (`git read-tree --reset -u <tree>`; no branch) and (ii) to **rehearse the
   owner's commit script** end to end — a copy with `REPO` pointed at the worktree and the
   `master` check dropped (detached HEAD) made the seven commits there, the armed pre-commit
   hook running on each (`core.hooksPath=.githooks` resolves inside the worktree), the tree
   invariant held, the tree was clean; those commits are throwaway (unreachable once the
   worktree was removed — `git worktree remove --force` + `prune`, done at the STOP; `master`
   untouched, no push). Rehearsal transcript: `~/.cache/life-agent/lineage-r00/rehearsal.txt`.
   The commit rule ("commit only when the owner asks") is read as governing branches and
   history the owner keeps; a rehearsal that proves the owner's script before they run it is
   disclosed here so the reading can be corrected if wrong.
6. **The interim constraint's variable was wrong** (§STATE finding). Not a deviation from the
   brief — a correction to r04's operational note and to the opening document's ruling 1
   wording, recorded because a reader of either would otherwise repeat the mistake. A0 makes
   both moot.

## REFUSED

- **A5** — not run (the opening document's precondition: the pandoc pin is mismatched). Not a
  refusal of the item; a refusal to take a witness that would measure the wrong thing.
- Nothing under `src/pkm` or `docs/pkm` touched (Phase B, S-L2 route signed, opens on review).
- No backfill, re-derivation, or restoration of the 2,047 (ruling 3); no reader cutover,
  retirement, or compaction; no rewrite of any ledger, log, or cache artefact — the only
  queue rewrite is the drain the queue already performed on every call, now dropping dead
  keys per S-L3.
- No commit, no push (owner-executed script prepared).
- No `$LIFE_AGENT_KB` write; no live-root write (proof in §A0; the `migrate counts` read is
  disclosed).
- The startup reconcile's `contextlib.suppress(Exception)` (`scripts/ask.py:1544-1547`) not
  changed — not an A item; raised as QUESTIONS 2 rather than done silently.

## QUESTIONS

1. **(reviewer) A0's broader guard** — Appendix A's parenthetical: an autouse fixture pointing
   every test's `ask._pkm_root` / `config.pkm_root` at a tmp root unless a test opts in
   (`tests/conftest.py` already does this for the GTD paths, lookup, narrative, mirror,
   executor). The finding that the reach ran through `PKM_CONFIG`'s *default* path argues for
   it: any future test that calls `ask.main` far enough will reconcile whatever
   `~/.config/life-agent/pkm.yaml` names. Recommend yes, as a one-fixture follow-on commit;
   not done here (a QUESTION per the brief).
2. **(reviewer) The startup reconcile's suppress** (`scripts/ask.py:1544-1547`): with A3, a
   swallowed exception there can only be a failure of the pass itself. Add a WARNING inside
   the suppress (one line), or leave? Recommend the WARNING, in Phase B's B3 commit or the
   A0-guard follow-on.
3. **(reviewer) `malformed` keys are kept queued** (WARNed on every ask; they never succeed
   unattended). Alternative: drop after N passes, or drop with WARNING like `dead`. Kept —
   deleting an index-lag record for a file that *exists* on disk is closer to the class Phase
   B forbids than to S-L3; the number is visible. Confirm or rule.
4. **(owner) A5's placement** once (d) lands: an addendum to this report (append-only, second
   sitting — the r03 precedent) or the first item of Phase B? Recommend the addendum: it lifts
   the constraint for the *ask path* independently of the SPEC route.
5. **(owner/reviewer) Phase B opening** — S-L2 is signed with the text as drafted (Appendix A
   B1); B1's SPEC commit is the first act of Phase B and needs no further ruling. Confirm the
   r00 review is the only gate, per S-L1.

## PROPOSED

1. Owner runs `~/.cache/life-agent/r00-lineage-writer-commit.sh` (seven commits on `b8f014d`),
   reads `git log --oneline b8f014d..HEAD`, pushes as a separate act.
2. Owner-side, unchanged priority: the backup audit (r04 Q1 — a hard gate on B2's live
   witness), the pandoc pin (d) (unblocks A5), FAILURES.md entry (e), the executor daemon.
3. On the r00 review: **Phase B** — B1 the SPEC §6.2 replacement + §18.9 rider + §16 entry
   (verbatim from Appendix A, a separate justified commit), B2 the pkm code TDD (`sweep_orphans`
   register-or-leave; `rebuild._read_lineage` loud dedup; `write_artifact` refuses), the
   dry-run then real live witness with the two-route count (only with the backup recorded), B3
   the constraint lift → STOP `r01-lineage-sweep.md`.
4. Then the collapse-census placement (Q-R5) and tranche 2, per r04 §4.

## Rulings applied — 2026-08-19 (post-review, before Phase B; the series' sixth commit)

The reviewer's verdict on this report: *"Phase A accepted; Phase B is green-lit on this
review, conditional only on the seven commits landing."* Two rulings asked for code, riding
one follow-on commit **before** the SPEC series so that Phase B stays clean; both done here,
TDD, and folded into the same owner script as its **sixth** commit (the docs commits follow),
so the STOP's one-script rule holds. Rulings on the record, verbatim where they bind:

- **Q1 — the three-route autouse guard: yes.** *"the fixture neutralises all three reach
  routes — `ask._pkm_root`, `config.pkm_root`, and the `PKM_CONFIG` environment variable
  pointed at a scratch config — with explicit opt-in for tests needing a real-shaped root.
  Patching the innermost symbol alone is how this class recurs."*
- **Q2 — the startup suppress: yes, the WARNING**, one line, on the Q1 commit.
- **Q3 — `malformed` keys stay queued; no N-pass auto-drop, ever** (*"a timer-shaped policy
  concealing a deletion"*; the remedy is repairing the artefact or an owner-signed
  quarantine). Nothing to change; recorded as the standing rule for the reconciler.
- **The rehearsal (DEVIATIONS 5) is accepted and henceforth required:** *"script rehearsal in
  a throwaway worktree is now part of the standing prepared-script pattern, transcript
  retained."* DEVIATIONS 1–4 accepted as recorded. **Q4:** A5 runs as an addendum to this
  report once the pandoc pin is fixed. **Q5:** this review is the only gate; Phase B needs no
  new brief.

### Q1 — `tests/conftest.py:59-88` `_hermetic_pkm_root` (autouse)

RED (`tests/test_ask.py:183`, `:190`): `KeyError: 'PKM_CONFIG'` (no scratch env), and the
spy on `ask.D.reconcile` saw **the machine's live pkm root** reconciled by an un-patched
`ask.main` call (the A0 mechanism, generalised — intercepted by the spy, nothing written).
GREEN: for every test not marked `llm`/`system`, the fixture writes a scratch `pkm.yaml`
naming a scratch `root` in a per-test `tmp_path_factory.mktemp("hermetic-pkm")` directory (a
sibling of `tmp_path` under basetemp — never inside it) and points **all three routes** at it — `monkeypatch.setenv("PKM_CONFIG", …)`, `config.PKM_CONFIG`,
`config.pkm_root`, and `ask._pkm_root` (four patches, three routes). Opt-in for a real-shaped
root: a test's own patch (as many already do — tmp roots, `/fake/root`, `None`), or the
`llm`/`system` markers — the opt-in live suites (`tests/test_bridge_server_live.py` skips on
`C.PKM_CONFIG.exists()`) keep the machine's config exactly as before, since a human chose
`-m` to run them. `test_ask.py:183` asserts the three routes agree on one scratch path under basetemp, not
under `~/.config`, and that the root is inert (does not exist); `:190` asserts the un-patched
`ask.main` reconciles exactly that root. A0's explicit
per-test patch stays (belt and braces).

### Q2 — `scripts/ask.py:1544-1552`

RED (`tests/test_ask.py:202`): with `D.reconcile` raising, `ask.main` still returned 2 and
**no** WARNING was emitted. GREEN: the `contextlib.suppress(Exception)` becomes `try/except`
that logs `logging.getLogger("ask").warning("startup reconcile pass failed (%s) — files stay
authoritative; retried next ask", type(e).__name__)` — the exception **class**, never the
message body (asserted absent). Fail-open unchanged (`main` returns 2 on the locked corpus).

### Verification (this sitting)

- Targeted: `tests/test_ask.py tests/test_ask_gtd_refresh.py tests/test_ask_cache.py
  tests/test_derivations.py` → `82 passed`; ruff clean on the three files; full configured
  `uv run mypy` → `Success: no issues found in 207 source files`.
- Full suite at the new tip (`LIFE_AGENT_KB` exported; mtimes proof repeated):
  ```
  $ LIFE_AGENT_KB=<kb> uv run pytest -q --basetemp=~/.cache/life-agent/basetemp-lineage -p no:cacheprovider
  2404 passed, 34 deselected in 153.84s (0:02:33)        exit=0
  live root after: catalogue.duckdb / external/pending.txt mtimes unchanged (06:07:11 / 06:08:54);
  files newer than the run's marker under the pkm root + the KB: 0
  (a first run of the fixture failed one test — tests/test_p3_gate.py:208 enumerates tmp_path and
   saw the scratch config; the scratch pair now lives in a per-test tmp_path_factory sibling under
   basetemp, never inside tmp_path — 2404 passed on the re-run.)
  ```
- The series is now **eight commits**: T1…T5 as above, **T6 = the Q1/Q2 follow-on**
  (`tests/conftest.py`, `tests/test_ask.py`, `scripts/ask.py`), then docs r04, docs r00 (this
  file, with this section). Trees rebuilt (`build_trees.sh`), the tree invariant is now
  `HEAD^{tree} == T6` after the sixth commit, bisect + rehearsal repeated:
  ```
  T6 28c98f90: 181 passed (targeted set + test_p3_gate)   ruff=All checks passed!   mypy=Success: 207 files
  rehearsal (fresh disposable worktree, hooks armed): preflight ok … working tree == T6;
    six code commits, "tree invariant ok: HEAD^{tree} == T6", docs r04, docs r00, working tree clean
  ```
- Guard: exit 0 on `tests/conftest.py`, `tests/test_ask.py`, `scripts/ask.py`, this report.

**Next, in order:** the owner runs `~/.cache/life-agent/r00-lineage-writer-commit.sh` (eight
commits on `b8f014d`), reads the log, pushes as a separate act, then pastes the reviewer's
opening note with confirmation that the commits are in — Phase B opens on that
(B1 the SPEC commit verbatim per S-L2; B2 TDD, the dry-run transcript read by the owner
before any live run, the live witness only with a verified backup recorded in STATE; B3 the
lift; STOP at `r01-lineage-sweep.md`). The pandoc pin remains the sole blocker on A5.
