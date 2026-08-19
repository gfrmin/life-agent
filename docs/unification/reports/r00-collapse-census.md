# r00-collapse — module-collapse pre-census — 2026-08-18

The grep-and-disposition census that opens tranche 2 (the module collapse): a read-only
inventory of (1) the decision entry points, (2) the belief-adjacent modules, (3) the call
graphs from external trigger to enacted effect, (4) the duplication table, (5) the PRINCIPLES
§16 gap list, and (6) every tunable each module reads. It is a census, not a design doc —
disposition vocabulary only; anything that begs for a proposal is a QUESTION. No code was
changed. Line numbers are against the pinned HEAD named in STATE, machine-verified against the
detached worktree (VERIFICATION RECORD). British spelling; no corpus values, no owner-specific
absolute paths, no `$LIFE_AGENT_KB` reads.

**Placement.** This report was written OUTSIDE the repository tree, at
`~/.cache/life-agent-census/r00-collapse-census.md`, because a separate session held the
repo's write token (ledger-unification tranche 1, Phase 3) for the whole of this one. The
owner places and commits it (the intended home is beside `docs/unification/reports/r00-census.md`)
after the tranche-1 write token is released. Nothing here was written into the main tree
(`$REPO` below — the checkout of `github.com/gfrmin/life-agent` that holds the write token) or
into the worktree.

Cross-references: "r00 (b)" / "r00 (c) #n" name the sections and fold-table rows of the prior
census `docs/unification/reports/r00-census.md` (2026-08-18); its dispositions of
`decide`/`executor`/`pricing` are inherited unless contradicted below (none were).

## STATE

**Pinned HEAD, worktree.**

```
$ git -C $REPO rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git -C $REPO worktree add --detach ~/.cache/life-agent-census/wt 873860a9b651fdc528bcd6b5f17f669205bca54a
Preparing worktree (detached HEAD 873860a)
HEAD is now at 873860a fix(pii-guard): close the HK/name gap that let the leak through, and arm the hooks
$ git -C ~/.cache/life-agent-census/wt rev-parse HEAD
873860a9b651fdc528bcd6b5f17f669205bca54a
$ git -C ~/.cache/life-agent-census/wt status --short
(clean)
```

The census is *as of* `873860a`. Commits that land in the main tree during the session are
not rebased onto; the worktree was not touched after creation (no edits, no `uv sync` needed —
see VERIFICATION RECORD for how the guard was run).

**Suite NOT run** — read-only session by brief; no `pytest`, no `ruff`, no `mypy` were
invoked. r00's STATE addendum records the last green run at this same HEAD (2317 passed / 34
deselected; ruff + mypy clean).

**Prior census read from the main tree.** `docs/unification/reports/r00-census.md` is
UNTRACKED in the main tree (`git status --short docs/unification` → `?? docs/unification/`)
and therefore absent from the pinned worktree; it was read read-only from
`$REPO/docs/unification/reports/r00-census.md` so its (b)/(c) rows could be cited. Reading is
not writing; nothing else in the main tree was touched.

**`$LIFE_AGENT_KB`:** not read, not listed, not resolved.

## DONE

### Method

Direct reads of every in-scope module (`cat -n` / `awk` with line numbers, pasted not
transcribed), plus `grep -rn` sweeps over `src/` and `scripts/` for every call site and
consumer. No subagents were used in the end — the in-scope surface (~12 k lines across
`core/`, `membrane/`, `bridge/`, `scripts/ask.py`, `core/ask_client.py`) was read directly, so
every row below is first-hand; the all-rows verifier (VERIFICATION RECORD) then re-checked
every `file:line`. Paths are repo-relative; a bare `:N` continues the row's last-named file.
Abbreviations: `LK`=`core/lookup.py`, `NR`=`core/narrative.py`, `EX`=`core/executor.py`,
`GATE`=`core/gate.py`, `DEC`=`core/decisions.py`, `SEAM`=`core/seam.py`, `BR`=`bridge/server.py`,
`SH`=`membrane/shadow.py`, `W`=`membrane/world.py`, `CO`=`membrane/coarse.py`,
`ASK`=`scripts/ask.py`, `AC`=`core/ask_client.py`. A "◆" marks a *choice among alternatives*
made in host Python (an argmax, threshold, ordering, or short-circuit) — the raw material for
§5.

### 1. Decision entry points

**1.0 The brief's candidate list, verified.** r00 (b) b.0's verdicts stand; this table adds
inputs / outputs / call sites and re-checks each against the pinned lines.

| Candidate | Disposition (unchanged from r00 unless noted) | Decides | Inputs | Outputs / side effects | Call sites |
|---|---|---|---|---|---|
| `core/decide.py` | **pure atom** — one function `u_assert :60` (the rest, `:1-54`, is the separability docstring) | nothing; supplies `p·u_correct + (1-p)·u_wrong` | `p_correct`, `u_bar` | none | `LK.action_utilities :878-879`; `NR.include_eu :307` (reference formula only — "not on the decision path" `:306`) |
| `core/decisions.py` | **log + vocabulary** — `DecisionEvent :78`, `ACTIONS :41`, `LOOKUP_ACTION_ORDER :52`, `NARRATIVE_ACTION_ORDER :54`, `question_id :59`, `append :140`, `read :145` | nothing; enforces the closed vocabulary `:111-125` | — | appends `DECISIONS_LOG` (`config.py:83`) via `jsonl_log` | producers `LK:1124`, `NR:519`, `BR._log_decision :820`; readers `reactions.load_reactions :183`, `BR._log_reaction :839`, `SH._read_decisions :926` |
| `core/deliberate.py` | **instrument** — `answer :279` proposes; `record_answer :372` writes a §18.9 artifact; `instrument :196` is the one edge-id spelling | nothing on the argmax; two *instrument-internal* choices: retry once `:308`, and the "blind decline ⇒ status=error" reclassification `:331-336` (◆ short-circuit: `detect_decline and not tool_log_rows`) | `question`, `DeliberateConfig :153` (`model`, `timeout_s`, `max_turns` defaults `:167-169`), the claude CLI over the pkm MCP surface `:207-228`, env `HOME`/`PATH` only `:231-234` | `DeliberateResult :173` (raw credence parsed `:102-114`, in-range only); `record_answer` refuses non-ok `:378-379` and blind declines `:380-383` | `BR._probe_deliberate :612` (answer) / `:615` (record); `EX:133,:564` (`instrument`) |
| `core/executor.py` | **enactment body** (r00: "holds NO posterior and picks NO action" `:19-20`) — *but see §3 trace A / §5: the body holds several host-side choices around the daemon's argmax* | the *transform-selection* argmax is the credence daemon's (`:3-6`), reached only via `SEAM.commit(DaemonDecide) :470-471` | `question`, `k`, `route`, `transforms` (`DEFAULT_TRANSFORMS :64` + `DELIBERATE_TRANSFORM :92`), `curves` (`Curves :39`), `u_bar` from `GET /utility` `:428`, `grow_lane`/`live` flags | a `View :48`; side effects: every bridge call (`/retrieve`, `/probe/*`, `/extract`, `/probe/corroborate`, `/probe/deliberate`), `POST /log_gather` per enacted grow `:339-350`; no ledger write of its own | `ASK.answer_via_executor :1039`; `AC.answer :132`; `scripts/eval_executor.py:199`; `scripts/run_eval.py:971` (via `ask.answer_via_executor`) |
| `core/gate.py` | **adoption-gate verdict** — `delta_posterior :308` | ADOPT/NOT: `passed = p_gt >= level :349` (◆ a **posterior-mass threshold**, δ `:73`, level `:76`, not an EU comparison — §5 G-1) | `list[PairedOutcome] :136`, a full `UtilityPosterior`, `oracle_p`, `n_draws :77`, `seed :78` | `GateResult :239`; writes nothing itself; `render_report :394` is written by `scripts/run_eval.py:1679`. Host-side EU arithmetic: `realised_utility :163` (per-action branches `:173-184`, spend `:171`), `_sample_u :190` (Gaussian moment sampler `:196-200`), `_dirichlet_ones :203` | `scripts/run_eval.py:1672`; `scripts/gate_splice.py:113`; `scripts/membrane/p3_gate.py:325`; `realised_utility` also `scripts/gate_splice.py:116-117`, `scripts/membrane/p3_gate.py:180-227` |
| `core/brain.py` | **the seam every in-process argmax crosses** — `optimise :289` ("M4's decision rule"); `value :296` (VOI building block, **no in-repo caller** — re-verified: `grep -rn "\.value(" src scripts` → only the definition) | nothing itself; transport (`_call :194`, `SubprocessTransport :80`) | JSON-RPC over stdio to the pinned `credence-skin` image `:40-44` (`CREDENCE_SKIN_IMAGE` env), dev override `:54-55`, `PROTOCOL_MAJOR :49` | opaque `state_id`s server-side; `optimise` returns `(action, eu)` | `SEAM.commit :106` (the only `.optimise(` in `src/`, drift-gated per `seam.py:21-23`); `create_state/condition/expect/mean/read_params/marginal` from `LK`, `NR`, `utility.py`, `gather.py` |
| `core/pricing.py` | **price table** — `PRICE_TABLE :33`, `price_of :47` (longest prefix `:53-56`), `cost_usd :60`; `PRICING_VERSION :20` | nothing | an `LLMResult` | a USD float or `None` (unpriced ⇒ caller records partial `:49-50`) | `BR._probe_corroborate :406`; `scripts/eval_factory/factory.py:618`; `scripts/fairfight/run_fairfight.py:527` |
| `core/probes.py` | **transformations (re-weight / gather), not deciders** — `probe_recency :95`, `probe_authority :119`, `probe_subject :157`, `probe_corroborate :189` | nothing on the argmax; internal choices: email-header date fallback only for `_EMAIL_PRODUCER` hits `:111-112` (◆ short-circuit "projected date always wins"), verdict→state map `_VERDICT_TO_STATE :134` (`unclear` default `:153`), `probe_corroborate` over-fetches `k*4` and keeps max-score per chunk text `:201-205` | catalogue conn, root, hit keys / question + leader value | covariate maps / new hits; **no writes** (read-only over the catalogue `:16-18`; the subject probe's `owner_verdict` is cached elsewhere) | `BR:247,:252,:259,:416,:871`; `core/gather.py:94,:150,:152`; `ASK:765`; `scripts/answer_brain_gate.py:142-143` |
| `membrane/` (all) | **shadow verdicts + one flag-gated live decider** — see 1.4 | `session.decide :131` / `categorical.decide_categorical :249` return the proplang engine's choice; on the decision path **only** under `LIFE_AGENT_MEMBRANE_LIVE=1` (`config.py:166-171`) via `coarse.live_decide :137` → `SH.decide_live :474` → `CO.map_action :105` | the executor's `/decide` request+reply pair | `shadow.jsonl` records (`SH._append_record :898`); the mapped view (live) | `BR:673,:695,:711` (feeds), `ASK:1025`, `AC:128`, `scripts/eval_executor.py:85` (live consult) |

**1.1 The response decision (report / report_scoped / hedge / ask_clarify / abstain).**
r00 (b) b.1 stands. Re-verified rows and the choices around them:

| Function | file:line | What it decides / holds | Inputs | Outputs + writes | Callers |
|---|---|---|---|---|---|
| `LK.action_utilities` | `core/lookup.py:864` | builds the per-action utility vectors; `report_j` per candidate so "the MAP candidate emerges from the ENGINE, never a host argmax" `:869`; `ask_clarify` priced at `_ORACLE_P·u_correct − lambda_int` `:884`; `report_scoped` flat at `scoped_eu` `:886` | `weights`, `u_bar`, `scoped_eu` | dict of vectors | `LK.decide :902` |
| `LK.decide` | `:894` | the argmax — via `SEAM.commit(SkinOptimise) :907-908`; host relabels `report_j → report` `:911-912` (a render label, not a second decision `:899-900`) | `brain, state_id, weights, u_bar, scoped_eu` | `(action, eu)` | `decide_and_record :1069` |
| `LK._scoped_option` | `:1003` | the report_scoped inputs; ◆ host picks the **freshest dated observation** as V_s (`max(dated, key=doc_date) :1020`); the EU itself is `brain.expect` `:1032/:1037`; ◆ short-circuit: no dated obs ⇒ `(0.0, 0.0, None, None) :1018-1019` (scoped can never win) | observations, candidates, rho, u_bar, state | `(scoped_eu, p_attested, V_s, as_of)` | `decide_and_record :1065` |
| **`LK.decide_and_record`** | `:1041` | folds Ū (`current_u_bar :1060`), rho (`extractor_reliability :1061` unless `rho_override`), posterior (`lookup_posterior :1063`), decides `:1069`; ◆ host sorts candidates by weight for render `:1074-1076` (`p_none = weights[-1] :1077`) | observations, indeterminate, n_hits, time_indexed, brain, decisions_path, run_id, rho_override | `LookupResult :354`; **writes** the §18.9 answer artifact `D.record :1110` (key `:1099`, params `:1088-1097`) and the decision `DEC.append :1124-1138` (`decision_id = akey.cache_key :1138`) | `LK.lookup_answer :1171`; `core/gather.py:171` |
| `LK.lookup_answer` | `:1142` | route → observe → decide; ◆ short-circuits: route `None` ⇒ `None` `:1162-1163`; zero observations ⇒ `None` `:1169-1170` (both "narrative answers"); ◆ `effective_ti = route.time_indexed and scope not in ("historical","as_of") :1164` | question, hits, scope, covariates | `LookupResult` or `None` | `ASK.answer :817`; `core/gather.py:129` |
| `NR.include_eu` | `core/narrative.py:297` | reference formula / test oracle — "not on the decision path" `:306` | `p, u_bar` | float | tests |
| `NR._include_fn` / `_claim_pref` | `:310` / `:323` | the integrated include-EU as a `linear_combination` `:317-320`; `{include, withhold}` preference `:326-329` — "the engine picks — the body never compares EUs" `:325` | `u_bar, tf` | wire specs | `decide_claims :371-372` |
| **`NR.decide_claims`** | `:346` | per claim `SEAM.commit(SkinOptimise) :369-371`; ◆ host rules after the per-claim optimise: `report` iff any claim included `:385`, else `abstain` with `REASON_ALL_WITHHELD :384` / `REASON_NO_CLAIMS :382`; ◆ claims sorted by credence `:379`; `credence = brain.mean(sid)*tf :373` (a host multiply on a belief readout, disclosed as display-only) | `brain`, `scored=[(text,cites,cell,as_of,tf)]`, `cells_ab`, `u_bar` | `(claims, action, eu, reason)`; `eu = Σ eu_include` over included `:385` | `narrative_answer :484` |
| **`NR.narrative_answer`** | `:447` | audit cells `:476` (`audit_cell :179` — ◆ a deterministic three-way classifier `:185-191`), `tf = scope_decay_factor :482`, decide `:484`, coverage `:485` | question, text, cards, scope, u_bar/fold (else `LK.current_u_bar :464`), outcomes/decisions paths | `NarrativeResult :137`; **writes** `D.record :510` (key `:498`) and `DEC.append :519-538` | `BR._narrative :874`; `ASK._narrative_scored :842→` (called at `ASK:838`) |
| `NR.record_owner_verdicts` | `:283` | owner verdicts → `eval_claim` outcomes (`owner_claim_outcomes :253`) | verdicts | appends `OUTCOMES_LOG` | `scripts/verdict.py:173` |
| `BR._log_decision` | `bridge/server.py:765` | the executor's terminal decision → the same `DecisionEvent` shape as `LK`; ◆ rejects `gather` `:778-781` (`_TERMINAL_ACTIONS :739`); ◆ sorts leader-first `:791-794`; mints `decision_id :742-752` (`ab-` namespace) | `question`, `retrieval_keys`, `decision{effector, credences, candidates, p_none, eu, n_obs, n_indeterminate, n_competing, instrument, cost_usd, latency_s, run_id}` | `DEC.append :820`; `membrane.submit_decision :823` (bind only) | `ASK._log_executor_decision :962`; `AC.answer :140` |
| `core/utility.py` | — | **no `optimise`**; `posterior :432` is the fold, `UtilityPosterior.u_bar :259` the posterior-mean utility every decider reads | model + evidence | in-memory posterior | `LK.current_u_bar :994`; `scripts/run_eval.py:1668`; `scripts/gate_splice.py:108`; `scripts/membrane/p3_gate.py:435`; `scripts/fairfight/loss_ledger.py:533` |

**1.2 The transform-selection decision (executor menu / probe scheduling / VOI).** r00 (b)
b.2 stands: the daemon prices `net_voi − cost` and arg-maxes (`EX:3-6`); the body enacts. The
host-side *choices around* that argmax, all in `core/executor.py`, are itemised in trace A (§3)
and §5 (E-1…E-13). Menu rows: `DEFAULT_TRANSFORMS :64-74` (two guards, three `voi` tiers with
`rho`/`cost`), `DELIBERATE_TRANSFORM :92-95` (appended by `menu_transforms :131-134`, re-priced
through `_conditioned_rho :166`); grow actuators `core/gather_outcomes.py:47-51` served by
`GET /grow_menu` (`BR:639`). `brain.value :296` still has no caller (transcript in 1.0).

**1.3 The adoption-gate decision.** r00 (b) b.3 stands (`core/gate.py`, verified: `MATERIALITY_DELTA=0.05 :73`,
`GATE_LEVEL=0.90 :76`, `DEFAULT_N_DRAWS=20000 :77`, `DEFAULT_SEED=8675309 :78`;
`ASSERT_ACTIONS :84`, `WITHHOLD_ACTIONS :85`; `PairedOutcome.censored :144-149`; interval
`deltas[int(0.05·n)]`/`deltas[min(int(0.95·n), n−1)]` `:352-353`). Callers as in 1.0.

**1.4 Membrane shadow verdicts and the live decider.** r00 (b) b.4 stands. Re-verified and
extended with the *choice sites* inside the package:

| Site | file:line | Kind | What it chooses |
|---|---|---|---|
| `SH.submit_decide` | `membrane/shadow.py:431` | shadow feed | enqueue-only; remembers the terminal-tick summary `:435-442` (`_is_terminal_effector :244` — everything but `gather` `:200`) |
| `SH.submit_decision` / `submit_gate` / `submit_reaction` | `:450` / `:464` / `:500` | shadow feed | bind / gate tick under `GATE_SUMMARY :210` / verdict → `y` via `session.verdict_y :508` (◆ `_VERDICT_Y` table `session.py:60-64` — a declared exclusion of hedge/ask_clarify/gather pairs) |
| `SH.decide_live` | `:474` | **live (M3)** | bounded wait `_LIVE_WAIT_S=10.0 :222`; `None` on any failure `:492-498` |
| `SH._tick_decide` / `_tick_gate` / `_tick_live` / `_tick_cat` / `_tick_verdict` | `:635` / `:655` / `:679` / `:722` / `:757` | worker | records `kind` = decide / gate / enact / cat / evidence; `_tick_live` applies `CO.map_action :698` and returns the mapped view `:720` |
| `session.decide` | `membrane/session.py:131` | engine tick | the engine's `act` grid value → affordance via `VALUE_TO_ACTION :145` (undeclared value raises `:149`) |
| `categorical.decide_categorical` / `run_categorical` | `membrane/categorical.py:249` / `:298` | engine episode (K+1) | one evidence tick per obs code then one decide tick `:263-273`; decode `value_to_action_cat :207` |
| `W.argmax_action` | `membrane/world.py:286` | ◆ **host argmax** (ties first-listed `:292`) | reads `eu_by_action :277` over `utility_by_action :214` — used by `scripts/membrane/report.py:1109,:1319`; not on the decision path |
| `W.respond_threshold` | `:295` | ◆ host threshold derivation | the p1 above which respond strictly wins `:310-320`; consumers `scripts/membrane/report.py:1089`, `scripts/membrane/p3_gate.py:420` |
| `CO.map_action` | `membrane/coarse.py:105` | ◆ **live rewrite of the daemon view** | agreement passes through `:112-113`; `abstain`/`ask` rewrite `:114-117`; `respond` → `_respond :69` (◆ **host MAP** `max(range, key=credences) :77`; no candidates ⇒ abstain `respond_no_value :75-76`); `gather` → `_gather :81` (◆ **cheapest unapplied `voi` row in menu order** `:85-89`; exhausted ⇒ ◆ **restricted host argmax** over `{abstain, ask, respond}` at the engine's p1 under `W.eu_by_action` `:90-102`, first-listed ties `:96`) |
| `CO.live_decide` | `:137` | ◆ short-circuit | any consult failure ⇒ `GATE_ENGINE_DOWN` abstain `:151-155`; transport bound `LIVE_TIMEOUT_S=20.0 :56` |
| `membrane/client.py` | `:47-165` | transport | no decision (`spawn :62`, `request :147`, `shutdown :162`); env `MEMBRANE_ENV :33`, `READ_TIMEOUT_ENV :34` duplicated from `config.py:116,:118` by design (`config.py:109-113`) |

Bridge exposure of the package: `POST /decide-support` `BR:673`, `/gate-support :695`,
`/decide-live :711` (`_POST :882-899`); construction `_build_membrane :993` (env-gated on
`config.membrane_command :1000-1002`; any start-up failure ⇒ disabled `:1021-1024`);
mirror wiring `core/shadow_mirror.py` (`mirror_decide :48`, `mirror_gate :69`,
`shadow_wrapped_post :82`, one-strike breaker `:94-101`, `MIRROR_TIMEOUT_S=2.0 :34`).

**1.5 The seam.** `core/seam.py:96 commit` — the ONE act seam. ◆ a declared gate pre-empts
everything: `if gates: return SeamDecision("abstain", …) :102-103` (`GATE_WEAK_RETRIEVAL :38`,
`GATE_EXECUTOR_DOWN :39`, `GATE_ENGINE_DOWN :42`); `SkinOptimise` → `brain.optimise :105-108`;
`DaemonDecide` → `POST {daemon}/decide` (`seam.py:109`; + optional `live` consult `:111-116`). Full act
surface, verbatim:

```
$ grep -rn "SEAM.commit(" src scripts --include=*.py | grep -v __pycache__
src/life_agent/core/narrative.py:369:            action = SEAM.commit(SEAM.SkinOptimise(
src/life_agent/core/lookup.py:907:    dec = SEAM.commit(SEAM.SkinOptimise(brain=brain, state_id=state_id,
src/life_agent/core/executor.py:470:        dec = SEAM.commit(SEAM.DaemonDecide(post=post, daemon=daemon, payload=payload,
scripts/ask.py:778:        gated = SEAM.commit(None, gates=(SEAM.GATE_WEAK_RETRIEVAL,))
scripts/ask.py:1008:        gated = SEAM.commit(None, gates=(SEAM.GATE_EXECUTOR_DOWN,))
```

**1.6 Entry points the candidate list omits (verified present).** `LK.decide :894` /
`decide_and_record :1041` / `lookup_answer :1142`; `NR.decide_claims :346` /
`narrative_answer :447`; `core/gather.py:103 gather_answer` (a second lookup driver — ◆ forks
on `owner_scoped :128` to the single-pass path; ◆ host-ranks gather targets by posterior
weight `_top_candidates :71-83`; ◆ flips `time_indexed` on `era_split :164-166`);
`SEAM.commit :96`; `BR._log_decision :765`; the membrane rows in 1.4; and `ASK.answer :647` /
`answer_via_executor :985` / `ask_once :1229` (the host that declares the gates and dispatches
paths — §3 trace B). `core/ask_client.py:110 answer` is the reach surface's copy of
`answer_via_executor` (duplication D-9).

### 2. Belief-adjacent modules

"Wire" = conditioning/reads through `core/brain.py` (`create_state`/`condition`/`read_params`/
`mean`/`expect`/`marginal`); "host" = pure Python arithmetic. r00 (c) rows are cited, not
re-derived.

| Module | What it computes | Store folded / r00 (c) | Wire or host | Consumers |
|---|---|---|---|---|
| `core/calibration.py` | per-edge **reliability curves**: `fit_reliability_curve :82` (per-bin Beta posterior **mean** `(α+n_c)/(α+β+n_c+n_w)` `:98`, then PAV monotone `_pav :53`), `fit_edge_curves :105`, `curve_for :118` (cold-start prior `Beta(1,3)` `:82-83,:118-119`), `ReliabilityCurve.calibrate :76` (bin lookup `_bin_index :49`) | `OUTCOMES_LOG` `eval_edge` rows via `edge_outcomes_from_log :126` — r00 (c) **#10** (latest-per-lineage in place `:163-172`), **#11** (the curves) | **host** — a closed-form Beta-mean + isotonic fit; no `brain` call anywhere in the module | `EX._conditioned_rho :187` (`curve_for(...).calibrate`), `EX.menu_transforms :128,:132`; curves built by `ASK._edge_curves :928-946` (◆ `None` when the fold has no rows `:941-942`), `AC._menu :99-107`; `scripts/regrade_edge_rows.py:33-53` mirrors the supersession rule (r00 (c) #23) |
| `core/outcomes.py` | the outcomes **log** (`OutcomeEvent :98`, closed `GRADERS :42` / `CORRECT_GRADES :80`, `append :149`, `read :154`) and **host scoring summaries**: `log_score :165` (clamped `SCORE_EPS=1e-6 :38`), `brier_score :174`, `summarize_scores :188`, `reliability_bins :208`, `ece :230`, `scored_pairs :250` | `OUTCOMES_LOG` (`config.py:79`) — r00 (c) **#26** (bins/ece), **#18** (writers in `run_eval`) | **host** (pure summaries; none feed a decision) | log: `LK._extractor_outcomes :479`, `NR._cell_observations :202`, `coverage_posterior :239`, `calibration :157`; scoring: `scripts/run_eval.py:244-246` (`scored_pairs`, `summarize_scores`), `scripts/fairfight/run_fairfight.py:493` (`brier_score`), `:835` (`ece`) |
| `core/gather_outcomes.py` | the grow menu as data (`GROW_ACTUATORS :47-51`: `retrieve_rerank`/`retrieve_expand`/`re_extract_strong` with `cost`, cold `Beta(α0,β0)`), the sensor vocabulary `SENSOR_FEATURES :37-41`, `sensors_from :54` (◆ buckets `p_none`: `hi` iff `p_none ≥ leader`, `lo` iff `< 0.2`, else `mid` `:59-63`), `append_outcome :76`, `warm_counts :87` (per-context `(n1,n0)`), `grow_block :111` | `GATHER_OUTCOMES_LOG` (`config.py:97`) — r00 (c) **#19** | **host** (counts only; the structure-BMA `g` lives daemon-side, `:3-6`) | `BR._grow_menu :644`, `BR._log_gather :654-666`; `EX:386,:621` (`sensors_from`); daemon reads the block via `/decide` payload `EX:463-465` |
| `core/volatility.py` | the per-construct **half-life** prior: `half_life :45` over `_SEED :29-42` (◆ first-match keyword order `:52-54`, `DEFAULT=5.0 :23`, `PERMANENT=9999.0 :22`) | none (a world-knowledge table; "never reaches the credence brain" `:15-16`) | **host** | `BR._route :189` (◆ `time_indexed = half_life < PERMANENT` — the router's `time_indexed` verdict is overridden), `BR._extract :219`, `BR._source_time_factor :317`, `BR:472` (confirm), `NR.scope_decay :434` |
| `core/utility.py` | the **utility posterior** P(U): `posterior :432` (components `_components :311`; `_fold_1d :339` = `truncated_gaussian` + `condition` per event; `_fold_joint :393` = `truncated_mv_gaussian` + `marginal`), `UtilityPosterior.u_bar :259` (posterior means + `GAUGE :52`), `LatentPosterior.near_bound :243` (◆ 1σ support-edge monitor `:249`), `fold_version :275`; `load_model :116` (gauge check `:120-122`, `REQUIRED_LATENTS :64-65`) | `UTILITY_MODEL` + `UTILITY_ELICITATIONS` (`config.py:103-104`) + reactions — r00 (c) **#7**, **#8** | **wire** (every condition/mean/expect/marginal is a brain call `:346-357,:403-424`; the only host arithmetic is the sampler for the *offline* gate `GATE._sample_u :190`, which reads `mean`/`variance`/`lo`/`hi`) | `LK.current_u_bar :981-998` (memoised on `fold_version :991-993`, r00 (c) #9) → every `u_bar` reader (`LK.action_utilities`, `NR._include_fn`, `EX:428` via `GET /utility` `BR:635`, `W.utility_by_action` via `SH._u_bar`); `GATE.delta_posterior :326`; scripts as in 1.1 |
| `core/lookup.py` (belief half) | the **rho reliability latent**: `extractor_reliability :503` (`Beta(4,4)` prior `:190-191` conditioned per graded outcome `_extractor_rho_state :492-500`, read back `read_params :513`), `extractor_reliability_mean :519` (wire `mean :527`); the **V posterior**: `lookup_posterior :821` (`reliability_categorical` state `:838-842`, one `group_noisy_channel` condition per document `:848-860`, weights `_v_marginal :813`); the evidence **shaper**: `observe_hits :572` (◆ grounding gate `_grounded :439` applied `:621-625`; covariates `subject_factor :298`, `time_factor :312`, `authority_for :451`, `competition_factor :213`), `dedup_correlated :778` (◆ collapse rule `:797-806`, max-covariate witness `:807-809`), `candidates_from :759` (`_candidate_key :394`, ◆ `_CANON_MIN_DIGITS=5 :201`), `era_split :412` (◆ span `> years` `:436`) | `OUTCOMES_LOG` (`_extractor_outcomes :472-489` filters `extract_prompt_hash :480`, `audit`/`eval_lookup` graders `:483-488`) — not in the r00 (c) table (a wire fold, not a stored projection); Ū memo r00 (c) **#9** | **wire** for rho and V (`brain.condition :499,:860`); **host** for the shaper's covariates and dedup | `decide_and_record :1061-1063`; `BR._extract :221-236` (`observe_hits`, `extractor_reliability_mean` for the daemon's scalar `rho`), `BR._probe_confirm :444→` (dormant); `core/gather.py:133-140,:159` |
| `core/reactions.py` | the reaction **log** (`ReactionEvent :75`, `KINDS :59`, `VALENCES :60`) and the **verdict → utility-evidence producer** `load_reactions :176` (◆ latest per `(decision_id, kind)` `:185-187`; ◆ only `chosen_action == "abstain"` folds `:194`; lookup ⇒ `Reaction` at threshold `_abstain_threshold :122` = `p/(1−p)` of `creds[0]` `:139-147`; narrative ⇒ `MarginReaction` iff `ALL_WITHHELD` `:157` with `marginal_credence` `:159-164`, ◆ `bad` rows coverage-gated at `_COVERAGE_BAR=0.5 :71,:165-168` using host `_coverage_mean = a/(a+b) :128-134`) | `REACTIONS_LOG` ⋈ `DECISIONS_LOG` — r00 (c) **#12** | **host** (the join, supersession, thresholds and the coverage mean are Python; the *evidence* it emits is then wire-conditioned by `utility.posterior`) | `LK.current_u_bar :990`; writers `BR._log_reaction :843`, `ASK.submit_reaction :1130→` (`_record_reaction :1162`) |
| `core/narrative.py` (belief half) | per-cell **population posteriors** `population_posteriors :212` (`_CELL_PRIORS :78-83` conditioned over the wire `:222-226`) and the **coverage posterior** `coverage_posterior :232` (`_COVERAGE_PRIOR :86`); the tally `_cell_observations :196` (filters `instrument_identity :153` `:203`, closed cells `:206-207`) | `OUTCOMES_LOG` `eval_claim` / `eval_coverage` — r00 (c) **#14**, **#15** | **wire** (`brain.condition`/`read_params`; the only host arithmetic is `render`'s `a/(a+b)` display `:413` and `reactions._coverage_mean`) | `narrative_answer :473,:485` |
| `core/gate.py` (belief half) | the **Δ posterior** over `EU(typed) − EU(mono)`: MC over `_sample_u` × `_dirichlet_ones` `:336-347` | paired rows (in memory; `paired.jsonl` written by `run_eval`) — r00 (c) **#16**, **#17** | **host** | as in 1.0 |
| `core/claude_verdicts.py` (not on the brief's list; adjacent) | Claude verdict log; `y :100` (the `correct` bit); `latest_by_decision :137` | `CLAUDE_VERDICTS_LOG` (`config.py:93`) — r00 (c) **#13**; feeds the membrane only (`config.py:90-92`) | host | `SH.boot_snapshot :1121-1127` (◆ owner precedence by source `:1125-1127`) |

Consumers of Ū outside `core/`: `scripts/run_eval.py:1663-1668`, `scripts/gate_splice.py:106-114`,
`scripts/membrane/p3_gate.py:433-435`, `scripts/fairfight/loss_ledger.py:531-533` — every one
rebuilds the posterior from `load_model` + `load_elicitations` **without** `load_reactions`
(the reactions join enters only through `LK.current_u_bar :990`) — see D-8.

### 3. Call graphs

Format: trigger → functions → argmax site → effect. ◆ = a host-side choice among alternatives
(numbered into §5 as E-n / A-n / L-n / N-n / M-n / R-n).

**Trace A — Telegram question (reach) → executor → enacted answer.**

```
Telegram message (owner id)                       reach/jarvis.py:251-275 poll_loop
└─ verdict_valence(text) → LAST_DECISION_ID?      jarvis:266-267   ◆ R-1 bare g/b short-circuits the NLU
└─ parse_intent → handle_action "question"        jarvis:222-234
   └─ ask_client.answer(q)                        core/ask_client.py:110
      ├─ AC._ready() both /ready                  AC:81-88, AC:118  ◆ A-1 down stack ⇒ DOWN string, no seam call
      ├─ live | shadow_wrapped_post               AC:125-130   (config.membrane_live)
      ├─ AC._menu(): CAL.edge_outcomes_from_log →
      │  CAL.fit_edge_curves | None → EX.menu_transforms   AC:91-107  ◆ A-2 curves None ⇒ declared constants (menu rho)
      └─ EX.decide_via_loop                       core/executor.py:222
         ├─ POST {bridge}/route                   EX:251  → BR._route :176 → LK.route_question :538
         │                                          ◆ E-1 route None ⇒ narrative branch EX:252-258
         │                                          ◆ BR-1 time_indexed := VOL.half_life(construct) < PERMANENT  BR:189
         ├─ [grow_lane]  run_pass(grow_lane=True) EX:259-262
         ├─ run_pass(rerank=False)                EX:263-265
         │  ├─ _evidence: /retrieve, /probe/subject, /probe/recency, /extract   EX:316-334
         │  │     BR._extract :214 → LK.observe_hits :572 (◆ L-1 grounding gate :621-625; ◆ L-2 dedup_correlated :660)
         │  │     → rho = LK.extractor_reliability_mean BR:236 (wire); era_split BR:231
         │  ├─ ◆ E-2 k=0 walk: no candidates ∧ grow_lane ⇒ walk menu["actuators"] IN MENU ORDER EX:374-419
         │  │        (rescue rho ◆ E-3 min(_RESCUE_RHO, conf) EX:411-414)
         │  ├─ ◆ E-4 no candidates ⇒ effector "miss", no /decide EX:420-427
         │  ├─ u_bar = GET /utility EX:428 → BR._utility :635 → LK.current_u_bar (r00 (c) #9)
         │  ├─ ◆ E-5 rate = u_bar.get("lambda_usd", 1.0); costs re-priced USD→gauge EX:434-440
         │  ├─ _decide → SEAM.commit(DaemonDecide) EX:457-473 → POST {daemon}/decide  ═══ ARGMAX (credence daemon, out of tree)
         │  │     [live] request.live → CO.live_decide.consult → POST /decide-live → BR._decide_live :711
         │  │           → SH.decide_live :474 → worker _tick_live :679 → session.decide :131 (proplang engine ═══ ARGMAX)
         │  │           → CO.map_action :105 (◆ M-1 agreement pass-through :112; ◆ M-2 respond ⇒ host MAP :77;
         │  │             ◆ M-3 gather ⇒ cheapest unapplied voi in menu order :86-89; ◆ M-4 exhausted ⇒ restricted
         │  │             host argmax at engine p1 :90-102); consult failure ⇒ ◆ M-5 GATE_ENGINE_DOWN abstain CO:151-155
         │  ├─ enact loop, bounded ◆ E-6 (2 + #voi + 2·#grow iterations) EX:491
         │  │  ├─ gather/recency ⇒ acknowledge, re-decide            EX:493-496
         │  │  ├─ gather/corroborate_* ⇒ /probe/corroborate           EX:497-519
         │  │  │     BR._probe_corroborate :331 → JE.extract_joint :350; join ◆ BR-2 exact norm | unique containment
         │  │  │     w/o competing shape | allow_new mint | else NO observation BR:353-386; time factor via
         │  │  │     BR._source_time_factor :305 (◆ BR-3 max doc_date of value-carrying hits, else as_of, else None)
         │  │  │     ◆ E-7 the re-read REPLACES the channel (obs := cr["observations"]) EX:515; rho via
         │  │  │     EX._conditioned_rho (◆ E-8 curves None|edge unseen ⇒ declared fallback; absent conf ⇒ bin 0) EX:166-187
         │  │  │     ◆ E-9 _TIER_MODEL.get(probe, "claude-opus-4-8") / _TIER_RHO.get(probe, _GATHER_RHO) EX:501-502
         │  │  ├─ gather/retrieve_rerank|expand ⇒ _evidence at (rr,ex) EX:520-535  ◆ E-10 adopt iff it grounded candidates EX:526-531
         │  │  ├─ gather/deliberate ⇒ /probe/deliberate            EX:536-588
         │  │  │     BR._probe_deliberate :574 → D.lookup warm | DL.answer BR:612 (subprocess claude -p, retry ◆ DL-1 DL:308,
         │  │  │     blind-decline ⇒ error ◆ DL-2 DL:331-336) → DL.record_answer BR:615 → BR._join_deliberate_value :537 (same rule as BR-2)
         │  │  │     ◆ E-11 infrastructure failure ⇒ channel kept, probe retired EX:558-560; ok ⇒ REPLACES channel EX:585;
         │  │  │     legacy rho min(_DELIBERATE_FALLBACK_RHO, conf) EX:583-584
         │  │  ├─ gather/re_extract_strong ⇒ /probe/corroborate(allow_new) EX:589-614  (◆ E-7 unconditional replace EX:605-608)
         │  │  ├─ ◆ E-12 withhold ∧ grow_lane ∧ unapplied grow ⇒ re-ask WITH grow block once EX:615-625
         │  │  └─ else break EX:626-627
         │  ├─ EX._log_outcomes → POST /log_gather per enacted grow EX:339-350 → BR._log_gather :647 → GO.append_outcome BR:664
         │  └─ View EX:630-638
         ├─ [legacy lane, grow ∧ ¬rerank] ◆ E-13 grow cascade ((True,False),(True,True)) EX:278-294 while effector ∈ _WITHHOLD ∧
         │     EX._truth_likely_missing (◆ E-14 p_none ≥ leader EX:190-205); adopt iff grown report ∨ no candidates EX:291-294
         └─ return view
      ├─ ◆ A-3 log iff route ∧ effector ∈ LOOKUP_ACTION_ORDER ∧ credences AC:137-138
      │     → POST /log_decision AC:140-149 → BR._log_decision :765 → DEC.append BR:820 (DECISIONS_LOG) → SH.submit_decision BR:823
      └─ EX.render_view :651 (◆ E-15 leader-first reorder EX:667-670; abstain reason by candidates EX:681-686)
   → telegram.send_message(reply + "Reply g/b…")   reach/jarvis.py:232-233, jarvis:275
```

Effects: bridge-side §18.9 records (route/extract/confirm/deliberate keys via `core/derivations`),
`gather_outcomes.jsonl`, `decisions.jsonl`, `shadow.jsonl` (if enabled), the Telegram reply.

**Trace B — ask-live (CLI) → executor or in-process families.**

```
bin/ask-live → scripts/ask.py main :1468
├─ ASK.parse_line :338 (◆ grammar kinds; /react handled without a corpus ASK:1507-1508)
├─ D.reconcile ASK:1519 ; ASK.ensure_gtd_fresh :1524 (◆ ASK.gtd_stale :1311 — stamp compare, r00 (c) #6)
├─ ASK.ask_once :1229
│  ├─ ◆ B-1 use_executor = executor ∧ _executor_ready() ASK:1242 (default executor; --legacy ASK:1482 forces in-process;
│  │     a down stack falls back to the in-process path, NAMED ASK:1243-1245)
│  ├─ [executor] ASK.answer_via_executor :985
│  │   ├─ ◆ B-2 ¬ready ⇒ SEAM.commit(gates=(GATE_EXECUTOR_DOWN,)) ASK:1003-1015 → SM.mirror_gate → EXECUTOR_DOWN string
│  │   ├─ live | shadow_wrapped_post ASK:1020-1029 ; ◆ B-3 deliberate_enabled ⇒ _edge_curves + menu_transforms ASK:1034-1038
│  │   ├─ EX.decide_via_loop ASK:1039  (= trace A from run_pass on)
│  │   ├─ ASK._log_executor_decision ASK:1044 (◆ A-3 same filter ASK:958-960; posts instrument/cost/latency ASK:975-977) → /log_decision
│  │   └─ EX.render_view ASK:1048
│  └─ [in-process] ASK.answer :647
│      ├─ TI.intent_verdict ASK:698 ; expand ASK:701 ; retrieve (cached) ASK:711-734 ; temporal filter ASK:744-747 ; subject filter ASK:756-759
│      ├─ ◆ B-4 retrieval_is_weak(scores, WEAK_SCORE_FLOOR, MIN_STRONG_HITS) ∧ ¬profile ⇒
│      │     SEAM.commit(gates=(GATE_WEAK_RETRIEVAL,)) ASK:777-784 → SM.mirror_gate ASK:782 → ABSTENTION string
│      ├─ ◆ B-5 families ∧ root ⇒ [gather] GA.gather_answer ASK:802 | LK.lookup_answer ASK:817 (covariates ASK:809-816, scope ASK:818)
│      │     GA.gather_answer core/gather.py:103 (◆ GA-1 ¬owner_scoped ⇒ single-pass GA:128-131; ◆ GA-2 targets by weight GA:71-83;
│      │       ◆ GA-3 era_split flips time_indexed GA:164-166) → LK.decide_and_record GA:171
│      │     LK.lookup_answer :1142 → LK.observe_hits LK:1165 → LK.decide_and_record :1041
│      │       → LK.lookup_posterior LK:1063 (wire) → LK._scoped_option LK:1065 (◆ L-3 freshest dated obs LK:1020) → LK.decide LK:1069
│      │         → SEAM.commit(SkinOptimise) LK:907 → brain.optimise SEAM:106 ═══ ARGMAX (credence skin)
│      │       → D.record LK:1110 ; DEC.append LK:1124 ; LK.render :918
│      │     ◆ B-6 _typed_lookup_applies(lk) ASK:822 ⇒ return lk.rendered ; else fall through
│      ├─ SYN.synthesize ASK:831 ; ◆ B-7 ¬families ⇒ raw prose (the monolithic instrument) ASK:836-837
│      └─ ASK._narrative_scored :838 → NR.narrative_answer :447
│            → NR.parse_claims NR:472 ; NR.audit_cell NR:476 (◆ N-1 three-way classifier NR:185-191) ; NR.scope_decay_factor NR:482
│            → NR.population_posteriors NR:473 (wire) → NR.decide_claims NR:484
│              → per claim SEAM.commit(SkinOptimise) NR:369 → brain.optimise ═══ ARGMAX (credence skin, per claim)
│              → ◆ N-2 report iff any included; else abstain(reason) NR:381-385 ; ◆ N-3 sort by credence NR:379
│            → NR.coverage_posterior NR:485 (wire) → D.record NR:510 ; DEC.append NR:519 ; NR.render :390
│  ├─ guard.audit ASK:1254 ; ASK.render :1259 ; ASK.capture :1260 (dogfood log)
│  └─ derive targets returned for /derive ASK:1261
└─ ASK.repl :1402 (same per line) | one-shot
```

**Trace C — the adoption gate (offline, human-read effect).**

```
uv run scripts/run_eval.py --gate … (owner)
├─ per question: typed arm = ask.answer_via_executor run_eval:971 (trace A) | ask.answer(gather=True) run_eval:982 (trace B);
│   mono arm = replay row | ask.answer(families=False) run_eval:986-989 ; PairedOutcome run_eval:991-992
│   withheld reason ◆ C-1 unavailable ≻ miss ≻ dispersed run_eval:599-603
├─ UT.posterior(brain, model, elicitations) run_eval:1663-1668  (◆ C-2 no reactions in the gate's fold — see D-8)
├─ GATE.delta_posterior run_eval:1672  → GATE._diagnostics :327 ; MC GATE:336-347 ; ◆ G-1 passed = p_gt >= level GATE:349  ═══ VERDICT (host threshold)
└─ report.md run_eval:1679 ; paired.jsonl run_eval:1682  → the owner adopts/rejects by reading (no automatic enactment)
```

**Trace D — the reaction loop (owner verdict → utility evidence → next decide).**

```
Telegram "g"/"b" → jarvis:266-270 → AC.react :156 → POST /log_reaction → BR._log_reaction :827
   ├─ ◆ D-1 valence ∈ {good,bad} BR:837 ; decision by id (latest row) BR:839-842 ; RX.append BR:843 ; SH.submit_reaction BR:846-848
   └─ "folds" iff chosen_action == "abstain" BR:849 (an echo of reactions.py:194)
(or ask-live "/react" → ASK.react :1183 → ASK.submit_reaction :1130 → RX.append)
Next decide: LK.current_u_bar :981 → R.load_reactions LK:990 (◆ R-2 latest per (decision_id,kind) RX:185-187;
   ◆ R-3 abstain-only RX:194; ◆ R-4 lookup threshold p/(1−p) of creds[0] RX:139-147; ◆ R-5 narrative ALL_WITHHELD ∧
   marginal_credence ∧ (good | coverage ≥ 0.5) RX:157-168) → UT.fold_version LK:991 → memo hit? LK:992 → UT.posterior LK:994 (wire)
   → u_bar → LK.action_utilities / NR._include_fn / EX via GET /utility
```

**Trace E — the membrane shadow (off the path; records only).**

```
executor /decide tick → SM.shadow_wrapped_post SM:96-101 → SM.mirror_decide :48 → POST /decide-support → BR._decide_support :673
   → SH.submit_decide :431 → queue → SH._tick_decide :635 → session.decide :131 (engine) → shadow.jsonl "decide"
   [+ SH._tick_cat :722 → categorical.run_categorical :298 → "cat"] ; gates → /gate-support → SH._tick_gate :655 → "gate"
   verdicts → SH.submit_reaction :500 → verdict_y SH:508 → SH._tick_verdict :757 → engine evidence tick
boot: SH.boot_snapshot :1064 (decisions ⋈ reactions ⋈ claude_verdicts; ◆ M-6 owner-routable verdict overrules Claude SH:1125-1127)
```

**Trace F — timers.** `bin/mail-to-tasks:20` (systemd `--user` timer, per CLAUDE.md) runs
`scripts/mail_to_tasks.py` → `tasks/project.py` (`scripts/mail_to_tasks.py:31`), which reads
only `config.PKM_CONFIG`/`GTD_DB_PATH` from `life_agent.core` (`scripts/mail_to_tasks.py:50,:95`) and touches none of
the decision modules; no timer invokes a decision entry point. `packaging/daily-digest.timer` →
`bin/daily-digest` (`packaging/daily-digest.service:16`) → `reach/digest.py` (read-model
only). Verified: `grep -rn "executor\|lookup_answer\|narrative_answer\|delta_posterior" bin packaging`
→ exit 1 (no hits).

### 4. The duplication table

Pairs/clusters computing overlapping quantities or making overlapping choices. Evidence and a
one-line statement of the overlap; no resolution proposed.

| # | Cluster | Evidence (file:line) | Overlap |
|---|---|---|---|
| D-1 | **Utility-of-action written four times** | `core/decide.py:60 u_assert`; `LK.action_utilities :864-887`; `GATE.realised_utility :163-185`; `W.utility_by_action :214-245` (with its own defaults `u_wrong=-9.0`, `lambda_int=0.1`, `kappa_att=0.02` `:237-239` and a *different* pricing of `gather`/`ask` — "myopic perfect information" `:226-234`) | four spellings of "what an action is worth under `u_bar`": the atom, the online lookup vectors, the offline realised-answer model, and the membrane's world sentence — the last two do not derive from `u_assert` |
| D-2 | **Reliability summaries, four estimators** | `LK.extractor_reliability :503` (wire Beta(4,4) → `read_params`); `NR.population_posteriors :212` (wire Beta per cell); `CAL.fit_reliability_curve :82-102` (host Beta(1,3) per bin + PAV); `O.reliability_bins :208` / `ece :230` (host summaries) | four "how reliable is this instrument" folds over the same `OUTCOMES_LOG`, two through the brain, two host-side; `calibration.py` alone conditions with `a += n` (`:98`) — the pattern `lookup.py:496`/`narrative.py:89-90` call "the discretisation antipattern / never a host `a += 1`" |
| D-3 | **Threshold gates beside EU comparisons on the same axis** | `EX._truth_likely_missing :205` (`p_none ≥ leader`) and `GO.sensors_from :63` (`p_none ≥ leader` ⇒ `hi`, `< 0.2` ⇒ `lo`) vs the daemon's priced grow (`EX:232-238`); `ASK.retrieval_is_weak :630-633` (score floor) vs the response optimise; `GATE:349` (`p_gt ≥ level`) vs the EU gap it summarises; `RX._COVERAGE_BAR :71` vs the coverage posterior it gates | the same quantity is compared to a fixed number in host code and priced by the engine elsewhere (`GO:9-11` states the bucketing is meant to *replace* the threshold "never control flow", while `EX:190-205` still uses it as control flow on the legacy lane) |
| D-4 | **The MAP candidate picked in three places** | engine `report_j` `LK:869,:882` (the sanctioned one); host `max(range, key=credences)` `CO._respond :77`; host `sorted(..., reverse=True)[0]` for render/log `LK:1074-1076`, `EX.render_view :667-670`, `BR._log_decision :791-794`, `W.summary_from_payload :97` (`max(credences)`) | one is a decision (coarse live), the rest are labels — but they are the same argmax written five ways |
| D-5 | **Withhold-reason derivation duplicated** | `LK.render :944-949` (`REASON_DISPERSED` iff candidates else `REASON_NO_OBSERVATIONS`); `EX.render_view :681-686` ("Mirrors lookup.render"); `scripts/run_eval.py:599-603` (`unavailable ≻ miss ≻ dispersed`); `GATE.WITHHELD_* :95-99` | the classification of *why* a withhold withheld is re-derived per surface from the same view fields |
| D-6 | **The action vocabulary restated per layer** | `DEC.ACTIONS :41`, `LOOKUP_ACTION_ORDER :52`, `NARRATIVE_ACTION_ORDER :54`; `GATE.ASSERT_ACTIONS/WITHHOLD_ACTIONS :84-85` (`_ALL_ACTIONS :86`); `EX._WITHHOLD :139` (adds `miss`); `BR._TERMINAL_ACTIONS :739`; `W.AFFORDANCES :35` + `REAL_TO_MEMBRANE :56-61` (adds `gather`, `miss`); `CO._ENACT_EFFECTOR :60`; `session._VERDICT_Y :60-64`; `categorical._INFO_ACTS :46` | six partitions of one action space, drift-gated in tests per `DEC:49-51` but each a separate literal |
| D-7 | **Menu / price tables in two modules** | `EX.DEFAULT_TRANSFORMS :64-74` + `DELIBERATE_TRANSFORM :92-95` (`rho`, `cost` in USD) and `GO.GROW_ACTUATORS :47-51` (`cost`, cold Beta); both re-priced by `EX:434-440`; the tier `rho`s restated in `_TIER_RHO :56` and `DEFAULT_TRANSFORMS` | two menus, one daemon; the corroborate rho appears in both `_TIER_RHO` and the row |
| D-8 | **Ū folded with and without reactions** | `LK.current_u_bar :985-994` folds elicitations + `load_reactions`; `scripts/run_eval.py:1663-1668`, `gate_splice.py:106-108`, `membrane/p3_gate.py:433-435`, `fairfight/loss_ledger.py:531-533` fold elicitations only | the online decider and the offline gate value actions under *different* posteriors once any reaction has folded |
| D-9 | **Two copies of the executor read-path driver** | `ASK.answer_via_executor :985-1048` and `AC.answer :110-153`; both call `_ready`, `membrane_live`, curves+menu, `decide_via_loop`, `/log_decision`, `render_view` — `AC.answer`'s `/log_decision` body `:143-149` omits `instrument`/`cost_usd`/`latency_s`/`run_id` that `ASK:975-979` posts | the reach surface and the CLI post the same decision with different field sets (§10 accounting present on one path only) |
| D-10 | **`/log_decision` poster filter duplicated** | `ASK._log_executor_decision :958-960` and `AC.answer :137-138` (`route ∧ effector ∈ LOOKUP_ACTION_ORDER ∧ credences`) | the same eligibility rule twice |
| D-11 | **Value-join rule duplicated** | `BR._probe_corroborate :353-386` and `BR._join_deliberate_value :537-571` (exact norm → unique containment w/o competing shape → `allow_new` mint → no observation) | the corroborate join and the deliberate join are the same rule in two bodies (`:541-544` says so) |
| D-12 | **Edge-name spellings** | `EX.extract_edge :102` (`extract@<model>`), `DL.instrument :196` (`deliberate@<model>`) | two constructors of the attribution namespace with the same shape |
| D-13 | **Env-name constants declared twice** | `config.py:116,:118` and `membrane/client.py:33-34` (deliberate, per `config.py:109-113`); bridge/daemon URLs + grow-lane flag read in `ASK:875-880` and `AC:31-33` | the same env keys read in two places each |
| D-14 | **Time-factor sources** | `LK.time_factor :312`; `BR._source_time_factor :305` (max doc_date over value-carrying hits, else self-reported `as_of`); `NR.scope_decay :420` (`LK.time_factor` at `VOL.half_life(claim_text)`) | three call shapes for the recency covariate — one function, three input-selection policies |
| D-15 | **Verdict → y mappings** | `session._VERDICT_Y :60-64` (owner valence + action → y); `claude_verdicts.y :100` (the `correct` bit); `RX._lookup_reaction :137` (valence → `reacted`) | three projections of a verdict into evidence, one per consumer |

### 5. The §16 gap list

Every mechanism that currently decides something *outside* an EU comparison — fixed thresholds,
priority orders, hardcoded short-circuits, host argmaxes — listed neutrally with lines. This is
raw material for tranche 2's Open Design Questions; nothing here is a defect claim. Grouped by
module; the ids match the ◆ marks in §3.

**Executor (`core/executor.py`)**
- E-1 route `None` ⇒ narrative branch, no `/decide` `:251-258`.
- E-2 k=0 walk in **menu order** (`menu["actuators"]`), stop at first grounding `:374-419` — "the one place enactment order is body-held" `:379`.
- E-3 rescue reliability `min(_RESCUE_RHO=0.5, conf)` `:163,:411-414`.
- E-4 no candidates ⇒ `"miss"`, daemon not consulted `:420-427`.
- E-5 spend exchange rate default `u_bar.get("lambda_usd", 1.0)` `:434`.
- E-6 the enact loop's iteration bound `2 + #voi + 2·#grow` `:491`.
- E-7 a re-read/deliberate **replaces** the grounded channel (`obs := cr["observations"]`) `:515`, `:585`, unconditional at `:605-608`.
- E-8 `_conditioned_rho`: `curves is None or edge not in curves` ⇒ declared fallback; absent confidence ⇒ `c = 0.0` (most pessimistic bin) `:184-187`.
- E-9 unknown corroborate probe name ⇒ opus tier / `_GATHER_RHO` `:501-502`.
- E-10 a daemon-scheduled retrieval grow is adopted **iff** it grounded candidates `:526-531`.
- E-11 deliberate infrastructure failure ⇒ channel kept, probe retired `:558-560`; ok-status test `:578`.
- E-12 withhold ∧ grow_lane ∧ unapplied grow ⇒ one grow re-ask `:615-625` (`grow_asked` latch).
- E-13 legacy grow cascade order `((True,False),(True,True))` and the adopt rule `grown report ∨ no candidates` `:278-294`.
- E-14 `_truth_likely_missing`: `p_none ≥ leader` (or no candidates) `:190-205` — the module calls it "no magic threshold" `:195` while it is a fixed comparison used as control flow.
- E-15 render reorder + abstain reason from `cands` `:667-686`.

**Lookup family (`core/lookup.py`)**
- L-1 grounding gate `_grounded` (quote OR value verbatim in chunk) `:439-448`, applied `:621-625` — the "error-model surgery" (`:8-10`).
- L-2 `dedup_correlated`: collapse iff same normalised quote spans >1 document AND the quote carries context beyond the value tokens; keep the max-covariate document `:797-809`.
- L-3 `_scoped_option`: V_s = freshest dated observation `:1020`; no dated obs ⇒ scoped disabled `:1018-1019`.
- L-4 candidate identity: date parse ⇒ ISO; ≥ `_CANON_MIN_DIGITS=5` digits ⇒ digit string; else casefold `:394-409`.
- L-5 `era_split`: `< 2` dated candidates ⇒ False; span `> years` `:433-436`.
- L-6 `time_factor`: future dates clamp to 1.0 (`max(days,0)`) `:325`; undated ⇒ `_A_TIME_UNKNOWN` `:322-323`; non-time-indexed ⇒ 1.0 `:320-321`.
- L-7 `subject_factor` partition table `:298-309` (raises outside it).
- L-8 `authority_for`: mail-path markers before extension classes; default `("other", 0.85)` `:451-459`.
- L-9 `lookup_answer` short-circuits (route None / zero obs ⇒ narrative) `:1162-1170`; `effective_ti` suppression for `historical`/`as_of` `:1164`.
- L-10 group covariate takes the group's **min** competition factor `:856`.
- L-11 `report_j → report` relabel `:911-912`.

**Narrative family (`core/narrative.py`)**
- N-1 `audit_cell` three-way classifier (`unverifiable` if no value spans or no cites; `verified` on any token-boundary containment; else `unsupported`) `:179-191`.
- N-2 answer action from the per-claim results: `report` iff any included, else `abstain` + reason `:381-385`.
- N-3 claims sorted by decayed credence `:379`; `credence = mean·tf` `:373`.
- N-4 `scope_decay`: applies only to `scope == "present"` and dated claims `:429-430`.
- N-5 `_cell_observations` raises on a cell outside the partition `:206-207` (closed vocabulary as a hard stop).

**Gate (`core/gate.py`)**
- G-1 the verdict is a posterior-mass threshold `passed = p_gt >= level` (δ `:73`, level `:76`) `:349`.
- G-2 `censored()` one-sided on the typed arm's `unavailable` `:144-149`, excluded from Δ `:328`; empty `included` ⇒ fail `:331-334`.
- G-3 `_sample_u` clamps a Gaussian moment sample to `[lo,hi]` `:196-200` (an offline approximation of the wire posterior).
- G-4 90 % interval by order statistics `:352-353`.

**Reactions / utility (`core/reactions.py`, `core/utility.py`)**
- R-2 supersession: latest per `(decision_id, kind)` `:185-187`.
- R-3 only `chosen_action == "abstain"` folds `:194`; report verdicts recorded-not-folded (`:16-20`).
- R-4 lookup threshold `p/(1−p)` of `creds[0]`, only for `0 ≤ p < 1` `:139-147`.
- R-5 narrative: `ALL_WITHHELD` only `:157`; `bad` rows need coverage mean `≥ _COVERAGE_BAR=0.5` `:71,:165-168` (host `a/(a+b)` `:134`).
- U-1 `near_bound` = within 1σ of a support edge `:243-249` (a monitor, prints only — `LK:995-996`).
- U-2 `_components` ordering "by model position of each component's earliest latent" `:332-336` (fold choreography, not a decision).

**Seam / hosts (`core/seam.py`, `scripts/ask.py`, `core/ask_client.py`)**
- S-1 a declared gate pre-empts any request: `if gates: abstain` `:102-103` (`GATE_WEAK_RETRIEVAL`, `GATE_EXECUTOR_DOWN`, `GATE_ENGINE_DOWN`).
- B-1 `use_executor = executor ∧ _executor_ready()` `ASK:1242`; `--legacy` `:1482`.
- B-2 executor down ⇒ gate ⇒ `EXECUTOR_DOWN` string `ASK:1003-1015`; A-1 the same in `AC:118-119` **without** the seam (returns `DOWN` directly).
- B-3 / A-2 `deliberate_enabled` ⇒ curves+menu, else `None` `ASK:1034-1038`, `AC:99-107`; `_edge_curves` returns `None` when the fold has no rows `ASK:941-942`, `AC:103`.
- B-4 `retrieval_is_weak(scores, WEAK_SCORE_FLOOR=4.0, MIN_STRONG_HITS=1) ∧ ¬profile` ⇒ gate `ASK:777-784`, predicate `:630-633`.
- B-5 `families ∧ root` ⇒ typed path; `gather` flag picks the driver `ASK:792-818`.
- B-6 `_typed_lookup_applies` = `lk is not None` `ASK:636-644`.
- B-7 `¬families` ⇒ raw prose (the monolithic instrument) `ASK:836-837`.
- A-3 log iff `route ∧ effector ∈ LOOKUP_ACTION_ORDER ∧ credences` `ASK:958-960`, `AC:137-138`.
- GA-1 / GA-2 / GA-3 (`core/gather.py`): `owner_scoped` fork `:128-131`; targets by posterior weight `:71-83`; `era_split` flips `time_indexed` `:164-166`.

**Bridge (`bridge/server.py`)**
- BR-1 `time_indexed := VOL.half_life(construct) < PERMANENT` overrides the route model's verdict `:189`.
- BR-2 the value-join rule (exact norm → unique containment without `_competing_value_shape` → `allow_new` mint at `len(candidates)` → no observation) `:353-386`, repeated `:550-564`.
- BR-3 `_source_time_factor`: max doc_date of value-carrying hits ≻ normalised self-reported `as_of` ≻ None `:305-324`; `_normalize_date_iso` partial date ⇒ earliest point `:282-302`.
- BR-4 `_probe_corroborate` default model/rho `_JOINT_MODEL`/`_JOINT_RHO` `:345-349`; the re-read's `authority=1.0`, `subject_factor=1.0` `:396-397`.
- BR-5 `_log_decision` rejects `gather` `:778-781`; leader-first sort `:791-794`; `run_id` default `"answer-brain"` `:802`.
- BR-6 `_log_reaction` valence check `:837`; "latest row" on id collision `:842`; `folds` echo `:849`.
- BR-7 `_deliberate_cfg` refuses a non-file `PKM_CONFIG` `:514-519`.
- BR-8 `_probe_deliberate`: warm hit ⇒ `cost_usd=0.0` `:606`; only `status=="ok"` recorded `:613-615`; non-ok ⇒ no observation `:622-623`.
- BR-9 `_build_membrane`: any start-up failure ⇒ disabled `:1021-1024`.

**Membrane (`membrane/`)**
- M-1 agreement pass-through `CO:112-113`; M-2 respond ⇒ host MAP `CO:73-78`; M-3 gather ⇒ cheapest unapplied `voi` row in **menu order** `CO:85-89`; M-4 exhausted ⇒ restricted host argmax over `{abstain, ask, respond}` at engine p1, first-listed ties `CO:90-102`; M-5 consult failure ⇒ `GATE_ENGINE_DOWN` `CO:151-155`.
- M-6 `boot_snapshot` owner precedence by source; Claude segment after owner segment `SH:1084-1085,:1121-1127`.
- M-7 `session._VERDICT_Y` declared exclusions `session.py:60-64`; `_is_terminal_effector = effector != "gather"` `SH:244-245`.
- M-8 `W.utility_by_action` prices `gather`/`ask` as myopic perfect information with fixed defaults `:235-245` ("FLAG — this OVERVALUES information, deliberately" `:228-234`); `W.argmax_action :286` and `respond_threshold :295` are host EU arithmetic (report-side).
- M-9 feature bucketing thresholds `W:141-174` (`_credence_bucket` 0.5/0.7/0.8/0.9; `_p_none_bucket` 0.2/0.5; obs `0/1-2/3+`); `GO.sensors_from` `p_none` buckets `:59-63`.
- M-10 wire tie rule "first-listed / wait first" encoded in grid order `W:19-22,:33-37`; `categorical.RESPOND_BASE=3.0 :49`.
- M-11 `ShadowConfig` sizing (`queue_size=1024`, `max_respawns=3`, `respawn_backoff_s=60.0`, `cat_timeout_s=20.0`) `SH:118-131`, restated `BR:82-84`; `_LIVE_WAIT_S=10.0 SH:222` vs `LIVE_TIMEOUT_S=20.0 CO:56` vs `MIRROR_TIMEOUT_S=2.0 shadow_mirror:34` (an ordering of timeouts, stated `CO:51-55`).

**Deliberate (`core/deliberate.py`)**
- DL-1 retry once `:308`; DL-2 blind decline (0 tool calls) ⇒ `status="error"` `:331-336`, refused again at `record_answer :380-383`; DL-3 credence outside `[0,1]` ⇒ no signal `:114`; DL-4 `_minimal_env` HOME+PATH `:231-234`.

**Probes / volatility / gather_outcomes**
- P-1 email-header date fills only email-produced dateless hits `probes.py:111-112`; P-2 `_VERDICT_TO_STATE` default `unclear` `:153`; P-3 `probe_corroborate` over-fetch `k*4`, max-score per chunk, top-`k` `:201-205`.
- V-1 `volatility.half_life` first-match keyword order `:52-54`, `DEFAULT=5.0`.
- GO-1 `sensors_from` buckets `:59-63`; GO-2 `warm_counts` `None` when no rows ⇒ daemon cold prior `:91,:105-106`.

Count: **85** listed mechanisms (E 15 · L 11 · N 5 · G 4 · R/U 6 · S/B/A/GA 14 · BR 9 · M 11 · DL 4 · P/V/GO 6; the two argmax sites proper — the credence daemon's `/decide` and `brain.optimise` — are *not* in the list, nor is `SEAM.commit`'s dispatch itself).

### 6. Config and constants

Every tunable each in-scope module reads: env, config file, or literal — value and location.
`$LIFE_AGENT_KB`-relative paths are named by their `config.py` symbol, never resolved.

**Environment variables (all reads in scope).**

| Env var | Read at | Default | Effect |
|---|---|---|---|
| `LIFE_AGENT_KB` | `core/config.py:14` | `~/.life-agent/kb` | root of every log below |
| `PKM_CONFIG` | `config.py:15`; `pkm_root :186-196` | `~/.config/life-agent/pkm.yaml` | catalogue root; refused as non-file by `BR._deliberate_cfg :514-519` |
| `GTD_DB_PATH`, `JARVIS_DB_PATH`, `TRIPS_LEDGER`, `TRIPS_DB_PATH`, `KITINERARY_EXTRACTOR`, `NOTMUCH_BINARY` | `config.py:25,:34,:42,:46,:49,:53` | KB-relative / system paths | out of the decision scope (listed for completeness of `config.py`) |
| `LIFE_AGENT_MEMBRANE_COMMAND` | `config.py:116,:146` (`membrane_command`); `membrane/client.py:33,:139` | unset | shadow enable switch (`BR:1000-1002`) |
| `LIFE_AGENT_MEMBRANE_UTILITY` | `config.py:117,:158` | `said@1` (`:127`) | forms; validated `SH:133-141` |
| `LIFE_AGENT_MEMBRANE_READ_TIMEOUT` | `config.py:118,:163`; `client.py:34,:144` | `300.0` (`:128`, `client.py:35`) | engine read timeout |
| `LIFE_AGENT_MEMBRANE_WARM_VECTORS` | `config.py:119,:211` | unset | boot warm-outcome dir |
| `LIFE_AGENT_MEMBRANE_LIVE` | `config.py:120,:171` | unset (`"1"` enables) | M3 live consult (`ASK:1020`, `AC:125`) |
| `LIFE_AGENT_MEMBRANE_CAT` | `config.py:121,:205` | unset | categorical mirror (`SH` `categorical`) |
| `LIFE_AGENT_DELIBERATE` | `config.py:122,:183` | on (`"0"` disables) | deliberate row + curves (`ASK:1034`, `AC:99`) |
| `LIFE_AGENT_FALLBACK_LANE` | — (retired, `config.py:123-125`) | ignored | none |
| `CREDENCE_SKIN_IMAGE` | `core/brain.py:44` | the pinned digest `:40-43` | skin image |
| `CREDENCE_REPO`, `CREDENCE_SKIN_SERVER` | `brain.py:54-55` | unset | dev-only local julia spawn `:176-183` |
| `LIFE_AGENT_BRIDGE_URL`, `ANSWER_BRAIN_URL` | `ASK:875-876`; `AC:31-32` | `http://127.0.0.1` ports 8798 / 8799 | executor transports |
| `LIFE_AGENT_GROW_LANE` | `ASK:880`; `AC:33` | off (`"1"` enables) | daemon-priced grow lane vs legacy cascade |
| `LIFE_AGENT_SCORE_FLOOR`, `LIFE_AGENT_MIN_HITS` | `ASK:85-86` | `4.0`, `1` | the weak-retrieval gate |
| `LIFE_AGENT_BRIDGE_HOST`, `LIFE_AGENT_BRIDGE_PORT` | `BR:72-73` | `127.0.0.1`, `8798` | bridge bind |
| `LIFE_AGENT_CLAUDE_BIN` | `BR:521` | `claude` | the deliberate CLI |
| `HOME`, `PATH` | `deliberate.py:234` | — | the only env the CLI child sees |
| (`bin/answer-brain`) `CREDENCE_DIR`, `ANSWER_BRAIN_PORT`, `OLLAMA_BASE_URL` | `bin/answer-brain:19-22` | a sibling `credence` checkout under the user's git dir, port 8799, a local model URL | daemon spawn (out of tree) |

**Config files (out of tree, by symbol).** `UTILITY_MODEL` (`config.py:103`; gauge + latent
priors, `utility.load_model :116`), `UTILITY_ELICITATIONS` (`:104`); logs `OUTCOMES_LOG :79`,
`DECISIONS_LOG :83`, `REACTIONS_LOG :87`, `CLAUDE_VERDICTS_LOG :93`, `GATHER_OUTCOMES_LOG :97`;
`membrane_shadow_log :136-139`; `DATA_SOURCES :60`. Schema example in tree:
`config/utility-model.example.yaml` (referenced `utility.py:33`, `config.py:101`).

**Literals, per module (name = value @ line).**

- `core/lookup.py`: `LOOKUP_MODEL = INSTR.INSTRUMENT_MODEL :63` (= `claude-haiku-4-5-20251001`, `core/instrument.py:22`); `_A_ALTERNATIVES=10.0 :181`; `_RHO_PRIOR_A=4.0 :190`, `_RHO_PRIOR_B=4.0 :191`; `_P_NONE_PRIOR=0.5 :195`; `_ORACLE_P=0.9 :196` (also the gate's `oracle_p` — `run_eval.py:1672`, `gate_splice.py:113`); `_PROB_EPS=1e-12 :197`; `_CANON_MIN_DIGITS=5 :201`; `_COMPETITION_CAP=1 :210`; `_AUTHORITY_CLASSES` (document 0.95 / email 0.90 / note 0.80) `:221-225`, `_AUTHORITY_MAIL_MARKERS :226`, `_AUTHORITY_DEFAULT=("other",0.85) :227`; `_A_SUBJECT_OTHER=0.05 :233`; `_P_OWNER_GIVEN_INDET=0.5 :234`; `_TIME_HALF_LIFE_YEARS=5.0 :235`; `_A_TIME_UNKNOWN=0.6 :236`; `REASON_* :248-250`; `GRAMMAR :255-273`; `_LOOKUP_ACTIONS :891`; `confirm_hits` `m=2 :681`.
- `core/narrative.py`: `_CELL_PRIORS` verified (3,2) / unsupported (1,3) / unverifiable (2,2) `:78-83`; `_COVERAGE_PRIOR=(2,2) :86`; `_BERNOULLI :91`; `REASON_* :99-100`; `GRAMMAR :103-112`; `_CLAIM_ACTIONS :333`.
- `core/executor.py`: `_TIER_MODEL :53-55`, `_TIER_RHO` 0.80/0.90/0.95 `:56`, `_GATHER_RHO=0.95 :57`; `DEFAULT_TRANSFORMS` (recency guard; corroborate_owner guard; tiers rho/cost 0.80/0.004, 0.90/0.012, 0.95/0.020) `:64-74`; `_DELIBERATE_MODEL :83`; `DELIBERATE_TRANSFORM` rho 0.92 / cost 0.38 `:92-95`; `_DELIBERATE_FALLBACK_RHO=0.5 :99`; `_WITHHOLD :139`; `_UNPRICED_ATTRIBUTION :144-147`; `_GROW_RETRIEVE :153`; `_RE_EXTRACT_MODEL :154`; `_RESCUE_RHO=0.5 :163`; loop bound `:491`; lambda default `1.0 :434`.
- `core/gate.py`: `MATERIALITY_DELTA=0.05 :73`; `GATE_LEVEL=0.90 :76`; `DEFAULT_N_DRAWS=20000 :77`; `DEFAULT_SEED=8675309 :78`; `ASSERT_ACTIONS/WITHHOLD_ACTIONS :84-85`; `WITHHELD_* :95-99`; interval quantiles 0.05/0.95 `:352-353`; spend default `u.get("lambda_usd", 0.0) :171`.
- `core/calibration.py`: `prior_alpha=1.0`, `prior_beta=3.0`, `n_bins=10` (defaults at `:82-83,:105-106,:118-119`).
- `core/outcomes.py`: `FORMAT_VERSION=1 :33`; `SCORE_EPS=1e-6 :38`; `GRADERS :42-76`; `CORRECT_GRADES :80-89`; `n_bins=10 :209,:230`.
- `core/gather_outcomes.py`: `SENSOR_FEATURES :37-41`; `GROW_ACTUATORS` (rerank 0.004 Beta(3,7); expand 0.006 Beta(3.5,6.5); re_extract_strong 0.020 Beta(4,6)) `:47-51`; `p_none` floor `0.2 :63`.
- `core/volatility.py`: `PERMANENT=9999.0 :22`; `DEFAULT=5.0 :23`; `_SEED` (birth ⇒ permanent; passport 10; national-id ⇒ permanent; email 10; phone 8; address 7; marital 15; visa 3; bank 8; employer 4; salary 2) `:29-42`.
- `core/utility.py`: `FORMAT_VERSION=1 :48`; `GAUGE = {u_correct: 1.0, u_abstain: 0.0} :52`; `REQUIRED_LATENTS :64-65` (`u_wrong`, `u_wrong_scoped`, `u_hedged`, `lambda_int`, `kappa_att`, `lambda_usd`); the priors themselves live in the model file (`:32-34`); `near_bound` 1σ `:249`.
- `core/reactions.py`: `FORMAT_VERSION=1 :55`; `KINDS :59`; `VALENCES :60`; `_FOLDED_VALENCES :64`; `_COVERAGE_BAR=0.5 :71`.
- `core/decisions.py`: `FORMAT_VERSION=2 :30`; `FAMILIES :34`; `ACTIONS :41-42`; `LOOKUP_ACTION_ORDER :52-53`; `NARRATIVE_ACTION_ORDER :54`; `QUESTION_ID_CHARS=16 :56`.
- `core/deliberate.py`: `_ALLOWED_TOOLS :40`; `PROMPT_DELIB_V2 :50-80` (frozen contract); `_CREDENCE_RE/_ANSWER_RE :83-84`; `DeliberateConfig` defaults `model="claude-opus-4-8"`, `timeout_s=240`, `max_turns=40` `:167-169`; retry count 2 `:308`; `--permission-mode default :305`.
- `core/pricing.py`: `PRICING_VERSION=1 :20`; `PRICE_TABLE` (opus 5/25/0.5/6.25; sonnet 3/15/0.3/3.75; haiku 1/5/0.1/1.25; gpt-5.1 1.25/10/0.125/1.25; `qwen` 0) `:33-44`.
- `core/brain.py`: `_SKIN_PINNED :40-43`; `PROTOCOL_MAJOR="1" :49`; `STARTUP_TIMEOUT=120.0 :59`; shutdown ladder waits 5/5/2 s `:144-153`.
- `core/seam.py`: `DECIDE_PATH="/decide" :35`; gate names `:38-42`.
- `core/probes.py`: `_EMAIL_PRODUCER="email" :66`; `_VERDICT_TO_STATE :134-136`; `probe_corroborate` `k=20`, over-fetch `k*4` `:190,:201`.
- `core/gather.py`: `_N_CANDIDATES=8 :59`; `_K_GATHER=6 :60`.
- `core/shadow_mirror.py`: `MIRROR_TIMEOUT_S=2.0 :34`.
- `core/ask_client.py`: `_SLOW_ENDPOINTS=("/narrative",) :44`; `_SLOW_TIMEOUT=900 :45`; default timeout 300 `:57,:76`; ready timeout 3 s `:85`; `k=20 :110`.
- `core/instrument.py`: `INSTRUMENT_MODEL="claude-haiku-4-5-20251001" :22`. Related models on the path: `core/rerank.py:21-22` (`RERANK_MODEL="claude-sonnet-4-6"`, `RERANK_POOL=150`), `core/expansion.py:25`, `core/joint_extract.py:50` (`_SNIPPET_CHARS=400`), `core/matching.py:94` (`_QUOTE_MARGIN=120`).
- `bridge/server.py`: `HOST/PORT :72-73`; `_DEFAULT_K=20 :74`; `_JOINT_MODEL="claude-opus-4-8" :77`; `_JOINT_RHO=0.95 :78`; `_MEMBRANE_QUEUE_SIZE=1024 :82`, `_MEMBRANE_MAX_RESPAWNS=3 :83`, `_MEMBRANE_RESPAWN_BACKOFF_S=60.0 :84`; `_CONFIRM_M=2 :424`; `_TERMINAL_ACTIONS :739`; `_decision_id` 32-hex `ab-` `:752`; scratch `KB/tmp/deliberate :522`; `run_id` default `"answer-brain" :802`.
- `membrane/world.py`: `ACT_NAME="act" :32`; `AFFORDANCES` (abstain 1, gather 2, ask 3, respond 4) `:35-37`; `UTILITY_FORMS=("said@1",) :46`; `REAL_TO_MEMBRANE :56-61`; bucket vocabularies `:134-138` with cut-points `:141-174`; utility defaults `u_wrong=-9.0`, `lambda_int=0.1`, `kappa_att=0.02` `:237-239`.
- `membrane/coarse.py`: `LIVE_TIMEOUT_S=20.0 :56`; `_ENACT_EFFECTOR :60`.
- `membrane/session.py`: `_VERDICT_Y :60-64`.
- `membrane/categorical.py`: `_INFO_ACTS :46-48`; `RESPOND_BASE=3.0 :49`; `run_categorical` `read_timeout_s=300.0 :303`.
- `membrane/shadow.py`: `ShadowConfig` `read_timeout_s=300.0`, `queue_size=1024`, `max_respawns=3`, `respawn_backoff_s=60.0`, `categorical=False`, `cat_timeout_s=20.0` `:118-131`; `_GATHER_EFFECTOR :200`; `GATE_SUMMARY :210-213`; `_QUEUE_POLL_S=0.05 :215`; `_CLOSE_JOIN_TIMEOUT_S=5.0 :216`; `_LIVE_WAIT_S=10.0 :222`; `_STATS_EVERY=100 :229`; `_MAX_TRACKED_ENTRIES=4096 :235`.
- `membrane/client.py`: `MEMBRANE_ENV :33`; `READ_TIMEOUT_ENV :34`; `DEFAULT_READ_TIMEOUT_S=300.0 :35`; `_ALLOWED_ESCAPES :39`.
- `scripts/ask.py`: `DEFAULT_K=8 :80`; `WEAK_SCORE_FLOOR`, `MIN_STRONG_HITS :85-86`; `ABSTENTION :87-91`; `RERANK_MODEL/RERANK_POOL :112-113`; `EXECUTOR_* :875-903`; `EXECUTOR_DOWN :881-882`; HTTP timeouts 300 `:913`, ready 3 s `:922`.

## DEVIATIONS

1. **Worktree location.** The brief's explicit path `~/.cache/life-agent-census/wt` was used
   (per the dispatcher's instruction), overriding the user-level convention that worktrees live
   under the user's `git/worktrees/REPONAME/NAME` directory. The worktree is registered in the main repo's
   `.git/worktrees` (unavoidable — `git worktree add` writes that metadata); no file under the
   main tree's working directory was written. Removing it (`git worktree remove`) is left to the
   owner/dispatcher, since it is a write to the main repo's metadata.
2. **No subagents.** The brief permits them; none were used, so no rows needed a second-pass
   attribution check beyond the mechanical verifier — recorded so the "all-rows verification"
   commitment reads as first-hand reading + machine check, not as a re-audit of a sweep.
3. **Coverage beyond the candidate lists.** `core/gather.py`, `core/ask_client.py`,
   `core/shadow_mirror.py`, `core/claude_verdicts.py`, `scripts/ask.py`, and the trace-F
   timer check were inventoried because they hold decision-adjacent choices or the triggers the
   brief asks traces to start from; flagged so the reviewer can prune (Q-R2).
4. **§5's count (85)** is a count of *listed* mechanisms at the granularity chosen here (one row
   per named site); a different granularity would give a different number — the number is a
   handle, not a metric.
5. **The PII guard** was run from the worktree without a `uv sync` (see VERIFICATION RECORD):
   the guard script imports only the standard library, so it ran under the system interpreter
   with no venv created inside the worktree.

## REFUSED

- No write into the main tree `$REPO` (no report file, no `docs/` placement, no `git
  commit`/`stash`/`checkout`); no edit to the worktree; no `uv sync` inside it.
- No `$LIFE_AGENT_KB` read, listing, or resolution.
- No test suite, lint, or type-check run (read-only session).
- No proposal, target architecture, or refactoring plan — dispositions only; every "this begs
  a resolution" is a QUESTION below.
- No edit to `PRINCIPLES.md`, any SPEC, `src/`, or `scripts/`.

## QUESTIONS

**Owner (rulings that shape tranche 2's design-doc scope):**

- Q-O1. **Is the executor's body-held choice set (E-1…E-15) inside the "one argmax", or
  transport?** PRINCIPLES §15 says "under §16 the spine is transport"; `EX:19-20` says the body
  "picks NO action". The census finds the body picks the k=0 walk order, the replace-channel
  rule, the grow adoption rule, the iteration bound, and the miss short-circuit. Are these to be
  read as enactment mechanics (out of scope for the collapse) or as decisions the collapse must
  fold into the priced menu?
- Q-O2. **Is the adoption gate (G-1, a posterior-mass threshold) exempt from §16 by design?**
  `gate.py:1-6,:51-57` frames it as a blind-comparison ritual with frozen δ/level, i.e.
  deliberately not an EU decision. Confirm exemption, or name it a §16 gap to price later.
- Q-O3. **`world.utility_by_action`'s own defaults and its perfect-information pricing (M-8):**
  the membrane world carries a *second* utility table with literal defaults (`W:237-239`) and a
  declared over-valuation of information (`W:226-234`). Is the membrane's utility to be
  collapsed onto the one Ū (D-1), or is it a separate, owner-re-decidable world by design?
- Q-O4. **`calibration.py` is the one belief fold that runs host-side (D-2).** Its docstring
  frames the Beta-shrunk isotonic curve as deliberate ("pure Python, no new dependency"
  `:11`); `lookup.py:496` and `narrative.py:89-90` frame any host `a += 1` as the antipattern.
  Which invariant governs tranche 2 — "every posterior through the brain seam" or "curves are a
  fold, not a belief"?
- Q-O5. **The Ū divergence between the online decider and the offline gate (D-8):** the gate
  folds elicitations only (`run_eval.py:1663-1668`), the decider folds elicitations +
  reactions (`LK:985-994`). Intended (blind discipline: the gate must not see verdicts) or an
  accident of history? The answer decides whether tranche 2 has one `posterior()` call site or
  two.
- Q-O6. **The reach surface's `/log_decision` omits the §10 accounting fields (D-9).** A
  Telegram-answered decision logs no `instrument`/`cost_usd`/`latency_s`. Is that a known
  coarsening or a gap the collapse should close by having one poster?

**Reviewer (scope and method):**

- Q-R1. Should the §16 gap list distinguish *belief-shaping* choices (grounding gate L-1, dedup
  L-2, join rule BR-2, replace-channel E-7 — which change the posterior's inputs) from
  *decision-shaping* choices (thresholds, argmaxes, orderings)? The census lists both flat; the
  design doc may want two ledgers.
- Q-R2. Confirm the coverage extension in DEVIATIONS 3 (gather.py, ask_client.py,
  shadow_mirror.py, claude_verdicts.py, scripts/ask.py) is wanted, or prune to the brief's
  candidate lists.
- Q-R3. The credence daemon (`../credence`, out of tree) holds the transform-selection argmax
  and the structure-BMA `g`; the census can only cite its request/reply shapes
  (`EX:459-465`, `:492`, `View :48`). Should tranche 2's design doc pull the daemon's own decision
  code into scope (a cross-repo census), or treat the wire as the boundary?
- Q-R4. `brain.value` (`:296`) still has no in-repo caller — record as "dormant, keep" (the VOI
  building block PRINCIPLES §16 will need) or as dead surface for the collapse to remove?
- Q-R5. Placement: this file is delivered at `~/.cache/life-agent-census/r00-collapse-census.md`;
  the intended committed home is `docs/unification/reports/` beside `r00-census.md` — confirm the
  name (`r00-collapse-census.md`) so cross-references from the tranche-2 design doc are stable.

## PROPOSED

The single next action: **open the tranche-2 design-doc phase** — a design doc written against
this census's facts (the six inventories above as its evidence base), **gated on** (a) the
tranche-1 close (write token released; r00/r01/r02 committed) and (b) the owner's signature on
Q-O1…Q-O6, which set the doc's scope. Nothing else is proposed here.

## VERIFICATION RECORD (2026-08-18, before delivery)

**Every `file:line` machine-checked against the pinned worktree.** A small verifier (out of
tree at `~/.cache/life-agent-census/verify_refs.py`, standard library only) parsed every
`path:N[-M]` reference and every shorthand `:N[-M]` in this file (resolving shorthands against
the nearest preceding path or the row's abbreviation `LK`/`NR`/`EX`/`GATE`/`DEC`/`SEAM`/`BR`/`SH`/
`W`/`CO`/`ASK`/`AC`), checked file existence and that the cited range lies within the file, and
flagged where the nearest preceding backticked identifier does not occur within −3..+3 lines
of the cited range. Independently, `grep -n "^def \|^class \|^[A-Z_][A-Z_0-9]* *[:=]\|^_[A-Za-z_0-9]* *[:=]"`
was run over every cited module and each named function/class/constant in the tables was
compared by eye against that dump (those dumps were the *source* of the line numbers, so this
was a self-consistency check, not a second derivation).

The verifier's output and the corrections it caused are appended below by the run itself
(VERIFICATION RECORD — run output). Any residual "hard failure" is explained beside it.

**PII shapes guard.** Run before delivery from the worktree with the system interpreter (the
guard needs no venv):

```
$ cd ~/.cache/life-agent-census/wt && python3 .githooks/pii_check.py --shapes-only ~/.cache/life-agent-census/r00-collapse-census.md
(see run output below)
```

### VERIFICATION RECORD — run output (final, before delivery)

Run over the body (everything above this section), before it was appended:

```
$ python3 ~/.cache/life-agent-census/verify_refs.py ~/.cache/life-agent-census/r00-collapse-census.md ~/.cache/life-agent-census/wt
refs checked: 1139; resolvable+in-range: 1139; hard failures: 0; ident-heuristic misses: 92
unresolved paths: {'.cache/life-agent-census/r00-collapse-census.md': 3, 'docs/unification/reports/r00-census.md': 3,
 'REPO/docs/unification/reports/r00-census.md': 1, 'report.md': 1, '.config/life-agent/pkm.yaml': 1,
 'r00-census.md': 1, 'r00-collapse-census.md': 1, '.cache/life-agent-census/verify_refs.py': 1}
```

**Every one of the 1139 `file:line` references in the body resolves to a file in the pinned
worktree and lies within that file's line count.** The "unresolved paths" are, by inspection,
the report's own path, the prior census (untracked at HEAD, deliberately absent from the
worktree — STATE), the gate report artefact name (`report.md`, written under
`$LIFE_AGENT_KB`), the default `PKM_CONFIG` location, and the verifier itself — none is a
citation into the tree. (Re-run over the *whole* file including this section, the tally reads
`refs checked: 1172; … hard failures: 8` — the eight are this section's own verbatim quotation
of the guard output naming *this report's* line numbers (seven lines), plus the mention of the
port artefact in item 2 below; they are quotations about the report, not citations into the
tree.)

**The 92 identifier-heuristic misses were each reviewed by hand; none is a wrong citation.**
They fall into three classes: (i) 16 are the `py` artefact — a second `:N` after a `path.py:M`
token, where the heuristic's "identifier" is the file extension; (ii) the trace lines (§3),
where the word before the number is English prose (`branch`, `order`, `retired`, `once`,
`View`, `reorder`, `filter`, `NAMED`, `MC`, …) rather than a symbol; (iii) the remainder,
where the cited line is a *call site inside* the named function and the function's `def` is
more than three lines above (`LK.action_utilities :878-879` = the `u_assert` calls inside a
function defined at `:864`; `BR._log_decision :820` = the `DEC.append` inside a handler defined
at `:765`; `NR.narrative_answer :473/:485`; `LK.decide_and_record :1061-1063`; `EX._conditioned_rho
:187`; `SH.boot_snapshot :1121-1127`; and so on). Two are case artefacts (`n_draws :77` /
`seed :78` cite `DEFAULT_N_DRAWS` / `DEFAULT_SEED`).

**What the check caught and corrected in the body:**

1. `core/volatility.py` — the `half_life` keyword loop was cited `:50-53`; the loop is `:52-54`
   (`:49-50` is the empty-construct guard, `:51` the lowercase). Corrected in §2 and §5 V-1.
2. `§6` — a port number written as `:8799` parsed as a line reference; rewritten as prose.
3. `§1.3` — the paragraph named no file (the gate constants were bare `:73` etc.); `core/gate.py`
   added.
4. `§1.5` — `POST {daemon}/decide :109` sat beside `brain.optimise :105-108` and resolved
   ambiguously; the file (`seam.py:109`) is now explicit.
5. The five call-graph traces (§3) — bare shorthands that meant "the enclosing function's file"
   were ambiguous where the previous hop named another module; every such shorthand now carries
   its module abbreviation (`EX:252-258`, `ASK:1242`, `RX:194`, `SM:96-101`, …). No line number
   changed.
6. §5 — the gather-driver choices had been labelled `G-1…G-3`, colliding with the gate's
   `G-1…G-4`; renamed `GA-1…GA-3` (§3 trace B and §5). The count line was recomputed from the
   ids actually listed: **85**, not the 77 first written (the S/B/A/GA group is 14, not 13,
   once A-1/A-2 and the three gather choices are counted separately).
7. Trace F — the timer entry point was described as `tasks/project.py`; it is
   `bin/mail-to-tasks:20` → `scripts/mail_to_tasks.py` → `tasks/project.py`, with the exact
   `life_agent.core` reads named (`scripts/mail_to_tasks.py:50,:95`).

**PII shapes guard — first run flagged, corrected, re-run clean.**

```
$ cd ~/.cache/life-agent-census/wt && python3 .githooks/pii_check.py --shapes-only ~/.cache/life-agent-census/r00-collapse-census.md
pii_check BLOCKED — possible PII (values withheld):
  …r00-collapse-census.md:17: personal-path (machine prefix)
  …r00-collapse-census.md:28: personal-path (machine prefix)
  …r00-collapse-census.md:30: personal-path (machine prefix)
  …r00-collapse-census.md:50: personal-path (machine prefix)
  …r00-collapse-census.md:493: personal-path (non-placeholder root)
  …r00-collapse-census.md:536: personal-path (non-placeholder root)
  …r00-collapse-census.md:556: personal-path (machine prefix)
exit=1
```

All seven were owner-machine paths in *this report's own prose* (the main tree's absolute
path in STATE/REFUSED/the placement note, and two user-git-directory roots in DEVIATIONS 1 and the
`bin/answer-brain` env row). Each was replaced with a placeholder (`$REPO` for the main tree;
"the user's git dir" for the roots) — no repo content was involved. Re-run:

```
$ cd ~/.cache/life-agent-census/wt && python3 .githooks/pii_check.py --shapes-only ~/.cache/life-agent-census/r00-collapse-census.md
exit=0
```

(The guard was run with the system `python3` from inside the worktree — the script imports
only the standard library — so no `.venv` was created there; `git -C ~/.cache/life-agent-census/wt
status --short` is empty at delivery.)

**Main tree at delivery.** `git -C $REPO status --short` shows the concurrent tranche-1 session's
own working files (`docs/unification/`, `docs/unified-ledger-design.md`, `src/life_agent/ledger/`,
new `tests/test_ledger_*.py`, a modified `tests/conftest.py`) — none of them touched by this
session; this census wrote nothing under `$REPO`.

## Rulings applied — 2026-08-19 (at placement; append-only — the census above is as delivered)

Placed on the reviewer's Q-R5 ruling with this section appended, so the tranche-2 design doc
cites *census plus addendum*, never a raw locator: the census's `file:line` cites are pinned at
`873860a`; the correction table below maps them to `b83dbc0` (the head at placement).

### 1. Drift since the pin — the correction table (Q-R5's condition)

**Drift since the census's pin (`873860a` → `b83dbc0`), every file the census cites.** 38 cited
files unchanged (all of `core/{brain,calibration,config,decide,deliberate,gate,gather,matching,
narrative,pricing,probes,seam,utility,ask_client}.py`, `membrane/{shadow,world,coarse,session,
client,categorical}.py`, `scripts/{run_eval,gate_splice,eval_executor}.py`, `scripts/membrane/*`,
`scripts/fairfight/*`). Changed, with the shift a cited line suffers:
- `core/executor.py` — +13 lines inserted at old `:102` (a fallback-rho block); `+12` net at
  `:512-532`; `+3` at `:605-610`. Census `EX:` cites in `:102-511` shift **+13**; `:512-519` is
  rewritten; `:520-604` shift **+25**; `:611+` shift **+28**. Cites `EX:19-20`, `:64-74`, `:92-95` unshifted.
- `core/lookup.py` — three one-line rewrites (`:658`, `:784`, `:847`: no shift) and +3 lines at
  `:1110`. Census `LK:` cites `≤1109` unshifted; `:1110+` (`decide_and_record`'s tail,
  `:1124-1138`, `lookup_answer :1142`, `:1171`) shift **+3**.
- `bridge/server.py` — +8 lines at old `:353` and one line each at `:354`, `:399`, `:411`
  (the `_probe_corroborate` dedup guard). Census `BR:` cites `≤352` unshifted; `:353` +8;
  `:354-398` +9; `:399-410` +10; `:411+` (`_join_deliberate_value :537-571`, `_TERMINAL_ACTIONS :739`,
  `:742-753`, `/log_decision :765`, `:791-794`, `:820`, `:843`) shift **+11**.
- `scripts/ask.py` — +1 at old `:29` (`import json`), then +3/+9/+9/+6 in `:1307-1376`
  (`REFRESH_NOTES`, `_reingest_state` reconcile-or-refuse, `ensure_gtd_fresh`) and +5 in
  `main` at `:1517-1520`. Census `ASK:` cites `≥29` shift **+1** (`:630-633`, `:778`, `:875-880`,
  `:958-960`, `:985-1048`, `:1008`, `:1039`); nothing the census cites lies in `:1307+`.
- `core/{decisions,outcomes,reactions,claude_verdicts,gather_outcomes,joint_extract}.py`,
  `scripts/verdict.py` — the tranche-1 C5 mirror hooks (2–4 lines after each writer's legacy
  append) and the joint_extract unique-lineage fix; no census-cited entry point or argmax moved.
- `tests/conftest.py` +184 (hermetic mirror + pkm-root fixtures); docs additions only.
Nothing the census classifies (entry points, ◆ choices, D-1…D-15, the §16 gap list) changed in
kind; the shifts above are the whole correction table for the tranche-2 design doc's citations.


### 2. Reviewer rulings on Q-R1…Q-R5 (verbatim), and the r04 carry-overs

> **Q-R1 — yes, two ledgers, with one rule stated once and applied to all 85, not just the
> E-list.** *Belief-shaping* = changes the observation set or the likelihood the posterior folds
> (L-1, L-2, BR-2, E-7, E-10): these collapse into **declared error models** — model content,
> priced as such. *Decision-shaping* = compares or orders to choose an action (E-4, E-14, G-1,
> M-2, the threshold rows of D-3): these collapse into the argmax or die. And a third verdict
> falls out rather than a third ledger: *mechanics* (E-2, E-6, U-2, M-11) — sequencing the same
> work, off both ledgers. This is your Q-O1 recommendation generalised: one classification rule,
> three verdicts, one table for everything.
>
> **Q-R2 — the coverage extension is confirmed, retroactively vindicated:** pruning to the
> candidate lists would have missed D-9/D-10 — the reach path's unpriced poster — which Q-O6 now
> closes. The extension found the gap the brief's list couldn't have.
>
> **Q-R3 — the wire is the boundary for tranche 2**, with an obligation attached: the design doc
> records the daemon's `/decide` argmax and structure-BMA `g` as trusted-by-contract at the wire,
> citing the request/reply shapes the census already pins. The cross-repo daemon census is real
> work — but it's a **named prerequisite of the seam tranche**, where it's needed anyway, not of
> the collapse. Pulling it into tranche 2 makes a single-repo tranche a two-repo one and stalls
> both.
>
> **Q-R4 — dormant-keep, conditionally.** `brain.value` is the VOI building block §16 names, and
> deleting a wire method to re-add it next tranche is churn theatre. But "dormant, keep" must be
> earned: the design doc's VOI section names it as consumer and a test pins the wire shape. If
> the design doc doesn't claim it, it converts to dead surface and dies at implementation — no
> unclaimed dormancy.
>
> **Q-R5 — confirmed:** `docs/unification/reports/r00-collapse-census.md`, with the packet's
> drift table appended to the census as a **dated addendum section at placement** — append-only,
> census as delivered plus the correction table — so the design doc cites census-plus-addendum,
> never raw stale locators. Run the script. **r04 Q2:** confirmed. **r04 Q3:** moot, closed.

The reviewer's overall reading, for the record: *"The census holds up — 85 mechanisms with the
two sanctioned argmax sites correctly excluded from the gap list, and the drift verification per
cited range is exactly what the r04 ruling required."*

### 3. Owner signatures Q-O1…Q-O6 and r04 Q4 — signed as recommended, with the reviewer's sharpenings

The recommendations were drafted from a re-read of the cited code on 2026-08-19, endorsed by the
reviewer ("endorse all seven recommendations, with four sharpenings"), and **signed by the owner
by executing the placement script** (the S12 form: the owner's run is the signature). Each entry:
the ruling as signed, then the reviewer's sharpening verbatim where one was given.

- **Q-O1 — E-1…E-15: a per-item classification, not a blanket answer.** A body-held choice that
  changes *what is asserted or what the posterior sees* (the replace-channel rule, the grow
  adoption rule, the miss short-circuit) is inside the argmax and must appear in the priced menu
  or be derived from it; a choice that only sequences the same work (walk order, iteration bound)
  is enactment mechanics, out of the collapse's scope. Generalised by Q-R1 into the one rule /
  three verdicts / one table for all 85 mechanisms. Evidence: PRINCIPLES §15–16;
  `core/executor.py:19-20`. *Sharpening:* "name the first collapse target now: **E-14**. The
  census caught `GO:9-11` declaring the bucketing exists so the threshold is 'never control
  flow' while `EX:190-205` uses it as control flow on the legacy lane — the repo contradicting
  its own doctrine in two files is the strongest single §16 violation on the list, and the
  design doc should lead with it."
- **Q-O2 — the adoption gate (G-1) is exempt from §16 by design, for a stated reason.** It is
  the instrument that adopts optimisers, EU-shaped already (a decision over arms under P(U));
  its one non-EU element — the frozen δ/level — is the blindness that makes runs comparable;
  folding the instrument into the optimiser it judges is circular. Recorded as a named exception
  with its reason, not a §16 gap. Evidence: `core/gate.py:1-6, :51-57`. *Sharpening:* "scoped
  precisely: it covers the gate's *verdict mechanism* (frozen δ/level …), not the gate's utility
  fold, which Q-O5 governs."
- **Q-O3 — the membrane world's utility table stays a deliberate second world; the three host
  spellings collapse.** D-1's four spellings split: `decide.u_assert`, `lookup.action_utilities`,
  `gate.realised_utility` collapse onto the atom; `world.utility_by_action` is a declared
  *different* world whose distance from Ū is the shadow's measurement (its own docstring:
  "never to be tuned away … owner-re-decidable"), off the decision path. Evidence:
  `membrane/world.py:224-239`. *Sharpening:* "with direction stated: the three host spellings
  derive *from* `decide.u_assert` — the collapse names the atom the source, not a fourth
  abstraction; the membrane's table stays a deliberate second world whose distance from Ū *is*
  the measurement, never tuned toward it."
- **Q-O4 — §16's invariant governs (`calibration.py`): every probability through the brain seam;
  the host-side curve is a named debt, not an exception.** A reliability curve is P(correct | c);
  it belongs behind the seam, but it is a monotone-curve fold credence does not offer today, and
  rewriting it host-side to look like a belief would be the antipattern in another coat. Design
  doc: it stays as is, listed as the one host fold with the reason; no *new* host folds; it moves
  behind the seam when credence gains a monotone fold — a successor item. Evidence:
  `core/calibration.py:1-14`; `lookup.py:496`; `narrative.py:89-90`. *Sharpening:* "the debt is
  realistic, not aspirational: per the fold-depth facts, a monotone fold at outcome-log depths
  (~10²–10³, refolded per ask) is exactly the shape the engine serves comfortably — the
  retirement path is a credence backlog item with a known cost envelope. The design doc should
  also say which of D-2's four estimators survives: one reliability posterior behind the seam,
  declared views for the rest."
- **Q-O5 — Ū with reactions online, without them offline: intended — one `posterior()` call
  site, two evidence cutoffs by declaration.** The gate must fold a frozen evidence set or its
  runs stop being comparable; the decider must fold everything to date or the reaction loop is
  dead. One fold entry point with an explicit evidence policy (frozen-elicitations |
  all-to-date), each caller naming its policy — not two folds, and not "make the gate see
  reactions". Evidence: `lookup.py:983-996`; `scripts/run_eval.py:1660-1670`. *Sharpening:*
  "the evidence-policy parameter *is* a regime indicator — the gate's frozen-elicitations regime
  and the decider's all-to-date regime are two declared conditioning sets over one fold."
- **Q-O6 — the reach path's unpriced `/log_decision` is a gap to close: one poster.** The bridge
  accepts `instrument`/`cost_usd`/`latency_s`/`run_id`; `scripts/ask.py` posts them, the reach/CLI
  driver `core/ask_client.py` does not; the collapse gives D-9/D-10 one driver with one
  `/log_decision` body, no field optional on the poster's side. Evidence:
  `bridge/server.py:796-830`; `scripts/ask.py:976-980`; `core/ask_client.py:140-149`.
  *Sharpening:* "one driver also closes D-10 and the B-2/A-1 seam asymmetry; three rows, one
  function."
- **r04 Q4 — the fold-depth facts accepted; (α) is the P2 re-run's frame** (measure the actual
  per-ask folds before redesigning; β only if α shows the per-ask cost matters; no overnight P2
  on the current numbers).

### 4. What opens

The tranche-2 design-doc phase, on this census's PROPOSED terms — inputs: census + this
addendum, the two-ledger rule (Q-R1), the wire boundary with its recorded trust (Q-R3), the
conditional dormancy of `brain.value` (Q-R4), the seven signed scope rulings, and E-14 as the
first named target. The opening brief is the reviewer's to draft on the owner's word.
