# Dig Deeper — Morning Brief Follow-Up Guide

Each section of the morning brief has a set of slash commands or skills you
can invoke to explore further. Reply in the same conversation where the brief
appeared.

## Section 2 — Todos

| Want to… | Use |
|---|---|
| Mark a todo done | `/done <todo-id>` |
| Dismiss a todo without completing | `/dismiss <todo-id>` |
| Snooze a todo to later | `/snooze <todo-id>` |

## Section 3 — Training

Use the **perf-coach** skill for all training follow-ups:

| Want to… | Skill call |
|---|---|
| Full training load breakdown (CTL/ATL/TSB/ACWR + verdict) | `training_load` |
| Today's planned session | `today` |
| Recent weight trend | `weight` |
| Morning brief snapshot | `brief` → `GET /api/brief/today` |

## Section 4 — Dev Report

Use the **commander-api** skill for all dev follow-ups:

| Want to… | Skill call |
|---|---|
| Live sprint/board status across all projects | `status` |
| Kanban board for a project | `board --project <id>` |
| Sprint state snapshot | `sprint_state <label> --project <slug>` |
| Full morning-brief dev report | `dev_report` → `GET /api/dev-report` |
