# this_file: src/fontlabapp/kerning/group_proof/model.py
# SPDX-License-Identifier: Apache-2.0
"""Open Reza Bohloul's complete same-kerning-groups proof independently.

Keep the first selected glyph, both visual-side groups, font order, literal L:/R:
labels and separators. Explicit glyph-name symbols preserve unencoded peers.
No original body is redistributed. See NOTICE for source/licence disposition.
"""

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class GlyphGroups:
    """One font-order FG glyph identity and its visual-side group names."""

    ident: int
    name: str
    left: str | None
    right: str | None


@dataclass(frozen=True)
class Proof:
    """Detached current glyph and independent left/right peer proof rows."""

    current: str
    left: tuple[str, ...]
    right: tuple[str, ...]
    rows: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def has_peers(self) -> bool:
        """The source opens a tab only when at least one other member exists."""
        return bool(self.left or self.right)


def build(glyphs: tuple[GlyphGroups, ...], current_id: int) -> Proof:
    """Keep every peer in font order, excluding only the current identity.

    A missing group contributes the source's blank row. A nonempty singleton
    group contributes no peer row. Every opened proof ends with a newline.
    Repeated names are retained; name/Unicode parsing is never used here.
    """
    current = next((g for g in glyphs if g.ident == current_id), None)
    if current is None:
        raise ValueError("The selected glyph is missing from the source font.")
    left = tuple(
        g.name
        for g in glyphs
        if current.left and g.left == current.left and g.ident != current_id
    )
    right = tuple(
        g.name
        for g in glyphs
        if current.right and g.right == current.right and g.ident != current_id
    )
    rows = [("", (current.name,))]
    for group, peers, prefix in [
        (current.left, left, "L: "),
        (current.right, right, "R: "),
    ]:
        if not group:
            rows.append(("", ()))
        elif peers:
            rows.append((prefix, peers))
    return Proof(current.name, left, right, (*rows, ("", ())))


def run() -> Proof | None:
    """Read/recheck the source and open a fresh proof; never rewrite a tab.

    Diagnose absent selection or no peers using an owned message box. The source
    singleton condition is retained, with accurate no-other-members wording.
    Native calls cannot be preempted. Native UI/cache/history qualification is
    pending; tab creation/population failures may leave a new tab.
    """
    from fontlabapp.kerning.group_proof import native

    deadline = monotonic() + 2.0
    try:
        before = native.capture(deadline)
        proof = build(before.rows, before.current_id)
        changed = before != native.capture(deadline)
    except native.NoSelectedGlyph as error:
        native.diagnose("Script Error", str(error))
        return None
    except native.AmbiguousGroups as error:
        native.diagnose("Ambiguous Kerning Groups", str(error))
        return None
    if changed:
        raise ValueError(
            "The selected glyph, groups or source font changed; run again."
        )
    if proof.has_peers:
        native.open_proof(before, proof, deadline)
    else:
        native.diagnose(
            "No Kerning Groups",
            "The selected glyph has no other left or right kerning-group members.",
        )
    return proof
