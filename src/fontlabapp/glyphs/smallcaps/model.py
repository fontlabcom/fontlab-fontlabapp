# this_file: src/fontlabapp/glyphs/smallcaps/model.py
# SPDX-License-Identifier: Apache-2.0
"""Analyze detached export, case, counterpart and kerning-group facts.

Reimplements both workflows of mekkablue's Check Smallcap Consistency;
the Boolean counterpart test is corrected. Native capture is separate.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from time import monotonic
from typing import Literal

Case = Literal["smallcap", "lower", "upper", "uncased", "unknown"]
SC_SUFFIXES = frozenset(("sc", "smcp", "c2sc"))


@dataclass(frozen=True)
class GlyphFact:
    """One detached glyph; None groups means unknown, () means no group.

    Text describes the base name, including multi-character ligatures. Group
    sides use Glyphs terminology: left=pair-right, right=pair-left.
    """

    name: str
    export: bool
    case: Case
    text: str | None = None
    left: tuple[str, ...] | None = ()
    right: tuple[str, ...] | None = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Glyph names must be nonempty strings")
        if type(self.export) is not bool or self.case not in (
            "smallcap",
            "lower",
            "upper",
            "uncased",
            "unknown",
        ):
            raise ValueError("Explicit export and case facts are required")
        if self.text is not None and (not isinstance(self.text, str) or not self.text):
            raise ValueError("Character mapping must be nonempty text or None")
        for group in (self.left, self.right):
            if group is not None and (
                not isinstance(group, tuple)
                or any(not isinstance(name, str) or not name for name in group)
            ):
                raise ValueError("Groups must be tuples of nonempty names or None")


def strip_sc(name: str) -> str:
    """Remove only complete SC suffix particles, preserving other suffix order."""
    root, *suffixes = name.split(".")
    return ".".join((root, *(s for s in suffixes if s not in SC_SUFFIXES)))


def legacy_cap_name(name: str) -> str:
    """Capitalize legacy ligature/name roots without destroying alternate suffixes."""
    root, *suffixes = strip_sc(name).split(".")
    parts = []
    for part in root.split("_"):
        split = 2 if part.startswith(("ae", "oe")) else 1
        parts.append(part[:split].upper() + part[split:])
    return ".".join(("_".join(parts), *suffixes))


def check_deadline(deadline: float, clock: Callable[[], float]) -> None:
    """Refuse a partial result when the shared capture/report deadline expires."""
    if clock() >= deadline:
        raise TimeoutError(
            "Could not complete Smallcap Consistency before its deadline"
        )


def analyze(
    glyphs: Iterable[GlyphFact],
    *,
    deadline: float = float("inf"),
    clock: Callable[[], float] = monotonic,
) -> dict:
    """Return deterministic modern and legacy findings in source font order.

    All counterpart sets exclude nonexporting glyphs. Unicode casing matches
    detached text with the same remaining suffix, so alternate names and
    multi-codepoint transformations never need ord() or guessed glyph names.
    """
    rows = []
    names = set()
    by_case = {case: [] for case in ("smallcap", "lower", "upper")}
    text_index = {}
    for glyph in glyphs:
        check_deadline(deadline, clock)
        if glyph.name in names:
            raise ValueError(f"Duplicate glyph name: {glyph.name}")
        names.add(glyph.name)
        rows.append(glyph)
        if glyph.export and glyph.case in by_case:
            by_case[glyph.case].append(glyph)
            if glyph.text is not None:
                suffix = strip_sc(glyph.name).partition(".")[2]
                text_index.setdefault((glyph.case, suffix, glyph.text), []).append(
                    glyph
                )
    exported = {g.name: g for g in rows if g.export}
    smallcaps = {g.name for g in by_case["smallcap"]}
    report = {
        "counts": {case: len(values) for case, values in by_case.items()},
        "excluded_nonexporting": [g.name for g in rows if not g.export],
        "unclassified": [g.name for g in rows if g.export and g.case == "unknown"],
        "unknown_mapping": [
            g.name for g in rows if g.export and g.text is None and g.case in by_case
        ],
        "missing_lowercase_smallcaps": [],
        "missing_uppercase_smallcaps": [],
        "orphan_smallcaps": [],
        "missing_smallcap_capitals": [],
        "missing_smallcap_lowercase": [],
        "legacy_capitals_without_smallcaps": [],
        "legacy_lowercase_without_smallcaps": [],
        "kerning_mismatches": [],
        "unknown_groups": [],
    }
    for case, suffix, key in (
        ("lower", "smcp", "missing_lowercase_smallcaps"),
        ("upper", "c2sc", "missing_uppercase_smallcaps"),
    ):
        for glyph in by_case[case]:
            check_deadline(deadline, clock)
            if not any(glyph.name + "." + s in smallcaps for s in ("sc", suffix)):
                report[key].append(glyph.name)
            if case == "lower" and glyph.name + ".sc" not in smallcaps:
                report["legacy_lowercase_without_smallcaps"].append(glyph.name)
            if case == "upper":
                root, dot, tail = glyph.name.partition(".")
                legacy = root.lower() + dot + tail + ".sc"
                if legacy not in smallcaps:
                    report["legacy_capitals_without_smallcaps"].append(glyph.name)
    for glyph in by_case["smallcap"]:
        check_deadline(deadline, clock)
        base = strip_sc(glyph.name)
        root, dot, tail = base.partition(".")
        matches = {}
        for case, transform, fallback in (
            ("upper", str.upper, legacy_cap_name(base)),
            ("lower", str.lower, root.lower() + dot + tail),
        ):
            direct = exported.get(base)
            named = exported.get(fallback)
            candidates = [
                g for g in (direct, named) if g is not None and g.case == case
            ]
            if glyph.text:
                candidates += text_index.get((case, tail, transform(glyph.text)), [])
            matches[case] = list({g.name: g for g in candidates}.values())
            if not matches[case]:
                key = (
                    "missing_smallcap_capitals"
                    if case == "upper"
                    else "missing_smallcap_lowercase"
                )
                report[key].append(glyph.name)
        if not matches["upper"] and not matches["lower"]:
            report["orphan_smallcaps"].append(glyph.name)
        for capital in matches["upper"]:
            for side in ("left", "right"):
                check_deadline(deadline, clock)
                sc, cap = getattr(glyph, side), getattr(capital, side)
                item = {"glyph": glyph.name, "capital": capital.name, "side": side}
                if sc is None or cap is None or len(sc) > 1 or len(cap) > 1:
                    report["unknown_groups"].append(item)
                elif tuple(legacy_cap_name(name) for name in sc) != cap:
                    report["kerning_mismatches"].append(
                        {**item, "smallcap": list(sc), "capital_groups": list(cap)}
                    )
    check_deadline(deadline, clock)
    return report
