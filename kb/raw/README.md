# kb/raw — immutable source corpus

This folder is the **ground truth** the wiki compiles from. It is **read-only** to the compiling
agent and **gitignored** (personal + large). Populate it with `../../scripts/build_corpus.sh`, which
assembles (idempotently):

- `notes/` — symlinks to `~/yo/notes/**.md` (journals, notebooks).
- `parsed-text/` — copies of the already-extracted `.txt` from `~/yo/parsed` (PDFs/office; see
  `docs/data-seams.md`). These cover documents that `pdftotext`/`pandoc` already handled.
- `ocr/` — `tesseract -l heb+eng` output for the **163 image files** in
  `/mnt/yo/dropbox/documents` (jpg/png/tiff) that were never OCR'd — this is how scanned docs like the
  Israeli ID join the corpus. Cached, so re-runs are cheap.
- `docs-index.tsv` — a manifest mapping each corpus file back to its original source path.

Re-run `build_corpus.sh` whenever the underlying data changes; it only adds what's new.

> If a question needs material that *isn't* here (e.g. full email or chat history), don't shovel it
> all in — that's a signal for pkm Phase-1 retrieval. Log it in `kb/FAILURES.md`.
