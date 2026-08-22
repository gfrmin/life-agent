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

*(pending — the criteria above are committed before the instrument runs)*
