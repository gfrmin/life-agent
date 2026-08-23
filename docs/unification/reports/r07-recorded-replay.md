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

## DEVIATION 7 — criterion 9(d)'s guard fired twice, once wrongly and once at its stated limit

The first render of pass 1 was refused by the instrument's own leak guard: golds of one to
three characters matched integers the render itself computes — `n_obs=7` contains a `7`, and a
word boundary does not help because `=` is not a word character. That was a false positive and
it cost a full 35-minute pass, because the rows lived only in memory when `render` raised. Two
fixes, both to the instrument and neither to the criterion: `leak_check` now runs two channels
(a DISTINCTIVE value is a leak anywhere in the report; a short or numeric value is checked only
against the free-text channels — pin notes, exclusion lines, site descriptions — with the limit
stated in the function rather than silently), and `audit_rows` dumps its rows to the yaml
BEFORE `render` runs, with `--render-only` to re-render from the dump, so a render defect now
costs seconds.

The guard fired a second time on pass 2's render and this time it was operating exactly at its
stated limit: a pass-2-only row carries a one-character numeric gold, and that digit occurs
literally in the render's own pin-note boilerplate. The refusal was accepted rather than the
guard weakened again — **pass 2's artefact of record is its rows dump**
(`eval/replay/audit-gate-20260821T094545-pass2.yaml`), and every pass-2 number in the reading
below is computed from it.

## DEVIATION 8 — the transport must never invent a reply shape the deployed code distinguishes

The recording transport coerced a null `/route` reply to `{}`. The executor branches on
`route is None`, so the coercion sent it down the routed path into a `KeyError` on a field
only a real route carries. Fixed with a null passthrough and a hermetic test. Recorded because
it is the transport-side twin of DEVIATION 4's lesson: the instrument sits between two
components that speak a richer protocol than the instrument assumed.

## DEVIATION 9 — the §18.9 warm-through: a $0 replay is not side-effect-free

Criterion 2(f)'s write isolation covers the KB and the ledger mirror. The §18.9 derivation
store under the pkm root is the LIVE store, shared with the deployed path by design — and a
replay walk that reaches a composed stage whose parts are all warm computes it at zero spend
and RECORDS it. **31 records were written into the live store during the 2026-08-22 passes**
(23 `joint_extract`, 4 `synthesize`, 4 `narrative_answer`). All are write-once and
content-addressed, so nothing was overwritten and — by the store's own key-determinism
contract — nothing recorded differs from what the deployed path would have recorded at the
same key. The store is not damaged. What the warm-through does move is **coverage**: whether a
question reads or goes cold is now pass-order-dependent, and the reading's criterion 9(c)
section carries the consequence — a third named alternative for "cold-mid-loop" beside cache
eviction and a failed run-10 call.

## DEVIATION 10 — one reader at a time

Before pass 1, two concurrent invocations shared a staging root that `build_staging_kb`
deletes and rebuilds — the second invocation destroyed the first's KB mid-read. The runner now
takes a non-blocking `flock` and REFUSES to start while another read holds it. The cause was
operational (two waiter shells watching the same run), the fix is structural.

## DEVIATION 11 — the volume failure between the passes

Pass 2's first attempt died at 23:09 on 2026-08-22 with an I/O error inside a §18.9 lookup:
the KB's backing disk dropped off the USB bus mid-read, nineteen minutes after pass 1's
artefacts were written. Nothing was written to the volume after the failure. The disk was
physically reconnected on 2026-08-23, the filesystem journal replayed clean, and both pass-1
artefacts survived byte-intact — as did every pass-1 number, because the runner logs to the
root disk and the aggregations had been computed while the volume was still readable. Pass 2
then re-ran to completion. The crashed attempt's 59-row partial log is preserved out of tree
and enters the reading only as the *supplementary third draw* in criterion 9(b), labelled as
such wherever it appears.

## THE READING

*Pass 1 read 2026-08-22 (three arms, 67 of 104 questions); pass 2 read 2026-08-23 (deployed
arm only, 73 of 104). Spend across every pass: **$0** — the tripwire and the refusing client
held. The pin verified on every clause both days; `src/` unchanged throughout (criterion 10),
so the tree replayed IS run 10's decision path.*

### Criterion 6 — the floor was the decide layer

Fidelity is **66/67** in pass 1 and **72/73** in pass 2, and the divergent row is the SAME row
both times (q2-017) — a stable ~1.5% bound on every claim below, not a noise floor. The
control is exact: on the 9 replayed questions where no site fired the replay reproduces the
recorded terminal **9/9**, where r06's reconstruction of its no-edge control disagreed at 28%.
Sharper still: r06's 8 disagreeing control rows are named in its own yaml; 7 of the 8 replayed
here (the eighth went cold), and the replay agrees with the record on **7/7**. The 28% was
`core/lookup`'s decide standing in for the daemon's — the decide LAYER, exactly as criterion 6
framed it. Consequence, stated as the criterion requires: r06's per-site excesses were
understated by a layer gap this instrument does not have; with the gap removed, the direct
counterfactuals below still read every site under the bar.

### Criteria 4–5 — the attribution, from the payload

Nineteen rows carry an attributed discarder in pass 1: **S1 on 10** (q2-013, q2-031, q2-038,
q2-040, q2-042, q2-064, q2-072, q2-081, q2-089, q2-103) and **S2 on 9** (q2-005, q2-014,
q2-044, q2-049, q2-054, q2-056, q2-061, q2-096, q2-102). **S3, S4 and S5 discard nothing on
any replayed row.** The double run of criterion 9(b) then withholds 7 of S2's 9 — four
unstable in committed n_obs across the passes, three read in pass 1 but cold in pass 2 — so
the confirmed attribution is **S1 ×10, S2 ×2** (q2-014, q2-056), with every S1 row stable
across both passes. r06's `extract@<opus>` ambiguity class is closed: resolved by payload,
the opus-tier volume is S1's cascade, not S4's re-extraction (S1's opus tier fires on 44
questions against S4's 34).

A grounded channel was zeroed outright on **7 questions — S1 did 6** (q2-001, q2-011, q2-027,
q2-055, q2-077, q2-082), **S3 did 1** (q2-054). On the blocking row, q2-011, the trace is
`base:5 → S1:0 → S1:0 → S3:1 → S1:1 → S4:1`, committed n_obs 1, terminal `report`,
reproducing run 10 exactly and **stable across the double run**: S1's first corroborate tier
zeroes the five-observation grounded base, and the deliberate edge then re-mints a
one-observation channel carrying the wrong leader. The criterion-5 rule names no discarder on
this row and that is the rule working as frozen: the channel fell to 0 and then ROSE to the
committed 1, so no firing satisfies "fell to the committed size". The trace names what the
mechanical rule cannot, and the limitation is published here rather than patched after the
fact.

**The centre of the reading is what the zeroing means for §6.12's counterfactual.** An empty
non-null reply is a *disagree*, and retire-not-replace explicitly leaves disagreeing reads
untouched — it retires only null reads. So the harm that actually shows up — S1 zeroing a
grounded channel on a disagreeing re-read — sits on a path the registered counterfactual
CANNOT see. The retire arm's numbers below are the measurement of that blindness.

### Criteria 7–8 — the counterfactuals, and the verdict beside r06's

Arm coverage first, as criterion 9(c) requires: the deployed arm read 67 of 104, the retire
arm 40 of those 67, the join arm 66 of 67 — an enacted counterfactual walks paths the pinned
run never took, and the retire arm pays for it in cold derivations.

**RETIRE (enacted through the deployed guards): reach 1 — 0 repairs, 1 regression.** On 39 of
its 40 rows the arm changes nothing; on the one row it reaches, it makes the answer worse.
Retire-not-replace is a no-op on the measured harm, exactly as the disagree-path argument
above predicts.

**JOIN (the upper bound, computed not enacted): reach 13 — 10 repairs, 2 regressions, 1
neutral** on 66 rows. The join numbers are the ARM's, shown in the artefact against each
site's exposure set — they do not add across sites. The bound is labelled everywhere it
appears: §5's dedup key is not on this wire (DEVIATION 3), so every pooled copy counts as an
independent witness and 10 repairs is the most joining could ever deliver, not what a
deployable join would.

**The verdict, published beside r06's and re-scoring nothing:** every site reads
**KNOWN-AND-UNCOVERED**. S1's retire excess over r07's own floor is 1.0 rows, S3's 1.0, S2,
S4 and S5 0.0 — all under the frozen bar of 5, and the floor itself is **0%** (0 of 9 control
rows). S2 and S3 are additionally gated by the owner's ruling: r06 left them at or under its
own floor and its criterion 8 is not reopened. **Nothing is bought.** The deployable question
this reading leaves is not a retire rule at all: it is whether a correlation key can be put on
the wire so a §5-deduped JOIN becomes readable — decision-path code, its own pre-registration,
outside this checkpoint by criterion 10.

### Criterion 9(b) — the double run, plus a third draw by accident

59 questions read in both completed passes. **11 are unstable and every one differs in
committed n_obs only** (by 1–3 observations): q2-006, q2-017, q2-026, q2-044, q2-054, q2-060,
q2-061, q2-071, q2-100, q2-102, q2-105. No question changed its terminal action and none
changed its firing order between the completed passes. The crashed attempt's 59-row prefix —
a third independent draw — adds q2-066 and q2-076 on committed n_obs and **q2-077 on firing
order** (the only order wobble seen anywhere, S2 and S4 exchanging places), none of them
attribution rows, so the confirmed set above survives all three draws. Coverage itself flaps:
8 questions read in pass 1 went cold in pass 2, 14 read in pass 2 were cold in pass 1
(warm-through, DEVIATION 9, explains the second direction but not the first). §6.13's witness
(q2-036) read in neither pass. Everything named here carries no attribution claim.

This is §6.13 measured at commit granularity rather than at the top-20: at fixed corpus, fixed
`src/` and fixed logs, **14 of 104 questions wobble in what the deployed path commits** across
three draws, and 22 flap between readable and cold. r06 measured one lottery question at the
retrieval set; the committed evidence is a wider tail than the set instability suggested, and
the register entry is updated with this incidence.

### Criterion 9(c) — what "cold" turned out to mean

All 113 pass-1 arm-exclusions are **cold-mid-loop; cold-at-start never occurred.** The frozen
criterion read cold-mid-loop as evidence of divergence (run 10 never made that call), with
eviction and a failed run-10 call as the named alternatives. The double run adds a third and
it changes the reading: coverage flapped in BOTH directions between passes at fixed corpus —
so a cold derivation can also mean *this pass drew a retrieval set run 10 did not*, and the
warm-through means the next pass may not reproduce it. Coldness is a property of the
(draw, store-state) pair, not of the question. The 37 deployed-arm exclusions are therefore
NOT read as 37 divergences from run 10; they are the overlap of the draw lottery with a store
whose warmth moves under the instrument's own feet, and no stronger claim survives.

### Predictions scored

1. **CONFIRMED.** Fidelity on r06's disagreeing control rows: 7/7 = 100% ≥ 90%. The floor was
   the decide layer.
2. **REFUTED, decisively.** JOIN out-reaches RETIRE 13 to 1. The blind expectation was that
   enacted retirement would reach further than pooling; the measured shape is the opposite,
   because the harm rides the disagree path retirement cannot see.
3. **CONFIRMED.** S4's exposure (34) is strictly under S1's opus-tier exposure (44), resolved
   by payload.
4. **CONFIRMED.** 11 questions besides the §6.13 witness prove unstable across the mandated
   double run (the witness itself read in neither pass).
5. **Scores nothing, as declared** — and the rehearsal-informed expectation was wrong anyway:
   it named S3 as the discarder taking the channel 5 → 1 with S4 minting the competitor. The
   read shows S1 zeroing the channel (5 → 0), S3 re-minting the one-observation competitor,
   and S4 size-preserving. Recorded as the third instance of this programme's oldest lesson:
   an expectation formed by an instrument's defect survives until a better instrument reads.

### What this closes and what it opens

Closed: r06's QUESTION 2, in full — the firing order is attributed (S1 ×10, S2 ×2 confirmed;
S3/S4/S5 discard nothing), the JOIN counterfactual is read as an upper bound (10 repairs / 2
regressions), and the 28% floor is diagnosed (the decide layer). The blocking row's mechanism
is named and double-run-stable. Nothing is bought, r06's criterion 8 stands untouched, and
the deployment block's premise is sharpened: the row's wrong commit needs BOTH S1 to zero the
grounded channel on a disagree AND the deliberate edge to re-mint the competitor into the
vacuum.

Opened, for the owner rather than by default: (a) the JOIN-with-a-correlation-key fix — the
only counterfactual that touches the harm, needs decision-path code and a frozen
pre-registration of its own; (b) §6.13's commit-granularity footprint (14 wobbling rows, 22
coverage flaps) as a standing noise floor under every gate reading until one of the register's
three named fixes is priced; (c) the §18.9 warm-through as an instrument-design constraint for
every future $0 replay.

## REFUSED

- No decision-path code (criterion 10). Nothing under `src/` changes in this checkpoint; the
  commit gate refuses if `src/` is dirty.
- No re-scoring of r06's criterion 8, in either direction (owner ruling).
- No §5-deduped JOIN, for the structural reason in DEVIATION 3 — the bound is published in its
  place, labelled as a bound everywhere it appears.
- The 9(d) guard was not weakened a second time: pass 2's render stays refused and its rows
  dump is the artefact of record (DEVIATION 7).
- No attribution is claimed on any row the double run names — including the seven S2 rows
  withheld, although withholding them costs the site most of its named evidence.
- No mechanism is claimed for the 37 deployed-arm exclusions. "Divergence from run 10" was the
  frozen reading and the double run weakened it (criterion 9(c) section); a weaker claim is
  published instead of a defended one.
