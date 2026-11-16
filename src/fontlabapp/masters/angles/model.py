# this_file: src/fontlabapp/masters/angles/model.py
# SPDX-License-Identifier: Apache-2.0
"""Stage master italic angles and apply one native masters-container history row.

Native imports stay lazy. Complete source values, font identity, master order and
current master are checked before history. A native partial-write error remains
in the one named history batch so the caller can invalidate the panel and Undo.
The original writer's notifying master restoration is required for native caches.
"""

from dataclasses import dataclass
from math import isfinite
from struct import pack, unpack
from typing import Any

from fontlabapp import _native
from fontlabapp.masters.inspect.model import italic_angles
from fontlabapp.core.scripting import current_package

MIN_ANGLE, MAX_ANGLE = -45.0, 45.0
DEFAULT_BLUE_SCALE = 0.039625
HISTORY_HINT_DIGITS = 8
HISTORY_COMPACT_LIMIT = 32768
NATIVE_INT_LIMIT = 2147483646


@dataclass(frozen=True)
class AngleSnapshot:
    """Plain immutable source values; no native object survives in the snapshot."""

    package_id: int
    current_master: str
    angles: tuple[tuple[str, float], ...]


def capture(package: Any) -> AngleSnapshot:
    """Read every ordered master angle and restore the original master on failure."""
    masters, original = tuple(package.masters), package.master
    if not masters or len(set(masters)) != len(masters) or original not in masters:
        raise ValueError("Source master order or current master is unavailable.")
    values = italic_angles(package, list(masters))
    if not all(isfinite(value) for value in values.values()):
        raise ValueError("Source italic angle is not finite.")
    if (tuple(package.masters), package.master) != (masters, original):
        raise ValueError("Source masters changed during capture.")
    return AngleSnapshot(package.id, original, tuple(values.items()))


def _values(snapshot: AngleSnapshot, proposed: dict[str, float]) -> dict[str, float]:
    """Parse the complete proposed batch before performing any native mutation."""
    values = dict(snapshot.angles)
    for master, value in proposed.items():
        if master not in values:
            raise ValueError(f"Unknown master: {master!r}.")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not MIN_ANGLE <= value <= MAX_ANGLE
            or not isfinite(value)
        ):
            raise ValueError(f"Italic angle for {master!r} must be between -45 and 45.")
        values[master] = float(value)
    return values


def _finish(
    native: Any, package: Any, original: str, container: Any, title: str
) -> None:
    """Restore source context and publish the single batch even after a setter error."""
    try:
        if package.master != original:
            package.setMaster(original, True)
    finally:
        try:
            native.flItems.notifyChangesApplied(title, [container])
        finally:
            native.UpdateAll()


def history_preserves_blue_scale(
    value: float, inherited: float = DEFAULT_BLUE_SCALE
) -> bool:
    """Refuse the measured native decimal/binary32 hinting loss (FontLab #8531).

    This models the current host's numeric history round trip without touching font
    data or history. Compare at its saved eight-decimal hint precision; do not repair
    hinting values before, after, or during Undo. Extreme values fail closed before
    the native encoder's signed-integer conversion can overflow.
    """
    if not isfinite(value) or abs(value) > NATIVE_INT_LIMIT:
        return False
    if abs(value - DEFAULT_BLUE_SCALE) * 1e12 <= min(abs(value), DEFAULT_BLUE_SCALE):
        restored = inherited
    else:
        scaled, exponent = abs(value), 0
        while (
            abs(scaled - int(scaled + 0.5)) > 10**-HISTORY_HINT_DIGITS
            and exponent < HISTORY_HINT_DIGITS
        ):
            scaled *= 10
            exponent += 1
            if scaled > NATIVE_INT_LIMIT:
                return False
        mantissa = int(scaled + 0.5)
        decoded = value
        if exponent < HISTORY_HINT_DIGITS and mantissa < HISTORY_COMPACT_LIMIT:
            decoded = (-1 if value < 0 else 1) * mantissa / 10**exponent
        restored = unpack("f", pack("f", decoded))[0]
    return isfinite(restored) and float(f"{value:.8f}") == float(f"{restored:.8f}")


def _check_hinting(package: Any) -> None:
    """Read all master hinting scalars and refuse unsafe history before mutation."""
    original, unsafe = package.master, []
    inherited = float(package.info.postscriptBlueScale)
    try:
        for master in package.masters:
            if package.master != master:
                package.setMaster(master)
            if not history_preserves_blue_scale(
                float(package.hinting.blueScale), inherited
            ):
                unsafe.append(master)
    finally:
        if package.master != original:
            package.setMaster(original)
    if unsafe:
        raise ValueError(
            "FontLab Undo cannot preserve blueScale exactly for "
            + ", ".join(unsafe)
            + "; angle changes were refused (FontLab #8531)."
        )


def apply(
    snapshot: AngleSnapshot,
    proposed: dict[str, float],
    *,
    undo_name: str = "Italic Angle",
) -> list[str]:
    """Apply finite in-range angles in font order, returning only changed masters.

    Empty and unchanged batches create no history. A switched or changed font refuses
    before history. Package/glyph/auto layers are never included in the notification.
    """
    values = _values(snapshot, proposed)
    package = current_package(snapshot.package_id)
    if package is None:
        raise ValueError("The original font is no longer current; reopen this tool.")
    if capture(package) != snapshot:
        raise ValueError("Source angles or masters changed; refresh this tool.")
    changed = [master for master, old in snapshot.angles if old != values[master]]
    if not changed:
        return []
    _check_hinting(package)
    native = _native("fontlab")
    container = package.mastersContainer()
    container.checkInitHistoryState(0)
    try:
        for master, value in values.items():
            if package.master != master:
                package.setMaster(master)
            if master in changed:
                package.italicAngle_value = value
    finally:
        _finish(native, package, snapshot.current_master, container, undo_name)
    return changed


def write_angles(package: Any, angles: dict[str, float]) -> list[str]:
    """Preserve the original direct helper while repeating the complete source guard."""
    return apply(capture(package), angles)
