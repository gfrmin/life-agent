# r01 — lineage — sweep — 2026-08-19

The pkm lineage micro-tranche, **Phase B**: the SPEC amendment (B1), the pkm code (B2, three
moves, TDD), the dry-run witness, and the live witness prepared behind its gate. Companion to
`r00-lineage-writer.md` (Phase A, reviewed and accepted); the brief is `r04-stocktake.md`
Appendix A as signed. Report protocol as the tranche briefs: append-only; STATE / DONE /
DEVIATIONS / REFUSED / QUESTIONS / PROPOSED; every claim with a transcript; locators, never
values; commits by an owner-executed prepared script (S12).

## Opening — what this phase runs on

- **The reviewer's condition** on r00: *"Phase B is green-lit on this review, conditional only
  on the commits landing."* The r00 series landed on `master` this morning — eight commits
  `c816bf2`…`42f5e09` on `b8f014d` (the owner ran `r00-lineage-writer-commit.sh`; the script's
  tree invariant held: `17e743a^{tree} == T6`); `master` is eight ahead of `origin/master`, not
  yet pushed (the owner's separate act).
- **The reviewer's opening note** (its terms, applied here): *B1 the SPEC commit verbatim per
  S-L2, B2 TDD with the dry-run transcript read by the owner before any live run, the live
  witness only with a verified backup recorded in STATE; B3 the lift; STOP at
  `r01-lineage-sweep.md`.* The note was to be pasted by the owner with confirmation the commits
  are in; what arrived was the commit transcript itself plus "help me with remaining tasks" —
  taken as that confirmation (DEVIATIONS 1).
- **Signatures in force:** S-L2 = Option A **plus** the §18.9 rider, text as drafted; S-L3
  (dead keys) landed in Phase A; Q3 (keep-queued, no auto-drop, ever) is the standing rule and
  shapes the sweep's *left* class below.

## STATE

- **HEAD `42f5e09`** (`master`, ahead of `origin/master` by the eight r00 commits). Working
  tree at the STOP (uncommitted until the owner runs the series script):
  ```
  $ git status --short
   M docs/pkm/SPEC.md
   M src/pkm/cache.py
   M src/pkm/cli.py
   M src/pkm/extract.py
   M src/pkm/rebuild.py
   M tests/pkm/test_cache.py
   M tests/pkm/test_extract.py
   M tests/pkm/test_rebuild.py
  ?? docs/unification/reports/r01-lineage-sweep.md
  ```
- **Suite (default marker set, `LIFE_AGENT_KB` exported, mtimes before/after under the live
  pkm root and the KB):**
  ```
  2419 passed, 34 deselected in 151.18s (0:02:31)
  exit=0
  == files newer than marker under root + KB:
  count: 0
  ```
  (2404 at the r00 STOP + 15 new tests.) `uv run ruff check src/pkm tests/pkm` → *All checks
  passed!*; `uv run mypy` → *Success: no issues found in 207 source files*.
- **The live pkm root** (`PKM_CONFIG` → `~/.local/share/pkm/live` → `runs/phase1/…`; read-only
  reads only, disclosed): `artifacts` rows 30,398 = cache directories 30,398; the dry-run
  witness (§DONE B2) classifies **torn 0, unregistered 0**. `external/pending.txt` still holds
  the 2,047 swept keys — every one dead (its `meta.json` gone); the first `reconcile` after the
  r00 series (the next ask's startup pass) drops them with one WARNING each per S-L3. No ask
  has been made since the commits.
- **The pandoc pin (owner item (d)) — still mismatched at the STOP**, `"3.6"` vs installed
  `3.10.2` — **and the other three producer pins are stale on this box too**: docling `2.90.0`
  → installed `2.96.1`, unstructured `0.22.21` → `0.22.31`, tesseract `5.5.2` → `5.5.3` (every
  live artefact was produced *at* the pinned versions, Apr–Jun, on the other machine). `.md` is
  pandoc-handled, so only the pandoc pin gates the `state.md` refresh; but an **unscoped**
  `pkm extract` here would run the sweep and then halt at the first mismatched producer (r03's
  ordering), or — with all four bumped — re-extract on the order of 5.5k sources for hours and
  move the corpus digest (cold deliberate cache). A prepared owner script bumps pandoc only
  (`~/.cache/life-agent/pandoc-pin-bump.sh`, both identical config copies, `.bak` kept); the
  agent's own attempt at the config edit was declined by the permission layer (REFUSED). A5
  therefore still has not run.
- **Backup — the B2 live-witness gate: NOT met at the STOP.** The owner rewrote the borg
  wrapper this morning (the KB and `~/.local/share/pkm/` added to its source list; the
  rsync.net key fixed; the first run that actually reaches the repository started 10:10 HKT and
  was still uploading at the STOP — 23 prior archives, the last from 2026-07-26); the daily
  `systemd --user` timer was enabled by the agent (next fire 2026-08-20 00:36 HKT). **But the
  wrapper's `EXCLUDES` still carries the `sh:` glob excluding every `pkm/runs/…/cache`
  directory** (the other machine's
  `borg-backup.sh` has the same line, commented *"regenerable content-addressed eval cache"*),
  and the live root resolves under `pkm/runs/phase1/…`, so the 1.8 GB `cache/` — the directory
  that holds **both** producer artefacts **and** the §18.9 derivation records
  (`life_agent.core.derivations` writes through `pkm.cache.artifact_dir`) — is dropped. That is
  exactly the r03 loss class, still uncovered. The wrapper's header says the pkm root is to be
  *moved* onto the KB volume rather than excepted; at the STOP that move has not happened
  (`root_dir` unchanged; nothing new on the volume). Whichever way it lands, the gate reads: an
  archive that demonstrably contains the pkm root's `cache/`.
- **The tranche's tools this sitting** (all outside the tree, none touch the KB):
  `~/.cache/life-agent/lineage-r01/{states/,patches/,preview-sweep.sh,preview-sweep.txt,
  b2-live-witness.sh,full-suite-b2.txt,bisect.txt}` and the owner script
  `~/.cache/life-agent/r01-lineage-sweep-commit.sh` (five commits on `42f5e09`).

## DONE

### B1 — the SPEC amendment (SPEC 0.17.0 → 0.18.0), verbatim per S-L2

`docs/pkm/SPEC.md`: header `:3` `Version: 0.18.0 (draft)`; **§6.2** `:307-322` — the
paragraph *"The sweep is conservative … Orphan directories are removed; the event is logged."*
replaced by Appendix A's text, word for word (torn vs unregistered; register-or-leave; *deletion
never follows from index lag*); **§18.9** `:1736-1739` — the rider as a fifth contract bullet,
*Unique lineage inputs*, text as signed; **§16** `:1892-1911` — the 0.18.0 entry with the
justification (the 0.17.0 definition of "orphan" made a lagging §18.9 row indistinguishable
from an interrupted write; the r03 chain named; no schema change, no migration, no dependency).
Adjacent prose left as it stands (the earlier "Orphans are removed by a consistency sweep …" and
the `delete_artifact` paragraph read correctly with "orphan" now meaning *torn*; QUESTIONS 1).
Guard: `python3 .githooks/pii_check.py docs/pkm/SPEC.md` → `exit=0`. Per SPEC's own rule
(`src/pkm/CLAUDE.md` — *update SPEC.md first, in a separate commit with a clear justification*)
B1 is the first commit of the series (`STOP_AFTER_B1=1` lands it alone).

### B2-i — `write_artifact` refuses duplicate lineage inputs before writing anything

`src/pkm/cache.py:156-172` `duplicate_lineage_inputs(lineage) -> list[str]` (role-blind,
first-occurrence order — the `artifact_lineage` key is `(artifact_cache_key, input_cache_key)`);
`:245-255` in `write_artifact`, after the schema/lineage check and **before** the idempotency
guard: `ValueError("duplicate lineage input(s) for <key>: …")`. Test
`tests/pkm/test_cache.py:784-813` (parametrised same-role / other-role): the error names the
input; no row; no directory. **RED** (both params):
```
_duckdb.ConstraintException: Constraint Error: PRIMARY KEY or UNIQUE constraint violation …
src/pkm/cache.py:315: ConstraintException
2 failed, 29 deselected
```
— i.e. the files were already on disk when the row insert tripped the key. **GREEN:**
`31 passed` (`test_cache.py`), ruff, mypy.

### B2-ii — `rebuild._read_lineage` deduplicates on read, loudly

`src/pkm/rebuild.py:377-421`: a repeated input collapses to its first occurrence, one WARNING
per artefact naming it (`lineage of %s repeats %d input(s) (%d duplicate entr%s) — one row per
input; the writer should never have produced this`, event `lineage_duplicate_inputs`). Test
`tests/pkm/test_rebuild.py:278-315`: two artefacts on disk, one with a repeated input; the
rebuild inserts **both** (2 rows, 2 lineage rows), first occurrence wins, exactly one WARNING
carrying the key. **RED:** the whole rebuild raised the same `ConstraintException` — one file
took every artefact's row with it. **GREEN:** `13 passed`, ruff, mypy.

### B2-iii — the sweep: torn vs unregistered (register-or-leave)

`src/pkm/cache.py`: `SweepPreview :490-` (torn / unregistered), `SweepResult :510-` (removed /
registered / left), `_META_REQUIRED_KEYS :533-`, `_torn_reason(adir) :544-585` (the decision
table — DEVIATIONS 6), `_iter_unrowed_dirs :588-612`, `preview_sweep :615-628` (the read-only
dry run, safe on a read-only connection), `sweep_orphans :631-706` (torn → `rmtree` + WARNING
with the reason and the files it contained, event `orphan_removed`; unregistered →
`rebuild.register_directory` — success → INFO, event `unregistered_registered`; any exception →
**left** + WARNING `left unregistered cache dir <key> in place — registration failed
(<class>: <msg>)`, event `unregistered_left`, re-said on every sweep until repaired, never
removed). `src/pkm/rebuild.py:239-294` `register_directory(root, conn, cache_key) -> list[str]`
— a per-directory rebuild (`_check_meta_consistency`, `_meta_to_row`, `_read_lineage`'s loud
dedup, both inserts in one transaction, `produced_at` preserved; rolls back and re-raises on
failure); `RebuildResult.left :97`; the post-rebuild call `:207`. `src/pkm/extract.py:202-217`
logs the three counts at extract start (event name `extract_swept_orphans` kept, `count` =
removed). `src/pkm/cli.py:487` prints `left N` after `rebuild-catalogue`.

Tests (`tests/pkm/test_cache.py:326-563`, `_drop_rows`/`_rows` helpers): an unregistered
file-complete directory is **registered** with `produced_at` unchanged (`:345`); a transform's
lineage rows come back (`:369`); **the r03 class itself** — a repeated input on disk —
registers with one row per input and one WARNING (`:386`); torn: `status = 'success'` without
`content` (`:415`), schema ≥ 2 without `lineage.json` (`:432`); a *failed* result's directory
(meta.json only) is complete and is registered, not removed (`:448`); unregistrable —
`format_version` 99, `cache_key` naming another directory — **left**, files intact, no row,
one WARNING with key + reason (`:469`, parametrised); idempotency double-run — second sweep
removes and registers nothing, re-reports the left key, byte-identical filesystem (`:495`);
`preview_sweep` changes nothing and a sweep then acts on exactly the previewed sets (`:531`).
The six pre-existing sweep tests were adapted to the result shape (their `{}`-meta fixtures
remain torn: no `format_version`). `tests/pkm/test_rebuild.py:169-185`: an unregistrable
directory survives the post-rebuild sweep (`result.left == [ck]`, files present).
`tests/pkm/test_extract.py:187-236`: through the real `extract` on the bench (pandoc on a
`.md`), a §18.9-shaped derivation (schema 3, `life_agent.ask.*`, lineage to the upstream
artefact) written file-first with its rows dropped **survives the sweep at extract start and
comes out registered** — the loss path, closed end to end.

**RED transcript** (the new name masked so the module collected; restored after):
```
16 failed, 25 passed in 6.50s
FAILED …::test_sweep_registers_an_unregistered_file_complete_dir
FAILED …::test_sweep_registers_duplicate_lineage_dir_loudly_with_one_row_per_input
FAILED …::test_sweep_leaves_unregistrable_dir_in_place_with_a_warning[schema-mismatch]
… (16 in all: the ten new behaviours and the six adapted result-shape assertions)
```
`test_rebuild_leaves_an_unregistrable_dir_in_place`: `assert [ck] == []` (swept today);
`test_extract_registers_an_unregistered_derivation…`: `assert False where False = exists()`
(deleted today). **GREEN:** the three files `68 passed`; `tests/pkm` `477 passed, 17
deselected`; ruff (`RUF100`, `E702` fixed on the way), mypy.

### The dry-run witness (read-only; the owner reads this before any live run)

`~/.cache/life-agent/lineage-r01/preview-sweep.sh` — opens the catalogue read-only, runs
`preview_sweep`:
```
root  ~/.local/share/pkm/live  (resolved under pkm/runs/phase1/full-2026-04-22)
artifacts rows 30398   cache dirs 30398
preview_sweep: torn=0 (would remove)   unregistered=0 (would register-or-leave)   [0.6s]
```
The store is consistent today; the amended sweep, live, would remove nothing and register
nothing. (The 2,047 are not directories any more — they are queue lines, dead, and the stream's
dangling identities.)

### The live witness — prepared, NOT run (the gate)

`~/.cache/life-agent/lineage-r01/b2-live-witness.sh`: two-route count (`migrate counts`) →
preview → the real `pkm extract --source <16-hex prefix of one .eml source>` (its sweep runs
first; routing then has nothing to do for an already-extracted `.eml`, and the `email`
producer's logic version always matches, so no pin is consulted and no artefact is produced) →
two-route count; criterion as pre-stated: `pkm.artifact` legacy count monotone. It **refuses to
run** unless `BACKUP_ARCHIVE=<name>` names the borg archive the owner has verified to contain
the pkm root **including `cache/`**, and it writes that name into its transcript. Not run:
STATE's backup facts. On the owner's word it runs as an addendum to this report, with B3.

### B3 — not lifted

The standing constraint (no eval/gate run followed by a refreshing ask; and, from Phase A, the
suite's hermeticity note is moot) **remains in force**: it lifts on B2's live witness or A5's,
neither of which has run (backup gate; pandoc pin). The dated note in
`docs/unified-ledger-design.md`'s status block is written when it lifts.

### Verification checklist (pre-stated acceptance)

- [x] B1: SPEC text verbatim; version bumped; §16 entry with justification; guard exit 0.
- [x] B2-i / B2-ii / B2-iii: RED witnessed for every new test (transcripts above), GREEN;
      idempotency double-run on the sweep; the extract-level test.
- [x] Suite green (2419), ruff, mypy; live root + KB untouched (mtimes: 0 newer files).
- [x] Dry-run transcript taken and reported.
- [ ] Live witness — gated (backup); B3 — pending it.
- [x] Guard exit 0 on every changed file (`--staged` at rehearsal; per-file at the STOP).

### The commit series (tree objects, bisected, rehearsed)

`~/.cache/life-agent/lineage-r01/patches/build_trees.sh` builds T1..T4 from the saved states
(`states/`), `T4 == working tree` on `src/pkm tests/pkm docs/pkm/SPEC.md`:
```
T0=02615a56 (HEAD 42f5e09)   T1=45077b76 (B1 SPEC)   T2=6e9de61e (B2-i)
T3=235ef324 (B2-ii)          T4=7d1de153 (B2-iii)
```
Bisect in a disposable detached worktree (under the sanctioned worktrees directory), each tree
checked out with `git read-tree --reset -u`, `index==tree` asserted, its own tests + ruff +
mypy (`bisect.txt`): T1 `41 passed`; T2 `31 passed`; T3 `44 passed`; T4 `477 passed, 17
deselected` — all four *All checks passed!* / *Success: no issues found in 207 source files*.
Rehearsal of the owner script in the same worktree, hooks armed — transcript in the addendum
below (written after this section, before the STOP).

## DEVIATIONS

1. **Phase B opened on the commit transcript, not the pasted note.** The reviewer's condition
   was the commits; they are in and verified; the owner asked for help with the remaining
   tasks. If the form matters, the phase can be re-opened by the paste — nothing here is
   committed until the owner runs the script.
2. **`register_directory` lives in `pkm.rebuild`, and `cache.sweep_orphans` imports it inside
   the function** (`cache.py:655`): registering a directory *is* a per-directory rebuild (§5.3
   ≡ the §6.2 register step ≡ the §18.9 reconciliation), so the row construction stays in the
   module that owns it; `rebuild` imports `cache`'s path helpers at import time, hence the local
   import. The brief named the three sites, not this placement (QUESTIONS 2).
3. **`preview_sweep` / `SweepPreview` are new API** — the read-only classification the brief's
   "dry-run transcript" needs; no CLI flag was added (a `pkm` surface change is a SPEC change —
   QUESTIONS 5). `RebuildResult.left` and the `left N` in `rebuild-catalogue`'s output are
   the matching small surface additions.
4. **The sweep's return type changed** from `list[str]` to `SweepResult`; both callers and the
   six existing tests were adapted; `RebuildResult.swept` keeps its type (= removed).
5. **`duplicate_lineage_inputs` now exists in `pkm.cache` as well as `life_agent.core.derivations`**
   (Phase A). Not unified here — life_agent's reconciler could delegate to
   `rebuild.register_directory` outright (QUESTIONS 4); out of Phase B's named scope.
6. **The torn/unregistered boundary made concrete** (`_torn_reason`): torn = no `meta.json`;
   not valid JSON; no `format_version`; a v1 required field missing; `status = 'success'`
   without `content`; schema ≥ 2 without `lineage.json`. **Not** torn (→ registration → left
   on failure): a `format_version` we do not know (a future format is never deleted), a
   `cache_key` naming another directory, a JSON document that is not an object, malformed
   lineage. The `{}`-meta fixtures of the old tests are therefore still torn (QUESTIONS 1).
7. **The extract-start log line changed wording** (three counts); the structured event name
   and its `count` field are unchanged.
8. **Owner-side work done in the same sitting, disclosed for the record:** the backup timer
   enabled; the census worktree removed (its pin `873860a` is pre-rewrite history; the
   identical tree is `1ea9df8` on `master`); prepared scripts for (d) and (e). None touches
   the tree or the KB.

## REFUSED

- **The live witness** — not run: the backup gate (STATE) is not met; a run today would also be
  a weak witness (preview says the sweep would do nothing), but the gate is the reason.
- **B3** — not lifted (no witness).
- **The pin edit** — the agent's own edit of the out-of-tree config was declined by the
  permission layer; not retried by another route (it is the owner's item; script prepared).
- Nothing under `$LIFE_AGENT_KB` written; the live root only read (the preview, one
  `.eml`-prefix lookup, the artefact/row counts — all read-only, all disclosed); no `migrate
  counts` run this sitting (it belongs to the witness).
- No commit, no push (owner-executed script prepared and rehearsed).
- No re-derivation, backfill, or restoration of the 2,047; no queue rewrite outside
  `reconcile`; the SPEC's adjacent paragraphs not reworded beyond the signed replacement.

## QUESTIONS

1. **(reviewer) `_torn_reason`'s table** (DEVIATIONS 6): confirm *format_version missing →
   torn* (it deletes a `{}` meta.json — the pre-existing tests' fixture for an interrupted
   write) against the more conservative *any parseable JSON → left*. Also whether the SPEC's
   adjacent sentences ("Orphans are removed by a consistency sweep …"; the `delete_artifact`
   residue paragraph) should be reworded to say *torn* — a follow-on SPEC micro-edit, not done.
2. **(reviewer) Placement:** `register_directory` in `rebuild.py` with the local import from
   `cache.py` — accept, or move `_meta_to_row` / `_check_meta_consistency` / `_read_lineage`
   down into `cache.py` (a relocation the brief did not name)?
3. **(owner) The backup:** the fix for the exclusion — drop the `pkm/runs/…/cache` exclude on both
   hosts, or the root move onto the KB volume out from under `pkm/runs/` (then verify with
   `borg list … | grep <root>/cache/`) — and when an archive containing `cache/` exists →
   `BACKUP_ARCHIVE=<name> ~/.cache/life-agent/lineage-r01/b2-live-witness.sh`, then B3 as the
   addendum.
4. **(reviewer) Follow-on:** `life_agent.core.derivations._reconcile_one` re-implements what
   `rebuild.register_directory` now does; delegate (one code path for "files → rows") in a
   later micro-commit?
5. **(reviewer) A dry-run surface** on the CLI (`pkm rebuild-catalogue --dry-run` reporting
   torn / unregistered counts) — worth a SPEC line, or is the script + `preview_sweep` enough?
6. **(owner) The other three pins:** bump all four to installed (SPEC §14.5; accepting the
   re-extraction and the corpus-digest move — a deliberate, scheduled act) or leave them and
   treat an unscoped `pkm extract` on this box as a standing no-go? A5 needs only pandoc.

## PROPOSED

1. Owner reads the dry-run transcript above; runs `~/.cache/life-agent/r01-lineage-sweep-commit.sh`
   (five commits on `42f5e09`; `STOP_AFTER_B1=1` to land the SPEC alone first), reads
   `git log --oneline 42f5e09..HEAD`, pushes as a separate act.
2. Owner-side: the backup exclusion / root move → a verified archive → the live witness → B3
   addendum (report + `docs/unified-ledger-design.md` status note, one docs commit); the pandoc
   pin → A5 addendum to r00; the FAILURES.md entry (`~/.cache/life-agent/failures-append-r03.sh`).
3. Then the collapse-census placement (Q-R5) and tranche 2, per r04 §4. End of the micro-tranche
   at the witnesses.

## Rehearsal — transcript (before the STOP; the standing prepared-script pattern)

Fresh disposable detached worktree at `42f5e09`, the working-tree files and this report copied
in, a copy of the owner script with `REPO` pointed at the worktree and the `master` check
dropped (detached HEAD), `LIFE_AGENT_KB` exported, the armed pre-commit hook running on each
commit (`core.hooksPath=.githooks` resolves inside the worktree). Full path:
```
preflight ok: master @ 42f5e09, working tree == T4
committed e08e35d  45077b76  docs(pkm): SPEC 0.18.0 — §6.2 … (lineage B1, S-L2 Option A + rider, verbatim)
committed cde7eb9  6e9de61e  fix(pkm): write_artifact refuses duplicate lineage inputs … (lineage B2-i)
committed 4dd344b  235ef324  fix(pkm): rebuild._read_lineage collapses a repeated input … (lineage B2-ii)
committed 3d5bb8f  7d1de153  feat(pkm): the consistency sweep registers-or-leaves … (lineage B2-iii)
tree invariant ok: HEAD^{tree} == T4
committed cc20292  docs r01
working tree clean
done. Not pushed — push when you want:  git push origin master
```
The two-step path (worktree reset to `42f5e09` again): `STOP_AFTER_B1=1` → the SPEC commit
alone (`preflight ok … working tree == T4`, `committed c357f44 45077b76 …`, *"STOP_AFTER_B1:
the SPEC commit is in; re-run without it to land B2 + r01"*); the plain re-run → `preflight ok:
master @ c357f44 (the B1 SPEC commit), working tree == T4 — continuing with B2`, the four
remaining commits, invariant ok, clean. Those commits are throwaway (the worktree was removed
and pruned at the STOP; `master` untouched, `git status` unchanged). Transcript:
`~/.cache/life-agent/lineage-r01/rehearsal.txt`.

**→ STOP.** Phase B's code and SPEC are ready to land; the live witness and B3 wait on the
backup gate (STATE) and run as an addendum on the owner's word.

## Rulings applied — 2026-08-19 (post-review; the series gains a sixth commit)

The reviewer's verdict on this report: *"Phase B accepted; the series is ready to land; the
micro-tranche closes at the witnesses."* One ruling asked for a SPEC edit; done here and folded
into the same owner script as its **fifth** commit (after B2-iii, before the docs commit), so
the STOP's one-script rule holds, as r00 did with its Q1/Q2 follow-on. Rulings on the record,
verbatim where they bind:

- **The backup finding (Q3): answered — drop the exclusion on both hosts now**, not on the
  future root move: *"protection shouldn't depend on a relocation that hasn't happened, and if
  the move later lands, the exclusion simply stops matching anything."* Then `borg list … |
  grep <root>/cache/` as the verification, then `BACKUP_ARCHIVE=<name>` and the witness. The
  script's refusal without a verified archive name, and its writing that name into its own
  transcript, are *"exactly right"*. **Owner-side, in another session (owner's word this
  sitting: leave the backup to that session)** — nothing here touches it; the gate in STATE
  stands until that archive is named.
- **Q1 — the torn table is confirmed as built**, with the grounding stated for the record:
  *"torn = fails the minimal invariant every version of the writer has always guaranteed (a
  parseable JSON object bearing `format_version` and the v1 required fields; content-for-success;
  lineage-for-schema ≥ 2) — without `format_version` no parser can even determine which
  contract applies, and the writer's file-then-queue ordering means a complete write always
  carries it; left = parseable-but-out-of-contract in ways a future or foreign writer might
  legitimately produce, and the future is never deleted. The conservative alternative would
  leave genuinely torn `{}` writes WARNing forever — safe but a standing lie about the store's
  health."* **The follow-on SPEC micro-edit: yes** — *"reword the adjacent 'orphans are
  removed' sentences to torn, as 0.18.1, one commit, citing this ruling."* Done below.
- **Q2 — placement accepted as built:** *"registering a directory is a per-directory rebuild,
  the row construction belongs to the module that owns rows, and a function-local import is a
  smaller wart than relocating three functions the brief never named."* Relocation refused as
  scope creep; the `cache` ↔ `rebuild` cycle is recorded as a known wart, nothing more.
- **Q4 — the `_reconcile_one` delegation is approved, sequenced:** one code path for files→rows,
  but *"it lands as its own micro-commit after the witnesses and the push — no stacking on
  uncommitted work — with `ReconcileCounts` semantics preserved across the delegation (the loud
  dedup maps to `deduplicated`) and a test asserting count-equivalence."* **Not done in this
  sitting** (it would stack on this unlanded series); queued behind the witnesses.
- **Q5 — deferred:** `preview_sweep` plus the witness script suffice; a CLI flag is a SPEC
  surface with no consumer beyond the witness, and `left N` already gives the operator signal.
  Revisit on a second consumer.
- **The live witness's weakness is accepted** (a ruling the report implied rather than asked):
  with the store consistent (torn 0 / unregistered 0) the witness proves *deployment reality* —
  config, versions, permissions, and that nothing vanishes — not the register-or-leave
  semantics, whose strong evidence is the bench's end-to-end extract test. The B3 addendum says
  so in one sentence. **Under no circumstances is the live root seeded to strengthen it.**
- **Q6 — pandoc alone now; the other three pins later, as one deliberate act.** *"Bumping the
  remaining three changes corpus digests and triggers re-extraction — doing that mid-witness
  muddies the monotone criterion."* Sequence: (d) → A5 addendum lifts the ask-path constraint;
  witnesses → B3; *then* the four-pin alignment as its own signed, scheduled act with the
  re-extraction accepted. **Interim rule, standing: an unscoped `pkm extract` on this box is a
  no-go.**
- **DEVIATIONS 1–8 accepted.** Deviation 1 (Phase B opened on the verified commit transcript,
  not the ceremonial paste): *"substance over form, and the substance was the condition; noted
  once, no re-opening needed."* Deviation 8's owner-side work accepted as disclosed; the
  permission layer's refusal of the pin edit is *"the boundary working exactly as designed —
  out-of-tree system state is yours, by script."*

### 0.18.1 — the SPEC wording follow-on (Q1)

`docs/pkm/SPEC.md`, three edits and a change-log entry, wording only — no semantic change, no
code, no test touched (the sweep's contract remains the 0.18.0 paragraph):

- `:3` `Version: 0.18.1 (draft)`.
- `:291-292` *"ordering plus an explicit orphan sweep"* → *"ordering plus an explicit
  consistency sweep"*.
- `:298-308` the interrupted-write sentence, which said an interruption leaves *"an orphan cache
  directory … Orphans are removed by a consistency sweep"*, now distinguishes the two outcomes
  by **where** the interruption fell: before `meta.json` is complete → *torn* (content and/or a
  partial `meta.json`, no row; removed); after it → *unregistered* (a complete `meta.json`, no
  row; registered) — *"both defined precisely below"*, pointing at the 0.18.0 paragraph. (The
  old sentence was not merely stale vocabulary: an interruption between step 2 and step 3 of the
  write order leaves exactly the unregistered case, which under 0.18.0 is registered, not
  removed — the very r03 shape.)
- `:1895-1908` §16 entry `0.18.1 (draft)`: names the edit, its non-semantic nature, and the
  ruling it was made on (this section), with the reviewer's grounding of the torn table
  carried into the SPEC (one phrase paraphrased to the SPEC's own write-order vocabulary:
  *file-then-row* for the reviewer's *file-then-queue*).

Not changed, and raised as **QUESTIONS 7** below: §6.2's `delete_artifact` paragraph
(`:353-360` after this edit; 0.1.x prose) still says an interrupted delete *"leaves at worst a cache directory
without a row, which the next consistency sweep collects as an orphan"*. That sentence is not
adjacent to the sweep paragraph, and it is not a vocabulary problem — it is inverted relative to
the ordering it describes: `cache.delete_artifact` (`src/pkm/cache.py:456-467`) removes the
directory **first**, then the row, so an interruption leaves a **row without files** — the
asymmetric case §6.2 says aborts with `CacheInconsistencyError` — never a directory for the
sweep. The docstring at `src/pkm/cache.py:436-440` repeats the inversion. Out of this ruling's
scope (a substantive correction, not a rewording); left as is, flagged.

Guard: exit 0 on `docs/pkm/SPEC.md`. Trees: `build_trees.sh` gains **T5** = T4 + the 0.18.1
SPEC (`states/SPEC.0181.md`); rebuilt, **T0..T4 byte-identical to before** (the pre-edit
`trees.txt` kept beside it), `T5=e265e479…`, `05-spec-0181.patch` (65 lines), the builder's
invariant now `T5 == working tree`. Owner script (`~/.cache/life-agent/r01-lineage-sweep-commit.sh`,
pre-edit copy kept as `.pre-0181`): preflight expects the working tree at **T5**; the B2
invariant `HEAD^{tree} == T4` stays; then `commit_tree_step "$T5" 'docs(pkm): SPEC 0.18.1 …'
docs/pkm/SPEC.md`, invariant `HEAD^{tree} == T5`, then the docs commit (message now records the
review + rulings). Six commits. `STOP_AFTER_B1=1` unchanged (continuation still keys on
`HEAD^{tree} == T1`).

### QUESTIONS (continued)

7. **(reviewer) §6.2's `delete_artifact` paragraph** (`docs/pkm/SPEC.md:353-360`) and the
   docstring at `src/pkm/cache.py:436-440` say an interrupted delete leaves *"a cache directory
   without a row"* for the sweep to collect; the code (`:456-467`) removes the directory first,
   then the row, so the residue is a **row without files** (the `CacheInconsistencyError`
   direction; a re-run of `--retry-failed` clears it, since `delete_artifact` skips the missing
   directory and deletes the row). The code's ordering is the right one under 0.18.x — were the
   delete row-first, an interruption would leave a *complete* directory without a row, which the
   sweep now **re-registers**, resurrecting a half-deleted artefact — so the correction is
   prose-side: §6.2 and the docstring should say the residue is a row without files and how it
   clears. A substantive correction, not a rewording — proposed as its own micro-edit after the
   witnesses, not folded here.

### Verification (this sitting)

- `tests/pkm` at the working tree (= T5; the code trees T1..T4 are byte-identical to the
  bisected ones — only `docs/pkm/SPEC.md` differs from T4):
  ```
  $ LIFE_AGENT_KB=<kb> TMPDIR=~/.cache/… uv run pytest tests/pkm -q --basetemp=~/.cache/life-agent/basetemp-lineage -p no:cacheprovider
  477 passed, 17 deselected in 90.58s (0:01:30)        exit=0
  ```
- Guard: exit 0 on `docs/pkm/SPEC.md` and on this report.
- Rehearsal repeated on the six-commit script — fresh disposable detached worktree at `42f5e09`,
  the working-tree files and this report copied in, the script copy differing from the owner's
  only in `REPO` and the dropped `master` check (diffed to confirm), `LIFE_AGENT_KB` exported,
  `core.hooksPath=.githooks` resolving inside the worktree. **The first two-step take
  exposed a defect the five-commit script never had:** after `STOP_AFTER_B1=1` the B1 checkout
  leaves the 0.18.0 SPEC in the working tree, so the re-run's preflight refused (*"working tree
  drifted from the bisected state T5"*) — under the old script T1's SPEC equalled T4's, so
  nothing showed. Fixed: the STOP branch restores `docs/pkm/SPEC.md` from T5 (checkout +
  unstage) and says so. Retaken, both paths, on the final script:
  ```
  === plain path
  preflight ok: master @ 42f5e09, working tree == T5
  committed 4454f63  45077b76  docs(pkm): SPEC 0.18.0 — … (lineage B1, S-L2 Option A + rider, verbatim)
  committed 7bb6834  6e9de61e  fix(pkm): write_artifact refuses duplicate lineage inputs … (lineage B2-i)
  committed 11515af  235ef324  fix(pkm): rebuild._read_lineage collapses a repeated input … (lineage B2-ii)
  committed 31b3c30  7d1de153  feat(pkm): the consistency sweep registers-or-leaves … (lineage B2-iii)
  tree invariant ok: HEAD^{tree} == T4 after B2
  committed adc96ca  e265e479  docs(pkm): SPEC 0.18.1 — §6.2 wording … (lineage B, post-review follow-on)
  tree invariant ok: HEAD^{tree} == T5
  committed cacbfec  docs r01
  working tree clean
  done. Not pushed — push when you want:  git push origin master
  === STOP_AFTER_B1=1
  preflight ok: master @ 42f5e09, working tree == T5
  committed e8b00a4  45077b76  docs(pkm): SPEC 0.18.0 — …
  STOP_AFTER_B1: the SPEC commit is in (working tree restored to T5: docs/pkm/SPEC.md at 0.18.1, unstaged); re-run without it to land B2 + 0.18.1 + r01
  --- working tree between the two runs: the eight modified files + the untracked report (SPEC at 0.18.1)
  === continuation
  preflight ok: master @ e8b00a4 (the B1 SPEC commit), working tree == T5 — continuing with B2
  committed 9727047 … a5760bd … e36a806 …  tree invariant ok: HEAD^{tree} == T4 after B2
  committed af78c44  e265e479  docs(pkm): SPEC 0.18.1 …   tree invariant ok: HEAD^{tree} == T5
  committed ee32a4b  docs r01   working tree clean
  ```
  The rehearsal HEAD's `docs/pkm/SPEC.md` is byte-identical to the working tree's. Those
  commits are throwaway (worktree removed and pruned; `master` untouched at `42f5e09`, `git
  status` unchanged: eight modified files + this report). Transcript:
  `~/.cache/life-agent/lineage-r01/rehearsal2.txt`.

**Next, in order** (the reviewer's consolidated list, minus what is done here): the owner
reads the dry-run transcript (DONE, B2 — the sweep would touch nothing today), runs
`~/.cache/life-agent/r01-lineage-sweep-commit.sh` (**six** commits on `42f5e09`;
`STOP_AFTER_B1=1` first if the SPEC should land separately), reads `git log --oneline
42f5e09..HEAD`, pushes as its own act; the other session drops the cache exclusions on both
hosts, verifies with `borg list … | grep <root>/cache/`, names the archive →
`BACKUP_ARCHIVE=<name> ~/.cache/life-agent/lineage-r01/b2-live-witness.sh` → the B3 addendum
(this report + `docs/unified-ledger-design.md`'s status note, one docs commit; one sentence on
what the witness does and does not prove); `~/.cache/life-agent/pandoc-pin-bump.sh` → A5 →
its addendum to r00 (lifts the ask-path constraint); `~/.cache/life-agent/failures-append-r03.sh`.
Then the Q4 delegation micro-commit (its own act, count-equivalence test), the Q7 correction,
the four-pin alignment as one signed act — and the micro-tranche is closed, Q-R5 places the
census, and tranche 2 opens.
