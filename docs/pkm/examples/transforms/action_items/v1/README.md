# `action_items` transform (v1) — SPEC §18.6

Extracts concrete, grounded to-do items from an **email** artifact. Each item is
an `action_phrase` plus a `source_quote` copied verbatim from the email; the
producer fails the whole source unless every quote resolves in the email under
§18.5 whitespace-normalised containment (so a weaker model loses recall but
cannot hallucinate an action).

Runs on an **Anthropic haiku model** by default (local Ollama deprecated
2026-08-17), metered under the cost gate; the grounding gate above is what keeps
a model swap safe.

## Install into a knowledge root

The declaration loader resolves `prompt.file` / `output_schema.file` relative to
the root, so copy these into `<root>/{transforms,prompts,schemas}/`:

```
cp transforms/action_items.yaml   <root>/transforms/
cp prompts/action_items_v1.txt    <root>/prompts/
cp schemas/action_items_v1.json   <root>/schemas/
```

## Run

```
pkm transform run action_items            # over every email artifact
pkm transform run action_items --limit 20 # bounded
```

Re-running is a cache hit per (email, declaration) — extraction cost is paid
once. The output artifact is `{format_version: 1, action_items: [...]}`; the
`life_agent` action faculty reads it and files each item to the GTD inbox with a
citation, deduped on a content+grounding *assertion identity* via its own
append-only event ledger (so a prompt bump re-files nothing it already has).

## Model knob

`model:` in `action_items.yaml` selects the backend (SPEC §18.3):

- `provider: anthropic`, `model: "claude-haiku-4-5-20251001"` (default) — local, `cost 0`.
  Pin the tag (never `:latest`); the tag is part of the cache key.
- `provider: anthropic`, `model: claude-haiku-4-5` — cloud fallback (metered);
  add `cost_gate` back to `policies` and ship `policies/cost_gate.py` if you use it.
