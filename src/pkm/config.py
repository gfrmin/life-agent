"""Configuration loading from ``config.yaml`` (SPEC §9, §14.6).

This module exposes exactly two things:

  - ``Config``: a frozen dataclass of the settings in use for one
    CLI invocation.
  - ``load_config(path)``: reads the YAML file, validates the
    shape, and returns a ``Config``.

Only ``root_dir`` is parsed at this step — the CLI needs it to
locate the catalogue and the cache. Later steps add producer
versions and their per-producer config dicts (required by SPEC
§14.5 exact-version matching) and the log-level key. Keeping
``Config`` narrow means the CLI skeleton depends on one field and
not on fields that do not yet exist.

No environment-variable overrides are supported. SPEC §14.6
prohibits hidden state; the single YAML file is the sole source
of configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when ``config.yaml`` is missing, unreadable, or the
    contents do not satisfy the minimum expected shape.
    """


@dataclass(frozen=True)
class ExtractorConfig:
    """The ``config.yaml`` ``extractors.<name>`` subtree (SPEC §9).

    ``version`` is the exact installed tool version pkm expects; a
    mismatch at producer construction time raises
    ``ProducerVersionMismatchError`` and halts extraction. ``config``
    is the producer-internal parameter dict (e.g. ``{"ocr": True,
    "table_structure": True}`` for docling); the producer's own
    constructor validates its shape. Both fields participate in the
    cache key via ``compute_cache_key`` (SPEC §4.2).
    """

    version: str
    config: dict[str, Any]


@dataclass(frozen=True)
class Config:
    """The settings the Phase 1 CLI needs to function.

    ``extractors`` is populated only when config.yaml supplies it.
    Commands that don't need extractors (``pkm migrate``,
    ``pkm rebuild-catalogue``, ``pkm ingest``) accept an empty dict;
    ``pkm extract`` raises when a producer it would call is missing
    from the dict.
    """

    root_dir: Path
    """Absolute, user-expanded knowledge root (SPEC §3)."""

    source: Path
    """The config file this was loaded from. Useful for error
    messages and for log events; not part of the data itself.
    """

    extractors: dict[str, ExtractorConfig] = field(default_factory=dict)
    """Extractor configs keyed by producer name. Empty if the
    config.yaml ``extractors`` section is absent."""

    policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Policy configs keyed by policy name (SPEC v0.2.0 §22.2).
    Empty if the config.yaml ``policies`` section is absent."""


def load_config(path: Path) -> Config:
    """Load and validate ``config.yaml`` at ``path``.

    Args:
        path: Path to the config file. Not expanded — callers
            should expand ``~`` themselves if needed.

    Returns:
        A ``Config`` with ``root_dir`` resolved to an absolute
        path (``~`` expansion + ``.resolve()``).

    Raises:
        ConfigError: file does not exist, is not valid YAML, is
            not a mapping at the top level, or does not contain
            a string ``root_dir`` field.
    """
    if not path.exists():
        raise ConfigError(
            f"config file not found at {path}. create it with at "
            f"minimum `root_dir: <path>` or pass --config to override."
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"config at {path} is not valid YAML: {e}") from e

    if raw is None:
        raise ConfigError(f"config at {path} is empty")
    if not isinstance(raw, dict):
        raise ConfigError(
            f"config at {path} must be a YAML mapping, got "
            f"{type(raw).__name__}"
        )

    root_dir_raw = raw.get("root_dir")
    if not isinstance(root_dir_raw, str):
        raise ConfigError(
            f"config at {path} must contain a string `root_dir` field; "
            f"got {type(root_dir_raw).__name__}"
        )

    root_dir = Path(root_dir_raw).expanduser().resolve()

    extractors = _parse_extractors(raw.get("extractors"), path)
    policies = _parse_policies(raw.get("policies"), path)

    return Config(
        root_dir=root_dir, source=path,
        extractors=extractors, policies=policies,
    )


def _parse_extractors(
    raw: Any, config_path: Path
) -> dict[str, ExtractorConfig]:
    """Parse the ``extractors`` section of ``config.yaml``, validating
    strictly. Missing section → empty dict (callers decide whether
    that's an error). Malformed shape → ``ConfigError`` with a
    message naming the offending key.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(
            f"config at {config_path}: `extractors` must be a mapping, "
            f"got {type(raw).__name__}"
        )

    result: dict[str, ExtractorConfig] = {}
    for name, spec in raw.items():
        if not isinstance(name, str):
            raise ConfigError(
                f"config at {config_path}: extractor name must be a "
                f"string, got {type(name).__name__}"
            )
        if not isinstance(spec, dict):
            raise ConfigError(
                f"config at {config_path}: extractors.{name} must be a "
                f"mapping, got {type(spec).__name__}"
            )
        version = spec.get("version")
        if not isinstance(version, str):
            raise ConfigError(
                f"config at {config_path}: extractors.{name}.version "
                f"must be a string, got {type(version).__name__}"
            )
        inner = spec.get("config", {})
        if not isinstance(inner, dict):
            raise ConfigError(
                f"config at {config_path}: extractors.{name}.config "
                f"must be a mapping, got {type(inner).__name__}"
            )
        result[name] = ExtractorConfig(version=version, config=inner)
    return result


def _parse_policies(
    raw: Any, config_path: Path,
) -> dict[str, dict[str, Any]]:
    """Parse the ``policies`` section of ``config.yaml``.

    Missing section -> empty dict.  Each policy value must be a mapping
    of configuration keys for that policy.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(
            f"config at {config_path}: `policies` must be a mapping, "
            f"got {type(raw).__name__}"
        )

    result: dict[str, dict[str, Any]] = {}
    for name, spec in raw.items():
        if not isinstance(name, str):
            raise ConfigError(
                f"config at {config_path}: policy name must be a "
                f"string, got {type(name).__name__}"
            )
        if not isinstance(spec, dict):
            raise ConfigError(
                f"config at {config_path}: policies.{name} must be a "
                f"mapping, got {type(spec).__name__}"
            )
        result[name] = spec
    return result
