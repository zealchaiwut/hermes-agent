"""Tests for perf_coach.py brief shortcut (issue #61).

AC: perf_coach.py has a `brief` shortcut that issues GET /api/brief/today;
    a unit test verifies the arg→path mapping without a live server.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "perf_coach",
    REPO_ROOT / "optional-skills" / "health" / "perf-coach" / "scripts" / "perf_coach.py",
)
perf_coach = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perf_coach)


class TestBriefShortcut:
    def test_brief_in_endpoints(self):
        """brief endpoint key exists in ENDPOINTS dict."""
        assert "brief" in perf_coach.ENDPOINTS

    def test_brief_path_is_api_brief_today(self):
        """brief endpoint maps to GET /api/brief/today."""
        assert perf_coach.ENDPOINTS["brief"] == "/api/brief/today"

    def test_brief_is_fetchable_endpoint(self):
        """brief is handled by the standard fetch path (not bedtime special-case)."""
        # fetch() looks up ENDPOINTS[key] — confirming 'brief' is a regular
        # endpoint and won't fall through to bedtime_snapshot.
        assert "brief" in perf_coach.ENDPOINTS
        assert perf_coach.ENDPOINTS["brief"] != perf_coach.ENDPOINTS.get("training_load")
