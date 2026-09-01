# r44 — the world-declaration repair: READING

Pre-registration + amendment 1:
[`r44-world-declaration-preregistration.md`](./r44-world-declaration-preregistration.md),
committed before any `src/` change (`M-3`). **$0. No decide-path change. Nothing installed,
nothing enabled.**

## Verdict

**All six KILL criteria pass. The declaration lands; no §18 bar is read.** The shadow's world
now speaks the engine's current contract: it handshakes at HEAD, its ticks are served, and its
declared utility **decides** — 59 of 59 battery cases agree with `world.argmax_action` read at
the engine's own reported belief, across 27 distinct beliefs and all four affordances.

| id | verdict | evidence |
|---|---|---|
| **W1** | **PASS** | battery 1: 24/24 (6 `u_bar` × 4 feature vectors). battery 2: **35/35** (5 `u_bar` × 7 conditioning histories, **27 distinct `p1`**). Predicted winners: respond 13 · abstain 8 · gather 7 · ask 7 — each ≥ 3 |
| **W2** | **PASS** | all three rows **byte-identical on arm A** over 1 hello + 5 ticks; `models` 2393 → 2393 in every configuration |
| **W3** | **PASS** | `think` fired **0** times in 59 cases |
| **W4** | **PASS** | `git diff master -- src/life_agent/core src/life_agent/bridge src/pkm` **empty**; membrane still env-disabled; nothing installed |
| **W5** | **PASS** | **8/8** mutations RED before the reading |
| **W6** | read | the placement effect is real, **small, and not in the naive direction** — see below |
| **W7** | **PASS** | 3 134 passed / 35 deselected; ruff clean; mypy clean on 147 source files |

## What the grid rule produced

The rule was frozen; these are the numbers it yields on the deployed `u_bar`:

```
crossings   0.02, 0.997778          (abstain↔gather at κ_att; the respond bar)
grid  n=8   0.02  0.05  0.18  0.339  0.857  0.864  0.95  0.997778
price       models = n(17n − 16) = 8 × 120 = 960
clock       price 11.0 = (max u − min u) + 1, batch 1
```

The registered expectation — *"hundreds of worlds, not thousands"* — is met at **960**. Note the
two rungs at **0.857** and **0.864**: the measured operating rate and the recorded shadow's p95
land 7 × 10⁻³ apart, well outside the 5 × 10⁻⁴ collision, so both survive. That crowding is what
W6 turns out to be about.

## W1 — the utility decides, and it decides at the crossings

Battery 2 is the one that carries the criterion. Battery 1 varied the **feature vector**, and the
honest reading of it is that **a fresh prior cannot distinguish feature vectors**: all four
summaries returned the same `p1` within a `u_bar`, so its 24 cases are 6 distinct decisions seen
four times each. That is disclosed rather than counted. Battery 2 varies the **belief** instead,
by conditioning 0/2/6/14 ticks of `evidence = 1` or `evidence = 0` before the decide:

| `u_bar` | (predicted act, `p1`) across the seven histories |
|---|---|
| deployed | gather at 0.040 · 0.069 · 0.123 · 0.532 · 0.898 · 0.940 · 0.964 |
| respond-fav | respond at 0.066 · 0.107 · 0.171 · 0.540 · 0.859 · 0.903 · 0.920 |
| ask-fav | ask at 0.040 · 0.069 · 0.123 · 0.532 · 0.898 · 0.940 · 0.964 |
| abstain-dom | abstain at 0.066 … 0.869, then **respond** at 0.902 · 0.915 |
| knife-edge | abstain at 0.066 · 0.115 · 0.206, then **respond** at 0.527 · 0.829 · 0.900 · 0.920 |

The last two rows are the ones that matter: **the argmax changes its mind inside a single
`u_bar`, and arm B changes with it**, at 0.90 and at 0.53 respectively. A chooser that ignored
the utility could not do that, and the r42 baseline (a constant `abstain`) fails these rows by
construction.

## W2 — every row is free on the control

| declared row | arm A hello identical | arm A ticks byte-identical | `models` |
|---|---|---|---|
| full coverage (item 2) | yes | yes | 2393 → 2393 |
| + `codebooks.theta` (item 1) | yes | yes | 2393 → 2393 |
| + `clock` (item 4) | yes | yes | 2393 → 2393 |

So **one declaration serves both arms**, and the repair can be verified before the swap rather
than after it — which is what r42 established for items 1–2 and r43 for the clock, now
re-measured against the actual shipped declaration rather than against hand-built stand-ins
(`M-7`).

## W5 — the mutation ladder

| id | predicate | mutation | result |
|---|---|---|---|
| M1 | the grid reads the **measured** rate | `OPERATING_RATE` 0.857 → 0.421 | RED — the rung moves; 0.857 leaves the grid |
| M6 | the grid reads the **crossings** | suppress `argmax_crossings` | RED — exactly `{0.02, 0.997778}` drop out |
| M7 | coverage is exhaustive | — | RED-ok — 18 names = `t` + 17 indicators, `act` excluded |
| M2 | the `think` detector can fire | clock price → −1000 | RED — `{"internal": "think"}` |
| M3 | coverage is load-bearing | send the pre-r44 sparse tick | RED — `tick refused: missing declared [...]` |
| M4 | `theta` is load-bearing | drop `codebooks` | RED — `bad hello` |
| M5 | the **clock** is load-bearing | drop `clock` | RED — `abstain` (the head) where the utility predicts `gather` |

**8/8.** M2 and M5 are the two that make W3 and W1 mean anything: without them, "think never
fired" and "arm B tracked the argmax" would both be consistent with a detector that cannot fire
and a criterion that cannot fail.

## W6 — `#19`'s placement warning, re-executed on this world

Two worlds identical but for one rung — one **at** the measured rate (0.857), one **near** it
(0.85) — fed the same stream at that rate (blocks of `1 1 1 1 1 1 0` = 6/7 = 0.857). Belief-only,
so the clock is omitted; it changes the choice, not the update.

| ticks | `p1` with the rung **at** 0.857 | with it **near** (0.85) | gap |
|---|---|---|---|
| 14 | 0.896664 | 0.895241 | 0.001423 |
| 42 | 0.869027 | 0.866320 | 0.002707 |
| 98 | 0.860848 | 0.857659 | **0.003189** |

**The gap grows monotonically with data** — the signature `#19` names. But the effect on this
world is **small** and **not in the naive direction**: the *near* grid is the one that ends
closer to the true rate. The reason is visible in the grid itself — the rate rung at 0.857 has
the p95 rung at 0.864 seven thousandths away, so the posterior spreads across a **pair**, and
which pair is nearer the truth is decided by the neighbourhood rather than by the single rung.

**The rule stands exactly as frozen.** Re-tuning the collision threshold to merge 0.857 and 0.864
would be tuning after seeing a result, which is the one thing a frozen rule exists to prevent.
Registered for a successor instead: *the placement lever is the grid's local density, not one
rung* — and at these magnitudes (3 × 10⁻³ against crossings at 0.02 and 0.998) **no false clear
is reachable on this world at this data volume**, which is why nothing is changed on the strength
of it.

## The cost the clock buys — disclosed, not buried

`Host.hs` reaches the substituting chooser only through the clock, and `thinkValue` takes its
preposterior branch whenever `batch ≥ 1` — which the wire **enforces** (`bI >= 1`). So the
lookahead is not optional: every decide pays for it, including the ones where `think` provably
cannot win.

```
with clock    : 297 ms per decide (median of 3 runs × 5 ticks)
without clock : 135 ms
```

**≈ 2.2×, structurally.** For reference the recorded shadow's own `decide` rows sit near 80 ms
on arm A at 2393 models. This is the price of a utility that decides, and it is stated here so
that a later "the shadow got slow" is not a mystery.

## Found en route — the repair has an untouched twin

`M-6` says an anomaly found en route is a disclosure item in the checkpoint that finds it, never
a new arc, so this is named and **not built**:

**`life_agent.membrane.categorical` declares a second world** — `handshake_decl_cat` /
`cat_features`, the E1 stage-1 categorical mirror (`obs_arity = K + 1`, value-indexed acts) —
and it carries **all three** of the defects r44 just repaired in the binary world:

- no `codebooks` key ⇒ `bad hello` at HEAD (item 1);
- `cat_features` emits the applicable indicators only, on a docstring that still states the dead
  contract verbatim — *"absent names read 0.0 on the wire — dormancy is free"* (item 2);
- no `clock` row ⇒ `chooseEU` ⇒ the option-space head, whatever the utility says (item 4).

It is env-gated and disabled (`config.membrane_categorical`), so nothing is broken today. But it
is **exactly the world §17.6's E1 re-earn path runs on**, so E1 cannot open until it is repaired,
and repairing it is not a copy-paste: its menu grid is per-question (`act_grid_cat(k)`), so its
crossings — and therefore its theta grid under r44's rule — are per-`K`. **Scoped to r45**, whose
own pre-registration must state whether the two worlds share one declaration of the rule or two.

## Deviations, disclosed

- **Amendment 1's ordering.** It was written during the build, after the pre-registration was
  committed and before any battery ran — prospective with respect to every reading, but not
  committed as its own separate act beforehand. Recorded in the pre-registration itself.
- **Battery 1's feature-vector variation is not independent evidence.** Named above and not
  counted; battery 2 is what carries W1.
- **W6 is belief-only.** The clock is omitted from that measurement because it changes the
  choice rather than the update; the choice is what W1 covers.
- **The tests that encoded the dead dormancy contract were updated, not deleted.** Five
  assertions in `tests/test_membrane_world.py` and the `tests/test_lattice_replay.py` drift guard
  now assert the new contract (the family is declared and covered; exactly one member fires).
  `scripts/membrane/lattice_replay.py`'s "full" variant was updated in the same commit so the
  drift guard stays green **because the two agree**, never because it was loosened.

## Consequence — branch 1, enacted

The declaration lands on master. The membrane stays env-disabled, nothing is installed, and
**no §18 bar is read here** — what changed is that one is now *readable*, which was `GD-11`'s
whole point and r43's finding.

`GD-11`'s four items now stand as:

1. `codebooks.theta` — **done**, by a declared rule with its price published (n = 8, 960 worlds).
2. Full-coverage ticks — **done**, with the writable name excluded rather than padded.
3. The evidence tuple — **open, and it is r45**: the act can never be a tick feature, so the
   engine picks what the fold conditions on. P1 stays blocked behind it (`GD-11`).
4. The dead utility — **done**: the clock row, at a derived price, with `think` measured never to
   win and its latency cost published.

Next: **r45** — item 3, the `act` guard row (r43 measured it as the one row that is *not* free on
the control), and P1's restored accrual with the gap declared as a segmentation boundary
(`M-14`). Then P0-4's smokes on an installed binary, then §17.6's E1 path, then the bars.

`D-2` defaults; no keypress. `M-1` is not engaged — nothing here touches the deployed decide
path or any named wrong-commit class.
