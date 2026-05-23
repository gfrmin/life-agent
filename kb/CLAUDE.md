# kb/ — the LLM knowledge base (Karpathy-style)

This is the **Phase-0 measurement wiki**. Its job is to answer real questions about the owner's life
*and* to reveal — via what it can't answer — which questions truly need the retrieval "cathedral"
(pkm). Near-zero code: you (the agent) are the compiler.

## The two folders
- **`raw/`** — immutable source material, **read-only for you**. Documents, notes, OCR'd scans, and
  the already-extracted text from `~/yo/parsed`. Populate it with `../scripts/build_corpus.sh`.
  Never edit `raw/`; treat it as ground truth. (Gitignored — personal/large.)
- **`wiki/`** — markdown you author; **read-only for the human**. One page per salient entity/topic,
  linked with `[[wikilinks]]`. This is the compiled, queryable second brain.

## The loop
1. **Ingest** — read across `raw/` (start with `raw/notes/` and `raw/ocr/`, then `raw/parsed-text/`).
2. **Compile** — write/refresh `wiki/` pages:
   - `wiki/index.md` — the map: links to the main entity/topic pages.
   - `wiki/<entity>.md` — e.g. people, organisations, accounts, recurring topics. Top of each page:
     a 2–4 line summary; then facts as bullets; **cite the source** as `(raw/<path>)`; cross-link
     related pages with `[[other-page]]`.
   - Prefer many small pages over few big ones. Keep pages current; supersede, don't duplicate.
3. **Query** — to answer a question, read `wiki/index.md` + the 3–5 most relevant pages (and, only if
   needed, the cited `raw/` files). Answer **with citations**.
4. **Lint** — flag stale claims, orphan pages (nothing links to them), and dead `[[links]]`.

## Measurement (the actual deliverable)
Keep **`../kb`'s sibling `FAILURES.md`** (i.e. `kb/FAILURES.md`). For every question you couldn't
answer well from the wiki, log one line: the question, why it failed (missing source? needs full-text
search over email/chat? needs a scan that wasn't OCR'd? needs cross-document join?), and what
retrieval capability would have answered it. **That list is the spec for pkm Phase 1.** Do not build
retrieval before you have it.

## Conventions
- Citations are mandatory; never assert a fact without a `(raw/...)` source.
- Dates absolute (YYYY-MM-DD). Names as the owner uses them.
- This wiki may contain sensitive personal data — it stays local; do not push it anywhere.
