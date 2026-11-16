# this_file: src/fontlabapp/masters/text/model.py
# SPDX-License-Identifier: Apache-2.0
"""Detached all-master word proofs, preserving the MasterBlaster workflow.

Character mode is the original per-character lookup. Explicit names mode adds
``/name`` tokens ending at slash or whitespace; one following ASCII space is
grammar, as in proof.parse_text. Unicode assignments are alternatives, and
font-order aliases use the first encoded glyph. No native imports or mutation.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass


def checkpoint(deadline: float, clock: Callable, cancelled: Callable) -> None:
    """One cooperative deadline/cancellation rule across the complete workflow."""
    if cancelled():
        raise InterruptedError("Master Text Comparison was cancelled.")
    if clock() >= deadline:
        raise TimeoutError(
            "Master Text Comparison exceeded its deadline; a created proof may remain."
        )


@dataclass(frozen=True)
class Omission:
    """One unavailable character/token, indexed in its original comma field."""

    word: int
    offset: int
    text: str
    kind: str


@dataclass(frozen=True)
class Comparison:
    """Complete exact rows and human text, including every trailing delimiter."""

    words: tuple[tuple[str, ...], ...]
    rows: tuple[tuple[tuple[str | None, str], ...], ...]
    preview: str
    dropped: tuple[Omission, ...]
    empty_words: tuple[int, ...]


class NoUsableGlyphs(ValueError):
    """Retain full empty-sanitation diagnostics without a misleading blank proof."""

    def __init__(self, comparison: Comparison) -> None:
        super().__init__("No usable glyphs remain after sanitation; no proof opened.")
        self.comparison = comparison


def font_maps(
    facts: Iterable[tuple[str, tuple[int, ...]]], *, check: Callable = lambda: None
) -> tuple[dict[int, str], set[str], tuple]:
    """Resolve alternative Unicode assignments with proof.font_maps' first policy."""
    cmap, names, aliases = {}, set(), []
    for name, codes in facts:
        check()
        if not name or name in names:
            raise ValueError(
                "Glyph names must be nonempty and unique in the source font."
            )
        names.add(name)
        for code in codes:
            check()
            if (
                type(code) is not int
                or not 0 <= code <= 0x10FFFF
                or 0xD800 <= code <= 0xDFFF
            ):
                raise ValueError("The source font contains an invalid Unicode scalar.")
            if code in cmap and cmap[code] != name:
                aliases.append((code, cmap[code], name))
            cmap.setdefault(code, name)
    check()
    return cmap, names, tuple(aliases)


def select_text(
    custom: str,
    presets: tuple[str, ...],
    selected: int,
    *,
    immediate: int | None = None,
) -> str:
    """Run prefers nonempty custom input; double-click always uses that preset."""
    if immediate is None and custom != "":
        return custom
    index = selected if immediate is None else immediate
    if not 0 <= index < len(presets):
        raise ValueError("Enter custom text or select a preset before running.")
    return presets[index]


def _word(
    text: str, index: int, cmap: dict, names: set, mode: str, check: Callable
) -> tuple:
    """Resolve every input occurrence while retaining complete omission diagnostics."""
    glyphs, display, dropped = [], [], []
    offset = 0
    while offset < len(text):
        check()
        start, token = offset, mode == "names" and text[offset] == "/"
        if token:
            offset += 1
            while (
                offset < len(text)
                and text[offset] != "/"
                and not text[offset].isspace()
            ):
                check()
                offset += 1
            raw = text[start:offset]
            name = raw[1:] if raw[1:] in names else None
            if offset < len(text) and text[offset] == " ":
                offset += 1
        else:
            raw = text[offset]
            name = cmap.get(ord(raw))
            offset += 1
        if name is None:
            dropped.append(
                Omission(index, start, raw, "token" if token else "character")
            )
        else:
            glyphs.append(name)
            display.append(raw)
    check()
    return tuple(glyphs), "".join(display), dropped


def analyze(
    text: str,
    cmap: dict,
    names: set,
    masters: tuple[str, ...],
    layout: int = 1,
    *,
    mode: str = "characters",
    check: Callable = lambda: None,
) -> Comparison:
    """Sanitize fully before staging every word across every captured master.

    Side-by-side adds a literal space after EACH master and a final group
    newline. Stacked adds a newline after EACH master and one extra after EACH
    group. Empty fields or fields sanitized to empty are disclosed and omitted.
    Named glyph slots represent mapped control characters without raw text
    conversion; native name/UTF16 capability is independently preflighted.
    """
    check()
    if layout not in (0, 1) or mode not in ("characters", "names"):
        raise ValueError(
            "Choose Stacked (0), Side-by-side (1), and a supported input mode."
        )
    seen = set()
    for master in masters:
        check()
        if not isinstance(master, str) or not master or master in seen:
            raise ValueError("The font needs distinct, nonempty master names.")
        seen.add(master)
    if not masters:
        raise ValueError("The font needs at least one master.")
    words, rows, dropped, empty, previews = [], [[]], [], [], []
    for index, field in enumerate(text.split(",")):
        check()
        glyphs, display, omissions = _word(field, index, cmap, names, mode, check)
        dropped.extend(omissions)
        if not glyphs:
            empty.append(index)
            continue
        words.append(glyphs)
        for master in masters:
            check()
            for name in glyphs:
                check()
                rows[-1].append((name, master))
            previews.append(display)
            if layout == 1:
                rows[-1].append((None, ""))
                previews.append(" ")
            else:
                rows.append([])
                previews.append("\n")
        rows.append([])
        previews.append("\n")
    check()
    immutable = []
    for row in rows:
        check()
        immutable.append(tuple(row))
    check()
    result = Comparison(
        tuple(words), tuple(immutable), "".join(previews), tuple(dropped), tuple(empty)
    )
    if not words:
        raise NoUsableGlyphs(result)
    return result
