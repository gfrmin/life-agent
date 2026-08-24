# r09e — the tree of record, read at $0 (ruling 1's free half)

**Status:** READ 2026-08-25, $0. This is not a checkpoint with its own frozen criteria; it is
the enactment of ruling 1 of the entity-key conferral ("targeted warm, then read"). The frozen
thing it speaks to is **run 14's third conjunct — zero new wrong commits** — which run 13's
FAIL left open for the tempered tree.

## Why it could run today

The conferral priced a warm before any read was possible. The rehearsal falsified that: three
of the five named rows already served at $0, because the §18.9 warm-through keeps warming the
store pass by pass. So the read ran first and cost nothing; **the priced warm was never
needed for it**.

## Method

`scripts/replay_audit.py`, deployed arm only, against run 13's own record
(`gate-20260824T144002`), on the **tree of record** — the parked branch carrying
JOIN + T1 + A1 + A2 + D3. Staging root, ledger mirror off, pin verified with the src drift
acknowledged. **66 of 104 questions readable, up from 58 at r09d** — the difference is
accumulated warmth, not a change of method.

The tree carries the spend-seam fix landed the same day, so the $0 claim is now a contract
rather than a coincidence (the conferral's correction 4 has the detail).

## What it reads

| | run 13's record, same 66 rows | the tree of record |
|---|---|---|
| correct | 59 | 57 |
| withheld | 4 | 7 |
| **wrong** | **3** | **2** |

Fidelity to the record is 63/66. **It is not a control here**: the tree deliberately differs
from the one that produced the record, so a disagreement is the temper's effect, and all three
disagreeing rows are exactly the rows that moved.

### The four known-wrong rows

| row | readable? | tree of record |
|---|---|---|
| a corroborate-tier row | yes | **still commits wrong** (n_obs 6, S1×3 → S3) |
| the entity-qualifier row | yes | **still commits wrong** (n_obs 5, channel only grows: base 3 → S1 4 → S1 5) |
| the warm-deliberate row | yes | **repaired** — reported wrong before, now withholds (n_obs 13 → 2) |
| the superset-confirm row | **no — still cold** | unreadable |

**Consequence, stated plainly: firing run 14 on this tree would fail the zero-new-wrong-commits
conjunct.** That is now measured on two rows rather than predicted, so the conferral's option B
is refuted on its own terms. Nothing was spent to learn it.

### The collateral, and what it is not

Two rows the record has correct now withhold. A five-row isolation on the A2 head (the same
tree **minus D3**, $0) attributes them: both still withhold without D3, with the same leader on
one and a lower-confidence action on the other. **D3 is not the cause** — the loss belongs to
the earlier temper stack (T1/A1/A2), which is where the r09b/r09c readings already priced it.
On these five rows D3 changes only the evidence count (n_obs 5→9, 1→2) and no outcome, so its
one measured benefit stands where it was measured and its collateral here is zero.

The repaired row repairs with and without D3 too.

## What is still unreadable

38 rows, including one of the four known-wrong rows. Coldness is pass-order-dependent, so the
readable set will keep drifting upward on its own; the warm instrument
(`$LIFE_AGENT_KB/eval/gate-outside-option/warm-rows.sh`) stays prepared and rehearsed for the
rows that do not warm themselves, and its priced half waits for the account's reset.

## Disclosure

The scorer reused from r09d prints that checkpoint's frozen criterion labels (S1''–S4''). They
are **not** criteria for this read and no verdict here is taken from them; they are left in the
artefact because editing an instrument's output after a reading is worse than explaining it.
The two numbers this read stands on — the wrong-commit count and the collateral attribution —
are computed from the rows dump and the record's own grades.

Artefacts: `$LIFE_AGENT_KB/eval/window/r09e-*`.

## What it licenses

The entity key's one repair candidate among the known-wrong rows is **now readable and still
wrong** — which is exactly the row the census said the key discriminates cleanly. Under the
owner's frozen bar (zero channel harms **and** at least one wrong-commit repair), E1 can now be
pre-registered and swept at $0 against evidence rather than against a prediction.
