# this_file: tests/_contour_fakes.py
"""Native FontLab fakes for the Transform Studio and Align & Nudge tests.

What: layers, shapes, contours, nodes, pins, glyphs, a package with masters and
per-master italic angles, and a fake ``AppShell`` whose ``history`` records the
label and the explicit layers, runs the mutation and the read-back.
Why: the studios read native objects only through ``transform_studio.native``;
these fakes expose exactly the attributes it reads and log every write, so a
test can prove a read-only path wrote nothing.
"""

from types import SimpleNamespace


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class NNode:
    def __init__(
        self, x, y, on=True, smooth=False, selected=False, log=None, rounding=False
    ):
        object.__setattr__(self, "log", log if log is not None else [])
        object.__setattr__(self, "rounding", rounding)
        for key, value in (
            ("x", x),
            ("y", y),
            ("on", on),
            ("smooth", smooth),
            ("selected", selected),
        ):
            object.__setattr__(self, key, value)

    def __setattr__(self, key, value):
        self.log.append(("node", key, value))
        object.__setattr__(
            self, key, round(value) if self.rounding and key in ("x", "y") else value
        )

    def isOn(self):
        return self.on


class NContour:
    def __init__(self, nodes, closed=True, tt=False, log=None):
        self._nodes, self.closed, self.isTT, self.transform, self.log = (
            list(nodes),
            closed,
            tt,
            None,
            log,
        )

    def nodes(self):
        return list(self._nodes)

    def removeAt(self, index):
        self.log.append(("remove", index))
        del self._nodes[index]


class NShape:
    def __init__(self, contours=(), *, component=False, locked=False, refs=1, selected=False, box=None,
                 transform=None, log=None):  # fmt: skip
        self.contours, self.isComponent, self.contentLocked = (
            list(contours),
            component,
            locked,
        )
        self.shapeData, self.includesList, self.selected = (
            SimpleNamespace(referenceCount=refs),
            [],
            selected,
        )
        self.boundingBox = None if box is None else Box(*box)
        self.transform, self.log = transform, log

    def applyTransform(self):
        t = self.transform
        m = (t.m11(), t.m12(), t.m21(), t.m22(), t.dx(), t.dy())
        for contour in self.contours:
            for n in contour._nodes:
                x, y = n.x, n.y
                n.x, n.y = m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]
        self.log.append(("bake",))
        self.transform = None

    def changed(self):
        self.log.append(("changed",))


class Box:
    def __init__(self, x, y, w, h):
        self._v = (x, y, w, h)

    def x(self):
        return self._v[0]

    def y(self):
        return self._v[1]

    def width(self):
        return self._v[2]

    def height(self):
        return self._v[3]


class Pin:
    def __init__(self, name, x, y, log):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "point", Point(x, y))
        object.__setattr__(self, "log", log)

    def __setattr__(self, key, value):
        self.log.append(("pin", self.name, value.x(), value.y()))
        object.__setattr__(self, key, Point(value.x(), value.y()))


class NLayer:
    def __init__(self, glyph, master, shapes, anchors=(), advance=500, log=None, *, hinted=False, auto=False,
                 locked=False):  # fmt: skip
        object.__setattr__(self, "log", log)
        for key, value in (("glyph", glyph), ("master", master), ("shapes", list(shapes)), ("autoLayer", auto),
                           ("hasHints", hinted), ("isLocked", locked), ("advanceWidth", advance)):  # fmt: skip
            object.__setattr__(self, key, value)
        object.__setattr__(self, "anchors", [Pin(n, x, y, log) for n, x, y in anchors])

    def __setattr__(self, key, value):
        self.log.append(("layer", key, value))
        object.__setattr__(self, key, value)

    def removeHints(self, *args):
        self.log.append(("remove hints", self.glyph, self.master))
        object.__setattr__(self, "hasHints", False)


def square(log, x0=0, y0=0, size=100, selected=(), rounding=False):
    """A closed four-node polygon with the listed indices selected."""
    points = ((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size))
    nodes = [
        NNode(x, y, selected=i in selected, log=log, rounding=rounding)
        for i, (x, y) in enumerate(points)
    ]
    return NContour(nodes, log=log)


def curve(log, selected=(0,)):
    """A closed cubic contour: on (0,0), off, off, on (100,100), off, off."""
    spec = (
        (0, 0, True),
        (40, 0, False),
        (100, 60, False),
        (100, 100, True),
        (60, 100, False),
        (0, 40, False),
    )
    nodes = [
        NNode(x, y, on, selected=i in selected, log=log)
        for i, (x, y, on) in enumerate(spec)
    ]
    return NContour(nodes, log=log)


class Glyph:
    def __init__(self, name, layers):
        self.name, self.isNull, self._layers = name, False, layers

    def findLayer(self, master):
        return self._layers.get(master)


class Package:
    def __init__(self, masters=("Regular", "Bold"), current="Regular", angles=None):
        self.log, self.masters, self.master, self.glyphs = (
            [],
            list(masters),
            current,
            {},
        )
        self.angles = angles or {m: 0.0 for m in masters}

    @property
    def italicAngle_value(self):
        return self.angles[self.master]

    def setMaster(self, name):
        self.master = name

    def add(self, name, build, masters=None, **kwargs):
        """``build(log)`` returns the shapes (and optionally anchors) of each master layer."""
        layers = {}
        for master in masters or self.masters:
            made = build(self.log)
            shapes, anchors = made if isinstance(made, tuple) else (made, ())
            layers[master] = NLayer(
                name, master, shapes, anchors, log=self.log, **kwargs
            )
        self.glyphs[name] = Glyph(name, layers)
        return self.glyphs[name]

    def findName(self, name):
        return self.glyphs.get(name)

    def layer(self, name, master="Regular"):
        return self.glyphs[name].findLayer(master)

    def writes(self):
        return [entry for entry in self.log if entry[0] != "remove hints"]


class Shell:
    """Fake AppShell: ``history`` records (label, glyph names, (glyph, master) layers)."""

    def __init__(self, pkg):
        self.pkg, self.statuses, self.calls, self.allowed, self.refuse = (
            pkg,
            [],
            [],
            [],
            False,
        )
        self.status = SimpleNamespace(
            text=lambda: self.statuses[-1] if self.statuses else ""
        )

    def package(self):
        return self.pkg

    def set_status(self, text):
        self.statuses.append(text)

    def history(
        self, label, glyphs, mutate, *, layers, read_back=None, allow_bases=False
    ):
        self.allowed.append(allow_bases)
        self.calls.append(
            (
                label,
                [g.name for g in glyphs],
                [(layer.glyph, layer.master) for layer in layers],
            )
        )
        if self.refuse:
            self.set_status("Refused.")
            return None
        mutate()
        self.set_status(f"{label}.")
        return SimpleNamespace(
            pending_note="", mismatches=tuple(read_back() if read_back else ())
        )


class Metrics:
    def __init__(self, package, master):
        self.xHeight = 480 if master == "Regular" else 500


def hint_counts(layer):
    return (1, 1) if layer.hasHints else (0, 0)
