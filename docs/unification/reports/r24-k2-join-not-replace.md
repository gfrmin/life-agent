# r24 · K2 — join, not replace

> **Status: PRE-REGISTRATION FROZEN.** Everything above the RESULTS rule is committed
> BEFORE any `src/` change. Results append below it; nothing above is edited afterwards.
> Part 1, milestone 2 of the plan approved 2026-08-27.

## What this fixes

`core/aggregate._compose_one` currently contains a **replace branch**:

```python
candidates = [a for a in group if a.basis in _COARSE_BASES
              and a.as_of is not None and date.fromisoformat(a.as_of) == scope.end]
if len(candidates) == 1:
    v = candidates[0].amount
    notes.append("issuer roll-up at the scope end is the single observation; "
                 f"{len(group) - 1} finer rows are slot evidence")
    return TotalPosterior(point=v, lo=v, hi=v, k=1, s_obs=v, ...)
```

One stated figure at the scope end **replaces** every other observation: the interval
collapses to zero width, `k` drops to 1, and a whole grounded monthly series is demoted to
"slot evidence" and discarded.

This is the exact class r06–r09 spent three checkpoints killing — *a replace branch
discarding a grounded channel* — and it was reintroduced **by design**: the deleted
`aggregate-family-design.md` §4.2 prescribed it. r07 measured the harm of the class
directly: S1 zeroed a five-observation base before the deliberate edge re-minted a
one-observation competitor, on the row that blocked deployment for two weeks.

There are two channels here and they are not rivals:

- **A — the issuer's roll-up.** One stated figure, one document, high authority (the issuer
  folded its own records). Says nothing about slots it never listed.
- **B — the summed series.** The finest-basis rows across several documents, plus the recall
  term's imputation for slots a generator says should exist. More documents, more
  assumptions.

They are two reads of one latent quantity. **Neither replaces the other, and disagreement
between them is information** — a zero-width interval on one channel while the other says
something different is the confident-wrong failure the whole project exists to avoid.

Under §11's line this stays host either way ("folding a declared model" is deterministic
computation), so it is correct work on the current tree and it stops the proplang migration
carrying a known defect across.

## The rule that replaces it

Deterministic composition of reads — no new learning, no new latent:

- Channel A absent ⇒ the series posterior, exactly as today.
- Channel B absent (a roll-up with no finer rows) ⇒ the roll-up as a point.
- **Both present ⇒ they join:** the point estimate is the issuer's roll-up when there is
  exactly one (highest authority for a point), or the series when roll-ups compete; the
  interval **spans both channels**; `k` counts **both** channels' observations; and the
  disagreement is NAMED in `basis_note` with its magnitude.

Agreement is rewarded rather than manufactured: when the roll-up equals the series sum and
no slots are imputed, the joined interval is zero-width at that value.

Over-widening is not free — `gate.realised_aggregate` scores intervals by Winkler at a
frozen central level, so width is priced. That is the check on this rule, and it is why the
interval spans the channels rather than padding beyond them.

## FROZEN CRITERIA

**J1 — no channel is discarded.** With a roll-up AND a non-empty series present, the
returned `k` equals `len(roll-ups) + len(summed)`. No path returns `k == 1` while a
non-empty series was in scope.

**J2 — the interval spans every channel.** For any input carrying a roll-up and a series,
`lo <= min(roll-up, series point)` and `hi >= max(roll-up, series point)`. A disagreeing
pair may never produce an interval that excludes either read.

**J3 — agreement is not padded.** Roll-up equal to the series sum, no imputed slots ⇒
`lo == hi == point == that value`. The join must not manufacture width where the channels
agree.

**J4 — disagreement is named.** When the channels differ, `basis_note` names both reads and
the magnitude of the gap. Silence about a disagreement is the defect, not the width.

**J5 — the replace branch cannot return.** A poison fixture requires the composition to FAIL
when a grounded series is discarded in favour of a single roll-up, verified RED by mutation
against the branch as it stands today.

**J6 — the decision path does not move.** `core/aggregate.py` is imported by no decision-path
module (verified before this prereg: the only importer in `src/` or `scripts/` is
`scripts/aggregate_eval.py`). The 314-fixture replay therefore reads **PURE EQUALITY**.
Anything else is a FAIL and a STOP — it would mean the module is on a path this prereg
claims it is not.

**J7 — every new fixture names its mutation** (register row 19, landed in r23's follow-on).

## Gates

G1 suite + ruff + mypy + PII green · G2 the replay per J6 · G3 not bought — the module is
off the decision path, and J6 is the evidence · G4 the adversary pass closes the milestone.

---
## RESULTS

*(appends here; nothing above is edited)*

**Read 2026-08-27, $0. All seven frozen criteria MET. No priced run bought.**

### J1 — no channel is discarded: MET

With one roll-up and a three-document monthly series, `k == 4` (was 1). `s_obs` carries both
channels. The `if len(candidates) == 1:` early return is gone; nothing in `_compose_one`
returns while a non-empty series is in scope.

### J2 — the interval spans every channel: MET

Issuer 31937.00 against a series of 324.00 now returns an interval containing both (it was
`[31937.0, 31937.0]`, excluding the series entirely). Competing roll-ups keep every read:
`lo <= 31937.00` and `hi >= 283886.00`.

That interval is very wide, and deliberately so. Two reads differing by two orders of
magnitude is a situation the report should be uncertain about; `gate.realised_aggregate`
scores by Winkler at a frozen central level, so the width is **priced**, not free. That is
the check on this rule and the reason the join spans the channels rather than padding
beyond them.

### J3 — agreement is not padded: MET

Roll-up equal to the series sum with no imputed slots ⇒ `lo == hi == point` at that value
and `k == 4`. Agreement is evidence: it earns a zero-width interval *and* a four-observation
count, where the old branch gave zero width on one observation.

### J4 — disagreement is named: MET

`basis_note` reads *"issuer roll-up X DISAGREES with the summed series Y (gap Z) — both
channels kept, the interval spans them"*, or *"...agree at X (k observations)"*. The old
note said *"issuer roll-up at the scope end is the single observation; N finer rows are
slot evidence"* — describing the discard as though it were a finding.

### J5 — the replace branch cannot return: MET

`tests/poison/test_join_poison.py`, six fixtures. **Verified RED by mutation**: restoring
the `if len(candidates) == 1:` early return fails three of them by name —
*"the composition kept 1 observation(s) where 4 were grounded"*, *"interval [31937.0,
31937.0] excludes one of the two channel reads"*, and *"the two channels disagree and the
basis note does not say so"*.

### J6 — the decision path does not move: MET, pure equality

**314/314 fixtures replay identically**, exit 0. The premise was verified before the prereg
was frozen (the only importer of `core/aggregate.py` in `src/` or `scripts/` is
`scripts/aggregate_eval.py`) and the replay confirms it rather than assuming it.

### J7 — every new fixture names its mutation: MET

Enforced by register row 19, landed in r23's follow-on and running in CI.

### Two existing tests encoded the defect and were rewritten

`test_rollup_at_scope_end_is_the_single_observation` asserted
`(point, lo, hi) == (v, v, v)` and `k == 1` — it pinned the discard as correct behaviour.
`test_competing_rollups_fall_back_to_the_series_named` asserted `k == 3`, silently accepting
that two roll-up observations vanished. Both are rewritten to the join, and a third test was
added for the agreement case, which had no coverage at all.

This is the second time in two days that the tests over a module encoded the very defect the
module carried (the first: `AMOUNTS_PRODUCERS`' fixtures restating the wrong constant). Both
were invisible for the same reason — the test was written from the implementation rather
than from the contract.

### `_issuer_fold` is untouched, and the distinction is load-bearing

A *same-document* stated total genuinely is the issuer's fold of its own parts: one document,
one arithmetic, no second channel. `_COARSE_BASES` excludes `point_in_time`, so that path
never enters the roll-up join. Only the **cross-document** roll-up-versus-series case is a
two-channel situation, and only that case changed.

### Gates

G1 `pytest -m "not llm and not system"` **2815 passed**, 35 deselected; `ruff` clean; `mypy`
clean on 226 files; PII guard exit 0.
G2 **314/314 pure equality** on `m5-base`.
G3 not bought — J6 is the evidence.
G4 the adversary pass closes the milestone.
