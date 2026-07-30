# P3 — pre-registration of the held-out actual-policy gate run

**Frozen 2026-07-30, before any held-out number exists.** This document fixes the protocol,
the arms, the bar, the decision rule, and the stated limits *blind* to the result it will
produce. It is committed on its own, ahead of any run, so the freeze is auditable in git
history. Register §17.5 will hold the results and cite this file; this file is not edited
after the run.

## What is (and is not) blind

I have already seen the **in-sample** figure the seed produced (register §17.4:
`scripts/membrane/lattice_replay.py` prices the folded engine's actual commit policy at
**+0.043 EU/q**, full lattice, folding each question's own verdict before probing it). That
number is the **hypothesis under test**, not a result of this run. What I have *not* seen —
and what this pre-registration fixes the method for — is the **held-out** figure: the same
policy priced as a forecast, with each scored question's own verdict removed from the fold.
The gate constants δ and level were frozen long ago in `life_agent/core/gate.py`
(bayesian-foundations §8) and are not re-chosen here.

The point of P3, in one line: **§17.4 showed the −0.688 was a respond-all counterfactual and
the actual policy is +0.043 in-sample; P3 asks whether that +0.043 survives as a forecast, or
was an in-sample fit.** The held-out sign is the arbiter.

## Data (fixed)

- **Evidence stream:** the verdict replay from `shadow.boot_snapshot` over the current ledger
  — 193 ticks / **84 distinct questions**, 144 correct / 49 wrong (owner reactions + Claude
  verdicts, owner precedence by source). This is the state the flip would ship under.
- **Held-out unit: the question.** Grouped leave-one-question-out (LOO): a question's *entire*
  set of verdict ticks is removed from the fold together, never one tick at a time — otherwise
  a sibling tick of the scored question leaks its label. 84 questions → 84 engine boots
  (measured 5.7 s per boot+fold+probe → ≈ 8 min total; LOO is affordable, so no k-fold
  approximation is used).
- **Scoring unit: the tick.** One scored row per leader-credence-bearing verdict summary
  (n = 190 of 193; 3 carry no leader credence). This is apples-to-apples with the §17.4 seed,
  which scored per tick. EU/q divides realised utility by the scored-row count.
- **Lattice:** the FULL 17-indicator world, byte-identical to `world.handshake_decl` /
  `world.shadow_features` (pinned by the drift guard in `tests/test_lattice_replay.py`). The
  narrowed variants (A2) declare strict subsets of the same frozen vocabulary.
- **Commit rule:** `respond` iff `world.eu_by_action` picks it over `{abstain, ask}` at the
  engine's own probed p1 — `coarse._gather`'s restricted argmax, modelled by
  `lattice_replay.commits_respond` (drift-tested). Break-even at the live Ū is p1 = 0.8559.
- **Differential baseline:** `eval/fairfight/ff-v2-baseline-m3off/arms/baseline` — the
  credence-era answer path with the membrane flag off. Joined to the held-out membrane acts by
  recomputing `core.decisions.question_id(question_text)` over `eval/questions_v2.yaml`
  (corpus `questions_sha256=b89f829a…`, pinned in that run's `run_meta.json`). **74 of the 84**
  verdict questions map to the v2 corpus and all 74 are present in the baseline arm; the other
  **10** are non-v2 (live-traffic) questions — named and excluded from the differential, kept
  in the primary arm A1.

## Arms (produced)

- **A1 — held-out actual-policy EU vs abstain (PRIMARY).** Grouped-LOO over the 84 questions;
  per tick, commit respond-iff-p1>bar over the held-out posterior and realise
  `u_correct / u_wrong / u_abstain` against the tick's label. Report EU/q at Ū and MC over
  P(U), per leader-credence bucket (`lt50 / 50-70 / 70-80 / 80-90 / ge90`), against three
  references: the respond-all counterfactual, abstain (gauge 0), and the in-sample +0.043.
- **A2 — the assertion-gating lever.** The same held-out protocol for {FULL} vs
  {leader-credence-only} vs {a bar raised to refuse the 70-80/80-90 break-even band}. Decides
  coarsening-vs-raised-bar on the held-out EU, not the in-sample one.
- **A3 — differential adoption gate (membrane vs credence baseline).** `PairedOutcome(typed =
  membrane held-out realised act per question, mono = baseline arm's realised act per
  question)` over the 74 joined questions → `gate.delta_posterior` at the **frozen** δ = 0.05,
  level = 0.90. This is proplang OB-12/#11's differential ("life-agent vs the credence brain").
  A question's held-out act aggregates its ticks to one act by majority-respond (ties →
  respond, the assertive side, so the gate cannot flatter the membrane by abstaining a tie).
- **A4 — typed-vs-monolithic (`run_eval --gate`).** The existing §8 gate, run fresh. It does
  not touch the membrane (it compares the typed answer path to raw synthesize); it is produced
  because proplang asked for *both* framings. Reported as-is, labelled as the answer-path gate.
- **Loss ledger** on the membrane held-out arm via `scripts/fairfight/loss_ledger.py` — regret
  vs the corpus-omniscient oracle and vs the empirical π* (the baseline arm).

## The bar and the decision rule (frozen)

- **δ = 0.05, level = 0.90** (already committed in `core/gate.py`; not re-chosen). A3 passes iff
  `P(Δ > 0.05) ≥ 0.90`.
- **A1 is the containment-relevant test:** the flip beats the current contained posture iff the
  held-out EU/q is materially **> 0** (the same δ = 0.05 margin, read against abstain = 0).
- **P3 does not flip `LIFE_AGENT_MEMBRANE_LIVE`.** P0 containment holds regardless of outcome.
  Re-enabling the live path stays owner-authorized only. This run produces *evidence* for that
  decision; it does not take it. Published pass **or** fail.

## Predictions (recorded blind, so the run can surprise me)

Non-binding, but on the record so a self-flattering read after the fact is visible as one:

- A1 held-out will land **below** the in-sample +0.043 (removing a question's own verdict
  should cost some of the fit). Whether it stays **> 0** is the open question — the population
  dial is weakly identified (193 verdicts, 2,393 hypotheses), so per-question leakage is small
  and the held-out figure may sit close to in-sample; that would be evidence the signal is real.
- The 70-80/80-90 band is where the sign is most fragile (p1 ≈ 0.867 > 0.856 bar at ≈ 0.77
  correct — EU-negative in-sample already, §17.4). If A1 is positive overall it is carried by
  ge90; A2 will show whether refusing the break-even band recovers EU held-out.
- A3 (74 questions, thin) most likely **does not** clear 0.90 — the prior §8 gate failed at
  0.848 on a wider corpus, and the credence baseline answers everything while the membrane
  abstains most. A FAIL that is *carried by the disagreement region* is still informative.

## Stated limits (up front, not for a sceptic to find)

- **In-sample ≠ forecast:** A1/A2 are the forecast; the in-sample +0.043 is disclosed as the
  prior, not evidence.
- **Thin cells:** 84 questions; per-bucket n runs ≈ 28 (lt50) … 54 (ge90). The gate's Bayesian
  bootstrap × P(U) MC integrates the finite-corpus uncertainty; the interval, not the point, is
  the honest read.
- **Mixed labels:** verdicts are owner reactions + Claude verdicts (owner precedence). Claude
  verdicts are the objective `correct` bit only, never P(U).
- **Exchangeability proxy:** the eval questions are a curated set treated as exchangeable draws
  — a proxy, per the gate docstring, not a claim about the deployment distribution.
- **Cross-run baseline:** A3/π* join a once-run baseline; a cross-run reference assumes the
  corpus did not change (corpus fingerprint pinned). 10 of 84 questions do not join — named,
  never silently dropped.
- **One engine, one wire:** the frozen `proplang-host` at `~/.local/bin` (W3/W4, `1a0cea7`);
  the θ ceiling (p1 ≤ 0.9) and the null-mass cap are proplang's open items (#19/#21) and bound
  this measurement exactly as §16/§17 record.

## Discharges

A3 (the differential) is proplang OB-12/#11's "single highest-leverage unexecuted measurement
in the programme." Producing it — pass or fail — discharges the consumer side of that ruling.
