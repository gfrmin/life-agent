# Conferral — the `u_abstain` residue, now with its number (2026-09-02)

Evidence, options and prices, written **before** the interview (house rule). Everything here
is **$0** arithmetic on the deployed rule (`membrane/world.utility_by_action` and
`eu_by_action`) over the utility posterior already recorded in the m5-base corpus. Nothing
was bought, no `src/` change is proposed, and no option below is enacted.

**Why this reaches the owner at all.** `u_abstain` is a **gauge constant** — part of the
objective — and `RULINGS.md` §5 keeps exactly one class on the owner's desk: changes to the
objective. `r35` §3 recorded the residue as *"`u_abstain = 0` cannot represent the cost of not
answering"*, and `GD-18` explicitly **rejected** touching it as a way to move a measurement.
Nothing here asks to move it. What has changed is that the residue is no longer abstract:
r46 measured what it is worth at the margin, and the answer is not what the obvious algebra
predicts.

---

## 1. The number the residue was missing

`r46` measured the mapped surface's terminal act as a step function of the engine's posterior
`p1`, with the commit threshold set by the gauge:

- The commit bar is `|u_wrong| / (u_correct + |u_wrong|)` = 8.710166 / 9.710166 =
  **0.897015**, and it sits there **because `u_abstain = 0`**.
- The engine's posterior has **never reached it**: 0 of 6 654 recorded rows, ceiling
  **0.8706**. The gap is **0.0264** — a near miss, not a chasm.

So the natural question is: *what would abstention have to cost before the system's best-ever
posterior would commit?*

## 2. The obvious algebra is wrong, and that is the finding

Reading only `respond` against `abstain` gives **−0.256**: price silence at about a quarter of
a correct answer and the ceiling clears the bar. **That answer is wrong**, because
`u_abstain` enters **three** of the four actions, not one — `abstain`, `gather` and `ask` all
carry it (`utility_by_action`). Computed against the deployed rule instead, at the ledger
ceiling `p1 = 0.8706`:

| `u_abstain` | the exhausted argmax | reading |
|---:|---|---|
| **0.000** (today) | `abstain` | silence is free, so silence wins |
| −0.100 | `abstain` | |
| **−0.149** | **`ask_clarify`** | the first thing pricing silence buys is **a question** |
| −0.500 | `ask_clarify` | |
| −0.900 | `ask_clarify` | |
| **−0.982** | **`report`** | only here does it buy **an answer** |
| −2.000 | `report` | |

**Pricing abstention buys a clarifying question long before it buys a commit**, and the band
where it buys a question is wide (−0.15 → −0.98). To reach a commit at today's ceiling,
silence would have to be priced at **−0.98 — as costly as forgoing a correct answer
outright** (`u_correct = 1.0`). That is a much stronger claim about the owner's preferences
than "silence isn't quite free", and it is the claim the −0.256 figure would have smuggled in.

## 3. A second finding, offered as a possible artefact rather than a preference

At the recorded posterior, `ask` beats `abstain` iff
`p1 > lambda_int / (u_correct − u_abstain)` = **1.0000000000000078**.

`ask` is therefore unreachable **by 7.8 × 10⁻¹⁵** — a floating-point hair, not a margin. The
gauge is sitting exactly on the degenerate point where asking a clarifying question is
*precisely never* worth it, because `lambda_int` was elicited at 1.0 and `u_correct` is fixed
at 1.0. Any negative `u_abstain` at all tips it (§2's −0.149 row).

**This is flagged, not interpreted.** It may be a real preference — the owner may genuinely
never want to be asked. But a knife-edge is an unusual shape for a preference, and it is
worth one sentence of confirmation before another arc builds on "the engine never asks".

For contrast, the same arithmetic gives `gather`'s bar as
`kappa_att / (u_correct − u_abstain)` = **0.0339** — it wins above 3.4% credence, which is
`C3`'s "96–98% of the range" reproduced independently from the utility table rather than from
the replay.

## 4. Options and prices

| | option | price | what it buys | what it costs |
|---|---|---|---|---|
| **A** | **Change nothing.** The residue stands as recorded; `r46`'s numbers are published beside it. | **$0** | The record stays honest and no measurement is perturbed. `GD-18`'s rejection of "fix the gauge to move a reading" is upheld in the strongest form. | The engine keeps abstaining; every §18 bar is read with an empty commit column, indefinitely. |
| **B** | **Confirm or correct the `ask` knife-edge only** (§3) — an elicitation question about `lambda_int`, not about `u_abstain`. | **$0** to ask; a re-elicitation if it moves | Removes a degenerate point that no one chose. Independent of the commit question. | If `lambda_int` moves, prior gate readings were taken under a different gauge and must say so. |
| **C** | **Re-elicit `u_abstain` on its own merits**, ignoring what it does to any threshold. | one elicitation | If silence genuinely has a cost, the gauge should say so regardless of consequence — and §2 says the consequence is a *question*, not a commit, which is a benign place to land. | Any re-elicitation moves every historical EU comparison; the arms of past runs are not re-comparable without a declared boundary (`M-14`). |
| **D** | **Set `u_abstain` to clear the commit bar** (≈ −0.98). | one edit | Nothing worth having. | **Rejected already** by `GD-18` and by `M-4`: it is tuning the objective to make a measurement come out, and §2 shows it would also assert a preference — "silence is as bad as losing a correct answer" — that no one has stated. Listed only so the interview does not have to rediscover why it is refused. |

**Recommendation: B, then A.** B is a $0 question about a value that is almost certainly an
artefact and is *independent* of the commit question, so it can be settled without touching
the residue. A holds the residue where `r35` put it. C is a real option but should follow B,
not precede it — re-eliciting `u_abstain` while `lambda_int` sits on a knife-edge would move
two gauge constants on one reading, which is the r30b mistake in the objective rather than in
a lever.

## 5. What this conferral does NOT ask for

It does not ask to move `u_abstain`, does not propose an `src/` change, and does not make any
§18 bar readable — §3 of `r46-readable-surface.md` stands unchanged whatever is decided here.
The commit column stays empty under options A, B and C alike.
