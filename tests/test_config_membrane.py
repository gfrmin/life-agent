"""Hermetic tests for the membrane shadow's config surface (Task 5).

life_agent.core.config's membrane_* helpers are FUNCTIONS (not precomputed constants,
unlike the file's other KB-derived paths) so they read the live env / config.KB at call
time — no importlib.reload needed to observe a monkeypatched value, matching
tests/test_gather.py's `monkeypatch.setattr(config, "...", ...)` idiom for the KB-relative
paths and a plain `monkeypatch.setenv` for the four env-driven scalars.
"""
from __future__ import annotations

from pathlib import Path

from life_agent.core import config

# --- membrane_dir / membrane_shadow_log: respect config.KB (itself $LIFE_AGENT_KB) -------

def test_membrane_dir_is_under_kb(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "KB", tmp_path)
    assert config.membrane_dir() == tmp_path / "membrane"


def test_membrane_shadow_log_is_under_membrane_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "KB", tmp_path)
    assert config.membrane_shadow_log() == tmp_path / "membrane" / "shadow.jsonl"


# --- membrane_command: the enable/disable switch ------------------------------------------

def test_membrane_command_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_COMMAND_ENV, raising=False)
    assert config.membrane_command() is None


def test_membrane_command_shell_splits_the_argv(monkeypatch) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "/opt/govhost --flag value")
    assert config.membrane_command() == ["/opt/govhost", "--flag", "value"]


def test_membrane_command_empty_string_is_none(monkeypatch) -> None:
    monkeypatch.setenv(config.MEMBRANE_COMMAND_ENV, "")
    assert config.membrane_command() is None


# --- membrane_utility_forms: comma list, default table@1 ----------------------------------

def test_membrane_utility_forms_default(monkeypatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_UTILITY_ENV, raising=False)
    assert config.membrane_utility_forms() == ("table@1",)


def test_membrane_utility_forms_comma_list_is_stripped(monkeypatch) -> None:
    monkeypatch.setenv(config.MEMBRANE_UTILITY_ENV, "table@1, latent@1")
    assert config.membrane_utility_forms() == ("table@1", "latent@1")


# --- membrane_read_timeout_s: default 300.0 ------------------------------------------------

def test_membrane_read_timeout_default(monkeypatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_READ_TIMEOUT_ENV, raising=False)
    assert config.membrane_read_timeout_s() == 300.0


def test_membrane_read_timeout_custom(monkeypatch) -> None:
    monkeypatch.setenv(config.MEMBRANE_READ_TIMEOUT_ENV, "45")
    assert config.membrane_read_timeout_s() == 45.0


# --- membrane_warm_vectors_dir: optional path ----------------------------------------------

def test_membrane_warm_vectors_dir_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv(config.MEMBRANE_WARM_VECTORS_ENV, raising=False)
    assert config.membrane_warm_vectors_dir() is None


def test_membrane_warm_vectors_dir_set(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "fairfight-run-1"
    monkeypatch.setenv(config.MEMBRANE_WARM_VECTORS_ENV, str(run_dir))
    assert config.membrane_warm_vectors_dir() == run_dir
