"""Tests for issue #68: Wire nudge schedulers and document new env vars.

Each test is anchored to a specific Acceptance Criterion from the issue.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter():
    """Return a LifeOpsDiscordAdapter instance bypassing DiscordAdapter.__init__."""
    from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

    with patch(
        "plugins.platforms.discord.adapter.DiscordAdapter.__init__",
        lambda self, cfg: None,
    ):
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
# AC1: Three new scheduler attributes initialized to None in __init__
# ---------------------------------------------------------------------------


class TestSchedulerAttributeInit:
    def test_stale_nudge_task_initialized_to_none(self):
        """AC1: _stale_nudge_task (stale_todo_scheduler) is None after __init__."""
        from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

        with patch(
            "plugins.platforms.discord.adapter.DiscordAdapter.__init__",
            lambda self, cfg: None,
        ):
            adapter = LifeOpsDiscordAdapter.__new__(LifeOpsDiscordAdapter)
            LifeOpsDiscordAdapter.__init__(adapter, {})

        assert hasattr(adapter, "_stale_nudge_task"), (
            "_stale_nudge_task must be initialized in __init__"
        )
        assert adapter._stale_nudge_task is None

    def test_idle_nudge_task_initialized_to_none(self):
        """AC1: _idle_nudge_task (idle_checkin_scheduler) is None after __init__."""
        from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

        with patch(
            "plugins.platforms.discord.adapter.DiscordAdapter.__init__",
            lambda self, cfg: None,
        ):
            adapter = LifeOpsDiscordAdapter.__new__(LifeOpsDiscordAdapter)
            LifeOpsDiscordAdapter.__init__(adapter, {})

        assert hasattr(adapter, "_idle_nudge_task"), (
            "_idle_nudge_task must be initialized in __init__"
        )
        assert adapter._idle_nudge_task is None

    def test_weekly_nudge_task_initialized_to_none(self):
        """AC1: _weekly_nudge_task (weekly_reset_scheduler) is None after __init__."""
        from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

        with patch(
            "plugins.platforms.discord.adapter.DiscordAdapter.__init__",
            lambda self, cfg: None,
        ):
            adapter = LifeOpsDiscordAdapter.__new__(LifeOpsDiscordAdapter)
            LifeOpsDiscordAdapter.__init__(adapter, {})

        assert hasattr(adapter, "_weekly_nudge_task"), (
            "_weekly_nudge_task must be initialized in __init__"
        )
        assert adapter._weekly_nudge_task is None

    def test_nudge_attrs_adjacent_to_existing_scheduler_attrs(self):
        """AC1: All six scheduler attributes (_bedtime_task, _approvals_task,
        _todo_closure_task, _stale_nudge_task, _idle_nudge_task, _weekly_nudge_task)
        are present after __init__."""
        from plugins.life_ops.discord_adapter import LifeOpsDiscordAdapter

        with patch(
            "plugins.platforms.discord.adapter.DiscordAdapter.__init__",
            lambda self, cfg: None,
        ):
            adapter = LifeOpsDiscordAdapter.__new__(LifeOpsDiscordAdapter)
            LifeOpsDiscordAdapter.__init__(adapter, {})

        for attr in (
            "_bedtime_task",
            "_approvals_task",
            "_todo_closure_task",
            "_stale_nudge_task",
            "_idle_nudge_task",
            "_weekly_nudge_task",
        ):
            assert hasattr(adapter, attr), f"{attr} must be set in __init__"
            assert getattr(adapter, attr) is None, f"{attr} must start as None"


# ---------------------------------------------------------------------------
# AC2: _run_post_connect_initialization starts all three new schedulers
# ---------------------------------------------------------------------------


class TestPostConnectStartsNudgeSchedulers:
    def test_stale_nudge_scheduler_started_in_post_connect(self):
        """AC2: _run_post_connect_initialization calls _start_stale_todo_nudge_scheduler."""
        adapter = _make_adapter()

        async def _check():
            with (
                patch.object(adapter, "_start_bedtime_scheduler"),
                patch.object(adapter, "_start_approvals_scheduler"),
                patch.object(adapter, "_start_todo_closure_scheduler"),
                patch.object(adapter, "_start_stale_todo_nudge_scheduler") as mock_stale,
                patch.object(adapter, "_start_idle_day_nudge_scheduler"),
                patch.object(adapter, "_start_weekly_nudge_scheduler"),
                patch(
                    "plugins.platforms.discord.adapter.DiscordAdapter"
                    "._run_post_connect_initialization",
                    new_callable=AsyncMock,
                ),
            ):
                await adapter._run_post_connect_initialization()
            mock_stale.assert_called_once()

        _run(_check())

    def test_idle_nudge_scheduler_started_in_post_connect(self):
        """AC2: _run_post_connect_initialization calls _start_idle_day_nudge_scheduler."""
        adapter = _make_adapter()

        async def _check():
            with (
                patch.object(adapter, "_start_bedtime_scheduler"),
                patch.object(adapter, "_start_approvals_scheduler"),
                patch.object(adapter, "_start_todo_closure_scheduler"),
                patch.object(adapter, "_start_stale_todo_nudge_scheduler"),
                patch.object(adapter, "_start_idle_day_nudge_scheduler") as mock_idle,
                patch.object(adapter, "_start_weekly_nudge_scheduler"),
                patch(
                    "plugins.platforms.discord.adapter.DiscordAdapter"
                    "._run_post_connect_initialization",
                    new_callable=AsyncMock,
                ),
            ):
                await adapter._run_post_connect_initialization()
            mock_idle.assert_called_once()

        _run(_check())

    def test_weekly_nudge_scheduler_started_in_post_connect(self):
        """AC2: _run_post_connect_initialization calls _start_weekly_nudge_scheduler."""
        adapter = _make_adapter()

        async def _check():
            with (
                patch.object(adapter, "_start_bedtime_scheduler"),
                patch.object(adapter, "_start_approvals_scheduler"),
                patch.object(adapter, "_start_todo_closure_scheduler"),
                patch.object(adapter, "_start_stale_todo_nudge_scheduler"),
                patch.object(adapter, "_start_idle_day_nudge_scheduler"),
                patch.object(adapter, "_start_weekly_nudge_scheduler") as mock_weekly,
                patch(
                    "plugins.platforms.discord.adapter.DiscordAdapter"
                    "._run_post_connect_initialization",
                    new_callable=AsyncMock,
                ),
            ):
                await adapter._run_post_connect_initialization()
            mock_weekly.assert_called_once()

        _run(_check())

    def test_existing_schedulers_also_started(self):
        """AC8: _run_post_connect_initialization still calls all three existing schedulers."""
        adapter = _make_adapter()
        started = {}

        async def _check():
            with (
                patch.object(adapter, "_start_bedtime_scheduler",
                              side_effect=lambda: started.setdefault("bedtime", True)),
                patch.object(adapter, "_start_approvals_scheduler",
                              side_effect=lambda: started.setdefault("approvals", True)),
                patch.object(adapter, "_start_todo_closure_scheduler",
                              side_effect=lambda: started.setdefault("todo_closure", True)),
                patch.object(adapter, "_start_stale_todo_nudge_scheduler"),
                patch.object(adapter, "_start_idle_day_nudge_scheduler"),
                patch.object(adapter, "_start_weekly_nudge_scheduler"),
                patch(
                    "plugins.platforms.discord.adapter.DiscordAdapter"
                    "._run_post_connect_initialization",
                    new_callable=AsyncMock,
                ),
            ):
                await adapter._run_post_connect_initialization()

        _run(_check())
        assert started.get("bedtime"), "bedtime scheduler must still be started"
        assert started.get("approvals"), "approvals scheduler must still be started"
        assert started.get("todo_closure"), "todo-closure scheduler must still be started"


# ---------------------------------------------------------------------------
# AC3: cancel_background_tasks cancels all three new schedulers
# ---------------------------------------------------------------------------


class TestCancelBackgroundTasksCancelsNudges:
    def test_stale_nudge_task_cancelled(self):
        """AC3: cancel_background_tasks cancels _stale_nudge_task."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(
                os.environ,
                {"DISCORD_NUDGE_STALE_HOUR": "9", "DISCORD_NUDGE_STALE_MINUTE": "0"},
            ):
                adapter._start_stale_todo_nudge_scheduler()
                assert adapter._stale_nudge_task is not None
            with patch(
                "plugins.platforms.discord.adapter.DiscordAdapter.cancel_background_tasks",
                new_callable=AsyncMock,
            ):
                await adapter.cancel_background_tasks()
            assert adapter._stale_nudge_task is None

        _run(_check())

    def test_idle_nudge_task_cancelled(self):
        """AC3: cancel_background_tasks cancels _idle_nudge_task."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(
                os.environ,
                {"DISCORD_NUDGE_IDLE_HOUR": "10", "DISCORD_NUDGE_IDLE_MINUTE": "0"},
            ):
                adapter._start_idle_day_nudge_scheduler()
                assert adapter._idle_nudge_task is not None
            with patch(
                "plugins.platforms.discord.adapter.DiscordAdapter.cancel_background_tasks",
                new_callable=AsyncMock,
            ):
                await adapter.cancel_background_tasks()
            assert adapter._idle_nudge_task is None

        _run(_check())

    def test_weekly_nudge_task_cancelled(self):
        """AC3: cancel_background_tasks cancels _weekly_nudge_task."""
        adapter = _make_adapter()

        async def _check():
            with patch.dict(
                os.environ,
                {"DISCORD_NUDGE_WEEKLY_HOUR": "8", "DISCORD_NUDGE_WEEKLY_MINUTE": "0"},
            ):
                adapter._start_weekly_nudge_scheduler()
                assert adapter._weekly_nudge_task is not None
            with patch(
                "plugins.platforms.discord.adapter.DiscordAdapter.cancel_background_tasks",
                new_callable=AsyncMock,
            ):
                await adapter.cancel_background_tasks()
            assert adapter._weekly_nudge_task is None

        _run(_check())

    def test_existing_tasks_also_cancelled(self):
        """AC8: cancel_background_tasks still cancels the three existing schedulers."""
        adapter = _make_adapter()

        cancelled = {}

        async def _check():
            with (
                patch.object(adapter, "_cancel_bedtime_task",
                              new_callable=AsyncMock,
                              side_effect=lambda: cancelled.setdefault("bedtime", True)),
                patch.object(adapter, "_cancel_approvals_task",
                              new_callable=AsyncMock,
                              side_effect=lambda: cancelled.setdefault("approvals", True)),
                patch.object(adapter, "_cancel_todo_closure_task",
                              new_callable=AsyncMock,
                              side_effect=lambda: cancelled.setdefault("todo_closure", True)),
                patch.object(adapter, "_cancel_stale_todo_nudge_task",
                              new_callable=AsyncMock),
                patch.object(adapter, "_cancel_idle_day_nudge_task",
                              new_callable=AsyncMock),
                patch.object(adapter, "_cancel_weekly_nudge_task",
                              new_callable=AsyncMock),
                patch(
                    "plugins.platforms.discord.adapter.DiscordAdapter.cancel_background_tasks",
                    new_callable=AsyncMock,
                ),
            ):
                await adapter.cancel_background_tasks()

        _run(_check())
        assert cancelled.get("bedtime"), "bedtime task must still be cancelled"
        assert cancelled.get("approvals"), "approvals task must still be cancelled"
        assert cancelled.get("todo_closure"), "todo-closure task must still be cancelled"


# ---------------------------------------------------------------------------
# AC4 + AC5 + AC6: README.md "Nudges" section
# ---------------------------------------------------------------------------

_README_PATH = pathlib.Path(__file__).parent.parent / "plugins" / "life_ops" / "README.md"


class TestReadmeNudgesSection:
    def _readme_text(self) -> str:
        return _README_PATH.read_text(encoding="utf-8")

    def test_nudges_section_exists(self):
        """AC4: README.md contains a '## Nudges' section (or 'Nudges' heading)."""
        text = self._readme_text()
        assert "## Nudges" in text or "# Nudges" in text, (
            "README.md must contain a 'Nudges' section heading"
        )

    def test_nudges_section_has_env_var_table(self):
        """AC4: Nudges section contains a Markdown table with env var entries."""
        text = self._readme_text()
        # Markdown tables use | as column separator
        assert "|" in text, "README.md must contain a Markdown table in the Nudges section"

    def test_stale_nudge_env_vars_present(self):
        """AC4: Nudges section covers stale-todo env vars (DISCORD_NUDGE_STALE_HOUR etc.)."""
        text = self._readme_text()
        assert "DISCORD_NUDGE_STALE_HOUR" in text, (
            "README.md must document DISCORD_NUDGE_STALE_HOUR"
        )
        # The companion var is either MINUTE or DAYS — at least one must appear
        assert "DISCORD_NUDGE_STALE_MINUTE" in text or "DISCORD_NUDGE_STALE_DAYS" in text, (
            "README.md must document a companion stale-nudge var"
        )

    def test_idle_nudge_env_vars_present(self):
        """AC4: Nudges section covers idle-day env vars."""
        text = self._readme_text()
        assert "DISCORD_NUDGE_IDLE_HOUR" in text, (
            "README.md must document DISCORD_NUDGE_IDLE_HOUR"
        )
        assert "DISCORD_NUDGE_IDLE_MINUTE" in text, (
            "README.md must document DISCORD_NUDGE_IDLE_MINUTE"
        )

    def test_weekly_nudge_env_vars_present(self):
        """AC4: Nudges section covers weekly-reset env vars."""
        text = self._readme_text()
        assert "DISCORD_NUDGE_WEEKLY_HOUR" in text, (
            "README.md must document DISCORD_NUDGE_WEEKLY_HOUR"
        )
        # Companion is either MINUTE or DAY
        assert "DISCORD_NUDGE_WEEKLY_MINUTE" in text or "DISCORD_NUDGE_WEEKLY_DAY" in text, (
            "README.md must document a companion weekly-nudge var"
        )

    def test_six_new_env_vars_covered(self):
        """AC4: All six new env vars are present (2 per scheduler)."""
        text = self._readme_text()
        six_vars = [
            "DISCORD_NUDGE_STALE_HOUR",
            "DISCORD_NUDGE_STALE_MINUTE",
            "DISCORD_NUDGE_IDLE_HOUR",
            "DISCORD_NUDGE_IDLE_MINUTE",
            "DISCORD_NUDGE_WEEKLY_HOUR",
            "DISCORD_NUDGE_WEEKLY_MINUTE",
        ]
        missing = [v for v in six_vars if v not in text]
        assert not missing, f"README.md is missing env var docs for: {missing}"

    def test_nudges_section_mentions_opt_in(self):
        """AC5: Nudges section states schedulers are opt-in."""
        text = self._readme_text()
        lower = text.lower()
        assert "opt-in" in lower or "opt in" in lower or "disabled unless" in lower or "disabled by default" in lower, (
            "Nudges section must state that schedulers are opt-in"
        )

    def test_nudges_section_mentions_away_mode(self):
        """AC5: Nudges section states schedulers respect away mode."""
        text = self._readme_text()
        lower = text.lower()
        assert "away" in lower, (
            "Nudges section must mention away mode"
        )

    def test_nudges_section_describes_stale_cadence(self):
        """AC6: Nudges section describes stale-todo nudge cadence (daily)."""
        text = self._readme_text()
        lower = text.lower()
        assert "stale" in lower, "Nudges section must describe stale-todo nudge"

    def test_nudges_section_describes_idle_cadence(self):
        """AC6: Nudges section describes idle-day check-in cadence."""
        text = self._readme_text()
        lower = text.lower()
        assert "idle" in lower, "Nudges section must describe idle-day nudge"

    def test_nudges_section_describes_weekly_cadence(self):
        """AC6: Nudges section describes weekly reset nudge cadence."""
        text = self._readme_text()
        lower = text.lower()
        assert "weekly" in lower or "week" in lower, (
            "Nudges section must describe weekly reset nudge"
        )


# ---------------------------------------------------------------------------
# AC7: dig-deeper.md one-liner about nudges + /done /dismiss /snooze
# ---------------------------------------------------------------------------

_DIG_DEEPER_PATH = (
    pathlib.Path(__file__).parent.parent
    / "plugins"
    / "life_ops"
    / "docs"
    / "dig-deeper.md"
)


class TestDigDeeperNudgeMention:
    def test_dig_deeper_mentions_nudges(self):
        """AC7: dig-deeper.md (if it exists) mentions nudges are informational."""
        if not _DIG_DEEPER_PATH.exists():
            pytest.skip("dig-deeper.md does not exist — AC7 does not apply")

        text = _DIG_DEEPER_PATH.read_text(encoding="utf-8")
        lower = text.lower()
        assert "nudge" in lower or "informational" in lower, (
            "dig-deeper.md must contain a one-line mention of nudges"
        )

    def test_dig_deeper_mentions_done_dismiss_snooze(self):
        """AC7: dig-deeper.md mentions /done /dismiss /snooze follow-ups for nudges."""
        if not _DIG_DEEPER_PATH.exists():
            pytest.skip("dig-deeper.md does not exist — AC7 does not apply")

        text = _DIG_DEEPER_PATH.read_text(encoding="utf-8")
        assert "/done" in text or "done" in text.lower(), (
            "dig-deeper.md must mention /done for nudge follow-ups"
        )
        assert "/dismiss" in text or "dismiss" in text.lower(), (
            "dig-deeper.md must mention /dismiss for nudge follow-ups"
        )
        assert "/snooze" in text or "snooze" in text.lower(), (
            "dig-deeper.md must mention /snooze for nudge follow-ups"
        )


# ---------------------------------------------------------------------------
# AC9: No new env vars required for existing schedulers
# ---------------------------------------------------------------------------


class TestExistingSchedulersUnchanged:
    def test_bedtime_config_still_uses_same_env_vars(self):
        """AC9: _read_bedtime_config still uses DISCORD_BEDTIME_HOUR/MINUTE."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "30"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 22
        assert cfg["minute"] == 30

    def test_approvals_config_still_uses_same_env_vars(self):
        """AC9: _read_approvals_config still uses DISCORD_APPROVALS_HOUR/MINUTE."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "8"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 8

    def test_todo_closure_config_still_uses_same_env_vars(self):
        """AC9: _read_todo_closure_config still uses DISCORD_TODO_CLOSURE_HOUR/MINUTE."""
        from plugins.life_ops.discord_adapter import _read_todo_closure_config

        with patch.dict(os.environ, {"DISCORD_TODO_CLOSURE_HOUR": "7"}):
            cfg = _read_todo_closure_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 7
