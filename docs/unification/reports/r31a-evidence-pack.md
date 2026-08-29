# r31a — the $0 evidence pack — READ (2026-08-29, $0)

Move 2 of the roadmap approved 2026-08-29. Three reads, no `src/` behaviour change, no priced
run: (i) re-pin run 18's splice on the r30b tree, (ii) the C9 both-utilities reading, (iii) the
off-gate sweep that must predict r31's assert set before money is spent (run 9's discipline).

**Ordering disclosed up front.** The Pop-B probe below was an *unregistered exploratory read* of
the existing decision record — taken before this document existed, while scoping r31. It is a
read of what is already on disk, not a criterion-gated verdict, and what it decided (r31's
population) was decided by an owner ruling, not by the read. The sweep's criteria (S0–S4) were
frozen in `scripts/interval_sweep.py`'s docstring and **committed at `064f995` before the
instrument read anything**.

## (i) Run 18 re-read on the r30b tree

`gate_splice.py --splice r30b-reread <run-18 paired> <run-18 paired> archived --pin … 0.959 0.514`

**Reproduced exactly: P(Δ>0.05) = 0.959, Δ̄ = +0.514 [+0.077, +0.999], Δ_answers = 0.019,
Δ_spend = 0.495; typed 61 ✓ / 2 ✗ / 41 withheld at $0.37, the comparator 95 / 6 / 3 at $39.01.**
The pin against run 18's own published verdict matched. r30b does not move the archive it is
read against — which is what makes the sweep below a statement about the lever rather than about
the tree.

## (ii) C9 — the both-utilities reading

The live Ū printed by the splice carries **no `voi_scale_*` / `regret_scale_*` entries**, so
"Δ under the new utility" and "Δ under the old" are the same number today. Published as a
documented no-op rather than as two identical tables. It stops being a no-op the moment the
owner opts a shape in — that is Conferral 1's item, not this one's.

## (iii) The off-gate sweep — r31's prediction, on the record before the run

`interval_sweep.py --run-id gate-20260826T083356`, reading run 18's own archived decision rows
and the population its `run_meta` pins.

| | |
|---|---|
| **S0 control — recorded action reproduced** | **100 of 102** rows |
| control failures (named, excluded from every count) | `q2-033` (recorded `report`, sweep predicts `abstain`), `q2-049` (recorded `report`, predicts `hedge`) |
| unreadable rows | 0 |
| rows where the lever CAN fire | **5** |
| **predicted reach** (interval wins where the run WITHHELD) | **0** |
| **predicted displacement** (interval wins where the run already committed) | **1** — `q2-059` |
| **predicted `interval-excludes-gold`** | **0** |

**The prediction, stated plainly: r30b changes exactly one row of the pinned 104, and it is a
displacement, not a rescue.** On `q2-059` the engine prefers a covering interval (EU 0.751) over
the crisp report it made in run 18. The interval contains the gold (Winkler x = 0.9903), so it
is not a wrong commit — but the crisp report was *right*, so the realised utility on that row
**falls from 1.000 to 0.903**, i.e. **−0.097 on the row and −0.00093 on the 104-question mean.**

That direction is not a defect; it is the trade a risk-averse claim makes. The engine ranks
under the *posterior*, which did not know the leader was correct; the interval hedges across two
near-agreeing values and wins in expectation. On this row the gamble was unnecessary in
hindsight. With n = 1 that is noise, and it is published as noise — but it is published, because
a sweep that only reports its lever's wins is not evidence.

### What the two control failures mean

Both are rows the archived run committed through the **executor** lane, whose action set differs
from the in-process `action_utilities` this sweep prices (the executor lane has no
`report_scoped_j` rows and the sweep does not reconstruct the transform menu). They are named
and excluded rather than counted, per S0 — a sweep that cannot reproduce the record it reads is
measuring itself. The exclusion is one-sided in the safe direction here: neither row is one of
the 5 where the lever can fire.

### The Pop-B probe (unregistered, exploratory) and what it settled

`aggregate-questions.yaml`'s 15 computed questions are the right population *on shape* — 15/15
classify `quantity` and 12 carry numeric golds, against 19/104 on the pinned set. But the
deployed record says they cannot exercise this lever at all: **all 15 recorded a narrative
abstain (2026-08-26), and none ever produced a lookup-family decision.** The cached router in
fact admits 11 of the 15 as typed lookups — so the fallthrough is not routing, it is
*extraction*: a computed answer is by construction not present in any single chunk, the
per-chunk extractor yields zero grounded observations, and no candidate set is ever built. An
interval claim needs ≥2 numeric candidates; Pop B has zero.

**Consequence, ruled by the owner 2026-08-29 (three answers, recorded here):**

1. **r31 reads Pop A only, as a do-no-harm gate** — zero new wrong commits, no named class
   worse, the 5-row reach published as a bound. It is not a proof of benefit and must not be
   reported as one; benefit is measured in vivo during the exit week.
2. **The composition question — `extract_amounts` as a priced act inside the argmax, so computed
   questions get a candidate set at all — is PARKED with a named trigger:** computed-question
   misses dominating the exit week's FAILURES entries. Pricing an actuator before the exit week
   says how badly it is wanted is the shape of run 17's mistake, and r29's two riders bind any
   such refit.
3. **The exit week starts immediately after r31 deploys.**

## What r31 is actually buying

The sweep already knows the lever's effect on this population at $0. What it cannot exercise is
the **integration**: the `extra_actions` wire, the daemon's ranking of body-priced rows, the
executor's refusal path when the decider cannot rank them, and the render. That — plus the
standing rule that an argmax change never deploys unread — is what the priced run buys. It
should be reported as an integration and do-no-harm gate, and the honest expectation registered
here **before** it fires is: **one changed row, a displacement, Δ moving by roughly −0.001.**

## Deviations disclosed

1. The Pop-B probe preceded this document (above).
2. **The sweep shipped a defect in its own measure, caught by its control before any verdict:**
   it read the module-default question file — a 20-question legacy set sharing **zero** ids with
   run 18 — and reported 102/102 unreadable. It now reads the population from the run's own
   `run_meta` pin. This is the fifth instance in this arc of the standing lesson (*a census must
   read the deployed rule end to end, never re-implement or re-guess what it prices*), and the
   reason S0 is a frozen criterion rather than a nicety.
3. The sweep prices the in-process action table, not the executor lane's; the two control
   failures are that limitation showing itself, named rather than absorbed.
