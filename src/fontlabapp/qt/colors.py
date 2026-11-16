# this_file: src/fontlabapp/qt/colors.py
# SPDX-License-Identifier: MIT
"""Injected Qt color presentation; foreign color/callback policy stays local.

No Qt binding is imported. Late getters retain native construction, mutation,
signal handoff and failure order. Dialogs keep the original one-instance policy:
accept/reject does not release ownership; only explicit disposal does.
"""
from collections.abc import Callable, Iterable
from typing import Any
from fontlabapp.qt.properties import value


def rgba255(channels: Iterable[float]) -> tuple[int, ...]:
    """Scale and banker's-round every channel without introducing clamping."""
    return tuple(round(channel * 255) for channel in channels)


def rgba_css(channels: Iterable[float]) -> str:
    """Format four channels; original unpack stops after the fifth on overflow.

    Do not materialize the iterable: later values may raise or never terminate.
    """
    red, green, blue, alpha = (round(channel * 255) for channel in channels)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def swatch_style(channels: Iterable[int]) -> str:
    """Format a button swatch from already rounded channels."""
    red, green, blue, alpha = channels
    return f"background-color: rgba({red}, {green}, {blue}, {alpha});"


def group_box_style(fill: Callable[[], str] | None,
                    border: Callable[[], str] | None,
                    width: Any, radius: Any) -> str | None:
    """Build optional ordered rules; no options means no stylesheet write.

    Color suppliers run only for their declared rule, retaining width/color and
    radius evaluation order. Callers retain their color-object conversion.
    """
    rules = []
    if fill is not None:
        rules.append(f"background-color: {fill()};")
    if border is not None:
        rules.append(f"border: {round(width or 1)}px solid {border()};")
    if radius is not None:
        rules.append(f"border-radius: {round(radius)}px;")
    return "QGroupBox { " + " ".join(rules) + " }" if rules else None


def color_palette(gui: Any, widget: Callable[[], Any],
                  convert: Callable[[], Any] | None,
                  role: Callable[[Any], Any]) -> Any:
    """Reset with a default palette or mutate the current palette once.

    Caller selects the role, converts its color and applies the resulting
    palette/autofill in its original order. None never reads widget or role.
    Read role before setter lookup; convert only after that lookup succeeds.
    """
    palette_class = gui.QPalette
    palette = palette_class() if convert is None else value(widget(), "palette")
    if convert is not None:
        native_role = role(palette_class)
        palette.setColor(native_role, convert())
    return palette


class ColorDialog:
    """One owned nonmodal dialog; caller owns tracking and selected-color policy."""

    def __init__(self) -> None:
        self.dialog: Any = None

    def open(self, gui: Any, channels: Callable[[], Iterable[int]],
             parent: Callable[[], Any], track: Callable[[], Callable],
             selected: Callable[[], Callable]) -> None:
        """Store before tracking/open; failures retain any created dialog."""
        if self.dialog is not None:
            return
        dialog = gui.QColorDialog(gui.QColor(*channels()), parent())
        self.dialog = dialog
        track()(dialog.colorSelected, selected())
        dialog.open()

    def dispose(self) -> None:
        """Called after caller disconnect; clear only after deletion succeeds."""
        if self.dialog is not None:
            self.dialog.deleteLater()
            self.dialog = None
