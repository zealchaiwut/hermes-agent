"""Tests for issue #67: Add weekly reset nudge scheduler to LifeOpsDiscordAdapter.

Each test is anchored to a specific Acceptance Criterion from the issue.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_adapter():
    from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

    with patch("plugins.platforms.discord.adapter.DiscordAdapter.__init__", lambda self, cfg: None):
        adapter = LifeOpsDiscordAdapter.__new__(LifeOpsDiscordAdapter)
        adapter._client = MagicMock()
        adapter._bedtime_task = None
        adapter._approvals_task = None
        adapter._todo_closure_task = None
        adapter._stale_nudge_task = None
        adapter._idle_nudge_task = None
        adapter._weekly_nudge_task = None
        adapter._allowed_user_ids = set()
        adapter._allowed_role_ids = set()
        platform_mock = MagicMock()
        platform_mock.value = "test"
        adapter.__dict__["platform"] = platform_mock
    return adapter


# ---------------------------------------------------------------------------
# _read_weekly_nudge_config helper
# ---------------------------------------------------------------------------


class TestReadWeeklyNudgeConfig:
    def test_disabled_when_all_vars_unset(self):
        """AC3: When all three env vars are unset, config is disabled."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        env = {k: v for k, v in os.environ.items()
               if k not in ("DISCORD_NUDGE_WEEKLY_DAY", "DISCORD_NUDGE_WEEKLY_HOUR",
                            "DISCORD_NUDGE_WEEKLY_MINUTE")}
        with patch.dict(os.environ, env, clear=True):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is False

    def test_disabled_when_hour_and_minute_unset(self):
        """AC3: Only day set is not enough — hour and minute must also be set."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        env = {k: v for k, v in os.environ.items()
               if k not in ("DISCORD_NUDGE_WEEKLY_DAY", "DISCORD_NUDGE_WEEKLY_HOUR",
                            "DISCORD_NUDGE_WEEKLY_MINUTE")}
        with patch.dict(os.environ, {**env, "DISCORD_NUDGE_WEEKLY_DAY": "6"}, clear=True):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is False

    def test_enabled_when_all_three_set(self):
        """AC2: When all three vars are set, config is enabled with correct values."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        with patch.dict(os.environ, {
            "DISCORD_NUDGE_WEEKLY_DAY": "6",
            "DISCORD_NUDGE_WEEKLY_HOUR": "10",
            "DISCORD_NUDGE_WEEKLY_MINUTE": "30",
        }):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is True
        assert cfg["day"] == 6
        assert cfg["hour"] == 10
        assert cfg["minute"] == 30

    def test_day_defaults_to_6_when_unset(self):
        """AC2: DISCORD_NUDGE_WEEKLY_DAY defaults to 6 (Sunday) when unset."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        env = {k: v for k, v in os.environ.items()
               if k not in ("DISCORD_NUDGE_WEEKLY_DAY", "DISCORD_NUDGE_WEEKLY_HOUR",
                            "DISCORD_NUDGE_WEEKLY_MINUTE")}
        with patch.dict(os.environ, {
            **env,
            "DISCORD_NUDGE_WEEKLY_HOUR": "10",
            "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
        }, clear=True):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is True
        assert cfg["day"] == 6

    def test_disabled_on_invalid_hour(self):
        """AC2: Invalid DISCORD_NUDGE_WEEKLY_HOUR yields disabled config."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        with patch.dict(os.environ, {
            "DISCORD_NUDGE_WEEKLY_DAY": "6",
            "DISCORD_NUDGE_WEEKLY_HOUR": "not-a-number",
            "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
        }):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is False

    def test_minute_defaults_to_0_when_unset(self):
        """AC2: DISCORD_NUDGE_WEEKLY_MINUTE defaults to 0 when unset."""
        from plugins.life_ops.discord_adapter import _read_weekly_nudge_config

        env = {k: v for k, v in os.environ.items()
               if k not in ("DISCORD_NUDGE_WEEKLY_DAY", "DISCORD_NUDGE_WEEKLY_HOUR",
                            "DISCORD_NUDGE_WEEKLY_MINUTE")}
        with patch.dict(os.environ, {
            **env,
            "DISCORD_NUDGE_WEEKLY_HOUR": "10",
        }, clear=True):
            cfg = _read_weekly_nudge_config()

        assert cfg["enabled"] is True
        assert cfg["minute"] == 0


# ---------------------------------------------------------------------------
# AC3: scheduler does not start when env vars are unset
# ---------------------------------------------------------------------------


class TestSchedulerDisabledByDefault:
    def test_no_task_created_when_all_vars_unset(self):
        """AC3: When no env vars are set, no task is created."""
        adapter = _make_adapter()
        env = {k: v for k, v in os.environ.items()
               if k not in ("DISCORD_NUDGE_WEEKLY_DAY", "DISCORD_NUDGE_WEEKLY_HOUR",
                            "DISCORD_NUDGE_WEEKLY_MINUTE")}
        with patch.dict(os.environ, env, clear=True):
            adapter._start_weekly_nudge_scheduler()

        assert adapter._weekly_nudge_task is None


# ---------------------------------------------------------------------------
# AC1: scheduler is registered following the same lifecycle pattern
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    def test_task_created_when_configured(self):
        """AC1: When env vars are set, _weekly_nudge_task is created."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(os.environ, {
                "DISCORD_NUDGE_WEEKLY_DAY": "6",
                "DISCORD_NUDGE_WEEKLY_HOUR": "10",
                "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
            }):
                adapter._start_weekly_nudge_scheduler()
                assert adapter._weekly_nudge_task is not None
                assert not adapter._weekly_nudge_task.done()
                adapter._weekly_nudge_task.cancel()
                try:
                    await adapter._weekly_nudge_task
                except asyncio.CancelledError:
                    pass

        _run(_check())

    def test_start_is_idempotent(self):
        """AC1: A second _start_weekly_nudge_scheduler call while running is a no-op."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(os.environ, {
                "DISCORD_NUDGE_WEEKLY_DAY": "6",
                "DISCORD_NUDGE_WEEKLY_HOUR": "10",
                "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
            }):
                adapter._start_weekly_nudge_scheduler()
                task_first = adapter._weekly_nudge_task
                adapter._start_weekly_nudge_scheduler()
                task_second = adapter._weekly_nudge_task
                assert task_first is task_second
                task_first.cancel()
                try:
                    await task_first
                except asyncio.CancelledError:
                    pass

        _run(_check())

    def test_cancel_task_cleans_up(self):
        """AC1: _cancel_weekly_nudge_task cancels and clears the task."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(os.environ, {
                "DISCORD_NUDGE_WEEKLY_DAY": "6",
                "DISCORD_NUDGE_WEEKLY_HOUR": "10",
                "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
            }):
                adapter._start_weekly_nudge_scheduler()
                assert adapter._weekly_nudge_task is not None
                await adapter._cancel_weekly_nudge_task()

            assert adapter._weekly_nudge_task is None

        _run(_check())

    def test_cancel_noop_when_no_task(self):
        """AC1: _cancel_weekly_nudge_task is safe when no task exists."""
        adapter = _make_adapter()
        adapter._weekly_nudge_task = None

        async def _check():
            await adapter._cancel_weekly_nudge_task()

        _run(_check())
        assert adapter._weekly_nudge_task is None

    def test_cancel_background_tasks_includes_weekly_nudge(self):
        """AC1: cancel_background_tasks() also cancels the weekly nudge task."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(os.environ, {
                "DISCORD_NUDGE_WEEKLY_DAY": "6",
                "DISCORD_NUDGE_WEEKLY_HOUR": "10",
                "DISCORD_NUDGE_WEEKLY_MINUTE": "0",
            }):
                adapter._start_weekly_nudge_scheduler()
                assert adapter._weekly_nudge_task is not None

            with patch("plugins.platforms.discord.adapter.DiscordAdapter.cancel_background_tasks",
                       new_callable=AsyncMock):
                await adapter.cancel_background_tasks()

            assert adapter._weekly_nudge_task is None

        _run(_check())

    def test_post_connect_starts_weekly_nudge_scheduler(self):
        """AC1: _run_post_connect_initialization calls _start_weekly_nudge_scheduler."""
        adapter = _make_adapter()

        async def _check():
            with patch.object(adapter, "_start_bedtime_scheduler"), \
                 patch.object(adapter, "_start_approvals_scheduler"), \
                 patch.object(adapter, "_start_todo_closure_scheduler"), \
                 patch.object(adapter, "_start_stale_todo_nudge_scheduler"), \
                 patch.object(adapter, "_start_idle_day_nudge_scheduler"), \
                 patch.object(adapter, "_start_weekly_nudge_scheduler") as mock_start, \
                 patch("plugins.platforms.discord.adapter.DiscordAdapter._run_post_connect_initialization",
                       new_callable=AsyncMock):
                await adapter._run_post_connect_initialization()

            mock_start.assert_called_once()

        _run(_check())


# ---------------------------------------------------------------------------
# AC4: correct day fires → post sent
# ---------------------------------------------------------------------------


def _make_frozen_utc(weekday: int, hour: int = 10, minute: int = 0):
    """Return a datetime-like mock whose weekday() returns `weekday`."""
    import datetime

    # Find a real date with the desired weekday
    base = datetime.datetime(2026, 7, 20, hour, minute, 0,
                              tzinfo=datetime.timezone.utc)  # 2026-07-20 is a Monday (0)
    delta = (weekday - base.weekday()) % 7
    target = base + datetime.timedelta(days=delta)
    return target


class TestFireOnCorrectDay:
    def test_correct_day_posts_message(self):
        """AC4 + AC7: When configured day matches today, a message is posted."""
        adapter = _make_adapter()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=MagicMock(id=123))
        adapter._client.get_channel = MagicMock(return_value=channel)

        frozen = _make_frozen_utc(weekday=6)  # Sunday

        open_todos = [{"key": "T-1", "text": "do something", "priority": "normal"}]

        async def _check():
            with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                       return_value="999"), \
                 patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
                 patch("plugins.life_ops.away_mode.is_away", return_value=False), \
                 patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
                 patch("plugins.life_ops.discord_adapter.TodoClosureView",
                       return_value=MagicMock()), \
                 patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = frozen
                mock_dt.timezone = __import__("datetime").timezone
                mock_dt.timedelta = __import__("datetime").timedelta
                await adapter._fire_weekly_nudge(day=6)

        _run(_check())
        channel.send.assert_called_once()

    def test_wrong_day_no_post(self):
        """AC4: When configured day does NOT match today, no message is posted."""
        adapter = _make_adapter()
        channel = MagicMock()
        channel.send = AsyncMock()
        adapter._client.get_channel = MagicMock(return_value=channel)

        frozen = _make_frozen_utc(weekday=0)  # Monday

        open_todos = [{"key": "T-1", "text": "do something", "priority": "normal"}]

        async def _check():
            with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                       return_value="999"), \
                 patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
                 patch("plugins.life_ops.away_mode.is_away", return_value=False), \
                 patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
                 patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = frozen
                mock_dt.timezone = __import__("datetime").timezone
                mock_dt.timedelta = __import__("datetime").timedelta
                await adapter._fire_weekly_nudge(day=6)  # expecting Sunday, got Monday

        _run(_check())
        channel.send.assert_not_called()

    def test_each_weekday_0_through_6_matches_correctly(self):
        """AC8: All seven weekday values (0–6) are matched correctly."""
        import datetime

        async def _run_check(configured_day: int, current_weekday: int, should_post: bool):
            adapter = _make_adapter()
            channel = MagicMock()
            channel.send = AsyncMock(return_value=MagicMock(id=1))
            adapter._client.get_channel = MagicMock(return_value=channel)

            frozen = _make_frozen_utc(weekday=current_weekday)
            open_todos = [{"key": "T-1", "text": "t", "priority": "normal"}]

            with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                       return_value="999"), \
                 patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
                 patch("plugins.life_ops.away_mode.is_away", return_value=False), \
                 patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
                 patch("plugins.life_ops.discord_adapter.TodoClosureView",
                       return_value=MagicMock()), \
                 patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = frozen
                mock_dt.timezone = __import__("datetime").timezone
                mock_dt.timedelta = __import__("datetime").timedelta
                await adapter._fire_weekly_nudge(day=configured_day)

            if should_post:
                channel.send.assert_called_once(), \
                    f"day={configured_day} current={current_weekday}: expected post"
            else:
                channel.send.assert_not_called(), \
                    f"day={configured_day} current={current_weekday}: expected no post"

        loop = asyncio.get_event_loop()
        for day in range(7):
            for current in range(7):
                loop.run_until_complete(_run_check(day, current, should_post=(day == current)))


# ---------------------------------------------------------------------------
# AC5: away_mode active → no post
# ---------------------------------------------------------------------------


def test_away_mode_suppresses_weekly_nudge():
    """AC5: When is_away() returns True, no message is posted."""
    adapter = _make_adapter()
    channel = MagicMock()
    channel.send = AsyncMock()
    adapter._client.get_channel = MagicMock(return_value=channel)

    frozen = _make_frozen_utc(weekday=6)  # Sunday — matches configured day
    open_todos = [{"key": "T-1", "text": "something", "priority": "normal"}]

    async def _check():
        with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                   return_value="999"), \
             patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
             patch("plugins.life_ops.away_mode.is_away", return_value=True), \
             patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
             patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = frozen
            mock_dt.timezone = __import__("datetime").timezone
            mock_dt.timedelta = __import__("datetime").timedelta
            await adapter._fire_weekly_nudge(day=6)

    _run(_check())
    channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# AC6: zero open todos → no post
# ---------------------------------------------------------------------------


def test_zero_open_todos_no_post():
    """AC6: When get_open_todos() returns [], no message is posted."""
    adapter = _make_adapter()
    channel = MagicMock()
    channel.send = AsyncMock()
    adapter._client.get_channel = MagicMock(return_value=channel)

    frozen = _make_frozen_utc(weekday=6)

    async def _check():
        with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                   return_value="999"), \
             patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
             patch("plugins.life_ops.away_mode.is_away", return_value=False), \
             patch("plugins.life_ops.todo_store.get_open_todos", return_value=[]), \
             patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = frozen
            mock_dt.timezone = __import__("datetime").timezone
            mock_dt.timedelta = __import__("datetime").timedelta
            await adapter._fire_weekly_nudge(day=6)

    _run(_check())
    channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# AC7: message format — "Weekly reset — {count} open todo(s)"
# ---------------------------------------------------------------------------


def test_message_header_format():
    """AC7: Posted message content matches 'Weekly reset — N open todo(s)' exactly."""
    adapter = _make_adapter()
    channel = MagicMock()
    captured_content = []

    async def capture_send(*args, **kwargs):
        content = kwargs.get("content") or (args[0] if args else "")
        captured_content.append(content)
        return MagicMock(id=42)

    channel.send = AsyncMock(side_effect=capture_send)
    adapter._client.get_channel = MagicMock(return_value=channel)

    frozen = _make_frozen_utc(weekday=6)
    open_todos = [
        {"key": "T-1", "text": "todo one", "priority": "normal"},
        {"key": "T-2", "text": "todo two", "priority": "high"},
        {"key": "T-3", "text": "todo three", "priority": "normal"},
    ]

    async def _check():
        with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                   return_value="999"), \
             patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
             patch("plugins.life_ops.away_mode.is_away", return_value=False), \
             patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
             patch("plugins.life_ops.discord_adapter.TodoClosureView",
                   return_value=MagicMock()), \
             patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = frozen
            mock_dt.timezone = __import__("datetime").timezone
            mock_dt.timedelta = __import__("datetime").timedelta
            await adapter._fire_weekly_nudge(day=6)

    _run(_check())

    assert len(captured_content) == 1, "Expected exactly one message"
    msg = captured_content[0]
    assert msg == "Weekly reset — 3 open todo(s)", \
        f"Expected exact header format, got: {msg!r}"


def test_message_includes_todo_closure_view():
    """AC7: Posted message includes a view= kwarg containing a TodoClosureView."""
    adapter = _make_adapter()
    channel = MagicMock()
    channel.send = AsyncMock(return_value=MagicMock(id=42))
    adapter._client.get_channel = MagicMock(return_value=channel)

    frozen = _make_frozen_utc(weekday=6)
    open_todos = [{"key": "T-1", "text": "something", "priority": "normal"}]

    async def _check():
        with patch("plugins.life_ops.discord_adapter._read_morning_brief_channel_id",
                   return_value="999"), \
             patch("plugins.life_ops.discord_adapter._ensure_view_classes", return_value=True), \
             patch("plugins.life_ops.away_mode.is_away", return_value=False), \
             patch("plugins.life_ops.todo_store.get_open_todos", return_value=open_todos), \
             patch("plugins.life_ops.discord_adapter.TodoClosureView") as mock_view_cls, \
             patch("plugins.life_ops.discord_adapter.datetime") as mock_dt:
            mock_view_cls.return_value = MagicMock()
            mock_dt.datetime.now.return_value = frozen
            mock_dt.timezone = __import__("datetime").timezone
            mock_dt.timedelta = __import__("datetime").timedelta
            await adapter._fire_weekly_nudge(day=6)

    _run(_check())

    channel.send.assert_called_once()
    call_kwargs = channel.send.call_args[1]
    assert "view" in call_kwargs, "Message must include a view= kwarg"


# ---------------------------------------------------------------------------
# No new View class introduced
# ---------------------------------------------------------------------------


def test_no_new_view_class_introduced():
    """Reuse check: TodoClosureView is reused; no new View subclass is added."""
    import plugins.life_ops.discord_adapter as adapter_mod

    known_views = {"JournalApproveView", "BedtimeView", "TodoClosureView"}
    new_views = {
        name for name in dir(adapter_mod)
        if name.endswith("View") and name not in known_views
    }
    assert not new_views, f"Unexpected new View classes introduced: {new_views}"
