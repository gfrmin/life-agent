# The knowledge base (`$LIFE_AGENT_KB`) schema

`life-agent` is **the system**; your knowledge lives **on your disk**, not in this repo
(PRINCIPLES §12). The tooling reads a configurable path:

```
LIFE_AGENT_KB   # default: $HOME/.life-agent/kb
```

Point it wherever you keep your stuff (`export LIFE_AGENT_KB=~/.life-agent/kb`). Everything
below lives **under `$LIFE_AGENT_KB`**. None of it is committed here — it is personal and may
be large. (The pkm content-addressed cache + DuckDB catalogue are separate, at the paths named
in your `PKM_CONFIG` yaml.)

## Layout

- **`config/`** — the machine's declared truth:
  - `data-sources.yaml` — which roots to ingest (the real registry; fake schema in
    `config/data-sources.example.yaml` in-repo). Read by `scripts/data_source_registry.py` /
    `scripts/ingest_sources.py`.
  - `mail-corpus.yaml`, `comparison-corpus.yaml` — corpus declarations for mail ingestion and
    the frozen comparison.
- **`pii-patterns.txt`** — the private denylist for the fail-closed PII guard
  (copy from `config/pii-patterns.txt.example`; see `CONTRIBUTING.md`).
- **`FAILURES.md`** — the dogfood failure log: one entry per question the system couldn't
  answer well ([`failures-template.md`](./failures-template.md)). **This list is the spec**
  (PRINCIPLES §9): Phase 1.5 builds only what it demands.
- **`eval/`** — the answer-grounded eval sets and logs (`questions.yaml`,
  `scripts/run_eval.py` output, dogfood session notes) and `eval/comparison/` — the frozen
  Phase-0-vs-Phase-1 comparison record (snapshot, grades, report; see `SPEC-comparison.md`).
- **`tasks/`** — the GTD act layer: `events.jsonl` (the append-only event ledger — **the**
  source of truth) and `gtd.db` (the SQLite read-model, a rebuildable fold — safe to delete).
- **`jarvis/jarvis.db`** — the legacy pre-event-sourcing GTD store, kept **read-only** as a
  natural pre-cutover snapshot (`scripts/migrate_jarvis_to_events.py`).
- **`ocr-cache/`** — on-demand OCR results from `scripts/needle.sh` (cached, re-used).
- **`owner.md`** — the owner profile (`bin/ask-live "/tell …"`): the identity lens that pins
  who "I" is in answers.
- **`docs/data-seams.md`** — the verified, machine-specific data map (which data lives where on
  this machine). Out-of-tree because it names personal paths.
- **`raw/`, `wiki/`, `notes/`** — **legacy Phase-0 artifacts.** The compiled-wiki approach was
  measured and retired (PRINCIPLES §14; `SPEC-comparison.md` is the frozen record). These stay
  only as archives; no tooling writes them.

## Conventions

- Citations are mandatory on every answer path; provenance is structural (PRINCIPLES §8).
- Dates absolute (YYYY-MM-DD). Names as the owner uses them.
- Everything here is sensitive personal data — it stays under `$LIFE_AGENT_KB`, never in the
  repo, never pushed anywhere.
