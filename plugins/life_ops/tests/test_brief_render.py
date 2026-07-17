"""Tests for brief_render footer feature (issue #61).

Each test is anchored to a specific AC:
  AC-footer-1  compose_brief appends the italic footer when footer.enabled is True (default)
  AC-footer-2  footer absent when footer.enabled is False
  AC-footer-3  load_brief_render_config reads and exposes footer.enabled key
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from plugins.life_ops.scripts.morning_brief_composer import (
    compose_brief,
    load_brief_render_config,
)

_FOOTER_LINE = '_Dig deeper: reply here — try "sprint details <label>", "why this advisory", "show week plan"._'


def _minimal_compose(**kwargs):
    defaults = dict(
        journal_data=None, journal_reason="unavailable",
        perfcoach_data=None, perfcoach_reason="unavailable",
        commander_data=None, commander_reason="unavailable",
    )
    defaults.update(kwargs)
    return compose_brief(**defaults)


# ---------------------------------------------------------------------------
# AC-footer-3: load_brief_render_config exposes footer.enabled
# ---------------------------------------------------------------------------

class TestLoadBriefRenderConfigFooter:
    def test_default_footer_enabled_true(self, tmp_path):
        """footer.enabled defaults to True when key is absent from YAML."""
        yaml_file = tmp_path / "brief_render.yaml"
        yaml_file.write_text("todo_section:\n  fields:\n    glyph: true\n", encoding="utf-8")
        with patch.dict(os.environ, {"BRIEF_RENDER_CONFIG": str(yaml_file)}):
            cfg = load_brief_render_config()
        assert cfg["footer"]["enabled"] is True

    def test_footer_enabled_false_from_yaml(self, tmp_path):
        """footer.enabled is False when YAML sets footer.enabled: false."""
        yaml_file = tmp_path / "brief_render.yaml"
        yaml_file.write_text("footer:\n  enabled: false\n", encoding="utf-8")
        with patch.dict(os.environ, {"BRIEF_RENDER_CONFIG": str(yaml_file)}):
            cfg = load_brief_render_config()
        assert cfg["footer"]["enabled"] is False

    def test_footer_enabled_true_from_yaml(self, tmp_path):
        """footer.enabled is True when YAML explicitly sets footer.enabled: true."""
        yaml_file = tmp_path / "brief_render.yaml"
        yaml_file.write_text("footer:\n  enabled: true\n", encoding="utf-8")
        with patch.dict(os.environ, {"BRIEF_RENDER_CONFIG": str(yaml_file)}):
            cfg = load_brief_render_config()
        assert cfg["footer"]["enabled"] is True


# ---------------------------------------------------------------------------
# AC-footer-1: footer appended when enabled (default)
# ---------------------------------------------------------------------------

class TestComposeBriefFooterEnabled:
    def test_footer_present_when_enabled(self):
        """compose_brief appends the footer line when footer.enabled is True."""
        cfg = {"todo_section": {"fields": {"glyph": True, "key": True, "text": True, "recency": True}, "text_max_chars": 64, "header_format": "To-do · {count} open · /done <key>"}, "footer": {"enabled": True}}
        with patch("plugins.life_ops.scripts.morning_brief_composer.load_brief_render_config", return_value=cfg):
            brief = _minimal_compose()
        assert _FOOTER_LINE in brief

    def test_footer_is_last_non_empty_line(self):
        """The footer is the last meaningful content of the brief."""
        cfg = {"todo_section": {"fields": {"glyph": True, "key": True, "text": True, "recency": True}, "text_max_chars": 64, "header_format": "To-do · {count} open · /done <key>"}, "footer": {"enabled": True}}
        with patch("plugins.life_ops.scripts.morning_brief_composer.load_brief_render_config", return_value=cfg):
            brief = _minimal_compose()
        non_empty_lines = [l for l in brief.splitlines() if l.strip()]
        assert non_empty_lines[-1] == _FOOTER_LINE


# ---------------------------------------------------------------------------
# AC-footer-2: footer suppressed when footer.enabled is False
# ---------------------------------------------------------------------------

class TestComposeBriefFooterDisabled:
    def test_footer_absent_when_disabled(self):
        """compose_brief omits the footer line when footer.enabled is False."""
        cfg = {"todo_section": {"fields": {"glyph": True, "key": True, "text": True, "recency": True}, "text_max_chars": 64, "header_format": "To-do · {count} open · /done <key>"}, "footer": {"enabled": False}}
        with patch("plugins.life_ops.scripts.morning_brief_composer.load_brief_render_config", return_value=cfg):
            brief = _minimal_compose()
        assert _FOOTER_LINE not in brief

    def test_footer_disabled_does_not_alter_other_sections(self):
        """Disabling the footer does not remove other brief sections."""
        cfg = {"todo_section": {"fields": {"glyph": True, "key": True, "text": True, "recency": True}, "text_max_chars": 64, "header_format": "To-do · {count} open · /done <key>"}, "footer": {"enabled": False}}
        with patch("plugins.life_ops.scripts.morning_brief_composer.load_brief_render_config", return_value=cfg):
            brief = _minimal_compose()
        assert "# Morning Brief" in brief
        assert "## Section 1" in brief
        assert "## Section 2" in brief
        assert "## Section 3" in brief
        assert "## Section 4" in brief
