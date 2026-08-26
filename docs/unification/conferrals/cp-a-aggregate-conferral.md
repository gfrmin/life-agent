# Conferral — CP-A: the aggregate family's design ruling (r18)

> Prepared 2026-08-26 for the owner's ruling that gates CP-A (the first checkpoint of
> Phase 1.6 item 4). Everything rulable is below with a recommendation and its evidence;
> the design itself is `docs/aggregate-family-design.md`, the report is
> `docs/unification/reports/r18-aggregate-cp-a.md`. CP-A is $0 and docs-only; nothing in
> `src/` changes until CP-B's pre-registration, and the priced run does not fire until
> CP-D under its own frozen conjuncts.

## Q1 — v0 scope: numeric-total aggregates only?

**Recommended: yes.** The family answers V = Σ g(W) ("total income", "how much did I spend
on X in P", "how many Y in P" when computed over documents). Lists, summaries, comparisons
and compound questions keep their current narrative treatment unchanged. Rationale: the sum
shape is where the two silent-wrongness hazards (undercount priced by the recall term,
overcount priced by typing + dedup) are defined; a list is honestly a claim set and the
narrative family already renders it. Cost of the narrow scope: some "which/what are my X"
questions stay mostly-abstaining narrative until their own family work. Widening later is
additive; narrowing later is a retraction.

## Q2 — the priced run's capability conjuncts under small N (the one genuinely open call)

**Census outcome, read before ruling:** the installed set holds **15 questions, of which
11 are gradeable** (7 external-gold + 4 structural-gold); the other 4 are gold-none
honesty rows (known-missing-slot and no-generator scopes — they exercise the readouts,
not correctness). Recommended clarification: **N in the rule below counts gradeable
questions**, so gold-none rows cannot pad the count — as installed, N=11 < 15 and the
Δ_agg comparison would be a disclosed reading, not a frozen conjunct, unless the
gradeable set grows before CP-D's prereg freezes.

The aggregate eval set holds ~10–15 questions. A bootstrap `P(Δ_agg>δ) ≥ level` conjunct
at run-14's numbers may be unreachable at that N regardless of merit — a conjunct that
cannot pass is not a gate, and one tuned after seeing the data is not frozen.

**Recommended structure:** hard binary conjuncts = the two §12 stage-gate exhibits (the
income question answered as a posterior with both coverage readouts containing the
external-provenance gold; the structure prior resolving the real duplicate pair against the
control) **plus zero commits in the family's new wrong-commit class** (asserted interval
excluding the external gold); the Δ_agg-vs-narrative comparison is a **frozen conjunct only
if the set reaches N≥15**, otherwise a disclosed reading published with the report. The
regression conjuncts on the 104-corpus (zero NEW wrong commits, the standing rows only,
P(Δ>0.05) ≥ 0.9 preserved) are unconditional either way.

Alternatives considered: (a) full bootstrap conjunct regardless of N — risks an unpassable
gate and invites post-hoc renegotiation, the exact failure the frozen-branch discipline
exists to prevent; (b) no capability conjunct beyond the exhibits — leaves the family
adoptable while performing *worse* than the narrative incumbent on its own questions.

## Q3 — the schema decisions (decided in the design with evidence; veto point)

The parked D3-era deliberation's four questions are answered in design §3–§4/§7, on two
pieces of evidence that did not exist when it was written (the Ollama deprecation; the KB
25-document grounding probe):

1. **Bounded typed line-items** (≤8/doc), not one-amount-per-document — a payslip's
   gross/net/tax are all real; one-amount re-imports "which?" as a silent model choice.
2. **Grounding gate:** verbatim `amount_raw` mandatory; `label_raw` the quality
   discriminator (probe: labels ground 28/40 on financial vs 2/14 on OCR noise, while bare
   amounts ground on both — so amounts alone cannot tell real from glyph soup, and full
   quotes reject 26/40 true addends);
   majority-unlabelled documents priced through a declared reliability cell, not dropped.
3. **`basis` enum + `as_of` date** per item (stock/flow + period identity — the overcount
   defence needs both).
4. **Dedup lives where each part belongs:** schema carries the keys, the CP-C inference
   dedupes, the answer discloses; the deterministic lookup clustering rule stays untouched
   as proposal generator (§6.8 scoping).

## Q4 — reactions on aggregate decisions: recorded, not folded (v0)

The lookup abstain-verdict fold (`-p/(1-p)` threshold datum) has no honest analogue for an
interval decision without its own likelihood design; inventing one silently is what §16
forbids. **Recommended: record aggregate verdicts, fold nothing, name the fold as the
family's successor entry.** (Same posture narrative v0 took.)

## Prices

CP-A $0 (this) · CP-B $0 · CP-C $0 (off-gate measurement on two labelled pairs) · CP-D one
priced §8 run, budget frozen ≤ $2 (runs 15–18 read $0.37–0.68; the aggregate set adds
synthesis) + the corpus amount-extraction warm cost at CP-D's prereg-computed cap.
Decline branch: nothing is built; aggregate questions keep falling to narrative (today's
behaviour — mostly honest abstains); foundations §12 stage 2 stays unmet and the completion
programme's DONE item 2 stays open on item 4.

## RULING

*Taken 2026-08-26 (owner, four-question interview). All four recommendations adopted:*

1. **Q1 — v0 scope: numeric-total aggregates only.** Sums and counts over a scope;
   lists, summaries, comparisons and compound questions keep their narrative treatment.
2. **Q2 — conjunct structure ruled as recommended, with the census clarification:**
   hard binary conjuncts = the two stage-gate exhibits + zero commits in the family's
   new wrong-commit class (asserted interval excluding the external gold); the
   Δ_agg-vs-narrative comparison is a frozen conjunct **only if the gradeable set
   reaches N≥15** — and **N counts gradeable questions** (gold-none honesty rows cannot
   pad the count). As installed the set holds 11 gradeable, so Δ_agg is a disclosed
   reading unless the gradeable set grows before CP-D's prereg freezes. The 104-corpus
   regression conjuncts are unconditional either way.
3. **Q3 — all four schema decisions adopted as written** (design §3–§4/§7): bounded
   typed line-items ≤8/doc; `amount_raw` grounding mandatory with `label_raw` the
   quality flag; `basis` enum + `as_of` per item; the dedup split (schema carries the
   keys, CP-C infers, the §5 lookup rule stays untouched as proposal generator).
4. **Q4 — aggregate verdicts recorded, not folded, in v0.** The interval-verdict fold
   is the family's named successor entry; nothing is invented silently.

CP-A's gate is met. CP-B (r19) opens under these terms.
