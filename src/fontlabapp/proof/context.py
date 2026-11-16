# this_file: src/fontlabapp/proof/context.py
# SPDX-License-Identifier: Apache-2.0
"""Eight Pedro Arilla selected-glyph context proofs; see NOTICE for provenance.

Generate explicit glyph-name rows. Preserve occurrence order, repeats, empty
selection behavior and trailing blank lines. Native opening is lazy and fenced.
"""

from time import monotonic
from typing import Literal

Mode = Literal[
    "lowercase", "uppercase", "lining", "oldstyle", "H", "I", "HHOHH", "nnonn"
]
_BETWEEN = {
    "lowercase": tuple("abcdefghijklmnopqrstuvwxyz"),
    "uppercase": tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    "lining": (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
    ),
    "oldstyle": tuple(
        n + ".osf"
        for n in (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        )
    ),
}
_SURROUND = {name: tuple(name) for name in ("H", "I", "HHOHH", "nnonn")}
MODES: tuple[Mode, ...] = (*_BETWEEN, *_SURROUND)


def proof_lines(
    mode: Mode, names: tuple[str, ...], *, deadline: float | None = None
) -> tuple[tuple[str, ...], ...]:
    """Build source-exact rows; keep names explicit even when unencoded.

    Between modes append a selected name before each context name and once
    after it, then two newlines per selected occurrence. Surround modes emit
    context + selected name repeatedly and end with one final context. With no
    selection, between opens an empty tab and surround retains its context.
    A supplied host deadline is checked while building every occurrence.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown context proof mode: {mode}")
    lines, row = [], ()
    for name in names:
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError(
                "Context proof generation exceeded its deadline; no tab opened."
            )
        if mode in _BETWEEN:
            line = tuple(part for other in _BETWEEN[mode] for part in (name, other)) + (
                name,
            )
            lines.extend((line, ()))
        else:
            row += _SURROUND[mode] + (name,)
    return tuple(lines) + ((),) if mode in _BETWEEN else (row + _SURROUND[mode],)


def run(mode: Mode) -> None:
    """Capture actual ordered selected layers and open a new named-glyph tab.

    One two-second deadline covers captures, generation, symbols and native
    preflight. No sorting, deduplication, current-glyph fallback or existing-tab
    rewrite. Native calls are not preemptible; installed native acceptance is open.
    """
    import fontlabapp.masters.layers.selection as layers
    from fontlabapp.proof.tabs.named import open_named_tab

    deadline = monotonic() + 2.0
    selection = layers.capture(deadline)
    lines = proof_lines(
        mode, tuple(row.glyph_name for row in selection.occurrences), deadline=deadline
    )
    if selection != layers.capture(deadline):
        raise ValueError("Selected layers or source font changed; run the proof again.")
    open_named_tab(
        lines,
        expected_id=selection.context[0],
        master=selection.context[1],
        deadline=deadline,
    )
