# this_file: src/fontlabapp/studios/proof_studio/generators/text_filter.py
# SPDX-License-Identifier: Apache-2.0
"""Text filter: keep only the characters of a regular-expression class (Text Simplifier).

What: absorbs Scriptmix "Text Filter" (after Slobzheninov's Apache-2.0 Text
Filter; see NOTICE). ``make`` runs ``fontlabapp.proof.text_filter.model.
filter_text(input, characters)``: order and repeats kept, an empty or
malformed class is an error. Persistence is the original's: QSettings
("FontLab", "ScriptTextFilter"), keys ``input``, ``output`` and
``characters`` through ``proof.text_filter.settings``, saved after each edit;
Reset removes only ``output``/``characters`` and keeps the input. Open opens
the output in one new tab (the original's "Open in a New Tab").
"""

from typing import Any

from fontlabapp.core.scripting import current_package, proof_studio_backends

from . import Action, Context, Field, Generator, Options, Outcome, Proof

SETTINGS = ("FontLab", "ScriptTextFilter")
NO_FONT = "Reopen this tool with a font to open a proof tab."


def _backend() -> Any:
    return proof_studio_backends()


def make(_choice: str, options: Options) -> Proof:
    """The filtered input as one part, with the original "Kept N characters." note."""
    backends = _backend()
    values = options.values
    characters = values.get("characters", backends.text_filter.DEFAULT_CHARACTERS)
    output = backends.text_filter.filter_text(str(values.get("input", "")), str(characters))
    return Proof((output,), note=f"Kept {len(output)} characters.")


def load(settings: Any) -> Outcome:
    """The saved input and character set (original defaults when unset)."""
    saved = _backend().text_filter_settings.load(settings)
    return Outcome(
        "Input and output are saved for the next session.",
        values={"input": saved.input, "characters": saved.characters},
    )


def save(settings: Any, values: dict[str, Any], proof: Proof) -> None:
    """Save input, output and character set, as the original does after every edit."""
    backends = _backend()
    output = proof.parts[0] if proof.parts else ""
    state = backends.text_filter.SavedText(str(values.get("input", "")), output, str(values.get("characters", "")))
    backends.text_filter_settings.save(settings, state)


def reset(context: Context) -> Outcome:
    """Keep input; restore the output and character-set defaults and remove only those keys."""
    backends = _backend()
    backends.text_filter_settings.reset(context.settings)
    return Outcome(
        "Output and character set reset. Input retained.",
        values={"characters": backends.text_filter.DEFAULT_CHARACTERS},
    )


def open_current(_choice: str, context: Context) -> None:
    """Open the output in one new tab bound to the current font."""
    package = current_package()
    if package is None:
        raise ValueError(NO_FONT)
    _backend().text_tab.open_text_tab(context.text(), expected_id=package.id)


GENERATOR = Generator(
    key="text-filter",
    title="Text filter",
    tab="Real text",
    tab_order=40,
    order=20,
    choices=(("Keep characters in the class", "text-filter"),),
    scripts={"text-filter": "Text Filter"},
    make=make,
    open=None,
    open_current=open_current,
    fields=(
        Field("input", "Input", "text"),
        Field("characters", "Character set (regular-expression class)", "text", default=_backend().text_filter.DEFAULT_CHARACTERS),
    ),
    settings=SETTINGS,
    load=load,
    save=save,
    actions=(Action("Reset", reset),),
)
