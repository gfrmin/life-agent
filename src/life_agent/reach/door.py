"""The door — a second place the morning digest is handed to. A mirror: outbound only.

The door is a Matrix server the owner reads on his phone. A keeper there shows him what
agents hand in; nobody else speaks to him in that room. This module hands the digest to
the keeper as one item a day, in the room the keeper made for this account, as data (an
event of type ``ITEM_EVENT``), never as a chat message. Telegram stays the authority for
the digest until the list itself moves to the door.

Configured entirely by the deploying box, like the other reach channels; nothing about
any particular door is baked in here:

- ``DOOR_URL``      the server's base URL as this box reaches it
- ``DOOR_SERVER``   the server's name, the part after the colon in an account's id
- ``DOOR_ACCOUNT``  this agent's account there (the keeper knows it by this name)
- ``DOOR_KEEPER``   the keeper's account (default ``keeper``)
- the password      ``DOOR_PASSWORD`` in the env or the keyring; ``DOOR_SECRET`` names
                    another key when a box holds more than one door password

With ``DOOR_URL`` unset the mirror does nothing at all. It never raises into its caller:
a door that is down must not cost the owner his morning message. "Handed to the door" is
not "shown": the keeper reads an item strictly and may refuse one, and says so in the
room it was handed in.
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from life_agent.core import secret

ITEM_EVENT = "in.gfrm.door.item"
API = "/_matrix/client/v3"  # PII-OK — a URL path on the server, not a file path
# The keeper's limits for an item's text (its contract): characters, and bytes.
TEXT_CHARS, TEXT_BYTES = 16000, 32000
_TIMEOUT_S = 20
# One device, whatever happens to a run: a sign-in under a device's name takes that device
# over, so a run that died before signing out leaves nothing behind to add up.
DEVICE = "LIFEAGENTDIGEST"
# (status, the answer's JSON or None); status 0 when there was no answer
Ask = Callable[[str, str, Any, "str | None"], tuple[int, Any]]


def configured() -> dict[str, str] | None:
    """The door this box mirrors to, or None when it has none."""
    url = os.environ.get("DOOR_URL", "").rstrip("/")
    server, account = os.environ.get("DOOR_SERVER", ""), os.environ.get("DOOR_ACCOUNT", "")
    if not (url and server and account):
        return None
    return {
        "url": url,
        "me": f"@{account}:{server}",
        "account": account,
        "keeper": f"@{os.environ.get('DOOR_KEEPER', 'keeper')}:{server}",
        "secret": os.environ.get("DOOR_SECRET", "DOOR_PASSWORD"),
    }


def clean(text: str) -> str:
    """The digest as the keeper will take it: line ends, tabs and typed spaces kept,
    anything else that is not printable made a space, and cut to the keeper's limits."""
    kept = "".join(
        ch if ch in "\n\t" or ch.isprintable() or unicodedata.category(ch) == "Zs" else " "
        for ch in text
    )[:TEXT_CHARS]
    while len(kept.encode()) > TEXT_BYTES:
        kept = kept[: len(kept) - 100]
    return kept


def item(digest: str, day: date, letters: str = "T-") -> dict[str, Any]:
    """The day's digest as an item for the keeper. One a day: the id is the date, and the
    keeper takes an id once, so a second run the same day changes nothing he sees."""
    return {
        "id": f"{letters}{day.isoformat()}",
        "kind": "report",
        "about": f"your list for {day.isoformat()}",
        "why": "the morning digest, mirrored: Telegram is still where you answer it",
        "text": clean(digest),
    }


def invited(answer: Any, me: str, keeper: str) -> list[str]:
    """The rooms a sync answer says the keeper has invited this account to. An invitation
    from anyone else is not one of them."""
    waiting = (answer.get("rooms") or {}).get("invite") if isinstance(answer, Mapping) else None
    found = []
    for room, about in sorted(waiting.items()) if isinstance(waiting, Mapping) else []:
        events = ((about or {}).get("invite_state") or {}).get("events") or []
        if any(
            isinstance(e, Mapping)
            and e.get("type") == "m.room.member"
            and e.get("state_key") == me
            and e.get("sender") == keeper
            and (e.get("content") or {}).get("membership") == "invite"
            for e in events
        ):
            found.append(room)
    return found


class _NoRedirect(HTTPRedirectHandler):
    """An answer that points elsewhere is the answer: it is not followed."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _asking(base: str) -> Ask:
    """Requests to the door through no proxy, and never on to where an answer points:
    the sign-in carries the password, and it goes to the door and nowhere else."""
    opener = build_opener(ProxyHandler({}), _NoRedirect())

    def ask(method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        headers = {"content-type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        try:
            request = Request(base + path, data=data, headers=headers, method=method)
            with opener.open(request, timeout=_TIMEOUT_S) as answer:
                return answer.status, json.loads(answer.read())
        except HTTPError as refused:
            try:
                return refused.code, json.loads(refused.read())
            except ValueError:
                return refused.code, None
        except (OSError, ValueError):
            return 0, None

    return ask


def _need(status: int, answer: Any, what: str) -> Any:
    if status != 200 or not isinstance(answer, Mapping):
        code = answer.get("errcode") if isinstance(answer, Mapping) else None
        raise RuntimeError(f"the door: {what}: status {status}, {code or 'no error code'}")
    return answer


def my_room(ask: Ask, token: str, door: Mapping[str, str]) -> str | None:
    """The room this account hands in through: the one the keeper has invited it to
    (joined now), else the one it is already in that carries its name and has the keeper
    in it. None while the keeper has made none."""
    query = urlencode({"timeout": "0", "filter": json.dumps(
        {"room": {"timeline": {"limit": 0}, "state": {"types": ["m.room.member"]}},
         "presence": {"types": []}, "account_data": {"types": []}})})
    sync = _need(*ask("GET", f"{API}/sync?{query}", None, token), "sync")
    for room in invited(sync, door["me"], door["keeper"]):
        _need(*ask("POST", f"{API}/join/{quote(room, safe='')}", {}, token), "join")
        return room
    rooms = _need(*ask("GET", f"{API}/joined_rooms", None, token), "rooms")
    keeper = quote(door["keeper"], safe="")
    for room in sorted(rooms.get("joined_rooms", [])):
        base = f"{API}/rooms/{quote(room, safe='')}/state"
        _, name = ask("GET", f"{base}/m.room.name", None, token)
        _, is_in = ask("GET", f"{base}/m.room.member/{keeper}", None, token)
        named = isinstance(name, Mapping) and name.get("name") == f"hand-in: {door['account']}"
        kept = isinstance(is_in, Mapping) and is_in.get("membership") == "join"
        if named and kept:  # the keeper's room for this account, and the keeper is in it
            return str(room)
    return None


def hand_in(
    content: Mapping[str, Any], door: Mapping[str, str], ask: Ask | None = None
) -> str | None:
    """Sign in, hand the keeper one item, sign out. The event's id, or None when the
    keeper has not made this account a room yet."""
    ask = ask or _asking(door["url"])
    login = _need(*ask("POST", f"{API}/login", {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": door["account"]},
        "password": secret(door["secret"]),
        "device_id": DEVICE,
        "initial_device_display_name": "life-agent digest",
    }, None), "sign-in")
    token = str(login["access_token"])
    try:
        room = my_room(ask, token, door)
        if room is None:
            return None
        name = "item-" + hashlib.sha256(str(content["id"]).encode()).hexdigest()[:40]
        path = f"{API}/rooms/{quote(room, safe='')}/send/{ITEM_EVENT}/{name}"
        return str(_need(*ask("PUT", path, dict(content), token), "hand-in")["event_id"])
    finally:
        ask("POST", f"{API}/logout", {}, token)


def mirror(digest: str, day: date | None = None) -> str:
    """Hand today's digest to the door, if this box has one. Says what happened, in one
    line, and never raises: the digest's own sending must not depend on the door."""
    door = configured()
    if door is None:
        if os.environ.get("DOOR_URL"):  # half a configuration is a mistake, and is said
            return "door mirror not run: DOOR_URL is set, and DOOR_SERVER or DOOR_ACCOUNT is not"
        return "no door configured"
    try:
        sent = hand_in(item(digest, day or date.today()), door)
    except (Exception, SystemExit) as error:  # never into the caller
        return f"door mirror failed: {type(error).__name__}: {str(error)[:200]}"
    if sent is None:
        return "the door's keeper has made no room for this account yet"
    return f"handed to the door as {sent}"
