# PRINCIPLES — the standing principles of life-agent

The principles that outlast any one feature. [`CLAUDE.md`](./CLAUDE.md) holds the five rules and
the working method, [`MODEL.md`](./MODEL.md) how a question becomes an answer,
[`ROADMAP.md`](./ROADMAP.md) the plan. pkm's own foundations live in
[`docs/pkm/SPEC-PRINCIPLES.md`](./docs/pkm/SPEC-PRINCIPLES.md) and are referenced, not
duplicated. Section numbers are stable: a retired section leaves a gap, it is not renumbered.
Changing this file is a deliberate act, not a side effect of a feature.

**§1. The kernel.** A **knowledge base created from DAGs of trustworthy transformations**, and
a **personal assistant — the "life agent" — making rational, utility-maximising decisions based
on it**. Two layers: the KB *derives* (pkm); the agent *decides* (life_agent). Every component
belongs to exactly one. The agent is, exactly, a **belief**, a **utility**, and a **decision
space**, acting by **argmax expected utility**; it differs from any other such agent only in
*which* utility it serves (the owner's) and *which* decisions it ranges over. The act is the
host's `core/decide.bayes_act`; the body supplies the utility and the decisions.

**§2. The KB layer — trustworthy transformations.** Trust is structural, not aspirational.
Every derived artifact is **cited** (traceable to source bytes), **content-addressed**
(identity = hash of inputs — SPEC-PRINCIPLES §2), **idempotent** (re-running is a no-op),
**independently auditable** (small, generic, chained steps — never one mega-transform), and
**composable** (a transform may consume another transform's output — pkm SPEC §18.7). The
recording layer makes no truth claims; reliability is assessed downstream (SPEC-PRINCIPLES §4).

**§4. Prime directive — compose, don't rebuild.** ~90% of the building blocks exist in the
owner's own projects. New work is integration plus thin layers. Before writing anything, check
whether a producer, a transform, or an existing script already does it.

**§5. Seams.** Faculties integrate over language-neutral seams — MCP / HTTP / CLI — so what
sits behind a seam stays swappable. `src/pkm/mcp_server.py` is live: the deliberative rung
runs it.

**§6. derive → project → reach.** Immutable derivations (pkm) flow through a thin, one-way
bridge into mutable state (*project* — each fact filed once, with its citation), and out to the
owner through dumb transports (*reach*). Transports hold no truth and no business logic.

**§7. Ledger as truth; the derive/act boundary.** Where state is legitimately mutable, truth is
`fold(append-only events)`: every read-model is a rebuildable projection, and a cleared item
never resurrects. The boundary test: **a fact derivable from sources is a pkm transform or a
read-time projection — never a new ledger.** Only human-authored mutable state (a task
completed, a note written) warrants act-layer events.

**§10. Determinism is semantic, defined in pkm.** The determinism contract (semantic
equivalence, not byte-equality; a cache hit is deterministic regardless of model behaviour on a
miss) is owned by [`docs/pkm/SPEC-PRINCIPLES.md`](./docs/pkm/SPEC-PRINCIPLES.md) and pkm's SPEC
§7.1. Do not redefine it elsewhere, and do not "fix" it.

**§11. Two rigors.** `src/pkm` is the frozen foundation: SPEC-first (amend the SPEC before the
code), TDD, every cache operation proven idempotent by a double-run, ask before a new
dependency / top-level directory / file format. Above pkm, rigor is **answer-grounded
evaluation**: facts graded against expected answers, failure-mode-classified, robust to corpus
growth. pkm records what happened; the layers above are accountable for what is true.

**§12. Privacy is structural.** This public repo holds the system, never the data: corpus,
evals, logs and identity live under `$LIFE_AGENT_KB`, outside the tree, enforced by a
fail-closed PII guard on every commit. Where a model runs (local or cloud) is engineering, chosen
by cost, latency and capability.

**§13. Tailscale-only.** Any networked surface binds to the Tailscale IP. Never expose
publicly; never use `tailscale serve`/funnel.

## Diagnostics (one-question tests)

**Derive or act?** *Could this state be recomputed as a pure function of sources + config?* If
yes, it is a pkm transform or a read-time projection. If no — a human authored or mutated it —
it is act-layer events (§7). There is no third category.

**KB or agent concern?** *Am I asking "what is recorded?" or "what should be done?"* The first
belongs to pkm (§2); the second to the agent (§1). Do not conflate them: the KB does not decide,
and the agent does not re-derive.

**Report or principle?** *Would this text be deleted if the research behind it were retracted?*
If yes, it is an input, and belongs in a report with a status header — not here.

**Seam or implementation?** *If the component were rewritten in another language tomorrow,
would its consumers change?* If yes, the boundary is not a seam yet (§5).
