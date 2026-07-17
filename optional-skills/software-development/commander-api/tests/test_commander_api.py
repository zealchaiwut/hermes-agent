"""Tests for commander_api.py dev_report shortcut (issue #61).

AC: commander_api.py has a `dev_report` shortcut that issues GET /api/dev-report;
    a unit test verifies the arg→path mapping without a live server.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "commander_api",
    REPO_ROOT / "optional-skills" / "software-development" / "commander-api" / "scripts" / "commander_api.py",
)
commander_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commander_api)


class TestDevReportShortcut:
    def test_dev_report_in_shortcuts(self):
        """dev_report shortcut exists in SHORTCUTS dict."""
        assert "dev_report" in commander_api.SHORTCUTS

    def test_dev_report_path_is_api_dev_report(self):
        """dev_report shortcut maps to GET /api/dev-report."""
        path_template, path_params, query_params, _help = commander_api.SHORTCUTS["dev_report"]
        assert path_template == "/api/dev-report"

    def test_dev_report_has_no_required_path_params(self):
        """dev_report requires no path parameters — it is a bare GET."""
        _path_template, path_params, _query_params, _help = commander_api.SHORTCUTS["dev_report"]
        assert path_params == []

    def test_dev_report_request_path_built_correctly(self):
        """The GET path resolves to /api/dev-report with no substitution needed."""
        path_template, path_params, _query_params, _help = commander_api.SHORTCUTS["dev_report"]
        path = path_template
        for param in path_params:
            path = path.replace(f"{{{param}}}", "placeholder")
        assert path == "/api/dev-report"
