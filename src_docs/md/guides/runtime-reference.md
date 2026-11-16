---
this_file: src_docs/md/guides/runtime-reference.md
---

# FontLab application utilities

`fontlab-fontlabapp` provides the `fontlabapp` package: shared FontLab application, UI, drawing, reporting and guarded editing helpers. It supplies reusable mechanics for Fly, Fontport, Glyport and FontLab scripts. Python 3.11 arm64 is the host target. The package declares Python >=3.11 and requires fontlab-python-pens>=1.0.0. Fontport remains optional through the fontport extra.

The host-free `smallcap_consistency` engine reports exporting case counts, missing and orphan smallcaps, legacy capital/lowercase coverage and two-sided kerning-group differences. The `legacy_lowercase_without_smallcaps` section independently requires an exporting `.sc` glyph even when modern `.smcp` coverage passes. `smallcap_capture.current_report()` lazily captures the current font and master within a shared three-second budget. Export scope is explicitly the `public.skipExportGlyphs` compatibility policy; unknown mappings and ambiguous groups are disclosed. Native qualification remains pending.

Pure utility modules load outside FontLab. Native operations require FontLab's `fontlab`, `FL`, `fontgate`, `fontpr` and PythonQt APIs as used by each operation. Native modules and panels load on demand. General UI belongs here; FontParts/UFO adapters belong in Fontport; Glyphs.app compatibility belongs in Glyport. App never imports Glyport. Optional Fontport imports are confined to `fontui`;
base App still installs without Fontport. Scriptmix scripts and App's own `Scripts/` access App through `fly.ap`.

## API map

The [module and domain map](api-map.md) lists every App module, its public
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

## Original Node Duplicator actions

`node_duplicator_native.duplicate_selected_nodes(mode)` is the guarded immediate
entry point. Choose mode `"current"`, `"all"` or `"handles"` for the three source policies. Current
and handles operate on the first selected layer. All broadcasts its selected
on-curve indices to every stored foreground layer of each selected parent
occurrence, retaining duplicate layer names and repeated parents. Handles adds
two fresh coincident controls and a copied curve endpoint. The separate Scriptmix
Node Duplicator panel retains its per-glyph reference/preview behavior.

Copies restore named native metadata and fractional positions; existing node
and captured layer/shape metadata are checked. Shared owners, automatic
dependants, hinted topology and unrepresentable control cases are refused.
Queue ids are disclosed without clearing them. A partial failure carries exact
owned recovery handles and whether its history notification returned; this does
not prove actual Undo/Redo or saved-font preservation. Do not blindly retry it.
The full native/four-font/window-priority/lifetime workflow still needs acceptance.

## Install

Use Python 3.11 arm64. The test extra supplies pytest, Markdown/PyMdown, ufoLib2, fontParts, fontTools and PySide6-Essentials. PySide6 is an offline test binding; it does not replace FontLab's PythonQt.

The full suite also needs **fontlab-fly installed with its target packages**. Adding Fly's source directory to PYTHONPATH alone is insufficient. The commands under Testing install the local App, Fontport and Glyport checkouts with their dependencies into a prepared virtual environment, and Fly with `--no-deps`: Fly's own target packages (Echopy, PythonQtSide) are not published on a package index. Sibling checkouts must exist at `../fontlab-fly`, `../fontlab-fontport` and `../fontlab-glyport`.

Editable installation into FontLab is owner-managed. Do not install or uninstall packages in FontLab's Python site-packages from a development or test session. Use a reviewed installed artifact and verify its import origin for native tests. This branch is development source; a historical tag or candidate floor does not prove that its current API is available from a package index.

Optional extras:

| Extra | Purpose |
| --- | --- |
| `markdown` | Python-Markdown and PyMdown conversion |
| `hotkeys` | macOS Quartz hooks; needs existing Accessibility permission |
| `unicode` | Extended Unicode data through unicodedata2 |
| `fontui` | fontTools for outline and browser helpers |
| `fontport` | `fontlab-fontport` and its fontParts/UFO stack, which the six FontParts editors and feature helpers in `fontlabapp.fontui` need |

Windows global hotkeys are not implemented. macOS global capture remains unverified. No feature compiler is supplied.

## Use inside FontLab

Read application state without opening or saving PrefLib:

```python
from fly.ap import Application
app = Application(with_ui=True, with_preflib=False)
print(app.versions.app_version)
print(app.control.current_font())
```

`fontlabapp.app` creates the legacy context lazily. Explicit `Application()` initializes UI and PrefLib by default. PrefLib preserves attribute dictionaries and JSON; malformed or non-object JSON fails before saving.

Scripts use the Fly namespace. Keep the module import form:

```python
import fly.ap.core.scripting as scripting
import fly.ap.core.history.glyphs as history

package = scripting.current_package()
print(scripting.font_id(package))  # fontpr uses fgId, not package.id
```

Outside FontLab, import a pure submodule directly:

```python
from fly.ap.core.utils import deepmerge, slugify
from fly.ap.contours.affine import apply, IDENTITY
print(apply(IDENTITY, 20, 30))
```

Real subpackages and legacy aliases resolve before native API names, so `from fly.ap import core` also works outside FontLab. Prefer explicit domain paths in new code. Outside FontLab, unknown names raise `AttributeError` on attribute access or `ImportError` on from-import. Explicit native names still raise a host-required `RuntimeError` outside FontLab.

Read and trigger native menus with `fontlabapp.core.host`:

```python
from fly.ap.core import host
host.menu.font.find("kern")
host.panels.preview.show()
host.menu.view.measurements.tension.set_checked(True)
```

Lookups resolve current QAction objects after menu rebuilds. Reading an attribute, `dir` or `repr` does not trigger an action. Disabled actions raise `ActionDisabledError`. Font Map has no exposed panel state.

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
its [Fontlab Ltd proprietary licence](../assets/LICENSE-native-ui); it is included
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
| `plugmix` | Native reporter, filter, palette, tool and General plugins with their menu install (see [Plugmix](#plugmix)) |
| `objects`, `ui`, `menus`, `shortcuts`, `signals`, `qtsafe_api` | Additive lazy facades over the domain modules (see the [API map](api-map.md)) |

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

## Plugmix

`fontlabapp.plugmix` adds native FontLab 9 plugins: reporter overlays, an
undoable filter, a dockable palette, a native tool and a General menu command.
It uses PythonQt and native per-canvas painters when available, with
`fontlabapp.qt.painting.editor.EditorPainters` on older builds. It imports no
PySide2 and no Glyphs emulation. Importing it does not need FontLab.

Install it once per FontLab session from your own `initScript.py`:

Before startup, separately install
[Fly 1.3.0 or later and its matching providers](https://github.com/fontlabcom/fontlab-fly#install)
in the same interpreter; App's source installer does not supply or check Fly.

```python
try:
    from fly.ap.plugins import install; install()
except Exception as error: print(f"Plugmix startup: {error}")
```

The Scripts in `fontlab-python-plugmix` (`Install Plugmix Menu`, `Duplicate
Anchor Rings`) call the same `install()`. It appends a View > Reporters submenu
with one checkable action per reporter, a separator and `Hide All` (turns every
reporter off), adds `Plugmix: Delete Small
Paths…` to the Glyph menu, `Plugmix: Step and Repeat Panel` and
`Plugmix: Tool Smart Select` to the Window menu, and `Plugmix: Zoom to
Selection` to the View menu. Choices are saved in
`~/Library/Application Support/FontLab/FontLab 9/Data/fontlab-plugmix.json`
(`enabled`, `enabled_filters`, `enabled_palettes`, `enabled_tools`,
`enabled_general`, last-used `params`). `install(config_dir=...)` selects
another directory. `fontlabapp.plugmix.boot.uninstall()` removes actions,
overlays and panels and keeps the saved choices. Filters, tools and General
plugins start enabled; palettes start hidden. No font data is written.

| Kind | Plugin | Behaviour |
| --- | --- | --- |
| Filter | Delete Small Paths | Deletes closed contours whose flattened path or bounds area is below the threshold (default 400 units²) in selected glyphs of the current master, in one geometry Undo step. Skips shared or transformed outlines and automatic layers. |
| Palette | Step and Repeat | Duplicates selected contours of the active glyph `count` more times, each shifted by another (dx, dy), in one geometry Undo step. Refuses shared or transformed outlines and two zero offsets. |
| Tool | Smart Select | Drag a rectangle to select whole contours touched by any node; Shift toggles. Selection only; it never changes outlines. |
| General | Zoom to Selection | Fits the active glyph's selected nodes in the canvas with a margin. |

Native Tool activation, drag mapping, overlay lifetime, General actions and
font events were verified in FontLab 9. Shortcut handling and keyboard cursor
mapping were later corrected from native findings and still need an in-app
recheck. The palette refresh key reads the glyph modification timestamp and
node selection; confirm that edits outside Plugmix advance that timestamp in
your build.

| Reporter | Overlay |
| --- | --- |
| Duplicate Anchor Rings | Red/yellow rings for every anchor pair less than one unit apart |
| Node Indexes | Contour index beside every node |
| Selected Node Coordinates | Coordinates beside selected nodes |
| Two Point Distance | Segment, length and angle for exactly two selected nodes |
| Off-curve Handles Outside Bounds | Handles beyond the on-curve bounding rectangle |
| Center Lines | Advance/2, x-height/2 and cap-height/2 lines |
| Vertical Metrics | Labelled ascender, descender, x-height, cap-height and baseline |
| Angled Handles | Rings on handles off the horizontal, vertical and italic axes |
| Crosshair | Long guides through selected nodes; no mouse tracking |
| Tops and Bottoms | Rings and y labels at the highest and lowest on-curves |
| Segment Length | Straight and flattened curve lengths |
| Glyph Focus | Shade outside the advance box between descender and ascender |
| Emphasise Selected Handles | Accent lines and rings for handles next to selected nodes |
| Anchor Cloud | Names and positions of the current glyph's anchors (local anchors only) |
| RSB Line | Advance boundary with RSB and LSB labels |
| Unitizer | Vertical grid at UPM / 18 |
| Nodes Close to Zones | Rings on on-curves near zone edges or metric heights |
| Imprecise Italic Angle | Straight segments within 2° of the slant but not on it |
| Smooth Node Angles | Handle-angle mismatch and length ratio at smooth nodes |
| Node Count | Total on- and off-curve nodes; components excluded |
| All Angles | Angle of each straight segment from vertical, mod 180°; components excluded |
| Smart Plumblines | Centre lines through each contour's and the selection's extents; components excluded |
| Show Stems | Rings and span widths along a scan line at half x-height; components excluded |
| Speed Punk | Colour-ramped curvature comb; components excluded |
| Show Rotated | Outline turned 180° about its bounds centre; components excluded |
| Blindfold | Opaque blocks hide the strip from 70 units under the descender up to the baseline, and everything from x-height up to 70 units over the ascender (`band = "cap_height"` for cap height); the band between baseline and that height stays visible |
| Show Label Color | Bar in the glyph's mark colour under the descender (`placement` baseline or body), slanted by the italic angle; layer marks are not distinguished |
| Show Glyphs In Label Color | Glyph and component outlines filled in the mark colour, counters open |
| Show Character | The glyph's first Unicode as 100 px text above the glyph; hidden below 20% zoom; no base-name lookup |
| Rekha Viewer | Head-line bar for Devanagari, Bengali and Gurmukhi letters, moved by `rekha` and `rekha_stop` anchors; suffixed or interrupted anchors are not supported |
| Show Export Status | Red cross over the body of a glyph that is set not to export |
| Show Background | Outlines of the glyph's background layer filled in pale blue (alpha 0.3), counters open; background components are not shown |
| Color Toner | Each component filled in translucent black (`darken = 0.15`, wrapped into 0..1) so composed parts stand out from drawn outlines |
| Show Global Glyph | Contours of a helper glyph named `_global` behind every other glyph: closed paths orange outline with faint fill, open paths blue outline with faint fill; its components are not shown and it is not drawn on itself |
| Show Siblings | Look-alike Latin letters (c/e/o, b/p, d/q/u, h/l/n/r/a) filled in green behind the glyph, fainter in larger groups; Latin groups only |
| Show Kerning Group Reference | Members of the glyph's left kerning class drawn on top of each other as small (0.2) teal silhouettes 150 units left of the glyph, and of its right class 150 units right of it, baseline at half x-height; opacity is 0.8 divided by the class size (floor 0.04), so crowded classes read denser. Left-to-right text only. Very large classes are truncated: at most 32 glyphs are requested, alternating left and right |
| Kern Indicator | Displayed kerning of the pairs touching the glyph, above each junction (orange positive, blue negative); shown only between 3% and 90% zoom |
| Show Interpolation | For each other compatible master, the glyph blended halfway (`factor = 0.5`) node by node between the shown layer and that master, filled in dark magenta (alpha 0.25), counters open; components are not drawn (neither the shown layer's nor the masters'); no instances, anchors or recentering, and masters with the same coordinates are skipped |
| Stem Thickness | Wherever the mouse is (no proximity limit), a line across the outline from the outline point nearest it, perpendicular to it, to the nearer crossing more than 1 unit away, labelled with its rounded length; nothing at a corner where the ray runs along the outline; own contours only, no guide command or modifier key |

Center Lines, Vertical Metrics, Crosshair, Tops and Bottoms, RSB Line,
Unitizer, Node Count, Smart Plumblines, Show Stems, Speed Punk, Show Rotated,
Show Label Color, Show Glyphs In Label Color, Show Character, Rekha Viewer,
Show Background, Color Toner, Show Global Glyph, Show Siblings, Show Kerning
Group Reference and Show Interpolation draw under the native glyph layer when native
canvas painters are available; the rest draw over it, and on older builds all
draw over the canvas.
The original seven reporters, native canvas drawing and all 18 pre-revision
reporters were checked in FontLab 9; Glyph Focus and the revised slant and unit
grid have offline coverage only. Node Count, All Angles, Smart Plumblines, Show
Stems, Speed Punk, Show Rotated, Blindfold, Show Label Color, Show Glyphs In
Label Color, Show Character, Rekha Viewer, Show Export Status, Show Background,
Color Toner, Show Global Glyph, Show Siblings, Show Kerning Group Reference,
Kern Indicator, Show Interpolation and Stem Thickness have offline test coverage
only.

Write a reporter by subclassing `fontlabapp.plugmix.Reporter` with a unique
`name`, a `title` and a pure `compute(snapshot)` that returns `Mark` objects
(`ring`, `line`, `polyline`, `polygon`, `text`) in glyph units; pixel sizes are
view pixels. Set `layer = "background"` to paint under the glyph layer.
An error raised by `compute` or `requested_glyphs` goes to the error sink
once per reporter and message until Plugmix is uninstalled. Every snapshot also carries `identity` (name, Unicodes, raw mark, mark RGB,
export flag) and `view.px_per_unit`; either is None when it cannot be read,
and the read error goes to the plugin error sink once. Mark RGB uses HSL lightness
0.65, so it differs slightly from FontLab's flag swatches (inferred, unverified
natively). Offline coverage only.
Opt-in class flags add costlier data: `needs_components` gives `components`
(base name, transform and decomposed base contours, nested up to 8 levels),
`needs_background` gives `background` (the mask's contours, `()` when empty,
None when there is none), and `needs_masters` gives `masters` (each master's
contours, anchors, advance and a `compatible` flag that compares contour
count, node count per contour and on/off-curve pattern with the shown layer,
ignoring components and open/closed state). Components and masters are cached
per glyph revision and shared by all reporters; components also re-check
their base glyphs. Master outlines may lag until the foreground glyph's
`lastModified` moves, which is unverified natively. The background is read on
every paint. An empty component layer means the master that owns the shown
layer. Metrics also come from that master. Zones and the italic angle need a
master switch to read, so when the shown layer belongs to another master the
zones are empty and the italic slant is the current master's.
Skipped components and failed reads go to the error sink once.
Offline coverage only.
`needs_kerning` gives `kerning_groups` (the classes used when the glyph is a
pair's first member, `left`, and second member, `right`, with their
members), read on every paint because a class edit may not move the glyph's
timestamp. Override `requested_glyphs(identity, kerning_groups=None)` to name up to 32 other
glyphs; `others` maps each one that exists to its own unselected contours
(components skipped), cached per requested glyph's revision. Both use the
master that owns the shown layer. `needs_neighbours` gives
`view.neighbours`: the previous and next glyph on the same line as
`(name, kerning)`, kerning in font units as displayed (0 when kerning
processing is off). Which glyph stores a pair's kerning is inferred,
unverified natively. Neighbours need the native canvas painter backend; with
EditorPainters, or when the view scale is unusable, they are None.
Offline coverage only.
`needs_mouse` gives `view.mouse`, the cursor in the glyph's own units
(`canvas.mousePosition()` mapped back through the glyph and text-block
transforms), or None when the map is not invertible. While any enabled
reporter asks for it, one event filter watches the active glyph window and
flushes (`updateScreenRect` plus `updateViewport`) at most once per 16 ms after
mouse moves, ending with a flush after the last move. The filter goes when the last such reporter is disabled, when the
active canvas changes or closes, and on `uninstall()`. Only the watched canvas
gets a mouse; with EditorPainters it is None. Whether moves reach the filter
under every tool is unverified natively.
Offline coverage only.
Third-party packages publish plugin classes in the `fontlabapp.plugmix`
entry-point group.

## Additional read-only reports

`kerning_persistence_api()` / `kerning_persistence_dialog_type()` audit explicit current/all-master kerning, retaining zero and exact values. The measured FontLab 9.0.9784 VFJ load check flags values outside ±2×UPM; it does not guarantee every aspect of persistence. The audit filters rows and changes no font selection.

`revision_compare_api()` / `revision_compare_dialog_type()` compare two explicitly chosen open fonts and masters: glyph/master/layer presence, advance, ordered raw contour geometry, anchors and components. Raw node flags include selection and appear separately. This reports named fields, not complete semantic font equality. Both modeless panels validate sources before displaying results and own Close/ signal cleanup. This isolated milestone still needs built-artifact/native release acceptance; the broader issue111 work remains open.

Modeless panels opened with `scripting.show_script_dialog` keep their existing window type and controls and request `WindowStaysOnTopHint`, matching TypeRig panel priority. Twelve panel constructors also set priority before fallible setup so their retained error windows do not bypass it. An existing panel that refuses to close keeps its flags. Independently launched panels and modal child dialogs retain their own policies; native stacking acceptance remains pending.

Owned Find Files directory/progress dialogs, Image Viewer file/print/message dialogs, and Same Kerning Groups diagnostics also request this priority. Their existing parents and modal/nonmodal policies remain; native child stacking and print-panel acceptance remain pending.

Modeless panels opened with `scripting.show_script_dialog` keep their existing window type and controls and request `WindowStaysOnTopHint`, matching TypeRig panel priority. An existing panel that refuses to close keeps its flags. Independently launched panels and modal child dialogs retain their own policies; native stacking acceptance remains pending.

Owned Find Files directory/progress dialogs, Image Viewer file/print/message dialogs, and Same Kerning Groups diagnostics also request this priority. Their existing parents and modal/nonmodal policies remain; native child stacking and print-panel acceptance remain pending.

## Write boundaries and acceptance

History helpers preflight before mutation, initialize history, mutate, stamp, notify once and read back. `retain=` enrolls removed component objects with deep history. Failures after history starts raise `PartialWriteError` with Undo guidance; that guidance is not a guarantee of complete recovery.

Rename, Unicode and geometry edits refuse automatic-layer owners and automatic composite bases; explicit consent can allow supported base edits. Metadata edits refuse automatic-layer owners. Writers disclose queued ids and the possible modification-date changes (FontLab issue 8537); `history.commit` defaults to `settled=False` and always captures the queue once before writing. Its result supports `result["pending_updates"]` and `result["pending_note"]` (empty when no ids). Writers carry both fields to their results; panels append the stored note with `edit_guards.append_note`. Legacy scalar writers can fill a `disclosure` output dictionary or print the disclosure for console use. Use `edit_guards.pending_updates(native: Any = None) -> tuple[int, ...]` before a write and `pending_note(ids: Sequence[int]) -> str` in its status. `require_settled` remains an explicit opt-in refusal. `history.commit`, `glyph_creation.create_glyphs` and the eight App writers that notify directly call `edit_guards.require_history_scope`: with a Glyph window as the active canvas they refuse ("Switch to the Font window first…") unless every owner glyph (matched by font id and glyph name) is in that canvas and no glyph is new (FontLab issue 8573). Glyport and Fontport host notifiers are not guarded yet. Never notify an automatic layer, clear the queue or normalise unrelated dates. Existing-anchor moves to (0, 0) are refused because of a measured Redo defect. Clones must retain raw node flags, names and shape notes.

Font-level master writes use `font_history.commit_masters(package, title, {master: MasterEdit(save, write, read, verify, restore)})`. It refuses off the GUI thread and unless a Font window of the font is active (no Glyph window canvas; text "Activate the Font window before editing font masters."). It calls `checkInitHistoryState(0)` on the package and `mastersContainer()`, writes and reads back each master after `setMaster(name, False)`, restores the original master and sends ONE `notifyChangesApplied(title, [package, container], False)`. The result has `values`, `pending_updates` and `pending_note`. Unlike `history.commit`, a failure before the notification (also an interrupt, which is then re-raised) restores every written master and the original master and notifies nothing: `RolledBackError` (a `ValueError`) when the restore holds, `UnrestoredError` (a `PartialWriteError` with no Undo advice) when it does not or when the notification fails. Callers: `master_metrics.write_master_metrics(package, {master: {field: value}}, title)` for `ascender`, `descender`, `xHeight`, `capsHeight` and `lineGap` (`capHeight` is an alias of `capsHeight`; unknown fields and non-finite values are refused; double read-back tolerance 1e-9), and `zone_native.backend()`, the production `zone_editor.Backend` (Font Info's `convertZonesToGuidelines` + `updateZonesFromGuidelines`; the thread and Font-window guards run before any master switch; empty or repeated names and zero-width rows of the other kind raise `zone_native.RowRefusal`, and `Editor.add` names new rows as FontLab does (`T: 500`, `T: 500.1`); a zone rollback re-creates the zone guides with new ids and says so; a read-back gap after the commit raises `history.unstored_error`; it does not use the held serializer, fl#8554). The Alignment Zones panel stays usable after a `RowRefusal` or `RolledBackError` and locks after a stale source, `UnrestoredError` or a read-back gap. **Known FontLab defect:** after Undo or Redo of such a step, both masters show only the zone guidelines, not the six font-metric guidelines, until `updateFontMetrics()` runs or the font is reopened; the saved file is correct (9.0.9790, fl#8574). `select_glyphs` and `master_switcher.switch` call no `UpdateAll()`: it queued glyph ids and changed nothing visible.

Glyph creation uses `fontpr.set_glyph(create=True)` and checks the created result; existing names are refused before the call. Components for a new glyph travel in its creation data. Adding components to existing layers requires a qualified plain component prototype. Creation can use multiple native steps; do not promise one Undo for the whole workflow. Unmeasured automatic-layer rebuilding stays guarded.

Earlier releases have bounded native receipts in CHANGELOG. Those receipts do not qualify later shared writers or the full migration. Zone serializer ABI/payload preservation remains open; the route-A zone and metrics writers have no native receipt yet. Current text, NUL/IME, printer/OS, cache/history, font preservation and UI lifecycle holds are listed in [TODO](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/TODO.md). Native proof requires installed artifacts in owned FontLab fixtures, exact source hashes, complete state comparison, real controls, Undo/Redo and saved reopening for writers. Source and standalone Qt checks do not qualify native behavior.

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
- Proof: Extrema Proof, Native Tabs, Numeric Worksheets, Proof Painters, Proof Tabs, Text Filter, Text Holder
- Reports: Font Reports, JSON Report
- Utilities: Application Info, Core Utilities, Host Menus, Shim Generator, Signals And Hotkeys
- Widgets: Find Files, Image Viewer, Owned Lifetime, Table Filter, Toolkit Reference, Widget Gallery

## Testing

Run from this repository. Set `FONTLAB_TEST_SCRATCH` to an existing writable directory on your external scratch volume. Use a fresh writable cache and an existing writable TMPDIR there. uv needs network access for packages not cached. Build from reviewed Git history so hatch-vcs supplies the genuine version required by the local Fontport/Glyport dependency floor. Do not reuse a cache containing App metadata from another build.

```sh
: "${FONTLAB_TEST_SCRATCH:?Set FONTLAB_TEST_SCRATCH to your external scratch directory}"
export UV_CACHE_DIR="$FONTLAB_TEST_SCRATCH/app-doc-check-cache"
export TMPDIR="$FONTLAB_TEST_SCRATCH/tmp"
mkdir -p "$UV_CACHE_DIR" "$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
uv venv --python cpython-3.11-macos-aarch64-none "$TMPDIR/app-venv"
uv pip install --python "$TMPDIR/app-venv/bin/python" -e '.[test]'
uv pip install --python "$TMPDIR/app-venv/bin/python" -e ../fontlab-fontport -e ../fontlab-glyport
uv pip install --python "$TMPDIR/app-venv/bin/python" --no-deps -e ../fontlab-fly
"$TMPDIR/app-venv/bin/python" -B -m pytest -q -p no:cacheprovider
```

Install Fontport and Glyport with their dependencies (defcon, fissix, fontpens, glyphsLib); without them two tests fail. The tests of the FontParts editors (`tests/test_ui_*.py`, `tests/test_cov_ui_*.py`) call `pytest.importorskip("fontlab_fontport")`: they skip, not fail, when Fontport is absent, so a plain `./test.sh` run does not exercise them. `./test.sh` installs the sibling Fontport and Glyport checkouts editable and puts the sibling Fly source on PYTHONPATH when they exist, so it runs the whole suite; the test extra itself does not list Fontport.

The plain test-extra environment previously gave 6240 passes and three failures because Fly was missing. `./test.sh` uses `uv run --extra test` with editable sibling Fontport/Glyport when available and sibling Fly on PYTHONPATH; the explicit environment above also verifies an installed Fly. Use the explicit command for the full suite. pytest reads `tests/` and adds `src` to its import path.

At the dated source snapshot, there was no separate `tests_docs/` suite. The current site now has the separate documentation checks described on the development page. With the same exports, run the README migration contract and public-surface/dependency checks:

```sh
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py tests/test_package_boundaries.py tests/test_tombstones.py
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py::test_readme_when_read_then_moved_table_names_every_tombstone
uv run --python cpython-3.11-macos-aarch64-none --no-project --with ruff==0.14.10 ruff check --no-cache --select F821 src tests Scripts
```

The lint command checks undefined names; there is no configured full lint gate. Offline tests cover Python logic and doubles. Standalone Qt uses a different binding. Neither establishes native FontLab acceptance.

## Licence

Licensed under Apache-2.0; all Python sources in `fontlabapp.fontui` also carry Apache-2.0 SPDX identifiers (Issue 204). Bundled third-party code keeps its MIT and BSD-3-Clause notices, and the external native UI example keeps its [proprietary licence](../assets/LICENSE-native-ui), so the distribution expression is `Apache-2.0 AND MIT AND BSD-3-Clause AND LicenseRef-Proprietary`. See [LICENSE](../assets/LICENSE), [NOTICE](../assets/NOTICE) and [MIGRATION.json](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/MIGRATION.json) for source-specific terms and attribution. Retained legacy sources and historical receipts do not grant permission to copy unlicensed third-party bodies into public artifacts.

Raise Ascender reports queued native glyph updates instead of refusing every edit.
FontLab may change those glyphs’ modification dates (issue 8537); the panel retains
that warning even if the edit fails. Source and history-scope checks still apply.
Complete native preservation remains unverified.

Perpendicular Guides discloses queued glyph IDs and FontLab issue 8537’s possible
modification-date changes before writing. A nonempty queue alone does not refuse
the action. Source/history guards remain; native preservation is unverified.

Perpendicular Guides retains ordinary append and finalization failures together
in `fontlabapp.core.history.glyphs.PartialWriteError.errors`. A failure does not imply rollback;
inspect the font and Edit > Undo before another write. Native qualification remains open.

`select_glyphs(add=True)` adds missing glyph names without clearing existing
selection. Already-selected glyphs, including partial duplicate chart-cell
selections, are untouched. If a native addition fails, earlier additions remain
and the original exception propagates. Replacement mode still clears first.

## Planned plugin ownership (Issue 210)

The `fontlabapp.plugmix` APIs above are current Issue 209 source. Issue 210 requests framework, scaffolding, discovery, registration and lifecycle under `fontlabapp.plugins`, with concrete bundles in Plugmix Extensions. Keep existing APIs usable until all callers migrate. Qualify bundle discovery, Reporters palette and View > Reporters, toolbar and Tools > Tool, Window > Panels, and a preservation-safe `initScript.py` installer hook. The target path is not yet a supported current import.

## CurrentGlyph and editing boundaries

A valid FontGate `CurrentGlyph` can be falsey when it has no contours. Glyph identity checks match the font ID and glyph name: `CurrentGlyph().id` can differ from the canvas slot ID for the same glyph. In an active Glyph window, a multi-glyph `notifyChangesApplied` Undo step attaches only to the canvas glyphs; other glyphs can keep the change and newly created glyphs can lack Undo. Shared `edit_guards.require_history_scope` guards refuse unsupported scopes. Close Glyph windows before a `.vfc` save. These native limitations remain distinct from source and standalone Qt test results; the historical consolidation-only CurrentGlyph exception does not waive current preservation or native qualification.
