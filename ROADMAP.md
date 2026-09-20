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
- **J2 — Origin, and escalation only if a rung earns it.** *Origin done 2026-09-20.* Every
  reply leads with where its answer came from — your documents, a named rung, or a
  decline with its reason (`decisions.origin`, one derivation; the record's v4 `origin`
  field; the first line of `executor.render_view`). Disclosure rows wait with the rung
  that would need them (`deliberate.record_answer` is the seam). The escalate ROW is measured and does
  not pay: the one rung with recorded verdicts (the deliberative edge) answers the owner's
  104 at 87 right / 13 wrong / 4 declined on the grader the act faces, which at today's
  gauge is −0.50 per escalation, and −0.04 even at zero price — a 12.5% wrong rate costs
  more than an 84% right rate earns when `u_wrong` is −5.13. Its own confidence cannot
  rescue it (best self-report bar 0.95: 67/3/24, +0.01 per question, because the call is
  paid before the confidence is visible). So a rung ships when it beats abstaining on the
  board, not before; `scripts/regrade_outside_option.py` is the measurement, and
  `core/outcome_mixture.py` already holds the row's shape.
- **J3 — The stranger.** *Landed 2026-09-20.* `make data` completes the ingest (it had
  registered sources and stopped, leaving nothing searchable); `make sets` fetches
  ATM-Bench at a pinned revision and builds its KB on your machine (CC-BY-NC: the corpus
  lands outside the tree and is never redistributed from here); and the fresh-clone smoke
  boots the real bridge with a tripwire in place of the extraction client, asserting that
  `/ready` reports the **host** act, that `/decide` commits on settled evidence and
  withholds on dispersed, and that both origin lines render — keyless, no network, no
  engine download. The defect it exposed was in the decider itself: a KB with no fitted
  gather row falls back to a uniform prior under which gathering never pays, so a fresh
  install could only ever decline (14 of 14 on the bundled synthetic corpus).
  `config/gather-row.example.json` ships the fitted row as the documented default, a KB's
  own fit always winning; the same 14 then read 8 right / 0 wrong / 6 declined. Both
  pending board rows are pinned: `sample`, the row a stranger reproduces from a clone, and
  `atm`, the external benchmark at its own KB root (`root_env:` in `eval/sets.yaml`).
- **J4 — Live.** jarvis serves asks; the production readout is a dead-man over the decision
  log. *The dead-man landed 2026-09-20:* a stale window exits non-zero and the weekly timer
  pages on it, so a stopped arm is loud instead of legible. "With escalation" is satisfied
  as the board allows it: the deliberative rung sits on the priced menu and the act may buy
  it, which is the only form escalation takes until a rung beats abstaining (J2). What
  remains is use — the exit test counts calendar days carrying live traffic — and the
  `live` row, produced by `scripts/live_archive.py` from the decision log joined to the
  owner's verdicts on `decision_id`.
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
