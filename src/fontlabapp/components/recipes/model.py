# this_file: src/fontlabapp/components/recipes/model.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Report ordered component recipes, adapted from Simon Cozens' Recipe Dumper.

Preserve repeated layer records, component order, repeated components and mixed
contour/component layers. The source prints names only: do not synthesize
positions, transforms, anchors or decomposed contours. See NOTICE for MIT terms.
The shared native reader preserves ordered Font/Glyph-window layer occurrences.
Actual9787selection and complete preservation still require native acceptance.
"""

from dataclasses import dataclass
from time import monotonic

import fontlabapp.masters.layers.selection as selection

CAPTURE_SECONDS = 2.0


@dataclass(frozen=True)
class RecipeLayer:
    """One source layer; duplicate records and base names remain meaningful."""

    glyph: str
    components: tuple[str, ...]


@dataclass(frozen=True)
class RecipeSnapshot:
    """Complete immutable selected-layer snapshot, retaining editor occurrences."""

    package_id: int
    master: str
    layers: tuple[RecipeLayer, ...]
    context: tuple = ()


def recipes(layers: tuple[RecipeLayer, ...]) -> str:
    """Return original `base+base=glyph` lines, without deduplication or sorting.

    Skip only layers without components. Keep missing-base names literally.
    A recipe records composition, not exact geometry or guaranteed import into
    another editor. The original format omits all transforms and offsets.
    Keep the final newline emitted by the original per-layer print call.
    """
    return "".join(
        "+".join(layer.components) + "=" + layer.glyph + "\n"
        for layer in layers
        if layer.components
    )


def _check_deadline(deadline: float) -> None:
    """Reject an overrun at a Python checkpoint; never publish a truncated scan."""
    if monotonic() >= deadline:
        raise TimeoutError("Recipe scan exceeded its deadline; no partial report.")


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Read ordered component names/identities without reading own geometry."""
    rows = []
    for occurrence in selected.occurrences:
        _check_deadline(deadline)
        glyph, layer = occurrence.glyph, occurrence.layer
        if (
            glyph.isNull
            or layer.isNull
            or int(glyph.id) != occurrence.glyph_id
            or int(layer.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(layer.name) != occurrence.layer_name
            or int(glyph.package.id) != occurrence.package_id
        ):
            raise ValueError("A selected glyph/layer identity changed; refresh.")
        bases, shapes = [], []
        for shape in layer.shapes:
            _check_deadline(deadline)
            component = bool(shape.isComponent)
            base = shape.shapeData.componentGlyph if component else None
            if component:
                if not isinstance(base, str):
                    raise ValueError("A component has no readable base name; refresh.")
                bases.append(base)
            shapes.append((int(shape.id), component, base))
            _check_deadline(deadline)
        rows.append(
            (
                occurrence.glyph_id,
                occurrence.layer_id,
                tuple(shapes),
                RecipeLayer(occurrence.glyph_name, tuple(bases)),
            )
        )
    _check_deadline(deadline)
    return tuple(rows)


def capture() -> RecipeSnapshot:
    """Capture actual selected layers, including ordered repeated editor slots.

    Use the shared Font/Glyph-window provider, read all components twice and
    reject changed observed identities, names, shape order or document context.
    A single2sdeadline covers every provider/component loop. No current-glyph
    fallback, sorting, deduplication, font write or partial result is used.
    Blocking native calls cannot be preempted; native acceptance remains open.
    """
    deadline = monotonic() + CAPTURE_SECONDS
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("Select glyph layers before dumping component recipes.")
    rows = _read(first, deadline)
    second = selection.capture(deadline)
    repeated = _read(second, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    _check_deadline(deadline)
    if (
        first != second
        or second != final
        or rows != repeated
        or context != final.context
    ):
        raise ValueError("Font, master, selection or components changed; refresh.")
    return RecipeSnapshot(
        int(context[0]), str(context[1]), tuple(row[3] for row in rows), context
    )
