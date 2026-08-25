# r15 — collapse M5: the argmax absorption (design §2, §5.1–5.2, ladder §8 M5)

> Pre-registration. Committed BEFORE any `src/` change on this branch; the RESULTS
> section is appended after the gates run and nothing above it changes. Amendments
> before a gate runs are blind, appended, and say what they correct. Per M4's report:
> the split is SIGNED as a **single M5**; **Q8 is DECIDED — the M3 live lane deletes**.

## STATE (census claims verified against live tree `a1ed336`, 2026-08-26)

Every anchor below was read in the live tree before this freeze; census line refs
have drifted and are replaced by what is actually there.

1. **E-1 (family choice).** `EX.decide_via_loop` short-circuits a null `/route` to
   `POST /narrative` and returns the leaf's view directly. The narrative leaf is
   ALREADY EU-decided end-to-end (`NR`: per-claim `optimise{include, withhold}` over
   the wire; terminal action `report` iff any claim clears, else `abstain`) — the fork
   is a short-circuit to a self-deciding leaf, not an unpriced report. What remains of
   E-1's absorption is structural: the route-None case is the space `{report(claims)}`
   ∪ withholds with the leaf specifying the one content-bearing terminal (§2.3's
   signed framing) — a declaration + record change, not a new ranking.
2. **E-4 (miss).** `EX.run_pass` returns an early `"miss"` view on empty candidates
   without consulting the daemon: the host decides a withhold the ranking never saw.
3. **E-12 (latch).** `run_pass`'s `grow_asked` one-shot: first consult WITHOUT the
   grow block; on a withholding terminal with unapplied grow probes, exactly one
   re-ask WITH it. The census: the space always carries the grow rows; the daemon's
   `grow_value` self-gates on terminal EU, so the split consult is transport economy
   elevated into a host choice.
4. **L-3 (scoped rows).** `LK._scoped_option`: the HOST picks V_s = the freshest
   dated observation (`max(dated, …)`), then the engine prices `scoped_eu`
   server-side. The absorption: one `report_scoped_j` row per dated candidate value,
   engine-priced with the attested (recency-off) posterior; the host pick dies; "no
   dated ⇒ disabled" becomes an empty option set.
5. **L-9 / B-6 (typed-else-narrative).** `ask._typed_lookup_applies` + the
   fallthrough in `ask.answer`: a declined route or zero grounded observations falls
   to the narrative path — the §9 no-hard-zeros routing, duplicated host-side from
   E-1's executor fork.
6. **B-1 / B-5 (dispatch).** `ask.ask_once` chooses executor-vs-in-process
   (`executor=`, `--legacy`, availability fallback NAMED); `ask.answer` holds the
   in-process family dispatch (`families=`, `gather=` forks). Two hosts choosing
   between two decision paths.
7. **B-4 (weak retrieval).** `ask.retrieval_is_weak` + `WEAK_SCORE_FLOOR` /
   `MIN_STRONG_HITS` (env-tunable) + the `SEAM.GATE_WEAK_RETRIEVAL` commit +
   `SM.mirror_gate` in `ask.answer`: a belief-side threshold enacted as a
   pre-emptive abstain before any ranking. S-1's split: this gate DIES (belief —
   few/weak observations ⇒ the argmax withholds by EU); `GATE_EXECUTOR_DOWN` stays
   as §6.5's unavailability record.
8. **GA-1…GA-3 (gather).** `core/gather.py` whole module (`gather_answer`, the
   `owner_scoped` single-pass fork, weight-ranked `_top_candidates`); callers:
   `ask.answer`'s `gather=` fork and `scripts/answer_brain_gate.py` (an off-path
   Stage-0 comparison script). Gathering is a K row the daemon already prices
   (retrieval grows); the module is a hand-priced VOI in host clothes.
9. **M-1…M-5 (the membrane live lane).** `CFG.membrane_live()` branch in `AC.drive`
   (live consult replaces the shadow mirror), `CRS.live_decide` + `LIVE_TIMEOUT_S`
   in `membrane/coarse.py`, the flag-gated lane in `bridge/server.py`,
   `config.MEMBRANE_LIVE_ENV`, `seam.py`'s docstring references, and
   `scripts/eval_executor.py`'s use. Q8 DECIDED: the lane deletes; `CO.map_action`
   survives as the shadow worker's measurement function (already shadow-called).
10. **Leaf write tails (r13 amendment 5).** `LK.decide_and_record` and
    `NR.narrative_answer` each call `REC.record_local` leaf-side; the driver posts
    separately on the executor path. §5.1: the leaf returns, THE DRIVER records —
    one place a decision becomes two records; `decision_id = akey.cache_key`
    verbatim.
11. **Terminals-only readiness.** `DEC.REGIMES` already carries `"terminals-only"`
    (stamped by nothing today); `RET.retrieve_set` and `SYN.synthesize` live in
    core (the bridge itself calls them in-process); the LK/NR leaves are core
    modules. Everything the regime needs exists in core except the orchestration,
    which lives in `scripts/ask.py:answer`.
12. **`AC._ready`** requires BOTH bridge and daemon `/ready`; a down stack yields
    abstain + the §6.5 unavailability record (`regime: unavailable`).

## MANDATE (one conceptual move: after M5 the driver holds no choice the ranking could make)

Availability partition after M5 (§2.3 + §6.5, Q1 signed α):
**full** (stack up: `T ∪ K`, daemon prices) · **terminals-only** (stack down, skin up:
the driver runs the absorbed in-process orchestration, the skin ranks `T`, regime
recorded) · **unavailable** (no engine at all: §6.5's record, unchanged, never folds
as abstain).

Phases, each landing green before the next starts (G2 runs cumulatively per phase):

- **P-I — deletions.** (a) The M3 live lane dies: `drive` always shadow-wraps;
  `live_decide`/`LIVE_TIMEOUT_S`/the bridge lane/`MEMBRANE_LIVE_ENV`/the seam-doc
  references die; `map_action` stays (shadow measurement, Q8); `scripts/eval_executor.py`
  re-pointed at `drive` or retired with its doc line. (b) `core/gather.py` dies with
  `ask.answer`'s `gather=` fork and `scripts/answer_brain_gate.py` (off-path, references
  the dead module). (c) B-4 dies: `retrieval_is_weak`, the two constants + env knobs,
  the `GATE_WEAK_RETRIEVAL` commit + mirror, and the seam gate itself (S-1 split).
- **P-II — executor absorptions.** (a) E-4: the empty-candidate early return dies —
  the daemon is consulted with empty candidates (`p_none = 1` territory); `miss`
  becomes a REASON via the one withhold-reason derivation (D-5:
  `unavailable ≻ miss ≻ dispersed`, one function, `run_eval`/`LK.render`/
  `EX.render_view`/GATE labels become callers). (b) E-12: the latch dies — every
  consult carries the sensors + grow block; the loop enacts kernels and re-consults
  until a terminal (the daemon's own `grow_value` self-gating is the rule that makes
  this behaviour-preserving; the wire request shape changes and is a named 7.2 class).
- **P-III — the dispatch absorption.** `ask.answer`'s orchestration moves to
  `core/terminals.py` (retrieve via `RET`, covariates, LK leaf, narrative
  fallthrough, temporal scoping intact) — the terminals-only regime's body, called
  by `drive`'s down-branch (stack down, skin up) and by nothing else. `ask_once`
  loses `executor=`; `--legacy` dies from argv (interaction-contract doc updated);
  the REPL always calls `drive`. B-6/L-9's typed-else-narrative inside the absorbed
  body is declared as the terminals-only ranking's no-hard-zeros rule (§2.3 keeps
  the leaves as leaves). jarvis gains terminals-only through `drive` with no change
  of its own.
- **P-IV — the leaf write tails move (r13 A5).** `LK.decide_and_record` and the
  narrative leaf return `(decision, artefact_key)`; the ONE driver (both regimes)
  writes the §18.9 node + posts/appends the ledger row via the one recorder;
  `decision_id = akey.cache_key` preserved verbatim; terminals-only decisions
  post with `regime: "terminals-only"`.
- **P-V — L-3 scoped rows + E-1 declaration.** One `report_scoped_j` row per dated
  candidate value, engine-priced on the attested posterior; the host V_s pick dies.
  E-1: the route-None short-circuit is re-stated as the declared space
  (`{report(claims)}` ∪ withholds, leaf-specified content) — record gains the
  regime/space honestly; no new ranking machinery (the leaf already decides).

**Stays, deliberately:** the LK/NR leaves as pure functions (not shims — §2.3); the
daemon wire contract §2.4 untouched (no cross-repo change; trusted-by-contract);
`SEAM.commit` the one act seam; §6.5 unchanged; the shadow feed + `map_action`;
D-4/D-6's remaining view-derivations beyond what P-I/P-II touch are NAMED RESIDUE
for M6/M7's register pass, not silently absorbed here.

## DIRECTIONS (7.2 — this checkpoint has named behaviour-change classes, unlike M3/M4)

Pure equality is NOT the oracle everywhere. The classes, pre-registered:

- **DIR-B4** (in-process weak-retrieval fixtures): the pre-emptive abstain dies; the
  outcome is EU-decided. Direction: few/weak observations withhold by EU (§16 —
  derived, not patched); the abstention text/provenance changes; a flip to report is
  a FINDING to disclose, not an auto-fail, unless it flips a named wrong-class row.
- **DIR-B** (all trace-B / in-process fixtures): records gain `regime:
  "terminals-only"` + driver-posted bodies (the M2 record-change pattern); body
  equality on the decision content, presence-change on the record fields.
- **DIR-E4** (miss fixtures): the wire gains a consult; the effector becomes a
  withhold with reason `miss` — label-view equality (same reason derived), wire
  shape changed.
- **DIR-E12** (every trace-A fixture): the first consult's request carries the grow
  block; replies must be decision-equal (the daemon's self-gate is the invariant
  being tested); fixtures whose recorded payloads cannot serve the grown request are
  the r09-named unservable class — counted and named, never silently passed.
- **DIR-L3** (dated-candidate fixtures): scoped rows per dated candidate; on
  single-dated-value questions the decision is equal by construction; multi-dated
  questions are a named class read row-by-row.
- **DIR-RETIRED**: gather-flag fixtures and any membrane-live fixtures retire with
  their code paths — listed by name in the results.

## GATES

- **G1** — full suite + ruff + mypy clean, per phase and on the final tree.
- **G2 (7.2)** — `collapse_replay --checkpoint m2-base`, cumulative per phase,
  PYTHONHASHSEED=0: equality outside the named DIR classes; every DIR-class fixture
  accounted to its class in the results (counts per class, no silent membership).
- **G3 (7.3) — run 17**, fired via the run-16 recipe (fire script + tree gate with
  M5 pins, rehearsed `RUN17_GATE_ONLY=1`, transient systemd --user unit, cap $8).
  Frozen conjuncts: (a) P(Δ>0.05) ≥ 0.90 at δ=0.05; (b) zero NEW wrong commits —
  NEW = a row not wrong in run 16's typed arm (its wrongs: the two standing rows);
  (c) no named wrong-commit class worse (superset-confirm, warm-deliberate); (d)
  rows state their regime + `policy="all-to-date"`, tree pinned pre-spend. FAIL on
  any conjunct = STOP for an owner ruling (plan keypress map).
- **G4** — 7.4 not run, declared: no store or path moves; the write MOVES CALLER
  (leaf → driver) but target, schema and `decision_id` rule are pinned by G2's
  body-equality and the recorder's own tests.
- **G5** — PII sweep: no corpus values in tree; hooks armed.

## PREDICTIONS (frozen before any gate runs)

- **P1**: P-I deletes ≥ 400 lines net; zero fixture diffs outside DIR-RETIRED and
  DIR-B4 (the live lane and gather have no non-retired fixtures on the replay set).
- **P2**: P-II's E-12 change produces decision-equal replies on every servable
  trace-A fixture (the daemon's self-gate holds); the unservable count is nonzero
  (the r09 precedent) and every unservable fixture is payload-shape, not
  decision-divergence.
- **P3**: the terminals-only regime never fires in run 17 (stack up throughout);
  its coverage comes from G2's DIR-B class + the seam tests, and the regime's first
  live firing is a production event the readout will show, not a gate event.
- **P4**: run 17 reads within run 16's band — P(Δ>0.05) ≥ 0.90 with zero NEW wrongs
  and answer rate within ±0.06 of 0.62; the two standing wrong rows persist (they
  are not this checkpoint's classes).
- **P5**: live calibration moves only by run 17's own rows under its `run_id`
  (prefix-hash verification; interleaved live `run_id="ask"` rows possible and
  disclosed, per r14).
- **P6**: no named wrong-commit class changes membership in either direction
  (the absorbed dispatch does not touch matching, tempering, or the §5 dedup).

## AMENDMENTS (blind — appended before P-II's gates ran; each corrects a frozen claim against a verified artefact)

**A1 — E-4 re-scoped: the censused death is REFUTED by the daemon's own wire
contract.** STATE item 2 and the mandate's P-II(a) inherited the census claim that
"the argmax with an empty candidate set already ranks the withhold terminals … the
daemon is consulted every time". Verified against the deployed engine
(`answer-brain/daemon/server.jl`): `decide_response` hard-errors on empty
candidates — ``k >= 1 || error("`candidates` must be non-empty")``. A k=0 consult is
not a decision the host stole from the ranking; it is a request the wire refuses.
§2.4 (trusted-by-contract, no cross-repo change this checkpoint) therefore re-types
the empty-candidate early return as the wire's ENACTMENT CONSTRAINT — mechanics, the
same logic as §6.5's "the derived behaviour needs an engine" — and it STAYS, with its
comment re-stated to name the contract. What survives of P-II(a): the D-5 one
withhold-reason derivation (``unavailable ≻ miss ≻ dispersed``), one function with
the named consumers as callers. DIR-E4 narrows to zero wire change and zero fixture
impact.

**A2 — E-12 re-scoped: the first-consult grow block is UNBUILDABLE host-side, and
the latch decomposes into verified non-choices plus ONE measurable residue.** The
censused endpoint ("the one decision space always carries the grow rows") requires
``sensors`` on every consult; sensors are derived from the PREVIOUS decide's
posterior (``GO.sensors_from`` over credences/p_none), so no first consult can carry
them without the stateless daemon computing its own — a daemon-side change §2.4
excludes. The latch's arms, decomposed against the verified engine source
(`answer_brain.jl`: "Grow self-gates on the terminal EU … a confident report prices
≈ −cost"): (i) no-grow-before-first-decide = the sensor dependency (mechanics);
(ii) stop-after-a-grow-block-consult-returns-a-terminal = obedience (the daemon saw
every unapplied grow and declined them); (iii) no-re-ask-after-a-REPORT = the
engine's own ≈−cost pricing, exact for confident reports, UNPROVEN for
low-confidence ones — the single genuine residue. Disposition: the residue is
MEASURED at $0 before any code change, by replaying every recorded A-loop ``/decide``
exchange whose reply was a report against the LIVE daemon with the grow block added
(sensors derived by the DEPLOYED ``GO.sensors_from`` from the recorded reply's own
posterior — the deployed rule end-to-end, never re-implemented; r10's lesson).
Frozen consequence, before the probe runs: **zero effector flips ⇒ E-12 is
re-classified verified-economy/mechanics and no code changes** (the fixture set
stays intact); **any flip ⇒ the residue is real, and the fix (the grow re-ask fires
after reports too) lands with its cassette-miss fixture cost counted under
DIR-E12.** P2's unservable-count prediction transfers to the flip>0 branch only.

**A3 — P-IV re-scoped: the single-writer invariant is already satisfied in substance;
the residual move would be churn without semantics.** Verified against the live tree
before any P-IV code: every decision has exactly ONE writer — the full regime's typed
decisions ride the M2 poster (`ask_client.post_decision`, the only writer on that
path; M2's 7.4 gate verified one-write-per-decision); the full regime's route-None
narrative and both terminals-regime families write through `REC.record_local`, whose
callers are exactly the two family leaves (one call site each — the "two writes" of
the census moved into the one recorder at M2 as §2.2's fate row required). Hoisting
those two calls further (into the bridge endpoint and the driver's down-branch) would
re-route the same two records through more plumbing for byte-identical output — the
kind of move r05/r10 taught us to refuse. P-IV lands as: (i) this amendment, (ii) a
drift gate pinning `record_local`'s caller set to exactly the two leaves, so a third
writer or a second spelling fails loud. r13 amendment 5's debt is closed by
declaration + gate, not by relocation.

**A4 — DIR-L3's equality clause named the wrong oracle layer; the whole lookup-leaf
class is wire-unservable.** DIR-L3 froze "on single-dated-value questions the decision
is equal by construction" — true of DECISIONS, but the 7.2 oracle matches the exact
WIRE, and L-3 changes every lookup decision's ``optimise`` request body (the flat
``report_scoped`` row died — undated questions lose a row; dated questions carry
``report_scoped_j`` rows instead; ``expect`` calls go per-candidate). The cassette
cannot serve a recorded reply to a request that was never asked, so ALL 102 replayable
B-lookup fixtures become the same named wire-shape class as DIR-E12 (P-V read: 165
raises = 63 DIR-E12 + 102 DIR-L3-wire, every one ``CassetteMissError``, ZERO decision
divergences among the 149 servable). The oracle for M5's final tree is therefore: the
149 servable fixtures (posters, narrative, seam, snapshots) + the unit suite's
behavioural pins + run 17's priced conjuncts; the post-M5 re-record restores the full
set. A registered request-transform that would serve old replies to new requests was
considered and REFUSED — a reply recorded for a different action set is not evidence
about this one.

## Deviations

Disclosure items in the final report; rollback = revert the branch (one PR). After
green: results appended, mirrors updated, PR/CI/merge, steel deploy (executor,
ask_client, lookup, narrative, membrane, bridge, ask all move — bridge + jarvis
restart), then M6 (E-7 verify-only) under its own pre-registration.

## RESULTS (read 2026-08-26, appended after the gates ran — nothing above changed)

Execution was five phases on branch `collapse-m5`, each landing green before the next
(P-I `4e5debd` deletions; P-II `f6bf3a9` executor absorptions; P-III `d9f5d4e` the
dispatch absorption; P-IV+P-V `22ba0f0`), under four blind amendments (A1–A4), every
`src/` change TDD'd RED-first.

### What the amendments settled (each against a verified artefact)

- **A1 (E-4):** the daemon hard-errors on k=0 (`server.jl`, verified) — the censused
  "consulted every time" is unbuildable over this wire; the early return is the wire's
  enactment constraint and stays. D-5's one reason derivation landed instead
  (`decisions.withhold_reason`, three callers).
- **A2 (E-12):** the first-consult grow block is unbuildable (sensors are
  posterior-derived); the latch decomposed into two proofs and ONE measurable residue —
  and the $0 probe read the residue REAL: **62 of 63** recorded economy-class report
  consults flip to a scheduled re-read when shown the block, up to EU 0.88 (the
  engine's "grow prices ≈ −cost after a confident report" holds only at credence ≈ 1).
  Per the frozen consequence the fix landed: the grow offer follows EVERY terminal.
- **A3 (P-IV):** the single-writer invariant verified already satisfied; drift-gated
  (`record_local`'s callers are exactly the two family leaves). r13 A5's debt closed.
- **A4 (DIR-L3):** the frozen equality clause named the wrong oracle layer — L-3
  changes every lookup `optimise` body, so the 102 B-lookup fixtures join the named
  wire-shape class.

### Gate readings

- **G1 — GREEN** per phase and on the final tree: 2704 passed; ruff + mypy clean.
- **G2 (7.2), cumulative per phase:** P-I **314/314 pure equality** (DIR-B4 and
  DIR-RETIRED both empty on the replay set — better than P1 predicted); P-II 251/314
  (63 = DIR-E12, all `CassetteMissError`, zero divergences); P-III 251/314 (all 105
  B-fixtures GREEN under the registered DIR-M5 regime direction; the §6.5 replay
  driver now forces the no-engine situation its fixture models); final **149/314
  identical · 165 misses = 63 DIR-E12 + 102 DIR-L3-wire, 100% cassette-shape, ZERO
  decision divergences** among the servable. The full-set oracle returns at the
  post-M5 re-record.
- **G3 (7.3) — FAIL on two conjuncts.** Run 17 (`gate-20260826T025059`), comparison
  arm run 16's meta, spend $4.51 of the $8 cap, tree gate pre-spend at `22ba0f0`.
  **(a) FAIL:** P(Δ>0.05) = **0.743** (gate ≥ 0.90); Δ̄ = **+0.238** [−0.220, +0.736].
  **(b) FAIL by the frozen letter:** typed wrongs {the two standing rows + the
  warm-deliberate wobble row}; the wobble row was withheld in run 16's typed arm, so
  its wrong here counts NEW under the frozen definition — it is simultaneously the
  standing run-13 class (wrong in runs 13 and 15 and live in run 14; both dispositions
  now observed repeatedly), which the ruling may weigh but this reading does not
  renegotiate. **(c)** the warm-deliberate class reads WORSE than run 16
  (withheld → wrong); superset-confirm unchanged (withheld). **(d) PASS** — 102/102
  decision rows `policy="all-to-date"`, `regime="full"`; tree pinned.
  Answer rate typed **0.49** (run 16: 0.62) · mono 0.97; correct-report 0.46 (run 16:
  0.61); withheld miss 2 · **dispersed 51** (run 16: 37); deliberate fired 71/104
  (run 16: 41), warm 65.
- **G4 — 7.4 not run**, declared (A3's gate covers the writer topology).
- **G5 — GREEN.** No corpus values in tree; hooks armed.

### Predictions vs readings

- **P1 — CONFIRMED+.** ~1,500 net lines deleted at P-I; zero fixture diffs (both named
  classes empty on the replay set).
- **P2 — TRANSFERRED by A2 and CONFIRMED on the flip>0 branch:** 63 unservable, every
  one payload-shape, none decision-divergence.
- **P3 — CONFIRMED.** The terminals-only regime never fired in run 17 (stack up;
  102/102 rows regime="full"); its coverage is the DIR-M5-directed fixtures + the
  seam/driver tests.
- **P4 — REFUTED.** Run 17 does NOT read within run 16's band: answer rate 0.49 is
  outside ±0.06 of 0.62, and the headline collapsed (0.961/+0.519 → 0.743/+0.238).
- **P5 — CONFIRMED** (accounting): decisions +102 and outcomes +106 under the run's
  `run_id`; the live ledger's movement is the gate rows.
- **P6 — REFUTED on the warm-deliberate class** (withheld → wrong vs run 16); the
  superset-confirm class held.

### The mechanism (diagnosis for the ruling, not a renegotiation)

The failure is A2's fix meeting the engine's calibration. With the grow block offered
after every terminal, the daemon schedules a re-read on essentially every report (the
probe's 62/63, confirmed live: deliberate firings 41 → 71, dispersed withholds
37 → 51). The bought evidence JOINS the channel (r09 semantics — nothing erased), and
on marginal reports the joined competing observations disperse the posterior below the
assert bar: the arm withholds where run 16 reported correctly. The engine's grow
pricing (hand-set Beta priors over recovery, `grow_value` against terminal EU) values
the information at more than the realised Δ says it is worth — the hand-priced VOI the
census wanted to retire is, on this reading, MIS-priced when exercised at full reach.
The old report-economy skip was, empirically, load-bearing protection — the same
structural lesson as run 13's "dispersal was the protection".

### Ruling required (the FAIL branch, plan keypress map)

Master is UNTOUCHED (M5 lives on `collapse-m5`, unmerged; live runs M4). The branch
parks pending an owner ruling; a conferral document with the options and prices
accompanies this report (`docs/unification/conferrals/run17-conferral.md`).
