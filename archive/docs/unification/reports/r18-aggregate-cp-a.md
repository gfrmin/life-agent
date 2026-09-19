# r18 — aggregate family CP-A: design + eval instrument ($0)

*2026-08-26. The first checkpoint of Phase 1.6 item 4 (the completion programme's Stage 2a),
opened per the plan of record after the collapse ladder closed (r17). CP-A is docs +
out-of-tree data only — no `src/` change, no model spend on the decision path. Its gate is
an owner conferral (`docs/unification/conferrals/cp-a-aggregate-conferral.md`); the RULING
section below fills at the interview and nothing above it changes after.*

## What CP-A delivers

1. **`docs/aggregate-family-design.md`** — the family's register: v0 scope (numeric-total
   aggregates only), the decision surface (`report`/`abstain`, the four-part report), the
   observation instrument (SPEC §18.14, the bounded typed line-item amount projection with
   probe-calibrated grounding), the overcount refusals, components 1–3 (recall term,
   missing-mass posterior, dedup-as-inference with the §6.8 scoping), the two-stage router,
   the registry contract, the grading rule + the family's named wrong-commit class, the
   priced-run conjunct structure, risks → retiring checkpoints.
2. **Rider:** `docs/derivation-engine-design.md`'s status block corrected — it still read
   "D2–D4 execute continuously", predating the 2026-06-12 re-scope; it now names the
   families and points at the register while keeping its mechanism text authoritative.
3. **Out of tree** (nothing enters the tree), both installed 2026-08-26:
   `$LIFE_AGENT_KB/eval/aggregate-questions.yaml` — 15 questions (7 external-gold, 4
   structural-gold, 4 gold-none honesty rows) with the known-missing-slot scope, the
   no-generator scope, non-financial count aggregates, and one real duplicate pair + two
   control pairs, every gradeable gold re-verified against the cited artifact's cache
   content; and `$LIFE_AGENT_KB/eval/route-audit-family.yaml` — the route-audit mixed
   set's 21 negatives re-labelled three-way (2 `aggregate` / 19 `narrative`; positives
   byte-untouched; the original file unmodified, preserving CP-D's C0 byte-identity
   instrument).

## The evidence CP-A stands on (all $0, all read this checkpoint)

- **The parked schema deliberation is resolved.** The D3-era amount-schema working doc (KB
  root, never enacted — SPEC §18 still ends at §18.13) asked four questions; the design
  answers all four, and the two arguments that had kept the one-amount scalar alive are both
  dead: the 8 GB local-model constraint (retired with Ollama, 2026-08-17) and executor
  complexity (per-line-grounded items are ordinary wire observations — the §5 row shape the
  decide path already speaks).
- **The KB amount-extraction probe** (25 documents: financial + OCR-noise controls) fixes
  the grounding gate empirically: verbatim amount grounding 40/40 on financial documents
  but 10/14 on OCR controls (grounding alone does NOT discriminate hallucinated glyph
  soup); full-quote grounding only 14/40 on financial (would reject two thirds of true
  addends); label grounding discriminates (28/40 vs 2/14). Hence: amount grounding
  mandatory, label grounding the quality flag, OCR-flagged items priced through a declared
  reliability cell — not trusted, not dropped.
- **The corpus supports every stage-gate exhibit, with the anchoring corrected by the
  census** (verified in the catalogue and in cache content): issuer annual income
  summaries exist and their totals are readable (the external-provenance gold class); a
  month-stamped payslip series and quarterly fund statements give two generator classes
  with countable expected slots — including a slot known-missing from an independent
  attestation of the scope's extent; distinct-bytes re-attestations give the real
  duplicate pair, with adjacent months of the same series as the hard control. But **no
  employment-income year holds both a roll-up and a readable payslip series** (roll-up
  years have no payslips; payslip years have locked or extraction-garbled roll-ups), so
  the primary exhibit — a generator-covered summation path checked by the issuer's own
  roll-up — anchors on a fund-deposit scope, where both coexist. Two extraction holes
  (a custom-font payslip series garbling digits; a digit-run-reversing extraction of a
  second payslip) are recorded in the instrument as named coverage facts, and the
  duplicate pair's record states plainly that amount-level equality is unverifiable on
  the garbled side (identity rides the month-stamped filename + a deterministic
  font-map decode).
- **The route-audit instrument** (40-item labelled mixed set, 21 negatives) exists and
  needs only the three-way relabel to become CP-D's C0 instrument.

## Named risks this design retires by construction

The run-8 router-drift class (the second-stage router leaves `ROUTE_PROMPT` byte-identical);
gold circularity (external-provenance requirement); width-gamed intervals (frozen Winkler
mapping); registry replay drift (content hash on the record); the §6.8 second-implementation
reading (dedup-as-inference scoped as a different object; the over-broad docstring label
corrected at CP-C). Full table: design §12.

## Checkpoint map forward

CP-B (r19, $0): component 1 + registry, library-only; 314/314 pure-equality replay.
CP-C (r20, $0): component 3 + the pre-registered off-gate duplicate-pair measurement
(directional miss = STOP); the CRM alias-dedup entry lands (draft below).
CP-D (r21, priced ≤ $2): SPEC §18.14 + the amount transform, component 2, family plumbing,
two-stage router, the §8 run (C0–C3). CP-D's prereg may split it (SPEC+transform first,
plumbing+run second) the way M5's split was signed — that is a prereg-time decision, not a
renegotiation.

## Draft CRM entry (lands at CP-C, quoted here so the conferral sees it)

> **#4 (alias dedup) — resolved by the aggregate family's dedup-as-inference
> (`docs/aggregate-family-design.md` §7):** "are these two records the same latent
> entity/transaction?" is hypothesis comparison under a structure prior, not a string rule;
> the deterministic §5 clustering rule stays the proposal generator. Landed with CP-C
> (r20).

## RULING

*2026-08-26, owner interviewed — all four recommendations adopted (the conferral doc's
RULING section has the full text):* v0 scope is numeric-total only; the priced run's
capability conjuncts are exhibits-hard with Δ_agg frozen only at gradeable N≥15 (N counts
gradeable questions; as installed N=11 ⇒ disclosed reading); the four schema decisions
stand as written; aggregate verdicts are recorded, not folded, with the fold the named
successor entry. **CP-A is CLOSED. CP-B (r19) opens.**
