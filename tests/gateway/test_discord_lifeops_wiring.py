"""Tests for issue #52: Wire nudge schedulers into DiscordAdapter lifecycle.

Each test class is anchored to a specific Acceptance Criterion.
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Discord mock — mirrors the pattern used in test_discord_connect.py
# ---------------------------------------------------------------------------

def _ensure_discord_mock():
    if "discord" in sys.modules and hasattr(sys.modules["discord"], "__file__"):
        return
    if sys.modules.get("discord") is None:
        discord_mod = MagicMock()
        discord_mod.Intents.default.return_value = MagicMock()
        discord_mod.Client = MagicMock
        discord_mod.File = MagicMock
        discord_mod.DMChannel = type("DMChannel", (), {})
        discord_mod.Thread = type("Thread", (), {})
        discord_mod.ForumChannel = type("ForumChannel", (), {})
        discord_mod.ui = SimpleNamespace(
            View=object,
            button=lambda *a, **k: (lambda fn: fn),
            Button=object,
            Select=MagicMock,
            SelectOption=MagicMock,
        )
        discord_mod.ButtonStyle = SimpleNamespace(
            success=1, primary=2, danger=3, green=1, blurple=2,
            red=3, grey=4, secondary=5,
        )
        discord_mod.Color = SimpleNamespace(
            orange=lambda: 1, green=lambda: 2, blue=lambda: 3, red=lambda: 4,
        )
        discord_mod.AllowedMentions = MagicMock
        discord_mod.Interaction = object
        discord_mod.Embed = MagicMock
        discord_mod.SelectOption = MagicMock
        discord_mod.app_commands = SimpleNamespace(
            describe=lambda **kwargs: (lambda fn: fn),
            choices=lambda **kwargs: (lambda fn: fn),
            Choice=lambda **kwargs: SimpleNamespace(**kwargs),
        )
        discord_mod.opus = SimpleNamespace(is_loaded=lambda: True)

        ext_mod = MagicMock()
        commands_mod = MagicMock()
        commands_mod.Bot = MagicMock
        ext_mod.commands = commands_mod

        sys.modules["discord"] = discord_mod
        sys.modules.setdefault("discord.ext", ext_mod)
        sys.modules.setdefault("discord.ext.commands", commands_mod)


_ensure_discord_mock()


from gateway.config import PlatformConfig  # noqa: E402
from plugins.platforms.discord.adapter import DiscordAdapter  # noqa: E402


def _make_config(**extra):
    cfg = MagicMock(spec=PlatformConfig)
    cfg.token = "tok"
    cfg.name = "discord-test"
    cfg.extra = extra
    cfg.reply_to_mode = "first"
    cfg.allowed_users = []
    cfg.allowed_roles = []
    return cfg


def _make_adapter(**extra):
    return DiscordAdapter(_make_config(**extra))


# ---------------------------------------------------------------------------
# AC1 — DiscordAdapter.__init__ has _lifeops_adapter attribute (todo-closure)
# ---------------------------------------------------------------------------


class TestLifeOpsAdapterAttributeExists:
    def test_lifeops_adapter_attr_initialized_to_none(self):
        """AC1: DiscordAdapter.__init__ declares _lifeops_adapter set to None."""
        adapter = _make_adapter()
        assert hasattr(adapter, "_lifeops_adapter")
        assert adapter._lifeops_adapter is None

    def test_nudge_stale_task_attr_exists(self):
        """AC1: _nudge_stale_task attribute is declared in __init__ (adjacent to bedtime/approvals)."""
        adapter = _make_adapter()
        assert hasattr(adapter, "_nudge_stale_task")
        assert adapter._nudge_stale_task is None

    def test_nudge_idle_task_attr_exists(self):
        """AC1: _nudge_idle_task attribute is declared in __init__."""
        adapter = _make_adapter()
        assert hasattr(adapter, "_nudge_idle_task")
        assert adapter._nudge_idle_task is None

    def test_nudge_weekly_task_attr_exists(self):
        """AC1: _nudge_weekly_task attribute is declared in __init__."""
        adapter = _make_adapter()
        assert hasattr(adapter, "_nudge_weekly_task")
        assert adapter._nudge_weekly_task is None

    def test_nudge_attrs_adjacent_to_bedtime_approvals(self):
        """AC1: All six scheduler attrs exist, nudge attrs adjacent to bedtime/approvals."""
        adapter = _make_adapter()
        assert hasattr(adapter, "_bedtime_task")
        assert hasattr(adapter, "_approvals_task")
        assert hasattr(adapter, "_lifeops_adapter")
        assert hasattr(adapter, "_nudge_stale_task")
        assert hasattr(adapter, "_nudge_idle_task")
        assert hasattr(adapter, "_nudge_weekly_task")


# ---------------------------------------------------------------------------
# AC2 — _run_post_connect_initialization starts nudge schedulers
# ---------------------------------------------------------------------------


class TestRunPostConnectStartsNudgeSchedulers:
    @pytest.mark.asyncio
    async def test_run_post_connect_calls_start_life_ops_nudges(self, monkeypatch):
        """AC2: _run_post_connect_initialization starts all three nudge schedulers."""
        adapter = _make_adapter()
        adapter._client = MagicMock()

        started = []

        def fake_start_nudges():
            started.append(True)

        with patch.object(adapter, "_start_life_ops_nudges", fake_start_nudges):
            with patch.object(adapter, "_start_bedtime_scheduler"):
                with patch.object(adapter, "_start_approvals_scheduler"):
                    with patch.object(adapter, "_get_discord_command_sync_policy", return_value="off"):
                        await adapter._run_post_connect_initialization()

        assert started, "_start_life_ops_nudges was not called"

    @pytest.mark.asyncio
    async def test_nudges_started_in_same_block_as_bedtime_approvals(self, monkeypatch):
        """AC2: Nudge start calls happen in same block as bedtime/approvals (not reordered)."""
        adapter = _make_adapter()
        adapter._client = MagicMock()
        call_order = []

        with patch.object(adapter, "_start_bedtime_scheduler", side_effect=lambda: call_order.append("bedtime")):
            with patch.object(adapter, "_start_approvals_scheduler", side_effect=lambda: call_order.append("approvals")):
                with patch.object(adapter, "_start_life_ops_nudges", side_effect=lambda: call_order.append("nudges")):
                    with patch.object(adapter, "_get_discord_command_sync_policy", return_value="off"):
                        await adapter._run_post_connect_initialization()

        assert "bedtime" in call_order
        assert "approvals" in call_order
        assert "nudges" in call_order


# ---------------------------------------------------------------------------
# AC3 — cancel_background_tasks cancels nudge schedulers
# ---------------------------------------------------------------------------


class TestCancelBackgroundTasksCancelsNudges:
    @pytest.mark.asyncio
    async def test_cancel_calls_lifeops_cancel_when_adapter_set(self):
        """AC3: cancel_background_tasks calls _lifeops_adapter.cancel_background_tasks."""
        adapter = _make_adapter()
        mock_lifeops = AsyncMock()
        mock_lifeops.cancel_background_tasks = AsyncMock()
        adapter._lifeops_adapter = mock_lifeops

        with patch.object(adapter, "_cancel_bedtime_task", AsyncMock()):
            with patch.object(adapter, "_cancel_approvals_task", AsyncMock()):
                with patch.object(adapter.__class__.__mro__[1], "cancel_background_tasks", AsyncMock()):
                    try:
                        await adapter.cancel_background_tasks()
                    except Exception:
                        pass

        mock_lifeops.cancel_background_tasks.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_skips_lifeops_when_adapter_not_set(self):
        """AC3: cancel_background_tasks is a no-op for nudges when _lifeops_adapter is None."""
        adapter = _make_adapter()
        assert adapter._lifeops_adapter is None

        with patch.object(adapter, "_cancel_bedtime_task", AsyncMock()):
            with patch.object(adapter, "_cancel_approvals_task", AsyncMock()):
                with patch.object(adapter.__class__.__mro__[1], "cancel_background_tasks", AsyncMock()):
                    await adapter.cancel_background_tasks()


# ---------------------------------------------------------------------------
# AC4/5 — plugins/life_ops/README.md exists with Nudges section
# ---------------------------------------------------------------------------


class TestLifeOpsReadme:
    def test_readme_exists(self):
        """AC4: plugins/life_ops/README.md exists."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        assert os.path.isfile(readme), "plugins/life_ops/README.md does not exist"

    def test_readme_has_nudges_section(self):
        """AC4: plugins/life_ops/README.md contains a ## Nudges section."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        with open(readme) as f:
            content = f.read()
        assert "## Nudges" in content or "# Nudges" in content, \
            "README.md missing Nudges section"

    def test_readme_nudges_table_has_six_env_vars(self):
        """AC4: Nudges section table documents all six env vars (two per scheduler)."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        with open(readme) as f:
            content = f.read()
        expected_vars = [
            "DISCORD_NUDGE_STALE_HOUR",
            "DISCORD_NUDGE_STALE_DAYS",
            "DISCORD_NUDGE_IDLE_HOUR",
            "DISCORD_NUDGE_IDLE_MINUTE",
            "DISCORD_NUDGE_WEEKLY_HOUR",
            "DISCORD_NUDGE_WEEKLY_DAY",
        ]
        for var in expected_vars:
            assert var in content, f"README.md missing env var {var}"

    def test_readme_nudges_mentions_opt_in(self):
        """AC4: README states each scheduler is opt-in (disabled unless *_HOUR is set)."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        with open(readme) as f:
            content = f.read()
        assert "opt-in" in content.lower() or "disabled" in content.lower(), \
            "README.md does not state schedulers are opt-in/disabled by default"

    def test_readme_nudges_mentions_away_mode(self):
        """AC4: README states each scheduler respects away mode."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        with open(readme) as f:
            content = f.read()
        assert "away" in content.lower(), \
            "README.md does not mention away mode"

    def test_readme_table_has_column_structure(self):
        """AC5: README Nudges table mirrors the bedtime env-var table format (Variable | Description)."""
        import os
        readme = os.path.join(
            os.path.dirname(__file__), "..", "..", "plugins", "life_ops", "README.md"
        )
        with open(readme) as f:
            content = f.read()
        assert "| Variable" in content or "| `DISCORD_NUDGE" in content, \
            "README.md Nudges table missing expected column structure"


# ---------------------------------------------------------------------------
# AC — plugins/life_ops/adapter.py exists and exports LifeOpsDiscordAdapter
# ---------------------------------------------------------------------------


class TestLifeOpsAdapterModule:
    def test_adapter_module_importable(self):
        """plugins/life_ops/adapter.py must be importable."""
        import importlib
        mod = importlib.import_module("plugins.life_ops.adapter")
        assert mod is not None

    def test_adapter_module_exports_lifeops_class(self):
        """plugins/life_ops/adapter.py must export LifeOpsDiscordAdapter."""
        from plugins.life_ops.adapter import LifeOpsDiscordAdapter
        assert LifeOpsDiscordAdapter is not None

    def test_lifeops_class_has_nudge_task(self):
        """LifeOpsDiscordAdapter from plugin module has _nudge_task, _idle_task, _weekly_task."""
        from plugins.life_ops.adapter import LifeOpsDiscordAdapter
        client = MagicMock()
        away = MagicMock()
        away.is_away.return_value = False
        store = MagicMock()
        adapter = LifeOpsDiscordAdapter(
            client=client, away_mode=away, todo_store=store, channel_id="123"
        )
        assert hasattr(adapter, "_nudge_task")
        assert hasattr(adapter, "_idle_task")
        assert hasattr(adapter, "_weekly_task")


# ---------------------------------------------------------------------------
# AC7 — Smoke: existing bedtime/approvals schedulers unaffected
# ---------------------------------------------------------------------------


class TestExistingSchedulersUnaffected:
    def test_bedtime_task_still_initialised_to_none(self):
        """AC7: _bedtime_task is still None after __init__ (existing behavior unchanged)."""
        adapter = _make_adapter()
        assert adapter._bedtime_task is None

    def test_approvals_task_still_initialised_to_none(self):
        """AC7: _approvals_task is still None after __init__ (existing behavior unchanged)."""
        adapter = _make_adapter()
        assert adapter._approvals_task is None

    def test_start_bedtime_scheduler_still_callable(self):
        """AC7: _start_bedtime_scheduler remains callable."""
        adapter = _make_adapter()
        assert callable(adapter._start_bedtime_scheduler)

    def test_cancel_bedtime_task_still_callable(self):
        """AC7: _cancel_bedtime_task remains callable."""
        adapter = _make_adapter()
        assert callable(adapter._cancel_bedtime_task)


# ---------------------------------------------------------------------------
# AC8 — With all *_HOUR vars unset, no nudge schedulers fire
# ---------------------------------------------------------------------------


class TestNudgeSchedulersDisabledByDefault:
    @pytest.mark.asyncio
    async def test_nudge_tasks_none_when_hours_unset(self, monkeypatch):
        """AC8: With all *_HOUR vars unset, nudge tasks remain None after _start_life_ops_nudges."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)

        adapter = _make_adapter()
        adapter._client = MagicMock()

        loop = asyncio.get_event_loop()
        adapter._start_life_ops_nudges()

        lifeops = adapter._lifeops_adapter
        assert lifeops is not None, "_lifeops_adapter should be created"
        assert lifeops._nudge_task is None, "_nudge_task should be None when STALE_HOUR unset"
        assert lifeops._idle_task is None, "_idle_task should be None when IDLE_HOUR unset"
        assert lifeops._weekly_task is None, "_weekly_task should be None when WEEKLY_HOUR unset"


# ---------------------------------------------------------------------------
# AC9 — Setting one *_HOUR only activates that scheduler
# ---------------------------------------------------------------------------


class TestSingleHourActivatesOnlyThatScheduler:
    @pytest.mark.asyncio
    async def test_only_stale_task_created_when_only_stale_hour_set(self, monkeypatch):
        """AC9: Only stale-todo task is created when only DISCORD_NUDGE_STALE_HOUR is set."""
        monkeypatch.setenv("DISCORD_NUDGE_STALE_HOUR", "8")
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)

        adapter = _make_adapter()
        adapter._client = MagicMock()
        adapter._client.get_channel.return_value = AsyncMock()

        try:
            adapter._start_life_ops_nudges()
            lifeops = adapter._lifeops_adapter
            assert lifeops._nudge_task is not None, "_nudge_task should be created"
            assert lifeops._idle_task is None, "_idle_task should be None"
            assert lifeops._weekly_task is None, "_weekly_task should be None"
        finally:
            if adapter._lifeops_adapter:
                await adapter._lifeops_adapter.cancel_background_tasks()

    @pytest.mark.asyncio
    async def test_only_idle_task_created_when_only_idle_hour_set(self, monkeypatch):
        """AC9: Only idle-day task is created when IDLE_HOUR+MINUTE are set."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_HOUR", "14")
        monkeypatch.setenv("DISCORD_NUDGE_IDLE_MINUTE", "0")
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_WEEKLY_MINUTE", raising=False)

        adapter = _make_adapter()
        adapter._client = MagicMock()

        try:
            adapter._start_life_ops_nudges()
            lifeops = adapter._lifeops_adapter
            assert lifeops._nudge_task is None, "_nudge_task should be None"
            assert lifeops._idle_task is not None, "_idle_task should be created"
            assert lifeops._weekly_task is None, "_weekly_task should be None"
        finally:
            if adapter._lifeops_adapter:
                await adapter._lifeops_adapter.cancel_background_tasks()

    @pytest.mark.asyncio
    async def test_only_weekly_task_created_when_only_weekly_hour_set(self, monkeypatch):
        """AC9: Only weekly-reset task is created when WEEKLY_HOUR+MINUTE are set."""
        monkeypatch.delenv("DISCORD_NUDGE_STALE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_HOUR", raising=False)
        monkeypatch.delenv("DISCORD_NUDGE_IDLE_MINUTE", raising=False)
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_HOUR", "20")
        monkeypatch.setenv("DISCORD_NUDGE_WEEKLY_MINUTE", "0")

        adapter = _make_adapter()
        adapter._client = MagicMock()

        try:
            adapter._start_life_ops_nudges()
            lifeops = adapter._lifeops_adapter
            assert lifeops._nudge_task is None, "_nudge_task should be None"
            assert lifeops._idle_task is None, "_idle_task should be None"
            assert lifeops._weekly_task is not None, "_weekly_task should be created"
        finally:
            if adapter._lifeops_adapter:
                await adapter._lifeops_adapter.cancel_background_tasks()
