# this_file: tests/test_issue122_G18.py
"""Exercise independent tools with strict host fakes; no native acceptance claim."""

import ast
import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace as NS
from typing import Any

import pytest
from _wp07_routes import behavior_path
from _wp05_scriptmix_shim import app_names_used, check_real_app_names

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    "Kerning/Delete Kerning Pair From All Masters",
    "Kerning/Kern To Max",
    "Features/Generate Random Alternates Feature",
    "Masters/Reorder Shapes",
    "Masters/Show All Layers",
    "Kerning/Steal Kerning From Next Pair",
]


def load(index: int) -> ModuleType:
    """Load a menu without running its entry point."""
    spec = importlib.util.spec_from_file_location(
        f"g18_{index}", behavior_path(ROOT / "Scripts" / (PATHS[index] + ".py"))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub(monkeypatch: Any, name: str, **members: Any) -> ModuleType:
    """Install a module double at the actual Fly boundary."""
    module = ModuleType(name)
    module.__dict__.update(members)
    monkeypatch.setitem(sys.modules, name, module)
    canonical = name.replace("fly.ap.", "fontlabapp.", 1) if name.startswith("fly.ap.") else {
        "fly.fp.feature_blocks": "fontlabapp.fontui.feature_blocks",
        "fly.qt": "PythonQt",
    }.get(name)
    if canonical:
        monkeypatch.setitem(sys.modules, canonical, module)
        if "." in canonical:
            parent_name, _, child_name = canonical.rpartition(".")
            parent_module = importlib.import_module(parent_name)
            monkeypatch.setattr(parent_module, child_name, module, raising=False)
    if "." in name:
        parent, _, child = name.rpartition(".")
        if parent not in sys.modules:
            stub(monkeypatch, parent, __path__=[])
        monkeypatch.setitem(sys.modules[parent].__dict__, child, module)
    return module


@pytest.fixture
def host(monkeypatch: Any) -> Any:
    """A current font and two adjacent master-layer occurrences."""
    stub(monkeypatch, "fly", __path__=[])
    stub(monkeypatch, "fly.ap", __path__=[])
    package = NS(id=7, master="Regular", masters=["Regular", "Bold"])
    rows = []
    for index, (name, width) in enumerate((("A", 601), ("V", 501))):
        layer = NS(name="Regular", isMasterLayer=True, advanceWidth=width)
        rows.append(
            NS(
                package=package,
                glyph_name=name,
                layer=layer,
                layer_name="Regular",
                block_id=11,
                index=index,
            )
        )
    selection = NS(context=(7, "Regular", "editor"), occurrences=tuple(rows))
    stub(monkeypatch, "fly.ap.masters.layers.selection", capture=lambda deadline: selection)
    stub(monkeypatch, "fly.ap.core.scripting", current_package=lambda: package)
    groups = {"AGroup": (("A",), "KernLeft"), "VGroup": (("V",), "KernRight")}
    pair = (("AGroup", "groupMode"), ("VGroup", "groupMode"))
    snapshot = NS(
        groups={m: groups for m in package.masters},
        pairs={m: {pair: -80} for m in package.masters},
    )
    writes = []
    stub(
        monkeypatch,
        "fly.ap.kerning.batch",
        snapshot_kerning=lambda p, typed: snapshot,
        write_kerning=lambda *a, **k: writes.append((a, k)) or True,
    )
    return NS(
        package=package,
        rows=rows,
        selection=selection,
        snapshot=snapshot,
        writes=writes,
    )














def test_feature_generator_deterministic_complete_and_compiles() -> None:
    from io import StringIO

    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.feaLib.parser import Parser
    from fontTools.ttLib import TTFont

    tool = load(2)
    names = ["a", "a.ss01", "b", "b.ss01", "period"]
    options = ("a a.ss01\nb b.ss01", names, names, "calt", 20, 3, 4, 5, 19)
    text = tool.generate(*options)
    assert text == tool.generate(*options)
    assert text.count("    sub ") == 80
    assert text.count("lookup G18") == 0, "No batch labels in public code"
    Parser(StringIO(text), glyphNames=names).parse()
    font = TTFont()
    font.setGlyphOrder([".notdef", *names])
    addOpenTypeFeaturesFromString(font, text)
    assert "GSUB" in font, "Generated contextual rules must compile to GSUB"


@pytest.mark.parametrize("text", ["", "a", "a missing", "a a", "a a.ss01\na b"])
def test_feature_invalid_alternates_refuse(text: str) -> None:
    with pytest.raises(ValueError):
        load(2).generate(text, ["a", "a.ss01", "b"], ["a"], "calt", 2, 3, 1, 1, 0)


@pytest.mark.parametrize("tag", ["", "longtag", "a{xx", "éabc"])
def test_feature_invalid_tag_refuses(tag: str) -> None:
    with pytest.raises(ValueError):
        load(2).generate("a a.ss01", ["a", "a.ss01"], ["a"], tag, 2, 3, 1, 1, 0)


def shape(ident: int, count: int, x: float, y: float, base: str = "") -> Any:
    """Shape carrier; no native clone or detach API exists on purpose."""
    return NS(
        id=ident,
        isComponent=bool(base),
        base=base,
        contours=[NS(nodesCount=count)],
        boundingBox=NS(x=lambda: x, y=lambda: y),
    )










@pytest.fixture
def reorder_host(host: Any, monkeypatch: Any, real_app: Any) -> Any:
    """Real App history over owned layer/glyph/notification fakes."""
    notifications = []
    native = NS(
        flGlyph=NS(updatedFgGlyphs=list),
        flItems=lambda: NS(notifyChangesApplied=lambda *a: notifications.append(a)),
    )
    qt = NS(QtCore=NS(QDateTime=NS(currentDateTimeUtc=lambda: "STAMP")))
    modules = real_app(
        qt=qt,
        fontlab=native,
        scripting={"current_package": lambda: host.package},
        modules=("history", "edit_guards"),
    )
    facts = modules["history"].auto_facts([])
    monkeypatch.setattr(modules["history"], "scan_auto_facts", lambda p: facts)
    stub(monkeypatch, "fly.ap.components.writer", base_of=lambda s: s.base)
    shapes = [shape(2, 8, 0, 0), shape(1, 4, 0, 0)]
    layer = NS(
        name="Regular",
        shapes=shapes,
        isMaskLayer=False,
        isService=False,
        autoLayer=False,
        isLocked=False,
        checkInitHistoryState=lambda n: None,
        changed=lambda: None,
    )

    def reorder(ids: list[int]) -> None:
        layer.shapes = sorted(layer.shapes, key=lambda s: ids.index(s.id))

    layer.reorderShapes = reorder
    glyph = NS(
        id=19,
        name="A",
        layers=[layer],
        lastModified="OLD",
        checkInitHistoryState=lambda n: None,
    )
    host.rows[0].glyph = glyph
    host.selection.occurrences = (host.rows[0],)
    return NS(host=host, layer=layer, glyph=glyph, calls=notifications, facts=facts)










@pytest.mark.parametrize("count", [0, -1, 1.5])
def test_feature_invalid_counts_refuse(count: Any) -> None:
    with pytest.raises(ValueError):
        load(2).generate("a a.ss01", ["a", "a.ss01"], ["a"], "calt", count, 3, 1, 1, 0)


@pytest.mark.parametrize("separator", ["\x00", "\u00a0", "\u2028", "\u2029"])
def test_feature_lossy_text_refuses(separator: str) -> None:
    with pytest.raises(ValueError):
        load(2).generate(
            "a" + separator + "a.ss01", ["a", "a.ss01"], ["a"], "calt", 2, 3, 1, 1, 0
        )


def test_feature_category_inheritance_and_unknown_refusal() -> None:
    tool = load(2)
    rows = (
        ("a", "U+0061", ""),
        ("a.ss01", "", ""),
        ("period", "U+002E", ""),
        ("unencoded", "", ""),
    )
    assert tool.category_members(rows, "Letter") == ["a", "a.ss01"]
    assert tool.category_members(rows, "All") == [r[0] for r in rows]
    with pytest.raises(ValueError):
        tool.category_members(rows, "Unknown")


def test_feature_panel_preview_invalidation_and_copy(
    host: Any, monkeypatch: Any
) -> None:
    """Use strict widget fakes to exercise source controls and Copy lifecycle."""
    forbidden = {"render", "size", "layout", "update", "font", "move", "statusBar"}

    class Widget:
        def __init__(self, text: str = "") -> None:
            self.text = text
            self.textChanged = object()
            self.clicked = object()

        def __setattr__(self, name: str, value: Any) -> None:
            if name in forbidden:
                raise AttributeError(name)
            object.__setattr__(self, name, value)

        def setText(self, text: str) -> None:
            self.text = text

        def setPlainText(self, text: str) -> None:
            self.text = text

        def toPlainText(self) -> str:
            return self.text

        def setEnabled(self, enabled: bool) -> None:
            self.enabled = enabled

        def setChecked(self, checked: bool) -> None:
            self.checked = checked

        def isChecked(self) -> bool:
            return getattr(self, "checked", False)

        def setReadOnly(self, enabled: bool) -> None:
            pass

        def setPlaceholderText(self, text: str) -> None:
            pass

        def addWidget(self, *args: Any) -> None:
            pass

        def addLayout(self, *args: Any) -> None:
            pass

    class PanelBase(Widget):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__()
            self.apply_button = Widget()
            self.status = Widget()
            self.package = host.package
            self.setup()

        def prepare(self) -> Any:
            return Widget()

        def _connect(self, signal: Any, slot: Any) -> None:
            pass

        def ensure_font(self) -> None:
            pass

        def ensure_preview(self) -> None:
            if not self._preview_valid:
                raise ValueError("No preview")

        def copy_text(self, text: str) -> None:
            self.copied_text = text

    stub(
        monkeypatch,
        "fly.qt",
        QtGui=NS(
            QLineEdit=Widget,
            QPlainTextEdit=Widget,
            QGridLayout=Widget,
            QHBoxLayout=Widget,
            QVBoxLayout=Widget,
            QCheckBox=Widget,
            QLabel=Widget,
            QPushButton=Widget,
        ),
    )
    sys.modules["fly.ap.core.scripting"].features_dialog_type = lambda: PanelBase
    rows = (("a", "U+0061", ""), ("a.ss01", "", ""))
    table = NS(rows=rows)
    stub(monkeypatch, "fly.ap.glyphs.catalog.model", capture=lambda: table)
    feature_writes = []
    feature_state = {"blocks": {"prefix": "", "features": []}}

    def write_blocks(*args: Any, **kwargs: Any) -> dict:
        feature_writes.append((args, kwargs))
        changed = int(feature_state["blocks"] != args[2])
        feature_state["blocks"] = args[2]
        return {"changed": changed}

    stub(
        monkeypatch,
        "fly.fp.feature_blocks",
        read_feature_blocks=lambda p: feature_state["blocks"],
        write_feature_blocks=write_blocks,
    )
    panel = load(2).panel_type()()
    panel.source_edit.text = "a a.ss01"
    panel.option_edits["Classes"].text = "2"
    panel.refresh()
    assert panel.apply_button.enabled
    panel.copy_preview()
    assert panel.copied_text == panel.preview_code
    assert panel.proof_text() == "/a/a.ss01"
    assert panel.apply_button.text == "Write feature"
    panel.apply()
    assert feature_writes[0][0][2]["features"] == [("calt", panel.preview_code)]
    old = "feature calt {\n# Keep this code until consent.\n} calt;\n"
    feature_state["blocks"] = {"prefix": "", "features": [("calt", old)]}
    panel.refresh()
    assert panel.existing_edit.text == old
    assert panel.output_edit.text == panel.preview_code
    assert not panel.replace_check.isChecked()
    assert "3 lines" in panel.status.text
    panel.apply()
    assert len(feature_writes) == 1, (
        "A differing existing feature needs explicit consent"
    )
    assert "already exists" in panel.status.text
    assert panel._preview_valid and panel.copy_button.enabled
    panel.replace_check.setChecked(True)
    panel.preview_changes()
    assert panel.replace_check.isChecked(), "An identical accepted proposal retains explicit consent"
    panel.apply()
    assert len(feature_writes) == 2
    assert not panel.replace_check.isChecked(), "Consent must reset after writing"
    assert panel.existing_edit.text == panel.preview_code
    panel.replace_check.setChecked(True)
    panel.option_edits["Feature"].text = "salt"
    panel.preview_changes()
    assert not panel.replace_check.isChecked(), "Changing the tag must reset consent"
    panel.replace_check.setChecked(True)
    feature_state["blocks"] = {"prefix": "# Source changed", "features": []}
    panel.refresh()
    assert not panel.replace_check.isChecked(), "Changing source must reset consent"
    panel.option_edits["Feature"].text = "calt"
    panel.option_edits["Lines"].text = "not a number"
    with pytest.raises(ValueError, match="must be whole numbers"):
        panel.refresh()
    assert not panel.copy_button.enabled
    panel.option_edits["Lines"].text = "20"
    panel.refresh()
    panel.invalidate_preview()
    assert not panel.apply_button.enabled
    with pytest.raises(ValueError):
        panel.copy_preview()
    panel.refresh()
    table.rows = rows + (("b", "U+0062", ""),)
    with pytest.raises(ValueError, match="catalogue changed"):
        panel.copy_preview()




def test_feature_entry_contains_panel_failure(host: Any, capsys: Any) -> None:
    def fail(*args: Any) -> None:
        raise TimeoutError("panel deadline")

    sys.modules["fly.ap.core.scripting"].show_script_dialog = fail
    tool = load(2)
    tool.panel_type = lambda: object
    assert tool.main() is None
    assert "panel deadline" in capsys.readouterr().out












@pytest.mark.parametrize("has_target", [False, True])
def test_feature_writer_replaces_only_target_with_exact_references(
    host: Any, monkeypatch: Any, has_target: bool
) -> None:
    tool = load(2)
    before = {
        "prefix": "# keep prefix",
        "features": [("liga", "KEEP")] + ([("calt", "OLD")] if has_target else []),
    }
    code = tool.generate("a a.ss01", ["a", "a.ss01"], ["a"], "calt", 1, 1, 1, 1, 3)
    writes = []
    stub(
        monkeypatch,
        "fly.fp.feature_blocks",
        read_feature_blocks=lambda p: before,
        write_feature_blocks=lambda *a, **k: writes.append((a, k)) or {"changed": 1},
    )
    tool.write_feature(host.package, before, "calt", code, replace=has_target)
    args, kwargs = writes[0]
    assert args == (
        host.package,
        before,
        {"prefix": "# keep prefix", "features": [("liga", "KEEP"), ("calt", code)]},
    )
    assert kwargs == {"references": ["a", "a.ss01"], "undo_name": tool.TITLE}
    assert before["features"] == [("liga", "KEEP")] + (
        [("calt", "OLD")] if has_target else []
    )


def test_feature_writer_refuses_stale_source(host: Any, monkeypatch: Any) -> None:
    writes = []
    stub(
        monkeypatch,
        "fly.fp.feature_blocks",
        read_feature_blocks=lambda p: {"prefix": "changed", "features": []},
        write_feature_blocks=lambda *a, **k: writes.append(a),
    )
    with pytest.raises(ValueError, match="source changed"):
        load(2).write_feature(
            host.package,
            {"prefix": "", "features": []},
            "calt",
            "feature calt {} calt;",
        )
    assert writes == []


def test_feature_writer_refuses_replacement_without_consent(
    host: Any, monkeypatch: Any
) -> None:
    before = {"prefix": "", "features": [("calt", "OLD")]}
    writes = []
    stub(
        monkeypatch,
        "fly.fp.feature_blocks",
        read_feature_blocks=lambda p: before,
        write_feature_blocks=lambda *a, **k: writes.append(a),
    )
    with pytest.raises(
        ValueError, match="Feature calt already exists; tick Replace existing feature"
    ):
        load(2).write_feature(host.package, before, "calt", "NEW")
    assert writes == []


@pytest.mark.parametrize("identical", [False, True])
def test_feature_append_and_identical_need_no_consent(
    host: Any, monkeypatch: Any, identical: bool
) -> None:
    code = "feature calt {\n} calt;\n"
    before = {"prefix": "", "features": [("calt", code)] if identical else []}
    writes = []
    stub(
        monkeypatch,
        "fly.fp.feature_blocks",
        read_feature_blocks=lambda p: before,
        write_feature_blocks=lambda *a, **k: (
            writes.append(a) or {"changed": int(not identical)}
        ),
    )
    result = load(2).write_feature(host.package, before, "calt", code)
    assert result["changed"] == int(not identical)
    assert len(writes) == 1






@pytest.fixture
def four_slots(host: Any, monkeypatch: Any) -> Any:
    """Four same-master slots with rectangular decomposed outline polygons."""
    names = ["A", "V", "V", "A"]
    for index in range(4):
        if index >= len(host.rows):
            host.rows.append(NS(**vars(host.rows[0])))
        row = host.rows[index]
        row.index, row.glyph_name = index, names[index]
        row.layer = NS(
            name="Regular",
            isMasterLayer=True,
            advanceWidth=500,
            edges=(50, 450) if index < 2 else (75, 425),
        )
    host.selection.occurrences = tuple(host.rows)
    host.package.kerning = lambda master: NS(get=lambda pair: -25)
    sys.modules["fly.ap.core.scripting"].kerning_pair_value = lambda kern, left, right: (
        kern.get((left, right))
    )
    for row in host.rows:
        row.layer.shapes = [NS(contours=[NS(isTT=False, closed=True)])]
    stub(
        monkeypatch,
        "fly.ap.masters.inspect.model",
        layer_contours=lambda layer: [
            [
                (layer.edges[0], 0, True),
                (layer.edges[1], 0, True),
                (layer.edges[1], 500, True),
                (layer.edges[0], 500, True),
            ]
        ],
        polygon=lambda points: [(x, y) for x, y, _ in points],
    )
    return host





























from _wp05_scriptmix_shim import app_sources, canonical_app_bindings, real_app  # noqa: E402,F401,I001
