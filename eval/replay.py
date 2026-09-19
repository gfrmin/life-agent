"""Read recorded decision fixtures: the pins a port is held to.

A checkpoint directory (``$LIFE_AGENT_KB/eval/collapse-fixtures/<checkpoint>/``) holds one
JSON file per recorded question plus ``manifest.json``. Each fixture carries the wire it saw:
every request/response at a tapped seam. Fixtures carry question text and corpus-derived
values, so they live under the KB and never enter this repository.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Exchange:
    """One recorded request/response. ``seam`` is ``skin``, ``http``, ``instrument`` or
    ``cache``."""

    seam: str
    request: dict[str, Any]
    response: Any


@dataclass(frozen=True)
class Fixture:
    """One recorded question: its inputs, its outputs and the wire in between."""

    fixture_id: str
    checkpoint: str
    trace: str
    classes: tuple[str, ...]
    question: str
    question_id: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    wire: tuple[Exchange, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    expected_change: dict[str, Any] | None = None
    format_version: int = 1


def from_json(text: str) -> Fixture:
    obj = json.loads(text)
    obj["classes"] = tuple(obj.get("classes", ()))
    obj["wire"] = tuple(Exchange(**e) for e in obj.get("wire", ()))
    return Fixture(**obj)


def read_all(directory: Path) -> list[Fixture]:
    """Every fixture in the directory, in id order. A malformed one raises: a replay that
    skips a fixture is not a pin."""
    return [from_json(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.json")) if p.name != "manifest.json"]


def http_exchanges(fixtures: list[Fixture], path: str
                   ) -> Iterator[tuple[str, dict[str, Any], Any]]:
    """``(fixture_id, payload, response)`` for every recorded HTTP call to ``path``."""
    for fx in fixtures:
        for ex in fx.wire:
            url = str(ex.request.get("url") or ex.request.get("path") or "")
            if ex.seam == "http" and url.split("?")[0].endswith(path):
                yield fx.fixture_id, ex.request["payload"], ex.response
