# this_file: tests/_interp_fakes.py
"""Interpolation Doctor fakes: glyphs that list their layers in stored order.

What: ``IPackage.add`` builds ``_outline_fakes`` layers per master and an
``IGlyph`` with ``findLayer`` and a stored-order ``layers`` list, so extra
layers (mask, service, non-master) can be appended for the report scripts.
Why: Point Counter, Point Counter (Master Layers) and Why You Not Compatible
walk ``flGlyph.layers``; the shared Glyph fake has no such list.
"""

from _outline_fakes import OLayer, OPackage


class IGlyph:
    def __init__(self, name, layers, log=None):
        for key, value in (("name", name), ("isNull", False), ("_layers", layers), ("extra", []),
                           ("log", log if log is not None else [])):  # fmt: skip
            object.__setattr__(self, key, value)

    def __setattr__(self, key, value):
        """Log every glyph-level write (e.g. ``__has_history_changes``) so read-only tests see it."""
        self.log.append(("glyph set", self.name, key))
        object.__setattr__(self, key, value)

    def findLayer(self, master):
        return self._layers.get(master)

    @property
    def layers(self):
        return list(self._layers.values()) + self.extra


class IPackage(OPackage):
    """``add(name, build, auto=(masters...))``: ``build(log, master)`` returns shapes or (shapes, anchors)."""

    def add(self, name, build, masters=None, *, auto=(), hinted=False):
        layers = {}
        for master in masters or self.masters:
            made = build(self.log, master)
            shapes, anchors = made if isinstance(made, tuple) else (made, ())
            layers[master] = OLayer(name, master, shapes, anchors, self.log, hinted=hinted, auto=master in auto)
        self.by_name[name] = IGlyph(name, layers, self.log)
        return self.by_name[name]


def extra_layer(glyph, name, shapes=(), *, master=False, mask=False, service=False):
    """Append a stored layer that is not one of the font masters."""
    layer = OLayer(glyph.name, name, shapes)
    for key, value in (("isMasterLayer", master), ("isMaskLayer", mask), ("isService", service)):
        object.__setattr__(layer, key, value)
    glyph.extra.append(layer)
    return layer
