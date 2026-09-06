# r52 — the corpus-pooling recon — READ: **Y1 KILL at both band constants, sized**

**2026-09-07 · $0 · repo `24d69bd` (the pre-registration's merge, PR #185; read on the same tree) · corpora pinned
on-machine, never in tree: LongMemEval-cleaned at HF revision `98d7416c24c778c2fee6e6f3006e7a073259d48f` (the 15 MB
oracle file; the S/M haystacks carry the same 500 questions), LoCoMo at commit `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376`
(`locomo10.json`, sha256 `79fa87e9…`), ATM-Bench at `r51`'s pin · vendored evaluator `ef4e5dff`.** Pre-registration
frozen at `24d69bd` after one review revision (its own §"Disclosure before the freeze"). Every number here is a count or
an aggregate; no question, answer, session line or id from any corpus appears in this document.

> **Verdict.** **Y0 PASS** — the vendored `detect_qtype` over ATM-Bench's 1,013 released answers reads 360 / 139 / 514,
> the paper's split exactly. **Y1 KILL at both constants**, as the pre-registration said it must: the pooled gradeable
> supply is **437** questions (ATM 198 + LongMemEval 142 + LoCoMo 97), projecting **65** band rows at 0.149 and **101** at
> 0.231 against the bar of 385. **Y1′:** reaching 385 in one pass each would take **14** corpora of ATM's size at 0.149,
> **9** at 0.231. The pooling route is closed at one pass each; what to build next is live for the owner
> (`RULINGS` §5, `conferrals/r52-successor-conferral.md`).

## 1. What was asked

`A-13`'s second half: with `r51b` read, does pooling public labelled corpora reach the ≈385 band rows `GD-28` priced as
binding on every evidence-side lever on §18's bar — counted in the unit the instrument folds (`M-35`: one verdicted tick
per mechanically gradeable question per pass) — and what does the route cost? Three candidates: ATM-Bench's email
subset (read by `r51b`), LongMemEval-cleaned, LoCoMo's released ten conversations.

## 2. The recon as it ran

- **Downloads after the freeze merged** (18:29–18:40 UTC): `snapshot_download` of the oracle file + README, the LoCoMo
  file by raw fetch at the `main` commit; revisions recorded beside the files in the external-corpora root
  (machine-specific, named in the session memory, not here; not a git tree; under no pushed path). The first pull matched `*.json` and began the 2.7 GB M-haystack
  file the recon does not need; it was stopped at 449 MB, the partial cache and the 277 MB S file deleted, the pattern
  narrowed to the oracle file (deviation 1).
- **Controls before verdicts:** Y0 was read first, in the same script, and the script exits before any count if it is RED.
- **Casting as frozen:** JSON-number answers cast with `str()` (LongMemEval 32, LoCoMo 6 — five of the 38, all four-digit,
  type `open_end` after the cast; the rule as frozen). LoCoMo's 444 category-5 rows carry no `answer` key at all (not a
  JSON null) and are counted as abstention-shaped, never typed.
- **Lane** by `answer_shape_census.classify(question)`; **abstention** by the corpus's own label with ATM's
  `is_abstention` beside it; **multi-session evidence** = more than one distinct session among the question's evidence
  ids (`answer_session_ids`; LoCoMo's `D<session>:<turn>` ids — four LoCoMo entries pack several ids in one string and
  are split).

## 3. Y0 — the harness control

`detect_qtype` over the 1,013 released ATM-Bench answers: number **360** · list_recall **139** · open_end **514** — the
paper's split reproduced exactly (`r51`'s X3e, re-read on this tree). PASS.

## 4. Y2 — the corpora, counted

| corpus | rows | abstention by label | `is_abstention` fires | answerable | `number`-typed | share | lanes on answerable (exact / quantity / set / threshold) | `number` × lane (exact / quantity / other) | multi-session evidence |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| ATM-Bench email subset (`r51`) | 381 | 14 (0.037) | — | 381 | 198 | 0.520 | 119 / 79 on the 198 (`r51`) | — | single-document by construction |
| LongMemEval-cleaned (oracle) | 500 | 30 (0.060; `_abs` ids) | 0 / 30 labelled · 0 / 500 | 470 | **142** | 0.302 | 249 / 213 / 6 / 2 | 15 / 125 / 2 | **300 / 470 = 0.638** |
| LoCoMo (released ten) | 1,986 | 446 (0.225; category 5, 444 without an `answer` key) | 0 / 446 `adversarial_answer` distractors · 0 / 1,542 | 1,542 | **97** | 0.063 | 1,485 / 40 / 13 / 4 | 90 / 7 / 0 | 334 / 1,542 = 0.217 |

- *The "answerable" column* excludes LongMemEval's 30 labelled abstentions and LoCoMo's 444 rows without an `answer`
  (its two category-5 rows that carry one stay, neither number-typed); ATM's 14 abstentions carry answers and stay.
- **LongMemEval's numbers hit P1's interval but not its ground**: they are counts, not dates — 4 of the 142 carry a
  month name. By `question_type` (denominators: answerable rows), multi-session 86 of 121, knowledge-update 24 of 72,
  single-session-user 16 of 64, temporal-reasoning 14 of 127, single-session-assistant 2 of 56, single-session-preference
  0 of 30. The lane regex reads `quantity` on 125 of the 142 (0.880) — the reverse of
  ATM's 0.40.
- **LoCoMo's numbers are almost all one category**: 86 of 97 in category 2, 7 in category 1, 4 in category 4. The
  release's own evaluator (`task_eval/evaluation.py`, lines 205–220 at the pinned commit) names category 1 multi-hop
  and category 5 adversarial, and names {2, 3, 4} only as a set (single-hop, temporal, open-domain); their assignment
  here — 2 temporal (85 of its 86 numbers carry a month name), 3 open-domain, 4 single-hop — rests on the release's
  shares against the paper's Table 5 and on the answer shapes. Category 1 spans more than one session on 270 of 282. The lane regex reads `exact` on 90 of the 97 numbers.
- **The abstention gold differs by corpus, and ATM's phrase list matches neither**: LongMemEval's 30 labelled
  abstentions are free-text refusals of the corpus's own shape (ATM's seven phrases fire on 0 of 30); LoCoMo's 446
  category-5 rows carry no gold answer but an `adversarial_answer` distractor each (439 distinct; the list fires on 0 of
  446), and the release's evaluator grades them by a two-phrase output test, one of whose phrases is on ATM's list. The
  NONE atom's public gold is a label on LongMemEval and an output-phrase test on LoCoMo — one benchmark's phrase list
  does not transfer.

## 5. Y1 and Y1′ — the supply, in the foldable unit

Pooled gradeable = 198 + 142 + 97 = **437** questions → at yield 1.0 for the two new corpora (ATM's was 195/198), band
rows **65.0** at 0.149 and **101.0** at 0.231, against **385**: **KILL at both** — and at the frozen constant the KILL was
foreclosed before download (the answerable pool's ceiling, 2,210 here, projects 329). **Y1′:** one ATM-sized corpus yields
29.4 band rows at 0.149 (45.8 at 0.231), so 385 needs **14** such corpora at the frozen constant, **9** at the owner
corpus's — one pass each, no repeats (`M-35`). The route does not reach the bar by pooling what exists.

## 6. Y3 — the price, had it cleared

- **Build**, by analogy with the ATM build: `scripts/atm_bench/build_kb.py` (284 lines) + `scripts/gold_verdicts.py`
  (215) with 15 + 14 tests (249 + 254 lines) — a transcript producer per conversation-shaped corpus (one document per
  session, `Date` from the session timestamp, speaker labels only), a questions writer and a manifest each: roughly one
  ATM-sized build per corpus, two builds.
- **Pass**: by the frozen letter ("at Y1's count") 437 × $0.107 = **$47**; on `r51b`'s basis — the pass answers every
  answerable question of a corpus to verdict its gradeable ones — the two new corpora's 2,012 answerable rows price at
  **$215** (LongMemEval $50, LoCoMo $165); ATM's 381 were paid in `r51b` (deviation 5).
- **Engine**: K = 10 on 437 ticks — linear scaling of `r51b`'s A3 pair (33.2 min per 195 ticks; 43.7 with its third
  variant) gives **≥ 74 min** (98 with three variants), a floor (per-tick cost is super-linear in fold depth: 0.172 →
  0.472 s from 50 to 195 ticks).

## 7. Y4 — disclosure

- **Licences**: LongMemEval-cleaned MIT; LoCoMo CC BY-NC 4.0; ATM-Bench data CC-BY-NC 4.0 — all compatible with an
  on-machine, never-redistributed research read; nothing from any of them enters the public repo.
- **What a pooled read would say**: three corpora of different shapes in one band — paraphrased emails, user–assistant
  chats, two-speaker diaries — is a heterogeneity the owner-corpus table does not carry; `r51b`'s X3c′ (one spawn's
  single-candidate rows carrying every commit) is the first instance of a corpus-specific cell.
- **385 assumes `r49`'s runner-up split** (0.862 / 0.722 on the owner's band); ATM's 29 band rows realised 1.000 and
  carry no correctness contrast to separate — a clear branch would have had to say so; none opened.

## 8. Blind predictions, scored

| # | prediction | read | disposition |
|---|---|---|---|
| P1 | LongMemEval number-typed ∈ [100, 200] of 500; LoCoMo ∈ [200, 500] of 1,542 | 142; 97 | CONFIRMED; **REFUTED** (half the floor — the numbers live in one category, 16% of the release) |
| P2 | pooled ∈ [498, 898] → band [74, 134] / [115, 207] → Y1 KILLs at both; Y1′ ≥ 13 / ≥ 8 | 437 → 65 / 101; 14 / 9 | interval **REFUTED** (below); KILL clause and sizing CONFIRMED |
| P3 | multi-session evidence ≥ 40% of LongMemEval's answerable; ≥ 30% of LoCoMo's multi-hop | 0.638; 0.957 (category 1, multi-hop by the release's evaluator) | CONFIRMED; CONFIRMED |
| P4′ | `is_abstention` fires on < 50% of LongMemEval's 30 labelled abstentions and on 0 of LoCoMo's null answers | 0 / 30; LoCoMo has no null answer to fire on (the 444 have no `answer` key) — 0 / 446 on their `adversarial_answer` distractors | CONFIRMED; CONFIRMED vacuously (its object does not exist — the distractor reading is the substantive one) |

## 9. Consequence enacted

The frozen Y1 KILL branch: published with Y1′'s sizing; the pooling route is closed at one pass each; the supply
question returns to the owner's channels (the Claude verdict re-supply — `RULINGS` §5) and to proplang#26 (the engine-side
demand, where `r51b`'s corroboration is posted). Nothing built, nothing deployed, no corpus content in tree, no §18
counter moves. **The next build is the residue class** (`RULINGS` §5: what to build when the ruled queue empties) —
posed with priced options in `conferrals/r52-successor-conferral.md`.

## 10. Deviations, disclosed

1. **The first download pulled the wrong files.** The pattern `*.json` matched LongMemEval's 277 MB S and 2.7 GB M
   haystack files; the run was stopped at 449 MB of the M file, both deleted, and the pattern narrowed to the oracle file.
   No count was taken from them. A `pkill` on the script's name also killed the shell issuing it (the pattern matched its
   own command line); the retry used a self-excluding pattern.
2. **The review verified counts from its own downloads before the freeze merged** (the pre-registration's own disclosure
   section): row counts, label shares, JSON-number and null counts were known before the freeze and are stated there as
   facts; the multi-session share was withheld and is read here for the first time. The reviewer's copies were deleted;
   the recon's downloads are the pinned ones above.
3. **LoCoMo's category labels are half read, half inferred**: the release's evaluator names 1 (multi-hop) and 5
   (adversarial); {2, 3, 4} are assigned here from shares and answer shapes (§4). P3's LoCoMo half is scored on the read
   label.
4. **P2's interval was set from P1's**, so both miss together; the KILL clause and the sizing do not depend on them.
5. **Y3's pass price is published on two bases** — the frozen letter ($47 at Y1's count) and `r51b`'s answer-everything
   basis over the two new corpora ($215); the first render priced 2,210 rows including ATM's already-answered 198 ($236)
   and was corrected at review.
6. **The first render's multi-session count took the first id of a packed evidence entry**; four LoCoMo entries pack
   several ids and are split now: category 1 269 → 270, category 3 31 → 34, overall 330 → 334. No prediction moves.
