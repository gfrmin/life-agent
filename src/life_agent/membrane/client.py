"""client.py — the membrane wire transport (JSON-lines over stdio).

One line out, one line back. Ported from the credence-governor's proven
`MembraneClient` (`packages/governor_core/credence_governor_core/membrane.py:233-316`):
`spawn` launches the frozen `proplang-govhost` decider binary as a subprocess, wires its
stdin/stdout as write/read callables, and enforces a per-read timeout so a wedged driver
surfaces as an error instead of parking the caller on `readline()` forever (a timeout
caveat carries over unchanged: a driver that writes a partial line and then wedges passes
the readiness check and still blocks — rare enough to accept). `MembraneClient.__init__`
itself takes only the write/read/shutdown callables, so tests inject a scripted transport
with no process at all.

The wire's encoding contract lives in `request_json`: the govhost's minimal JSON-string
parser understands only the three escapes `\\" \\\\ \\n`. `json.dumps` always escapes
every control character (RFC 8259), but via its OWN vocabulary — `\\t`, `\\r`, `\\b`,
`\\f`, `\\uXXXX` — none of which the govhost can decode; shipping one would desync or
silently corrupt the session (a stray `\\t` from, say, an owner note copied into a
feature string). `request_json` therefore re-scans the compact encoding and rejects any
escape outside that three-name set before the line ever reaches `write_line`.
"""
from __future__ import annotations

import json
import os
import selectors
import shlex
import subprocess
from collections.abc import Callable

MEMBRANE_ENV = "LIFE_AGENT_MEMBRANE_COMMAND"
READ_TIMEOUT_ENV = "LIFE_AGENT_MEMBRANE_READ_TIMEOUT"
DEFAULT_READ_TIMEOUT_S = 300.0

# The only escapes the govhost's string parser decodes (membrane-wire.md's wire
# constraint) — the second character of a backslash escape must be one of these.
_ALLOWED_ESCAPES = frozenset('"\\n')


class MembraneError(RuntimeError):
    """Any wire failure: a non-dict reply, a reader exception, EOF, a read timeout, or
    a payload that the govhost's minimal parser could not round-trip."""


class MembraneClient:
    """The transport half, injectable for tests (pass write_line/read_line callables
    directly) or spawned (`spawn`) to drive a real subprocess."""

    def __init__(
        self,
        write_line: Callable[[str], None],
        read_line: Callable[[], str],
        shutdown: Callable[[], None] | None = None,
    ) -> None:
        self._write = write_line
        self._read = read_line
        self._shutdown = shutdown

    @classmethod
    def spawn(
        cls,
        argv: list[str],
        *,
        log: Callable[[str], None] = print,
        read_timeout_s: float = DEFAULT_READ_TIMEOUT_S,
    ) -> MembraneClient:
        log(f"life-agent: membrane engine = {' '.join(argv)}")
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def write_line(s: str) -> None:
            assert proc.stdin is not None
            proc.stdin.write(s + "\n")
            proc.stdin.flush()

        def read_line() -> str:
            assert proc.stdout is not None
            if read_timeout_s > 0:
                # a hung driver (alive, no reply) must surface as an error, not park
                # the caller forever. read_timeout_s <= 0 disables this check (blocks
                # on readline() directly) — the documented opt-out for a driver whose
                # per-tick replies are legitimately slow.
                sel = selectors.DefaultSelector()
                try:
                    sel.register(proc.stdout, selectors.EVENT_READ)
                    if not sel.select(timeout=read_timeout_s):
                        raise MembraneError(
                            f"membrane driver unresponsive ({read_timeout_s}s read timeout)"
                        )
                finally:
                    sel.close()
            line = proc.stdout.readline()
            if line == "":
                raise MembraneError("membrane driver closed the wire (EOF)")
            return line.rstrip("\n")

        def shutdown() -> None:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

        return cls(write_line, read_line, shutdown)

    @classmethod
    def from_env(cls, *, log: Callable[[str], None] = print) -> MembraneClient:
        cmd = os.environ.get(MEMBRANE_ENV)
        if not cmd:
            raise MembraneError(
                f"no membrane engine: set {MEMBRANE_ENV} to the proplang-govhost launch argv"
            )
        timeout = float(os.environ.get(READ_TIMEOUT_ENV, DEFAULT_READ_TIMEOUT_S))
        return cls.spawn(shlex.split(cmd), log=log, read_timeout_s=timeout)

    def request(self, obj: dict[str, object]) -> dict[str, object]:
        self._write(request_json(obj))
        try:
            line = self._read()
        except MembraneError:
            raise
        except Exception as exc:
            raise MembraneError(f"membrane read failed: {exc}") from exc
        if line == "":
            raise MembraneError("membrane driver closed the wire (EOF)")
        reply = json.loads(line)
        if not isinstance(reply, dict):
            raise MembraneError(f"malformed reply (not a JSON object): {reply!r}")
        return reply

    def shutdown(self) -> None:
        if self._shutdown is not None:
            self._shutdown()


def request_json(obj: dict[str, object]) -> str:
    """Compact, non-ASCII-preserving JSON for the membrane wire — no trailing newline
    (the caller's write_line appends the line terminator). Raises `MembraneError` if
    the encoding contains any escape the govhost's minimal parser cannot decode (see
    module docstring): only `\\"`, `\\\\`, and `\\n` are permitted."""
    encoded = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    i = 0
    while i < len(encoded):
        ch = encoded[i]
        if ch == "\\":
            nxt = encoded[i + 1] if i + 1 < len(encoded) else ""
            if nxt not in _ALLOWED_ESCAPES:
                raise MembraneError(
                    f"membrane wire: unsupported escape {encoded[i : i + 2]!r} "
                    '(the govhost decodes only \\" \\\\ \\n)'
                )
            i += 2
            continue
        if ord(ch) < 0x20 and ch != "\n":
            raise MembraneError(f"membrane wire: raw control char {ch!r} in payload")
        i += 1
    return encoded
