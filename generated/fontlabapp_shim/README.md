---
this_file: generated/fontlabapp_shim/README.md
---

# Static `fontlabapp_shim` package

This folder lives in fontlab-fontlabapp. Echopy no longer hosts it (issue 201); consumers read it from here.

| File | Content |
|---|---|
| `__init__.py` | Tiny lazy facade: attribute access imports `fontlabapp.core.host` (needs `fontlab-fontlabapp` inside FontLab); dunder probes and a missing `fontlabapp` raise `AttributeError` |
| `__init__.pyi` | Typed tree: one class per menu (73), every menu QAction (606 attributes), an `ActionPath` literal of all action keys, 38 panels, 72 Tools > Actions entries; docstrings carry path, shortcut, objectName, tooltip |
| `provenance.json` | Capture SHA-256, generator name/version, host version and command |
| `capture.json` | Read-only capture of FontLab 9.0.9783 (English UI, 2026-10-15) the stub was generated from |

The stub describes the objects `fontlabapp.core.host` builds at run time:
`menu.glyph.add_component()`, `actions["Glyph > Add Component"]`, `panels.preview.show()`,
`glyph_actions.remove_overlap(["B"])`. Names follow `fontlabapp.core.menu_names`; the generator
replays the capture through `fontlabapp.core.host.Host` itself, so stub and runtime agree.

## Privacy

Recent Fonts, Window > Windows & Tabs, Window > Panels > Custom Panels and the user's own
Script menu folders are captured as `dynamic` with their entries dropped on the host side
(`dropped` counts only). Six main-window QActions that belong to user scripts are dropped
too. The capture contains no paths, user or document names.

## Regenerate

Capture (read-only, owner session allowed), from the workspace root:

```sh
verification/issue-104/fl-native.sh --lane L6 -- uv run --project fontlab-remopy python \
  verification/issue-101-ecosystem/evidence/fontlabapp-104/capture_host.py \
  fontlab-fontlabapp/generated/fontlabapp_shim/capture.json
```

Generate (offline, deterministic: same capture and generator version give the same bytes), from `fontlab-fontlabapp/`:

```sh
uv run python -m fontlabapp.core.shimgen generated/fontlabapp_shim/capture.json \
  generated/fontlabapp_shim
```

`tests/test_shimgen.py` fails when the delivered files are stale or a stub name does not
resolve in the replayed tree.
