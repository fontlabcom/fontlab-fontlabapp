# this_file: Scripts/Font Editors/Fontui Helpers Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Run App's pure fontui helpers on made-up data and explain the host ones.

What: Shows, in one message box, the results of the host-free helpers behind
the fontui controls: fontlabapp.fontui.model (font list labels, glyph name
filter state, the drawing viewport and the open-contour split),
fontlabapp.fontui.wrap (line wrapping of a placed run) and
fontlabapp.fontui.features_state (feature block staging with its line-ending
rules). It also names what fontlabapp.fontui.feature_blocks (the exact VFJ
source reader and writer of the active FontLab font) and
fontlabapp.fontui.lifecycle (owned widget lifetime and the change signals the
controls follow) provide, without calling them. The studio apps build on
fontlabapp.fontui.appshell (the window shell with preview, tabs, status line
and guarded history), fontlabapp.fontui.table (the sortable glyph list) and
fontlabapp.fontui.hinting (the hinted-layer guard); this demo names them only.
The Examples Labs menu demonstrates fontlabapp.fontui.teaching (the shared
Close-acknowledged host, file search and image profiles),
fontlabapp.fontui.teaching_painter (SVG, sketch and polygon tools),
fontlabapp.fontui.teaching_graph (dependency and feature graphs),
fontlabapp.fontui.teaching_text (editors, snapshots and scripting),
fontlabapp.fontui.teaching_writers (the existing guarded editing lessons), and
fontlabapp.fontui.getgo_labs (verified GetGo lesson controls). Their show
entrypoints create real task windows; this read-only helper demo names them
without opening them or performing their writes. Use the named Examples Labs
launchers to explore those complete controls individually.
Use: Run it from the Scripts menu and click Show Details. No font is needed.
Safety: Nothing is read from a font or written. The inputs are literals in this
script. The two reader and writer functions of feature_blocks are only listed,
because they work on the active FontLab font and the writer changes it. The
lifecycle module is only imported for its constants; no widget, timer or signal
is created and nothing is connected. No font, master, selection, history,
preference, Output or clipboard is read or written and no file is touched. The
only window is the message box.
"""

from types import SimpleNamespace

TITLE = "Fontui Helpers Demo"
CRLF_PREFIX = "languagesystem DFLT dflt;\r\n"
CRLF_KERN = "feature kern {\r\n} kern;\r\n"
EDITED_KERN = "feature kern {\n    pos A V -80;\n} kern;\n"


def notify(title: str, text: str, details: str = "") -> None:
    """Show one modal message box owned by this call."""
    import fly
    from fly.ap.qt.dialogs import create_message_box, run_message_box

    qt = fly.qt
    box = create_message_box(qt.QtGui, title, text, "Information", (fly.fl.MainWindow(),), detail=details)
    box.setWindowTitle(title)
    run_message_box(box, qt.QtGui.QMessageBox.Ok)


def model_lines() -> list[str]:
    """Labels, name filtering, the drawing viewport and the open-contour split."""
    from fly.ap.fontui.model import BrowserState, FontListState, partition_paths, viewport

    named = SimpleNamespace(info=SimpleNamespace(familyName="Demo Sans", styleName="Bold"), path="Demo-Bold.ufo", dirty=True)
    unnamed = SimpleNamespace(info=SimpleNamespace(familyName=None, styleName=None))
    fonts = FontListState([unnamed, named])
    before = fonts.labels
    fonts.sort()
    browser = BrowserState({"A": 1, "Aacute": 2, "B": 3})
    browser.filter("a")
    filtered = browser.names
    browser.select(["Aacute", "missing"])
    scale, x, y = viewport((0, 0, 600, 700), 600, -200, 800, 400, 300)
    recording = [("moveTo", ((0, 0),)), ("lineTo", ((9, 9),)), ("closePath", ()), ("moveTo", ((5, 5),)), ("lineTo", ((6, 6),)), ("endPath", ())]
    closed, opened = partition_paths(recording)
    return [
        f"FontListState labels: {list(before)}",
        f"  after sort(): {list(fonts.labels)}",
        f"BrowserState names {list(browser.original)}, filter('a') -> {list(filtered)}, select(['Aacute', 'missing']) -> {list(browser.selected)}",
        f"viewport(bounds (0, 0, 600, 700), advance 600, descender -200, ascender 800, view 400 x 300): scale {scale:g}, x {x:g}, y {y:g}",
        f"partition_paths: {len(closed)} commands in closed paths, {len(opened)} in open paths",
    ]


def wrap_lines() -> list[str]:
    """Wrap five placed glyphs of advance 400 into lines no wider than 1000."""
    from fly.ap.fontui.wrap import wrap

    run = [SimpleNamespace(x=400 * index, advance=400) for index in range(5)]
    return [f"wrap(5 glyphs of advance 400, width 1000, 'ltr') -> {wrap(run, 1000, 'ltr')}", f"wrap(..., width None) -> {wrap(run, None, 'ltr')}"]


def state_lines() -> list[str]:
    """Stage an edit of a CRLF block, add a feature, and refuse mixed endings."""
    from fly.ap.fontui.features_state import PREFIX, FeatureState, line_ending

    state = FeatureState({"prefix": CRLF_PREFIX, "features": [("kern", CRLF_KERN)]})
    state.set_text("kern", EDITED_KERN)
    state.add("liga")
    crlf, lf, mixed = "a\r\nb", "a\nb", "a\r\nb\n"
    result = [
        f"line_ending: {crlf!r} -> {line_ending(crlf)!r}, {lf!r} -> {line_ending(lf)!r}, {mixed!r} -> {line_ending(mixed)!r}",
        f"keys {state.keys()}, dirty {state.dirty}",
        f"kern stays CRLF after the edit: {state.raw('kern')!r}",
        f"whole_text: {state.whole_text()!r}",
    ]
    try:
        FeatureState({"prefix": "a\r\nb\n", "features": []}).set_text(PREFIX, "x")
    except ValueError as error:
        result.append(f"Mixed line endings are refused: {error}")
    return result


def blocks_lines() -> list[str]:
    """Name the reader and writer; do not call them."""
    from fly.ap.fontui import feature_blocks

    return [f"fontlabapp.fontui.feature_blocks exports {', '.join(feature_blocks.__all__)}.", "Both work on the active FontLab font through Fontport; the demo does not call them."]


def lifecycle_lines() -> list[str]:
    """The change signals and timing the controls follow; nothing is connected."""
    from fly.ap.fontui import lifecycle

    return [
        f"fontlabapp.fontui.lifecycle follows {', '.join(lifecycle.CHANGE_SIGNALS)} and the actions {', '.join(lifecycle.HISTORY_ACTIONS)}.",
        f"A first change arms one {lifecycle.CHANGE_DELAY_MS} ms timer; the control then refreshes once.",
        "Owned closes by disconnecting every connection it made, then hiding and deleting its widget.",
    ]


SECTIONS = (
    ("fontui.model", model_lines),
    ("fontui.wrap", wrap_lines),
    ("fontui.features_state", state_lines),
    ("fontui.feature_blocks", blocks_lines),
    ("fontui.lifecycle", lifecycle_lines),
)


def report() -> list[str]:
    """Every section under its title, one after the other."""
    lines: list[str] = []
    for title, build in SECTIONS:
        lines += [f"== {title} ==", *build(), ""]
    return lines


def main() -> None:
    """Show the sections; no font is needed."""
    notify(TITLE, "Sample fontui helper results. Nothing was read or written.", "\n".join(report()).rstrip())


if __name__ == "__main__":
    main()
