"""Tests for ``pkm.approval`` — HITL approval lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from pkm.approval import (
    approve,
    create_approval,
    get_approval,
    list_pending,
    reject,
)
from pkm.catalogue import open_catalogue


def _create(root: Path, **overrides: object) -> str:
    defaults = {
        "transform_name": "entity_extraction",
        "transform_declaration_hash": "a" * 64,
        "cost_estimate_usd": 1.50,
        "source_ids": ["s1", "s2"],
        "sample_cache_keys": ["c" * 64],
        "policy_reasons": [("cost_gate", "exceeds $1 budget")],
    }
    defaults.update(overrides)
    with open_catalogue(root) as conn:
        return create_approval(conn, **defaults)  # type: ignore[arg-type]


def test_create_and_get_round_trip(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        record = get_approval(conn, aid)

    assert record is not None
    assert record.approval_id == aid
    assert record.transform_name == "entity_extraction"
    assert record.status == "pending"
    assert record.cost_estimate_usd == 1.50
    assert record.source_count == 2
    assert record.source_ids == ["s1", "s2"]
    assert record.sample_cache_keys == ["c" * 64]
    assert record.policy_reasons == [("cost_gate", "exceeds $1 budget")]
    assert record.decided_at is None
    assert record.rejection_reason is None


def test_approve_lifecycle(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        approve(conn, aid)
        record = get_approval(conn, aid)

    assert record is not None
    assert record.status == "approved"
    assert record.decided_at is not None


def test_double_approve_is_no_op(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        approve(conn, aid)
        approve(conn, aid)
        record = get_approval(conn, aid)

    assert record is not None
    assert record.status == "approved"


def test_reject_lifecycle(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        reject(conn, aid, reason="too expensive")
        record = get_approval(conn, aid)

    assert record is not None
    assert record.status == "rejected"
    assert record.rejection_reason == "too expensive"
    assert record.decided_at is not None


def test_reject_requires_reason(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn, pytest.raises(
        ValueError, match=r"reason.*required"
    ):
        reject(conn, aid, reason="")


def test_approve_rejected_fails(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        reject(conn, aid, reason="nope")
    with open_catalogue(migrated_root) as conn, pytest.raises(
        ValueError, match=r"already rejected"
    ):
        approve(conn, aid)


def test_reject_approved_fails(migrated_root: Path) -> None:
    aid = _create(migrated_root)
    with open_catalogue(migrated_root) as conn:
        approve(conn, aid)
    with open_catalogue(migrated_root) as conn, pytest.raises(
        ValueError, match=r"already approved"
    ):
        reject(conn, aid, reason="too late")


def test_list_pending(migrated_root: Path) -> None:
    aid1 = _create(migrated_root)
    aid2 = _create(
        migrated_root,
        transform_declaration_hash="b" * 64,
    )
    with open_catalogue(migrated_root) as conn:
        approve(conn, aid1)

    with open_catalogue(migrated_root) as conn:
        pending = list_pending(conn)

    assert len(pending) == 1
    assert pending[0].approval_id == aid2


def test_get_nonexistent_returns_none(migrated_root: Path) -> None:
    with open_catalogue(migrated_root) as conn:
        assert get_approval(conn, "nonexistent") is None
