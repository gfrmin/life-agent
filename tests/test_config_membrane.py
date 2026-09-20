"""The decider engine's launch argv (config.membrane_command)."""
from __future__ import annotations

from pathlib import Path

import pytest

from life_agent.core import config


@pytest.fixture(autouse=True)
def _no_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(config.MEMBRANE_COMMAND_ENV, raising=False)
    monkeypatch.setenv(config.ENGINE_BIN_ENV, str(tmp_path / "absent" / "proplang-host"))


def test_no_command_and_no_install_is_none() -> None:
    assert config.membrane_command() is None


def test_the_command_env_is_shell_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "/opt/host --flag value")
    assert config.membrane_command() == ["/opt/host", "--flag", "value"]


def test_an_empty_command_falls_through_to_the_install(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    binary = tmp_path / "proplang-host"
    binary.write_text("")
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "")
    monkeypatch.setenv(config.ENGINE_BIN_ENV, str(binary))
    assert config.membrane_command() == [str(binary)]


def test_the_command_env_wins_over_the_install(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    binary = tmp_path / "proplang-host"
    binary.write_text("")
    monkeypatch.setenv(config.ENGINE_BIN_ENV, str(binary))
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "/opt/host")
    assert config.membrane_command() == ["/opt/host"]


def test_read_timeout_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_READ_TIMEOUT_ENV, raising=False)
    assert config.membrane_read_timeout_s() == 300.0
    monkeypatch.setenv(config.MEMBRANE_READ_TIMEOUT_ENV, "45")
    assert config.membrane_read_timeout_s() == 45.0
