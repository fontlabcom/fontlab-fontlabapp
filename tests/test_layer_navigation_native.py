# this_file: tests/test_layer_navigation_native.py
from copy import deepcopy
from types import SimpleNamespace as NS
from typing import ClassVar

import fontlabapp.masters.layers.navigation.native as adapter
import pytest
from fontlabapp.masters.layers.navigation.symbols import freeze, tokens


class Symbol:
    DataCode: ClassVar[dict] = {"UserAreaBegin": 100}

    def __init__(self, original=None, **kw):
        self.__dict__.update(
            {
                "id": 11,
                "pid": 22,
                "unicode": 0x1F600,
                "name": "A",
                "layerName": "",
                "glyphIndex": 0,
                "ligatureIndex": 0,
                "cr": False,
                "space": False,
                "attrs": {150: "private"},
            }
        )
        if original is not None:
            self.__dict__.update(deepcopy(original.__dict__))
        self.__dict__.update(kw)

    def containsData(self, code):
        return code in self.attrs

    def data(self, code):
        return self.attrs[code]


class Symbols:
    def __init__(self, items=()):
        self.items = list(items)

    def symbols(self):
        return self.items

    def append(self, value):
        raise TypeError("Error creating object of type fgSymbolList")


def native(monkeypatch):
    layers = [
        NS(
            id=1,
            name="Regular",
            isService=False,
            isMaskLayer=False,
            shapes=[NS(id=101, active=True)],
        ),
        NS(
            id=2,
            name="Sketch",
            isService=False,
            isMaskLayer=False,
            shapes=[NS(id=102, active=False)],
        ),
    ]
    glyph = NS(id=9, activeLayer=layers[0], layers=layers)
    package = NS(id=22, isValid=True, masters=["Regular"], master="Regular")
    symbols = [
        Symbol(glyphIndex=0),
        Symbol(name="unencoded", unicode=0xFFFFFFFF, glyphIndex=1),
    ]
    active = NS(id=10, isActive=True, isNullGlyph=False, symbol=symbols[0], glyph=glyph)
    matrix = NS(
        **{
            f"m{r}{c}": lambda r=r, c=c: int(r == c)
            for r in range(1, 4)
            for c in range(1, 4)
        }
    )
    canvas = NS(
        id=33,
        viewPoint=NS(x=lambda: 2, y=lambda: 3),
        viewTransform=NS(transform=matrix),
    )
    block = NS(
        id=44,
        package=package,
        editMode=1,
        formatMode=0,
        getActiveGlyph=lambda: active,
        symbolList=lambda: Symbols(symbols),
        getSelectedCharacters=lambda: Symbols(symbols),
    )
    workspace = NS(getActiveCanvas=lambda: canvas, getActiveTextBlock=lambda: block)
    calls = []

    def write(content, offset, mode):
        calls.append((content, offset, mode))
        index = next(
            i
            for i, symbol in enumerate(symbols)
            if symbol.glyphIndex == active.symbol.glyphIndex and not symbol.cr
        )
        symbols[index] = Symbol(content.items[0])
        active.symbol = symbols[index]
        glyph.activeLayer = next(
            layer for layer in layers if layer.name == content.items[0].layerName
        )
        glyph.activeLayer.shapes[0].active = True
        canvas.viewPoint = NS(x=lambda: 99, y=lambda: 100)

    module = NS(
        CurrentFont=lambda: package,
        flWorkspace=NS(instance=lambda: workspace),
        MainWindow=lambda: NS(doRequestSubContent=write),
        fgSymbol=Symbol,
        fgSymbolList=Symbols,
        EditMode={"emEditOutline": 1, "emEditMetrics": 2},
        flTransform=lambda value: NS(transform=value),
    )
    monkeypatch.setattr(adapter, "import_module", lambda name: module)
    return NS(
        module=module,
        workspace=workspace,
        block=block,
        active=active,
        glyph=glyph,
        package=package,
        symbols=symbols,
        canvas=canvas,
        calls=calls,
    )


def test_native_copy_route_preserves_private_data_and_context(monkeypatch):
    state = native(monkeypatch)
    backend = adapter.Backend()
    before = backend.capture()
    backend.replace(before, "2")
    backend.verify(before, "2")
    assert state.symbols[0].attrs[150] == "private"
    assert state.symbols[1].name == "unencoded"
    assert state.glyph.activeLayer.id == 1
    assert not state.glyph.layers[1].shapes[0].active
    assert (state.canvas.viewPoint.x(), state.canvas.viewPoint.y()) == (2, 3)
    assert len(state.calls) == 1 and state.calls[0][1:] == (0, 0)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: setattr(s.workspace, "getActiveTextBlock", lambda: None),
        lambda s: setattr(s.package, "isValid", False),
        lambda s: setattr(s.block, "editMode", 3),
        lambda s: setattr(s.block, "getActiveGlyph", lambda: None),
        lambda s: setattr(s.active, "isActive", False),
        lambda s: setattr(s.active, "isNullGlyph", True),
        lambda s: setattr(s.active.symbol, "ligatureIndex", 1),
        lambda s: setattr(s.active.symbol, "glyphIndex", -1),
        lambda s: s.symbols.append(Symbol(s.symbols[0])),
        lambda s: setattr(s.active, "symbol", Symbol(s.symbols[0], name="different")),
        lambda s: setattr(s.package, "masters", ["Regular", "Bold"]),
        lambda s: setattr(s.glyph.layers[1], "name", "Regular"),
        lambda s: setattr(s.glyph.layers[1], "name", ""),
        lambda s: setattr(s.active.symbol, "layerName", "missing"),
    ],
)
def test_capture_refuses_unsupported_before_write(monkeypatch, mutation):
    state = native(monkeypatch)
    mutation(state)
    with pytest.raises(ValueError):
        adapter.Backend().capture()
    assert not state.calls


def test_stale_final_check(monkeypatch):
    state = native(monkeypatch)
    backend = adapter.Backend()
    before = backend.capture()
    state.symbols[1].layerName = "changed"
    with pytest.raises(ValueError, match="changed"):
        backend.replace(before, "2")
    assert not state.calls


def test_postcondition_refuses_other_occurrence_change(monkeypatch):
    state = native(monkeypatch)
    backend = adapter.Backend()
    before = backend.capture()
    backend.replace(before, "2")
    state.symbols[1].name = "changed"
    with pytest.raises(RuntimeError):
        backend.verify(before, "2")


def test_invalid_slot(monkeypatch):
    state = native(monkeypatch)
    state.module.MainWindow = lambda: NS()
    with pytest.raises(TypeError):
        adapter.Backend()


def test_invalid_data_profile(monkeypatch):
    state = native(monkeypatch)
    state.module.fgSymbol = NS(DataCode={"UserAreaBegin": 200})
    with pytest.raises(ValueError):
        adapter.Backend()


def test_symbol_reserved_values_and_freeze():
    symbol = Symbol(attrs={0: 3, 5: ["a", {"b": 2}]})
    assert tokens([symbol], 100)[0][-1] == (
        (0, freeze(3)),
        (5, freeze(["a", {"b": 2}])),
    )
    with pytest.raises(ValueError):
        freeze(object())
    assert freeze(None) == ("None",)


def test_restoration_attempts_all_fields():
    class Broken:
        def __setattr__(self, key, value):
            raise RuntimeError("broken")

    good = NS()
    with pytest.raises(RuntimeError, match="restoration failed"):
        adapter._restore([(Broken(), "x", 1), (good, "x", 2)])
    assert good.x == 2


def test_failed_write_restores_context(monkeypatch):
    state = native(monkeypatch)
    backend = adapter.Backend()
    before = backend.capture()
    original = backend.window.doRequestSubContent

    def fail(*args):
        original(*args)
        raise RuntimeError("write failure")

    backend.window.doRequestSubContent = fail
    with pytest.raises(RuntimeError, match="write failure"):
        backend.replace(before, "2")
    assert adapter._context(state.canvas, state.glyph) == before.context


def test_no_selected_characters(monkeypatch):
    state = native(monkeypatch)
    state.block.getSelectedCharacters = lambda: None
    assert adapter.Backend().capture().selected == ()


def test_named_multimaster_family_uses_native_source_order(monkeypatch):
    state = native(monkeypatch)
    state.package.masters = ["Regular", "Bold"]
    state.glyph.layers[1].name = "Regular.Sketch"
    state.glyph.layers.insert(
        1, NS(id=3, name="Bold", isService=False, isMaskLayer=False, shapes=[])
    )
    backend = adapter.Backend()
    before = backend.capture()
    assert before.layers == (("1", "Regular"), ("2", "Regular.Sketch"))
    backend.replace(before, "2")
    backend.verify(before, "2")


@pytest.mark.parametrize("masters", [[], ["Regular", "Regular"]])
def test_master_domain_refuses(monkeypatch, masters):
    state = native(monkeypatch)
    state.package.masters = masters
    with pytest.raises(ValueError):
        adapter.Backend().capture()


def test_ambiguous_selection_refuses(monkeypatch):
    state = native(monkeypatch)
    state.block.getSelectedCharacters = lambda: Symbols(
        [state.symbols[0], state.symbols[0]]
    )
    with pytest.raises(ValueError, match="selected occurrence"):
        adapter.Backend().capture()


def test_missing_root_refuses(monkeypatch):
    state = native(monkeypatch)
    state.glyph.layers[0].name = "Regular.Backup"
    with pytest.raises(ValueError, match="master layer is absent"):
        adapter.Backend().capture()


def test_default_public_backend_uses_native_adapter(monkeypatch):
    from fontlabapp.masters.layers.navigation.model import next_layer, previous_layer

    state = native(monkeypatch)
    assert next_layer().status == "changed"
    assert previous_layer().status == "changed"
    assert state.symbols[0].layerName == "Regular"


def test_ineligible_duplicate_name_refuses(monkeypatch):
    state = native(monkeypatch)
    state.glyph.layers.append(
        NS(id=99, name="Sketch", isService=True, isMaskLayer=True, shapes=[])
    )
    with pytest.raises(ValueError, match="collides"):
        adapter.Backend().capture()


def test_repeated_unencoded_unicode_and_separators_keep_exact_occurrences(monkeypatch):
    state = native(monkeypatch)
    state.symbols[:] = [
        Symbol(name="", unicode=10, cr=True, glyphIndex=-1),
        Symbol(name="A", unicode=0x1F600, glyphIndex=0),
        Symbol(name="A", unicode=0x1F600, glyphIndex=1),
        Symbol(name="unencoded", unicode=0xFFFFFFFF, glyphIndex=2),
        Symbol(name="", unicode=10, cr=True, glyphIndex=-1),
    ]
    state.active.symbol = state.symbols[2]
    backend = adapter.Backend()
    before = backend.capture()
    assert before.index == 2
    backend.replace(before, "2")
    backend.verify(before, "2")
    after = backend.capture()
    assert after.symbols[:2] == before.symbols[:2]
    assert after.symbols[3:] == before.symbols[3:]
    backend.replace(after, "1")
    backend.verify(after, "1")
    assert backend.capture().layer == before.layer
    assert all(symbol.attrs == {150: "private"} for symbol in state.symbols)


def test_current_master_drift_refuses(monkeypatch):
    state = native(monkeypatch)
    backend = adapter.Backend()
    before = backend.capture()
    state.package.master = "Bold"
    with pytest.raises(ValueError, match="changed"):
        backend.replace(before, "2")
    assert not state.calls


@pytest.mark.parametrize(
    "left,right",
    [
        (True, 1),
        (1, 1.0),
        (False, 0.0),
        ([], ()),
        ([True], [1]),
        ({"x": True}, {"x": 1}),
        (0.0, -0.0),
    ],
)
def test_freeze_preserves_exact_primitive_and_container_types(left, right):
    assert freeze(left) != freeze(right), "Exact source fences must retain value types"


def test_reserved_type_drift_refuses_before_write(monkeypatch):
    state = native(monkeypatch)
    state.symbols[1].attrs = {3: True}
    backend = adapter.Backend()
    before = backend.capture()
    state.symbols[1].attrs[3] = 1
    with pytest.raises(ValueError, match="changed"):
        backend.replace(before, "2")
    assert not state.calls


def test_postwrite_shape_getter_failure_restores_other_context(monkeypatch):
    state = native(monkeypatch)

    class Shape:
        id = 101
        broken = False
        value = True

        @property
        def active(self):
            if self.broken:
                raise RuntimeError("postwrite getter failure")
            return self.value

        @active.setter
        def active(self, value):
            self.value = value

    shape = Shape()
    state.glyph.layers[0].shapes[0] = shape
    backend = adapter.Backend()
    before = backend.capture()
    original = backend.window.doRequestSubContent

    def write(*args):
        original(*args)
        shape.broken = True

    backend.window.doRequestSubContent = write
    with pytest.raises(RuntimeError, match="getter failure"):
        backend.replace(before, "2")
    assert state.glyph.activeLayer.id == 1
    assert (state.canvas.viewPoint.x(), state.canvas.viewPoint.y()) == (2, 3)


def test_final_prewrite_source_drift_is_refused(monkeypatch):
    from fontlabapp.masters.layers.navigation import model as layer_navigation

    state = native(monkeypatch)
    backend = adapter.Backend()
    original = backend.capture
    captures = 0

    def capture():
        nonlocal captures
        captures += 1
        if captures == 3:
            state.package.master = "Bold"
        return original()

    backend.capture = capture
    monkeypatch.setattr(layer_navigation, "_backend", lambda: backend)
    assert layer_navigation.next_layer().status == "refused"
    assert not state.calls


def test_reserved_type_change_is_detected_after_write(monkeypatch):
    state = native(monkeypatch)
    state.symbols[1].attrs = {3: True}
    backend = adapter.Backend()
    before = backend.capture()
    backend.replace(before, "2")
    state.symbols[1].attrs[3] = 1
    with pytest.raises(RuntimeError, match="postcondition"):
        backend.verify(before, "2")


@pytest.mark.parametrize("fault", ["format_mode", "writer_getter", "invalid_writer"])
def test_writer_preparation_failure_refuses_without_writes_or_restoration(
    monkeypatch, fault
):
    import fontlabapp.masters.layers.navigation.model as nav

    state = native(monkeypatch)
    original = state.block

    class Block:
        def __getattr__(self, name):
            return getattr(original, name)

        @property
        def formatMode(self):
            raise RuntimeError("format mode unavailable")

    class Window:
        @property
        def doRequestSubContent(self):
            raise RuntimeError("writer lookup unavailable")

    if fault == "format_mode":
        state.workspace.getActiveTextBlock = Block
    backend = adapter.Backend()
    if fault == "writer_getter":
        backend.window = Window()
    if fault == "invalid_writer":
        backend.window = NS(doRequestSubContent=None)
    restored = []
    monkeypatch.setattr(adapter, "_restore", restored.append)
    monkeypatch.setattr(nav, "_backend", lambda: backend)
    assert nav.next_layer().status == "refused"
    assert not state.calls, "Preparation failure must not invoke the writer"
    assert not restored, "Preparation failure must not enter native restoration"
