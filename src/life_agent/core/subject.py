"""Subject projection over retrieval hits (design doc §5/§11 D2).

Read-only over the catalogue by construction: this module PROJECTS current
doc_subject artifacts (pkm SPEC §18.13) over hits via ``artifact_lineage``
and never derives them. The owner match is consumer-side policy — the
profile never enters pkm (PRINCIPLES §12): a grammar-constrained local-model
two-class-plus-unclear classification of (projected subject, profile),
cached file-first through the §18.9 derivations seam so each distinct
subject string is judged once per profile version; the per-question filter
is then a deterministic fold over cached verdicts (the §18.8 decomposition).

Demand is logged per hit (pkm SPEC §18.11): ``hit=False`` lines are
the unmet-demand signal the VOI layer will calibrate on.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb

from life_agent.core import derivations as D
from life_agent.core.instrument import INSTRUMENT_MODEL, instrument_client
from pkm.cache import content_file
from pkm.telemetry import DemandLogEntry, log_demand

SUBJECT_PRODUCER = "doc_subject"

# The subject-vs-profile instrument model (local Ollama deprecated 2026-08-17 —
# owner directive, §14-registered). The verdict is cached, so the call count is
# bounded by distinct subjects, not by questions. PRINCIPLES §12: local/cloud is
# engineering, not privacy — the synthesize stage already sends the profile to the
# same provider.
OWNER_MATCH_MODEL = INSTRUMENT_MODEL

OWNER_MATCH_PROMPT = """\
You are matching a document subject against the owner profile below.

OWNER PROFILE (authoritative — including any names it says are NOT the owner):
{profile}

DOCUMENT SUBJECT (a name copied from a document, in its original language):
{subject}

Is this subject the owner? Consider name variants, transliterations, and
aliases the profile names. Reply with JSON only:
{{"verdict": "owner"}} if it is the owner,
{{"verdict": "not_owner"}} if it is determinately someone or something else,
{{"verdict": "unclear"}} if the profile cannot settle it.
"""

VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdict"],
    "properties": {
        "verdict": {"type": "string", "enum": ["owner", "not_owner", "unclear"]},
    },
}

Verdict = Literal["owner", "not_owner", "unclear"]


@dataclass(frozen=True)
class SubjectedHit:
    """One retrieval hit's subject projection."""

    artifact_cache_key: str
    state: Literal["named", "generic", "underived"]
    subject_kind: str | None     # "person" | "organisation", set iff named
    subject: str | None          # the name as written, set iff named
    extractor: str               # the hit artifact's producer_name


def project_subjects(
    conn: duckdb.DuckDBPyConnection,
    root: Path,
    hit_keys: list[str],
    *,
    caller: str = "ask.subject",
) -> list[SubjectedHit]:
    """Project the CURRENT doc_subject artifact onto each hit, read-only.

    Currency is the §18.10 ordering — max ``(produced_at, cache_key)`` per
    hit over successful doc_subject artifacts whose lineage names the hit as
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
        f"AND a.producer_name = ? AND a.status = 'success'",
        [*hit_keys, SUBJECT_PRODUCER],
    ).fetchall()

    # Current projection per hit: max (produced_at, cache_key) — §18.10.
    current: dict[str, tuple[object, str]] = {}
    for input_key, proj_key, produced_at in rows:
        candidate = (produced_at, proj_key)
        if input_key not in current or candidate > current[input_key]:
            current[input_key] = candidate

    hits: list[SubjectedHit] = []
    for key in hit_keys:
        t0 = time.monotonic()  # per-hit, so latency_ms is not cumulative
        extractor = str(extractor_of.get(key, ""))
        projection = current.get(key)
        if projection is None:
            hits.append(SubjectedHit(key, "underived", None, None, extractor))
            _demand(root, caller, key, "", hit=False, t0=t0)
            continue
        proj_key = projection[1]
        parsed = json.loads(
            content_file(root, proj_key).read_text(encoding="utf-8")
        )
        kind = parsed.get("subject_kind")
        if kind == "generic":
            hits.append(SubjectedHit(key, "generic", None, None, extractor))
        else:
            hits.append(SubjectedHit(key, "named", kind,
                                     parsed.get("subject"), extractor))
        _demand(root, caller, key, proj_key, hit=True, t0=t0)
    return hits


def owner_verdict(
    root: Path,
    subject: str,
    profile: str,
    *,
    client: Any | None = None,
    meter: list[float] | None = None,
) -> Verdict:
    """Judge one subject string against the profile — cached, loud.

    A replayed verdict makes the filter deterministic per (subject, profile);
    only a cache miss calls the model. A verdict outside the enum raises and
    is NEVER recorded (§18.11 miss-path parity: junk must not be frozen)."""
    profile_hash = hashlib.sha256(profile.encode("utf-8")).hexdigest()
    if client is None:
        client = instrument_client(OWNER_MATCH_MODEL)
    key = D.owner_match_key(
        subject, profile_hash, model=OWNER_MATCH_MODEL,
        prompt_template=OWNER_MATCH_PROMPT,
        engine_version=str(client.engine_version),
        output_schema=VERDICT_SCHEMA,
    )
    cached = D.lookup(root, key.cache_key)
    if cached is not None:
        return _as_verdict(json.loads(cached.decode("utf-8"))["verdict"])

    prompt = OWNER_MATCH_PROMPT.replace("{profile}", profile).replace(
        "{subject}", subject)
    response = client.complete(prompt, VERDICT_SCHEMA)
    if meter is not None:
        meter.append(float(getattr(response, "cost_usd", 0.0) or 0.0))
    verdict = _as_verdict(json.loads(response.raw_text).get("verdict"))
    D.record(
        root, key,
        json.dumps({"format_version": 1, "verdict": verdict},
                   sort_keys=True, ensure_ascii=False).encode("utf-8"),
        lineage=[],
    )
    return verdict


def _as_verdict(value: object) -> Verdict:
    if value not in ("owner", "not_owner", "unclear"):
        raise ValueError(
            f"owner_match emitted a verdict outside the enum: {value!r}"
        )
    return value


def _demand(root: Path, caller: str, input_key: str, projection_key: str,
            *, hit: bool, t0: float) -> None:
    """One §18.11 demand line. ``cache_key`` is the projection's key on a
    hit and ``""`` on a read-side miss (the node key is declaration-dependent
    and unresolvable without one; the input key carries the signal)."""
    log_demand(root, DemandLogEntry(
        timestamp=datetime.now(UTC).isoformat(),
        caller=caller,
        transform_name=SUBJECT_PRODUCER,
        cache_key=projection_key,
        input_cache_key=input_key,
        hit=hit,
        cost_usd=0.0,
        latency_ms=int((time.monotonic() - t0) * 1000),
    ))
