"""extract(payload, context_date) -> JSON-LD. The only edge that touches the binary.

Follows the pkm/producers/tesseract.py precedent: a system binary wrapped as a producer,
subprocess-called, never raising — any failure returns []. Deterministic: same bytes +
same context_date -> same JSON-LD, with barcode verification underneath. context_date is
mandatory: kitinerary uses it to resolve partial dates ('12 Aug') to a real year, and a
wrong one is the single most common source of garbage output.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Any

from life_agent.core.config import KITINERARY_EXTRACTOR

BINARY: str = KITINERARY_EXTRACTOR
_TIMEOUT_SECONDS = 60


def extract(payload: bytes, context_date: datetime) -> list[dict[str, Any]]:
    """Run the extractor over raw bytes (an email, a PDF, or raw JSON-LD to enrich).

    Returns the parsed JSON-LD reservation list, or [] on any failure. Never raises."""
    try:
        completed = subprocess.run(
            [BINARY, "-o", "JsonLd", "--context-date", context_date.isoformat()],
            input=payload,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    try:
        parsed = json.loads(completed.stdout or b"[]")
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [o for o in parsed if isinstance(o, dict)]
