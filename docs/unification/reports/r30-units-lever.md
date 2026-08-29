# r30 — the units lever — PRE-REGISTRATION (2026-08-29)

> **This document is the pre-registration. It is committed BEFORE any `src/` change; git
> history is the proof.** r30 builds under the frozen consequence r29 read
> (`docs/unification/reports/r29-answer-shape-census.md`): owner-origin `exact ∧ verbatim`
> reads 0.753 against the 0.85 bar and read 2's structural-abstention prediction holds, so
> **PROCEED** — with two riders on the gather-outcome stream that bind any later checkpoint
> touching it, not this one (see Scope, below).

## STATE

- master `12022ec` (r29 merged: the census read PROCEED; nothing under `src/` moved). Suite
  2919 passed / 35 deselected; ruff + mypy clean; replay 314/314 pure equality on `m5-base`.
- **The mandate.** The plan of 2026-08-28 (as amended 2026-08-29 — owner decision: split into
  r30/r30b so each gate reading is attributable to one lever) proposes five build steps.
  This checkpoint carries steps 1 and 2: the loss-shape construct and question-dependent
  utility units. Steps 3–4 (precision-parameterised claims, the quantity-parameterised
  experiment) move to r30b. Step 5 (streams 3/5) is **investigated and deferred** — see Scope.

## Scope: steps 1–2 only, and why step 5 does not land here

Before any `src/` edit, the tree was read for what streams 3 and 5 would actually fold
against:

- **Stream 3 (`calibration.corrections`) already has a live writer**: `scripts/verdict.py`
  appends `{tx_time, question, claim, cell, claim_as_of, correction}` rows with **no
  `decision_id`** and **no credence** — a free-text steering signal from narrative-claim
  verdicting, not a lookup-family report's commit-time `p`. Its own comment states the
  design intent explicitly: *"a CORRECTION is recorded as a durable... truth plus a
  steering signal — and is NEVER force-folded (reaction-loop economics: the bit calibrates,
  prose steers)."* No `corrections.jsonl` exists yet under `$LIFE_AGENT_KB` (zero rows to
  date), so this is a design reading, not a data-shape surprise.
- Building an automatic Ū fold onto this stream now means one of two things: contradicting
  that stated design position without new justification, or inventing a second correction
  shape alongside the one already declared and used — which C7 (no vocabulary invented
  alongside the ones already named) forbids.
- **Stream 5 (re-asks)** has no writer and no declared detector. Folding it requires a
  similarity metric and a time window between an abstain and a candidate re-ask — both
  unregistered modelling choices. Freezing them now, under this checkpoint's time budget,
  with no prior evidence to ground them, is exactly the kind of un-registered parameter this
  codebase's pre-registration discipline exists to prevent (PRINCIPLES §11).

**Consequence: step 5 is out of scope for r30, disclosed here rather than silently dropped.**
It is not abandoned — the finding above (stream 3's real shape, stream 5's missing
parameters) is itself the pre-registration a future checkpoint needs, and is recorded in
`docs/bayesian-foundations.md` §14 as a named open item. r29's two riders (segment or
exclude run 17's gather-outcome window before any refit; a harm term is a precondition on
any grow-prior refit) bind that future checkpoint, not this one — r30 does not touch
`gather_outcomes.py` at all.

## What r30 builds

### Step 1 — the loss-shape construct

`core/answer_shape.py` (new): the closed vocabulary `exact` · `quantity` · `threshold` ·
`set`, promoting r29's own frozen classification rules
(`scripts/answer_shape_census.py`'s `SPACE_RULES`/`answer_space`/`normalise`) as the ONE
copy — the census script is refactored to import them rather than hold a second copy, so
the decision-path classifier and the audited r29 instrument can never drift apart. Pure
regex over question text; no model call exists to make caching worth its complexity (unlike
`core/subject.py`'s LLM-backed owner-match, which the original plan's "instrument under the
§2 contract, cached" language was modelled on — disclosed deviation: v0 is a plain
predicate, in the same family as `terminals.owner_question`, not a cached instrument).
Conservative default **unknown → `exact`** (C3), unchanged from r29's own default.

### Step 2 — question-dependent utility units

`core/decide.py` gains `shaped_u_bar(u_bar, shape)`: `exact` is the **anchor**
(`u_correct`/`u_wrong` pass through unscaled — today's §4.4 convention, unchanged); each of
`quantity`/`threshold`/`set` carries a `voi_scale_<shape>` (multiplies `u_correct`) and a
`regret_scale_<shape>` (multiplies `u_wrong`), read from Ū when the owner's model.yaml has
declared them and **defaulting to 1.0 — the anchor's own value — when it has not**. This is
a deliberate deviation from the original plan's "six REQUIRED latents": `REQUIRED_LATENTS`
forces every model file (including the fourteen-plus test fixtures across this repo and the
owner's live, out-of-tree `$LIFE_AGENT_KB/utility/model.yaml`) to declare a value before it
loads at all — the `lambda_usd` rollout took that path deliberately, as a hard latent the
gate's spend term needed unconditionally. These six do not need that force: `tau_narrative`
is the existing precedent for an **optional** latent block that falls back to a stated
default when the file omits it, and that is the lower-risk, zero-forced-migration shape
here. `load_model` parses `voi_scale_<shape>`/`regret_scale_<shape>` **iff present**,
through the same generic fold (`_components`/`_fold_1d`) every other latent already uses —
no engine change.

`core/lookup.py`'s `current_u_bar` gains a keyword-only `shape` parameter (default
`answer_shape.DEFAULT_SHAPE`, i.e. `exact` — every existing call site is unchanged): it
folds the engine posterior **once** per fold_version (unchanged cost) and memoises
`shaped_u_bar` per `(fold_version, shape)` (cheap, pure). `lookup.decide_and_record` and
`narrative.narrative_answer` each classify their own `question` via `answer_shape.classify`
and pass the result through. The bridge's `GET /utility` gains an optional `shape` query
parameter (`_utility` handler; `dispatch`'s GET branch is extended to parse a query string
into the same `Payload`-dict shape POST handlers already receive — no new parsing
machinery); `core/executor.py`'s `run_pass` classifies the question once and requests
`/utility?shape=<shape>`, so the grow-menu pricing the daemon argmaxes over is shaped too
(C5: this reaches both halves of the argmax through the same seam). The membrane shadow's
own `u_bar` closure is left at the anchor shape unconditionally (a separate, decoupled
closure) — membrane is explicitly off the decision path and out of scope here.

**Every scale at 1.0 — i.e. every model file that does not declare the six optional
latents, which is every fixture and the owner's file today — reproduces pre-r30 behaviour
byte-for-byte.** This is not asserted; it is what G2's replay checks.

## Frozen criteria

| | Criterion |
|---|---|
| **C1** | The loss-shape instrument defaults **unknown → `exact`**; RED under a mutation defaulting to `quantity`. |
| **C2** | `core/answer_shape.py` and `scripts/answer_shape_census.py` share ONE rule table — the census script imports it, never retypes it; RED under a mutation that diverges the two. |
| **C3** | `shaped_u_bar("exact", ...)` returns the input `u_bar` unchanged (object equality of every value) — the anchor does nothing; RED under a mutation that scales `exact` too. |
| **C4** | A model file declaring **none** of the six optional latents produces IDENTICAL `u_bar` output for every shape (`shaped_u_bar` falls back to 1.0 for both scales) — RED under a mutation that raises or silently zeroes instead of defaulting. |
| **C5** | Question-dependent units reach BOTH halves of the argmax — `current_u_bar`'s lookup/narrative callers AND the bridge `/utility` endpoint `executor.run_pass` reads for grow-menu pricing — through the SAME `shaped_u_bar` function; RED under a mutation that re-implements the scale arithmetic at a second call site. |
| **C6** | The six new latents carry stated supports and priors, frozen in `config/utility-model.example.yaml` (and the owner's deployed copy) BEFORE this report reads any gate — each prior centred at 1.0 (mean, post-truncation, computed not assumed — the `lambda_usd`/#67-review lesson). |
| **C7** | Step 5 is not silently dropped: this document's Scope section names what stream 3's existing shape and stream 5's missing parameters are, and `docs/bayesian-foundations.md` §14 records the open item. |
| **C8** | **Hard clause** (owner ruling 2026-08-28): the wrong-commit count and its per-class breakdown are published beside the gate splice reading; no lever ships while a named class is worse in expected utility. |
| **C9** | Δ under `shaped_u_bar` is not comparable to Δ under the flat units — the gate splice states this explicitly and publishes both readings on the same rows if both exist. |
| **C10** | **G2 — the 314-fixture replay, pure equality on `m5-base`.** Since every shipped model file leaves the six latents undeclared (C4/C6), the replay must show 314/314 unchanged — a delta here means the change is NOT the no-op it is designed to be, and must be diagnosed before anything ships. |
| **C11** | PII: no question text, corpus value, or owner-specific identifier enters the tree. The six latent names and their stated priors are generic constants, not personal data (unlike the values in `$LIFE_AGENT_KB/utility/model.yaml`, which stay out of tree). |

## Verification plan

1. `uv run pytest -m "not llm and not system"` (`TMPDIR=~/.cache/tmp`) + `ruff check .` +
   `mypy` — full suite, evidence pasted.
2. `uv run python .githooks/pii_check.py` exit 0 with the private name layer live.
3. C1–C6 each demonstrated RED by its named mutation, then restored — transcript in the
   report.
4. `PYTHONHASHSEED=0 scripts/collapse_replay.py --checkpoint m5-base` — 314/314 (C10).
5. A $0 splice on run 18's own record, read under `shaped_u_bar` at every scale = 1.0 (the
   only state the owner's live model file is in today) — a no-op reading by construction,
   published to demonstrate C4/C10's claim rather than merely assert it.

## Gates

**G1** suite + ruff + mypy · **G2** `collapse_replay --checkpoint m5-base`, 314/314 ·
**G3b** the $0 splice against these frozen conjuncts, before any priced run (none is bought
in this checkpoint — the units lever ships as a no-op until the owner's model file opts a
shape in, so there is nothing a priced run would newly measure yet).
