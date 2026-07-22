# Trips — itinerary faculty

*Design doc. Status: proposed. Replaces a third-party dependency (Kayak Trips) with a
self-hosted faculty, per PRINCIPLES §5 (faculties over language-neutral seams) and §7
(ledger-as-truth).*

## Why

Kayak Trips is the last piece of the owner's life-management stack that is neither
self-hosted nor exportable. It holds ~15 years of travel history behind an account that
offers no data export. The goal is to replace it: own the data, own the itinerary view,
and make travel a queryable part of the life corpus rather than a silo.

The scope is "80% of Kayak Trips": bookings collected from email into a trustworthy
chronological itinerary, readable on a phone while travelling. Explicitly *not* a booking
engine, price tracker, or trip-planning tool.

## The kernel insight

[KItinerary](https://invent.kde.org/pim/kitinerary) already solves the hard part.
`/usr/lib/kf6/kitinerary-extractor` is installed with the full capability set: 349
extractors, PDF (poppler), HTML (libxml2), barcode decoding (ZXing), iCal, and phone-number
parsing. It turns a booking email into schema.org JSON-LD.

Critically for this repo, **it is deterministic**. `action_items` uses a local model with
grounded quotes and needs the citation guard because a model can drift. kitinerary is a
parser: same bytes in, same JSON-LD out, with barcode verification underneath. It is the
most citable transform in the system — every field traces to a byte range in an email the
owner can point at. It satisfies the no-hallucination promise structurally.

It is also **enriching**, which removes work we would otherwise hand-write. Given a minimal
`FlightReservation` carrying only IATA codes, it returns airport geo-coordinates, country
codes, and IANA timezones resolved from its built-in airport database:

```
departureTime.timezone -> Europe/Lisbon
arrivalAirport.geo     -> {52.31, 4.76}
```

Timezone-correct rendering — where most itinerary tools are bad — therefore comes free.

## Verified findings

Everything below was checked against the real system, not assumed.

| Finding | Status |
|---|---|
| `kitinerary-extractor` parses email → enriched JSON-LD | **Verified** (`test.eml` → full `FlightReservation` with tz + geo) |
| It accepts **raw JSON-LD as input** and enriches it | **Verified** — no email wrapper needed |
| It returns `[]` for the Kayak ICS, whole file *and* single event | **Verified** — Kayak VEVENTs are unstructured prose |
| kitinerary ships **no** Kayak extractor | **Verified** — 464 files under `src/lib/scripts`, zero matches |
| Kayak private Trips API exists | **Verified** — routes 401 authenticated vs 404 bogus |
| The API requires an `X-CSRF` header | **Verified** — otherwise `INVALID_FORM_TOKEN`; token is absent from cookies, localStorage, sessionStorage and meta tags, so it must be lifted from the page's own requests |
| A full export succeeds and reaches back to 2010 | **Verified** — 115 trips, 260 events, unbroken year histogram 2010→2026 |
| Event taxonomy maps onto schema.org | **Verified** — 160 flight, 90 hotel, 8 train, 1 restaurant, 1 custom |
| `confirmationNumber` is too sparse to key identity | **Verified** — 151/260 present, and only 147 distinct where present |
| Kayak records no cancellations | **Verified** — 260/260 `isBooked`, 0 `isCancelled` |
| Kayak ICS feed has no date-range parameter | **Verified negative** — only a per-trip `calendarFeed` route |
| Kayak offers no self-service data export | **Verified negative** — its privacy-management page offers deletion only |
| No prior-art Kayak Trips exporter on GitHub | **Verified negative** — all hits scrape flight *search* |
| Owner's ICS export holds only ~2 years of trips | **Verified** — 79 VEVENTs, 12 trip containers |
| A single archive folder holds >690k messages | **Verified** — full-Maildir scanning is not viable |

The last row justifies the ingest design; the ICS rows justify the seeder design.

## Ingest — the `Trips` folder

The owner files booking confirmations into a `Trips` folder in their mail account. mbsync
(`Patterns *`, `Create Both`) syncs it to `<maildir>/Trips` with no config change. Ingest
reads that folder; the concrete path is declared in the `data-sources.yaml` registry under
`$LIFE_AGENT_KB`, never here.

This is deliberate over the alternatives:

- **Not** a full-Maildir scan — the owner's archive exceeds 690k messages on a slow mount,
  overwhelmingly airline marketing rather than bookings.
- **Not** a forwarding address — needs SMTP infrastructure and a second mail path.
- **Not** an auto-detect + review queue — a queue that must be worked is a queue that rots.

Filing an email is one gesture, works from a phone mid-trip, and the folder doubles as the
permanent record of what fed the system. Backfill is the same mechanism: drag old
confirmations in and re-run. Ingest is idempotent by `Message-ID` + SHA256, so re-running
costs nothing.

Two supplementary paths, both landing in the same place: **file upload** (for PDFs and
`.pkpass` files that never arrive as mail) and a **CLI** (`trips ingest <path>`).

## Constraint: personal data is never part of the code

Not "scrubbed before commit" — *never present*. Scrubbing is a process that fails silently
the one time it is skipped; absence is structural. Concretely:

- **No personal constant, ever.** Maildir roots, the data root, folder names, account
  identifiers and calendar-feed URLs are **configuration**, read from the `data-sources.yaml`
  registry under `$LIFE_AGENT_KB`. Code contains the *key*, never the value. A path literal
  in a module is a bug, not a cleanup task.
- **Fixtures are synthetic by construction**, not anonymised captures. A scrubbed real
  confirmation still carries a real PNR, route and traveller name if the scrub misses a
  field; a hand-built fixture cannot. Same reasoning as the checksum-invalid IDs the guard
  already relies on.
- **Extracted content stays in the ledger**, which lives under the personal data root and is
  never a repo artifact. Nothing in the pipeline writes reservation content into the tree.
- **Docs use placeholders** — `<maildir>/Trips`, `!<tripId>` — with concrete values only in
  private config.

`.githooks/pii_check.py` is the backstop, not the mechanism. It caught one line of this
document during review; the design intent is that it should have nothing to catch.

## Data model

Ledger-as-truth, mirroring `life_agent.tasks`. Stdlib `sqlite3`, `truth = fold(events)`.

### Tables

1. **`source`** — one row per ingested artifact: `message_id`, `path`, `sha256`,
   `received_at`, `fidelity`, `kind`. The provenance anchor every reservation cites.
2. **`reservation_event`** — the append-only ledger. Event types mirror `tasks/events.py`:
   `observed` · `superseded` · `cancelled` · `amended`. Corrections are compensating
   entries; nothing is erased.
3. **`trip`** — an optional name and date range. A label, nothing depends on it.

`reservation` is a **projection** folded from the ledger, not a base table: raw JSON-LD
stored verbatim, plus extracted columns for querying (type, start/end + IANA timezone,
confirmation number, provider, lat/lon, cancelled, `superseded_by`, nullable `trip_id`).
`store.rebuild(conn, events)` regenerates it, exactly as `tasks` does.

Storing JSON-LD **verbatim** is load-bearing. kitinerary's schema.org model is richer and
more volatile than anything we would design; re-deriving the projection is a cheap rebuild
rather than a lossy migration. It is also what makes Phase 2 cheap.

### Reservation identity

Mirroring `assertion_identity()` — keyed on **content, deliberately excluding provenance**.

An earlier draft of this document keyed identity on
`(res_type, confirmation_number, leg_key)`. **Measurement killed that.** In a 260-event
export, `confirmationNumber` was present on only 151 events (58%) — 113/160 flights,
37/90 hotels, 1/8 trains. Falling back to `bookingDetail.bookingReferenceNumber` lifts
coverage to 191/260 (73%), still far from total. Worse, `(res_type, confirmation_number)`
was not even unique where present: 151 references collapsed to 147 distinct pairs, because
one booking reference legitimately covers several reservations (an outbound and a return,
two rooms, two travelers). A confirmation number is neither necessary nor sufficient.

So identity is derived **entirely from the booked thing itself**:

```
reservation_identity(res_type, content_key)

  flight, train  ->  ordered tuple over segments of
                     (departure_iata, arrival_iata, departure_datetime, flight_number)
  lodging        ->  (property_id or property_name, check_in, check_out)
  other          ->  (title, start, end)
```

Confirmation number becomes an ordinary **attribute** — displayed, searchable, and useful
for matching a record against an email, but never load-bearing for identity.

Measured against the same export, this yields **259 distinct identities from 260 events**.
The single collision is two flight events in one trip sharing a confirmation number and an
identical segment list with different vendor `eventId`s — a true duplicate, which this
scheme is *supposed* to collapse. Zero false merges; the degenerate cases are empty too
(0 flights/trains with no segments, 0 lodging rows with neither id nor name).

Vendor `eventId` is unique across the export (260/260) and would make an easy key — which
is exactly why it is not used. It is provenance. Keying on it would make the same booking
seen via Kayak and later via its own confirmation email resolve to two identities instead
of dedup'ing into one, which is the whole point of the exercise.

### Fidelity tiers and supersession

The hard problem is real-world churn: airlines send a confirmation, a schedule change, a
re-issue, then maybe a cancellation, all against one PNR. Naive ingest yields four
overlapping flights. Compounding it, Kayak's own data contains errors — one observed train event in the owner's
export renders a 30-minute domestic commute as an 18-hour trip arriving the next day, in
the timezone of a different continent.

So records are ranked by **(fidelity, then `received_at`)**, highest wins:

| Tier | Source | Rationale |
|---|---|---|
| 1 | `manual` | An explicit human correction always wins |
| 2 | `email-kitinerary` | Structured, deterministic, barcode-verified |
| 3 | `kayak-api` | Kayak's trip JSON — structured, second-hand, but richer than expected |
| 4 | `kayak-ics` | Text-scraped calendar stub; known to contain errors |

Tier 3 earns its rank. The API returns per-segment IATA codes *and* coordinates, IANA
timezones on both ends (223/260 events), operating-carrier distinct from marketing
carrier (47 segments), seat numbers (33), and for lodging the address, phone, coordinates
and star rating. Several enrichments the extraction seam was expected to recover from
kitinerary's airport database arrive already populated. It stays below `email-kitinerary`
because it is still a vendor's reinterpretation of an email we may later hold directly —
but it is a far better floor than the ICS.

When a higher-ranked record arrives for an existing identity, the older row is marked
`superseded_by` and retained. Cancellations mark the chain cancelled rather than deleting.

One caveat the export makes concrete: **all 260 events came back `isBooked`, with zero
`isCancelled`.** Kayak appears to drop cancellations rather than tombstone them. So the
ledger's `cancelled` transition has no Kayak source at all — it can only ever arrive from a
filed email or a manual correction. A Kayak re-import must therefore never be treated as
authoritative about *absence*: a reservation missing from a later export means nothing, and
must not be inferred as a cancellation.

This yields the desired property: **the ICS gives 12 populated trips on day one, and each
one silently upgrades** as real confirmation emails are filed into `Trips`. A full history
immediately, improving over time, with no need to gather every email up front.

## Extraction seam

One pure function, the only thing that touches the binary:

```python
extract(payload: bytes, context_date: datetime) -> list[dict]   # JSON-LD
```

It shells out to `kitinerary-extractor -o JsonLd --context-date <iso>`, following the
`pkm/producers/tesseract.py` precedent — an external system binary wrapped as a producer,
exactly as pandoc, tesseract and Ollama already are. No new Python dependency.

`context_date` is **not optional**. kitinerary needs it to resolve partial dates ("12 Aug")
to a real year; passing it wrong is the single most common source of garbage output. It
comes from the email's `Date:` header.

Because the function takes bytes and not a path, every ingest path — Maildir, upload, CLI,
seeder — is the same code.

### The seeder trick

kitinerary cannot read the Kayak ICS, but it *does* accept raw JSON-LD. So the seeder
hand-writes only **recognition** — regex `SUMMARY`/`DESCRIPTION` into minimal schema.org
JSON-LD — and feeds that back through `extract()` for **enrichment**. The airport/timezone
database does the hard part, and ICS-derived records emerge in the identical shape as
email-derived ones. One schema, one downstream path; tiers differ by provenance only.

Two ICS quirks the recogniser must handle:

- **Hotels are split in two.** `Check in to…` and `Check out from…` are separate VEVENTs
  whose UIDs share a booking id and differ only by an index prefix (`0-<id>`, `1-<id>`).
  Re-pair them by that suffix into one `LodgingReservation`, or the timeline shows twice
  as many hotel events as there were stays.
- **Trip grouping is free.** Every event embeds `kayak.com/trips/!<tripId>`, and the
  all-day container event's UID prefix matches it, carrying the trip's name and dates.

## Non-goals

**No automatic trip grouping, and no clustering heuristic.** Interrogating the actual uses:
"what's next?" is a *time window*; "when was I in Lisbon?" is *search*; only "show me the
London trip" wants a group, and that is a named date range. Clustering heuristics are
exactly the systems that split a layover into two trips or silently merge two others.
`trip` is therefore a nullable label — populated free from Kayak where it exists, editable
by hand, null otherwise with nothing breaking. This deletes a table and a subsystem.

Also out of scope: booking, price tracking, recommendations, multi-user sharing.

## Surfaces

### Web

Mirrors `life_agent/reach/web/` exactly: stdlib `http.server`, a `dispatch(user_id, method,
path, body)` function separate from the handler (testable without a socket), and a single
self-contained `index.html` with inline CSS custom properties and vanilla `fetch`. No
framework, no build step, no npm — consistent with this repo's standing choices (stdlib
`urllib` for embeddings; Tesseract as a "~1-file clone of the pandoc producer, no new dep").
It reuses GTD's CSS variables so both surfaces read as one system.

The view is a single reverse-chronological timeline with search and "now / next" pinned at
the top, grouped by day, rendered in **each event's local time** — which is what a traveller
wants and what the kitinerary enrichment makes possible.

### Calendar feed

The app publishes an ICS feed the owner's phone subscribes to. This solves offline access
almost for free: the itinerary lands in the native calendar app and works on a plane, with
no PWA, service worker, or offline cache to build. kitinerary already emits iCal
(`-o iCal`). Given the server is reachable only over Tailscale, this matters — a phone in
airplane mode cannot reach the origin at all.

## Phases

Each is usable alone, per the roadmap's convention.

**Phase 0 — Extract the Kayak history.** *Urgent and independent; the only irreplaceable
piece.* ~15 years of trips exist solely inside an account with no export, one deletion away
from gone. Script at `kayak-trips-export.js` (reviewed: same-origin GETs only, no
third-party calls, no exfiltration, 250ms pacing). Run diagnostic first (`DEEP = false`) to
confirm `type=owned` returns pre-2024 trips, then `DEEP = true`.

`allParsedEmails` is the prize: Kayak retains the **source confirmation emails** it parsed.
If those return real message content, they are original airline/hotel confirmations from
2010 onward, feedable straight into `extract()` — landing in **tier 2**, not tier 4, and
recovering high-fidelity data for trips whose emails are long gone from the mailbox.

Caveat: undocumented internal API, and Kayak's ToS prohibits automated access. It is the
owner's own data from their own session; if 429s appear, raise `DELAY_MS` rather than push.

**Phase 1 — `life_agent.trips`.** The ledger (`events`/`commands`/`store`/`project`/`read`,
mirroring `tasks/`), the `extract()` wrapper, the ICS seeder, Maildir ingest, the web
surface, the calendar feed. At the end of this phase Kayak is redundant.

**Phase 2 — `ask-live` integration.** Reservations become cited pkm artifacts, so *"when did
I fly to Lisbon?"* answers with citations through the guard. Cheap because Phase 1 stores
JSON-LD verbatim and the Maildir is already a registered pkm source — this is a transform
over artifacts pkm already holds, not a new ingestion path.

**Phase 3 — Alerts via `life_agent.reach`.** Flight status and departure reminders,
delivered alongside the GTD digest. Needs an external flight-data provider behind a
pluggable interface; deferred deliberately because it is the only part requiring a paid
third party.

## Testing

Following the repo's gates (mypy, ruff, pytest):

- **Extraction is deterministic**, so it is golden-file testable: a corpus of fixture
  emails → expected JSON-LD. No mocking a model, no flakiness.
- **Supersession is the highest-risk logic** and gets tested first: confirmation → schedule
  change → re-issue → cancellation against one PNR must fold to exactly one current
  reservation, cancelled, with three superseded ancestors.
- **Cross-tier upgrade**: an ICS stub and its later email must resolve to one identity, with
  the email winning.
- **Idempotency**: ingesting the same message twice is a no-op.
- **`dispatch()` is tested without a socket**, as in `reach/web`.

Fixtures must be synthetic or scrubbed — real confirmations carry PNRs and personal data,
and this repo is public.

## Data locations

Code is public; personal data never enters the repo. Concrete paths live in the operator's
private config, following the `data-sources.yaml` convention.

- **Ledger + cached artifacts**: under a personal data root that is already inside the
  operator's borg backup set. No new backup configuration is required.
- **Backup caveat**: that backup script deliberately excludes another service's *live*
  database directory, because hot DB files are unsafe to copy. The same applies here —
  exclude the live SQLite file, and write a periodic `sqlite3 .backup` into a `backups/`
  subdirectory that the existing backup then picks up for free.

## Open questions

1. **Does `type=owned` actually return 2010-era trips?** The ownership-vs-recency reading is
   inferred from the frontend bundle's enum, not observed. Phase 0's diagnostic run settles
   it. If it does not, per-trip `calendarFeed` over discovered trip IDs is the fallback.
2. **Does `allParsedEmails` return raw RFC822, or Kayak's post-parse structure?** Determines
   whether the historical corpus lands in tier 2 or tier 3. Unknown until an authenticated
   run.
3. **Which flight-status provider** for Phase 3. Deferred; unblocks nothing earlier.
