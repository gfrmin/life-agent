# Sample corpus — try life-agent before you point it at your own life

Everything under [`sample-corpus/`](./sample-corpus/) is **100% synthetic**. The
demo owner is **Ada Lovelace**; her partner is **Charles Babbage**. Every name,
number, ID, address, and email is invented — the IDs are deliberately
checksum-invalid and all emails use `@example.com`, so the repo's own PII guard
(`.githooks/pii_check.py`) passes on them.

The point of the sample is to let a newcomer get a **cited answer in minutes**,
on data that isn't theirs, before deciding whether to ingest their own.

## One command

```bash
scripts/bootstrap-sample.sh
```

That builds a throwaway sandbox under `examples/.sandbox/` (git-ignored): it
runs the pkm pipeline (`migrate → ingest → extract → chunk → rebuild-index`)
over the sample corpus and prints the exact `bin/ask-live` command to ask it
questions. Re-running is safe — the content-addressed cache makes it idempotent.

The sample is **markdown-only and pandoc-only** on purpose: it needs `pandoc`
and nothing else — no Ollama, no embeddings, no OCR/tesseract, no API key for
the build itself. (Asking questions with `bin/ask-live` does need an
`ANTHROPIC_API_KEY` for the answer-synthesis step — see [`SETUP.md`](../SETUP.md).)

## Questions to try

Grounded answers, each citable to one of the sample documents:

- `what is my national ID number?` → **123456789** (from `identity.md`)
- `when does my passport expire?` → **18 April 2031** (from `passport.md`)
- `how do I make money?` → consulting retainer + tutoring + royalties (`employment.md`)
- `am I employed or self-employed?` → self-employed contractor (`employment.md`)
- `when does my car insurance renew?` → **1 September 2026** (from `vehicle.md`)
- `when does my tenancy renew?` → **1 August 2027** (from `tenancy.md`)

## The identity-guard demo (the no-confusion promise)

`partner-charles.md` is a decoy: a medical letter for Ada's partner, Charles
Babbage, whose national ID is **987654321**. A naive search-and-summarise
assistant, asked *"what is my ID?"*, can surface Charles's letter and report
**his** ID as yours — a real failure this project is built to avoid.

`bootstrap-sample.sh` seeds the owner profile (`owner.md`) with *"I am Ada
Lovelace, national ID 123456789"*. That profile is injected into every answer as
the lens for who "I"/"my" means, so the assistant attributes 123456789 to you
and treats 987654321 as Charles's — not yours. Ask both:

- `what is my national ID number?` → **123456789** (Ada's — yours)
- `what is Charles's ID number?` → **987654321** (his, clearly labelled as his)

## Mapping this to your own data

When you're ready, copy [`../config/data-sources.example.yaml`](../config/data-sources.example.yaml)
to `$LIFE_AGENT_KB/config/data-sources.yaml`, point its roots at your real
folders, and run `scripts/ingest_sources.py --extract --chunk` (then
`pkm rebuild-index`). See [`SETUP.md`](../SETUP.md) for the full path.
