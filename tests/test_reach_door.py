"""The door mirror (reach/door.py): the morning digest handed to a door's keeper as one
item a day. Outbound only, configured by the deploying box, and never in the way of the
digest's own sending. Every name here is a synthetic stand-in (``*.example.test``)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from life_agent.reach import digest as reach_digest
from life_agent.reach import door

SERVER = "door.example.test"
ME, KEEPER = f"@today:{SERVER}", f"@keeper:{SERVER}"
DAY = date(2026, 1, 2)


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("DOOR_URL", "http://door.example.test:6167/")
    monkeypatch.setenv("DOOR_SERVER", SERVER)
    monkeypatch.setenv("DOOR_ACCOUNT", "today")
    monkeypatch.delenv("DOOR_KEEPER", raising=False)
    monkeypatch.delenv("DOOR_SECRET", raising=False)
    monkeypatch.setattr(door, "secret", lambda name: f"the-{name}")
    configured = door.configured()
    assert configured is not None
    return configured


def invite(room: str, sender: str, to: str = ME) -> dict[str, Any]:
    member = {"type": "m.room.member", "state_key": to, "sender": sender,
              "content": {"membership": "invite"}}
    return {room: {"invite_state": {"events": [member]}}}


class Door:
    """A door that is a table of answers, and a list of what it was asked."""

    def __init__(self, **answers: tuple[int, Any]) -> None:
        self.answers = {
            "login": (200, {"access_token": "tok"}),
            "sync": (200, {"rooms": {}}),
            "joined_rooms": (200, {"joined_rooms": []}),
            "logout": (200, {}),
            **answers,
        }
        self.asked: list[tuple[str, str, Any, str | None]] = []

    def ask(self, method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        self.asked.append((method, path, body, token))
        route = path.split("?")[0]
        for key, answer in self.answers.items():
            if route.endswith(key) or f"/{key}/" in route:
                return answer
        return 404, {"errcode": "M_NOT_FOUND"}

    def routes(self) -> list[str]:
        return [
            f"{method} {path.split('?')[0].replace(door.API, '')}"
            for method, path, _, _ in self.asked
        ]


def test_a_box_with_no_door_mirrors_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DOOR_URL", "DOOR_SERVER", "DOOR_ACCOUNT"):
        monkeypatch.delenv(name, raising=False)
    assert door.configured() is None
    assert door.mirror("a digest") == "no door configured"
    monkeypatch.setenv("DOOR_URL", "http://door.example.test:6167")
    assert door.configured() is None  # half a configuration is none, and it is said
    assert door.mirror("a digest") == (
        "door mirror not run: DOOR_URL is set, and DOOR_SERVER or DOOR_ACCOUNT is not"
    )


def test_the_box_says_which_door_and_which_account(box: dict[str, str]) -> None:
    assert box == {
        "url": "http://door.example.test:6167",
        "me": ME,
        "account": "today",
        "keeper": KEEPER,
        "secret": "DOOR_PASSWORD",
    }


def test_the_days_digest_is_one_item_named_by_its_date() -> None:
    assert door.item("TODAY'S FOCUS:\n  [1] A task", DAY) == {
        "id": "T-2026-01-02",
        "kind": "report",
        "about": "your list for 2026-01-02",
        "why": "the morning digest, mirrored: Telegram is still where you answer it",
        "text": "TODAY'S FOCUS:\n  [1] A task",
    }


def test_the_text_is_made_one_the_keeper_takes() -> None:
    nbsp, bell, cr, override = chr(0xA0), chr(7), chr(13), chr(0x202E)
    dirty = f"tab\there\nnbsp{nbsp}bell{bell}cr{cr}override{override}."
    assert door.clean(dirty) == f"tab\there\nnbsp{nbsp}bell cr override ."
    assert len(door.clean("x" * 20000)) == door.TEXT_CHARS
    wide = door.clean(chr(0x1F600) * 16000)
    assert len(wide.encode()) <= door.TEXT_BYTES and wide


def test_only_the_keepers_invitation_is_one() -> None:
    answer = {"rooms": {"invite": {**invite("!b", KEEPER), **invite("!a", f"@someone:{SERVER}"),
                                   **invite("!c", KEEPER, to=KEEPER)}}}
    assert door.invited(answer, ME, KEEPER) == ["!b"]
    for nothing in ({}, {"rooms": {}}, {"rooms": {"invite": []}}, None, []):
        assert door.invited(nothing, ME, KEEPER) == []


def test_invited_it_joins_hands_the_item_in_and_signs_out(box: dict[str, str]) -> None:
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {"room_id": "!b"}), send=(200, {"event_id": "$e"}))
    content = door.item("a digest", DAY)
    assert door.hand_in(content, box, there.ask) == "$e"
    assert there.routes()[:3] == ["POST /login", "GET /sync", "POST /join/%21b"]
    method, path, body, token = there.asked[3]
    assert (method, body, token) == ("PUT", content, "tok")
    assert path.startswith(f"{door.API}/rooms/%21b/send/{door.ITEM_EVENT}/item-")
    assert there.routes()[-1] == "POST /logout"
    # the password is the one the box names, and it goes nowhere but the sign-in
    assert there.asked[0][2]["password"] == "the-DOOR_PASSWORD"
    assert there.asked[0][2]["identifier"] == {"type": "m.id.user", "user": "today"}
    # one device, by name: a run that died before signing out leaves none behind to add up
    assert there.asked[0][2]["device_id"] == door.DEVICE


def test_the_password_goes_to_the_door_through_no_proxy_and_follows_no_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    class Opener:
        def open(self, request: Any, timeout: float) -> Any:
            raise OSError("no door here")

    def build(*handlers: Any) -> Opener:
        seen["handlers"] = handlers
        return Opener()

    monkeypatch.setenv("http_proxy", "http://proxy.example.test:3128")
    monkeypatch.setattr(door, "build_opener", build)
    ask = door._asking("http://door.example.test:6167")
    assert ask("POST", f"{door.API}/login", {"password": "p"}, None) == (0, None)
    proxy, redirect = seen["handlers"]
    assert isinstance(proxy, door.ProxyHandler) and proxy.proxies == {}  # whatever the env says
    assert isinstance(redirect, door._NoRedirect)
    elsewhere = "http://elsewhere.example.test"
    assert redirect.redirect_request(None, None, 302, "Found", {}, elsewhere) is None


def test_already_in_its_room_it_finds_it_by_its_name_and_the_keeper(box: dict[str, str]) -> None:
    keeper = door.quote(KEEPER, safe="")

    def ask(method: str, path: str, body: Any, token: str | None) -> tuple[int, Any]:
        route = path.split("?")[0]
        table: dict[str, tuple[int, Any]] = {
            "/sync": (200, {"rooms": {}}),
            "/joined_rooms": (200, {"joined_rooms": ["!other", "!mine", "!lookalike"]}),
            "/rooms/%21other/state/m.room.name": (200, {"name": "something else"}),
            "/rooms/%21mine/state/m.room.name": (200, {"name": "hand-in: today"}),
            "/rooms/%21lookalike/state/m.room.name": (200, {"name": "hand-in: today"}),
            f"/rooms/%21mine/state/m.room.member/{keeper}": (200, {"membership": "join"}),
            f"/rooms/%21lookalike/state/m.room.member/{keeper}": (200, {"membership": "leave"}),
        }
        return table.get(route.replace(door.API, ""), (404, {"errcode": "M_NOT_FOUND"}))

    assert door.my_room(ask, "tok", box) == "!mine"  # not the one the keeper is not in


def test_with_no_room_yet_nothing_is_handed_in_and_it_still_signs_out(box: dict[str, str]) -> None:
    there = Door()
    assert door.hand_in(door.item("a digest", DAY), box, there.ask) is None
    assert not [r for r in there.routes() if r.startswith("PUT")]
    assert there.routes()[-1] == "POST /logout"


def test_a_door_that_fails_is_said_in_a_line_and_never_raised(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    down = Door(login=(0, None))
    monkeypatch.setattr(door, "_asking", lambda base: down.ask)
    assert door.mirror("a digest", DAY) == (
        "door mirror failed: RuntimeError: the door: sign-in: status 0, no error code"
    )
    refused = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                   join=(200, {}), send=(403, {"errcode": "M_FORBIDDEN", "error": "private words"}))
    monkeypatch.setattr(door, "_asking", lambda base: refused.ask)
    said = door.mirror("a digest", DAY)
    assert said == "door mirror failed: RuntimeError: the door: hand-in: status 403, M_FORBIDDEN"
    assert refused.routes()[-1] == "POST /logout"  # signed out even so

    def no_secret(name: str) -> str:
        raise SystemExit(f"{name} not found in env or gnome-keyring")

    monkeypatch.setattr(door, "secret", no_secret)
    assert door.mirror("a digest", DAY).startswith("door mirror failed: SystemExit: DOOR_PASSWORD")


def test_the_mirror_says_when_it_handed_in_and_when_there_is_no_room(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {}), send=(200, {"event_id": "$e"}))
    monkeypatch.setattr(door, "_asking", lambda base: there.ask)
    assert door.mirror("a digest", DAY) == "handed to the door as $e"
    monkeypatch.setattr(door, "_asking", lambda base: Door().ask)
    assert door.mirror("a digest", DAY) == "the door's keeper has made no room for this account yet"


def test_the_digest_is_mirrored_after_it_is_sent_and_a_failed_send_does_not_stop_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    order: list[str] = []
    monkeypatch.setattr(reach_digest, "owner_user_id", lambda: 7)
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: "the digest")

    def send(user_id: int, text: str) -> None:
        order.append("telegram")
        raise RuntimeError("telegram is down")

    monkeypatch.setattr(reach_digest.telegram, "send_message", send)
    monkeypatch.setattr(reach_digest.door, "mirror",
                        lambda text: order.append(f"door:{text}") or "handed to the door as $e")
    # the mirror is not stopped by a failed send; the run then fails (issue #221)
    with pytest.raises(SystemExit):
        reach_digest.main()
    assert order == ["telegram", "door:the digest"]
    assert "door: handed to the door as $e" in capsys.readouterr().out
    # a box with no door says nothing about one
    monkeypatch.setattr(reach_digest.door, "mirror", lambda text: "no door configured")
    with pytest.raises(SystemExit):
        reach_digest.main()
    assert "door" not in capsys.readouterr().out
    # and no digest, no mirror
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: None)
    order.clear()
    reach_digest.main()
    assert order == []
