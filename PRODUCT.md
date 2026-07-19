# Hermes Agent — Product Overview

A personal life-ops Discord bot built on the open-source Hermes agent framework, extended via `plugins/life_ops/` (this fork's single owned plugin — see `FORK.md`).

## Core Purpose

Deliver a daily morning brief (journal reflection, todos, training status, dev-report across tracked projects) to Discord, and let the operator manage todos and nudges from chat instead of a dashboard.

## Primary User

Solo operator (single Discord user/server) — not multi-tenant.

## Key Features

- **Morning brief chain** (`deploy/bin/morning-chain.sh`, scheduled via launchd at 05:45 Asia/Bangkok): journal fetch/OCR, journal reflection generation, todo sync, perf-coach training export, commander dev-report export, then composed brief delivered to Discord.
- **Discord slash commands** (`plugins/life_ops/discord_commands.py`): `/done`, `/dismiss`, `/snooze` (todo management), `/away-on`/`/away-off` (pause overnight runs/bedtime prompts).
- **Nudge schedulers** (`plugins/life_ops/discord_adapter.py`): stale-todo, idle-day, weekly-reset, opt-in via `DISCORD_NUDGE_*` env vars.
- **Bundled Discord adapter subclass** (`plugins/life_ops/discord_adapter.py`) registered via the upstream `gateway/platform_registry.py` last-writer-wins semantics; upstream files stay pristine.

## Tech Stack

- Python, upstream Hermes agent framework (bundled `DiscordAdapter` base)
- discord.py-based slash commands (`@tree.command`)
- Shell scripts for the scheduled morning chain, launchd for scheduling on the deploy machine (zeal-server, mac mini)
- No database of its own; reads/writes contract JSON files under `~/.hermes/contracts/` produced by other projects (perf-coach, commander) and the journal repo

## Fork Boundary

All fork-owned code lives under `plugins/life_ops/`, `deploy/`, `optional-skills/`, and `tests/`. Everything else is upstream and stays pristine to keep future syncs conflict-free; see `FORK.md`.
