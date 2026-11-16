# this_file: src/fontlabapp/glyphs/case_coverage/model.py
# SPDX-License-Identifier: Apache-2.0
"""Host-free Casefolding Report analysis with explicit metadata and alternatives.

Canonical names are supplied by the caller's GlyphData policy. Alternate
encodings are independent characters, never a concatenated ligature string.
Unicode expansions are retained without ord(mapped_text). See NOTICE.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, InitVar
from time import monotonic


@dataclass(frozen=True)
class Options:
    """The four original controls, retaining their names and defaults."""

    excludeMathSymbols: bool = False
    allFonts: bool = True
    reuseTab: bool = True
    showMacroWindow: bool = False

    def __post_init__(self) -> None:
        """Reject invalid boundary facts before analysis or persistence."""
        if any(type(value) is not bool for value in vars(self).values()):
            raise ValueError("Case Coverage options must be boolean.")


@dataclass(frozen=True)
class GlyphFact:
    """One detached glyph with real metadata; None subcategory means unknown.

    ``unicodes`` contains alternative scalar encodings. ``text`` is the
    metadata character fallback for an unencoded glyph, not a glyph sequence.
    """

    name: str
    unicodes: tuple[int, ...]
    export: bool
    subcategory: str | None
    text: str | None = None
    validation_check: InitVar[Callable[[], None]] = lambda: None

    def __post_init__(self, validation_check: Callable[[], None]) -> None:
        """Reject invalid boundary facts before analysis or persistence."""
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Glyph names must be nonempty strings.")
        if type(self.export) is not bool or type(self.unicodes) is not tuple:
            raise ValueError("Explicit export and immutable Unicode facts required.")
        for code in self.unicodes:
            validation_check()
            if (
                type(code) is not int
                or not 0 <= code <= 0x10FFFF
                or 0xD800 <= code <= 0xDFFF
            ):
                raise ValueError("Glyph encodings must be Unicode scalar values.")
        if self.subcategory is not None and not isinstance(self.subcategory, str):
            raise ValueError("Subcategory must be text or unknown.")
        if self.text is not None and (not isinstance(self.text, str) or not self.text):
            raise ValueError("Metadata character mapping must be nonempty text.")


def checkpoint(deadline: float, clock: Callable, cancelled: Callable) -> None:
    """Check cancellation and the shared deadline; never return a partial report."""
    if cancelled():
        raise InterruptedError("Case Coverage was cancelled.")
    if clock() >= deadline:
        raise TimeoutError("Case Coverage exceeded its deadline; run again.")


def _mapping_row(
    glyph: GlyphFact,
    text: str,
    mapped: str,
    direction: str,
    names: dict,
    encoded: dict,
    preferred: Mapping[str, str],
    options: Options,
    check: Callable,
) -> dict:
    """Resolve the canonical or encoded counterpart without losing expansion text."""
    canonical = preferred.get(mapped)
    canonical = {"i_dotaccentcomb": "i", "SS": "Germandbls"}.get(canonical, canonical)
    # Source compatibility names also define their encoded alternate identity.
    equivalent = {"i̇": "i", "SS": "ẞ"}.get(mapped, mapped)
    aliases = encoded.get(equivalent, [])
    counterpart = names.get(canonical) if canonical else None
    if counterpart is None and aliases:
        counterpart = aliases[0]
    status = "matched"
    if counterpart is None:
        status = (
            "excluded_math"
            if options.excludeMathSymbols and glyph.subcategory == "Math"
            else "missing"
        )
    elif glyph.export and not counterpart.export:
        status = "export_mismatch"
    candidates = []
    for alias in aliases:
        check()
        candidates.append(alias.name)
    check()
    return dict(
        glyph=glyph.name,
        text=text,
        mapped_text=mapped,
        direction=direction,
        preferred=canonical,
        counterpart=None if counterpart is None else counterpart.name,
        candidates=candidates,
        ambiguous=len(aliases) > 1,
        status=status,
        subcategory=glyph.subcategory,
        metadata_unknown=glyph.subcategory is None,
        name_mapping_unknown=canonical is None,
        encoded_equivalent=equivalent,
    )


def character_texts(glyph: GlyphFact, check: Callable) -> tuple[str, ...]:
    """Read independent encodings in first-occurrence order under the caller budget."""
    result, seen = [], set()
    for code in glyph.unicodes:
        check()
        text = chr(code)
        if text not in seen:
            seen.add(text)
            result.append(text)
    check()
    return tuple(result) or ((glyph.text,) if glyph.text else ())


def analyze(
    glyphs: Iterable[GlyphFact],
    preferred: Mapping[str, str],
    options: Options = Options(),
    *,
    deadline: float = float("inf"),
    clock: Callable = monotonic,
    cancelled: Callable = lambda: False,
) -> dict:
    """Return all diagnostics and exact ordered/repeated proof occurrences.

    Preferred canonical names win even when unencoded. Otherwise the first
    glyph in font order encoding the whole mapped character wins; ambiguity
    lists every candidate. Multi-character expansions require a canonical
    named glyph (including i_dotaccentcomb→i and SS→Germandbls), never a set
    of independent glyphs. Source and counterpart export asymmetry applies
    equally to named and encoded aliases. Nonexporting source glyphs are read.
    Math exclusion suppresses missing cases only, as in the source workflow.
    Unknowns are reported explicitly and cannot produce all-clear feedback.
    """
    check = lambda: checkpoint(deadline, clock, cancelled)
    names, encoded, source = {}, {}, []
    for glyph in glyphs:
        check()
        if glyph.name in names:
            raise ValueError(f"Duplicate glyph name: {glyph.name}")
        names[glyph.name] = glyph
        source.append(glyph)
        for code in dict.fromkeys(glyph.unicodes):
            check()
            encoded.setdefault(chr(code), []).append(glyph)
    rows, proof = [], []
    for glyph in source:
        check()
        if glyph.subcategory == "Ligature":
            rows.append(dict(glyph=glyph.name, status="excluded_ligature"))
            continue
        texts = character_texts(glyph, check)
        if not texts:
            rows.append(dict(glyph=glyph.name, status="unknown_mapping"))
        for text in texts:
            check()
            directions = [("lowercase", text.lower())] if text.isupper() else []
            if text.islower():
                directions.append(("uppercase", text.upper()))
            if not directions:
                # Math-category symbols such as increment have case mappings
                # even when Unicode's isupper/islower classify them as uncased.
                rows.append(
                    dict(
                        glyph=glyph.name,
                        text=text,
                        status="uncased",
                        subcategory=glyph.subcategory,
                        metadata_unknown=glyph.subcategory is None,
                    )
                )
            for direction, mapped in directions:
                check()
                row = _mapping_row(
                    glyph,
                    text,
                    mapped,
                    direction,
                    names,
                    encoded,
                    preferred,
                    options,
                    check,
                )
                rows.append(row)
                if row["status"] in ("missing", "export_mismatch"):
                    proof.append(glyph.name)
                    if row["status"] == "export_mismatch":
                        proof.append(row["counterpart"])
    check()
    unresolved = False
    for row in rows:
        check()
        unresolved = (
            unresolved
            or row["status"] == "unknown_mapping"
            or row.get("metadata_unknown", False)
        )
    check()
    return dict(
        rows=rows,
        proof=proof,
        all_clear=not proof and not unresolved,
        unresolved=unresolved,
        alias_policy="canonical preferred name, then first encoded alias in font order; all candidates disclosed",
    )
