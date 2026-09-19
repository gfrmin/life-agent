# r23 · K1-G4 — the adversary's thirteen, converted

> **Status: PRE-REGISTRATION FROZEN.** Everything above the RESULTS rule is committed
> BEFORE any change to `src/`, `.githooks/`, `tests/` or `.github/`. Results append below
> it; nothing above is edited afterwards.

## What this is

K1's G4 adversary pass ran against `ea8b27e` in a throwaway worktree: a fresh session, no
memory of why the guards looked sufficient, one question — *can the rules be broken while
the gate stays green?* It planted ten violations and ran the full five-leg gate. **All
five legs stayed green, with the pytest count byte-identical to the pre-attack baseline
(2780 passed, 35 deselected).** Thirteen findings were reproduced by running; a further
six were reported as arguable-not-reproduced and are NOT converted here.

Owner ruling 2026-08-27: convert all thirteen in one milestone.

The scoreboard the pass produced, which is the honest state of `docs/guards.md` as opened:
**of the four rows the register called `resolved`, three are defeated** (rows 1, 3, 4) and
one (row 2) is defeated as a guarantee while its literal claim stands. Of the twelve
`instrumented` rows, four are defeated (5, 6, 11, 13) — row 13, the PII guard, four
separate ways. Two findings fall in gaps no row covers.

Guards that HELD are recorded too, because they are evidence of teeth: the K1 re-listing
census fired on the adversary's explanatory *comment* and forced a redesign; the same
happened to the one-recorder census; `test_executor.py` pins `rho` on `menu_transforms`'
output and killed the first pricing attack; the replay oracle went `212/314` with
`CassetteMissError` against a payload-shaped change. It is narrow, not decorative.

## The thirteen, by what they break

**The PII floor of a public repo (rows 13, and gaps).** `CLAUDE.md` makes PII-freedom a
hard constraint. Four independent defeats, all confirmed in the clean tree, one
reproduced independently by the reporting session with its own synthetic values:
- **F4** — every read path returns `None` on a NUL byte and callers drop it silently, so
  one NUL byte unscans a whole file. Binary-detection used as a *skip* is indistinguishable
  from a clean scan. Measured: five findings → zero.
- **F5** — `_skip()` matches `os.path.basename`, so a file named `uv.lock` (or any of nine
  lockfile names) is exempt **anywhere in the tree, forever**, and lockfiles are text.
- **F6** — seven shapes `CLAUDE.md` forbids by name have **no rule at all**: bare 8-digit
  HK phone, IL mobile with two separators, `+972` international form, single-letter
  passport prefix, account numbers, document references, obfuscated emails. Separately,
  `--shapes-only` — the flag CI uses — sets `denylist = []`, so the name layer runs against
  an empty pattern list. A check pointed at nothing cannot tell "clean" from "not looking".
- **F7** — `_path_allowed` is a *prefix* test, so an allowlisted root exempts every
  personal segment beneath it (a customer name, an account id, a document title).
- **F13** — no rule covers owner-specific hostnames, tailnet names, or non-Israeli 9-digit
  ids in `src/`, which `CLAUDE.md` forbids. (The 9-digit rule fires only on values passing
  the Israeli-ID checksum, so every other 9-digit personal id is unenforced by
  construction.)

**Censuses whose universe is drawn from the wrong place** — the register's own entry-1
shape, three more times:
- **F8** — `test_seam.py` excludes by `p.name`, so a file called `seam.py` **anywhere**
  under `src/life_agent` exempts itself from the guard that says one function commits acts.
- **F9** — the one-recorder census greps two dotted spellings; a bare
  `from ... import record_local` is a third it does not enumerate — the exact drift its own
  docstring forbids.
- **F11** — **the fix this reporting session shipped this afternoon has the same shape as
  the defect it closed.** `AMOUNTS_PRODUCERS = (_ExtractAmountsProducer.name,)` and the
  guard asserts `set(AMOUNTS_PRODUCERS) == {ExtractAmountsProducer.name}` — an identity.
  It caught the original defect only because it was run against pre-fix code; after the fix
  it is vacuously true and can never fail. The thing actually being checked is
  `artifacts.producer_name` **as already recorded**, which nothing in tree reads.

**Guards satisfied by prose rather than behaviour:**
- **F10** — `test_reason_consumers_derive_not_respell` asserts `"withhold_reason" in
  <file>.read_text()`. A comment satisfies it while the chain is re-spelled to *disagree*
  (a zero-observation miss rendered as a dispersal). Two sibling guards share the shape.
- **F12** — `_REGISTER_PINS["6.7"]` has needle `""` (existence only), so its artefact can
  be gutted — `collapse_replay.main` made to `return 0` — with the pin green. Three further
  pins use the needle `"def test_"`, satisfied by any test in the file. And
  **`collapse_replay.py` is run by no CI step at all**, so row 5's own precondition for
  *resolved* was never met: a 314/314 reading is a local claim, not a gate.

**Guards that pin the wrong half of the thing:**
- **F1** — the offer-set pin compares `probe` and `name` only. Every row's `cost` can be
  set to `0.0` — including the $0.38 opus deliberate edge run 17 measured as the most
  expensive act on the menu — and nothing anywhere asserts a cost on `menu_transforms`'
  output. This is the largest possible argmax move short of adding a row, and C4 declared
  it the evidence that K1 owed no priced run.
- **F2** — family routing returns on the decision path *and the wire* under a new name
  (`pipeline_verdict`, `POST /pipeline`), because the C1 guard is a **name census over a
  frozen list**. Its literal claim holds; the guarantee a reader takes from it does not.
- **F3** — the replay oracle replays **314/314 pure equality** with two live decision-path
  defects in the tree. It sees changes that alter the `/decide` payload and is blind to
  changes in *which code runs before the payload is built*.

## FROZEN CRITERIA

**P1 — every reproduced finding has a fixture, and every fixture is verified RED by
mutation.** Thirteen findings; a fixture may cover more than one. For each, the transcript
records the planted violation, the guard's failure, and the **marker string** naming the
specific tooth. A fixture that passes on arrival without a recorded mutation does not count.

**P2 — no new PII shape without a kill.** Every shape added to `.githooks/pii_check.py`
ships with a fixture carrying a synthetic violation it catches, and that fixture must fail
if the shape is removed. **A shape with no demonstrated kill is prose that looks like
protection, and is not to be added.** This criterion exists because the fix for F6 is
*adding rules*, and rule count is exactly the metric that rises when you write things.

**P3 — no tautological guard.** Every fixture must be capable of failing when the
**deployed** artefact changes, not merely when a re-implementation of it changes.
Specifically for F11: renaming `ExtractAmountsProducer.name` must fail a guard. A guard
whose two sides move together is recorded as *unenforced*, never *resolved*.

**P4 — the register is updated row by row**, each defeated row naming the finding that
defeated it and its new state. States may only move to *resolved* where P1's transcript
exists. The known-and-uncovered list absorbs everything not converted, in English.

**P5 — the decision path does not move.** The 314-fixture replay reads **PURE EQUALITY**
on every non-aggregate fixture, as at r22. Frozen here because these are guard fixes:
`executor.py:655` already calls the one derivation (verified before this prereg was
written), so F10 is guard-only. **Anything other than pure equality is a FAIL and a STOP**
— it would mean a guard fix silently changed behaviour.

**P6 — the oracle gains a positive control that runs in CI.** `collapse_replay.py` cannot
run the `m5-base` set in CI (the fixtures live under `$LIFE_AGENT_KB`, out of tree). So the
control is in-tree: a deliberately-mismatched fixture the oracle **must** exit 1 on. A green
CI leg then comes from a harness that has just proved it can speak.

**P7 — the arguable-not-reproduced six are NOT converted.** They are recorded in the
register as known-and-uncovered, in English. An argument is not evidence and does not earn
a fixture.

## Gates

G1 suite + ruff + mypy + PII guard green · G2 the replay per P5 · G3 not bought (guard
fixes; P5 is the evidence) · **G4 is not re-run here** — a second adversary pass against
the converted tree belongs to the next milestone, not to the one converting the first
pass's findings.

---
## RESULTS

*(appends here; nothing above is edited)*

**Read 2026-08-27, $0. All seven frozen criteria MET. No priced run bought.**

### P1 — every finding has a fixture, every fixture verified RED by mutation: MET

**28 poison fixtures** under `tests/poison/`, all running in CI's ordinary pytest leg.
Fourteen mutations were applied to the fixed tree and each produced its named marker:

| # | Mutation | Fixture that died | Marker |
|---|---|---|---|
| M1 | NUL returns `None` instead of raising | F4 | `contains a NUL byte and was NOT scanned` |
| M2 | `_skip` matches basename again | F5 | `skips are declared per PATH, not per basename` |
| M3 | all seven new shape rules removed | F6 (×7, each independently) | one failure per shape |
| M4 | src-scoped owner-literal rule removed | F13 (×2) | `owner-specific literal` |
| M5 | the shapes-only announcement removed | F6b | `name layer not run` |
| M6 | a `seam.py` elsewhere calling `.optimise(` | F8 | `assert [PosixPath('tasks/seam.py')] == []` |
| M7 | a bare `from ...recorder import record_local` | F9 | `a spelling of the one recorder outside the declared leaves` |
| M8 | the withhold chain re-spelled to disagree | F10 | `does not CALL decisions.withhold_reason — a source substring is not a call site` |
| M9 | every menu row's `cost` set to `0.0` | F1 | `a price change moves the argmax and owes a priced gate run` |
| M10 | `pipeline_verdict(question)` gating the typed path | F2 | `a new call consumes the question on the dispatch path: ['pipeline_verdict']` |
| M11 | `POST /pipeline` added to the bridge | F2b | `the bridge serves undeclared endpoint(s) ['/pipeline']` |
| M12 | `ExtractAmountsProducer.name` renamed | F11 | `a rename orphans every derived artifact and needs a migration` |
| M13 | `collapse_replay.main` made to `return 0` | F12 | `the oracle has been made unable to fail` |
| M14 | an existence-only (`""`) register needle restored | F12b | `pins with a needle that names nothing specific` |

M6–M11 replant the adversary's own violations verbatim.

### P2 — no new PII shape without a kill: MET

Seven shapes added. M3 removed all seven at once and **each produced its own failure**, so
every one has an independent tooth. All are context-anchored (a bare 8-digit run collides
with dates; a bare `[A-Z]\d{7}` collides with hashes) because a noisy guard gets disabled,
and a disabled guard is what let the 2026-08-18 leak through.

The single-letter passport rule earned its place immediately: on its first run over the
tracked tree it found **four** synthetic passport literals of exactly the forbidden shape in
`tests/test_lookup.py`, invisible to the old two-letter rule. They are now marked
`# PII-OK: synthetic passport` per the repo convention.

### P3 — no tautological guard: MET

`RECORDED_PRODUCER_NAME = "extract_amounts"` is pinned as a literal in
`tests/poison/test_oracle_poison.py`, so the guard no longer compares an expression with
itself. M12 confirms a class rename fails it. The demand log's hard-coded `transform_name`
is pinned to the same constant, closing F11's collateral.

### P4 — the register is updated row by row: MET

`docs/guards.md`: **eleven resolved, nine instrumented**, each resolved row naming the
mutation that kills it. It opened this morning at four and twelve, and three of those four
were then defeated — so this is the first time any of these numbers has been earned rather
than assumed. Nine known-and-uncovered items in English, including the two the fix work
itself produced (below).

### P5 — the decision path does not move: MET, pure equality

`collapse_replay.py --checkpoint m5-base`, `PYTHONHASHSEED=0`: **314/314 fixtures replay
identically**, exit 0. All thirteen conversions are guard-side.

### P6 — a positive control that runs in CI: MET

`tests/poison/harness_control.py` is a deliberately failing test, not named `test_*.py` so
the ordinary suite never collects it (2808 collected, not 2809). CI runs it explicitly as
the **first** test step and fails the job if it PASSES. A green test step is otherwise
indistinguishable from a step that ran nothing — a conftest import error, a bad marker
expression, zero items collected.

### P7 — the arguable six are not converted: MET

Recorded in `docs/guards.md` as known-and-uncovered item 5, in English, unconverted.

### Gates

G1 `pytest -m "not llm and not system"` **2808 passed**, 35 deselected (2780 → 2808 = the
new fixtures); `ruff check .` clean; `mypy` clean on 226 files; `pii_check --shapes-only`
exit 0 on the tracked tree.
G2 **314/314 pure equality** on `m5-base`.
G3 not bought — P5 is the evidence.
G4 not re-run: a second adversary pass belongs to the next milestone.

### Defects in this milestone's own work, found while doing it

1. **Two of the fixes were wrong and were withdrawn or corrected after being run against
   the real tree**, not after being reasoned about. The obfuscated-email rule's `\s+at\s+`
   branch matched ordinary English prose (8 false positives). The personal-segment shape
   rule fired on **20 legitimate paths**, because a personal name and a kebab-case slug are
   structurally identical. The first was narrowed to bracketed forms only; **the second was
   withdrawn entirely** and recorded as known-and-uncovered rather than shipped as a noisy
   rule. This is P2's clause working as intended.
2. **The first version of the oracle control did not go red under its own mutation.** It
   asserted the *shape* of `main`'s returns by AST; because `main` has other non-zero
   returns (argument errors), an unconditional early `return 0` slipped past it. Replaced
   with a behavioural control that drives the real entry point against an absent fixture
   directory. Found only because P1 requires the mutation to be run — an AST guard that
   passes on arrival would otherwise have been recorded as *resolved*.
3. **A fixture built from invented field names "passed" for the wrong reason.** The
   comparator flags anything unclassified, so a self-comparison of invented keys also
   diffed; the fixture was rebuilt on `compare.VALUE_COMPARED`'s declared vocabulary.
4. **An over-wide source slice deleted `il_id_valid` and the skip helpers** while removing
   the withdrawn rule; caught by the tree scan crashing, restored, and re-verified.
5. **The D-5 behavioural assertion was initially too wide**, asserting the reason token
   appears in the render for `hedge` and `ask_clarify` — which have their own contract
   grammars and render no reason. The guard was scoped to the withhold branch. My
   expectation was wrong, not the code.

6. **The pre-commit PII hook blocked this milestone's own fixtures**, twice over: the
   `# PII-OK` marker is LINE-based and had been placed on the parametrize decorator's
   closing bracket rather than on each line carrying a shape; and the owner's private
   denylist caught a real company domain inside a value labelled "synthetic". Both were
   corrected (markers moved onto the shaped lines; the domain replaced with
   `example.test`). Worth recording plainly: the guard being repaired here caught the
   repair, and the denylist layer — the one CI does not run — was what caught the domain.

All six are disclosed rather than quietly corrected, because a milestone that converts an
adversary's findings while hiding its own is doing the thing it was built to stop.

---
## FOLLOW-ON (2026-08-27, same day, $0) — the consequences of the disclosures above

The six defects disclosed above were recorded and nothing was done with them. That is the
failure the whole method exists to prevent: *a report is a photograph, the repository is a
film.* Owner challenge, same day: "no consequences from the learnings?" Correct. This
section is the consequence, and it is machine-checked, not prose.

**F10 was a CLASS, not a guard.** The adversary named two siblings; a census found **nine**
`assert "<name>(" in inspect.getsource(...)` assertions across `test_m7_register.py` and
`test_m6_declaration.py`. One was converted in r23 and eight were left standing — the exact
"finding is not the deliverable" error, committed while writing the milestone about it.

Landed:
- `tests/_guard_ast.py` — `calls(obj, name)` resolves a call by AST walk, so a name in a
  comment or docstring is not a call. All nine assertions converted, each now carrying a
  marker naming its tooth (verified: removing `DEC.edge_id(` while leaving the name in a
  comment produces *"EX.extract_edge does not CALL edge_id() — one declaration, one home"*).
- **Register row 18** — no guard may prove a call with a substring. Mutation: reintroducing
  `assert "leader_order(" in inspect.getsource(LK)` fails it by file and line.
- **Register row 19** — every `test_poison_*` fixture must name, in its docstring, the
  planted violation that kills it. Mutation: a fixture with a docstring naming no kill fails
  it by name. This is the standing answer to r23's own worst defect — a control that passed
  its own mutation and would have been recorded as `resolved` on the strength of passing.

Scoped honestly, and both scopings were found by **running the rules against the tree before
believing them** (r23's own lesson, applied immediately): row 18 anchors at the start of a
stripped line, because prose *quoting* the forbidden pattern is not a use of it; row 19
covers `test_poison_*` only, because the precision controls beside them (a rule must NOT
fire on legitimate content) are a different and equally necessary category with no mutation
by construction.

Register: **13 resolved / 9 instrumented**. Gates: G1 **2810 passed** + clean lint/type/PII;
G2 **314/314 pure equality**; G3 not bought.
