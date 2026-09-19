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

---
## RESULTS

**Read 2026-08-27, $0. Eleven of twelve criteria MET; C10 is met in its letter and its
premise is refuted — see below. G3 not bought (C12), as frozen.**

### C1 — the oracle is controlled end to end: MET

A hermetic two-fixture set is written into a tmpdir and `main` is driven at it through
`--fixtures`. `trace == "seam"` needs no wire and no snapshot, and omitting
`provenance.python_hash_seed` skips the seed refusal, so the control runs anywhere the
suite runs. One fixture matches the truth; the other has its recorded effector and EU
corrupted. `main` must exit **1** with the corrupted fixture id and the word `mismatched`
in stdout.

**RED under all three named mutations** — `diffs = []` inside the loop, `if diffs:` → `pass`,
`bad = len(errored)`. Each leaves both pre-existing controls green and prints `314/314`,
which is the defect stated as a demonstration rather than as an argument.

### C2 — every control discriminates: MET

`test_gate_legs_are_reachable` (whose sole assertion was `r.returncode is not None`, true
of every subprocess that completed) is replaced by a clean-input/planted-violation pair per
leg: `ruff` on a file with a real `F401`, and the PII guard on a file carrying a synthetic
shape it must reject. The general rule is C4's row 23.

### C3 — no census takes a whole module as its universe: MET, with the residue in English

The three `leader_order` censuses are scoped to the deployed function. The defect was
demonstrated first: with the bridge handler re-spelled to a divergent `sorted(...)` and the
call moved to a never-called helper, the module-scoped census still returned `True` while
the deployed path ordered differently.

**Residue, named rather than papered over** (`docs/guards.md` known-and-uncovered 13): only
the bridge site was shown to diverge under a planted re-spelling. The other two are pinned
by a *scoped call census*, which proves the call is on the deployed function's body and not
that the emitted order matches. A behavioural driver for those two is not written.

### C4 — the two rules are pure functions over synthetic source: MET

Both are exercised on synthetic source first and applied to the real tree second, so each
can be mutation-tested without touching the thing it guards (r25's L8).

Rule 1 (module-scoped censuses) discriminates on the argument's **syntax** — an `ast.Name`
is a module or class, an `ast.Attribute` is a named function — so it needs no list of module
aliases to keep current. Killed by restricting it to ALL-CAPS names, which makes its
universe a naming convention.

Rule 2 (discrimination) was **narrowed twice against the real fixture set, and both
narrowings are recorded with their counts** because the discarded breadth is the
interesting part: including bare truthiness flagged **7** sound census fixtures
(`assert not offenders` is a claim about a value the test derived); including `is None`
flagged **1** more, where `is None` is the function's specified return. `is not None` only
flags **0** today and would still have caught the defect. The written limitation stands in
the docstring and in the register: `is not None` is not vacuous in general, and the house
rule is deliberately narrower than the English.

**Numbering disclosure.** This pre-registration calls them "rows 20, 21"; those numbers were
already taken by r25 (`_SKIP_PATHS`, the upstream join). They land as **22 and 23**. The
prereg is frozen and is not edited.

### C5 — zero tracked files name an owner host: MET

`git grep -icE` on both names returns **0 files**. 25 occurrences across 15+ files are gone:
`packaging/`, six reports, one conferral, a design doc, one poison fixture. Each was replaced
by the **role** it stood for, read in context so that reports distinguishing two machines
still distinguish them. No report lost a number or a finding.

Checked **after** this section was written, per the order of work fixed above — writing a
report about a purge is the most natural way to reintroduce what the purge removed.

### C6 — the two layers: MET

*Shape (public, in tree):* the tailnet-host rule fires outside `src/` now — verified live on
a planted synthetic host in a `docs/` path, and still in `src/`. The owner-id literal rule
stays `src/`-scoped deliberately: it matches an identity-shaped *binding*, which outside
`src/` is someone quoting code, and widening it is a separate change with its own
false-positive question.

*Name (private, never in tree):* the KB denylist went 38 → **40** patterns. Probing every
alpha-literal pattern in the loaded set: **6 of 6 caught in bare prose**, and **6 of 6 still
caught when the line carries the marker**. An in-tree denylist of forbidden hostnames would
publish the hostnames it forbids, which is why this layer has exactly one correct home.

### C7 — the marker exempts shapes only: MET

`PII-OK` had been an unconditional `continue` ahead of every check, so a line marked
synthetic was never tested against the real-value layer. A synthetic value has a real shape
by design and can never contain a real name, so there is no legitimate use this breaks.
Verified live: a marked synthetic shape is still suppressed; the same shape unmarked is
caught; a marked line carrying a denylist name is caught, with the message saying the marker
does not exempt the name layer.

**The marker's whole accumulated set was re-scanned — 172 lines across 53 files, the first
audit of that set in its life.** It came up clean. The marker had been an unreviewed kill
switch with no trail and no cap for as long as it existed.

### C8 — the tree runs on any box: MET

Split by what can actually be driven. The **wrappers** are behaviour: each is symlinked into
a scratch directory (the deploy shape) and run with an empty `HOME` and a stubbed `PATH`,
and must still hand off `uv run --project <this repo>`. The **units** are a rule over the
file, and that half is disclosed as a spelling census in the register — `systemd` is the
deployed reader of a unit file and cannot be invoked offline against a fake home.

Seven mutations RED. Two are worth naming: dropping the rule's directive scoping flags the
install **comment** every unit carries (a rule that flags correct files gets switched off,
which is how a guard dies), and a unit that stops declaring a repo `ExecStart` at all trips
the census's own coverage assertion rather than passing silently.

**Found en route:** `production-readout.service` was the one unit with no wrapper — it ran
a build artefact at a fixed path and never sourced `.env`, so its KB root had to come from a
unit override. That is exactly the drift trap `jarvis.service`'s own comment warns about,
sitting in the tree beside the warning. Now `bin/production-readout`.

### C9 — the readout unions roots and reports its own staleness: MET

`--kb` is repeatable and the three streams are unioned. Dedup is on the whole row: the
streams are append-only and immutable, and **a decision row carries no decision id**, so the
row is the identity. The report states the window it covered, the age of its newest row, and
the word STALE when nothing is newer than 8 days or when there are no rows at all. Roots are
reported **by index and row count**, never by path — a KB root is an owner-specific absolute
path and this report may be pasted anywhere; a dead root reads `0 rows (EMPTY)`.

The eval-run exclusion now sets the window too, so a gate sweep cannot make a dead
production stream look fresh. Smoke-run live against two roots, one of them empty.

### C10 — the DONE conditions in `ROADMAP.md`: MET in its letter, and its premise REFUTED

The list is landed with each condition carrying its in-tree source or the word UNSOURCED,
which is what C10 asks. What the reconstruction found is worse than a missing list:

- **Only items 1 and 2 are ever referenced anywhere in tree** — six item-numbered lines in
  total, across reports, conferrals, design docs, root docs and every commit message in
  history. **No text names a DONE item numbered 3 or higher.**
- **Item 1 is stated exactly once, inside a decline branch that was never taken.** Item 2 is
  never stated at all — referenced twice by number — and **its referent was deleted** by a
  ruling that does not mention the programme, the item, or what becomes of it.
- **The count "five" appears exactly once in tree: in C10 itself.** It came from the plan
  that opened this milestone, not from any earlier text. So C10 asked for five conditions on
  the authority of C10.

That is this milestone's own defect class one level up — *a checker's universe derived from
somewhere other than the thing being checked* — committed in a frozen criterion by the
session writing the guards against it. It is recorded, not rounded off. Honouring the
owner's ruling that the proplang graduation is not a completion condition, the chain yields
**four** elements, not five; the most economical reading (DONE item *N* = the close of Stage
*N*, which holds for both attested numbers) predicts a Stage 3 that is named nowhere. Four
further disagreements are unreconciled in tree and are recorded beside the list.

**This is an owner keypress, and it was already on the plan's keypress map.** The completion
audit reads against this list; it should not read until the owner says what items 3–5 were,
or that there were four.

### C11 — the replay: MET, PURE EQUALITY

**314/314 fixtures replay identically** on `m5-base` at `PYTHONHASHSEED=0`. No `src/` change
was necessary, so C11's frozen expectation never re-opened.

### C12 — G3 not bought: HELD

The evidence is C11, exactly as K1/K2/r25. Frozen before the read so it could not be
renegotiated after it.

### Found beyond the frozen set

**The register's own headline had drifted twice.** `docs/guards.md` said *thirteen resolved,
nine instrumented*; the rows said fifteen and ten; the report that last touched it said
sixteen and nine. Three numbers, one register — and the headline is the number a reader
quotes. It is now recomputed from the rows (`tests/test_guard_register.py`), with row ids
required unique and every *resolved* row required to name its kill. Four mutations RED.
True count today: **18 resolved / 11 instrumented**.

**In production, the deployed arm has answered nothing.** The live readout over the deploy
window reads 22 non-eval decisions, **all abstain**, zero graded outcomes, newest row
2026-08-26. Two standing wrong-commit rows ride in production and neither has had an
opportunity to fire. This is a readout, not a diagnosis (the cap): recorded as a disclosure
item for the owner, not opened as an arc.

**No record carries a deployment origin.** `run_id` names a *lane* (two literals across all
live traffic), never a box, and a decision row has no decision id. Two deployments' streams
are therefore indistinguishable in kind as well as unmergeable in principle. C9 delivers the
honest read-side half; the record-format half moves the replay fixtures, which C11 froze at
pure equality, so it is scoped to its own pre-registration.

### Defects in this milestone's own instruments, all caught before a verdict

1. **An incomplete mutation reads exactly like a dead guard.** The first mutation script for
   the PII legs matched only rules whose pattern sits on one line, so two multi-line rules
   were never neutered and the run reported a false all-clear. Redone with named anchors:
   neutering the bare rule alone stays green (it is shadowed), neutering the labelled rule
   goes red, neutering both goes red.
2. **A frozen criterion's own count was unsourced** — C10, above.
3. **A new fixture was caught by an existing rule** (row 19) for not naming its mutation in
   the accepted phrasing. Fixed by rewording, not by exempting.
4. **The PII guard blocked this milestone's own new fixture**, twice — once for a synthetic
   mobile shape (correct; marked), once for a home-rooted synthetic path (correct; the S3
   rule working one day after it landed, on the session that wrote it). Both rule mutations
   were re-verified RED against the *new* synthetic rather than assumed to survive the edit.
5. **A test expectation contradicted its own assertion message.** The readout window fixture
   asserted the eval row's timestamp while its message said an eval row must not set the
   window. Corrected to the production row, which makes the fixture sharper, not weaker.

### Deviations from the order of work fixed above

- `docs/guards.md` was written before Strand D rather than after the gates. C5 was still
  checked after every doc landed, which is the constraint the ordering existed to serve.
- `bin/` was not in the prereg's list of touched directories; `bin/production-readout` is new
  (C8's finding). No `src/` change, so C11 is unaffected.
- `tests/test_guard_register.py` is beyond the frozen set, opened by a defect found while
  editing the register the criteria report into.

### Gates

G1 **2849 passed**, 35 deselected; ruff clean; mypy clean on 226 files; PII exit 0 with
the name layer live · G2 **314/314 pure equality** on `m5-base` · G3 not bought (C12) · G4 the adversary
pass, below.

### Post-RESULTS self-audit (same day, before G4 read)

Re-reading the new portability guard against this milestone's own rule 22 found **two
list-shaped universes inside the guard that enforces it**:

- `_WRAPPERS` was a hard-coded tuple of nine names, so a wrapper added later would simply
  never be checked. The universe is now the **`bin/` directory** (executables minus one
  declared exception), with a floor assertion so an empty or unreadable `bin/` cannot
  silently check nothing.
- `_PATH_DIRECTIVES` is a list, so a systemd directive not on it is not read at all. Every
  directive appearing in `packaging/` must now be classified as path-carrying or not, and a
  new one fails until someone decides which set it joins.

Three further mutations RED: a new wrapper reading its root from `$HOME` is caught without
editing the test; an unclassified directive appended to a unit fails; narrowing the `bin/`
census to match nothing fails the floor. C8's mutation count is **ten**, not the seven
recorded above.

The finding worth keeping is not the two gaps. It is that a milestone whose whole subject is
*a census whose universe is a string* shipped two of them in its own new guard, and they
were found by re-reading rather than by any check — the same way K2's adversary found eight.

**Also closed in the self-audit: C2's rule was narrower than C2's English.** The
discrimination census walked `tests/poison/` while the criterion says *"no assertion in
`tests/`"*. Measured first — zero offenders outside the poison directory — then widened to
all of `tests/`, so the narrower universe was costing coverage and buying nothing. Verified
RED by planting the vacuous shape in a non-poison test file, which the old universe could
not see.

---
## G4 — the adversary pass

**Method.** Five adversaries, one throwaway detached worktree each at the K3 head, split by
guard family (the oracle; the census rules; the PII layers; portability; the register + CI).
Each had to **plant a defect and show the gate green with a transcript** — an argument was
not admissible (r23 P7). Every claimed finding was then handed to a **different** agent
starting from its own clean worktree, told to default to *not reproduced* and given the
common ways a claimed defeat is actually wrong.

**The pass was cut short by an account limit.** 47 findings were claimed; **12 completed
independent reproduction and all 12 were confirmed**; 35 never reached a verifier. Those 35
are recorded below as claims with the attacker's transcript, **not as findings**, and the
rows they touch are marked provisional. This is disclosed rather than smoothed: a pass that
verified a quarter of its claims is not a pass that found twelve things.

### Verdict

**Six rows the register called *resolved* were defeated, one of them with no plant at all.**
K3's central claim — *a guard proves behaviour, not spelling* — **does not survive its own
first adversary pass.** The four defects K3 fixed were real and their fixes hold; what does
not hold is the generalisation, and the reason is uncomfortable and specific: **the two new
rules K3 wrote to close the census-universe class are themselves defeated by narrowing their
universe, in a way their own synthetic mutation tests cannot express.** That is r25's L8
lesson recurring one level up — the rule was extracted as a pure function so it could be
mutation-tested, and the mutation test's universe is now the thing that is unguarded.

### Confirmed findings (independently reproduced)

**Row 5b — the oracle's end-to-end control, defeated three ways.** All three leave every
control green and the replay printing `314/314`.
1. *The control is structurally distinguishable from every real fixture.* It omits
   `provenance.python_hash_seed` (deliberately, to skip the seed refusal) and carries a
   distinct `engine_version`. Gating the compare loop on that tell gives `314/314`, exit 0
   and a byte-identical transcript with a live poster defect in the tree. The fixture that
   proves the machinery works is the one that says which inputs to ignore.
2. *`bad = len(failed)` — the mirror of the mutation row 5b names as its kill.* 103 fixtures
   that could not be replayed at all exit 0.
3. *The comparator's field-class list is silently weakenable* (**high**): 5 of the 12
   value-compared decision fields drop to type-only with the whole guard layer green — and
   the suite gets *larger*. The verifier's correction is worth keeping: row 5b's literal
   claim (a planted mismatch reaches the exit code) still holds; what is defeated is the
   **machinery's input**, which no criterion covered.
4. *The oracle never reads the manifest that declares its own fixture set*: a doctored
   314-file set reports `314/314`, exit 0.

**Row 18 — defeated, and LIVE in the tree with no plant.** The no-substring-proof census is a
one-line spelling census that catches 2 of 7 spellings of the identical proof. An assertion
already in tree evades it. This row was earned at r23 and re-earned at r25.

**Row 22 — the module-universe rule, defeated three ways.** `G.called_names(MODULE)` (the
repo's own public helper) restores the whole-module universe because the rule matches the
identifier `calls`; an `rglob("src/**/*.py")` existence census produces a guard wider than a
module that neither row 22 nor row 18 sees; and the rule can be narrowed tree-wide while its
own synthetic mutation test stays green.

**Row 23 — the discrimination rule, defeated two ways.** It is annotation-blind (one line
makes it skip every real test while the unannotated synthetic fixtures still pass), and it
matches only the literal `is not None`, so an `isinstance(..., int)`-only control — D-b's
exact defect in a different spelling — passes the full gate.

**Rows 13 + 20 — a second, unannounced, unpinned skip set** (**high**). `_BINARY_SUFFIXES`
(20 entries) is checked *before* the NUL refusal, keyed on extension alone, so a plain-ASCII
`.db` and a real PDF carrying PII ride every leg green. Row 20 pins `_SKIP_PATHS` by
equality and announces every skip; this second set is pinned by nothing and announced never,
which restores K2-16's exact defect through a door the pin does not cover.

**Row 12 — the drift gates are substring censuses** and fall to re-spelling.

### The through-line

There is one, and it is not the one K3 fixed. Every confirmed defeat is **a guard whose
universe is narrower than the property it stands for, where the narrowing is invisible to
the guard's own test**: a skip set the pin does not cover; a field-class list no criterion
reads; a spelling the census does not enumerate; a synthetic fixture set that cannot express
the mutation that would kill the rule. K3 converted *whole-module* universes to
*function-scoped* ones and called the class closed. The class was never about modules — it
is about **the checker's universe being derived from somewhere other than the thing being
checked**, which is entry 1, and K3's own rules are the newest instances of it.

### What held — the part that says which rows are load-bearing

45 attacks were caught by the guards, and the oracle's family is where they concentrate: the
float tolerance widened to 9e-3, `values_equal`'s list branch stubbed to `True`,
`retrieval_keys`/`regime`/`n_obs`/`effector`/`credences`/`candidates`/`eu`/`policy` each
moved to runtime-measured, the whole posted body skipped, the unclassified-field branch
replaced by `continue`, the M2 poster stubbed — **every one caught, by a named test.** Both
kills `docs/guards.md` names for rows 18 and 22 were re-verified to still bite. The comparator
is not decoration; its *classification input* is what nothing covered.

One adversary recorded a methodological failure of its own unprompted: its first mutation
matrix produced a false all-clear, "because it reads exactly like a dead guard" — the same
defect this milestone's own RESULTS records at item 1, found independently.

### Not converted

- **35 claims never reached a verifier** (all 14 register/CI claims, 11 portability, 9 PII,
  1 census). They touch rows 0, 4, 13, 19, 20, 24, 25 and the new register-count guard. Each
  has an attacker's transcript and none has second-agent reproduction, so **none is a
  finding** and none earns a fixture. The rows they touch are **provisional**.
- **28 arguable items**, never reproduced by anyone, are not carried forward at all.

**Two of the unverified portability claims were independently correct** — `_WRAPPERS` as a
hand-maintained literal, and path directives the rule does not list. Both were found the same
day by re-reading the guard against rule 22 (the post-RESULTS self-audit above) and both are
already fixed. That the adversary and the author found the same two gaps by different routes
is the strongest single piece of evidence in this pass that the class is real.

### Conversion is the next session's work, not this one's

The standing discipline is that findings become poison fixtures written by a **different**
session and verified RED before landing — the author of a guard is the worst person to write
its kill. The confirmed twelve are specified above in enough detail to write those fixtures
without re-deriving the attacks. The 35 unverified claims need verification first, and the
verification is what the limit interrupted.
