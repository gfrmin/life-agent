"""Tests for the email→GTD action faculty (`life_agent.tasks`, M2).

Pure-unit tests for policy + dedup, a temp-db test for the jarvis write seam, and
an end-to-end test that seeds a pkm catalogue (email + action_items artifact +
lineage), reads it, files to a temp jarvis db, and proves process-once dedup on a
re-run. No live model, no live store.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from life_agent.tasks import dedup
from life_agent.tasks.project import project_action_items, to_candidates
from life_agent.tasks.read import EmailActions, read_action_items
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult

_EMAIL = (
    "From: Dana <dana@example.com>\nSubject: Lease\n\n"
    "Please send the signed lease back by Friday."
)


# --- policy -------------------------------------------------------------------


def _email_actions(message_id, items, *, email_ck="emailck", ai_ck="aick") -> EmailActions:
    return EmailActions(
        message_id=message_id, subject="Lease", email_produced_at=None,
        items=items, email_cache_key=email_ck, action_items_cache_key=ai_ck,
    )


def test_to_candidates_everything_to_inbox_with_citation() -> None:
    ea = _email_actions(
        "<lease-1@example.com>",
        [
            {
                "action_phrase": "Send the signed lease by Friday",
                "source_quote": "send the signed lease",
            },
            {"action_phrase": "Pay the deposit", "source_quote": "pay the deposit"},
        ],
    )
    cands = to_candidates([ea])
    assert len(cands) == 2
    assert all(c.list_name == "inbox" for c in cands)
    assert cands[0].citation == "[src:email <lease-1@example.com>]"
    assert cands[0].task_text().endswith("[src:email <lease-1@example.com>]")
    assert cands[0].dedup_key == "<lease-1@example.com>#0"
    assert cands[1].dedup_key == "<lease-1@example.com>#1"


def test_to_candidates_falls_back_to_cache_key_without_message_id() -> None:
    ea = _email_actions(
        None, [{"action_phrase": "Do it", "source_quote": "do it"}], email_ck="abc123",
    )
    (c,) = to_candidates([ea])
    assert c.message_id == "abc123"
    assert c.dedup_key == "abc123#0"


def test_to_candidates_skips_empty_action_phrase() -> None:
    ea = _email_actions("<m@x>", [{"action_phrase": "  ", "source_quote": "x"}])
    assert to_candidates([ea]) == []


# --- dedup ledger -------------------------------------------------------------


def test_dedup_load_missing_is_empty(tmp_path: Path) -> None:
    assert dedup.load_seen(tmp_path / "nope.jsonl") == set()


def test_dedup_round_trip(tmp_path: Path) -> None:
    ledger = tmp_path / "tasks" / "seen.jsonl"
    dedup.append_seen(ledger, [{"dedup_key": "a#0", "message_id": "a"}])
    dedup.append_seen(ledger, [{"dedup_key": "b#1", "message_id": "b"}])
    assert dedup.load_seen(ledger) == {"a#0", "b#1"}


def test_dedup_tolerates_garbage_lines(tmp_path: Path) -> None:
    ledger = tmp_path / "seen.jsonl"
    ledger.write_text('{"dedup_key": "ok#0"}\nnot json\n{"no_key": 1}\n', encoding="utf-8")
    assert dedup.load_seen(ledger) == {"ok#0"}


# --- end-to-end: seed catalogue → project → dedup ----------------------------


def _seed_catalogue(root: Path, *, message_id: str, items: list[dict]) -> None:
    for d in ("cache", "logs", "sources"):
        (root / d).mkdir(parents=True, exist_ok=True)
    run_migrations(root)
    email_bytes = _EMAIL.encode("utf-8")
    src_id = hashlib.sha256(email_bytes).hexdigest()
    with open_catalogue(root) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, current_path, first_seen, last_seen, size_bytes) "
            "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
            [src_id, str(root / "sources" / "m.eml"), len(email_bytes)],
        )
        email_ck = compute_cache_key(
            input_hash=src_id, producer_name="email", producer_version="1", producer_config={},
        )
        write_artifact(
            root, conn, cache_key=email_ck, input_hash=src_id, producer_name="email",
            producer_version="1", producer_config={},
            result=ProducerResult(
                status="success", content=email_bytes, content_type="text/plain",
                content_encoding="utf-8", error_message=None,
                producer_metadata={
                    "completion": "complete", "message_id": message_id, "subject": "Lease",
                },
            ),
        )
        ai_content = json.dumps({"format_version": 1, "action_items": items}).encode("utf-8")
        ai_hash = hashlib.sha256(email_bytes).hexdigest()  # transform input = email content hash
        ai_ck = compute_cache_key(
            input_hash=ai_hash, producer_name="action_items",
            producer_version="0.1.0", producer_config={},
        )
        write_artifact(
            root, conn, cache_key=ai_ck, input_hash=ai_hash, producer_name="action_items",
            producer_version="0.1.0", producer_config={},
            result=ProducerResult(
                status="success", content=ai_content, content_type="application/json",
                content_encoding="utf-8", error_message=None,
                producer_metadata={"completion": "complete"},
            ),
            lineage=[{"cache_key": email_ck, "role": "source_text"}],
        )


def test_read_action_items_traces_email_provenance(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(
        root, message_id="<lease-7@example.com>",
        items=[{"action_phrase": "Send the lease", "source_quote": "send the signed lease"}],
    )
    emails = read_action_items(root)
    assert len(emails) == 1
    assert emails[0].message_id == "<lease-7@example.com>"
    assert emails[0].subject == "Lease"
    assert emails[0].items[0]["action_phrase"] == "Send the lease"


def test_project_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(
        root, message_id="<lease-7@example.com>",
        items=[{"action_phrase": "Send the lease", "source_quote": "send the signed lease"}],
    )
    ledger = tmp_path / "tasks" / "seen.jsonl"
    db_path = tmp_path / "jarvis.db"

    report = project_action_items(
        root, db_path=db_path, user_id=7, ledger=ledger, commit=False, notify=False,
    )
    assert len(report.fresh) == 1
    assert report.filed == 0
    assert not ledger.exists()   # nothing recorded
    assert not db_path.exists()  # no store written


def test_project_files_then_dedup(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(
        root, message_id="<lease-7@example.com>",
        items=[{"action_phrase": "Send the lease", "source_quote": "send the signed lease"}],
    )
    ledger = tmp_path / "tasks" / "seen.jsonl"
    db_path = tmp_path / "jarvis.db"

    # First pass: one fresh candidate → filed with its citation → ledger records it.
    r1 = project_action_items(
        root, db_path=db_path, user_id=7, ledger=ledger, notify=False,
    )
    assert r1.filed == 1
    rows = sqlite3.connect(db_path).execute(
        "SELECT user_id, text, list FROM tasks"
    ).fetchall()
    assert rows == [(7, "Send the lease [src:email <lease-7@example.com>]", "inbox")]

    # Second pass: same artifacts → zero fresh (process-once), no new row.
    r2 = project_action_items(
        root, db_path=db_path, user_id=7, ledger=ledger, notify=False,
    )
    assert r2.fresh == []
    assert r2.filed == 0
    n2 = sqlite3.connect(db_path).execute("SELECT count(*) FROM tasks").fetchone()[0]
    assert n2 == 1  # idempotent — no new task
