# this_file: src/fontlabapp/studios/proof_studio/generators/word_finder.py
# SPDX-License-Identifier: Apache-2.0
"""Word finder: words from the embedded English and Latin list that the font can set.

What: absorbs Scriptmix "Word Finder". Same controls and defaults: Case
(lowercase, Capitalised, UPPERCASE), Must contain (placeholder "e.g. kz"),
Only letters (placeholder "e.g. hamburgefonstiv (empty = any)"), Length 1..20
from 3 to 12. ``make`` runs ``proof_api().find_words`` over the same ``WORDS``
against the font's encoded characters; the proof is the words joined by one
space, exactly what the original copied. No Glyph tab: the original had
Copy only. Pure; reads font facts only.
"""

from fontlabapp.core.scripting import proof_api

from . import Facts, Field, Generator, Options, Proof

NO_FONT = "Open a font with encoded glyphs first."


def make(case: str, options: Options) -> Proof:
    """The filtered words as one space-separated part, with the original subtitle and count."""
    api = proof_api()
    facts = options.facts or Facts()
    available = {chr(code) for code in facts.cmap}
    values = options.values
    words = api.find_words(
        api.WORDS,
        available,
        case,
        str(values.get("must", "")).strip(),
        str(values.get("only", "")).strip(),
        int(values.get("min_len", 3)),
        int(values.get("max_len", 12)),
    )
    count = f"{len(words)} word{'s' if len(words) != 1 else ''}"
    if not available:
        note = f"{NO_FONT} {count}"
    else:
        note = (
            f"{len(api.WORDS)} English and Latin words; showing those the font can set "
            f"with its {len(available)} characters. {count}"
        )
    return Proof((" ".join(words),), note=note)


GENERATOR = Generator(
    key="word-finder",
    title="Word finder",
    tab="Word finder",
    tab_order=50,
    order=10,
    choices=(("lowercase", "lowercase"), ("Capitalised", "Capitalised"), ("UPPERCASE", "UPPERCASE")),
    scripts={"lowercase": "Word Finder", "Capitalised": "Word Finder", "UPPERCASE": "Word Finder"},
    make=make,
    open=None,
    uses_font=True,
    choice_label="Case",
    fields=(
        Field("must", "Must contain", placeholder="e.g. kz"),
        Field("only", "Only letters", placeholder="e.g. hamburgefonstiv (empty = any)"),
        Field("min_len", "Length from", "int", 3, 1, 20),
        Field("max_len", "to", "int", 12, 1, 20),
    ),
)
