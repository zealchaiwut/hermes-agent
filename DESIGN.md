# Hermes Agent — Design Reference

## Discord Slash Command Pattern

New commands live in `plugins/life_ops/discord_commands.py`, registered via `@tree.command(name=..., description=...)` and passed the shared `tree` object at plugin setup time (see `done`/`dismiss`/`snooze`/`away-on`/`away-off` for the established pattern).

- Owner-only commands reuse the existing gate used by `away-on`/`away-off` — do not invent a second gating mechanism.
- Long-running commands (subprocess-backed) must never block the event loop; run subprocess work off-thread (matching the pattern already used for other subprocess-invoking commands in this file) and report back to the invoking channel/interaction when done.
- Every mutating or process-invoking command replies to the interaction (ack/defer immediately if the work will take more than a few seconds, then follow up) rather than leaving Discord's interaction hanging.

## Morning Chain Conventions

- `deploy/bin/morning-chain.sh` is fork-owned and the canonical reference for correct env/PATH handling when invoking journal or brief scripts from a subprocess: it explicitly extends `PATH` to include `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` before invoking anything that shells out to the `claude` CLI, and uses an `mkdir`-based lock directory (not `flock`, unavailable on macOS) to prevent concurrent runs.
- Any new on-demand trigger (Discord command or otherwise) that re-runs journal or brief generation must reuse this exact PATH extension and locking approach rather than reimplementing it — the journal repo's real deployed scripts and venv live at its repo root, not any of its Commander-managed `main`/`coder`/`tester`/`uat` clone subdirectories.

## Contract File Conventions

- Contract files under `~/.hermes/contracts/*.latest.json` are the hand-off format between producer projects (journal, perf-coach, commander) and the composer (`plugins/life_ops/scripts/morning_brief_composer.py`). Additive-only changes are expected; the composer already tolerates missing fields via `.get()` with graceful degrade.
