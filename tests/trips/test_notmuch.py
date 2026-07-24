"""The mailbox selection seam: a subprocess wrapper over the notmuch binary. Unlike extract,
it RAISES on failure — a broken index must never be a silent empty ingest. Fully hermetic:
subprocess is monkeypatched, the real binary is never invoked."""
from __future__ import annotations

import pytest

from life_agent.trips import notmuch as nm


class _Completed:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_run(result=None, exc=None):
    def run(args, **kwargs):
        if exc is not None:
            raise exc
        return result
    return run


def test_search_parses_and_strips_id_prefix(monkeypatch) -> None:
    out = b"id:aaa@x\nid:bbb@y\n"
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, out)))
    assert nm.search("folder:Trips") == ["aaa@x", "bbb@y"]


def test_search_empty_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"")))
    assert nm.search("folder:Trips") == []


def test_show_raw_returns_bytes(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"From: a\r\n\r\nhi")))
    assert nm.show_raw("aaa@x") == b"From: a\r\n\r\nhi"


def test_missing_binary_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(exc=FileNotFoundError()))
    with pytest.raises(nm.NotmuchError):
        nm.search("folder:Trips")


def test_nonzero_exit_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(1, b"", b"bad query")))
    with pytest.raises(nm.NotmuchError):
        nm.search("(((")


def test_show_raw_empty_body_raises(monkeypatch) -> None:
    monkeypatch.setattr(nm.subprocess, "run", _fake_run(_Completed(0, b"")))
    with pytest.raises(nm.NotmuchError):
        nm.show_raw("missing@x")
