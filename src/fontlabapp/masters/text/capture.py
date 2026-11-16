# this_file: src/fontlabapp/masters/text/capture.py
# SPDX-License-Identifier: Apache-2.0
"""Bound opening-font facts; never substitute a font with matching names."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from time import monotonic
from fontlabapp.anchors.crossfont.capture import fonts
from fontlabapp.core.scripting import current_package
from fontlabapp.masters.text.model import font_maps


@dataclass(frozen=True)
class Opening:
    """Exact font/master/glyph identities and alternative Unicode assignments."""

    identity: int
    fg_id: int
    master: str
    masters: tuple[str, ...]
    glyphs: tuple[tuple[str, tuple[int, ...], int], ...]

    def maps(self, check: Callable = lambda: None) -> tuple:
        """Use the first font-order encoded alias; return all alias diagnostics."""
        return font_maps(((name, codes) for name, codes, _ in self.glyphs), check=check)


def sources(deadline: float, check: Callable) -> tuple:
    """Expose bounded registered carriers without native FontGate mirror reads."""
    check()
    result = fonts(deadline, checkpoint=check)
    check()
    return result


def _capture(source: Any, check: Callable) -> Opening:
    package, glyphs, masters = source.package, [], []
    for master in package.masters:
        check()
        masters.append(str(master))
    for raw in source.font.glyphs:
        check()
        name = str(raw.name)
        codes = []
        for code in raw.unicodes:
            check()
            codes.append(int(code))
        glyph = package.findName(name)
        check()
        if glyph is None or glyph.isNull:
            raise ValueError("An opening glyph changed or closed during capture.")
        glyphs.append((name, tuple(codes), int(glyph.id)))
    result = Opening(
        int(package.id),
        int(package.fgId),
        str(package.master),
        tuple(masters),
        tuple(glyphs),
    )
    result.maps(check)
    check()
    return result


def read(deadline: float, *, check: Callable = lambda: None) -> Opening:
    """Capture the actual registered opening font and all its masters in order."""
    check = _budget(deadline, check)
    check()
    current = current_package()
    if current is None:
        raise ValueError("Open a font before opening Master Text Comparison.")
    for source in sources(deadline, check):
        check()
        if source.identity == int(current.id):
            result = _capture(source, check)
            if current_package(result.identity) is None:
                raise ValueError(
                    "The opening font changed or closed; reopen this panel."
                )
            return result
    raise ValueError("The opening font is no longer registered; reopen this panel.")


def validate(
    opening: Opening, deadline: float, *, check: Callable = lambda: None
) -> Any:
    """Re-read all relevant facts: same names never authorize a replaced glyph."""
    check = _budget(deadline, check)
    check()
    if current_package(opening.identity) is None:
        raise ValueError("The opening font changed or closed; reopen this panel.")
    for source in sources(deadline, check):
        check()
        if source.identity == opening.identity:
            if _capture(source, check) != opening:
                raise ValueError(
                    "The opening font, glyph identities or masters changed; reopen this panel."
                )
            return source
    raise ValueError("The opening font changed or closed; reopen this panel.")


def _budget(deadline: float, caller: Callable) -> Callable:
    """Keep public capture bounded even when no extra cancellation is supplied."""

    def check() -> None:
        caller()
        if monotonic() >= deadline:
            raise TimeoutError(
                "Opening-font capture expired; no partial result is available."
            )

    return check
