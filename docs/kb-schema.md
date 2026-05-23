# The knowledge base (`kb/`) schema — Karpathy-style LLM wiki

`life-agent` is **the system**; your knowledge lives **on your disk**, not in this repo. The tooling
(`scripts/build_corpus.sh`, `scripts/needle.sh`, `bin/ask`) reads a configurable path:

```
LIFE_AGENT_KB   # default: $HOME/.life-agent/kb
```

Point it wherever you keep your stuff (`export LIFE_AGENT_KB=~/yo/life-agent-kb`). Everything below
describes the layout the tooling expects **under `$LIFE_AGENT_KB`**. None of it is committed here —
it is personal and may be large.

## The two folders

- **`raw/`** — immutable source material, **read-only**. Documents, notes, OCR'd scans, and any
  already-extracted text. Populate it with `scripts/build_corpus.sh`. Never edit `raw/`; treat it as
  ground truth.
- **`wiki/`** — markdown the agent authors; the compiled, queryable second brain. One page per
  salient entity/topic, linked with `[[wikilinks]]`.

## The loop

1. **Ingest** — read across `raw/` (start with the smallest, highest-signal sources — notes and
   OCR'd scans — then the bulk extracted text).
2. **Compile** — write/refresh `wiki/` pages:
   - `wiki/index.md` — the map: links to the main entity/topic pages.
   - `wiki/<entity>.md` — people, organisations, accounts, recurring topics. Top of each page: a
     2–4 line summary; then facts as bullets; **cite the source** as `(raw/<path>)`; cross-link
     related pages with `[[other-page]]`.
   - Prefer many small pages over few big ones. Keep pages current; supersede, don't duplicate.
3. **Query** — to answer a question, read `wiki/index.md` + the 3–5 most relevant pages (and, only if
   needed, the cited `raw/` files). Answer **with citations**.
4. **Lint** — flag stale claims, orphan pages (nothing links to them), and dead `[[links]]`.

## Measurement (the actual deliverable)

Keep a `FAILURES.md` at `$LIFE_AGENT_KB/FAILURES.md`. For every question you couldn't answer well
from the wiki, log one line per the categories in [`failures-template.md`](./failures-template.md):
the question, why it failed, and what retrieval capability would have answered it. **That list is the
spec for the retrieval substrate.** Do not build retrieval before you have it.

## Conventions

- Citations are mandatory; never assert a fact without a `(raw/...)` source.
- Dates absolute (YYYY-MM-DD). Names as the owner uses them.
- The wiki contains sensitive personal data — it stays under `$LIFE_AGENT_KB`, never in the repo,
  never pushed anywhere.
