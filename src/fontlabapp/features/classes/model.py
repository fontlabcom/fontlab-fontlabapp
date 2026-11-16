# this_file: src/fontlabapp/features/classes/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Simon Cozens' complete Clean Classes policy and real ordered writer."""

from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    """Exact font domain and ordered class code; whitespace is significant."""

    context: tuple
    names: tuple[str, ...]
    classes: tuple[tuple[str, str], ...]


def changes(facts: Snapshot) -> tuple[tuple[str, str, str], ...]:
    """Only missing tokens trigger writes; retain order/duplicates, join once."""
    existing = set(facts.names)
    result = []
    for name, code in facts.classes:
        tokens = code.split()
        kept = [token for token in tokens if token in existing]
        if tokens != kept:
            result.append((name, code, " ".join(kept)))
    return tuple(result)


def render(facts: Snapshot) -> str:
    """Show every proposed class replacement, including an empty result."""
    return (
        "\n\n".join(
            f"{name}\nBefore: {old}\nAfter: {new}" for name, old, new in changes(facts)
        )
        or "No missing glyph names in OpenType classes."
    )


def apply(bridge: Any, facts: Snapshot) -> dict[str, int]:
    """Fence the whole domain before the batch; failures retain Undo diagnosis."""
    if bridge.poisoned:
        raise RuntimeError(
            "Previous write failed; inspect the font and reopen this tool."
        )
    deadline = monotonic() + 2.0
    if bridge.capture(deadline=deadline) != facts:
        raise ValueError(
            "Font, glyph names or classes changed; Refresh before applying."
        )
    work = changes(facts)
    if not work:
        return {"classes": 0, "tokens": 0}
    attempted = completed = 0
    errors = []
    bridge.begin()
    try:
        for name, old, new in work:
            if monotonic() >= deadline:
                raise TimeoutError("Class cleanup deadline exceeded.")
            attempted += 1
            bridge.write(name, tuple(new.split()))
            completed += 1
    except Exception as error:  # noqa: BLE001 - retain and finalize partial native edits
        errors.append(error)
    finally:
        try:
            bridge.end()
        except Exception as error:  # noqa: BLE001 - failed notification is not success
            errors.append(error)
    if errors:
        bridge.poisoned = True
        raise RuntimeError(
            f"Clean Classes failed after {attempted} attempts ({completed} confirmed). Changes may remain; use Edit > Undo and inspect the font. "
            + "; ".join(map(str, errors))
        ) from errors[0]
    replacements = {name: new for name, _, new in work}
    expected = Snapshot(
        facts.context,
        facts.names,
        tuple((name, replacements.get(name, code)) for name, code in facts.classes),
    )
    try:
        if bridge.capture(deadline=deadline) != expected:
            raise ValueError(
                "The complete class result differs from the planned state."
            )
    except Exception as error:  # noqa: BLE001 - post-write verification cannot claim success
        bridge.poisoned = True
        raise RuntimeError(
            "Class writes finished but verification failed; changes may remain. Use Edit > Undo and inspect the font. "
            + str(error)
        ) from error
    return {
        "classes": completed,
        "tokens": sum(len(old.split()) - len(new.split()) for _, old, new in work),
    }


def show(backend: Any) -> Any:
    """Open the practical complete writer lazily through the shared registry."""
    from fontlabapp import _native
    from fontlabapp.features.classes.native import Bridge
    from fontlabapp.features.classes.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    return show_script_dialog(
        lambda parent: panel_type(qt.QtCore, qt.QtGui)(parent, Bridge(backend)),
        "clean_classes",
    )
