# r52 — the corpus-pooling recon — PRE-REGISTRATION

**Frozen 2026-09-07 before any download, build or count (`M-3`).** Repo tree at freeze: `741b629` (master after
`r51b`'s merge, PR #184). Inputs it binds: the vendored ATM-Bench evaluator (`scripts/atm_bench/vendored`, upstream
`ef4e5dff`) for answer typing and abstention; the lane classifier `scripts/answer_shape_census.classify`; the band
constant from `r51b-replication.md` (29 of 195 verdicted ticks in the 0.7–0.9 band, 0.149) with `r49`'s 55 of 238
(0.231) beside it; `r51b`'s measured $0.107/q and 0.472 s per tick-fold. Every count below is read on-machine; no
corpus content — question, answer, session text, id — enters the tree, the PR or the report (the `r51` rule). A
change after this commit is a dated amendment; the consequence branches are frozen (`A-2`).

**Ruled by `A-13`** (owner, 2026-09-06): after `r51b`, the corpus-pooling recon opens as its own $0 checkpoint, sized
in the foldable unit (`M-35`). This is that checkpoint's pre-registration. Nothing is downloaded, built, or run until
it is committed; the read is counts and aggregates only; no corpus content ever enters the tree.

## Question

Can pooling public labelled corpora reach the labelled supply that `GD-28` priced as binding on every evidence-side
lever on §18's bar — **≈385 band rows (0.7 ≤ leader credence < 0.9) for a two-cell separation at BF ≥ 10** — when
each corpus yields **one verdicted tick per mechanically gradeable question per pass** (`M-35`), and what does it cost
to get there?

## Candidates and what is known before download (public sources, read 2026-09-06 — counts to be verified at recon)

| corpus | items | shape | evidence labels | answer grading | data licence |
|---|---:|---|---|---|---|
| ATM-Bench email subset (`r51`/`r51b`) | 381 email-only QA, **198** number-typed | paraphrased emails | `evidence_ids` (human, validated) | benchmark matcher, deterministic | CC-BY-NC 4.0 |
| LongMemEval (`xiaowu0162/longmemeval-cleaned`, MIT) | **500** questions (S/M/Oracle are one question set with three haystacks); 6 `question_type` values; exactly 30 abstention rows (`_abs` id suffix) | user–assistant chat sessions with dates; Oracle carries only the evidence sessions | `answer_session_ids` + per-turn `has_answer` (human) | LLM judge (gpt-4o) only; answers "flexible forms" — some numeric (the released `answer` field mixes JSON numbers and strings; the 15 MB oracle file carries the whole question set) | MIT |
| LoCoMo (`snap-research/locomo`, `data/locomo10.json`) | 10 conversations released (`locomo10.json`; the paper's full set is 50 conversations / 7,512 QA — single-hop 36%, multi-hop 14.6%, temporal 20.6%, open-domain 3.9%, adversarial 24.9%), exactly 1,986 QA in the release, of which 446 adversarial rows (22.5%) carry a null answer | two-speaker multi-session chats with `session_<n>_date_time` | `evidence` = dialog ids (human) | F1 after normalisation in the paper; answers are spans lifted from the conversation, so single-hop/temporal carry short factual answers | CC-BY-NC 4.0 |

Rejected before recon: CRAG (web QA, not personal memory — `r51-successor-conferral`).

## Frozen rules

- **Gradeability** is the answer-typed rule `r51` froze: `detect_qtype(answer) == "number"` under the vendored ATM
  matcher (`scripts/atm_bench/vendored`). **Casting frozen here:** a JSON-number answer is cast with `str()` before
  typing; a `null` or missing answer is untypeable and counted as abstention-shaped, never as `open_end`. A corpus
  whose answers the matcher cannot type is counted, not graded. No LLM judge in any verdict path.
- **Abstention share** is defined by the corpus's own label — LoCoMo category 5 (adversarial, null answer),
  LongMemEval the `_abs` id suffix — with ATM's `is_abstention` phrase list read beside it as a second reading that
  decides nothing.
- **Foldable unit**: one verdicted tick per gradeable question per pass; repeated passes are not evidence. The
  per-pass yield is named (`M-35`): ATM's was 195/198 = 0.985; the other two are taken at 1.0 (conservative — yield ≤ 1).
- **Band projection constant**: the fraction of verdicted ticks in the 0.7–0.9 band on an external corpus, from `r51b`'s
  read (**29/195 = 0.149**; those 29 realised 1.000), with `r49`'s owner-corpus rate (55/238 = 0.231) beside it; the
  projection uses the LOWER, **0.149**, and both are published.
- **Producer cost** is priced, not built: each conversation-shaped corpus needs a pkm transcript producer (one document
  per session, `Date` from the session timestamp, no participant identity beyond the corpus's own speaker labels), its
  own `questions.yaml` writer, and a manifest; the executor pass is priced at `r51b`'s measured $0.107/q.

## Criteria

- **Y0 (control, harness)**: `detect_qtype` over ATM-Bench's 1,013 released answers reproduces the paper's 360 / 139 / 514
  exactly (`r51`'s X3e read) — a mis-wired or mis-cast matcher turns it RED, and it is independent of the pooled outcome
  (a harness control under `G-3`, not an `M-36` ablation). RED → STOP, amend, no count is read.
- **Y1 (KILL, recon) — foreclosed at the frozen constant, and said so before download.** Pooled gradeable questions
  (ATM 198 + LongMemEval number-typed + LoCoMo number-typed) × the band constant < **385** → KILL. The answerable pool's
  ceiling is 198 + 500 + 1,542 = **2,240** (LoCoMo's 444 null-answer rows cannot type), so at 0.149 the ceiling projects
  **334 < 385 even if every answerable answer typed `number`**; at 0.231 the bar is 1,667 gradeable, 74% of the pool.
  Y1 therefore reads KILL by arithmetic on facts known before download. It is kept as the trigger of the frozen
  consequence, and the recon's information is Y1′–Y4.
- **Y1′ (sizing — the question `A-13` asked)**: the projected band rows at both constants, and the number of one-pass
  corpora of ATM's size (198 gradeable) needed to reach 385 at each — the price of the pooling route, published.
- **Y2 (recon)**: per corpus, the number-typed share and the abstention share (by label, with `is_abstention` beside
  it), the type × lane cross-tab (lane by `classify(question)`), and the count of questions whose evidence spans > 1
  session (multi-hop shape the single-document lattice never joins — `r09` arc).
- **Y3 (price)**: build cost in files and tests (producer + writer + manifest + tests, by analogy with
  `scripts/atm_bench/build_kb.py`); pass cost in $ at Y1's count; engine cost at K = 10 from `r51b`'s timing constant.
- **Y4 (disclosure)**: licence compatibility per corpus (MIT / CC-BY-NC) for an on-machine, never-redistributed read;
  what the pooled read would and would not say — three corpora of different shapes pooled into one band is a
  heterogeneity the owner-corpus table does not carry (`r51b`'s X3c′ is the first instance: one spawn's
  single-candidate rows carried every commit on ATM-Bench and none on the owner's corpus); and 385 itself assumes
  `r49`'s runner-up split rates (0.862 / 0.722) — ATM's 29 band rows realised 1.000, so rows of that shape carry no
  correctness contrast to separate, which bites only on a clear branch.
- **Controls before verdicts** (`M-36`): Y0 is read before Y1′–Y4 are computed; the build successor inherits the rule.

## Blind predictions

- **P1** LongMemEval number-typed ∈ [100, 200] of 500 (temporal-reasoning + knowledge-update carry dates/counts);
  LoCoMo number-typed ∈ [200, 500] of the 1,542 answerable (temporal + single-hop).
- **P2** pooled gradeable ∈ [498, 898] → projected band rows [74, 134] at 0.149 and [115, 207] at 0.231 — **Y1 KILLs
  at both**; Y1′ reads ≥ 13 ATM-sized corpora at 0.149 and ≥ 8 at 0.231.
- **P3** multi-session evidence on ≥ 40% of LongMemEval's non-abstention questions; ≥ 30% of LoCoMo's multi-hop.
- **P4′** ATM's `is_abstention` phrase list fires on < 50% of LongMemEval's 30 labelled abstention answers and on 0 of
  LoCoMo's 446 null answers (the label shares themselves — 6.0% and 22.5% — are facts, not predictions; see below).

## Consequence branches (frozen)

Y0 RED → STOP, amend. Y1 KILL → published with Y1′'s sizing; the pooling route is closed at one pass each; the supply
question returns to the owner's channels (the Claude verdict re-supply, `RULINGS` §5) and to proplang#26. Y1 clears →
a build pre-registration (its own `M-3`) for the transcript producer and the pooled run, sized by Y3, is named for the
ruled queue — not opened here. In every branch: nothing built, nothing deployed, no corpus content in tree, no §18
counter moves.

## Disclosure before the freeze

The fresh-eyes review of this document (2026-09-07, before merge) verified the public counts by downloading
`locomo10.json` and `longmemeval_oracle.json` into the review agent's scratchpad — not the recon's directory, nothing in
tree — and reported row counts, the abstention-by-label shares (446 / 1,986; 30 / 500), the JSON-number answer counts
(6; 32) and the null-answer count (444), withholding the multi-session share. Those quantities are facts above, not
predictions; the copies were deleted, and the recon downloads afresh at pinned revisions after this merges.

## Amendment log (blind, dated)

*(none yet)*
