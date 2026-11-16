# this_file: src/fontlabapp/fontui/features_state.py
# SPDX-License-Identifier: Apache-2.0
"""Pure staging for the B08 editor: blocks, line endings, add/remove.

Qt's plain-text widget shows every line break as LF. Each block remembers its
own stored line ending (LF, CRLF or CR) and gets it back on write; a block with
mixed endings may be shown but not rewritten. Fontport validates the result.
"""

from copy import deepcopy
from typing import Any

PREFIX = "Prefix"
MIXED = "Mixed line endings cannot be preserved; this block cannot be rewritten."
NEW_FEATURE = "feature {tag} {{\n}} {tag};\n"


def line_ending(text: str) -> str | None:
    """Return the one line ending used by text (LF if none), or None if mixed."""
    crlf = text.count("\r\n")
    cr, lf = text.count("\r") - crlf, text.count("\n") - crlf
    used = [end for end, n in (("\r\n", crlf), ("\r", cr), ("\n", lf)) if n]
    return "\n" if not used else used[0] if len(used) == 1 else None


def shown(text: str) -> str:
    """What QPlainTextEdit displays for text."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class FeatureState:
    """Staged blocks: {"prefix": str, "features": [(tag, code), ...]}."""

    def __init__(self, blocks: dict[str, Any]) -> None:
        self.loaded = {
            "prefix": blocks["prefix"] or "",
            "features": [tuple(pair) for pair in blocks["features"]],
        }
        self.staged = deepcopy(self.loaded)

    def keys(self) -> list[str]:
        return [PREFIX, *(tag for tag, _ in self.staged["features"])]

    def raw(self, key: str) -> str:
        if key == PREFIX:
            return self.staged["prefix"]
        return dict(self.staged["features"])[key]

    def text(self, key: str) -> str:
        return shown(self.raw(key))

    def set_text(self, key: str, widget_text: str) -> None:
        """Stage widget text for key, restoring that block's own line ending."""
        current = self.raw(key)
        if widget_text == shown(current):
            return
        ending = line_ending(current)
        if ending is None:
            raise ValueError(f"{key}: {MIXED}")
        value = widget_text.replace("\n", ending)
        if key == PREFIX:
            self.staged["prefix"] = value
        else:
            self.staged["features"] = [
                (tag, value if tag == key else code)
                for tag, code in self.staged["features"]
            ]

    def add(self, tag: str) -> None:
        if tag in self.keys():
            raise ValueError(f"Feature block already exists: {tag}")
        self.staged["features"].append((tag, NEW_FEATURE.format(tag=tag)))

    def remove(self, key: str) -> None:
        if key == PREFIX:
            raise ValueError("The prefix block cannot be removed")
        self.staged["features"] = [
            pair for pair in self.staged["features"] if pair[0] != key
        ]

    @property
    def dirty(self) -> bool:
        return self.staged != self.loaded

    def value(self) -> dict[str, Any]:
        return {
            "prefix": self.staged["prefix"],
            "features": list(self.staged["features"]),
        }

    def whole_text(self) -> str:
        return self.staged["prefix"] + "".join(
            code for _, code in self.staged["features"]
        )
