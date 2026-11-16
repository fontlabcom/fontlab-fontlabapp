---
this_file: TODO.md
---

- [ ] Live-check `fontlabapp.vfjo.scale` in FontLab 9.1 with a non-zero `origin`, and on a glyph with guidelines and hints; the default origin with `widths=True` on `o` and `dcaron` is checked.
- [ ] Live-check vfjo Undo in FontLab 9.1: after `vfjo.paste` of glyphs, Edit > Undo removes each pasted glyph (one step per glyph plus one for the outlines).
- [ ] Live-check vfjo shape paste in FontLab 9.1: `vfjo.paste` of element or contour data lands on the current glyph's active layer as one Undo step; `font=` another font is refused.
- [ ] Live-check the scriptmix vfjo demo scripts in FontLab 9.1 (Task 3).
- [ ] Run `Scripts/Objects/Edit JSON Nodes With vfjo Demo.py` in FontLab 9.1 on a few selected glyphs; check the `.raised` copies have every outline node 20 units higher in every master.
- [ ] Re-run `Copy Selection As JSON Demo`, `Object JSON Demo` and `Paste JSON Shapes Into Layer Demo` in FontLab 9.1 with a glyph open (the `activeLayer` fix uses `json_data.current_layer()`); check selected shapes copy and shapes paste on the active layer.
- [ ] Object JSON `paste_glyphs`: run the auto-rebuild skip before reserving names and Unicode values, so a skipped glyph does not rename or strip later items (review round 1 Minor).
- [ ] Live-check object JSON in FontLab 9.1 on the Lato Desktop VFJ: Paste JSON Glyphs and Import Glyphs From JSON File create renamed glyphs with outlines and widths per master (a live dict round trip through `export` and `paste_glyphs` also kept anchors, guidelines and hints), and Edit > Undo removes them; Paste JSON Shapes Into Layer adds element, layer and contour items as one Undo step (check whether shapes of a decoded detached layer can be added directly or need copying); Edit > Paste of shapes copied by Copy Selection As JSON (glyph Paste passed live); `glyph.activeLayer()` and `shape.selected` work as the Copy demo expects; the FontLab 9.0 message shows on 9.0.
- [ ] Live-check TMetrics typing timing on the Desktop i2-lato.vfj with the old fontport (630edf1, no `glyph_summaries`): keys after the first should not grow with glyph count; time the first key after a font edit and one external width edit while TMetrics is open (offline `follow()` costs about N whole-font scans, 3007 at N=3000). Done with current fontport 8ffb9af on 2026-11-16: 0.056–0.172 s per key, open 1.13 s, refresh about 0.75 s, follow 1.13 s.
- [ ] TMetrics `follow()` still costs about 1.1 s per external edit on i2-lato (3055 glyphs): one whole kerning read through fontport (`host.get_kerning`, about 0.75 s) plus the fingerprint. Consider a cheaper change test (a font-level revision or changed-glyph names from the notification) before re-reading kerning.
- [ ] Live-check TMetrics typing speed with the released fontlabapp and fontport installed (target about 0.13 s per key on Lato); confirm kerning/outline updates appear after a master switch and after editing a glyph while TMetrics is open.
- [ ] TMetrics: while a `/name` is being typed, each new prefix (`/s`, `/sp`, …) costs one native glyph-name read (measured 0.05–0.07 s per key live, within target); probe only completed tokens or add a cheap has-glyph path if it shows.
- [ ] Live-check the 2026-11-16 fixes in FontLab 9 on the Lato Desktop VFJ: Reporters panel opens at 3 columns on the Qt 5 host (layout timing of `_fit`); Glyph Browser and Node Counts open and scroll without a hang (PythonQt `visualItemRect`/`verticalScrollBar`); all five filters edit `a`; Outline Doctor and Transform Studio edit `a`/`o` with `aacute` following and Undo restoring; probe `referenceCount` on a component base with two or more separate elements (none exist in Lato).

- [ ] Deliver the independently reviewed, controller-qualified compact Node Table action row through normal main hooks; verify actual remote SHA and exact-commit CI, qualify release artifacts and matching installed standalone/embedded controls, both themes, cleanup, complete font/history/Undo/Redo and saved reopen. Keep automatic history refresh held; focused Qt checks pass 81 tests and recover 62 pixels of table height, with a measured offscreen Qt minimum-size hint of 346 pixels wide; actual geometry is qualified only at widths 420 and 800, and widths below 420 remain unqualified.

- [ ] Deliver the reviewed, controller-qualified TMetrics event-local prepared-path reuse through normal main hooks; verify actual remote SHA and exact-commit CI, qualify release artifacts and matching installation, then measure native first-use/warm input and visible frames in both routes, preserving both themes, complete font/history, Undo/Redo and saved reopen. Source tests prove reuse and unchanged drawing only.

- [ ] Deliver the reviewed Spacing Studio integration through normal main hooks, verify actual remote SHA and exact-commit CI, qualify release artifacts and matching installation, then verify native action ordering, preserved typed controls/master/font/targets, reference/clipboard freshness, explicit Preview acceptance, selected alternate-offset invalidation without recapture, refused/missing actions, Close retry/reopen, both themes and whole-font/history/save-reopen preservation.

- [ ] Independently review and deliver the exact API-map successor provenance check, then verify the new main commit's documentation and immutable-output CI before releasing the coordinated packages; preserve historical hashes and private Pages holds.

- [ ] Independently review and integrate Kerning Studio captured-target Undo/Redo refresh and preserved Pair Editor drafts; run combined controller/Scriptmix checks, then qualify matching installed native action ordering, both controllers, controls/filter/active editors, stale Apply refusal, explicit Preview, manual Refresh, failed Close retry and reopen, fresh Preview cell baselines/added-removed pair identities, frozen column mapping on target refusal, and staged recovery with absent/refused hooks, table-only drafts after another history event, early Preview refusal disabling Apply and matching Scriptmix retained-draft contracts.

- [ ] Independently review and integrate the compact Master Text action row, then qualify matching installed FontLab controls, both themes, saved geometry and cleanup; 24 focused source Qt tests pass locally.

- [ ] T28: independently review and integrate conditional-sibling marker applicability; qualify combined gates, fresh main/CI, genuine release artifacts and all allowed installer copies, then installed-provider closure and admitted root-installer completion. Local source checks do not establish FontLab/native acceptance.

- [ ] Advance compact forms, selected-layer Filters and TMetrics typing fixes in shared App code with matching Scriptmix/Plugmix consumers; measure the changed input route and defer the full theme/native matrix.

- [ ] Qualify matching FontLab installation of App 1.2.18 translated-element filters, the deletion target fence and host-follow refresh deduplication, then after native admission physical typing, both themes, all five filters, whole-font/history, Undo/Redo and saved reopen without closing T44/T49 by inference.


- [ ] Complete Font Info/Master Text final documentation/combined review and graph check, normal pre-push gates, actual main delivery and exact-commit CI, then release and matching artifact/installation qualification.
- [ ] Qualify matching released/installed Master Text source and native PythonQt preset reload, text/selection, proof dispatch and close/parent-destruction/reopen behavior; retain the unproved underlying C++ corruption mechanism separately.


- [ ] Qualify matching released/installed/cached Font Info form and demo source, then native default/compact fit, all 24 fields, outer/inner scrolling, fixed controls, drafts/read-only refusal and repeated cleanup under both themes with complete font/history/Undo/Redo/save-reopen preservation.



- [ ] Qualify reviewed compact Font UI Lab Anchor/Unicode source on combined main, then matching release/install/cached origins, all controls and table values, repeated/non-BMP occurrence selection, scrolling/resize and cleanup in FontLab under both themes with complete font/history/save-reopen preservation.


- [ ] Qualify matching release/install of the reviewed Filter explicit-selected-layer repair, then native all-five-filter Bold-only, mixed-layer and multi-glyph Apply/Undo/Redo/save-reopen with loaded-source identity, complete-font preservation and both themes. Preserve whole-font refusal safeguards; the historical screenshot cause remains unproved.


- [ ] TMetrics: review the raw text-field observer compatibility limit after delivered source integration; qualify matched release/install and real typing/visible-frame latency in both input routes without weakening font/history/Undo/Redo/reopen gates.

- [ ] Diagnose the actual native `Skipped: a` with admitted loaded filter code; distinguish legitimate automatic-layer/base refusal from wrapper ownership/transform or stale/history refusal.
- [ ] Qualify released Filter reason text and all five filters live, including Apply/Undo/Redo/save-reopen and complete font preservation.

- [ ] Issue 253 Reporters/inspectors: independently review and integrate the compact grid and shared right-hand preview; then qualify released/installed/cached origins, all toggles and rescans, long names, actual glyph/master values, resize, native light/dark appearance and repeated/failed Close with complete font/history preservation. Keep the original full-script scope open.
- [ ] Issue 242 Node Inspector (A19) studio series on `issue-242-integrate-3` (e8e7b4b) and `issue-242-phaseD` (237bff9), about 32,000 added lines with 12-13 merge conflicts against main: re-derive it onto current main in a fresh clone, or retire the branches after checking which A19 parts main already covers.
- [ ] WP04 (079fcbe), WP04b (d423bfc, 0f4256b) and WP07 (44c28ce) deltas sit on the not-for-delivery stack 3955e43: re-derive the still-wanted parts onto main (WP07 identity studios were partly re-derived by c202504) and then retire the branches.
- [ ] Licence (Issue 250, owner Q5): 53 files under `src/fontlabapp` still carry non-Apache SPDX headers: 21 `MIT`, 18 `Apache-2.0 AND MIT`, 14 `MIT AND Apache-2.0` (742 of the 795 files with SPDX headers already read Apache-2.0 only). Relicense FontLab-authored ones to Apache-2.0 and keep third-party MIT/BSD copyright and text in NOTICE; list any file of unclear authorship for team-lead. `pyproject.toml` reads `Apache-2.0 AND MIT AND BSD-3-Clause AND LicenseRef-Proprietary` (MIT/BSD are third-party notices; the proprietary term is `examples/LICENSE-native-ui`, which the owner has also set to Apache-2.0): reduce it accordingly. The Sansomatic G13 oracle in Scriptmix (`tests/test_issue122_G13.py`) must move with the App copies. Do this after the App queue.
- [ ] Repoint the evidence pointers in `src_docs/md/assets/NOTICE` (12 places between lines 134 and 271 say evidence or pending gates are "recorded in WORK.md"), now that `WORK.md` is a stub: point them at CHANGELOG.md entries or the open TODO rows, then regenerate `docs`.
- [ ] WP03 native acceptance (owner: livetester): run the eight consolidated spacing and kerning studios in FontLab on owned fixtures: kerning write, Undo/Redo, save and reopen, and cleanup after close; the offscreen suites do not establish them.
- [ ] App user-visible string changes must run the Scriptmix S1/S2 suite (cross-repo consumer): App 3083abe's gate log (pushlogs/app-3083abe.log) shows App and App-docs tests only, and Scriptmix tests/test_issue122_S1.py and S2.py asserted the old Metrics status wording, so Scriptmix main went red until Scriptmix 6c02460f. Add a gate step or a checklist item that runs the Scriptmix suite (or at least S1/S2) against an App change that alters status or dialog text.
- [ ] Issue 253-C: qualify the E01 embedded four-table minimum on smaller displays; retained offscreen evidence uses 1920x1440. Keep globally complete stock graph analysis held: scoped source qualification retains truncation, CRITICAL/UNKNOWN, arbitrary reflection and native-callback limits.
- [ ] Issue 253-C: after reviewed integration/release/install, native-qualify the new thin Table Filter Demo and shared helper with matched source/cached callable hashes, eight full rows per view, readable content-sized columns, compact controls, five actions and owned cleanup in dark/light FontLab; keep prior compactness failure and original555/App136 scope open until actual evidence.
- [ ] Issue 254: five repos still ship the older 620-line install.vfpy (fontlab-grablab, fontlab-python-examples, fontlab-remopy, pythonqtside, fontlab-aidus-agentus) and lack the `extensions` key; for each, move it to the current installer and check install, reinstall, uninstall and foreign-target behaviour with a temp data folder; none ships bundles today. Also owner-optional native check: install Plugmix, restart FontLab, confirm Plugmix Demo lists the 50 bundles
- [ ] WP07: run canonical G-App and G-Scriptmix with orchestrator-owned milestone/upstream baselines and fully provisioned dependencies on the integrated cohort.
- [ ] WP07 native: qualify all nine tools and 31 tabs in installed FontLab PythonQt, including active-master context, live previews, sorting/resizing, staged actions and repeated/failed Close.
- [ ] WP07 native: verify names/encoding, duplicate Unicode, tags/marks/notes, exact feature text and U+2029 refusals with whole-font preservation, Apply/Undo/Redo and save/reopen.
- [ ] WP07 native: qualify Style Linker instance writes and source/target font context; source tests do not close this hold.
- [ ] WP07/WP11: qualify matching distributions, installed menu routes and genuine containing-commit documentation links after orchestrator integration; retain wpf inventory reconciliation.

- [ ] WP02: run canonical G-App with writable controller evidence/cache directories and resolved dependencies; require 80% lines and branches separately for every changed production module.
- [ ] F47-1 live recheck (livetester): with Light current, a kerning edit targeting Light in a Kerning Studio window shows "Kerning is written to the default master (<name>) only; Light cannot be targeted." and changes nothing; pinned by `tests/test_fontui_tmetrics_embed.py` and `tests/test_fontui_tmetrics_layers.py`.
- [ ] Node Editing Lab "Node table" tab keeps stale coordinates after a native Undo/Redo until Refresh (livetester proposal: `issue250/live-tests/patches/r46-node-table-follows-history.patch`). Next check: follow the host history notification (ImportError/AttributeError guard, no signals means no timer), refresh unless cell edits are staged and then show a status line instead, with fakes and mutants; proposal only until livetester proves it live. The Examples copy cannot change: `Scripts/Contours/Node Table.py` is a pinned consolidation source (85dda66).
- [ ] Issue 253-B: independently review renderer colors/layout and current API-map pin; run the qualified full sibling-cohort gate, then verify released actual glyph canvases, native policy, signed kerning and owned cleanup in FontLab.
- [ ] Issue 253: qualify native PythonQt sizing, content minima, equal preview halves, frame clamp and retained resize under both themes.
- [ ] Issue 253: run every requested script/palette, capture screenshots, compare native FontLab controls and fix remaining local wasted space; retain the full issue denominator.
- [ ] Native (owner: livetester): `shape.contentLocked` on build 9809 is constant True for every component (A2 report 26), so the getter says nothing; the setter changes the saved lock and the VFJ `locked` key is the real state (`edieresis`/`egrave` Light locked, Regular and Bold not; the prototype chooser follows the VFJ key and skips the 105 locked components). Still owner-run: lock one component in the UI on an owned copy and confirm the VFJ `locked` key shows it; if it does not, restore a guard in `components.creation._qualifies`.
- [ ] `flShape.contentLocked` getter always reads True although its setter changes the saved lock: filed as fontlab/fl#8637 (A2 report 26 evidence). Next check: build an owned fixture whose outline shape (not component) is locked and unlocked, rerun the getter and add the result to the issue; recheck when FontLab answers.
- [ ] Master Text Comparison presets path: the missing-file status and a patched-directory load are proven (A2 reports 33 and 33c); still check that a real `MasterBlaster-presets.txt` in `<FontLab user folder>/Scripts` loads through the default folder. Use an owned copy of the user-folder layout, never the owner's folder.
- [ ] WP08: run canonical G-App/G-Scriptmix after exact provisioning and the external WP01 inventory correction; qualify complete changed-module line and branch coverage.
- [ ] WP08: review and adopt S27/S55/S59 launcher transitions, preserving historical bytes and every original action oracle before removing menus.
- [ ] WP08: complete S28–S36 and S56–S58 as separately reviewed increments; absorb TGlyph Window only after parity.
- [ ] WP08 native: qualify all adopted tabs (including the Open Contours and Nodes Near Zones double-click hint and right-aligned numeric columns), captured fonts/layers, actual glyph/proof rendering, sorting, resize, lifecycle failures, preservation and applicable Undo/Redo/save-reopen.
- [ ] WP08: Compare Open Font Revisions (own `RevisionCompareDialog`) and Sidebearing Direction Marker (live Glyph-window overlay via `glyph_view.draw`) are not snapshot reports and stay open; absorb only with a tab-embeddable dialog and a TMetrics canvas overlay hook.
- [ ] WP08: Point Counter (Master Layers) credits Reza Bohloul as inspiration with "no code copied", verified against the App implementation only; diff `masters/point_counts` against the original `Path/Point Counter.py` once that source is lawfully available.
- [ ] WP08 native: Font Revision Comparison and Metric Reports candidate launchers are unadopted until native parity.
- [ ] WP08 native: `Scripts/Utilities/Reference Image Viewer App.py`, `Scripts/Reports/Geometry Audit.py` and `Scripts/Reports/Master Structure Audit.py` are candidate launchers, not adopted, until native parity is shown; Geometry Audit's Dangerous Offcurves route calls `native.run()`, which opens an exact-layer FontLab proof tab on every Refresh (qualify natively); Open Contours App module exists (S65; the original's row selection, double-click glyph selection and red non-zero gap markers are not restored, the tab is text-based); its candidate launcher is not adopted until native parity (Select glyphs on a live font); Nodes Near Zones App module exists (S66; the original's row selection and double-click glyph selection are not restored); its candidate launcher is not adopted until native parity (tolerance rescan and Select glyphs on a live font); Live Glyph Info stays unabsorbed (own Scriptmix dialog, no App model yet).
- [ ] Native: WP09 labs and 51 profiles in installed FontLab PythonQt: E01-E09 open/refresh/preview and the E09 Mark Colours and Review Form writers are proven (CHANGELOG 2026-11-11, A2 report 14); still open: E08 Apply Unicode Map (next check: owner closes Glyph windows, then re-run), captured target/master switches from local controls, Unicode/IME and deferred MIME.
- [ ] Port WP10 Codex labs snapshot (App c957722-era teaching_* modules + 20 Examples tests) onto WP09 routes (production_path/run_profile); App-level tests to 80% per module before landing
- [ ] WP10 mutation survivors, remaining: the embedded `show()` branches of the teaching modules (each needs one assertion that kills its mutant, none changes behaviour). Source: issue250/review/wp10port-batch3-4-review.md. The boundary/comparison survivors listed there (feature_graph :56, outline_svg :61/:95, sketch :45/:88/:92/:169, svg_reference :48/:77/:311, polygon :57, tags :60/:83, notebook :52/:255/:385, paths :58/:60/:74, diff :264, localized_font_names :138, import_kerning_pair_list :57) are killed; see CHANGELOG.
- [ ] Native WP10: qualify all sixteen teaching/GetGo labs in PythonQt, captured glyph/layer previews, font-switch refusal, table sorting/resizing, staged Refresh refusal and Close/reopen.
- [ ] Native WP10: verify retained writer Apply/Undo/Redo/save-reopen and whole-font/source preservation; GetGo verified-fixture previews and disposable operations need a dedicated no-document session.
- [ ] Orchestrator WP10: integrate the reviewed App/Examples cohort, rerun canonical coverage controllers and qualify installed artifacts independently of host/offscreen evidence.
- [ ] Native: qualify all nine WP09 labs and 51 profiles in installed FontLab PythonQt, including captured target/master switches from local controls, read-only previews, Unicode/IME and deferred MIME.
- [ ] Native: verify WP09 local Close/Escape, dock-refused Close retry, child cleanup and reopen; verify writer Apply/Undo/Redo/save-reopen and complete font preservation.
- [ ] Native: verify implemented WP09 proxy/list sorting, numeric order, selection/source identity, active-editor target retention and interactive column resizing in FontLab PythonQt.
- [ ] WP11/WP12: reconcile WP09 compatibility launchers, packaged Lessons entrypoints, truthful catalogue links and installed menu cleanup; retain native acceptance separately.

- [ ] WP02: run canonical G-App with writable controller evidence/cache directories, resolved dependencies and matching Plugmix coordinate-filter bundles; require 80% lines and branches separately for every changed production module.
- [ ] WP05: run canonical App/Scriptmix wrappers with authorized evidence directories and resolved dependencies; independently reviewed full prepared suites and all 88 per-module line/branch gates pass.
- [ ] WP05: rebuild generated documentation in the pinned docs environment and run controller-owned graph/integration checks; source API map and demo references are updated, generated HTML remains stale.
- [ ] WP05 native: qualify all ten tools in installed FontLab PythonQt, including captured targets, previews, sorting/resizing, close recovery, exact topology/raw flags/shape notes, refusals, Apply/Undo/Redo and saved reopen.
- [ ] WP02: run graph change analysis in the orchestrator-owned index before integration; this isolated worktree has no index.
- [ ] WP02 native: qualify TGlyph read-only O-key, drag, delete, nudge, clipboard and direct edit refusal in installed FontLab PythonQt with whole-font/history preservation.
- [ ] WP02 native: qualify AppShell screen clamping, initial splitter proportions, staged bottom actions, About/credits, captured row/layer selection and TGlyph/TMetrics failed-close retry.
- [ ] Native: recheck live that the fractional-kerning refusal now names master, pair and value (source fixed: `kerning/batch.py` `_stage`; unit-tested with a double). Reproduce on an owned fixture: `flPackage.kerning(master).scale(0.5)` stores a fractional pair (`set()` rounds), then run a TMetrics kerning edit and read the refusal text. Reopening a saved VFJ rounds fractional pairs (native defect draft `live-tests/fl-issue-drafts/r37-vfj-reopen-rounds-fractional-kerning.md`, not filed), so the pair must be made by script in the same session.
- [ ] Scope: `write_kerning` refuses a fractional pair on ANY master (the package-wide native checkpoint rounds all of them; pinned by `test_fractional_history_even_on_unedited_master_is_refused`), but Fontport `native_kerning.write_kerning` checks only the CURRENT master, so a TMetrics edit with only another master fractional is applied (A2 report 37 rows 25-28). Decide whether the narrower Fontport check is a gap (the checkpoint covers `kerningContainer`) or intended; do not change behaviour before that decision. Next check (livetester, owned two-master fixture): write a TMetrics kerning edit to master A while master B holds a fractional pair, then use Undo/Redo and save/reopen to see whether B's fraction survives. If it is lost, Fontport must refuse like App; if it survives, App's any-master refusal is stricter than needed.
- [ ] Independently review and integrate the shared Metrics Undo/Redo captured-target refresh; run combined gates and Scriptmix S1/S2, then qualify matching installed native fresh plans/Apply, dependency warnings and consent, captured glyph/master/settings, manual Refresh and close cleanup. Focused source/real Qt checks pass; Report 34 F34-2 native proof remains open.
- [ ] Qualify the Scriptmix Zero-Width Marks "Only marks" subclass with the shared Metrics refresh, then prove live that Undo/Redo updates the captured plan and Apply without replacing settings or selection (A2 report 45, Scriptmix 0c30804f). Source shared-base checks alone do not establish this native result.
- [ ] Native: measure the Metrics planners not yet run live (Scale Advances, Round Advances, Tabular Width, Italic Sidebearings, Copy Metrics From Reference, Sidebearings Tuner and Zero-Width Marks) for composite-plus-base double shift on an owned font. Centre In Advance and Equalize Sidebearings are proven (reports 34 and 35). Companion: Scriptmix TODO row 48.
- [ ] Low priority (F29-1): `LayerEditEditor.check` in `src/fontlabapp/plugins/filters/apply.py:260` compares `node.selected`; consider omitting it from the fence, since a selection change is not an edit. Report 29's Scale `NOT_STORED` was concurrent owner interaction and did not reproduce in 29b.

- [ ] Qualify Issue 234 workflow 14 external designspace comparison in the installed/native view: per-source metrics, glyph-set differences, complete report preservation on failure and safe chooser closure.
- [ ] Qualify Issue 234 #14 matching ordinary artifacts and native PythonQt refresh/error/lifetime behavior and source preservation before closing the integrated Source Comparison workflow.

- [ ] Native-qualify UFO Roundtrip Inspector failure paths: pending-edit preservation (not tested; history was clean), deadline/failure staging cleanup and repeated Close in PythonQt. The success path passed live (A2 report 21, 2.7 s against the 120 s deadline).
- [ ] Native-qualify Representation and Notification Explorer: selection, representations, actual native-to-model notifications/cache synchronization, disclosed cache population, and observer/widget cleanup.
- [ ] Qualify matching ordinary App/Scriptmix installations and reconcile workflow 16/18 with parallel lanes with the matching read-only peer tuple.

- [ ] Native-qualify Designspace Source Comparison with matched artifacts: explicit source/layer selection, metrics and compatibility summaries, complete font preservation and owned teardown.

- [ ] Qualify Issue 234 workflows #1/#4/#5 with matching ordinary installed artifacts and native PythonQt: open-font/current-master identity, glyph preview, reference-master count differences, stale targets, repeated Close and complete font/cache/history preservation.
- [ ] Native-qualify Issue 241 TMetrics/TGlyph bidirectional outlines, metrics, kerning and literal Glyph-window text on owned fonts, including notifications, exact master/layer scope, Undo/Redo, save/reopen and Close.
- [ ] Add explicit non-current-master kerning transactions when the shared Fontport host supports them; TMetrics currently disables kerning for these layers.
- [ ] Qualify Issue 241 named/layer-specific Glyph-window symbol round trips separately; the literal-text bridge leaves these streams local.

- [ ] Native-qualify workflow #6 Interpolation Preview: installed origins, designspace location changes, endpoint/mixed outlines, unsupported-location diagnostics, captured-font identity, complete font/history/selection/cache/dirty preservation and repeated Close; qualify ordinary artifacts separately.

- [ ] Qualify Master Width Comparison ordinary installed artifacts and native master identity/rendering, full font/cache/pending-edit/history preservation and repeated Close; retain the repaired source lifetime evidence and separate full-lint/sibling documentation-write limitations.

- [ ] Independently review and deliver the verified batch recipe filename-literal correction, qualify genuine-commit docs and exact CI/generated parity, then recheck the public literal; retain ordinary/native gates.



- [ ] Qualify Detached Transform Preview genuine archives/distributions/two ordinary prefixes, native owned-font/history/lifetime behavior and truthful containing-commit/generated-doc links; preserve all 8,723 obligations and the minimum eighteen workflows.


- [ ] Carry source-qualified exact UFO feature-source integration and linked source/proof workflow through ordinary artifacts and owned native/history/reopen checks; full literal paragraph-separator editing remains separate.

- [ ] Complete separate A1 artifact/ordinary/native/history/reopen/canonical/publication gates for the eight source-qualified workflows, including Feature Source and Proof.
- [ ] Qualify matching ordinary and native Detached Transform Preview consumers, preserving backend-stored capture, borrowed caches/pending edits, explicit layer/target/generation, current proof, resources and three-owner ACK lifetime; whole-workflow acceptance remains open.



# Open tasks

- [ ] Issue 255: After explicit D43 recovery and admission, qualify the released App/Fly consumer routes, plugin startup and original UI/history/Undo/Redo/save-reopen workflows in FontLab with exact installed and cached source identity; preserve every existing native scenario.

- [ ] Qualify installed native canvas timer reuse after independent source review, current-source ordinary artifact/origin checks and reviewed delivery: close/last-remove/register/watch replacement, retained callbacks and teardown/sink faults, current polling/repaint, complete-font/history and saved reopen.
- [ ] Qualify installed native in-flight canvas poll/getter/sink, repaint, immediate-register and successful painter/filter attachment ownership after current source review/artifact qualification/delivery, including the two demonstrated ID reads, same-timer token/mouse removal, multiple reporters, falsy handles and cleanup/raising/reentrant sinks; qualify selected order-getter and timer/filter construction contracts in installed PythonQt separately from passing source controls, retaining native constructor dispatch, partial allocation/connection side effects, arbitrary nested lifecycle behavior, other ID reads, Qt5 wrapper lifetime, complete-font/history, saved reopen and owner-installation gates.

- [ ] native: verify Extensions discovery from FontLab's actual user-data folder and plugin startup at launch in FontLab 9.
- [ ] native: verify Reporters palette toggles, View > Reporters synchronization and Hide All in FontLab 9.
- [ ] native: verify plugin tool toolbar registration, selection and Tools > Tool placement in FontLab 9.
- [ ] native: verify plugin palettes and Reporters under Window > Panels, close/reopen and signal ownership in FontLab 9.
- [ ] native: verify reporter painting, callback failure containment and complete owned teardown in FontLab 9.
- [ ] native: verify App installation, repeated startup-hook installation, marked-block removal and interrupted-uninstall retry in FontLab 9.
- [ ] Qualify ordinary installed App/Plugmix artifacts separately from the Issue 210 source/fake-host checks; keep the legacy Plugmix runtime separate.
- [ ] Audit external consumers (in-App consumers are clean and guarded by `tests/test_plugmix_shim_consumers.py`) after one deprecated release before removing the `fontlabapp.plugmix` shim.
- [ ] Complete Issue 211 native probes and four minor fixes with independent regression review; reconcile Issue 207 before integrating over current Issue 208/209/M12 code.
- [ ] Run the exact repository checks on the integrated source, obtain independent review, commit/push the scoped milestone and verify its remote head.
- [ ] After qualified main integration, inventory obsolete branches/files, preserve unique work and remove only proven stale items with recovery evidence.

- [ ] Native-requalify the relocated external examples/native_ui.py with the combined App/Remopy cohort, including TypeRig, ownership, cleanup and whole-font preservation.

- [ ] Qualify complete ordinary consumer cohorts and native window/lifetime acceptance after D30 reconciliation; local App source/archive checks are tracked in the Issue 204 integration report.
- [ ] Complete all27 direct Examples constructor/parent-death and shared launcher disconnect contracts without losing refused-Close recovery.
- [ ] Native-qualify guarded original Node Duplicator actions on all four fonts with full history/Undo/Redo/reopen/window-priority/lifetime after D30 reconciliation; Y source/archive/ordinary proof remains separately recorded. Current/all/handles scopes passed live on an owned fixture (A2 report 18 W5); the remaining fonts and window-priority/lifetime checks stay open.

- [ ] Independently review the private release-ancestry integration, run final whole-source/artifact/installed-tuple gates, and qualify native workflows before any D11/D12/D17 promotion or release; genuine development metadata is not a released dependency floor.

- [ ] Complete and qualify Common Glyphs original all-font charcoal action after FontLab issue 8564 supplies a supported glyph-only mark/history path; retain raw layer inheritance and full auto/locked/unencoded/nonexport scope. Qualify installed report rendering, literal Copy Characters/Copy Original Report callback and OS clipboard handoff, whole-font/context preservation and bounded lifecycle separately; current source stage is partial.

- [ ] Qualify installed Master Text Comparison: FontLab #8576 exact active-model binding, all-slot master/layer and trailing delimiter rendering, complete font/cache/history preservation, NUL/UTF16/IME domain, owned settings/geometry, cleanup recovery and real Close.

- [ ] Qualify installed Case Coverage controls/persistence, complete font/history preservation, exact model binding, current/all-font proofs, inactive-view chooser, repeated glyph/layer content, no-op refusal, bounded cleanup/failure fence and owned report lifetime.

- [ ] Qualify installed Smallcap Consistency: export-policy/case disclosures, complete modern and legacy findings, both kerning-group sides, deadline/stale refusal, repeat refresh and destruction, complete-font preservation.

- [ ] Measure canvas-history effect on package-level notifications.
- [ ] Native receipt for `require_history_scope`'s allowed multi-glyph branch: a Glyph window whose text shows two edited glyphs, one Undo restores both; also Metrics and Kerning canvases.
- [ ] Native receipt: Em Star Polygon draws from a Glyph window (owner matched by name).

- [ ] Native-test the extracted qtsafe, Drawing and EditorPainters paths on owned glyph windows; verify GUI-thread execution, mapping, painter failures and teardown.
- [ ] Native-test OwnedMenus add/trigger/remove-in-slot, tool-window title-bar Close and owned text/file/message dialogs; include Glyport plugin/filter/export consumers.
- [ ] Native-test the shared history, Metrics, Names, Anchors, Components and Contours writers through installed callers: exact complete-font deltas, repeated edits, one-step history where promised, failures, Undo/Redo and saved reopen.
- [ ] Measure in-place applyTransform versus preserving detached clones on raw Smooth controls, shape notes and manual composites; cover Centre In Advance, Zero-Width Marks, Italic Sidebearings and Transform Background.
- [ ] Native: tag edits on auto-composite bases (no App writer edits glyph tags, so this cannot run) and mark propagation from glyph to layer, without assuming an expectation (report 16 row 5c).
- [ ] Qualify glyph creation, contour copies, component prototypes, new-glyph components and exact layer-row tabs; verify automatic rebuilding, multiple Undo steps, refusals, read-back and complete saved state. Passed live (A2 report 18 W6): component-of-A and copy glyphs, one row each, exact Undo/Redo, reopen; component prototypes passed live after the D18-4 fix (report 26); new components saved locked is D26-1.
- [ ] Native-run `issue122-native2/drivers/p2_app.py` for the route-A writers (`zone_native.backend`, `master_metrics.write_master_metrics`, `font_history.commit_masters`): both masters in one step, one Undo, Undo/Redo, .vfj reopen, other glyphs, queue and the three refusals. Then add the practical Alignment Zones menu entry. Master Metrics Table, Alignment Zones and Suggest Zones passed live (A2 report 18 W2); the practical menu entry and the refusals stay open.
- [ ] Qualify zone tags/lock retention on edited rows and the `ps_zonesT/B` cache against the zone guides (capture reads the cache, as Font Info's apply path does).
- [ ] The serializer capture/preparation route (`zone_capture`, `zone_prepare`, `zone_write_plan`) stays held on serializer ABI/payload qualification (fl#8554); the route-A writer does not use it.
- [ ] Qualify installed text/named-tab backends, eight context proofs, random proofs, four kerning proofs and group-peer proof: exact symbols/layers/master/order, repeats, empty scopes, fresh-tab ownership and complete font/workspace/history preservation.
- [ ] Qualify Text Simplifier, extrema proofs, bracket-layer reports and compatibility reports in native FontLab, including complete scope/topology, lifecycle, failure paths and saved-font preservation.
- [ ] Qualify both glyph sort/filter profiles, both calendars, read-only and editable glyph trees, both completers and Pattern Lab in PythonQt; verify virtuals, timestamps/locales, menus, selection, refresh, errors and teardown.
- [ ] Qualify shared layout, content geometry, key/resize routing, Qt properties/numeric ranges, editable choices, table items/selection, nested callback guards, signal ownership and deferred scheduling through complete Cocoa/Vanilla/NIB/plugin callers.
- [ ] Qualify owned message boxes, custom/accessory dialogs, images/resources/DPR, both Image Viewers and printer/OS dialogs in the installed host with complete lifetime and font preservation.
- [ ] Qualify both spacing worksheets, spinbox/slider profiles, elastic component graphs, Near Miss and report pairs; retain exact original numerical, graph, read-only and Close policies.
- [ ] Qualify Master-layer Point Counter literal MIME, Dangerous Offcurves engine equivalence and exact-layer proof tabs, and actual Small Contours Close/button/Escape destruction.
- [ ] Qualify typed Cutoff/Symmetry kerning, all 378 sequential comparisons and explicit zero/absence; retain the legacy leading-@ string-identity limitation.
- [ ] Qualify both Character Map profiles in native light/dark themes, initial/updated sizing, markers, damage paint, clipboard/NUL boundaries and complete preservation.
- [ ] Qualify complete Text Holder Unicode/NUL/IME/preedit, selection/replacement, Return caret Undo/Redo, persistent text/frame recovery and terminal lifecycle on final installed artifacts.
- [ ] Qualify both Find Files profiles against native choosers, decoding/progressive results, filesystem/desktop opening and cancellation.
- [ ] Qualify final Raise Ascender and Perpendicular Guides writers with exact selected occurrences, whole-font/history/reopen preservation and failure cleanup; retain all inherited native holds. Perpendicular Guides passed live (report 18 W4); Raise Ascender passed live after the D18-3 fix (report 26: all masters, one row per master, Undo/Redo, reopen).
- [ ] Re-run every affected consumer against the final App/Fontport/Glyport/Fly tuple and complete the final whole-branch source, installed artifact, docs and native gates; select the release floor before delivery.
- [ ] Remove the import-free Vanilla tombstone only after their one-release migration period and consumer checks.
- [ ] Review the dotless-name automatic-rebuild candidate gap in glyph_creation; qualify exact rebuild detection before relaxing consent. Live (A2 report 18 W7): `auto_candidates` returns {} for dotlessi, idotless, i.sc and acute.case, and adding acutecomb silently rebuilt 14 default-recipe Regular auto layers (Undo restores them exactly). Keep open; treat `auto_changes` as the real guard and document that Redo of Add Glyph can leave auto layers stale until reopen.
- [ ] Review parked affine/qtsafe details: main_window identity assertion, absolute singular epsilon, Matrix typing and non-finite drawing failure/painter cleanup.
- [ ] Review parked dialog coercion and test slicing, duplicate master-layer/auto-dependant walks, anchor duplicate-refusal wording and current suite warnings; change only measured defects.
- [ ] Finish Resistenza ShortNames/StyleLinker panels, native instance writes and export proof; detached naming rules alone do not finish that workflow.
- [ ] Qualify VanillaSession in Glyport; recheck Font Info and Groups after host-boundary fixes, then repeat Features and batch-editor workflows with current Fontport.
- [ ] Promote and independently verify the complete Italic Angle candidate before recording its native acceptance; retain broader metrics/master and full-archive work.
- [ ] Complete remaining original-script migration, additional tools/reporters and documentation; retain archived inputs and do not infer whole-project acceptance from bounded historical releases.

- [ ] Qualify shared-launcher priority in native FontLab and cover independent Examples/delegated menu dialog routes before claiming all dialogs match TypeRig.

- [ ] Native-qualify priority and retry cleanup for retained setup-failure windows across12 constructor sites, preserving all original parent/type/chrome and error diagnostics.

- [ ] Independently review C2/C3/C4 child-dialog priority, then qualify ordinary artifacts and native stacking/print-panel behavior with owned fixtures.

- [ ] Integrate and independently qualify18standard warning/question routes using the owned priority helper; retain native/ordinary-artifact and current-cohort gaps.

- [ ] Qualify Raise Ascender queue-disclosing writes natively, including complete-font dates/history/reopen, partial failures and both original scopes. Source repair does not close native preservation or deadline gates.

- [ ] Qualify Perpendicular Guides queue disclosure natively with complete font/history/reopen preservation and bounded finalization; source repair alone is not native acceptance.

- [ ] Qualify Perpendicular Guides partial-failure finalization and native interruption behavior, including whole-font history and deadline propagation; offline exception retention is verified separately.

- [ ] Qualify both background-clearing scopes natively after the queue-disclosure source repair: full-font history/reopen, dates, retained payload and bounded finalization.

- [ ] Qualify background clearing native interruption cleanup timing and complete-font history/reopen after the source interruption-finalization repair.

- [ ] Native-qualify additive selection with duplicate chart cells, filtered views, failures and full font/context preservation; source regression checks alone are insufficient.

- [ ] Native-qualify the no-UpdateAll select_glyphs/master_switcher change using p2_app.py part m1; its source repair is recorded, its native receipt remains open.

- [ ] Complete reviewed D12/D17 integration and independent downloaded R053 for
  the two additional tools; preserve the original130-sample acceptance count.

- [ ] The Vertical Metrics studio (`studios/vertical_metrics/calculate.py:271`) is the only production caller of `core.scripting.write_font_info` (`core/scripting.py:258`), which still ends in `native.UpdateAll()` (`:329`). Next check: migrate that caller to `metrics.master_writer` (no UpdateAll), then narrow or drop `write_font_info`; livetester native run of the Vertical Metrics studio on an owned fixture (one Undo row, Undo/Redo, saved and reopened).

- [ ] Qualify the reviewed documentation main workflow and generated-output identity; retain the owner hold on private Pages configuration and publication.

- [ ] TMetrics: decide whether an LSB change shifts guidelines (owner design decision).
- [ ] TGlyph: stop refitting on each live change before the first zoom or pan (needs live FontLab testing).
- [ ] TGlyph: read the glyph once per follow notification and match the current glyph beyond its name (multi-font behaviour unverified natively).
- [ ] TGlyph: qualify native smooth-only follow/redraw, exact selection/view retention, structural cancellation, history and saved reopen.
- [ ] TGlyph: coalesce auto-repeated nudges into one undo step (needs native Undo evidence).

- [ ] Reconcile the reviewed shared-pens candidate for Qt outline paths and area measurement with current direct source under the November 8 authority; qualify ordinary installed origins, relevant native explicit-layer/element consumers, full FONT/history, original sequential and reopen gates before adoption; follow the [Pens plan](../fontlab-python-pens/PLAN.md#task-6-consumer-migrations-and-adoption) and [tasks](../fontlab-python-pens/TODO.md).

- [ ] Qualify the delivered Kern Indicator correction in native drawing and the owner installation, preserving both junctions, signs, zoom limits and true-zero omission.
- [ ] Qualify the delivered Reporter stable-source/actual-exception-class policy in the native lifecycle with changing messages, replacement instances and distinct same-named classes; retain the existing bounded cache eviction/reset contract.
- [ ] Obtain native close/reopen evidence for the existing `NativeCanvasBackend.close` view-failure clearing and snapshot reset through the separately available native lane; do not infer a missing source fix.
- [ ] Qualify the Find Files directory sizing policy in native PythonQt with complete editing/history/popup paths; retain native chooser/search/cancellation, historical bytes-height and arbitrary font/style/display layout limits separately.

- [ ] Qualify Darwin batch socket output through installed native FontLab/Fontport: complete jobs and rows, cancellation, Close/destruction, child collection and endpoint/scratch release; qualify other supported platforms separately from the mocked non-Darwin PIPE branch.

- [ ] Qualify the required Pens 1.0.0 installed App/Fontport consumer tuple in the remaining native outline/selection workflows, with explicit layer/element targets and complete font/history/Undo/Redo/reopen preservation; keep the dated release-order note separate from current native adoption.

- [ ] Qualify the current eight-distribution App ordinary tuple and RECORD, refresh only necessary consumer locks and run the current normal gate; public Pens v1.0.0 tagging and the App pre-push Pens recipe are already present, while native adoption remains separate.

- [ ] Studios (Issue 242 Phase D T29): natively qualify one labelled Undo step per Apply for every studio, including Component Studio builder/decompose deep history, Derived Glyphs per-glyph creation steps, Advance Widths/Anchor Transfer cross-font transactions and Vertical Metrics route-A master writers; then Undo/Redo and saved reopen.
- [ ] Studios: add the About/credits tab (Issue 242 Phase D plan §1.7) to the studios from Phase D T2 onward.

- [ ] Qualify Issue 234 keyed Tool capture and component opt-in with matching installed inspection Tools in a permitted owned native session.

- [ ] Qualify truthful containing commits, immutable source links, native workflows and later integrated tuples for the eight source-qualified implementations without treating them as eight fully accepted workflows; preserve finite accepted A0/I1 ordinary evidence for its exact older bytes.
- [ ] Qualify whole Task12/native teardown and complete owned-font/history preservation; finite A0/I1 source and ordinary cleanup evidence does not close the native gate.
- [ ] Implement source for the remaining ten compositions in the minimum eighteen, in reviewed A1–A4 order; qualify all workflows and retain all 8,723 compatibility obligations and the 18-or-more floor.
- [ ] Generate and qualify new catalogue pages at a genuine committed source revision; no old-SHA links to new uncommitted paths.

- [ ] For a reproduced upstream FontLab gap in these workflows, retain a privacy-safe reproducer, file or extend the fl issue and link a required fix PR in the proven responsible Proteus, FontGate or pyfontgate repository; preserve native safety and ownership gates.

- [ ] Bind the accepted A0/I1 payload to reviewed containing commits and truthful source links; requalify any later changed payload.
- [ ] Qualify Tabular Width Audit native painting, history, cleanup and whole-font preservation in an admitted owned lane.

- [ ] Qualify one matched A1 batch of complete private archives, genuine wheel/sdist and two fresh ordinary prefixes, including real installed Kerning Proof and Kerning Group Explorer workflows, exact origins/RECORD and retained regression/coverage gates; keep #8/#9 ordinary acceptance pending until then.
- [ ] Qualify Kerning Proof native target/master, painting, whole-font and unrelated-font preservation, history, Undo/Redo, save/reopen and cleanup in an admitted owned lane; retain separate containing-commit, canonical, owner-installation, delivery and publication gates.
- [ ] Qualify Kerning Group Explorer native captured-font/current-master behavior, both previews, group-policy refusals, exact Apply/readback, four-owner cleanup, whole-font/history preservation, Undo/Redo and save/reopen; retain separate containing-commit, canonical and publication gates.
- [ ] Qualify full literal-U+2029 editing separately; do not count refusal as a successful edit or standalone Qt6 as native PythonQt5 acceptance.
- [ ] Complete #17 P2 post-change graph, exact ledger/source qualification and staged review; refresh actual main, reconcile intervening changes, qualify genuine-commit docs, then verify normal hooked main delivery, exact-commit CI and generated-output lineage.
- [ ] Qualify #17 P2 matching ordinary artifacts, two fresh prefixes and archives, then its actual consumer/native/history/Undo/Redo/reopen checks; retain recipe-only No Font, complete input/output preservation, distinct cleanup ACKs and actual terminal worker cleanup. Keep wider literal-U+2029 feature editing, canonical adoption, publication and private Pages holds as separate workflow gates.

- [ ] Kerning: deleting a pair whose class has a missing member (stale subset-font class) is still refused; relax only if users need it.
- [ ] Native: after the drag-distance fix lands in the installed App, the owner runs a real OS drag from each of the six E06 handles (deferred_glyph_report, draggable_glyph_names, font_drop_inspector, font_file_drop_shelf, glyph_pair_board, proof_word_magnets) into a Glyph window text bar or the Finder and confirms the payload; also an OS-level star click in Glyph Review Priorities.
- [ ] Low priority: one TMetrics kerning edit (and Fontport empty-layer writes, Suffix Substitution) shows two Undo rows with the same label, one data row plus a no-op, because the pre+post notify is kept (round 11); data is exact at every step (report 16 rows 2b, 7b; report 17). Either accept it or revisit a single notify for kerning only.
- [ ] Make the `fl.font` fakes in `tests/test_perpendicular_guides_selection.py` realistic: the live legacy `FL.fl.font` has no `.id` (the fakes set `fl.font.id = 98`); implementer2 is removing `.id` from legacy fakes, so reconcile after that lands.
- [ ] Stem Blend with the same glyph's own Glyph editor open (livetester): Apply on an owned fixture while that glyph's editor is open; check one Undo row "Stem Blend", exact nodes, Redo and reopen. Report 15 W2 covered only an editor open in a different font. If this fails, add `window=` to the `create_layer` history commit (the editor guard) in `src/fontlabapp/fontui/teaching_writers/stem_blend.py`.
- [ ] Owner-run native: install, reinstall and uninstall with the WP11A `install.vfpy` in a real FontLab 9 user folder (superseded-distribution cleanup, I-4..I-11 paths, user-folder preservation on reinstall). Agents must not touch the owner's user folder; run only against an owned temporary user folder if FontLab can be pointed at one without changing owner preferences.
- [ ] Native draft, reviewed: not yet fileable; needs a native repro (plain FontLab Python or the Font menu, shareable fixture), Regular-only master scope and inline evidence, reworked by livetester: Redo of Add Glyph does not rebuild the automatic layers that Add Glyph rebuilt (stale until reopen); draft `fl-issue-drafts/r18-redo-add-glyph-auto-layers.md` is not filed.
- [ ] Low priority F19-1: feature Undo did nothing once (fid 10645, report 19; `ss01` stayed after both Undos); not reproduced in 3 variants (report 21 section 3); recheck if seen again, no fl issue until reproduced. If it recurs capture: font id, the active font, the history rows before and after Undo (including `checkInitHistoryState` and the features-container history), and whether the features were written through the App or through FontLab.
- [ ] Text Editors Lab header shows "unshaped: uharfbuzz not available" in FontLab 9 (A2 report 21): the FontLab Python environment has no uharfbuzz, so the shaped preview falls back. Decide whether to document it or ship the dependency; not a defect in the lab.
- [ ] Native: verify the stale-class-member kerning fix in a real subset font, then save and reopen it.
- [ ] Native: verify in FontLab PythonQt that the QPoint/QEvent wrapper reads now routed through `value()` (drag-distance `x`/`y` in six drag profiles; `type`/`key`/`pos().x()`/`rect.left`/`width` in Glyph Review Priorities) return numbers, not bound methods, and that drag start and star click/Delete/Backspace work.
- [ ] Examples R gate: `tests/test_issue122_E10.py::test_entry_uses_existing_host_application` fails under the installed App for Font Name Encoding Audit, Localized Font Names and Font Info Snapshot (passes in the core run). Repro: from the Examples checkout run `PYTHONPATH=../fontlab-fly/src:$PWD/tests QT_QPA_PLATFORM=offscreen <venv>/bin/python -B -m pytest -q -p no:cacheprovider tests/test_issue122_E10.py -k test_entry_uses_existing_host_application` with the installed App wheel; find why the installed-path entry no longer resolves to the host application.
