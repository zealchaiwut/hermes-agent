"""Tests for perf-coach brief shortcut — issue #43 AC items 10, 13.

AC coverage:
- AC10: perf_coach.py has brief shortcut calling GET /api/brief/today
- AC13: arg-to-path mapping verified without live server
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PERF_COACH_PY = (
    REPO_ROOT
    / "optional-skills"
    / "health"
    / "perf-coach"
    / "scripts"
    / "perf_coach.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("perf_coach", PERF_COACH_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBriefShortcut:
    def test_brief_in_endpoints(self):
        """AC10: brief endpoint exists in ENDPOINTS registry."""
        mod = _load_module()
        assert "brief" in mod.ENDPOINTS

    def test_brief_maps_to_api_brief_today(self):
        """AC13: brief resolves to GET /api/brief/today (no live server)."""
        mod = _load_module()
        assert mod.ENDPOINTS["brief"] == "/api/brief/today"
