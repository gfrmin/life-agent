# The interaction contract

What the human can say to this system, what it says back, and the rules that keep that
surface **clear, no more than necessary, and free of redundancy**. This governs every
human-facing surface of the **reach** step of derive → project → reach
([`PRINCIPLES.md`](../PRINCIPLES.md) §6) plus the command-line surfaces around the KB.
Code conforms to this document; when they disagree, one of them is wrong on purpose and
the fix starts here.

## Modes — one surface per mode

| mode | surface | direction | entrypoint |
|------|---------|-----------|------------|
| **act** | Telegram / Jarvis NLU → GTD | two-way | `python -m life_agent.reach.jarvis` |
| **know** | ask-anything REPL with citations | two-way | `bin/ask-live` → `scripts/ask.py` |
| **push** | digest + nudges | outbound only | `life_agent.reach.digest`, `mail_to_tasks` notify |
| **plumbing** | pkm primitives | command | `pkm <subcommand>` |
| **porcelain** | compositions of primitives | command | `scripts/ingest_sources.py`, `scripts/mail_to_tasks.py`, `scripts/mail_bridge.py` |

A capability lives in exactly one mode. Mutating a task is *act*; asking about your life is
*know*; *push* never parses replies (a reply to a digest is just a new *act* message); a
*porcelain* script never does anything a sequence of *plumbing* commands couldn't.

## Invariants

1. **One grammar per concept.** The temporal predicate, teaching a fact, quitting — each has
   exactly one spelling, and it is the same spelling in the REPL and in one-shot argv.
   *Named exception:* quitting accepts `/q`, `/quit`, `/exit`, and EOF. It is the
   highest-frequency, zero-ambiguity command; erroring on `/quit` to preserve a principle
   buys nothing. The exception is documented here, not smuggled.
2. **Paraphrase tolerance is not redundancy.** An NLU surface (Jarvis) accepts free phrasing
   — "done 3", "complete #3", "finished the milk one" — but everything maps onto ONE
   canonical intent vocabulary (the table below). Many phrasings, one vocabulary.
3. **Nothing vanishes, nothing is silent.** Generalises the doc_date coverage contract
   (pkm SPEC §18.12): a date filter names what it excluded; an ambiguous reference is
   surfaced as a question, never resolved by an arbitrary pick; an unknown command is a loud
   error naming the grammar, never silently reinterpreted as something else.
4. **Help renders from the vocabulary it documents.** The NLU prompt and the help reply are
   generated from one table (`jarvis.INTENTS`); the REPL banner, usage errors, and `--help`
   epilog from another (`ask.GRAMMAR`). A vocabulary table nothing enforces will quietly
   diverge, so drift-gate tests assert every entry dispatches and appears in both renderings.
5. **Flags configure the run; the line is the language.** argv flags are run-configuration
   and debug knobs only (`--k`, `--no-expand`, `--no-cache`). A concept the line can express
   is never also a flag — one grammar, two contexts (REPL prompt and one-shot argv).

## know — ask-live

| form | meaning |
|------|---------|
| `QUESTION` | cited answer over the live corpus (abstains below the relevance floor rather than guess) |
| `/recent QUESTION` | rank dated sources newest-first — **ranks only, no implied bound, excludes nothing** |
| `/since YYYY-MM-DD QUESTION` | admit sources dated on/after; the excluded are named, not dropped |
| `/until YYYY-MM-DD QUESTION` | admit sources dated on/before |
| `/tell FACT` | record an authoritative owner fact (corpus-free: works even while extraction holds the catalogue lock) |
| `/derive` | materialise the doc_dates the last answer named as underived, then re-ask |
| `/q` (or `/quit`, `/exit`, EOF) | quit |

One-shot is the same grammar: `bin/ask-live "/since 2026-01-01 what invoices arrived?"`.

**Temporal composition.** `/since` and `/until` are bounds: together they form a range, each
may appear at most once. `/recent` is a ranking directive and stands alone — applying any
bound already ranks admitted sources newest-first (`life_agent.core.temporal.apply_temporal`
sorts whenever a predicate is present and excludes nothing absent bounds), so `/recent`
combined with a bound is pure redundancy and is rejected with the rule spelled out. Likewise
rejected, never guessed at: a duplicated prefix, `/since` later than `/until` (an empty
range is almost certainly a typo), an unparseable date, an unknown slash-command.

**Flags** (run-config only): `--k N` retrieval width, `--no-expand` raw-question BM25
baseline, `--no-cache` recompute every stage.

**After each answer:** sources are listed with scores; a temporal answer carries the
nothing-vanishes footer (admitted / excluded-by-date / undated / not-yet-derived, each set
named with its remedy); unverified citations are flagged by the citation guard; then one
verdict key — `g`ood / `b`ad / `n`ote / Enter to skip — logs to the dogfood journal that
feeds `FAILURES.md`.

## act — Jarvis

Free-text Telegram messages, parsed by a local model into one of these intents
(`jarvis.INTENTS`, the single source for the NLU prompt and the help reply):

| intent | canonical phrasing | reply shape |
|--------|--------------------|-------------|
| `add` | "buy milk", "call dentist @health", "schedule X for next tuesday" | `Added [id] TEXT to #list (due D)` |
| `complete` | "done 3", "done buy milk" | `Completed: TEXT` |
| `delete` | "delete 5" | `Deleted: TEXT` |
| `move` | "move 5 to next" | `Moved [5] TEXT to #next` |
| `mark_today` | "today 3", "focus on 3" | `Marked for today: [3] TEXT` |
| `clear_today` | "clear today" | `Cleared today flag from N tasks.` |
| `list` | "show inbox", "show all", "today", "overdue", "show @work" | `[id] ★ TEXT #list (due D)` per task |
| `counts` | "counts", "stats" | per-list counts |
| `completed` | "completed" | tasks completed this week |
| `help` | "help", "?" | the vocabulary above, rendered from `INTENTS` |
| `chat` | anything not about tasks | a brief reply; never mutates |

**Ambiguity rule** (invariant 3): completing by text when several active tasks match lists
the matches — `N tasks match 'call' — which one? Say 'done <id>'` — and completes nothing.
`store.resolve_by_text` returns every match; the arbitrary-first-pick is gone.

Lists are `inbox | next | scheduled | someday`; views are `all | today | overdue | @tag`.
Truth is the append-only event ledger; every reply reflects the fold
([`act-layer-events.md`](./act-layer-events.md)).

## push — outbound only

The morning **digest** (today's focus, overdue, due today, up-next, inbox count) and the
**mail nudge** ("Added N task(s) to your GTD inbox from email") are broadcasts. They parse
nothing; acting on them is an ordinary *act* message. One inbox state, two cadences —
arrival nudge and morning summary — not two sources of truth.

## plumbing and porcelain

`pkm` subcommands are primitives with stable exit codes (0 ok · 1 failure · 2 config error ·
3 approval required): `ingest → extract → chunk → rebuild-index` build the corpus;
`search` debugs raw retrieval (answers belong to *know*); `derive` resolves one target
demand-driven, `transform run` sweeps eagerly (complementary, not overlapping);
`migrate`/`rebuild-catalogue`/`stale`/`serve` are maintenance and seams.

Porcelain owns sequencing knowledge so the human doesn't have to:
`ingest_sources.py --chunk` chains `rebuild-index` after `chunk --backfill` — a chunk pass
whose index is stale would silently miss new content in search, which invariant 3 forbids.
The primitives stay separate; the composition remembers the order.

## Conformance

The vocabularies live in code as single sources: `ask.GRAMMAR` (banner, usage errors,
`--help` epilog) and `jarvis.INTENTS` (NLU prompt, help reply). Drift gates in
`tests/test_ask_temporal.py` and `tests/test_reach.py` assert every table entry parses or
dispatches and appears in every rendering; `tests/test_gtd.py` pins the ambiguity rule;
`tests/test_ingest_sources.py` pins the porcelain sequencing. Removing redundancy is cheap;
keeping it removed is these tests.
