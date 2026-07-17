"""Tests for issue #49: daily stale-todo nudge scheduler in LifeOpsDiscordAdapter.

Each test class is anchored to a specific Acceptance Criterion.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_todo(key="todo-1", text="Fix auth bug", days_old=6):
    return {
        "key": key,
        "text": text,
        "priority": 1,
        "recurring": False,
        "last_seen": date.today() - timedelta(days=days_old),
        "first_seen": date.today() - timedelta(days=days_old + 1),
        "source_dates": [],
    }


def _make_away_mode(is_away=False):
    m = MagicMock()
    m.is_away.return_value = is_away
    return m


def _make_todo_store(stale_todos=None):
    m = MagicMock()
    m.get_stale_todos.return_value = stale_todos if stale_todos is not None else []
    return m


def _make_channel():
    ch = AsyncMock()
    ch.send = AsyncMock()
    return ch


def _make_client(channel=None):
    client = MagicMock()
    client.get_channel.return_value = channel if channel is not None else _make_channel()
    return client


def _make_adapter(client=None, away_mode=None, todo_store=None, channel_id="12345"):
    from services.lifeops_discord_adapter import LifeOpsDiscordAdapter
    return LifeOpsDiscordAdapter(
        client=client or _make_client(),
        away_mode=away_mode or _make_away_mode(),
        todo_store=todo_store or _make_todo_store(),
        channel_id=channel_id,
    )


# ---------------------------------------------------------------------------
# AC1 — DISCORD_NUDGE_STALE_HOUR unset → scheduler does not start
# ---------------------------------------------------------------------------


class TestSchedulerDisabledByDefault:
    def test_scheduler_disabled_when_hour_not_set(self, monkeypatch):
        """AC1: No DISCORD_NUDGE_STALE_HOUR → _start_stale_todo_nudge_scheduler is a no-op."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        adapter = _make_adapter()
        adapter._start_stale_todo_nudge_scheduler()
        assert adapter._nudge_task is None

    def test_config_disabled_when_hour_not_set(self, monkeypatch):
        """AC1: _read_stale_todo_nudge_config returns enabled=False when hour unset."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["enabled"] is False

    def test_config_disabled_when_hour_is_empty_string(self, monkeypatch):
        """AC1: Empty DISCORD_NUDGE_STALE_HOUR string also disables the scheduler."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["enabled"] is False

    def test_config_disabled_when_hour_is_non_integer(self, monkeypatch):
        """AC1: Non-integer DISCORD_NUDGE_STALE_HOUR disables the scheduler gracefully."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "noon")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["enabled"] is False


# ---------------------------------------------------------------------------
# AC2 — DISCORD_NUDGE_STALE_MINUTE defaults gracefully when unset
# ---------------------------------------------------------------------------


class TestMinuteDefault:
    def test_minute_defaults_to_zero_when_unset(self, monkeypatch):
        """AC2: Unset DISCORD_NUDGE_STALE_MINUTE defaults to 0."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.delenv("DISCORD_NUDGE_STALE_MINUTE", raising=False)
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["enabled"] is True
        assert cfg["minute"] == 0

    def test_minute_parsed_when_set(self, monkeypatch):
        """AC2: DISCORD_NUDGE_STALE_MINUTE is parsed correctly when set."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.setenv("DISCORD_NUDGE_STALE_MINUTE", "30")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["minute"] == 30

    def test_minute_defaults_to_zero_on_bad_value(self, monkeypatch):
        """AC2: Non-integer DISCORD_NUDGE_STALE_MINUTE falls back to 0."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.setenv("DISCORD_NUDGE_STALE_MINUTE", "half-past")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["minute"] == 0

    def test_hour_is_parsed_correctly(self, monkeypatch):
        """AC2: DISCORD_NUDGE_STALE_HOUR is parsed and stored in config."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "22")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["hour"] == 22


# ---------------------------------------------------------------------------
# AC3 — DISCORD_NUDGE_STALE_DAYS defaults to 5; passed to get_stale_todos()
# ---------------------------------------------------------------------------


class TestStaleDaysDefault:
    def test_days_defaults_to_five_when_unset(self, monkeypatch):
        """AC3: Unset DISCORD_NUDGE_STALE_DAYS defaults to 5."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.delenv("DISCORD_NUDGE_STALE_DAYS", raising=False)
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["threshold_days"] == 5

    def test_days_parsed_when_set(self, monkeypatch):
        """AC3: Custom DISCORD_NUDGE_STALE_DAYS is parsed correctly."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.setenv("DISCORD_NUDGE_STALE_DAYS", "10")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["threshold_days"] == 10

    def test_days_defaults_to_five_on_bad_value(self, monkeypatch):
        """AC3: Non-integer DISCORD_NUDGE_STALE_DAYS falls back to 5."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.setenv("DISCORD_NUDGE_STALE_DAYS", "many")
        from services.lifeops_discord_adapter import _read_stale_todo_nudge_config
        cfg = _read_stale_todo_nudge_config()
        assert cfg["threshold_days"] == 5

    @pytest.mark.asyncio
    async def test_fire_passes_threshold_days_to_get_stale_todos(self):
        """AC3: _fire_stale_todo_nudge passes threshold_days to get_stale_todos()."""
        store = _make_todo_store(stale_todos=[])
        adapter = _make_adapter(todo_store=store)
        cfg = {"threshold_days": 7}
        await adapter._fire_stale_todo_nudge(cfg)
        store.get_stale_todos.assert_called_once_with(threshold_days=7)

    @pytest.mark.asyncio
    async def test_fire_passes_custom_threshold_days(self):
        """AC3: Custom threshold_days value is forwarded to get_stale_todos()."""
        store = _make_todo_store(stale_todos=[])
        adapter = _make_adapter(todo_store=store)
        cfg = {"threshold_days": 10}
        await adapter._fire_stale_todo_nudge(cfg)
        store.get_stale_todos.assert_called_once_with(threshold_days=10)


# ---------------------------------------------------------------------------
# AC4 — away_mode.is_away() True → no message posted
# ---------------------------------------------------------------------------


class TestAwayModeSuppressesNudge:
    @pytest.mark.asyncio
    async def test_no_send_when_away(self):
        """AC4: Nudge is suppressed when away_mode.is_away() returns True."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        away_mode = _make_away_mode(is_away=True)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, away_mode=away_mode, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_stale_todos_not_called_when_away(self):
        """AC4: get_stale_todos() is not even called when away_mode.is_away() is True."""
        store = _make_todo_store(stale_todos=[_make_todo()])
        away_mode = _make_away_mode(is_away=True)
        adapter = _make_adapter(away_mode=away_mode, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        store.get_stale_todos.assert_not_called()


# ---------------------------------------------------------------------------
# AC5 — empty stale list → no message posted
# ---------------------------------------------------------------------------


class TestEmptyStaleListSuppressesNudge:
    @pytest.mark.asyncio
    async def test_no_send_when_stale_list_is_empty(self):
        """AC5: No Discord message is posted when get_stale_todos() returns []."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_stale_todos_is_called_even_when_not_away(self):
        """AC5: get_stale_todos() is always called when not in away mode."""
        store = _make_todo_store(stale_todos=[])
        away_mode = _make_away_mode(is_away=False)
        adapter = _make_adapter(away_mode=away_mode, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        store.get_stale_todos.assert_called_once()


# ---------------------------------------------------------------------------
# AC6 — correct message format when stale todos are present
# ---------------------------------------------------------------------------


class TestNudgeMessageFormat:
    @pytest.mark.asyncio
    async def test_message_starts_with_still_on_these(self):
        """AC6: Message content begins with 'Still on these?'."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        channel.send.assert_awaited_once()
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert content.startswith("Still on these?")

    @pytest.mark.asyncio
    async def test_message_includes_todo_count(self):
        """AC6: Message includes '{n} todo(s)' with the correct count."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo("t1"), _make_todo("t2")])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert "2 todo(s)" in content

    @pytest.mark.asyncio
    async def test_message_includes_threshold_days(self):
        """AC6: Message includes '{threshold}+ days'."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert "5+ days" in content

    @pytest.mark.asyncio
    async def test_message_exact_format(self):
        """AC6: Full format matches 'Still on these? {n} todo(s) haven't moved in {threshold}+ days:'."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("t1"), _make_todo("t2"), _make_todo("t3")]
        store = _make_todo_store(stale_todos=todos)
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 7}
        await adapter._fire_stale_todo_nudge(cfg)
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert content == "Still on these? 3 todo(s) haven't moved in 7+ days:"

    @pytest.mark.asyncio
    async def test_single_todo_uses_singular_count(self):
        """AC6: A single stale todo still uses '1 todo(s)' per the AC format."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert "1 todo(s)" in content

    @pytest.mark.asyncio
    async def test_custom_threshold_appears_in_message(self):
        """AC6/UAT5: Custom threshold (10) appears in the message as '10+ days'."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 10}
        await adapter._fire_stale_todo_nudge(cfg)
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert "10+ days" in content


# ---------------------------------------------------------------------------
# AC7 — TodoClosureView (select → Mark Done / Dismiss / Snooze) is reused
# ---------------------------------------------------------------------------


class TestTodoClosureViewExists:
    def test_todo_closure_view_is_importable(self):
        """AC7: TodoClosureView is importable from services.lifeops_discord_adapter."""
        from services.lifeops_discord_adapter import TodoClosureView
        assert TodoClosureView is not None

    def test_no_other_view_class_introduced(self):
        """AC7: The module exports TodoClosureView and no other View class."""
        import services.lifeops_discord_adapter as mod
        import inspect
        # Collect names that look like View classes (other than TodoClosureView)
        extra_views = [
            name for name, obj in inspect.getmembers(mod, inspect.isclass)
            if name.endswith("View") and name != "TodoClosureView"
        ]
        assert extra_views == [], f"Unexpected View classes: {extra_views}"

    @pytest.mark.asyncio
    async def test_fire_sends_with_todo_closure_view(self):
        """AC7: _fire_stale_todo_nudge sends with a TodoClosureView instance as 'view'."""
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store(stale_todos=[_make_todo()])
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        channel.send.assert_awaited_once()
        _, kwargs = channel.send.call_args
        assert isinstance(kwargs.get("view"), TodoClosureView)

    @pytest.mark.asyncio
    async def test_todo_closure_view_receives_stale_todos(self):
        """AC7: TodoClosureView is constructed with the stale todo list."""
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("t1"), _make_todo("t2")]
        store = _make_todo_store(stale_todos=todos)
        adapter = _make_adapter(client=client, todo_store=store)
        cfg = {"threshold_days": 5}
        await adapter._fire_stale_todo_nudge(cfg)
        _, kwargs = channel.send.call_args
        view = kwargs.get("view")
        assert isinstance(view, TodoClosureView)
        assert view.todos == todos


# ---------------------------------------------------------------------------
# TodoClosureView internals (discord.py-dependent)
# ---------------------------------------------------------------------------


try:
    import discord as _discord_mod
    _DISCORD_AVAILABLE = True
except ImportError:
    _DISCORD_AVAILABLE = False


@pytest.mark.skipif(not _DISCORD_AVAILABLE, reason="discord.py not installed")
class TestTodoClosureViewDiscord:
    def test_view_is_discord_ui_view_subclass(self):
        """AC7: TodoClosureView subclasses discord.ui.View."""
        import discord
        from services.lifeops_discord_adapter import TodoClosureView
        assert issubclass(TodoClosureView, discord.ui.View)

    def test_view_has_select_component(self):
        """AC7: TodoClosureView includes a select → choose which todo to act on."""
        import discord
        from services.lifeops_discord_adapter import TodoClosureView
        todos = [_make_todo("t1", "Fix auth"), _make_todo("t2", "Update docs")]
        view = TodoClosureView(todos=todos)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1, "TodoClosureView must have at least one Select component"

    def test_view_has_mark_done_button(self):
        """AC7: TodoClosureView has a 'Mark Done' button."""
        import discord
        from services.lifeops_discord_adapter import TodoClosureView
        todos = [_make_todo()]
        view = TodoClosureView(todos=todos)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        labels = [b.label for b in buttons]
        assert "Mark Done" in labels

    def test_view_has_dismiss_button(self):
        """AC7: TodoClosureView has a 'Dismiss' button."""
        import discord
        from services.lifeops_discord_adapter import TodoClosureView
        todos = [_make_todo()]
        view = TodoClosureView(todos=todos)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        labels = [b.label for b in buttons]
        assert "Dismiss" in labels

    def test_view_has_snooze_button(self):
        """AC7: TodoClosureView has a 'Snooze' button."""
        import discord
        from services.lifeops_discord_adapter import TodoClosureView
        todos = [_make_todo()]
        view = TodoClosureView(todos=todos)
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        labels = [b.label for b in buttons]
        assert "Snooze" in labels


# ---------------------------------------------------------------------------
# AC8 — Scheduler loop fires once per 24 h, idempotent per day
# ---------------------------------------------------------------------------


class TestSchedulerLoopCadence:
    @pytest.mark.asyncio
    async def test_scheduler_creates_task_when_enabled(self, monkeypatch):
        """AC8: _start_stale_todo_nudge_scheduler creates an asyncio task when enabled."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.setenv("DISCORD_NUDGE_STALE_MINUTE", "0")
        adapter = _make_adapter()

        loop_started = asyncio.Event()

        async def fake_loop(cfg):
            loop_started.set()
            await asyncio.sleep(9999)

        with patch.object(adapter, "_stale_todo_nudge_scheduler_loop", fake_loop):
            adapter._start_stale_todo_nudge_scheduler()
            assert adapter._nudge_task is not None
            adapter._nudge_task.cancel()
            try:
                await adapter._nudge_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, monkeypatch):
        """AC8: Calling _start_stale_todo_nudge_scheduler twice does not create a second task."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        adapter = _make_adapter()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_stale_todo_nudge_scheduler_loop", fake_loop):
            adapter._start_stale_todo_nudge_scheduler()
            first_task = adapter._nudge_task
            adapter._start_stale_todo_nudge_scheduler()
            second_task = adapter._nudge_task
            assert first_task is second_task
            first_task.cancel()
            try:
                await first_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cancel_task_sets_nudge_task_to_none(self, monkeypatch):
        """AC8: _cancel_stale_todo_nudge_task cancels and clears the task."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        adapter = _make_adapter()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_stale_todo_nudge_scheduler_loop", fake_loop):
            adapter._start_stale_todo_nudge_scheduler()
            assert adapter._nudge_task is not None
            await adapter._cancel_stale_todo_nudge_task()
            assert adapter._nudge_task is None

    @pytest.mark.asyncio
    async def test_loop_sleeps_until_next_target_time(self, monkeypatch):
        """AC8: The loop computes a positive delay and sleeps before firing."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        import datetime

        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)
            raise asyncio.CancelledError()

        adapter = _make_adapter()
        cfg = {"hour": 8, "minute": 0, "threshold_days": 5}

        with patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await adapter._stale_todo_nudge_scheduler_loop(cfg)
            except asyncio.CancelledError:
                pass

        assert len(sleep_calls) == 1
        # Delay must be positive and ≤ 24 h (86400 s)
        assert 0 < sleep_calls[0] <= 86400


# ---------------------------------------------------------------------------
# AC9 — Method names follow the established pattern
# ---------------------------------------------------------------------------


class TestMethodNames:
    def test_has_start_method(self):
        """AC9: LifeOpsDiscordAdapter has _start_stale_todo_nudge_scheduler."""
        adapter = _make_adapter()
        assert callable(getattr(adapter, "_start_stale_todo_nudge_scheduler", None))

    def test_has_loop_method(self):
        """AC9: LifeOpsDiscordAdapter has _stale_todo_nudge_scheduler_loop."""
        adapter = _make_adapter()
        assert callable(getattr(adapter, "_stale_todo_nudge_scheduler_loop", None))

    def test_has_fire_method(self):
        """AC9: LifeOpsDiscordAdapter has _fire_stale_todo_nudge."""
        adapter = _make_adapter()
        assert callable(getattr(adapter, "_fire_stale_todo_nudge", None))

    def test_has_cancel_method(self):
        """AC9: LifeOpsDiscordAdapter has _cancel_stale_todo_nudge_task."""
        adapter = _make_adapter()
        assert callable(getattr(adapter, "_cancel_stale_todo_nudge_task", None))

    def test_nudge_task_attribute_initialized_to_none(self):
        """AC9: _nudge_task is initialized to None on construction."""
        adapter = _make_adapter()
        assert adapter._nudge_task is None


# ===========================================================================
# Issue #50 — Idle-day nudge scheduler
# ===========================================================================


def _make_todo_store_with_open(open_todos=None, closed_today=0):
    m = MagicMock()
    m.get_open_todos.return_value = open_todos if open_todos is not None else []
    m.count_todos_closed_today.return_value = closed_today
    return m


def _make_adapter_for_idle(client=None, away_mode=None, todo_store=None, channel_id="12345"):
    from services.lifeops_discord_adapter import LifeOpsDiscordAdapter
    return LifeOpsDiscordAdapter(
        client=client or _make_client(),
        away_mode=away_mode or _make_away_mode(),
        todo_store=todo_store or _make_todo_store_with_open(),
        channel_id=channel_id,
    )


# ---------------------------------------------------------------------------
# Idle-day config — both DISCORD_NUDGE_IDLE_HOUR and DISCORD_NUDGE_IDLE_MINUTE required
# ---------------------------------------------------------------------------


class TestIdleDayNudgeConfig:
    def test_disabled_when_hour_unset(self, monkeypatch):
        """AC: DISCORD_NUDGE_IDLE_HOUR unset → scheduler disabled."""
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_minute_unset(self, monkeypatch):
        """AC: DISCORD_NUDGE_IDLE_MINUTE unset → scheduler disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_both_unset(self, monkeypatch):
        """AC: Both unset → scheduler disabled."""
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is False

    def test_enabled_when_both_set(self, monkeypatch):
        """AC: Both set with valid integers → scheduler enabled."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "30")
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is True
        assert cfg["hour"] == 21
        assert cfg["minute"] == 30

    def test_disabled_when_hour_non_integer(self, monkeypatch):
        """AC: Non-integer DISCORD_NUDGE_IDLE_HOUR → disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "evening")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_minute_non_integer(self, monkeypatch):
        """AC: Non-integer DISCORD_NUDGE_IDLE_MINUTE → disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "half")
        from services.lifeops_discord_adapter import _read_idle_day_nudge_config
        cfg = _read_idle_day_nudge_config()
        assert cfg["enabled"] is False


# ---------------------------------------------------------------------------
# Idle-day scheduler lifecycle
# ---------------------------------------------------------------------------


class TestIdleDaySchedulerLifecycle:
    def test_scheduler_not_started_when_hour_missing(self, monkeypatch):
        """AC: If DISCORD_NUDGE_IDLE_HOUR unset, _start_idle_day_nudge_scheduler is a no-op."""
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        adapter = _make_adapter_for_idle()
        adapter._start_idle_day_nudge_scheduler()
        assert adapter._idle_task is None

    def test_idle_task_initialized_to_none(self):
        """AC: _idle_task is None on construction."""
        adapter = _make_adapter_for_idle()
        assert adapter._idle_task is None

    @pytest.mark.asyncio
    async def test_scheduler_creates_task_when_both_env_vars_set(self, monkeypatch):
        """AC: _start_idle_day_nudge_scheduler creates a task when both vars are set."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        adapter = _make_adapter_for_idle()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_idle_day_nudge_scheduler_loop", fake_loop):
            adapter._start_idle_day_nudge_scheduler()
            assert adapter._idle_task is not None
            adapter._idle_task.cancel()
            try:
                await adapter._idle_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, monkeypatch):
        """AC: Calling _start_idle_day_nudge_scheduler twice creates only one task."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        adapter = _make_adapter_for_idle()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_idle_day_nudge_scheduler_loop", fake_loop):
            adapter._start_idle_day_nudge_scheduler()
            first_task = adapter._idle_task
            adapter._start_idle_day_nudge_scheduler()
            assert adapter._idle_task is first_task
            first_task.cancel()
            try:
                await first_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cancel_clears_idle_task(self, monkeypatch):
        """AC: _cancel_idle_day_nudge_task() cancels and clears _idle_task."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        adapter = _make_adapter_for_idle()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_idle_day_nudge_scheduler_loop", fake_loop):
            adapter._start_idle_day_nudge_scheduler()
            assert adapter._idle_task is not None
            await adapter._cancel_idle_day_nudge_task()
            assert adapter._idle_task is None

    @pytest.mark.asyncio
    async def test_loop_sleeps_positive_delay(self, monkeypatch):
        """AC: The loop sleeps a positive delay ≤ 86400s before firing."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "30")

        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)
            raise asyncio.CancelledError()

        adapter = _make_adapter_for_idle()
        cfg = {"hour": 21, "minute": 30}

        with patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await adapter._idle_day_nudge_scheduler_loop(cfg)
            except asyncio.CancelledError:
                pass

        assert len(sleep_calls) == 1
        assert 0 < sleep_calls[0] <= 86400


# ---------------------------------------------------------------------------
# _fire_idle_day_nudge skip conditions
# ---------------------------------------------------------------------------


class TestIdleDayNudgeFireSkipConditions:
    @pytest.mark.asyncio
    async def test_skip_when_away(self):
        """AC: away_mode active → no post."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        away_mode = _make_away_mode(is_away=True)
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=0)
        adapter = _make_adapter_for_idle(client=client, away_mode=away_mode, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_away_does_not_call_count_closed(self):
        """AC: count_todos_closed_today() is not called when away."""
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=0)
        away_mode = _make_away_mode(is_away=True)
        adapter = _make_adapter_for_idle(away_mode=away_mode, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        store.count_todos_closed_today.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_todos_closed_today(self):
        """AC: count_todos_closed_today() > 0 → no post."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=1)
        adapter = _make_adapter_for_idle(client=client, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_open_todos_empty(self):
        """AC: get_open_todos() returns [] → no post."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_with_open(open_todos=[], closed_today=0)
        adapter = _make_adapter_for_idle(client=client, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# _fire_idle_day_nudge success path
# ---------------------------------------------------------------------------


class TestIdleDayNudgeFireSuccess:
    @pytest.mark.asyncio
    async def test_posts_correct_message(self):
        """AC: Posts exactly "Haven't touched your list today — want to review it?"."""
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=0)
        adapter = _make_adapter_for_idle(client=client, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        channel.send.assert_awaited_once()
        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert content == "Haven't touched your list today — want to review it?"

    @pytest.mark.asyncio
    async def test_posts_with_todo_closure_view(self):
        """AC: Message is sent with a TodoClosureView as 'view'."""
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=0)
        adapter = _make_adapter_for_idle(client=client, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        _, kwargs = channel.send.call_args
        assert isinstance(kwargs.get("view"), TodoClosureView)

    @pytest.mark.asyncio
    async def test_todo_closure_view_receives_open_todos(self):
        """AC: TodoClosureView is populated with the current open todos."""
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        open_todos = [_make_todo("o1"), _make_todo("o2")]
        store = _make_todo_store_with_open(open_todos=open_todos, closed_today=0)
        adapter = _make_adapter_for_idle(client=client, todo_store=store)
        await adapter._fire_idle_day_nudge({})
        _, kwargs = channel.send.call_args
        view = kwargs.get("view")
        assert isinstance(view, TodoClosureView)
        assert view.todos == open_todos

    @pytest.mark.asyncio
    async def test_calls_get_open_todos_not_get_stale_todos(self):
        """AC: Uses get_open_todos() (not get_stale_todos()) for the view payload."""
        store = _make_todo_store_with_open(open_todos=[_make_todo()], closed_today=0)
        adapter = _make_adapter_for_idle(todo_store=store)
        await adapter._fire_idle_day_nudge({})
        store.get_open_todos.assert_called_once()
        store.get_stale_todos.assert_not_called()


# ---------------------------------------------------------------------------
# Method names for idle-day scheduler
# ---------------------------------------------------------------------------


class TestIdleDaySchedulerMethodNames:
    def test_has_start_idle_method(self):
        """AC: LifeOpsDiscordAdapter has _start_idle_day_nudge_scheduler."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "_start_idle_day_nudge_scheduler", None))

    def test_has_loop_idle_method(self):
        """AC: LifeOpsDiscordAdapter has _idle_day_nudge_scheduler_loop."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "_idle_day_nudge_scheduler_loop", None))

    def test_has_fire_idle_method(self):
        """AC: LifeOpsDiscordAdapter has _fire_idle_day_nudge."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "_fire_idle_day_nudge", None))

    def test_has_cancel_idle_method(self):
        """AC: LifeOpsDiscordAdapter has _cancel_idle_day_nudge_task."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "_cancel_idle_day_nudge_task", None))


# ---------------------------------------------------------------------------
# Lifecycle wiring: _run_post_connect_initialization / cancel_background_tasks
# ---------------------------------------------------------------------------


class TestLifecycleWiring:
    def test_has_run_post_connect_initialization(self):
        """AC: LifeOpsDiscordAdapter has _run_post_connect_initialization."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "_run_post_connect_initialization", None))

    def test_has_cancel_background_tasks(self):
        """AC: LifeOpsDiscordAdapter has cancel_background_tasks."""
        adapter = _make_adapter_for_idle()
        assert callable(getattr(adapter, "cancel_background_tasks", None))

    def test_run_post_connect_starts_idle_scheduler(self, monkeypatch):
        """AC: _run_post_connect_initialization calls _start_idle_day_nudge_scheduler."""
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        adapter = _make_adapter_for_idle()
        called = []
        original = adapter._start_idle_day_nudge_scheduler
        adapter._start_idle_day_nudge_scheduler = lambda: called.append("idle")
        adapter._start_stale_todo_nudge_scheduler = lambda: called.append("stale")
        adapter._run_post_connect_initialization()
        assert "idle" in called

    def test_run_post_connect_starts_stale_scheduler(self, monkeypatch):
        """AC: _run_post_connect_initialization also calls _start_stale_todo_nudge_scheduler."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        adapter = _make_adapter_for_idle()
        called = []
        adapter._start_idle_day_nudge_scheduler = lambda: called.append("idle")
        adapter._start_stale_todo_nudge_scheduler = lambda: called.append("stale")
        adapter._run_post_connect_initialization()
        assert "stale" in called

    @pytest.mark.asyncio
    async def test_cancel_background_tasks_cancels_idle(self, monkeypatch):
        """AC: cancel_background_tasks cancels the idle-day task."""
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "21")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        adapter = _make_adapter_for_idle()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_idle_day_nudge_scheduler_loop", fake_loop):
            adapter._start_idle_day_nudge_scheduler()
            assert adapter._idle_task is not None
            await adapter.cancel_background_tasks()
            assert adapter._idle_task is None


# ===========================================================================
# Issue #51 — Weekly reset nudge scheduler
# ===========================================================================


def _make_todo_store_weekly(open_todos=None):
    m = MagicMock()
    m.get_open_todos.return_value = open_todos if open_todos is not None else []
    return m


def _make_adapter_weekly(client=None, away_mode=None, todo_store=None, channel_id="12345"):
    from services.lifeops_discord_adapter import LifeOpsDiscordAdapter
    return LifeOpsDiscordAdapter(
        client=client or _make_client(),
        away_mode=away_mode or _make_away_mode(),
        todo_store=todo_store or _make_todo_store_weekly(),
        channel_id=channel_id,
    )


# ---------------------------------------------------------------------------
# AC2/AC3 — _read_weekly_nudge_config
# ---------------------------------------------------------------------------


class TestWeeklyNudgeConfig:
    def test_disabled_when_all_unset(self, monkeypatch):
        """AC3: All three env vars unset → disabled."""
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_DAY", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_only_day_set(self, monkeypatch):
        """AC3/UAT6: Only DAY set, hour+minute unset → disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_DAY", "0")
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_hour_missing(self, monkeypatch):
        """AC3: HOUR unset → disabled even with MINUTE and DAY."""
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_DAY", "6")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_when_minute_missing(self, monkeypatch):
        """AC3: MINUTE unset → disabled even with HOUR and DAY."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_DAY", "6")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False

    def test_enabled_when_hour_and_minute_set(self, monkeypatch):
        """AC2: HOUR and MINUTE set → enabled with default day=6."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_DAY", raising=False)
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is True
        assert cfg["day"] == 6
        assert cfg["hour"] == 20
        assert cfg["minute"] == 0

    def test_custom_day_parsed(self, monkeypatch):
        """AC2: Custom DISCORD_NUDGE_WEEKLY_DAY is parsed correctly."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_DAY", "0")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "9")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "30")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is True
        assert cfg["day"] == 0
        assert cfg["hour"] == 9
        assert cfg["minute"] == 30

    def test_day_defaults_to_6_on_bad_value(self, monkeypatch):
        """AC2: Non-integer DISCORD_NUDGE_WEEKLY_DAY falls back to 6."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_DAY", "sunday")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is True
        assert cfg["day"] == 6

    def test_disabled_on_non_integer_hour(self, monkeypatch):
        """AC2: Non-integer DISCORD_NUDGE_WEEKLY_HOUR → disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "evening")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False

    def test_disabled_on_non_integer_minute(self, monkeypatch):
        """AC2: Non-integer DISCORD_NUDGE_WEEKLY_MINUTE → disabled."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "half")
        from services.lifeops_discord_adapter import _read_weekly_nudge_config
        cfg = _read_weekly_nudge_config()
        assert cfg["enabled"] is False


# ---------------------------------------------------------------------------
# AC1 — Scheduler lifecycle: start / idempotent / cancel
# ---------------------------------------------------------------------------


class TestWeeklySchedulerLifecycle:
    def test_not_started_when_disabled(self, monkeypatch):
        """AC1/AC3: Scheduler not started when config disabled."""
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)
        adapter = _make_adapter_weekly()
        adapter._start_weekly_nudge_scheduler()
        assert adapter._weekly_task is None

    def test_weekly_task_initialized_to_none(self):
        """AC1: _weekly_task is None on construction."""
        adapter = _make_adapter_weekly()
        assert adapter._weekly_task is None

    @pytest.mark.asyncio
    async def test_creates_task_when_enabled(self, monkeypatch):
        """AC1: _start_weekly_nudge_scheduler creates a task when HOUR+MINUTE set."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        adapter = _make_adapter_weekly()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_weekly_nudge_scheduler_loop", fake_loop):
            adapter._start_weekly_nudge_scheduler()
            assert adapter._weekly_task is not None
            adapter._weekly_task.cancel()
            try:
                await adapter._weekly_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, monkeypatch):
        """AC1: Calling _start_weekly_nudge_scheduler twice creates only one task."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        adapter = _make_adapter_weekly()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_weekly_nudge_scheduler_loop", fake_loop):
            adapter._start_weekly_nudge_scheduler()
            first_task = adapter._weekly_task
            adapter._start_weekly_nudge_scheduler()
            assert adapter._weekly_task is first_task
            first_task.cancel()
            try:
                await first_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cancel_clears_weekly_task(self, monkeypatch):
        """AC1: _cancel_weekly_nudge_task() cancels and clears _weekly_task."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        adapter = _make_adapter_weekly()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_weekly_nudge_scheduler_loop", fake_loop):
            adapter._start_weekly_nudge_scheduler()
            assert adapter._weekly_task is not None
            await adapter._cancel_weekly_nudge_task()
            assert adapter._weekly_task is None

    @pytest.mark.asyncio
    async def test_loop_sleeps_positive_delay(self):
        """AC1: The loop sleeps a positive delay ≤ 86400s before firing."""
        sleep_calls = []

        async def fake_sleep(delay):
            sleep_calls.append(delay)
            raise asyncio.CancelledError()

        adapter = _make_adapter_weekly()
        cfg = {"day": 6, "hour": 20, "minute": 0}

        with patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await adapter._weekly_nudge_scheduler_loop(cfg)
            except asyncio.CancelledError:
                pass

        assert len(sleep_calls) == 1
        assert 0 < sleep_calls[0] <= 86400


# ---------------------------------------------------------------------------
# AC7 — away_mode suppresses message
# ---------------------------------------------------------------------------


class TestWeeklyNudgeAwayMode:
    @pytest.mark.asyncio
    async def test_no_send_when_away(self):
        """AC7: No message when away_mode.is_away() is True."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        away_mode = _make_away_mode(is_away=True)
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        adapter = _make_adapter_weekly(client=client, away_mode=away_mode, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)  # Sunday = weekday 6
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)
        channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_open_todos_not_called_when_away(self):
        """AC7: get_open_todos() is not called when away."""
        import datetime
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        away_mode = _make_away_mode(is_away=True)
        adapter = _make_adapter_weekly(away_mode=away_mode, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)  # Sunday = weekday 6
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)
        store.get_open_todos.assert_not_called()


# ---------------------------------------------------------------------------
# AC6 — empty open list suppresses message
# ---------------------------------------------------------------------------


class TestWeeklyNudgeEmptyList:
    @pytest.mark.asyncio
    async def test_no_send_when_open_todos_empty(self):
        """AC6: No message when get_open_todos() returns []."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_weekly(open_todos=[])
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)  # Sunday = weekday 6
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)
        channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# AC4 — weekday gate: fires only on configured day
# ---------------------------------------------------------------------------


class TestWeeklyNudgeWeekdayGate:
    @pytest.mark.asyncio
    async def test_fires_on_matching_weekday(self):
        """AC4: Message is posted when weekday matches cfg['day']."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        # 2026-07-19 is a Sunday (weekday=6)
        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)
        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_suppressed_on_non_matching_weekday(self):
        """AC4: Message is NOT posted when weekday does not match cfg['day']."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        # 2026-07-18 is a Saturday (weekday=5), configured for Sunday (6)
        fixed_dt = datetime.datetime(2026, 7, 18, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)
        channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# AC8 — frozen datetime for all 7 days: fires only on configured day
# ---------------------------------------------------------------------------


class TestWeeklyNudgeFrozenDatetimeAllDays:
    """AC8: For each weekday 0–6, assert fires only on the matching day."""

    # Map weekday → a fixed datetime on that day in July 2026
    # 2026-07-13=Monday(0), 14=Tue(1), 15=Wed(2), 16=Thu(3), 17=Fri(4), 18=Sat(5), 19=Sun(6)
    _WEEKDAY_DATES = {
        0: "2026-07-13",
        1: "2026-07-14",
        2: "2026-07-15",
        3: "2026-07-16",
        4: "2026-07-17",
        5: "2026-07-18",
        6: "2026-07-19",
    }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("configured_day", range(7))
    async def test_fires_only_on_configured_day(self, configured_day):
        """AC8: With configured_day=N, fires only when frozen weekday==N."""
        import datetime
        cfg = {"day": configured_day, "hour": 20, "minute": 0}

        for weekday, date_str in self._WEEKDAY_DATES.items():
            channel = _make_channel()
            client = _make_client(channel=channel)
            store = _make_todo_store_weekly(open_todos=[_make_todo()])
            adapter = _make_adapter_weekly(client=client, todo_store=store)

            fixed_dt = datetime.datetime.fromisoformat(f"{date_str} 20:00:00")

            with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = fixed_dt
                await adapter._fire_weekly_nudge(cfg)

            if weekday == configured_day:
                channel.send.assert_awaited_once(), (
                    f"Expected send on weekday {weekday} (configured={configured_day})"
                )
            else:
                channel.send.assert_not_called(), (
                    f"Expected no send on weekday {weekday} (configured={configured_day})"
                )


# ---------------------------------------------------------------------------
# AC5 — message format and TodoClosureView
# ---------------------------------------------------------------------------


class TestWeeklyNudgeMessageFormat:
    @pytest.mark.asyncio
    async def test_message_starts_with_weekly_reset(self):
        """AC5: Message starts with 'Weekly reset — {open_count} open todo(s)'."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("t1"), _make_todo("t2"), _make_todo("t3")]
        store = _make_todo_store_weekly(open_todos=todos)
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert content.startswith("Weekly reset —"), f"Got: {content!r}"

    @pytest.mark.asyncio
    async def test_message_includes_open_count(self):
        """AC5: Message includes correct open todo count."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("t1"), _make_todo("t2")]
        store = _make_todo_store_weekly(open_todos=todos)
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert "2 open todo(s)" in content

    @pytest.mark.asyncio
    async def test_message_exact_format(self):
        """AC5: Exact message format: 'Weekly reset — {n} open todo(s)'."""
        import datetime
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("t1")]
        store = _make_todo_store_weekly(open_todos=todos)
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        args, kwargs = channel.send.call_args
        content = args[0] if args else kwargs.get("content", "")
        assert content == "Weekly reset — 1 open todo(s)"

    @pytest.mark.asyncio
    async def test_sends_with_todo_closure_view(self):
        """AC5: Message is sent with a TodoClosureView as 'view' kwarg."""
        import datetime
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        _, kwargs = channel.send.call_args
        assert isinstance(kwargs.get("view"), TodoClosureView)

    @pytest.mark.asyncio
    async def test_todo_closure_view_receives_open_todos(self):
        """AC5: TodoClosureView is built from get_open_todos()."""
        import datetime
        from services.lifeops_discord_adapter import TodoClosureView
        channel = _make_channel()
        client = _make_client(channel=channel)
        todos = [_make_todo("w1"), _make_todo("w2")]
        store = _make_todo_store_weekly(open_todos=todos)
        adapter = _make_adapter_weekly(client=client, todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        _, kwargs = channel.send.call_args
        view = kwargs.get("view")
        assert isinstance(view, TodoClosureView)
        assert view.todos == todos

    @pytest.mark.asyncio
    async def test_uses_get_open_todos_not_get_stale(self):
        """AC5/AC9: Uses get_open_todos(), never get_stale_todos()."""
        import datetime
        store = _make_todo_store_weekly(open_todos=[_make_todo()])
        adapter = _make_adapter_weekly(todo_store=store)

        fixed_dt = datetime.datetime(2026, 7, 19, 20, 0, 0)
        cfg = {"day": 6, "hour": 20, "minute": 0}
        with patch("services.lifeops_discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = fixed_dt
            await adapter._fire_weekly_nudge(cfg)

        store.get_open_todos.assert_called_once()
        store.get_stale_todos.assert_not_called()


# ---------------------------------------------------------------------------
# AC1 — Method names / presence
# ---------------------------------------------------------------------------


class TestWeeklySchedulerMethodNames:
    def test_has_start_method(self):
        """AC1: LifeOpsDiscordAdapter has _start_weekly_nudge_scheduler."""
        adapter = _make_adapter_weekly()
        assert callable(getattr(adapter, "_start_weekly_nudge_scheduler", None))

    def test_has_loop_method(self):
        """AC1: LifeOpsDiscordAdapter has _weekly_nudge_scheduler_loop."""
        adapter = _make_adapter_weekly()
        assert callable(getattr(adapter, "_weekly_nudge_scheduler_loop", None))

    def test_has_fire_method(self):
        """AC1: LifeOpsDiscordAdapter has _fire_weekly_nudge."""
        adapter = _make_adapter_weekly()
        assert callable(getattr(adapter, "_fire_weekly_nudge", None))

    def test_has_cancel_method(self):
        """AC1: LifeOpsDiscordAdapter has _cancel_weekly_nudge_task."""
        adapter = _make_adapter_weekly()
        assert callable(getattr(adapter, "_cancel_weekly_nudge_task", None))


# ---------------------------------------------------------------------------
# AC1 — Lifecycle wiring: _run_post_connect_initialization / cancel_background_tasks
# ---------------------------------------------------------------------------


class TestWeeklyLifecycleWiring:
    def test_run_post_connect_starts_weekly_scheduler(self, monkeypatch):
        """AC1: _run_post_connect_initialization calls _start_weekly_nudge_scheduler."""
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        adapter = _make_adapter_weekly()
        called = []
        adapter._start_stale_todo_nudge_scheduler = lambda: None
        adapter._start_idle_day_nudge_scheduler = lambda: None
        adapter._start_weekly_nudge_scheduler = lambda: called.append("weekly")
        adapter._run_post_connect_initialization()
        assert "weekly" in called

    @pytest.mark.asyncio
    async def test_cancel_background_tasks_cancels_weekly(self, monkeypatch):
        """AC1: cancel_background_tasks cancels the weekly task."""
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")
        adapter = _make_adapter_weekly()

        async def fake_loop(cfg):
            await asyncio.sleep(9999)

        with patch.object(adapter, "_weekly_nudge_scheduler_loop", fake_loop):
            adapter._start_weekly_nudge_scheduler()
            assert adapter._weekly_task is not None
            await adapter.cancel_background_tasks()
            assert adapter._weekly_task is None
