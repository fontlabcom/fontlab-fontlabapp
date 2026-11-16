# this_file: tests/test_demo_scripts_objects.py
"""Offline runs of the seven Scripts/Objects demos (FontLab 9.1 object JSON).

Each demo runs through runpy as ``__main__``. ``PythonQt`` and ``fontlab`` are
stubbed: on a FontLab 9.0 stand-in (no object JSON API) every demo must show
the "needs FontLab 9.1" message and open no dialog; with no font open each one
stops with one message. The read-only tour and the file export also run on a
fake 9.1 producer. Offline results are not native FontLab acceptance.
"""

import json
from types import SimpleNamespace

import pytest
from _demo_support import qt_namespace, run_script, script_path

from fontlabapp.objects import json_data

TITLES = [
    "Object JSON Demo",
    "Copy Selection As JSON Demo",
    "Paste JSON Glyphs Demo",
    "Paste JSON Shapes Into Layer Demo",
    "Export Glyphs To JSON File Demo",
    "Import Glyphs From JSON File Demo",
    "Edit JSON Before Paste Demo",
]
ENVELOPE = {"dataType": json_data.DATA_TYPE, "upm": 1000, "packageId": 3}


class QBA:
    def __init__(self, raw=b""):
        self.raw = bytes(raw)

    def data(self):
        return self.raw


class Producer:
    """Fake 9.1 flModelProducer: export one glyph per object, decode only QBA."""

    def __init__(self):
        self.decoded = 0

    def getClipboardDataJson(self, package_id, upm, objects):  # noqa: N802 - native name
        items = [
            {"glyph": {"name": getattr(o, "name", "x"), "layers": []}} for o in objects
        ]
        payload = (
            {"objects": items}
            if len(items) > 1
            else ({"glyph": items[0]["glyph"]} if items else {})
        )
        return QBA(json.dumps({**ENVELOPE, **payload}).encode())

    def getObjectsFromJsonData(self, data):  # noqa: N802 - native name
        assert type(data) is QBA, "decode must receive a QByteArray"
        self.decoded += 1
        envelope = json_data.Envelope.parse(data.raw)
        return [object() for _ in envelope.items]


class Package:
    def __init__(self, names=("o",)):
        self.isNull, self.id, self.upm, self.fgId = False, 3, 1000, 77
        self.glyphs = {
            n: SimpleNamespace(name=n, activeLayer=lambda: None) for n in names
        }

    def findName(self, name):  # noqa: N802
        return self.glyphs.get(name)

    def addGlyph(self, *_):  # noqa: N802
        raise AssertionError("addGlyph must never be called")


def install_host(monkeypatch, producer, package=None, current=None):
    """Stub PythonQt and fontlab; return the stubbed QtGui."""
    qt = qt_namespace()
    qt.QtCore.QByteArray = QBA
    stub = SimpleNamespace(
        MainWindow=lambda: "main-window",
        flModelProducer=producer,
        flWorkspace=SimpleNamespace(
            instance=lambda: SimpleNamespace(currentPackage=package)
        ),
        CurrentGlyph=lambda: current,
        CurrentFont=lambda: None,
    )
    from _demo_support import stub_module

    stub_module(monkeypatch, "PythonQt", QtGui=qt.QtGui, QtCore=qt.QtCore)
    stub_module(monkeypatch, "fontlab", **vars(stub))
    return qt.QtGui


def texts(gui) -> list[str]:
    """Main text of every message box the demo showed."""
    box = gui.QMessageBox.return_value
    return [c.args[0] for c in box.setInformativeText.call_args_list]


@pytest.mark.parametrize("title", TITLES)
def test_objects_demo_when_fontlab_90_then_needs_91_message_and_no_dialog(
    monkeypatch, title
) -> None:
    gui = install_host(monkeypatch, SimpleNamespace(), package=Package())
    run_script(script_path("Objects", title))
    assert texts(gui) == [json_data.NEEDS_91]
    assert (
        not gui.QFileDialog.getOpenFileName.called
        and not gui.QFileDialog.getSaveFileName.called
    )


@pytest.mark.parametrize("title", TITLES)
def test_objects_demo_when_no_font_then_one_message_and_nothing_changes(
    monkeypatch, title
) -> None:
    producer = Producer()
    gui = install_host(monkeypatch, producer, package=None)
    run_script(script_path("Objects", title))
    (text,) = texts(gui)
    assert text.startswith("Open a"), text
    assert producer.decoded == 0


@pytest.mark.parametrize("title", TITLES)
def test_objects_demo_when_imported_by_name_then_nothing_runs(
    monkeypatch, title
) -> None:
    gui = install_host(monkeypatch, Producer(), package=Package())
    run_script(script_path("Objects", title), run_name="demo")
    assert gui.QMessageBox.call_count == 0


def test_object_json_demo_when_glyph_selected_then_reports_round_trip(
    monkeypatch,
) -> None:
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "names_selected_names", lambda: ["o"])
    producer = Producer()
    gui = install_host(monkeypatch, producer, package=Package())
    run_script(script_path("Objects", "Object JSON Demo"))
    assert texts(gui) == ["Object JSON tour. Nothing was changed."]
    details = gui.QMessageBox.return_value.setDetailedText.call_args[0][0]
    assert "Selected glyphs:" in details and "Read back by FontLab: yes" in details
    assert producer.decoded == 1


def test_export_demo_when_path_chosen_then_file_holds_object_json(
    monkeypatch, tmp_path
) -> None:
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "names_selected_names", lambda: ["o"])
    gui = install_host(monkeypatch, Producer(), package=Package())
    target = tmp_path / "glyphs.json"
    gui.QFileDialog.getSaveFileName.return_value = str(target)
    run_script(script_path("Objects", "Export Glyphs To JSON File Demo"))
    assert json_data.Envelope.parse(target.read_bytes()).glyph_names() == ("o",)
    assert texts(gui) == ["Saved 1 glyphs to glyphs.json."]


PASTERS = [
    ("Paste JSON Glyphs Demo", "paste_glyphs"),
    ("Import Glyphs From JSON File Demo", "paste_glyphs"),
    ("Edit JSON Before Paste Demo", "paste_glyphs"),
    ("Paste JSON Shapes Into Layer Demo", "paste_shapes"),
]


@pytest.mark.parametrize(("title", "function"), PASTERS)
def test_paste_demo_when_partial_write_then_partial_message_with_undo_hint(
    monkeypatch, tmp_path, title, function
) -> None:
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.core.scripting as scripting

    raw = json.dumps({**ENVELOPE, "glyph": {"name": "o", "layers": []}}).encode()
    source = tmp_path / "in.json"
    source.write_bytes(raw)
    error = history.PartialWriteError(
        "Paste", [RuntimeError("new glyphs that exist now: o.1")]
    )

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(json_data, function, fail)
    monkeypatch.setattr(json_data, "read_clipboard", lambda *a, **k: raw)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: "facts")
    monkeypatch.setattr(scripting, "names_selected_names", lambda: ["o"])
    layer = SimpleNamespace(name="Regular")
    current = SimpleNamespace(name="o", activeLayer=lambda: layer)
    gui = install_host(monkeypatch, Producer(), package=Package(), current=current)
    gui.QFileDialog.getOpenFileName.return_value = str(source)
    run_script(script_path("Objects", title))
    assert texts(gui) == [json_data.PARTIAL_TEXT]
    details = gui.QMessageBox.return_value.setDetailedText.call_args[0][0]
    assert "o.1" in details and history.UNDO_HINT in details


def sel_names(monkeypatch, names):
    import fontlabapp.core.scripting as scripting

    monkeypatch.setattr(scripting, "names_selected_names", lambda: list(names))


def details_of(gui) -> str:
    return gui.QMessageBox.return_value.setDetailedText.call_args[0][0]


def test_copy_demo_when_nothing_selected_then_asks_for_selection(monkeypatch) -> None:
    sel_names(monkeypatch, [])
    gui = install_host(monkeypatch, Producer(), package=Package(), current=None)
    run_script(script_path("Objects", "Copy Selection As JSON Demo"))
    assert texts(gui) == ["Select glyphs or shapes first. Nothing was copied."]


def test_copy_demo_when_glyphs_selected_then_clipboard_written(monkeypatch) -> None:
    sel_names(monkeypatch, ["o", "missing"])
    copied = []
    monkeypatch.setattr(
        json_data, "copy_to_clipboard", lambda raw, **_: copied.append(raw)
    )
    gui = install_host(monkeypatch, Producer(), package=Package(), current=None)
    run_script(script_path("Objects", "Copy Selection As JSON Demo"))
    (text,) = texts(gui)
    assert text.startswith("Copied 1 selected glyphs as object JSON (")
    assert json_data.Envelope.parse(copied[0]).glyph_names() == ("o",)
    assert "o" in details_of(gui)


def test_copy_demo_when_shapes_selected_then_copies_only_selected_shapes(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, ["o"])
    copied = []
    monkeypatch.setattr(
        json_data, "copy_to_clipboard", lambda raw, **_: copied.append(raw)
    )
    picked = SimpleNamespace(name="s1", selected=True)
    layer = SimpleNamespace(name="Bold", shapes=[picked, SimpleNamespace(name="s2")])
    current = SimpleNamespace(name="o", activeLayer=lambda: layer)
    gui = install_host(monkeypatch, Producer(), package=Package(), current=current)
    run_script(script_path("Objects", "Copy Selection As JSON Demo"))
    (text,) = texts(gui)
    assert text.startswith("Copied 1 selected shapes of o/Bold as object JSON")
    assert len(copied) == 1


def test_copy_demo_when_glyph_has_no_selected_shape_then_falls_back_to_glyphs(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, ["o"])
    monkeypatch.setattr(json_data, "copy_to_clipboard", lambda raw, **_: None)
    layer = SimpleNamespace(name="Bold", shapes=[SimpleNamespace(selected=False)])
    current = SimpleNamespace(name="o", activeLayer=lambda: layer)
    gui = install_host(monkeypatch, Producer(), package=Package(), current=current)
    run_script(script_path("Objects", "Copy Selection As JSON Demo"))
    assert texts(gui)[0].startswith("Copied 1 selected glyphs")


def test_object_json_demo_when_nothing_selected_then_asks_for_glyph(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, [])
    gui = install_host(monkeypatch, Producer(), package=Package(), current=None)
    run_script(script_path("Objects", "Object JSON Demo"))
    assert texts(gui) == ["Select glyphs or open a glyph first. Nothing was changed."]


class Shrinking(Producer):
    """Decodes one object fewer than exported: read-back mismatch."""

    def getObjectsFromJsonData(self, data):  # noqa: N802 - native name
        return super().getObjectsFromJsonData(data)[1:] or []


def test_object_json_demo_when_glyph_open_then_layer_shape_contour_toured(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, [])
    contour = SimpleNamespace(name="c")
    shape = SimpleNamespace(name="s", contours=[contour])
    layer = SimpleNamespace(name="Regular", shapes=[shape])
    current = SimpleNamespace(name="o", activeLayer=lambda: layer)
    gui = install_host(monkeypatch, Shrinking(), package=Package(), current=current)
    run_script(script_path("Objects", "Object JSON Demo"))
    details = details_of(gui)
    for label in ("Layer o/Regular", "First shape", "First contour"):
        assert label in details
    assert "Read back by FontLab: no (0 of 1)" in details


def test_object_json_demo_when_layer_has_shape_without_contours_then_no_contour_line(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, ["o"])
    layer = SimpleNamespace(name="Regular", shapes=[SimpleNamespace(contours=[])])
    package = Package()
    package.glyphs["o"].activeLayer = lambda: layer
    gui = install_host(monkeypatch, Producer(), package=package, current=None)
    run_script(script_path("Objects", "Object JSON Demo"))
    details = details_of(gui)
    assert "First shape" in details and "First contour" not in details


def test_object_json_demo_when_empty_layer_then_only_glyph_and_layer(
    monkeypatch,
) -> None:
    sel_names(monkeypatch, ["o"])
    layer = SimpleNamespace(name="Regular", shapes=[])
    package = Package()
    package.glyphs["o"].activeLayer = lambda: layer
    gui = install_host(monkeypatch, Producer(), package=package, current=None)
    run_script(script_path("Objects", "Object JSON Demo"))
    details = details_of(gui)
    assert "Layer o/Regular" in details and "First shape" not in details


RAW = json.dumps({**ENVELOPE, "glyph": {"name": "o", "layers": []}}).encode()


def paste_host(monkeypatch, clipboard=RAW):
    import fontlabapp.core.history.glyphs as history

    monkeypatch.setattr(json_data, "read_clipboard", lambda *a, **k: clipboard)
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: "facts")
    return install_host(monkeypatch, Producer(), package=Package())


def test_paste_glyphs_demo_when_clipboard_empty_then_says_so(monkeypatch) -> None:
    gui = paste_host(monkeypatch, clipboard=None)
    run_script(script_path("Objects", "Paste JSON Glyphs Demo"))
    assert texts(gui) == ["The clipboard holds no object JSON. Nothing was changed."]


def test_paste_glyphs_demo_when_refused_then_nothing_pasted_message(
    monkeypatch,
) -> None:
    def refuse(*_a, **_k):
        raise ValueError("bad data")

    monkeypatch.setattr(json_data, "paste_glyphs", refuse)
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Glyphs Demo"))
    assert texts(gui) == ["Nothing was pasted: bad data"]


def test_paste_glyphs_demo_when_pasted_then_reports_created_notes_skipped(
    monkeypatch,
) -> None:
    seen = {}

    def paste(package, raw, *, facts, title):
        seen.update(raw=raw, facts=facts, title=title)
        return json_data.Pasted(("o.1",), ("layer: not a glyph",), ("o -> o.1",))

    monkeypatch.setattr(json_data, "paste_glyphs", paste)
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Glyphs Demo"))
    assert texts(gui) == [f"Created 1 glyphs. {json_data.GLYPHS_UNDO_TEXT}"]
    assert details_of(gui).splitlines() == [
        "Created: o.1",
        "Note: o -> o.1",
        "Skipped: layer: not a glyph",
    ]
    assert seen == {"raw": RAW, "facts": "facts", "title": "Paste JSON Glyphs"}


def test_paste_glyphs_demo_when_nothing_created_then_created_nothing_line(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        json_data, "paste_glyphs", lambda *a, **k: json_data.Pasted((), ("o: exists",))
    )
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Glyphs Demo"))
    assert details_of(gui).splitlines() == ["Created: nothing", "Skipped: o: exists"]


# --- Edit JSON Before Paste, Import From File, Paste Shapes: remaining paths


def test_edit_demo_when_nothing_selected_then_asks_for_glyphs(monkeypatch) -> None:
    sel_names(monkeypatch, [])
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Edit JSON Before Paste Demo"))
    assert texts(gui) == ["Select glyphs first. Nothing was changed."]


def test_edit_demo_when_pasted_then_edited_envelope_pasted_and_reported(
    monkeypatch,
) -> None:
    seen = {}

    def paste(package, envelope, *, facts, title):
        seen.update(envelope=envelope, facts=facts, title=title)
        return json_data.Pasted(("o.edit",), ("p: exists",), ("note one",))

    sel_names(monkeypatch, ["o", "missing"])
    monkeypatch.setattr(json_data, "export", lambda package, glyphs: RAW)
    monkeypatch.setattr(json_data, "paste_glyphs", paste)
    gui = paste_host(monkeypatch)
    module = run_script(script_path("Objects", "Edit JSON Before Paste Demo"))
    assert texts(gui) == [f"Created 1 edited glyphs. {json_data.GLYPHS_UNDO_TEXT}"]
    names = [p["name"] for _, p in seen["envelope"].items]
    assert names == ["o" + module["SUFFIX"]], "the pasted envelope is the edited one"
    assert (seen["facts"], seen["title"]) == ("facts", module["TITLE"])
    lines = details_of(gui).splitlines()
    assert lines[0] == "Edited JSON:"
    assert lines[-3:] == ["Created: o.edit", "Note: note one", "Skipped: p: exists"]


def test_edit_demo_when_paste_refused_then_nothing_pasted_with_edited_json(
    monkeypatch,
) -> None:
    def refuse(*_a, **_k):
        raise RuntimeError("native refused")

    sel_names(monkeypatch, ["o"])
    monkeypatch.setattr(json_data, "export", lambda package, glyphs: RAW)
    monkeypatch.setattr(json_data, "paste_glyphs", refuse)
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Edit JSON Before Paste Demo"))
    assert texts(gui) == ["Nothing was pasted: native refused"]
    assert details_of(gui).splitlines()[0] == "Edited JSON:"


def test_import_demo_when_dialog_cancelled_then_no_message_and_no_paste(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        json_data, "paste_glyphs", lambda *a, **k: pytest.fail("pasted")
    )
    gui = paste_host(monkeypatch)
    gui.QFileDialog.getOpenFileName.return_value = ""
    run_script(script_path("Objects", "Import Glyphs From JSON File Demo"))
    assert texts(gui) == []


def test_import_demo_when_file_chosen_then_file_bytes_pasted_and_reported(
    monkeypatch, tmp_path
) -> None:
    source = tmp_path / "glyphs.json"
    source.write_bytes(RAW)
    seen = {}

    def paste(package, raw, *, facts, title):
        seen.update(raw=raw, facts=facts)
        return json_data.Pasted((), ("o: exists",), ("note",))

    monkeypatch.setattr(json_data, "paste_glyphs", paste)
    gui = paste_host(monkeypatch)
    gui.QFileDialog.getOpenFileName.return_value = str(source)
    run_script(script_path("Objects", "Import Glyphs From JSON File Demo"))
    assert texts(gui) == [f"Created 0 glyphs. {json_data.GLYPHS_UNDO_TEXT}"]
    assert details_of(gui).splitlines() == [
        "Created: nothing",
        "Note: note",
        "Skipped: o: exists",
    ]
    assert seen == {"raw": RAW, "facts": "facts"}


def test_import_demo_when_file_missing_then_nothing_imported(
    monkeypatch, tmp_path
) -> None:
    gui = paste_host(monkeypatch)
    gui.QFileDialog.getOpenFileName.return_value = str(tmp_path / "absent.json")
    run_script(script_path("Objects", "Import Glyphs From JSON File Demo"))
    (text,) = texts(gui)
    assert text.startswith("Nothing was imported: ")


def shapes_host(monkeypatch, clipboard=RAW):
    gui = paste_host(monkeypatch, clipboard=clipboard)
    import fontlab

    layer = SimpleNamespace(name="Regular")
    monkeypatch.setattr(
        fontlab,
        "CurrentGlyph",
        lambda: SimpleNamespace(name="o", activeLayer=lambda: layer),
        raising=False,
    )
    return gui, layer


def test_shapes_demo_when_no_glyph_open_then_asks_for_glyph(monkeypatch) -> None:
    gui = paste_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Shapes Into Layer Demo"))
    assert texts(gui) == ["Open a glyph first. Nothing was changed."]


def test_shapes_demo_when_clipboard_empty_then_says_so(monkeypatch) -> None:
    gui, _ = shapes_host(monkeypatch, clipboard=None)
    run_script(script_path("Objects", "Paste JSON Shapes Into Layer Demo"))
    assert texts(gui) == ["The clipboard holds no object JSON. Nothing was changed."]


def test_shapes_demo_when_pasted_then_undo_text_and_lines(monkeypatch) -> None:
    seen = {}

    def paste(layer, glyph, raw, *, facts, title):
        seen.update(layer=layer, glyph=glyph.name, raw=raw, facts=facts)
        return json_data.Pasted(("2 shapes on o/Regular",), ("glyph: paste glyphs",))

    monkeypatch.setattr(json_data, "paste_shapes", paste)
    gui, layer = shapes_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Shapes Into Layer Demo"))
    assert texts(gui) == [json_data.SHAPES_UNDO_TEXT]
    assert details_of(gui).splitlines() == [
        "Pasted: 2 shapes on o/Regular",
        "Skipped: glyph: paste glyphs",
    ]
    assert seen == {"layer": layer, "glyph": "o", "raw": RAW, "facts": "facts"}


def test_shapes_demo_when_nothing_usable_then_no_shapes_message(monkeypatch) -> None:
    monkeypatch.setattr(
        json_data,
        "paste_shapes",
        lambda *a, **k: json_data.Pasted((), ("glyph: paste glyphs",)),
    )
    gui, _ = shapes_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Shapes Into Layer Demo"))
    assert texts(gui) == ["No shapes to paste. Nothing was changed."]


def test_shapes_demo_when_refused_then_nothing_pasted_message(monkeypatch) -> None:
    def refuse(*_a, **_k):
        raise ValueError("bad data")

    monkeypatch.setattr(json_data, "paste_shapes", refuse)
    gui, _ = shapes_host(monkeypatch)
    run_script(script_path("Objects", "Paste JSON Shapes Into Layer Demo"))
    assert texts(gui) == ["Nothing was pasted: bad data"]


def test_export_demo_when_nothing_selected_then_asks_for_glyphs(monkeypatch) -> None:
    sel_names(monkeypatch, ["missing"])
    gui = install_host(monkeypatch, Producer(), package=Package())
    run_script(script_path("Objects", "Export Glyphs To JSON File Demo"))
    assert texts(gui) == ["Select glyphs first. Nothing was saved."]
    gui.QFileDialog.getSaveFileName.assert_not_called()


def test_export_demo_when_dialog_cancelled_then_nothing_saved(
    monkeypatch, tmp_path
) -> None:
    sel_names(monkeypatch, ["o"])
    monkeypatch.setattr(json_data, "save_file", lambda *a: pytest.fail("saved"))
    gui = install_host(monkeypatch, Producer(), package=Package())
    gui.QFileDialog.getSaveFileName.return_value = ""
    run_script(script_path("Objects", "Export Glyphs To JSON File Demo"))
    assert texts(gui) == []
