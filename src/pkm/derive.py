"""Demand-driven derivation (SPEC §18.11).

``derive`` resolves ONE (input, declared transform chain) target cache-first:
every node's schema-3 cache key is computed BEFORE any model call, a fully
warm chain performs zero model calls, and a miss materialises exactly the
missing suffix through the existing policy gate and ``write_artifact``.

Chain resolution is static (§18.11): a declaration whose ``input.producer``
names another declaration recurses; any other name is the leaf (a Phase-1
extractor). The ``source_id`` form binds the leaf to the §18.10-**current**
artifact — that binding is what makes rederivation lazy.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import duckdb

from pkm.cache import content_file, has_success_artifact, write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config
from pkm.hashing import compute_cache_key
from pkm.policy import Block, RequireApproval
from pkm.telemetry import DemandLogEntry, log_demand
from pkm.transform import TransformProducer
from pkm.transform_declaration import (
    TransformDeclaration,
    load_transform_declaration,
)
from pkm.transform_run import (
    _create_approval_record,
    _EligibleSource,
    _evaluate_all_policies,
    _log_telemetry,
)
from pkm.transforms._shared import estimate_cost, make_producer

DeriveStatus = Literal["success", "failed", "blocked", "approval_required"]


@dataclass(frozen=True)
class NodeResolution:
    """One resolved chain node: its key, its input, and how it resolved."""

    transform_name: str
    cache_key: str
    input_cache_key: str
    hit: bool


@dataclass(frozen=True)
class DeriveResult:
    """Outcome of a ``derive`` invocation (SPEC §18.11)."""

    status: DeriveStatus
    target_cache_key: str | None
    nodes: list[NodeResolution]
    error_message: str | None = None
    approval_id: str | None = None


def derive(
    root: Path,
    config: Config,
    transform_name: str,
    *,
    source_id: str | None = None,
    input_cache_key: str | None = None,
    caller: str = "cli",
    approval_id: str | None = None,
    producer_overrides: dict[str, TransformProducer] | None = None,
) -> DeriveResult:
    """Resolve one (input, declared chain) target, materialising misses.

    Exactly one of ``source_id`` (binds the leaf to the §18.10-current
    artifact) and ``input_cache_key`` (an explicit pin) must be given.
    ``producer_overrides`` maps transform names to injected producers
    (the test seam, mirroring ``run_transform``'s ``producer_override``).
    """
    chain, leaf_producer = _resolve_chain(root, transform_name)
    overrides = producer_overrides or {}
    nodes: list[NodeResolution] = []

    with open_catalogue(root) as conn:
        if input_cache_key is not None and source_id is None:
            if not has_success_artifact(root, conn, input_cache_key):
                return DeriveResult(
                    "failed", None, nodes,
                    error_message=(
                        f"input artifact {input_cache_key} is not a cached "
                        f"success"),
                )
            current_ck = input_cache_key
        elif source_id is not None and input_cache_key is None:
            leaf = _current_leaf_artifact(conn, source_id, leaf_producer)
            if leaf is None:
                return DeriveResult(
                    "failed", None, nodes,
                    error_message=(
                        f"no current '{leaf_producer}' artifact for source "
                        f"{source_id} — run `pkm extract` first"),
                )
            current_ck = leaf
        else:
            raise ValueError(
                "exactly one of source_id / input_cache_key is required"
            )

        for decl in chain:
            outcome = _resolve_node(
                root, conn, config, decl,
                input_ck=current_ck,
                producer=overrides.get(decl.name),
                caller=caller,
                approval_id=approval_id,
            )
            if isinstance(outcome, DeriveResult):
                return DeriveResult(
                    outcome.status, None, nodes,
                    error_message=outcome.error_message,
                    approval_id=outcome.approval_id,
                )
            nodes.append(outcome)
            current_ck = outcome.cache_key

    return DeriveResult("success", current_ck, nodes)


def _resolve_chain(
    root: Path, transform_name: str,
) -> tuple[list[TransformDeclaration], str]:
    """Declarations leaf-transform-first, plus the primary leaf producer name."""
    reversed_chain: list[TransformDeclaration] = []
    seen: set[str] = set()
    name = transform_name
    while True:
        if name in seen:
            raise ValueError(f"transform chain cycle at {name!r}")
        seen.add(name)
        decl = load_transform_declaration(root, name)
        reversed_chain.append(decl)
        upstream = decl.input_producer
        if upstream is None:
            raise ValueError(
                f"transform {name!r} declares no input.producer"
            )
        if (root / "transforms" / f"{upstream}.yaml").exists():
            name = upstream
            continue
        return list(reversed(reversed_chain)), upstream


def _current_leaf_artifact(
    conn: duckdb.DuckDBPyConnection, source_id: str, producer_name: str,
) -> str | None:
    """The §18.10-current artifact for (source, leaf producer), or None."""
    row = conn.execute(
        "SELECT cache_key FROM artifacts "
        "WHERE input_hash = ? AND producer_name = ? AND status = 'success' "
        "ORDER BY produced_at DESC, cache_key DESC LIMIT 1",
        [source_id, producer_name],
    ).fetchone()
    return str(row[0]) if row is not None else None


def _resolve_node(
    root: Path,
    conn: duckdb.DuckDBPyConnection,
    config: Config,
    decl: TransformDeclaration,
    *,
    input_ck: str,
    producer: TransformProducer | None,
    caller: str,
    approval_id: str | None,
) -> NodeResolution | DeriveResult:
    """Resolve one chain node cache-first. Returns the resolution, or a
    terminal ``DeriveResult`` (blocked / approval / failed)."""
    t0 = time.monotonic()

    cf = content_file(root, input_ck)
    if not cf.exists():
        return DeriveResult(
            "failed", None, [],
            error_message=f"content missing for input artifact {input_ck}",
        )
    input_content = cf.read_bytes()
    input_hash = hashlib.sha256(input_content).hexdigest()

    prod = producer if producer is not None else make_producer(decl)
    prompt_template_hash = hashlib.sha256(
        decl.prompt_text.encode("utf-8")
    ).hexdigest()
    cache_key = compute_cache_key(
        input_hash=input_hash,
        producer_name=prod.name,
        producer_version=prod.version,
        producer_config={},
        schema_version=3,
        model_identity=prod.model_identity,
        engine_version=prod.engine_version,
        prompt_template_hash=prompt_template_hash,
        output_schema=decl.output_schema,
    )

    if has_success_artifact(root, conn, cache_key):
        _demand(root, caller, decl.name, cache_key, input_ck,
                hit=True, cost_usd=0.0, t0=t0)
        return NodeResolution(decl.name, cache_key, input_ck, hit=True)

    src = _eligible_for(conn, input_ck)
    if approval_id is None:
        cost = estimate_cost(decl, [len(input_content)])
        decision = _evaluate_all_policies(root, config, decl, [src], cost)
        if isinstance(decision, Block):
            return DeriveResult(
                "blocked", None, [], error_message=decision.reason,
            )
        if isinstance(decision, RequireApproval):
            aid = _create_approval_record(
                root, config, decl, [src], cost, decision.reason,
            )
            return DeriveResult(
                "approval_required", None, [], approval_id=aid,
            )

    result = prod.produce(cf, input_hash, {})
    prompt_hash = result.producer_metadata.get("prompt_hash", "")
    if result.status != "success" or not prompt_hash:
        _log_telemetry(root, decl, prod, "", src, result, True)
        _demand(root, caller, decl.name, cache_key, input_ck,
                hit=False, cost_usd=0.0, t0=t0)
        return DeriveResult(
            "failed", None, [],
            error_message=result.error_message or "transform failed",
        )

    write_artifact(
        root, conn,
        cache_key=cache_key,
        input_hash=input_hash,
        producer_name=prod.name,
        producer_version=prod.version,
        producer_config={},
        result=result,
        lineage=[{"cache_key": input_ck, "role": decl.input_role}],
        cache_key_schema_version=3,
    )
    _log_telemetry(root, decl, prod, cache_key, src, result, True)
    _demand(root, caller, decl.name, cache_key, input_ck, hit=False,
            cost_usd=float(result.producer_metadata.get("cost_usd", 0.0)),
            t0=t0)
    return NodeResolution(decl.name, cache_key, input_ck, hit=False)


def _eligible_for(
    conn: duckdb.DuckDBPyConnection, artifact_ck: str,
) -> _EligibleSource:
    """Policy-facing identity for one input artifact (§18.7 fallback rules)."""
    row = conn.execute(
        "SELECT a.input_hash, s.source_id, s.current_path "
        "FROM artifacts a "
        "LEFT JOIN sources s ON s.source_id = a.input_hash "
        "WHERE a.cache_key = ?",
        [artifact_ck],
    ).fetchone()
    if row is None or row[1] is None:
        return _EligibleSource(
            source_id=artifact_ck, current_path="", tags=frozenset(),
            extractor_cache_key=artifact_ck,
        )
    tags = frozenset(
        str(r[0]) for r in conn.execute(
            "SELECT tag FROM source_tags WHERE source_id = ?", [row[1]],
        ).fetchall()
    )
    return _EligibleSource(
        source_id=str(row[1]),
        current_path=str(row[2]) if row[2] is not None else "",
        tags=tags,
        extractor_cache_key=artifact_ck,
    )


def _demand(
    root: Path, caller: str, transform_name: str, cache_key: str,
    input_cache_key: str, *, hit: bool, cost_usd: float, t0: float,
) -> None:
    log_demand(root, DemandLogEntry(
        timestamp=datetime.now(UTC).isoformat(),
        caller=caller,
        transform_name=transform_name,
        cache_key=cache_key,
        input_cache_key=input_cache_key,
        hit=hit,
        cost_usd=cost_usd,
        latency_ms=int((time.monotonic() - t0) * 1000),
    ))
