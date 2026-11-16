---
this_file: AGENTS.md
---
Managed local packages need origin protection as well as version constraints: retain the installed distribution and reject wheel/source replacement through uv's scoped package controls, including transitive direct references. Qualify both interpreter and target modes with actual resolver fixtures.

## Shared installer dependency qualification — 2026-11-15

Keep original dependency requirements through sibling installation and let uv resolve versions, extras and markers. Preserve installer-managed local versions with temporary constraints, including active-cycle records. Generated local metadata must advertise optional dependencies. Without uv, only installed bare names can be proved; refuse unverifiable requirements before destructive replacement. Record ownership before fallible dependency execution. Focused source checks do not establish shared-copy propagation, release, installation or FontLab acceptance.

## Owner priority: functional progress first (2026-11-15)

Future agents must make large, swift advances in working functionality. Prioritize visible user problems and useful, coherent feature increments. This instruction sets the work order and supersedes older requirements to complete exhaustive testing or build test infrastructure before ordinary implementation.

Keep packages coherent and compatible. Check shared APIs, imports and lazy aliases, data formats, dependency direction, object ownership and lifetime, installers, launchers and examples. Update affected providers and consumers together; preserve existing supported behavior and avoid dependency cycles.

During implementation, use the smallest meaningful smoke checks and focused regression tests for the changed behavior and affected package boundaries. Detailed testing, exhaustive coverage, broad performance studies and full acceptance matrices can follow in a later testing pass. Do not let test harnesses, sandbox/supervisor design, repeated unchanged suites, evidence machinery or review paperwork become the main project. Build such infrastructure only when a concrete functional defect or necessary safety constraint requires it.

Record deferred checks and known limits plainly. Do not call untested native, installed or published behavior verified. Keep existing mandatory delivery hooks, preservation rules, licence/privacy obligations, repository exclusions and explicit native/publication holds intact. When one action is held, continue other authorized functional work instead of expanding unrelated infrastructure.

Choose the next substantial useful feature or shared fix and carry its affected providers and consumers together. Timebox supporting investigation; once focused checks establish a usable increment, continue functionality work. Queue detailed testing for a later pass with its concrete remaining checks instead of letting test infrastructure displace product delivery.


## Current scope — 2026-11-05

Issue 230 documentation reconciliation is current. Issue 123 remains paused. The qualified Issue 207 isolated candidate is separate from canonical source, installed artifacts, native acceptance and publication. Reconcile that candidate with later work before integration. Issue 210 specifies future architecture; Issue 211 retains unfinished follow-up checks. Retained dated receipts describe their original source and acceptance surface only.

Canonical source inspected for this proposal: `6c48291ca654`. This is a dated source observation, not an installed or native acceptance claim.

Implement Issue 210 in an isolated successor: framework and lifecycle in `src/fontlabapp/plugins`, concrete plugins in Plugmix Extensions, and migrate all callers together.

Complete Issue 211 native probes and four minor fixes with independent regression review; reconcile Issue 207 before integrating over current Issue 208/209/M12 code.

## Organization and checks

`src/fontlabapp/` owns domain packages; `Scripts/` holds package demonstrations; `tests/` contains source and offline UI checks; `examples/` holds external/native drivers. Current plugins live in `src/fontlabapp/plugmix/`, with tests in `tests/plugmix/`.

Use README Testing to prepare arm64 Python 3.11 with App[test], Fontport, Glyport and Fly. Run that interpreter with `python -B -m pytest -q -p no:cacheprovider`. `./test.sh` uses sibling Fontport/Glyport checkouts and Fly source when present; classify missing peers and skips.

## Issue 205 domain layout — 2026-11-03

The current request authorizes this source restructure; the older docs-only
handoff above is historical. Implementations live in core, qt, glyphs, proof,
fonts, masters, components, anchors, contours, metrics, kerning, guides,
features and hints. fontui and root public exports stay in place. New imports
use domain paths; _legacy preserves all 382 old module names plus three old
package names. Six domain packages lazily forward model reads/writes/deletes;
their moved models are separate normal modules with canonical metadata.
Keep child package names and dunders local, and preserve patch undo and reload.
tools/restructure.py and its mapping/templates document the historical one-off
migration; do not rerun it on the current tree. Keep it stdlib-only and free of
Git/index operations. Retain historical MIGRATION.json hashes.
The domain restructure is present in current canonical main. Native FontLab
and unchanged external caller suites remain separate acceptance surfaces.

# App working rules

Purpose: share FontLab application, UI, drawing and guarded editing mechanics.

- Use Python 3.11 arm64: `--python cpython-3.11-macos-aarch64-none`.
  No later syntax. General UI goes here; FontParts/UFO stays in Fontport;
  Glyphs.app emulation stays in Glyport. App never imports Glyport; optional
  Fontport imports are allowed only inside `src/fontlabapp/fontui/`. Scriptmix and Fly callers
  use `fly.ap`, including App's own `Scripts/` demos;
  offline callers use explicit `fly.ap` domain submodules to avoid native fallback.
  Libraries retain canonical provider imports to avoid dependency cycles; demos
  and teaching examples require FontLab Fly 1.3.0 or later in their interpreter.
- Use README Testing exports and commands below. Full pytest needs a prepared
  venv with App[test], Fontport and Glyport (with dependencies) and Fly installed
  `--no-deps` (its targets are unpublished). Fly on PYTHONPATH alone is
  insufficient. A fresh writable external cache and TMPDIR are prerequisites.
  Focused tests use App's test extra; lint uses
  Ruff 0.14.10 with `--no-cache --select F821 src tests Scripts`. No full lint gate exists.
- Native proof requires installed artifacts, asserted origins, owned fonts/widgets
  and a dedicated FontLab session. Compare complete font/history/dirty/cache state;
  writers need real Undo/Redo and saved reopen. Offline/Qt tests are not proof.
  Owner manages FontLab editable installs; preserve user fonts/preferences/Output.
- PythonQt widgets are in QtGui; QObject is in private. Call native event bases
  explicitly. Do not add attributes to raw wrappers or shadow native slots.
  Bind senders explicitly. Never create QApplication or load another Qt binary.
- Disconnect owned signals before deletion and after dispatch returns. Do not mix
  native-slot and bound-method receivers; wrap native slots. Use qtsafe.qt_list on
  the GUI thread. Catch paint errors and end painters in finally. Read only known
  Qt properties; unloaded SVG currentFrame can crash.
- Remopy's five-second limit does not stop abandoned code. Keep imports lazy and
  enforce in-host deadlines/cancellation. Never clear pending async exceptions.
- fontpr uses package.fgId: call scripting.font_id. Creation can replace existing
  layers: reject existing names. Do not add bare FontGate glyphs or read fgPackage
  from unregistered packages. Layer-role flags are properties; guide angles are
  radians; shape.selected differs from active. Metadata scans avoid glyph.fgGlyph.
- Disclose pending_updates and pending_note in writer results/status; queued ids
  alone do not block ordinary writes. require_settled is explicit opt-in only.
  Never normalise unrelated dates. Never notify auto layers or clear updatedFgGlyphs. Keep operation-specific
  owner/base guards; FL selection writes require an active Font window. Detached
  clones must retain raw Smooth bits and shape notes; inspect reopened node types.
  Refuse existing-anchor moves to (0, 0); new named pins need explicit appearance.
  Retain removed component objects with deep history. Zone serializer remains held.
- From an active Glyph window (canvas history), FontLab attaches a multi-glyph
  notifyChangesApplied Undo step only to the canvas glyphs; other glyphs keep
  the change, and new glyphs get no Undo (fl#8573, 9790). history.commit and
  create_glyphs refuse via edit_guards.require_history_scope; the eight App
  direct notifiers call it too (Glyport/Fontport host notifiers do not yet).
  Match canvas glyphs by font id and name: CurrentGlyph().id differs from the
  canvas slot id. Close Glyph windows before a .vfc save (fl#8572).
- Preserve canonical installs, owner edits, reference corpora and archived inputs.
  Read git with `GIT_OPTIONAL_LOCKS=0 /opt/homebrew/bin/git --no-optional-locks`.
  Git mutations, publication and deletion need explicit scope authorization.
- Plugmix (`src/fontlabapp/plugmix`, tests in `tests/plugmix`): keep glyph
  geometry and metrics reads in `snapshot.py`, canvas painter access in
  `backend.py` and startup imports in `boot.py`. Reporter `compute()` stays
  pure and FontLab-free. Never let an exception escape a paint or Qt signal
  callback. Use App's overlay and QAction ownership; do not duplicate its
  viewport polling or teardown. Write no font data; the only preference write
  is `fontlab-plugmix.json`. Import App code by domain path. Native FontLab
  tests need a host-equipped user.

```sh
uv venv --python cpython-3.11-macos-aarch64-none "$TMPDIR/app-venv"
uv pip install --python "$TMPDIR/app-venv/bin/python" -e '.[test]'
uv pip install --python "$TMPDIR/app-venv/bin/python" -e ../fontlab-fontport -e ../fontlab-glyport
uv pip install --python "$TMPDIR/app-venv/bin/python" --no-deps -e ../fontlab-fly
"$TMPDIR/app-venv/bin/python" -B -m pytest -q -p no:cacheprovider
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py tests/test_package_boundaries.py tests/test_tombstones.py
uv run --python cpython-3.11-macos-aarch64-none --no-project --with-editable '.[test]' python -B -m pytest -q -p no:cacheprovider tests/test_public_surface.py::test_readme_when_read_then_moved_table_names_every_tombstone
uv run --python cpython-3.11-macos-aarch64-none --no-project --with ruff==0.14.10 ruff check --no-cache --select F821 src tests Scripts
```

## Milestones and delivery

Read [PLAN.md](PLAN.md), [TODO.md](TODO.md) and [WORK.md](WORK.md) before work.
Make the smallest complete MVP for one named acceptance task. Find all callers,
tests, fixtures, exports and documentation first. Use graph impact before source
symbol edits; confirm stale or unknown graph results against current source.
Keep product work in isolated successors and preserve the owner's checkout.

Run this repository's exact checks and the unchanged 80% gate for each complete
changed production module. Use an independent review before a milestone commit.
Under the current owner task, commit and push reviewed, passing milestones;
verify remote heads rather than inferring delivery from local tracking refs.
Before main integration, reconcile concurrent work and all consumers, run graph
change analysis and repeat the required acceptance on the combined source.

Before removing obsolete branches or files, prove integration, retain recoverable
unique work and check fresh owner/worktree attachments. Preserve sealed reports,
licences, archives and private data. Do not rewrite history by implication.
Remove verified completed work from PLAN/TODO and record scoped evidence in
CHANGELOG. Keep implemented-only native/artifact checks open in TODO. Issue 123
remains paused; no instruction here authorizes driving the owner's FontLab,
installing into its user folder or publishing a site.

## Documentation source/build site

Author `src_docs/md/`; `docs/` is generated output. Keep both complete maintained guides and all catalogue/native qualifiers. Use a separate Python 3.13 hash-locked environment for `sh src_docs/build.sh` and `python -m unittest discover -s tests_docs -v`; host checks remain explicit arm64 Python 3.11. The every-main immutable X/Y workflow is build-only. Private Pages configuration, requests and deployment remain owner-held. Preserve complete generated-output parity, the actual source epoch and normal concurrent-update rejection.

## Integration rounds

After each round of important changes, integrate it into `main` and upstream:
fetch `origin/main`, build the change on top of it in an isolated branch or
worktree, and resolve conflicts by keeping both our work and teammates' work.
Never discard upstream commits, and never force-push. Run the repository's
checks on the merged result, then push to `origin main`. Record the change in
CHANGELOG.md, move verified-solved TODO.md items into CHANGELOG.md, update
PLAN.md, and continue with the next TODO.md item until the list is clear.
`install.vfpy` is shared: keep it byte-identical in every installer repository.

## Verified integration rounds — 2026-11-10

After each important independently reviewed round, recheck actual upstream
`main` and owner/worktree attachments. Fetch in a new isolated successor based
on current `origin/main`, merge the round's reviewed work, and resolve conflicts
by preserving both sides' intent, newer fixes and teammates' changes. Preserve
owner checkouts, branches, indexes, refs and configuration; never pull, switch
or rebase an owner's or another agent's active worktree. Stage only the exact
reviewed residual delta. Run the repository's applicable full suite, lint and
graph change gates on the combined tree, obtain independent merge review, then
commit and push under the current owner task's authority. Keep required hooks,
including the installed Dismisser pre-push gate, active; never bypass them or
force-push or rewrite history. Verify the actual remote head and required
main-triggered Actions; a local tracking ref is not delivery proof.

Move only evidenced solved tasks from future PLAN/TODO into cumulative
CHANGELOG, retaining every unrelated entry and placing new progress first. Keep
TODO flat and unchecked, update PLAN to remaining work, and continue the next
authorized task. Unverified native, SDK, UI, history, artifact, adoption and
publication checks stay open. The workspace root remains non-Git. Preserve
excluded repositories, recovery, licences and private data; this workflow does
not authorize FontLab installation or native operations, resume Issue 123, or
lift private Pages holds. Native upstream fixes use reviewed PRs to the
cause-appropriate Proteus, FontGate or pyfontgate repository.

## Isolated successors

Overrides generic bootstrap/MCP.

For graph work in an isolated successor, use the qualified installed CLI or backend with both `GITNEXUS_HOME` and `GITNEXUS_STORAGE_PATH` set to separate task-owned locations before the first invocation, including index discovery and analysis. A private storage path alone can still register the successor in global control files. During ordinary analysis, do not fall back to global MCP defaults, global `list-repos` or global setup/bootstrap, and do not make unreviewed global registry edits. Retain exact command/selected environment and before/after owned metadata; record expected task-owned `.git/info/exclude` additions and preserve unrelated state. If discovery or indexing escapes the owned scope, preserve evidence and obtain independent bounded control-file review before integration. Any necessary recovery must be separately reviewed, use fresh guarded current bytes and reviewed writer coordination, and change only the proven task-owned entry while preserving all other current records and bytes; never restore an old whole global registry.

## Agent workflow (Issue 250, 2026-11-10)

- Plan with `superpowers:subagent-driven-development`: one fresh implementer per task, a separate read-only reviewer, then the controller runs the gates and commits.
- Send bulk, well-specified work to Codex via the `codex-delegate` skill (`node ~/.agents/skills/codex-delegate/scripts/relay.mjs --brief BRIEF --cd WORKTREE`, in the background). Use `claude-delegate` or `cursor-delegate` for second opinions or independent lanes. Delegates never commit, push or tag.
- Work in a fresh worktree of `origin/main` on the workspace data volume; never pull, switch or reset the owner checkout. Merge `origin/main` again before pushing, keep both sides' CHANGELOG/PLAN/TODO entries, rerun the full suite, lint and graph change analysis, push through the pre-push hook where one is installed (never force), verify the remote SHA and the CI run where a workflow is configured. Held private Pages operations (workspace D41) stay held.
- Release: tag the next semver above the latest tag and publish a GitHub release. Install released, gated packages into `~/Library/Application Support/FontLab/FontLab 9/` and test live in FontLab 9. This owner route (Issue 250) supersedes, for released packages only, every older line in this guide that forbids installing into the FontLab user folder or its site-packages, owner-managed editable installs, or starting FontLab for a live test (the owner's canonical editable checkouts themselves stay owner-managed): record the previous installed distribution first so it can be restored, and never touch FontLab preferences (owner fonts and documents: see live font editing below); native work goes through the workspace `verification/issue-104/fl-native.sh` gate.
- Documents: CHANGELOG holds verified completed work; TODO only open or to-verify items; PLAN the major remaining changes; WORK.md the current round only (older WORK bytes are archived on the owner's workspace data volume, not public).
- Native defects: issues at github.com/fontlab/fl; fixes as pull requests to fontlab/Proteus, fontlab/FontGate or fontlab/pyfontgate. Never commit to the local C++ snapshot.
- Older "work directly" or "no delegation" lines in this guide are superseded by this section (Issue 250).
- Live font editing (owner, 2026-11-10; workspace D44): test, verify and edit the font open in FontLab 9, and do not stop because the owner might be working in it. Open a VFJ from `~/Desktop` first (those files are for agents), then add glyphs, kerning pairs, elements, contours, masters or whatever the test needs, and save them freely. This supersedes, for live testing, every older line here that forbids mutating owner fonts or documents or requires owned fixtures only. FontLab preferences, Output folders and global update queues stay untouched. Keep the serialized host lock (`fl-native.sh`, one native run at a time; `--mutating` now allows open fonts); do not quit or restart FontLab and do not close fonts from Python, which has crashed the host.
