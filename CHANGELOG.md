---
this_file: CHANGELOG.md
---

## 2026-11-18 — compact is the default for every fontlabapp window (Issue 253)

- `Owned`, `create_panel`, `create_dialog` and `create_widget` now apply FontLab panel metrics (6 px margins, 4 px spacing) by default; pass `compact=False` to keep Qt's roomy 11/6. Tab pages inside compact windows are capped to the same margins. Redundant per-window `compact_layout` calls were removed.
- The Transform preview canvas and Font Browser thumbnails follow the canvas palette instead of painting white in the dark theme.
- New tests: `tests/test_compact_default.py`, `tests/test_bound_slot_guard.py` (source check that no signal is connected to a bound Qt slot, which PythonQt silently ignores), `tests/test_canvas_palette_literals.py`.

## 2026-11-18 — v1.2.37: compact GUI metrics for eleven windows; `qt.compact` helpers (Issue 253)

- New `fontlabapp.qt.compact` (re-exported by `fontlabapp.ui`; scripts import it as `fly.ap.qt.compact`): `compact_layout`, `compact`, `compact_dialog`, `controls_box` and `split_view`. They give windows FontLab's own panel metrics (margins 6 px, spacing 4 px, instead of Qt's 11 and 6) and put a glyph view frameless above or beside its controls. A missing Qt setter logs a warning and leaves the object unchanged, because compaction is cosmetic and the window must still open.
- Compacted windows (11): TGlyph, TMetrics, the filter dialog, Kerning, Font Info, Groups, Features, Sequence, Transform, Designspace and Font Browser. TGlyph and TMetrics place the canvas first with stretch 1 (`insertWidget(0, view, 1)`).
- New script `Scripts/Widgets/Compact Dialog Demo.py`: a modeless compact dialog with a frameless glyph view above a label and a Close button.
- `document_raw_text` falls back to a bounded block loop when `toRawText` is missing (FontLab 9.1.9813 has none) or raises.
- PythonQt finding: in FontLab 9.1.9813, `button.clicked.connect(dialog.close)` and `.connect(dialog.hide)` (bound C++ methods) do nothing; a lambda or a string slot works (`native/p17`). The demo uses a lambda. Other windows that connect bound C++ methods were not audited.
- Native checks (FontLab 9.1.9813, clone source): the helpers' margins, spacing and frames and the `toRawText` fallback (`native/p15`), and the demo itself, Close included (`native/p16`). Not covered by a margin test: Designspace, Features, Font Browser.
- Docs: the api-map pin in `tests_docs/test_site.py` gets reviewed reversal entries for the new module.

## 2026-11-17 — Reporters panel screen lookup; installer stub 1.0.15 (Issue 259 follow-ups)

- The Reporters and Inspectors panel no longer fails with
  `'NoneType' object is not callable` when FontLab's `primaryScreen` binding is a
  value or null: the screen is read as a value or a call, and the first of
  `screens()` is used when there is none. With no screen at all the
  initial fit is skipped.
- `install.vfpy` is now the stub from fontlab-python-instamix 1.0.15. It replaces an
  installed instamix older than 1.0.13 and puts the old copy back if the upgrade
  fails; linked checkouts and local builds are kept. A download that fails for
  lack of root certificates (FontLab 9 for macOS) is retried with the system curl.

## 2026-11-17 — v1.2.35: TMetrics falls back to the default master when the current master names no layer

- FontLab's `renameMaster()` renames the master but leaves every glyph layer under the old name. On a copy of i2-lato, renaming Black to "Black Renamed" left glyph A with the layers Black and Hairline. On i2-lato (3,055 glyphs) and KinneyMM (3,171 glyphs) the master names match the master layer names; KinneyMM's `space.superior` has no master layers at all. `FontReads.current_master` now checks the master name against the first glyph that has the default layer. If no layer has that name, TMetrics shows the default master, and the status says "FontLab's current master Black Renamed has no layer of that name, so the default master (Hairline) is shown." (commit `227efb7`).
- Cost: in FontLab 9.1.9813, `package_of()` takes about 0.0012 ms and `master_changed()` about 0.006 ms per call (`live_default_layer` alone 0.004 ms), with a typing median of 0.013 s on i2-lato. The docstrings now state this cost instead of "costs nothing per keystroke"; no per-refresh cache was needed.
- New tests: a master that names no layer, empty and `None` masters, a non-`str` master, and the kerning refusal when the current master is not the default.
- Native checks with the dev wheel and then the v1.2.35 release wheel (both installed with `fontlab_instamix pkg install`): the rename fallback (`p11/rename_fix.json`, renamed back afterwards, copy not saved), and Black's widths after `setMaster("Black")` (`p11/master_dev.json`, `p11/master_release.json`). Evidence: `/Volumes/Falstaff4T/fontlab-scripting-data/issue258/native/p11/`. PyPI publishing still fails; the GitHub release has the wheel.

## 2026-11-17 — v1.2.34: TMetrics "Current master" follows FontLab's current master

- FontLab's `setMaster()` moves `flPackage.master` and leaves `flPackage.defaultMaster`, which Fontport reports as `defaultLayerName`. TMetrics read "Current master" through `defaultLayerName`, so after a switch it kept showing (and would have written) the old master's widths. `FontReads.current_master` now reads `flPackage.master` (falling back to `defaultLayerName` for a detached or host-free font), `master_changed()` compares it too, and TMetrics passes the resolved layer explicitly to the model, metric writes, nudges, hint checks and kerning (commit `64f06f8`, tests in `tests/test_tmetrics_font_reads.py`).
- Font kerning stays on the default master: when the current master is another one, kerning is not shown and the status says "kerning is unavailable for Black; FontLab keeps font kerning on the default master (Hairline)."
- Native check (FontLab 9.1.9813, `i2-lato.vfj`): first with a locally built dev wheel, then with the v1.2.34 release wheel, both installed with `fontlab_instamix pkg install`. `setMaster("Black", True)` then `follow()` showed Black's widths 1554/1422/1422/1422/2130; switching back showed Hairline's 1496/1274/1274/1274/2002. Evidence: `/Volumes/Falstaff4T/fontlab-scripting-data/issue258/native/p10/`.
- Not checked: a master switch made by hand in the FontLab UI (none could be driven from Python), outlines and kerning after a switch. v1.2.33 was already taken by the Issue 259 release, so this is v1.2.34; PyPI publishing still fails (trusted publisher), the GitHub release has the wheel.

## 2026-11-17 — v1.2.32 TMetrics master switch and large-font checks

Evidence: `/Volumes/Falstaff4T/fontlab-scripting-data/issue258/native/p9/`. FontLab 9.1.9813, installed App 1.2.32, no uharfbuzz.

- Large font: on `terminaldesign--KinneyMM-Upr.vfj` (3,171 glyphs, master Light), TMetrics opened in 0.32 s with 21 cells, and three `follow()` calls, each including the font refresh, took 0.35, 0.35 and 0.37 s (`large.json`).
- Master switch: a defect was found and is not fixed. After `setMaster("Black", True)` on i2-lato, `follow()` kept the Hairline widths and showed no error (`master3.json`); see the TODO row.

## 2026-11-17 — App windows open in FontLab 9 for Windows (Issue 259)

- `available_geometry` reads `QScreen.availableGeometry` as a value or a method. FontLab 9.1 for Windows exposes it as a `QRect` value, so every App studio window (for example Font Audit) failed with `TypeError: 'QRect' object is not callable` before it opened. Verified in Windows FontLab 9.1.9813: Font Audit now opens.

## 2026-11-17 — v1.2.32 installed and checked in FontLab

Evidence: `/Volumes/Falstaff4T/fontlab-scripting-data/issue258/native/p8/` (`result.json`, `install-command.txt`). FontLab 9.1.9813, `i2-lato.vfj`, App 1.2.32 installed from the GitHub release wheel into the FontLab 9 site-packages with `fontlab_instamix pkg install`, fontport 1.2.13. uharfbuzz is not installed on this host.

- TMetrics follows a width change made through the FontLab API (`flLayer.advanceWidth`, outside fontport): `A`/Hairline 1274 to 1284 was shown after `follow()` (0.22 s), and 1274 again after the restore.
- TMetrics typing speed: 21 keys of "HAVAW Hamburgefonstiv" typed into the text field, median 0.019 s per key, slowest 0.032 s (the first key). The target was 0.13 s.
- Not checked: updates after a master switch, an edit made by hand in the FontLab UI, or a large font. PyPI publishing of v1.2.32 failed (trusted-publisher configuration), so the GitHub release is the install source.

## 2026-11-17 — TMetrics: follow survives a refused Fontport refresh

- `FontReads.reset()` (`src/fontlabapp/fontui/_font_reads.py`) catches Fontport's `UnsupportedCapability`, which `RFont.refresh()` raises while a glyph has unfinished point edits. The memo is still cleared, the refresh is skipped with a debug log line, and other `NotImplementedError`s still raise. The class is matched by name because App code outside the Fontport editors must not import Fontport. Commit `49ee592`, merged as `bd9deb7`; test `test_reset_when_refresh_refused_for_pending_edits_then_memo_cleared_without_error`. Offline tests only; not run in FontLab.

## 2026-11-17 — Issue 258 task cleanup, round 4 (native Round 3 evidence)

Evidence: `WORK/issue258/tasks/n1-report.md` "Round 3"; native files under `/Volumes/Falstaff4T/fontlab-scripting-data/issue258/native/`. FontLab 9.1.9813, Lato `i2-lato.vfj`, installed App 1.2.30 and fontport 1.2.13. Every probe restored its edits.

- T44 five filters (`p5/filters.json`, unreleased source with `d3962ed`): Apply changed the outline and one Undo restored it exactly for DeleteSmallPaths, MoveOutlines, RoundOutlineToGrid, ScaleOutlines and SlantOutlines. With the element scaled to 1.1, each filter refused `A` with a reason row, none bare. Redo and save/reopen were not run.
- `vfjo.scale` ghost hints (`p6/vfjo.json`, fix `92f35ba`, in App 1.2.30): `scale(2, 0.5, origin=(100, 200))` on `W` and `A` kept the ghosts at -20/21 in both masters, and the read-back from FontLab matched.
- `vfjo.paste` shapes (`p6/vfjo.json`): element and contour data landed on the active layer, one Undo each restored it (1 to 2 to 1), and `font=` another font was refused with the "make that font current first" message.
- Object JSON glyph paste through the API (`p6/vfjo.json`): `objs.paste()` created renamed glyphs `W.n1sc` and `A.n1sc` with outlines, per-master widths and hints. Three Undo triggers removed them. The demo scripts and Edit > Paste were not driven.
- TMetrics `follow()` (`p7/tmetrics.json`, `p7/retest.json`): 0.21 s per call, open 0.36 s, measured without uharfbuzz. This replaces the earlier 1.1 s figure. A width edit (`A` 1274 to 1284) was not shown after `follow()` because the fontport `RFont` kept stale glyph handles (`p7/width_diag.json`, `p7/cache_diag.json`). `FontReads.reset()` now calls the font's `refresh()`: commit `bf7d5b3`, merged as `66113f5`; the retest showed 1284 after `follow()` and 1274 after restore. Not checked in an installed release or with an edit through the FontLab UI.

## 2026-11-17 — Issue 258 task cleanup, round 2

- T44 "Skipped: a" (Issue 253): the Filters now name why a coordinate edit was skipped (shared, scaled and rotated elements) in a reason row. Commit `d3962ed`. Live Apply/Undo of all five filters is not yet tested; a follow-up row stays in TODO.
- Node Editing Lab node table follows native Undo/Redo and outside outline edits. Commit `0450641`. Native check: node 0 went 43 to 53 to 43 to 53 across Apply, Undo, Redo (`WORK/issue258/tasks/n1-report.md`).
- Closed the Examples R gate row (`tests/test_issue122_E10.py`): Examples commit `e8f7809` deleted that test, and all three entries (Font Name Encoding Audit, Localized Font Names, Font Info Snapshot) open cleanly in native FontLab (`native/p4/result.json`).
- `fontlabapp.vfjo.scale` ghost-hint fix `92f35ba` ("vfjo: keep ghost hints unscaled in scale") is on origin/main. Its live recheck, the vfjo paste and object JSON live checks and the TMetrics `follow()` cost stay open in TODO because none is natively verified.
- Added one low-priority TODO row for the minor findings of the static review of `0450641`/`d3962ed` (silent read errors in the node table follow, positional index in `apply.py`).

## 2026-11-17 — Issue 258 task cleanup

- TODO: removed a duplicated "Advance compact forms, selected-layer Filters and TMetrics typing fixes" row.
- TODO: the Issue 254 row now lists three repositories, not five. Remopy 2.0.4 and pythonqtside moved to the Instamix stub installer (see their CHANGELOGs, 2026-11-15 to 2026-11-16).
- TODO: the "link a fix PR" row now says to file the issue in fontlab/fl with suggested code changes (owner rule 2026-11-16).
- TODO: the native_ui.py requalification row cites fl#8657 as its blocker.
- Added a prioritised Next steps list. Documentation only.

## Issue 256 source qualification completed — 2026-11-17

The corrected owned-peer environment passes 17,011 tests with 47 existing skips (229.35 s). The earlier 30 failures reproduce on baseline and are retained below: missing Lessons and Fly context, resolved without source/test changes. Bundle-module combined coverage is 97.44%; all five Instamix-generated plugin kinds load offline from source and scratch installation. Independent review, normal-hook integration, release and native acceptance remain separate gates.

## Issue 256 lowercase bundles — 2026-11-17

App accepts canonical lowercase and established title-case bundle suffixes for all five kinds. Metadata, parent, import, inheritance, duplicate and symlink constraints remain. Focused bundle/filter/route checks: 139 passed; F821 lint passed. Actual Instamix draft output loads for all five kinds before and after scratch copy installation, preserving source bytes. Full prepared arm64 suite: 16,981 passed, 47 skipped, 30 failed in table embedding/Fly routing; delivery remains unqualified pending triage. Native, installed and release checks remain open.


## 2026-11-16 — vfjo: Box-based object JSON (Task 2)

- Fix: `vfjo.scale` scaled ghost hints. FontLab 9.1 JSON writes a top ghost as `thickness: -20` and a bottom ghost as `21`; after `scale(2, 0.5, origin=(100, 200))` on Lato `W` and `A` they became -10 and 10.5, which FontLab read as real stem hints. Ghost thickness now stays as it is while the hint point still maps; a real stem hint of exactly -20 or 21 units is also left unscaled. `move` never touched thickness. Offline tests in `tests/test_vfjo.py`; live re-check is in TODO.
- Live checks in FontLab 9.1 (team lead, 2026-11-17): `vfjo.scale` with a non-zero origin on Lato `W` (guideline + hints) and `A` (hints) gave correct nodes, widths, guides and stem hints (ghosts failed, fixed above). Edit > Undo three times after the `Edit JSON Nodes With vfjo Demo` output removed the outlines step, then `B.raised`, then `o.raised`. That demo gave `o.raised`/`B.raised` with every node +20 in both masters and unchanged point counts. `Copy Selection As JSON Demo`, `Object JSON Demo` and `Paste JSON Shapes Into Layer Demo` re-ran with a glyph open.
- Fix: `fontlabapp.plugins.bundles` rejected every per-file symlink that the 2026-11-16 plugmix install puts into `Extensions` ("entry module must exist inside its bundle"), so `registry.discover()` found 0 bundles. An entry module or `plugin.json` now counts as inside its bundle by its location: no `..` component, and its parent folder resolves inside the bundle; the file itself may link to a source checkout. Entries escaping through `..` or a symlinked folder are still refused. Tests: `tests/plugmix/test_issue210_bundles.py`; discovery over the real user `Extensions` folder finds 50 bundles with 0 errors, and `tests/test_issue253_reporters_inspectors_layout.py` passes 40/40. Live loading in FontLab not yet checked.
- Fix: `Copy Selection As JSON Demo`, `Object JSON Demo`, `Paste JSON Shapes Into Layer Demo` and `vfjo.paste` (shape data) called `CurrentGlyph().activeLayer()`. Live FontLab 9.1.9812 raised `TypeError: 'fgLayer' object is not callable`: `CurrentGlyph()` returns an fgGlyph, and `flGlyph(fg).activeLayer` is a property. New `json_data.current_layer()` returns `(flGlyph, flLayer)`; all four use it. Test fakes now model the live types (fgGlyph wrapped by `flGlyph`, non-callable `activeLayer`). Offline tests only; the live re-run is in TODO.
- New `fontlabapp.vfjo` casts FontLab 9.1 object JSON onto python-box: `loads`, `load`, `from_glyphs`, `from_clipboard` return `Objects`, whose `data` is the box tree, with `kind`, `glyphs`, `glyph_names`, `to_dict`, `to_bytes`, `envelope`, `describe`, `save`, `copy_to_clipboard`, `paste` and `copy`. Data is validated through `json_data.Envelope.parse` in and out.
- Safety: reading a missing key raises; a misspelt new key on a known level (root, glyph, layer, element, elementData, contour, transform, anchor, guideline, component) raises `UnknownKeyError`, also through `update`, `|=` and `setdefault`; `add_key` adds a key on purpose. Items added to lists (`append`, `extend`, `insert`, `lst[i] = ...`) and dicts assigned to existing keys are locked at their level. Keys are not converted (`conversion_box=False`, `box_dots=False`). Copies stay locked.
- Navigation: `layers`, `elements` (including nested elements), `contours`, `anchors`. Edits: `edit_nodes` (refuses point-count changes), `move`, `scale` (components and transformed elements change their transform, other elements their nodes; anchors, guidelines, hint points and thickness follow; optional widths), `rename`, `set_width`, `add_suffix` (drops Unicode values unless `drop_unicodes=False`). `paste` routes glyph data to `json_data.paste_glyphs` (`on_conflict` applies there only) and one kind of layer/element/contour data to `json_data.paste_shapes` on the current glyph's active layer; mixed data raises `ValueError`.
- New dependency `python-box>=7.1,<9`. `uv lock` could not resolve (unpublished sibling `fontlab-fontport`); no lock file is tracked.
- Tests: `tests/test_vfjo.py` with four live-exported fixtures (dict round trip, exact move/scale values for `o`, `Aogonek` and the scaled `dcaron` component, paste routing with fakes); with `test_vfjo_nodes.py` and `test_objects_json_data.py` 144 passed, vfjo coverage 96% (guards for `update`, `|=`, list `append`/`extend`/`insert`/setitem, unconverted keys, mixed shape kinds).
- Final review fixes: keys of every mapping added to the tree (`append`, `extend`, `+=`, `insert`, item and slice assignment, key assignment) are checked against the known keys at every depth; `paste(font=...)` with shape data refuses a font that is not current; vfjo re-exports `available`, `NEEDS_91`, `PARTIAL_TEXT`, `GLYPHS_UNDO_TEXT` and `PartialWriteError`; Undo text matches `json_data` (one step per pasted glyph plus one for the outlines).
- `import fontlabapp.vfjo` is lazy: names resolve on first use, so importing the package loads no implementation module. New demo `Scripts/Objects/Edit JSON Nodes With vfjo Demo.py` copies the selected glyphs with a `.raised` suffix, moves every outline node up 20 units with `edit_nodes` and `Node.moved`, then pastes the copies; offline tests in `tests/test_demo_scripts_objects.py` (9.0 message, no font, no selection, partial write, exact pasted nodes). Not yet run in FontLab.
- Checked live in FontLab 9.1.9812 with Lato (controller): python-box 7.4.1 installed in FontLab's venv; `from_glyphs(['o', 'Aogonek'])` → `add_suffix` → `move(40, 0)` → `set_width(w + 80)` → `paste` gave correct nodes, anchors, component `xOffset` values and widths in both masters; a misspelt read raised `BoxKeyError` and a misspelt write raised `UnknownKeyError`. `from_glyphs(['o', 'dcaron'])` → `scale(0.5, widths=True)` → `paste` halved widths, nodes and anchors of `o` and gave `dcaron` scaled component transforms in both masters; a misspelt key in an appended anchor raised `UnknownKeyError`. Not checked live: `scale` with an `origin` or on guides and hints, Edit > Undo, shape paste, the scriptmix demos.

## 2026-11-16 — Pasted JSON glyphs keep anchors, guidelines and hints

- `json_data.paste_glyphs` now adds each JSON layer's anchors (`flLayer.addAnchor`) and its guidelines and hints (one `flLayer.appendGuidelines` call) to the new master layer, as well as its outlines and width. Before, anchors, guidelines and hints were dropped.
- Live on 9.1.9812, Lato Desktop VFJ, Font window: glyph `o` was exported with `export`, edited as a plain Python dict (renamed `o.roundtrip2`, Unicode removed, width +100, every node, anchor and vertical guideline x+50) and created with `paste_glyphs`. Read back through the native layer API and through `export`, both masters had the edited width, 24 nodes all at x+50 and y unchanged, the `top` and `bottom` anchors at x+50, and the guideline and four hints (vertical hints at x+50); per layer the JSON had 2 anchors, 1 guideline and 4 hints, the same as `o`. Other glyph and layer properties (colour flag, OpenType class, `lastModified`) are still not carried.
- Tests: `tests/test_objects_json_data.py`, `tests/test_demo_scripts_objects.py` and `tests/test_api_facades.py` 159 passed.

## 2026-11-16 — Copy Selection As JSON pastes in FontLab

- New `json_data.copy_objects(package, objects)`: on FontLab 9.1 it calls `flModelProducer.copyToClipboard`, which writes FontLab's `vic/objects` types plus `application/json` and plain text; without that method it falls back to `copy_to_clipboard` (JSON and text only). It returns the copied object JSON.
- Copy Selection As JSON Demo uses it. Live on 9.1.9812 (owner hand test): a glyph copied this way pasted with Edit > Paste in the Font window and in a Glyph window, in both masters. Paste of copied shapes is not checked.
- Never call `flModelProducer.getObjectsFromClipboard()` or `getObjectsFromData()` on 9.1.9812: the binding crashes (Fontlab/fl#8655). `read_clipboard` does not use them.
- Tests: `tests/test_objects_json_data.py`, `tests/test_demo_scripts_objects.py` and `tests/test_api_facades.py` 157 passed.

## 1.2.28 (2026-11-16) — install.vfpy is the fontlab-instamix stub

- `install.vfpy` is now the short fontlab-instamix stub. It installs
  fontlab-instamix from PyPI when it is missing, then installs this checkout from
  its `[tool.fontlab-install]` table. The large legacy installer is gone.
- Tests of legacy installer internals were removed or rewritten for the stub. The
  initScript startup block is now written by instamix.
- `tests/test_plugins_startup.py`: the install-failure hook test no longer depends
  on a `fly.ap.plugins` alias cached by an earlier test.
- README describes the stub install.

## 2026-11-16 — Object JSON uses FontLab's clipboard type

- `json_data.copy_to_clipboard` now writes MIME `application/json`, the type FontLab 9.1's own Copy writes (as `public.json` on macOS), plus plain text. `read_clipboard` reads `application/json` first and still accepts the older custom type.
- Live in FontLab 9: `read_clipboard` read FontLab's own Copy of glyph "a" (10,496 bytes) and decoded both masters. Our Copy writes only `application/json` and plain text, not FontLab's `vic/*` types; whether Edit > Paste accepts that is not verified.
- Tests: `tests/test_objects_json_data.py` 60 passed.

## 2026-11-16 — TMetrics text of unknown glyph names

- With HarfBuzz installed, text made only of unknown `/name` tokens (for example `/zzz /qqq`) showed "Cannot shape: 'NoneType' object is not iterable": the HarfBuzz buffer was empty and uharfbuzz returns no glyph lists for it. `shaping.shape` now returns an empty run with one "unknown glyph name /…" note per token.
- Test: `test_shape_when_only_unknown_glyph_names_then_empty_run_with_diagnostics`; shaping and TMetrics test files with uharfbuzz: 187 passed.

## 2026-11-16 — TMetrics reads the font once per external edit

- `TMetrics.follow()` forgot the font reads, re-read the font for its fingerprint, then called `refresh()`, which forgot and re-read everything again. It now re-shapes from the reads it just made. A change notification now reads the kerning, groups and names once instead of twice.
- Measured live in FontLab 9 on i2-lato.vfj (3055 glyphs, fontport 8ffb9af, lane source loaded for the run): follow 1.57 s before, 1.13 s after; refresh about 0.75 s. Most of what remains is one whole kerning read through fontport (about 0.75 s).
- Tests: new `test_follow_when_font_edited_then_whole_font_read_once`; the TMetrics test files give 30 passed and 8 skipped (uharfbuzz not installed in this venv).

## 2026-11-16 — TMetrics typing with older Fontport (source only)

- TMetrics no longer scans the whole font once per glyph on every key when fontport lacks `glyph_summaries`. On older fontport (630edf1) every `font[name]` re-lists the layer to check the name, and each key asked `font[name]` for every glyph (HarfBuzz font snapshot, fallback layout and per-cell side-bearings), so a key cost about N whole-font scans (N^2 work) on an N-glyph font. `FontReads` now keeps each glyph object until the next re-read (a missing name is asked again), iterates through that memo, and side-bearings for the default layer go through it.
- Scan counts per key with an old-fontport double (each `keys()`, `in`, `font[name]` is one whole-font scan), typing `AVA` after `AV`: before 309 (N=300) and 1209 (N=1200) on the fallback path, 606 and 2406 with HarfBuzz; after 0 for both N and both paths (a new `/name` token costs one `in`). The first read after a font change still asks each glyph once.
- Tests: 5 new/changed tests in `tests/test_tmetrics_font_reads.py`; focused TMetrics/shaping files 204 passed; coverage of `_font_reads` and `tmetrics_model` 99%. Not checked live in FontLab.

## 2026-11-16 — Object JSON for FontLab 9.1 (source only)

- New `fontlabapp.objects.json_data` for FontLab 9.1's object JSON (`flModelProducer.getClipboardDataJson` / `getObjectsFromJsonData`): an `Envelope` model that parses and rebuilds the singleton, `objects` and empty shapes exactly; edit helpers (`rename_glyphs`, `unique_name`, `unique_glyph_names`, `filter_layers`, `set_advance_width`, `drop_unicodes`, `only_glyphs`); `describe`; and native wrappers `available`, `export`, `decode`, clipboard (own `application/x-fontlab-objects+json` plus text) and UTF-8 file save/load. `decode` always passes a `QByteArray`, because Python `bytes` crash FontLab 9.1.9812, and turns FontLab's `None` into `ValueError`.
- `paste_glyphs` creates new glyphs through `creation.create_glyphs` (never `addGlyph`), with unique names, per-master advance widths matched by layer name and outlines filled in the same history commit; `paste_shapes` adds decoded shapes or contours to one live layer in one `history.commit`.
- Seven new `Scripts/Objects` demos: Object JSON (read-only tour), Copy Selection As JSON, Paste JSON Glyphs, Paste JSON Shapes Into Layer, Export Glyphs To JSON File, Import Glyphs From JSON File and Edit JSON Before Paste. On FontLab 9.0 each says it needs 9.1 and changes nothing.
- Tests: 48 module tests (99% coverage of the new module) and 23 offline script runs pass. Live in FontLab 9.1 (Lato VFJ, through the module, not the script dialogs): export and describe, paste_glyphs (a -> a.1, o -> o.1 with per-master widths and outlines, Unicode dropped), a Unicode clash dropped with a note, paste_shapes (3 -> 5 contours) and bad-JSON rejection work. Undo/Redo, the partial-write path, the auto-glyph skip, FontLab's own clipboard interop and the script dialogs are not checked live.

## 2026-11-16 — TMetrics typing speed

- TMetrics: typing in the text field no longer re-reads the whole font on every key. New `fontlabapp.fontui._font_reads.FontReads` keeps kerning, groups, the default layer and glyph outlines per font. It is dropped when the font changes (change notification, a different font, or a master switch without a notification) and when `follow()` runs. Outline read errors are not cached. The text callback now passes `text_callback` so the host refreshes only the text.
- Measured live in FontLab 9 on Lato with the lane source loaded: about 0.85 s per key before, 0.11–0.14 s after. Needs fontlab-fontport with fast `glyph_summaries`/`has_glyph` reads for the full gain; older fontport still works, only slower.
- Pre-push gate fixes: `refresh()`, `set_text()` without a text signal and `follow()` after an external change re-read the font again; typed `/name` tokens for a glyph added since the last read re-read the font; `model.source` returns the font itself, not the read memo; writes to `model.font.info` pass through to the font. The API map now counts 1024 modules (`fontui._font_reads` row; docs pins updated).
- Pre-push gate passes: 16,858 tests pass with 31 skipped, 869 Pens tests pass and coverage is 95.76%; 15 new tests in `tests/test_tmetrics_font_reads.py`. Independent review approves. The installed (released) build is not yet verified live.

## 2026-11-16 — Reporters fit, lazy Browser thumbnails, component bases editable

- Docs: the API map now counts 1023 modules. The frozen guide test pins the reviewed `core.sharing`, writer re-export and `fontui.native` additions, so the Documentation workflow passes again.

- Reporters panel: size the dock from the same cell arithmetic its reflow uses, so it reaches 3 columns; on Qt 5 hosts without `QWidget.screen` fall back to `QApplication.desktop()`; tolerate missing geometry attributes without recording an error.
- Glyph Browser: build thumbnails lazily for rows near the viewport (geometry bisection, cached), instead of all glyphs at once. This removes the 30-second-plus hang when Node Counts or Glyph Browser opens a 3,055-glyph font.
- Filters, Outline Doctor, Interpolation Doctor, studio contour selection, Align & Nudge and Transform Studio point moves no longer refuse a component base glyph (for example `a` in Lato) as a "shared outline". New `fontlabapp.core.sharing.element_shared` subtracts the counted component shapes from `referenceCount` (measured live in Lato: count = 1 + component shapes); a truly shared or uncountable element is still refused. Bake and ownership decisions keep the raw count.
- Filters: Slant and Scale no longer fail post-write verification on float drift. FontLab round-trips node positions through its own float math (1 ULP on non-integer results), so the read-back now accepts x/y within the private `_COORDINATE_TOLERANCE = 1e-6`; ids, node flags, smooth, transform and counts stay exact.
- Owner local history 71332cd (v1.2.14 line) is merged into main so the owner checkout can fast-forward.
- Pre-push gate: 16,839 App tests and 869 Pens tests pass, 31 skipped; all 23 changed modules at or above 80% coverage. Final whole-branch review approves. Nothing here is verified live in FontLab yet.

## 2026-11-15 — Node Table compact actions in focused source

- Group the existing Refresh, Read Canvas Selection and Apply buttons in one horizontal row, preserving their callbacks, ownership, edit guards and embedded/standalone routes.
- Focused checks pass 81 tests in 2.75 seconds; the two compact-layout cases fail on old source. Pinned Ruff F821 passes. Real offscreen Qt table height gains 62 pixels at both checked sizes; the 420 × 320 action row fits without overlap. Minimum-size hint becomes 346 × 164.
- Independent specification and quality review passes. The controller required gate passes in 307.370 seconds: 16,802 App tests pass with 31 inherited skips and 870 Pens tests pass. Complete node_table.py combined coverage is 98.60% over 360 statements and 140 branches. An initial gate exited 3 before tests for missing upstream baseline; after the owned branch tracked origin/main, tests ran once without assertion, skip, oracle or coverage-rule changes. Only the two reviewed documentation precision edits occurred during that successful gate; source/tests stayed unchanged.
- Final scoped graph analysis is LOW with six nonempty identifiers across six files and zero reported affected flows. Retain the index omissions of 5,230 unranked entrypoints, 1,269 skipped callees and 36 cut walks; this does not establish whole-program clearance.
- Normal main delivery, actual remote SHA and exact-commit CI, release/artifacts, matching installation and native theme/history/Undo/Redo/reopen acceptance remain open; automatic history refresh remains held.

## 2026-11-15 — TMetrics event-local path reuse qualified in focused source

- Reuse prepared Qt paths for repeated outline recordings within one paint call, preserving empty outlines and rebuilding on every later paint. Keep occurrence-specific transforms, colors, open/closed brushes, inverse-scale stroke and cleanup.
- Existing focused tests pass 63 cases in 1.82 seconds; four preparation-count regressions fail on the old source. Real Qt geometry and injected partition/replay/draw failures remain covered. Independent source specification and quality reviews pass.
- The exact unchanged controller gate retry passes in 321.399 seconds: 16,800 App tests pass with 31 existing skips, and 870 Pens tests pass. Complete TMetrics combined coverage is 98.34% over 613 statements and 172 branches. Pinned F821 lint and whitespace pass; four current Scriptmix modules pass 183 tests. The original standalone Qt segmentation fault and unavailable coverage remain recorded in WORK; no fixture, skip, oracle or coverage rule changed.
- A bounded source fixture retains all 120 draws over 16 paints while reducing path construction from 120 to one per paint. First-paint time changes from 4.966 ms to 2.102 ms and following-paint median from 2.425 ms to 2.035 ms, using a recording painter with real Qt conversion. Physical typing and native visible-frame behavior remain unproved.
- Final source graph is LOW with 19 symbols in six files and zero reported flows; the integration graph before the document update is LOW with 14 nonempty symbol IDs in six files and zero reported flows. The final scoped result after the document update is LOW with 15 nonempty symbol IDs in six files and zero reported flows; only the unchanged following WORK Spacing Studio heading is additionally mapped at the documentation hunk boundary, with all prior IDs and flows unchanged. Retain incomplete-index caps (5,230 unranked entrypoints, 1,269 skipped callees, 36 cut walks) and receiver-typing omissions. Normal main delivery, actual remote SHA and exact-commit CI, release/artifacts, matching installation and native acceptance remain open.

## 2026-11-15 — Spacing Studio fresh-source refresh in focused source

- Refresh and attached Undo/Redo actions reread displayed spacing/reference data on the captured font and master, preserving typed controls. Invalidate accepted writes until explicit Preview; keep deep Apply source/layer guards.
- Clear selected alternate-layer snapshots without selecting or recapturing them. Recompute captured comparisons and keep clipboard data aligned with displayed reference rows. Missing targets or read failures visibly refuse and clear stale rows; owned cleanup remains retryable.
- Existing focused module: 92 passed in 4.17 seconds. Independent source specification and quality reviews pass. Controller gate passes in 306.81 seconds: 16,793 App tests pass with 31 existing skips and 870 Pens tests pass; all four complete changed modules have combined coverage of 96.77%, 98.68%, 97.64% and 97.40%. Pinned Ruff F821 and whitespace pass. Eight Scriptmix modules pass 338 tests with two existing skips; frozen source/tests remain unchanged.
- Fresh integration graph risk is HIGH: 40 nonempty symbol IDs, nine files and 14 affected flows. Retain the historical raw CRITICAL 26-symbol/619-process result and incomplete-index caps (5,230 unranked entrypoints, 1,269 skipped callees, 36 cut walks). Normal main delivery, exact-commit CI, release/artifacts, matching installation and native acceptance remain open.

## 2026-11-15 — Exact API-map successor provenance in documentation checks

- Preserve both historical frozen guide hashes while qualifying the reviewed public follow_history export addition against an exact current canonical digest and an exact single-addition reversal to the original historical digest.
- Preserve every original module/reporter/native-limit/source-census assertion. All 37 docs tests and the pinned strict build pass; unrelated title/export/tail mutations still fail the actual test and both strict digest checks.
- This is local documentation-oracle qualification only. Independent review, ordinary main delivery, exact-commit CI and release remain pending; guide sources, runtime, workflows, dependencies and publication holds are unchanged.

## 2026-11-15 — Kerning draft continuations and public contracts qualified in source

Keep table-only pending text stale across a refused focus-loss commit, return to the captured font and another history event. Invalidate acceptance before every explicit Preview target read, so early refusal disables Apply. Refresh failures also invalidate partially prepared Pair Editor drafts without clearing them. Public help names Preview Changes for staged recovery when manual Refresh is guarded.

Add the public history service to the actual API-map row and strict export/cold-import contracts; all 1,022 module/domain-count checks remain. Final focused App checks pass 306 tests in 8.70 seconds. Matching isolated Scriptmix assertions preserve exact drafts/errors/table rows and native/history state on refusal; four separate existing modules pass 134 tests. F821 and whitespace pass in both repositories. Independent re-review, complete controller gates, generated documentation, delivery, installation and native acceptance remain open.

## 2026-11-15 — Kerning Studio history refresh qualified in focused source

- Re-read captured-font kerning caches and tables after attached Undo/Redo actions, preserving the selected master, numeric/control/filter drafts and consolidated-controller consistency. Refuse missing or changed targets without native writes.
- Invalidate Stage and derived plans; retain Pair Editor staged values and active cell text, requiring explicit Preview to accept a fresh baseline. Reuse owned signal disconnection, failed-close retry and late-callback guards; retain a disclosed manual Refresh fallback.
- Focused real Qt/source checks pass 74 tests in 3.79 seconds; required F821 lint passes. Independent review, complete controller gates, current Scriptmix qualification, main/release/installation and FontLab native acceptance remain open.
- Review corrections rebase accepted cell comparisons against fresh native rows, preserve staged/added pair identities and uncommitted text, freeze displayed master columns before target checks, retain drafts on refused Apply, and let explicit Preview recover without hooks. A public lazy fontui history facade repairs the unchanged Studio import boundary. All 191 focused checks pass in 6.22 seconds; independent re-review and complete controller gates remain open.

## 2026-11-15 — Metrics captured-target history refresh in source

- Refresh the shared Metrics plan and component facts after connected Undo/Redo actions without recapturing host selection or master. Preserve settings, pending numeric text and existing consent binding. Use selection explicitly recaptures glyphs/current master; All masters remains available.
- Add the same fresh read as a compact manual Refresh fallback. Refuse missing captured fonts, glyphs and masters; retain guarded owned history signals and close disconnection. The obsolete Use selection instruction is removed; unavailable history actions retain an accurate manual Refresh hint.
- Focused source and real Qt checks pass 56 tests in 2.83 seconds, including action ordering, fresh auto warnings/Apply, missing targets, refused attachment and late callbacks after close. Required F821 lint and whitespace pass. Independent review, complete controller gates, Scriptmix consumers, delivery and actual FontLab/native acceptance remain open.

## 2026-11-15 — Master Text actions share one row locally

- Place the existing Load presets, List as Masters and Close buttons together at the bottom of the shared panel, preserving their order, callbacks and saved geometry.
- Existing real-Qt workflow asserts aligned, ordered, contained actions; all 24 panel tests pass. Native FontLab, both themes, installation and delivery remain unqualified.

## 2026-11-15 — Conditional installer staging repaired locally

- Evaluate conditional dependencies with canonical packaging in uv's external target Python before any sibling installer executes. Inactive requirements cause no sibling writes; active constraints still reach the unchanged uv resolver.
- Preserve exact original requirement strings and installer-managed origin protections. Bind --target resolution to the concrete Python used for marker evaluation; retain explicit interpreter destinations. Refuse invalid/helper results and unprovable no-uv requirements before sibling staging.
- Focused source regressions cover false/true markers, version rejection, URL semicolons, invalid input and helper failures. Four actual offline cross-version cases pass with Python 3.11.14 driving target 3.11.18. Independent review, complete controller gates, propagation, release, installation and native qualification remain open.

## 2026-11-15 — Source archive installer payload repaired locally

- Include `install.vfpy` in the existing explicit sdist selection. The actual build regression reproduces its prior omission, then verifies exact source bytes, the FLM header and genuine PKG-INFO version lookup from the extracted installer without running its main function.
- The focused installer/startup cohort passes 133 tests in 5.84 seconds; required F821 lint passes. Installer core bytes are unchanged. Independent packaging review, combined main gates and fresh release artifacts remain pending; the unpublished 1.2.19 candidate is preserved, not released. T28, shared-copy propagation, provider closure, installation and native holds remain open.

## 2026-11-15 — Same-version installer origins fenced in source

- Reproduce version-only uv constraints replacing a managed editable origin with a same-version wheel, directly and transitively, in interpreter and target modes. Retain the reviewed preimage.
- Add documented per-package binary/source restrictions alongside local version pins. All four actual wheel-origin regressions now refuse before mutation, preserving source links, metadata and complete fixture source bytes; installed matching-version, development-version and extra cases still pass.
- Focused installer/startup checks pass 132 tests in 4.06 seconds. Raw coverage collection passes the same 132 tests in 6.30 seconds; complete-module aggregation and acceptance remain controller work. Independent re-review, full gates, source propagation, ordinary delivery, release and installation remain open. False-marker sibling staging is still an unresolved T28 defect.

## 2026-11-15 — Shared installer dependency source checks

- Keep original version, extra and marker requirements after sibling installation; uv resolves them with temporary pins protecting installer-managed local versions, including active-cycle records. Generated local metadata carries optional dependencies and preserves existing markers and URL semicolons.
- Without uv, reject unverifiable requirements before site preparation or obsolete-script removal, and raise for missing bare dependencies. Preserve ownership logging before dependency execution and report completion only after successful resolution.
- Owned offline uv checks reject local 1.2.8 against >=1.2.10 and accept 1.2.10 in both interpreter/target modes with unchanged source links and payload bytes. The focused installer/startup cohort passes 128 tests in 3.70 seconds. The pre-existing eager sibling staging for false markers remains open in T28. This records final-resolver/source-fixture evidence only; review, shared-copy propagation, ordinary delivery, release, installation and native qualification remain separate and open.

## 2026-11-15 — App 1.2.18 release qualification retained

The preceding [App 1.2.18 release](https://github.com/fontlabcom/fontlab-fontlabapp/releases/tag/v1.2.18) binds reviewed source 8c1685f. Independent review qualifies ordinary main/tag/release delivery, both downloaded artifacts and isolated installed-file identity. Actual root installation, FontLab GUI/native behavior, history, Undo/Redo and saved reopen remain unproved. This release does not contain the new installer dependency repair.

## 2026-11-14 — Filter deletion target fence qualified in source

Deletion plans bind removal ordinals to the original ordered contour identities, geometry and native state. Changed targets are refused during compute, before history and again at writing after history initialization. Correct deletion preserves reverse removal, original contour retention, ownership safeguards and `Change.key` ordinals. Public Apply plans immediately before writing; the fix protects that planning-to-preparation/write interval. Public APIs and shared writer/history kernels are unchanged.

Controller RED: eight expected failures and one valid-deletion pass. Controller GREEN: 114 focused tests passed in 0.35 seconds; required F821 lint passed. Independent specification and quality review passed. Full normal pre-push gates, exact-commit CI, release, matching installation and native qualification remain pending. All-five-filter, whole-font/history, Undo/Redo and saved-reopen requirements remain open under the native hold.

## 2026-11-14 — Functional work order documented

- Added the owner's functional-progress-first guidance and repository-specific priorities, including cross-package compatibility and a later detailed testing pass. Existing mandatory hooks, holds and unfinished work remain in force.
- This change updates guidance and planning only; it establishes no new runtime, installed, native or release result.

## 2026-11-14 — Filter coordinates and TMetrics host-follow source fixes

Coordinate filters now convert requested layer-space points to each owned element's translated local coordinates before history. Finite, exactly reversible translations are supported; shared and linear-transformed elements remain refused. Complete transform and raw-node flag fences retain stale-plan refusal and post-write checks. Controller focused checks: 104 passed in 2.80 seconds; independent filter specification and quality review passed.

TMetrics host-follow avoids a second layout after successful synchronous text refresh when the fresh font fingerprint matches the drawing. Failed layout retries, observer-driven font changes and Echo invalidation remain covered. Controller focused checks: 63 passed in 11.67 seconds; independent TMetrics specification and quality review passed for the bounded source delta.

These are source results only. Broader verification before delivery remains pending; this round is not committed, released, installed or native-qualified. Physical typing latency, all five filters, whole-font/history, Undo/Redo and saved-reopen acceptance remain open.

## 2026-11-14 — Guarded documentation repair delivered

- Independent source and final delivery review accept source commit
  `2b53ca46463ef540a4913d42b4e2e06102d8c113` through the normal pre-push hook
  to actual main. Its generated child
  `3834bae3e42c32477a6d81e81ecd213476ab6f56` changes only sitemap.xml and
  sitemap.xml.gz; all 2,001 reviewed source payloads and modes remain exact.
- The accepted manual run retains all 16,688 ordered case identities/results:
  16,666 passes and 22 existing skips, with genuine released Scriptmix fixtures.
  All 37 docs tests and strict 54-file hash/mode parity pass. Five real-Git
  states preserve the original worktree/index boundary and fixture indexes.
- The unmodified normal hook separately passes 16,666 App tests/22 existing
  skips and 869 Pens tests with 95.76% existing coverage. No production module
  changed; no coverage threshold, assertion, skip or hook was weakened.
- [Documentation run 43554627631](https://github.com/fontlabcom/fontlab-fontlabapp/actions/runs/43554627631)
  passes both jobs at the exact source commit. Its qualifier checks the exact
  generated child, source epoch and output lineage; no separate child run or
  private Pages deployment is inferred.
- Close only the solved documentation-oracle source-review/main-delivery row.
  Matching installation, full provider closure, release, root installer and
  all seventeen native rows remain open. Retain historical setup/hook index
  failures with UNKNOWN writers, graph UNKNOWN/overflow/process omissions and
  degraded FTS; bounded delivery does not establish global preservation,
  native behavior or publication. Private Pages and Issue 123 holds remain.

## 2026-11-14 — Content-aware guarded documentation oracle

- Replace the reproducible-docs test's final name-only comparison with an
  explicit patch; disable external/textconv diff while preserving the original
  working-tree/index boundary and index-refresh guard.
- Add five real-Git cases: accept timestamp-only and staged/index-equal states;
  report unstaged bytes, deletion and executable-mode changes. Each oracle
  preserves raw index bytes and mode. The old oracle fails the two stat-only
  cases; the repaired oracle passes all five.
- Preserve every original full-output hash/count, source-epoch and lineage
  assertion. All 37 docs tests pass, strict output matches all 54 committed
  files and modes, and changed-test plus required F821 lint passes.
- This records local source qualification only. Independent review, combined
  controller gates, main/hook/CI delivery, installation and native acceptance
  remain separate. Runtime, dependencies, pins, workflows, source guides and
  generated output are unchanged.

## 2026-11-13 — Issue 255 verified release qualification

- [fontlab-fontlabapp v1.2.16](https://github.com/fontlabcom/fontlab-fontlabapp/releases/tag/v1.2.16) is released at `516f9dfba810e4a4cac5225ee817cd763a40410b`. Reviewed main/tag delivery, applicable CI and actual downloads match the qualified artifacts.
- All 146 Scripts and current examples/teaching use the reviewed Fly routes. The Vanilla tombstone teaches fly.gp.ui.session without changing its runtime contract; incoming Font Info and Master Text source/tests are retained.
- 16,666 source tests pass with 22 inherited skips; both tombstone statement/branch gates are 100% with zero exclusions. All 36 documentation tests and exact 54-file containing-source rebuild parity pass. Genuine wheel and actual-sdist ordinary cohorts each contain 28 compatible packages and match all 1,030 installed App payload files; lazy Scripts, intercepted startup/restoration and 19 archive/tombstone cases pass.
- Ordinary external installation is qualified; installed FontLab/native acceptance remains unproved under D43. Consumer setup still requires separately installing matching Fly >=1.3 in the same interpreter. Provider source installers do not automatically supply or enforce this prerequisite; no reverse mandatory Fly dependency is claimed.

## 2026-11-13 — Issue 255 residual teaching and consumer setup

Correct six current guidance claims to name `fly.ap` and the verified 146 Scripts
in 15 categories; preserve their detailed safety statements. The Vanilla
migration instruction now uses `fly.gp.ui.session`, while its canonical error
text and zero-import runtime remain unchanged. README and installation/startup
guides explicitly require separately installed Fly >=1.3 in the same interpreter:
the source installer copies Scripts and writes the startup block without
supplying/checking Fly. Missing Fly is caught by the existing startup block;
no installer, startup behavior or dependency metadata changed.

The docstring regression fails on the old instruction, then all five tombstone
checks pass. The complete changed module has 4/4 statements and 2/2 branches
covered, with zero exclusions; runtime AST outside the docstring is identical.
Fresh public e8b012e retains the incoming Font Info/Master Text changes. Both
baseline and final complete source runs pass 16,666 tests, 22 inherited skips and
227 warnings on arm64 Python 3.11.14. The final run takes 237.82 seconds. Pinned Ruff
F821 scope passes. Final adjacent-startup prerequisite prose additionally passes
119 README-reading source cases. The repeated hash-locked strict docs build,
36 tests and exact 54-file rebuild parity pass. This is source/stand-in and dirty
preview evidence; final artifacts, native and publication remain separate.

## 2026-11-13 — Font Info and Master Text complete source gates

Independent source and controller-result reviews pass for the combined App
79ec1f1 candidate. The complete uninstrumented App suite passes 16,666 tests
with the same 22 skips and 231 warnings in 275.85 seconds, without SIGBUS.
All 16,688 ordered cases match the preceding current-main run. The 22 retained
skips leave pinned cross-repository hash checks unexecuted. The complete
Scriptmix consumer suite separately passes 5,084 tests with six skips in
191.85 seconds; these results do not clear unrelated workflow gates.

Complete statement/branch coverage is 99.588% for Font Info, 94.921% for
Master Text and 100% for the demo, with zero exclusions. The reviewed bounded
replay passes all 191 cases, preserving the original 187 IDs and relative
order plus four lifecycle cases; all observed header returns are QHeaderView.
That replay uses the earlier current-main cohort and diagnostic observer,
separately from the uninstrumented full suite. Source and index guards pass.

The first current-main full run remains a failure: 16,665 passed, 22 skipped
and one missing fly.pens import with Fly 1.2.6. A separate successor uses
released Fly 1.3.0 at 1505b291, as required by the newer App demo routes; the
same source and assertions then pass. No dependency declaration or test was
changed to hide the mismatch. Both cohorts and their evidence are retained.

The operational full-source blocker is addressed for this exact cohort.
The underlying C++ corruption mechanism and a unique causal repair remain
unproved. Normal pre-push gates, actual main delivery/CI, release, installation
and native FontLab/PythonQt, both-theme and whole-font/history/reopen acceptance
remain open, as does the complete Issues 252/253 GUI scope.

## 2026-11-13 — Master Text preset item lifetime (source/Qt)

Master Text creates each preset with an explicit QListWidgetItem, matching the
existing Browser construction pattern. Retained item wrappers now invalidate
when the panel closes or its parent is destroyed, including after preset reload.
String-created items remained valid-marked after their native owner was deleted
in the tested PySide6 6.12.0 binding. Text, selection, proof dispatch, settings,
signal cleanup and the replacement path remain unchanged.

Four lifecycle cases fail on the original source and pass after the one-call
change. The 80-test Master Text suite passes. Combined compact Font Info and
Master Text checks pass 397 tests with no skips; complete changed-module coverage
is 94.92% for Master Text, 99.59% for Font Info and 100% for the demo, without
exclusions. These focused results qualify source/offscreen behavior only;
the subsequent complete-source qualification is recorded above. Delivery and
native acceptance remain separate.

## 2026-11-13 — compact Font Info forms (source/offscreen)

The existing 24-field editor form now scrolls inside a resizable Qt scroll
area. Apply, Revert and diagnostics stay outside it; the combined vertical
metrics report and Refresh remain visible below. Both real compositions share
the same field instances, parsing, staged edits and lifetime. The sample demo
requests 560 x 580 instead of 560 x 900. No dependency or public API changes.

The focused real/fake gate passes 317 tests in 20.87 seconds. All 48 real-Qt
geometry cases fit their exact 460/580/700-pixel requests at unchanged default
family and 9/13 pt, including read-only, long values and long captions. Four
unresized default openings stay within 580 pixels. The exact final regression
fails all 48 geometry and four default cases on original production bytes.
Every field is reachable through the outer scrollbar; inner text/report
scrolling, fixed controls, drafts, selection, Revert, Refresh, invalid Apply,
read-only keyboard refusal, complete UFO equality before/after teardown and
substantive repeat-close/DeferredDelete cleanup pass. An intentional sample
Apply is checked separately from the no-write comparisons.

Complete editor combined coverage is 99.59%; the complete changed demo launcher
is 100%, without exclusions. F821 and whitespace pass. These are source and
detached Qt results. Subsequent review and complete-source gates are recorded
above; release/install, native FontLab, both themes and history/reopen remain open.

## 2026-11-13 — Fly routes for App user scripts and examples (Issue 255)

All 146 App menu demos and six runnable examples access the relevant APIs
through Fly, including the 132 PythonQt and 126 FontLab native access sites.
Native access stays at its original lazy execution site. Dynamic toolkit/core
and editor module lists use Fly; canonical human-origin labels and module
metadata are preserved. Active authored guide/README examples, 16 source
teaching docstrings and the generated owned startup import use the same route.
Examples/startup require Fly 1.3.0 or later; library runtime imports and package
dependencies retain the canonical providers without a dependency cycle.

The complete source gate passes 16,608 tests with 22 existing optional skips
and 227 warnings in 274.70 seconds on arm64 Python 3.11.14. Every complete
changed Python module clears the unchanged 80% combined statement/branch gate:
17 source modules at 83.33–100%, 146 menu demos at 87.50–100%, and six examples
at 88.52–100%, with no exclusions or partial-branch exceptions. Real Fly finder
checks retain canonical App/Fontport/Pens identities and metadata; native
stand-ins separately retain identity and a None spec. The structural and facade
docstring gates validate Fly imports against canonical exports; missing-export
negative controls, feature coverage and stdlib-only demo imports remain.
F821 lint and whitespace checks pass. Graph change analysis retains HIGH breadth
risk and its explicit truncation/reflection limits.

Shared installers, library imports, internal batch transport, frozen provenance
and historical source hashes are unchanged. The standalone Fontport worker
verification probe stays canonical. Generated docs are rebuilt separately by
the qualified locked builder. Independent review, fresh-main integration,
final artifacts/ordinary installation and native loaded-route behavior remain
separate acceptance steps; this source evidence does not publish the site.

## 2026-11-13 — compact Font UI Lab reports (source/offscreen)

Anchor and Component Inspector keeps both ordered report tables beside its
frameless glyph preview. Unicode and Glyph Order Explorer keeps its Sequence
controls/proof above the Browser and moves metadata/status beside the preview;
only this embedded Sequence loses duplicate margins and its frame. Shared
Browser/Preview/Sequence APIs, launchers and the separate Studio build remain
unchanged. All records and full affine transforms remain available by scrolling.

Eight real-Qt regressions fail against the original production source. The
focused layout, Anchor/Unicode and composition/lifecycle checks pass 158 tests
in 6.72 seconds. Complete changed-module combined coverage is 93.45% for Anchor
and 90.75% for Unicode, with no exclusions. At the default font family, a
760 x 580 request remains 760 x 580 for Anchor at 9/13 pt and Unicode at 9 pt;
Unicode at 13 pt requires 760 x 584. Controls, selection, repeated/non-BMP data,
resize/scroll, detached-model equality and substantive cleanup are checked.

These are standalone Qt results. Independent review, combined-main gates,
release/install and native FontLab/both-theme/history/reopen checks remain open.

## 2026-11-13 — Filter selected-layer source repair qualified

Filter planning retains each selected native layer instead of substituting the
package's current master. It checks captured font/glyph/layer identities and
ownership before compute, then deduplicates by captured font/glyph/layer ids in
selection order. Distinct layers of the same glyph remain separate work items.
Whole-font automatic-owner/base refusals, selected automatic-layer skips,
shared/transform protection and the existing history/write kernel are retained.

Maintained regressions reproduce wrong-layer, lost-layer and missing ownership
refusals against the previous source. The focused Plugmix source suite passed
651 tests with zero native import attempts. Independent specification, quality
and combined-checkout reviews passed. The complete App gate passed 16,444 tests
with 22 existing optional skips and 231 warnings in 259.17 seconds. Complete
Filter Apply coverage is 169/169 statements and 78/78 branches, 100% combined
with no exclusions. External Plugmix passed 420 tests in 4.89 seconds; F821
lint and whitespace checks passed. Graph analysis reports seven changed files,
nineteen symbols and LOW risk, with broad flow-coverage limits retained.

Commit, normal push and exact-commit CI remain pending. Matching release,
installation and native Apply/Undo/Redo/save-reopen with complete-font
preservation remain open. This source repair does not establish the original
screenshot's cause.

## 2026-11-13 — TMetrics source delivered through the normal gate

The reviewed source milestone is on `main` at
`3a50a5c13183960d5f20d81e7f06b919fd5160d0`. The unchanged pre-push gate
passed: App 16,371 passed, 31 skipped, 227 warnings in 253.64 seconds; Pens
857 passed in 1.26 seconds. Complete `tmetrics.py` coverage is 597/604
statements and 162/168 branches, 98.32% combined, with no exclusions.

A separate provenance check passed 63 cases (154 deselected) in 1.05 seconds,
including all 31 known historical pinned-source parameter IDs. The primary
terse suite log does not identify individual skipped cases; this supplement
does not replace its counts or prove one-to-one skip correspondence.

[Documentation CI 43369379415](https://github.com/fontlabcom/fontlab-fontlabapp/actions/runs/43369379415)
succeeded at that exact source commit. Actual upstream `main` was verified at
`dfaf9000f5e23863fd52ea08ac62939775599afb`, its direct generated-output child,
which changes only `docs/sitemap.xml` and `docs/sitemap.xml.gz`.

Source integration is complete. Release, installed-source identity, external
raw text-field observer compatibility, native typing/visible-frame latency
and full font/history/Undo/Redo/reopen qualification remain open. No private
Pages publication or native acceptance follows from the source CI result.

## 2026-11-13 — TMetrics programmatic refresh source candidate

`TMetrics.set_text` now uses the synchronous text-change refresh when it
completes successfully, instead of repeating the same refresh. A private
generation advances only after the complete refresh, including layout. Unchanged
or truncated text, blocked signals and a failed first refresh retain the explicit
refresh path; ordinary signals and existing partial/error state are preserved.

Eleven real Qt5/Qt6 text-signal regressions cover callback order, reentrant text,
font rereads, blocked state, reshape/layout retry and owned cleanup. Other widgets
use the existing doubles. Final complete App: 16,380 passed, 22 existing skips,
227 warnings in 258.81 seconds (260.82 shell seconds). Whole TMetrics module:
98.84% statements, 96.43% branches, 98.32% combined, zero excluded lines. Qt5:
11 passed; Scriptmix S1/S2 and Issue 241 consumers: 182 passed. F821 passed.

A raw text-field observer that changes font data after the owned refresh must
request its own refresh; no maintained observer of that form was found. This is
an independently reviewed source milestone, subsequently delivered as recorded above.
Native typing/visible-frame latency, installation and broader GUI acceptance
remain unproved; no claim resolves the reported one-second delay.

## 2026-11-12 — Plugmix Filter refusal diagnostics (source)

Filter Apply retains the planner's explanatory rows in its status instead of
reducing a refusal to the glyph name. Source regressions cover full and partial
refusal display and all five filters' automatic-layer/base protection. Native
screenshot diagnosis and installed/history/reopen acceptance remain separate.
The review correction retains every skipped/refused name when only some targets
have explanatory rows; reason labels are appended without parsing display names.
## 2026-11-12 — compact Reporters and glyph inspectors (Issue 253, source/offscreen)

- Reporters reflows the same owned checkbox controls into one to three measured
  columns, preserving complete labels, state synchronization and callbacks;
  narrow docks use a bounded scroll area.
- Shared glyph browsers put their existing frameless preview on the right.
  Search/display controls share a row; existing zoom and six preview options
  remain visible. Metrics and master point inspectors use compact tables with
  visible selected-width matches, master counters and signed reference deltas.
- Focused verification: 267 passed; all five complete changed modules exceed
  95% combined statement/branch coverage without exclusions. Real Qt5 and Qt6
  each pass 20 9pt/13pt geometry/render cases, including 760×580 inspectors.
  Native FontLab appearance, installed origins and lifecycle remain open.

Fix round 1 adds property-shaped PythonQt size hints and guarded optional
initial fitting after registry listener registration. Property/method and
screen/resize-failure cases preserve subsequent show, toggle, sync and close.
This fresh-main composition still requires independent review; offline bindings
do not prove native FontLab behavior.

## 2026-11-12 — D46 documentation pass (Issue 250)

- Landed on `main` this session: the Issue 254 `install.vfpy` series (`d9e6058` Extensions bundle links, `76882a0` too-old App message, `dbcac43` and `50a913d` stale dist-info refresh); `be085e8` and `3083abe` (binding-neutral `status.text`, Metrics status plurals); `6ed1822` (compact table layouts, E01 embedding); `5e94a6e` (glyph notes compared as GLIF stores them); `edc3265` (`./test.sh` defaults Qt to offscreen); `c97bbee` (kerning-limit stand-in pinned to Examples); `585a307` (opt-in real-dialog lesson route test); `c202504` and `78ee651` (WP07 identity studios re-derived, api-map re-pinned to 1007); `89055df`, `7188df9` and `42029bf` (WP03 spacing and kerning studios re-derived, module count 1022); `5eb5147` and `286cc7a` (TMetrics fractional-kerning refusal, row 132). No source changed in this pass.
- New open TODO rows: the Issue 242 Node Inspector series, the WP04/WP04b/WP07 branch deltas, the owner's Apache-2.0 licence decision (Q5) and the `install.vfpy` pens floor. The licence row counts 742 Apache-2.0-only files of 795 with SPDX headers (corrected from 810), and a further row repoints the `NOTICE` evidence pointers that still name `WORK.md`. Native checks stay open.
- `WORK.md` is a short status stub; its earlier 18,882-byte content (SHA-256 `c937602554d94479ece7be5a1c5cc49f097d131d8d5a0c07850b593359cc1789`) stays archived on the workspace data volume.

## 2026-11-12 — Issue 250 WP03: spacing and kerning consolidation, re-derived onto main 286cc7a

- Eight tabbed studios (S26, S39–S42, S48–S50) re-applied on the WP01 resolver and WP02 shell
  from the reviewed lane, file by file against current main (not the old unreviewed base):
  kerning browser, batch, studio, proof, advance widths, vertical metrics and spacing studio,
  plus the `Kerning Proof Studio Demo.py` demo, core scripting facades, AppShell readiness and
  the API map (956 modules).
- `tests/_studio_qt.py` gains `isolated_studio_modules`: it removes cached `fontlabapp.studios.*`
  modules before a test and restores them (and the parent attributes) afterwards. The lane's
  teardown popped them, so the WP03 files running first broke 28 `advance_widths` tests and
  `test_native_text_canvas_when_painter_or_owner_fails_then_cleanup_is_contained`.
  `tests/test_studio_qt_isolation.py` is the oracle; removing the restore line fails it.
- The Marks tab reads Unicode values from `package.fgPackage` and refuses a glyph FontGate lacks with a named error
  (`widths.glyph_unicodes`, ported byte-exact from Scriptmix main D36-1/F43-1). The lane read `glyph.unicodes`,
  which `flGlyph` does not have, and its test fakes hid it. Re-pinned the Zero-Width Marks original in the parity test.
- Behaviour change: the Exceptions Finder apply path now returns False and sets the status to `stale` when the
  pair's class changed since the scan; the retired Scriptmix tool raised ValueError. Covered by tests in
  `tests/test_studio_kerning_tools.py::test_exceptions_tab_when_stale_then_refused`.
- Coverage: the 46 changed source modules (15 new) are all at or above 90.3% combined; quality.sh reports 0 of 50
  modules below 80%. Mutants: reading `glyph.unicodes` instead of `package.fgPackage` fails 5 tests, removing the
  named refusal fails 2.
- Evidence: full `./test.sh` 15445 passed, 22 skipped on the merged head. Scriptmix half follows separately.
  Native FontLab checks stay open.
## 2026-11-12 — UFO roundtrip report ignores empty-note noise (Issue 250, TODO:14)

- `fontui.ufo_roundtrip_editor._snapshot` now compares glyph notes as GLIF stores them (`_glif_note`: lines stripped, blanks dropped, empty is None). The 615 `''` to `None` rows in report 18 came from fontTools `glifLib._writeNote`, which writes no `<note>` for an empty note, so the writer cannot preserve it and the UFO format has no empty note; Fontport is unchanged. Test `test_snapshot_when_empty_or_padded_glyph_note_then_equals_what_glif_stores` fails without the change and also pins that a real note edit still reports one row. Analysis: `issue250/reports/app-14-notes.md`.

## 2026-11-12 — Too-old App message names the bundle and the fix (Issue 254)

- A bundle rejected for `min_app_version` now says `plugin <name> requires App <min> or newer (installed <running>); re-run fontlab-fontlabapp/install.vfpy` instead of a bare `plugin requires App <min> or newer`. Re-running the installer refreshes the recorded App version. Test `test_manifest_when_app_too_old_then_message_names_bundle_versions_and_installer` failed before the change. `test_reinstall_when_app_version_changed_then_stale_dist_info_is_replaced_by_the_current_one` pins that re-running the installer replaces a stale `1.2.9+74.g621033e` dist-info with the current version, which is what lets the bundles load. `test_install_when_unlogged_stale_dist_info_exists_then_it_is_replaced_by_the_current_one` plants a 1.2.9 record the install log never saw; it fails with `remove_old_dist` removed (mutant log: reports/mutant-i254-refresh.log), so that function, not the log-driven cleanup, is what is pinned.

## 2026-11-12 — E01 embedded table footprint (Issue 253-C, source/offscreen)

- E01 retains each table's measured initial minimum before Profile reparenting.
  Real Qt5 assembly covers all seven selected tabs and four eager table profiles
  at 9pt/13pt: 28 passing cases, including guarded Refresh and owned shell cleanup.
  The complete changed E01 module has 100% source line/branch coverage. Smaller
  displays, installed PythonQt behavior and QObject destruction remain unverified.

## 2026-11-12 — Compact table filter layout and shared demo (Issue 253-C, source/offscreen)

- Shared basic/custom/official table panels use aligned filter/date rows and
  flat inner containers. The first/date columns fit displayed contents and
  descriptions receive remaining width; one initial font/content sizing pass
  makes room for eight rows while Refresh preserves user resizing.
- Table Filter Demo is a lazy, import-safe launcher with two behavior statements;
  `qt.tables.filter.model.show_demo` owns its unchanged eight-row table, key and
  captured object lifetime. The API map includes this additive helper.
- Physical Qt tests cover complete rows and rendered text widths, larger fonts,
  minimum-size controls, official visibility, label buddies, empty/large refresh
  and retained geometry. The focused gate passes 352 tests with complete line
  and branch coverage in all three changed production modules. Native sizing,
  installed/cached origins, dark/light FontLab behavior and the wider script
  denominator remain separate pending acceptance.

## 2026-11-12 — Copied installs keep the bundle kind folder (Issue 254 fix)

- A copied (non-Git) install linked bundles to `Extensions/<id>/bundles/<Name>`; the plugin core resolves links and requires the parent folder to be the kind folder, so it rejected every copied bundle. Copies now live at `bundles/<kind>/<Name>` (found by installing the Plugmix pack from a non-Git folder). `tests/test_install_extensions.py` asserts the kind folder.

## 2026-11-12 — Metrics "layers skipped (auto)" singular (Issue 250, follow-up to :50)

- The Metrics panel apply status now says "1 layer skipped (auto)" instead of "1 layers skipped (auto)" (`src/fontlabapp/metrics/panel/ui.py`); the plural is unchanged. Test `test_panel_when_apply_skips_one_auto_layer_then_status_uses_singular` failed before the fix; forcing the plural again fails it.

## 2026-11-12 — install.vfpy links Extensions bundles (Issue 254)

- New optional `[tool.fontlab-install] extensions = "Extensions"`: every `<extensions>/<kind>/<Name>.fontlab<Kind>` folder (kinds reporters, filters, tools, palettes, general; must hold `plugin.json`) is linked as an absolute symlink into `<FontLab data>/Extensions/<kind>/`. A copied (non-Git) install copies the bundles under `Extensions/<id>/bundles` and links into that. Links are recorded in `install.log` `files`/`links`.
- A target that is not our recorded link is printed as `Kept (foreign bundle, not overwritten)` and never touched, on install, reinstall and uninstall; a link removed by hand or replaced by the user's own folder or link does not fail uninstall and the replacement stays. Stale links of bundles dropped from the source are removed only while still exactly ours.
- A required dependency with no sibling checkout is now stated plainly ("no checkout of it sits beside ...") before the missing-dependencies line.
- `BUNDLE_KINDS` in the installer is pinned against `fontlabapp.plugins.bundles.KINDS`. Tests: `tests/test_install_extensions.py` (23, including a logged link re-pointed to the user's own target). Repos without the key behave as before.

## 2026-11-12 — Binding-neutral status text; Metrics status wording (Issue 250, TODO :225, :50)

- `fontui/batch.py` and `fontui/designspace.py` append callback errors to the status via `qt_value(self.status, 'text')`, so a method-style `text()` (PySide) no longer leaks a function repr. Tests cover method and property labels (`tests/test_cov_ui_batch.py`, `tests/test_issue205_fontui.py`); the method variants failed before the fix. Reverting either call to `.text` fails them.
- Metrics panel apply status uses "1 layer in 1 glyph" and ends with "after Edit > Undo press Use selection to refresh the plan" (`src/fontlabapp/metrics/panel/ui.py`, `tests/test_metrics_panel.py`). Refresh-on-undo-notify stays an open native TODO row.
- TODO :21 (real-dialog lesson-route test) was the same work as :15 (366d95e) and is already gone from TODO.

## 2026-11-12 — Lesson routes run against the real packaged dialogs (Issue 250, TODO :15)

- New opt-in `tests/test_core_pythonqt_profiles_lessons_real.py` drives the E01 Glyph Name Filter,
  E03 Glyph Metrics Model and E03 Glyph Metrics Form routes against the packaged
  `fontlab_python_lessons` dialogs, models, snapshots and `.ui` form. Only the host surface
  (`fly.qt`, `fly.ap.core.scripting`) is replaced by Qt-backed stand-ins, so drift from the
  App-owned fake in `tests/test_core_pythonqt_profiles_widgets.py` now fails a test.
- It skips with a stated reason unless `FONTLAB_EXAMPLES_LESSONS_SRC` or the sibling
  `../fontlab-python-examples/lessons/src` exists. Two mutant tests copy the packaged source
  and break `panels.py` (prefix filter dropped; `package_id` not passed to `select_glyphs`);
  the scenario must raise `AssertionError` for each.
- Not claimed: real FontLab, the real `fly.qt` PythonQt wrappers and native Undo/Redo.

## 2026-11-12 — Kerning-limit stand-in pinned to Examples (Issue 250)

- `test_strict_summarize_kerning_when_compared_with_examples_then_limit_contract_matches` (tests/test_fontui_getgo_labs.py) loads the real `summarize_kerning` from the sibling `fontlab-python-examples` (native import stubbed, Examples untouched) and compares it with the App-owned `_strict_summarize_kerning` on `None`, `0`, `1`, `5`, `99`, `-1`, `2.0`, `1.5`, `True`, `False` and `'5'`: same refusal text, same `pairs` and `limit`. It skips only when the sibling file is absent.
- Mutants: loosening the stand-in's type check, shifting its bound, or changing its slice fails the test; weakening the Examples validator (`type(limit) is not int` removed) fails 5 cases, so drift on either side is caught.

## 2026-11-12 — `./test.sh` runs Qt offscreen (Issue 250)

- `test.sh` now exports `QT_QPA_PLATFORM=offscreen` unless the caller already set it (an explicit value, even empty, wins). Before: under cocoa, `tests/test_find_files_dialog.py` failed 5 of 19 (`test_profile_window_size_table_editing_and_all_terminals[bytes]` and the four `test_physical_long_home_*`); after: 19 passed with `env -u QT_QPA_PLATFORM ./test.sh`.
- `tests/test_test_sh.py` pins unset -> offscreen and caller value kept (cocoa, empty); a mutant forcing offscreen fails it.

## 2026-11-12 — WP07 docs pins re-pinned after the CI Documentation failure

The Documentation workflow on e1a08ec failed one test because `quality.sh coverage` does not run
`tests_docs`: `tests_docs/test_site.py` pinned 941 `fontlabapp` module rows and the api-map hash
of the pre-WP07 map. The 66 WP07 module rows make the honest count 1007 (the map was already
rebuilt in e1a08ec). Re-pinned: the row count in `tests_docs/test_site.py` (and the '1007' index
term), the `api-map` entry of `GUIDE_BODY_HASHES` (aa8bdb3b... to 09c44c1f..., recomputed from the
current `src_docs/md/guides/api-map.md` body), and the "lists all 1007 modules" sentence in
`src_docs/md/index.md`. Verified with the locked docs environment (`src_docs/requirements.txt`,
`sh src_docs/build.sh`, `python -m unittest discover -s tests_docs`): 36 tests OK.

## 2026-11-12 — Issue 250 WP07 re-derived onto current main

The WP07 identity and feature studios (reference commit 44c28ce) are re-applied on
origin/main c980c136. Conflicts were additive only: ledgers kept both sides (WP07 entries
first), `fontui.__init__` and its two export-list tests keep the `core_pythonqt_lab` and
identity exports, and `api-map.md` was rebuilt from main's map plus the 66 new WP07 module rows
(domain counts and total recomputed; the `fontlabapp.fontui` row gains `identity_*`). Gate
results are in the commit message once the suite has run.

## 2026-11-11 — Issue 250 WP07: identity and feature tools

Implemented Feature Authoring, Feature Explorer, Nastaliq Connections, Font
Identity, Encoding and Order, Glyph Identity, Glyph Labels, Glyph Browser and
Character Consistency. Preserved all 31 old task implementations as live App
domain routes; the old Scriptmix paths now open their named tabs, alongside
nine canonical launchers. Frozen historical manifests remain byte-identical;
31 transition rows record exact new destination hashes without asserting
native acceptance or complete behavior parity.

Reused AppShell with captured active-master read-only TGlyph/TMetrics previews,
connected task selections, numeric sorting and stable glyph identities. Added
staged-input acceptance, target-switch refusal, explicit refresh disclosure,
active-tab preview synchronization and whole-shell embedded-dialog dismissal.
Original writer/partial-failure, feature-text and U+2029 refusal behavior stays
in the retained implementations; Style Linker native instance writes stay held.

Prepared arm64 Python 3.11 offscreen full suites: App 12,502 passed / 28 existing
skips; Scriptmix 4,781 passed / 6 existing skips; zero failures. A final label
check passed 30 tests; independent scoped review passed 57. Combined cohort
coverage, with no exclusions, passes separately for all 116 complete changed
production modules: 85.39–100% lines and 84.21–100% branches. This is combined
App/Scriptmix coverage, not a standalone canonical G-App coverage claim.
Pinned Ruff 0.14.10 passes all 149 changed Python files. Six frozen provenance
manifests are unchanged. Generated catalogue pages were restored rather than
promoting dirty-source immutable links.

Canonical G-App/G-Scriptmix controller attempts exit 3 before tests: no milestone
baseline or upstream merge-base. uv provisioning and uvx Ruff also fail on PyPI
DNS; prepared dependencies and the installed pinned Ruff were used explicitly.
Native PythonQt, ordinary artifacts, genuine-commit docs, wpf inventory repair
and orchestrator integration remain open. No commits, pushes or branch changes.

## 2026-11-12 — Glyport drops its `\x00owned` fallback (Issue 250)

- Glyport `e3364e03998c40095d14a3f91522113a5db2e7a0` (origin/main; Documentation CI run 43251445671 success) now requires `fontlab-fontlabapp>=1.2.10` and deleted the NUL-owned fallback in `fontlab_host.py`; the App seam `OwnedMenus.own_menu` (1c41ec4) is the only path. Caller check: `review/glyport-floor-e3364e0-review.md`. Closes the App TODO row.

## 2026-11-12 — Kerning refusal names the default master (Issue 250, F47-1)

- `fontui.kerning.apply_kerning` refusal now reads "Kerning is written to the default master (<name>) only; <master> cannot be targeted." (Fontport R39 writes the default master, so "make it the current master" no longer helps); docstring updated. Tests pin the exact text and that "current master" is absent. Live recheck row added to TODO.

## 2026-11-12 — F44-1 and F44-2 proved live (A2 report 48, Issue 250)

- On App main 405ba2c (FontLab 9.0.9809, owned copy of plum-var1, fid 547): Font Info and Vertical Metrics Apply (one history row "Undo Font information"; native and Fontport read 780 and the note), the status stayed "Applied font information." after the post-Apply notify and a later report refresh, Undo and Redo updated fields and report at once with the "Edits are staged until Apply." hint returning, Apply with nothing staged said "No changes to apply.", save/reopen (fid 753) read 780, and teardown left `_HANDLES` at 0. Closes the F44-1/F44-2 live-proof row and the "Native-qualify Font Info and Vertical Metrics" row (report 18 passed the Font Info workflow; D18-2 landed and report 48 now covers the vertical-metric fields: captured font, Apply/readback, report refresh, Undo/Redo, saved reopen, teardown). Scriptmix TODO :33 (Font Info and Vertical Metrics native qualification) is closed in the Scriptmix repository on the same evidence (A2 report 48).

## 2026-11-12 — Font Info and Vertical Metrics follows Undo/Redo; Apply status survives its echo (Issue 250)

- F44-1 (A2 report 44): after native Undo or Redo the vertical-metrics report stayed stale until Refresh was pressed, because `FontInfoEditor._changed` calls `refresh()` and only `on_apply` refreshed the report. `FontInfoMetrics.refresh` in `src/fontlabapp/fontui/font_info_metrics.py` now calls `refresh_report()` after the base refresh (patch `live-tests/patches/r44-font-info-metrics-report-follows-history.patch`, proven live on lane r44p: Apply 790, Undo 765, Redo 790 with no Refresh press; the F44-1b field lag after Redo did not recur).
- F44-2 (guard test added: a non-Apply status is replaced by the hint on an unchanged-values notify): `FontInfoEditor._changed` in `src/fontlabapp/fontui/fontinfo.py` now keeps the "Applied font information" status when the notify that follows Apply reloads identical values; a notify that changes the values (Undo) still shows the staged-edits hint.
- Tests in `tests/test_fontui_font_info_metrics.py` fail on the old code. Mutants: dropping the `refresh_report()` call fails the report test; dropping the status restore fails the status test.

## 2026-11-12 — Cold-import flake row closed: environment mismatch, already fixed (Issue 250)

- The row's failing set (`tests/test_ui_package.py` cold import plus the three
  `tests/test_cov_ui_info.py` cold-cleanup cases) is not a `sys.modules` leak: each test
  runs its check in a fresh subprocess. On 3d3077b the child ran with `-I`, ignored
  `PYTHONPATH` and imported whichever editable `fontlabapp` the venv held. 3b90ed0 and
  6c6e890 (both on main) give the child the parent's package root and assert it imports
  this checkout's `__file__`.
- Reproduced with a venv whose editable install points at another checkout: 3d3077b fails
  alone (1 failed) and with `tests/test_cov_ui_info.py` (4 failed); current main passes
  both (67 passed) and a full ad hoc run passes (15,025 passed, 30 skipped). No test changed.

## 2026-11-12 — Installer: unreachable blocked skip removed from `remove_old_dist` (Issue 250, review M-10)

- `install.vfpy` `remove_old_dist` no longer skips `path.name in blocked`: every
  `plan_old_dist` branch that blocks a top-level name also adds it (or its left
  files) to `held`, and a non-empty `held` refuses before anything is deleted.
- New `tests/test_install_superseded.py::test_plan_old_dist_when_a_top_is_blocked_then_held_names_it_so_remove_refuses`
  (ours-without-marker and foreign-leftover cases) pins that invariant; dropping
  either `held` update or the refusal fails it.
- sha256 2eb71691e9752b03387d2ce33b237b27dcbab4bfa775e02f267ee97b53521a60 →
  bbe8104e33036d87c3c119d154a9fde8f159dcc3b3cea4a9524b661674dc2609, synced to the
  echopy, fly, fontport, glyport, pens and scriptmix copies. No repository pins
  the hash; `tools/check_install_copies.py` compares the copies.

## 2026-11-12 — Fontport floor raised to 1.2.2 for the Issue 241 write-back fixes (Issue 250)

- The `fontport` extra now requires `fontlab-fontport>=1.2.2` (was 1.2.0). Fontport
  5b8211f (UFO anchor/guideline copies; one contour shape rewritten among several)
  is first contained in tag v1.2.2 (`git tag --contains`: v1.2.2–v1.2.5); v1.2.1 lacks it.
- New `tests/test_package_boundaries.py::test_pyproject_when_read_then_fontport_floor_includes_issue241_writeback`
  pins the floor; floors 1.2.1, 1.2.0 and 1.1.9 each fail it. DEPENDENCIES and PLAN updated;
  TODO row closed. Installed/native write-back acceptance stays with Fontport's own rows.

## 2026-11-12 — Glyph row table hides the duplicate text pane (F41-1, live report R41, Issue 250)

- Live report R41 found that Nodes Near Zones App listed its results twice: the `SnapshotAuditTab` text pane and the `GlyphTableTab` table. `src/fontlabapp/fontui/glyph_row_table.py` now calls `self.output.hide()`; the text stays populated because tests read it, and the table is the one visible list. Consumers: Open Contours and Nodes Near Zones (`fontui/open_contours.py`, `fontui/nodes_near_zones.py`) and their Scriptmix launchers, which only call `show`. The Font Audit studio `GlyphTableTab` in `studios/font_audit/tabs.py` is a separate class and is unchanged.
- New tests in `tests/test_wp08_nodes_near_zones.py` and `tests/test_wp08_open_contours.py` assert the pane is hidden, the table visible and the text filled; removing the `hide()` call fails both.

## 2026-11-12 — Scriptmix defence in depth for S67-F closed by test (Issue 250)

- Audit: every feature-code write by the suffix-builder scripts goes through `write_feature_blocks` (Build Suffix Substitution, Generate Random Alternates Feature, Nastaliq Connection Editor); `feature_text` in `src/fontlabapp/features/code.py` returns no trailing newline and `_terminated` in `src/fontlabapp/fontui/feature_blocks.py` normalises it before any write. Suffix Report, Alternate Preview, Ligature Finder and Suffix Tool write no feature text. Generate Random Alternates `generate()` and the Nastaliq default already end with a newline; the preview pane is cosmetic.
- Scriptmix `0c30804f` (row-225 tests in `tests/test_features.py`, no script bytes or pins changed) pins that stored feature code ends with "\n" for an empty and an existing feature through the real `write_feature_blocks`. Mutant: making App `_terminated` the identity fails three tests. This closes the defence-in-depth row without changing the Scripts.
- A2 report 45: the Zero-Width Marks "Apply stays disabled after Undo until Use selection" gap is recorded as its own open low-priority TODO row beside F34-2 (same staleness class).

## 2026-11-12 — Fractional kerning refusal names the pair (Issue 250)

- `src/fontlabapp/kerning/batch.py` `_stage` now wraps `whole_value` (existing pairs and staged edit values alike, helper `_whole`) per master and pair and raises `Kerning on <master>: <left> <right> = <value> is not a whole number; ... Round that pair first; no changes applied.` (patch `r37`, helper `_side_text`). Previously the refusal was the bare `Native kerning history cannot preserve fractional/nonfinite values`.
- New tests in `tests/test_kerning_batch.py` (existing pair on an unedited master, a staged edit value, `_side_text`) fail on the old code and pass now. Native recheck and the any-master versus current-master scope question stay open in TODO.

## 2026-11-12 — TODO closures: pens editable recipe, own-menu seam release (Issue 250)

- Closed: "add the pens editable to the App pre-push recipe and refresh consumer locks". fontlab-python-pens v1.0.0 to v1.0.2 are tagged; `test.sh:10-15` installs `../fontlab-python-pens` editable; no consumer lock (App, Fontport, Glyport) pins pens to a tag, because all three use the editable source the owner chose (owner answer to the controller session, 2026-11-11), so there are no locks to refresh. Evidence: reviewer2's table in `issue250/review/app-todo-triage.md`.
- Narrowed: the own-menu seam row. `OwnedMenus.own_menu` (1c41ec4) is in tags v1.2.10 and v1.2.11 (`git tag --contains 1c41ec4`). Only the Glyport fallback removal remains, owner-gated on its App floor of 1.2.10.
- Added a TODO row for contract-testing the App-owned kerning stand-in against Examples (reviewer2 M-1).

## 2026-11-12 — WP10 mutation survivors: boundary and guard assertions (Issue 250)

- Tests only; no production change. Each survivor named in the reviewer's batch 3-4 list now has an assertion that fails on its mutant. Method: mutate the one expression with a throw-away `sed`, run the file's tests, restore the source (`git status` shows no `src/` change).
- Deadline checks `>=` -> `>` (exact-deadline clock): `teaching_graph/feature_graph.py:56`, `teaching_painter/outline_svg.py:61` and `:95`, `sketch.py:92`, `svg_reference.py:48` and `:77`, `teaching_text/tags.py:60` and `:83`. Each new test makes the fake clock return exactly the 2.0 s budget.
- Range edges: `polygon.py:57` (UPM 16/16384 accepted, 15/16385 refused), `sketch.py:45` (exactly `MAX_POINTS` accepted, one more refused) and the control/surrogate label edges, `notebook.py:52` (U+D7FF/U+E000 accepted, U+D800/U+DFFF refused), `localized_font_names.py:138` (0 and 65535 accepted), `import_kerning_pair_list.py:57` (+/-32767 accepted; 32767.4, 32768 refused before rounding).
- Logic: `notebook.py:255` (navigate from a missing title: forward starts first, backward starts last), `:385` (Find walks matches in order and wraps), `paths.py:58` (exactly three on-curve nodes is enough), `:60` (no wrap repeat for open contours or a single node), `:74` (either extent below the threshold), `diff.py:264` (exactly one page of changes is page 1/1), `sketch.py:88` (glyph disappears during capture), `sketch.py:169` (no `painter.end()` when the painter was never created), `svg_reference.py:311` (item without boxes and boxes without item).
- Still open: the embedded `show()` branches of the teaching modules (TODO row kept, narrowed).

## 2026-11-12 — OwnedMenus reap-inside-slot mutant killed (Issue 250)

- New `tests/test_owned_menus.py::test_reap_when_drain_already_scheduled_and_nested_tick_inside_slot_then_work_waits_for_slot_exit`. The earlier nested-tick test never reached the guard: a `remove` inside a slot is deferred without scheduling the batch, so the nested `fire()` found no owner to reap. The new test queues work with `_defer` outside any slot first, so the shared batch holds the owner, then fires the timer inside a slot and asserts the work waits until the slot exits. Mutant evidence: deleting ` and not self._depth` from `while self._pending and not self._depth:` in `src/fontlabapp/qt/menus.py` (`_reap`) makes the new test fail (the other 38 owned-menu tests still pass, which is why it survived); restored, 39 passed. No production change. Closes the TODO row.

## 2026-11-12 — GetGo labs kerning-limit test no longer needs a sibling Examples checkout (Issue 250)

- `tests/test_fontui_getgo_labs.py::test_kerning_limit_reaches_original_validator_as_integer_or_none` imported `fontlab_python_lessons.getgo.kerning_classes` from `../fontlab-python-examples`; without that checkout its four parametrizations failed. It now calls an App-owned stand-in, `_strict_summarize_kerning`, that keeps the original `limit` contract (`None` or a non-negative `int`, `pairs[:limit]`). Examples tests own the real function. Failing-first: on the previous file with the sibling absent 4 failed, 3 passed; with the change and the sibling absent 7 passed. Closes the matching TODO row.

## 2026-11-12 — Native: Metrics panel route, composite base and presets loading (A2 reports 33, 33c, 34, 35, Issue 250)

- Report 40 (lane `e90cfe9`, Scriptmix `1db7016f` Centre In Advance, owned fixture fid 5533): the F34-1 display check passes live. The six skip-note rows (period, colon, ellipsis) show no cells from an earlier plan, including after switching Current/All masters; no write, fixture closed unsaved. Closes the TODO row "Metrics panel display: after fixing stale cells in skip-note rows".
- Report 38 (lane `333a910`, `plugins/` byte-identical to `6e6f6de`; fixture fid 4267): the Plugmix coordinate-edit writer (`plugins/filters/apply.py`) passes on every master. Move Outlines (Light), Scale 150% (Bold), Slant 10 degrees (Regular), Delete Small Paths 400 (Bold) and Round grid 5 (Light) each made one Undo row and left the other masters untouched; Undo/Redo exact; a topology-adding test filter is refused with `ValueError: Filter cannot change contour topology` and no Undo row; save/reopen (fid 4500) exact; five Undos restore the seeded state. Note: there is no one-row all-masters mode, because `plan_filter` passes `[str(package.master)]` to `outlines.collect`; each master was edited in turn and read back. Closes the TODO row "Native-qualify the rest of the Plugmix coordinate-edit writer".
- Report 34 (lane `311cb8c`, owned font, FontLab 9.0.9809): the Metrics panel UI route and Centre In Advance with a composite and its base, All masters, Set width 400, passed ten checks including one Undo row, exact Undo/Redo and save/reopen. Report 35 repeated this for Equalize Sidebearings (selected composite plus base): no double shift, one Undo row, Undo/Redo and save/reopen all passed. This closes the App row for the Metrics panel route and the composite-base path.
- Fix F34-1: `fill_table` in `src/fontlabapp/metrics/panel/ui.py` now calls `clearContents()` before `setRowCount`, so a reused skip-note row no longer keeps cells from an earlier plan. An offline test fails without the fix; the live display check stays open in TODO.
- Reports 33 and 33c: with the presets file absent, the status line names `<dir>/MasterBlaster-presets.txt` with the four defaults and there is no cwd fallback. With the folder patched to an owned directory, the file loads and the status names it. The real user-folder file was not exercised.

## 2026-11-12 — TGlyph/TMetrics semantic palettes and compact embeds (Issue 253-B)

- Resolve all renderer canvas colors per paint, using the read-only native
  `generalDarkGlyph && isDark` policy where available and the actual widget
  palette otherwise. Explicit owned-canvas palettes support controlled tests;
  global color maps and preferences stay unchanged. Selected text pairs and
  disabled colors follow the canvas.
- Remove embedded outer margins/spacing and the TMetrics scroll frame while
  retaining controls, diagnostics, scrolling, model/history and owned teardown.
  Draw signed kerning marks after cell boxes so negative spans remain visible.
- Source/offscreen: 311 focused checks pass; full changed renderer modules exceed
  80% combined coverage, the private palette helper reaches 100%, pinned F821
  lint passes, and strict docs build plus all 36 docs checks pass. The API map
  inventories all 941 source modules, including the private helper.
- Controller full sibling-cohort gate: 15,160 passed, 22 existing skips;
  combined coverage is 100% for the helper, 96.66% for TGlyph and 98.30% for
  TMetrics. Exact-final F821 and 36 docs checks pass. Independent source and
  combined-tree reviews approve this bounded increment. Installed/native
  themes and all-script visual acceptance remain open; no native claim.

## 2026-11-12 — Native: Plugmix filters and D26-1 pass (A2 reports 29b and 30, Issue 250)

- Report 29b (FontLab 9.0.9809, owned fixture): Move, Scale, Round to Grid and Slant Outlines plus Delete Small Paths, run through `fontlabapp.plugins.filters.apply.apply_filter`, each made one Undo row, restored exactly on Undo and Redo, left other masters untouched and survived save/reopen. Report 29's Scale "did not store" error was concurrent owner interaction and did not reproduce.
- Report 30 (App `be468da`): `build_components` clones are saved unlocked in every master (`copy.contentLocked = False` in `_retarget`, `src/fontlabapp/components/creation.py:249`); Undo/Redo exact; saved/reopened font identical. This closes the D26-1 native rerun row. The `contentLocked` getter was not used as evidence (fl#8637).

## 2026-11-12 — Master Text Comparison reads presets from the user folder's Scripts subfolder (Issue 250, owner decision)

- `masters/text/settings.py` gains `presets_directory(directory=None)`: an explicit directory wins, else `<flPreferences().dataPathDefault>/Scripts`, else the working directory when no host reports a folder. `masters/text/ui.py` (path field and automatic load) and `studios/proof_studio/generators/master_text.py` use it, so FontLab's working directory `/` no longer yields "No such file: '/MasterBlaster-presets.txt'". The user-visible reason: FontLab's cwd is `/`, so the old `Path.cwd()` fallback at `ui.py:116` looked in `/`. Native part 1 (A2 report 33): `dataPathDefault` is the user-folder root and `<root>/Scripts` exists with no presets file.
- `load_presets` notices now name the path read ("Local presets loaded from <path>; ..." / "Four original fallback lists; local presets unavailable at <path>: <error>"); the missing-file fallback to the four defaults is unchanged.
- Tests in `tests/test_master_text.py` use `tmp_path` and a fake host; the owner's user folder is never touched. Native verification stays an open TODO row.

## 2026-11-11 — Open Contours and Nodes Near Zones tables: hint and right-aligned numbers (Issue 250, reviewer2 M-1)

- `fontui/glyph_row_table.py` `GlyphTableTab` shows the hint "Double-click a row to select its glyph." above the table and right-aligns the columns named in the new `RIGHT_COLUMNS` class attribute. Open Contours uses columns 3-4 (Nodes, End gap); Nodes Near Zones uses 3-6 (Value, X, Y, Offset).
- Only those two tabs use this helper (`src/fontlabapp/studios/font_audit/tabs.py` has its own `GlyphTableTab`), so no other tab changes.
- Tests: `tests/test_wp08_open_contours.py` and `tests/test_wp08_nodes_near_zones.py`, `test_table_when_shown_then_hint_and_numeric_columns_right_aligned` (real offscreen Qt; both failed with no `hint` attribute before the change).
- WP11 api-map pin row removed from TODO: `tests_docs/test_site.py` now pins 940 modules and asserts `set(rows) == actual` from the source tree; the old 780 pin was replaced in 6f29e51 and 4a5f82c (`git log -S"assertEqual(len(rows), 780)"`), and `tests_docs` passes on be468da.
- Native check stays in TODO under the WP08 native rows (hint and alignment in installed PythonQt).

## 2026-11-11 — compact AppShell initial sizing (Issue 253-A)

- Replaced the fixed screen percentage with Qt content and minimum-size hints;
  preview panes initially receive equal halves with room for the larger pane.
  Preserved the frame-aware available-screen clamp, later user resizing,
  frameless zero-margin preview container and existing action/lifecycle state.
- Offscreen regression: four failures on the original code, then 39 passing
  AppShell tests, 100% complete-module line and branch coverage; pinned F821
  lint passed. Final full suite with actual-main Plugmix fixture: 14,967 passed,
  39 skipped, 109 warnings (214.11 s). Wider Issue 253 qualification remains open.
- Controller's separate native no-preview check observed 1196x631 -> 391x203
  logical pixels and retained user resize 411x213 on repeated show; preview
  rendering, dark theme and all-script native acceptance remain open. Native
  placeholder-preview halves were 369/369 (TGlyph) and 128/127 (TMetrics).

## 2026-11-11 — Built components are saved unlocked (Issue 250, D26-1)

- `components.creation._retarget` sets `copy.contentLocked = False` on every clone. A cloned component serialized as VFJ `"locked": true` in all masters even when the prototype was unlocked (A2 report 26); the setter clears the saved flag. The getter reads True on 9.0.9809 regardless, so the test asserts the glyph VFJ `locked` key, not the getter.
- Tests: `tests/test_component_creation.py::test_build_when_cloned_then_saved_vfj_locked_key_is_false` (the double now serializes `locked: True` on clone and clears it through the setter); it failed before the fix. Patch reference: livetester `r26-component-clone-unlock.patch`.
- Graph: `_retarget` impact LOW (1 direct caller, `_one`), 0 processes, run before the edit.
- Native recheck (owner: livetester) stays open in TODO.

## 2026-11-11 — Raise Ascender, Metric Reports and build_components pass live; new components saved locked (A2 live report 26, Issue 250)

- FontLab 9.0.9809, lane `mainref10` (git-archive of App 7f96170, not the owner install), owned fixture `a2-r26-d.vfj` saved as `a2-r26-d-saved.vfj` and reopened, both closed.
- D18-3 Raise Ascender, all masters, +10: 3 occurrences, 6 nodes, 3 "Raise Ascender" rows; max y 710 to 720 in Light, Regular and Bold; Undo x3 back one master at a time, Redo x3 forward; saved and reopened 720/720/720. D24-1 Metric Reports: "Snapshot: 1 fonts, 3 masters", all 8 keys present, no "Open fonts with masters", history unchanged.
- D18-4 `build_components` finds a prototype (base `A`) and adds `acute` at 150,200 to `Hw6` in all 3 masters as one row; Undo/Redo exact; saved and reopened identical.
- New defect D26-1: every component `build_components` adds is saved `"locked": true`; clearing `contentLocked` on the clone gives unlocked output in all 3 masters (read the glyph VFJ, not the getter). Fixed by the D26-1 entry above; native recheck open in TODO.
- S67-F (App 547dd3f) passed live (A2 report 28): write, Undo/Redo, save and reopen for space, tab, whitespace-after-newline, `\r` and mixed tails; control on main 7f96170 (lane mainref10) keeps the whitespace (`ss07;\t\n`), so 547dd3f stores cleaner text.
- `flShape.contentLocked` reads True for every component (the setter works); the VFJ `locked` key is the real state. The UI-lock step stays owner-run in TODO.

## 2026-11-11 — TMetrics outline build-count test (Issue 250)

- New `tests/test_fontui_tmetrics_outline_once.py` spies on `tmetrics_model.outline` and proves one `refresh()` of "AAB" builds every present glyph exactly once (`A` once; the fake font has no `B`), and that two `outline_of` reads outside `outline_scope()` build twice while inside it they build once. Mutants: `outline_of` without the cache fails both tests; `refresh()` without the `outline_scope()` wrapper fails the refresh test (`A` built 4 times); reviewer2's persistent-cache-outside-scope mutant (a follow poll reusing stale outlines) fails it and survives the existing TMetrics suite, so it is not redundant with the 2026-11-10 test. Needs uharfbuzz (the gate installs it; the module skips without it). `follow()` fingerprints outside a scope on purpose, so a stale poll builds twice (once in the fingerprint, once in `refresh()`); this is by design. No TODO row remained for this item. Evidence: `issue250/triage/tmetrics-outlines-evidence.md`.

## 2026-11-11 — Feature blocks: trailing spaces and tabs normalised (Issue 250, S67-F)

- `fontui.write_feature_blocks` now strips spaces and tabs after a block's last newline and ends each non-empty block with one newline, so `"…;\n  "`, `"…; "` and `"…;\n\t"` reach Fontport staging instead of failing with "history code differs". Tails already ending in a newline (`"\n\n"`, `"  \n"`) are untouched; blank-only code becomes empty.
- Proven against the real Fontport `stage_blocks` (parametrised tail matrix through all three entry points); a test pins that Fontport itself still refuses the raw tail, so its check is not weakened. Closes the TODO row from the S67-F review.
- Only spaces and tabs are stripped; tails ending in `\r` or `\f` keep them and get one `\n` after (pinned; Fontport stages both). The redundant early return in the normaliser was removed (reviewer2 M-1, M-2).
- Process deviation: graph impact was run after the edit, not before. `_terminated` upstream LOW (1 direct caller, 0 processes); `write_feature_blocks` LOW for the fontui candidate, UNKNOWN for the `core/scripting.py` wrapper (dynamic import), resolved by text search to three Scriptmix scripts, their tests and Fontport `feature_blocks.py`. `detect_changes` against origin/main: low risk, 0 processes, not partial or truncated.

## 2026-11-11 — Pin deferred-undo failure inside an OwnedMenus slot (Issue 250)

- `tests/test_owned_menus.py::test_remove_when_deferred_undo_fails_inside_slot_then_error_goes_to_sink_not_qt`: a `remove()` requested inside a slot whose undo then fails is deferred, the failure reaches the error sink on the drain and never Qt, and the token is gone. It passes on current main (no production change); replacing `_guarded(self, teardown)` with a bare `teardown()` in `_reap` makes it fail. Existing tests covered callback-raises (line 293) and deferred removal success (315, 388) but not a failing deferred undo.

## 2026-11-11 — fontpr tuple arrays and component prototype lock (Issue 250, D18-3/D18-4)

- fontpr `call` returns tuples for JSON arrays on FontLab 9.0.9808. Raise Ascender (`raise_ascender/_capture.py`), `core/outline.py`, `metrics/vertical/native.py`, `contours/near_miss/native.py` and `components/creation.py` `_elements` now accept a list or a tuple. Raise Ascender no longer fails with "Unreadable or ambiguous declared master domain." Also fixes D24-1: Metric Reports "Open fonts with masters" because metrics/vertical/native.py `_registry` rejected the tuple from `list_fonts()["fonts"]`.
- `components.creation._qualifies` no longer reads `shape.contentLocked`: it is True for all 504 components in plum (A2 report 18), so `build_components` always refused NO_PROTOTYPE. The VFJ `locked` key (already in `STYLE_DEFAULTS`) stays the lock source. Native cause of the always-True read is not investigated.
- Tests: `tests/test_fontpr_tuple_arrays.py` (tuple-returning fakes; fail on main).

## 2026-11-11 — Stem Blend and Scale With Stem Compensation through their own panels (A2 live report 22, Issue 250)

- FontLab 9.0.9808, lane mainref8 (App 6a6d35c; the two writer files match ad8775a): Stem Blend run through `stem_blend.show` with the real `current_context()` (no swap), and Scale With Stem Compensation through `panel_type()(None)` with a Font-window selection of H, V, T. Each gives one Undo row ("Stem Blend", "Scale With Stem Compensation" over it), exact Undo and Redo, and a saved reopen with clean history. Create Layers is refused without Preview and confirm, and writes nothing. Scale With Stem created 6 layers (3 glyphs x Regular and Bold).
- Caveats: the run used a trimmed 120-glyph fixture in which `A` has no dependants (in the plum fixture Stem Blend correctly refuses `A`, the base of automatic composites). Buttons and fields were driven through Qt setters and `click()`, not OS events, and the Font-window selection was set by script (`fl.Select`), not by clicking. The read-back compared contour count, advance and first point per layer; the full `stored_outline_matches` check was last done in report 20 for the same writer code. Stem Blend with the glyph's own Glyph window open stays owner-run in TODO.

## 2026-11-11 — Live evidence from A2 live report 21 (FontLab 9) (Issue 250)

- UFO Roundtrip Inspector (D18-1, App 6a6d35c): `fontui.ufo_roundtrip.show` plus run completed in 2.7 s; the report lists export_to_reopened 616 and reopened_to_imported 5 differences, 205 layers x 3 masters checked, 6 limitations, source_written False. The Transform repr error no longer occurs; history clean, glyph state unchanged, handles released. Deadline/failure staging cleanup and repeated Close stay open in TODO.
- wp10port lab smoke (App b9ea7bb, read-only): eleven labs (Text Editors, Scripting Workbench, Snapshot, Font Inspection, Node Editing, Stem Interpolation, Kerning Recipe, Font Metadata, Layer Transfer, Graph, Painter) ran refresh and preview on every tab, history clean, closed with host.OPEN 0. Expected guards only (Layer Transfer needs a second font; Painter needs a stroke). Not covered: menu launch (main has no WP10 menu routes yet) and every apply action.
- F19-1 not reproduced; kept as a low-priority TODO row: feature Undo no-op seen once (fid 10645), not reproduced in three variants (report 19 k2-k5 and report 21 section 3); no FontLab issue drafted, no minimal recipe exists.

## 2026-11-11 — Live evidence from A2 live reports 18 (part 2), 19 and 20 (Issue 250)

- Layer Manager (report 18 W9): all five tabs pass live on owned fixtures: copy layers, copy twins, add intermediate layers and clean-up are one Undo row each ("Layer Manager: copy layers B" and so on), deliver is two rows ("MCP set_glyph" plus "Layer Manager: deliver glyphs"), as documented; Undo/Redo exact and saved reopen clean.
- Duplicate Anchors (report 19, App d81d7f2): scan works; applying 2 anchors on 1 layer is one "Anchor Duplicates" row; Undo/Redo exact; reopen clean. The `font.id` defect A1 is fixed.
- Scale With Stem Compensation and Stem Blend (report 20, App 6dc6944, tolerance 1e-3): Scale With Stem changed 6 and kept 2 in one row; Undo clean; Redo delta 1.2e-5..1.6e-5; save and reopen delta 1.4e-4..5.0e-4, all accepted. Stem Blend created layer "Stem 110x75 (Regular)" in one "Stem Blend" row, advance 394 = 394, Undo/Redo/reopen True. Caveat: the harness replaced `stem_blend.current_context` (`prepare_blend` needs `fontlab.CurrentGlyph()`), so the panel selection path was not rerun (report 10 covered it).
- Passes noted on rows that stay open for other parts: Font Info, Master Metrics Table, Alignment Zones and Suggest Zones, Perpendicular Guides, Node Duplicator, glyph creation (report 18 W1, W2, W4, W5, W6).
- Defects found and recorded as TODO rows: D18-3 (tuple masters), D18-4 (component prototypes), D18-2 (Fontport vertical-metric fields), F19-1 (feature Undo no-op), and the Redo of Add Glyph auto-layer draft.

## 2026-11-11 — Legacy-font fakes audit closes the conversion row (Issue 250)

- Audited every production `font.id` read: `kerning/group_proof/native.py`, `contours/raise_ascender/_capture.py`, `masters/background/capture.py`, `masters/layers/brackets/_snapshot.py`, `glyphs/catalog/native.py`, `contours/nodes/duplicator/_capture.py`, `anchors/crossfont/capture.py`, `studios/layer_manager/_from_font.py`, `glyphs/common/capture.py` and the others read an fgFont from `CurrentFont()` or `AllFonts()`, whose `.id` is `getPackageID` (pyfontgate `fgfont.cxx`). The only code that reads the legacy `FL.fl.font` is `core/scripting._carrier_id` (already fenced; also `core/scripting.py` `names_font_window_selection`), `guides/perpendicular/selection.py` and `anchors/duplicates/capture.py` (both go through `_carrier_id`), `glyphs/selection/_mark_colors_native.py`, `studios/vertical_metrics/calculate.py` and `studios/_records.py`, none of which read `.id`. The listed tests fake fgFont, so their `id` is correct; no fake sets `id` on an `fl.font` object. Scale With Stem Compensation: `tests/test_teaching_writers_stem.py` and `tests/test_teaching_writers_scale_plan.py` were checked; the only `id` is `Package.id = 7` (an flPackage fake, correct), and neither fakes `FL.fl.font` or `CurrentFont`; `src/fontlabapp/fontui/teaching_writers/scale_with_stem_compensation.py` reads only `package.id`. Tests checked for the other areas: `tests/test_kerning_group_proof*.py`, `test_raise_ascender*.py`, `test_near_miss*.py`, `test_crossfont_anchors*.py`, `test_background*.py`, `test_studio_layer_manager.py`, `tests/_layer_manager_originals.py`. Source for fgFont `.id`: `pyfontgate/fgfont.cxx` `getPackageID`, as cited in `core/scripting.py` `names_font_window_selection`; the C++ source itself is not in this workspace and was not re-read. The TODO row is closed with no code change.

## 2026-11-11 — Test hygiene: live-shaped legacy-font fakes, cold-import children, sibling-free suite (Issue 250)

- Legacy `FL.fl.font` test fakes omit `.id` like FontLab 9 and identify through `_carrier_id`'s saved-path fallback; wrong-carrier cases change the saved path.
- Cold-import subprocess tests resolve `fontlabapp` through the parent's package root (`PYTHONPATH`, `-s`) so a venv editable install pointing at another checkout no longer breaks them.
- The lesson-route test builds an App-owned fake `fontlab_python_lessons` package (name filter, metrics model, metrics form), so it runs without the Examples sibling and no skip remains.
- Perpendicular-guide selection tests again cover the same-path/different-fgId carrier refusals (`selection.py` back to 100%): at start ("differs from the active package") and mid-capture ("carrier changed"); path-change cases now assert "path differs".

## 2026-11-11 — UFO Roundtrip Inspector survives Transform values (Issue 250, D18-1)

`attrs.asdict` rebuilt fontTools `Transform` namedtuples (component and image transformations) from a single list, so the inspector's snapshot raised `TypeError('must be real number, not list')` when diffed (livetester report 18 part 1). `_snapshot` now passes `value_serializer=_plain_transform`, keeping 6-tuples. New test `test_snapshot_when_component_and_image_have_real_transforms_then_plain_tuples_and_diffable` fails on main and passes now (tests/test_fontui_ufo_roundtrip.py: 22 passed, including a changed-image-transform diff case; offline the unfixed code fails with a wrong value, the native TypeError is confirmed by livetester rerun). Two follow-ups stay open in TODO (Master Text presets path; '' to None glyph notes).

## 2026-11-11 — WP08b review fixes after merge onto b8fa1e7

Pinned the `native.select` names filter of Open Contours and Nodes Near Zones (an `if True` mutant now fails), renamed the Font Audit About credit test to what it checks, gave the Context Proof lazy-dispatch test an App-owned launcher fixture instead of a Scriptmix sibling, and recorded the Point Counter (Master Layers) provenance TODO.

## 2026-11-11 — WP08c S66 Nodes Near Zones

Added `fontlabapp.contours.nodes_near_zones` (pure `scan`/`render`/`summary`, native `capture`/`select`/`selected_names`) and `fontlabapp.fontui.nodes_near_zones` (shell report tab with a 1-30 unit tolerance that rescans and a Select glyphs action). 9 tests, 100% line and branch on the new modules; demo; API map (790 modules).

## 2026-11-11 — WP08c S65 Open Contours

Added `fontlabapp.contours.open_contours` (pure `scan`/`render`/`summary`, native `capture`/`select` bound to the scanned package id) and `fontlabapp.fontui.open_contours` (shell report tab with a Select glyphs action; stale or failed refresh disables selection). `show_snapshots` gained `tab_type`. 9 tests, 100% line and branch on the new modules.

## 2026-11-11 — WP08c S62/S63 Font Revision Comparison and Metric Reports

Added `fontlabapp.fontui.font_revision_comparison` (Report Composite Differences, Report Glyph Set Differences) and `fontlabapp.fontui.metric_reports` (Vertical Metrics Reporter) over the shared snapshot shell, reusing each original capture/render pair; demos, API map (782 modules). Compare Open Font Revisions and Sidebearing Direction Marker stay unabsorbed (own dialog / live overlay).

## 2026-11-11 — WP08c review fix I-4/M-3/M-4

Pinned each S60/S61 route to its own owner capture/render pair by identity and the exact status text; documented that Dangerous Offcurves opens an exact-layer proof tab on every Refresh.

## 2026-11-11 — WP08c S60/S61 Geometry Audit and Master Structure Audit apps

Added `fontui.snapshot_audit` (shared tabbed report shell), `fontui.geometry_audit`
(Close But No Cigar, Dangerous Offcurves, Dump to Svg Path Commands, Point Counter
(Master Layers), Point Counter) and `fontui.master_structure_audit` (Master Node
Compatibility Report, Why You Not Compatible), each reusing the existing report
capture/render triples. Ten new tests (failed before the modules existed), demo
scripts, API map rows (780). Live Glyph Info, Nodes Near Zones and Open Contours
own Scriptmix dialogs with no App model and stay unabsorbed. Native acceptance open.

## 2026-11-11 — WP08c S64 Reference Image Viewer app

Added `fontlabapp.fontui.reference_images.show()`: the original read-only image
viewer embedded in the shared shell with About. Exit, Escape, window close and
the Close button all close the shell; a refused viewer cleanup keeps it open
for a retry; off-main-thread calls are refused. Six new tests (failed before
the module existed), 95% line/branch coverage, demo script added, API map row
added (api-map pin 777 rows; generated docs remain WP11). Native acceptance open.

## 2026-11-11 — WP08 first source increments (consolidation blocked)

Final prepared App full suite: **12,392 passed, zero failures, 28 existing skips**.
All 14 changed production modules across both repositories meet separate
80% line/branch gates with zero exclusions; minimum 98.42% lines/91.30%
branches. Installed pinned Ruff 0.14.10 passes all 24 changed Python files.

Added the S27 Anchor and Component Inspector shell assembly, S55 Context Proof
and S59 Font Audit named-tab assemblies, reusing their existing owners and
algorithms. Captured font/layer checks refuse stale actions; callback failures
remain contained. Public lazy factories keep studio imports within the existing
package boundary. AppShell reads count/currentWidget through the Qt property
adapter. Updated the API module map without changing its audit.

Independent source reviews approved all three increments after correcting
cross-font actions, callback containment and layer binding. Focused checks:
S27 121 passed (92/92 lines, 20/20 branches in its owner; wrapper 4/4 lines),
S55 132 passed before final facade checks; S59 158 passed (its three modules
100% lines/branches); shell 34 passed. Broad fontui checks: 1,050 passed,
three existing skips; three additional facade tests passed, bringing the
shared facade to 89.90% lines and 80% branches. Final reviewer subset: 79 passed.
These overlapping runs are not additive test totals.

WP08 is not complete. Exact provisioning failed on PyPI DNS; the canonical
quality wrapper writes outside this lane. Active menu transition/inventory and
native gates remain open. S28–S36, S56–S58 and S60–S64 were not advanced after
the first failed full increment gate. No old scripts or provenance pins were
removed, no commit/install/native operation was performed, and the ten missing
composition implementations plus all 8,723 obligations remain open.

## 2026-11-11 — WP05 route behaviour tests move into App (Issue 250)

The pre-push coverage gate measures App tests only, so the consolidated WP05 modules (`fontui/outline_routes/*`, `fontui/node_editor/*`, `fontui/outline_compatibility_routes/*`, `studios/derived_glyphs/compat_*`, `studios/shape_generators/*`, `fontui/superaligner.py`, `fontui/outline_order.py`) scored 0%. Ported the Scriptmix behaviour tests that exercise them (`tests/test_wp05_route_behaviour_*.py`, helpers `tests/_wp05_app_routes.py`, `_wp05_scriptmix_shim.py`, `_smx_*.py`) and added `tests/test_wp05_simplify_main.py`. Tests that only audited Scriptmix launcher files or historical release bytes stay in Scriptmix. All 41 changed modules now reach at least 80% (statements and branches combined) in the App-only run. Review fixes (reviewer2): `test_public_lazy_factories_open_same_window` no longer runs the Scriptmix launcher file, so App tests need no Scriptmix checkout (982 WP05/node-editor tests pass with the sibling removed); deleted the empty `tests/test_wp05_route_behaviour_tab.py` and the dead `Scripts/Kerning` paths in `test_wp05_route_behaviour_g13.py`. Suite: 13873 passed, 22 skipped. Second merge with origin/main e8879d4: the api-map body hash pin recomputed to 245143a9... from the combined tree after rebuilding the docs (row count stays 884).

Merge with origin/main 3d3077b (teaching_writers, Font Info capabilities): API-map rows 881 -> 884 (the 3 `fontui.teaching_writers` rows; ui.windows/views 267 -> 270, total 884 recounted from the combined tree) and the api-map body hash pin recomputed to 0451a5f9... after rebuilding the docs.

## 2026-11-11 — Duplicate-anchor writer no longer reads FL.fl.font.id (Issue 250)

- Fix: `anchors/duplicates/capture.py` `context` read `int(fl.font.id)`, which FontLab 9 legacy `FL.fl.font` lacks (livetester, live). It now uses `core.scripting._carrier_id` (package path fence when `.id` is absent). Test with an `.id`-less carrier fails before the fix. Other `font.id` uses read fgFont (`CurrentFont()`/`AllFonts()`), which has `.id`.

## 2026-11-11 — Feature code gets a final newline before staging (S67-F, Issue 250)

- Fix: `fontui.feature_blocks.write_feature_blocks` (also reached as `core.scripting.write_feature_blocks`) appends one newline to each non-empty feature code that lacks it, before the source comparison and Fontport staging. `features.code.feature_text` returns code without a final newline while Fontport's history split-back returns `code + "\n"`, so Build Suffix Substitution always failed on a new feature with "Feature block 'ss01': history code differs" (A2 live report 17). Fontport's check is unchanged; terminated and empty codes are untouched. Tests in `tests/test_feature_blocks.py` (the new-feature write fails 5 of the parametrised cases before the fix).

## 2026-11-11 — Live evidence from A2 live reports 16 and 17 (FontLab 9.0.9809) (Issue 250)

- Studios glyph records (report 16 row 1, App 3d3077b): legacy `vertical_metrics.calculate.glyph_records` and `studios/_records.glyph_records` agree on order and unicodes: Lato 3055/3055 (893 unencoded, 7 multi-code glyphs, no duplicated codes), plum 205/205. Read-only: Undo disabled. The migration precondition is met.
- TMetrics echo token (row 3): after a write there is one refresh, the token is recorded, two later host notifications leave `echo.stale` False with 0 extra refreshes; an external write sets `stale` True with 1 refresh and clears the token.
- Layer Manager Backups tab (row 4): a freshly re-planned key (new PythonQt wrappers) equals the shown key; Apply is one row "Layer Manager: back up H"; Undo and Redo exact; a forged key is refused with "The layers changed since the list was made; check the list again." The other tabs stay under TODO.
- Marks, notes and Unicode refusal (rows 5, 5b): on base n, Glyph Mark Colours and the Review Form note are one row each, the dependant ntilde is unchanged on all 3 masters, Undo/Redo exact; Apply Unicode Map with a Glyph window active is refused before any write. After save and reopen the mark 120 and note are kept and ntilde is unchanged (report 17 row R1).
- Stem Blend / Layer Manager layers have `isMasterLayer=False` and `autoLayer=False` after create, Redo and reopen (rows 6, R1).
- Drag helper (report 17, App e8879d4): `start_drag_distance(QApplication)` returns 10 live while the class attribute is None. On all six E06 handles x=18 gives no drag call and keeps the origin, x=23 gives exactly one call and clears it, x=40 gives no further call; no exception. The drag hook was stubbed (no OS drag). The OS drag by the owner stays in TODO.
- Duplicate Unicodes (report 17 row D1): `apply([(V, 72)])` changed V, one row "Duplicate Unicodes"; Undo and Redo exact; save and reopen shows no groups. Apply Unicode Map without a Glyph editor (U1): n refused, H 72 to [72, 57362], one row, Undo/Redo exact, reopen equal.
- Scale With Stem Compensation write (S1): unconfirmed apply refused, confirmed apply is one row with 6 new layers, a stale re-apply is refused, one Undo removes all layers, and reopen shows the layers. The post-Redo read-back tolerance defect (S1b) stays with its fix.
- Fontport empty-layer pen route (row 7) and `import_native` `close()` (N3, F1) are recorded in the Fontport CHANGELOG.
- Anchor rounding (row 8): the host rounds fractional anchor offsets (+0.6 gives +1, +0.4 and +0.2 are swallowed) but the +0.6/-0.6 round trip does not drift.

## 2026-11-11 — Stem writers accept live coordinate drift (Issue 250, S1b)

- Fix: `COORDINATE_TOLERANCE` in `fontui/teaching_writers/stem_blend.py` and `scale_with_stem_compensation.py` is now 1e-3 font units (was 1e-5). Live FontLab drift is 1.2e-5 to 1.6e-5 after Redo and up to 5e-4 after reopen, so correct outlines were rejected. The constant also bounds the advance-width and plan checks in the same modules. Tests pin 5e-4 accepted and 2e-3 refused.

## 2026-11-11 — Drag-distance fix and star-click evidence from A2 live report 15 (Issue 250)

- Fix: the six E06 drag handles (`deferred_glyph_report`, `draggable_glyph_names`, `font_drop_inspector`, `font_file_drop_shelf`, `glyph_pair_board`, `proof_word_magnets`) raised `TypeError` in `mouseMoveEvent` under FontLab PythonQt, because `QApplication.startDragDistance` is None on the class and holds 10 only on `QApplication.instance()` (report 15 section 2b). They now share `fontlabapp.qt.properties.start_drag_distance`, which reads the instance first, then the class, then Qt's default of 10. Offline tests (`tests/test_drag_distance.py`): class attribute None with instance 10 gives no drag at 9, a drag at 10 and 25; the old lookup fails 4 of those (mutation check).
- Glyph Review Priorities star click verified in FontLab (report 15 section 2a, `r15e_stars.json`): in a 130 px cell x=70 gives 3 stars, x=129 gives 5 and x=1 gives 1; Delete and Backspace cleared rows 0 and 1; the font and its Undo history were untouched. No OS events were synthesized: the live `StarDelegate.editorEvent` was called with Qt-built events. This closes the star-click and key half of the former `value()` wrapper TODO row.

## 2026-11-11 — Live evidence from A2 live report 14 (FontLab 9.0.9809) (Issue 250)

- Lab shell: after Apply the shell shows the task panel's status text (`AppShell.set_actions(status=...)`; E07-E09 bindings pass the panel status label), so a refusal such as `require_no_editors` no longer leaves "Ready.". Tests in `tests/test_fontui_appshell.py` and `tests/test_core_pythonqt_profile_actions.py`; the E08 native re-run should also check the shell status line.
- Stale-class-member kerning verified in a real subset font (section 3, `r14k_*.json`, App main 621033e): `fontui.write_kerning` o/o=17 gave one Undo row; the stale-class pair V/@_R_o was refused with `ValueError: Unknown glyph: cacute on Regular` and changed nothing; Undo and Redo were exact; save and reopen preserved the 63 stale classes and o/o 17.
- Master capHeight write through `vertical_metrics.table.write_changes` (section 4, `r14m_*.json`): +7 on all masters gave one row (688 to 695 x3), +3 on Bold gave 698; Undo x2 and Redo x2 exact; the saved VFJ kept capHeight 695/695/698; the document was clean after Undo. The composite-base path and the Metrics panel UI route were not tested.
- WP09 labs E01-E09 on main (results row 5, `r14s_*`): 9 of 9 tabs open Ready, refresh and preview write nothing, font signature and history unchanged. E09 Mark Colours and E09 Review Form each wrote one row and Undo restored (results row 6). E08 Apply Unicode Map was correctly refused by `require_no_editors` because a Glyph window was open (section 7).

## 2026-11-11 — Issue 250 WP10b: Stem Interpolation and Scale With Stem Compensation modules

- Added `fontlabapp.fontui.teaching_writers.stem_blend` and `scale_with_stem_compensation` with behaviour tests (97.6% and 93.5% line coverage). Their read-back accepts FontLab's integer-grid storage (`_stored`: a half-unit value stored as the nearest integer passes, a real mismatch fails).
- `core.edit_guards.require_no_editors` takes `action` (default "removing Unicode assignments"); `history.commit` passes "writing to the font", so the refusal no longer says "Unicode" for geometry writes. Tests pin the forwarding and the `_stored` bounds.
- The rest of the Codex WP10 teaching snapshot is held; see TODO.
 batch keeps its pre-mutation notify (Issue 250, live round 11)

## 2026-11-11 — Font Info blank-metric note in plain words (Issue 250)

The visible note is now "FontLab can't clear a blank metric; enter a value instead."; Fontport's technical `info.clearOptionalMetric` reason moved to the diagnostic label's tooltip. Tests in `tests/test_ui_info.py` cover the note, the tooltip, the supported case (no note, empty tooltip) and the non-mapping fallback.

## 2026-11-11 — Font Info editor reads Fontport capabilities() (Issue 250)

`FontInfoEditor.refresh` (`src/fontlabapp/fontui/fontinfo.py`) no longer hardcodes "Blank metrics cannot be unset in FontLab". It asks `font.capabilities()` for `info.clearOptionalMetric`: when unsupported it shows the backend's own reason, when supported it omits the warning, and a model without `capabilities()` (or one that raises) keeps the generic note. Tests (`tests/test_ui_info.py`, three new; two failed before the change). Full gate 12873 passed, 22 skipped. This closes the App-side half of Fontport TODO row 48; the Font Info editor is the only App consumer that guessed a Fontport feature.

## 2026-11-11 — Console deadline boundaries and reviewer minors (Issue 250, WP10)

- Console `evaluate()` tests pin the 60 s upper bound and the `monotonic() >= deadline` boundary (mutants `<`, `>` , `0 <=` killed). copy_layers retained-pin, node_table smart-flag restore and vanished-node tests (9527477). Remaining survivors are one TODO row.

## 2026-11-11 — Issue 242 WP10: teaching and GetGo labs

- Added the shared teaching host and sixteen lab compositions across 39 App
  modules, retaining 30 concrete teaching implementations and existing guarded
  writers. Captured glyph/layer previews, stale-target refusal, staged-edit
  Refresh protection, stable numeric table sorting and failed-Close retry share
  the existing AppShell. GetGo source previews disclose their representation
  limits and call the original thirteen disposable-copy lesson routes.
- Final matched-cohort arm64 Python 3.11 offscreen suite: **12,703 passed,
  22 existing skips, zero failures**. All 810 App Python files match the genuine
  built wheel and temporary regular installation. The exact matched App
  source/test/demo snapshot has 1,480 Python files with zero differences.
- Across App and Examples, **60/60 changed production files pass separate 80%
  line and branch gates**; minimum 85.44% lines and 80.26% branches (empty modules
  and absent branches are N/A). The changed Fontui Helpers demo is 100%/100%.
  Ruff 0.14.10 passes all 101 changed Python files across both repositories.
- Independent source review resolved parameter parsing, preview context/lifetime,
  numeric sorting, staged edits and embedded Close findings; 104 combined
  teaching/GetGo tests passed independently. Preserved source oracles and all
  historical workflow holds; no native acceptance or Git delivery is claimed.
- Updated the API inventory to 810 modules and documented the new teaching APIs
  in the existing helper demo. Rendered docs remain stale: docs checks report
  **35 passed, 1 failed, 17 subtests passed**, solely the old rendered 771-module
  map. WP11 rebuild and WP12 installed PythonQt/writer acceptance remain open.
  Canonical coverage wrapper exits 3 without a milestone/merge-base; the full
  prepared equivalent above preserves its test selection and coverage policy.

## 2026-11-11 — Kerning batch keeps its pre-mutation notify (Issue 250, live round 11)

Reverted the round 10 single-notify change (M1). The notify before the mutation records history-less edits a script made earlier as a separate Undo row; without it the next Undo also reverts them (reproduced live for glyph, kerning and font info). The extra Undo row is by design. `test_write_kerning_when_unrecorded_edit_precedes_then_notify_order_pre_then_post` pins the order.

## 2026-11-11 — Issue 250 WP05: outline editing compositions

Added the ten S11–S20 outline tools on the existing AppShell and read-only
TGlyph. The compositions retain exact original callable algorithms and layer
scope, capture targets before writes, require an accepted preview, preserve
staged state until discard, and retain failed-close owners. Original callable
interfaces remain outside active menus. Added eight lazy public services and
updated the API map and five existing demo descriptions without adding menus.

Independent source/migration review completed. Full prepared arm64 Python 3.11
offscreen gates: App **12,473 passed, 28 existing skips**; Scriptmix **4,792
passed, two existing skips**. After import-only cleanup, 124 original generator
cases passed again. All 77 complete changed App production modules meet both
80% gates: minimum **88.37% lines / 80.00% branches**, no exclusions. Coverage
combines the full App suite and the migrated Scriptmix behavioral oracles;
two stale import-line measurements were replaced by the fresh generator run.
Pinned Ruff 0.14.10 and uvx with the same default rule scope pass 139 changed
Python files. The earlier batch-recipe Close race remains recorded separately;
a passing final run does not resolve that existing flaky behavior.

Canonical quality wrappers cannot write their hardcoded evidence locations from
this lane; fresh recipe provisioning failed on PyPI DNS. Prepared runs are
explicit substitutes, not canonical wrapper passes. Native PythonQt, ordinary
installed artifacts, graph integration and generated-site rebuilding remain
open. No commits, pushes, installations or native font edits were performed.

Landing on current App main (a0358ea): git merged all 843 api-map rows without conflict and the Domain table was recounted from them (ui.windows/views 229, total 843); tests_docs pins moved to 843 rows and api-map body hash 32bd2e0e. Combined-tree App gate with Plugmix 87fc0ec: 12,752 passed, 22 skipped, 1 failed. The failure, `tests/test_fontui_node_editor.py::test_public_lazy_factories_and_menu_route_open_same_window`, reads WP05's Scriptmix `Scripts/Contours/Node Editor.py` and passes (10 passed) with that Scriptmix lane; it is a paired test that needs the Scriptmix landing. tests_docs 36 OK. Graph change analysis: risk critical (100 files, 1279 symbols, 30 processes), the expected size of ten new tools plus eight lazy services.

## 2026-11-11 — Refuse on any unowned old-RECORD entry (Issue 250, WP11A I-11/M-8)

- `install.vfpy`: `plan_old_dist` also returns every entry in the earlier install's RECORD that is not provably ours (edited or unhashed files, unshipped packages, top-level modules, a user's replacement folder). `check_site_free` and `remove_old_dist` refuse on any of them, naming up to five files, before anything changes, so the dist-info is never dropped while files stay behind.

## 2026-11-11 — Reinstall over a uv/pip install of the same distribution (Issue 250, WP11A I-10/M-7)

- `install.vfpy`: `plan_old_dist` applies the marker rule only to our own dist-info (INSTALLER `install.vfpy`). For a uv/pip dist-info only RECORD files whose sha256 still matches are removed, and folders only when nothing else is left in them (`__pycache__` ignored); an edited or unlisted file keeps its folder and `check_site_free` refuses before anything changes. Rows that are unhashed, absolute or contain `..` are never removed. `remove_old_dist` keeps a user's folder but still drops the dist-info.

## 2026-11-11 — Installer never deletes a user's replacement folder (Issue 250, WP11A I-9/M-6)

- `install.vfpy`: new `our_tops` — a RECORD entry is ours to remove only if it is a link/file, a `.dist-info`, or a real folder carrying our `.fontlab-install.json` marker (the copy fallback of `write_record` now writes it). `remove_old_dist` and `check_site_free` both use it, so a user who replaced our `site/<pkg>` link with a real folder and reinstalls is refused with their files intact (was: `rmtree`).
- `check_site_free` now runs before `prepare_site`/`ensure_venv` (uses `site_dir(data)`), so "Nothing was changed." is true.
- Tests: replaced-link reinstall refusal, copy-fallback marker ownership, `test_plugins_startup` RECORD test now distinguishes a marked folder (removed) from an unmarked one (kept).

## 2026-11-11 — Uninstall of editable installs from older logs (Issue 250, WP11A I-8)

- `install.vfpy` `plan_uninstall`: a symlink in `files` that an older install.log (no `links`) never recorded is now removed when it still resolves into `Extensions/<id>/lib` or the logged `source`; a link re-pointed elsewhere stays kept. Before, the first uninstall after upgrading left the editable `site/<pkg>` link, so the package stayed importable. Tests: three old-log cases in `tests/test_install_superseded.py` (two fail on a13260a; the re-point case is a guard).
- M-5: `check_site_free` runs before any removal, copy or script placement and refuses cleanly ("another distribution owns it. Nothing was changed.") when a non-symlink folder in site-packages is not in this distribution's RECORD; no scripts, lib or log are written.

## 2026-11-11 — WP11A I-6/I-7/M-3: ownership beyond Scripts/, edited scripts survive reinstall

- I-6: uninstall removes an entry outside `Scripts/` only when proven ours: a symlink whose `readlink` equals the logged link target, a folder carrying the installer marker `.fontlab-install.json` with this extension's id, or a `.dist-info` whose `INSTALLER` is `install.vfpy`. A user folder that replaced our `site/<pkg>` link, or any other file or folder, is kept and reported.
- I-7: install no longer overwrites an existing script that is not provably ours (hash differs from this release, the last logged hash, and the ledger). It is printed as `Kept (..., not overwritten)`, recorded in `kept`, and the new version is not placed. Logged hashes now persist across an uninstall record.
- M-3: a failing removal is logged as an `uninstall-failed` record (kept paths, error), history only, so the uninstall stays retryable, then re-raised. Removal stops at the first failure so the generated launcher survives.
- The earlier I-4/I-5 `0e230a5` ran only against temporary directories in tests, never a real FontLab user folder.
- Tests: six new in `tests/test_install_superseded.py`; four fail on 82bc069.

## 2026-11-11 — WP11A I-5: uninstall verifies ownership

- `uninstall` now goes through `plan_uninstall`: under `Scripts/` a file is removed only when its sha256 equals the hash logged at install, a link only when it still points to the logged target, an empty folder only when empty. Edited, re-pointed, unhashed (older log) and non-empty-folder entries are kept, printed as `Kept (reason): path` and recorded in the uninstall log entry's `kept` list. lib/ entries we created are removed as before.
- Tests: install-edit-uninstall, re-pointed link, unchanged link, old log without hash, folders, lib entry; four fail on 602202e.

## 2026-11-11 — WP11A C-2: kept entries are never uninstalled

- Kept superseded entries (user links, edited files, folders) are now logged under a separate `"kept"` list, not `"files"`. Uninstall removes only `files`, so it can no longer delete a kept link or edited file or rmtree a kept folder. Their old hash and link records still carry forward and later installs re-examine and re-report them.
- New install, install, uninstall test proves a kept link, an edited file and a kept folder with contents all survive; other install tests assert `kept` instead of `files`.
- Open: the six sibling `install.vfpy` copies (echopy, fly, fontport, glyport, pens, scriptmix) still differ from this one.

## 2026-11-11 — WP11A I-4 and minors

- `install.vfpy` no longer adopts a kept user link: `links` for kept entries carries only the previous log's records, never a freshly read target, so a kept link survives later installs. Kept folders and links stay in the new log's `files`.
- `linked_parent` docstring now says the data folder itself is also checked.
- Two-install regression tests (kept link, kept folder) fail on the previous code.

## 2026-11-11 — WP11A review fixes (C-1, I-1..I-3)

- `tools/check_install_copies.py` lists the root with `os.listdir` and drops FontRig and TypeRig-Icons before any path is built; a test wraps `os.stat`/`lstat`/`scandir`/`listdir` and fails on any excluded path.
- `install.vfpy` refuses a superseded entry whose parent component is a symlink (every component is lstat'ed); removes a symlink only if the last log recorded it (`links`) and `readlink` still matches; for entries with no logged hash, removes only when the file's sha256 is in `menu-consolidations.json` (`source.sha256`), else keeps it; kept entries stay in the new log's `files` with their old hash carried, so they are reported again and uninstall still sees them.
- `tests/test_install_superseded.py` (19 tests) includes end-to-end `install()` runs with `prepare_site`, `find_uv`, `install_dependencies` and `package_dirs` stubbed via `monkeypatch.setitem` on `install.__globals__`.

## 2026-11-11 — install.vfpy removes superseded scripts only when unmodified (Issue 250, WP11A)

`install.vfpy` logs a sha256 per installed script (`hashes` in install.log). On the next install a script that the new package no longer ships is removed only if it is listed in the last install record, lies under FontLab's `Scripts/`, and still has its logged hash. Edited files, files without a logged hash (older logs), and folders are kept and reported; entries with `..` or outside the data folder are refused; a corrupt install.log removes nothing. `FONTLAB_INSTALL_DRY_RUN=1` prints the report and changes nothing. New `tools/check_install_copies.py` lists every workspace `install.vfpy` sha256 against this copy (rollout to the other repos is a later mechanical byte-identical copy; not done here). `tests/test_install_superseded.py`: 14 tests, including a stubbed prepare_site/uv end-to-end reinstall through install().

## 2026-11-11 — Issue 250: sibling studio status text under PythonQt

`Studio.shell_status` in `spacing_studio`, `anchor_studio` and `transform_studio` called `status.text()`, which raises `TypeError: 'str' object is not callable` when PythonQt exposes `text` as a property. All three, and `layer_manager.refusal_text`, now read it through `studios._kerning_ui.get`. A str-property/method fake test per site fails without the change. `fontui/batch.py:265` and `fontui/designspace.py:140` read `status.text` as a property inside an f-string; that is correct under PythonQt (the host) and wrong only under the offline PySide binding, so they are unchanged. Native check of a refused write in each studio stays an open TODO row.

## 2026-11-11 — Issue 250: Layer Manager refusal text under PythonQt

`layer_manager/_from_font.py` and `deliver.py` read `tool.shell.status.text()`, which fails in PythonQt where `text` is a property. Both now call `_shared.refusal_text(tool)`, which reads either form (property or method) and falls back to "The write was refused." New test `test_refusal_text_when_status_text_is_property_then_string_is_used` covers property, method and blank. Full App suite on 11fd1d6 plus this change: 12475 passed, 28 skipped, 3 failed (`tests/test_cov_ui_info.py` cold-cleanup, which also fail on the unmodified tree); tests_docs 36 OK. Native FontLab check stays an open TODO row.

## 2026-11-11 — Kerning writes tolerate stale class members (Issue 250, live round 8)

A kerning class whose member glyph is absent from the font (common in subset fonts) made `validate_pair` raise "Unknown glyph: Aacute" for every write, because the batch re-validated every re-seeded pair's class members. `validate_pair(..., members=False)` now checks only class identity and side for pairs the batch merely re-seeds; pairs the user edits are still fully validated. Regression test `test_stale_class_member_when_unrelated_pair_edited_then_write_succeeds` fails before the fix. Live acceptance in FontLab remains with the owner.

## 2026-11-11 — feature_blocks native-import pin review minors (Issue 250)

Review minors on the row-48 pin: `test_write_when_fontlab_missing_then_backend_import_fails_first` wraps traceback paths in `Path(str(...))`, so a regression (the App's own `import fontlab` moved ahead of the backend constructor) now fails with `AssertionError` instead of crashing with `AttributeError`; checked with that mutant, 3/3 fail. A comment at the `import_module("fontlab")` call in `src/fontlabapp/fontui/feature_blocks.py` records why it stays.

## 2026-11-11 — Issue 250 WP09b review fixes

- Live round 9 D1: `bindings.dirty()` in `e07_e09_actions.py` no longer counts callable `pending`/`dirty` (Apply Unicode Map's `SelectionPanel.pending` hook method) as staged edits, so Refresh and Preview open; regression test fails before the fix.
- WORK.md: restored the other lanes' notes; only the WP09 section is added.
- Qt wrapper reads: drag-distance QPoint `x`/`y` in six drag profiles and
  `type`/`key`/`pos().x()`/`rect.left`/`width` in Glyph Review Priorities now go
  through `value()`; native check stays an open TODO row.
- New `tests/test_core_pythonqt_unicode_pair_profiles.py`: with the existing WP09
  App tests the App suite alone now covers `apply_unicode_map` 89% lines / 100%
  branches and `pair_proof_generator` 98% / ~94% (were 26% and 56%); 217 passed.

## 2026-11-11 — Issue 250 WP09: core PythonQt labs

Added nine tabbed labs retaining all 51 original filtering, tree, metrics,
calendar, completion, drag/drop, proof, Unicode and review profiles. Existing
App controllers and three packaged Lessons routes remain the underlying
implementations; first-party current script bodies moved into callable App
profile modules. Public `fontui.core_pythonqt_lab` and
`studios.core_pythonqt_labs.show` reuse AppShell and read-only TGlyph/TMetrics.
The shell publishes actual profile output, binds captured font/master context,
refuses changed targets, preserves drafts and routes local Close through owned
whole-lab cleanup. Existing profile writers retain their history/validation.

The final prepared full App suite passes **12,789 tests, 22 existing skips,
zero failures** on arm64 Python 3.11 with offscreen Qt. Its matched Plugmix
cohort avoids the stale supplied reference; all App source, tests and demos
match the tested snapshot byte-for-byte. Combined final App/Examples coverage
passes separately for all **40 changed App production modules**, with minimum
**90.55% lines and 81.25% branches**. Pinned Ruff 0.14.10 passes all 142 changed
Python files across the two repositories. The canonical coverage wrapper exits
3 because this local lane has no milestone baseline or upstream merge-base.

The lab-only sorting adapters preserve source-row identity, numeric and Unicode
order, selected glyphs, active-editor targets and interactive column widths.
Trees, fixed factor matrices and user-arranged proof lists retain their semantic
order. A complete Drag Drop Lab renders actual A/V cells in read-only TMetrics;
local Apply, target changes and refused Close have regression coverage. The
built wheel matches all 809 production Python files. Native FontLab,
installed-menu cleanup and truthful post-commit catalogue regeneration remain
open; standalone Qt is not PythonQt acceptance.

## 2026-11-11 — Issue 250 WPF: WP02 integration and resumable preview cleanup

Resolved the App documentation conflicts, retaining both branches' entries.
TGlyph and TMetrics now stop repeated Close only after `_close_complete`, so
AppShell can retry a transient disconnect failure. Existing timer stopping,
callback clearing and the shared lifecycle cleanup remain intact. Four new
actual-preview/AppShell button regressions cover raised and false-returning
disconnects: four failed before the two-line fix and four pass after it;
independent review also replayed all four successfully.

The full offscreen arm64 Python 3.11 suite passes **12,598 tests, 22 existing
skips, zero failures** against byte-identical App source and matching Plugmix
`87fc0ec24cc8c8c8306e3de407cf5f41eb884a41`. The supplied older read-only Plugmix
reference lacked the four C8 coordinate-filter bundles: the initial complete
run recorded 12,580 passed, 18 related failures and 22 skips. No oracle was
weakened and no reference symlink changed. The matched snapshot verified 1,575
App files; final production/test/demo equivalence remains independently checked.

Complete-module line/branch coverage with zero exclusions: fontui.__init__
100/90%; appshell 100/100%; tglyph 97.24/94.76%; tglyph_edit 99.26/98.28%;
tmetrics 98.82/95.73%. Pinned `uvx ruff==0.14.10 check --no-cache` passes all
19 changed Python files; the repository F821 and whitespace checks pass.
The exact sourced metaswarm recipe was attempted but dependency provisioning
failed on PyPI DNS before tests. Canonical controller, fresh matched ordinary
installation, graph integration and native PythonQt acceptance remain open.
The WPF lane's `app-evidence/report.md` retains commands, fractions and logs.
No commit, push, branch operation or native operation was performed.

## 2026-11-11 — Issue 250 WP02: safe reusable shell

Extended AppShell with frame-inclusive available-screen clamping, preserved
resizes, initial 60% preview allocation, per-task Refresh / Preview Changes /
Apply Changes / Close actions, staged-refresh and unaccepted-plan refusal,
and an About/credits/help tab. Retained task indexes, legacy cleanup adapters,
owned close acknowledgements and actual-button retry after cleanup failure.
TGlyph and glyph_view accept explicit read_only=True; the shared Editor refuses
writes and editing gestures, including O, drag, delete, nudge and clipboard
shortcuts. Editable defaults remain compatible; later packages opt previews in.

Tests-first regressions and independent source review completed. Final prepared
arm64 Python 3.11 offscreen full suite: 12,256 passed, 28 existing skips, zero
failures. Additional constructor-cleanup coverage run: 43 passed; independent
new-test check: two passed. Changed-test review: 440 passed before the two
additions. Pinned Ruff 0.14.10 passes all 17 changed Python files and repository
F821 checks. Complete modules, zero exclusions, line/branch percentages:
fontui.__init__ 100/90; appshell 100/100; tglyph 97.24/94.76;
tglyph_edit 99.26/98.28.

Canonical G-App cannot create owner-workspace evidence from this lane; the
unchanged lane-local recipe also failed fresh dependency provisioning (PyPI
DNS). Full tests instead used a lane-local venv with prepared dependencies and
verified current-worktree isolated imports. Canonical cohort, graph analysis,
installed artifacts and native FontLab qualification remain open. No commits,
pushes, installations, menu/provenance rewrites or native font edits.

## 2026-11-11 — Plugmix consumer guard resolves relative imports (Issue 250)

Review fix I-1: the AST guard now resolves relative imports against the module's package, so `from ..plugmix import x` and `from .. import plugmix` are flagged, and matches `fontlabapp.plugmix` exactly or as a dotted prefix (`plugmixer` is not flagged). The failure text names `ALLOWED_STRINGS`. Two new tests pin the flagged and unflagged shapes.

## 2026-11-11 — Metrics panel Undo/Redo row closed (Issue 250)

The open row "Native: Undo/Redo of the Metrics panel capHeight/composite write" is closed for the composite write: verified live through the real panel model (commit, Undo, Redo, Undo exact; Aacute follows without a double shift; saved-VFJ readback matches). Evidence: `issue250/reports/a5-implementer2-report-12.md`, `live-tests/i2/r87f-live.json`; see the Scriptmix CHANGELOG entry of the same date. Scope limit: only glyph A and the metrics edit were tested; a Master Metrics `capHeight` Undo/Redo was not separately run.

## 2026-11-10 — gate counts and Metrics Undo/Redo row (Issue 250)

Full App suite via `./test.sh -q` on d9f7f49 (the tree after 03ff266, e4c5116 and the follow-ups), own log `reports/app-gate-d9f7f49.log`: 12522 passed, 22 skipped, 0 failed in 155 s. Other agents' pytest processes were running on the machine but not in this checkout. This stands in for the unrecorded 03ff266 counts. Added the open TODO row for native Undo/Redo of the Metrics panel capHeight/composite write.

## 2026-11-11 — Issue 250: positional coordinate edits in the Plugmix filter writer (C8)

`fontlabapp.plugins.filters.apply` now commits, besides contour deletions,
finite positional coordinate edits from filters that keep contour/node
topology, order and metadata. Mixed deletion/replacement, reordering, topology
or metadata changes, anchors/advance edits and non-finite values are refused
before any native write; native node ids and raw node states fence the plan.
This is the App half of the four Plugmix coordinate filters (MoveOutlines,
RoundOutlineToGrid, ScaleOutlines, SlantOutlines), which require this change;
the Plugmix change lands after it. Lane tests: 53 focused App filter tests;
`apply.py` 100% lines and branches. Merged-tree App gate (with the Plugmix lane bundles in the sibling): 12,574 passed, 22 skipped; graph staged analysis risk low, 0 affected processes. Native
FontLab history/reopen acceptance remains open (TODO).

## 2026-11-11 — Issue 250: docs module-count pin

- `tests_docs/test_site.py`: module-row pin 770 -> 771 for `fontlabapp.fontui.designspace_sources` (C10) and the api-map body hash; the first push `de1eb8c` failed this check in CI.

## 2026-11-11 — Issue 234 #14 designspace report API (C10)

Added the Qt-free `fontui.designspace_sources` report and callback hook beside
C5's unchanged Source Comparison view. Reuses Fontport's FontTools designspace
adapter/UFO backend and App's structural compatibility model. Reports axes/maps,
source paths/layers/design and user locations, six font metrics, first-source
relative glyph-set differences and per-glyph advances/compatibility. Missing
glyphs and single-source inputs remain not comparable; inputs are never saved.

Real tiny UFO/designspace regressions and package-boundary checks pass: 29 tests;
new report module 100% lines (102/102) and branches (22/22), and the runnable
CLI demo 100% lines (11/11) and branches (4/4), no exclusions. Added its API-map
entry and inventory counts without weakening existing integration checks.
Complete App suite on lane-local arm64 Python 3.11: 12,255 passed, 28 existing
skips, zero failures. Fresh metaswarm/uvx provisioning remains PyPI-DNS blocked.
Independent review found no remaining code blocker after the anisotropic-location
refusal regression. Changed-file Ruff and repository F821 checks pass with
installed Ruff 0.14.10. Exact commands and full-suite/provisioning evidence are
in `C10-REPORT.md`.

Supported scope is continuous-axis UFO sources. Discrete axes, anisotropic
locations and multi-axis mappings are refused; FontTools ignores dimensions for
undefined axes. No interpolation/export certification, C5 view wiring, native
PythonQt acceptance, ordinary artifact acceptance or delivery is claimed.

## 2026-11-10 — Issue 250 row 123 landing and test extra

`uharfbuzz>=0.39` joins the `test` extra so the TMetrics shaping tests no longer skip silently in the standard gate (reviewer2 I-1). The eb82fa7 merge keeps main's kerning-unavailable status and uses the one-outline-per-refresh `_outline(self.model, name)` signature.

## 2026-11-10 — Issue 234 UFO and representation inspectors (#16 and #18)

Review fix I-1: the UFO inspection default deadline is now 120 s (was 3 s, too short for a real native font); a test pins it as generous. Pins recomputed from the combined tree after merging origin/main b5122e4 (which carries the C2 browsers): api-map 767 to 770 modules (three new ui.windows/views rows; windows 154 to 157), api-map body hash a963f541 to the combined-tree hash and tests_docs row count 767 to 770; generated docs rebuilt, tests_docs 37 OK. Graph change analysis: risk low. Full App suite on the combined tree is recorded by the pre-push gate run.

Added UFO Roundtrip Inspector with owned temporary export/reopen/import staging,
complete persisted UFO-family comparisons and explicit native adapter limits.
Borrowed sources are never saved or closed. Fontport loss findings include info,
images/data and layer metadata rather than claiming lossless conversion.

Added Representation and Notification Explorer with glyph browsing, decomposed
outline reports, cached area inspection and verified scripting-model observer
registration/delivery. Failed registration cannot claim observation; native
external synchronization is explicitly unverified. Both compositions use Owned
cleanup and have paired App/Scriptmix demos. Independent review found no remaining
source blocker. Focused workflow/API/demo checks: 813 passed; additional complete
API-map/demo-coverage checks: 51 passed. All seven new production files exceed 80%
line and branch coverage (96.30–100% combined). Complete App gate: 12,369 passed,
22 retained skips; paired complete Scriptmix gate: 4,631 passed, two retained skips.
Native and ordinary installed artifact qualification remain open.

## 2026-11-10 — package attribute and Metrics survey rows closed with evidence (Issue 250)

- `fontlabapp.<unknown>` raises `AttributeError` (so `hasattr` is False); the
  `RuntimeError` appears only for the explicit native names (`FL`, `fontgate`,
  `fontlab`, `PythonQt`) off-host. Pinned by `tests/test_top_level_getattr.py`
  (explicit-native-absent and fallback-absent cases); compatibility unchanged.
- `metrics/panel/model.py` `survey()` skips a manual composite whose base moves
  in the same plan; this composite planning fix is unit-proven
  (`tests/test_metrics_panel.py:702-740`). The live check in FontLab 9 on a Lato
  copy moved base A by +7 with a bare `shift_and_set`, not through the Metrics
  panel, so the panel's live write path was not exercised; the saved-VFJ
  readback (`save_font`) showed Aacute's components, offset and advance
  unchanged, but the composite bbox readback may be stale. Master Metrics
  `capHeight` wrote and read back exactly (690.0 to 697.0). Undo/Redo of the
  panel's own write is not verified and stays open: Scriptmix `TODO.md` row 48
  (Metrics writers) and, for `capHeight`, the App `TODO.md` row "Native: Undo/Redo of the Metrics panel capHeight/composite write".

## 2026-11-10 — Issue 234 compositions 11 and 14 (C5)

Added Font Info and Vertical Metrics and Designspace Source Comparison compositions with captured-font ownership and paired Scriptmix menu entries. Paired App demos added. Exact App recipe on the combined tree: 12,507 passed, 22 skipped; both new modules pass the 80% coverage gate (100% and 98.04%). Workflow 14 is partial: it compares glyph advance widths and structural compatibility across open masters/layers only; it does not load a designspace file or compare per-source font metrics (see TODO). Native FontLab and installed-artifact qualification remain open.

## 2026-11-11 — TMetrics fractional kerning row closed with live evidence (Issue 250)

Live FontLab 9 on a font copy through Fontport's `NativeFontBackend.set_kerning`:
-12.4, -12.5, -12.6 and 7.25 are refused with `UnsupportedCapability:
kerning.fractionalHistory: Native kerning history rounds fractional values`
before any write; integer 3 writes and reads back exactly. The readback-differs
error is therefore not reachable for fractions (the probe called `set_kerning` directly; the panel reaches it through `apply_kerning`), so neither rounding nor
rewording is needed. `test_commit_when_backend_refuses_fractional_kerning_then_capability_message_shown`
pins that TMetrics shows the backend reason.

## 2026-11-11 — in-App `fontlabapp.plugmix` references removed (Issue 250)

- No App module imported the deprecated shim; seven module docstrings still named `fontlabapp.plugmix.*` (glyphs identity/others/background, kerning groups, qt painting view, components decompose, masters interpolation outlines) and now name `fontlabapp.plugins.*`. New `tests/test_plugmix_shim_consumers.py` scans every module outside `src/fontlabapp/plugmix` by AST for imports and string/docstring mentions (failed first with seven hits); the entry-point group string `fontlabapp.plugmix` in `plugins/registry.py` is an external contract and is allowed. The shim and its deprecation tests are unchanged. The external-consumer audit row stays open. Verification: App gate green; `src_docs/build.sh` plus `python -m unittest discover -s tests_docs` (the docs CI command, locked `src_docs/requirements.txt` venv) ran 36 tests OK and left the tree clean.

## 2026-11-11 — Issue 250: dependency reads use the target package's glyph order

`guides.inspect.model.dependency_values(package)` read glyph names from the
active font (`masters.inspect.model.all_names()` → `CurrentFont()`), so any
caller given a non-active package (Plugmix filter `apply_filter` auto-facts,
`core.history.glyphs.scan_auto_facts`, anchors, guides) failed with "Glyph source
changed; reopen this tool." It now iterates `package.fgPackage.glyphs`, the
package's own font order. New test
`test_dependency_values_when_package_is_not_active_then_reads_its_own_glyph_order`
failed before the fix; panel fixtures expose `fgPackage` font order. Live
(FontLab 9.0.9808): Move Outlines on non-active a2-plum Regular now applies
(15/15 points Δ(+10, −20), other masters unchanged, one Undo step, exact undo);
unfixed control still raised.

## 2026-11-10 — Issue 234 workflow 6 Interpolation Preview (C6)

Added the read-only designspace-location/two-master preview composition, paired
App demo and Scriptmix menu, fake-font dispatch/lifecycle tests and catalogue/API
entries. Reuses existing designspace controls and interpolation model/painter;
unsupported off-segment locations and incompatible outlines remain explicit.
No font writes, Fontport changes, commits or publication.

App full suite on the landed tree (current origin/main 0fde39a plus this change): 12,390 passed, 22 skipped; the flaky batch-recipe close test passed on this run. Changed-file Ruff passes. Preview module 98% lines (158 statements, one missed) and 54 branches; sequence 100%; both launchers reach 100% of both.
Graph change analysis (detect-changes, task-owned storage): risk low, zero affected processes, not partial. Independent source review passed. Native PythonQt rendering, whole-font/history/
cache preservation and ordinary installed artifacts remain open in PLAN/TODO.
An existing batch-recipe close/cancellation test failed in an earlier App full run
and passed the final run; its receipt and separate investigation remain open.

Docs pins recomputed from the combined tree after merging origin/main 03ff266: api-map rows 763 to 764 (the one added fontui.interpolation_preview row, plus the sequence note), api-map body hash c0e1952b to f7fbf6a0 (diff limited to that row, its section count and the total); generated docs rebuilt with the locked properdocs environment; tests_docs 36 passed.

## 2026-11-10 — Issue 234 workflows 1, 4 and 5 (C2)

Added Open Fonts and Master Overview, Master Compatibility Browser and Node Counts
Across Masters, reusing the existing browsers, preview, native reports and owned
lifecycle. A default-preserving FontBrowser follow option disables automatic
borrowed-cache invalidation in the overview. Added App demos, fake-font tests and
API-map entries. Independent source review approved the corrected selection and
cleanup guards. Final focused App gate: 471 passed; changed modules exceed 80%
line and branch coverage, all three demos reach 100%. Changed Python files pass
Ruff 0.14.10. Scriptmix companion suite: 4,635 passed, two existing skips.

Lander gate on the combined tree (current origin/main including C1, current
sibling mains): exact metaswarm App coverage recipe 12,443 passed, 22 skipped;
changed modules master_compatibility 93.84%, node_counts_masters 96.00%,
open_fonts_overview 94.74%, fonts 100%, all three demos 100%. The docs-site
oracle pins 767 module rows (766 before merging C6) and the api-map hash; ProperDocs
build and 36 `tests_docs` units pass. Native PythonQt and ordinary installed
artifacts remain open.

## 2026-11-11 — batch close test race fixed (Issue 250)

- `tests/test_fontui_batch_recipes.py::test_actual_child_when_between_files_then_cancel_failure_or_close_preserves_partial_outputs[close]` flaked because `release()` (and destroy) drain through `QTimer.singleShot(0)`, yet the test opened the child's `go` barrier at once; the child could write `B-transformed.ufo` before the queued close wrote the cancel request. The test now waits for `process.cancel_path` first. Reproduced about 1 in 3 before; 30 repeats of all five actions green after.

## 2026-11-11 — TMetrics Glyph-window sync matches the font by FontGate id (Issue 250/241)

- `fontui/twindow_host.py` `FontLabHost._block` compared the Fontport `font_id` (the FontGate id, which `findPackageId` matches) with `flPackage.id`, an address-like workspace identity. In FontLab 9.0.9808 the two never match (live: font_id 4056, package.id 523586929536), so TMetrics never read or wrote Glyph-window text. It now compares `package.fgId`. Live, after the fix: FontLab text edits reach TMetrics within the 250 ms poll, a TMetrics commit replaces the Glyph-window text as one literal block, slash names are refused with the diagnostic, named symbols in FontLab leave TMetrics text local, and closing TMetrics stops the poll. Test doubles in `tests/test_twindow_host.py` now give `package.id` and `fgId` different values (13 tests fail without the fix).

## 2026-11-10 — Issue 241 TMetrics/TGlyph lane completion

Extended existing windows: TMetrics now selects master/layer and synchronizes
available literal Glyph-window text through an injectable host; explicit text,
unsubmitted drafts and embedded/read-only previews are preserved. Non-current
master kerning is disabled rather than displaying/writing another master's pair.
TGlyph's O key toggles on/off-curve points with topology refusals, keeping the
explicit-layer transaction path; modifier shortcuts and key-repeat do not edit.
Existing Scriptmix demos are retained. Added fake-host regressions, API-map and
demo references; no upstream reference code was copied.

Independent source review passes after draft-preservation and shortcut fixes.
Combined focused checks: 364 passed, no skips; API/demo index checks: 51 passed;
App demo checks: 177 passed. Every changed production module passes 80% lines
and branches separately with zero exclusions. Changed-file and F821 Ruff pass
using the installed tool. Lander gate on the combined tree (current origin/main
plus this change, current sibling mains): exact metaswarm App coverage recipe
12,364 passed, 22 skipped; changed modules tglyph_edit 98.68%, tmetrics 98.15%,
twindow_host 100%, all five at or above 80%. Exact Scriptmix recipe 4,617 passed,
two retained skips. Graph change analysis: medium risk, one affected flow
(`write_text`, the new text bridge). The docs-site oracle now pins 763
module rows and the new api-map body hash; the locked ProperDocs build and all
36 `tests_docs` units pass. Native FontLab, ordinary artifacts,
Undo/Redo and saved reopen remain open.

## 2026-11-10 — Issue 250: own-menu lookup seam

- `OwnedMenus.own_menu()` returns the owner's own menu (created once) without searching the menubar, so a same-titled menu of another host is never shared. `_menu` falls back to it. Tests cover separation from a same-titled FontLab menu, reuse, and add/remove through the returned menu. Native add/trigger/remove stays in its own TODO row.

## 2026-11-10 — floating panels paint under FontLab's hidden MainWindow (Issue 250)

- `create_panel` now enables updates on a dock it floats because MainWindow is
  hidden, both on creation and when it re-floats after a redock. FontLab
  9.0.9808 keeps its hidden MainWindow at `updatesEnabled` False, and docks
  inherited that, so the Reporters palette opened as a blank window. The
  MainWindow state is not changed. Offscreen Qt regression test with a parent
  whose updates are disabled (created and re-floated cases), plus a
  PythonQt-shaped value-property test.

## 2026-11-10 — TGlyph per-component read failures (Issue 250)

- `fontui/tglyph_model.own_glyph`: when the owner glyph's components cannot load, each component now reports its own failure (cyclic, unsupported, or missing base) and healthy bases still decompose; the owner reason remains only if the layer itself cannot be read. Test: `test_own_glyph_when_owner_unsupported_then_each_component_gets_its_own_reason`.

## 2026-11-10 — TMetrics builds each outline once per refresh (Issue 250)

- `fontui/tmetrics.py` refresh now runs inside `TMetricsModel.outline_scope()`; shaping sidebearings, the drawn-state fingerprint and the painted outlines share one `outline_of` build per glyph (failures cached within the refresh only; follow polls still read fresh). `fingerprint(font, names, read=None)` also fixes a loop variable that would have shadowed the reader. Test: `test_refresh_when_run_shown_then_each_outline_built_once`.

## 2026-11-10 — live font editing rule (Issue 250, D44)

- AGENTS.md: agents test and edit the font open in FontLab 9, starting from the Desktop VFJs, and may save them.

## 2026-11-10 — Master Width Comparison review fixes (Issue 250)

Independent review: APPROVE_WITH_FIXES. Clicking a missing-glyph occurrence
now shows "The selected occurrence has no glyph" and keeps the tool open; font,
layer-identity and read failures still close it. New regression test. The
SimpleNamespace fallback in `sequence_canvas.py` is documented as test-only.
A stray `.coverage` file was dropped and is now ignored. Tests: comparison,
demo and lifecycle 83 passed.

## 2026-11-10 — Master Width Comparison additional consumer evidence

The five source repairs pass independent review and the complete App suite:
12,250 passed, 22 provenance skips in this selection. Every changed production
module exceeds 80% line coverage with zero exclusions; demo coverage is 100%.
The complete byte-verified Scriptmix writable copy passes 4,613 tests with six
retained skips. Original sibling files are unchanged; its catalogue write remains
sandbox-blocked. Full Ruff retains 528 unrelated findings; changed files pass.
Exact commands and limits: [WF3_REPORT.md](WF3_REPORT.md). Preserve the separate
concurrent evidence below. No native, artifact, integration or release claim.

## 2026-11-10 — Master Width Comparison independent source verification

Verified the concurrent workflow #3 repairs: weak-owner callbacks retain live
behavior and release normal owners; non-weakrefable canvas owners use the strong
fallback; Fontport types come through Sequence's editor boundary; the App demo
uses canonical imports. Deliberately updated lifecycle byte pin preserves every
origin and partial-disconnect assertion. No test was weakened.
Scope: only the class-level close/viewport/canvas closures hold the owner weakly;
the destroyed-signal lambdas still hold it until `release_owned` disconnects them,
so destruction order changes only for a close that arrives after disconnection.

App: 12,271 passed, one optional Examples hash audit skipped. Coverage suite:
1,017 passed; lifecycle 97%, sequence 98%, sequence_canvas 89%, comparison 91%.
Independent focused review: 121 passed and changed-file Ruff clean. Full Ruff:
528 existing findings outside the changed workflow files; F821 gate passes.
Scriptmix: 4,612 passed, six retained skips, one catalogue rebuild failure because
the sandbox prohibits sibling documentation writes. All four new menu checks pass.
No Git mutations or native/owner-installation/publication actions were performed.
Exact commands, setup repairs, output tails and evidence are in
[ISSUE234-WF3-REPORT.md](ISSUE234-WF3-REPORT.md). Ordinary/native qualification,
full lint and the writable-sibling catalogue gate remain open in PLAN/TODO.

## 2026-11-10 — Issue 210 plugin core and Extensions candidate

Review fixes (independent review, APPROVE_WITH_FIXES): an uninstalled source
checkout no longer rejects every bundle by `min_app_version`; `uninstall()`
closes palettes before the Reporters panel so a palette refusal keeps the
panel; core error messages name `fontlabapp.plugins`. The API-map site was
rebuilt with the locked Python 3.13 docs environment (tests_docs: 36 OK).
Verified: App suite 12,133 passed / 36 skipped; Plugmix 353 passed.

Moved the host contracts, discovery, registry and lifecycle to
`fontlabapp.plugins`. The one-release `fontlabapp.plugmix` shim emits
DeprecationWarning and retains module identity, including concrete imports when
the companion bundles are available. Plugmix now owns all 39 reporters plus the
Filter, Palette, Tool and General examples in 43 manifest bundles.

Added sorted manifest validation and idempotent discovery, guarded rescan
activation, the synchronized Reporters panel/menu, Tools > Tool and Window >
Panels seams. Rescan preserves native action ownership. App installation adds
one marked startup hook, preserves existing bytes and supports retry-safe
removal after an interrupted uninstall.

Final arm64 Python 3.11.18 checks: full App suite 12,133 passed, 36 retained
skips; changed-module coverage run 611 passed. All 34 complete App production
modules meet 80% line and 80% branch coverage separately. The paired Plugmix
suite passed 353 tests and all 44 changed production-module coverage gates.
Ruff 0.14.10 F821 and whitespace checks passed. Independent core, startup and
pack source reviews approved after fixing the identified lifecycle regressions.
Updated the API-map test count/hash for the moved paths; all five source
count/set/uniqueness/guide-hash assertions pass. Generated-site checks remain open.

Exact commands, per-module coverage, skip reasons and native checks are in
ISSUE210-REPORT.md. The direct suites used an owned test interpreter with
available read-only dependencies; PyPI DNS prevented fresh uv setup. Native
FontLab, ordinary installed artifacts, generated-site rebuilding and delivery
remain unverified. No commit, push, tag, user installation or FontLab launch
was performed. Existing native and Issue 211 obligations remain open.

## 2026-11-10 — isolated graph guidance proposal

Prepare append-only AGENTS guidance for separate task-owned graph HOME and storage, ordinary-analysis scope and independently reviewed bounded recovery. Preserve existing integration rules and acceptance holds. This documentation proposal records no new runtime, test, native, integration or publication result.

## 2026-11-10 — Batch recipe filename literal passes candidate checks

Quoted the filename template in both paired demo/menu docstrings and updated
only the new Scriptmix catalogue row's source hash. Executable script ASTs and
all old tests remain unchanged; the other 200 catalogue records are exact. The
new rendered-HTML regression reuses the existing parser and now sees the full
`<source-name>-transformed.ufo` literal, after the retained genuine-HTML RED.

Candidate checks passed: App demo three cases, Scriptmix menu three; both complete
scripts cover 7/7 statement-plus-branch obligations (100%, zero exclusions). The
complete Scriptmix suite passed 4,609 cases with the same six retained skips.
Both strict documentation builds passed, followed by App 36 and Scriptmix 43
documentation units, 14 legacy checks and pinned Ruff on the three changed Python
files. These are explicit uncommitted candidate-copy checks, not a new containing
commit or live-site result. The original public rendering failure remains open
until reviewed additive delivery, genuine-commit docs, exact CI/generated parity
and a new public browser check. Source floor eight and ordinary/native/history/
reopen qualification remain unchanged. Prior diagnosis and histories are retained.

## 2026-11-10 — Batch recipe public literal defect diagnosed

P2 source commits reached main through normal hooks and exact-commit CI; the
reviewed generated outputs match all 525 rendered files. The actual public
workbench page nevertheless hides the angle-bracket filename placeholder: its
source says `<source-name>-transformed.ufo`, while visible text loses the prefix.
A private regression using the existing HTML parser fails against genuine
committed HTML (one assertion failure, no errors/skips). The correction is pending:
quote the literal in both paired docstrings, update only the new catalogue row's
source hash and add one rendered-HTML regression. All prior source/runtime and
live failure evidence remains retained. Normal fix delivery, exact CI and a new
public check are still required; no ordinary/native or source-floor promotion.

## 2026-11-10 — P2 source/test review passed; integration gates remain

Implemented the recipe-only Batch UFO Recipe Workbench and its actual demo with
real TransformEditor(None) controls and BatchPanel results, log and progress.

The independently reviewed fix closes in-flight close/nested-provider acquisition
and scheduling-failure retry defects. New real-Qt regressions cover complete
fractional reopened geometry and component conjugation across layers, font/glyph
guides and metadata/resources; connected Add/Start and captured-run stability;
active-window cancellation/isolation and the existing supervisor's actual
terminate/kill/terminal cleanup; and retained primary/cleanup errors with retry
only for unacknowledged owners. Shared helpers and worker policy are unchanged.

Final source checks passed: App 12,212 cases with no skips; Scriptmix 4,609 with
six unchanged skips; affected App 524; targeted Fontport 92; pinned Ruff on all
15 changed Python files. Complete workbench coverage is 187/202 statement-plus-
branch obligations (92.5743%); demo and menu each cover 7/7 (100%), all with zero
exclusions. Independent scoped specification/quality review passed F1–F3.
Retain the original close/reentry and queue REDs, the initial missing-shaping
runtime epoch and setup failures. The new font-guideline assertion correction
compares against independently transformed info while preserving all 107 other
info fields and the complete original test prefix.

These results close the implementation and source-test portions only. Post-change
graph, ledger/controller source qualification, genuine-commit documentation,
normal main integration and exact-commit CI remain open. No new commit, push,
ordinary installation, native result or publication is claimed. Source floor
eight, full parity zero, all 8,723 obligations and the minimum eighteen workflows
remain unchanged; ordinary artifacts/two prefixes/archives and native history,
Undo/Redo/reopen, literal U+2029, canonical adoption and private Pages holds remain
separate. Earlier history and its Scriptmix intermediate-file correction stand.

## 2026-11-10 — P1 containment round delivered; P2 remains next

The reviewed [P1 round commit](https://github.com/fontlabcom/fontlab-fontlabapp/commit/9b6c0e6ff5f21fe4dc1a3f5f3907d82ed6629ab8)
reached main through the normal qualified pre-push gate (24 core passes and four
retained opt-in skips). Its [exact-commit Actions run](https://github.com/fontlabcom/fontlab-fontlabapp/actions/runs/42802872225)
succeeded. Fontport's filesystem-identity containment fix and App regressions
resolved [issue 8624](https://github.com/Fontlab/fl/issues/8624), now closed with
[verified resolution evidence](https://github.com/Fontlab/fl/issues/8624#issuecomment-6765750168).
This completes the former P1 reproduction, source-review and main-delivery tasks;
it does not implement the P2 recipe-workbench composition.

Retained source gates are Fontport 5,076 passes plus one existing corpus skip,
271 affected App passes and 96.9231% complete batch-module combined coverage with
zero exclusions, including the unchanged covered 0.5-second startup check.
The commit-bound documentation gates passed three strict builds, 114 unit checks
and 14 legacy checks. All 524 rendered files match (App 54, Fontport 60,
Scriptmix 410). Fontport's [generated docs child](https://github.com/fontlabcom/fontlab-fontport/commit/c06b0b4d68dc11853e36e3b2e5db5daa8adae242)
is a direct child of its source commit and changes only two generated docs files.
Scriptmix's [public Pages run](https://github.com/fontlabcom/fontlab-python-scriptmix/actions/runs/42803269873)
succeeded; its unchanged 410 rendered files retain the earlier nine-route browser
proof. No new browser run or native qualification is claimed.

Correction to the earlier catalogue-intermediate shorthand: of 285 Scriptmix
Markdown intermediates, 14 match, 262 tracked files differ and nine generated
files are absent from the committed tree. The 271 differences are not all tracked
revision changes. The generator uses the last commit affecting the Scripts tree
(`git log -1 --format=%H -- Scripts`), currently
`09a09447df23d87373a8e4a3fa13381dc946d337`, not the whole source commit or a per-file
revision. The qualified publication is the 410 rendered files; this is not a
695-file parity claim or a waiver for missing generated intermediates.

P2 planning now targets actual recipe-only controls plus BatchPanel results,
with no implicit font or geometry preview. Source floor eight, full parity zero,
all 8,723 obligations and the minimum eighteen workflows remain unchanged.
Ordinary artifacts/two-prefix installation, native/history/reopen, U+2029,
archives, canonical adoption and other publication gates remain open.

## 2026-11-10 — batch filesystem-alias boundary regressions (Refs #8624)

Four real Qt cases now cover case and Unicode aliases into later input UFOs and reversed source order. The first run reached an actual process-launch attempt and OS permission refusal instead of containment; an owned non-executable selection prevented worker execution, and complete rich input trees/models were preserved. With the corrected shared Fontport helper, every case refuses with the exact containment diagnostic before any process-launch attempt. App production and all existing batch/worker/deferred/lifecycle tests remain unchanged.

The affected App cohort passes 271 cases, including the original three containment cases, unchanged covered 0.5-second startup oracle and real pipe/socket across-poll controls. Fontport passes 5,076 tests plus one existing corpus skip; complete changed helper coverage is 96.9231% combined with zero exclusions, and pinned Ruff passes the three changed Python files. A fresh owned isolated source cohort resolves the corrected helper; old recorded origins remain preserved.

The earlier lexical containment candidate failed independent review; its source-check results do not establish correctness. This successor remains source/standalone Qt evidence for [Refs #8624](https://github.com/Fontlab/fl/issues/8624), with independent review, current graph, commit-bound docs and normal main/CI delivery pending. P2, source17, full ordinary/native/history/reopen and canonical acceptance remain open; source floor eight/full parity zero are unchanged.

## 2026-11-10 — reviewed main and documentation delivery verified

The additive [X2 source commit](https://github.com/fontlabcom/fontlab-fontlabapp/commit/0597677dc1809d496d4fd662e12338a8c0451273) passed its genuine commit-bound strict documentation build and all 36 documentation unittest cases. Independent source/fix and graph reviews passed before normal push. The qualified installed pre-push gate passed 24 core tests with four existing opt-in skips. [Exact-X2 CI](https://github.com/fontlabcom/fontlab-fontlabapp/actions/runs/42783431170) succeeded, and the direct [documentation-only successor](https://github.com/fontlabcom/fontlab-fontlabapp/commit/a641d25f4fed820ec93314ffb34e9dff45409628) preserved all non-docs source while delivering 54 generated files byte-for-byte equal to the commit-bound build.

Across App, Fontport and Scriptmix, all 524 delivered generated files match. Scriptmix's 271 differing tracked catalogue Markdown intermediates are historical source-link revisions: the build regenerates them as inputs and commits only rendered docs. This is not a claim that all 695 Scriptmix output/intermediate files match. The public Scriptmix Font UI Lab category and all eight new menu routes passed live checks, including immutable source links and source hashes. Private App/Fontport Pages operations remain held.

This closes the recorded X2 documentation, reviewed combined-main source, normal-push and exact-commit CI tasks. Earlier candidate and failure entries remain historical evidence. Source qualification remains eight workflows, full workflow parity zero, all 8,723 obligations and the minimum eighteen-workflow scope retained. Genuine archives/distributions/two ordinary prefixes, native/history/reopen, literal paragraph-separator editing, canonical adoption and remaining publication gates are not closed by this delivery.

## 2026-11-10 — App documentation candidate corrected

Corrected the exact API census from 790 to 799 and the fixed canonical api-map digest. All original 790 rows, the nine named additions, other guide digests, public-set and native-limit assertions are preserved.

The strict build and 36 documentation unittest cases pass in owned full-history X1 copies with the admitted documentation-only overlay. Pinned Ruff 0.14.10 F/py313 passes all four changed docs test files. The earlier failures remain retained. All 42 production source hashes and their full-suite/coverage bindings remain unchanged.

This closes the candidate correction only. Independent fix review, post-change graph checks, an additive X2 commit and fresh X2 commit-bound documentation checks remain before normal hooked push and exact-commit CI. Generated-output promotion, full ordinary-product/native acceptance and private publication remain separate; source floor eight and zero full workflow parity are unchanged.

## 2026-11-10 — combined main-source verification

The reconciled App, Fontport and Scriptmix source passed the complete suites:
App 12,133 tests with no skips; Fontport 5,047 with one retained corpus skip;
Scriptmix 4,606 with six retained skips. The 42 complete changed production
modules reached 89.3023–100% combined coverage with zero excluded lines.
Pinned Ruff passed all 88 scoped Python files. Paired installed Plugmix consumers
passed 100 tests; the strict installed reader/lifecycle checks passed 31.

These results qualify the recorded source-test epoch only. They do not establish
full ordinary-product or native acceptance. Independent combined review, a main
commit, normal push and exact-commit remote CI remain pending. Tracked-change
graph analysis reports CRITICAL, HIGH and LOW risks; the separate staged graph
gate for 49 new paths remains pending. Documentation builds and generated-output
lineage remain separate delivery gates. Source floor eight, ten remaining source
workflows, zero full workflow parity and all 8,723 retained obligations are
unchanged. Existing ordinary/native and private-publication holds remain.

## 2026-11-10 — qualified source carried into main reconciliation

Feature Source and Proof (#10) is independently source-qualified, including
lossless supported UFO source, ordinary code view and safe refusals. Its retained
full suites passed App 10,377, Fontport 5,017 with one existing corpus skip, and
Scriptmix 4,583 with six existing skips. Detached Transform Preview (#15) is also
independently source-qualified; its retained full App run passed 10,544 and
Scriptmix passed 4,590 with six existing skips. The common final before-model
digest is included in the qualified #15 source fixture.

The minimum source floor is eight of eighteen; ten compositions still lack source,
full workflow parity remains zero and all 8,723 obligations remain. These are
retained source-epoch results, not tests of this new main union. Combined-source
tests, independent integration review, containing commits, exact-SHA remote CI,
matching ordinary artifacts, native/history/reopen and publication gates remain
open. Full literal-U+2029 editing remains pending; safe refusal is not successful
editing. Existing history below is preserved.

## 2026-11-10 — Detached Transform Preview source candidate

Port the independently reviewed detached snapshot composition with explicit target
selection, real before/after proofs, early invalidation, reentrant target handling
and owned cleanup. Source tests and independent product review are pending; the
source floor remains seven and full parity remains unqualified. Ordinary artifacts,
native FontLab and delivery remain separate.

Reconcile current #10 status: Feature Source and Proof is source-qualified with
App 10,377 passing tests, Fontport 5,017 plus one existing GetGo corpus skip and
Scriptmix 4,583 plus six existing conditional skips. Retain ordinary code view and
safe refusals; ordinary artifacts, native PythonQt5/history/reopen and full literal
U+2029 editing remain pending. Earlier entries below retain their historical scope.

## 2026-11-10 — Shared transform helper source qualification

Independent spec/quality review and controller verification qualify the bounded shared transform invalidation SOURCE MVP. Its tested source epoch passed 430 focused tests and the complete App suite: 10,439 passed, 100 existing warnings, zero failures/errors/skips. Complete-module statement/branch coverage is 96.45% for `fontui/transform.py` and 100% for `fontui/__init__.py`, with zero exclusions. This documentation rollup retains that tested epoch; no tests were rerun for these Markdown-only changes.

Workflow #15 is not complete: the source-workflow floor remains seven and full-parity acceptance remains zero. Full detached composition, backend-stored capture/borrowed-cache preservation, explicit layer/target/generation, resources/lifetime, complete views/menus, ordinary artifacts/archives, native history/reopen and canonical/remote gates remain pending, with all 8,723 obligations and the minimum eighteen workflows retained. PLAN/TODO now carry deferred nonblocking M1: add a common final full `before_model` digest assertion after temporary fault restoration and before fixture cleanup when extending the composition tests, and include it in whole-branch triage.

## 2026-11-10 — Shared transform invalidation candidate

Add an optional invalidation callback after the initial legacy preview. Update, intensity synchronization, Reset and selected load clear the current result before work; callback reentry/closure refuses, ordinary callback errors report while the owner is available, and BaseException restores the fence before propagating. Default factory forwarding and successful callback behavior remain unchanged.

The focused cohort passes 430 tests, including real Qt, two actual sequence views, owned font models, independent nonidentity geometry, early/final invalidation, refusal and exact borrowed source/cache/pending-edit preservation. Complete-module statement/branch coverage is 96.45% for the transform helper and 100% for its factory module, with zero exclusions. Retain the initial missing-API setup result and the corrected new bridge's closed-peer publication failure. Complete App testing and independent product review remain pending at this entry; workflow #15, ordinary artifacts and native/history/reopen qualification remain open. Seven other workflows are source-qualified.

## 2026-11-09 — API-map public contract correction

Document only `show` as the explicit feature-proof public export and reconcile the widget/window/total counts with all 626 module rows. The complete unchanged API-facade cohort passes 42 tests. Production and test code are unchanged; independent review and full App qualification remain pending.

## 2026-11-09 — Demo feature-source test-host compatibility

Use the original guarded SourceInput with owned real Qt controls in the offline demo fixture, preserving all prior demo lifecycle and fault assertions. Verify current/initial document and widget cleanup, unsupported selected-input refusal and the actual owner-close fence. Update two text accessors and add the source/proof API-map rows. The same-process covering cohort passes 250 tests; production source is unchanged. Independent review, full App/Scriptmix reruns and ordinary/native qualification remain pending.

## 2026-11-09 — Current feature-source documentation

Reconcile the current feature-source overview and remaining qualification plan with the passed independent code/focused review. Focused UFO source preservation and duplicate inspection are implemented; complete source suites and ordinary/native qualification remain pending.

## 2026-11-09 — Exact feature source integration candidate

Inspect duplicate feature tags as complete source, with disabled editing and a truthful refusal reason that resets on refresh. Verify CR-preserving Apply through the actual UFO backend and upgrade the shared-control fixture to real Qt while retaining its labels and actions. Source qualification remains subject to independent review and complete controlled suites; ordinary and native acceptance are separate.

## 2026-11-09 — Feature Source and Proof integration candidate

Feature Source and Proof is available through `fontlabapp.fontui.feature_proof.show(font, parent=None)`. It keeps the ordinary code view, refuses unsupported input before selection loss, and quarantines opaque document changes until explicit Revert. Accepted source Apply refreshes the independent Unicode/kerning sequence once; it does not compile or shape OpenType features. The window captures one borrowed font. External changes retain dirty drafts with a warning; explicit Apply can overwrite newer source. Refresh proof retries only the view. Original paragraph separators are inspect-only. Exact all-CR source preservation remains under investigation; this candidate is not yet source-qualified. Native PythonQt/FontLab, full literal paragraph-separator editing and broader clipboard routes remain unqualified.

The mixed-EOL draft-switch loss was reproduced before repair. The existing two feature suites pass with real guarded text controls. All 183 inherited boundary controls execute on the actual new module. The actual fresh owned offscreen product run qualifies safe and unsafe Paste through native paste, standard key and native menu, plus Enter: safe source applies once, unsafe source retains the pre-call selection, and two complete fonts are checked. The source/proof controller retains both child acknowledgements and retries cleanup without replaying source writes.

Focused failures remain retained: all-CR reader synthesis can rewrite an untouched sibling, and old current-count/fake-text view tests need finite amendments. No full suite, source acceptance, installed artifact, native FontLab, canonical promotion, commit or publication is claimed. Earlier history remains unchanged below.

## 2026-11-09 — Feature-source corruption reproduced; repair pending

Confirmed App feature-source loss in a bounded, independently reviewed real
Qt6/editor/RFont/UFO-backend run: 19 cases, nine NBSP/U+2028/U+2029 stored-source
discrepancies across no-op/edit/switch, six unexpected-write cases and 12 actual
writes in total, exit 0. Unrelated two-font data and UI teardown were preserved.
This qualifies the reproduction, not a source fix or native PythonQt5 behavior.

The chosen repair direction keeps ordinary code view with qualified safe refusals;
full literal-U+2029 editing remains pending. New separator input and refused-draft
selection switching still need a safe contract and reviewed finite repair scope.
No product fix has been applied, and #10 remains without source. All six existing
source implementations, twelve remaining in the minimum eighteen, 8,723 obligations
and the prior #9 suite evidence and separate delivery gates below remain unchanged.

## 2026-11-09 — Kerning Group Explorer finite source acceptance

Independent final review and controller verification accepted #9 source and
closed both cleanup findings. Public release fences both editors/previews and
Apply callbacks immediately, then queues cleanup until actual acknowledgements;
queued interruptions retain the original exception and owners for explicit retry.
Real editor/preview callbacks and complete two-font preservation remain covered.
Arbitrary nested Qt event loops and native painting remain unqualified.

The controlled full App suite passed 10,291 tests with 100 warnings and zero
skips/errors/failures. Full isolated Scriptmix passed 4,576 with six inherited
skips and zero errors/failures. Both exited 0. The skips retain four original-source
audits requiring their explicit source root, one external rescued-source audit
requiring opt-in, and Spacing Preview's absent selection read; none is new to #9.
Generated catalogue output remains isolated test evidence. All 21 source-bound
whole-module gates remain >=80% combined with zero exclusions; the corrected
controller retains 238/244 points (97.54%).

Six source implementations (#2, #7, #13, #12, #8 and #9) leave twelve without source
in the minimum eighteen; this does not mean six fully accepted workflows. All
8,723 obligations and the 18-or-more floor remain. Complete-source archives,
genuine matched A1 wheel/sdist/rebuilt-wheel artifacts and two ordinary prefixes
remain batched after the remaining A1 source increments. Native whole-font/history,
Undo/Redo/reopen, containing revision, canonical/owner installation, remote delivery
and publication remain separate. Earlier results, failures and wrapper provenance
limits below retain their original scope and are not retroactively changed.

## 2026-11-09 — Kerning Group Explorer callback cleanup fix candidate

Public release now fences both editors, both previews and Apply callbacks
immediately, queues one cleanup attempt and returns False until real cleanup
acknowledgements complete. The previous synchronous cleanup entry remains
private for the unwound constructor and direct failure/retry checks. Actual
standalone Kerning Apply and Sequence update callbacks retain their children
until callback return. Queued cleanup contains KeyboardInterrupt/SystemExit,
retains the same exception and owners, and waits for explicit retry after failure.

Eight new failing cases reproduced the two review findings; four terminal-signal
cases already passed. All 1,488 tests in the affected 22-file App cohort now pass,
exit 0, including the twelve new cases and prior font/error/owner/ACK oracles.
One old immediate-success assertion was explicitly adapted to queued completion;
its failed run remains evidence. Complete controller coverage is 238/244 combined
points (97.54%), with zero exclusions. The other twenty exact-source module gates
remain retained, for twenty-one total. Pinned Python 3.11 Ruff checks pass.

This is a fix candidate for independent re-review. Root's controlled frozen full
App/Scriptmix pair remains pending; no full suite was rerun here. Earlier counts
and failures below remain historical. Arbitrary nested Qt event loops and native
painting are unqualified. All 8,723 obligations, the minimum eighteen workflows,
batched A1 archives/genuine artifacts/two ordinary installs, native/history/reopen,
containing revision, canonical and publication gates remain separate.

## 2026-11-09 — Kerning Group Explorer source candidate

- Compose the existing group and kerning editors over one captured font, with
  explicit Use-left/right, draft-preserving accepted-group revalidation and
  distinct member/representative-pair previews. Existing algorithms stay intact.
- Add the real App demo and lazy Scriptmix menu. Retain all four owners through
  construction/cleanup faults; fence callbacks before cleanup and defer active
  dispatch teardown with one queued request and positive ACK retry.
- Verify 1,476 affected App tests, 87 unchanged Fontport tests and 65 finite
  isolated Scriptmix tests plus one inherited skip, all exit 0. Whole-module
  combined gates are 231/234, 9/9 and 9/9, zero exclusions; retain the prior
  eighteen exact-source gates. Current counts are 196/265/95; frozen 190/259
  and original 350 classifications are unchanged.
- Keep independent review, one controlled frozen full-suite pair and all matched
  A1 artifact/ordinary, native/history/reopen, containing-commit, canonical and
  publication gates pending. No release floor or native acceptance is asserted.

## 2026-11-09 — Kerning Proof Workbench source accepted

Independent review and controller verification accept the finite Kerning Proof
Workbench source, real App demo, lazy menu and R2 repair. Both review findings
are closed: direct release fences editor/Sequence work before fallible cleanup,
and refresh captures the empty-key branch before callbacks can change it.

The controlled full App run passes 10,165 tests with 100 warnings, zero failures,
errors or skips, and exit 0. The corrected full Scriptmix run passes 4,569 tests
with six inherited skips, zero failures/errors and exit 0. Its first isolated
run remains recorded as 4,546 passes, six skips and 23 setup errors, exit 1.
The existing documented Fontport source override and a fresh isolated copy
resolved that setup issue without production or test changes. The earlier App
run's missing command/exit provenance remains historical; the new controlled
result does not retroactively reconstruct it.

The current coverage inventory has 18 unique complete-module gates, each at
least 80% combined statements/branches with zero exclusions: the fourteen prior
paths with kerning's metric replaced, plus Sequence, the window, App demo and
menu. The five current kerning-workflow results are 236/237, 249/249, 149/154,
9/9 and 9/9; the unchanged menu reuses its exact prior measurement.

Five compositions have source implementations (#2, #7, #13, #12 and #8);
thirteen of the minimum eighteen remain without source implementation. This
is not five fully accepted workflows. Next is the separately reviewed #9
Kerning Group Explorer source preparation, followed by the remaining A1 work.
Complete private archives, genuine wheel/sdist and two fresh ordinary install
checks remain pending for one reviewed matched A1 batch. Earlier A0 artifacts
qualify only their exact older bytes. Containing commits, truthful source links,
native master/whole-font/history/Undo/Redo/save-reopen, canonical adoption,
owner installation, delivery and publication remain separate. All 8,723
obligations and the 18-or-more workflow floor remain required.

## 2026-11-09 — Kerning Proof Workbench review fixes

Fence the real editor and Sequence and clear the Apply callback before any
fallible direct release cleanup, including refusal and interruption. Retained
owners remain available for cleanup retry. Capture the actual empty-key inspect
branch before its update callback can change the controls, preventing a second
layout/read/publication pass. Keep inspect, public signatures, the original
selection identity loop and borrowed-font lifetime unchanged.

Seven new real-backend regressions first failed; the six release cases also
triggered the complete-font preservation oracle after prohibited writes. All
seven now pass. The affected 33-module cohort passes 1,894 tests with 24 existing
warnings and terminal exit 0. Whole-module combined coverage is 236/237 for
kerning, 249/249 for Sequence, 149/154 for the window and 9/9 for the App demo,
with zero exclusions; the unchanged menu retains its prior 9/9 evidence.
Pinned Ruff checks pass. An initial affected-cohort collection ordering conflict
was resolved by collecting its existing GUI fixture first, without editing
those tests. Independent re-review and controlled full App/isolated Scriptmix
verification remain pending. Earlier full-suite counts are historical evidence
for their recorded source bytes; the final prior App run's command/exit gap
remains disclosed. No artifact, installed, native, canonical or publication gate
is accepted. All 8,723 obligations and the 18-or-more workflow floor remain.

## 2026-11-09 — Kerning Proof Workbench source candidate

Add the retained App workbench, real direct-import demo and thin lazy Scriptmix
route over one captured borrowed font. Repair the reproduced R2 temporal gap by
invalidating proof before the first fallible read and preserving only the pending
selected occurrence. Keep the original selection identity loop, guarded writer,
readback and callback semantics. No R1 inspect repair or native defect is claimed.

The initial real-backend workflow checks recorded four temporal failures and
two passing sequential-empty cases; the absent window also failed as expected.
The repaired full App suite passes 10,158 tests with no failure or skip (100
existing warnings). The isolated Scriptmix finite cohort passes 58 tests with
one inherited optional-source skip; unchanged Fontport regressions pass 80.
Whole-module combined statement/branch coverage is 235/236 for kerning,
249/249 for Sequence, 146/152 for the new window and 9/9 for each entry script,
with zero excluded statements. Pinned Ruff checks pass. Full Scriptmix execution
and independent source review remain separate pending gates.
The menu count is now 195 additional records / 264 tools; frozen original
provenance remains unchanged. No artifact, installed, native, canonical or
publication acceptance follows. All 8,723 obligations and the 18-or-more workflow
floor remain required.

## 2026-11-09 — A0/I1 paired ordinary milestone and A1 preflight

The finite A0/I1 qualification is accepted: the fresh wheel and rebuilt-sdist
prefixes each passed 1,508 App/auxiliary tests with zero skips, plus 51 Scriptmix
checks and one exact inherited conditional skip. Genuine artifacts and complete
private source archives are accepted for that payload. The full source results
remain 10,089 App passes with no failure, error or skip and 4,562 isolated
Scriptmix passes with six inherited conditional skips; these were not rerun for
the preflight. Containing commits, truthful immutable links, native workflows,
canonical promotion and publication remain open.

Prepared a contract-only proposal for the next A1 Kerning Proof Workbench,
reusing the integrated editor, exact borrowed-font route and retained window
ownership. Source inspection identified possible stale-preview boundaries for
owned reproduction; no runtime defect, shared repair or upstream defect is
claimed. No new product implementation or test acceptance follows from the
preflight. Four source compositions exist; fourteen remain, with all 8,723
obligations and the 18-or-more workflow floor unchanged.

## 2026-11-09 — Complete source consumer verification

Verify the audit and ownership repair with the complete isolated Scriptmix
source suite: 4,562 passed and six inherited skips. Original source and Git
endpoints remain unchanged, and generated catalogue files stay in the test clone.
Runtime, tests and dependencies are unchanged by the subsequent progress notes;
App's 10,089-test result and coverage remain applicable to those exact bytes.
Independent review, genuine immutable provenance, fresh ordinary artifacts and
native qualification remain separate gates.

## 2026-11-09 — Retained constructor cleanup

Route nested FontUI construction through the existing owner-preserving factory.
Require child cleanup acknowledgement before completing a parent, and retain
nested and outer dialog owners separately in all four inspection workflows.
Add real constructor-failure, interruption and cleanup-retry regressions and a
working FontWorld audit demo. Source fixture qualification passes; independent review remains pending.
This change has no new installed or native acceptance.

## 2026-11-09 — Tabular Width Audit source candidate

Add a retained read-only FontWorld chooser linked to the existing exact tabular
comparison and renderer. Preserve duplicate font identities, browser row order,
fractional advances and borrowed-font ownership. Clear stale reports on refresh
and read errors; acknowledge FontBrowser, Browser and Preview cleanup separately
and retain retry diagnostics. Add callback, real FontWorld, closure and failure
regressions. Shared nested-constructor recovery and a required working App demo
remain open; no new ordinary installation or native acceptance is claimed.

## 2026-11-08 — Issue 234 lifecycle origin fixture qualification

The lifecycle regression now admits installed modules using both the
controller-approved origin-record path and its SHA. Original behavior
assertions and test identities remain intact. Current-source qualification
passes all 10,014 tests with no failure, error or skip. Retained complete
line/branch reports qualify the exact eleven unchanged production modules
above 80%; this fixture-only run does not create new coverage measurements.

The installed positive is a CONTROL with the candidate test, not a new
ordinary artifact result. Earlier ordinary failures remain failed; the new
wheel/rebuilt-sdist pair still requires qualification. Native workflows,
saved/reopened whole-font history, owner installation, canonical promotion,
publication and full 8,723-obligation/18-or-more-workflow acceptance remain
open. This test-fixture error establishes no native upstream defect.

## 2026-11-07 — Font UI inspection source candidate

Add three read-only linked inspection compositions and their lazy menu routes:
glyph metrics, anchors/components and Unicode/glyph order. Reuse existing
Browser/Preview, Sequence and exact selected-width comparison APIs. Add optional
selection/update callbacks with host-refresh/error clearing and a detached
in-memory three-window demo. Preserve borrowed
fonts, historical menu payloads and recovery owners; native acceptance and the
known partial base-close repair remain open.

## 2026-11-07 — Issue 234 failed Tool paint invalidation

Clear inspection interaction after missing, failed or unsuccessful Tool paint
capture/computation through the existing frozen-data contract. Keep inherited
Reporter capture/rendering and contain legacy marks(None)/diagnostic errors.

## 2026-11-07 — Issue 234 keyed Tool capture

Append optional source identity to frozen Plugmix snapshots without changing
existing content equality/hash or positional construction. Thread the Tool's
component opt-in through ToolContext and its existing Reporter painter, passing
the actual resolved glyph and owner master. Missing optional identity remains
None and malformed reads use existing capture error containment. No writer,
reserved master implementation, native watcher or second Qt binding is added.

## 2026-11-10 — verified integration-round guidance

- Record current-main reconciliation in a new isolated successor, preservation
  of concurrent work and exact reviewed staging, combined repository/graph
  checks, independent merge review, required hooks and actual remote proof.
- Keep solved tasks in cumulative history and unfinished acceptance in the
  future queue. Native, installation, adoption, Issue 123 and private Pages
  boundaries remain unchanged. This entry records documentation only.

## 2026-11-10 — install.vfpy always reinstalls scripts and dependencies

- Every install copies all files from `Scripts/` afresh and replaces any file
  already at the same path. A symlinked script folder is replaced by a real
  folder; the link target is never written. A directory where a script file
  belongs is still refused.
- Required packages are installed on every run. Packages that no package
  index carries (the fontlab-* packages, pythonqtside) are installed from
  checkouts beside this one through their own `install.vfpy`, once per run
  and safe against cycles. uv receives every other requirement, so version
  ranges, markers and extras are enforced. Without uv, sibling checkouts are
  still installed and only the remaining missing requirements are reported.
- The installer is byte-identical across all eleven installer repositories.

## 2026-11-10 — Studio apps, integration rounds 1–2 (Issue 242 Phase D T1–T16)

- New `fontui` host layer: `AppShell` (tabbed 80vw × 75vh shell with one
  labelled Undo step per Apply through `AppShell.history`, optional `retain=`
  for deep history), `GlyphTable`, the hint guard, explicit-layer writes, and
  embeddable TMetrics/TGlyph previews (TMetrics reads its target layer).
- New `studios/` packages, each absorbing Scriptmix scripts as tabs with a
  dry-run list before every Apply and stale-snapshot refusals: Kerning Studio,
  Spacing Studio, Anchor Studio, Transform Studio, Align & Nudge, Outline
  Doctor, Interpolation Doctor, Proof Studio (parts 1 and 2), Font Audit,
  Kerning Browser, Kerning Batch, Advance Widths, Anchor Transfer, Vertical
  Metrics & Zones, Mark Attachment, Component Studio, Component Audit and
  Derived Glyphs. Shared helpers: `studios/_contours.py`, `_kerning*.py`,
  `_records.py`. Round 2 adds Layer Manager (T16: duplicate, restore, use as
  master, copy masters, twins, intermediate, cleanup, empty layers, copy
  layers from font, backups), with stale checks keyed on native layer ids,
  and launcher/model tests that satisfy the 80% pre-push coverage gate.
- Every task passed an independent spec and quality review; tests pin the
  sha256 of each absorbed original and skip with a visible reason when
  `FONTLAB_SCRIPTMIX` is unset. Native FontLab Undo/Redo, cross-font history
  and saved-reopen qualification remain open (Phase D T29).
- Round 1 merged with concurrent main (canvas lifecycle and TGlyph
  smooth-selection work): 11,095 passed, 21 skipped; Ruff F821 clean.
- Round 2 merged with concurrent main (installer reinstall, docs rebuild,
  integration-round guidance): 11,226 passed, 31 skipped; Ruff F821 clean;
  the 80% per-module pre-push coverage gate passes.

## 2026-11-09 — Proof Studio part 2 (Issue 242 Phase D T9)

- Proof Studio adds the Real text, Random, Word finder, Waterfall and By master
  tabs. They absorb the seven Random scripts, Real English/Spanish Text, Text
  Filter, Word Finder, Waterfall, Text By Master, Master Text Comparison and
  the Examples Saved Proof Sample. Random and Real text take an optional seed.
- Tab registration now adds any missing tab title once, so generator modules
  that appear later in the same process get their tabs without duplicates.
- The Real text passages moved to `proof/real_text_passages.json` (NOTICE).
- TMetrics gains `read_only=` (refuses metric and kerning writes) and
  `set_view(size, kerning)`; Proof Studio's preview uses both.

## 2026-11-09 — Verify existing canvas construction and order behavior

- Added 37 offline order/layer, timer setup/refusal/retry, inert construction
  and filter-constructor controls. All 203 focused cases pass on unchanged
  production; all 166 original cases and helpers remain exact prefixes.
  Read-only Ruff 0.14.10 F821 passes.
- Independent SPEC/QUALITY review found no source defect in these selected
  contracts. No production guard, dependency or version metadata changed.
- The prior 10,102-test complete run and d82 ordinary installation retain
  their dated scope. Current integrated normal, exact-source CI and delivery
  gates remain pending; no new package artifact or installation is claimed.
- Native constructor dispatch, partial allocation/connection side effects,
  arbitrary nested lifecycle behavior, other native ID reads, installed Qt5
  wrapper lifetime, complete-font/history, saved reopen and owner installation
  remain unqualified. Offline adapter cases do not establish those outcomes.

---
this_file: CHANGELOG.md
---

## 2026-11-09 — Retain ownership across canvas attachment calls

- Successful painter/filter attachment keeps its result local until existing
  timer, reporter, entry, watch and mouse-demand ownership is rechecked. An
  obsolete successful result is cleaned up through its captured old resource.
- Later ID reads cannot publish a stale canvas entry or watch after teardown.
  Removed tokens are ignored during retained multiple-reporter iteration;
  same-timer token/mouse removal and replacement failure caches stay separate.
- Preserved zero/False native handles, False removal results and existing
  cleanup-failure reporting/retention. Cleanup errors and raising/reentrant
  sinks cannot overwrite the replacement watch or its pending repaint.
- Added 55 fake-native cases without changing original tests/helpers. The
  unchanged source produced 23 failures in 33 cases; focused checks pass 166.
  One complete fresh prepared source run passes 10,102 tests with 100 retained
  warnings; whole backend combined coverage is 97.312860%, zero exclusions,
  and read-only Ruff F821 passes.
- Final independent source review, artifacts/ordinary origins, delivery and
  native PythonQt/history/saved-reopen qualification remain separate. These
  cases do not qualify constructor/order-getter reentry or every native ID read.

---
this_file: CHANGELOG.md
---

## 2026-11-09 — Stop obsolete in-flight canvas continuations

- Polling and repaint recheck existing timer/watch ownership after the
  demonstrated native getter, update and error-sink boundaries. Obsolete
  repaint errors cannot suppress a replacement watch's genuine failure.
- Register stops attaching its removed reporter token after immediate polling
  reenters close/register. Current callbacks and completed native updates retain
  their behavior; teardown and native attachment failure policies are unchanged.
- Added 20 fake-native regressions/controls after 13 old-source failures.
  Focused checks pass 111 cases; one complete fresh prepared source run passes
  10,047 tests with 100 retained warnings. Complete backend combined coverage
  is 97.419355%, zero exclusions; read-only Ruff F821 passes.
- Source review, artifacts/ordinary origins, delivery, native PythonQt and
  whole-font/history/saved-reopen acceptance remain separate. Successful
  helper-internal painter/filter installation reentry and later native ID reads
  remain unqualified; no owner installation was performed.

---
this_file: CHANGELOG.md
---

## 2026-11-09 — Retained canvas timer callbacks stay inert after reuse

- Poll and repaint signal callbacks now check their captured timer identity.
  Backend close, last reporter removal and viewport replacement clear ownership
  before teardown; disconnect receives the exact connected callable. Failed
  teardown still retains wrappers and reports under the existing sink policy.
- Old filters detach before timer error reporting, preventing an error sink
  from restarting repaint through a stale filter. Failed-start callbacks remain
  inert after registration retry; current polling and repaint still work.
- Added 47 offline cases without changing prior tests/helpers/classes. Corrected
  old-source behavioral failures precede the fix. Final focused checks pass
  152 tests; the complete unchanged launcher passes 10,027 tests with 100 retained
  warnings. Whole backend statement/branch coverage is 97.4419%, zero exclusions;
  Ruff F821 passes. Source review, ordinary artifacts, delivery, owner installation
  and native FontLab/history/saved-reopen acceptance remain separate.

---
this_file: CHANGELOG.md
---

## 2026-11-09 — Native canvas lifetime regression qualification

- Added nine offline lifetime/error cases for the existing native canvas
  backend: same-ID reuse, real capture/report reset, removal faults, inert old
  paint callbacks after reuse and inert poll/flush/filter callbacks while closed
  after failed teardown, including a failing sink.
- Production and pre-existing test/helper/class ASTs remain unchanged. The
  complete prepared source suite passes 9,980 tests with 100 retained warnings;
  whole backend statement/branch coverage is 97.6077%, with zero exclusions.
  Ruff F821 passes.
- Removed completed TGlyph source review/delivery/ordinary clauses from its
  forward task. Native follow/history/reopen remain open. This candidate adds
  no native, ordinary artifact, owner-installation or delivery qualification.
  Retained timers after backend reuse remain unqualified.

---
this_file: CHANGELOG.md
---

## 2026-11-09 — TGlyph smooth-only selection retention

- Smoothness no longer changes structural point identity. Smooth-only refresh
  and follow retain exact point selection and adjusted zoom/pan; the unchanged
  visual fingerprint still triggers fresh data, readout and canvas updates.
- Added first/last/multiple-selection regressions and structural/editor controls;
  point count/type, open/closed state and distinguishable contour/component-base
  order still invalidate selection, and structural refresh cancels stale edits.
- Source validation: six genuine old-source regression failures, 132 focused
  passes and 9,971 complete-suite passes with 100 retained warnings. Complete
  model statement/branch coverage is 99.19%; Ruff F821 passed.
- Native FontLab, ordinary installation, history and saved-reopen qualification
  remain separate; identical-type/structure reorder detection is unchanged.

## 2026-11-08 — TMetrics echo token and version-floor notes (Issue 241 final review)

- TMetrics now records its echo-suppression token from the state it drew, not
  from a fresh read after `refresh()`, matching `tglyph_edit.py`.
- Recorded in PLAN and TODO: the `fontport>=1.2.0` floor lacks the Issue 241
  Fontport write-back fixes; raise it when Fontport is tagged.

## 2026-11-08 — TMetrics mark rule correction (Issue 241 Task 8, fix round 1)

- Correction to the Task 8 entry below: without GDEF glyph classes, TMetrics
  identifies a mark by the glyph's own nominal width of 0, not by its shaped
  advance. The shaped advance includes kerning, so a base glyph kerned to zero
  advance is not a mark and keeps its kern bar.
- The GDEF lookup also gives no verdict when uharfbuzz lacks
  `get_layout_glyph_class`, instead of failing while placing glyphs.

## 2026-11-08 — TMetrics and TGlyph fixes (Issue 241 Task 8)

- TGlyph pen: the first click places a pending point in the preview only; the
  second click writes a two-point open contour. Escape or a tool switch discards
  the pending point. The pen no longer leaves a one-point contour.
- TGlyph Delete: a cubic curve segment left with one handle becomes a line; a
  quadratic curve keeps its single off-curve point.
- TMetrics: a kerning write to a group pair names the group keys in the status
  line, for example `Kerning public.kern1.A/public.kern2.V (group pair for A V): -50.`
- TMetrics help names the macOS kerning keys: Control+Option or Command+Option
  with Left/Right.
- TMetrics: marks get no kern bar. A glyph is a mark when the shaping font's
  GDEF classes say so, or, without glyph classes, when its shaped advance is
  zero. `PlacedGlyph.mark` and `Cell.mark` carry the verdict.
- Known limits: removed the pen one-point-contour limit; added the Delete
  normalisation rule. Remaining deferred items are in PLAN and TODO with reasons.
- Native FontLab behaviour of these changes is unverified; offline tests only.

## 2026-11-08 — TMetrics and TGlyph windows (Issue 241)

Added two modeless windows to `fontlabapp.fontui`. `show_tmetrics()` shapes
text in a font (HarfBuzz through the new `fontui-shaping` extra, else one glyph
per character), draws metrics and kerning, and writes sidebearings, widths and
pair kerning back as one named undo step each. `show_tglyph()` shows one glyph
on an explicit layer and edits its points: drag, nudge, delete and a pen tool,
one write to the shown layer per gesture. Both follow FontLab edits and
Undo/Redo and skip their own writes. Qt-free shaping, layout, geometry and
edit logic live in `shaping`, `tmetrics_model`, `tglyph_model`, `tglyph_edit`,
`livesync` and `lifecycle`. The README documents keys, the extra and the known
limits. Scriptmix gains Metrics > TMetrics Window and Contours > TGlyph Window.
Live FontLab round-trip is not verified.

## 2026-11-07 — pen migration reconciled with cold packaging

Reconciled the reviewed pen migration with the newer cold-distribution repair.
All five static-shim fixture files, source-distribution include entries and
cold/cache inventory regressions remain intact; the four pen implementation
files are unchanged from the reviewed migration. The combined source passes
9,673 tests with 100 retained warnings through the literal prepared-environment
launcher on arm64 Python 3.11. Explicit editable providers and a verification-only
source-table override bind this isolated worktree; this is not a standalone
unprepared-launcher claim. Genuine combined artifacts and independent review
remain separate gates. Earlier native results refer to their recorded tuple;
this reconciliation adds no native, history, adoption or publication claim.

## 2026-11-07 — bounded native and ordinary-artifact qualification

Bounded owned-font native checks passed for the three migrated outline_path
helpers on H and curved O across Light, Regular and Bold, comparing real
QPainterPath geometry with independent native paths. H polygon area also
checked the migrated selection unsigned_area route. This qualifies these
helpers, not every painting or selection workflow.

Ordinary precommit artifacts have matching source/sdist/wheel/site package
payloads in the normal 19-distribution cohort: App 620, Fontport 38 and Glyport
182 files; 2,011 installed RECORD entries were checked. These dirty-VCS
artifacts are separate from the bounded native runs. The consumer candidates
remain uncommitted; canonical adoption, clean committed artifact requalification
and delivery are not complete. Native notification can restamp 40 unrelated
glyph timestamps; the exact per-run date inventory remains explicit. No
whole-font history safety or general UI/workflow acceptance is claimed.

Launcher follow-up: `./test.sh` now uses `uv run --no-project` with the
explicit editable App test extra and the existing sibling pens/Fontport/Glyport
rules, avoiding the earlier unpublished-registry project solve. A fresh default
`./test.sh -q` reached the full suite: 9,664 passed and six failed (five missing
Fly cases and the existing oversized-line timing case), on Python 3.14 selected
by that unprepared environment. With the documented prepared Fly environment,
explicit arm64 Python 3.11 and fresh external temporary/cache storage, the same
literal invocation produced 9,669 passes and one oversized-line timing failure.
Both failures are retained; the launcher is not claimed standalone-green. No
test oracle changed and no further full rerun was attempted during the active
native batch. Earlier 9,670-pass prepared-suite and coverage results remain
separate dated evidence; serial timing requalification remains pending.

Serial follow-up after the native batch ended: the unchanged literal
`./test.sh -q`, with prepared Fly, arm64 Python 3.11 and another fresh external
temporary/cache pair, passed all 9,670 tests (100 existing warnings, exit 0).
The earlier default and concurrent prepared failures remain separate results;
this pass qualifies the documented prepared-environment launcher, not an
unprepared standalone installation. No timeout, skip or test oracle changed.

## 2026-11-07 — pens moved to fontlab-python-pens (Issue 235)

The three `outline_path` painters (`contours.transform.model`,
`masters.interpolation.model`, `proof.inspectors.views`) keep their names and
signatures and now draw through `fontlab_pens.qt.draw_onoff_contours` into a
`QPainterPathPen`. Contours with no on-curve point stay undrawn, as before.
`contours.selection.model.unsigned_area` uses `fontlab_pens.AreaPen`; its
validation errors are unchanged and the `fontui` RuntimeError is gone.
Offline tests only; native FontLab painting and selection remain unverified.

## 2026-11-07 — cold source-distribution test contract

Include the five existing static-shim fixture files in the source distribution
so documentation and delivered-shim replay checks run. Keep the installed wheel
namespace unchanged. Treat bytecode caches as transient hidden entries while
retaining the required `_legacy` source and every stale-exclusion/reason check.
New owned-copy regressions prove identical complete feature inventory with
absent and genuinely compiled caches, and refusal of missing private source.
Missing shim documentation/type material still fails the original oracles.

The complete source suite passes 9,673 tests with 100 retained warnings. Artifact,
ordinary-origin, unchanged-hook and native acceptance remain separate surfaces;
the README now states the cold extraction and installed-parent verification
contract. No runtime API, captured fixture or dependency declaration changed.

## 2026-11-06 — maintained App documentation site

Moved the complete API map and background-tools guide to `src_docs/md/guides/` and updated their active README, packaging and test consumers. Added six focused documentation pages, a complete runtime reference, exact component licence downloads and local search in light fltheme26. ProperDocs/MaterialX use an exact hash lock. Every main push builds and independently qualifies immutable generated output; private Pages operations remain held. No native acceptance or runtime behavior changes follow from this site.

## 2026-11-06 — owned submenu removal disconnects child actions

Removing an owned submenu now removes its owned action tokens before Qt deletes
their parent. This prevents a later `close()` from disconnecting deleted actions,
including removal requested by a child action callback. Other menus remain intact.

The reconciled reporter-menu source passes 9,670 offline tests. Complete branch
and statement coverage is 93.04% for boot, 97.73% for reporter menus, 98.36% for
owned menus and 100% for the Demo script, with no exclusions. The new regressions
cover actual standalone Qt deferred deletion and PythonQt-shaped dispatch doubles;
Hide All save failures retain persisted state and resynchronise checkmarks.
Native FontLab placement, dispatch and cleanup remain unverified.

## 2026-11-06 — Plugmix reporters move to View > Reporters

`fontlabapp.plugmix.menu.install` now appends a View > Reporters submenu instead
of flat `Plugmix: Show …` View entries. Entries use the reporter title without a
leading `Show `; a separator and `Hide All` (disables every enabled reporter and
resyncs checkmarks) end the submenu; entries sort by displayed label. Boot now
installs reporters after the other kinds, so the submenu stays last in View
(after `Plugmix: Zoom to Selection`). `OwnedMenus.add_menu`/`menu` add owned
submenus, and `add_action` accepts a QMenu target. Offline: 518 focused tests
passed; Ruff F821 clean. Native FontLab menu placement is unverified.

## 2026-11-05 — independently approved documentation applied

[Task 2 final review](../verification/issue-230/task-2-fix2-review.md) records
SPEC PASS / QUALITY APPROVED. The [78-file application receipt](../verification/issue-230/task-2-apply.json)
includes this repository's six guides and preserves all 21 repository heads,
branches, indexes and non-selected diffs. This is applied documentation evidence,
not a new product test, installed artifact, native result or publication.

The complete earlier handoff/history below retains its proposal-stage statements
and dated source pins. Later review, application and delivery status belong in the
[live workspace ledger](../verification/issue-230/progress.md). Original future,
native, artifact and preservation contracts remain binding.

## 2026-11-05 — documentation reconciliation proposal

Prepared repository-specific organization, test and MVP/delivery guidance from current source/test configuration and retained Issue 207–211 evidence. Distinguished current canonical layout from qualified candidates, future plugin ownership and unfinished native/artifact gates. Preserved all prior work and changelog evidence; no runtime completion, installation or publication is claimed. Completed historical task rows were removed from the active checklist and consolidated below from existing local CHANGELOG/WORK receipts. Unfinished native, artifact and integration checks remain open.

## Retained scoped completion receipts — corrected evidence map

These are dated results at the stated source/version and acceptance surface. They do not establish current integrated, installed, native or published acceptance. Full receipts and hashes are indexed in the workspace Issue 230 task-2 manifest. Canonical-preimage line ranges below refer to the unchanged historical documents, before these new entries.

- Issue205 mapping tool and all382 reviewed modules/aliases documented.
  Historical receipt: CHANGELOG.md:274–289.

- Issue205 all10 per-batch whole gates pass;final7750;all10 reruns byte-identical over887 files.
  Historical receipt: WORK.md:314–353.

- Issue205 all382 identities;77 cold models;clean root;10 reruns;wheel origins.
  Historical receipt: WORK.md:340–359.

- Issue205 layout/migration/provenance and ten-batch evidence documented.
  Historical receipt: CHANGELOG.md:274–289.

- Issue205 ownership reversal:11 implementations and6 factory ASTs preserved;App7738/Fontport4601+1skip pass.
  Historical receipt: WORK.md:365–390.

- Issue205 optional App edge;Fontport native drivers/backend unchanged;isolated imports pass without App.
  Historical receipt: WORK.md:365–390.

- Issue205 migration/boundary contracts and ownership documentation updated.
  Historical receipt: CHANGELOG.md:289–308.

- Issue205 App7738/Fontport4601+1skip;isolated Fontport imports without App pass.
  Historical receipt: WORK.md:384–390.

- 04eb3bc isolated two-tool stage:867 full source tests after two import sorts;focused77;Ruff/diff pass.
  Historical receipt: WORK.md:3989–4016.

- Exact04eb3bc five-module source/installed combination:App867;Scriptmix787+2optional skips;every whole-module80% gate passes;98.26714801444044 aggregate. Earlier source-only RED retained.
  Historical receipt: WORK.md:3964–3987; WORK.md:4018–4026.

- Same isolated two-tool wheel:97runtime payload parity;867 per wheel/sdist;4 native drivers68 checks;prior68=552 workflows/196 preservation/Close68;5 modules pass. Release/R053 remains separate.
  Historical receipt: WORK.md:4018–4036.

- Issue122M1 source change:select_glyphs/master_switcher no longer call UpdateAll. Missing p2_app.py native receipt remains open.
  Historical receipt: CHANGELOG.md:526–542.

## 2026-11-05 — planning chronology reconciliation

Issue205 ten-batch import/resource/provenance relocation and No commits are historical actions, not live commands. WORK314–390 binds the passing migration/ownership receipt. Preserve lazy domain/model identities and current App/Fontport ownership. Existing route-A zone source supersedes the old serializer-first implementation instruction; serializer ABI acceptance stays separate. The04eb3bc source/native/coverage closure does not close release/R053. Historical passing results retain their dated source and acceptance scope in the entries above and original history below. This documentation change creates no new runtime acceptance.

---
this_file: CHANGELOG.md
---

## 1.2.28 (2026-11-16)

- Move the `fontlab_plugmix` package from fontlab-python-plugmix (source commit
  ba4a45a) to `fontlabapp.plugmix`, with all five plugin kinds and unchanged
  module names. Its App imports use domain paths (`fontlabapp.qt.safe`,
  `fontlabapp.qt.menus`, `fontlabapp.masters.layers.writer`, …). No
  `fontlab_plugmix` shim is kept.
- Third-party plugins use the `fontlabapp.plugmix` entry-point group. The
  preference file stays `fontlab-plugmix.json`.
- Move the plugmix tests to `tests/plugmix/test_plugmix_*.py` with a scoped
  `conftest.py`; plugmix's own runner and coverage-script tests are dropped.
- Add Plugmix provenance to `NOTICE` and a README Plugmix section.
  `docs/api-map.md` lists 618 modules (domain `plugmix` included).
- Drop Plugmix's legacy preference names: the `nodes_outside_paths` rename map
  is gone. A preference file without `params` (the pre-filter format with
  only `enabled`) is refused and reported as invalid instead of loaded; the
  next save replaces it, so its old enabled list and any unknown keys are lost.
- Reporters paint the layer the text slot shows (`info.symbol.layerName`,
  else the current master), as the palette's `active_glyph` already did.
  Before, every reporter painted current-master data for a slot that showed
  another layer. Metrics, components, kerning groups and requested glyphs
  come from the master that owns the shown layer
  (`components.decompose.owner_master`). When that is not the current master,
  zones are empty and the italic slant is still the current master's: both
  need a paint-unsafe master switch to read.
- Reporter snapshots gain `identity` (name, Unicodes, raw mark, mark RGB,
  export flag; new `fontlabapp.glyphs.identity`) and `view` with
  `px_per_unit` (new `fontlabapp.qt.painting.view`).
- Reporters can opt in to more data:
  - `needs_components`: decomposed components, nested up to 8 levels (new
    `fontlabapp.components.decompose`);
  - `needs_background`: the mask layer's contours (new
    `fontlabapp.glyphs.background`);
  - `needs_masters`: each master's outline with a `compatible` flag (new
    `fontlabapp.masters.interpolation.outlines`);
  - `needs_kerning`: the glyph's kerning classes and members (new
    `fontlabapp.kerning.groups`);
  - `requested_glyphs(identity, kerning_groups=None)`: the own contours of up
    to 32 other glyphs (new `fontlabapp.glyphs.others`);
  - `needs_neighbours`: the same-line previous and next glyph with displayed
    kerning;
  - `needs_mouse`: the cursor in glyph units; the native backend watches the
    canvas and repaints only while such a reporter is enabled.
- Identity, components, master outlines and requested glyphs are read once
  per glyph revision and shared by all reporters. The background and kerning
  groups are read on every paint. A failed read leaves the field at its
  default and goes to the error sink once. An error raised by a reporter's own
  code is also reported once per reporter and message until Plugmix closes.
- Add 14 reporters: Blindfold, Show Label Color, Show Glyphs In Label Color,
  Show Character, Rekha Viewer, Show Export Status, Show Background, Color
  Toner, Show Global Glyph, Show Siblings, Show Kerning Group Reference, Kern
  Indicator, Show Interpolation and Stem Thickness. Add the `geometry` helpers
  `flatten`, `fill_points` (one odd-even polygon, counters open) and `shear`,
  and `reporter.fill_mark`. Background-layer components are not drawn.
- View menu labels no longer double the prefix ("Plugmix: Show Background",
  not "Plugmix: Show Show Background").
- Native behaviour is unverified: mouse delivery to the viewport filter, the
  odd-even fill in FontLab's painter, the kerning side convention, and whether
  other-master edits move a glyph's `lastModified` (master outlines may lag
  until it moves). Coverage is offline only.

## 1.2.28 (2026-11-16)

- Add 90 GUI demo scripts, `Scripts/<Category>/<Title> Demo.py`, in 15 categories
  (Anchors, Components, Contours, Features, Font Editors, Font Info, Guides,
  Kerning, Masters, Metrics, Names, Proof, Reports, Utilities, Widgets). Each demo imports `fontlabapp` directly and
  lazily, never `fly.ap`, and checks for an open font first when it needs one.
  `install.vfpy` copies them into the Scripts menu; the `Demo.py` suffix keeps
  them apart from Scriptmix scripts when both are installed.
- Safety model: demos write nothing by themselves (no font, selection, history,
  preference, Output or clipboard). The only writes are user-started: Copy
  buttons of Glyph Map and Common Glyphs write the clipboard; Proof Tabs,
  Kerning Proofs and Text Filter open a text tab after a confirmation or a
  ticked box (the tab code snapshots and restores shape active flags);
  Image Viewer's Print may write a PDF where the user chooses; Text Holder,
  Text Filter and Image Viewer keep files in fixed
  `fontlabapp-demos/<demo>` folders under the system temp directory.
- Tests: `tests/test_demo_scripts.py` is a structural gate (layout, header,
  imports, `fontlabapp` names by `ast`) over every demo; ten area modules
  `tests/test_demo_scripts_*.py` run the demos offline under stubbed natives
  (`tests/_demo_support.py`, `tests/_widget_qt.py`).
- Packaging and lint: the sdist `only-include` now contains `Scripts`; the Ruff
  F821 command covers `Scripts` too. README gains a "Demo scripts" section.
- Native FontLab acceptance of the demos is pending.
- Glyph demos in `Scripts/Names` now keep going when one panel refuses to open
  and report which one failed; the sample V contour is clockwise like the A.
- Add `tests/test_demo_scripts_coverage.py`: every `fontlabapp.<domain>.<feature>`
  module or package on disk must be named by some `Scripts/` demo, found by `ast` in
  an import or string literal. Only `_legacy` and `__pycache__`
  are excluded by name; the feature exclusion dict is empty and checked against the disk.
- Core Utilities Demo now also names and summarises `fontlabapp.core.legacy` and
  `shimgen`, and spells out every `fontlabapp.core.*` module it imports (`history`,
  `completion`, `native_tabs` were the other uncovered features).
- README lists the 90 demos by category; AGENTS.md says Scriptmix and Fly callers use
  `fly.ap` while App's own demos import `fontlabapp` directly.

- Four demos now use features the others only name. Shim Generator
  (`Scripts/Utilities`) replays an embedded sample capture through
  `core.shimgen` and shows the host tree and the generated stub, writing
  nothing. Native Tabs (`Scripts/Proof`) reads `core.native_tabs` canvases and
  the active block. History Preflight (`Scripts/Masters`) runs
  `core.history.glyphs.scan_auto_facts` and
  `core.history.masters.require_font_window` read-only. Owned Lifetime
  (`Scripts/Widgets`) creates a widget, a dock panel and a dialog through the
  `fontlabapp.ui` factories and installs `core.completion` on a demo-owned
  dialog; it adds one panel to the main window (it may float) and removes it. Tests
  are in `tests/test_demo_scripts_core_demos.py`.
- The stale-window probe of Text Holder and Text Filter Demos treats a
  `ValueError` as a destroyed widget only when its text says "destroyed", like
  `show_script_dialog`; any other `ValueError` keeps the window registered.
- Demo review fixes. Glyph Names Report keeps its other sections when the
  scan fails. Font Browser, and now the other six Font Editors demos that
  import Fontport or ufoLib2 (Batch Panel, Font Info Editor, FontParts Kerning
  Editor, Glyph Browser, Glyph Sequence, Groups Editor, Transform Editor),
  blame the `fontport` extra only for a missing `fontlab_fontport` or
  `ufoLib2` and name any other import failure as it is. The Revisions panel
  import moved inside its `try`. The Proof Tabs and Kerning Proofs questions,
  and now Extrema Proof's, say that tab creation restores every shape's
  active flag. Native Tabs reports "Glyph canvases found: N (some builds list
  only the active one)". History Preflight warns that a large font makes the
  scan slow. A `src/` docstring in `glyphs/common/ui.py` now says the
  clipboard is written only by the literal-copy action.
- Test gates. `tests/test_demo_scripts.py` resolves every `fontlabapp.<name>`
  path spelled in a non-docstring string of a demo (whole values, f-strings and
  prose), as it already did for imports; Core Utilities spells its root shims
  as full dotted names. `defined_names` ignores comprehension targets.
- README: a "Named but not run, and why" paragraph explains why the writer
  panels, `core.hotkey`, `core.legacy` and the `fontlabapp.ui.*` subpackages
  are only named or summarised.
- `fontlabapp.qt.dialogs.create_message_box` takes a keyword-only `detail`. A
  non-empty value becomes the Show Details text; if setting it fails, the box is
  deleted and the error re-raised. The 56 demos that set detail text by hand
  now pass `detail=`; `notify` signatures and demo behaviour are unchanged.
- Add `fontlabapp.qt.widgets.release_owned(scope, owned, problems, closers=())`.
  It finishes a signal scope, closes the closers and then the owned window,
  and stops at the first refusal. It records Qt's `RuntimeError`s and returns
  whether everything was released. The nine Font Editors demos use it in
  `Demo.release` and keep their window and message when Qt refuses. Demos with
  other release policies keep their own code. API map updated.

## 1.2.28 (2026-11-16)

- Integrate reviewed feature 0db16ed with committed main 2e6999d in an isolated
  successor; preserve installer/release source and both documentation histories.
- Refresh current handoffs; keep canonical owner edits and native acceptance separate.
- Merge the reviewed Issue 201/204 branch into main 1.2.4 (Issue 205 layout).
  Fontport editors keep their Apache-2.0 SPDX headers, the `require_fontport`
  guard and relative imports. The node duplicator recovery helpers live at
  `contours/nodes/duplicator/_finish.py`; the facades and their tests use domain
  paths; `docs/api-map.md` and `generated/fontlabapp_shim/` are regenerated.
  The package stays Apache-2.0 with the scoped fontui and native-example notices.

## 1.2.28 (2026-11-16)

- Move the external native UI example from Remopy with unchanged implementation,
  original Fontlab Ltd proprietary terms, usage guidance and host-free ownership/error checks.

## 1.2.28 (2026-11-16)

- Merge the reviewed API facades with the accepted FontParts editors, retaining
  both histories and all existing editor factories.
- Refresh the complete 422-module API map, including the 11 returned editor
  modules, current public names and source purposes.
- License all 23 fontui Python sources under Apache-2.0; retain source text,
  package copyright and unrelated third-party licences/notices.
- Use genuine Git-derived test versions and document the host-free fallback.
- Add meaningful shared-control tests; full suite passes 7,864 tests and all
  40 complete changed modules exceed the unchanged 80% coverage floor.

## 1.2.28 (2026-11-16)

- `create_panel`: a panel docked while FontLab's MainWindow is hidden (for example
  by a title-bar double-click) floats again on the next event-loop pass instead of
  vanishing into the hidden window. Verified in FontLab 9.
- `EditorPainters._attach_all`: a failing error sink no longer escapes the timer slot.
- DEPENDENCIES: `uv lock`/`uv run` need the sibling Fontport checkout; the extra cycle is recorded.

## 1.2.28 (2026-11-16)

- Move the Qt editors `font_info_editor`, `groups_editor`, `kerning_editor`,
  `transform_editor`, `batch_panel` and `glyph_sequence`, with their modules
  (`fontinfo`, `groups`, `groups_view`, `kerning`, `kerning_view`, `transform`,
  `transform_view`, `batch`, `batch_worker`, `sequence`), back from
  `fontlab_fontport.ui` into `fontlabapp.fontui`. Fontport has no UI.
- Remove the tombstone machinery in `fontlabapp/fontui/__init__.py`
  (`MOVED`, `MOVED_HOME`, the module `__getattr__` and the meta-path finder).
  The six factories are public again and part of `__all__`.
- Import `fontlab_fontport` lazily, only in the editor modules. A new
  `fontlabapp.fontui._load` turns a missing Fontport into an `ImportError` that
  names `fontlab-fontlabapp[fontport]`. Add that optional extra.
- Move the editor tests, the Qt fake `tests/_cov_qt.py` and
  `examples/font_transform.py` here. The tests skip when Fontport is absent.
  `test_package_boundaries.py` now allows Fontport in those editor modules only.
- Move the generated `fontlabapp_shim` to `generated/fontlabapp_shim` and retarget
  `shimgen.DEST`; Echopy no longer hosts it.
- Evidence: see the issue 201 task 2 report in the workspace. Native acceptance
  of the editors is unchanged and still pending.

## 1.2.28 (2026-11-16)

- Add a source-based domain and public-name map for every App Python module.
- Add lazy facades for object access, UI, menus, actions, shortcuts, signals and
  Qt helpers; preserve the existing modules and native loading behavior.
- Put the action facade at `fontlabapp.ui.actions` to preserve the legacy
  `fontlabapp.actions` live attribute. Name the Qt helper facade
  `fontlabapp.qtsafe_api` to avoid a case-only collision with `Qt` on macOS.
- Test cold imports, re-export identity, top-level lookup preservation and
  package boundaries.
- Let unknown top-level names fall through to submodule imports outside
  FontLab, while explicit native names retain their host-required errors.
- Keep the API map checked against every source module and expose accurate
  facade discovery through `dir()`.

## 1.2.4 — 2026-11-03

- Case Coverage stores its report as report_result: QDialog.result is a native
  slot PythonQt refuses to overwrite, so the dialog failed to open. Reference
  Image Viewer (part 3) wraps menu shortcuts in QKeySequence; PythonQt's
  setShortcut accepts no str. Both found by running the risk-flagged scripts in
  a QSettings/dialog/process sandbox; tests model both PythonQt behaviours.

## 1.2.3 — 2026-11-03

- Case Coverage and Master Text Comparison proofs (not run by the sweep: they
  write QSettings) shared the fresh-tab defect: active_model now falls back to
  the active canvas's first block, so new tabs are found and verified. A new
  core.native_tabs.canvases() survives FontLab 9.0.9804's broken
  flWorkspace.canvases() binding (TypeError) by using the active canvas, which
  keeps new-tab fences sound. Native probe: fresh() + verify() deliver exact
  A/B content into a new tab.
- Extrema test fake makes glyphs write-only, so the old flPackage.glyphs read fails.

## 1.2.2 — 2026-11-03

- Editable Glyph Tree: read QItemSelectionModel.selection through
  qt.properties.value; FontLab's PythonQt exposes it as a property value, so
  calling it raised TypeError on open (examples native sweep).

## 1.2.1 — 2026-11-03

- Fix four native defects found by the scratch-font script sweep (FontLab 9.0.9804):
  named/text proof tabs read the fresh tab from the active canvas (a new tab has no
  active text block), extrema scans glyphs via fgPackage order + findName (flPackage
  has no glyph list), perpendicular guides fence the legacy font by saved path
  (legacy Font has no id), mark-colour selection reads flWorkspace.currentPackage
  (no activePackage). Each test double now models the probed native shape.

## 1.2.0 — 2026-11-03

- Normalize rewritten imports with a retained stdlib formatter: preserve scopes,
  aliases, comments and module order; merge adjacent imports and wrap at 88 columns.
  The restructure tool now emits the same idiomatic imports. Source/test E702
  findings are zero; import-line E501 findings are zero. AST/token checks verify
  all 453 formatted files; full suite: 7861 passed, 100 warnings.
- Import moved models as normal modules with canonical names and metadata.
  The six colliding domain packages lazily forward model reads, writes and
  deletions, preserving monkeypatch/mock undo, child packages, pickle and reload.
- Resolve real root subpackages before native API fallback, including host-free
  `from fontlabapp import core`. Updated examples and migration guidance.

- Added 90 tests using existing owned FontLab doubles and offscreen PySide6
  adapters. Assertions cover native calls, history, widget state, emitted
  values, complete source snapshots, painted geometry and stale-action refusals.
- All 41 executable modules in the coverage failure list now exceed 80%
  combined statement/branch coverage. All 410 executable modules in the supplied
  changed-file inventory pass; final suite: 7849 passed, 100 warnings.
- The workspace coverage gate scores code-free files at 100%; coverage passes
  without added exclusions or reduced thresholds. Per-domain results are in WORK.md.

### Domain package layout

- Moved all 382 reviewed modules into 14 domain packages; kept root public
  exports in place. Moved the two packaged proof-text resources.
- Added lazy old-name import aliases, including application/hotkey/utils and
  their children. Six colliding packages forward model attributes while
  retaining their package identity, preserving legacy patches and fly.ap callers.
- Added the deterministic stdlib-only ten-batch migration tool and complete
  alias, forwarding, package-laziness and host-free-model regression checks.
- Updated source/test imports, source-inspection paths, shim output, provenance
  destinations and documentation. Historical migration hashes are unchanged.
- Vanilla's module is importable; VanillaSession still raises its migration error.
- Per-batch/full verification and native/external-suite limits are in WORK.md.

### FontLab UI ownership

- Moved the ten FontParts editor modules and active-font feature helpers from
  Fontport to `fontlabapp.fontui`, with six lazy factories and their regressions.
- Restored `fontlabapp.core.scripting` feature helpers; the shipped Fontport feature
  path forwards lazily. Old Fontport UI imports raise precise migration errors.
- Removed App from Fontport base requirements; added Fontport's optional `fontlab`
  extra and App's optional `fontport` extra. AST tests enforce the allowed imports.
- Updated ownership, dependencies, examples and migration documentation.
- Verification and sandbox move limitation are recorded in WORK.md.

## 2026-11-03 — Glyph window and selection fixes from FontLab 9

- Glyph windows: FontLab 9 exposes `widgetViewport` only as a named child, not an
  attribute, so drawing tools such as Reports > Duplicate Anchor Rings failed. The child
  is now found by objectName; checked live on FontLab 9.0.
- Font-window selection fence: FontLab 9's legacy `FL.fl.font` has no `id`, so every
  fenced selection (Scale With Stem Compensation, Copy Layers From Font and five App
  captures) refused. Without `id`, the carrier now matches when the current package has the
  expected fgId and a saved path equal to `FL.fl.font.file_name`; unsaved fonts still refuse.

## 2026-11-03 — fixes from runs inside FontLab 9

- Filter Table dialog: the date editors were stored as `lower`/`upper`, which PythonQt
  refuses to overwrite (QWidget slots), so Models > Glyph Sorting and Filtering with
  Dates crashed. Renamed to `date_from`/`date_to`; a test now fails on any control
  that shadows a QDialog member.

## 2026-11-03 — installer options, licence and cleanup

- `install.vfpy` reads optional `[tool.fontlab-install]` keys: `name` (the distribution
  record), `packages` (`[]` installs scripts only) and `dependencies` (what FontLab needs,
  instead of `project.dependencies`). Symlinks inside `Scripts/` are not copied.
- Relicensed under Apache-2.0 by the copyright owner (previously BSD-3-Clause, with code adapted from Glyport under MIT). `LICENSE` now
  holds the Apache License 2.0 text; `LICENSE-APACHE-2.0` is gone. Third-party code keeps its MIT and
  BSD-3-Clause notices in `NOTICE` (mergedeep, Simon Cozens, LukeProwse, Jens Kutilek,
  Riverbank/Nokia PyQt examples), so the expression is `Apache-2.0 AND MIT AND BSD-3-Clause`.
- Removed the `WORK-ISSUE105.md` working notes (kept in Git history).

## 2026-11-03 — install.vfpy fixes from runs inside FontLab 9

Verified by installing all nine packages inside FontLab 9 (Python 3.11.6, arm64).
- Dependencies with console scripts (glyphsLib, fontTools) failed: uv writes them to
  `site-packages/../../../bin`, which resolves through the venv link to the FontLab
  folder. `bin`, `share` and `include` there now link back into `.venv`.
- A failed install appends a `"failed"` record with the traceback and uv's output to
  `install.log`; List/Uninstall ignore failed records.
- Package records include `WHEEL`, so `uv pip check` accepts them.
- Scripts are copied file by file into FontLab's `Scripts` folder, from a package's
  `Scripts/` folder (exact case) and from folders listed in `[tool.fontlab-install] scripts`.
  Folders shared by several packages merge, e.g. two packages' `Scripts/Kerning`. The
  installer refuses to overwrite a file another package or the user put there; uninstall
  removes only its own files, their `.pyc`, and folders left empty. An older install's
  folder link (`Scripts/Aidus Code`) is replaced by copied files.
- `*.vfpyc` (FontLab's compiled `install.vfpy`) is ignored by Git.

## 2026-11-03 — install.vfpy creates FontLab's venv

FontLab's `python/3.11/site-packages` is now always a real folder; packages are
symlinked into it, so no `.pth` processing is needed. `install.vfpy` creates `.venv` with
uv from FontLab's exact Python version and processor type, and links the venv's
site-packages to FontLab's folder, so `uv pip install --python .venv/bin/python` installs
into FontLab. An older layout (FontLab's folder linked into `.venv`) is migrated.

## 2026-11-03 — reverse-domain extension id and install.log

`[tool.fontlab-install] id = "com.fontlab.fontlabapp"` names this extension. `install.vfpy` keeps
`Extensions/com.fontlab.fontlabapp/install.log` (JSON Lines; the last line lists every installed file),
puts copied code in `Extensions/com.fontlab.fontlabapp/lib/`, and adds Scripts > Extensions >
List Extensions and Uninstall com.fontlab.fontlabapp.

## 2026-11-03 — install.vfpy without uv

`install.vfpy` now needs only FontLab's Python. It asks FontLab for its data folder
(`flPreferences().dataPathDefault`), links a Git checkout or copies a plain folder into
`Extensions/`, and writes a `.pth` plus `.dist-info` into `python/3.11/site-packages`.
uv is used only to add missing dependencies. It never replaces folders it does not own.

## 2026-11-03 — release scripts

Added `build.sh` (uv build into dist/), `publish.sh` (`uv publish`; refuses a dirty
tree or an untagged HEAD) and `install.vfpy` (editable install into FontLab's venv
from inside FontLab). Version stays hatch-vcs from `vX.Y.Z` tags.

<!-- workspace-handoff:2026-11-03 -->

## 2026-11-03 — documentation handoff for November 2–3

Latest accepted feature 29e837d delivers shared priority/retryable ownership; unfinished AB adds shared launcher/completion/caller recovery.

Latest complete AB suite had39 failures before later fixes;84 targeted checks pass. Full current gates, artifacts and promotion remain pending.

Observed canonical checkout: `main` at `73011d1ee6ea`. No source integration is performed by this update.

Updated the requested AGENTS/TODO/PLAN/CHANGELOG/README documentation and
recorded the paused state. Existing project text, examples and history remain;
no runtime source, installation, native session, branch/ref, release or site was
changed by this documentation maintenance. Source/archive/ordinary/native and
promotion acceptance remain separate claims. Detailed workspace evidence is
recorded in the root CHANGELOG and retained verification reports.
<!-- /workspace-handoff -->

## Dialog priority and retryable cleanup candidate — 2026-11-03

- Request TypeRig-style priority in Common Glyphs, floating docks and plugin tools.
- Preserve refused Close, retryable owned cleanup, exact signal records and
  parent-fallback destruction recovery. Expose both factory/setup cleanup errors
  and the exact owner when cleanup cannot finish.
- Add independent real-Qt and failure-injection regressions plus six executable
  window-recovery examples. Full ordinary/native/canonical acceptance is separate.

## Original Node Duplicator boundary repair — 2026-11-02

The retained literal current/all/handles engine now follows the current queue
and history policies: read/disclose queued ids once without clearing/refusal;
use the real shared history-scope guard before staging and direct publication;
verify pre-captured layer/shape metadata after the write. Owned failure cleanup,
stamping and notification obey the caller deadline and retain exact recovery
handles/history-notification status. Expired cleanup never claims rollback.
Skipped targets receive captured glyph/layer labels. The public
node_duplicator_native.duplicate_selected_nodes name is absent from old rescued
adapters, preventing new menu actions from silently using stale safety behavior.

First11independent regressions:10fail/1pass before repair. Focused52pass includes
real offscreen Qt parenting/priority/Close/reopen and complete partial-failure
controls. Initial unchanged normal7485pass/zero skips,5changed modules89.91–100%.
Final exact-source normal and genuine matching artifacts follow root review.
One inherited test's obsolete blanket queue-refusal case is replaced by stronger
3profile read-once/disclosure checks; its stale-history refusal stays intact.
Old/rejected test preimages and all source/command evidence remain under the
external original-workflows-20261102 stage. Standalone Qt is not FontLab native
acceptance. D30live access/safety and all four-font/history/reopen gates remain.

## Private issue123 integration fix1 — standalone Qt tests, 2026-10-23

- Add real Qt behavioral tests for the held Italic Angle panel/gauge and shared
  Names shell: controls, snapshot refusals, paint geometry/pixels, palette,
  selection, error containment and owned completion/destruction.
- Preserve every original runtime/test byte and all native acceptance holds.
  Focused154tests pass; the three previously uncovered modules now exceed80%
  separately in statements and branches, with zero exclusions. Final whole-source
  review/artifact/native gates remain controller-owned.

## Private issue123 release-ancestry integration — 2026-10-22

- Preserve actual v0.2.25 ancestry and both parents source histories without
  tags, version overrides, dependency changes or accepted-main promotion.
- Keep qualified read-only kerning/revision workflows with the feature line
  owned-completion cleanup, exact Common Glyphs source and H1 history guards.
- Retain the held Italic Angle source and provenance solely as private candidate
  content. Its unrelated active-state/native regression and every other native
  acceptance hold remain open; no writer was enabled by this integration.

## Common Glyphs report repair (partial source milestone)

- Add explicit literal Copy Characters/Copy Original Report actions using the
  existing Qt-owned MIME factory/helper, with exact source readback, bounded
  ownership transfer and retained failure recovery. The selectable human view
  remains distinct; native callbacks/OS clipboard handoff still need qualification.

- Explicitly disclose primary character-copy normalization: NBSP/line separators
  can change in Qt plain text. Exact original characters and the complete source
  report remain recoverable from escaped JSON; native literal-copy/rendering
  acceptance is still open.

- Preserve exact Unicode in copyable escaped diagnostic JSON despite Qt plain-text
  normalization. Human-readable NUL displays a disclosed escape; the original
  source string remains exact in detached facts and JSON.

- Move generic all-font capture, analysis and owned report lifecycle into App;
  retain single-font order, sorted multi-font intersection, first-open primary
  character strings, family order, exact trailing spaces, slash proof text and
  complete alternative encodings. Caller-provided production metadata distinguishes
  verified mappings from unknown fallback; App imports no Glyphs/UFO peer.
- Expose the original optional charcoal action unchecked and unavailable, with a
  visible FontLab issue 8564 explanation. No font writer is implemented. Full
  original workflow and native report/action acceptance remain open.
- Focused source/Qt/boundary verification and retained failed attempts are in WORK.

## 2026-10-22 — Master Text Comparison review fix1

- Preserve QDialog.result and clean up failures during early panel state initialization.
- Run immediate presets before unrelated custom representation checks; retain the exact saved custom when its getter is held.
- Retain all failed owners and their errors, fence new construction, and expose explicit bounded recovery with partial receipts and per-signal cancellation.

## 2026-10-22 — Master Text Comparison workflow repair

- Restore original blank custom/Side-by-side defaults, automatic optional local presets/four attributed fallback lists, Run/double-click precedence, full sanitation diagnostics and every final space/newline.
- Share bounded opening-font capture, exact named-symbol staging/readback and retained sender/shape cleanup; persist only owned source controls after proof and geometry on Close. Native model binding, special text/IME, rendering and complete preservation remain pending (FontLab #8576).

- Carry one absolute opening deadline through capture, panel construction and cleanup, with a reserved half second; never restart the capture budget in the constructor.

## 2026-10-22 — Case Coverage review fixes

- Prevent unknown metadata on encoded uncased glyphs from producing all-clear feedback; retain known uncased and excluded rows.
- Honor automatic Details for complete analysis retained after proof failure or target choice, while keeping failed captures from showing stale reports.

## 2026-10-22 — Case Coverage candidate

- Add full original controls, persistent owned settings, current/all-font detached case reports, explicit aliases/Unicode alternatives/Math/Ligature/unknown findings and multi-character compatibility fixes.
- Propagate cooperative checkpoints through shared registered-font metadata loops and caller case metadata, preserving cleanup reserve; retain failed proof analysis and bound complete shared JSON serialization.
- Add explicit exact-view target choices and source-backed proof mechanics with content verification and bounded retained cleanup. Native text-block binding and actual proof usability remain held; no native/full-port acceptance claimed.

## 2026-10-22 — Separate legacy lowercase coverage

- Report legacy lowercase-to-`.sc` gaps separately from modern `.sc`/`.smcp` acceptance; retain export filtering and font order. Correct the Scriptmix menu total to 241.

## 2026-10-22 — Portable testing recipe

- Replace owner-specific testing scratch paths with FONTLAB_TEST_SCRATCH guidance so README-derived distribution metadata contains no personal volume path.

## 2026-10-22 — Smallcap Consistency

- Add complete modern/legacy smallcap reporting: export census, missing and orphan counterparts, capital/lowercase coverage and both kerning-group sides. Correct the original Boolean predicate and preserve Unicode/ligature/alternate names. Report unknown mappings and ambiguous groups.
- Use detached facts and bounded lazy native capture; explicit public.skipExportGlyphs compatibility policy, no font changes. Installed native qualification remains pending.

# Changelog

## 2026-11-10 — Issue 250 documentation round

- AGENTS.md describes the delegation, integration and release workflow.
- WORK.md reset to the current round; the earlier bytes are archived on the owner's workspace data volume, not public.

## 2026-11-01 — Priority for retained constructor failures (source candidate)

- Twelve panel constructors request topmost priority before fallible setup, covering their retained error-window show branches as well as normal launch. Preserve existing Window/Dialog type, native chrome, parent and refusal cleanup. No modal helper or global policy changes.
- Actual Qt tests force setup failure and cleanup refusal across17 factory profiles and4 class variants; assert flags before show, exact original exception, registry owner and retained terminal signals. Native stacking remains pending.

## 2026-11-01 — Shared modeless panel priority (source candidate)

- `show_script_dialog` adds `WindowStaysOnTopHint` before showing a new owned panel, preserving existing type/chrome. Existing owners that refuse Close retain their flags; modal helpers are unchanged. Regression controls cover flag preservation, ordering and failed flag configuration retaining the owner for normal cleanup. Independent launchers and native z-order acceptance remain open.

## 2026-10-22 - Writer message fixes after native session 3 (offline only)

- `master_metrics`: a field named twice through its alias now names both spellings (`'capHeight' and 'capsHeight'`); the docstring says `lineGap` is the Font Info master line gap and the hhea line gap is refused.
- `zone_native.check`: a capture timeout now refuses with the stale-font text instead of a raw `TimeoutError`.
- `alignment_zones.Editor.add` formats the integer position exactly (`T: 500`). `font_history` states that a second interrupt during rollback is not caught.
- Native session 3 (five owned-fixture runs, PASS) covered commit 1a64b9d; these message-only changes are tested offline.
- New `outline_extent.vertical_extent(layer)`: ymin/ymax from outline nodes (shape transforms applied; exact cubic and quadratic extremes; implied on-curve points between two quadratic `Off` nodes; closing segments), never from `boundingBox` and with no `update()`. Each segment's kind comes from the node kind (`isOn()`/`isCurve()`, else `Off`), not `contour.isTT`, so a contour that mixes cubic and quadratic segments measures correctly. Stroke thickness (`maxThickness`, which `flShape.boundingBox` adds) is not counted, by design: zones measure the outline. The per-contour `contour.transform()` is ignored; it is identity outside an interactive transform. `zone_native.bounds` (Suggest from o / O) now uses it: FontLab's cached layer and shape boxes stay stale after a Python node move, also after `notifyChangesApplied` (fl#8575, native session 4).
- Alignment Zones panel: the GUI-thread and Font-window refusals (`font_history.THREAD_TEXT`/`WINDOW_TEXT`) come before any master switch, so Apply now shows them and keeps the panel usable instead of locking it. A stale source, `UnrestoredError`, a read-back gap or a foreign result still lock it (offline tests).

## 2026-10-22 - Font-level master writers and refreshes that do not queue (issue 122 native phase 2)

- `scripting.select_glyphs` and `master_switcher.switch` no longer call `UpdateAll()`. On 9.0.9790 it queued glyph ids (fl#8537) and changed nothing visible; `FL.fl.Unselect/Select` repaint their cells and `setMaster(name, True)` alone gives the same state with an empty queue (issue 122 M1). `notifyPackageContentUpdated` is not used: it reverted the master.
- New `font_history.commit_masters`: ONE Undo step for font-level edits on one or more masters (M2 route A: `checkInitHistoryState(0)` on package and `mastersContainer()`, `setMaster(name, False)` per master, write, read back, restore the master, one `notifyChangesApplied(title, [package, container], False)`). Guards: GUI thread, active Font window, no Glyph window canvas. Rollback policy differs from `history.commit`: a failure before the notification restores every written master and notifies nothing (`RolledBackError`, a `ValueError`); a failed restore or notification raises `UnrestoredError` (a `PartialWriteError` without Undo advice). Never clears `updatedFgGlyphs`; notifies no glyph or layer.
- New `master_metrics.write_master_metrics`: ascender, descender, xHeight, capsHeight and lineGap through `commit_masters`; unknown fields (also the hhea line gap) and non-finite values are refused before history; `capHeight` is an alias of `capsHeight`; read-back tolerance 1e-9 for the stored C++ double.
- New `zone_native.backend()`: the first production `zone_editor.Backend` (capture, check, bounds, apply). Zones are read from `ps_zonesT/B` and written the Font Info way (`convertZonesToGuidelines` + `updateZonesFromGuidelines`) through `commit_masters`; retained rows copy their source native zone (tags, lock); empty or repeated names and zero-width rows of the other kind are refused. It does not call the serializer, so fl#8554 does not affect it; the serializer modules stay held.
- Known host defect, documented (fl#8574): after Undo/Redo of such a step, the six font-metric guidelines are missing until `updateFontMetrics()` or a reopen (saved file correct).
- Review fixes (after the native p2 session passed nine runs): `commit_masters` also rolls back and restores the master on an interrupt, then re-raises it; its Font-window refusal says "…before editing font masters."; `restored_text` lets `zone_native` say that a zone rollback re-creates the zone guides with new ids. `zone_native.apply` runs the thread/Font-window guards before `check` switches masters; row refusals raise `RowRefusal`; a failed read-back capture after the commit becomes `history.unstored_error`, whose rule (no claim about Undo) the zone texts now follow. `Editor.add` names new rows `T: <pos>`/`B: <pos>` with `.N` suffixes, as FontLab does. The Alignment Zones panel stays usable after `RowRefusal`/`RolledBackError`. `master_metrics` accepts `capHeight` as an alias of `capsHeight`. The driver's bad field is now `lineGapX`.
- Offline tests only; native driver notes: `issue122-native2/drivers/p2_app.py` (not run).

## 2026-10-22 - Coverage tests for the issue-122 modules

- `tests/test_cov_application_ui.py`, `test_cov_views.py`, `test_cov_fontui_init.py` and `test_cov_fontui_features.py` bring `application/ui.py`, `views.py` and `fontui` to the 80% branch-coverage gate (99-100%). Every assert carries a message.
- Tests only: no production code changed.

## 2026-10-22 - Canvas-scope identity by glyph name

- `require_history_scope` and `canvas_glyphs` match owners by font id and
  glyph name, not glyph id: on 9790 `CurrentGlyph().id` (412) differs from the
  canvas slot id of the same glyph (531175085312), so Em Star Polygon was
  refused from the Glyph window it draws in.
- The unreadable-canvas rule now allows no owner (as a readable canvas does)
  and counts a repeated owner once. Calls off the GUI thread are refused.
- New refusal text: "Switch to the Font window first: from a Glyph window
  FontLab cannot undo this edit in glyphs the window does not show."
- Offline only: the multi-glyph "every owner shown" branch and Metrics or
  Kerning canvases have no native receipt yet (TODO).

## 2026-10-22 - Direct writer canvas-history guards

- Guard all eight direct glyph-notification writers before history or mutation,
  using their notified owner sets and existing native-module seams. Raise
  Ascender checks all occurrence owners and dependants once before the batch.
- Add offline refusal and no-canvas controls for every writer. Package-level
  notification history still needs measurement; native protocols are unchanged.
- Verification: 6,330 offline tests passed (76 warnings); the F821 check passed.

## 2026-10-22 - Glyph-window history scope (fl#8573)

- `history.commit` refuses before any history call when a Glyph window is the
  active canvas and an owner glyph is not in that canvas; `create_glyphs`
  refuses any creation there before the first Add Glyph. Measured on 9790:
  from a Glyph window the Undo step covers only the canvas glyphs, and new
  glyphs get no Undo. New `edit_guards.canvas_glyphs` and
  `require_history_scope`; `glyph_window_ok=True` skips the check (no caller).
  An unreadable canvas allows only the current glyph as the single owner.

## 2026-10-22 - Complete queued-update disclosure

- Return stored ids and note from every shared writer; read the commit queue
  once and preserve pre-creation provenance. Remove unused snapshot/imports.
- Standardize visible note formatting and strengthen queued-write coverage.

## 2026-10-22 - Pending native update disclosure

- Ordinary writers report queued native ids and the FontLab issue 8537 date
  caveat instead of blocking. Explicit settled guards remain available.
- Preserve native queues, automatic-layer guards and older native protocols.

## 1.2.28 (2026-11-16)

- Backup naming accepts a user or timestamp suffix and resolves overlapping master names safely. Shape clone repair supports source view state and contour subsets. Metrics plans skip transitive composite users, and copy previews retain their write-time facts.

- Reuse selection-panel auto facts between control changes; skip manual composites when a base moves in the metrics plan. Read each prototype glyph VFJ once and support an Apply-local prototype cache.
- Add shared backup layer naming, detached shape repair, and read-only menu state properties. Remove process labels from source prose, document moved/new-code licences, shorten README without removing content, and record the pending-update native probe.

- Added shared affine math, guarded widget discovery, editor painters, owned
  menus and dialogs (`84243bb`–`8a8a617`); added the missing-window exception,
  ordered teardown and public-surface contracts (`0aa84ed`, `baa9bbf`).
- Moved VanillaSession to Glyport and FontParts editors/feature-block I/O to
  Fontport (`4574c06`, `4e035b0`). Old App names give import-free migration errors.
- Added shared edit guards, history, writer plans and panels, glyph/component
  creation, contour copying, hint counts and exact layer-row tabs
  (`312e308`–`2937e3a`). Native qualification remains separate from source tests.
- The full test suite needs Fly installed with its target packages. A test-extra
  environment without Fly produced 6240 passes and three missing-Fly failures.
  Fly source on PYTHONPATH alone also failed collection through native fallback.
  The documented prepared-venv command (Fontport and Glyport with dependencies,
  Fly `--no-deps`, Python 3.11 arm64) runs the full suite: 6243 passed.

## fontpr font addressing, creation checks, panel hooks, layer rows, components

- New `scripting.font_id(package)` returns `int(package.fgId)`, the id
  that fontpr tools need (fontpr finds fonts by fgId). `near_miss_native`
  and `_raise_ascender_capture` passed `package.id` to `get_font_info`;
  they and `glyph_creation` now use the helper. A source scan test refuses
  `font_id=...package.id`.
- `glyph_creation`: `_add` refuses a name that exists just before the
  `set_glyph(create=True)` call (that call replaces the layers of an
  existing glyph) and requires `"created": true` in the answer. When
  fontpr refuses the FIRST glyph before its command runs, the error is a
  plain `RuntimeError` ("... did not start ... No glyph was added.") without
  the Undo hint. Every unexpected error in the fill commit is wrapped and
  names the new glyphs. `auto_changes` text: "FontLab rebuilt it. Check
  it." The dotless-name candidate gap is documented.
- Undo wording: `history.unstored_error`, `history.NOT_STORED` ("FontLab
  did not store") and `history.CHECK_TEXT` ("Check those layers before you
  save."); `anchor_writer` and `layer_writer` use them, so
  `anchor_writer.apply_work` no longer says "Edit > Undo restores the
  font". The outline panel bases tooltip no longer says "Undo may not
  restore". A source scan test refuses such claims.
- New `named_tab.open_layer_rows(rows, *, expected_id, master, deadline)`:
  rows of exact (glyph, layer) items with `named_tab.SPACE` spacers and line
  breaks, in one verified fresh tab; every layer must exist before any
  symbol is built. `named_tab` now has `__all__` and is in the public
  surface test.
- Documented panel API: `outline_panel.HOOKS`, `outline_panel.MEMBERS`
  (for example `slot_error`, `spin`, `status`, `apply_button`),
  `outline_panel.NOT_STORED` and `outline_panel.UNDO_HINT`;
  `selection_panel.HOOKS` and `selection_panel.MEMBERS`. Tests check that a
  built panel has every listed name. Underscore names keep working.
- New `component_creation` (fix round 1: no scratch glyph):
  `build_components(package, target, wanted, facts)` clones one plain
  component that the font already has (`prototype`) once per
  `NewComponent(base, layer, x=0, y=0)` and re-targets the detached clones,
  BEFORE the caller's commit; `add_component(layer, shape)` adds one inside
  the caller's `history.commit` and checks that the layer holds one more
  component of that base. A font without any plain component is refused
  with "<target>: kept; ..." (`NO_PROTOTYPE`). A failed clone says that
  nothing was added to the font, with no Undo advice.
- Fix round 2: `component_creation.prototype` takes only a plain,
  unattached, default-style component: `excluded`/`contentLocked` False and
  `opacity` 1.0 (bound `flShape` members), and in the fontpr `get_glyph` VFJ
  no `attached`, `attachAnchor`, `off2026Variation`, `nonSpacing`,
  `booleanOperation`, `locked`, `excluded` or `opacity` other than the
  default (`COMPONENT_KEYS`, `STYLE_DEFAULTS`). Unreadable means not
  qualified. Clones are read back for base, layer and offset (`EPSILON`).
  `NO_PROTOTYPE` no longer claims that no constructor exists.
  `glyph_creation`: a glyph whose components FontLab did not add is named
  in the error; `CREATE_UNDO_TEXT` and `undo_text(filled)` for creation
  without outlines.
- `glyph_creation.NewGlyph(components=(Part(master, base, x, y), ...))`:
  NEW glyphs carry their components in their own `set_glyph(create=True)`
  data (`glyph_data` layer `elements`), so each new glyph and its
  components are one Add Glyph Undo step, also in a font without
  components. Components are refused before any call when FontLab cannot
  resolve them, and checked after the call.
- `glyph_creation.auto_candidates` docstring: the name rule is a pre-write
  heuristic; adding any glyph re-resolves every automatic layer
  (source reading); `auto_changes` is the guard.
- `outline_panel.MEMBERS`: one line of meaning per member.
  `named_tab.open_layer_rows` split into `_row_parts` and `_join`. The
  font_id source scan now catches any `<object>.id`.

## shared glyph creation, contour copy, hint counts and selection panel

- New `glyph_creation`: `create_glyphs` makes each new glyph through the
  fontpr tool `set_glyph(create=True, glyph_data={name, layers: [{name:
  master, advanceWidth}], unicodes})` with `font_id=package.fgId`, which runs
  FontLab's undoable Add Glyph command; then an optional `fill` writes the
  new layers in ONE `history.commit(operation="geometry")` that declares the
  new layers and glyphs. It never calls `flPackage.addGlyph` and never writes
  a FontGate record. Refusals before any change: a repeated or existing
  name, queued glyph updates, and (without consent) a name that can make
  FontLab rebuild automatic glyphs (`auto_candidates`: auto layers without
  an own recipe whose glyph name shares a whole dotted suffix segment;
  `rebuild_note`, `REBUILD_LABEL`). A failure after the first glyph exists
  names the new glyphs. `auto_signatures`/`auto_changes` keep the
  after-write check. `UNDO_TEXT` is the ruled user sentence.
- New `glyph_copies`: the copy-generator kernel of Small Caps From
  Capitals, Superior & Inferior Figures and Tabular Figure Copies (`Row`
  with `rebuild`, `survey_with`, `source_problem`, `half_up`, `create`) and
  `panel_type()` -> `CopiesPanel`.
- New `contour_copy`: `contour_shapes`, `copy_contours`, `repair_nodes`
  (copies only node names and raw node flags), `path_contours`.
- New `hints`: `hint_counts` counts PostScript hints by role
  (`isHorizontal()`/`isVertical()`), as FontLab's `removeHints` selects them.
- New `selection_panel` (+ `_selection_panel`): `panel_type()` ->
  `SelectionPanel`, the panel of the in-place Contours tools, with hooks for
  the script controls. Use selection catches refusals and shows them in the
  status line, and clears the consent tick.
- `outline_transform`: an anchor that moves to 0, 0 is refused unless it is
  exactly on 0, 0 already (an anchor at (0.3, 0) is now refused, fl#8527).
  The `bakes` docstring states the extra empty-shape condition.

## shared layer, outline and transform writers

- New `layer_writer`: the generic kernel that the component and outline
  writers shared (`Change` with `key`, `Plan` with `refused`/`held`,
  `Planner`, `Editor` with `retain`, `apply_work(..., allow_bases=False)`,
  `settle`, `layer_of`, `plural`, `shown`, `fmt(value, places=None)`).
  `component_writer` re-exports it, so the Components scripts do not change;
  their `fmt` output stays the same.
- New `outline_writer`, `outline_panel` (`panel_type()` loads
  `_outline_panel.OutlinePanel`) and `outline_transform` (`panel_type()`
  loads `_outline_transform.TransformPanel`): the kernel, panel and
  Transform/Slant writer that the eleven Contours scripts copied, moved as
  they were. The outline family keeps its own `collect`: each refused glyph
  is listed and skipped, and bases of automatic composites need consent.
  `OutlinePanel` is its own class (not a `ComponentPanel` subclass) and
  reuses the `anchor_panel` colour helpers.
- `anchor_writer.on_origin` is the fl#8527 Redo rule as one function.
  `require_safe` uses it with exact zeros (same behaviour);
  `outline_transform` uses it with the 0.5-unit rounding tolerance.
- Wording: the read-back error says "Check those layers before you save.";
  no kernel text claims that Undo restores the font, and the `apply_work`
  text says that the write strategy decides what is kept. The
  `component_writer` module text no longer says that Undo brings the
  component back.

## (extension) — shared component panel and offset writer

- New `component_panel` (load time: only `anchor_panel`/`metrics_panel`
  helpers, no PythonQt): `panel_type()` loads `_component_panel.ComponentPanel`,
  the non-modal panel that all seven Components writer scripts copied byte for
  byte (controls, live preview, Reload selection, Close, Apply through the
  script's `editor()`). `ink`, `readable_palette`, `ERROR_COLOR` and `MAX_ROWS`
  are the `anchor_panel` objects and `muted` is `metrics_panel.muted` (same
  code as the copies). Apply calls `edit_guards.require_settled()` with the
  default native module.
- `component_writer` gains the offset writer that Align By Anchor and Copy
  Offsets Between Masters copied: `plain_move` and `MoveEditor` (PythonQt
  `QTransform` loads inside `write`). The module text now names all seven
  writers.

## shared component eject and write kernel

- New `component_writer` (standard library and `history`/`edit_guards` only
  at load time; `fontlab` loads inside `keep_raw_state`). It holds the logic
  that Decompose and Nested Finder copied byte for byte, moved unchanged:
  `collect`/`Plan`/`Change` (auto layers listed, never edited),
  `require_safe` (queued native updates, fl#8537; glyphs the geometry policy
  refuses), `apply_work` through ONE `history.commit(operation="geometry",
  retain=..., read_back=...)`, and the eject block: `refreshed`, `eject`,
  `keep_raw_state` (raw Smooth bits fl#8516, element note fl#8538, element
  name), `copy_problem` (plain base layer, affine only, no non-component
  composite, loop, nesting deeper than `MAX_DEPTH` 64, outer perspective),
  `part_counts`, `parts_text` and `EjectEditor` (retains each removed
  component, its data and builder through `history.component_history`).
- `require_safe` now calls `edit_guards.require_settled()` with the default
  native module instead of a module the script passed; same module.
- In `tests/test_public_surface.py` and the README table. Offline tests only:
  native Undo of a removed component (fl#7641) is not measured.

## `history.commit` retains removed native objects (fl#7641)

- `history.commit` has a new keyword `retain: Sequence = ()`. Retained objects
  go first in the one notification, before the layers, and the call becomes
  `notifyChangesApplied(title, retain + layers + created + glyphs, True)`
  (deep history), as glyport's `_retain_component_history`/`_notify` do for a
  removed component. They get no `checkInitHistoryState` and are not in
  `Committed.created`. Without `retain` the two-argument call is unchanged.
- A retained object that reports `autoLayer` is refused before any history
  call, with the same "auto layer ... is in the edit list" `ValueError`.
- New `history.component_history(shape)`: `(shape, shapeData, builder)` for a
  component, `()` for other shapes, `ValueError` for a component without
  shapeData. Call it before `removeShape`.
- Offline tests prove the call order and arguments only; native Undo of a
  removed component is not measured.

## anchor writer kernel and panel base

- New `anchor_writer` (standard library only at load time): the plan and
  write kernel of the seven Anchors writer scripts. `collect` plans every
  existing layer (auto layers listed, never edited); `require_safe` refuses
  queued native updates, an existing anchor moved to 0, 0 (FontLab cannot
  Redo it, fl#8527), a "set" edit of a name that several pins carry, and
  glyphs that the geometry policy refuses; `prepare` builds every pin before
  history and gives new pins the name-derived `anchor_copy.APPEARANCE`;
  `apply_work` writes through `history.commit(operation="geometry",
  read_back=...)` and raises "FontLab did not store ..." for a value FontLab
  did not keep. `layer_of` reuses `anchor_copy.layer_of`.
- New `anchor_panel` (`ink`, `muted` from `metrics_panel`, `readable_palette`,
  `ERROR_COLOR`, `MAX_ROWS`, `panel_type()`) and `_anchor_panel.AnchorPanel`
  (PythonQt, loaded by `panel_type()`): live preview, Reload selection, Close,
  Apply. It calls `scripting`, `anchor_writer` and `history` through their
  modules, so replaced functions take effect.
- Both modules are in `tests/test_public_surface.py` and the README table.

## App prep before scripts are re-pointed

- `history.commit`: a `checkInitHistoryState` failure on any item (after earlier
  items were initialised) now raises `PartialWriteError` with the Edit > Undo
  text and the original error chained and collected, as the docstring promised.
- `history.auto_facts`: component base names are normalised with `str()`, as
  `names_edit.scan` does.
- Usage examples in `history` and `names_edit` use the recommended
  `import fly.ap.core.history.glyphs as history` / `import fly.ap.glyphs.names.model as names_edit`.
- Metrics panel status reads "N layers skipped (auto)".
- NOTICE: the Glyport Apache-2.0 notice gap is resolved (Glyport ships
  `LICENSE-APACHE-2.0` and a NOTICE for `fontlab_glyport/ui/session.py`).

## shared helpers for the ported scripts

- `glyph_catalog.capture(deadline=None)`: public, documented glyph-catalogue
  capture. It delegates lazily to `_glyph_catalog_native.capture`, which stays
  the implementation (App's own callers are unchanged).
- New `edit_guards`: `require_selection_window(package_id)`,
  `require_no_editors(qt=None, deadline=None)` and `require_settled(native=None)`
  delegate to the reviewed private guards or read the native update queue once
  (never clear it).
- New `history`: `commit(title, layers, glyphs, mutate, operation=..., facts=...)`
  runs one native Undo step (init history, mutate, stamp, one notify of layers,
  created objects and glyphs, stamp, read-back). Refusals come first: queued
  updates, optional Unicode window/editor guards, auto layers in the list, and
  the per-operation policy (`rename`/`unicode`/`geometry` refuse auto owners and
  bases of auto composites, chains included; `metadata` refuses only auto
  owners). Later failures raise `PartialWriteError` with the Edit > Undo text.
- New `metrics_panel` (pure) and `_metrics_panel` (PythonQt, via
  `panel_type()`): the Metrics block (plan model, survey, in-place
  `shift_and_set`, read-back, commit, rebuild note, preview table and the
  non-modal `MetricsPanel` with the override tick bound to the changed names).
  Under the geometry policy a glyph that owns an auto layer is listed and
  skipped as a whole.
- New `names_edit`: `Entry`, `Facts`, `scan`, `refusal(facts, name, operation)`,
  `editable`, `fresh_facts` and `commit` for the Names editors.
- `masters.associated_master(name, masters)`: FontLab's `@`/`#` layer-name rule.
- minors: `editor_painters._attach_all` does nothing after `close` (a kept
  timer can still fire); the disconnect-failure test asserts the kept timer.
  `_defer(first=True)` docstring states the drain limit. The `fontui` finder
  answers module names only; its `find_spec` raising is documented. `MOVED` and
  `MOVED_HOME` leave `fontui.__all__` (still importable by name).
  DEPENDENCIES names the exact sibling imports.
- Not changed: `fontlabapp.__getattr__` (raises `RuntimeError`, not
  `AttributeError`, for unknown names off-host); no drag-and-drop panel base
  (only the six scripts would use it, and their blocks differ).

## public surface of the shared modules

- `__all__` in `affine`, `qtsafe` and `qt_dialogs` (new) and complete in
  `editor_painters` and `fontui`; docstrings on every exported def, class and
  public method; `#:` comments on constants. `tests/test_public_surface.py`
  checks this from the source (AST) and checks the README migration table.
- New `qtsafe.MainWindowNotFound(RuntimeError)`, raised by `qtsafe.main_window`
  and so by `OwnedMenus.main_window`. Same text ("FontLab main window not
  found"): `except RuntimeError` and text matches keep working. The off-thread
  `qt_list` refusal stays a plain `RuntimeError`.
- `OwnedMenus._defer(fn, first=True)`: subclass seam that queues teardown at the
  front. Same result as Glyport's current `_pending.insert(0, _pending.pop())`,
  which keeps working. `remove(token: int)` (no `type: ignore`); docstrings for
  `__init__`, attributes, `_token`, `_guarded`, `_menubar`, `_reaper`; the
  dispatch guard's scope (only its own slots) is documented.
- `editor_painters`: entries are `PainterEntry` / `OverlayEntry` NamedTuples
  (tuple indexing still works). A failed timer teardown no longer skips overlay
  detach; that timer is stopped, kept alive and never deleted with a live slot.
  A raising `painter.end()` goes to the sink after the first error, never into
  `paintEvent`. `_update_all` documented; absolute imports explained.
- `fontui`: `import fontlabapp.fontui.<moved module>` now raises `ImportError`
  naming `fontlab_fontport.ui.<name>` (meta-path finder, appended once, exact
  names only). Factories have type hints and full docstrings.

## FontParts-bound editors leave App; packaging cycle broken

- Deleted `fontui` modules `fontinfo`, `groups`, `groups_view`, `kerning`,
  `kerning_view`, `transform`, `transform_view`, `batch`, `batch_worker`,
  `sequence`, plus their tests and the five matching `examples/`. They live in
  `fontlab_fontport.ui`.
- `fontlabapp.fontui` keeps `lifecycle`, `model`, `native`, `preview`,
  `sequence_canvas`, `wrap`, browsers, features and Designspace panel. The names
  `font_info_editor`, `groups_editor`, `kerning_editor`, `transform_editor`,
  `batch_panel`, `glyph_sequence` and the ten module names are tombstones: a
  from-import or attribute read raises `ImportError` naming `fontlab_fontport.ui`.
- `pyproject.toml`: removed extras `fontedit`, `fontsequence`, the Fontport entry
  in `test`, and `[tool.uv.sources]`. App now installs with neither peer.
- Tests: `test_package_boundaries.py` (AST guard: no `fontlab_glyport` /
  `fontlab_fontport` import in `src/fontlabapp`, no peer in `pyproject.toml`);
  tombstone tests for the removed fontui names; `test_fontui_lifecycle.py` keeps
  `follow_history` coverage; `test_fontui_wrap.py` keeps the pure `wrap` tests.

## VanillaSession and feature blocks leave App

- `fontlabapp.core.legacy.vanilla` is now an import-free tombstone: any import raises
  `ImportError` naming `fontlab_glyport.ui.session` (new home of `VanillaSession`).
- `fontlabapp.core.scripting.read_feature_blocks` / `write_feature_blocks` are
  tombstone functions: calling them raises `RuntimeError` naming
  `fontlab_fontport.feature_blocks`. Every other `scripting` function is unchanged,
  so Fontport's `current_package` import stays cheap.
- Deleted `examples/vanilla_controls.py`, `tests/test_vanilla_session.py`,
  `tests/test_vanilla_session_lifetime.py`, `tests/test_scripting_features.py`
  (the code now lives and is tested in Glyport/Fontport). Added
  `tests/test_tombstones.py` (from-import form, attribute form, new-path text,
  no peer import).

## dialog helpers

- `fontlabapp.qt.dialogs` gains `name_filters(filetypes)` (`["ufo", ".glyphs"]`
  gives `["Files (*.ufo *.glyphs)"]`; `None`/`[]` give `[]`) and
  `run_text_dialog(gui, message, value, title, ok_button, parent_args)`
  (owned `QInputDialog`; returns the text, or None on cancel; deleted on every
  exit).
- Generalised from `fontlab_glyport.glyphsapp.fontlab_dialogs`; no Glyport
  import. Glyport uses both helpers. Offline tests only; native dialog run is
  a separate owner gate.

## owned menus and tool windows

- New `fontlabapp.qt.menus`: `OwnedMenus`, `OWNED_MENU_TITLE`.
  `add_action` finds a FontLab menu by title (`&` ignored) or creates one owned
  menu; `tool_window` shows a widget in a tool window and fires `on_close` once.
  `remove` and `close` called inside one of its own slots are queued on a shared
  `DeferredBatch` and run once after the slot returns, so no QAction or window
  is disconnected or deleted under signal dispatch (PythonQtSignalReceiver
  double-delete). `close()` removes newest first, tries every item, re-raises
  the first failure. `main_window()` uses `qtsafe.main_window`.
- Generalised from `fontlab_glyport.plugins.fontlab_host`; no Glyport import.
  Glyport uses this helper. Offline tests only; native menu add/trigger/remove
  inside the triggered slot is a separate owner gate.

## generic glyph-editor painters

- New `fontlabapp.qt.painting.editor`: `EditorPainters`, `PaintContext`,
  `AFTER_NATIVE_LAYER`, `BEFORE_NATIVE_LAYER`, `LAYER_FILTERS`, `POLL_MS`.
  One transparent overlay per visible GlyphWindow viewport; a 250 ms poll finds
  new windows. `register` / `remove` / `close` start and stop the poll.
  Callback errors go to `error_sink`, never out of `paintEvent`. The painter is
  saved and restored around each callback. Signals are disconnected before
  `deleteLater`. `document_id` and layer filters work.
- `register("before_native_layer", ...)` raises `ValueError` (the native canvas
  paints opaquely). Glyport keeps its `UnsupportedCapability` refusal in a
  subclass.
- Ported from `fontlab_glyport.drawing.editor` with `fontlabapp.contours.affine` and
  `fontlabapp.qt.safe`; no Glyport import. Glyport uses this helper.
- `GlyphWindow.draw` docstring and README cross-reference it. Offline tests
  only; native overlay regression is a separate owner gate.

## shared affine math and Qt-safe helpers

- New `fontlabapp.contours.affine`: pure 2D affine math (`Affine`, `IDENTITY`, `concat`,
  `apply`, `invert`, `rotation`, `from_qtransform`, `viewport_transform`). No Qt
  import. Non-finite input raises `ValueError` unless `finite=False`.
- `fontlabapp.qt.safe.qt_list` now raises `RuntimeError` off the main thread
  (moved from Glyport). New `qtsafe.main_window(fontlab, qt)`.
- `canvas_rsb`, `canvas_anchor_rings` and `drawing` sample the canvas map once
  through `affine.viewport_transform`. `canvas_rsb.compose/matrix/map_point`
  keep their names and delegate to `affine`.
- Removed `fontlabapp._qtsafe` (private alias; no importer outside App).
  Offline tests only; native overlay regression is a separate owner gate.

## .141 reviewed-source integration candidate

Combine complete typed Symmetry/Cutoff with the current numeric workflows and
the basic Character Map initial viewport. Preserve every prior runtime/menu and
all original filters, pair order, type identities and existing native holds.
Source/artifact evidence does not qualify native/font-history behavior.

## 0.2.143.dev0 — Find Files literal query candidate

Preserve embedded NUL in both Find Files editable query fields and in the byte
profile's ordered native combo histories. Retain the original 32,767 UTF-16-unit
editor limit, literal matching, profile-specific publication and cancellation.
History insertion preserves the live draft, selection and Undo state. The shared
literal Qt helper is a separately reviewed dependency; final artifact and native
acceptance remain separate from source preparation.

## 0.2.138.dev0 — Character Map initial viewport

The basic profile starts at 700 logical pixels high so the added FontLab coverage
controls leave six complete BMP rows visible at the default typography. This is
an explicit adaptation of the original 640×460 initial size. Original controls,
full scrolling grid, typography, predicates and flexible user resizing remain.
Native geometry and full original workflow acceptance require root qualification.

## 0.2.119.dev0 — Text Holder NUL loss prevention

PythonQt transfers containing NUL (U+0000) are refused before editor mutation,
panel replacement or Find/Replace selection changes. Native MIME/key/IME refusal
is contained and reported in the owned status. Direct Python calls raise
ValueError. Existing draft, selection, history and saved bytes stay unchanged.
Checked host content is captured once before panel replacement and reused by
the constructor, preventing a later read failure after an old draft closes.
Ordinary Qt5/Qt6 retain their existing NUL support; UTF8 storage still supports
NUL. Geometry is unchanged. This safety policy is not full original Unicode
support: native NUL workflows remain explicitly unaccepted pending a faithful
length-aware transfer and root-owned native verification. Raw external cursor or
document mutation bypasses panel ingress and is not qualified by this repair.

## 0.2.103.dev1 — Character Map coverage repaint

Refresh now schedules the visible grid to repaint after successful coverage
capture and after a failure clears stale coverage. The original reference-face
controls and text remain unchanged. Four actual Qt event-loop regressions failed
before the fix and pass after it; the full 53 Character Map controls pass on Qt5.
Ordinary rebuilt archive and native acceptance are recorded separately.

## 1.2.28 (2026-11-16)

Add Simon Cozens' complete ordered Mark/base UFO lib fragment workflow using
the existing Glyport category policy through Fly and a shared read-only App
snapshot panel. Escape XML glyph names; reject observed source changes and
incomplete captures. Source/artifact controls are tracked separately from pending
native preservation, lifecycle and release acceptance.

## 0.2.73.dev0 — private integration candidate

- Combine the reviewed three contour-selection tools and two spacing worksheets with the current Qt readers and Box geometry. Native acceptance remains pending; no release or live installation.

## 1.2.28 (2026-11-16)

Retain primitive/container types and float bits in exact source tokens, attempt
independent viewport/activation restoration after getter failures and report
known prewrite faults as refusals. Copy original source symbols before writes.
Original-to-formatted occurrence mapping remains unresolved; ordinary native
input is not qualified and the complete next/previous pair remains open.

## 1.2.28 (2026-11-16)

Add the complete Italic Angle editor, immutable source snapshots, one native
masters-container Undo batch and the original slanted-stem gauge. Changed fonts,
master order/current master and source values refuse before writing. Empty and
unchanged batches create no history; Close disconnects spins before destruction.
Source suites and the original native UI/default-master persistence checks pass.
Artifact/native regression/release gates remain pending in WORK.md.

Refuse changing angle batches before history when FontLab's native history
encoding would alter a master's blueScale (fl#8531). Hinting stays untouched;
unchanged angle batches remain no-ops. The native non-default master reopen
reset also occurs without edits and is tracked separately as fl#8530.

The original candidate record above remains historical. Main967d349 held this
prerelease after an unrelated element active-state regression; this private
integration retains that hold and does not promote the writer.

## v0.2.25 — 2026-10-18 — read-only kerning and revision audits

Add Kerning Persistence Audit and Compare Open Font Revisions with explicit
source choices, exact named-field results and owned callback teardown. The
isolated runtime passes867App tests,788consumer tests,68new native check instances
and the full68original-menu regression. Downloaded-tag acceptance follows release.
Keep the earlier Italic Angle prerelease on verification hold; use the last
accepted runtime plus these two independently qualified tools.

## 1.2.28 (2026-11-16)

- Add exact current/all-master kerning persistence risk reports for the measured
  FontLab9.0.9784 VFJ two-UPM load boundary, preserving explicit zero and raw values.
- Add explicit open-font/master revision comparison with named-field details,
  missing-source states and independently reported raw node flags.
- Reuse reviewed lifecycle helpers, lazy menu factories and guarded source checks.
  The isolated artifact passes68native check instances and all68prior menu
  regressions. Versioned release and independent downloaded-tag gates remain open.

## 1.2.28 (2026-11-16)

- Preserve the chosen history timestamp after native notification and refresh
  for targets and transitive dependants. Forced native second-boundary checks
  pass on the owned eight-glyph calibration; original recipe refusals remain.

- Add complete Center Horizontally, Round to Grid and Snap to Metrics panels
  with original controls, preview rows, methods and statuses on the guarded
  Masters lifecycle. Construct Close before reading native font state.
- Bind all raw points, pin attributes, bounds, widths, master/active-layer ids,
  metrics, selection, membership, options and affected dependencies. Cache a
  preconstructed operation only after a complete stable preview; keep expected
  refusals visible without discarding the preview.
- Retain original direct master-layer rebuild names as information. Use the
  reviewed transitive point core for writes. Keep canonical Font-window selection
  and contourless current-glyph safety fixes when adding the two lazy facades.

- Add Center, Round and Snap preview arithmetic and preconstructed point moves,
  preserving native pin identity, style, expressions and untouched raw axes.
- Validate the full batch, bind raw snapshots, refuse origin-Redo moves and
  unsupported dependency graphs, then enroll transitive component users before
  one final UTC-stamped notification. Automatic layers are initialized only.
- Keep inactive master recipes frozen without vetoing another master's edit;
  explicit recipes on edited or notification-active dependency layers still
  refuse. Bind the actual active-layer identity used by native notification.
- Apply active-layer preflight and history enrollment to targets as well as
  dependants. Preserve attempted-write ownership when post-write reads fail,
  retaining the first error and attempting conservative history/refresh cleanup.
- Native acceptance, complete original workflows, UI and release remain pending;
  the released 68 tools and their runtime files remain unchanged.
## v0.2.23 — 2026-10-18 — foreground reporters and exact glyph dates

Add Sidebearing Direction Marker and Duplicate Anchor Rings with owned foreground
painting, explicit direction/handle controls and verified cleanup. Preserve the
committed glyph date across native observers in guide and anchor-copy writers.
Source/artifact/native gates pass, including full68original regression and six
forced date-boundary cases. Downloaded-tag verification follows this release.

## 1.2.28 (2026-11-16)

- Keep the chosen UTC timestamp after native notification and UpdateAll in
  guide additions, guide rewrites and anchor copying, including observer errors.
  FontLab's window observer can otherwise change it after history capture
  (upstream fl#8529), leaving Apply and Redo with different saved metadata.
- Add twelve regressions; actual installed native forced-second-boundary tests
  pass twice per writer with complete font/history/Undo/Redo/reopen comparisons.
  No fields are excluded and Undo/Redo perform no application date repair.

## 1.2.28 (2026-11-16)

- Pass an explicit empty QBrush at PythonQt's native painter boundary; preserve
  unfilled rings and add the measured enum-conversion regression.

- Add immutable source/occurrence snapshots and original strict duplicate-pair
  ring geometry, including all three pair markers for coincident triples.
- Preserve original handle sizes, scale exponents and red/yellow stroke widths;
  restore the borrowed painter on failure and bound native reads/pair searches.
- Add modeless Enabled, explicit5/8/12handle choices(default8),bound status and
  Close on the reviewed RSB activation/cleanup lifecycle. Compare two complete
  snapshots; contain paint faults until safe reactivation, including empty errors.
- Seed reviewed RSB lifecycle/Drawing/registry dependencies unchanged, preserving
  canonical selection guards. Add lazy ring API/UI facades and Apache NOTICE.
- Label the foreground adaptation visibly. Geometry, pixels, lifecycle,
  preservation and both actual menus pass native acceptance; the full prior68
  regression passes after the separately measured glyph-date correction.

## v0.2.22 — 2026-10-18 — safe selection context and current glyphs

Reviewed source619tests, installed-wheel Scriptmix771tests/1historicalskip,
extracted-sdist617tests/2sibling-onlyskips, full changed-module coverage96.55%
and all68existing native script scenarios pass. Native positive/refusal controls
preserve complete font/workspace/history. No new sample-tool count.

### Verify Font-window context before selection

- Refuse legacy selection writes unless the current native FontWindow has a
  verified YFrameWindow ancestor. A Glyph window, docked/unknown panel, changed
  font, unreadable context or cyclic/exhausted parent chain changes no selection.
- Recheck immediately before clearing selection; retain explicit add/replace
  behavior and font order in the supported regular Font-window context.
- Retain transient PythonQt ancestor wrappers during traversal so Python cannot
  reuse their identities and falsely reject a valid Font-window parent chain.

### Shared current-glyph fallback

- Retain valid empty and component-only current glyphs when the Font window has
  no selection. Preserve Font-window order, closed-font handling and native read
  failures. Tests cover the shared helper and its Proof consumer. Installed
  native checks13/13 and all four original Proof workflows pass with complete
  font/workspace/history preservation; independent review approves the fix.

## v0.2.21 — 2026-10-18 — anchor-copy refusal layout

- Fit the owned dialog when a refusal explanation appears; keep a short footer
  status. The anchor preview, explanation and Close controls remain separated.
- Retain the preceding tags unchanged: their numerical acceptance passed, but
  the visual gate rejected overlapping refusal text before canonical promotion.
  New native geometry checks and independent fresh-tag acceptance are required.

## v0.2.20 — 2026-10-18 — Copy Anchors From Glyph

- Retain full source completion, merge/replace, width scaling and master scope.
  Preconstruct native values, preserve existing pins and stabilize new appearance.
  Bind raw coordinates, widths, expressions, selection and every option.
- Refuse automatic dependants before mutation (fl#8512), and existing-anchor
  origin moves that native Redo cannot restore (fl#8527). Keep original previews.
  Installed candidate passes11original/7complete persistence/130native controls
  and Close. Prior67 regression, App597, Scriptmix770+1skip and280installed
  tests per wheel/sdist pass. Downloaded-tag follows release.

## v0.2.17 — 2026-10-18 — compact Master Switcher

- Add original ordered master/location buttons, exclusive current emphasis and
  first9shortcuts on the guarded owned Masters shell. Preserve all60released tools.
  Native original5/preservation2/additional43 pass on3/25masters, including
  actual key events and lifecycle/fault controls. Prior60same-runtime regression
  passes. Source and candidate acceptance reviewed; fresh-tag acceptance follows release.
  Preserve package-master semantics; no editor-layer switching claim.

## v0.2.16 — 2026-10-18 — live Node Coordinates

- Port complete selected-node coordinate/pair tables,400ms polling and Copy.
  Follow active glyph/master edits with guarded font binding and owned cleanup.
  Accept490combined native workflows/145preservation checks andClose60; retain24new timer/Copy/fault/font-boundary controls. Independent downloaded-tag pending.

## v0.2.15 — 2026-10-18 — read-only glyph reviews

- Fix original native feature iteration: use fgOTLayout.keys tags, not its
  sequence code values; eliminate392false candidates and retain exact395Rafi
  list/selection. New native-shaped tests and unchanged original oracle pass.
- Accept combined59native:483workflow/143preservation/407safety/294error plus
  22selection/layout andClose59; retain all originals and the full130scope.

- Add complete Select Unreferenced Glyphs and Interpolation Preview source tools.
  Preserve candidate/reference rules, all controls and full interpolation painting.
- Reuse guarded lifecycle, source snapshots and safe painters; retain previous57
  menus/rows exactly. Source/artifact/native/prior57 pass; release/ pending.

## v0.2.14 — 2026-10-18 — read-only Anchors

- Add complete Anchor Cloud, Anchor Compatibility and Mark Attachment Preview
  source tools with shared raw anchor snapshots and existing owned lifecycle/
  geometry/painter boundaries. Preserve original controls and all54prior mappings.
- Reject stale data without rejecting intended selector changes; retain exact
  None paint diagnostics, explicit current-glyph fallback and complete cleanup.
  Source/artifact/native/prior54 gates pass; integration/release/ pending.
- Fix late-binding tree columns after native image review: expose every master
  and missing-anchor cell, with source and native width/count regression checks.
- Accept combined57 native:473workflow/139preservation/368safety/261error plus
  16selection/layout andClose57. Preserve previous54menus and all original inputs.
- Correct the carried Components NOTICE status to its verified release receipts.

## v0.2.13 — 2026-10-18 — read-only Components

- Accept all five installed-wheel native workflows and prior49regression: combined54
  passes453workflow/133preservation/305safety/201error controls,6selection andClose54.
  Fix falsey-current fallback, retain exact empty Compatibility scope and safe painters.
  Source/artifact/privacy checks pass; downloaded-tag is recorded separately.

- Fix the measured CountBadges empty-selection fallback for a valid falsey native
  CurrentGlyph. Resolve selected/current names with original is-not-None rules;
  keep Compatibility's exact selection and prior Proof/scripting helpers unchanged.
  Source proof: App506, Scriptmix620/1skip, Git-free619/2skips; fix2artifact/native
  confirmation remains parent-owned and pending.

- Fix: Compatibility's selected scope keeps empty selection;
  CountBadges alone retains its original current-glyph fallback.
- Fix: reuse ProofView painter activation/finalization containment,
  exact None success and explicit owned fallback cleanup/Close release. Source-only
  regression proof: App505, Scriptmix618/1skip, Git-free617/2skips; native/artifact
  re-review remains pending. Prior49menus and mappings stay exact.

- Add five complete component inspectors, preserving original UI, ordering,
  selection, simulation, pure CSV oracle and complete native badge drawings.
- Share lazy calculations and existing owned Proof/Names lifecycle; guard exact
  font/master/membership/source drift, opening/paint errors and Close cleanup.
- Append five mappings (54 total) and immutable Git-free prior49 provenance/menu
  byte checks; preserve the prior45 invariant and all original sources.
- Source tests only; independent review, artifacts, native preservation/painting/
  safety/Close and prior49 regression remain pending. No release is claimed.

## v0.2.12 — 2026-10-18

- Add complete Spacing String Preview, Width Table, Contour Order View and Node
  Statistics with original controls, defaults, class/key/helper interfaces and
  exact native scenario data. No original source is changed or removed.
- Reuse lazy App helpers, existing Proof/Names/Masters lifecycle, actual transformed
  outlines, raw node-polygon winding and contour/node counts. Preserve zero,
  missing and auto values and numeric width sorting.
- Guard initial scans, exact source/current-master/ordered-master domain and
  Whole-font membership. Failed reads/paints clear results and handles, retain
  Close and diagnosis, drain repaint queues and allow explicit same-font recovery.
- Append four provenance pairs (49 total); previous 45 menus/rows remain exact.
  Source/fix review, installed-wheel native acceptance and artifact audits pass:
  41 original workflows,8 complete preservation,10 paint,24 opening,59 safety,
  actualClose 4;70 source hashes and imports match. Node uses its fresh post-seed baseline.
- App 497/actual-wheel Scriptmix 501 passed, 1 skipped and180 installed tests each for wheel/sdist
  pass;66 production files,72 wheel/116 sdist entries and license/NOTICE/privacy match.
- Same-wheel45 prior-tool regression passes379 workflow/115 preservation/166 safety/
  116 error controls/Close 45,113hashes and import restoration. Combined 49 native:
  420 workflow/123 preservation/225 safety/150 error controls/Close 49. Historical 15 chooser
  receipts are retained; no new chooser run occurred. Full 130/archive/held 7 Names stay open.

## v0.2.11 — 2026-10-17

Fix2: native screenshot inspection exposed an inherited tick endpoint defect.
Shared nice_ticks now covers the native plotted range, including max713,
while preserving nice steps and bounded generation. Complete original chart
commands have axis-bounds regressions. Scoped source review and native screenshots pass.

Fix1: refresh scans the actual ordered master domain and refuses mid-scan changes;
Whole-font actions recheck complete ordered glyph membership; repeated failed
chart invalidation schedules at most one clear repaint. New regressions retain
explicit refresh recovery and captured Selected scope. README frontmatter fixed.
Independent fix review and the four-tool native/artifact gates pass.

- Add complete Overview, Width Chart, Glyph Weight Chart and Compatibility Check,
  retaining original controls/defaults/keys/classes, labelled lines and bars,
  structural tree, master-axis order, limits and native DRIVE interfaces.
- Share original twelve-step transformed contour areas/counter nesting, missing
  width/weight semantics and own-contour signatures through lazy App helpers.
  Reuse existing owned panel/signal registry/paint containment, with visible
  initial-read failures, exact source/master action guards and native-handle cleanup.
- Bound tick generation for equal huge ranges so tiny floating increments cannot
  loop forever; normal original chart ticks and numerical meaning remain.
- Keep all41previous menu bytes and provenance rows exact, append four new pairs,
  retain originals/dependencies and consolidate README within200lines.

Installed-artifact acceptance on FontLab9.0.9784 passes43original workflows,
8complete font/workspace/history checks,12real paint controls (axis coverage and
six-event settling),24opening faults,43safety and actualClose4/4. Fresh charts
confirm the clipping fix;67exercised hashes match. App480,actual-wheel Scriptmix413,
163installed wheel/163sdist tests and63production-file parity pass. All45mappings
pass with prior41rows/menu bytes exact. Separate chooser8+7checks use fix1
artifacts with unchanged chooser/common source. Same-fix2-wheel regression of
all41prior tools passes336workflows/107preservation/123safety/80error controls/Close41;
106source hashes verify and imports restore. Combined45:379workflows/115preservation/
166safety/116error controls/Close45.
Full archive cleanup and held7Names editors remain separate.

## 1.2.28 (2026-11-16)

- Fix R3: read only layer/component structure for auto-rebuild warnings, avoiding
  the native `fgGlyph` metadata getter while preserving warning targets and text.

- Fix R2: include transitive component-dependent glyphs in metadata history
  lists, retaining existing rename layers and excluding added dependent layers.

- Fix I1: share rename/suffix candidate filtering and refusal/status checks,
  preserving both public interfaces, row order and exact precedence.

- Preserve complete Batch Rename, Duplicate Unicodes, Glyph Notes, Glyph Tags,
  Mark Color Palette, Suffix Tool and Unicode From Names controls and actions.
- Share lazy App0.2.11 plans/reads/batch writes, complete snapshots, safe opening
  reads, whole-batch preflight, no-op skips and honest partial/post-write errors.
- Retain auto-layer rename refusals, plain component updates, original warnings
  and explicit Reload/Rescan rebinding. Source-only tests; native/artifact gates
  remain pending. Previous41menus/rows and archived originals stay unchanged.

## v0.2.10 — 2026-10-17

Native installed acceptance: all41core tools pass336workflow/107preservation,
123safety,80writer/error controls andClose41; separate15chooser checks pass.
All41hash mappings and60Appsource bytes pass. Full archive migration staysactive.

- Retain complete Glyph Grid, Text By Master, Waterfall and Word Finder tools,
  sharing real transformed paths, exact advance-only runs, original word data,
  filters and guarded owned UI through lazy App0.2.10 helpers.
- Fit Grid's common scale to wide overhangs and tall accents/components; preserve
  deliberate Reload font/selection adoption and refuse automatic stale refresh.
- Clear failed previews, contain painter/callback/finalization errors and retain
  original controls/keys/scenario globals. Copy has host-free coverage; native
  clipboard remains excluded. Installed native/artifact acceptance passes.

###  fix1 — contain all opening font reads

- Build empty controls/status/Close before binding/id/selection/maps/characters/
  master reads; diagnose early failures in a closable invalid panel.
- Retry initial loads through existing guarded controls without adopting a
  different known font. Preserve explicit Grid Reload adoption and Waterfall's
  initial active-master choice with signal state restored in finally.
- Add23actual constructor/recovery/failed-state Close/stale-binding regressions;
  independent source review and installed native/artifact reacceptance pass.

## v0.2.9 — 2026-10-17

Review fix: retain a completed batch's applied outcome, original cause and
Undo/Refresh guidance across all later display/preview failures. Preflight and
partial-write diagnostics stay distinct. Both selected editors reuse the shared
preview-table builder while retaining exact headers and checkbox callbacks.

Add complete Exceptions Finder and Pairs From Text menu workflows. Share original
class precedence, word parsing, explicit/effective previews and ticked plans in
lazy App0.2.9 helpers. Reuse complete snapshot-bound preflight/history writing,
including zero/absence and native save/reopen range refusal; retain all controls,
manual checkboxes, Refresh and owned Close. Failed reads clear pair/value previews.
Append two exact provenance mappings without changing prior35. Host-free tests
pass; all37native tools pass301workflow/99preservation checks,94safety,32writer
and12postwrite controls,15chooser checks andClose37. Full archive migration
and cleanup remain active.

## v0.2.8 — 2026-10-17

Refuse changing batches whose final pairs on any master exceed twice the font's
positive finite units per em: FontLab's load pipeline otherwise clamps them and
adds a mark. Signed32/history validation remains; no values are silently clamped.
Valid corrections/deletions of existing extremes work; true no-op stays untouched.

Add Copy Between Masters, Pair Editor, Scale Values, Round Values and Remove
Small Pairs through shared lazy App plans, snapshots and native batch writing.
Preflight all masters/classes/glyphs and whole-unit history before any mutation;
retain explicit zero, unrelated pairs and active master. Failed reads/stale
previews disable Apply and offer Refresh. Invalid cell text never enters the
staged map; other valid edits remain. All35tools pass280native workflows,85
preservation/history checks,82safety checks,32writer controls,7actual-export
checks andClose35/35. Archived sources stay unchanged; full migration stays open.

## v0.2.7 — 2026-10-17

Add lazy native kerning snapshots, class indexes, effective layout and a shared
inspection panel for five Kerning tools. Explicit values retain zero/absence;
proof uses actual native fallback and complete outlines. All30 Scriptmix tools
pass247native workflows,50preservation/history,52safety,7save-dialog checks and
Close destruction. App359source/55installed-helper tests and artifact audits pass.

## v0.2.6 — 2026-10-17

- Add shared Names panels, complete refresh guards and exact/additive Font
  window selection access for five practical inspection tools.
- All 25 Scriptmix tools pass 216 native workflow checks, 40 complete font/history
  checks, 44 safety checks and native Close destruction on FontLab 9.0.9784.
- App 350 source tests and 46 installed-helper tests pass on Python 3.11.
  Wheel/sdist source equality, licenses, NOTICE and privacy audits pass.

## 1.2.28 (2026-11-16)

- Share lazy Names panel/table/lifecycle and complete-refresh selection guards.
- Preserve five original tools, Unicode/language data, live outline proof,
  copy, keyboard and row actions; keep/add selection validates all names first.
- Retain all source originals; native verification of this batch is pending.

## v0.2.5 — 2026-10-17

- Add lazy shared scripting panels, guarded dialog lifecycle and stale-font edit
  checks for 20 practical Reports, Font Info and Features tools.
- Preserve ordered feature source through Fontport, validate metadata edit plans
  before writes and retain Apache-2.0 source notices.
- Verified on FontLab 9.0.9784: 183 tool workflow checks, 30 complete preservation,
  Undo/Redo and saved-file checks across five editors, 12 safety checks and native
  destruction of all 20 dialogs. Export choosers pass separate native checks.
- Host-free App suite: 347 passed. Wheel and sdist payload/license audits pass.

## v0.2.4 (2026-10-16)

Font info editor gains structured OS/2 weight/width class, Panose and stem-snap fields (key master), with exact integer parsing; the automatic follower skips fonts with unfinished script edits (never discards them); requires fontlab-fontport >= 1.0.2. Native structured-field and follow checks on installed wheel and sdist (FontLab 9.0.9783).

## v0.2.3 (2026-10-16)

Edited existing glyphs now reach open controls: the follower drops Fontport's cached glyph handles (invalidate or refresh) before each refresh, isolates per-font reload failures (closed fonts show their unavailable state) and keeps sequence selection across reloads. Code at 270d029; native follow-round10-src2 (FontLab 9.0.9783).

## v0.2.2 (2026-10-16)

Font Info: font-info text fields, wrap lines with resize reflow, Vanilla example, automatic following of FontLab changes in every editor (bounded coalescing, shared feedback suppression, staged edits preserved, explicit Reload), negative-advance hit-testing; Fontport pin v1.0.0. Native follow checks on installed wheel and sdist (FontLab 9.0.9783).

## 2026-10-15 — completed checklist (moved from TODO.md)

- Record source provenance and baseline.
- Implement complete package migration and scoped modernization.
- Verify wheel, sdist, isolated installs and privacy.
- Verify relevant native behavior in FontLab.
- Add named direct native controls and owned custom UI composition.
- Verify removable Preview/Glyph drawing with native bitmap/SVG primitives.
- Pass review and scoped fixes.
- Complete all three project iterations.
- Push, tag, release and verify assets.

## 2026-10-16 — batch child supervision (616756f, review round 5)

- The batch child takes its jobs from a spec file (stdin is /dev/null), gets an
  allowlisted environment and is supervised by batch_worker.supervise
  independently of the panel: collected after close, parent or own-widget
  destruction, terminated then killed, capped at 16, stdout closed and scratch
  removed on every path. Output is read in bounded slices (64 KiB, 64 rows per
  poll); malformed output stops the run visibly. External interpreter setup is
  documented in examples/font_transform.py.
- Evidence (test results): r5-repro-59f8ff4.log
  (16 failures before), ./test.sh 206 passed; artifacts-616756f (Twine, privacy,
  70 module byte checks, extracted App 204 + 2 skips on 3.11, Fontport 366);
  native ui-b09-r5src6 and r5-b09-616756f-{wheel,sdist} on FontLab 9.0.9783:
  20 ms timer worst gap 22.1/21.5 ms, dispatch worst 1.2/1.3 ms, close under
  1 ms, stubborn child killed (-9) and released.

## 2026-10-16 — verified kerning editor (moved from TODO.md)

- kerning editor (7e45fb3) with Fontport d1dd578: source tests pass; paired
  wheel/sdist pass Twine, privacy audit, 49 installed-module byte checks and
  extracted tests (App 155 + 2 expected skips, Fontport 206). Source, installed
  wheel and installed sdist native runs pass on owned documents: four key
  combinations, zero vs absent, exception over group fallback, Delete restoring
  fallback, refusals with unchanged history, first Undo/Redo, preview/toggle,
  keyboard, lifetime, closed document, VFJ reopen. Documented contract:
  fractions refused (host history rounds them); view refreshes on Reload.

## 2026-10-15 — application and UI layer

Pythonic host structure and static shim, driven by what the other workspace packages
need (TypeRig `Automat` status-tip codes, glyport menu lookup, aidus-code docks,
examples' `fontlabapp.qt.widgets`, echopy/docs static typing).

- Host-free naming rules (`fontlabapp.core.menu_names`) with deterministic collision handling.
- Read-only live capture of menus, QActions, docks, toolbars, widgets and the action
  catalogue under the Remopy limits; owner-specific dynamic menus dropped.
- Runtime tree `app.menu`, `app.actions`, `app.panels` with reprs, `dir()`, checked
  state; disabled actions raise; attribute access never triggers.
- Native verification: read-only (re-run 2026-10-15 at 772f193: shim-vs-live 788
  names, 0 missing, no fonts open; retained native results) and a harmless-trigger check in a
  no-document session.
- Shim generator `fontlabapp.core.shimgen` and `generated/echopy/fontlabapp_shim/`
  (.py facade, .pyi, capture, provenance), available to peer packages.
- `ApplicationUI.updatePanels` wiring fixes; de-duplicated `Application` message
  formatting.
- README, CHANGELOG and WORK updated. Tests: 96 passed.

## v0.2.1 (2026-10-16)

Clean-room FontLab application/UI layer : font UI controls (live and detached models, block editor, sequence view, batch panel in an isolated Python process with supervised children), GC-guarded native widget enumeration, shim generator; native checks on installed wheel and sdist (FontLab 9.0.9783). Source and release reviews passed.

- Guard PythonQt native widget-list conversion in host panel lookup, ApplicationUI
  discovery and Preview/Glyph views with cyclic GC disabled; restore the caller's
  GC state in `finally`, including on conversion failure. Reuse the top-level
  widget snapshot when filtering. Add success/error regressions with GC initially
  enabled and disabled, and remove the stale README test count.

- 2026-10-15 : new optional extra `unicode` (unicodedata2>=15); removed the
  `mdx_steroids.keys` detection (not on PyPI), so keys always use `pymdownx.keys`.
  DEPENDENCIES.md rewritten from the dependency re-evaluation.

- Review fix round 4 : batch work moves to a separate Python
  process (python= or $FONTLABAPP_BATCH_PYTHON, 3.11+ with fontlab-fontport),
  so it never holds FontLab's GIL; the GUI poll only reads a non-blocking pipe.
  Validation stays in FontLab before any spawn or write; Cancel creates a
  sentinel file checked before each font; close terminates a child that
  ignores it after GRACE_SECONDS; pending reapers are capped (16) and logged.
- Review fix round 3 : BatchPanel.close cancels and returns
  at once; it detaches the panel from its parent, hides it and leaves deletion
  to a Python-owned reaper timer that lends the worker GIL slices and deletes
  the widget after the worker exits (also on parent destruction). The worker
  sees only a threading.Event and plain data (batch_worker.py). Measured
  Python timer gaps over four native runs: 43-50 ms median, 151-1,069 ms worst.
- Review fix round 2 : BatchPanel.close (and parent
  destruction) cancels and joins the worker in 30 ms GIL slices before widget
  cleanup. Docs state the measured batch latency (48 ms median, 232 ms worst
  timer gap) instead of a bound, and the FontLab feature-code reopen limit
  fontlab/fl#8510.
- Review fix round 1 : batch work runs on a worker thread
  with GUI-thread polling, validates before any work and cancels before the
  next font; settings keep full matrix/intensity precision (exact text
  field beside the whole-percent slider); Apply keeps the document's line
  ending and refuses mixed endings; now edits Fontport's structured
  blocks (Prefix plus each feature tag, Add/Remove feature, one set_blocks
  Apply) because native FontLab accepts no arbitrary whole-text split; refreshes on FontLab's Undo/Redo
  actions (disconnected on close); the `test` extra installs Fontport (git
  source) so editor tests run instead of skipping.

- Add the original explicit-model groups editor with group/member lists,
  preview, create/rename/delete and deduplicated membership actions. Fontport
  stages and validates complete mappings; native errors and dependent-pair
  refusals stay visible. Verify actual readback before success callbacks.
  Source native actions, first Undo/Redo, keyboard, read-only/empty states,
  nested lifetime and VFJ reload pass. Both final installed wheel/sdist pairs pass
  all native phases and117 earlier UI checks each;44 installed modules match
  wheel bytes. Full native-name/both-sided/legacy boundaries remain open.

- Add original controls: `designspace_panel` (synchronised axis slider and
  numeric field, reset to defaults, sources/instances list, unavailable sources
  with reasons, instance locations never labelled as masters),
  `transform_editor` (affine matrix fields, intensity 0–100%, enabled, compare
  overlay, separate view/transform resets, inspectable script, explicit
  non-overwriting settings save/load; unavailable methods listed) and
  `batch_panel` (explicit sources/destination, one run at a time, one job per
  timer tick, progress/log, per-item failures, cancel, validation before any
  write). Fontport owns Recipe/Designspace/BatchRunner. Native dev receipt
  ui-b09-dev2 used an uncommitted Fontport snapshot; pinned re-run pending.

- Add the original `features_editor`: multiline feature text, dirty state,
  Apply (one `features.apply` call with exact readback) and Revert; no compile
  action, text is never executed. CR/CRLF display as LF and are reported.
  Native detached-model receipt covers Unicode, staging,
  malformed text, CRLF, real key press, lifetime; document-backed Undo and VFJ
  persistence wait for Fontport's feature backend.

- Add the original `kerning_editor`: filtered explicit pair list, left/
  right/value fields, Apply/Delete/Reload, explicit versus effective (group
  fallback) values, and a pair preview with the Apply-kerning toggle. Fontport
  stages and validates each batch; one callback per accepted edit. Integral
  values display without a fraction (native Undo can restore -0.0). Fractional
  values are refused by the native backend with no write. Optional `[fontedit]`
  requires Fontport 0.1.1.dev19+. Source native receipt:
  four key combinations, zero vs absent, exception delete restoring fallback,
  refusals with unchanged history, first Undo/Redo, keyboard, lifetime, closed
  document and VFJ reopen.

- PLAN/TODO audit: staged controls at7f23668 pass source132tests and
  independently installed wheel/sdist native Apply/Revert, validation focus,
  Unicode, first Undo/Redo, VFJ reload, accessibility and lifetime. Live
  document preview/closure is also verified. Exact one-history-row behavior,
  unset optional native metrics and other editors remain open; full UI not complete.

- Add the original staged `font_info_editor`: separate text, integer,
  metric, version and multiline note/copyright controls, pure Fontport batch
  validation, field focus on errors, explicit Apply/Revert and one accepted
  batch callback. Repeated close and native parent destruction release owned
  callbacks. Closed documents show safe diagnostics; models without batch
  support are read-only. Optional `[fontedit]` requires Fontport 0.1.1.dev14+.
  Native source receipts prove first Undo/Redo and VFJ persistence. Native
  metric clearing and the backend's extra history row remain gaps.

### Verified groups archived from PLAN/TODO

- Historical application work at7ab8c64: host-free stable naming and
  collisions; lazy menu/action/panel tree; privacy-safe native capture; static
  shim generation; updatePanels/message fixes; documentation and native checks.
  Scoped review approved after three rounds. These legacy source modules remain
  unchanged by the later UI additions; their completed checklist is archived.
- Original borrowed-model controls throughb6decb0: source118tests,
  independent installed wheel/sdist native checks, selection/keyboard/scroll
  fixes and scoped reviews approved. Final artifacts pass35checks each;
  prior113checks retained for unchanged controls. Native document integration
  and other editor workflows remain separate open work.

- review fixes: preserve actual selected glyph occurrences across refresh;
  add focusable keyboard occurrence navigation and clear replaced identities.

- Add original glyph sequence preview using the optional Fontport layout engine:
  Unicode or slash-name input, kerning, left/right direction, size, distinct
  repeated-occurrence selection and explicit missing-glyph indicators. No
  shaping is claimed; unsupported kerning is disabled with a reason.

- : original explicit-model font browser, glyph list/grid and glyph
  preview controls, with filtering, identity-preserving font selection/sorting,
  curve/component drawing and independent overlays. Add the optional fontui
  dependency extra. Explicit close, native parent destruction, direct deferred
  deletion and constructor failures release Python signal callbacks safely.
  This covers the foundational controls; the complete UI migration remains open.

- : `fontlabapp.core.menu_names` (English label to stable snake_case, collision
  rules), `fontlabapp.core.host` live tree (`menu`, `actions`, `panels`, `glyph_actions`;
  also on `Application`), and `fontlabapp.core.shimgen` generating the echopy static shim
  from a read-only capture (`generated/echopy/fontlabapp_shim/`). Verified natively:
  788 shim names resolve live; disabled-action error, checked state, path trigger
  and panel visibility round-trip in a no-document session.
- Fix `ApplicationUI.updatePanels`: Brush show was overwritten by its toggle; Panels
  List show/toggle pointed at Preview/Selections.
- `Application.debug/info/warn/error` share one formatter (behaviour unchanged, tested).

- Document native UI composition from external Python, including actual TypeRig
  widgets through the existing build callback.

- Let the drawing example select an available Glyph view without requiring it
  to be active or activating/closing user views.
- Add lazy native FontLab/Application.control with named font/glyph/action and
  full Output access, preserving raw native objects and legacy ApplicationUI.
- Add explicit native panel visibility, real Preview setters and Glyph-window
  canvas/pixel mapping, pan and zoom helpers.
- Draw removable transparent overlays on actual Preview/Glyph content with
  QPainter callbacks, pixel/canvas coordinates and safe lifecycle/error cleanup.
- Add owned registered docks, modeless dialogs and visible widget compositions.
- Verify installed native SVG/bitmap primitives, actual canvas mapping, native
  UI visibility, font/glyph/view/zoom restoration and temporary UI removal.

- Preserve all source functionality and license notices with migration hashes.
- Add hatch-vcs wheel/sdist packaging, lazy imports and source annotations.
- Keep pure utilities host-free and load native application context on demand.
- Fix optional Markdown extension typo and reset each parser conversion.
- Preserve malformed preference files and reject non-object preference roots.
- Support suffixed/long native version strings, correct UI child lookup and
  allow empty bytes through the existing JSON encoder.
- Verify source regressions and installed native hidden-widget capture.
- Make macOS hotkey stop safe before start and on repeated calls; clean up via
  documented Quartz functions and reject denied event-tap creation clearly.

## v0.2.0 publication verified

Actual publication and independent downloaded-asset verification complete.
Three full-project iterations pass; installed tagged wheel/sdist each457tests.
Downloaded native smoke covers all eight packages and both formats, including
production ACP/native UI and TypeRig composition. Exact release URLs, immutable
code commit and asset digests are in RELEASE.md. This follow-up changes only
completion evidence; release code and tag are unchanged.

## report scripting helpers

Added host-free `fontlabapp.core.scripting.current_package(expected_id=None)` and
`select_glyphs(names, package_id=...)` for modeless report scripts. Native access
is lazy; stale/missing fonts and unknown names fail before selection is cleared.
Selection returns actual names in font order and calls native UpdateAll. Six
owned-double tests cover null/missing/stale fonts, duplicate Unicode names, empty
selection and host errors. No new dependencies; native verification pending.

## shared script dialog lifecycle (2026-10-17)

Shared `fontlabapp.core.scripting` helpers handle guarded Python callbacks,
identity-checked registry removal, explicit native close handling and deferred
widget deletion. All eight Reports use them through `fly.ap.core.scripting`; CSV
passes its owned chooser and Live Glyph Info its timer. No new dependencies.

Native acceptance passed on FontLab 9.0.9784 using the installed wheel:
all eight original scenarios, 68 independent checks, and actual Close-button
native destruction for every dialog. Registry cleanup and host import-state
restoration pass. The old immutable source released its registry entry but
remained native-live while a wrapper was retained; the new source destroys it.
App 315 tests, Scriptmix 55 tests and 11 installed-helper tests pass; all 47
production files match wheel bytes. No owner site-packages install or new tag.

## complete Font Info sources (2026-10-17)

Migrated all six Font Info tools with full original UI/data and mutation paths.
Preserved original KEY/registry interfaces and all eight existing Reports sources.
Applied shared fly aliases/current-package access, guarded slots and deterministic
close/destruction. Full previews bind Apply to the original package, retain the
actual edit plan, refuse stale old fields and invalidate after failed previews.
Names/current-scope metrics bind their master. No glyph/layer notifications.

API review: Fontport NativeFontBackend.set_info_many and its info-backend tests
provide the measured checkInitHistoryState(0) + [package, mastersContainer]
history protocol, but not an explicit multi-master plan or rollback. App fontui
FontInfoEditor stages through Fontport and eagerly imports PythonQt, so it is not
a reusable script-core editing API. Added a bounded shared write_font_info helper
only in the App worktree, without dependencies. No-op plans produce no history;
whole plans validate first; native old values are retained for exact rollback.

Tests-first RED: Scriptmix initial test_font_info.py exited1 (14 failures; six
requested-tool existence assertions). App initial direct import errored during
collection; corrected explicit module import then two genuine missing-helper
assertions failed (exit1). App regression for normalized-empty rollback failed
against implemented code (None became empty text); fixed by retaining actual
native preflight values. Three native-boundary regressions then failed for huge
integers/null/surrogate text; bounded numeric comparison and Unicode validation
fixes pass. Rollback-failure fixture initially expected failure from a no-op
setter; corrected to apply a changing field whose restore setter raises.

Focused GREEN: Scriptmix21tests and App7tests pass. Full Scriptmix76tests pass.
Native runs, Undo/Redo, chooser interaction and full saved/reopened metadata
native proof remains pending.

## shared Font Info shell

Extracted the repeated six-tool layout, palette/heading/status/footer, guarded
callbacks, failed-preview invalidation, current-font/master checks, preview guard,
table rendering and default close into App's private FontInfoDialog. The public
`fly.ap.core.scripting.font_info_dialog_type()` loads it only when a tool runs; importing
scripting remains host-free. Per-tool controls, preview calculations, plans,
master-bound choice and mutation actions stay in Scriptmix. The glyph-order
modeless chooser, single callback/reuse and owned-child close cleanup are retained.

This shell adapts Apache-2.0 sample code. Its SPDX/provenance is retained in the
new source and NOTICE, with LICENSE-APACHE-2.0 and combined distribution license
metadata preserving the existing BSD-3-Clause/MIT terms. No dependencies added.

Tests-first: six Scriptmix AST assertions failed against copied safety methods
(exit1;22prior tests passed); App factory assertion failed before implementation
(exit1;three related fixture assertions also failed). The Apache-metadata test
then failed before metadata/provenance changes (exit1;fourpanel tests passed).
App tests exercise the actual shared constructor styling/layout/control wiring,
callback argument handling, safety/master checks, numeric table alignment,
missing-font/failed-setup disabling and separate-process lazy host-free import.
Scriptmix imports the actual shared base against owned native/Qt doubles and
retains all calculation/mutation/chooser tests.

Full Scriptmix tests:83passed0.11s,exit0. Full App/scoped Ruff/hash receipts and
updated source hashes are retained with the test results.
Native acceptance of the refactored bytes remains pending; prior v4
native receipts belong to the preceding production hashes. No native runs,
installs, commits or edits to Reports/canonical App occurred in this round.

## Native acceptance: Font Info shared UI and metadata edits

Fresh source tests328pass; installed
helper/shared-panel tests24pass with pytest source-path injection disabled.
All48production Python files match the wheel. Wheel and90-entry sdist contain
the shared module, all existing licenses, Apache2text and NOTICE, with combined
license metadata; scratch/archive payload is excluded.

Native FontLab9.0.9784 acceptance through the scratch-installed wheel:
14original workflows/153checks, four editors'24complete metadata/preservation/
one-Undo/Redo/reopen checks,12no-op/preflight/switched-font safety checks,8real
chooser export checks and actual Close destruction14/14. Loaded App modules
resolve to the installed wheel. Original paths/modules restore and all owned
fonts close. Native tests confirm that

No-op and rejected whole plans leave complete font JSON, native history dirty
property, Undo availability and current master unchanged. Stale Apply disables
all four editors and leaves both owned fonts unchanged. Raw reopen differences
are retained: regenerated window UUIDs and the expected family-title update
are checked separately; no font-design field is normalized.

The preceding shared-v1 chooser probe exceeded its3.5sstep deadline. Splitting
native sheet reject/configure/reopen into separate bounded steps fixed it.
Shared-v2 then exposed a verifier id-namespace mistake: MCP ids are package.fgId,
not package.id (mcptools_fonts.cpp743-749). Corrected the assertion; v3passes.
Neither failed verifier attempt required production changes or crashed the host.
Scriptmix-only export-status polish follows separately; App bytes are frozen.
No tag, publication or install into the owner's FontLab environment.

## 1.2.28 (2026-11-16)

Add a lazy FeaturesDialog extension of the existing FontInfoDialog shell.
Add current-font/source/reference-bound feature reads/writes that reuse the
existing Fontport NativeFontBackend and its complete native history checks.
Preserve no-ops and current master, notify no glyphs, and report possible partial
changes on native failures. Native acceptance remains with the native verification.

 review fixes: share host-free suffix/FEA calculations, document concrete
row contracts, and load the Feature Code Viewer from exact ordered VFJ source
instead of native index iteration/synthesized prefix. Native rerun pending.

## Native acceptance: six Features tools

The implementation adds shared pure calculations and useful typing/docs.
Native v1 additionally exposed blank feature bodies in the viewer. Fix1 review
passes: host-free App feature_code calculations are shared through fly; viewer
uses exact persisted prefix/ordered sources rather than raw native iteration.

Fresh Python3.11 source347App13.02s/110Scriptmix tests pass; installed helper,
shared panel/writer and calculation tests43pass;50production files match wheel.
20provenance source/destination pairs match. Wheel56entries and sdist94entries
retain shared sources, licenses and NOTICE; ignored scratch/venv/archive payload
is excluded. Fontport v1.0.2 source confirms the required ordered API exists.

Native installed-wheel six-tool v2 passes30workflow checks,6Close destructions,
and Build's six full feature-only/preservation/one-Undo/Redo/reopen checks.
All20tool v2 additionally passes183workflow checks,30persistence checks across
five editors,12no-op/preflight/stale-font safety checks andClose20/20. Actual
App/Fontport source paths are asserted; App/fly/Fontport imports restore. Every
owned font closes and no host crash occurs. Screenshots of all six reviewed:
real alternate outlines, complete scrollable tables/source, working highlights.

Suffix clipboard
scenario is explicitly adapted to actual preview by policy; clipboard remains
native-unverified. All20-v1 reached20workflow/5editor-persistence passes then a
cold native chooser hit FontLab's5sRPC deadline. This unchanged chooser already
passes independently on the same Scriptmix source hash (footer-v1); all20-v2
tests lifecycle/safety separately. Failure receipts retained; no performance
claim or speculative source fix. Feature-source mutation does not compile or
prove shaping: test generated code in FontLab's Features panel.

Full archive migration/cleanup, further practical and broader scripts,
package cleanup, new reporters and docs/finalreview remain open. No original
source removed, owner environment install, publication or release tag.

## Names review fix 1

Fit complete Character Info outlines including tall accents and side overhangs
inside the padded proof area while keeping baseline/labels/system proof.
Centralize exact Font window selection reads and correct character-list docs.
Host-free geometry regression passes; native fix rerun remains pending.

## 2026-10-17: Names native acceptance

Independent source review and fix review pass. The corrected native Wacute
screenshot shows the complete accent inside the outline frame; tall-accent and
side-overhang geometry regressions pass. Original constant expressions, presets
and signal callbacks match all five source tools. The shared shell supplies the
per-script heading label and lifecycle.

The installed App wheel passes the combined 25-tool run on FontLab 9.0.9784:
216 original workflow checks, 40 full preservation/history checks, 12 editor
safety checks, 32 switched/closed selection checks and actual Close destruction
for all 25 dialogs. All owned fonts close and App/fly/Fontport imports restore.
The Names checks compare every saved font/format field and dirty/Undo/master;
owned workspace UI changes are recorded separately. The live timer stops.

Fresh Python 3.11 checks: App 350, Scriptmix 151, installed App helpers 46.
All 25 source/destination hashes pass; the prior 20 mappings are unchanged.
Wheel 57 and sdist 95 entries contain 51 byte-identical source files, complete
licenses and updated NOTICE; private paths and scratch payloads are excluded.
The source and native results retain the
source/fix reviews. Clipboard and chooser timing have no new native claim.
Full remains active; no archived input is removed.

## read-only kerning implementation (native acceptance pending)

Add Classes Browser, Compare Masters, Pair List Browser, Missing Pairs and Text
Preview with every original control and original registry/class interfaces.
Share the lazy panel shell, guarded callbacks, validated selection, all-master
explicit pair/class reads and effective native kerning layout through App.
Preserve explicit zero versus missing pairs, numeric sorting and shown-order
UTF-8 CSV. The owned modeless chooser reports pair count and basename in a
wrapping status label. Proof fits complete transformed ink with actual advances
and native class fallback; paint and cleanup failures are contained. Invalid
or switched-font snapshots refuse selection, export and Copy. These five are
read-only; Exceptions Finder and Pairs From Text remain later editor work.
No native acceptance, publication or archive-removal claim in this milestone.

## Kerning review polish

Clarify Missing Pairs data types/coverage and Text Preview empty-state docs without
changing behavior. Make the new public work-log commands portable and retain exact
private receipts separately. App source remains identical to the native-tested wheel.

## 2026-10-17: Kerning native acceptance

Source and scoped fix reviews approve. Five kerning tools pass 31 independent
native workflow checks, ten complete saved-font/history checks, eight stale
class-selection checks, seven actual chooser/export checks and Close 5/5.
Screenshots show real wrapped accented outlines, native kerning positions,
master flags, class members, coverage and a concise export footer. Original
constant expressions and signal callbacks match all five originals.

The combined 30-tool run on FontLab 9.0.9784 passes 247 workflows, 50 complete
font/preservation/history checks, 52 safety checks, seven actual save-dialog
checks and native destruction of every dialog. Five informational composite
notes are retained separately from test counts. Clipboard invocation/check is
explicitly excluded by policy; Copy remains host-free tested. Exact exported CSV
UTF-8/CRLF bytes match independently read MCP values in native table order.

Python 3.11: App359 and Scriptmix171 tests pass; installed App helpers55 pass.
All30 source/destination mappings pass; the prior25 are unchanged. Wheel58 and
sdist97 entries contain52 exact source matches, licenses and NOTICE, with private
paths/scratch excluded. Full migration and all remaining editors stay active; no
archived input or owner environment installation is changed.

## v0.2.18 — 2026-10-18 — complete guide panels

- Add complete Font Guides Panel, Grid Generator and Metric
  Reference Lines on the shared owned UI. Refuse unsafe automatic dependants
  before history. Safe edits restore complete fonts and prior Undo state.
  Native27original/21persistence/167controls/Close3 pass; all61prior tools pass
  on the same installed runtime. Artifact/source acceptance reviewed; fresh-tag
  acceptance follows release. Retain every original and the full original scope.

## v0.2.19 — 2026-10-18 — complete guide rewrite editors

- Add complete Clear Glyph Guides, Copy Guides Between
  Masters and Guide List Editor. Preserve retained native guide properties/hints,
  preconstruct whole batches and refuse unsafe dependencies/nonfinite cells.
  Native19original/21persistence/162controls/Close3 and prior64same-runtime
  regression pass. Current580App/756Scriptmix/263installed per artifact pass.
  Source/artifact/native acceptance reviewed; independent fresh-tag follows
  release. Retain every original and the full original scope.

## 1.2.28 (2026-11-16)

- Expose stdlib-only `fontlabapp.qt.safe.qt_list` with the existing GUI-thread
  documentation and exact GC restoration algorithm. Keep `_qtsafe.qt_list` as
  the same function for existing consumers.
- Add cold-import, API identity and GC-toggle/error regressions. Source956tests
  pass; both isolated artifact installs pass62focused tests; changed modules
  have100%coverage. Native execution and downstream Glyport adoption are pending.

## 1.2.28 (2026-11-16)

Add a practical Apache-2.0 Pedro Arilla tabular-width report through shared App
and Fly. Compare actual selected active-master advances exactly; retain original
row statuses, counts and time heading. Use a modeless read-only snapshot with
Refresh and owned Close; diagnose empty, missing or changed sources. Preserve
owner Output content. Source/consumer/artifact checks pass; native acceptance
and release remain pending. This is additional to the130sample inventory.

### Unreleased correction — tabular selection carrier and scan deadline

Bind selected names to the active FontGate package id before any width reads.
Share one two-second monotonic deadline across complete selection/width passes
and final checks. A timed-out report clears its results with a diagnosis; it
never truncates rows. Preserve existing zero-argument selection helper behavior.
Native calls remain non-preemptible; checkpoints diagnose overruns on return.

- Fence retained tabular-report Close callbacks after Close or native destruction; three offscreen regression cases and rebuilt candidate artifacts pass. Native acceptance remains pending.

## 2026-10-19 — test results detached reports candidate

Add host-free reports.format_report/show_report and lazy _report_dialog on the
existing NamesDialog owned lifecycle. Strict Unicode JSON snapshots use a
read-only nonmodal editor; Close, replacement and parent destruction release
callbacks. No active-font/Output access. Unreleased API; native acceptance pending.

Direct destruction also disconnects owned callbacks; released callbacks are inert.
Failed initial show releases the new window.

- Add the reviewed lazy rescued-example dispatcher and explicit retained GetGo namespace boundary; original script compatibility remains individually pending.

- App owns generic VanillaSession lifetime; Fontport keeps an identical-class compatibility import. Existing optional Glyport factories and cleanup behavior are preserved. Native/release acceptance remains pending.

- Make the existing batch destruction test deterministic for an already-exited child; retain live-child cancellation and exact cleanup checks.

## 1.2.28 (2026-11-16)

Extract host-free file lookup, high-DPI sibling discovery, bounded macOS PDF
conversion and injected Qt raster/SVG rendering into image_resources. Caller
adapters retain localization order and Cocoa values. Preserve source MIT notice;
no required Glyport/Fontport dependency or native import is added. Native pixel
and lifetime acceptance remains pending.

## 1.2.28 (2026-11-16)

Extract ordered graph/tree recording, node/connection records, reference/ID
checks and versioned JSON serialization into host-free ui_graph. Frame data
is an opaque mapping; foreign frame parsing and layout resolution remain in
compatibility adapters. Preserve source MIT attribution; no required reverse
dependency or native import is introduced.

## 1.2.28 (2026-11-16)

Adapt Simon Cozens' MIT Recipe Dumper into shared App logic and a typed lazy
Fly menu. Preserve ordered/duplicate layer and component records, mixed layers
and original line endings; do not synthesize offsets or transforms. Native
capture currently binds Font-window selection on the active master, with stale
source/carrier/deadline guards. The owned modeless report supports Refresh,
clear failure diagnosis and Close. Original editor-tab/repeated/multi-master
selection and native acceptance remain open; the130sample count is unchanged.
Angularizzle remains an explicitly unfinished named priority requirement.

## 1.2.28 (2026-11-16)

- Port the original130step cubic lookup, linear subdivision, duplicate and
  detail behavior without importing Glyphs or touching native fonts.
- Diagnose invalid/nonfinite/coincident geometry and excessive output before
  returning a partial plan. Keep collapsed counters explicit.
- Preserve upstream MIT terms and README Apache-2.0 declaration. The complete
  original preview/Process/Cancel/native workflow remains unfinished.

## 1.2.28 (2026-11-16)

- Add the original Min plane/Keep detail/Process/Cancel workflow with ordered
  repeated selections, first-master targets, saved defaults and bound previews.
- Refuse stale or unsupported source plans before history; retain diagnosed
  recovery state after late native failures. Native acceptance remains pending.
- Restore actual overwritten target paths on Cancel, repairing the original
  cross-layer restoration defect. Closing keeps Process results.

The same candidate includes reviewed qt_dialogs shared primitives, preserving
the API required by the paired Glyport0.2.29dev-minimum consumer.

## 1.2.28 (2026-11-16)

Read actual ordered Font/Glyph-window layers through App’s shared selection
provider, retaining repeated editor slots and their layer choices. Compare
component reads and fence final selection/context before publishing. Native
qualification and complete font preservation remain pending.

## 1.2.28 (2026-11-16)

Share configure/exec/result/deleteLater in App. Glyphs input/file dialogs keep
raw argument/default/answer/cancel/filter policy in Glyport and delegate only
the owned execution edge. Vanilla message/file helpers use the same boundary.
No signals, application loop or native acceptance is introduced.

## 1.2.28 (2026-11-16)

Use the shared Font/Glyph-window selection reader. Preserve editor repeats and
each slot’s layer choice; compare exact actual advances against the first
occurrence. Fence source/selection/context under one deadline before reporting.
Native selected-layer order/focus/preservation qualification remains pending.

## 1.2.28 (2026-11-16)

Add original29abbreviations, ordered advisory naming checks and whole-word
style-link calculations. Preserve explicit Regular links and bold-only fallback.
Original panels, native instance field mapping/writes, saved/exported results
and native acceptance remain pending.

## Point Counter candidate

- Add licensed Slobzheninov Point Counter with complete foreground-layer/repeated-selection reports and explicit quadratic counting repair. Native acceptance remains pending.
- Share recipe, width and point report Refresh/Close ownership in one App panel. No new dependencies.

## Linear layout backend candidate

- Share the existing binding-free required/weak linear solver in App. Vanilla syntax, intrinsic hints, nonnegative-size adjustment, geometry writes and compatibility errors remain in Glyport. No new third-party dependency.
- Preserve ordered elimination, free-variable defaults, tolerance and malformed-input errors; translate only generic inconsistent-equation errors at the foreign boundary. Native artifact regression remains pending.

Add all-open-font/all-master Vertical Metrics Reporter, eight exact stored values, unset/zero distinction, complete-source fences and owned Refresh/Close text panel. Native acceptance pending.

seven complete random-proof generation/tab workflows; preserve all4,991dictionary entries, draw order, casing and whitespace. Explicit current-font repair; native acceptance pending.

share native text-tab sender ownership, rendered-block lookup and existing activation contexts in App. Preserve App and Glyphs caller-specific font/deadline/restore/error policies. No new dependency beyond the reviewed App API floor; native regression pending.

eight selected-glyph context proofs with exact order/repeats/contexts/blank lines, explicit native named symbols and a fresh-tab writer fence. Native qualification pending.

immutable all-master alignment-zone staging, complete source table
parsing/add/remove/o-O Suggest and ordered no-op-aware Apply plans. Invalid input
retains previous stages; raw source numbers are preserved. Native capture/writer,
modeless UI and final workflow acceptance remain pending. No dependency changes.

Complete owned modeless Alignment Zones panel, per-master staging,
row diagnostics/removal repair, source checks, ordered batch Apply callbacks,
complete-result fencing, no-op/reentrancy guards and Close/destruction cleanup.
Native adapter/history/persistence and practical-menu acceptance remain pending.

Shared script completion owner for Names/Proof/Masters/Font Info and
detached reports; standard completion runs existing subclass Close cleanup.
Snapshot callbacks and late results are fenced/released. Direct-destruction hooks
use the completion owner instead of disconnecting dead self-emitter signals.
Native PythonQt/workflow/preservation acceptance remains pending.

explicit immutable per-row source identity/metadata now travels
through complete zone staging and the actual modeless table, including duplicate
rows, invalid-cell repair, sorting, master switching and repeat Apply. Fresh
post-write identities bind only new rows; captured or removed keys cannot be
recycled. Native capture/writer/history/persistence acceptance remains pending.

Zone capture: direct native all-master zone capture with raw values and
ordered native guide-buffer fences, two complete passes, source/domain checks,
deadline checkpoints and starting-master restoration. Native three-argument
buffer serializer is used without system clipboard access; no binary parser or
new dependency. Actual native read/serialization preservation and the complete
Apply/history/cache/persistence adapter remain pending; no menu promotion.

-read correction: require the corrected three-argument serializer declaration before any master switch/call; legacy arity macro defect tracked in Fontlab/fl#8554. Accept immutable bytes or QByteArray data without decoding. Native qualification and complete writer remain pending.

immutable complete native write preflight checks every raw baseline,
master/guide domain, normalized row and retained payload identity before returning
operations. Source-order effective masters, ascending construction rows, explicit
editable removals and untouched guide IDs are retained. Complete current-capture
fence and native-kind diagnostics prevent silent kind/label changes. No native
allocation/history/writer implemented by this pure layer; complete workflow remains pending.

Complete guarded zone preparation returns owned native handles and
exact payloads after full preflight and source/graph fences. Corrected serializer
and one-argument decoder profiles are required. Retained roots use native buffer
round-trips and restoration witnesses; new rows use source-verified constructors.
Known source/root/node/marker aliases and native constraint deltas are refused.
No attachment/history writer or practical menu; native isolation, opaque metadata
coverage, read/counter preservation and complete native acceptance remain pending.

Complete Text Simplifier candidate with regex-class filtering,
input/read-only output/character fields, autosave/reopen, selective Reset,
original-font optional proof tab, resizing/geometry and owned completion.
Native PythonQt/settings/tab/whole-font-history qualification remains pending.

Complete selected-master Tallest and Shortest and all-foreground
Highest & Lowest Glyphs candidates share exact extrema/native capture and new
per-symbol layer tabs. Stable ties/repeated winners/zero/large coordinates are
preserved; missing layers are never created. All-layer coordinate results use an
owned panel with Run Again and survive a diagnosed tab failure. Shared NamesDialog
subtitle colour now follows palette changes. Native qualification remains pending.

share binding-free one-axis stack distributions in stack_layout.
Cocoa/Vanilla adapters retain their enum/coordinate/natural-size/hidden/ownership
policy. Existing nonempty finite geometry is exact; empty helper input returns
an empty result. Fixed/equal/proportional/spacing/centering, clamping and list
identity are tested. No required dependency or native qualification added.

Complete Why You Not Compatible? report candidate compares every
adjacent foreground-layer pair for each selected occurrence: ordered path/node
counts/types plus anchor/component name sets. Keep repeated groups, master-first/
auxiliary order and source messages; fix foreign first-glyph labels and global
path suppression, and sort displayed name sets. Owned Refresh/Close replaces
Output writes. These source checks are not an export-compatibility certificate.
Actual native topology/order/read/cache/font/history/reopen acceptance is pending.

## shared key routing

 shares the complete handled-key acceptance/unhandled explicit-native-base mechanism through host-free App.key_events. All five existing consumers remain: App glyph browser and sequence canvas, Glyport Cocoa stepping field, Vanilla list and Vanilla window. Each keeps its original key/owner/callback/error/cleanup policy. No super protected-slot lookup or new widget inheritance layer.28newApp/12newGlyport tests pass; complete source suites2033App and2996Glyport/4existing skips. All6whole changed production modules exceed80%statements/branches,zero exclusions. Five real offscreen Qt6 controls pass; this does not prove compiled PythonQt/native-font/history/reopen acceptance.

## bracket-layer report and proof candidates

Both Reset Type Studio source workflows now scan the complete current font's
foreground layer names and transitive component dependencies. Shared App core,
full-source observations and report/tab routes preserve both original groups.
The report explains overlap and counts a distinct total; the proof sorts names
and uses explicit glyph symbols, avoiding orphan slashes. Apache attribution
and the full licence are retained. Source originals are never executed.

Owned Qt6 controls and host-shaped boundary tests are offline evidence only.
Native PythonQt, dependency/cache/read preservation, complete saved-font/history
and actual symbol/layer mapping remain pending under . No native acceptance,
canonical merge, live install, tag, release or site publication is claimed.

## complete part2 glyph sorting/filtering candidates

Adapt both basic/custom part2 source/proxy workflows to the complete current
font's names, all Unicode assignments and local modification dates. Shared App
Table/Query, Qt controls and owned model lifetime keep all three pattern modes,
independent case switches, Basic key-column/native QRegExp, Custom first-two-
column OR/inclusive dates/angle-tail ordering, both views and modeless Close.
Raw demonstration records are replaced; initial dates are unrestricted and date
limits explicit. Custom's ignored column control stays visible and disabled.
Two immutable source-index identities now route to practical Models commands.
Original bodies/resources and all other menus stay untouched. Distinct part3
contracts remain pending. Qt5/Qt6 and metadata-shaped tests are offline evidence;
native PythonQt callbacks/read/cache/font/history/save/reopen and publication/
integration/release gates remain open under . No original numerator changes.

## complete part3 typed-date workflows

Both official part3 Basic/Custom models now adapt complete current-font metadata
through shared App controls. Typed QDateTime cells, locale short-date matching,
native QRegExp syntaxes, inclusive calendar-day limits, case-sensitive email-token
text comparison and original ISODate ordering remain distinct from part2. Data-
specific demo filters become full-font snapshots with explicit optional limits.
Read-only models, Refresh/refusal and all completion routes keep owned lifetime.

Tests exposed two timestamp-reader defects: displayed local dates assumed an
already-local stamp and the source fence lost within-second changes. A local
copy and native epoch milliseconds now preserve the intended observations. An
optional immutable epoch channel keeps exact typed-cell instants (including DST
folds); Basic retains millisecond ordering, Custom retains its source comparator.
No new native font API, writer, original-source execution or live install is used.
Standalone tests do not establish actual PythonQt/font/cache/history/persistence
acceptance. All original/native/integration/distribution/publication gates stay open.

## shared message-box ownership candidate

Generic custom-button/accessory QMessageBox execution, original-parent restoration,
modeless configuration/retention and hidden-box retirement now belong in App.
Glyport retains Cocoa NSAlert answer injection, style/button numbering/default
policy and Glyphs message text/title/button semantics. Existing Vanilla/Glyphs
modal/file helpers continue using the same shared module. Unreturned prepared
message boxes now delete on setup errors. Parent-restoration failure still
propagates before deleting a box with borrowed children; this preserves the
existing ordering and is not a claim of recovery from invalid native wrappers.

Requires reviewed unpublished App 0.2.56.dev0; normal candidate wheels must be
installed together. No live install or original/corpus execution. Full native
PythonQt ownership/modal/teardown and font/history/persistence regression,
integration/released dependency and all original goal gates remain pending.

 rendered Qt5 control exposed a narrow accessory field: the old fixed two-column span clips controls in QMessageBox layouts with more columns. Shared execution now spans the full native grid; a tests-first measured-width regression and retained before/after render cover the correction. Native PythonQt qualification remains pending.

## complete read-only Simple Tree Model pair

Both archived part2/part3 read-only tree entrypoints now show complete current-
font glyph metadata through a generic immutable App tree and injected Qt model.
Each glyph keeps font order, every Unicode assignment and its local modification
date; missing values stay explicit. Expand/collapse and cell selection are
read-only. Part2 retains fixed columns, noneditable EditRole text, row/column
status and File > Exit; part3 retains DisplayRole-only text and parent-item
column counts. Their separate editable-tree entrypoints remain outside this pair.

Source-specific synthetic outline/default.txt loading becomes structured native
metadata input, using the existing source-fenced reader. Capture and model
construction share one deadline. Refresh replaces the entire model and selection
owner; failure removes all results. Model virtual failures are contained and
obsolete callbacks become inert. All completion routes release owned resources.
The raw sources/resources are preserved and never executed or packaged here.

Requires reviewed unpublished App>=0.2.57.dev0 through Fly. Standalone Qt model
tester/view/lifecycle checks and ordinary artifacts do not establish PythonQt
virtual dispatch, native getter/font/cache/history/dirty/save/reopen acceptance.
Native acceptance, integration/distribution/release/publication and the full original
goal remain open. No new native API, writer or live installation is used.

## shared image presentation candidate

App.image_view now owns generic QLabel clearing, proportional-down, proportional
up/down, unscaled and stretched presentation, point-to-pixel rendering scales,
smooth stretching and display DPR normalization. It accepts an injected Qt
namespace, label and renderer; imports remain host-free. Glyport keeps NSImage
resource/size/retina/SVG/PDF behavior, Cocoa scaling enum/unknown fallback and
Vanilla image sources/alignment/placement. Both current Cocoa/Vanilla paths
share the helper. Source behavior, including zero natural/frame rules and error
propagation, is retained. No new widget or lifecycle framework is introduced.

Requires reviewed unpublished App>=0.2.58.dev0; native PythonQt/image/plugin/
font/history/cache/reopen regression, released dependencies, integration and all
original goal gates remain pending. No original/corpus body, live installation
or FontLab driver is used. Owned standalone Qt pixels are not FontLab proof.

## 1.2.28 (2026-11-16)

- Share eight programmatic callback suppression scopes through App.callback_guard; nested setters restore the prior state on all exits. Preserve unrelated Qt signals and existing Cocoa/Vanilla policy. Native qualification is pending.

## 1.2.28 (2026-11-16)

- Adapt the complete part2 Calendar Controls workflow to current-font modification dates through Fly and shared App UI. Keep all original controls; synchronize defaults/limits and repair dark date-surface readability. Preserve the distinct part3 source and all original bytes. Native qualification remains pending.

## 1.2.28 (2026-11-16)

- Adapt the distinct complete part3 calendar to current-font dates via Fly and App. Preserve every locale, seven week starts, source ranges/styles and independent first-Friday/May1 rules; clear stale owned marks. Share mechanics and lifecycle while retaining the full part2 policy/public paths. Native qualification remains pending.

## 1.2.28 (2026-11-16)

- Centralize exact signal connection tracking and reverse teardown in App for both Cocoa and Vanilla control bases. Preserve every callback/error/owner cleanup policy and unrelated listener. Native qualification remains pending.

## complete glyph-name completion pair

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
pending, as do every original integration/distribution/publication
gate. Source and artifact checks do not constitute native acceptance.

 visual acceptance caught the preserved part2 one-pixel completion popup. A tests-first content-width repair now applies the existing Qt popup-size calculation to both variants; key/focus/insertion policies stay distinct. Retain the initial candidate/renders and repeat final full/source/ordinary-install/Qt5 gates with artifact v2. Native qualification remains pending.

## 1.2.28 (2026-11-16)

- Add host-free DraftTree data for the pending editable-tree pair: stable occurrence IDs, complete subtree removal, global editable columns and bounded all-or-refuse argument validation. This is a data-only candidate; no editable-tree menu/window or native acceptance is claimed.

## 1.2.28 (2026-11-16)

- Add the complete injected-Qt editable-tree model interfaces with distinct text/QVariant policies, complete preflight, row notifications and global persistent-column remapping. Retain expanded row identities through column changes, with owned callback fencing. Both windows/menus and native qualification remain pending.

## complete editable glyph-tree pair

Implement both original editable-tree controllers over full local glyph metadata. Retain distinct sibling/child/column positions, text/QVariant values, header/default labels, part3 key sequences/mnemonics/separators, selection action enablement/status and ordinary delegate editing. Shared App model/view/editor/signal mechanics stage complete replacement views before releasing the current draft. Refresh refuses edited-draft discard; Reset Draft explicitly requests reload; capture/setup faults preserve the prior draft. Failed disconnects retain exact owners. Close button retries control/editor failures; terminal failures retain the destruction tombstone and use window Close. Every ordinary completion, parent destruction, constructor fault and queued callback is fenced. No original body/resource is executed or bundled. Requires reviewed unpublished App>=0.2.66.dev0 through Fly. Native PythonQt and full font/getter/cache/history/dirty/save/reopen, integration/distribution/docs/release/publication gates remain pending.

## resize-event extraction candidate

Share explicit native-base resize dispatch and dimensions forwarding through
App.resize_events. Preserve owner lookup timing, exception identity and foreign
Cocoa/Vanilla policies. Native qualification and released dependencies pending.

## 1.2.28 (2026-11-16)

Share the existing explicit Qt property-or-method read through host-free App qt_properties.value. Keep all four original callable paths, metadata, signatures, exception and caller policies. Glyport requires local candidate App>=0.2.69.dev0. Full source, ordinary artifact/consumer and standalone Qt5 gates are recorded in WORK.md; native FontLab and whole-project acceptance remain open.

## 1.2.28 (2026-11-16)

- Move the exact titled Box content-rectangle geometry mechanism to host-free
  App.content_geometry.fit_contents. Keep Glyport's old wrapper and all four
  callers, event/owner order, raw values and exception timing.
- Require candidate App>=0.2.72.dev0 for Glyport. Source/artifact/standalone Qt
  results are recorded in WORK.md; native and original full-goal gates stay open.

## 1.2.28 (2026-11-16)

- Integrate the exact named Qt property reader and Box content geometry helper,
  keeping original adapters, caller policies and cleanup unchanged.

## 2026-10-20 — contour selection candidate (native pending)

Independent Pedro Arilla adaptations add Select Contours, Select Small Contours and Select Partial Contours through shared App immutable plans and lazy selection-only transport. Preserve original path/node order, offcurve inclusion, cross-contour toggles and strict unsigned analytic area. Owned input UI diagnoses invalid/nonfinite/stale sources without clearing selection. Full original/native acceptance, including mixed selection transport outside a single displayed glyph, remains open. Apache attribution and complete terms retained.
## Glyph Spacing Worksheet pair (unreleased)

Independently implement both complete spinboxdelegate profiles through lazy Fly/App entrypoints. Preserve all four rows/eight cells, profile-specific storage/headers/frame/sizing and native delegate events. Add complete selected-layer baseline/candidate reports, atomic Refresh Selection, exact Reset Factors and owned Close/error/destruction handling. No font writer or original body/helper execution. Native FontLab/PythonQt, complete getter/cache/history/save/reopen acceptance and publication remain pending.

Original identities/resources and other menus remain preserved.

## complete glyph-name pattern laboratory candidate

Retain the complete clean-room Pattern Matching Inspector as a useful modeless glyph-name rule authoring tool: editable native histories, four QRegExp syntaxes, case/minimal matching, escaped literals, UTF-16 positions/lengths and all captures. Add complete captured glyph names and ordered batch capture inspection through existing owned capture mechanics. Share only injected native Qt evaluation, controls and owned lifetime in App. Drafts remain local; no font/selection/history/preferences/file/Output writer or live install is added. Source/artifact/standalone checks are distinct from native PythonQt/getter/cache/history/dirty/save/reopen acceptance, which remains pending.

## 1.2.28 (2026-11-16)
Add first-master node compatibility counts/first differences and own-path SVG
commands with shared Refresh/Close panels. Fix original false-compatible cases;
retain unconditional Z policy and refuse unsupported whole reports. Native pending.

## 1.2.28 (2026-11-16)

Repair visible Small Contours closing through the native QDialog rejection path after owned cleanup. Close, its button, reject and Escape now hide the dialog and preserve native terminal signals before deferred destruction. Late retained close/reject calls remain inert. Shared dialog cleanup and other panel policies are unchanged. Standalone Qt5 regression covers the formerly hidden-only test gap; native qualification remains pending.

## Same Kerning Groups proof candidate

Implement the complete first-selected-glyph left/right peer proof, independent class maps, font order, explicit named peers, literal labels and original empty/singleton diagnosis. Native acceptance pending.

 repair round1 (.82): preserve first selected parent only, without layer or later slot/block-ID reads. Peer-side resolution is conditional on current groups; no-group diagnosis skips the peer inventory. Prior failures retained; 53 focused controls pass. Whole ordinary artifact/native qualification receipts: test results. Native acceptance remains pending.

## both elastic-node component dependency graphs (.83 candidate)

Retain the distinct part2/part3 force laws, fixed nine-node graphs, node/edge
geometry/paint, keyboard/wheel controls and timer policies. Current-font mode
reads all current-master glyph component names twice; repeated/cyclic/missing
references and isolated/unencoded glyphs remain in source order. Drag/shuffle
change only local coordinates. Refresh clears stale captures, Stop Motion stops
both timer forms, and actual drag state guards Close. No font writer runs.

Focused tests first failed with the missing new module; subsequent pure-model,
SDK-shaped rejection and actual standalone Qt widget tests pass. Exact expanded
commands/results and final ordinary artifact/whole-module evidence are retained
in test results. Existing source
bytes and both original hashes remain preserved. Native FontLab acceptance is
pending; no canonical write, live install, push, tag, release or publication.

 source-fidelity repair: retain part2's zoom-out branch for zero-y wheel
events and part3's unselectable nodes. Cover actual native viewport wheel
dispatch and selection behavior; prior candidate evidence remains retained.

Preserve part2 native ellipse type/shape/bounds/default pen/selection painting,
and native line/separate arrow pens and stacking order; part3 custom graphics
remain distinct. Compare selected/unselected pixels against native ellipse.

Read the part3 sceneRect through the existing Qt property reader, matching
PythonQt's declared property and the original behavior. Force cache refresh in
the real-widget property-profile paint test.

## 1.2.28 (2026-11-16)

Add both complete retained spinbox profiles as selected-layer metric/proof-cost
and whole-font revision worksheets. Keep all numeric/date/time/format controls,
precision and distinct special-value/stepping semantics. Local drafts only.
Source, actual Qt5, package and coverage verification recorded in WORK.md;
native FontLab acceptance remains pending. App0.2.88.dev0 is reserved.

### independent spinbox fidelity repair

The Detailed separate QTimeEdit now uses time-only initialization, preserving
the original hidden2000-01-01date and date-bearing range endpoints. Visible
time/cutoff behavior is unchanged. Explicit real-binding hidden-date and
minimum/maximumDateTime checks cover the source distinction. Earlier.88artifacts
remain superseded evidence; revision- and the combined.90artifact must pass
the complete checks before integration. No native FontLab call ran.

## 1.2.28 (2026-11-16)

Add both complete spinbox worksheets to the reviewed.89graph/kerning/pattern
union. Preserve all238prior App runtime files,33prior Examples menus and
106Scriptmix menus. Carry the independently reviewed N95time-editor hidden-date
repair from original.88commitf29d401. Native qualification remains pending.

## Close But No Cigar (.93 source candidate)

Complete ordered all-selected-parent/first-layer near-angle, horizontal/vertical
stem and six node-position checks, with explicit associated-master data and
strict original boundaries/exclusions. Shared modeless Refresh/Close report;
no Output/font/selection writers. Numeric cubic angle repaired; original curve
sampling/open wrap preserved. Tests, source/API calibration and ordinary
archive verification: test results.
Native acceptance, root review and delivery remain pending.

## Paired slider spacing-offset previews (.95 source candidate)

Both original slider workflows now preview left+offset/right-offset against
immutable selected-layer geometric margins with unchanged advance. Complete
controls and distinct native feedback remain; part2 initial orientation now
matches its label. No font writer; native acceptance remains pending.

## complete duplicate-anchor source candidate

Retain the complete original all-master duplicate removal workflow, exact first-in-layer/name-family/coincident policies, opening-selection scope and auto-layer skips. Direct original pin removals use preflight and one final layer/glyph notification; partial failures remain explicit for Undo. Native one-Undo, whole-font/history/dirty/save/reopen and lifetime acceptance remain pending. No native/live/canonical operation occurred.

## 1.2.28 (2026-11-16)

- Add both original reference-font character picker profiles with complete controls, drawing, insertion and explicit copy actions.
- Report full current-FontLab Unicode coverage, duplicate assignments and ordered proof occurrences; refresh clears stale results.
- Refuse isolated surrogate insertion/copy explicitly and retain owned signal/painter cleanup. Native qualification remains pending.

## 1.2.28 (2026-11-16)

Keep literal LF/PS identity on native paragraph character formats, so selected
cross-block replacement, typing and native deletion cannot move a separator
from the removed text onto an untouched paragraph. IME relative replacement
spans use the same literal inserter within one native Undo step and preserve
native preedit handling, event fields and Redo caret behavior. No font/user-store
migration or separator normalization is performed. Native qualification pending.

 Text Holder candidate (.91): full editable/resizable floating window; literal
Find first/highlight; UTF16-correct selected-or-whole replacement; Save stays
open, Save & Close, Ignore & Close; owned-path UTF8 persistence and window size.
Source/licence disposition retained; no original body is copied or executed.
No native calls or user-store validation. Native acceptance remains pending.

 geometry repair: preserve initial content500×400 separately from source
NS frame min500×400/max1200×800. Persist decorated frame sizes, restore client
sizes by measured chrome and map literal Cocoa origin(0,500) through complete
primary logical screen geometry/current frame height after first show; no
availableGeometry, DPR scaling or silent clamp. Prior .91 commits/artifacts
are retained in attempt2; no immutable final .91 freeze existed before repair.
27 focused actualQt5 controls pass; independent geometry controls pass bothQt5
andQt6. Native qualification remains pending on root final combined .92.

 final source fidelity: use normal Qt.Window with stays-on-top and explicit
title/system/close/minmax hints, matching original Vanilla Window/NSWindow
role rather than Tool/NSPanel hide-on-deactivation behavior. Preserve literal
button ampersands, full frame constraints, Cocoa origin and saved frame sizes.
Producer28 actualQt5 controls and independent32controls perQt5/Qt6 pass;
ordinary final .91 artifacts and full declared147/42 gates are bound separately.
Native acceptance remains pending on root combined .92, never claimed for .91.

 literal-Unicode repair revision4: frozen8433...candidate retained as failed
source attempt after independent NBSP/LS/PS Find/Save counterexamples. Added
text_holder_editor with undo-aware native block separator provenance; literal
block.text reads preserve NBSP/LS and distinguish PS/LF. Controlled text ingress,
local mime copy/paste, native Return, IME, selection merge and Undo/Redo preserve
literal text; original disk universal-newline read remains unchanged. Four
owned modules; complete App milestone scope grows148, Scriptmix stays42, no
sample denominator changes. Qt5/Qt6 focused51controls each pass at this stage.
Native acceptance remains pending on root combined.96 onto.94; .92 prep is
historical and .91 remains a private source candidate, never native acceptance.

 ownership repair revision5: independent pinned PythonQt virtual-return source
identified an ownerless Python-QMimeData lifetime seam (host binary equivalence
unproven). The copy factory now returns the explicit nativebase Qt-owned object;
its lazy source fragment is materialized before clear/setText, preventing a
later default MIME read from overwriting the literal payload. Constructor-route
tripwire is RED on revision4 source/GREEN now.52producer Qt5/Qt6 controls pass.
Revision4 ordinary archives eef6ac94.../305df303... and full148/42 gates remain
retained as a prior source attempt, with no immutable candidate promotion.
Fresh revision5 ordinary artifacts/full unchanged gates bind this repair.

## 0.2.109.dev0 — Text Holder Return history repair

Preserve native caret and selection after Return, Undo and Redo by assigning separator insertion format before native paragraph insertion. Match the platform paragraph action and preserve read-only and modifier routing.

## 2026-10-21 — shared deferred batch (.108 / Glyport .33)

Move only complete generic zero-timer coalescing and snapshot draining to App. Keep host registry, dispatch-depth refusals, foreign ownership and errors in Glyport. Initial missing-module RED retained; 38 focused controls and eleven exact original AST scheduling traces pass, including duplicates, reentrancy, equality/start/processor failures. Actual standalone Qt5 timer, nested-dispatch refusal, owned-widget destruction and drained-host collection pass. Ordinary wheel/sdist, full consumer and original-baseline coverage checks pass; native qualification remains pending.

## 2026-10-21 — shared table selection (.113 / Glyport .34)

Move complete generic Qt model-row selection and table-range selection/read
mechanics to injected host-free App.table_selection. Preserve distinct native
strategies, original order/duplicates/int conversion/extension/bounds, signal
timing and propagated errors. Keep Cocoa/Vanilla suppression, notifications,
bindings, data and foreign policy in Glyport. Regression-first focused cases,
original AST traces, full source/ordinary archives/current consumers and
unchanged original whole-module80/80 floors with zero exclusions are recorded
in test results. Native FontLab and
complete preservation qualification remain separate; no live/canonical/push.

## 1.2.28 (2026-11-16)

Combine complete DeferredBatch scheduling with both distinct Qt model-row/table-range selection mechanisms. Existing .106 workflows and all foreign ownership, callback, dispatch and lifecycle policy remain intact. Glyport requires matching reviewed App>=0.2.115.dev0, supplied by explicit local ordinary artifacts; public registry and native qualification remain pending.

## 2026-10-21 — shared editable choice commits (.116 / Glyport .36)

Move complete generic editable-QComboBox setup, Qt5 activation-overload
filtering, user-modified commit acknowledgement and programmatic text reset
to injected host-free App.editable_choices. Both Cocoa and Vanilla combo
paths use it; Cocoa text/path fields use the same existing commit primitive.
Retain callback/continuous/quiet scopes, datasource, conversions, completion,
public APIs, errors and ownership in Glyport. Regression-first source,
original full-method traces, actual Qt signals/lifecycle, ordinary wheel/sdist,
seven consumers and unchanged whole-module80/80 zero-exclusion evidence:
test results. No native/canonical/push.

## .118 Point Counter literal selection repair

Import complete Reza master-layer report on reviewed .106, preserving its prior workflows.
Reuse unchanged Text Holder literal editor read-only; preserve NBSP/LS/PS and UTF16 selections.
 RED, complete artifacts/consumer/coverage results are recorded after verification. Native pending.

Added complete Dangerous Offcurves full-font probe action and exact-layer proof tab; explicit fontTools analytic ordering adaptation.

 finite-probe numerical repair (.120): exact control-hull exclusion prevents
rounded solver hits for curves strictly beyond either finite probe endpoint.
Exact endpoint coordinates replace rounded backend endpoint hits only when
source fixed-coordinate equality and finite bounds prove the hit. All four
probes, strict0.05 predicate, traversal, owned result and real-layer tab workflow
remain. Ascending curve-time ordering stays an explicit adaptation; Glyphs
engine equivalence and complete FontLab native acceptance remain pending.

 retained first .120 artifacts as a failed attempt: an outside exact endpoint
can round onto a finite probe even with overlapping hulls. Drop numerical t0/t1
hits before restoring only valid exact source endpoints; interior roots survive.

 combined source candidate: The combined reviewed-source candidate uses App0.2.122.dev0 and Glyport1.0.8.dev37. Complete deferred, table-selection and editable-choice mechanics retain their separate foreign-policy owners. Point Counter (Master Layers) retains the complete reviewed read-only report and literal-text postcondition. Dangerous Offcurves retains its complete all-font finite-probe and exact-layer proof workflow; ascending fontTools curve-time order is an explicit adaptation of the opaque Glyphs engine, whose equivalence remains unproved. Literal NUL publication is refused on lossy bindings; full native PythonQt/NUL and complete font/UI/history/reopen acceptance remain held.

## Duplicate Unicodes .121 candidate

Complete whole-font checkbox cleanup editor through shared App/Fly, preserving primary-owner defaults and ordered surviving assignments. Adds stale/preflight/partial-write handling and single final history notification; original native getter/UpdateAll paths are not used. Native qualification remains pending.

Added complete paired Find Files practical workflows; bounded read-only streaming searches and owned nonmodal UI.

## 0.2.124.dev0 — Styles Character Map sizing

Apply the original Styles grid size hint explicitly at attachment and after reference-font changes. This preserves variable cell sizes and scrolling without fixing the widget bounds, while avoiding PythonQt native size-hint dispatch loss. Native NUL conversion remains a separate hold.

## 0.2.125.dev0 — native Text Holder IME text conversion

Convert native QString commit values through Qt's value-return bridge before
Python text processing, including empty preedit-only events. Preserve literal
separators, selection/replacement, caret and native Undo/Redo. Python string
inputs are unchanged. Native embedded-NUL support and final workflow acceptance
remain held; the separate NUL refusal candidate is not included.

## 0.2.126.dev0 coherent reviewed workflow union

Combines the complete Duplicate Unicodes and paired Find Files tools with the reviewed Character Map sizing and literal IME repairs on .122. Preserves the prior shared UI and writer workflows. Native acceptance remains pending.

### shared proportional Qt numeric ranges

- Move four Cocoa/Vanilla callers’ repeated range setup, proportional conversion and rounded setter mechanics into App `qt_numeric`; preserve all clamping, exact caches, tick snapping, callbacks, busy state and error/mutation order in the adapters. App .131 / Glyport .38 remain source/artifact candidates, native qualification pending.

: integrate the complete reviewed proportional Qt numeric extraction with all .126 workflows, retaining every prior runtime/menu byte except the four declared Glyport adapters.

 private source candidate: complete all-master Kerning Cutoff action retains inclusive[-250,100], explicit pair kinds and per-master counts; repairs earlier-master-only notification with the qualified batch writer. Native qualification pending.

## 1.2.28 (2026-11-16)

Kerning Cutoff now retains explicit glyph/group modes, including literal glyph names beginning with @ that collide with class names. Additive typed snapshots and edits use the existing history writer. Legacy string readers refuse an unrepresentable glyph instead of silently merging pairs. Existing unambiguous callers retain their keys. Native qualification remains pending.

## 1.2.28 (2026-11-16)

Add the complete Science Gothic 28-target/378-comparison Symmetry writer with lossless explicit glyph/group identities, sequential class aliases and zero deletion. Preserve original # and case-sensitive Ctr master exclusion. Cutoff retains its distinct all-native-master policy. Native qualification pending.

: private .145 coherent union on reviewed .141; complete admitted CopyAnchors/shared scalar-style reader .144 and TextHolder/literal helper .139revision3 retained. Fresh artifacts/full consumer/Qt/whole-original coverage verification pending; full native qualification remains separate. No host/canonical/live install writes.

## 0.2.143.dev0 — Find Files literal query candidate

Preserve embedded NUL in both Find Files editable query fields and in the byte
profile's ordered native combo histories. Retain the original 32,767 UTF-16-unit
editor limit, literal matching, profile-specific publication and cancellation.
History insertion preserves the live draft, selection and Undo state. The shared
literal Qt helper is a separately reviewed dependency; final artifact and native
acceptance remain separate from source preparation.

: share complete native Qt text/checkbox item construction, flags/check-state ordering and table ownership across Cocoa NSTableView and Vanilla List through App.table_items; preserve every existing public consumer and foreign policy.

: integrate complete reviewed literal TextHolder/anchor tools, both literal Find Files profiles and generic Qt table items without replacing prior workflows; host acceptance remains pending.

## complete four kerning proofs

Add Hoefler Lowercase, Hoefler Uppercase, KernKing and KernSym through shared App/Fly. Keep all five exact licensed texts and KernKing two-tab order. Preserve Output. Ordinary artifact/current consumer/whole-module verification follows; full native tabs/font/history acceptance remains pending.

### paired whole-font background cleaning candidate

- Add distinct all-layer and declared-master background removal tools through Fly/App.
- Remove original whole mask objects; reject ambiguous mapping and automatic dependencies before history.
- Contain partial native failures with one final notification and explicit Undo diagnosis. Native acceptance pending.

### background failure and active-state repair candidate

- Always attempt one final notification after attempted removal, aggregate individual pre/post stamp and notification errors.
- Use nonassigning active resolver; active/locked backgrounds remain explicitly unsupported original-domain gates.
- Prepare survivor identities in checked per-glyph passes before history, and fence final staged sources/queue.
- No native acceptance or reconstructed background rollback.

 complete .153 union retains reviewed .148 and all four .149 proof workflows/five licensed texts, both complete .151 background cleaners and final admitted .152 Character Map contrast. Preserve full original workflow/coverage denominators and all prior menus. Active/locked backgrounds remain UNACCEPTED; all native font/history/reopen gates stay open. No canonical/native/live installation/push.

## 1.2.28 (2026-11-16)

- Paint the basic grid damage rectangle white before its existing dark glyphs and coverage markers, preserving readability under inherited dark themes. The official profile, typography, geometry, selection and palette remain unchanged.

- Private .159 integrates complete Raise Ascender with reviewed .157 failed-Close lifetime repair; all original font/history domains remain pending.

- Private .159 includes complete reviewed Perpendicular Guides: selected nodes and component centre guides, first-selected-layer scope, transformed geometry and retained carriers; native full-font/history acceptance remains pending.

- Private .159 combines both complete reviewed reference Image Viewer profiles and their source-distinct zoom/Fit/printing, modal/asynchronous dialog and lifetime policies; native printer/OS and whole-font qualification remain pending.

## 2026-11-01 — Owned child dialog priority (source candidate)

- Find Files directory/progress children, Image Viewer file/print/message children, and Same Kerning Groups diagnostics preserve their flags and add `WindowStaysOnTopHint` before display. Existing parents, modality differences and printer leases remain. Directory retries reapply priority; failed child setup remains inside owned cleanup. Native stacking and print-panel acceptance remain open.

## 2026-11-01 — Owned standard message boxes

- Add `qt_dialogs.run_standard_message_box` for parented priority warning/question dialogs. Preserve static Qt title/text/icon/button/default/result behavior, including interrupted exec returning Cancel; owned finally cleanup covers setup, execution and result failures. Existing helpers and defaults remain unchanged.

Private .161 adds complete Jens Kutilek composite-difference and all-other-font glyph-set reports with source-defined reference/target/order/filepath policies and owned selectable output.

## N267 — shared Qt color presentation

Extract complete generic color/style/palette/dialog mechanics into App; retain every Cocoa/Vanilla conversion, callback, quiet, ownership and failure policy in Glyport. Native qualification remains pending.

### N228 — paired whole-font background cleaning candidate

- Add distinct all-layer and declared-master background removal tools through Fly/App.
- Remove original whole mask objects; reject ambiguous mapping and automatic dependencies before history.
- Contain partial native failures with one final notification and explicit Undo diagnosis. Native acceptance pending.

### N239 — background failure and active-state repair candidate

- Always attempt one final notification after attempted removal, aggregate individual pre/post stamp and notification errors.
- Use nonassigning active resolver; active/locked backgrounds remain explicitly unsupported original-domain gates.
- Prepare survivor identities in checked per-glyph passes before history, and fence final staged sources/queue.
- No native acceptance or reconstructed background rollback.

N227: share complete native Qt text/checkbox item construction, flags/check-state ordering and table ownership across Cocoa NSTableView and Vanilla List through App.table_items; preserve every existing public consumer and foreign policy.

## N177 private preparation — incomplete Reflect family

Added a detached tested coordinate/component-scale plan for both original
Reflect actions. Native capture/writer and public menus remain unimplemented
pending typed selected-anchor ownership. This is not a usable tool or released
source/artifact candidate. No existing runtime behavior changes.

### Private incomplete Common Glyphs investigation (N175)

- Add an unpublished comparison model and injectable owned UI prototype; the optional glyph-only charcoal writer remains held on native API/mapping/history requirements. No public menu or complete workflow claim.

Added complete Dangerous Offcurves full-font probe action and exact-layer proof tab; explicit fontTools analytic ordering adaptation.

N157 finite-probe numerical repair (.120): exact control-hull exclusion prevents
rounded solver hits for curves strictly beyond either finite probe endpoint.
Exact endpoint coordinates replace rounded backend endpoint hits only when
source fixed-coordinate equality and finite bounds prove the hit. All four
probes, strict0.05 predicate, traversal, owned result and real-layer tab workflow
remain. Ascending curve-time ordering stays an explicit adaptation; Glyphs
engine equivalence and complete FontLab native acceptance remain pending.

N160 retained first .120 artifacts as a failed attempt: an outside exact endpoint
can round onto a finite probe even with overlapping hulls. Drop numerical t0/t1
hits before restoring only valid exact source endpoints; interior roots survive.

## N145 .118 Point Counter literal selection repair

Import complete Reza master-layer report on reviewed .106, preserving its prior workflows.
Reuse unchanged Text Holder literal editor read-only; preserve NBSP/LS/PS and UTF16 selections.
F1 RED, complete artifacts/consumer/coverage results are recorded after verification. Native pending.

## 2026-10-21 — N137 shared table selection (.113 / Glyport .34)

Move complete generic Qt model-row selection and table-range selection/read
mechanics to injected host-free App.table_selection. Preserve distinct native
strategies, original order/duplicates/int conversion/extension/bounds, signal
timing and propagated errors. Keep Cocoa/Vanilla suppression, notifications,
bindings, data and foreign policy in Glyport. Regression-first focused cases,
original AST traces, full source/ordinary archives/current consumers and
unchanged original whole-module80/80 floors with zero exclusions are recorded
in workspace verification/issue-120/shared-ui-next-z42. Native FontLab and
complete preservation qualification remain separate; no live/canonical/push.

## 2026-10-21 — N143 shared editable choice commits (.116 / Glyport .36)

Move complete generic editable-QComboBox setup, Qt5 activation-overload
filtering, user-modified commit acknowledgement and programmatic text reset
to injected host-free App.editable_choices. Both Cocoa and Vanilla combo
paths use it; Cocoa text/path fields use the same existing commit primitive.
Retain callback/continuous/quiet scopes, datasource, conversions, completion,
public APIs, errors and ownership in Glyport. Regression-first source,
original full-method traces, actual Qt signals/lifecycle, ordinary wheel/sdist,
seven consumers and unchanged whole-module80/80 zero-exclusion evidence:
workspace verification/issue-120/shared-ui-next-z43. No native/canonical/push.

## .114 — master-layer Point Counter

Independent complete Reza report: every selected occurrence, stored master layers, empty masters, own contour totals and fixed400×300 read-only window. Quadratic endpoints are included, correcting the original omission. Native qualification remains pending.

- N128/.110: complete Show All Layers proof candidate, preserving repeated selected parents, stored foreground layer order and trailing newlines. Native acceptance pending.

## 2026-10-21 — N127 shared deferred batch (.108 / Glyport .33)

Move only complete generic zero-timer coalescing and snapshot draining to App. Keep host registry, dispatch-depth refusals, foreign ownership and errors in Glyport. Initial missing-module RED retained; 38 focused controls and eleven exact original AST scheduling traces pass, including duplicates, reentrancy, equality/start/processor failures. Actual standalone Qt5 timer, nested-dispatch refusal, owned-widget destruction and drained-host collection pass. Final ordinary wheel/sdist, full consumer and unchanged original-baseline80/80 zero-exclusion gates are bound in private shared-ui-next-z39 evidence; native qualification remains pending. No canonical/live/native/push work.

## N105 Close But No Cigar (.93 source candidate)

Complete ordered all-selected-parent/first-layer near-angle, horizontal/vertical
stem and six node-position checks, with explicit associated-master data and
strict original boundaries/exclusions. Shared modeless Refresh/Close report;
no Output/font/selection writers. Numeric cubic angle repaired; original curve
sampling/open wrap preserved. Tests, source/API calibration and ordinary
archive verification: workspace verification/issue-120/near-miss-z35/.
Native acceptance, root review and delivery remain pending.

## 1.2.28 (2026-11-16)

Add both complete retained spinbox profiles as selected-layer metric/proof-cost
and whole-font revision worksheets. Keep all numeric/date/time/format controls,
precision and distinct special-value/stepping semantics. Local drafts only.
Source, actual Qt5, package and coverage verification recorded in WORK.md;
native FontLab acceptance remains pending. App0.2.88.dev0 is reserved.

### N95 independent spinbox fidelity repair

The Detailed separate QTimeEdit now uses time-only initialization, preserving
the original hidden2000-01-01date and date-bearing range endpoints. Visible
time/cutoff behavior is unchanged. Explicit real-binding hidden-date and
minimum/maximumDateTime checks cover the source distinction. Earlier.88artifacts
remain superseded evidence; revision-N95 and the combined.90artifact must pass
the complete checks before integration. No native FontLab call ran.

## N79: both elastic-node component dependency graphs (.83 candidate)

Retain the distinct part2/part3 force laws, fixed nine-node graphs, node/edge
geometry/paint, keyboard/wheel controls and timer policies. Current-font mode
reads all current-master glyph component names twice; repeated/cyclic/missing
references and isolated/unencoded glyphs remain in source order. Drag/shuffle
change only local coordinates. Refresh clears stale captures, Stop Motion stops
both timer forms, and actual drag state guards Close. No font writer runs.

Focused tests first failed with the missing new module; subsequent pure-model,
SDK-shaped rejection and actual standalone Qt widget tests pass. Exact expanded
commands/results and final ordinary artifact/whole-module evidence are retained
in workspace verification/issue-120/elastic-component-graphs-z32. Existing source
bytes and both original hashes remain preserved. Native FontLab acceptance is
pending; no canonical write, live install, push, tag, release or publication.

N85 source-fidelity repair: retain part2's zoom-out branch for zero-y wheel
events and part3's unselectable nodes. Cover actual native viewport wheel
dispatch and selection behavior; prior candidate evidence remains retained.

Preserve part2 native ellipse type/shape/bounds/default pen/selection painting,
and native line/separate arrow pens and stacking order; part3 custom graphics
remain distinct. Compare selected/unselected pixels against native ellipse.

Read the part3 sceneRect through the existing Qt property reader, matching
PythonQt's declared property and the original behavior. Force cache refresh in
the real-widget property-profile paint test.

## Issue120 Z27 — Glyph Spacing Worksheet pair (unreleased)

Independently implement both complete spinboxdelegate profiles through lazy Fly/App entrypoints. Preserve all four rows/eight cells, profile-specific storage/headers/frame/sizing and native delegate events. Add complete selected-layer baseline/candidate reports, atomic Refresh Selection, exact Reset Factors and owned Close/error/destruction handling. No font writer or original body/helper execution. Native FontLab/PythonQt, complete getter/cache/history/save/reopen acceptance and publication remain pending.

Tests and exact commands/exit receipts are recorded in WORK.md and the workspace spacing-worksheet-implementation-z27 evidence. Original identities/resources and other menus remain preserved. No canonical/live install, tag, commit or push is included.

## 1.2.28 (2026-11-16)

Relocate injected message/file dialog construction/execution and retained-box
show/teardown into qt_dialogs. Preserve constructor arguments, ordering, modal
finally cleanup and existing close failure priority. No signals, native imports
or foreign callback/answer/filter policy are introduced. Native acceptance pending.

## 1.2.28 (2026-11-16)

Add strict immutable source snapshots and same-associated-master ordered next/previous occurrence plans with wraparound and full stale-source refusal. The public next/previous source candidate now uses that shared planner and a direct native MainWindow occurrence slot with a complete symbol copy. Source-backed master/prefix families retain native order. Structured failures distinguish refusal from potentially partial native writes. Unsupported text/preview/shaping and unassociated multi-master contexts remain unfinished original requirements; native preservation is unqualified.

Pedro background family (issue 120 N86, App 0.2.86.dev0 candidate): complete
Scale/Shift numeric dialogs with Apply and immediate selected-path replacement
across every glyph current-master background, including the first auxiliary
layer background. Scale excludes components; Shift includes their positions.
Existing mask metadata is retained; staged copies restore raw node flags,
shape notes and names. Original source/provenance stays read-only. Native
full-font cache/history/Undo/Redo/reopen and widget lifecycle remain pending.
## Raise Ascender queue disclosure — 2026-11-01

Raise Ascender now follows the ordinary-writer pending-update policy. It reads
the native queue once after final source recapture and discloses the captured IDs
and modification-date caveat before history. Queued IDs alone no longer refuse
the action. Source drift, automatic-dependent and canvas-history guards remain.
The optional disclosure mapping retains warnings on failure; CLI callers without
one see the warning in Output, while the panel shows it once in owned status.
Each action resets stale disclosure, including no-op and early-failure actions.
No queue clearing or timestamp normalization was introduced. Native complete-font
preservation, deadline/finalization and original workflow qualification stay open.

## Perpendicular Guides queue disclosure — 2026-11-01

Removed the unrelated anchor-copy pending-queue guard from guide capture and
writing. A nonempty native queue alone no longer prevents capture or editing.
The writer reads the queue once after source and history-scope checks, prints
the existing date caveat before possible mutation, and returns pending_updates
and pending_note with its counters. No-op results have empty disclosure and do
not read the queue. Source recapture, automatic-layer/dependant refusal, guide
order readback, retained objects and one final notification are unchanged.
Native complete-font preservation and finalization deadlines remain open.

Baseline command (rtk proxy, existing ordinary-artifacts/wheel-env interpreter):
`env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 QT_QPA_PLATFORM=offscreen $FONTLAB_TEST_SCRATCH/issue123/standard-message-priority-20261101/ordinary-artifacts/wheel-env/bin/python -B -m pytest -q -p no:cacheprovider tests/test_perpendicular_guides.py tests/test_perpendicular_guides_native.py tests/test_perpendicular_guides_selection.py`:exit0,45passed.
New regressions before repair: same interpreter/flags, tests/test_perpendicular_guides_native.py
-k 'queue_is_read_once or noop_never_reads':exit1,3failed/16deselected; ../red.log.
Focused after repair:exit0,48passed; ../focused.log. Strengthened real capture
test to trap any queue read before the configured full gate. No dependency change.

## Perpendicular Guides partial-failure diagnostics — 2026-11-01

Reused history.PartialWriteError to retain append, first stamp, notification and
final stamp exceptions in order, with the first as cause and shared Undo guidance.
A first-stamp failure no longer skips notification. The pre-append deadline check
now precedes the attempted-write cleanup block: an expired precondition does not
change timestamps or notify a semantic edit. History initialization may already
have occurred; this is not a claim of untouched native history internals.

Baseline48focused passed. Fifteen combinations of ordinary failures plus the
pre-append deadline case failed before repair (../red.log:16failed). An intermediate
implementation omitted finally and failed the new interruption check; corrected
to retain finally so KeyboardInterrupt propagates after one cleanup attempt
(../interruption-red.log retained). Final65focused pass (../focused-final.log).
These are typed host doubles, not native preservation or hard deadline proof.

Commands use rtk proxy and the existing read-only ordinary artifact interpreter:
`env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $FONTLAB_TEST_SCRATCH/issue123/standard-message-priority-20261101/ordinary-artifacts/wheel-env/bin/python -B -m pytest -q -p no:cacheprovider tests/test_perpendicular_guides.py tests/test_perpendicular_guides_native.py tests/test_perpendicular_guides_selection.py` (baseline/final exit0).
RED tests use the same interpreter/flags with test_perpendicular_guides_native.py
-k 'all_finalization_errors or deadline_before_append' (exit1); interruption
-k interruption_after (exit1 before finally restoration).

### Review correction: interruption plus failed cleanup

Review found ordinary cleanup failures could be lost behind a pending interruption,
and an interruption in the first stamp could skip notification. Four new tests
failed (../review-red.log); all four phases now retain BaseException until cleanup
attempts finish. The original first interruption is reraised with the other failure
diagnostics and Undo guidance as Python3.11 exception notes; ordinary failures
use the shared PartialWriteError. Official API consulted before use:
https://docs.python.org/3.11/library/exceptions.html#BaseException.add_note .
Review recheck clears the material finding. Focused69passed (../review-focused.log).
This proves exception behavior for injected calls; native timing remains unproved.

## 2026-11-01 — background clearing queue disclosure

Both clearing scopes now use shared pending-update disclosure before history.
The backend reads the queue once after final revalidation and history-scope guard;
never clears it. It returns pending_updates/pending_note alongside counts, or
retains them in an optional keyword disclosure mapping if a write fails. Callers
without a mapping receive the warning in Output before history. No-op results
carry empty fields without querying the queue. Panels preserve the warning after
partial removal and failed rescan; explicit Refresh and new Apply reset it.
All existing mapping, active/locked-mask, automatic-dependant and history guards
remain. Native full-font preservation, cancellation/finalization and reopen are
still unqualified. No canonical installation, promotion or release.

Baseline81pass. New regression12fail after fixing a test import collection error;
all attempts retained externally. Final focused95pass. Whole gate6891pass,
76warnings; changed native module99.07% and panel95.10% combined coverage.
Independent bounded source review: no blockers. No native calls.
Exact commands (candidate cwd unless noted):
- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 QT_QPA_PLATFORM=offscreen PYTHONPATH=src $FONTLAB_TEST_SCRATCH/issue123/writer-menu-integration-20261101/env/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_clear*.py`: exit0.
- Workspace cwd: `rtk proxy env PATH=/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin sh .metaswarm/quality.sh coverage $FONTLAB_TEST_SCRATCH/issue123/background-queue-20261101/fontlab-fontlabapp fontlab-fontlabapp`: exit0.
Evidence: external issue123/background-queue-20261101, gate7CHd2T.

## 2026-11-01 — background clearing interruption finalization

Retain BaseException identity through attempted-batch finalization. A removal or
readback interruption stops further removals but still attempts both owner date
passes and one notification. Each cleanup failure leaves subsequent owners and
phases runnable. Reraise the first original non-Exception after attaching other
failure types/messages and conservative attempts/removals plus Undo guidance.
Before any removal attempt, propagate interruption without notification or Undo
advice. Ordinary errors retain existing messages/counters and chain their first
cause. Queue disclosure and all source/native guards remain unchanged.

Eighteen new cases: initial12failed1passed; final113focused pass. Full gate6909
passed,76warnings; native module99.15% combined coverage. Independent bounded
review: no blockers. Native deadlines, preservation and Undo/Redo/reopen remain
open. No canonical installation, publication or promotion.

Commands (candidate cwd unless noted):
- `rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 QT_QPA_PLATFORM=offscreen PYTHONPATH=src $FONTLAB_TEST_SCRATCH/issue123/writer-menu-integration-20261101/env/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_clear*.py`: exit0.
- Workspace cwd: `rtk proxy env PATH=/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin sh .metaswarm/quality.sh coverage $FONTLAB_TEST_SCRATCH/issue123/background-interruption-20261101/fontlab-fontlabapp fontlab-fontlabapp`: exit0.
Evidence: external issue123/background-interruption-20261101; gatexqauIa.
Python3.11 add_note contract checked against https://docs.python.org/3.11/library/exceptions.html#BaseException.add_note .

## Additive selection — 2026-11-01

select_glyphs(add=True) now selects only requested names not already selected.
It never calls Unselect in additive mode. Empty/already-selected inputs are
write-free after the existing package and Font-window checks. Replacement mode
still clears first. Native failure propagates unchanged; completed additions may
remain, but the prior selection is never explicitly cleared. No UpdateAll added.

Current upstream pFontLab.cxx Selected reports any selected matching chart cell;
Select adds all matching cells. Skipping already-selected glyphs therefore
preserves partial duplicate-cell selection. This is a name-level additive API,
not an all-cell expansion command. Source inspection does not qualify the host.

Baseline focused41passed; eight new behavioral cases failed before repair.
After repair one historical clear-count expectation failed; changed that expected
count to0 while retaining result/preservation assertions. Final focused49passed.
Commands (rtk proxy, candidate cwd): env PYTHONDONTWRITEBYTECODE=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src
$FONTLAB_TEST_SCRATCH/issue123/background-menu-20261101/env/bin/python
-B -m pytest -q -p no:cacheprovider tests/test_scripting.py.
Full gate/artifact/review results are recorded by root after completion.

Wait, but: this does not implement atomic rollback, deadlines, filtered colour
scope or complete native selection/history/preservation acceptance.

Final configured App gate:6917passed/76warnings; scripting.py83.02%combined,
background_clear_native99.15%; unchanged80%gate passes both full modules against
e61c02f28 baseline. Evidence .metaswarm/runs/fontlab-fontlabapp.nbKmMy.
Command: rtk proxy env PATH=/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin sh .metaswarm/quality.sh coverage $FONTLAB_TEST_SCRATCH/issue123/additive-selection-20261101/fontlab-fontlabapp fontlab-fontlabapp (root cwd), exit0. Initial gate attempt exit3 because no upstream; assigned same upstream as predecessor, preserving its baseline, then passed. Independent scoped review found no blocker. Native and ordinary-artifact qualification remain separate.

## 2026-11-07 — Exact frontend notices and English search assets

Added exact upstream frontend notices and source-map provenance for the existing MaterialX 10.1.8 payload. Explicit English configuration and a small build hook reject language, corpus, reference, asset-set or hash drift before omitting the 35 unused language helpers. All nine retained core assets, original product legal files, guides, catalogue rows, media, runtime and dependency/build locks are preserved.

The strict site build and all 35 documentation tests pass. The complete new hook has 100% statement/branch coverage; real Git staging, checkout and archives preserve exact legal bytes. An independently installed matching lock reproduces all 54 output bytes and modes. Existing immutable source/output, epoch, concurrency and full-parity workflow checks remain active. Browser and independent review evidence are separate from these local checks.

Private Pages configuration, grants, requests and publication remain owner-held; this source follow-up adds none.
No product release or installation is claimed. Prior ordinary artifacts remain bound to their recorded revisions; a later Git revision changes genuine hatch-vcs metadata. Full current source archives include these documentation additions; no unchanged-sdist or whole-wheel identity is asserted. Native acceptance and owner installation remain separate.

## 2026-11-07 — installed icon path-tuple inventory refinement

The current HTML/CSS contains 45 distinct ordered SVG path tuples. A complete scan of the four installed MaterialX icon families finds 43 exact installed matches and two unmatched Lucide tuples, refining the earlier known-candidate inventory. The additional installed match is the Font Awesome version caret-down. Its existing CSS header and full notice retain Font Awesome Free 7.1.0, Fonticons and CC-BY-4.0 icon attribution. The official NPM caret SVG has different raw path bytes; no unmodified-primary SVG, whole-geometry or optimizer-recipe equivalence is claimed. The two unmatched Lucide tuples retain their pinned SCSS source attribution.

A new actual-output regression derives these counts and checks installed matches, unmatched CSS references and the caret header. It fails against the prior 42 count and passes with the corrected metadata. All 36 current documentation tests pass; full strict and independent exact-lock builds match every output byte and mode. Only the legal paragraph, corresponding inventory and legal search row change in the site. Runtime, packaging, generators, vendor assets, full notices, existing guidance and the Fly search fix remain exact. Fresh browser verification and independent review are recorded separately. No private Pages operation, delivery, installed-product upgrade or native acceptance is claimed.

## 2026-11-08 — documentation module count for Issue 241

The complete API map and the documentation index now list 625 modules, adding the seven Issue 241 fontui modules (livesync, shaping, tglyph, tglyph_edit, tglyph_model, tmetrics, tmetrics_model); the docs tests and generated site were updated to match.

## 2026-11-09 — TMetrics echo-token wording for Issue 241

PLAN and TODO now state that TMetrics records its echo token from the drawn state. Only the native check that FontLab's post-write notification matches that fingerprint remains open.

## 2026-11-08 — Issue 235 adoption planning

Added a precise future shared-pens adoption gate linked to the [Pens plan](../fontlab-python-pens/PLAN.md#task-6-consumer-migrations-and-adoption) and [tasks](../fontlab-python-pens/TODO.md). This documentation update changes no runtime code and delivers no installed/native/canonical adoption.

## 2026-11-08 — preserve tiny nonzero kerning labels

Use two significant digits only when Kern Indicator's existing rounding would label a nonzero kerning value `0` or `-0`. Preserve normal labels, true-zero omission, both junctions, sign colours and zoom limits. Eight signed literal regressions fail against the original formatter and pass with the narrow correction.

The complete source suite passes 9,681 tests with 100 retained warnings; the whole changed module covers 33/33 statements and 10/10 branches with zero exclusions. The qualified owned short-HOME/offscreen route also passes all 29 unchanged Find Files/literal tests. The initial long-HOME geometry failures remain recorded and are not a responsive-layout fix. Independent source review and delivery remain separate; no ordinary artifact upgrade, owner installation or native acceptance follows from these source tests. Specific Reporter-policy, native close/reset and long-HOME follow-ups remain in PLAN/TODO.

## 2026-11-09 — Reconcile tiny kerning labels with current App source

Preserved the incoming TMetrics/TGlyph implementation and complete documentation histories while composing the reviewed tiny nonzero kerning-label formatter and regressions. Fresh arm64 Python 3.11.17 with real HarfBuzz passed 9,909 tests (100 warnings); the complete changed module has 100% statement and branch coverage without exclusions. This source-only local candidate still requires independent CODE review and a normal local merge milestone. Reporter follow-up and final combined normal-hook, distribution, installed-origin, remote and CI gates remain separate; no native or canonical installation is claimed.

## 2026-11-09 — Suppress changing Reporter errors by stable source and type

Reporter._once now keys the existing bounded shared history by stable reporter name and actual exception class, without message text. Preserve first-error identity and sink containment; distinguish actual classes sharing a name. README describes cache eviction and backend-reset limits. Existing backend/cache behavior is unchanged. Five old-production failures reproduce the policy mismatch; stable-source and both close/reset controls already pass. All 26 focused cases and the complete 9,917-test suite pass (100 warnings), with complete reporter.py combined coverage 152/155 = 98.0645% and zero exclusions. Native lifecycle and final combined delivery/install gates remain separate; this source candidate does not establish them.

## 2026-11-09 — Issue 242 shared-pens main candidate

Contour selection, contour transform, master interpolation and proof inspectors use fontlab-python-pens (Issue 235 commit c70f18d, cherry-picked onto the Issue 241 TMetrics/TGlyph and shaping work; CHANGELOG and WORK conflicts kept both sides). The dependency floor is `fontlab-python-pens>=1.0.0`. Changed modules are 99–100% covered in source tests. No native acceptance is claimed.

## 2026-11-09 — Issue 242 review fixes: recorded test and runner changes

- `tests/test_contour_selection_native.py`: the missing-dependency test now
  blocks `fontlab_pens` instead of `fontTools.pens.areaPen` and expects an
  `ImportError` instead of `RuntimeError("...[fontui]")`. fontlab-python-pens
  is a required dependency, so its absence is a broken install, not a missing
  optional extra. The test still checks that nothing is cleared first.
- `tests/test_package_boundaries.py` still forbids `[tool.uv.sources]` entries,
  with one exception: the fontlab-python-pens leaf, which has no FontLab
  package dependencies of its own and is not a peer.
- `test.sh` now runs `uv run --no-project --with-editable "$here[test]"`
  instead of `uv run --extra test`, so it no longer resolves the project's own
  sources. App has no `uv.lock`; the runner installs fontlab-python-pens from
  the sibling `../fontlab-python-pens` checkout and exits 2 with a message
  when that checkout is missing.
- The suite collects 9,796 tests at both fa7d01b and this tree. The earlier
  9,901 figure came from the pre-push gate, which adds `uharfbuzz>=0.39` and
  `defcon`; with those, both trees collect 9,901. The 105 extra tests are in
  `tests/test_cov_ui_tmetrics.py` (51), `tests/test_fontui_tmetrics_model.py`
  (28) and `tests/test_fontui_shaping.py` (26), which skip at import without
  them. No tests were lost in the pens merge.

## 2026-11-09 — Find Files long-directory source correction

- Reuse the existing calendar combo sizing policy on Find Files' directory
  control only. Complete paths remain editable/selectable and unchanged in the
  model, history and normal popup; both profiles retain their original sizes.
- Four real long-HOME cases (text/bytes, Documents present/absent) fail on OLD
  width and pass after the two settings. The complete Find Files/literal checks
  pass 68 tests; the full App selection passes 9,921 with 100 inherited warnings.
  Whole ui.py statement-plus-branch coverage is 132/139 (94.964%), exclusions 0.
- Remove completed prior kerning-label/Reporter source-delivery tasks from the
  forward plan while retaining native drawing/lifecycle and owner-install work.
  Layout source review/delivery and native PythonQt remain separate; historical
  height/style limitations and failed harness runs are retained.

## 2026-11-09 — Darwin batch stdout transport and ownership

- Use a Darwin AF_UNIX stream pair for batch child output. Keep its receiver
  owned by the process object, close the parent's writer after spawn, and close
  output even when startup fails before a child exists. Other platforms retain
  PIPE and the actual child.stdout; no descriptor is disguised on Popen.
- Preserve the 64 KiB byte budget, 64-row parsing limit, one-MiB malformed-line
  threshold, child environment, cancellation and supervisor timings. Clarify the
  BatchPanel docstring without changing its behavior.
- Retain five genuine old ownership failures and the earlier source/ordinary
  timeouts. New uninstrumented B09 passes all 56 tests, including the original
  four-MiB/ten-second oversized-output assertion. Error controls retain original
  exceptions and explicitly collect their own fixture children.
- Full source qualification: 9946 passed, zero skips, 100 warnings; complete
  combined coverage is batch.py 198/199 and batch_worker.py 189/193, with no
  excluded lines. These source checks do not establish an ordinary installed
  artifact, current normal-gate result, native FontLab behavior or a general
  latency guarantee.

## 2026-11-09 — Reconcile current required-Pens source and batch regressions

- Preserve the upstream required Pens >=1.0.0 migration and launcher, the reviewed Find Files/Darwin transport source, and both histories. Correct three source-guide dependency sentences; no dependency, generated-page or native policy changes.
- Keep the owner's named 16 KiB oversized-output test and a separate production-default one-MiB/four-MiB/ten-second regression, including cleanup controls. Full B09 passes 57 tests.
- The fresh unchanged full source selection passes 9,947 tests with 100 inherited warnings; all seven complete module combined coverage gates pass with no excluded lines, minimum 132/139 (94.964%).
- Retain the earlier 9,946-pass/one-failure run caused by an added bytecode-cache prefix; an environment-only correction passes the unchanged fixture and new full run. A separate launch/preflight sequencing exception remains explicit and unwaived; no clean prelaunch or continuous-preservation claim is made.
- These are finite source-test results pending independent CODE review. Genuine merged artifacts, ordinary installation, the normal delivery gate, remote/CI and native/owner acceptance remain separate.

## 2026-11-15 — External designspace action in Source Comparison

Source Comparison opens an explicitly selected designspace through the existing
reader, with file identity, per-source metrics, advances, missing glyphs and
structural compatibility. Cancel and failures preserve the complete prior report;
errors appear separately. Closed owners ignore late chooser/read results.
Captured-font selectors and launcher API remain unchanged; Fontport stays lazy.

Focused arm64 Python 3.11 checks: 42 passed in 3.29 seconds, including real Qt
controls and owned designspace/UFO fixtures. Ruff F821 and diff whitespace pass.
Existing qualified offline Fly source resolved the initial 14 fixture setup
errors; no Fly dependency installation was performed. Optional reader checkpoints
cover sources, glyphs, rendering and publication with the GUI deadline/closed
checks; blocking I/O remains non-preemptible. Native PythonQt, themes, actual
installation and latency remain unverified; controller review/full gates and
delivery are separate.
