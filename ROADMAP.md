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
| Escalation rungs | host (`core/oracle.py`), priced as rows beside the others |
| Decision / disclosure / verdict records | host write-once JSONL (`core/recorder.py`); **tannen** after the MVP |
| Measurement | `eval/score.py` → `SCOREBOARD.md` |

## Milestones

- **J0 — Reset.** *Done 2026-09-19.* Unification arc archived (tag
  `archive/unification-arc-v0`); `make check`/`score`/`data`/`sets`/`engine`; the board
  reproduces run 18. No behaviour change.
- **J1 — The decider.** The candidate posterior (`answer_brain.jl` → `core/posterior.py`,
  pinned to the 314 m5-base exchanges) and the utility folds (credence-skin → local
  quadrature, pinned to recorded boot Ū); the act is the host Bayes act
  (`core/decide.bayes_act`, `core/decider.py`, `core/enact.py`) with gather and ask priced at
  measured recovery rates; the Julia daemon, the credence skin and the in-process lanes
  retire; rule 5 becomes the ΔU merge rule. The board re-scores the typed arm live.
- **J2 — Escalate + origin.** `core/oracle.py` rungs as rows `bayes_act` ranks, each with a
  Beta reliability folded from its verdicts; disclosure rows in the write-once recorder;
  origin on every reply.
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
- **Gather as a preposterior** over the current posterior, replacing the constant recovery
  rate.

`u_wrong` re-elicitation is the owner's alone (it moves every bar, including escalation's).
