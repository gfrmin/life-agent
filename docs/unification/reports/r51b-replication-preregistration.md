# r51b — the 1×-n replication on ATM-Bench's email subset — PRE-REGISTRATION

**Frozen before any build, stack or engine work** (`M-3`). Opened on the owner's ruling of
2026-09-06 (`conferrals/r51-successor-conferral.md` RULING → `A-13`): after `r51` closed on its
X1 KILL, build the pre-registered instrument on the **198** gradeable questions the recon found,
re-cut the cells to that known n, read once, and open the corpus-pooling recon afterwards.
**This document inherits `r51-external-corpus-preregistration.md` verbatim wherever it is
silent** — population, gradeability, verdict path, grader-error ceiling, folds, Ū source, tree
pins, the "never values" scoping, X2, X3a–e, X5–X10, the consequence branches' shape, the build
list and the one `src/` docstring clause — and restates only what the known sample size
changes. Amendments after this commit are dated and blind (the log at the end).

## The question, honestly sized

Does the engine's held-out `p1` on a public corpus the owner did not author read as the same
pooled shape `r49` found on the owner's — credence flat across leader-credence cells, truth
rising with them? **At ~1× `r49`'s n, not 10×** (`M-35`): one executor pass posts at most one
decision per question, so the verdict supply here is ≤ 198 ticks against `r49`'s 238. A
CONFIRMED here is **corroboration on a second corpus, never power**; it cannot answer
proplang#26's small-n objection and the report and any comment will say so in those words.
The by-products are the reason the owner chose this over a hold: the first reliability
diagram and ECE for A-CAL (`DR-DECISION-1` §2.1), the A3 differential quoted under `M-34` on a
public corpus, and the `u_wrong` sensitivity curve with implied bar, coverage and selective risk
(X7 — the reading the owner's own survey asked for on "ATM-Bench emails").

## What the recon fixed before this was frozen (facts, not results)

Read in `r51-external-corpus.md` §2, all counts: 381 email-only QA; **198** `number`-typed
(gradeable), 182 `open_end` (14 of them abstentions), 1 `list_recall`; the released `qtype`
field agrees with the vendored detector on all 1,013 rows; 74 of the 198 carry a "Today is …"
anchor; evidence ids per question 1 / 2 / 3 = 358 / 16 / 7; HF revision
`78e826dc07e97466b2f54443831ef9a83ab8b27c`; evaluator `ef4e5dff` (pins per `r51` Amendment 1).
**No `p1`, no verdict, no answer text has been seen.** Re-cutting cells to n is a sample-size
decision, which `M-3` permits before any outcome exists; it is the only reason this is `r51b`
and not an amendment.

## Restated rules (everything else is `r51`'s)

- **Population and questions file.** All 381 email-only QA are written to the external
  `questions.yaml` (the executor answers them all; `fuzzy` = not `number`, so only the 198 get
  verdicts). The 14 abstention rows ride for X10 as decisions without verdicts.
- **Cells.** PRIMARY — **quintiles of leader credence** over the verdicted ticks (five cells,
  edges published, ties broken by stable sort on question id), readable at **n ≥ 30**.
  SECONDARY — `r49`'s five fixed buckets, readable at n ≥ 30 for the upper three and n ≥ 15
  for the lower two. DESCRIPTIVE — reliability diagram and ECE over deciles of held-out `p1`.
- **Folds.** K = 10 by sorted-rank round-robin (`r51`), K = n ≡ LOO as the unit control; at
  ≈ 180 ticks and `r49`'s 0.48 s per tick-fold the run is ≈ 15 min, LOO ≈ 4 h, so the timing
  probe is one spawn at N = 180.
- **Readable-count minimum.** At least **four** readable quintiles for any X4 verdict other than
  INCONCLUSIVE.

## Criteria (`r51`'s X2, X3a–e, X5–X10 unchanged; X1 is read; X4 restated)

- **X1 — read, no longer a KILL.** The population is 198 by the recon; the pre-registration
  records it and predicts the verdicted-tick count (P1) instead.
- **X4 (PRIMARY).** Per readable quintile: n, realised rate, mean held-out `p1`, 90% interval;
  the fixed-bucket table; the `p1`-decile reliability diagram and ECE.
  **CONFIRMED** if, over ≥ 4 readable quintiles, mean `p1` spans < **0.05**, realised spans
  > **0.15**, and Spearman ρ(realised, quintile index) ≥ **0.6** — *or* the fixed upper three
  are all readable, their mean `p1` within **0.02** of one another and their realised rates span
  > **0.10** (`r49`'s form).
  **REFUTED** if ≥ 4 quintiles are readable and every readable quintile has |mean `p1` −
  realised| ≤ **0.10** (power-consistent at n ≈ 36 per cell, where 2·SE ≈ 0.13; `r51`'s 0.05
  would have been inside noise) *and* ρ < 0.6.
  Otherwise **INCONCLUSIVE**, the failed condition named and whether it failed for rows or for
  effect. **Disclosed power asymmetry:** at this n CONFIRMED is the powered direction (a 0.15
  monotone span is detectable); REFUTED is weak, and the report says so beside the verdict.
- **X6, X7, X10** as `r51`; X7's grid {−1, −4, −5.131, −7.4285, −9, −12} with implied bar,
  coverage and selective risk per point.
- **X9** as `r51`, taken before the stack is built and after the read; the r51 root and
  `elicitations.jsonl` custody clauses unchanged.

## Blind predictions

1. **P1** verdicted ticks (eligible `number` decisions) ∈ **[120, 190]**.
2. **P2** typed `report` rate on the 381 ∈ **0.30–0.50**.
3. **P3** X4 **CONFIRMED on the quintile read**; **P3′** the fixed upper three are NOT all
   readable (`ge90` < 30), so the fixed form is INCONCLUSIVE.
4. **P4** X6 reads **FAIL**, dominated by marginal commits in the 70–90 band, no straddle (none is
   possible on a reaction-free KB — `r51` Scope).
5. **P5** grader false-negative rate on the 60-row audit ≤ 0.05; `answer_matches` alone > 0.10.
6. **P6** X7 coverage < 0.30 at `u_wrong = −9` and > 0.60 at −1.
7. **P7** the 14 abstention rows' mean held-out `p_none` exceeds the `number` rows' mean
   `p_none` (X10, directional).
8. **P8** ECE over `p1`-deciles ≤ **0.05** — the pooled-prior signature is *marginal* calibration
   with *conditional* flatness, so a CONFIRMED X4 and a small ECE are expected together.
9. **P9** lane regex on the 198: `quantity` on 40% (already read — 79 / 198 — recorded so the
   cross-tab's second axis, the leader's shape, is the only unknown).

## Consequence branches (frozen)

X2 / X3a–c KILL → STOP, amend. X3d ceiling exceeded → X4 VOID, published, fix by amendment.
**X4 CONFIRMED** → a comment on proplang#26 with the quintile table, the fixed-bucket table, the
audit and the pins, *worded as corroboration at ~1× n on a second corpus*. **X4 REFUTED** →
proplang#26 gets a dated note ("does not replicate on a public corpus at ~1× n"), `A-CAL`
annotated as held on this corpus. **INCONCLUSIVE** → published with the reason. In every branch:
`DR-DECISION-1` §2.1 gets its first reliability diagram and ECE; OQ-0′ (c′) gets X7's table;
nothing deploys; no bar moves; §18's counters do not move; **then the corpus-pooling recon opens
as its own $0 checkpoint (`A-13`), sized in the foldable unit (`M-35`)**.

## Cost

Build $0 (agent time; the `r51` build list, TDD + mutation battery, one PR). Pilot ≤ $2; full
pass ≈ 381 × ~$0.007 ≈ **≤ $3**. Engine ≈ 15 min at K = 10 as a transient unit with `M-32`
marks. No production unit restarted.

## Amendment log (blind, dated)

**Amendment 3 — 2026-09-06, after the build and the pilots, before any `p1` or verdict exists.**
Tree pins: repo `e9275c7` (the merged build, PRs #182 + #183); engine `~/.local/bin/proplang-host`
sha256 `71998f6556f5…`; corpus `Jingbiao/ATM-Bench` at HF revision
`78e826dc07e97466b2f54443831ef9a83ab8b27c`, built into a second root by `build_kb.py` (6,742
emails, 381 questions, 198 gradeable, 14 abstention rows, the two gauge files copied) and
pinned as `atm-bench-20260906` (digest `50a73805…`, 6,742 artifacts / 6,919 chunks).
**X2a PASSES**: the second build run wrote nothing (0 new paths, 0 re-extractions, 0 emails
rewritten) and `pin_corpus verify` reads MATCH. The root is not a git tree and carries no
`membrane/` directory; the owner KB's ten X9 files hash identically to the before-manifest.
**X2b, honestly**: the first two pilots ran on a stack whose deliberate edge was silently dead
— transient `systemd --user` units inherit the manager's PATH, which lacks the local bin the
`claude` binary lives in, so the bridge's deliberate subprocess failed on every call while the
decision rows were still stamped `deliberate@…` (zero tool-call logs, zero deliberate records,
zero spend; the deployed bridge unit sets its PATH explicitly, which is the recipe now used).
Both pilots and one aborted full pass (24 decisions) are archived under the root outside the
KB's live paths and read for nothing. The third pilot, on the corrected stack: 20 questions in
≈ 10 min, 19 decisions (`lookup` 18, `narrative` 1), **5 reports, 4 of them right by the
harness bucket** (`CORRECT` 4 · `CONFIDENT_WRONG` 1 · `RIGHTLY_WITHHELD` 3 · `WRONGLY_WITHHELD`
12) — the report conjunct holds; the deliberate edge fired on 11 questions (52 tool calls, no
declines, all recorded), **$4.46 in total → $0.223 per question, ABOVE the frozen $0.10**. The
cost conjunct therefore STOPs the pass and this amendment re-prices it: the "≤ $3" assumed run
14's warm deliberates; here every deliberate is cold at ≈ $0.41 a call on 55% of questions, so
the 381-question pass projects ≈ **$85** and ≈ 3.2 h. Spend is delegated (`RULINGS` §5) and
no outcome exists to pick on, so **the pass proceeds at the measured price, on the frozen
population of 381**. One observation for the report: the corrected pilot's decision set is
IDENTICAL to the dead-edge pilots' (the same 5 reports, the same buckets) — eleven deliberates
searched and returned and moved no decision on these twenty. The third pilot's calibration rows
are archived too, so the reading's decision log starts empty; the full pass runs as
`ff-atm-baseline-20260906c`. No criterion, prediction or branch changes.

Expected further entries: the `--expect-*` pins and the harness-match cross-tab after the gold
pass; the X3d tally; the timing constant; the X9 after-manifest.

**Amendment 4 — 2026-09-06, after the gold pass and the audit, before any held-out `p1` exists.**
The pass `ff-atm-baseline-20260906c` finished at 15:00:23 UTC (6 h 32 min of wall from the 08:28:26 UTC launch; 381 answers, 361
decisions, $40.58 — $0.107/q against Amendment 3's projected $0.223/q). The gold pass wrote
**195 verdicts over 195 questions** (eligible 340 · not gradeable 145 · no
question 0 · already verdicted 0 · correct 164 · wrong 31; a second run appended nothing), so the
harness runs with `--expect-ticks 195 --expect-questions 195`; band rows (0.7 ≤ leader credence < 0.9)
29, so X5 is under-powered as predicted (P5 of `r51`) and is published as such. The harness-match cross-tab:
`answer_matches` agrees with the vendored matcher on 160 verdicts and disagrees on 35
(all 35 one way: the vendored matcher reads correct where `answer_matches` reads wrong, never the reverse). **X3d, the blind audit:** 60 rows sampled by seed 8675309 from the sorted verdicted ids, each read
against its evidence emails on-machine and judged before the key was opened — TP 52 · FN 3 · FP 0 ·
TN 5, **FN-rate 0.050 against the 0.10 ceiling → X4 STANDS**; precision 1.000, recall
0.945; `answer_matches` on the same rows would have read FN-rate 0.283. Both files were deleted after the
tally; nothing from them is quoted. **Timing constant:** one spawn folding 195 ticks read 0.472 (92.1 s in all; super-linear in depth: 0.172 at 50 ticks, 0.247 at 100, 0.355 at 150) s per
tick-fold, so K = 10 projects ≈ 25–40 min of engine time for both variants (20 spawns each folding ~176 ticks at ~70 s, plus 390 decide ticks). No criterion, prediction or branch changes.

**Amendment 5 — 2026-09-07 (HKT; written from 16:00 UTC on 2026-09-06), after the run: X3b read, X3c fired by its letter and
re-scoped. NOT blind — disclosed.** The harness run (`r51b-gate`, 15:07–15:51 UTC, 43 min 42 s) writes X3c's, X4's and X6's
artefacts together, and the runbook applied X4's frozen rule (15:51 UTC) before the X3 controls were checked (15:53 UTC);
when this amendment was written its author had seen X4 read CONFIRMED under FULL and `leader-credence+p-none`, X6 PASS, X7
and X9. **X3b** was then read on the real engine (16:00–16:07 UTC): fold 8 re-run twice through the harness's own
`probe_heldout` — 19/19 rows identical between the runs and identical to the recorded `heldout-FULL.jsonl` rows, max |Δ`p1`|
0 — **PASS**. **X3c fails by its letter**: FULL commits on 10 of 195 held-out ticks, the control on 0 (`leader-credence-only`
also 0, and the control ≡ it on all 195); the ten are all `n-candidates=1`, all in one fold, at `p1` 0.949–0.950 where the
control reads 0.865–0.874. The frozen consequence (STOP; re-scope by amendment; no reading taken) is enacted here. **Ground:**
X3c is not a control in `G-3`'s sense — breaking the family ablation it checks would make the variants identical and turn it
GREEN, not RED — it froze `r49`'s *empirical* S4 finding (three families inert on 238 ticks) as a harness check, and the
harness ground it stood for is carried by X3a (unit: K = n byte-identical to LOO), X3b (above), the three variants sharing
ids and folds, and the ablated variants reproducing `r49`'s degenerate `p1` ≈ 0.86 (0.8584 there). **Re-scope: X3c becomes
X3c′, a reading — the per-variant policy table and the discriminating indicator, published — with no consequence for X4,**
whose verdict is invariant across the three variants (the same frozen rule reads CONFIRMED on each: mean `p1` spans 0.018 /
0.010 / 0.006, realised identical, ρ 0.90). This amendment touches no X4 rule, cell, threshold or branch and would read the
same had X4 read REFUTED or INCONCLUSIVE. No re-run is bought: X3b certifies the artefacts deterministic, so the reading of
record is the frozen rule applied after this amendment to the same rows. Registered: `GD-33`, `M-36`.
