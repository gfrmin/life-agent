# Ideas to steal from `bayesian-orchestrator`

> **Status: a sourced idea-bank, not the plan.** Each entry names where it would land in
> life-agent and the trigger that would make it worth doing. Reviewed 2026-06-17 against
> [`sheinkmana/bayesian-orchestrator`](https://github.com/sheinkmana/bayesian-orchestrator).

## What the source is
A Bayesian **model-routing** evaluator (Python/JAX/NumPyro/LangGraph, MIT). It fits a
hierarchical-logistic reliability model `P(correct | model, subject, question-length, cost,
confidence, latency, tokens)` with partial pooling (HMC-NUTS), routes by expected utility
`P(correct) − λ·cost`, optionally takes a myopic-VOI second opinion (Noisy-OR adjudication),
and evaluates **offline on a frozen full call-matrix** (4000 q × 3 models, 1200 explore /
2800 held-out) with proper scoring + bootstrap CIs.

Its *thesis* — "don't trust the LLM's self-confidence; fit reliability externally and act by
EU" — is already ours ([`bayesian-foundations.md`](../bayesian-foundations.md), PRINCIPLES).
What's transferable is a set of **specific techniques**, below. (Where life-agent is already
ahead, see the last section — don't import those.)

## The ideas

### B1 — A stored full call-matrix to de-starve the §8 gate *(highest value)*
The §8 decision-weighted adoption gate (`core/gate.py`) ran once and **FAILED** — not on the
merits but on data: P(Δ>δ)=0.848 over a **21-question** corpus, typed answer rate 0.11. Its
two named levers (narrow P(U), raise answer rate) both starve for evaluation data.
- **Steal:** for a fixed question set, run *every* extraction strategy / model / family once
  and persist the result matrix; then typed-vs-monolithic — and any other policy pair —
  compares **offline and exactly**, with no model re-runs. Her stratified sample + complete
  matrix is the template.
- **Lands in:** the eval harness behind `core/gate.py` and `run_eval`; pairs with the
  outcomes stream (`core/outcomes.py`).
- **Trigger:** next time the gate is the critical path. This is the most direct way to give it
  enough N to move off 0.848.

### B2 — Learn instrument reliability as a covariate fit, not stated constants
`core/lookup.py` currently **states** the source-authority lattice (`authority_for`, the
0.95/0.90/0.80 classes) and the subject/recency covariates, and learns only a **flat pooled**
ρ per instrument (`extractor_reliability`). The code's own comments say these are "calibrated
later from outcomes." Her `_fit_reliability_model` is that calibration: reliability as a
function of covariates with partial pooling, fit from the outcomes stream.
- **The honest tension:** her fit is non-conjugate logistic + pooling via NUTS/NumPyro, which
  collides with the conjugate-only credence seam (`core/brain.py`) and the zero-new-deps rule.
  Two clean resolutions: **(a)** per-cell Beta folds keyed on (instrument × source-class ×
  subject × recency) — life-agent **already has this idiom** in `narrative.cell_posteriors` —
  accepting that bucketed conjugate can't pool across cells or use continuous covariates; or
  **(b)** decide reliability-calibration is the one place a small logistic fit earns the
  dependency. The covariate *menu* (subject, length, source-class, recency,
  self-confidence-as-audited-feature) transfers either way.
- **Lands in:** `lookup.py` (`authority_for`, `extractor_reliability`), reusing
  `narrative.cell_posteriors`.
- **Trigger:** when stated authority/covariate constants become a measured source of
  confident-wrong reports.

### B3 — Calibration diagnostics for the outcomes stream *(cheap, do anytime)*
`core/outcomes.py` scores with log score + Brier only. She also reports **ECE**, a
**reliability diagram**, **AUROC**, and **LOO-ELPD**, and her posterior is demonstrably
calibrated (held-out ECE 0.028). She also runs a clean **feature ablation** (fit with vs
without self-confidence; report the Brier/log/AUROC delta) to justify a covariate before
trusting it.
- **Steal:** add ECE + a reliability diagram over the outcomes log; adopt the
  fit-with/without-feature ablation as the gate for admitting any new covariate.
- **Lands in:** `run_eval` / `core/outcomes.py`.

### B4 — Myopic-VOI second-opinion as a reference design for the deferred governor
Her second-call rule `Δ = E[max(b, V_m)] − b − λ·E[c]` (with empirical group future-values)
is a concrete, working myopic-VOI recipe.
- **Steal (later):** reference design for the **deliberately deferred** VOI governor
  (`bayesian-foundations.md` §12 stage 6 / `system-design.md` L3) and for any future
  local-Ollama-vs-cloud extraction routing.
- **Trigger:** when the governor or multi-model extraction routing is actually on the roadmap.
  Premature now.

### B5 — Eval ops hygiene *(copy when the corpus grows)*
Append+fsync checkpoint, resume-by-validating-cached-pairs, versioned pricing snapshots, fixed
seeds, a network-free fake provider for smoke tests, and a **gated auto-recommendation** (the
report only says "adopt" if every robustness gate passes).
- **Trigger:** once B1's call-matrix corpus is large enough that re-runs and resumes matter.

## What NOT to steal (life-agent is already ahead here)
- **Correlated errors.** Her README flags this as an unhandled gap and her `_dependence_caution`
  is a binary warning. `lookup.py`'s lineage tempering (`_BETA_ANCESTRY`, `_BETA_MODEL`;
  m correlated observations count as `1 + β(m−1)`) already prices it continuously. *We give
  this to her, not the reverse.*
- **The adoption decision.** Her gates use a point λ + a bootstrap CI on a policy difference.
  `core/gate.py` integrates the decision over a P(U) prior **and** the Bayesian bootstrap
  jointly (`P(Δ>δ)≥level`) — strictly more honest.
- **The whole offline-NUTS pipeline** as an architecture: it conflicts with the conjugate
  credence seam. Take the *ideas* (B1–B5), not the engine.

## See also
[`docs/candidates/brain-design.md`](./brain-design.md) and the credence-pi sibling note
`apps/credence-pi/IDEAS-FROM-BAYESIAN-ORCHESTRATOR.md` (the direct head-to-head — credence-pi
and bayesian-orchestrator do the same job by opposite means).
