"""Tests for the email→GTD projector (`life_agent.tasks.project`).

The projector is now a pure *producer* into the one task ledger: it reads grounded
``action_items`` artifacts from a seeded pkm catalogue and files fresh assertions via the
command layer (``commands.add`` → ``Asserted(origin="email")``). Idempotency and
"never resurrect a cleared task" are properties of the ledger's known identities — a task
the human completes (a real ``Disposed`` event) is not re-filed. No capture/diff, no live
store, no live model.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from life_agent.tasks import commands, store
from life_agent.tasks import events as ev
from life_agent.tasks.project import project_action_items, to_candidates
from life_agent.tasks.read import EmailActions
from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue, run_migrations
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult

_EMAIL = (
    "From: Dana <dana@example.com>\nSubject: Lease\n\n"
    "Please send the signed lease back by Friday."
)


@pytest.fixture(autouse=True)
def temp_gtd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "tasks.db")
    monkeypatch.setattr(commands, "LEDGER_PATH", tmp_path / "events.jsonl")
    store.init_db()


# --- candidate flattening + assertion identity --------------------------------


def _email_actions(message_id: str | None, items: list[dict]) -> EmailActions:
    return EmailActions(
        message_id=message_id, subject="Lease", email_produced_at=None,
        items=items, email_cache_key="emailck", action_items_cache_key="aick",
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
    assert cands[0].identity != cands[1].identity
    assert cands[0].identity == ev.assertion_identity(
        "task", "send the signed lease", "Send the signed lease by Friday"
    )


def test_to_candidates_identity_is_message_id_independent() -> None:
    item = [{"action_phrase": "Do it", "source_quote": "do it"}]
    a = to_candidates([_email_actions("<a@x>", item)])
    b = to_candidates([_email_actions("<b@y>", item)])
    assert a[0].identity == b[0].identity
    assert a[0].message_id != b[0].message_id


def test_to_candidates_skips_empty_action_phrase() -> None:
    ea = _email_actions("<m@x>", [{"action_phrase": "  ", "source_quote": "x"}])
    assert to_candidates([ea]) == []


# --- end-to-end: seed pkm catalogue → project → ledger ------------------------


def _seed_catalogue(
    root: Path, *, message_id: str, items: list[dict], triage_category: str | None = None,
) -> None:
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
        if triage_category is not None:
            tri_content = json.dumps(
                {"format_version": 1, "category": triage_category, "reason": "test"}
            ).encode("utf-8")
            tri_in = hashlib.sha256(b"triage:" + email_bytes).hexdigest()
            tri_ck = compute_cache_key(
                input_hash=tri_in, producer_name="email_triage",
                producer_version="0.1.0", producer_config={},
            )
            write_artifact(
                root, conn, cache_key=tri_ck, input_hash=tri_in,
                producer_name="email_triage", producer_version="0.1.0", producer_config={},
                result=ProducerResult(
                    status="success", content=tri_content,
                    content_type="application/json", content_encoding="utf-8",
                    error_message=None, producer_metadata={"completion": "complete"},
                ),
                lineage=[{"cache_key": email_ck, "role": "source_text"}],
            )


_LEASE = [{"action_phrase": "Send the lease", "source_quote": "send the signed lease"}]


def test_project_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(root, message_id="<lease-7@example.com>", items=_LEASE)
    report = project_action_items(root, user_id=7, commit=False, notify=False)
    assert len(report.fresh) == 1
    assert report.filed == 0
    assert not commands.LEDGER_PATH.exists()  # nothing recorded
    assert "No tasks" in store.get_tasks(7)  # nothing projected


def test_project_files_then_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(root, message_id="<lease-7@example.com>", items=_LEASE)

    r1 = project_action_items(root, user_id=7, notify=False)
    assert r1.filed == 1
    tasks = store.get_tasks(7)
    assert "Send the lease [src:email <lease-7@example.com>]" in tasks
    assert [e.type for e in ev.load(commands.LEDGER_PATH)] == ["asserted"]

    r2 = project_action_items(root, user_id=7, notify=False)
    assert r2.fresh == []
    assert r2.filed == 0  # known identity → not re-filed


def test_project_does_not_refile_a_completed_email_task(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(root, message_id="<lease-7@example.com>", items=_LEASE)

    project_action_items(root, user_id=7, notify=False)  # files task id 1
    commands.complete(7, task_id=1)  # human completes it → Disposed{done}

    r = project_action_items(root, user_id=7, notify=False)
    assert r.filed == 0  # the disposed identity is known → never resurrected
    types = [e.type for e in ev.load(commands.LEDGER_PATH)]
    assert types == ["asserted", "disposed"]


# --- triage gate (SPEC §18.8) -------------------------------------------------


def test_project_filters_nonactionable_email_by_triage(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(
        root, message_id="<promo@example.com>",
        items=[{"action_phrase": "Register now", "source_quote": "send the signed lease"}],
        triage_category="newsletter_marketing",
    )
    report = project_action_items(root, user_id=7, notify=False)
    assert report.nonactionable_filtered == 1
    assert report.total_emails == 0
    assert report.filed == 0
    assert "No tasks" in store.get_tasks(7)


def test_project_keeps_actionable_email_by_triage(tmp_path: Path) -> None:
    root = tmp_path / "pkm"
    _seed_catalogue(
        root, message_id="<invoice@example.com>",
        items=[{"action_phrase": "Pay the invoice", "source_quote": "send the signed lease"}],
        triage_category="transactional",
    )
    report = project_action_items(root, user_id=7, notify=False)
    assert report.nonactionable_filtered == 0
    assert report.total_emails == 1
    assert report.filed == 1
