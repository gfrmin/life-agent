# r14 — collapse M4: the utility atom + the one price table (Q-O3, §4)

**Pre-registration.** Committed BEFORE any `src/` change on this branch. Frozen criteria
are not renegotiable at read time; blind amendments (before any gate runs) must say what
they correct. Cap-the-arc applies. Every clause below was checked against the artefact
it names on 2026-08-25 (master `d4b7b57`) — the r13 lesson applied.

## STATE (recon, master `d4b7b57` — M3 merged and deployed)

- **The atom already has one source and one derived consumer:** `core/decide.py
  u_assert` is the written atom; `LK.action_utilities` already derives its report rows
  from it (`u_assert(1.0/0.0, u_bar)` — the docstring names the derivation).
  `GATE.realised_utility` does NOT spell the atom: its `report` branch reads
  `u["u_correct"] if resp.correct else u["u_wrong"]` — the atom's two endpoints,
  un-derived; `hedge`/`report_scoped`/`ask_clarify`/`abstain` are their own vocabulary
  reads (not `u_assert` outcomes — correct as they are).
- **`lambda_usd` has two different defaults in two modules** (the E-5 defect, live):
  `EX:390` `u_bar.get("lambda_usd", 1.0)`; `GATE:171` `u.get("lambda_usd", 0.0)` — the
  latter's docstring DECLARES the 0.0 a comparability pin for pre-elicitation models.
  `load_model` fails loud on a missing `lambda_usd` latent (REQUIRED_LATENTS, pinned by
  tests), so both defaults are dead-in-practice for every live fold.
- **The tier rhos already flow as priors:** `menu_rows` computes
  `_conditioned_rho(curves, edge, t["rho"], t["rho"])` — the declared value is the
  curve-conditioned read's cold fallback, not a fixed reliability. The census's
  "become priors" is the CURRENT semantics; what M4 moves is the declaration's home.
- **Census drift found (three rows already dead):** `_JOINT_MODEL`/`_JOINT_RHO` are
  gone from the bridge and `_RESCUE_RHO` + the `min(0.5, conf)` clamps are gone from
  the executor (the r09 JOIN/retire arc removed them); E-3/E-11's deaths already
  happened. `_ORACLE_P` already has one home (`LK:198`) with `gate_splice` reading it;
  `run_eval`'s read is verified at phase 2.
- **Q8's premise is already discharged:** the only `map_action` in the tree is
  `membrane/coarse.py:105`, called by the live shadow worker (`shadow.py:698`) — it
  already lives in the shadow namespace as a measurement function. No `CO.map_action`
  exists outside the membrane.
- **The price constants in scope:** `EX:54-58` `_TIER_MODEL`/`_TIER_RHO`/`_GATHER_RHO`;
  `EX:65-100` `DEFAULT_TRANSFORMS`/`DELIBERATE_TRANSFORM`/`_DELIBERATE_FALLBACK_RHO`;
  `EX:168` `_RE_EXTRACT_MODEL`; `gather_outcomes.py:47` `GROW_ACTUATORS` (already
  served by the bridge's `/grow_menu` — D-7's wire half exists);
  `core/pricing.py:20,33` `PRICING_VERSION`/`PRICE_TABLE` (the spend half);
  `LK:198` `_ORACLE_P`; M3's `reliability.PRIORS` (the prior column's interim home).

## The mandate (design §8 M4 row; §4.1; §4.2)

1. **The one price table.** `core/pricing.py` becomes THE table (it already owns the
   spend half and the version): a declared `MENU` — one row per priced edge
   (three corroborate tiers · deliberate · the two guards and grow actuators · the
   re-read) — each row `edge`/`model`/`cost`/`prior`/`kind`, data only.
   `EX.DEFAULT_TRANSFORMS`, `EX.DELIBERATE_TRANSFORM`, `EX._TIER_MODEL/_TIER_RHO/
   _GATHER_RHO/_RE_EXTRACT_MODEL` and `GO.GROW_ACTUATORS` become bindings/readers of
   table rows — no priced constant is declared outside the table. `PRICING_VERSION`
   bumps (the table grew; its identity contract is unchanged).
2. **The prior column.** `reliability.PRIORS` (M3's interim home) moves INTO the table
   module as the reliability column (§3.2's own text: "the priors declared per
   (edge, cell) in the price table's reliability column"); `core/reliability.py`
   imports it — the fold stays where M3 put it, the DATA lives in the table, one
   spelling total.
3. **The atom derivation (D-1).** `GATE.realised_utility`'s `report` branch is spelled
   through `u_assert(1.0 if resp.correct else 0.0, u)` — an exact rewrite (the other
   branches are not atom outcomes and stay). `W.utility_by_action` is NOT touched
   (§6.2: the membrane world's own utility is the register's second world).
4. **E-5 — one exchange rate.** Both `lambda_usd` defaults die: `EX:390` and `GATE:171`
   read `u[...]["lambda_usd"]` and a missing latent fails loud. The gate docstring's
   "comparability pin" claim is tested, not trusted: if any archived-replay path feeds
   a pre-elicitation `u` dict, it surfaces as a RED test at phase 3 and is resolved by
   blind amendment with the evidence in hand (expectation: none does — every live fold
   passes REQUIRED_LATENTS).
5. **Q8 DECIDED (this report):** the M3 lane DELETES at M5 (the design's default), and
   `map_action` survives exactly where it already lives — `membrane/coarse.py`, a
   measurement function in the shadow namespace, never a lane. (The rename Q8
   contemplated already happened; the evidence is in STATE.)
6. **The M5a/M5b split** is signed in this report's RESULTS from M4's own 7.2 evidence
   (default: single M5; the split only if the fixture work here shows the family-choice
   and grow-target moves are not bisectable in one step).

Out of scope: covariate parameters, sizing/timeouts, the gate's frozen δ/level (§6.1's
own exception), the membrane world's defaults, every M5 absorption move.

## Machine directions for 7.2

**None — pure equality on all 314.** Every move is a relocation or an exact rewrite:
menu rows carry the same numbers from a new home; the conditioned-rho flow is untouched;
the atom rewrite is algebraically identical; the lambda_usd defaults are dead-in-practice.

## Gates (frozen; any FAIL is a STOP for an owner ruling)

- **G1** — suite green + this checkpoint's tests; `ruff` + `mypy` clean. TDD (RED first).
- **G2 (7.2)** — 314/314 pure equality on the final tree.
- **G3 (7.3)** — the priced frozen-regime gate (run 16), the run-15 recipe verbatim
  (tree gate = run-14 lineage + M3 pins + M4 pins), comparison arm run 15's meta,
  **cap $8**. Conjuncts: (a) P(Δ>0.05) ≥ 0.90; (b) zero NEW wrong commits (NEW = not
  wrong in run 15's typed arm: {the two standing rows + the warm-deliberate row});
  (c) no named class worse; (d) every decision row states `policy="all-to-date"` and
  the tree pins the gate's frozen fold (run 15's d1/d2, verbatim).
- **G4** — 7.4 not run (no store or writer moved; declared per §7.4).
- **G5** — PII clean, hooks armed.

## Predictions

- P1: G2 reads 314/314 zero diffs on the first complete build.
- P2: the menu the daemon serves (`/grow_menu`) and the executor's transform rows are
  byte-identical before/after (pinned by a test that snapshots both from the OLD
  declarations before they die — written RED against the new table first).
- P3: no archived-replay path feeds a pre-elicitation `u` (the E-5 fail-loud lands
  without a compat guard).
- P4: run 16 reads run 15's numbers (behaviour-preserving on warm caches), zero NEW
  wrongs, answer rate within ±0.06 of 0.62.
- P5: live calibration moves ONLY by run 16's own gate rows under its `run_id`
  (the r13-corrected accounting: decisions/outcomes append to the live ledger;
  reactions untouched).

## Deviations

Disclosure items in the final report; rollback = revert the branch (one PR). After
green: results appended, mirrors updated, PR/CI/merge, deploy to the live box, then M5 (single or
split per item 6) under its own pre-registration.

## RESULTS (read 2026-08-25/26, appended after the gates ran — nothing above changed)

Execution was one TDD phase on branch `collapse-m4` (implementation commit `7949266`):
the P2 snapshot tests written RED against the not-yet-existing table (all six failed for
the right reasons), then the table (`core/pricing.py`, version 2), the bindings
(executor/gather_outcomes/reliability serve the SAME objects), the atom spelling in
`realised_utility`, and E-5's fail-loud.

### Gate readings

- **G1 — GREEN.** 2724 passed, 35 deselected; ruff clean; mypy clean (221 files).
- **G2 (7.2) — GREEN.** 314/314 pure equality, re-verified on the final committed tree.
- **G3 (7.3) — PASS on all four conjuncts.** Run 16 (`gate-20260826T003710`), comparison
  arm run 15's meta, spend $0.60 of the $8 cap, elapsed 1338s.
  (a) P(Δ>0.05) = **0.961** (gate ≥ 0.90); Δ̄ = **+0.519** [+0.081, +1.003].
  (b) NEW wrongs vs run 15: **none** — typed wrongs are exactly the two standing rows,
  a strict subset of run 15's three.
  (c) named classes: the superset-confirm row withholds (as in runs 14–15); the
  warm-deliberate row converts wrong → withheld — better, not worse.
  (d1) all 102 of the run's decision rows state `policy="all-to-date"`,
  `regime="full"`; (d2) the firing script's tree gate pinned `7949266`
  (run-14 lineage + M3 + M4 pins) before spend.
  Answer rate: typed 0.62 · mono 0.97; withheld miss 2 · dispersed 37.
- **G4 — 7.4 not run** (no store/writer moved; declared).
- **G5 — GREEN.** No corpus values; hooks armed.

### Predictions vs readings

- **P1 — CONFIRMED.** 314/314 zero diffs on the first complete build.
- **P2 — CONFIRMED.** The snapshot literals (dumped from the pre-move declarations)
  pin the table AND the bindings; the bindings are the same objects (`is`, not `==`).
- **P3 — CONFIRMED.** The E-5 fail-loud landed with no compat guard; the two tests that
  had pinned the silent defaults (`test_run_pass_without_the_rate_latent_keeps_legacy_costs`,
  `test_realised_utility_without_the_rate_latent_is_byte_identical`) flip to pin the
  loudness — the never-silently-weaken direction (a silent fallback died; nothing else
  fed a pre-elicitation vector).
- **P4 — CONFIRMED on both exact clauses; the headline moved by one named row.**
  Zero NEW wrongs ✓; answer rate 0.62, dead centre of the ±0.06 band ✓. The pair
  0.907/+0.421 → 0.961/+0.519 is carried entirely by the warm-deliberate wobble row
  landing withheld (the disposition run 14's warmed re-read predicted) — the judge
  flips are the identical five cached mono-side rows, and the movement sits inside
  r08's measured commit-wobble floor (2). Behaviour-preserving modulo the standing
  named wobble; both dispositions of that row are now observed live.
- **P5 — CONFIRMED, one interleaved live row disclosed.** Append-only verified by
  prefix hash (the ledger head before the run hashes identically as a prefix of the
  ledger after): +102 decisions and +22 outcomes, all under the run's `run_id`;
  reactions byte-identical. One live ask-surface decision row (`run_id="ask"`,
  correctly policy-stamped) interleaved between fingerprint and read — the dogfood
  surface working as designed, not gate leakage.

### The two decisions this report owes

- **Q8 — DECIDED: the M3 lane DELETES at M5** (the design's default). Evidence: the
  only `map_action` in the tree already lives in the shadow namespace
  (`membrane/coarse.py:105`, called by the live shadow worker) — the rename Q8
  contemplated happened in an earlier arc; nothing outside the membrane needs it.
- **The M5a/M5b split — SIGNED: single M5.** M4's 7.2 work surfaced no evidence of
  non-bisectability: every fixture class replays under pure equality through both the
  M3 and M4 moves, and the absorption's two halves (family choice + grow-target) touch
  disjoint fixture populations (A-loop vs B-traces). If M5's own 7.2 contradicts this,
  the split re-opens as a blind amendment under M5's pre-registration — evidence first.

### Disclosures (cap-the-arc)

- **D1 — E-5 removed a PRE-REGISTERED contract.** The gate's 0.0 default was documented
  as "the run-5 comparability pin… pre-registered" (its own docstring and
  `RealisedResponse`'s). The r14 freeze argued it dead-in-practice (REQUIRED_LATENTS
  guarantees every live fold carries the latent) and the suite confirmed: the only
  consumers feeding latent-less vectors were the two legacy-pin tests themselves and
  hand-built fixtures. The pin's purpose (comparability of pre-run-6 readings) is
  history — those readings are published in their reports, not recomputed.
- **D2 — the tier fallback literal.** The executor's unknown-corroborate-tier default
  was re-spelled to the table's `_RE_EXTRACT_MODEL` — same value, one spelling;
  behaviourally unreachable today (every scheduled tier is in the map).
- **D3 — three more test files carried latent-less synthetic posteriors**
  (loss_ledger, p3_gate, fairfight_runner) — extended with a zero-rate point latent
  (numbers unchanged); the fairfight meta test's `pricing_version == 1` literal now
  reads the table's own version.
- **D4 — run 16 was externally SIGTERM'd twice before it could fire a question.** Root
  cause: the launching agent session's restarts reap its own background children; both
  kills tore down cleanly via the script's trap with ~zero spend and no ledger rows.
  The successful firing ran as a transient `systemd --user` unit, outside any session's
  process tree — the durable recipe for priced runs from here on.

### Verdict

**M4 is DONE.** The price table has one spelling (`core/pricing.py`, PRICING_VERSION 2)
and every consumer binds the same objects; the utility atom is spelled where realised
utility is computed; the rate latent is REQUIRED and fails loud. All gates green,
including the series' best priced reading (0.961 / +0.519) with zero wrong commits
beyond the two standing rows. Q8 is decided (the M3 lane deletes at M5) and the split
is signed (single M5). The ladder resumes at **M5 — the argmax absorption**, under its
own pre-registration.
