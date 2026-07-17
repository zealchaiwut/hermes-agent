"""Todo store module for managing open todos and tracking staleness.

Provides TodoStore class with methods to add, retrieve, and analyze todos.
The get_stale_todos() method identifies todos that haven't been seen recently.
"""

from datetime import datetime, timedelta
from typing import Any, Callable, Optional
import json
from pathlib import Path
import os


class TodoStore:
    """In-memory todo store with staleness detection."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the todo store.

        Args:
            db_path: Optional path to persist todos. If None, uses in-memory storage.
        """
        self._todos = {}  # key -> todo dict
        self.db_path = db_path or self._get_default_db_path()
        self._load_from_disk()

    def _get_default_db_path(self) -> str:
        """Get the default database path from HERMES_HOME."""
        hermes_home = os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))
        db_dir = Path(hermes_home) / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "todos.json")

    def _load_from_disk(self) -> None:
        """Load todos from disk if the database file exists."""
        if Path(self.db_path).exists():
            try:
                with open(self.db_path, "r") as f:
                    data = json.load(f)
                    # Convert date strings back to date objects
                    for key, todo in data.items():
                        if "last_seen" in todo and isinstance(todo["last_seen"], str):
                            todo["last_seen"] = datetime.fromisoformat(todo["last_seen"]).date()
                        if "first_seen" in todo and isinstance(todo["first_seen"], str):
                            todo["first_seen"] = datetime.fromisoformat(todo["first_seen"]).date()
                    self._todos = data
            except (json.JSONDecodeError, IOError):
                self._todos = {}

    def _save_to_disk(self) -> None:
        """Save todos to disk."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # Convert date objects to ISO format strings for JSON
        serializable = {}
        for key, todo in self._todos.items():
            todo_copy = dict(todo)
            if isinstance(todo_copy.get("last_seen"), datetime):
                todo_copy["last_seen"] = todo_copy["last_seen"].isoformat()
            else:
                todo_copy["last_seen"] = todo_copy["last_seen"].isoformat() if hasattr(todo_copy.get("last_seen"), "isoformat") else str(todo_copy["last_seen"])
            if isinstance(todo_copy.get("first_seen"), datetime):
                todo_copy["first_seen"] = todo_copy["first_seen"].isoformat()
            else:
                todo_copy["first_seen"] = todo_copy["first_seen"].isoformat() if hasattr(todo_copy.get("first_seen"), "isoformat") else str(todo_copy["first_seen"])
            serializable[key] = todo_copy
        with open(self.db_path, "w") as f:
            json.dump(serializable, f, indent=2)

    def add_todo(
        self,
        key: str,
        text: str,
        priority: int,
        recurring: bool,
        last_seen: Optional[datetime.date] = None,
        first_seen: Optional[datetime.date] = None,
        source_dates: Optional[list] = None,
    ) -> None:
        """Add or update a todo.

        Args:
            key: Unique identifier for the todo.
            text: Human-readable description.
            priority: Priority level (integer).
            recurring: Whether this is a recurring todo.
            last_seen: Date the todo was last seen (defaults to today).
            first_seen: Date the todo was first created (defaults to today).
            source_dates: List of dates this todo appears on (defaults to empty list).
        """
        today = datetime.now().date()
        self._todos[key] = {
            "key": key,
            "text": text,
            "priority": priority,
            "recurring": recurring,
            "last_seen": last_seen or today,
            "first_seen": first_seen or today,
            "source_dates": source_dates or [],
        }
        self._save_to_disk()

    def get_open_todos(self) -> list[dict[str, Any]]:
        """Get all open todos.

        Returns:
            List of todo dictionaries with keys: key, text, priority, recurring,
            source_dates, first_seen, last_seen.
        """
        # Return a copy of all todos
        result = []
        for todo in self._todos.values():
            result.append(dict(todo))
        return result

    def get_stale_todos(self, threshold_days: int = 5) -> list[dict[str, Any]]:
        """Get todos that haven't been seen recently.

        A todo is considered stale if its last_seen date is strictly older
        than (today - threshold_days) days.

        Args:
            threshold_days: Number of days to consider as the staleness threshold.
                           Defaults to 5.

        Returns:
            List of stale todo dictionaries, sorted oldest-first by last_seen.
            Each dict has keys: key, text, priority, recurring, source_dates,
            first_seen, last_seen.
        """
        today = datetime.now().date()
        cutoff_date = today - timedelta(days=threshold_days)

        stale = []
        for todo in self._todos.values():
            # Include todos whose last_seen is strictly before the cutoff
            # i.e., last_seen < (today - threshold_days)
            if todo["last_seen"] < cutoff_date:
                stale.append(dict(todo))

        # Sort by last_seen ascending (oldest first)
        stale.sort(key=lambda t: t["last_seen"])

        return stale
