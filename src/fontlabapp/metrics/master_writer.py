# this_file: src/fontlabapp/metrics/master_writer.py
# SPDX-License-Identifier: Apache-2.0
"""Write font master vertical metrics as ONE native Undo step.

What: ``write_master_metrics(package, {master: {field: value}}, title)``
writes ascender, descender, x-height, caps height and line gap of one or more
masters through ``font_history.commit_masters`` (route A of issue 122 M2,
measured for ascender and xHeight on FontLab 9.0.9790). The same
``flPackage.*_value`` setters are what Font Info uses
(``fontinfo_data.cpp:577-581``).

Fields (``FIELDS``): ``ascender``, ``descender``, ``xHeight``,
``capsHeight`` and ``lineGap``. ``capHeight`` is an alias of ``capsHeight``
(``ALIASES``): the host registers ``flPackage.capHeight`` on the same
setter (``pyflpackage.cpp:1405-1414,3545``); results use ``capsHeight``.
``lineGap`` is the master line gap of Font Info (``flPackage.lineGap_value``).
The separate hhea line gap is in master ``otherData``; no measured setter
exists for it, so a name such as ``hhea_line_gap`` is refused as unknown.

Refusals (``ValueError``) come before any history call: an empty request, an
unknown field, a value that is not a finite real number, and every refusal of
``commit_masters`` (GUI thread, Font window, unknown master).

Read-back: FontLab stores these values as C++ ``double``
(``flpackage.h:603-654``). A stored value reads back as the same double, so
the tolerance (``TOLERANCE``) only absorbs a last-bit difference; a rounded
or clamped value fails the read-back, all values are restored and
``font_history.RolledBackError`` is raised.

Known host defect (fl#8574): after Undo/Redo, the font-metric guidelines show 3 of 9
until ``updateFontMetrics()`` or a reopen (see ``font_history``).
``scripting.write_font_info`` stays unchanged. Offline tests prove the call
order only.
"""

from collections.abc import Mapping
from math import isclose, isfinite
from typing import Any

from fontlabapp.core.history.masters import MasterEdit, MastersCommitted, commit_masters

#: Public field name -> ``flPackage`` property, in write order.
FIELDS: Mapping[str, str] = {
    "ascender": "ascender_value",
    "descender": "descender_value",
    "xHeight": "xHeight_value",
    "capsHeight": "capsHeight_value",
    "lineGap": "lineGap_value",
}
#: Accepted alias -> field in ``FIELDS``.
ALIASES: Mapping[str, str] = {"capHeight": "capsHeight"}
#: Absolute read-back tolerance in font units for a stored C++ double.
TOLERANCE = 1e-9
#: The default Undo name.
TITLE = "Master Metrics"


def _value(master: str, field: str, value: object) -> float:
    """Return ``value`` as a float, or raise ``ValueError`` for a bad cell."""
    if field not in FIELDS:
        raise ValueError(
            f"Unknown metric field {field!r} for master {master!r}; use one of {list(FIELDS)}."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{master} {field} must be a finite number, not {value!r}.")
    return float(value)


def parse(values: Mapping[str, Mapping[str, object]]) -> dict[str, dict[str, float]]:
    """Return the checked request ``{master: {field: float}}`` in field order.

    Aliases (``ALIASES``) become their field. Raise ``ValueError`` for an
    empty request, an empty master entry, an unknown field, a field named
    twice (also through an alias) or a non-finite value. No native call is made.
    """
    if not values:
        raise ValueError("No master metric to write.")
    result: dict[str, dict[str, float]] = {}
    for master, fields in values.items():
        if not isinstance(master, str) or not fields:
            raise ValueError(f"Master {master!r} has no metric to write.")
        parsed: dict[str, float] = {}
        spelled: dict[str, str] = {}
        for field, value in fields.items():
            name = ALIASES.get(field, field)
            if name in parsed:
                raise ValueError(
                    f"Master {master!r} names {name!r} twice ({spelled[name]!r} and {field!r})."
                )
            parsed[name], spelled[name] = _value(master, name, value), field
        result[master] = {field: parsed[field] for field in FIELDS if field in parsed}
    return result


def _edit(package: Any, plan: Mapping[str, float]) -> MasterEdit:
    """Return the ``MasterEdit`` that writes ``plan`` on the selected master."""

    def read() -> dict[str, float]:
        return {field: float(getattr(package, FIELDS[field])) for field in plan}

    def write(values: Mapping[str, float]) -> None:
        for field, value in values.items():
            setattr(package, FIELDS[field], value)

    def verify(found: Mapping[str, float]) -> list[str]:
        return [
            f"{field} {found[field]:g} (planned {value:g})"
            for field, value in plan.items()
            if not isclose(found[field], value, rel_tol=0.0, abs_tol=TOLERANCE)
        ]

    return MasterEdit(read, lambda: write(plan), read, verify, write)


def write_master_metrics(
    package: Any,
    values: Mapping[str, Mapping[str, object]],
    title: str = TITLE,
    *,
    native: Any = None,
) -> MastersCommitted:
    """Write ``values`` (``{master: {field: value}}``) as ONE Undo step.

    Return ``font_history.MastersCommitted``: ``values`` holds each master's
    read-back ``{field: float}``; disclose ``pending_note`` with
    ``edit_guards.disclose``. ``native`` is the ``fontlab`` module (default:
    the native one). Raise as ``parse`` and ``font_history.commit_masters``.
    """
    plan = parse(values)
    edits = {master: _edit(package, fields) for master, fields in plan.items()}
    return commit_masters(package, title, edits, native=native)


__all__ = ["ALIASES", "FIELDS", "TITLE", "TOLERANCE", "parse", "write_master_metrics"]
