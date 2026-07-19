# life_ops — fork-owned personal automation plugin

Everything the `zealchaiwut/hermes-agent` fork adds on top of
`NousResearch/hermes-agent` lives in this package. Upstream files stay
byte-identical to upstream (two documented exceptions, see
[`../../FORK.md`](../../FORK.md)), so `git merge upstream/main` never
conflicts with fork code.

## Enable (once per machine)

```bash
hermes plugins enable life_ops
# or in ~/.hermes/config.yaml:
# plugins:
#   enabled: [life_ops]
```

Without this, the gateway runs the stock bundled Discord adapter and none
of the features below are active.

## What it provides

| Feature | Where |
| --- | --- |
| Persistent todo store (stable keys, open/done/dismiss/snooze) | `todo_store.py`, `todo_store_sync.py`, `todo_store_seed.py` |
| `/done` `/dismiss` `/snooze` slash commands + morning todo-closure buttons | `discord_commands.py`, `discord_adapter.py` |
| Away mode (`/away-on`, `/away-off`) | `away_mode.py` |
| Bedtime overnight-sprint prompt (Start/Skip buttons) | `discord_adapter.py`, `bedtime.py` |
| Journal-approvals dispatch (dev todo → Commander ticket `[Approve]`) | `journal_approve.py`, `discord_adapter.py` |
| `/rpe` training feedback → perf-coach | `discord_commands.py` |
| Morning brief composer + Discord delivery | `scripts/morning_brief_composer.py`, `scripts/morning_brief_discord.py`, `brief_render.yaml` |

The Discord features work by re-registering the `discord` platform with
`LifeOpsDiscordAdapter`, a subclass of the bundled adapter
(`gateway.platform_registry` is last-writer-wins by design).

## Morning brief

```bash
python3 plugins/life_ops/scripts/morning_brief_composer.py            # writes ~/.hermes/morning_brief.md
python3 plugins/life_ops/scripts/morning_brief_composer.py --dry-run  # print to stdout
```

Scheduled delivery runs via the launchd chain in [`../../deploy/`](../../deploy/)
(`deploy/bin/morning-chain.sh`, 5 steps, 05:45 Asia/Bangkok). Setup and
config keys (`discord.morning_brief_channel_id`,
`discord.morning_brief_contracts`, `DISCORD_BOT_TOKEN`): see
[`docs/morning-brief.md`](docs/morning-brief.md).

## Discord bedtime scheduler

Set these env vars (e.g. in `~/.hermes/.env`) to enable the nightly
overnight-sprint prompt:

| Variable | Description |
| --- | --- |
| `DISCORD_BEDTIME_HOUR` | UTC hour to fire, 0–23 (e.g. `22`); out-of-range disables the scheduler |
| `DISCORD_BEDTIME_MINUTE` | UTC minute, 0–59 (default `0`); out-of-range disables the scheduler |
| `DISCORD_HOME_CHANNEL` | Discord channel ID to post the prompt |
| `DISCORD_BEDTIME_TIMEOUT` | Seconds to wait for a click (default `300`) |

Journal approvals: `DISCORD_APPROVALS_HOUR` (0–23) / `_MINUTE` (0–59) +
`JOURNAL_APPROVE_PROJECTS`; out-of-range values disable the scheduler with a log warning. Todo-closure view:
`DISCORD_TODO_CLOSURE_HOUR`/`_MINUTE`. Both post to
`discord.morning_brief_channel_id`.

## Nudges

Three **opt-in** schedulers that send informational prompts when your todo list
needs attention. All three are disabled by default — each starts only when its
`*_HOUR` variable is set. All three **respect away mode**: no nudge is sent
while `/away-on` is active.

### Stale-todo threshold nudge

Fires **daily** at the configured UTC time. Posts a `TodoClosureView` for any
todos that have not moved in `DISCORD_NUDGE_STALE_DAYS` days (default 5).

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_STALE_HOUR` | UTC hour to fire (required to enable; e.g. `9`) |
| `DISCORD_NUDGE_STALE_MINUTE` | UTC minute (default `0`) |

Optional companion: `DISCORD_NUDGE_STALE_DAYS` — stale threshold in days
(default `5`).

### Idle-day check-in nudge

Fires **daily** at the configured UTC time. Posts a `TodoClosureView` only
when **both** conditions hold: no todos were closed today AND at least one
open todo exists. Silent skip otherwise.

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_IDLE_HOUR` | UTC hour to fire (required; **both** vars must be set) |
| `DISCORD_NUDGE_IDLE_MINUTE` | UTC minute (required; **both** vars must be set) |

### Weekly reset nudge

Fires **daily** at the configured UTC time but only **acts** on the configured
day-of-week (`DISCORD_NUDGE_WEEKLY_DAY`, 0=Monday…6=Sunday, default `6` =
Sunday). Posts a `TodoClosureView` for all open todos on the matching day.

| Variable | Description |
| --- | --- |
| `DISCORD_NUDGE_WEEKLY_HOUR` | UTC hour to fire (required to enable; e.g. `8`) |
| `DISCORD_NUDGE_WEEKLY_MINUTE` | UTC minute (default `0`) |

Optional companion: `DISCORD_NUDGE_WEEKLY_DAY` — day of week to fire
(0=Monday…6=Sunday, default `6`).

All nudge prompts post to `discord.morning_brief_channel_id` and show the
same `TodoClosureView` interactive control — use `/done`, `/dismiss`, or
`/snooze` to act on the highlighted todos.

## Docs

- [`docs/PRODUCT.md`](docs/PRODUCT.md), [`docs/DESIGN.md`](docs/DESIGN.md) — product/design contracts
- [`docs/morning-brief.md`](docs/morning-brief.md) — morning brief setup
- [`docs/dig-deeper.md`](docs/dig-deeper.md) — expand any brief section with follow-up commands and skills
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — fork changelog

## Tests

Fork tests live under the repo's standard `tests/` tree (`tests/hermes/`,
`tests/cron/`, `tests/test_morning_*.py`, `tests/test_discord_bedtime_*`)
so upstream's pristine `testpaths = ["tests"]` config and CI discover them
unchanged. `tests/hermes/test_life_ops_canary.py` fails loudly if upstream
renames the adapter internals this plugin relies on.
