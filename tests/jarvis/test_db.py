"""Tests for Jarvis Lite GTD database functions."""

import pytest

from jarvis import db


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    yield


USER = 12345


class TestAddTask:
    def test_add_to_inbox(self):
        result = db.add_task(USER, "Buy milk")
        assert "Added" in result
        assert "Buy milk" in result
        assert "#inbox" in result

    def test_add_with_due_date(self):
        result = db.add_task(USER, "Call dentist", "scheduled", "2026-05-01")
        assert "#scheduled" in result
        assert "2026-05-01" in result

    def test_add_invalid_list(self):
        result = db.add_task(USER, "test", "badlist")
        assert "Invalid list" in result

    def test_add_invalid_date(self):
        result = db.add_task(USER, "test", "scheduled", "not-a-date")
        assert "Invalid date" in result

    def test_add_preserves_tags(self):
        result = db.add_task(USER, "Buy milk @errands")
        assert "@errands" in result


class TestCompleteTask:
    def test_complete_by_id(self):
        db.add_task(USER, "Task one")
        result = db.complete_task(USER, task_id=1)
        assert "Completed" in result
        assert "Task one" in result

    def test_complete_by_text_match(self):
        db.add_task(USER, "Buy groceries")
        result = db.complete_task(USER, text_match="groceries")
        assert "Completed" in result

    def test_complete_not_found(self):
        result = db.complete_task(USER, task_id=999)
        assert "not found" in result

    def test_complete_no_args(self):
        result = db.complete_task(USER)
        assert "Specify" in result

    def test_task_id_zero(self):
        result = db.complete_task(USER, task_id=0)
        assert "not found" in result


class TestDeleteTask:
    def test_delete(self):
        db.add_task(USER, "To delete")
        result = db.delete_task(USER, 1)
        assert "Deleted" in result

    def test_delete_not_found(self):
        result = db.delete_task(USER, 999)
        assert "not found" in result


class TestMoveTask:
    def test_move_to_next(self):
        db.add_task(USER, "A task")
        result = db.move_task(USER, 1, "next")
        assert "#next" in result

    def test_move_with_date(self):
        db.add_task(USER, "Schedule me")
        result = db.move_task(USER, 1, "scheduled", "2026-06-01")
        assert "#scheduled" in result
        assert "2026-06-01" in result

    def test_move_invalid_list(self):
        db.add_task(USER, "A task")
        result = db.move_task(USER, 1, "bad")
        assert "Invalid list" in result

    def test_move_not_found(self):
        result = db.move_task(USER, 999, "next")
        assert "not found" in result


class TestTodayFeatures:
    def test_mark_today(self):
        db.add_task(USER, "Focus task")
        result = db.mark_today(USER, 1)
        assert "Marked for today" in result

    def test_get_today_tasks(self):
        db.add_task(USER, "Task A")
        db.mark_today(USER, 1)
        result = db.get_today_tasks(USER)
        assert "Task A" in result
        assert "★" in result

    def test_clear_today(self):
        db.add_task(USER, "Task A")
        db.mark_today(USER, 1)
        result = db.clear_today(USER)
        assert "Cleared" in result
        today = db.get_today_tasks(USER)
        assert "No tasks" in today


class TestReadTools:
    def test_get_tasks_all(self):
        db.add_task(USER, "A")
        db.add_task(USER, "B", "next")
        result = db.get_tasks(USER)
        assert "A" in result
        assert "B" in result

    def test_get_tasks_filtered(self):
        db.add_task(USER, "Inbox item")
        db.add_task(USER, "Next item", "next")
        result = db.get_tasks(USER, "inbox")
        assert "Inbox item" in result
        assert "Next item" not in result

    def test_get_tasks_empty(self):
        result = db.get_tasks(USER)
        assert "No tasks" in result

    def test_get_by_tag(self):
        db.add_task(USER, "Task @work")
        db.add_task(USER, "Task @home")
        result = db.get_tasks_by_tag(USER, "work")
        assert "@work" in result
        assert "@home" not in result

    def test_get_task_counts(self):
        db.add_task(USER, "A")
        db.add_task(USER, "B", "next")
        result = db.get_task_counts(USER)
        assert "#inbox: 1" in result
        assert "#next: 1" in result

    def test_completed_this_week(self):
        db.add_task(USER, "Done task")
        db.complete_task(USER, task_id=1)
        result = db.get_completed_this_week(USER)
        assert "Done task" in result


class TestMultiUser:
    def test_user_isolation(self):
        db.add_task(111, "User A task")
        db.add_task(222, "User B task")
        a_tasks = db.get_tasks(111)
        b_tasks = db.get_tasks(222)
        assert "User A task" in a_tasks
        assert "User B task" not in a_tasks
        assert "User B task" in b_tasks
        assert "User A task" not in b_tasks
