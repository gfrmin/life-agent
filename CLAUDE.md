# CLAUDE.md — life-agent

Read this, then [`MODEL.md`](./MODEL.md), then [`ROADMAP.md`](./ROADMAP.md). Nothing under
`archive/` is required reading; do not import from it. [`PRINCIPLES.md`](./PRINCIPLES.md) holds
the standing principles; [`docs/ORIENTATION.md`](./docs/ORIENTATION.md) is the five-minute tour.

## What this is

A personal assistant over your own documents (mail, files). Ask it a question over Telegram or
the CLI and it returns either:

- an answer **from your documents**, with the citation and the credence it was committed at;
- an answer **from an escalated model**, saying which rung and what was disclosed to it; or
- **declined**, with the reason.

The MVP bar is **verbatim point facts**: an ID, date, number, name, reference or short list
that appears as a span in a document, graded by exact match with no judge. Everything else is
escalated or declined. Success is measured on the scoreboard: more right answers without more
wrong ones.

## Five rules

1. **Never invent.** A committed answer is a candidate that stands as a span in a cited
   document, or it came from a named escalation rung. The loss is stated, never a bar:
   `u_wrong` is a posterior with prior mean −9 (a wrong answer costs nine rights), folded
   from your reactions; the respond bar is derived from it (0.90 at the prior, 0.84 folded
   today), never set. Declining is an answer.
2. **The decider is one function, string-blind.** `core/decide.bayes_act` ranks the declared
   rows over the posterior on candidate *indices*. No other argmax, anywhere.
3. **Provenance on every answer.** Origin (documents / rung / declined), citation, credence.
   Every decision, every disclosure and every verdict is recorded write-once.
4. **No personal data in the repo.** It is public (`github.com/gfrmin/life-agent`). Owner data
   lives under `$LIFE_AGENT_KB`. No real name, number, address, id or corpus value in code,
   docs, tests or commit messages; a shape-alike synthetic value is marked
   `# PII-OK: synthetic <what>`. The PII hook (`.githooks/pii_check.py`) is armed; every
   commit needs `LIFE_AGENT_KB` set.
5. **The scoreboard decides by expected utility.** Iterate on `make score-quick`; run
   `make score` once per PR and commit the regenerated `SCOREBOARD.md`. A change merges when,
   on every row, its paired utility is not below the incumbent's:
   ΔU = Σ_rows [u(new) − u(old)] − λ_usd·Δ$ ≥ 0, with u_right = 1, u_wrong the folded mean,
   u_declined = 0 (`python -m eval.score --gate`). Every row whose outcome changed is listed
   in the PR.

## Layout

```
src/pkm/          the KB: sources → content-addressed, cited artifacts (SPEC-first; read
                  docs/pkm/SPEC.md and src/pkm/CLAUDE.md before touching it)
src/life_agent/   core/ (retrieval shaping, posterior, utility, pricing, the decider in
                  decide.py + decider.py, executor), bridge/ (:8798 evidence server +
                  /decide), reach/ (Telegram), tasks/ (GTD, event-sourced), trips/,
                  membrane/ (the proplang client — deferred, kept green off the path)
eval/             score.py → SCOREBOARD.md; sets.yaml pins each set by sha256
scripts/          entry points (ask, verdict, ingest_sources, production_readout, fairfight/,
                  atm_bench/, engine.sh)
config/           example configs; engine.lock pins the decider engine
packaging/        systemd --user units
archive/          the unification arc (tag archive/unification-arc-v0); historical only
```

## How to work

- **Sessions and commits.** One goal per session, small commits, `make check` (ruff + mypy +
  pytest, under two minutes) green before each. Worktrees under a sibling `worktrees/life-agent/<name>`; merge
  by PR. Commit and push when the owner asks or has delegated it.
- **History.** Docstrings describe current behaviour only; history lives in git. End a session
  with a summary of at most 15 lines (what changed, the board delta, at most three questions
  for the owner) and at most 5 lines appended to `CHANGELOG.md`.
- **Autonomy.**
  - *Just do:* reversible, measured changes.
  - *Do and flag:* a new dependency, a default change, an additive contract change.
  - *Ask first:* the action menu, the utility gauge (`u_wrong`, `lambda_usd`), golden or eval
    questions, a new data source, anything touching personal data, removing an output field.
- **Engines are upstream, and deferred.** proplang (an engine for the act) and tannen
  (write-once records) are separate public repos, pinned (`config/engine.lock`; a `-close`
  tag), and off the MVP path: each returns when it beats the host on the board. An issue filed
  on either cites a board row or a failing law, never an opinion.
- **Debugging.** When a number moves unexpectedly, print ten example rows before building an
  instrument to explain it. Anchor the clock (`date`) before any timing claim.

## Known traps

- **Secrets are two-tier.** Interactive tools read gnome-keyring (`secret-tool lookup service
  env key VAR`); linger-started `systemd --user` units read the gitignored `.env` (the keyring
  is locked at boot). Anything a unit needs at boot lives in `.env` (see `.env.example`).
- **`/tmp` quota.** If pytest dies writing temp files, run with `TMPDIR=~/.cache/...`.
- **ATM-Bench is CC-BY-NC.** Built on-machine by `make sets`, never redistributed from the repo.
- **pkm's determinism is semantic, not bitwise** — do not "fix" it (PRINCIPLES §10).
- **Grading is exact match on the point fact.** A judge-graded row is not on the MVP board.
