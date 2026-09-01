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
| act pinned to a one-point menu grid | A | accepted | accepted | accepted |
| `act` guard row added | A | accepted | accepted | accepted |
| shipped | **B** | **refused** | **accepted** | accepted |
| act pinned to a one-point menu grid | **B** | **refused** | **accepted** | accepted |
| `act` guard row added | **B** | **refused** | **accepted** | accepted |

All six cells measured (3 world variants × 2 arms × 3 tick shapes = 18 replies, each read
whole and recorded in `matrix.json`). `models` moves with the declaration exactly as r42's
enumerator predicts: arm A 2393 → 2465 with the act guard, arm B 960 → 1016.

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

## C3 — option 2's bar: **FAIL at 0/250**, and the reason is structural

The full recorded stream was replayed on arm B — every row `boot_snapshot` yields, folded
in order, the engine's chosen act read off each evidence tick.

```
UNIVERSE (C6): decisions.jsonl rows joined to a decodable verdict = 250
  boot_snapshot len(verdict_replay) = 250   n_source_records = 4116
  join binds boot_snapshot: OK          (asserted before measuring, not after)

C3: engine-chosen act == recorded act on 0/250 = 0.0000   bar 0.95 -> FAIL
  recorded abstain        (162)  -> engine gather
  recorded report          (87)  -> engine gather
  recorded report_scoped    (1)  -> engine gather
```

**The engine chose `gather` on 250 of 250 rows.** Not a near miss — a constant.

Corrected en route: the first comparison matched raw strings, but `report`/`report_scoped`
are the *executor's* vocabulary and can never be returned by a world whose affordances are
`{abstain, gather, ask, respond}`. `world.REAL_TO_MEMBRANE` is the ONE declared projection
between them and is now bound rather than re-spelled. It does not change the answer —
nothing maps to `gather`, so both readings give 0/250 — but a census that gets the right
number through the wrong constant is right by luck (the r10 lesson).

### Why it is a constant

Host-side, from the same utility the world declares — `argmax_action` over the credence
range, for the declared defaults and for the **deployed** `u_bar` read off the final
recorded boot row:

| `u_bar` | `abstain` wins | `gather` wins | `respond` wins |
|---|---|---|---|
| declared defaults | p1 ≤ 0.020 (2.1%) | **0.021 – 0.997 (97.7%)** | p1 ≥ 0.998 (0.3%) |
| deployed | p1 ≤ 0.033 (3.4%) | **0.034 – 0.996 (96.3%)** | p1 ≥ 0.997 (0.4%) |

`gather` is the argmax across **96–98% of the credence range**, at the measured operating
rate (0.857) included. r44's W1 established 59/59 that the engine tracks `argmax_action` at
its own `p1`, so `gather` on 250/250 *implies* `p1` stayed inside that band throughout —
stated as the inference it is, not as a second measurement.

**This is `world.py`'s own registered flag, now measured.** `utility_by_action` prices
`gather`/`ask` as MYOPIC PERFECT INFORMATION and says so in its docstring: *"this
OVERVALUES information, deliberately and namedly… whether that dissolves the v1 gather-bar
pathology is an EMPIRICAL question the v2 shadow answers."* **It does not dissolve it.** The
v2 shadow gathers essentially always.

### What C3 therefore decides — and what it does not

C3 is recorded **FAIL as frozen**: option 2 does not meet its bar, and no reading below
softens that. But the criterion disqualifies option 2 *"as a corruption"*, and **A2 measured
that there is no corruption to have**: the act does not enter the fold on either arm, so
options 1 and 2 produce the *same posterior over the same rows*. The disqualifying quantity
is causally inert with respect to the thing the backfill is for.

The frozen disjunction is therefore dissolved rather than satisfied, and this is said plainly
instead of being resolved by picking whichever branch reads better (`M-4`):

- **Option 1 preserves the recorded act but cannot serve P1.** One session per act means one
  belief per act — two here, `abstain` (162) and `respond` (88) under the declared
  projection. The live shadow is a single session that must decide; it cannot decide against
  two beliefs. Option 1 restores no accrual.
- **Option 2 serves P1 and is the historical shape** — `session.boot()` has always replayed
  one pooled session with the full menu, which is how every row already in `shadow.jsonl`
  was produced — but it fails C3's number.
- **Option 3 is r46's lever**, cross-checked here (A4) and not built.

The decision this forces is recorded as **`GD-16`**, with the condition that would reverse
it named there.

## Part B — P1

### B1 — the deployed replay path could not replay a single row

The first C7 backfill **died on row 1**, and the failure is the most useful thing in Part B:

```
MembraneError: unparsable reply line: '{"error": "tick refused: missing declared ["act"]"}'
  session.boot -> observe_verdict -> _tick({"features": ..., "evidence": y})
```

`session.observe_verdict` and `observe_outcome` send a **menu-less** evidence tick. HEAD
requires the declared namespace covered exactly; `act` is in the namespace; and
`shadow_features` deliberately never emits `act`, because padding it in is a
`feature/assignment collision` on both arms (A4). The menu is the only supplier left — so
**every** evidence tick was refused and `session.boot()` could not replay against HEAD at all.

Part A's own probes had missed this because they hand-built their ticks *with* a menu. That
is precisely the substitution `M-7` names, committed by the instrument that was supposed to
be checking for it, and it was caught only by driving the deployed surface end to end. The
client fix from A5 earned itself here too: the failure arrived as a legible `MembraneError`
naming the refusal, where before it would have been a bare `JSONDecodeError` from
`json.loads`.

**The repair, measured free on the control before being taken.** Evidence ticks now carry
`"menu": [ACT_NAME]`. On arm A, six evidence ticks followed by a decide return a
byte-identical `p1` (`0.496689261820934`) and `entropy_bits` (`4.073428751831122`) with and
without the menu — so this **restores** the replay rather than re-writing what it folds, the
same "provably a no-op on arm A ⇒ safe forward repair" standard r42 set for items 1–2. The
act the engine then picks is discarded, and A2 is what makes discarding it free.

### B2 — the skip census (C7's first half)

```
UNIVERSE (C6)
  decisions            3865      reactions raw          71
  reactions deduped      70      claude verdicts raw   180
  folded                250      verdict_replay rows   250    (census binds boot_snapshot)
  outcome_replay rows     0      n_source_records     4116

SKIP CENSUS: 0 skipped -> unexplained skips = 0
```

Every reaction that survives dedup routes to a decision and decodes through `VERDICT_Y`, and
every Claude verdict either routes or is superseded by a declared-precedence owner verdict.
Nothing is dropped silently. `outcome_replay` is empty because no warm-vectors directory is
passed — named here rather than left to look like an absence of outcomes.

### B3 — C7: **PASS**

With the replay path repaired, the backfill runs clean and deterministic:

```
DOUBLE RUN
  run 1: 251 wire exchanges, t=250, digest=6ac80708eec83dafdc6913c8…
  run 2: 251 wire exchanges, t=250, digest=6ac80708eec83dafdc6913c8…
  byte-identical double run: YES        C7: PASS
```

251 = one handshake + 250 evidence ticks; `t` lands on 250, so every folded row advanced the
evidence clock exactly once and none was silently skipped. Both halves of C7 are met: **0
unexplained skips and a byte-identical double run**, verified before anything touched the
deployed box.

**Two operational costs, published rather than discovered later.** The replay takes minutes,
not seconds — the C3 pass over the same 250 rows ran ~12 min wall at ~85% CPU with the
engine's resident set climbing throughout — and `session.boot()` pays it on **every service
start**, growing with the stream. It is safe (the supervisor boots inside its daemon worker;
`submit_*` is `put_nowait` on a bounded 1024 queue, overflow counted as drops, so a caller
never blocks on a slow boot) but it is not free, and it is the same fold-depth quantity
`GD-15` is about. Second, the clock r44 declared forces a preposterior on every decide —
297 ms against 135 ms — paid on the worker, never in jarvis's reply.

### B4 — what C7 did and did not verify

Disclosed rather than left implicit:

- **The double run used the world's declared-default `u_bar` (`{}`), not the live posterior.**
  The live shadow is constructed with the real posterior, which moves the grid: both yield
  **n = 8 and `models` 960**, but the two *crossing* rungs shift (`0.02 → 0.033879`,
  `0.997778 → 0.996163`) and the clock price reads `10.830…` rather than `11.0`. So C7
  verifies the **mechanism's** determinism, not the live numbers; the live boot record is
  what verifies those, which is exactly what C9 asks for.
- **`outcome_replay` is empty on both paths, and that is checked rather than assumed.**
  `LIFE_AGENT_MEMBRANE_WARM_VECTORS` is unset, so `config.membrane_warm_vectors_dir()`
  returns `None` and the live boot folds precisely the 250 verdict rows the backfill
  verified — not a larger set the backfill never saw.
- **The bridge disables the shadow on any construction failure** (`server.py`'s
  `except Exception … return None`), and `submit_*` is `put_nowait` on a bounded queue with
  overflow counted as drops. A slow or failing boot degrades the shadow, never the ask path.

### B5 — the review finding: one relation, three declarations

Reviewing the session repair before merge turned up the thing the repair itself had missed.
The menu-less evidence tick was **not** one bug in one place — the same body was spelled
three times:

| sender | role |
|---|---|
| `session.observe_verdict` / `observe_outcome` | the live and backfill path |
| `scripts/membrane/lattice_replay.py` | **r46's own grid-precision leg runs through this** |
| `scripts/membrane/p3_gate.py` | the P3 held-out gate instrument |

Fixing only the session would have left r46's replay tooling dead on arrival against HEAD —
and one relation surviving with several declarations, each defensible in isolation, is
precisely how the value-join defect survived M6 (r34–r38). So
**`session.evidence_tick_body` is now the ONE declaration** and all three senders bind it,
with a drift test pinning each (`tests/test_lattice_replay.py`). The scripts' change is free
on the control by the same arm-A measurement as the session's.

One check the refactor needed and got: `request_json` serialises **without** `sort_keys`, so key order is on the wire, and a helper that re-ordered the dict would have changed the bytes and silently invalidated C7's digest. Verified byte-identical to the pre-refactor spelling rather than assumed.

**The categorical twin is deliberately NOT touched.** `categorical.py:266` still sends a
menu-less evidence tick, and that is left standing on purpose: the categorical world also
has no `codebooks` key (so it cannot handshake at HEAD at all) and no clock row, so a
menu-only fix would repair one third of a world that still cannot boot. It is env-disabled
(`LIFE_AGENT_MEMBRANE_CAT` unset), nothing on any path reaches it, and it is **r46's whole
subject** under the carried `GD-13` obligation. Named here so nobody reads the one
declaration as already covering both worlds — it covers the binary world's three senders,
and the twin is the fourth, outstanding.

## Verdict

| id | criterion | verdict |
|---|---|---|
| **C1** | reachability measured on the built binaries, replies quoted | **PASS** — 18 replies over 3 variants × 2 arms; all three options reachable, refusal quoted verbatim |
| **C2** | the chosen option named before the run that justifies it | **PASS** — `GD-16` committed before the backfill ran |
| **C3** | option 2 admissible only at ≥ 95% act agreement over ≥ 100 rows | **FAIL — 0/250.** Recorded as frozen. See `GD-16` for what it does and does not decide |
| **C4** | every load-bearing predicate RED by mutation | **PASS with a correction** — the act-inertness control was RED but on the wrong axis (A3); re-done, and registered as **`M-25`** |
| **C5** | every reply stream read whole | **PASS** — raw-line capture throughout, which is how the malformed refusal was found at all |
| **C6** | every universe named with its size | **PASS** — 250 joined rows / 3 865 decisions / 70 deduped reactions / 180 Claude verdicts / 4 116 source records |
| **C7** | 0 unexplained skips ∧ byte-identical double run, before any production change | **PASS** — 0 skips, digests identical, scope disclosed in B4 |
| **C8** | `GD-10`'s question answered from evidence consulted, or re-recorded | **PASS — answered**, and it falsified a fact this pre-registration had frozen |
| **C9** | live enable reversible, launcher restores what it found, rows appear or roll back | *(below)* |
| **C10** | the gap declared a segmentation boundary, recorded in the stream | *(below)* |

**Item 3 is resolved, and it was never one thing.** It is (a) a door rule — an evidence tick
must supply every declared name, and the menu is the only supplier for `act`; (b) a modelling
non-question — the act does not enter the fold on either arm, so which act a recorded verdict
is "claimed to have been taken under" changes nothing; and (c) a **capability** that does
exist but not in a world that can also decide (A4). r42 saw only the refusal; r43 narrowed it
to the collision; r45 finds the collision is menu-vs-feature and that the whole modelling
worry was moot.

**Three defects were found in this checkpoint's own instruments**, all published: a guard
grid that could not express the distinction it was testing (A3, → `M-25`), an ordering
confound from probing twice in one session (A3), and a raw-string comparison standing in for
a declared projection (C3). The first would have shipped a false null; it was caught because
the number reversed under a grid that could actually separate the values.

## What this hands forward

**To r46, with r45's measurements changing two of its three items:**

1. **The `act` guard row is not the lever r43 described.** As stated — a guard row added
   while `act` stays in the menu — it is measured **inert** for conditioning (byte-identical
   `p1` across all four acts). The lever that works needs a **discriminating grid** (r45 used
   `[1.5, 2.5, 3.5]`; the `[0.5]` spelling copied from the indicator rows cannot separate
   values 1–4) **and** `act` out of the menu — and that world cannot decide. So r46's first
   item is not "add a guard row and price it" but **"can one world both condition on the act
   and choose it, and if not, what two-world arrangement is admissible?"** Its bar has to be
   written against that question, not the old one. `GD-16` binds: if act-conditioning lands,
   C3's premise goes live and `GD-16` must be re-read before any further backfill.
2. **`GD-15`'s grid precision** — unchanged by r45, still carrying its own bar and lattice.
   Note `lattice_replay.py`, the tool its decision-equality leg runs through, was **broken on
   HEAD until this checkpoint** (B5) and is now bound to the one evidence-tick declaration.
3. **The categorical twin** (carried `GD-13`) — now with a third defect named: it is the
   fourth evidence-tick sender and the only one still menu-less (B5).

**To whichever checkpoint reads a §18 bar** — a precondition, not a nicety: the engine's raw
affordance is a near-constant `gather` (250/250; argmax across 96–98% of the credence range).
A bar must state **which surface it reads** — the raw affordance or `coarse.map_action` — and
must establish that surface's distribution first. r45 measured the raw one and not the mapped
one.

**Not filed, deliberately.** The engine's refusal replies are invalid JSON
(`Eval.hs:40-43` builds them with Haskell `show`, so `["act"]` reaches the wire with
unescaped quotes, against `membrane-wire.md`'s own rule that strings escape `"`). It is not
in their register (`M-23` checked — `exact-author-pack.md:206-208` documents the message
*content*, not its encoding). **r45's pre-registration froze "no new upstream issue is
filed", so none was**, and the finding is handed to a successor with its evidence and its
one-line locus rather than filed against a frozen scope clause. Our side is already hardened
(A5), so nothing here waits on the engine.
