# Getting started — first session

This is the concrete checklist for a fresh agent/session. Read [`CLAUDE.md`](./CLAUDE.md) and
[`ROADMAP.md`](./ROADMAP.md) first. Current phase: **Phase 0** (measure + needle-find, in parallel).

## Prerequisites (verify, don't assume)
- Ollama is up: `curl -s localhost:11434/api/tags | jq '.models[].name'` should list
  `nomic-embed-text` and a chat model.
- OCR ready: `tesseract --list-langs` includes `heb` and `eng`.
- `rga --version` works (ripgrep-all; searches inside PDFs).
- Secrets, if needed, come from gnome-keyring (`secret-tool lookup service env key VARNAME`); never
  read `~/.env`.

## Track A — the needle-finder (minutes)

The repeatable "find any document, including inside scans." The Israeli ID is already known to live at
`/mnt/yo/dropbox/documents/` (`il id.pdf`, `il id.jpg`, `il id back.jpg`, `il id.png`).

```bash
# keyword across PDFs/office/text (rga) + on-demand OCR of images, then grep
scripts/needle.sh "תעודת זהות"      # Hebrew: "identity card"
scripts/needle.sh "teudat"          # transliterations / filename hits
```

If it surfaces the ID files with a snippet, Track A is done. (First image run is slow — it OCRs and
caches into `.ocr-cache/`.)

## Track B — the Karpathy measurement wiki (a weekend)

The point is **measurement**: find out which questions actually need the retrieval "cathedral" before
building it (see the research report's Phase 0).

1. **Assemble the corpus** into `kb/raw/`:
   ```bash
   scripts/build_corpus.sh        # symlinks notes, copies parsed text, OCRs the document images
   ```
   This pulls from `/mnt/yo/dropbox/documents`, `~/yo/notes`, and the already-extracted text in
   `~/yo/parsed` (see [`docs/data-seams.md`](./docs/data-seams.md)).
2. **Compile the wiki.** Open `kb/` in Claude Code; follow [`kb/CLAUDE.md`](./kb/CLAUDE.md): read
   `raw/`, author `wiki/` pages with `[[wikilinks]]`, build an index page.
3. **Interrogate + measure.** Ask ~20 real questions you'd want a PA to answer. For each, note whether
   the wiki answered well. **Log failures to `kb/FAILURES.md`** — that list is the spec for Phase 1
   retrieval. (Don't build retrieval until you have it.)

## Then — Phase 1 (in `~/git/pkm`, not here)

Only after Track B's failure log justifies it. See [`docs/pkm-retrieval-design.md`](./docs/pkm-retrieval-design.md).
Order: (1) amend pkm `SPEC.md` → v0.3.0; (2) `TesseractProducer` **test-first**; (3) migration `0004`
(`chunks`/`embeddings`/`source_origin`); (4) Ollama embeddings + DuckDB hybrid search + `pkm search`;
(5) `pkm-memory` MCP server; (6) source adapters. Respect pkm's TDD + idempotency-double-run rules.

## House rules
- Don't commit unless the owner asks.
- Compose existing systems before writing new code (`CLAUDE.md` → "Prime directive").
- Keep capabilities behind MCP so the interface stays swappable.
