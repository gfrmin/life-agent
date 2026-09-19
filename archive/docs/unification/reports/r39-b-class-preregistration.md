# r39 — the B class (narrative inclusion): PRE-REGISTRATION

Opened by `A-1` (levers from the Stage-4 measurement before proplang) on conferral 2's
candidate 2 — *narrative inclusion calibration*, B, **9 instances**, described there as
*"the kill is one constant across four rounds; a per-cell recalibration is the registered §7
path."* **$0.** Committed before any `src/` change (`M-3`).

## Disclosure, up front

Writing this, I inspected **one** narrative decision row to establish what the log records
(its keys, and that `posterior_summary` carries `cells`, `n_proposed`, `n_included`,
`abstain_reason`). That row's own numbers were visible in doing so. Every criterion below is
frozen against the **population** of 945 narrative rows, not that row, and the quantities the
criteria name were not computed before this file was committed. Recording it because a
pre-registration written after a peek is worth less than one written blind, and the reader
should price it accordingly (`M-4`'s spirit: the record is what makes a frozen criterion mean
anything).

## The question

B is *"claims proposed, none included"*. The deployed rule is `narrative._claim_pref`:
`optimise{include, withhold}` per claim, where `withhold` is the gauge zero `u_abstain` and
`include` is the **integrated** claim-EU over the cell Beta,
`E_θ[(θ·tf)·u_assert(θ·tf)] − κ_att`. So a claim is included iff that integral clears zero.

Conferral 2 attributes the kill to **one constant**. There are three candidates for which
constant, and they have different consequences:

1. **`κ_att`**, the per-claim attention cost — a tunable price, and a recalibration target.
2. **The cell Betas** — population-calibrated from the `eval_claim` stream; low `E[θ]` would
   make this a *calibration* problem, which is what conferral 2 assumed.
3. **`u_wrong`** — the declared exchange rate. If the break-even reliance implied by
   `u_assert` sits above what any cell can reach, then B is **not** a calibration problem at
   all: it is the same threshold boundary as C, which `A-3` already closed
   (*"C is a dispersion problem, not a threshold problem; bar-move levers are closed"*).

**If (3) holds, B and C are one class**, conferral 2's candidate 2 is mis-scoped, and the
lever it proposes is one `A-3` has already ruled out. That would be the finding.

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **B1** | The population is **named and non-empty**: the number of narrative rows, how many carry `abstain_reason = "all claims below the inclusion threshold"`, and how many have `n_proposed > 0`. An empty population fails the read (`G-3`). | **KILL** |
| **B2** | **Break-even reliance is computed from the DEPLOYED functional**, by binding `narrative._include_fn` / `narrative.include_eu` and the production `u_bar`, never by re-deriving the algebra (`M-7`, now at six instances). | **KILL** |
| **B3** | The three candidate constants are separated **numerically**: for each, the value it would need to take for **any** observed cell to clear inclusion, holding the other two at their deployed values. | **KILL** |
| **B4** | Every load-bearing predicate verified **RED by mutation** before the read. | **KILL** |
| **B5** | The read reports **how many of the 9 measured B instances it can actually locate** in the decision log, and names the remainder rather than dropping them (`M-8`). | **KILL** |

## Consequence, frozen before the read

- **If `κ_att` or the cell Betas are the binding constant** → conferral 2's candidate 2 stands;
  r39 opens a successor pre-registration for the recalibration, with `M-1`'s hard clause
  binding (conferral 2's own warning: candidate 2 *admits* answers presently withheld, and
  admitted answers are the only way a wrong commit can enter).
- **If `u_wrong`'s break-even is the binding constant** → **B is C**, candidate 2 is
  mis-scoped, `A-3` already governs it, and **no lever opens**. r39 publishes that, updates the
  register, and the queue advances to **Arc C (proplang)**.
- **If the three cannot be separated** → say so; a read that cannot attribute is a null result,
  not a licence.

Nothing is bought either way. r39 buys no run and changes no `src/`.

## Cost

$0.
