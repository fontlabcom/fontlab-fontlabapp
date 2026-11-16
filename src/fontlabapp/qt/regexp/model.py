# this_file: src/fontlabapp/qt/regexp/model.py
# SPDX-License-Identifier: Apache-2.0
"""Evaluate authored patterns with an injected native Qt 5 QRegExp.

Keep the four archived syntax policies and Qt's UTF-16 positions, lengths and
captures. No Python regular-expression parser or replacement engine is used.
Batch names are an immutable complete vocabulary, never a live font iterator.
"""

import json
from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class Rule:
    """A complete local pattern configuration; every original control is retained."""

    pattern: str
    syntax: int = 0
    case: bool = False
    minimal: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.pattern, str):
            raise TypeError("The pattern must be text.")
        if type(self.syntax) is not int or not 0 <= self.syntax < 4:
            raise ValueError("Select one of the four original Qt syntaxes.")
        if type(self.case) is not bool or type(self.minimal) is not bool:
            raise TypeError("Case and minimal-match settings must be boolean.")


def _check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Pattern evaluation expired; no partial batch is shown.")


def _match(expression: Any, text: str) -> dict[str, Any]:
    position = expression.indexIn(text)
    if type(position) is not int:
        raise TypeError("Qt returned an unreadable match position.")
    length = expression.matchedLength() if position >= 0 else -1
    count = expression.captureCount() if position >= 0 else -1
    if type(length) is not int or type(count) is not int or count < -1:
        raise TypeError("Qt returned unreadable match dimensions.")
    captures = [expression.cap(i) for i in range(count + 1)]
    if any(not isinstance(item, str) for item in captures):
        raise TypeError("Qt returned unreadable captured text.")
    return {"position": position, "length": length, "captures": captures}


def evaluate(
    core: Any,
    rule: Rule,
    text: str,
    words: tuple[str, ...],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    """Return original input results and all matching captured glyph names.

    Qt calls retain their native semantics. A deadline fences whole Python
    traversal and publication; it cannot preempt a blocking native Qt call.
    """
    if not isinstance(rule, Rule) or not isinstance(text, str):
        raise TypeError("A complete Rule and input text are required.")
    if type(words) is not tuple or any(not isinstance(w, str) or not w for w in words):
        raise TypeError("Supply the complete immutable glyph-name vocabulary.")
    if len(set(words)) != len(words):
        raise ValueError("The captured glyph vocabulary has duplicate names.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    _check(limit)
    kind = core.QRegExp
    modes = (kind.RegExp, kind.RegExp2, kind.Wildcard, kind.FixedString)
    expression = kind(rule.pattern)
    expression.setPatternSyntax(modes[rule.syntax])
    expression.setCaseSensitivity(
        core.Qt.CaseSensitive if rule.case else core.Qt.CaseInsensitive
    )
    expression.setMinimal(rule.minimal)
    valid, error = expression.isValid(), expression.errorString()
    if type(valid) is not bool or not isinstance(error, str):
        raise TypeError("Qt returned unreadable pattern validity.")
    result = {
        "pattern": rule.pattern,
        "escaped": json.dumps(rule.pattern),
        **_match(expression, text),
        "valid": valid,
        "error": "" if valid else error,
        "tested_glyphs": len(words),
        "glyph_matches": [],
    }
    for name in words:
        _check(limit)
        match = _match(expression, name)
        if match["position"] >= 0:
            result["glyph_matches"].append({"name": name, **match})
    _check(limit)
    return result
