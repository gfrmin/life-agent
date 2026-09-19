# r11 — the baseline re-record: `m2-base` is the collapse ladder's fixture set of record

**Date:** 2026-08-25 · **Spend:** $0.0388 (cap $8.00, delegated) · **Status:** DONE — all
four verification clauses read green; ruling 2's rider is CLOSED.

## What was ruled, and when it came due

r07's RULINGS (owner interview, 2026-08-23), ruling 2: after the JOIN lands, *"E-7 at M6
becomes verify-only; the m0-5 baseline is re-recorded and O2 re-prepared after it lands."*
The rider deferred through run 13's FAIL (the JOIN reverted), the tempered arc (r09b–r09d,
nothing merged), and run 14's conferral; its due condition — the JOIN tree merged and
deployed — was satisfied 2026-08-25 when run 14 PASSED and the §6.12 block closed. At the
completion-programme planning session (same day) the owner ruled the priced portion
**delegated, capped at $8** — the third option ("Delegate, capped") of the sequencing
question, taken as recommended.

Why it must precede M2: the fixture set is the ladder's bisection oracle
(module-collapse-design §8), and after r09 the old set could no longer serve it — **95
probe-firing fixtures of m0-5 were unservable because the payload grew** (the §5
correlation key on every wire observation; the named class, disclosed at r09). An oracle
that cannot serve a third of its rows on the tree it is meant to bisect is not an oracle.

## The instrument, prepared first

Two named gaps were closed before any recording:

1. **Spend metering** (recommended at O2, never taken; PR #82, merged, TDD — 5 tests
   red→green): `spent_usd` is **derived** on the manifest from the instrument-seam wire
   exchanges (`FX.manifest()` sums `cost_usd` over recorded exchanges — the `merged_from`
   lesson: derived, not asserted), and `MeteredRecordingClient` aborts any run that
   crosses `--max-usd` (default 8.00) by raising `RecordBudgetExceeded`, a
   **`BaseException`** — deliberately outside `Exception`, so the recorder's per-trace
   absence handlers (`except Exception` → a named absence) cannot swallow a blown budget
   into 300 quiet absences.
2. **A prepared, gated script** (`~/.cache/life-agent/m2-base/record.sh`, out of tree —
   an instrument, not product): G1 clean tree == `origin/master` plus three git-grep
   asserts (the JOIN in the bridge, r08's quantised order in `src/pkm/retrieval.py`, the
   metering in the recorder); G2 credence code == pin `f474e70` (packaging-only delta
   allowed); G3 `PKM_CONFIG` present; G4 the R8 guard honoured (the checkpoint directory
   must not exist — a new label, never an overwrite); G5 a fresh daemon on :8799 (a stale
   listener would run stale code). `PYTHONHASHSEED=0`, `LIFE_AGENT_DELIBERATE=1`.

**Rehearsal (S12), before the real run:** `REHEARSE=1` runs the same gates, records 2
questions in no-spend mode into a `mktemp` scratch, and replays them. Read: 4/4 fixtures
replay identically, $0.0000, the KB directory untouched, one named absence (q2-001's
A-loop is a cold §18.9 derivation and the recorder was refusing spend) — precisely the
absence class the priced run exists to remove. PASS.

## The record

Checkpoint **`m2-base`** → `$LIFE_AGENT_KB/eval/collapse-fixtures/m2-base/`, recorded
2026-08-25T04:18:30Z against the corpus pin, k=20, run_id `collapse-m2-base` (excluded
from the live calibration stream by prefix), engine 0.105.2, **one single run** — free and
priced traces together, so the manifest carries **one `tree_sha`
(`d161a76…`)** and the m0-5 two-provenance merge wart does not recur. `d161a76` is master
at launch: the deployed run-14 decision path plus the metering commit; the two PRs merged
mid-run (#83 docs, #84 readout) touch nothing the recorder imports.

| quantity | m0-5 (was) | m2-base (now) |
|---|---:|---:|
| fixtures | 311 | **314** |
| named absences | 3 | **0** |
| B-lookup family | 101 | **104** |
| A-loop family | 104 (id label `growlane`) | 104 (id label `aloop`) |
| A-poster / B-narrative / seam | 104 / 1 / 1 | 104 / 1 / 1 |
| servable on the deployed tree | 216 of 311 (95 unservable — payload grew) | **314 of 314** |
| metered spend on the manifest | (absent — pre-metering) | **$0.0388** |

The id-label change is a rename, not a coverage change: m0-5 recorded the A-loop trace
while `LIFE_AGENT_GROW_LANE` still named the lane; M1 retired the flag (the priced lane is
the lane) and the label followed. Coverage holes remain **named, never silent** — six:
`terminal:report_scoped`, `terminal:ask_clarify`, `terminal:report(claims)`,
`regime:terminals-only`, `regime:unavailable`, `policy:frozen-elicitations` (all
dispositioned known-and-uncovered or unbuilt at M1.5; unchanged in kind).

The recorder annotated the two **pre-registered expected-change classes** in its own
output as it replayed: every A-poster fixture ("M2 — one poster: the reach surface's
absent accounting keys become present at `0.0`/`''` — never absent", design §5.1) and the
seam executor-down fixture ("M2/M5 — the same unavailability becomes a RECORD carrying
`regime=unavailable` with no `decision_id` — never an abstain verdict", design §6.5). The
M2 gate reads those as expected changes, not regressions.

## Verification — the frozen clause, read line by line

The plan's Stage-0.1 clause: *"replay transcript green on the re-recorded baseline;
q2-036 served; metered spend on the manifest ≤ cap."*

1. **Replay green:** `collapse_replay.py --checkpoint m2-base` — **314/314 fixtures
   replay identically** (transcript: `record-20260825T121713.log` beside the script).
2. **q2-036 served:** fixtures present in A-loop, B-lookup and A-poster; **zero q2-036
   absences**. The last named B-lookup absence — r08's own footprint (its top-k changed;
   its new chunks had never been derived) — is CLOSED, as M1.5 said it would be.
3. **Spend ≤ cap:** manifest `spent_usd = 0.0388` ≤ 8.00 — within a factor of the
   ≈$0.05 warm-store expectation measured at O2, and 0.5% of the cap.
4. *(the script's own fourth clause)* **The live surfaces are untouched:** sha256
   fingerprints of `calibration/{decisions,outcomes,reactions}.jsonl` byte-identical
   before and after the record (`e598ba05… / 1d558e2d… / b3b7df24…`).

## Disposition

- **`m2-base` is the baseline of record.** The ladder's bisection oracle from M2 onward is
  `scripts/collapse_replay.py --checkpoint m2-base`; 7.2 comparisons read against it.
- **m0-5 stands as history**, manifest untouched — the readings taken against it (M0.5
  through M1.5) are unchanged; this entry is their forward pointer.
- **Ruling 2's rider is CLOSED in both halves by one artefact:** the re-record and the O2
  re-preparation collapse into the same single run — the priced traces were recorded in
  it at $0.0388, so no separate O2 instrument exists to re-prepare.
- The one remaining named absence-class fact from M0.5 (q2-036) is closed; the ladder
  resumes at **M2** with a fully-servable, zero-absence oracle.
