---
this_file: src_docs/md/installation.md
---

# Installation and host use

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

User scripts, examples and the optional startup block require FontLab Fly 1.3.0
or later in the same interpreter. Libraries retain canonical provider imports
without a mandatory Fly dependency.

The source installer copies Scripts and writes App's owned startup block, but
does not install or check Fly. Install
[Fly and its matching providers](https://github.com/fontlabcom/fontlab-fly#install)
separately in the same interpreter before running these consumers or relying on
plugin startup. A missing Fly import makes the startup block print
`FontLab plugins startup:` and skip activation.

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
