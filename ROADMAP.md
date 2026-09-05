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
| **Brain** — beliefs under uncertainty; value-of-information → ask/proceed/block | **credence** (`../credence`, Julia; the skin's JSON-RPC-over-stdio seam) | **Adopted, being wired (Phase 1.6 / Ask v0):** [`docs/bayesian-foundations.md`](./docs/bayesian-foundations.md) — answers become claim sets with posteriors; responses are EU decisions through `src/life_agent/core/brain.py` (slice 1). **The typed arm is the deployed default since 2026-08-25 (run 14 PASS — §14).** Per §16 there is no separate VOI governor to build afterwards: the governor is the spine itself. **proplang is the RULED successor of credence at this seam** (owner ruling 2026-08-25; [`docs/membrane-shadow.md`](./docs/membrane-shadow.md) §18 — gated-mandatory, FAIL means iterate, never park), being migrated as **Arc C** (item 3h below); its shadow engine mirrors live decide traffic off the decision path again since 2026-09-01. |
| **Hands** — capabilities/actions | **GTD** (`life_agent.tasks`, event-sourced) reached via **`life_agent.reach`** (Telegram transport + persona); email (`msmtp`/JMAP), calendar (CalDAV/Google), chat (matrix) | GTD live, ledger-as-truth (PRINCIPLES §7); **email→GTD shipped (M2)** — the `action_items` transform (haiku, grounded quotes) **auto-files** cited tasks to the inbox; you triage in Telegram. Rest not wired. |
| **Goals / Utility** — what the owner values | **`core/utility.py`** (this repo, Python) | **Partly built.** The *answer*-utility gauge is live: one utility posterior, a learned belief about the owner (foundations §4.4/§10 as amended), elicited P(U) pricing every gate run and the deployed argmax. **Still unbuilt:** any goal/plan representation beyond it — owed before autonomous *action* (PRINCIPLES §3, Phase 2). **Named residue (owner-only):** the gauge fixes `u_abstain = 0`, so it cannot represent the cost of *not* answering — now priced, not just named: [`docs/unification/conferrals/u-abstain-conferral.md`](./docs/unification/conferrals/u-abstain-conferral.md) (2026-09-02) holds the evidence and four costed options, awaiting the owner, and r46 leg A tied the residue to the decision path (it is what sets the engine's commit threshold at `p1 = 0.897015`). |
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
   MVP exit test running wall-clock-parallel from the deploy. **[Corrected 2026-09-01: the
   proplang graduation is struck from this chain — owner ruling `G-2` (2026-08-31) makes it
   NOT a completion condition. The resolved stage map below governs; this sentence is left
   standing as the record it was. `r35` §1 D-4 claimed this correction and enacted only the
   table rows, which is why it is being made here.]**
3g. **The ruled queue — r28 → r39 (2026-08-28 → 08-31), after the collapse ladder closed.**
   Not *post-programme*: the queue straddles the programme's own close, and `r32`/`r33` are
   Conferral 2's rulings on the Stage-4 measurement — programme work, not successors to it.
   The readings themselves are $0; the gate runs they bought are **runs 20–23**, cents each,
   every figure in its own report. (Run 19 belongs to `r21`/CP-D, fired 2026-08-26 and
   stopped before its first conjunct; its artefacts are voided.)
   **`r28`** decomposed what the gate measures:
   Δ = Δ_answers + Δ_spend reads 0.019 + 0.495 on run 18, so **96% of the adoption margin is
   the price of the baseline arm** — quote the split, never the total. **`r29`–`r31`** ran the
   units lever (the answer-shape census, then the INTERVAL claim priced inside the argmax) and
   **closed it FAIL**: the interval is dominated on both sides and never fires; `r30b` stays in
   tree measured-dormant by ruling, nothing deployed. **`r32`/`r33`** priced the commit bar's
   drift (below, under Stage 4) and fixed the exit measurement's five instrument defects.
   **`r34` → `r38`**
   repaired the value-join — M6's one declaration of the value-join tested identity while five
   other call sites used a different key, two declarations of one relation surviving M6 because
   they carried different §-numbers — and **run 23 PASSED on all five frozen criteria, so it is
   merged and DEPLOYED**; `GD-8` binds the reading (the benefit is one row, below §6.13's wobble
   floor: it shipped as a defect repair, never on its row count). En route, **`M-18`** (pin the
   comparison tree, not just the deciding tree) and **`M-19`** (a measurement launcher restores
   the tree it found). **`r39`** closed the B class: **B is C** — the constant that kills
   narrative inclusion is `u_wrong`, so no lever opens. `CLAUDE.md` and the reports under
   `docs/unification/reports/` carry the detail.
3h. **Arc C — the proplang migration · OPEN** (unblocked 2026-08-31 by `G-2`; the ruled successor
   at the decide seam, `docs/membrane-shadow.md` §18: gated-mandatory, FAIL means iterate and
   re-run, never park). The ladder is `GD-10`'s: **P0** (engine pinned) → **P1** (accrual
   restored) → §17.6's **E1** re-earn → §18's bars → §11's exit criteria ("credence fully
   retired"). Read so far — all $0 except `r45`, whose Part B changed the deployed box:
   **`r40`** found the premise stale — no engine binary on this
   box and the shadow dead since 2026-08-10; **`r41`** pinned both engine arms and read P0;
   **`r42`** measured HEAD's door to differ in four ways, not the one named from source;
   **`r43`** found the blocker was **our** declaration, not the engine's; **`r44`** landed the
   repair (59/59 battery cases tracking the engine's own argmax, 8/8 mutations RED); and
   **`r45`** restored P1 — **the shadow is live again since 2026-09-01**, folding real traffic,
   with the 2026-08-10 → 09-01 gap recorded in the stream as a segmentation boundary because
   the engine's model space changed underneath it. Three constraints found en route bind
   what comes next: the engine chooses `gather` across 96–98% of the credence range under
   both the declared and deployed utility (the v1 gather-bar pathology is **not**
   dissolved, and it stands); the fold-depth cost is real and biting (~20 s wall /
   **6.8 s engine CPU** per mirrored decide at fold depth 250 — `GD-17`, which falsifies
   `GD-15`'s first ground); and the one engine-side ask is filed upstream as demand,
   `proplang#24` (`GD-14`). **`r46` has since read its two readable legs, both $0
   (2026-09-02) — leg A declaring the §18 bar's surface, leg B cutting the fold cost 3.3×
   (merged, not yet live):**

   **Leg A** ([`r46-readable-surface.md`](./docs/unification/reports/r46-readable-surface.md))
   discharged the §18 surface precondition: the surface a §18 bar reads is **declared** to
   be the mapped one — `coarse.map_action`, which had **zero `src/` call sites since M5** —
   and its distribution is published (`GD-18`); the raw affordance is disqualified on
   measurement (6 654 of 6 654 action-bearing rows `gather`, at a stated read time — the
   ledger is live and the count moves). The mapped surface varies and carries engine
   signal (echo 0.636 over 605 recorded exchanges; 118 disagreeing rows, every one
   engine-contributed) — **but its commit branch has never once been reached**: the
   threshold is `p1 = 0.897015` (`|u_wrong| / (u_correct + |u_wrong|)`, sitting there
   **because `u_abstain = 0`** — the owner-only residue named in the table above), the
   ledger max **0.8706**, gap 0.0264 (0.0349 in the new era). §17.6 found the near-miss
   first, on 193 ticks; leg A extends it to the whole ledger, both engine arms, and the
   mapped surface. The ceiling is **empirical, not structural**: a bar read today prices
   gather-versus-withhold and must say plainly that its commit column is empty on every
   row ever recorded. The observation-only tap that restores the surface is live and
   writing since the bridge's 2026-09-02 restart — a restart pair whose price `GD-20`
   records: the first one **permanently killed the shadow** (the skin's 112 s cold Julia
   precompile racing a 120 s ready-sentinel timeout, ready arriving 3 s after the last
   respawn gave up, `ActiveState=active` green throughout), caught and repaired by a
   second, warm restart. Registered: `M-26` (a column's meaning can depend on the row's
   kind) from the leg itself, and `M-27` (restarting a service is a measurement, not a
   formality) from that incident. The same sitting also settled `GD-19`, apart from r46:
   the measurement-tree tags stay unpushed — the PII guard is right — with the SHAs
   pinned in `M-16` instead.

   **Leg B** ([`r46b-grid-precision.md`](./docs/unification/reports/r46b-grid-precision.md))
   discharged `GD-15`'s inherited conditional and closed `M-24` — **not** by the
   sixteenths rule, which this world refutes (sixteenths merge two rung pairs: `n` 8 → 6,
   `models` 960 → 516 — a different hypothesis space, not a placement fix), but by the
   finest lattice the frozen bar admits: `world._GRID_LATTICE_BITS = 20`, snapped after
   rung selection and refused rather than allowed to merge. Depth 250 — the checkpoint
   `GD-17` was interrupted before — was reached: **748 s → 226 s** within-run (the
   deployed baseline is unstable across runs, 1 102 / 744 / 748 s; the 1 102 s run is the
   one reproducing `GD-17`'s ~19.5 min live boot). **Nothing clears at depth 25**, so
   `GD-15`'s "depth is small" and `GD-17`'s falsification of it are both true at their own
   depths. `p1` gap ~3 × 10⁻⁷ (~9 500× under `W6`'s, with no growth at the three tick
   counts `W6` used — though three points cannot prove absence of a trend), and **zero
   differing actions over 428 distinct summaries**. One correction disclosed: the
   pre-registration's own mechanism claim was wrong — every IEEE double is already dyadic;
   cost tracks denominator **bit-length**, the 2⁻⁵³ control landing back on the deployed
   cost. The change is **merged, not on the wire** (the running shadow keeps the old grid
   until the next restart taken for its own reasons — none is spent for an 8.7-minute
   saving), and it does **not** reduce `GD-20`'s hazard, which sits before any fold.
   Registered: `M-28` (a measurement pins its tree for the whole run — one equality run
   was void for comparing the treatment against itself, and its output looked perfect).

   **Leg C IS READ (2026-09-03, `r46c-act-conditioning.md`, `GD-21`, PR #165, $0):**
   act-conditioning is real (K3) and choosable (K4) — r45's YES, via a mirrored NON-writable
   `act-taken` guard with `act` kept in the menu — but **INERT for the commit ceiling** (+7×10⁻⁵,
   0/250 rows lifted), and the bar had drifted BELOW the ceiling anyway (live p† **0.8369**,
   < pooled ceiling **0.862188**, 180/250 clear). Branch 1 letter met / ground refuted (the
   `GD-16` shape): NOT opened as a lever; **leg A's sharpened target CORRECTED** — the p1 ceiling
   is not the blocker under the deployed bar (whether it flips any exhausted-gather row is handed
   to the §18 checkpoint). `M-29` registered. **Leg D IS READ (2026-09-03,
   `r46d-categorical-twin.md`, `GD-22`, PR #166, $0):** `GD-13` RESOLVED — the two worlds share
   **ONE grid rule**; the θ codebook is **K-INDEPENDENT** (same 8-rung grid across k, models
   688/1032/1720 = 344·k via `obs_arity`), so `GD-13`'s "per-K" conflated the menu grid (per-K,
   already correct) with θ. r45's three source claims measured true, one broader: the twin's tick
   fails arm B on **TWO** counts (menu-less `act` + the dormant indicators `cat_features` omits).
   A categorical enablement (E1/§17.6) needs four items — SPECIFIED, NOT built; nothing deployed.
   **All four r46 legs are read.**

   **§17.6's E1 re-earn is OPEN, and its grounding pass is read (2026-09-03, `GD-23`, $0).**
   E1 is not greenfield: stages 0–1 LANDED 2026-07-22 (membrane-shadow §15/§16) and
   `membrane/categorical.py` is in tree, env-gated OFF and byte-inert. What was missing is that
   its governing design — `docs/candidates/e1-categorical-outcome.md`, owner-approved
   2026-07-21 — **was stranded on a paused branch while §15 named it governing**, so the link
   was broken on master. It is salvaged verbatim with a third dated re-ground rather than
   rebased (the branch sat 521 commits behind and its only unique bytes were that file); the
   branch is retired. The re-ground's finding is that the design's "not landed" list is
   materially stale: **six of its eight engine dependencies have closed**, three load-bearing —
   the per-code readout **shipped** (#20 — and verified **live on our own arm B**, one $0
   probe: every categorical reply carries `p0`, `argmax_code`, `p_argmax` and `p_codes[]`, so
   §16's unobservable R-D23 question is answerable and §4.4's observability gap closes),
   the null-mass cap closed at the `OB-19` heir (#21), and the θ ceiling **changed owner rather
   than dissolving** (#19 — θ is REQUIRED hello data now, which is why leg D's item 1 exists;
   our declared grid's top rung reads **0.990634** under the deployed Ū, neither the doc's 0.9
   nor the 0.95 endpoint). `OB-12` discharged with increment B out **on measurement**, while
   naming the one thing that reopens it — a second verdict source, which this repo has **built
   and dormant** (`core/claude_verdicts.py`: 180 verdicts, none since 2026-07-22, so
   re-opening B means restarting and pricing it). **#10** closed against our stated position
   too, ruling a **reserved unallocated tail priced from tick 0** where §5.4(c) had said it was
   not needed — a cost `r47` declares deliberately. Deliberately NOT concluded: whether §16
   finding 3's gather binder still binds — two of its three terms moved while `r45`'s C3
   measured the pathology standing, and the categorical crossing needs the engine under
   today's Ū.

   **`r47` IS READ and BUILT (2026-09-03, `GD-24`, $0, all ten frozen criteria PASS):** the
   deployed categorical episode now speaks the enabled world at HEAD. `GD-22`'s four items land
   in `categorical.py` — codebooks **binding** `world.theta_grid` unchanged, the clock row
   binding the binary world's own objects, every tick naming the writable act, and `cat_features`
   emitting every declared indicator dormant at 0.0. Arm B accepts the episode end to end at
   k ∈ {2,3,5} (`models` 688/1032/1720, reproducing leg D's `344·k`) while the pre-enablement
   episode is refused at the **handshake**; arm A unharmed; the binary world byte-untouched;
   4/4 mutations RED. **Nothing deployed or enabled** — the world stays env-disabled and
   byte-inert, `M-1` not engaged. The ordering was frozen with its reason (`GD-24`): build
   before measuring, because `M-7` forbids pricing a constant through a re-implementation of
   the rule that assembles it and `r30b` showed an in-process-only lever is invisible to the
   measurement that matters. Two corrections recorded: a blind prediction **refuted** (arm B
   refuses at the handshake, so no tick item can bite first), and a test that **asserted an
   invented requirement** — that the clock name must be a namespace member — refuted by the
   deployed binary world, which keeps `think` out of its namespace in the shape `r44` verified
   at arm B.

   **`r48` IS READ (2026-09-04, `GD-25`, $0): the E1 re-earn does NOT clear, and the KILL that
   fired names a cost defect rather than a build defect.** J1 fires — three of 129 summaries
   returned no action, all at k ≥ 12 — and **its stated ground is refuted**: 126 episodes
   handshook, folded and returned a declared action on the deployed enabled world, covering
   **2 009 of 2 012 recorded rows (99.85%)**. It stands as fired anyway (`GD-16`'s letter-met /
   ground-refuted shape), and the re-read it mandates finds the opposite of the guess —
   `r47`'s enablement is sound; its **episode budget** is unbounded. On the leg that completed:
   **`gather` on all 126 replay episodes and all 55 sweep steps, no flip anywhere.** Forty
   observations reach `p_argmax` **0.98348** against a necessary bar of **0.99063** (gap
   **0.00716**, closed 14.3× from §16's era and still open), **K-independent to 16 digits**;
   eleven summaries clear the vs-abstain bar 0.836894 — nine of them the degenerate k=1 — and
   every one still chose `gather`. §17.6's rule binds unchanged: a sharper `p1` or #15 / E3,
   **never a softer bar**, and r48 proposes neither. Three corrections published:
   **`M-30`** — §16 finding 3's *by-construction* clause is **VOID**, because `r46` leg B's
   2⁻²⁰ snap rounded the decisive rung **up** and the θ ceiling now sits 1.2×10⁻⁸ **above** the
   bar (leg B's own verification was honest and complete on the rows it checked; the boundary it
   moved is one no episode visits) — finding 3's primary attribution, the overvalued information
   row, stands and is now **empirical**; **blind prediction 4 REFUTED** — arm B runs **2.3× to
   145× slower** than arm A on a model space 4.65× *smaller*, median latency scaling **~k⁴**
   where `models` is k¹ (mechanism named, not measured); and **§16 finding 5 answered** — #20's
   readout makes `p0` observable and R-D23's `1/(K−1)` cap shows **zero violations** over 113
   rows, tightening monotonically (0.26 of the cap at k=2 → 0.82 at k=11) without ever binding.
   §16 finding 4's owed K-cap now has a number: **k ≤ 3**, the largest cap under which every
   observed episode finishes inside production's 20 s `cat_timeout_s`, covering **74.3%** of
   recorded traffic — the other 25.7% needs a *named* skip. Nothing deployed or enabled, no
   `src/` change, `M-1` not engaged.

   **r49 — §18's first bar IS READ, and it FAILs (2026-09-04,
   [`r49-s18-bars.md`](./docs/unification/reports/r49-s18-bars.md), `GD-26`, $0).** The
   pre-registration was frozen before the harness ran (S1–S11 with S1/S3 KILL, six blind
   predictions, four consequence branches; binary world only — r48's six preconditions
   disposed inside it: four discharged by construction, two scoped to a categorical bar this
   read does not price), and it already carries a correction against its own author: the
   recon disclosure claimed `GD-18`'s empty commit column was *already* false, and a blind
   Amendment 1 **withdraws** that — `M-26` fired on this checkpoint itself. The 555
   `kind: "enact"` rows behind the claim are the **M5-deleted M3 lane's** (2026-07-20/22),
   whose writer's named defect is recording an agreement pass-through and a probe selection
   identically; the real leg A tap writes `mapped_*` onto `kind: "decide"` rows and exactly
   **one** exists — recording `gather` at `p1` 0.8621, *above* the deployed bar, mapped to
   gather anyway because an unapplied VOI transform pre-empts the argmax. **`GD-18`
   stands**, and the discarded "net −84 commits" figure never reached a criterion. Of what
   is read: **S3 (KILL) PASSES** — the commit rule's two spellings
   (`lattice_replay.commits_respond`, `coarse._gather`'s exhaustion argmax) agree on all
   200 001 grid points and flip at the bit-identical **0.8368942119315517** (prediction 1
   confirmed). And **S11 answers `GD-21`'s handed census YES, by a wide margin** — **116 of
   605** recorded m5-base `/decide` exchanges (19.2%) reach the exhausted argmax, and
   swapping the fixtures' era Ū (bar 0.897020) for the deployed boot Ū (bar 0.836900) flips
   **all 116** from abstain to commit at the ledger-max `p1` 0.8706074, while the control
   arm flips **0 of 116**, reproducing leg A exactly — the arms differ by the bar
   substitution alone. Ledger-wide, **1 276 of 6 873** recorded `p1` clear the deployed bar
   and **0** clear the fixture bar. Blind prediction 6 REFUTED (it said single digits:
   pre-emption acts *before* the population forms, not inside it). **S5 — THE BAR — FAILs on
   all three variants**: best P(Δ>0.05) **0.301** against the frozen 0.90, Δ̄ **−0.081**
   [−0.482, +0.205] (the leader-credence-only coarsening reads 0.000 / −1.479), over 423
   engine spawns in 14h02m. **The failure is pure over-assertion and 24 rows wide** — the
   membrane's report set strictly *contains* the baseline's (zero abstain×report rows), the
   26 shared commits never disagree about correctness, and the whole differential is 24
   marginal commits at **21 right / 3 wrong = 0.875**. **The gauge decides the sign**: those
   same rows are worth **+0.234/question** at the deployed boot Ū (break-even 0.837, the bar
   the policy was measured at) and **−0.250** at the gate's utility posterior (break-even
   0.900) — point Δ **+0.075 vs −0.080**, registered `M-31`, and `GD-26` **declined to
   re-read the bar at the softer gauge after seeing the FAIL** (§17.6 / `M-4`). **S6 blocks
   independently under `M-1`**: the arm commits **q2-019**, the named superset-confirm class
   currently *withheld* on deployed master, **wrong**. A third finding stands on its own:
   **`p-none` carries the entire policy** — `leader-credence` alone is degenerate
   (mean `p1` 0.8584 in four of five buckets ⇒ respond-all), while `n-candidates`, `n-obs`
   and `flags` change **no action on any of 238 ticks** and three of the seventeen declared
   indicators never fire at all. Predictions 2 and 4 REFUTED, 3 confirmed-in-letter with its
   ground refuted, 5 untested (depth was held fixed; model space varied). Two instrument
   gaps disclosed: Δ_spend is **0.000 structurally** (all 104 baseline rows carry
   `cost_usd: null` with zero token counters — unimputable, unlike r28's π\*), and the
   harness timestamps no phase boundary, so 14 hours cannot be attributed across its arms
   (`M-32` — which is what blocks sizing the parallel-harness successor). **The frozen stop
   rule is ENACTED**: §17.6 FAILed this same A3 criterion on 2026-08-17, so this is the
   second consecutive FAIL on one frozen criterion and **work STOPS for an owner ruling** —
   [`conferrals/s18-bar-conferral.md`](./docs/unification/conferrals/s18-bar-conferral.md)
   carries the evidence, five options and their prices. Nothing deployed, enabled or
   swapped; no `src/` change; no successor opened.

   **r49b IS READ — the conferral's question is WITHDRAWN as mis-posed (2026-09-05,
   [`r49b-utility-regimes.md`](./docs/unification/reports/r49b-utility-regimes.md), `GD-27`,
   $0).** The owner ruled that `u_wrong` is **not a gauge**: the affine gauge is the two pins
   (`u_correct = +1`, `u_abstain = 0`), and once they are fixed `u_wrong` is an **identified
   latent**, so −9.0 and −5.131 are two **estimates of one quantity**. That makes the choice
   **epistemic** — a question the constitution had already assigned to evidence — and `M-31`
   mis-routed it into `RULINGS` §5's *conventional* bucket, producing a **result-relevant**
   keypress: it flips the headline sign toward adoption (point Δ −0.080 → +0.075), though not by
   itself to a PASS — A3's P(Δ>0.05) ≥ 0.90 was never computed at that regime and is implausible
   at the measured interval width. **A bad question, not a bad answer**, and `core/utility.py` carried
   the right framing all along: *"two conditioning sets over one probability model"* —
   `all-to-date` folds the §4.4 verdict→evidence projection; the gate's `frozen-elicitations`
   **structurally refuses** it (it raises, so the blindness is a guard, not a default).

   The ruled remedy — *one utility, decision layer and gate both read it* — is **enacted in part
   and escalated in part**, because three facts refute its mechanism. (1) **There is no stale
   side-store:** `lookup.current_u_bar` re-reads model, elicitations *and* reactions on every
   call, recomputes `fold_version` and re-folds when it moves, and the bridge hands the membrane
   shadow that same live fold — so the "boot Ū" is a **snapshot of the live belief**, not a
   constant that drifted from it. (2) **It tracks, and not monotonically:** across 20 boot
   records `u_wrong` reads −5.9395 → **−8.8301** → −5.1310 (break-evens 0.8559 → **0.8983** →
   0.8369), so **in August the deployed bar sat within 0.002 of the gate's** — the gap is
   volatility in a conditioned latent, not a fixed offset between two ways of measuring. (3)
   **The labels are reversed:** −9.0 is the *elicitation-only* number (and `world.py:247`'s
   hardcoded fallback), −5.131 the *reaction-conditioned* one, so "the current posterior mean"
   is **−5.131** — the **softer** bar. Implemented literally the rule therefore scores the gate
   at 0.837, flips r49's point Δ from −0.080 to **+0.075**, and deletes an **anti-circularity
   guard**: reactions are projected from the owner's verdicts on the very decision log the gate
   scores. The rule written to prevent result-picking would, on today's numbers, deliver it. So
   it is **escalated, not resolved** (§17.6 / `M-4`), and the re-posed question is narrow and
   genuinely objective-class: **does the A3 gate keep its blind regime?** — circularity on one
   horn, a second master on the other, with three sub-answers costed in `r49b` §5.

   **Enacted:** `M-31` corrected (the word "gauge" withdrawn, the anti-circularity guard named),
   `GD-26` given a dated correction and its Reaction field filled, and **C built** — **`M-33`**:
   `gate.regime_pairing` / `break_even` / `render_regime_pairing`, with `break_even` derived
   *through* `decide.u_assert` rather than respelled (`M-7`), wired as a **preflight in
   `scripts/membrane/p3_gate.py`** that declares both regimes and both break-evens **before any
   engine spawns** and names the interval that would bite. Reproduced on r49's own artefacts:
   preflight prints `[0.8369, 0.9000]`, and at the measured 21/24 = 0.875 it flags the verdict
   **pairing-sensitive**. 16 tests, **6/6 mutations RED** — three initially SURVIVED (rounded
   endpoint stand-ins, no coincident-regime case, no reversed-order case) and one predicate was
   **dead rather than untested**, so it was removed instead of given a contrived test. Two record
   gaps disclosed and deliberately deferred (the boot record stores `u_bar` but not its policy;
   `a3_meta-*.json` stores neither) — additive schema fixes whose cost is a bridge restart, the
   `GD-20`/`M-27` hazard. **B is NOT opened**: the ruling is right that it is the substantive
   move and regime-independent (the 70–90 band's realised correctness of 0.80 sits below *both*
   break-evens), but it is a decision-path lever and needs its own pre-registration under `M-3`.
   `M-1`'s q2-019 still blocks deployment regardless.

   **Next (2026-09-05).** One question is held for the owner and gates nothing else: *does the
   A3 gate keep its blind regime?* — three sub-answers costed in `r49b` §5, each convertible
   into a $0 PR the day it is answered, and **nothing is re-read at the softer regime while it
   is open**. The stop rule is discharged: the ruling licensed the successor by name. **B IS
   OPEN as `r50` — pre-registration frozen `037b506`** (`r50-band-sharpening-preregistration.md`:
   eleven criteria, S1/S2 KILLs, three candidate families with an X-only tercile bucketing
   rule, six blind predictions, five consequence branches) — the address is r49's 70–90
   leader-credence band, 55 rows at realised 0.800 committed on every one at mean `p1` 0.863–0.873, below
   *both* break-evens, so the lever is regime-independent and it is §17.6's own direction (a
   sharper `p1`, never a softer bar). Its fork — a host-side family that *separates* the band,
   or the engine's guard prior (filed as demand, `M-23`/`GD-14`, never edited from here) — is
   settled by a $0 census through the harness's own `features_for` (`M-7`), with a KILL if no
   family separates the band. The same pre-registration carries the lattice trim under §10's
   retention test: `flags` fires 0/250, `n-candidates`/`n-obs` move zero actions once
   `leader-credence` + `p-none` are present, 960 models against 456 for identical decisions —
   the trimmed lattice reproducing r49's S4 policy is the control leg. The verdict is quoted at
   the standing blind regime with the `M-33` preflight, a straddle reported pairing-sensitive,
   a FAIL stopping for a ruling as before, and `M-1` (q2-019) gating any deployment regardless.
   **C's remainder — the harness half LANDED 2026-09-05**: `M-32` phase marks with
   `phases.json` and a line-buffered, boundary-stamped log, and the `a3_meta` regime record
   (both regimes, both Ū at full precision, the marginal-commit table, the pairing re-printed
   at the measured marginal rate) in `p3_gate.py` — 12 tests, 8/8 mutations RED, $0, no
   restart, so B's run is the first with attributable per-arm cost. Still open under C: the
   boot record's policy name on the next *natural* bridge restart (`GD-20`/`M-27`), and the
   baseline arm's spend re-recorded (`scripts/fairfight/arm_baseline.py`, single dollars, an
   `M-18` comparability rider) so Δ_spend is measured rather than structurally 0. **D** (the
   parallel harness, ~14h → ~2h) is sized from B's timestamped run, not before. The K-cap
   (k ≤ 3) and any move on #15 / E3 each still need their own pre-registration. Then §11's exit.
4. **[RETIRED 2026-08-31 — `G-1`. Items 4 and 5 *were* Stage 2; the aggregate family was
   additionally deleted by K1 as "family routing in disguise", its transformations kept.
   The thread transformations may still be built when evidence calls for them, never as a
   completion condition. Both are left standing below as the record they were.]**
   **The aggregate family** (subsumes D3): recall term + completeness priors,
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
should not read until this is settled. **[DISCHARGED — no keypress was needed. `r27`
(K4, 2026-08-28) resolved the numbering from four sites this reconstruction never opened,
and the audit read on 2026-08-31 (`G-2`). The next section is the resolution; this one is
left standing as the record of what was knowable from the sites it did open.]**

#### The stage map, resolved — 2026-08-28 (K4 · r27)

The reconstruction above stood on two attested item numbers and called items 3–5
unsourced. Four further sites, none of which it used, resolve the numbering — and they
agree with each other:

- `docs/membrane-shadow.md:1274` — the migration "is NOT a completion condition … **(Stages
  1–2–4 close without it)**". So the programme's stages run to at least 4, and one of them
  is the migration itself.
- `docs/unification/reports/r12-collapse-m2.md:14` — "**Stage 0 closed**: m2-base recorded".
- `docs/unification/reports/r18-aggregate-cp-a.md:3` — the aggregate family is "the
  completion programme's **Stage 2a**".
- `ROADMAP.md:161` — "**MVP exit test:** a week of the owner asking Jarvis instead of the
  incumbent harnesses for life-data questions + morning triage, misses logged to
  FAILURES.md", which `:223` places at the end of the chain, wall-clock-parallel from the
  deploy.

| Stage | What | Status |
|---|---|---|
| **0** | the riders — baseline re-record, doc-currency sweep, production readout | **DONE** (r11) |
| **1** | the collapse ladder M2–M7; Appendix A signed at M7 | **DONE** 2026-08-26 (r12–r17) |
| **2** | Phase 1.6 items 4–5 — the aggregate (2a) and thread families | **RETIRED from the programme by owner ruling 2026-08-31** (below) |
| **3** | the proplang graduation | ruled **not** a completion condition; **OPEN as Arc C** since the audit read (owner ruling 2026-08-31, `RULINGS.md` `G-2`) — item 3h below |
| **4** | the MVP exit test | **CLOSED 2026-08-30 at 69 asks** (Conferral 2, ruling 4) — see below |

That is five stages, 0–4, which is where "five DONE conditions" came from; item *N* is the
close of Stage *N* once the riders are dropped, exactly as the reconstruction's most
economical reading predicted. **The one thing it could not have known** is that Stage 3 is
the migration — the sentence naming it is in `membrane-shadow.md`, which never says
"programme stage".

**THE COMPLETION PROGRAMME IS CLOSED — 2026-08-31** (the completion audit,
[`r35`](./docs/unification/reports/r35-completion-audit.md), $0). Stages 0, 1 and 4 close
it; Stage 2 is retired (`G-1`) and Stage 3 was never a condition (`G-2`). Nothing in the
programme remains open. What that does **not**
close is recorded with it: Stage 4's named question — *why a system that measures better is not
the one being reached for* — which is a question about the objective, beyond what evidence can
settle from inside the system (`RULINGS.md` §5). Work continues, but it is no longer *programme*
work: capability is continuous and eval-gated under PRINCIPLES §9 as amended.

**Stage 2 — RETIRED 2026-08-31 (owner ruling, `RULINGS.md` `G-1`).** The deferral below waited on the exit-test measurement; that measurement closed 2026-08-30 at 69 asks, the question was put, and the ruling is **retire, not redefine** — capability work is continuous and eval-gated under PRINCIPLES §9 as amended, so it needs no programme stage, and the thread transformations may still be built when evidence calls for them, never as a completion condition. **The programme closes at Stages 0, 1 and 4.** The original deferral and its three options stand below as the record they were.

**Stage 2 — the deferral, as it stood.** As written Stage 2 cannot
close: it was specified as *builds* (the two families) while `bayesian-foundations.md` §12
gives it *gates*; K1 deleted the aggregate family as "family routing in disguise" while
keeping its transformations; and `cp-d-routing-conferral.md` says the remainder "dies with
`/route` at migration stage M5" — inside Stage 3, the stage ruled out of the programme. No
ruling about the thread family alone repairs that. The owner ruled on 2026-08-28 to **wait
for the exit-test measurement** rather than decide on a premise it may overturn. The three
live options are recorded for that ruling: read Stage 2 by its §12 gate and build only the
thread *transformations* with no family; re-point it at the fixed-pipeline property and
pull migration-M5 out of Stage 3; or retire it from the programme, capability work being
continuous and eval-gated under PRINCIPLES §9 as amended.

**Stage 4 — the owner is not running it, and the comparator has been measured all along.**
Asked on 2026-08-28, the owner said the exit test is not used, because a general coding
agent does the same job. That comparator is π\* (`scripts/fairfight/arm_claude.py`, ruled
the gold standard 2026-07-19), and `run_eval --gate-replay` has been reading against it
since run 6 — **every gate run in the §14 series is Δ2 against π\***, which no report said
because the renderer hard-coded the other arm's name (fixed at r27; register row 28).
**Run 18 (2026-08-26) reads PASS at P(Δ>0.05) = 0.959, Δ̄ = +0.514** — typed ahead of
Claude-Code-with-corpus-access on the owner's utility, up from −1.058 on 2026-08-06.

So Stage 4's open question is no longer "is the agent as good as the outside option" but
**why a system that measures better is not the one being reached for**. The gauge fixes
`u_abstain = 0`, so the utility model cannot represent the cost of *not* answering — and
declining to pay that cost is exactly what the owner did. That is the named next question,
recorded rather than answered — and since 2026-09-02 *priced* rather than merely recorded
([`u-abstain-conferral.md`](./docs/unification/conferrals/u-abstain-conferral.md): four
costed options, still owner-only).

**Stage 4 — CLOSED 2026-08-30 at 69 asks, and it ran after all.** The measurement went ahead
under a VOI stopping rule (owner-ruled, PR #120): it closes when two consecutive rounds of ≥8
mixed-class asks add no new failure signature and keep the dominant-class ranking. Rounds 7 and
8 both read dry, so it stopped at **69 lifetime asks**, six days inside the hard cap — eight
rounds, each under a manifest frozen and hashed before its first ask.

**The headline is zero wrong commits in 69 asks**, including on the strongest miscommit trap
built during the measurement (a question whose answer does not exist, with a plausible wrong
value adjacent to the very field label the question names, in four documents). The failure mode
is uniformly *silence*, never *error* — the calibration property the typed arm was adopted for.
The misses concentrate in three classes: **C** gold-leads-below-bar 13 · **normalisation** 12 ·
**B** narrative-inclusion 9.

[`Conferral 2`](./docs/unification/conferrals/conferral-2.md) (2026-08-30) took four rulings on
it; the three that bear on the reading are below, and the two that commissioned readings
have since read:

- **The Stage-4 closure is ACCEPTED as the exit read** (ruling 4), with levers before proplang
  and the risk named: levers built on the credence seam are work the ruled successor may reshape.
- **C was HELD pending a $0 bar reading** (rulings 1–2), which read the same day:
  [`r32`](./docs/unification/reports/r32-bar-reading.md) **PRICED** — the deployed bar is
  p† = 0.8522 at the rows in question (0.8369 today), not the declared 0.90, with the reaction
  stream the whole difference and all four attenuation candidates refuted. **C therefore gets no
  lever:** the window's highest abstained leader is 0.8282, *below* the deployed bar, and only 2
  of 70 abstains sit within 0.05 of it — **C is a dispersion problem, not a threshold problem**,
  the same finding the normalisation class reaches from the other side. The bar's own drift is a
  separate ruling (2026-08-31): **MONITOR ONLY**, armed by `r33` in the weekly readout.
- **All five instrument defects are fixed before any successor measurement** (ruling 3) — `r33`.

So the exit test is closed *and* read; the question above it stands, unanswered and unclaimed.

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
- **The goals/utility representation** (Phase 2) — still open as PRINCIPLES §15 states it
  ("the form the expected-utility model takes"). Note what is *not* open: the **answer**-utility
  gauge is built and deployed (`core/utility.py`, the faculty table above). What the decision
  covers is the model beyond it — goals, plans, and the write-actions those gate.
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
- **Phase 1.6 (the active phase):** every checkpoint is **pre-registered** — criteria, the rule
  table and the numeric consequence committed BEFORE the instrument exists and before any
  `src/` change (`M-3`); each load-bearing predicate verified **RED by mutation** before it is
  read (`G-3`); each universe named with its size. A lever that changes the decision path is
  read by a **priced gate run** against its frozen conjuncts (`run_eval --gate`), a $0 replay
  of an existing record, or both. **The outcome is bound by the consequence branch the
  checkpoint froze before it read** (`M-3`) — which has meant STOP-for-a-ruling as often as
  iterate (`r31` FAILed K6 and the arc closed; run 13 FAILed and the JOIN was reverted); a
  bar is never softened after the fact. Arc C alone carries `A-2`'s stricter rule, that a FAIL
  means iterate and re-run rather than park. The hard clause `M-1` overrides a PASS:
  **no lever ships while it makes a named wrong-commit class worse.**
- **Phase 2:** the read-only loop renders a daily briefing; credence asks/auto-proceeds appropriately
  on read-only capabilities; a goals/utility representation exists and is consulted.
