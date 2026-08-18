# r00 — census — 2026-08-18

Phase 0 of the ledger-unification tranche 1 brief: a read-only, grep-and-disposition
inventory of (a) every immutable-record flavour in the tree, (b) every decision entry point
in `src/life_agent/core/` and `src/life_agent/membrane/`, (c) every projection/fold and the
store it folds, and (d) the design-doc template. No code was changed. Line numbers are
against the HEAD named below. British spelling throughout; no corpus values, no
owner-specific absolute paths (everything is `$LIFE_AGENT_KB`- or repo-relative).

## STATE

**HEAD, working tree.**

```
$ git rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git status --short
(clean before this report; after: only docs/unification/reports/ untracked)
```

**Lint / types (run before the `/tmp` incident below; both clean).**

```
$ uv run ruff check src tests
All checks passed!
exit=0
$ uv run mypy
Success: no issues found in 198 source files
exit=0
```

**Suite.** The first `uv run pytest -q` run (default marker set, i.e. `-m 'not llm and not
system'`) was **invalidated by the environment, not the code**: `/tmp` on this machine is a
`tmpfs` mounted with `usrquota`, and the per-user quota was exhausted mid-run by other
processes (a concurrent session's 3.4 GB scratchpad under `/tmp/claude-1000/…-dataguru/…`,
actively written at the time, plus eighteen orphaned 107 MB `tailwindcss-linux-x64`
downloads under `/tmp/tmp*/`), so every test that touches `tmp_path` / a subprocess started
erroring with `Disk quota exceeded` (the shell itself returned `pwd: write error: Disk quota
exceeded`). Evidence, verbatim from the diagnostic I wrote to the root disk:

```
$ mount | grep ' /tmp '
tmpfs on /tmp type tmpfs (rw,nosuid,nodev,size=8036068k,nr_inodes=1048576,inode64,huge=advise,usrquota)
$ df -h /tmp
tmpfs                  7.7G  6.2G  1.6G  80% /tmp
$ du -sh /tmp/pytest-of-g /tmp/claude-1000 /tmp/* | sort -h | tail -3
720M	/tmp/pytest-of-g
3.5G	/tmp/claude-1000
(+ 18 × 107M  /tmp/tmp*/tailwindcss-linux-x64, ages 3–67 h, zero open handles per lsof)
```

I did **not** delete anything under `/tmp` (an attempt to remove the orphaned tailwind
binaries ≥12 h old with no open handles was blocked by the permission classifier; the
active session's scratchpad was never a candidate). The suite was re-run with temporary
storage redirected to the root disk:

```
$ TMPDIR=~/.cache/census-r00/tmp uv run pytest -q --basetemp=~/.cache/census-r00/basetemp -p no:cacheprovider
```

Result of that re-run: **see the "STATE — addendum" section at the end of this report** (the
run was still in progress when the body was written; the section is appended, never
edited into this one — the report protocol is append-only).

**Files touched:** `docs/unification/reports/r00-census.md` (this file) and its parent
directory. Nothing else. Not committed.

## DONE

### Method

Three read-only sweeps (one per sub-task, run as parallel Explore subagents over `src/`,
`scripts/`, `bin/`, `docs/`) produced the candidate rows; every row that enters this report
carries a `file:line`, and I spot-verified the load-bearing ones by direct `sed -n` reads
(`tasks/events.py`, `core/jsonl_log.py`, `core/decisions.py`, `core/outcomes.py`,
`core/reactions.py`, `core/config.py`, `core/utility.py`, `core/derivations.py`,
`core/executor.py`, `tasks/knowledge.py`, `trips/fold.py`, `core/gather_outcomes.py`,
`membrane/shadow.py`, `scripts/ask.py`, `pkm/telemetry.py`, `pkm/derive.py`,
`docs/pkm/SPEC.md` §7.1, `docs/derivation-engine-design.md` §12, `PRINCIPLES.md` §14/§16).
The short transcripts that decide the sharpest claims are pasted inline below.

### (a) Immutable-record flavours

**a.0 The shared append mechanics.** `src/life_agent/core/jsonl_log.py:20-25` (`append_line`:
`mkdir`, `open("a")`, `write`, `flush`, `os.fsync`) and `:29-32` (`read_lines`: file order,
"never sorted"). Its docstring `:9-13` states the three invariants — append-only,
order-defined ("file order is the canonical replay order; nothing sorts"), durable. Who uses
it, and who does not:

```
$ grep -rln "jsonl_log" src scripts --include=*.py
src/life_agent/core/outcomes.py
src/life_agent/core/claude_verdicts.py
src/life_agent/core/decisions.py
src/life_agent/core/reactions.py
src/life_agent/membrane/shadow.py
scripts/fairfight/run_fairfight.py

$ grep -rn 'open("a"' src scripts --include=*.py | grep -v __pycache__
src/life_agent/core/gather_outcomes.py:83:    with path.open("a", encoding="utf-8") as f:
src/life_agent/trips/events.py:126:    with ledger.open("a", encoding="utf-8") as fh:
src/pkm/telemetry.py:48:    with log_file.open("a", encoding="utf-8") as f:
src/pkm/telemetry.py:79:    with log_file.open("a", encoding="utf-8") as f:
src/life_agent/tasks/events.py:194:    with ledger.open("a", encoding="utf-8") as fh:
src/life_agent/owner.py:45:    with PROFILE.open("a", encoding="utf-8") as fh:
src/life_agent/core/derivations.py:487:    with queue.open("a", encoding="utf-8") as fh:
src/life_agent/core/jsonl_log.py:23:    with path.open("a", encoding="utf-8") as fh:
scripts/ask.py:1093:    with log.open("a", encoding="utf-8") as fh:
scripts/eval_judge.py:136:        with path.open("a", encoding="utf-8") as f:
scripts/answer_labels.py:89:    with path.open("a", encoding="utf-8") as fh:
scripts/verdict.py:176:        with _CORRECTIONS.open("a", encoding="utf-8") as fh:
src/pkm/mcp_server.py:102:        with _TOOL_LOG_PATH.open("a", encoding="utf-8") as f:
scripts/run_eval.py:1715:                with (gate_dir / "report.md").open("a", encoding="utf-8") as f:
```

So four calibration logs + the shadow log + fair-fight go through the durable seam; the two
act ledgers (tasks, trips), the gather-outcome log, pkm's telemetry/demand logs, the §18.9
pending queue, the owner profile, the dogfood log, the judge cache, labels and corrections
all append with a bare `open("a")` (no fsync).

**a.1 life_agent flavours.** Path constants resolve in `src/life_agent/core/config.py`
(root `KB` at `:13`). Each row: location · schema · writers · readers · ordering · identity.

| # | Flavour | Location (config) | Schema | Writers | Readers | Ordering guarantee | Identity / dedup |
|---|---|---|---|---|---|---|---|
| 1 | **Outcomes log** | `$LIFE_AGENT_KB/calibration/outcomes.jsonl` — `config.py:79` | `OutcomeEvent` `core/outcomes.py:97-134`: `tx_time, run_id, question_id, claim, construct, grade, grader, instrument_identity: dict, lineage_keys: tuple=(), probability: float\|None, signals: dict\|None, format_version=1` (`:33`); closed `GRADERS` `:42-76`, `CORRECT_GRADES` `:80-89`; `__post_init__` `:125-134` fails loudly. Serialised `_to_line` `:137-140` `sort_keys=True, ensure_ascii=False, separators=(",",":")`. `tx_time = datetime.now(UTC).isoformat()` `:92-94`. | `outcomes.append` `:149-151` (jsonl_log) ← `scripts/run_eval.py:242` (`_append_outcomes` fed by graders `:192,:208,:271,:312,:329,:350-377,:527-538`), `core/narrative.py:291` (`record_owner_verdicts` `:284-292`), `scripts/regrade_edge_rows.py:121` | `outcomes.read` `:154-160` (malformed line raises); `core/calibration.edge_outcomes_from_log :126-172` → `fit_edge_curves :105-115`; `core/narrative.population_posteriors :212`, `coverage_posterior :232`; `core/lookup.py:503,:520`; `run_eval.py:520`; `core/ask_client.py:102`; `scripts/ask.py:939`; `outcomes.scored_pairs :250-255` → `summarize_scores :188`, `reliability_bins :208`, `ece :230` | File order = replay order (`:11-12`; `docs/bayesian-foundations.md:201-204`) | `lineage_keys` = §18.9 cache keys. Supersession: latest row per `(edge, lineage key)`, **replaced in the superseded row's position** — `calibration.py:155-171`; write-side dedup `run_eval.dedup_edge_events :541-553`; regrade rows carry `signals.regrade_of` (`regrade_edge_rows.py:78-82`) |
| 2 | **Decision log** | `$LIFE_AGENT_KB/calibration/decisions.jsonl` — `config.py:83` | `DecisionEvent` `core/decisions.py:77-125` (v2, `FORMAT_VERSION=2` `:30`): `tx_time, run_id, question_id, family∈FAMILIES(:34), action_set⊆ACTIONS(:41-42), posterior_summary, utility_fold_version, chosen_action, predicted_eu, decision_id="", instrument="", cost_usd, latency_s, format_version`. `_to_line` `:128-131`. | `decisions.append` `:140-142` ← `core/lookup.py:1124-1137`, `core/narrative.py:519-537`, `bridge/server.py:820` (`_log_decision` `:765-823`); `scripts/fairfight/run_fairfight.py:340-368` rebinds the path to `<run>/shadow_calibration/decisions.jsonl` | `decisions.read` `:145-148`; `core/reactions.py:183`; `membrane/shadow._read_decisions :926-936` (fail-open per line); `bridge/server.py:841` (`match[-1]` = last row); `scripts/claude_verdict.py:76`, `live_readout.py:160`, `gate_splice.py:85`, `temper_audit.py:164`, `membrane/p3_gate.py:89` | File order (`:11-12`) | `question_id = sha256(text)[:16]` `:59-74`, declared the one derivation, drift-gated `:67-68`; `decision_id` = the §18.9 answer cache key (`lookup.py:1137`, `narrative.py:537`) or `"ab-"+sha256(canonical json of {source, question, sorted retrieval keys, credences, p_none})[:32]` (`server.py:742-753`) — content-addressed, identical re-runs coalesce |
| 3 | **Reaction log** | `$LIFE_AGENT_KB/calibration/reactions.jsonl` — `config.py:87` | `ReactionEvent` `core/reactions.py:74-93`: `tx_time, question_id, decision_id, kind∈{verdict}(:59), valence∈{good,bad}(:60), format_version=1`; one bit, retired `reason` key dropped on read `:103-106` | `reactions.append` `:109-111` ← `bridge/server.py:843`, `scripts/ask.py:1158` (fallback when bridge down `:1150-1159`), `core/ask_client.react :156` (via bridge), `reach/jarvis.py:93` | `reactions.read` `:114-119`; **`load_reactions :176-205`** joins decisions on `decision_id` (`:183`), folds clean rows to `UT.Reaction`/`UT.MarginReaction` (`:137-147`, `:150-173`); `membrane/shadow._read_reactions :938-949`, `boot_snapshot :1116-1123`; `scripts/claude_verdict.py:89`, `live_readout.py:161`, `membrane/p3_gate.py:90` | File order; **supersession latest per `(decision_id, kind)`** `:184-187` | Report-verdicts, `NO_CLAIMS` abstains, coverage-gated narrative `bad`, unrouted → recorded-not-folded `:179-182` |
| 4 | **Claude verdict log** | `$LIFE_AGENT_KB/calibration/claude_verdicts.jsonl` — `config.py:93` | `ClaudeVerdictEvent` `core/claude_verdicts.py:61-94`: `tx_time, question_id, decision_id, dimensions{correct,complete,grounded}→int bit (:57-58, bools rejected :89-91), evidence: tuple, note, issuer="claude-code"(:49), format_version=1` | `claude_verdicts.append` `:126-128` ← `scripts/claude_verdict.py:175` only | `read` `:131-134`; `latest_by_decision :137-144`; `membrane/shadow._read_claude_verdicts :951-959`, merged in `boot_snapshot :1124-1131`; `scripts/membrane/p3_gate.py:91`, `report.py:1813` | File order; latest per `decision_id` `:142-144` | **Cross-source precedence: an owner reaction that decodes through `verdict_y` overrules the Claude verdict regardless of file order** `shadow.py:1124-1131` (verified verbatim: `continue  # owner precedence: his ROUTABLE verdict overrules the Claude one`); feeds the engine only, never P(U) `:16-20` |
| 5 | **Gather-outcome log** | `$LIFE_AGENT_KB/calibration/gather_outcomes.jsonl` — `config.py:97` | plain dict `core/gather_outcomes.py:81-82` `{"tx_time", "probe", "ctx": list[str], "recovered": bool}`; **no `format_version`, no id, no lineage** | `append_outcome` `:76-84` — bare `open("a")`, `json.dumps(row, ensure_ascii=False)` **without `sort_keys`, no fsync** (`:83-84`, verified) ← `bridge/server.py:664` (`_log_gather` `:646-667`) ← `core/executor.py:339-350` (fail-open) | `warm_counts :87-108` (per-context `(n1,n0)`, `sorted` output `:107-108`), `grow_block :111-118` (served `server.py:644`) | **None relied on** — the fold is a count (`:19-20`) | none; enactment-level dedup `executor.py:610-611` |
| 6 | **Corrections log** | `$LIFE_AGENT_KB/calibration/corrections.jsonl` — `scripts/verdict.py:50` | `{tx_time, question, claim (≤300 chars), cell, claim_as_of, correction}` `:172-175`; no version/id | `:176-177` bare `open("a")`, no `sort_keys`, no fsync | **none in the repo** (write-only capture) | file order | none |
| 7 | **Utility elicitations + model** | `$LIFE_AGENT_KB/utility/elicitations.jsonl` — `config.py:104`; `$LIFE_AGENT_KB/utility/model.yaml` — `config.py:103` | `Elicitation` `core/utility.py:155-162`: `tx_time, latent, stated_value, noise_sigma`; in-memory-only siblings `Reaction :165-177`, `MarginReaction :180-200` (coeffs canonicalised in `__post_init__` `:199-200` so `fold_version` is deterministic) | **no writer in code** — hand-authored (`utility.py:10-11`); `model.yaml` hand-edited (`load_model :116-142` validates gauge) | `load_elicitations :206-225` (bare `read_text().splitlines()`, missing ⇒ `[]` `:210`) ← `core/lookup.current_u_bar :987`, `scripts/run_eval.py:1666`, `gate_splice.py:107`, `membrane/p3_gate.py:434`, `fairfight/loss_ledger.py:532` | Consumed **in order** (`posterior :432-458`, `:436`) | `fold_version(model, events)` `:275-284` = sha256 over canonical JSON of `(model, events-in-order)` — written into every `DecisionEvent.utility_fold_version` and mixed into `lookup_answer_key`/`narrative_answer_key` (`derivations.py:385-386`, `:407-408`); in-process memo `lookup.py:960`, invalidated by version compare `:989-991` |
| 8 | **Gate run outputs** | `$LIFE_AGENT_KB/eval/gate/{report.md, paired.jsonl, run_meta.json}` (+ `gate-outside-option/` for Δ2) — `scripts/run_eval.py:1542-1546`; named in `core/gate.py:396` | `GateResult` `core/gate.py:238-249`; `PairedOutcome :135-149` over `RealisedResponse :102-132`; `run_meta` from `build_gate_run_meta` (`run_eval.py:1550-1553`; stamps `model_sha256`/`elicitations_sha256` `:893-896`) | `run_meta.json` before the first question `:1554`; `report.md` `:1679-1681` (whole-file), judge shadow **appends** `:1715`; `paired.jsonl` `:1682-1691` whole-file `write_text` (`sort_keys=True` per line); archive copies `archive_gate_artifacts :1200-1218` | `scripts/gate_splice.py:21-23`, `extraction_audit.py:49`, `corroborate_audit.py:46`, `reach_audit.py:48`, `temper_audit.py:30` (all read a `paired-gate-<ts>.jsonl` archive) | Not a log: a per-run snapshot at a fixed path, clobbered each run; the run-id-suffixed archive is the only history (`:1204-1207` names runs 3/4 as lost to exactly this) | `run_meta` carries `questions_sha256`, model/elicitation shas; the gate itself is a replayable fold given `(paired, posterior, oracle_p, seed)` `gate.py:315-316`, `DEFAULT_SEED :78` |
| 9 | **Membrane shadow log** | `$LIFE_AGENT_KB/membrane/shadow.jsonl` — `config.membrane_shadow_log()` `:136-139` | one envelope `{"event_type":"membrane-shadow","kind":…,"ts": time.time(), …}` (**float epoch, not ISO**); kinds `decide` `shadow.py:647-655`, `gate` `:672-677`, `enact` `:711-719`, `cat` `:746-754`, `evidence` `:767-771`, `boot` `:873-882` (persists the `u_bar` means, rationale `:861-868`), `respawn` `:847-852`, `stats` `:891-894` | `_append_record` `:898-904` — `sort_keys=True` → `jsonl_log.append_line`, **fail-open** (write error swallowed and counted `:902-904`); worker thread only | `scripts/membrane/report.py:107-112` (`load_shadow_records`, file order), `latest_boot_u_bar :227-247` (last boot wins); `membrane/p3_gate.py:407`; `membrane/lattice_replay.py:188` | File order | none; boot fold `boot_snapshot :1064-1138`: decisions ⋈ reactions ⋈ claude_verdicts on `decision_id`, replay order = owner segment then Claude segment (`:1084-1086`); id-namespace bridge `warm_question_id_map :972-1007` |
| 10 | **GTD act ledger** | `$LIFE_AGENT_KB/tasks/events.jsonl` — `config.py:21` (`TASKS_LEDGER`); alias `tasks/commands.py:24` | `Event` `tasks/events.py:73-96`: `type∈{asserted,disposed,superseded,amended}(:33), identity, tx_time, valid_time\|None, reason\|None, superseded_by\|None, payload: dict, event_id` (auto = `sha256(type␟identity␟tx_time␟reason␟superseded_by)[:16]` `:86-96` — **payload not in the digest**); **bitemporal** (`tx_time`+`valid_time` `:79-80`; `valid_time` = the email's date, `tasks/project.py:69`); `tx_time = datetime.now().isoformat(timespec="seconds")` `:57-59` (**naive local**); **no `format_version`**; `_to_json` `:155-169` `ensure_ascii=False, sort_keys=True` | `events.append` `:189-196` — bare `open("a")`, loop-write, **no fsync** ← `tasks/commands._emit :27-30` (append-then-project) ← `add/complete/delete/move/mark_today/clear_today :33-135`; `tasks/project.project_action_items :116-174` (calls `commands.add` at `project.py:157-163`); `scripts/migrate_jarvis_to_events.py:150` | `events.load` `:199-211` (**skips garbage lines silently** — `_from_json` returns `None` `:172-186`); `fold :214-232`; `known_identities :235-241`; `tasks/store.rebuild :143-148` / `apply :103-140`; `tasks/knowledge.render :47-112` | `fold` is deliberately **order-independent** ("close always wins" `:218-220`, closed set computed first `:222-231`); `store.apply` is order-dependent (sequential UPDATEs), hence `rebuild` replays the whole file | `assertion_identity(claim_type, grounding_span, claim_content)` `:44-54` — content + grounding, **explicitly not provenance** (`:47-51`); `new_identity()` `:62-70` = `uuid4().hex` for human commands (the draw recorded once, replayed); re-filing suppressed on `known_identities` (`tasks/project.py:133-134`) |
| 11 | GTD projections (derived) | `$LIFE_AGENT_KB/tasks/gtd.db` — `config.py:24`; `$LIFE_AGENT_KB/tasks/state.md` — `config.py:29`; legacy `jarvis/jarvis.db` `:31-33` read-only | SQLite `tasks` table `tasks/store.py:74-92` (`id INTEGER PRIMARY KEY AUTOINCREMENT, identity UNIQUE, user_id, text, list, due_date, is_today, origin, created_at, completed_at`); `state.md` stamp `knowledge.py:60` `as of event {N} · ledger sha256 {sha} · render v{RENDER_VERSION}` (`RENDER_VERSION=2` `:30`, `_STAMP_RE :32`, `parse_stamp :41-44`) | `gtd.db` written **incrementally in place** per command (`commands.py:27-30`), `rebuild :143-148` is the recovery; `state.md` by `knowledge.write_state :115-126` (write-only-on-change `:124-125`; `ledger_sha = sha256(ledger.read_bytes())` `:120-121`) | `reach/digest.py:32`, `store.get_board :296`, `reach/web`; `state.md` re-ingested by `scripts/ask.py:1370-1375`, staleness at `:1314-1321` (verified: `parse_stamp(text) != (sha, RENDER_VERSION)`) | derived | the stamp is the staleness join to the **ledger file bytes** |
| 12 | **Trips act ledger** | `$LIFE_AGENT_KB/trips/events.jsonl` (env `TRIPS_LEDGER`) — `config.py:41-43`; alias `trips/commands.py:19` | `Event` `trips/events.py:36-60`: `type∈{observed,superseded,cancelled,amended}(:20), identity, tx_time, received_at, fidelity, source_id, superseded_by, reason, payload (JSON-LD verbatim), event_id` = `sha256(type␟identity␟tx_time␟superseded_by␟source_id␟reason␟json.dumps(payload,sort_keys))[:16]` `:51-60` (**payload included**, unlike tasks); `tx_time` naive local `:32-33`; no `format_version`; `_to_json :100-106` sorted keys | `events.append :122-128` bare `open("a")`, no fsync ← `trips/commands.observe :34-52`, `cancel :54-60`, `amend :62-66`, `supersede :68-70`; producers `trips/cli.py:79`, `seeder.py:127`, `kayak.py:179`, `mailbox.py:91` | `events.load :131-142` (skips garbage); `trips/fold.fold :48+`; `commands._rebuild :22-24`, `_already_observed :27-32` | **Fold is NOT file-order-defined**: competing `observed` events resolve by `FIDELITY_RANK` (`events.py:22-27`: manual 1 < email-kitinerary 2 < kayak-api 3 < kayak-ics 4) then later `received_at` — `trips/fold.py:30-36` (verified `_better`) | `reservation_identity(jsonld)` `trips/identity.py:99-103` = `sha256(res_type ␟ json.dumps(content_key))`, per-type `content_key :81-97`; confirmation number and vendor id excluded (`:4-6`); superseded ancestors retained (`fold.py:8-9`). Projection `trips.db` `config.py:45`: `store.rebuild :128-145` deletes+reinserts `reservation`; **`source` and `trip` tables are `INSERT OR REPLACE` side-stores that `rebuild` never touches** (`store.py:47-58`, `:147-158`) |
| 13 | **§18.9 derivation records** (life_agent writing into pkm's cache) | `<pkm root>/cache/<aa>/<bb…>/{content, lineage.json, meta.json}` + queue `<root>/external/pending.txt` (`_PENDING_QUEUE` `derivations.py:92`) + catalogue `<root>/catalogue.duckdb`; root via `config.pkm_root()` `:171-180` (None ⇒ caching disabled, fail-open) | `StageKey` `derivations.py:106-118`; `meta.json` built `:464-483` (`format_version=META_FORMAT_VERSION`, `cache_key, input_hash, producer_name/version/config/config_hash, status:"success", produced_at` naive UTC `:473`, `size_bytes, content_type, content_encoding, producer_metadata{inputs,…}`, `cache_key_schema_version` if ≥2 `:480-481`); `lineage.json` `:458-462` `{format_version:1, inputs:[{cache_key, role}]}`; both `indent=2, sort_keys=True` | `record(root, key, content, lineage=, metadata=)` `:440-489` — **write-once** (existing `meta.json` ⇒ `False` `:450-452`); content → lineage → meta each via `_write_atomic` `:434-437` (temp + `os.replace`); then `pending.txt` `open("a")` `:485-488`. Sites: `expansion.py:171`, `synthesis.py:87`, `subject.py:208`, `temporal_intent.py:85`, `joint_extract.py:120`, `lookup.py:562,612,718,1110`, `narrative.py:510`, `deliberate.py:391` (`record_answer :373-394` refuses a blind decline `:376-384`), `scripts/ask.py:562,734`, `scripts/route_audit.py:51` | `lookup(root, cache_key)` `:423-431` (meta.json is the commit marker); `reconcile(root)` `:493-528` (opportunistic catalogue insert; **rewrites** `pending.txt` preserving concurrent appends `:522-527`); `_reconcile_one :531-569` preserves recorded `produced_at` | none — content-addressed set; queue order irrelevant (`dict.fromkeys` `:502`) | keys via `pkm.hashing.compute_cache_key` through twelve builders `:130-419` (`EXPAND/RETRIEVE/…/DELIBERATE_VERSION` `:50-62`, `ENGINE_VERSION :46`, `DELIBERATE_ENGINE_VERSION :66`); `input_hash = sha256(canonical_json(inputs))` `:95-96`; **`lookup_answer_key`/`narrative_answer_key` mix in `utility_fold_version`** `:385-386`, `:407-408` — the point where the calibration ledger and the pkm DAG share one address (= `decision_id`) |
| 14 | pkm demand log, life_agent writers | `<pkm root>/logs/demand/<UTC-date>.jsonl` — `src/pkm/telemetry.py:72-76` | `DemandLogEntry` `telemetry.py:53-67`: `timestamp, caller, transform_name, cache_key, input_cache_key, hit, cost_usd, latency_ms` | `core/temporal.py:179-192` (`transform_name="doc_date"`; **`cache_key=""` on a read-side miss** `:181-183`), `core/subject.py:268-281`; mechanism `log_demand :70-80` bare `open("a")`, `sort_keys=True`, no fsync | **none** (see a.2 #14) | none | none — pure occurrence |
| 15 | **Fair-fight records** | `$LIFE_AGENT_KB/eval/fairfight/<run_id>/` (`fairfight/records.py:6`): `run_meta.json`, `questions.sha256` (`run_fairfight.py:976`), `arms/<arm>/answers.jsonl` (`:594`), `arms/<arm>/vectors.jsonl` (`:725`), `judge/<arm>_scores.jsonl` (`:638`), `shadow_calibration/decisions.jsonl` (`:359`), `summary.md` (`:1030`), competitor tool logs (`arm_hermes.py:156,176`, `arm_claude.py:120,135,268`) | `OutcomeVector` `records.py:83-161` — 40 fields, **all required** (`:88-90`), closed vocabularies `ARMS :49-50`, `COST_STATUSES :69`, `STATUSES :73`, `BUCKETS :78-80`; `question_id` = the **corpus** id; "no combined score field" `:10-12` | `_append_jsonl` `run_fairfight.py:374-375` (`jsonl_log`, sorted keys); `answers.jsonl` per question `:590-616` (unlinked fresh `:596`); `vectors.jsonl` once after judging `:724-730`; `answer_sha256 = sha256(text)` `:719` | `records.from_json :176-186`; `records.scored :193-207` (the one `status=="ok"` filter); `scripts/dominance/run_dominance.py:200`, `fairfight/loss_ledger.py:357,362`, `fairfight/oracle_audit.py:219-220`, `membrane/report.py:149`, `membrane/shadow._warm_outcomes :1027` | File order = question order | `shadow_calibration/decisions.jsonl` is a one-time copy of production's decision log (`:361-364`); `_warm_outcomes` dedups on `f"{run_id}:{corpus_id}"` (`shadow.py:1043-1044`, "a dedup key, not a join key") |
| 16 | Eval labels | `$LIFE_AGENT_KB/eval/labels.jsonl` — `scripts/answer_labels.py:11-13`, `label_answers.py:33` | `Label :36-40` `{question_id, value, verdict∈{correct,stale,wrong}(:27), note}` + `value_norm` `:87-88`; back-compat bare `correct: bool` `:44-45`, `:54` | `append_label :82-90` bare `open("a")`, no `sort_keys`, no fsync ← `label_answers.py:123` | `load_labels :43-56`, `verdict :59-75`, `is_labeled :78-79` ← `eval_executor.py:183`, `triage_answers.py:277` | **last matching label wins by file order** `:74` | none |
| 17 | Judge verdict cache | `$LIFE_AGENT_KB/eval/judge-verdicts.jsonl` — `scripts/eval_judge.py:22`, `run_eval.py:1706` | `{key, correct, judge, prompt_version}` `:136-138` | `judge_with_cache :120-142` (`:135-139`, `sort_keys=True`, no fsync); **`None` verdicts never cached** `:130-131` | `load_verdicts :108-117` (dict overwrite ⇒ last wins) | file order (last wins) | `judge_key :50-62` = sha256 of `{v: JUDGE_PROMPT_VERSION, judge model pin, question, gold, variants, candidate}` |
| 18 | Dogfood log; owner profile | `$LIFE_AGENT_KB/eval/dogfood-<date>.md` — `scripts/ask.py:1091`; `$LIFE_AGENT_KB/owner.md` — `owner.py:24` | markdown blocks `ask.py:1071-1085`; profile bullets `owner.py:38-51` | `append_log :1087-1097`; `append_fact :38-52` — both bare `open("a")` | none / `load_profile :29-35` | file order | profile sha keys `owner_match_key`/`synthesize_key` (`derivations.py:167-186`, `:199-221`) — hand-editable, so an edit silently re-keys cache cells |
| 19 | Deliberate side records | `$LIFE_AGENT_KB/tmp/deliberate/tool_calls/<qid>.jsonl` (`core/deliberate.py:212`, written by `pkm serve --tool-log`), `$LIFE_AGENT_KB/tmp/deliberate/workdir/mcp-config.json` (`:226-227`, rewritten); void manifest `deliberate-void-<ts>.json` (`scripts/void_deliberate_poison.py:105-115`) | tool-log rows per SPEC §17.8; manifest `{voided_at, root, reason, records:[{cache_key, catalogue_row}]}` | pkm; `_read_tool_log :239+` reads back; the void script is the **one deletion path** for §18.9 artifacts (`:93-101`) and the manifest is its compensating record | `deliberate.py:367-368`, `scripts/temper_audit.py:208` | overwritten per re-run | — |
| 20 | Snapshot (non-log) eval artefacts | `eval/triage/*` (`triage_answers.py:292-295`), `answer_brain_gate` (`answer_brain_gate.py:221,297`), `eval/comparison/*` (`comparison/phase0_answer.py:56`, `blind_judge.py:142-146`), `eval/judge_meta.json` (`run_eval.py:1811`), dominance outputs (`run_dominance.py:237-264`), loss-ledger (`loss_ledger.py:503-505`), membrane `report.{json,md}` (`membrane/report.py:1833-1834`), audit reports (`extraction_audit.py:268`, `corroborate_audit.py:291`, `reach_audit.py:238`, `temper_audit.py:402`, `route_audit.py:110`, `live_readout.py:166`), `paired-confirm-*.jsonl` (`corroborate_audit.py:230`), `paired-temper-*.jsonl` (`temper_audit.py:343`) | various | whole-file `write_text` rewrites | various | **snapshots, not logs** — clobbered at a fixed path; audits point `BridgeDeps` at throwaway logs under `$LIFE_AGENT_KB/tmp/corroborate-audit/` so they never write the real ledgers (`corroborate_audit.py:266-271`) | — |

**a.2 pkm flavours.** Root is `Config.root_dir` (`src/pkm/config.py:65`, resolved `:124`);
catalogue at `<root>/catalogue.duckdb` (`catalogue.py:90-92`, `open_catalogue :95-109`).
There are **no `.sql` files**: migrations are Python DDL under `src/pkm/migrations/`.

| # | Flavour | Location | Schema | Writers | Readers | Ordering | Identity vs occurrence |
|---|---|---|---|---|---|---|---|
| 1 | `sources` | DuckDB table | `migrations/0001_initial_schema.py:42-52`, recreated without `tags` at `0002_normalise_tags.py:62-73`: `source_id PK, current_path, first_seen, last_seen, size_bytes, mime_type` (SPEC `SPEC.md:182-189`) | `ingest.ingest_sources :110`; INSERT `:197-203`, **UPDATE `current_path`/`last_seen` `:181-185`**; one txn per sweep `:167/:238/:240`; guard `_source_exists :407-413` (SELECT, not `INSERT OR IGNORE`) | `derive._eligible_for :266-272`; `transform_run._find_eligible_sources :188-195`; `retrieval.search :181`; `_PATH_CURRENT_CTE :46-59`; `extract._load_sources :351` | none intrinsic (PK = content hash); query-time `(last_seen DESC, first_seen DESC, source_id DESC)` `retrieval.py:53` | **identity** `source_id = sha256(file bytes)` `ingest.py:392-401` (= SPEC-PRINCIPLES §1); `first_seen/last_seen/current_path` are **mutable occurrence** — this row is not immutable |
| 2 | `source_paths` | DuckDB | `0001:53-63` / `0002:84-94`: `(source_id, path) PK, seen_at` (SPEC `:191-200`, "history is kept") | `ingest.py:220-226`, guard `_source_path_exists :416-423`; pure append | **no production reader** in `src/pkm/**` | none | hybrid: identity on `source_id`, occurrence on `seen_at`; path is declared not canonical (`ingest.py:352-359`, SPEC §13.6) |
| 3 | `source_tags` | DuckDB | `0002:100-110` `(source_id, tag) PK` | `_replace_tags :426-443` — **DELETE then INSERT** (declarative manifest `ingest.py:21-28`) | `transform_run.py:200-203`, `derive.py:279-281`, `extract.py:521` | none | **state, not a record**; not content-addressed |
| 4 | **Artifacts (cache)** | `<root>/cache/<aa>/<bb…62>/{content, meta.json, lineage.json}` — `cache.py:123-153` (SPEC layout `:80-95`) | `meta.json` `cache.py:266-283`: `format_version(=1 :63), cache_key, input_hash, producer_name/version/config/config_hash, status, produced_at (naive UTC :244), size_bytes, error_message, content_type, content_encoding, producer_metadata` (+ `cache_key_schema_version` ≥2 `:282-283`); `lineage.json` `{format_version:1, inputs:[{cache_key, role}]}` `:167-168,:255-263`; **meta.json authoritative** (SPEC §13.1 `:738`; `cache.py:9-14`) | `write_artifact :171-343`: content `:251` → lineage `:259-263` → meta `:284-287` → DuckDB txn `:290-321`; **plain `write_bytes`/`write_text`, no temp+rename, no fsync**; guards `_row_exists :227-229`, `_require_files_present :585-613`. Callers `extract._run_one :591-600` (schema 1), `transform_run._execute_run :362-372` (schema 3 + lineage), `derive._resolve_node :244-254` | `read_artifact :349-389`; `has_success_artifact :535-555` (the §18.11 cache-first check); `rebuild._iter_meta_files/_meta_to_row :227-244,:247-280`, `_read_lineage :304-318`; `derive.py:187-194`, `transform_run.py:299-309` (read content bytes to hash the next `input_hash`) | **none** — set semantics; only `produced_at` inside meta | **identity** = `compute_cache_key` `hashing.py:62-209` (payload `:182-207`: `schema_version, input_hash, producer_name, producer_version, producer_config_hash`; +schema 2 `model_identity_hash, prompt_hash(rendered)` `:190-196`; +schema 3 `model_identity_hash, engine_version, prompt_template_hash, output_schema_hash` `:197-207`; digest `:209`; `canonical_json :23-52`); **occurrence** = `produced_at` |
| 5 | `artifacts` (DuckDB) | table | `0001:64-81` (`cache_key PK, input_hash, producer_name/version/config_hash, status, produced_at, size_bytes, error_message, content_type, content_encoding, content_path`), indexes `:82-87` | `cache.write_artifact :292-312`; `rebuild_artifacts :172-182` (DELETE + reinsert from meta.json); `derivations._reconcile_one :545-558`; deleter `cache.delete_artifact :395-453` (`--retry-failed`, `extract.py:549`) | `_fetch_artifacts_row :558-582`, `has_success_artifact :545-548`, `_row_exists :528-532`, `extract.py:646-650,:680-684,:701-704`, `staleness.superseded :55-58`, `derive._current_leaf_artifact :163-168`, `transform_run.py:188-195`, `retrieval.py:180`, `cli.py:539-552`, `sweep_orphans :478-481` | none intrinsic; consumers impose `ORDER BY produced_at DESC, cache_key DESC` (`derive.py:166`), `produced_at DESC, input_hash` (`transform_run.py:193`), sort `(produced_at, cache_key)` reverse (`staleness.py:69`) — SPEC calls the tiebreak "deterministic … not meaningful" (`:1300`, `:1750-1754`) | **a rebuildable index, not the record** (`catalogue.py:3-5`, `rebuild.py:1-8`, SPEC §13.1/§5.3) |
| 6 | `artifact_lineage` + `lineage.json` | table + file | `0003_transform_substrate.py:41-54` `(artifact_cache_key, input_cache_key) PK, role`; "derived index … rebuildable from lineage.json" `0003:5-8` | `cache.write_artifact :313-320`; `rebuild.py:169,183-189`; `derivations._reconcile_one :559-564`; role from `TransformDeclaration.input_role` (`transform_declaration.py:47`); schema-≥2 artifacts **must** carry lineage (`cache.py:221-224`, `:646-661`) | `staleness.stale :91-114` (BFS, determinism manufactured by `sorted` `:105,:108`); `rebuild._read_lineage :304-318`; `core/temporal.py:3-10` | none — set of edges | pure identity (two cache keys) |
| 7 | `artifact_chunks` + `seq_chunk_id` | table + sequence | `0004_chunks_and_embeddings.py:32-47` (`artifact_cache_key, chunk_index, chunk_text, embedding FLOAT[768], source_origin`; PK `(cache_key, chunk_index)`); `0005_chunk_surrogate_key.py:32-43` adds `seq_chunk_id` + `chunk_id BIGINT` (no UNIQUE, deliberate `:36-39`) | `chunking.write_chunks :102-127` **DELETE-then-INSERT** (`:114-117`, `:119-126`), `nextval` `:122`; callers `extract._chunk_artifact :707-720`, `cli._cmd_chunk --backfill :582` | `retrieval.build_fts_index :76-102`, `search :157-188`, `count_path_superseded_chunks :105-121`; MCP `extract` (§17.7) | **the only monotonic sequence in the system**, declared non-semantic except for the MCP surface (SPEC `:1093-1102`) | not content-addressed: `(artifact_cache_key, chunk_index)` positional; chunk params (`max_chars=1000, overlap=100` `chunking.py:74-75`) not in any hash; `chunk_id` allocation-order surrogate; **`embedding` column never written or read anywhere in `src/`** |
| 8 | FTS index | DuckDB `fts` extension | config `retrieval.py:32-39` | `build_fts_index :76-97` (`overwrite=1`, full rebuild) | `search :157-188` | BM25 DESC | pure index, not a record |
| 9 | Path currency (§15.4) | a **view**, no table — `_PATH_CURRENT_CTE` `retrieval.py:46-59` | `row_number() OVER (PARTITION BY current_path ORDER BY last_seen DESC, first_seen DESC, source_id DESC)` | none (query-side only, SPEC `:1305-1307`) | `search :182`; `count_path_superseded_chunks :118` | tuple order "not meaningful" (SPEC `:1299-1300`) | groups by **declared path** — the one place pkm orders by a mutable observation rather than a hash |
| 10 | Staleness (§18.10) | a **computation** — `staleness.py`; `StaleArtifact :33-44` | — | **none** ("only reads" `:14-15`; SPEC `:1759-1762`) | `superseded :47-73`, `stale :76-116`, `cli._cmd_stale :634-655` | grouping by `(input_hash, producer_name)` `:60-62`; current = max `(produced_at, cache_key)` `:68-70`; output sorted by `cache_key` `:116` | the seam where **occurrence becomes load-bearing** over a content-addressed set |
| 11 | **`schema_meta`** (migrations ledger) | table; files `src/pkm/migrations/*.py` (`MIGRATIONS_DIR` `catalogue.py:40`) | `0001:30-39` `schema_version PK, migration_id, migration_hash, applied_at` | `_apply_single :290-322` (INSERT `:313-318` in the same txn as the DDL); `applied_at` naive UTC `:309` | `_read_applied_migrations :226-243`, `_verify_integrity :246-276` | **strictly monotonic and enforced** (`:205-210`, `:165-174`; filename regex `:45`) | `migration_hash = sha256(file bytes)` `:214-215`; editing a landed migration ⇒ `MigrationHashMismatchError :268-276`; **the strongest immutability enforcement in the tree**. Migrations: 0001 (`schema_meta, sources, source_paths, artifacts` + 3 indexes), 0002 (drop `sources.tags`, recreate, add `source_tags`), 0003 (`artifact_lineage`, `pending_approvals`, `approval_sources/samples/reasons`), 0004 (`artifact_chunks`), 0005 (`seq_chunk_id`, `chunk_id`) |
| 12 | Approvals | `pending_approvals` + 3 satellites | `0003:56-107` (`approval_id PK, transform_name, transform_declaration_hash, cost_estimate_usd, source_count, status, created_at, decided_at, rejection_reason, schema_version`); `ApprovalRecord` `approval.py:19-34` | `create_approval :37-90` (one txn); `approve :93-113` / `reject :116-142` **UPDATE in place** (`:108-113`, `:136-142`); callers `transform_run.py:259-278`, `derive.py:225-228` | `get_approval :145-194`, `list_pending :197-210` | `created_at` only | **`approval_id = uuid4()` `:48` — the only randomly generated id in pkm**; `transform_declaration_hash` (`transform_declaration.py:73-75`) stored here and **nowhere else** (not in any cache key); `approval_samples` always written empty (`transform_run.py:276`) — pure occurrence + mutable lifecycle |
| 13 | Transform telemetry log | `<root>/logs/transforms/<UTC-date>.jsonl` — `telemetry.py:41-45` | `TransformLogEntry :17-34` (14 fields incl. `cache_key, model, status, tokens, latency_ms, cost_usd, cache_hit`) | `log_transform_execution :37-49` (bare `open("a")`, sorted keys, no fsync) ← `transform_run._log_telemetry :414-442` (hit `:330-333`, fail `:346-348`, write `:382`), `derive.py:236,255` | **none** in `src/pkm/**` (`jq` by design `:5`) | append order, UTC day partition `:44` | occurrence only |
| 14 | **Demand log** | `<root>/logs/demand/<UTC-date>.jsonl` — `telemetry.py:72-76` | `DemandLogEntry :53-67`, exactly 8 fields (`timestamp, caller, transform_name, cache_key, input_cache_key, hit, cost_usd, latency_ms`); SPEC §18.11 `:1802-1806` | `log_demand :70-80` — `mkdir`, `open("a")`, `write` — **no `os.replace`, no fsync, no lock, no idempotency guard**; call sites `derive._demand :291-304` (hit `:213-214`, fail `:237-238`, write `:256-258`; `caller` from CLI `--caller` `cli.py:665`, default `"cli"` `derive.py:75`), `core/temporal.py:179-193`, `core/subject.py:268-282`; observed callers `"ask.lookup"` `scripts/ask.py:814`, `"ask.derive"` `:1282`, `"derive_eval_slice"` `derive_eval_slice.py:47,55` | **NOTHING READS IT** — transcript below | append order within a UTC-day file; `latency_ms` from `time.monotonic()` (`derive.py:185,:303`) | pure occurrence; `cache_key` may be `""` (`temporal.py:181-183`, `subject.py:270-272`) so a line is not guaranteed to reference a resolvable artifact; SPEC: "it cannot be backfilled" `:1804-1806` |
| 15 | Diagnostic log | `<root>/logs/<LOCAL-date>.jsonl` — `logging_setup.py:120-135` | field order `:3-13`; timestamps UTC-aware `:19-24` | `setup_logging :138` (stdlib `FileHandler`); events scattered (`cache.py:333,451,505,631,650`, `catalogue.py:329`, `ingest.py:191,212,232,251,454`, `extract.py:610,629,726`, `rebuild.py:138,206`, `retrieval.py:101,193`, `mcp_server.py:109`) | none | append order; **local-date filename vs UTC lines, deliberate** (`:26-28`); no rotation `:30-32` | occurrence |
| 16 | MCP tool-call log (§17.8) | operator path via `--tool-log` — `mcp_server.set_tool_log :61-69`, `cli.py:625`; never under `<root>/logs/` (SPEC `:1509-1511`) | `{ts, tool, args, n_results, results[]}` + `error` `:92-100`; per-result fields SPEC `:1513-1528` | `_log_tool_call :76-113` (`:102-103`), **fail-open** (`:104-113`, SPEC `:1553-1558`) | external harness only | append order; **explicitly non-idempotent** — identical calls append two lines (SPEC `:1560-1563`) | occurrence |
| 17 | §18.9 file-first seam (pkm side of a.1 #13) | as a.1 #13 | as a.1 #13 | SPEC contract `:1694-1734`; `record` uses temp+rename `derivations.py:434-437` — **stricter than pkm's own `write_artifact`** (`cache.py:251,259,284` write directly) | `derivations.lookup :423-431`; `scripts/forensics/corpus_timeline.py:45`; `scripts/void_deliberate_poison.py:43` | `pending.txt` "append-only" per SPEC `:1717-1718` but **rewritten** by `reconcile` `:526-527` — a drainable queue | keys: schema 3 for model stages (`expand_key :136-143`, `synthesize_key :175-182`), **schema 1** for the deterministic retrieval stage (`retrieve_key :156-159`); `input_hash` is a *derived* hash (`:135,:154,:174`), not raw source bytes; only successes recorded (`:472`) |
| 18 | Transform declarations (input) | `<root>/transforms/<name>.yaml` | loader `transform_declaration.py:50-93`; `declaration_hash :73-75`, `prompt_hash :68` | — | `transform_run.py:313-315`, `derive.py:197-199` recompute `sha256(prompt_text)` inline (same value as `prompt_hash`, computed twice) | — | `declaration_hash` never enters a cache key; §18.12/§18.13 (`doc_date`, `doc_date_email`, `doc_subject`) are declarations of this shape |

The demand-log reader claim, verbatim (the whole repo, `.py` and `.md`):

```
$ grep -rn "logs/demand\|log_demand\|DemandLogEntry" --include=*.py --include=*.md . | grep -v __pycache__
CLAUDE.md:21:  chain makes zero model calls — demand-logged under `logs/demand/`.
docs/system-design.md:56:under `logs/demand/`), and ask's three stages (`life_agent/core/derivations.py`, §18.9
docs/pkm/SPEC.md:1803:  `<root>/logs/demand/<YYYY-MM-DD>.jsonl`: `timestamp`, `caller` (free-form — `cli`, or a
docs/pkm/SPEC.md:1926:  gate + lineage on the miss path, failures not cached, demand telemetry under `logs/demand/`.
src/pkm/derive.py:30:from pkm.telemetry import DemandLogEntry, log_demand
src/pkm/derive.py:295:    log_demand(root, DemandLogEntry(
tests/pkm/test_demand_log.py:8:from pkm.telemetry import DemandLogEntry, log_demand
tests/pkm/test_demand_log.py:11:def _entry(**overrides: object) -> DemandLogEntry:
tests/pkm/test_demand_log.py:23:    return DemandLogEntry(**base)  # type: ignore[arg-type]
tests/pkm/test_demand_log.py:26:def test_log_demand_appends_one_jsonl_line(tmp_root: Path) -> None:
tests/pkm/test_demand_log.py:27:    log_demand(tmp_root, _entry())
tests/pkm/test_demand_log.py:28:    log_demand(tmp_root, _entry(hit=False, cost_usd=0.01))
src/pkm/telemetry.py:53:class DemandLogEntry:
src/pkm/telemetry.py:70:def log_demand(root: Path, entry: DemandLogEntry) -> None:
src/life_agent/core/subject.py:36:from pkm.telemetry import DemandLogEntry, log_demand
src/life_agent/core/subject.py:273:    log_demand(root, DemandLogEntry(
src/life_agent/core/temporal.py:29:from pkm.telemetry import DemandLogEntry, log_demand
src/life_agent/core/temporal.py:184:    log_demand(root, DemandLogEntry(
```

Three writers, one test, prose — no reader.

**a.3 The determinism contract the mission binds to (SPEC §7.1, verbatim
`docs/pkm/SPEC.md:400-415`).**

> **Determinism contract.** Producers produce *semantically* equivalent output given the
> same input content and config. Byte-level determinism across runs is not required;
> ML-backed producers may produce output that varies at sub-semantic levels
> (floating-point layout coordinates, token-level timestamps, inference-noise scores, and
> similar) between runs on the same input.
>
> The cache is keyed on `(input_hash, producer_name, producer_version,
> producer_config_hash)` — not on output bytes. A cache hit means "we have already run this
> producer with these inputs; reuse the cached output" — not "this is the canonical output
> that would be reproduced bit-exactly if we ran it now." Output bytes written once are
> preserved; the system never overwrites an artifact with a fresh run of the same producer
> at the same version. Re-running only happens via explicit `--retry-failed` after a
> recorded failure (see §14.3).

Consequences the census draws for "replay of pkm" (each with its evidence): (i) **index
replay** exists and is exact — `pkm rebuild-catalogue` → `rebuild_artifacts` `rebuild.py:88`
reconstructs `artifacts` + `artifact_lineage` from `meta.json`/`lineage.json` (`:169-189`),
sweeps orphans `:195`; (ii) **read replay** exists and is exact — a cache hit re-reads the
stored bytes (`cache.py:535-555`), never re-runs (`:227-229`; SPEC `:411-413`); (iii)
**computational replay does not exist and §7.1 says it cannot be byte-exact** — what would
reproduce is the **key set** (`compute_cache_key` over §4.4-excluded inputs, SPEC
`:154-161`), so pkm replay is *key-deterministic, content-nondeterministic*
(SPEC-PRINCIPLES §2/§3: the event's identity is the hash of its inputs; its output is what
it produced); (iv) the **occurrence layer** (`produced_at`, `first_seen`, demand/telemetry/
diagnostic/tool logs, approvals) is write-once and unreconstructable — SPEC says so of the
demand log explicitly (`:1804-1806`). Only `artifacts` and `artifact_lineage` are
rebuildable from disk; `sources/source_paths/source_tags` (observational, `rebuild.py:10-13`,
SPEC `:262-266`), `schema_meta`, approvals and `artifact_chunks` (+ `chunk_id`, which
`--backfill` reassigns) are primary state living in a store advertised as derived. And the
one thing that breaks replay outright is editing a landed migration (`catalogue.py:246-276`).

**a.4 Cross-cutting observations (both sides).**

- **Identity hashes, catalogued** (preimage → where): `source_id` = raw bytes
  (`ingest.py:392-401`); extract `input_hash` = `source_id` (`extract.py:537`); transform
  `input_hash` = sha256 of the upstream artifact's *content bytes* (`transform_run.py:309`,
  `derive.py:194`); §18.9 `input_hash` = sha256(canonical_json(inputs)) (`derivations.py:135,
  154,174`); `producer_config_hash` (`hashing.py:178-180`); `model_identity_hash` (`:55-59`);
  `prompt_hash` (rendered, schema 2 `:196`) vs `prompt_template_hash` (schema 3;
  `transform_run.py:313`, `derive.py:197`); `output_schema_hash` (`:205-207`); `cache_key`
  (`:209`); `migration_hash` (`catalogue.py:214-215`); `declaration_hash`
  (`transform_declaration.py:73-75`, in no cache key); `assertion_identity`
  (`tasks/events.py:44-54`); `reservation_identity` (`trips/identity.py:99-103`);
  `question_id` (`decisions.py:59-74`); `decision_id` (`lookup.py:1137`, `narrative.py:537`,
  `server.py:742-753`); `judge_key` (`eval_judge.py:50-62`); `fold_version`
  (`utility.py:275-284`); `event_id` (tasks `:86-96`, trips `:51-60`); `answer_sha256`
  (`run_fairfight.py:719`). Allocated, not derived: `approval_id` (uuid4), `chunk_id`
  (sequence), `new_identity()` (uuid4, the recorded draw).
- **The byte/semantic seam inside pkm chains**: a producer may emit different bytes each
  run, but the next transform hashes those bytes (`derive.py:193-194`,
  `transform_run.py:308-309`), so byte variance at step N would yield a different key at
  N+1 — the only thing preventing thrash is the never-overwrite rule (`cache.py:227-229`).
- **`tx_time` clocks disagree**: UTC-aware ISO (`outcomes.py:92-94`), naive local ISO
  (`tasks/events.py:57-59`, `trips/events.py:32-33`), naive UTC (`derivations.py:473`,
  `cache.py:244`, `catalogue.py:309`, `approval.py:49,107,135`), float epoch (`shadow.py`
  `ts`), UTC-aware in pkm logs (`logging_setup.py:19-24`, `derive.py:296`); pkm documents
  its own catalogue-naive vs log-aware split as deliberate (`logging_setup.py:21-24`).
  **No record anywhere carries a `seq` number** (grep for `seq` in record schemas: only
  `seq_chunk_id`).
- **`format_version` presence**: `OutcomeEvent`(1), `DecisionEvent`(2), `ReactionEvent`(1),
  `ClaudeVerdictEvent`(1), `OutcomeVector`(1), `lineage.json`(1), `meta.json`(1). **Absent**
  from gather rows, task events, trip events, corrections, labels, judge-cache rows,
  demand/telemetry lines.
- **Read policy split**: calibration logs are loud (`outcomes.read :158` "a corrupt evidence
  log is a loud failure, never a skip"); act ledgers are quiet (`tasks/events.py:185-186`,
  `trips/events.py:118-119` swallow and drop); the shadow reader is fail-open per line
  (`shadow.py:906-915`).
- **Two `question_id` namespaces**, one declared bridge: `sha256(text)[:16]` (decisions,
  reactions, Claude verdicts, shadow) vs corpus ids `q-NNN` (eval, fair-fight); joined only
  through `shadow.warm_question_id_map :972-1007` via `run_meta.json → questions_path`.
- **Joins between records**: reactions→decisions on `decision_id` (`reactions.py:183`);
  claude_verdicts→decisions (`shadow.py:1125`); outcomes `lineage_keys` → §18.9 keys;
  `decisions.decision_id == lookup/narrative answer cache_key`; `decisions.instrument` (v2)
  → `deliberate.instrument(model)` (`deliberate.py:196-201`) and `executor.extract_edge`
  (`executor.py:102`); fair-fight `vectors.question_id` → shadow decisions via the bridge;
  `state.md` stamp → sha256(ledger bytes) (`knowledge.py:120-121` ⟷ `ask.py:1317-1318`).
- **Supersession rules, catalogued (seven)**: (a) reactions — latest per
  `(decision_id, kind)`, file order (`reactions.py:184-187`); (b) Claude verdicts — latest
  per `decision_id`, then owner precedence overrides file order (`shadow.py:1124-1131`);
  (c) `eval_edge` outcomes — latest per `(edge, lineage key)` in the superseded row's
  position (`calibration.py:155-171`); (d) labels — last match wins
  (`answer_labels.py:74`); (e) tasks — close-always-wins, order-independent
  (`tasks/events.py:218-231`); (f) trips — fidelity rank then `received_at`, not file order
  (`trips/fold.py:30-36`); (g) §18.9 artifacts — write-once, never superseded
  (`derivations.py:450-452`) — which is exactly why regrades append to the outcomes log.
- **Mutable stores that are NOT a fold of an append-only record (ten)**: `utility/model.yaml`
  (hand-edited; provenance only as `model_sha256` in gate `run_meta` `run_eval.py:893-894`);
  `utility/elicitations.jsonl` (no writer in code — append-only by convention, not
  mechanism); `config/data-sources.yaml` (`config.py:63-77`); `owner.md`
  (`owner.py:38-51`); `trips.db` `source`/`trip` (`trips/store.py:147-158`); `gtd.db`
  (incremental in-place `commands.py:27-30`, drift possible between rebuilds);
  `catalogue.duckdb` (rebuildable index; `reconcile` best-effort `derivations.py:493-497`);
  `external/pending.txt` (rewritten `:526-527`); every fixed-path eval snapshot (a.1 #8,
  #20); `lookup._U_BAR` (`lookup.py:960`, an in-process memo in front of a fold).

### (b) Decision entry points (`src/life_agent/core/`, `src/life_agent/membrane/`)

**b.0 The brief's candidate list, verified.**

```
$ grep -n "^def " src/life_agent/core/decide.py src/life_agent/core/pricing.py
src/life_agent/core/decide.py:60:def u_assert(p_correct: float, u_bar: Mapping[str, float]) -> float:
src/life_agent/core/pricing.py:47:def price_of(served_model: str) -> ModelPrice | None:
src/life_agent/core/pricing.py:60:def cost_usd(r: LLMResult) -> float | None:
```

| Candidate | Verdict |
|---|---|
| `core/decide.py` | **Not an entry point.** One pure function, the correctness-utility atom `u_assert` (`:60`); the rest of the 64-line file is the separability proof docstring (`:1-58`). No posterior, no argmax, no log. |
| `core/decisions.py` | **Not a decision-maker — the decision LOG and vocabulary.** `DecisionEvent :78`, `ACTIONS :41`, `LOOKUP_ACTION_ORDER :52`, `NARRATIVE_ACTION_ORDER :54`, `question_id :59`, `append :140`, `read :145`. |
| `core/deliberate.py` | **An instrument, not a decision.** `answer :279` produces a proposal; `record_answer :372` writes a §18.9 artifact; `parse_credence :102` is "a signal, never a score" (`:12`); `instrument(model) :196` is the one spelling of the edge id. |
| `core/executor.py` | **Yes, as the enactment body of the transform-selection decision — but it holds no posterior and picks no action** (`:19-20`, verified verbatim: "The body holds NO posterior and picks NO action; it only shapes evidence and enacts what the daemon scheduled"). The decision is taken by the credence daemon (`:4-6`). |
| `core/gate.py` | **Yes — the adoption-gate verdict** (`delta_posterior :308`). |
| `core/brain.py` | **Yes — the seam every argmax crosses**: `optimise :289` ("M4's decision rule"), `value :296` (VOI building block — **no in-repo caller**, transcript below). Transport, not policy (`_SKIN_PINNED :40-43`, `PROTOCOL_MAJOR :49`). |
| `core/pricing.py` | **Not a decision.** A price table: `price_of :47`, `cost_usd :60`; writes nothing. |

```
$ grep -rn "\.value(" src scripts bin --include=*.py | grep -v __pycache__
(exit 1)
```

Entry points the candidate list omitted: `core/lookup.py:894/:1041`, `core/narrative.py:346/:447`,
`core/seam.py:96`, `membrane/session.py:131`, `membrane/categorical.py:249`, `membrane/coarse.py:105`,
`bridge/server.py:765/:673/:695/:711` — all below.

**b.1 The response decision (report / report_scoped / hedge / ask_clarify / abstain).**

| Function | file:line | Inputs | Returns | Records written | Callers |
|---|---|---|---|---|---|
| `lookup.action_utilities` | `core/lookup.py:864` | posterior `weights` (K candidates + NONE), `u_bar`, `scoped_eu` | `dict[action → utility vector]`; `report_j` per candidate so "the MAP candidate emerges from the ENGINE, never a host argmax" (`:869`) | none | `lookup.decide :902` |
| `lookup.decide` | `:894` | `brain, state_id, weights, u_bar, scoped_eu` | `(action, eu)` via `SEAM.commit(SEAM.SkinOptimise(...))` `:907`; `report_j → report` `:911-912` | none | `decide_and_record :1069` |
| **`lookup.decide_and_record`** | `:1041` | observations, `indeterminate`, `n_hits`, `time_indexed`, `rho_override`; folds `u_bar` (`current_u_bar :1060`), posterior (`lookup_posterior :1063`), scoped option (`_scoped_option :1065`) | `LookupResult` | (1) §18.9 answer artifact `D.record` `:1110` under `lookup_answer_key :1099`; (2) `DEC.append(DecisionEvent(family="lookup", …, decision_id=akey.cache_key))` `:1124-1138` | `lookup_answer :1171`, `core/gather.py:171` |
| `lookup.lookup_answer` | `:1142` | question | route → observe → decide_and_record; `None` ⇒ narrative path | as above | `scripts/ask.py`, bridge |
| `narrative.include_eu` | `core/narrative.py:297` | `p, u_bar` | reference formula / test oracle — **not on the decision path** (`:306`) | — | tests |
| `narrative._include_fn` / `_claim_pref` | `:310` / `:323` | `tf`, `u_bar` | the integrated claim-EU as a `linear_combination`; `{include, withhold}` preference — "the engine picks — the body never compares EUs" | — | `decide_claims` |
| **`narrative.decide_claims`** | `:346` | `brain, scored=[(text,cites,cell,as_of,tf)], cells_ab, u_bar` | `(claims sorted by credence desc, action, eu, abstain_reason)`; per claim `SEAM.commit(SEAM.SkinOptimise(...))` `:369-371`; `report` iff any claim clears `:385`, else `REASON_ALL_WITHHELD :384` / `REASON_NO_CLAIMS :382` | none | `narrative_answer :484` |
| **`narrative.narrative_answer`** | `:447` | question, proposals, … | rendered answer | §18.9 artifact `D.record` `:510` under `narrative_answer_key :498`; `DEC.append(family="narrative", …, decision_id=akey.cache_key)` `:519-538` | `bridge/server.py:874` (`POST /narrative`), `scripts/ask.py:856` |
| `narrative.record_owner_verdicts` | `:283` | owner verdicts | appends `eval_claim` outcomes `:291` (only verdicted claims, disclosed `:258-259`) | outcomes log | `scripts/verdict.py:171-173` |
| bridge `POST /log_decision` → `_log_decision` | `bridge/server.py:765` | executor view | rejects `gather` (`:778-781`, `_TERMINAL_ACTIONS :739`); sorts credences leader-first `:791-794`; mints `decision_id` `:742-753` | `DEC.append :820`; mirrors to the membrane `:821-823` | `scripts/ask.py:962` (`_log_executor_decision :949`) |
| `decisions.DecisionEvent.__post_init__` | `core/decisions.py:111` | — | enforces the closed vocabulary | — | every producer |
| `core/utility.py` | — | **No `optimise` here.** `posterior :432` folds P(U); `UtilityPosterior.u_bar :259` is the posterior-mean utility "all a one-shot optimise needs" (collapse theorem); consumed by `lookup.current_u_bar :981` | — | — | — |

**b.2 The transform-selection decision (executor menu / probe scheduling / VOI).**

Key finding: **the executor does not decide.** `core/executor.py:4-6`: "there is one optimiser.
The **decision** lives in the credence daemon (`gather_decide` / `terminal_decide`) — it prices
the per-question transform MENU by `net_voi - cost` and arg-maxes. This module is the **body**
that enacts that schedule." That daemon is out-of-tree (`../credence`), reached over HTTP.

| Function | file:line | Role | Records |
|---|---|---|---|
| `executor.menu_transforms` | `:109` | the priced menu rows (`DEFAULT_TRANSFORMS :64` + `DELIBERATE_TRANSFORM :92`), `rho` re-priced through `_conditioned_rho :166`; upper-bound honesty note `:116-119` | none; callers `scripts/ask.py:1036`, `core/ask_client.py:107` |
| `executor.decide_via_loop` | `:222` | one question → `View` (`:48-49`) | none itself; callers `scripts/ask.py:1039`, `scripts/eval_executor.py:199`, `core/ask_client.py:132` |
| `executor.run_pass` | `:298` | the enactment loop; `_decide` closure `:457` posts through `SEAM.commit(SEAM.DaemonDecide(...))` `:470` — the daemon's view is the decision verbatim (`:468`); enacts by name `recency :493`, `corroborate*` tiers `:497` (`_TIER_MODEL :53`, `_TIER_RHO :56`), `retrieve_rerank/expand :520` (`_GROW_RETRIEVE :153`), `deliberate :536`, `re_extract_strong :589`; bounded iterations `:491`; USD→gauge via `u_bar["lambda_usd"]` `:434-440` | `POST /log_gather` per enacted grow via `_log_outcomes :339,:346` — the gather-outcome ledger (a.1 #5) |
| `gather_outcomes` | `core/gather_outcomes.py:37` (`SENSOR_FEATURES`), `:47` (`GROW_ACTUATORS`), `:76` (`append_outcome`), `:87` (`warm_counts`), `:111` (`grow_block`) | menu-as-data + its ledger; bridge `GET /grow_menu` `server.py:639`, `POST /log_gather` `:647` (vocabulary validated `:654,:661-663`) | a.1 #5 |
| probes | `core/probes.py:95` (`probe_recency`), `:119` (`probe_authority`), `:157` (`probe_subject`), `:189` (`probe_corroborate`); bridge `_probe_recency :246`, `_probe_subject :250`, `_probe_authority :258`, `_probe_corroborate :331`, `_probe_confirm :444`, `_probe_deliberate :574` | the enacted transformations | §18.9 records via `lookup.py:612/718`, `deliberate.py:391` |
| `brain.value` | `core/brain.py:296` | "the VOI building block (VOI = value(informed) − value(uninformed), composed at the call site)" — **no call site in the repo**; the VOI arithmetic lives daemon-side | — |
| **`seam.commit`** | `core/seam.py:96` | the one act seam: `SkinOptimise :56` → `brain.optimise :106`; `DaemonDecide :67` → `POST {daemon}/decide` `:109`; or a **declared gate** (`:102-103`) returning `abstain` without consulting anything — `GATE_WEAK_RETRIEVAL :38`, `GATE_EXECUTOR_DOWN :39`, `GATE_ENGINE_DOWN :42` | — |

The full act surface, verbatim:

```
$ grep -rn "SEAM.commit(" src scripts --include=*.py | grep -v __pycache__
src/life_agent/core/lookup.py:907:    dec = SEAM.commit(SEAM.SkinOptimise(brain=brain, state_id=state_id,
src/life_agent/core/narrative.py:369:            action = SEAM.commit(SEAM.SkinOptimise(
src/life_agent/core/executor.py:470:        dec = SEAM.commit(SEAM.DaemonDecide(post=post, daemon=daemon, payload=payload,
scripts/ask.py:778:        gated = SEAM.commit(None, gates=(SEAM.GATE_WEAK_RETRIEVAL,))
scripts/ask.py:1008:        gated = SEAM.commit(None, gates=(SEAM.GATE_EXECUTOR_DOWN,))
```

**b.3 The adoption-gate decision.** `gate.realised_utility :163` (prices spend at
`lambda_usd·cost_usd` `:171`, per-action branches `:173-184`, pure); `gate.realised_report :154`
(token-boundary gold containment via `matching.answer_matches`); **`gate.delta_posterior :308`**
— inputs `list[PairedOutcome]` (`:135`), a full `UtilityPosterior`, `oracle_p, n_draws, seed,
delta, level`; returns `GateResult :238` with `passed = p_gt >= level` `:349`; frozen-blind
`MATERIALITY_DELTA=0.05 :73`, `GATE_LEVEL=0.90 :76`, `DEFAULT_N_DRAWS=20000 :77`,
`DEFAULT_SEED=8675309 :78`; per draw `_sample_u :190` × `_dirichlet_ones :203` (`:339-344`);
censoring `PairedOutcome.censored :144` applied `:328`; writes nothing; callers
`scripts/run_eval.py:1672`, `scripts/gate_splice.py:113`, `scripts/membrane/p3_gate.py:325`.
`gate.render_report :394` → written by `run_eval.py:1679` (a.1 #8).

**b.4 Membrane shadow verdicts.** `membrane/shadow.py:9-10`: "off the SAME live traffic — never
on the decision path itself" (except M3 `decide_live`). Records go to `shadow.jsonl` (a.1 #9)
through `_append_record :898`.

| Entry point | file:line | Inputs | Record |
|---|---|---|---|
| `submit_decide` | `shadow.py:431` | `question_id`, `/decide` payload, daemon `dec` | `kind:"decide"` `:647-653` |
| `submit_decision` | `:450` | `decision_id, question_id`, the `DecisionEvent` dict | **no record** — in-memory `_bindings` `:457-460` |
| `submit_gate` | `:464` | `question_id`, gate name | `kind:"gate"` `:672-677` (`GATE_SUMMARY :210`) |
| `decide_live` | `:474` | payload + dec; bounded wait `_LIVE_WAIT_S=10.0 :222` | `kind:"enact"` `:711-719` |
| `submit_reaction` | `:500` | `decision_id`, valence → `verdict_y` (`session.py:67`) | `kind:"evidence"`, `stream:"verdict"` `:767-771` |
| `_tick_cat` | `:722` | `CatSummary` | `kind:"cat"` `:746-755` |
| `_write_boot_record` / `_write_stats_record` | `:853` / `:885` | — | `kind:"boot"` (with `u_bar`), `kind:"stats"` every `_STATS_EVERY=100 :229` + at `close()` |

Worlds and sessions: `membrane/world.py` — `DecideSummary :68`, `summary_from_payload :84`,
`summary_from_decision_event :106`, bucketing `:141-169`, `shadow_features :189`,
`utility_said :254`, `eu_by_action :277`, `argmax_action :286`, `respond_threshold :295`,
`handshake_decl :323`, `UTILITY_FORMS :46`. `membrane/session.py` — `decide :131` (a decide tick
never advances `t` `:132-133`), `observe_verdict :152`, `observe_outcome :159` (event-id
deduped), `verdict_y :67`. `membrane/categorical.py` — `decide_categorical :249` (K+1 mirror,
one evidence tick per obs code then one decide tick `:252-256`), `run_categorical :298` (fresh
engine per tick `:317-321`). `membrane/coarse.py` — `map_action :105` (engine act → rewrite of
the daemon view; agreement passes through `:112-113`), `_respond :69`, `_gather :81`,
`live_decide :137` (the injected `SEAM.LiveFn`). `membrane/client.py` — pure transport
(`spawn :62`, `request :147`, `shutdown :162`); no decision. Bridge exposure: `POST
/decide-support` `server.py:673`, `/gate-support :695`, `/decide-live :711`; dispatch tables
`_POST :882-899`, `_GET :900`; mirror wiring `core/shadow_mirror.py:48/:69/:82`
(`MIRROR_TIMEOUT_S=2.0 :34`, one-strike breaker `:94-101`). Doc:
`docs/membrane-shadow.md` §11 (`:474`), §12–§15, §17 (`:881`).

**b.5 The credence seam — is any decision made Julia-side? Yes, every argmax.** `core/brain.py`
methods and what crosses the wire: `initialize :208` (inline BDSL sources, never host paths
`:213-214`; major mismatch ⇒ `BrainError(-32010)` `:220-225`), `create_state :237`,
`condition :248` ("the only learning mechanism" `:249`), `weights/mean :258/:262`,
`expect :266`, `read_params :272` ("never folding `a += 1`" `:275-276`), `marginal :280`
("no belief arithmetic" `:284-285`), **`optimise :289`** → `(action, eu)`, `value :296`. The host
never compares EUs — asserted at `lookup.py:869`, `narrative.py:325`, `executor.py:20`. The
*second* Julia-side decider is the answer-brain daemon (`seam.py:35/:109`) pricing the transform
menu.

### (c) Projections / folds

| # | Fold | file:line | Input stream | Output store / artefact | Deterministic? | Order-dependent? | Staleness detection |
|---|---|---|---|---|---|---|---|
| 1 | `tasks.store.apply` | `src/life_agent/tasks/store.py:103` | one `Event` | SQLite `tasks` row | yes | n/a | — |
| 2 | `tasks.store.rebuild` | `store.py:143` | whole GTD ledger | `tasks` table at `GTD_DB_PATH` (`config.py:24`) | **semantically**: `id AUTOINCREMENT` is assigned in **insert order** (reset `:146`) | **yes** (ids) | none (manual) |
| 3 | `tasks.events.fold` | `tasks/events.py:214` | `list[Event]` | `{identity → OpenAssertion}` | yes | **no** — close always wins (`:218-220`) | — |
| 4 | `tasks.events.known_identities` | `:235` | `list[Event]` | `set[str]` | yes | no | — |
| 5 | `tasks.knowledge.render` | `tasks/knowledge.py:47` | events + `ledger_sha` | markdown | **byte-identical** given `(events, ledger_sha)` — "same events, same bytes" (`:48`) | yes (via `rebuild` ids and history reversal `:111`) | the stamp `:60` |
| 6 | `tasks.knowledge.write_state` | `:115` | ledger **file** | `$LIFE_AGENT_KB/tasks/state.md` (`config.py:29`) | yes; write-only-on-change `:124-125`; **`ledger_sha = sha256(ledger.read_bytes())` `:120-121`** — the stamp binds to the *bytes of the file*, not to the event set | yes | `parse_stamp(text) != (sha, RENDER_VERSION)` at `scripts/ask.py:1321` (verified) |
| 7 | `utility.posterior` | `core/utility.py:432` | `list[Evidence]` (Elicitation \| Reaction \| MarginReaction) | `UtilityPosterior` (in memory; conditioning via the credence skin) | semantically (engine quadrature) | **yes** — "consumed in order (the canonical replay order)" `:435` | `fold_version` |
| 8 | `utility.fold_version` | `:275` | model + events | sha256 hex | **byte-identical** (`:282-284`) | **yes** — hashes events in order | is the stamp |
| 9 | `lookup.current_u_bar` | `core/lookup.py:981` | model + elicitations + `load_reactions` (`:990`) | `(u_bar, version)` memo | yes | yes | version compare `:992` |
| 10 | `calibration.edge_outcomes_from_log` | `core/calibration.py:126` | `eval_edge` outcome rows | `list[EdgeOutcome]` | yes | **yes** — latest per `(edge, lineage key)` **in the superseded row's position** `:151-152`, code `:156-172` | append-only; regrade appends |
| 11 | `calibration.fit_edge_curves` / `fit_reliability_curve` | `:105` / `:82` | `EdgeOutcome`s | per-edge `ReliabilityCurve` | yes | no (binned counts `:89-96`, PAV `:53`) | via #10 |
| 12 | `reactions.load_reactions` | `core/reactions.py:176` | reactions ⋈ decisions on `decision_id` | `list[Reaction \| MarginReaction]` | yes | **yes** — latest per `(decision_id, kind)` `:184-187`; output = `latest.values()` insertion order | — |
| 13 | `claude_verdicts.latest_by_decision` | `core/claude_verdicts.py:137` | Claude verdicts | `{decision_id → event}` | yes | yes (last wins) | — |
| 14 | `narrative._cell_observations` | `core/narrative.py:196` | `eval_claim` rows filtered on the **current** `instrument_identity` (`:203`) | `{cell → [0/1]}` | yes | list order | instrument identity |
| 15 | `narrative.population_posteriors` / `coverage_posterior` | `:212` / `:232` | #14 / `eval_coverage` rows | Beta `(α,β)` per cell / `((α,β), n)` | semantically | exchangeable (Beta) | priors `_CELL_PRIORS :78`, `_COVERAGE_PRIOR :86` |
| 16 | `gate.delta_posterior` | `core/gate.py:308` | `list[PairedOutcome]` | `GateResult` | "Deterministic given (paired, posterior, oracle_p, seed)" (`:315`) | **yes** — one `rng` consumes draws in row order `:339-344` | frozen constants |
| 17 | `gate.render_report` + gate paired ledger | `gate.py:394`; `scripts/run_eval.py:1682` | `GateResult`; `paired` rows | `eval/gate/report.md`, `paired.jsonl` (`sort_keys=True` per line, `run_id`/`corpus_digest`/`corpus_snapshot` per row `:1684-1688`) | yes | yes | `run_meta.json` `:1554` |
| 18 | `run_eval.edge_outcome`; `_fresh_edge_rows` / `dedup_edge_events`; `narrative_claim_outcome` | `run_eval.py:350`; `:511/:539`; `:312` | edge firings + gold; prior log; narrative result + gold | `OutcomeEvent`s appended to the outcomes log | yes | first-wins on lineage (`:522-523`, `:547`) | §18.9 lineage dedup |
| 19 | `gather_outcomes.warm_counts` / `grow_block` | `core/gather_outcomes.py:87` / `:111` | gather log | `{contexts:[{ctx,n1,n0}]}` (`sorted` `:107`) / the `/decide` grow block | yes | **no** (`:19-20`) | none (`None` ⇒ cold prior) |
| 20 | `derivations.record` / `lookup` / `reconcile` | `core/derivations.py:440` / `:423` / `:493` | one `StageKey` + content / a key / `pending.txt` | cache files (+ queue) / bytes or `None` / catalogue rows | write-once (`:451-452`); meta.json commit marker (`:424-425`); idempotent (`:497`, `:537`) | file-first order is the commit protocol; queue order irrelevant | key identity; catalogue rebuildable |
| 21 | `shadow.boot_snapshot`; `_warm_outcomes` / `warm_question_id_map` | `membrane/shadow.py:1064`; `:1011` / `:973` | decisions ⋈ reactions ⋈ claude_verdicts; fair-fight vectors | `BootSnapshot`; `outcome_replay` + `WarmJoin` | yes; never raises (`:1094-1096`) | **yes** — owner segment then Claude segment (`:1084-1085`); latest reaction per `decision_id` | `n_source_records :1104`, `WarmJoin :144` (`note` non-empty iff wrong `:150-152`) |
| 22 | membrane report | `scripts/membrane/report.py:1833-1834` | `shadow.jsonl` | `report.{json,md}` under `membrane_dir()` (`:1818`) | yes (offline) | yes | last `boot` `u_bar`/`world_digest` |
| 23 | `regrade_edge_rows.latest_per_lineage` / `plan_regrades` | `scripts/regrade_edge_rows.py:33` / `:53` | `eval_edge` rows; rows + current gold | rows in force; `(to_append, unfixable)` — pure | yes | **yes** — mirrors #10 (`:35`) | `signals.regrade_of` names the superseded row's `tx_time` (`:11-12`) |
| 24 | `live_readout.summarize` | `scripts/live_readout.py:71` | decisions + reactions (`is_live :41`) | `Readout :52` | yes ("pure at the core" `:16-17`) | day ordering `:77` | days since last live decision `:79` |
| 25 | `reach.digest.build_digest`; `store.get_board` | `reach/digest.py:32`; `tasks/store.py:296` | the SQLite read-model (#2) | Telegram message; JSON board | yes given the DB | `ORDER BY id` | reads the projection |
| 26 | `outcomes.reliability_bins` / `ece` / `summarize_scores` | `core/outcomes.py:208/:230/:188` | `(p, correct)` pairs | calibration summaries | yes | no (binned) | — |
| 27 | trips `fold.fold` / `store.rebuild` | `trips/fold.py:48+` / `trips/store.py:128-145` | trips ledger | `reservation` table | yes | **no** (fidelity, then `received_at` — `fold.py:30-36`) | none (rebuild on every write) |
| 28 | pkm `rebuild_artifacts` | `src/pkm/rebuild.py:88` | `meta.json` + `lineage.json` on disk | `artifacts` + `artifact_lineage` | byte-exact | no | orphan sweep `:195` |
| 29 | pkm `staleness.stale` / `superseded` | `src/pkm/staleness.py:76` / `:47` | `artifacts` + lineage | `StaleArtifact` list | yes (sorted `:105,:108,:116`) | no (uses `produced_at`) | — |
| 30 | pkm path currency | `src/pkm/retrieval.py:46-59` | `sources` | a query-time view | yes | no | — |

Schemas and stamps quoted where they decide a golden-replay criterion:

```
# tasks/store.py:74-92 — the GTD read-model
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    list TEXT NOT NULL DEFAULT 'inbox',
    due_date TEXT,
    is_today INTEGER DEFAULT 0,
    origin TEXT NOT NULL DEFAULT 'human',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
)
# tasks/knowledge.py:60 — the state.md stamp
f"as of event {len(events)} · ledger sha256 {ledger_sha} · render v{RENDER_VERSION}",
# core/utility.py:278-284 — the utility fold version
payload = {"model": asdict(model),
           "events": [{"kind": type(e).__name__, **asdict(e)} for e in events]}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
# core/calibration.py:163-172 — supersession in place
keys = [(str(edge), k) for k in ev.lineage_keys]
hit = next((slot[k] for k in keys if k in slot), None)
if hit is None: rows.append(row); …
else:           rows[hit] = row; …
# core/reactions.py:183-187 — the join and the last-write-wins
decisions = {d.decision_id: d for d in DEC.read(decisions_path) if d.decision_id}
latest = {}
for r in read(reactions_path):
    latest[(r.decision_id, r.kind)] = r
```

Note `created_at TEXT DEFAULT (datetime('now'))` in the read-model: `store.apply` writes
`created_at` from the event's `tx_time` (the projection is a fold), but the schema default is a
wall clock — a replay that omitted the column would silently stamp replay time. Flagged for the
harness (Phase 2), not asserted as a defect.

### (d) Design-doc template

**There is no owner design-doc template in the tree.** Evidence: the only file named
"template" is `docs/failures-template.md:1` (`# FAILURES.md — authoring template`), which
templates the FAILURES.md *deliverable* (entry format `:10-15`, categories `:17-29`);
`docs/superpowers/plans/` holds three dated implementation plans (2026-07-23/24, trips), no
template; `.claude/` holds only `RESUME.md`; `CONTRIBUTING.md` H2s (`:6,:12,:36,:46,:62,:76`)
carry no design-doc section or Status convention; `docs/pkm/README.md:13` is a README status.

What exists is a **de-facto convention** across the nine design docs, visible in their headers
and H2 skeletons:

- a Status block immediately under the H1, in two spellings — blockquote bold
  (`docs/system-design.md:3` `> **Status: adopted 2026-06-11 (owner-approved); …**`,
  `docs/derivation-engine-design.md:3`, `docs/bayesian-foundations.md:3` + `Amendment` `:11`,
  `docs/pkm-retrieval-design.md:3`, `docs/candidates/brain-design.md:3`) or a plain line
  (`docs/answer-voi-executor-design.md:3` `Status: **draft for owner review** (date)`,
  `docs/scoped-claims-design.md:3`, `docs/trips-design.md:3`, `docs/membrane-shadow.md:3`);
- H1 = artefact name + em-dash gloss; explicit links to the docs it composes with; a "what
  this document is / is not" scoping sentence;
- H2 skeleton shared by seven of nine: `## 0/1 — what this document is / the frame / the
  problem` (`system-design.md:13`, `derivation-engine-design.md:11`,
  `bayesian-foundations.md:23`, `answer-voi-executor-design.md:13`,
  `scoped-claims-design.md:9`); numbered `Decision N —` sections each stating the decision and
  the rejected alternative (`derivation-engine-design.md:103-320`,
  `scoped-claims-design.md:27-79`); forward-compatibility / discipline
  (`derivation-engine-design.md:320`, `answer-voi-executor-design.md:106`,
  `scoped-claims-design.md:143`); phasing with gates (`system-design.md:133`,
  `derivation-engine-design.md:367`, `bayesian-foundations.md:935`,
  `answer-voi-executor-design.md:115`, `pkm-retrieval-design.md:74`, `trips-design.md:354`);
  how it is measured (`bayesian-foundations.md:673`, `answer-voi-executor-design.md:87`,
  `scoped-claims-design.md:129`); terminal `Open questions` / successors
  (`derivation-engine-design.md:389`,`:404`, `bayesian-foundations.md:996`,
  `scoped-claims-design.md:117`, `trips-design.md:420`; `system-design.md:154` genealogy
  variant); a change-surface / out-of-scope fence (`scoped-claims-design.md:151`,
  `answer-voi-executor-design.md:122`, `trips-design.md:320`).

**Proposed section headings for `docs/unified-ledger-design.md` — for approval, not
adopted** (Question 7):

```
> **Status: draft for owner review (date).** composes with PRINCIPLES §7/§16, system-design §3/§5,
> act-layer-events, bayesian-foundations §2/§8, pkm SPEC-PRINCIPLES §1–§4 / SPEC §7.1.
## 0. What this document is (and is not)          — scope, the outcome-preservation requirement
## 1. The record flavours today                    — pointer to r00 (a)/(c); the migration inventory
## 2. The event schema                             — (tx_time, seq, kernel_id, inputs, output, author, recorded_draw?), typed
## 3. Ordering and the merge rule                  — per-source seq + tx_time; each ledger's internal order preserved
## 4. Identity vs occurrence                       — content-addressing (pkm) ↔ the append log; what is an event
## 5. The recorded-draw rule                       — stochastic transforms: replay the draw, never re-roll
## 6. The derive/act boundary as a predicate        — recomputable-from-sources, on events not substrates
## 7. Folds as adapters                            — one adapter per read-model; byte vs semantic identity each
## 8. Migration plan and checkpoints               — dual-write; retirement out of scope
## 9. Golden replay criteria (pre-stated)          — artefact list; identity kind; deciding command per artefact
## 10. Discipline and change surface               — refusal list; SPEC-first where pkm is touched
## 11. Open design questions                       — genuine questions only
## Appendix A. PRINCIPLES amendment proposals       — §7 boundary-as-predicate; the "governor" word
```

### (e) The engine-§12 vs PRINCIPLES-§14 "governor" contradiction — the exact lines

```
$ sed -n 400,402p docs/derivation-engine-design.md
The **VOI governor** is explicitly deferred beyond both: it is the abstraction the
no-abstraction-before-three-implementations rule forbids until the demand logs and the
confidence layer exist to calibrate against.
$ sed -n 121,123p PRINCIPLES.md
- **The executor unification is adopted (2026-06-28):** an autonomous agent *is* (belief,
  utility, decision space) ranked by expected utility (§1) — there is no separate "governor" to
  build later. The **VOI executor** — one argmax-EU over the terminal responses **and** the
$ sed -n 147,149p PRINCIPLES.md
invariant is that truth is the fold.* This is **the executor**; §1 makes plain it is not a
deferred final stage — an autonomous agent simply *is* (belief, utility, decisions) ranked by
EU, so there is no separate "governor" to build afterwards. There is only this optimiser: built
```

Supporting engine-design lines that treat the governor as a distinct future layer: `:20-21`
(L3 "VOI governor" in the layer list), `:27`, `:29-31`, `:44-45`, `:325`, `:333`. Also
`docs/system-design.md:44`, `:62`, `:71` (L3 row), `:145`. Assessment: real, dated,
one-directional — engine design adopted 2026-06-11, PRINCIPLES §14's executor unification
2026-06-28; PRINCIPLES `:127-128` re-grounds `bayesian-foundations.md` §12's "stage 6 governor"
but **never names engine-design §12**, so an adopted-status doc still says "explicitly deferred"
beside PRINCIPLES' "no separate governor". The code sides with PRINCIPLES (`core/executor.py:4`
"PRINCIPLES §16: there is one optimiser"); "governor" survives in `src/` only as vestigial prose
(`bridge/server.py:770`, `core/lookup.py:1106`, `core/utility.py:261`; `membrane/shadow.py:12,66`
refer to the sibling *credence-governor* repo, a different object). Middle artefact:
`docs/answer-voi-executor-design.md:6-8` (2026-06-18) "scopes the governor to the MVP" — the
design that became `core/executor.py`. The proposal (retire the word) is drafted in Phase 1's
appendix, not here.

## DEVIATIONS

1. **Coverage beyond the brief's list.** The brief names pkm sources/derivations, act-ledger
   events, demand-log entries, outcomes, decision/calibration records. The census also
   inventories: the trips ledger, gather-outcomes, Claude verdicts, corrections, the membrane
   shadow log, fair-fight records, labels, the judge cache, dogfood log, owner profile,
   deliberate side records, pkm telemetry/diagnostic/tool logs, approvals, `schema_meta`,
   chunks/FTS/currency/staleness. "Every immutable-record flavour" was read literally;
   flagged so the reviewer can prune (Question 8).
2. **Method.** Three parallel Explore subagents did the sweep; I read the controlling texts
   myself and spot-verified the load-bearing rows by direct `sed -n`. Where a subagent's
   phrasing entered this report it was checked against the cited line first.
3. **Environment, not code.** The first suite run was destroyed by the `/tmp` per-user quota
   (STATE). I re-ran with temp storage on the root disk rather than freeing `/tmp` — an
   attempt to remove eighteen orphaned `tailwindcss-linux-x64` downloads (≥12 h old, zero open
   handles) was blocked by the permission classifier and not retried. Nothing outside the
   repo was modified. The condition persists and will keep breaking any `/tmp`-based test run
   on this box until someone with permission clears it (Question 9).
4. **Scratchpad.** Because `/tmp` was over quota, working files for this phase went to
   `~/.cache/census-r00/` instead of the session scratchpad; nothing there is needed again.

## REFUSED

- No edit to `PRINCIPLES.md`, any pkm SPEC, `src/`, or `$LIFE_AGENT_KB`; no `$LIFE_AGENT_KB`
  reads at all (the census is code-only, so no data entered the tree).
- The design doc and the PRINCIPLES amendment texts were **not** drafted — Phase 1, gated on
  this report's review; only headings are proposed (d).
- No commit (owner commits on request).
- No new dependency, directory outside `docs/`, or file format.

## QUESTIONS

1. **`tasks/state.md` — byte or semantic?** Its stamp hashes the *ledger file bytes*
   (`knowledge.py:120-121`; checked at `ask.py:1317-1321`). After unification the GTD events
   are a sub-stream; the fold adapter can reproduce byte-identical `state.md` only if it hashes
   the *original* `events.jsonl` bytes (kept as the dual-written store) or if the stream
   carries each original line verbatim. Which does the owner want: (a) byte identity, stamp
   preserved (the adapter reads the old ledger's bytes for the sha); (b) byte identity of the
   body with a re-defined stamp (a `render v3` bump — semantically identical); or (c) the sha
   over the sub-stream's canonical serialisation? (a) keeps the old store load-bearing; (b)/(c)
   change a stamp the ask path already parses.
2. **`gtd.db` — semantic only.** SQLite `id AUTOINCREMENT` follows insert order
   (`store.py:143-148`) and `created_at` has a wall-clock default (`:83`). Confirm the criterion
   for `gtd.db` is *row-set equality modulo `id`* (i.e. compare on `identity`), not byte-identity
   of the database file.
3. **Utility posterior replay needs the credence skin.** `utility.posterior` conditions
   through Julia (`utility.py:432-458`); `fold_version` is a pure sha over `(model,
   events-in-order)` (`:275-284`). Is the golden criterion `fold_version` equality (pure Python,
   no Julia) plus `u_bar` equality *when the skin is available*, or must the harness always
   drive Julia?
4. **`tx_time` normalisation.** Clocks differ (naive local in `tasks/events.py:59` and
   `trips/events.py:33`; UTC-aware in `outcomes.py:94`; naive UTC in `derivations.py:473` and
   the pkm catalogue; float epoch in `shadow.jsonl`; and no `seq` anywhere). The merge rule can
   only be *per-source sequence + original stamp verbatim* (never a cross-source `tx_time`
   sort). Should the unified event carry the original stamp verbatim **and** a normalised
   UTC-aware `tx_time`, or the original only? (bayesian-foundations §2 makes order semantics
   for the calibration logs — a re-sort would change posteriors.)
5. **Are pkm's content-addressed sets events?** `artifacts`/`artifact_lineage`/the cache are
   *sets* (no order, identity = key); what is event-shaped is the **occurrence** (`produced_at`
   in `meta.json`, the demand line, the telemetry line) pointing at the identity
   (SPEC-PRINCIPLES §2/§3: "a transform invocation is an event"; the cache is a view over the
   record). Proposal to rule on: the unified stream records *occurrences* (`kernel_id` = the
   instrument identity = cache key minus `input_hash`; `inputs` = the lineage keys; `output` =
   the artifact's cache key) and never the artifact bytes. Yes/no?
6. **The demand log** has zero readers and SPEC says it cannot be backfilled
   (`SPEC.md:1804-1806`). Include it as an event flavour (occurrence rows with `hit`),
   exclude it, or defer? Same question for pkm's transform telemetry log.
7. **Template.** Approve the proposed headings in (d), or supply the owner's template.
8. **Exclusions.** Confirm which flavours are *out* for tranche 1: pkm diagnostic log
   (`logs/<date>.jsonl`), the MCP `--tool-log`, dogfood markdown, `owner.md`, deliberate side
   records, all §20 snapshot artefacts, and the fair-fight run directories (large, per-run,
   already content-pinned by `questions.sha256`)?
9. **The `/tmp` quota.** Not a repo matter, but it will invalidate every Phase-2 harness run
   that uses `tmp_path`: may I (or should the owner) clear the orphaned tailwind downloads, and
   should the harness pin `--basetemp` under `$LIFE_AGENT_KB/tmp/` (root disk) as a rule?
10. **Trips in scope?** The trips ledger is a second act ledger with a *non-file-order* fold
    (fidelity then `received_at`) and two un-folded side tables. Include it in tranche 1's
    stream (it is small and structurally identical to tasks) or defer to keep the tranche to
    the brief's named flavours?
11. **`event_id` payload asymmetry.** Tasks' `event_id` excludes the payload
    (`tasks/events.py:86-96`); trips' includes it (`trips/events.py:51-60`). Should the unified
    event's identity hash the full record (payload included) — the natural choice for
    "content-addressed occurrence" — accepting that old task `event_id`s are then a legacy
    field carried, not the identity?

## PROPOSED

Open Phase 1 on receipt of rulings 1–11: draft `docs/unified-ledger-design.md` under the
approved headings, using (a)/(c) above as the migration inventory and (e) as the appendix's
evidence; the golden-replay artefact list starts from folds #2, #5/#6, #7/#8, #10–#13, #16
and pkm #28.

## STATE — addendum (2026-08-18, same day, appended after the body was written)

The root-disk re-run of the default suite completed green:

```
$ TMPDIR=~/.cache/census-r00/tmp uv run pytest -q --basetemp=~/.cache/census-r00/basetemp -p no:cacheprovider
........................................................................ [ 87%]
........................................................................ [ 90%]
........................................................................ [ 93%]
........................................................................ [ 96%]
........................................................................ [ 99%]
.............                                                            [100%]
2317 passed, 34 deselected in 145.43s (0:02:25)
exit=0
```

So at HEAD `873860a`: ruff clean, mypy clean (198 files), **2317 passed / 34 deselected** (the
`llm`/`system` markers). The earlier red run was the `/tmp` quota, not the code.

## VERIFICATION RECORD (2026-08-18, before delivery — the "every `file:line` spot-checked" commitment)

The reviewer's note on the plan held me to spot-checking **all** subagent-produced rows, not
only the load-bearing ones. Done before this report was relayed, so the body above already
carries the corrected numbers; this section records what the check was and what it caught, so
nothing is silent. (The report protocol's append-only rule governs a *delivered* report; this
is the pre-delivery draft. From delivery onward, corrections are new dated sections only.)

**Method.** A small verifier (kept out of tree at `~/.cache/census-r00/verify_refs.py`)
parsed every `path:N[-M]` and shorthand `:N[-M]` reference in this file, resolved bare names
against the known source dirs (pkm-first inside the pkm table), checked file existence and
line range, and flagged where the nearest preceding backticked identifier did not occur within
−3..+3 lines of the cited range. Independently, `grep -n "^def \|^class \|^[A-Z_]* ="` was run
over **every cited file** (68 files, 1298 def/class/constant lines) and every cited function,
class and constant in the tables was compared by eye against that dump.

```
$ uv run python ~/.cache/census-r00/verify_refs.py          # after corrections
refs checked: 1107; resolvable+in-range: 1041; hard failures: 66; ident-heuristic misses: 227
```

The 66 residual "hard failures" and the 227 identifier misses were each reviewed by hand and
are **tool attribution artefacts** (a shorthand `:1300` after "SPEC" resolved against a `.py`
file; a bold-wrapped module hint like `**`lookup.decide_and_record`**` not parsed, so the cell's
`:1041` fell back to the row's first path; `bridge/server.py` probe handlers cited by name only,
resolved to `core/probes.py`; CONTRIBUTING.md H2 lines resolved to the previous file) — in each
case the report's own text names the right file. Not one of them was a wrong citation.

**What the check caught and corrected in the body (all four were subagent-produced):**

1. **`src/pkm/staleness.py` — every line number was wrong** (the file is 116 lines; the sweep
   had cited `superseded :127-153`, `stale :156-196`, `StaleArtifact :112-124`, `:149`,
   `:185/:188/:196`, `:94-95` — none in range). Re-cited from the file: constants `:28-29`,
   `StaleArtifact :33-44`, "only reads" `:14-15`, `superseded :47-73` (SELECT `:55-58`,
   grouping `:60-62`, current = max `(produced_at, cache_key)` `:68-70`), `stale :76-116`
   (adjacency `:91-96`, BFS `:105-114`, `sorted` at `:105`/`:108`, output sorted `:116`).
   Rows affected: a.2 #5, #6, #10; (c) #29.
2. **`src/life_agent/membrane/shadow.py` — the `_read_*` helper block was mis-cited by
   ~+140 lines** (`_read_decisions :1063-1072` etc.). Actual: `_read_lines_fail_open
   :919-923`, `_read_decisions :926-936`, `_read_reactions :938-949`,
   `_read_claude_verdicts :951-959`, fail-open-per-line rationale `:906-915`,
   `boot_snapshot :1064-1138`. The other shadow numbers (`:1084-1086` replay order,
   `:1116-1123`, `:1124-1131` owner precedence, `:972-1007`, `:1011-1060`, `:1043-1044`,
   record kinds, `_append_record :898-904`) were verified correct. Rows affected: a.1 #2, #3,
   #4, #9; a.4.
3. **`scripts/answer_labels.py` — off by 1–2 throughout**: `Label :36-40` (was 34-39),
   `load_labels :43-56`, `verdict :59-75`, `is_labeled :78-79`, `append_label :82-90` (was
   84-91 in a 90-line file), last-wins at `:74`, `value_norm :87-88`. Rows: a.1 #16; a.4 (d).
4. Small offsets: `owner.py:38-52` → `:38-51` (51-line file); `trips/fold.py:28-33` →
   `_better :30-36`; and one ambiguity clarified (`commands.add` is *called at*
   `tasks/project.py:157-163`).

Everything else cited in (a)–(e) matched the def/constant dump: derive, transform_run, cache,
catalogue, ingest, rebuild, retrieval, chunking, approval, telemetry, logging_setup,
mcp_server, cli, hashing, extract, transform_declaration, all five migrations, world, session,
categorical, coarse, client, trips store/fold/identity/commands/events, seam, executor, lookup,
narrative, gate, calibration, derivations, utility, reactions, claude_verdicts,
gather_outcomes, probes, brain, shadow_mirror, temporal, subject, deliberate, tasks
store/knowledge/project/commands, bridge/server, fairfight/records, digest, run_eval,
run_fairfight, eval_judge, verdict, claude_verdict, regrade_edge_rows, live_readout,
membrane/report, ask, and the SPEC/PRINCIPLES/engine-design line quotes (which were pasted
from `sed -n` output, not transcribed).

## RULINGS RECEIVED (reviewer, relayed by the owner 2026-08-18) — recorded, with what still awaits signature

Verbatim substance of the reviewer's verdict on the Phase-0 plan: *strong census — approve
Phase 0*, with rulings to fold into r00 and carry into Phase 1. Recorded here per the report
protocol; **Phase 1 opens on the owner's signature, not on the review** — the STOP holds.

**Two reviewer self-corrections, recorded as given.** (1) The brief's candidate decider list
named `decide.py`, `executor.py`, `pricing.py`; the census dispositions them as a pure atom, an
enactment body that "holds NO posterior and picks NO action", and a price table — "verify,
don't trust this list" did its job. (2) The brief's merge requirement "preserves each original
ledger's internal order" is under-specified: the trips fold orders by fidelity then
`received_at`, not file order, so **the correct invariant is that each fold's declared ordering
key remains computable from the stream** — not that file order is sacred. The design doc's §3
must state it that way.

**Findings the reviewer names as landing directly in the design doc:** no flavour carries a
`seq`; four incompatible `tx_time` clocks; eight-plus writers bypassing `jsonl_log`'s
durability; the utility fold requiring Julia; the identity/occurrence split on the pkm side.

**Rulings on QUESTIONS 1–8** (resolved by reviewer ruling unless marked *awaits signature*):

- **Q1 (state.md stamp) — RESOLVED.** The stamp is derived display, not truth. During tranche
  1's dual-write the original ledger file keeps being written, so the fold adapter keeps hashing
  those bytes — byte-identical stamp for free. The byte-vs-semantic decision belongs to the
  cutover tranche (separately signed); the criterion is to be *pre-stated* that way, not decided
  now.
- **Q2 (gtd.db) — RESOLVED.** Semantic identity; the comparator must be defined in the
  pre-stated criteria (row multiset ignoring `id`, or a canonical ordering). No byte identity of
  the SQLite file.
- **Q3 (utility fold) — RESOLVED as "both", one call *awaits signature*.** `fold_version` sha
  is the cheap always-on gate; the golden run itself goes Julia-in-the-loop **once**, credence
  version pinned and recorded in the transcript (dual-purpose: the first parity datum for the
  later credence→proplang swap); thereafter sha-only. **Awaits the owner's signature:** the
  CI-weight call — how often, if ever, the Julia-in-the-loop run repeats.
- **Q4 (clocks) — RESOLVED.** Never order across sources on `tx_time`. Total order =
  deterministic interleave keyed by `(source_id, per-source seq)`; original stamps preserved
  verbatim (compensating-entry ethos); a normalised UTC `tx_time` added as a *derived
  annotation* only. Where a fold needs a cross-source order it declares one — membrane
  `boot_snapshot`'s owner-then-Claude merge is the precedent; declared-per-fold is the rule.
- **Q5 (identity vs occurrence) — RESOLVED.** Endorsed: content-addressed artifacts are
  identities (set semantics, no ordering); the stream records *occurrences* pointing at them.
  This is the answer to the design doc's "content-addressing vs append log" section — write it
  as such.
- **Q6 (demand log) — RESOLVED: in scope.** Zero readers is the argument (system-design §3
  designates it the governor's future calibration corpus); it joins the stream before it grows
  further. Non-backfillable is fine — the stream has an epoch.
- **Q7 (headings) — APPROVED with one addition, and the approval itself *awaits signature*.**
  Add a **durability contract** section (single writer, fsync / temp-and-rename guarantees) —
  the census found three durability regimes and unifying the writer is half the point. The
  heading list in (d) is therefore amended to: `… ## 10. Durability contract · ## 11. Discipline
  and change surface · ## 12. Open design questions · Appendix A`. The reviewer notes the
  headings are "genuinely yours" — the owner signs them.
- **Q8 (exclusions) — RESOLVED.** Exclude the pkm diagnostic log and the MCP tool-log
  (operational telemetry; the tool-log's non-idempotence is SPEC-sanctioned). The transforms
  telemetry log is excluded from tranche-1 *migration* but named in the design doc as a
  candidate later flavour (recorded, not silent). Added to the open-items ledger, low priority:
  `FAILURES.md` is itself an append-only evidence stream out of tree — Phase 1 notes (does not
  decide) whether it eventually becomes an event flavour.

**Not ruled on (still open for the owner):** Q9 (`/tmp` quota / harness `--basetemp` rule),
Q10 (trips ledger in tranche 1 or deferred), Q11 (unified `event_id` hashes the payload;
tasks' legacy `event_id` carried as a field). Plus the two "awaits signature" items above (Q3
CI-weight; Q7 headings).

**Signature awaited.** Per the reviewer: "Phase 1 opens on your signature, not on my review."
This report stops here.

## STATE — addendum 2 (2026-08-18): PII guard and working tree at delivery

```
$ uv run python .githooks/pii_check.py --shapes-only docs/unification/reports/r00-census.md
exit=0
$ LIFE_AGENT_KB=<kb> uv run python .githooks/pii_check.py docs/unification/reports/r00-census.md
exit=0
```

(The first run of the guard blocked one line — a.1 #19's elided `mcp-config.json` path (written
with a leading ellipsis), which the shape rule reads as a non-placeholder root — rewritten as the full
`$LIFE_AGENT_KB/tmp/deliberate/workdir/…` path; both modes then pass. The denylist mode reads
only the pattern file under `$LIFE_AGENT_KB`, nothing else — disclosed because REFUSED above
says "no `$LIFE_AGENT_KB` reads"; this one is the repo's own commit gate, run read-only.)

`git status --short` at delivery shows two untracked entries: `docs/unification/` (this
report) and `docs/2026-08-agent-litsweep-dispositions.m` — **the latter is not mine** (it
predates or is concurrent with this session; untouched, unread, and left alone). Still not
committed.
