# r51 — an external, public, labelled corpus for §18's evidence problem — PRE-REGISTRATION

**Frozen before any download, build or engine work** (`M-3`). Ten criteria (X1, X2 and X3a–c
carry KILL clauses; X3d carries a VOID clause on the primary read), eleven blind predictions,
six consequence branches. Committed before any measurement — before even the corpus is on the
machine — and every frozen clause is re-read against the artefact it names before it is applied.
Changes after this commit go by dated blind amendment only (the log at the end).

## The question

`GD-28` closed B because **the verdict supply binds every evidence-side lever on §18's bar**: a
two-cell separation of the 70–90 band at BF ≥ 10 needs ≈385 verdicted band rows (≈495 for three
cells) and the owner supplies ≈7 a month. `A-11` filed the engine-side pooled-prior hypothesis as
demand on proplang (#26, 0 comments at freeze) on a five-cell table built from **238 ticks / 141
questions** — small enough that the counterparty can reasonably answer "small-n shrinkage".
Nothing in the ruled queue grows n.

**Does the engine's held-out `p1` still read as a pooled shape — pulled toward a common value in
both directions — when the labelled supply is ~10× `r49`'s, on a public corpus the owner did not
author?** And, as by-products of the same run: the A3 differential quoted under `M-34`, and the
`u_wrong` sensitivity curve `DR-UTILITY-1` §4 asks for, with the bounded-improvement reading
`OPEN-QUESTIONS-utility.md` OQ-0′ (c′) needs.

The corpus is **ATM-Bench** (arXiv 2603.01990; HF dataset `Jingbiao/ATM-Bench`, released
2026-03-12; data CC-BY-NC 4.0, code MIT): 6,741 emails, LLM-paraphrased with synthetic PII then
human-audited, and 1,013 + 25 QA pairs with human-annotated, second-annotator-validated evidence
ids. A labelled personal-memory corpus at roughly 30–50× the owner's monthly accrual, with zero PII
risk to this public repo, read by an instrument a stranger can reproduce.

## Provenance — the owner's choice, and what it excludes

This checkpoint opens on an owner choice taken in plan mode on 2026-09-06 (`M-17`'s form: four
priced options, a recommendation first). Offered: **external-corpus pre-registration** ·
docs-only external anchors for `u_wrong` · rule the number by convention · hold. The owner chose
the first and nothing else; the other three are NOT in scope and are not reopened here. The
choice is registered as `A-12` and the fork as `GD-30`, in this commit.

## Scope — one instrument, two KB roots, nothing deploys

- **A measurement, not a bar.** The existing harness (`scripts/membrane/p3_gate.py`) runs over a
  SECOND KB root built from the external corpus. It reads the engine's held-out calibration per
  leader-credence cell at ~10× the n, the A3 differential, and the `u_wrong` curve. It is also the
  well-powered form of `DR-DECISION-1` §10 step 0 — the pooled-shape read *is* the A-CAL
  measurement (§2.1), whose theorem is Fumera, Roli & Giacinto (2000): Chow's rule is optimal
  only against true posteriors.
- **NOT a §18 bar read.** The bars are the owner's traffic under the frozen bars
  (membrane-shadow §18); the consecutive-FAIL counter does not move on anything read here.
- **NOT a gauge change.** `GD-27`/`M-34` untouched; the gate scores at `frozen-elicitations`.
- **NOT a decide-path lever.** The one `src/` edit is a dated docstring clause in
  `core/claude_verdicts.py` (below); `M-1` is not engaged; nothing deploys, enables or swaps.
- **The owner's KB is byte-untouched** (X9).
- **World and variants**: the binary `said@1` world; FULL and `leader-credence+p-none` (`r49`'s
  control pair).
- **Pricing Ū and the pairing.** The pricing Ū is the external KB's `current_u_bar` — the
  `all-to-date` fold over ZERO reactions, which equals the elicitation fold numerically. So the
  two break-evens **coincide** while the policy LABELS still differ; `RegimePairing.divergent` is
  "names differ OR break-evens differ" (`core/gate.py`), and `straddles` is strict, so
  **`M-34`'s INCONCLUSIVE cannot arise on a reaction-free KB**. Pinned by a test, disclosed in
  the report; the owner-corpus straddle is not reproducible here.

## Recon disclosure — what was seen before this was frozen

Seen: the paper's counts and taxonomy; `docs/data.md`'s field names (email records
`{id, timestamp, short_summary, detail}` — no from/to/subject; QA records `{id, question, answer,
evidence_ids}` — no type field); the README's license and judge; and the evaluator source at
`JingbiaoMei/ATM-Bench` `ef4e5dff1a47e…` (`normalizer.py`, `qtype_utils.py`, `evaluate_qa.py`,
`config.py`). **NOT seen**: any question, answer or email text; any per-shape or per-modality
count; the dataset files themselves (not downloaded).

Corrections to the survey that motivated this, from the sources: the data license is
**CC-BY-NC 4.0** (the GitHub code is MIT) — fine for non-commercial research, never redistributed
from this repo, never committed; **abstention items number 25** (paper App. C.1; the "0.3%"
printed beside it is the paper's own arithmetic error, 25/1,038 = 2.4%), so the abstention leg is
a small named secondary (X10), not a primary; the paper's 360 / 139 / 514 number / list / open
split is produced by a deterministic **answer-text** detector (`qtype_utils.detect_qtype`, line
176 — *Amendment 1*; falling back from an optional `qtype` key via `normalize_qtype_value`,
`evaluate_qa.py:913`); numbers are graded by
exact match after resolving relative dates against the question's "Today is …" anchor, stripping
currency breakdowns and parentheticals, and normalising (`_deterministic_accuracy_core`,
`evaluate_qa.py:181`, returning `tuple[bool, str]`; `deterministic_accuracy -> bool` at 304 —
*Amendment 1*);
lists by Jaccard; open-ended by an LLM judge. The π\* baseline is NOT needed — the A3 differential
baselines on the credence executor arm — so the priced pass is single-digit dollars.

**The "never values" rule is the owner-KB PII rule.** ATM-Bench is consented, PII-stripped and
public; on it the rule is narrowed to: *no ATM value in the repo, the PR, the report, or any
pushed artefact; values may be read on the machine where this pre-registration requires it* —
the grader audit (X3d) and nowhere else. Stated here so the audit is not a deviation.

## Frozen rules

- **Population.** QA whose `evidence_ids` are ALL email ids.
- **Gradeability is a property of the ANSWER**, typed by the vendored `detect_qtype(answer)`:
  `number` rows are mechanically gradeable; `list_recall` and `open_end` rows are not (named
  classes, counted, no verdict tick). The LANE (r29's rule table, `answer_shape_census.classify`,
  measured 0.74 vs a blind manual reference, disagreement one-directional toward `exact`) is run
  mechanically over the QUESTION text before any answering and its distribution published; type
  × lane is reported as a cross-tabulation, itself an output — the first external measurement
  of the lane regex against an answer-typed reference. The lane no longer gates gradeability.
- **Verdict.** For `number` rows, `correct = atm_number_match(gold, leader, question)` — the
  vendored `_deterministic_accuracy_core` at pinned sha (relative dates resolved against the
  question's anchor, currency breakdowns and parentheticals stripped, codes matched exactly, then
  normalised comparison). The harness's own `answer_matches` (`core/matching.py`) is computed on
  the same rows as a SECOND reading and the two are cross-tabulated; it decides nothing. No LLM
  judge in the verdict path. The leader is the harness's own (`scripts/claude_verdict.py`'s
  `_leader`, max credence) — one leader rule, `M-7`.
- **Grader-error ceiling (X3d).** After the gold pass, 60 verdicted rows sampled by a pinned seed
  from the sorted ids, hand-audited on-machine, blind to `p1` and to the verdict column.
  Auditor: this agent, in-session, deliberating each row against the corpus (the Claude verdict
  channel's own standard — a deliberation, never a batch projection); the owner may overrule any
  row. Report grader precision and recall against the audit. **If the grader's false-negative
  rate (gold correct, verdict wrong) exceeds 0.10, X4 is VOID** — published as such, no branch
  fires — and a blind amendment names the fix before any re-read. Why 0.10: a false-negative rate
  r lowers every cell's realised rate by ≈ r·(1−realised); at r = 0.10 that is ≤ 0.05 in the
  upper cells, X4-R's tolerance.
- **Folds.** K = 10, questions assigned by **sorted-rank round-robin** (`sorted(qids).index(q) %
  K`): `question_id` is already sha256(text) (`core/decisions.py`), so sorted order is
  pseudo-random w.r.t. time and content, balanced (sizes differ ≤ 1), deterministic, with no
  second hash. Rejected: insertion-order blocks (ledger time order, not exchangeable); sha256 mod
  K (multinomially unbalanced, ±5 at n ≈ 245). One engine per fold, folded on the other nine.
  K = n is exactly today's LOO and must reproduce it byte-for-byte (X3a).
- **Cells.** PRIMARY — **deciles of LEADER CREDENCE** over all verdicted ticks (ten cells,
  always populated; edges published; ties broken by stable sort on question id). SECONDARY —
  `r49`'s five fixed leader-credence buckets (`lt50`, `50to70`, `70to80`, `80to90`, `ge90`), for
  side-by-side comparability with the owner-corpus table. DESCRIPTIVE — the reliability diagram
  and ECE over deciles of held-out `p1`. *Why not `p1`-deciles as primary*: the hypothesis is that
  `p1` does not follow the cells the FEATURE defines, so the cells must be cut on the feature.
  Cut on `p1` itself, a pooled `p1` (near-constant, heavily tied) makes the cells arbitrary, and
  ten arbitrary cells of n = 60 at realised ≈ 0.8 have an expected range of ≈ 3.1·SE ≈ 0.16 by
  noise alone — a "realised span > 0.15" bar would fire about half the time under the null.
  Leader-credence deciles carry a real gradient (`r49`: 0.65 → 1.00) and a monotonicity guard
  (X4 iii) that noise cannot pass.
- **Readability.** A decile is readable at n ≥ 60 (2·SE ≤ 0.13; a 0.10 span between adjacent
  deciles is detectable). A fixed bucket is readable at n ≥ 100 for the three upper buckets
  (they carry the CONFIRMED read and need the power) and n ≥ 30 for the lower two (descriptive).
- **Tree pins (`M-28`).** Repo sha, engine sha (`~/.local/bin/proplang-host`, `r49`'s pin),
  HF dataset revision, ATM-Bench code sha (`ef4e5dff`) for the vendored evaluator, the external
  `questions.yaml` sha256, the `pin_corpus` manifest of the external store — in the report and
  in `run_meta`.
- **The corpus never enters the repo.** No ATM-Bench file, value, id or per-row field is
  committed, pushed, or quoted; the report carries counts and aggregates only.

## Criteria (X1–X10; X1, X2 and X3a–c carry KILLs; X3d carries a VOID)

- **X1 (KILL, recon).** Email-only ∧ `number`-typed QA ≥ **200** (≈2× the owner's 104). Below →
  KILL: the corpus cannot move the supply; report and stop. The count is mechanical from the
  released answers (`detect_qtype`), so X1 is decided by recon alone with no question text read.
- **X2 (KILL, build control).** (a) pkm ingest double-run = zero new writes; (b) a 20-question
  pilot through the second bridge returns ≥ 1 `report` and measures ≤ **$0.10/q** (else STOP and
  re-price before the full pass).
- **X3 (controls, harness).** (a) unit: K = n reproduces today's LOO rows byte-identically on the
  fake client; (b) one fold re-run twice → identical `p1`s; (c) the `leader-credence+p-none`
  variant reproduces FULL's policy on the paired file (`r49`'s control); (d) the grader audit
  above — precision, recall, and the `atm_number_match` vs `answer_matches` cross-tab, published
  whatever they show; (e) the vendored classifier reproduces the paper: `detect_qtype` over ALL
  1,013 released answers reads number / list / open within **±5%** of 360 / 139 / 514 (the paper
  attributes the split to annotators; the code derives it — a larger disagreement means the
  vendoring or the attribution is wrong, and X1's count is not trusted until the difference is
  named). (a)–(c) KILL; (d) VOIDs X4 above the ceiling; (e) holds X1's count.
- **X4 (PRIMARY — the pooled-prior read).** Per readable leader-credence decile (n ≥ 60): n,
  realised rate, mean held-out `p1`, 90% interval; the same table over the fixed buckets as the
  secondary; the `p1`-decile reliability diagram and ECE as descriptives.
  **CONFIRMED** if, over the readable leader-credence deciles, (i) mean `p1` spans < **0.05**,
  (ii) realised spans > **0.15**, and (iii) realised is monotone in the decile index — Spearman
  ρ ≥ **0.6** over the readable deciles (credence flat, truth rising with the feature; (iii) is
  what noise cannot pass) — *or*, on the fixed buckets, the three upper buckets are all readable,
  their mean `p1` lie within **0.02** of one another and their realised rates span > **0.10**
  (`r49`'s exact form, so the two corpora are read by one rule).
  **REFUTED** if every readable leader-credence decile has |mean `p1` − realised| ≤ **0.05** *and*
  at least six deciles are readable (calibration within tolerance along the feature, with the
  power to have seen a miss).
  Otherwise **INCONCLUSIVE**, the reason named: which condition failed, and whether for want of
  rows or for want of effect.
- **X5 (secondary).** `r50`'s S2 separation census through `band_census.py` on the external
  replay — read ONLY if band n ≥ **385**; otherwise published as under-powered with the n reached.
  AUGRC reported beside any selective-risk aggregate (Traub et al., NeurIPS 2024).
- **X6.** The A3 differential (P(Δ > 0.05), Δ̄, the marginal-commit table) quoted with the `M-34`
  verdict at `frozen-elicitations`. **Recorded, not enacted; NOT a §18 bar** — no counter moves.
- **X7.** The `u_wrong` curve on the external paired file at **{−1, −4, −5.131, −7.4285, −9,
  −12}**: P(Δ > δ), Δ̄, break-even, marginal reach; the ruled regime's point marked. At each grid
  point also the implied commit bar `|u|/(1+|u|)`, the coverage at that bar, and the selective
  risk among the covered rows — the first data on whether OQ-0′ (c′), *rule a target risk and
  derive `u_wrong`*, has anything to bite on. A sensitivity deliverable, never a verdict (`M-4`).
- **X8.** `M-1` — N/A: nothing deploys; the named classes are owner-corpus rows. Stated.
- **X9 (blast radius).** sha256 manifest of the owner KB's `calibration/*.jsonl`,
  `membrane/shadow.jsonl` and `utility/*` taken before the second stack is built and after the
  read — **identical**; no production unit restarted. Plus: the r51 root is not a git working
  tree and sits under no path any pushed repo tracks; `utility/elicitations.jsonl` — copied to the
  external root by `copy_gauge` and the one file C-1 says is unverifiable from public master — is
  named in the manifest of things that must never appear in a diff.
- **X10 (secondary, descriptive).** The 25 abstention rows (identified by the vendored
  `is_abstention(answer)`), where email-only: their held-out `p_none` and leader `p1` against the
  same statistics on the `number` rows. Descriptive only, and the only public gold for the NONE
  atom this programme will see.

## Blind predictions (reasoning only — nothing has been downloaded)

1. **P1** — email-only ∧ `number`-typed QA ∈ **[120, 240]**. 360 number rows overall; the paper's
   topic table (Table 7: Work + Learning, Personal Information, Travel, Activities, Household,
   Everyday Life Logging) suggests record-keeping topics are email-centric, so roughly half of
   number rows are email-only. Its per-modality breakdown was not visible in the fetched text, so
   this rationale is a guess, stated as one. X1 sits inside the interval.
2. **P1′** — `detect_qtype` over all 1,013 released answers reproduces 360 / 139 / 514 within ±5%
   (X3e).
3. **P2** — the lane regex reads `quantity` on ≥ **60%** of the gradeable rows; the cross-tab shows
   it under-calling `quantity` on date answers.
4. **P3** — the typed answer rate on the external corpus is **0.30–0.50** (below the owner's
   0.47–0.71: short paraphrased emails disperse).
5. **P4** — X4 **CONFIRMED on the decile read** (the shape survives 10× n — the result that
   matters for proplang#26).
6. **P4′** — the fixed-bucket read is INCONCLUSIVE for want of rows in `ge90` (P3's consequence;
   this is why deciles are primary).
7. **P5** — band n ∈ [80, 200]; X5 under-powered.
8. **P6** — X6 reads **FAIL**, the differential dominated by marginal commits in 70–90 (as `r49`),
   no straddle (none is possible here).
9. **P7** — the grader's false-negative rate on the audit is ≤ 0.05 with the vendored matcher (X4
   not void); `answer_matches` alone would have exceeded 0.10 on the same rows.
10. **P8** — X7's implied-bar coverage falls below 0.30 at `u_wrong = −9` and above 0.60 at `−1`.
11. **P9** — X10 has ≤ 10 email-only abstention rows.

## Consequence branches (frozen before the reading)

- **X1 KILLs** → no build; the recon counts are published and the checkpoint closes as *cannot
  move the supply*.
- **X2 or X3a–c KILLs** → STOP; re-scope under a dated blind amendment; no reading is taken.
- **X3d ceiling exceeded** → X4 is VOID, published as such, no branch fires; the fix goes in a
  blind amendment before any re-read.
- **X4 CONFIRMED** → the decile table, the fixed-bucket table and the pins go to **proplang#26 as
  a comment** (evidence on the standing demand — `M-23`/`GD-14`'s channel; never a repo edit),
  with the grader audit and the decile-vs-bucket disclosure attached so the counterparty can see
  the verdict path was not the source of the shape.
- **X4 REFUTED** → proplang#26 gets a dated correction ("small-n shape; the demand is withdrawn,
  the note kept"); re-opening B with the external supply is **named for the owner** (`RULINGS`
  §5's "what to build next" class), not opened; `DR-DECISION-1` §2.1 A-CAL is annotated: held on
  this corpus at this n, per-lane not yet tested.
- **X4 INCONCLUSIVE** → published with the reason; nothing opens.
- **In every branch**: nothing deploys; `r49`'s reading is untouched; §18's counters are
  untouched; no bar is loosened (`M-4`).

## Cost

Build $0. Download ≈ 50 MB (email + QA JSON only). Ingest ≈ $0 (email producer + FTS; no
projections derived). Pilot ≤ $2. Full executor pass ≈ email-only questions × ~$0.007 (run 14's
typed $/q including deliberates; `--no-judge`) — **≤ $7** over the whole email-only set. Engine run
$0: `r49` measured 423 spawns in 14h02m ≈ 119 s per spawn at ≈ 249 folded ticks ≈ **0.48 s per
tick-fold**, so ~1,000 ticks read **LOO ≈ 133 h · K = 10 ≈ 72 min · K = 20 ≈ 2.5 h**; a timing
probe (one spawn folding N ∈ {250, 500, 900} ticks) confirms the constant before the run. Serial
on this machine as a transient `systemd --user` unit with `M-32` marks; no second machine is assumed (production moved here 2026-08-30).
**Comparability disclosure:** K = 10 folds each engine on 90% of the ticks where `r49`'s LOO
folded on ≈ 99.6%; the "10× n" claim is about the *verdict* supply, and the per-engine training
supply is ≈ 9×. Stated once here, not repeated.

## The build this licenses (summary; the PR carries the tests)

In order, each under TDD with a mutation battery: (2e) ATM-Bench's evaluator vendored at pinned
sha into `scripts/atm_bench/vendored/` — `normalizer.py` and `qtype_utils.py` copied, the
`ABSTENTION_PHRASES` constant copied out of a `config.py` that is itself not vendorable (it
imports the project's OpenAI/vLLM configuration), `_deterministic_accuracy_core` and
`deterministic_accuracy` extracted from `evaluate_qa.py` together with the four date/token
helpers the core calls that live in that file and not in the normalizer
(`date_component_match`, `date_token_match`, `dates_match`, `tokens_match` — *Amendment 1*),
with only the imports they need; the
only edit to copied text is the import path, disclosed in a `SOURCE` file and pinned by a sha
test; the directory excluded from ruff/mypy by a named entry. (2c) `p3_gate.py`: k-fold
`probe_heldout` (K = n ≡ LOO), a declared Ū source (`boot` | `current`, the label carrying the
source — a disclosed record change: boot runs print `all-to-date@boot` where `r49`/`r50` printed
`all-to-date`), `pricing` in the regime record, decile cells, ECE/reliability/Spearman.
(2b) `scripts/gold_verdicts.py`: a verdict writer that refuses (rc 2) any KB without
`external-corpus.json` — the ONE guard keeping a gold row off the owner's ledger (issuer-blind
supersession would otherwise let `gold:*` supersede a `claude-code` row there) — writing
`ClaudeVerdictEvent`s with issuer `gold:<corpus>`, `evidence=("<corpus>:<qa id>",)`, and the
harness-match bit in `note`; plus the seeded audit sample to a local file outside the repo.
(2a) `scripts/atm_bench/build_kb.py`: `.eml` per record carrying only `Date`, `Subject` (the
short summary) and `Message-ID: <id@atm-bench>` — no From/To/Cc — with the detail as body;
questions with all-email evidence, `fuzzy` from the answer type, `answer_variants` empty on
purpose (normalisation lives in the matcher, not the data), notes carrying ids never values; the
registry, pkm config (binding the installed email-producer version), a one-line owner profile,
`copy_gauge` (exactly `utility/model.yaml` + `utility/elicitations.jsonl`, both sha256s in the
manifest), the pkm steps as subprocesses. (2d) `GD-30`; this log.

**The one `src/` edit**, named here because `M-3` binds: `core/claude_verdicts.py`'s docstring
gains a dated clause — the rule "every verdict must be deliberated, never batch-derived" protects
the OWNER's ledger from grader output at verdict authority; it does not forbid a gold verdict on
a non-owner KB where a human-annotated benchmark answer IS the truth measurement; such rows carry
a non-default issuer `gold:<corpus>`, are written only by `scripts/gold_verdicts.py` into a KB
that declares itself external, and never enter the owner's log (`GD-30`).

## Scope, explicit

This does **not** touch the utility model, the gauge, the commit rule, the gate's δ/level, the
regime the gate scores at, or `M-34`'s verdict rule; does **not** enable or price the categorical
world; does **not** build the parallel harness (D); does **not** re-record the baseline arm's
spend; does **not** restart any production unit; does **not** edit proplang (a comment on #26 is
the only outward act, and only on the branch that earns it); and does **not** commit, push or
quote any ATM-Bench content.

## Amendment log (blind, dated)

**Amendment 1 — 2026-09-06, after the freeze commit `62a880f`, before any download.** The
evaluator line pins in the recon disclosure were wrong and are corrected in place (marked
*Amendment 1*). Read by `curl` of the raw files at the pinned sha
`ef4e5dff1a47ec71213a06e359f02753defa8fb1` — which is also HEAD of the repository's `main`
(last push 2026-08-13; the evaluator directory last changed 2026-06-01): `normalizer.py` is 745
lines; `qtype_utils.py` 191 with `detect_qtype` at 176; `evaluate_qa.py` 1,370 with
`_deterministic_accuracy_core` at 181 (→ `tuple[bool, str]`), `deterministic_accuracy` at 304
(→ `bool`) and the `qtype` fallback `normalize_qtype_value` at 913; `config.py` 98 lines with
`ABSTENTION_PHRASES` = **seven** strings (one the "no evidnece" typo-duplicate, kept verbatim),
importing `memqa.global_config` and therefore not vendorable. The plan's revision-3 numbers
(574 / 159:121 / 211 / 294 / 357 / 105 lines / eight strings) match no ref of the repository
and are withdrawn; revision 2's were right. **Every mechanism claim holds at the sha**:
`detect_qtype` is answer-only; the core resolves relative dates against
`extract_reference_date(question)`, strips parentheticals and currency breakdowns, matches
codes exactly, then compares normalised text; `is_abstention` is a substring test over the
phrase list. One consequence for the build: the core calls four helpers defined in
`evaluate_qa.py` itself (`date_component_match` 145, `date_token_match` 151, `dates_match`
163, `tokens_match` 177), so `matcher.py` extracts six functions, not two. **No criterion,
rule, prediction or consequence branch changes.** Lesson, for the amendment record: a line
pin is verified only by a `curl` of the raw file at the sha; a rendered or summarised fetch
is not a source.

Expected further entries, each named here so they are not deviations: the recon counts (X1,
X3e); the `--expect-ticks` / `--expect-questions` pins and the harness-match cross-tab after the
gold pass; the X3d audit tally (TP/FP/FN/TN); the timing-probe constant; the X9 manifests.
