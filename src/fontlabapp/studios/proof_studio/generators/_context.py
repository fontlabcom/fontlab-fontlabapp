# this_file: src/fontlabapp/studios/proof_studio/generators/_context.py
# SPDX-License-Identifier: Apache-2.0
"""Shared Glyphs Between / Glyphs Surrounded generation over the App context proof.

What: ``make`` runs ``fontlabapp.proof.context.proof_lines`` (through
``core.scripting.context_proof_api``) on the selected names and renders its
rows as text: one line per row, ``/name`` tokens separated by spaces, an empty
row as an empty line. ``open`` calls the same ``run(mode)`` the absorbed
scripts call. Pure apart from the lazy backend import; no Qt, no host.
Used by ``between`` and ``surround`` in this package.
"""

from fontlabapp.core.scripting import context_proof_api

from . import Options, Proof


def rows_text(rows: tuple[tuple[str, ...], ...]) -> str:
    """Rows as text lines of space-separated ``/name`` tokens (TMetrics names run)."""
    return "\n".join(" ".join(f"/{name}" for name in row) for row in rows)


def make(mode: str, options: Options) -> Proof:
    """The one-tab proof for ``mode`` over ``options.names`` (order and repeats kept)."""
    return Proof((rows_text(context_proof_api().proof_lines(mode, tuple(options.names))),))


def open_tab(mode: str) -> None:
    """Open the new named-glyph tab exactly as the absorbed script: live selection, current master."""
    context_proof_api().run(mode)
