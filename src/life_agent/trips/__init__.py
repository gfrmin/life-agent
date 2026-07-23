"""life_agent.trips — the itinerary faculty: bookings -> a queryable, timezone-correct timeline.

Event-sourced, mirroring life_agent.tasks: an append-only JSONL ledger (events.py) is the
truth, a rebuildable SQLite table (store.py) is the read projection, and truth = fold(events)
(fold.py). Reservation identity (identity.py) is content-keyed and excludes provenance, so the
same booking seen via the Kayak export and via its own confirmation email dedupes to one row.
The single impure edge is extract.py, a subprocess wrapper over kitinerary-extractor.
"""
