# ROADMAP — to the MVP

The design, with its reasons, is [`docs/superpowers/specs/2026-09-19-mvp-reset-design.md`](./docs/superpowers/specs/2026-09-19-mvp-reset-design.md).
Each milestone closes with an owner sitting; the scoreboard is read at every close.

**MVP** = reusable by a stranger: ask and escalate over Telegram, verbatim point facts only,
and a clone over someone else's mail works end to end.

## One owner per responsibility

| Responsibility | Owner |
|---|---|
| Rank actions by expected utility | **proplang** (the engine, via `membrane/`) |
| Declare the menu, prices, utility | host (`membrane/world.py`, `core/pricing.py`, `core/utility.py`) |
| Candidate posterior + claim lattice | **ER core** (host `core/posterior.py` until the core's own repo publishes) |
| Action reliability, learned | **proplang** guards, fed by verdict ticks |
| Evidence shaping | host (bridge, `core/lookup.py`, `core/matching.py`) |
| Escalation rungs | host (`core/oracle.py`) |
| Decision / disclosure / verdict records | **tannen** (write-once relations, pinned at a `-close` tag) |
| Measurement | `eval/score.py` → `SCOREBOARD.md` |

## Milestones

- **J0 — Reset.** *Done 2026-09-19.* Unification arc archived (tag
  `archive/unification-arc-v0`); `make check`/`score`/`data`/`sets`/`engine`; the board
  reproduces run 18. No behaviour change.
- **J1 — The decider.** Port the candidate posterior (`answer_brain.jl` → `core/posterior.py`,
  pinned to the 314 m5-base exchanges) and the utility folds (credence-skin → local quadrature,
  pinned to recorded boot Ū); proplang on the path synchronously, `coarse.map_action` as
  enactment, `escalate` rows on the menu; gather priced from measured recovery; retire the
  Julia daemon and the skin. Retires here too: the narrative lane (`narrative`, `synthesis`,
  `volatility`), `membrane/categorical.py`, `decide.interval_options`, and `core/gate.py`
  with `scripts/run_eval.py` once `eval/score.py` scores live.
- **J2 — Escalate + the boundary ledger.** `core/oracle.py` rungs; tannen records for
  decision, disclosure, verdict (replacing `life_agent/ledger`'s mirror); origin on every
  reply.
- **J3 — The stranger.** `make data` over any maildir/filetree; `make sets` downloads and
  builds ATM-Bench; `make engine` fetches the proplang release; fresh-clone smoke covers
  decide + escalate in CI.
- **J4 — Live.** jarvis serves asks with escalation; the production readout is a dead-man
  over the tannen store.
- **J5 — The second domain.** Swap the posterior, lattice, loss and laws for the ER core's
  own public repo at a pinned tag (hkaddresses consumes the same core).

## Doors on the owner's side

- proplang: released as `doctrine-sitting-r1` (= `94fd4eb`, 2026-09-19;
  [gfrmin/proplang#28](https://github.com/gfrmin/proplang/issues/28)); pinned in `config/engine.lock`.
- hkaddresses: extract the core into its own public repo, with life-agent as the second
  domain — asked in `renavondata/hkaddresses#27`.
- tannen: `m5-close` is closed (2026-09-19); J2 pins it.
- `u_wrong` re-elicitation is the owner's alone (it moves every bar, including escalation's).
