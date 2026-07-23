"""Supersession is the highest-risk logic — tested first, per the design's testing section."""
from __future__ import annotations

from life_agent.trips import events as ev
from life_agent.trips.fold import fold


def _flight(fno: str) -> dict:
    return {"@type": "FlightReservation", "reservationFor": {"flightNumber": fno}}


def test_same_identity_two_sources_email_wins_over_kayak() -> None:
    """Kayak (tier 3) and the flight's own email (tier 2) observe ONE identity -> email wins."""
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                    source_id="kayak", received_at="2019-08-01T00:00:00"),
        ev.observed("id1", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="mail", received_at="2019-08-02T00:00:00"),
    ]
    result = fold(events)
    assert set(result) == {"id1"}
    assert result["id1"].fidelity == "email-kitinerary"
    assert result["id1"].source_id == "mail"
    assert result["id1"].superseded_by is None and not result["id1"].cancelled


def test_lower_fidelity_arriving_later_does_not_win() -> None:
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="mail", received_at="2019-08-01T00:00:00"),
        ev.observed("id1", _flight("EX1"), fidelity="kayak-ics",
                    source_id="ics", received_at="2020-01-01T00:00:00"),
    ]
    assert fold(events)["id1"].fidelity == "email-kitinerary"


def test_reschedule_reissue_cancel_folds_to_one_current_cancelled() -> None:
    """confirmation -> schedule change -> re-issue -> cancellation against one PNR must fold
    to exactly ONE current reservation, cancelled, with superseded ancestors retained."""
    events = [
        ev.observed("conf", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="m1", received_at="2019-08-01T00:00:00"),
        ev.observed("sched", _flight("EX1b"), fidelity="email-kitinerary",
                    source_id="m2", received_at="2019-08-02T00:00:00"),
        ev.superseded("conf", "sched"),
        ev.observed("reissue", _flight("EX9"), fidelity="email-kitinerary",
                    source_id="m3", received_at="2019-08-03T00:00:00"),
        ev.superseded("sched", "reissue"),
        ev.cancelled("reissue", reason="cancelled by airline", source_id="m4"),
    ]
    result = fold(events)
    current = [r for r in result.values() if r.superseded_by is None]
    assert len(current) == 1
    assert current[0].identity == "reissue"
    assert current[0].cancelled is True
    superseded = [r for r in result.values() if r.superseded_by is not None]
    assert len(superseded) == 2  # conf, sched retained


def test_amendment_deep_merges_without_clobbering_siblings() -> None:
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                    source_id="k", received_at="2019-08-01T00:00:00"),
        ev.amended("id1", {"reservationFor": {"seat": "12A"}}),
    ]
    merged = fold(events)["id1"].jsonld
    assert merged["reservationFor"]["flightNumber"] == "EX1"  # sibling preserved (deep-merge)
    assert merged["reservationFor"]["seat"] == "12A"          # new key merged in


def test_kayak_import_never_infers_cancellation_from_absence() -> None:
    """A record present once and simply not re-observed stays booked (Kayak drops
    cancellations; absence is never cancellation)."""
    events = [ev.observed("id1", _flight("EX1"), fidelity="kayak-api",
                          source_id="k", received_at="2019-08-01T00:00:00")]
    assert fold(events)["id1"].cancelled is False


def test_unknown_fidelity_degrades_and_never_crashes() -> None:
    events = [
        ev.observed("id1", _flight("EX1"), fidelity="mystery-source",
                    source_id="x", received_at="2019-08-01T00:00:00"),
        ev.observed("id1", _flight("EX1"), fidelity="email-kitinerary",
                    source_id="mail", received_at="2019-08-02T00:00:00"),
    ]
    # A ranked fidelity beats an unranked one (which degrades to worst rank), no KeyError.
    assert fold(events)["id1"].fidelity == "email-kitinerary"
    # And a lone unranked observation is still retained, not dropped.
    solo = fold([ev.observed("id2", _flight("EX2"), fidelity="mystery",
                             source_id="y", received_at="2019-08-01T00:00:00")])
    assert solo["id2"].fidelity == "mystery"


def test_orphan_events_without_observation_are_ignored() -> None:
    events = [
        ev.superseded("ghost-old", "ghost-new"),
        ev.cancelled("ghost", reason="stray"),
        ev.amended("ghost", {"seat": "1A"}),
    ]
    assert fold(events) == {}  # nothing observed -> empty projection, no KeyError
