# this_file: src/fontlabapp/studios/layer_manager/deliver.py
# SPDX-License-Identifier: Apache-2.0
"""Deliver tab: the Scriptmix "Deliver Glyphs" (Scripts/Masters/) and the Examples "Copy Layers From Font".

Mode "Deliver glyphs": the source glyphs are captured when the tab opens
or on "Use selection as source" (never on a refresh: the original bound
its source when it opened). Activate the destination Font window, press
Preview, check the rows, then Deliver. Missing glyphs are added with
FontLab's Add Glyph (``glyphs.creation``: one Undo step per new glyph,
the original's route), then every eligible master layer is filled as ONE
``Layer Manager: deliver glyphs <subject>`` Undo step through
``AppShell.history``. Only the destination font is written. The planning,
master pairing and the ``Delivery`` editor are the original's, verbatim;
Deliver refuses a destination or plan that differs from the Preview
("The delivery changed; click Preview again."). Native cross-font Undo
and Redo are not qualified here (Scriptmix TODO, T29).

Mode "Copy layers from font": ``_from_font``.
"""

import math
from time import monotonic
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning import Tool
from .._kerning_ui import Panel, button, check, label as text_label
from ._from_font import FromFontPanel
from ._modes import ModesPanel
from ._shared import Modules, apply_editor, hline, label as undo_label, refusal_text

anchors = Modules("anchors")
guards = Modules("guards")
glyph_copies = Modules("copies")
glyph_creation = Modules("creation")
outlines = Modules("outlines")
scripting = Modules("scripting")
selection = Modules("selection")
contour_copy = Modules("contour_copy")
fl = Modules("fontlab")


TITLE, KEY = "Deliver Glyphs", "masters_deliver_glyphs"
METRICS = ("advanceWidth", "metricsLeft", "metricsRight", "metricsWidth")


def master_pairs(
    source: list[str], target: list[str], fallback: str
) -> list[tuple[str, str, bool]]:
    """Pair each target with a source, reporting fallback and ambiguity."""
    normalized = [name.strip().casefold() for name in source]
    if (
        not source
        or not target
        or fallback not in source
        or len(normalized) != len(set(normalized))
    ):
        raise ValueError(
            "Source masters must be unique; both fonts need masters and a valid fallback."
        )
    mapping = dict(zip(normalized, source, strict=True))
    return [
        (
            name,
            mapping.get(name.strip().casefold(), fallback),
            name.strip().casefold() not in mapping,
        )
        for name in target
    ]


def usable_layer(layer: Any) -> None:
    """Refuse content that this cross-font writer cannot retain faithfully."""
    if layer is None or layer.isNull:
        raise ValueError("A master layer is missing.")
    if layer.autoLayer or layer.isLocked or layer.isMaskLayer or layer.isService:
        raise ValueError(
            "Automatic, locked, mask and service layers cannot be delivered."
        )
    if layer.hasHints or layer.hasTTH:
        raise ValueError(
            "Hinted layers cannot be delivered; no hint writer is available."
        )
    if any(shape.isComponent for shape in layer.shapes):
        raise ValueError(
            "Components cannot be delivered; use plain outlines or FontLab's native Paste."
        )
    for shape in layer.shapes:
        if int(shape.shapeData.referenceCount) > 1:
            raise ValueError("shared shape data")
        for contour in shape.contours:
            if contour.name:
                raise ValueError("contour name is not copied")
            for node in contour.nodes():
                if node.getProperty("corner_smooth") is not None:
                    raise ValueError("explicit corner_smooth is not copied")
    if not math.isfinite(float(layer.advanceWidth)):
        raise ValueError("Advance width must be finite.")


def copy_shapes(layer: Any) -> list[Any]:
    """Copy shapes; restore node names and raw flags through contour_copy only."""

    output = []
    for shape in layer.shapes:
        cloned = shape.clone()
        cloned.name = shape.name
        cloned.shapeData.name = shape.shapeData.name
        cloned.shapeData.note = shape.shapeData.note
        cloned.transform = shape.transform
        cloned.active = cloned.selected = False
        for before, after in zip(shape.contours, cloned.contours, strict=True):
            contour_copy.repair_nodes(before, after)
        output.append(cloned)
    return output


def glyph_codes(package: Any) -> dict[str, list[int]]:
    """Read the FontGate Unicode lists of a registered package; no flGlyph.fgGlyph getter."""
    return {str(glyph.name): list(glyph.unicodes) for glyph in package.fgPackage}


def delivery_plan(
    source: Any, target: Any, names: list[str], fallback: str, replace: bool
) -> list[dict[str, Any]]:
    """List each selected glyph as deliverable or kept; make no font changes."""

    if int(source.fgId) == int(target.fgId):
        raise ValueError("Activate a different destination font.")
    if float(source.info.unitsPerEm) != float(target.info.unitsPerEm):
        raise ValueError(
            "Source and destination units per em differ; scale deliberately before delivery."
        )
    if not names:
        raise ValueError("The source selection is empty; reopen the panel.")
    pairs = master_pairs(list(source.masters), list(target.masters), fallback)
    facts = history.scan_auto_facts(target)
    source_codes, target_codes = glyph_codes(source), glyph_codes(target)
    owners: dict[int, set[str]] = {}
    for name, codes in target_codes.items():
        for code in codes:
            owners.setdefault(code, set()).add(name)
    jobs = []
    for name in dict.fromkeys(names):
        job: dict[str, Any] = {
            "name": name,
            "existing": False,
            "layers": [],
            "unicodes": [],
            "metrics": {},
            "note": "",
            "unicode_changes": False,
        }
        try:
            glyph = source.findName(name)
            if glyph is None or glyph.isNull or name not in source_codes:
                raise ValueError("source glyph is missing")
            existing = target.findName(name)
            job["existing"] = existing is not None and not existing.isNull
            if job["existing"] and not replace:
                raise ValueError("already exists; Replace is off")
            reason = history.refusal(facts, name, "geometry")
            if reason:
                raise ValueError(reason)
            conflicts = [
                code for code in source_codes[name] if owners.get(code, set()) - {name}
            ]
            if conflicts:
                raise ValueError(
                    "Unicode already held by another destination glyph: "
                    + ", ".join(f"U+{c:04X}" for c in conflicts)
                )
            layers = []
            for destination, origin, guessed in pairs:
                layer = glyph.findLayer(origin)
                usable_layer(layer)
                if anchors.duplicated(layer, [str(pin.name) for pin in layer.anchors]):
                    raise ValueError("Duplicate anchor names in source")
                points = anchors.anchor_points(layer)
                if any(
                    not all(math.isfinite(v) for v in point)
                    for point in points.values()
                ):
                    raise ValueError("Anchor positions must be finite")
                if job["existing"]:
                    old = existing.findLayer(destination)
                    usable_layer(old)
                    if anchors.duplicated(old, [str(pin.name) for pin in old.anchors]):
                        raise ValueError("Duplicate anchor names in destination")
                    before = anchors.anchor_points(old)
                    if any(
                        n in before and point == (0.0, 0.0) and before[n] != point
                        for n, point in points.items()
                    ):
                        raise ValueError("an existing anchor would move to the origin")
                layers.append((destination, origin, guessed, layer, points))
            job.update(
                layers=layers,
                unicodes=target_codes[name] if job["existing"] else source_codes[name],
                metrics={key: getattr(glyph, key) for key in METRICS[1:]},
                unicode_changes=bool(source_codes[name]) and not job["existing"],
            )
            if not job["existing"]:
                for code in source_codes[name]:
                    owners.setdefault(code, set()).add(name)
        except ValueError as error:
            job["note"] = str(error)
        jobs.append(job)
    return jobs


def rebuild_rows(target: Any, jobs: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """Use the shared suffix-scoped auto-candidate scan for new glyphs only."""

    return glyph_creation.auto_candidates(
        target,
        history.scan_auto_facts(target),
        [j["name"] for j in jobs if not j["note"] and not j["existing"]],
    )


def deliver(
    tool: Any,
    target: Any,
    jobs: list[dict[str, Any]],
    consent: bool,
    title: str = TITLE,
) -> dict[str, Any]:
    """Add through glyph_creation; fill all eligible master layers in one action.

    The original ``deliver``: the outline step goes through ``tool.shell.history``
    (``apply_editor``) titled ``title``; Add Glyph keeps its own route.
    """

    current = scripting.current_package()
    if current is None or int(current.fgId) != int(target.fgId):
        raise ValueError("Activate the destination Font window first.")
    # This guard explicitly takes an object id, not a fontpr/workspace font id.
    guards.require_selection_window(int(current.id))
    guards.require_no_editors()
    ids = guards.pending_updates()
    ready = [j for j in jobs if not j["note"]]
    if not ready:
        return {
            "pending_updates": (),
            "pending_note": "",
            "created": 0,
            "glyphs": 0,
            "layers": 0,
            "unicode_changes": [],
        }
    # All source shape copies exist before the first Add Glyph command.
    prepared = [
        (
            job,
            [
                (
                    master,
                    copy_shapes(layer),
                    dict(points),
                    {key: getattr(layer, key) for key in METRICS},
                )
                for master, _, _, layer, points in job["layers"]
            ],
        )
        for job in ready
    ]
    facts = history.scan_auto_facts(target)
    specs = [
        glyph_creation.NewGlyph(
            job["name"],
            tuple(
                (master, glyph_copies.half_up(metrics["advanceWidth"]))
                for master, _, _, metrics in layers
            ),
            tuple(job["unicodes"]),
        )
        for job, layers in prepared
        if not job["existing"]
    ]
    auto_before = glyph_creation.auto_signatures(target, facts)
    made = glyph_creation.create_glyphs(
        target, specs, title, facts, allow_rebuild=consent
    )
    try:
        if made.mismatches:
            raise RuntimeError("; ".join(made.mismatches))
        work = []
        for job, layers in prepared:
            glyph = target.findName(job["name"])
            if glyph is None or glyph.isNull:
                raise RuntimeError(f"FontLab did not keep {job['name']}.")
            for master, shapes, points, metrics in layers:
                layer = glyph.findLayer(master)
                usable_layer(layer)
                before = anchors.anchor_points(layer)
                edits = [("remove", n, None) for n in before if n not in points] + [
                    ("set", n, point)
                    for n, point in points.items()
                    if before.get(n) != point
                ]
                work.append((glyph, layer, [(job, shapes, edits, metrics)]))

        class Delivery(outlines.Editor):
            """Write outlines and anchors only; Unicode is never assigned here."""

            def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
                job, shapes, pins, metrics = edits[0]
                return [
                    (
                        job,
                        list(layer.shapes),
                        shapes,
                        anchors.prepare(layer, pins),
                        metrics,
                    )
                ]

            def write(self, layer: Any, steps: list[Any]) -> None:
                for job, removed, shapes, pins, metrics in steps:
                    for shape in removed:
                        layer.removeShape(shape)
                    for shape in shapes:
                        layer.addShape(shape)
                    anchors.write(layer, pins)
                    for key, value in metrics.items():
                        setattr(layer, key, value)
                    glyph = target.findName(job["name"])
                    for key, value in job["metrics"].items():
                        setattr(glyph, key, value)

            def check(self, prepared: list[Any]) -> list[str]:
                errors = []
                codes = glyph_codes(target)
                for layer, steps in prepared:
                    for job, removed, shapes, _, metrics in steps:
                        ids = {shape.id for shape in layer.shapes}
                        if any(shape.id not in ids for shape in shapes) or any(
                            shape.id in ids for shape in removed
                        ):
                            errors.append(f"{job['name']}: shapes")
                        if (
                            any(
                                getattr(layer, key) != value
                                for key, value in metrics.items()
                            )
                            or codes.get(job["name"]) != job["unicodes"]
                        ):
                            errors.append(f"{job['name']}: metrics or Unicode")
                        points = next(
                            p
                            for master, _, _, _, p in job["layers"]
                            if master == str(layer.name)
                        )
                        if anchors.anchor_points(layer) != points:
                            errors.append(f"{job['name']}: anchors")
                return errors + glyph_creation.auto_changes(target, auto_before)

        result = apply_editor(tool, title, work, Delivery(), allow_bases=consent)
        if result is None:
            raise RuntimeError(refusal_text(tool))
        return {
            "pending_note": guards.pending_note(ids),
            "pending_updates": ids,
            "created": len(made.glyphs),
            "glyphs": len(ready),
            "layers": result["layers"],
            "unicode_changes": [j["name"] for j in ready if j["unicode_changes"]],
        }
    except (ValueError, RuntimeError, TimeoutError) as error:
        if "use Edit > Undo" not in str(error):
            raise RuntimeError(
                f"{error} Native changes may remain; use Edit > Undo"
            ) from error
        raise


def preview_rows(
    jobs: list[dict[str, Any]], candidates: dict[str, tuple[str, ...]] | None = None
) -> list[tuple[str, str, str, str]]:
    """Keep a visible row for every selected glyph, including each refusal."""

    rows = []
    for job in jobs:
        if job["note"]:
            rows.append((job["name"], "", "", "kept: " + job["note"]))
            continue
        for master, source, guessed, _, _ in job["layers"]:
            action = (
                "replace; Unicode kept"
                if job["existing"]
                else "add; Unicode assigned on creation"
                if job["unicode_changes"]
                else "add; no Unicode"
            )
            if (candidates or {}).get(job["name"]):
                action += "; " + glyph_creation.rebuild_note(candidates[job["name"]])
            rows.append(
                (
                    job["name"],
                    master,
                    source,
                    action + ("; fallback" if guessed else ""),
                )
            )
    return rows


class DeliverGlyphsPanel(Panel):
    """The original panel as a tab: Replace, the rebuild consent, the preview table, Preview and Deliver."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.source_id: int | None = None
        self.source_names: list[str] = []
        self.fallback = ""
        self.preview_token: tuple[Any, ...] | None = None
        self.replace_box = check(
            self.widget,
            self.layout,
            "Replace existing glyphs",
            False,
            self.contain(self.preview),
        )
        self.consent_box = check(
            self.widget, self.layout, glyph_creation.REBUILD_LABEL, False
        )
        text_label(self.widget, self.layout, glyph_creation.UNDO_TEXT)
        self.grid = self.table(
            ["Glyph", "Destination master", "Source master", "Action"], self.row_chosen
        )
        self.status = text_label(self.widget, self.layout)
        line = hline(self.layout)
        self.source_button = button(
            self.widget, line, "Use selection as source", self.contain(self.capture)
        )
        self.preview_button = button(
            self.widget, line, "Preview", self.contain(self.preview)
        )
        self.apply_button = button(self.widget, line, "Deliver", self.press)
        self.apply_button.setEnabled(False)
        self.capture()

    def capture(self) -> None:
        """Bind the source font and glyphs (the original did it when it opened)."""
        self.source_id, self.source_names, self.fallback = None, [], ""
        self.invalidate()
        try:
            package = self.tool.shell.package()
            if package is None:
                raise ValueError("Select glyphs in the source font first.")
            capture = selection.capture(monotonic() + 2.0)
            self.source_names = list(
                dict.fromkeys(o.glyph_name for o in capture.occurrences)
            )
            if not self.source_names:
                raise ValueError("Select source glyphs, then reopen this panel.")
            self.source_id, self.fallback = int(package.fgId), str(package.master)
            self.subtitle.setText(
                f"{len(self.source_names)} source glyphs · activate a destination Font window, then Preview"
            )
        except (ValueError, RuntimeError, TimeoutError) as error:
            self.subtitle.setText("")
            self.status.setText(str(error))

    def refresh(self) -> None:
        """A reload never rebinds the source; it drops a Preview that may be stale."""
        if self.preview_token is not None:
            self.invalidate()
            self.status.setText("The fonts changed; click Preview again.")

    def invalidate(self) -> None:
        self.preview_token = None
        self.grid.set_rows([])
        self.apply_button.setEnabled(False)

    def fresh_plan(self) -> tuple[Any, list[dict[str, Any]]]:
        """Require both fonts to remain open and a distinct current target."""
        if self.source_id is None:
            raise ValueError("Reopen this tool with a source selection.")
        source = fl.flWorkspace.instance().findPackageId(self.source_id)
        target = scripting.current_package()
        if source is None or source.isNull or target is None:
            raise ValueError("The source or destination font is closed.")
        return target, delivery_plan(source, target, self.source_names, self.fallback,
                                     bool(self.replace_box.isChecked()))  # fmt: skip

    def token(
        self, target: Any, jobs: list[dict[str, Any]]
    ) -> tuple[Any, list, list[str]]:
        candidates = rebuild_rows(target, jobs)
        rows = preview_rows(jobs, candidates)
        warnings = [
            f"{name}: {glyph_creation.rebuild_note(owners)}"
            for name, owners in candidates.items()
        ]
        return (int(target.fgId), tuple(rows), tuple(warnings)), rows, warnings

    def preview(self) -> None:
        """Display every master mapping, plus any automatic rebuild warning."""
        self.invalidate()
        self.consent_box.setChecked(False)
        try:
            target, jobs = self.fresh_plan()
            token, rows, warnings = self.token(target, jobs)
        except (ValueError, RuntimeError, TimeoutError) as error:
            self.status.setText(str(error))
            return
        self.grid.set_rows(
            [
                (name, master or None, (master, source, action))
                for name, master, source, action in rows
            ]
        )
        more = (
            ["More rebuild candidates are listed in the table."]
            if len(warnings) > 8
            else []
        )
        self.status.setText("\n".join([
            f"{sum(not j['note'] for j in jobs)} glyphs to deliver · {sum(bool(j['note']) for j in jobs)} kept",
            *warnings[:8], *more]))  # fmt: skip
        self.preview_token = token
        self.apply_button.setEnabled(any(not j["note"] for j in jobs))

    def press(self) -> None:
        """Check target and mapping against preview, then write current font."""
        try:
            target, jobs = self.fresh_plan()
            token, _, _ = self.token(target, jobs)
            if self.preview_token != token:
                raise ValueError("The delivery changed; click Preview again.")
            names = [j["name"] for j in jobs if not j["note"]]
            result = deliver(self.tool, target, jobs, bool(self.consent_box.isChecked()),
                             undo_label("deliver glyphs", names))  # fmt: skip
            self.preview()
            text = f"Delivered {result['glyphs']} glyphs in {result['layers']} layers; {result['created']} added." + (
                " · " + result["pending_note"] if result.get("pending_note") else "")  # fmt: skip
            self.status.setText(text)
            self.tool.say(text)
        except (ValueError, RuntimeError, TimeoutError) as error:
            self.apply_button.setEnabled(False)
            self.status.setText(str(error))

    def row_chosen(self, name: str, layer: Any) -> None:
        if self.tool.preview is not None and name:
            self.tool.preview.load(name, layer or None)


class DeliverPanel(ModesPanel):
    MODES = (
        ("Deliver glyphs", DeliverGlyphsPanel),
        ("Copy layers from font", FromFontPanel),
    )


__all__ = ["METRICS", "TITLE", "DeliverGlyphsPanel", "DeliverPanel", "copy_shapes", "deliver", "delivery_plan",
           "glyph_codes", "master_pairs", "preview_rows", "rebuild_rows", "usable_layer"]  # fmt: skip
