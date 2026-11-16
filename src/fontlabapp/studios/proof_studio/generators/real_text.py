# this_file: src/fontlabapp/studios/proof_studio/generators/real_text.py
# SPDX-License-Identifier: Apache-2.0
"""Real text: five prose passages drawn without replacement, English or Spanish.

What: absorbs Scriptmix "Real English Text" and "Real Spanish Text". The 24
original passages per language (Apache-2.0, original to those tools; behaviour
after Pedro Arilla's Real* text scripts) moved to App data
``fontlabapp/proof/real_text_passages.json`` byte for byte. A proof is
``" ".join(sample(passages, 5)) + " "``; text with NUL, NBSP, U+2028 or U+2029
is refused. ``open`` repeats the script; ``open_current`` opens the previewed draw.
The originals write nothing but the new tab; neither does this module.
"""

import json
import random
from importlib.resources import files

from fontlabapp.core.scripting import current_package, proof_studio_backends

from . import Context, Generator, Options, Proof

DRAW_COUNT = 5
NO_FONT = "Open a font before creating a prose proof."
REFUSED = ("\0", " ", " ", " ")


def passages(language: str) -> tuple[str, ...]:
    """The bundled passages of ``language`` (``english`` or ``spanish``), in source order."""
    data = json.loads(files("fontlabapp").joinpath("proof", "real_text_passages.json").read_text(encoding="utf-8"))
    return tuple(data[language])


def proof_text(language: str, rng: random.Random | None = None) -> str:
    """Five distinct passages and a final space, as the absorbed scripts build them."""
    found = passages(language)
    if not found:
        raise ValueError("No proof passages are available.")
    if any(c in passage for passage in found for c in REFUSED):
        raise ValueError("Unsupported proof character; text cannot pass intact.")
    return " ".join((rng or random).sample(found, DRAW_COUNT)) + " "


def make(language: str, options: Options) -> Proof:
    """Five passages of ``language`` (seeded when ``options.seed`` is set)."""
    rng = None if options.seed is None else random.Random(options.seed)
    return Proof((proof_text(language, rng),))


def open_current(language: str, context: Context) -> None:
    """Open the previewed draw in one new tab bound to the current font's id."""
    package = current_package()
    if package is None:
        raise ValueError(NO_FONT)
    proof_studio_backends().text_tab.open_text_tab(context.text(), expected_id=int(package.id))


def open_tab(language: str) -> None:
    """The absorbed script: capture the font, draw five passages, open one new tab."""
    package = current_package()
    if package is None:
        raise ValueError(NO_FONT)
    proof_studio_backends().text_tab.open_text_tab(proof_text(language), expected_id=int(package.id))


GENERATOR = Generator(
    key="real-text",
    title="Real text",
    tab="Real text",
    tab_order=40,
    order=10,
    choices=(("English", "english"), ("Spanish", "spanish")),
    scripts={"english": "Real English Text", "spanish": "Real Spanish Text"},
    make=make,
    open=open_tab,
    seeded=True,
    open_current=open_current,
    choice_label="Language",
)
