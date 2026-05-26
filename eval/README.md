# eval/ — the answer-grounded eval set

The questions a great PA should answer about the owner's life, each with its **ground-truth
answer**. The runner (`scripts/run_eval.py`) checks whether the system can surface that answer,
with a citation — which is the mission ("ask anything about my life, with citations").

**Ground truth is the answer (the fact), not a source.** Earlier iterations pinned each question to
an `expected_source_id` and graded "is that source in top-k?". That proxy breaks as the corpus
grows: the same fact appears in many sources (an ID shows up in a contract, a chat, an email), so
adding data can *displace* a pinned source and fail a question whose answer is now *more* available.
Grading the fact instead is source-agnostic and growth-robust. (Supersedes the source-id
`phase1_questions.yaml` and the wiki-citation Phase-0 set, archived in the KB as
`questions.phase0.yaml`.)

## Where the real file lives

This repo holds only the **schema** (`questions.example.yaml`, fake). The real, PII-bearing set is
out of tree:

```
$LIFE_AGENT_KB/eval/questions.yaml   # the real questions + ground-truth answers
$LIFE_AGENT_KB/eval/eval_log.md      # the latest run's report (generated)
```

(`LIFE_AGENT_KB` default `$HOME/.life-agent/kb`; on this machine `~/yo/life-agent-kb`.)

## Schema

```yaml
questions:
  - id: q-001
    question: "<natural-language question, as a PA would be asked it>"
    subject: me | partner | n/a      # whose fact (n/a => the distractor check is skipped)
    answer: "<canonical ground-truth value>"   # "" = known-unanswerable (no value)
    answer_variants: ["<alt form>"]  # optional: 0123456789, 50,000/50000, 01/01/1990 …
    distractors: ["<value>"]         # optional: concrete confusable WRONG-subject values
    fuzzy: false                     # optional: true => sentence answer, graded by LLM judge
    search_queries: ["<lexical>"]    # FTS terms for the retrieval grader (keyword, not the question)
    mode_hint: coverage | extraction # optional: annotates an ABSENT answer
    notes: "<freeform>"
```

## Grading (`scripts/run_eval.py`)

Run in the pkm env (for `pkm.retrieval` + DuckDB):

```
uv run --project ~/git/pkm python scripts/run_eval.py --k 20
```

For each question it unions `search()` over `search_queries`, then checks the answer with a
**token-boundary matcher** (same Unicode tokenization as the FTS index — so `123456789` doesn't
match inside `1123456789`). Verdicts, classified by **failure mode**:

| verdict | meaning | the fix lives in |
|---|---|---|
| `PASS` | answer is in a top-k chunk | — |
| `RETRIEVAL_MISS` | answer is in the corpus but not top-k | retrieval/ranking |
| `ABSENT_COVERAGE` | answer nowhere in corpus, source not ingested | ingestion |
| `ABSENT_EXTRACTION` | answer nowhere in corpus, extraction destroyed it (OCR) | extraction/OCR |

`SUBJECT_CONFUSION` is reported as an **orthogonal flag** (a distractor — e.g. the partner's ID —
was retrieved in top-k): a question can be `PASS`+confused. It quantifies the "facts have subjects"
hazard now; once a synthesis layer exists it becomes a hard fail (the agent asserted the wrong
subject's value). The grading logic is in `scripts/eval_grading.py` (unit-tested).

`--synthesis` reserves the **end-to-end grader** (synthesized answer + citation-validity + subject,
LLM-judged) for Phase 2 / pkm-memory; it is inert today (we have retrieval, not synthesis).

## The dogfood loop (the living set)

The fixed set is a regression guard; the **dogfood week is the real eval**. Each real query — hit or
miss — graduates into `questions.yaml` as `(question, subject, answer, mode_hint)`, tagged by the
failure mode it exposed. The failures are the spec. Over time the set accretes from real use rather
than staying a frozen 20.
