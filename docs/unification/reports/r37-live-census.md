# r37 — the live firing census: READING

Pre-registration (committed before any `src/` change, with its two blind amendments):
[`r37-live-census-preregistration.md`](./r37-live-census-preregistration.md).
Instrument: `bridge/server._join_tap` + `scripts/join_census.py --live/--superset/--equivalence`.
Consequence: `D-2`'s defaults, no keypress.

*(sections filled in as they read — the build and the $0 legs first, the priced run last)*

## 0 · What r37 is for

r36 killed r34's lever on **K3**, an attribution conjunct: the frozen clause required the
rows whose action changed to be a subset of the census's firing surface, and two rows outside
it moved. The cause was not the lever. `scripts/join_census.py` enumerated that surface from
**recorded wire** — m5-base cassettes frozen on an older tree — while a live run re-derives its
own trajectory, so the recorded surface is a **lower bound, not an enumeration**.

r37 replaces the bound with a measurement.

## 1 · The instrument

`bridge/server._lattice_join` takes its identity as a parameter whose **default is the
deployed one** (`LK._norm_value`). r37's tap re-runs *that function* under the declared §4.2
key to get the counterfactual, instead of writing a second copy of the rule — `M-7` is the
standing lesson at five instances and its signature is exactly an instrument that prices a
constant it re-spelled itself.

The parameter is a back door to a second declared identity on the decision path, so it is
gated: an AST guard fails if any `src/` call site other than `_join_tap` passes `key=`
(mutation-verified by planting exactly such a call).

The tap is **off unless `LIFE_AGENT_JOIN_TAP` is set**, writes to `config.JOIN_TAP_LOG`
(`$LIFE_AGENT_KB/eval/join-tap.jsonl` — deliberately outside `calibration/`, `M-14`), records
**every** call rather than only firings so the surface has a denominator (`G-3`), carries no
`decision_id` and no credence, and never raises onto the decide path. `dispatch` publishes
`(url, question)` once per request so the join — several frames below the handler — can key
its rows by question without a per-handler wiring.

## 2 · L5 — the mutation ladder (18/18 RED)

Run before any reading, per the frozen criterion. Each row: the predicate, the mutation, and
the test that turned RED.

| # | predicate | mutation | test that went RED |
|---|---|---|---|
| M1 | the flag gate | `if not os.environ.get(...)` → `if False` | tap is off by default |
| M2 | the deployed default key | `_norm_value` → `_candidate_key` | deployed identity; and r36's defect-pinned-live test |
| M3 | the recursion guard | `if key is LK._norm_value` → `if True` | a disagreement is a firing |
| M4 | the firing comparison | `!=` → `==` | a disagreement is a firing |
| M5 | non-firings recorded | early-return on agreement | every call has a denominator |
| M6 | the tap never raises | `except: return` → `raise` | never raises onto the decision path |
| M7 | the question key is the declared id | `DEC.question_id(q)` → `q` | key is the declared id, not text |
| M8 | the row field allow-list | add `decision_id` | no decision_id, no credence |
| M9 | the dispatcher context | delete the `_tap_context` call | dispatch supplies the context |
| M10 | the log is outside the fold | `eval/` → `calibration/` | log path outside the fold |
| M11 | L3's direction | `r_fire - o_fire` → reversed | a recorded firing absent live |
| M12 | L3's shared set | `&` → `\|` | empty shared set is not a pass |
| M13 | the empty-population guard | `if not triples` → `if False` | empty population fails |
| M14 | the census disarms the tap | delete the `environ.pop` | census disarms the tap |
| M15 | the equivalence comparison | `bad = [...]` → `bad = []` | detects an injected divergence |
| M16 | the `key=` drift gate | plant `key=` at a decision-path call site | no call site overrides the identity |
| M17 | no second question hash | key → a local `sha256(question)` | the existing `test_no_other_site_hashes_a_question_itself`; and r37's own AST proof |
| M18 | equivalence restores module state | drop the `JOIN_TAP_LOG` restore | the restore test |

**M15 is the one worth reading twice.** Its first form was GREEN: the test asserted
`divergences == 0`, which a comparison that always returns "no divergence" satisfies. ON and
OFF never diverge on the real join — that is the *claim* — so the only way to show the check
can fail is to inject a join that behaves differently under the flag and require it to be
caught. The test was replaced with that; then M15 went RED. A criterion that cannot fail is
not a criterion (`G-3`), and this is the second time in two checkpoints that the *verifier*,
not the code, was the defect.

**A second defect the ladder did not find — an existing guard did.** The tap first grew its
own `sha256(question)`. `tests/test_decisions.py::test_no_other_site_hashes_a_question_itself`
failed it: `decisions.question_id` is the ONE derivation of a question's identity, and a
second spelling silently splits the id namespace so that every join across it reads as *no
data* rather than as an error. The tap now binds it (M17 in the ladder pins that). The
alignment this buys is exact rather than incidental: `DEC.question_id` reproduces the recorded
`question_id` of **all 308** m5-base probe exchanges from the payload question, with **0**
disagreements — so the recorded side computes no key at all, and there is nothing for the two
surfaces to drift apart on.

**Two findings from reviewing this PR before merging it**, both fixed in the same branch and
both now pinned (M18 and a same-population test). The instrument walked the recorded wire
**twice** — once in `census`, once to build the equivalence population — which is two
definitions of "what was recorded", the r37 defect one level up; there is now one
`recorded_joins` walk that both consume. And `equivalence` borrowed two pieces of module state
(the flag and the declared log path) and restored only one, so anything later in the process
would have had its tap silently disarmed. Neither changed a number: the equivalence still
reads 234/0/234 and the census still reads 234 joins · 5 firings after the refactor.

## 3 · L1 and L2 — the tap is inert, and it does not decide

Two verifiers, per amendment 1 (`GD-7`). They are not redundant; one of them is the one that
can fail.

**(a) The host-side check — m5-base replay, tap OFF.** `288/314`, errored exactly the standing
26: the 21 A-loop `?shape=` wire artefacts (r30) and the 5 B-lookup interval rows
(q2-004/029/056/059/090, r30b). Byte-identical to the baseline. `PYTHONHASHSEED=0`.

**(b) The paired equivalence — GD-7's added verifier.** Every `(value, candidates, allow_new)`
triple recoverable from the 314 fixtures — **234** of them — through the deployed join with
the flag ON and with it OFF:

```
{"population": 234, "divergences": 0, "tap_rows_written": 234, "ok": true}
```

`divergences: 0` is L2. `tap_rows_written: 234` is the **non-vacuity** half: the tap really
was armed and really did observe every call, so "no divergence" is a measurement and not a
silence.

**Why (a) alone would have been a vacuous pass, restated with the evidence.** The replay
serves `/probe/deliberate` and `/probe/corroborate` from cassettes, so it never enters
`_lattice_join`. Run again with the flag ARMED, it wrote **0 tap rows** — the log was not
even created. That is the pre-registration's named verifier demonstrating, on its own
artefact, that it cannot see the thing it was named to verify. `GD-7` was written before this
run, on the source; this is the confirmation.

## 4 · The recorded-wire surface (the bound r37 replaces)

Since the join takes its identity as a parameter, one pass now reads both arms — the census no
longer needs two trees to say where the lever fires:

```
234 recorded joins over 97 fixtures · 5 firings
```

**5 firing exchanges over exactly 2 questions** — the same two r34 found, so the re-built
instrument reproduces the number it replaces. 97 of 104 questions have a join exchange at all.

One thing the firing rows say that r34's diff did not. Three of the five are
`deployed → no join at all` against `declared → index 1`: the deployed key finds no exact
match, containment is ambiguous or competing, `allow_new` is false, and the channel gets **no
observation**. So the lever does not only merge two atoms into one — on those rows it
**supplies an observation the deployed tree discards entirely**. That is a materially
different mechanism from the q2-027 merge run 21 demonstrated, and any successor's directional
claims have to name both.

*(L2's host-side leg, run for the record: the m5-base replay with the flag ARMED reads the
same `288/314` and the same 26, and wrote `0` tap rows — the log was never created.)*
