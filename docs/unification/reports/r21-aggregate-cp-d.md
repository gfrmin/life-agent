# r21 — aggregate family CP-D: instrument, plumbing, and the priced gate

*2026-08-26. The closing checkpoint of Stage 2a, opened by r20's RESULTS. The
pre-registration below is committed BEFORE any `src/` change; results append per phase
under RESULTS. Every frozen conjunct FAIL is a STOP for an owner ruling (keypress map);
anomalies en route are disclosure items (cap-the-arc).*

## Pre-registration (frozen)

### The split (prereg-time decision, the M5-precedent licence in design §13)

CP-D runs as **two phases inside this one report**, each with its own gate, merged as
two PRs:

- **Phase 1 — the observation instrument (pkm side, $0 on the decision path):**
  SPEC §18.14 + the `extract_amounts` transform. No life_agent decision-path change;
  the family stays un-plumbed until phase 2.
- **Phase 2 — the family (engine side, priced):** component 2, the family plumbing,
  the two-stage router, the gate machinery, the demand-led warm, then the one §8 run.

This is a split of WORK, not of conjuncts: everything below is frozen now, and phase 2
re-freezes nothing.

### Phase 1 — SPEC §18.14 + `extract_amounts`

- **SPEC §18.14** enacts design §3's schema verbatim: bounded typed line-items
  (`maxItems` 8; `kind`/`basis` closed enums; `as_of`; `amount` + `currency`;
  verbatim `amount_raw` mandatory, `label_raw` the quality discriminator; empty
  `items` a determinate success; `unreadable: true` the named indeterminate), the
  §18.5 whitespace-normalised grounding gate on `amount_raw` (and on `label_raw`
  when present) with an ungroundable amount failing the source, and the
  majority-unlabelled document flag (`majority_unlabelled: true` when over half the
  items carry `label_raw: null` — a flag on the artifact, priced downstream, never a
  drop). Change-log entry 0.19.0 (draft). The §18.13 pattern is the template: one
  producer class, one declaration per input producer (`docling`, `tesseract`,
  `pandoc`, `email`), provider `anthropic`/haiku, `cost_gate` policy,
  `post_validate` fail-loud (never cache a miss).
- **Attributed from birth (§3's instrument discipline):** the transform's executor
  edge writes `eval_edge` rows keyed `extract_amounts@<model>` from its first firing
  — the §14 extractor-ρ lesson applied prospectively, and NOT the base extractor's
  ρ-exit (which stays its own registered arc, sequenced AFTER CP-D so nothing
  confounds C1).
- **Tests (pkm governance: SPEC-first, TDD red-first, hermetic):** grounding
  accept/reject (amount grounds ⇒ item kept; ungroundable amount ⇒ source fails, not
  cached), the closed-enum validations, empty-items success, `unreadable`
  indeterminate, the majority-unlabelled flag boundary, normalisation raw/parsed
  pairing (RTL digit order and thousands separators covered by synthetic fixtures
  marked `# PII-OK`), and the idempotency double-run.
- **Phase-1 gate:** pkm + life_agent suites, ruff, mypy green; the m5-base replay
  **314/314 pure equality** (nothing on the decision path changed); SPEC committed
  before the transform code.

### Phase 2 — component 2, plumbing, router, gate machinery

**Component 2 (`core/aggregate.py`), the v0 composition — honesty per parameter:**

- Addends = the §18.14 items of the retrieved documents after the §4 refusals (kind
  filter; basis branch: an issuer roll-up when present is THE single observation of
  the period total and the series becomes slot-evidence only, else the series sums —
  which branch fired is stated in the basis line; per-currency subtotals), after
  component 3 prices the §5-uncollapsed candidate pairs (a pair reading `p_one > 0.5`
  contributes once, the resolution named in readout 1).
- `S_obs` = the deduplicated on-kind sum, `k` its count. With a covering generator
  (`estimated=True`) and named missed slots `m ≥ 1`: the **central-80% interval** is
  `[S_obs + m·q10, S_obs + m·q90]` and the point summary `S_obs + m·mean`, where
  `q10/mean/q90` are the empirical order statistics of the observed same-generator
  addend values — deterministic composition of recorded observations, no invented
  likelihood; the exchangeability-within-generator assumption is DISCLOSED in the
  basis line whenever imputation fires. `m = 0` ⇒ the interval is `[S_obs, S_obs]`.
- No covering generator (`estimated=False`) ⇒ **no imputation**: the report is
  `S_obs` with readout 2's unmodelled-recall sentence verbatim (design §2).
- The recall posterior (CP-B, wire-read) renders in readout 2 (mean + estimated
  flag); OCR-flagged (majority-unlabelled) documents' items are priced through the
  declared reliability cell — `pricing.RELIABILITY_PRIORS` gains the
  `("extract_amounts", cell)` rows, frozen: `("extract_amounts", "labelled")` =
  (4.0, 1.0) and `("extract_amounts", "unlabelled_flagged")` = (2.0, 2.0) — the
  probe's 28/40-vs-2/14 label-grounding asymmetry as a prior, weak enough for the
  graded stream to move. An item's inclusion follows the narrative per-claim
  precedent: EU-priced through its cell; **family-level abstain is derived, never
  invented** — zero includable on-kind addends after the refusals ⇒ abstain via the
  standing `decisions.withhold_reason` derivation.
- **The report renders the four blocks of design §2, always** (interval + citations;
  readout 1 with named indeterminates and named dedup resolutions; readout 2;
  the basis line).

**Plumbing (each site named, smallest honest change):** `decisions.FAMILIES` gains
`"aggregate"`; `AGGREGATE_ACTION_ORDER = ("report", "abstain")`; the
`tests/test_decide.py` partition invariants extend; `reactions.py` gains the explicit
third arm (recorded, never folded — the CP-A ruling; the arm returns no fold event and
says why); the recorder/`ask_client.post_decision` rows carry the family + the
registry `content_hash` (CP-B's replay-determinism field, mechanics — recorded, never
priced); the bridge gains the aggregate handler; `terminals.py`'s declined path
repartitions through the second-stage router; `run_eval.py` values aggregate rows
through the frozen rule below.

**The two-stage router (design §8):** `ROUTE_PROMPT` stays **byte-identical** (C0
checks the prompt hash, no model call). A new second classifier — own prompt, closed
schema `aggregate | narrative`, own cache key — runs only on the declined path;
default narrative; admits to aggregate only on a confident sum-shaped verdict.
$0 pre-run sweep on the 40-item labelled set (`route-audit-family.yaml`): **zero
narrative→aggregate false positives** is the bar; aggregate recall is reported, not
gated.

**The frozen grading rule (the gate.py extension — itself pre-registered here):**

- An aggregate report asserts the rendered central-80% interval `[l, h]` and its
  point summary. Against an external/structural gold `g`: the **Winkler score**
  `W = (h − l) + (2/α)·(l − g)·1{g<l} + (2/α)·(g − h)·1{g>h}` at `α = 0.2` (the
  rendered level), mapped affinely onto the assert atom:
  `x = max(0, 1 − W/(2·|g|))`, realised utility `u_assert(x, u) − spend`. The
  constants (α = 0.2, scale 2·|g|) are frozen here: a sharp covering interval reads
  near `u_correct`; an interval wider than twice the gold reads as wrong even when
  covering — width pays linearly; a miss pays in miss distance through the `2/α`
  term.
- **The family's new wrong-commit class — an asserted interval that excludes the
  external gold** (`g < l` or `g > h`) — is categorical, independent of `x`, and
  joins the hard clause's census from birth.
- Gold-none honesty rows are not Winkler-graded; they are read against their named
  expectations (the known-missing-slot readout fires; the no-generator scope renders
  the unmodelled-recall sentence; the count questions report the artifact census).
- Abstains grade `u_abstain − spend` as everywhere.

**The demand-led warm (frozen formula, number published before firing):** only the
aggregate set's retrieved documents are derived — never a corpus sweep. Cap =
`n_questions × k × p_derive` with `k = 20` and `p_derive` the §18.14 haiku price from
`core/pricing.py`'s menu row; the computed dollar number is published in this report
BEFORE the run fires, and the warm aborts at the cap. Warm derivations land in the
live store (write-once, key-deterministic — the §18.9 warm-through discipline).

### The one priced §8 run — frozen conjuncts (C0–C3)

- **C0 — route integrity, $0, first:** the lookup admission prompt hash is
  byte-identical to master's (no model call); the second-stage sweep on the labelled
  set reads zero narrative→aggregate false positives; aggregate recall reported.
- **C1 — regression, priced:** the 104-corpus under the run-14 frozen numbers copied,
  not re-chosen — `P(Δ > 0.05) ≥ 0.90`; **zero NEW wrong commits**; wrongs exactly
  the two standing rows. With C0 holding this reproduces run 18 nearly warm.
- **C2 — capability, priced:** the aggregate set. Hard binary (the CP-A ruling): the
  two stage-gate exhibits — (a) the fund-deposit question answered as a posterior
  with BOTH coverage readouts and the issuer's own roll-up landing inside the
  asserted interval, (b) the real duplicate pair resolved against the control in the
  priced context — plus **zero commits in the new wrong-commit class**. The
  Δ_agg-vs-narrative comparison is a **disclosed reading** (gradeable N = 11 < 15;
  the ruled threshold, unchanged — the gradeable set has not grown).
- **C3 — the hard clause:** across both sets, no named wrong-commit class worse,
  including the new class.
- **Budget:** the run ≤ $2 + the published warm cap. The run fires as a transient
  `systemd --user` unit; a FAIL on any frozen conjunct is a STOP for an owner
  ruling; PASS closes foundations §12 stage 2 and deploys.

### Sequencing riders (stated, not built here)

The §14 S2/tier attribution recording change does NOT ride CP-D — it takes its own
small prereg after this checkpoint (minimal-confound discipline; nothing in CP-D
depends on it). The extractor-ρ pooling exit (a) is sequenced AFTER CP-D for the same
reason. The thread family (Stage 2b) opens on CP-B's component 1 as planned, after
this checkpoint closes.

## RESULTS

*(appends per phase; nothing above this line changes.)*
