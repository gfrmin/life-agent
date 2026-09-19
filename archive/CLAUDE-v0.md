# CLAUDE.md — operating manual for `life-agent`

You are an agent working in `.`, the composition root of a personal life-management
assistant. **Read [`PRINCIPLES.md`](./PRINCIPLES.md) first** — it is the single source of the
philosophy (the kernel, the derive/act boundary, resolved and open decisions); this file is
only the operating manual. Then [`docs/system-design.md`](./docs/system-design.md) — the
adopted whole-system design (one DAG; everything is an edge on it; act ledgers project back
into knowledge) — then [`ROADMAP.md`](./ROADMAP.md) for the plan and
[`GETTING_STARTED.md`](./GETTING_STARTED.md) for the immediate tasks. The owner is a strong
engineer (builds Julia DSLs, TS, Python data platforms) — be precise, terse, and don't
over-build (PRINCIPLES §4: compose, don't rebuild).

## What exists (present tense, no aspiration)

Two in-tree Python packages — `pkm` (the KB: derive) and `life_agent` (the agent: decide) — in
a **derive → project → reach** shape (PRINCIPLES §6):

- **derive (`src/pkm`):** sources → primary artifacts → composable transforms → cited, cached,
  idempotent artifacts (SPEC §18.7 chaining; small auditable steps, never a mega-transform).
  `pkm derive` resolves one (input, transform-chain) target cache-first (SPEC §18.11) — a warm
  chain makes zero model calls — demand-logged under `logs/demand/`.
- **project (`src/life_agent/tasks/project.py`):** a thin immutable→mutable bridge — terminal
  `action_items` artifacts filed **once** into the GTD inbox with a `[src:email <id>]` citation.
- **reach (`src/life_agent/reach`):** Telegram as a dumb transport; "Jarvis" is just the persona.

The GTD is event-sourced: an append-only ledger is truth, the SQLite read-model is a fold of it
(PRINCIPLES §7; `docs/act-layer-events.md`). **email→GTD is built but NOT deployed** --
`bin/mail-to-tasks` is the intended timer/debug entrypoint, but no `systemd --user`
timer runs it anywhere today (wiring one in after the mail sync, or retiring the
entrypoint, is a recorded follow-up): the `action_items` transform (haiku,
grounded quotes) auto-files cited tasks; the grounding gate is the safety; triage
happens in Telegram. The ask-anything read path is `scripts/ask.py`, dogfooded via
`bin/ask-live`; its temporal mode (`/recent`, `/since`, `/until`, `/derive` — one line
grammar, identical in the REPL and one-shot argv) filters by the `doc_date` projection
(SPEC §18.12) read-side, naming undated and not-yet-derived hits instead of dropping them.
Its subject mode (engine D2) owner-filters "my X" questions by the `doc_subject`
projection (SPEC §18.13) matched against the owner profile via cached model
verdicts (`life_agent.core.subject`; the profile never enters pkm) — determinate
non-owner and template hits are excluded by name, indeterminates kept and named.
**The GTD ledger projects into knowledge** (`tasks/knowledge.py` →
`$LIFE_AGENT_KB/tasks/state.md`, the mutable→knowledge mirror of `project.py`): the ask
path re-projects + re-ingests it demand-led when the ledger head moves (announced, never
silent), and pkm's path-currency rule (SPEC §15.4) keeps only the newest version
retrievable — so "what's next on my gtd list?" is an ordinary cited `QUESTION`.
Every human-facing surface is governed by
[`docs/interaction-contract.md`](./docs/interaction-contract.md) — read it before touching
a command, intent, flag, or reply string.

**Adopted, being built (Phase 1.6):** the derivation framework —
[`docs/system-design.md`](./docs/system-design.md) +
[`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) (D0–D2 and the
GTD ledger's knowledge projection + pkm path-currency landed) — and, adopted 2026-06-12,
the **Bayesian foundations**
([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)): Ask re-derived as
inference (answers = claim sets with posteriors; responses = EU decisions; calibration
measured). Ask v0 slices 0–3 are landed: the outcomes + decision logs accrue under
`$LIFE_AGENT_KB/calibration/`; `core/brain.py` is the credence skin seam; the **utility
posterior** (`core/utility.py` — utility is a learned belief about the owner, §4.4/§10
as amended: one utility, the agent has none of its own); the **lookup family**
(`core/lookup.py` — §4 with §4.1 covariates); and **narrative subsumption**
(`core/narrative.py` — §7: synthesize is a proposal distribution; claims audited into
cells, population-calibrated per-cell from the eval_claim stream, per-claim EU inclusion
under Ū, the proposal-coverage tail named); and the **§8 decision-weighted adoption
gate** (`core/gate.py`, `run_eval --gate` → `$LIFE_AGENT_KB/eval/gate/`: a posterior
over Δ = EU(typed) − EU(baseline) by MC over P(U) × the Bayesian bootstrap, P(Δ>δ)≥
level with δ/level frozen blind; the disagreement region + answer rates published.
**Since run 6 the baseline is π\*, not the monolithic instrument** — `--gate-replay`
swaps in the raw-deliberative replay (Claude Code with corpus access, the owner's
outside option) and every paired row records `baseline: raw-deliberative-replay`.
**r28 (2026-08-28) publishes the split** `Δ = Δ_answers + Δ_spend`: on run 18 it reads
**0.019 + 0.495 = 0.514**, so 96% of the adoption margin is the price of the baseline
arm — whose $39.01 is imputed from token counts, not metered. On delivered answers the
arms are level and π\* returns 95 correct to typed's 61. Quote the split, never the
total alone.
**r29 (2026-08-28, `docs/unification/reports/r29-answer-shape-census.md`, $0) is the
answer-shape census** — criteria, rule table and a three-branch numeric consequence frozen
before any label existed. Three reads, nothing adopted, no `src/` change. (1) **The harvest
of "real asks" is 42% eval corpus** — all 104 gate questions appear verbatim in it, so the
owner-origin population is exactly 146 and the gate set is a census of the eval instrument,
never of the owner's questions (it carries **zero** questions whose answer must be
computed — an artefact of how it was built). Owner-origin reads `exact ∧ verbatim` **0.753**
against a frozen 0.85 bar, and that is an **upper** bound: the classifier's measured
disagreement with a blind manual reference runs one way (10 of 10 provenance disagreements
are computed→verbatim; 11 of 13 space disagreements are X→exact), the reference itself
putting the same quantity at 0.48. (2) **Abstention tracks answer shape:** `computed` 8/8 =
1.00 vs `verbatim` 0.62 (P = 0.023 under the verbatim null; the 95% one-sided lower bound is
0.688, so n=8 cannot carry the 0.95 conjunct as a *bound* — disclosed), and by space
exact 0.56 · quantity 0.95 · set 1.00. (3) **Run 17's collapse: the hand-set grow priors are
REFUTED as its cause** — by run 17 each probe's warm fold held ~380 rows, so the declared
cold prior carried 2.5-2.6% and the daemon's g was ~0.05, not 0.30-0.40. The priors are
wrong anyway in level (6.9-9.6x) and in **order** (the costliest actuator is priced as the
likeliest to recover and is the least). Flat units stay consistent and unrefuted (g/cost
2.6-12.5x, uniform by construction) but are NOT isolated at $0. The finding neither
candidate named: **the gather-outcome stream is contaminated and its proxy is one-sided** —
run 17 wrote 292 rows at recovered-rate 0.432 vs 0.069/0.048 for the latched runs, lifting
the pooled rate to 0.1133 from 0.0411, permanently, in an append-only stream with no policy
segmentation; and `recovered` cannot express harm, so no refit of g on it could have
prevented run 17's 14 report→abstain flips. Two riders bind any successor: **segment or
exclude that window before refitting**, and **a harm term is a precondition, not a
refinement**. Consequence enacted: PROCEED with the utility replan's r30.)
**r30 (2026-08-29, `docs/unification/reports/r30-units-lever.md`, $0) builds the units
lever as a documented no-op:** `core/decide.shaped_u_bar` is the one seam every
`current_u_bar` caller (lookup, narrative, the bridge's grow-menu pricing) now routes
through; `exact` stays the anchor, each other declared shape carries an optional
`voi_scale`/`regret_scale` pair defaulting to 1.0 until the owner opts one in via
`config/utility-model-shape-scales.example.yaml` (kept OUT of the example file the
ledger's own test fixtures copy, to avoid moving pinned hashes for nothing). A $0 splice
re-read run 18's own archive end to end on the r30 tree and reproduced 0.959/+0.514
[+0.077, +0.999] to the printed precision; the replay corpus reads 293/314 with 0
mismatches, the other 21 a fully attributed wire-only artefact (a `?shape=` query param a
pre-r30 cassette cannot contain), verified against exactly the non-`exact`-classified
population. Step 5 (streams 3/5) was investigated and DEFERRED, not built: the real
`calibration.corrections` writer (`scripts/verdict.py`) carries free-text claim
corrections with no `decision_id`/credence and states "NEVER force-folded... prose
steers"; re-ask detection has no frozen similarity/window parameters. Both are named open
items for their own future pre-registration. Next: r30b (steps 3-4, the claim space).)
**The value-join arc is CLOSED and DEPLOYED (r34 → r36 → r37 → r38, 2026-08-31).**
`bridge/server._lattice_join` — M6's ONE declaration of the value-join — tested identity
with `_norm_value` while `candidates_from`, `render`, `era_split`, the S2 grow join and
the confirm probe all used `_candidate_key`: two declarations of one relation, surviving
M6 because they carried different §-numbers. **r34** bound the declared key and **run 21**
PASSED the gate while **K3** killed it on attribution; **r36** reverted it. **r37** built
an observation-only tap over the join (off unless `LIFE_AGENT_JOIN_TAP` is set; the
decision is always the deployed predicate's; recorded never folded) and **run 22** measured
the live firing surface — larger than the recorded-wire one, so r36's stated cause is true
— **but found the real defect: K3 baselined on run 20, whose tree differed by the lever
AND r33 AND #127, and two of its three changed rows belonged to the other two.**
Registered **`M-18`: pin the comparison tree, not just the deciding tree.** **r38**
re-landed against run 22 (differs by the lever alone): **run 23 PASS on all five frozen
criteria — exactly one row differs (q2-027, abstain → correct report at leader 0.863 vs
0.346), the wrong set is byte-identical across runs 21/22/23, and run 23 agrees with run
21 on all 104 rows.** Merged and deployed. **`GD-8` binds the reading: the benefit is ONE
row, below §6.13's wobble floor of 2 — it shipped as a defect repair, never on its row
count.** Two further lessons: a merge is **not additive** (r34 predicted 0.346+0.146=0.493
and called it inert; re-running the posterior reads 0.863, because a merge removes a
competing atom and re-normalises `p_none`) — folded into `M-7`; and **`M-19`**, a
measurement launcher restores the tree it found.

**r30b (2026-08-29, `docs/unification/reports/r30b-interval-claims.md`, $0) builds the
claim space — the INTERVAL claim, priced inside the argmax.** Step 4 ("extract k more") is
scoped OUT with reasons (r29 rider 2 froze a harm term as a precondition; it would be a
second lever on one gate reading). On a `quantity` question with >=2 distinct numeric
candidates, each contiguous range over the candidate order statistics is one more tabular
row over the same K+1 atoms — `u_assert(x_j, U)` with `x_j` the r21-frozen Winkler grade —
ranked by the same optimise call. Width pays INSIDE the row; the response vocabulary does
NOT grow (an interval is a `report` at lower precision, so r21's frozen grading branch took
it unchanged). **The build site was re-scoped before any src change, and the finding is
structural: the gate's typed arm and the deployed read path both decide in the credence
answer-brain daemon, not in `lookup.action_utilities`** — a lever built only in-process
would be invisible to r31 and absent from production. So `core.decide.interval_options` is
the ONE declaration and both surfaces bind it; the daemon gained a generic `extra_actions`
wire (body-priced rows, engine-ranked, zero arithmetic daemon-side, `act` naming the speech
act so the guards still ask "did this commit?") and echoes `n_extra_actions` so a daemon
predating it fails loud instead of silently measuring the old action set. Replay under an
ATTRIBUTED-delta criterion (not pure equality — the lever moves the argmax by design):
288/314 vs the master baseline's 293/314, the 21 carried r30 artefacts identical, the 5 new
ones predicted exactly by the declared gate on 104/104 fixtures in both directions, two
draws identical. Nine mutations RED. **The finding that binds r31: the lever can fire on 5
of the pinned 104** — 19 classify `quantity` but 13 carry exactly one distinct numeric
candidate and 1 carries none, so on 14 of 19 there is no range to claim. Against the §6.13
wobble floor of 2 that is not a reading: **`eval/aggregate-questions.yaml`'s 15 computed
questions are a precondition for r31, not an enhancement.** Merge != deploy (the run-14
precedent): the deploy gates on r31. Also landed: `run_meta.decider_git` (§6.10 covered only
this repo; a run that cannot name the tree that decided cannot attribute its own reading).
Next: r31a (the $0 evidence pack), Conferral 1, then r31. Six
runs so far (§14 ledger has each): the executor series read 0.002 → 0.010 → 0.065 →
0.092 → 0.098, then **run 6 (2026-08-17: judge-graded arms, λ_usd spend on both arms,
the post-Ollama cloud instruments): FAIL at P(Δ>0.05)=0.678, Δ̄=+0.180 [−0.244, +0.661]
— the first positive mean;** typed answer rate 0.47 (47 ✓ / 2 ✗) vs π\* 0.97,
withholdings split miss 18 · dispersed 37 (the reach lever's first *direction*). The
run-5 attribution counterfactual (`scripts/gate_splice.py`, same day, not a reading)
settled what carried the sign: run 5's cautious typed arm, judge-graded and priced, reads
**0.905 / +0.343** — grading + spend did it; the new instrument's live arm gave back
Δ̄ −0.163 (corrects +0.192, two wrongs −0.173, spend −0.183). Audited the same day:
q2-053 was a stale gold (superseded in-corpus; corrected, disclosed), q2-105 a cached
opus coin-flip at 0.93 whose stale CORRECT curve rows the append-only regrade
(`scripts/regrade_edge_rows.py`) now supersedes; and run 6's nine cold deliberates
($10.87) never reached the corpus — the pkm MCP server failed to register (PKM_CONFIG
unset in the launcher) and blind declines were cached as evidence (voided; guarded at
`deliberate.answer`, the bridge cfg, and the gate preflight). **Run 7 (same day,
`gate-20260817T160244`: the run-6 recipe with a working deliberate, corrected golds,
regraded curves) — the series' first PASS: P(Δ>0.05)=0.945, Δ̄=+0.429 [+0.040,
+0.884]**, typed 50 ✓ / 1 ✗ / 53 withheld (miss 18 · dispersed 35) at $5.56 vs π\*
0.97 at $39.01. **Run 8 (router v2,
`gate-20260817T164427`): FAIL 0.857, Δ̄ +0.344 [−0.109, +0.841]** — the router worked
(16 newly admitted: 6 ✓ / 10 dispersed / 0 wrong; miss 18→2; answer rate 0.57; $3.25)
but two curve-evolution wrong-leader commits on multi-value chunks (q2-053, q2-090)
pulled it back under. **Run 9 (the competing-values temper, `gate-20260817T195737`):
PASS 0.938, Δ̄ +0.390 [+0.032, +0.841] — zero wrong commits** (35 ✓ / 0 ✗ / 69 withheld,
answer rate 0.34, $4.10): a same-shape competitor in the extractor's quote window halves
the observation's r on both commit sites (`matching.quote_scoped_competitors` →
`competition_factor`, join channel inherits it — §2 lineage), registered blind off-gate
(`scripts/temper_audit.py`, counterfactual floor 0.945/+0.401 — the live run matched it
almost exactly and the sweep predicted the assert set perfectly). The wrong-commit class
was closed at the price of reach — and **reopened by run 10
(`gate-20260821T094545`): FAIL 0.861, Δ̄ +0.323 [−0.074, +0.787], 36 ✓ / 1 ✗ / 67
withheld** at $3.28. The failure is one row: spliced with that row withheld the same
run reads 0.952 / +0.410 — PASS, stronger than run 9. But it is **not an attributable
reading**: four decision-path changes were in the tree (the pre-registered null-read
fail-open, R2's declared retrieval order, §6.9's probe order, tranche-2 M1's executor
deletion) and three are invisible to the 7.2 oracle by construction. The named risk of
the null-read fail-open was the first suspect and was **refuted**. An isolation ladder
settled it: **run 11** (−fail-open) FAIL 0.880, same single wrong row → the fail-open is
**exonerated** and stays; **run 12** (−§6.9's declared probe order) **PASS 0.964, Δ̄
+0.434, 0 wrong — the best reading in the series and the first PASS on the priced lane**,
so §6.9's key is **convicted** as what moved the commit. It did not create the wrong
leader (the same competitor leads in runs 10–12); it concentrated the posterior enough to
carry an already-wrong leader over the bar. **§6.9 is NOT reverted** — pre-registered
before the run: the old order is nondeterministic, a luckier ticket rather than a better
rule, so master knowingly carries the wrong commit. **Do not deploy this arc** (it is not
deployed now) — the block is KEPT and, by owner ruling 2026-08-22, **re-pointed at the
replace branch (§6.12)**: the carrier-identity checkpoint ran and refuted the block's
original premise (below), but the tree still commits that row wrongly, which is what the
block was for. It closes when r06 reads and the row is fixed or priced. Also
found: **runs 7–9 all fired the LEGACY cascade lane** (the arm's flag defaulted off; each
run's `env_flags` records it), so run 10 was the first gate run ever on the priced lane
and M1's deletion switched the arm's lane rather than removing dead code from its path.
Registered: **§6.10 — a gate run must pin its tree, not just its recipe** (built, tiered,
used live in runs 11–12).
**§13 adoption RESOLVED (2026-08-17, on runs 7+9):
typed is the silent default, honest-withhold-only (the uncalibrated fallback lane is
REMOVED — `LIFE_AGENT_FALLBACK_LANE` is ignored), and the deliberate edge is ON by
default (`LIFE_AGENT_DELIBERATE=0` is the rollback)** — §14's adoption entry has the
evidence and rejected alternatives. The reach audit (`scripts/reach_audit.py`, $0)
priced the levers and pointed at independent-document corroboration (ceiling 40/69) —
**built (2026-08-18: `lookup.confirm_hits`, the `/probe/confirm` bridge endpoint,
`scripts/corroborate_audit.py`) and then REFUSED by its own frozen criteria: NO-GO
at 3 predicted rescues (< 5) with 1 wrong-rescue flip (q2-019, a truncated-leader
superset-confirm — the named defect class).** The 40-ceiling was carrier-count
inflation: 48/63 grounded confirms were forwarded/quoted copies of one attestation,
killed by the §5 dedup guard; true independent-corroboration ceiling ~6, under the
"not worth building pre-dogfood" line — the instrument + endpoint stay in-tree,
tested and dormant (nothing on the decision path calls them; no menu row).
**The n_obs=0 cluster is DECISION-side (`scripts/extraction_audit.py`, 2026-08-18,
$0): not retrieval (ceiling 0), not extraction (delivered reach 4) — 17 of the 19
rows carry candidates with n_obs=0 at EXACTLY uniform credences, i.e. a grounded
channel a replace-branch probe erased, with the gold already on the lattice in 14.
"retrieved-not-extracted" is retired as the cluster's name (wrong twice now); the
suspected over-strong inference is that a NULL re-read is treated as a
DISAGREEMENT (fail-open precedent one branch away), registered in §14 as NOT yet
measured — it needs its own frozen criteria + pre-registration.**
**The carrier-identity checkpoint is READ (r04 RULING 4 → `docs/unification/reports/r05-carrier-identity.md`,
register §6.11, instrument `scripts/carrier_audit.py`, criteria frozen in its docstring
before it ran, $0).** Two surfaces on run 10's tree: the cheap first pass and the
corroborate probe. **BUILD on exposure (17 load-bearing questions on each, ≥ the frozen 5)
with delivered reach 0, so no gate run bought — and the pre-registered fix REFUTED as a
provable no-op:** carriers of byte-identical text never differ in authority class, subject
state or date-projection status here, so argmax-covariate always returns what the declared
key already picked. What is arbitrary is the **grouping** (q2-059: the gold leads in every
arm, the deployed assignment hedges at 0.683, a max-independence assignment reports at
0.975 — and the mirror case lowers a gold), and on the probe surface **37 of 37 straddles
fall on the conservative side**, so the declared key's *consistency* is doing real work and
any fix must preserve it. **The redirection is the result that matters: run 10's wrong
commit is NOT carrier identity.** The base channel on that row carries 5 grounded
observations over 4 documents with the gold alone at 0.985, invariant under every carrier
permutation; the run's own decision row shows the committing view was
`instrument: deliberate@<opus>` with **n_obs = 1** and the gold demoted to 0.033, and the
recorded wire agrees that the competitor appears only after the gather steps. So the wrong
*leader* comes from a **replace branch discarding a grounded channel** — the same class as
the n_obs=0 cluster above, here at n_obs=1. This does not overturn run 12 (§6.9's key
remains the *marginal* cause of the commit); it names what the ladder could not. The audit
found **four defects in itself**, three in its measures — one found after the first reading,
flipping surface (a) NO-GO → BUILD, disclosed in r05's chronology with both quantities
published. **Rulings taken 2026-08-22 (r05's RULINGS section has all four):** the
deployment block is kept and re-pointed at §6.12; §6.11's BUILD licenses
**known-and-uncovered, not a fix** (the grouping bound in both directions and the 37/37
cross-surface conservatism are what the entry now stands for; `scripts/carrier_audit.py`
stays in-tree, tested and dormant); **M1 is ACCEPTED and its checkpoint closed** (run 12
carried the deletion and read 0.964 with zero wrong commits, so the hold had no live
hypothesis left — **M1.5, the coverage census, is unblocked**); and r06 is scoped to every
replace/override site rather than to one hypothesis.
**r06 IS OPEN (`docs/unification/reports/r06-replace-branch.md`, register §6.12, instrument
`scripts/replace_audit.py`, criteria frozen and committed BEFORE it reads).** §6.12
enumerates five replace sites from `core/executor.py` and names the asymmetry that makes
them readable: the corroborate tiers and in-loop `re_extract_strong` retire fail-open on a
null read; **the `deliberate` edge has no null-read guard at all** and collapses the channel
on an empty ok reply by design. The counterfactual is RETIRE-NOT-REPLACE (a deployable rule,
not an invented one), read at $0 off the run's own decision + attributed-edge records, with
the deployed arm READ rather than re-derived. Every mirror of the decision path is imported
from it, and every load-bearing predicate was verified RED by mutation before the read —
r05's lesson applied.
**r06 IS READ (2026-08-22, $0, 102 questions):** exposure S3 68 · S1 26 · S4/S5 12 · S2
unreadable; 59 grounded observations discarded over 27 questions; delivered reach 23 of the 73
questions where a site fired (12 repairs · 11 regressions). Criterion 8 reads **BUILD+PRICE on
S1, S3, S4 and S5** — and the instrument's own control contradicts it: on 29 questions NO site
fired, so retire-not-replace is provably a no-op, yet the arms differ on 8. **Noise floor 28%**,
against which S1 delivers +3.8 rows of excess, S4/S5 +0.7, and **S3 just +0.2 — nothing
distinguishable from the layer gap.** The criterion is left standing as frozen with the bound
published beside it; no run was bought. **The blocking row IS repaired** (deployed reports at
n_obs=1 on the competitor, the counterfactual at n_obs=5 over 4 documents on the gold) but four
sites fired on it and the records carry no ordering, so the attribution is unavailable.
**Criterion 7 retires a standing suspicion:** the S3-collapse signature fires once and a
cross-run dedup explains it — zero genuine null-read collapses, so the empty-ok collapse is
**not** what produced the n_obs=0 cluster, and the S1/S4-vs-S3 asymmetry is structural-only
here. The instrument shipped three defects in its measures and one in an interpretation, all
caught before a verdict and all published. **Registered en route: §6.13 — a declared total
order cannot restore determinism when the tie block is larger than the over-fetch window; the
window itself is the sampler** (found by r06's idempotency double-run: 1 of 104 questions
returns five different top-20s in five calls, 73 of its 80 over-fetched rows sharing one
quantised score; invisible to 7.2 and to a gate run alike).
**r07 IS READ (the recorded replay, `docs/unification/reports/r07-recorded-replay.md`,
instrument `scripts/replay_audit.py`, ten criteria frozen and committed before it read; pass 1
2026-08-22 three arms 67/104, pass 2 2026-08-23 deployed-only 73/104, $0):** fidelity 66/67
and 72/73 with the SAME divergent row both times, control 9/9 — **r06's 28% floor was its
decide-layer stand-in, not the evidence** (r06's 8 disagreeing control rows replay 7/7 with
the record). Attribution from the payload: **S1 ×10 + S2 ×2 confirmed** across the mandated
double run (7 S2 rows withheld as draw-unstable); **S3/S4/S5 discard nothing anywhere**; a
grounded channel was zeroed on 7 questions (S1 on 6, S3 on 1), and on the blocking row S1
zeroes the five-observation base before the deliberate edge re-mints the one-observation
competitor — stable across the double run. **The harm rides the DISAGREE path, which
retire-not-replace cannot see by construction: the enacted RETIRE arm reads 0 repairs / 1
regression while the JOIN upper bound reads 10 repairs / 2 regressions** — so §6.12's live
successor question is a correlation key on the wire (making a §5-deduped JOIN readable),
decision-path code needing its own frozen pre-registration. Every site KNOWN-AND-UNCOVERED
under the frozen bar (floor 0%); **nothing bought**; r06's criterion 8 untouched. En route:
**§6.13 re-measured at commit granularity** (across three draws, 14 of 104 questions wobble
in committed n_obs, 22 flap between readable and cold — a standing noise floor under every
gate reading) and the **§18.9 warm-through** (a $0 replay records composed derivations into
the live store — write-once and key-deterministic so undamaged, but coldness is
pass-order-dependent). Five further deviations disclosed in the report, including the volume
failure that interrupted pass 2 mid-read. Single-doc 12 is
the temper's standing price.
**Rulings 2026-08-23 (owner, interviewed — r07's RULINGS section):** the
JOIN-with-a-correlation-key fix **OPENS as r09**, pulled forward to immediately after M1.5
(E-7 at M6 becomes verify-only; the m0-5 baseline is re-recorded and O2 re-prepared after it
lands); **§6.13 is repaired first as r08** (own pre-registration, $0 multi-draw verification)
so run 13's Δ is attributable to the JOIN alone; **run 13's outcome branches are frozen at
full delegation** — PASS (the gate's frozen δ/level ∧ the blocking row repaired ∧ zero new
wrong commits) closes the §6.12 block and deploys master to live without a further keypress;
FAIL on any conjunct reverts the JOIN from the deploy path and STOPS for a ruling. The cap
stands: r07 was the last pure-diagnosis checkpoint — anomalies en route are disclosure items,
never a new diagnostic arc. Sequencing: **r08 → M1.5 → r09 → run 13**.
**r08 IS READ — §6.13 REPAIRED (2026-08-23/24,
`docs/unification/reports/r08-window-determinism.md`, $0):** fix (b) frozen blind and landed
under TDD (`src/pkm/retrieval.py`, SPEC 0.18.2 — the declared total order goes into the SQL
before `LIMIT`, so the engine cuts a declared prefix, never a sample). Baseline reproduced
and decomposed the defect (window layer order-unstable 75/74/75, set-unstable 15/14/28 per
surface; decision layer stable 103/104 with the witness the sole exception); post-fix **zero
draw-unstable questions everywhere at both layers**; blast radius **one question at one
surface** (the witness at base — §5 dedup absorbs the other 16 straddles); three replay
draws: action wobble 0, firing-order wobble 0, n_obs wobble 2 with
**retrieval-attributable component 0** — run 13's commit-wobble floor is 2, not 14, both
residue rows named (monotone accumulation, the §18.9 warm-through's signature). Predictions
2+4 confirmed, 3 refuted, 1 half, 5 an instructive containment-not-equality. Two deviations
disclosed: the C5 "instrument unmodified" clause contradicted the instrument's own §6.10 pin
on the fixed tree (resolved: `--acknowledge-src-drift` names the one expected tree, stamped
into every pin note), and the draws' render-stage 9(d) guard fired as in r07 (rows dumps are
the artefact of record). The 17/15/30 saturation census is the standing arbitrariness
record. **M1.5 IS DONE (2026-08-24, `docs/unification/reports/r05-collapse-m1-5.md`, $0, nothing moved):** 7.2 green on every set against post-r08 master (311/311 + 104/104 + 2/2); every declared class dispositioned; two of M0.5's three B-lookup absences closed free (warmed by the r07/r08 replays), q2-036 the named remainder — the fix's own footprint (its top-k changed, its new chunks never derived), closed by the post-r09 re-record; bridge-internal lanes each named with their actual oracle; the priced lane and seam path stamp neither regime nor policy (0/104 — M2's poster owns it). Also corrected: **O2 already ran and merged** (m0-5's manifest: 102 free + 209 priced, 2026-08-20) — the baseline of record is the merged m0-5. **r09 IS BUILT AND READ (2026-08-24,
`docs/unification/reports/r09-deduped-join.md`; pre-registration committed BEFORE any src
change):** the §5 dedup key (quote/doc_key/value_norm) rides every wire observation
(executor strips before decide — the brain stays string-blind); every S1/S3/S4/S5 probe
receives the standing channel and returns the §5-deduped JOIN (one rule:
`lookup.dedup_drop_rows`; groups doc-keyed). Disagree no longer erases; empty-ok no longer
collapses; null-guard kept; S2 untouched. Finding: the base arrives deduped + probe obs are
value-only ⇒ the JOIN is idempotent over the raw pool ⇒ **r07's 10/2 bound is run 13's
expected read, not a ceiling**. 7.2: non-probe fixtures byte-identical; 95 probe-firing
fixtures unservable (payload grew — the named class). Suite 2653, ruff, mypy green.
**Run 13 IS READ (2026-08-24, `gate-20260824T144002`): FAIL on two conjuncts —
0.895 < 0.90 and four new wrong commits — with the blocking row REPAIRED and the series'
best mean (Δ̄ +0.424, answer rate 0.71, $0.58).** All four wrong rows were run-10
dispersals (two are standing named classes: superset-confirm q2-019, warm-deliberate
q2-105) — the JOIN converts dispersals in both directions and dispersal was the
protection. **Ruling 4's FAIL branch enacted: the JOIN's code commits are REVERTED from
master (docs stay), the §6.12 block STANDS, the m0-5 re-record/O2 riders were sequenced
after the run and cost nothing, and work is STOPPED for an owner ruling** — re-open r09
with a temper for the named classes under a new pre-registration, or park the JOIN.
**The temper was re-opened and is now CLOSED: r09b → r09c → r09d, three sweep-gated
iterations (2026-08-24/25), each pre-registered before any `src/` change, each read on a
$0 replay of run 13's own record, each STOPPED on its own frozen consequence — total spend
$0, run 14 never fired.** What the wire settled, in order: the block is NOT synthesised
stacking (r09b: 0 of 4 wrong rows flipped), NOT covariate inflation (r09c: A2 fires exactly
as designed and the row never depended on it — its competitor is carried by two of three
genuinely distinct documents answering a file-scoped and a remainder-scoped question while
the question asks a class-scoped one), and NOT any decide-side rule that scores documents by
question-vocabulary overlap (r09d: three window/term variants moved the totals and left one
invariant set of five harmful rows, so the entity anchor is DONE by its own hard clause and
reverted). **The finding that constrains every successor: on the rows that matter the gold's
carrier is TERSE — a table row, a bare line — and the competitor's is DISCURSIVE.**
Surviving the arc: **D3, the S2 join** (the one replace site r09 left untouched now joins —
one correct commit recovered, none lost), parked unmerged pending a gate run (the parked
chain's head is `r10-entity-key` post-revert, tree-identical to the pre-E1 head). **Run 14 is
externally blocked: the Anthropic account hit its usage limit, access returns 2026-09-01.**
The blocked window was spent on $0 checkpoints: **r09e** read the tree of record on run 13's
record (66/104 readable under the §18.9 warm-through; two known-wrong rows still commit
wrong, one repaired to withheld, one cold — so run 14 on this tree would fail a zero-wrong
conjunct as-is, measured not predicted); the **entity-key conferral** took three rulings
(warm-then-read; the extract-side entity field RETIRES; E1's bar frozen at zero channel
harms AND ≥1 wrong-commit repair); and **r10 built E1 (exact typed identifier filter at the
base mint) and REFUSED it by its own frozen bar** — the sweep's marginal read is exactly one
row, the entity-qualifier row, wrong → correct (conjunct 2 met), but a channel-harm census
through the DEPLOYED rule found one gold-dropping *inversion* on a row the motivating census
had misread through its re-implemented carrier mapping, so E1 is reverted from the parked
tree. **The terse-carrier finding now closes the whole carrier-side family, exact or fuzzy,
hard or soft: a terse gold carrier omits qualifiers, so any carrier-side requirement damps
it.** The run-14 conferral (owner, 2026-08-25,
`docs/unification/conferrals/run14-conferral.md`) ruled option A at full delegation: fire on
the parked tree, conjunct 3 baselined on run 13's typed arm (a wrong commit is NEW iff the
row was not wrong there), cap raised. The ruled tail ran the same day. The warm pass fixed a
warm-instrument defect en route: the rerank lane is uncached with fail-open, so a refusing
replay takes the lexical branch wherever the deployed daemon's rerank moved the window — the
first warm minted the DEPLOYED trajectory's frontier, which the $0 lane never visits; the
priced pass became a hybrid (deployed client at every §18.9-recorded seam, refusal kept at
rerank/raw-llm), verified RED→GREEN. This also names the mechanism of r07's one persistently
fidelity-divergent row — disclosure, not a new arc. The $0 re-read on the warmed tree read
zero new wrong commits (both readable run-13 wrongs convert to withheld) and the refreshed
splice registered PASS 0.977 / Δ̄ +0.583 as the expectation. **Run 14
(`gate-20260825T102725`, 2026-08-25): PASS on all four frozen conjuncts — P(Δ>0.05)=0.907,
Δ̄ +0.421 [−0.046, +0.920]; the run-10 blocking row commits correct; zero NEW wrong commits
(the three wrongs are all run-13 rows: the two standing wrongs + the warm-deliberate row);
no named class worse (the superset-confirm row converts wrong → withheld).** Typed 60 ✓ +
2 ✓hedge / 3 ✗ / 39 withheld (miss 2 · dispersed 37) at $0.69 vs π\* 0.97 at $39.01. The
live read sits under the registered expectation (0.907 vs 0.977); the gap is the
warm-deliberate row reporting wrong live where the warmed re-read had it withheld — a
run-13 row, carried not new; disclosed, not renegotiated. **Ruling 4's PASS branch is
ENACTED: the §6.12 deployment block is CLOSED, the parked tree is merged to master (src
tree-identical to `r10-entity-key` post-E1-revert), and master deploys to live
(`bin/ask-live` / jarvis).** The two standing wrongs ride in production, priced and
published. Hard clause carried
forward (owner ruling): **no lever ships while it makes a named wrong-commit class worse.**
Two standing lessons registered: a criterion naming specific rows can go unreadable between
two passes of the same instrument (14 in / 14 out), so name a class + a bar + the
cold-row consequence; and **a census must read the deployed rule end-to-end, never
re-implement the constant it prices** (four instances this arc — the fourth, r10's carrier
mapping, is the first to flip a verdict at a frozen bar; an earlier signature =
byte-identical numbers before and after a change).
**Stage 0 of the completion programme is DONE (2026-08-25): the collapse baseline is
re-recorded as `m2-base` (`docs/unification/reports/r11-baseline-rerecord.md` — one
single run on the deployed tree, 314/314 replay green, 0 absences, q2-036 served,
$0.0388 of the delegated $8 cap, live calibration surfaces byte-identical before/after;
r07 ruling 2's rider CLOSED, m0-5 stands as history), and a weekly production readout
watches the live calibration stream for the carried wrong-row classes
(`scripts/production_readout.py` + `packaging/production-readout.*`, installed on the
live box; report at `$LIFE_AGENT_KB/calibration/readout.md`).
M2 IS DONE (2026-08-25, `docs/unification/reports/r12-collapse-m2.md`, $0): the one
poster — `ask_client.post_decision` + `drive` own the reach surface's record;
`core/recorder.py` is the one recorder (family leaves write through it, the leaf-drift
gate pins it); the §6.5 unavailability RECORD lands locally with `decision_id=""`
(unfoldable — the bridge refuses an empty id, pinned). The pre-registered record change
shipped: reach decisions are priced rows (`regime`/`policy`/`run_id`/`instrument`
appear; `cost_usd`/`latency_s` become numbers). Gates: G1 2705 + clean lint/type; G2
314/314 twice, 105 direction-asserted, DIR-1 amended blind for the 102 posting A-loop
bodies; G3 golden green on both legs, counts identical; P5 live fingerprints
byte-identical to r11. `answer_via_executor`/`_edge_curves` are one-checkpoint shims
that die at M3.
M3 IS DONE (2026-08-25, `docs/unification/reports/r13-collapse-m3.md`, $0.68): ONE fold
entry point — `utility.posterior(brain, model, evidence, *, policy)`, the regime a
required indicator naming a declared conditioning set, structurally enforced
(frozen-elicitations refuses verdict-projected events), `fold_version` covering the
policy so no memo can cross regimes; six callers name their regime and the driver's
stamp derives from `LK.U_BAR_POLICY`. ONE reliability posterior — `core/reliability.py`
(`PRIORS` keyed (edge, cell)); `LK.extractor_reliability` + `NR.population_posteriors`
are drift-gated bindings. `AC.answer` and `ask._edge_curves` deleted; jarvis and the
A-loop driver inline drive + render; `answer_via_executor` is retained as ask's
executor-lane surface (amendment 4); the leaf write tails stay with the one recorder
until M5's single caller (amendment 5). Six blind amendments, three catching defects in
the pre-registration itself (a frozen G3 conjunct would have failed every row by
construction — re-read every frozen clause against the artefact it names). Gates: G1
2718 + clean; G2 314/314 pure equality; G3 = run 15 (`gate-20260825T215428`) PASS on
all four conjuncts — 0.907/+0.421, zero NEW wrongs, the same three carried rows as run
14.
M4 IS DONE (2026-08-26, `docs/unification/reports/r14-collapse-m4.md`, $0.60): ONE
price table — `core/pricing.py` (PRICING_VERSION 2) declares the corroborate tiers,
the transform menu, the deliberate seed, the grow actuators, the re-read model and the
D-2 reliability prior column; executor/gather/reliability BIND the same objects
(drift-gated — a second spelling cannot exist); `realised_utility`'s report branch is
spelled through the `u_assert` atom (exact); E-5: both silent `lambda_usd` defaults are
dead — the latent is REQUIRED and a missing one fails loud. Gates: G1 2724 + clean; G2
314/314 pure equality; G3 = run 16 (`gate-20260826T003710`) PASS on all four conjuncts
— 0.961/+0.519 [+0.081, +1.003], zero NEW wrongs (the two standing rows only; the
warm-deliberate row lands withheld this time — the headline's whole move off run 15 is
that one named wobble), $0.60, all-warm deliberates. Q8 DECIDED: the M3 lane deletes at
M5. The split SIGNED: single M5. Run 16 also settled an ops class: a priced run fired
as an agent-session background task dies with the session (two clean SIGTERM teardowns,
~$0) — priced runs launch as transient `systemd --user` units from here on.
M5 IS DONE (2026-08-26, `docs/unification/reports/r15-collapse-m5.md`, $4.88 across
runs 17+18): the argmax absorption — ONE decide surface. Ask's B-4 pre-emption, the
gather fork + `core/gather.py`, and the M3 live lane (membrane live half, /decide-live,
GATE_WEAK_RETRIEVAL) are deleted; `core/terminals.py` holds the absorbed orchestration;
drive's down-branch runs the in-process body under a DECLARED terminals-only regime
(§6.5 kept for no-engine-at-all); L-3's scoped rows are engine-picked; D-5:
`decisions.withhold_reason` is THE reason derivation. The arc's finding: A2's $0 probe
read the engine's preference for re-reads as real (62/63 recorded reports flip when
shown the grow block) and the frozen consequence landed the every-terminal grow offer —
which run 17 (`gate-20260826T025059`) then PRICED: **FAIL 0.743/+0.238, answer rate
0.62→0.49, dispersed 37→51** — the engine's hand-set grow priors over-value re-reads
(registered §14 as the **hand-priced-VOI arc**, the post-M5 successor: ground the grow
priors in the gather-outcome stream; the argmax cannot genuinely own recall while VOI
is hand-priced). Owner ruling (option A, conferral in-tree): revert A2's ENACTMENT
alone — the report-economy latch returns as measured protection — pre-registered blind
as A5 with directional claims and conjunct (b) restated CLASS-BASED (prospective only;
run 17's record untouched). **Run 18 (`gate-20260826T083356`): PASS on all four —
0.959/+0.514 [+0.077, +0.999], wrongs exactly the two standing rows, the wobble row
withheld, all three directional claims confirmed, $0.37** — reproducing run 16 almost
exactly, so run 17's collapse is attributed to the grow-offer alone.
M6 IS DONE (2026-08-26, `docs/unification/reports/r16-collapse-m6.md`, $0): the
observation model declared once — every §3.3 clause ONE declaration with ONE home.
Three unifications (D-11 `BR._lattice_join` — both edge joins bind; D-14
`LK.source_date_iso` — the date-selection ≻-chain declared, P-1/N-4 named as its
branches; D-15 `RX.VERDICT_Y` — the verdict→evidence projection's one declaration,
membrane binds is-identity), two riders (D-12 `DEC.edge_id`; D-13 the stack URLs
read once), 23 drift-gated `[§3.3 · X-n]` stamps. E-7 VERIFIED second-channel at
every site — zero replace sites, each pinned by a named test. Q5's transcript
produced ($0, 103/104 warm from the route cache): 89/103 disagree, all
one-directional, 65 on the DEFAULT branch ⇒ NOT all table wins ⇒ **a per-construct
volatility latent is warranted — registered, not built; the override stays until
that arc lands.** Gates: G1 2721 + clean; G2 **314/314 pure equality on m5-base**;
no priced run demanded.
M7 IS COMPLETE (2026-08-26, `docs/unification/reports/r17-collapse-m7.md`, $0): the
§6 register pinned by a mutation-verified re-listing guard (census {6.1…6.13} →
artefact pins); D-6 (`EX._WITHHOLD` derives from the one action vocabulary) and D-4
(the leader as one label-view) closed; advisory replay 314/314 pure equality. **Appendix
A SIGNED (owner keypress, 2026-08-26** — the conferral's RULING records the provenance):
PRINCIPLES §16 gains the three-verdict rule, §15's spine sentence carries the
no-space/policy-preference clause, §14 records the module collapse adopted.
**The collapse ladder is CLOSED.** Old D3–D4 stay
re-scoped as Ask's
aggregate/thread families. The doc's §14 open questions are a **live empirical ledger**
(owner's adoption rider): each entry names the evidence that decides it — keep it
current. Sequencing is continuous and eval-gated, not dogfood-gated (PRINCIPLES §9 as
amended).

**Not built, deliberately:** the agent-loop spine (open decision — PRINCIPLES §15),
a separate VOI governor (there is none to build — the governor is the spine itself, PRINCIPLES §16), a live MCP server
(`src/pkm/mcp_server.py` is dormant-by-design — PRINCIPLES §5). One candidate spine+brain
composition is documented at
[`docs/candidates/brain-design.md`](./docs/candidates/brain-design.md) — a candidate, not the
plan; the related external repos (`../credence/apps/credence-pi`, `../pi-mono`) are reference
material for that candidate only.

- **Membrane shadow (`src/life_agent/membrane`, `src/life_agent/bridge`):** the frozen
  proplang-govhost engine mirrors live decide/verdict traffic off to the side, never on the
  decision path. Env-gated (absence = disabled); report at `$LIFE_AGENT_KB/membrane/report.md`,
  register at [`docs/membrane-shadow.md`](./docs/membrane-shadow.md). **Owner ruling
  (2026-08-25, superseding run-14 conferral ruling 5): proplang is the RULED successor of
  credence at the decide seam — the migration is MANDATORY, gated-mandatory
  (membrane-shadow §18: the frozen bars pace the swap and a FAIL means iterate-and-re-run,
  never park; refusal is retired as an endpoint) and DEFERRED (not a completion-programme
  condition). **The completion audit is DEFINED and READ** (owner ruling 2026-08-31,
  `RULINGS.md` `G-2`; `docs/unification/reports/r35-completion-audit.md`), so **Arc C is
  UNBLOCKED**; the programme itself closes at Stages 0, 1 and 4 with Stage 2 RETIRED (`G-1`). Nothing in tree may presuppose the
  swap until it lands.** **Arc C IS OPEN and its first three rungs are read, all $0: `r40` found no engine binary here and the shadow dead
  since 2026-08-10; `r41`/P0 pinned the engine and its control replays a recorded decide
  exactly, while HEAD refuses the handshake; `r42` measured HEAD's door to differ in **four**
  ways, not the one named from source. **`r43` closes the blocker: item 4 — HEAD parsing our
  utility then deciding as if absent — is OUR declaration.** HEAD's `chooseEU` compares two
  BELIEFS under one common utility row, so per-action levels never enter; and `act` is one of
  exactly two names (with `t`) in a 19-name namespace that cannot move the predictive, because
  `handshake_decl` declares guard rows only for the indicators. Declaring a **`clock`** row
  routes selection to the substitution path and arm B tracks `argmax_action` on 5/5 cases
  (three winners not the head); an **`act` guard row** is a second, independent repair.
  Registered: **`M-23` — read the counterparty's own register first** (the engine had it as
  `OB-24` all along, remedy named). **`GD-14` then superseded that decision's consequence on
  owner direction: the issue IS filed** (`proplang#24`) as **demand**, not diagnosis —
  `OB-24` is a *ruled deferral*, and a deferral is a judgement about demand, the one input a
  downstream consumer supplies and the counterparty's register cannot derive. `M-23` carries the
  rider; r43's reading is untouched. **`r44` LANDED the repair**
  (items 1, 2, 4; no decide-path change): a declared grid rule (rungs at the measured
  operating rate, every `argmax_action` crossing, the shadow's p05/median/p95 and the
  endpoints → n=8, 960 worlds), full-coverage ticks with the writable name EXCLUDED, and the
  clock row at a derived price. **59/59 battery cases track `argmax_action` at the engine's
  own belief across 27 distinct p1 and all four affordances**; all three rows byte-identical
  on the control; `think` never fires; 8/8 mutations RED. Disclosed costs: the clock forces a
  preposterior every decide (**297 ms vs 135 ms**), and `#19`'s placement effect is real but
  small and neighbourhood-driven, not single-rung. **No §18 bar is read — one is now
  READABLE.** **`GD-15` (2026-09-01) then found r44 had fired a registered conditional without
  discharging it:** `r04-stocktake` §3(ii) held that *if* the swap discretises, the fold-depth
  bench's "sixteenths" rule applies from day one — r44 discretised, and the frozen grid rule
  emits 49–56-bit denominators, the bench's own P3 regime at 13–100× the fold-growth of
  sixteenths. Not repaired by reflex: it contradicts two clauses r44 froze (a rung AT the
  operating rate; a crossing survives the collision) and reintroduces `#19`'s placement hazard,
  and depth — the multiplier — only accrues once P1 lands. Registered: **`M-24` — a conditional
  in the register is a trigger you own.**
  **`r45` IS READ (2026-09-01, `r45-evidence-path.md`, `GD-16`, $0): item 3 was never one
  thing, and the modelling worry was moot.** (a) A door rule — an evidence tick must supply
  every declared name, and since `shadow_features` never emits `act`, the **menu** is its only
  supplier; a menu-less tick is refused, which is why `session.boot()` could not replay a
  single row against HEAD. (b) A non-question — **the recorded act does not enter the fold on
  either arm** (four pinned acts, byte-identical `p1`), so no option could corrupt
  act-conditioning because there has never been any. (c) A capability that *does* exist, but
  only with a **discriminating** guard grid AND `act` out of the menu — and that world has no
  writable name, so it cannot decide. **`act` is either written or observed, never both**, so
  r43's "never a tick feature" holds only while it is in the menu. **C3 FAILS at 0/250**: the
  engine chose `gather` on every row, because `gather` is the argmax across **96–98% of the
  credence range** under both the declared and deployed `u_bar` — `world.utility_by_action`'s
  own flagged myopic-perfect-information bake-in, whose docstring named it an *empirical*
  question whether v2 dissolves the v1 gather-bar pathology. **It does not**, and that is now a
  precondition on reading any §18 bar. `GD-16` records the decision C3 forces (backfill pooled;
  C3 stands FAIL; reverses if act-conditioning ever lands). **C8 answered and falsified a fact
  r45 itself froze**: the stack did NOT keep running — it and the shadow stopped *together* on
  08-09; only the stack returned on 08-17, because the shadow's enablement lived in an env var
  no `.env`, unit or dotfile carried (now in `.env.example`). Registered: **`M-25` — a mutation
  control must vary the dimension the null is about** (r45's own act-null shipped a RED control
  that varied the *evidence*, certifying a null its `[0.5]` guard grid had manufactured). Also
  landed: `client.request` raises `MembraneError` on an unparsable reply (HEAD's refusals are
  invalid JSON), and **`session.evidence_tick_body` is the ONE evidence-tick declaration** —
  the body had been spelled three times (session, `lattice_replay`, `p3_gate`), all menu-less,
  which would have left r46's own grid leg dead on arrival.
  **P1 IS RESTORED AND LIVE (C9/C10 PASS, 2026-09-01).** Arm B is installed at the path the
  code names, `LIFE_AGENT_MEMBRANE_COMMAND` is in the deployed **`.env`** (never the keyring —
  a linger-started unit boots with it locked), and the 08-10 → 09-01 gap is a `kind: "boundary"`
  row **in the stream** (`M-14`) carrying both engine shas — mandatory because `models` went
  2 393 → 960, so `p1` either side is a posterior over a different space. The boot row is itself
  the proof of the fold (`shadow.py:678` must not raise for `:697` to write it) and reached
  **t = 250**, the same 250 the offline backfill verified. Four labelled live decides
  (`question_id` `r45c9probe*`, the only non-hex ids in 3 765 decide rows, so exclusion is
  mechanical) close the **mirror** leg too — "clean boot then silence" was the 08-10 failure, so
  the boot leg alone would not have tested it — and all four chose `gather`, confirming C3 on
  the deployed path. **The cost is published, not buried: ~20 s wall / 6.8 s engine CPU per
  mirrored decide at depth 250 vs `r44`'s 297 ms at negligible depth, and a bridge restart re-pays the
  whole ~19.5 min boot fold.** A depth sweep on one process attributes it to FOLD DEPTH (0.280 s
  CPU at depth 0 — `r44`'s bench reproduced — then 0.640 s at 25, 4.440 s at 100), which
  **falsifies `GD-15`'s first ground** (*"depth is small … very likely not yet biting"*).
  **`GD-17`** publishes it, corrects the register (`M-20`), keeps the shadow enabled (branch 1
  is frozen; nothing user-facing waits — `submit_decide` is enqueue-only off the decision path)
  and still changes no rule today (`GD-15`'s other two grounds are unmoved; `M-4`).
  **`r46` legs A and B ARE READ, both $0 (2026-09-02).** Leg A discharged the §18 surface
  precondition: the bar's surface is DECLARED to be `coarse.map_action`'s mapped one
  (`GD-18`) — the raw affordance is a constant (6 654/6 654 `gather` at the read), the
  mapped surface varies with engine signal (echo 0.636; 118/605 disagreeing rows, all
  engine-contributed), **but its commit branch has never once been reached**: threshold
  `p1 = 0.897015` (sitting there because `u_abstain = 0` — the owner-only residue, now
  priced in `docs/unification/conferrals/u-abstain-conferral.md`), ledger max 0.8706, gap
  0.0264 — §17.6's near-miss extended to the whole ledger, both arms, and the mapped
  surface; empirical, not structural, so a bar read today prices gather-vs-withhold and
  must say its commit column is empty. The tap is live and writing since the bridge's
  restart — whose first attempt **permanently killed the shadow** (112 s cold precompile
  vs a 120 s ready timeout; `ActiveState=active` throughout), repaired by a warm second
  (`GD-20`, `M-27`). Leg B discharged `GD-15`'s conditional and closed `M-24` — sixteenths
  are REFUTED for this world (they merge rung pairs, `n` 8→6, `models` 960→516) — by
  snapping the grid to the finest lattice the frozen bar admits
  (`world._GRID_LATTICE_BITS = 20`, applied after rung selection, refused rather than
  allowed to merge): depth 250 reached, **748 s → 226 s** within-run, **zero differing
  actions over 428 summaries**, `p1` gap ~3×10⁻⁷ (~9 500× under `W6`'s); the mechanism is
  denominator **bit-length**, not non-dyadicity — the pre-registration's own claim,
  corrected not dropped. **Merged, NOT on the wire** until the next natural restart, and
  no reduction of `GD-20`'s hazard, which sits before any fold. Also registered: `M-26`
  (a column's meaning can depend on the row's kind) and `M-28` (a measurement pins its
  tree for the whole run); `GD-19` — settled the same day, apart from r46 — keeps the
  measurement-tree tags unpushed, their SHAs pinned in `M-16`.
  **Leg C IS READ (2026-09-03, `r46c-act-conditioning.md`, `GD-21`, PR #165, $0):**
  act-conditioning is real (K3) and choosable (K4) — r45's YES, via a mirrored NON-writable
  `act-taken` guard with `act` kept in the menu — but **INERT for the commit ceiling** (K5:
  +7×10⁻⁵, 0/250 rows lifted), and the bar had drifted BELOW the ceiling anyway (live p†
  **0.8369** = r32's, < pooled ceiling **0.862188**, 180/250 clear). Branch 1 letter met /
  ground refuted (the `GD-16` shape): NOT opened as a lever; **leg A's sharpened target
  CORRECTED** — the p1 ceiling is not the blocker under the deployed bar (K5 does not re-run
  `coarse.map_action`, so the affordance-`gather` explanation is inferred; whether the drifted
  bar flips any exhausted-gather row is handed to the §18 checkpoint). `M-29` registered
  (never run a git-checkout mutation harness over uncommitted work). **Leg D IS READ
  (2026-09-03, `r46d-categorical-twin.md`, `GD-22`, PR #166, $0):** `GD-13` RESOLVED — the two
  worlds share **ONE grid rule**; the θ codebook is **K-INDEPENDENT** (same 8-rung grid across
  k, models 688/1032/1720 = 344·k via `obs_arity`), so `GD-13`'s "per-K" conflated the menu
  grid (per-K, already correct) with θ (the K-independent channel rate). r45's three source
  claims measured true, one broader: the twin's tick fails arm B on **TWO** counts (menu-less
  `act` + the dormant indicators `cat_features` omits). A categorical enablement (E1/§17.6)
  needs four items (codebooks=`theta_grid`, clock, menu-tick, full indicator coverage) —
  SPECIFIED, NOT built; nothing deployed, world env-disabled. **All four r46 legs are read.**
  **§17.6's E1 re-earn is OPEN and its grounding pass is read (`GD-23`, 2026-09-03, $0).**
  E1 is NOT greenfield — stages 0-1 landed 2026-07-22 (membrane-shadow §15/§16) and
  `membrane/categorical.py` is in tree, env-gated OFF and byte-inert. Its governing design
  (`docs/candidates/e1-categorical-outcome.md`, owner-approved 2026-07-21) had been **stranded
  on a paused branch while §15 named it governing**; it is salvaged verbatim with a third dated
  re-ground (§7) rather than rebased, and `feat/e1-design` is retired. The finding: **six of
  its eight engine dependencies have closed** — #20's per-code readout SHIPPED and
  verified **live on our arm B** ($0 probe: `p0`/`argmax_code`/`p_argmax`/`p_codes[]` in every
  reply — §16's unobservable R-D23 question is answerable, §4.4's gap closes), #21's null-mass cap closed at the `OB-19`
  heir, and #19 closed with the θ ceiling **changing owner rather than dissolving** (θ is
  REQUIRED hello data — the reason leg D's item 1 exists; our declared grid's top rung reads
  **0.990634** under the deployed Ū, not the doc's 0.9). `OB-12` discharged, increment B out
  **on measurement**, its named re-opener a second verdict source — which this repo has **built
  and dormant** (`core/claude_verdicts.py`: 180 verdicts, none since 2026-07-22), so the demand
  is ours to file AND to re-supply (`M-23`/`GD-14`). #10 ruled a **reserved tail priced from
  tick 0**, the option §5.4(c) said we did not need. NOT
  concluded, deliberately: whether §16 finding 3's gather binder still binds (two of its three
  terms moved; `r45`'s C3 measured the pathology standing; the crossing needs the engine under
  today's Ū — `r48`'s job). **`r47` IS READ AND BUILT** (`GD-24`, $0, ten
  criteria PASS): the deployed categorical episode speaks the enabled world at HEAD — the four
  items land in `categorical.py`, codebooks/clock **binding** the binary world's own objects;
  arm B accepts end to end at k ∈ {2,3,5} (`models` 688/1032/1720 = leg D's `344·k`) where the
  pre-enablement episode is refused at the handshake; binary world byte-untouched; 4/4
  mutations RED; **nothing deployed or enabled**. The order was frozen with its reason: build
  before measuring (`M-7` forbids pricing a constant through a re-implementation of the rule
  that assembles it; `r30b`'s in-process lever is invisible). Two corrections: a prediction
  refuted (arm B refuses at the handshake) and a test asserting an **invented** requirement
  (clock name in the namespace) refuted by the deployed binary world.
  **`r48` IS READ (2026-09-04, `GD-25`, $0) — the E1 re-earn does NOT clear, and the KILL that
  fired names a COST defect, not a build defect.** J1 fires (3 of 129 summaries returned no
  action, all k ≥ 12, one of them at **`n_obs` = 0** — so the cost is model-space and handshake,
  not evidence depth) and **its stated ground is refuted**: 126 episodes returned a declared
  action on the deployed enabled world, covering **2 009/2 012 recorded rows (99.85%)**. It
  stands as fired (`GD-16`'s letter-met/ground-refuted shape); the re-read it mandates finds
  `r47`'s enablement **sound** and its **episode budget unbounded**. On the completing leg:
  `gather` on all 126 replay episodes and all 55 sweep steps, **no flip**; 40 observations reach
  `p_argmax` **0.98348** vs a necessary bar of **0.99063** (gap **0.00716**, closed 14.3× from
  §16's era, still open), **K-independent to 16 digits**; 11 summaries clear the vs-abstain bar
  0.836894 — nine of them the degenerate k=1 — and all still chose `gather`. §17.6 binds
  unchanged: a sharper `p1` or #15 / E3, **never a softer bar**; r48 proposes neither. Three
  corrections: **`M-30`** — §16 finding 3's *by-construction* clause is **VOID** (`r46` leg B's
  2⁻²⁰ snap rounded the decisive rung **up**; the θ ceiling now sits 1.2×10⁻⁸ **above** the bar,
  so reachability rests on a rounding direction — leg B's verification was honest and complete on
  the rows it checked, and the boundary it moved is one no episode visits; finding 3's primary
  attribution, the overvalued information row, stands and is now **empirical**); **blind
  prediction 4 REFUTED** — arm B is **2.3–145× SLOWER** than arm A on a **4.65× smaller** model
  space, median latency **~k⁴** where `models` is k¹ (mechanism named, not measured); and **§16
  finding 5 answered** — R-D23's `1/(K−1)` cap shows **zero violations** over 113 rows,
  tightening monotonically (0.26 of cap at k=2 → 0.82 at k=11) without binding. §16 finding 4's
  owed K-cap has a number: **k ≤ 3** (every observed episode inside production's 20 s
  `cat_timeout_s`; **74.3%** of recorded traffic, the rest needs a *named* skip). Nothing
  deployed or enabled; no `src/` change; `M-1` not engaged.
  **r49 — §18's FIRST BAR IS READ, and it FAILs (2026-09-04, `GD-26`, $0).** Pre-reg
  frozen before the harness ran (S1–S11, S1/S3 KILL, six blind predictions; r48's six
  preconditions disposed inside it); a blind Amendment 1 **withdrew its own recon claim**
  that `GD-18`'s empty commit column was already false — `M-26` fired on the checkpoint's
  author (the 555 `kind: "enact"` rows are the M5-deleted M3 lane's; the real leg A tap has
  exactly ONE `kind: "decide"` row, recording `gather` — **`GD-18` stands**). Read so far:
  **S3 (KILL) PASSES** (both commit-rule spellings flip bit-identically at
  **0.8368942119315517** over 200 001 points) and **S11 answers `GD-21`'s census YES** —
  116/605 exchanges (19.2%) reach the exhausted argmax and the deployed bar flips **all
  116** abstain → commit at ledger-max `p1` 0.8706 where the fixture bar flips **0**
  (ledger-wide 1 276/6 873 clear the deployed bar, 0 the fixture bar; prediction 6 REFUTED
  — 116, not single digits; `GD-18` takes a dated correction, its *hedge* — empirical, not
  structural — being what survives). **S5, THE BAR: FAIL on all three variants** — best
  P(Δ>0.05) **0.301** vs the frozen 0.90, Δ̄ **−0.081** [−0.482, +0.205], 423 engine spawns
  in 14h02m. **The failure is pure over-assertion, 24 rows wide**: the membrane's report set
  strictly *contains* the baseline's (zero abstain×report), the 26 shared commits never
  disagree, and the entire differential is 24 marginal commits at **21/3 = 0.875**. **The
  gauge decides the sign** — the same rows are worth **+0.234/q** at the deployed boot Ū
  (break-even 0.837) and **−0.250/q** at the gate's posterior (break-even 0.900); point Δ
  **+0.075 vs −0.080** (`M-31`), and `GD-26` **declined to re-read the bar at the softer
  gauge after seeing the FAIL** (§17.6 / `M-4`). **S6 blocks independently under `M-1`** —
  the arm commits **q2-019**, the named superset-confirm class, wrong. And **`p-none`
  carries the whole policy**: `leader-credence` alone is degenerate (mean `p1` 0.8584 in
  four of five buckets ⇒ respond-all) while `n-candidates`/`n-obs`/`flags` change **no
  action on any of 238 ticks**, three of seventeen indicators never firing at all.
  Δ_spend is **0.000 structurally** (104/104 baseline rows `cost_usd: null`, token counters
  zero — unimputable), and the harness timestamps no phase boundary so 14h is unattributable
  across arms (`M-32`, which blocks sizing the parallel-harness successor). **The frozen
  stop rule is ENACTED**: §17.6 FAILed this same A3 criterion, so this is the second
  consecutive FAIL on one frozen criterion and **work STOPS for an owner ruling** —
  `docs/unification/conferrals/s18-bar-conferral.md` carries evidence, five options and
  prices. Nothing deployed, enabled or swapped; no successor opened.
  **r49b IS READ (2026-09-05, `GD-27`, $0) and the conferral's question is WITHDRAWN as
  mis-posed.** The owner ruled `u_wrong` is **not a gauge**: the affine gauge is the two pins
  (`u_correct = +1`, `u_abstain = 0`), so `u_wrong` is an **identified latent** and −9.0 vs
  −5.131 are two **estimates of one quantity** — an *epistemic* question the constitution had
  already assigned to evidence, which `M-31` mis-routed into §5's conventional bucket, producing
  a **result-relevant** keypress: it flips the headline sign toward adoption (point Δ −0.080 →
  +0.075), though not by itself to a PASS (A3's P(Δ>0.05) ≥ 0.90 was never computed there).
  **A bad question, not a bad answer.**
  `core/utility.py` carried the right framing all along ("two conditioning sets over one
  probability model"): `all-to-date` folds the §4.4 verdict→evidence projection, the gate's
  `frozen-elicitations` **structurally refuses** it. The ruled remedy — *one utility, decision
  layer and gate both read it* — is **enacted in part and escalated in part**, because three
  facts refute its mechanism: (1) **no stale side-store exists** — `current_u_bar` re-folds live
  on every call and the bridge hands the shadow that same fold, so the boot Ū is a *snapshot of
  the live belief*; (2) it **tracks non-monotonically** — −5.9395 → **−8.8301** → −5.1310 across
  20 boot records, and in August the deployed bar sat **within 0.002** of the gate's; (3) **the
  labels are reversed** — −9.0 is the *elicitation-only* number, −5.131 the *reaction-conditioned*
  one, so "the current posterior mean" is the **softer** bar. Implemented literally the rule
  scores the gate at 0.837, flips r49's Δ to **+0.075**, and deletes an **anti-circularity
  guard** (reactions are projected from verdicts on the very decision log the gate scores) — the
  rule written to prevent result-picking would deliver it. **Escalated, not resolved** (§17.6 /
  `M-4`); the re-posed question is narrow: **does the A3 gate keep its blind regime?** Enacted:
  `M-31` corrected, `GD-26` given a dated correction and its Reaction filled, and **C built** —
  **`M-33`**, `gate.regime_pairing`/`break_even`/`render_regime_pairing` (derived *through*
  `decide.u_assert`, `M-7`) with a **preflight in `p3_gate.py`** that declares both regimes and
  both break-evens before any engine spawns; reproduced on r49's own artefacts, 16 tests, 6/6
  mutations RED (three initially SURVIVED — rounded endpoint stand-ins, no coincident-regime
  case, no reversed-order case — and one predicate was **dead, not untested**, so it was
  removed). **B is NOT opened** — right and regime-independent (the band's realised 0.80 sits
  below both break-evens) but a decision-path lever needing its own `M-3` pre-registration.
  **Next (2026-09-05):** the guard question is held for the owner and gates nothing else
  (three sub-answers costed in `r49b` §5; nothing is re-read at the softer regime while it is
  open). The stop rule is discharged — the ruling named B — so **B was OPENED as `r50`
  (pre-registration frozen `037b506`) and READ the same day: S2 KILLs** (`GD-28`, $0, no run
  bought — no candidate family separates the band, BF 0.229/0.253/0.212 vs 10; `runner-up` has
  the direction, 0.862 without a competitor vs 0.731 with, but the split needs ~7× the band's
  rows and owner verdicts add ~7 a month with the Claude verdict channel dormant since
  2026-07-22, so **the verdict supply binds every evidence-side lever on §18's bar**; B closes,
  `runner_up_credence` kept as a neutral field, the census dormant in tree, D unsized; named
  not opened: re-supply the Claude verdict channel, and the engine-side pooled-prior hypothesis
  filed as demand). Its frozen shape (S1/S2 KILLs; three candidate families, X-only tercile
  edges; six blind predictions) was: r49's 70–90 band (55 rows, realised 0.800 committed at mean `p1`
  0.863–0.873, below both break-evens), a host-side family that separates the band or the
  engine's guard prior (filed as demand), decided by a $0 census through the harness's own
  `features_for`, KILL if nothing separates; the lattice trim under §10's retention test rides
  with it (`flags` 0/250; `n-candidates`/`n-obs` move zero actions; 960 vs 456 models), its
  control leg reproducing r49's S4 policy. Verdict at the standing blind regime with the `M-33`
  preflight; a FAIL stops for a ruling as before; `M-1` (q2-019) gates any deployment. C's
  harness half LANDED 2026-09-05 (`M-32` phase marks + `phases.json`; the `a3_meta` regime
  record with both Ū and the marginal-commit table, the pairing re-printed at the measured
  marginal rate; 8/8 mutations RED, $0, no restart); still open under C: the boot record's
  policy name on the next natural restart, and the baseline arm's spend re-recorded under an
  `M-18` rider. D is sized from B's timestamped run. The K-cap build and any move on #15 / E3
  each need their own pre-registration. Then §11's exit.
  **Both owner questions RULED 2026-09-05 by interview (`conferrals/a3-regime-conferral.md`):**
  the A3 gate **keeps its blind regime and is made honest** — `M-34`, built: `core/gate.py`
  quotes **INCONCLUSIVE** when the marginal reach straddles the declared pairing (adopts
  nothing; does not advance the consecutive-FAIL count; the remedy is evidence, never a softer
  bar), `run_eval` now declares the pairing the classic gate spans, and `r49` carries a dated
  note; and **the next §18 rung is engine-side demand** — the pooled-prior hypothesis filed as
  proplang#26 with `r49` S4 attached (`A-11`); the verdict re-supply, C's spend re-record and a
  §18 hold were offered and not chosen. `RULINGS` §5 had nothing live.
  **`r51` OPENED and CLOSED 2026-09-06 (`A-12`, `GD-30`/`GD-31`, $0): X1 KILLs.** The owner chose
  (plan-mode interview, `conferrals/external-corpus-conferral.md`) an external labelled corpus —
  ATM-Bench, read by the existing harness over a second KB root — to test the pooled-prior
  hypothesis at ~10× the verdict supply. Pre-registration frozen before download (`401c494`);
  the recon read **198** email-only number-typed questions against the frozen bar of **200** —
  KILL by the letter, and by its ground more strongly than written: the owner's log shows exactly
  **one decision per question per pass**, so a pass yields ≤ 198 verdicted ticks, ≈ 0.8× `r49`'s
  238, not 10× (`M-35`: size a supply in the unit the instrument folds). The benchmark's own
  detector reproduced the paper's 360 / 139 / 514 exactly; the lane regex read `quantity` on
  only 40% of number-typed answers (P2 refuted). Nothing built, nothing deployed, no proplang
  comment; the corpus stays on-machine, never in tree. **What to build next is live in
  `RULINGS` §5** (`conferrals/r51-successor-conferral.md`: the 1×-n replication, a corpus-pooling
  recon, the verdict re-supply, or hold).
  **`r51b` IS READ (2026-09-06, `A-13`, `GD-32`, $45.04 ($40.58 pass + $4.46 third pilot, whose
  11 warm deliberates the pass served)): X4 CONFIRMED.** The owner chose the 1×-n replication
  first (`conferrals/r51-successor-conferral.md`), and it was built and read as pre-registered
  (frozen `18f7840`; Amendments 3–4 blind before the run, 5–6 informed after it): the 381
  email-only ATM-Bench questions answered through a second bridge over a second KB root, the 198
  number-typed ones verdicted by the benchmark's own matcher (195 ticks / 195 questions — P1
  REFUTED (5 above the interval)), a blind 60-row grader audit (FN-rate 0.050 — X4 STANDS), then
  the harness at K = 10 with cells cut blind to the n as quintiles of leader credence. Five of
  five quintiles readable at n = 39: mean held-out `p1` spans 0.018 while realised spans 0.436
  (0.538 → 0.974), ρ 0.90 — **CONFIRMED under every variant**, the pooled shape corroborated on a
  corpus the owner did not author; ECE 0.113 (P8 refuted); the fixed form unreadable (P3′). X6's
  differential read FAIL 0.008 / −0.240 [−0.387, −0.059] once both arms are graded by the verdict
  of record (the harness had graded the baseline by `answer_matches` and read PASS +0.424 —
  `GD-34`, `M-37`): the mirror of `r49`, 10 commits against the baseline's 77, lost on the 68
  rows the membrane withholds and the baseline answers correctly, no straddle under `M-34`
  (recorded, never a §18 bar); X7's `u_wrong` curve carries the first
  implied-bar/coverage/selective-risk table for OQ-0′ (c′); X10 the abstention rows' `p_none`.
  The CONFIRMED branch fired: proplang#26 carries the table as corroboration at ~1× n. The
  self-review found two defects after the first commit, both fixed and disclosed: a control
  clause (X3c) that KILLed on the informative outcome — one spawn lifted `p1` ≈ 0.08 on its
  single-candidate rows — re-scoped by an informed Amendment 5 (`GD-33`; `M-36`: an ablation is
  not a control), and the A3 join grading its arms with two graders (`GD-34`; `M-37`). Nothing
  deploys, no bar or counter moves, the owner KB is byte-untouched (X9), and no benchmark content
  is in tree. **Next: the corpus-pooling recon opens as its own $0 checkpoint (`A-13`), sized in
  the foldable unit (`M-35`).**
  **`r52` IS READ (2026-09-07, `A-13`, `GD-35`, $0): Y1 KILLs at both band constants.**
  LongMemEval-cleaned and LoCoMo's released ten add 142 + 97 number-typed questions to ATM's 198
  — 437 pooled, projecting 65 band rows at `r51b`'s 0.149 and 101 at `r49`'s 0.231 against 385,
  so 14 or 9 corpora of ATM's size would be needed at one pass each (`M-35`) and the pooling
  route is closed. Y0 reproduced the paper's 360 / 139 / 514 exactly; multi-session evidence
  spans 64% of LongMemEval's answerable rows and 96% of LoCoMo's multi-hop; ATM's abstention
  phrase list fires on none of either corpus's labelled abstentions — the NONE atom's public gold
  is a label on LongMemEval and an output-phrase test on LoCoMo. Nothing built; no corpus content
  in tree. **What to build next is the residue class, live for the owner (`RULINGS` §5,
  `conferrals/r52-successor-conferral.md`).**

## `src/pkm` — the KB core (Python, uv, DuckDB): key files

Content-addressed extraction cache + DuckDB catalogue + format producers + transforms.
**It already nails content-addressing and a *semantic* (not bitwise) determinism contract —
don't "fix" that (PRINCIPLES §10).**
- **Producer protocol:** `src/pkm/producer.py` (`Producer` Protocol, `ProducerResult`).
- **Producer template (subprocess + version parse, never raises):** `src/pkm/producers/pandoc.py`.
- **Wiring ladders (edit to add a producer):** `src/pkm/routing.py`, `src/pkm/extract.py`
  (`_PRODUCER_NAMES`, `_needed_producer_names`, `_ensure_constructed`), `src/pkm/cli.py`
  (`--producer` choices, `_SUBCOMMANDS`).
- **Catalogue + migrations:** `src/pkm/catalogue.py`, `src/pkm/migrations/` (hash-verified;
  never edit a landed migration — add the next number).
- **Cache key:** `src/pkm/hashing.py` (`compute_cache_key`, `compute_model_identity_hash`).
- **Transforms:** `src/pkm/transform.py`, `src/pkm/transforms/{entity_extraction,action_items,email_triage}.py`;
  they **chain** (`_find_eligible_sources` resolves `input.producer` over `artifacts` — SPEC §18.7).
  Live model calls gated behind markers (`-m 'not llm and not system'` is the default; both are
  non-deterministic, opt-in only).
- **Tests:** `tests/conftest.py` (`tmp_root`, `migrated_root`); hermetic by default.
- **Governance — READ FIRST:** `docs/pkm/SPEC.md` and `src/pkm/CLAUDE.md`. The frozen-foundation
  rigor (PRINCIPLES §11): SPEC-first, TDD, idempotency double-runs, ask before a new
  dependency / top-level directory / file format.
- Verified: **DuckDB 1.5.2** here loads both `fts` and `vss` (HNSW cosine + `array_cosine_distance`).

## `life_agent.tasks` — the GTD, event-sourced (Python, SQLite, the act layer)

One append-only **event ledger** is the source of truth; the SQLite is a rebuildable
projection. See `docs/act-layer-events.md`.
- **Ledger:** `src/life_agent/tasks/events.py` — `Asserted`/`Disposed`/`Superseded`/`Amended`,
  keyed on a content+grounding **assertion identity** (human commands mint a unique identity;
  email-derived use content).
- **Read-model:** `src/life_agent/tasks/store.py` — the `tasks` table (lists
  inbox/next/scheduled/someday; `@tags`; `is_today`; due); `apply(event)` folds one event,
  `rebuild(events)` replays the ledger. Paths (`src/life_agent/core/config.py`): ledger at
  `$LIFE_AGENT_KB/tasks/events.jsonl`, read-model at `GTD_DB_PATH` (default
  `$LIFE_AGENT_KB/tasks/gtd.db` — derived, safe to delete and rebuild); the legacy
  `JARVIS_DB_PATH` (`$LIFE_AGENT_KB/jarvis/jarvis.db`) is a read-only pre-cutover snapshot.
- **Commands (write seam):** `src/life_agent/tasks/commands.py` →
  `commands.add/complete/delete/move/...` (append event(s) → fold the read-model → return the
  reply). The email projector (`project.py`) is just another producer of
  `Asserted(origin="email")` events.

## `life_agent.reach` — the Telegram channel + persona (transport only, no truth)

- **Transport:** `src/life_agent/reach/telegram.py` (poll/send; knows only Telegram).
- **Loop + NLU + persona:** `src/life_agent/reach/jarvis.py` — a haiku call parses a message →
  intent → routes to `tasks.commands`/`tasks.store`. Runs as `systemd --user jarvis.service`
  via `python -m life_agent.reach.jarvis`.
- **Digest:** `src/life_agent/reach/digest.py` (`python -m life_agent.reach.digest`).
- **Owner's Telegram id:** `JARVIS_USER_ID` (env / gnome-keyring) — never hard-code it.

## Conventions & constraints (operational)

The principles themselves (functional style, seams, provenance, local/cloud, Tailscale,
dogfood) live in [`PRINCIPLES.md`](./PRINCIPLES.md) — they are not restated here.
- **THIS REPO IS PUBLIC (`github.com/gfrmin/life-agent`) AND MUST STAY PII-FREE AND
  REUSABLE BY STRANGERS.** The owner's data lives out of tree under `$LIFE_AGENT_KB`
  (corpus, eval question files, audit artifacts, FAILURES.md) — keep it there. Nothing
  in tree may carry a real person's name, phone/fax number, email address, account or
  document id, or a verbatim value lifted from the corpus, **including in docs prose,
  §14 ledger entries, commit messages, and test fixtures.** When an example needs the
  *shape* of a real value (the competition detector's digit-count classes, a tel/fax
  pair), invent a synthetic value with the same shape and mark it
  `# PII-OK: synthetic <what>` — the existing convention. When a ledger entry must
  describe a real failure, describe the *class* ("the gold is a three-token personal
  name; the leader is its two-token suffix"), never the value. Equally: no
  owner-specific absolute paths, hostnames, or ids hard-coded in `src/` — they belong
  in config/env (`$LIFE_AGENT_KB`, `PKM_CONFIG`, `JARVIS_USER_ID`).
- **In `pkm`:** obey its SPEC-first + TDD + idempotency rules (see Governance above).
- **Secrets are two-tier** (packaging/README.md is the governing write-up):
  **interactive tools read gnome-keyring** (`secret-tool lookup service env key
  VARNAME`; load all into a shell with `load_secrets_from_keyring`), while
  **linger-started `systemd --user` services read the gitignored `.env` (mode 0600)**
  -- under `loginctl enable-linger` the keyring is LOCKED at boot, so a
  keyring-only value fails exactly when a deployed unit needs it. Anything a
  unit needs at boot therefore lives in `.env`, with the keyring as the
  interactive source of truth (see `.env.example`). Fastmail tokens: keyring
  `service=carddav` / `service=jmap`; sending email: `~/.msmtprc` (passwordeval).
- **Tooling preferences:** `rclone` (not s3cmd) for R2; `gh` (not a GitHub MCP) for GitHub;
  don't pipe long-running commands through `head`/`tail` (use native verbosity).
- **Commit/push only when the owner asks** — except where a standing ruling delegates it
  (`RULINGS.md` `D-1`/`D-2`: a PASS on frozen conjuncts ships without a keypress).

## Environment (Arch Linux, this machine)

- **GPU:** RTX 4060 (8 GB). **Local Ollama is DEPRECATED (2026-08-17, owner directive)** —
  the cached ask instruments, the pkm LLM transforms, and jarvis's NLU all run on the
  Anthropic seam (`core/instrument.py`, haiku); local inference returns only via a
  non-Ollama runtime (e.g. for embeddings, unbuilt). Do not assume `localhost:11434`.
- **OCR/docs:** `tesseract 5.5.2` (langs incl. **`heb`** + `eng`), `pdftotext`, `exiftool`,
  ImageMagick 7, ghostscript, libreoffice.
- **Search:** `rg 15.1`, **`rga 0.10.10`** (ripgrep-all, searches inside PDFs), `sqlite3 3.53`
  (FTS5), `pandoc`, `jq`. (No `fd`/`fzf`/`recoll`.) **DuckDB 1.5.2.**
- **Langs:** Python 3.14 system-wide, but **this project pins 3.13** via `uv`
  (`pyproject.toml` `requires-python`); Node 26 + `pnpm`/`bun`; Julia (for credence).
- **Running services:** the life-agent surfaces `jarvis.service`,
  `life-agent-bridge.service`, `gtd-web.service`, `trips-web.service` (+ credence's
  `answer-brain-daemon.service`); timers `daily-digest`, `production-readout`,
  `mbsync` (mail); alongside the box's self-hosted stack (PhotoPrism, Tuwunel +
  mautrix bridges + `matrix-archiver`, miniflux, n8n) and a daily borg backup.

## Start here

0. **Before escalating any choice, read
   [`docs/unification/RULINGS.md`](./docs/unification/RULINGS.md)** — the standing-ruling
   register. A fork it determines is execution, not a question. A fork it does not determine
   is resolved by $0 evidence, then by the current utility posterior, then **decided and
   published** in [`docs/unification/DECISIONS.md`](./docs/unification/DECISIONS.md) (silence
   is assent; that stream is recorded, never folded). **Exactly one class still reaches the
   owner: changes to the objective** — PRINCIPLES, the kernel, the utility gauge. Every
   conferral or report that takes a ruling registers it in the same commit; a guard test
   fails otherwise.
1. Read [`PRINCIPLES.md`](./PRINCIPLES.md), then [`ROADMAP.md`](./ROADMAP.md) (phases), then
   `$LIFE_AGENT_KB/docs/data-seams.md` (the verified, machine-specific data map — out of tree;
   saves you a re-exploration).
2. Follow [`GETTING_STARTED.md`](./GETTING_STARTED.md). Current phase: **Phase 1.6 — the
   derivation framework** (`docs/system-design.md` §8 is the program; FAILURES.md remains
   the evidence log, no longer the gate — PRINCIPLES §9).
