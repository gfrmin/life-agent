# r13 — collapse M3: the one fold entry point (Q-O5/D-8) + the D-2 reliability unification

**Pre-registration.** This document is committed BEFORE any `src/` change on this branch.
The frozen criteria are not renegotiable at read time; blind amendments (committed before
any gate runs) are allowed and must say what they correct. Cap-the-arc: anomalies en
route are disclosure items in this report's final form, never a new diagnostic arc.

## STATE (recon, 2026-08-25, master `43cf34f` — M2 merged and deployed)

- `UT.posterior(brain, model, events)` (`core/utility.py:~430`) takes no policy; each
  caller hand-assembles its conditioning set:
  - `LK.current_u_bar` (`core/lookup.py:1031`): elicitations + `R.load_reactions` — the
    **all-to-date** regime; memoized in `_U_BAR` keyed by `fold_version(model, events)`.
  - `scripts/run_eval.py:1833`, `scripts/gate_splice.py:107`,
    `scripts/membrane/p3_gate.py:434`: elicitations only — the **frozen-elicitations**
    regime, unnamed in code.
  - The census's fifth D-8 site (`fairfight/loss_ledger.py:531-533`) **no longer
    exists** — the file was deleted in an earlier arc. Four live sites. (Disclosure D0.)
- `fold_version(model, events)` (`utility.py:275`) does not cover the regime; a memo
  keyed by it cannot distinguish the two conditioning sets (today only one process ever
  holds one regime, so it has never misServed — the defect is structural).
- The M2 recorder stamps `policy="all-to-date"` as a **constant** at the one poster
  (r12 "The design, frozen": *"frozen-elicitations becomes stateable at M3's
  `posterior(policy=…)`, never here"*).
- D-2's two instances are the same wire fold with different keys/priors:
  `LK.extractor_reliability` (`lookup.py:504`; Beta(4,4) via `_RHO_PRIOR_A/B:191`,
  conditioned per graded outcome) and `NR.population_posteriors` (`narrative.py:213`;
  cells verified/unsupported/unverifiable, `_CELL_PRIORS:79`). Both condition over the
  wire and read params back; neither is a host fold. `CAL.fit_reliability_curve:82` is
  the confidence-conditioned view — the named debt (§6.3), untouched here.
  `O.reliability_bins:211`/`ece` feed no decision (census §2) — diagnostic views.
- M2's shims stand as promised: `AC.answer` (5 lines: `drive` → `DOWN` |
  `EX.render_view`), `ASK.answer_via_executor` (drive + the `*_LAST` surface concerns),
  `ASK._edge_curves`. Callers: `reach/jarvis.py` (×2, via `AC.answer`),
  `scripts/run_eval.py:1129`, ask's REPL dispatch, `collapse/drive.py:393` (A-loop).
- r12 promise 3: the family leaves' write tails (`LK.decide_and_record`,
  `NR.narrative_answer` → `REC.record_local`) are the leaves' side effects **for exactly
  one checkpoint**; at M3 the leaves return and their caller records.
- The m2-base fixture bodies do **not** carry `utility_fold_version` (verified on
  m2-base-blookup-q2-001: body = {decision, question, retrieval_keys}) — the fold-version
  hash change below is invisible to 7.2.

## The mandate (design §8 M3 row; §3.1; §3.2)

1. **Q-O5/D-8 — one entry point, two declared evidence policies.**
   `UT.posterior(brain, model, evidence, *, policy)` with
   `policy: Literal["frozen-elicitations", "all-to-date"]` — required keyword, no
   default, no old spelling surviving (the row: *"a rename with a required argument"*).
   The policy is a **regime indicator naming a declared conditioning set**, enforced
   structurally: `frozen-elicitations` REFUSES any non-`Elicitation` event (raises —
   the policy-swap seeded defect of §7.5 dies at the fold itself);
   `all-to-date` accepts elicitations + the verdict→evidence projection.
   `fold_version(model, events, policy)` covers the policy name. The `_U_BAR` memo keys
   by the covered version (a memo can never serve one regime's Ū to the other).
   The four callers name their policy at the call. `current_u_bar` returns the policy it
   folded under, and **the M2 driver's `policy` stamp derives from it** — the constant
   dies; the record states the fold actually used.
2. **D-2 — one reliability posterior behind the seam.** One wire fold
   `reliability(brain, edge, cell, outcomes_path)` → `(alpha, beta)`, priors declared in
   one table keyed `(edge, cell)`, in a new `core/reliability.py` (the recorder-module
   precedent; no fourth abstraction — it is the D-2 clause's one home).
   `LK.extractor_reliability` and `NR.population_posteriors` keep their public names as
   **bindings** of the one fold (they name (edge, cell) selections; the fold logic lives
   once). Wire semantics unchanged: same priors, same conditioning stream, same
   `read_params` readback — bindings must be byte-equivalent on the wire (7.2 pins the
   B-traces; the cassette would miss on any changed wire shape, loudly).
   `fit_reliability_curve` untouched (debt, §6.3). `reliability_bins`/`ece` get the
   "declared diagnostic view" docstring — no behaviour change.
3. **The M2 shims die.** `AC.answer`, `ASK.answer_via_executor`, `ASK._edge_curves`,
   deleted; jarvis calls `AC.drive` + `EX.render_view` (DOWN string verbatim), run_eval
   and the REPL take the driver directly (the `*_LAST` surface concerns move to ask's
   own dispatch, not into core), `collapse/drive.py` drives `AC.drive` + renders.
   Interaction-contract strings untouched everywhere.
4. **The leaves return; the one recorder's caller records.** `LK.decide_and_record` and
   `NR.narrative_answer` stop performing the write tail; they return what they minted
   and their caller invokes `REC.record_local` — same body, same writer function, new
   call site; `decision_id = akey.cache_key` preserved verbatim. Trace-B ledger events
   stay **byte-identical** (7.2 asserts it).

Out of scope, deliberately: the price table and utility atom (M4); any argmax move (M5);
`fit_reliability_curve`'s successor; every membrane surface (the shadow reads, never
moves); anything presupposing the proplang swap.

## Machine directions for 7.2

**None.** The comparator is **pure equality on all 314 m2-base fixtures** — M3 changes
no recorded field's value: `policy` remains `"all-to-date"` on every A-trace body (now
derived instead of stamped), trace-B bodies/events are byte-identical, and
`utility_fold_version` is absent from fixture bodies. The 105 M2-era annotations still
assert their (now-satisfied) M2 directions. A single field diff anywhere is a FAIL.

## Gates (all frozen; a FAIL on any is a STOP for an owner ruling)

- **G1** — `uv run pytest` default set green (plus this checkpoint's tests); `ruff` and
  `mypy` clean. TDD throughout: every new predicate verified RED before GREEN.
- **G2 (7.2)** — `collapse_replay --checkpoint m2-base`: **314/314, equality**, run on
  the final tree.
- **G3 (7.3)** — the priced frozen-regime eval gate on the run-14 recipe and corpus pin
  (`run_eval --gate`, §6.10 tree pin, `PYTHONHASHSEED` pinned), **spend cap $8**.
  Frozen comparator, all four conjuncts required:
  (a) `P(Δ>0.05) ≥ 0.90` at the series' frozen δ/level;
  (b) **zero NEW wrong commits** — a wrong is NEW iff its row was not wrong in run 14's
  typed arm (the run-14 conferral's baselining convention; run 14's carried wrongs:
  the two standing rows + the warm-deliberate row);
  (c) **no named wrong-commit class worse** (the hard clause);
  (d) every typed-arm decision row states `policy="frozen-elicitations"` (the field the
  fixtures cannot measure — §7.3's own purpose).
  The known §6.13 residue (commit-wobble floor 2 rows, r08) and the warm-deliberate
  live-vs-replay wobble (run 14) are **published context, not adjustments**: if the read
  lands under (a) by wobble, it is a FAIL and stops for a ruling.
- **G4** — 7.4 **not run**: M3 touches no store and no writer identity (the recorder
  performs every write before and after; only its call sites move). Stated per §7.4.
- **G5** — PII: no corpus values in tree; hooks armed on every commit.

## Predictions (registered before implementation)

- P1: G2 reads 314/314 with zero diffs on the first green build.
- P2: the frozen-policy refusal test is RED before the enforcement lands (posterior with
  a `Reaction` under `frozen-elicitations` must raise) and GREEN after.
- P3: `fold_version` output changes for identical (model, events) once policy enters the
  hash — asserted by a test pinning old≠new and new≠new-across-policies; nothing else
  observes the hex (fixtures carry none; the ledger is append-only identity).
- P4: G3 reads within the band with zero NEW wrongs; the typed arm's answer rate lands
  within ±0.06 of run 14's 0.60 (no decide-policy change is in this tree).
- P5: live calibration fingerprints (`decisions/outcomes/reactions.jsonl`) are
  byte-identical across the whole checkpoint EXCEPT G3's own eval-side writes, which
  land under `$LIFE_AGENT_KB/eval/` — verified before/after.

## Deviations

Anything unexpected is a disclosure item in this report's final form. Rollback: revert
the branch (one PR). Sequencing after green: report results appended, mirrors updated
(CLAUDE.md tail + design §8 row), PR, CI, merge, deploy to the live box, then M4 under its own
pre-registration.

## AMENDMENT 1 (2026-08-25, blind — before any src change; nothing above edited)

Recon error, caught by enumerating `UT.posterior(` callers before touching the
signature. Two corrections to STATE:

1. **The census's fifth D-8 site LIVES** — `fairfight/loss_ledger.py` moved to
   `scripts/fairfight/loss_ledger.py` (the recon greped the census's old `src/` path and
   read exit-1 as deletion). Its evidence set is elicitations only → it names
   `policy="frozen-elicitations"`. Five live D-8 sites, not four; Disclosure D0 is
   withdrawn.
2. **A sixth caller exists outside the census:** `ledger/golden.py:160`
   (`_utility_evidence` → the A4a/A4b artefacts) folds elicitations + reactions —
   it snapshots the live decider's fold → it names `policy="all-to-date"`.
   Consequence for G4's not-run declaration: A4a compares `fold_version` hex, so any
   CROSS-tree (pre-M3 vs post-M3) golden comparison would read a hex difference by
   design — P3 already predicts the hex change; within-tree snapshot/compare pairs
   (the only mandated use) are unaffected.

The mandate's caller list is restated as: `current_u_bar` + `golden._utility_evidence`
→ `"all-to-date"`; `run_eval`, `gate_splice`, `p3_gate`, `loss_ledger` →
`"frozen-elicitations"`. Everything else in the pre-registration stands unchanged.

## AMENDMENT 2 (2026-08-25, blind — before any gate run; src Phase 1 in progress)

Mandate 4's sentence "Trace-B ledger events stay **byte-identical** (7.2 asserts it)"
is wrong on two counts, found by checking what the fixtures actually observe before
relying on it:

1. The leaf events stamp `utility_fold_version`, and P3 registers that the hash changes
   once the policy enters it — so post-M3 leaf events are **field-identical except that
   stamp**, not byte-identical. (The m2-base fixtures carry the old hex at
   `outputs/audit/utility_fold_version`.)
2. 7.2 does not assert event bytes: the comparator's field classes declare `audit`
   as `OUTPUT_RECORDED_ONLY` — recorded, never compared — so the hash change is
   invisible to G2 and the pure-equality comparator stands exactly as frozen.

Restated mandate 4, replacing the sentence: the write tail moves call-site only (same
body, same writer function); every event field except `utility_fold_version` is
unchanged, `utility_fold_version` changes per P3, and G2's assertion is the projected
output equality (in which `audit` is recorded-only). No gate, direction, or prediction
changes; the mandate's substance (who records) is untouched.

## AMENDMENT 3 (2026-08-25, blind — before any gate run; D-2 not yet implemented)

The frozen D-2 signature `reliability(brain, edge, cell, outcomes_path)` cannot be built
as written: the two observation-stream selectors (`LK._extractor_outcomes`,
`NR._cell_observations`) filter on their instruments' CURRENT identity
(`extract_instrument_hash()` / `instrument_identity()`), so a fold module reading
`outcomes_path` itself would import the instruments while they import the fold — a
cycle; and the selectors are §3.3 observation-model clauses (each docstring: "pure
data-reading… no host belief arithmetic"), owned by their instruments, not belief
folds. Corrected signature: **`reliability(brain, edge, cell, observations)`** — the
one fold owns the prior table keyed `(edge, cell)` and the create→condition→read→destroy
choreography; the instruments keep their declared stream selectors and pass the
Bernoulli stream in. A `conditioned_state(brain, edge, cell, observations)` companion
serves the mean-readback binding (`extractor_reliability_mean` reads `mean`, not
`read_params` — the wire choreography of every binding must stay cassette-identical).
`NR.coverage_posterior` is NOT a D-2 instance (the open-world tail is its own belief,
not an edge's reliability) and stays where it is. Everything else stands.

## AMENDMENT 4 (2026-08-25, blind — before any gate run; shim phase not yet implemented)

Mandate 3 said all three M2 shims are deleted. Two are; the third is retained with its
shim-ness removed, because deleting the NAME would duplicate a surface:

- `AC.answer` — **deleted.** Its two callers (jarvis, the A-loop replay driver) inline
  `drive` + `EX.render_view` / the DOWN string. No old-poster spelling survives in core.
- `ASK._edge_curves` — **deleted.** Its consumers take `AC._edge_curves` with ask's
  hold-out constant directly.
- `ASK.answer_via_executor` — **retained as ask's executor-lane surface** (docstring
  rewritten; the "shim over the one driver, deleted at M3" language retires). It was
  never a second spelling of the driver: its body is the `*_LAST` seam resets,
  cards/scores derivation, and the `EXECUTOR_DOWN` contract string — exactly what
  mandate 3's own parenthetical keeps "in ask's own dispatch, not into core". Its
  second caller is `run_eval`'s typed arm, which must take the executor lane WITHOUT
  the dispatch's in-process fallback (a daemon outage mid-gate must raise, never
  silently switch arms). Deleting the name would force that surface to be spelled
  twice — the opposite of the collapse. The r12 D3 promise is discharged as: no shim
  remains (the two duplicate spellings are gone; the survivor is a surface, not a shim).

## AMENDMENT 5 (2026-08-25, blind — before any gate run; phase 4 not implemented)

Mandate 4 ("the leaves return what they minted and their caller invokes
`REC.record_local`") is withdrawn as written — enumerating the callers before moving
anything showed it would MULTIPLY spellings, not collapse them:

- The design's §8 premise ("the leaves' own write calls become dead code at M2 and are
  removed at M3") assumed the M2 driver records for the in-process leaves. r12 froze the
  safer construction instead: the leaves write THROUGH the one recorder
  (`REC.record_local`, byte-identical events) — the calls are live and load-bearing,
  not dead.
- Each leaf has THREE callers today (`ask.py`'s in-process lanes, `bridge/server.py`,
  `gather.py`/the replay drivers). Moving the write to the callers turns 2 recording
  sites into 6 — the opposite of Q-O6 — and every new site is a chance to record
  differently.
- The collapsed end-state (one driver records once) arrives at M5, when the argmax
  absorption makes the driver the leaves' ONLY caller; the write moves then, as one
  move, to one place.

What M3 keeps: one write path (`core/recorder.py`), leaf drift-gated
(`tests/test_recorder.py` bans leaf-side `DEC.append`), `decision_id = akey.cache_key`
verbatim. The r12 promise "removed at M3" is discharged as: there is no dead code to
remove, and the single-writer invariant it protected is already enforced. Gates,
directions, and predictions unchanged.

## AMENDMENT 6 (2026-08-25, blind — before any gate run)

G3's conjunct (d) as frozen — "every typed-arm decision row states
`policy="frozen-elicitations"`" — is wrong and would fail every row by construction:
the typed arm's decisions are ranked by the DAEMON under `current_u_bar`, whose declared
regime is `all-to-date` (§5.1: the record states which set ranked the decision — that is
the field working as designed, not a defect). What §7.3 freezes is the GATE'S OWN
evaluation fold (`run_eval`'s posterior for scoring), which now names
`policy="frozen-elicitations"` at its call site and is structurally enforced (a
verdict-projected event under the frozen policy raises — the §7.5 policy-swap defect
dies at the fold).

Conjunct (d) restated: **(d1)** every typed-arm decision row states
`policy="all-to-date"` (the decider's regime, derived from `LK.U_BAR_POLICY`, never an
independent literal), and **(d2)** the firing script's tree gate pins
`policy="frozen-elicitations"` at `scripts/run_eval.py`'s fold site (a static assert on
the tree the run describes). Conjuncts (a)–(c) unchanged.
## RESULTS (read 2026-08-25, appended after the gates ran — nothing above this line changed)

Execution was three TDD phases on branch `collapse-m3` (implementation commit `1a54854`),
plus one phase discharged by amendment: (1) the policy-covered fold
(`utility.posterior(…, *, policy)`, structural enforcement, `fold_version` covering the
policy, the `_U_BAR` memo keyed by the covered version, six callers naming their regime,
the driver's stamp derived from `LK.U_BAR_POLICY`), (2) the one reliability fold
(`core/reliability.py`: `PRIORS` keyed `(edge, cell)`, `reliability`/`conditioned_state`,
both instruments as bindings, drift-gated), (3) the shim deletions as amended
(`AC.answer` and `ask._edge_curves` deleted, jarvis and the A-loop driver inline
drive + render, `answer_via_executor` re-documented as the executor-lane surface),
(4) withdrawn by amendment 5 (the leaf write tails stay with the one recorder until M5).

### Gate readings

- **G1 — GREEN.** 2718 passed, 35 deselected; `ruff` clean; `mypy` clean (221 files).
  (`~/.cache/life-agent/m3/pytest-final2.log`.)
- **G2 (7.2) — GREEN.** 314/314 fixtures replay identically under PURE EQUALITY — no
  new directions, exactly as pre-registered: the `policy` value on every A-trace body is
  unchanged (now derived, not stamped), trace-B projections byte-identical, and the
  fold-version hash change is invisible to the comparator (`audit` is recorded-only).
  (`~/.cache/life-agent/m3/replay-final-*.log`.)
- **G3 (7.3) — PASS on all four conjuncts.** Run 15 (`gate-20260825T215428`), the
  run-14 recipe on the committed tree `1a54854`, comparison arm run 14's meta, spend
  $0.68 of the $8 cap (deliberate 40/104, all warm).
  (a) **P(Δ>0.05) = 0.907** (≥ 0.90), Δ̄ = +0.421 [−0.046, +0.920] — numerically
  identical to run 14, which is exactly what a behaviour-preserving checkpoint on warm
  caches should read. (b) typed wrongs = {the two standing rows + the warm-deliberate
  row} — **precisely run 14's carried set; zero NEW.** (c) no named class worse (same
  three rows, same classes). (d1) **every run-15 decision row states
  `policy="all-to-date"` and `regime="full"`** (102 rows under
  `run_id=gate-20260825T215428`). (d2) pinned at the tree gate (rehearsed gate-only,
  then fired). Answer rate typed 0.62 · mono 0.97.
- **G4 — 7.4 not run**, as declared: no store or writer identity moved (the recorder
  performs every write before and after; only signatures and bindings changed).
- **G5 — GREEN.** No corpus values in tree; hooks armed on every commit.

### Predictions vs readings

- **P1 — CONFIRMED.** G2 read 314/314 with zero diffs on the first complete build (one
  earlier partial run had two jarvis-surface test failures — G1 side, not fixtures).
- **P2 — CONFIRMED.** The frozen-policy refusal test was RED (TypeError — the keyword
  did not exist) before the enforcement landed, GREEN after.
- **P3 — CONFIRMED.** `fold_version` covers the policy (old two-arg spelling refused;
  same inputs differ across policies; deterministic within one); nothing compared
  observes the hex.
- **P4 — CONFIRMED.** Within band with zero NEW wrongs; answer rate 0.62, inside ±0.06
  of run 14's 0.60.
- **P5 — HALF-REFUTED, disclosed.** Before run 15 the fingerprints were r11's exactly
  (`live-fingerprints-before-run15.txt`); development touched nothing. But the
  prediction located G3's writes "under $LIFE_AGENT_KB/eval/" — in fact the gate's
  bridge appends its decisions and outcomes to the LIVE calibration ledger
  (`decisions.jsonl` +102 rows at `run_id=gate-20260825T215428`, `outcomes.jsonl`
  +22; `reactions.jsonl` untouched), exactly as run 14's did (run 14's 37 gate rows
  already sat in the ledger under its run_id, inside the r11 fingerprints). Gate rows
  are run_id-distinguishable and no live fold moved (Ū conditions on reactions joined
  to decisions; reactions unchanged). A prediction about WHERE, wrong; the invariant it
  protected — no untracked live-state change — holds by the run_id accounting.

### Disclosures (cap-the-arc)

- **D1 — six blind amendments, all committed before any gate ran**, three of them
  catching defects in the pre-registration itself: amendment 1 (the fifth D-8 site
  lives under `scripts/`; recon greped the census's old path and read exit-1 as
  deletion), amendment 2 (mandate 4 claimed byte-identical trace-B events and a 7.2
  assertion that does not exist), amendment 6 (G3(d) as frozen would have failed every
  row by construction — the decision rows record the DECIDER'S regime; the gate's
  frozen fold is a tree-pinned property). The lesson of r05 — audits measure the fix —
  extends to pre-registrations: every frozen clause was re-read against the artefact it
  names before being relied on, and three did not survive contact.
- **D2 — amendment 2's commit carried in-progress src** (utility.py Phase 1) under a
  `docs(r13)` message; the pre-registration itself (`01c080d`) and amendment 1 predate
  every src change, so the freeze-before-build discipline held where it matters.
- **D3 — the leaf-write promise (r12 → M3) discharged, not executed** (amendment 5):
  the design's "dead code removed at M3" assumed a driver-records-for-leaves M2 that
  r12 deliberately did not build; moving the write to today's three callers per leaf
  would multiply spellings 2→6. The single-writer invariant is enforced by the drift
  gates; the move happens at M5 as one move to one place.
- **D4 — `_CELL_PRIORS` retained as a binding** (narrative's partition name now derives
  its values from `REL.PRIORS`), and narrative legitimately keeps two non-D-2 beta
  creates (the coverage tail; the per-claim cell-state re-materialization) — both named
  in the drift gate.

### Verdict

**M3 is DONE**: one fold entry point with two declared, structurally-enforced evidence
policies, the fold identity covering the regime; one reliability posterior behind the
seam with its priors in one table; the M2 shims dead as amended; every gate green with
the priced 7.3 a PASS at run 14's own numbers. The ladder proceeds to **M4 — the
utility atom + the price table** under its own pre-registration (M4's report also
decides Q8 and signs the M5a/M5b split).
