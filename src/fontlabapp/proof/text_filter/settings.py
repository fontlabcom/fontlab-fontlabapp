# this_file: src/fontlabapp/proof/text_filter/settings.py
# SPDX-License-Identifier: Apache-2.0
"""Persist only Text Filter's three strings through an injected QSettings object.

No host import or settings object is created here. Tests use owned memory or an
explicit temporary INI. The UI owns geometry separately. Reset removes only the
output/character keys, keeping input and unrelated settings. See NOTICE.
"""

from typing import Any

from fontlabapp.proof.text_filter.model import SavedText

NO_ERROR = 0


def sync(settings: Any) -> None:
    """Flush the owned tool store and report actual access/format errors."""
    settings.sync()
    status = settings.status()
    if getattr(status, "value", status) != NO_ERROR:
        raise OSError("Text Filter settings could not be saved or read.")


def load(settings: Any) -> SavedText:
    """Read complete strings or diagnose corruption without changing the store."""
    defaults = SavedText()
    values = tuple(
        settings.value(key, getattr(defaults, key))
        for key in ("input", "output", "characters")
    )
    if any(not isinstance(value, str) for value in values):
        raise ValueError("Saved Text Filter fields must contain text.")
    sync(settings)
    return SavedText(*values)


def save(settings: Any, state: SavedText) -> None:
    """Validate all three strings before writing; report a failed/partial save."""
    values = (state.input, state.output, state.characters)
    if any(not isinstance(value, str) for value in values):
        raise ValueError("Text Filter fields must contain text.")
    if not settings.isWritable():
        raise OSError("Text Filter settings are read-only.")
    for key, value in zip(("input", "output", "characters"), values, strict=True):
        settings.setValue(key, value)
    sync(settings)


def reset(settings: Any) -> None:
    """Restore the source defaults without erasing saved input or other tools."""
    if not settings.isWritable():
        raise OSError("Text Filter settings are read-only.")
    settings.remove("output")
    settings.remove("characters")
    sync(settings)
