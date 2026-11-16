# this_file: src/fontlabapp/features/code.py
# SPDX-License-Identifier: Apache-2.0
"""Host-free suffix pairing and conservative FEA substitution generation.

Import through fly.ap.features.code from scripts. These shared calculations
serve the suffix builder, suffix inventory and ligature recipe finder without
importing FontLab or Qt. Adapted from Apache-2.0 fontlab-samples; see NOTICE.
They generate naming-based source only and never compile or mutate a font.
"""

import re
from collections.abc import Iterable


def safe_name(name: str) -> bool:
    """Return whether a glyph name can appear unescaped in generated FEA.

    Permit ASCII letters/underscore initially and letters, digits, dots or
    hyphens thereafter, plus .notdef. This is intentionally conservative: it
    does not parse escaped FEA names or verify a glyph exists in a font.
    """
    return bool(re.fullmatch("[A-Za-z_][A-Za-z0-9_.\\-]*|\\.notdef", name))


def suffix_pairs(names: Iterable[str], suffix: str) -> list[tuple[str, str]]:
    """Return unique existing base/alternate pairs in alternate-name order.

    Ignore leading suffix dots, orphan alternates and unsafe names. Every
    generated pair needs both names in the supplied glyph-name iterable.
    Empty suffixes yield no pairs. No font or feature source is modified.
    """
    suffix = suffix.lstrip(".")
    known = set(names)
    ending = "." + suffix
    return [
        (name[: -len(ending)], name)
        for name in sorted(known)
        if suffix
        and name.endswith(ending)
        and (name[: -len(ending)] in known)
        and safe_name(name)
        and safe_name(name[: -len(ending)])
    ]


def feature_text(tag: str, pairs: Iterable[tuple[str, str]]) -> str:
    """Build a complete substitution block without a trailing newline.

    Require a four-character ASCII alphanumeric tag, safe glyph names and
    unique source names. Preserve pair order; empty pairs produce an empty
    block. The result is source text, not proof that the feature compiles or
    shapes correctly. Ordered native writers may require a final newline.
    """
    pairs = list(pairs)
    if not re.fullmatch("[A-Za-z0-9]{4}", tag):
        msg = "Feature tag must contain four ASCII letters or digits."
        raise ValueError(msg)
    if len({base for base, _ in pairs}) != len(pairs):
        raise ValueError("Duplicate substitution source glyphs.")
    if any(not safe_name(base) or not safe_name(target) for base, target in pairs):
        raise ValueError("Invalid glyph name in substitution plan.")
    lines = ["    sub " + base + " by " + target + ";" for base, target in pairs]
    return "feature " + tag + " {\n" + "\n".join(lines) + "\n} " + tag + ";"
