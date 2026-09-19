# Kickoff — change of direction

Paste this to the agent at the start of a session. It replaces every earlier session brief.

---

We changed direction on 2026-09-19. The unification arc is over: its registers (RULINGS,
DECISIONS, GD-/M-/A- entries), pre-registrations, frozen bars and adoption gate are archived
under `archive/` (tag `archive/unification-arc-v0`). None of it binds. The scoreboard, git
history and `CHANGELOG.md` replace all of it. Read `CLAUDE.md`, `MODEL.md`, `ROADMAP.md`.

What survives is the model: a string-blind decider, a Bayes act under a stated loss
(`u_wrong = −9`, bar 0.90), provenance on every answer, never invent. What changes is who owns
what: **proplang** ranks actions, **tannen** holds the records, the **ER core** (hkaddresses,
once published) holds the posterior; this repo declares the menu, the prices and the utility,
and shapes the evidence. One home per responsibility; delete the duplicates.

The MVP is **reusable by a stranger**, answering **verbatim point facts only** (graded by
exact match) and escalating or declining everything else.

## Next session — J1, the decider (in order, one commit each)

1. **Port the candidate posterior.** credence's `apps/answer-brain/brain/answer_brain.jl`
   (`temper_scales`, `observation_densities`, `candidate_posterior`) → `core/posterior.py`.
   Constants (`A`, `β_ancestry`, `β_model`, `p_none`, `oracle_p`) move into `core/pricing.py`
   as their one home. Pin: replay `$LIFE_AGENT_KB/eval/collapse-fixtures/m5-base` (314
   exchanges, `decision.credences`/`p_none`) bit-for-bit; the fixture reader is at
   `archive/src/life_agent/collapse/fixture.py` — lift it to `eval/replay.py`.
2. **Port the utility folds.** `core/utility.py`'s `_fold_1d`/`_fold_joint` call the credence
   skin; replace with a local fixed-grid quadrature. Pin: Ū on the recorded boot rows to
   printed precision, per `fold_version`. Delete `core/brain.py`.
3. **Put proplang on the path.** The bridge's enqueue-only shadow becomes a synchronous
   `decide(summary)` at `executor.run_pass`'s terminal step; `coarse.map_action` is the
   enactment; boot from the decision ⋈ verdict join. Menu gains `escalate` rows; its first
   design task is the `said@1` form for a learned-reliability rung.
4. **Price gather** from the measured recovery rate (`gather_outcomes.warm_counts`), run 17's
   window (2026-08-26) excluded.
5. **Retire Julia**: the answer-brain daemon, `ask_client.DAEMON`, the `/decide` proxy.
6. `make score`; rule 5 holds or the owner decides.

Tests that need owner data skip and say what they need. `make check` stays under two minutes.
