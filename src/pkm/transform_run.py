"""Transform run orchestration (SPEC v0.2.0 §20-§24).

Analogous to ``extract.py`` for Phase 1.  Loads a transform
declaration, finds eligible sources, evaluates policies, optionally
pauses for HITL approval, then dispatches the producer over each
source and writes artifacts through the cache layer.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from pkm.cache import content_file, write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config
from pkm.hashing import compute_cache_key
from pkm.policy import (
    Allow,
    Block,
    PolicyContext,
    RequireApproval,
    SourceRef,
    evaluate_policies,
)
from pkm.policy_loader import load_policy
from pkm.telemetry import TransformLogEntry, log_transform_execution
from pkm.transform import TransformProducer
from pkm.transform_declaration import TransformDeclaration, load_transform_declaration
from pkm.transforms._shared import estimate_cost, make_producer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransformRunResult:
    """Outcome of a ``run_transform`` invocation."""

    total_sources: int
    processed: int
    succeeded: int
    failed: int
    cache_hits: int
    approval_required: bool
    approval_id: str | None
    blocked: bool
    block_reason: str | None
    elapsed_seconds: float
    total_cost_usd: float


@dataclass(frozen=True)
class _EligibleSource:
    # ``source_id``/``current_path``/``tags`` carry the upstream's source
    # identity when the input is a primary-producer artifact. For a chained
    # input (another transform's output, §18.7) there is no source row, so
    # ``source_id`` falls back to the input artifact's ``cache_key``,
    # ``current_path`` is empty, and ``tags`` is empty.
    source_id: str
    current_path: str
    tags: frozenset[str]
    extractor_cache_key: str


def run_transform(
    root: Path,
    config: Config,
    transform_name: str,
    *,
    limit: int | None = None,
    approval_id: str | None = None,
    producer_override: TransformProducer | None = None,
    progress: Callable[[str], None] | None = None,
) -> TransformRunResult:
    """Full transform orchestration pipeline.

    Args:
        root: Knowledge root (SPEC S3).
        config: Loaded config with policies section.
        transform_name: Name of the transform declaration.
        limit: Maximum number of sources to process.
        approval_id: Pre-approved approval ID (skips policy evaluation).
        producer_override: Injected producer for testing (skips
            construction from declaration).
        progress: Optional per-source progress callback.
    """
    t_start = time.monotonic()

    decl = load_transform_declaration(root, transform_name)

    with open_catalogue(root) as conn:
        eligible = _find_eligible_sources(conn, decl)

    if limit is not None:
        eligible = eligible[:limit]

    if not eligible:
        elapsed = time.monotonic() - t_start
        return TransformRunResult(
            total_sources=0, processed=0, succeeded=0, failed=0,
            cache_hits=0, approval_required=False, approval_id=None,
            blocked=False, block_reason=None,
            elapsed_seconds=elapsed, total_cost_usd=0.0,
        )

    input_sizes = _estimate_input_sizes(root, eligible)
    cost = estimate_cost(decl, input_sizes)

    if approval_id is None:
        decision = _evaluate_all_policies(root, config, decl, eligible, cost)

        if isinstance(decision, Block):
            elapsed = time.monotonic() - t_start
            logger.warning(
                "transform %s blocked: %s", transform_name, decision.reason,
            )
            return TransformRunResult(
                total_sources=len(eligible), processed=0, succeeded=0,
                failed=0, cache_hits=0,
                approval_required=False, approval_id=None,
                blocked=True, block_reason=decision.reason,
                elapsed_seconds=elapsed, total_cost_usd=0.0,
            )

        if isinstance(decision, RequireApproval):
            aid = _create_approval_record(
                root, config, decl, eligible, cost, decision.reason,
            )
            elapsed = time.monotonic() - t_start
            return TransformRunResult(
                total_sources=len(eligible), processed=0, succeeded=0,
                failed=0, cache_hits=0,
                approval_required=True, approval_id=aid,
                blocked=False, block_reason=None,
                elapsed_seconds=elapsed, total_cost_usd=0.0,
            )

    # Dispatch on the declaration's producer_class (SPEC §18.2) — an explicit,
    # closed lookup, replacing the hard-wired EntityExtractionProducer.
    producer = producer_override or make_producer(decl)

    result = _execute_run(
        root=root,
        decl=decl,
        producer=producer,
        eligible=eligible,
        estimated_cost=cost,
        progress=progress,
        t_start=t_start,
    )
    return result


def _find_eligible_sources(
    conn: duckdb.DuckDBPyConnection,
    decl: TransformDeclaration,
) -> list[_EligibleSource]:
    """Find artifacts of the declaration's ``input_producer`` to transform.

    Resolved over the ``artifacts`` table (by producer + status), left-joined
    to ``sources`` (§18.7): a primary-producer input keeps its source identity,
    while a chained input — another transform's output, which has no ``sources``
    row — is no longer dropped (the previous inner join silently did so). For a
    chained input, source-derived fields fall back to the input artifact itself.
    """
    if decl.input_producer is None:
        return []

    rows = conn.execute(
        "SELECT a.cache_key, a.input_hash, s.source_id, s.current_path "
        "FROM artifacts a "
        "LEFT JOIN sources s ON s.source_id = a.input_hash "
        "WHERE a.producer_name = ? AND a.status = ? "
        "ORDER BY a.input_hash",
        [decl.input_producer, decl.input_required_status],
    ).fetchall()

    result: list[_EligibleSource] = []
    for cache_key, _input_hash, source_id, current_path in rows:
        if source_id is not None:
            tag_rows = conn.execute(
                "SELECT tag FROM source_tags WHERE source_id = ?",
                [source_id],
            ).fetchall()
            tags = frozenset(r[0] for r in tag_rows)
        else:
            tags = frozenset()
        result.append(
            _EligibleSource(
                source_id=source_id if source_id is not None else cache_key,
                current_path=current_path if current_path is not None else "",
                tags=tags,
                extractor_cache_key=cache_key,
            )
        )
    return result


def _estimate_input_sizes(
    root: Path, eligible: list[_EligibleSource],
) -> list[int]:
    sizes: list[int] = []
    for src in eligible:
        cf = content_file(root, src.extractor_cache_key)
        if cf.exists():
            sizes.append(cf.stat().st_size)
        else:
            sizes.append(0)
    return sizes


def _evaluate_all_policies(
    root: Path,
    config: Config,
    decl: TransformDeclaration,
    eligible: list[_EligibleSource],
    cost: Any,
) -> Allow | Block | RequireApproval:
    policies = []
    for name in decl.policies:
        policies.append(load_policy(root, name))

    source_refs = [
        SourceRef(
            source_id=s.source_id,
            tags=s.tags,
            path=s.current_path,
        )
        for s in eligible
    ]

    ctx = PolicyContext(
        root=root,
        policy_config=config.policies,
    )

    return evaluate_policies(policies, decl, source_refs, cost, ctx)


def _create_approval_record(
    root: Path,
    config: Config,
    decl: TransformDeclaration,
    eligible: list[_EligibleSource],
    cost: Any,
    reason: str,
) -> str:
    from pkm.approval import create_approval

    with open_catalogue(root) as conn:
        return create_approval(
            conn,
            transform_name=decl.name,
            transform_declaration_hash=decl.declaration_hash,
            cost_estimate_usd=cost.total_usd,
            source_ids=[s.source_id for s in eligible],
            sample_cache_keys=[],
            policy_reasons=[("policy", reason)],
        )


def _execute_run(
    *,
    root: Path,
    decl: TransformDeclaration,
    producer: TransformProducer,
    eligible: list[_EligibleSource],
    estimated_cost: Any,
    progress: Callable[[str], None] | None,
    t_start: float,
) -> TransformRunResult:
    succeeded = 0
    failed = 0
    cache_hits = 0
    total_cost = 0.0
    cost_limit = estimated_cost.total_usd * 2.0

    with open_catalogue(root) as conn:
        for i, src in enumerate(eligible, start=1):
            cf = content_file(root, src.extractor_cache_key)
            if not cf.exists():
                logger.warning(
                    "extractor content missing for %s, skipping",
                    src.extractor_cache_key[:12],
                )
                failed += 1
                continue

            input_content = cf.read_bytes()
            input_hash = hashlib.sha256(input_content).hexdigest()

            result = producer.produce(cf, input_hash, {})

            prompt_hash = result.producer_metadata.get("prompt_hash", "")
            if result.status != "success" or not prompt_hash:
                failed += 1
                _log_telemetry(
                    root, decl, producer, "", src, result, True,
                )
                if progress is not None:
                    err = result.error_message or ""
                    suffix = f": {err[:60]}" if err else ""
                    progress(
                        f"[{i}/{len(eligible)}] "
                        f"{src.source_id[:12]}... {result.status}{suffix}"
                    )
                continue

            prompt_template_hash = hashlib.sha256(
                decl.prompt_text.encode("utf-8")
            ).hexdigest()
            cache_key = compute_cache_key(
                input_hash=input_hash,
                producer_name=producer.name,
                producer_version=producer.version,
                producer_config={},
                schema_version=3,
                model_identity=producer.model_identity,
                engine_version=producer.engine_version,
                prompt_template_hash=prompt_template_hash,
                output_schema=decl.output_schema,
            )

            lineage = [
                {"cache_key": src.extractor_cache_key, "role": decl.input_role},
            ]

            outcome = write_artifact(
                root, conn,
                cache_key=cache_key,
                input_hash=input_hash,
                producer_name=producer.name,
                producer_version=producer.version,
                producer_config={},
                result=result,
                lineage=lineage,
                cache_key_schema_version=3,
            )

            if not outcome.wrote:
                cache_hits += 1
            else:
                succeeded += 1

            source_cost = result.producer_metadata.get("cost_usd", 0.0)
            total_cost += source_cost

            _log_telemetry(root, decl, producer, cache_key, src, result, outcome.wrote)

            if progress is not None:
                status = "hit" if not outcome.wrote else result.status
                progress(
                    f"[{i}/{len(eligible)}] "
                    f"{src.source_id[:12]}... {status}"
                )

            if cost_limit > 0 and total_cost > cost_limit:
                logger.warning(
                    "cost limit exceeded: $%.4f > 2x estimate $%.4f",
                    total_cost, estimated_cost.total_usd,
                )
                break

    elapsed = time.monotonic() - t_start
    return TransformRunResult(
        total_sources=len(eligible),
        processed=succeeded + failed + cache_hits,
        succeeded=succeeded,
        failed=failed,
        cache_hits=cache_hits,
        approval_required=False,
        approval_id=None,
        blocked=False,
        block_reason=None,
        elapsed_seconds=elapsed,
        total_cost_usd=total_cost,
    )


def _log_telemetry(
    root: Path,
    decl: TransformDeclaration,
    producer: TransformProducer,
    cache_key: str,
    src: _EligibleSource,
    result: Any,
    is_new: bool,
) -> None:
    pm = result.producer_metadata or {}
    log_transform_execution(
        root,
        TransformLogEntry(
            timestamp=datetime.now(UTC).isoformat(),
            transform_name=decl.name,
            transform_version=decl.version,
            cache_key=cache_key,
            input_cache_key=src.extractor_cache_key,
            model=decl.model_identity.get("model", ""),
            prompt_name=decl.prompt_name,
            status=result.status,
            error_message=result.error_message or "",
            input_tokens=pm.get("input_tokens", 0),
            output_tokens=pm.get("output_tokens", 0),
            latency_ms=pm.get("latency_ms", 0),
            cost_usd=pm.get("cost_usd", 0.0),
            cache_hit=not is_new,
        ),
    )
