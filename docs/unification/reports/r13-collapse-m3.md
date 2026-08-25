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
(CLAUDE.md tail + design §8 row), PR, CI, merge, steel deploy, then M4 under its own
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
