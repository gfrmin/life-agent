# Unified ledger design — one append-only event stream, every read-model a fold of it

> **Status: draft for owner review (2026-08-18) — Phase 1 of the ledger-unification
> tranche 1; owner approval of this document gates Phase 2 (the golden-replay harness).**
> Composes with [`PRINCIPLES.md`](../PRINCIPLES.md) §7/§16, [`system-design.md`](./system-design.md)
> §3/§5, [`act-layer-events.md`](./act-layer-events.md), [`bayesian-foundations.md`](./bayesian-foundations.md)
> §2/§8, pkm [`SPEC-PRINCIPLES.md`](./pkm/SPEC-PRINCIPLES.md) §1–§4 and SPEC §7.1. It rests on
> the Phase-0 census, [`unification/reports/r00-census.md`](./unification/reports/r00-census.md)
> (cited below as *r00 a.1 #n*, *a.2 #n*, *(c) #n*, *(e)*), and on the owner-signed Phase-1
> rulings **R1–R8** (cited by number). Reviewer rulings relayed on 2026-08-18 but not in the
> signed Phase-1 brief are cited as *reviewer R2a / R8a / R9 / R10 / R11* and listed for
> signature in r01. Nothing here changes code, `PRINCIPLES.md`, or any pkm SPEC — amendments
> are proposals in Appendix A. British spelling; no corpus values; `$LIFE_AGENT_KB`-relative
> paths only.
>
> **Revision 2026-08-18 (post-review, before Phase 2):** the reviewer's conditional approval
> is folded in — §10 gains the torn-tail protocol (the one required clarification); reviewer
> rulings Q6–Q9 (r01 numbering) are applied in §2 (`instrument:` namespace on `kernel_id`), §4,
> §8 (C0 duplicate-key flag), §9 (kill categories + a pinned-invariance fixture) and §12 (Q1, Q4,
> Q13 resolved). Owner signatures on r01 Q1–Q5 are pending; the sections they touch are
> unchanged.
>
> **Revision 2026-08-18 (Phase 3 pre-C0, reviewer rulings V4/V5/V8 on r02):** §9 gains (i) a
> fifth kill category — an *unrouted Claude verdict* must kill A7 and exactly A7 (V5), pinning
> the routing-gated join (A6) vs routing-blind map (A7) asymmetry beside the unrouted-reaction
> invariance fixture; (ii) the verdict line's `EXACT`/`SUPERSET` flag semantics (V4); (iii)
> the A11 same-function contract (V8). No criterion is weakened; §9 is otherwise unchanged.
>
> **Revision 2026-08-18 (Addendum D, owner signature S11 — verified-citation upgrades):** §10's
> order-of-magnitude target now carries OpenHands' verified figures (0.20 ms median / 0.31 ms
> P95 per-event persist latency, Table 3 of arXiv:2511.03690v2) in place of the "preprint
> figure, unverified" marker, and the SSGM sentence is reframed to the paper's own terms (the
> latency–safety trade-off, arXiv:2603.11768v2 §1 contribution 4; Principles 1–2). Source: the
> owner's verify-before-cite memo (2026-08-18), which checked each figure against the papers'
> own tables and body text. Two sentences of prose; no criterion, schema or code change.
>
> **Revision 2026-08-18 (r03a review — C0–C4 accepted; reviewer rulings Q7–Q13 applied):** §4
> gains the schema-3 `kernel_id` completeness paragraph (Q7: accepted for tranche 1; **no
> backfill**; forward fix queued as a proposal) and the sweep-order consequence (Q10); §7 records
> materialisation as the adapters' standing realisation (Q8); §9's A2 row names its sha component
> legacy-pinned by R1 (Q12); §10 states the **durability split** — per-line for live appends,
> per-batch for migration and sweeps — and the **manifest lock** (Q11); §11 records the standing
> **locator policy** (Q13). Q9 (seeds by re-migration) accepted without text change. No criterion
> is weakened. Same day, on measurement: §10's unmeasured "an fsync per line is within it on this
> disk" is replaced by the measured mirror cost (~30 ms per call on the stream's volume; the
> 0.20 ms target is not met, and says so).
>
> **Revision 2026-08-18 (r03 close — reviewer rulings on the C6 finding):** §4 names the
> **dangling-identity class** (occurrence records the stream retains while the pointed-at
> content is gone — functionally re-derivable, identity-unrecoverable); §9's A11 row carries the
> **merge-verdict amendment**: *stream ⊇ legacy, with the difference exactly the enumerated
> swept set, verified by key list, not by count* — a reviewed restatement under the
> never-silently-weaken rule, cited to the ruling; the RED transcript at T2 stands as the finding
> of record and is never re-run to green. The tranche's dual-write end-state was reached
> (r03-merge); the pkm-side fixes the finding calls for are a separate micro-tranche.

## 0. What this document is (and is not)

**The mission** (tranche brief): unify the repository's immutable-record flavours — pkm
sources/derivations, act-ledger events, demand-log entries, outcomes, decision/calibration
records — into **one append-only event stream**, such that every current read-model (the
GTD task list, the KB knowledge projections, cached answers, calibration data) is a fold of
that stream. **Outcome preservation is binding:** after migration, replaying the unified
stream reproduces the existing projections — byte-identical where the artefact is
deterministic, semantically identical where pkm's determinism contract (SPEC §7.1) says so.
The derive/act boundary (PRINCIPLES §7) survives as a **predicate on events**, not a substrate
split.

**What tranche 1 delivers and does not.** It delivers: this design (Phase 1); a golden-replay
harness with a demonstrated kill (Phase 2); the unified stream, its migration writer, and one
fold adapter per read-model, behind the green harness, with the old stores **still written
(dual-write)** (Phase 3). It does **not** deliver cutover, retirement of any old store, any
change to `src/pkm`'s cache semantics or SPEC, any brain-seam change, or any spine decision —
each is a separate, owner-signed step. Corrections to any store are compensating entries;
nothing is deleted or rewritten.

**Prior-art positioning.** The substrate pattern is published: ESAA (arXiv:2602.23193,
Feb 2026) uses event sourcing as the source of truth with projections made verifiable by
replay, and the OpenHands Software Agent SDK (arXiv:2511.03690, rev. Apr 2026) rests on a typed
append-only event log with "negligible event-sourcing overhead" reported in production. This
document's contribution is **not** the pattern — it is the unification of the repository's
existing flavours (r00 counted twenty on the life_agent side and eighteen on the pkm side,
under three durability regimes, four clocks, and seven supersession rules) and of the
decision layer above them, with outcome preservation as the acceptance test.

**One-sentence summary.** A record becomes an *event* `(source_id, seq, record-verbatim, …)`;
the stream's total order is `(source_id, seq)` (R4); pkm's content-addressed artefacts stay
identities and the stream records their *occurrences* (R5); every fold declares its ordering
key and re-reads recorded draws (§5); each read-model gets one adapter whose output is
compared against a frozen snapshot by a pre-stated criterion and command (§9).

## 1. The record flavours today — the scope table

The census inventory is the authoritative list; this table dispositions every row for
tranche 1. Dispositions: **migrates** (historical records enter the stream in Phase 3),
**dual-written** (its live writer also appends to the stream from Phase 3), **excluded (R8)**
(recorded here, not silent), **identity, not event (R5)**, **projection / config / cache**
(the census's non-fold mutable stores). Author per §2.

| Census row | Flavour (source store) | Disposition | `source_id` | Notes |
|---|---|---|---|---|
| a.1 #1 | outcomes log `calibration/outcomes.jsonl` | migrates + dual-written | `calibration.outcomes` | grader vocabulary closed already; `format_version 1` |
| a.1 #2 | decision log `calibration/decisions.jsonl` | migrates + dual-written | `calibration.decisions` | v1 lines replay with defaults (r00 a.1 #2) |
| a.1 #3 | reaction log `calibration/reactions.jsonl` | migrates + dual-written | `calibration.reactions` | one bit; supersession latest per `(decision_id, kind)` |
| a.1 #4 | Claude verdict log | migrates + dual-written | `calibration.claude_verdicts` | owner-precedence merge is a *declared* cross-source order (§3) |
| a.1 #5 | gather-outcome log | migrates + dual-written | `calibration.gather_outcomes` | gains `format_version` only on the stream envelope; the legacy line is carried verbatim |
| a.1 #6 | corrections log `calibration/corrections.jsonl` | migrates + dual-written | `calibration.corrections` | owner-authored evidence, no reader today; small |
| a.1 #7 | utility elicitations `utility/elicitations.jsonl` | migrates; live: **swept** (no in-code writer — hand-authored, r00 a.1 #7) | `utility.elicitations` | the fold's first evidence segment (§3) |
| a.1 #7 | `utility/model.yaml` | **declared config input** (its sha is provenance in gate `run_meta`) | — | not an event; a change is a new model, pinned by `fold_version` |
| a.1 #8 | gate run outputs `eval/gate/*` | **projection** (per-run snapshot; archive is history) | — | not a ledger (r00: fixed-path clobber); reproducible from stream + `run_meta` |
| a.1 #9 | membrane shadow log `membrane/shadow.jsonl` | **excluded from tranche-1 migration; named candidate later flavour** | (`membrane.shadow`, reserved) | shadow-only, never on the decision path; its report is a fold of it, so it *is* ledger-shaped — deferred to keep the tranche to the mission's four read-models (§12 Q9) |
| a.1 #10 | GTD ledger `tasks/events.jsonl` | migrates + dual-written | `act.tasks` | the bitemporal precedent (`tx_time` + `valid_time`) |
| a.1 #11 | `tasks/gtd.db`, `tasks/state.md` | **projections** (folds of `act.tasks`) | — | §7 adapters; criteria §9 (R1, R2) |
| a.1 #11 | `jarvis/jarvis.db` | pre-cutover snapshot, read-only | — | untouched |
| a.1 #12 | trips ledger `trips/events.jsonl` | migrates + dual-written (**reviewer R10**, awaiting signature) | `act.trips` | the one non-file-order fold and the payload-inclusive `event_id` — the design's hardest ordering case |
| a.1 #12 | `trips.db` `reservation` | **projection** | — | §7 |
| a.1 #12 | `trips.db` `source`, `trip` | **mutable side-stores, not folds** (`INSERT OR REPLACE`) | — | out of the golden set; dispositioned as *rebuildable cache of ingest metadata* — an open item whether they become `act.trips` amendments later (§12 Q7) |
| a.1 #13 | §18.9 derivation records (life_agent writes into pkm's cache) | **identity, not event (R5)**; their **occurrences** migrate | `pkm.artifact` | one occurrence per `meta.json` (`produced_at`), see §4 |
| a.1 #14 / a.2 #14 | pkm demand log `logs/demand/*.jsonl` | migrates + **swept** live (R6) | `pkm.demand` | pkm code untouched; the sweep is life_agent-side (§8) |
| a.1 #15 | fair-fight run directories | **excluded** (reviewer R8a) | — | already content-pinned by `questions.sha256`; per-run |
| a.1 #16 | eval labels `eval/labels.jsonl` | migrates + dual-written | `eval.labels` | owner gold; last-match-wins fold |
| a.1 #17 | judge verdict cache | **excluded; named candidate** | — | a content-addressed record living outside pkm's cache — the natural home is a §18.9 stage (§12 Q10) |
| a.1 #18 | dogfood markdown | **excluded** (reviewer R8a: owner-facing evidence, not a ledger) | — | |
| a.1 #18 | `owner.md` | **declared config input** (its sha keys `owner_match_key`/`synthesize_key`) | — | not an event flavour (reviewer R8a) |
| a.1 #19 | deliberate side records, void manifest | **excluded** (transient); the void manifest stays the compensating record of the one deletion path | — | |
| a.1 #20 | snapshot eval artefacts | **projections**, excluded (reviewer R8a) | — | |
| a.2 #1–3 | pkm `sources` / `source_paths` / `source_tags` | **identity** (`source_id`) + **observational state**; not events in tranche 1 | — | `source_paths` is append-only but has no reader; candidate later flavour `pkm.source_seen` (§12 Q11) |
| a.2 #4–6 | artefacts, `artifacts`, `artifact_lineage` | **identity, not event (R5)**; occurrences migrate as `pkm.artifact` | `pkm.artifact` | the catalogue is a rebuildable index (SPEC §13.1) — never a source |
| a.2 #7–10 | chunks, FTS, path currency, staleness | **derived index / view / computation** | — | out of scope |
| a.2 #11 | `schema_meta` | pkm's own hash-verified migration ledger | — | untouched (frozen foundation) |
| a.2 #12 | approvals | **mutable lifecycle state** (UUID id, UPDATE in place) | — | not an event flavour in tranche 1; candidate `pkm.approval` (§12 Q11) |
| a.2 #13 | transforms telemetry log | **excluded from migration; named candidate later flavour (R8)** | (`pkm.telemetry`, reserved) | |
| a.2 #15 | pkm diagnostic log | **excluded (R8)** | — | operational |
| a.2 #16 | MCP tool-call log | **excluded (R8)** | — | SPEC-sanctioned non-idempotence |
| a.2 #17 | `external/pending.txt` | **queue**, rewritten (r00) | — | not a record |
| a.2 #18 | transform declarations | **config input** | — | `declaration_hash` is provenance |
| r00 a.4 | `config/data-sources.yaml` | **declared config input** | — | |
| r00 a.4 | `catalogue.duckdb` | **rebuildable index** | — | |
| r00 a.4 | `gtd.db` incremental in-place | **projection** (drift bounded by rebuild) | — | §7 |
| r00 a.4 | `lookup._U_BAR` memo | **cache in front of a fold** | — | invalidated by `fold_version` |
| out of tree | `$LIFE_AGENT_KB/FAILURES.md` | open item — whether it becomes an event flavour (R8) | — | §12 Q12 |

Two consequences of the table. First, tranche 1's **migrating sources** are exactly twelve:
`calibration.{outcomes, decisions, reactions, claude_verdicts, gather_outcomes, corrections}`,
`utility.elicitations`, `act.tasks`, `act.trips` (reviewer R10), `pkm.artifact`, `pkm.demand`,
`eval.labels`. Second, the read-models whose folds must be reproduced (§7/§9) are the
mission's four families plus what the census showed hangs off them: the GTD read-model and
knowledge projection, the trips projection, the utility posterior, the calibration curves and
the reaction/verdict/gather folds, and the cached-answer set with its pkm index.

## 2. The event schema

One typed envelope, one `format_version`, the source record carried **verbatim** so that every
adapter in §7 is the *existing* fold applied to `record` — the design adds no second
serialisation of any flavour.

```python
@dataclass(frozen=True)
class UnifiedEvent:                       # format_version = 1
    event_id: str        # sha256(canonical_json({"source_id", "seq", "record"})) — reviewer R11:
                         #   the occurrence's identity = source + assignment pair + verbatim record;
                         #   two content-identical appends are two events; derived fields never hashed
    source_id: str       # closed enum — the twelve §1 source ids (+ reserved names)
    seq: int             # dense from 1 per source_id; assignment rules below
    tx_time_raw: str     # the source's own stamp, VERBATIM (whatever field it was: tx_time /
                         #   timestamp / produced_at / ts) — never destroyed, never rewritten (R4)
    tx_time: str | None  # DERIVED annotation: UTC-aware ISO where the source clock is known
                         #   (aware ISO → itself; naive-UTC catalogue stamps → +00:00; epoch float →
                         #   UTC); None for naive-LOCAL stamps (act.tasks, act.trips) — never hashed,
                         #   never ordered on across sources (R4)
    kernel_id: str       # the instrument that produced the record (table below); for pkm
                         #   occurrences the §2-of-foundations instrument identity = the cache-key
                         #   payload minus input_hash (R5, sharpened), namespace-tagged
                         #   `instrument:sha256:<hex>` so it can never be mistaken for a cache key
                         #   (reviewer Q7); never computed inside pkm
    inputs: tuple[str, ...]   # content addresses the record depends on (table below)
    output: str | None   # the content address the occurrence produced or points at (R5)
    author: Literal["world", "owner", "agent"]
    recorded_draw: dict | None   # {"kind": "content"|"uuid"|"seed", "ref": <address or value>}
                                 #   when the record embodies a stochastic draw (§5)
    record: dict         # the source record, verbatim (parsed JSON of the legacy line; for
                         #   pkm.artifact: {"meta": <meta.json>, "lineage": <lineage.json>|None})
    format_version: int = 1
```

**Serialisation.** One JSON object per line, `json.dumps(sort_keys=True, ensure_ascii=False,
separators=(",", ":"))` — the calibration logs' existing convention (r00 a.1 #1–#4).
`record` is the parsed legacy JSON re-serialised canonically; **the legacy line's own bytes are
not the identity** (`event_id` hashes the canonical form), so a legacy line whose keys were
unsorted (gather rows, corrections, labels — r00 a.4) maps to a stable id.

**Per-source `seq` assignment.** No existing record carries a sequence (r00 a.4).
*At migration:* `seq` = the ordinal of the record among the **parsed** records of its source, in
that source's canonical order — file order for every JSONL flavour; `(produced_at, cache_key)`
ascending for `pkm.artifact` (the SPEC's own deterministic-but-not-meaningful tiebreak, r00
a.2 #5); UTC-day file then line order for `pkm.demand`. Unparseable lines (the act ledgers'
readers skip them silently today, r00 a.4) are **not** events; their count per source is
recorded in the migration manifest and reconciled in the two-route count (§8). *At write (dual
write):* each live writer appends its legacy line first (unchanged behaviour), then appends the
event with `seq = last(seq of source) + 1`. Because §10 lays the stream out as one segment
file per `source_id`, `seq` is the segment's ordinal **among parseable lines** (a
manifest-quarantined torn tail is not a line — §10) — no cursor file, no cross-source
coordination. Sources with no in-code writer (`utility.elicitations`) or a writer that must not
change (`pkm.demand`, `pkm.artifact` — pkm is frozen) are **swept**: a life_agent-side sync
appends every record present in the legacy store beyond the last mirrored one, in the source's
canonical order (§8 C5).

**`author` and `kernel_id`, per flavour.**

| `source_id` | `author` | `kernel_id` | `inputs` | `output` | `recorded_draw` |
|---|---|---|---|---|---|
| `calibration.outcomes` | `agent` for graders `eval_*`/`audit`; `owner` for grader `owner` | `grader:<grader>` + `instrument_identity` digest | `lineage_keys` | `None` | `None` |
| `calibration.decisions` | `agent` | `decide:<family>[:<instrument>]` | `posterior_summary`-referenced lineage is not on the row; `inputs = ()` and `utility_fold_version` stays in `record` | `decision_id` (= §18.9 answer cache key or the `ab-…` digest) | `None` (the answer artefact is the draw; see `pkm.artifact`) |
| `calibration.reactions` | `owner` | `owner:verdict` | `(decision_id,)` | `None` | `None` |
| `calibration.claude_verdicts` | `agent` (issued on the owner's behalf; overrulable — r00 a.1 #4) | `claude-code:verdict` | `(decision_id,)` | `None` | `None` |
| `calibration.gather_outcomes` | `agent` | `executor:grow:<probe>` | `()` | `None` | `None` |
| `calibration.corrections` | `owner` | `owner:correction` | `()` | `None` | `None` |
| `utility.elicitations` | `owner` | `owner:elicitation` | `()` | `None` | `None` |
| `act.tasks` | `owner` for `origin="human"` asserts and every disposal/amend/complete issued through `commands.*`; `agent` for `origin="email"` asserts (`project.py`) and `superseded` | `owner:command` / `tasks.project@<action_items instrument>` | `()` (the email citation lives in `record.payload`) | `identity` | `{"kind": "uuid", "ref": identity}` for `new_identity()` asserts (r00 a.1 #10) |
| `act.trips` | `world` for `observed` (a source attests a reservation), `owner` for `amended`/`cancelled` by hand, `agent` for `superseded` | `trips.ingest:<fidelity>` / `owner:command` | `(source_id,)` when present | `identity` | `None` |
| `pkm.artifact` | `agent` | `instrument:sha256:<hex>` where hex = `sha256(canonical_json(key payload − input_hash))` — computed life_agent-side from `meta.json` (`producer_name/version/config_hash`, `cache_key_schema_version`, and for schema 3 `model_identity_hash`, `engine_version`, `prompt_template_hash`, `output_schema_hash` from `producer_metadata`/lineage — see §4) | lineage input cache keys ∪ `{input_hash}` | `cache_key` | `{"kind": "content", "ref": cache_key}` for schema-2/3 (LLM) producers; `None` for schema 1 |
| `pkm.demand` | `agent` | `derive:<transform_name>` | `(input_cache_key,)` | `cache_key` (may be `""` — r00 a.2 #14) | `None` |
| `eval.labels` | `owner` | `owner:label` | `()` | `None` | `None` |

The `kernel_id` vocabulary for non-pkm sources is a **declared closed set** (like the graders'
vocabulary), checked at construction; growing it is a code edit, never a silent new string.

**Bitemporality.** Only `act.tasks` is bitemporal today (`tx_time` + `valid_time`, r00 a.1
#10). The envelope does not add a `valid_time` column: valid time is a property of *what a
record asserts* and stays inside `record` for the flavours that have it; TOKI's treatment
(§4) is the reference for why the envelope's `tx_time_raw`/`tx_time` are transaction time only.

## 3. Ordering and the merge rule

**R4 total order.** The stream's total order is the deterministic interleave keyed by
`(source_id, seq)`; concretely, the union of the per-source segments in the source order the
manifest declares, each in `seq` order. **Cross-source `tx_time` comparison is never
semantic** — four clocks (r00 a.4). No adapter may sort on `tx_time`/`tx_time_raw` across
sources; an adapter *may* sort on a source-internal field its legacy fold already sorts on.

**The corrected invariant (reviewer correction ii).** The requirement is **not** that file order
is sacred; it is that **each fold's declared ordering key remains computable from the
stream**. The trips fold orders competing `observed` events by `(FIDELITY_RANK[fidelity],
received_at)` — fields of `record` — not by file order (r00 a.1 #12); the reaction fold uses
`seq` (file order) for last-write-wins; the utility fold uses a declared segment order.

**Declared-per-fold merge order.** Where a fold reads more than one source it declares its
merge order in §7, and the stream neither guesses nor imposes one. The in-repo precedent is
membrane `boot_snapshot`'s owner-segment-then-Claude-segment replay (r00 (c) #21). The
declared orders in this design:

| Fold | Sources | Declared order |
|---|---|---|
| utility posterior (`utility.posterior`, `current_u_bar`) | `utility.elicitations`, then `calibration.reactions` ⋈ `calibration.decisions` | elicitations in `seq` order; then the reaction evidence in **first-appearance order of `(decision_id, kind)` with the latest value** (the `dict` insertion semantics of `load_reactions :183-187`, r00 (c) #12) — stated exactly because `fold_version` hashes the event list in this order |
| Claude-verdict merge (`boot_snapshot`) | reactions, claude_verdicts, decisions | owner segment (`seq`) then Claude segment (`seq`); owner precedence by *source*, not position |
| calibration curves | `calibration.outcomes` | `seq`; supersession latest per `(edge, lineage key)` **in the superseded row's position** (r00 (c) #10) |
| GTD read-model | `act.tasks` | `seq` (the `store.apply` replay); `events.fold` itself is order-independent |
| trips projection | `act.trips` | `(fidelity rank, received_at)` within identity; explicit `superseded` edges |
| labels | `eval.labels` | `seq`, last match wins |
| gather counts | `calibration.gather_outcomes` | none (counts) |
| pkm index replay | `pkm.artifact` | none (set); recency inside pkm remains `(produced_at, cache_key)` |

**Physical order versus logical order.** The dual-write period appends to each segment as
records arrive; the *physical* interleave across segments is incidental. Any consumer that
depends on cross-segment physical order is a bug by definition (§10 makes segments the unit).

## 4. Identity vs occurrence — content-addressing and the append log

**R5, written as the resolution.** pkm's cache is a **set of identities**: an artefact's name
is `compute_cache_key(...)` (SPEC §4.3), it has no position, and two machines producing the
same key hold the same identity. What is *event-shaped* is the **occurrence**: "at
`produced_at`, kernel K, applied to inputs I, wrote identity C" — recorded once per
`meta.json`, and "at `timestamp`, caller X demanded transform T on input I: hit/miss" —
recorded once per demand line. The unified stream records occurrences and **points at**
identities (`output = cache_key`, `inputs = lineage keys`); it never carries artefact bytes.
This is SPEC-PRINCIPLES §2/§3 restated with the two roles named: the catalogue and cache are
the *view over the record optimised for "did this happen, and what was the output?"*; the
stream is the record's *occurrence order*.

**Where the instrument identity comes from.** bayesian-foundations §2: the schema-3 key
minus `input_hash` *is* the instrument's identity. `kernel_id` for `pkm.artifact` is that
quantity made explicit — recomputable from `meta.json` alone (`producer_name`,
`producer_version`, `producer_config_hash`, `cache_key_schema_version` and, for schema ≥ 2,
the model/engine/prompt/schema hashes pkm records in the key payload). This is a **new
digest** computed outside `compute_cache_key`; it is *not a cache key* and creates no
artefact. **Ruled (reviewer Q7, 2026-08-18): pkm's "never hash outside it" rule is not
engaged** — its object is artefact identity, whereas `kernel_id` is an *instrument* identity,
recomputable from `record` (derived, not identity-bearing) — under two conditions, both
adopted: it is never computed inside pkm, and it is namespace-tagged (`instrument:sha256:…`)
so it is structurally incapable of being mistaken for a cache key. The verbatim-fields
fallback is unnecessary: the fields are already verbatim in `record`.

**Completeness (r03a C0; reviewer Q7 on r03a).** For schema-1/2 records the key payload is
complete from `meta.json`; for schema-3 records the §18.9 writer does not record the key
components (`model_identity_hash`, `engine_version`, `prompt_template_hash`,
`output_schema_hash`) in `producer_metadata`, so `kernel_id` is a digest over the **recorded
subset** — still namespace-tagged, recomputable from `record`, and the census records the
completeness class per record (`kernel_payload_complete`), so the limitation is legible, not
hidden. Accepted for tranche 1 with two riders: (i) the forward fix — the §18.9 writer
recording the components — is a *queued proposal* with a named landing site (the
module-collapse tranche, or a small standalone change after this tranche), not built here;
(ii) **existing records are never backfilled** (identity permanence) — new records simply
start a third completeness era in the census.

**Segment order after sweeps (reviewer Q10 on r03a).** The `pkm.artifact` sweep dedups by
output identity (`cache_key`), not by ordinal — R5's set semantics make ordinal dedup wrong
for a set-shaped source — and appends the not-yet-recorded identities after the existing tail
with key verification, so the segment's *physical* order may diverge from the §2 canonical
`(produced_at, cache_key)` order once sweeps have run. Harmless precisely because §3's
invariant is that each fold's ordering key is computable from `record`, not from file order:
no fold orders `pkm.artifact` by position (recency stays `(produced_at, cache_key)`).

**Dangling identities (r03 C6 finding; reviewer ruling 2026-08-18).** The stream records
occurrences and *points at* identities; nothing in the design makes the pointed-at content
durable, and the legacy cache can lose it (r03: pkm's orphan sweep at extract start removed
2,047 file-first artefacts that a swallowed duplicate-key exception had left uncatalogued for
two months). The stream then holds occurrence records whose `output` names an identity with no
content — a **dangling identity**. Named exactly: such content is *functionally* re-derivable
(the sources persist and derive is a transformation) but *identity*-unrecoverable —
re-derivation mints a **new occurrence**, and for LLM-produced schema-3 artefacts not
necessarily equal content (the recorded draw is lost, §5). The two-route count names the class
per source (`counts` → `legacy_lost_identities` + the key list); a dangling identity is a
legacy-side loss the append-only stream survived, never a mirror fault, and never a reason to
delete or rewrite the occurrence record.

**Consequence for replay (SPEC §7.1).** Replaying `pkm.artifact` occurrences reproduces the
**index** (`artifacts` + `artifact_lineage` rows — exactly what `pkm rebuild-catalogue`
reproduces, r00 a.3) and the **key set**; it never re-runs a producer. Content is verified by
*read replay* (bytes on disk under the pointed-at identity), never by re-execution — §5.

**Bitemporality.** TOKI (arXiv:2606.06240) is the formal bitemporal treatment: contradiction
resolution as write-time concurrency control with explicit transaction time and valid time.
The in-repo precedent is the GTD ledger's `tx_time` + `valid_time` (census row 10) — three
fields, deliberately not a bitemporal database (`act-layer-events.md`). The stream keeps that
posture: transaction time on the envelope (`tx_time_raw`, verbatim), valid time inside
`record` where a flavour has it, and no valid-time inference in any fold.

## 5. The recorded-draw rule

`act-layer-events.md` states it: a stochastic transform's value is not deterministic, but the
instant it runs it produces an immutable fact stamped `tx_time`; we **replay the recorded
draw, never re-roll it**. Made precise, with OpenHands' replay design as the reference:

- **Replay-as-recording** — a fold *re-reads* the logged output of a stochastic kernel. Every
  fold in §7 does only this: an LLM answer is the §18.9 artefact's bytes under its cache key
  (`recorded_draw = {"kind": "content", "ref": cache_key}`); a human-minted task identity is the
  recorded `uuid4` (`{"kind": "uuid"}`); the gate's Monte-Carlo draws are a recorded seed
  (`{"kind": "seed"}`, out of tranche-1 scope but named); a judge verdict is the cached line.
- **Re-execution** — re-invoking the kernel — is a **new occurrence**, appended with its own
  `seq`, **never substituted** for the recorded one. A regrade appends (as
  `regrade_edge_rows.py` already does, r00 (c) #23); a re-answered question is a new
  `pkm.artifact` occurrence only if its key differs (a warm key hits and produces no
  occurrence at all — the cache-first rule).

A fold that would need to call a model, a clock, or a random source to reproduce a read-model
is a defect in the fold, not a property of the data. The harness's third seeded defect (§9)
tests exactly this: a *substituted* draw must turn the comparison red.

## 6. The derive/act boundary as a predicate

PRINCIPLES §7 today draws the boundary between substrates ("a pkm transform or a read-time
projection — never a new ledger"). On one stream the same boundary is a **predicate on
events**:

```
derived(e)  ⇔  e.author == "agent"
               ∧ every address in e.inputs is content-addressed
               ∧ e.kernel_id names a declared instrument
               (recomputable-from-sources under SPEC §7.1's *semantic* determinism:
                the same event would occur; the same bytes need not)
act(e)      ⇔  e.author ∈ {"owner", "world"}
```

The diagnostic keeps its one-question form: *could this record be recomputed as a pure
function of sources + config?* — yes ⇒ `derived`, filed as a `pkm.artifact`/`pkm.demand`
occurrence or a read-time projection; no ⇒ an act event. There is no third category, and no
new ledger is ever created for a derivable fact — a `derived` event whose kernel is not
declared is a construction error. Appendix A.1 drafts the PRINCIPLES §7 replacement text.

Two edge cases the census exposed, dispositioned: `calibration.claude_verdicts` are `agent`
(issued by a model on the owner's behalf) yet are *evidence about the owner's preferences*
consumed only by the membrane, never P(U) — the predicate says `derived`, which is right: they
are recomputable in principle and overrulable by an owner reaction. `act.tasks` asserts from
`project.py` are `agent` (derived from a cited email extraction) while their disposals are
`owner` — the same identity carries both kinds of event, which is precisely why the boundary
must be per-event, not per-store.

## 7. Folds as adapters — one row per read-model

Each adapter is the **existing** fold applied to `record` in the declared order; the design
adds no new fold logic. `A(stream) := legacy_fold([e.record for e in stream if e.source_id ∈ S] in declared order)`.
**Realisation (r03a; reviewer Q8):** the adapters are realised by *materialisation* — the
stream's records are written back as legacy-shaped files (and, for `pkm.artifact`, a
cache-shaped `meta.json`/`lineage.json` tree) under the harness's work directory and the
**existing** functions run over them unchanged; this is the stronger reading of the
same-function contract (V8: same function by construction, not a paraphrase). It is the
harness's realisation; whether production adapters at cutover need an incremental form is a
cutover-tranche design question, not a debt of this tranche.

| # | Read-model / artefact | Existing fold (r00 (c) row) | Stream inputs `S` | Ordering key | Identity kind (→ §9) |
|---|---|---|---|---|---|
| A1 | `tasks/gtd.db` `tasks` table | `store.rebuild` ((c) #2) over `events.Event` | `act.tasks` | `seq` | semantic (R2) |
| A2 | `tasks/state.md` | `knowledge.render` + `write_state` ((c) #5–#6) | `act.tasks` (+ the dual-written `events.jsonl` **bytes** for the sha, R1) | `seq` | byte (R1) |
| A3 | `trips.db` `reservation` | `trips.fold.fold` + `store.rebuild` ((c) #27) | `act.trips` | `(fidelity rank, received_at)` within identity | semantic (rowset) |
| A4 | utility posterior `u_bar` and `fold_version` | `utility.posterior` / `fold_version` ((c) #7–#8) via `current_u_bar` | `utility.elicitations`; `calibration.reactions` ⋈ `calibration.decisions` | declared segment order (§3) | byte for `fold_version`; Julia-once for `u_bar` (R3) |
| A5 | per-edge reliability curves | `edge_outcomes_from_log` + `fit_edge_curves` ((c) #10–#11) | `calibration.outcomes` | `seq`, in-position supersession | byte (canonical JSON of curves) |
| A6 | reaction evidence list | `load_reactions` ((c) #12) | reactions ⋈ decisions | first-appearance / latest value | byte (canonical JSON) |
| A7 | latest Claude verdict per decision | `latest_by_decision` ((c) #13) | `calibration.claude_verdicts` | `seq` | byte |
| A8 | gather warm counts / grow block | `warm_counts` / `grow_block` ((c) #19) | `calibration.gather_outcomes` | none | byte |
| A9 | narrative cell / coverage posteriors' inputs | `_cell_observations` ((c) #14) | `calibration.outcomes` | `seq` | byte (the observation lists; the Beta conditioning is exchangeable) |
| A10 | cached answers (the decision-referenced §18.9 artefacts) | `derivations.lookup` ((c) #26) | `calibration.decisions` (`decision_id`) → `pkm.artifact` (`output`) | none | identity: key set + bytes under each key |
| A11 | pkm index (`artifacts`, `artifact_lineage`) | `rebuild_artifacts` ((c) #28) | `pkm.artifact` | none | semantic (rowset) |
| A12 | demand log | (no fold today; R6) | `pkm.demand` | `seq` | byte per line (multiset) |
| A13 | labels verdict | `answer_labels.verdict` | `eval.labels` | `seq`, last wins | byte (verdict table over the label set) |
| A14 | corrections | (no fold; write-only) | `calibration.corrections` | `seq` | byte per line |

Not adapted in tranche 1 (recorded): the gate outputs (per-run projections, reproducible from
`run_meta` + A4/A5), the membrane report (its source log is excluded, §1), the digest and web
board (they read A1), `trips.db` `source`/`trip` (side-stores, §1).

## 8. Migration plan with checkpoints

Every checkpoint is a commit that is green on the whole suite, bisectable, and does one
conceptual thing. **Dual-write is the end-state of this tranche** — no reader is switched to
the stream, no old store is retired.

- **C0 — freeze and count.** Record, out of tree, the source list with per-source raw line
  count, parsed-record count and unparseable count (the two-route count's second route), plus
  `sha256` of each legacy file at T0. **Flag duplicate-key JSON lines separately** (reviewer
  Q8): `json.loads` silently keeps the last value, and canonical re-serialisation would launder
  the loss into a clean-looking `record` — such lines are counted, quarantined by ordinal in the
  manifest, and dispositioned at cutover. No code.
- **C1 — the schema and the writer.** A new package `src/life_agent/ledger/` (not a top-level
  directory; JSONL is an existing format): `schema.py` (`UnifiedEvent`, the closed `source_id`
  and `kernel_id` vocabularies, canonical serialisation, `event_id`), `store.py` (per-source
  segment append with the §10 guarantees; `read(source_id)` in `seq` order; a manifest with the
  epoch). Tests: construction fails loudly outside the vocabularies; idempotent double-append of
  the same `(source_id, seq, record)` is a no-op by `event_id`.
- **C2 — the migration writer, one source at a time.** `migrate.py` with one pure
  `records_of(source) -> Iterator[(seq, tx_time_raw, record, …)]` per source, in the §2
  canonical order; each source lands as its own commit in this order: `act.tasks`, `act.trips`,
  `calibration.decisions`, `calibration.reactions`, `calibration.claude_verdicts`,
  `calibration.outcomes`, `calibration.gather_outcomes`, `calibration.corrections`,
  `utility.elicitations`, `eval.labels`, `pkm.demand`, `pkm.artifact` (last: largest, and its
  canonical order needs the `meta.json` walk `rebuild._iter_meta_files`). Re-running a
  migration is a no-op (dedup on `event_id`); the writer reports its count per source.
- **C3 — the fold adapters** (§7 A1–A14), each a thin function over `store.read` and the
  existing fold, landed with its §9 comparator.
- **C4 — golden harness green** (Phase 2 built it against the legacy stores; here it runs
  against the stream) — every §9 criterion green, the seeded red run re-demonstrated against
  the *stream* copy.
- **C5 — dual-write hooks.** One mirror call at each typed writer after its legacy append:
  `outcomes.append`, `decisions.append`, `reactions.append`, `claude_verdicts.append`,
  `gather_outcomes.append_outcome`, `tasks/events.append`, `trips/events.append`,
  `answer_labels.append_label`, `scripts/verdict.py`'s corrections append; and the **sweeps** for
  `utility.elicitations`, `pkm.demand`, `pkm.artifact` (`ledger sync` — invoked where
  `derivations.reconcile` already runs on the ask path, and by the harness). pkm code is not
  touched: the sweep reads `meta.json`/`lineage.json` and the demand files read-only, applying
  the meta.json-last commit marker (r00 a.2 #4: pkm's own writer is not atomic).
- **C6 — two-route count and r03.** Stream count per source (writer's tally and `wc -l` per
  segment) versus C0's parsed-record counts (+ live appends since T0), reconciled in the report.

Rollback at any checkpoint is `git revert` of that commit; the legacy stores are never
modified, so nothing downstream moves.

## 9. Golden replay criteria (pre-stated)

The harness (Phase 2) snapshots each artefact **from the legacy stores** at T0 with the
existing folds, then replays the same artefact through the §7 adapter, and compares by the
criterion below. Commands are the harness's CLI, `uv run python -m life_agent.ledger.golden
<verb> <artefact>` (`snapshot`, `replay`, `compare`; `--seed-defect <name>` for the red run);
each `compare` prints the comparator's inputs and exits non-zero on mismatch. Snapshots hold
personal data and live under `$LIFE_AGENT_KB/ledger/golden/<T0>/` (an owner-signature item in
r01: the tranche brief's KB refusal must be read as permitting the stream and its snapshots to
live in the KB — there is nowhere else they may live).

| Artefact | Criterion | Comparator (exact) | Command | Ruling |
|---|---|---|---|---|
| A1 `gtd.db` | **semantic** | multiset of rows of `tasks` projected to `(identity, user_id, text, list, due_date, is_today, origin, created_at, completed_at)` — i.e. **ignoring `id`** (AUTOINCREMENT, insert-order). `created_at`/`completed_at` are *fold-determined* (`store.apply` writes `event.tx_time`, r00 §(c) note) so they stay in the comparator; the schema's wall-clock `DEFAULT (datetime('now'))` is a latent hazard named, not a column excluded (reviewer R2a would exclude any wall-clock-defaulted column; the adapter carries `tx_time`, so nothing is excluded — recorded for the ruling) | `golden compare gtd` | R2 |
| A2 `state.md` | **byte-identical**, stamp included | `cmp` of the rendered document; the adapter hashes the dual-written `tasks/events.jsonl` bytes for the sha (R1) — the sha component is **legacy-pinned by R1** on both routes (`Paths.state_sha_source`, the legacy ledger's bytes; never derived from the stream — reviewer Q12 on r03a); byte-vs-semantic at cutover is *not decided here* (cutover tranche) | `golden compare state-md` | R1 |
| A3 trips `reservation` | **semantic** | multiset of full rows (no autoincrement; `identity` PK) | `golden compare trips` | reviewer R10 |
| A4a `fold_version` | **byte** | hex string equality — the always-on gate | `golden compare utility-fold-version` | R3 |
| A4b `u_bar` | **Julia-in-the-loop once** | exact equality of the `u_bar` dict (and `read_params` per latent) between snapshot and replay, both computed through the credence skin pinned at `brain._SKIN_PINNED` (image digest) and `PROTOCOL_MAJOR`, both recorded in the transcript; thereafter A4a only. **This run is also the first parity datum for the later credence→proplang seam swap** (R3) | `golden compare utility-posterior --julia` | R3 |
| A5 curves | **byte** | canonical JSON of `fit_edge_curves(...)` output (`{edge: ReliabilityCurve}` as dict) | `golden compare curves` | — |
| A6 reactions evidence | **byte** | canonical JSON of the `Reaction`/`MarginReaction` list, in order | `golden compare reactions` | — |
| A7 Claude latest | **byte** | canonical JSON of `latest_by_decision` | `golden compare claude-verdicts` | — |
| A8 gather | **byte** | canonical JSON of `grow_block` | `golden compare gather` | — |
| A9 cells | **byte** | canonical JSON of `_cell_observations` and the coverage row list | `golden compare cells` | — |
| A10 cached answers | **identity + bytes** | the set of `decision_id`s that are §18.9 keys equals the set of `pkm.artifact` outputs referenced; for each, `content` bytes and `meta.json` equal on disk (read replay; never re-executed, §5) | `golden compare answers` | R5 |
| A11 pkm index | **semantic** | rowset of `artifacts` and of `artifact_lineage` from the stream's occurrences equals `rebuild_artifacts`'s rowset over the same cache (columns as SPEC §5.1; `produced_at` preserved). **Merge-verdict amendment (reviewer ruling on r03, 2026-08-18 — a reviewed restatement, never a silent weakening):** where the legacy cache has *lost* identities the stream retains (§4 dangling identities), the verdict criterion is *stream ⊇ legacy with the difference exactly the enumerated swept set, compared **by key list**, not by count* (r03: 2,047 keys, symmetric difference 0); the RED transcript remains the finding of record | `golden compare pkm-index` · `migrate counts` (`legacy_lost_keys`) | R5 |
| A12 demand | **byte** | multiset of canonical lines per UTC-day file equals the stream's `pkm.demand` records | `golden compare demand` | R6 |
| A13 labels | **byte** | canonical JSON of `verdict(labels, q, v)` over every `(question_id, value)` present | `golden compare labels` | — |
| A14 corrections | **byte** | multiset of canonical lines | `golden compare corrections` | — |
| counts | two-route | per source: writer tally == `wc -l` of segment == C0 parsed count + live appends | `golden compare counts` | tranche brief |

**The seeded-defect obligation.** A gate with no demonstrated kill is a non-functional alarm.
Phase 2 must show, with transcript, that each of the following **kill categories** turns at
least one criterion red — and name which:

1. **a reordered per-source event** — swap two `calibration.reactions` events on the same
   `decision_id` (must kill A6 and A4a; A4b if run) and swap two `act.tasks` events with the
   same identity where one is `amended` (must kill A1; A2 by construction);
2. **a dropped event** — remove one `act.tasks` `disposed` (must kill A1 and A2) and one
   `calibration.outcomes` `eval_edge` row (must kill A5);
3. **a substituted draw** — alter one byte of a decision-referenced §18.9 artefact's content
   under the same key (must kill A10) and alter one `posterior_summary` value on a decision
   (must kill A4a; A6 if the row is folded);
4. **a cross-source retarget** (reviewer Q9) — repoint one folded reaction's `decision_id` at
   a *different existing* decision (must kill A6 and A4a);
5. **an unrouted Claude verdict** (reviewer V5, 2026-08-18) — append a `claude_verdicts` row
   whose `decision_id` matches no decision (must kill **A7, and exactly A7**: `latest_by_decision`
   is a routing-blind map keyed on `decision_id`, so the row lands; every other artefact must
   stay green — the unrouted-*reaction* invariance fixture below stays green beside it, and the
   pair pins the routing-gated join (A6) vs routing-blind map (A7) asymmetry).

**Verdict-line semantics (reviewer V4, 2026-08-18).** "Must kill" is a floor. Every seeded
run's verdict line reports `CLAIM MET` / `CLAIM MISSED` **and** an `EXACT` / `SUPERSET` flag:
`EXACT` when the killed set equals the claimed set, `SUPERSET` when it is a strict superset. A
`SUPERSET` obliges a per-kill explanation of every collateral in the transcript; unexplained
collateral is a finding, never a pass.

**A11 same-function contract (reviewer V8, 2026-08-18).** The §7 adapter for A11 computes its
rows by calling the same pure functions the harness and `rebuild_artifacts` use —
`_iter_meta_files` semantics, `_check_meta_consistency`, `_meta_to_row`, `_read_lineage` —
applied to the stream's `record.meta` / `record.lineage` (materialised as a cache-shaped tree),
never a re-implementation that matches their output format; `produced_at`'s rendering is
therefore the same code path on both routes.

Beside the kill list, one **pinned-invariance fixture** (reviewer Q9's classification): an
*unrouted* reaction — a `decision_id` that matches no decision — is seeded, the run stays
green, and every artefact's output is asserted identical to the unseeded run; the join must be
inert where it must be inert and alarmed where it must alarm. Phase 2's **crash fixtures**
exercise the §10 torn-tail protocol: a segment with a torn last line, then an append, must
yield a dense `seq`, a manifest quarantine entry, and identical fold outputs.

## 10. Durability contract

The census found three regimes: fsync-per-line through `jsonl_log` (six writers), bare
`open("a")` with no fsync (eight-plus writers, including both act ledgers), and whole-file
rewrites for snapshots (r00 a.0, a.4). The stream has **one** contract:

- **Layout.** One segment file per `source_id` under `$LIFE_AGENT_KB/ledger/<source_id>.jsonl`
  plus `MANIFEST.json` (`format_version`, epoch, declared source order, per-source unparseable
  count at migration). The logical stream is the union in `(source_id, seq)` order (§3).
- **Single writer per segment.** Exactly one live writer per source (§8 C5); the sweeps are
  the writer for the swept sources and run under a per-source lock file. Where two processes
  can today append to one legacy log (the bridge and `scripts/ask.py`'s fallback both append
  reactions, r00 a.1 #3), the mirror is taken by whichever process performed the legacy append,
  under the same lock — the lock, not `O_APPEND` atomicity, is the guarantee (decision rows can
  exceed `PIPE_BUF`).
- **Append.** `open("a")` + write one whole line + `flush` + `os.fsync` — `jsonl_log.append_line`
  generalised; a crash leaves at most one torn last line. **Durability split (reviewer Q11 on
  r03a):** the promise is **per-line for live appends** — the mirror call at a live writer
  appends one line and fsyncs before it returns — and **per-batch for the migration writer and
  the sweeps** (`append_many`: one segment lock, one tail scan, one fsync at the end of the
  batch — per-batch atomicity: a crash mid-batch loses at most that batch's unfsynced tail,
  which the next sweep re-appends idempotently by `event_id`). The live-path promise is
  therefore unchanged by batching; the two shapes share one code path and one prefix check.
- **Manifest lock (reviewer Q11 on r03a).** Every manifest read-modify-write (epoch, per-source
  counts and tallies, quarantine entries) runs under **one manifest-wide lock**
  (`.MANIFEST.lock`), distinct from the per-segment locks — found in Phase 3 before any live
  writer existed (r03a): per-segment locks alone would have raced across sources exactly when
  the nine live writers arrived.
- **Torn tail (the reviewer's required clarification, 2026-08-18).** **A torn line was never an
  event.** On open-for-append the writer checks the tail; if the last physical line is
  unterminated or unparseable, it (i) records the torn bytes **in the manifest** (segment,
  byte offset, length, the bytes hex-encoded, detected-at) — quarantined, never erased; (ii)
  terminates the physical line with a newline so no later append concatenates onto it; the
  segment is **never truncated**. `seq` is the ordinal among *parseable* lines, so the
  parseable-line count is the sweep's resume point, the re-appended canonical line **reuses
  the torn ordinal** (its `event_id` is what the torn line's would have been — dedup stays
  well-defined), and density holds. Readers skip exactly the manifest-quarantined byte ranges
  and read every other line **loudly** (an unlisted unparseable line raises, naming segment and
  ordinal — the calibration logs' policy, not the act ledgers' silent skip). Corrections to
  content are compensating entries; nothing is rewritten.
- **What is promised on crash.** Every event whose append returned has been fsynced; the
  legacy append precedes the mirror, so a crash between them loses only the mirror, and the
  sweep/idempotent re-append (dedup on `event_id`) restores it — the legacy store is the
  recovery source during dual-write.
- **Snapshots and derived files** (golden snapshots, manifest rewrites) use temp-file +
  `os.replace` (the §18.9 seam's discipline, r00 a.1 #13).
- **Order-of-magnitude target.** OpenHands reports 0.20 ms median / 0.31 ms P95 per-event
  persist latency (Table 3, arXiv:2511.03690v2, measured on 433 SWE-Bench Verified
  conversations through the production LocalFileStore path) — **verified 2026-08-18** —
  taken as the order-of-magnitude target for the mirror on the ask path. **Measured (Phase 3,
  C5 preparation; r03a addendum):** on the stream's own volume one appended-line fsync costs
  ~0.7 ms median, and the append-shaped mirror costs **~30 ms median / ~32 ms P95 per call in
  step** on a decisions-sized segment (of which the fsynced temp-file + `os.replace` manifest
  write ~12 ms, one whole-segment scan — the density/torn-tail check — ~3–5 ms, the segment
  fsync ~1 ms); the fallback full sweep ~0.3 s. The target names the persist step alone and is
  **not met** — two orders of magnitude — by a per-line fsync plus a per-line manifest
  rewrite here; that is the stated price of the §10 promise, not an assumption. The levers if
  it must fall (an append-only mirror log as the tally's home instead of a manifest rewrite;
  the delta by tail-count instead of a recorded offset) are queued in r03, not built. SSGM
  (arXiv:2603.11768v2) names
  the latency–safety trade-off as a fundamental trade-off of governed memory (§1 contribution
  4; the in-path cost arises from its Write Validation and Read Filtering gates, Principles
  1–2): the writer verifies vocabulary and shape only; every cross-record check (joins,
  supersession, counts) is a fold or the harness, never on the append path.

## 11. Discipline and change surface

- **No pkm code, cache semantics, SPEC or determinism-contract change** (tranche refusal 4).
  pkm occurrences are read from `meta.json`/`lineage.json` and the demand files, read-only.
- **No brain-seam, spine, or utility-model change** (refusals 2–3). A4b uses the seam as is.
- **New code lands only under `src/life_agent/ledger/`** (+ tests, + `bin/` entry for the
  harness if wanted); the dual-write hooks are one call each at the writers named in §8 C5.
- **New format? No** — JSONL with a typed envelope, canonical serialisation, `format_version`.
  New directory? A subpackage and a KB subdirectory, not a top-level tree directory. New
  dependency? None (stdlib `hashlib`/`json`/`os`; DuckDB and SQLite already present).
- **Append-only everywhere.** Legacy stores are never rewritten; corrections are compensating
  events; the void manifest stays the record of the one deletion path.
- **PII.** The stream and snapshots live under `$LIFE_AGENT_KB`; the tree holds schema and
  code only; fixtures synthetic by construction (`# PII-OK: synthetic …`).
- **Locator policy (reviewer Q13 on r03a, standing).** Reports, transcripts and harness output
  name locators (source, ordinal, path, field), never record values; **digests, hashes and keys
  pass the locator policy; record field values do not** — a cache key is a content digest, not
  personal data.
- **TDD above pkm, answer-grounded**: every adapter lands with its comparator test; the seeded
  red runs are tests, not scripts.
- **Out of scope, explicitly:** cutover of any reader; retirement of any legacy store;
  `LIFE_AGENT_KB` layout changes beyond `ledger/`; membrane shadow, fair-fight, judge cache,
  telemetry as flavours (§1).

## 12. Open design questions

Each is a genuine question, with the evidence that decides it.

1. **Segments or one file? — RESOLVED (reviewer, 2026-08-18): segments.** "One append-only
   event stream" names the *logical* object — one schema, one total order, one manifest — and
   the manifest is what makes it one; a single physical file would need a cross-process,
   cross-host `seq` allocator and a global lock to serve a slogan. Evidence: the census's
   multi-process writers and >`PIPE_BUF` decision lines; §3's interleave already presupposed it.
2. **Multi-host writers.** Jarvis runs on a second host and writes the tasks ledger; the KB is
   a mounted volume. Is the segment lock sufficient across hosts, or must remote writers post
   through the bridge? *Decided by:* an inventory of which processes on which hosts append to
   which legacy store today (a Phase-2 preflight), and whether the mount honours `flock`.
3. **`tx_time` derivation for naive-local stamps.** `act.tasks`/`act.trips` stamp naive local
   time; the writing host's zone is not recorded. Leave `tx_time = None` (as designed) or
   annotate with the migrating host's zone as a *labelled guess*? *Decided by:* whether any
   fold or reader needs a UTC view of act events before cutover (none does today).
4. **`kernel_id` digest vs pkm's hashing rule — RESOLVED (reviewer, 2026-08-18): not engaged**,
   under the two conditions now in §4 (never computed inside pkm; `instrument:` namespace).
5. **`record` verbatim doubles storage of every legacy line during dual-write.** Acceptable
   (the calibration logs are small; `pkm.artifact` carries `meta.json`, not content), or should
   `record` be a pointer `(legacy path, ordinal)` for the largest sources? *Decided by:* the
   C0 counts and sizes.
6. **`created_at` in the GTD comparator.** `store.apply` sets it from `tx_time`, so A1 keeps
   it; reviewer R2a would exclude any wall-clock-defaulted column. Keep (as designed) or
   exclude for robustness against a future `apply` that omits it? *Decided by:* the reviewer's
   ruling on R2a's letter versus its intent.
7. **Trips side tables.** `source`/`trip` are `INSERT OR REPLACE` stores no fold reproduces.
   Do they become `act.trips` amendments (then a schema addition to trips events) or stay
   rebuildable ingest metadata? *Decided by:* whether any surface reads them for anything but
   display (`reach/trips` reads only `reservation` today).
8. **The epoch and pre-epoch losses.** Fixed-path gate snapshots (runs 3/4) are already lost;
   the stream starts at T0. Is any legacy record *outside* the twelve sources worth capturing
   before it grows further (the transforms telemetry log is the candidate, R8)? *Decided by:*
   the owner's call at C0 with the sizes in hand.
9. **Membrane shadow log as a flavour.** It is ledger-shaped (append-only, its report a fold),
   shadow-only, float-epoch stamped. Later tranche or never? *Decided by:* whether the
   membrane graduates from shadow to decision path (M3 flag today).
10. **Judge verdict cache.** A content-addressed record outside pkm's cache; should it become
    a §18.9 stage (then it is a `pkm.artifact` identity, not a flavour)? *Decided by:* whether
    its `judge_key` inputs are expressible as a `StageKey` without changing SPEC §18.9.
11. **pkm's own occurrence flavours.** `source_paths` (append-only, no reader), approvals
    (UUID, mutable status), `schema_meta` (a hash-verified ledger already): which, if any,
    become sources in a later tranche? *Decided by:* the first consumer that needs a
    time-ordered view of ingestion or approval — none exists today.
12. **`FAILURES.md`.** Out of tree, append-only, human-authored — the evidence stream of
    PRINCIPLES §9. Whether it eventually becomes an event flavour (author `owner`, one event
    per entry) is noted, not decided (R8). *Decided by:* whether the failure log gains a
    reader beyond the owner (a fold that ranks or counts misses).
13. **Reader-policy unification — RESOLVED (reviewer, 2026-08-18): loud is the intended
    semantics.** Silent skip fabricates a truth the fold cannot compute, breaking
    `truth = fold(events)` at the root. In this tranche the consequence is interpretive only:
    C0's unparseable and duplicate-key counts are recorded in the manifest, a nonzero count on
    the act ledgers does not block, and each such line is dispositioned at cutover
    (compensating entry or manifest-recorded exclusion) — owner-visible then, not now.

## Appendix A. PRINCIPLES amendment proposals (verbatim replacement text; owner signs or rejects)

Two jobs only, per the tranche brief. Neither is applied here.

### A.1 — PRINCIPLES §7: the derive/act boundary as a predicate

Replace §7 in full with:

> **§7. Ledger as truth; the derive/act boundary as a predicate.** Where state is legitimately
> mutable, truth is `fold(append-only events)`: every read-model is a rebuildable projection,
> and a cleared item never resurrects. There is **one** append-only event stream; "derive"
> and "act" are not two substrates but a **predicate on events**. An event is *derived* when
> it is recomputable from content-addressed inputs by a declared kernel (`author = agent`,
> inputs content-addressed, kernel identity declared — recomputable in the *semantic* sense
> of pkm's determinism contract, SPEC §7.1: the same event would occur, not necessarily the
> same bytes). An event is an *act* when a human authored or mutated it (`author = owner`) or
> the world attested it (`author = world`). The boundary test is unchanged in force: **a fact
> derivable from sources is a derived event — a pkm transform occurrence or a read-time
> projection — never a new ledger.** Only human-authored mutable state (a task completed, a
> note written) and world attestations warrant act events. Folds replay recorded draws and
> never re-execute a kernel (a re-execution is a new event). This principle dissolved the
> bespoke CRM faculty — see [`docs/crm-architecture-decisions.md`](./docs/crm-architecture-decisions.md)
> and [`docs/act-layer-events.md`](./docs/act-layer-events.md); its event form is
> [`docs/unified-ledger-design.md`](./docs/unified-ledger-design.md).

And amend the diagnostic **Derive or act?** to end: "…it is act-layer events (§7) — on the
same stream, distinguished by author and kernel, never by store."

### A.2 — the engine-design §12 vs PRINCIPLES §14 "governor" contradiction: retire the word

**Evidence** (r00 (e)): `docs/derivation-engine-design.md:400-402` (adopted 2026-06-11) says
"The **VOI governor** is explicitly deferred beyond both …", and its `:20-21`, `:27`, `:29-31`,
`:44-45`, `:325`, `:333` treat the governor as a distinct future layer; `PRINCIPLES.md:122-123`
and `:148` (adopted 2026-06-28) say "there is no separate 'governor' to build later / afterwards";
PRINCIPLES `:127-128` re-grounds `bayesian-foundations.md` §12 but never names engine-design
§12. The code sides with PRINCIPLES (`core/executor.py:4`); the word survives in `src/` only as
vestigial prose at `bridge/server.py:770`, `core/lookup.py:1106`, `core/utility.py:261`
(`membrane/shadow.py:12,66` name the sibling *credence-governor* repo, a different object).
`docs/system-design.md:44`, `:62`, `:71` (the L3 row) and `:145` also carry the word.

**Proposed resolution: retire the word.** There is no governor — deferred, scoped, or
otherwise; the endogenous scheduling of transformations *is* the executor's own argmax
(PRINCIPLES §1/§16).

(i) In `PRINCIPLES.md` §14, replace the executor-unification bullet's final sentence
("This re-grounds the staged plan … not a deferred stage.") with:

> This re-grounds the staged plan ([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)
> §12) — its "stage 6 governor" is the spine itself, not a deferred stage — and supersedes
> [`docs/derivation-engine-design.md`](./docs/derivation-engine-design.md) §12's "the VOI
> governor is explicitly deferred": **the word "governor" is retired.** Where older documents
> say "the (VOI) governor", read "the executor's transformation argmax"; new text does not use
> the word. The demand log's designation as its future calibration corpus
> ([`docs/system-design.md`](./docs/system-design.md) §3) stands, re-pointed at the executor.

(ii) In `docs/derivation-engine-design.md` §12 (`:400-402`), replace the paragraph with:

> *(Superseded 2026-06-28 by PRINCIPLES §14, recorded here on the owner's signature of the
> unified-ledger design.)* There is no separate VOI governor: the endogenous ranking of
> transformations is the executor's own argmax-EU (PRINCIPLES §1/§16), built now and
> conservative-first. The demand logs and the confidence layer remain what that argmax
> calibrates against.

(iii) In `docs/system-design.md`, rename the L3 row (`:71`) to
`L3  executor transformation argmax   derive / ask / act ranked in one queue   [PRINCIPLES §16]`
and re-word `:44`, `:62`, `:145` from "the VOI governor" to "the executor's transformation
argmax". (iv) The three vestigial code comments are a follow-up edit outside this tranche
(no code changes here), listed so the retirement is complete when it lands.

Nothing beyond these two jobs is proposed here; anything more would be a DEVIATIONS entry.
