# Owner rulings

One numbered, dated paragraph per ruling; the owner's decision, then what it settles.

1. 2026-09-30 — Owner: delete `membrane/` and the engine packaging (`config/engine.lock`, `scripts/engine.sh`, `make engine`). A git tag (`archive/pre-prune-2026-09-30`) holds the code.
2. 2026-09-30 — Owner: delete the unified ledger. The JSONL logs stay the record, as they always were; nothing read the ledger but its own reconciliation.
3. 2026-09-30 — Owner: score the owner set like the others, and cut `run_eval.py` and `gate.py` to what that needs. The outside and router rows stay as frozen pinned archives.
4. 2026-09-30 — Owner: keep the readers that fold pre-reset history rows, because the folded `u_wrong` depends on them.
5. 2026-09-30 — Owner: "get rid of SEALED". MODEL.md promised that a document marked SEALED could never reach a disclosing rung; nothing in the code marked or checked it. The paragraph and law 9 are struck, and MODEL §4 now says plainly that retrieved chunks go to a cloud model and the deliberative rung can search the whole corpus. The disclosure record (rule 3, law 7) is still owed.
6. 2026-09-30 — Owner: "no such thing as 'mechanics', everything is a decision": every choice on the ask path is a row of the one argmax. Done here: which transform to buy and which candidate to answer with are rows of `core/decide.bayes_act` (one `gather` row per open probe, one `respond` row per candidate); `core/enact.py` no longer picks, and a drift gate fails if it calls `max`, `min` or `sorted`. The no-candidate state is decided like any other (candidates `[]`, `p1` = 0): the executor no longer walks the probe menu by itself, and at the current gauge an empty extraction abstains. Still outside the argmax: whether to attempt a question the router calls not a point fact.
