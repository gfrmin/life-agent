# Scoreboard

`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` are value answers, escalated ones included, the esc- columns their escalated share; `cite-right`/`cite-wrong` are partial answers (the document named, not the value; right iff it attests the gold), neither right, wrong nor declined. `$/q` is the arm's calls at their declared prices, cache or no cache (the typed arm's applied probes at the menu's prices; the outside arm's recorded call). `U/q` is priced at the folded gauge u_right 1, u_wrong -5.1310, u_cite_right 0.5, u_cite_wrong -1, u_declined 0, lambda_usd 1.33108/$. A pinned set is one biased draw: a row whose U fell against the committed board is explained in its PR, not vetoed (rule 5; `--falls`). `log score` and `ECE` calibrate the typed arm's `p1` (see Calibration below); "—" where the archive records none.

| set | arm | rows | right | wrong | esc-right | esc-wrong | cite-right | cite-wrong | declined | $/q | U/q | s/q | log score | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| owner | typed | 104 | 41 (39.4%) | 0 (0.0%) | 0 | 0 | 26 | 0 | 37 (35.6%) | 0.0114 | +0.504 | — | -0.423 | 0.137 |
| owner-0920 | outside | 104 | 87 (83.7%) | 13 (12.5%) | 0 | 0 | 0 | 0 | 4 (3.8%) | 0.4135 | -0.355 | — | — | — |
| owner-0920 | router | 104 | 90 (86.5%) | 11 (10.6%) | 42 | 11 | 0 | 0 | 3 (2.9%) | 0.2357 | +0.009 | — | — | — |
| generated | typed | 212 | 84 (39.6%) | 4 (1.9%) | 0 | 0 | 52 | 1 | 71 (33.5%) | 0.0112 | +0.402 | — | -0.398 | 0.107 |
| generated-withheld | typed | 188 | 0 (0.0%) | 5 (2.7%) | 0 | 0 | 0 | 17 | 166 (88.3%) | 0.0043 | -0.233 | — | -0.853 | 0.467 |
| atm | typed | 198 | 26 (13.1%) | 5 (2.5%) | 0 | 0 | 0 | 0 | 167 (84.3%) | 0.0102 | -0.012 | — | — | — |
| sample | typed | 14 | 8 (57.1%) | 0 (0.0%) | 0 | 0 | 0 | 0 | 6 (42.9%) | 0.0119 | +0.556 | — | — | — |

## Calibration

The typed arm's `p1` (the probability it gave its leading candidate) against whether that candidate matched the gold, on every row with a candidate, whatever the act. `log score` is the mean log probability of the realised outcome (0 is perfect); `ECE` the bin-weighted gap between mean `p1` and the fraction right.

**`owner`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 3 | 0.069 | 0.333 |
| 0.1-0.2 | 9 | 0.154 | 0.444 |
| 0.2-0.3 | 6 | 0.264 | 0.500 |
| 0.3-0.4 | 6 | 0.338 | 0.500 |
| 0.4-0.5 | 1 | 0.492 | 0.000 |
| 0.5-0.6 | 7 | 0.579 | 0.857 |
| 0.6-0.7 | 8 | 0.643 | 0.875 |
| 0.7-0.8 | 8 | 0.739 | 0.875 |
| 0.8-0.9 | 16 | 0.853 | 0.812 |
| 0.9-1.0 | 39 | 0.940 | 1.000 |

103 scored · 1 with no candidate · 4 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

**`generated`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 5 | 0.052 | 0.200 |
| 0.1-0.2 | 8 | 0.126 | 0.500 |
| 0.2-0.3 | 15 | 0.252 | 0.400 |
| 0.3-0.4 | 13 | 0.342 | 0.538 |
| 0.4-0.5 | 3 | 0.453 | 0.667 |
| 0.5-0.6 | 6 | 0.564 | 0.500 |
| 0.6-0.7 | 21 | 0.659 | 0.952 |
| 0.7-0.8 | 21 | 0.733 | 0.905 |
| 0.8-0.9 | 20 | 0.858 | 0.950 |
| 0.9-1.0 | 86 | 0.952 | 0.953 |

198 scored · 14 with no candidate · 15 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

**`generated-withheld`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 5 | 0.052 | 0.000 |
| 0.1-0.2 | 7 | 0.145 | 0.000 |
| 0.2-0.3 | 11 | 0.236 | 0.000 |
| 0.3-0.4 | 7 | 0.345 | 0.000 |
| 0.4-0.5 | 1 | 0.497 | 0.000 |
| 0.5-0.6 | 4 | 0.566 | 0.000 |
| 0.6-0.7 | 12 | 0.672 | 0.000 |
| 0.7-0.8 | 7 | 0.718 | 0.000 |
| 0.8-0.9 | 3 | 0.846 | 0.000 |
| 0.9-1.0 | 4 | 0.955 | 0.000 |

61 scored · 127 with no candidate · 61 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

Not scored:

- `live` — the live stream since the reset; scored from J4

What each row is:

- **`owner`** — The owner's 104 questions, typed arm only, re-run 2026-09-30 with the `cite` row (partial answers: the document named, not the value) against the corpus pin full-2026-06-11 (catalogue digest 03d1b09c…): 34 right / 0 wrong / 29 cite-right / 0 cite-wrong / 41 declined, list price $1.32 (the menu's prices for the probes applied), metered $0 because every call replayed from the cache of the cold run earlier the same day. Calibration is the archive's own (`typed.p1`): 103 scored, mean log score -0.474, ECE 0.153. Replaces the same day's row without the cite row (43/0/61, the earlier draw): 34 of its 43 rights are right again, 9 became right pointers (a cite pre-empts a value answer where the document's mass is between the cite row's and the respond row's crossing), and 20 of its declines became right pointers; nothing else moved. The 29 cites name a document at `p1` 0.59-0.89 and every one attests the gold (26 with the leading candidate correct, 3 with it wrong but the document right). 24 of the 41 declines still had the correct leader. The outside and router rows for this set are the frozen recordings under `owner-0920`.
- **`owner-0920`** — FROZEN RECORDINGS from 2026-09-20, the owner's 104 questions (corpus pin full-2026-06-11): the outside arm is the live deliberative rung's ANSWER line at the cost the call recorded, graded by exact match (87 right / 13 wrong / 4 declined). The router row recombines that OUTSIDE arm with the 2026-09-20 typed arm (48/0/56), NOT with today's `owner/typed` row: typed where that asserted, otherwise the outside answer, at the sum of both costs. Neither row has been re-run; the typed arm of this archive is not a board row (see `owner`). Both were priced at their declared prices on one grader with J1's host Bayes act; they replace run 18 (the Julia daemon, 2026-08-26, paired-gate-20260826T083356-strict-priced.jsonl).
- **`generated`** — The generated golden set: 212 verbatim point-fact questions extracted from the owner's corpus by the generator (claude-haiku-4-5-20251001, prompt sha ea86a53553e58005; questions file sha256 2a548ef4239c4347 in $LIFE_AGENT_KB/eval/questions_generated.yaml). Re-run 2026-09-30 with the `cite` row (partial answers: the document named, not the value) against the corpus pin full-2026-06-11 (catalogue digest 03d1b09c…): 71 right / 4 wrong / 44 cite-right / 0 cite-wrong / 93 declined, list price $2.57, metered $0 because every call replayed from the cache of the 2026-09-20 cold run. Calibration is the archive's own (`typed.p1`): 198 scored, mean log score -0.428, ECE 0.142; leaders given 0.6-0.9 were right about 96% of the time (64 rows), leaders given under 0.4 about 43% (51 rows), the top bin 0.947 stated against 0.946 realised. Every question's answer is in the corpus by construction, so this reads calibration on answerable questions only. Replaces the same day's row without the cite row (81/4/127): 71 of its 81 rights are right again, 10 became right pointers, 34 of its 127 declines became right pointers, and all 4 wrongs are wrong again (a wrong value at `p1` above the respond crossing is not reached by the cite row). The 44 cites name a document at `p1` 0.41-0.89 and every one attests the gold (41 with the leading candidate correct, 3 with it wrong but the document right); predicted from the captured decide states before the run: 74/4 + 40 cite-right / 2 cite-wrong / 88 declined. 48 of the 93 declines still had the correct leader, 14 had no candidate.
- **`generated-withheld`** — The generated set's questions re-asked with their answers ABSENT: for each question, every document with any chunk the grader's matcher finds the gold (or a variant) in, plus the question's own source, is withheld from retrieval, and the deliberative rung is off (`eval.run --withhold-source`, `eval/withheld.py`). Declining is right, an assertion is wrong, and an assertion matching the gold would be a leak (none). 188 of the 212 questions; the other 24 were skipped because more than 500 documents attest their answer. Re-run 2026-09-30 with the `cite` row on the corpus pin full-2026-06-11: 0 right / 3 wrong / 0 cite-right / 11 cite-wrong / 174 declined, 0 leaks, 61 rows with a candidate (mean `p1` 0.445). A cite here is wrong by construction (every attesting document is withheld), so the 11 are the price of the row on questions the corpus cannot answer: 9 were declines on the same day's row without it (0/5/183), 2 were wrong values that became wrong pointers, and 3 wrong values remain. At the folded gauge the row's U falls 0.738 over the 188 (11 pointers at -1 against 2 wrongs at -5.131 saved), predicted 13 wrong pointers from the captured states. Wrong here is the cost of answering a question whose answer is not in the corpus; it reads calibration on unanswerable questions, where the answerable sets read it only on answerable ones.
- **`atm`** — Somebody else's corpus and somebody else's questions — the only row here whose difficulty this project did not choose. ATM-Bench at pinned revision 78e826dc07e97466b2f54443831ef9a83ab8b27c, built into its own KB root by `make sets` (6742 emails; CC-BY-NC, so it stays on the machine that built it and this row names its root by environment variable rather than a path). 198 of the 381 questions: the build marks the other 183 `fuzzy`, graded by resemblance, and a judge-graded row is not on this board. J1's host Bayes act, COLD on a second machine 2026-09-20 at the owner's folded gauge and the menu's declared prices ($2.02 for the 198; metered $3.80). 26 right / 5 wrong / 167 declined, nothing censored — every gold chunk was present, so the declines are the act's and not the catalogue's. **Read the U/q as a floor, not an error rate.** All five wrongs were re-asked through the same bridge and NONE is an invention: each named the gold fact in another surface form (gold `June 30, 2024.` against `June 30th, 2024`; gold `from 9:30am to 10:30am.` against `9:30am to 10:30am`; one, `July 4th` for `July 4th, 2025.`, dropped the year). Exact match is the declared grader and this row is scored by it unaltered, but ATM's gold is the dataset author's prose, not a span lifted from the document: only 77 of the 198 golds appear verbatim in their own cited email, so 121 of these questions do not meet this project's own MVP precondition. Re-cutting the set on that precondition is an eval-question change and is the owner's to take. First pin either way: the baseline, no incumbent.
- **`sample`** — The one row a stranger can reproduce from a clone. The bundled synthetic corpus (examples/sample-corpus, 8 documents, the fictional Ada Lovelace) built by scripts/bootstrap-sample.sh; 14 questions generated from it by the same `make golden` recipe the owner's set uses (eval/sample/questions.yaml, sha256 9a24703502...), answered cold through a bridge over that sandbox. Synthetic by construction, so both the questions and the archive live IN the repo and `root: repo` scores them with no $LIFE_AGENT_KB at all. The gauge is the shipped example folded with no evidence (the declared prior, u_wrong -9, bar 0.90) and the gather row is config/gather-row.example.json, because a fresh KB has fitted neither — which is exactly the configuration a stranger runs. 8 right / 0 wrong / 6 declined. Re-running it needs an API key; scoring the pinned bytes needs nothing.
