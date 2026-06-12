# System design — one framework, every component adapted to it

> **Status: adopted 2026-06-11 (owner-approved); sequencing amended 2026-06-12 by
> [`bayesian-foundations.md`](./bayesian-foundations.md) (§8 below).** This is the
> whole-system view: the objects, the one binding invariant, the loop, and the adaptation
> map for everything already in the tree. The philosophy lives in [`PRINCIPLES.md`](../PRINCIPLES.md); the
> derivation leg's detailed design lives in
> [`derivation-engine-design.md`](./derivation-engine-design.md) (adopted the same day) and
> is referenced, not restated. Sequencing changed with adoption: phases execute
> continuously, gated by answer-grounded evals — the failure log remains the evidence
> stream, no longer the permission gate (PRINCIPLES §9 as amended).

## 1. The kernel, restated as a system

The owner's articulation (2026-06-11, verbatim in substance): there is **knowledge**;
**questions** are answered from it — or honestly not; **actions** are taken from knowledge
plus the owner's **utility**; **transformations are endogenous and demand-led** — the
system decides to derive because a question (later: a decision) needs it; and **knowledge
grows from answers and actions**. GTD, CRM, and pkm are not three systems: one substrate,
many projections. A question like *"how much money did I spend last year?"* is not a
feature — it is a demand the system plans for (extract, classify, sum) and executes over
the DAG, deriving what is missing and citing everything.

## 2. The objects

- **Knowledge** is the derivation DAG: immutable sources plus every artifact derivable from
  them — content-addressed, cited, idempotent, composable (PRINCIPLES §2). It includes
  projections of the act ledgers (§5 below). Knowledge is recorded evidence with
  provenance, not truth (pkm SPEC-PRINCIPLES §4); truth-assessment is the credence layer's
  future remit.
- **A question** is a demand on the DAG. It resolves to a **plan** (itself a cached,
  corpus-independent derivation — engine design §4), whose execution materialises exactly
  the missing nodes (`pkm derive`, SPEC §18.11, cache-first), then synthesizes an answer.
  The existing expand → retrieve → synthesize pipeline is the degenerate plan.
- **An answer** is an artifact: every stage records through the SPEC §18.9 file-first seam,
  with citations, abstention below the relevance floor, and the indeterminacy readout
  (engine design §5). Answers entering retrieval — the second growth loop — is the §18.9
  gate lift, a named successor.
- **An action** is an event appended to an act-layer ledger; truth is the fold; every
  read-model is rebuildable (PRINCIPLES §7). Ledgers are the only mutable state in the
  system.
- **A transformation** is a node-producing edge on the DAG — LLM or deterministic, declared
  (pkm transforms) or executor-side (operators). Demand is the only scheduler today
  (exogenous: an owner question); the VOI governor that makes demand fully endogenous is
  deliberately last (engine design §12).

## 3. The binding invariant — everything is an edge on the DAG

Owner directive: *all derivations, aggregations, LLM calls are stored as edges on the DAG.*
Binding form: **no computation in the answer path is off-ledger.** Every LLM call (declared
transform or synthesis stage), every deterministic operator application (filter, agg, a
ledger fold), every plan, and every answer is a content-addressed node with lineage edges
to its inputs, its key computed before any model call, its resolution demand-logged.

Already true for: declared transforms (SPEC §18.7), `pkm derive` walks (§18.11, demand log
under `logs/demand/`), and ask's three stages (`life_agent/core/derivations.py`, §18.9
file-first). Made binding by this design for: the D3 executor operators (each application a
recorded §18.9 stage in the new plan/operator content types, per-addend citations — engine
design §4–5) and the act-ledger fold projection (§5 below — stamped with the ledger head it
folds, the ledger itself the cited source). Consequences, in order of importance: answers
audit to leaf bytes; warm chains cost zero model calls; the demand log accumulates the
governor's future calibration corpus (engine design §9.3).

## 4. The loop

```
L0  event logs            GTD ledger (events.jsonl) · future act ledgers     [truth = fold]
    + immutable sources   documents, mail, notes, chat                       [pkm sources]
L1  derivation DAG        pkm transforms + derive · executor operators · plans · answers
L2  credence              assertions as distributions + provenance           [being wired — Ask v0; ../credence]
L3  VOI governor          derive / ask / act ranked in one queue             [future, last]
L4  act seam + reach      Telegram GTD commands · digest · email→GTD projector
```

Two growth loops close the cycle (owner: "knowledge grows from answers and actions"):
**actions → knowledge** — the ledger projection is ingested knowledge (Phase 1), so every
Asserted/Disposed/Amended event becomes askable; **answers → knowledge** — §18.9 records
exist now; retrievability awaits the gate lift (successor). Outcome observation (L4 → L0)
exists today only as the GTD ledger itself; richer outcome capture is Phase-3 territory.

## 5. The act ledgers and their knowledge projections

The derive/act boundary test is unchanged (PRINCIPLES §7): derivable-from-sources ⇒ pkm
transform or read-time projection; human-authored mutation ⇒ act-layer events. What this
design adds is the **return path**: every act ledger gets a deterministic, pure
**knowledge projection** — `fold(events)` rendered to a document at one stable declared
path, stamped `as of event N / ledger-content-hash`, ingested like any source, refreshed
**on demand** at question time when the ledger head has moved (the degenerate, zero-cost
case of derive-when-stale: deterministic and near-free, so the derive-or-not decision needs
no VOI machinery). The GTD is the first instance (`tasks/knowledge.py`, the
mutable→knowledge mirror of `tasks/project.py`); any future ledger (CRM notes, if decision
#3 lands that way) inherits the pattern. Supporting pkm rule (generic, SPEC-first):
**retrieval currency for evolving sources** — when ingested versions share a declared path,
only the newest success is retrievable; superseded versions stay catalogued, excluded
countably (nothing vanishes, nothing silent).

## 6. Question execution

Engine design §3–§8 governs; the split is mechanism in pkm, policy in life_agent. The
planner (v0: template router `lookup | aggregate | temporal-lookup`, later `thread`, with
an AND-only predicate-slot list) and the operators (`retrieve`, `sem_map` = declared
transforms, `filter`, `agg`, later `assemble`) live in the life_agent executor. The LLM
appears only in cached per-document (or per-thread) projections; everything question-shaped
downstream is deterministic. The coverage contract is algebra-wide: satisfied ·
unsatisfied · indeterminate, indeterminates attributed and carried, the denominator
anchored at the retrieved set, retrieval recall stated as uncertifiable. Every surface
obeys the [interaction contract](./interaction-contract.md): one grammar per concept,
nothing silent.

## 7. Component map — what exists, its place, its adaptation

| Component (exists) | Role in the framework | Adaptation |
|---|---|---|
| pkm ingest/extract/chunk/FTS+vss | knowledge admission | currency-for-evolving-sources rule (Phase 1) |
| pkm transforms + `pkm derive` (D0, landed) | LLM projections, demand-driven, cache-first | new declarations only: `doc_subject` (D2), field extraction (D3), `thread_state` (D4) |
| `doc_date` + temporal ask mode (D1, landed) | first deterministic predicate | none |
| `scripts/ask.py` (expand→retrieve→synthesize) | the query executor; current pipeline = the degenerate plan | GTD staleness refresh (Phase 1); planner v0 + operators + coverage contract (D3) |
| `life_agent.tasks` (events/store/commands) | the first L0 act ledger + its fold | knowledge projection `tasks/knowledge.py` (Phase 1) |
| `tasks/project.py` (email→GTD) | immutable→mutable bridge | unchanged; gains its mirror (mutable→knowledge) |
| `life_agent.reach` (telegram/jarvis/digest) | L4 transport + persona, contract-governed | unchanged |
| owner profile (`/tell`) | identity policy, agent-side only | unchanged; D2's filter consumes it — it never enters pkm |
| `scripts/run_eval.py` (answer-grounded) | the gates | per-phase gate assertions (engine design §11) |
| `src/pkm/mcp_server.py` (dormant) | endorsed seam for the future spine | unchanged |
| `../credence` (Julia) | **L2 — the brain** | **wired (Phase 1.6 / Ask v0)**: the skin's JSON-RPC-over-stdio seam behind `src/life_agent/core/brain.py`; query-with-confidence executes now as the Bayesian re-derivation of Ask ([`bayesian-foundations.md`](./bayesian-foundations.md)) |
| CRM (dissolved faculty) | resolved into the framework | LLM projections = transforms; deterministic reads = executor-side; threads/awaiting-reply = D4; mutable notes (#3) & alias dedup (#4) stay open |

## 8. Sequencing

The execution plan (owner-approved 2026-06-11): **Phase 0** adopt + doc adaptation (this
document) → **Phase 1** the act ledger becomes knowledge (currency rule · `tasks/knowledge.py`
· demand-led refresh in ask) → **Phase 2** = engine D2 (subject + owner filter) — both
landed. **Amended 2026-06-12** ([`bayesian-foundations.md`](./bayesian-foundations.md),
owner-adopted): from here the program is that document's §12 — **Ask v0** (outcomes log →
credence seam → lookup family → narrative subsumption), then the **aggregate family**
(subsumes engine D3: its planner/operators are built as the family's machinery) and the
**thread family** (subsumes engine D4: `assemble` remains the one SPEC shape change).
Each stage lands SPEC-first/TDD where it touches pkm, gated by the foundations doc's §8
decision-weighted gates. Successors, named not designed: structure learning
(`program_space`), the VOI governor, the §18.9 gate lift.

## 9. Boundaries that hold (unchanged, restated as commitments)

pkm stays domain-free and identity-free (mechanism, not policy). The derive/act diagnostic
decides where state lives; there is no third category. The interaction contract governs
every human-facing surface. PII stays out of tree; secrets in the keyring; networked
surfaces Tailscale-only. Determinism remains semantic, defined in pkm — not redefined here.

## 10. Genealogy — where the ideas came from, and their fates

The genesis input is [`nix-for-documents-report.md`](./nix-for-documents-report.md)
(commissioned research, 2026-05 — an input, never a mandate). Its idea-by-idea fate, so the
trail is auditable:

| Report idea | Fate |
|---|---|
| suspending scheduler + constructive traces ("Cloud Shake" quadrant) | absorbed — the formal model behind `pkm derive` (engine design §0/§2) |
| demand-driven materialisation; early cutoff | **landed** (D0; content-hash-keyed edges) |
| "design the invalidation UI around demand, not auto-re-derivation" | adopted verbatim — staleness stays read-only, rederivation lazy (engine §7) |
| LOTUS/DocETL semantic-operator algebra | adopted **bounded**: v1 operator set (engine §5); `sem_agg` folds rejected (provenance-destroying) |
| LLM planner emits a small DAG per question ("Phase 3") | adopted as planner v0 — template router + predicate slots (engine §8 / D3) |
| Hamilton as orchestrator | rejected for now (ROADMAP verdict; `artifact_lineage` stays Hamilton-ready; revisit Phase 3) |
| DuckDB `vss`+`fts`, over-fetch k·10, persistence flag | **landed** |
| DSPy | offline-only policy (freeze tuned prompts; never runtime) |
| temp-0 ≠ deterministic; a cache hit is deterministic regardless | already pkm's semantic determinism contract (PRINCIPLES §10) |
| cache-key schema crux (model snapshot, engine version, template/bindings split) | absorbed into schema-3 keys; remaining hardening items on the ROADMAP |
| Karpathy compiled wiki as warm-cache layer | built, **measured, retired** (PRINCIPLES §14 — does not scale, hallucinates) |
| PROV-O sidecars; CIDv1/BLAKE3 | not adopted — lineage lives in the catalogue; SHA-256 addressing stands |
| open question: do higher-order views earn their cache slots? | the demand log's purpose — plan-key vs node-key reuse, logged from D0 (engine §9.3) |
