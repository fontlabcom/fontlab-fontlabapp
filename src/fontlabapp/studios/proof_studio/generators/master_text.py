# this_file: src/fontlabapp/studios/proof_studio/generators/master_text.py
# SPDX-License-Identifier: Apache-2.0
"""Master text comparison: comma-separated text set across all masters of the font.

What: absorbs Scriptmix "Master Text Comparison" (after Luke Prowse's
MasterBlaster, MIT; see NOTICE) on the shared ``fontlabapp.masters.text``
workflow. Same inputs: comma-separated custom text, Stacked (0) or
Side-by-side (1, default), Characters or Named tokens, presets from a local
``MasterBlaster-presets.txt`` in the working directory or the four original
fallback lists, and Load presets from an absolute path. Open prefers nonempty
custom text, then the chosen preset; "Open chosen preset" runs that preset
whatever the custom text (the original double-click); both save the
custom field afterwards, as the original does when it is readable. ``analyze`` builds the
preview (one part per master, on that master's layer) and the exact text;
Open captures the font afresh, opens one new comparison tab through
``masters.text.proof.open_proof`` and then saves ``inputCustom``/``layout``
in QSettings ("FontLabScriptmix", "MasterTextComparison"), as the original.
"""

from pathlib import Path
from time import monotonic
from typing import Any

from fontlabapp.core.scripting import proof_studio_backends

from . import Action, Context, Field, Generator, Options, Outcome, Proof
from ._text import names_run

SETTINGS = ("FontLabScriptmix", "MasterTextComparison")
LAYOUTS = ("Stacked", "Side-by-side")
PRESET_FILE = "MasterBlaster-presets.txt"
NONE = "(no preset)"


def _mt() -> Any:
    return proof_studio_backends().master_text


def _presets(values: dict[str, Any]) -> tuple[str, ...]:
    return tuple(values.get("presets", _mt().settings.FALLBACKS))


def _text(values: dict[str, Any], immediate: bool = False) -> str:
    """Custom text first, else the chosen preset (index 0 is "no preset")."""
    selected = int(values.get("preset", 0)) - 1
    presets = _presets(values)
    if immediate:
        return _mt().model.select_text("", presets, selected, immediate=selected)
    return _mt().model.select_text(str(values.get("custom", "")), presets, selected)


def make(mode: str, options: Options) -> Proof:
    """Sanitize like the original; one preview part per master and the exact text as Copy."""
    facts = options.facts
    if facts is None:
        return Proof((), note="Open a font first.")
    values = options.values
    result = _mt().model.analyze(
        _text(values), dict(facts.cmap), set(facts.names), facts.masters, int(values.get("layout", 1)), mode=mode
    )
    run = names_run([name for word in result.words for name in word])
    return Proof(
        tuple(result.preview for _ in facts.masters),
        labels=facts.masters,
        previews=tuple(run for _ in facts.masters),
        layers=facts.masters,
        note=f"{len(result.words)} words × {len(facts.masters)} masters; "
        f"{len(result.dropped)} unavailable occurrences and {len(result.empty_words)} empty words omitted.",
    )


def load(settings: Any, *, directory: Path | None = None) -> Outcome:
    """Saved custom text and layout, then local presets (or the four fallbacks)."""
    mt = _mt()
    status = ""
    custom, layout = "", 1
    try:
        custom, layout, _geometry = mt.settings.load(settings)
    except Exception as error:  # noqa: BLE001 - the original keeps defaults and reports
        status = f"{error} "
    folder = mt.settings.presets_directory(directory)
    presets = mt.settings.load_presets(folder)
    return Outcome(
        status + presets.notice,
        values={"custom": custom, "layout": layout, "presets": presets.lines, "preset": 0,
                "preset_file": str(folder / PRESET_FILE)},
        items={"preset": (NONE, *presets.lines)},
    )


def load_file(context: Context) -> Outcome:
    """Replace the presets with the lines of the absolute preset file."""
    lines = _mt().settings.read_presets(str(context.values.get("preset_file", "")))
    return Outcome(
        f"{len(lines)} presets loaded; UTF-8 BOM and newlines normalized.",
        values={"presets": lines, "preset": 0},
        items={"preset": (NONE, *lines)},
    )


def _open(mode: str, context: Context, *, immediate: bool, clock: Any = monotonic) -> str:
    mt = _mt()
    mt.owners.require_clear()
    deadline = clock() + 3.0
    check = lambda: mt.model.checkpoint(deadline - 0.5, clock, context.cancelled)  # noqa: E731
    opening = mt.capture.read(deadline - 0.5, check=check)
    cmap, names, _aliases = opening.maps(check)
    layout = int(context.values.get("layout", 1))
    result = mt.model.analyze(_text(context.values, immediate), cmap, names, opening.masters, layout,
                              mode=mode, check=check)
    mt.proof.open_proof(opening, result, deadline=deadline, cancelled=context.cancelled)
    mt.settings.save(context.settings, str(context.values.get("custom", "")), layout,
                     preserve_custom=False, check=check)
    return (
        f"Opened comparison; omitted {len(result.dropped)} unavailable occurrences and "
        f"{len(result.empty_words)} empty words. First font-order encoded aliases used."
    )


def open_current(mode: str, context: Context) -> str:
    """List as Masters: custom text first, else the chosen preset; save controls after success."""
    return _open(mode, context, immediate=False)


def open_preset(context: Context) -> Outcome:
    """The original double-click: run the chosen preset now, then save the custom field."""
    return Outcome(_open(context.choice, context, immediate=True))


GENERATOR = Generator(
    key="master-text",
    title="Master text comparison",
    tab="By master",
    tab_order=70,
    order=20,
    choices=(
        ("Characters", "characters"),
        ("Named tokens: /glyphname (one following space is syntax)", "names"),
    ),
    scripts={"characters": "Master Text Comparison", "names": "Master Text Comparison"},
    make=make,
    open=None,
    open_current=open_current,
    uses_font=True,
    choice_label="Input",
    part_label="Master",
    fields=(
        Field("custom", "Comma-separated text (unavailable characters are omitted)", "text"),
        Field("layout", "Arrangement", "combo", 1, items=LAYOUTS),
        Field("preset", "Preset", "combo", 0, items=(NONE, *_mt().settings.FALLBACKS)),
        Field("preset_file", "Preset file", default=str(Path.cwd() / PRESET_FILE)),
    ),
    settings=SETTINGS,
    load=load,
    actions=(Action("Load presets", load_file), Action("Open chosen preset", open_preset)),
)
