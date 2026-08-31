# r41 / P0 — the engine, pinned and provenanced: READING

Pre-registration + amendments 1–2 + the `t` addendum:
[`r41-p0-engine-preregistration.md`](./r41-p0-engine-preregistration.md). Instrument:
`scripts/p0_engine_replay.py`. **$0 model spend. Nothing installed, nothing enabled.**

## Verdict

**P0-2 PASSES on the one readable row, and the control arm did exactly what a control arm is
for.** Arm A — `proplang-host` at `1a0cea7` — reproduces a recorded shadow decide **exactly**:

```
-- decide t=13 under boot n_source_records=867
   t reached 13 of 13 (verdicts available 70)
   action  recorded='gather' replayed='gather'  -> MATCH
   readouts MATCH
```

`readouts MATCH` is full-precision equality on both `p1` and `entropy_bits` — the ledger stores
float repr and the instrument compares it, with no tolerance, because choosing a tolerance is
the criterion's job and not the instrument's.

So the harness is proven: a decide recorded in July, replayed today from the shadow's own boot
path against the commit the ledger names, comes back identical. **Arm B's differences will
therefore be attributable** (P0-3), which was the entire point of insisting on a control.

## The second row is UNREADABLE, and the reason is a measurement

```
-- decide t=193 under boot n_source_records=1644
   t reached 70 of 193 (verdicts available 70)
   -> UNREADABLE: only 70 verdicts survive today, so t=193 is unreachable.
```

**The derived verdict stream has shrunk from ≥193 to 70 — a 64% loss — while its source logs
only ever grew.** That is not a contradiction, and the addendum half-predicted it: `boot_snapshot`
supersedes on `decision_id`, latest reaction wins. What the addendum said was that supersession
could **rewrite** a verdict. The measurement is stronger: it can **remove** one. A later reaction
whose `(chosen_action, valence)` pair is `verdict_y`-undeclared — a `good` on a `hedge`, say —
decodes to nothing, so the decision it superseded contributes **no** observation at all.

The instrument reports this as **UNREADABLE, never as FAIL**. `t` is an *input feature* of the
decide, so a session that cannot reach the recorded `t` is a different engine state; scoring
that as a mismatch would blame the engine for the ledger's own shrinkage. (`G-3`: a check whose
universe is absent reports absence, not a verdict. The first version of this instrument did fold
it into FAIL; that was fixed before the reading, and the fix is pinned by its own mutation.)

**Consequence beyond P0.** Most of the shadow's history is **not warm-reconstructible today**,
and the deficit grows with `t`. Any future reading of this ledger inherits that, and P1's
"declare the 21-day gap as a segmentation boundary" is now the *smaller* of two discontinuities:
the larger one is that the pre-existing record's own warm states cannot be rebuilt.

## Criteria

| id | verdict | evidence |
|---|---|---|
| **P0-1** | **PASS** | arm A is `1a0cea7`, sha `1d008643…` recorded; arm B's worktree prepared at the pinned current commit, unbuilt |
| **P0-2** | **PASS** on the readable row | exact action + readouts at `t=13`; the `t=193` row unreadable, with its cause measured |
| **P0-3** | **not reached** | arm B is not built; this reading buys the control, not the comparison |
| **P0-4** | **not reached** | nothing is installed, so there is nothing to smoke |
| **P0-5** | **PASS** | nothing enabled, no `MEMBRANE_COMMAND` set, no proplang issue filed |

The instrument's own ladder: **9/9 mutations RED**, run before the reading.

## What is deliberately left for the next step

Arm B (build the pinned current commit, replay the same row, attribute every difference), then
P0-4's smokes on whatever is installed. Both are cheap now that the control holds — which is
the only reason the control was worth buying first.
