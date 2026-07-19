"""Tests for issue #16: Simplify redundant 'or None' pattern in config getters.

Each test is anchored to a specific acceptance criterion from the issue.
"""
from __future__ import annotations

import os
import textwrap

import pytest


# ---------------------------------------------------------------------------
# AC: get_perf_coach_url returns None when env var is unset (idiomatic, no 'or None')
# ---------------------------------------------------------------------------


def test_get_perf_coach_url_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("PERF_COACH_URL", raising=False)
    from plugins.life_ops.config import get_perf_coach_url
    assert get_perf_coach_url() is None


def test_get_perf_coach_url_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("PERF_COACH_URL", "http://example.com")
    from plugins.life_ops.config import get_perf_coach_url
    assert get_perf_coach_url() == "http://example.com"


# ---------------------------------------------------------------------------
# AC: get_perf_coach_token returns None when env var is unset
# ---------------------------------------------------------------------------


def test_get_perf_coach_token_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("PERF_COACH_BEARER_TOKEN", raising=False)
    from plugins.life_ops.config import get_perf_coach_token
    assert get_perf_coach_token() is None


def test_get_perf_coach_token_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("PERF_COACH_BEARER_TOKEN", "secret-token")
    from plugins.life_ops.config import get_perf_coach_token
    assert get_perf_coach_token() == "secret-token"


# ---------------------------------------------------------------------------
# AC: source code no longer contains the redundant 'or None' on these lines
# ---------------------------------------------------------------------------


def _return_line(fn) -> str:
    """Return the return statement line(s) from a single-return function."""
    import inspect
    lines = [l.strip() for l in inspect.getsource(fn).splitlines() if l.strip().startswith("return")]
    return "\n".join(lines)


def test_no_or_none_pattern_in_perf_coach_url_getter():
    """The return statement of get_perf_coach_url must not use 'or None'."""
    from plugins.life_ops import config
    assert "or None" not in _return_line(config.get_perf_coach_url), (
        "get_perf_coach_url return statement still contains redundant 'or None'"
    )


def test_no_or_none_pattern_in_perf_coach_token_getter():
    """The return statement of get_perf_coach_token must not use 'or None'."""
    from plugins.life_ops import config
    assert "or None" not in _return_line(config.get_perf_coach_token), (
        "get_perf_coach_token return statement still contains redundant 'or None'"
    )
