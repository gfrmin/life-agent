# CRM — architectural decisions (four resolved by the adopted framework)

> **Resolution note (2026-06-11).** The adopted framework
> ([`system-design.md`](./system-design.md), [`derivation-engine-design.md`](./derivation-engine-design.md))
> resolves the crux and most of its dependents:
> **#1** — both, by kind: LLM projections (per-thread classification, `thread_state`) are
> pkm transforms, cached forever; deterministic reads (direction/counterparty from headers,
> filters, aggregates) are executor-side query-layer operators — never a bespoke faculty.
> **#2** — moot: deterministic operators live in the life_agent executor, so no model-free
> transform-substrate change; the one pkm shape change is D4's `assemble`.
> **#5** — ask (*know* mode) is the CRM read surface; Telegram intents deferred.
> **#6** — identity/owned-domains knowledge lives life_agent-side (with the owner profile);
> it never enters pkm.
> "Awaiting reply" lands as engine phase D4. **#3 (mutable notes/reminders) and #4 (alias
> dedup) remain open** — if #3 lands as a ledger, it inherits the knowledge-projection
> pattern (system design §5).

Context: the attempt to "incorporate the renavon CRM, like email→GTD" first produced a full
event-sourced `life_agent.crm` faculty, which was then torn down on the principle that **the CRM
is "just pkm in another form"** — interactions are immutable derived facts (pure pkm), not a
mutable act-layer that warrants its own ledger/store/CLI. The working tree is back to the pre-CRM
state. These were the decisions that needed taking before rebuilding (resolutions above).

Ordered by how much each gates the rest; the crux of each is in **bold**.

> Note on identity: "owned domains" below refers to the set decided this session — own *whole
> domains* (the several personal + business domains you send as) plus a few explicit non-owned-domain
> addresses (Gmail, university). The concrete list is PII and lives in out-of-tree config, not here.

## 1. Materialised artifact vs read-time projection (the crux)

Does deriving an "interaction" (direction + counterparty) warrant a **materialised pkm artifact**
(a `crm_interaction` transform), or is it a **read-time projection** computed at query time?

- *Transform:* cached, citeable, lineage off `email` — but forces decision #2 (substrate change).
- *Query-layer:* zero new pkm machinery — direction/counterparty are cheap deterministic functions
  of headers already present; "CRM" becomes a retrieval view like `ask.py`. No cache-key risk.

**This decision makes #2 moot if you go query-layer.** Tentatively leaning "transform", but worth
confirming now that it's known to cost a substrate change.

## 2. Model-free transform substrate + cache-key semantics (only if #1 = transform)

SPEC §18.7 blesses a "deterministic op" transform, but the substrate is LLM-coupled (declaration
loader, run loop, cache key). Extending it is a **pkm-level commitment** that sets precedent for all
future non-LLM transforms. The load-bearing sub-decision: **how a model-free transform's cache key
is composed** (proposal: fold `producer_class + version + config + output_schema + schema_version`;
drop `model_identity`/`prompt_hash`). Sensitive — wrong key semantics means rebuilding the cache.

Coupling points verified this session:
- `transform_declaration.py:83-87` — `model`, `prompt`, `output_schema` are required keys.
- `transform_run.py:306-307` — a result with no `prompt_hash` is counted *failed*.
- `transform_run.py:324-334` — cache key folds `model_identity` + `engine_version` + `prompt_template_hash`.

## 3. The mutable CRM layer — notes / reminders / merge

These are **not pkm** (human-authored, mutable); the "full collapse" deletes them. Decide where they live:

- Fold into the **GTD** (a reminder = a task with a `[src:crm]` citation) — reuses the existing
  act-layer ledger.
- A **separate small act-layer** for CRM — but that risks re-creating the bespoke faculty just rejected.
- **Drop them** for v1; CRM is read-only memory.

## 4. Contact identity & alias resolution

Owned-domains handles *self*-identity. Two residual decisions:

- **Business-domain false positives:** a colleague/customer on a business domain you own would read
  as "you". Accept, or maintain a per-domain exception list?
- **External-contact dedup:** renavon's `email_aliases`/`merge` collapsed one person's many addresses
  onto one contact. Is that needed here, and if so where does the (mutable) alias map live — ties to #3.

## 5. Reach surface

CRM reads should surface the way the GTD does — **Telegram** (the channel is the reach), not a
bespoke CLI. Decide: build CRM intents into `reach/jarvis.py` NLU, or expose only a read-only debug
surface (like `bin/ask-live`) and defer Telegram. And **where the query code lives** (a life_agent
retrieval module vs elsewhere).

## 6. Config boundary for owned-domains

pkm's CLAUDE.md forbids env overrides / multiple config systems ("one `config.yaml`"); life-agent
keeps PII out-of-tree (public repos). So: does owned-domains live in the **pkm transform declaration**
(out-of-tree root), a **life_agent config**, or a shared out-of-tree file? This is really a question of
**which side owns identity knowledge** — and whether pkm should know it at all (arguably not, which
again favours #1 = query-layer in life_agent).

## 7. Scope & indexing

- **Scope:** does every email become an interaction (personal CRM, all correspondents) or is it scoped
  to business/customers? In the pkm-native frame this becomes a *query-side* filter, not a derive-side one.
- **Performance:** contacts/unanswered aggregate over thousands of artifacts whose metadata lives in
  per-artifact `meta.json`, not catalogue columns. Accept a scan, or add a catalogue index / lean on
  DuckDB `fts`/`vss`?

---

**The throughline:** #2, #6, and part of #7 only exist *if* #1 is "transform." If #1 is "query-layer,"
the CRM collapses to a read-time projection over `email` artifacts plus a small mutable store for #3 —
no pkm substrate change, no cross-component identity leak. So **#1 is the decision to make first**;
most others fall out of it.
