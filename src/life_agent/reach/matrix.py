"""Jarvis at the door: the owner's task list and questions, in a room of jarvis's own.

The door is a Matrix server the owner reads on his phone (reach/door.py says more). Beside
the keeper's room, where agents' items are shown, jarvis keeps one room of its own with
him: he types there, and jarvis answers there. Since the owner moved his agents to the door
(gfrmin/ops#274, win B3) this room is where jarvis listens; Telegram goes on beside it only
while the box switches it on (``TELEGRAM_REACH``), and both carry the same replies
(``jarvis.respond``).

Configured entirely by the deploying box; nothing about any particular door is baked in:

- ``DOOR_URL``, ``DOOR_SERVER``  the door, as in reach/door.py
- ``JARVIS_DOOR_ACCOUNT``        jarvis's account there (``jarvis``)
- ``JARVIS_DOOR_OWNER``          the owner's account there (``guy``): the one whose words
                                 are read, and the one invited
- the password                   ``DOOR_JARVIS_PASSWORD`` in the env or the keyring
- ``JARVIS_DOOR_STATE``          where what was read is kept (default beside the task
                                 ledger, on the drive)

What it reads: in its own room only, messages of the owner's account only, plain text
only. Everything else is passed over. Its replies are notices, so they do not ring him.

NOTHING IS DONE TWICE. Where it has read to (the sync's position) and the last messages
it answered are kept in one file on the drive, beside the task ledger, and that file is
written after each message is answered: a laptop that takes the drive over goes on from
there. A task made from a message carries an identity made from that message's id, so a
message answered twice still adds one task. On its first start it reads from now on:
what was said in the room before is history, not a request.

A REPLY IS MADE ONCE (the review of #224). The reply is written down before it is sent,
so a door that is down is sent the same words again later and the model is not asked
again; and a reply the door will never take (a word too long) is replaced by one line
that says so, and the room goes on. Replies are cut to the door's limits first.

ONE ROOM. The room's id is kept in the same file. Before making one, the rooms it is in
are looked through for its own, so a room whose id was lost is found again, not made twice.
If the owner has left it, or declined, he is invited again when jarvis starts.

What it does not do: a sync answers at most 50 messages since the last one, and one sent
while jarvis was away beyond that is not read (it is said in the log). A swipe-reply is
read as a message, without the lines it quotes; an edit is not read.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from life_agent.core import secret
from life_agent.core.config import KB
from life_agent.reach import door

log = logging.getLogger("jarvis.door")

API = door.API
ROOM_NAME = "Jarvis"
DEVICE = "LIFEAGENTJARVIS"  # one device, taken over by each sign-in
WAIT_MS = 25_000  # how long one sync waits for something to say
ANSWERED_KEPT = 200  # how many answered message ids are kept against a second answer


def never_taken(status: int) -> bool:
    """A refusal that sending again will not change: any 4xx but a token the door has
    dropped (401: signing in again is the cure, and the reply stays owed until then), a
    request that took too long (408) and "too many requests" (429)."""
    return 400 <= status < 500 and status not in (401, 408, 429)

NOT_SENT = "That answer could not be sent here: the door refused it. Ask for less?"
# (status, the answer's JSON or None), as reach/door.py asks
Ask = door.Ask
# respond(text, identity) -> the reply: jarvis.respond with the owner's id bound
Respond = Callable[[str, str], str]


def configured() -> dict[str, str] | None:
    """The door jarvis speaks at, or None when this box names none."""
    url = os.environ.get("DOOR_URL", "").rstrip("/")
    server = os.environ.get("DOOR_SERVER", "")
    account = os.environ.get("JARVIS_DOOR_ACCOUNT", "")
    owner = os.environ.get("JARVIS_DOOR_OWNER", "")
    if not (url and server and account and owner):
        return None
    return {
        "url": url,
        "account": account,
        "me": f"@{account}:{server}",
        "owner": f"@{owner}:{server}",
        "state": os.environ.get("JARVIS_DOOR_STATE", str(KB / "reach" / "jarvis-door.json")),
    }


def load(path: Path) -> dict[str, Any]:
    """What was kept, or nothing yet. A file that cannot be read stops the loop: going on
    without it would answer the room's whole history again."""
    try:
        kept = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    if not isinstance(kept, dict):
        raise ValueError(f"{path} does not hold what jarvis keeps")
    return kept


def keep(path: Path, kept: Mapping[str, Any]) -> None:
    """Write what was kept, whole or not at all."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = path.with_name(f".{path.name}.new")
    fresh.write_text(json.dumps(kept, sort_keys=True))
    os.replace(fresh, path)


def sign_in(ask: Ask, there: Mapping[str, str]) -> str:
    login = door._need(*ask("POST", f"{API}/login", {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": there["account"]},
        "password": secret("DOOR_JARVIS_PASSWORD"),
        "device_id": DEVICE,
        "initial_device_display_name": "life-agent jarvis",
    }, None), "sign-in")
    return str(login["access_token"])


def room_of(ask: Ask, token: str, there: Mapping[str, str], kept: dict[str, Any]) -> str:
    """Its room with the owner: the one kept, else one it is in by its name, else a new
    one, unencrypted, to which the owner is invited."""
    rooms = door._need(*ask("GET", f"{API}/joined_rooms", None, token), "rooms")
    joined = [str(r) for r in rooms.get("joined_rooms", [])]
    if kept.get("room") in joined:
        return _with_owner(ask, token, there, str(kept["room"]))
    for room in sorted(joined):
        state = f"{API}/rooms/{quote(room, safe='')}/state"  # PII-OK — a URL path on the server
        _, name = ask("GET", f"{state}/m.room.name", None, token)
        if isinstance(name, Mapping) and name.get("name") == ROOM_NAME:
            return _with_owner(ask, token, there, room)
    made = door._need(*ask("POST", f"{API}/createRoom", {
        "name": ROOM_NAME,
        "topic": "Your tasks and questions: type as you would to Jarvis on Telegram.",
        "preset": "private_chat",
        "visibility": "private",
        "invite": [there["owner"]],
        "is_direct": True,
    }, token), "make the room")
    return str(made["room_id"])


def _with_owner(ask: Ask, token: str, there: Mapping[str, str], room: str) -> str:
    """The room, with the owner in it or invited to it: one who has left or declined is
    invited again (the review of #224: else the room was jarvis's alone for good). One the
    room has banned is not."""
    state = f"{API}/rooms/{quote(room, safe='')}/state"  # PII-OK — a URL path on the server
    _, member = ask("GET", f"{state}/m.room.member/{quote(there['owner'], safe='')}", None, token)
    membership = member.get("membership") if isinstance(member, Mapping) else None
    if membership in (None, "leave"):
        log.info("The owner is not in the door room: inviting him again")
        status, _ = ask("POST", f"{API}/rooms/{quote(room, safe='')}/invite",
                        {"user_id": there["owner"]}, token)
        if status != 200:  # said, and the room is read all the same
            log.warning("The door refused to invite the owner again (%s)", status)
    return room


def _filter(room: str) -> str:
    return json.dumps({
        "room": {"rooms": [room], "timeline": {"types": ["m.room.message"], "limit": 50},
                 "state": {"types": []}, "ephemeral": {"types": []},
                 "account_data": {"types": []}},
        "presence": {"types": []}, "account_data": {"types": []},
    })


def _unquoted(body: str, content: Mapping[str, Any]) -> str:
    """His own words. A reply may carry the lines it quotes ("> ...") before them, and
    those are not his; a message that is no reply is read whole, "> 3 done" and all."""
    if "m.relates_to" not in content:
        return body.strip()
    lines = body.split("\n")
    if lines and lines[0].startswith("> "):
        while lines and lines[0].startswith(">"):
            lines.pop(0)
    return "\n".join(lines).strip()


def _new_words(content: Mapping[str, Any]) -> bool:
    """A message of its own, or a reply to one: not an edit or anything else related."""
    related = content.get("m.relates_to")
    if related is None:
        return True
    return isinstance(related, Mapping) and set(related) == {"m.in_reply_to"}


def said(answer: Any, room: str, owner: str) -> list[tuple[str, str]]:
    """(event id, text) of each plain-text message of the owner's in the room, in order.
    Nobody else's words, and nothing that is not a plain message, are ever read."""
    joined = ((answer.get("rooms") or {}).get("join") or {}) if isinstance(answer, Mapping) else {}
    timeline = (joined.get(room) or {}).get("timeline") or {}
    if timeline.get("limited"):
        log.warning("The door: more was said than one sync holds; the earliest is not read")
    events = timeline.get("events") or []
    found = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        content = event.get("content") or {}
        body = content.get("body") if isinstance(content, Mapping) else None
        if (
            event.get("type") == "m.room.message"
            and event.get("sender") == owner
            and isinstance(event.get("event_id"), str)
            and isinstance(content, Mapping)
            and content.get("msgtype") == "m.text"
            and _new_words(content)  # an edit is not a new word; a reply is
            and isinstance(body, str)
            and _unquoted(body, content)
        ):
            found.append((event["event_id"], _unquoted(body, content)))
    return found


def identity_of(event_id: str) -> str:
    """A task made from this message is this task, however often it is answered."""
    return "door-" + hashlib.sha256(event_id.encode()).hexdigest()[:32]


def reply(ask: Ask, token: str, room: str, event_id: str, text: str) -> int:
    """Send a notice in the room, named for the message it answers: one reply to it, and
    no ring (a notice does not notify). The door's status: 200 when it took it."""
    txn = "reply-" + hashlib.sha256(event_id.encode()).hexdigest()[:40]
    sent = f"{API}/rooms/{quote(room, safe='')}/send"  # PII-OK — a URL path on the server
    path = f"{sent}/m.room.message/{txn}"
    status, _ = ask("PUT", path, {"msgtype": "m.notice", "body": door.clean(text)}, token)
    return status


def _deliver(ask: Ask, token: str, room: str, kept: dict[str, Any], path: Path) -> None:
    """Send the reply that is written down as owed, and write down that it went. One the
    door will never take is replaced by NOT_SENT; a door that is down is tried again by
    the next pass, with the same words, and no model is asked again."""
    owed = kept["owed"]
    status = reply(ask, token, room, owed["event"], owed["text"])
    if never_taken(status) and owed["text"] != NOT_SENT:
        log.warning("The door refused a reply (%s): saying so instead", status)
        kept["owed"] = owed = {**owed, "text": NOT_SENT}
        keep(path, kept)
        status = reply(ask, token, room, owed["event"], NOT_SENT)
    if never_taken(status):
        log.warning("The door refused even that (%s): the message is let go", status)
    elif status != 200:
        raise RuntimeError(f"the door: reply: status {status}")
    answered = [str(e) for e in kept.get("answered", [])]
    kept["answered"] = [*answered, owed["event"]][-ANSWERED_KEPT:]
    del kept["owed"]
    keep(path, kept)


def one_pass(ask: Ask, token: str, there: Mapping[str, str], kept: dict[str, Any],
             respond: Respond, wait_ms: int = WAIT_MS) -> int:
    """Read what the owner said since the last pass and answer each message; return how
    many were answered. `kept` is changed in place and written after each answer."""
    path = Path(there["state"])
    room = str(kept["room"])
    if kept.get("owed"):  # a reply made and not yet sent: send it, ask nothing again
        _deliver(ask, token, room, kept, path)
    since = kept.get("since")
    query = {"filter": _filter(room), "timeout": str(wait_ms if since else 0)}
    if since:
        query["since"] = str(since)
    answer = door._need(*ask("GET", f"{API}/sync?{urlencode(query)}", None, token), "sync")
    batch = answer.get("next_batch")
    if not isinstance(batch, str):
        raise RuntimeError("the door: sync gave no position to read on from")
    if not since:  # the first start: what was said before is history
        kept["since"] = batch
        keep(path, kept)
        return 0
    done = 0
    for event_id, text in said(answer, room, there["owner"]):
        if event_id in kept.get("answered", []):
            continue
        kept["owed"] = {"event": event_id, "text": respond(text, identity_of(event_id))}
        keep(path, kept)  # before it is sent: the model is never asked twice for it
        _deliver(ask, token, room, kept, path)
        done += 1
    kept["since"] = batch
    keep(path, kept)
    return done


def loop(respond: Respond, ask: Ask | None = None, *, forever: bool = True,
         after_pass: Callable[[], None] = lambda: None) -> None:
    """Sign in, find or make the room, and answer what the owner says there, for as long
    as the process runs. A door that is down is waited for; it never stops Telegram.
    `after_pass` runs after each pass that read the room (jarvis's dead-man beat), and
    not while the door is down, so a door jarvis cannot hear is heard of."""
    there = configured()
    if there is None:
        log.info("No door configured for jarvis: the door is not read")
        return
    ask = ask or door._asking(there["url"], timeout=WAIT_MS / 1000 + 20)
    path = Path(there["state"])
    while True:
        try:
            kept = load(path)
            token = sign_in(ask, there)
            room = room_of(ask, token, there, kept)
            if kept.get("room") != room:
                kept["room"] = room
                keep(path, kept)
            log.info("Reading the door room %s", room)
            while True:
                one_pass(ask, token, there, kept, respond)
                after_pass()
                if not forever:
                    return
        except Exception:
            log.exception("The door: stopped; trying again in 30s")
            if not forever:
                raise
            time.sleep(30)
