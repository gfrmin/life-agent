# r46 leg C — act-conditioning: PRE-REGISTRATION

The question `r45` handed forward, verbatim: **"can one world both condition on the act and
choose it, and if not, what two-world arrangement is admissible?"** — with leg A's sharpened
target bound to it: **the p1 ceiling, not the affordance constant, is what blocks a
commit-pricing §18 bar** (ledger max 0.8706 against the mapped surface's commit bar
0.897015; gap 0.0264). **Committed before any `src/` change and before any engine probe of
this leg runs** (`M-3`).

Instrument: `scripts/membrane/act_conditioning.py` (+ `tests/test_act_conditioning.py`).
Report: `r46c-act-conditioning.md`. **$0** — engine CPU on already-built binaries, no API
call, no priced run, no restart.

## Disclosure — what was consulted before freezing (no engine probe ran)

The `M-20` sweep behind this document consulted registers, code and streams only — zero
engine invocations. Verified live 2026-09-03: arm A `1d008643…` and arm B `71998f65…` at
their r41 pins, arm B also installed at `~/.local/bin/proplang-host`; the bridge unrestarted
since 2026-09-02 17:17:54 (leg B's lattice **in the tree of record but not on the wire** —
this leg is offline and runs on the tree, so its folds use the snapped grid; named so the
control cannot be read as an exact r45 reproduction); the gather constant now 6 789/6 789
action-bearing rows; the p1 ledger max still 0.8706 (an old-era row); upstream **#15** is
the engine-side register entry (a guard on a *writable* name never receives evidence and
never differentiates candidates at decide time), and `OB-24` is about utility substitution,
a different mechanism. `GD-16`'s reversal rider is quoted in K10. `boot_snapshot`'s
`verdict_replay` rows are `(DecideSummary, y)` — they do **not** carry the recorded act,
which is why the one permitted `src/` change below exists.

## The arrangements

The collision r43 found is **name-level** (menu-vs-feature for the *same* name, r45 A4).
The unmeasured arrangement is therefore a mirrored non-writable feature. Three cells:

- **A0 — control (shipped declaration).** Reproduces r45 A2's inertness null on the tree of
  record: four one-point-menu sessions, one per pinned act, over one fixed evidence stream —
  the distinct-`p1` count must be 1. The `M-25` control varies the **act axis on a
  discriminating grid** (not the evidence axis — r45 A3's own defect class).
- **A1 — mirrored feature, one world.** The deployed `handshake_decl` output modified
  **additively** (a drift test pins the base equal to the deployed declaration — the
  `lattice_replay` precedent, `M-7`): namespace gains `act-taken` (non-writable), guards gain
  `{"name": "act-taken", "grid": [1.5, 2.5, 3.5]}` (the r45-corrected discriminating grid
  over act values 1–4), menu unchanged. Evidence ticks carry `act-taken` = the recorded
  act's value via `_VALUE_FOR[REAL_TO_MEMBRANE[chosen_action]]` — the ONE declared projection, never a
  re-spelling. Open door question, measured not derived: whether HEAD refuses a **decide**
  whose features omit the new declared name (r45's door rule was stated for *evidence*
  ticks; nothing supplies `act-taken` at decide). Both outcomes are handled below (K5).
  - **A1b — the conditional readout**, if the wire admits it: a decide (or readout probe)
    with `act-taken` pinned to each of the four candidate values in turn reads
    `p1 | act-taken = v` per candidate — #15's missing engine-side capability recovered
    seam-side, selection staying wherever the engine puts it. A decide provably does not
    advance the evidence index (`MembraneSession.decide`'s own contract — "a decision tick never advances" `_t` — r45-confirmed live at t=250); that this holds
    for a decide *carrying extra features* is a load-bearing predicate and gets its own
    contamination check (four value-pinned decides then a fifth repeating the first —
    byte-identical or the probe is void).
- **A2 — two worlds.** The shipped world decides; a second session runs r45 A4's observing
  world (`act` as guard on the discriminating grid, out of the menu). Its conditioning is
  established (r45 A4: arm B gap +3.37 bits) and is not re-litigated; what A2 must answer is
  whether its belief is **readable** (a p1-equivalent readout exists on some reply — if only
  tick-reply loss readouts exist, the implied predictive is derived and said to be derived;
  if nothing is readable, A2 reads UNREADABLE and that is a finding) and what it **costs**
  (a second full fold).

## Criteria — frozen

| id | criterion | kill? |
|---|---|---|
| **K1** | Every admissibility cell (handshake / evidence tick / decide, per arrangement) measured on **both** arms' built binaries, every reply stream read whole (`M-22`), refusals quoted verbatim. | **KILL** |
| **K2** | A0 reproduces the inertness null on the tree of record (distinct-p1 count = 1 per arm), and the `M-25` mutation control varies the **act** axis on a discriminating grid and comes back RED (distinct count > 1 in the A4-shape world). | **KILL** |
| **K3** | Conditioning existence per arrangement: two act-distinct evidence streams give distinct `p1`; an act-identical control pair gives byte-identical `p1`. | — |
| **K4** | The selection contract: wherever a decide is served, the chosen act equals `argmax_action(u_bar, that reply's p1)` (r44 W1's bound) on every probed row. A deviation is published as a finding — it would mean per-candidate conditioning exists engine-side, against #15 — never smoothed. | — |
| **K5** | The ceiling leg, **arm B only** (the deployed engine — admissibility generality comes from K1): a **prequential** fold of the joined verdict universe (each row's decide probed **before** that row's evidence folds — the live stream's order), recording per-row `p1`, and, where A1b is admissible, `p1 | act-taken = v` for all four v. Published: the pooled ceiling, the conditional ceiling `max_v`, and each one's gap to the **mapped surface's commit bar**, located by sweeping the deployed `coarse.map_action` (leg A's own method — swept, never spelled as a formula; `world.respond_threshold` is a DIFFERENT number, the raw menu's ~0.997 bar, published beside it but not the target). | — |
| **K6** | Every universe named with its size at its read time; an empty universe fails the leg rather than reads. | **KILL** |
| **K7** | Every load-bearing instrument predicate RED by mutation before the reading (`G-3`), each mutation varying its own claim's dimension (`M-25`). The A1b contamination check is one of them. | **KILL** |
| **K8** | Costs published: `models` per arrangement, engine CPU per fold and per probe within-run, wall beside it; every run records the git head + dirty state and the instrument-file mtimes against the process start time (`M-28`) — a run that cannot prove which tree it loaded is void. | — |
| **K9** | Observation-only: no change to `world.handshake_decl`, `shadow_features`, the wire, or the deployed unit; **no restart taken**. The ONE permitted `src/` change: an additive, index-aligned field on `BootSnapshot` carrying each replay row's recorded `chosen_action`, under TDD with an alignment mutation — never a re-implemented join (the r45-C3/`M-7` class). | **KILL** |
| **K10** | `GD-16`'s rider named in the report: *"if act-conditioning lands, the act stops being inert, C3's premise becomes live, and GD-16 must be re-read before any further backfill"* — this leg lands nothing, and any successor that deploys act-conditioning carries that re-read as a precondition. `M-23`: nothing new is filed upstream; engine-side findings are handed forward with their locus. | — |

## Predictions — blind, falsifiable, with the refutation channel named

- **P1.** A1 is wire-admissible on both arms at handshake and on evidence ticks — the
  collision is name-level. Refuted by: a refusal reply, quoted.
- **P2.** A1's fold conditions on `act-taken` (an ordinary non-writable guard receives
  evidence — #15's own statement read forward). Refuted by: K3's distinct streams giving
  byte-identical `p1`.
- **P3.** Engine selection stays act-unconditional in every arrangement — K4 holds
  everywhere. Refuted by: one probed row where the chosen act deviates from
  `argmax_action` at the reply's own `p1`.
- **P4 — deliberately NOT a prediction.** Whether HEAD's door refuses a decide missing
  `act-taken` is a measured fork with both branches handled in K5 (refused → the plain-decide
  trace is served through A1b's value-pinned probes, disclosed; admitted → both readouts
  exist). Freezing a bet here would add nothing the branches don't already carry.
- **P5 — direction only.** The conditional ceiling `max_v p1|v` will sit **at or above** the
  pooled ceiling (conditioning on a y-correlated value concentrates; equality if the act
  carries no information about y in this stream). **Whether it crosses 0.897015 is the open
  question this leg exists to read — no bet is frozen on the crossing**; the consequence
  branches split on it instead.

## Consequence — three branches, frozen

1. **Some admissible arrangement conditions AND its recorded-stream ceiling reaches the
   mapped commit bar on ≥ 1 row** → act-conditioning is a **named candidate lever** for the
   §18 commit-pricing bar — named, not built (`M-6`): the successor gets its own
   pre-registration and its own bar, and **`GD-16`'s re-read is a precondition of any
   deployment**. Nothing in this leg touches the wire.
2. **Conditioning exists but the ceiling stays under the bar everywhere** → published as:
   act-conditioning does not fill the commit column on the recorded stream; the block
   remains on the utility side (the `u_abstain` residue — owner-only, already priced) or on
   model capacity; leg D proceeds; **no successor lever is opened from this leg**.
3. **No arrangement is admissible + conditioning + readable** → #15 binds downstream too;
   the finding is handed to whichever checkpoint reads a §18 bar as a constraint, with the
   measured refusals quoted; nothing is built.

A failed KILL criterion voids the reading: publish why, amend blind (`M-4`), re-run.

## Scope — out, with reasons

- **Leg D** (the categorical twin, `GD-13`) — its own pre-registration, and it carries
  `GD-13`'s still-unanswered question: whether the two worlds share one declaration of the
  grid rule or two (checked: neither r46 pre-registration answered it; it is leg D's).
- **Deploying anything** — the shadow's declaration does not change; the next natural
  restart carries leg B's lattice only.
- **The `u_abstain` residue** — owner-only, priced in its conferral; this leg reads the
  bar's distance, never moves the bar (`A-3`: bar-move levers are closed).
- **Engine-side work** — the proplang repo is read and executed, never written (`GD-14`
  filed the demand already; `M-23` forbids re-filing the diagnosis).
