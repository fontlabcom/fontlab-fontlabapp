# this_file: src/fontlabapp/metrics/vertical/native.py
# SPDX-License-Identifier: Apache-2.0
"""Read all stored master metrics through fontpr's metadata-only native API.

The source writer emits master ascender/descender explicitly; omitted lineGap,
safeTop and safeBottom mean stored zero. Missing hhea otherData entries remain
unset (None), distinct from zero. No setMaster, glyph getter, font/selection/
history/preference/Output writer is called. Serialization/getter preservation,
actual9787schema and order still require dedicated owned native qualification.
"""

from math import isfinite
from pathlib import Path
from time import monotonic, strftime
from typing import Any

from fontlabapp import _native
from fontlabapp.metrics.vertical.model import MasterMetrics, MetricsReport, render


def _call(name: str, **arguments: Any) -> Any:
    """Call a documented native read tool only when the report is invoked."""
    return _native("fontpr").call(name, **arguments)


def _check(deadline: float) -> None:
    """Reject an overrun at Python checkpoints; never return a report prefix."""
    if monotonic() >= deadline:
        raise TimeoutError(
            "Vertical metric scan exceeded its deadline; no partial report."
        )


def _number(value: Any) -> int | float:
    """Keep numeric integers exact and accept native otherData numeric text."""
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            value = float(value)
    if type(value) is int or (type(value) is float and isfinite(value)):
        return value
    raise ValueError("A stored vertical metric is not a finite number.")


def _registry(deadline: float) -> tuple[tuple[int, str, int], ...]:
    """Keep native workspace font order and opaque API ids; never use flPackage.id."""
    _check(deadline)
    fonts = _call("list_fonts")["fonts"]
    if not isinstance(fonts, (list, tuple)) or not fonts:
        raise ValueError("Open fonts with masters before reporting vertical metrics.")
    result, seen = [], set()
    for font in fonts:
        _check(deadline)
        identifier, count = font["id"], font["masters_count"]
        if (
            type(identifier) is not int
            or identifier in seen
            or type(count) is not int
            or count < 1
        ):
            raise ValueError(
                "Unreadable or duplicate font identity/master count; refresh."
            )
        labels = tuple(
            font.get(key, "") for key in ("file_name", "full_name", "family_name")
        )
        if any(not isinstance(label, str) for label in labels):
            raise ValueError("Unreadable open-font document name; refresh.")
        name = (
            Path(labels[0]).name
            if labels[0]
            else labels[1] or labels[2] or f"Untitled {identifier}"
        )
        result.append((identifier, name, count))
        seen.add(identifier)
    _check(deadline)
    return tuple(result)


def _master(identifier: int, document: str, entry: dict) -> MasterMetrics:
    """Parse the native fontMaster record; do not substitute a missing master."""
    master = entry.get("fontMaster")
    if not isinstance(master, dict) or any(
        key not in master for key in ("name", "ascender", "descender")
    ):
        raise ValueError("A font master has incomplete native metric data.")
    other = master.get("otherData", {})
    if not isinstance(master["name"], str) or not isinstance(other, dict):
        raise TypeError("Unreadable native master name/otherData.")
    hhea = tuple(
        _number(other[key]) if key in other else None
        for key in ("hhea_ascender", "hhea_descender", "hhea_line_gap")
    )
    values = (
        _number(master["ascender"]),
        _number(master["descender"]),
        _number(master.get("lineGap", 0)),
        *hhea,
        _number(master.get("safeBottom", 0)),
        _number(master.get("safeTop", 0)),
    )
    return MasterMetrics(identifier, document, master["name"], values)


def _read(fonts: tuple, deadline: float) -> tuple[MasterMetrics, ...]:
    """Read every serialized master in order; discard no unreadable record."""
    rows = []
    for identifier, document, count in fonts:
        _check(deadline)
        data = _call("get_font_info", font_id=identifier)
        masters = data.get("masters")
        if not isinstance(masters, (list, tuple)) or len(masters) != count:
            raise ValueError(
                "Open-font master domain changed or is unreadable; refresh."
            )
        for entry in masters:
            _check(deadline)
            rows.append(_master(identifier, document, entry))
    _check(deadline)
    return tuple(rows)


def capture() -> MetricsReport:
    """Double-read all open fonts/masters and fence the final registry in two seconds.

    Calls may serialize large metadata, including kerning/lib; discard everything
    except immutable document/master/eight-value rows. Native C++ calls cannot be
    preempted. No fallback, sorting, active-master switch or partial report.
    All-native preservation/schema/order qualification remains pending.
    """
    deadline = monotonic() + 2.0
    first = _registry(deadline)
    rows = _read(first, deadline)
    second = _registry(deadline)
    repeated = _read(second, deadline)
    final = _registry(deadline)
    _check(deadline)
    if first != second or second != final or rows != repeated:
        raise ValueError(
            "Open fonts, masters or vertical metrics changed; refresh the report."
        )
    return MetricsReport(rows, strftime("%H:%M:%S"))
