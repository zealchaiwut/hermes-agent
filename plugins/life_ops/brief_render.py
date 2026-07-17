"""Compose the Hermes morning brief from per-section render results.

Sections are pre-rendered strings (todos block, training block, dev block, …).
A footer prompt is appended when ``footer.enabled`` is true in
``brief_render.yaml``, giving the user a discoverable path to dig deeper into
any section via skills or slash commands.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "brief_render.yaml"

FOOTER_LINE = (
    '_Dig deeper: reply here — try "sprint details <label>", '
    '"why this advisory", "show week plan"._'
)


def load_brief_render_config(config_path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Load brief render configuration from a YAML file.

    Args:
        config_path: Path to the YAML config. Defaults to brief_render.yaml
                     next to this module.

    Returns:
        Parsed config dict.
    """
    path = Path(config_path) if config_path is not None else _DEFAULT_CONFIG_PATH
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def compose_brief(sections: list[str], config: dict[str, Any] | None = None) -> str:
    """Assemble the morning brief from pre-rendered section strings.

    Args:
        sections: Ordered list of rendered section strings.
        config: Optional pre-loaded config dict. Loads from brief_render.yaml
                when None.

    Returns:
        Composed brief as a single string, with footer appended when enabled.
    """
    if config is None:
        config = load_brief_render_config()

    brief = "\n\n".join(sections)
    if config.get("footer", {}).get("enabled", True):
        brief = brief + "\n\n" + FOOTER_LINE
    return brief
