"""Tests for ``pkm.telemetry`` — transform execution logging."""

from __future__ import annotations

import json
from pathlib import Path

from pkm.telemetry import TransformLogEntry, log_transform_execution


def _entry(**overrides: object) -> TransformLogEntry:
    defaults = {
        "timestamp": "2026-04-26T12:00:00Z",
        "transform_name": "entity_extraction",
        "transform_version": "0.1.0",
        "cache_key": "a" * 64,
        "input_cache_key": "b" * 64,
        "model": "claude-haiku-4-5",
        "prompt_name": "entity_v1",
        "status": "success",
        "error_message": "",
        "input_tokens": 100,
        "output_tokens": 50,
        "latency_ms": 250,
        "cost_usd": 0.001,
        "cache_hit": False,
    }
    defaults.update(overrides)
    return TransformLogEntry(**defaults)  # type: ignore[arg-type]


def test_log_creates_daily_jsonl(tmp_path: Path) -> None:
    log_transform_execution(tmp_path, _entry())

    log_dir = tmp_path / "logs" / "transforms"
    assert log_dir.exists()
    files = list(log_dir.glob("*.jsonl"))
    assert len(files) == 1

    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["transform_name"] == "entity_extraction"
    assert record["status"] == "success"
    assert record["cache_hit"] is False


def test_log_appends_multiple_entries(tmp_path: Path) -> None:
    log_transform_execution(tmp_path, _entry(status="success"))
    log_transform_execution(tmp_path, _entry(status="failed"))

    files = list((tmp_path / "logs" / "transforms").glob("*.jsonl"))
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "success"
    assert json.loads(lines[1])["status"] == "failed"


def test_log_is_valid_jsonl(tmp_path: Path) -> None:
    for i in range(5):
        log_transform_execution(
            tmp_path,
            _entry(input_tokens=i * 10),
        )

    files = list((tmp_path / "logs" / "transforms").glob("*.jsonl"))
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    for line in lines:
        json.loads(line)
