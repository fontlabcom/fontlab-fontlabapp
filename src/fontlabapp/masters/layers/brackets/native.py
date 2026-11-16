# this_file: src/fontlabapp/masters/layers/brackets/native.py
# SPDX-License-Identifier: Apache-2.0
"""Complete report/tab routes over a fenced full-font dependency snapshot.

No source font, selection, master, history, preference or Output writer runs.
The tab route reuses named_tab's existing fresh-target/activation safeguards;
create/populate failure can still leave a new tab. Native acceptance is pending.
"""

from time import monotonic
from typing import Any

import fontlabapp.proof.tabs.named as named_tab  # noqa: PLR0402 - package __getattr__ routes cold from-imports to native
from fontlabapp.masters.layers.brackets import _snapshot as snapshot
from fontlabapp import _native
from fontlabapp.masters.layers.brackets.model import Report, analyse, tab_names


def report() -> Report:
    """Return the complete original groups; never return an observed prefix."""
    return analyse(snapshot.capture().glyphs)


def _symbols(native: Any, result: Report, master: str, deadline: float) -> Any:
    """Keep literal headings and both sorted named groups, including overlap.

    Names never pass through Unicode or slash parsing. Empty sections add no
    dangling slash. These repair the source's unordered-set/orphan-marker paths.
    """
    combined = None
    for header, names in zip(
        ("Glyphs:\n", "\n\nComponents:\n"), tab_names(result), strict=True
    ):
        snapshot.check(deadline)
        literal = native.fgSymbolList(header)
        if combined is None:
            combined = literal
        else:
            combined.append(literal)
        values = []
        for name in names:
            snapshot.check(deadline)
            symbol = native.fgSymbol(name)
            symbol.layerName = master
            values.append(symbol)
        if values:
            combined.append(native.fgSymbolList(values))
    snapshot.check(deadline)
    return combined


def open_tab() -> None:
    """Capture, build, recheck, then open a fresh proof in that exact source font."""
    deadline = monotonic() + 2.0
    captured = snapshot.capture(deadline=deadline)
    result = analyse(captured.glyphs)
    if not result.total:
        raise ValueError("No bracket-layered glyphs or components found.")
    native = _native("fontlab")
    symbols = _symbols(native, result, captured.context[2], deadline)
    snapshot.validate(captured, deadline)
    named_tab._open_symbols(
        native, symbols, captured.context[0], captured.context[2], deadline
    )
