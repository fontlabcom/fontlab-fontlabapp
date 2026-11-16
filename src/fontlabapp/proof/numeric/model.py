# this_file: src/fontlabapp/proof/numeric/model.py
# SPDX-License-Identifier: Apache-2.0
"""Calculate local proof measurements from immutable captured font facts.

Keep every selected glyph-layer occurrence, including repeated glyphs. Currency
quotes charge each distinct captured selected glyph once. Values never leave the
worksheet or enter a font/history writer. Dates are evaluated by the native Qt
calendar in the panel, retaining local-time and millisecond semantics.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Facts:
    """Plain UPM, ordered selected advances and whole-font revision instants."""

    upm: float
    advances: tuple[tuple[str, str, float], ...]
    revisions: tuple[tuple[str, int | None], ...]

    def __post_init__(self) -> None:
        if (
            type(self.upm) not in (int, float)
            or not isfinite(self.upm)
            or self.upm <= 0
        ):
            raise ValueError("Font UPM must be positive and finite.")
        for name, layer, width in self.advances:
            if not isinstance(name, str) or not name or not isinstance(layer, str):
                raise ValueError("A captured glyph/layer name is unreadable.")
            if type(width) not in (int, float) or not isfinite(width):
                raise ValueError("A captured advance is not finite.")
        names = set()
        for name, epoch in self.revisions:
            if not isinstance(name, str) or not name or name in names:
                raise ValueError("A revision name is missing or repeated.")
            names.add(name)
            if epoch is not None and type(epoch) is not int:
                raise TypeError(
                    "A revision instant must be integer milliseconds or None."
                )


def calculate(facts: Facts, part: int, values: tuple) -> dict:
    """Return both original numeric recipes plus a 12pt proof-width estimate.

    Integer offset and decimal offset are independent recipes. Integer zoom
    affects the first recipe at12pt; part3 zero fits the absolute total to500pt.
    Decimal scale affects the second recipe; part3 zero means no scaling.
    Part2 retains literal zero and negative percentages. These are estimates,
    without kerning, shaping or a promise of actual view zoom.
    """
    if part not in (2, 3) or len(values) != 6:
        raise ValueError("Choose a complete part2 or part3 worksheet.")
    bounds = ((-20, 20), (0, 1000), (0, 999)) + (
        ((-20, 20), (0, 1000), (0, 1000)) if part == 3 else ((-1000, 1000),) * 3
    )
    for index, (number, (lo, hi)) in enumerate(zip(values, bounds, strict=True)):
        if type(number) not in (int, float) or not isfinite(number):
            raise TypeError("Worksheet values must be finite numbers.")
        if not lo <= number <= hi or (index < 3 and type(number) is not int):
            raise ValueError("A worksheet value is outside its original range/type.")
    offset, zoom, price, delta, scale, quote = values
    rows = tuple(
        (
            name,
            layer,
            width + offset,
            (width + delta) * (1 if part == 3 and scale == 0 else scale / 100),
        )
        for name, layer, width in facts.advances
    )
    total = sum(abs(row[2]) * 12 / facts.upm for row in rows)
    effective = (
        (500 / total * 100 if total else 100) if part == 3 and zoom == 0 else zoom
    )
    count = len({row[0] for row in rows})
    result = {
        "advances_units": rows,
        "proof_widths_pt": tuple(
            row[2] * 12 / facts.upm * effective / 100 for row in rows
        ),
        "effective_zoom_percent": effective,
        "integer_quote_usd": count * price,
        "decimal_quote_usd": count * quote,
    }
    numbers = [*result["proof_widths_pt"], effective, result["decimal_quote_usd"]]
    numbers.extend(row[3] for row in rows)
    if not all(isfinite(number) for number in numbers):
        raise ValueError("The captured magnitude exceeds finite proof arithmetic.")
    return result
