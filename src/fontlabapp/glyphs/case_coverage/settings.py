# this_file: src/fontlabapp/glyphs/case_coverage/settings.py
# SPDX-License-Identifier: Apache-2.0
"""Persist only Case Coverage's four original booleans in its owned store.

Use an injected QSettings instance; tests/native probes use isolated INI files.
No FontLab preference API or global key is read, saved or restored.
"""

from typing import Any
from fontlabapp.glyphs.case_coverage.model import Options


def _boolean(value: Any) -> bool:
    """Parse the boolean encodings used by the owned QSettings store."""
    if type(value) is bool:
        return value
    if value in (0, 1, "true", "false"):
        return value in (1, "true")
    raise ValueError("Saved Case Coverage controls must be boolean.")


def _sync(settings: Any) -> None:
    """Flush the owned store and surface the actual native settings error."""
    settings.sync()
    status = settings.status()
    if getattr(status, "value", status) != 0:
        raise OSError("Case Coverage settings could not be read or saved.")


def load(settings: Any) -> Options:
    """Read the exact original defaults, accepting QSettings bool encodings."""
    values = {
        key: _boolean(settings.value(key, value))
        for key, value in vars(Options()).items()
    }
    _sync(settings)
    return Options(**values)


def save(settings: Any, options: Options) -> None:
    """Write only owned control keys; unrelated settings remain byte-independent."""
    if not settings.isWritable():
        raise OSError("Case Coverage settings are read-only.")
    for key, value in vars(options).items():
        settings.setValue(key, value)
    _sync(settings)
