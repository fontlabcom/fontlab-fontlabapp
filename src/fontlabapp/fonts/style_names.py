# this_file: src/fontlabapp/fonts/style_names.py
# SPDX-License-Identifier: Apache-2.0
"""Detached naming rules from Resistenza ShortNames and StyleLinker.

Callers resolve eligible static instances and typographic family precedence.
This module does not invent native instance fields, change family/style names,
write fonts or implement the original editable panels. Native adapters remain
pending. Preserve original case, tokenization and confirmation warnings.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from types import MappingProxyType

ABBREVIATIONS = MappingProxyType(
    {
        "Regular": "Rg",
        "Italic": "It",
        "Oblique": "Obl",
        "Slanted": "Sl",
        "Bold": "Bd",
        "Light": "Lt",
        "Medium": "Md",
        "Black": "Blk",
        "Thin": "Th",
        "Book": "Bk",
        "Heavy": "Hv",
        "Hairline": "Hair",
        "Extra": "X",
        "Semi": "Sm",
        "Demi": "Dm",
        "Ultra": "Ult",
        "Super": "Sup",
        "Condensed": "Cn",
        "Compressed": "Cm",
        "Compact": "Cp",
        "Narrow": "Nr",
        "Extended": "Ex",
        "Expanded": "Exp",
        "Wide": "Wd",
        "Display": "Ds",
        "Text": "Tx",
        "Caption": "Ca",
        "Poster": "Po",
        "Variable": "VF",
    }
)
_WORDS = re.compile(r"[A-Z][a-z]*|[a-z]+|\d+")
_ITALIC_WORDS = ("Italic", "Oblique")


@dataclass(frozen=True)
class NameEdits:
    """Trimmed edit values and ordered warnings requiring Apply-anyway choice."""

    names: tuple[str, ...]
    problems: tuple[str, ...]


@dataclass(frozen=True)
class Link:
    """Base style and explicit bold/italic flags; Regular stays an explicit word."""

    base: str
    bold: bool
    italic: bool


def split_style_words(name: str) -> tuple[str, ...]:
    """Keep source ASCII-regex behavior, including punctuation/accent quirks."""
    return tuple(
        word for chunk in name.split() for word in (_WORDS.findall(chunk) or [chunk])
    )


def shorten_style(style: str) -> str:
    """Apply all 29 case-sensitive abbreviations; empty output becomes Rg."""
    return (
        "".join(ABBREVIATIONS.get(word, word) for word in split_style_words(style))
        or "Rg"
    )


def propose_ps_name(resolved_family: str, style: str) -> str:
    """Join caller-resolved typographic family and abbreviated style exactly."""
    return f"{resolved_family.replace(' ', '')}-{shorten_style(style)}"


def prepare_names(values: tuple[object, ...]) -> NameEdits:
    """Retain source str/strip, warning order and 29-character advisory limit.

    These warnings do not silently veto the source's Apply-anyway interaction.
    A future native adapter must separately prove representability before writes.
    """
    names, problems, seen = [], [], set()
    for value in values:
        name = str(value).strip()
        if not name or "-" not in name:
            problems.append(f"'{name}' is not a valid PS name")
        if name in seen:
            problems.append(f"duplicate: {name}")
        if len(name) > 29:
            problems.append(f"{name} is {len(name)} chars (>29)")
        seen.add(name)
        names.append(name)
    return NameEdits(tuple(names), tuple(problems))


def style_link(style: str, available_styles: Collection[str]) -> Link | None:
    """Use whole-word Bold/Italic/Oblique and the original bold-base fallback."""
    words = style.split()
    italic = any(word in _ITALIC_WORDS for word in words)
    remainder = [word for word in words if word not in _ITALIC_WORDS]
    bold = "Bold" in remainder
    base_words = [word for word in remainder if word != "Bold"] if bold else remainder
    if not (bold or italic):
        return None
    base = " ".join(base_words) or "Regular"
    if base == style:
        return None
    if base not in available_styles:
        bold_base = " ".join(remainder)
        return (
            Link(bold_base, False, True)
            if bold and italic and bold_base in available_styles
            else None
        )
    return Link(base, bold, italic)
