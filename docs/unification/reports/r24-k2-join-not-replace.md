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
