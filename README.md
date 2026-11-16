---
this_file: README.md
---

User scripts and examples require FontLab Fly 1.3.0 or later in the interpreter
that runs them. Use `fly.ap` for App and explicit domain imports; the aliases
share the canonical provider objects and load only on use. Library internals
retain direct provider imports without a mandatory Fly dependency.

The source installer copies Scripts and writes App's owned startup block, but
does not install or check Fly. Install
[Fly and its matching providers](https://github.com/fontlabcom/fontlab-fly#install)
separately in the same interpreter before running these consumers or relying on
plugin startup. A missing Fly import makes the startup block print
`FontLab plugins startup:` and skip activation.

## Install in FontLab

To install into FontLab 9, open `install.vfpy` from a checkout in FontLab
(double-click it or drop it onto FontLab), then restart FontLab. The file is a
short stub that hands the work to
[fontlab-instamix](https://github.com/fontlabcom/fontlab-python-instamix); if
instamix is not installed yet, the stub installs it from PyPI first. Instamix
installs the package into FontLab's own `site-packages` and records the install
under the extension id `com.fontlab.fontlabapp`.

## UFO and representation inspectors

`fontlabapp.fontui.ufo_roundtrip.show(font, parent=None)` opens an explicit
export/reopen/import inspection in owned temporary staging. It never saves or
closes the borrowed source. Its report distinguishes source/export, saved UFO and
imported-model differences, including interchange losses. Native fonts expose only
the adapter-readable UFO model; native preservation remains unverified.

`fontlabapp.fontui.representation_notifications.show(font, parent=None)` combines
glyph browsing, outline inspection and representation cache observations. It
reports actual scripting-model notifications and cache states. Representation reads
populate caches; external native synchronization remains unverified. Both tools
have paired demonstrations under **Font Editors** and Scriptmix **Font UI Lab**.


Batch UFO Recipe Workbench is available through `fontlabapp.fontui.batch_recipes.show(parent=None, python=None)`. Use the real affine recipe controls without opening a font or geometry preview, then explicitly select UFO sources, an output directory and Python 3.11+ with Fontport. Start writes new outputs; existing files and destinations inside any input UFO are refused. The actual panel shows per-file results, progress and failures. Cancel stops between files and retains completed outputs. Closing transfers an active run to supervision; terminal cleanup and independently reopened outputs are separate observations. Source review, ordinary artifacts and native qualification remain distinct.

Detached Transform Preview is available through `fontlabapp.fontui.detached_transform.show(font, parent=None)`. Run **Font Editors > Detached Transform Preview Demo**. Choose an explicit layer and glyph, then Capture to compare the backend-stored snapshot with an affine result. Refresh reads the same captured font; borrowed caches and pending edits remain untouched. Settings Save creates only a chosen new JSON file, and Show script displays text without executing it. No font Apply/save/export is provided. This workflow is independently source-qualified. Combined-main review, matching ordinary installation and native behavior remain pending.


Feature Source and Proof is available through `fontlabapp.fontui.feature_proof.show(font, parent=None)`. It keeps the ordinary code view, refuses unsupported input before selection loss, and quarantines opaque document changes until explicit Revert. Accepted source Apply refreshes the independent Unicode/kerning sequence once; it does not compile or shape OpenType features. The window captures one borrowed font. External changes retain dirty drafts with a warning; explicit Apply can overwrite newer source. Refresh proof retries only the view. Original paragraph separators are inspect-only. Focused checks confirm exact UFO source preservation through the backend and editor for CR, CRLF, mixed endings and absent final newlines, including untouched siblings; duplicate feature tags are inspect-only. This workflow is source-qualified through independent review and complete controlled Fontport/App/Scriptmix suites. Ordinary artifact and native history/reopen qualification remain pending. Native PythonQt/FontLab, full literal paragraph-separator editing and broader clipboard routes remain unqualified.



## Development status — 2026-11-05

Canonical source inspected for this proposal: `6c48291ca654`. This is a dated source observation, not an installed or native acceptance claim.

Issue 210 separates the plugin core in `src/fontlabapp/plugins` from the concrete Plugmix Extensions bundles. Native qualification remains open.

Complete Issue 211 native probes and four minor fixes with independent regression review; reconcile Issue 207 before integrating over current Issue 208/209/M12 code.

## Repository and development

`src/fontlabapp/` owns domain packages; `Scripts/` holds package demonstrations; `tests/` contains source and offline UI checks; `examples/` holds external/native drivers. The plugin core lives in `src/fontlabapp/plugins/`, with regression tests in `tests/plugmix/`; `fontlabapp.plugmix` is a deprecated compatibility shim.

Use README Testing to prepare arm64 Python 3.11 with App[test], Fontport, Glyport and Fly. Run that interpreter with `python -B -m pytest -q -p no:cacheprovider`. `./test.sh` uses sibling Fontport/Glyport checkouts and Fly source when present; classify missing peers and skips.

Keep runtime, ordinary installed artifacts, native workflows and published documentation as separate acceptance results. Track open checks in [TODO.md](TODO.md), the implementation route in [PLAN.md](PLAN.md), and dated evidence in [CHANGELOG.md](CHANGELOG.md).

Private release-ancestry integration candidate: v0.2.25 and the reviewed issue123 feature source are both ancestors. This source retains held writers, including Italic Angle, whose prerelease remains outside accepted main after the unrelated active-state regression. No writer/native acceptance, canonical promotion or release follows from this private integration; all existing holds remain.

Common Glyphs now reports every open font without requiring a current one. It preserves one-font glyph order, deterministic multi-font intersections, first-font primary character strings and exact trailing name/string spaces. The caller supplies verified GlyphData production names; unknowns and all alternative encodings stay visible. Escaped JSON preserves exact Unicode when Qt normalizes copied text; literal NUL uses a disclosed display escape. Ordinary primary-selection copying can normalize NBSP/line separators. Explicit Copy Characters/Copy Original Report actions stage the exact detached source as literal MIME data using the existing Qt helper. Their native callbacks, OS clipboard handoff and rendering remain unqualified. Its owned report refreshes without clearing Output. The charcoal option is visible, unchecked and unavailable: the full all-font action still needs a supported glyph-only mark/history API (FontLab issue 8564). This partial source milestone does not complete the original workflow or establish native acceptance.

Master Text Comparison restores the original preset/custom workflow, usable-character sanitation, exact master-copy delimiters and owned settings. It stages named glyph/layer symbols in a fresh proof; native model binding, rendering and full preservation remain unqualified. Multiline/paragraph custom input is held explicitly; exact UTF-8 presets retain those scalars.

# FontLab application utilities

`fontlab-fontlabapp` provides the `fontlabapp` package: shared FontLab application, UI, drawing, reporting and guarded editing helpers. It supplies reusable mechanics for Fly, Fontport, Glyport and FontLab scripts. Python 3.11 arm64 is the host target. The package declares Python >=3.11 and requires fontlab-python-pens>=1.0.0. Fontport remains optional through the fontport extra.

The host-free `smallcap_consistency` engine reports exporting case counts, missing and orphan smallcaps, legacy capital/lowercase coverage and two-sided kerning-group differences. The `legacy_lowercase_without_smallcaps` section independently requires an exporting `.sc` glyph even when modern `.smcp` coverage passes. `smallcap_capture.current_report()` lazily captures the current font and master within a shared three-second budget. Export scope is explicitly the `public.skipExportGlyphs` compatibility policy; unknown mappings and ambiguous groups are disclosed. Native qualification remains pending.

Pure utility modules load outside FontLab. Native operations require FontLab's `fontlab`, `FL`, `fontgate`, `fontpr` and PythonQt APIs as used by each operation. Native modules and panels load on demand. General UI belongs here; FontParts/UFO adapters belong in Fontport; Glyphs.app compatibility belongs in Glyport. App never imports Glyport. Optional Fontport imports are confined to `fontui`;
base App still installs without Fontport. Scriptmix scripts and App's own `Scripts/` access App through `fly.ap`.

## Designspace source report (Issue 234 #14)

The Source Comparison view offers **Open designspace…** beside its captured-font
refresh control. External reports identify their file and retain the previous
complete report on cancel or failure. Install the existing `fontport` extra.
The Qt-free `fontlabapp.fontui.designspace_sources` module also supports:

```python
from fly.ap.fontui.designspace_sources import compare, render, refresh
report = compare("Family.designspace")
print(render(report))
# Update a view after a complete read:
refresh(path, view.setPlainText)
```

For an ordinary Python command-line report (with App and Fontport installed):

```sh
python "Scripts/Font Editors/Designspace Source Report Demo.py" Family.designspace
```

`Report` contains ordered sources, axis bounds/maps, design/user locations,
UPM/ascender/descender/xHeight/capHeight/italicAngle, glyph-set differences
relative to source 1, and sorted per-glyph advances/structural diagnostics.
Metrics are raw source units; unset values remain unset. Named source layers
use their glyphs and the UFO's shared font info. Missing glyphs and single-source
reports are not comparable. `refresh(path, set_text)` reads the complete report
before calling the supplied text setter; errors propagate to the caller.

This uses Fontport's FontTools designspace adapter and UFO readers. Continuous
axes and UFO sources are supported; discrete axes, anisotropic locations and
multi-axis mappings are refused. FontTools discards dimensions for undefined
axes during parsing. Compatibility uses App's ordered node types and anchor/
component name sets; it does not certify interpolation or export. No fonts are
written, no Qt is imported and no widget is owned. C5 view wiring, native
PythonQt behavior and ordinary artifact qualification remain open.

## API map

The [module and domain map](src_docs/md/guides/api-map.md) lists every App module, its public
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
| `fontui-shaping` | fontTools and uharfbuzz, which TMetrics uses to shape text; without them it maps characters one to one and says the text is unshaped |

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

`create_panel`, `create_dialog` and `create_widget` in `fontlabapp.qt.widgets` build owned UI under MainWindow. Keep handles alive; close them when finished, and retry Close if it returns False or raises. Context exit removes owned controls and overlays. It preserves user views and fonts. Failed factory cleanup exposes both errors and its exact recovery owner. Floating docks and plugin tools request priority. See [window recovery](examples/owned_windows.md) for six standalone experiments; native acceptance remains separate.

`fontlabapp.qt.views.Drawing` paints one widget. Glyph overlays accept pixel or canvas coordinates; canvas coordinates are not implicit glyph-local coordinates. `fontlabapp.qt.painting.editor.EditorPainters` registers after-native-layer callbacks across visible glyph windows, with affine mapping and active/inactive layer filters. Before-native-layer painting is refused. `fontlabapp.qt.menus.OwnedMenus` owns actions and tool windows; removal inside its own connected slots is deferred until dispatch returns. Other slots must queue their own teardown. `_defer(fn, first=True)` queues prerequisite cleanup before pending teardown.

`fontlabapp.qt.safe.qt_list` converts widget lists with cyclic GC disabled on the GUI thread. `fontlabapp.qt.safe.main_window` raises `MainWindowNotFound`. `fontlabapp.qt.dialogs` executes owned input/file/message dialogs and releases them on exit. Caller adapters retain button, conversion and cancel policy. The extracted painter/menu/dialog workflows still need native acceptance. Offline tests do not establish PythonQt safety.

`fontlabapp.qt.dialogs.run_standard_message_box(qt, parent, title, text, icon, buttons, default_button=None)` runs an owned priority dialog with static warning/question semantics. Pass `"Warning"` or `"Question"` for the icon; the title and primary text stay separate. It preserves standard-button results, explicit No defaults and automatic defaults, and deletes the box on every exit.

`fontlabapp.fontui` also holds the editors for FontParts-style fonts: `font_info_editor(font, parent=None, on_apply=None)`, `groups_editor(font, parent=None, on_apply=None)`, `kerning_editor(font, parent=None, on_apply=None)`, `transform_editor(font, name=None, parent=None, on_change=None, on_invalidate=None)` (a detached affine glyph transform), `batch_panel(recipe, parent=None, on_finish=None, python=None)` (a recipe over source UFOs) and `glyph_sequence(font, parent=None, on_select=None)` (text or slash-separated glyph names). They validate and apply data with Fontport, so install it with `pip install "fontlab-fontlabapp[fontport]"`; without it a factory raises `ImportError` that names the extra. Importing `fontlabapp.fontui` loads neither PythonQt nor an editor module. Batch work runs in a separate Python 3.11+ that has `fontlab-fontport`: pass `python=` or set `FONTLABAPP_BATCH_PYTHON`. [The transform example](examples/font_transform.py) connects preview and batch. Fontport has no UI (issue 201); these editors lived in `fontlab_fontport.ui` for one release. Moved editor interaction still needs native acceptance.

The optional transform `on_invalidate()` callback runs before subsequent update, intensity synchronization, Reset and selected-load work. It is registered after the initial preview, which keeps the existing `on_change` timing. Use it to clear linked proof, not calculate or publish. Callback reentry refuses; ordinary callback errors refuse the attempt, and `BaseException` propagates with the notification fence restored. A cancelled chooser keeps valid proof. Consumers must clear their own validity before fallible view work and check actual publication: `update()` success alone does not establish it. This shared helper is a source candidate; the complete Detached Transform Preview workflow and native qualification remain pending.

[The external native UI example](examples/native_ui.py) uses `fontlab-remopy` in
ordinary external Python to create a native panel, modeless dialog and removable
Preview drawing. Install App inside FontLab first; `--typerig` also needs TypeRig
in FontLab. From this source checkout or an extracted sdist, run
`python examples/native_ui.py --seconds 5` with Remopy installed in
the external interpreter. It retains its handles across calls, waits outside the
UI thread and removes only its own resources in `finally`. The example retains
its [Fontlab Ltd proprietary licence](examples/LICENSE-native-ui); it is included
in the sdist, separate from the installed App runtime. Native requalification
against the current combined cohort remains pending.

See [drawing](examples/drawing.py), [font browser](examples/font_browser.py), [features](examples/font_features.py), [native smoke](examples/native_smoke.py), [Text Holder](examples/text_holder.md), [Find Files](examples/find_files.md), [Character Map](examples/character_map.md), [Raise Ascender](examples/raise_ascender.md) and [kerning proofs](examples/kerning_proofs.md).

## TMetrics and TGlyph windows

`TMetrics.set_text()` uses a successful synchronous refresh from the public
`text_control.textChanged` signal. Observers that change font data or need to
retry a failed refresh after an earlier successful refresh must call `refresh()`
explicitly; `set_text()` does not add a trailing refresh after those observers.

Two modeless windows in `fontlabapp.fontui` follow and edit a FontParts-style
font. Inside FontLab they open on the current font through Fontport, so they
need the `fontport` extra; `fontui-shaping` adds HarfBuzz shaping. FontLab edits
and Undo/Redo refresh both windows within the follow delay. Their own writes are
recognised and do not refresh them twice.

`show_tmetrics(font=None, text=None)` (`fontlabapp.fontui.tmetrics`) sets text
or `/names` with features, direction, script and language. It draws the
shaped rows with metric lines, glyph boxes, sidebearing marks and kerning, and
reads out the selected glyph's advance, LSB and RSB and the pair before it.
Click or Left/Right/Home/End select; double-click opens the glyph in TGlyph.
The LSB, RSB, Width and Kerning fields write on Return. Alt+Left/Right nudges
the RSB and Ctrl+Alt+Left/Right the pair kerning by 1; Shift makes it 10. On
macOS the kerning keys are Control+Option or Command+Option with Left/Right.
A kerning write to a group pair names the group keys in the status line, for
example `Kerning public.kern1.A/public.kern2.V (group pair for A V): -50.`
Marks (GDEF class mark, or a glyph whose own width is 0 when the font has no
glyph classes) get no kern bar. The Master/layer selector targets glyph outlines and metric writes explicitly.
For a non-current native master, kerning display and edits are disabled; make
that master current in FontLab to edit its kerning. Each glyph write uses the
existing named Fontport transaction; native Undo/Redo remains unqualified.
Press Return in the text field to send literal Unicode text to the captured
FontLab Glyph-window block. External text changes refresh the window unless
there is an unsubmitted draft. Named/layer-specific symbol streams stay local.

`show_tglyph(font=None, name=None, layer=None)` (`fontlabapp.fontui.tglyph`)
shows one glyph on an explicit layer: outline, points and handles, start
point, components, anchors and metric lines. Zoom with the wheel, `+`/`-` or
`0` (fit); pan with space-drag or a middle-button drag. Click, Shift-click or
drag a rectangle to select points; drag them, nudge with the arrows (Shift: 10)
or press Delete. `O` toggles selected on/off-curve points while preserving their
coordinates; open endpoints and contours with no remaining on-curve point are
refused. `P` starts the pen tool: the first click places a pending point in
the preview only, the second click writes a two-point open contour, later clicks
add points, clicking the first point closes it, and Escape or a tool switch
discards a pending point. `V` returns to selection. Each gesture writes the
shown layer once. "Follow FontLab current glyph" tracks FontLab's glyph.

The Scriptmix menu tools Metrics > TMetrics Window and Contours > TGlyph Window
open these windows. Known limits:

- Live FontLab round-trip is unverified; offline tests use fakes.
- Optional `host=` injection provides text and follow notifications for tests;
  native operation uses the existing Fontport explicit-layer edit boundary.
- The host write refuses glyphs with several, transformed or hinted shapes,
  and fractional anchors.
- A UFO opened through Fontport cannot write glyphs with anchors (a Fontport bug).
- Each auto-repeated nudge is a separate undo step.
- Before the first zoom or pan, the view refits on each live change.
- Deleting points normalises segments: a cubic curve left with one handle
  becomes a line; a quadratic curve keeps its single off-curve point.

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
| `plugins` | Core contracts, discovery and host lifecycle for reporter, filter, palette, tool and General Extensions |
| `objects`, `ui`, `menus`, `shortcuts`, `signals`, `qtsafe_api` | Additive lazy facades over the domain modules (see the [API map](src_docs/md/guides/api-map.md)) |

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

The retained stdlib-only [migration tool](tools/restructure.py) and
[reviewed mapping](tools/fontlabapp-mapping.json) document the historical
one-off migration that produced this layout. They are migration evidence,
not a maintenance command to rerun on the current source tree.

## Plugmix

Tool snapshots now carry optional immutable package/glyph/layer/owner-master
identity independently of content equality/hash. `Tool.needs_components`
defaults to false; an opted-in Tool receives decomposed components consistently
in its event context and painter. `ToolContext(services)` and its no-argument
`snapshot()` remain compatible. Unknown source identity is `None`, allowing
inspection clients to clear stale overlays without reading native state in
`marks()`. Native behavior of the new inspection Tools remains unqualified.


`fontlabapp.plugins` supplies the FontLab 9 plugin core. The companion Plugmix
Extensions pack supplies reporter overlays, a filter, a palette, a tool and a
General command; no concrete examples are bundled in App.
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

App's `install.vfpy` creates one marked startup block and preserves existing
`initScript.py` bytes. Reinstallation does not duplicate it; App uninstall
removes only that block. This is tested with temporary directories, not an
owner installation.

At launch, the core resolves FontLab's actual user-data folder and scans
`Extensions/reporters`, `filters`, `tools`, `palettes` and `general`. Bundles use
`Name.fontlabReporter` (or the matching kind suffix), with `plugin.json` fields
`id`, `name`, `kind`, `version`, `entry` (`module:Class`) and `min_app_version`.
Version fields use three-part release numbers. Invalid or incompatible bundles
are logged and skipped. Sorted discovery preserves class identity on rescan.
Python source changes require a host restart; rescanning does not reload code.
New menu entries append after Hide All on rescan; restart restores sorted order.
See the companion pack's `Extensions/README.md` for a minimal example.

View > Reporters provides per-reporter toggles and Hide All. Window > Panels >
Reporters opens a nonmodal panel reflecting the same choices. Plugin palettes
use Window > Panels; tools use Tools > Tool and the existing native toolbar
registration seam. FontLab 9 placement, synchronization and toolbar behavior
still require native verification. Plugmix's Show Reporters action opens this
panel; individual reporter launcher scripts are replaced by bundles.

Choices remain in `Data/fontlab-plugmix.json` under FontLab's data root
(`enabled`, `enabled_filters`, `enabled_palettes`, `enabled_tools`,
`enabled_general`, last-used `params`). `install(config_dir=..., extensions_dir=...)`
provides explicit locations. `fontlabapp.plugins.boot.uninstall()` removes owned
runtime resources while retaining saved choices. Filters, tools and General
plugins default enabled; reporters and palettes start hidden unless saved.
Installing the core itself does not edit font data; explicit filter and palette
actions can make the edits described below.

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

Write a reporter by subclassing `fontlabapp.plugins.Reporter` with a unique
`name`, a `title` and a pure `compute(snapshot)` that returns `Mark` objects
(`ring`, `line`, `polyline`, `polygon`, `text`) in glyph units; pixel sizes are
view pixels. Set `layer = "background"` to paint under the glyph layer.
An error raised by `compute` or `requested_glyphs` goes to the error sink
once per stable reporter name and actual exception class while its key remains
in the shared 256-entry cache. Changing the error text or recreating the same
named reporter does not reopen a retained key. Eviction permits another report;
closing either backend resets the shared history. The first exception is passed
unchanged, and sink failures remain contained.
Every snapshot also carries `identity` (name, Unicodes, raw mark, mark RGB,
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
The legacy `fontlabapp.plugmix` entry-point group remains supported. New
extensions can use bundles without packaging or installation into site-packages.

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

Earlier releases have bounded native receipts in CHANGELOG. Those receipts do not qualify later shared writers or the full migration. Zone serializer ABI/payload preservation remains open; the route-A zone and metrics writers have no native receipt yet. Current text, NUL/IME, printer/OS, cache/history, font preservation and UI lifecycle holds are listed in [TODO](TODO.md). Native proof requires installed artifacts in owned FontLab fixtures, exact source hashes, complete state comparison, real controls, Undo/Redo and saved reopening for writers. Source and standalone Qt checks do not qualify native behavior.

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
| `transform_editor(font, name=None, parent=None, on_change=None, on_invalidate=None)` | Preview affine glyph transforms |
| `batch_panel(recipe, parent=None, on_finish=None, python=None)` | Run a UFO recipe in a child interpreter |
| `glyph_sequence(font, parent=None, on_select=None)` | Preview placed glyph sequences |

Importing the facade loads neither Qt nor Fontport. Call a factory inside
FontLab, retain the handle, and call `close()` when finished. Batch requires an
installed Python 3.11+ with Fontport; pass `python=` or set
`FONTLABAPP_BATCH_PYTHON`. See [the transform example](examples/font_transform.py).
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

Issue 210's reporter regression fixtures also require the sibling
`../fontlab-python-plugmix` source checkout, including its `Extensions` bundles
and `tests/bundle-map.json`. Tests select that path explicitly; production
discovery never searches a sibling checkout.

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

The source distribution includes the five unchanged files in
`generated/fontlabapp_shim` for the documentation and delivered-shim replay
checks; this fixture is separate from the installed runtime. A fresh extraction
must pass the complete suite with the same peers and `-B`, without precompiling
the package. Bytecode caches are transient hidden entries, while the required
private `_legacy` source must still exist and have its exclusion reason.
For ordinary-wheel verification, install the wheel and qualified peer wheels
in a fresh environment, unset `PYTHONPATH`, and add `-o pythonpath=` to the
pytest command from the extracted sdist. This selects the installed parent
runtime; some tests deliberately inspect or import extracted source in child
processes. Keep a separate `python -I -B` installed-only smoke check from an
unrelated directory, with import-origin and wheel RECORD verification.

The separate `tests_docs/` suite checks the generated documentation and immutable build workflow. With the same host exports, run the README migration contract and public-surface/dependency checks:

```sh
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py tests/test_package_boundaries.py tests/test_tombstones.py
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py::test_readme_when_read_then_moved_table_names_every_tombstone
uv run --python cpython-3.11-macos-aarch64-none --no-project --with ruff==0.14.10 ruff check --no-cache --select F821 src tests Scripts
```

The lint command checks undefined names; there is no configured full lint gate. Offline tests cover Python logic and doubles. Standalone Qt uses a different binding. Neither establishes native FontLab acceptance.

## Licence

Licensed under Apache-2.0; all Python sources in `fontlabapp.fontui` also carry Apache-2.0 SPDX identifiers (Issue 204). Bundled third-party code keeps its MIT and BSD-3-Clause notices, and the external native UI example keeps its [proprietary licence](examples/LICENSE-native-ui), so the distribution expression is `Apache-2.0 AND MIT AND BSD-3-Clause AND LicenseRef-Proprietary`. See [LICENSE](LICENSE), [NOTICE](NOTICE) and [MIGRATION.json](MIGRATION.json) for source-specific terms and attribution. Retained legacy sources and historical receipts do not grant permission to copy unlicensed third-party bodies into public artifacts.

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

## Plugin compatibility (Issue 210)

`fontlabapp.plugins` is the core namespace. `fontlabapp.plugmix` forwards to it
for one release and emits `DeprecationWarning`; migrate imports now. Concrete
examples belong to the companion Plugmix Extensions pack. Source tests establish
discovery and fake-host behavior; installed artifacts and native acceptance are
separate open checks in TODO.md.

## Documentation site

Author pages under `src_docs/md/`; `docs/` is generated output. Both complete maintained guides live under `src_docs/md/guides/`. Use a separate Python 3.13 environment, install `src_docs/requirements.txt` with `--require-hashes`, run `sh src_docs/build.sh`, then `python -m unittest discover -s tests_docs -v`. Every main push builds and qualifies immutable generated output. Private Pages configuration and publication remain owner-held; a passing build does not establish deployment or native FontLab acceptance.

## Font UI inspection compositions

The paired candidate provides `fontui.glyph_metrics.show(font, parent=None)`,
`fontui.anchor_components.show(font, parent=None)` and
`fontui.unicode_order.show(font, parent=None)`. They borrow the supplied font,
return retained modeless controllers and never close or edit that font.
Glyph metrics combines the Browser/Preview with exact selected-advance
comparison and geometric sidebearings; the inspector retains direct anchor
and component rows; Unicode/order uses the real glyph-name Sequence and
occurrence metadata. Public pure readers are `metrics`, `details` and `records`.
Imports stay host-free; UI is loaded on show. Unicode UI needs the existing
Fontport extra. Native UI/lifetime acceptance remains pending. A child whose
base cleanup partly failed remains retained/refused; shared lifecycle repair
is still required before whole-workflow teardown acceptance.

The [Font UI Lab Demo](Scripts/Font%20Editors/Font%20UI%20Lab%20Demo.py) opens all
three views over an explicit detached in-memory UFO sample. It requires the
Fontport extra and leaves native fonts, files and font registries untouched.

## Tabular Width Audit

The source candidate adds a borrowed-font chooser and exact selected-advance
report through `fontlabapp.fontui.tabular_audit.show(world, parent=None)`.
The first selected browser row supplies the reference; every selected advance
remains unrounded. Refresh discovers open fonts through the supplied FontWorld.
Source tests, matching ordinary distributions and native qualification are
separate gates. The implemented shared constructor recovery remains under independent review.

## Kerning Proof Workbench

`fontlabapp.fontui.kerning_proof.show(font, parent=None)` opens the existing kerning
editor and its linked sequence in one retained window. Pass an explicit borrowed
Fontport font; the window keeps that exact target when the active font changes.
None opens an unavailable view; an empty font is a valid target. The native backend
follows the captured font's current master.

Select a pair or type glyph/group names, then Apply or Delete explicitly. Zero
overrides group fallback; Delete restores fallback where available. Group proof
uses the first member. Reload keeps the target and rereads its data. The real
[demo](Scripts/Font%20Editors/Kerning%20Proof%20Workbench%20Demo.py) captures the
current font once. These controls write kerning; closing the window leaves the
font open. Fractional detached values remain supported; native fractional
history can refuse a change. Native Undo/Redo and saved/reopened acceptance are
separate from ordinary source tests.


## Kerning Group Explorer

`fontlabapp.fontui.kerning_groups.show(font, parent=None)` retains the existing
groups and kerning editors over the exact borrowed font. Select a group and use
it as the left or right key; the opposite key and value draft stay unchanged.
Accepted group actions refresh the pair through the existing editor. Renaming
or deleting a group does not rewrite stored kerning keys. The member preview
and pair proof are distinct. The proof uses first members and their effective
kerning, which can differ from the selected group row's value.

The [App demo](Scripts/Font%20Editors/Kerning%20Group%20Explorer%20Demo.py) captures the current font once.
Changing the active font does not retarget the window. Apply/Delete and group
actions write only that captured font; closing does not save or close it. Native
edits follow its current master. Source review, controlled full suites, matched
A1 artifacts/ordinary installs and native history/save-reopen remain separate
qualification gates; this addition asserts no release floor.

Master Width Comparison captures the current registered FontLab font once when the menu or demo opens. Select an occurrence in the real glyph sequence to compare fractional master widths; missing layers remain explicit. The window reads stored backend state through its own borrowed view, preserving unfinished edits held by other wrappers. It never switches or closes the source font. Ordinary UFO fonts receive a visible refusal. Source checks do not establish native history, reopen or ordinary installed acceptance.
