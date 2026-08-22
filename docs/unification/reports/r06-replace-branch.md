# r06 — the replace branch — 2026-08-22

Opened on r05's PROPOSED and the owner's rulings of the same day (r05 RULINGS 1–4). The
subject is the mechanism r05's DONE 4 *named* rather than suspected: at five sites the
executor's enactment loop lets a probe's reply REPLACE the grounded channel instead of joining
it, and run 10's one wrong commit was taken by a view that had done exactly that.

This report is append-only. Nothing under `src/` moves in this checkpoint — the criteria are
frozen and committed before the instrument reads anything, and a commit gate refuses if the
decision path is dirty.

## STATE

`e441f50` (master, clean at open). Suite, lint and types are re-run by the commit gate below
and their output is pasted there rather than summarised.

The rulings this checkpoint opens under, taken before any of it existed:

1. **The deployment block is KEPT and RE-POINTED at §6.12.** Its premise — waiting on the
   carrier-identity checkpoint — was refuted by r05. The tree it blocks still commits a row
   wrongly, which is what the block was for.
2. **§6.11 BUILD licenses known-and-uncovered, not a fix.** The grouping bound (both
   directions) and the 37/37 cross-surface conservatism are recorded in the entry; the named
   fix is retired as refuted; no decision-path code. The next run's budget comes here.
3. **M1 is ACCEPTED and closed** (r04 RULING 3 released; the release is appended to r04, which
   is append-only). M1.5, the coverage census, is unblocked.
4. **r06 is scoped to EVERY replace/override site**, not to the registered
   NULL-as-disagreement hypothesis alone — on r05's own lesson that an instrument written
   around the presumed fix measures the fix and not the defect.

## DONE 1 — the register entry, before any measurement

`docs/module-collapse-design.md` **§6.12 — the replace branch: a view that DISCARDS a grounded
channel instead of joining it.** It enumerates the five sites **from the code**, each with the
guard that decides whether the replace is taken:

| # | site | guard on the replace | what is discarded |
|---|---|---|---|
| S1 | the `corroborate_*` tiers | `not _null_read(cr)` | `obs`, `era` |
| S2 | the retrieval grows | `bool(n_ext["candidates"])` | `hits`, `recency`, `ext`, `candidates`, `cand_comp`, `obs`, `rho`, `era` |
| S3 | the `deliberate` edge | `status == "ok"` **only — no null-read guard** | `obs`, `era` |
| S4 | `re_extract_strong`, in-loop | `not _null_read(cr)` | `obs`, `era` |
| S5 | the k=0 rescue walk | reached only with nothing grounded | nothing — it mints |

The entry's sharpest edge is the **asymmetry**: S1 and S4 were taught on 2026-08-18 that a
joint re-read naming nothing is *absence* of evidence and must not erase a grounded posterior.
S3 was not, and its docstring says so outright — an empty ok reply COLLAPSES the channel by
design, on the reading that NOT_IN_CORPUS from an independent searcher is evidence for NONE.
Whether that is right has never been measured, and the row that failed run 10 committed
through S3.

The population is not one row. Run 10 supplies the first witness; the registered **n_obs=0
cluster** supplies a population — 17 of 19 questions carrying candidates at *exactly* uniform
credences, which is the signature of a posterior computed over an empty observation set, with
the gold still on the lattice in 14 of them.

*Also recorded in §6.11, by RULING 2:* the carrier entry becomes a standing
known-and-uncovered source, its candidate fix retired as refuted, and its two surviving
findings (the grouping bound in both directions; the load-bearing cross-surface consistency of
the declared key) written down as what it now stands for. Its "the tell" paragraph is corrected
in place by the appendix rather than deleted: on this corpus the two duplicate-witness rules
agree wherever both can see, so the conflict it described is real in principle and unobservable
here.

## DONE 2 — the criteria, frozen before the instrument reads

Ten criteria live in `scripts/replace_audit.py`'s module docstring — the authority, so they
travel with the instrument — and are mirrored in the §14 pre-registration. In brief:

- **C1 scope** — the five sites above, from the code. **S2 emits no attributed edge event**, so
  its exposure is NOT READABLE from these records and is reported as *unmeasured*, never as
  zero. The `extract@<opus>` spelling is shared by S1's opus tier, S4 and S5, so it is reported
  as an **ambiguity class** the records cannot resolve; S5 is separable because it is reached
  only when nothing grounded.
- **C2 exposure** — per site. Exposure 0 reads as *untaken*, never as *clean*.
- **C3 channel loss** — the grounded channel's `n_obs` against the committed posterior's.
- **C4 delivered reach** — the counterfactual is **RETIRE-NOT-REPLACE**: the probe retires
  fail-open and the grounded channel stands, which is exactly what S1 and S4 already do on a
  null read. It is a deployable rule, not an invented one. Reach counts questions whose
  committed action differs.
- **C5 the split** — REPAIR / REGRESSION / NEUTRAL against the run's own gold, published as a
  triple. The frozen text left the withholding→commit direction unnamed; it is fixed *before*
  the read (correct commit ⇒ repair, wrong commit ⇒ regression) and the fix is disclosed here
  rather than chosen after a result.
- **C6 conservatism** — which side the deployed rule falls on, both directions counted.
- **C7 the asymmetry** — amended before reading on a *feasibility* fact: the eval writer emits
  an edge row only when a firing carried both a value and a self-report, so a reply that named
  nothing leaves no row. The asymmetry is therefore read off a conjunction of the run's own
  records — `instrument` naming deliberate (only that branch sets it), no `deliberate@` outcome
  row, terminal `n_obs` 0, base `n_obs` > 0. That conjunction is also the n_obs=0 cluster's own
  description, so C7 doubles as the first test of whether that cluster **is** S3.
- **C8 the verdict**, mechanical per site: reach ≥ 1 with repairs > regressions ⇒ BUILD the
  guard **and** buy one isolated run under §6.10; reach ≥ 1 with repairs ≤ regressions ⇒
  REFUSE; reach 0 at exposure ≥ 5 ⇒ known-and-uncovered; exposure < 5 ⇒ NO-GO. The bar of 5 is
  inherited from r05 so the two checkpoints are comparable.
- **C9 the instrument's own limits** — (a) only ONE arm is recomputed: the deployed arm is
  **read** from the run's terminal decision row, so r05's 70-of-102 layer gap applies to the
  counterfactual alone, and it is bounded by a **direct control** (on questions where no edge
  fired the terminal *is* the base channel, so agreement there measures the layer gap on this
  very run) rather than inherited. Both arms are graded by the same matcher, and matcher-vs-
  judge flips on the deployed arm are named. (b) The JOIN counterfactual is **not read here** —
  the probe's observations are not in the records and reading them needs a live bridge replay;
  it is named as the escalation. (c) Any question needing spend is excluded by name.
- **C10 no decision-path code.**

**Blind predictions, recorded before the read:** (1) S3 shows the largest channel loss per
firing, being the only site with no null-read guard. (2) The run-10 wrong commit is an S3
firing with loss ≥ 3. (3) Total exposure across the readable sites is ≥ 20 on 102 questions.
(4) S3's delivered reach is ≥ 1 and its repairs exceed its regressions. (5) S2 has exposure > 0
but delivered reach 0 — except that C1 says S2's exposure is unreadable here, so prediction (5)
is recorded as **unresolvable by this instrument** and will be scored only if the escalation
runs.

**Named risks, recorded before the read:** the instrument mirrors the loop's branch conditions,
and a mis-mirror produces a confident wrong number — which is precisely how r05 shipped three
measure defects. Two answers to that, both in place before the reading: every mirror is
**imported from the decision path** (`EX._TIER_MODEL`, `EX._RE_EXTRACT_MODEL`,
`EX._DELIBERATE_MODEL`, `EX.extract_edge`, `DL.instrument`, `RET.retrieve_set`) rather than
hand-copied, with a test that fails if a tier is added and not mapped; and every load-bearing
predicate was **verified RED by mutation before the reading** (below). Second risk:
retire-not-replace is a **bound, not presumptively a better rule** — retiring a probe that
legitimately corrects a wrong grounded channel is a regression, and C5 exists to see it.

### The RED verification, done before the read and not after

r05's DEVIATION 1 was that its instrument was written before its tests and three measure
defects survived to a reading. Here the tests were written first and the module did not exist
(`ModuleNotFoundError` on collection). Because a whole-file collection error is a weaker RED
than a per-behaviour one, each load-bearing predicate was then mutated to its plausible-wrong
form and the specific test confirmed failing, with the file restored and green after each:

| mutation | test that caught it |
|---|---|
| the `extract@<opus>` ambiguity class collapsed to S1 alone | `..._ambiguity_class_not_a_guess` |
| the withholding→commit direction dropped from the split | `..._becomes_a_correct_commit_is_a_repair` |
| C7's conjunction weakened (the no-gradeable-row conjunct removed) | `..._needs_every_conjunct` |
| the deployed leader read as the first candidate, not the argmax | `..._read_off_the_recorded_decision_row` |
| the verdict buying a run on a repairs/regressions tie | `..._refuses_when_regressions_do_not_lose` |
| the decision loader keeping the FIRST row per question, not the terminal one | `..._last_row_per_question_wins` |
| the edge loader keeping non-`eval_edge` graders | `..._group_by_eval_id_and_keep_firing_order` |
| the site table hand-copied with a tier dropped | `..._derived_from_the_executor_module` |

27 tests, all green with the file restored.

## DONE 3 — the reading

`$LIFE_AGENT_KB/eval/replace/audit-gate-20260821T094545.{md,yaml}`, $0, 102 questions read and
2 excluded by name (both for want of a terminal decision row in this run). Nothing was warmed:
the client refuses any cold derivation and its question is named.

### Criteria 1–3 — exposure and channel loss

| site | exposure | rows with loss | observations discarded | per firing |
|---|---|---|---|---|
| S1 the `corroborate_*` tiers | 26 | 8 | 21 | 0.81 |
| S2 the retrieval grows | **unreadable** | — | — | — |
| S3 the `deliberate` edge | **68** | 15 | 34 | 0.50 |
| S4 `re_extract_strong` | 12 | 4 | 7 | 0.58 |
| S5 the k=0 rescue walk | 12 | 4 | 7 | 0.58 |

27 questions show a positive channel loss and **59 grounded observations are discarded across
the battery**. S2's exposure is unmeasured as C1 declared it would be, never zero. S1, S4 and
S5 share the `extract@<opus>` spelling and their rows are counted under all three, with the
overlap stated rather than resolved by a guess.

**S3 fired on 68 questions and left a gradeable edge row on none of them.** That is not a
finding about deliberate's answers; it is a fact about the records, and it has two consistent
causes the records cannot separate (the firing named nothing gradeable, or a cross-run dedup
had already graded its §18.9 lineage). Exposure counts the firing either way.

### Criteria 4–6 — delivered reach, the split, and the side it falls on

Delivered reach **23 of the 73 questions where a site fired** — repairs **12**, regressions
**11**, neutral 0, ungradeable 0. The deployed rule is conservative on 13 and aggressive on 9.

**Criterion 9(a)'s control is what qualifies all of it.** On **29** questions no site fired at
all, so retire-not-replace is provably a no-op there — and the two arms still differ on **8**.
That is a **28% noise floor**, measured on this very run rather than inherited from r05:

| site | reach | the floor alone predicts | excess |
|---|---|---|---|
| S1 | 11 / 26 | 7.2 | **+3.8 rows** |
| S3 | 19 / 68 | 18.8 | **+0.2 rows** |
| S4 | 4 / 12 | 3.3 | +0.7 rows |
| S5 | 4 / 12 | 3.3 | +0.7 rows |

**S3 — the site with no null-read guard, the site that took run 10's wrong commit — has
delivered nothing this instrument can distinguish from its own layer gap.** Criterion 8,
applied mechanically as frozen, nonetheless reads **BUILD+PRICE on S1, S3, S4 and S5** and
NOT READ on S2. The criterion is left standing exactly as written. Renegotiating a criterion
once its numbers are in is the failure this programme exists to avoid; publishing the bound
beside it is the alternative, and that is what the table above is.

### DONE 4 — the witness is repaired, and the attribution is not available

On run 10's wrong-commit row the deployed arm **reports at n_obs = 1** on the competitor; the
counterfactual **reports at n_obs = 5 over 4 documents** on the gold. Channel loss 4,
classified a **REPAIR**, side `none` (both arms commit, so it is not a conservatism trade).
Retiring the replace fixes the row the deployment block is pointed at — which confirms RULING
1's target is real.

What the records cannot supply is **which** site did it. Four fired on that question: the
`extract@<opus>` spelling puts S1, S4 and S5 in one ambiguity class, and the deliberate firing
is recorded only in the terminal decision row's `instrument` field. The two record streams
carry no ordering between them, so the firing order is not recoverable and is not guessed.

### DONE 5 — criterion 7 retires a suspicion the ledger has carried since 2026-08-18

The S3-collapse signature fires on exactly **one** question — and that one has a graded
`deliberate@` row in another run, so a cross-run dedup explains its absence here. **Zero rows
survive as genuine null-read collapses.** Two consequences, both stated as findings rather
than as absences: the S1/S4-versus-S3 asymmetry is **structural-only on this corpus's
records**, and the empty-ok collapse is **not** what produced the registered n_obs=0 cluster.
That cluster keeps its entry and loses its leading suspect.

### The predictions, scored

| # | prediction | outcome |
|---|---|---|
| 1 | S3 shows the largest channel loss per firing | **falsified** — S1 discards 0.81 per firing, S3 0.50 |
| 2 | the wrong-commit row is an S3 firing with loss ≥ 3 | held — loss 4, with S3 among four sites |
| 3 | total exposure across readable sites ≥ 20 | held — S3 alone is 68 |
| 4 | S3's reach ≥ 1 with repairs > regressions | **held as stated, empty in content** — 19 reach, 12 > 7, excess over the floor +0.2 rows |
| 5 | S2 exposure > 0 with reach 0 | unresolved, exactly as pre-registered — S2 is unreadable here |

## DEVIATION 1 — three defects in the instrument's measures and a fourth in an interpretation

All four were caught before a verdict was published, and all four are published rather than
folded away. This is the same failure mode r05 recorded; what changed is when it was caught.

1. **Exposure read off the attributed-edge stream alone** (found in a 3-question smoke test,
   before the first full reading). The eval writer emits an edge row only when a firing carried
   both a value and a self-report, so S3 read as **untaken on the one question it decided**.
   Fixed by `sites_for`, which unions the edge stream with the terminal decision row's
   `instrument` field — a field only the deliberate branch ever sets.
2. **The control set keyed on the same stream** (found in the first full reading). 68 of its 76
   "control" rows had S3 fire: the control was measuring precisely what it existed to exclude.
   It read **56/76 = 74% agreement**; the true control set is **29 rows at 21/29**, a 28% floor.
   Both quantities are published. Fixed by `is_control`, which keys on the site union.
3. **A rate-against-rate comparison** that labelled 19/68 "above" 8/29 — 27.9% against 27.6%,
   a third of a percentage point dressed as a signal. Replaced by `excess_over_floor`, which
   states the same thing in rows.
4. **A dedup confound in criterion 7's interpretation.** `run_eval._fresh_edge_rows` dedups
   this run's edge rows against the **whole prior log's** §18.9 lineage, so a warm-replayed
   deliberate answer already graded in an earlier run leaves no row here. Absence of a row is
   therefore not evidence of a null read. Criterion 7's count is published as an **upper
   bound**, split by whether any run holds a graded `deliberate@` row for that question — and
   the split is what turns 1 into 0.

Corrections (1) and (2) are the same defect twice, which is the honest way to describe it: the
first fix did not carry through to the control because the control was written from the same
wrong assumption.

## DONE 6 — the idempotency double-run, and what it found instead

Two identical invocations of the audit on the same records disagreed: one question flapped in
and out of the exclusion set, moving S1's exposure 25↔26, reach 10↔11, regressions 4↔5 and
excess +3.1↔+3.8. No verdict changed. The reading of record is the 102-question one; the
101-question variant is recorded here rather than discarded.

The cause is not the audit, and it is **registered as `docs/module-collapse-design.md`
§6.13**: *a declared total order cannot restore determinism when the tie block is larger than
the over-fetch window — the window itself is the sampler.* R2 imposes the declared key on the
rows the over-fetch **returned**, and pkm's FTS ends `ORDER BY score DESC` with a `LIMIT`, so
which of a tied population those rows are is settled before the key runs. §14's "quantising
takes both to zero" was measured at k=80 (an over-fetch of 320). At the arm's own k=20 the
window is 80 rows, and on **1 of 104** questions those 80 carry five distinct quantised scores
with **73 sharing one** — the top-20 is four stable hits plus sixteen drawn from a tie block
larger than the window. Five consecutive calls returned five different chunk sets differing by
half the top-20; the other 103 questions are stable across three calls each, at 0 chunks of
symmetric difference. A tail, not a regime, but a live one: on that question the arm's first
pass is a lottery and every derivation keyed on the retrieval set is a lottery with it.

It is invisible to 7.2 (the fixture set tapes the derivation cache and never executes
`retrieve_set`) and invisible to a gate run (one question, and a run records a decision, never
the draw behind it). It took running the same read twice on purpose.

## REFUSED

- **No decision-path code.** C10 forbids it before a reading, a commit gate refuses if `src/`
  is dirty, and §6.13 — found here and live — was registered rather than patched, for the same
  reason.
- **The criterion was not renegotiated after its numbers.** S3's mechanical BUILD+PRICE stands
  in the report exactly as the frozen rule computes it, with the floor published beside it.
- **No gate run was bought.** The mechanical verdict buys four; the evidence supports at most
  one, and which one is not determinable from these records. Buying four would be spending to
  avoid a decision.
- **The site attribution was not guessed.** The ambiguity class is reported as a class.

## QUESTIONS

1. **What to do with a mechanical BUILD the bound contradicts.** Criterion 8 buys a run on four
   sites; the floor says only S1 shows an excess worth the name (+3.8 rows), and S3 — the one
   the investigation was aimed at — shows +0.2. Options: **(a)** buy one isolated run on S1's
   guard alone, the only site with an excess, and leave the rest known-and-uncovered
   (recommended — it is the one place the instrument distinguishes signal from its own gap);
   **(b)** buy nothing and escalate first (below), on the ground that a 28% floor makes any of
   these numbers a poor thing to spend $3–4 confirming; **(c)** honour the criterion literally
   and buy four.
2. **Whether to close the attribution before spending.** The blocking row IS repaired by
   retire-not-replace, but four sites fired on it. The escalation criterion 9(b) already names
   what would settle it: a **bridge replay that records the firing order per question and the
   probe observations**, which converts the ambiguity class into an attribution *and* unlocks
   the JOIN counterfactual that C9(b) excluded here. It needs a live stack, not a gate run, and
   is $0 if the replay is warm.
3. **§6.13's disposition.** One question in 104, live on the decision path, invisible to both
   oracles. Its own checkpoint, folded into M1.5's coverage census (which this checkpoint's
   RULING 3 unblocked), or left standing as registered?

## PROPOSED

**r07 — the recorded replay**, answering QUESTION 2 before any money is spent: replay run 10's
questions against a live bridge with the firing order and the probe observations recorded, so
that (a) the `extract@<opus>` ambiguity class becomes an attribution, (b) the JOIN
counterfactual becomes readable, and (c) the 28% floor can be diagnosed rather than merely
published — on the control rows the two arms differ at identical `n_obs`, which points at the
decide layer and not at the evidence. Same shape as this checkpoint: frozen criteria first, no
decision-path code until they exist.
