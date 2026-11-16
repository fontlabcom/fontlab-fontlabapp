# this_file: src/fontlabapp/kerning/selection.py
# SPDX-License-Identifier: Apache-2.0
"""Plan selected exception deletions and explicit pairs from typed text.

Adapted from the Apache-2.0 fontlab-samples tools. Keep first class membership,
right-class before left-class exception precedence and original slash-token
parsing. Native effective reads use scripting; all writes use kerning_batch.
"""

from collections.abc import Iterable, Mapping
from itertools import pairwise
from typing import Any

from fontlabapp.kerning.edit.model import Edits, Pair, whole_value
from fontlabapp.core.scripting import (
    kerning_class_lists,
    kerning_pair_value,
    kerning_pairs,
)

ExceptionRow = tuple[str, Pair, float, Pair, float]
Values = dict[tuple[Pair, str], tuple[float, bool]]


def class_maps(package: Any, master: str) -> tuple[dict[str, str], dict[str, str]]:
    """Map glyphs to their first native class on each permitted side."""
    left, right, _ = kerning_class_lists(package, master)
    return (
        {g: names[0] for g, names in left.items()},
        {g: names[0] for g, names in right.items()},
    )


def exceptions(
    pairs: Mapping[Pair, float],
    left_classes: Mapping[str, str],
    right_classes: Mapping[str, str],
) -> list[tuple[Pair, float, Pair, float]]:
    """Find the first explicit broader pair, including zero-valued class pairs."""
    found = []
    for (left, right), value in sorted(pairs.items()):
        lc = left_classes.get(left) if not left.startswith("@") else None
        rc = right_classes.get(right) if not right.startswith("@") else None
        for candidate in ((left, rc), (lc, right), (lc, rc)):
            if None not in candidate and candidate in pairs:
                found.append(((left, right), value, candidate, pairs[candidate]))
                break
    return found


def find(package: Any, masters: list[str]) -> list[ExceptionRow]:
    """Return ordered master/pair/value/broader/value rows, never changing master."""
    rows = []
    for master in masters:
        left, right = class_maps(package, master)
        rows.extend(
            (master, *row)
            for row in exceptions(kerning_pairs(package, master), left, right)
        )
    return rows


def exception_plan(rows: Iterable[ExceptionRow]) -> Edits:
    """Delete exactly selected exceptions, including manually selected overrides."""
    edits = {}
    for master, pair, _, _, _ in rows:
        edits.setdefault(master, {})[pair] = None
    return edits


def parse_words(text: str, package: Any) -> list[list[str]]:
    """Resolve characters and slash-delimited glyph names within whitespace words.

    Unknown characters/tokens are skipped, so known neighbors remain adjacent.
    A slash token consumes the rest of its chunk up to the next slash.
    """
    words = []
    for chunk in text.split():
        names, i = [], 0
        while i < len(chunk):
            if chunk[i] == "/":
                j = chunk.find("/", i + 1)
                j = len(chunk) if j < 0 else j
                token = chunk[i + 1 : j]
                if token and package.findName(token) is not None:
                    names.append(token)
                i = j
                continue
            glyph = package.findUnicode(ord(chunk[i]))
            if glyph is not None:
                names.append(glyph.name)
            i += 1
        words.append(names)
    return words


def adjacent_pairs(words: Iterable[list[str]]) -> list[Pair]:
    """Keep unique adjacent pairs inside words in first reading order."""
    return list(dict.fromkeys(pair for names in words for pair in pairwise(names)))


def explicit_pairs(package: Any, master: str) -> dict[Pair, float]:
    """Read only explicit glyph/glyph pairs, preserving zero presence."""
    return {
        pair: value
        for pair, value in kerning_pairs(package, master).items()
        if not any(name.startswith("@") for name in pair)
    }


def current_value(
    kerning: Any, explicit: Mapping[Pair, float], pair: Pair
) -> tuple[float, bool]:
    """Mark explicit glyph pairs; otherwise read native effective kerning or absent zero."""
    if pair in explicit:
        return explicit[pair], True
    return kerning_pair_value(kerning, *pair), False


def text_values(package: Any, masters: list[str], pairs: list[Pair]) -> Values:
    """Read the complete preview before publishing any ticked write action."""
    values = {}
    for master in masters:
        kerning, explicit = package.kerning(master), explicit_pairs(package, master)
        values.update(
            {(pair, master): current_value(kerning, explicit, pair) for pair in pairs}
        )
    return values


def text_plan(
    masters: list[str], ticked: list[Pair], values: Values, mode: str, value: float
) -> Edits:
    """Set or add from displayed effective values, writing only ticked glyph pairs."""
    if mode not in {"add", "set"}:
        raise ValueError(f"Unknown text kerning mode: {mode}")
    value = whole_value(value)
    edits = {}
    for master in masters:
        for pair in ticked:
            if (pair, master) not in values:
                raise ValueError(
                    "Pair preview is incomplete; use Refresh before applying."
                )
            current = values[pair, master][0]
            edits.setdefault(master, {})[pair] = whole_value(
                current + value if mode == "add" else value
            )
    return edits
