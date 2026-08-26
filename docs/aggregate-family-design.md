# The aggregate family — design (CP-A of Phase 1.6 item 4)

*Status: DESIGN — written 2026-08-26 at CP-A (report `docs/unification/reports/r18-aggregate-cp-a.md`),
the first checkpoint of the aggregate family. Authoritative spec: `docs/bayesian-foundations.md`
§5 (the three components), §12 stage 2 (the gate). This document is the family's register: every
decision the build needs is made HERE, in writing, before any `src/` change; the checkpoints
(CP-B recall, CP-C dedup, CP-D composition + priced run) each pre-register against it. It also
resolves the amount-projection schema deliberation that has been parked since the D3 era (the
working doc lives out of tree in the KB root — it was never enacted; SPEC §18 still ends at
§18.13).*

*Corpus facts in this document are described **structurally** — document classes, counts,
grounding rates — never by value, name, or identifier. The concrete instances (provider names,
file paths, the probe's marker set, the eval golds) live out of tree under `$LIFE_AGENT_KB`.*

---

## 1. Scope — what v0 is, and is not

**v0 answers numeric-total aggregates only: V = Σ g(W) over a latent document-attested set** —
"how much did I spend on X last year", "what is my total annual income", "how many Y in period
P" *when the answer must be computed over several documents*. Everything else the typed router
declines today keeps falling to the narrative family unchanged:

- **Lists** ("which banks do I have accounts with") — narrative. A list is a set-valued answer
  with per-element credences; its honest rendering is the narrative claim set, and forcing it
  through a sum-shaped posterior buys nothing.
- **Summaries / compound questions** — narrative, unchanged.
- **Single readable figures** ("the total listed in document D") — already lookup, by the
  router's own carve-out; nothing moves.

The family's boundary is *the reader must fold values across documents*. That is the question
shape whose failure mode (a silently-wrong sum, in either direction) the three §5 components
exist to price.

**Deliberately not in v0** (each a named successor, none load-bearing for the stage gate):
cross-currency conversion (multi-currency matches render as per-currency subtotals plus a named
"not summed across currencies" line — never one number); a `hedge` action (narrative set the
precedent: restricted action set first); folding aggregate reactions into the utility posterior
(§8); group-by rendering beyond the single grouping the question names.

## 2. The decision surface

`AGGREGATE_ACTION_ORDER = ("report", "abstain")` — the narrative-family restriction, for the
same principled reason (richer actions over an interval posterior are not yet defined). The
family joins `decisions.FAMILIES` as the third member; the partition invariants in
`tests/test_decide.py` extend; `reactions.py` gains a third dispatch arm (v0: aggregate
verdicts are **recorded, never folded** — the abstain-threshold datum for an interval decision
is not the lookup `-p/(1-p)` datum, and inventing its likelihood without a design is exactly
what §16 forbids; the fold is a named successor).

**A report renders four things, always** (the interaction contract gains one aggregate block):

1. the **posterior interval** for the total (central 80% credible interval from the wire
   posterior, plus its point summary — the mean), with per-addend citations;
2. **readout 1 — extraction coverage within the retrieved set**: "summed *k* of *n* retrieved,
   deduplicated documents; *m* indeterminate (named)" — the engine-§5 denominator contract,
   now stated from the model's own counts;
3. **readout 2 — recall bounding the whole**: the recall posterior's mean and whether it is
   generator-estimated or prior-dominated (`estimated=False` renders as "no known generator
   covers this scope — retrieval recall is unmodelled here", verbatim honesty, not a caveat
   the model may drop);
4. the **basis line**: which `kind`/`basis` the addends were restricted to and any refused
   mixtures (cross-currency, stock+flow — §4).

An abstain follows the standing withhold-reason derivation (`decisions.withhold_reason`).

## 3. The observation instrument — the amount projection (SPEC §18.14, new)

The family's observations are **grounded, typed line-items extracted per document** by one new
pkm transform — the corpus's parked schema question, now decided:

**Decision: the bounded typed line-item schema** (the deliberation's Option C), amended by the
probe evidence below:

```json
{"format_version": 1, "currency_default": "…"|null, "items": [
   {"kind":  "income_gross|income_net|tax|deduction|balance|deposit|fee|invoice_total|payment|other",
    "basis": "point_in_time|monthly|quarterly|annual|other",
    "as_of": "YYYY-MM-DD"|null,
    "amount": 123456.78, "currency": "ISO-4217",
    "amount_raw": "<verbatim source substring>",
    "label_raw": "<verbatim source substring>"|null,
    "entity": "<counterparty/account label as written>"|null}],
 "unreadable": false}
```

with `maxItems` bounded (8), empty `items` a determinate success ("no amounts of interest"),
and `unreadable: true` the named indeterminate for extraction-soup documents.

**Why the list, and why now.** A financial document is a small table of labelled amounts, not
a scalar; one-amount-per-document re-imports "which?" as a silent model choice. The two
arguments that kept the scalar option alive in the deliberation are both dead: the extraction
model is no longer an 8 GB local model (the Ollama deprecation moved every instrument to the
Anthropic seam, where schema-constrained lists are routine), and the executor complexity it
feared is exactly what the wire-observation machinery already handles — per-line-grounded
items ARE wire observations with quotes, the same §5 row shape (`quote`/`doc_key`/
`value_norm`) the whole decide path already speaks.

**The grounding gate, calibrated by the probe** (the KB holds a 25-document probe over real
financial documents plus OCR-noise controls; its report is the evidence of record here):

- verbatim **amount grounding is near-free on real documents** (40/40 mentions grounded) and
  **survives on OCR noise** (10/14) — so amount grounding alone does NOT discriminate real
  amounts from OCR-hallucinated glyph soup;
- **full-sentence quote grounding fails most real documents** (14/40) — tables and RTL text
  paraphrase; requiring it would reject two thirds of true addends as indeterminate;
- **label grounding discriminates**: 28/40 on real documents vs 2/14 on controls.

Therefore the gate is: `amount_raw` MUST ground verbatim (whitespace-normalised, the §18.5
gate `action_items` already uses); `label_raw` grounds when present; an item with an
ungroundable amount is never cached as a success; and a document whose items are
majority-unlabelled is flagged in the artifact (the executor treats its items as a weaker
error-model cell — §5 below — rather than dropping them, so OCR-soup amounts are *priced*,
not trusted and not silently discarded). Raw + normalised pairs per item because the
normalisation (RTL digit order, thousands separators, currency glyphs) is itself error-prone:
`agg`/display cite the raw, the model folds the parsed decimal.

**Instrument discipline from birth:** the transform is versioned pkm (`_VERSION`d, cached,
fail-loud, never-cache-on-miss), and its executor edge is **attributed** — it writes
`eval_edge` rows keyed by `extract_amounts@<model>` from its first firing, so its reliability
posterior is never pooled across models. This is the §14 extractor-ρ lesson applied
prospectively: no new instrument may repeat the base extractor's unpooled-prompt-hash defect.

## 4. The overcount defence — typing before summing

The engine's §5 contract prices the **under**count; this corpus's financial layer adds the
mirror hazard, and the schema above is its defence. Three refusals, enforced
deterministically before anything reaches the posterior:

1. **Kind mixtures are refused**: stocks (`balance`) never sum with flows (`deposit`,
   `income_*`); gross never sums with net. The question's target kind is part of the
   aggregation key; off-kind items are excluded *by name* in readout 1's accounting.
2. **Basis mixtures are refused** unless relatable: a monthly series and its own annual
   roll-up attest the SAME latent total twice (the corpus contains exactly this shape,
   verified in one document class: an issuer's statement carries per-month deposit rows
   alongside the same issuer's period roll-up — summing both double-counts). The
   annual roll-up is preferred as a *single* observation of the year-total (it is the
   issuer's own fold — one document, authority-of-source); the monthly series is the
   *slot-generator evidence* (§5) and the fallback addend set when no roll-up exists. Which
   branch fired is stated in the basis line.
3. **Currency mixtures are refused** (per-currency subtotals, §1).

## 5. Component 1 — the selection/recall term (CP-B)

`r = P(relevant document retrieved | relevant)` is unidentifiable from the retrieved set —
the denominator is not in hand — so it is estimated from **periodic generators**: a monthly
generator over a 12-month scope has 12 expected slots, and retrieving 9 is nine Bernoulli
successes and three failures, a direct sample of r. The corpus supports this concretely: a
monthly payslip series with month-stamped filenames and quarterly fund statements are the
first two registry entries' classes.

- **API is scope-generic** (`Generator`, `Scope`, `expected_slots(generator, scope)`,
  `recall_posterior(brain, generators, scope, hits)`) — nothing spending-specific; item 5's
  membership recall is the same term over thread-member slots.
- **Fold choreography** (the narrative coverage-tail precedent, Invariant 1 — no host math):
  one Beta state on the wire (`create_state` beta), one `bernoulli` condition per EXPECTED
  slot (misses are observations, not absences — folding only hits would read nine-of-nine
  and report r≈1.0 on a 75%-recall scope), `mean` + a `centered_power` variance read,
  state destroyed. Conjugate, no grid.
- **The prior is deliberately not Beta(1,1)** — uniform recall is a strong and false belief
  about retrieval, not a neutral one. Weakly optimistic, weak enough that one monthly scope
  overturns it; the constants live beside the narrative `_COVERAGE_PRIOR` convention,
  frozen-blind.
- **No generator covers the scope ⇒ prior-dominated, declared**: `RecallPosterior` carries
  `estimated: bool`, and `False` renders readout 2's unmodelled-recall sentence. Never an
  interval no data touched.
- **A generator's schedule is a claim about the world**: a wrong denominator biases r down,
  which *inflates the total* (missing mass over-imputed). Hence the registry contract (§9):
  an entry without citing evidence is inadmissible at load.

## 6. Component 2 — the missing-mass posterior (CP-D)

The answer is `P(total | observed addends, r)`. v0's model, chosen for honesty per parameter
over cleverness:

- Deduplicated, kind/basis-filtered addends give the observed sum `S_obs` and count `k`.
- The recall posterior gives r; the unobserved count is imputed through the generator's
  expected slots (missed slots are *named* — a missing month is "month M absent", not an
  anonymous mass); each missed slot's addend is imputed from the observed addends' empirical
  spread over the same generator (exchangeability within a generator's slot series — a
  disclosed modelling assumption, right for periodic instruments like salary/statements and
  stated in the basis line when it fires).
- The interval is composed from wire-read posterior quantiles — **composition of reads, not
  learning**: every distributional read happens on the wire (Invariant 1); the host composes
  point reads deterministically. Where no generator covers the scope, there is NO imputation:
  the report is `S_obs` with readout 2's unmodelled-recall declaration (the honest v0 of "the
  credible interval is wider than the summed extractions" — width without a model is not
  honesty, it is decoration).
- OCR-flagged documents' items (§3) enter with their weaker error-model cell priced into the
  addend's inclusion the same way lookup prices extractor reliability — through the declared
  per-cell reliability posterior (`core/reliability.py` PRIORS gains the
  `extract_amounts` edge's cells; a new (edge, cell) row, not a new mechanism).

## 7. Component 3 — dedup-as-inference (CP-C)

"Are these two line-items the same latent transaction?" is hypothesis comparison over latent
entity structure with a **structure prior** — fewer latent entities preferred exactly insofar
as they predict the observations (PRINCIPLES/§9's first formal Occam appearance). v0 is
**pairwise**: P(one latent | pair) vs P(two), on covariates the schema already carries —
normalised amount equality/proximity, kind, basis, `as_of` proximity, entity label, and the
carrier documents' byte-distinctness. The corpus supplies the gate's real pair (the same
document class re-attested with distinct bytes) and the control pair (same series, adjacent
periods — near-identical form, different values; the hard negative).

**§6.8 scoping — explicit.** `lookup.dedup_drop_rows` is THE §5 *clustering rule* over
`(quote, doc_key, value_norm, covariate)` and is untouched by this family; its docstring's
"§5 dedup-as-inference" label over-claims (it is the correlation-collapse half; the inference
half arrives here) and is corrected to "§5 dedup (correlation collapse)" in CP-C's commit.
The clustering rule may serve as the *proposal generator* — pairs it does NOT collapse are
the candidates the inference prices. One rule, two declared roles; no second implementation
of either.

## 8. The two-stage router (CP-D)

`ROUTE_PROMPT` stays **byte-identical** — any edit re-mints every lookup admission verdict in
the derivation cache (the run-8 lesson; the terse-carrier lesson retires vocabulary-overlap
scoring besides). A NEW second classifier — own prompt, own closed schema
(`aggregate | narrative`), own cache key — runs only on the **declined** path, exactly where
`terminals.py`/`executor.py` today route unconditionally to narrative. Misroute posture is
asymmetric by design: a narrative question sent to aggregate is the harmful direction (a
sum-shaped answer to a non-sum question), so the second stage admits to aggregate only on a
confident sum-shaped verdict and defaults to narrative — **zero narrative→aggregate false
positives on the labelled mixed set** is CP-D's C0 bar, and the route-audit instrument grows
a second confusion matrix (its labelled set gains the three-way labels at CP-A). Lookup
admission blast radius is zero by construction and C0 verifies the byte-identity claim
without a model call.

## 9. The generator registry — contract

- **In tree**: the schema, the loader, validation, and a synthetic fixture
  (`# PII-OK: synthetic generator registry`). **Out of tree**: the real registry at
  `$LIFE_AGENT_KB/generators.yaml`.
- Entry shape: `{generator_id, kind (of the amounts it emits), cadence (closed enum:
  monthly|quarterly|annual), active_from, active_to|null, scope_keys (how questions bind to
  it), evidence: [KB citations]}`. The cadence vocabulary is closed — an unknown cadence is
  a registry error, never a silent zero slots.
- **Admissibility**: an entry whose `evidence` citations do not resolve against the KB at
  load fails loud. A schedule is a claim about the world; uncited claims don't enter the
  denominator.
- **Replay determinism**: the loaded registry's content hash is recorded onto every decision
  record it conditioned (a mechanics field — recorded, never priced), so a gate replay pins
  the registry state and a registry edit between record and replay is visible, never silent.

## 10. Grading, the new wrong-commit class, and the priced gate (CP-D)

- **`gate.realised_report`'s token containment cannot grade an interval**, and "gold ∈
  interval" alone rewards infinite width. The aggregate realised rule is a **proper interval
  score**: the Winkler score of the asserted central interval at the frozen level (80%, the
  same level the report renders) against the external gold, affinely mapped onto the
  `u_assert` scale so a sharp correct interval reads near `u_correct`, a miss reads
  `u_wrong`-ward in its miss distance, and width pays linearly. The mapping's constants are
  frozen in CP-D's prereg before the run. Extending `gate.py`'s realised model is itself a
  pre-registered change (the model is frozen machinery).
- **The family's named wrong-commit class: an asserted interval that excludes the external
  gold.** It joins the hard clause's census from birth: no lever ships while it makes this
  class worse.
- **External-provenance golds.** A gold hand-summed from the same corpus whose recall is
  under test inherits the recall failure — circular. Every aggregate gold comes from an
  authority outside the summation path (the issuer's own roll-up figure — the corpus's
  annual employer summary is the canonical instance), read out-of-band and recorded with
  provenance in the out-of-tree question file.
- **The priced run's conjuncts** (frozen blind in CP-D's prereg): C0 route integrity
  (§8) · C1 regression on the 104-corpus (zero NEW wrong commits; wrongs exactly the two
  standing rows; P(Δ>0.05) ≥ 0.9 preserved — run-14's frozen numbers copied, not re-chosen)
  · C2 capability on the aggregate set (the two stage-gate exhibits + zero commits in the
  new wrong class; the Δ_agg-vs-narrative comparison per the CP-A ruling) · C3 the hard
  clause across both sets. Budget ≤ $2. Any FAIL = STOP for an owner ruling.
- **Small-N honesty** (the CP-A conferral's question): at ~10–15 aggregate questions a
  bootstrap `P(Δ_agg>δ)` conjunct may be unreachable regardless of merit. Proposed: the
  exhibits + zero-new-class as hard binary conjuncts; Δ_agg a frozen conjunct only if the
  set reaches N≥15, else a disclosed reading. The owner rules; the ruling freezes.

## 11. The eval instrument (CP-A, out of tree)

`$LIFE_AGENT_KB/eval/aggregate-questions.yaml`: the real income/total questions over scopes
the registry covers (including at least one scope with a *known missing slot*, so readout 2
is exercised on evidence, not vacuously), at least one scope no generator covers (the
prior-dominated rendering exercised), non-financial count aggregates (scope-genericity), the
labelled duplicate pair + control pair, and per-question `gold`, `gold_provenance`,
`gold_level` fields. The route-audit mixed set's 21 negatives gain three-way labels (as a
sibling file; the original stays untouched as the C0 byte-identity instrument). Nothing
in these files ever enters the tree.

**Census outcome (instrument built and installed 2026-08-26; golds re-verified against the
cited artifacts' cache content):** 15 questions — 7 external-gold, 4 structural-gold
(closed-set census, no issuer states the number), 4 gold-none honesty rows — plus one real
duplicate pair and two control pairs. Three findings the family must carry rather than
assume away: (1) **no employment-income scope has both an issuer roll-up and a readable
in-corpus addend series** — years with roll-ups have no payslips and vice versa — so the
one scope where a generator covers the summation path AND the issuer's own roll-up checks
the sum is a fund-deposit scope, and that question is the primary stage-gate exhibit;
(2) **two named extraction holes**: one payslip series' embedded custom font garbles every
extraction (digits included), and a second payslip's extraction reverses digit runs — both
recorded in the instrument's notes; the family surfaces them as coverage readouts (the
slots still count for recall — presence, not readability), never papers over them;
(3) the real duplicate pair's amount-level equality is honestly unverifiable on the garbled
side — identity is fixed by the month-stamped filename plus a deterministic font-map decode
of the header, and the pair's record says so.

## 12. Risks → where each dies

| Risk | Dies at |
|---|---|
| Router misfire re-routes narrative questions (run-8 class) | CP-D C0 — byte-identity + zero-FP bar, structural |
| Gold circularity | CP-A — external-provenance requirement per question |
| Width-gamed interval | CP-A frozen Winkler mapping; enforced at C2 |
| Registry drift breaks replay | CP-B — content hash on the record |
| §6.8 second-implementation reading | §7 scoping + CP-C docstring correction |
| Spending-specific component 1 blocks item 5 | CP-B — non-financial generator test |
| Prior-dominated overclaiming | CP-B `estimated=False` invariant; C2 rendering check |
| Overcount (roll-up + series double-count) | §4 refusals; the duplicate-pair exhibit |
| OCR-soup amounts trusted | §3 label-grounding flag + §6 priced cell |
| Small-N conjunct meaningless | CP-A ruling on the conjunct structure |

## 13. Checkpoint map (the plan of record, restated)

- **CP-A (this doc, r18, $0)**: design + eval instrument + conferral. No src.
- **CP-B (r19, $0)**: component 1 + registry, library-only; suite/lint/type green; 314/314
  pure-equality replay.
- **CP-C (r20, $0)**: component 3, library + pre-registered off-gate duplicate-pair
  measurement (a directional miss = STOP); the CRM alias-dedup entry lands.
- **CP-D (r21, priced)**: SPEC §18.14 + the amount transform; component 2; family plumbing;
  two-stage router; the §8 gate run (C0–C3). PASS closes foundations §12 stage 2 and
  deploys; FAIL stops for a ruling.
