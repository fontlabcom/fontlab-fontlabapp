# this_file: src/fontlabapp/contours/affine.py
"""Pure 2D affine math in Qt's row-vector convention. No Qt import.

What it does:
    Holds a transform as six floats ``(a, b, c, d, e, f)``, the same order as
    ``QTransform(m11, m12, m21, m22, dx, dy)``. A point maps as
    ``x' = a*x + c*y + e`` and ``y' = b*x + d*y + f``.

How to use:
    ``concat(first, then)`` applies ``first``, then ``then``. This is Qt's
    ``first * then``. ``apply`` maps one point. ``invert`` gives the inverse.
    ``rotation`` makes a rotation; ``IDENTITY`` changes nothing.
    ``from_qtransform`` copies a native QTransform into plain floats.
    ``viewport_transform`` reads a FontLab canvas map as one Affine.
    Example: ``apply(concat(glyph_to_canvas, canvas_to_view), x, y)`` maps
    one glyph point to widget pixels.

Why this design:
    - Plain tuples keep no native wrapper alive and are safe in paint code.
    - No Qt import. The module loads in a cold FontLab start (5 s limit) and in
      tests without PythonQt. Qt classes arrive as arguments.
    - Every public function rejects non-finite numbers with ``ValueError`` by
      default. A bad native matrix then fails loud, not as a silent bad paint.
      Pass ``finite=False`` only for deliberate raw math.

Used by: ``canvas_rsb``, ``canvas_anchor_rings``, ``drawing``. Glyport adopts
the same names later (``fontlab_glyport.drawing.context``).
"""

import math
from collections.abc import Callable
from typing import Any

__all__ = [
    "IDENTITY",
    "SINGULAR_EPSILON",
    "Affine",
    "apply",
    "concat",
    "from_qtransform",
    "invert",
    "rotation",
    "viewport_transform",
]

#: Six floats ``(a, b, c, d, e, f)`` in ``QTransform(m11, m12, m21, m22, dx, dy)`` order.
Affine = tuple[float, float, float, float, float, float]
#: The transform that maps every point to itself.
IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

#: Smallest ``|determinant|`` that ``invert`` accepts. Same bound as the Glyport copy.
SINGULAR_EPSILON = 1e-12

_QT_GETTERS = ("m11", "m12", "m21", "m22", "dx", "dy")


def _require_finite(values: tuple[float, ...], what: str) -> None:
    """Raise ValueError when any value is NaN or infinite."""
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Non-finite {what}; all values must be finite.")


def concat(first: Affine, then: Affine, *, finite: bool = True) -> Affine:
    """Apply ``first``, then ``then`` (Qt's row-vector ``first * then``).

    Order matters. With ``finite`` set, both inputs and the result must be
    finite; an overflow therefore raises ``ValueError`` too.
    """
    a, b, c, d, e, f = first
    A, B, C, D, E, F = then
    result = (
        a * A + b * C,
        a * B + b * D,
        c * A + d * C,
        c * B + d * D,
        e * A + f * C + E,
        e * B + f * D + F,
    )
    if finite:
        _require_finite((*first, *then, *result), "affine transform")
    return result


def apply(
    t: Affine, x: float, y: float, *, finite: bool = True
) -> tuple[float, float]:
    """Map one point ``(x, y)`` through ``t``."""
    a, b, c, d, e, f = t
    result = x * a + y * c + e, x * b + y * d + f
    if finite:
        _require_finite((*t, x, y, *result), "affine point")
    return result


def invert(t: Affine) -> Affine:
    """Return the inverse of ``t``.

    Raises ``ValueError`` for a non-finite or singular matrix (``|det|`` below
    ``SINGULAR_EPSILON``).
    """
    _require_finite(t, "affine transform")
    a, b, c, d, e, f = t
    det = a * d - b * c
    if abs(det) < SINGULAR_EPSILON:
        raise ValueError("transform is not invertible")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_)


def rotation(degrees: float) -> Affine:
    """Return a rotation about the origin; positive turns x toward y."""
    r = math.radians(degrees)
    cos, sin = math.cos(r), math.sin(r)
    return cos, sin, -sin, cos, 0.0, 0.0


def from_qtransform(qt_transform: Any, *, finite: bool = True) -> Affine:
    """Copy a QTransform into six floats; retain no native wrapper."""
    values = tuple(float(getattr(qt_transform, n)()) for n in _QT_GETTERS)
    if finite:
        _require_finite(values, "native transform")
    return values  # type: ignore[return-value]


def viewport_transform(canvas: Any, point_type: Callable[[float, float], Any]) -> Affine:
    """Sample ``canvas.mapToViewportF`` at (0,0), (1,0), (0,1) as one Affine.

    ``mapToViewportF`` maps canvas units to widget pixels and is affine. Three
    samples fix it. ``point_type`` is the caller's ``QPointF`` class; it keeps
    this module free of Qt. Read fresh at each paint or poll: pan and zoom
    change the map. Raises ``ValueError`` when the native map is non-finite.
    """
    origin, x, y = (
        canvas.mapToViewportF(point_type(px, py)) for px, py in ((0, 0), (1, 0), (0, 1))
    )
    result = (
        x.x() - origin.x(),
        x.y() - origin.y(),
        y.x() - origin.x(),
        y.y() - origin.y(),
        origin.x(),
        origin.y(),
    )
    _require_finite(result, "native viewport transform")
    return result
