# this_file: src/fontlabapp/qt/images/view.py
# SPDX-License-Identifier: MIT
"""Injected QLabel image presentation in points, rendered at display resolution.

Resource lookup, image APIs, alignment and foreign enums belong to the caller.
The renderer receives a pixel scale and returns a QPixmap. Fit modes request
that scale directly, retaining vector/high-DPI resource quality. No binding,
application, event loop or font API loads here. Call on the widget's GUI thread.
"""

from collections.abc import Callable
from typing import Any, Literal


def present(
    qt: Any,
    label: Any,
    render: Callable[[float], Any] | None = None,
    *,
    size: tuple[float, float] = (0.0, 0.0),
    natural: tuple[float, float] = (0.0, 0.0),
    mode: Literal["down", "fit", "none", "stretch"] = "down",
) -> None:
    """Clear or present an image using the caller's point sizes and renderer.

    Preserve proportional-down, proportional-up/down, unscaled and stretched
    behavior. Zero natural dimensions use scale1; zero fitted frames request
    scale0, preserving the caller's established empty-frame renderer policy.
    Set the resulting pixmap's DPR to the label's display ratio. Render/scale
    failures propagate before setPixmap; widget setter failures propagate unchanged.
    """
    if render is None:
        label.clear()
        return
    if mode not in {"down", "fit", "none", "stretch"}:
        raise ValueError(f"Unknown image fit mode: {mode}")
    ratio = label.devicePixelRatioF()
    width, height = size
    if mode == "stretch":
        flags = qt.QtCore.Qt
        pixmap = render(ratio).scaled(
            round(width * ratio),
            round(height * ratio),
            flags.IgnoreAspectRatio,
            flags.SmoothTransformation,
        )
    else:
        w, h = natural
        fit = min(width / w, height / h) if w and h else 1.0
        scale = {"down": min(fit, 1.0), "fit": fit, "none": 1.0}[mode]
        pixmap = render(scale * ratio)
    pixmap.setDevicePixelRatio(ratio)
    label.setPixmap(pixmap)
