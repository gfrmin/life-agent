# ROADMAP — to the MVP

The design authority is [`MODEL.md`](./MODEL.md); the rules are [`CLAUDE.md`](./CLAUDE.md).
Each milestone closes with an owner sitting; the scoreboard is read at every close.

**MVP** = reusable by a stranger: ask and escalate over Telegram, verbatim point facts only,
and a clone over someone else's mail works end to end.

## One owner per responsibility

| Responsibility | Owner |
|---|---|
| Rank actions by expected utility | host `core/decide.bayes_act` (the one argmax) |
| Declare the menu, prices, utility | host (`core/decide.py`, `core/pricing.py`, `core/utility.py`) |
| Candidate posterior + claim lattice | host `core/posterior.py` (the **ER core** replaces it at J5) |
| Action reliability, learned | host Beta folds from outcomes and verdicts (`core/reliability.py`, `core/gather_outcomes.py`, `core/reactions.py`) |
| Evidence shaping | host (bridge, `core/lookup.py`, `core/matching.py`) |
| Escalation rungs | rows like any other, shipped only when one beats abstaining (J2) |
| Decision / disclosure / verdict records | host write-once JSONL (`core/recorder.py`); **tannen** after the MVP |
| Measurement | `eval/score.py` → `SCOREBOARD.md` |

## Milestones

- **J0 — Reset.** *Done 2026-09-19.* Unification arc archived (tag
  `archive/unification-arc-v0`); `make check`/`score`/`data`/`sets`/`engine`; the board
  reproduces run 18. No behaviour change.
- **J1 — The decider.** *Done 2026-09-20 (PR #192).* The candidate posterior
  (`answer_brain.jl` → `core/posterior.py`, pinned to the 314 m5-base exchanges) and the
  utility folds (credence-skin → local quadrature, pinned to recorded boot Ū); the act is
  the host Bayes act (`core/decide.bayes_act`, `core/decider.py`, `core/enact.py`) with
  gather priced from recorded gather sequences and ask at a measured recovery rate; the
  Julia daemon, the credence skin and the in-process lanes retire; rule 5 is the ΔU merge
  rule. The board is on one grader and one price list (the typed arm's applied probes at
  the menu's prices, cache or no cache): the host act 48/0/56 at $1.44, U/q +0.443, against
  the daemon's 61/2/41 at $20.95, +0.220 — its 13 extra right answers rode with 2 wrongs and
  40 warm calls to the deliberative rung that had been metered at $0. ΔU +23.2. The
  generated golden set (212 questions from the corpus, `make golden`) is the second row:
  the act cold reads 85/4/123 at $0.015 a question, U/q +0.284 — the baseline.
- **J2 — Origin, and escalation only if a rung earns it.** Origin on every reply and
  disclosure rows in the write-once recorder stand. The escalate ROW is measured and does
  not pay: the one rung with recorded verdicts (the deliberative edge) answers the owner's
  104 at 87 right / 13 wrong / 4 declined on the grader the act faces, which at today's
  gauge is −0.50 per escalation, and −0.04 even at zero price — a 12.5% wrong rate costs
  more than an 84% right rate earns when `u_wrong` is −5.13. Its own confidence cannot
  rescue it (best self-report bar 0.95: 67/3/24, +0.01 per question, because the call is
  paid before the confidence is visible). So a rung ships when it beats abstaining on the
  board, not before; `scripts/regrade_outside_option.py` is the measurement, and
  `core/outcome_mixture.py` already holds the row's shape.
- **J3 — The stranger.** `make data` over any maildir/filetree; `make sets` downloads and
  builds ATM-Bench; fresh-clone smoke covers decide + escalate in CI (no
  engine download on the stranger's path).
- **J4 — Live.** jarvis serves asks with escalation; the production readout is a dead-man
  over the decision log.
- **J5 — The second domain.** Swap the posterior, lattice, loss and laws for the ER core's
  own public repo at a pinned tag (hkaddresses consumes the same core).

## Doors after the MVP

Each returns through the board: its arm's paired ΔU ≥ 0 against the host on every set, from the
same recorded decisions.

- **proplang** as the engine for the act: released as `doctrine-sitting-r1` (= `94fd4eb`;
  [gfrmin/proplang#28](https://github.com/gfrmin/proplang/issues/28)), pinned in
  `config/engine.lock`; `membrane/` stays in tree and green off the path. Precondition
  upstream: #26 (per-cell p1 pooling) disposed and a new release pinned.
- **tannen** as the write-once store, at its `m5-close` tag, once the MVP is live.
- **The ER core** (J5): hkaddresses extracts it into its own public repo, with life-agent as
  the second domain (`renavondata/hkaddresses#27`).
- **Gather as a preposterior** over the current posterior, replacing the fitted
  sequence row (`core/gather_row.py`).

`u_wrong` re-elicitation is the owner's alone (it moves every bar, including escalation's).
