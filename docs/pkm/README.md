# pkm

A content-addressed extraction cache and catalogue for personal knowledge
management.

`pkm` ingests source documents, routes each one through format-appropriate
extractors, and writes the results to an append-only content-addressed
filesystem cache indexed by a DuckDB catalogue. Running the same command
twice is a no-op: cache keys are derived deterministically from the input
hash, the producer name, the producer version, and the producer's config
hash, so everything is reproducible and every artifact is reconstructible.

## Status

Early foundation. The current scope is the extraction layer — sources,
routing, producers, cache, and catalogue. LLM transforms, query planning,
retrieval, and UI are explicitly out of scope until the foundation is
stable. See `SPEC.md` for the versioned contract.

## Install

Requires Python 3.13 and [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
```

External tools used by producers: `pandoc` (system binary), plus the
Python packages `docling` and `unstructured` (pulled in by `uv sync`).

## CLI

```sh
uv run pkm migrate              # apply pending schema migrations
uv run pkm ingest               # register sources from sources.yaml
uv run pkm extract              # run extractors over registered sources
uv run pkm rebuild-catalogue    # rebuild the catalogue from on-disk cache
```

Configuration lives in a single `config.yaml` (default
`~/.local/share/pkm/config.yaml`). There are no environment-variable overrides
and no per-flag config (see `SPEC.md` §14.6).

## Architecture

    ingest  →  route  →  extract  →  (cache + catalogue)

- **cache** — append-only filesystem store under `<root>/cache/<aa>/<bb…>/`,
  keyed by SHA-256 of `{input_hash, producer_name, producer_version,
  producer_config_hash}`.
- **catalogue** — mutable DuckDB database indexing the cache; rebuildable
  from it.
- **producers** — three today (`pandoc`, `docling`, `unstructured`), each
  implementing the `Producer` protocol and declaring its `handled_formats`.

`SPEC.md` is the authoritative contract. `CLAUDE.md` contains the
engineering rules this repo is built under (content-addressing discipline,
idempotency, no premature abstraction, first-principles debuggability).

## Development

```sh
uv run pytest                   # full test suite
uv run ruff check src tests     # lint
uv run mypy                     # strict type-check
```

## Licence

AGPL-3.0-or-later. See `LICENSE`.
