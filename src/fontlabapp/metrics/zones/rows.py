# this_file: src/fontlabapp/metrics/zones/rows.py
# SPDX-License-Identifier: Apache-2.0
"""Parse visible zone cells and retain explicit per-row source identities.

Hidden metadata never participates in visible tuple sorting. Duplicate visible
rows use their source key as a deterministic tie-breaker; no name/value lookup
is used to recover identity after editing or removing a row.
"""

from collections.abc import Iterable
from dataclasses import replace
from math import isfinite

from fontlabapp.metrics.zones.data import Origin, Zone, Zones

Row = tuple[str, float, float, str]


def number(value: object) -> float:
    """Parse a finite source/table number before rounding or arithmetic."""
    if isinstance(value, bool):
        raise ValueError("A finite number is required.")  # noqa: TRY004
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("A finite number is required.") from error
    if not isfinite(result):
        raise ValueError("A finite number is required.")
    return result


def text(value: object) -> str:
    """Reject malformed text before it reaches a native QString boundary."""
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Zone kind and name require valid text.")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("Zone kind and name require valid text.") from error
    return value


def key(zone: Zone) -> tuple:
    """Keep source tuple sorting; resolve equal visible values by opaque key."""
    return zone.position, zone.width, zone.name, zone.origin.key if zone.origin else ""


def _origin(origin: Origin | None) -> None:
    """Require immutable source identity before sorting or retaining its bytes."""
    if origin is not None and (
        not isinstance(origin, Origin)
        or not text(origin.key)
        or type(origin.metadata) is not bytes
    ):
        raise ValueError("Invalid source identity.")


def parse_rows(
    rows: Iterable[Iterable[object]], *, origins: Iterable[Origin | None] | None = None
) -> Zones:
    """Parse every four-cell row and its separate exact-length identity channel."""
    parsed = []
    for index, cells in enumerate(rows, 1):
        try:
            kind, position, width, name = cells
            side = "Bottom" if text(kind).strip().lower().startswith("b") else "Top"
            parsed.append(
                (
                    side,
                    Zone(
                        round(number(position)), abs(round(number(width))), text(name)
                    ),
                )
            )
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid zone row {index}: {error}") from error
    identities = tuple(origins) if origins is not None else (None,) * len(parsed)
    if len(identities) != len(parsed):
        raise ValueError("Zone row identities differ from the complete table.")
    kinds: dict[str, list[Zone]] = {"Top": [], "Bottom": []}
    seen = set()
    for index, ((side, zone), origin) in enumerate(
        zip(parsed, identities, strict=True), 1
    ):
        if origin is not None:
            try:
                _origin(origin)
            except ValueError as error:
                raise ValueError(
                    f"Invalid zone row {index}: invalid source identity."
                ) from error
            if origin.key in seen:
                raise ValueError("Duplicate zone source identity.")
            seen.add(origin.key)
        kinds[side].append(replace(zone, origin=origin))
    return Zones(
        tuple(sorted(kinds["Top"], key=key)), tuple(sorted(kinds["Bottom"], key=key))
    )


def ordered(zones: Zones) -> tuple[tuple[str, Zone], ...]:
    """Copy display order without native item handles or mutable metadata."""
    return tuple(
        (kind, zone)
        for kind, values in (("Top", zones.top), ("Bottom", zones.bottom))
        for zone in sorted(values, key=key, reverse=True)
    )


def rows(zones: Zones) -> tuple[Row, ...]:
    """Display top rows first, then bottom, descending by the visible tuple."""
    return tuple(
        (kind, zone.position, zone.width, zone.name) for kind, zone in ordered(zones)
    )


def origins(zones: Zones) -> tuple[Origin | None, ...]:
    """Return identities in exactly the same order as the four visible cells."""
    return tuple(zone.origin for _, zone in ordered(zones))


def normalize(zones: Zones) -> Zones:
    """Normalize visible source values while retaining all original metadata."""
    for zone in (*zones.top, *zones.bottom):
        _origin(zone.origin)
    return parse_rows(rows(zones), origins=origins(zones))


def require_origins(before: Zones, after: Zones) -> None:
    """Reject foreign, altered or duplicated source identities before staging."""
    captured = {origin.key: origin for origin in origins(before) if origin is not None}
    for origin in origins(after):
        if origin is not None and captured.get(origin.key) != origin:
            raise ValueError("Zone source identity or metadata changed; reopen.")


def inherit(proposed: Zones, current: Zones) -> Zones:
    """Retain each exact Suggest match once; replacement rows have no origin."""
    pool = list(ordered(current))
    retained = []
    for side, zone in ordered(proposed):
        index = next(
            (
                i
                for i, (kind, old) in enumerate(pool)
                if kind == side
                and (old.position, old.width, old.name)
                == (zone.position, zone.width, zone.name)
            ),
            None,
        )
        retained.append(pool.pop(index)[1].origin if index is not None else None)
    return parse_rows(rows(proposed), origins=retained)


def result_matches(expected: Zones, actual: Zones, before: Zones) -> bool:
    """Allow fresh identities for new rows; preserve every retained source row.

    Keep exact visible values/order. Equal visible duplicates match one-to-one
    by origin; a new row cannot steal even an explicitly removed source key.
    The adapter must independently qualify new-guide metadata/defaults.
    """
    normalize(actual)
    captured = {origin.key for origin in origins(before) if origin is not None}
    for left, right in ((expected.top, actual.top), (expected.bottom, actual.bottom)):
        if tuple(key(z)[:3] for z in left) != tuple(key(z)[:3] for z in right):
            return False
        pool = list(right)
        for zone in left:
            index = next(
                (
                    i
                    for i, found in enumerate(pool)
                    if key(zone)[:3] == key(found)[:3]
                    and (
                        zone.origin == found.origin
                        if zone.origin is not None
                        else found.origin is None or found.origin.key not in captured
                    )
                ),
                None,
            )
            if index is None:
                return False
            pool.pop(index)
    return True
