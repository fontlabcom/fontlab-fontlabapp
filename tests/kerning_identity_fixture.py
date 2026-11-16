# this_file: tests/kerning_identity_fixture.py
"""Owned explicit native pair and history model; no @notation encoding."""
from copy import deepcopy
from types import SimpleNamespace as NS

import fontlabapp.kerning.batch as batch
from fontlabapp.core import scripting

G, C = "glyphMode", "groupMode"


def owned_font(monkeypatch, reverse=False):
    """Model typed native keys directly; never encode modes into @ strings."""

    class Kern:
        def __init__(self):
            rows = [
                ((("@L", G), ("V", G)), 101),
                ((("L", C), ("V", G)), 100),
                ((("A", G), ("@R", G)), -251),
                ((("A", G), ("R", C)), -250),
                ((("L", C), ("R", C)), 0),
            ]
            self.values = dict(reversed(rows) if reverse else rows)
            self.groups = {
                "L": (["@L", "A"], "KernLeft"),
                "R": (["@R", "V"], "KernRight"),
            }
            self.fail = False

        def items(self):
            return [
                (NS(left=NS(id=a, mode=am), right=NS(id=b, mode=bm)), v)
                for ((a, am), (b, bm)), v in self.values.items()
            ]

        def set(self, key, value):
            if self.fail:
                raise RuntimeError("owned setter failure")
            if value:
                self.values[key] = value

        def remove(self, key):
            self.values.pop(key, None)

        def scale(self, value):
            self.values = {key: old * value for key, old in self.values.items()}

    kerns = {"Regular": Kern(), "#Bold": Kern()}
    history = []
    font = NS(
        id=7,
        isNull=False,
        masters=list(kerns),
        master="#Bold",
        upm=1000,
        kerning=kerns.__getitem__,
        findName=lambda n: NS(isNull=False) if n in {"@L", "A", "@R", "V"} else None,
        checkInitHistoryState=lambda _: None,
        mastersContainer=lambda: "masters",
        kerningContainer=lambda: "kerning",
    )

    def notify(name, objects):
        assert objects == [font, "masters", "kerning"]
        history.append(deepcopy({m: k.values for m, k in kerns.items()}))

    native = NS(
        flWorkspace=NS(instance=lambda: NS(currentPackage=font)),
        flItems=NS(notifyChangesApplied=notify),
    )
    monkeypatch.setattr(scripting, "_native", lambda _: native)
    monkeypatch.setattr(batch, "_native", lambda _: native)
    return font, kerns, history


