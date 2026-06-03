# PHASE2.md — Phase 2 planning

**Status:** plan, pre-implementation.
**Pairs with:** SPEC v0.2.0.
**Predecessor:** PHASE1.md (extraction substrate, complete).

This document is the forward-looking companion to SPEC v0.2.0. The
SPEC is the contract; this is the plan. Where they overlap, the SPEC
wins. Where this document specifies things the SPEC doesn't (timing,
milestones, exit criteria, risk surfaces), it stands on its own.

The structure mirrors PHASE1.md's retrospective shape, written
forward: stages with exit criteria, risks named, definition of done
explicit. The intent is that when Phase 2 is complete, this document
becomes the retrospective with at most light editing.

## 1. What Phase 2 is for

Phase 1 built a content-addressed extraction substrate: 2,107 sources
extracted into a 134MB cache + 3.6MB DuckDB catalogue, three
producers, hash-verified migrations, atomic writes, 1.1% failure rate.
The Phase 1 retrospective named what Phase 2 should inherit
(producer_metadata, the uncatchable-failure-modes paragraph template,
sampling discipline) and what it should not (premature plugin systems,
designed-up-front taxonomies).

Phase 2 ships **one LLM transform end-to-end** — entity extraction —
with the substrate seams that transforms two and three will need
already designed but not implemented. SPEC v0.2.0 is the contract.
This plan is how that contract gets honoured in practice.

The justification for "one transform, substrate seams designed" rather
than "full substrate, several transforms" comes from the Phase 2
research pass. Four of five design questions resolved toward "do less
than you think." Building one transform exposes which seams matter;
building three transforms before any of them is in production
guarantees the seams will be subtly wrong.

## 2. Stages

Five stages. Each has an exit criterion that must be met before the
next begins. Internal steps within a stage emerge from the work, in
the Phase 1 tradition.

### Stage A — Substrate

Implement the SPEC v0.2.0 extensions that aren't transform-specific:
cache-key extension (§17), storage layout for structured artifacts
(§18), lineage recording (§21.1), the policy interface (§22.1), the
HITL approval data model (§22.4), the telemetry log (§23). No actual
LLM calls; no prompt files; no model SDK dependencies. The system
should be able to ingest, route, and store a hand-fabricated
"transform artifact" — JSON written by a stub producer — through the
full pipeline.

**Exit criterion**: A stub TransformProducer that returns a
hard-coded JSON output runs successfully via `pkm transform run`,
produces a cache hit on second run, and `pkm transform show` displays
the artifact with lineage. All Phase 1 invariants still hold; new
invariants 9–13 are enforced.

### Stage B — Entity extraction, real LLM, small scale

The first real transform. Implement EntityExtractionProducer against
Anthropic's Haiku 4.5. Write `entity_extraction_v1.txt` and
`entity_extraction_v1.json`. Wire up `cost_gate` and
`sensitive_doc_gate`. Run on **50 sources** chosen to span the
heterogeneous corpus (legal, medical, CV, research notes, mixed
text-and-tables documents).

The 50-source run is the smoke test. The cost is roughly $0.30–0.70
total. The point is not statistical confidence; the point is to
discover what the smoke test discovers.

**Exit criterion**: 50-source run completes. Schema validation
passes on ≥48/50. The two policies trigger correctly on at least one
source each (deliberately seed a sensitive-tagged document and a
budget-overrun-causing config). Manual review of all 50 outputs
finds the entity extractions broadly sensible (no hard target; this
is qualitative).

### Stage C — Adversarial pass

Before scaling, deliberately stress-test the things that won't
surface in normal documents. Construct or identify ~10 adversarial
sources from the existing corpus:

- A document with no extractable entities (the schema permits an
  empty array; verify the model produces it rather than hallucinating).
- A very long document at the context-window edge.
- A document in a non-English language (the corpus has some).
- A document that's mostly tables or mostly code.
- A document with deliberately ambiguous entities (a person's name
  that's also a place, a date written in mixed formats).
- A document that previously failed Phase 1 extraction.
- A near-duplicate of a document already extracted (same content,
  different cache key path) — to verify the cache hit logic.

This stage's purpose is to surface prompt fragility (§4.1) before
it becomes a 2,000-doc problem.

**Exit criterion**: Each adversarial source produces either a
schema-valid output that the human judges acceptable, or a
documented failure with a clear reason. No silent garbage. If the
prompt needs revising, do so via `entity_extraction_v2.txt`
(invariant 13 forbids in-place edits), update the YAML to point to
v2, and confirm cache keys diverge correctly.

### Stage D — 500-source run

The middle scale. Run on 500 sources sampled stratified across the
corpus tags. Cost: roughly $3–7. The point of this stage is the same
as Phase 1's 500-doc Docling run — most problems that exist surface
here, and the cost of discovering them is bounded.

The HITL approval flow is exercised in earnest at this stage. The
sample-for-approval (§22.5 of the SPEC) shows three real outputs;
the user actually decides whether the prompt is producing what they
want before committing to 500 runs. If the user rubber-stamps the
approval without reading the samples, that's a workflow finding
worth recording.

**Exit criterion**: 500-source run completes. Schema validation
≥98%. Per-source cost variance is within the modelled distribution
(no document costs more than 5× the median). The HITL approval flow
took the user less than 5 minutes from `pkm transform run` to
approval. Telemetry log is well-formed and queryable.

### Stage E — Full corpus

Run entity extraction on the full corpus. Cost: roughly $10–20.
Confirms scale, surfaces the long tail, produces the artifact set
that v0.3.0 will eventually query.

**Exit criterion**: Definition of Done met (§5).

## 3. What gets built first within Stage A

Suggested ordering inside Stage A, in priority order. This is
guidance, not contract — Stage A's exit criterion is what matters.

1. **Cache-key extension** (§17 of SPEC). The composite key with
   `model_identity_hash` and `prompt_hash` defaulting to the empty
   hash for v0.1.x extractors. This is the foundation; everything
   else extends it. Verify all v0.1.x cache keys are preserved.

2. **TransformProducer base class** (§20.1). An abstract class with
   `render_prompt`, `call_model`, `parse_output`, `produce`. A stub
   implementation for testing.

3. **Storage layout for structured artifacts** (§18). Add
   `lineage.json` to the artifact directory. Extend the atomic write
   sequence (§18.4). Update orphan cleanup.

4. **Catalogue migrations** for the new fields. Hash-verified per
   v0.1.x §14.8.

5. **Telemetry log** (§23). Trivial — JSON Lines append. Build it
   early so all subsequent stages produce data.

6. **Policy interface** (§22.1). The `PolicyDecision` ADT, sequential
   evaluation, the import mechanism for `<root_dir>/policies/`. Stub
   policies that always return `Allow()` for testing.

7. **HITL approval data model** (§22.4). The pending-approval table
   in the catalogue. The approve/reject CLI commands. No real
   approval triggers yet (stub policies don't trigger them); just the
   data model.

8. **`pkm transform` command surface** (§24). Each command stubbed
   to the point of returning structured output the test harness can
   assert on.

The Stage A test harness is a stub TransformProducer that returns
a hard-coded entity-extraction-shaped JSON, with policies that
always allow. This lets every part of the substrate be exercised
without any LLM call.

## 4. Risk surfaces

Phase 1's risks were known unknowns: format coverage, OOM, extraction
correctness. Phase 2's risks are categorically different. Naming them
explicitly so they aren't discovered late.

### 4.1 Prompt fragility

The dominant Phase 2 risk. Unlike a Phase 1 OOM that crashes loudly,
a misfiring prompt produces schema-valid output that's
content-wrong. Specific failure modes:

- The model refuses to produce JSON for a document it interprets as
  sensitive (e.g. medical records). Schema validation fails; the
  failure is recorded as a producer failure, but the *cause* — the
  refusal — is in the model's output text and won't be obvious from
  the failure message alone.
- The model produces JSON-valid output that contains hallucinated
  entities (people who aren't in the document, dates from the
  prompt example carrying through into the output).
- The model anchors on the example in the prompt and produces
  outputs structurally similar to the example regardless of input.
- The model produces inconsistent results for near-duplicate
  documents.

**Mitigation**: Stage C is the primary defence. Beyond that, every
stage produces telemetry and the user spot-checks at least 30 random
outputs at each scale boundary. If prompt fragility surfaces, the
fix is `entity_extraction_v2.txt` and possibly v3, with the prompt
revisions being a normal part of Phase 2 — not a deviation.

### 4.2 Cost discovery

The cost estimate (§22.4) is computed from prompt-template length +
expected input length + a fixed allowance for output. The actual
cost depends on tokenisation specifics, output length variance, and
provider-side variability.

The risk: Stage E's full-corpus run costs significantly more than
estimated, the 2× abort rule (§22.4) kicks in mid-run, and the user
ends up with a half-completed corpus and a re-approval loop.

**Mitigation**: Track actual-vs-estimated cost ratio in Stages B
and D. If Stage D's actual exceeds estimate by more than 1.5×, fix
the estimator before Stage E. The fix may simply be increasing the
output-token allowance based on observed distributions.

### 4.3 HITL workflow friction

If the approval flow is too onerous, the user works around it
(disables policies, raises budget thresholds to infinity, scripts
auto-approval). If too permissive, the user rubber-stamps without
reading samples and the flow is theatre.

**Mitigation**: Treat the time-from-`run`-to-`approve` as
telemetry. Stage D's exit criterion specifies <5 minutes; if the
flow is taking 30 minutes, redesign before scaling. If the flow
takes 30 seconds because the user didn't actually look at the
samples, redesign before scaling — possibly by including a
"summarise these 3 outputs in 50 words" forced step before the
approve button enables.

### 4.4 Provider-side instability

Specific concrete risks at April 2026:

- Haiku 4.5 gets deprecated mid-Phase 2. Migration cost is real but
  bounded — bump model identity, new cache keys, regenerate.
- Rate limits change without notice. Stage E has 2,107 documents;
  at the current per-key Haiku rate limit this is well within
  bounds, but a tightening could force batching.
- Provider routes the same model string to a different weight
  (acknowledged in SPEC §20.3). Not detectable client-side.
  Surfaces as silent quality drift between Stage B and Stage E.

**Mitigation**: The model_identity_hash means a model-string change
is detected as a new transform invocation, not a silent
substitution. For weight drift within the same string,
spot-checking at each scale boundary is the only defence.

### 4.5 Schema-valid-but-semantically-wrong outputs

The schema validates structure (entity has text, type, span). It
doesn't validate that the span actually points to the entity text
in the source, or that the type is correct, or that the text isn't
hallucinated.

**Mitigation**: Add a deterministic post-validator that checks at
least the easy invariants — span indices in range, span text in
source equals entity text. This catches hallucination of entity
text and out-of-range spans. The harder semantic checks (type
correctness, completeness) are spot-check territory.

This post-validator is in scope for Stage A. The SPEC §20.2 says
"validate output against schema"; the post-validator is an
additional schema-independent check that should be implemented as
part of the producer's `produce()` method. Treat a span-index
mismatch as a producer failure.

### 4.6 Lineage staleness in practice

Invariant 10 says staleness is detectable, not enforced. The risk
is the user forgets to run `pkm transform rerun --stale` for
months, then queries an outdated artifact and doesn't realise.

**Mitigation**: `pkm transform show <key>` displays a prominent
"⚠ STALE" indicator if any input cache key in `lineage.json` is no
longer current. `pkm transform status` reports stale counts in
its summary line. Beyond that, this is a personal-discipline
problem, not a system-design problem.

### 4.7 Catalogue corruption from concurrent invocations

Phase 1 was single-process, ran in 31 minutes, no concurrency.
Phase 2 transforms could run for hours; the temptation to run two
transforms concurrently (different transforms over the same
sources, or the same transform over different subsets) will arise.
DuckDB's concurrency model is not designed for this.

**Mitigation**: For v0.2.0, enforce a single-writer lock at the
catalogue level. `pkm transform run` acquires the lock, holds it
for the duration of the run, releases on completion or failure.
Trying to run two transforms concurrently fails fast with a clear
error. This is restrictive but correct; relaxing it is a v0.3.0
decision once the workload pattern is clearer.

## 5. Definition of done

v0.2.0 is "done" when all of the following hold:

1. **Schema validation pass rate ≥98%** on the full-corpus run. The
   1.1% Phase 1 failure rate gives the natural anchor; expect 1–2%
   transform failures, mostly on documents that already failed
   extraction.

2. **Manual spot-check on 30 random successful outputs** finds ≤2
   that are clearly wrong (hallucinated entities, wrong types,
   missing major entities). The 30-sample, ≤2-error bar is the same
   discipline as Phase 1's spot-checks scaled to a more error-prone
   process.

3. **Total full-corpus cost within 2× of estimate.** If the
   estimator is off by more than 2×, fix it before declaring done.

4. **All Phase 1 invariants hold post-Phase-2.** Specifically: the
   v0.1.x extraction cache is byte-identical to its pre-Phase-2
   state. No cache key drift, no metadata schema drift, no
   migration disruption.

5. **All v0.2.0 invariants (9–13) are enforced** with at least one
   test per invariant deliberately attempting to violate it.

6. **The HITL approval flow took <5 minutes** at each of the three
   scale boundaries (Stage B, Stage D, Stage E).

7. **The Phase 2 retrospective draft can be written from this
   document with light editing.** If the structure of this plan
   doesn't survive contact with reality, the plan was wrong, not
   reality. Document the divergences honestly.

## 6. What is explicitly NOT done at the end of v0.2.0

Listing these so they don't accidentally creep in:

- A query surface. `pkm query` does not exist.
- A second transform. Embeddings, summarisation, date extraction,
  PII detection — all v0.3.0 or later.
- A transform registry beyond YAML declarations.
- Demand-driven discovery. The LLM-proposes-transform machinery is
  v0.3.0, when there are 3 transforms to generalise from.
- Automatic stale-artifact rerun.
- Per-source granular approval.
- Concurrent transform invocations.
- A vector index.
- Aggregated cost priors for planning.
- Anything Pixeltable, LOTUS, DocETL, or Palimpzest does that the
  SPEC didn't explicitly include.

## 7. What v0.3.0 will inherit from Phase 2

Forward-looking notes for the v0.3.0 plan, written now while the
context is fresh.

The HITL approval flow's actual usage data — the time taken, the
approve/reject ratio, the reasons for rejection — is the input to
designing the discovery loop. If the user approves 90% of proposed
runs without modification, the discovery loop should bias toward
auto-running cheap transforms and only pausing for expensive ones.
If the user rejects 30%, the flow needs richer pre-approval
information, not less.

The telemetry log accumulates from Stage A onward. By the time
v0.3.0 starts, there will be hundreds of entity-extraction
invocations logged. That's the training data a cost estimator or
query planner would consume. Not enough to train anything serious,
but enough to validate that the format is right.

The adversarial sources from Stage C should be retained as a
permanent test corpus. v0.3.0's second and third transforms get run
against them as a sanity check before scaling.

The first prompt revision (when Stage C surfaces a fragility) is the
first concrete evidence about how prompts evolve in this system.
Whether that revision is `entity_extraction_v2` (small fix) or a
full rewrite (`entity_extraction_v1` was wrong-shaped) tells you
something about how stable transform definitions are. v0.3.0's
discovery design hinges on this.

## 8. Operational notes

### 8.1 Backup before Stage E

The full-corpus run produces ~50–100MB of new artifacts. Before
Stage E, snapshot the entire `<root_dir>` (cache + catalogue +
config). Phase 1 didn't need this discipline because extraction is
re-runnable cheaply. Phase 2 transforms cost real money to re-run,
so a snapshot before the largest run is worth the disk.

### 8.2 Provider account hygiene

Use a dedicated API key for Phase 2. Set provider-side spend
limits as a backstop to the in-system policies. The cost_gate
policy is the primary defence; provider-side limits are the
"if everything else has failed" defence.

### 8.3 Logging volume

The telemetry log produces one entry per transform invocation.
Stage E adds ~2,000 entries. Cumulative through Phase 2: ~3,000.
Daily JSONL files keep this manageable. No log rotation needed in
v0.2.0.

### 8.4 Documentation discipline

Each stage produces a brief retrospective note (a few paragraphs)
in `<root_dir>/notes/phase2/<stage>.md`. The Phase 1 retrospective
was written from memory; some details were lost. Phase 2's notes
are written contemporaneously so the eventual retrospective is
accurate.

## 9. Order of work

Concretely, the recommended starting sequence:

1. Read SPEC v0.2.0 end-to-end. Disagreements get resolved as SPEC
   amendments before code starts.
2. Create the v0.2.0 catalogue migration. Run it on a copy of the
   Phase 1 catalogue. Verify all Phase 1 cache keys still resolve.
3. Implement the cache-key extension and verify on Phase 1 cache.
   This is Stage A's first concrete deliverable.
4. Stub TransformProducer. Stage A continues.
5. ... (Stage A internal sequencing per §3 above)
6. Stage A exit criterion met → Stage B starts.

The first real LLM call should not happen until Stage A is
complete. Mixing substrate work with LLM work courts the failure
mode where a substrate bug looks like a prompt bug.

## 10. Closing

Phase 2 is harder than Phase 1 in one specific way: the failure
modes are quieter. Phase 1's OOM crashed loudly. Phase 2's bad
prompt produces schema-valid garbage. The discipline that Phase 1
established — staged scales, sampling, deliberate failure-mode
hunting, immutable migrations, content-addressed everything —
transfers directly. The new discipline Phase 2 adds is **deliberate
adversarial testing** (Stage C) and **HITL workflow telemetry**.

Everything else is the Phase 1 playbook applied to a new substrate.
