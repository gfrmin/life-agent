"""Transform execution telemetry (SPEC v0.2.0 §23.1).

Appends one JSONL line per transform execution to
``<root>/logs/transforms/<YYYY-MM-DD>.jsonl``.  The log is
append-only and human-readable (inspectable with ``jq``).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class TransformLogEntry:
    """One line in the transform execution log (§23.1)."""

    timestamp: str
    transform_name: str
    transform_version: str
    cache_key: str
    input_cache_key: str
    model: str
    prompt_name: str
    status: Literal["success", "failed"]
    error_message: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    cache_hit: bool


def log_transform_execution(
    root: Path, entry: TransformLogEntry,
) -> None:
    """Append a transform execution record to the daily JSONL log."""
    log_dir = root / "logs" / "transforms"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = log_dir / f"{date_str}.jsonl"

    line = json.dumps(asdict(entry), sort_keys=True, ensure_ascii=False)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
