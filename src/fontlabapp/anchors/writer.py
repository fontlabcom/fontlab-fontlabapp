# this_file: src/fontlabapp/anchors/writer.py
# SPDX-License-Identifier: Apache-2.0
"""Shared plan and write kernel of the anchor writer scripts.

What: the Anchors scripts (Rename Bulk, Center Horizontally, Place From
Bounds, Snap To Metrics, Round To Grid, Delete By Name, Mirror Across Masters)
share one model. A script planner turns one layer into ``Change`` rows. Each
row can hold one ``Edit``:

- ``("set", name, (x, y))``: move the anchor; add it when it is missing;
- ``("remove", name, None)``: delete every anchor with this name;
- ``("rename", name, new)``: rename every anchor with this name.

``collect`` runs the planner on every editable layer and returns a ``Plan``.
``require_safe`` refuses the whole batch before any history exists.
``apply_work`` writes all edits as ONE native Undo step and reads every
value back.

How: ``apply_work`` builds every native pin and point first (``prepare``),
then calls ``fontlabapp.core.history.glyphs.commit`` with ``operation="geometry"``. The
commit discloses queued native updates and refuses auto layers in the edit list, glyphs
that own an auto layer and bases of auto composites (also through other
composites). Then it inits history, runs ``write``, stamps the glyphs, sends
one notification and stamps again. ``unstored`` is the read-back: a value
that FontLab did not keep raises ``RuntimeError``. A failure after history
started raises ``history.PartialWriteError`` ("... use Edit > Undo").

Why: FontLab cannot Redo an existing anchor moved to 0, 0 (FontLab issue
8527), so ``require_safe`` refuses that move. A new pin gets its
name-derived appearance now (``anchor_copy.APPEARANCE``), because FontLab
infers it only on Redo or reopen. An existing pin keeps its own style and
expressions: ``write`` edits the existing pin object in place.

This module imports only the standard library and stdlib-only App modules at
load time. PythonQt, FontLab and ``anchor_copy`` load inside the functions,
so FontLab's 5-second cold import stays fast. The panel base is in
``fontlabapp.anchors.panel.model``. Offline tests do not prove native Undo/Redo.

How to use (a script)::

    import fly.ap.anchors.panel.model as anchor_panel
    import fly.ap.anchors.writer as anchor_writer

    def planner(glyph, master, layer):
        return [anchor_writer.Change("top", "1, 2", "0, 2", ("set", "top", (0, 2)))]

    class Panel(anchor_panel.panel_type()):
        TITLE, KEY = "Example", "anchors_example"

        def planner(self):
            return planner
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native

#: One anchor edit: (operation, anchor name, value). See the module text.
Edit = tuple[str, str, Any]
#: The write list: (glyph, layer, edits) per edited layer. No auto layer.
Work = list[tuple[Any, Any, list[Edit]]]
#: A planner takes (glyph, master name, layer) and returns the layer's rows.
Planner = Callable[[Any, str, Any], list["Change"]]
#: The refusal text of an existing anchor moved to 0, 0 (FontLab issue 8527).
ORIGIN_ERROR = (
    "FontLab cannot Redo an existing anchor moved to 0, 0. "
    "Choose other values or other glyphs."
)
#: Units. A read-back value closer than this to the plan counts as stored.
EPSILON = 1e-6
#: Names shown before "…" in a refusal text.
SHOWN_NAMES = 8


@dataclass(frozen=True)
class Change:
    """One preview row of a planner.

    ``name``: the anchor (or a short label). ``old`` and ``new``: preview
    texts. ``edit``: the ``Edit`` that Apply writes; None shows the row only.
    ``problem``: a reason that blocks Apply; empty when the row is safe.
    """

    name: str
    old: str
    new: str
    edit: Edit | None = None
    problem: str = ""


@dataclass
class Plan:
    """Everything that one Apply would do, and the reasons it may not.

    ``work``: the write list. ``rows``: (label, Change) preview rows.
    ``skipped``: "glyph/master" of each auto layer that is listed, not
    edited. ``problems``: "label: reason" of each blocked row.
    """

    work: Work = field(default_factory=list)
    rows: list[tuple[str, Change]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def anchors(self) -> int:
        """Return the number of planned edits on all layers."""
        return sum(len(edits) for _, _, edits in self.work)


def half_up(value: float) -> int:
    """Round half up on every platform: 14.5 gives 15, -14.5 gives -14.

    Python ``round()`` rounds half to even, so it is not used.
    """
    return math.floor(value + 0.5)


def plural(count: int, word: str) -> str:
    """Return "1 layer" or "2 layers": add "s" when ``count`` is not 1."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def fmt(value: float) -> str:
    """Format a unit value without trailing decimals: 700.0 gives "700"."""
    return f"{value:g}"


def layer_of(glyph: Any, master: str) -> Any | None:
    """Return the existing layer of ``glyph`` in ``master``, or None.

    Never create a layer. Reuse ``fontlabapp.anchors.copy.model.layer_of``; it loads
    when this function runs.
    """
    from fontlabapp.anchors.copy.model import layer_of as existing_layer

    return existing_layer(glyph, master)


def raw_point(pin: Any) -> tuple[float, float]:
    """Return the stored position of an anchor, not rounded."""
    return float(pin.point.x()), float(pin.point.y())


def on_origin(point: Iterable[float], near: float = 0.0) -> bool:
    """True when ``point`` counts as 0, 0 for the Redo rule (FontLab issue 8527).

    FontLab cannot Redo an existing anchor moved to 0, 0: the writer omits a
    default origin point, and the reader keeps the old point. ``near`` 0
    accepts only exact zeros (``require_safe``). A caller that expects
    FontLab's rounding gives a tolerance: a value closer than ``near`` units
    to 0 also counts (Contours > Transform and Slant use 0.5).
    """
    x, y = point
    return all(value == 0 or abs(value) < near for value in (x, y))


def anchor_points(layer: Any) -> dict[str, tuple[float, float]]:
    """Return ``{name: (x, y)}`` of the layer anchors, not rounded.

    When several anchors share a name, the last one wins. Use ``duplicated``
    to find such names. ``fontlabapp.anchors.inspect.model.anchor_points`` rounds; this
    function does not.
    """
    return {pin.name: raw_point(pin) for pin in layer.anchors}


def duplicated(layer: Any, names: Iterable[str]) -> list[str]:
    """Return the sorted names in ``names`` that several layer anchors carry."""
    counts: dict[str, int] = {}
    for pin in layer.anchors:
        counts[pin.name] = counts.get(pin.name, 0) + 1
    return sorted(n for n in set(names) if counts.get(n, 0) > 1)


def refusal(names: Iterable[str]) -> list[Change]:
    """Return one blocking row per name: an edit of a repeated name is ambiguous."""
    return [
        Change(n, "", "", problem=f"several anchors named {n}; use Duplicates Finder")
        for n in names
    ]


def parse_names(text: str) -> list[str]:
    """Split a name list at commas and semicolons: "top, bottom;ogonek" gives 3 names."""
    return [n.strip() for n in text.replace(";", ",").split(",") if n.strip()]


def collect(glyphs: Iterable[Any], masters: Iterable[str], planner: Planner) -> Plan:
    """Run ``planner`` on every existing layer and return the ``Plan``.

    An auto layer with changes is listed as "N anchors · auto layer, skipped"
    and goes into ``skipped``, never into ``work``. A layer with a blocked row
    goes into ``problems`` and not into ``work``. A missing layer is ignored.
    """
    masters = list(masters)
    plan = Plan()
    for glyph in glyphs:
        for master in masters:
            layer = layer_of(glyph, master)
            changes = planner(glyph, master, layer) if layer is not None else []
            if not changes:
                continue
            label = f"{glyph.name} · {master}"
            if layer.autoLayer:
                plan.skipped.append(f"{glyph.name}/{master}")
                note = Change(plural(len(changes), "anchor"), "", "auto layer, skipped")
                plan.rows.append((label, note))
                continue
            plan.rows.extend((label, change) for change in changes)
            blocked = [c.problem for c in changes if c.problem]
            plan.problems.extend(f"{label}: {text}" for text in blocked)
            edits = [c.edit for c in changes if c.edit is not None]
            if edits and not blocked:
                plan.work.append((glyph, layer, edits))
    return plan


def shown(names: list[str]) -> str:
    """Join the first ``SHOWN_NAMES`` names with commas; add " …" for more."""
    more = " …" if len(names) > SHOWN_NAMES else ""
    return ", ".join(names[:SHOWN_NAMES]) + more


def blocked_rows(work: Work, facts: history.AutoFacts) -> list[tuple[str, Change]]:
    """Return one blocking row per edited glyph that the geometry policy refuses.

    A glyph that owns an auto layer, or is a base of one (also through other
    composites), is refused: FontLab rebuilds the auto composite and Undo does
    not restore it. ``facts`` is a fresh ``history.scan_auto_facts``.
    """
    names = [glyph.name for glyph, _, _ in work]
    found = history.refusals(facts, names, "geometry")
    return [
        (name, Change("blocked", "", "", problem=why)) for name, why in found.items()
    ]


def require_safe(work: Work, facts: history.AutoFacts) -> None:
    """Refuse the whole batch before any history exists. Raise ``ValueError``.

    1. A "set" edit of an existing anchor to 0, 0: FontLab cannot Redo it
       (FontLab issue 8527). A new anchor at 0, 0 is safe.
    2. A "set" edit of a name that several anchors of the layer carry: the
       move is ambiguous. "remove" and "rename" act on every pin with the name
       on purpose, so they pass.
    3. A glyph that owns an auto layer or is a base of one (``blocked_rows``).
    """
    for glyph, layer, edits in work:
        existing = {pin.name for pin in layer.anchors}
        moved = [name for operation, name, _ in edits if operation == "set"]
        for operation, name, value in edits:
            if operation == "set" and name in existing and on_origin(value):
                raise ValueError(ORIGIN_ERROR)
        repeated = duplicated(layer, moved)
        if repeated:
            raise ValueError(
                f"{glyph.name}: several anchors named {shown(repeated)}; "
                "use Duplicates Finder."
            )
    found = blocked_rows(work, facts)
    if found:
        reasons = [f"{name}: {change.problem}" for name, change in found]
        raise ValueError(
            f"FontLab cannot undo edits to these glyphs: {shown(reasons)}. "
            "Choose other glyphs."
        )


def prepare(layer: Any, edits: list[Edit]) -> list[tuple[str, Any, Any]]:
    """Build every native pin and point BEFORE history opens.

    Return ``[(step, pin, value)]`` with step "add", "move", "remove" or
    "rename". A new pin gets the name-derived appearance of
    ``fontlabapp.anchors.copy.model.APPEARANCE`` (lower-case name; 0 for other
    names). An existing pin is never rebuilt, so it keeps its own appearance
    and expressions.
    """
    from fontlabapp.anchors.copy.model import APPEARANCE

    qtcore, native = _native("PythonQt").QtCore, _native("fontlab")
    pins = list(layer.anchors)
    steps: list[tuple[str, Any, Any]] = []
    for operation, name, value in edits:
        same = [pin for pin in pins if pin.name == name]
        if operation == "set":
            point = qtcore.QPointF(float(value[0]), float(value[1]))
            if same:
                steps.append(("move", same[0], point))
            else:
                pin = native.flPinPoint(point)
                pin.name, pin.anchor = name, True
                pin.appearance = APPEARANCE.get(name.lower(), 0)
                steps.append(("add", None, pin))
        elif operation == "remove":
            steps.extend(("remove", pin, None) for pin in same)
        elif operation == "rename":
            steps.extend(("rename", pin, value) for pin in same)
    return steps


def write(layer: Any, steps: list[tuple[str, Any, Any]]) -> None:
    """Run the prepared steps on the layer. Touch only the planned pins.

    "add" adds the new pin; "move" sets the point of the existing pin;
    "remove" removes the pin; "rename" sets its name.
    """
    for step, pin, value in steps:
        if step == "add":
            layer.addAnchor(value)
        elif step == "move":
            pin.point = value
        elif step == "remove":
            layer.removeAnchor(pin)
        elif step == "rename":
            pin.name = value


def unstored(work: Work, before: list[dict[str, tuple[float, float]]]) -> list[str]:
    """Return "glyph/anchor" of each edit that FontLab did not keep.

    ``before`` holds each layer's ``anchor_points`` from before the write.
    For "set", check only a coordinate that the edit changed: FontLab can
    round an untouched coordinate (strong rounding preference), and that is
    not an error. For "remove", the name must be gone. For "rename", the old
    name must be gone and the new name present.
    """
    missed: list[str] = []
    for (glyph, layer, edits), old_points in zip(work, before, strict=True):
        points = anchor_points(layer)
        names = {pin.name for pin in layer.anchors}
        for operation, name, value in edits:
            if operation == "set":
                point, old = points.get(name), old_points.get(name)
                ok = point is not None and all(
                    abs(point[axis] - value[axis]) < EPSILON
                    for axis in (0, 1)
                    if old is None or abs(old[axis] - value[axis]) >= EPSILON
                )
            elif operation == "remove":
                ok = name not in names
            else:
                ok = name not in names and value in names
            if not ok:
                missed.append(f"{glyph.name}/{name}")
    return missed


def apply_work(work: Work, title: str, facts: history.AutoFacts) -> dict[str, Any]:
    """Write all edits as ONE native Undo step named ``title``.

    ``work`` holds no auto layer (``collect``); ``facts`` is a fresh
    ``history.scan_auto_facts``. Call ``require_safe`` first. The commit uses
    ``history.commit(..., operation="geometry", read_back=...)``. No rollback
    is tried: a failure after history started raises
    ``history.PartialWriteError`` with "use Edit > Undo". A value that FontLab
    did not keep raises ``history.unstored_error`` ("FontLab did not store
    ... Check those layers before you save."). Empty ``work`` returns zeros and makes no history call.

    Return ``{"anchors": native pin operations, "layers": edited layers}``. One
    removed pin counts once, also for a repeated name.
    """
    prepared = [(layer, prepare(layer, edits)) for _, layer, edits in work]
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    layers = [layer for _, layer, _ in work]
    if not layers:
        return {"pending_updates": (), "pending_note": "", "anchors": 0, "layers": 0}
    before = [anchor_points(layer) for layer in layers]

    def mutate() -> None:
        for layer, steps in prepared:
            write(layer, steps)

    def read_back() -> list[str]:
        return unstored(work, before)

    done = history.commit(
        title,
        layers,
        glyphs,
        mutate,
        operation="geometry",
        facts=facts,
        read_back=read_back,
    )
    if done.mismatches:
        raise history.unstored_error(done.mismatches, "Check Preferences > Rounding.")
    return {"pending_note": done.pending_note, "anchors": sum(len(steps) for _, steps in prepared), "layers": len(work), "pending_updates": done.pending_updates}


__all__ = [
    "EPSILON",
    "ORIGIN_ERROR",
    "SHOWN_NAMES",
    "Change",
    "Edit",
    "Plan",
    "Planner",
    "Work",
    "anchor_points",
    "apply_work",
    "blocked_rows",
    "collect",
    "duplicated",
    "fmt",
    "half_up",
    "layer_of",
    "on_origin",
    "parse_names",
    "plural",
    "prepare",
    "raw_point",
    "refusal",
    "require_safe",
    "shown",
    "unstored",
    "write",
]
