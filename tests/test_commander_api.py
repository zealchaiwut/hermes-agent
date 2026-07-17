"""Tests for commander-api dev_report shortcut — issue #43 AC items 7, 13.

AC coverage:
- AC7: commander_api.py has dev_report shortcut calling GET /api/dev-report
- AC13: arg-to-path mapping verified without live server
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDER_API_PY = (
    REPO_ROOT
    / "optional-skills"
    / "software-development"
    / "commander-api"
    / "scripts"
    / "commander_api.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("commander_api", COMMANDER_API_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestDevReportShortcut:
    def test_dev_report_in_shortcuts(self):
        """AC7: dev_report shortcut exists in SHORTCUTS registry."""
        mod = _load_module()
        assert "dev_report" in mod.SHORTCUTS

    def test_dev_report_maps_to_api_dev_report(self):
        """AC13: dev_report resolves to GET /api/dev-report (no live server)."""
        mod = _load_module()
        path_template, _path_params, _query_params, _help = mod.SHORTCUTS["dev_report"]
        assert path_template == "/api/dev-report"

    def test_dev_report_is_a_get_shortcut(self):
        """AC13: dev_report has no path params (plain GET, no url segments)."""
        mod = _load_module()
        _path, path_params, _query, _help = mod.SHORTCUTS["dev_report"]
        assert path_params == []
