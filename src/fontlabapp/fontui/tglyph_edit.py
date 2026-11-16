# this_file: src/fontlabapp/fontui/tglyph_edit.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free point edits for TGlyph: move, delete, rubber band and redraw.

What: pure functions over ``fontlabapp.fontui.tglyph_model`` values.
``move_points`` shifts the selected points; a moved on-curve point carries its
adjacent off-curve handles (wrapping round a closed contour, not an open one).
``delete_points`` removes the selected points, and the handles of selected
on-curve points, then ``normalise`` keeps each touched contour valid: a
contour with no on-curve point left is dropped, handles left in front of a
line or move point are dropped, a curve left without handles becomes a line,
a cubic ``curve`` left with exactly one handle becomes a line (the lone handle
is dropped rather than reinterpreted as an implied quadratic),
a closed contour starts on an on-curve point and an open contour starts with
a ``move`` point. ``points_in_rect`` is the rubber-band hit test in screen
pixels and ``draw_contours`` replays contours into a point pen. Every
coordinate is stored as a float so a written glyph fingerprints exactly like
the same glyph read back.
``Editor`` is the gesture state over a ``TGlyphModel``: select, toggle,
rubber band, drag with a preview, nudge, delete and the pen tool. The pen's
first click only sets ``Editor.pending`` (drawn as a preview, never written);
the second click writes a two-point open contour, and Escape or a tool switch
discards the pending point. Each gesture yields at most one ``Edit``; ``Editor.commit`` writes it once through
``font.edit_glyph(name, layer=..., undo_name="TGlyph: <action> <name>")``,
redrawing only the staged contours (components and anchors stay), and returns
the fingerprint of the state it drew for ``fontlabapp.fontui.livesync.Echo``.
A failed write restores the pre-gesture glyph and re-raises.
Use: ``fontlabapp.fontui.tglyph.TGlyph`` forwards canvas input to ``Editor``.
Why: the structural rules stay unit-testable without Qt or FontLab.
"""

from dataclasses import dataclass, replace
from typing import Any

from .tglyph_model import (
    HIT_TOLERANCE,
    Contour,
    GlyphData,
    Point,
    TGlyphModel,
    View,
    fingerprint,
    hit_point,
)

__all__ = [
    "Edit",
    "Editor",
    "delete_points",
    "draw_contours",
    "handles",
    "move_points",
    "normalise",
    "points_in_rect",
    "toggle_points",
    "write_contours",
]

Key = tuple[int, int]


def handles(contour: Contour, index: int) -> list[int]:
    """Indices of the off-curve points next to the on-curve point at ``index``."""
    points = contour.points
    count = len(points)
    if not points[index].on_curve:
        return []
    found = []
    for step in (-1, 1):
        other = index + step
        if contour.closed:
            other %= count
        elif not 0 <= other < count:
            continue
        if other != index and not points[other].on_curve:
            found.append(other)
    return found


def _with_handles(data: GlyphData, selection: set[Key]) -> set[Key]:
    keys = {(c, p) for c, p in selection if c < len(data.contours) and p < len(data.contours[c].points)}
    for c, p in list(keys):
        keys.update((c, h) for h in handles(data.contours[c], p))
    return keys


def move_points(data: GlyphData, selection: set[Key], dx: float, dy: float) -> GlyphData:
    """``data`` with the selected points (and their handles) shifted by ``(dx, dy)``."""
    moved = _with_handles(data, selection)
    contours = tuple(
        Contour(
            tuple(
                replace(point, x=float(point.x + dx), y=float(point.y + dy)) if (c, p) in moved else point
                for p, point in enumerate(contour.points)
            )
        )
        for c, contour in enumerate(data.contours)
    )
    return replace(data, contours=contours)


def normalise(points: tuple[Point, ...], closed: bool) -> tuple[Point, ...] | None:
    """A valid contour from ``points``, or None when no on-curve point is left."""
    starts = [i for i, point in enumerate(points) if point.on_curve]
    if not starts:
        return None
    if closed:
        points = points[starts[0] :] + points[: starts[0]]  # cyclic order kept
    else:
        points = points[starts[0] : starts[-1] + 1]  # no dangling handles at either end
    # Split into (handles, on-curve) runs; a closed contour's trailing handles lead into point 0.
    runs: list[tuple[list[Point], Point]] = []
    pending: list[Point] = []
    for point in points:
        if point.on_curve:
            runs.append((pending, point))
            pending = []
        else:
            pending.append(point)
    if closed:
        runs[0] = (pending, runs[0][1])
    fixed = [_fix_run(offs, point) for offs, point in runs]
    if closed:
        lead, first = fixed[0]
        out = [first]
        for offs, point in fixed[1:]:
            out.extend(offs)
            out.append(point)
        out.extend(lead)
        return tuple(out)
    first = replace(fixed[0][1], type="move", smooth=False)
    out = [first]
    for offs, point in fixed[1:]:
        out.extend(offs)
        out.append(point)
    return tuple(out)


def _fix_run(offs: list[Point], point: Point) -> tuple[list[Point], Point]:
    if point.type in ("line", "move"):
        return [], point
    if not offs or (point.type == "curve" and len(offs) == 1):
        return [], replace(point, type="line")
    return offs, point


def delete_points(data: GlyphData, selection: set[Key]) -> GlyphData:
    """``data`` without the selected points; touched contours are normalised or dropped."""
    removed = _with_handles(data, selection)
    contours = []
    for c, contour in enumerate(data.contours):
        if not any(key[0] == c for key in removed):
            contours.append(contour)
            continue
        kept = tuple(point for p, point in enumerate(contour.points) if (c, p) not in removed)
        points = normalise(kept, contour.closed)
        if points is not None:
            contours.append(Contour(points))
    return replace(data, contours=tuple(contours))


def toggle_points(data: GlyphData, selection: set[Key]) -> GlyphData:
    """Toggle point roles, preserving coordinates and valid point-pen segments.

    Open endpoints must remain on-curve. A single control becomes quadratic;
    two controls become cubic unless the existing segment is quadratic.
    """
    contours = list(data.contours)
    for c, contour in enumerate(contours):
        chosen = {p for ci, p in selection if ci == c and 0 <= p < len(contour.points)}
        if not chosen:
            continue
        if not contour.closed and chosen & {0, len(contour.points) - 1}:
            raise ValueError("An open contour endpoint must stay on-curve")
        points = [
            replace(point, type=None if point.on_curve else "line", smooth=False) if p in chosen else point
            for p, point in enumerate(contour.points)
        ]
        on_curves = [p for p, point in enumerate(points) if point.on_curve]
        if not on_curves:
            raise ValueError("A contour must retain an on-curve point")
        for index, p in enumerate(on_curves):
            if not contour.closed and index == 0:
                continue
            previous = on_curves[index - 1]
            controls = (p - previous - 1) % len(points)
            kind = "line" if not controls else "curve" if controls == 2 else "qcurve"
            if controls and points[p].type == "qcurve":
                kind = "qcurve"
            points[p] = replace(points[p], type=kind)
        contours[c] = Contour(tuple(points))
    return replace(data, contours=tuple(contours))


def points_in_rect(data: GlyphData | None, view: View, rect: tuple[float, float, float, float]) -> set[Key]:
    """(contour, point) keys of own points inside the screen rectangle ``(x0, y0, x1, y1)``."""
    if data is None:
        return set()
    x0, x1 = sorted((rect[0], rect[2]))
    y0, y1 = sorted((rect[1], rect[3]))
    found = set()
    for c, contour in enumerate(data.contours):
        for p, point in enumerate(contour.points):
            sx, sy = view.to_screen(point.x, point.y)
            if x0 <= sx <= x1 and y0 <= sy <= y1:
                found.add((c, p))
    return found


def draw_contours(contours: tuple[Contour, ...], pen: Any) -> None:
    """Replay ``contours`` into a FontParts point pen."""
    for contour in contours:
        pen.beginPath()
        for point in contour.points:
            pen.addPoint((point.x, point.y), segmentType=point.type, smooth=point.smooth)
        pen.endPath()


def write_contours(font: Any, name: str, layer: str, contours: tuple[Contour, ...], undo_name: str) -> None:
    """Replace ``name``'s own contours on ``layer`` in one ``edit_glyph`` write."""
    edit = getattr(font, "edit_glyph", None)
    if not callable(edit):
        raise TypeError("Read-only: font has no edit_glyph")
    with edit(name, layer=layer, undo_name=undo_name) as glyph:
        glyph.clearContours()  # components and anchors stay on the staged glyph
        draw_contours(contours, glyph.getPointPen())


@dataclass(frozen=True)
class Edit:
    """One gesture's result: the action name, the glyph to write and the selection after."""

    action: str
    data: GlyphData
    selection: frozenset[Key]


class Editor:
    """Gesture state of one TGlyph window over ``model``; Qt-free.

    ``tool`` is ``"select"`` or ``"pen"``. ``drag`` holds the font-unit origin
    of a point drag, ``band`` the screen rectangle of a rubber band, ``pen``
    the contour index the pen tool is extending, ``pending`` the font-unit
    first point of a pen contour not yet written and ``before`` the glyph as
    it was when the current gesture started.
    """

    def __init__(self, model: TGlyphModel, label_prefix: str = "TGlyph", *, read_only: bool = False) -> None:
        self.label_prefix = label_prefix
        self.read_only = read_only
        self.model = model
        self.tool = "select"
        self.drag: tuple[float, float] | None = None
        self.band: tuple[float, float, float, float] | None = None
        self.base: set[Key] = set()
        self.pen: int | None = None
        self.pending: Point | None = None
        self.before: GlyphData | None = None

    @property
    def busy(self) -> bool:
        """True while a drag or a rubber band is in progress."""
        return self.drag is not None or self.band is not None

    def set_tool(self, tool: str) -> None:
        """Switch to ``"select"`` or ``"pen"``; any gesture and pen contour end."""
        if tool not in ("select", "pen"):
            raise ValueError(f"unknown tool {tool}")
        self.reset()
        self.tool = "select" if self.read_only else tool

    def reset(self) -> None:
        """Cancel the gesture (reverting a preview), end the pen contour and drop a pending point."""
        self.cancel()
        self.pen = None
        self.pending = None

    def cancel(self) -> None:
        """Cancel a drag or rubber band; a drag preview reverts to ``before``."""
        if self.drag is not None and self.before is not None:
            self.model.data = self.before
        self.drag = self.band = self.before = None
        self.base = set()

    def escape(self) -> bool:
        """Escape: cancel the gesture or end the pen contour; True when something ended."""
        ended = self.busy or self.pen is not None or self.pending is not None
        self.reset()
        return ended

    # --- select tool ---------------------------------------------------------------
    def press(self, sx: float, sy: float, extend: bool = False) -> None:
        """Select-tool press: drag a hit selection, select a hit point, or start a band."""
        self.cancel()
        model = self.model
        if model.data is None:
            return
        hit = hit_point(model.data, model.view, sx, sy)
        if hit is None:
            self.base = set(model.selection) if extend else set()
            model.selection = set(self.base)
            self.band = (sx, sy, sx, sy)
            return
        if extend:
            model.selection ^= {hit}
        elif hit not in model.selection:
            model.selection = {hit}
        if hit in model.selection and not self.read_only:
            self.drag = model.view.to_font(sx, sy)
            self.before = model.data

    def move(self, sx: float, sy: float) -> None:
        """Pointer moved: preview a drag (no write) or grow the rubber band."""
        model = self.model
        if self.band is not None:
            self.band = (self.band[0], self.band[1], sx, sy)
            model.selection = self.base | points_in_rect(model.data, model.view, self.band)
        elif self.drag is not None and self.before is not None:
            dx, dy = self._delta(sx, sy)
            model.data = move_points(self.before, model.selection, dx, dy)

    def release(self, sx: float | None = None, sy: float | None = None) -> Edit | None:
        """End the gesture; a drag that moved returns its ``Move`` edit, else None."""
        if self.drag is None or self.before is None:
            self.cancel()
            return None
        if sx is not None and sy is not None:
            dx, dy = self._delta(sx, sy)
        else:
            dx = dy = 0.0
        before, selection = self.before, frozenset(self.model.selection)
        self.cancel()
        if dx == 0 and dy == 0:
            return None
        return Edit("Move", move_points(before, set(selection), dx, dy), selection)

    def _delta(self, sx: float, sy: float) -> tuple[float, float]:
        x, y = self.model.view.to_font(sx, sy)
        return float(round(x - self.drag[0])), float(round(y - self.drag[1]))

    # --- key actions ---------------------------------------------------------------
    def nudge(self, dx: float, dy: float) -> Edit | None:
        """Shift the selection by ``(dx, dy)`` font units; None without a selection."""
        data = self.model.data
        if self.read_only or data is None or not self.model.selection or (dx == 0 and dy == 0) or self.busy:
            return None
        selection = frozenset(self.model.selection)
        return Edit("Nudge", move_points(data, set(selection), dx, dy), selection)

    def delete(self) -> Edit | None:
        """Delete the selected points; None without a selection. The selection clears."""
        data = self.model.data
        if self.read_only or data is None or not self.model.selection or self.busy:
            return None
        self.pen = self.pending = None
        return Edit("Delete", delete_points(data, self.model.selection), frozenset())

    def toggle(self) -> Edit | None:
        """Toggle selected on/off-curve roles; refuse invalid open endpoints."""
        data = self.model.data
        if self.read_only or data is None or not self.model.selection or self.busy:
            return None
        self.pen = self.pending = None
        return Edit("Toggle on/off-curve", toggle_points(data, self.model.selection), frozenset(self.model.selection))

    # --- pen tool ------------------------------------------------------------------
    def pen_click(self, sx: float, sy: float) -> Edit | None:
        """Pen click: start, extend or close an open contour.

        The first click of a contour only sets ``pending`` and returns None, so
        nothing is written; the second click (away from the pending point)
        returns the two-point open contour. Later clicks add a point, or close
        the contour on its first point.
        """
        model = self.model
        data = model.data
        if data is None:
            return None
        if self.read_only:
            return None
        contours = list(data.contours)
        if self.pen is not None and not (0 <= self.pen < len(contours) and not contours[self.pen].closed):
            self.pen = None
        if self.pen is not None:
            points = contours[self.pen].points
            first = points[0]
            fx, fy = model.view.to_screen(first.x, first.y)
            if (fx - sx) ** 2 + (fy - sy) ** 2 <= HIT_TOLERANCE**2:
                if len(points) < 2:
                    return None
                closed = (replace(first, type="line"), *points[1:])
                contours[self.pen] = Contour(closed)
                index, self.pen = self.pen, None
                return Edit("Close contour", replace(data, contours=tuple(contours)), frozenset({(index, 0)}))
        x, y = model.view.to_font(sx, sy)
        point = Point(float(round(x)), float(round(y)), "line")
        if self.pen is None:
            start = self.pending
            if start is None:
                self.pending = replace(point, type="move")
                return None
            if (start.x, start.y) == (point.x, point.y):
                return None  # a second click on the pending point adds nothing
            contours.append(Contour((start, point)))
            self.pen, self.pending = len(contours) - 1, None
        else:
            contours[self.pen] = Contour((*contours[self.pen].points, point))
        key = (self.pen, len(contours[self.pen].points) - 1)
        return Edit("Add point", replace(data, contours=tuple(contours)), frozenset({key}))

    # --- write ---------------------------------------------------------------------
    def commit(self, edit: Edit) -> str:
        """Write ``edit`` once; return the fingerprint of the drawn state for ``Echo``.

        On failure the glyph shown before the edit is restored (pen state ends)
        and the error propagates for the window's diagnostic line.
        """
        if self.read_only:
            raise ValueError("This glyph preview is read-only")
        model = self.model
        before = model.data
        try:
            write_contours(model.font, model.name, model.layer, edit.data.contours, f"{self.label_prefix}: {edit.action} {model.name}")
        except Exception:
            model.data = before
            self.pen = self.pending = None
            raise
        model.data = edit.data
        model.selection = set(edit.selection)
        return fingerprint(edit.data, model.metrics)
