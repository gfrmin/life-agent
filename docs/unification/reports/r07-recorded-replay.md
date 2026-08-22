# r07 — the recorded replay — 2026-08-22

> Opened on r06's QUESTION 2 (owner ruling **"start r07"**, 2026-08-22): close the attribution
> before any money is spent. Register entry: [`module-collapse-design.md`](../../module-collapse-design.md)
> §6.12 (the replace branch). Instrument: [`scripts/replay_audit.py`](../../../scripts/replay_audit.py),
> its ten criteria frozen in the docstring and committed **before** it read anything.
> Predecessor: [`r06-replace-branch.md`](./r06-replace-branch.md).

## STATE

- branch `r07-recorded-replay`, off `master` at `0a9666b`
- `uv run pytest -q` — **2609 passed, 35 deselected** (41 of them this checkpoint's, all new)
- `uv run ruff check src tests scripts` — **All checks passed**
- `uv run mypy` — **Success: no issues found in 217 source files**
- **THE READING IS PENDING.** This document is committed in this state, so that what the
  criteria said before the numbers existed is a matter of record and not of memory.

## DONE 1 — the ruling recorded at its own width

r06 asked three questions. "start r07" answers one, implies a second, and is silent on the
third; that is written down in [r06's RULINGS section](./r06-replace-branch.md#rulings-owner-2026-08-22--on-the-reading)
rather than paraphrased here. The load-bearing half is the implication: **nothing is bought,
and r06's criterion 8 is not reopened, not narrowed and not re-scored.** r07 may add a reading
beside it. It may not promote a site r06 left under its own floor — criterion 8 below encodes
that as a predicate, not as an intention, and a mutation that removes it turns a test red.

## DONE 2 — the criteria, frozen

Ten, in the instrument's docstring, mirrored into
[`bayesian-foundations.md`](../../bayesian-foundations.md) §14. They are not restated here;
what belongs here is why three of them are shaped the way they are.

**Criterion 2 (the pin) is longer than r06's because a replay can be wrong in more ways than a
record read can.** Four of its clauses were verified live before the criteria were written —
`src/` at HEAD is byte-identical to run 10's pinned sha (r05 and r06 changed nothing under
`src/`, so **master IS run 10's decision path**), the live corpus digest equals run 10's, the
utility elicitations sha equals run 10's, and the outcomes and gather logs truncate cleanly at
run 10's `created_at`. That last one is only correct because `run_eval` appends a run's edge
rows **after** the run: no question in run 10 conditioned on run 10's own rows, so the cut is
exact rather than approximate.

**Criterion 7(a) is the method's one real idea.** The counterfactual is not reconstructed
beside the decision path; it is **enacted through it**. The recording transport rewrites a
replace-site reply into the shape the deployed code *already* retires on — a null read at
S1/S4, a non-ok status at S3, a withheld mint at S5 — so RETIRE-NOT-REPLACE runs through the
real executor and the real daemon, and the guard under test is `executor._null_read` itself.
r06 had to re-derive its counterfactual arm through `core/lookup`'s decide, and criterion 6
exists because that substitution is the leading suspect for its 28% floor.

**Criterion 9(c) turns a limitation into a measurement.** A question the pin cannot serve
without spend is excluded by name — but *cold-at-start* and *cold-mid-loop* are counted apart,
because a derivation that goes cold after the loop began means run 10 never made that call (a
§18.9 record is written on success). That is evidence of divergence, not merely an absence.
Eviction and a failed run-10 call are the named alternatives.

## DEVIATION 1 — a rehearsal wrote into the live unified ledger, and criterion 2(f) is the fix

The first staging root symlinked every directory it did not rewrite, `ledger/` included. The
ledger mirror is a writer: on the first `/log_gather` it swept the *truncated* staging
calibration log and recorded that file's length as the live stream's resume offset. One field
of the owner's `MANIFEST.json` moved — `calibration.gather_outcomes.legacy_bytes`, from 85763
to 8286.

Assessed and repaired the same hour, with the numbers rather than an assurance: the unified
stream held **670 parseable events** against **670 rows** in the live legacy log, so nothing
had been appended and nothing lost. The repair was the mirror's own idempotent operation —
`migrate.sync_source` against the LIVE paths — which reported `written: 0` and restored
`legacy_bytes` to 85763. Nothing was hand-edited.

The instrument's fix is not a note. `NEVER_SYMLINKED` now names every directory a writer can
reach, the staging root creates them empty and owns them, `LIFE_AGENT_LEDGER_MIRROR=0` is set
before the re-exec, and `main()` REFUSES to read at all if `LIFE_AGENT_KB` is not the staging
root. A mutation that shrinks that set turns a test red — and the test names the directories
literally rather than iterating the constant, because the first version of it iterated
`NEVER_SYMLINKED` and would have shrunk happily along with it.

## DEVIATION 2 — the rehearsal that drew the opposite conclusion

Before the criteria were frozen, a one-question rehearsal of run 10's wrong-commit row reported
that **S1's haiku tier** collapsed the grounded channel from five observations to one and that
the deliberate edge never fired at all. That was a harness artefact:
`EX.DELIBERATE_TRANSFORM` is **not** in `EX.DEFAULT_TRANSFORMS` — the deployed caller opts it
in with `menu_transforms(curves)` — and the rehearsal passed the default menu. With the menu
the deployed caller actually builds, the same row reproduces run 10 exactly (terminal `report`,
`n_obs = 1`, the gold at 0.033, `instrument = deliberate@<opus>`) and the discarder is **S3**.

Recorded because it is the reason criterion 2(e) exists and the reason prediction (5) is
declared **not blind**: the expectation about that row was formed by a rehearsal, so it scores
nothing.

## DEVIATION 3 — criterion 7(b) amended before any reading, on a structural fact

§5's dedup-as-inference (`lookup.dedup_correlated`) clusters on an observation's **quote**.
`/extract` returns ABSTRACT observations by design — the body is string-blind — and
`_probe_corroborate` synthesises **one** abstract observation mapping the re-read value to a
candidate index. So the guard that makes joining safe cannot be applied to the thing a JOIN
would pool, and a §5-deduped JOIN is not readable by any instrument that stays off the decision
path.

That is a finding about §6.12's alternative rather than a shortfall of this checkpoint, and it
is reported as one. What the instrument reads instead is the **upper bound**: pooling with no
dedup, the most favourable case joining could ever have. If the bound is small the question
closes; if it is large, JOIN needs an instrument with a correlation key, which needs
decision-path code. `dedup_key_available` is a live predicate rather than a comment, so a wire
that ever grows the key turns the deployed rule back on by itself.

## DONE 3 — every load-bearing predicate verified RED by mutation, before the read

Twenty mutations, each applied to the instrument alone and reverted. r06 established the
practice; this run is what it is worth: **three predicates came back GREEN and were not covered
at all.**

| # | mutation | first pass | after |
|---|---|---|---|
| 1 | `site_of_call` reads the payload before the endpoint | RED | — |
| 2 | S4 and S5 swapped | RED | — |
| 3 | the first `/retrieve` counted as a grow | RED | — |
| 4 | a null read REPLACES at S1/S4 | RED | — |
| 5 | S3 gains a null-read guard | **GREEN** | RED |
| 6 | the rescue walk mints unconditionally | **GREEN** | RED |
| 7 | the discarder test drops "and the channel fell" | RED | — |
| 8 | `retire_reply` no longer satisfies the deployed guard | RED | — |
| 9 | retire at S3 keeps `status: ok` | RED | — |
| 10 | retire at S5 keeps the mint | RED | — |
| 11 | JOIN pools with a local dedup instead of the deployed rule | RED | — |
| 12 | `ledger/` symlinked at the live KB | **GREEN** | RED |
| 13 | the truncation cutoff made exclusive | RED | — |
| 14 | an undated row dropped silently | RED | — |
| 15 | the pin stops checking `loo` | RED | — |
| 16 | the pin stops checking the corpus digest | RED | — |
| 17 | the verdict's r06 gate removed | RED | — |
| 18 | the bar of 5 lowered to 0 | RED | — |
| 19 | the spend tripwire disarmed | RED | — |
| 20 | cold-mid-loop made indistinguishable | RED | — |

The three misses are worth naming because two of them are the same mistake in different
clothes. (5) and (6) were *fixtures that could not feel the mutation*: the S3 test used a reply
with no `read` field, so adding a null-read guard changed nothing on it; the S5 mint test did
not exist. (12) was worse — **the assertion iterated the very constant the mutation shrinks**,
so a smaller isolation set produced a smaller check and passed. That is r05's and r06's lesson
arriving a third time: an instrument's measures need their own adversary, and a test that reads
its expectation from the code under test is not one.

## DEVIATION 6 — one retrieval draw per question, shared across its arms

Added to criterion 7 before any reading. §6.13's sampler makes at least one question's
retrieval a lottery; an arm that differed from the deployed arm because it *drew differently*
would be a confound wearing a counterfactual's clothes. The draw is therefore memoised per
(question, breadth) and shared by that question's arms, so the arms differ because of the
rewrite and nothing else. Criterion 9(b)'s double run draws afresh, which is where instability
is looked for and where it belongs.

## DEVIATION 5 — criterion 9(b) narrowed before reading, with its argument

The double run covers the **deployed arm only**. Instability under §6.13 is a property of the
retrieval draw rather than of the arm — an unstable question is unstable in every arm — and the
deployed arm is what every attribution claim rests on, so a second deployed pass names exactly
the rows that must be withheld. Re-running the counterfactual arms would add cost and no
detections. They are read once, and that is stated wherever their numbers appear.

## DEVIATION 4 — four defects the three-question rehearsal exposed, before the read

The instrument was run on three questions before it was run on 104. It came back with one
question read, two excluded, and four things wrong with itself.

1. **Every cold arm read as "cold-at-start".** `replay` returned the tape, so the assignment
   that would have delivered it never happened on the raising call and `cold_kind` saw an empty
   list every time. The distinction criterion 9(c) is *built on* — cold-mid-loop means run 10
   never made that call — was silently dead. The caller owns the tape now.
2. **A blanket deliberate preflight over-excluded.** A question was dropped because its
   deliberate cache was cold even when its loop would never have scheduled the edge. The check
   moved into the transport, at the endpoint — but `run_pass` wraps that post in
   `except Exception` and reads a raise as an infrastructure fail-open, so an ordinary refusal
   there would have been swallowed and recorded as evidence. `ColdDeliberate` therefore derives
   from **`BaseException`**, which passes straight through the executor's handler. A question is
   now excluded for a cold edge only when the edge was actually scheduled.
3. **A cold counterfactual arm killed the whole question.** q2-011 — the blocking row — read
   perfectly on the deployed arm and was thrown away because the *retire* arm went cold.
   Exclusion is per arm now, with arm coverage published beside every counterfactual number.
4. **The r06 gate encoded my re-reading of r06's floor instead of r06's verdict.** It listed
   S1, S4 and S5 as "above floor" — which is what r06's *bound* says. r06's published criterion
   8 bought **S1, S3, S4 and S5** and left S2 NOT READ, and that verdict is what the owner ruled
   closed. `R06_BOUGHT` now mirrors the verdict; a re-reading of the bound belongs in prose,
   never in the gate.

**And (3) is a result, not only a defect.** Enacting a counterfactual walks paths the pinned run
never took, so the retire and join arms reach cold derivations far more often than the deployed
arm. That is the price of criterion 7(a)'s method, and it is the reason r06 reconstructed rather
than enacted: **a reconstructed counterfactual is free and inherits a layer gap; an enacted one
has no layer gap and costs money.** How much of each arm survives at $0 is published in the
reading rather than assumed.

## THE READING

**PENDING.** Nothing below this line exists yet.

## REFUSED

- No decision-path code (criterion 10). Nothing under `src/` changes in this checkpoint; the
  commit gate refuses if `src/` is dirty.
- No re-scoring of r06's criterion 8, in either direction (owner ruling).
- No §5-deduped JOIN, for the structural reason in DEVIATION 3 — the bound is published in its
  place, labelled as a bound everywhere it appears.
