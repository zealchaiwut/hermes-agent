"""Life Ops Discord adapter — re-export and factory helpers.

Import LifeOpsDiscordAdapter from here when wiring it into the Discord
platform adapter lifecycle, rather than importing directly from services/.
"""
from __future__ import annotations

import os

from services.lifeops_discord_adapter import LifeOpsDiscordAdapter


class _NeverAway:
    """Stub away-mode that always reports the user as present.

    Used as the default away_mode for LifeOpsDiscordAdapter when the Discord
    platform adapter does not have a richer away-mode implementation.
    """

    def is_away(self) -> bool:
        return False


def make_default_away_mode() -> _NeverAway:
    return _NeverAway()


def make_default_todo_store():
    from plugins.life_ops.todo_store import TodoStore
    return TodoStore()


def make_lifeops_adapter(client, *, channel_id: str = "") -> LifeOpsDiscordAdapter:
    """Create a LifeOpsDiscordAdapter with production defaults.

    Args:
        client: Active Discord client (discord.ext.commands.Bot).
        channel_id: Discord channel ID for nudge messages
                    (defaults to DISCORD_HOME_CHANNEL env var).
    """
    if not channel_id:
        channel_id = os.getenv("DISCORD_HOME_CHANNEL", "")
    return LifeOpsDiscordAdapter(
        client=client,
        away_mode=make_default_away_mode(),
        todo_store=make_default_todo_store(),
        channel_id=channel_id,
    )


__all__ = [
    "LifeOpsDiscordAdapter",
    "make_lifeops_adapter",
    "make_default_away_mode",
    "make_default_todo_store",
]
