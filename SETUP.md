# Setup — from clone to a cited answer

life-agent answers questions about your own life and **cites the document each
fact came from**. Facts are verified, at answer time, to actually appear in the
source they cite (see [Reliability](#reliability)). This guide gets you from a
clone to a cited answer on the bundled synthetic corpus in a few minutes, then
shows how to point it at your own data. (The why behind the design:
[`PRINCIPLES.md`](./PRINCIPLES.md).)

## 1. Prerequisites

**Required**

- [`uv`](https://docs.astral.sh/uv/) — Python env + runner. It installs the
  pinned Python (3.13) and all dependencies for you; there is **no second repo
  to clone** (pkm lives in this one, under `src/pkm`).
- `pandoc` — extracts text from documents. The sample corpus is markdown, so
  this is all the sample needs. (`apt install pandoc` · `brew install pandoc` ·
  `sudo pacman -S pandoc`.)
- `git`.

**Required only to *ask* (not to build the corpus)**

- An `ANTHROPIC_API_KEY` — used by `bin/ask-live` to synthesise the answer from
  the retrieved, cited sources. Put it in your shell (`export ANTHROPIC_API_KEY=…`),
  in a gitignored `.env`, or in gnome-keyring if you have one. Building and
  searching the corpus needs **no** key.

**Optional (improve coverage of your *own* data later — not needed for the sample)**

- **Ollama** + `nomic-embed-text` — local embeddings for semantic recall. The
  live `bin/ask-live` path is BM25 keyword search and needs neither.
- **tesseract** (`-l heb+eng` etc.) — OCR for scanned images / image-only PDFs.
- **docling** / **unstructured** — already installed as Python deps; only run
  when you ingest PDFs / office / spreadsheet formats and declare them in config.
- **plocate** — only for the `--report`/`--discover` data census.

## 2. Try the sample corpus (synthetic — no real data)

```bash
git clone <this-repo-url> life-agent && cd life-agent
scripts/bootstrap-sample.sh
```

`bootstrap-sample.sh` builds a throwaway corpus from
[`examples/sample-corpus/`](./examples/sample-corpus/) (the fictional Ada
Lovelace) under `examples/.sandbox/` and prints the commands to query it:

```bash
export LIFE_AGENT_KB=$PWD/examples/.sandbox/kb
export PKM_CONFIG=$PWD/examples/.sandbox/pkm.yaml
export ANTHROPIC_API_KEY=sk-ant-...        # your key

bin/ask-live "what is my national ID number?"
bin/ask-live "when does my passport expire?"
bin/ask-live "how do I make money?"
```

Each answer carries a `[n]` citation into a numbered source document. See
[`examples/README.md`](./examples/README.md) for the full list and the
**identity-guard demo** — proof that the partner's decoy record is never
reported as yours.

## 3. Point it at your own data

Your data and answers never enter the repo — they live under `$LIFE_AGENT_KB`
(default `~/.life-agent/kb`). Set that and `$PKM_CONFIG` once (copy
[`.env.example`](./.env.example) to `.env`), then:

```bash
# a) the pkm content store + which extractors you use
cp config/pkm.example.yaml ~/.config/life-agent/pkm.yaml
$EDITOR ~/.config/life-agent/pkm.yaml        # set root_dir + your pandoc version

# b) which folders to ingest
mkdir -p "$LIFE_AGENT_KB/config"
cp config/data-sources.example.yaml "$LIFE_AGENT_KB/config/data-sources.yaml"
$EDITOR "$LIFE_AGENT_KB/config/data-sources.yaml"   # point roots at your dirs

# c) build the memory: register → extract → chunk → make searchable
uv run --project . pkm --config "$PKM_CONFIG" migrate
uv run --project . python scripts/ingest_sources.py --extract --chunk

# d) teach it who you are (stops other people's docs being read as yours)
bin/ask-live "/tell My name is <you>"
bin/ask-live "/tell My national ID is <id>"

# e) ask
bin/ask-live "when does my passport expire?"
```

`ingest_sources.py --chunk` finishes by rebuilding the FTS index the live query
reads, so new chunks are searchable immediately — no separate `rebuild-index`
step. (Running the `pkm` primitives by hand? Then `pkm rebuild-index` after
`pkm chunk --backfill` is on you.)

## 4. Optional: the task half (Telegram + email→GTD)

Everything above is the **know** half — ask, get a cited answer. There is also
an **act** half: a GTD task list you manage in plain language over Telegram,
which your email can auto-file into. It is optional and layers on separately.

```bash
# a) a Telegram bot: talk to @BotFather, /newbot, copy the token.
#    Your numeric user id: message @userinfobot and it replies with it.
export TELEGRAM_TOKEN=123456:ABC...
export JARVIS_USER_ID=<your numeric id>      # the bot answers only this user

# b) a local chat model for the language→intent step (no cloud call)
ollama pull qwen2.5:7b-instruct              # any small instruct model works
export OLLAMA_MODEL=qwen2.5:7b-instruct      # default: qwen3.5:9b

# c) run the bot (a long-running poller — supervise it however you like:
#    a systemd --user service, tmux, whatever you already use)
uv run --project . python -m life_agent.reach.jarvis
```

Message it `help` for what it understands (`add buy milk`, `list inbox`,
`done 3`, …). Secrets resolve from the environment first, then gnome-keyring
(`secret-tool`) if you have one — plain `export` is fine.

**Email→GTD (optional, on top).** Once your mail is ingested into pkm (declare
your maildir in `data-sources.yaml`, step 3), `bin/mail-to-tasks` extracts
**grounded** action items from new mail with the local model and files each one
once into the GTD inbox, cited `[src:email <Message-ID>]`; you triage in
Telegram. `--dry-run` previews without writing anything. Meant to run from a
timer after your mail sync.

**Morning digest (optional).** `uv run --project . python -m
life_agent.reach.digest` sends a today / overdue / inbox summary through the
same bot — timer material.

Internals (the event ledger, why the SQLite is safe to delete):
[`docs/act-layer-events.md`](./docs/act-layer-events.md).

## 5. Day to day

You interact in exactly **two places**; everything else runs on timers.

- **To know — `bin/ask-live`.** One-shot for a quick question; run it bare for
  a REPL session. One line grammar, identical in both: a plain question,
  `/since 2026-01-01 …`, `/until …`, `/recent …`, `/tell <fact about you>`,
  `/derive`. The full grammar and its rules:
  [`docs/interaction-contract.md`](./docs/interaction-contract.md).
- **To act — the Telegram bot.** Capture and triage tasks in plain language;
  say `help` for the vocabulary.

**The verdict prompt is how it gets better.** After each REPL answer, ask-live
asks `[g]ood / [b]ad / Enter` — one bit, logged to a dated journal at
`$LIFE_AGENT_KB/eval/dogfood-YYYY-MM-DD.md` (never the repo). Misses that
matter get promoted to `$LIFE_AGENT_KB/FAILURES.md` (template:
[`docs/failures-template.md`](./docs/failures-template.md)); the failure log —
not speculation — is what drives what gets built next.

## Reliability

The promise is **cited, no-hallucination** answers, and it is structural, not
aspirational:

- **Verbatim facts are gated.** Before an answer is shown, a deterministic guard
  (`scripts/citation_guard.py`) checks that every value-bearing cited fact (IDs,
  numbers, proper nouns) actually appears in the source it cites. A fact that
  doesn't is flagged `⚠ unverified` rather than presented as trusted.
- **Weak retrieval abstains.** If nothing in your corpus is a strong enough
  match, the assistant says so instead of guessing (tune with
  `LIFE_AGENT_SCORE_FLOOR` / `LIFE_AGENT_MIN_HITS`).
- **Identity is pinned.** An owner profile (`/tell`) is the lens for who "I" is,
  so a relative's or co-signer's document is never attributed to you.

What is **not** guaranteed: facts pkm extracted wrong upstream (e.g. OCR
garble), and the *prose* faithfulness of paraphrase — that is **measured**
(`scripts/run_eval.py --synthesis` reports hallucination / grounded / abstention
rates), not hard-gated.

## Troubleshooting

- **`pandoc is not installed`** — install it (see prerequisites); the sample
  needs it.
- **`ProducerVersionMismatchError`** — your `config.yaml` `extractors.<tool>.version`
  must equal the installed tool's version exactly. Run `pandoc --version | head -1`
  (or `tesseract --version`) and update it. `bootstrap-sample.sh` does this for
  you for the sample.
- **`corpus locked by extraction`** — a build is holding the catalogue; retry the
  query in a moment (reads are read-only and never block a build).
- **An answer abstains and you expected a hit** — retrieval was below the
  relevance floor. Lower `LIFE_AGENT_SCORE_FLOOR`, widen context with
  `bin/ask-live --k 12`, or check the doc was ingested (`pkm --config "$PKM_CONFIG"
  search "<term>"`).
- **`ANTHROPIC_API_KEY not found`** — only needed to ask; export it or add it to
  `.env`. Building/searching the corpus does not need it.
