"""The door (reach/door.py): the morning digest handed to a door's keeper as one item a
day. Outbound only, configured by the deploying box. The door is where the digest goes;
with Telegram switched on it is a mirror beside Telegram, never in the way of that send.
Every name here is a synthetic stand-in (``*.example.test``)."""

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
            "messages": (200, {"chunk": []}),  # its own room, empty
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
    assert door.hand_over("a digest") == (False, "no door configured")
    monkeypatch.setenv("DOOR_URL", "http://door.example.test:6167")
    assert door.configured() is None  # half a configuration is none, and it is said
    assert door.hand_over("a digest") == (
        False, "not handed in: DOOR_URL is set, and DOOR_SERVER or DOOR_ACCOUNT is not"
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
        "why": "the morning digest: answer it in the Jarvis room (done N, later N)",
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
    assert door.hand_in(content, box, there.ask) == ("$e", "")
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
    assert door.hand_in(door.item("a digest", DAY), box, there.ask) == (None, "")
    assert not [r for r in there.routes() if r.startswith("PUT")]
    assert there.routes()[-1] == "POST /logout"


def test_a_door_that_fails_is_said_in_a_line_and_never_raised(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    down = Door(login=(0, None))
    monkeypatch.setattr(door, "_asking", lambda base: down.ask)
    assert door.hand_over("a digest", DAY) == (
        False, "not handed in: RuntimeError: the door: sign-in: status 0, no error code"
    )
    refused = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                   join=(200, {}), send=(403, {"errcode": "M_FORBIDDEN", "error": "private words"}))
    monkeypatch.setattr(door, "_asking", lambda base: refused.ask)
    said = door.hand_over("a digest", DAY)
    assert said == (
        False, "not handed in: RuntimeError: the door: hand-in: status 403, M_FORBIDDEN")
    assert refused.routes()[-1] == "POST /logout"  # signed out even so

    def no_secret(name: str) -> str:
        raise SystemExit(f"{name} not found in env or gnome-keyring")

    monkeypatch.setattr(door, "secret", no_secret)
    handed, said = door.hand_over("a digest", DAY)
    assert not handed and said.startswith("not handed in: SystemExit: DOOR_PASSWORD")


def test_the_hand_over_says_when_it_handed_in_and_when_there_is_no_room(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {}), send=(200, {"event_id": "$e"}))
    monkeypatch.setattr(door, "_asking", lambda base: there.ask)
    assert door.hand_over("a digest", DAY) == (True, "handed to the door as $e")
    monkeypatch.setattr(door, "_asking", lambda base: Door().ask)
    assert door.hand_over("a digest", DAY) == (
        False, "the door's keeper has made no room for this account yet")


def test_with_telegram_on_the_digest_is_mirrored_after_it_is_sent_and_a_failed_send_goes_on(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TELEGRAM_REACH", "on")  # the way back: Telegram first, the door a mirror
    order: list[str] = []
    monkeypatch.setattr(reach_digest, "owner_user_id", lambda: 7)
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: "the digest")

    def send(user_id: int, text: str) -> None:
        order.append("telegram")
        raise RuntimeError("telegram is down")

    monkeypatch.setattr(reach_digest.telegram, "send_message", send)
    monkeypatch.setattr(reach_digest.door, "hand_over", lambda text: order.append(f"door:{text}")
                        or (True, "handed to the door as $e"))
    # the mirror is not stopped by a failed send; the run then fails (issue #221)
    with pytest.raises(SystemExit):
        reach_digest.main()
    assert order == ["telegram", "door:the digest"]
    assert "door: handed to the door as $e" in capsys.readouterr().out
    # a box with no door says nothing about one
    monkeypatch.setattr(reach_digest.door, "hand_over", lambda text: (False, "no door configured"))
    with pytest.raises(SystemExit):
        reach_digest.main()
    assert "door" not in capsys.readouterr().out
    # and a door that fails beside a Telegram send that went does not fail the run
    monkeypatch.setattr(reach_digest.telegram, "send_message", lambda *_: None)
    monkeypatch.setattr(reach_digest.door, "hand_over", lambda text: (False, "not handed in: x"))
    reach_digest.main()  # returns: no SystemExit
    assert "door: not handed in: x" in capsys.readouterr().out
    # and no digest, no mirror
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: None)
    order.clear()
    reach_digest.main()
    assert order == []


# --- the door is where the digest goes (gfrmin/ops#274, win B3) -------------------------


def test_the_digest_goes_to_the_door_and_never_to_telegram(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(reach_digest, "owner_user_id", lambda: 7)
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: "the digest")
    monkeypatch.setattr(reach_digest.telegram, "send_message",
                        lambda *_: pytest.fail("Telegram was sent to while it is off"))
    handed: list[str] = []
    monkeypatch.setattr(reach_digest.door, "hand_over",
                        lambda text: handed.append(text) or (True, "handed to the door as $e"))
    reach_digest.main()  # returns: no SystemExit
    assert handed == ["the digest"]
    assert "door: handed to the door as $e" in capsys.readouterr().out


@pytest.mark.parametrize("said", [
    "not handed in: RuntimeError: the door: sign-in: status 0, no error code",
    "the door's keeper has made no room for this account yet",
    "no door configured",  # with Telegram off, a box with no door has nowhere to send
])
def test_a_digest_that_did_not_reach_the_door_fails_the_run_and_says_why(
    said: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(reach_digest, "owner_user_id", lambda: 7)
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: "the digest")
    monkeypatch.setattr(reach_digest.telegram, "send_message",
                        lambda *_: pytest.fail("Telegram was sent to while it is off"))
    monkeypatch.setattr(reach_digest.door, "hand_over", lambda text: (False, said))
    with pytest.raises(SystemExit) as stopped:
        reach_digest.main()
    assert stopped.value.code == 1
    assert f"door: {said}" in capsys.readouterr().err


def test_the_real_hand_over_is_what_the_digest_runs(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not a stand-in: the digest's main through door.hand_over to a door that takes it."""
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {}), send=(200, {"event_id": "$e"}))
    monkeypatch.setattr(door, "_asking", lambda base: there.ask)
    monkeypatch.setattr(reach_digest, "owner_user_id", lambda: 7)
    monkeypatch.setattr(reach_digest, "build_digest", lambda user_id: "the digest")
    reach_digest.main()
    sent = next(body for method, path, body, _ in there.asked if method == "PUT")
    assert sent["kind"] == "report" and sent["text"] == "the digest"
    assert "Jarvis room" in sent["why"]


# --- one list at a time (the owner's rule of 2026-11-26) -----------------------------------


def handed(named: str, event: str) -> dict[str, Any]:
    return {"type": door.ITEM_EVENT, "sender": ME, "event_id": event, "content": {"id": named}}


def withdrew(named: str) -> dict[str, Any]:
    return {"type": door.WITHDRAW_EVENT, "sender": ME, "event_id": "$w", "content": {"id": named}}


def refused(event: str) -> dict[str, Any]:
    return {"type": door.REFUSED_EVENT, "sender": KEEPER, "event_id": "$r",
            "content": {"event": event, "why": "no"}}


def test_the_earlier_lists_are_the_ones_it_handed_in_and_has_not_withdrawn() -> None:
    events = [
        handed("T-2026-01-02", "$today"),
        handed("T-2026-01-01", "$y"),
        handed("T-2025-12-30", "$old"),  # a day missed between: still found
        handed("T-2025-12-29", "$gone"), withdrew("T-2025-12-29"),
        handed("T-2025-12-28", "$bad"), refused("$bad"),  # the keeper never took it
        {**handed("T-2025-12-27", "$x"), "sender": "@someone:door.example.test"},
        handed("I-drill-1", "$i"),  # not a list
        {"type": door.REFUSED_EVENT, "sender": ME, "content": {"event": "$y"}},  # not the keeper
        "not an event", {"type": door.ITEM_EVENT, "sender": ME, "content": "no"},
    ]
    earlier = door.earlier_lists(events, ME, KEEPER, "T-2026-01-02")
    assert earlier == ["T-2025-12-30", "T-2026-01-01"]
    assert door.earlier_lists(None, ME, KEEPER, "T-2026-01-02") == []


def test_once_today_is_in_the_earlier_lists_are_withdrawn_after_it(box: dict[str, str]) -> None:
    room = {"chunk": [handed("T-2026-01-01", "$y"), handed("T-2025-12-31", "$z")]}
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {"room_id": "!b"}), send=(200, {"event_id": "$e"}),
                 messages=(200, room))
    assert door.hand_in(door.item("a digest", DAY), box, there.ask) == (
        "$e", "withdrew T-2025-12-31, T-2026-01-01")
    puts = [(path.split("/send/")[1].split("/")[0], body)
            for method, path, body, _ in there.asked if method == "PUT"]
    # today's first, so he is never left with none; then each earlier one, by its id
    assert [kind for kind, _ in puts] == [door.ITEM_EVENT, door.WITHDRAW_EVENT, door.WITHDRAW_EVENT]
    assert [body for _, body in puts[1:]] == [{"id": "T-2025-12-31"}, {"id": "T-2026-01-01"}]
    assert there.routes()[-1] == "POST /logout"


def test_a_withdrawal_that_fails_never_fails_the_days_hand_in(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {"room_id": "!b"}), send=(200, {"event_id": "$e"}),
                 messages=(500, {"errcode": "M_UNKNOWN"}))
    monkeypatch.setattr(door, "_asking", lambda base: there.ask)
    ok, said = door.hand_over("a digest", DAY)
    assert ok and said == (
        "handed to the door as $e; earlier lists not withdrawn:"
        " RuntimeError: the door: its own room: status 500, M_UNKNOWN")
    assert there.routes()[-1] == "POST /logout"


def test_with_nothing_earlier_nothing_is_withdrawn_and_nothing_more_is_said(
    box: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    there = Door(sync=(200, {"rooms": {"invite": invite("!b", KEEPER)}}),
                 join=(200, {"room_id": "!b"}), send=(200, {"event_id": "$e"}),
                 messages=(200, {"chunk": [handed("T-2026-01-02", "$e")]}))
    monkeypatch.setattr(door, "_asking", lambda base: there.ask)
    assert door.hand_over("a digest", DAY) == (True, "handed to the door as $e")
    assert [m for m, *_ in there.asked].count("PUT") == 1
