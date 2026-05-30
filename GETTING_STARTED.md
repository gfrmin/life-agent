# Getting started — first session

This is the concrete checklist for a fresh agent/session. Read [`CLAUDE.md`](./CLAUDE.md) and
[`ROADMAP.md`](./ROADMAP.md) first.

**Status:** Phase 0 **and** the Phase 1 retrieval substrate are done — pkm `SPEC-v0.3.0`, migration
`0004` (chunks+embeddings), `pkm search` + the `pkm-memory` MCP server, and the **configurable data
layer** (`scripts/data_source_registry.py` census + `scripts/ingest_sources.py` promote, driven by a
`data-sources.yaml` registry over plocate). The **live corpus is ingested and searchable** via
`pkm-memory`: mail INBOX+Sent (8288 src / 37,439 chunks), documents (364 / 3,786), notes (69 / 211).
To see what's on the system, run `python scripts/data_source_registry.py --report`; to add a source,
edit `$LIFE_AGENT_KB/config/data-sources.yaml` and re-run `scripts/ingest_sources.py`. **Next is a
dogfood week** — use it, log misses to `$LIFE_AGENT_KB/FAILURES.md`, re-rank — *then* Phase 2 (the pi
MCP-bridge). Build only what the failure log demands.

**Knowledge lives outside this repo**, at `$LIFE_AGENT_KB` (default `$HOME/.life-agent/kb`) — see
[`docs/kb-schema.md`](./docs/kb-schema.md). `export LIFE_AGENT_KB=...` before running the tooling.

## Prerequisites (verify, don't assume)
- Ollama is up: `curl -s localhost:11434/api/tags | jq '.models[].name'` should list
  `nomic-embed-text` and a chat model.
- OCR ready: `tesseract --list-langs` includes `heb` and `eng`.
- `rga --version` works (ripgrep-all; searches inside PDFs).
- Secrets, if needed, come from gnome-keyring (`secret-tool lookup service env key VARNAME`); never
  read `~/.env`.

## Track A — the needle-finder (minutes)

The repeatable "find any document, including inside scans." The seed example is an ID-card scan in
your documents directory (set `DOCS_DIR`); the finder OCRs it on demand and greps the corpus.

```bash
# keyword across PDFs/office/text (rga) + on-demand OCR of images, then grep
scripts/needle.sh "תעודת זהות"      # Hebrew: "identity card"
scripts/needle.sh "teudat"          # transliterations / filename hits
```

If it surfaces the ID files with a snippet, Track A is done. (First image run is slow — it OCRs and
caches into `$LIFE_AGENT_KB/ocr-cache/`.)

## Track B — the Karpathy measurement wiki (a weekend)

The point is **measurement**: find out which questions actually need the retrieval "cathedral" before
building it (see the research report's Phase 0).

1. **Assemble the corpus** into `$LIFE_AGENT_KB/raw/`:
   ```bash
   scripts/build_corpus.sh        # symlinks notes, copies parsed text, OCRs the document images
   ```
   This pulls from your documents / notes / extracted-text directories (set `DOCS_SRC`, `NOTES_SRC`,
   `PARSED_SRC`; the verified per-machine data map lives at `$LIFE_AGENT_KB/docs/data-seams.md`).
2. **Compile the wiki.** Follow [`docs/kb-schema.md`](./docs/kb-schema.md): read `$LIFE_AGENT_KB/raw/`,
   author `$LIFE_AGENT_KB/wiki/` pages with `[[wikilinks]]`, build an index page.
3. **Interrogate + measure.** Ask ~20 real questions you'd want a PA to answer (use `bin/ask`). For
   each, note whether the wiki answered well; record them in `$LIFE_AGENT_KB/eval/questions.yaml`.
   **Log failures to `$LIFE_AGENT_KB/FAILURES.md`** ([`docs/failures-template.md`](./docs/failures-template.md))
   — that list is the spec for Phase 1 retrieval. (Don't build retrieval until you have it.)

## Then — Phase 1 (in `~/git/pkm`, not here)

Spec'd by `$LIFE_AGENT_KB/FAILURES.md`. See [`docs/pkm-retrieval-design.md`](./docs/pkm-retrieval-design.md).
**Already landed (Phase-0 foundation):** pkm `SPEC-v0.3.0.md` drafted; cache key hardened to
`schema_version: 3`; migration `0004` (`artifact_chunks` + `embedding FLOAT[768]` + `source_origin`).
**Remaining, in order:** (1) `TesseractProducer` **test-first** — with image preprocessing
(deskew/contrast/upscale), since the failure log shows raw ID-card OCR is the #1 gap; (2) Ollama
embeddings + DuckDB `fts`+`vss` hybrid search + `pkm search`; (3) `pkm-memory` MCP server; (4) source
adapters (email/chat). Respect pkm's SPEC-first + TDD + idempotency-double-run rules.

## House rules
- Don't commit unless the owner asks.
- Compose existing systems before writing new code (`CLAUDE.md` → "Prime directive").
- Keep capabilities behind MCP so the interface stays swappable.
