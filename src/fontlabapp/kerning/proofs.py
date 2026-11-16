# this_file: src/fontlabapp/kerning/proofs.py
# SPDX-License-Identifier: Apache-2.0
"""Open Pedro Arilla's four complete kerning proofs in native FontLab tabs.

Keep all five original text resources and their exact whitespace/slash escapes.
KernKing opens lowercase first, then mixed case. See NOTICE for source credits.
No source script is executed; native access is lazy and uses shared tab ownership.
"""

import json
from importlib.resources import files
from time import monotonic
from typing import Literal

Mode = Literal["hoefler-lowercase", "hoefler-uppercase", "kernking", "kernsym"]
MODES: tuple[Mode, ...] = (
    "hoefler-lowercase",
    "hoefler-uppercase",
    "kernking",
    "kernsym",
)


def proof_texts(mode: Mode) -> tuple[str, ...]:
    """Read all text for one command before tab creation; never trim or filter.

    Preserve literal Unicode, blank lines and named escapes even when a font
    lacks a requested glyph. FontLab's native advanced text parser resolves
    /quoteright and /germandbls; doubled slash denotes a literal slash.
    Resource failures propagate before any native lookup or new tab.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown kerning proof: {mode}")
    data = json.loads(
        files("fontlabapp")
        .joinpath("kerning", "kerning_proof_texts.json")
        .read_text(encoding="utf-8")
    )
    return tuple(data[mode])


def run(mode: Mode) -> None:
    """Open every original tab in order, bound to one captured font/master.

    Native Glyph tabs are the nonmodal interface. Preserve existing tabs and
    Output. One two-second preflight deadline covers the complete invocation;
    native calls cannot be preempted. Shared cleanup restores shape activation
    and disconnects/deletes each hidden sender. If a later tab fails, earlier
    new tabs may remain: no atomic UI rollback or native acceptance is claimed.
    """
    from fontlabapp.core.scripting import current_package
    from fontlabapp.proof.tabs.text import _open_tab

    texts = proof_texts(mode)
    package = current_package()
    if package is None:
        raise ValueError("Open a font before creating a kerning proof.")
    package_id, master = int(package.id), package.master
    deadline = monotonic() + 2.0
    for text in texts:
        _open_tab(
            text, expected_id=package_id, expected_master=master, deadline=deadline
        )
