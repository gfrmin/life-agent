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
