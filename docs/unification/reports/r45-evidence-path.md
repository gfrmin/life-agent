# r45 — the evidence path, and accrual restored

Opened by [`GD-10`](../DECISIONS.md)'s Arc C ladder (**P0** engine pinned → **P1** accrual
restored → §17.6's E1 re-earn → §18's bars) and by [`r43`](./r43-selection-contract.md)'s
narrowing of item 3. `r44` landed the world-declaration repair, which is what made a §18 bar
**readable**; none has been read.

Scope split ruled by the owner (2026-09-01): this checkpoint takes **item 3 and P1**, which are
coupled — P1's replay cannot be faithful until item 3 says what a *recorded act* means on this
wire. The two **declaration levers** (the `act` guard row, and `GD-15`'s grid precision) are
**r46**, gated separately, because bundling two levers on one reading is the r30b mistake.

**Part A is $0** — both engine binaries are already built. **Part B changes the deployed box**
only after Part A and the backfill pass, and only reversibly.

---

## FROZEN BEFORE ANY PROBE RAN

Everything in this section — the options, the criteria, the bars and the consequence branches —
is committed **before the first probe of this checkpoint executes** (`M-3`; the r37/r43
precedent). The reading follows below the rule.

### Part A — what a recorded act can mean on this wire

`r43` established, measured on **both** arms: the writable name may **never** appear in a tick's
features (`Host.hs:399`, `feature/assignment collision`). So the only satisfiable evidence tick
carries a **menu** — and then **the engine picks the act the fold conditions on**. A replay can
pin the act only with a one-point menu grid declared at hello, which means a mixed-act stream
cannot fold in one session.

Three options. r45 measures reachability on the binaries before choosing; a source reading is a
claim about code, never a measurement (`M-7`, `M-20`).

| # | option | what it costs |
|---|---|---|
| **1** | **One session per act** — segment the replay by recorded act, one-point menu each | pins the act exactly; loses cross-act sharing; *n* sessions |
| **2** | **One session, engine-chosen conditioning** | the fold conditions on what the engine picks, **not on what happened** — a corruption, to be named as one and priced, not measured around |
| **3** | **Condition through an `act` guard row** instead of the menu | r43 measured the guard alone does not restore selection; it is r46's lever. Cross-checked here, built there |

### Part B — P1, and the shape the owner ruled

**Backfill offline and verify it, then restore the live shadow.** Never the reverse.

What this session already measured, $0, and which reframes P1 (facts, carried into the
pre-registration so the reading cannot quietly re-derive them):

- **The stack never stopped — the shadow specifically did.** `decisions.jsonl` accrued through
  **2026-08-31**; shadow rows stop at **2026-08-09 15:38** (decide/cat), **16:24** (gate).
- **The final row is a clean boot**: 2026-08-10 16:06:47, `ok: true`, `models: 2393`,
  `respawn_count: 0`, `n_source_records: 2188` — and **zero rows after it**.
- **The binary it booted is absent**: `ebc06c81…`, neither of the two current builds.

That is a **hypothesis with a decisive test**, not a finding: the 08-10 stop and the
missing-binary-today are two facts, and the production-role move (2026-08-30) cannot explain the
first — it is twenty days later.

### Criteria

| id | criterion | kill? |
|---|---|---|
| **C1** | Each of the three options' reachability is **measured on the built binaries** — accepted or refused, with the exact reply quoted — never read from source. | **KILL** |
| **C2** | The chosen option is named **before** the run that justifies it, together with the quantity that would refute the choice. | **KILL** |
| **C3** | Option 2 is admissible **only** if the engine's chosen act matches the recorded act on **≥ 95 %** of a sample of **≥ 100** replayed decide rows. Below that it is disqualified as a corruption and said to be one. | — |
| **C4** | Every load-bearing predicate verified **RED by mutation** before the reading (`G-3`). | **KILL** |
| **C5** | Every probe reads the **whole** reply stream, never the last line (`M-22`). | **KILL** |
| **C6** | The universe of every claim is named **with its size**; an empty universe fails rather than reads (`G-3`). | **KILL** |
| **C7** | The backfill is verified **before any production change**: **0 unexplained skips** (every eligible recorded row is folded or named skipped with a reason) **and** a double run byte-identical. | **KILL** |
| **C8** | `GD-10`'s open question is either **answered from evidence actually consulted** (named), or **re-recorded as closed-by-unavailability** — never left implied. | — |
| **C9** | The live enable is reversible, the launcher restores what it found (`M-19`), and rows must appear in `shadow.jsonl` or the enable is **rolled back** in the same session. | **KILL** |
| **C10** | The gap (2026-08-10 → enable date) is declared a **segmentation boundary** (`M-14`) and the boundary is recorded in the stream, not only in prose. | — |

### Consequence — three branches, frozen

1. **An option preserves the recorded act ∧ the backfill passes C7** → P1 proceeds to the live
   enable under C9/C10. §18's "the shadow keeps accruing" becomes true again and its correction
   block is updated to say so.
2. **No option preserves the recorded act** → item 3 is an **engine** blocker, not a declaration
   one. P1 accrues **live-only**: no historical backfill, the gap is a boundary, and the
   historical stream is published as **unfoldable on this wire**. Cite upstream **#15**, which
   is the engine-side twin and is already OPEN — **file nothing new** (`M-23`).
3. **Backfill passes but the live enable fails C9** → publish the failure, roll back, P1 stays
   offline, and the successor is named on whatever the enable showed.

### Carried obligations — named, not dropped (`M-24`)

- **From `GD-13`:** *"r45's pre-registration must say whether the two worlds share one
  declaration of the grid rule or two."* The split moves the grid lever to **r46**, so this
  obligation is **carried to r46's pre-registration** with that reason. Owner-confirmed
  2026-09-01. This is `M-24`'s first application.
- **To r46:** the `act` guard row (r43: `models` 2393 → 2681, **not** free on the control) and
  `GD-15`'s grid precision, each with its own bar and its own reading.

### Not in scope

- **The declaration is not touched here** — no change to `world.handshake_decl`. That is r46.
- **The proplang repo is read and executed, never written**, and no new upstream issue is filed.
- **§18's bars are not read.** They are readable; reading them comes after E1.

---

## THE READING

*(follows; nothing above this line may be renegotiated — `M-4`)*
