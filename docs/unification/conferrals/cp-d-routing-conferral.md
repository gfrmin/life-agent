# Conferral — CP-D's routing STOP: the frozen C2 exhibit is unreachable as instrumented

> Prepared 2026-08-26, before the interview. Run 19 was fired under r21's frozen
> conjuncts and STOPPED before its C1 leg when the pre-C1 legs surfaced, in order: two
> instrument defects (both fixed under their own red-first tests, PRs #102/#103, each a
> disclosure item), and then — from the voided C2 rows — a routing census that makes
> the frozen C2 exhibit (a) unreachable under the deployed tree. No frozen conjunct has
> been *read*; what follows is why one cannot be, and the options. Everything below is
> $0 evidence already in hand; the aborted run's spend was a few tens of cents (the
> warm derived nothing — its failure was defect 2 — and C1 died ~5 questions in; the
> partial gate rows are inert under an unpublished run id, artifacts renamed
> `VOID-coldlane-*`).

## The evidence

1. **The routing census (deployed rule, end-to-end, live verdicts):** of the 15
   aggregate eval questions, **11 are ADMITTED by the stage-1 lookup router** —
   including the primary exhibit's fund-deposit question and all three admitted
   gold-none honesty rows — 2 route to the aggregate family, 2 decline to narrative.
   The family, wired per the frozen §8 design to the *declined path only*, never
   fires on an admitted question, so exhibit (a) ("the fund-deposit question reports
   a posterior with BOTH readouts and the issuer's roll-up inside the interval")
   cannot read. Firing the priced run would purchase a known C2 FAIL.
2. **Stage 1's verdicts are defensible under its own rule.** The admitted questions
   are phrased as single-value asks ("How much was deposited into … during …?") and
   the census established at CP-A that these scopes carry an **issuer roll-up** — one
   readable value on one document. The mixed labelled set's two aggregate negatives
   are sum-explicit ("total … across all …") and both DECLINE (the C0b sweep read
   **0 narrative→aggregate false positives and 2/2 aggregate recall** — a valid,
   kept reading; verdicts cached).
3. **The joint freeze is what broke.** §8 froze declined-path-only (the
   blast-radius-zero rationale, the run-8 lesson) AND CP-A/r21 froze exhibit (a) on
   the fund-deposit question. Under the deployed router those are jointly
   unsatisfiable. Neither code defect nor grader defect: an instrument-assumption
   miss — the eval set assumed aggregate questions decline stage 1; the two that are
   sum-explicit do, the eleven that read as single values don't.
4. **The epistemics cut both ways.** The lookup lane answering a roll-up-attested
   aggregate is the same §4.2 move the family itself makes (the issuer's own fold is
   THE single observation — authority-of-source), minus the coverage readouts. The
   family's *irreplaceable* class is the summation-required scope (no roll-up; a
   known-missing slot; a computed count) — and those are exactly the shapes that DO
   route to it (the sum-explicit supplier-total question with its external
   roll-up-checkable gold; the employer-count question).

## The options

**E — re-read the exhibit through the deployed behaviour (recommended).** No `src/`
change. The owner amends the frozen exhibit anchor: exhibit (a) reads on the
**sum-explicit supplier-total question** (family-reachable; external-provenance gold;
the roll-up lands as the scope-end single observation, so the posterior + both
readouts render), exhibit (b) as already pre-disclosed; the fund-deposit question and
the other admitted rows read through the lookup lane as **disclosed correctness
rows** (graded by containment — does the deployed system get them right, whatever the
lane). Zero-new-class stays hard everywhere; the 104 regression conjuncts untouched.
Rationale: the deployed routing is arguably *correct* on roll-up-attested phrasings;
the family keeps exactly the class it is irreplaceable for; no new misroute hazard is
purchased. Price: one ruling + re-fire (~the frozen budget). Cost: the priced
capability reading through the family narrows to the family-reachable rows (Δ_agg was
already a disclosed reading by the CP-A ruling); the coverage readouts do not appear
on admitted sum-shaped questions in v0 (registerable as a successor: a lookup-lane
coverage footnote).

**A′ — let an aggregate verdict pre-empt stage-1 admission.** `src/` change under an
amended prereg: on ADMITTED questions, also consult the second-stage router; an
aggregate verdict wins. ROUTE_PROMPT stays byte-identical and stage-1 verdicts stay
cached (C0a intact), but the misroute hazard **flips into the harmful direction §8
deliberately avoided**: a route2 false positive can now steal a genuine lookup
question. Measurable before firing (extend the sweep to the 19 stage-1 positives,
zero-FP bar), and C1 still guards the 104 empirically. Price: prereg amendment + a
small src change + sweep extension (~$0.02) + ~100 route2 verdicts on the 104
(~$0.05) + re-fire. Buys: the readouts render on every sum-shaped question, the
exhibit reads as originally anchored.

**B — park CP-D's run.** Nothing changes; the block stands; foundations §12 stage 2
stays unmet with the family built but ungated. Named here for completeness; it
contradicts the completion programme's item 2 without buying evidence.

## Prices

Already spent on the aborted run: ≲$1 (sweep verdicts, C2 narrative arm synthesis,
~5 C1 questions). Re-fire under any option: the frozen budget (run ≤ $2 + warm cap
$3.00 — the warm now actually derives, post-#103). Option A′ adds ~$0.07 of verdicts
and a second sweep bar before the run.

## RULING

*(fills at the interview; nothing above changes.)*
