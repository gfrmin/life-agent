"""Demand telemetry (SPEC §18.11) — one JSONL line per node resolution."""

from __future__ import annotations

import json
from pathlib import Path

from pkm.telemetry import DemandLogEntry, log_demand


def _entry(**overrides: object) -> DemandLogEntry:
    base: dict[str, object] = {
        "timestamp": "2026-06-10T12:00:00+00:00",
        "caller": "cli",
        "transform_name": "t_upper",
        "cache_key": "ab" * 32,
        "input_cache_key": "cd" * 32,
        "hit": True,
        "cost_usd": 0.0,
        "latency_ms": 3,
    }
    base.update(overrides)
    return DemandLogEntry(**base)  # type: ignore[arg-type]


def test_log_demand_appends_one_jsonl_line(tmp_root: Path) -> None:
    log_demand(tmp_root, _entry())
    log_demand(tmp_root, _entry(hit=False, cost_usd=0.01))

    files = list((tmp_root / "logs" / "demand").iterdir())
    assert len(files) == 1
    lines = [json.loads(line) for line in files[0].read_text("utf-8").splitlines()]
    assert [e["hit"] for e in lines] == [True, False]
    assert lines[0]["cache_key"] == "ab" * 32  # full hash, never truncated
    assert lines[1]["cost_usd"] == 0.01
    assert set(lines[0]) == {
        "timestamp", "caller", "transform_name", "cache_key",
        "input_cache_key", "hit", "cost_usd", "latency_ms",
    }
