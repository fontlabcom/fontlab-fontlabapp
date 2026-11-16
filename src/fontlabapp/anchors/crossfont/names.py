# this_file: src/fontlabapp/anchors/crossfont/names.py
# SPDX-License-Identifier: Apache-2.0
"""Resolve insertion names through the host's complete native anchor helper.

Qt trimming, numeric suffix conversion and Unicode behavior belong to the host.
A detached name-only layer preserves captured duplicate names, asks addAnchor,
and releases its owned placeholders without removeAnchor/changed notifications.
The exact host cleanup/queue behavior requires separate native qualification.
"""

from contextlib import ExitStack
from typing import Any

from fontlabapp.anchors.duplicates.capture import check


def insertion_name(
    name: str, names: tuple[str, ...], native: Any, qt: Any, deadline: float
) -> str:
    """Ask native addAnchor with the exact ordered existing-name multiset."""
    check(deadline)
    layer = native.flLayer()
    try:
        with ExitStack() as owned:
            pins = []
            try:
                for current in (*names, name):
                    check(deadline)
                    pin = native.flPinPoint(qt.QtCore.QPointF(0, 0))
                    owned.callback(pin.release)
                    pins.append(pin)
                    pin.name = current
                    layer.addAnchor(pin)
                    if len(pins) <= len(names):
                        # Retain existing duplicates/whitespace exactly; only
                        # insertion, not a plain setter, normalizes a pin name.
                        pin.name = current
                        if str(pin.name) != current:
                            raise ValueError(
                                "Native staging could not retain an existing name."
                            )
                return str(pins[-1].name)
            finally:
                # removeAnchor calls changed(); clearAnchors removes dependency
                # edges without that notification. Pins release after clearing.
                layer.clearAnchors()
    finally:
        layer.release()
