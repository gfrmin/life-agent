# r42 — the engine door, measured: four changes, not one

Opened directly by [`r41`](./r41-p0-engine.md)'s closing line — *"the next rung is the
world-declaration repair, pre-registered on its own"* — and by its rider that the
pre-registration must say **what grid is declared and why that one**.

**$0, no `src/` change, no verdict, nothing installed, nothing enabled.** Same shape as
[`r40`](./r40-arc-c-preconditions.md): a bounded look whose output is a **re-scope**, not a
reading. It exists because r41 named the repair from *source*, and the standing rule is that a
successor starts from evidence.

It found the repair is **four changes, not one** — and that the obvious one-line version of it
ships a green handshake over a dead engine.

## Method

Both engine binaries from r41 already exist, so this cost nothing to run:

| arm | commit | role |
|---|---|---|
| **A** | `1a0cea7` | the control — the tree the shadow was written against |
| **B** | `94fd4eb` | current engine HEAD — the migration target |

Every probe drives the **real** `handshake_decl(u_bar)` and `shadow_features(...)` out of
`life_agent.membrane.world` — never a hand-written stand-in (`M-7`). Only the JSON *around*
them varies. The engine repo was read and executed, never written.

## 1. `hello` requires `world.codebooks.theta` — and the grid is the hypothesis space

r41 established the refusal. The parse shape is now read exactly: `codebooks.theta` is a
**bare non-empty array of finite numbers** (`Host.hs` `pairGridNamed`), `codebooks.rho`
optional.

Adding it is sufficient for the handshake. What it costs is the finding:

| declared `theta` | `models` | `namespace_bits` |
|---|---|---|
| `[0.5]` | **1** | 4.2479 |
| `[0.1, 0.9]` | 36 | 4.2479 |
| `[0.1, 0.5, 0.9]` | 105 | 4.2479 |
| `[0.1, 0.3, 0.5, 0.7, 0.9]` | 345 | 4.2479 |
| nine even points `0.1 … 0.9` | 1233 | 4.2479 |
| **arm A, baked in** | **2393** | 4.2479 |

Reproduced identically on a second pass. Two things follow, both measured rather than argued:

- **The grid is priced in models, not in namespace bits** — `namespace_bits` is invariant
  across every grid. Declaring more rungs does not cost namespace; it multiplies the world set.
- **No grid tried here restores arm A.** Nine even points reach 1233 against arm A's baked
  2393. So "declare the obvious grid" is not a restoration to the control's behaviour — it is a
  strictly smaller hypothesis space, chosen by us. That is the substance behind r41's claim
  that this is world data, now with numbers on it.

And the degenerate case is the one a hurried fix would reach for: `theta: [0.5]` handshakes
green with **`models: 1`** and `entropy_bits: 0.0` — a single-world engine that cannot learn
anything, ever.

## 2. Decide ticks require FULL namespace coverage — the dormancy contract is dead

`world.shadow_features` deliberately omits inapplicable one-hot names, on a contract its own
docstring states: *"Absent names read 0.0 on the wire (dormancy is free — membrane-wire.md
§4)."* At HEAD that is retired (`Host.hs`: *"the 0.0-dormancy default is dead; an
under-specified tick is an error reply"*). Measured, on a typical summary — 5 emitted names
against a 19-name namespace:

```
{"error": "tick refused: missing declared ["n-candidates=0","n-candidates=1",
 "leader-credence=lt50", … 13 names …]"}
```

**This repair is provably free on the control.** Arm A, given the same tick with every absent
name explicitly at 0.0, returns a reply **identical** to its sparse one — `act 2`, `p1 0.5`,
`entropy_bits 4.214166839717911`. Arm A also **ignores** a `codebooks` block entirely (models
stays 2393). So changes 1 and 2 are both backwards-compatible: **one declaration serves both
arms**, and the swap needs no version-conditional handshake.

## 3. Evidence ticks are REFUSED at HEAD — the shadow cannot learn at all

This is the change that matters most, and it was nearly missed.

An evidence tick (`{"features": …, "evidence": 1}`) carries no menu, so the writable name is
unsupplied — and HEAD's door requires the namespace covered *including* the writable name,
which the tick's assignment is expected to supply:

```
armB:  {"error": "tick refused: missing declared ["act"]"}     × every evidence tick
armA:  {"observed": 1, "loss_bits": 0.9999999999999758}        (accepted, conditioning)
```

So `MembraneSession.observe_verdict` / `observe_outcome` — the entire evidence path, and
therefore `boot(verdict_replay=…)` — **fail closed at HEAD**. Not degraded: refused.

The fix is not shape-level plumbing. An evidence tick that must name an act is a **full
experience tuple** `(features, act, outcome)`, where the shadow currently sends
`(features, outcome)`. Deciding what act a recorded verdict is claimed to have been taken
under is a modelling choice about what the shadow is learning from, and it is the successor's
to pre-register.

## 4. HEAD parses the utility sentence, then decides as if it were absent

With theta declared and ticks fully covered, on one feature vector, varying only `u_bar` so
the host-side argmax moves across all four affordances:

| `u_bar` | host `argmax_action` | arm A | arm B |
|---|---|---|---|
| deployed (`u_wrong = −9`) | gather | **gather** | abstain |
| respond-favouring (`u_wrong = 0`) | respond | **respond** | abstain |
| ask-favouring (gather dear) | ask | **ask** | abstain |
| info-dear (both dear) | abstain | **abstain** | abstain |

`world.argmax_action` exists to *predict the engine's chooser* from the declared `said@1`
sentence. **Arm A matches it on all four.** Arm B returns `abstain` on all four — which is the
option space's head, the structural `wait`.

The sentence is **not** being silently dropped at the door. HEAD validates it: an unknown
`form` answers `bad hello`, and a malformed `said` answers `bad hello`. It is parsed, accepted
— and then, measured byte-for-byte:

```
utility declared as usual : {"act": {"act": 1}, "p1": 0.5, "entropy_bits": 2.837681148035951,
                             "p0": 0.5, "argmax_code": 0, "p_argmax": 0.5, "p_codes": [0.5,0.5]}
utility block REMOVED     : {"act": {"act": 1}, "p1": 0.5, "entropy_bits": 2.837681148035951,
                             "p0": 0.5, "argmax_code": 0, "p_argmax": 0.5, "p_codes": [0.5,0.5]}
```

**Identical.** Declaring the utility changes nothing about the decision; the reply is the one
`Host.hs` documents for a world that declared no utility at all — *"the option space's head
fires as a plain EXTERNAL act"*.

So on this world, at HEAD, the engine **parses and validates a utility declaration and then
selects as though it had none.** Both grid size and belief entropy are irrelevant to it
(`abstain` at `|θ|` = 1, 2, 3, 5 and 9, at `entropy_bits` from 0.0 to 3.78).

**Not diagnosed here, deliberately** — that is the successor's, with its own bounded look. Two
mechanisms are visible in the source without running anything: the selection path is
`maybe o0 fst picked`, so a `chooseEU` returning `Nothing` fires the head indistinguishably
from an absent utility; and the parser accepts a second form our declaration does not use
(`utility.cgrid`, routing to `parseSaidIn` over an explicit constant grid). Either would
explain it. What is established here is that **it is real, reproducible, and silent.**

## What this changes

**The one-line fix is a trap, and it is now measured rather than suspected.** Declaring
`codebooks.theta` alone yields: handshake `ok: true` · every evidence tick silently refused ·
belief pinned at the prior · a constant `abstain` policy. Green lights over a dead engine. Had
the repair been done as a tail-end convenience at the close of P0 — which is exactly what was
proposed and declined — that is what would have shipped.

The successor's pre-registration therefore covers **four** items, and the bars in
membrane-shadow §18 have to measure the last two, not just the first:

1. `codebooks.theta` — **what grid, and why that one.** Free on arm A.
2. Full-coverage ticks — **provably a no-op on arm A**, so it can be verified before the swap.
3. The evidence tuple — a modelling choice, not plumbing; without it the shadow learns nothing.
4. The dead utility — **must** be understood before any bar reads. A §18 bar taken in this
   state compares arm A's utility-driven policy against a constant `abstain`, and books the
   difference to the migration. `M-18` one level up: pin what the comparison arm is actually
   deciding with, not just which tree it is on.

The engine repo's own `#19` record already carries a warning for item 1 that this arc must not
re-learn the expensive way: a rung placed *near* but not *at* the operating rate lets the
posterior settle on the KL-nearest rung and **false-clear** a consumer threshold — worse than
never clearing, and its error grows under data. A rung at the operating rate is the recorded
cure. That is a claim about the engine repo's own evidence, cited here and **not** re-measured
in this reading; the successor should re-execute it on our world before relying on it.

**No upstream issue is filed.** It is not established that this is an engine defect rather
than a declaration of ours that HEAD no longer accepts in the way we intend — the `cgrid` form
alone is enough to make that live. Filing before the diagnosis would spend someone else's
attention on our unfinished work. It stays an in-tree finding, and filing is an option the
successor holds once item 4 is understood, not a step skipped here.

## Deviations, disclosed

- **The probe's first version had the tick nesting wrong** (`{"tick": 1, "features": …}`
  instead of `{"tick": {…}}`). The host read the payload as a bare number, so features and
  menu were invisible and every tick answered a bland `{"ok": true}`. Read at face value that
  is *"sparse ticks are accepted at HEAD"* — the exact opposite of finding 2. Caught by asking
  why a decide reply carried no `act`.
- **A 120-tick learning sweep was run without checking mid-stream replies**, and produced an
  apparent mystery — *"arm B learns nothing; `p1` is pinned at 0.5 under 120 positive
  evidences"* — that was in fact 120 refused ticks. Finding 3 exists because that sweep was
  re-run printing every reply instead of only the last. The standing lesson (read the whole
  wire, not the end of it) claimed a fresh instance today.
- Findings 1–2 were reproduced on a second pass; findings 3–4 are single-pass but exact and
  deterministic (identical bytes across the repeats that did run).

## Consequence

`D-2` defaults; no keypress. r42 produces a re-scope and nothing else. **P1 (restoring shadow
accrual) is blocked behind item 3, not merely behind item 1** — accrual against HEAD would
accrue nothing.
