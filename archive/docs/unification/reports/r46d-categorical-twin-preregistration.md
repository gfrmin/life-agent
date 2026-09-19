# r46 leg D — the categorical twin: PRE-REGISTRATION

Frozen before any engine probe of this leg and before any `src/` change (`M-3`). This
document fixes the criteria, the blind predictions and the consequence branches; the reading
lands in `r46d-categorical-twin.md`. **$0** — engine CPU on the two already-built binaries, no
API call, no priced run, no restart, nothing deployed. The categorical world stays
env-disabled (`LIFE_AGENT_MEMBRANE_CAT` unset) throughout — this is a **diagnosis**, the twin
of legs A–C for the E1 stage-1 world, not a build and not an enable.

## The question

`GD-13` carried one obligation forward in as many words: *"r45's pre-registration must say
whether the two worlds share one declaration of the [grid] rule or two."* r45 deferred it
whole to r46 and named the twin's door state from **source, not measurement** (`r45` B5): the
categorical world *"has no `codebooks` key (so it cannot handshake at HEAD at all) and no clock
row"*, and its evidence tick is *"the fourth [sender] and the only one still menu-less."* Leg D
turns those three source claims into measurements on both arms, and returns `GD-13`'s decision
with the evidence behind it.

**The three-defect frame** (`GD-13`, `r45` B5). The binary world (`membrane/world.py`) reached
the live wire across r42→r46 by acquiring, in order: a declared `codebooks.theta` grid rule
(r44 item 1, snapped in r46 leg B), a `clock` row that routes selection to the substituting
chooser (r44 item 4 / `GD-12` / r43), and a `menu`-bearing evidence tick (`r45` B5). The
categorical world (`membrane/categorical.py`, `handshake_decl_cat`) declares **none** of the
three: it carries `obs_arity = K+1` in place of `codebooks`, no `clock`, and `cat_features`
never emits `act`. Leg D measures which of the three actually bite on the categorical world,
on both arms, and — the load-bearing one — settles whether r44's grid rule transfers.

**Why the grid question is not a re-run of leg B.** The binary `theta_grid(u_bar)` is
**K-independent**: it keys on `OPERATING_RATE`, the recorded shadow quantiles, the endpoints,
and `argmax_crossings(u_bar)`. But the categorical utility has **K+3 action rows**
(`abstain`, `gather`, `ask`, `respond_1…respond_K`), so *its* `argmax_crossings` are **per-K**
— which means r44's rule, applied to the categorical world's own utility, yields a **per-K**
grid. That is exactly the object `GD-13` calls "its grid under r44's rule is per-`K`". The
decision is whether **one declaration of the rule** (one crossing-plus-fixtures function keyed
on each world's own utility) serves both, or whether the categorical world needs its own.

## The arms and the surfaces

- **Arm A** — the r41 pin (worktree `pin-1a0cea7`), permissive: r45 A1 measured it does **not**
  enforce full-namespace coverage on a decide. Passed as `--arm-a` (machine-local path kept out
  of tree; the run stamp records what was passed — the `r46c` / PII precedent).
- **Arm B** — the deployed HEAD (`~/.local/bin/proplang-host`, worktree `armB-94fd4eb`), which
  enforces the door rule leg C read: every declared name covered exactly on a decide, and (r45
  B5) on an evidence tick.
- Every probe drives the **deployed** `handshake_decl_cat` / `cat_features` / `decide_categorical`
  from `membrane/categorical.py`, or an **instrument-local declaration delta** on them (add
  `codebooks`, add `clock`, add a menu to the evidence tick) — never a re-implementation of the
  constant under test (`M-7`). No `src/` change is expected (see K9).

## Criteria

Frozen. **KILL** criteria (a FAIL is disqualifying for the leg's central claim) are marked.

- **K1 · the categorical handshake, both arms, as-is — KILL.** Drive `handshake_decl_cat(u_bar, k)`
  for `k ∈ {2, 3, 5}` on arm A and arm B; record `ok` / `models` / the **verbatim** reply, and a
  refusal's error string whole (`M-22`). PASS = r45's *"cannot handshake at HEAD"* claim is
  settled either way, with the reply on the record. KILL if the probe cannot be driven at all
  (no reachable engine, or an unparsable reply the client cannot surface).
- **K2 · the missing-declaration ladder — which defect bites, measured not asserted.** For each
  of {`codebooks.theta`, `clock`, menu-on-evidence}, the minimal instrument-local declaration
  delta, and whether it clears the corresponding refusal or inertness, on **both** arms. A
  defect that does **not** bite (a delta that changes nothing) is reported as a no-op, not
  quietly dropped — the r45-A2 "measured free on the control before taken" standard.
- **K3 · `GD-13`'s decision: one grid rule or two — KILL.** Two parts, both required:
  (a) does arm B **require** `codebooks.theta` for a categorical (`obs_arity`) world, or does
  `obs_arity` alone suffice? (b) if required, does **one** declaration of r44's rule — keyed on
  each world's own `argmax_crossings` — serve both worlds, with the categorical application
  yielding the expected per-K grid (`models = n(17n−16)`, r42's law, at the categorical n)?
  PASS = a **decision** on `GD-13` with the measured grid(s) behind it. KILL if leg D ends
  without resolving `GD-13`.
- **K4 · the fourth menu-less evidence sender (`r45` B5).** Confirm `decide_categorical`'s
  evidence tick (`{"tick": {"features": …, "evidence": code}}`, no menu) is **refused on arm B**
  for the same door reason leg C read, and that a `menu: [ACT_NAME]` repair clears it **and is a
  byte-identical no-op on arm A** (the r45 forward-repair standard). The categorical tick is
  **code-valued** (`evidence: int`), not the binary `evidence: y`, so the refusal wording and
  the repair are checked on the categorical tick specifically, not inherited from leg C.
- **K5 · utility inertness without a clock (the r43 twin).** Without a `clock`, does the
  categorical world fire the **menu head** over a constant act (r42/r43's binary signature)?
  Measured by permuting `act_grid_cat`'s order on arm B and checking whether the chosen value
  tracks the head or the utility-argmax; and whether adding a `clock` row routes to the
  substituting chooser (r43 / `OB-24`), as it did for the binary world.
- **K6 · the reduction is PII-clean and every universe is named at read.** `CatSummary` carries
  only numbers (K, codes, counts, flags) — verified, no candidate string reaches the wire or a
  JSON output. Any live reduction used is named with its size at the stamped read.
- **K7 · every load-bearing predicate RED by mutation (`M-25`).** Each instrument predicate
  mutated on **its own** axis (a handshake-refusal read, the codebooks-required read, the per-K
  `models` law, the door refusal, the clock routing) — RED then GREEN, on the **committed**
  instrument (`M-29`: the instrument is committed before the battery runs).
- **K8 · costs published; the tree pinned for the whole run (`M-28`).** Every leg's run stamp
  records the head, dirty state and instrument mtimes against process start; wall/CPU published.
- **K9 · no deployment; the one permitted `src/` change named.** Expected **NONE** — pure
  measurement via instrument-local deltas. Should the reading adopt a shared grid-rule
  declaration (a `theta_grid`-shaped function the categorical world binds), that refactor lands
  in a **separate** follow-up under its own pre-registration, never in this reading (the r30b
  "two levers on one reading" precedent). The categorical world stays env-disabled.
- **K10 · `GD-13`'s rider carried; nothing filed upstream (`M-23`).** Engine-side asks (a
  refusal's encoding, `OB-24`) are issues on the public repo, never a diagnosis smuggled into
  this report; #15 stays the engine-side twin.

## Blind predictions (source reasoning only — no probe has run)

1. **P1** — arm B **refuses** `handshake_decl_cat` as-is, the error naming a missing
   `codebooks`/`theta` key (r45's claim). Arm A: **uncertain** — the codebook requirement is a
   wire-level (W3) `Host.hs` thing, not the tick-coverage asymmetry arm A relaxes, so I predict
   arm A **also** refuses without `codebooks`. Recorded as the weaker leg of P1.
2. **P2** — adding `codebooks.theta` (per-K, via r44's rule keyed on the categorical utility)
   clears the handshake on both arms; `models` follows r42's `n(17n−16)` at the categorical n.
3. **P3** — the categorical θ grid under r44's rule is **per-K and distinct** from the binary
   grid, so `GD-13` resolves to **one rule, two applications** (one crossing-plus-fixtures
   function keyed on each world's own utility), not two rules. Blind — the measurement decides.
4. **P4** — the categorical evidence tick is **refused on arm B** without a menu (leg C's door),
   and `menu: [ACT_NAME]` is a **byte-identical no-op on arm A**.
5. **P5** — without a `clock` the categorical utility is **inert** (the menu head fires over a
   constant act); declaring a `clock` routes to the substituting chooser (r43 / `OB-24` transfers
   whole to the categorical world).

## Consequence branches (frozen before the reading)

- **Branch 1 — `codebooks` required AND one shared rule admissible** (P1∧P2∧P3 hold): `GD-13`
  resolves **one rule, two applications**; the shared declaration is **specified** here and
  **handed to §17.6 / E1 to build**, not built in this reading. Leg D closes Arc C's readable
  diagnosis of the twin. Register a new `GD` resolving `GD-13`.
- **Branch 2 — `codebooks` NOT required for a categorical world** (`obs_arity` alone
  handshakes): `GD-13`'s premise **dissolves** — the categorical world's hypothesis space is
  the code simplex the engine holds natively, not a θ grid. Report that r44's grid rule **does
  not transfer**, name the actual hypothesis-space object for E1, and resolve `GD-13` as
  moot-by-measurement.
- **Branch 3 — `codebooks` required but NO single declaration serves both** (P3 refuted; the
  rules genuinely diverge): `GD-13` resolves **two rules**; name precisely **what** makes them
  irreconcilable (a fixture the categorical world cannot honour, a per-K dependence the binary
  rule cannot express), and hand both declarations to E1.

Under every branch: nothing is deployed, `M-1` is not engaged (no lever ships), and the
decision is published in `DECISIONS.md` — a $0 reading a fork the register and evidence decide
(`D-3`), never an objective change. The cap from r07 holds: anomalies en route are disclosure
items, not a new diagnostic arc.
