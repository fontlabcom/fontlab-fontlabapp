# this_file: src/fontlabapp/studios/proof_studio/generators/_text.py
# SPDX-License-Identifier: Apache-2.0
"""Shared text-to-glyph helpers for Word finder, Waterfall and By master.

What: ``glyph_names`` parses proof text with the absorbed panels' grammar
(``fontlabapp.proof.inspect.model.parse_text``: characters by first encoded
glyph, ``/name`` for any glyph, one following space is syntax); a missing
character or name is None. ``names_run`` is the TMetrics form of the same
text: ``/name`` tokens of the glyphs that exist, so TMetrics draws exactly
the glyphs the panels drew. Pure; no Qt, no host.
"""

from fontlabapp.core.scripting import proof_api

from . import Facts


def glyph_names(text: str, facts: Facts) -> list[str | None]:
    """The glyph name (or None when missing) for each character or ``/name`` token of ``text``."""
    return proof_api().parse_text(text, facts.cmap, set(facts.names))


def names_run(names: list[str | None]) -> str:
    """``/a /b …`` for the glyphs that exist, in order (missing ones are left out)."""
    return " ".join(f"/{name}" for name in names if name is not None)

