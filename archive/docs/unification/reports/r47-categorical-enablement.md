# r47 — the four-item categorical enablement: READING

**Pre-registration**: `docs/unification/reports/r47-categorical-enablement-preregistration.md`,
committed `9c505bd` **before any `src/` change** (`M-3`). Ten criteria, three KILL.
**Cost $0** (engine CPU on the two built binaries). **Nothing deployed**: the categorical world
stays env-disabled and byte-inert without `LIFE_AGENT_MEMBRANE_CAT`. `M-1` not engaged.

## Verdict — all ten criteria PASS; the enablement is built and merged, nothing enabled

The deployed categorical episode — `categorical.decide_categorical` / `run_categorical`, the
code the shadow supervisor actually calls — now speaks the enabled world at proplang HEAD.
`GD-22`'s four items land in `categorical.py`, the ONE declaration both the supervisor and any
future replay bind, so `r48` measures through the deployed rule rather than a re-implementation
of it (`M-7`).

| id | criterion | verdict |
|---|---|---|
| **C1** | **(KILL)** arm B accepts the episode end to end, k ∈ {2,3,5} | **PASS** — handshake ok, every tick accepted, act decoded; `models` 688 / 1032 / 1720 |
| **C2** | the pre-enablement episode is refused by arm B | **PASS** — `bad hello`, at the handshake |
| **C3** | arm A unharmed | **PASS** — completes and decodes at all three k (`models` 3202 / 4803 / 8005) |
| **C4** | **(KILL)** the binary world byte-untouched | **PASS** — no `world.py` change; the shared objects are BOUND, not copied |
| **C5** | one declaration each | **PASS** — `theta_grid`, the clock row and the coverage rule have one spelling each, test-pinned |
| **C6** | byte-inertness survives | **PASS** — `test_categorical_default_off_is_inert` unchanged and green |
| **C7** | **(KILL)** every changed predicate RED by mutation | **PASS** — 4/4 RED on the committed tree, tree restored clean |
| **C8** | suite, lint, types green | **PASS** — ruff clean, mypy clean, suite green; the two fixture moves were predicted |
| **C9** | no measurement read | **PASS** — no bar, crossing or `respond_j` claim is made here |
| **C10** | PII-clean and costed | **PASS** — synthetic summaries, numbers-only rows, tree pinned, $0 |

## What landed, and where

| # | item | site | shape |
|---|---|---|---|
| 1 | `codebooks.theta` | `handshake_decl_cat` | **binds** `world.theta_grid(u_bar)` unchanged — the one rule, K-independent (`GD-22`) |
| 2 | the `clock` row | `handshake_decl_cat` | **binds** `world.CLOCK_NAME` / `clock_price` / `CLOCK_BATCH` |
| 3 | a menu-bearing tick | `decide_categorical` | the evidence ticks gain `menu: [act]`; the decide tick already had it |
| 4 | full indicator coverage | `cat_features` | every name in `cat_indicator_names()`, dormant at `0.0` |

Item 4's coverage derives from `cat_indicator_names()` — the same list the namespace and guards
are built from — so a new indicator cannot be declared without being emitted.

## The two things the run corrected in me

Stated before the results they touch (`r05`).

**1. Prediction 2 is REFUTED, and instructively.** It said C2 would fail "on item 4 first, not
item 3" — a claim about which *tick* item bites. The measurement shows arm B refuses at the
**handshake** (`bad hello`), so **no tick is ever sent** and neither tick item can be the first
to bite. Item 1 (codebooks) gates everything, exactly as leg D's K1/K2 read it; the prediction
was written as though the tick items were reachable, and they are not. The frozen text stands
as written, refuted.

**2. A test I wrote asserted an invented requirement, and the deployed rule refuted it.** A
first draft also added the clock name to the categorical namespace and pinned
`clock["name"] in world["namespace"]`. An **existing** assertion
(`names[-1] == ACT_NAME`) failed, which sent me to the deployed binary world: it keeps
`think` **out** of its 19-name namespace, and `r44` verified that exact shape at arm B across
59 battery cases. So the requirement was mine, not the wire's. The namespace change is reverted
and the test now pins the deployed shape **on both worlds**, recording that an earlier draft
asserted the opposite from first principles. This is `M-7` in test form — a predicate asserted
from reasoning rather than from the rule it prices — caught by the suite that already existed.

## Leg D's drift pin fired, as designed

`scripts/membrane/categorical_twin.py`'s `base_cat_decl` is *defined* as the deployed
declaration verbatim, and its test pinned a base carrying neither codebooks nor a clock. r47
moved the deployed declaration, so the pin fired. Both facts are now recorded in that test: the
base carries the items, and the instrument's `codebooks=` / `clock=` deltas are **idempotent**
post-r47 rather than additive — asserted explicitly so the instrument cannot appear to vary
something it no longer varies. **Leg D's K1/K2 arms measured a world without those items and
re-running them needs leg D's own tree** (`M-28`). The instrument stays in tree, tested and
dormant, like `carrier_audit.py` and `replace_audit.py` before it.

## Disclosures for `r48` (C9 forbids reading them here)

- Every enabled episode observed on either arm chose **`gather`** (prediction 5's shape, and
  `r45`'s C3 constant). Whether that is the binder still binding is `r48`'s question, under
  today's Ū, through the deployed runner. **No claim is made here.**
- Arm B's replies carry the per-code readout (`p0`, `argmax_code`, `p_argmax`, `p_codes[]`);
  **arm A's do not** — #20's readout postdates the `r41` pin. A measurement wanting `p0` must
  therefore run on arm B, which is also the deployed arm.
- Arm B's `models` counts reproduce leg D's `344·k` exactly (688 / 1032 / 1720), an independent
  cross-check that the enabled declaration is the one leg D measured.
