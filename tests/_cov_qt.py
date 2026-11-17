# this_file: tests/_cov_qt.py
"""A small behavioural fake of ``PythonQt`` for building Fontport UI editors offscreen.

Widgets keep PythonQt-style properties (``text``, ``checked``, ``currentRow``...) as
plain attributes and emit the signals real Qt emits for programmatic changes unless
``blockSignals(True)`` is active. Only the Qt methods in ``RECORDED_METHODS`` record their
call and return None; any other unknown name raises ``AttributeError`` like PythonQt would.
"""

import importlib
import sys
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

SIGNALS = frozenset(
    {
        "clicked",
        "textChanged",
        "toggled",
        "valueChanged",
        "currentIndexChanged",
        "currentRowChanged",
        "itemSelectionChanged",
        "destroyed",
        "timeout",
        "triggered",
    }
)


# Qt methods the Fontport editors call that need no behaviour beyond being recorded.
RECORDED_METHODS = frozenset(
    {
        "addItem",
        "addLayout",
        "insertWidget",
        "setContentsMargins",
        "setSpacing",
        "setSizeConstraint",
        "setRootIsDecorated",
        "removeWidget",
        "resizeColumnToContents",
        "addRow",
        "addWidget",
        "closeSubpath",
        "drawPath",
        "end",
        "ensureVisible",
        "fillRect",
        "lineTo",
        "moveTo",
        "resize",
        "scale",
        "setAccessibleName",
        "setBrush",
        "setBuddy",
        "setColor",
        "setFillRule",
        "setFocus",
        "setFocusPolicy",
        "setFrameShape",
        "setInterval",
        "setMaxLength",
        "setMaximumHeight",
        "setMinimumSize",
        "setParent",
        "setPen",
        "setPlaceholderText",
        "setRange",
        "setRenderHint",
        "setSelectionMode",
        "setSingleShot",
        "setSuffix",
        "setToolTip",
        "setWidget",
        "setWidgetResizable",
        "setWidthF",
        "setWordWrap",
        "stop",
        "translate",
        "update",
    }
)


class Signal:
    """Connect/disconnect/emit recorder."""

    def __init__(self) -> None:
        self.slots: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        self.slots.append(callback)

    def disconnect(self, callback: Callable[..., Any]) -> None:
        self.slots.remove(callback)

    def emit(self, *args: Any) -> None:
        for slot in list(self.slots):
            slot(*args)


class _Meta(type):
    """Capitalised class attributes (Qt enums) resolve to their own name."""

    def __getattr__(cls, name: str) -> Any:
        if name[:1].isupper():
            return name
        raise AttributeError(name)


class Item:
    """A list item with PythonQt's ``text()`` method."""

    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class FakeWidget(metaclass=_Meta):
    """Any Qt widget, layout, painter or helper object."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.calls: list[tuple[str, tuple]] = []
        self.text: str = args[0] if args and isinstance(args[0], str) else ""
        self.checked = False
        self.enabled = True
        self.read_only = False
        self.blocked = False
        self.items: list[Item] = []
        self.selected: list[Item] = []
        self.currentRow = -1
        self.currentIndex = 0
        self.value = 0
        self.width = 100
        self.height = 100
        self.rect = SimpleNamespace(width=100)
        self.shown = True
        self.deleted = False
        self.plain_text = ""

    # --- signal-aware state setters -------------------------------------------------
    def _emit(self, name: str, *args: Any) -> None:
        if not self.blocked:
            getattr(self, name).emit(*args)

    def blockSignals(self, state: bool) -> bool:
        previous, self.blocked = self.blocked, bool(state)
        return previous

    def setText(self, text: str) -> None:
        changed = text != self.text
        self.text = text
        if changed:
            self._emit("textChanged", text)

    def setChecked(self, state: bool) -> None:
        changed = bool(state) != self.checked
        self.checked = bool(state)
        if changed:
            self._emit("toggled", self.checked)

    def setValue(self, value: int) -> None:
        changed = value != self.value
        self.value = value
        if changed:
            self._emit("valueChanged", value)

    def setCurrentIndex(self, index: int) -> None:
        changed = index != self.currentIndex
        self.currentIndex = index
        if changed:
            self._emit("currentIndexChanged", index)

    @property
    def currentText(self) -> str:
        if 0 <= self.currentIndex < len(self.items):
            return self.items[self.currentIndex].text()
        return ""

    def setCurrentRow(self, row: int) -> None:
        changed = row != self.currentRow
        self.currentRow = row
        self.selected = [self.items[row]] if 0 <= row < len(self.items) else []
        if changed:
            self._emit("currentRowChanged", row)

    def addItems(self, names: list[str]) -> None:
        self.items.extend(Item(str(n)) for n in names)

    def clear(self) -> None:
        self.items, self.selected, self.currentRow = [], [], -1

    def selectedItems(self) -> list[Item]:
        return list(self.selected)

    def setEnabled(self, state: bool) -> None:
        self.enabled = bool(state)

    def setReadOnly(self, state: bool) -> None:
        self.read_only = bool(state)

    def setPlainText(self, text: str) -> None:
        self.plain_text = text

    def toPlainText(self) -> str:
        return self.plain_text

    def hide(self) -> None:
        self.shown = False

    def show(self) -> None:
        self.shown = True

    def deleteLater(self) -> None:
        self.deleted = True

    def viewport(self) -> "FakeWidget":
        return self

    def viewportEvent(self, event: Any) -> bool:
        return True

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        if name in SIGNALS:
            signal = Signal()
            self.__dict__[name] = signal
            return signal
        if name not in RECORDED_METHODS:
            raise AttributeError(f"PythonQt widget has no method {name!r}")

        def method(*args: Any, **kwargs: Any) -> None:
            self.__dict__.setdefault("calls", []).append((name, args))

        return method


class FakeTimer(FakeWidget):
    """QTimer recording starts."""

    started = 0

    def start(self, *args: Any) -> None:
        self.started += 1


class FakeEvent(metaclass=_Meta):
    """A resize or other event."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def type(self) -> str:
        return self._kind


class FakeFileDialog(FakeWidget):
    """QFileDialog statics return the next queued path."""

    path: Any = ""

    @staticmethod
    def getSaveFileName(*args: Any) -> Any:
        return FakeFileDialog.path

    getOpenFileName = getSaveFileName
    getExistingDirectory = getSaveFileName


class _Namespace:
    """Module-like namespace creating a ``FakeWidget`` subclass per requested name."""

    def __init__(self, **special: Any) -> None:
        self.__dict__.update(special)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(name, (FakeWidget,), {})
        self.__dict__[name] = cls
        return cls


def make_pythonqt() -> SimpleNamespace:
    """Build the fake ``PythonQt`` module."""
    qtgui = _Namespace(QFileDialog=FakeFileDialog)
    qtcore = _Namespace(QTimer=FakeTimer, QEvent=FakeEvent, Qt=FakeWidget)
    return SimpleNamespace(QtGui=qtgui, QtCore=qtcore)


UI_MODULES = (
    "fontlabapp.fontui.batch",
    "fontlabapp.fontui.batch_worker",
    "fontlabapp.fontui.fontinfo",
    "fontlabapp.fontui.groups",
    "fontlabapp.fontui.groups_view",
    "fontlabapp.fontui.kerning",
    "fontlabapp.fontui.kerning_view",
    "fontlabapp.fontui.sequence",
    "fontlabapp.fontui.transform",
    "fontlabapp.fontui.transform_view",
    "fontlabapp.fontui.lifecycle",
    "fontlabapp.fontui.sequence_canvas",
    "fontlabapp.fontui.native",
    "fontlabapp.fontui.model",
)


def _forget_on_parent(name: str, monkeypatch: Any = None) -> None:
    """Remove the submodule attribute a package keeps for ``name`` (stale-module guard).

    With ``monkeypatch`` the original attribute is restored at teardown; without it the
    attribute is simply deleted.
    """
    parent_name, _, child = name.rpartition(".")
    parent = sys.modules.get(parent_name)
    if parent is None or not hasattr(parent, child):
        return
    if monkeypatch is not None:
        monkeypatch.delattr(parent, child, raising=False)
    else:
        delattr(parent, child)


def install(monkeypatch: Any) -> SimpleNamespace:
    """Install the fake PythonQt and return a handle that imports UI modules fresh."""
    importlib.import_module("fontlab_fontport.groups")
    importlib.import_module("fontTools.pens.qtPen")
    for name in UI_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
        _forget_on_parent(name, monkeypatch)
    fake = make_pythonqt()
    monkeypatch.setitem(sys.modules, "PythonQt", fake)
    monkeypatch.delitem(sys.modules, "fontlab", raising=False)
    return SimpleNamespace(qt=fake, load=importlib.import_module)


def release() -> None:
    """Drop UI modules imported against the fake."""
    for name in UI_MODULES:
        sys.modules.pop(name, None)
        _forget_on_parent(name)


class Applying(dict):
    """A dict model with the ``apply(values, undo_name=...)`` hook editors need."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.undo_names: list[str] = []

    def apply(self, values: dict, *, undo_name: str) -> None:
        self.undo_names.append(undo_name)
        self.clear()
        self.update(values)


class FontModel:
    """A borrowed FontParts-like font over a ufoLib2 font with applyable groups/kerning."""

    def __init__(self, font: Any, editable: bool = True) -> None:
        self.ufo = font
        self.info = font.info
        cls = Applying if editable else dict
        self.groups = cls(font.groups)
        self.kerning = cls(font.kerning)

    def keys(self) -> list[str]:
        return list(self.ufo.keys())

    def __getitem__(self, name: str) -> Any:
        return self.ufo[name]

    def __contains__(self, name: object) -> bool:
        return name in self.ufo


def ufo_font() -> Any:
    """A tiny ufoLib2 font: A and V (kerned), each with one triangle contour."""
    from ufoLib2 import Font

    font = Font()
    font.info.unitsPerEm = 1000
    font.info.ascender, font.info.descender = 800, -200
    for name, code in (("A", 65), ("V", 86)):
        glyph = font.newGlyph(name)
        glyph.width = 600
        glyph.unicodes = [code]
        pen = glyph.getPen()
        pen.moveTo((0, 0))
        pen.lineTo((300, 700))
        pen.lineTo((600, 0))
        pen.closePath()
    font.groups["public.kern1.A"] = ["A"]
    font.groups["public.kern2.V"] = ["V"]
    font.kerning[("public.kern1.A", "public.kern2.V")] = -80
    return font
