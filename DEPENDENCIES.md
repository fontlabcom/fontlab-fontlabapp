---
this_file: DEPENDENCIES.md
---

## 2026-11-16 — python-box (vfjo)

`python-box>=7.1,<9` casts FontLab 9.1 object JSON onto attribute-access trees for `fontlabapp.vfjo`, so scripts write `objs.data.glyph.layers[0].advanceWidth` instead of nested dict lookups. A small `Box` subclass refuses misspelt new keys on known levels and reading a missing key raises. Box is imported only inside `fontlabapp.vfjo`. Pydantic models may replace or complement it later. Canonical docs: [python-box wiki](https://github.com/cdgriffith/Box/wiki). FontLab's Python needs the package installed; that install is not yet checked live.

## 2026-11-15 — Transient installer marker parser

Conditional requirements in `install.vfpy` use `packaging==26.3` through `uv run --no-project --with` in an external Python matching final uv resolution. This is a transient parser dependency, not a package runtime requirement or FontLab-host import. Bare requirements avoid the helper. uv's cache or normal package access must provide the parser; failure stops sibling staging with an explicit error. The host installer still imports only the standard library.

Canonical APIs: [Requirement.marker](https://packaging.pypa.io/en/stable/requirements.html) and [Marker.evaluate](https://packaging.pypa.io/en/stable/markers.html). No custom PEP 508 parser is used. Cold-cache and native installation qualification remain separate.


## 2026-11-07 — fontlab-python-pens (Issue 235)

App now requires `fontlab-python-pens` (import name `fontlab_pens`): a
zero-dependency, fontTools-compatible Pen/PointPen protocol for FontLab layers
and elements. `outline_path` (transform, interpolation and inspector painters)
draws through `fontlab_pens.qt`, and Select Small Contours measures with
`fontlab_pens.AreaPen`, so it no longer needs the `fontui` extra. The package
is unpublished: `[tool.uv.sources]` resolves the sibling checkout, unpinned
because its untagged hatch-vcs version is a dev release. The `fontui` extra
keeps fontTools for the browser and preview helpers.

## 2026-11-06 — isolated documentation environment

`src_docs/requirements.in` and its 31-package hash-locked `requirements.txt` define the separate Python 3.13 ProperDocs/MaterialX documentation toolchain. They do not add host runtime dependencies or alter the arm64 Python 3.11 target. The theme loads versioned light fltheme26 components; all 44 bundled SSG vendor files are covered by complete rebuild parity.

# Dependencies

The external `examples/native_ui.py` script requires `fontlab-remopy` in its
external interpreter and App in FontLab. `--typerig` additionally requires
TypeRig in FontLab. These are example prerequisites, not required App runtime
dependencies; the host-free example tests use injected doubles.

## N156 — Text Holder NUL safety

No dependencies added. Existing injected Qt identifies PythonQt by its module
name. Its measured transfer defect is refused; ordinary Qt and storage retain
existing NUL behavior. Tests use existing read-only Qt5/Qt6 installations.


No runtime pip dependency. FontLab supplies `fontlab`, `fontgate`, `fontpr` and
PythonQt (Qt 5.15), imported only on native access.

Optional extras, all imported lazily with fallbacks:
- `markdown`: Markdown>=3.7 (BSD-3-Clause) and pymdown-extensions>=10 (MIT) for
  rich message formatting. Keyboard keys use PyMdown's `keys` extension.
- `hotkeys`: pyobjc-framework-Quartz>=10 (MIT, macOS only; cp311 universal2 wheels)
  for global hotkeys.
- `unicode`: unicodedata2>=15 (Apache-2.0) provides newer Unicode data for
  normalisation; otherwise the stdlib `unicodedata` is used.
- `fontui`: fontTools>=4.59 for outline decomposition, curve bounds and Qt paths
  in the original explicit-model browsers and glyph preview. The caller supplies
  its FontParts, defcon or ufoLib2 model; nothing is opened implicitly.
- `fontport`: fontlab-fontport>=1.2.2 (Apache-2.0), added by issue 201. It
  supplies the real fontParts/defcon/fontPens/fontTools/ufoLib2 stack for the
  info, groups, kerning, transform, batch and sequence editors restored to
  `fontlabapp.fontui`, plus active-font feature I/O
  (`fontlabapp.fontui.feature_blocks`). The editors came back from
  `fontlab_fontport.ui`, which keeps only an `ImportError` tombstone. App
  imports Fontport lazily: a factory call imports its editor module, and a
  missing Fontport raises `ImportError` that names this extra
  (`fontlabapp.fontui._fontport.require_fontport`). This extra is the only
  place where `pyproject.toml` may name Fontport; no `[tool.uv.sources]` entry
  is kept. Fontport base has no App dependency; its optional `fontlab` extra
  supplies the lazy native guards and deprecated feature forwarder. No hard
  cycle exists. `tests/test_package_boundaries.py` allows `fontlab_fontport`
  imports only in those editor modules and `feature_blocks`, and no Glyport
  import anywhere. The editor tests require Fontport in the test environment
  (`test.sh` installs the sibling `../fontlab-fontport` checkout). Tests
  install ufoLib2 and FontParts to exercise the model-agnostic browsers.
- Issue 122 shared modules (`affine`, `qtsafe`, `qt_dialogs`, `owned_menus`,
  `editor_painters`, `edit_guards`, `history`, `metrics_panel`, `names_edit`)
  add no dependency. At load time they import only the standard library and
  sibling `fontlabapp` modules that do the same: `affine`, `qtsafe`,
  `qt_dialogs`, `edit_guards` and `history` import no sibling, `owned_menus`
  imports `deferred_batch` and `qtsafe`, `editor_painters` imports `affine`
  and `qtsafe`, `names_edit` imports `history`. Other siblings
  (`scripting`, `guides`, `duplicate_unicodes_capture`) load only inside
  the functions that need them.
  PythonQt and `fontlab` come from the caller or load inside a function
  (`metrics_panel.panel_type()` loads the PythonQt panel class).
  Cold-import tests enforce this. The `fontui` facade exports lazy factories;
  no tombstone finder remains. Public-surface tests check `__all__` and docstrings.

The former `mdx_steroids.keys` detection was removed (R046): that package is not
on PyPI, and `pymdownx.keys` with the same settings is the supported path.

Build and test: hatchling and hatch-vcs; pytest. The `test` extra also installs
PySide6-Essentials (LGPL-3.0) so tests/test_fontui_follow_qt.py runs the change follower on
a real Qt event loop; it is never imported by the package and never loaded in FontLab.

Re-evaluated 2026-10-15 (R046): all optional packages are maintained, with releases
in 2026, and import under arm64 CPython 3.11. Install host-side extras into an arm64
Python 3.11 environment, never an x86_64 one (see the workspace INSTALL.md).

Official APIs consulted:
[Python-Markdown](https://python-markdown.github.io/reference/markdown/) and
[PyMdown Keys](https://facelessuser.github.io/pymdown-extensions/extensions/keys/).
Vendored collection and merge implementations preserve existing source semantics
and their BSD/MIT notices; no replacement package changes these behaviors.

Hotkey cleanup APIs checked against installed Quartz and official
[PyObjC Quartz](https://pyobjc.readthedocs.io/en/latest/apinotes/Quartz.html),
[PyObjC memory management](https://pyobjc.readthedocs.io/en/latest/core/intro.html)
and [CFMachPort](https://developer.apple.com/documentation/corefoundation/cfmachport).
Python references retain bridge-owned objects; explicit Core Foundation
retain/release calls are unnecessary here.

Font UI ownership follows Qt 5's documented QObject destroyed-before-children
signal order: <https://doc.qt.io/qt-5/qobject.html#destroyed>. Native receipts
verify parent destruction and direct deferred deletion, in addition to close().
The staged information form uses documented Qt 5
[QLineEdit](https://doc.qt.io/qt-5/qlineedit.html),
[QPlainTextEdit](https://doc.qt.io/qt-5/qplaintextedit.html),
[QLabel buddies](https://doc.qt.io/qt-5/qlabel.html#setBuddy) and
[QFormLayout](https://doc.qt.io/qt-5/qformlayout.html). PythonQt exposes Qt
properties such as QLineEdit.text as values rather than callable getters.

Feature script writes (`fontlabapp.fontui.feature_blocks`) require native fontpr. No new runtime dependency or Qt framework is added.
The backend supplies ordered VFJ source and validates history round trips before
writing; script metadata setters are deliberately not used for feature edits.

Names inspection tools use existing FontLab/PythonQt, fly and standard-library
Unicode/glob/regex modules; no new third-party dependencies. The new shared Names
panel requires the updated App sources/build beyond the v0.2.5 baseline.

The five read-only Kerning tools need the forthcoming App 0.2.7 helpers.
For development use an explicit current App wheel plus SCRIPTMIX_APP_SOURCE
pointing at the updated sources. This does not claim package-index publication.
Inspection uses FontLab's native named-master kerning items/groups and effective
get(names), with existing PythonQt.QtGui and standard-library CSV only. Fontport's
current-master UFO normalization/editor is not needed; no Fontport extra
or foreign Qt package is loaded by this batch.

The five Kerning editors use App0.2.8's lazy shared plans and all-master writer,
existing FontLab/PythonQt.QtGui and the standard library. No new package or Qt
binding is added. Fontport's existing writer is key-master/UFO-normalized; calling
it once per master would split history, so App retains a small native @notation
batch using its measured zero-seed/scale protocol and container checkpoints.
Official local pyfontgate/fgkerning.cxx and QtGui stubs were consulted for native
items/set/remove/scale and QBoxLayout insertion. Native acceptance is pending.

Kerning batch preflight also follows FontLab's native load limit in
Proteus/workspace2/ioengine.cpp: every final master must stay within +/-2*UPM.
This is a persistence constraint, not a new dependency or Fontport API change.

Exceptions Finder and Pairs From Text require forthcoming App0.2.9's
kerning_selection helper plus the existing snapshot/batch/dialog helpers. They
add no packages: word adjacency uses standard-library itertools.pairwise and
preview reads reuse native FontLab effective kerning. Use a built wheel and an
explicit updated source override during development; no index release is implied.

Proof tools require forthcoming App0.2.10's lazy proof_api/proof_dialog_type/
proof_view_types/proof_snapshot_refresh helpers. No package or framework is added:
existing FontLab/PythonQt supplies actual QPainterPath/QTransform/QPainter, and
existing fly.ap/scripting provides ordered names/selection and owned lifecycle.
Pure filters and text calculations use the standard library. Current source
or a current built wheel is needed; no registry publication is claimed. Official
local pyflshape.cpp path getters and QtGui stubs were checked. Qt's QPainter.end
and QPainterPath.addPath documentation supports the existing painter lifetime
and compound-path model; Qt5 native acceptance remains separate from Qt6
mathematical path tests in the external test environment.

Proof opening-read fix1 reuses QObject.blockSignals(bool)->bool, documented by
local QtCore.pyi and already used in App fontui controls. Previous signal state
is restored in finally around initial/retried QComboBox.clear/addItem/index
publication. No new dependency or Qt binding is introduced.

App never imports Glyport; optional Fontport imports stay inside the
`fontlabapp.fontui` editors and `feature_blocks` (issue 201).
`fontlabapp.core.legacy.vanilla` remains host-free and raises its migration
error on VanillaSession access. Feature helpers in `fontlabapp.core.scripting`
lazily forward to `fontlabapp.fontui.feature_blocks`. Cold imports remain
host-free.


Image resources use Python stdlib only. Qt is an explicit injected namespace,
not an imported Python binding. PDF conversion invokes the existing macOS
/usr/bin/sips command on request, with a bounded timeout and scratch cleanup;
non-macOS callers can inject their own runner/executable. No required Glyport
or Fontport dependency is introduced. The relocated Glyport implementation is
MIT-licensed; its complete notice is retained in NOTICE.


The host-free ui_graph module uses stdlib dataclasses and mappings for ordered
node/tree/event records and versioned JSON serialization. Frame dictionaries
are opaque facts, not a layout engine. Compatibility subclasses bind their
existing node/frame types; App imports no Glyport/Fontport/native package.
Source MIT attribution is retained in NOTICE.

Angularizzle numerical candidate uses only dataclasses, itertools and math from
the standard library. Existing generic Bezier interpolation/subdivision does
not reproduce its accumulated1/130lookup, first-interval-zero interpolation,
strict detail threshold and duplicate endpoint behavior. This is an adaptation
of the licensed core algorithm, not a new general geometry dependency.


qt_dialogs is stdlib-only and receives Qt explicitly. It constructs prepared
message boxes, runs supplied boxes/owned file choosers with deleteLater in
finally, and shows/closes boxes using caller-owned storage. It connects no
signals and creates no application event loop. Existing OwnedWidget adds
destroyed-signal ownership and is not substituted for this legacy lifecycle.
Callback/answer/filter/foreign parent policy stays in the caller. Original MIT
attribution is retained in NOTICE; no required Glyport/Fontport edge is added.


Shared owned dialog execution uses App qt_dialogs.run_owned_dialog. The caller
retains all text conversion, defaults and acceptance/cancel policy. The helper
adds no package, Qt binding, signal or application event loop. Glyport requires
the unpublished reviewed App>=0.2.32.dev0 API; release/lock refresh is still a
publication gate.


instance_style_names uses stdlib regex/dataclasses only. No existing matching
helper was found in App. These are licensed source-specific computation rules;
Glyphs property lookup, instance eligibility and native writing stay outside
this generic core. No new package or native dependency is introduced.

M1 Point Counter uses only stdlib plus existing native FontLab/PythonQt access.
No runtime dependencies added; shared owned text lifecycle stays in App.

O1: the generic linear_layout solver lives in App (stdlib only). Glyport now requires the explicit unpublished App>=0.2.36.dev0 candidate; its relative local development lock must be refreshed against an accepted release before publication. No mandatory reverse dependency.

X1 alignment-zone staging uses only dataclasses, math and collections.abc. No
new dependency or host import is needed; native integration remains a separate gate.

Y1 uses host-provided PythonQt only when the editor is opened. Public zone_editor
imports remain host-free. Offscreen tests reuse the existing PySide6 test extra;
no runtime or optional dependency is added.

Y2 script completion uses only the standard library; Qt access occurs only for
the native Close dispatcher fallback. Existing PythonQt and offscreen PySide6
roles remain unchanged. No dependency is added.

X2a zone row identity/metadata transport uses existing stdlib dataclasses and
shared App table/lifecycle helpers. No package dependency or native codec added.

X2b-read uses stdlib frozen dataclasses, existing App source/value parsers and
FontLab's own binary guide serializer. No package dependency or custom codec added.

X2b verification alone compiles an isolated SDK macro with upstream PyCXX7.2.0; no PyCXX source, extension or dependency enters the runtime package.

X2c write preflight reuses frozen stdlib dataclasses, existing zone Editor/row
normalization and a shared source-derived native kind rule. No dependency added.

X2d preparation uses existing stdlib dataclasses, host-provided FontLab binary
model operations and PythonQt value objects only on explicit invocation. No new
package, custom binary parser or system clipboard dependency is introduced.

Z1 Text Filter adds no dependency: stdlib re/dataclasses/string, host PythonQt
QSettings/widgets, and existing shared owned completion/literal-text tab sender.
Qt6 tests use existing PySide6 with explicit temporary INI stores.

Z2 extrema add no dependency: stdlib dataclasses/math/time, existing native
package/layer readers, named-tab sender and owned snapshot dialog. Foreground
role/order mapping follows the reviewed Glyphs2.5 iterator and existing bridge.


Issue120 Z3: share binding-free one-axis stack distributions in stack_layout.
Cocoa/Vanilla adapters retain their enum/coordinate/natural-size/hidden/ownership
policy. Existing nonempty finite geometry is exact; empty helper input returns
an empty result. Fixed/equal/proportional/spacing/centering, clamping and list
identity are tested. No required dependency or native qualification added.

Z4 adds no dependency: stdlib immutable records plus existing native selection
and owned snapshot dialog. Scriptmix requires unpublished reviewed App>=0.2.51.dev0
via Fly. No required reverse package edge or third-party implementation is added.


## Issue120 shared key routing Z8

Z8 shares the complete handled-key acceptance/unhandled explicit-native-base mechanism through host-free App.key_events. All five existing consumers remain: App glyph browser and sequence canvas, Glyport Cocoa stepping field, Vanilla list and Vanilla window. Each keeps its original key/owner/callback/error/cleanup policy. No super() protected-slot lookup or new widget inheritance layer.28newApp/12newGlyport tests pass; complete source suites2033App and2996Glyport/4existing skips. All6whole changed production modules exceed80%statements/branches,zero exclusions. Five real offscreen Qt6 controls pass; this does not prove compiled PythonQt/native-font/history/reopen acceptance.

Z9 bracket-layer workflows add no runtime dependency: stdlib graph traversal, existing shared App report/tab controls and FontLab native APIs. Menus require the reviewed unpublished App>=0.2.53.dev0. Apache-2.0 source attribution is in NOTICE.

Z10 adds no runtime dependency. App uses stdlib and FontLab PythonQt; menus require the reviewed unpublished App>=0.2.54.dev0. Standalone PyQt5==5.15.11/Qt5 and PySide6 checks run in separate private test processes and are never loaded into FontLab. Archived first-party Python source attribution is in NOTICE.

Z11 adds no runtime dependency. Typed Qt date policies use existing FontLab PythonQt. Optional Table.epochs is plain immutable integer data; old string-table callers retain their behavior. Menus require reviewed unpublished App>=0.2.55.dev0. Standalone Qt5/Qt6 remain separate private test processes.

Z12 adds no third-party dependency. Shared borrowed/message-box ownership uses injected Qt and stdlib only. Glyport requires the reviewed unpublished App>=0.2.56.dev0 candidate; native acceptance remains pending.

Z13 adds no third-party dependency. Immutable topology/model helpers use stdlib and injected existing Qt. The two practical tree menus require reviewed unpublished App>=0.2.57.dev0 and Fly; actual native acceptance remains pending.

Z14 adds no third-party package. Generic image presentation uses stdlib and injected existing Qt. Glyport requires the reviewed unpublished App>=0.2.58.dev0 candidate; native and released-dependency gates remain open.


## Issue120 Z15 — nested callback suppression

App.callback_guard.quiet_callbacks owns the eight existing programmatic callback
suppression scopes. It restores the incoming flag on normal/error/cancellation
exits, so nested setters cannot unmute an outer update. Qt signal connections
and unrelated listeners stay active; Cocoa target/action/delegate/bindings and
Vanilla callback/edit/selection policy remain in Glyport. The helper imports only
stdlib and accepts Python wrappers with an existing writable _quiet flag on their
UI thread. It provides no rollback, thread synchronization or widget ownership.
Glyport requires reviewed unpublished App>=0.2.59.dev0. Actual PythonQt/plugin/
font/cache/history/dirty/save/reopen, released dependencies and every original
issue120 gate remain pending D25. No originals/corpus/live installation change.


## Issue120 Z16 — complete part2 modification calendar candidate

The complete part2 calendar retains three locales, Monday/Sunday, single/no
selection, grid/navigation, every horizontal/vertical heading mode, selected/
minimum/maximum date editors, all weekday/weekend/header colours and first-Friday/
January-1 markings. Selected days show all matching current-font glyph metadata
in font order, all Unicode assignments, explicit unencoded values and exact local
timestamps. Undated glyphs are counted. Refresh replaces the entire observation.

Initial controls agree with the actual calendar; crossing limits synchronize all
three date editors. A copied owned date-surface palette preserves explicit named
colours on dark hosts, including readable headers/off-month dates; the surrounding
UI retains its host palette. Generic UI takes injected Qt and caller-owned signals.
Setup failures fence queued slots; all completion routes, parent destruction and
late Close release callbacks/data. Reads and planning share a bounded deadline.

Requires reviewed unpublished App>=0.2.60.dev0 via Fly. No font, selection, history,
preferences, file, clipboard or Output writer is added. The distinct part3 calendar
is not implemented by this entry. Originals/dependencies remain read-only and
unexecuted. Actual PythonQt/FontLab/getter/cache/font/history/dirty/reopen/native
workflow, release/integration/download/docs/publication and full issue120 gates
remain pending D25. Standalone scalar/Qt tests do not accept those requirements.


## Issue120 Z17 — complete distinct part3 calendar candidate

Part3 retains every Qt locale in original order, native language/country labels
and last matching initial locale, all seven week starts, both selection modes,
grid/navigation, every heading format, 1900–3000 date limits and MMM d yyyy
editors, four weekday/weekend colours and Bold/Italic/Plain headers. The latent
programmatic Green header rule remains without a new UI choice. Blue first-Friday
and red May1 switches are independent; May1 wins collisions. Only owned old marks
clear after page/year/switch changes. Full locale labels remain in the popup and
tooltip while the field stays bounded. No global locale or theme setting changes.

A shared injected-Qt base owns geometry, fields, coherent dates and callback
fencing. Part2 retains every public import path and its distinct policy. Both
modeless panels share whole captured local-day glyph reports and separate registry
keys. Source/type/empty/error/deadline/close/teardown paths remain complete.

Requires reviewed unpublished App>=0.2.61.dev0 through Fly. No original/corpus
script, native font/selection/history/preferences/clipboard/file/Output writer,
live install, canonical merge, release or publication is introduced. Actual
PythonQt/native UI/getter/font/cache/history/dirty/save/reopen and all original
issue120 source/integration/distribution/docs/publication gates remain pending D25.


## Issue120 Z18 — shared signal connections

App.signal_connections.track_connection and disconnect_connections own the exact
signal/slot list mechanics shared by both Cocoa and Vanilla control bases.
Connect first and retain exact objects, duplicate connections and order. Drain
in reverse order, popping before disconnect. Ordinary disconnect failures go to
the caller's existing sink; sink failures and BaseException propagate with all
unattempted pairs still retained. Only owned slots are disconnected. Repeated
empty teardown is harmless; unrelated listeners remain active.

Glyport keeps callback guards, target/action/delegate/binding and foreign API
policy, private _slots layout and owner cleanup order. No widget framework,
connection-wide disconnect, new dependency, live installation or original/corpus
execution is introduced. Slots must satisfy the binding's existing safety rules;
this helper cannot repair invalid native wrappers or cancel queued callbacks.
Reviewed unpublished App>=0.2.62.dev0 and Glyport1.0.8.dev28 are candidates only.
Actual PythonQt/plugin/teardown and complete font/cache/history/dirty/save/reopen,
released dependencies and every original issue120 gate remain pending D25.


## Issue120 Z20 — complete glyph-name completion pair

Implement both distinct part2/part3 custom-completer workflows over the complete
current-font glyph-name snapshot. Share injected Qt editor/model ownership in
App; preserve each original key, focus, suffix and menu policy. Use Qt itself
for case-insensitive sorting before completer binary search. Refresh keeps the
draft and discards stale vocabulary on failure. About information appears in
the modeless status area; Vocabulary names are escaped plain data. Disconnect
faults retain ownership and refuse Close for retry. Every ordinary completion,
parent destruction, setup failure and queued callback is owned and fenced.

Requires reviewed unpublished App>=0.2.63.dev0 through Fly. Originals/resources
remain read only, unexecuted and unbundled. No native font/selection/history/
preferences/file/Output writer or live install is added. Full installed PythonQt
behavior and complete font/cache/history/dirty/save/reopen preservation remain
pending D25, as do every original issue120 integration/distribution/publication
gate. Source and artifact checks do not constitute native acceptance.

Issue120 resize forwarding: App resize_events uses only the standard library.
Glyport requires fontlab-fontlabapp>=0.2.67.dev0 for the shared helper; candidate
artifact verification does not prove released dependency closure.

## Issue120 Qt known-property reader Z27

App qt_properties.value uses only standard-library getattr/callable and typing.Any; import is host/binding-free. Existing known-property names remain explicit; no scanning API or dependency is added. Glyport needs unpublished local App>=0.2.69.dev0 for this new module. Standalone PyQt5 tests remain in private external environments, never FontLab.

## Issue120 N23 — contents rectangle ownership

App.content_geometry.fit_contents now owns the exact one-read contentsRect
geometry mechanism. Glyport Box keeps the original entry point, event handlers,
size assignment and child relayout order. Values and exceptions pass unchanged.
Cocoa NSBox foreign content frames and layout-managed groups retain their own
policies. No Qt, font model or new external dependency is added to App.

Glyport requires candidate App>=0.2.72.dev0. Candidate resolution does not prove
public registry availability. Actual installed PythonQt, lifecycle and complete
font/UI/cache/history/dirty/Undo/Redo/save/reopen acceptance, independent review,
integration/release and every original issue120 gate remain pending.
Contour selection reuses optional fontui fontTools>=4.59 AreaPen for analytic
line/quadratic/cubic unsigned area. No mandatory dependency or reverse dependency
was added. Missing FontTools refuses before selection clearing. Calibrated against
FontTools4.67.0 source and official AreaPen documentation.
Z27 spacing worksheets add no runtime dependency. Use existing injected FontLab PythonQt, shared draft_signals/layer_selection/tabular_width mechanics and Fly. Standalone PyQt5 is test-only rehearsal; foreign Qt is never imported into FontLab. Normal wheel/sdist installs retain declared dependency resolution and pip check; host architecture is aarch64 Python3.11.

N119 adds no dependency. Duplicate-anchor UI uses injected host Qt5/PythonQt and existing Fly/App ownership helpers; external PyQt5/PySide6 serve offline tests only.

N137 shares Qt table-selection mechanics without new runtime packages or a binding import. Glyport requires unpublished reviewed App>=0.2.113.dev0; the private relative .local/shared-ui-next-z42/app-dist find-links supplies exact ordinary artifacts for coherent uv lock/check/sync and consumer resolution. No public registry availability or native acceptance is claimed.


N141 combined source uses App0.2.115.dev0 and Glyport1.0.8.dev35. Glyport declares App>=0.2.115.dev0 for the union of complete shared deferred scheduling and table selection. The private relative `.local/ui-integration-z43/app-dist` flat index supplies exact reviewed App wheel/sdist before normal `uv lock --check`, `uv sync --locked` and installed-consumer resolution. No absolute private path enters package metadata, no reverse App dependency is added and no public registry availability is claimed.

N143 uses existing injected Qt and stdlib only. Glyport needs reviewed unpublished App>=0.2.116.dev0. Private .local/shared-ui-next-z43/app-dist holds exact ordinary artifacts for coherent uv lock/check/sync/run; no registry publication or native claim.

Master-layer Point Counter reuses local `text_holder_editor` literal MIME and report-local readonly IME refusal; no new package dependency.

Duplicate Unicodes reuses App-owned glyph catalog facts, dependency analysis, exact signal ownership and completion lifecycle. No new runtime dependency; menu requires Fly and App0.2.121.dev0.

N181: generic Qt numeric ranges use stdlib and injected native setters only. Glyport requires reviewed unpublished App>=0.2.131.dev0; ordinary local artifacts supply the prerequisite. No App→Glyport required edge, foreign Qt import, Fontport policy or registry/publication claim is added.


N267 color UI requires reviewed unpublished fontlab-fontlabapp>=0.2.158.dev0. Glyport1.0.8.dev41 uses the exact local App wheel through relative `.local/color-ui-z59/app-dist` in its owned lock; normal uv lock/check/sync must resolve that same candidate. No new Qt or foreign dependency is introduced; binding injection stays unchanged.

Clean Classes accepts a caller-supplied backend for actual OpenType class/history operations. App never imports or requires Glyport. The Scriptmix menu explicitly constructs the existing Glyport FontLabBackend through Fly; no App dependency metadata, minimum Glyport version or circular package dependency is added.
