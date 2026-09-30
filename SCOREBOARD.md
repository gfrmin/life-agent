# Scoreboard

`python -m eval.score --write`. Counts over each set's rows; `right`/`wrong` are value answers, escalated ones included, the esc- columns their escalated share; `cite-right`/`cite-wrong` are partial answers (the document named, not the value; right iff it attests the gold), neither right, wrong nor declined. `$/q` is the arm's calls at their declared prices, cache or no cache (the typed arm's applied probes at the menu's prices; the outside arm's recorded call). `U/q` is priced at the folded gauge u_right 1, u_wrong -5.1310, u_cite_right 0.5, u_cite_wrong -1, u_declined 0, lambda_usd 1.33108/$. A pinned set is one biased draw: a row whose U fell against the committed board is explained in its PR, not vetoed (rule 5; `--falls`). `log score` and `ECE` calibrate the typed arm's `p1` (see Calibration below); "—" where the archive records none.

| set | arm | rows | right | wrong | esc-right | esc-wrong | cite-right | cite-wrong | declined | $/q | U/q | s/q | log score | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| owner | typed | 104 | 43 (41.3%) | 0 (0.0%) | 0 | 0 | 0 | 0 | 61 (58.7%) | 0.0136 | +0.395 | — | -0.464 | 0.146 |
| owner-0920 | outside | 104 | 87 (83.7%) | 13 (12.5%) | 0 | 0 | 0 | 0 | 4 (3.8%) | 0.4135 | -0.355 | — | — | — |
| owner-0920 | router | 104 | 90 (86.5%) | 11 (10.6%) | 42 | 11 | 0 | 0 | 3 (2.9%) | 0.2357 | +0.009 | — | — | — |
| generated | typed | 212 | 81 (38.2%) | 4 (1.9%) | 0 | 0 | 0 | 0 | 127 (59.9%) | 0.0124 | +0.269 | — | -0.425 | 0.136 |
| generated-withheld | typed | 188 | 0 (0.0%) | 5 (2.7%) | 0 | 0 | 0 | 0 | 183 (97.3%) | 0.0042 | -0.142 | — | -0.786 | 0.445 |
| atm | typed | 198 | 26 (13.1%) | 5 (2.5%) | 0 | 0 | 0 | 0 | 167 (84.3%) | 0.0102 | -0.012 | — | — | — |
| sample | typed | 14 | 8 (57.1%) | 0 (0.0%) | 0 | 0 | 0 | 0 | 6 (42.9%) | 0.0119 | +0.556 | — | — | — |

## Calibration

The typed arm's `p1` (the probability it gave its leading candidate) against whether that candidate matched the gold, on every row with a candidate, whatever the act. `log score` is the mean log probability of the realised outcome (0 is perfect); `ECE` the bin-weighted gap between mean `p1` and the fraction right.

**`owner`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 4 | 0.076 | 0.500 |
| 0.1-0.2 | 7 | 0.145 | 0.571 |
| 0.2-0.3 | 8 | 0.256 | 0.500 |
| 0.3-0.4 | 7 | 0.316 | 0.571 |
| 0.4-0.5 | 2 | 0.483 | 0.500 |
| 0.5-0.6 | 7 | 0.577 | 0.857 |
| 0.6-0.7 | 6 | 0.647 | 0.833 |
| 0.7-0.8 | 11 | 0.746 | 0.818 |
| 0.8-0.9 | 20 | 0.851 | 0.900 |
| 0.9-1.0 | 31 | 0.944 | 1.000 |

103 scored · 1 with no candidate · 4 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

**`generated`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 5 | 0.051 | 0.200 |
| 0.1-0.2 | 9 | 0.119 | 0.444 |
| 0.2-0.3 | 18 | 0.253 | 0.444 |
| 0.3-0.4 | 20 | 0.336 | 0.450 |
| 0.4-0.5 | 1 | 0.418 | 0.000 |
| 0.5-0.6 | 7 | 0.552 | 0.857 |
| 0.6-0.7 | 29 | 0.649 | 0.931 |
| 0.7-0.8 | 19 | 0.748 | 1.000 |
| 0.8-0.9 | 13 | 0.849 | 1.000 |
| 0.9-1.0 | 77 | 0.947 | 0.948 |

198 scored · 14 with no candidate · 15 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

**`generated-withheld`**

| p1 bin | n | mean p1 | right |
|---|---:|---:|---:|
| 0.0-0.1 | 5 | 0.051 | 0.000 |
| 0.1-0.2 | 11 | 0.153 | 0.000 |
| 0.2-0.3 | 7 | 0.255 | 0.000 |
| 0.3-0.4 | 7 | 0.325 | 0.000 |
| 0.4-0.5 | 2 | 0.491 | 0.000 |
| 0.5-0.6 | 6 | 0.556 | 0.000 |
| 0.6-0.7 | 14 | 0.652 | 0.000 |
| 0.7-0.8 | 2 | 0.732 | 0.000 |
| 0.8-0.9 | 4 | 0.837 | 0.000 |
| 0.9-1.0 | 3 | 0.964 | 0.000 |

61 scored · 127 with no candidate · 61 truth absent from the candidates (scored, the leader is wrong) · 0 clamped

Not scored:

- `live` — the live stream since the reset; scored from J4

What each row is:

- **`owner`** — The owner's 104 questions, typed arm only, re-run 2026-09-30 on master 4912b08 against the corpus pin full-2026-06-11 (catalogue digest 03d1b09c…): 43 right / 0 wrong / 61 declined, list price $1.41 (the menu's prices for the probes applied), metered $0.19 on this run because most calls replayed from the cache of an earlier cold run the same day (which metered $5.49). Calibration is the archive's own (`typed.p1`): 103 scored, mean log score -0.464, ECE 0.146. Replaces the 2026-09-20 typed row (48/0/56 at $1.44): 43 of its 48 rights are right again; the other 5 went right -> declined, the same probes applied and the leading candidate correct, `p1` ending between 0.47 and 0.78, below the bar. They come from one fresh cold draw of the model calls (the earlier run today, now cached); the pinned run was a different draw, and no code change explains them. 41 of the 61 declines had the correct leader. The outside and router rows for this set are the frozen recordings under `owner-0920`.
- **`owner-0920`** — FROZEN RECORDINGS from 2026-09-20, the owner's 104 questions (corpus pin full-2026-06-11): the outside arm is the live deliberative rung's ANSWER line at the cost the call recorded, graded by exact match (87 right / 13 wrong / 4 declined). The router row recombines that OUTSIDE arm with the 2026-09-20 typed arm (48/0/56), NOT with today's `owner/typed` row: typed where that asserted, otherwise the outside answer, at the sum of both costs. Neither row has been re-run; the typed arm of this archive is not a board row (see `owner`). Both were priced at their declared prices on one grader with J1's host Bayes act; they replace run 18 (the Julia daemon, 2026-08-26, paired-gate-20260826T083356-strict-priced.jsonl).
- **`generated`** — The generated golden set: 212 verbatim point-fact questions extracted from the owner's corpus by the generator (claude-haiku-4-5-20251001, prompt sha ea86a53553e58005; questions file sha256 2a548ef4239c4347 in $LIFE_AGENT_KB/eval/questions_generated.yaml). Re-run 2026-09-30 on master 4912b08 against the corpus pin full-2026-06-11 (catalogue digest 03d1b09c…): 81 right / 4 wrong / 127 declined, list price $2.63, metered $0 because every call replayed from the cache of the 2026-09-20 cold run. Calibration is the archive's own (`typed.p1`): 198 scored, mean log score -0.425, ECE 0.136; leaders given 0.6-0.9 were right about 96% of the time (61 rows), leaders given under 0.4 about 44% (52 rows), the top bin 0.947 stated against 0.948 realised; 79 of the 127 declines had the correct leader. Every question's answer is in the corpus by construction, so this reads calibration on answerable questions only. Replaces the 2026-09-20 row (85/4/123): 81 of its 85 rights are right again and all 4 wrongs are wrong again. 4 went right -> declined with nothing applied: they began with nothing extracted and were answered by the fixed rescue sequence; since PR #206 (ruling 6) a state with no candidate is decided by the argmax, which at today's gauge abstains. 5 former declines that had reached candidates through that rescue are now declines with nothing applied, for the same reason.
- **`generated-withheld`** — The generated set's questions re-asked with their answers ABSENT: for each question, every document with any chunk the grader's matcher finds the gold (or a variant) in, plus the question's own source, is withheld from retrieval, and the deliberative rung is off (`eval.run --withhold-source`, `eval/withheld.py`). Declining is right, an assertion is wrong, and an assertion matching the gold would be a leak (none). 188 of the 212 questions; the other 24 were skipped because more than 500 documents attest their answer. Run 2026-09-30 on the corpus pin full-2026-06-11 (the 188 rows are one archive: 163 from the first run plus 25 re-run after the attestation finder was fixed, its index-based proposal having missed every attestation of a gold holding a stopword token): 0 right / 5 wrong / 183 declined, 0 leaks, 61 rows with a candidate (mean `p1` 0.445). Wrong here is the cost of answering a question whose answer is not in the corpus; it reads calibration on unanswerable questions, where the answerable sets read it only on answerable ones.
- **`atm`** — Somebody else's corpus and somebody else's questions — the only row here whose difficulty this project did not choose. ATM-Bench at pinned revision 78e826dc07e97466b2f54443831ef9a83ab8b27c, built into its own KB root by `make sets` (6742 emails; CC-BY-NC, so it stays on the machine that built it and this row names its root by environment variable rather than a path). 198 of the 381 questions: the build marks the other 183 `fuzzy`, graded by resemblance, and a judge-graded row is not on this board. J1's host Bayes act, COLD on a second machine 2026-09-20 at the owner's folded gauge and the menu's declared prices ($2.02 for the 198; metered $3.80). 26 right / 5 wrong / 167 declined, nothing censored — every gold chunk was present, so the declines are the act's and not the catalogue's. **Read the U/q as a floor, not an error rate.** All five wrongs were re-asked through the same bridge and NONE is an invention: each named the gold fact in another surface form (gold `June 30, 2024.` against `June 30th, 2024`; gold `from 9:30am to 10:30am.` against `9:30am to 10:30am`; one, `July 4th` for `July 4th, 2025.`, dropped the year). Exact match is the declared grader and this row is scored by it unaltered, but ATM's gold is the dataset author's prose, not a span lifted from the document: only 77 of the 198 golds appear verbatim in their own cited email, so 121 of these questions do not meet this project's own MVP precondition. Re-cutting the set on that precondition is an eval-question change and is the owner's to take. First pin either way: the baseline, no incumbent.
- **`sample`** — The one row a stranger can reproduce from a clone. The bundled synthetic corpus (examples/sample-corpus, 8 documents, the fictional Ada Lovelace) built by scripts/bootstrap-sample.sh; 14 questions generated from it by the same `make golden` recipe the owner's set uses (eval/sample/questions.yaml, sha256 9a24703502...), answered cold through a bridge over that sandbox. Synthetic by construction, so both the questions and the archive live IN the repo and `root: repo` scores them with no $LIFE_AGENT_KB at all. The gauge is the shipped example folded with no evidence (the declared prior, u_wrong -9, bar 0.90) and the gather row is config/gather-row.example.json, because a fresh KB has fitted neither — which is exactly the configuration a stranger runs. 8 right / 0 wrong / 6 declined. Re-running it needs an API key; scoring the pinned bytes needs nothing.
