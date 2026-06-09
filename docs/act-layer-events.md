# The act-layer event ledger

How the agent's *mutable* truth (the GTD task list) is reconciled with its *immutable*
derivations (pkm `action_items` artifacts). This is the **project** step of
**derive → project → reach** ([`PRINCIPLES.md`](../PRINCIPLES.md) §6–7), and the part the
`reconciliation-as-transformation` design is about. Implemented in
`src/life_agent/tasks/events.py` + `project.py`.

## The principle

`truth ≠ f(transforms)` — the task list is not a pure function of the email extractions,
because the human curates it (completes, deletes) and the world moves on. But

> **`truth = fold(events)` is pure, if the path is an append-only log.**

So we keep two operators on one immutable substrate:

- **derive** = `map` over content-addressed inputs (pkm): email → grounded `action_items`.
- **project** = `fold` over an ordered, append-only **event ledger** (here): the current
  task set is the projection of the ledger, never an independent mutable store.

The only mutable object is the materialised projection (jarvis's SQLite), which is a
**rebuildable cache** — exactly the concept the derive layer already trusts.

### Immutability ≠ determinism

A stochastic transform (an LLM) has no deterministic *value*, but the instant it runs it
produces an immutable *fact* stamped with `tx_time`: "at T, model M on X drew Y." We replay
the **recorded draw**, never re-roll it, so the fold stays deterministic even though the
draw was not. (This is why a future LLM correlator's verdict is recorded as an *event*, not
recomputed inside the fold — see Deferred.) `tx_time` is the only clock that matters.

### Log vs ledger

Structurally identical (append-only, immutable, ordered). The difference is **role**: a
*log* can be a subordinate side-record; a **ledger** is the authoritative book of record —
complete (all event types), the thing state folds out of, and *corrections are compensating
entries, never erasures*. This is a ledger. (The old `dedup.py` was a lossy marker-log.)

## The model

Three event types, each concerning one assertion `identity`:

| event | meaning | closes the identity? |
|-------|---------|----------------------|
| `Asserted` | the agent filed this grounded item as a task | no (it is *open*) |
| `Disposed` | the human cleared it (deleted/completed); carries a `reason` | yes |
| `Superseded` | a newer assertion replaces it (`superseded_by`) | yes |

Each event carries `tx_time` (when recorded), `valid_time` (when true in the world, if
known — the email's date for now), `reason`, and a `payload` (the assertion attributes).
Bitemporality is **three fields**, deliberately not a bitemporal database.

### Assertion identity — the key that is *not* the cache key

```
identity = sha256( normalize(claim_type) ⨁ normalize(grounding_span) ⨁ normalize(claim_content) )
```

(`life_agent.tasks.events.assertion_identity`; whitespace-normalised, case preserved.)

It deliberately **excludes** model / prompt / schema. That is the pkm **cache key**'s job —
its purpose is byte-reproducibility, so it *should* change on a prompt bump. Identity's job
is the opposite: **referential stability across re-derivation**, so the same claim extracted
from the same quote dedups even after a bump, and a positional index never enters into it.
This single change fixes both the old positional-duplicate bug and the read-all-generations
duplicate (identical content → one identity).

### Two projections of the ledger

- `fold(events) → {identity: OpenAssertion}` — the **open** assertions (the live task set).
  A close always wins (a disposed identity never reopens), which makes the fold
  order-independent and therefore stable across replay.
- `known_identities(events) → set` — **every** identity ever recorded (open ∪ closed). This
  is the set that **suppresses re-filing**: an identity here is either already filed (open)
  or handled (closed); neither is *fresh*. Suppressing on `known` (not on `fold`) is what
  stops a cleared task from being **resurrected** on the next run.

## v1 behaviour (what is built)

`project_action_items` each run:

1. read the newest `action_items` artifact **per email** (`read.py` — older generations are
   never surfaced), gate by `email_triage` actionability (SPEC §18.8);
2. **capture dispositions** (commit only): any open assertion whose `task_text` is no longer
   in the *active* jarvis set (deleted or completed) gets a `Disposed{reason: "cleared"}`
   compensating entry. Non-invasive — it reads jarvis, the bot is untouched;
3. file every candidate whose identity is not in `known_identities`, appending an `Asserted`
   event per filed task;
4. idempotent by construction: a second run files nothing; a cleared task never returns.

## Deferred (named, on the same foundation)

- **Full authority / Option A.** Today jarvis is still the live surface the human mutates, so
  the ledger *follows* by capture (eventually-consistent, with a "jarvis leads" window). Making
  the bot emit `Disposed`/`Superseded` events directly and rebuilding jarvis as a pure
  projection of `fold(events)` removes that window. Changes *consistency*, not the model.
- **The LLM correlator tier.** Hash identity is exact-match and span-stability-bounded. Fuzzy
  cases (reworded post-bump claim = dup or supersede? re-grounded span = same task?) are an
  LLM's job, as a first pass with human adjudication. **Guard:** run it once at *ingestion* and
  record its verdict as an event — never inside the fold (that would re-introduce
  nondeterminism and replay cost). It is then just another `map` feeding the ledger.
- **Reason-rich disposal.** Capture sets `reason: "cleared"`; distinguishing *done* vs
  *wrong* needs a prompt at disposal time (the bot). `Disposed{reason: "wrong"}` is the
  offline learning signal (batch → eval set → recompile prompts), never runtime feedback into
  the pure derive layer.
- **Generalisation.** This is the *first* projection. Build the 2nd (entities) and 3rd
  (calendar) as copy-pasted folds, then extract — no event-sourcing framework before three.
