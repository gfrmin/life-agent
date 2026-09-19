# The answer VOI executor — design draft

Status: **draft for owner review** (2026-06-18). Not the discovery of an architecture — the
**buildable instance** of the one already adopted: `system-design.md` §2/§4 (a question is a
demand on the DAG; it resolves to a plan whose execution materialises the missing nodes; the
**VOI governor that makes demand endogenous is "deliberately last"**) and
`derivation-engine-design.md` (the executor + operators, §12 the governor). This doc scopes the
governor to the MVP — *answer questions over a document corpus* — and is buildable now for one
reason: the session measured the **edge weights** (cost + owner-graded accuracy) the scheduler
needs, and the **grader is trustworthy** (the owner's trichotomy labels). The utility is
`bayesian-foundations.md` §4; the scope edge is `scoped-claims-design.md`.

## 1. The frame (not new)

"Different paths for different purposes" is the VOI executor over the transformation DAG. There
is no single answer path; there is a **library of transforms** (DAG edges) each with a measured
(cost, accuracy-lift), and a **scheduler** that, for a given question, traverses the cheapest
sub-DAG that clears the owner's confidence bar — escalating to costlier edges (and ultimately a
human) only when the cheap ones can't. Querying-with-confidence and deriving-more are the *same*
move: choosing the next edge by `EU(traverse) − cost > EU(stop)`.

## 2. The answer DAG — nodes and edges

Nodes are content-addressed artifacts (the binding invariant, system-design §3 — every edge is
on-ledger, key-before-call): `corpus → retrieval-set → candidate-set → claim → answer`. Edges are
the transform library — all already built this session (as production code or measured probes):

| edge (transform) | node it produces | reuses |
|---|---|---|
| `retrieve` (BM25 k) | retrieval-set | `core/retrieval.py` |
| `rerank` (listwise, wide pool) | retrieval-set' | `ask._rerank_hits` |
| `extract` (local Qwen, per-chunk) | candidate-set | `lookup.observe_hits` |
| `extract_joint` (subject-aware Opus, whole-doc) | candidate-set | `probe_opus_answer` |
| `gather` (corroboration) | candidate-set' | `core/gather.py` |
| `probe_recency` / `probe_subject` | re-weighted candidates | `core/{temporal,subject}` |
| `scope` (as-of rendering) | claim (time-qualified) | `lookup.report_scoped` |
| `decide` (EU under Ū) | claim → answer | `lookup.decide` |
| `synthesize` (narrative) | answer (prose) | `core/narrative.py` |
| `ask_human` (escalate to the assistant) | new evidence | **to build** (effector) |

## 3. The edge weights (the session's contribution)

Each transform now has a measured cost and an **owner-graded** accuracy (trichotomy labels;
"correct" = current value, at **zero real confident-wrong**). The numbers the scheduler runs on:

| edge | cost / question | accuracy effect (owner-graded) |
|---|---|---|
| `retrieve` k=20 | ~free (local) | 1/18 correct |
| `rerank` 150→20 | ~20k tok (Sonnet) | pulls buried golds into top-k (recall enabler) |
| `extract` local | ~free | fast, but **mis-attributes** (assigned a relative's passport) |
| `extract_joint` Opus, subject-aware | ~5k tok | **3/18 correct, 0 sins; withholds mis-attributable values** |
| `rerank` + `extract_joint` | ~25k tok | 3/18 @ 0 sins (current best confident path) |
| `scope` | ~free | converts a stale confident-wrong → honest non-answer |
| `gather` | +re-retrieval | decision-side concentrate; amplifies stale if unguarded |
| `ask_human` | slow + attention | the only edge that reaches un-ingested truth (q-020, OCR scans) |

Two findings are load-bearing for the scheduler: (a) **the bar is not the lever** between p\*=0.90
and 0.95 — nothing sits there; lifting confidence needs a better *edge*, not a lower threshold;
(b) **a stale answer is still wrong** for a current-value question — only `scope` rescues it, and
to a non-answer, not a correct answer.

## 4. The executor

```
classify(question) → purpose  (point-fact | relational | synthesis ; current | historical)
plan = ordered edges by ascending cost for that purpose
state = retrieve(question)               # the cheapest node
loop:
    answer = decide(state)               # EU under Ū over {report, scope, hedge, abstain}
    if answer.confident:        return report(answer)         # cleared the bar — stop, cheaply
    next = argmax_edge net_voi(edge | state) − cost(edge)     # the most useful unused edge
    if net_voi(next) − cost(next) ≤ 0:                        # no edge worth its price
        if answer.has_dated_leader: return scope(answer)      # honest "as of <date>"
        if answerable and corpus-exhausted: return ask_human(question)
        return abstain(answer)                                # named, with what it withheld
    state = next(state)                  # traverse — derive more, then re-decide
```

The escalation is **local → `extract_joint` (cheap cloud) → `+rerank` (when the gold ranks deep)
→ `ask_human` (when truth isn't in the corpus)**, with `scope` / `abstain` as the honest terminal
moves. `decide` is the existing EU step under the §4.4 utility posterior (Ū): `u_correct` /
`u_wrong` (−9, the owner's 10:1) / `u_wrong_scoped` / `u_abstain` — so the *same* utility that
gates report-vs-abstain also prices *whether to spend on the next edge* (the deferred cost-aware
upgrade, scoped-claims §6, now generalised). `net_voi` is `core/brain.value` — the unused VOI
hinge the candidate brain design already exposes.

## 5. The grader is the calibration loop

The executor's edge weights are not hand-set — they are **folded from the owner's trichotomy
labels** (`scripts/answer_labels.py`): every confident answer is shown with its evidence and
labelled correct / stale / wrong in one keypress; those verdicts are the gold *and* the §4.4
`u_wrong` signal. As the system runs, each answer it commits to becomes a new labelled edge
observation — the demand log *is* the governor's calibration corpus (system-design §3). The
scheduler improves because the edge weights sharpen, not because anyone re-tunes it.

## 6. Built vs to build

- **Built (this session):** every edge above except `ask_human`; the cost measurements; the
  owner-label grader + trichotomy utility mapping; `scope` (production) and subject-aware
  `extract_joint` (probe).
- **To build:** (1) the **executor loop** itself (classify → escalate → terminal), composing the
  existing edges — the genuinely new code, and small; (2) the `ask_human` effector (escalate to
  the assistant — `ask_clarify` generalised, priced in latency); (3) production wiring (the
  executor becomes `ask.answer`'s spine / the bridge route).

## 7. Discipline

Everything-on-ledger (system-design §3 — `extract_joint`/`rerank` become recorded §18.9 stages,
keyed before the call). Frozen-blind: edge weights fold from verdicts, never fitted to a gate.
Never fabricate a verdict (the owner labels; the executor only records its own committed
answers). PII stays in `$LIFE_AGENT_KB`. Compose, don't rebuild (PRINCIPLES §4): the executor is
a scheduler over existing transforms + the existing `route`/`decide`; pkm stays frozen. The
hard gate is unchanged — zero confident-wrong, where "wrong" is now the owner's verdict.

## 8. First build (minimal, measurable)

A two-tier executor: `retrieve → decide`; on a withhold, escalate to `rerank + extract_joint →
decide`; terminal `scope` / `abstain`. Measure end-to-end against the owner labels (correct @ 0
real sins) and the **cost actually spent** (the executor should buy the expensive edge only when
it pays). `ask_human` and the full purpose-classifier are the next tiers, not v0.

## Out of scope (until v0 is gate-clean)

The full §12 governor over the *whole* DAG (beyond answering); the narrative/aggregate/thread
families as executor purposes; structure learning of the plan; the always-on daemon.
