# r51b — the 1×-n replication on ATM-Bench's email subset — READ: **X4 CONFIRMED**

**2026-09-06 · $40.58 · one executor pass + one K = 10 engine run · repo `e9275c7` (build) / `2795fc8` (read) ·
engine `71998f6556f5…` · corpus `Jingbiao/ATM-Bench` at HF revision `78e826dc07e97466b2f54443831ef9a83ab8b27c`, pinned
`atm-bench-20260906` (digest `50a73805…`) · evaluator `ef4e5dff`.** Pre-registration frozen at `18f7840` before any
build; amended blind four times before the run (Amendment 3 the pins and the re-price; Amendment 4 the `--expect-*` pins, the
X3d tally and the timing constant — each dated in the log) and once after it (Amendment 5, dated and informed — §8 deviation 6). No ATM-Bench question, answer, email text or id is quoted here; every
number is a count or an aggregate.

> **Verdict.** **X4 CONFIRMED on the quintile form, under every variant.** Over five readable quintiles of leader credence (n = 39 each) the mean held-out `p1` spans **0.018** (0.860 → 0.878) while realised spans **0.436** (0.538 → 0.974), Spearman ρ **0.90** — the pooled shape `r49` read on the owner's corpus, here on a public one with independent labels: credence flat across the feature, truth rising with it, the pull in both directions (+0.32 in the lowest cell, −0.10 in the highest). The fixed form is not readable (P3′, as predicted). ECE over `p1`-deciles 0.113, so the pooled `p1` is not marginally calibrated either (P8 refuted). The reading is **corroboration at ~1× n** (`M-35`, `GD-32`), never power. One control clause, X3c, fired by its letter after the run and is re-scoped by Amendment 5 (§3b; §8 deviation 6) — the verdict is invariant to it: the same frozen rule reads CONFIRMED under all three variants. Consequence enacted: the frozen CONFIRMED branch (a comment on proplang#26 worded as corroboration); nothing deploys.

## 1. What was asked

`A-13` (owner, interviewed after `r51`'s X1 KILL): build the pre-registered instrument on the **198** gradeable email-only
questions the recon found, re-cut the cells blind to that n, read once, and open the corpus-pooling recon afterwards. The
question: does the engine's held-out `p1` on a corpus the owner did not author read as the pooled shape `r49` found on the
owner's — credence flat across leader-credence cells, truth rising with them — **at ~1× `r49`'s n, never power** (`M-35`).
By-products: A-CAL's first reliability diagram and ECE (`DR-DECISION-1` §2.1), the A3 differential quoted under `M-34` on
a public corpus, and the `u_wrong` sensitivity curve with implied bar, coverage and selective risk (X7).

## 2. The instrument as it ran

- **Population.** 381 email-only QA written to the external `questions.yaml`; 198 `number`-typed (gradeable), 182
  `open_end` (14 abstentions), 1 `list_recall`. The executor answered all 381 through a second bridge (`:8898`) over the
  second KB root, sharing only the stateless credence daemon with production.
- **The pass.** `ff-atm-baseline-20260906c`, launched 08:28:26 UTC as a transient unit, finished 15:00:23 UTC (6 h 32 min):
  381 answers, 361 decisions (155 report · 206 abstain; 340 under the full regime, 21 terminals-only; 0 defaulted), typed report rate 0.407 on 381 scored
  rows (P2); deliberate edge fired on 120 questions (497 tool calls, 1 declines), 11
  of them warm from the third pilot's cache; spend 40.58 (decision rows $40.58, 361/361 numeric; deliberate records $40.26 over 109 fresh records).
- **Verdicts.** `gold_verdicts.py grade` over the pass's decision log: eligible 340 · no question 0 · not
  gradeable 145 · correct 164 · wrong 31 → **195 verdicted ticks over 195 questions**
  (P1 [120, 190]); harness `answer_matches` agrees on 160, disagrees on 35 (the cross-tab, §3).
- **The engine run.** `p3_gate.py --folds 10 --u-bar-source current`, unit `r51b-gate`, 43 min 42 s wall (fold 1 min 22 s · probe:FULL 24 min 29 s · probe:leader-credence-only 8 min 51 s · probe:leader-credence+p-none 8 min 40 s · pricing ≤ 9 s each · a3 3 s + 4 s; cpu 40 min 48 s, cpu/wall 0.93);
  pricing Ū = the external KB's live fold (`all-to-date@current`, elicitation-only: `u_wrong` −8.9993, `lambda_int` 1.0)
  → break-even **0.900**, the gate's `frozen-elicitations` posterior break-even **0.9000** — coincident numerically,
  divergent by label, as the `r51` Scope clause predicted; `M-34`'s INCONCLUSIVE cannot arise here.
- **Timing constant.** One spawn folding 195 ticks: 0.472 (super-linear in depth: 0.172 at 50, 0.247 at 100, 0.355 at 150) s per tick-fold (`r49`: 0.48).

## 3. X3d — the grader audit (blind, on-machine, files deleted)

Sixty verdicted rows were drawn by seed 8675309 from the sorted verdicted ids into a file outside the KB and the repo, each carrying the question, the gold, the leader and the full text of its gold evidence emails. Every row was read against its evidence and judged leader-correct or leader-wrong before the key was opened; the tally was then computed mechanically against the key. Five rows were judged wrong: in four the leader carried a different amount or date than the evidence states; in one it gave the stay in nights where the gold counts days and the evidence shown did not confirm the arrival date, so it was counted wrong (the conservative side). Two rows were judged correct although the leader answered a 'when' question to the day where the gold adds the hour — named as the class a precision mismatch is most likely to turn into a grader false negative, so a reader can price it.

| | grader CORRECT | grader WRONG |
|---|---:|---:|
| audit: leader correct | 52 | 3 |
| audit: leader wrong | 0 | 5 |

FN-rate 0.050 against the 0.10 VOID ceiling → **X4 STANDS**. Precision 1.000, recall 0.945.
`answer_matches` alone on the same 60 rows: 17 false negatives (0.283) — P5's second half.
Type × lane cross-tab on the verdicted ticks (P9): all 195 verdicted ticks are `number`-typed by construction; the lane regex reads `quantity` on 77 and `exact` on 118 (39.5%, the recon's 40% on the 198), so the lane label is a coin the type label is not.

## 3b. X3a–c — the harness controls, and the one that fired

- **X3a** (K = n reproduces LOO byte-for-byte on the fake client): `tests/test_p3_gate_folds.py`, green on the read tree.
- **X3b** (one fold re-run twice → identical `p1`s), read on the real engine after the run (16:00–16:07 UTC): fold 8 (19 questions, train 176) re-run twice through the harness's own `probe_heldout` — 19/19 rows identical between the runs and identical to the run's recorded `heldout-FULL.jsonl` rows (max |Δ`p1`| = 0.0); 159 s and 169 s per spawn. **PASS.**
- **X3c** (the `leader-credence+p-none` variant reproduces FULL's policy): **fails by its letter.** FULL commits on 10 of 195 held-out ticks; the control on 0; `leader-credence-only` on 0 (control ≡ leader-credence-only on all 195). The ten are all `n-candidates=1` (77 of the other 185 are), 9 of 10 `p-none<0.20`, leader credence 6 in ≥0.90 · 3 in 0.80–0.90 · 1 in 0.50–0.70; all ten sit in one fold, whose engine returned `p1` 0.949–0.950 on them where the control's returned 0.865–0.874; over all 195 ticks `p1`(FULL) − `p1`(control) has mean +0.004 and max +0.083; 8 of the 10 are correct. The frozen consequence — STOP, re-scope by amendment, no reading taken — is enacted by **Amendment 5** (deviation 6): X3c is not a control under `G-3` (breaking the ablation it checks would turn it GREEN, not RED); it froze `r49`'s *empirical* S4 finding as a harness check, and the harness ground it stood for is carried by X3a, X3b, the three variants sharing ids and folds, and the ablated variants reproducing `r49`'s degenerate `p1` ≈ 0.86. Re-scoped as this reading (**X3c′**), whose consequence for X4 is none — the verdict is invariant across the variants. What X3c′ says about the engine: on this corpus the candidate-count family is the only one that ever lifts `p1` over the commit bar; `r49` found it inert on 238 ticks. Registered as `GD-33` and `M-36`.

## 4. X4 — the pooled-prior read

**Primary — quintiles of leader credence** (readable at n ≥ 30; 90% Jeffreys interval on realised):

| quintile [edges) | n | realised [90% CI] | mean held-out `p1` | `p1` − realised |
|---|---:|---:|---:|---:|
| q1 [0.053, 0.313) | 39 | 0.538 [0.409, 0.666] | 0.8600 | +0.322 |
| q2 [0.314, 0.584) | 39 | 0.821 [0.712, 0.913] | 0.8604 | +0.040 |
| q3 [0.610, 0.894) | 39 | 0.949 [0.875, 1.000] | 0.8774 | -0.071 |
| q4 [0.895, 0.925) | 39 | 0.923 [0.840, 0.985] | 0.8779 | -0.045 |
| q5 [0.925, 0.990) | 39 | 0.974 [0.914, 1.000] | 0.8741 | -0.100 |

Spearman ρ (realised vs quintile index, harness) 0.9; ECE over these cells 0.11563754933173478.

**Secondary — `r49`'s fixed leader-credence buckets** (upper three readable at n ≥ 30, lower two at n ≥ 15):

| leader bucket | n | realised [90% CI] | mean held-out `p1` | `p1` − realised |
|---|---:|---:|---:|---:|
| lt50 | 70 | 0.671 [0.578, 0.760] | 0.8600 | +0.189 |
| 50-70 | 19 | 0.789 [0.625, 0.925] | 0.8679 | +0.078 |
| 70-80 | 7 | 1.000 [0.805, 1.000] | 0.8668 | -0.133 (unreadable) |
| 80-90 | 22 | 1.000 [0.929, 1.000] | 0.8830 | -0.117 (unreadable) |
| ge90 | 77 | 0.948 [0.899, 0.985] | 0.8761 | -0.072 |

The `leader-credence+p-none` and `leader-credence-only` variants read the same verdict on the same rows: mean `p1` spans 0.010 and 0.006, realised identical, ρ 0.90, ECE over `p1`-deciles 0.106 and 0.107.

**Rule applied** (frozen; evaluator sha `99b4434e80751626…`, written and tested on synthetic tables before any held-out row
existed): five of five quintiles readable at n ≥ 30 (39 each); mean `p1` span 0.0179 < 0.05 ✓; realised span 0.436 > 0.15 ✓; ρ 0.900 ≥ 0.6 ✓ → **CONFIRMED (quintile form)**. The fixed form is not read: 70–80 (n = 7) and 80–90 (n = 22) are unreadable at n ≥ 30, so P3′ holds. REFUTED's conjuncts are not met (max |gap| 0.322 > 0.10; ρ ≥ 0.6). The same script applied to the other two variants' cells in `a1_a2.json` reads CONFIRMED on each (spans 0.0104 and 0.0060).

**Power asymmetry, repeated beside the verdict:** at n ≈ 36 per cell CONFIRMED is the powered direction (a 0.15 monotone
span is detectable); REFUTED is weak. Here the powered direction is the one that fired, on a span nearly three times its bar and a ρ well clear of 0.6; the lowest and highest cells' 90% intervals ([0.409, 0.666] vs [0.914, 1.000]) do not overlap. What this n cannot do is bound the *size* of the pull in the middle cells (q2–q4 gaps +0.04 / −0.07 / −0.05 sit inside ±0.10 intervals) — so the claim carried to proplang#26 is the shape, never a per-cell number.

### 4.1 For `DR-DECISION-1` §2.1 (A-CAL) — delivered here, not as an edit to that document

**Descriptive — reliability over deciles of held-out `p1`:**

| `p1` decile [edges) | n | realised | mean `p1` | gap |
|---|---:|---:|---:|---:|
| q1 [0.860, 0.860) | 19 | 0.842 | 0.8597 | +0.018 |
| q2 [0.860, 0.860) | 20 | 0.800 | 0.8600 | +0.060 |
| q3 [0.860, 0.860) | 19 | 0.526 | 0.8601 | +0.334 |
| q4 [0.860, 0.862) | 20 | 0.650 | 0.8606 | +0.211 |
| q5 [0.862, 0.866) | 19 | 0.947 | 0.8626 | -0.085 |
| q6 [0.866, 0.867) | 20 | 0.850 | 0.8665 | +0.017 |
| q7 [0.867, 0.868) | 19 | 1.000 | 0.8675 | -0.132 |
| q8 [0.868, 0.873) | 20 | 1.000 | 0.8689 | -0.131 |
| q9 [0.873, 0.873) | 19 | 0.947 | 0.8728 | -0.075 |
| q10 [0.873, 0.950) | 20 | 0.850 | 0.9195 | +0.070 |

ECE over `p1`-deciles **0.11269889546525991** (P8 ≤ 0.05).

A-CAL's step-0 read on this corpus: **ECE 0.113** over `p1`-deciles (0.116 over the leader-credence quintiles). The pooled `p1` sits in [0.860, 0.950] with 185 of 195 rows inside [0.860, 0.874], while realised across those deciles runs 0.526 → 1.000 — so the condition under which Chow's rule is optimal (Fumera, Roli & Giacinto 2000: true posteriors) is not met on this corpus at this n. Per-lane not tested: these rows are 39.5% `quantity` by the lane regex and the rest `exact`, with no per-lane cell readable at n ≥ 30. Annotation for §2.1: *A-CAL held on ATM-Bench's email subset, 195 verdicted ticks, 2026-09-06 — the owner-corpus read (`r49`, 238 ticks) stands beside it.* Delivered here because the document is untracked (deviation 5).

## 5. X6, X7, X10

**X6 — the A3 differential at `frozen-elicitations`, `M-34` verdict: PASS**, P(Δ > 0.05) **0.984**, Δ̄ **+0.424** [+0.127, +0.766] (20 000 draws, seed 8675309) — recorded, never a §18 bar. The shape is the mirror of `r49`'s: the membrane arm commits on **10 of 195** held-out ticks (8 ✓ / 2 ✗, answer rate 0.05) against the baseline's 77 (60 ✓ / 17 ✗, 0.39). The disagreement region is 75 rows: abstain×report 71 (mean Δ +1.253 — the baseline's 17 wrong commits at `u_wrong` −9 outweigh its 54 correct ones), report×abstain 4 (−1.500: 3 ✓ 1 ✗), report×report 6 (0). Marginal commits n = 4 at rate 0.750, measured reach outside [0.900, 0.900] — no straddle. P4's straddle clause holds; its FAIL does not, and the differential is carried by the baseline's over-assertion, not by marginal commits. Under the control variant (0 commits) the same reads PASS 0.996 / +0.476 [+0.180, +0.821]. Δ_spend reads 0.000 **structurally** — the harness's paired file carries the typed act and its correctness only, no spend, so the baseline's metered $40.58 never enters; the same zero as `r49`'s for a different reason (`r49`'s rows had null costs; these carry 361/361 numeric costs the join does not read).

**X7 — the `u_wrong` curve** (`u_wrong_curve.py`, the same 195 held-out ticks re-scored at each grid point; the ruled regime's point ★ and the run's pricing point ◆ coincide at −9):

A sensitivity deliverable, **never a verdict** (`M-4`): the same held-out ticks re-scored at each grid point of the identified latent; the ruled regime's point (`-9.0`) and the run's own pricing point (`-8.999307289508993`) are marked, not preferred.

| u_wrong | implied bar | effective bar | coverage | selective risk | joined | marginal n / rate | P(Δ>δ) | Δ̄ [5%, 95%] |
|---:|---:|---:|---:|---:|---:|---|---:|---|
| -1.0 | 0.5000 | 0.501 | 1.000 | 0.159 | 195 | 118 / 0.771 | 1.000 | +0.461 [+0.365, +0.555] |
| -4.0 | 0.8000 | 0.800 | 1.000 | 0.159 | 195 | 118 / 0.771 | 0.910 | +0.246 [-0.001, +0.484] |
| -5.131 | 0.8369 | 0.837 | 1.000 | 0.159 | 195 | 118 / 0.771 | 0.740 | +0.164 [-0.139, +0.459] |
| -7.4285 | 0.8814 | 0.882 | 0.087 | 0.176 | 195 | 6 / 0.833 | 0.952 | +0.298 [+0.054, +0.574] |
| -9.0 ★ | 0.9000 | 0.900 | 0.051 | 0.200 | 195 | 4 / 0.750 | 0.986 | +0.427 [+0.131, +0.755] |
| -12.0 | 0.9231 | 0.924 | 0.051 | 0.200 | 195 | 4 / 0.750 | 0.998 | +0.659 [+0.270, +1.090] |

◆ the run's pricing point · ★ the ruled regime's point (`M-34`). Implied bar = the break-even; effective bar = where the engine's restricted argmax actually flips to respond (a cheap `ask` can hold it above the break-even). Coverage = the share of held-out ticks the policy commits at the effective bar; selective risk = the wrong rate among them; δ = the gate's frozen materiality.

### 5.1 For `OPEN-QUESTIONS-utility` OQ-0′ (c′) — delivered here, not as an edit to that document

At the ruled point (−9, bar 0.900) coverage is **0.051** with selective risk 0.200 (2 of 10); at −7.4285 (0.882) 0.087 / 0.176; at −5.131 and below the effective bar (≤ 0.837) sits under the pooled `p1`'s floor (0.860), so coverage is 1.000 and the selective risk is the base rate 0.159 (31 of 195). What (c′) — *rule a target risk, derive `u_wrong`* — has to bite on here: **nothing between 0.837 and 0.900**. Coverage falls from 1.000 to 0.087 across that interval because the pooled `p1` has almost no mass in it, so a target-risk rule on this corpus chooses between accepting the base rate and abstaining on 91–95% of rows; the curve is a step, not a slope, until `p1` carries the feature's gradient (§4). A sensitivity deliverable, never a verdict (`M-4`); delivered here because the document is untracked (deviation 5).

**X10 (descriptive, n = 3).** Of the 14 email-only abstention questions, **11 posted no decision row at all** — the executor withheld before any posterior existed (the fairfight scorer files all 20 no-decision questions as withholds, 15 rightly and 5 wrongly: 11 abstention · 8 `open_end` · 1 `number`), so on this corpus the NONE atom's public gold is mostly exercised by 'nothing to decide over', never by `p_none`. On the 3 that did post: mean `p_none` 0.103 (median 0.140), mean leader credence 0.897 — against the 197 `number` rows' mean `p_none` 0.177 (median 0.168) and mean leader credence 0.651. **P7 REFUTED on n = 3**: the abstention rows that reached a posterior look like confident answers, not like doubt. A reading, never a verdict.

## 6. Blind predictions, scored

| # | prediction | read | disposition |
|---|---|---|---|
| P1 | verdicted ticks ∈ [120, 190] | 195 | REFUTED (5 above the interval) |
| P2 | typed report rate on the 381 ∈ 0.30–0.50 | 0.407 | CONFIRMED |
| P3 | X4 CONFIRMED on the quintile read | CONFIRMED | CONFIRMED |
| P3′ | fixed upper three not all readable | 70–80 n = 7 · 80–90 n = 22 · ≥90 n = 77 | CONFIRMED |
| P4 | X6 FAIL, marginal commits in 70–90, no straddle | PASS 0.984 / +0.424 [+0.127, +0.766]; marginal 4 @ 0.750; no straddle | REFUTED (PASS, not FAIL; the no-straddle clause holds) |
| P5 | grader FN ≤ 0.05; `answer_matches` alone > 0.10 | 0.050 / 0.283 | CONFIRMED (the grader at the boundary: 3/60) |
| P6 | X7 coverage < 0.30 at −9, > 0.60 at −1 | 0.051 / 1.000 | CONFIRMED |
| P7 | abstention rows' mean p_none > number rows' | 0.103 vs 0.177 | REFUTED (n = 3) |
| P8 | ECE over p1-deciles ≤ 0.05 | 0.113 | REFUTED (0.113) |
| P9 | lane `quantity` on 40% of the 198 | 79 / 198 (recon) | already read |

## 7. Consequence enacted

**The frozen CONFIRMED branch.** A comment on proplang#26 (posted 2026-09-07: https://github.com/gfrmin/proplang/issues/26#issuecomment-5560495676) with the quintile table, the fixed-bucket table, the audit and the pins, worded as corroboration at ~1× n on a second corpus — nothing new is asked; Amendment 5 is disclosed in it. `DR-DECISION-1` §2.1 receives its first reliability diagram and ECE (§4.1) and OQ-0′ (c′) X7's table (§5.1), both delivered here (deviation 5). Nothing deploys; no bar moves; §18's counters do not move; `M-1` is not engaged. **Next: the corpus-pooling recon opens as its own $0 checkpoint (`A-13`), sized in the foldable unit (`M-35`)**, its pre-registration frozen before any download. Registered en route: `GD-33` (X3c's disposition) and `M-36` (an ablation is not a control).

## 8. Deviations, disclosed

1. **Two dead-edge pilots and one aborted pass** (Amendment 3): transient units inherit a PATH without the local bin, so
   the bridge's deliberate subprocess failed silently while rows were stamped `deliberate@…`; archived, read for nothing.
2. **X2b's cost conjunct STOPped the pass and it was re-priced** (Amendment 3): $0.223/q measured on the corrected pilot
   vs the frozen $0.10; the pass proceeded at the measured price under delegated spend. The full pass read $0.107/q.
3. **Eleven of the 120 deliberate edges were warm** from the third pilot's cache: the 20-question pilot ran on the same store, its deliberate records persisted and were served rather than re-spawned, so those rows carry the cached record's cost. The pass's fresh spend is 109 records at $40.26; the decision rows sum to $40.58 with every one of the 361 numeric — no null spend on this pass, where `r49`'s baseline arm carried 104/104 nulls.
4. **Twenty of the 381 answered questions posted no decision row** (§5, X10). The keyed replay is built from decisions, not answers, so the pins are 195: the 198 gradeable questions less one no-decision `number` row less two the eligibility rule dropped (empty candidates) — the 21 ineligible decisions of 361 are 2 `number` and 19 other. P1's [120, 190] was set from the recon's 198 and the owner corpus's eligibility rate; the read is 195, five above it — the prediction under-estimated how many gradeable questions reach a posterior when the evidence is one short paraphrased email. Also: the gate unit's first launch was refused by systemd on a non-normalised log path and relaunched 25 s later on the same tree; the first attempt wrote nothing.
5. **The two owner deliverables are carried by named report sections (§4.1, §5.1), not by edits to the documents the
   pre-registration names.** `DR-DECISION-1` and `OPEN-QUESTIONS-utility` are untracked owner files in the main checkout,
   edited by the owner out of band and off-limits to this agent; the pre-registration's "gets" clauses are discharged by
   delivering the reliability diagram + ECE and X7's table under headings that name their destination, for the owner to
   carry across.
6. **X3c fired by its letter after the run, and Amendment 5 is dated but not blind.** The harness writes X3c's, X4's and X6's artefacts in one run, and the runbook applied the X4 rule (15:51 UTC) before the control was checked (15:53 UTC). The amendment names what had been seen when it was written (X4 CONFIRMED under two variants, X6 PASS, X7, X9), touches no rule, cell, threshold or branch, and would read the same had X4 read REFUTED or INCONCLUSIVE — the test it states for itself. No re-run was bought: X3b certifies the artefacts deterministic to the last digit, so the post-amendment read is the same rule on the same rows. Disclosed in the proplang#26 comment.

## 9. Method notes

- The verdict is the benchmark's own matcher (vendored at `ef4e5dff`); the harness's `answer_matches` is recorded as a
  second reading in each event's `note` and decides nothing.
- Held-out `p1` is the engine's decide on a fold that excludes the question's own fold (K = 10, sorted-rank round-robin);
  `p_none` and leader credence in X10 are the credence posterior's, not an engine fold — the abstention rows carry no
  verdict and so never enter the keyed replay.
- The audit file and its key were written outside the KB and the repo, read on-machine, and deleted after the tally; no
  value from either appears in any pushed artefact.
- `a1_a2.json` carries three variants — `leader-credence-only` is the A1/A2 default set's third; `--gate-variants` selects only the A3 pair — so its X4 read is reported too (§4). Held-out commits by fold: 10 in one fold, 0 in the other nine (§3b). The runbook's step order put the X4 verdict before the X3 controls, a sequencing defect disclosed in deviation 6. The unit's third engine probe was not projected in Amendment 4 (which priced two variants); wall stayed inside the projection.

## 10. X9 — blast radius

Before-manifest 06:51 UTC (10 files: `calibration/*.jsonl`, `membrane/shadow.jsonl`, `utility/*`); after the read, `sha256sum -c`: **all 10 identical**. The r51 root is not a git working tree, and `elicitations.jsonl`'s copy in it carries the manifest-recorded hash. No production unit changed state inside the window: `life-agent-bridge` active since 2026-09-02, `jarvis` since 2026-08-31, `answer-brain-daemon` since 00:29 UTC on 2026-09-06 — six hours before the manifest and eight before the second stack; the journal shows that activation and three earlier stop/starts the same night (23:21–00:29 UTC) each paired to the second with the yo-drive roaming sidecar (a mount cascade), and this session issued no start, stop or restart of any production unit (its only such command is dated 2026-08-31). The second bridge (`r51b-bridge`, :8898, up since 08:15 UTC) was stopped at close.
