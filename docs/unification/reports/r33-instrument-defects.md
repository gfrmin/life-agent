# r33 — the instrument-defect arc (Conferral 2, ruling 3; declared before any `src/` change)

**Ruling 3 (owner, 2026-08-30): all five instrument defects found by the Stage-4 exit
measurement are fixed BEFORE any successor measurement.** Plus two riders ruled since: the
sixth item r32 found (the reaction-driven bar drift — owner ruling 2026-08-31: MONITOR ONLY),
and the `shaped_u_bar` docstring correction r32 queued. This document declares every record
change and its expected replay delta BEFORE the first `src/` edit (the M2 pattern: a record
change is pre-registered, tightly directed, and everything it does not name stays under the
standing §7.2 classes).

Scope: defect fixes only. Nothing here changes the argmax, the fold semantics, or any
decision the engine takes — the one behavioural change on the decision path is that a
transport error is retried before it kills an ask. No priced run is demanded.

## The items

| # | defect (conferral 2 §3) | fix site | record change? |
|---|---|---|---|
| A1 | `post_json` has no retry/backoff/5xx handling (signature E, seen live) | `core/ask_client.py` | no |
| A2 | a lookup that grounds nothing writes NO decision row — the class is invisible to the reaction stream, in both directions | `core/ask_client.py` poster guard + `core/recorder.py` + `core/decisions.py` | **RC-1** |
| A3 | narrative rows log `cost_usd: null` — every round's cost is a lower bound | `core/synthesis.py` → callers → `core/narrative.py` | **RC-2** |
| A4 | `none-of-retrieved` renders `0.000` when NOTHING was admitted — indistinguishable from a confident absence | `core/executor.py` footer render | **RC-3** (render) |
| A5 | a carrier census taken from one spelling of one string is wrong (two round-8 self-catches) | `scripts/carrier_census.py` (new) | no |
| A6 | the bar drifts with the reaction fold (r32's sixth; 0.900 → 0.837, monotone) — MONITOR ONLY per ruling | `scripts/production_readout.py` + `scripts/bar_audit.py` imports | no |
| A7 | `decide.shaped_u_bar` docstring still calls 0.90 "today's uniform bar" — false since the fold moved | `core/decide.py` docstring | no |
| A8 | master's lint gate is red (one pre-existing I001 in `ledger/migrate.py`) | autofix rides along | no |

## RC-1 — the miss row (A2)

**What exists:** the executor's zero-candidate exit (`executor.py` "miss") returns a view the
poster's guard drops by documented intent — no row of any family is written. The in-process
terminals lane already ends in a narrative row, so the blind lane is exactly the deployed
executor lane. (`docs/unification/reports/r31-integration-gate.md` claims this lane "emits
the §6.5 unavailability record with an empty decision id" — that is WRONG, it emits nothing;
the correction lands in this arc, and the out-of-tree FAILURES.md class name "§6.5 empty-id"
is retired with a correction note. Fifth instance of the standing lesson: a census must read
the deployed rule end-to-end — here it re-narrated a code path instead of tracing it.)

**Declared change:** a miss appends ONE local `lookup`-family row through the one recorder —
`recorder.record_miss` beside `record_unavailable` — with:

- `chosen_action: "abstain"` (the §6.5 precedent: the action vocabulary stays closed; the
  REGIME names the truth),
- `regime: "miss"` — a NEW declared regime value in `core/decisions.py` (a coverage failure
  under a live engine, distinct from `unavailable` = no engine at all),
- a **real, content-addressed `decision_id`** so the owner can react and the measurement can
  credit/price the class. The id rule is the bridge's `_decision_id` PROMOTED to one
  declaration in `core/decisions.py`; the bridge binds it (drift-gated identity) — a second
  spelling cannot exist,
- `utility_fold_version: ""` — no fold ran; no `/decide` was called (the same honesty as §6.5),
- `posterior_summary` with empty candidates/credences, `p_none: None` is NOT available in the
  row schema (summary floats stay honest: `p_none: 0.0` with `n_obs: 0` and `regime: "miss"`
  carrying the distinction — the row-side twin of RC-3),
- local append, not a bridge post: the bridge's poster derives ids for RANKED decisions and
  stamps the CURRENT fold version, both wrong for a miss; the §6.5 precedent already
  established the local lane, and client + ledger share the box by deployment.

**The frozen rider — fold exclusion:** `reactions.load_reactions` SKIPS rows whose
`regime == "miss"`. A reaction to a coverage failure is not evidence about `u_wrong` — the
r29 stream-segmentation lesson applied prospectively. Without this, A2 would feed the very
drift A6 is ruled to watch: every `bad` on a miss would fold as a threshold observation and
drag the bar further down. Pinned by a test that a reacted miss row folds NOTHING.

**Expected replay delta:** none on the wire (local append only; no new HTTP exchange). If a
fixture's output-level comparison sees the new record event on miss questions, the delta is
DIRECTED: exactly `regime: "miss"` rows appearing on fixtures whose recorded terminal was the
miss render — nothing else moves. Any other diff FAILS the gate.

## RC-2 — the narrative price (A3)

**What exists:** `synthesize` already measures usage (`in_tokens`/`out_tokens`/`seconds` land
in the derivation node's metadata) but returns no price; `narrative_answer` records its
`DecisionEvent` with the v2 leaf defaults (`instrument: ""`, `cost_usd: None`,
`latency_s: None`). The recorder's own docstring dates this: leaves keep v2 defaults "until
the checkpoint that declares their regime (M5)" — M5 declared the regime and left the price.

**Declared change:** `synthesize` returns its realised price through the ONE price rule
(`pricing.cost_usd(LLMResult)`) — a cached serve prices `0.0` — and both callers thread
`cost_usd`/`latency_s`/`instrument` into `narrative_answer`, whose event now applies the
poster's never-absent normalisation (`0.0` = ran unpriced, never null). The audit stage's
cached verdict calls stay outside this price (they ride the eval_claim stream); the
in-process LOOKUP leaf keeps its v2 defaults — named remainder, out of scope: the defect
names the narrative rows, and the terminals-only lookup lane runs only with the daemon down.

**Expected replay delta:** narrative-leaf fixture bodies move `cost_usd: null → number`
(and may gain a non-empty `instrument`). DIRECTED: only those fields, only on
narrative-family leaf bodies. Cached-synthesize replays price `0.0`.

## RC-3 — the honest footer (A4)

**What exists:** the miss view carries `p_none: None`; `render_view` coerces it to `0.0` at
format time, so "I found nothing" prints the same `none-of-retrieved 0.000` as a genuine
posterior that put zero mass on NONE. The body sentence already distinguishes
(`withhold_reason` → "no admitted evidence"); the footer number lies.

**Declared change:** the footer renders `none-of-retrieved —` (and `EU —`) when the view
carries `None` — a number prints only when a posterior produced it. `REASON_UNAVAILABLE`,
defined and never bound, binds on the §6.5 render branch. No record change (the ledger-side
distinction is RC-1's `regime: "miss"`).

**Expected replay delta:** miss-question fixtures whose recorded output includes the
rendered reply diff EXACTLY on the footer's `none-of-retrieved`/`EU` tokens. Nothing else.

## A6 — the bar monitor (ruled MONITOR ONLY, 2026-08-31)

The weekly readout gains one line: **p† (the deployed assert bar) beside the declared-prior
bar**, both computed through `scripts/bar_audit.py`'s machinery — `u_bar_as_of` (the deployed
fold as of now) and `indifference_point` (bisection of the imported `decide.u_assert`) —
imported, never re-implemented; the declared-prior bar comes from folding the EMPTY evidence
list, so 0.90 is never hard-coded. The readout stays a watch, not a dependency: the p†
computation needs the live brain (`LK.shared_brain()`), so it runs under a guard and a dead
daemon renders `p† unavailable (<reason>)` instead of failing the report. Fold semantics
untouched; any fold reform is its own future pre-registration.

## Gates (all $0)

1. TDD per item: every new predicate RED before GREEN; the fold-exclusion, the retry
   classifier (5xx/URLError/timeout retried, 4xx never), the id-promotion identity
   (`bridge._decision_id is DEC.<name>` or equality on a probe body), and the footer branch
   each carry a test that fails on the pre-r33 tree.
2. Full suite, mypy, ruff (repo gates), PII guard on every touched file.
3. The m5-base collapse replay: green under the three declared directions above; PURE
   EQUALITY on every fixture the directions do not name. An undirected diff is a FAIL, not
   an amendment — the M3 lesson (re-read every frozen clause against the artefact it names)
   applies to these directions too.
4. A6 cross-check: the readout's p† on the live stream equals `scripts/bar_audit.py`'s
   number for the same as-of, to printed precision.

## Consequence

All gates green → PR onto the conferral2-r32 branch chain (this arc stacks on PR #125,
which carries `scripts/bar_audit.py`); the owner merges. Any gate red → fix or STOP and
disclose; no gate is renegotiated after it reads.
