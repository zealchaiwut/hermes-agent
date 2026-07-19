# Hermes Agent — Product

Personal fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent):
a self-improving personal AI agent that runs one agent core across a CLI/TUI, a
multi-platform messaging gateway (Telegram, Discord, Slack, …), and a desktop
app. It learns across sessions (memory + skills), delegates to subagents, runs
scheduled cron jobs, and drives a real terminal and browser.

## What this fork adds

- **Life-ops plugin** (`plugins/life_ops/`): a Discord-based daily operations
  layer — morning brief, bedtime check-in, RPE logging, todo closure views,
  approvals — wired to the owner's personal stack.
- **Personal-stack skills** (`optional-skills/`): integrations with
  **perf-coach** (health/training dashboard) and **commander** (sprint/agent
  orchestration dashboard) via their HTTP APIs.
- **Deploy artifacts** (`deploy/`): launchd plists and shell chains
  (e.g. `com.hermes.morning-chain.plist`, `bin/morning-chain.sh`) for
  unattended scheduled runs on macOS.
- Upstream is tracked via periodic `sync/upstream-*` branches; local work goes
  through the commander sprint flow (`feature/*` → `develop` → `master`).

## Users

Single-user (the repo owner). No multi-tenant concerns; secrets live in local
config/env, never in the repo.

## Priorities

1. Reliability of scheduled life-ops automations (cron, morning chain, bedtime).
2. Correctness of Discord command handlers and config parsing.
3. Clean upstream syncs — keep fork-local surface small (plugins/skills, not core).
