# this_file: Scripts/Utilities/Plugmix Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Install Plugmix and list its reporters, filters, palettes, tools and commands.

What: Calls fontlabapp.plugins.boot.install, which adds Plugmix's View, Glyph
and Window actions (fontlabapp.plugins.menu, fontlabapp.plugins.backend), then
lists every plugin that fontlabapp.plugins.registry discovers, grouped by kind
(fontlabapp.plugins.kinds): reporters (fontlabapp.plugins.reporter,
fontlabapp.plugins.plugins), filters (fontlabapp.plugins.filter,
fontlabapp.plugins.filters), palettes (fontlabapp.plugins.palette,
fontlabapp.plugins.palettes), tools (fontlabapp.plugins.tool,
fontlabapp.plugins.tools) and General commands (fontlabapp.plugins.general,
fontlabapp.plugins.general_plugins), all based on fontlabapp.plugins.plugin.
Extensions bundles use fontlabapp.plugins.bundles; the shared
Reporters panel is fontlabapp.plugins.reporters_panel, and the removable startup
hook is fontlabapp.plugins.startup.
Reporters draw from one read-only snapshot per paint
(fontlabapp.plugins.snapshot, shapes from fontlabapp.plugins.geometry). It
reads the glyph's name, unicodes, mark and export flag
(fontlabapp.glyphs.identity), its background (fontlabapp.glyphs.background),
its components and owner master (fontlabapp.components.decompose), its kerning
classes (fontlabapp.kerning.groups) and other glyphs by name
(fontlabapp.glyphs.others).
Use: Run it once per session, then tick reporters under View > Reporters. The
message lists each plugin's title and marks the reporters already enabled.
Safety: Installing adds menu actions and painters only; no font, master,
selection or history changes. Plugmix writes one preference file,
fontlab-plugmix.json, when you tick or untick a plugin. Running it again does
not install twice.
"""

TITLE = "Plugmix Demo"
KINDS = ("reporter", "filter", "palette", "tool", "general")


def main() -> None:
    """Install Plugmix, then show the discovered plugins by kind."""
    import fly
    from fly.ap.plugins import registry
    from fly.ap.plugins.boot import install
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    try:
        install()
    except (ValueError, RuntimeError, ImportError) as error:
        run_standard_message_box(qt, parent, TITLE, f"Plugmix did not install: {error}", "Warning", kind.Ok)
        return
    enabled = set(registry.enabled())
    lines = []
    for name in KINDS:
        found = registry.available(name)
        lines.append(f"{name.title()}s ({len(found)}):")
        lines += [f"  {cls.title}{' (on)' if key in enabled else ''}" for key, cls in sorted(found.items())]
    run_standard_message_box(qt, parent, TITLE, "\n".join(lines), "Information", kind.Ok)


if __name__ == "__main__":
    main()
