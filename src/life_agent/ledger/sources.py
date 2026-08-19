"""Legacy stores → stream records: one pure parser per migrating source (design §2, §8 C0-C2).

``scan(source_id, paths)`` reads a legacy store **read-only** and returns every record it
holds in the source's canonical order (§2: file order for JSONL; ``(produced_at, cache_key)``
for ``pkm.artifact``; UTC-day file then line for ``pkm.demand``), each already carrying its
envelope annotations (``author``, ``kernel_id``, ``inputs``, ``output``, ``recorded_draw``, the
derived UTC ``tx_time`` or ``None`` — the §2 table), plus the counts the migration manifest
records: **unparseable** lines (not events), **duplicate-key** JSON lines (not events —
``json.loads`` would silently keep the last value and canonical re-serialisation would launder
the loss; reviewer Q8) and blank lines. Nothing here writes; nothing here imports the segment
store. Locators are ``<file>:<line>`` or a cache key — never a record value.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from life_agent.core import claude_verdicts as CV
from life_agent.core import decisions as DEC
from life_agent.core import outcomes as O
from life_agent.core import reactions as RX
from life_agent.ledger.paths import Paths
from life_agent.ledger.schema import SOURCE_IDS, canonical
from life_agent.tasks import events as TEV
from life_agent.trips import events as REV
from pkm.hashing import compute_model_identity_hash
from pkm.rebuild import _iter_meta_files

# The design's §8 C2 migration order — `act.tasks` first, `pkm.artifact` last.
MIGRATION_ORDER: tuple[str, ...] = (
    "act.tasks", "act.trips", "calibration.decisions", "calibration.reactions",
    "calibration.claude_verdicts", "calibration.outcomes", "calibration.gather_outcomes",
    "calibration.corrections", "utility.elicitations", "eval.labels", "pkm.demand",
    "pkm.artifact",
)
assert set(MIGRATION_ORDER) == SOURCE_IDS

# Per-source clock (r00 a.4; design §2): how `tx_time` is derived from the verbatim stamp.
CLOCKS: dict[str, str] = {
    "act.tasks": "naive-local", "act.trips": "naive-local",
    "calibration.outcomes": "aware", "calibration.decisions": "aware",
    "calibration.reactions": "aware", "calibration.claude_verdicts": "aware",
    "calibration.gather_outcomes": "aware", "calibration.corrections": "aware",
    "utility.elicitations": "aware", "eval.labels": "none",
    "pkm.artifact": "naive-utc", "pkm.demand": "aware",
}


@dataclass(frozen=True)
class Parsed:
    """One legacy record in canonical order, with its envelope annotations (no `seq` yet)."""

    ordinal: int                  # 1-based among the parsed records of the source
    record: dict[str, Any]
    tx_time_raw: str
    tx_time: str | None
    kernel_id: str
    author: str
    inputs: tuple[str, ...]
    output: str | None
    recorded_draw: dict[str, Any] | None
    locator: str                  # PII-safe: "<file>:<line>" or a cache key


@dataclass(frozen=True)
class Scan:
    source_id: str
    parsed: tuple[Parsed, ...]
    unparseable: int
    duplicate_key: int
    blank: int
    unparseable_locators: tuple[str, ...]
    extras: dict[str, Any] = field(default_factory=dict)   # diagnostics, counts only

    def counts(self) -> dict[str, Any]:
        return {"parsed": len(self.parsed), "unparseable": self.unparseable,
                "duplicate_key": self.duplicate_key, "blank": self.blank, **self.extras}


# --- JSON with duplicate-key detection --------------------------------------------------------

class _DuplicateKeyError(Exception):
    pass


def _no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _DuplicateKeyError
    return dict(pairs)


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str]:
    """→ (object, "ok") | (None, "duplicate_key") | (None, "unparseable")."""
    try:
        obj = json.loads(text, object_pairs_hook=_no_dup)
    except _DuplicateKeyError:
        return None, "duplicate_key"
    except (json.JSONDecodeError, RecursionError, ValueError):
        return None, "unparseable"
    if not isinstance(obj, dict):
        return None, "unparseable"
    return obj, "ok"


# --- the derived UTC annotation (R4: never hashed, never ordered on across sources) -----------

def utc_annotation(stamp: str | None, clock: str) -> str | None:
    if not stamp or clock in ("naive-local", "none"):
        return None
    try:
        dt = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    if dt.tzinfo is None:
        if clock != "naive-utc":
            return None
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _stamp_shape(stamp: Any) -> str:
    if stamp is None:
        return "none"
    s = str(stamp)
    if s.endswith("Z"):
        return "aware-Z"
    if len(s) >= 6 and s[-6] in "+-" and s[-3] == ":":
        return "aware"
    return f"naive{len(s)}"


# --- per-source envelope rules (design §2 table) ---------------------------------------------

def _hex16(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()[:16]


def _is_hex(s: Any, n: int) -> bool:
    return isinstance(s, str) and len(s) == n and all(c in "0123456789abcdef" for c in s)


def _envelope(source_id: str, rec: dict[str, Any]) -> dict[str, Any]:
    """author / kernel_id / inputs / output / recorded_draw / tx_time_raw for one record."""
    sid = source_id
    if sid == "calibration.outcomes":
        grader = str(rec.get("grader", ""))
        return {"author": "owner" if grader == "owner" else "agent",
                "kernel_id": f"grader:{grader}:sha256:{_hex16(rec.get('instrument_identity'))}",
                "inputs": tuple(str(k) for k in rec.get("lineage_keys", ()) or ()),
                "output": None, "recorded_draw": None, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "calibration.decisions":
        fam, inst = str(rec.get("family", "")), str(rec.get("instrument", "") or "")
        did = rec.get("decision_id") or None
        return {"author": "agent", "kernel_id": f"decide:{fam}" + (f":{inst}" if inst else ""),
                "inputs": (), "output": did, "recorded_draw": None,
                "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "calibration.reactions":
        return {"author": "owner", "kernel_id": "owner:verdict",
                "inputs": (str(rec.get("decision_id", "")),), "output": None,
                "recorded_draw": None, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "calibration.claude_verdicts":
        return {"author": "agent", "kernel_id": "claude-code:verdict",
                "inputs": (str(rec.get("decision_id", "")),), "output": None,
                "recorded_draw": None, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "calibration.gather_outcomes":
        return {"author": "agent", "kernel_id": f"executor:grow:{rec.get('probe', '')}",
                "inputs": (), "output": None, "recorded_draw": None,
                "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "calibration.corrections":
        return {"author": "owner", "kernel_id": "owner:correction", "inputs": (),
                "output": None, "recorded_draw": None, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "utility.elicitations":
        return {"author": "owner", "kernel_id": "owner:elicitation", "inputs": (),
                "output": None, "recorded_draw": None, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "eval.labels":
        return {"author": "owner", "kernel_id": "owner:label", "inputs": (), "output": None,
                "recorded_draw": None, "tx_time_raw": ""}       # labels carry no stamp (r00)
    if sid == "act.tasks":
        typ = str(rec.get("type", ""))
        payload = rec.get("payload") or {}
        origin = payload.get("origin") if isinstance(payload, dict) else None
        ident = str(rec.get("identity", ""))
        if typ == "asserted" and origin == "email":
            author, kernel = "agent", "tasks.project:action_items"
        elif typ == "superseded":
            author, kernel = "agent", "tasks.project:supersede"
        else:
            author, kernel = "owner", "owner:command"
        draw = {"kind": "uuid", "ref": ident} if typ == "asserted" and _is_hex(ident, 32) else None
        return {"author": author, "kernel_id": kernel, "inputs": (), "output": ident,
                "recorded_draw": draw, "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "act.trips":
        typ = str(rec.get("type", ""))
        ident = str(rec.get("identity", ""))
        src = rec.get("source_id")
        if typ == "observed":
            author, kernel = "world", f"trips.ingest:{rec.get('fidelity', '')}"
        elif typ == "superseded":
            author, kernel = "agent", "trips.ingest:supersede"
        else:
            author, kernel = "owner", "owner:command"
        return {"author": author, "kernel_id": kernel,
                "inputs": (str(src),) if src else (), "output": ident, "recorded_draw": None,
                "tx_time_raw": str(rec.get("tx_time", ""))}
    if sid == "pkm.demand":
        return {"author": "agent", "kernel_id": f"derive:{rec.get('transform_name', '')}",
                "inputs": (str(rec.get("input_cache_key", "")),),
                "output": str(rec.get("cache_key", "")), "recorded_draw": None,
                "tx_time_raw": str(rec.get("timestamp", ""))}
    if sid == "pkm.artifact":
        meta = rec.get("meta") or {}
        lineage = rec.get("lineage") or {}
        key = str(meta.get("cache_key", ""))
        sv = meta.get("cache_key_schema_version", 1)
        ins = [str(e.get("cache_key", "")) for e in (lineage.get("inputs") or [])
               if isinstance(e, dict)]
        if meta.get("input_hash"):
            ins.append(str(meta["input_hash"]))
        kernel, _complete = instrument_kernel_id(meta)
        return {"author": "agent", "kernel_id": kernel, "inputs": tuple(dict.fromkeys(ins)),
                "output": key,
                "recorded_draw": ({"kind": "content", "ref": key} if sv in (2, 3) else None),
                "tx_time_raw": str(meta.get("produced_at", ""))}
    raise ValueError(f"unknown source_id {sid!r}")


def instrument_kernel_id(meta: dict[str, Any]) -> tuple[str, bool]:
    """`kernel_id` for a `pkm.artifact` occurrence (design §2/§4, reviewer Q7): the cache-key
    payload minus `input_hash`, digested and namespace-tagged `instrument:sha256:<hex>` — never
    computed inside pkm, never a cache key. Built from what `meta.json` records: always
    `schema_version, producer_name, producer_version, producer_config_hash`; schema 2 adds
    `model_identity_hash` (via pkm's own `compute_model_identity_hash` over
    `producer_metadata.model_identity`) and `prompt_hash`; schema 3 adds `model_identity_hash`,
    `engine_version`, `prompt_template_hash`, `output_schema_hash` **when present**. Returns
    (kernel_id, payload_complete) — the §18.9 records life_agent writes do NOT record the
    schema-3 components, so their kernel_id is a recorded-subset digest (r03a DEVIATIONS)."""
    sv = meta.get("cache_key_schema_version", 1)
    pm = meta.get("producer_metadata") or {}
    payload: dict[str, Any] = {
        "schema_version": sv, "producer_name": meta.get("producer_name"),
        "producer_version": meta.get("producer_version"),
        "producer_config_hash": meta.get("producer_config_hash"),
    }
    complete = True
    if sv in (2, 3):
        mi = pm.get("model_identity") if isinstance(pm, dict) else None
        if isinstance(mi, dict):
            payload["model_identity_hash"] = compute_model_identity_hash(mi)
        else:
            complete = False
        wanted = ("prompt_hash",) if sv == 2 else (
            "engine_version", "prompt_template_hash", "output_schema_hash")
        for f in wanted:
            if isinstance(pm, dict) and f in pm:
                payload[f] = pm[f]
            else:
                complete = False
    hexd = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
    return f"instrument:sha256:{hexd}", complete


# --- typed acceptance: "parseable" = the legacy reader would accept the line ------------------

def _accepts(source_id: str, line: str, obj: dict[str, Any]) -> bool:
    try:
        if source_id == "act.tasks":
            return TEV._from_json(line) is not None
        if source_id == "act.trips":
            return REV._from_json(line) is not None
        if source_id == "calibration.outcomes":
            O._from_line(line)
        elif source_id == "calibration.decisions":
            DEC._from_line(line)
        elif source_id == "calibration.reactions":
            RX._from_line(line)
        elif source_id == "calibration.claude_verdicts":
            CV.from_line(line)
        elif source_id == "utility.elicitations":
            for k in ("tx_time", "latent", "stated_value", "noise_sigma"):
                if k not in obj:
                    return False
            float(obj["stated_value"]), float(obj["noise_sigma"])
        # gather / corrections / labels / demand: any JSON object (their readers index by key)
        return True
    except Exception:
        return False


# --- scanning -----------------------------------------------------------------------------------

def parse_line(source_id: str, line: str, *, ordinal: int,
               locator: str) -> tuple[Parsed | None, str]:
    """One legacy JSONL line → ``(Parsed, "ok")`` at the given canonical ordinal, or
    ``(None, status)`` with status ∈ {``blank``, ``duplicate_key``, ``unparseable``} — a
    non-event. This is THE line parser: the scan (migration/sweeps) and the live mirror both
    call it, so a mirrored line and a swept line are the same event by construction."""
    if not line.strip():
        return None, "blank"
    obj, status = parse_json_object(line)
    if status == "duplicate_key":
        return None, "duplicate_key"
    if obj is None or not _accepts(source_id, line, obj):
        return None, "unparseable"
    env = _envelope(source_id, obj)
    return Parsed(ordinal=ordinal, record=obj,
                  tx_time=utc_annotation(env["tx_time_raw"], CLOCKS[source_id]),
                  locator=locator, **env), "ok"


def _scan_jsonl(source_id: str, path: Path) -> Scan:
    clock = CLOCKS[source_id]
    parsed: list[Parsed] = []
    unparseable = dup = blank = 0
    bad: list[str] = []
    shapes: dict[str, int] = {}
    data = path.read_bytes() if path.exists() else b""
    for i, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        rec, status = parse_line(source_id, line, ordinal=len(parsed) + 1,
                                 locator=f"{path.name}:{i}")
        if rec is None:
            if status == "blank":
                blank += 1
            elif status == "duplicate_key":
                dup += 1
                bad.append(f"{path.name}:{i}:duplicate_key")
            else:
                unparseable += 1
                bad.append(f"{path.name}:{i}")
            continue
        stamp = rec.tx_time_raw
        shapes[_stamp_shape(stamp if stamp else None)] = \
            shapes.get(_stamp_shape(stamp if stamp else None), 0) + 1
        parsed.append(rec)
    # `legacy_bytes` = the byte length actually read: the live mirror's resume offset (§10)
    return Scan(source_id, tuple(parsed), unparseable, dup, blank, tuple(bad),
                {"stamp_shapes": shapes, "clock": clock, "exists": path.exists(),
                 "legacy_bytes": len(data)})


def _scan_demand(root: Path | None) -> Scan:
    parsed: list[Parsed] = []
    unparseable = dup = blank = mismatch = 0
    bad: list[str] = []
    files = 0
    if root is not None and (root / "logs" / "demand").exists():
        for f in sorted((root / "logs" / "demand").glob("*.jsonl")):     # UTC-day file order
            files += 1
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    blank += 1
                    continue
                obj, status = parse_json_object(line)
                if status == "duplicate_key":
                    dup += 1
                    bad.append(f"{f.name}:{i}:duplicate_key")
                    continue
                if obj is None:
                    unparseable += 1
                    bad.append(f"{f.name}:{i}")
                    continue
                if str(obj.get("timestamp", ""))[:10] != f.stem:
                    mismatch += 1        # A12 regroups by timestamp[:10]; a mismatch is a finding
                env = _envelope("pkm.demand", obj)
                parsed.append(Parsed(ordinal=len(parsed) + 1, record=obj,
                                     tx_time=utc_annotation(env["tx_time_raw"], "aware"),
                                     locator=f"{f.name}:{i}", **env))
    return Scan("pkm.demand", tuple(parsed), unparseable, dup, blank, tuple(bad),
                {"files": files, "file_day_mismatch": mismatch, "clock": "aware"})


def _scan_artifacts(root: Path | None) -> Scan:
    """One occurrence per `meta.json` (R5), canonical order `(produced_at, cache_key)` — realised
    as lexicographic order on the verbatim `produced_at` string then the key (r03a DEVIATIONS).
    A `lineage.json` that exists but does not parse makes the occurrence unparseable (its record
    could not be carried verbatim); an absent `lineage.json` is `lineage: null`."""
    rows: list[tuple[str, str, dict[str, Any], str]] = []
    unparseable = dup = 0
    bad: list[str] = []
    n_meta = 0
    n_dup_lineage = 0        # artefacts whose lineage.json repeats an input key (a writer
    complete: dict[str, int] = {}                # violation the envelope collapses — counted,
    shapes: dict[str, int] = {}                  # never laundered)
    if root is not None:
        for key, mp in _iter_meta_files(root):
            n_meta += 1
            meta, status = parse_json_object(mp.read_text(encoding="utf-8"))
            if status == "duplicate_key":
                dup += 1
                bad.append(f"{key}:meta:duplicate_key")
                continue
            if meta is None:
                unparseable += 1
                bad.append(f"{key}:meta")
                continue
            lp = mp.parent / "lineage.json"
            lineage: dict[str, Any] | None = None
            if lp.is_file():
                lineage, lstatus = parse_json_object(lp.read_text(encoding="utf-8"))
                if lineage is None:
                    if lstatus == "duplicate_key":
                        dup += 1
                    else:
                        unparseable += 1
                    bad.append(f"{key}:lineage:{lstatus}")
                    continue
            if lineage is not None:
                lin_keys = [str(e.get("cache_key", "")) for e in (lineage.get("inputs") or [])
                            if isinstance(e, dict)]
                if len(lin_keys) != len(set(lin_keys)):
                    n_dup_lineage += 1
            _kernel, is_complete = instrument_kernel_id(meta)
            sv = str(meta.get("cache_key_schema_version", 1))
            complete[f"schema{sv}:{'complete' if is_complete else 'partial'}"] = \
                complete.get(f"schema{sv}:{'complete' if is_complete else 'partial'}", 0) + 1
            shapes[_stamp_shape(meta.get("produced_at"))] = \
                shapes.get(_stamp_shape(meta.get("produced_at")), 0) + 1
            rows.append((str(meta.get("produced_at", "")), key,
                         {"meta": meta, "lineage": lineage}, key))
    rows.sort(key=lambda r: (r[0], r[1]))
    parsed: list[Parsed] = []
    for produced_at, _key, rec, loc in rows:
        env = _envelope("pkm.artifact", rec)
        parsed.append(Parsed(ordinal=len(parsed) + 1, record=rec,
                             tx_time=utc_annotation(produced_at, "naive-utc"), locator=loc, **env))
    return Scan("pkm.artifact", tuple(parsed), unparseable, dup, 0, tuple(bad),
                {"meta_json_files": n_meta, "kernel_payload": complete,
                 "produced_at_shapes": shapes, "lineage_duplicate_inputs": n_dup_lineage,
                 "clock": "naive-utc"})


def scan(source_id: str, paths: Paths) -> Scan:
    """Read one legacy source read-only → its parsed records in canonical order + counts."""
    if source_id == "pkm.demand":
        return _scan_demand(paths.pkm_root)
    if source_id == "pkm.artifact":
        return _scan_artifacts(paths.pkm_root)
    return _scan_jsonl(source_id, paths.legacy_file(source_id))


def scan_all(paths: Paths, order: tuple[str, ...] = MIGRATION_ORDER,
             progress: Callable[[str], None] | None = None) -> Iterator[Scan]:
    for sid in order:
        if progress:
            progress(sid)
        yield scan(sid, paths)
