# this_file: src/fontlabapp/qt/trees/data.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable text trees for injected Qt models; no host or foreign UI imports."""

from dataclasses import dataclass
from time import monotonic


def check_deadline(deadline: float) -> None:
    """Refuse expired complete-tree work; never publish a partial model."""
    if monotonic() >= deadline:
        raise TimeoutError("Tree snapshot expired; refresh the complete tree.")


@dataclass(frozen=True)
class Tree:
    """Ordered rows contain (earlier parent row or -1, immutable text cells).

    An earlier parent makes cycles impossible. Equal text rows remain distinct.
    Cells may vary in count, as required by hierarchical Qt item models.
    """

    headers: tuple[str, ...]
    rows: tuple[tuple[int, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.headers, tuple)
            or not self.headers
            or any(type(v) is not str for v in self.headers)
        ):
            raise TypeError("Tree headers must be a nonempty tuple of text.")
        if not isinstance(self.rows, tuple):
            raise TypeError("Tree rows must be immutable.")
        for position, row in enumerate(self.rows):
            if not isinstance(row, tuple) or len(row) != 2:
                raise TypeError("Each tree row needs a parent and text cells.")
            parent, cells = row
            if type(parent) is not int or not -1 <= parent < position:
                raise ValueError("A tree parent must precede its child, or be -1.")
            if (
                not isinstance(cells, tuple)
                or not cells
                or any(type(v) is not str for v in cells)
            ):
                raise TypeError("Tree cells must be a nonempty tuple of text.")
