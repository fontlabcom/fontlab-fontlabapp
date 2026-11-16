# this_file: tests/master_doubles.py
"""Owned doubles of a two-master flPackage and the fontlab module (no host).

The package keeps zone guides per master and rebuilds ps_zonesT/B the way
flpackage.cpp:12452-12523 does: bottom zones are guides with a negative
extension, an empty name becomes "T: <pos>"/"B: <pos>", a repeated name
gets ".1". Guides are ``(id, is_zone, position, extension, name, tags,
locked)``: convert keeps every non-zone guide (same id) and re-creates the
zone guides with new ids. Every native call is logged in ``package.log``.
"""

from types import SimpleNamespace as NS

from fontlabapp.metrics.zones.native_rules import is_top

METRICS = ("ascender_value", "descender_value", "xHeight_value", "capsHeight_value", "lineGap_value")


class FakeZone:
    """flZone double: flZone() and the flZone(flZone) copy constructor."""

    def __init__(self, other: "FakeZone | None" = None) -> None:
        self.position, self.width, self.name, self.tags, self.locked = 0.0, 0.0, "", "", False
        if other is not None:
            self.position, self.width, self.name = other.position, other.width, other.name
            self.tags, self.locked = other.tags, other.locked


def _unique(names: list[str], name: str) -> str:
    """Return ``name`` or ``name.N`` like _check_zone_name."""
    if name not in names:
        return name
    counter = 1
    while f"{name}.{counter}" in names:
        counter += 1
    return f"{name}.{counter}"


class FakePackage:
    """A two-master flPackage double with zones as guides, per master."""

    def __init__(self, masters: dict | None = None, current: str = "Regular") -> None:
        object.__setattr__(self, "log", [])
        object.__setattr__(self, "id", 7)
        object.__setattr__(self, "isNull", False)
        object.__setattr__(self, "_master", current)
        object.__setattr__(self, "fail", {})
        object.__setattr__(self, "next_id", 100)
        data = masters or {
            "Regular": dict(guides=[(500.0, 15.0, "x", "", False), (0.0, -15.0, "base", "t1", True)]),
            "Bold": dict(guides=[(510.0, 15.0, "x", "", False), (700.0, 12.0, "caps", "", False)]),
        }
        for index, values in enumerate(data.values()):
            for offset, field in enumerate(METRICS):
                values.setdefault(field, float(750 - 250 * offset + index))
            zones = values.pop("guides", [])
            metric = [(index * 10 + 1, False, 750.0, 0.0, "ascender", "", False), (index * 10 + 2, False, 0.0, 0.0, "baseline", "", False)]
            values["guides"] = metric + [(index * 10 + 3 + i, True, *z) for i, z in enumerate(zones)]
            values["cache"] = None
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "container", NS(checkInitHistoryState=self._init_container))
        for name in data:
            self._master = name
            self.updateZonesFromGuidelines()
        self._master = current
        self.log.clear()

    @property
    def masters(self) -> list[str]:
        return list(self.data)

    @property
    def master(self) -> str:
        return self._master

    def _hook(self, name: str) -> None:
        self.log.append(name)
        error = self.fail.get((name, self._master)) or self.fail.get(name)
        if error is not None:
            raise error

    def setMaster(self, name: str, notify: bool = True) -> None:
        self.log.append(("setMaster", name, notify))
        if name in self.data and self.fail.get(("stuck", name)) is None:
            object.__setattr__(self, "_master", name)

    def mastersContainer(self):
        self.log.append("mastersContainer")
        return self.container

    def _init_container(self, index: int) -> None:
        self._hook("init-container")
        self.log.append(("init", "container", index))

    def checkInitHistoryState(self, index: int) -> None:
        self._hook("init-package")
        self.log.append(("init", "package", index))

    def __getattr__(self, name: str):
        if name in METRICS:
            return self.data[self._master][name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in METRICS:
            self._hook(f"set-{name}")
            once = self.fail.pop(("store-once", name), None)
            stored = once if once is not None else self.fail.get(("store", name), value)
            self.data[self._master][name] = stored
            return
        object.__setattr__(self, name, value)

    @property
    def ps_zonesT(self) -> list[FakeZone]:
        return [FakeZone(z) for z in self.data[self._master]["cache"][0]]

    @property
    def ps_zonesB(self) -> list[FakeZone]:
        return [FakeZone(z) for z in self.data[self._master]["cache"][1]]

    def convertZonesToGuidelines(self, top: list, bottom: list) -> None:
        self._hook("convert")
        kept = [g for g in self.data[self._master]["guides"] if not g[1]]
        rows = [(z.position, z.width, z.name, z.tags, z.locked) for z in top]
        rows += [(z.position, -z.width, z.name, z.tags, z.locked) for z in bottom]
        for row in rows:
            object.__setattr__(self, "next_id", self.next_id + 1)
            kept.append((self.next_id, True, *row))
        self.data[self._master]["guides"] = kept

    def updateZonesFromGuidelines(self) -> None:
        self.log.append("update-zones")
        top, bottom = [], []
        for _id, is_zone, position, ext, name, tags, locked in self.data[self._master]["guides"]:
            if not is_zone:
                continue
            zone = FakeZone()
            zone.position, zone.tags, zone.locked = position, tags, locked
            upper = is_top(ext, name, position)
            zone.width = abs(ext)
            zone.name = name or f"{'T' if upper else 'B'}: {position:g}"
            target = top if upper else bottom
            zone.name = _unique([z.name for z in target], zone.name)
            target.append(zone)
        self.data[self._master]["cache"] = (top, bottom)

    def findName(self, name: str):
        boxes = self.data[self._master].get("boxes", {})
        if name not in boxes:
            return None
        return NS(findLayer=lambda master: _layer(boxes[name]))


def _layer(box):
    if box is None:
        return NS(isNull=True)
    y, height = box
    corners = [(0.0, y), (100.0, y), (100.0, y + height), (0.0, y + height)]
    nodes = [NS(x=x, y=v, isOn=lambda: True) for x, v in corners]
    identity = {f"m{i}{j}": (lambda value=float(i == j): value) for i in (1, 2, 3) for j in (1, 2, 3)}
    contour = NS(nodes=lambda: nodes, closed=True, isTT=False)
    shape = NS(contours=[contour], transform=NS(**identity))
    # No boundingBox: the cached box is stale after node moves (fl#8575) and must not be read.
    return NS(isNull=False, shapes=[shape])


def native(package: FakePackage, queue: tuple[int, ...] = ()) -> NS:
    """Return a fontlab module double that logs into ``package.log``."""

    def notify(*args):
        package.log.append(("notify", args[0], tuple(args[1]), *args[2:]))
        error = package.fail.get("notify")
        if error is not None:
            raise error

    return NS(
        flZone=FakeZone,
        flItems=lambda: NS(notifyChangesApplied=notify),
        flGlyph=NS(updatedFgGlyphs=lambda: queue),
    )


def zone_guides(package: FakePackage, master: str) -> list[tuple]:
    """Return the zone guides of ``master`` without ids."""
    return [g[2:] for g in package.data[master]["guides"] if g[1]]


def other_guides(package: FakePackage, master: str) -> list[tuple]:
    """Return the non-zone guides of ``master``, with ids."""
    return [g for g in package.data[master]["guides"] if not g[1]]
