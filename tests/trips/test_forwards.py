"""Pure forward->original resolution. The notmuch lookup is injected (a dict), so this is
socket-free. Precedence: X-Forwarded-Message-Id -> In-Reply-To -> last References -> subject."""
from __future__ import annotations

from collections.abc import Callable

from life_agent.trips import forwards


def _lookup(mapping: dict[str, list[str]]) -> Callable[[str], list[str]]:
    return lambda query: mapping.get(query, [])


def test_x_forwarded_message_id_wins() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<orig@x>",
               "In-Reply-To": "<other@x>"}
    got = forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]}))
    assert got == "orig@x"


def test_in_reply_to_when_no_xforwarded() -> None:
    headers = {"Message-ID": "<fwd@x>", "In-Reply-To": "<orig@x>"}
    assert forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]})) == "orig@x"


def test_references_uses_last_id() -> None:
    headers = {"Message-ID": "<fwd@x>", "References": "<a@x> <b@x> <orig@x>"}
    assert forwards.resolve_original(headers, _lookup({"id:orig@x": ["orig@x"]})) == "orig@x"


def test_subject_match_after_stripping_repeated_mixed_case_prefixes() -> None:
    headers = {"Message-ID": "<fwd@x>", "Subject": "Fwd: RE: Fw: Your booking ABC"}
    lookup = _lookup({'subject:"Your booking ABC"': ["orig@x"]})
    assert forwards.resolve_original(headers, lookup) == "orig@x"


def test_returns_none_when_nothing_resolves() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<gone@x>"}
    assert forwards.resolve_original(headers, _lookup({})) is None


def test_never_returns_the_forward_itself() -> None:
    # A subject search that only finds the forward itself must not resolve to it.
    headers = {"Message-ID": "<fwd@x>", "Subject": "Fwd: Booking"}
    assert forwards.resolve_original(headers, _lookup({'subject:"Booking"': ["fwd@x"]})) is None


def test_plain_subject_without_prefix_is_not_searched() -> None:
    # No forwarding prefix -> no broad subject lookup (would match unrelated mail).
    called: list[str] = []

    def lookup(q: str) -> list[str]:
        called.append(q)
        return ["someone@x"]

    headers = {"Message-ID": "<msg@x>", "Subject": "Booking confirmation"}
    assert forwards.resolve_original(headers, lookup) is None
    assert called == []  # nothing was looked up


def test_precedence_xforwarded_over_references() -> None:
    headers = {"Message-ID": "<fwd@x>", "X-Forwarded-Message-Id": "<a@x>",
               "References": "<b@x>"}
    lookup = _lookup({"id:a@x": ["a@x"], "id:b@x": ["b@x"]})
    assert forwards.resolve_original(headers, lookup) == "a@x"
