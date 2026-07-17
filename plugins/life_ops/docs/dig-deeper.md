# Dig Deeper — Morning Brief Expansion Guide

Each section of the morning brief can be expanded with follow-up commands or skills.
Reply in the brief thread with any of the prompts below.

## Section 2 — Todo List

Manage open todos directly:

| Command | Effect |
|---|---|
| `/done <key>` | Mark a todo done |
| `/dismiss <key>` | Dismiss a todo (won't recur) |
| `/snooze <key>` | Snooze a todo until tomorrow |

## Section 3 — Training

Expand with the **perf-coach** skill:

| Tool | Endpoint | What it returns |
|---|---|---|
| `training_load` | `GET /api/training/load` | CTL/ATL/TSB/ACWR + pre-computed verdict |
| `today` | `GET /api/plan/today` | Today's planned session |
| `weight` | `GET /api/weight/recent` | Recent weight entries |
| `brief` | `GET /api/brief/today` | Full training brief for today |

Example follow-up: _"why this advisory"_ → perf-coach reads `training_load` and narrates the verdict.

## Section 4 — Overnight Dev Report

Expand with the **commander-api** skill:

| Tool | Endpoint | What it returns |
|---|---|---|
| `status` | `GET /api/home` | Live status across all tracked projects |
| `board --project <id>` | `GET /api/board` | Kanban board for a project |
| `sprint_state <label> --project <slug>` | `GET /api/sprints/{label}/state` | Sprint state snapshot |
| `dev_report` | `GET /api/dev-report` | Daily dev report across all tracked projects |

Example follow-up: _"sprint details sprint-5"_ → commander-api runs `sprint_state sprint-5 --project <slug>`.
