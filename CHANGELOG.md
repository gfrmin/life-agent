# Changelog

- 2026-09-19 (J0, reset): unification arc archived (tag `archive/unification-arc-v0`; registers, reports, conferrals, 60+ audit instruments and their tests under `archive/`); no behaviour change on the ask path.
- One scoreboard (`eval/score.py` → `SCOREBOARD.md`, sets pinned by sha256, rule 5 gate); owner board reproduces run 18: typed 61/2/41, oracle 95/6/3, router 97/5/2 at $15.97 vs $39.01.
- `make check` (ruff + pytest -n, 71 s, green with no KB) / `score` / `score-quick` / `data` / `sets` / `engine`; `config/engine.lock` pins proplang at `94fd4eb`. New dev dependency: pytest-xdist.
- Entry docs replaced: one-page `CLAUDE.md`, `MODEL.md`, J0–J5 `ROADMAP.md`, `KICKOFF.md`; PRINCIPLES §1/§14 name proplang as the brain. Production readout drops its governance-register line.
