# this_file: tests/paint_safety.py
"""Recording native fakes and the paint-safety oracle shared by G003 tests."""

#: Native names the paint path must never touch (Issue 209 design §2, map §6).
FORBIDDEN = frozenset(
    {
        "getMaskLayer",
        "ensureMaskLayer",
        "findLayerCreate",
        "activeLayer",
        "interpolateInstance",
        "fgGlyph",
        "getLayerByName",
    }
)


class Spy:
    """Log every attribute read, item lookup and write on a native fake.

    Entries are ``(label, "get" | "item" | "set", name_or_key)``. Item lookups
    read the ``items`` mapping given at construction.
    """

    def __init__(self, log, label, **attrs):
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_attrs", attrs)

    def __getattr__(self, name):
        self._log.append((self._label, "get", name))
        try:
            return self._attrs[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key):
        self._log.append((self._label, "item", key))
        return self._attrs["items"][key]

    def __setattr__(self, name, value):
        self._log.append((self._label, "set", name))


def recorder(log, label, name, result):
    """A native method fake that logs ``(label, "call", name, args)``."""

    def call(*args):
        log.append((label, "call", name, args))
        return result

    return call


def assert_paint_safe(log, allowed=()):
    """Fail if the log touches a forbidden native name or writes anything.

    ``allowed`` holds exact ``(label, name, args)`` calls, such as
    ``("layer", "getMaskLayer", (False,))``. Reading that name on that label
    is then permitted; any other call of it, or any use elsewhere, fails.
    """
    allowed = set(allowed)
    readable = {(label, name) for label, name, _args in allowed}
    bad = [
        entry
        for entry in log
        if entry[2] in FORBIDDEN
        and not (entry[1] == "get" and (entry[0], entry[2]) in readable)
        and not (entry[1] == "call" and (entry[0], entry[2], entry[3]) in allowed)
    ]
    assert bad == [], f"paint-unsafe native calls: {bad}"
    writes = [entry for entry in log if entry[1] == "set"]
    assert writes == [], f"paint must never write native state: {writes}"
