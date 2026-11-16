# this_file: src/fontlabapp/studios/kerning_proof/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Proof: text pairs, read-only text proof and staged symmetry."""

from typing import Any

APP = "Kerning Proof"
TAB_TITLES = ("Pairs From Text", "Text Preview", "Symmetry")


def show(*args: Any, **kwargs: Any) -> Any:
    """Open the captured-font proof shell; native acceptance remains separate."""
    from .app import show as open_proof

    return open_proof(*args, **kwargs)
