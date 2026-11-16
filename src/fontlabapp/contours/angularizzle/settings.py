# this_file: src/fontlabapp/contours/angularizzle/settings.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Original Angularizzle settings with repaired Keep detail key spelling."""

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass

from fontlabapp.contours.angularizzle.session import parse_plane

PLANE = "com.LNP.Angela.inputSize"
CHECK = "com.LNP.Angela.checkBox"
LEGACY_CHECK = "com.LNP.Angela.checkbox"
WINDOW = "com.LNP.Angela.mainwindow"


@dataclass(frozen=True)
class Settings:
    """Parsed preferences; malformed values are explicit default diagnostics."""

    plane: str = "80"
    detail: bool = True
    geometry: tuple[int, int, int, int] | None = None
    warning: str = ""


def load(values: Mapping) -> Settings:
    """Read only this tool's keys; retain false values and legacy lowercase key."""
    plane, detail, geometry, warnings = "80", True, None, []
    if PLANE in values:
        try:
            candidate = str(values[PLANE])
            parse_plane(candidate)
            plane = candidate
        except ValueError:
            warnings.append("Invalid saved minimum plane; using 80.")
    raw = values.get(CHECK, values.get(LEGACY_CHECK, True))
    if isinstance(raw, bool):
        detail = raw
    elif isinstance(raw, str) and raw.lower() in {"true", "false"}:
        detail = raw.lower() == "true"
    else:
        warnings.append("Invalid saved Keep detail; using checked.")
    raw = values.get(WINDOW)
    if raw is not None:
        if (
            isinstance(raw, (list, tuple))
            and len(raw) == 4
            and all(type(v) is int for v in raw)
            and raw[2] > 0
            and raw[3] > 0
        ):
            geometry = tuple(raw)
        else:
            warnings.append("Invalid saved window placement; using default.")
    return Settings(plane, detail, geometry, " ".join(warnings))


def save(
    values: MutableMapping,
    plane: str,
    detail: bool,
    geometry: tuple[int, int, int, int],
) -> None:
    """Store canonical values after Process; never erase unrelated settings."""
    parse_plane(plane)
    values[PLANE] = plane
    values[CHECK] = bool(detail)
    values[WINDOW] = geometry


def native_preferences(qt: object) -> tuple[object, dict]:
    """Open this tool's explicit namespace; never change application globals."""
    backend = qt.QSettings("FontLab", "Angularizzle")
    backend.setFallbacksEnabled(False)
    keys = (PLANE, CHECK, LEGACY_CHECK, WINDOW)
    return backend, {key: backend.value(key) for key in keys if backend.contains(key)}


def persist(
    qt: object, backend: object, values: Mapping, keys: tuple[str, ...]
) -> None:
    """Flush only named tool keys and report the real QSettings write status."""
    for key in keys:
        backend.setValue(key, values[key])
    backend.sync()
    if backend.status() != qt.QSettings.NoError:
        raise OSError("Angularizzle settings could not be saved.")
