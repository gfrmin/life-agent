# r04 — stock-take (tranche 1 closed → what opens next) — 2026-08-19

The stock-take the reviewer's r03 ruling asked for ("then we take stock properly"), opened on
the owner's word after the close commit was pushed. It is an inventory, not a design doc:
where tranche 1 left the system, what is still owed from it, the state of tranche 2's two
inputs (the module-collapse census and the fold-depth cost report), and — as an appendix — the
**draft** session brief for the pkm lineage micro-tranche (fixes (a)–(c)), for the owner and
reviewer to sign, amend, or reject. Everything below is verified against this box today;
transcripts are pasted where short. British spelling; locators, never values; no corpus data.

## STATE

```
$ git rev-parse --short HEAD origin/master && git status --short | wc -l
f4d1ab0
f4d1ab0
0
```

Full default suite, lint, types (run 2026-08-18 22:06Z–22:10Z, `TMPDIR`/`--basetemp` pinned
under `~/.cache` per the standing rule; transcripts `~/.cache/census-r01/p4/{suite,ruff,mypy}.txt`):

```
$ TMPDIR=~/.cache/census-r01/tmp uv run pytest -q --basetemp=~/.cache/life-agent/basetemp-stocktake -p no:cacheprovider
2384 passed, 34 deselected in 195.35s (0:03:15)
exit=0
$ uv run ruff check src tests scripts
All checks passed!
$ uv run mypy
Success: no issues found in 207 source files
```

**A finding from running the suite (disclosed here, not smoothed):** the run touched the
owner's *live* pkm store. `catalogue.duckdb` and `external/pending.txt` under the live root
were rewritten at 06:07:11 local, one minute into the run — `pending.txt` went from 2,048 keys
(one registerable) to 2,047 (none). The cause is `tests/test_ask.py:152-158`
(`test_main_returns_2_on_locked_corpus`): it calls `ask.main(["…"])` with only `connect`
monkeypatched, so `main` runs the real startup path — `D.reconcile(_pkm_root())`
(`scripts/ask.py:1515-1519`, the live root resolves from `PKM_CONFIG`, independent of
`LIFE_AGENT_KB`) and then `ensure_gtd_fresh()` (`:1524`) — before `connect()` raises. Its
neighbours patch `_pkm_root` to `None` (`tests/test_ask.py:174`, `:224`); this one does not.
Today the effect was benign (one registerable key registered — reconcile is idempotent) and
`ensure_gtd_fresh` was a no-op (the state doc is stamped; the GTD ledger has not moved since
2026-07-28). But with `LIFE_AGENT_KB` exported and a *stale* GTD state, this test would run the
live extract (`:1357`) — i.e. **the orphan sweep from inside the test suite**, the r03 finding's
deletion path. Not fixed here (no code change without a brief); it is item A0 of the draft
micro-tranche brief (Appendix A) and an operational note in §2 below.

Files touched by this session: this report only. KB reads: `ledger/MANIFEST.json` (counts),
`tasks/state.md` + `tasks/events.jsonl` (mtimes only), `FAILURES.md` (a `grep -c` for the
2026-08-18 entry — absent). pkm-root reads: `external/pending.txt`, a read-only catalogue
connection (row counts), a `meta.json` directory walk (counts). No writes anywhere except this
file — save the indirect one the suite made, disclosed above.

## DONE — the stock, in four ledgers

### 1. Tranche 1 — end state

**On `origin/master` (`1ea9df8..f4d1ab0`, seven commits, the whole series pushed):**

```
f4d1ab0 ledger(r03): close — C6 count with live traffic (13/14 GREEN; A11 amended by ruling …); counts names legacy-side deletions; design §4 dangling identities; r03-merge report
4780991 feat(ledger): dual-write hooks at the nine typed writers (§8 C5) — legacy-append-first, configured-store-only, hermetic in tests
3de1749 feat(ledger): live mirror (§8 C5) — append-shaped, fail-open counted, recorded switch; unwired
360380c docs(unification): design doc (rev. V4/V5/V8, r03a-review rulings, Addendum D) + r00–r03a; S10 relocation; governor register entry
809226d feat(ledger): golden-replay harness (§9) — kills 1–5 with V4 flags, S8 lifecycle, --from stream, S7 julia-run; all ledger tests
da3d76d feat(ledger): legacy parsers + migration writer/sweeps/two-route counts (§8 C0–C2) and the §7 adapters (C3)
eee0094 feat(ledger): unified event schema + segment store (§10: torn tail, manifest lock, batch append)
```

**Live on this box (the stream's manifest, read today; counts only):** epoch `20260818T100854Z`;
`mirror_state.enabled = true` (recorded 2026-08-18 14:37:52Z); quarantine empty; last sweep
2026-08-18 14:43Z. Writer tallies: `act.tasks` 300 · `act.trips` 339 ·
`calibration.claude_verdicts` 180 · `calibration.corrections` 0 · `calibration.decisions` 2,442
(8 mirror appends) · `calibration.gather_outcomes` 64 · `calibration.outcomes` 905 ·
`calibration.reactions` 15 (1 mirror append) · `eval.labels` 21 · `pkm.artifact` 32,445 ·
`pkm.demand` 104,027 · `utility.elicitations` 5. No traffic since the close.

**pkm cache vs catalogue today:** `artifacts` rows 30,398 = `meta.json` directories 30,398;
**unregistered on-disk artefacts 0** (nothing the next sweep would remove); `joint_extract`
rows 313 (the survivors of r03's finding); `pending.txt` 2,047 keys, **all dead** (their
`meta.json` is gone — the swept set) — the queue never drains of them because
`_reconcile_one` raises `FileNotFoundError` for each (`core/derivations.py:534-536`) and
`reconcile` keeps a raising key "for later" (`:517-518`).

**Standing:** the mirror is on at every typed writer (`LIFE_AGENT_LEDGER_MIRROR=0` is the
recorded rollback; `git revert 4780991` the code one); sweeps are the manual
`python -m life_agent.ledger.migrate sync all`; **no reader has cut over; nothing is retired;
the quarantine rule (S6) is permanent.** Dormant by design: `lookup.confirm_hits` /
`/probe/confirm` (refused by its own criteria, r03a), the ask-path sweep invocation
(r03-merge Q1, unruled). The design doc's status block carries the r03-close revision (§4
dangling identities; §9 A11 amended by ruling).

### 2. Open items carried out of tranche 1 — each verified today

| # | Item (owner of the action) | Status 2026-08-19 | Evidence |
|---|---|---|---|
| (d) | pandoc pin (owner, "today") | **NOT done** — the retry loop stays armed for the next GTD ledger move | `PKM_CONFIG` → `producers.pandoc.version: "3.6"`; `pandoc --version` → 3.10.2 |
| (e) | FAILURES.md entry (owner-signed, out of tree) | **NOT appended** | `grep -c 2026-08-18 $LIFE_AGENT_KB/FAILURES.md` → 0 |
| infra-1 | pkm live root into borg (owner) | **NOT done — and the audit found the gap is wider.** The owner's backup script (the `borg create` wrapper `travel-backup.sh` in the home `bin/`, its `SOURCE_DIRS` block) lists eleven source directories on the KB volume; **`$LIFE_AGENT_KB`'s own directory is not among them** (the KB is a sibling of the listed directories, not a child) and neither is `~/.local/share/pkm`; `pkm/runs/**/cache` is additionally excluded (its `--exclude` list). Further: no systemd timer (user or system), no cron line, and an empty borg log directory (the one the script writes to) — **no evidence the script runs on this box at all** (the machine notes' "bi-hourly borg" may describe another host). If this is right, the calibration ledgers, the GTD/trips ledgers, `utility/`, and the unified stream have **no backup**. Verify against the other host before acting on it; then add both roots and confirm a run. | the script itself; `systemctl --user list-timers --all`; `systemctl list-timers --all`; `crontab -l` (two unrelated jobs); the log directory listing → empty |
| infra-2 | executor daemon + bridge (owner) | **down** (every ask falls back in-process) | `curl 127.0.0.1:8798/health`, `:8799/health` → connection refused |
| infra-3 | census worktree removal (owner) | still registered at `873860a` | `git worktree list` |
| infra-4 | the standing signature slot (owner) | open | — |
| Q | r03-merge QUESTIONS 1–3 (sweep wording doc-vs-brief; the schema-3 `kernel_id` forward-fix landing site; the ~30 ms mirror cost) and r03a Q14/Q15 | **unruled, carried** | r03-merge §QUESTIONS |
| C | standing constraint: no eval/gate run followed by an ask that refreshes | **in force** until (a)–(c) land — and, from today's finding, **run the test suite without `LIFE_AGENT_KB` exported** (pytest does not need it; the PII hooks do — export it for `git commit`/`git push` only) until A0 lands | STATE above |

### 3. Tranche 2's inputs — the state of each

**(i) The module-collapse census** (`~/.cache/life-agent-census/r00-collapse-census.md`,
734 lines, pinned at `873860a`, written outside the tree while tranche 1 held the write token).

- *Placement:* not yet in the tree; its own Q-R5 asks the reviewer to confirm the name
  (`docs/unification/reports/r00-collapse-census.md`) before it is placed. The full PII guard
  (denylist + shapes, with `LIFE_AGENT_KB` set) passes on it today: `python3
  .githooks/pii_check.py ~/.cache/life-agent-census/r00-collapse-census.md` → `exit=0`. A
  prepared placement+commit script exists (`~/.cache/life-agent/r00-collapse-place.sh`), gated
  on Q-R5 — the owner runs it once the name is ruled.
- *Signatures it is waiting for:* owner Q-O1…Q-O6 (they set the tranche-2 design doc's scope:
  the executor's body-held choices; the gate's exemption; the membrane's second utility table;
  which invariant governs `calibration.py`'s host fold; the Ū divergence D-8; the reach
  surface's `/log_decision` fields); reviewer Q-R1…Q-R5.
- *Drift since its pin* — five commits, 18 files under `src/`+`scripts/`, of which nine are files
  the census cites: the C5 hooks inserted two lines after each writer's legacy append (three in
  the four `core/*` writers whose append line was also re-wrapped). Everything the census cites
  **before** the insertion point is unchanged; cited lines at or after it shift by the delta:

  | file | lines ≥ | shift | census rows affected (examples) |
  |---|---|---|---|
  | `core/decisions.py` | 143 | +3 | `DEC.read :145` → 148 |
  | `core/reactions.py` | 112 | +3 | `load_reactions :176-205` → 179-208; `_lookup_reaction :137` → 140; `:139-147`, `:157`, `:165-168`, `:184-187`, `:194` likewise |
  | `core/outcomes.py` | 152 | +3 | `reliability_bins :208` → 211; `ece :230` → 233 |
  | `core/claude_verdicts.py` | 129 | +3 | `latest_by_decision :137` → 140 (`y :100` unchanged) |
  | `core/gather_outcomes.py` | 85 | +2 | `warm_counts :87` → 89; `:91`, `:105-106` likewise (`sensors_from :59-63`, `GROW_ACTUATORS :47-51` unchanged) |
  | `tasks/events.py` | 197 | +2 | `load :199-211` → 201-213; `fold :214` → 216 |
  | `trips/events.py` | 129 | +2 | (the census cites `trips/fold.py`, `trips/identity.py` — unchanged) |
  | `scripts/answer_labels.py` | 91 | +2 | — |
  | `scripts/verdict.py` | 178 | +2 | — |

  The new `src/life_agent/ledger/` package is not cited by the census. The census's own
  verifier re-run at `f4d1ab0` reports the same totals as at the pin (it checks existence and
  range, not identity at the line, so a +2/+3 shift is invisible to it — a limit worth knowing).
  Recommendation: place the census **as pinned** (its STATE already says "as of `873860a`") with
  this table cited from it, and re-cite at the tranche-2 design-doc phase against that phase's
  HEAD; do not re-verify 1,139 references for a nine-file shift.

**(ii) The fold-depth cost report** (`bench/bench-fold-depth-r01.md` in the sibling
`proplang` repository; uncommitted three-commit series in its PROPOSED; the owner's acceptance band was
never filled in, so it carries no verdict). Its headline: per-tick cost under exact rational
arithmetic grows as c(t) = c0 + a·t^α with α_3p ≈ 1.43–1.60 on all profiles (bits grow
linearly, β ≈ 1; GMP's gcd/multiply cost ≈ bits^1.5); at its operating point (10⁴ ticks
accumulated) P1 ≈ 21 ms/tick solo, P2 ≈ 25 s/tick *projected*, P3 ≈ 10³ s/tick projected — and
its P2 world was a *reconstruction* (its Q1) that must be re-run at the consumer's parameters.
**The consumer facts that answer its owner questions Q1–Q3 are in this tree, and they reframe
the P2 re-run:**

- *Q1 (which document carries the utility model's arity and grids).* There is no grid on the
  wire. Each utility latent is a **continuous truncated Gaussian on a stated support**
  `{mu, sigma, lo, hi}` — `core/utility.py:20-24` ("bounds are stated support, not a grid …
  the engine integrates over the support internally"), the 1-D state at `:346-350`, the
  coupled `truncated_mv_gaussian` at `:403-408`; τ and τ_narrative are marginalised against
  their priors, never updated (`:13-16`). The model file's `grid.n` stanza is the legacy
  truncation declaration (in-tree schema example `config/utility-model.example.yaml`: six
  latents with `n` 97/53/36/35/25/33, τ and τ_narrative `n` 8 — the owner's live values are
  out of tree). Evidence arity today: 5 elicitations + 15 reactions in the live stores (only
  abstain-decision reactions fold, `core/reactions.py:17-20`) → **the utility fold's depth is
  ≤ 20 events**. The other two fold families on the same wire: the extractor-reliability fold —
  a `beta` state, Beta(4,4), conditioned once per graded outcome row with a `bernoulli` kernel
  (`core/lookup.py:190-191`, `:492-500`) over the 905-row outcomes log → **depth ≈ 10²–10³**;
  and the per-ask lookup posterior — `reliability_categorical` + one `group_noisy_channel`
  condition per document group (`:821-862`) → **depth < 10 per ask**.
- *Q2 (ticks per event).* Every state is created, conditioned, read, and **destroyed within
  one call** (`_fold_1d` `:346-359`, `_fold_joint`, `_extractor_rho_state`'s "the caller reads
  + destroys it"): the consumer **re-folds from scratch on every ask** and accumulates no
  session. So a tick is one `condition`; an ask costs ≈ 20 + ~900 + n_obs ticks, all
  discarded; there is no month-long 10⁴-tick session anywhere in the consumer as built. The
  bench's operating point describes an always-on persistent session the consumer does not run
  — it would become the consumer's shape only if the swap tranche also changed the fold
  discipline (persistent state, no re-fold), which is a design decision, not a given.
- *Q3 (decimals vs binary-exact grid values).* No grid values are declared on today's wire, so
  the question does not arise for the consumer as built; **if the swap discretises**, the
  bench's "sixteenths" rule applies from day one, and P3's 100× lever is avoidable by
  declaration.
- *Consequence for the P2 re-run (bench PROPOSED 2, QUESTIONS 1/6):* a P2 built as
  `UConst + UWalk over one grid` is not a faithful world for this consumer; the truthful P2 is
  either (α) the consumer's *actual* per-ask folds — a Beta-Bernoulli at depth ~10³, a
  categorical-with-reliability at depth < 10, and six truncated Gaussians at depth ≤ 20, each
  re-folded from scratch — whose per-tick cost at those depths the bench already brackets at
  the P1 end (tick 1 ≈ 0.3 ms; depth 10³ well under the P1 curve), or (β) a discretised
  persistent-session redesign whose parameters do not exist yet. Under (α) the swap's cost
  question is small and the swap's *representational* question is the real one:
  continuous truncated Gaussians and analytic Beta marginalisation (`:826-832` "NO grid") vs
  proplang's exact discrete hypothesis worlds. **Recommendation:** answer the bench's Q1–Q3
  from this section, do *not* run the overnight P2@10⁴ (Q6), and make "which of (α)/(β) is
  the swap's target" the first question of the seam-swap tranche's own census; the bench's
  `--world FILE` door (its PROPOSED 2) is worth building only once (α)/(β) is chosen.

### 4. What is ready to open, and in what order (recommendation)

1. **The pkm lineage micro-tranche** — the draft brief is Appendix A. Smallest, closes a live
   data-loss path (the sweep-at-extract-start over unregistered §18.9 artefacts), lifts the
   standing constraint, and fixes the suite-hermeticity gap found today. Opens on the owner's
   and reviewer's signatures on the brief.
2. **Owner-side, today, no tranche:** (d) the pandoc pin; (e) the FAILURES.md entry; the backup
   audit in §2 infra-1 (verify the job exists anywhere; add the KB and the pkm live root); the
   executor daemon; the census worktree.
3. **The collapse census placement** on Q-R5, then owner signatures Q-O1…Q-O6 → the tranche-2
   design-doc phase opens on the census's own PROPOSED terms.
4. **The fold-depth report:** the owner fills the band and reads §3(ii); the P2 re-run is
   reframed as above; the proplang three-commit series is the owner's to land or not.

## DEVIATIONS

1. This report sits in the tranche-1 `rNN` series (`r04`) although no tranche-1 phase remains —
   chosen so cross-references stay stable; the reviewer may rename (Q2 below).
2. The suite run touched the live pkm store (STATE) — not intended; disclosed with cause and
   effect. It also means the "no writes" claim in STATE carries that one indirect exception.
3. The stock-take answers the bench's owner questions Q1–Q3 from the code rather than leaving
   them to the owner (§3(ii)); the answers are facts with locators, and the *reading* of them
   (α/β) is marked as a recommendation.
4. The backup finding (§2 infra-1) goes beyond the reviewer's "add the pkm root to borg" — the
   audit was of the source list the ruling named, and what it showed is reported whole.

## REFUSED

- No code changes: not the one-line A0 test fix, not (a)–(c), not the SPEC amendment — all are
  in the draft brief for signature.
- No placement of the collapse census (Q-R5 gates it); the script is prepared, not run.
- No commit, no push; no KB write; no pkm-root write (the indirect one is disclosed).
- No verdict on the fold-depth band (the owner's), no seam-swap judgement.

## QUESTIONS

1. **(owner)** The backup finding: is there a borg job on another host that covers
   `$LIFE_AGENT_KB` and the pkm live root? If not, the calibration ledgers, the GTD/trips
   ledgers, `utility/`, and the unified stream are unbacked today — the priority is above
   every tranche.
2. **(reviewer)** Numbering/placement of this report (`r04-stocktake.md`) and of the
   micro-tranche's reports (proposed `r00-lineage-writer.md`, `r01-lineage-sweep.md`,
   following the collapse census's `r00-collapse-*` convention).
3. **(reviewer)** A0 — the suite-hermeticity fix (`tests/test_ask.py:152-158` patches
   `_pkm_root` like its neighbours): part of the micro-tranche's Phase A as drafted, or a
   standalone one-line change now? The exposure is bounded (the reconcile it runs is idempotent;
   the extract only fires on a stale GTD state), and the standing constraint plus the
   "run pytest without `LIFE_AGENT_KB`" note cover it meanwhile.
4. **(owner)** §3(ii): accept the consumer facts as the answer to the bench's Q1–Q3, and the
   (α)/(β) reframing of the P2 re-run?
5. **(owner/reviewer)** The draft brief in Appendix A — sign, amend, or reject; in particular
   the two rulings it needs before it can open (SPEC route for Phase B; the dead-key policy).

## PROPOSED

Open the pkm lineage micro-tranche on the signed brief (Appendix A). Owner-side today: (d),
(e), the backup audit, the daemon. Everything else waits on the signatures named in §3.

---

## Appendix A — DRAFT session brief: pkm lineage micro-tranche (unsigned)

*Drafted by the agent on the owner's word, from the r03 finding and the reviewer's ruling that
sequenced fixes (a)–(c) into "a separate micro-tranche with its own SPEC-first brief". It is a
proposal: the owner and reviewer sign, amend, or reject. Where it needs a ruling before it can
open, it says so.*

# Session brief — pkm lineage micro-tranche (the §18.9 writer, reconciler, caller, and the §6.2 sweep)

You are working in the `life-agent` repository under `CLAUDE.md` governance and, for anything
under `src/pkm` or `docs/pkm`, under `src/pkm/CLAUDE.md` and `docs/pkm/SPEC.md` (SPEC-first,
TDD, idempotency double-runs — PRINCIPLES §11). This brief is narrow-scoped; everything outside
§Scope is on the refusal list. You stop at every STOP line, write the report named there, and
wait.

## Controlling texts (read in this order before touching anything)

`PRINCIPLES.md` §7, §10, §11; `docs/pkm/SPEC.md` §5.1–§5.3, §6.2, §13.1, §14.3, §18.4, §18.9;
`docs/pkm/SPEC-PRINCIPLES.md`; `docs/unified-ledger-design.md` §4 (dangling identities), §9
(A11 as amended); `docs/unification/reports/r03-merge.md` §THE FINDING and §Rulings on the C6
finding; `docs/unification/reports/r04-stocktake.md` (this report) §STATE and §3(i). Where this
brief and those texts conflict, stop and report the conflict.

## Mission

On 2026-08-18 the unified ledger's two-route count exposed the deletion of 2,047 external
derivations (`life_agent.ask.joint_extract`, schema 3) from the pkm cache. The causal chain,
each link verified in r03: the writer recorded **duplicate lineage inputs**
(`src/life_agent/core/joint_extract.py:120-124` — one entry per hit; several hits of one
artefact ⇒ the same key twice); the reconciler's per-entry insert tripped
`artifact_lineage`'s primary key `(artifact_cache_key, input_cache_key)`
(`src/pkm/migrations/0003_transform_substrate.py:43-49`; `core/derivations.py:559-564`), the
transaction rolled back (`:566-568`) and `reconcile` swallowed the exception, keeping the key
"for later" (`:517-518`) — silently, and the ask path wraps the call in
`contextlib.suppress(Exception)` (`scripts/ask.py:1515-1519`); the artefacts therefore stayed
**unregistered** for up to two months; and pkm's orphan sweep at `extract` start
(`src/pkm/extract.py:202` → `src/pkm/cache.py:459`, SPEC §6.2), reached from the ask path's GTD
refresh (`scripts/ask.py:1343-1358`, retrying every ask on a config pin mismatch), removed
them. Occurrence records survive in the stream (design §4's dangling-identity class); the
content and the recorded draws do not.

After this micro-tranche: (1) no §18.9 writer in this tree can record duplicate lineage inputs
and the seam refuses them; (2) reconciliation failures are loud, per key, and counted; a
dedup-on-read never launders silently — the ledger census counts it; (3) the ask path never
runs an extract while a registerable artefact is unregistered — reconcile-or-refuse; (4) the
test suite cannot reach the owner's live pkm root; and, gated on a SPEC signature, (5) pkm's
sweep no longer deletes a file-complete artefact because its index row lags — the SPEC's own
§13.1 ("`meta.json` is authoritative; the catalogue is a rebuildable index") applied to the
sweep, resolving the §6.2 / §18.9 contradiction the loss exposed (§6.2 defines "orphan" as
"no catalogue row"; §18.9 makes a lagging row "a consistent state, not a corruption"; `pkm
rebuild-catalogue` already *registers* such directories — `src/pkm/rebuild.py:169-195` inserts
every parseable `meta.json` before it sweeps — while `pkm extract` deletes them: two sweeps,
one SPEC, opposite verdicts on the same directory).

## Signatures this brief needs before it can open (proposed text; the owner signs or strikes)

- **S-L1 (scope).** Phase A (life_agent-side, no SPEC change) is authorised as written. Phase B
  (a SPEC amendment + a pkm code change) opens only on S-L2.
- **S-L2 (the SPEC route for Phase B) — ruling required.** Option A: amend SPEC §6.2 so the
  sweep registers-or-leaves file-complete unregistered directories (proposal text in Phase B).
  Option B: leave §6.2's sweep as is and add a §18.9 rider making it the *writer's* duty to
  reconcile before any operation that sweeps (Phase A's (c) is then the whole fix for the ask
  path, and every other trigger — a manual `pkm extract`, the harness — stays exposed). The
  draft recommends **A**, with B's rider *also* added as a writer obligation.
- **S-L3 (dead keys) — ruling required.** A queued key whose `meta.json` no longer exists is
  a dead entry (its artefact was removed). Proposed: `reconcile` drops it from the queue with
  one WARNING naming the key and increments a `dead` count in its return; the queue is a
  rewritten drain queue, not a ledger (r00 census; design §4) — the truth of the deletion is
  the stream's dangling identity, not the queue line. Alternative: keep dead keys forever
  (2,047 `stat` calls per ask, a queue that never drains).
- **S-L4 (report names).** `docs/unification/reports/r00-lineage-writer.md` (Phase A) and
  `r01-lineage-sweep.md` (Phase B), following the collapse census's convention.

## Out of scope — refusal list

Refuse, and record the refusal: any pkm change before S-L2 (Phase A touches nothing under
`src/pkm`); any change to `compute_cache_key`, cache layout, or the determinism contract; any
reader cutover, retirement, or compaction of any store; any deletion or rewrite of a ledger, log,
or cache artefact (the dead-key drop under S-L3 is a queue rewrite the queue already performs on
every call — `derivations.py:521-527`); any backfill or re-derivation of the 2,047 lost artefacts
(they are re-derived on demand by re-asks; a batch re-derivation is a separate, priced decision);
`PRINCIPLES.md`; the brain seam, the spine, the collapse tranche; new dependencies, top-level
directories, or file formats. `$LIFE_AGENT_KB` writes only under `ledger/` (S1); pkm-root
writes only through the sanctioned seams the phases name; PII rules as standing (synthetic
fixtures, locators never values, digests pass, record values do not).

## Phases

**Phase A — the writer, the seam, the reconciler, the caller (life_agent side; TDD; no SPEC
change).** One conceptual move per commit, each green and bisectable.

- **A0 — the suite cannot reach the live root.** `tests/test_ask.py:152-158` patches
  `ask._pkm_root` to `None` like its neighbours (`:174`, `:224`). Then a *proof*, not a hope:
  the report pastes the live root's `catalogue.duckdb` and `external/pending.txt` mtimes before
  and after a full suite run with `LIFE_AGENT_KB` exported — unchanged. (Whether a broader
  autouse guard is wanted — every test's `_pkm_root` and `config.pkm_root` pointing at a tmp
  root unless a test opts in — is a QUESTION for the report, not a decision here.)
- **A1 — the writer.** `core/joint_extract.py:120-124` records **unique** lineage inputs, first
  occurrence order preserved (the idiom already used at `core/synthesis.py:85-86` and
  `scripts/ask.py:732-733`: `dict.fromkeys(...)`). Test: a pool with two hits of one artefact
  records one lineage entry for it. Then **audit every lineage-writing site** and table it in
  the report (`derivations.record` callers: `joint_extract.py:120`, `lookup.py:562/612/718/1110`,
  `narrative.py:510`, `synthesis.py:87`, `scripts/ask.py:734`, plus `expansion.py:171`,
  `deliberate.py:391`, `temporal_intent.py:85`, `subject.py:208`, `scripts/route_audit.py:51`
  with empty/single lineage): for each, whether duplicate inputs are structurally impossible,
  already deduplicated, or possible — `lookup.py:1110-1112` (`lookup_answer`: one entry per
  observation, and two hits with identical chunk text share an extract key,
  `lookup.py:593-597`) is the one to settle by a **test**, not by reading.
- **A2 — the seam refuses.** `derivations.record` raises `ValueError` on duplicate lineage
  inputs — the contract of §18.4/§18.9 enforced where the file is written, so a duplicate can
  never reach disk again from any writer (a writer bug surfaces in that writer's tests, not in
  the sweep two months later). Test: `record` with a duplicated input raises and writes nothing
  (no directory, no queue line).
- **A3 — the reconciler is loud and counted.** `reconcile` logs each per-key failure at WARNING
  with the exception class and the key (never content) and returns/prints a per-class count
  (inserted · already-present · retry-later · dead per S-L3 · malformed-lineage); `_reconcile_one`
  deduplicates lineage inputs **on read** for artefacts already on disk (the doctrine as ruled:
  dedup-on-read must not launder what the writer should never produce — so it logs at WARNING
  naming the key and the duplicate count) and registers the artefact; and the ledger census
  counts the class: `src/life_agent/ledger/sources.py:377-428` (`_scan_artifacts`) adds
  `lineage_duplicate_inputs` (artefacts whose on-disk `lineage.json` repeats a key; today the
  envelope silently collapses them at `:225`) to its extras, so `migrate counts` shows a laundered
  dedup as a number. Tests: a synthetic duplicate-lineage artefact reconciles with a WARNING and
  one lineage row; the census counts it; a dead key follows S-L3.
- **A4 — the caller: reconcile-or-refuse.** `scripts/ask.py:_reingest_state` calls
  `D.reconcile(root)` **immediately before** `pkm_extract` (`:1357`) — the startup call at
  `:1515-1519` does not cover the REPL's per-question refresh (`:1453`); if registerable keys
  remain pending after it (a key whose `meta.json` exists), the refresh **refuses to extract**:
  it prints a new `REFRESH_NOTES["blocked"]` line naming the count (drift-gated with the table,
  `tests/test_ask_gtd_refresh.py`), leaves the state doc un-stamped so the next ask retries, and
  never reaches `pkm_extract`. Test: with a fake extract, a pending registerable key ⇒ the
  extract is not called and the blocked line prints; with none ⇒ it is called.
- **A5 — the operating constraint's first witness (optional within A, on the owner's word):**
  one eval/gate run followed by a refreshing ask, with the two-route count taken before and
  after (`migrate counts`): stream ⊇ legacy, difference unchanged, `pkm.artifact` legacy count
  monotone. If it holds, the standing constraint is lifted for the *ask path*; manual `pkm
  extract` / `rebuild-catalogue` remain covered by Phase B.

→ **STOP. Report `r00-lineage-writer.md`.** Pre-stated acceptance: A0's before/after mtimes
unchanged; A1's test green and the audit table complete; A2's refusal test; A3's WARNING +
one-row test, the census count visible in `migrate counts` output (transcript), the dead-key
behaviour per S-L3; A4's two tests; suite green, ruff, mypy; guard exit 0 on every changed file.

**Phase B — the SPEC amendment and the sweep (gated on S-L2 = A; SPEC-first).**

- **B1 — the SPEC change (a separate commit with justification, per SPEC's own rule).**
  Proposal text, verbatim, for §6.2's sweep paragraph (replacing "The sweep is conservative …
  Orphan directories are removed; the event is logged."):

  > The sweep distinguishes **torn** directories from **unregistered** ones. A cache directory
  > is *torn* iff it contains a `content` and/or `meta.json` file, no row in `artifacts` has
  > `cache_key` equal to the directory name, **and** it does not hold a complete, parseable
  > `meta.json` (with `content` present when `status = 'success'`, and `lineage.json` present
  > when `cache_key_schema_version ≥ 2`). Torn directories are removed; the event is logged.
  > A directory that has no row but holds a complete `meta.json` is *unregistered*, not
  > orphaned: the sweep MUST NOT remove it — it registers it (inserting the `artifacts` and
  > `artifact_lineage` rows from the on-disk files, preserving `produced_at` — the §5.3 /
  > §18.9 reconciliation), or, if registration fails (malformed lineage, schema mismatch),
  > leaves it in place and logs at WARNING with the cache key and the reason. Deletion never
  > follows from index lag: `meta.json` is authoritative and the catalogue is rebuildable
  > (§13.1); the sweep exists for the interrupted-write case only.

  plus a §18.9 rider: "Writers MUST NOT record duplicate lineage inputs (the `artifact_lineage`
  key is `(artifact_cache_key, input_cache_key)`); the writer's seam refuses them, and the
  reconciler / rebuild deduplicate on read **loudly** (WARNING per artefact) so a violation is
  counted, never laundered."; a §16 change-log entry and the version bump. The owner signs the
  text (S-L2) before B2 opens.
- **B2 — the pkm code, TDD.** `cache.sweep_orphans` (`src/pkm/cache.py:459-`) implements the
  amended definition (register-or-leave; remove torn only); `rebuild._read_lineage`
  (`src/pkm/rebuild.py:304-317`) deduplicates on read with a WARNING so **one** malformed
  `lineage.json` can no longer roll back the entire rebuild (`:169-190`); `cache.write_artifact`
  (`:313-320`) refuses duplicate lineage inputs before writing any file. Tests: an unregistered
  file-complete directory survives `extract` and is registered; a torn directory is removed; a
  duplicate-lineage artefact on disk rebuilds with a WARNING and one row; `write_artifact`
  refuses; idempotency double-runs on each. Then a live witness on the owner's root — a
  **dry-run** transcript first (counts of torn vs unregistered), then the real `pkm extract`
  with the two-route count before and after: `pkm.artifact` legacy count monotone.
- **B3 — the standing constraint lifts** on B2's witness (or A5's, for the ask path alone if B
  is not opened): recorded in the report and in `docs/unified-ledger-design.md`'s status
  block as a dated note.

→ **STOP. Report `r01-lineage-sweep.md`.** End of micro-tranche.

## Report protocol

As the tranche briefs: reports in `docs/unification/reports/`, append-only, `STATE / DONE /
DEVIATIONS / REFUSED / QUESTIONS / PROPOSED`; every claim with a transcript; a red suite leads;
British spelling; locators, never values; commits by owner-executed prepared scripts (S12).

## Working style

TDD at every unit boundary (all of these have one); the idempotency double-run for anything
that writes; no new abstractions — every change here is a *narrowing* (unique, refuse, loud,
count) of something that already exists. Any diff that adds a concept should make you
suspicious of yourself.

## Rulings applied — 2026-08-19 (post-review; recorded at the collapse census's placement)

- **Q1 (owner, the backup finding):** being acted on in a separate session — the wrapper's
  source list now carries the KB volume's directories and the pkm live root, the cache exclusion
  is dropped, the timer is enabled; the pkm root's move onto the backed-up volume and the first
  archive after it are the gate for the micro-tranche's two witnesses (r01 B2-live, r00 A5).
- **Q2 (reviewer, numbering):** confirmed — `r04-stocktake.md`, `r00-lineage-writer.md`,
  `r01-lineage-sweep.md` as used; the collapse census placed as `r00-collapse-census.md` (Q-R5).
- **Q3 (reviewer, A0):** moot, closed — landed inside the micro-tranche's Phase A as drafted.
- **Q4 (owner, §3(ii)):** signed — the consumer facts accepted as the answer to the bench's Q1–Q3;
  (α) actual per-ask folds is the P2 re-run's frame (β only if α shows the per-ask cost matters).
  Signed at the census's placement (its addendum §3).
- **Q5 (owner/reviewer, the draft brief):** signed and executed — the pkm lineage micro-tranche
  ran on it (r00 Phase A, r01 Phase B; landed and pushed at `b83dbc0`).
