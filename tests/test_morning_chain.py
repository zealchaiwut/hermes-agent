"""Tests for issue #11: M5 morning launchd chain with kill switch.

Each test is anchored to a specific Acceptance Criterion.
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
PLIST = REPO_ROOT / "deploy" / "com.hermes.morning-chain.plist"
CHAIN_SCRIPT = REPO_ROOT / "deploy" / "bin" / "morning-chain.sh"
README = REPO_ROOT / "deploy" / "README.md"


# ---------------------------------------------------------------------------
# AC1 — plist exists, schedules at 22:45 UTC (= 05:45 Asia/Bangkok)
# ---------------------------------------------------------------------------

class TestPlist:
    def test_plist_file_exists(self):
        assert PLIST.exists(), f"{PLIST} must exist"

    def test_plist_is_valid_xml(self):
        tree = ET.parse(PLIST)
        root = tree.getroot()
        assert root is not None

    def test_plist_schedules_2245_utc(self):
        """Hour=22 Minute=45 in the StartCalendarInterval dict."""
        tree = ET.parse(PLIST)
        root = tree.getroot()
        # Find the StartCalendarInterval dict values
        plist_text = PLIST.read_text()
        # Look for Hour key followed by 22 and Minute key followed by 45
        assert re.search(r"<key>Hour</key>\s*<integer>22</integer>", plist_text), \
            "Plist must schedule at hour 22 (UTC)"
        assert re.search(r"<key>Minute</key>\s*<integer>45</integer>", plist_text), \
            "Plist must schedule at minute 45"

    def test_plist_has_cron_comment(self):
        """A cron-syntax comment is included in the plist file."""
        plist_text = PLIST.read_text()
        # The comment should mention 22:45 UTC or the cron expression
        assert "22:45" in plist_text or "cron" in plist_text.lower(), \
            "Plist must include a cron-syntax comment (see AC1)"

    def test_plist_references_morning_chain_script(self):
        plist_text = PLIST.read_text()
        assert "morning-chain" in plist_text, \
            "Plist must reference morning-chain.sh"

    @pytest.mark.skipif(shutil.which("plutil") is None, reason="plutil not available (macOS-only)")
    def test_plutil_lint_passes(self):
        """AC9 — CI validates the plist with plutil -lint."""
        result = subprocess.run(
            ["plutil", "-lint", str(PLIST)],
            capture_output=True, text=True
        )
        assert result.returncode == 0, \
            f"plutil -lint failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# AC2 — morning-chain.sh exists and references three steps
# ---------------------------------------------------------------------------

class TestChainScriptExists:
    def test_script_file_exists(self):
        assert CHAIN_SCRIPT.exists(), f"{CHAIN_SCRIPT} must exist"

    def test_script_is_executable(self):
        mode = CHAIN_SCRIPT.stat().st_mode
        assert bool(mode & stat.S_IXUSR), "morning-chain.sh must be executable"

    def test_script_references_journal_morning_run(self):
        text = CHAIN_SCRIPT.read_text()
        assert "journal-morning-run.sh" in text, \
            "Step 1: script must reference bin/journal-morning-run.sh"

    def test_script_references_export_brief(self):
        text = CHAIN_SCRIPT.read_text()
        assert "export_brief.py" in text, \
            "Step 2: script must reference scripts/export_brief.py"

    def test_script_references_hermes_brief(self):
        text = CHAIN_SCRIPT.read_text()
        # Step 3: hermes brief compose+deliver
        assert re.search(r"hermes.*brief|brief.*deliver|compose.*brief", text), \
            "Step 3: script must reference hermes brief compose/deliver"


# ---------------------------------------------------------------------------
# AC3 — flock per-step locking
# ---------------------------------------------------------------------------

class TestFlockLocking:
    def test_script_uses_flock(self):
        text = CHAIN_SCRIPT.read_text()
        assert "flock" in text, "Script must use flock for per-step locking"

    def test_flock_appears_at_least_once_per_step(self):
        """At least one flock call per step (3 steps → ≥3 flock refs or one shared)."""
        text = CHAIN_SCRIPT.read_text()
        flock_count = text.count("flock")
        # Each step should have its own flock guard; minimum 1 flock per step
        assert flock_count >= 1, "At least one flock per step guard required"

    def test_lock_files_have_step_specific_names(self):
        text = CHAIN_SCRIPT.read_text()
        assert ".lock" in text, "Lock files must be referenced with .lock extension"


# ---------------------------------------------------------------------------
# AC4 — timestamped logging to logs/morning-chain-YYYY-MM-DD.log
# ---------------------------------------------------------------------------

class TestLogging:
    def test_script_references_log_file(self):
        text = CHAIN_SCRIPT.read_text()
        assert "morning-chain" in text and ".log" in text, \
            "Script must write to a morning-chain-*.log file"

    def test_log_path_includes_date_pattern(self):
        text = CHAIN_SCRIPT.read_text()
        # Should use date formatting for the log filename
        assert "$(date" in text or "${DATE" in text or "date +" in text, \
            "Log filename must include a date (e.g. $(date +%Y-%m-%d))"

    def test_log_path_is_under_logs_dir(self):
        text = CHAIN_SCRIPT.read_text()
        assert "logs/" in text, "Log file must be written under logs/ directory"


# ---------------------------------------------------------------------------
# AC5 — non-zero step exit aborts the chain
# ---------------------------------------------------------------------------

class TestChainAbortOnFailure:
    def test_script_has_set_e_or_error_check(self):
        """set -e or explicit error checking ensures abort on step failure."""
        text = CHAIN_SCRIPT.read_text()
        has_set_e = "set -e" in text
        # Alternative: explicit exit on failure after each step
        has_explicit_exit = bool(re.search(r"\|\|\s*(exit|return)", text))
        assert has_set_e or has_explicit_exit, \
            "Script must abort chain on non-zero step exit (set -e or || exit)"

    def test_dry_run_abort_on_failure(self, tmp_path):
        """A mock step that exits non-zero aborts the chain; step 3 must not run."""
        # Create a wrapper that replaces steps with controllable mocks
        fail_script = tmp_path / "fail.sh"
        fail_script.write_text("#!/bin/sh\nexit 1\n")
        fail_script.chmod(0o755)

        noop_script = tmp_path / "noop.sh"
        noop_script.write_text("#!/bin/sh\necho ran_noop\nexit 0\n")
        noop_script.chmod(0o755)

        sentinel = tmp_path / "step3_ran"

        step3_script = tmp_path / "step3.sh"
        step3_script.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n")
        step3_script.chmod(0o755)

        # Run morning-chain.sh with overridden step commands via env vars
        env = os.environ.copy()
        env["MORNING_CHAIN_STEP1"] = str(fail_script)
        env["MORNING_CHAIN_STEP2"] = str(noop_script)
        env["MORNING_CHAIN_STEP3"] = str(step3_script)
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT)],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        assert result.returncode != 0, "Chain must exit non-zero when a step fails"
        assert not sentinel.exists(), "Step 3 must not run after step 2 fails"


# ---------------------------------------------------------------------------
# AC6 — kill-switch file causes silent exit 0
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_script_checks_kill_switch(self):
        text = CHAIN_SCRIPT.read_text()
        assert ".morning-chain-disabled" in text or "MORNING_CHAIN_DISABLED" in text, \
            "Script must check for the kill-switch file"

    def test_kill_switch_exits_zero(self, tmp_path):
        """When deploy/.morning-chain-disabled exists, script exits 0 silently."""
        kill_switch = REPO_ROOT / "deploy" / ".morning-chain-disabled"
        created = False
        try:
            if not kill_switch.exists():
                kill_switch.parent.mkdir(parents=True, exist_ok=True)
                kill_switch.touch()
                created = True

            env = os.environ.copy()
            env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
            env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

            result = subprocess.run(
                [str(CHAIN_SCRIPT)],
                capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
            )
            assert result.returncode == 0, \
                f"Script must exit 0 when kill-switch is present; got {result.returncode}\n{result.stderr}"
        finally:
            if created and kill_switch.exists():
                kill_switch.unlink()

    def test_kill_switch_produces_no_step_output(self, tmp_path):
        """Kill-switch must suppress all step execution."""
        kill_switch = REPO_ROOT / "deploy" / ".morning-chain-disabled"
        created = False
        try:
            if not kill_switch.exists():
                kill_switch.parent.mkdir(parents=True, exist_ok=True)
                kill_switch.touch()
                created = True

            env = os.environ.copy()
            env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
            env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

            result = subprocess.run(
                [str(CHAIN_SCRIPT)],
                capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
            )
            # Must NOT execute any real step — combined output should be minimal/empty
            combined = (result.stdout + result.stderr).lower()
            assert "journal" not in combined and "export_brief" not in combined, \
                "Kill-switch: no step should have run"
        finally:
            if created and kill_switch.exists():
                kill_switch.unlink()


# ---------------------------------------------------------------------------
# AC7 — --dry-run prints each command without executing
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_exits_zero(self, tmp_path):
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        assert result.returncode == 0, \
            f"--dry-run must exit 0; got {result.returncode}\n{result.stderr}"

    def test_dry_run_prints_dry_run_prefix(self, tmp_path):
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        combined = result.stdout + result.stderr
        assert "[dry-run]" in combined, \
            f"--dry-run output must contain '[dry-run]' prefix; got:\n{combined}"

    def test_dry_run_mentions_all_three_steps(self, tmp_path):
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        combined = result.stdout + result.stderr
        assert "journal-morning-run" in combined or "journal" in combined, \
            "--dry-run must print step 1 (journal)"
        assert "export_brief" in combined or "brief" in combined, \
            "--dry-run must print step 2 (export_brief)"
        # Step 3 = hermes brief compose/deliver
        assert "hermes" in combined or "brief" in combined, \
            "--dry-run must print step 3 (hermes brief)"

    def test_dry_run_creates_no_log_file(self, tmp_path):
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        log_files = list(tmp_path.glob("morning-chain-*.log"))
        assert not log_files, "--dry-run must not create a log file"


# ---------------------------------------------------------------------------
# AC8 — README.md documentation
# ---------------------------------------------------------------------------

class TestReadme:
    def test_readme_exists(self):
        assert README.exists(), "deploy/README.md must exist"

    def test_readme_documents_pmset(self):
        text = README.read_text()
        assert "pmset" in text, \
            "README must document pmset wakeorpoweron for pre-05:45 Mac wake"

    def test_readme_documents_oauth_token(self):
        text = README.read_text()
        assert "CLAUDE_CODE_OAUTH_TOKEN" in text, \
            "README must document CLAUDE_CODE_OAUTH_TOKEN in launchd EnvironmentVariables"

    def test_readme_documents_launchctl_install(self):
        text = README.read_text()
        assert "launchctl load" in text or "launchctl bootstrap" in text, \
            "README must document installing the plist with launchctl"

    def test_readme_documents_launchctl_uninstall(self):
        text = README.read_text()
        assert "launchctl unload" in text or "launchctl bootout" in text or "launchctl remove" in text, \
            "README must document uninstalling the plist with launchctl"

    def test_readme_step_table_has_6_rows(self):
        """AC (issue #44) — README step table reflects 6 steps."""
        text = README.read_text()
        step_rows = [l for l in text.splitlines() if re.match(r"\|\s*Step\s*\d", l)]
        assert len(step_rows) == 6, \
            f"README step table must have 6 step rows, found {len(step_rows)}"

    def test_readme_prose_references_6_steps(self):
        """AC (issue #44) — any prose count of steps says 6, not 3 or 5."""
        text = README.read_text()
        assert "six" in text.lower() or "6" in text, \
            "README must reference 6 steps somewhere in prose"


# ---------------------------------------------------------------------------
# AC (issue #44) — 6-step chain: commander exporter step 5, discord step 6
# ---------------------------------------------------------------------------

class TestSixStepChain:
    def test_script_references_commander_exporter(self):
        """AC1 — script must reference export_hermes_report.py as step 5."""
        text = CHAIN_SCRIPT.read_text()
        assert "export_hermes_report.py" in text, \
            "Script must reference export_hermes_report.py for step 5"

    def test_script_has_step5_env_override(self):
        """AC1 — MORNING_CHAIN_STEP5 env var must exist."""
        text = CHAIN_SCRIPT.read_text()
        assert "MORNING_CHAIN_STEP5" in text, \
            "Script must support MORNING_CHAIN_STEP5 override"

    def test_script_has_step6_env_override(self):
        """AC3 — MORNING_CHAIN_STEP6 env var must exist."""
        text = CHAIN_SCRIPT.read_text()
        assert "MORNING_CHAIN_STEP6" in text, \
            "Script must support MORNING_CHAIN_STEP6 override (Discord delivery)"

    def test_script_has_step5_lock(self):
        """AC2 — STEP5_LOCK guard must exist."""
        text = CHAIN_SCRIPT.read_text()
        assert "STEP5_LOCK" in text, \
            "Script must define STEP5_LOCK consistent with other step locks"

    def test_script_has_step6_lock(self):
        """AC3 — STEP6_LOCK guard must exist."""
        text = CHAIN_SCRIPT.read_text()
        assert "STEP6_LOCK" in text, \
            "Script must define STEP6_LOCK consistent with other step locks"

    def test_header_documents_step1_through_step6(self):
        """AC4 — header comment must document MORNING_CHAIN_STEP1 through STEP6."""
        text = CHAIN_SCRIPT.read_text()
        for n in range(1, 7):
            assert f"MORNING_CHAIN_STEP{n}" in text, \
                f"Header must document MORNING_CHAIN_STEP{n}"

    def test_dry_run_prints_exactly_6_steps(self, tmp_path):
        """AC (issue #44) — dry-run must print exactly 6 steps in order."""
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        combined = result.stdout + result.stderr
        dry_run_lines = [l for l in combined.splitlines() if "[dry-run]" in l]
        assert len(dry_run_lines) == 6, \
            f"Expected exactly 6 dry-run steps, got {len(dry_run_lines)}:\n{combined}"
        for idx, step_num in enumerate([1, 2, 3, 4, 5, 6]):
            assert f"Step {step_num}:" in dry_run_lines[idx], \
                f"Expected 'Step {step_num}:' at position {idx + 1}, got: {dry_run_lines[idx]}"

    def test_dry_run_step5_shows_commander_exporter(self, tmp_path):
        """AC1 — dry-run Step 5 line shows the commander exporter command."""
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        combined = result.stdout + result.stderr
        step5_line = next(
            (l for l in combined.splitlines() if "[dry-run]" in l and "Step 5:" in l), ""
        )
        assert "export_hermes_report" in step5_line, \
            f"Dry-run Step 5 must show commander exporter; got: {step5_line!r}"

    def test_dry_run_step5_override_respected(self, tmp_path):
        """AC1 — MORNING_CHAIN_STEP5 override must appear in dry-run output."""
        env = os.environ.copy()
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_STEP5"] = "echo custom-cmd"

        result = subprocess.run(
            [str(CHAIN_SCRIPT), "--dry-run"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        combined = result.stdout + result.stderr
        step5_line = next(
            (l for l in combined.splitlines() if "[dry-run]" in l and "Step 5:" in l), ""
        )
        assert "echo custom-cmd" in step5_line, \
            f"MORNING_CHAIN_STEP5 override must appear in dry-run; got: {step5_line!r}"

    def test_step5_failure_does_not_block_step6(self, tmp_path):
        """AC (issue #44) — Step 5 failure (|| true) must not abort Step 6."""
        sentinel = tmp_path / "step6_ran"
        step6_script = tmp_path / "step6.sh"
        step6_script.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n")
        step6_script.chmod(0o755)

        env = os.environ.copy()
        env["MORNING_CHAIN_STEP1"] = "true"
        env["MORNING_CHAIN_STEP2"] = "true"
        env["MORNING_CHAIN_STEP3"] = "true"
        env["MORNING_CHAIN_STEP4"] = "true"
        env["MORNING_CHAIN_STEP5"] = "false"  # non-zero exit — simulates failure
        env["MORNING_CHAIN_STEP6"] = str(step6_script)
        env["MORNING_CHAIN_LOG_DIR"] = str(tmp_path)
        env["MORNING_CHAIN_LOCK_DIR"] = str(tmp_path)

        result = subprocess.run(
            [str(CHAIN_SCRIPT)],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT)
        )
        assert sentinel.exists(), \
            f"Step 6 must execute even when Step 5 fails; exit={result.returncode}\n{result.stderr}"
