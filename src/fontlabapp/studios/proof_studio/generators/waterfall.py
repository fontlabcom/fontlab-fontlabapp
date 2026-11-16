# this_file: src/fontlabapp/studios/proof_studio/generators/waterfall.py
# SPDX-License-Identifier: Apache-2.0
"""Waterfall: one line of text at a cascade of sizes, from one master's outlines.

What: absorbs Scriptmix "Waterfall". Same controls and defaults: Text
"Hamburgefonstiv 0123", Sizes (px) "10 12 14 18 24 32 48 64 96" (kept in
order, 4..400, invalid tokens ignored by ``proof_api().parse_sizes``) and
Master (default: the active master). Advance widths, no kerning, ``/name``
for unencoded glyphs, as the original. The original's own ``WaterfallView``
draws the whole cascade with red boxes for missing glyphs (``canvas``);
each size is also one part (the Size picker) in TMetrics, on that master's
layer with kerning off, where sizes below 8 px show at 8 px. No Glyph tab:
the original had none. Pure; reads font facts only.
"""

from fontlabapp.core.scripting import proof_api

from . import Field, Generator, Options, Proof
from ._text import glyph_names, names_run

DEFAULT_TEXT = "Hamburgefonstiv 0123"
DEFAULT_SIZES = "10 12 14 18 24 32 48 64 96"
TMETRICS_MIN = 8


def make(_choice: str, options: Options) -> Proof:
    """One part per size: the text, its glyph run as the preview, on the chosen master."""
    values, facts = options.values, options.facts
    text = str(values.get("text", DEFAULT_TEXT))
    sizes = tuple(proof_api().parse_sizes(str(values.get("sizes", DEFAULT_SIZES))))
    if facts is None:
        return Proof((), note="Open a font first.")
    master = str(values.get("master") or facts.master)
    names = glyph_names(text, facts)
    clamp = sum(1 for size in sizes if size < TMETRICS_MIN)
    note = (
        f"Master {master} · {len(names)} glyphs · advance widths, no kerning. "
        "Use /name for unencoded glyphs."
        + (f" TMetrics shows {clamp} size(s) below {TMETRICS_MIN} px at {TMETRICS_MIN} px." if clamp else "")
    )
    return Proof(
        tuple(text for _ in sizes),
        labels=tuple(f"{size:g} px" for size in sizes),
        previews=tuple(names_run(names) for _ in sizes),
        sizes=sizes,
        layers=tuple(master for _ in sizes),
        kerning=False,
        note=note,
        canvas=(tuple(names), sizes, master),
    )


GENERATOR = Generator(
    key="waterfall",
    title="Waterfall",
    tab="Waterfall",
    tab_order=60,
    order=10,
    choices=(("Advance widths, no kerning", "waterfall"),),
    scripts={"waterfall": "Waterfall"},
    make=make,
    open=None,
    uses_font=True,
    part_label="Size",
    canvas="WaterfallView",
    fields=(
        Field("text", "Text", default=DEFAULT_TEXT),
        Field("sizes", "Sizes (px)", default=DEFAULT_SIZES),
        Field("master", "Master", "master"),
    ),
)
