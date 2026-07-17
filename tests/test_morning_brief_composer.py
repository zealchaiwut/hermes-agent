"""Tests for the morning brief composer script (issue #6).

Each test class is anchored to a specific Acceptance Criterion:
  AC-a  staleness detection for each of the three contracts
  AC-b  todo dedup logic
  AC-c  confidence threshold filtering
  AC-d  dev-category approval-routing annotation
  AC-e  all three individual degradation paths (file missing, file stale)
  AC-f  all-contracts-unavailable producing a valid (all-unavailable) brief
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "morning_brief_composer.py"

sys.path.insert(0, str(REPO_ROOT))
from scripts.morning_brief_composer import (
    compose_brief,
    filter_todos,
    get_today_bangkok,
    get_todo_text,
    load_contract,
    normalize_todo_text,
    render_advisory,
    render_dev_report_section,
    render_journal_section,
    render_session_value,
    render_todo_section,
    render_training_section,
    validate_freshness,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return get_today_bangkok()


def _yesterday() -> str:
    from zoneinfo import ZoneInfo
    from datetime import datetime
    tz = ZoneInfo("Asia/Bangkok")
    now = datetime.now(tz)
    return (now.date() - timedelta(days=1)).isoformat()


def _journal_data(reflection="Morning thoughts.", todos=None, for_date=None):
    return {
        "for_date": for_date or _today(),
        "reflection": {"markdown": reflection},
        "todos": todos or [],
    }


def _perfcoach_data(advisories=None, for_date=None, **extra):
    d = {"for_date": for_date or _today()}
    if advisories is not None:
        d["advisories"] = advisories
    d.update(extra)
    return d


def _commander_data(completed=None, needs_review=None, dead_letter=None, cost="$0.12", for_date=None):
    return {
        "for_date": for_date or _today(),
        "completed": completed or [],
        "needs_review": needs_review or [],
        "dead_letter": dead_letter or [],
        "cost": cost,
    }


# ---------------------------------------------------------------------------
# AC-a  staleness detection (validate_freshness)
# ---------------------------------------------------------------------------

class TestStalenessDetection:
    """AC-a: each contract's for_date is validated against today (Asia/Bangkok)."""

    def test_fresh_contract_passes(self):
        data = {"for_date": _today()}
        assert validate_freshness(data, _today()) is True

    def test_stale_contract_fails(self):
        data = {"for_date": _yesterday()}
        assert validate_freshness(data, _today()) is False

    def test_missing_for_date_fails(self):
        data = {}
        assert validate_freshness(data, _today()) is False

    def test_future_date_fails(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tomorrow = (datetime.now(ZoneInfo("Asia/Bangkok")).date() + timedelta(days=1)).isoformat()
        data = {"for_date": tomorrow}
        assert validate_freshness(data, _today()) is False

    def test_journal_staleness_independent(self, tmp_path):
        """Journal staleness does not affect perfcoach or commander rendering."""
        journal_path = tmp_path / "journal.json"
        journal_path.write_text(
            json.dumps({"for_date": _yesterday(), "reflection": {"markdown": "old"}, "todos": []}),
            encoding="utf-8",
        )
        perfcoach_path = tmp_path / "perf.json"
        perfcoach_path.write_text(json.dumps(_perfcoach_data(advisories=["Rest well."])), encoding="utf-8")
        commander_path = tmp_path / "cmd.json"
        commander_path.write_text(json.dumps(_commander_data(completed=["task-A"])), encoding="utf-8")

        j_data, j_reason = load_contract(journal_path)
        p_data, _ = load_contract(perfcoach_path)
        c_data, _ = load_contract(commander_path)

        brief = compose_brief(j_data, j_reason, p_data, "", c_data, "")
        assert "⚠️ unavailable" in brief       # journal section degraded
        assert "Rest well." in brief            # perfcoach section still renders
        assert "task-A" in brief                # commander section still renders

    def test_perfcoach_staleness_independent(self, tmp_path):
        """Perfcoach staleness does not affect journal or commander."""
        journal_path = tmp_path / "journal.json"
        journal_path.write_text(json.dumps(_journal_data(reflection="Fresh reflection.")), encoding="utf-8")
        perfcoach_path = tmp_path / "perf.json"
        perfcoach_path.write_text(
            json.dumps({"for_date": _yesterday(), "advisories": ["old advice"]}),
            encoding="utf-8",
        )
        commander_path = tmp_path / "cmd.json"
        commander_path.write_text(json.dumps(_commander_data(completed=["task-B"])), encoding="utf-8")

        j_data, j_reason = load_contract(journal_path)
        p_data, p_reason = load_contract(perfcoach_path)
        c_data, c_reason = load_contract(commander_path)

        brief = compose_brief(j_data, j_reason, p_data, p_reason, c_data, c_reason)
        assert "Fresh reflection." in brief
        assert "⚠️ unavailable" in brief        # perfcoach degraded
        assert "task-B" in brief

    def test_commander_staleness_independent(self, tmp_path):
        """Commander staleness does not affect journal or perfcoach."""
        journal_path = tmp_path / "journal.json"
        journal_path.write_text(json.dumps(_journal_data(reflection="Good morning.")), encoding="utf-8")
        perfcoach_path = tmp_path / "perf.json"
        perfcoach_path.write_text(json.dumps(_perfcoach_data(advisories=["Stay hydrated."])), encoding="utf-8")
        commander_path = tmp_path / "cmd.json"
        commander_path.write_text(
            json.dumps({"for_date": _yesterday(), "completed": [], "needs_review": [], "dead_letter": [], "cost": "$0"}),
            encoding="utf-8",
        )

        j_data, j_reason = load_contract(journal_path)
        p_data, p_reason = load_contract(perfcoach_path)
        c_data, c_reason = load_contract(commander_path)

        brief = compose_brief(j_data, j_reason, p_data, p_reason, c_data, c_reason)
        assert "Good morning." in brief
        assert "Stay hydrated." in brief
        assert "⚠️ unavailable" in brief        # commander degraded


# ---------------------------------------------------------------------------
# AC-b  todo dedup logic (normalize_todo_text + filter_todos)
# ---------------------------------------------------------------------------

class TestTodoDedup:
    """AC-b: todos are deduplicated by normalising text (case-insensitive, strip punctuation)."""

    def test_exact_duplicates_removed(self):
        todos = [
            {"text": "Fix the bug", "confidence": 0.9, "priority": 1, "category": "dev"},
            {"text": "Fix the bug", "confidence": 0.8, "priority": 2, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        todos = [
            {"text": "fix the bug", "confidence": 0.9, "priority": 1, "category": "dev"},
            {"text": "Fix The Bug", "confidence": 0.8, "priority": 2, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 1

    def test_punctuation_stripped_for_dedup(self):
        todos = [
            {"text": "Review PR!", "confidence": 0.9, "priority": 1, "category": "dev"},
            {"text": "Review PR", "confidence": 0.8, "priority": 2, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 1

    def test_different_todos_kept(self):
        todos = [
            {"text": "Buy groceries", "confidence": 0.9, "priority": 2, "category": "personal"},
            {"text": "Write tests", "confidence": 0.8, "priority": 1, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 2

    def test_normalize_strips_leading_trailing_punctuation(self):
        assert normalize_todo_text("  Fix bug!  ") == normalize_todo_text("fix bug")

    def test_normalize_case_fold(self):
        assert normalize_todo_text("UPPER") == normalize_todo_text("upper")

    def test_normalize_internal_punctuation_stripped(self):
        normalized = normalize_todo_text("do it, now!")
        assert "," not in normalized
        assert "!" not in normalized


# ---------------------------------------------------------------------------
# get_todo_text — "content" is canonical, "text" is a fallback
# ---------------------------------------------------------------------------

class TestTodoContentField:
    """The journal contract's canonical todo field is "content"; "text" is
    kept only as a fallback for older/alternate producers."""

    def test_content_key_used_when_present(self):
        assert get_todo_text({"content": "Ship the release"}) == "Ship the release"

    def test_falls_back_to_text_when_content_absent(self):
        assert get_todo_text({"text": "Legacy shaped todo"}) == "Legacy shaped todo"

    def test_content_preferred_over_text_when_both_present(self):
        item = {"content": "New shape", "text": "Old shape"}
        assert get_todo_text(item) == "New shape"

    def test_empty_content_falls_back_to_text(self):
        # "" is falsy, so get_todo_text() should fall back to "text" per the
        # `item.get("content") or item.get("text", "")` implementation.
        item = {"content": "", "text": "Fallback text"}
        assert get_todo_text(item) == "Fallback text"

    def test_missing_both_returns_empty_string(self):
        assert get_todo_text({}) == ""

    def test_filter_todos_dedups_content_key_items(self):
        todos = [
            {"content": "Fix the bug", "confidence": 0.9, "priority": 1, "category": "dev"},
            {"content": "Fix the bug", "confidence": 0.8, "priority": 2, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 1

    def test_filter_todos_dedups_across_content_and_text_keys(self):
        """A "content"-shaped item and a "text"-shaped item with the same
        normalized text are still recognized as duplicates."""
        todos = [
            {"content": "Fix the bug", "confidence": 0.9, "priority": 2, "category": "dev"},
            {"text": "Fix the bug", "confidence": 0.8, "priority": 1, "category": "dev"},
        ]
        result = filter_todos(todos)
        assert len(result) == 1

    def test_render_todo_section_uses_content_field(self):
        todos = [{"content": "Ship the release", "confidence": 0.9, "priority": 5, "category": "dev"}]
        data = _journal_data(todos=todos)
        section = render_todo_section(data, "")
        assert "Ship the release" in section

    def test_render_todo_section_content_key_contract_shape(self):
        """End-to-end: a journal contract shaped with "content" (the
        canonical field name) renders correctly through the full section."""
        data = _journal_data(
            todos=[
                {"content": "Write the design doc", "confidence": 0.8, "priority": 3, "category": "dev"},
                {"content": "Water the plants", "confidence": 0.7, "priority": 1, "category": "personal"},
            ]
        )
        section = render_todo_section(data, "")
        assert "Write the design doc" in section
        assert "Water the plants" in section
        assert "<!-- route: approval -->" in section


# ---------------------------------------------------------------------------
# AC-c  confidence threshold filtering
# ---------------------------------------------------------------------------

class TestConfidenceFiltering:
    """AC-c: only todos with confidence >= 0.6 are kept."""

    def test_high_confidence_kept(self):
        todos = [{"text": "Task A", "confidence": 0.9, "priority": 1, "category": "dev"}]
        assert len(filter_todos(todos)) == 1

    def test_exactly_0_6_kept(self):
        todos = [{"text": "Task B", "confidence": 0.6, "priority": 1, "category": "dev"}]
        assert len(filter_todos(todos)) == 1

    def test_below_threshold_excluded(self):
        todos = [{"text": "Task C", "confidence": 0.59, "priority": 1, "category": "dev"}]
        assert len(filter_todos(todos)) == 0

    def test_zero_confidence_excluded(self):
        todos = [{"text": "Task D", "confidence": 0.0, "priority": 1, "category": "dev"}]
        assert len(filter_todos(todos)) == 0

    def test_missing_confidence_excluded(self):
        todos = [{"text": "Task E", "priority": 1, "category": "dev"}]
        assert len(filter_todos(todos)) == 0

    def test_mixed_confidence_filtered_correctly(self):
        todos = [
            {"text": "Keep A", "confidence": 0.8, "priority": 2, "category": "personal"},
            {"text": "Drop B", "confidence": 0.4, "priority": 1, "category": "personal"},
            {"text": "Keep C", "confidence": 0.6, "priority": 3, "category": "personal"},
        ]
        result = filter_todos(todos)
        texts = [t["text"] for t in result]
        assert "Keep A" in texts
        assert "Keep C" in texts
        assert "Drop B" not in texts


# ---------------------------------------------------------------------------
# AC-c (sort)  priority sort descending
# ---------------------------------------------------------------------------

class TestTodoPrioritySort:
    """Part of AC-c: todos are sorted by priority field descending."""

    def test_sorted_descending(self):
        todos = [
            {"text": "Low", "confidence": 0.9, "priority": 1, "category": "dev"},
            {"text": "High", "confidence": 0.9, "priority": 10, "category": "dev"},
            {"text": "Mid", "confidence": 0.9, "priority": 5, "category": "dev"},
        ]
        result = filter_todos(todos)
        priorities = [t["priority"] for t in result]
        assert priorities == sorted(priorities, reverse=True)

    def test_items_with_equal_priority_both_present(self):
        todos = [
            {"text": "Alpha", "confidence": 0.9, "priority": 5, "category": "dev"},
            {"text": "Beta", "confidence": 0.9, "priority": 5, "category": "personal"},
        ]
        result = filter_todos(todos)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AC-d  dev-category approval-routing annotation
# ---------------------------------------------------------------------------

class TestDevCategoryAnnotation:
    """AC-d: items with category='dev' get <!-- route: approval --> annotation."""

    def test_dev_category_annotated(self):
        todos = [{"text": "Deploy feature", "confidence": 0.9, "priority": 5, "category": "dev"}]
        result = filter_todos(todos)
        assert result[0].get("_approval_route") is True

    def test_non_dev_not_annotated(self):
        todos = [{"text": "Go for a run", "confidence": 0.9, "priority": 5, "category": "health"}]
        result = filter_todos(todos)
        assert not result[0].get("_approval_route")

    def test_annotation_in_rendered_output(self):
        todos = [
            {"text": "Ship it", "confidence": 0.9, "priority": 5, "category": "dev"},
            {"text": "Meditate", "confidence": 0.9, "priority": 3, "category": "wellness"},
        ]
        data = _journal_data(todos=todos)
        section = render_todo_section(data, "")
        assert "<!-- route: approval -->" in section

    def test_non_dev_no_approval_comment_in_output(self):
        todos = [{"text": "Read a book", "confidence": 0.9, "priority": 5, "category": "learning"}]
        data = _journal_data(todos=todos)
        section = render_todo_section(data, "")
        assert "<!-- route: approval -->" not in section

    def test_mixed_categories_only_dev_annotated(self):
        todos = [
            {"text": "Code review", "confidence": 0.9, "priority": 8, "category": "dev"},
            {"text": "Buy coffee", "confidence": 0.9, "priority": 7, "category": "personal"},
        ]
        data = _journal_data(todos=todos)
        section = render_todo_section(data, "")
        lines = section.splitlines()
        dev_line = next((l for l in lines if "Code review" in l), "")
        personal_line = next((l for l in lines if "Buy coffee" in l), "")
        assert "<!-- route: approval -->" in dev_line or any(
            "<!-- route: approval -->" in lines[i]
            for i, l in enumerate(lines) if "Code review" in l
        )
        assert "<!-- route: approval -->" not in personal_line


# ---------------------------------------------------------------------------
# AC-e  individual degradation paths
# ---------------------------------------------------------------------------

class TestDegradationPaths:
    """AC-e: each contract degrades independently — file missing or stale."""

    def test_journal_file_missing_shows_unavailable(self, tmp_path):
        missing = tmp_path / "no_file.json"
        data, reason = load_contract(missing)
        section = render_journal_section(data, reason)
        assert "⚠️ unavailable" in section
        assert reason  # reason string is non-empty

    def test_perfcoach_file_missing_shows_unavailable(self, tmp_path):
        missing = tmp_path / "no_perf.json"
        data, reason = load_contract(missing)
        section = render_training_section(data, reason)
        assert "⚠️ unavailable" in section

    def test_commander_file_missing_shows_unavailable(self, tmp_path):
        missing = tmp_path / "no_cmd.json"
        data, reason = load_contract(missing)
        section = render_dev_report_section(data, reason)
        assert "⚠️ unavailable" in section

    def test_journal_stale_shows_unavailable_with_date(self, tmp_path):
        path = tmp_path / "journal.json"
        stale_date = _yesterday()
        path.write_text(
            json.dumps({"for_date": stale_date, "reflection": {"markdown": "old"}, "todos": []}),
            encoding="utf-8",
        )
        data, reason = load_contract(path)
        section = render_journal_section(data, reason)
        assert "⚠️ unavailable" in section
        assert stale_date in section or "stale" in section.lower()

    def test_perfcoach_stale_shows_unavailable_with_date(self, tmp_path):
        path = tmp_path / "perf.json"
        stale_date = _yesterday()
        path.write_text(
            json.dumps({"for_date": stale_date, "advisories": ["old"]}),
            encoding="utf-8",
        )
        data, reason = load_contract(path)
        section = render_training_section(data, reason)
        assert "⚠️ unavailable" in section
        assert stale_date in section or "stale" in section.lower()

    def test_commander_stale_shows_unavailable_with_date(self, tmp_path):
        path = tmp_path / "cmd.json"
        stale_date = _yesterday()
        path.write_text(
            json.dumps({
                "for_date": stale_date,
                "completed": [], "needs_review": [], "dead_letter": [], "cost": "$0",
            }),
            encoding="utf-8",
        )
        data, reason = load_contract(path)
        section = render_dev_report_section(data, reason)
        assert "⚠️ unavailable" in section
        assert stale_date in section or "stale" in section.lower()

    def test_missing_file_exit_code_still_zero(self, tmp_path, monkeypatch):
        """Script never exits non-zero due to missing contract files alone."""
        import subprocess
        env_overrides = {
            "JOURNAL_BRIEF_PATH": str(tmp_path / "nope1.json"),
            "PERFCOACH_BRIEF_PATH": str(tmp_path / "nope2.json"),
            "COMMANDER_REPORT_PATH": str(tmp_path / "nope3.json"),
        }
        import os
        env = {**os.environ, **env_overrides}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"exit non-zero on missing contracts: {result.stderr}"


# ---------------------------------------------------------------------------
# AC-f  all-contracts-unavailable → valid brief printed
# ---------------------------------------------------------------------------

class TestAllContractsUnavailable:
    """AC-f: when all contracts are unavailable, compose_brief still returns a valid markdown brief."""

    def test_all_unavailable_brief_has_four_sections(self):
        brief = compose_brief(None, "file not found", None, "file not found", None, "file not found")
        assert "Journal Reflection" in brief or "Section 1" in brief or "## " in brief
        assert brief.count("⚠️ unavailable") == 4

    def test_all_unavailable_brief_is_string(self):
        brief = compose_brief(None, "missing", None, "missing", None, "missing")
        assert isinstance(brief, str)
        assert len(brief) > 0

    def test_all_unavailable_brief_exit_zero(self, tmp_path):
        import subprocess
        import os
        env = {
            **os.environ,
            "JOURNAL_BRIEF_PATH": str(tmp_path / "x1.json"),
            "PERFCOACH_BRIEF_PATH": str(tmp_path / "x2.json"),
            "COMMANDER_REPORT_PATH": str(tmp_path / "x3.json"),
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "⚠️ unavailable" in result.stdout


# ---------------------------------------------------------------------------
# Section rendering — happy-path smoke tests (not exhaustive; anchored to AC3-7)
# ---------------------------------------------------------------------------

class TestSectionRendering:
    """Happy-path rendering for all four sections."""

    def test_journal_reflection_rendered_verbatim(self):
        data = _journal_data(reflection="## My morning thoughts\n\nFeel great today.")
        section = render_journal_section(data, "")
        assert "## My morning thoughts" in section
        assert "Feel great today." in section

    def test_training_uses_advisories_primary(self):
        data = _perfcoach_data(advisories=["Easy 30-min run.", "Focus on form."])
        section = render_training_section(data, "")
        assert "Easy 30-min run." in section
        assert "Focus on form." in section

    def test_training_falls_back_when_advisories_absent(self):
        data = _perfcoach_data(today="Rest day.", tomorrow="Long run.")
        section = render_training_section(data, "")
        assert "Rest day." in section
        assert "Long run." in section

    def test_training_falls_back_when_advisories_empty(self):
        data = _perfcoach_data(advisories=[], today="Easy jog.", form="Neutral posture.")
        section = render_training_section(data, "")
        assert "Easy jog." in section or "Neutral posture." in section

    def test_dev_report_renders_completed(self):
        data = _commander_data(completed=["feature-X shipped", "bug-Y fixed"])
        section = render_dev_report_section(data, "")
        assert "feature-X shipped" in section
        assert "bug-Y fixed" in section

    def test_dev_report_renders_needs_review(self):
        data = _commander_data(needs_review=["PR #42"])
        section = render_dev_report_section(data, "")
        assert "PR #42" in section

    def test_dev_report_renders_dead_letter(self):
        data = _commander_data(dead_letter=["stalled-task-Z"])
        section = render_dev_report_section(data, "")
        assert "stalled-task-Z" in section

    def test_dev_report_renders_cost(self):
        data = _commander_data(cost="$1.23")
        section = render_dev_report_section(data, "")
        assert "Cost: $1.23" in section

    def test_dry_run_prints_to_stdout(self, tmp_path):
        import subprocess
        import os
        journal = tmp_path / "j.json"
        journal.write_text(json.dumps(_journal_data(reflection="Hello.")), encoding="utf-8")
        perf = tmp_path / "p.json"
        perf.write_text(json.dumps(_perfcoach_data(advisories=["Run easy."])), encoding="utf-8")
        cmd = tmp_path / "c.json"
        cmd.write_text(json.dumps(_commander_data(completed=["task done"])), encoding="utf-8")

        env = {
            **os.environ,
            "JOURNAL_BRIEF_PATH": str(journal),
            "PERFCOACH_BRIEF_PATH": str(perf),
            "COMMANDER_REPORT_PATH": str(cmd),
        }
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Hello." in result.stdout
        assert "Run easy." in result.stdout
        assert "task done" in result.stdout


# ---------------------------------------------------------------------------
# render_advisory — dict advisories (warn / info) and legacy string advisories
# ---------------------------------------------------------------------------

class TestAdvisoryRendering:
    """Advisories are {key, severity: "info"|"warn", text} dicts; plain
    strings are still accepted for legacy producers."""

    def test_warn_severity_gets_warning_prefix(self):
        advisory = {"key": "overtraining", "severity": "warn", "text": "Back off intensity today."}
        assert render_advisory(advisory) == "- ⚠️ Back off intensity today."

    def test_info_severity_has_no_prefix(self):
        advisory = {"key": "hydration", "severity": "info", "text": "Drink more water."}
        assert render_advisory(advisory) == "- Drink more water."

    def test_missing_severity_has_no_prefix(self):
        advisory = {"key": "misc", "text": "Just a note."}
        assert render_advisory(advisory) == "- Just a note."

    def test_legacy_string_advisory_rendered_verbatim(self):
        assert render_advisory("Easy 30-min run.") == "- Easy 30-min run."

    def test_training_section_renders_dict_advisories_warn(self):
        data = _perfcoach_data(advisories=[{"key": "load", "severity": "warn", "text": "High load this week."}])
        section = render_training_section(data, "")
        assert "- ⚠️ High load this week." in section

    def test_training_section_renders_dict_advisories_info(self):
        data = _perfcoach_data(advisories=[{"key": "note", "severity": "info", "text": "Sleep was solid."}])
        section = render_training_section(data, "")
        assert "- Sleep was solid." in section
        assert "⚠️" not in section

    def test_training_section_renders_mixed_warn_and_info_advisories(self):
        data = _perfcoach_data(
            advisories=[
                {"key": "load", "severity": "warn", "text": "Reduce volume."},
                {"key": "note", "severity": "info", "text": "HRV trending up."},
            ]
        )
        section = render_training_section(data, "")
        assert "- ⚠️ Reduce volume." in section
        assert "- HRV trending up." in section


# ---------------------------------------------------------------------------
# render_session_value — today/tomorrow/recent_wrap dicts, including planned=False
# ---------------------------------------------------------------------------

class TestSessionRendering:
    """Sessions are dicts with session_type/intensity/duration_min/notes and
    a "planned" flag; planned=False renders as a rest/nothing-planned line."""

    def test_planned_false_renders_rest_message(self):
        value = {"planned": False}
        assert render_session_value(value) == "Rest / nothing planned"

    def test_planned_false_ignores_other_fields(self):
        """Even if other fields are present, planned=False short-circuits to
        the rest message — a rest day shouldn't show stale session details."""
        value = {"planned": False, "session_type": "easy run", "notes": "stale leftover"}
        assert render_session_value(value) == "Rest / nothing planned"

    def test_full_session_renders_all_present_fields(self):
        value = {
            "planned": True,
            "session_type": "long run",
            "intensity": "moderate",
            "duration_min": 60,
            "notes": "negative split",
        }
        rendered = render_session_value(value)
        assert "session type: long run" in rendered
        assert "intensity: moderate" in rendered
        assert "duration min: 60" in rendered
        assert "notes: negative split" in rendered

    def test_partial_session_skips_missing_fields(self):
        value = {"planned": True, "session_type": "easy run"}
        rendered = render_session_value(value)
        assert rendered == "session type: easy run"

    def test_empty_dict_renders_em_dash(self):
        assert render_session_value({}) == "—"

    def test_legacy_string_value_rendered_verbatim(self):
        assert render_session_value("Long run.") == "Long run."

    def test_training_section_fallback_renders_planned_false_session(self):
        data = _perfcoach_data(today={"planned": False}, tomorrow={"planned": True, "session_type": "intervals"})
        section = render_training_section(data, "")
        assert "**today:** Rest / nothing planned" in section
        assert "**tomorrow:** session type: intervals" in section

    def test_training_section_fallback_dict_session_shape_contract(self):
        """End-to-end: perfcoach contract shaped with dict sessions (the
        canonical shape) renders readable lines, not raw dict reprs."""
        data = _perfcoach_data(
            today={"planned": True, "session_type": "tempo run", "intensity": "hard", "duration_min": 45},
            recent_wrap={"planned": False},
        )
        section = render_training_section(data, "")
        assert "{" not in section  # no raw dict repr leaking into output
        assert "session type: tempo run" in section
        assert "**recent_wrap:** Rest / nothing planned" in section


# ---------------------------------------------------------------------------
# SCHEMA_VERSION 3 — render_training_section extensions (issue #41)
# ---------------------------------------------------------------------------

def _v3_form(ctl=42.5, atl=38.1, tsb=4.4, acwr=1.1, acwr_state="optimal", interpretation="Good form"):
    d = {"ctl": ctl, "atl": atl, "tsb": tsb, "interpretation": interpretation}
    if acwr is not None:
        d["acwr"] = acwr
        d["acwr_state"] = acwr_state
    return d


def _v3_weight(current_kg=75.2, trend_7d="-0.3kg", target_kg=73.0, target_date="2026-08-01", on_track=True):
    return {
        "current_kg": current_kg,
        "trend_7d": trend_7d,
        "target_kg": target_kg,
        "target_date": target_date,
        "on_track": on_track,
    }


def _v3_week_plan(with_rest=False):
    plan = [
        {"day": "Monday", "planned": True, "session_type": "easy run", "duration_min": 30},
        {"day": "Tuesday", "planned": True, "session_type": "strength", "duration_min": 45},
    ]
    if with_rest:
        plan.append({"day": "Wednesday", "planned": False})
    return plan


# AC-13 — Snapshot: v2 advisory-only fixture renders byte-identically

class TestV2SnapshotByteIdentical:
    """AC-13: v2 advisories-only fixture renders byte-identically after the change."""

    _V2_SNAPSHOT = (
        "## Section 3 — Training\n"
        "\n"
        "- Easy 30-min run.\n"
        "- Focus on form."
    )

    def test_v2_advisories_only_snapshot(self):
        data = _perfcoach_data(advisories=["Easy 30-min run.", "Focus on form."])
        section = render_training_section(data, "")
        assert section == self._V2_SNAPSHOT

    def test_v2_dict_advisory_snapshot_unchanged(self):
        data = _perfcoach_data(advisories=[{"key": "load", "severity": "warn", "text": "Back off."}])
        section = render_training_section(data, "")
        assert section == "## Section 3 — Training\n\n- ⚠️ Back off."


# AC-1, AC-2, AC-3 — Form line rendering

class TestV3FormRendering:
    """AC-1/2/3: Form line format, ACWR omission, and full-line omission."""

    def test_form_line_with_all_fields_including_acwr(self):
        data = _perfcoach_data(form=_v3_form())
        section = render_training_section(data, "")
        assert "**Form:** CTL 42.5 · ATL 38.1 · TSB 4.4 · ACWR 1.1 (optimal) — Good form" in section

    def test_form_line_acwr_segment_omitted_when_absent(self):
        form = _v3_form(acwr=None)
        data = _perfcoach_data(form=form)
        section = render_training_section(data, "")
        assert "**Form:** CTL 42.5 · ATL 38.1 · TSB 4.4 — Good form" in section
        assert "ACWR" not in section

    def test_form_line_omitted_when_form_missing(self):
        data = _perfcoach_data(weight=_v3_weight())
        section = render_training_section(data, "")
        assert "**Form:**" not in section

    def test_form_line_omitted_when_form_is_string(self):
        # String "form" belongs to the legacy fallback path, not v3
        data = _perfcoach_data(advisories=[], form="Neutral posture.")
        section = render_training_section(data, "")
        assert "**Form:** CTL" not in section
        # the legacy form string should render via the fallback path
        assert "Neutral posture." in section

    def test_form_line_omitted_when_form_is_none(self):
        data = _perfcoach_data(weight=_v3_weight(), form=None)
        section = render_training_section(data, "")
        assert "**Form:**" not in section


# AC-4, AC-5 — Weight line rendering

class TestV3WeightRendering:
    """AC-4/5: Weight line format and omission when absent."""

    def test_weight_line_renders_on_track(self):
        data = _perfcoach_data(weight=_v3_weight(on_track=True))
        section = render_training_section(data, "")
        assert "**Weight:** 75.2kg · 7d -0.3kg · target 73.0 by 2026-08-01 (on track)" in section

    def test_weight_line_renders_off_pace(self):
        data = _perfcoach_data(weight=_v3_weight(on_track=False))
        section = render_training_section(data, "")
        assert "(off pace)" in section

    def test_weight_line_omitted_when_absent(self):
        data = _perfcoach_data(form=_v3_form())
        section = render_training_section(data, "")
        assert "**Weight:**" not in section


# AC-6, AC-7, AC-8 — Week plan rendering

class TestV3WeekPlanRendering:
    """AC-6/7/8: Week plan block, planned=False rest row, and omission cases."""

    def test_week_plan_renders_header_and_rows(self):
        data = _perfcoach_data(week_plan=_v3_week_plan())
        section = render_training_section(data, "")
        assert "**Week plan:**" in section
        assert "· Monday  easy run 30min" in section
        assert "· Tuesday  strength 45min" in section

    def test_week_plan_planned_false_renders_rest(self):
        data = _perfcoach_data(week_plan=_v3_week_plan(with_rest=True))
        section = render_training_section(data, "")
        assert "· Wednesday  rest" in section

    def test_week_plan_planned_false_no_session_fields(self):
        plan = [{"day": "Thursday", "planned": False, "session_type": "stale", "duration_min": 999}]
        data = _perfcoach_data(week_plan=plan)
        section = render_training_section(data, "")
        assert "· Thursday  rest" in section
        assert "stale" not in section
        assert "999" not in section

    def test_week_plan_omitted_when_missing(self):
        data = _perfcoach_data(form=_v3_form())
        section = render_training_section(data, "")
        assert "**Week plan:**" not in section

    def test_week_plan_omitted_when_empty_list(self):
        data = _perfcoach_data(form=_v3_form(), week_plan=[])
        section = render_training_section(data, "")
        assert "**Week plan:**" not in section


# AC-9 — Advisories heading

class TestV3AdvisoriesHeading:
    """AC-9: Advisories heading present iff at least one v3 block was rendered."""

    def test_advisories_heading_present_when_v3_block_present(self):
        data = _perfcoach_data(
            form=_v3_form(),
            advisories=[{"key": "load", "severity": "warn", "text": "Reduce volume."}],
        )
        section = render_training_section(data, "")
        assert "**Advisories:**" in section
        assert "- ⚠️ Reduce volume." in section

    def test_advisories_heading_omitted_for_v2_advisories_only(self):
        # Pure v2: advisories present, no form/weight/week_plan dicts
        data = _perfcoach_data(advisories=["Run easy."])
        section = render_training_section(data, "")
        assert "**Advisories:**" not in section
        assert "- Run easy." in section

    def test_advisories_heading_omitted_when_advisories_empty_and_v3_blocks(self):
        # v3 blocks present but no advisories → no Advisories heading
        data = _perfcoach_data(form=_v3_form(), advisories=[])
        section = render_training_section(data, "")
        assert "**Advisories:**" not in section

    def test_advisories_heading_appears_with_weight_block(self):
        data = _perfcoach_data(weight=_v3_weight(), advisories=["Stay hydrated."])
        section = render_training_section(data, "")
        assert "**Advisories:**" in section

    def test_advisories_heading_appears_with_week_plan_block(self):
        data = _perfcoach_data(week_plan=_v3_week_plan(), advisories=["Easy week."])
        section = render_training_section(data, "")
        assert "**Advisories:**" in section


# AC-11 — Legacy fallback preserved

class TestV3LegacyFallbackPreserved:
    """AC-11: today/tomorrow/form(str)/recent_wrap fallback is fully preserved."""

    def test_legacy_fallback_renders_when_advisories_empty(self):
        data = _perfcoach_data(advisories=[], today="Rest day.", tomorrow="Long run.")
        section = render_training_section(data, "")
        assert "**today:** Rest day." in section
        assert "**tomorrow:** Long run." in section
        assert "**Advisories:**" not in section

    def test_legacy_fallback_string_form_renders(self):
        data = _perfcoach_data(advisories=[], form="Neutral posture.")
        section = render_training_section(data, "")
        assert "**form:** Neutral posture." in section

    def test_v2_advisories_non_empty_renders_without_heading(self):
        data = _perfcoach_data(advisories=["Rest well.", "Focus on form."])
        section = render_training_section(data, "")
        assert "- Rest well." in section
        assert "- Focus on form." in section
        assert "**Advisories:**" not in section


# AC-12 — No KeyError on partial v3 contracts

class TestV3PartialContracts:
    """AC-12: All field access uses .get() — no KeyError on partial v3 contracts."""

    def test_form_partial_missing_interpretation(self):
        form = {"ctl": 40.0, "atl": 35.0, "tsb": 5.0}  # no interpretation
        data = _perfcoach_data(form=form)
        section = render_training_section(data, "")
        assert "**Form:** CTL 40.0 · ATL 35.0 · TSB 5.0" in section

    def test_form_partial_missing_ctl_atl_tsb(self):
        form = {"interpretation": "Feeling good"}
        data = _perfcoach_data(form=form)
        section = render_training_section(data, "")  # must not raise KeyError
        assert "**Form:**" in section

    def test_weight_partial_missing_on_track(self):
        weight = {"current_kg": 70.0, "trend_7d": "+0.1kg", "target_kg": 68.0, "target_date": "2026-09-01"}
        data = _perfcoach_data(weight=weight)
        section = render_training_section(data, "")  # must not raise KeyError
        assert "**Weight:**" in section

    def test_week_plan_partial_missing_duration(self):
        plan = [{"day": "Friday", "planned": True, "session_type": "swim"}]  # no duration_min
        data = _perfcoach_data(week_plan=plan)
        section = render_training_section(data, "")  # must not raise KeyError
        assert "· Friday" in section

    def test_week_plan_entry_missing_day(self):
        plan = [{"planned": True, "session_type": "run", "duration_min": 20}]  # no day
        data = _perfcoach_data(week_plan=plan)
        section = render_training_section(data, "")  # must not raise KeyError
        assert "**Week plan:**" in section


# AC-14 — Full v3 integration test: order Form → Weight → Week plan → Advisories

class TestV3FullIntegration:
    """AC-14: Full v3 fixture renders in correct order."""

    def test_full_v3_fixture_section_order(self):
        data = _perfcoach_data(
            form=_v3_form(),
            weight=_v3_weight(),
            week_plan=_v3_week_plan(),
            advisories=[{"key": "load", "severity": "info", "text": "Good recovery."}],
        )
        section = render_training_section(data, "")
        form_pos = section.index("**Form:**")
        weight_pos = section.index("**Weight:**")
        plan_pos = section.index("**Week plan:**")
        adv_pos = section.index("**Advisories:**")
        assert form_pos < weight_pos < plan_pos < adv_pos

    def test_full_v3_fixture_all_content_present(self):
        data = _perfcoach_data(
            form=_v3_form(),
            weight=_v3_weight(),
            week_plan=_v3_week_plan(with_rest=True),
            advisories=[{"key": "note", "severity": "info", "text": "Sleep was solid."}],
        )
        section = render_training_section(data, "")
        assert "**Form:**" in section
        assert "**Weight:**" in section
        assert "**Week plan:**" in section
        assert "**Advisories:**" in section
        assert "- Sleep was solid." in section
        assert "· Wednesday  rest" in section


# AC-15 — Per-block omission tests

class TestV3PerBlockOmission:
    """AC-15: Omitting form, weight, or week_plan individually produces correct partial output."""

    def test_omit_form_weight_and_week_plan_present(self):
        data = _perfcoach_data(weight=_v3_weight(), week_plan=_v3_week_plan())
        section = render_training_section(data, "")
        assert "**Form:**" not in section
        assert "**Weight:**" in section
        assert "**Week plan:**" in section

    def test_omit_weight_form_and_week_plan_present(self):
        data = _perfcoach_data(form=_v3_form(), week_plan=_v3_week_plan())
        section = render_training_section(data, "")
        assert "**Weight:**" not in section
        assert "**Form:**" in section
        assert "**Week plan:**" in section

    def test_omit_week_plan_form_and_weight_present(self):
        data = _perfcoach_data(form=_v3_form(), weight=_v3_weight())
        section = render_training_section(data, "")
        assert "**Week plan:**" not in section
        assert "**Form:**" in section
        assert "**Weight:**" in section

    def test_week_plan_empty_list_omitted_form_and_weight_present(self):
        data = _perfcoach_data(form=_v3_form(), weight=_v3_weight(), week_plan=[])
        section = render_training_section(data, "")
        assert "**Week plan:**" not in section
        assert "**Form:**" in section
        assert "**Weight:**" in section


# ---------------------------------------------------------------------------
# Issue #42 — Structured commander contract in render_dev_report_section
# ---------------------------------------------------------------------------

_STATUS_GLYPHS = {
    "shipped": "🚀",
    "in_progress": "⏳",
    "blocked": "⛔",
    "waiting_signoff": "📋",
    "idle": "💤",
}


def _project(
    name="TestProject",
    status="idle",
    in_progress_info=None,
    shipped=None,
    fixed=None,
    stale=None,
    waiting=None,
):
    p = {"name": name, "status": status}
    if in_progress_info is not None:
        p["in_progress"] = in_progress_info
    if shipped is not None:
        p["shipped"] = shipped
    if fixed is not None:
        p["fixed"] = fixed
    if stale is not None:
        p["stale"] = stale
    if waiting is not None:
        p["waiting"] = waiting
    return p


def _cmd_projects(projects, cost="$1.00", for_date=None):
    return {
        "for_date": for_date or _today(),
        "projects": projects,
        "cost": cost,
    }


# AC-42-1: Glyph per status

class TestCommanderProjectGlyphs:
    """AC1: One block per project; header uses correct glyph for each status."""

    def test_shipped_glyph(self):
        data = _cmd_projects([_project(name="Alpha", status="shipped")])
        section = render_dev_report_section(data, "")
        assert "**Alpha** — 🚀 shipped" in section

    def test_in_progress_glyph(self):
        data = _cmd_projects([_project(name="Beta", status="in_progress")])
        section = render_dev_report_section(data, "")
        assert "**Beta** — ⏳ in_progress" in section

    def test_blocked_glyph(self):
        data = _cmd_projects([_project(name="Gamma", status="blocked")])
        section = render_dev_report_section(data, "")
        assert "**Gamma** — ⛔ blocked" in section

    def test_waiting_signoff_glyph(self):
        data = _cmd_projects([_project(name="Delta", status="waiting_signoff")])
        section = render_dev_report_section(data, "")
        assert "**Delta** — 📋 waiting_signoff" in section

    def test_idle_glyph(self):
        data = _cmd_projects([_project(name="Epsilon", status="idle")])
        section = render_dev_report_section(data, "")
        assert "**Epsilon** — 💤 idle" in section

    def test_multiple_projects_each_gets_block(self):
        data = _cmd_projects([
            _project(name="Proj1", status="shipped"),
            _project(name="Proj2", status="idle"),
        ])
        section = render_dev_report_section(data, "")
        assert "**Proj1** — 🚀 shipped" in section
        assert "**Proj2** — 💤 idle" in section


# AC-42-2: in_progress suffix

class TestCommanderInProgressSuffix:
    """AC2: in_progress header appends (sprint_label, percent% — ticket) when in_progress sub-key present."""

    def test_in_progress_suffix_appended(self):
        data = _cmd_projects([_project(
            name="Hermes",
            status="in_progress",
            in_progress_info={"sprint_label": "Sprint 2", "percent": 75, "ticket": "HRM-42"},
        )])
        section = render_dev_report_section(data, "")
        assert "(Sprint 2, 75% — HRM-42)" in section

    def test_in_progress_suffix_absent_when_no_in_progress_key(self):
        data = _cmd_projects([_project(name="Hermes", status="in_progress")])
        section = render_dev_report_section(data, "")
        # header has status but no parenthetical suffix with percent
        assert "%" not in section

    def test_in_progress_suffix_not_on_other_statuses(self):
        data = _cmd_projects([_project(
            name="Hermes",
            status="shipped",
            in_progress_info={"sprint_label": "Sprint 2", "percent": 100, "ticket": "HRM-1"},
        )])
        section = render_dev_report_section(data, "")
        # Only in_progress status gets the suffix
        assert "(Sprint 2, 100% — HRM-1)" not in section


# AC-42-3: Compact counts suffix

class TestCommanderCountsSuffix:
    """AC3: Header includes a compact counts suffix when any bucket is non-empty."""

    def test_counts_suffix_present_when_shipped_non_empty(self):
        data = _cmd_projects([_project(
            name="Alpha",
            status="shipped",
            shipped=[{"label": "v1", "goal": "Ship it", "done": 1, "pr_number": 10}],
        )])
        section = render_dev_report_section(data, "")
        header_line = next(l for l in section.splitlines() if "**Alpha**" in l)
        # should contain some count indicator with '1'
        assert "1" in header_line

    def test_counts_suffix_absent_when_all_buckets_empty(self):
        data = _cmd_projects([_project(name="Idle", status="idle")])
        section = render_dev_report_section(data, "")
        # idle project with no buckets: header should be just name/glyph/status, no extra parens with counts
        header_line = next(l for l in section.splitlines() if "**Idle**" in l)
        assert "**Idle** — 💤 idle" == header_line.strip()


# AC-42-4: Sub-bullet order (Shipped → Fixed → Stale → Waiting)

class TestCommanderBucketOrder:
    """AC4: Sub-bullets rendered only for non-empty buckets in order Shipped→Fixed→Stale→Waiting."""

    def test_bucket_order(self):
        data = _cmd_projects([_project(
            name="Hermes",
            status="in_progress",
            shipped=[{"label": "v1", "goal": "g", "done": 1, "pr_number": 1}],
            fixed=[{"issue_number": 10, "title": "Bug fix"}],
            stale=[{"kind": "blocked", "issue_number": 20, "age_days": 2, "type": "review", "title": "T"}],
            waiting=[{"label": "sec", "ticket_count": 3, "estimated_hours": 5}],
        )])
        section = render_dev_report_section(data, "")
        shipped_pos = section.index("Shipped:")
        fixed_pos = section.index("Fixed:")
        stale_pos = section.index("Stale:")
        waiting_pos = section.index("Waiting:")
        assert shipped_pos < fixed_pos < stale_pos < waiting_pos

    def test_empty_buckets_omitted(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            fixed=[{"issue_number": 5, "title": "T"}],
        )])
        section = render_dev_report_section(data, "")
        assert "Shipped:" not in section
        assert "Fixed:" in section
        assert "Stale:" not in section
        assert "Waiting:" not in section


# AC-42-5: Shipped bullet format

class TestCommanderShippedBullets:
    """AC5: Shipped bullets render as '- Shipped: {label} "{goal}" ({done} done, PR #{pr_number})'."""

    def test_shipped_bullet_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            shipped=[{"label": "feature/auth", "goal": "Add OAuth login", "done": 3, "pr_number": 101}],
        )])
        section = render_dev_report_section(data, "")
        assert '- Shipped: feature/auth "Add OAuth login" (3 done, PR #101)' in section

    def test_shipped_multiple_items(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            shipped=[
                {"label": "a", "goal": "A goal", "done": 1, "pr_number": 1},
                {"label": "b", "goal": "B goal", "done": 2, "pr_number": 2},
            ],
        )])
        section = render_dev_report_section(data, "")
        assert '- Shipped: a "A goal" (1 done, PR #1)' in section
        assert '- Shipped: b "B goal" (2 done, PR #2)' in section


# AC-42-6: Fixed bullet format

class TestCommanderFixedBullets:
    """AC6: Fixed bullets render as '- Fixed: #{issue_number} {title}'."""

    def test_fixed_bullet_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            fixed=[{"issue_number": 55, "title": "Fix memory leak"}],
        )])
        section = render_dev_report_section(data, "")
        assert "- Fixed: #55 Fix memory leak" in section

    def test_fixed_multiple_items(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            fixed=[
                {"issue_number": 10, "title": "Bug A"},
                {"issue_number": 11, "title": "Bug B"},
            ],
        )])
        section = render_dev_report_section(data, "")
        assert "- Fixed: #10 Bug A" in section
        assert "- Fixed: #11 Bug B" in section


# AC-42-7: Stale bullet formats (three kinds)

class TestCommanderStaleBullets:
    """AC7: Stale bullets cover blocked, waiting_signoff, and backlog kinds."""

    def test_stale_blocked_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[{"kind": "blocked", "issue_number": 60, "age_days": 5, "type": "review", "title": "Old PR"}],
        )])
        section = render_dev_report_section(data, "")
        assert "- Stale: #60 blocked 5d (review) — Old PR" in section

    def test_stale_waiting_signoff_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[{"kind": "waiting_signoff", "label": "feature/deploy", "age_days": 3}],
        )])
        section = render_dev_report_section(data, "")
        assert "- Stale: feature/deploy awaiting sign-off 3d" in section

    def test_stale_backlog_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[{"kind": "backlog", "label": "v2.0", "age_days": 14, "ticket_count": 7}],
        )])
        section = render_dev_report_section(data, "")
        assert "- Stale: v2.0 backlog untouched 14d (7 tickets)" in section

    def test_all_three_stale_kinds_in_one_project(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[
                {"kind": "blocked", "issue_number": 60, "age_days": 5, "type": "review", "title": "Old PR"},
                {"kind": "waiting_signoff", "label": "feature/deploy", "age_days": 3},
                {"kind": "backlog", "label": "v2.0", "age_days": 14, "ticket_count": 7},
            ],
        )])
        section = render_dev_report_section(data, "")
        assert "- Stale: #60 blocked 5d (review) — Old PR" in section
        assert "- Stale: feature/deploy awaiting sign-off 3d" in section
        assert "- Stale: v2.0 backlog untouched 14d (7 tickets)" in section


# AC-42-8: Waiting bullet format

class TestCommanderWaitingBullets:
    """AC8: Waiting bullets render as '- Waiting: {label} sign-off ({ticket_count} tickets, ~{estimated_hours}h)'."""

    def test_waiting_bullet_format(self):
        data = _cmd_projects([_project(
            name="P",
            status="waiting_signoff",
            waiting=[{"label": "security-review", "ticket_count": 4, "estimated_hours": 8}],
        )])
        section = render_dev_report_section(data, "")
        assert "- Waiting: security-review sign-off (4 tickets, ~8h)" in section

    def test_waiting_multiple_items(self):
        data = _cmd_projects([_project(
            name="P",
            status="waiting_signoff",
            waiting=[
                {"label": "sec", "ticket_count": 2, "estimated_hours": 4},
                {"label": "qa", "ticket_count": 1, "estimated_hours": 2},
            ],
        )])
        section = render_dev_report_section(data, "")
        assert "- Waiting: sec sign-off (2 tickets, ~4h)" in section
        assert "- Waiting: qa sign-off (1 tickets, ~2h)" in section


# AC-42-9: Idle collapse

class TestCommanderIdleCollapse:
    """AC9: An idle project with all empty buckets collapses to header only."""

    def test_idle_project_no_sub_bullets(self):
        data = _cmd_projects([_project(name="Idle", status="idle")])
        section = render_dev_report_section(data, "")
        assert "**Idle** — 💤 idle" in section
        assert "Shipped:" not in section
        assert "Fixed:" not in section
        assert "Stale:" not in section
        assert "Waiting:" not in section

    def test_idle_project_with_all_empty_lists_collapses(self):
        data = _cmd_projects([_project(
            name="Idle",
            status="idle",
            shipped=[],
            fixed=[],
            stale=[],
            waiting=[],
        )])
        section = render_dev_report_section(data, "")
        assert "**Idle** — 💤 idle" in section
        assert "Shipped:" not in section


# AC-42-10: Dict-or-string tolerance

class TestCommanderDictOrString:
    """AC10: Plain string bucket items render verbatim as bullet text."""

    def test_string_shipped_item_verbatim(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            shipped=["plain shipped string"],
        )])
        section = render_dev_report_section(data, "")
        assert "- plain shipped string" in section

    def test_string_fixed_item_verbatim(self):
        data = _cmd_projects([_project(
            name="P",
            status="shipped",
            fixed=["plain fixed string"],
        )])
        section = render_dev_report_section(data, "")
        assert "- plain fixed string" in section

    def test_string_stale_item_verbatim(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=["plain stale string"],
        )])
        section = render_dev_report_section(data, "")
        assert "- plain stale string" in section

    def test_string_waiting_item_verbatim(self):
        data = _cmd_projects([_project(
            name="P",
            status="waiting_signoff",
            waiting=["plain waiting string"],
        )])
        section = render_dev_report_section(data, "")
        assert "- plain waiting string" in section

    def test_mixed_dict_and_string_items(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[
                {"kind": "blocked", "issue_number": 1, "age_days": 2, "type": "t", "title": "T"},
                "plain stale string",
            ],
        )])
        section = render_dev_report_section(data, "")
        assert "- Stale: #1 blocked 2d (t) — T" in section
        assert "- plain stale string" in section


# AC-42-11: Missing sub-keys — no KeyError

class TestCommanderMissingSubkeys:
    """AC11: Missing project sub-keys default cleanly with no KeyError."""

    def test_missing_in_progress_key_no_error(self):
        data = _cmd_projects([_project(name="P", status="in_progress")])
        section = render_dev_report_section(data, "")
        assert "**P** — ⏳ in_progress" in section  # rendered without suffix

    def test_missing_all_buckets_no_error(self):
        data = _cmd_projects([{"name": "Bare", "status": "idle"}])
        section = render_dev_report_section(data, "")
        assert "**Bare** — 💤 idle" in section

    def test_empty_stale_item_dict_no_error(self):
        data = _cmd_projects([_project(
            name="P",
            status="in_progress",
            stale=[{}],
        )])
        section = render_dev_report_section(data, "")  # must not raise KeyError
        assert "**P** — ⏳ in_progress" in section


# AC-42-12: projects key takes precedence over legacy flat keys

class TestCommanderProjectsPrecedence:
    """AC12: When both data.projects and legacy flat keys are present, projects takes precedence."""

    def test_projects_wins_over_legacy_keys(self):
        data = {
            "for_date": _today(),
            "projects": [_project(name="ProjectMode", status="idle")],
            "completed": ["legacy-task"],
            "needs_review": ["legacy-pr"],
            "dead_letter": ["legacy-stale"],
            "cost": "$2.00",
        }
        section = render_dev_report_section(data, "")
        assert "**ProjectMode** — 💤 idle" in section
        assert "legacy-task" not in section
        assert "**Completed:**" not in section


# AC-42-13: Empty/missing projects falls through to legacy path byte-for-byte

class TestCommanderLegacyFallthrough:
    """AC13: When data.projects is missing or empty list, falls through to legacy code path."""

    def test_missing_projects_key_uses_legacy(self):
        data = _commander_data(completed=["task-A"], needs_review=[], dead_letter=[], cost="$0.50")
        section = render_dev_report_section(data, "")
        assert "**Completed:**" in section
        assert "task-A" in section

    def test_empty_projects_list_uses_legacy(self):
        data = {
            "for_date": _today(),
            "projects": [],
            "completed": ["task-B"],
            "needs_review": [],
            "dead_letter": [],
            "cost": "$0.75",
        }
        section = render_dev_report_section(data, "")
        assert "**Completed:**" in section
        assert "task-B" in section
        assert "projects" not in section.lower() or "**" not in section.split("projects")[0][-5:]

    def test_empty_projects_no_project_headers(self):
        data = {
            "for_date": _today(),
            "projects": [],
            "completed": [],
            "needs_review": [],
            "dead_letter": [],
            "cost": "$0.00",
        }
        section = render_dev_report_section(data, "")
        # No project-mode header pattern (bold-name — glyph)
        assert " — 🚀" not in section
        assert " — ⏳" not in section
        assert " — 💤" not in section


# AC-42-14: Cost line unchanged in both paths

class TestCommanderCostLine:
    """AC14: Trailing Cost: {cost} line rendered unchanged in both contract paths."""

    def test_cost_in_projects_path(self):
        data = _cmd_projects([_project(name="P", status="idle")], cost="$3.14")
        section = render_dev_report_section(data, "")
        assert "Cost: $3.14" in section

    def test_cost_in_legacy_path(self):
        data = _commander_data(cost="$9.99")
        section = render_dev_report_section(data, "")
        assert "Cost: $9.99" in section


# AC-42-15: Snapshot — legacy flat contract output is byte-for-byte identical

class TestCommanderLegacySnapshot:
    """AC15: Legacy flat contract produces exactly the same output as before this change."""

    _LEGACY_SNAPSHOT = (
        "## Section 4 — Overnight Dev Report\n"
        "\n"
        "**Completed:**\n"
        "- feature-X shipped\n"
        "- bug-Y fixed\n"
        "\n"
        "**Needs Review:**\n"
        "- PR #42\n"
        "\n"
        "**Dead Letter:** (none)\n"
        "\n"
        "Cost: $0.12"
    )

    def test_legacy_snapshot_byte_identical(self):
        data = _commander_data(
            completed=["feature-X shipped", "bug-Y fixed"],
            needs_review=["PR #42"],
            dead_letter=[],
            cost="$0.12",
        )
        section = render_dev_report_section(data, "")
        assert section == self._LEGACY_SNAPSHOT

    def test_legacy_all_none_snapshot(self):
        data = _commander_data(completed=[], needs_review=[], dead_letter=[], cost="$0.00")
        section = render_dev_report_section(data, "")
        assert "**Completed:** (none)" in section
        assert "**Needs Review:** (none)" in section
        assert "**Dead Letter:** (none)" in section
        assert "Cost: $0.00" in section


# AC-42-16: Fixture test covering all features

class TestCommanderFullFixture:
    """AC16: Fixture test covers per-project blocks, all three stale kinds, and idle collapse."""

    def _full_fixture_data(self):
        return _cmd_projects([
            _project(
                name="Hermes",
                status="in_progress",
                in_progress_info={"sprint_label": "Sprint 2", "percent": 75, "ticket": "HRM-42"},
                shipped=[{"label": "feature/auth", "goal": "Add OAuth login", "done": 3, "pr_number": 101}],
                fixed=[{"issue_number": 55, "title": "Fix memory leak"}],
                stale=[
                    {"kind": "blocked", "issue_number": 60, "age_days": 5, "type": "review", "title": "Stale PR"},
                    {"kind": "waiting_signoff", "label": "feature/deploy", "age_days": 3},
                    {"kind": "backlog", "label": "v2.0", "age_days": 14, "ticket_count": 7},
                ],
                waiting=[{"label": "security-review", "ticket_count": 4, "estimated_hours": 8}],
            ),
            _project(name="IdleProj", status="idle"),
        ], cost="$1.50")

    def test_full_fixture_in_progress_header(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "**Hermes** — ⏳ in_progress" in section
        assert "(Sprint 2, 75% — HRM-42)" in section

    def test_full_fixture_shipped_bullet(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert '- Shipped: feature/auth "Add OAuth login" (3 done, PR #101)' in section

    def test_full_fixture_fixed_bullet(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "- Fixed: #55 Fix memory leak" in section

    def test_full_fixture_all_stale_kinds(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "- Stale: #60 blocked 5d (review) — Stale PR" in section
        assert "- Stale: feature/deploy awaiting sign-off 3d" in section
        assert "- Stale: v2.0 backlog untouched 14d (7 tickets)" in section

    def test_full_fixture_waiting_bullet(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "- Waiting: security-review sign-off (4 tickets, ~8h)" in section

    def test_full_fixture_idle_collapse(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "**IdleProj** — 💤 idle" in section
        # idle project should not introduce Shipped:/Fixed:/Stale:/Waiting: for itself
        # (we already test via the general assertions above that these labels do appear
        # once for Hermes — we just verify IdleProj does not duplicate them by checking
        # count of occurrences is exactly 1 for each label)
        assert section.count("Shipped:") == 1
        assert section.count("Fixed:") == 1
        assert section.count("Stale:") == 3  # three stale items
        assert section.count("Waiting:") == 1

    def test_full_fixture_cost_line(self):
        section = render_dev_report_section(self._full_fixture_data(), "")
        assert "Cost: $1.50" in section
