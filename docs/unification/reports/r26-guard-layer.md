# r26 · K3 — the guard layer proves behaviour, not spelling; and no host is a concept here

> **Status: PRE-REGISTRATION FROZEN.** Committed BEFORE any change. Results append below
> the rule; nothing above is edited afterwards.

## Why this exists

K2's G4 adversary pass defeated **8 of the 13 rows `docs/guards.md` called *resolved***,
including guards written the same day to close the previous pass. r25 fixed the three
findings that were live defects in the *inference*; it deliberately did not touch the
structural finding underneath, and surfaced it to the owner instead:

> Eight of K2's eleven defeats were **a census whose universe is a string**. Repairing each
> evasion individually produces more string censuses one alias wider. Whether the remaining
> censuses should be replaced by behavioural assertions is a design question carried to the
> owner, not answered by reflex.

**Owner ruling 2026-08-27:** the standing directive (*the most principled option, with its
design cost named*) answers it — convert, do not patch. This milestone is that conversion,
scoped to where a behavioural form exists, with the residue written in English rather than
re-spelled as a weaker census.

Four defects are fixed. All four were **verified against merged master before this prereg**,
and all four are the same class — *the checker's universe is derived from somewhere other
than the thing being checked*, which is `docs/guards.md` entry 1's own lesson describing the
guards written after entry 1 was recorded.

## The four live defects

| # | Defect | How it was verified |
|---|---|---|
| **D-a** | The replay oracle's **wiring** is uncontrolled. One control exercises the comparator in isolation (sound); the other drives `main` at a **missing directory** — `collapse_replay.py:122`, three checks before the compare loop. Nothing proves that on a real fixture set `main` reaches `compare_fixture` and lets a diff reach the exit code. | read `scripts/collapse_replay.py:120-172` against `tests/poison/test_oracle_poison.py` |
| **D-b** | `test_gate_legs_are_reachable` asserts `r.returncode is not None` — true of every completed subprocess. It cannot fail. | read; trivially total |
| **D-c** | `G.calls(<module>, name)` takes a **whole module** as its universe (`_guard_ast.called_names` walks `inspect.getsource(obj)`). A call in a never-executed or env-gated branch satisfies it while the deployed path diverges. | read `tests/_guard_ast.py` against `tests/test_m7_register.py:116-124`; the bridge has env-gated code |
| **D-d** | **The `PII-OK` marker is an unconditional bypass of the private denylist.** `pii_check.scan_text` does `if MARKER in line: continue` *before every check*, so a line marked synthetic is never tested against the real-value layer. | ran the guard with a synthetic denylist pattern: unmarked → hit, marked → no hit |

**Correction carried into the record.** An earlier reading of D-a claimed the comparator
itself was unproven. It is proven — `compare_body` is driven with a planted mismatch. What is
unproven is the *wiring* between comparator and exit code. D-a is narrower than first stated
and still real.

D-a's survivable mutations, named here so the control is written against them and not
against a paraphrase: `diffs = []` inside the loop; `if diffs:` → `pass`;
`bad = len(errored)`. Each leaves both existing controls green and prints `314/314`.

## The host purge (owner ruling, same day)

> *"we need to design this repo to work without \<the deploy host\>, simple as that"* — and,
> on the draft plan: *"dont forget this is a public repo so \<it\> shouldnt even be a
> concept"*.

The second sentence is the load-bearing one. A machine name is owner-specific
infrastructure, and this repo's rule already covers it: nothing in tree carries an
owner-specific hostname, *"including in docs prose, §14 ledger entries, commit messages, and
test fixtures."* So this is a **PII scrub**, not a portability tidy-up.

Measured before this prereg, and stated as counts because **this report is in tree and may
not name what it removes**:

- **25 occurrences of two owner host names across 15+ tracked files** — `packaging/`, the
  reports, the conferrals, a design doc, and one poison fixture.
- **The private denylist catches neither.** 38 patterns load from the KB; the host token is
  caught nowhere — not in prose, not bare, not in `src/`.
- **The public shape rule cannot reach them.** The tailnet-host shape fires only when
  `in_src` (`pii_check.py:606` gates on `path.startswith("src/")`) and requires the
  `.tail<hex>.ts.net` suffix, which a bare name in prose does not have.
- **One was laundered in the day before this milestone**, by the session writing the guard:
  a real host name under a synthetic tailnet suffix, marked `PII-OK: synthetic`. The suffix
  is synthetic; the name is not — and per **D-d** the marker meant the guard never looked.

**Append-only does not exempt PII.** The convention protects *findings* from being rewritten;
`04cc161` already scrubbed corpus PII from reports under exactly this rule. Every report keeps
its meaning and its numbers; only the machine name goes, replaced by the **role** it stood for,
with two machines kept distinguishable where a report distinguishes them.

## What is deliberately NOT attempted

- **Converting every census.** Some properties have no behavioural form on this tree. Those
  stay censuses and are listed in `docs/guards.md` **in English as known-and-uncovered** —
  there is no coverage fraction over an attack surface, because the denominator is not
  enumerable.
- **Choosing which box runs the live surfaces.** After this milestone that is a `.env` +
  `systemctl --user enable` choice with no repo change, which is what the ruling asks for.
- **Any sync mechanism for the calibration stream.** The readout learns to union more than
  one KB root and to report its own staleness; nothing replicates anything.

## Frozen criteria

Read after the gates run. Each is met or it is not; a criterion is not restated after a read.

| | Criterion |
|---|---|
| **C1** | The oracle has an **end-to-end** control: a synthetic fixture set with one planted mismatch drives `main` to exit **1** naming that fixture. RED under all three named mutations |
| **C2** | No assertion in `tests/` reads only that something happened; every gate-leg control discriminates a planted violation from a clean input |
| **C3** | No module-scoped `G.calls` survives where a function-scoped or behavioural form exists; residue is a register row in English |
| **C4** | The two new rules (rows 20, 21) exist as **pure functions over synthetic source**, each RED under its own mutation, then applied to the real tree |
| **C5** | **Zero** tracked files name an owner host — reports and conferrals included. Each edited report still reads correctly, with its machines still distinguishable by role |
| **C6** | The shape layer is RED on a planted tailnet host anywhere outside `src/`; the private layer carries both host names and is RED on a bare host name in prose |
| **C7** | The `PII-OK` marker no longer suppresses the private denylist — RED on the laundered line — and every existing marked line has been re-scanned under it and cleared or fixed |
| **C8** | Every unit + wrapper resolves against a sandbox `HOME` with no host-specific value |
| **C9** | The readout unions ≥1 KB root and reports its covered window + newest-row age |
| **C10** | The five completion-programme DONE conditions are in `ROADMAP.md`, each with its in-tree source, or **marked unsourced** |
| **C11** | G2 — the 314-fixture replay on `m5-base`, **pure equality**. This milestone touches `tests/`, `.githooks/`, `packaging/`, `scripts/` and `docs/`. If a `src/` change proves necessary, C11's expectation re-opens and the change is **disclosed**, not absorbed |
| **C12** | **G3 not bought.** The evidence is C11, exactly as K1/K2/r25. Frozen here so it is not renegotiated after the read |

## Gates

**G1** full suite (`-m "not llm and not system"`) + `ruff check .` + `mypy`, evidence pasted ·
**G2** `scripts/collapse_replay.py --checkpoint m5-base` at `PYTHONHASHSEED=0` ·
**G3** not bought (C12) · **G4** the adversary pass — fresh session, throwaway worktree,
discarded and verified clean, findings **reproduced not reasoned**, each becoming a poison
fixture written by the *next* session and verified RED before landing.

## Order of work (fixed here so C5 is not checked against a report that reintroduces the token)

1. This prereg.
2. Strand A (the four defects) and Strand B (the two rules), TDD red-first.
3. Strand C: the purge, then the two guard layers, then portability + the readout.
4. Strand D: the DONE conditions into `ROADMAP.md`.
5. The RESULTS section below — written **before** C5 is checked, because writing this report
   is the most natural way to reintroduce exactly what step 3 removed.
6. Gates, then `docs/guards.md`.
