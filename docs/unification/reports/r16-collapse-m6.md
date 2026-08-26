# r16 — collapse M6: the observation model declared once

> Pre-registration, committed BEFORE any src change (the standing discipline). Design:
> `docs/module-collapse-design.md` §3.3 (the clause list), §5.3 (D-11…D-15), §8's M6
> row, §9 Q3 (E-7 verify-only) and Q5 (the volatility transcript). Baseline of record:
> **`m5-base`** (314 fixtures, 0 absences, tree `cb33be0`). Everything below was
> verified against the LIVE tree while writing (the r05/r10 lesson: a census must read
> the deployed rule end-to-end, never re-implement the constant it prices).

## STATE (the clause census, verified 2026-08-26 on master `a89165a`)

The thirty-six belief-shaping clauses of design §3.3, grouped, each with its verified
current home(s):

**Already ONE declaration with ONE home (verify + stamp, no code motion):**

- **L-1/E-10 — the grounding predicate:** `LK._grounded` (lookup.py:441-451; the
  quote-or-value containment gate). E-10 folds in structurally: a retrieval grow's
  results re-enter through `/extract`'s gate — no second grounding spelling exists.
- **L-2 — correlation structure:** `LK.dedup_correlated` (:778) + `LK.dedup_drop_rows`
  (:800, the r09 wire form) — the §5 dedup key in one module.
- **L-4 — candidate identity:** `LK._norm_value` + the candidate-key rules (:394
  region); every bridge join reads `LK._norm_value` (verified: server.py has no local
  normaliser).
- **L-5/GA-3 — era structure:** `LK.era_split` (:414). GA-3's second home died with
  `core/gather.py` at M5 — the clause collapsed to one home by deletion (verified: the
  module is gone; executor carries only the era flag the bridge computed).
- **L-6/L-7/L-8/L-10 — the covariates:** `LK.time_factor` (:314), `LK.subject_factor`
  (:300), `LK.authority_for` (:453), group-competition-min (the lookup module). One
  home each.
- **BR-1/V-1 — volatility:** the prior table + first-match order `VOL._SEED`/
  `VOL.half_life` (volatility.py:40-55); the override site is ONE place
  (server.py:189: `time_indexed = VOL.half_life(construct) < VOL.PERMANENT`).
  Override-vs-combine is Q5's transcript (below), not this checkpoint's code.
- **BR-8/DL-2/DL-3 — edge failure semantics:** ok-only observation (server.py:617
  region), the blind-decline poison guard (deliberate.py:328-338), out-of-range
  credence ⇒ no signal (deliberate.py:110-115). One home each; BR-8's warm-cost
  already moved to the price table at M4.
- **M-9/GO-1/GO-2 — the sensor vocabulary:** `W` buckets (world.py:138-176),
  `GO.sensors_from`/`SENSOR_FEATURES` (gather_outcomes.py:55-70), the cold prior
  (gather_outcomes.py grow_block). One home each.
- **N-1 — the claim cells:** `NR._CELLS` + the classifier (narrative.py:82, 179
  region). One home.
- **N-4 — the claims' time covariate:** `NR.scope_decay`/`scope_decay_factor`
  (narrative.py:415-440) — already DERIVES from `LK.time_factor` at the claim's
  volatility half-life; its input (the claim's `as_of`, present-scope only) is a
  declared branch of D-14 (below), not a second spelling of the decay.

**TWO-OR-MORE spellings (the checkpoint's code):**

- **D-11 — the value-join (with L-4/BR-2):** TWO spellings in bridge/server.py: the
  corroborate join inline (:363-364 and the :413 value_norm restatement) and
  `_join_deliberate_value` (:631+), whose own docstring says "the corroborate join's
  contract verbatim". One function; both callers bind.
- **D-14 — the one recency policy (with L-6/N-4/BR-3/P-1):** the FUNCTIONAL FORM
  already has one home (`LK.time_factor`; `BR._source_time_factor`:305-324 and
  `NR.scope_decay` both call it). What is plural is the DATE-SELECTION policy:
  BR._source_time_factor embeds the ≻-chain (max doc_date of value-carrying hits ≻
  self-reported `as_of` ≻ undated) inline; P-1's email-header fallback
  (probes.py:100-113) is a date-SOURCE rule of the same policy on the projection
  side; N-4's claim-side selection (as_of, present scope) is a third branch. The
  design's demand: ONE declared policy function with its input-selection stated,
  every consumer reading it.
- **D-15 — the verdict→evidence projection (R-2…R-5, M-6, M-7):** FOUR sites:
  `SES._VERDICT_Y`/`verdict_y` (membrane/session.py:55-69 — the (action, valence)→y
  domain), `claude_verdicts.y` (core/claude_verdicts.py:98-103 — the Claude channel's
  y), `RX._lookup_reaction`/`_narrative_reaction` (core/reactions.py:140-177 — the
  utility-evidence branches R-3/R-4/R-5, incl. the abstain-threshold datum and the
  coverage-gated narrative branch), and the owner ≻ Claude precedence
  (membrane/shadow.py:1012 + claude_verdicts' boot-snapshot merge). These are
  BRANCHES of one projection spelled across four modules with no single declaration
  naming the whole.

**Mechanics riders (§5.3, dispositioned nowhere else — carried here, declared):**

- **D-12 — edge names:** `EX.extract_edge` (executor.py:79-83) and `DL.instrument`
  (deliberate.py:196-200) — two constructors, one naming rule (`kind@model`). One
  `edge_id(kind, model)`; both become bindings. Wire strings identical by
  construction.
- **D-13 — env constants:** `AC:33-34` and `ASK:250-251` spell
  `LIFE_AGENT_BRIDGE_URL`/`ANSWER_BRAIN_URL` twice (verified live). Read once
  (`ask_client` stays the reader — config.py is paths/KB config; the census's
  "config.py" letter is amended to "one home" since AC is every caller's import
  root already; ASK binds AC's).

**E-7 — VERIFY-ONLY (r07 ruling 2; the structural move already landed):** the r09
JOIN arc (merged at run 14) + r09d's D3 (the S2 join) retired the replace branch at
every §6.12 site; run 18's tree carries them. M6 owes a VERIFICATION, not code: the
audit below.

**Q5 — the volatility transcript (deferred to M6 by the design's own ruling):** the
route model's own `time_indexed` verdict is parsed (`LK:569`) and route derivations
are §18.9-cached, so the router-vs-table disagreement table is readable at $0.

## MANDATE (what M6 does, and nothing else)

1. **P-I — D-11:** one join function (home: bridge/server.py, where both callers
   live); the corroborate inline join and `_join_deliberate_value` become one
   declaration with two thin call sites. TDD: a RED test pinning byte-equality of
   both call paths through the one function.
2. **P-II — D-14:** one date-selection function declaring the ≻-chain (home:
   core/lookup.py beside `time_factor` — the covariate's module);
   `BR._source_time_factor` binds it; P-1's email fallback and N-4's claim branch
   are named IN the declaration's docstring as the projection-side and claim-side
   branches (their code stays where it is — they are different inputs to the same
   declared policy, not duplicate spellings of the chain).
3. **P-III — D-15:** one projection declaration (home: core/reactions.py — the fold's
   evidence gate) naming the full domain: the (action, valence)→y table, the Claude
   channel's y, the R-3/R-4/R-5 utility branches, and the owner ≻ Claude precedence;
   SES and claude_verdicts BIND the shared table/domain (drift-gated `is`-identity
   where a table is shared, the M4 pattern). Fold outputs byte-identical.
4. **P-IV — the declaration stamps:** every already-single-homed clause above gets
   its clause id named in its docstring (`§3.3: L-1` etc.) so a reader lands on the
   declaration from the design and vice versa; the census table above is the
   verification transcript.
5. **P-V — riders:** D-12's `edge_id` + D-13's single reading.
6. **P-VI — E-7 verify-only:** an audit transcript in this report enumerating the
   §6.12 sites (+ S2/D3) on today's tree, each shown JOINING with the null-guard
   present, each pinned by an existing test named in the transcript (no new
   behaviour).
7. **P-VII — Q5's transcript:** a $0 instrument (`scripts/q5_volatility_transcript.py`)
   reading, for every eval question with a cached route derivation: the model's
   `time_indexed` verdict, the table's verdict, construct, half-life. Published as an
   appendix here. **Frozen decision rule (the design's own words): a latent with a
   prior is warranted iff the disagreements are NOT all the table's wins.** The
   transcript DECIDES Q5's disposition entry; no code moves either way this
   checkpoint.

Out of scope, explicitly: any behaviour change (E-7 included), any priced run, the
hand-priced-VOI arc (§14, post-M5 — untouched), proplang (deferred).

## GATES (frozen)

- **G1:** full suite + ruff + mypy green.
- **G2:** `collapse_replay.py --checkpoint m5-base` — **314/314 PURE EQUALITY.**
  Declaring is not changing: NO direction class is registered for M6. Any fixture
  diff is a FINDING (a real spelling divergence between two homes of one clause) —
  work STOPS on it and the finding is disclosed before any "fix"; a divergence
  discovered this way must not be silently normalised to either spelling.
- **G3:** none — the M6 row demands no priced run.
- **G4:** none (no store/writer moves; the D-15 unification binds tables, it does not
  move a write).
- **G5:** PII-free tree; hooks armed.

## PREDICTIONS (frozen blind)

- **P1:** G2 reads 314/314 pure equality on the final tree.
- **P2:** D-11's two spellings are byte-equivalent on every fixture (if not, G2
  catches it and the divergence is published as a finding — the docstring's
  "verbatim" claim is then false and the TRUE behaviour is the deployed corroborate
  spelling, which wins by the deployed-rule rule).
- **P3:** D-15's binding leaves every fold byte-identical (same tables, one home).
- **P4:** the Q5 transcript is readable for ≥ 100 of 104 questions from cache alone
  ($0), and the q-014 class (the table rescuing a model "permanent" wrong-call)
  appears in it.
- **P5:** E-7's audit finds zero replace sites (the run-18 tree).

## Consequence branches (frozen)

All gates green → M6 completes on the standing pattern (results appended, mirrors,
PR/merge, steel deploy) without a further keypress; the ladder resumes at M7 (owner
keypress — Appendix A). Any G2 divergence → STOP, publish the finding, blind
amendment before any further phase. Anomalies en route are disclosure items
(cap-the-arc).
