# FAILURES.md — authoring template

`$LIFE_AGENT_KB/FAILURES.md` is the measurement deliverable of the dogfood loop: the questions
the system (`bin/ask-live`) **couldn't** answer well, each tagged with *why* and *what
capability would fix it*. That list is the spec (PRINCIPLES §9) — build nothing it doesn't
demand.

## One entry per miss

```markdown
- **Q:** <the question, as asked>
  **Verdict:** missed | partial
  **Why:** <one of the categories below>
  **Needs:** <the retrieval capability that would have answered it>
```

## Failure categories (the "Why")

- **missing-source** — the answer isn't in the corpus at all (source not yet ingested).
- **unindexed-bulk** — the answer is somewhere in bulk text the index doesn't surface
  (needs better full-text / semantic search over the corpus).
- **needs-fulltext-email-or-chat** — answer lives in email or chat the corpus doesn't cover
  (needs an email/chat adapter + search).
- **un-OCR'd-scan** — answer is in an image/scan that wasn't OCR'd (needs OCR coverage).
- **cross-document-join** — answer requires combining facts across several sources (needs
  retrieval that can gather + synthesise multiple hits).
- **structured-extraction** — answer requires pulling a specific structured field (a date, an
  amount, an ID) from semi-structured text (needs entity/field extraction).
- **freshness** — answer requires the *latest* state, but sources are stale (needs live ingestion).

## Capabilities (the "Needs") — vocabulary

Keyword (FTS) search · semantic (embedding) search · hybrid search · email adapter · chat adapter ·
OCR coverage · structured field extraction · cross-document synthesis · recency-aware retrieval.

Keep entries terse — one line of reasoning each. The value is the *pattern* of misses, which tells
you which capability to build first.
