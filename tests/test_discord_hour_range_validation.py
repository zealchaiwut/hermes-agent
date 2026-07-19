"""Tests for issue #30: validate DISCORD_BEDTIME_HOUR / DISCORD_APPROVALS_HOUR ranges.

Each test is anchored to a specific acceptance criterion from the issue:
  - Out-of-range hour (outside 0-23) must disable the feature and emit a log warning.
  - Out-of-range minute (outside 0-59) must disable the feature and emit a log warning.
  - Valid in-range values must still enable the feature correctly.
"""
from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# AC1 — _read_bedtime_config: out-of-range DISCORD_BEDTIME_HOUR disables + logs
# ---------------------------------------------------------------------------


class TestBedtimeHourValidation:
    def test_hour_above_23_disables_bedtime(self):
        """DISCORD_BEDTIME_HOUR=25 must return enabled=False (AC1)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "25", "DISCORD_BEDTIME_MINUTE": "0"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is False

    def test_hour_negative_disables_bedtime(self):
        """DISCORD_BEDTIME_HOUR=-1 must return enabled=False (AC1)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "-1", "DISCORD_BEDTIME_MINUTE": "0"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is False

    def test_hour_above_23_logs_warning(self, caplog):
        """DISCORD_BEDTIME_HOUR=25 must emit a log warning (AC1)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with caplog.at_level(logging.WARNING, logger="plugins.life_ops.discord_adapter"):
            with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "25", "DISCORD_BEDTIME_MINUTE": "0"}):
                _read_bedtime_config()

        assert any("DISCORD_BEDTIME_HOUR" in r.message for r in caplog.records), (
            "Expected a log warning mentioning DISCORD_BEDTIME_HOUR"
        )

    def test_hour_negative_logs_warning(self, caplog):
        """DISCORD_BEDTIME_HOUR=-1 must emit a log warning (AC1)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with caplog.at_level(logging.WARNING, logger="plugins.life_ops.discord_adapter"):
            with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "-1", "DISCORD_BEDTIME_MINUTE": "0"}):
                _read_bedtime_config()

        assert any("DISCORD_BEDTIME_HOUR" in r.message for r in caplog.records), (
            "Expected a log warning mentioning DISCORD_BEDTIME_HOUR"
        )

    def test_hour_zero_is_valid(self):
        """DISCORD_BEDTIME_HOUR=0 is in range and must enable bedtime (AC1 boundary)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "0", "DISCORD_BEDTIME_MINUTE": "0"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 0

    def test_hour_23_is_valid(self):
        """DISCORD_BEDTIME_HOUR=23 is in range and must enable bedtime (AC1 boundary)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "23", "DISCORD_BEDTIME_MINUTE": "0"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 23


# ---------------------------------------------------------------------------
# AC2 — _read_bedtime_config: out-of-range DISCORD_BEDTIME_MINUTE disables + logs
# ---------------------------------------------------------------------------


class TestBedtimeMinuteValidation:
    def test_minute_above_59_disables_bedtime(self):
        """DISCORD_BEDTIME_MINUTE=60 must return enabled=False (AC2)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "60"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is False

    def test_minute_negative_disables_bedtime(self):
        """DISCORD_BEDTIME_MINUTE=-1 must return enabled=False (AC2)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "-1"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is False

    def test_minute_above_59_logs_warning(self, caplog):
        """DISCORD_BEDTIME_MINUTE=60 must emit a log warning (AC2)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with caplog.at_level(logging.WARNING, logger="plugins.life_ops.discord_adapter"):
            with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "60"}):
                _read_bedtime_config()

        assert any("DISCORD_BEDTIME_MINUTE" in r.message for r in caplog.records), (
            "Expected a log warning mentioning DISCORD_BEDTIME_MINUTE"
        )

    def test_minute_zero_is_valid(self):
        """DISCORD_BEDTIME_MINUTE=0 is in range (AC2 boundary)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "0"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is True
        assert cfg["minute"] == 0

    def test_minute_59_is_valid(self):
        """DISCORD_BEDTIME_MINUTE=59 is in range (AC2 boundary)."""
        from plugins.life_ops.discord_adapter import _read_bedtime_config

        with patch.dict(os.environ, {"DISCORD_BEDTIME_HOUR": "22", "DISCORD_BEDTIME_MINUTE": "59"}):
            cfg = _read_bedtime_config()

        assert cfg["enabled"] is True
        assert cfg["minute"] == 59


# ---------------------------------------------------------------------------
# AC3 — _read_approvals_config: out-of-range DISCORD_APPROVALS_HOUR disables + logs
# ---------------------------------------------------------------------------


class TestApprovalsHourValidation:
    def test_approvals_hour_above_23_disables(self):
        """DISCORD_APPROVALS_HOUR=24 must return enabled=False (AC3)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "24", "DISCORD_APPROVALS_MINUTE": "0"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is False

    def test_approvals_hour_negative_disables(self):
        """DISCORD_APPROVALS_HOUR=-5 must return enabled=False (AC3)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "-5", "DISCORD_APPROVALS_MINUTE": "0"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is False

    def test_approvals_hour_above_23_logs_warning(self, caplog):
        """DISCORD_APPROVALS_HOUR=24 must emit a log warning (AC3)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with caplog.at_level(logging.WARNING, logger="plugins.life_ops.discord_adapter"):
            with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "24", "DISCORD_APPROVALS_MINUTE": "0"}):
                _read_approvals_config()

        assert any("DISCORD_APPROVALS_HOUR" in r.message for r in caplog.records), (
            "Expected a log warning mentioning DISCORD_APPROVALS_HOUR"
        )

    def test_approvals_hour_zero_is_valid(self):
        """DISCORD_APPROVALS_HOUR=0 is in range (AC3 boundary)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "0", "DISCORD_APPROVALS_MINUTE": "0"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 0

    def test_approvals_hour_23_is_valid(self):
        """DISCORD_APPROVALS_HOUR=23 is in range (AC3 boundary)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "23", "DISCORD_APPROVALS_MINUTE": "0"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is True
        assert cfg["hour"] == 23


# ---------------------------------------------------------------------------
# AC4 — _read_approvals_config: out-of-range DISCORD_APPROVALS_MINUTE disables + logs
# ---------------------------------------------------------------------------


class TestApprovalsMinuteValidation:
    def test_approvals_minute_above_59_disables(self):
        """DISCORD_APPROVALS_MINUTE=60 must return enabled=False (AC4)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "9", "DISCORD_APPROVALS_MINUTE": "60"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is False

    def test_approvals_minute_negative_disables(self):
        """DISCORD_APPROVALS_MINUTE=-1 must return enabled=False (AC4)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "9", "DISCORD_APPROVALS_MINUTE": "-1"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is False

    def test_approvals_minute_above_59_logs_warning(self, caplog):
        """DISCORD_APPROVALS_MINUTE=60 must emit a log warning (AC4)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with caplog.at_level(logging.WARNING, logger="plugins.life_ops.discord_adapter"):
            with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "9", "DISCORD_APPROVALS_MINUTE": "60"}):
                _read_approvals_config()

        assert any("DISCORD_APPROVALS_MINUTE" in r.message for r in caplog.records), (
            "Expected a log warning mentioning DISCORD_APPROVALS_MINUTE"
        )

    def test_approvals_minute_59_is_valid(self):
        """DISCORD_APPROVALS_MINUTE=59 is in range (AC4 boundary)."""
        from plugins.life_ops.discord_adapter import _read_approvals_config

        with patch.dict(os.environ, {"DISCORD_APPROVALS_HOUR": "9", "DISCORD_APPROVALS_MINUTE": "59"}):
            cfg = _read_approvals_config()

        assert cfg["enabled"] is True
        assert cfg["minute"] == 59
