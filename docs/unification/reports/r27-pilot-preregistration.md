# r27 · the exit-test pilot — PRE-REGISTRATION

> **FROZEN.** Committed BEFORE the pilot runs. Results append below the rule; nothing above
> it is edited afterwards. This is a second frozen block, in its own file, so that r27's
> first pre-registration stays untouched.

## What the owner asked, and what was already in tree

Asked on 2026-08-28 whether the MVP exit test (Stage 4) is running, the owner said it is
**not used**, and gave the reason: a general coding agent does the same job.

Three things were then found in tree, none of which the plan that opened K4 knew about:

1. **The arm exists and is named π\*.** `scripts/fairfight/arm_claude.py` drives
   `claude -p` — Claude Code headless — over the same pkm MCP surface the other arms use,
   restricted to `mcp__pkm__search` / `mcp__pkm__extract`. The owner's ruling of
   2026-07-19 made it "the actual π\*", explicitly *not* a one-shot frontier call.
2. **The gate can already read against it.** `run_eval --gate-replay` is Δ2, "the
   outside-option gate", whose own docstring records the owner decision of 2026-08-06:
   *the comparator is what he would do anyway — ask Claude with corpus access.*
3. **It was read, twice, and both readings FAILED — three weeks ago.**
   `bayesian-foundations.md` §14: the first Δ2 reading (2026-08-06,
   `gate-20260806T072244`) read **P(Δ>0.05) = 0.002, Δ̄ = −1.058 [−1.678, −0.529]** —
   the shipped policy about one correct-answer-equivalent per question **worse** than the
   outside option, at an answer rate of 0.21 against 0.97. The second (same day, flag on,
   `u_wrong` pinned) read 0.010 / −0.644.

**So the owner's belief is not a hunch — it is the last measurement anyone took.** What has
changed since is everything: runs 7–18, the §5-deduped JOIN, the whole collapse ladder
M2–M7, and the run-14 deploy. Every one of those runs measured Δ1 (typed vs the
*monolithic* single-call arm), which improved 0.678 → 0.959. **Δ2 has not been re-read
once.** A twelve-run improvement against one baseline says nothing about the other.

## Why the replay is a fair comparator, and where it is not

`ff-v2-delib-20260719` holds **104 deliberative answers** over the authored corpus.
Measured before freezing this: the catalogue today holds **529,788 chunks / 13,183
sources** against the **529,788 / 13,182** recorded in that run's fingerprint — the
evidence surface is the same one, one source added. The replay is not stale.

**Named caveat, and its direction.** π\* ran on `claude-opus-4-8` under Claude Code
2.1.215, five weeks old. Today's would very likely be at least as strong. That biases the
comparison **in the typed arm's favour**, so:

- a result where π\* still wins is **robust** — a stronger π\* only widens it;
- a result where the typed arm wins is **overstated** by an unmeasured amount, and may not
  be claimed without re-running π\* on a current binary.

This asymmetry is frozen here so it cannot be chosen after the numbers are seen.

## The two reads

**P1 — Δ2 re-read on the authored corpus.** Today's deployed typed arm against the
`ff-v2-delib-20260719` replay, through `run_eval --gate --gate-replay`. The expensive arm
is pre-recorded, so this costs only the typed arm's own execution. Directly comparable to
the 2026-08-06 readings because it is the same machinery over the same 104 questions.

**P2 — π\* on questions that were actually asked.** A stratified sample of **15** questions
drawn from the 250 real asks harvested at A1 (`$LIFE_AGENT_KB/eval/real-asks/`), run
through π\* fresh, against the typed arm on the same 15. This is the population the gate
has never covered — known-and-uncovered 9 — and where the arms should differ most: the
typed arm reports on **21%** of real asks against ~58% of authored ones.

P2 is run **only if P1 completes cleanly**, and only within the cap.

## FROZEN QUANTITIES

- **δ = 0.05, level = 0.90** — the standing gate conjuncts, unchanged, so P1 is comparable
  to every reading in the §14 series.
- **Sample frame for P2:** stratified over `family` × `chosen_action`
  (report / abstain), drawn from rows where `decided` is true, ordered by `question_id`
  and taken round-robin across strata so the draw is deterministic and re-derivable. No
  gold exists for these, so P2 is graded by the same judge the gate uses, and its
  correctness column is **advisory**, not a §8 input.
- **Cap: $25 across both reads.** A read that would exceed it stops and reports what it
  bought.

## FROZEN PREDICTIONS (directional, stated before the numbers)

1. **P1's Δ̄ is greater than −1.058** — the twelve runs since bought something against π\*.
2. **P1's Δ̄ is still negative** — π\* still beats the deployed arm on the owner's utility.
3. **P1's typed answer rate is above 0.21**, the rate the first Δ2 reading measured.
4. **The typed arm's answer rate on P2's real asks is below its rate on P1's authored
   questions** — the two populations differ, and the harvested 21% vs ~58% is not an
   artefact of which questions have gold.

A prediction that misses is reported as missed. They exist so the read cannot be narrated
into agreement with whatever it produces.

## FROZEN CONSEQUENCE

**This is a SIZING read. It adopts nothing, retires nothing, deploys nothing, and changes
no default.** It cannot close Stage 4 and it cannot re-open Stage 2 by itself. Its outputs
are an effect size, a cost ratio, a working P2 harness, and a named next question. Whether
a full run follows is the owner's keypress.

**Void conditions**, stated in advance: the Δ2 join refusing on a missing question; the
bridge or daemon going down mid-run (the typed arm's view would be missing, and a partial
gate reading is not a reading); or the cap being reached mid-read. Any of these is reported
as a void, not as a result.

---
## RESULTS

*(appended after the run; nothing above this line is edited)*
