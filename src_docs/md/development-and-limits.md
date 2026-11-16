---
this_file: src_docs/md/development-and-limits.md
---

# Development and limits

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

There is a separate `tests_docs/` suite for the documentation site. With the same exports, run the README migration contract and public-surface/dependency checks:

```sh
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py tests/test_package_boundaries.py tests/test_tombstones.py
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py::test_readme_when_read_then_moved_table_names_every_tombstone
uv run --python cpython-3.11-macos-aarch64-none --no-project --with ruff==0.14.10 ruff check --no-cache --select F821 src tests Scripts
```

The lint command checks undefined names; there is no configured full lint gate. Offline tests cover Python logic and doubles. Standalone Qt uses a different binding. Neither establishes native FontLab acceptance.

## Write boundaries and acceptance

History helpers preflight before mutation, initialize history, mutate, stamp, notify once and read back. `retain=` enrolls removed component objects with deep history. Failures after history starts raise `PartialWriteError` with Undo guidance; that guidance is not a guarantee of complete recovery.

Rename, Unicode and geometry edits refuse automatic-layer owners and automatic composite bases; explicit consent can allow supported base edits. Metadata edits refuse automatic-layer owners. Writers disclose queued ids and the possible modification-date changes (FontLab issue 8537); `history.commit` defaults to `settled=False` and always captures the queue once before writing. Its result supports `result["pending_updates"]` and `result["pending_note"]` (empty when no ids). Writers carry both fields to their results; panels append the stored note with `edit_guards.append_note`. Legacy scalar writers can fill a `disclosure` output dictionary or print the disclosure for console use. Use `edit_guards.pending_updates(native: Any = None) -> tuple[int, ...]` before a write and `pending_note(ids: Sequence[int]) -> str` in its status. `require_settled` remains an explicit opt-in refusal. `history.commit`, `glyph_creation.create_glyphs` and the eight App writers that notify directly call `edit_guards.require_history_scope`: with a Glyph window as the active canvas they refuse ("Switch to the Font window first…") unless every owner glyph (matched by font id and glyph name) is in that canvas and no glyph is new (FontLab issue 8573). Glyport and Fontport host notifiers are not guarded yet. Never notify an automatic layer, clear the queue or normalise unrelated dates. Existing-anchor moves to (0, 0) are refused because of a measured Redo defect. Clones must retain raw node flags, names and shape notes.

Font-level master writes use `font_history.commit_masters(package, title, {master: MasterEdit(save, write, read, verify, restore)})`. It refuses off the GUI thread and unless a Font window of the font is active (no Glyph window canvas; text "Activate the Font window before editing font masters."). It calls `checkInitHistoryState(0)` on the package and `mastersContainer()`, writes and reads back each master after `setMaster(name, False)`, restores the original master and sends ONE `notifyChangesApplied(title, [package, container], False)`. The result has `values`, `pending_updates` and `pending_note`. Unlike `history.commit`, a failure before the notification (also an interrupt, which is then re-raised) restores every written master and the original master and notifies nothing: `RolledBackError` (a `ValueError`) when the restore holds, `UnrestoredError` (a `PartialWriteError` with no Undo advice) when it does not or when the notification fails. Callers: `master_metrics.write_master_metrics(package, {master: {field: value}}, title)` for `ascender`, `descender`, `xHeight`, `capsHeight` and `lineGap` (`capHeight` is an alias of `capsHeight`; unknown fields and non-finite values are refused; double read-back tolerance 1e-9), and `zone_native.backend()`, the production `zone_editor.Backend` (Font Info's `convertZonesToGuidelines` + `updateZonesFromGuidelines`; the thread and Font-window guards run before any master switch; empty or repeated names and zero-width rows of the other kind raise `zone_native.RowRefusal`, and `Editor.add` names new rows as FontLab does (`T: 500`, `T: 500.1`); a zone rollback re-creates the zone guides with new ids and says so; a read-back gap after the commit raises `history.unstored_error`; it does not use the held serializer, fl#8554). The Alignment Zones panel stays usable after a `RowRefusal` or `RolledBackError` and locks after a stale source, `UnrestoredError` or a read-back gap. **Known FontLab defect:** after Undo or Redo of such a step, both masters show only the zone guidelines, not the six font-metric guidelines, until `updateFontMetrics()` runs or the font is reopened; the saved file is correct (9.0.9790, fl#8574). `select_glyphs` and `master_switcher.switch` call no `UpdateAll()`: it queued glyph ids and changed nothing visible.

Glyph creation uses `fontpr.set_glyph(create=True)` and checks the created result; existing names are refused before the call. Components for a new glyph travel in its creation data. Adding components to existing layers requires a qualified plain component prototype. Creation can use multiple native steps; do not promise one Undo for the whole workflow. Unmeasured automatic-layer rebuilding stays guarded.

Earlier releases have bounded native receipts in CHANGELOG. Those receipts do not qualify later shared writers or the full migration. Zone serializer ABI/payload preservation remains open; the route-A zone and metrics writers have no native receipt yet. Current text, NUL/IME, printer/OS, cache/history, font preservation and UI lifecycle holds are listed in [TODO](https://github.com/fontlabcom/fontlab-fontlabapp/blob/a5a8732e4cdf2cd5a5bfb75f51f33708868cdec3/TODO.md). Native proof requires installed artifacts in owned FontLab fixtures, exact source hashes, complete state comparison, real controls, Undo/Redo and saved reopening for writers. Source and standalone Qt checks do not qualify native behavior.


## Documentation builds

Use a separate Python 3.13 environment with the exact hash-locked `src_docs/requirements.txt`; run `sh src_docs/build.sh` and `python -m unittest discover -s tests_docs -v`. ProperDocs and MaterialX generate the site with light fltheme26 and local search. The every-main workflow builds source X and independently qualifies generated child Y using X’s epoch and source identity; unexpected tracked, ignored or untracked output and concurrent changes refuse publication. This is a generated-docs commit pipeline only. Private Pages configuration, requests and deployment remain owner-held.

## Preserved qualification boundaries

The complete [runtime reference](guides/runtime-reference.md) retains CurrentGlyph, editor, writer, Undo/Redo and native limitations. The [background tools guide](guides/background-family.md) retains the N86 HOLD and N92 rich-copy source-review blocker; all three workflows remain INCOMPLETE. Issue 123 remains paused and the zone/master lane remains reserved. The future Issue 210 architecture is not a supported current import. Ordinary source, sdist, complete-source harness, installed wheel, native behavior and publication are separate evidence surfaces.
