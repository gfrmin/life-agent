# Module-collapse design — one argmax, one fold, one atom

> **Status: draft for owner + reviewer review (2026-08-19) — the design-doc phase of
> tranche 2 (the module collapse); review of this document gates the implementation
> phases, which are briefed from it, not before it.** Composes with
> [`PRINCIPLES.md`](../PRINCIPLES.md) §15–§16 (the object: *one optimiser, learning by
> running*), [`bayesian-foundations.md`](./bayesian-foundations.md) §4/§8/§10 (utility, gate,
> accounting), [`unified-ledger-design.md`](./unified-ledger-design.md) (tranche 1: the
> stream every record lands on; the golden harness A1–A14 this design's §7 reuses where a
> store is touched), and the tranche-1 end state (the unified stream dual-written beside the
> legacy stores; the pkm lineage micro-tranche landed at `b83dbc0`). It rests on **one
> input of record**: the module-collapse census
> [`unification/reports/r00-collapse-census.md`](./unification/reports/r00-collapse-census.md)
> **plus its placement addendum** ("Rulings applied — 2026-08-19": the `873860a → b83dbc0`
> correction table, the reviewer's Q-R1…Q-R5, the owner's signatures Q-O1…Q-O6 and r04 Q4
> with the reviewer's sharpenings). Census rows are cited as *census §n* / *E-n, L-n, D-n…*
> with the census's own abbreviations (`EX`=`core/executor.py`, `LK`=`core/lookup.py`,
> `NR`=`core/narrative.py`, `GATE`=`core/gate.py`, `DEC`=`core/decisions.py`,
> `SEAM`=`core/seam.py`, `BR`=`bridge/server.py`, `SH`=`membrane/shadow.py`,
> `W`=`membrane/world.py`, `CO`=`membrane/coarse.py`, `SES`=`membrane/session.py`,
> `ASK`=`scripts/ask.py`, `AC`=`core/ask_client.py`, `GA`=`core/gather.py`,
> `RX`=`core/reactions.py`, `UT`=`core/utility.py`, `DL`=`core/deliberate.py`,
> `PR`=`core/probes.py`, `VOL`=`core/volatility.py`, `GO`=`core/gather_outcomes.py`,
> `CAL`=`core/calibration.py`, `O`=`core/outcomes.py`); every locator is the census's line
> **and**, where the addendum's correction table moves it, the `b83dbc0` line after an arrow
> (`EX:190-205 → :203-218`). Unchanged rows are not re-verified; the four fresh claims this
> document makes carry their own transcripts in the phase report
> (`unification/reports/r01-collapse-design.md`, "fresh transcripts F1–F4"). Nothing here
> changes code, `PRINCIPLES.md`, any SPEC, or the daemon; amendments are proposals in
> Appendix A. British spelling; no corpus values; no owner-specific paths.
>
> **Revision 2026-08-19 (post-review, before M0) — adopted as the design of record.** The
> reviewer's rulings and the owner's signatures (r01-collapse-design "Rulings applied") are
> folded in: §2.3 carries the signed (α) for the reach surface (Q1); §6.5 is a register entry,
> not a proposal (Q2: regime value *and* fixture *and* register); §6.3b's procedure is
> pre-committed to M0's wire-shape check (Q4); §7.2 gains the field-class rule
> (value-compared vs presence-and-type) and the per-terminal-type coverage condition (Q9);
> §8 M1 gains its config-surface line, M4's report decides Q8 (default delete), M6 waits on
> Q3's measurement; §9 marks each question resolved with its ruling; Appendix A is signed **at
> M7**, not before. Q5 deferred to M6's transcript. Q7 is applied to the census addendum
> itself (append-only). No section is otherwise changed.

## 0. What this document is

**Thesis, one sentence.** PRINCIPLES §16 made structural: *every question is decided by one
EU ranking over one decision space {terminal responses ∪ transformations}, under one belief
folded through one entry point behind the brain seam, with one utility atom — and every host
mechanism the census found beside that ranking is either declared model content (an error
model), absorbed into the ranking, retired, or recorded as enactment mechanics.*

**Scope.** The 85 mechanisms of census §5, the fifteen duplication clusters of census §4, the
entry points of census §1 and the tunables of census §6 — each receives one verdict and one
disposition (§1); the four "ones" are specified (§2–§5); the exceptions are registered once
(§6); the equivalence instrument is pre-stated (§7); the migration is checkpointed (§8).

**Non-goals.** No reader cutover (tranche 1's stores stay dual-written; this design reads
what tranche 1 writes). No seam swap: `core/brain.py` (the skin wire) and the daemon's
`/decide` wire stay as they are — Q-R3 makes the wire the boundary and the daemon's argmax
and structure-BMA `g` trusted-by-contract (§2.4); the cross-repo daemon census is a named
prerequisite of the *seam* tranche, not of this one. No daemon changes. No new host folds,
ever (Q-O4). No PRINCIPLES/SPEC edits (Appendix A proposes; the owner signs). No touching of
the two gated witnesses (B2-live, A5) or of the pin alignment; an unscoped `pkm extract`
remains a standing no-go — environment notes, not scope.

**Inputs of record and their standing.** The census + addendum (facts and locators); the
signed rulings restated as binding in the tranche-2 brief and cited here by name (Q-R1…Q-R5,
Q-O1…Q-O6, r04 Q4); tranche 1's end state. The three-verdict rule (Q-R1 + Q-O1) is stated
once in §1.2 and applied to everything; nothing below re-derives it.

**How to read a verdict.** *belief-shaping* — the mechanism changes the observation set or
the likelihood the posterior folds → it becomes a **declared error model** (model content,
priced as such, calibrated where the outcomes stream reaches it). *decision-shaping* — it
compares or orders to choose an action → it goes **into the argmax or dies** (dies = the
ranking already implies it, or it was a hand-priced VOI beside the priced one). *mechanics* —
it sequences the same work → **enactment**, out of the collapse's scope, recorded so the
next census does not re-list it. One verdict per mechanism, per Q-R1; where a census row
bundles two clauses, the row's verdict is the clause that decides, and the disposition names
where the other clause goes.

## 1. The classification table

### 1.1 The worked example, and the first collapse target: E-14

`core/gather_outcomes.py:9-11` declares that the sensor bucketing exists *so that* the
`p_none`-vs-leader comparison is model input to the daemon's grow structure `g` and "never
control flow" (census §2, `GO.sensors_from :54-63` — the `hi`/`mid`/`lo` buckets); on the same
axis, `EX._truth_likely_missing` (`EX:190-205 → :203-218`) compares `p_none ≥ leader` and uses
the result as **control flow** on the legacy lane — the cascade `((True,False),(True,True))`
runs while the effector withholds and the comparison holds (E-13, `EX:278-294 → :291-307`);
the module calls it "no magic threshold" (`:195 → :208`) while it is a fixed comparison
choosing an action (census D-3, first row). Two files, one repository, one doctrine
contradicted — the reviewer's sharpening on Q-O1 names it the strongest single §16 violation
on the list.

**Verdict:** decision-shaping. **Disposition:** dies. The decision it makes — *grow now?* —
is already the daemon's priced grow row (`GET /grow_menu` → `GO.GROW_ACTUATORS :47-51`,
scheduled by `/decide` with the sensors block, trace A `EX:463-465 → :476-478`); the
comparison itself survives only where the doctrine puts it, as the `p_none` sensor feature
of `g` (M-9/GO-1, belief-shaping, kept). The legacy lane (E-13) and its flag
(`LIFE_AGENT_GROW_LANE`, census §6) retire with it. **Equivalence obligation (§7):** on the
recorded view→decision fixtures the priced lane must reproduce every *terminal* the cascade
reached — a swap of the comparison's direction is the seeded defect the fixture set must kill.
**Migration:** checkpoint M1 (§8), first, alone.

### 1.2 The rule, stated once (Q-R1 + Q-O1)

For each mechanism *m* in census §5 and each cluster in census §4: if *m* changes the
observation set or the likelihood the posterior folds → **belief-shaping** → a declared
error model; else if *m* compares or orders to choose an action → **decision-shaping** →
into the argmax or dies; else *m* sequences the same work → **mechanics** → enactment. The
exemplars fixed by the ruling: belief-shaping L-1, L-2, BR-2, E-7, E-10; decision-shaping
E-4, E-14, G-1's threshold, M-2, the D-3 rows; mechanics E-2, E-6, U-2, M-11 — every row
below is consistent with them. Where the disposition is "declared error model", the model
content is *named*, not written here: what is declared, and that it is declared once, is the
design; its parameters are the implementation phase's, calibrated from the outcomes stream
where the stream reaches them.

### 1.3 The table — 85 mechanisms + D-1…D-15

Locators: the census's line, then `→ :new` where the addendum's correction table (or the
finer per-cite map in the phase report, F1) moves it. † = a census line inside a hunk the
addendum marks *rewritten* (`EX:512-519`, `:605-610` — the null-read fail-open landed after
the pin); the arrow gives the line that now carries the mechanism, from fresh transcript F2.

| id | verdict | disposition | locator (census → b83dbc0) |
|---|---|---|---|
| **E-1** | decision-shaping | **absorbed** — the family choice is a row of the one decision space: `route None` is a posterior view (no recognised construct), the narrative terminal is priced beside the lookup terminals; the fork dies | `EX:251-258` → `:264-271` |
| **E-2** | mechanics | **kept as mechanics** — enactment order of the k=0 walk ("the one place enactment order is body-held"); recorded, not priced | `EX:374-419` → `:387-432` |
| **E-3** | belief-shaping | **declared error model** — the rescue channel's reliability is the edge's reliability posterior (D-2, cold prior), not `min(0.5, conf)`; the clamp dies into the prior | `EX:163` → `:176`; `EX:411-414` → `:424-427` |
| **E-4** | decision-shaping | **dies** — the argmax with an empty candidate set already ranks the withhold terminals (p_none = 1); `miss` becomes a label-view of the withheld action (D-5), the daemon is consulted every time | `EX:420-427` → `:433-440` |
| **E-5** | decision-shaping | **dies** — `lambda_usd` is a `REQUIRED_LATENT` of Ū (§4); the `1.0` fallback is unreachable under a well-formed model and moves to the one price table as a declared constant, or fails loud | `EX:434` → `:447` |
| **E-6** | mechanics | **kept as mechanics** — the loop bound sequences the same work; declared, tested, not priced | `EX:491` → `:504` |
| **E-7** | belief-shaping | **declared error model** — a re-read/deliberate is a *second observation channel* combined by the likelihood at its own reliability, never a replacement of the grounded channel; the replace-branch dies (this is the branch the n_obs=0 cluster points at — §9 Q3) | `EX:515` → `:540-541`†; `EX:585` → `:610`; `EX:605-608` → `:635-637`† |
| **E-8** | belief-shaping | **declared error model** — cold-start and unseen-edge fall out of the reliability posterior's prior (D-2), absent confidence conditions at the prior, not at bin 0; the constants die | `EX:184-187` → `:197-200` |
| **E-9** | belief-shaping | **declared error model** — reliability and model are keyed by edge id in the one price table + reliability posterior; an unknown probe name is an error, not a default | `EX:501-502` → `:514-515` |
| **E-10** | belief-shaping | **declared error model** — a retrieval grow's result is new observations through the grounding gate (L-1); "adopt iff grounded" is L-1 applied, so it collapses with L-1 into the grounding error model | `EX:526-531` → `:551-556` |
| **E-11** | mechanics | **kept as mechanics** — an infrastructure failure yields no observation (correct: no evidence) and marks the row unavailable for this pass; availability is a fact the menu carries, not a choice | `EX:558-560` → `:583-585`; `EX:578` → `:603` |
| **E-12** | decision-shaping | **dies** — the one decision space always carries the grow rows; the argmax ends the loop by choosing a terminal, so the one-shot re-ask latch has nothing to decide | `EX:615-625` → `:643-653` |
| **E-13** | decision-shaping | **dies** — the legacy cascade is a hand-ordered VOI (E-14's twin); the daemon-priced grow lane is the same decision priced; the lane flag retires with it (§8 M1) | `EX:278-294` → `:291-307` |
| **E-14** | decision-shaping | **dies — first collapse target (§1.1)** — `p_none ≥ leader` as control flow contradicts `GO:9-11`; the grow decision is the daemon's priced row, `p_none` stays a *sensor* feature of `g` (M-9/GO-1) | `EX:190-205` → `:203-218` |
| **E-15** | mechanics | **kept as a pure view** — leader-first order and the abstain reason are labels derived from the decision record by the one derivation (D-4 label-view, D-5) | `EX:667-686` → `:695-714` |
| **L-1** | belief-shaping | **declared error model** — the grounding predicate is a likelihood term of the observation model (an ungrounded quote is not an observation), declared once, its reliability calibrated from outcomes; E-10 folds into it | `LK:439-448`; `LK:621-625` |
| **L-2** | belief-shaping | **declared error model** — correlated duplicates are one attestation: the collapse rule + witness choice become the declared correlation structure of the observation model (the reach audit's dedup guard is its consumer) | `LK:797-809` |
| **L-3** | decision-shaping | **absorbed** — `report_scoped` per dated candidate becomes `report_scoped_j` rows priced by the engine with the time covariate; "no dated ⇒ disabled" is an empty option set (no EU mass), the host pick of V_s dies | `LK:1018-1020` |
| **L-4** | belief-shaping | **declared error model** — candidate identity (ISO date / digit string / casefold) is the observation equivalence relation, declared model content | `LK:394-409` |
| **L-5** | belief-shaping | **declared error model** — the era structure of the observation set is model content (a declared partition rule now; a latent with a prior when learned — §9 Q5) | `LK:433-436` |
| **L-6** | belief-shaping | **declared error model** — the recency covariate's functional form incl. undated/future cases, one declared policy with D-14/N-4/BR-3/P-1 | `LK:320-325` |
| **L-7** | belief-shaping | **declared error model** — the subject partition is the owner-subject error model (already a table; declared once) | `LK:298-309` |
| **L-8** | belief-shaping | **declared error model** — source-class reliability priors (document/email/note/other), declared; learnable later | `LK:451-459` |
| **L-9** | decision-shaping | **absorbed** — route None / zero observations ⇒ narrative is E-1's family choice (a row); the `effective_ti` suppression for `historical`/`as_of` moves with L-6 into the declared time policy | `LK:1162-1170` → `:1165-1173`; `LK:1164` → `:1167` |
| **L-10** | belief-shaping | **declared error model** — group competition = min over members is a declared aggregation of the covariate; stated once | `LK:856` |
| **L-11** | mechanics | **kept as a pure view** — `report_j → report` is a render label (the census: not a second decision) | `LK:911-912` |
| **N-1** | belief-shaping | **declared error model** — the cell classifier is the claims' observation model (verified/unsupported/unverifiable), population-calibrated per cell; declared once | `NR:179-191` |
| **N-2** | decision-shaping | **dies** — implied by the per-claim argmax: the answer is the included set, empty ⇒ withhold; the reason is a label-view (D-5) | `NR:381-385` |
| **N-3** | mechanics | **kept as a pure view** — display order; `mean·tf` is a display readout, disclosed | `NR:373`; `NR:379` |
| **N-4** | belief-shaping | **declared error model** — the claims' time covariate is one policy with L-6 (D-14) | `NR:429-430` |
| **N-5** | mechanics | **kept as an invariant** — a closed vocabulary hard stop (D-6's one vocabulary pins it) | `NR:206-207` |
| **G-1** | decision-shaping | **named exception (register §6.1)** — the verdict mechanism (frozen δ/level) is the blindness that makes runs comparable; kept, reason stated once (Q-O2) | `GATE:73`; `GATE:76`; `GATE:349` |
| **G-2** | decision-shaping | **within the G-1 exception** — censoring/exclusion rules are the verdict mechanism's definition of the comparison; kept with G-1, stated in the register | `GATE:144-149`; `GATE:328-334` |
| **G-3** | belief-shaping | **declared approximation, debt-listed (§6.3b, §9 Q4)** — a host Gaussian-moment sampler for P(U) approximates the wire posterior; retires when the seam exposes posterior sampling; no new host folds | `GATE:196-200` |
| **G-4** | mechanics | **kept as a pure view** — the 90 % interval is a summary of the Δ posterior | `GATE:352-353` |
| **R-2** | belief-shaping | **declared conditioning set** — latest verdict per `(decision_id, kind)` is part of the fold's evidence policy (Q-O5), stated once | `RX:185-187` → `:188-190` |
| **R-3** | belief-shaping | **declared error model** — which verdicts become utility evidence is the one verdict→evidence projection (D-15), stated once | `RX:194` → `:197` |
| **R-4** | belief-shaping | **declared error model** — the implied abstain-threshold datum is part of the projection (D-15) | `RX:139-147` → `:142-150` |
| **R-5** | belief-shaping | **declared error model** — the narrative branch of the projection (D-15); the host `a/(a+b)` becomes a wire `mean`, and the coverage *bar* (D-3 row) dies: coverage enters the datum as a covariate, not a gate | `RX:157-168` → `:160-171`; `RX:134` → `:137` |
| **U-1** | mechanics | **kept as a diagnostic view** — a monitor that prints | `UT:243-249` |
| **U-2** | mechanics | **kept as mechanics** — fold choreography | `UT:332-336` |
| **S-1** | decision-shaping | **split** — `GATE_WEAK_RETRIEVAL` **dies** (weak retrieval is belief: few/weak observations ⇒ the argmax withholds by EU, §16 derived not patched); `GATE_EXECUTOR_DOWN`/`GATE_ENGINE_DOWN` are **kept as the seam's unavailability record** — no optimiser ran, so no decision was priced; recorded as an unavailability event, distinct from an abstain decision (register §6.5, §9 Q1) | `SEAM:102-103` |
| **B-1** | mechanics | **availability-driven, no longer a choice** — one driver (Q-O6) runs the loop; when the daemon is unavailable the same seam runs the terminals-only regime (§2.3) and the record says so; `--legacy` as a *choice* dies | `ASK:1242` → `:1243`; `ASK:1482` → `:1510` |
| **B-2** | decision-shaping | **unified into S-1's unavailability path** — through the seam on every driver; A-1's seam-less `DOWN` bypass dies (Q-O6) | `ASK:1003-1015` → `:1004-1016` |
| **B-3** | mechanics | **kept as mechanics** — a feature flag composes the menu (row availability); the `None`-curves rho fallback dies with E-8 | `ASK:1034-1038` → `:1035-1039`; `ASK:941-942` → `:942-943` |
| **B-4** | decision-shaping | **dies** — the weak-retrieval predicate is a threshold beside the posterior it approximates (D-3); the argmax withholds by EU on the same evidence | `ASK:777-784` → `:778-785`; `ASK:630-633` → `:631-634` |
| **B-5** | decision-shaping | **dies** — driver dispatch (families/gather) is replaced by the one driver over the one decision space | `ASK:792-818` → `:793-819` |
| **B-6** | decision-shaping | **absorbed** — typed-answered-else-narrative is the family choice (E-1); a lookup with no observations has no mass, the narrative row is ranked | `ASK:636-644` → `:637-645`; `ASK:822` → `:823` |
| **B-7** | decision-shaping | **dies** — the monolithic instrument is the adoption gate's comparator, not a live terminal; it survives inside the eval harness only (outside the decision site) | `ASK:836-837` → `:837-838` |
| **A-1** | decision-shaping | **dies** — see B-2 (Q-O6: one driver, one seam) | `AC:118-119` |
| **A-2** | mechanics | **kept as mechanics** — see B-3 (one driver, one menu composition) | `AC:99-107` |
| **A-3** | mechanics | **dies** — the one poster records every decision once, family-agnostic; the eligibility filter (D-10) has nothing to filter | `ASK:958-960` → `:959-961` |
| **GA-1** | decision-shaping | **dies** — gathering is a transformation priced by the argmax; the `owner_scoped` fork to a single pass is a hand-priced VOI | `GA:128-131` |
| **GA-2** | decision-shaping | **absorbed** — gather targets are grow rows priced by VOI; ranking by posterior weight is a heuristic VOI the engine owns | `GA:71-83` |
| **GA-3** | belief-shaping | **declared error model** — with L-5 (era structure) | `GA:164-166` |
| **BR-1** | belief-shaping | **declared error model** — volatility is a declared prior over the construct's half-life; whether it *overrides* or *combines with* the route model's verdict is model content stated once (§9 Q5) | `BR:189` |
| **BR-2** | belief-shaping | **declared error model** — the value-join is the observation-equivalence rule for re-reads (with L-4), one function (D-11), declared once | `BR:353-386` → `:361-395` |
| **BR-3** | belief-shaping | **declared error model** — one recency policy (D-14) | `BR:305-324` |
| **BR-4** | belief-shaping | **declared error model** — the re-read edge's rho/model come from the price table + reliability posterior; its fixed `authority=1.0`/`subject=1.0` covariates are declared model content (learnable) | `BR:345-349`; `BR:396-397` → `:405-406` |
| **BR-5** | mechanics | **one poster** — the poster's shape (Q-O6); the leader-first sort is a label-view (D-4); `run_id` default declared once | `BR:778-781` → `:789-792`; `BR:791-794` → `:802-805`; `BR:802` → `:813` |
| **BR-6** | mechanics | **kept as mechanics** — ledger write validation; the `folds` echo dies (a copy of R-3; one projection D-15) | `BR:837` → `:848`; `BR:842` → `:853`; `BR:849` → `:860` |
| **BR-7** | mechanics | **kept as mechanics** — config validation | `BR:514-519` → `:525-530` |
| **BR-8** | belief-shaping | **declared error model** — when the deliberate edge yields an observation (ok only; non-ok ⇒ none) is the edge's failure semantics; the warm-hit `cost 0` moves to the price table | `BR:606` → `:617`; `BR:613-615` → `:624-626`; `BR:622-623` → `:633-634` |
| **BR-9** | mechanics | **kept as mechanics** — shadow availability | `BR:1021-1024` → `:1032-1035` |
| **M-1** | decision-shaping | **dies with the M3 live lane** — a second optimiser's rewrite of the daemon view; the membrane keeps measuring off-path (register §6.2) | `CO:112-113` |
| **M-2** | decision-shaping | **dies** — a host MAP (D-4); the sanctioned argmax owns the leader | `CO:73-78` |
| **M-3** | decision-shaping | **dies** — "cheapest unapplied voi in menu order" is a hand-priced VOI beside the priced one | `CO:85-89` |
| **M-4** | decision-shaping | **dies** — a restricted host argmax with first-listed ties beside the engine's | `CO:90-102` |
| **M-5** | decision-shaping | **dies with M-1** (as an unavailability record it is S-1's) | `CO:151-155` |
| **M-6** | belief-shaping | **declared error model** — owner ≻ Claude precedence is part of the one verdict→evidence projection (D-15), stated once | `SH:1084-1085`; `SH:1121-1127` |
| **M-7** | belief-shaping | **declared error model** — the `_VERDICT_Y` exclusions and the terminal-effector predicate are the projection's declared domain (D-15) | `SES:60-64` |
| **M-8** | decision-shaping | **named exception (register §6.2)** — the membrane world's utility table + report-side EU arithmetic: a deliberate second world whose distance from Ū is the measurement (Q-O3); never on the path, never tuned toward Ū | `W:214-245`; `W:286`; `W:295` |
| **M-9** | belief-shaping | **declared error model** — feature bucketing is the sensor vocabulary of `g` and of the world (model inputs, "never control flow"); declared, kept | `W:141-174` |
| **M-10** | decision-shaping | **absorbed** — tie-breaking is the argmax's own, declared and pinned by a test (§7's seeded defect); "first-listed" becomes an explicit rule, not a grid accident | `W:19-22`; `W:33-37` |
| **M-11** | mechanics | **kept as mechanics** — sizing and timeouts | `SH:118-131` |
| **DL-1** | mechanics | **kept as mechanics** — instrument-internal retry | `DL:308` |
| **DL-2** | belief-shaping | **declared error model** — a blind decline is a non-observation (the poison guard); the edge's failure semantics stated once with BR-8 | `DL:331-336` |
| **DL-3** | belief-shaping | **declared error model** — output validation of the edge (out-of-range credence ⇒ no signal) | `DL:114` |
| **DL-4** | mechanics | **kept as mechanics** — subprocess environment | `DL:231-234` |
| **P-1** | belief-shaping | **declared error model** — a date-source rule of the one recency policy (D-14) | `PR:111-112` |
| **P-2** | belief-shaping | **declared error model** — the subject-verdict → state map is the owner-subject error model (with L-7) | `PR:153` |
| **P-3** | mechanics | **kept as mechanics** — retrieval over-fetch and top-k | `PR:201-205` |
| **V-1** | belief-shaping | **declared error model** — the volatility prior table; first-match order made explicit as a declared rule (§9 Q5) | `VOL:52-54` |
| **GO-1** | belief-shaping | **declared error model** — with M-9 (sensor vocabulary) | `GO:59-63` |
| **GO-2** | belief-shaping | **declared error model** — the grow model's cold prior when no rows: correct, declared | `GO:91` → `:93`; `GO:105-106` → `:107-108` |
| **D-1** | decision-shaping | **collapse onto the atom** — `decide.u_assert` is the source; `LK.action_utilities` and `GATE.realised_utility` derive from it (no fourth abstraction, Q-O3); `W.utility_by_action` is the register's second world (§6.2) | `DEC:60` |
| **D-2** | belief-shaping | **one reliability posterior behind the seam** — `LK.extractor_reliability` and `NR.population_posteriors` are the same wire fold keyed by (edge, cell); unified as `reliability(edge, cell)`; `CAL.fit_reliability_curve` = the confidence-conditioned view of it with monotone smoothing = the named debt (§6.3); `O.reliability_bins`/`ece` = declared diagnostic views | `LK:503` |
| **D-3** | decision-shaping | **per row: into the argmax or dies** — E-14 dies; `GO.sensors_from` stays a sensor (belief, M-9); `ASK.retrieval_is_weak` dies (B-4); `GATE:349` is the G-1 exception; `RX._COVERAGE_BAR` dies (R-5: coverage is a covariate of the datum) | `EX:190-205` → `:203-218` |
| **D-4** | decision-shaping | **the sanctioned one + one label-view** — engine `report_j` (`LK:869,:882`) is the argmax; the four host copies become one derived `leader(view)` used for labels only; `CO._respond` dies (M-2) | `LK:869`; `LK:882` |
| **D-5** | mechanics | **one derivation** — withhold-reason as a single view function over the decision record (`unavailable ≻ miss ≻ dispersed` declared once); the per-surface copies die | `LK:944-949` |
| **D-6** | mechanics | **one declared vocabulary** — `decisions.py` holds the action space; every partition (assert/withhold, terminal, lookup/narrative order, membrane affordance map) is a derived view; the drift test pins them | `DEC:41`; `DEC:52-54` |
| **D-7** | decision-shaping | **one price table** (§4) — menu rows carry cost + model + edge id; the `rho`s move to the reliability posterior's priors (D-2); the tier ladder is one row set | `EX:64-74`; `EX:92-95` |
| **D-8** | belief-shaping | **one `posterior()`, two declared evidence policies** (Q-O5) — the regime indicator; §3 | `LK:985-994` |
| **D-9** | mechanics | **one driver** (Q-O6) — `answer_via_executor` + `ask_client.answer` become one function with one `/log_decision` body; closes D-10 and B-2/A-1 | `ASK:985-1048` → `:986-1049` |
| **D-10** | mechanics | **dies** — with A-3 (one poster records every decision) | `ASK:958-960` → `:959-961` |
| **D-11** | belief-shaping | **one function** — the value-join (BR-2) declared once | `BR:353-386` → `:361-395` |
| **D-12** | mechanics | **one constructor** — the edge-id namespace `<kind>@<model>` | `EX:102` → `:115` |
| **D-13** | mechanics | **one config surface** — env names read once in `config.py` | `CFG:116-118` |
| **D-14** | belief-shaping | **one recency policy** — one function, its input-selection declared (doc_date of value-carrying hits ≻ self-reported `as_of` ≻ undated), used by lookup, bridge and narrative | `LK:312` |
| **D-15** | belief-shaping | **one projection** — verdict → evidence (owner ≻ Claude; the `_VERDICT_Y` domain; abstain-only lookup datum; narrative margin datum with coverage as covariate) declared once, three consumers | `SES:60-64` |

### 1.4 Tallies and what they say

Of the 85 mechanisms: **36 belief-shaping** → declared error models; **27 decision-shaping**
→ 6 absorbed into the argmax (E-1, L-3, L-9, B-6, GA-2, M-10), 16 die (E-4, E-5, E-12, E-13,
E-14, N-2, B-4, B-5, B-7, A-1, GA-1, M-1…M-5), 1 folded into another's path (B-2 → S-1), 1
split (S-1), 3 named exceptions (G-1, G-2 within it, M-8); **22 mechanics**. Of the fifteen
clusters: 5 belief-shaping declared once (D-2, D-8, D-11, D-14, D-15), 4 decision-shaping
(D-1 onto the atom, D-3 row by row, D-4 the sanctioned argmax + one view, D-7 one price
table), 6 mechanics → one function / one vocabulary / one config surface (D-5, D-6, D-9,
D-10, D-12, D-13). Three readings: (i) the error-model column is where the
belief content of the system has been hiding in host code — thirty-six declarations is the
size of the observation model that has never been written down as one; (ii) sixteen deaths
are the §16 violations proper, and every one of them is a hand-priced VOI or a threshold
beside the posterior it approximates — none is a capability, so nothing is lost when they go
except the paths' names; (iii) the mechanics column is enactment, and its size (22 + 6
clusters) is why PRINCIPLES §15 needs the wording Appendix A.2 proposes — "the spine is
transport" has to say that *enactment order and bounds are recorded, not priced*, or the next
census re-lists them.

## 2. The one decision site

### 2.1 The ranking

**Decision space.** `A = T ∪ K`: the terminal responses `T` (the closed vocabulary of
`DEC.ACTIONS :41-42` — report / report_scoped / hedge / ask_clarify / abstain, per candidate
where the action asserts one: `report_j`, `report_scoped_j`; the narrative terminal
`report(claims)` whose claim set is the per-claim leaf, §2.3) and the transformations `K`
(every row of the one price table §4: the corroborate tiers, retrieval grows, re-extract,
deliberate; each with edge id, model, cost, and its reliability from D-2). One row set per
question, composed by availability (which instruments are up — mechanics), never by a host
choice.

**Inputs.** (i) the posterior views: the lookup `V` posterior over candidates + NONE
(`LK.lookup_posterior :821`, wire), the per-edge reliability `ρ` (D-2, wire), the claim-cell
posteriors for the narrative terminal (`NR.population_posteriors :212`, wire), the sensor
block for `g` (M-9/GO-1); (ii) the priced menu (§4); (iii) `Ū` from the one `posterior()`
under the *all-to-date* policy (§3). **Output.** One chosen element of `A` with its EU, the
credences it was ranked over, and the accounting the record needs (§5.1) — a terminal ends
the question; a kernel is enacted (mechanics) and the site is consulted again with the new
observations, until a terminal is chosen. **Ranking rule.** EU under Ū, `u_assert` the atom
(§4), by credence: the daemon's `/decide` for the transform-and-terminal ranking
(trusted-by-contract, §2.4) and the skin's `optimise` (`brain.py:289`) for the
terminals-only regime (§2.3) — the same rule computed by the same engine family, reached
through the ONE act seam `SEAM.commit :96` (census §1.5, the five sites verbatim). What
changes is not the engines but the *hosts around them*: after the collapse there is exactly
one host driver, and it makes no choice the ranking could have made.

### 2.2 The fate of every entry point (census §1.0, §1.1, §1.6)

| Entry point (census) | Fate | Why / how |
|---|---|---|
| `SEAM.commit :96` | **the site** — kept, unchanged in kind | already the one act seam; gains nothing but callers' honesty (S-1's split, §1.3) |
| daemon `POST /decide` (via `SEAM.DaemonDecide`, `EX:470-471 → :483-484`) | **the ranking** (Q-R3, §2.4) | over the full `A`; the terminals-only regime is the same rule via `SkinOptimise` |
| `EX.decide_via_loop :222 → :235` (the body) | **the one driver's loop** — kept as enactment | its 15 host choices dispositioned in §1.3; after M1–M5 it holds no choice: it composes the menu (availability), enacts the chosen kernel, re-consults, records |
| `ASK.answer_via_executor :985 → :986` + `AC.answer :110` | **one function** (Q-O6) | the reach surface and the CLI call the same driver with the same `/log_decision` body; closes D-9, D-10, B-2/A-1 |
| `ASK.answer :647` (the in-process families) + `ASK.ask_once :1229` dispatch (B-1, B-5) | **absorbed into the driver as the terminals-only regime** (§2.3); the dispatch dies | when the daemon is unavailable the driver runs the same seam over `T` and the record says which regime ran; when it is up, `T ∪ K` |
| `LK.lookup_answer :1142 → :1145` / `LK.decide_and_record :1041 → :1044` / `LK.decide :894` | **leaves, not entry points** — kept as pure functions the site calls | observation shaping (`observe_hits`) stays the declared error models of §1.3; `decide` is the terminals-only ranking call; `decide_and_record`'s two writes move to the one recorder (§5.1) |
| `NR.narrative_answer :447` / `NR.decide_claims :346` | **the narrative leaf** — kept, called by the site | the per-claim `SkinOptimise` is the terminal `report(claims)`'s specification (§2.3); its writes move to the one recorder |
| `GA.gather_answer :103` (GA-1…GA-3) | **dies** | its gathering is a `K` row priced by the daemon; its owner-scoped fork and weight-ranked targets are hand-priced VOI (§1.3) |
| `BR._log_decision :765 → :776` | **the one poster's endpoint** — kept | one body, no optional accounting fields (§5.1) |
| `core/decide.py u_assert :60` | **the atom** (§4) | source of every host utility spelling (Q-O3) |
| `core/decisions.py` | **the one vocabulary + the log** (§5.2) | partitions become derived views |
| `core/deliberate.py` | **a `K` row's instrument** | its internal choices are edge failure semantics (DL-1…DL-4, §1.3) |
| `core/pricing.py` | **the price table's spend half** (§4) | `PRICE_TABLE :33` joins the one table |
| `core/probes.py` | **transformations' bodies** — kept | read-only over the catalogue; their choices are declared error models / mechanics (P-1…P-3) |
| `core/gate.py delta_posterior :308` | **named exception** (§6.1) | off the decision path by construction (offline, human-read effect — trace C) |
| `core/brain.py optimise :289` | **the seam's engine call** — kept | `value :296` — dormant-keep iff §2.5 claims it (Q-R4) |
| `membrane/*` (`session.decide :131`, `categorical.decide_categorical :249`, `CO.map_action :105`, `CO.live_decide :137`, `SH.decide_live :474`) | **shadow only** — the M3 live lane (M-1…M-5) **dies**; the shadow feed and its records stay | a second optimiser's rewrite of the daemon view cannot coexist with one argmax; the shadow's *distance* from the decision is the measurement (§6.2) |
| `ASK:778` / `ASK:1008 → :1009` (the two gate-only commits) | **one dies, one is re-typed** | `GATE_WEAK_RETRIEVAL` dies (belief); `GATE_EXECUTOR_DOWN` becomes the seam's unavailability record (S-1, §6.5) |

### 2.3 Regimes: full and terminals-only — one rule, two declared spaces

The in-process path (trace B) and the executor path (trace A) are today two decision paths
with two hosts choosing between them (B-1, B-5). After the collapse they are **one driver
over one rule with two declared decision spaces**: *full* (`T ∪ K`, the daemon up) and
*terminals-only* (`T`, the daemon unavailable — the skin ranks the terminals over the
same posterior and the same Ū). The regime is a **fact of availability recorded on the
decision** (a field of the one `/log_decision` body, §5.1), never a choice: nothing in the
host may prefer one regime when both are available, and a terminals-only decision is not
"the fallback lane" of the retired uncalibrated fallback — it is the same ranking with an
empty `K`, honestly recorded. This is the Q-O5 regime-indicator pattern applied to the
decision space rather than to the evidence set, and it is what lets the in-process families
survive as *leaves* rather than as a second site. **Signed (Q1, α):** the terminals-only regime *is*
wanted on the reach surface — an unavailable daemon answers over `T` with the regime honestly
recorded, rather than going mute; the M0 field makes the frequency measurable and 7.3's
arm-split prices the quality difference; revisited on the count.

**The narrative terminal.** `report(claims)` is one element of `T` whose *content* is the
per-claim EU rule (`NR.decide_claims :346`, per claim `SkinOptimise`): the site prices the
terminal at `Σ eu_include` over the included set (census N-2: `eu = Σ eu_include :385`), the
leaf computes that set as a pure function of the claim posteriors and Ū. Nested, but not a
second decision: the leaf never compares terminals against each other or against kernels —
it specifies one terminal's content. (Reviewer Q9, §9, signs this framing.)

### 2.4 The daemon-wire contract (Q-R3) — trusted-by-contract, tabled

| Wire | Request (census cite) | Reply | Trust statement |
|---|---|---|---|
| `POST {daemon}/decide` (`SEAM.commit(DaemonDecide)`, `EX:457-473 → :470-486`) | `candidates`, `observations`, `rho`, `u_bar`, `era_split`, `owner_scoped`, `applied_probes`, `transforms`; with the grow lane `sensors` + `grow` (`EX:459-465 → :472-478`) | the `View` (`EX:48-49`): `effector`, `asserted`, `candidates`, `credences` (in candidate order — the poster sorts leader-first, `BR:791-794 → :802-805`, a label), `p_none`, `eu`, `n_obs`, `hits`, `route`; the executor arm adds `n_indeterminate`/`n_competing` (poster body) | the daemon prices `net_voi − cost` and arg-maxes over `transforms` ∪ terminals (`EX:3-6`); its structure-BMA `g` over the sensors is its own (`GO:3-6`). Trusted-by-contract: the request/reply shapes above ARE the contract; the daemon's internal ranking is not re-derived host-side, and the seeded-defect fixtures (§7) pin the shapes, not the arithmetic |
| `GET {bridge}/utility` (`EX:428 → :441`, `BR._utility :635 → :646`) | — | `u_bar` (Ū's posterior means + gauge, `UT.u_bar :259`) | one Ū (§3, §4); the daemon reads it, never folds it |
| `GET {bridge}/grow_menu` (`BR:639 → :650`) | — | `actuators` (`GO.GROW_ACTUATORS :47-51`) + warm counts (`GO.warm_counts :87 → :89`) | the grow rows of the price table (§4); the counts condition `g` daemon-side |
| `POST {bridge}/route`, `/retrieve`, `/probe/*`, `/extract`, `/probe/corroborate`, `/probe/deliberate` (trace A) | per capability | observations / covariates / a re-read channel | transformations' bodies (mechanics + declared error models); no ranking |
| skin `optimise` (`brain.py:289`, via `SEAM.SkinOptimise`) | `state_id`, action utility vectors (`LK.action_utilities :864`, `NR._include_fn :310`) | `(action, eu)` | the terminals-only ranking and the narrative leaf; same engine family, same rule |

**Recorded obligation for the seam tranche (Q-R3):** the cross-repo daemon census (its
`/decide` argmax, `g`, tie-break, and the exact treatment of `u_bar`) is a named prerequisite
there; until then the contract above is what this design relies on and what §7 pins.

### 2.5 `brain.value` — the claim (Q-R4)

The VOI building block PRINCIPLES §16 names. **Claimed here as the consumer's slot:** the
one decision site prices a kernel at *E[U | after k] − E[U | now] − cost* — the daemon's
`net_voi` today; when the terminals-only regime gains any kernel (a first in-process
transformation), the skin's `value` is the wire that prices it. This claim earns
"dormant-keep" **iff** the implementation phase adds the wire-shape test the ruling requires
(§7: `value(state_id, action_utilities) → float`, pinned like `optimise`); the test is a
checkpoint deliverable in §8 (M0), not a promise. Unclaimed at M0 → dead surface, dies.

## 3. The one fold entry point

### 3.1 `posterior()` with a declared evidence policy (Q-O5, D-8)

One entry point, `utility.posterior(brain, model, evidence, *, policy)`, where **`policy`
is a regime indicator** naming a *declared conditioning set*, not a boolean:

- **`frozen-elicitations`** — the model file + the committed elicitation set, nothing else
  (`scripts/run_eval.py:1663-1668`, `gate_splice.py:106-108`, `membrane/p3_gate.py:433-435`,
  `fairfight/loss_ledger.py:531-533` — census D-8): the gate's regime, the blindness that
  keeps runs comparable (Q-O2's utility-fold half is governed here, not by the exemption).
- **`all-to-date`** — elicitations + the verdict→evidence projection (D-15: `R.load_reactions`,
  `LK.current_u_bar :985-994`): the decider's regime, the reaction loop alive.

Both regimes are the *same fold* over the *same model*: `_fold_1d`/`_fold_joint`
(`UT:339,:393`, wire), `fold_version :275` covering the policy name so the memo (`LK:991-993`)
never serves one regime's Ū to the other's caller. Every caller names its policy at the call;
D-8's five sites become five callers of one function with two spellings of `policy`. The
Dawid reading, made explicit so it never degrades into a flag: the two regimes are two
conditioning sets over one probability model, and *which* set a decision was ranked under is
part of that decision's record (§5.1).

### 3.2 D-2 — which reliability estimator survives

**One reliability posterior behind the seam: `reliability(edge, cell)`** — a Beta family
conditioned on the outcomes stream through the wire, keyed by the edge id (D-12's one
constructor) and a cell. Its two current instances are the same wire fold with different
cell keys and priors: `LK.extractor_reliability :503` (edge = the extractor, one cell,
`Beta(4,4)` prior `:190-191`, conditioned per graded outcome `:492-500`) and
`NR.population_posteriors :212` (edge = the claim instrument, cell ∈ {verified, unsupported,
unverifiable}, `_CELL_PRIORS :78-83`). They unify: one function, the cell key an argument, the
priors declared per (edge, cell) in the price table's reliability column (§4). What the
argmax reads for a kernel's `ρ` (`EX:428 → :441` … `_conditioned_rho :166 → :179`) is this
posterior — E-3, E-8, E-9, BR-4's constants die into its priors.

**`CAL.fit_reliability_curve :82` is the confidence-conditioned view of the same posterior with
monotone smoothing across confidence bins** — the one host fold, the named debt (§6.3): kept as
is until the seam offers a monotone (isotonic) fold; its retirement path is realistic (the
reviewer's sharpening: outcome-log depths ~10²–10³ refolded per ask are the shape the engine
serves comfortably) — a credence backlog item with a known cost envelope, a successor of
this tranche, not a change in it. **`O.reliability_bins :208 → :211` and `ece :230 → :233`
become declared diagnostic views** (they never feed a decision — census §2), not beliefs. No
new host folds, ever.

### 3.3 The observation model, declared once

The thirty-six belief-shaping rows of §1.3 are the observation model's clauses: the grounding
predicate (L-1/E-10), correlation structure (L-2), candidate identity and the value-join
(L-4/BR-2/D-11), covariates (L-6/L-7/L-8/L-10; the one recency policy D-14 with N-4/BR-3/P-1;
volatility BR-1/V-1), era structure (L-5/GA-3), the re-read as a second channel (E-7), edge
failure semantics (BR-8/DL-2/DL-3), the sensor vocabulary (M-9/GO-1/GO-2), the claim cells
(N-1), and the verdict→evidence projection (D-15: R-2…R-5, M-6, M-7). The design's demand is
structural, not numeric: each clause is *one* declaration with *one* home, its parameters
listed in §4's table where they are prices/priors and in the module that owns the clause
otherwise, and every consumer reads the declaration. The implementation phase writes them
where they are (no new module is required by this design — Q-O3's "no fourth abstraction"
applies to the model too); what it may not do is leave two spellings of one clause.

## 4. The one utility atom, and the one price table

### 4.1 D-1 with direction (Q-O3)

`core/decide.py u_assert :60` — `p·u_correct + (1−p)·u_wrong` — is **the source**.
`LK.action_utilities :864-887` (the online vectors: `report_j` via the atom `:878-879`,
`ask_clarify` at `_ORACLE_P·u_correct − lambda_int :884`, `report_scoped` at `scoped_eu
:886`) and `GATE.realised_utility :163-185` (the offline realised-answer model, per-action
branches `:173-184`, spend `:171`) **derive from it**: each spelled as the atom applied to
its action's `p` and its action's `u` — one function of the vocabulary and Ū, no fourth
abstraction, and the derivation is what §7's fixtures pin (same inputs → the same vector on
both paths). `W.utility_by_action :214-245` does **not** derive: it is the membrane world's
own utility (its literal defaults `:237-239`, its myopic perfect-information pricing of
`gather`/`ask` `:226-234`, "FLAG — this OVERVALUES information, deliberately") — the
register's second world (§6.2), whose distance from Ū *is* the shadow's measurement and is
never tuned toward it.

### 4.2 The one price table

Every priced constant of census §6 that ranks an action, in one declared table (data, one
module, versioned like `PRICING_VERSION :20`), each row: `edge id` (D-12) · `model` · `cost`
(USD or utility, with the exchange rate below) · `reliability prior (α, β)` per cell (D-2) ·
`availability` (mechanics: a fact the driver fills). Its rows today, and where they come from:

| Today | Where (census §6) | Becomes |
|---|---|---|
| corroborate tiers: `_TIER_MODEL`, `_TIER_RHO` 0.80/0.90/0.95, `_GATHER_RHO` 0.95 | `EX:53-57 → :66-70` | three rows; the `rho`s become the tiers' reliability priors (D-2), not fixed reliabilities |
| `DEFAULT_TRANSFORMS` (two guards; three `voi` tiers rho/cost 0.80/0.004, 0.90/0.012, 0.95/0.020) | `EX:64-74 → :77-87` | the same rows — the *menu* IS the table |
| `DELIBERATE_TRANSFORM` rho 0.92 / cost 0.38, `_DELIBERATE_FALLBACK_RHO` 0.5, `_RESCUE_RHO` 0.5 | `EX:92-95 → :105-108`, `:99 → :112`, `:163 → :176` | one row + priors; the two `min(0.5, conf)` clamps die (E-3, E-11's kin) |
| `GROW_ACTUATORS` (rerank 0.004 Beta(3,7); expand 0.006 Beta(3.5,6.5); re_extract_strong 0.020 Beta(4,6)) | `GO:47-51` | three rows (grow); D-7 closes — one table, the daemon reads it via `/grow_menu` |
| `_JOINT_MODEL`/`_JOINT_RHO` 0.95; `_RE_EXTRACT_MODEL` | `BR:77-78`, `EX:154 → :167` | the re-read rows' model + prior (BR-4) |
| `PRICE_TABLE` (per-model USD per token) | `core/pricing.py:33-44` | the table's *spend* half — realised `cost_usd` per firing (§5.1 accounting) |
| `lambda_usd` — the $↔utility exchange rate | a `REQUIRED_LATENT` of Ū (`UT:64-65`); defaulted **`1.0`** at `EX:434 → :447` and **`0.0`** at `GATE:171` | **one source: Ū** (`GET /utility`); the two defaults — different in two modules — die (E-5); a missing latent fails loud |
| `_ORACLE_P` 0.9 (`ask_clarify`'s oracle) | `LK:196`; reused as the gate's `oracle_p` (`run_eval.py:1672`, `gate_splice.py:113`) | one declared constant, one home, both readers |
| `WEAK_SCORE_FLOOR` 4.0 / `MIN_STRONG_HITS` 1 (`LIFE_AGENT_SCORE_FLOOR`/`MIN_HITS`) | `ASK:85-86 → :86-87` | die with B-4 (belief, not price) |
| `_P_NONE_PRIOR` 0.5, `_RHO_PRIOR_A/B` 4/4, `_CELL_PRIORS`, `_COVERAGE_PRIOR` | `LK:190-195`, `NR:78-86` | reliability/coverage priors — the table's prior column (D-2) |

What is *not* in the table: covariate parameters (`_A_*`, half-lives, authority classes —
observation-model content, §3.3), sizing/timeouts (mechanics), the gate's frozen δ/level (the
exception's own, §6.1). The membrane world's defaults (`W:237-239`) stay in the world (§6.2).

## 5. The one poster and the one vocabulary

### 5.1 One driver, one poster (Q-O6)

`ASK.answer_via_executor :985 → :986` and `AC.answer :110` become **one function** — the
driver of §2.2 — with **one `/log_decision` body**: `question`, `retrieval_keys`,
`decision{effector, credences, candidates, p_none, eu, n_obs, n_indeterminate, n_competing,
instrument, cost_usd, latency_s, run_id}` (the union `BR._log_decision` already accepts,
`BR:765-830 → :776-841`), plus two fields this design adds and the record needs: **`regime`**
(`full` | `terminals-only`, §2.3) and **`policy`** (the Ū conditioning set the ranking used,
§3.1). *No accounting field is optional on the poster's side*: a firing that ran unpriced
records `cost_usd: 0.0` with its instrument, never an absent key (today `AC:143-149` posts
none of them — the reach surface's decisions are unpriced in the ledger). The eligibility
filter (A-3/D-10, `ASK:958-960 → :959-961`, `AC:137-138`) dies: **every decision is recorded
once**, terminals-only or full, lookup or narrative — the family-specific `DecisionEvent`
producers (`LK:1124-1138 → :1127-1141`, `NR:519-538`) become the leaves' *return values*, and
the driver posts. This closes D-9, D-10 and the B-2/A-1 seam asymmetry in one move (the
reviewer's sharpening): three rows, one function.

**The one recorder.** `D.record` of the §18.9 answer artefact (`LK:1110 → :1113`, `NR:510`)
and `DEC.append` are the leaves' side effects today; after the collapse the leaf returns
`(decision, artefact_key)` and the driver's poster is the only writer of the decision — one
place where a decision becomes two records (the §18.9 node and the ledger row), the
`decision_id = akey.cache_key` rule (`LK:1138 → :1141`) preserved verbatim.

### 5.2 One vocabulary (D-6), one label-view (D-4), one reason (D-5)

`core/decisions.py` holds the action space (`ACTIONS :41-42`, `FAMILIES :34`); every partition
becomes a **derived view** of it: `LOOKUP_ACTION_ORDER`/`NARRATIVE_ACTION_ORDER` (`:52-54`),
`GATE.ASSERT_ACTIONS`/`WITHHOLD_ACTIONS` (`:84-86`), `EX._WITHHOLD :139 → :152` (adds `miss`),
`BR._TERMINAL_ACTIONS :739 → :750`, `W.AFFORDANCES :35` + `REAL_TO_MEMBRANE :56-61`,
`CO._ENACT_EFFECTOR :60`, `SES._VERDICT_Y :60-64`, `categorical._INFO_ACTS :46` — each a
function of the one vocabulary, drift-gated by one test (the census notes the tests exist per
`DEC:49-51`; the collapse makes them derive rather than compare). `miss` and `gather` are
recognised for what they are: `gather` is a kernel, not a terminal (it leaves `T`); `miss` is
a **reason**, not an action (E-4 dies) — which is D-5: withhold-reason is **one derivation**
over the decision record (`unavailable ≻ miss ≻ dispersed`, `run_eval.py:599-603` today, and
`LK.render :944-949`, `EX.render_view :681-686 → :709-714`, `GATE.WITHHELD_* :95-99` all
become its callers). D-4: the engine's `report_j` (`LK:869,:882`) is the argmax; the four host
`max`/`sorted` spellings (`CO._respond :77`, `LK:1074-1076`, `EX:667-670 → :695-698`,
`BR:791-794 → :802-805`, `W:97`) become one `leader(view)` used for **labels only** — and
`CO._respond` dies outright with M-2.

### 5.3 D-11…D-15, dispositioned

D-11 the value-join → one function (BR-2's error model; `BR:353-386 → :361-395` and `:550-564
→ :561-575` — the census's own `:541-544` says they are the same rule). D-12 edge names → one
constructor (`EX.extract_edge :102 → :115` and `DL.instrument :196` → one `edge_id(kind,
model)`). D-13 env constants → read once in `config.py` (`:116,:118` vs `membrane/client.py:33-34`;
`ASK:875-880 → :876-881` vs `AC:31-33`). D-14 the recency covariate → one function with its
input-selection declared (doc_date of value-carrying hits ≻ self-reported `as_of` ≻ undated;
`LK.time_factor :312`, `BR._source_time_factor :305`, `NR.scope_decay :420`). D-15 the
verdict→evidence projection → one function (`SES._VERDICT_Y :60-64` domain, `claude_verdicts.y
:100`, `RX._lookup_reaction :137 → :140`, owner ≻ Claude precedence `SH:1121-1127`), three
consumers.

## 6. The named-exceptions register

The purpose of this register is that the next census reads it and re-lists nothing here.
Each entry: what, why (once), what it does *not* cover, and the test that pins it.

**6.1 G-1 — the adoption gate's verdict mechanism** (`GATE:349`, δ `:73`, level `:76`; G-2
`:144-149`, `:328-334`). *Why:* the gate is the instrument that adopts optimisers; it is
EU-shaped already (a posterior over Δ under P(U), `GATE:1-6`) and its one non-EU element —
the frozen δ/level threshold — is the blindness that makes runs comparable; folding the
instrument into the optimiser it judges is circular (Q-O2). *Not covered:* the gate's
utility fold — that is `posterior(policy=frozen-elicitations)`, §3.1 — and (open, §9 Q4) its
host Gaussian-moment sampler G-3. *Pinned by:* the existing gate tests + §7's frozen-regime
eval battery. *Q4, executed at M0 (R1 confirmed):* `draw` is served by the engine but
has no method for the measures the utility posterior is built from, so P(U) is not
wire-samplable and G-3 stays inside this exception rather than becoming a 6.3-style debt.
The reading is self-revising —
`tests/test_brain.py::test_live_skin_serves_draw_but_not_for_the_utility_posterior_s_measures`
(system-marked) asserts both `MethodError`s against the pinned image and fails the moment the
engine gains the capability, at which point G-3 moves to 6.3b's retirement path.

**6.2 The membrane world's utility table** (`W.utility_by_action :214-245`, defaults
`:237-239`, perfect-information pricing `:226-234`; `argmax_action :286`,
`respond_threshold :295` report-side; M-8). *Why:* a deliberate second world whose distance
from Ū is the shadow's measurement (Q-O3); tuning it toward Ū would destroy the differential
it exists to measure. *Not covered:* the M3 live lane (M-1…M-5) — that put the second world
*on* the decision path and dies (§2.2). *Pinned by:* the membrane's host-declaration
register + a test that the world's table is not read by any decision-path module.

**6.3 `core/calibration.py` — the one host fold, a named debt** (`fit_reliability_curve :82`,
`_pav :53`, `curve_for :118`). *Why:* the confidence-conditioned reliability curve is a
probability and belongs behind the seam (§16), but a monotone fold is not on the wire today,
and a host rewrite to look like a belief would be the antipattern in another coat (Q-O4).
*Retirement path:* an isotonic/monotone fold behind the seam at outcome-log depths — a
credence backlog item with a known cost envelope, a successor of this tranche. *Rule:* no new
host folds, ever. *Pinned by:* a test that the decision path reads reliability from D-2's one
posterior except through `curve_for` (the debt's one door). **6.3b (procedure pre-committed, Q4):**
`GATE._sample_u :190-200` — a host approximation of P(U) for the offline MC — is decided by
M0's wire-shape check and recorded in M0's report: posterior draws exposed on the wire → a
second debt entry with a short retirement path (sample on the wire); not exposed → inside 6.1's
exception. No further ruling.

**6.4 `brain.value :296` — dormant-keep, conditionally** (Q-R4). *Why:* the VOI building
block §16 names; §2.5 claims it as the wire that prices a kernel in the terminals-only
regime. *Condition:* the wire-shape test at M0 (§8); unclaimed, it dies. *Pinned by:* that
test.

**6.5 The seam's unavailability record** (ruled Q2: register entry *and* regime value *and*
fixture) — `SEAM.commit(gates=…)` for
`GATE_EXECUTOR_DOWN`/`GATE_ENGINE_DOWN` (`SEAM:102-103`; S-1). *Why:* when no optimiser is
available there is no ranking to be inside of; the record is an *unavailability event*, not
an abstain decision, and saying so keeps "safe behaviour is derived, not patched" honest —
the derived behaviour needs an engine. *Not covered:* `GATE_WEAK_RETRIEVAL`, which is belief
and dies. *Pinned by:* the fixture that a down stack yields an unavailability record with no
`decision_id`, and the poster's body carrying `regime: unavailable`. *Why also here:* R-3 folds
abstain verdicts as utility evidence; an unavailability must never fold as an abstain — the
one line a future census would otherwise re-open.

**6.6 Instrument isolation — path-redirection is not isolation; only sinking is.** An
*instrument-design* rule rather than a decision-shaping exception; it lives in the register
because the register is what the next census reads. *Why:* a writer that takes no path
argument falls through to `core/config.py`, so redirecting the configured path does not move
the instrument off the live store — it moves the instrument's writes onto whatever the config
now names, and the C5 dual-write mirror then mirrors them faithfully, because that path *is*
the configured one. Redirection also disarms the guard that would have caught it ("not the
configured path" cannot fire when it is). An instrument must therefore **sink** the append —
replace the writer, not its destination. Learned at M0 by leaking exactly one decision row
onto the owner's stream (r02 DEVIATIONS 1; its provenance is recorded under
`$LIFE_AGENT_KB/ledger/provenance/`). *Not covered:* the §18.9 derivation writer, which takes
its root as an argument and is correctly redirected rather than sunk. *Pinned by:*
`life_agent.collapse.drive.sealed()` and
`tests/test_collapse_record.py::test_the_seal_sinks_decision_appends_so_the_c5_mirror_never_fires`.

**6.7 A gate is a script, not a sentence.** An *instrument-design* rule, added at M0.5 on two
instances one checkpoint apart. *Why:* M0's brief required the tree to be ruff-, mypy- and
guard-clean; its commit script ran the guard, the suite and ruff, and the discipline statement
was left to carry mypy. Thirteen type errors — all in M0's own new files — reached master, and
the report was silent, because nothing executed the claim. M0.5's script runs mypy, which is
the only reason the gap was found at all: the checkpoint that *had* the gate caught the
checkpoint that only had the sentence. The same shape governs rehearsals — a rehearsal that
inherits ambient state (an exported `PYTHONHASHSEED`; a file set present in the working tree
but absent from the commit) is a green that cannot fail, and both instances passed in
rehearsal and failed on the signed run. *The rule:* every condition a checkpoint states is
executed by its own commit script, and the script is rehearsed against a clean checkout of
exactly the file set it will commit, in an environment scrubbed of the variables the check
depends on. *Not covered:* claims about the world that no script can execute (a spend
estimate, a coverage judgement) — those stay prose, and the register is where they are named
as prose. *Pinned by:* the checkpoint commit scripts' own gate sequence (guard, suite, ruff,
mypy, replay), and stated as run in each checkpoint's report.

**6.8 The declared comparator is the only oracle.** An *instrument-design* rule, added at M0.5.
*Why:* the fixture-level delta table wanted a per-fixture digest, and a hand-rolled one was
quicker to write than routing through §7.2's comparator. It reported 91 retrieval moves and 99
decision moves; the declared comparator reported 17 and 6. Both hand-rolled figures were
artefacts — a score drifting in its last bits, and the `run_id` the recorder stamps from the
checkpoint name, a field §7.2 declares *runtime-measured* precisely so that it cannot be read
as a change. The only reason it was caught is that a third reading contradicted it; had the
convenience oracle merely *agreed*, nothing would have been learned and the agreement would
have been quoted as corroboration. *The rule:* every comparison a report states is produced by
`life_agent.collapse.compare.compare_outputs` under the §7.2 field classes; a second comparator
built for convenience is a defect **even when it agrees** — agreement teaches nothing, and
disagreement costs a session establishing which of the two is wrong. *Not covered:* summaries
*of* the comparator's output (counts, groupings, the delta table's rows) — that is presentation,
and stays cheap. *Pinned by:* the comparator's own tests, and by each checkpoint's delta table
being produced by a script that calls it.

**6.9 `probes.probe_corroborate`'s two unordered ties — registered, dispositioned to M1 behind
a trace.** Not an exception this design wants to keep: a *pending fix*, registered here so the
disposition survives whatever happens at M1 — the register is what the next census reads.
*What:* the function dedups candidates keeping the first-arrived on a strict `>`, then sorts by
raw score with no tie-breakers — the same two layers M0.5 declared total orders for at
`lookup.dedup_correlated` and `retrieve_set`, in one place, live whenever the gather lane runs.
*Why not fixed at M0.5:* that checkpoint's one-change rule, and then the standing rule that
makes this entry worth having — **no fixture exercises the gather lane**, so the one-line
declared key would land with no oracle, and an unwitnessed change to the decision path is a
hope, not a fix. *Disposition (ruled at M0.5's review):* record a gather-lane trace first — it
is wanted regardless (§8 M1.5) — then apply the same declared key with the same two kills
(a seed sweep and a direct three-call determinism check including score equality) against it,
at M1's checkpoint. *Fallback, pre-committed:* if the trace proves expensive or awkward, this
entry converts to a standing one naming the source known-and-uncovered, and M1 proceeds without
the fix. *Pinned by:* whichever branch is taken — the trace's fixtures, or this entry.

*Resolved at M1 — by a different oracle than the disposition named.* The precondition ("record
a gather-lane trace first") could not have delivered what it was imposed to deliver: the
function runs INSIDE the bridge, and the fixture set tapes the bridge at the `http` seam, so
replay serves the recorded response and never executes it (`collapse/taps.py`: replay "needs no
daemon, no engine, no API key and no corpus"). A trace would have recorded this function's
ANSWERS, and a reordering inside it would not be exercised on replay at all. Measured, not
argued: on the M1 priced baseline all 309 `/probe/corroborate` calls carry `reextract=True`
(326/326 on the legacy baseline) — the plain branch is 0 calls over 104 fixtures either way, so
recording the surviving lane bought no coverage here. The source is real and R2 did NOT close
it: `probe_corroborate` imports `search` from `pkm.retrieval`, whose SQL ends
`ORDER BY scored.score DESC` with no tie-breaker, while R2's declared key landed in
`life_agent/core/retrieval.py`. **The oracle used instead** is stronger and hermetic: the
function's output must be invariant under a permutation of `search`'s return order. Both layers
were witnessed failing it — a tied dedup returns a different document, a tied sort a different
ranking — and both pass under one declared key `(-round(score, 9), artifact_cache_key,
chunk_text)`, used by the dedup and the sort alike, with a third test pinning that score still
dominates the tie-breakers. *Pinned by:* `tests/test_probes.py`'s three corroborate-order tests.

**6.10 A gate run must pin its tree, not just its recipe.** An *instrument-design* rule, added
at M1 on a failure of my own instrument. *What happened:* `fire-run10.sh` was the run-9 recipe
verbatim plus a TREE gate — clean worktree, HEAD lacks the deleted cascade, HEAD carries §6.9's
declared key. Three assertions about the change under test, none about anything else. Three
further decision-path changes had landed between the two runs (a pre-registered bridge change,
R2's declared order on the primary retrieval path, §6.9's on the probe), all three invisible to
the 7.2 oracle because the fixture set tapes the bridge at the `http` seam. The run read FAIL on
one wrong commit and **no argument can say which of the four changes bought it**. *The rule:* a
gate whose result will be compared against an earlier run must record the decision-path tree it
ran against — the file set and its hashes — and diff that against the comparison run's, naming
every difference in the report. A recipe-verbatim gate is not a tree-verbatim gate, and
"nothing else changed" is a claim that needs an instrument like any other. *Why a register entry
rather than a one-line fix:* the same shape recurred twice in one checkpoint (§6.7 was the
first), so the standing hazard is the class — a comparison instrument that pins the foreground
and lets the background float — not this script. *Corollary, and the reason this bites here
specifically:* while the bridge is taped at the `http` seam, **every bridge-side change is
outside 7.2 by construction**, so for those the gate is the only oracle there is; bundling two
of them into one priced run spends the reading without buying it. *Pinned by:* the next gate
run's own report, which must carry the tree diff or say there was none.

*Built at M1, before run 11 fires (the ruling: registering a rule and not carrying it on the
very next run is how a register rots).* `run_eval.decision_path_tree()` hashes a **declared**
file set — `src/life_agent/core/**/*.py`, `src/life_agent/bridge/**/*.py`,
`scripts/eval_executor.py`, `scripts/run_eval.py`: the body, the bridge it decides through, and
the harness that drives the arm. Transport, the act layer, the equivalence instrument and prose
are deliberately excluded — none can move a terminal, and a noisy diff is an ignored diff, which
is the failure mode this is built against. The manifest and its digest land in `run_meta.json`
before the first question, beside the corpus and utility pins. `--compare-run-meta` diffs against
the run this one will be read against and the report names **every** difference, above the
verdict; with no comparison the report says *not diffed* rather than presenting a pinned
background it does not have. **The back-series is comparable too:** every earlier run recorded a
git sha and a dirty flag, and a *clean* sha IS the tree, so `comparison_tree()` reconstructs it
from the commit (`decision_path_tree_at()`); a run recorded **dirty** refuses reconstruction —
it is not its commit, and reconstructing anyway would manufacture the very "nothing else changed"
this entry exists to prevent. Verified live: run 10's recorded commit reconstructs to 45
decision-path files. One divergence was caught by its own test and is worth recording, because
it would have made the pin quietly wrong in the direction of *under*-reporting: `fnmatch`'s `**`
is a plain `*`, so the git-side matcher skipped every file directly under `core/` while the
working-tree side (`Path.glob`) matched them. Both halves now use `PurePath.full_match`. The declaration is **tiered**: `core`/`bridge` are *decision logic*, `eval_executor.py`/`run_eval.py` the *harness*. The harness shapes a run and belongs in the digest, but it moves for reasons that are not decision changes — this pin was itself one — and a diff that fires on every run is a diff that gets ignored, which is the failure mode named above. So a harness-only difference is reported as exactly that, and the note's claim is kept to what a hash can support: a tree diff says WHAT moved, never whether the mover was intended. *Pinned by:* `tests/test_gate_tree_pin.py` (14 tests).

**6.11 Carrier identity — which document represents duplicated text must not decide the
answer.** Registered at M1 on the mechanism run 12 exposed, and given its own checkpoint by
ruling (r04 RULING 4) rather than folded into R6: this is a *decision-model* defect, not an
ordering one, and the difference between the two is the whole point of the entry.

*What:* `core/retrieval.retrieve_set` dedupes the over-fetched hits by `chunk_text` and keeps
ONE — and that survivor's `artifact_cache_key` becomes the text's carrier for the rest of the
decision. Everything downstream is keyed on it: `observe_hits` reads the §4.1 covariates per
artifact (authority from the origin path, `doc_date`, `subject_state`), and `lookup_posterior`
**groups the observations BY artifact**, one `group_noisy_channel` per document sharing r_d.
So the carrier choice sets both the weight on an observation and the *correlation structure* of
the evidence: two chunks that would have shared a document, and been conditioned as one
correlated group, instead land in two documents and are conditioned as more nearly independent
— purely because different copies won their dedups.

*How it is chosen today:* by R2's declared key `(-round(score, 9), artifact_cache_key,
chunk_text)`. Byte-identical text scores identically, so in practice the survivor is the
lexicographically smallest content hash. Deterministic, reproducible, and arbitrary — a coin
flip frozen, not resolved.

*Why a declared order is not the fix here, which is what run 12 bought.* §6.9 declared exactly
this key one layer over on the probe path and the gate convicted it — and the conviction's
content is narrower than it sounds: the key did not add the wrong candidate and did not swap
the leader (the same competitor led in runs 10, 11 AND 12), it **concentrated** the posterior
(p_none 0.126 → 0.066) enough to carry an already-wrong leader from EU 0 to EU +0.044, a hair
over the commit bar. A declared total order buys reproducibility; it does not buy a right
answer, and where the tie is between *witnesses of the same content* it hard-codes an answer to
a question the model should never have been asked. On this corpus what protects the arm from a
wrong leader is dispersion — and how much dispersion survives is currently decided by a hash.

*The tell is already in the tree: the same question is answered twice, by two different rules.*
§5's `lookup.dedup_correlated` collapses a cross-document duplicate quote to the
**max-covariate** document — a substantive rule, and deliberately order-free (`max` returns the
first maximal element "rather than ... the interpreter's per-process hash seed"). `retrieve_set`
answers the same duplicate-witness question with a content hash one layer earlier, and *its*
answer is the one that stands, because by the time §5 runs the losing carriers have already
been discarded. Only one of the two can be right.

*Candidate fix, named before the measurement so it cannot be tuned to it:* carry the carrier
SET on the retrieved hit and make the representative a function of that set rather than of its
order — the §5 max-covariate rule lifted one layer up, with the declared key breaking ties only
*within* equal covariate. Not adopted here: this entry registers the defect, the audit freezes
the criteria, and the fix is bought or refused on the reading.

*What oracle it has, which is less than it looks:* none from 7.2. The fixture set tapes the
§18.9 derivation cache at the `cache` seam, so a replay serves the *recorded* retrieval set and
never executes `retrieve_set` — the same structural blindness §6.10's corollary named for the
bridge, and the reason R2's declared order was invisible to 104/104 fixtures. The oracles are
therefore (1) a hermetic **permutation-invariance** test — §6.9's own kill, and the right shape
here because invariance is precisely the property being bought — and (2) a priced gate run
under §6.10, isolated, one change.

*Pinned by:* `scripts/carrier_audit.py` and the frozen criteria in its docstring (mirrored in
the §14 pre-registration), then whichever branch they take.

*RULED (owner, 2026-08-22, on the reading — QUESTION 2 of r05): §6.11 becomes a **standing
known-and-uncovered source**, and the candidate fix named above is retired as **refuted**.*
The audit read BUILD on exposure — 17 load-bearing questions on each of the two surfaces
against a frozen bar of 5 — but **delivered reach 0**, and the fix is a *provable no-op on
this corpus*: carriers of byte-identical text never differ in authority class, subject state
or date-projection status, so an argmax over the §4.1 covariates always returns what the
declared key already picked. The tell above therefore **overstates the conflict**: on this
corpus §5's max-covariate rule and `retrieve_set`'s content hash agree wherever both can see.
Only one of the two *could* be right; neither is observably wrong here.

Three findings survive the reading, and are what this entry now stands for:

- **The grouping is what is arbitrary, not the representative.** `lookup_posterior` partitions
  observations by carrier, so permuting carriers among byte-identical texts changes how many
  independent `group_noisy_channel`s the evidence forms. Measured bound, both directions: on
  one question a maximum-independence assignment lifts the (correct) leader from a hedge at
  0.683 to a report at 0.975 (EU 0.369 → 0.755); on another the *same* permutation lowers a
  correct leader from 0.985 to 0.961 (EU 0.858 → 0.618). One question in each direction is a
  bound, never a rule — which is why no rule is adopted.
- **The declared key's CONSISTENCY across surfaces is load-bearing and must be preserved.**
  `probes.probe_corroborate` drops a hit whose document is already held (`_fresh_hits`), so
  where carriers straddle the held set the carrier choice decides whether corroboration
  *exists*. All 37 straddling texts measured resolve on the conservative side — the probe
  re-picks the base pass's carrier and the duplicate is dropped — precisely because the same
  function ranks both layers. Any future fix that makes the two layers choose independently
  would admit copies as if independent, defeating §5's dedup guard.
- **No decision-path change is licensed by this entry.** It is registered, measured, bounded
  and left uncovered. A future fix must (a) preserve cross-surface consistency, (b) be scored
  on *both* directions of the grouping bound rather than the helping one, and (c) come with its
  own pre-registration and a priced run — not inherit this checkpoint's BUILD.

*Superseded as the deployment blocker.* The block on deploying the run-10/12 arc named this
entry as what it was waiting for. The reading refutes that premise — carrier identity is not
what makes that arc commit wrongly — so by the same ruling the block is **kept and re-pointed
at §6.12**, which is where the wrong answer actually comes from.

*Successor arc (r09b/r09c/r09d, 2026-08-24/25, $0, nothing fired):* three sweep-gated tempers
against the blocking class, each pre-registered and each STOPPED on its own frozen
consequence — T1/T2, then A1/A2, then the entity anchor. The wire settled what the block is
NOT: not synthesised stacking (r09b), not covariate inflation (r09c — A2 works and the row
never depended on it), and not any decide-side rule that scores documents by
question-vocabulary overlap (r09d — the gold's carrier is systematically the terse one). The
one surviving change is **D3: S2, the replace site r09 left untouched, now joins**, parked
unmerged pending a gate run. **§6.12's block STANDS**, and run 14 is externally blocked by an
API usage limit until 2026-09-01. Hard clause carried forward: no lever ships while
it makes a named wrong-commit class worse.

*Continuation (r09e + r10, 2026-08-25, both $0):* **r09e** replayed run 13's record on the
parked tree itself (66/104 readable — the §18.9 warm-through keeps growing the readable set
pass over pass): two of run 13's four wrong rows still commit wrong there, one is repaired to
withheld, one is cold — so a gate run on this tree fails a zero-wrong conjunct as-is,
measured rather than predicted, and the two decision-level collaterals attribute to the
temper stack, not D3 (a five-row isolation). The **entity-key conferral** then took three
rulings: warm-then-read; the **extract-side entity field RETIRES** (the qualifier is already
carried where an extractor could see it — and where it is not carried, no extractor could
recover it either); and E1's bar frozen blind at zero channel harms AND ≥1 wrong-commit
repair. **r10 built E1** — an exact, typed identifier filter at the base mint, pre-registered
and amended before implementation — **and REFUSED it by its own frozen bar**: the sweep's
marginal read against r09e is exactly one row (the entity-qualifier row, wrong → correct —
conjunct 2 met, the first lever to repair it), but a channel-harm census through the
**deployed** rule found one gold-dropping *inversion* on a row the motivating census had
misread via its re-implemented carrier mapping (the census class's fourth instance this arc
and the first to flip a verdict at a frozen bar). E1 is reverted from the parked chain
(`r10-entity-key` head, tree-identical to the pre-E1 head). **The terse-carrier finding now
closes the carrier-side family in full — exact or fuzzy, hard or soft: a terse gold carrier
omits qualifiers, so any carrier-side requirement damps it.** The queue for 2026-09-01:
warm the one still-cold named row (superset-confirm; the other three now serve at $0), then
a run-14 conferral that picks the tree and freezes the wrong-commit conjunct — the parked
tree measurably carries two standing wrongs; master carries the un-repaired blocking row.

**6.12 The replace branch — a view that DISCARDS a grounded channel instead of joining it.**
Registered 2026-08-22 on r05's redirection (its DONE 4), which is the first evidence that names
this mechanism rather than suspecting it. Like §6.11 this is a *decision-model* defect, not an
ordering one, and it is the class §14 already carried as the n_obs=0 cluster's suspected
mechanism — here caught one step up, at n_obs = 1.

*What:* the executor's enactment loop holds the grounded channel in `obs` / `rho` / `era` and,
at five sites, a probe's reply **replaces** those bindings outright rather than joining its
observations to them. The replacement is deliberate and documented at each site as a
conservative coarsening ("independent-search corroboration is not modelled v0"), on the
argument that a whole-document re-read of the *same* documents is nested inside the evidence it
re-reads. That argument is sound for a re-read of the same documents. It is *not* obviously
sound for an instrument that searches the corpus independently, and it is the deliberate edge —
the independent searcher — where the measured harm shows up.

*The five sites, enumerated from the code and not from the suspicion:*

| # | site | guard on the replace | what is discarded |
|---|---|---|---|
| S1 | the `corroborate_*` tiers | `not _null_read(cr)` — a null read retires the probe fail-open | `obs`, `era` |
| S2 | the retrieval grows (`retrieve_rerank` / `retrieve_expand`) | `bool(n_ext["candidates"])` — a fruitless recall must not erase a posterior | `hits`, `recency`, `ext`, `candidates`, `cand_comp`, `obs`, `rho`, `era` |
| S3 | the `deliberate` edge | `status == "ok"` only — **no null-read guard**: an empty ok reply COLLAPSES the channel, by design (NOT_IN_CORPUS read as evidence for NONE) | `obs`, `era` |
| S4 | `re_extract_strong` in-loop | `not _null_read(cr)` | `obs`, `era` |
| S5 | the k=0 rescue walk | reached only when nothing grounded | nothing — it mints from zero |

*The asymmetry is the entry's sharpest edge.* S1 and S4 were taught in 2026-08-18 that a joint
re-read naming nothing is *absence* of evidence and must not erase a grounded posterior. S3 was
not, and its docstring says so in as many words. Whether that difference is right is an
empirical question — an independent searcher declining to find a value is better evidence for
NONE than a lossy 400-character re-read declining is — but it has never been measured, and the
one row that fails run 10 committed through S3.

*The witness, and why it is not a one-off.* On run 10's wrong commit the grounded channel
carries five observations over four documents with the gold alone at 0.985, invariant under
every carrier permutation measured; the committing view is `deliberate@<opus>` at **n_obs = 1**
with the gold demoted to 0.033, and the recorded wire shows the competitor appearing only after
the gather steps. The population is not one row: 17 of the 19 questions in the registered
n_obs=0 cluster carry candidates at exactly uniform credences — the signature of a grounded
channel a replace branch erased, with the gold still on the lattice in 14 of them.

*What oracle it has:* none from 7.2, for the same structural reason §6.11 has none — the
fixture set tapes the derivation cache and the probe replies are bridge-side. The oracles are
(1) a hermetic test that a replace branch's guard is the *stated* guard (the S1/S4-vs-S3
asymmetry made explicit rather than incidental), and (2) a priced gate run under §6.10,
isolated, one change — bought only if the audit's frozen criteria buy it.

*Pinned by:* `scripts/replace_audit.py` and the frozen criteria in its docstring (mirrored in
the §14 pre-registration), and — since 2026-08-22 — **`scripts/replay_audit.py`**, which reads
the same entry a second way: a $0 replay of the pinned run's questions through the deployed
executor, bridge handlers and live daemon, with every call taped in firing order. It exists
because r06 could name the class but not the culprit, and because its counterfactual is
*enacted* through the deployed guards rather than reconstructed beside them. Its reading is
published BESIDE r06's and may not re-score it (owner ruling, 2026-08-22), then whichever
branch they take. Scope ruled by the owner on
2026-08-22: **every replace/override site**, measured as a class — not the registered
NULL-as-disagreement hypothesis alone, because r05's own lesson is that an audit written around
the presumed fix measures the fix and not the defect.

*Read (r07, 2026-08-22/23, $0, double-run):* attribution lands **S1 ×10 + S2 ×2 confirmed**
(7 more S2 rows named and withheld as draw-unstable); S3, S4 and S5 discard nothing on any
replayed row. A grounded channel was zeroed on 7 questions — S1 on 6, S3 on 1 — and on the
blocking row S1 zeroes the five-observation base before the deliberate edge re-mints the
one-observation competitor, stable across the double run. **The harm rides the disagree path:
an empty non-null reply is a disagree, which retire-not-replace leaves untouched by
construction — the enacted RETIRE arm reads 0 repairs / 1 regression while the JOIN upper
bound reads 10 repairs / 2 regressions.** Every site KNOWN-AND-UNCOVERED under the frozen
bar; nothing bought; r06's criterion 8 untouched. The entry's live successor question is a
correlation key on the wire (so §5's dedup can make a JOIN safe) — decision-path code, its
own pre-registration.

*Ruled (owner interview 2026-08-23 — r07's RULINGS section):* the successor **OPENS** as
checkpoint **r09**, pulled forward to immediately after M1.5 rather than riding M6's E-7 slot
(E-7 becomes verify-only; the m0-5 baseline is re-recorded and O2 re-prepared after it lands).
Run 13's outcome branches are frozen at full delegation: PASS (the gate's frozen δ/level ∧ the
blocking row repaired ∧ zero new wrong commits) closes this deployment block and deploys
master to live; FAIL on any conjunct reverts the JOIN from the deploy path and STOPS for a
ruling. §6.13's repair (r08) lands first so r09's Δ is attributable to the JOIN alone.
*BUILT (r09, 2026-08-24 — `docs/unification/reports/r09-deduped-join.md`).* The §5 key
(quote, doc_key, value_norm — the third field forced by C2's identity in TDD, disclosed)
rides every wire observation, stripped before any decide post; the executor hands its
standing channel to every S1/S3/S4/S5 probe and the bridge returns the §5-deduped pool
(`lookup.dedup_drop_rows` — the ONE rule, `dedup_correlated` delegating; groups re-derived
from doc_key, the bound's group-0 collision dead). A disagree or empty-ok reply pools
nothing: the channel survives — run 7's disagree⇒abstain contract and the deliberate
empty-ok collapse are retired by the ruling's fix, named in the pre-registration. Finding en
route: the base channel arrives already §5-deduped and probe observations are value-only, so
on today's shapes the deduped JOIN is provably idempotent over the raw pool — **r07's upper
bound (10 repairs / 2 regressions) is the expected read for run 13, not a ceiling.** 7.2:
every non-probe fixture replays byte-identically; the 95 probe-firing fixtures are
unservable (the payload grew — the named class; why the baseline re-records post-r09).
**Run 13 (2026-08-24) FAILED two conjuncts (0.895 < 0.90; four new wrong commits — all run-10 dispersals, two of standing named classes) with the blocking row REPAIRED; ruling 4's FAIL branch enacted — the JOIN's code is reverted from master and this deployment block STANDS. STOPPED for an owner ruling.**

**6.13 A declared total order cannot restore determinism when the tie block is larger than
the over-fetch window — the window itself is the sampler.** Found 2026-08-22 by r06's
idempotency double-run, on a question that flapped in and out of that audit's exclusion set
across two identical invocations. Not r06's subject; registered here because it is a
*decision-path* nondeterminism the R2 fix was believed to have closed.

*What R2 fixed and what it could not.* R2 quantised the retrieval sort key's leading term
(`-round(score, 9)`) so that `core/retrieval.retrieve_set`'s key is a genuine total order, and
§14 records the measurement: over the 104-question battery, ordering alone still left 48
questions with a different order and 22 with a different set, and quantising took **both to
zero**. That measurement was taken at k=80 — an over-fetch of `k*4` = 320. The order is
imposed on the rows the over-fetch **returned**, and pkm's FTS ends `ORDER BY scored.score
DESC` with a `LIMIT`, so which of a tied population those rows *are* is decided before the
declared key ever runs. When the tie block fits inside the window the two coincide and the fix
is total. When it does not, the window is a nondeterministic sample of the tie block and no
downstream ordering can undo it.

*Measured, at the arm's own k.* At k=20 the over-fetch is 80 rows. On **1 of 104** questions
those 80 rows carry **five** distinct quantised scores, of which one covers **73** of them: the
top-20 is four stable hits plus sixteen drawn from a 73-way tie whose population exceeds the
window. Five consecutive calls returned five different chunk sets, differing by half the
top-20. The other 103 questions are stable across three calls each — 0 chunks of symmetric
difference — so this is a tail, not a regime. The tail is nonetheless live: on that question
the arm's first pass is a lottery, and everything keyed on the retrieval set (the §18.9
derivations, the carrier assignment of §6.11, the document partition the posterior groups by)
is a lottery with it.

*Why it stayed invisible.* The equivalence instrument cannot see it for the reason §6.10's
corollary and §6.11 both give — the fixture set tapes the derivation cache at the `cache` seam,
so a replay serves the recorded retrieval set and never executes `retrieve_set`. And a gate run
cannot see it either: it is one question, and the run's own report shows a decision, never the
draw that produced it. It took an audit that ran the same read twice on purpose.

*Candidate fixes, named before any measurement of them:* (a) close the tie block — over-fetch
until the score strictly drops below the cut rather than at a fixed multiple, so the window is
never a sampler; (b) push the tie-break into the SQL so the engine's `LIMIT` cuts a totally
ordered stream rather than an arbitrary one; (c) declare the saturated case and refuse to
decide on it. (c) is the cheapest and the most honest, and it composes with `carrier_audit`'s
criterion 1, which already counts a saturated over-fetch window as a reportable limitation
rather than assuming it away. None is adopted here: this entry registers the defect.

*Pinned by:* its own checkpoint, when one opens. Until then it is a **standing
known-and-uncovered source** with a measured incidence (1 of 104 at k=20) and a named witness.
*Ruled (owner interview 2026-08-23 — r07's RULINGS section):* the checkpoint **OPENS** as
**r08**, sequenced before the r09 JOIN checkpoint: its own frozen pre-registration, the repair
landed and verified at **$0** by a multi-draw replay read. Which of the three named fixes is
adopted is r08's pre-registration's to freeze, not this entry's.
*Incidence re-measured at commit granularity (r07, 2026-08-23):* across three fresh draws of
the same 104-question replay at fixed corpus, fixed `src/` and fixed logs, **14 questions
wobble in the committed n_obs** (one of them in firing order) and **22 flap between readable
and cold** — the committed evidence is a wider tail than the retrieval-set instability
suggested, and it sits under every gate reading as a noise floor until one of the three named
fixes is priced.
*REPAIRED (r08, 2026-08-23/24 — `docs/unification/reports/r08-window-determinism.md`).* Fix
(b) was frozen and landed (`src/pkm/retrieval.py`, SPEC 0.18.2): the declared total order is
pushed into the SQL so the engine's `LIMIT` cuts a declared prefix, never a sample. Post-fix:
**zero draw-unstable questions on every surface at both layers** across five calls in two
processes (C2); the decision-visible top-k changed on exactly **one** question at one surface
— the witness at base, inside the straddling census (C6); three replay draws read
**committed-action wobble 0, firing-order wobble 0, n_obs wobble 2 with the
retrieval-attributable component 0** (C5's hard clause) — the noise floor above is retired
from 14 to 2, both residue rows named (monotone accumulation signature, the §18.9
warm-through's suspected class, not diagnosed per the cap). The saturation census (17/15/30
straddling per surface; the witness's boundary block saturates its 2× probe) is published as
the standing arbitrariness record and composes with `carrier_audit` criterion 1.

## 7. Behaviour preservation — the equivalence instrument, pre-stated

**The invariant.** The collapse must not change *what the system decides*: for the same
question, the same corpus, the same Ū regime and the same availability, the chosen action,
its asserted value, and its record are identical before and after every checkpoint of §8 —
where the design *intends* a change (a death that removes a hand-priced VOI, E-14 first),
the change is named at the checkpoint and its direction pre-registered, never discovered.
Four instruments, each with its comparator and command; the never-silently-weaken rule
(tranche 1 §9) carries over verbatim: a criterion may be tightened at a checkpoint, never
loosened, and a loosening is a design revision the owner signs.

**7.1 The suite** — the existing `pytest` default set (2,419 at `b83dbc0`, 34 deselected) plus
the tests each checkpoint adds; comparator: green; command: `uv run pytest -q` (temp under
the user cache — the tranche-1 note). Weakest of the four (it pins mechanism, not
behaviour) and necessary.

**7.2 The decision-equivalence fixture set — the instrument this design adds.** A recorded
corpus of *view → decision* pairs at the pure-function boundary: for each fixture, the
inputs the site ranks over (candidates, observations with their covariates, `ρ`, `u_bar`,
`era_split`, `owner_scoped`, the applied probes, the menu, the sensors) and the outputs
(effector, credences, asserted value, eu, and the full `/log_decision` body incl. `regime` and
`policy`). Recorded **once from the pre-collapse paths** (both the executor path and the
in-process families — trace A and trace B — on the eval battery's questions plus the
withheld/dispersed/miss classes run 9 named), stored beside the eval artefacts under
`$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>/` (out of tree; the design names the
directory, the implementation phase the schema), replayed through old and new paths at every
checkpoint. **Comparator:** identical chosen action **and** identical `/log_decision` body
per fixture — with the **field-class rule** pre-stated (pre-M0 addition): every body field is
declared once as *value-compared* (effector, credences at 1e-9 in leader-first order via the
one label-view, candidates, p_none, eu, n_obs, n_indeterminate, n_competing, instrument,
run_id, regime, policy, retrieval_keys) or *runtime-measured* — compared by **presence and
type**, never value (`latency_s`; `cost_usd` on warm hits and wherever the price is realised at
runtime rather than tabled); the class list is part of the fixture schema and a field may move
from measured to value-compared at a checkpoint, never the other way (never-silently-weaken); **command:** `uv run python scripts/collapse_replay.py --checkpoint <id>` (to be
built at M0), exit 1 on any mismatch, the diff printed by field. **Where the design intends a
difference** (M1: fixtures whose pre-collapse decision came from the cascade E-13/E-14): the
fixture carries the pre-registered expected *direction* (the priced lane reaches a
terminal ⊇ the cascade's) and the comparator asserts that direction, not equality.
**Coverage condition (Q9):** the set holds at least one fixture per terminal type — every
member of `T`, `report(claims)` included — so the narrative leaf's content computation sits
*under* the comparator, not beside it.

**7.3 The eval battery, frozen regime** — `run_eval.py --gate` on the run-9 recipe with
`policy=frozen-elicitations` (Q-O5) and the run-9 corpus pin; comparator: typed answer
rate, wrong-commit count (**must stay 0**), and P(Δ>δ) within the run-9/run-7 band, per
checkpoint that touches the decision path (M1, M4, M5); command: the recipe as pinned. It
measures the *policy* the fixtures cannot (a real corpus, real instruments) — and it is the
only instrument allowed to say "the priced lane reaches more than the cascade did".

**7.4 The tranche-1 golden harness (A1–A14)** — where a checkpoint touches a *store*
(M2: the one poster changes who writes `decisions.jsonl` and the §18.9 answer node): the
harness's A-rows for `calibration.decisions` and `pkm.artifact` run before and after, with
the C6 count; comparator and command as tranche 1 pins them. Where no store is touched, not
run (say so at the checkpoint).

**7.5 Seeded defects the instruments must kill** (each named with the instrument that catches
it; a kill list that grows is fine, one that shrinks is a design revision):
- a **swapped tie-break** in the argmax (M-10: first-listed ↔ last-listed) → 7.2 kills (a fixture
  with two equal-credence candidates, pre-registered);
- the **grounding gate dropped** (L-1 not applied) → 7.2 kills (a fixture whose ungrounded
  quote must not be an observation) and 7.3 kills (wrong commits > 0);
- **policy swap** (`all-to-date` served to the gate, or `frozen-elicitations` to the decider)
  → 7.2 kills (the body's `policy` field) and 7.3 kills (Δ moves off the band);
- the **replace-branch resurrected** (E-7: a null re-read erasing the grounded channel) → 7.2
  kills (fixtures from the n_obs=0 cluster with the gold on the lattice) and 7.3 (answer rate);
- **an optional accounting field** on the poster (Q-O6 regressed) → 7.2 kills (body equality
  fails on the absent key);
- **a second writer** of `decisions.jsonl` (the one recorder regressed) → 7.4 kills (the count
  moves twice per decision);
- **`brain.value` unclaimed but kept** → the M0 wire-shape test fails on absence.

## 8. Migration plan — checkpoints, each green and bisectable, one conceptual move each

The recommended order — E-14 first, then the poster, then the fold entry point, then the
utility atom, then the argmax absorption — is followed, with one addition in front of it
(M0, the instrument) and one adjustment argued at M5. Each checkpoint: what moves · what
stays dual and for how long · the instruments that must be green · the seeded defects
re-run.

| # | Move | Dual / shims | Green | Notes |
|---|---|---|---|---|
| **M0** | the instrument: `scripts/collapse_replay.py`, the fixture recorder (7.2, with the field-class list and the per-terminal-type coverage), the `brain.value` wire-shape test (§2.5, Q-R4), the `regime`/`policy` fields accepted by `/log_decision` (defaults honest), the wire-shape check that decides 6.3b (Q4) | nothing moves | 7.1; 7.2 records its baseline (no comparison yet) | no behaviour change; the fixtures are recorded from **this** tree — the pre-collapse truth; M0's report records the 6.3b decision |
| **M1** | **E-14 dies** (with E-13, `LIFE_AGENT_GROW_LANE` retires: the priced lane is the lane) | none — the cascade is deleted outright (a hand-priced VOI has no shim value) | 7.1; 7.2 with the pre-registered direction on cascade fixtures; **7.3** (wrong commits 0; answer rate reported) | the first collapse target, alone; the eval run is the checkpoint's evidence, filed in the §14 ledger like runs 1–9; **`LIFE_AGENT_GROW_LANE`'s retirement is a config-surface change and gets its one documentation line at this checkpoint** (pre-M0 addition) · **rides this commit (ruled at M0.5's review):** the recorder's non-empty-output-directory guard (R8 — refuse to write into a non-empty checkpoint directory without an explicit flag; the hazard is a partial failure presenting as a whole artefact, with the manifest globbing a directory it never verified) and §6.9's gather-lane fix *behind* its trace; **R4's hedge-path statement is satisfied by a fixture rather than an argument** — quantised retrieval moved one free-set question into `hedge` at M0.5, so the cascade deletion's effect on that path has an oracle |
| **M1.5** | **the coverage census** (R7): enumerate every reachable lane and terminal — the gather lane (§6.9) and each hole the baseline's own manifest names — and for each either record a fixture or register it as known-and-uncovered | nothing moves | 7.2 on the widened set | *why its own checkpoint:* the fixture set pins the traces the recorder was **told** to run, so coverage is a declared quantity, not an emergent one — `terminal:hedge` was unpinned until an unrelated change happened to produce one. Widening coverage inside a checkpoint that also changes behaviour (or that pays for a priced baseline) conflates two variables: an odd fixture could not be attributed. Inherits §6.9's gather trace as its first row · **DONE 2026-08-24** (`docs/unification/reports/r05-collapse-m1-5.md`): every declared class dispositioned (covered / known-and-uncovered landscape·unbuilt·structural / reachable-but-unstamped); 2 fixtures recorded at $0 (q2-043, q2-095), q2-036 the named absence — the r08 fix's own footprint, closed by ruling 2's post-r09 re-record; the gather first-row inherited premise discharged as re-scoped by M1 (host side covered by the priced A-loop wire, ordering pinned hermetically); the regime/policy stamping observation handed to M2 |
| **M2** | **the one poster** (Q-O6): one driver function; `AC.answer`/`answer_via_executor` become thin delegating shims; the family leaves return their decision; the driver records once; A-3/D-10 die; S-1's unavailability path unified (B-2/A-1) | shims for **one checkpoint** (M2→M3), then deleted; the leaves' own `DEC.append`/`D.record` calls become dead code at M2 and are removed at M3 | 7.1; 7.2 (body equality incl. the new fields); **7.4** (decisions + §18.9 nodes: one write per decision) | the reach surface's decisions become priced in the ledger — a *known* record change, pre-registered: absent keys → present with `0.0`/`""` |
| **M3** | **the one fold entry point** (Q-O5): `posterior(policy=…)`; D-8's five sites become callers; `fold_version` covers the policy; the memo keyed by it | none (a rename with a required argument; no old spelling survives) | 7.1; 7.2 (`policy` field); **7.3** in the frozen regime — Δ on the band | also the D-2 unification of the two wire reliability instances into `reliability(edge, cell)` — same checkpoint, same instruments; the calibration curve untouched (debt) |
| **M4** | **the utility atom + the price table** (Q-O3, §4): `action_utilities`/`realised_utility` derived from `u_assert`; the table one module; `lambda_usd` from Ū only (E-5); the tier/menu constants relocated; E-3/E-8/E-9/BR-4's constants die into priors | none | 7.1; 7.2 (vectors identical on every fixture — the derivation is exact); 7.3 | the gate reads the same atom (offline) — its frozen δ/level untouched (§6.1) |
| **M5** | **the argmax absorption**: the driver's remaining choices die or absorb (E-1/L-9/B-6 family choice → rows; E-4 miss → reason; E-12 latch; L-3 scoped rows; GA-1/GA-2/`gather_answer` dies; M-1…M-5 the live lane dies; B-4/B-1/B-5 dispatch dies; the terminals-only regime declared) | `gather_answer` and the M3 lane deleted; the in-process families stay as **leaves** (not shims — they are the terminals-only regime's ranking) | 7.1; 7.2 on **every** fixture incl. terminals-only ones; **7.3**; 7.4 not needed (no store) | *argued adjustment (approved as written):* absorption is the largest move and depends on M2–M4; it splits into M5a (family choice + regimes) and M5b (grow-target absorption + live-lane retirement) if 7.2 shows the pair is not bisectable in one step — the reviewer signs the split at M4's report. **M4's report also decides Q8:** default *delete* the M3 lane; if the shadow's v2 differential needs `CO.map_action` to compute its counterfactual, it survives *renamed into the shadow namespace* as a measurement function — never as anything that could be read as a lane |
| **M6** | **the observation model declared once** (§3.3): the 36 clauses each with one home; D-11/D-14/D-15 one function each; E-7's replace-branch → second channel (gated on §9 Q3's measurement) | none | 7.1; 7.2 (identical decisions — declaring is not changing, except E-7 which is gated) | may interleave with M2–M5 per clause where a clause's two spellings block a move; E-7 waits for its measurement (Q3, endorsed: pre-registered off-gate, criteria frozen first); Q5's volatility transcript is produced here |
| **M7** | the register (§6) pinned by its tests; the vocabulary derivations (D-6) + label-views (D-4/D-5); config surface (D-13); **Appendix A signed here, not before** (the constitution changes when the structure exists) | — | 7.1 | the census's re-listing guard |

Between checkpoints nothing is dual except the M2 shims for one step. Every checkpoint is a
prepared script the owner executes after a rehearsal (S12), reported append-only, and every
one after M0 ends with 7.2's replay transcript in its report. Bisectability: each checkpoint
is one commit or one short series on a clean base; the fixture set is the bisection oracle.

## 9. Open design questions

Genuine questions; each names the evidence that decides it. Owner (O) / reviewer (R).

- **Q1 (O) — is the terminals-only regime wanted on the reach surface?** Two readings of an
  unavailable daemon: (α) the same ranking over `T` (this design's §2.3, the record says
  `terminals-only`), or (β) an unavailability record and no answer (S-1 only). *Evidence:*
  PRINCIPLES §15's "cost of always-on operation" criterion; the reach ledger's count of
  decisions taken while the stack was down (today unmeasurable — the `regime` field at M0
  measures it); the gate's Δ on terminals-only decisions vs full ones (7.3 can arm-split it).
  **Resolved — signed (α)** at M5, measured, revisited on the count.
- **Q2 (R) — 6.5, register entry or regime value?** The seam's unavailability record: a fifth
  named exception, or `regime: unavailable` on the poster's body with no exception at all.
  *Evidence:* whether any consumer needs to distinguish "no optimiser" from "optimiser chose
  abstain" — the reaction loop does (R-3 folds abstain verdicts; an unavailability must not
  fold as an abstain). **Resolved — ruled: both** — regime value + fixture +
  register entry (§6.5).
- **Q3 (O/R) — E-7's error model needs its measurement first.** The design's disposition
  (second channel, combined by likelihood) is the structural answer; whether a *disagreeing*
  strong re-read should still replace the grounded channel (today it does — F2) or condition
  it is the empirical question the operating manual's §14 entry left NOT yet measured (the
  n_obs=0 cluster: a probe erasing a grounded channel). *Evidence:* its own frozen criteria +
  pre-registration, run off-gate like the temper audit; M6 gates E-7 on it. **Resolved — the
  gating endorsed:** structural disposition here, replace-vs-condition measured first.
- **Q4 (R) — G-3, the gate's host sampler:** inside 6.1's exception (part of the verdict
  mechanism's estimator) or a second debt entry 6.3b (a host approximation of a wire
  posterior, retire on wire sampling)? *Evidence:* whether the skin exposes posterior draws
  today (a wire-shape check at M0); if it does, 6.3b with a short retirement; if not, 6.1.
  **Resolved — procedure pre-committed to M0's report; no further ruling.**
- **Q5 (R) — volatility: override or combine, table or latent?** BR-1 lets the half-life
  table override the router's `time_indexed` verdict; V-1's first-match keyword order is a
  hand rule. *Evidence:* the disagreement rate between the router's verdict and the table on
  the eval questions (a transcript to produce at M6, not now); a latent with a prior is
  warranted iff the disagreements are not all the table's wins. **Deferred as stated — M6's
  transcript decides.**
- **Q6 (O) — the census pin is an unreferenced object.** `873860a` is not in `master`'s
  history (the PII rewrite re-created it as `1ea9df8`, tree-identical — F3); no branch, tag or
  worktree references it, so it survives only until a prune. *Evidence:* F3. Recommendation:
  `git tag census-pin-873860a 873860a` (local; the sha stays citable), or re-cite the census
  as pinned at `1ea9df8` in a one-line addendum. The addendum's correction table is a content
  diff and holds either way. **Resolved — signed: the addendum line naming both shas**
  (survives clones); the local tag optional belt-and-braces.
- **Q7 (R) — the addendum's correction table under-reports six files.** The C5-hooked writers
  (`decisions.py` +3 past `:143`, `outcomes.py` +3 past `:152`, `reactions.py` +3 past `:112`,
  `claude_verdicts.py` +3 past `:129`, `gather_outcomes.py` +2 past `:85`, `joint_extract.py`
  +2 past `:124`) shift census cites the addendum listed as "changed" without a shift (F1). This
  design uses the finer map; the census+addendum is the input of record — append a one-line
  correction to the addendum (append-only), or let this design's table stand as the
  correction of record? **Resolved — ruled: append the correction to the addendum** (the input
  of record must be correct in itself); done in the same commit as this revision.
- **Q8 (O) — the M3 live lane: delete or flag-dead?** The design retires it (M5); the code can
  be deleted or left unreachable behind `LIFE_AGENT_MEMBRANE_LIVE`. *Evidence:* whether the
  shadow's v2 differential (the register's measurement) still needs the mapping code
  (`CO.map_action`) to *compute* the counterfactual it records — if yes, keep it as a
  measurement function off the path; if no, delete. **Resolved — signed: default delete,
  decided at M4's report;** if kept, renamed into the shadow namespace, never lane-shaped.
- **Q9 (R) — the narrative terminal as a nested specification (§2.3).** Sign, or require the
  per-claim rule to be flattened into the outer decision space (`2^claims` terminals — the
  alternative this design rejects on size). *Evidence:* the census's own reading of
  `decide_claims` (per-claim optimise, host aggregation N-2 = the argmax's implication).
  **Resolved — signed,** with the coverage condition attached to §7.2 (one fixture per terminal
  type, `report(claims)` included).
- **Q10 (O) — the monolithic instrument (B-7)** survives only in the eval harness as the gate's
  comparator; confirm it is not wanted as a live terminal under any regime. **Resolved —
  signed:** harness-only; an uncalibrated monolithic instrument has no place as a live terminal.

## Appendix A — PRINCIPLES amendment proposals (verbatim replacement text; the owner signs **at M7**, as scheduled — not before)

**A.1 — §16, add after the sentence ending "…truth is the fold." (the three-verdict rule):**

> Every mechanism outside that argmax that shapes a decision receives exactly one of three
> verdicts, and the collapse design (`docs/module-collapse-design.md` §1) is the register of
> them: **belief-shaping** — it changes the observation set or the likelihood the posterior
> folds — is *declared error model*, model content priced as such and calibrated where the
> outcomes stream reaches it; **decision-shaping** — it compares or orders to choose an action
> — goes *into the argmax or dies*; **mechanics** — it sequences the same work — is
> *enactment*, recorded and never priced. There is no fourth verdict, and a mechanism that
> resists classification is a design question, not an exception. The named exceptions (the
> adoption gate's verdict mechanism, the membrane world's utility, the one host reliability
> curve, `brain.value` while claimed) are listed once with their reasons in that design's §6.

**A.2 — §15, replace the sentence "**Under §16 the spine is transport** — it feeds events in
and executes the chosen action's *how*; the agent itself lives in the belief-core (credence +
U + A), so this is a reversible engineering choice, not an architectural fork." with:**

> **Under §16 the spine is transport** — it feeds events in and executes the chosen action's
> *how*: enactment order, iteration bounds, availability, retries, and rendering are
> mechanics, *recorded* on the decision's record and never *priced* by it. The agent itself
> lives in the belief-core (credence + U + A), so the spine is a reversible engineering
> choice, not an architectural fork — and nothing in the spine may prefer one decision space
> or one evidence policy over another when both are available: which space and which policy
> a decision was ranked under is a fact on its record, not a host choice.

**A.3 — §14, add a resolved-decision entry (after the executor unification entry):**

> **The module collapse is adopted (date of signature):** one decision site over
> {terminal responses ∪ transformations}, one `posterior()` behind the brain seam with two
> declared evidence policies (frozen-elicitations for the gate, all-to-date for the decider —
> a regime indicator, not a flag), one utility atom (`u_assert`) from which every host
> spelling derives, one price table, one poster recording every decision once with its
> regime and policy. Adopted on the module-collapse census (`docs/unification/reports/
> r00-collapse-census.md` + addendum) and the reviewed design (`docs/module-collapse-design.md`);
> its behaviour-preservation instrument is the decision-equivalence fixture set (design §7),
> and each checkpoint of its migration is eval-gated (design §8).
