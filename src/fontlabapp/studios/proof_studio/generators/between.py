# this_file: src/fontlabapp/studios/proof_studio/generators/between.py
# SPDX-License-Identifier: Apache-2.0
"""Glyphs between: each selected glyph interleaved with one character class.

Absorbs the four Scriptmix "Glyphs Between …" scripts (adapted from Pedro
Arilla's Apache-2.0 Glyphs between scripts). Character-class sources:
lowercase a-z, uppercase A-Z, lining figures zero-nine, oldstyle figures
zero.osf-nine.osf. Per selected occurrence: ``name c1 name c2 … name`` then
an empty line; one final empty line; no selection gives one empty line.
"""

from . import Generator
from ._context import make, open_tab

GENERATOR = Generator(
    key="between",
    title="Glyphs between",
    tab="Pattern strings",
    tab_order=10,
    order=10,
    choices=(
        ("Lining figures", "lining"),
        ("Lowercase", "lowercase"),
        ("Oldstyle figures", "oldstyle"),
        ("Uppercase", "uppercase"),
    ),
    scripts={
        "lining": "Glyphs Between Lining Figures",
        "lowercase": "Glyphs Between Lowercase",
        "oldstyle": "Glyphs Between Oldstyle Figures",
        "uppercase": "Glyphs Between Uppercase",
    },
    make=make,
    open=open_tab,
    uses_selection=True,
)
