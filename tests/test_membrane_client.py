"""Hermetic tests for the membrane transport (life_agent.membrane.client).

No network, no external binary: the request/reply tests inject bare write/read
callables (the same idiom credence-governor's test_membrane.py uses); the spawn tests
use a tiny `sys.executable -c` echo child as the "real subprocess" case. These pin the
transport's contract — round-trip parsing, error mapping (non-dict reply / reader
exception / EOF / read timeout), and the wire's compact-JSON escape constraint (the
govhost's minimal string parser accepts only \\" \\\\ \\n) — not anything about the
proplang world/session shape, which later tasks add.
"""
from __future__ import annotations

import json
import os
import shlex
import sys

import pytest

from life_agent.membrane.client import MembraneClient, MembraneError, request_json

# --- real-subprocess fixtures: tiny stdlib-only children, no external binary ----------

# Echoes every stdin line straight back (round-trip + shutdown lifecycle).
_ECHO = "import sys\nfor line in sys.stdin:\n    sys.stdout.write(line)\n    sys.stdout.flush()\n"

# Reads one line, sleeps, then echoes it — long enough to force a short read timeout.
_SLOW_ECHO = (
    "import sys, time\n"
    "line = sys.stdin.readline()\n"
    "time.sleep(0.4)\n"
    "sys.stdout.write(line)\n"
    "sys.stdout.flush()\n"
)


def _echo_argv() -> list[str]:
    return [sys.executable, "-c", _ECHO]


def _slow_echo_argv() -> list[str]:
    return [sys.executable, "-c", _SLOW_ECHO]


# --- request(): injected write/read callables ------------------------------------------


def test_request_round_trip_parses_reply_dict() -> None:
    written: list[str] = []
    replies = iter([json.dumps({"ok": True, "n": 3})])
    client = MembraneClient(written.append, lambda: next(replies))

    reply = client.request({"tick": {"features": {"t": 0.0}}})

    assert reply == {"ok": True, "n": 3}
    assert json.loads(written[0]) == {"tick": {"features": {"t": 0.0}}}


def test_non_dict_reply_raises_membrane_error() -> None:
    client = MembraneClient(lambda _s: None, lambda: json.dumps([1, 2, 3]))
    with pytest.raises(MembraneError):
        client.request({"tick": {}})


def test_reader_exception_propagates_as_membrane_error() -> None:
    def boom() -> str:
        raise RuntimeError("wire broke")

    client = MembraneClient(lambda _s: None, boom)
    with pytest.raises(MembraneError):
        client.request({"tick": {}})


def test_reader_membrane_error_passes_through_unwrapped() -> None:
    def boom() -> str:
        raise MembraneError("membrane driver unresponsive (0.1s read timeout)")

    client = MembraneClient(lambda _s: None, boom)
    with pytest.raises(MembraneError, match="unresponsive"):
        client.request({"tick": {}})


def test_eof_empty_read_raises_membrane_error() -> None:
    client = MembraneClient(lambda _s: None, lambda: "")
    with pytest.raises(MembraneError):
        client.request({"tick": {}})


def test_shutdown_calls_injected_callable() -> None:
    calls: list[bool] = []
    client = MembraneClient(lambda _s: None, lambda: "{}", shutdown=lambda: calls.append(True))
    client.shutdown()
    assert calls == [True]


def test_shutdown_without_injected_callable_is_a_noop() -> None:
    client = MembraneClient(lambda _s: None, lambda: "{}")
    client.shutdown()  # must not raise


# --- request_json(): the wire escape constraint -----------------------------------------


def test_request_json_is_compact_and_preserves_non_ascii() -> None:
    s = request_json({"b": 1, "a": "héllo"})
    assert s == '{"b":1,"a":"héllo"}'
    assert " " not in s


def test_request_json_allows_quote_backslash_and_newline() -> None:
    s = request_json({"x": 'a\nb "q" c\\d'})
    assert json.loads(s) == {"x": 'a\nb "q" c\\d'}


def test_request_json_rejects_tab_in_a_string_value() -> None:
    with pytest.raises(MembraneError):
        request_json({"x": "a\tb"})


def test_request_json_rejects_carriage_return() -> None:
    with pytest.raises(MembraneError):
        request_json({"x": "a\rb"})


def test_request_json_rejects_uescaped_control_char() -> None:
    with pytest.raises(MembraneError):
        request_json({"x": "a\x01b"})


# --- from_env() ---------------------------------------------------------------------------


def test_from_env_missing_var_raises_membrane_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIFE_AGENT_MEMBRANE_COMMAND", raising=False)
    with pytest.raises(MembraneError):
        MembraneClient.from_env(log=lambda _m: None)


def test_from_env_spawns_and_parses_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    argv = " ".join(shlex.quote(a) for a in _echo_argv())
    monkeypatch.setenv("LIFE_AGENT_MEMBRANE_COMMAND", argv)
    monkeypatch.setenv("LIFE_AGENT_MEMBRANE_READ_TIMEOUT", "5")

    client = MembraneClient.from_env(log=lambda _m: None)
    try:
        assert client.request({"ping": 1}) == {"ping": 1}
    finally:
        client.shutdown()


# --- spawn(): a real subprocess, no external binary -----------------------------------------


def test_spawn_round_trip_and_graceful_shutdown() -> None:
    client = MembraneClient.spawn(_echo_argv(), log=lambda _m: None, read_timeout_s=5.0)
    try:
        assert client.request({"ping": 1}) == {"ping": 1}
        assert client.request({"ping": 2}) == {"ping": 2}
    finally:
        client.shutdown()


def test_spawn_read_timeout_raises_membrane_error() -> None:
    client = MembraneClient.spawn(_slow_echo_argv(), log=lambda _m: None, read_timeout_s=0.05)
    try:
        with pytest.raises(MembraneError, match="unresponsive"):
            client.request({"ping": 1})
    finally:
        client.shutdown()


def test_spawn_read_timeout_le_zero_disables_the_timeout() -> None:
    client = MembraneClient.spawn(_slow_echo_argv(), log=lambda _m: None, read_timeout_s=0.0)
    try:
        assert client.request({"ping": 1}) == {"ping": 1}  # the 0.4s sleep must not time out
    finally:
        client.shutdown()


def test_spawn_eof_on_child_exit_raises_membrane_error() -> None:
    client = MembraneClient.spawn(
        [sys.executable, "-c", "pass"], log=lambda _m: None, read_timeout_s=5.0
    )
    try:
        with pytest.raises(MembraneError, match="EOF"):
            client.request({"ping": 1})
    finally:
        client.shutdown()


def test_spawn_failure_closes_both_pty_fds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A spawn that never produces a process (ENOENT) must not leak the pty pair —
    the supervisor's respawn loop would otherwise leak one pair per attempt against
    a bad command (e.g. a typo'd LIFE_AGENT_MEMBRANE_COMMAND in the prod drop-in)."""
    import pty as _pty

    opened: list[int] = []
    real_openpty = _pty.openpty

    def recording_openpty() -> tuple[int, int]:
        master, slave = real_openpty()
        opened.extend((master, slave))
        return master, slave

    monkeypatch.setattr("life_agent.membrane.client.pty.openpty", recording_openpty)
    with pytest.raises(FileNotFoundError):
        MembraneClient.spawn(["/fake/nonexistent-engine-binary"], log=lambda _m: None)
    assert len(opened) == 2
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)
