# this_file: tests/test_wp07_alternate_preview.py
# SPDX-License-Identifier: Apache-2.0
"""Behaviour checks for the Alternate Preview App module with fake Qt and fonts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS

import pytest

SOURCE = (
    Path(__file__).parents[1]
    / "src/fontlabapp/features/identity_tools/feature_explorer/alternate_preview.py"
)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)


class Widget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.width = 600
        self.font = "font"
        self.palette = NS(color=lambda role: "black")
        self.minimum = None
        self.updated = 0

    def setMinimumHeight(self, value):
        self.minimum = value

    def update(self):
        self.updated += 1

    def viewport(self):
        return NS(width=600)

    def setWidgetResizable(self, value):
        pass

    def setWidget(self, widget):
        self.widget = widget

    def addLayout(self, layout):
        pass

    def addWidget(self, *args):
        pass

    def addItem(self, text):
        self.items = getattr(self, "items", []) + [text]


class Edit(Widget):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self.textChanged = Signal()

    @property
    def text(self):
        return self._text

    def setText(self, text):
        self._text = text


class Combo(Widget):
    def __init__(self):
        super().__init__()
        self.currentIndex = 0
        self.currentIndexChanged = Signal()


class Painter:
    def __init__(self, widget):
        self.calls = []
        self.fail = False

    def setRenderHint(self, hint):
        if self.fail:
            raise RuntimeError("paint broke")

    def setPen(self, color):
        self.calls.append("pen")

    def drawText(self, *args):
        self.calls.append(args[-1])

    def fillPath(self, path, brush):
        self.calls.append("fill")

    def end(self):
        self.calls.append("end")


class Path:
    def __init__(self):
        self.added = []

    def setFillRule(self, rule):
        pass

    def addPath(self, part):
        self.added.append(part)

    def isEmpty(self):
        return not self.added


class FakePart:
    def __init__(self, empty=False):
        self.empty = empty

    def isEmpty(self):
        return self.empty


class Dialog:
    def __init__(self, parent=None, *, title="", subtitle="", key=""):
        self.package = None
        self.apply_button = NS(setText=lambda t: None, setEnabled=lambda v: None)
        self.status = NS(text="", setText=lambda t: setattr(self.status, "text", t))
        self.names = []
        self.setup_done = False

    def prepare(self):
        return Widget()

    def ensure_font(self):
        pass

    def ensure_preview(self):
        pass

    def _connect(self, signal, slot):
        signal.connect(slot)


@pytest.fixture
def module(monkeypatch):
    shown = []
    qt_gui = NS(
        QWidget=Widget,
        QPainter=Painter,
        QPainterPath=Path,
        QColor=lambda c: c,
        QBrush=lambda c: c,
        QPalette=NS(WindowText=1),
        QTransform=lambda *a: NS(map=lambda path: path),
        QFontMetrics=lambda font: NS(elidedText=lambda name, mode, width: name),
        QGridLayout=Widget,
        QLineEdit=Edit,
        QComboBox=Combo,
        QLabel=Widget,
        QScrollArea=Widget,
    )
    qt = NS(QtCore=NS(Qt=NS(WindingFill=1, ElideRight=2)), QtGui=qt_gui)
    state = NS(glyph=None, font_glyphs=[])
    native = NS(
        CurrentGlyph=lambda: state.glyph,
        CurrentFont=lambda: NS(glyphs=[NS(name=n) for n in state.font_glyphs]),
    )
    app = ModuleType("fontlabapp")
    app._native = lambda name: native if name == "fontlab" else qt
    scripting = ModuleType("fontlabapp.core.scripting")
    scripting.features_dialog_type = lambda: Dialog
    scripting.show_script_dialog = lambda cls, key: shown.append((cls, key)) or "shown"
    for name, mod in (
        ("fontlabapp", app),
        ("fontlabapp.core", ModuleType("fontlabapp.core")),
        ("fontlabapp.core.scripting", scripting),
    ):
        monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("alt_preview_under_test", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.state, mod.shown = state, shown
    return mod


def test_run_when_base_exists_then_base_first_and_prefix_exact(module):
    names = ["a-cy", "a.ss01", "a", "a.alt", "b.alt"]
    assert module.run(names, "a") == ["a", "a.alt", "a.ss01"]
    assert module.run(names, "z") == []


def test_layer_path_when_parts_mixed_then_only_non_empty_added(module):
    keep, empty = FakePart(), FakePart(empty=True)
    shape = NS(
        closedPath=keep,
        openedPath=None,
        transform=NS(map=lambda part: part),
    )
    shape2 = NS(closedPath=empty, openedPath=keep, transform=NS(map=lambda p: p))
    path = module.layer_path(NS(shapes=[shape, shape2]))
    assert path.added == [keep, keep]


def _layer(w=100, h=200):
    return NS(
        isNull=False,
        shapes=[],
        boundingBox=NS(x=lambda: 0, y=lambda: 0, width=lambda: w, height=lambda: h),
    )


def _owner(names, masters, package):
    return NS(
        preview_names=names,
        chosen_masters=masters,
        ensure_font=lambda: None,
        package=package,
        status=NS(text="", setText=lambda t: None),
    )


def test_draw_proof_when_no_names_then_prompt_only(module):
    proof = module.Proof(_owner([], [], None))
    painter = Painter(None)
    proof.draw_proof(painter)
    assert any("Enter an existing base" in str(c) for c in painter.calls)


def test_draw_proof_when_layers_present_or_missing_then_fill_and_label(module):
    layer = _layer()
    box_fn = lambda: None  # noqa: E731
    glyphs = {
        "a": NS(findLayer=lambda m: layer),
        "a.alt": NS(findLayer=lambda m: None),
        "a.null": NS(findLayer=lambda m: NS(isNull=True)),
    }
    package = NS(findName=lambda name: glyphs.get(name))
    proof = module.Proof(_owner(["a", "a.alt", "a.null", "ghost"], ["Regular"], package))
    painter = Painter(None)
    proof.draw_proof(painter)
    assert painter.calls.count("fill") == 1
    assert painter.calls.count("Missing layer") == 3
    assert "Regular" in painter.calls and "ghost" in painter.calls


def test_paint_event_when_painter_raises_then_error_reported_and_painter_ended(
    module, monkeypatch
):
    owner = _owner(["a"], ["R"], NS(findName=lambda n: None))
    seen = []
    owner.status = NS(setText=seen.append)
    proof = module.Proof(owner)
    _f = lambda w: _failing()
    _f.Antialiasing = 1
    monkeypatch.setattr(module.QtGui, "QPainter", _f)
    proof.paintEvent(None)
    assert seen == ["Proof error: paint broke"]
    assert proof._error == "paint broke"


def _failing():
    painter = Painter(None)
    painter.fail = True
    _failing.last = painter
    return painter


def test_paint_event_when_ok_then_draws_and_ends(module):
    proof = module.Proof(_owner([], [], None))
    painters = []
    _mk = lambda w: painters.append(Painter(w)) or painters[-1]
    _mk.Antialiasing = 1
    module.QtGui.QPainter = _mk
    proof.paintEvent(None)
    assert painters[0].calls[-1] == "end"


def test_dialog_when_package_present_then_setup_refresh_reload_apply(module):
    module.state.glyph = NS(name="a.alt")
    module.state.font_glyphs = ["b", "a", "a.alt"]
    dialog = module.Dialog()
    dialog.package = NS(master="Bold", masters=["Bold", "Light"])
    dialog.names = ["a", "a.alt", "b"]
    dialog.setup()
    assert dialog.base.text == "a"
    assert dialog.scope.items == ["Current master (Bold)", "All masters (2)"]
    dialog.refresh()
    assert dialog.preview_names == ["a", "a.alt"]
    assert dialog.chosen_masters == ["Bold"]
    assert dialog.status.text.startswith("2 glyphs × 1 masters")
    assert dialog.proof_text() == "/a/a.alt"
    dialog.scope.currentIndex = 1
    dialog.reload()
    assert dialog.names == ["a", "a.alt", "b"]
    assert dialog.chosen_masters == ["Bold", "Light"]
    dialog.apply()
    assert dialog.last_result == {
        "names": ["a", "a.alt"],
        "masters": ["Bold", "Light"],
    }
    dialog.base.setText("   ")
    dialog.refresh()
    assert dialog.preview_names == []


def test_dialog_when_no_package_then_empty_scope_and_no_masters(module):
    dialog = module.Dialog()
    dialog.setup()
    assert dialog.scope.items == ["Current master (none)", "All masters (0)"]
    dialog.refresh()
    assert dialog.chosen_masters == []


def test_main_when_called_then_shows_dialog_under_key(module):
    assert module.main() == "shown"
    assert module.shown == [(module.Dialog, module.KEY)]
