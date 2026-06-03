"""HITL approval data model (SPEC v0.2.0 §22.4).

Manages the lifecycle of transform approval records in the catalogue:
create → (approve | reject).  Approval records are stored in
``pending_approvals`` with related tables for sources, samples, and
reasons.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import duckdb


@dataclass(frozen=True)
class ApprovalRecord:
    """Read-back of a pending_approvals row plus related data."""

    approval_id: str
    transform_name: str
    transform_declaration_hash: str
    cost_estimate_usd: float | None
    source_count: int
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime
    decided_at: datetime | None
    rejection_reason: str | None
    source_ids: list[str]
    sample_cache_keys: list[str]
    policy_reasons: list[tuple[str, str]]


def create_approval(
    conn: duckdb.DuckDBPyConnection,
    *,
    transform_name: str,
    transform_declaration_hash: str,
    cost_estimate_usd: float | None,
    source_ids: list[str],
    sample_cache_keys: list[str],
    policy_reasons: list[tuple[str, str]],
) -> str:
    """Create a pending approval record and return its UUID4 ID."""
    approval_id = str(uuid.uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)

    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute(
            "INSERT INTO pending_approvals "
            "(approval_id, transform_name, transform_declaration_hash, "
            " cost_estimate_usd, source_count, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            [
                approval_id,
                transform_name,
                transform_declaration_hash,
                cost_estimate_usd,
                len(source_ids),
                now,
            ],
        )
        for sid in source_ids:
            conn.execute(
                "INSERT INTO approval_sources (approval_id, source_id) "
                "VALUES (?, ?)",
                [approval_id, sid],
            )
        for ck in sample_cache_keys:
            conn.execute(
                "INSERT INTO approval_samples (approval_id, cache_key) "
                "VALUES (?, ?)",
                [approval_id, ck],
            )
        for policy_name, reason in policy_reasons:
            conn.execute(
                "INSERT INTO approval_reasons "
                "(approval_id, policy_name, reason) VALUES (?, ?, ?)",
                [approval_id, policy_name, reason],
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return approval_id


def approve(
    conn: duckdb.DuckDBPyConnection, approval_id: str,
) -> None:
    """Approve a pending record.  No-op if already approved."""
    record = get_approval(conn, approval_id)
    if record is None:
        raise ValueError(f"approval {approval_id} not found")
    if record.status == "approved":
        return
    if record.status == "rejected":
        raise ValueError(
            f"approval {approval_id} was already rejected"
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    conn.execute(
        "UPDATE pending_approvals "
        "SET status = 'approved', decided_at = ? "
        "WHERE approval_id = ?",
        [now, approval_id],
    )


def reject(
    conn: duckdb.DuckDBPyConnection,
    approval_id: str,
    *,
    reason: str,
) -> None:
    """Reject a pending record.  Reason is required."""
    if not reason:
        raise ValueError("rejection reason is required")
    record = get_approval(conn, approval_id)
    if record is None:
        raise ValueError(f"approval {approval_id} not found")
    if record.status == "rejected":
        return
    if record.status == "approved":
        raise ValueError(
            f"approval {approval_id} was already approved"
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    conn.execute(
        "UPDATE pending_approvals "
        "SET status = 'rejected', decided_at = ?, "
        "    rejection_reason = ? "
        "WHERE approval_id = ?",
        [now, reason, approval_id],
    )


def get_approval(
    conn: duckdb.DuckDBPyConnection, approval_id: str,
) -> ApprovalRecord | None:
    """Fetch a single approval record with all related data."""
    row = conn.execute(
        "SELECT transform_name, transform_declaration_hash, "
        "cost_estimate_usd, source_count, status, created_at, "
        "decided_at, rejection_reason "
        "FROM pending_approvals WHERE approval_id = ?",
        [approval_id],
    ).fetchone()
    if row is None:
        return None

    source_ids = [
        r[0] for r in conn.execute(
            "SELECT source_id FROM approval_sources "
            "WHERE approval_id = ? ORDER BY source_id",
            [approval_id],
        ).fetchall()
    ]
    sample_cache_keys = [
        r[0] for r in conn.execute(
            "SELECT cache_key FROM approval_samples "
            "WHERE approval_id = ? ORDER BY cache_key",
            [approval_id],
        ).fetchall()
    ]
    policy_reasons = [
        (r[0], r[1]) for r in conn.execute(
            "SELECT policy_name, reason FROM approval_reasons "
            "WHERE approval_id = ? ORDER BY policy_name",
            [approval_id],
        ).fetchall()
    ]

    return ApprovalRecord(
        approval_id=approval_id,
        transform_name=row[0],
        transform_declaration_hash=row[1],
        cost_estimate_usd=row[2],
        source_count=row[3],
        status=row[4],
        created_at=row[5],
        decided_at=row[6],
        rejection_reason=row[7],
        source_ids=source_ids,
        sample_cache_keys=sample_cache_keys,
        policy_reasons=policy_reasons,
    )


def list_pending(
    conn: duckdb.DuckDBPyConnection,
) -> list[ApprovalRecord]:
    """Return all pending approval records."""
    rows = conn.execute(
        "SELECT approval_id FROM pending_approvals "
        "WHERE status = 'pending' ORDER BY created_at",
    ).fetchall()
    results: list[ApprovalRecord] = []
    for (aid,) in rows:
        record = get_approval(conn, aid)
        if record is not None:
            results.append(record)
    return results
