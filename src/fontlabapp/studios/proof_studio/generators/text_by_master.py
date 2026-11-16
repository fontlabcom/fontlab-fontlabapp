# this_file: src/fontlabapp/studios/proof_studio/generators/text_by_master.py
# SPDX-License-Identifier: Apache-2.0
"""Text by master: the same text once per master, to compare weight and width.

What: absorbs Scriptmix "Text By Master". Same controls and defaults: Text
"Hamburgefonstiv" (``/name`` for unencoded glyphs) and Size 12..160 px,
default 48. Advance widths, no kerning. The original's own ``MasterRows``
draws one labelled row per master with its width and red boxes for missing
glyphs (``canvas``); each master is also one part (the Master picker) in
TMetrics on that master's layer (``set_layer``), in master order. No Glyph tab: the original had none. Pure; reads font facts.
"""

from . import Field, Generator, Options, Proof
from ._text import glyph_names, names_run

DEFAULT_TEXT = "Hamburgefonstiv"
DEFAULT_SIZE = 48


def make(_choice: str, options: Options) -> Proof:
    """One part per master, in order, at the chosen size with kerning off."""
    values, facts = options.values, options.facts
    if facts is None:
        return Proof((), note="Open a font first.")
    text = str(values.get("text", DEFAULT_TEXT))
    size = float(values.get("size", DEFAULT_SIZE))
    names = glyph_names(text, facts)
    masters = facts.masters
    return Proof(
        tuple(text for _ in masters),
        labels=masters,
        previews=tuple(names_run(names) for _ in masters),
        sizes=tuple(size for _ in masters),
        layers=masters,
        kerning=False,
        note=f"{len(masters)} masters · {len(names)} glyphs · advance widths, no kerning.",
        canvas=(tuple(names), size),
    )


GENERATOR = Generator(
    key="text-by-master",
    title="Text by master",
    tab="By master",
    tab_order=70,
    order=10,
    choices=(("Advance widths, no kerning", "text-by-master"),),
    scripts={"text-by-master": "Text By Master"},
    make=make,
    open=None,
    uses_font=True,
    part_label="Master",
    canvas="MasterRows",
    fields=(
        Field("text", "Text", default=DEFAULT_TEXT),
        Field("size", "Size (px)", "int", DEFAULT_SIZE, 12, 160),
    ),
)
