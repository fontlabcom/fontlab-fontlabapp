# this_file: src/fontlabapp/studios/proof_studio/generators/surround.py
# SPDX-License-Identifier: Apache-2.0
"""Glyphs surrounded: every selected glyph between copies of one surround string.

Absorbs the four Scriptmix "Glyphs Surrounded by …" scripts (adapted from
Pedro Arilla's Apache-2.0 Glyphs between scripts). Surround strings: H, HHOHH,
I and nnonn (glyph names, one per character). One line: ``ctx name ctx name …
ctx``; no selection gives the surround string alone.
"""

from . import Generator
from ._context import make, open_tab

GENERATOR = Generator(
    key="surround",
    title="Glyphs surrounded by",
    tab="Pattern strings",
    tab_order=10,
    order=20,
    choices=(("H", "H"), ("HHOHH", "HHOHH"), ("I", "I"), ("nnonn", "nnonn")),
    scripts={
        "H": "Glyphs Surrounded by H",
        "HHOHH": "Glyphs Surrounded by HHOHH",
        "I": "Glyphs Surrounded by I",
        "nnonn": "Glyphs Surrounded by Nnonn",
    },
    make=make,
    open=open_tab,
    uses_selection=True,
)
