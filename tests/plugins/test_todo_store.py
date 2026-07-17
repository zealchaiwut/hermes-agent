"""Tests for get_stale_todos() in todo_store.py.

Covers the todo_store module at ``plugins/life_ops/todo_store.py``:

  * ``get_stale_todos(threshold_days=5)`` returns open todos whose
    ``last_seen`` is strictly older than the threshold.
  * Results are sorted oldest-first by ``last_seen``.
  * Recurring todos are eligible for staleness.
  * Calling ``get_stale_todos()`` does not mutate the store or affect
    ``get_open_todos()`` output.
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
