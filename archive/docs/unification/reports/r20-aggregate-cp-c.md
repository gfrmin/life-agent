# r20 — aggregate family CP-C: component 3, dedup-as-inference ($0)

*2026-08-26. The third checkpoint of Stage 2a, opened by r19's RESULTS ("CP-C (r20)
opens"). Library-only plus two riders — nothing on the decision path imports what this
checkpoint builds. The pre-registration below is committed BEFORE any `src/` change and
BEFORE the measurement runs; results append under RESULTS. Per the keypress map, a
directional miss in the off-gate measurement is a STOP for an owner ruling, never a
quiet iteration loop.*

## Pre-registration (frozen)

### What CP-C builds

Component 3 of `docs/aggregate-family-design.md` (§7): pairwise same-entity hypothesis
comparison under a structure prior, scoped to aggregate addends —
`same_entity_posterior` + `PairCovariates` + `SameEntityPosterior` in
`core/aggregate.py` — plus the off-gate measurement `scripts/dedup_pair_audit.py` run
on the three labelled pairs in `$LIFE_AGENT_KB/eval/aggregate-questions.yaml`. Riders,
same PR: (a) the three over-broad "§5 dedup-as-inference" labels in `lookup.py`
(the module comment at the shared shaper, `dedup_correlated`'s docstring, and the
`observe_hits` NB) corrected to "§5 dedup (correlation collapse)" — the inference half
arrives here as a DIFFERENT object and `lookup`'s rule is untouched (§6.8 scoping);
(b) the CRM alias-dedup entry (#4) lands in `docs/crm-architecture-decisions.md`
exactly as drafted in r18. NOT built here: any decision-path plumbing, §18.14, the
router, component 2 (all CP-D).

### Frozen wire choreography

One categorical state over the two structure hypotheses —
`create_state({"type": "categorical", "space": {"type": "finite", "values": [1.0,
2.0]}, "log_weights": [0.0, 0.0]})`, where `1.0` ≡ one latent transaction and `2.0` ≡
two. **The structure prior is uniform**: §7 reads "fewer latent entities preferred
exactly insofar as they predict the observations" — the Occam preference lives in the
marginal likelihood, and a tilted prior would be a second, silent Occam. Per READABLE
covariate, one `condition` with a `tabular_log_density` kernel (`source_vals` = the two
hypotheses, `target_vals` = the covariate's bucket atoms, `densities[h][b]` = the
frozen log-likelihood `log P(bucket b | hypothesis h)`); the observation is the bucket
atom. Read `weights` → `(p_one, p_two)`; destroy in `finally`. No host math — the
tables are the consumer's declared observation model crossing the wire as data (the
`structure_decide` convention).

### Frozen covariates and likelihood tables

Buckets are closed vocabularies; tables are frozen here, before the measurement runs,
with their rationale. (Values below are probabilities; the wire carries their logs.)

| covariate | buckets | P(· \| one) | P(· \| two) |
|---|---|---|---|
| `period` | same / adjacent / other | 0.98 / 0.01 / 0.01 | 0.15 / 0.45 / 0.40 |
| `amount` | equal / close / different | 0.90 / 0.05 / 0.05 | 0.20 / 0.10 / 0.70 |
| `entity` | same / different | 0.97 / 0.03 | 0.70 / 0.30 |
| `kind` | same / different | 0.99 / 0.01 | 0.80 / 0.20 |

- **`period`** is the designed discriminator: one transaction bears one period stamp,
  so both attestations agree up to extraction error; two distinct addends from a
  periodic series mostly sit in adjacent/other periods, with same-period collisions
  real but uncommon.
- **`amount`** is deliberately humble under H₂: recurring instruments repeat amounts
  by design (a salary series can post identical gross in adjacent months), so
  `P(equal | two) = 0.20`, not something tiny — this is what keeps `period` decisive
  on the adjacent-month equal-amount case rather than letting amount equality
  steamroll it. `close` means within 1% after normalisation.
- **`entity`/`kind`** are weak-when-same by construction: within one aggregate scope
  most candidate pairs share issuer and kind under BOTH hypotheses, so `same` carries
  a likelihood ratio near 1 while `different` is strong evidence for two.
- **Unreadable ⇒ skipped, named.** A covariate unreadable on either side is NOT
  conditioned and is listed in `SameEntityPosterior.skipped`: an honest
  `P(unreadable | h)` is hypothesis-independent, so the bucket carries zero evidence —
  skipping is the same inference stated louder.
- **Byte-distinctness: recorded, not conditioned (v0).** §7 lists it among the
  covariates the schema carries; it stays carried, but the §5 clustering rule (the
  proposal generator) only emits byte-distinct pairs, so within the proposal
  population the covariate is selection-fixed and folding it would levy a constant
  Bayes-factor penalty on every genuine re-attestation. A deliberate, disclosed
  prereg-time decision.
- **`basis`** enters at CP-D with the §18.14 schema (stock/flow is not readable off
  the document pairs below without the amount projection); v0's `kind` carries the
  type discrimination. Named here so its absence is a decision, not an omission.

### Frozen measurement: pairs, mapping, directions

`scripts/dedup_pair_audit.py` reads the three labelled `duplicate_pairs` from the
installed eval file and runs `same_entity_posterior` **on the live credence engine**
(the same seam the deployed path uses — never the test oracle: a census must read the
deployed rule end-to-end). If the engine cannot spawn on this box, that is a
STOP-disclosure, not a quiet substitution. $0 — no model calls.

Each document pair induces the line-item pair of its principal addend; the covariate
mapping is frozen from the eval file's own recorded evidence:

1. **real-duplicate** (two distinct-bytes attestations of the same month's payslip):
   `period=same`, `entity=same`, `kind=same`, `amount=UNREADABLE` (the garbled side's
   digits are font-mapped — recorded honestly in the instrument) ⇒ amount skipped.
2. **control-non-duplicate** (adjacent months, same series): `period=adjacent`,
   `entity=same`, `kind=same`, `amount=UNREADABLE` (both sides garbled) ⇒ skipped.
3. **control-non-duplicate-readable** (adjacent quarters, same fund, readable):
   `period=adjacent`, `entity=same`, `kind=same`, `amount=different`.

**Pre-registered directions (the frozen consequence):** pair 1 → `p_one > 0.5`; pairs
2 and 3 → `p_one < 0.5`. Any miss = STOP for an owner ruling. Paper expectation under
the frozen tables, published so the live run is checked against magnitude too:
`p_one ≈ 0.92 / 0.04 / 0.003`. A live reading directionally right but far off these
magnitudes is a disclosure item, not a renegotiation.

### Tests (TDD, each watched RED before its code)

t1 choreography: uniform categorical prior, one condition per readable covariate,
weights read, state destroyed in `finally` (oracle-counted, success and raise paths).
· t2 the real-pair shape reads `p_one > 0.5`, exact against the oracle's independent
Bayes arithmetic. · t3 the adjacent-period shape reads `p_one < 0.5`. · t4 an
unreadable covariate is skipped and named. · t5 `p_one + p_two = 1`. · t6 an unknown
bucket is a loud error (closed vocabularies). The local oracle extends the
`ConjugateBrain` convention with categorical states + `tabular_log_density`
conditioning — an independent reimplementation, not the module's own math.

### Gate (frozen)

Full suite + `ruff check` + `mypy` green; `collapse_replay.py --checkpoint m5-base` at
the recorded seed reads **314/314 pure equality**; the three pre-registered directions
met on the live engine; library-only re-verified (no decision-path import). Anomalies
en route are disclosure items here (cap-the-arc).

## RESULTS

*2026-08-26, same day. TDD held: the six CP-C tests (c-t1..c-t6 with the `TabularBrain`
oracle) were watched RED — `ImportError: cannot import name 'UNREADABLE'` — before
component 3 existed; then GREEN with no test edit beyond lint import placement.*

- **The off-gate measurement, on the live engine, all three pre-registered directions
  MET** — and the magnitudes land on the published paper expectations exactly:
  `real-duplicate` p_one **0.9181** (expected ≈0.92, conditioned period/entity/kind,
  amount skipped-and-named); `control-non-duplicate` p_one **0.0367** (≈0.04 — the hard
  adjacent-month same-template control resolves as two on the period covariate alone);
  `control-non-duplicate-readable` p_one **0.0027** (≈0.003). The agreement also
  confirms the `tabular_log_density` semantics reading (`densities[h][b]` as declared
  log-likelihoods) against the deployed engine, not just the oracle.
- **Gate, all conjuncts (re-run fresh after lint fixes):** suite **2742 passed**;
  `ruff check` clean; `mypy` clean (224 files); m5-base replay **314/314 pure
  equality**; library-only re-verified (no module under `src/life_agent/` imports
  `aggregate` — tests and the audit script only).
- **Riders landed:** the three over-broad "§5 dedup-as-inference" labels in `lookup.py`
  (shared-shaper comment, `dedup_correlated` docstring, `observe_hits` NB) now read
  "§5 dedup (correlation collapse)" with the inference half named as the aggregate
  family's component 3; the CRM #4 alias-dedup entry landed in
  `docs/crm-architecture-decisions.md` as drafted in r18 (#3 stays open).
- **Deviations: none.** The only post-prereg adjustments were lint-shape (an unused
  loop variable, comment rewraps, import placement), each followed by a fresh full
  gate run.

**CP-C is DONE. CP-D (r21) opens** — SPEC §18.14 + the amount transform, component 2,
family plumbing, the two-stage router, and the priced §8 run under CP-A's ruled
conjunct structure; its prereg (which may split the checkpoint, M5 precedent) commits
before any further `src/` change.
