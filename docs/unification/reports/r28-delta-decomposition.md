# r28 — the Δ decomposition: what the adoption gate has actually been measuring

**Status: PRE-REGISTRATION (frozen).** Criteria C1–C4 below are committed BEFORE any
`src/` change and before the corrected reading is published. Results append after.

Register: bayesian-foundations §8 (the decision-weighted adoption gate), §14 (the live
empirical ledger). Instrument: `core/gate.py`. Cost: **$0** — this checkpoint reads the
existing paired records and changes what a report publishes. It buys no run.

---

## 1. Why

The §8 gate is the instrument every adoption ruling in the §14 ledger rests on. Its
headline is a posterior over `Δ = EU(typed) − EU(baseline)`. Twelve runs have been read
from that headline. **The headline has never been decomposed**, and the decomposition
changes what it means.

### Verified before freezing (each checked against the artefact named)

- **V1 — the baseline is the owner's outside option, and has been since run 6.**
  Every one of run 18's 104 rows in
  `paired-gate-20260826T083356.jsonl` carries `baseline: "raw-deliberative-replay"`.
  Confirmed by direct read, not inferred from prose.
- **V2 — that arm is Claude Code with corpus access.** The replayed fair-fight run's
  `run_meta.json` records `entrypoint: "claude -p"`,
  `claude_version: "2.1.215 (Claude Code)"`,
  `allowed_tools: "mcp__pkm__search,mcp__pkm__extract"`, `max_turns: 40`. It is the
  comparator the owner actually uses, replayed from 2026-07-19 on a model one generation
  behind today's — so it is a **floor** on the outside option, not a ceiling.
- **V3 — the baseline's spend is imputed, not metered.** That run's summary records
  `cost status: {'estimated': 104}`: the $39.01 comes from the CLI's own
  `total_cost_usd` token pricing. Under a flat-rate plan it is not money that left an
  account. (The typed arm's spend is metered the same way and is immaterial at $0.37.)
- **V4 — the entire Δ is the spend term.** Point-estimate arithmetic at the elicited
  latents (`u_wrong −9`, `lambda_usd 1.5`) over run 18's own rows:
  **Δ = +0.577 as run**, and **Δ = +0.014 with the baseline's spend uncharged**. On
  delivered answers the two arms are level; the baseline delivers **95 correct answers
  to typed's 61**. This is a sizing arithmetic at point values, NOT a gate reading —
  the real read marginalises over P(U) × the bootstrap, and is what C1 builds.
- **V5 — the report cannot show this.** `render_report` gained a `baseline` parameter in
  K4, so the arm is now named correctly. It publishes **no decomposition**: `Diagnostics`
  carries no spend field, and `realised_utility` folds the `−lambda_usd · cost_usd` term
  into a single number before any diagnostic sees it.
- **V6 — the split is exact, not an approximation.** `realised_utility` is affine in the
  sampled latents given the actions, so
  `Δ = Δ_answers + lambda_usd · (c̄_baseline − c̄_typed)` holds **per draw** and therefore
  in expectation at Ū. The decomposition is arithmetic, not a model.

### What this checkpoint is not

It does not re-price spend. Re-basing `lambda_usd` on the constraint actually faced (a
usage window rather than an imputed dollar) was offered to the owner on 2026-08-28 and
**declined**; spend stays at `lambda_usd × cost_usd` and abstention stays at the gauge
zero. This checkpoint makes the existing price **visible**, so that the successor arc's
readings can never again confound an answer-quality effect with a price effect. That is
the whole of its scope.

It also does not re-run anything. Every number it publishes is computable from records
already on disk.

---

## 2. Frozen criteria

| | Criterion | How it goes RED |
|---|---|---|
| **C1** | Every gate report publishes the decomposition `Δ = Δ_answers + Δ_spend` over **the same row set Δ is computed over** (the Δ-included set, i.e. after availability censoring), together with each arm's realised spend and its correct / wrong / abstain counts. | A mutation that drops the spend split from the rendered report, or that computes it over all rows instead of the included set, fails a named test. |
| **C2** | `Δ_answers` and `Δ_spend` are computed **independently** and their sum is asserted equal to the at-Ū mean gap over the same set. The identity is a test, not a comment. | A mutation that derives one term by subtracting the other from the total makes the identity vacuous; the test pins both against separately-computed quantities and fails. |
| **C3** | The value naming the baseline in the rendered report and the value stamped into every paired row are **the same object**, pinned by a drift gate — the divergence that made twelve reports quote the wrong arm cannot recur structurally. | A mutation that passes a different literal to `render_report` than to the paired-row writer fails a named test. |
| **C4** | The in-tree §14 prose naming the gate's baseline is corrected to name the arm the records carry. Where a summary describes a run's comparator, it says what `paired-gate-*.jsonl` says. | Verified by reading the corrected prose against the recorded tag; a residual "monolithic" describing a replay run is a defect, disclosed. |

**Non-goals, stated so they cannot be claimed later:** no change to Δ's value, to the
verdict, to `MATERIALITY_DELTA`, to `GATE_LEVEL`, to the utility model, or to any
decision path. C5 below is the pin.

| | |
|---|---|
| **C5** | **G2 — the 314-fixture replay, pure equality on `m5-base`.** This checkpoint touches the report and the diagnostics; it must move no fixture. |

---

## 3. Method

1. `Diagnostics` gains defaulted spend fields, so every existing construction of the
   dataclass is unchanged (the codebase's own convention for additive record change).
2. `_diagnostics` computes, over the **Δ-included** rows:
   - each arm's mean realised spend in dollars;
   - `Δ_spend` at Ū as `lambda_usd · (c̄_baseline − c̄_typed)`;
   - `Δ_answers` at Ū as the mean gap with the spend term zeroed — obtained by valuing
     both arms at `lambda_usd = 0`, which is the deployed `realised_utility` reading its
     own spend term, **never a re-implementation of it**.
3. `render_report` publishes the two terms beside the headline, with the arms' raw dollar
   totals and outcome counts, so a reader can reconstruct the arithmetic.
4. The §14 prose is corrected (C4).

The standing lesson is load-bearing here: **a census must read the deployed rule end to
end, never re-implement the constant it prices.** `Δ_answers` is therefore obtained by
calling `realised_utility` with the spend rate set to zero, not by writing out the
correctness terms a second time. A second spelling of the answer term is exactly the
defect class this project has shipped four times.

---

## 4. Verification

1. Full suite, ruff, mypy — evidence pasted.
2. PII check exit 0 with the private name layer live.
3. C1–C3 each demonstrated **RED by its named mutation, then restored**, transcript below.
4. `PYTHONHASHSEED=0 scripts/collapse_replay.py --checkpoint m5-base` — 314/314 pure
   equality (C5).
5. The corrected reading published for run 18 off its own record.

---

## RESULTS

_(appended after the reading — nothing above this line changes)_
