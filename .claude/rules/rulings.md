# Owner rulings

One numbered, dated paragraph per ruling; the owner's decision, then what it settles.

1. 2026-09-30 — Owner: delete `membrane/` and the engine packaging (`config/engine.lock`, `scripts/engine.sh`, `make engine`). A git tag (`archive/pre-prune-2026-09-30`) holds the code.
2. 2026-09-30 — Owner: delete the unified ledger. The JSONL logs stay the record, as they always were; nothing read the ledger but its own reconciliation.
3. 2026-09-30 — Owner: score the owner set like the others, and cut `run_eval.py` and `gate.py` to what that needs. The outside and router rows stay as frozen pinned archives.
4. 2026-09-30 — Owner: keep the readers that fold pre-reset history rows, because the folded `u_wrong` depends on them.
