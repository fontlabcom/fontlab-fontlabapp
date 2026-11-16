# this_file: src/fontlabapp/studios/layer_manager/_empty.py
# SPDX-License-Identifier: Apache-2.0
"""Clean-up tab, Empty layers mode: the Scriptmix "Empty Layers" (Scripts/Cleanup/).

List the extra layers of the selected glyphs that hold no data and no
mask content (shown and locked ones are listed as skipped), then delete
them with their empty masks. The planning is the original's, verbatim.
Delete plans again, refuses a plan that differs from the list, and writes
ONE ``Layer Manager: delete empty layers <subject>`` Undo step through
``AppShell.history`` on the original's carrier layers (the first master
layer that stays). The original retains nothing (empty layers hold no
components); kept so.
"""

from collections.abc import Sequence
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from ._shared import PlanTab, append_note, commit, label as undo_label, result_dict

TITLE = "Empty Layers"
TEMP_PREFIX = "|temp|"
#: Layer fields that make a layer "not empty" when they hold any value.
DATA_FIELDS = (
    "shapes", "anchors", "guidelines", "note", "recipe", "lib",
    "hasTTH", "hasTTData", "metricsLeft", "metricsRight", "metricsWidth",
)  # fmt: skip
MAX_LISTED = 10  # deleted layers and skipped items named in the result


def is_empty_auxiliary(layer: Any, masters: Sequence[str]) -> bool:
    """True for an extra layer that holds no data and no mask content."""
    name = str(layer.name)
    if name.lower() in {str(m).lower() for m in masters} or name.startswith(
        TEMP_PREFIX
    ):
        return False
    if layer.autoLayer or layer.isMaskLayer or layer.isService or layer.isImgLayer:
        return False
    if any(getattr(layer, field) for field in DATA_FIELDS):
        return False
    mask = layer.getMaskLayer(False)
    return (
        mask is None
        or mask.isNull
        or not any(getattr(mask, field) for field in DATA_FIELDS)
    )


def plan(
    package: Any, names: Sequence[str], facts: Any
) -> tuple[list[tuple[Any, Any]], list[str]]:
    """Return ([(glyph, layer)] to delete, [skip texts]). Change nothing."""

    masters = [str(m) for m in package.masters]
    jobs: list[tuple[Any, Any]] = []
    skipped: list[str] = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        reason = history.refusal(facts, str(glyph.name), "geometry")
        if reason:
            skipped.append(f"{glyph.name}: {reason}")
            continue
        active = glyph.updateActiveLayer(False)
        shown = int(active.id) if active is not None and not active.isNull else None
        for layer in glyph.layers:
            if not is_empty_auxiliary(layer, masters):
                continue
            mask = layer.getMaskLayer(False)
            if int(layer.id) == shown:
                skipped.append(f"{glyph.name}/{layer.name}: shown layer")
            elif layer.isLocked or (
                mask is not None and not mask.isNull and mask.isLocked
            ):
                skipped.append(f"{glyph.name}/{layer.name}: locked layer")
            else:
                jobs.append((glyph, layer))
    return jobs, skipped


def doomed_layers(jobs: Sequence[tuple[Any, Any]]) -> list[tuple[Any, Any, str]]:
    """Return [(glyph, layer, name)] in removal order: each empty mask, then its layer.

    Names are read now, before the layers go.
    """
    found = []
    for glyph, layer in jobs:
        mask = layer.getMaskLayer(False)
        if mask is not None and not mask.isNull:
            found.append((glyph, mask, str(mask.name)))
        found.append((glyph, layer, str(layer.name)))
    return found


def undo_layer(glyph: Any, doomed: set[int], masters: Sequence[str]) -> Any:
    """Return the first master layer of ``glyph`` that stays.

    FontLab records an Undo step only for a list of layers plus their glyph;
    a glyph alone adds no step. ``doomed`` holds layer ids. Raise ValueError
    when no master layer is left.
    """
    for master in masters:
        layer = glyph.findLayer(master)
        if (
            layer is not None
            and not layer.isNull
            and int(layer.id) not in doomed
            and not layer.autoLayer
        ):
            return layer
    raise ValueError(f"'{glyph.name}' has no layer left to record the Undo step.")


def plural(count: int, word: str) -> str:
    """Return "1 glyph" or "2 glyphs"."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def remove(
    tool: Any,
    jobs: Sequence[tuple[Any, Any]],
    masters: Sequence[str],
    title: str = TITLE,
) -> dict | None:
    """The original ``remove`` through ``tool.shell.history``: ONE Undo step; None when refused."""
    glyphs = list({str(g.name): g for g, _ in jobs}.values())
    names = doomed_layers(jobs)
    doomed = {int(layer.id) for _, layer, _ in names}
    carriers = [undo_layer(glyph, doomed, masters) for glyph in glyphs]

    def mutate() -> None:
        for glyph, layer, _ in names:
            glyph.removeLayer(layer)

    def read_back() -> list[str]:
        return [
            f"{glyph.name}: layer '{name}' is still there"
            for glyph, layer, name in names
            if int(layer.id) in {int(x.id) for x in glyph.layers}
        ]

    done = commit(tool, title, carriers, glyphs, mutate, read_back=read_back)
    return None if done is None else result_dict(done)


def skipped_row(text: str) -> tuple[str, None, tuple[str, str]]:
    """A table row for one skipped entry of ``plan``.

    ``plan`` writes "glyph/layer: reason" for a kept layer and "glyph: reason"
    for a refused glyph (no layer); both, and any other text, give a row.
    """
    head, sep, reason = text.partition(": ")
    if not sep:
        head, reason = text, ""
    glyph, _, layer = head.partition("/")
    return glyph, None, (layer, f"skipped: {reason}" if reason else "skipped")


class EmptyPanel(PlanTab):
    """The original's run as a dry-run list: empty layers to delete, skipped ones kept."""

    ACTION = "Delete Empty Layers"
    HEADERS = ("Glyph", "Layer", "Action")
    NO_FONT_TEXT = "Open a font first."
    CHANGED_TEXT = "The font changed. Run this script again."
    NONE = "No empty layer in the selected glyphs."
    STATUS_REFUSALS = (NONE,)

    def plan(self) -> tuple[list[tuple[Any, Any]], list[str]]:
        package = self.bound()
        if not self.names:
            raise ValueError("Select glyphs in the Font window first.")
        jobs, skipped = plan(package, self.names, history.scan_auto_facts(package))
        if not jobs:
            raise ValueError(self.NONE)
        return jobs, skipped

    def rows(self, items: Any) -> list[tuple]:
        jobs, skipped = items
        done = [(str(g.name), str(x.name), (str(x.name), "delete")) for g, x in jobs]
        return done + [skipped_row(text) for text in skipped]

    def key(self, items: Any) -> Any:
        jobs, skipped = items
        return tuple((int(g.id), int(x.id)) for g, x in jobs), tuple(skipped)

    def ready_items(self, items: Any) -> bool:
        return bool(items[0])

    def summary(self, items: Any) -> str:
        jobs, skipped = items
        return f"{plural(len(jobs), 'empty layer')} will be deleted · {len(skipped)} skipped"

    def write(self, items: Any) -> str | None:
        jobs, skipped = items
        package = self.bound()
        result = remove(self.tool, jobs, [str(m) for m in package.masters],
                        undo_label("delete empty layers", [g.name for g, _ in jobs]))  # fmt: skip
        if result is None:
            return None
        glyphs = len({str(g.name) for g, _ in jobs})
        shown = ", ".join(f"{g.name}/{x.name}" for g, x in jobs[:MAX_LISTED])
        extra = f" and {len(jobs) - MAX_LISTED} more" if len(jobs) > MAX_LISTED else ""
        text = f"Deleted {plural(len(jobs), 'empty layer')} from {plural(glyphs, 'glyph')}: {shown}{extra}."
        if skipped:
            more = (
                f" and {len(skipped) - MAX_LISTED} more"
                if len(skipped) > MAX_LISTED
                else ""
            )
            text += f" Skipped {len(skipped)}: {'; '.join(skipped[:MAX_LISTED])}{more}."
        if result["mismatches"]:
            text += (
                " Did not read back as planned: "
                + "; ".join(result["mismatches"])
                + "."
            )
        return append_note(text, result)


__all__ = [
    "DATA_FIELDS",
    "TITLE",
    "EmptyPanel",
    "doomed_layers",
    "is_empty_auxiliary",
    "plan",
    "remove",
    "skipped_row",
    "undo_layer",
]
