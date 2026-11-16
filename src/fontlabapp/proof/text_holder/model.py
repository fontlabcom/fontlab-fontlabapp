# this_file: src/fontlabapp/proof/text_holder/model.py
# SPDX-License-Identifier: Apache-2.0
"""Independent Reza Text Holder workflow; literal Unicode editing, lazy Qt UI.

Original source has no declared licence; no original body is redistributed.
See NOTICE. Native FontLab/PythonQt qualification remains pending.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

KEY = "text-holder"


def utf16_units(text: str) -> int:
    """Count QString/QTextCursor code units, including non-BMP characters."""
    return len(text.encode("utf-16-le", errors="surrogatepass")) // 2


def index_at(text: str, position: int) -> int:
    """Translate a Qt cursor boundary; refuse half of a surrogate pair."""
    if type(position) is not int:
        raise TypeError("A UTF16 cursor position must be an integer.")
    units = 0
    for index, char in enumerate(text):
        if units == position:
            return index
        units += utf16_units(char)
    if units == position:
        return len(text)
    raise ValueError("Cursor position is not a complete Unicode boundary.")


def find_first(text: str, needle: str) -> tuple[int, int] | None:
    """Find from document start, preserving literal case and normalization."""
    index = text.find(needle) if needle else -1
    if index < 0:
        return None
    start = utf16_units(text[:index])
    return start, start + utf16_units(needle)


@dataclass(frozen=True)
class Replacement:
    """One complete Qt range and its replacement, before any editor write."""

    start: int
    end: int
    text: str


def plan_replacement(
    text: str, needle: str, replacement: str, start: int, end: int
) -> Replacement | None:
    """Replace all literal matches inside selection, or whole text if collapsed."""
    if start > end:
        raise ValueError("Selection boundaries must be ordered.")
    first, last = index_at(text, start), index_at(text, end)
    if not needle:
        return None
    if start == end:
        start, end, first, last = 0, utf16_units(text), 0, len(text)
    old = text[first:last]
    new = old.replace(needle, replacement)
    return None if new == old else Replacement(start, end, new)


def window_origin(
    left: int, top: int, screen_height: int, frame_height: int
) -> tuple[int, int]:
    """Map original Cocoa frame origin (0,500) to primary Qt logical coordinates.

    Use the complete screen and decorated frame, not available area, content
    height or physical pixels. Negative positions are valid original results.
    """
    if screen_height <= 0 or frame_height <= 0:
        raise ValueError("Screen and window frame heights must be positive.")
    return left, top + screen_height - 500 - frame_height


def client_sizes(extra: tuple[int, int], saved_frame: tuple[int, int] | None) -> tuple:
    """Retain initial content500×400 but original NS frame min/max constraints."""
    if not (0 <= extra[0] < 500 and 0 <= extra[1] < 400):
        raise ValueError("Window frame decoration extents are invalid.")
    low = (500 - extra[0], 400 - extra[1])
    high = (1200 - extra[0], 800 - extra[1])
    initial = (
        (500, 400)
        if saved_frame is None
        else (saved_frame[0] - extra[0], saved_frame[1] - extra[1])
    )
    return low, high, initial


def show(*, path: Path | None = None, qt: Any = None) -> Any:
    """Open the owned floating editor; tests inject an explicit temporary path."""
    import sys

    from fontlabapp import _native
    from fontlabapp.core import scripting
    from fontlabapp.qt.properties import value
    from fontlabapp.core.scripting import show_script_dialog
    from fontlabapp.proof.text_holder.ui import dialog_type
    from fontlabapp.proof.text_holder.storage import TextStore, default_path

    qt = qt if qt is not None else _native("PythonQt")
    store = TextStore(path if path is not None else default_path(qt))
    # Load once and finish the hidden owned candidate before retiring a draft.
    content, saved_frame = store.load(), store.size()
    old = getattr(sys, "_fontlab_samples", {}).get(KEY)
    old_store = getattr(old, "store", None)
    if old_store is not None and old_store.path == store.path:
        frame = value(old, "frameGeometry")
        saved_frame = (int(value(frame, "width")), int(value(frame, "height")))
    candidate = dialog_type(qt, store)(
        scripting._native("fontlab").MainWindow(), snapshot=(content, saved_frame)
    )
    try:
        result = show_script_dialog(lambda parent: candidate, KEY)
    except BaseException:
        candidate._discard()
        raise
    if result is not candidate:
        candidate._discard()
    return result
