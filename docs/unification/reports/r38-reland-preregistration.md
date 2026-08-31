# r38 — re-landing the value-join unification: PRE-REGISTRATION

Opened by `D-2`'s successor clause, on the evidence of
[`r37-live-census.md`](./r37-live-census.md). Decision to proceed published as
[`DECISIONS.md` `GD-8`](../DECISIONS.md). **Committed before any `src/` change** (`M-3`).

## What ships

`bridge/server._lattice_join`'s identity **default** moves from `LK._norm_value` to
`LK._candidate_key` — the §4.2 declared identity that `candidates_from`, `render`, `era_split`,
the S2 grow join and the confirm probe already use. r37 made the identity a parameter, so the
lever is now literally one default argument. **No new rule is invented**; the join site stops
disagreeing with the five sites around it.

r37's drift gate stays and inverts with it: `_join_tap`'s counterfactual must then run under
`LK._norm_value`, and no other `src/` call site may pass `key=`. The tap keeps measuring the
same disagreement, from the other side.

**Scoped out, again and for the same reason:** widening `_candidate_key` itself (B2 — dial
prefix, sub-`_CANON_MIN_DIGITS` affixes). It invents a rule and breaches the confident-wrong
boundary the key's own docstring declares. Chasing a larger row count is not a reason to
reopen it (`GD-8`).

## What r34 lacked and this has

Two different things, and r36 conflated them:

1. **A measured live firing surface** — `{q2-027, q2-028, q2-029, q2-090}`, from r37 §5. r34's
   surface was lifted from recorded wire and was a **lower bound**: it missed q2-028 and q2-029.
2. **A baseline that differs by the lever alone** — **run 22**. r34's K3 baselined on run 20,
   whose tree differed by the lever *and* r33 *and* #127, and two of its three changed rows
   belonged to the other two (`M-18`).

## Frozen criteria

Baseline for every row-level criterion is **run 22** (`gate-20260831T190924`), whose tree is
this arm's minus the lever and nothing else.

| id | criterion | kill? |
|---|---|---|
| **K1** | **Zero NEW wrong commits.** A wrong commit is NEW iff that row was not wrong in run 22's typed arm. Class-based and prospective (`M-8`). | **KILL** |
| **K2** | **No named wrong-commit class worse than run 22** — the hard clause (`M-1`). The named classes: the superset-confirm row, the warm-deliberate row, and q2-090's wrong-leader class. A row moving *into* any of them is blocking on its own, whatever the totals say. | **KILL** |
| **K3** | **Rows whose action differs from run 22 are a subset of r37's measured live firing surface** `{q2-027, q2-028, q2-029, q2-090}`. This is r34's K3 with both defects repaired: the surface is measured, not inferred, and the baseline differs by the lever alone. | **KILL** |
| **K4** | **P(Δ>0.05) ≥ 0.90** under the production Ū, δ and level unchanged. | **KILL** |
| **K5** | On any firing row whose action changes, the leader credence is **≥ run 22's**. | **KILL** |
| **K6** | Abstain→report conversions on a gold are **recorded, not a kill**. | no |

## Directional claims, frozen

- **Exactly one row changes: q2-027, abstain → correct report**, reproducing run 21.
- **q2-028 and q2-029 fire and stay inert** — they abstain in runs 20, 21 and 22, and the
  lever is *correct but inert* there (the r30b category, named in advance this time).
- **q2-090 does not change** — it abstains in all three runs and stays a named wrong-leader
  class, not a wrong commit.
- Aggregate lands near run 21's **0.969 / +0.544**; run 22 read 0.965 / +0.534.

If more than the four surface questions move, K3 kills — and that would say the live surface is
*itself* a lower bound, which would be a finding about r37's instrument and would open its own
successor rather than a re-reading of this one.

## What this run does NOT claim

**The benefit is at or below §6.13's commit-wobble floor of 2.** One row is not a statistical
result and must never be quoted as one (`GD-8`). The case for the lever is structural — one
declaration of candidate identity instead of two — and the criteria above exist to prove it
does no harm, not to prove it does good.

## Consequence

`D-2`'s defaults, no keypress. **PASS ⇒ merge and deploy.** **FAIL ⇒ revert from the deploy
path, publish, open a successor.** A **second FAIL on K3** parks the lever, publishes why, and
advances to Arc C.

## Cost

One typed arm (~$0.25); the baseline arm is a recorded replay. Plus $0 replays and the tap
census.
