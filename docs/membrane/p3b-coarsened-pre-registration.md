# P3b — pre-registration of the coarsened-lattice differential gate (A3-coarsened)

**Frozen 2026-08-17, before any coarsened-Δ number exists.** This document fixes the
lattice, the arms, the bar, the decision rule, and the stated limits *blind* to the result it
will produce, and is committed on its own ahead of the run (the P3 precedent,
`p3-pre-registration.md`, commit `839ba2e`). Register §17.6 will hold the results and cite
this file; this file is not edited after the run.

## What is (and is not) blind

Already seen, and therefore the **hypothesis under test**, not a result:

- P3's A3 (FULL lattice) **FAILED** the differential gate against the credence baseline —
  P(Δ>0.05) = 0.003, Δ̄ = −0.338 (register §17.5): held-out, the full 17-indicator lattice
  over-asserts.
- P3's A1/A2 **containment** number for the coarsened variant: leader-credence-only priced
  at **+0.284 EU/q held-out** — the only EU-positive variant — because it responds only in
  the `ge90` bucket, where held-out correctness was 1.00. That is a policy-vs-abstain
  number; it says nothing about the *differential* against the baseline, which is what
  adoption requires (register §17.5 named this as the one measurement A3 did not make).

Not seen — the thing this pre-registration fixes the method for: **A3-coarsened**, the same
differential gate P3 ran, over the coarsened lattice's held-out acts. The gate constants δ
and level were frozen in `life_agent/core/gate.py` (bayesian-foundations §8) and are not
re-chosen here.

In one line: **the coarsening rescued the policy's sign against abstention; P3b asks whether
it also beats the owner's outside option — the bar re-earning the flip actually requires.**

## Data (fixed — verified identical to P3's window)

- **Evidence stream:** the keyed verdict replay (`p3_gate.load_keyed_replay`) over the ledger
  as of 2026-08-17: **193 ticks / 84 distinct questions, 144 correct / 49 wrong, 190 ticks
  carrying a leader credence** — byte-for-byte P3's window (the ledger has not moved since
  2026-07-30). Ledger file hashes (sha256, first 16): `decisions.jsonl 232a9f7b27a74cb5`,
  `reactions.jsonl 374fe1d475d2e78a`, `claude_verdicts.jsonl c224281ce09df5c6`. The run
  passes `--expect-ticks 193 --expect-questions 84`; the harness **refuses** on drift.
- **Ū:** the `said@1` boot row on `$LIFE_AGENT_KB/membrane/shadow.jsonl` — u_correct 1.0,
  u_wrong −8.8301, u_abstain 0, u_hedged 0.3964, lambda_int 1.0009. Under it the
  restricted commit rule (`LR.commits_respond`, gather excluded, ask+abstain kept) fires at
  **p1 ≥ 0.899**; the full-menu bar is 0.9962 (not the commit rule; stated for the record).
- **P(U):** `UT.posterior` over `$LIFE_AGENT_KB/utility/{model.yaml, elicitations.jsonl}` —
  the current five-line elicitation file (u_wrong, lambda_usd, u_hedged, lambda_int,
  u_wrong_scoped; the last three added 2026-08-17 at their prior means, foundations §14).
  Disclosed: P3's P(U) had two lines; the three additions narrow, they do not move, the
  marginals P3 sampled. A3-FULL is NOT re-run under the new P(U) — its record stands.
- **Held-out unit: the question** (grouped LOO), exactly as P3.

## The lattice under test (fixed)

- **Families:** `("leader-credence",)` — the coarsening drops `n-candidates`, `p-none`,
  `n-obs`, and the three flags. Namespace `["t", leader-credence=lt50 | 50to70 | 70to80 |
  80to90 | ge90, "act"]`; **5 guards**; menu and `utility_said(Ū)` byte-identical to the
  FULL world (`LR.handshake_for`; the drift guard `tests/test_lattice_replay.py`
  `test_narrowing_drops_the_other_families` pins the narrowing).
- **Commit rule:** `LR.commits_respond` — the restricted argmax at the probed p1.
- **Aggregation to a question act:** `p3_gate.question_acts` — report iff a majority of the
  question's ticks committed respond (tie → respond, anti-flattering); when reporting,
  correct = strict majority of the responded ticks' labels (tie → wrong).

## Arms (produced)

- **Typed:** the coarsened lattice's held-out per-question acts.
- **Baseline:** `ff-v2-baseline-m3off`, arm `baseline` (`vectors.jsonl`), corpus
  `questions_sha256 = b89f829a…` — the same 74 joinable questions P3 joined; the 10
  non-joiners are named in the artifact, never dropped.
- **Join:** `hash_to_qid` recomputing `DEC.question_id` over `questions_v2.yaml`.

## The bar and the decision rule (frozen)

`GATE.delta_posterior(paired, P(U), oracle_p = 0.9, n_draws = 20000, seed = 8675309)`;
**δ = 0.05, level = 0.90** (`core/gate.py:73,76`, not re-chosen). PASS iff P(Δ>δ) ≥ level.
Artifacts: `a3_gate-leader-credence-only.md`, `a3_paired-leader-credence-only.jsonl`,
`a3_meta-leader-credence-only.json` (families + resolved indicator vocabulary as
provenance) — variant-suffixed so P3's FULL record is never clobbered.

**A PASS is evidence toward re-earning the flip and does not by itself flip
`LIFE_AGENT_MEMBRANE_LIVE`** — that stays an owner authorization (P3's rule, kept). A FAIL
closes the coarsening as a re-earn route on this ledger.

## Engine (fixed)

`proplang-host` built from the pinned commit **`1a0cea7`** (W4 freeze) in a worktree at
`~/git/worktrees/proplang/pin-1a0cea7`; binary sha256 (first 16) `1d00864383362213`.
Byte-compatibility with the §17 record: the FULL variant is re-run in the same execution
and its A1/A2 numbers must reproduce P3's (`a1_a2.json` FULL: policy EU/q, P(U) interval)
— a mismatch voids the run before the coarsened Δ is read.

## Predictions (recorded blind)

- The coarsened arm asserts on **few** questions (only those whose majority tick sits in
  `ge90` above the 0.899 commit bar): I expect a typed answer rate well under 0.3 against a
  baseline near 0.9.
- The disagreement region is therefore dominated by `abstain × report ✓` at ≈ −0.333/q,
  with the coarsened arm's `report ✓ × report ✓` agreements contributing 0. **I predict
  FAIL** — Δ̄ negative, P(Δ>0.05) far below 0.90 — but a **different failure mode from
  FULL's**: FAIL-by-abstention (too little reach), not over-assertion. The reading must say
  which it is.
- If it PASSES, it does so on a small disagreement set; a PASS on ≲ 10 disagreement rows is
  named as under-powered in the reading, not celebrated.

## Stated limits

- The `ge90 = 1.00 correct` bucket is one ledger's fact; its robustness to corpus shift is
  untested (register §17.5 named this). P3b does not produce a second corpus.
- 74 joined questions; the bootstrap's small-n width is real and reported, not hidden.
- The engine at the pin predates HEAD by many commits; conformance binds to the wire
  (`membrane-wire.md` §§1–3), and the FULL-reproduction check above is the byte-compat
  gate.
