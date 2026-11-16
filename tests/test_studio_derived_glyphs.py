# this_file: tests/test_studio_derived_glyphs.py
"""Derived Glyphs (A17): parity with the 6 Scriptmix scripts, read-only previews and labelled writes.

Every tab is opened on a fake font. Opening, control changes and row choices
must call no writer and change no shape. Apply is checked against the
recorded writer call: the ``Derived Glyphs: <action> <subject>`` title, the
target glyphs and master layers, the transforms and widths, the rebuild
consent and (for Default figures and Unicase) the one ``history.commit``
step of the shared component-set writer. The pure functions are compared
with the Scriptmix originals by AST; their file hashes are pinned.
"""

from _demo_support import stub_natives

import ast
import hashlib
import importlib
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_studio_component_studio as t14
from _derived_glyphs_originals import ORIGINALS
from _studio_qt import studio_qt  # noqa: F401 - fixture

PKG = "fontlabapp.studios.derived_glyphs"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "fontlabapp" / "studios" / "derived_glyphs"
DEMO = ROOT / "Scripts" / "Contours" / "Derived Glyphs Demo.py"
SCRIPTMIX_ENV = os.environ.get("FONTLAB_SCRIPTMIX", "")
PINNED = "25c86b4"
#: Original title -> the port modules that hold its verbatim definitions.
PORTS = {
    "Small Caps From Capitals": ("small_caps",),
    "Superior & Inferior Figures": ("sups_subs",),
    "Tabular Figure Copies": ("tabular",),
    "Set Default Figures": ("default_figures", "_component_sets"),
    "Make Lower Unicase": ("unicase", "_component_sets"),
    "Placeholder Glyphs": ("placeholders",),
}
DIGITS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)
MASTERS = ("Regular", "Bold")


@pytest.fixture(autouse=True)
def fresh_studios():
    t14._forget_studio_children()
    yield
    t14._forget_studio_children()


def qt():
    return importlib.import_module("PythonQt")


def package():
    """The Component Studio font plus H, figures, .lf figures and lowercase a/b."""
    pkg = t14.package()
    both = lambda make: {m: make for m in MASTERS}  # noqa: E731
    pkg.add("H", both(t14.outline(2)))
    pkg.add("B", both(t14.outline(2)))
    pkg.add("a", both(t14.outline(1)), width=450)
    pkg.add("b", both(t14.outline(1)), width=470)
    pkg.add("zero", both(t14.outline(1)), width=480)
    pkg.add("one", both(t14.outline(1)), width=401)
    pkg.add("one.sups", both(t14.outline(1)))
    for name in DIGITS:
        pkg.add(f"{name}.lf", both(t14.outline(1)), width=520)
    return pkg


def shapes(pkg):
    return {
        (name, layer.name): [(s.isComponent, s.shapeData.componentGlyph, len(s.contours)) for s in layer.shapes]
        for name, glyph in pkg.glyphs.items()
        for layer in glyph.layers
    }  # fmt: skip


class Settings:
    """``QSettings("FontLab", "ScriptDefaultFigures")`` stand-in."""

    NoError, AccessError = 0, 1

    def __init__(self, value=0, *, writable=True, status=0):
        self.values, self.writable, self.state, self.saved = (
            {"optionFigures": value},
            writable,
            status,
            [],
        )

    def setFallbacksEnabled(self, flag):  # noqa: N802 - Qt API
        self.fallbacks = flag

    def sync(self):
        pass

    def status(self):
        return self.state

    def value(self, key, default):
        return self.values.get(key, default)

    def isWritable(self):  # noqa: N802 - Qt API
        return self.writable

    def setValue(self, key, value):  # noqa: N802 - Qt API
        self.values[key] = value
        self.saved.append(value)


def preview_widget():
    """The read-only TMetrics stand-in: a widget that records what the tabs show."""
    from PySide6.QtWidgets import QWidget

    class Preview(QWidget):
        def __init__(self):
            super().__init__()
            self.calls = []

        def set_text(self, text):
            self.calls.append(("text", text))

        def set_layer(self, layer):
            self.calls.append(("layer", layer))

    return Preview()


@pytest.fixture
def opened(studio_qt, monkeypatch):  # noqa: F811
    import fontlabapp.components.creation as component_creation
    import fontlabapp.components.writer as writer
    import fontlabapp.contours.copy as contour_copy
    import fontlabapp.core.edit_guards as edit_guards
    import fontlabapp.core.history.glyphs as history
    import fontlabapp.glyphs.copies as copies
    import fontlabapp.glyphs.creation as creation

    layer_type, package_type = t14.Layer, t14.Package
    monkeypatch.setattr(layer_type, "anchors", (), raising=False)
    monkeypatch.setattr(layer_type, "recipe", "", raising=False)
    monkeypatch.setattr(
        layer_type,
        "boundingBox",
        NS(x=lambda: 50.4, width=lambda: 301.0),
        raising=False,
    )
    monkeypatch.setattr(layer_type, "clearAnchors",
                        lambda self: self.pkg.log.append(("clear anchors", self.glyph, self.name)), raising=False)  # fmt: skip
    container = NS(checkInitHistoryState=lambda flag: None)
    monkeypatch.setattr(package_type, "kerning",
                        lambda self, m: self.__dict__.setdefault("kern", {}).setdefault(str(m), NS(groups={})),
                        raising=False)  # fmt: skip
    monkeypatch.setattr(
        package_type, "kerningContainer", lambda self: container, raising=False
    )
    monkeypatch.setattr(
        package_type, "mastersContainer", lambda self: container, raising=False
    )
    monkeypatch.setattr(
        package_type, "checkInitHistoryState", lambda self, flag: None, raising=False
    )
    monkeypatch.setattr(package_type, "name", "Demo Sans", raising=False)
    monkeypatch.setattr(edit_guards, "pending_updates", lambda native=None: ())
    facts = NS(value=history.auto_facts([]))
    monkeypatch.setattr(history, "scan_auto_facts", lambda package: facts.value)

    def open_app(
        pkg=None, selection=("A", "H", "Aacute", "acute"), figures=None, catalog_rows=()
    ):
        pkg = package() if pkg is None else pkg
        writes, guards, proto = [], [], NS(value="prototype")
        app = NS(pkg=pkg, writes=writes, guards=guards, proto=proto, facts=facts, mismatches=[],
                 settings=figures or Settings(), selection=list(selection), catalog=list(catalog_rows))  # fmt: skip

        def commit(
            title,
            layers,
            glyphs,
            mutate,
            *,
            operation,
            facts,
            allow_bases=False,
            retain=(),
            read_back=None,
        ):
            writes.append(("commit", title, [g.name for g in glyphs], [(la.glyph, la.name) for la in layers],
                           operation, allow_bases))  # fmt: skip
            mutate()
            return NS(
                mismatches=(read_back() if read_back else []) + app.mismatches,
                pending_note="",
            )

        def create_glyphs(
            package,
            specs,
            title,
            facts,
            *,
            fill=None,
            read_back=None,
            allow_rebuild=False,
        ):
            writes.append(("create", title, [(s.name, s.layers, s.unicodes,
                                             tuple((p.master, p.base) for p in s.components)) for s in specs],
                           allow_rebuild))  # fmt: skip
            made = []
            for spec in specs:
                parts = {
                    m: [(p.base, (p.x, p.y)) for p in spec.components if p.master == m]
                    for m, _ in spec.layers
                }
                glyph = package.add(
                    spec.name,
                    {
                        m: t14.comps(*parts[m]) if parts[m] else None
                        for m, _ in spec.layers
                    },
                )
                for master, width in spec.layers:
                    glyph.findLayer(master).advanceWidth = width
                glyph.unicodes, glyph.fgGlyphId = (
                    spec.unicodes,
                    900 + len(package.glyphs),
                )
                made.append(glyph)
            return creation.Created(
                tuple(made), tuple(read_back() if read_back else ())
            )

        def copies_create(package, jobs, title, facts, *, allow_rebuild=False):
            writes.append(("copies", title, jobs, allow_rebuild))
            layers = sum(len(job[1]) for job in jobs)
            return {
                "glyphs": len(jobs),
                "layers": layers,
                "mismatches": [],
                "pending_note": "",
                "pending_updates": (),
            }

        def current_font():
            glyphs = [NS(name=g.name, unicodes=getattr(g, "unicodes", ()), id=getattr(g, "fgGlyphId", 0))
                      for g in app.pkg.glyphs.values()]  # fmt: skip
            return NS(glyphs=glyphs)

        found = NS(
            copies=NS(**{**vars(copies), "create": copies_create}),
            creation=NS(**{**vars(creation), "create_glyphs": create_glyphs}),
            component_creation=NS(
                NewComponent=component_creation.NewComponent,
                NO_PROTOTYPE=component_creation.NO_PROTOTYPE,
                prototype=lambda package, facts: proto.value,
                build_components=lambda package, target, wanted, facts: [
                    t14.Shape(package, base=w.base) for w in wanted
                ],
                add_component=lambda layer, shape: layer.insertShape(
                    len(layer.shapes), shape
                ),
            ),
            components=writer,
            contour_copy=NS(
                contour_shapes=contour_copy.contour_shapes,
                copy_contours=lambda layer, t: [
                    (layer.glyph, layer.name, t.m11(), t.m22(), t.dx(), t.dy())
                ],
            ),
            catalog=NS(capture=lambda: NS(rows=list(app.catalog))),
            fontlab=NS(CurrentFont=current_font),
        )
        studio = importlib.import_module(PKG)
        shared = importlib.import_module(f"{PKG}._shared")
        monkeypatch.setattr(shared, "backends", lambda: found)
        monkeypatch.setattr(history, "commit", commit)
        monkeypatch.setattr(
            importlib.import_module(f"{PKG}.default_figures"),
            "settings",
            lambda: app.settings,
        )
        monkeypatch.setattr(
            edit_guards,
            "require_selection_window",
            lambda font_id: guards.append(("window", font_id)),
        )
        monkeypatch.setattr(
            edit_guards, "require_no_editors", lambda: guards.append(("editors",))
        )
        kerning = sys.modules["fontlabapp.studios._kerning"]
        monkeypatch.setattr(
            kerning, "names_selected_names", lambda: list(app.selection)
        )
        active = NS(package=pkg)
        app.active = active
        app.preview = preview_widget()
        app.shell = studio.show(
            package=lambda: active.package,
            font=lambda: "font",
            preview=lambda shell, tool: app.preview,
        )
        studio_qt.owned.append(app.shell)
        app.tool = app.shell.derived_glyphs_tool
        app.studio = studio
        app.panels = {
            title: view.__self__
            for title, view in zip(studio.TAB_TITLES, app.tool.views)
        }
        app.before = shapes(pkg)
        return app

    return open_app


def rows(panel):
    return [(r.glyph_name, tuple(r.values)) for r in panel.grid.rows]


def text(widget):
    value = widget.text
    return value() if callable(value) else value


def unchanged(app):
    assert app.writes == [] and app.pkg.log == [] and shapes(app.pkg) == app.before


# ---------------------------------------------------------------- shell, registry, backends
def test_show_when_opened_then_six_tabs_tmetrics_preview_and_masters(opened):
    app = opened()
    assert app.studio.TAB_TITLES == (
        "Small caps",
        "Sups & subs",
        "Tabular figures",
        "Default figures",
        "Unicase",
        "Placeholders",
    )
    assert list(app.panels) == list(app.studio.TAB_TITLES)
    assert app.tool.app == "Derived Glyphs" and app.tool.masters == ["Regular", "Bold"]
    assert [p.ACTION for p in app.panels.values()] == [
        "Create glyphs",
        "Create glyphs",
        "Create glyphs",
        "Apply to default figures",
        "Apply to uppercase",
        "Create glyphs",
    ]
    unchanged(app)


def test_registry_when_imported_then_lazy_and_idempotent():
    import fontlabapp.studios as studios

    studio = importlib.import_module(PKG)
    assert studio.register_tabs() == studio.register_tabs() == studio.TAB_TITLES
    assert tuple(spec.title for spec in studios.tabs(studio.APP)) == studio.TAB_TITLES
    for module in {studio.PANELS[t][0] for t in studio.TAB_TITLES} | {
        "_shared",
        "_component_sets",
        "app",
    }:
        assert f"{PKG}.{module}" not in sys.modules, module


def test_backends_when_loaded_then_reused_app_modules_and_lazy_native(monkeypatch):
    import fontlabapp.core.scripting as scripting

    found = scripting.derived_glyphs_backends()
    assert {
        key: value.__name__ for key, value in vars(found).items() if key != "fontlab"
    } == {
        "copies": "fontlabapp.glyphs.copies",
        "creation": "fontlabapp.glyphs.creation",
        "component_creation": "fontlabapp.components.creation",
        "components": "fontlabapp.components.writer",
        "contour_copy": "fontlabapp.contours.copy",
        "catalog": "fontlabapp.glyphs.catalog.model",
        "dialogs": "fontlabapp.qt.dialogs",
    }
    seen = []
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: seen.append(name) or NS(CurrentFont=lambda: "font"),
    )
    assert seen == [] and found.fontlab.CurrentFont() == "font" and seen == ["fontlab"]


# ---------------------------------------------------------------- parity
def strip_fly(node):
    """Drop the originals' function-local ``fly`` imports (the ports read module names instead)."""
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if isinstance(body, list):
            child.body = [
                s
                for s in body
                if not (
                    isinstance(s, (ast.Import, ast.ImportFrom))
                    and "fly" in ast.unparse(s)
                )
            ]
    return node


def definitions(source):
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found[node.name] = node
        elif isinstance(node, ast.Assign):
            found.update({t.id: node for t in node.targets if isinstance(t, ast.Name)})
        elif isinstance(node, ast.AnnAssign):
            found[node.target.id] = node
    return found


def ported(title):
    found = {}
    for module in PORTS[title]:
        for name, node in definitions(
            (SOURCE / f"{module}.py").read_text(encoding="utf-8")
        ).items():
            found.setdefault(name, node)
    return found


@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_ported_then_pure_functions_match_the_script_ast(title):
    path, digest, names, source = ORIGINALS[title]
    assert path.endswith(".py") and len(digest) == 64 and names
    expected, found = definitions(source), ported(title)
    assert set(expected) == set(names), title
    for name in names:
        if (title, name) == ("Make Lower Unicase", "apply_pairs"):
            continue  # compared with the shared writer below
        assert ast.dump(strip_fly(found[name])) == ast.dump(
            strip_fly(expected[name])
        ), f"{title}: {name}"


def test_unicase_apply_pairs_when_compared_then_body_is_the_shared_writer_and_signature_kept():
    """Make Lower Unicase carried its own copy of the Set Default Figures writer (Scriptmix TODO:84)."""
    original = strip_fly(definitions(ORIGINALS["Make Lower Unicase"][3])["apply_pairs"])
    unicase = definitions((SOURCE / "unicase.py").read_text(encoding="utf-8"))[
        "apply_pairs"
    ]
    shared = definitions((SOURCE / "_component_sets.py").read_text(encoding="utf-8"))[
        "write_components"
    ]
    assert ast.dump(unicase.args) == ast.dump(original.args), (
        "Unicase keeps the original's signature and defaults"
    )
    defaults = dict(
        zip(
            (a.arg for a in original.args.kwonlyargs),
            original.args.kw_defaults,
            strict=True,
        )
    )
    assert defaults["replace_contours"].value is True
    defaults["replace_contours"].value = False
    original.name, original.body[0] = "write_components", shared.body[0]
    assert ast.dump(original) == ast.dump(shared)


@pytest.mark.skipif(
    not SCRIPTMIX_ENV,
    reason="FONTLAB_SCRIPTMIX is not set: pinned Scriptmix hashes not checked",
)
@pytest.mark.parametrize("title", sorted(ORIGINALS))
def test_originals_when_scriptmix_present_then_pinned_hash_matches(title):
    path, digest, _, _ = ORIGINALS[title]
    data = subprocess.run(
        ["git", "-C", SCRIPTMIX_ENV, "show", f"{PINNED}:{path}"],
        capture_output=True,
        check=False,
    )
    if data.returncode:
        pytest.skip(
            f"pinned Scriptmix commit {PINNED} not available in FONTLAB_SCRIPTMIX={SCRIPTMIX_ENV}"
        )
    assert hashlib.sha256(data.stdout).hexdigest() == digest


@pytest.mark.usefixtures("studio_qt")
def test_label_when_one_or_many_glyphs_then_name_or_count():
    shared = importlib.import_module(f"{PKG}._shared")
    assert (
        shared.label("create small caps", ["h.sc", "h.sc"])
        == "Derived Glyphs: create small caps h.sc"
    )
    assert (
        shared.label("create small caps", ["a.sc", "h.sc"])
        == "Derived Glyphs: create small caps 2 glyphs"
    )
    assert (
        shared.plural(1, "glyph") == "1 glyph"
        and shared.plural(2, "glyph") == "2 glyphs"
    )
    many = {"mismatches": [str(n) for n in range(7)], "pending_note": "queued"}
    assert (
        shared.result_note("Done", many)
        == "Done · did not read back as planned: 0; 1; 2; 3; 4 · queued"
    )
    assert (
        shared.result_note("Done · queued", {"pending_note": "queued"})
        == "Done · queued"
    )
    with pytest.raises(AttributeError):
        shared.Modules("copies").__wrapped__  # noqa: B018 - dunder lookups never reach the backends


# ---------------------------------------------------------------- Small caps
def test_small_caps_when_opened_then_original_plan_and_read_only(opened):
    app = opened()
    panel = app.panels["Small caps"]
    assert rows(panel) == [
        ("A", ("a.sc", "create on 2 masters")),
        ("H", ("h.sc", "create on 2 masters")),
        ("Aacute", ("aacute.sc", "Regular: built from components")),
        ("acute", ("", "not a capital")),
    ]
    assert text(panel.subtitle) == "4 glyphs: A, H, Aacute, acute"
    assert text(panel.status) == "2 glyphs to create" and panel.apply_button.isEnabled()
    assert (panel.x_scale.value(), panel.y_scale.value()) == (75, 70)
    assert (panel.x_scale.minimum(), panel.x_scale.maximum()) == (10, 200)
    assert (
        panel.consent.text() == "Create even if FontLab may rebuild these auto glyphs"
    )
    panel.x_scale.setValue(80)
    panel.grid.select("A")
    assert app.preview.calls[-2:] == [("text", "/A"), ("layer", "Regular")]
    unchanged(app)


def test_small_caps_when_applied_then_one_labelled_copies_call_with_scaled_jobs(opened):
    app = opened()
    panel = app.panels["Small caps"]
    assert panel.apply() is True
    [(kind, title, jobs, allow)] = app.writes
    assert (kind, title, allow) == (
        "copies",
        "Derived Glyphs: create small caps 2 glyphs",
        False,
    )
    assert jobs == [
        ("a.sc", [(m, [("A", m, 0.75, 0.7, 0.0, 0.0)], 450) for m in MASTERS]),
        ("h.sc", [(m, [("H", m, 0.75, 0.7, 0.0, 0.0)], 375) for m in MASTERS]),
    ]
    assert app.tool.status == "Created 2 glyphs (4 master layers)"


def test_small_caps_when_auto_glyph_may_rebuild_then_consent_gates_and_reselect_clears(
    opened,
):
    import fontlabapp.core.history.glyphs as history

    pkg = package()
    pkg.add("aacute.sc", {m: t14.comps(("a", (0, 0))) for m in MASTERS}, auto=True)
    app = opened(pkg)
    app.facts.value = history.auto_facts([("aacute.sc", True, ("a",))])
    panel = app.panels["Small caps"]
    panel.reselect()
    assert rows(panel)[0] == ("A", ("a.sc", "may rebuild auto aacute.sc"))
    panel.consent.setChecked(True)
    assert rows(panel)[0] == (
        "A",
        ("a.sc", "create on 2 masters · may rebuild auto aacute.sc"),
    )
    unchanged(app)
    assert panel.apply() is True and app.writes[-1][-1] is True
    panel.consent.setChecked(True)
    panel.reselect()
    assert not panel.consent.isChecked()


def test_small_caps_when_font_changed_after_listing_then_stale_refusal_and_no_write(
    opened,
):
    app = opened()
    panel = app.panels["Small caps"]
    app.pkg.add("h.sc", {m: t14.outline(1) for m in MASTERS})
    assert panel.apply() is False
    assert (
        app.writes == []
        and app.tool.status
        == "The font changed since the list was made; check the list again."
    )
    assert rows(panel)[1] == ("H", ("h.sc", "h.sc exists"))


def test_plan_panel_when_no_font_or_other_font_or_empty_selection_then_refusals(opened):
    app = opened(selection=())
    panel = app.panels["Small caps"]
    assert (
        text(panel.subtitle)
        == "Select capitals in the Font window. Then press Use selection."
    )
    assert not panel.apply_button.isEnabled() and rows(panel) == []
    app.selection[:] = ["H"]
    panel.selection_button.click()
    assert rows(panel) == [("H", ("h.sc", "create on 2 masters"))]
    other = package()
    other.id = 8
    app.active.package = other
    assert (
        panel.apply() is False
        and app.tool.status == "The font changed. Run this script again."
    )
    app.active.package = None
    assert panel.apply() is False and app.tool.status == "Open a font first."
    panel.refresh()
    assert (
        text(panel.subtitle) == "Derived Glyphs: Open a font first."
        and rows(panel) == []
    )
    panel.row_chosen("H")
    assert app.writes == []


# ---------------------------------------------------------------- Sups & subs
def test_sups_subs_when_kind_changes_then_preset_shift_label_and_transform(opened):
    app = opened(selection=("zero", "one", "one.sups", "A"))
    panel = app.panels["Sups & subs"]
    assert [panel.kind.itemText(i) for i in range(2)] == [
        "Superior (.sups)",
        "Inferior (.subs)",
    ]
    assert (panel.factor.value(), panel.shift.value()) == (60, 350)
    assert rows(panel) == [
        ("zero", ("zero.sups", "create on 2 masters")),
        ("one", ("one.sups", "one.sups exists")),
        ("one.sups", ("", "already superior or inferior")),
        ("A", ("", "not a figure")),
    ]
    panel.kind.setCurrentIndex(1)
    assert panel.shift.value() == -150 and rows(panel)[1] == (
        "one",
        ("one.subs", "create on 2 masters"),
    )
    unchanged(app)
    assert panel.apply() is True
    [(_, title, jobs, _)] = app.writes
    assert title == "Derived Glyphs: create inferior figures 2 glyphs"
    assert jobs[1] == (
        "one.subs",
        [(m, [("one", m, 0.6, 0.6, 0.0, -150.0)], 241) for m in MASTERS],
    )


# ---------------------------------------------------------------- Tabular figures
def test_tabular_when_opened_then_shared_width_intro_and_centred_jobs(opened):
    app = opened(selection=("zero", "one", "zero.lf", "A"))
    panel = app.panels["Tabular figures"]
    assert (panel.extra.value(), panel.extra.minimum(), panel.extra.maximum()) == (
        0,
        -200,
        400,
    )
    assert text(panel.subtitle) == "Shared width per master: Regular 520, Bold 520"
    assert rows(panel)[3] == ("A", ("", "not a figure"))
    panel.extra.setValue(10)
    assert text(panel.subtitle) == "Shared width per master: Regular 530, Bold 530"
    unchanged(app)
    assert panel.apply() is True
    [(_, title, jobs, _)] = app.writes
    assert title == "Derived Glyphs: create tabular figures 3 glyphs"
    # Ink 50..351: left 50, ink 301; (530 - 301) // 2 - 50 = 64.
    assert jobs[0] == (
        "zero.tf",
        [(m, [("zero", m, 1.0, 1.0, 64.0, 0.0)], 530) for m in MASTERS],
    )
    app.selection[:] = ["A"]
    panel.reselect()
    assert text(panel.subtitle) == "No figure qualifies."


# ---------------------------------------------------------------- Default figures
def test_default_figures_when_opened_then_ten_cells_planned_read_only(opened):
    app = opened()
    panel = app.panels["Default figures"]
    assert [panel.figure_family.itemText(i) for i in range(4)] == [
        "Lining (.lf)", "Oldstyle (.osf)", "Tabular lining (.tf)", "Tabular oldstyle (.tosf)",
    ]  # fmt: skip
    assert not panel.replace_contours.isChecked() and not hasattr(
        panel, "selection_button"
    )
    assert rows(panel)[0] == ("zero.lf", ("zero", "replace components; keep contours"))
    assert len(rows(panel)) == 10 and text(panel.status) == "10 rows ready"
    assert text(panel.subtitle).startswith(
        "Source advances and kerning memberships are copied; existing anchors stay."
    )
    panel.replace_contours.setChecked(True)
    assert rows(panel)[0] == ("zero.lf", ("zero", "replace contours and components"))
    panel.check_button.click()
    panel.grid.select("zero.lf")
    assert app.preview.calls[-2] == ("text", "/zero.lf/zero")
    unchanged(app)


def test_default_figures_when_applied_then_creates_missing_cells_and_keeps_own_contours(
    opened,
):
    app = opened()
    panel = app.panels["Default figures"]
    assert panel.apply() is True
    title = "Derived Glyphs: set default figures digits"
    create, commit = app.writes
    assert create[:2] == ("create", title) and create[3] is False
    assert create[2][0] == (
        "two",
        (("Regular", 520.0), ("Bold", 520.0)),
        (0x32,),
        (("Regular", "two.lf"), ("Bold", "two.lf")),
    )
    assert [spec[0] for spec in create[2]] == list(DIGITS[2:])
    assert commit == ("commit", title, ["zero", "one"], [(g, m) for g in ("zero", "one") for m in MASTERS],
                      "geometry", False)  # fmt: skip
    zero = shapes(app.pkg)[("zero", "Regular")]
    assert zero == [(False, None, 1), (True, "zero.lf", 0)], (
        "source-default contours stay (Scriptmix TODO:16)"
    )
    assert app.pkg.layer("zero", "Bold").advanceWidth == 520.0
    assert app.tool.status.startswith(
        "Changed 20 master layers. new glyphs that exist now: two, three, four"
    )


def test_default_figures_when_replace_own_contours_then_contours_removed_anchors_kept(
    opened,
):
    app = opened()
    panel = app.panels["Default figures"]
    panel.replace_contours.setChecked(True)
    assert panel.apply() is True
    assert shapes(app.pkg)[("zero", "Regular")] == [(True, "zero.lf", 0)]
    assert not [entry for entry in app.pkg.log if entry[0] == "clear anchors"]


def test_default_figures_when_family_changes_then_saved_and_missing_source_refused(
    opened,
):
    app = opened()
    panel = app.panels["Default figures"]
    panel.figure_family.setCurrentIndex(1)
    assert app.settings.saved == [1]
    assert text(panel.subtitle) == "Missing zero or zero.osf; no figures changed."
    assert not panel.apply_button.isEnabled()
    unchanged(app)


def test_default_figures_when_settings_fail_then_usable_tab_and_original_errors(opened):
    app = opened(figures=Settings(value="7", writable=False, status=1))
    panel = app.panels["Default figures"]
    assert (
        text(panel.status)
        == "Saved figure settings could not be loaded: Figure settings could not be read."
    )
    assert panel.figure_family.currentIndex() == 0
    module = sys.modules[f"{PKG}.default_figures"]
    good = Settings(value="9")
    assert module.load_family(good) == 0 and good.fallbacks is False
    assert module.load_family(Settings(value=3)) == 3
    with pytest.raises(ValueError, match="Choose one of the four figure sets."):
        module.save_family(good, 4)
    with pytest.raises(RuntimeError, match="Figure settings are read-only."):
        module.save_family(Settings(writable=False), 1)
    with pytest.raises(RuntimeError, match="Figure settings could not be saved."):
        module.save_family(Settings(status=1), 1)
    with pytest.raises(ValueError, match="Choose one of the four figure sets."):
        module.mappings(app.pkg, 5)


def test_default_figures_when_existing_cell_has_no_prototype_or_is_locked_then_kept(
    opened,
):
    app = opened()
    app.proto.value = None
    panel = app.panels["Default figures"]
    panel.rescan()
    assert rows(panel)[0][1][1].startswith(
        "zero: kept; the font has no plain, unattached component"
    )
    app.proto.value = "prototype"
    app.pkg.layer("zero", "Bold").isLocked = True
    panel.rescan()
    assert rows(panel)[0][1][1] == "zero: kept; zero · Bold: layer is locked."
    assert text(panel.status) == "9 rows ready"


# ---------------------------------------------------------------- Unicase
CATALOG = (
    ("A", "U+0041", ""),
    ("a", "U+0061", ""),
    ("B", "U+0042", ""),
    ("b", "U+0062", ""),
    ("c", "U+0063", ""),
)


def test_unicase_when_opened_then_survey_listed_and_apply_waits_for_preview(opened):
    app = opened(catalog_rows=CATALOG)
    panel = app.panels["Unicase"]
    assert rows(panel) == [
        ("a", ("A", "replace on 2 masters")),
        ("b", ("B", "replace on 2 masters")),
        ("c", ("", "kept: no existing uppercase glyph")),
    ]
    assert not panel.apply_button.isEnabled() and text(panel.status) == "2 rows ready"
    assert (
        panel.apply() is False
        and app.tool.status == "The plan changed. Press Preview before Apply."
    )
    panel.preview_button.click()
    assert (
        panel.apply_button.isEnabled()
        and app.tool.status == "Preview ready. Apply asks for confirmation."
    )
    unchanged(app)


def test_unicase_when_confirmed_then_one_labelled_commit_replaces_drawings(
    opened, monkeypatch
):
    app = opened(catalog_rows=CATALOG)
    panel = app.panels["Unicase"]
    asked = []
    monkeypatch.setattr(
        sys.modules[f"{PKG}.unicase"],
        "confirm",
        lambda parent, message: asked.append(message) or True,
    )
    panel.preview()
    assert panel.apply() is True
    assert asked == [
        'Replace uppercase drawings in "Demo Sans"?\n2 glyphs, 4 layers.\n0 targets created; 2 targets replaced.'
    ]
    [commit] = [w for w in app.writes if w[0] == "commit"]
    assert commit == ("commit", "Derived Glyphs: make unicase 2 glyphs", ["A", "B"],
                      [(g, m) for g in "AB" for m in MASTERS], "geometry", False)  # fmt: skip
    assert shapes(app.pkg)[("A", "Bold")] == [(True, "a", 0)]
    assert ("clear anchors", "A", "Regular") in app.pkg.log
    assert app.pkg.layer("B", "Regular").advanceWidth == 470.0
    assert (
        app.tool.status == "Changed 4 master layers."
        and not panel.apply_button.isEnabled()
    )


def test_unicase_when_declined_or_changed_then_no_write(opened, monkeypatch):
    app = opened(catalog_rows=CATALOG)
    panel = app.panels["Unicase"]
    module = sys.modules[f"{PKG}.unicase"]
    monkeypatch.setattr(module, "confirm", lambda parent, message: False)
    panel.preview()
    assert panel.apply() is False and app.writes == []

    def change(parent, message):
        app.pkg.glyphs["A"].findLayer("Regular").shapes.append(
            t14.Shape(app.pkg, contours=1)
        )
        return True

    monkeypatch.setattr(module, "confirm", change)
    assert panel.apply() is False
    assert (
        app.tool.status == "The plan changed during confirmation. Press Preview again."
        and app.writes == []
    )
    panel.preview()
    app.pkg.glyphs["B"].findLayer("Regular").shapes.append(
        t14.Shape(app.pkg, contours=1)
    )
    assert (
        panel.apply() is False
        and app.tool.status == "The plan changed. Press Preview before Apply."
    )
    assert app.writes == []


def test_unicase_when_target_is_base_of_auto_glyph_then_kept_without_opt_in(opened):
    import fontlabapp.core.history.glyphs as history

    app = opened(catalog_rows=CATALOG)
    app.facts.value = history.auto_facts([("Aacute", True, ("A", "acute"))])
    panel = app.panels["Unicase"]
    panel.preview()
    assert rows(panel)[0] == ("a", ("A", "A: kept; A: base of auto Aacute."))
    assert panel.consent is None


@pytest.mark.usefixtures("studio_qt")
def test_unicase_confirm_when_asked_then_standard_question_box_default_no(monkeypatch):
    import fontlabapp.qt.dialogs as dialogs

    module = importlib.import_module(f"{PKG}.unicase")
    box = qt().QtGui.QMessageBox
    seen = []
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a: seen.append(a[2:]) or box.Yes
    )
    assert module.confirm(None, "Replace?") is True
    assert seen == [
        (
            "Make Lower Unicase",
            "Replace?",
            "Question",
            box.StandardButtons(box.Yes | box.No),
            box.No,
        )
    ]


# ---------------------------------------------------------------- Placeholders
def test_placeholders_when_typed_then_live_list_and_read_only(opened):
    app = opened()
    panel = app.panels["Placeholders"]
    assert panel.advance.value() == 600 and (
        panel.advance.minimum(),
        panel.advance.maximum(),
    ) == (0, 4000)
    panel.consent.setChecked(True)
    panel.text.setPlainText("A.alt ₿ A, &")
    assert not panel.consent.isChecked(), "a text change clears the rebuild consent"
    assert rows(panel) == [
        ("A.alt", ("", "create on 2 masters")),
        ("uni20BF", ("U+20BF", "create on 2 masters")),
        ("A", ("", "exists: skipped")),
        ("&", ("", "invalid name: skipped")),
    ]
    assert (
        text(panel.subtitle)
        == "Creates empty glyphs on all 2 masters. Existing glyphs are never overwritten."
    )
    assert text(panel.status) == "2 glyphs to create · 2 skipped"
    panel.grid.select("A.alt")
    unchanged(app)


def test_placeholders_when_created_then_add_glyph_route_with_code_point_guards(opened):
    app = opened()
    panel = app.panels["Placeholders"]
    panel.text.setPlainText("A.alt ₿")
    panel.advance.setValue(610)
    assert panel.apply() is True
    [(kind, title, specs, allow)] = app.writes
    assert (kind, title, allow) == (
        "create",
        "Derived Glyphs: create placeholder glyphs",
        False,
    )
    assert specs == [("A.alt", (("Regular", 610), ("Bold", 610)), (), ()),
                     ("uni20BF", (("Regular", 610), ("Bold", 610)), (0x20BF,), ())]  # fmt: skip
    assert app.guards == [("window", 7), ("editors",)]
    assert app.tool.status == "Created 2 glyphs (4 master layers, 1 code point)"


def test_placeholders_when_unsafe_or_taken_then_original_refusals(opened):
    app = opened()
    panel = app.panels["Placeholders"]
    module = sys.modules[f"{PKG}.placeholders"]
    with pytest.raises(ValueError) as refused:
        module.parse("A.alt\u00a0B.alt")
    assert str(refused.value) == (
        "Refused: the text holds no-break space. FontLab's text conversion can change it; "
        "remove it and type the names again."
    )
    panel.text.setPlainText("A.alt \u20bf")
    app.pkg.glyphs["H"].unicodes, app.pkg.glyphs["H"].fgGlyphId = (0x20BF,), 5
    assert panel.apply() is False and app.tool.status == STALE_TEXT
    row = module.Row("uni20BE", 0x20BE)
    app.pkg.glyphs["B"].unicodes = (0x20BE,)
    with pytest.raises(
        ValueError, match=r"Refused: U\+20BE is on B now. Check the list again."
    ):
        module.create(app.pkg, [row], 600, app.facts.value)
    assert (
        module.create(app.pkg, [module.Row("x", None, problem="exists")], 600, None)[
            "glyphs"
        ]
        == 0
    )
    assert (
        module.code_of("uD800") is None
        and module.code_of("uniD800") is None
        and module.code_of("u110000") is None
    )
    assert module.char_name("\U0001f600") == "u1F600"
    assert app.writes == []


STALE_TEXT = "The font changed since the list was made; check the list again."


# ---------------------------------------------------------------- shared writer failure paths
def test_component_writer_when_read_back_fails_after_creation_then_partial_write_error(
    opened,
):
    import fontlabapp.core.history.glyphs as history

    app = opened()
    sets = sys.modules[f"{PKG}._component_sets"]
    app.mismatches.append("zero: not written")
    with pytest.raises(RuntimeError, match="zero: not written"):
        sets.write_components(
            app.pkg,
            [("zero", "zero.lf"), ("one", "one.lf")],
            title="T",
            clear_anchors=False,
        )

    def broken(*args, **kwargs):
        raise TimeoutError("FontLab did not answer")

    pkg = package()
    app.active.package = pkg
    sets_history = sets.history
    original = sets_history.commit
    sets_history.commit = broken
    try:
        with pytest.raises(
            history.PartialWriteError, match="T did not finish: FontLab did not answer"
        ):
            sets.write_components(
                pkg, [("zero", "zero.lf"), ("two", "two.lf")], title="T"
            )
    finally:
        sets_history.commit = original
    kept, report = [], []
    with pytest.raises(ValueError, match="No matching glyphs"):
        sets.validate_pairs(pkg, [])
    pkg.add("loop", {m: t14.comps(("zero", (0, 0))) for m in MASTERS})
    with pytest.raises(ValueError, match="zero: the new component would be circular."):
        sets.validate_pairs(pkg, [("zero", "loop")], facts=app.facts.value)
    pkg.add("auto", {m: t14.outline(1) for m in MASTERS}, auto=True)
    with pytest.raises(ValueError, match="auto: needs a plain layer for Regular."):
        sets.validate_pairs(pkg, [("x", "auto")], facts=app.facts.value)
    with pytest.raises(ValueError, match="Aacute: has auto layers."):
        sets.validate_pairs(
            pkg, [("Aacute", "A")], facts=history.auto_facts([("Aacute", True, ())])
        )
    assert (
        sets.write_components(pkg, [("zero", "missing")], kept=kept, report=report) == 0
    )
    assert kept and kept[0].startswith("zero: kept;")


def test_component_writer_when_only_classes_change_then_metadata_step(opened):
    app = opened()
    sets = sys.modules[f"{PKG}._component_sets"]
    pkg = app.pkg
    for master in MASTERS:
        pkg.kerning(master).groups["_zero"] = (["zero.lf"], "KernLeft")
        pkg.kerning(master).groups["mark"] = (["zero.lf"], "Mark")
    pkg.add("zero.new", {m: None for m in MASTERS})
    assert sets.group_plan(pkg, [("zero", "zero.lf")]) == {
        m: {"_zero": (["zero.lf", "zero"], "KernLeft")} for m in MASTERS
    }
    del pkg.glyphs["zero"]
    count = sets.write_components(pkg, [("zero", "zero.lf")], title="T", disclosure={})
    assert count == 2
    commit = app.writes[-1]
    assert commit[:3] == ("commit", "T", ["zero"]) and commit[4] == "metadata"
    assert pkg.kerning("Bold").groups["_zero"] == (["zero.lf", "zero"], "KernLeft")


# ---------------------------------------------------------------- demo and window assembly
def test_demo_when_run_then_shows_or_warns(monkeypatch):
    import fontlabapp
    import fontlabapp.qt.dialogs as dialogs

    calls = []
    studio = importlib.import_module(PKG)
    monkeypatch.setattr(studio, "show", lambda: calls.append("show"))
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls == ["show"]

    def broken():
        raise RuntimeError("no font")

    monkeypatch.setattr(studio, "show", broken)
    stub_natives(monkeypatch, fontlabapp, lambda name: NS(MainWindow=lambda: 'main', QtGui=NS(QMessageBox=NS(Ok=1))))
    monkeypatch.setattr(
        dialogs, "run_standard_message_box", lambda *a: calls.append(a[2:5])
    )
    runpy.run_path(str(DEMO), run_name="__main__")
    assert calls[-1] == (
        "Derived Glyphs Demo",
        "Derived Glyphs did not open: no font",
        "Warning",
    )
    assert runpy.run_path(str(DEMO), run_name="demo")["TITLE"] == "Derived Glyphs Demo"


@pytest.mark.usefixtures("studio_qt")
def test_app_when_default_preview_then_controlless_read_only_tmetrics(monkeypatch):
    import fontlabapp.fontui as fontui

    app_module = importlib.import_module(f"{PKG}.app")
    seen = []
    monkeypatch.setattr(
        fontui,
        "metrics_preview",
        lambda font, parent, **kw: seen.append((font, parent, kw)) or "view",
    )
    shell = NS(widget="widget", hint_check="check")
    tool = app_module.tool_for(shell)
    assert app_module.tool_for(shell) is tool and tool.app == "Derived Glyphs"
    tool._font = lambda: None
    assert app_module.metrics_preview(shell, tool) is None
    tool._font = lambda: "font"
    assert app_module.metrics_preview(shell, tool) == "view"
    assert seen == [("font", "widget", {"controls": False, "label_prefix": "Derived Glyphs",
                                        "hint_check": "check", "read_only": True})]  # fmt: skip


@pytest.mark.usefixtures("studio_qt")
def test_app_when_assembly_fails_then_shell_closed_and_error_raised(monkeypatch):
    import fontlabapp.fontui as fontui

    closed = []

    class Shell:
        def close(self):
            closed.append(True)

    monkeypatch.setattr(fontui, "app_shell", lambda *a, **k: Shell())
    studio = importlib.import_module(PKG)

    def broken(shell, tool):
        raise RuntimeError("no preview")

    with pytest.raises(RuntimeError, match="no preview"):
        studio.show(package=lambda: None, font=lambda: None, preview=broken)
    assert closed == [True]
    assert studio.tool_for(NS()).app == "Derived Glyphs"
