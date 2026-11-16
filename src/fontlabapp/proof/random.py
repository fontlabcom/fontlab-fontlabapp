# this_file: src/fontlabapp/proof/random.py
# SPDX-License-Identifier: Apache-2.0
"""Generate Pedro Arilla's seven random proofs; see NOTICE for provenance.

Keep the complete word data, draw order, index-zero space and final whitespace.
The caller opens a new native tab. Importing or generating touches no host API.
"""

import json
import random
from importlib.resources import files
from string import ascii_lowercase, digits
from typing import Literal

Mode = Literal[
    "numbers",
    "lowercase-nontext",
    "title-nontext",
    "uppercase-nontext",
    "lowercase-words",
    "title-words",
    "uppercase-words",
]
MODES: tuple[Mode, ...] = (
    "numbers",
    "lowercase-nontext",
    "title-nontext",
    "uppercase-nontext",
    "lowercase-words",
    "title-words",
    "uppercase-words",
)
_CASE = {"lowercase": str.lower, "title": str.title, "uppercase": str.upper}


def word_dictionary() -> dict[str, list[str]]:
    """Read all 4,991 source entries, retaining duplicate/compound words and order.

    Return fresh data so a caller cannot change a later proof's dictionary.
    Package read/JSON failures propagate before the caller opens a native tab.
    """
    return json.loads(
        files("fontlabapp")
        .joinpath("proof", "random_proof_words.json")
        .read_text(encoding="utf-8")
    )


def generate(mode: Mode, *, rng: random.Random | None = None) -> str:
    """Build one complete source-defined proof using module RNG or injected RNG.

    Numbers: 200 digit draws alternating with divisor draws from [2,3].
    Non-text: 700 letter draws alternating with divisors [3,5,7]. At each index
    append one space exactly when index % chosen_divisor == 0, including zero.
    Words: one draw per a..z bucket, one trailing space per chosen entry, then
    apply lower/title/upper to the whole text. No sorting, trimming or filtering.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown random proof mode: {mode}")
    choose = random.choice if rng is None else rng.choice
    if mode.endswith("-words"):
        dictionary = word_dictionary()
        text = "".join(choose(dictionary[letter]) + " " for letter in ascii_lowercase)
    else:
        alphabet = list(digits if mode == "numbers" else ascii_lowercase)
        divisors = [2, 3] if mode == "numbers" else [3, 5, 7]
        text = ""
        for index in range(200 if mode == "numbers" else 700):
            text += choose(alphabet)
            if index % choose(divisors) == 0:
                text += " "
    return text if mode == "numbers" else _CASE[mode.split("-")[0]](text)
