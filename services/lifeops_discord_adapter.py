"""LifeOps Discord adapter: stale-todo, idle-day, and weekly-reset nudge schedulers.

Provides LifeOpsDiscordAdapter, a standalone class that owns the daily
stale-todo nudge scheduler, idle-day nudge scheduler, and weekly reset
nudge scheduler. TodoClosureView is the Discord UI view for acting on todos.

Mirrors the _start_bedtime_scheduler / _start_approvals_scheduler pattern
in plugins/platforms/discord/adapter.py.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import discord
    _DISCORD_AVAILABLE = True
except ImportError:
    _DISCORD_AVAILABLE = False
    discord = None  # type: ignore[assignment]


def _read_idle_day_nudge_config() -> dict:
    """Read idle-day nudge scheduler config from environment variables.

    Both DISCORD_NUDGE_IDLE_HOUR and DISCORD_NUDGE_IDLE_MINUTE must be set
    and parseable as integers; if either is missing the scheduler is disabled.

    Keys:
        enabled — True only when both env vars are set and parseable
        hour    — int, local hour (0-23)
        minute  — int, local minute (0-59)
    """
    raw_hour = os.getenv("DISCORD_NUDGE_IDLE_HOUR", "").strip()
    raw_minute = os.getenv("DISCORD_NUDGE_IDLE_MINUTE", "").strip()
    if not raw_hour or not raw_minute:
        return {"enabled": False, "hour": 0, "minute": 0}
    try:
        hour = int(raw_hour)
    except ValueError:
        return {"enabled": False, "hour": 0, "minute": 0}
    try:
        minute = int(raw_minute)
    except ValueError:
        return {"enabled": False, "hour": 0, "minute": 0}
    return {"enabled": True, "hour": hour, "minute": minute}


def _read_stale_todo_nudge_config() -> dict:
    """Read stale-todo nudge scheduler config from environment variables.

    Keys:
        enabled        — True when DISCORD_NUDGE_STALE_HOUR is set and parseable
        hour           — int, UTC hour (0-23)
        minute         — int, UTC minute (0-59, default 0)
        threshold_days — int, days before a todo is stale (default 5)
    """
    raw_hour = os.getenv("DISCORD_NUDGE_STALE_HOUR", "").strip()
    if not raw_hour:
        return {"enabled": False, "hour": 0, "minute": 0, "threshold_days": 5}
    try:
        hour = int(raw_hour)
    except ValueError:
        return {"enabled": False, "hour": 0, "minute": 0, "threshold_days": 5}
    raw_minute = os.getenv("DISCORD_NUDGE_STALE_MINUTE", "0").strip()
    try:
        minute = int(raw_minute)
    except ValueError:
        minute = 0
    raw_days = os.getenv("DISCORD_NUDGE_STALE_DAYS", "5").strip()
    try:
        threshold_days = int(raw_days)
    except ValueError:
        threshold_days = 5
    return {"enabled": True, "hour": hour, "minute": minute, "threshold_days": threshold_days}


def _read_weekly_nudge_config() -> dict:
    """Read weekly-reset nudge config from environment variables.

    Both DISCORD_NUDGE_WEEKLY_HOUR and DISCORD_NUDGE_WEEKLY_MINUTE must be set
    and parseable as integers; if either is missing the scheduler is disabled.
    DISCORD_NUDGE_WEEKLY_DAY defaults to 6 (Sunday) when unset.

    Keys:
        enabled — True only when HOUR and MINUTE are both set and parseable
        day     — int, weekday 0=Monday … 6=Sunday (default 6)
        hour    — int, local hour (0-23)
        minute  — int, local minute (0-59)
    """
    raw_hour = os.getenv("DISCORD_NUDGE_WEEKLY_HOUR", "").strip()
    raw_minute = os.getenv("DISCORD_NUDGE_WEEKLY_MINUTE", "").strip()
    if not raw_hour or not raw_minute:
        return {"enabled": False, "day": 6, "hour": 0, "minute": 0}
    try:
        hour = int(raw_hour)
    except ValueError:
        return {"enabled": False, "day": 6, "hour": 0, "minute": 0}
    try:
        minute = int(raw_minute)
    except ValueError:
        return {"enabled": False, "day": 6, "hour": 0, "minute": 0}
    raw_day = os.getenv("DISCORD_NUDGE_WEEKLY_DAY", "6").strip()
    try:
        day = int(raw_day)
    except ValueError:
        day = 6
    return {"enabled": True, "day": day, "hour": hour, "minute": minute}


class LifeOpsDiscordAdapter:
    """Stale-todo nudge scheduler for a Discord bot.

    Constructed with an active Discord client, an away_mode object, and a
    TodoStore.  Call _start_stale_todo_nudge_scheduler() once the bot is
    connected; the scheduler reads configuration from environment variables
    and is a no-op when DISCORD_NUDGE_STALE_HOUR is unset.
    """

    def __init__(
        self,
        *,
        client,
        away_mode,
        todo_store,
        channel_id: str,
        name: str = "lifeops",
    ) -> None:
        self._client = client
        self._away_mode = away_mode
        self._todo_store = todo_store
        self._channel_id = channel_id
        self.name = name
        self._nudge_task: Optional[asyncio.Task] = None
        self._idle_task: Optional[asyncio.Task] = None
        self._weekly_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Scheduler lifecycle
    # ------------------------------------------------------------------

    def _start_stale_todo_nudge_scheduler(self) -> None:
        """Start the stale-todo nudge scheduler if DISCORD_NUDGE_STALE_HOUR is set.

        Idempotent: a second call while the task is live is a no-op.
        """
        cfg = _read_stale_todo_nudge_config()
        if not cfg["enabled"]:
            return
        if self._nudge_task and not self._nudge_task.done():
            return
        self._nudge_task = asyncio.create_task(
            self._stale_todo_nudge_scheduler_loop(cfg)
        )
        logger.info(
            "[%s] Stale-todo nudge scheduler started (fire at %02d:%02d UTC)",
            self.name, cfg["hour"], cfg["minute"],
        )

    async def _stale_todo_nudge_scheduler_loop(self, cfg: dict) -> None:
        """Loop indefinitely, firing the stale-todo nudge once per 24 h."""
        import datetime

        while True:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            target = now_utc.replace(
                hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0
            )
            if target <= now_utc:
                target += datetime.timedelta(days=1)
            delay = (target - now_utc).total_seconds()
            logger.debug(
                "[%s] Stale-todo nudge: sleeping %.0fs until %s UTC",
                self.name, delay, target.isoformat(),
            )
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

            try:
                await self._fire_stale_todo_nudge(cfg)
            except Exception as exc:
                logger.error(
                    "[%s] Stale-todo nudge: unexpected error: %s", self.name, exc
                )

    async def _fire_stale_todo_nudge(self, cfg: dict) -> None:
        """Post the stale-todo nudge message to the configured channel.

        Skips silently when:
        - away_mode.is_away() is True
        - get_stale_todos() returns an empty list
        - the channel is not reachable
        """
        if self._away_mode.is_away():
            logger.debug("[%s] Stale-todo nudge: away mode active; skipping", self.name)
            return

        threshold_days = cfg.get("threshold_days", 5)
        stale_todos = self._todo_store.get_stale_todos(threshold_days=threshold_days)

        if not stale_todos:
            logger.info("[%s] Stale-todo nudge: no stale todos; skipping", self.name)
            return

        if not self._channel_id or not self._client:
            logger.warning(
                "[%s] Stale-todo nudge: channel not configured; skipping", self.name
            )
            return

        ch = self._client.get_channel(int(self._channel_id))
        if ch is None:
            logger.warning(
                "[%s] Stale-todo nudge: channel %s not found; skipping",
                self.name, self._channel_id,
            )
            return

        n = len(stale_todos)
        content = (
            f"Still on these? {n} todo(s) haven't moved in {threshold_days}+ days:"
        )
        view = TodoClosureView(todos=stale_todos)
        await ch.send(content, view=view)
        logger.info(
            "[%s] Stale-todo nudge posted (%d todo(s), channel=%s)",
            self.name, n, self._channel_id,
        )

    async def _cancel_stale_todo_nudge_task(self) -> None:
        """Cancel and await the stale-todo nudge scheduler task, if running."""
        if self._nudge_task and not self._nudge_task.done():
            self._nudge_task.cancel()
            try:
                await self._nudge_task
            except asyncio.CancelledError:
                pass
        self._nudge_task = None

    # ------------------------------------------------------------------
    # Idle-day nudge scheduler
    # ------------------------------------------------------------------

    def _start_idle_day_nudge_scheduler(self) -> None:
        """Start the idle-day nudge scheduler if both DISCORD_NUDGE_IDLE_HOUR
        and DISCORD_NUDGE_IDLE_MINUTE are set.

        Idempotent: a second call while the task is live is a no-op.
        """
        cfg = _read_idle_day_nudge_config()
        if not cfg["enabled"]:
            return
        if self._idle_task and not self._idle_task.done():
            return
        self._idle_task = asyncio.create_task(
            self._idle_day_nudge_scheduler_loop(cfg)
        )
        logger.info(
            "[%s] Idle-day nudge scheduler started (fire at %02d:%02d local)",
            self.name, cfg["hour"], cfg["minute"],
        )

    async def _idle_day_nudge_scheduler_loop(self, cfg: dict) -> None:
        """Loop indefinitely, firing the idle-day nudge once per 24 h."""
        import datetime

        while True:
            now = datetime.datetime.now()
            target = now.replace(
                hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0
            )
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            logger.debug(
                "[%s] Idle-day nudge: sleeping %.0fs until %s local",
                self.name, delay, target.isoformat(),
            )
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

            try:
                await self._fire_idle_day_nudge(cfg)
            except Exception as exc:
                logger.error(
                    "[%s] Idle-day nudge: unexpected error: %s", self.name, exc
                )

    async def _fire_idle_day_nudge(self, cfg: dict) -> None:
        """Post the idle-day nudge if the user hasn't closed any todos today
        and still has open items.

        Skips silently when:
        - away_mode.is_away() is True
        - count_todos_closed_today() > 0
        - get_open_todos() returns an empty list
        - the channel is not reachable
        """
        if self._away_mode.is_away():
            logger.debug("[%s] Idle-day nudge: away mode active; skipping", self.name)
            return

        if self._todo_store.count_todos_closed_today() > 0:
            logger.info("[%s] Idle-day nudge: todos already closed today; skipping", self.name)
            return

        open_todos = self._todo_store.get_open_todos()
        if not open_todos:
            logger.info("[%s] Idle-day nudge: no open todos; skipping", self.name)
            return

        if not self._channel_id or not self._client:
            logger.warning(
                "[%s] Idle-day nudge: channel not configured; skipping", self.name
            )
            return

        ch = self._client.get_channel(int(self._channel_id))
        if ch is None:
            logger.warning(
                "[%s] Idle-day nudge: channel %s not found; skipping",
                self.name, self._channel_id,
            )
            return

        content = "Haven't touched your list today — want to review it?"
        view = TodoClosureView(todos=open_todos)
        await ch.send(content, view=view)
        logger.info(
            "[%s] Idle-day nudge posted (%d open todo(s), channel=%s)",
            self.name, len(open_todos), self._channel_id,
        )

    async def _cancel_idle_day_nudge_task(self) -> None:
        """Cancel and await the idle-day nudge scheduler task, if running."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass
        self._idle_task = None

    # ------------------------------------------------------------------
    # Weekly reset nudge scheduler
    # ------------------------------------------------------------------

    def _start_weekly_nudge_scheduler(self) -> None:
        """Start the weekly-reset nudge scheduler if HOUR and MINUTE are set.

        Idempotent: a second call while the task is live is a no-op.
        """
        cfg = _read_weekly_nudge_config()
        if not cfg["enabled"]:
            return
        if self._weekly_task and not self._weekly_task.done():
            return
        self._weekly_task = asyncio.create_task(
            self._weekly_nudge_scheduler_loop(cfg)
        )
        logger.info(
            "[%s] Weekly-reset nudge scheduler started (fire day=%d at %02d:%02d local)",
            self.name, cfg["day"], cfg["hour"], cfg["minute"],
        )

    async def _weekly_nudge_scheduler_loop(self, cfg: dict) -> None:
        """Loop indefinitely, waking once per 24 h and checking the weekday."""
        while True:
            now = datetime.datetime.now()
            target = now.replace(
                hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0
            )
            if target <= now:
                target += datetime.timedelta(days=1)
            delay = (target - now).total_seconds()
            logger.debug(
                "[%s] Weekly-reset nudge: sleeping %.0fs until %s local",
                self.name, delay, target.isoformat(),
            )
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

            try:
                await self._fire_weekly_nudge(cfg)
            except Exception as exc:
                logger.error(
                    "[%s] Weekly-reset nudge: unexpected error: %s", self.name, exc
                )

    async def _fire_weekly_nudge(self, cfg: dict) -> None:
        """Post the weekly-reset nudge if today is the configured weekday.

        Skips silently when:
        - current weekday != cfg["day"]
        - away_mode.is_away() is True
        - get_open_todos() returns an empty list
        - the channel is not reachable
        """
        now = datetime.datetime.now()
        if now.weekday() != cfg["day"]:
            logger.debug(
                "[%s] Weekly-reset nudge: weekday %d != configured %d; skipping",
                self.name, now.weekday(), cfg["day"],
            )
            return

        if self._away_mode.is_away():
            logger.debug("[%s] Weekly-reset nudge: away mode active; skipping", self.name)
            return

        open_todos = self._todo_store.get_open_todos()
        if not open_todos:
            logger.info("[%s] Weekly-reset nudge: no open todos; skipping", self.name)
            return

        if not self._channel_id or not self._client:
            logger.warning(
                "[%s] Weekly-reset nudge: channel not configured; skipping", self.name
            )
            return

        ch = self._client.get_channel(int(self._channel_id))
        if ch is None:
            logger.warning(
                "[%s] Weekly-reset nudge: channel %s not found; skipping",
                self.name, self._channel_id,
            )
            return

        n = len(open_todos)
        content = f"Weekly reset — {n} open todo(s)"
        view = TodoClosureView(todos=open_todos)
        await ch.send(content, view=view)
        logger.info(
            "[%s] Weekly-reset nudge posted (%d open todo(s), channel=%s)",
            self.name, n, self._channel_id,
        )

    async def _cancel_weekly_nudge_task(self) -> None:
        """Cancel and await the weekly-reset nudge scheduler task, if running."""
        if self._weekly_task and not self._weekly_task.done():
            self._weekly_task.cancel()
            try:
                await self._weekly_task
            except asyncio.CancelledError:
                pass
        self._weekly_task = None

    # ------------------------------------------------------------------
    # Lifecycle aggregates
    # ------------------------------------------------------------------

    def _run_post_connect_initialization(self) -> None:
        """Start all background schedulers after the bot connects."""
        self._start_stale_todo_nudge_scheduler()
        self._start_idle_day_nudge_scheduler()
        self._start_weekly_nudge_scheduler()

    async def cancel_background_tasks(self) -> None:
        """Cancel all background scheduler tasks."""
        await self._cancel_stale_todo_nudge_task()
        await self._cancel_idle_day_nudge_task()
        await self._cancel_weekly_nudge_task()


# ---------------------------------------------------------------------------
# TodoClosureView — reused as-is; no other View class is introduced
# ---------------------------------------------------------------------------

if _DISCORD_AVAILABLE:
    class TodoClosureView(discord.ui.View):  # type: ignore[misc]
        """Discord UI view for acting on stale todos.

        Layout:
          - Select: choose which todo to act on (populated from the stale list)
          - Buttons: Mark Done / Dismiss / Snooze
        """

        def __init__(self, *, todos: list, timeout: int = 300) -> None:
            super().__init__(timeout=timeout)
            self.todos = todos
            self.selected_key: Optional[str] = todos[0]["key"] if todos else None

            options = [
                discord.SelectOption(
                    label=t["text"][:100],
                    value=t["key"],
                    default=(i == 0),
                )
                for i, t in enumerate(todos[:25])
            ]

            select = discord.ui.Select(
                placeholder="Choose a todo to act on…",
                options=options,
                custom_id="stale_todo_select",
            )
            select.callback = self._on_todo_selected
            self.add_item(select)

        async def _on_todo_selected(self, interaction: discord.Interaction) -> None:
            values = interaction.data.get("values", [])
            if values:
                self.selected_key = values[0]
            await interaction.response.edit_message(view=self)

        @discord.ui.button(
            label="Mark Done",
            style=discord.ButtonStyle.green,
            custom_id="stale_mark_done",
        )
        async def mark_done(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ) -> None:
            await interaction.response.send_message(
                f"✅ Marked done (todo: {self.selected_key or 'none selected'})",
                ephemeral=True,
            )

        @discord.ui.button(
            label="Dismiss",
            style=discord.ButtonStyle.grey,
            custom_id="stale_dismiss",
        )
        async def dismiss(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ) -> None:
            await interaction.response.send_message(
                f"Dismissed (todo: {self.selected_key or 'none selected'})",
                ephemeral=True,
            )

        @discord.ui.button(
            label="Snooze",
            style=discord.ButtonStyle.blurple,
            custom_id="stale_snooze",
        )
        async def snooze(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ) -> None:
            await interaction.response.send_message(
                f"💤 Snoozed (todo: {self.selected_key or 'none selected'})",
                ephemeral=True,
            )

else:
    class TodoClosureView:  # type: ignore[no-redef]
        """Stub when discord.py is not installed."""

        def __init__(self, *, todos: list, timeout: int = 300) -> None:
            self.todos = todos
            self.selected_key: Optional[str] = todos[0]["key"] if todos else None
