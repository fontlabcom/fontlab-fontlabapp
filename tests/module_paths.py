# this_file: tests/module_paths.py
"""Resolve dynamically parameterized module names to their current domain home."""

from fontlabapp._legacy import ALIASES
from pathlib import Path


def module_name(short_name: str) -> str:
    """Return the canonical name for a legacy short name used by a test matrix."""
    name = "fontlabapp." + short_name
    return ALIASES.get(name, name)


def module_file(short_name: str) -> Path:
    """Locate source for AST/wording checks without importing native UI code."""
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / (module_name(short_name).replace(".", "/") + ".py")
    )
