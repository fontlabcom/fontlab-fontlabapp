# this_file: src/fontlabapp/studios/component_studio/build.py
# SPDX-License-Identifier: Apache-2.0
"""Build tab (Build From Recipes, with Dump Component Recipes as "Dump from selection").

The original's rules are kept unchanged (``Line``, ``Result``, ``parse``,
``data_tool``, ``build``, ``check_lines``): one recipe per line,
``target = base + mark@anchor`` (``@acute`` without brackets names both
anchors, ``@acute[_acute]``); ``#`` starts a comment. Check runs FontLab's
own builder (``build_glyph``) as a dry run on every line and master; it
does not run on open, because the builder can refresh glyph data. A line
with NUL, no-break space or line/paragraph separators is refused; a
target that owns auto layers or is a base of an auto composite is refused
(no opt-in, as in the original). "Masters": current master (default) or
all; "Replace existing layers" is off by default. Build is enabled only
after Check with every row ready; any change asks for Check again.

Build keeps the original's builder route. The empty master layers the
builds need are added first as ONE ``Component Studio: add master layers
<subject>`` Undo step through ``AppShell.history``. Each layer is then built
by FontLab's ``build_glyph`` data tool with ``auto_layer=False``, as in the
original; that tool records its own history, so ``AppShell.history`` cannot
wrap it and the builder's Undo is FontLab's (native history is qualified
in T29). A new glyph is built on its first master; press Build again for
the others.

"Dump from selection" (Dump Component Recipes) only reads: it captures the
selected Font/Glyph-window layers and shows their ``base+base=glyph``
recipes verbatim in a read-only box (copy it from there); it writes
nothing and opens no history. The dump format is the original's and is not
the Build syntax, so it is never pasted into the recipe editor.
"""

import re
from dataclasses import dataclass
from typing import Any

from PythonQt import QtGui

import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning import NO_FONT
from .._kerning_ui import button, check, get
from .._kerning_ui import label as text_label
from . import _shared

#: The original's module names, read by the verbatim functions below.
component_writer = _shared.Modules("components")
pr = _shared.Modules("pr")
recipes_model = _shared.Modules("recipes")

EXAMPLE = "Aacute.alt = A + acute@acute\n"
# "@acute" without brackets names both anchors: "@acute[_acute]".
ATTACH = re.compile(r"@([A-Za-z_][A-Za-z0-9_.-]*)(?!\[)(?=$|[+&])")
GLYPH_NAME = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.-]*$")
# PythonQt text conversion can drop or change these; refuse them.
UNSAFE_TEXT = {"\x00": "NUL", "\xa0": "no-break space", " ": "line separator",
               " ": "paragraph separator"}  # fmt: skip
LAYER_MISSING = "Target layer not found."


# ---------------------------------------------------------------- verbatim original
# Build From Recipes
@dataclass(frozen=True)
class Line:
    """One recipe line. `problem` set: the line cannot be built."""

    number: int
    target: str
    recipe: str
    problem: str = ""


@dataclass(frozen=True)
class Result:
    """Verdict for one target layer. `adds_layer`: the glyph lacks this layer."""

    target: str
    master: str
    recipe: str
    ok: bool
    message: str
    adds_layer: bool = False


def parse(text: str) -> list[Line]:
    """Non-empty lines as `Line` records. '#' starts a comment."""
    lines: list[Line] = []
    for number, raw in enumerate(text.splitlines(), 1):
        unsafe = sorted({label for char, label in UNSAFE_TEXT.items() if char in raw})
        line = raw.split("#", 1)[0].strip()
        if unsafe:
            lines.append(Line(number, line, "", f"remove the {', '.join(unsafe)}"))
            continue
        if not line:
            continue
        if "=" not in line:
            lines.append(Line(number, line, "", "use: target = base + mark@anchor"))
            continue
        target, recipe = (part.strip() for part in line.split("=", 1))
        recipe = ATTACH.sub(lambda m: f"@{m[1]}[_{m[1]}]", re.sub(r"\s+", "", recipe))
        problem = ""
        if not target or not recipe:
            problem = "empty target or recipe"
        elif not GLYPH_NAME.match(target):
            problem = f"{target} is not a valid glyph name"
        lines.append(Line(number, target, "=" + recipe if recipe else "", problem))
    return lines


def data_tool(tool: str, **arguments: Any) -> Any:
    """Call one of FontLab's own data tools in-process (fly.pr is native fontpr)."""
    return pr.call(tool, **arguments)


def build(
    package: Any,
    line: Line,
    master: str,
    replace: bool,
    dry_run: bool,
) -> tuple[bool, str]:
    """Build (or only validate) one target layer. Returns (ok, message).

    Never an auto layer: FontLab's builder notifies the glyph deeply, and an
    auto layer there rebuilds every default-recipe auto layer in the font.
    """
    arguments = {
        "font_id": scripting.font_id(package),  # fontpr finds fonts by fgId
        "glyph_name": line.target,
        "recipe": line.recipe,
        "layer_name": master,
        "replace": replace,
        "auto_layer": False,
        "dry_run": dry_run,
    }
    try:
        result = data_tool("build_glyph", **arguments)
    except Exception as error:  # noqa: BLE001 - FontLab's text goes to the table
        return False, str(error).strip() or type(error).__name__
    if not isinstance(result, dict) or result.get("status") not in {"ok", "validated"}:
        if isinstance(result, dict):
            return False, str(result.get("error") or result.get("message") or result)
        return False, str(result)
    parts = " + ".join(
        str(c.get("glyph_name")) for c in result.get("resolved_components", [])
    )
    verb = "valid" if dry_run else ("created" if result.get("created") else "built")
    return True, f"{verb}: {parts}"


def check_lines(
    package: Any,
    lines: list[Line],
    masters: list[str],
    replace: bool,
    facts: history.AutoFacts,
) -> list[Result]:
    """Dry-run every line on every master. Nothing in the font changes."""
    results: list[Result] = []
    for line in lines:
        if line.problem:
            results.append(Result(line.target, "", line.recipe, False, line.problem))
            continue
        glyph = package.findName(line.target)
        why = history.refusal(facts, line.target, "geometry") if glyph else ""
        if why:
            results.append(Result(line.target, "", line.recipe, False, why))
            continue
        for index, master in enumerate(masters):
            if glyph is None and index > 0:
                note = f"new glyph: press Build again for {master}"
                results.append(Result(line.target, master, line.recipe, True, note))
                continue
            ok, message = build(package, line, master, replace, dry_run=True)
            adds = (
                glyph is not None and component_writer.layer_of(glyph, master) is None
            )
            if adds and not ok and LAYER_MISSING in message:
                ok, message = True, f"valid: adds layer {master} first"
            results.append(Result(line.target, master, line.recipe, ok, message, adds))
    return results


# ---------------------------------------------------------------- dump (read-only)
def dump_text() -> tuple[str, str]:
    """(recipes, summary) of the selected layers; the Dump Component Recipes report. Reads only."""
    report = recipes_model.capture()
    count = sum(bool(layer.components) for layer in report.layers)
    summary = (
        f"Recipes: {count} · Layers: {len(report.layers)} · Current master: {report.master}."
        " Refresh after changes."
    )
    return recipes_model.recipes(report.layers), summary


# ---------------------------------------------------------------- tab
class BuildPanel(_shared.ComponentPanel):
    """Recipe text, master scope and the replace option; one row per target layer."""

    ACTION, RELOAD, UNDO = "Build", "Check", "add master layers"
    HEADERS: tuple[str, ...] = ("Target · master", "Recipe", "Check")

    def build_controls(self, form: Any) -> None:
        self.results: list[Result] = []
        self.checked = False
        self.recipes = QtGui.QPlainTextEdit(self.widget)
        self.recipes.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )
        self.recipes.setPlainText(EXAMPLE)
        self.recipes.setPlaceholderText("target = base + mark@anchor   (one per line)")
        self.recipes.setMinimumHeight(110)
        form.addWidget(self.recipes)
        self.scope_box(form)
        self.replace = check(
            self.widget,
            form,
            "Replace existing layers",
            False,
            self.contain(self.invalidate),
        )
        self.recipes.textChanged.connect(self.contain(self.invalidate))
        self.dumped = QtGui.QPlainTextEdit(self.widget)
        self.dumped.setReadOnly(True)
        self.dumped.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )
        self.dumped.setPlaceholderText(
            "Dump from selection: base+base=glyph per selected layer"
        )
        self.dumped.setMaximumHeight(90)
        form.addWidget(self.dumped)
        self.dump_status = text_label(self.widget, form, "")

    def add_buttons(self, buttons: Any) -> None:
        button(self.widget, buttons, "Dump from selection", self.contain(self.dump))

    def replacing(self) -> bool:
        return bool(get(self.replace.isChecked))

    def lines(self) -> list[Line]:
        return parse(str(get(self.recipes.toPlainText)))

    def intro(self) -> str:
        if self.package is None:
            return NO_FONT
        return "One recipe per line. Check runs FontLab's builder as a dry run."

    # Check / table -----------------------------------------------------------
    def refresh(self) -> None:
        """Bind to the current font; no dry run until Check (the original's ``first_scan``)."""
        if not self.ready:
            return
        tool = self.tool
        self.package = tool.package
        self.package_id = self.package.id if self.package is not None else None
        self.current_master = tool.current
        self.relabel()
        self.results, self.checked = [], False
        self.show_results()

    def reloaded(self) -> None:
        """The Check button: re-read the font, then dry-run every line."""
        self.tool.reload()
        self.scan()

    def scan(self) -> None:
        """Check button: bind to the current font, then dry-run every line."""
        self.refresh()
        self.facts = history.auto_facts(())
        if self.package is not None:
            self.facts = history.scan_auto_facts(self.package)
            self.results = check_lines(
                self.package,
                self.lines(),
                self.chosen_masters(),
                self.replacing(),
                self.facts,
            )
            self.checked = True
        self.show_results()

    def replan(self) -> None:
        self.invalidate()

    def invalidate(self) -> None:
        if not self.ready:
            return
        self.results, self.checked = [], False
        self.show_results()
        self.count.setText("Recipes changed: press Check")

    def show_results(self) -> None:
        self.subtitle.setText(self.intro())
        rows = [
            (
                f"{r.target} · {r.master}" if r.master else r.target,
                component_writer.Change(r.recipe, "", r.message, None if not r.ok else r.target,
                                        "" if r.ok else r.message),
            )
            for r in self.results
        ]  # fmt: skip
        self.fill(component_writer.Plan(rows=rows))
        good = sum(1 for r in self.results if r.ok)
        ready = self.checked and bool(self.results) and good == len(self.results)
        self.apply_button.setEnabled(ready)
        if not self.checked:
            self.count.setText("Press Check" if self.package else "")
        else:
            missing = "" if ready else " · fix the red lines"
            self.count.setText(f"{good} of {len(self.results)} layers ready{missing}")

    # Dump (read-only) --------------------------------------------------------
    def dump(self) -> None:
        """Show the selected layers' recipes; nothing is written and no history opens."""
        self.dumped.setPlainText("")
        try:
            text, summary = dump_text()
        except (ValueError, TimeoutError, RuntimeError) as error:
            self.dump_status.setText(str(error))
            return
        self.dumped.setPlainText(text)
        self.dump_status.setText(summary)

    # Build -------------------------------------------------------------------
    def add_layers(self, package: Any, results: list[Result]) -> int | None:
        """Add the empty master layers the builds need, as ONE labelled Undo step; None when refused."""
        wanted: dict[str, list[str]] = {}
        for result in results:
            if result.adds_layer:
                wanted.setdefault(result.target, []).append(result.master)
        if not wanted:
            return 0
        glyphs = [package.findName(name) for name in wanted]

        def mutate() -> list[Any]:
            made = []
            for glyph in glyphs:
                made.extend(glyph.findLayerCreate(m) for m in wanted[glyph.name])
            return made

        committed = self.tool.shell.history(
            _shared.label(self.UNDO, wanted), glyphs, mutate, layers=[]
        )
        if committed is None:
            return None
        return sum(len(masters) for masters in wanted.values())

    def apply(self) -> bool:
        """Re-check safety, add missing layers, then build each layer with FontLab's builder."""

        def run() -> bool:
            package = scripting.current_package(self.package_id)
            if package is None:
                raise ValueError("The font changed; press Check.")
            ids = edit_guards.pending_updates()
            facts = history.scan_auto_facts(package)
            results = check_lines(
                package, self.lines(), self.chosen_masters(), self.replacing(), facts
            )
            failed = [r for r in results if not r.ok]
            if failed:
                self.results = results
                self.show_results()
                raise ValueError(f"{failed[0].target}: {failed[0].message}")
            added = self.add_layers(package, results)
            if added is None:
                return False
            built: list[Result] = []
            for result in results:
                if result.message.startswith("new glyph:"):
                    built.append(result)
                    continue
                line = Line(0, result.target, result.recipe)
                ok, message = build(
                    package, line, result.master, self.replacing(), False
                )
                built.append(
                    Result(result.target, result.master, result.recipe, ok, message)
                )
            self.results, self.checked = built, False
            self.show_results()
            done = sum(
                1 for r in built if r.ok and not r.message.startswith("new glyph:")
            )
            errors = [r for r in built if not r.ok]
            note = (
                f" · added {component_writer.plural(added, 'empty layer')}"
                if added
                else ""
            )
            left = sum(1 for r in built if r.message.startswith("new glyph:"))
            more = f" · {component_writer.plural(left, 'master')} still to build: press Build again"
            tail = f" · {len(errors)} failed: {errors[0].message}" if errors else ""
            pending = edit_guards.pending_note(ids)
            self.last_result = {"pending_note": pending, "built": done, "failed": len(errors), "added": added,
                                "pending_updates": ids}  # fmt: skip
            text = f"Built {component_writer.plural(done, 'layer')}{note}{more if left else ''}{tail}"
            self.tool.say(text + (" · " + pending if pending else ""))
            self.count.setText(text)
            return True

        return bool(self.run(run))


__all__ = [
    "ATTACH", "EXAMPLE", "GLYPH_NAME", "LAYER_MISSING", "UNSAFE_TEXT", "BuildPanel", "Line", "Result",
    "build", "check_lines", "data_tool", "dump_text", "parse",
]  # fmt: skip
