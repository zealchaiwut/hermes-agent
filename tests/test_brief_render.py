"""Tests for plugins/life_ops/brief_render.py — issue #43 AC items 1-4.

AC coverage:
- AC1: composed brief ends with the footer line when footer.enabled=true
- AC2: brief_render.yaml has footer.enabled defaulting to true
- AC3: load_brief_render_config reads footer.enabled; false suppresses footer
- AC4: both enabled=true and enabled=false paths are tested
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_RENDER_PY = REPO_ROOT / "plugins" / "life_ops" / "brief_render.py"
BRIEF_RENDER_YAML = REPO_ROOT / "plugins" / "life_ops" / "brief_render.yaml"

FOOTER_LINE = (
    '_Dig deeper: reply here — try "sprint details <label>", '
    '"why this advisory", "show week plan"._'
)


def _load_module():
    spec = importlib.util.spec_from_file_location("brief_render", BRIEF_RENDER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBriefRenderYaml:
    def test_yaml_has_footer_enabled_true(self):
        """AC2: brief_render.yaml contains footer.enabled defaulting to true."""
        import yaml

        config = yaml.safe_load(BRIEF_RENDER_YAML.read_text())
        assert config["footer"]["enabled"] is True


class TestLoadBriefRenderConfig:
    def test_returns_enabled_true(self, tmp_path):
        """AC3: load_brief_render_config reads footer.enabled=true."""
        cfg = tmp_path / "brief_render.yaml"
        cfg.write_text("footer:\n  enabled: true\n")
        mod = _load_module()
        result = mod.load_brief_render_config(str(cfg))
        assert result["footer"]["enabled"] is True

    def test_returns_enabled_false(self, tmp_path):
        """AC3: load_brief_render_config reads footer.enabled=false."""
        cfg = tmp_path / "brief_render.yaml"
        cfg.write_text("footer:\n  enabled: false\n")
        mod = _load_module()
        result = mod.load_brief_render_config(str(cfg))
        assert result["footer"]["enabled"] is False


class TestComposeBrief:
    def test_footer_present_when_enabled(self):
        """AC1 & AC4: footer line appears in composed brief when enabled=true."""
        mod = _load_module()
        result = mod.compose_brief(
            ["## Todos\n- Buy milk"],
            config={"footer": {"enabled": True}},
        )
        assert FOOTER_LINE in result

    def test_footer_absent_when_disabled(self):
        """AC3 & AC4: footer line is absent when enabled=false."""
        mod = _load_module()
        result = mod.compose_brief(
            ["## Todos\n- Buy milk"],
            config={"footer": {"enabled": False}},
        )
        assert FOOTER_LINE not in result

    def test_footer_is_last_content_line(self):
        """AC1: footer line is the single trailing line of the composed brief."""
        mod = _load_module()
        result = mod.compose_brief(
            ["## Section"],
            config={"footer": {"enabled": True}},
        )
        stripped = result.rstrip("\n")
        assert stripped.endswith(FOOTER_LINE)
