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
| LongMemEval (`xiaowu0162/longmemeval-cleaned`, MIT) | **500** questions (S/M/Oracle are one question set with three haystacks); 7 types incl. ~30 abstention | user–assistant chat sessions with dates; Oracle carries only the evidence sessions | `answer_session_ids` + per-turn `has_answer` (human) | LLM judge (gpt-4o) only; answers "flexible forms" — some numeric (the HF viewer's `answer` column mixes int and str) | MIT |
| LoCoMo (`snap-research/locomo`, `data/locomo10.json`) | 10 conversations released (`locomo10.json`; the paper's full set is 50 conversations / 7,512 QA — single-hop 36%, multi-hop 14.6%, temporal 20.6%, open-domain 3.9%, adversarial 24.9%), ≈1,986 QA in the release (count at recon) | two-speaker multi-session chats with `session_<n>_date_time` | `evidence` = dialog ids (human) | F1 after normalisation in the paper; answers are spans lifted from the conversation, so single-hop/temporal carry short factual answers | CC-BY-NC 4.0 |

Rejected before recon: CRAG (web QA, not personal memory — `r51-successor-conferral`).

## Frozen rules

- **Gradeability** is the answer-typed rule `r51` froze: `detect_qtype(answer) == "number"` under the vendored ATM
  matcher (`scripts/atm_bench/vendored`), applied to every candidate's answer field unchanged. A corpus whose answers the
  matcher cannot type is counted, not graded. No LLM judge in any verdict path.
- **Foldable unit**: one verdicted tick per gradeable question per pass. Repeated passes are not evidence.
- **Band projection constant**: the fraction of verdicted ticks landing in the 0.7–0.9 band on an external corpus is
  taken from `r51b`'s read (**29/195 = 0.149**; those 29 realised 1.000 at mean leader credence 0.824), with `r49`'s
  owner-corpus rate (55/238 = 0.231) beside it as the second point; the projection uses the LOWER of the two, **0.149**.
- **Producer cost** is priced, not built: each conversation-shaped corpus needs a pkm transcript producer (one document
  per session, `Date` from the session timestamp, no participant identity beyond the corpus's own speaker labels), its
  own `questions.yaml` writer, and a manifest; the executor pass is priced at `r51b`'s measured $/q ($0.107).

## Criteria

- **Y1 (KILL, recon)**: pooled gradeable questions (ATM 198 + LongMemEval number-typed + LoCoMo number-typed) ×
  the band projection constant < **385** → KILL: pooling cannot reach the separation supply in one pass each; report
  and stop. (Predicted: this is close — see P1.)
- **Y2 (recon)**: per corpus, the number-typed share and the abstention share (via `is_abstention`), the type × lane
  cross-tab (lane by `classify(question)`), and the count of questions whose evidence spans > 1 session (multi-hop
  shape the single-document lattice never joins — `r09` arc).
- **Y3 (price)**: build cost in files and tests (producer + writer + manifest + tests, by analogy with
  `scripts/atm_bench/build_kb.py`); pass cost in $ at Y1's count; engine cost at K = 10 from `r51b`'s timing constant.
- **Y4 (disclosure)**: licence compatibility per corpus (MIT / CC-BY-NC) for an on-machine, never-redistributed read;
  what the pooled read would and would not say (three corpora of different shapes pooled into one band is a
  heterogeneity the owner-corpus table does not carry — named, not resolved here; `r51b`'s X3c′ is the first instance:
  the candidate-count family, inert on the owner's corpus, carried every commit on ATM-Bench).
- **Controls before verdicts** (`M-36`): the recon's only KILL is Y1 and it is a count, but the rule is stated so the
  build successor inherits it — no verdict rule is applied before every pre-registered control has been read.

## Blind predictions

- **P1** LongMemEval number-typed ∈ [100, 200] of 500 (temporal-reasoning + knowledge-update carry dates/counts);
  LoCoMo number-typed ∈ [200, 500] of the ≈1,986 released (temporal + single-hop; the adversarial 25% are unanswerable by design and count as abstention-shaped).
- **P2** pooled gradeable ∈ [500, 900]; at the band constant 0.149 the projected band rows ∈ [75, 134] — **Y1 KILLs**
  (even at `r49`'s 0.231 the range is [116, 208], still under 385).
- **P3** multi-session evidence on ≥ 40% of LongMemEval's non-abstention questions; ≥ 30% of LoCoMo's multi-hop.
- **P4** neither corpus's abstention share exceeds 10%.

## Consequence branches (frozen)

Y1 KILL → published; the pooling route is closed at one pass each; the supply question returns to the owner's channels
(the Claude verdict re-supply, `RULINGS` §5) and to proplang#26. Y1 clears → a build pre-registration (its own `M-3`)
for the transcript producer and the pooled run, sized by Y3, is named for the ruled queue — not opened here. In every
branch: nothing built, nothing deployed, no corpus content in tree, no §18 counter moves.

## Amendment log (blind, dated)

*(none yet)*
