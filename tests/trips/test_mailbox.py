"""Mailbox ingest orchestration: select -> resolve forward -> extract higher-yield -> observe.
Hermetic: notmuch + extract are injected fakes; observe is the real write seam over the tmp
ledger, so idempotency and provenance are asserted against real projection state."""
from __future__ import annotations

import pytest

from life_agent.trips import commands, mailbox, store
from life_agent.trips import events as ev
from life_agent.trips import notmuch as nm


def _eml(message_id: str, subject: str = "Booking",
         date: str = "Mon, 12 Aug 2019 09:00:00 +0000", extra: str = "") -> bytes:
    head = f"Message-ID: <{message_id}>\r\nDate: {date}\r\nSubject: {subject}\r\n"
    return (head + extra + "\r\nbody\r\n").encode()


def _flight(fno: str) -> dict:
    return {"@type": "FlightReservation",
            "reservationFor": {"flightNumber": fno,
                "departureAirport": {"iataCode": "LIS"},
                "arrivalAirport": {"iataCode": "AMS"},
                "departureTime": "2019-08-12T09:30:00Z"}}


class FakeNm:
    """Stands in for the notmuch module: search() + show_raw(), plus the real error class."""
    NotmuchError = nm.NotmuchError

    def __init__(self, raws: dict[str, bytes], search_map: dict[str, list[str]]) -> None:
        self.raws = raws
        self.search_map = search_map

    def search(self, query: str) -> list[str]:
        return self.search_map.get(query, [])

    def show_raw(self, msgid: str) -> bytes:
        return self.raws[msgid]


def test_ingests_from_higher_yield_original() -> None:
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")
    orig = _eml("orig@x")
    fake = FakeNm(raws={"fwd@x": fwd, "orig@x": orig},
                  search_map={"q": ["fwd@x"], "id:orig@x": ["orig@x"]})
    extract_map = {fwd: [_flight("EX1")], orig: [_flight("EX1"), _flight("EX2")]}
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: extract_map[raw])
    assert stats.forwards_resolved == 1
    assert stats.reservations == 2            # from the original, the higher-yield candidate
    assert len(store.timeline()) == 2
    # provenance: source_id is the ORIGINAL's message id
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:orig@x"}


def test_tie_prefers_original() -> None:
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")
    orig = _eml("orig@x")
    fake = FakeNm(raws={"fwd@x": fwd, "orig@x": orig},
                  search_map={"q": ["fwd@x"], "id:orig@x": ["orig@x"]})
    extract_map = {fwd: [_flight("EX1")], orig: [_flight("EX1")]}   # equal yield
    mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: extract_map[raw])
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:orig@x"}            # tie -> original


def test_non_booking_yields_nothing() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [])
    assert stats.reservations == 0
    assert stats.messages_with_yield == 0
    assert len(store.timeline()) == 0


def test_bad_message_skipped_and_counted() -> None:
    good = _eml("good@x")
    fake = FakeNm(raws={"good@x": good, "bad@x": b"whatever"},
                  search_map={"q": ["bad@x", "good@x"]})

    def flaky(raw, ctx):
        if raw == b"whatever":
            raise ValueError("boom")
        return [_flight("EX1")]

    stats = mailbox.ingest_query("q", nm=fake, extract_fn=flaky)
    assert stats.errors == 1
    assert stats.reservations == 1            # the good one still ingested
    assert len(store.timeline()) == 1


def test_second_identical_run_is_a_noop() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})

    def extract_fn(raw: bytes, ctx: object) -> list[dict]:
        return [_flight("EX1")]

    mailbox.ingest_query("q", nm=fake, extract_fn=extract_fn)
    n_events = len(ev.load(commands.LEDGER_PATH))
    mailbox.ingest_query("q", nm=fake, extract_fn=extract_fn)  # again
    assert len(ev.load(commands.LEDGER_PATH)) == n_events      # idempotent, no new events
    assert len(store.timeline()) == 1


def test_dry_run_writes_nothing_but_counts() -> None:
    msg = _eml("m@x")
    fake = FakeNm(raws={"m@x": msg}, search_map={"q": ["m@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")],
                                 dry_run=True)
    assert stats.reservations == 1
    assert stats.messages_with_yield == 1
    assert len(store.timeline()) == 0         # nothing written
    assert len(ev.load(commands.LEDGER_PATH)) == 0


def test_limit_caps_selection() -> None:
    raws = {f"m{i}@x": _eml(f"m{i}@x") for i in range(5)}
    fake = FakeNm(raws=raws, search_map={"q": list(raws)})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")],
                                 limit=2)
    assert stats.selected == 2


def test_notmuch_error_from_search_propagates() -> None:
    class Boom:
        NotmuchError = nm.NotmuchError

        def search(self, query):
            raise nm.NotmuchError("bad index")

        def show_raw(self, msgid):  # pragma: no cover
            raise AssertionError("unreached")

    with pytest.raises(nm.NotmuchError):
        mailbox.ingest_query("q", nm=Boom(), extract_fn=lambda raw, ctx: [])


def test_per_message_resolution_error_degrades_to_forward() -> None:
    # A NotmuchError DURING per-message forward resolution must NOT abort the run and must NOT
    # skip the message — it degrades to extracting the forward itself. Only the top-level
    # selection search aborts (see the test above).
    fwd = _eml("fwd@x", subject="Fwd: Booking", extra="X-Forwarded-Message-Id: <orig@x>\r\n")

    class ResolveBoom(FakeNm):
        def search(self, query: str) -> list[str]:
            if query == "q":
                return ["fwd@x"]            # selection succeeds
            raise nm.NotmuchError("index blip during resolution")  # id:/subject: lookup fails

    fake = ResolveBoom(raws={"fwd@x": fwd}, search_map={})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")])
    assert stats.errors == 0                 # degraded, not an error
    assert stats.forwards_resolved == 0
    assert stats.reservations == 1           # the forward itself was still ingested
    assert len(store.timeline()) == 1
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:fwd@x"}


def test_message_without_date_is_skipped_and_counted() -> None:
    dateless = b"Message-ID: <nodate@x>\r\nSubject: Booking\r\n\r\nbody\r\n"
    fake = FakeNm(raws={"nodate@x": dateless}, search_map={"q": ["nodate@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")])
    assert stats.errors == 1
    assert stats.reservations == 0
    assert store.timeline() == []


def test_unparseable_date_is_skipped() -> None:
    garbled = b"Message-ID: <garbled@x>\r\nDate: not-a-date\r\nSubject: Booking\r\n\r\nbody\r\n"
    fake = FakeNm(raws={"garbled@x": garbled}, search_map={"q": ["garbled@x"]})
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: [_flight("EX1")])
    assert stats.errors == 1
    assert stats.reservations == 0
    assert store.timeline() == []


def test_dateless_forward_still_ingests_dated_original() -> None:
    fwd = (b"Message-ID: <fwd@x>\r\nSubject: Fwd: Booking\r\n"
           b"X-Forwarded-Message-Id: <orig@x>\r\n\r\nbody\r\n")
    orig = _eml("orig@x")
    fake = FakeNm(raws={"fwd@x": fwd, "orig@x": orig},
                  search_map={"q": ["fwd@x"], "id:orig@x": ["orig@x"]})
    extract_map = {fwd: [_flight("EX1")], orig: [_flight("EX1"), _flight("EX2")]}
    stats = mailbox.ingest_query("q", nm=fake, extract_fn=lambda raw, ctx: extract_map[raw])
    assert stats.errors == 0
    assert stats.reservations >= 1
    with store.get_db() as conn:
        srcs = {r["source_id"] for r in conn.execute("SELECT source_id FROM source")}
    assert srcs == {"mail:orig@x"}


def test_configured_query_raises_when_unset(tmp_path, monkeypatch) -> None:
    from life_agent.core import config
    monkeypatch.setattr(config, "DATA_SOURCES", tmp_path / "absent.yaml")
    with pytest.raises(mailbox.IngestConfigError):
        mailbox.configured_query()


def test_configured_query_reads_yaml(tmp_path, monkeypatch) -> None:
    from life_agent.core import config
    f = tmp_path / "data-sources.yaml"
    f.write_text("trips:\n  ingest:\n    query: 'folder:Trips'\n", encoding="utf-8")
    monkeypatch.setattr(config, "DATA_SOURCES", f)
    assert mailbox.configured_query() == "folder:Trips"
