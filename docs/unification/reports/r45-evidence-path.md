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

## Part A — the reading

**$0.** Both binaries were already built and were verified against the pins r41 recorded
before anything ran: arm A `1d008643…`, arm B `71998f65…`, each at
`dist-newstyle/…/proplang-host` in its own proplang worktree. `~/.local/bin/proplang-host`
— `lattice_replay.py`'s `DEFAULT_ENGINE` — **does not exist on this box**, which is why
every script defaulting to it is currently unrunnable and why Part B's install is real work.

### A1 — item 3, re-measured on the SHIPPED declaration

r42 named item 3 from a hand-built stand-in. Re-measured against `world.handshake_decl`
and `world.shadow_features` as they actually ship (`M-7`), on both arms, three world
variants each:

| world variant | arm | evidence tick, no menu | evidence tick + menu | decide |
|---|---|---|---|---|
| shipped | A | accepted | accepted | accepted |
| shipped | **B** | **refused** | **accepted** | accepted |
| act pinned to a one-point menu grid | B | **refused** | **accepted** | accepted |
| `act` guard row added | B | **refused** | **accepted** | accepted |

HEAD's refusal, quoted exactly (C1):

```
{"error": "tick refused: missing declared ["act"]"}
```

So item 3 holds on the shipped declaration, and the `act` guard row does **not** lift it.
**But all three pre-registered options are REACHABLE**: every one accepts an evidence tick
that carries a menu, and every one folds it (`observed` and `loss_bits` both present).

### A2 — the finding that decides Part A: the recorded act is INERT in the fold

Reachability is not conditioning. Replaying one fixed evidence stream (n = 8) under each of
the four affordances, one session per act:

| arm | act guard row | distinct `p1` across the four pinned acts |
|---|---|---|
| A | no | **1** — `0.6935446081286201` for all four |
| A | yes | **1** — `0.6933384515963547` for all four |
| B | no | **1** — `0.8497121294632395` for all four |
| B | yes | **1** — `0.8497121294632395` for all four |

**Mutation control (C4):** the same harness, varying the *evidence* instead of the act,
returns **4 distinct `p1`** on both arms. The detector fires; the null is real.

The consequence is the one that matters: **arm A does not condition on the act either.**
The historical shadow — every row in `shadow.jsonl` — was produced by a fold that ignored
the act. So no option can "corrupt" act-conditioning, because there has never been any.

### A3 — a probe defect of my own, found and corrected

The first act-conditioning probe declared the `act` guard with grid `[0.5]`, copied from the
indicator rows. Indicators are 0/1, so `0.5` splits them; **acts take the values 1–4, so a
0.5 threshold reads 1 for every act and cannot separate them by construction.** That probe
reported "the act cannot condition the fold" — a result manufactured by its own grid.
Corrected to thresholds *between* the act values (`[1.5, 2.5, 3.5]`), the answer reverses.
Published because the audit's own measure was wrong, which is the class `M-7` and the
carrier-audit lesson name; caught before it reached a verdict, unlike r10's.

A second defect in the same probe: both acts were probed inside **one** session, but a probe
tick *is* an evidence tick, so the first probe folded and biased the second — a systematic
negative gap. Fixed by one session per probe.

### A4 — what the act CAN do, and the engine contract behind it

With `act` declared as a guard on a discriminating grid **and removed from the menu**, an
act-carrying evidence tick is accepted on both arms and the fold **does** condition on it:

| arm | teach | loss(abstain, y=1) | loss(respond, y=1) | gap |
|---|---|---|---|---|
| A | abstain→1, respond→0 | 0.901098 | 1.139787 | **+0.238689** |
| B | abstain→1, respond→0 | 0.151762 | 3.519046 | **+3.367284** |
| B | 9 pos / 3 neg (asymmetric) | 0.130745 | 1.296901 | +1.166155 |

Untaught middle acts interpolate monotonically (arm B: gather 0.4255, ask 0.7964, between
abstain 0.1307 and respond 1.2969) — the signature of a guard-threshold model, not an
artefact. The identical numbers under an act-separable and an indicator-separable teach were
checked rather than rationalised: they survive an asymmetric teach, so the two streams are
isomorphic by construction and the coincidence is expected.

**The engine contract this exposes, stated once:** `act` is either **written** (a menu name)
or **observed** (a tick feature), never both — every attempt at both returns
`feature/assignment collision`, on both arms. r43's *"the writable name may never be a tick
feature"* is therefore true only **while `act` is in the menu**; the collision is
menu-vs-feature, not namespace-vs-feature. And the act-conditioned world **cannot decide**,
having no writable name left.

That is a genuinely new capability and it is **named, not built** (`M-6`): it belongs to the
`act`-guard lever, which is **r46**, and it needs its own bar.

### A5 — an engine defect, and our own

HEAD's refusal line is **not valid JSON**: `Eval.hs:40-43` builds the message with Haskell
`show` on the offending name list, so `["act"]` reaches the wire with unescaped inner quotes
— against the engine's own `membrane-wire.md` rule that strings escape `"`. Their author
pack documents the message *content* (`exact-author-pack.md:206-208`); nothing registers how
it is encoded, so this is not a known entry (`M-23` checked).

Ours is the worse half: `client.request` called `json.loads` unguarded, so a **refusal** —
the one reply a backfill most needs to read — escaped as `json.JSONDecodeError` rather than
the `MembraneError` the class's own contract promises. Fixed here under TDD (RED verified
first); the supervisor's `except Exception` fail-open meant production was never exposed,
but the offline backfill path is not under the supervisor and would have died.

## C8 — `GD-10`'s open question, ANSWERED from evidence consulted

`GD-10` left *why the stream stops on 2026-08-10* open rather than inferring it, "because
inferring a cause from an adjacent fact is precisely what r36 got wrong." The evidence was
reachable after all, and it **falsifies a fact this pre-registration itself froze**.

### The correction first

The frozen section states: *"The stack never stopped — the shadow specifically did."*
**That is wrong.** Counted by `tx_time` over all 3 867 rows of `decisions.jsonl`:

```
2026-08-06  211
2026-08-07  232
2026-08-09  100      <- last day before the hole
                     <- 08-10 .. 08-16: NOTHING
2026-08-17  440      <- the stack resumes
2026-08-18    8   2026-08-21  309   2026-08-24  103   2026-08-25  412
2026-08-26  125   2026-08-29  108   2026-08-30   56   2026-08-31  312
```

The stack and the shadow **stopped together on 2026-08-09**. What is true — and is the real
question — is that the stack came back on 08-17 and the shadow did not. The claim entered
the freeze from a file-mtime reading (`decisions.jsonl` last written 08-31), which says when
a file was last appended to, never that it was appended to continuously. Disclosed here in
full rather than quietly restated (`M-4`): a fact carried into a pre-registration is still a
measurement, and this one was wrong.

### The answer

| evidence | reading |
|---|---|
| the former production box is reachable on the tailnet (active, direct) | the evidence was **not** lost with the production move |
| `sha256` of that box's `~/.local/bin/proplang-host` = `ebc06c81b954afb0f7b951548ed5d06d5b69cfc4e3f0f04b6597d55bcdd644d3` | **byte-identical** to the binary named in the final boot row — the engine was never missing |
| the final row (08-10 16:06:47) is `engine.ok: true`, `models: 2393`, `respawn_count: 0`, `n_source_records: 2188` | it booted cleanly and then saw **no traffic** — because during 08-10…08-16 there was none |
| `LIFE_AGENT_MEMBRANE_COMMAND` appears in no `.env`, no `systemd --user` unit, and no dotfile on **either** box | its enablement was **ad hoc, in an interactive shell** |
| absent from `.env.example` and from `packaging/` | it was never part of the deployment recipe, so nothing could restore it |
| no membrane-touching commit exists between 2026-08-05 and 2026-08-15 | the cause is not a code change |

**The shadow stopped because the whole stack stopped on 2026-08-09; it never returned
because its only enablement was an environment variable that no deployment artefact
carried.** The 08-17 restart brought back everything that was written down and nothing that
was not. The production-role move (2026-08-30) is **not implicated** — it is three weeks
later, exactly as `GD-10` suspected when it refused to infer.

The remedy is already what C9 prescribes for its own reasons: the variable goes in the
deployed unit's `.env` **and** in `.env.example`, so the next restart carries it.
