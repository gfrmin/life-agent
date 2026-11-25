"""Jarvis at the door (reach/matrix.py): the owner's words in jarvis's own room, answered
there, each once. Every name here is a synthetic stand-in (``*.example.test``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from life_agent.reach import jarvis, matrix
from life_agent.tasks import commands, store

SERVER = "door.example.test"
ME, OWNER = f"@jarvis:{SERVER}", f"@owner:{SERVER}"
ROOM = "!room:door.example.test"
USER = 12345


@pytest.fixture(autouse=True)
def temp_gtd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()


@pytest.fixture
def there(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("DOOR_URL", "http://door.example.test:6167/")
    monkeypatch.setenv("DOOR_SERVER", SERVER)
    monkeypatch.setenv("JARVIS_DOOR_ACCOUNT", "jarvis")
    monkeypatch.setenv("JARVIS_DOOR_OWNER", "owner")
    monkeypatch.setenv("JARVIS_DOOR_STATE", str(tmp_path / "kb" / "reach" / "jarvis-door.json"))
    monkeypatch.setattr(matrix, "secret", lambda name: f"the-{name}")
    configured = matrix.configured()
    assert configured is not None
    return configured


def message(event_id: str, body: str, sender: str = OWNER, **content: Any) -> dict[str, Any]:
    return {"type": "m.room.message", "event_id": event_id, "sender": sender,
            "content": {"msgtype": "m.text", "body": body, **content}}


def synced(batch: str, *events: dict[str, Any]) -> dict[str, Any]:
    return {"next_batch": batch, "rooms": {"join": {ROOM: {"timeline": {"events": list(events)}}}}}


class Door:
    """A door that answers each sync from a list, and keeps what it was asked."""

    def __init__(self, syncs: list[dict[str, Any]], joined: list[str] | None = None,
                 names: dict[str, str] | None = None, down_on: str | None = None,
                 refuse: str | None = None, owner_is: str | None = "join") -> None:
        self.syncs, self.joined, self.names = list(syncs), joined or [], names or {}
        self.down_on = down_on  # a reply whose text holds this finds the door down
        self.refuse = refuse  # a reply whose text holds this the door will never take
        self.owner_is = owner_is  # the owner's membership of the room
        self.invited: list[str] = []
        self.refused_with = 413  # the status of a refused reply
        self.invite_status = 200
        self.asked: list[tuple[str, str, Any]] = []
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        self.asked.append((method, path, body))
        route = path.split("?")[0]
        if route.endswith("/login"):
            return 200, {"access_token": "tok"}
        if route.endswith("/joined_rooms"):
            return 200, {"joined_rooms": self.joined}
        if "/state/m.room.member/" in route:  # PII-OK — a URL path on the server
            if self.owner_is is None:
                return 404, {"errcode": "M_NOT_FOUND"}
            return 200, {"membership": self.owner_is}
        if route.endswith("/invite"):
            self.invited.append(body["user_id"])
            return self.invite_status, {}
        if route.endswith("/state/m.room.name"):  # PII-OK — a URL path on the server
            room = route.split("/rooms/")[1].split("/")[0].replace("%21", "!").replace("%3A", ":")
            return (200, {"name": self.names[room]}) if room in self.names else (404, {})
        if route.endswith("/createRoom"):
            self.joined.append(ROOM)
            return 200, {"room_id": ROOM}
        if route.endswith("/sync"):
            return 200, self.syncs.pop(0)
        if "/send/m.room.message/" in route:  # PII-OK — a URL path on the server
            if self.down_on and self.down_on in json.dumps(body):
                return 0, None
            if self.refuse and self.refuse in json.dumps(body):
                return self.refused_with, {"errcode": "M_REFUSED"}
            self.sent.append((route.rsplit("/", 1)[1], body))
            return 200, {"event_id": "$reply"}
        return 404, {"errcode": "M_NOT_FOUND"}

    def query_of(self, n: int) -> dict[str, list[str]]:
        syncs = [p for m, p, _ in self.asked if p.split("?")[0].endswith("/sync")]
        return parse_qs(urlsplit(syncs[n]).query)


def echo(seen: list[tuple[str, str]]) -> matrix.Respond:
    def respond(text: str, identity: str) -> str:
        seen.append((text, identity))
        return f"you said {text}"
    return respond


def test_the_box_says_which_door_which_account_and_whose_words(there: dict[str, str]) -> None:
    assert there["me"] == ME and there["owner"] == OWNER and there["account"] == "jarvis"
    assert there["url"] == "http://door.example.test:6167"


@pytest.mark.parametrize("missing", ["DOOR_URL", "DOOR_SERVER", "JARVIS_DOOR_ACCOUNT",
                                     "JARVIS_DOOR_OWNER"])
def test_a_box_that_names_no_door_reads_none(
    there: dict[str, str], monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.delenv(missing)
    assert matrix.configured() is None
    matrix.loop(echo([]), ask=lambda *a: pytest.fail("asked the door"))  # returns at once


def test_by_default_what_it_reads_is_kept_beside_the_task_ledger(
    there: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JARVIS_DOOR_STATE")
    found = matrix.configured()
    assert found is not None and found["state"] == str(matrix.KB / "reach" / "jarvis-door.json")


def test_on_its_first_start_what_was_said_before_is_history(there: dict[str, str]) -> None:
    seen: list[tuple[str, str]] = []
    door = Door([synced("s1", message("$old", "done 3"))])
    kept: dict[str, Any] = {"room": ROOM}
    assert matrix.one_pass(door.ask, "tok", there, kept, echo(seen)) == 0
    assert seen == [] and door.sent == [] and kept == {"room": ROOM, "since": "s1"}
    assert door.query_of(0)["timeout"] == ["0"] and "since" not in door.query_of(0)
    assert json.loads(Path(there["state"]).read_text()) == kept


def test_the_owners_words_are_answered_in_the_room_as_a_notice_each_once(
    there: dict[str, str],
) -> None:
    seen: list[tuple[str, str]] = []
    door = Door([synced("s2", message("$a", "buy milk"), message("$b", "done 3"))])
    kept: dict[str, Any] = {"room": ROOM, "since": "s1"}
    assert matrix.one_pass(door.ask, "tok", there, kept, echo(seen)) == 2
    assert seen == [("buy milk", matrix.identity_of("$a")), ("done 3", matrix.identity_of("$b"))]
    assert [body for _, body in door.sent] == [
        {"msgtype": "m.notice", "body": "you said buy milk"},
        {"msgtype": "m.notice", "body": "you said done 3"},
    ]
    # each reply is named for the message it answers
    assert door.sent[0][0] != door.sent[1][0] and door.sent[0][0].startswith("reply-")
    assert kept == {"room": ROOM, "since": "s2", "answered": ["$a", "$b"]}
    assert door.query_of(0)["since"] == ["s1"] and door.query_of(0)["timeout"] == ["25000"]
    assert json.loads(Path(there["state"]).read_text()) == kept


@pytest.mark.parametrize(
    "event",
    [
        message("$x", "done 3", sender=f"@someone:{SERVER}"),  # not the owner
        message("$x", "done 3", sender=ME),  # its own reply
        message("$x", "done 3", msgtype="m.notice"),
        message("$x", "* done 4", **{"m.relates_to": {"rel_type": "m.replace"}}),  # an edit
        message("$x", "done 4", **{"m.relates_to": {"rel_type": "m.thread"}}),
        message("$x", "> <@jarvis> quoted only", **{"m.relates_to": {"m.in_reply_to": {}}}),
        message("$x", "   "),
        {"type": "m.reaction", "event_id": "$x", "sender": OWNER, "content": {}},
        {"type": "m.room.message", "sender": OWNER, "content": {"msgtype": "m.text", "body": "x"}},
        "not an event",
    ],
)
def test_nothing_but_the_owners_plain_words_is_read(there: dict[str, str], event: Any) -> None:
    seen: list[tuple[str, str]] = []
    door = Door([synced("s2", event)])
    assert matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"}, echo(seen)) == 0
    assert seen == [] and door.sent == []


def test_a_swipe_reply_is_read_as_his_words_without_what_it_quotes(
    there: dict[str, str],
) -> None:
    """The review of #224: a reply carries `m.in_reply_to`, and was passed over."""
    seen: list[tuple[str, str]] = []
    quoted = "> <@jarvis:door.example.test> Added [3] Buy milk\n> to #inbox\n\ndone 3"
    reply = {"m.relates_to": {"m.in_reply_to": {"event_id": "$prev"}}}
    door = Door([synced("s2", message("$a", quoted, **reply), message("$b", "later 4", **reply))])
    assert matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"}, echo(seen)) == 2
    assert [text for text, _ in seen] == ["done 3", "later 4"]


def test_a_message_of_his_that_begins_with_a_quote_is_read_whole(there: dict[str, str]) -> None:
    """The second review of #224: only a reply's quote is taken off; "> 3 done" is his."""
    seen: list[tuple[str, str]] = []
    door = Door([synced("s2", message("$a", "> 3 done\nand more"))])
    assert matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"}, echo(seen)) == 1
    assert [text for text, _ in seen] == ["> 3 done\nand more"]


def test_a_message_in_another_room_is_not_read(there: dict[str, str]) -> None:
    seen: list[tuple[str, str]] = []
    other = {"next_batch": "s2", "rooms": {"join": {"!other:x": {"timeline": {"events": [
        message("$a", "done 3")]}}}}}
    door = Door([other])
    assert matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"}, echo(seen)) == 0


def test_a_pass_cut_off_answers_the_rest_next_time_and_none_twice(there: dict[str, str]) -> None:
    """The door goes down after the first answer: it is kept, the position is not moved,
    and the next pass, given the same messages again, answers the second only."""
    seen: list[tuple[str, str]] = []
    batch = synced("s2", message("$a", "one"), message("$b", "two"))
    door = Door([batch, batch], down_on="you said two")
    kept: dict[str, Any] = {"room": ROOM, "since": "s1"}
    with pytest.raises(RuntimeError):
        matrix.one_pass(door.ask, "tok", there, kept, echo(seen))
    # the reply to "two" was made and written down as owed before it was sent
    assert json.loads(Path(there["state"]).read_text()) == {
        "room": ROOM, "since": "s1", "answered": ["$a"],
        "owed": {"event": "$b", "text": "you said two"}}
    door.down_on = None
    kept = matrix.load(Path(there["state"]))  # as a restart would find it
    assert matrix.one_pass(door.ask, "tok", there, kept, echo(seen)) == 0
    # the review of #224: nothing was asked again, and each reply went once
    assert [text for text, _ in seen] == ["one", "two"]
    assert [body["body"] for _, body in door.sent] == ["you said one", "you said two"]
    assert kept == {"room": ROOM, "since": "s2", "answered": ["$a", "$b"]}


def test_a_reply_the_door_will_never_take_is_said_in_one_line_and_the_room_goes_on(
    there: dict[str, str],
) -> None:
    """The review of #224: an answer too long for the door was sent again, and the model
    asked again, every 30 seconds for good, and nothing after it was answered."""
    seen: list[tuple[str, str]] = []
    door = Door([synced("s2", message("$a", "huge"), message("$b", "add milk"))],
                refuse="you said huge")
    kept: dict[str, Any] = {"room": ROOM, "since": "s1"}
    assert matrix.one_pass(door.ask, "tok", there, kept, echo(seen)) == 2
    assert [body["body"] for _, body in door.sent] == [matrix.NOT_SENT, "you said add milk"]
    assert [text for text, _ in seen] == ["huge", "add milk"]
    assert kept == {"room": ROOM, "since": "s2", "answered": ["$a", "$b"]}


@pytest.mark.parametrize("status", [400, 403, 413])
def test_when_even_the_one_line_is_refused_the_message_is_let_go(
    there: dict[str, str], status: int
) -> None:
    """The second review of #224: a 403 wedged the room as a 413 had."""
    door = Door([synced("s2", message("$a", "huge"), message("$b", "add milk"))],
                refuse="you said huge")
    door.refused_with = status
    kept: dict[str, Any] = {"room": ROOM, "since": "s1"}
    assert matrix.one_pass(door.ask, "tok", there, kept, echo([])) == 2
    assert [body["body"] for _, body in door.sent] == [matrix.NOT_SENT, "you said add milk"]
    everything = Door([synced("s2", message("$a", "huge"))], refuse="m.notice")
    everything.refused_with = status
    kept = {"room": ROOM, "since": "s1"}
    assert matrix.one_pass(everything.ask, "tok", there, kept, echo([])) == 1
    assert everything.sent == [] and kept["answered"] == ["$a"] and "owed" not in kept


@pytest.mark.parametrize("status", [0, 401, 408, 429, 500, 502])
def test_a_door_that_is_down_or_busy_keeps_the_reply_owed(
    there: dict[str, str], status: int
) -> None:
    door = Door([synced("s2", message("$a", "x"))], refuse="you said x")
    door.refused_with = status
    kept: dict[str, Any] = {"room": ROOM, "since": "s1"}
    with pytest.raises(RuntimeError):
        matrix.one_pass(door.ask, "tok", there, kept, echo([]))
    assert kept["owed"] == {"event": "$a", "text": "you said x"} and kept["since"] == "s1"


def test_a_reply_is_cut_to_the_doors_limits_before_it_is_sent(there: dict[str, str]) -> None:
    door = Door([synced("s2", message("$a", "x"))])
    matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"},
                    lambda text, identity: "y" * 100_000)
    (_, body), = door.sent
    assert len(body["body"]) == door_limits() and body["msgtype"] == "m.notice"


def door_limits() -> int:
    from life_agent.reach import door
    return door.TEXT_CHARS


def test_what_was_answered_is_kept_to_a_bound(there: dict[str, str]) -> None:
    door = Door([synced("s2", message("$new", "x"))])
    kept: dict[str, Any] = {"room": ROOM, "since": "s1",
                            "answered": [f"$e{n}" for n in range(matrix.ANSWERED_KEPT)]}
    matrix.one_pass(door.ask, "tok", there, kept, echo([]))
    assert len(kept["answered"]) == matrix.ANSWERED_KEPT and kept["answered"][-1] == "$new"


def test_a_sync_with_no_position_stops_the_pass(there: dict[str, str]) -> None:
    door = Door([{"rooms": {}}])
    with pytest.raises(RuntimeError, match="no position"):
        matrix.one_pass(door.ask, "tok", there, {"room": ROOM, "since": "s1"}, echo([]))


def test_a_kept_file_it_cannot_read_stops_it(tmp_path: Path) -> None:
    path = tmp_path / "kept.json"
    assert matrix.load(path) == {}
    path.write_text("[1, 2]")
    with pytest.raises(ValueError):
        matrix.load(path)
    path.write_text("{ cut")
    with pytest.raises(ValueError):
        matrix.load(path)


def test_its_room_is_the_one_kept_else_found_by_its_name_else_made_once(
    there: dict[str, str],
) -> None:
    kept = Door([], joined=[ROOM, "!x:y"])
    assert matrix.room_of(kept.ask, "tok", there, {"room": ROOM}) == ROOM
    assert not [p for m, p, _ in kept.asked if p.endswith("/createRoom")]
    named = Door([], joined=["!x:y", ROOM], names={ROOM: "Jarvis"})
    assert matrix.room_of(named.ask, "tok", there, {}) == ROOM  # the id was lost: found again
    assert not [p for m, p, _ in named.asked if p.endswith("/createRoom")]
    fresh = Door([], joined=["!x:y"], owner_is=None)
    assert matrix.room_of(fresh.ask, "tok", there, {}) == ROOM
    assert fresh.invited == []  # a new room invites him as it is made
    ((_, _, body),) = [(m, p, b) for m, p, b in fresh.asked if p.endswith("/createRoom")]
    assert body["invite"] == [OWNER] and body["preset"] == "private_chat"
    assert body["name"] == "Jarvis" and "initial_state" not in body  # no encryption asked for


@pytest.mark.parametrize(("owner_is", "invited"), [
    ("join", []), ("invite", []), ("leave", [OWNER]), (None, [OWNER]), ("ban", []),
])
def test_an_owner_who_has_left_the_room_is_invited_again(
    there: dict[str, str], owner_is: str | None, invited: list[str]
) -> None:
    """The review of #224: if he declined or left, the room was jarvis's alone for good."""
    door = Door([], joined=[ROOM], owner_is=owner_is)
    assert matrix.room_of(door.ask, "tok", there, {"room": ROOM}) == ROOM
    assert door.invited == invited
    # a door that refuses the invitation is said, and the room is read all the same
    refusing = Door([], joined=[ROOM], owner_is=owner_is)
    refusing.invite_status = 403
    assert matrix.room_of(refusing.ask, "tok", there, {"room": ROOM}) == ROOM


def test_the_loop_beats_after_each_pass_that_read_the_room_and_not_when_the_door_is_down(
    there: dict[str, str],
) -> None:
    """With Telegram off the door's passes are jarvis's dead-man beat (gfrmin/ops#274, B3):
    a pass that read the room beats; a door that cannot be read does not."""
    beats: list[int] = []
    matrix.loop(echo([]), ask=Door([synced("s1")], joined=[]).ask, forever=False,
                after_pass=lambda: beats.append(1))
    assert beats == [1]

    class DownOnRead(Door):  # signed in and in its room, and the door goes down on the read
        def ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
            if path.split("?")[0].endswith("/sync"):
                return 0, None
            return super().ask(method, path, body, token)

    with pytest.raises(RuntimeError, match="sync"):
        matrix.loop(echo([]), ask=DownOnRead([], joined=[]).ask, forever=False,
                    after_pass=lambda: beats.append(2))
    assert beats == [1]


def test_the_loop_signs_in_finds_its_room_keeps_it_and_reads(there: dict[str, str]) -> None:
    door = Door([synced("s1")], joined=[])
    matrix.loop(echo([]), ask=door.ask, forever=False)
    kept = json.loads(Path(there["state"]).read_text())
    assert kept == {"room": ROOM, "since": "s1"}
    login = next(b for m, p, b in door.asked if p.endswith("/login"))
    assert login["identifier"]["user"] == "jarvis" and login["device_id"] == matrix.DEVICE
    assert login["password"] == "the-DOOR_JARVIS_PASSWORD"


# --- jarvis.respond: one reply, whichever transport ------------------------------------


def test_a_task_added_from_a_door_message_twice_is_one_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(jarvis, "parse_intent", lambda text: {"action": "add", "text": text})
    identity = matrix.identity_of("$a")
    first = jarvis.respond("Buy milk", USER, identity=identity)
    again = jarvis.respond("Buy milk", USER, identity=identity)
    assert first.startswith("Added [1] Buy milk") and again == "Already added [1] Buy milk"
    assert store.get_tasks(USER).count("Buy milk") == 1
    assert len(commands.LEDGER_PATH.read_text().splitlines()) == 1  # one event in the ledger


def test_the_door_and_telegram_give_the_same_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jarvis, "parse_intent", lambda text: pytest.fail("the model was asked"))
    commands.add(USER, "Finish me")
    assert jarvis.door_reply("done 1", "door-x", USER) == "Completed: Finish me"


def test_a_fault_in_a_door_reply_is_said_in_the_room(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(text: str) -> dict[str, Any]:
        raise RuntimeError("the model is down")

    monkeypatch.setattr(jarvis, "parse_intent", broken)
    assert jarvis.door_reply("buy milk", "door-x", USER) == "Something went wrong. Try again?"


def test_a_refusal_by_the_model_is_said_in_the_room_and_a_stop_still_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The review of #225: core.llm raises an API refusal as SystemExit; let through, it
    stopped jarvis, and a refusal that lasts would have stopped it on every restart."""
    def refused(text: str) -> dict[str, Any]:
        raise SystemExit("Anthropic API 400: a refusal")

    monkeypatch.setattr(jarvis, "parse_intent", refused)
    assert jarvis.door_reply("buy milk", "door-x", USER) == "Something went wrong. Try again?"

    def stopped(text: str) -> dict[str, Any]:
        raise SystemExit(0)  # what SIGTERM's handler raises

    monkeypatch.setattr(jarvis, "parse_intent", stopped)
    with pytest.raises(SystemExit) as stop:
        jarvis.door_reply("buy milk", "door-x", USER)
    assert stop.value.code == 0


def test_with_telegram_on_jarvis_reads_the_door_beside_it_only_when_the_box_names_one(
    there: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TELEGRAM_REACH", "on")
    started: list[str] = []

    class _Thread:
        def __init__(self, target: Any, args: tuple[Any, ...], name: str, **more: Any) -> None:
            self.target, self.args, self.name, self.more = target, args, name, more

        def start(self) -> None:
            started.append(self.name)
            # a background thread: it never keeps the process up on its own
            assert self.target is matrix.loop
            assert self.more == dict(daemon=True)
            assert self.args[0]("done 99", "door-x") == "Task not found."  # the owner's store

    monkeypatch.setattr(jarvis.threading, "Thread", _Thread)
    monkeypatch.setattr(jarvis, "poll_loop", lambda: started.append("telegram"))
    monkeypatch.setattr(jarvis, "_user_id", lambda: USER)
    monkeypatch.setattr(jarvis.signal, "signal", lambda *a: None)
    jarvis.main()
    assert started == ["door", "telegram"]
    started.clear()
    monkeypatch.delenv("JARVIS_DOOR_OWNER")
    jarvis.main()
    assert started == ["telegram"]
