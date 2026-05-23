# Data seams — verified integration map

Verified by exploration on 2026-05-23. Read this before re-exploring; paths/counts are concrete.
All personal data roots under `/mnt/yo` (`~/yo` → `/mnt/yo`; `~/git` → `~/yo/git`).

## Email — `~/mail` (= `/mnt/yo/mail`)
- **Maildir**, ~40 GB, **notmuch 0.40** index live (`notmuch count "*"` ≈ **724,615**). Synced by
  `mbsync.timer`. One Fastmail account; Archive subfoldered by project.
- **No Python `notmuch` bindings** (`import notmuch` fails). Ingest via subprocess:
  - enumerate: `notmuch search --output=files --format=json "*"`
  - bodies+headers: `notmuch show --format=json <query>`
- For pkm: the **unstructured** producer already reads `.eml`; an email source-adapter can hand it raw RFC822 bytes.

## Chat — Matrix
- **Tuwunel** homeserver (Docker), API `http://localhost:6167`, store at
  `~/git/matrix-local/data/tuwunel` (**RocksDB — opaque**, don't parse directly).
- **`matrix-archiver`** writes a **SQLite** archive at
  **`~/git/matrix-local/data/archiver/archive.db`** (~88 MB, live). **This is the ingestion path** —
  query with the stdlib `sqlite3`. ~600 bridged rooms (WhatsApp/Telegram/Signal/Meta/Discord).
- Skills exist: `~/.claude/skills/matrix-messages` (API search), `matrix-voice-transcribe` (local Whisper).
  Auth (if using the API): `POST localhost:6167/_matrix/client/v3/login`, user `guy`, password in
  `~/git/matrix-local/.env`.

## Tasks — `~/git/jarvis-lite`
- SQLite `jarvis.db`; `systemd --user jarvis.service` running. **`user_id = 12365873`** (pass to every call).
- **13 MCP tools** in `mcp_server.py`: `add_task`, `complete_task`, `delete_task`, `move_task`,
  `mark_today`, `clear_today`, `get_tasks`, `get_today_tasks`, `get_tasks_by_tag`,
  `get_tasks_due_today`, `get_overdue_tasks`, `get_task_counts`, `get_completed_this_week`.
- GTD lists inbox/next/scheduled/someday; `@tags`; `is_today` focus flag.

## Documents — `/mnt/yo/dropbox/documents` (457 files)
- **266 PDF, 163 image (jpg/jpeg/png/tiff/heic), ~28 office.**
- **Israeli ID confirmed:** `il id.pdf`, `il id.jpg`, `il id back.jpg`, `il id.png` (family IDs in
  subdirs like `a5-2024/`). Also HK IDs, passports, tax/bank/medical/degree docs.

## OCR already done — `/mnt/yo/parsed` (~4391 files)
- `.json` + `.txt` pairs. Schema: `{source_path, source_hash, extracted_at, extractor, char_count, …}`.
- Extractors: `pdftotext`, `pandoc`. **Covers PDFs/office only — the 163 images are NOT OCR'd.**
  → the images (incl. the ID scans) are exactly what the Tesseract path adds.
- To reuse: read `.json`, join `source_path` back to the document, use the `.txt` text.

## Contacts
- Local VCF dump `/mnt/yo/Contacts` (208 files) is **stale (2023)**. **Fastmail CardDAV is the source
  of truth** (4,727 deduped Apr 2026): `https://carddav.fastmail.com/dav/addressbooks/user/<acct>/Default/`,
  cred in keyring `service=carddav`. Skill: `~/.claude/skills/fastmail-contacts`.

## Calendar
- No local tool (no khal/vdirsyncer). Options: Fastmail **CalDAV** (same keyring cred) or the
  **Google Calendar MCP** connector available in Claude Code (OAuth on first use).

## Email send
- **`msmtp` configured** (`~/.msmtprc`, `passwordeval` from keyring; Fastmail SMTP). Ready to use.
- Reference JMAP client (Julia): `~/git/credence/apps/julia/email_agent/jmap_client.jl`
  (token in keyring `service=jmap`).

## Local tooling (what's installed)
- **Ollama** (GPU, RTX 4060): `nomic-embed-text` (768-dim), `qwen2.5:7b-instruct`, `qwen3.5:9b`,
  `llama3.1`, 2 vision models. `localhost:11434`.
- **OCR/docs:** `tesseract 5.5.2` (heb+eng), `pdftotext`, `exiftool`, ImageMagick 7, ghostscript, libreoffice.
- **Search/DB:** `rg 15.1`, `rga 0.10.10`, `sqlite3 3.53` (FTS5), **DuckDB 1.5.2** (`fts` + `vss` both load), `pandoc`, `jq`.
- **Langs:** Python 3.14 + `uv`; Node 26 + `pnpm`/`bun`; Julia.
- **Out of scope for v1:** PhotoPrism (1.2M photos, 52 GB) and the **661 GB encrypted `/mnt/yo/more`** (needs keys).
