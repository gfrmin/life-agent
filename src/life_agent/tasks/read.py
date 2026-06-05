"""Read cached ``action_items`` artifacts and trace each back to its email (M2).

Read-only over the live pkm catalogue. For each successful ``action_items``
artifact: load its `{action_items:[…]}` JSON, follow the lineage edge
(`role='source_text'`, written by `transform_run`) to the source **email**
artifact, and pull the email's Message-ID + subject + extraction time from its
producer metadata — the citation/dedup key for the action faculty.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import yaml

import life_agent.core as C
from pkm.cache import CacheInconsistencyError, read_artifact

logger = logging.getLogger(__name__)


def pkm_root() -> Path:
    """The pkm knowledge root (where ``catalogue.duckdb`` + the cache live)."""
    cfg = yaml.safe_load(C.PKM_CONFIG.read_text(encoding="utf-8"))
    return Path(cfg["root_dir"]).expanduser()


@dataclass(frozen=True)
class EmailActions:
    """The action items extracted from one email, plus its provenance."""

    message_id: str | None
    subject: str | None
    email_produced_at: datetime | None
    items: list[dict[str, Any]]
    email_cache_key: str | None
    action_items_cache_key: str
    # The email's ``email_triage`` category (SPEC §18.8), or None if the email
    # has not been triaged. The projector's actionable-category policy reads this.
    category: str | None = None


def _connect(root: Path) -> duckdb.DuckDBPyConnection:
    """Open the catalogue read-only (never block, never be blocked by, an extraction)."""
    return duckdb.connect(str(root / "catalogue.duckdb"), read_only=True)


def read_action_items(
    root: Path,
    *,
    limit: int | None = None,
    since: datetime | None = None,
) -> list[EmailActions]:
    """Most-recent-first ``action_items`` artifacts with their email provenance.

    ``limit`` caps the number of artifacts; ``since`` filters by the artifact's
    extraction time (``produced_at``). Artifacts with no items are skipped.
    """
    out: list[EmailActions] = []
    conn = _connect(root)
    try:
        q = (
            "SELECT cache_key FROM artifacts "
            "WHERE producer_name = 'action_items' AND status = 'success'"
        )
        params: list[Any] = []
        if since is not None:
            q += " AND produced_at >= ?"
            params.append(since)
        q += " ORDER BY produced_at DESC"
        if limit is not None:
            q += " LIMIT ?"
            params.append(limit)

        for (ai_ck,) in conn.execute(q, params).fetchall():
            entry = _safe_read(root, conn, ai_ck)
            if entry is None or entry.content is None:
                continue
            items = json.loads(entry.content.decode("utf-8")).get("action_items", [])
            if not items:
                continue

            email_ck = _source_email_key(conn, ai_ck)
            message_id = subject = None
            email_produced_at: datetime | None = None
            category: str | None = None
            if email_ck is not None:
                email = _safe_read(root, conn, email_ck)
                if email is not None:
                    message_id = email.producer_metadata.get("message_id")
                    subject = email.producer_metadata.get("subject")
                    email_produced_at = email.produced_at
                category = _triage_category(root, conn, email_ck)

            out.append(
                EmailActions(
                    message_id=message_id,
                    subject=subject,
                    email_produced_at=email_produced_at,
                    items=items,
                    email_cache_key=email_ck,
                    action_items_cache_key=ai_ck,
                    category=category,
                )
            )
    finally:
        conn.close()
    return out


def _source_email_key(
    conn: duckdb.DuckDBPyConnection, action_items_cache_key: str,
) -> str | None:
    row = conn.execute(
        "SELECT input_cache_key FROM artifact_lineage "
        "WHERE artifact_cache_key = ? AND role = 'source_text'",
        [action_items_cache_key],
    ).fetchone()
    return row[0] if row else None


def _triage_category(
    root: Path, conn: duckdb.DuckDBPyConnection, email_cache_key: str,
) -> str | None:
    """The most recent ``email_triage`` category for this email (None if untriaged).

    Reverse-lineage: find the triage artifact whose input is this email
    (`role='source_text'`), newest first, and read its ``category`` (§18.8).
    """
    row = conn.execute(
        "SELECT l.artifact_cache_key FROM artifact_lineage l "
        "JOIN artifacts a ON a.cache_key = l.artifact_cache_key "
        "WHERE l.input_cache_key = ? AND a.producer_name = 'email_triage' "
        "AND a.status = 'success' ORDER BY a.produced_at DESC LIMIT 1",
        [email_cache_key],
    ).fetchone()
    if not row:
        return None
    entry = _safe_read(root, conn, row[0])
    if entry is None or entry.content is None:
        return None
    cat = json.loads(entry.content.decode("utf-8")).get("category")
    return str(cat) if cat is not None else None


def _safe_read(root: Path, conn: duckdb.DuckDBPyConnection, cache_key: str) -> Any:
    """``read_artifact`` that downgrades a cache inconsistency to a warning + skip."""
    try:
        return read_artifact(root, conn, cache_key)
    except CacheInconsistencyError:
        logger.warning("skipping artifact with missing cache files: %s", cache_key[:12])
        return None
