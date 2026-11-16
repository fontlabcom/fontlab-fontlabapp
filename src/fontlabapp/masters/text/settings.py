# this_file: src/fontlabapp/masters/text/settings.py
# SPDX-License-Identifier: Apache-2.0
"""Owned settings and optional local UTF8 preset lists, never host preferences.

The four fallback VALUES are attributed behavioral data from Luke Prowse's
MasterBlaster (2019): root LICENSE MIT; README declares Apache-2.0. Independent
implementation; original executable code and preset resource are not shipped.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fontlabapp import _native

PRESET_FILE = "MasterBlaster-presets.txt"

_LOWER = "arrowroot,barley,chervil,dumpling,endive,flaxseed,garbanzo,hijiki,ishtu,jicama,kale,lychee,marjioram,nectarine,oxtail,pizza,quinoa,roquefort,squash,tofu,uppuma,vanilla,wheat,xergis,yogurt,zweiback"
FALLBACKS = (
    _LOWER,
    ",".join(s[:1].upper() + s[1:] for s in _LOWER.split(",")),
    _LOWER.upper(),
    "00000,00100,00200,00300,00400,00500,00600,00700,00800,00900",
)


@dataclass(frozen=True)
class Presets:
    """Complete staged lines and an explicit load/fallback diagnostic."""

    lines: tuple[str, ...]
    notice: str


def read_presets(
    path: Path | str, *, check: Callable = lambda: None
) -> tuple[str, ...]:
    """Read BOM/CRLF/CR normalized UTF8 without stripping mapped whitespace.

    Split only physical LF newlines; Unicode line/paragraph separators remain
    source characters. Read in bounded chunks with cooperative checkpoints.
    Blocking filesystem primitives cannot be preempted; check on return.
    """
    check()
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("Enter an absolute preset-file path.")
    parts = []
    with target.open(encoding="utf-8-sig", newline=None) as stream:
        while True:
            check()
            chunk = stream.read(4096)
            check()
            if not chunk:
                break
            parts.append(chunk)
    lines = []
    for line in "".join(parts).split("\n"):
        check()
        if line != "":
            lines.append(line)
    check()
    if not lines:
        raise ValueError("The preset file contains no text.")
    return tuple(lines)


def presets_directory(directory: Path | None = None) -> Path:
    """Explicit directory, else the FontLab user folder's ``Scripts``, else the cwd."""
    if directory is not None:
        return Path(directory)
    try:
        value = _native("fontlab").flPreferences().dataPathDefault
        value = value() if callable(value) else value
    except (RuntimeError, AttributeError):
        value = None
    return Path(str(value)) / "Scripts" if value else Path.cwd()


def load_presets(directory: Path, *, check: Callable = lambda: None) -> Presets:
    """Seek the preset file in ``directory``, then use four defaults; name the path."""
    path = directory / PRESET_FILE
    try:
        lines = read_presets(path, check=check)
        return Presets(
            lines, f"Local presets loaded from {path}; UTF-8 BOM and newlines normalized."
        )
    except (TimeoutError, InterruptedError):
        raise
    except (OSError, UnicodeError, ValueError) as error:
        check()
        return Presets(
            FALLBACKS,
            f"Four original fallback lists; local presets unavailable at {path}: {error}",
        )


def _sync(settings: Any, check: Callable) -> None:
    check()
    settings.sync()
    check()
    status = settings.status()
    if getattr(status, "value", status) != 0:
        raise OSError("Master Text Comparison settings could not be read or saved.")


def load(settings: Any, *, check: Callable = lambda: None) -> tuple[str, int, Any]:
    """Read only tool-owned controls/geometry, with exact original defaults."""
    check()
    custom = settings.value("inputCustom", "")
    check()
    layout = settings.value("layout", 1)
    if not isinstance(custom, str) or layout not in (0, 1, "0", "1"):
        raise ValueError(
            "Saved custom text/layout is invalid; original defaults retained."
        )
    check()
    geometry = settings.value("geometry", None)
    _sync(settings, check)
    return custom, int(layout), geometry


def save(
    settings: Any,
    custom: str | None = None,
    layout: int | None = None,
    *,
    geometry: Any = None,
    preserve_custom: bool = False,
    check: Callable = lambda: None,
) -> None:
    """Save source controls after proof, or geometry on Close.

    A successful immediate preset may hold unrelated custom representation;
    preserve_custom skips that key entirely, retaining its last exact value.
    """
    check()
    if not settings.isWritable():
        raise OSError("Master Text Comparison settings are read-only.")
    values = (
        {"geometry": geometry}
        if geometry is not None
        else {"inputCustom": custom, "layout": layout}
    )
    if preserve_custom:
        values.pop("inputCustom", None)
    for key, item in values.items():
        check()
        settings.setValue(key, item)
    _sync(settings, check)
