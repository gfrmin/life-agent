# r44 — the world-declaration repair: PRE-REGISTRATION

Opened by [`r43`](./r43-selection-contract.md) and `GD-12`. **Committed before any `src/`
change** (`M-3`).

## The one job

Make the shadow's world declaration speak the engine's current contract, so that a §18 bar
becomes **readable**. r44 does not read one.

[`r42`](./r42-engine-door.md) found four door changes; r43 resolved the blocking one and
narrowed another. Their current state:

| item | state after r43 | in r44? |
|---|---|---|
| 1 · `codebooks.theta` | required; grid is the hypothesis space, priced `n(17n − 16)`; **grid unchosen** | **yes** |
| 2 · full-coverage ticks | required; no-op on arm A; **rider: the writable name is EXCLUDED, never padded in** | **yes** |
| 3 · the evidence path | the act can never be a tick feature, so the engine picks what the fold conditions on | **no — r45** |
| 4 · the inert utility | **solved**: a `clock` row routes selection to the substitution chooser; 5/5 on the host's own argmax | **yes** |

**Item 3 is scoped OUT with a reason.** It is a modelling question about what the shadow learns
from, not a declaration fix, and it carries its own design candidates (a separate non-writable
`acted` name; one-point menu grids; a re-shaped menu). Bundling it would put two levers on one
reading — the r30b precedent. P1 stays blocked behind it, as `GD-11` ruled.

**The `act` guard row is scoped OUT with it.** r43 measured it to repair a *different* defect —
an act-blind belief — and to be the one row that is **not** a no-op on the control (`models`
2393 → 2681). It is a learning-side repair and belongs with item 3.

## What lands

`src/life_agent/membrane/world.py` (and `session.py` only if the tick shape demands it).
**No decide-path change.** The membrane stays env-disabled; nothing is installed.

### Item 1 — the theta grid, chosen by a declared rule

The grid is not picked by eye and not fitted to arm A's `models` (r42: two enumerators, a
reference, never a target). It is the deduplicated union, at 3 decimal places, clipped to
(0, 1), of:

1. the **measured operating rate** — `y = 1` frequency over the reaction stream joined to
   `decisions.jsonl` through `core.reactions.VERDICT_Y`, deduplicated on `decision_id`
   (latest reaction wins, the `r41` supersession rule). Read at pre-registration time:
   **0.857** (60 / 70, zero unmapped);
2. every finite **affordance crossing** of the deployed `u_bar` in (0, 1) — the p1 values at
   which `argmax_action` changes its mind, computed from `utility_by_action`, which is where a
   consumer threshold actually sits in this world;
3. the **5th, 50th and 95th percentiles** of the recorded shadow `p1` (`shadow.jsonl`,
   `readouts.p1`, n = 6 610);
4. the endpoints **0.05** and **0.95**.

The resulting `n` and its price `n(17n − 16)` are **reported with the grid**, and the rule is
what is frozen — not the numbers it happens to produce today.

Rationale for (1) and (2) together: the engine repo's `#19` records a false clear in which a
rung placed *near* but not *at* the operating rate lets the posterior settle on the KL-nearest
rung and clear a consumer threshold it should not, with error that **grows** under data. A rung
at the rate is the recorded cure; a rung at each crossing is the same argument applied to this
world's actual consumer.

### Item 2 — coverage, with r43's rider

`shadow_features` emits **every declared name except the menu names**. Padding the writable name
in is not conservative — it is refused (`feature/assignment collision`, both arms).

### Item 4 — the clock row

`"clock": [{"name": "think", "price": <declared>, "batch": 1}]`. `think` is not a namespace
name, so it is admitted. **This is not free and is not presented as free**: it adds an internal
deliberation act to the option space that this world does not otherwise model. The price is
declared, and W3 measures whether it ever wins.

## Frozen criteria

| id | criterion | kill? |
|---|---|---|
| **W1** | With the repair, HEAD answers `ok: true`, and arm B's chosen act equals `world.argmax_action(u_bar, p1)` on a declared battery of **≥ 20** (u_bar, feature-vector) cases in which **each of the four affordances is the predicted winner at least 3 times**. The battery and its size are reported (`G-3`). | **KILL** |
| **W2** | Every declared row is either **byte-identical on arm A** over a multi-tick session, or **named in the report as a deliberate change to the control with its effect measured**. No row changes arm A silently. | **KILL** |
| **W3** | The internal `think` act **never wins** on the W1 battery. If it does, the report names where and the price is **re-derived from what `think` is worth**, never raised until it stops firing. | **KILL** |
| **W4** | **No decide-path change**: `git diff master -- src/life_agent/core src/life_agent/bridge src/pkm` is empty, the membrane stays env-disabled, and nothing is installed on this machine. | **KILL** |
| **W5** | Every load-bearing predicate verified **RED by mutation** before the reading (`G-3`: a control counts only if removing what it controls for turns it RED). | **KILL** |
| **W6** | `#19`'s placement warning is **re-executed on this world**, not cited: measure a rung *near but not at* a consumer threshold against one *at* it, and report the difference. The *result* informs the grid and is a disclosure; only an inability to make the measurement kills. | — |
| **W7** | Suite, ruff, mypy, the PII guard and the poison census green; `M-16`/`M-21` repo hygiene. | **KILL** |

## Consequence — frozen

1. **All KILL criteria pass** → the declaration lands on master. The membrane stays disabled and
   **no §18 bar is read by r44**; what changes is that one becomes *readable*. P0-4's smokes and
   r45 (item 3 + the `act` guard + P1) open next.
2. **W1 fails** → the repair is insufficient; publish the battery and open a successor on what it
   showed. No bar is read, nothing is loosened (`A-2`: the fix is never a softer bar).
3. **W2 fails in its silent-change sense** → revert the offending row and re-scope in the same
   report.

`D-2` defaults; no keypress. `M-1`'s hard clause is not engaged — nothing here touches the
deployed decide path or any named wrong-commit class.

## Registered expectations

Stated before the build so the reading can be checked against them (`M-4`: these add no kill):

- **The grid rule yields a small `n`** — the operating rate, the crossings, three percentiles and
  two endpoints collide heavily at 3 decimal places, so the price should land in the hundreds of
  worlds, not the thousands.
- **`think` never wins** at any price ≥ 0, on the evidence of r43's single-vector sweep
  (0 → 10⁶ invariant). If it wins anywhere in the battery, that sweep was not representative and
  the disclosure matters more than the criterion.
- **W2 passes for all three rows in r44's scope** — theta and coverage were measured free on arm A
  by r42, and the clock row by r43.

## Cost

**$0.** Both engine binaries already exist; no model calls; no priced run.

---

## Amendment 1 — crossings enter at full precision (blind, before any reading)

**Disclosure of ordering first:** this amendment was written while the repair was being built,
**after** the pre-registration was committed and **before** any battery ran. It is prospective
with respect to every reading below, but it was not committed as a separate act beforehand, and
that is a deviation from `M-4`'s cleanest form. It is recorded here rather than folded silently
into the rule.

The rule above says the grid is the union of its four sources "deduplicated ... at 3 decimal
places". Re-read against the artefact it names (`M-3`), that clause **defeats the rule's own
purpose**: an `argmax_crossings` threshold rounded to 3 dp is a rung *near* the crossing rather
than *at* it, which is exactly the `#19` hazard the placement argument exists to avoid.

> **Amended.** Crossings enter the grid at **full precision**. The other three sources are
> already stated at 3 dp. Two rungs closer than **5 × 10⁻⁴** are one rung, and a **crossing
> always survives** that collision.

No criterion changes; the rule becomes the thing it was written to be.
