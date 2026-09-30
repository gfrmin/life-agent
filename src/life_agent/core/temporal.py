"""Temporal projection over retrieval hits (design doc §5/§11 D1).

Read-only by construction: the ask path holds a read-only catalogue connection
(pkm SPEC §18.9), so this module PROJECTS current doc_date artifacts (SPEC
§18.12) over hits via ``artifact_lineage`` and never derives; hits without a
projection are indeterminate.

Demand is logged per hit (pkm SPEC §18.11, filesystem-only — no catalogue
lock): ``hit=False`` lines are the unmet-demand signal the VOI layer will
calibrate on.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import duckdb

from pkm.cache import content_file
from pkm.telemetry import DemandLogEntry, log_demand

DOC_DATE_PRODUCERS = ("doc_date_email", "doc_date")


@dataclass(frozen=True)
class DatedHit:
    """One retrieval hit's temporal projection."""

    artifact_cache_key: str
    state: Literal["dated", "undated", "underived"]
    date: date | None            # set iff state == "dated"
    extractor: str               # the hit artifact's producer_name


def project_dates(
    conn: duckdb.DuckDBPyConnection,
    root: Path,
    hit_keys: list[str],
    *,
    caller: str = "ask.temporal",
) -> list[DatedHit]:
    """Project the CURRENT doc_date artifact onto each hit, read-only.

    Currency is the §18.10 ordering — max ``(produced_at, cache_key)`` per
    hit over successful doc_date artifacts whose lineage names the hit as
    input. Logs one demand line per hit (§18.11).
    """
    if not hit_keys:
        return []

    placeholders = ", ".join("?" for _ in hit_keys)
    extractor_of = dict(conn.execute(
        f"SELECT cache_key, producer_name FROM artifacts "
        f"WHERE cache_key IN ({placeholders})",
        hit_keys,
    ).fetchall())

    rows = conn.execute(
        f"SELECT l.input_cache_key, a.cache_key, a.produced_at "
        f"FROM artifact_lineage l "
        f"JOIN artifacts a ON a.cache_key = l.artifact_cache_key "
        f"WHERE l.input_cache_key IN ({placeholders}) "
        f"AND a.producer_name IN (?, ?) AND a.status = 'success'",
        [*hit_keys, *DOC_DATE_PRODUCERS],
    ).fetchall()

    # Current projection per hit: max (produced_at, cache_key) — §18.10.
    current: dict[str, tuple[object, str]] = {}
    for input_key, proj_key, produced_at in rows:
        candidate = (produced_at, proj_key)
        if input_key not in current or candidate > current[input_key]:
            current[input_key] = candidate

    hits: list[DatedHit] = []
    for key in hit_keys:
        t0 = time.monotonic()  # per-hit, so latency_ms is not cumulative
        extractor = str(extractor_of.get(key, ""))
        projection = current.get(key)
        if projection is None:
            hits.append(DatedHit(key, "underived", None, extractor))
            _demand(root, caller, key, "", hit=False, t0=t0)
            continue
        proj_key = projection[1]
        parsed = json.loads(
            content_file(root, proj_key).read_text(encoding="utf-8")
        )
        raw = parsed.get("date")
        if raw is None:
            hits.append(DatedHit(key, "undated", None, extractor))
        else:
            hits.append(DatedHit(key, "dated", date.fromisoformat(raw),
                                 extractor))
        _demand(root, caller, key, proj_key, hit=True, t0=t0)
    return hits


def _demand(root: Path, caller: str, input_key: str, projection_key: str,
            *, hit: bool, t0: float) -> None:
    """One §18.11 demand line. ``cache_key`` is the projection's key on a
    hit and ``""`` on a read-side miss (the node key is declaration-dependent
    and unresolvable without one; the input key carries the signal)."""
    log_demand(root, DemandLogEntry(
        timestamp=datetime.now(UTC).isoformat(),
        caller=caller,
        transform_name="doc_date",
        cache_key=projection_key,
        input_cache_key=input_key,
        hit=hit,
        cost_usd=0.0,
        latency_ms=int((time.monotonic() - t0) * 1000),
    ))
