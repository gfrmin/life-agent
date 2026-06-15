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
| `/derive` | materialise the projections (doc_date, doc_subject) the last answer named as underived, then re-ask |
| `/react ID g\|b` | verdict a past answer by its `decision_id` — a **deferred** dogfood verdict, one bit, corpus-free |
| `/q` (or `/quit`, `/exit`, EOF) | quit |

One-shot is the same grammar: `bin/ask-live "/since 2026-01-01 what invoices arrived?"`.

**Deferred verdicts.** The inline `g`/`b` key grades the answer you just saw; `/react`
grades one you saw *earlier*, addressed by its content-addressed `decision_id` (or a unique
prefix of it, resolved git-style — zero or several is a loud error, never a silent pick).
This decouples asking from judging: a batch of questions can be answered now and verdicted
whenever, the verdict still binding to the answer **as it stood at decision time** (the
`decision_id` is the answer's cache key, so it cannot drift). The verdict is recorded
regardless; whether it *moves* the utility posterior is the fold's call, not the command's
(`reactions.load_reactions` folds only clean abstain-verdicts — `/react` names that fate in
its reply rather than implying every verdict counts).

**The verdict is one bit.** Good or bad — nothing more is elicited from the owner. The loop
treats the owner's free text as its only expensive resource, so it never asks for a note: any
richer signal must be measured cheaply (auto-derived, or a bit per claim), never typed. Cheap
auto-measurement (the decision, its held-back candidates, the posterior) is unconstrained and
already logged; only the elicitation is rationed.

**Temporal composition.** `/since` and `/until` are bounds: together they form a range, each
may appear at most once. `/recent` is a ranking directive and stands alone — applying any
bound already ranks admitted sources newest-first (`life_agent.core.temporal.apply_temporal`
sorts whenever a predicate is present and excludes nothing absent bounds), so `/recent`
combined with a bound is pure redundancy and is rejected with the rule spelled out. Likewise
rejected, never guessed at: a duplicated prefix, `/since` later than `/until` (an empty
range is almost certainly a typo), an unparseable date, an unknown slash-command.

**Flags** (run-config only): `--k N` retrieval width, `--no-expand` raw-question BM25
baseline, `--no-cache` recompute every stage.

**Act-layer state.** A plain `QUESTION` covers the GTD — no special grammar. The task
ledger's knowledge projection (`life_agent.tasks.knowledge` →
`$LIFE_AGENT_KB/tasks/state.md`) is re-projected and re-ingested **on demand**, before a
question is answered, whenever the ledger has moved past it; retrieval then finds current
task state like any source (pkm SPEC §15.4 keeps only the newest version of an evolving
document retrievable). The refresh is announced, never silent: `gtd state refreshed @
event N` on success, or the named fail-open degradation `gtd state refresh failed (…) —
answering over the corpus as-is` (same contract as `/derive`). A failed refresh leaves the
state stale: the next question retries and the failure is re-named each time — degraded,
never silent. When fresh: nothing printed, nothing written. The strings are one table
(`ask.REFRESH_NOTES`), drift-gated.

**The owner filter (subject mode).** A plain `QUESTION` with an *unchained* first-person
possessive — "what is **my** Israeli ID?", "the **owner's** mortgage" — filters hits by
each document's projected subject (pkm SPEC §18.13 `doc_subject`) matched against the
owner profile. The match is consumer-side (the profile never enters pkm): a cached local-
model verdict per distinct subject string, so the per-question filter is deterministic. A
*relational* possessive — "my **partner's** ID" — does NOT trigger it (filtering for the
owner there would exclude exactly the right answer). Only documents *determinately* about
someone else, or determinately about nobody (`generic`: templates, blank forms), are
excluded — each named in the footer; an absent or unclear classification is indeterminate:
**kept** in the evidence and named, never silently excluded. No pkm root, no profile, or a
failed verdict degrades fail-open with a printed notice. Underived subjects carry `pkm
derive` remedies; `/derive` materialises them alongside doc_dates.

**After each answer:** sources are listed with scores; a temporal answer carries the
nothing-vanishes footer (admitted / excluded-by-date / undated / not-yet-derived, each set
named with its remedy); an owner-filtered answer carries the same contract's subject footer
(admitted / someone-else's / generic-template / unclear-kept / underived-kept); the two
compose — both footers print when both modes ran; unverified citations are flagged by the
citation guard; then one verdict key — `g`ood / `b`ad / `n`ote / Enter to skip — logs to
the dogfood journal that feeds `FAILURES.md`.

## Credence rendering — one grammar for uncertainty

Binding from Ask v0 slice 2 ([`bayesian-foundations.md`](./bayesian-foundations.md) §3,
adopted 2026-06-12): every *know* answer is a claim set with posteriors, and its
rendering obeys one grammar — uncertainty named, never mumbled (invariant 3 extended to
credence):

| element | form |
|---------|------|
| claim credence | every rendered claim carries its credence in one vocabulary across surfaces — never per-surface prose inventions |
| hedge | when no value dominates, the mixture is reported as alternatives with credences — never a silent pick of the leader |
| abstention | a named reason from a closed set (dispersed posterior · no admitted evidence · below the relevance floor) — never an empty or evasive reply; and when the posterior held candidates below the assert threshold, it names them with credences (`Held back: …`) — the withheld "thinking" the owner verdicts the abstain *decision* against, never a blind "should you have answered?" |
| clarifying ask | asked only when `voi` prices it above the interruption belief×cost; the question names what it would resolve |
| withheld claims | inclusion is a decision (foundations §3): withheld claims are counted with their EU reason — `n claims withheld: low relevance` |
| indeterminates | carried and named, as in the temporal/subject footers — the §18.12/§18.13 contract generalised |

Rendering order is posterior order, not rhetorical order; LLM paraphrase stays within
claim boundaries; the conformance audit (the citation guard extended to claim coverage)
runs per render, never cached. The strings live in per-family tables
(`lookup.GRAMMAR`, `narrative.GRAMMAR` — landed with slices 2b/3), drift-gated like
`GRAMMAR` and `REFRESH_NOTES`. The narrative family adds two contract points (§7):
withheld claims are *counted* with the inclusion reason, and the proposal-coverage
posterior is named in every footer — "this may be incomplete" is a number, not a vibe.

## act — Jarvis

Free-text Telegram messages, parsed by a local model into one of these intents
(`jarvis.INTENTS`, the single source for the NLU prompt and the help reply):

| intent | canonical phrasing | reply shape |
|--------|--------------------|-------------|
| `add` | "buy milk", "call dentist @health", "schedule X for next tuesday" | `Added [id] TEXT to #list (due D)` |
| `complete` | "done 3", "done buy milk" | `Completed: TEXT` |
| `delete` | "delete 5" | `Deleted: TEXT` |
| `move` | "move 5 to next" | `Moved [5] TEXT to #next` |
| `mark_today` | "today 3", "focus on 3"; "untoday 3" unmarks | `Marked for today: [3] TEXT` |
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
`--help` epilog), `ask.REFRESH_NOTES` (the GTD refresh announcements), and
`jarvis.INTENTS` (NLU prompt, help reply). Drift gates in `tests/test_ask_temporal.py`,
`tests/test_ask_gtd_refresh.py`, and `tests/test_reach.py` assert every table entry
parses, dispatches, or renders and appears in every rendering; `tests/test_gtd.py` pins the ambiguity rule;
`tests/test_ingest_sources.py` pins the porcelain sequencing; `tests/test_ask_subject.py`
pins the owner-filter trigger (possessive vs relational), the subject footer's totality,
and the temporal+subject report composition; `tests/test_ask_react.py` pins the deferred
verdict (prefix resolution, the recorded `ReactionEvent`, and the report-vs-abstain fate it
names). Removing redundancy is cheap; keeping it removed is these tests.
