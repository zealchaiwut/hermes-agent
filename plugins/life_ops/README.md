# Life Ops Plugin

The Life Ops plugin manages personal productivity features delivered through the Discord gateway: todo tracking, staleness nudges, idle-day check-ins, and weekly resets.

## Nudges

The plugin provides three opt-in nudge schedulers. Each scheduler is **disabled by default** — it only activates when its `*_HOUR` environment variable is set. All three schedulers respect away mode: no message is sent while away mode is active.

### Stale-todo nudge

Posts a message when open todos haven't moved in N days. Fires daily at the configured UTC hour.

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_STALE_HOUR` | UTC hour to fire (e.g. `8`). Unset → scheduler disabled (opt-in). |
| `DISCORD_NUDGE_STALE_DAYS` | Days before a todo is considered stale (default `5`). |

### Idle-day check-in nudge

Posts a check-in message when no todos have been closed today and there are open items. Fires daily at the configured local hour.

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_IDLE_HOUR` | Local hour to fire (e.g. `14`). Unset → scheduler disabled (opt-in). |
| `DISCORD_NUDGE_IDLE_MINUTE` | Local minute (required alongside `DISCORD_NUDGE_IDLE_HOUR`). |

### Weekly reset nudge

Posts a weekly summary of open todos on the configured weekday. Fires once per week at the configured local hour.

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_WEEKLY_HOUR` | Local hour to fire (e.g. `20`). Unset → scheduler disabled (opt-in). |
| `DISCORD_NUDGE_WEEKLY_DAY` | Weekday to fire: `0`=Monday … `6`=Sunday (default `6` = Sunday). |

### Common settings

All nudge messages are delivered to `DISCORD_HOME_CHANNEL`. Each message includes a **TodoClosureView** with Mark Done / Dismiss / Snooze actions so you can act on items inline.

Away mode is respected across all three schedulers: if away mode is active at fire time, the message is suppressed and no retry occurs until the next scheduled window.
