"""Tests for get_stale_todos(), close_todo(), and count_todos_closed_today() in todo_store.py.

Covers the todo_store module at ``plugins/life_ops/todo_store.py``:

  * ``get_stale_todos(threshold_days=5)`` returns open todos whose
    ``last_seen`` is strictly older than the threshold.
  * Results are sorted oldest-first by ``last_seen``.
  * Recurring todos are eligible for staleness.
  * Calling ``get_stale_todos()`` does not mutate the store or affect
    ``get_open_todos()`` output.
  * ``close_todo(key)`` removes a todo from the open list and records a closure.
  * ``count_todos_closed_today()`` returns the count of todos closed since local midnight.
"""

import importlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _load_lib():
    """Import the todo_store module directly from the repo path."""
    repo_root = Path(__file__).resolve().parents[2]
    lib_path = repo_root / "plugins" / "life_ops" / "todo_store.py"
    spec = importlib.util.spec_from_file_location(
        "todo_store_under_test", lib_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def todo_store(tmp_path, monkeypatch):
    """Load todo_store module and set up isolated database."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    todo_store_mod = _load_lib()
    # Initialize the store with a fresh in-memory database or temp file
    return todo_store_mod


def test_get_stale_todos_older_than_threshold(todo_store):
    """AC: Only todos with last_seen strictly older than threshold are returned."""
    today = datetime.now().date()

    # Add three todos with different last_seen values
    store = todo_store.TodoStore()

    # Todo 1: last_seen today (not stale)
    store.add_todo(
        key="todo-today",
        text="Task for today",
        priority=1,
        recurring=False,
        last_seen=today,
    )

    # Todo 2: last_seen 3 days ago (not stale with threshold=5)
    store.add_todo(
        key="todo-3d",
        text="Task 3 days ago",
        priority=2,
        recurring=False,
        last_seen=today - timedelta(days=3),
    )

    # Todo 3: last_seen 10 days ago (stale with threshold=5)
    store.add_todo(
        key="todo-10d",
        text="Task 10 days ago",
        priority=3,
        recurring=False,
        last_seen=today - timedelta(days=10),
    )

    result = store.get_stale_todos(threshold_days=5)

    assert len(result) == 1
    assert result[0]["key"] == "todo-10d"
    assert result[0]["text"] == "Task 10 days ago"


def test_get_stale_todos_sorted_oldest_first(todo_store):
    """AC: Results are sorted oldest-first by last_seen (ascending)."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    # Add todos in random order
    store.add_todo(
        key="todo-3d",
        text="3 days ago",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=3),
    )
    store.add_todo(
        key="todo-10d",
        text="10 days ago",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=10),
    )
    store.add_todo(
        key="todo-6d",
        text="6 days ago",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=6),
    )

    result = store.get_stale_todos(threshold_days=5)

    # Should get 3d, 6d, 10d when threshold=5, but sorted oldest first
    assert len(result) == 2  # 6d and 10d are stale
    assert result[0]["key"] == "todo-10d"  # oldest first
    assert result[1]["key"] == "todo-6d"


def test_get_stale_todos_includes_recurring(todo_store):
    """AC: Recurring todos (recurring=True) are eligible for staleness."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    # Add a recurring todo that is stale
    store.add_todo(
        key="recurring-old",
        text="Old recurring task",
        priority=1,
        recurring=True,
        last_seen=today - timedelta(days=7),
    )

    result = store.get_stale_todos(threshold_days=5)

    assert len(result) == 1
    assert result[0]["key"] == "recurring-old"
    assert result[0]["recurring"] is True


def test_get_stale_todos_returns_empty_when_none_stale(todo_store):
    """AC: Returns empty list when no todos are stale."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    # All todos are recent
    store.add_todo(
        key="todo-1",
        text="Recent task 1",
        priority=1,
        recurring=False,
        last_seen=today,
    )
    store.add_todo(
        key="todo-2",
        text="Recent task 2",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=2),
    )
    store.add_todo(
        key="todo-3",
        text="Recent task 3",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=4),
    )

    result = store.get_stale_todos(threshold_days=5)

    assert result == []


def test_get_stale_todos_returns_empty_when_store_empty(todo_store):
    """AC: Returns empty list when the store is empty without error."""
    store = todo_store.TodoStore()

    result = store.get_stale_todos(threshold_days=5)

    assert result == []


def test_get_stale_todos_default_threshold(todo_store):
    """AC: Default argument threshold_days=5 is honoured."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    # Add a todo last seen 6 days ago
    store.add_todo(
        key="todo-6d",
        text="6 days old",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=6),
    )

    # Call with no arguments
    result = store.get_stale_todos()

    assert len(result) == 1
    assert result[0]["key"] == "todo-6d"


def test_get_stale_todos_does_not_mutate_store(todo_store):
    """AC: Calling get_stale_todos() does not alter get_open_todos() output."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    store.add_todo(
        key="todo-1",
        text="Task 1",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=10),
    )
    store.add_todo(
        key="todo-2",
        text="Task 2",
        priority=1,
        recurring=False,
        last_seen=today,
    )

    # Get open todos before calling get_stale_todos
    open_before = store.get_open_todos()

    # Call get_stale_todos
    store.get_stale_todos(threshold_days=5)

    # Get open todos after
    open_after = store.get_open_todos()

    # Should be identical
    assert len(open_before) == len(open_after)
    assert open_before == open_after


def test_get_stale_todos_returns_correct_row_shape(todo_store):
    """AC: Returns list of dicts with keys key, text, priority, recurring,
    source_dates, first_seen, last_seen."""
    today = datetime.now().date()

    store = todo_store.TodoStore()

    store.add_todo(
        key="test-key",
        text="Test text",
        priority=2,
        recurring=False,
        last_seen=today - timedelta(days=10),
    )

    result = store.get_stale_todos(threshold_days=5)

    assert len(result) == 1
    todo = result[0]

    # Verify all required keys are present
    required_keys = {"key", "text", "priority", "recurring", "source_dates", "first_seen", "last_seen"}
    assert set(todo.keys()) >= required_keys

    # Verify values match what we put in
    assert todo["key"] == "test-key"
    assert todo["text"] == "Test text"
    assert todo["priority"] == 2
    assert todo["recurring"] is False


def test_get_stale_todos_boundary_condition_exactly_at_threshold(todo_store):
    """AC: Todos whose last_seen falls within threshold window are excluded.
    A todo with last_seen exactly at (today - threshold_days) should be excluded."""
    today = datetime.now().date()
    threshold = 5

    store = todo_store.TodoStore()

    # Add a todo exactly at the boundary (not stale)
    store.add_todo(
        key="todo-exact",
        text="Exactly at boundary",
        priority=1,
        recurring=False,
        last_seen=today - timedelta(days=threshold),
    )

    result = store.get_stale_todos(threshold_days=threshold)

    # This todo should NOT be included (not strictly older)
    assert len(result) == 0


# ===========================================================================
# Issue #50 — close_todo() and count_todos_closed_today()
# ===========================================================================


class TestCloseTodo:
    """AC: close_todo() removes a todo from the open list and records a closure."""

    def test_close_todo_removes_from_open_todos(self, todo_store, tmp_path, monkeypatch):
        """AC: closed todo no longer appears in get_open_todos()."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.add_todo(key="t1", text="Task one", priority=1, recurring=False)
        store.close_todo("t1")
        open_todos = store.get_open_todos()
        assert not any(t["key"] == "t1" for t in open_todos)

    def test_close_todo_does_not_affect_other_todos(self, todo_store, tmp_path, monkeypatch):
        """AC: only the specified todo is removed; others remain open."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.add_todo(key="t1", text="Task one", priority=1, recurring=False)
        store.add_todo(key="t2", text="Task two", priority=2, recurring=False)
        store.close_todo("t1")
        open_todos = store.get_open_todos()
        assert any(t["key"] == "t2" for t in open_todos)
        assert len(open_todos) == 1

    def test_close_todo_nonexistent_key_does_not_raise(self, todo_store, tmp_path, monkeypatch):
        """AC: close_todo() on an unknown key is a no-op, not an error."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.close_todo("does-not-exist")


class TestCountTodosClosedToday:
    """AC: count_todos_closed_today() returns the count of todos closed since local midnight."""

    def test_returns_zero_on_fresh_store(self, todo_store, tmp_path, monkeypatch):
        """AC: Fresh store with no closures returns 0."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        assert store.count_todos_closed_today() == 0

    def test_returns_one_after_single_close_today(self, todo_store, tmp_path, monkeypatch):
        """AC: Closing one todo today returns 1."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.add_todo(key="t1", text="Task", priority=1, recurring=False)
        store.close_todo("t1")
        assert store.count_todos_closed_today() == 1

    def test_returns_correct_count_after_multiple_closures(self, todo_store, tmp_path, monkeypatch):
        """AC: Returns the correct positive integer after multiple closures today."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.add_todo(key="t1", text="Task 1", priority=1, recurring=False)
        store.add_todo(key="t2", text="Task 2", priority=1, recurring=False)
        store.close_todo("t1")
        store.close_todo("t2")
        assert store.count_todos_closed_today() == 2

    def test_excludes_closures_from_yesterday(self, todo_store, tmp_path, monkeypatch):
        """AC: Closures recorded before local midnight today are not counted."""
        import datetime
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        store._closures.append({"key": "old", "closed_at": yesterday})
        store._save_to_disk()
        assert store.count_todos_closed_today() == 0

    def test_counts_today_but_not_yesterday(self, todo_store, tmp_path, monkeypatch):
        """AC: Two closures from yesterday + one today → returns 1."""
        import datetime
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
        store._closures.append({"key": "old1", "closed_at": yesterday})
        store._closures.append({"key": "old2", "closed_at": yesterday})
        store.add_todo(key="today", text="Today", priority=1, recurring=False)
        store.close_todo("today")
        assert store.count_todos_closed_today() == 1

    def test_persists_across_reload(self, todo_store, tmp_path, monkeypatch):
        """AC: Closure count survives a store reload from disk."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        store = todo_store.TodoStore()
        store.add_todo(key="t1", text="Task", priority=1, recurring=False)
        store.close_todo("t1")
        store2 = todo_store.TodoStore()
        assert store2.count_todos_closed_today() == 1
