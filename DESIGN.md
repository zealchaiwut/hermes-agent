# Hermes Agent — Design

See `AGENTS.md` for the authoritative development guide. This file summarizes
the architecture for sprint agents (coder/tester) working in this fork.

## Core principles (from upstream)

- **Per-conversation prompt caching is sacred.** Never mutate past context,
  swap toolsets, or rebuild the system prompt mid-conversation (only exception:
  context compression).
- **The core is a narrow waist; capability lives at the edges.** New capability
  arrives as a plugin, a CLI command + skill, or a service-gated tool — not as
  new core tool surface.

## Layout

    agent/            agent core (loop, tools, context)
    gateway/          multi-platform messaging gateway (Discord, Telegram, …)
    hermes_cli/       CLI/TUI entry points
    cron/             scheduler: jobs.py, scheduler.py, lifecycle_guard.py,
                      blueprint/suggestion catalogs
    plugins/          edge capability; fork-local work concentrates in
                      plugins/life_ops/ (discord_adapter.py, discord_commands.py,
                      bedtime.py, config.py)
    optional-skills/  agentskills.io-style skills, incl. health/perf-coach and
                      software-development/commander-api
    deploy/           launchd plists + bin/ shell chains for unattended macOS runs
    docs/             design notes, contracts (chronos cron contract, relay
                      connector contract, session lifecycle)

## Fork conventions

- Branching: `feature/<N>-<slug>` off `develop`; tester merges to `develop`;
  human merges `develop` → `master`. Upstream syncs land via `sync/upstream-*`
  branches — never rebase fork history onto upstream.
- Keep fork-local diffs at the edges (plugins, skills, deploy). Changing agent
  core files complicates upstream sync and needs strong justification.
- Config values are read via `plugins/life_ops/config.py` getters backed by env
  vars; validate ranges at parse time and fail loudly (logger.error + non-zero
  exit) rather than silently falling back.
- launchd `StartCalendarInterval` uses **local time** (Asia/Bangkok on the host),
  not UTC — comments and docs must not claim otherwise.
- Tests: pytest under `tests/`; Discord handlers are tested via their pure
  helper functions where possible (no live gateway in unit tests).
