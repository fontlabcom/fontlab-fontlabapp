---
this_file: src_docs/md/domains-and-usage.md
---

# Domains and shared UI

## API map

The [module and domain map](guides/api-map.md) lists every App module, its public
names and purpose. Additive lazy facades give the main capabilities shorter
import paths without loading PythonQt when the facade itself is imported:

```python
from fly.ap.objects import FontLab, current_package
from fly.ap.ui.actions import Action, ActionDisabledError
from fly.ap.ui.canvas import EditorPainters
from fly.ap.ui.dialogs import run_standard_message_box
from fly.ap.menus import OwnedMenus
from fly.ap.signals import track_connection
from fly.ap.qtsafe_api import qt_list
```

The other facades are `fontlabapp.ui.panels`, `.widgets`, `.windows`,
`fontlabapp.ui`, `fontlabapp.shortcuts` and `fontlabapp.qtsafe_api`. Accessing
native objects still requires FontLab. The legacy `fontlabapp.actions` package
attribute remains the live host action tree; the facade lives at
`fontlabapp.ui.actions`. The Qt helper facade uses `qtsafe_api` so its path
cannot differ from the existing lazy `fontlabapp.Qt` name only by case.

Case Coverage provides the original four report controls, complete detached
case diagnostics and an explicit existing-view chooser when inactive views are
ambiguous. GlyphData metadata is supplied by the Scriptmix caller. Exact native
text-block binding and proof usability remain unqualified; a capability refusal
is not native acceptance.

## UI and drawing

`FontLab()` or `Application.control` reads fonts, glyphs, metrics and live views; it also exposes native open/new/save/close and tool calls. Tool results and errors retain their JSON form. Raw wrapper reads can produce different Python objects; compare native IDs. `output()` reads Output without clearing it.

`create_panel`, `create_dialog` and `create_widget` in `fontlabapp.qt.widgets` build owned UI under MainWindow. Keep handles alive; close them when finished, and retry Close if it returns False or raises. Context exit removes owned controls and overlays. It preserves user views and fonts. Failed factory cleanup exposes both errors and its exact recovery owner. Floating docks and plugin tools request priority. See [window recovery](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/owned_windows.md) for six standalone experiments; native acceptance remains separate.

`fontlabapp.qt.views.Drawing` paints one widget. Glyph overlays accept pixel or canvas coordinates; canvas coordinates are not implicit glyph-local coordinates. `fontlabapp.qt.painting.editor.EditorPainters` registers after-native-layer callbacks across visible glyph windows, with affine mapping and active/inactive layer filters. Before-native-layer painting is refused. `fontlabapp.qt.menus.OwnedMenus` owns actions and tool windows; removal inside its own connected slots is deferred until dispatch returns. Other slots must queue their own teardown. `_defer(fn, first=True)` queues prerequisite cleanup before pending teardown.

`fontlabapp.qt.safe.qt_list` converts widget lists with cyclic GC disabled on the GUI thread. `fontlabapp.qt.safe.main_window` raises `MainWindowNotFound`. `fontlabapp.qt.dialogs` executes owned input/file/message dialogs and releases them on exit. Caller adapters retain button, conversion and cancel policy. The extracted painter/menu/dialog workflows still need native acceptance. Offline tests do not establish PythonQt safety.

`fontlabapp.qt.dialogs.run_standard_message_box(qt, parent, title, text, icon, buttons, default_button=None)` runs an owned priority dialog with static warning/question semantics. Pass `"Warning"` or `"Question"` for the icon; the title and primary text stay separate. It preserves standard-button results, explicit No defaults and automatic defaults, and deletes the box on every exit.

`fontlabapp.fontui` also holds the editors for FontParts-style fonts: `font_info_editor(font, parent=None, on_apply=None)`, `groups_editor(font, parent=None, on_apply=None)`, `kerning_editor(font, parent=None, on_apply=None)`, `transform_editor(font, name=None, parent=None, on_change=None)` (a detached affine glyph transform), `batch_panel(recipe, parent=None, on_finish=None, python=None)` (a recipe over source UFOs) and `glyph_sequence(font, parent=None, on_select=None)` (text or slash-separated glyph names). They validate and apply data with Fontport, so install it with `pip install "fontlab-fontlabapp[fontport]"`; without it a factory raises `ImportError` that names the extra. Importing `fontlabapp.fontui` loads neither PythonQt nor an editor module. Batch work runs in a separate Python 3.11+ that has `fontlab-fontport`: pass `python=` or set `FONTLABAPP_BATCH_PYTHON`. [The transform example](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/font_transform.py) connects preview and batch. Fontport has no UI (issue 201); these editors lived in `fontlab_fontport.ui` for one release. Moved editor interaction still needs native acceptance.

[The external native UI example](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/native_ui.py) uses `fontlab-remopy` in
ordinary external Python to create a native panel, modeless dialog and removable
Preview drawing. Install App inside FontLab first; `--typerig` also needs TypeRig
in FontLab. From this source checkout or an extracted sdist, run
`python examples/native_ui.py --seconds 5` with Remopy installed in
the external interpreter. It retains its handles across calls, waits outside the
UI thread and removes only its own resources in `finally`. The example retains
its [Fontlab Ltd proprietary licence](assets/LICENSE-native-ui); it is included
in the sdist, separate from the installed App runtime. Native requalification
against the current combined cohort remains pending.

See [drawing](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/drawing.py), [font browser](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/font_browser.py), [features](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/font_features.py), [native smoke](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/native_smoke.py), [Text Holder](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/text_holder.md), [Find Files](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/find_files.md), [Character Map](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/character_map.md), [Raise Ascender](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/raise_ascender.md) and [kerning proofs](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/kerning_proofs.md).

## Module map

The implementation is grouped by domain under `fontlabapp`:

| Package | Responsibility |
| --- | --- |
| `core` | Application context, host access, guards, histories, signals, completion, utilities and hotkeys |
| `qt` | Owned widgets, painting, events, layouts, tables, trees, calendars, images, search and completion |
| `glyphs` | Creation, copies, names, catalog, trees, Unicode, coverage and selection |
| `proof` | Reports, inspectors, proof tabs, numeric worksheets and text tools |
| `fonts` | Font information, style names and revision comparison |
| `masters` | Inspection, angles, switching, interpolation, layers, backgrounds and text comparison |
| `components` | Inspection, creation, writers, recipes and graph views |
| `anchors` | Inspection, writers, copying, coordinates, duplicate and cross-font tools |
| `contours` | Geometry, transforms, nodes, selection, diagnostics, SVG commands and point counts |
| `metrics` | Advance editing, sidebearings, worksheets, offsets, vertical metrics and alignment zones |
| `kerning` | Identity, batch editing, groups, symmetry, persistence and proof text |
| `guides` | Inspection, records, rewriting, perpendicular guides and editing |
| `features` | Feature code, class cleanup and category XML |
| `hints` | PostScript hint helpers |
| `fontui` | Browsers, editors, feature staging, designspace display and sequence canvas, including the editors moved here from Fontport in 1.2.0 |
| `plugmix` | Native reporter, filter, palette, tool and General plugins with their menu install (see [Plugmix](plugmix.md#plugmix)) |
| `objects`, `ui`, `menus`, `shortcuts`, `signals`, `qtsafe_api` | Additive lazy facades over the domain modules (see the [API map](guides/api-map.md)) |

Feature packages keep host-free entry points in `model.py`; native dialogs and
views live beside them in `ui.py`, `views.py`, or other role-specific modules.
Import these modules directly in new code, for example:

```python
from fly.ap.qt.safe import qt_list
from fly.ap.glyphs.names import model as names
from fly.ap.masters.inspect import model as masters
```

The package root contains only `__init__.py`, `_legacy.py` and domain package
directories. Proof words and kerning texts are packaged in
`proof/random_proof_words.json` and `kerning/kerning_proof_texts.json`.
Tests, examples and captured shim output stay in their existing directories.

### Migration from flat module names (issue 205)

All 382 reviewed old module names remain importable through `fontlabapp._legacy`. Old imports such as
`fontlabapp.qtsafe`, `from fontlabapp import qtsafe`, `fly.ap.qtsafe` and
`importlib.import_module("fontlabapp.qtsafe")` resolve to the same module object
as `fontlabapp.qt.safe`. Existing monkeypatch targets therefore affect the
canonical implementation. New code should use the new domain paths.

The six old names `anchors`, `components`, `guides`, `hints`, `masters` and
`proof` also name domain packages. Their packages lazily expose the moved
implementation's attributes and forward model writes and deletions, including
private monkeypatch targets and patch undo. Each model is a separate normal
module with its canonical name, file and import metadata. The packages retain
their own children, metadata and resource access.
No child implementation or PythonQt module is loaded just by importing a
domain package. Root public exports remain in place; `fontlabapp.fontui` also
received the Fontport editors and active-font feature helpers in 1.2.0.
`application`, `hotkey` and `utils`, including their old child module names,
are aliases under `core`.

The Vanilla tombstone is importable for alias identity, but requesting
`VanillaSession` still raises its Glyport migration error and imports no peer.

The retained stdlib-only [migration tool](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/tools/restructure.py) and
[reviewed mapping](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/tools/fontlabapp-mapping.json) document the historical
one-off migration that produced this layout. They are migration evidence,
not a maintenance command to rerun on the current source tree.

## Moved in 1.2.0

App never imports Glyport and imports Fontport only inside `fontlabapp.fontui`,
behind the `fontport` extra. FontLab editors and active-font feature helpers
belong in App. Fontport owns
DesignSpace/UFO/fontParts and its FontLab backend. Install
`fontlab-fontlabapp[fontport]` for these editors; native operations still need
FontLab's PythonQt and existing event loop.

| Old | Current home | Compatibility |
| --- | --- | --- |
| `fontlabapp.vanilla.VanillaSession` / `fontlabapp.core.legacy.vanilla.VanillaSession` | `fontlab_glyport.ui.session.VanillaSession` | Session access/from-import raises `ImportError`; module imports remain available |
| `fontlab_fontport.ui` factories/modules | `fontlabapp.fontui` matching names | Old access raises `ImportError` with the new home |
| `fontlab_fontport.feature_blocks` | `fontlabapp.fontui.feature_blocks` | Deprecated lazy forwarder; Fontport's `fontlab` extra supplies App |
| `fontlabapp.core.scripting.read_feature_blocks`, `fontlabapp.core.scripting.write_feature_blocks` | `fontlabapp.fontui.feature_blocks` | Restored lazy function wrappers |
| extras `[fontedit]`, `[fontsequence]` | `[fontport]` | Install the current extra |
| `fontlabapp._qtsafe` | `fontlabapp.qt.safe` | Old import raises `ModuleNotFoundError` |
| text match on "main window not found" | `fontlabapp.qt.safe.MainWindowNotFound` | Same text and `RuntimeError` base |

Example: `from fontlab_fontport.ui import kerning_editor` becomes `from fly.ap.fontui import kerning_editor`; `import fontlab_fontport.ui.kerning` becomes `import fly.ap.fontui.kerning`.

The lazy factories on `fontlabapp.fontui` preserve their signatures:

| Factory | Purpose |
| --- | --- |
| `font_info_editor(font, parent=None, on_apply=None)` | Stage font information |
| `groups_editor(font, parent=None, on_apply=None)` | Edit groups |
| `kerning_editor(font, parent=None, on_apply=None)` | Inspect/edit kerning |
| `transform_editor(font, name=None, parent=None, on_change=None)` | Preview affine glyph transforms |
| `batch_panel(recipe, parent=None, on_finish=None, python=None)` | Run a UFO recipe in a child interpreter |
| `glyph_sequence(font, parent=None, on_select=None)` | Preview placed glyph sequences |

Importing the facade loads neither Qt nor Fontport. Call a factory inside
FontLab, retain the handle, and call `close()` when finished. Batch requires an
installed Python 3.11+ with Fontport; pass `python=` or set
`FONTLABAPP_BATCH_PYTHON`. See [the transform example](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/examples/font_transform.py).
`fontui.feature_blocks.read_feature_blocks(package)` reads ordered VFJ source;
`write_feature_blocks(package, expected, updated, references=..., undo_name=...)`
checks the active font, source snapshot and glyph references, restores the master,
and returns `{"changed": 0 or 1}`. Unexpected host failures can leave partial changes.

## Demo scripts

`Scripts/<Category>/<Tool> Demo.py` holds small GUI demos of the App modules, one menu entry each (146 in 15 categories). `install.vfpy` copies them into FontLab's Scripts menu; the `Demo.py` suffix keeps them apart from Fly's Scriptmix scripts when both are installed. Demos import App through `fly.ap` and keep native imports lazy inside `main()`. They write nothing by themselves: no font, selection, history, preference, Output or clipboard, and no menu action is triggered. The exceptions start with your own click: the Copy buttons of Glyph Map and Common Glyphs write the clipboard; Proof Tabs, Kerning Proofs and Text Filter open a text tab only after you confirm or tick a box; Image Viewer's Print can write a PDF to a path you pick; and Text Holder, Text Filter and Image Viewer keep files in fixed `fontlabapp-demos/<demo>` folders under the system temp directory. Each script's Safety paragraph gives the details. `tests/test_demo_scripts.py` checks every file's layout, header and Fly imports by AST; `tests/_demo_support.py` runs a demo offline under stubbed natives. Four demos show core features in use rather than by name: Shim Generator (`core.shimgen`), Native Tabs (`core.native_tabs`), History Preflight (`core.history`) and Owned Lifetime (`core.completion` and the `fontlabapp.ui` factories); the last one adds a small panel to the main window (it may float) and removes it on close. Native FontLab acceptance of the demos is pending. `tests/test_demo_scripts_coverage.py` fails when a `fontlabapp.<domain>.<feature>` module has no demo naming it.

Named but not run, and why. The coverage test counts a module that a demo names, so some are named or summarised without running, for these reasons:

- `components.panel`, `contours.panel`, `anchors.panel` and `guides.rewrite` hold the writer panels of the component, contour, anchor and guide scripts, and `contours.copy` and `anchors.edit` copy contours and run point transactions. Their buttons change glyphs, so Component Writers, Contour Panels, Anchor Plans and Guide Plans compute the plans on made-up data and only name the panels.
- `core.hotkey`: its macOS `HotkeyManager` creates a session-wide Quartz event tap and needs the Accessibility permission, and on Windows it raises `NotImplementedError`. A demo would register global hotkeys, so Signals And Hotkeys only reports whether the backend can load.
- `core.legacy`: `examples` launches relocated scripts with `runpy`, and `vanilla` is a tombstone that raises `ImportError` naming Glyport. Core Utilities shows their summaries.
- `fontlabapp.ui.actions`, `canvas`, `dialogs`, `panels`, `widgets` and `windows` re-export objects of `qt` and `core`. Owned Lifetime runs `create_widget`, `create_panel` and `create_dialog` through that facade; the rest need live native objects or act on FontLab (`actions` triggers menu items, `canvas` registers painters on the glyph editor, `windows` wraps native glyph and preview windows), so Toolkit Reference lists their `__all__` only.

Six demos open the same window as a Scriptmix tool, so with both installed, running one closes the other: Glyph Map and Character Map, Glyph Tree and Glyph Metadata Tree, Component Graph (App) and Component Graph (Scriptmix), Spacing Offset and Sidebearing Offset Preview, Find Files and Find Font Files, Image Viewer and Reference Image Viewer.

- Anchors: Anchor Cleanup, Anchor Plans, Anchor Rings, Anchors Inspect
- Components: Component Graph, Component Recipes, Component Writers, Components Inspect
- Contours: Contour Math, Contour Panels, Contour Plans, Contour Reports, Contour Samples
- Features: Feature Categories, Feature Classes, Feature Code, Features Editor
- Font Editors (Fontport extra): Batch Panel, Designspace Panel, Font Browser, Font Info Editor, FontParts Features Editor, FontParts Kerning Editor, Fontui Helpers, Glyph Browser, Glyph Sequence, Groups Editor, Transform Editor
- Font Info: Font Info Panel, Revisions, Style Names
- Guides: Guide Plans, Postscript Hints
- Kerning: Kerning Batch, Kerning Cutoff, Kerning Editor, Kerning Group Proof, Kerning Identity, Kerning Inspect, Kerning Persistence, Kerning Proofs, Kerning Selection, Kerning Symmetry
- Masters: Background Samples, History Preflight, Interpolation Blend, Italic Angles, Layers Samples, Master Reports, Master Switcher, Master Text, Masters Inspect
- Metrics: Alignment Zones, Canvas RSB, Master Writer, Metrics Panel, Spacing Offset, Spacing Worksheet, Tabular Width, Vertical Metrics
- Names: Case Coverage, Common Glyphs, Editable Glyph Tree, Glyph Calendar, Glyph Catalog, Glyph Creation Explained, Glyph Map, Glyph Name Entry, Glyph Names Report, Glyph Tree
- Objects (FontLab 9.1 or later): Copy Selection As JSON, Edit JSON Before Paste, Export Glyphs To JSON File, Import Glyphs From JSON File, Object JSON, Paste JSON Glyphs, Paste JSON Shapes Into Layer
- Proof: Extrema Proof, Native Tabs, Numeric Worksheets, Proof Painters, Proof Tabs, Text Filter, Text Holder
- Reports: Font Reports, JSON Report
- Utilities: Application Info, Core Utilities, Host Menus, Shim Generator, Signals And Hotkeys
- Widgets: Find Files, Image Viewer, Owned Lifetime, Table Filter, Toolkit Reference, Widget Gallery

## Object JSON (FontLab 9.1)

FontLab 9.1 writes glyphs, layers, elements and contours as object JSON (`"dataType": "com.fontlab.objects"`) and reads that JSON back into detached objects. `fontlabapp.objects.json_data` parses and edits the JSON in plain Python (`Envelope`, `describe`, `rename_glyphs`, `unique_glyph_names`, `filter_layers`, `set_advance_width`) and wraps the native calls (`export`, `decode`, clipboard and file helpers). `paste_glyphs` creates new glyphs through `create_glyphs` (each glyph its own Undo step, the outlines one more), with names made unique; a Unicode value already in the font or earlier in the paste is dropped with a note, and a name that may make FontLab rebuild automatic glyphs is skipped unless `allow_rebuild=True`. If the write stops part way, the scripts report what exists and point to Edit > Undo; `paste_shapes` adds shapes or contours to one layer as one Undo step. `decode` always hands FontLab a `QByteArray`: Python `bytes` crash FontLab 9.1.9812. On FontLab 9.0 the Objects scripts say they need 9.1 and change nothing.
