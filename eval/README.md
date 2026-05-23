# eval/ — the retrieval eval set

The eval set is the Phase-0 question log promoted to a durable, versioned artefact: the questions a
great PA should answer about the owner's life, each with its expected answer's **source citation**.
Authored during Phase 0 (against the wiki), it becomes the regression/quality fixture for the
retrieval substrate in Phase 1, and the seed for any prompt tuning later.

## Where the real file lives

This repo contains only the **schema** (`questions.example.yaml`, illustrative/fake). The real,
populated eval set is **personal** and lives **outside the repo**, at:

```
$LIFE_AGENT_KB/eval/questions.yaml      # the real questions + expected citations
$LIFE_AGENT_KB/eval/phase0_log.md       # Phase-0 ephemera (manual answers, wiki page consulted)
```

(`LIFE_AGENT_KB` default `$HOME/.life-agent/kb` — see [`../docs/kb-schema.md`](../docs/kb-schema.md).)

## Schema

```yaml
questions:
  - id: q-001
    question: "<the question, as a PA would be asked it>"
    expected_citations:
      - path: "raw/ocr/<file>.txt"      # human-readable, for eyeballing during Phase 0
        source_id: "sha256:<hex>"        # the DURABLE identity — see below
    notes: "<freeform>"
    status: answered | partial | missed
```

- **`source_id` is `sha256:` of the original source's RAW bytes** — the same identity pkm assigns a
  source (`sha256sum` of the file, reproducible outside pkm; SPEC-PRINCIPLES §1). This is what makes
  the YAML run unchanged against pkm retrieval in Phase 1, with no rewrite from `raw/…` paths to
  source-ids.
- **For an OCR'd document, `source_id` is the hash of the ORIGINAL image** (e.g. `il id.jpg`), **not**
  the OCR `.txt` derivation. The `.txt` is a derivation; the image is the source.
- Keep the top-level shape minimal and stable. Phase-0-only fields (manual answer, which wiki page
  was consulted) go in `phase0_log.md`, never here — `questions.yaml` is the durable artefact.

## Promotion (Phase 1)

When the retrieval substrate + a runner exist, this set moves into `pkm/evals/` (pkm is where
retrieval is measured). Because citations are content-hashes, no rewrite is needed at promotion.
