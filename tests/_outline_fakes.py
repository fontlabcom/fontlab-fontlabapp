# this_file: tests/_outline_fakes.py
"""Native outline fakes for the Outline Doctor tests.

What: nodes, contours, shapes and layers with the structural calls the
Outline Doctor fixes use (insertNodeTo, convertToLine/Curve, removeAt,
setStartPoint, removeContour, assign, hasIntersPoints/contains/clockwise),
a package whose layers carry a name, and a fake FontGate whose
``removeOverlap`` returns a prepared outline. Every write is logged.
Why: a test can prove a scan or a plan wrote nothing, and that a fix wrote
exactly the planned layers inside one history step.
"""

from types import SimpleNamespace

from _contour_fakes import Glyph, Package, Pin

MASTERS = ("Regular", "Bold")


class T:
    """A QTransform-shaped matrix."""

    def __init__(self, dx=0.0, dy=0.0, m11=1.0, m12=0.0, m21=0.0, m22=1.0):
        self._v = (m11, m12, m21, m22, dx, dy)

    def m11(self):
        return self._v[0]

    def m12(self):
        return self._v[1]

    def m21(self):
        return self._v[2]

    def m22(self):
        return self._v[3]

    def dx(self):
        return self._v[4]

    def dy(self):
        return self._v[5]


class ONode:
    def __init__(self, x, y, on=True, *, smooth=False, selected=False, log=None):
        object.__setattr__(self, "log", log if log is not None else [])
        object.__setattr__(self, "contour", None)
        for key, value in (("x", x), ("y", y), ("on", on), ("smooth", smooth), ("selected", selected)):
            object.__setattr__(self, key, value)

    def __setattr__(self, key, value):
        self.log.append(("node", key, value))
        object.__setattr__(self, key, value)

    def isOn(self):
        return self.on

    def isOff(self):
        """Quadratic off-curve (TrueType contour)."""
        return not self.on and bool(getattr(self.contour, "isTT", False))

    def isCurve(self):
        """Cubic handle (PostScript contour)."""
        return not self.on and not getattr(self.contour, "isTT", False)

    def convertToLine(self):
        self.log.append(("line",))
        nodes = self.contour._nodes
        i = nodes.index(self)
        doomed = [nodes[(i - 1) % len(nodes)], nodes[(i - 2) % len(nodes)]]
        if any(n.on for n in doomed):
            return False
        for n in doomed:
            nodes.remove(n)
        return True

    def convertToCurve(self, smooth):
        self.log.append(("curve",))
        nodes = self.contour._nodes
        i = nodes.index(self)
        p = nodes[i - 1]
        handles = [ONode(p.x + (self.x - p.x) * k / 3, p.y + (self.y - p.y) * k / 3, False, log=self.log)
                   for k in (1, 2)]  # fmt: skip
        for h in handles:
            object.__setattr__(h, "contour", self.contour)
        nodes[i:i] = handles
        return True


class OContour:
    def __init__(self, spec, *, closed=True, tt=False, log=None, refuse=False):
        self.log = log if log is not None else []
        self._nodes = []
        for item in spec:
            x, y, on, *rest = item
            node = ONode(x, y, on, selected=bool(rest and rest[0]), log=self.log)
            object.__setattr__(node, "contour", self)
            self._nodes.append(node)
        self.closed, self.isTT, self.refuse = closed, tt, refuse
        self.inters, self.within = set(), set()
        self.clockwise = True

    def nodes(self):
        return list(self._nodes)

    @property
    def nodesCount(self):
        return len(self._nodes)

    def countNodes(self):
        return len(self._nodes)

    def removeAt(self, index):
        self.log.append(("remove", index))
        del self._nodes[index]

    def setStartPoint(self, index):
        self.log.append(("start", index))
        if self.refuse:
            return False
        self._nodes = self._nodes[index:] + self._nodes[:index]
        return True

    def insertNodeTo(self, t):
        """Cut segment ``int(t)`` (counted from the first on-curve node) at its local parameter."""
        from fontlabapp.studios.outline_doctor.fixes import split

        self.log.append(("insert", t))
        k, local = int(t), t - int(t)
        ends = [i for i, n in enumerate(self._nodes) if n.on]
        start = ends[k]
        a, b, c = (self._nodes[(start + j) % len(self._nodes)] for j in (1, 2, 3))
        cubic = ((self._nodes[start].x, self._nodes[start].y), (a.x, a.y), (b.x, b.y), (c.x, c.y))
        made = []
        for x, y, on in split(cubic, [local]):
            node = ONode(x, y, on, log=self.log)
            object.__setattr__(node, "contour", self)
            made.append(node)
        self._nodes[start + 1 : start + 3] = made

    def hasIntersPoints(self, other):
        return id(other) in self.inters or id(self) in other.inters

    def contains(self, other):
        return id(other) in self.within


class OShape:
    def __init__(self, contours=(), *, component=None, refs=1, transform=None, log=None):
        self.contours = list(contours)
        self.isComponent = component is not None
        self.shapeData = SimpleNamespace(referenceCount=refs, componentGlyph=component)
        self.transform, self.log = transform, log if log is not None else []
        self.selected, self.contentLocked = False, False

    def removeContour(self, contour):
        self.log.append(("remove contour",))
        self.contours.remove(contour)

    def changed(self):
        self.log.append(("changed",))

    def convertToFgShape(self, result):
        result.source = self

    def assign(self, result):
        self.log.append(("assign",))
        self.contours = list(result.contours)


class FgShape:
    """FontGate stand-in: ``removeOverlap`` installs ``FontGate.merged``."""

    def __init__(self, module):
        self.module, self.contours, self.source = module, [], None

    def removeOverlap(self):
        self.contours = list(self.module.merged)


class FontGate:
    def __init__(self, merged):
        self.merged = merged

    def fgShape(self):
        return FgShape(self)


class OLayer:
    isMasterLayer, isMaskLayer, isService = True, False, False

    def __init__(self, glyph, master, shapes, anchors=(), log=None, *, hinted=False, auto=False):
        object.__setattr__(self, "log", log if log is not None else [])
        for key, value in (("glyph", glyph), ("master", master), ("name", master), ("shapes", list(shapes)),
                           ("autoLayer", auto), ("hasHints", hinted), ("isLocked", False)):  # fmt: skip
            object.__setattr__(self, key, value)
        object.__setattr__(self, "anchors", [Pin(n, x, y, self.log) for n, x, y in anchors])

    def __setattr__(self, key, value):
        self.log.append(("layer", key, value))
        object.__setattr__(self, key, value)

    def removeHints(self, *args):
        self.log.append(("remove hints", self.glyph, self.master))
        object.__setattr__(self, "hasHints", False)


class OPackage(Package):
    """``add(name, build)``: ``build(log, master)`` returns shapes or (shapes, anchors)."""

    def add(self, name, build, masters=None, **kwargs):
        layers = {}
        for master in masters or self.masters:
            made = build(self.log, master)
            shapes, anchors = made if isinstance(made, tuple) else (made, ())
            layers[master] = OLayer(name, master, shapes, anchors, self.log, **kwargs)
        self.by_name[name] = Glyph(name, layers)
        return self.by_name[name]

    @property
    def by_name(self):
        return self.__dict__.setdefault("_by_name", {})

    @property
    def glyphs(self):
        return list(self.by_name.values())

    @glyphs.setter
    def glyphs(self, value):
        pass

    def findName(self, name):
        return self.by_name.get(name)

    def layer(self, name, master="Regular"):
        return self.by_name[name].findLayer(master)


def box(x0, y0, size, log, **kwargs):
    """A closed four-node square."""
    return OContour([(x0, y0, True), (x0 + size, y0, True), (x0 + size, y0 + size, True), (x0, y0 + size, True)],
                    log=log, **kwargs)  # fmt: skip


def blob(log, *, flat=False, **kwargs):
    """A closed cubic contour with one curve whose extremes lie inside it."""
    spec = [(0, 0, True), (100, 0, True), (160, 50, False), (160, 150, False), (100, 200, True), (0, 200, True)]
    if flat:
        spec[2:4] = [(100, 0, False), (100, 200, False)]
    return OContour(spec, log=log, **kwargs)
