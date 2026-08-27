# Derivation engine — demand-driven materialisation over pkm

> **Status: adopted 2026-06-11 (owner-approved); D3–D4 re-scoped 2026-06-12.** D0–D2 are
> landed. The old D3/D4 are no longer deterministic pipelines: they are **Ask's aggregate
> and thread question families** (PRINCIPLES §14; `docs/bayesian-foundations.md` §5/§6,
> §12 stages 2–3). **The aggregate family was deleted at K1 (2026-08-27,
> `unification/reports/r22-k1-family-deletion.md`) and its build register with it:** a
> classifier choosing a pipeline is decision-shaping outside the argmax (PRINCIPLES §16).
> The transformations and inference it produced are kept. Read "family" below as naming a
> *belief shape*, never a dispatch target — the remaining lookup/narrative split dies with
> `/route` at proplang migration stage M5 (`membrane-shadow.md` §11 i-6). This doc's §5/§10/§11
> D3–D4 text remains authoritative for the *mechanisms* the families reuse (the coverage
> contract, the `assemble` amendment, the reclassification budget), read through that
> re-scope. The whole-system view this leg belongs to is
> [`system-design.md`](./system-design.md). The genesis research report
> ([`nix-for-documents-report.md`](./nix-for-documents-report.md), April 2026) is an input
> to this design, not a mandate. Every in-tree claim verified against the working tree on
> 2026-06-10.

## 0. North star, and what this document is

The owner's pinned asymptote:

> *Believing, computing, and acting are the same move, scheduled by value of information,
> over an immutable log whose only invariant is that truth is the fold.*

The architecture it implies is a five-layer cycle: **L0** event log (append-only; truth =
fold(events)) → **L1** derivation DAG (pure, content-addressed, cached) → **L2** credence
layer (assertions as distributions + provenance) → **L3** VOI governor (ranks derive · ask ·
act in one queue) → **L4** act seam (execute, observe outcome), with outcomes feeding back to
the log. The unification: a suspending build scheduler that discovers dependencies dynamically
*is* a bounded-rational metareasoning controller (Russell–Wefald: computation is an action
priced by its expected value) once "dependency" means *decision-relevant* rather than
*syntactically upstream*. The credence layer is then a functor over the derivation DAG —
change the codomain of every derivation from `Value` to `(Distribution[Value], Provenance)` —
and the governor is the existing scheduler with a decision-theoretic target swapped in.

The asymptote carries its own discipline: the geodesic runs **derivation →
query-with-confidence → bounded action, in that order**, and the VOI governor is explicitly
premature until a corpus of real questions and demand logs exists to calibrate it. **This
document designs the derivation leg only.** Every decision below is judged against two tests:

1. **Evidence**: does it solve a named FAILURES.md entry now?
2. **Asymptote**: does it avoid foreclosing the layers above?

The machinery is accordingly derived as *consequences*, not features:

- **Demand-driven materialisation** — demand becomes endogenous later (a live decision pulls
  a derivation); today demand is exogenous (an owner question), but the mechanism is the same.
- **Early cutoff** — bounded rationality applied at the content level. Today: stop recomputing
  when regenerated content is identical. The credence-layer generalisation: stop when no live
  posterior moves past a decision-relevant threshold.
- **Read-only staleness** — invalidation awaiting its VOI dual. §18.10 says "this might have
  changed"; the governor will say "and it matters enough to recompute". Until then the cascade
  is pruned by demand itself (§7 below).

The north-star statement is lifted into PRINCIPLES.md §16 (resolved 2026-06-11; was §13's
first open question).

## 1. The four failures and what each minimally demands

The open dominant patterns in `$LIFE_AGENT_KB/FAILURES.md` are all failures of the *fixed*
ask pipeline (expand → retrieve → synthesize), and each decomposes into a small set of
operators — most of them deterministic:

| # | Failure | Minimal decomposition |
|---|---------|----------------------|
| F1 | retrieval-then-aggregate ("sum all invoices" finds hits, can't sum) | retrieve (exists) + per-doc field extraction (LLM, cached) + **deterministic** aggregation |
| F2 | subject/domain collisions ("my Israeli ID" → form templates) | per-doc subject classification (LLM, cached) + **deterministic** filter against the owner profile |
| F3 | temporal blindness ("upcoming appointments" → 2020 hits) | per-doc date projection (deterministic for email; small LLM transform otherwise) + **deterministic** date predicate/rank — never an LLM op |
| F4 | email thread state ("awaiting reply?") | multi-input thread assembly (deterministic) + per-thread classification (LLM, cached) |

The pattern: the LLM appears only in per-document (or per-thread) *projections* that are
cached forever; everything question-shaped downstream of them is deterministic. That is what
makes the answers auditable and the cache slots reusable across questions. *(Scope note,
2026-08-06: this is the typed families' pattern, not a global answer-path invariant —
bayesian-foundations §7 supersedes it there; the deliberative instrument
(`core/deliberate.py`) is a whole-question LLM edge, on-ledger and per-edge-calibrated,
scheduled by the same EU pricing as every other transform.)*

## 2. Prior art in-tree (what this design generalises)

Four verified findings shape everything below.

1. **The pay-on-hit defect.** The eager transform runner calls `producer.produce()`
   unconditionally (`src/pkm/transform_run.py:304`) and computes the schema-3 cache key only
   afterwards (`:321-334`) — yet every key input (input hash, `decl.prompt_text`, model
   identity, engine version, output schema) is available *before* the call. `write_artifact`
   merely dedupes the write (`:352`, counted as `cache_hits`). The model is paid on warm
   entries. Cache-first resolution (key → lookup → call only on miss) is therefore both the
   demand engine's primitive and a defect fix for the eager sweep.
2. **The demand DAG already exists in embryo.** `scripts/ask.py` is a hand-coded three-node
   demand pipeline with constructive traces and early cutoff: expand is corpus-independent
   (keyed on question + model + template, `src/life_agent/core/derivations.py:101-118`);
   retrieve is keyed on (query, corpus digest, k) (`:121-135`); synthesize is keyed on the
   retrieval set's **content hash** (`scripts/ask.py:305-308`, `derivations.py:138-157`) — the
   early-cutoff hinge: equal evidence ⇒ cache hit, whatever the corpus digest did. All three
   stages record through the SPEC §18.9 file-first seam. This design generalises that shape;
   it does not invent a scheduler.
3. **§18.10 currency gives lazy rederivation for free.** *Current* is the most recently
   produced success per `(input_hash, producer_name)` group (`src/pkm/staleness.py:47-73`).
   If a demand walk binds every chain input to the current artifact, a demand on a chain with
   a superseded upstream computes a new downstream key, misses, and rederives exactly the
   stale suffix — no invalidation machinery required.
4. **The single-input mandate bounds F4.** SPEC §18.7: "A transform reads exactly **one**
   upstream artifact's content (single-input)." A thread is N emails, so F4 needs a
   deterministic multi-input *assemble* shape — the one SPEC shape change in this design. The
   email producer's rendered header set is From/To/Cc/Date/Subject/Message-ID only
   (`src/pkm/producers/email_producer.py:61-68`) — no In-Reply-To/References — so threading
   also requires an email `_VERSION` bump and a corpus-wide re-extraction. F4 phases last.

## 3. Decision 1 — split: mechanism in pkm, policy in life_agent

**pkm gains exactly one verb.** `pkm derive` (new SPEC §18.11): given a transform name and
one input (source or artifact), return the *current* artifact for the declared chain,
materialising misses recursively, computing each node's key **before** any model call.
Everything question-shaped — the planner, operator composition, retrieval, synthesis,
abstention, and the owner profile — lives in `life_agent` above the §18.9 external-derivation
seam (SPEC §18.9; `src/life_agent/core/derivations.py`). The existing fixed ask pipeline
becomes the degenerate plan.

Why not the alternatives:

- **Entirely in pkm** fails structurally: synthesis needs the owner profile
  (`scripts/ask.py:317`), and identity/PII does not belong in the derive layer (PRINCIPLES
  §12). A question-answering planner also fails the PRINCIPLES boundary diagnostic — "what
  should be done to answer this?" is an agent-layer question. SPEC change cost is maximal.
- **Entirely in life_agent** leaves per-document derivable facts (invoice amounts, dates,
  subjects, thread state) materialised outside the transform substrate, duplicating
  declarations, grounding (§18.5), policies and the approval gate that already exist in pkm
  and are exactly what those facts need — and it violates the §7 boundary test ("derivable
  from sources ⇒ pkm transform"). It also leaves the pay-on-hit defect in place.

**Recorded counterargument (two walkers).** pkm's derive walk and life_agent's plan executor
are both "walk a DAG, check the cache, materialise misses" — a real duplication smell.
Answer: they traverse different graphs under different invariants. pkm walks *statically
declared* chains (`input.producer` pointers, SPEC §18.7, resolvable before any question
exists) under producer/policy/grounding contracts; the executor walks a *per-question* plan
whose nodes include things pkm must never own (owner profile, abstention, spend decisions).
Collapsing them either drags policy into the frozen layer or re-implements the transform
substrate outside its SPEC. The seam between them is one call: "give me the current artifact
for (input, chain)". What must be shared is not the walker but the **currency primitive**
(§4, binding invariant).

## 4. Decision 2 — target addressing and keys

Two address spaces, deliberately not merged.

**pkm targets:** `(input source-or-artifact, declared chain head)`. No new key schema: the
chain is statically resolvable from declarations, each node's schema-3 key is computable
pre-call (finding 1), and the target's identity is the final node's existing cache key.

**life_agent targets:** a question. `question → plan → node keys`. The plan is itself a
cached §18.9 derivation: schema-3 key, producer `life_agent.ask.plan`, `input_hash` over
`{question}`, with an **operator-registry digest** (hash of the available transforms'
declaration hashes + operator names/versions) in `producer_config`. The plan is therefore
**corpus-independent** — like the expand stage (`derivations.py:101-104`), corpus growth
never replans; emptiness is an executor-time outcome (retrieve returns nothing → abstain) —
but **capability-dependent**: a new operator or transform correctly invalidates old plans.
Plan node execution keys follow the proven ask.py pattern: deterministic nodes take schema-1
keys over canonical inputs; LLM nodes take schema-3 keys over upstream **content hashes** —
generalising the early-cutoff hinge from one edge (the retrieval set) to every edge of the
plan. New stage content types (e.g. `application/x-ask-plan+json`) join the existing three
(`derivations.py:59-61`) and stay out of `CHUNKABLE_CONTENT_TYPES` (the §18.9 retrieval gate).

**Binding invariant — current-binding is one primitive, called not reimplemented.** Every
plan-node input is re-resolved to *current* content at execution time via `pkm derive`; no
plan node ever caches a frozen upstream artifact hash. Without this, staleness-for-free
(finding 3) — a property of the pkm walk — does not reach the plan layer, and silent
staleness reappears one storey up where §18.10 cannot see it.

**The corpus_digest asymmetry, stated rather than inferred.** Plan *structure* is
corpus-independent; *retrieval* nodes are corpus-dependent (keyed on `corpus_digest`,
`src/life_agent/core/corpus.py:25`, as today at `scripts/ask.py:279-280`). This asymmetry is
correct — replayed plans must re-retrieve over the live corpus — but it is the seam most
likely to replay a stale BM25 set without complaint, so it is named here as a contract:
a plan replay never reuses a retrieval result whose corpus_digest no longer matches.

**Recorded counterargument.** A corpus-independent plan made when the corpus had no invoices
replays forever, even after invoices arrive. Answer: the plan names *selectors* (transform
names, query templates, predicates), not artifacts; emptiness is an executor-time outcome,
and re-planning on corpus change would destroy plan reuse entirely. The registry digest
covers what actually changes the space of possible plans.

## 5. Decision 3 — the v1 operator set, and the algebra's binding contract

**v1 operators:**

| Operator | Kind | Notes |
|---|---|---|
| `retrieve` | deterministic | exists (`src/pkm/retrieval.py`); keyed on (query, corpus_digest, k) |
| `sem_map` | LLM, cached | = declared pkm transforms, demanded via `pkm derive`; not new machinery |
| `filter` | deterministic | predicate over fields projected from transform outputs |
| `agg` | deterministic | DuckDB sum/count/group-by over structured extractions; every addend carries its artifact citation |
| `assemble` | deterministic, multi-input | input_hash = hash of sorted member content hashes; lineage edge per member; the one SPEC shape change; F4 only |

The decisive precedent is §18.8: `email_triage` *is* `sem_filter` decomposed — an LLM
classifies each document into a grammar-constrained closed enum **once, cached forever**,
and *which categories matter* is a deterministic consumer-side policy, re-tunable for free
without touching the model. Every v1 filter follows that decomposition. No new LLM-operator
machinery exists in v1: the LLM side of the algebra is exactly the transform substrate.

**Explicit non-goals (load-bearing, not aspirational):** LOTUS-completeness; `sem_agg`
scratchpad folds (a judgment fold destroys per-addend provenance, and extraction errors must
surface as FAILURES entries against the extraction transform — not be absorbed); free-form
LLM filters; full entity `resolve` (embedding blocking + Union-Find) — deferred with
embeddings (§6).

**Binding contract of the algebra — indeterminacy is first-class.** Every operator that
filters or folds over an extracted field partitions its input three ways:

    satisfied · unsatisfied · indeterminate-because-extraction-absent

and the indeterminate set propagates to the answer, with citations. Rationale:
"deterministic" describes the operator, not the trustworthiness of its input. A deterministic
operator over lossy extractions launders upstream dropout — the corpus's dominant failure
mode is context overflow on large documents, not hallucination — into clean-looking results:
impeccably cited and silently wrong. This bites every consumer identically: `agg` silently
undercounts (F1), the subject filter silently excludes documents whose classification failed
(F2), the date predicate silently drops documents whose date failed to extract (F3). So the
contract is a property of the algebra, not an `agg` nicety, and every aggregate answer
carries its denominator:

> *Summed 18 of 23 matching invoices; 5 could not be extracted (citations for both sets).*

The indeterminate set is forward-compatibility constraint (iv) (§9) in operational dress —
the weakest link in the provenance chain, surfaced at query time instead of inferred from
lineage.

**Composition rule — indeterminacy is monotone along the plan, and the denominator anchors
at retrieval.** The partition is defined per-operator; the readout is defined per-plan; this
rule joins them. No operator ever drops an indeterminate item: items an operator cannot
resolve are carried forward in the indeterminate set, **attributed to the operator that could
not resolve them**, and excluded from that operator's *satisfied* flow (a document of unknown
subject is not summed — it is reported). The answer's denominator is therefore the
**retrieved-and-deduplicated set** — the only set the plan ever saw — never any intermediate
stage's survivor set; otherwise a filter launders its own indeterminacy one operator upstream
of where the denominator is struck, which is this contract's bug recursed. With §8's
predicate list there are several indeterminacy sources, so the readout unions them by source:

> *Summed 18 of 23 retrieved invoices that matched supplier X; a further 4 could not be
> classified by supplier and 5 could not be summed (citations for every set).*

The contract **surfaces** indeterminacy; it does not **act** on it. Whether an answer with a
dominant indeterminate set should be abstained from is a posterior-on-the-answer decision —
query-with-confidence's remit (§12.1) — and the threshold question is recorded in §13. Until
then the eval gates must at least distinguish honest from useful (§11, D3).

**Second layer of the same honesty: the denominator's floor is retrieval recall, which BM25
cannot certify.** "18 of 23" describes coverage *within the retrieved set* (the §5
composition rule's anchor); retrieval recall is a separate, unbounded undercount the
aggregate cannot self-measure. Every
aggregate/filter answer therefore carries both readouts: extraction coverage within the
retrieved set, plus an explicit statement that retrieval recall bounds the whole and is not
certified. (This is also the strongest form of §6's argument: recall is the quantity that
cannot be certified on either side of the embeddings choice.) Both readouts are asserted in
the D1/D2/D3 eval gates (§11). F4 has the same floor in different dress: its denominator is
thread *membership*, not retrieved documents — `assemble` computes thread state over the N
members *present*, and a member that never synced, or a reply living only in the other
party's mailbox, truncates the thread silently while leaving the answer impeccably derived
from the members it has. Membership recall is retrieval recall's structural twin — an
unbounded, uncertifiable undercount — and the `assemble` amendment carries the same caveat
(§10, §11 D4).

## 6. Decision 4 — embeddings/hybrid search: deferred to its own design

No open failure requires vectors. F2 is "right words, wrong document subject" — the template
and the ID card are semantically *near*, so embeddings plausibly make it worse; F1/F3/F4 are
metadata and aggregation problems; vocabulary mismatch is already mitigated by cached query
expansion. The only operator with a hard embeddings dependency is `resolve` blocking — itself
deferred. The schema slot already exists (migration 0004's nullable `embedding FLOAT[768]`),
so deferral costs nothing.

Two constraints are recorded *now* so the later design doesn't fight this one:

1. **Embeddings are chunk-level catalogue enrichment, not a Producer.** Chunks are rebuildable
   catalogue rows written delete-then-insert (`src/pkm/chunking.py:102-127`), not CAS
   artifacts; the embedding fill follows that precedent, keyed on (chunker version, model
   tag), rebuildable — never one-artifact-per-source content addressing.
2. **`corpus_digest` must learn the embedding identity when hybrid lands**
   (`src/life_agent/core/corpus.py:25`), or cached retrieval sets silently replay BM25-only
   results over a changed retrieval universe.

v1 subject filtering needs no resolution: matching against the owner profile (already
authoritative, `life_agent.owner`) is a closed two-class problem (owner / not-owner) that
grammar-constrained classification handles — the §18.8 pattern again.

## 7. Decision 5 — invalidation: staleness stays read-only; rederivation is lazy

`pkm stale` remains the report; `pkm derive` becomes the repair; nothing recomputes without
demand. This falls out of the mechanism: the derive walk binds every chain input to the
§18.10 *current* artifact, so a demand on a stale chain misses exactly on the stale suffix
and rederives it; early cutoff (content-hash-keyed edges) stops the recompute the moment
regenerated content is identical. Cascading auto-recompute is rejected: it is unbounded LLM
spend with no question to justify it, the cost/approval machinery (§18.5, policies) is
gate-shaped rather than daemon-shaped, and the genesis report itself recommends designing
"your invalidation UI around this, not around automatic re-derivation".

**Silent-staleness mitigation, in the query executor** (the act seam does not exist yet —
calling this the act layer would muddy the geodesic): before presenting a cached answer, the
executor checks the answer's lineage against the stale set (a read-only §18.10 query) and
annotates: *derived from superseded inputs; re-ask to refresh*. Zero-cost replay is
preserved; a stale fact is never asserted unflagged.

Lifting the §18.9 answers-into-retrieval gate (SPEC §18.9's forward reference) remains a
separate future SPEC decision, not part of this design.

## 8. Decision 6 — planner v0: a template router with fenced predicate slots

One cheap schema-constrained LLM call selects a plan **template** — `lookup | aggregate |
temporal-lookup`, later `thread` — and fills its slots. The plan is cached per §4. Templates
carry an **optional predicate list** over the deterministic operators (temporal, subject,
tag/metadata), because the first realistic dogfood question is compound: "sum supplier X's
invoices from Q2" is aggregate + temporal predicate + subject filter in one plan, and
without predicate slots it lands on the deferred escape hatch on day one. Bounded composition
via a *slot* is cheap, testable, and cacheable; it is not the spine.

**The slot's own non-goals fence:** a flat **AND-only conjunction** of deterministic
predicates over projected fields. No disjunction, no nesting, no predicate mini-language.
"Supplier X *or* Y, not yet paid" is the free-form planner wearing a slot; it routes to Open
Questions (§13), it does not quietly grow the list.

Free-form emitted DAGs (template *rewrite*) remain deferred until a failure fits no
template+conjunction — the PRINCIPLES §15 spine-avoidance argument in miniature: a
constrained router is testable and cacheable; an open-ended planner is a spine fragment. The
owner's genesis-conversation ambition (organic taxonomy emergence; Bayesian/VOI spend
decisions) is the named escape hatch, recorded in §13.

## 9. Forward-compatibility constraints (the asymptote test)

Binding design constraints — what the derivation leg must not foreclose:

1. **Derive targets are first-class values.** A target — (input, chain) or a plan node — is a
   serialisable object a future governor can hold in a ranked queue. `pkm derive` is the
   mechanism a scheduler calls; it is never itself a policy.
2. **Operators stay pure value-level with per-node provenance.** This is exactly what makes
   the credence functor a type change rather than a rewrite: an operator correct over values
   lifts to distributions-with-provenance for free. No operator may collapse provenance (the
   `sem_agg`-fold rejection in §5 is also this constraint).
3. **Demand logging from D0.** Every derive/plan/execute records (caller or question, target
   keys, hit/miss, cost_usd, latency) by extending the transform telemetry precedent
   (`_log_telemetry`, `src/pkm/transform_run.py`) to the demand path. This is the governor's
   calibration corpus and it cannot be backfilled. Stated plainly: **reuse frequency is the
   only calibratable VOI input D0 yields, and it is two signals, not one.** The
   current-binding decoupling (§4) makes them genuinely distinct — a replayed plan-key can
   carry entirely fresh node-keys. *Plan-key reuse* measures question-pattern frequency ("we
   ask this shape often"); *node-key reuse* measures derivation value ("which third-order
   views nobody reads"). They answer different governor questions, so the log records both,
   labelled — each a trivial group-by once keys are logged. Stakes and utilities cannot be
   logged yet; the human-annoyance placeholder (§13) is the honest admission of that. D0's
   log must not later be mistaken for the whole calibration corpus.
4. **The weakest-link readout stays possible.** Answer lineage must remain traversable to
   leaf reliability — the §18.10 stale-set check (§7) is the degenerate form of "posterior
   variance is dominated by the least-reliable input", and the indeterminate set (§5) is the
   same readout surfaced at query time.

## 10. SPEC delta inventory (for later sessions; nothing edited now)

- **New §18.11 — derive.** Demand-driven resolution of one (input, declared chain) target:
  cache-first (key before model call), recursive over `input.producer` chains, binding every
  input to the §18.10 current artifact. Fixes the pay-on-hit defect for the eager sweep as a
  by-product (the sweep becomes "derive over all eligible sources").
- **§18.7 amendment — `assemble`.** One deterministic multi-input producer kind: input_hash =
  hash of sorted member content hashes, lineage edges to every member. All LLM transforms
  remain single-input. The amendment carries §5's honesty for its own denominator: thread
  state is computed over the members *present*, and membership recall bounds it — an
  uncertifiable undercount (the structural twin of retrieval recall), so `thread_state`
  answers state the member count and that membership is not certified. (F4 only; lands
  with D4.)
- **New external content types** for plan/operator stages, joining the §18.9 family, all
  excluded from `CHUNKABLE_CONTENT_TYPES`.
- **The operator-algebra coverage contract** (§5) recorded at spec level for the executor.
- **Explicitly unchanged:** key schemas v1–3 (`src/pkm/hashing.py`), §6.2 append-only
  atomicity, the chunking gate, §18.10 read-only staleness, the §18.9 retrieval gate.

## 11. Phasing — dependency order with eval gates

Each phase is independently valuable against a named FAILURES entry, gated on
`scripts/run_eval.py` answer-grounded evals plus the dogfood log. No timelines.

| Phase | Builds | Gate |
|---|---|---|
| **D0** | `pkm derive` mechanism (SPEC §18.11) + pay-on-hit fix + demand logging | Hermetic stub-producer tests; double-run idempotency; telemetry proves **zero model calls on a warm derive** |
| **D1** | F3 temporal: `doc_date` projection (deterministic email-date parse; small local-model transform otherwise) + recency predicate in the ask path | Temporal eval questions green; **indeterminate set reported** — documents whose date failed to extract are named, not dropped; no regression on the existing set |
| **D2** | F2 subject: `doc_subject` closed-enum transform (§18.8 pattern) + deterministic owner-profile filter in the query executor (profile never enters pkm) | "My Israeli ID"-class collisions stop returning templates; **failed classifications surface as indeterminate, not excluded** |
| **D3** | F1 aggregate + planner v0: template router with predicate slots; retrieve → derive field-extraction per hit → deterministic agg → synthesize | Citation-guard per addend **and** the coverage contract — answers state the **retrieval-anchored** denominator with per-operator attribution of indeterminates (§5 composition rule) and cite every set; a compound question exercises predicate slots; **honest ≠ useful**: an indeterminacy-dominated case (most addends unresolvable) must be flagged as such, not green-lit as a sum; second run fully warm (`cache_stats`) |
| **D4** | F4 threads: `assemble` SPEC amendment; email producer `_VERSION` bump adding In-Reply-To/References; `thread_state` transform; `thread` template | "Awaiting reply?" eval questions green; thread answers carry the member count and the uncertified-membership caveat (§5's twin floor) |

**D4's real cost is the reclassification, not the re-render.** The `_VERSION` bump changes
every email artifact's *content* by construction, so every content-hash-keyed LLM transform
over emails — `doc_subject` (D2), and any other email-input `sem_map` — reruns across the
entire email corpus on next demand. Early cutoff cannot rescue this: the hinge fires only
when regenerated content is identical, and here it genuinely changed. `doc_date(email)`
reruns too but is deterministic and free. So D4 is value-independent of D1–D2 but not
input-independent of them; budget the model spend of the corpus-wide reclassification, with
the re-render itself the cheap half (`pkm stale` flags the old chain throughout).

## 12. Successor designs (named, not designed here)

The next two legs of the geodesic, in order:

1. **Query-with-confidence** — assertions surfaced *with* their posterior and provenance,
   dogfooded against real questions. Interfaces this design already secures for it:
   per-answer lineage (§18.9), per-node provenance (§9.2), the stale-set annotation (§7), and
   the demand logs (§9.3). The `../credence` repo is reference material.
2. **Embeddings/hybrid retrieval** (§6's deferral) — its own design when a failure demands
   it, under the two recorded constraints.

The **VOI governor** is explicitly deferred beyond both: it is the abstraction the
no-abstraction-before-three-implementations rule forbids until the demand logs and the
confidence layer exist to calibrate against.

## 13. Open questions

- ~~Lift the north-star statement (§0) into PRINCIPLES.md?~~ Done — PRINCIPLES §16
  (2026-06-11).
- Planner escape hatch: free-form DAG emission / organic taxonomy emergence — what failure
  evidence opens it?
- Disjunctive/nested predicates ("supplier X or Y, not yet paid") — beyond the AND-only
  fence; needs its own failure evidence.
- Abstention threshold on the indeterminacy ratio: "summed 3 of 23; 20 could not be
  extracted" is honest but useless — when does the executor abstain instead of answer? A
  posterior-on-the-answer decision, deferred to query-with-confidence (§12.1); D3 only flags
  indeterminacy dominance.
- Lifting the §18.9 answers-into-retrieval gate once staleness annotation is proven.
- Embeddings/hybrid trigger condition (which FAILURES pattern would demand vectors rather
  than metadata?).
- Demand-log units for later VOI calibration: tokens + cost_usd + latency are logged from
  D0; human-annoyance (the ask-channel cost) is a placeholder with no measurement yet.
