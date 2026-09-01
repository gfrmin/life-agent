"""client.py — the membrane wire transport (JSON-lines over stdio).

One line out, one line back. Ported from the credence-governor's proven
`MembraneClient` (`packages/governor_core/credence_governor_core/membrane.py:233-316`):
`spawn` launches the frozen `proplang-host` decider binary as a subprocess (its stdout on
a pty slave — see the in-function note on GHC buffering), wires write/read callables, and
enforces a per-read timeout so a wedged driver
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

import contextlib
import json
import os
import pty
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
        # The child's stdout is a PTY SLAVE, not a pipe: the re-derived proplang-host's
        # hostMain (src/PropLang/Host.hs) is getLine/putStrLn with no hSetBuffering, so
        # GHC block-buffers stdout on a pipe and replies do not flush until stdin closes
        # — measured in the B0 wire spike (2026-07-19). A tty flips GHC to line
        # buffering, restoring the wire's "one request, one reply, synchronous". The
        # shim belongs engine-side (one hSetBuffering line); carry it here until then.
        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=slave_fd,
            )
        except OSError:
            # a failed spawn (ENOENT, EACCES) must not leak the pty pair: nothing else
            # ever learns these fds exist, so the supervisor's respawn loop would leak
            # one pair per attempt against a bad command
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)
        read_buf = bytearray()

        def write_line(s: str) -> None:
            assert proc.stdin is not None
            proc.stdin.write((s + "\n").encode("utf-8"))
            proc.stdin.flush()

        def read_line() -> str:
            # a hung driver (alive, no reply) must surface as an error, not park the
            # caller forever. read_timeout_s <= 0 blocks indefinitely — the documented
            # opt-out for a driver whose per-tick replies are legitimately slow.
            while b"\n" not in read_buf:
                sel = selectors.DefaultSelector()
                try:
                    sel.register(master_fd, selectors.EVENT_READ)
                    timeout = read_timeout_s if read_timeout_s > 0 else None
                    if not sel.select(timeout=timeout):
                        raise MembraneError(
                            f"membrane driver unresponsive ({read_timeout_s}s read timeout)"
                        )
                finally:
                    sel.close()
                try:
                    chunk = os.read(master_fd, 65536)
                except OSError:  # pty master EIO after the child exits = EOF
                    chunk = b""
                if chunk == b"":
                    raise MembraneError("membrane driver closed the wire (EOF)")
                read_buf.extend(chunk)
            line, _, rest = bytes(read_buf).partition(b"\n")
            read_buf[:] = rest
            return line.decode("utf-8").rstrip("\r")

        def shutdown() -> None:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            finally:
                with contextlib.suppress(OSError):
                    os.close(master_fd)

        return cls(write_line, read_line, shutdown)

    @classmethod
    def from_env(cls, *, log: Callable[[str], None] = print) -> MembraneClient:
        cmd = os.environ.get(MEMBRANE_ENV)
        if not cmd:
            raise MembraneError(
                f"no membrane engine: set {MEMBRANE_ENV} to the proplang-host launch argv"
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
        try:
            reply = json.loads(line)
        except ValueError as exc:
            # A reply line that will not parse is a WIRE failure like any other, and
            # this class's contract says every wire failure surfaces as MembraneError.
            # It is not hypothetical: HEAD's tick refusals are built with Haskell `show`
            # on the offending name list, so `["act"]` reaches the wire with its inner
            # quotes unescaped -- invalid JSON, against the engine's own wire rule that
            # strings escape `"`. Letting JSONDecodeError escape means a caller that
            # handles every documented failure still dies on a REFUSAL.
            raise MembraneError(f"unparsable reply line: {line!r}") from exc
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
