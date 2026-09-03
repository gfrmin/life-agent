# r46 leg D — the categorical twin: READING

Criteria K1–K10, three consequence branches and five blind predictions frozen in
[`r46d-categorical-twin-preregistration.md`](./r46d-categorical-twin-preregistration.md)
before any engine probe and before any `src/` change (`M-3`). Instrument:
`scripts/membrane/categorical_twin.py` (+ `tests/test_categorical_twin.py`). **$0** — engine
CPU on the two already-built binaries (arm A the r41 pin, arm B the deployed HEAD), no API
call, no priced run, no restart, **no `src/` change** (K9), nothing deployed; the categorical
world stays env-disabled throughout. Measurement tree pinned `7db5ff7…`, clean on every leg
(`M-28`).

## The question, and the answer

`GD-13` carried one obligation: **do the two worlds share one declaration of r44's grid rule,
or two.** r45 named the twin's door state from source, unmeasured: *"no `codebooks` key so it
cannot handshake at HEAD at all"*, no clock, *"the fourth [sender] and the only one still
menu-less."*

**Answer: ONE rule, one declaration — and `GD-13`'s "per-`K`" premise was a category error.**
The θ codebook parametrises the **channel rate** and is **K-independent**: on arm B the
categorical world binds r44's `theta_grid(u_bar)` **unchanged** (the same 8 rungs at every
`k`), and its model count grows with `k` **only through `obs_arity`** — the candidate/outcome
dimension, which is a different object entirely. `GD-13`'s "its grid under r44's rule is
per-`K`" conflated the **menu** grid (`act_grid_cat(k)`, genuinely per-`K` and already correct)
with the **θ** codebook (K-independent). So there is nothing to split: both worlds bind the
same rule keyed on the same owner utility. This is the `GD-16` shape again — a carried
premise's conclusion (one rule) survives while its stated mechanism (per-`K`, two applications)
is refuted.

r45's three source claims all measured **true**, and one is **broader** than r45 named:

1. **arm B cannot handshake the twin as-is — confirmed; arm A can — refuted.** r45 read "cannot
   handshake at HEAD" as a property of the twin; it is a property of **arm B**. Arm A handshakes
   the twin with no codebooks at all (K1).
2. **the clock defect is real** — without it the twin fires the menu head over a constant act;
   with it, selection tracks the utility (K5), r43/`OB-24` transferred whole.
3. **the evidence-tick defect is real and has TWO halves** — the twin's tick fails arm B's
   coverage door on **both** the writable `act` (r45's "menu-less") **and** the dormant
   indicator names, which `cat_features` omits on its "dormancy is free" assumption — the exact
   `shadow_features` defect r45 A4/B5 fixed for the binary world, still live in the twin (K4).

**Nothing is built or enabled.** Leg D specifies what a categorical enablement (E1 / §17.6)
must carry — four items, below — and hands them forward. The decision is recorded as `GD-22`.

## Disclosure — two instrument defects, found and fixed before any verdict (`r05`)

Stated first. Both were caught by the first run's own output, fixed, and the instrument
**re-committed before the K7 battery and before this reading** (`M-29`).

1. **A reused session cannot re-handshake.** The first `handshake_matrix` / `ladder` / `grid`
   sent several handshakes down **one** session; a handshake is once-per-session, so the second
   came back `expected tick`, not a re-handshake — which would have read as "arm A refuses
   `k=3`". Each isolated handshake now spawns its own engine (`hello_fresh`). The recon that
   preceded the committed instrument had used a fresh session per probe and was right; the
   committed first draft regressed it, and the output (`expected tick` where a refusal was
   impossible) is what caught it.
2. **The tick omitted the dormant names.** The door/inertness legs first sent `cat_features`,
   which emits only the **active** indicators — so the arm-B decide was refused for want of the
   dormant ones, nulling K5 entirely. That refusal is itself finding K4; the fix
   (`full_cat_features`, every declared name present, dormant at 0.0) is what a tick needs to
   clear arm B, and measuring it required carrying it.

## K1 — the handshake, both arms (KILL: met)

The deployed `handshake_decl_cat(u_bar, k)`, verbatim, each handshake in its own session:

| arm | k=2 | k=3 | k=5 |
|---|---|---|---|
| A (r41 pin) | ok, models **3202** | ok, **4803** | ok, **8005** |
| B (HEAD) | **`bad hello`** | **`bad hello`** | **`bad hello`** |

**Settled both ways.** r45's *"cannot handshake at HEAD"* is **confirmed for arm B** and
**refuted for arm A** — arm A admits the twin with no `codebooks` at all. Arm B's refusal is a
generic `bad hello` (a valid-JSON handshake refusal, not the unparsable tick refusal of K4), so
the *reason* is not in the error text — the ladder supplies it.

## K2 — the {codebooks, clock} ladder — which item bites

| arm | base | +clock | +codebooks | +codebooks+clock |
|---|---|---|---|---|
| A | ok 4803 | ok 4803 | ok 4803 | ok 4803 |
| B | `bad hello` | `bad hello` | **ok 1032** | ok 1032 |

**`codebooks` is the single item that clears arm B's handshake**; the clock does nothing for it
(it is a *selection* seam, priced in K5, not a handshake requirement). On **arm A every variant
is a no-op** — models stay 4803, so arm A neither requires nor consumes the codebooks for the
twin (its count is `obs_arity`-driven). `+clock` leaves the model count unchanged on arm B too
(1032 either way): the clock adds a selection route, not hypotheses.

## K3 — `GD-13`'s decision (KILL: met)

- **(a) arm B requires `codebooks` for a categorical world** — `base` refused ∧ `base+codebooks`
  ok. Confirmed. Branch 2 (obs_arity suffices, premise dissolves) is **refuted for arm B**.
- **(b) the θ grid is K-INDEPENDENT.** With the SAME `theta_grid(u_bar)` (8 rungs, the r46-leg-B
  snapped grid) the arm-B model count is **688 / 1032 / 1720 for k = 2 / 3 / 5** — exactly
  `344·k`, i.e. it scales with `obs_arity = k+1`, **not** with any change to the θ grid. The
  binary world under the same rule reads 960. So the rule is one function keyed on `u_bar`; the
  per-`k` growth is the outcome dimension, which `obs_arity` and `act_grid_cat` already carry.
- **The crossings half has no categorical definition anyway** (`respond_arm_code_conditional` =
  true): the categorical `respond_j` arm is `(= y (- act RESPOND_BASE))` — conditional on
  **which code** `y` equals, not linear in one scalar `p1`. So `argmax_crossings`, which requires
  every row linear in a single `p1`, cannot even be applied to the twin's utility; the only
  defined θ rule is the K-independent fixtures-plus-binary-crossings one. A per-`K` θ grid was
  never on the table.

**`GD-13` resolves: one rule, one declaration.** The categorical world binds r44's `theta_grid`
unchanged. Register `GD-22`.

## K4 — the fourth evidence sender, and its two-count refusal

Three tick variants, codebooks added so arm B handshakes, each in its own session:

| variant | arm A | arm B |
|---|---|---|
| menu-less (`cat_features`, no menu) | accepted | **refused** — missing `["…5 indicators…","act"]` |
| +menu (`cat_features` + menu) | accepted, act=2 | **refused** — missing `["…5 indicators…"]` |
| full coverage (every name + menu) | accepted, act=2 | **accepted**, act=1, `p_codes` len 4 |

**The twin's tick fails arm B on two counts, not one.** r45 named the writable `act` (the
menu-less half); leg D reads the refusal whole — with the menu supplied, arm B **still** refuses
for the **dormant indicator names** `cat_features` omits. Both halves are the same defect class
r45 A4/B5 fixed for the binary world (`shadow_features`' "dormancy is free", false at HEAD),
still live in the twin. **The full repair is a byte-identical no-op on arm A** (`+menu` and
`full coverage` return the same reply there — entropy 5.7668, loss 1.8480, p1 0.27778), the r45
forward-repair standard, so it restores rather than rewrites.

## K5 — the r43 inertness twin

Permuting the menu grid's order, codebooks added, no clock vs clock:

| menu order | no clock → chosen | clock → chosen |
|---|---|---|
| declared `[1,2,3,4,5,6]` | **1** (the head, abstain) | **2** (gather) |
| `[4,5,6,1,2,3]` | **4** (the new head) | **2** (gather) |

**Without a clock the twin fires the MENU HEAD** regardless of utility — r42/r43's signature,
confirmed on the categorical world. **With a clock, selection tracks the utility** (gather,
stable across both permutations) — the substituting chooser (`Host.hs` → `pickWire`, `OB-24`)
is reached, exactly as r43 measured for the binary world. That the utility-argmax is **gather**
is the same gather-bar pathology Arc C has read throughout (`r45` C3, leg A), here in the twin.
The r43 finding transfers whole.

## K6 · K8 · K9 · K10

- **K6** — the reduction is PII-clean: `CatSummary` carries only numbers (K, codes, counts,
  flags); no candidate string reaches the wire or a JSON output. No live corpus reduction was
  used — every probe drives a synthetic `_cat_summary`, named as such, so there is no live
  universe to size.
- **K8** — costs: five legs, all engine-CPU on built binaries, **$0**, seconds each; every leg's
  run stamp records `7db5ff7…` clean against its process start (`M-28`).
- **K9** — **no `src/` change.** The categorical world is untouched; every declaration is an
  instrument-local delta on the deployed `handshake_decl_cat`. Nothing deployed; the world stays
  env-disabled.
- **K10** — `GD-13`'s rider carried (below); nothing filed upstream (`M-23`). Arm B's refusals
  (`bad hello`; the unparsable `tick refused` line) are the same encoding class r45 already
  handed to a successor with its locus; not re-filed.

## K7 — seven mutations, each on its own axis (`M-25`, `M-29`)

All RED then GREEN on the **committed** instrument (`7db5ff7`): base drift (k+1); the codebooks
delta spelling a wrong grid; the clock price flattened to a constant; `theta_rule` dropping a
rung; `theta_rule` gaining a `k` parameter (the K-independence pin); the respond-arm predicate
forced False; the full-coverage tick dropping its dormant names. The battery restores each
mutant with `git checkout` — safe because the instrument was committed first (`M-29`, leg C's
lesson applied). Guards in `tests/test_categorical_twin.py`.

## Consequence — Branch 1, with its premise corrected

The frozen Branch 1 reads: *codebooks required AND one shared rule admissible → `GD-13` resolves
one rule; the shared declaration is specified and handed to §17.6/E1, not built.* **Enacted** —
with the correction that the shared rule is not "two applications of one function" but literally
**one K-independent grid** both worlds bind, because the twin's utility admits no crossings and
its per-`K` structure lives in `obs_arity`, not θ (P3's conclusion held, its mechanism refuted —
recorded, not softened, `M-4`).

**What a categorical enablement (E1 / §17.6) must carry, specified here and NOT built:**

1. **`codebooks.theta` = r44's `theta_grid(u_bar)`, unchanged** (the one rule; K-independent).
2. **a `clock` row** (r44 item 4 / `OB-24`) — else selection is inert (K5).
3. **a menu-bearing evidence/decide tick** (r45 B5) — the writable `act`.
4. **full indicator coverage on every tick** — `cat_features` must emit every declared name
   (dormant 0.0), not only the active ones; arm B refuses the dormant-omitting tick (K4). This
   is the half r45's "menu-less" naming did not cover.

Under every clause: nothing deployed, `M-1` not engaged (no lever ships), `GD-13`'s rider
carried (an enabled categorical world inherits `GD-16`'s re-read before its first backfill, as
the binary world does). The decision is published in `DECISIONS.md` (`GD-22`, `D-3`) — a $0
reading a fork the register and evidence decide, never an objective change. r07's cap holds: the
two instrument defects are disclosure items, not a new arc.

## Verdict

| id | criterion | verdict |
|---|---|---|
| **K1** | handshake both arms, replies whole (KILL) | **PASS** — arm A ok (3202/4803/8005), arm B `bad hello`; r45's claim settled both ways |
| **K2** | which item bites | **PASS** — codebooks clears arm B; clock orthogonal; arm A no-op throughout |
| **K3** | `GD-13`'s decision (KILL) | **PASS** — one rule, K-independent θ; per-`K` premise refuted; `GD-22` |
| **K4** | the fourth evidence sender | **PASS** — refused on arm B on TWO counts; full repair no-op on arm A |
| **K5** | inertness without a clock | **PASS** — menu head fires; clock routes to the substituting chooser (gather) |
| **K6** | PII-clean; universes named | **PASS** — `CatSummary` numbers only; synthetic summaries named, no live universe |
| **K7** | every predicate RED by mutation | **PASS** — seven, RED→GREEN on the committed tree |
| **K8** | costs published; tree pinned | **PASS** — $0, five legs stamped `7db5ff7` clean |
| **K9** | no deployment; the one `src/` change | **PASS** — NONE; world untouched, env-disabled |
| **K10** | `GD-13` rider carried; nothing filed | **PASS** — carried; not re-filed |

**Predictions:** P1 half (arm B refused ✓, arm A refuted); P2 confirmed (codebooks clears arm
B; the count grows with `k` via `obs_arity`); **P3 conclusion confirmed / mechanism refuted**
(one rule, but K-independent, not per-`K`); P4 confirmed and **broadened** (two-count refusal);
P5 confirmed whole (r43 transfers).
