# Personal Life-Management Agent — Roadmap

*This is the plan and status. The principles it executes live in
[`PRINCIPLES.md`](./PRINCIPLES.md); the agent operating manual is [`CLAUDE.md`](./CLAUDE.md).*

## Context

The kernel (PRINCIPLES §1): a knowledge base of trustworthy transformation DAGs (pkm), and a
life agent making rational, utility-maximising decisions over it. The seed task ("find my
Israeli ID across all my data") generalises to "ask/find anything about my life, with
citations" — the first win (§14). The work is integration + a retrieval layer + wiring, not
greenfield (§4): ~90% of the building blocks already exist in the owner's repos.

## Architecture — faculties over language-neutral seams

Faculties compose over MCP / HTTP / CLI seams (PRINCIPLES §5); the table below is the **status
view** — what each faculty is and where it stands.

| Faculty | System / language | Status |
|---|---|---|
| **Memory** — recall + retrieval | **PKM** (`src/pkm`, Python) + **`life_agent`** (this repo, Python) | **Live.** PKM: content-addressed extraction + DuckDB `fts`/`vss` + **composable transforms** (chained, cited perspectives — SPEC §18.7). `life_agent` adds the retrieval/synthesis read path (`scripts/ask.py`, dogfooded via `bin/ask-live`). |
| **Brain** — beliefs under uncertainty; value-of-information → ask/proceed/block | **credence** (`../credence`, Julia; the skin's JSON-RPC-over-stdio seam) | **Adopted, being wired (Phase 1.6 / Ask v0):** [`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md) — answers become claim sets with posteriors; responses are EU decisions through `src/life_agent/core/brain.py` (slice 1). **The typed arm is the deployed default since 2026-08-25 (run 14 PASS — §14).** Per §16 there is no separate VOI governor to build afterwards: the governor is the spine itself. |
| **Hands** — capabilities/actions | **GTD** (`life_agent.tasks`, event-sourced) reached via **`life_agent.reach`** (Telegram transport + persona); email (`msmtp`/JMAP), calendar (CalDAV/Google), chat (matrix) | GTD live, ledger-as-truth (PRINCIPLES §7); **email→GTD shipped (M2)** — the `action_items` transform (haiku, grounded quotes) **auto-files** cited tasks to the inbox; you triage in Telegram. Rest not wired. |
| **Goals / Utility** — what the owner values | *(new, unbuilt)* | **The hardest missing piece.** EU-maximisation presupposes it; owed a design before any autonomous *action* (PRINCIPLES §3). |
| **Spine** — the agent loop + routing | **TBD — open decision** | Deferred to Phase 2 (PRINCIPLES §15). Candidates: pi-mono (TS), a Python loop, or Claude Code as an interim loop. |

The earlier `pkm-memory` MCP server was built then **torn down** (operational — a leaked
process — not an architecture verdict); `src/pkm/mcp_server.py` stays dormant-by-design (§5).
Today the memory read path is dogfooded directly via `bin/ask-live`, and Claude Code itself is
the only (manual) reasoning loop. **Autonomic:** n8n + `systemd` timers (`mbsync`,
`renavon-inbox-ingest`, email→GTD) already run ingestion.

## What the report changes (build-vs-adopt verdicts)

From the commissioned research ([`docs/nix-for-documents-report.md`](./docs/nix-for-documents-report.md))
— a candidate input, not a mandate (PRINCIPLES §9); these are the verdicts the plan *adopted*:
- **Determinism:** PKM already correct (semantic, not bitwise; cache keyed on inputs; SPEC §7.1). No change.
- **Orchestration:** keep PKM bespoke — **do NOT adopt Hamilton now** (over-engineering until multi-step
  DAGs; `artifact_lineage` is already Hamilton-ready; revisit Phase 3).
- **Vectors:** DuckDB `vss`+`fts` (endorsed). Mind: filtered top-k is broken → **over-fetch k·10 then
  filter**; `SET hnsw_enable_experimental_persistence=true`; back up `.duckdb` (borg already runs).
- **Prompts:** DSPy **offline only** (freeze tuned prompts in YAML; never at runtime — would break cache).
- **Chunking/ingestion:** optional LlamaIndex `IngestionPipeline` as a wrapped Phase-1 chunker, or hand-roll.
- **Cache-key hardening (minor, Phase 1):** add `output_schema_hash`, inference-engine/SDK version, and
  split `prompt_template_hash` from filled bindings. Not blocking.
- **OCR:** standalone **Tesseract producer** (`tesseract -l heb+eng`, ~1-file clone of the pandoc
  producer, no new Python dep) — chosen for speed and predictable Hebrew over the heavier Docling path.

## Roadmap (each phase usable on its own)

### Phase 0 — Measure + needle-find · **done and retired**
The compiled-wiki path was built, measured against retrieval in a blind pre-registered
comparison ([`SPEC-comparison.md`](./SPEC-comparison.md) is the frozen record), and **retired**
(PRINCIPLES §14): compiling a summary of everything does not scale and hallucinates. Its
deliverable survives as the dogfood discipline — `$LIFE_AGENT_KB/FAILURES.md` is the spec. The
OCR+grep needle-finder (`scripts/needle.sh`) survives as a standalone tool.

### Phase 1 — PKM retrieval substrate · **substrate complete; corpus live**
1. **(done)** Bump PKM **SPEC → v0.3.0** authorising retrieval/embeddings/extensions/local MCP server (governance-first).
2. **(done)** **`TesseractProducer`** (`src/pkm/producers/tesseract.py`, heb+eng) wired into `routing.py` +
   `extract.py` + `cli.py`; migration `0004` (`chunks`, `embeddings FLOAT[768]`, `source_origin`).
3. ~~(done) Local embeddings via Ollama `nomic-embed-text`~~ **CORRECTED 2026-08-17: never
   implemented.** No embedding call site exists in `src/`; the live catalogue's 529,788
   chunks carry zero non-NULL embeddings; retrieval is BM25/FTS only. The "(done)" was
   aspiration recorded as fact (SPEC v0.3.0 §31's identity rules for embeddings stand,
   unexercised). Greenfield when picked up — and per the 2026-08-17 Ollama deprecation
   (owner directive), on a **local non-Ollama runtime** (same-model weights via
   llama.cpp/ONNX-class serving), keeping the 768-dim schema.
4. **(done)** DuckDB `fts` hybrid query scaffolding (over-fetch k·10); `pkm search` CLI;
   `pkm-memory` MCP (FastMCP) — **later retired**; retrieval now via `bin/ask-live`. The
   `vss` leg was never populated (see 3).
5. **(done) Source adapters — a declarative registry, not ad-hoc scripts.** Sources are declared
   in a **`data-sources.yaml`** registry (real one under `$LIFE_AGENT_KB`, fake schema in
   `config/data-sources.example.yaml`) and enumerated from **plocate**. Two pieces:
   - `scripts/data_source_registry.py` — loader + plocate census + `--report` (classifies every file
     by pkm producer coverage); deferred roots (photos) counted, never ingested.
   - `scripts/ingest_sources.py` — promote step: `filetree` + `maildir` adapters → merge into pkm
     `sources.yaml` (dedupe by path, union tags) → `pkm ingest`.
   Adding **chat** (matrix-archiver SQLite) or **contacts** (Fastmail CardDAV) is *a new `kind`
   adapter + a registry entry*, deferred to dogfood evidence / Phase 2.

> **Status — substrate built, corpus live, dogfooded via `bin/ask-live`:** the live catalogue
> (NVMe; ~13k sources / ~400k chunks incl. the Downloads root) answers cited questions end-to-end.
> Dogfooding surfaced a real retrieval miss (query-expansion, shipped) and a synthesis miss
> (own-corpus attribution, fixed) — exactly the FAILURES-driven signal the loop is for (§9).

### Phase 1.5 — Mature memory · **superseded 2026-06-11**
Was dogfood-gated ("build only what FAILURES.md demands"); superseded by the adopted
framework below (owner directive; PRINCIPLES §9 as amended). Its open levers (OCR the
image-PDFs; `EXPAND_SYSTEM` ranking nudges; new source-`kind` adapters) remain valid
backlog items, promoted by evidence as before.

### Phase 1.6 — The derivation framework · **ACTIVE** (re-scoped 2026-06-12)
The adopted system design ([`docs/system-design.md`](./docs/system-design.md)) executed
continuously, eval-gated (engine design §11); engine D0–D2 and the GTD ledger's knowledge
projection are landed. On 2026-06-12 the owner adopted the **Bayesian foundations**
([`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md)): Ask is re-derived as
inference — answers are claim sets with posteriors, responses are EU decisions,
calibration is measured — and the old D3/D4 are re-scoped as question families of
Bayesian Ask rather than deterministic pipelines. Remaining program, in dependency order
(the doc's §12 roadmap governs; gates per its §8):
1. **(done)** The act ledger becomes knowledge — currency rule (pkm SPEC §15.4),
   `tasks/knowledge.py`, demand-led refresh in the ask path.
2. **(done)** D2 — subject — `doc_subject` closed-enum transform + executor-side
   owner-profile filter (profile never enters pkm).
3. **Ask v0** — slice 0 **(done)**: outcomes log + scoring-rule eval (the evidence
   stream cannot be backfilled); slice 1 **(done)**: the credence seam
   (`src/life_agent/core/brain.py` over the skin's JSON-RPC-over-stdio; live Julia
   smoke green); slice 2: the lookup family + the **utility posterior v0** + the
   decision log (utility is a learned belief about the owner — foundations §4.4/§10 as
   amended 2026-06-12: one utility, the agent has none of its own); slice 3: narrative
   subsumption.
3a. **Gate-instrument work — corpus availability as a modelled variable** *(landed
   2026-08-15; foundations §14, registered blind before run 6)*. The corpus differs
   across machines, and the gate's arms are not symmetric under it: the typed arm runs
   live against the running box's catalogue while the replay arm is a frozen full-corpus
   recording, so every availability gap biased Δ **pro-baseline** by a per-machine amount
   that no artifact recorded. Three changes: every gate report now carries its
   `corpus_digest` and availability count; the paired row records *why* the typed arm
   withheld (`miss` / `dispersed` / `unavailable` — run 5's 70 abstains were
   undifferentiated, which is why the reach lever had no direction); and `unavailable`
   rows are censored from Δ while staying in the published diagnostics. Disclosed blind:
   this censors **zero** rows on the run-6 corpus (104/104 gold chunks resolve), and run
   5's archived rows replay bit-identically — it is a forward guarantee, not a re-pricing.
   Registry roots gained `availability` (`required`/`optional`/`deferred`), so an absent
   root no longer aborts every other root's ingest.
3b. **Corpus identity as an artifact property** *(landed 2026-08-17; foundations §14)*.
   The corpus is not a fixed thing being measured — files move, get deleted, get added —
   so the gate needed to record *which* universe each reading used. Forensics first
   (`scripts/forensics/corpus_timeline.py`): the retrieval universe has been **frozen
   since 2026-06-11T20:24:55**, so runs 3–5 are one controlled series and §14's run-5
   claim that "the corpus digest moved" was wrong — corrected with disclosure, which
   *removes* a confound. Then three landed changes: gold provenance is now
   **content-addressed** (`artifact_cache_key` + `chunk_index` beside the surrogate
   `chunk_id`, which `pkm rebuild-catalogue` silently re-issues), backfilled across all
   104 questions under a guard that aborts on any non-provenance diff; a corpus version
   is a **self-verifying ~1 MB manifest** whose re-hash *is* `corpus_digest`
   (`scripts/corpus/pin_corpus.py`, pinned as `full-2026-06-11`), not a 2.8 GB copy —
   the store is content-addressed and monotone, so version *n+1* is a strict superset;
   and every gate run publishes a `run_meta.json` (git sha, questions/utility sha256s,
   corpus + pin status) plus `run_id`/`corpus_digest`/`corpus_snapshot` on every paired
   row, with `--corpus-pin` **refusing before spending** on a mismatch. Run 5's archived
   rows replay bit-identically, so none of it re-prices anything.
3c. **The MVP fast path — re-sequenced 2026-08-17 (owner directive: "MVP sooner, vision
   intact")**. Nothing in the daily-driver surface depends on the proplang ladder: the
   spine is transport (PRINCIPLES §16) and there is one act-committing seam, so the
   read-only assistant surface (Phase 2's item, pulled forward) ships underneath the
   ladders and *feeds* the evidence they gate on. Landed the same day: **judge grading
   adopted** for the gate arms (`run_eval --judge-grade`, §14 run-6 reg. (2)); the **P(U)
   elicitation sprint** (u_hedged/lambda_int/u_wrong_scoped, disclosed blind); the
   **uncalibrated lane** (`LIFE_AGENT_FALLBACK_LANE=1` — a typed withholding additionally
   renders the monolithic prose over the same hits, labeled; typed-first, presentation
   only, one seam for terminal + Telegram; **removed 2026-08-17 when the §8 gate passed
   and the owner adopted honest-withhold-only** — §14's adoption entry); the **daily
   briefing** as a real timer (`bin/daily-digest`, `packaging/daily-digest.{service,timer}`,
   owner-targeted, invariant-3 truncation naming, drift-gated section table); and the
   **local-Ollama deprecation** (owner directive — instruments, transforms, NLU on the
   Anthropic seam via `core/instrument.py`; §14 registered the instrument change blind
   before run 6; ~7.9k local-keyed cache artifacts deliberately orphaned; base instrument
   spend now metered into Δ). The Telegram `question` intent and one-bit `g`/`b`
   reactions were already built. **MVP exit test:** a week of the owner asking Jarvis
   instead of the incumbent harnesses for life-data questions + morning triage, misses
   logged to FAILURES.md.
3d. **Proplang re-earn, rung 2 — P3b (harness + blind pre-registration landed 2026-08-17;
   measurement running).** The held-out differential gate (A3) is variant-parameterized
   (`p3_gate.py --gate-variants`, suffixed artifacts, ledger-window guards) so the
   coarsened leader-credence-only lattice — the one EU-positive held-out variant — gets
   its own A3 against the credence baseline, the named-but-unrun measurement that blocks
   any re-flip. **Read 2026-08-17 (`docs/membrane-shadow.md` §17.6): FAIL by total
   abstention** — under the owner's current utility (u_wrong −8.83, commit bar 0.899) the
   coarsened lattice commits 0/190 held-out ticks; its §17.5 +0.284 lived in a 0.04-wide
   p1 window that the u_wrong elicitation closed. The coarsening is closed as a re-earn
   route; the path is E1 (a sharper engine posterior), not lattice surgery. First execution
   voided on Ū drift and caught by the freeze; the engine reproduced §17.5 to four decimals.
3e. **Gate run 6 + its attribution (2026-08-17; foundations §14).** Run 6 — judge-graded
   arms, λ_usd spend on both arms, the post-Ollama cloud instruments — read **FAIL at
   P(Δ>0.05) = 0.678, Δ̄ +0.180 [−0.244, +0.661]**, the series' first positive mean, typed
   answer rate 0.47 (47 ✓ / 2 ✗) vs monolithic 0.97, withholdings miss 18 · dispersed 37.
   Three things changed at once, so the same day's **arm-splice counterfactual**
   (`scripts/gate_splice.py`, deterministic on archived artifacts, pinned to reproduce run
   6 first; not a reading) attributed it: run 5's cautious typed arm, judge-graded and
   priced, reads **0.905 / +0.343** — grading and pricing carried the sign; the new
   instrument's live arm gave back Δ̄ −0.163 (corrects +0.192, two confident-wrongs −0.173,
   spend −0.183 — nine cold deliberate probes are $10.87 of it, and 13/13 cold deliberates
   across runs 5–6 converted nothing). The audits landed the same day (q2-053 stale gold
   corrected; q2-105 a cached coin-flip; 10 stale curve rows regraded append-only; the
   nine cold deliberates were MCP failures cached as declines — voided, guarded) and
   **run 7 (`gate-20260817T160244`, the run-6 recipe repaired) read the series' first
   PASS: P(Δ>0.05) = 0.945, Δ̄ +0.429 [+0.040, +0.884]**, typed 50 ✓ / 1 ✗ at $5.56.
   Adoption is the owner's rider. **Run 8 (router v2, same day): FAIL 0.857 / +0.344**
   — the router delivered (miss 18→2, answer rate 0.57, 0 wrongs among the admitted)
   but two wrong-leader commits on multi-value chunks (curve-evolution variance, not
   the router) pulled the reading under. **Run 9 (the competing-values temper, same
   day): PASS 0.938 / +0.390 with ZERO wrong commits** (35 ✓ / 0 ✗, answer rate 0.34,
   $4.10) — the registered off-gate sweep predicted the live assert set perfectly; the
   wrong-commit class is closed at the price of reach. Independent-document
   corroboration (the only rescue path the temper permits) was **built and refused by
   its own frozen audit (2026-08-18, NO-GO: true ceiling ~6 — the reach audit's 40
   was forwarded-copy inflation; §14 has the negative reading)** — the instrument
   (`/probe/confirm`) stays in-tree, dormant. Reach now accrues from live dogfood.
3f. **Runs 10–14 — the wrong-commit arc closed and the typed arm DEPLOYED (2026-08-21 →
   2026-08-25; foundations §14 has every reading, `docs/module-collapse-design.md` §6.9–§6.13
   the registered defect classes).** Run 10 reopened the wrong-commit class (FAIL 0.861, one
   row); the isolation ladder (runs 11–12) convicted §6.9's declared probe order as the
   marginal cause and run 12 read the then-best 0.964; the §6.12 deployment block was
   registered on the replace-branch mechanism (a probe view DISCARDING a grounded channel).
   Diagnosis checkpoints r05–r08 ($0) named the mechanism, repaired window determinism
   (§6.13, SPEC 0.18.2), and capped further diagnosis; r09 built the §5-deduped JOIN with a
   correlation key on the wire; run 13 FAILED (0.895, four wrong commits) and was reverted;
   the tempered arc (r09b–r09d, r09e, r10 — all $0, each STOPPED by its own frozen
   consequence) established the terse-carrier finding (any carrier-side requirement damps the
   terse gold — a closed lever family) and parked the tempered tree. **Run 14
   (`gate-20260825T102725`): PASS on all four frozen conjuncts — P(Δ>0.05)=0.907, Δ̄ +0.421;
   the blocking row commits correct; zero NEW wrong commits; no named class worse. §6.12
   CLOSED; the tree merged (PR #81); master deployed to live (`bin/ask-live` / jarvis on the
   typed arm).** Two standing wrongs ride priced (corroborate-tier; entity-qualifier); the
   hard clause — no lever ships while it makes a named wrong-commit class worse — binds every
   successor. **The completion programme from here (owner-approved 2026-08-25):** stage 0
   riders (baseline re-record closing q2-036; this doc-currency sweep; a production readout
   for the carried risks) → the collapse ladder M2–M7 (`docs/module-collapse-design.md` §8;
   Appendix A signed at M7) → items 4–5 below through §8 gates → the proplang graduation
   (shadow → challenger → priced run; `docs/membrane-shadow.md` §11 exit criteria), with the
   MVP exit test running wall-clock-parallel from the deploy.
4. **The aggregate family** (subsumes D3): recall term + completeness priors,
   missing-mass posterior, dedup-as-inference — the spending question answered as a
   posterior with both coverage readouts.
5. **The thread family** (subsumes D4): `assemble` SPEC amendment, email `_VERSION` bump
   (budget the corpus-wide reclassification), `thread_state` instrument, membership
   recall ("awaiting reply?").


#### The completion programme's DONE conditions — reconstructed 2026-08-27 (K3 · r26 C10)

Two owner rulings were taken against this list before it existed anywhere as a list. It is
reconstructed here from every in-tree site that states, quotes, references or presupposes a
condition; every quotation below was re-verified against the file it cites, and anything
marked RECONSTRUCTED is inference from the citing sites, **not** recovered text.

The programme itself is stated once, as prose, in the paragraph above (`ROADMAP.md`, Phase
1.6 item 3): stage-0 riders → the collapse ladder M2–M7 → items 4–5 below through §8 gates
→ the proplang graduation, with the MVP exit test running wall-clock-parallel from the
deploy. Its members are unnumbered there and it is never called the DONE conditions.

| # | Condition | Source | Status |
|---|---|---|---|
| 1 | The owner has signed Appendix A at M7 | `docs/unification/conferrals/appendix-a-conferral.md:43` (the only statement of its text, and it sits inside a *decline* branch that was never taken); the requirement itself at `docs/module-collapse-design.md:1066` and `ROADMAP.md:221` | **MET** 2026-08-26 — `appendix-a-conferral.md:72-73`, enacted at `docs/unification/reports/r17-collapse-m7.md:131-138` |
| 2 | **UNSOURCED.** RECONSTRUCTED: item 4 below (the aggregate family) is not merely built but gated by a priced §8 run — i.e. `docs/bayesian-foundations.md` §12 stage 2 reads met | Referenced by number twice, stated never: `docs/unification/conferrals/cp-a-aggregate-conferral.md:81-82`, `cp-d-routing-conferral.md:74-76` | **OPEN, and its referent was deleted** — the 2026-08-27 ruling deleted the aggregate family and its design doc (`cp-d-routing-conferral.md:113-125`) **without mentioning the programme, item 2, or what becomes of it** |
| 3 | **UNSOURCED. No in-tree text names a DONE item numbered 3 or higher** — not in reports, conferrals, design docs, root docs, or any commit message in history | — | unknown |
| 4 | **UNSOURCED**, as above | — | unknown |
| 5 | **UNSOURCED**, as above | — | unknown |

**The count itself is unsourced.** "Five" appears exactly once in tree, in
`docs/unification/reports/r26-guard-layer.md:102` — K3's own frozen criterion C10, which
inherited it from the plan that opened K3 rather than from any earlier text. So C10 asked
for five conditions on the authority of C10. That is this milestone's own defect class one
level up (a checker's universe derived from somewhere other than the thing checked), and it
is recorded rather than quietly rounded off.

What the evidence does support:

- **Only items 1 and 2 are ever referenced.** The complete census of item-numbered
  references is six lines, listed above plus `r17-collapse-m7.md:89`.
- **The two attested numbers do not line up with the chain read in order.** In chain order
  item 1 would be the stage-0 riders; it is in fact the Appendix A signature, which closes
  the *second* element. Dropping the riders (closed the day the programme was approved)
  realigns item 1 → the ladder and item 2 → the families, and leaves **four** elements.
- **Restoring five requires counting the proplang graduation**, which the owner ruled is
  *not* a completion condition (`docs/membrane-shadow.md:1273-1274`: "the migration is NOT
  a completion condition of the 2026-08-25 completion programme (Stages 1–2–4 close without
  it)"), directly contradicting `ROADMAP.md:221-222`, which lists it in the chain. Both
  texts carry the same date and neither references the other.
- **RECONSTRUCTED, and the most economical reading:** DONE item *N* is the close of Stage
  *N*. Item 1 ↔ Stage 1 (the ladder, closed by the signature) and item 2 ↔ Stage 2 (the
  families) both hold. That makes "five" the *stage* count 0–4, not an item count, and
  predicts items 3 and 4 exist as Stages 3 and 4. **Stage 3 is named nowhere in tree**;
  "Stages 1–2–4" appears exactly once, at `membrane-shadow.md:1274`, which implies a Stage
  3 that those three close without. This is a hypothesis with two confirmations and one
  gap, not a finding.

**Four further disagreements are unreconciled in tree** and are recorded, not resolved:
what Stage 0 consisted of (`ROADMAP.md:219-220` names three riders; `CLAUDE.md:326-333`
declares it DONE citing two, omitting the doc-currency sweep — which is never reported done
anywhere); item 1's wording (the conferral's quoted string exists nowhere else); which
numbering discharges the family stage (three labels — "DONE item 2", "foundations §12 stage
2", "Phase 1.6 item 4 / Stage 2a" — for one referent, with no reconciling text); and what
opens the proplang migration (three different statements, only one of them enumerated, and
the "completion audit" the others gate it behind is undefined).

**Owner keypress.** Items 3–5 have no in-tree text and only the owner can say what they
were — or whether there were four. The completion audit reads against this list, so it
should not read until this is settled.

### Phase 2 — Goals/utility model + first agent loop (read-only) · future
- Design the **goals/utility representation** (the unbuilt faculty) — how the agent learns and
  stores what the owner values. Owed before any write-action (PRINCIPLES §3).
- Build the **first real agent loop over read-only capabilities** (daily briefing, "what needs
  attention"), reasoning over memory, gated by **credence** (VOI ask/proceed/block — safe because
  nothing is destructive). **The spine is chosen here** (see Open decisions).

### Phase 3 — Action layer + autonomy · future
Write-capabilities (GTD tasks, email drafts, calendar) under credence ask/proceed/block;
omnichannel (Telegram/Matrix, Tailscale-only); scope expansion to photos (PhotoPrism + vision),
then the 661 GB encrypted `more/` (needs keys).

### Open decisions (decide when the phase arrives, not before)
PRINCIPLES §15 is the canonical list, with criteria:
- **The spine** (Phase 2): pi-mono vs a Python agent loop vs Claude Code as an interim loop. One
  candidate composition is sketched in [`docs/candidates/brain-design.md`](./docs/candidates/brain-design.md).
- **The goals/utility representation** (Phase 2).
- **The CRM rebuild** — #1/#2/#5/#6 resolved by the adopted framework (recorded in
  [`docs/crm-architecture-decisions.md`](./docs/crm-architecture-decisions.md)); #3
  (mutable notes) and #4 (alias dedup) remain open.

## Critical files
- **`.` (this repo):** `src/life_agent/core/` (shared infra: LLM calls, secrets, config, source
  rendering), `scripts/ask.py` (retrieval + synthesis, run via `bin/ask-live`), the configurable
  data layer (`scripts/data_source_registry.py`, `scripts/ingest_sources.py`,
  `config/data-sources.example.yaml`), and the frozen blind-comparison harness
  (`scripts/comparison/`). (Knowledge + the *real* `data-sources.yaml` live under `$LIFE_AGENT_KB`.)
- **GTD (act layer):** `src/life_agent/tasks/{events,store,commands,project}.py`.
- **Reach:** `src/life_agent/reach/{telegram,jarvis,digest}.py`.
- **pkm:** `docs/pkm/SPEC.md` + `docs/pkm/SPEC-PRINCIPLES.md` (governance);
  `src/pkm/{routing,extract,cli}.py` (producer wiring ladders); `src/pkm/transform.py` + transforms.
- **credence-pi (candidate brain):** `bdsl/capabilities.bdsl`, `extension/src/index.ts`, `daemon/server.jl`.

## Verification
- **Phase 1:** `uv run pkm search "תעודת זהות"` returns the ID with provenance; idempotent re-ingest
  (double-run no-op); `pytest`/`ruff`/`mypy` green; `bin/ask-live` returns cited answers from the corpus.
  **Data layer:** `python scripts/data_source_registry.py --report` prints the per-root census;
  `python scripts/ingest_sources.py` is idempotent (re-run = no new catalogue rows).
- **Phase 1.5:** a `FAILURES.md`-traced change moves a real dogfood miss (e.g. an image-PDF becomes
  searchable after OCR routing); idempotent re-ingest; no FTS-ranking regressions.
- **Phase 2:** the read-only loop renders a daily briefing; credence asks/auto-proceeds appropriately
  on read-only capabilities; a goals/utility representation exists and is consulted.
