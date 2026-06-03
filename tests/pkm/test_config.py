"""Tests for ``pkm.config`` — YAML loading of the minimum shape
needed by the Phase 1 CLI (SPEC §9, §14.6).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.config import Config, ConfigError, load_config


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_load_config_parses_root_dir(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    root = tmp_path / "knowledge"
    _write(cfg_path, f"root_dir: {root}\n")
    cfg = load_config(cfg_path)
    assert isinstance(cfg, Config)
    assert cfg.root_dir == root.resolve()
    assert cfg.source == cfg_path


def test_load_config_expands_tilde(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "root_dir: ~/.local/share/pkm\n")
    cfg = load_config(cfg_path)
    assert cfg.root_dir.is_absolute()
    assert "~" not in str(cfg.root_dir)


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_config(tmp_path / "does_not_exist.yaml")
    assert "not found" in str(excinfo.value)
    assert "root_dir" in str(excinfo.value)


def test_load_config_empty_file_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "")
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "empty" in str(excinfo.value)


def test_load_config_non_mapping_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "- just\n- a list\n")
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "mapping" in str(excinfo.value)


def test_load_config_missing_root_dir_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "log_level: INFO\n")
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "root_dir" in str(excinfo.value)


def test_load_config_non_string_root_dir_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "root_dir: 42\n")
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "root_dir" in str(excinfo.value)


def test_load_config_invalid_yaml_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, "root_dir: [unclosed\n")
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "YAML" in str(excinfo.value)


# --- policies section ---------------------------------------------------


def test_load_config_without_policies_has_empty_dict(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, f"root_dir: {tmp_path}\n")
    cfg = load_config(cfg_path)
    assert cfg.policies == {}


def test_load_config_parses_policies(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(
        cfg_path,
        f"root_dir: {tmp_path}\n"
        "policies:\n"
        "  cost_gate:\n"
        "    budget_per_invocation_usd: 5.00\n"
        "    budget_per_day_usd: 50.00\n"
        "  sensitive_doc_gate:\n"
        "    tags: [sensitive, medical]\n",
    )
    cfg = load_config(cfg_path)
    assert "cost_gate" in cfg.policies
    assert cfg.policies["cost_gate"]["budget_per_invocation_usd"] == 5.00
    assert "sensitive_doc_gate" in cfg.policies
    assert cfg.policies["sensitive_doc_gate"]["tags"] == [
        "sensitive", "medical",
    ]


def test_load_config_policies_non_mapping_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(
        cfg_path,
        f"root_dir: {tmp_path}\n"
        "policies: not_a_mapping\n",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "policies" in str(excinfo.value)


def test_load_config_policy_value_non_mapping_raises(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "config.yaml"
    _write(
        cfg_path,
        f"root_dir: {tmp_path}\n"
        "policies:\n"
        "  cost_gate: just_a_string\n",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_config(cfg_path)
    assert "cost_gate" in str(excinfo.value)
