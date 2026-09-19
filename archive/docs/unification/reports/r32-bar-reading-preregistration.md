# r32 — the commit-bar reading: PRE-REGISTRATION

**Frozen and committed BEFORE anything reads.** Conferral 2, ruling 1. $0: every input is an
artefact already on disk (the decision log, the owner's utility model, the deployed source).
Nothing is bought, nothing is built, no `src/` change is in scope.

## The question

The Stage-4 exit measurement's round 8 recorded three boundary rows in the deployed decision
log, by leader credence and recorded action:

| leader credence | p_none | n_obs | recorded action |
|---:|---:|---:|---|
| 0.943 | 0.057 | 2 | report |
| **0.875** | 0.125 | 3 | **report** |
| 0.828 | 0.172 | 2 | abstain |

The owner's declared exchange rate is 10:1, which `core/decide.shaped_u_bar`'s docstring calls
"today's uniform 0.90 bar" — Chow's rule at the `exact` special case with VOI and R held
constant across questions. **A report was issued at 0.875.** Either the deployed pricing
legitimately puts the indifference point below 0.90, or the declared bar leaks. r32 decides
which. It does not decide what to do about it.

## Sites (named before the read; every constant IMPORTED, never re-implemented)

The standing lesson — *a census must read the deployed rule end-to-end, never re-implement the
constant it prices* — binds this instrument. Four instances of that defect are on the record,
one of which flipped a verdict at a frozen bar.

- **S-A** `core/decide.u_assert` — the one written atom, `p·u_correct + (1-p)·u_wrong`.
- **S-B** `core/decide.shaped_u_bar` — the r30 units seam; the anchor `exact` passes through
  unscaled and each optional `voi_scale_*`/`regret_scale_*` defaults to 1.0.
- **S-C** `core/lookup.action_utilities` — the tabular rows over the K+1 atoms and the argmax
  that picks the recorded `chosen_action`.
- **S-D** the owner's utility model out of tree (`$LIFE_AGENT_KB/utility/model.yaml`) folded
  through `core/utility.posterior` under the regime the rows themselves name.
- **S-E** the recorded rows in `$LIFE_AGENT_KB/calibration/decisions.jsonl`
  (`posterior_summary`, `predicted_eu`, `chosen_action`, `action_set`, `utility_fold_version`).

## Criteria (frozen)

**C1 — reproduction.** Re-price each of the three boundary rows from its RECORDED posterior
through S-A..S-D as imported objects. *Criterion: the reproduced argmax equals the recorded
`chosen_action` on 3 of 3.* Fewer than 3 of 3 and the reading is UNREADABLE — the instrument is
not seeing the deployed rule, and no verdict may be taken from it.

**C2 — the verdict.** Conditional on C1 = 3/3:
- **PRICED** iff the reproduced 0.875 report beats abstain under the recorded Ū with the full
  declared regret latent in force — i.e. the indifference point genuinely sits below 0.90 and
  the "0.90 bar" is a docstring approximation under a uniform-VOI/R assumption, not a deployed
  constant.
- **LEAK** iff the 0.875 report only beats abstain because some path attenuates the regret term
  (a scale, a scoped substitution, a fold-version mismatch, a defaulted latent) that the
  owner's declaration does not license. The attenuation is then named and its size published.

**C3 — the empirical bar.** Compute p†, the deployed indifference point where
EU(report) = EU(abstain) under the recorded Ū, as a number. *Criterion: all three rows fall on
the side of p† their recorded action implies.* Any row on the wrong side is a defect and is
named as one, whatever C2 reads.

**C4 — scope.** The reading covers only rows in the report family in the rounds 5–8 dogfood
window. It does not touch the eval corpus, does not re-run any ask, and buys nothing.

**C5 — mutation.** Every load-bearing predicate in the instrument is verified RED by mutation
before its output is believed (the r05 lesson: audits ship defects in their own measures).

**C6 — consequence (frozen before the read).**
- **PRICED** → C's 13 instances are the bar working as declared; conferral 2's ruling on C
  resolves to *preference, not defect*; p† is published as the empirical bar and the docstring's
  "0.90" is corrected to name the assumption it holds under. No lever opens from C.
- **LEAK** → C is partly a defect; the leak's size is published and the C lever question
  re-opens under its own pre-registration. The hard clause still binds any successor.
- **UNREADABLE** → nothing is concluded; the instrument's failure is published and the reading
  is either repaired under this same pre-registration or abandoned.

In every branch **nothing is built by r32** and the round-8 record is untouched.

## Disclosure rules

Deviations, instrument defects and mid-read corrections are published in the report with
timestamps, never silently fixed — the discipline every round of the measurement ran under.
