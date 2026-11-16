# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/e07_e09.py
# SPDX-License-Identifier: Apache-2.0
"""Exact retained proof, Unicode and review profiles, imported only on use."""
from functools import partial
from importlib import import_module
from typing import Any

from .e07_e09_actions import bindings as bindings


def build_profile(module: str, parent: Any) -> Any:
    """Construct one existing profile without importing every native widget."""
    return import_module(f"{__package__}.{module}").build(parent)


def character_map(part: int, parent: Any) -> Any:
    """Retain the original fixed-style and database-style picker contracts."""
    from PythonQt import QtCore, QtGui
    from fontlabapp.glyphs.character_map.capture import capture
    from fontlabapp.glyphs.character_map.ui import panel_type

    return panel_type(QtCore, QtGui, part)(parent, capture)


PROFILES = {
    "E07": (
        ("Glyph Batch Recipe Settings", partial(build_profile, "glyph_batch_recipe_settings")),
        ("Glyph Proof Batch Wizard", partial(build_profile, "glyph_proof_batch_wizard")),
        ("Glyph Proof Groups", partial(build_profile, "glyph_proof_groups")),
        ("Glyph Proof Worksheet", partial(build_profile, "glyph_proof_worksheet")),
        ("Pair Proof Generator", partial(build_profile, "pair_proof_generator")),
        ("Saved Proof Sample", partial(build_profile, "saved_proof_sample")),
        ("Glyph Proof Layout", partial(build_profile, "glyph_proof_layout")),
        ("Glyph Proof Pad", partial(build_profile, "glyph_proof_pad")),
    ),
    "E08": (
        ("Glyph Coverage Grid", partial(build_profile, "glyph_coverage_grid")),
        ("Glyph Encoding Chart", partial(build_profile, "glyph_encoding_chart")),
        ("Glyph Character Map", partial(character_map, 2)),
        ("Glyph Character Map - Styles", partial(character_map, 3)),
        ("Proof Text Coverage Dialog", partial(build_profile, "proof_text_coverage_dialog")),
        ("Unicode Issues Dock", partial(build_profile, "unicode_issues_dock")),
        ("Apply Unicode Map", partial(build_profile, "apply_unicode_map")),
    ),
    "E09": (
        ("Glyph Mark Colours", partial(build_profile, "glyph_mark_colours")),
        ("Glyph Review Form", partial(build_profile, "glyph_review_form")),
        ("Glyph Review Priorities", partial(build_profile, "glyph_review_priorities")),
        ("Glyph Mark Colour Board", partial(build_profile, "glyph_mark_colour_board")),
        ("Glyph Review Cards", partial(build_profile, "glyph_review_cards")),
    ),
}
