# this_file: Scripts/Utilities/Core Utilities Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Tour fontlabapp.core, its root shims and its pure helpers in one report.

What: Opens a message box whose details (1) name the open fonts through
fontlabapp.core.controls and scripting, (2) summarise each fontlabapp.core
module (application, host, hotkey, signals, scripting, history, edit_guards,
completion, controls, utils, menu_names, native_tabs, legacy, shimgen), (3) resolve every name
of the root shims fontlabapp.menus, objects, qtsafe_api, shortcuts and signals
to the module that defines it, (4) read the native queue of pending glyph
updates and (5) run the host-free helpers (menu_names, utils) on sample text.
Use: Run it from the Scripts menu. Click Show Details for the full report.
Safety: Read-only. It imports modules, reads the open-font list and the update
queue, and computes on its own sample data. The queue is never cleared, no
dialog or hotkey manager is created, and no font, selection, history,
preference, Output or clipboard is changed.
"""

_BOXES: list = []  # modeless boxes stay referenced until the user closes them
CORE_MODULES = (
    "fly.ap.core.application", "fly.ap.core.host", "fly.ap.core.hotkey",
    "fly.ap.core.signals", "fly.ap.core.scripting", "fly.ap.core.history",
    "fly.ap.core.edit_guards", "fly.ap.core.completion", "fly.ap.core.controls",
    "fly.ap.core.utils", "fly.ap.core.menu_names", "fly.ap.core.native_tabs",
    "fly.ap.core.legacy", "fly.ap.core.shimgen",
)
SHIMS = (
    "fly.ap.menus", "fly.ap.objects", "fly.ap.qtsafe_api",
    "fly.ap.shortcuts", "fly.ap.signals",
)


def first_line(module) -> str:
    """The first docstring line of ``module`` (empty when it has none)."""
    return ((module.__doc__ or "").strip().splitlines() or [""])[0]


def core_lines(import_module) -> list[str]:
    """One line per fontlabapp.core module: public name count and summary."""
    lines = []
    for dotted in CORE_MODULES:
        name = dotted.removeprefix("fly.ap.core.").removeprefix("fontlabapp.core.")
        module = import_module(dotted)
        public = getattr(module, "__all__", None) or [n for n in vars(module) if not n.startswith("_")]
        lines.append(f"core.{name} ({len(public)} public names): {first_line(module)}")
    return lines


def shim_lines(import_module) -> list[str]:
    """Resolve each shim name lazily and name the module that defines it."""
    lines = []
    for dotted in SHIMS:
        shim = dotted.removeprefix("fly.ap.").removeprefix("fontlabapp.")
        module = import_module(dotted)
        for name in module.__all__:
            try:
                origin = getattr(getattr(module, name), "__module__", None) or "a constant"
            except Exception as error:  # an optional dependency of that module may be missing
                origin = f"unavailable ({type(error).__name__}: {error})"
            lines.append(f"{shim}.{name} -> {origin}")
    return lines


def font_lines(app, control_type, current_package, font_id) -> list[str]:
    """Open fonts from fontpr and the current package id, both read-only."""
    with control_type(application=app) as control:
        fonts = control.fonts()
    package = current_package()
    current = "no font open" if package is None else f"current font id {font_id(package)}"
    return [f"Open fonts: {len(fonts)}; {current}"] + [f"  {font}"[:100] for font in fonts]


def queue_lines(pending_updates, pending_note) -> list[str]:
    """Read the pending native glyph-update ids once; never clear them."""
    ids = pending_updates()
    return [f"Pending glyph updates: {len(ids)}", pending_note(ids) or "No pending-update note."]


def helper_lines(clean_label, snake, assign_names, slugify, deepmerge, attribdict, stringify) -> list[str]:
    """Run the pure helpers on sample data of this demo's own."""
    names = assign_names([("Save", "actionSave", True), ("Save...", "actionSave_As", True)])
    merged = deepmerge({"a": {"b": 1}}, {"a": {"c": 2}})
    return [
        f"clean_label('Open &Recent...\\tCtrl+R') = {clean_label('Open &Recent...' + chr(9) + 'Ctrl+R')!r}",
        f"snake('Glyph && Metrics...') = {snake('Glyph && Metrics...')!r}",
        f"assign_names(Save, Save...) = {names!r}",
        f"slugify('Cafe Noir Bold!') = {slugify('Cafe Noir Bold!')!r}",
        f"deepmerge({{'a': {{'b': 1}}}}, {{'a': {{'c': 2}}}}) = {merged!r}",
        f"attribdict({{'x': 1}}).x = {attribdict({'x': 1}).x!r}",
        f"stringify(b'bytes') = {stringify(b'bytes')!r}",
    ]


def show_report(app, title: str, summary: str, lines: list[str]) -> None:
    """Show the report as a modeless, owned message box with selectable details."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, release_closed_message_boxes, show_message_box

    release_closed_message_boxes(_BOXES)
    box = create_message_box(fly.qt.QtGui, title, summary, "Information", (app.main,), detail="\n".join(lines))

    def configure(current) -> None:
        current.setWindowTitle(title)

    show_message_box(box, _BOXES, configure)


def main() -> None:
    """Gather the five read-only sections and show them."""
    from importlib import import_module

    from fly.ap.core.application.context import Application
    from fly.ap.core.controls import FontLab
    from fly.ap.core.edit_guards import pending_note, pending_updates
    from fly.ap.core.menu_names import assign_names, clean_label, snake
    from fly.ap.core.scripting import current_package, font_id
    from fly.ap.core.utils.collections import attribdict
    from fly.ap.core.utils.json import stringify
    from fly.ap.core.utils.merge import deepmerge
    from fly.ap.core.utils.text import slugify

    app = Application(with_ui=False, with_preflib=False)
    sections = (
        ("Fonts", font_lines(app, FontLab, current_package, font_id)),
        ("Core modules", core_lines(import_module)),
        ("Root shims", shim_lines(import_module)),
        ("Native update queue", queue_lines(pending_updates, pending_note)),
        ("Helpers on sample data", helper_lines(clean_label, snake, assign_names, slugify, deepmerge, attribdict, stringify)),
    )
    lines = [line for title, body in sections for line in [title + ":", *body, ""]]
    show_report(app, "Core Utilities Demo", "Click Show Details for the full report.", lines)


if __name__ == "__main__":
    main()
