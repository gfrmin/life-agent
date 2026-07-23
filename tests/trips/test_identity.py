"""Content-keyed identity: same booked thing -> same id, regardless of provenance."""
from __future__ import annotations

from life_agent.trips.identity import content_key, res_type, reservation_identity

_FLIGHT = {
    "@type": "FlightReservation",
    "reservationFor": {
        "@type": "Flight",
        "flightNumber": "TP123",
        "departureAirport": {"@type": "Airport", "iataCode": "LIS"},
        "arrivalAirport": {"@type": "Airport", "iataCode": "AMS"},
        "departureTime": "2019-08-12T09:30:00+01:00",
    },
}

_LODGING = {
    "@type": "LodgingReservation",
    "reservationFor": {"@type": "LodgingBusiness", "name": "Hotel Example"},
    "checkinTime": "2019-08-12",
    "checkoutTime": "2019-08-15",
}


def test_flight_identity_is_stable_and_type_aware() -> None:
    assert res_type(_FLIGHT) == "FlightReservation"
    a = reservation_identity(_FLIGHT)
    assert a == reservation_identity(dict(_FLIGHT))  # same content -> same id
    assert len(a) == 64  # sha256 hex


def test_provenance_does_not_change_identity() -> None:
    """The same flight carrying a different confirmation number is ONE identity."""
    with_conf = {**_FLIGHT, "reservationNumber": "ABC123"}
    without = {**_FLIGHT}
    assert reservation_identity(with_conf) == reservation_identity(without)


def test_lodging_falls_back_to_name_when_no_property_id() -> None:
    assert content_key(_LODGING) == ("Hotel Example", "2019-08-12", "2019-08-15")


def test_segment_with_no_flight_number_still_keys() -> None:
    """Degenerate case fixtures must cover: a segment lacking flightNumber/airline code."""
    bare = {
        "@type": "FlightReservation",
        "reservationFor": {
            "@type": "Flight",
            "departureAirport": {"iataCode": "LHR"},
            "arrivalAirport": {"iataCode": "JFK"},
            "departureTime": "2015-03-01T10:00:00Z",
        },
    }
    # Must not raise and must produce a stable id (flight_number slot empty, others present).
    assert content_key(bare)[0][0] == ("LHR", "JFK", "2015-03-01T10:00:00+00:00", "")


def test_multisegment_flight_orders_segments() -> None:
    two = {
        "@type": "FlightReservation",
        "reservationFor": [
            {"flightNumber": "TP1", "departureAirport": {"iataCode": "LIS"},
             "arrivalAirport": {"iataCode": "OPO"}, "departureTime": "2019-08-12T09:00:00Z"},
            {"flightNumber": "TP2", "departureAirport": {"iataCode": "OPO"},
             "arrivalAirport": {"iataCode": "AMS"}, "departureTime": "2019-08-12T12:00:00Z"},
        ],
    }
    key = content_key(two)
    assert key[0][0][0] == "LIS" and key[0][-1][1] == "AMS"


def test_train_keys_on_stations_and_number() -> None:
    train = {
        "@type": "TrainReservation",
        "reservationFor": {
            "@type": "TrainTrip",
            "trainNumber": "IC-100",
            "departureStation": {"@type": "TrainStation", "name": "Lisboa Oriente"},
            "arrivalStation": {"@type": "TrainStation", "name": "Porto Campanha"},
            "departureTime": "2019-08-12T09:00:00Z",
        },
    }
    key = content_key(train)
    assert key[0][0] == ("Lisboa Oriente", "Porto Campanha", "2019-08-12T09:00:00+00:00", "IC-100")


def test_other_reservation_keys_on_title_start_end() -> None:
    dinner = {
        "@type": "FoodEstablishmentReservation",
        "reservationFor": {"@type": "FoodEstablishment", "name": "Cafe Example"},
        "startTime": "2019-08-13T20:00:00Z",
        "endTime": "2019-08-13T22:00:00Z",
    }
    assert content_key(dinner) == (
        "Cafe Example", "2019-08-13T20:00:00+00:00", "2019-08-13T22:00:00+00:00")
