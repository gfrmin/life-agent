# SPEC-comparison.md — Phase 0 vs Phase 1, a pre-registered fairness contract

**Status:** frozen 2026-05-30. Changes require owner sign-off (this is a pre-registration; silent
edits defeat its purpose). No PII in this file or anywhere in the repo; the real eval fixture and all
run outputs live under `$LIFE_AGENT_KB`.

## 0. Purpose

Locate **where** two answer-anything systems diverge, not crown a winner.

- **Phase 0 (compile):** `bin/ask` — load the whole hand/model-authored wiki into the answer model,
  answer with citations. Anticipated facts are pre-materialised at compile time.
- **Phase 1 (retrieve):** pkm content-addressed retrieval (`pkm.retrieval.search`, FTS/vss over
  chunks) → the same model synthesises an answer from the top-k chunks. Misses are materialised into a
  content-addressed cache on demand.

**Hypothesis (not a foregone result):** parity on answer quality for *anticipated* order-1/order-2
questions; divergence on *engineering properties* — novel-query cost, incremental-update cost,
reproducibility/provenance — concentrated on order-N and unanticipated questions. Phase 1's claimed
wins are engineering, not answer quality. Answer-quality gains are a Phase-3 story and are **out of
scope** to claim here.

## 1. Corpus snapshot S — identical inputs, method is the only variable

Both systems are built from one frozen source set S, read **in full by both**. `scripts/comparison/
pin_snapshot.py` writes a content-addressed manifest `$LIFE_AGENT_KB/eval/snapshot_S.json` —
`{path, sha256, bytes}` per source file, reusing `pkm.hashing`.

**S is a *tractable complete slice* of the live pkm catalogue, not the whole catalogue.** The full
catalogue (~345k chunks / ~8.3k emails / 400+ MB of text) cannot be compiled into a Phase-0 wiki —
see the ceiling finding in §7d — so a corpus that *both* architectures can consume identically and
completely is required. S is bounded by **content-defined rules, not by the eval questions** (no
question-driven triage — that would confound architecture with input scope and destroy "method is the
only variable"):

  S = the source roots listed in the out-of-tree corpus config
      (`$LIFE_AGENT_KB/config/comparison-corpus.yaml`) ∪ **all mail (`INBOX`+`Sent`) dated within a
      single pinned calendar year** (~300 messages).

The mail-year bound is principled (a complete time window) and chosen so the frozen questions' one
email-dependent answer (a mid-year thread that falls inside the window) stays in scope; the window is
**not** narrowed to the thread. Total S ≈ 1,000 sources. The concrete roots, year, and pkm paths are
machine-specific identifiers and live only in the out-of-tree config — never in this repo.

**Claims are bounded to S.** This is a tractable complete slice; results characterise the two methods
*on this slice*, demonstrating mechanisms (the study is illustrative, n=22), not estimating effects
over the full corpus. `answerable` per question is (re)computed against S at pin time by the
membership check (`run_eval._answer_in_corpus`); a question whose only source falls outside S becomes
an honest-abstention case under S — recorded as a property of S, not hidden.

Phase 1 reads exactly S by searching the existing live pkm catalogue and **filtering every hit to the
pinned `snapshot_S.json` path set** (over-fetch, then drop any chunk whose source is not in S). This
is equivalent to "reading S" (S ⊂ live) with no re-extraction — avoiding a second extraction pass that
could differ from the live one. Phase 0's wiki is compiled from exactly S (§2). Email is thus in scope
for both, identically.

## 2. Phase-0 system

`scripts/comparison/compile_wiki.py` authors `wiki/*.md` from S with the **pinned answer model**
(§4, temperature 0) using the `docs/kb-schema.md` authoring prompt. Because S exceeds one context
(thousands of emails), the compile is **topic-sharded map-reduce**: shard sources → author per-topic
page drafts → reduce/merge into the wiki page set. The compile is metered (tokens, wall-clock) — that
cost is itself a divergence datum.

- **Not bit-reproducible — and that is a finding, not a flaw.** Temperature 0 is not deterministic,
  and on a hosted API request batching is not controllable, so a fresh compile of the same S can
  differ. The wiki is **compiled-once-and-frozen**: fixed *within* the experiment, not re-derivable
  across runs. Banked in §7c against Phase 1's byte-identical re-runs.
- **Known deviation (named, not silent).** The original q-001–q-019 answers were produced against the
  *real, hand-authored* wiki. `compile_wiki.py` produces a fresh **model-authored stand-in** from S.
  This recompile is the accepted price of getting email into scope for both systems (corpus Option 1).
  The stand-in is a faithful-method proxy for as-run Phase 0, **not** the identical artifact those
  answers came from. Results are read with this in mind.

`scripts/comparison/phase0_answer.py` runs the `bin/ask` method: whole wiki + question → answer +
citations; meters tokens and wall-clock.

## 3. Phase-1 system

`scripts/comparison/phase1_answer.py`: `pkm.retrieval.search` returns the top-k chunks (over-fetch,
then filter to the S manifest, then take top-k); the **same pinned model** synthesises an answer +
citations from only those chunks. Differs from Phase 0 **only** in context assembly (whole-wiki vs
top-k). Meters tokens, wall-clock, and pkm cache hit/miss.

**`k` is pinned at `k = 8`** — a conventional single-fact RAG context depth, chosen for the dominant
order-1/order-2 case and **deliberately independent of any aggregation question** (NOT tuned to
q-022's 12 invoices). **Both systems stay naive:** Phase 0 stuffs the whole wiki (unbounded recall
over its compiled corpus); Phase 1 retrieves a fixed k. No adaptive-k or retrieve-then-iterate — that
would pit a sophisticated Phase 1 against a vanilla Phase 0, its own asymmetry. The recall ceiling
this fixed k implies on wide aggregation queries is a **pre-registered architectural property**, not a
tuning accident — see §7e. So when q-022 (and possibly q-023) undercount, the report reads "as
predicted by the recall-ceiling property," never "noticed after the fact."

## 4. Pinned answer model (both systems)

`claude-sonnet-4-6` (matches `bin/ask`; strongest on this Hebrew/OCR-heavy corpus), temperature 0.
Exact dated snapshot ID is pinned in the run header at freeze and recorded with every result.
Sharing the model across both systems is the point: context assembly is the only free variable.

## 5. Comparable compute

Same machine, same model. Token / wall-clock / cache deltas are **measured, not equalised** — the
delta *is* the novel-query-cost metric. "Comparable" means same hardware and model tier, not equal
token counts.

## 6. Blind grading

`scripts/comparison/blind_judge.py`:

- **Strip provenance and normalise form.** Remove system labels; **normalise citation format across
  both answers** to a single neutral shape before grading. Phase 0 emits whole-wiki-style citations
  and Phase 1 emits chunk-id citations — if the *shape* survives, the judge infers the system even
  with labels gone and the blind leaks. Normalisation closes that channel. Randomise A/B order per
  question (seed recorded).
- **Rubric** `eval/rubric_v1.yaml`, scored per dimension: **faithfulness**, **completeness** (against
  the question's `expected_components`), **citation-fidelity**.
- **Citation-fidelity needs the span.** The judge is fed the **cited source text itself** (the
  chunk/span the answer points at), not just the answer + a citation marker. A judge shown only
  `[cite: doc_47]` rubber-stamps fabrications; verifying support requires the span in context.
- **Judge = one pinned cross-provider snapshot: OpenAI `gpt-5.1`** (`OPENAI_API_KEY`, read from
  gnome-keyring). A judge from a different model family than the Sonnet answerer is a structural
  defence against self-preference bias — independence, not capability, is what the result rests on.
  The nominal pin was Google Gemini, but that key has **zero billing credits** (HTTP 429), so the
  judge falls back to OpenAI — the **pre-approved alternate** from the same "Gemini or OpenAI"
  decision. The independence property (different family from the Anthropic answerer) is preserved;
  only the specific cross-provider vendor changed, under a forced operational constraint. The exact
  served snapshot string is captured per call into the run record. OpenAI's newer models accept only
  the default temperature, so judge temperature is left at default and determinism is approximated by
  **N=3 modal** per question (the same N=3 the contract already specified).
- Per-question dimension scores persisted to `$LIFE_AGENT_KB/eval/comparison/`, **broken down by
  order**.

## 7. Divergence metrics — the point of the exercise

- **(a) Novel-query cost (order-N / unanticipated).** Tokens, wall-clock, cache hit-rate per system.
  Phase 0 re-stuffs whole-wiki context (and, for a genuinely novel topic, needs a recompile to even
  contain the fact); Phase 1 materialises the miss into its cache once, then serves it.
- **(b) Incremental-update cost.** Edit a few source docs in S → re-ask the dependent questions →
  measure what each system spends to reflect the change, **and whether it reflects it at all**. Phase
  0 must re-compile affected pages; Phase 1 re-ingests only the changed content-addressed objects
  (unchanged objects stay cached). Report spend + correctness-of-reflection for both.
- **(c) Reproducibility.** Re-run identical queries. Phase 1 re-runs **byte-identical** (content-
  addressed cache hit) with intact PROV-O lineage. Phase 0's compile is **not** bit-reproducible (§2).
  This asymmetry is a **primary finding**: determinism + re-derivable lineage is exactly the
  engineering property Phase 1 buys and Phase 0 cannot, independent of answer quality.
- **(d) Corpus-size ceiling — a structural finding, surfaced by the scoping itself.** The reason S had
  to be a tractable slice (§1) is itself evidence for the thesis: **Phase 0 (compile-everything) has a
  corpus-size ceiling that Phase 1 (retrieve-on-demand) does not.** The full catalogue (~345k chunks)
  cannot be stuffed into a wiki compile at any acceptable cost; retrieval indexes it without that
  ceiling. This belongs in the divergence column next to (c), not as an apology for the slice: the
  constraint that forced the scoping decision *is* a result. Report the chunk/token scale of full S vs
  the slice, and state that Phase 0 does not run at full-S scale.
- **(e) Recall ceiling — the symmetric counterpart to (d).** Phase 1 reads a **fixed top-k=8** (§3),
  so on **wide aggregation queries** (q-022 sums 12 invoices; q-023 enumerates ≥5 holdings) it
  structurally cannot see every relevant chunk at once, while Phase 0's whole-wiki context has
  unbounded recall over its compiled corpus. **Pre-registered** (decided before the run, not after
  seeing q-022 undercount). Pairs symmetrically with (d): each architecture has a context-budget
  failure at **opposite ends** — Phase 0 cannot scale the corpus *up* (size ceiling), Phase 1 cannot
  widen recall *within* a query (recall ceiling). Reported as a matched pair. **Attribution rule for
  `report.py`:** at k=8 a q-022/q-023 undercount is *one* underlying cause (the recall ceiling) — it is
  attributed **once**, not double-counted as both a recall-ceiling finding *and* an independent
  completeness failure.

## 8. Reporting

Order buckets (1 / 2 / N) reported **separately**. **Report parity where it exists** rather than
burying it under an aggregate. State plainly that Phase 1's wins are engineering (cost / provenance /
determinism), not answer quality. Caveats stated in-line, not hidden:

- **order-N is small-n**; within it the anticipated-vs-unanticipated contrast is **n=1 (q-013) vs n=2
  (q-022, q-023)**. It survives only because the divergence metrics are *mechanistic per-question
  costs*, not statistical effects. The writeup must not imply the anticipated-order-N quality reading
  rests on more than that single point.
- **Recorded deviations** (named, not silent): the recompiled-wiki stand-in (§2) and Phase-0
  non-reproducibility (§7c) are reported as findings; and the **judge vendor swap Gemini→OpenAI
  `gpt-5.1`** (§6, forced by Gemini's depleted key) — a move within the pre-approved cross-provider
  set that preserves the independence property (judge family ≠ answerer family).
- The gold for q-022/q-023 is **human-established, double-pass reconciled** (§ eval fixture), not
  pipeline-derived — so a pipeline miss vs hand-counted gold is a *measured* coverage gap.
- **q-023 completeness is recall-against-known-minimum, and `report.py` must label it as such.** Its
  gold is a known *lower bound* (not proven-exhaustive), so a system scoring 100% means "found the
  known minimum," not "found everything." `report.py` prints q-023 completeness under that explicit
  label and **must not fold it into any aggregate completeness number that would read as true recall**.
  The flag survives into the output, not just the planning notes.
- **Interrogate the wins harder than the ties.** Parity on order-1/2 is self-consistent and expected;
  a large Phase-1 advantage on q-022/q-023 is exactly where a quiet bug would hide (a citation-shape
  leak normalisation missed, a gold miscount, a judge reading chunk-ids), because it is the flattering
  result and thus the least-scrutinised. The analysis treats the convenient result as the suspect:
  every order-N Phase-1 win is re-checked against the raw answers, the normalised blind inputs, and the
  hand-counted gold before it is reported.

## 9. Placement (no PII / no experiment artifacts in the repo)

| In repo (no PII) | Out of tree (`$LIFE_AGENT_KB`, PII / outputs) |
|---|---|
| `scripts/comparison/*.py`, this SPEC, `eval/rubric_v1.yaml`, `eval/questions_v1.example.jsonl` | `eval/questions_v1.jsonl` (real), `eval/snapshot_S.json`, recompiled `wiki/`, per-question answers, judge scores, reports |

## 10. Eval fixture binding

The frozen question set is `$LIFE_AGENT_KB/eval/questions_v1.jsonl` (schema mirrored in
`eval/questions_v1.example.jsonl`). Immutable once approved. q-019 is retained for lineage but
**excluded from scoring** (duplicate of q-001). Aggregation gold (q-022, q-023) is **human-established
by reading the source documents in S, enumerated twice on separate passes and reconciled** before
freeze, with per-fact source provenance recorded — never derived from the pipeline's own extraction.
