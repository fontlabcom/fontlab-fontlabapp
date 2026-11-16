# this_file: src/fontlabapp/glyphs/unreferenced.py
# SPDX-License-Identifier: Apache-2.0
"""Find unencoded, unreferenced glyphs without deleting or changing font data.

Retain the original Select Unreferenced Glyphs rules. Read encodings through the
existing FontGate reader, avoiding the native flGlyph.fgGlyph conversion. Keep
raw inputs as plain values so the panel can refuse stale selection actions.
"""

import re
from typing import Any

from fontlabapp import _native
from fontlabapp.components.inspect.model import font_glyph_names
from fontlabapp.core.scripting import names_font_glyphs

RESERVED = {".notdef", ".null", "nonmarkingreturn"}


def feature_source(font: Any) -> str:
    """Read the prefix and every feature block in tag order.

    Native fgOTLayout iteration yields feature text. Use keys() to retrieve tags;
    treating the text as a tag silently loses referenced glyph names.
    """
    features = font.features
    return (
        features.get_prefix()
        + "\n"
        + "\n".join(features.get_feature(tag) for tag in features.keys())  # noqa: SIM118 - Native iteration yields code, not keys.
    )


def tokens(text: str) -> set[str]:
    """Read original FEA name tokens, including hyphens, after dropping comments."""
    return set(re.findall(r"[A-Za-z0-9_.-]+", re.sub(r"#[^\n]*", "", text)))


def _class_source(font: Any) -> tuple:
    """Capture feature-class flags and raw records before resolving used classes."""
    groups = font.groups
    names = tuple(str(name) for name, group in groups.items() if group.isFeaGroup())
    return names, tuple(str(record) for record in groups.getAsClassRecords() or [])


def _members(classes: tuple, used_tokens: set[str]) -> set[str]:
    """Keep members of used feature classes; remove original key-glyph apostrophes."""
    feature_names, records = classes
    members = set()
    for record in records:
        name, _, body = record.partition(":")
        if name in feature_names and name in used_tokens:
            members.update(part.rstrip("'") for part in body.split())
    return members


def class_members(font: Any, used_tokens: set[str]) -> set[str]:
    """Retain the original helper interface for used feature-class members."""
    return _members(_class_source(font), used_tokens)


def source_values(package: Any) -> tuple | None:
    """Snapshot every input to the candidate list without native glyph conversion.

    Ordered membership and encodings must agree. A disappearing glyph is a scan
    failure; publishing a partial candidate list could select the wrong glyphs.
    """
    if package is None:
        return None
    font = _native("fontlab").CurrentFont()
    if font is None:
        raise ValueError("The original font is no longer current; reopen this tool.")
    names = font_glyph_names()
    encoded = names_font_glyphs()
    if [name for name, _ in encoded] != names:
        raise ValueError("Font encoding order changed; reopen this tool.")
    records = []
    for name, codes in encoded:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        layers = tuple(
            (
                layer.name,
                layer.recipe or "",
                tuple(
                    shape.shapeData.componentGlyph
                    for shape in layer.shapes
                    if shape.isComponent
                ),
            )
            for layer in glyph.layers
        )
        records.append((name, tuple(codes), layers))
    return feature_source(font), _class_source(font), tuple(records)


def unreferenced(package: Any) -> list[tuple[str, str]]:
    """Return all original candidates and alternate hints in font order.

    Included FEA files cannot be inspected here. Refuse the complete scan when
    include() occurs outside comments; do not silently omit its references.
    """
    source = source_values(package)
    if source is None:
        return []
    text, classes, records = source
    if re.search(r"\binclude\s*\(", re.sub(r"#[^\n]*", "", text)):
        raise ValueError(
            "The feature source uses include(): open the included code in FontLab first."
        )
    used = tokens(text) | RESERVED
    used |= _members(classes, used)
    for _, _, layers in records:
        for _, recipe, components in layers:
            used.update(components)
            used.update(tokens(recipe))
    known = {name for name, _, _ in records}
    rows = []
    for name, codes, _ in records:
        if name in used or codes:
            continue
        base = name.split(".")[0]
        note = f"alternate of {base}?" if "." in name and base in known else ""
        rows.append((name, note))
    return rows
