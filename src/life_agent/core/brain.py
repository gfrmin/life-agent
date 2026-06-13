"""The credence seam — a thin JSON-RPC 2.0 client over stdio (bayesian-foundations §11).

This is the L2 transport: posteriors, conditioning, expectations, and EU decisions run
through credence's **skin** (``$CREDENCE_REPO/apps/skin/server.jl``; wire protocol in
``apps/skin/protocol.md`` — newline-delimited JSON-RPC 2.0, opaque state handles).
Language-neutral, so it passes the PRINCIPLES §5 seam diagnostic; zero new Python
dependencies; promotion to an always-on daemon (Tailscale-only, PRINCIPLES §13) is the
named successor behind this same API.

The method surface is exactly the §11 mapping — conjugate states, ``condition``,
``expect``, ``optimise`` — not the skin's full surface (program_space, DSL environments
stay in credence until the stage that needs them, §12 stage 5). Transport mechanics
(the ready sentinel, the bounded shutdown ladder) are adapted from the proven
``credence/apps/skin/client.py``.

The transport is injectable (:class:`Transport`), so everything above the pipe is
hermetically testable; :meth:`Brain.spawn` builds the real Julia subprocess transport.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import select
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol, Self

log = logging.getLogger(__name__)

# The sibling credence checkout (the brain is credence — PRINCIPLES §14). Out-of-tree,
# machine-specific, hence env-derived like the KB paths in config.py.
CREDENCE_REPO = Path(os.environ.get("CREDENCE_REPO", str(Path.home() / "git/credence")))

# Julia cold-compile on first spawn is slow (minutes on first run after an update);
# the generous ceiling is the skin client's proven default.
STARTUP_TIMEOUT = 120.0


class BrainError(Exception):
    """A skin-side error (JSON-RPC error object) or a transport failure."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class Transport(Protocol):
    """One line out, one line in — the wire beneath the protocol."""

    def send(self, line: str) -> None: ...

    def recv(self) -> str: ...

    def close(self) -> None: ...


class SubprocessTransport:
    """Spawns the skin process and frames newline-delimited JSON over its stdio.

    Startup blocks until the server's ready sentinel (``{"status": "ready"}``) arrives,
    polling for early crash; ``close()`` is the bounded shutdown ladder (stdin EOF →
    wait → SIGTERM → wait → SIGKILL), guaranteed to finish.
    """

    def __init__(self, argv: list[str], *, startup_timeout: float = STARTUP_TIMEOUT) -> None:
        log.info("starting skin process: %s", " ".join(argv))
        self._process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        self._wait_for_ready(startup_timeout)

    def _wait_for_ready(self, timeout: float) -> None:
        proc = self._process
        assert proc.stdout is not None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            code = proc.poll()
            if code is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise BrainError(-1, f"skin process exited with code {code} before "
                                     f"ready sentinel. stderr: {stderr}")
            readable, _, _ = select.select(
                [proc.stdout.fileno()], [], [],
                min(max(deadline - time.monotonic(), 0.0), 1.0))
            if not readable:
                continue
            line = proc.stdout.readline()
            if not line:
                continue  # EOF: poll() catches the exit next iteration
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # stray non-JSON stdout line; stderr carries warnings
            if isinstance(msg, dict) and msg.get("status") == "ready":
                log.info("skin process ready")
                return
        raise BrainError(-1, f"skin process did not emit ready sentinel within {timeout}s")

    def send(self, line: str) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()

    def recv(self) -> str:
        assert self._process.stdout is not None
        line = self._process.stdout.readline()
        if not line:
            stderr = self._process.stderr.read() if self._process.stderr else ""
            raise BrainError(-1, f"skin process died. stderr: {stderr}")
        return line

    def close(self) -> None:
        proc = self._process
        try:
            if proc.stdin:
                proc.stdin.close()  # EOF ends the server's eachline(stdin) loop
        except (BrokenPipeError, OSError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.info("skin did not exit on EOF; SIGTERM")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning("skin ignored SIGTERM; SIGKILL")
                proc.kill()
                proc.wait(timeout=2)


class Brain:
    """The §11 protocol surface over an injected transport.

    Use as a context manager: ``with Brain.spawn() as b: ...`` — exit sends the
    ``shutdown`` RPC and closes the transport (bounded)."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._request_id = 0

    @classmethod
    def spawn(cls, *, julia: str = "julia", repo: Path = CREDENCE_REPO,
              startup_timeout: float = STARTUP_TIMEOUT) -> Brain:
        """Spawn the real Julia skin: ``julia --project=REPO REPO/apps/skin/server.jl``."""
        argv = [julia, f"--project={repo}", str(repo / "apps" / "skin" / "server.jl")]
        return cls(SubprocessTransport(argv, startup_timeout=startup_timeout))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        self._transport.send(json.dumps({
            "jsonrpc": "2.0", "id": self._request_id,
            "method": method, "params": params or {},
        }))
        response = json.loads(self._transport.recv())
        if "error" in response:
            err = response["error"]
            raise BrainError(err["code"], err["message"])
        return response["result"]

    # --- lifecycle ---

    def initialize(self, *, dsl_files: dict[str, Path] | None = None,
                   plugins: list[Path] | None = None) -> dict[str, Any]:
        """Load the Credence module (and optionally DSL programs / plugins). Once,
        after spawn, before anything else."""
        params: dict[str, Any] = {}
        if dsl_files:
            params["dsl_files"] = {k: str(Path(v).resolve()) for k, v in dsl_files.items()}
        if plugins:
            params["plugins"] = [str(Path(p).resolve()) for p in plugins]
        result: dict[str, Any] = self._call("initialize", params)
        return result

    def shutdown(self) -> None:
        """Graceful shutdown RPC, then the transport's bounded close. Idempotent enough
        for __exit__: a dead pipe is not an error on the way out."""
        with contextlib.suppress(BrainError, BrokenPipeError, OSError):
            self._call("shutdown")
        self._transport.close()

    # --- state ---

    def create_state(self, spec: dict[str, Any]) -> str:
        """Create a measure from a protocol measure spec (beta/dirichlet/categorical/
        product/mixture — protocol.md 'Measure specs'). Returns the opaque state id."""
        result = self._call("create_state", spec)
        return str(result["state_id"])

    def destroy_state(self, state_id: str) -> None:
        self._call("destroy_state", {"state_id": state_id})

    # --- inference (the §11 mapping: condition / expect / optimise) ---

    def condition(self, state_id: str, *, kernel: dict[str, Any],
                  observation: float | int | str) -> float:
        """Bayesian inversion in place — the only learning mechanism. Returns the
        log marginal likelihood of the observation."""
        result = self._call("condition", {
            "state_id": state_id, "kernel": kernel, "observation": observation})
        return float(result["log_marginal"])

    def weights(self, state_id: str) -> list[float]:
        result = self._call("weights", {"state_id": state_id})
        return [float(w) for w in result["weights"]]

    def mean(self, state_id: str) -> float:
        result = self._call("mean", {"state_id": state_id})
        return float(result["mean"])

    def expect(self, state_id: str, *, function: dict[str, Any]) -> float:
        """Expectation of a function spec (protocol.md 'Function specs') under the
        measure."""
        result = self._call("expect", {"state_id": state_id, "function": function})
        return float(result["value"])

    def optimise(self, state_id: str, *, actions: dict[str, Any],
                 preference: dict[str, Any]) -> tuple[Any, float]:
        """The EU-maximising action and its expected utility — M4's decision rule."""
        result = self._call("optimise", {
            "state_id": state_id, "actions": actions, "preference": preference})
        return result["action"], float(result["eu"])

    def value(self, state_id: str, *, actions: dict[str, Any],
              preference: dict[str, Any]) -> float:
        """Maximum expected utility without the action — the VOI building block
        (VOI = value(informed) - value(uninformed), composed at the call site)."""
        result = self._call("value", {
            "state_id": state_id, "actions": actions, "preference": preference})
        return float(result["value"])
