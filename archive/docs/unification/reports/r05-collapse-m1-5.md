# r05-collapse — M1.5, the coverage census — 2026-08-24

> **Checkpoint M1.5 (module-collapse §8, R7's row): enumerate every reachable lane and
> terminal; for each, record a fixture or register it known-and-uncovered. Nothing moves.**
> Continues `r04-collapse-m1.md`; the slug disambiguates from `r05-carrier-identity.md`
> (the diagnostic thread shares the number series).

## STATE

- master `9453e5b` (r08 merged: §6.13 repaired, SPEC 0.18.2). Suite 2638 passed, ruff and
  mypy green at the r08 PR head — the same tree.
- **7.2 against this tree, all three sets, today:** `m0-5` **311/311**, `m0-5-growlane`
  **104/104**, `m1-5` (new, below) **2/2** — every fixture replays identically. r08's
  retrieval fix is invisible to the oracle by construction (retrieval rides in the
  fixture), which is §6.13's registered blindness, not a surprise.
- **The baseline of record is the MERGED m0-5** — its manifest's `merged_from` shows two
  recordings: 102 fixtures free (2026-08-20T06:00Z) and **209 fixtures priced,
  `allow_spend: true` (2026-08-20T10:08Z)**. O2 ran and merged; the inherited "O2 prepared,
  awaiting the owner" status was stale and the census read the manifest, not the claim.
  M1's surviving-lane record `m0-5-growlane` (104 A-loop, priced lane) sits beside it.
  Historical dirs (`m0`, `m0-priced`, `m0-5-{growlane-pilot,legacy-aloop,pre-r2,verify}`)
  are superseded provenance, counted in no census row.

## THE CENSUS

Coverage counts are the union of the baseline of record (`m0-5`, 311) and the surviving-lane
record (`m0-5-growlane`, 104), plus this checkpoint's widening (`m1-5`, 2). The class
taxonomy is the declared one (`life_agent/collapse/fixture.py`: 7 terminal types ×
`DECLARED_CLASSES` × 5 trace types) — a class nobody reached is as visible as one everybody
did, which is what makes this census a reading rather than a build.

### Traces

| trace | m0-5 | growlane | m1-5 | disposition |
|---|---|---|---|---|
| A-loop | 104 (legacy lane) | 104 (priced lane) | — | **covered** — the priced record is the live lane's (M1 retired the flag) |
| A-poster | 104 | 0 | — | **covered** (the poster path, pre-M2) |
| B-lookup | 101 | 0 | 2 | **covered**, one named absence (q2-036, below) |
| B-narrative | 1 | 0 | — | **thin, and truthfully so** — the narrative family engages for 1 of 104 battery questions; O2's priced run recorded this trace and produced no more. The thinness is routing truth, not a recording gap |
| seam | 1 | 0 | — | **covered ×1** — the §6.5 commit-with-no-engine lane, witnessed |

### Terminals

| terminal | count | disposition |
|---|---|---|
| report | 146 | covered |
| abstain | 264 | covered |
| miss | 5 | covered |
| hedge | 1 | covered ×1 — organic (M0.5's quantised retrieval moved one free-set question into it; R4 accepted the single witness) |
| ask_clarify | 0 | **KNOWN-AND-UNCOVERED (landscape).** In the ranked action space of every decision (`decisions.ACTIONS`, EU-ranked in `lookup`/`executor`); no battery question's posterior/utility landscape selects it. R4's rule stands: manufacturing a question for its terminal is fitting to the test |
| report_scoped | 0 | **KNOWN-AND-UNCOVERED (landscape).** Same standing as ask_clarify |
| report(claims) | 0 | **KNOWN-AND-UNCOVERED (landscape).** The narrative terminal; the family's single engagement abstains |

### Outcomes, posterior kills, gates

All covered, at depth: committed 146 · withheld 269 · dispersed 259 · miss 9;
two-equal-credences 55 · n_obs=0 10; gate:executor_down 1.

### Regimes and policies — covered lanes, unstamped records

| class | count | disposition |
|---|---|---|
| regime:full | 99 | covered (free-run B-lookup rows) |
| regime:terminals-only | 0 | **KNOWN-AND-UNCOVERED (unbuilt).** Q1 signed (α) at M5; the regime does not exist on this tree |
| regime:unavailable | 0 | **REACHABLE BUT UNSTAMPED.** The seam trace witnesses the lane (`gate:executor_down` ×1) but the seam path's decision record carries `regime: None` — verified on the fixture body |
| policy:all-to-date | 99 | covered (same rows) |
| policy:frozen-elicitations | 0 | **KNOWN-AND-UNCOVERED (unbuilt).** `posterior(policy=…)` is M3's move |

**The stamping observation, named for M2:** 0 of 104 priced A-loop rows stamp `regime` or
`policy` (verified across the growlane fixture bodies), while the free B-lookup rows stamp
both (99). M0 added the fields "defaults honest", and the priced path and the seam path are
honestly not filling them. When M2's one poster records once, the stamps become uniform or
their absence becomes a decision — either way it is that checkpoint's, not this one's.

### The named absence, and two closed at $0

M0.5 recorded three B-lookup absences (cold §18.9 derivations, no-spend mode): q2-036,
q2-043, q2-095. This checkpoint re-attempted all three at $0 (`--checkpoint m1-5`,
no-spend): **q2-043 (report) and q2-095 (abstain) recorded** — their derivations were warmed
by the intervening r07/r08 replays — and both replay identically. **q2-036 remains cold, and
that is the r08 fix's own footprint:** it is the §6.13 witness, the one question whose
decision-visible top-k the fix changed, so its new chunks' extraction derivations have never
been derived. Slot for closing it: the post-r09 re-record of the baseline (ruling 2), which
re-records all three anyway.

### Bridge-internal lanes — structurally unfixturable, each with its actual oracle

The fixture set tapes the bridge at the `http` seam (M1 DONE 6): replay serves recorded
responses and never executes bridge code. These lanes are therefore not fixture-coverable
by construction, and the census names each with the oracle it actually has:

1. **The corroborate plain branch** (`reextract=False`): 0 calls over 309 priced + 326
   legacy recorded calls. No oracle would catch a regression there. Known-and-uncovered.
2. **`probe_corroborate`'s ordering** (§6.9): pinned by `tests/test_probes.py`'s three
   permutation-invariance tests — hermetic, and stronger than a trace would have been
   (a trace records answers, not behaviour).
3. **The S1–S5 replace sites' internals** (§6.12): read live by r06/r07's $0 replays;
   known-and-uncovered under 7.2's bar. r09's JOIN changes here carry their own frozen
   pre-registration (ruled).
4. **pkm's FTS window**: was §6.13; **repaired at r08** (the declared order in the SQL),
   pinned by `tests/pkm/test_retrieval.py`'s two tie-block tests and the r08 artefacts.
5. **The daemon's argmax**: a separate process by design; the wire is recorded, the
   internals are the credence repo's own tests.

### §6.9's gather trace — the inherited first row, discharged as re-scoped

The §8 row inherits "§6.9's gather trace as its first row". M1 discharged the premise: a
gather-lane trace would tape `probe_corroborate`'s answers and exercise nothing on replay
(DONE 6(b)), and the ordering got the hermetic oracle instead. What remains coverable is the
gather lane's **host side**, and it is covered: the priced A-loop set records the full
gather wire (`/grow_menu` ×103, `/log_gather` ×202 — M1's own count). No gather trace type
exists, and none is needed. The row is closed by naming, which is what a census does.

## DONE

1. 7.2 replayed green on every live set against current master (STATE).
2. The census: every declared class dispositioned — covered / known-and-uncovered
   (landscape · unbuilt · structural) / reachable-but-unstamped — with the bridge-internal
   lanes named beside their actual oracles.
3. The widening: 2 fixtures recorded at $0 into `m1-5` (manifest R8-guarded, fresh
   directory), 1 absence named with its cause and its closing slot.
4. The O2 status correction (STATE) — the baseline of record is the merged one.

## DEVIATIONS

None in procedure. One inherited-state correction (O2, in STATE) — a read, not a change.

## REFUSED

- Manufacturing questions to close the three landscape terminals (R4's rule).
- Spending to warm q2-036 now — ruling 2's post-r09 re-record covers it; paying twice for a
  fixture the JOIN will invalidate buys nothing.
- Touching the regime/policy stamping — M2's poster owns it; nothing moves at M1.5.

## NEXT

r09 opens: the JOIN-with-a-correlation-key checkpoint (ruling 1) — frozen pre-registration
committed before any `src/` change, then TDD. After it lands: the m0-5 baseline re-record
and O2 re-preparation (ruling 2), then run 13 under §6.10 with the ruled frozen branches.
