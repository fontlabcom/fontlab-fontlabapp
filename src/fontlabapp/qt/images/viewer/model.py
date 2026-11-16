# this_file: src/fontlabapp/qt/images/viewer/model.py
# SPDX-License-Identifier: Apache-2.0
"""Inspect font reference artwork with either complete original image workflow.

Both panels open local images, preserve their original zoom/Fit policies and
print only on explicit action. They use FontLab's existing Qt runtime and do
not read or edit font data. File and printer dialogs remain asynchronous.
"""
from threading import current_thread, main_thread
from typing import Any


def scaled_size(width: int, height: int, factor: float) -> tuple[int, int]:
    """Keep the source's raw-pixel integer truncation, including zero sizes."""
    return int(width * factor), int(height * factor)


def scroll_value(factor: float, old: int, page: int) -> int:
    """Preserve the source center-scroll rule after the image label resizes."""
    return int(factor * old + (factor - 1) * page / 2)


def _show(part: int) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open reference image viewers on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.qt.images.viewer.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    return show_script_dialog(panel_type(qt.QtCore, qt.QtGui, part), f"reference_image_{part}")


def show() -> Any:
    """Open free zoom, scale-preserving Fit and native-size image printing."""
    return _show(2)


def show_bounded() -> Any:
    """Open bounded zoom, Fit reset and aspect-fit owned temporary PDF printing."""
    return _show(3)
