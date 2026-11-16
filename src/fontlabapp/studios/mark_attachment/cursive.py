# this_file: src/fontlabapp/studios/mark_attachment/cursive.py
# SPDX-License-Identifier: Apache-2.0
"""Cursive tab (Scriptmix Auto Cursive Attachment Get Sample and Add Anchors).

Get sample: one selected body layer with ``entry``/``exit`` anchors inside
closed ink is measured (``measure_sample``) and saved as a NEW
``fontlab-cursive-sample-1`` JSON file (an existing file is never
overwritten; default folder: home). The format is the originals', so the old
and the new tool read each other's samples. It writes nothing to the font.

Add anchors: the sample (same master only) fits the missing ``exit`` (ini,
med) and ``entry`` (fin, med) anchors of the selected glyphs on the current
master: 10–500 unit ink spans near the connection edge, scored by thickness
and boundary angle, rounded half up (``choose_attachment``,
``cursive_changes``; unchanged). A layer that cannot be fitted becomes a
note row. Apply writes the listed anchors as one
``Mark Attachment: add cursive anchors <subject>`` Undo step.

The originals import ``fly.ap.anchors.writer`` inside two functions; here
that name is the reused backend (``anchor_writer`` below), the only change.
"""

import io
import json
import math
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import current_package

from .._kerning_ui import button, get, label
from . import _shared

TITLE = "Auto Cursive Attachment Get Sample"
Point = tuple[float, float]
Rings = list[list[Point]]
#: ``fly.ap.anchors.writer`` of the originals.
anchor_writer = _shared.Modules("anchors")
FILTER = "Cursive sample (*.json)"


def outline_rings(layer: Any) -> Rings:
    """Flatten transformed, closed outline shapes; keep contour winding and holes."""
    rings: Rings = []
    for shape in layer.shapes:
        if (
            shape.isComposite
            or not shape.transform.isAffine()
            or not shape.openedPath.isEmpty()
        ):
            raise ValueError("Use closed, decomposed outlines for cursive sampling.")
        for polygon in shape.closedPath.toSubpathPolygons(shape.transform):
            # PythonQt QPolygonF is neither iterable nor subscriptable (native probe).
            points = (polygon.at(index) for index in range(polygon.size()))
            ring = [(float(point.x()), float(point.y())) for point in points]
            if len(ring) >= 3:
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                if not all(math.isfinite(v) for point in ring for v in point):
                    raise ValueError("Outline coordinates must be finite.")
                rings.append(ring)
    if not rings:
        raise ValueError("No closed outline was found.")
    return rings


def vertical_spans(rings: Rings, x: float) -> list[tuple[float, float, float, float]]:
    """Return filled vertical spans and their boundary angles using nonzero winding."""
    hits: dict[float, list[tuple[int, float]]] = {}
    for ring in rings:
        for (ax, ay), (bx, by) in pairwise(ring):
            if min(ax, bx) <= x < max(ax, bx):
                y = ay + (x - ax) * (by - ay) / (bx - ax)
                tangent = (
                    math.atan2(by - ay, bx - ax) + math.pi / 2
                ) % math.pi - math.pi / 2
                hits.setdefault(y, []).append((1 if bx > ax else -1, tangent))
    spans = []
    winding = 0
    lower, lower_angle = 0.0, 0.0
    for y, values in sorted(hits.items()):
        previous = winding
        winding += sum(direction for direction, _ in values)
        if previous == 0 and winding != 0:
            lower, lower_angle = y, values[0][1]
        if previous != 0 and winding == 0 and y > lower:
            spans.append((lower, y, lower_angle, values[0][1]))
    return spans


def measure_sample(rings: Rings, points: list[Point]) -> dict[str, float]:
    """Average thickness fractions and boundary tangents around entry/exit pins."""
    if not points:
        raise ValueError("Create an entry or exit anchor inside the outline first.")
    samples = []
    for x, y in points:
        spans = [span for span in vertical_spans(rings, x) if span[0] <= y <= span[1]]
        if not spans:
            raise ValueError("Every sample anchor must lie inside closed ink.")
        low, high, low_angle, high_angle = min(
            spans, key=lambda span: span[1] - span[0]
        )
        samples.append((y - low, high - y, low_angle, high_angle))
    count = len(samples)
    values = [sum(sample[i] for sample in samples) / count for i in range(2)]
    for i in (2, 3):
        values.append(
            math.atan2(
                sum(math.sin(2 * s[i]) for s in samples),
                sum(math.cos(2 * s[i]) for s in samples),
            )
            / 2
        )
    return dict(zip(("below", "above", "lower_angle", "upper_angle"), values))


def validate_profile(data: Any) -> dict[str, float]:
    """Require a finite, nonnegative thickness profile and two tangent angles."""
    fields = ("below", "above", "lower_angle", "upper_angle")
    try:
        profile = {key: float(data[key]) for key in fields}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError("Sample needs four numeric profile values.") from error
    if not all(math.isfinite(value) for value in profile.values()):
        raise ValueError("Sample values must be finite.")
    if (
        min(profile["below"], profile["above"]) < 0
        or profile["below"] + profile["above"] <= 0
    ):
        raise ValueError("Sample must have positive ink thickness.")
    return profile


def sample_document(layer: Any, master: str) -> dict[str, Any]:
    """Capture the two named connection pins and package the portable profile."""

    pins = [pin for pin in layer.anchors if pin.name in ("entry", "exit")]
    if len({pin.name for pin in pins}) != len(pins):
        raise ValueError("Entry and exit names must be unique.")
    profile = measure_sample(
        outline_rings(layer), [anchor_writer.raw_point(pin) for pin in pins]
    )
    return {
        "format": "fontlab-cursive-sample-1",
        "master": master,
        "profile": validate_profile(profile),
    }


def save_document(path: str, document: dict[str, Any]) -> None:
    """Write a new UTF-8 file; leave any existing file untouched."""
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.write("\n")
    except FileExistsError as error:
        raise ValueError(
            "Choose a new file name; existing sample files stay unchanged."
        ) from error


def needed_connections(name: str) -> list[str]:
    """Retain the source tool's form-name routing without Unicode guesses."""
    lower = name.lower()
    return (["exit"] if "ini" in lower or "med" in lower else []) + (
        ["entry"] if "fin" in lower or "med" in lower else []
    )


def choose_attachment(
    rings: Rings, profile: dict[str, float], candidates: list[float]
) -> Point:
    """Pick the first minimum of thickness and undirected boundary-angle errors."""
    profile = validate_profile(profile)
    thickness = profile["below"] + profile["above"]
    best: tuple[float, Point] | None = None
    deadline = monotonic() + 1.5
    for x in candidates:
        if monotonic() >= deadline:
            raise TimeoutError("Cursive fitting exceeded its time budget.")
        for low, high, lower_angle, upper_angle in vertical_spans(rings, x):
            distance = high - low
            if not 10 <= distance <= 500:
                continue
            errors = [
                (actual - profile[key] + math.pi / 2) % math.pi - math.pi / 2
                for actual, key in (
                    (lower_angle, "lower_angle"),
                    (upper_angle, "upper_angle"),
                )
            ]
            score = (distance - thickness) ** 2 + 25 * sum(
                error * error for error in errors
            )
            point = (x, low + distance * profile["below"] / thickness)
            if best is None or score < best[0]:
                best = (score, point)
    if best is None:
        raise ValueError("No suitable 10–500 unit ink span near the connection edge.")
    return best[1]


def read_sample(
    path: str, master: str, conversions: list[str] | None = None
) -> dict[str, float]:
    """Load a portable profile; reject text loss, wrong format and master mismatch."""
    if not path:
        raise ValueError("Choose a sample file.")
    try:
        raw = Path(path).read_bytes()
        if conversions is not None:
            if raw.startswith(b"\xef\xbb\xbf"):
                conversions.append("BOM removed")
            if b"\r" in raw:
                conversions.append("CR/CRLF read as LF")
        with io.TextIOWrapper(
            io.BytesIO(raw), encoding="utf-8-sig", newline=None
        ) as stream:
            text = stream.read()
        if any(char in text for char in ("\0", "\u00a0", "\u2028", "\u2029")):
            raise ValueError("Sample contains text that FontLab cannot preserve.")
        document = json.loads(text)
        if (
            not isinstance(document, dict)
            or document.get("format") != "fontlab-cursive-sample-1"
        ):
            raise ValueError("Choose a FontLab cursive sample JSON file.")
        if document.get("master") != master:
            raise ValueError("The sample master name must match the current master.")
        return validate_profile(document.get("profile"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read sample: {error}") from error


def cursive_changes(glyph: Any, layer: Any, profile: dict[str, float]) -> list[Any]:
    """Plan missing connections only, with deterministic near-edge searches."""

    existing = {pin.name for pin in layer.anchors}
    wanted = [name for name in needed_connections(glyph.name) if name not in existing]
    if not wanted:
        return []
    rings = outline_rings(layer)
    xs = [point[0] for ring in rings for point in ring]
    left, right = min(xs), max(xs)
    changes = []
    for name in wanted:
        start = math.floor(left) if name == "exit" else math.ceil(right) - 1
        step = 1 if name == "exit" else -1
        candidates = [
            start + step * i + 0.5
            for i in range(200)
            if left <= start + step * i + 0.5 < right
        ]
        point = choose_attachment(rings, profile, candidates)
        target = tuple(anchor_writer.half_up(value) for value in point)
        changes.append(
            anchor_writer.Change(name, "missing", str(target), ("set", name, target))
        )
    return changes


class CursivePanel(_shared.PlanPanel):
    """Get a cursive sample; add the missing entry/exit anchors it fits."""

    ACTION = "Add"
    UNDO = "add cursive anchors"
    WRITER = "anchors"

    def build_controls(self, form: Any) -> None:
        line = QtGui.QHBoxLayout()
        form.addLayout(line)
        label(self.widget, line, "Sample JSON path")
        self.sample_path = QtGui.QLineEdit(self.widget)
        self.sample_path.setAccessibleName("Sample JSON path")
        line.addWidget(self.sample_path, 1)
        self.sample_path.textChanged.connect(
            lambda *args: self.ready and self.run(self.refresh)
        )
        self.browse_button = button(
            self.widget, line, "Browse…", lambda: self.run(self.choose_profile)
        )
        self.sample_info = label(self.widget, form, "Choose a sample file.")

    def add_buttons(self, buttons: Any) -> None:
        self.sample_button = button(
            self.widget, buttons, "Get sample…", lambda: self.run(self.get_sample)
        )

    # file choosers (tests replace them) -------------------------------------------
    def dialog(self, title: str, folder: str) -> Any:
        dialog = QtGui.QFileDialog(self.widget, title, folder)
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        dialog.setNameFilter(FILTER)
        return dialog

    def save_path(self) -> str:
        """The originals' save chooser: home folder, any new file, no overwrite question."""
        kind = QtGui.QFileDialog
        dialog = self.dialog(TITLE, str(Path.home()))
        dialog.setAcceptMode(kind.AcceptSave)
        dialog.setOption(kind.DontConfirmOverwrite, True)
        dialog.setFileMode(kind.AnyFile)
        dialog.setDefaultSuffix("json")
        return dialog.selectedFiles()[0] if dialog.exec_() else ""

    def open_path(self) -> str:
        dialog = self.dialog("Open Cursive Sample", "")
        dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
        return dialog.selectedFiles()[0] if dialog.exec_() else ""

    # actions --------------------------------------------------------------------
    def choose_profile(self) -> None:
        """Choose an existing sample; changing the path rebuilds the dry run."""
        path = self.open_path()
        if path:
            self.sample_path.setText(path)

    def get_sample(self) -> dict[str, Any] | None:
        """The original Get Sample ``main``: one body layer, one new file; nothing in the font changes."""
        b = _shared.backends()
        selection = b.selection.capture(monotonic() + 1.5)
        package = current_package()
        if package is None or len(selection.occurrences) != 1:
            raise ValueError("Select exactly one glyph layer in an open font.")
        layer = selection.occurrences[0].layer
        if layer.isMaskLayer or layer.isService:
            raise ValueError("Choose a body layer for the sample.")
        master = b.masters.associated_master(layer.name, package.masters)
        if master is None:
            raise ValueError("The layer has no associated font master.")
        document = sample_document(layer, master)
        path = self.save_path()
        if not path:
            return None
        save_document(path, document)
        self.sample_path.setText(path)
        self.tool.say(f"Saved cursive sample: {path}")
        return document

    # plan -------------------------------------------------------------------------
    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        conversions: list[str] = []
        self.sample_info.setText("")
        profile = read_sample(
            get(self.sample_path.text).strip(), self.tool.current, conversions
        )
        self.sample_info.setText(
            "; ".join(conversions) + "."
            if conversions
            else "No text conversion needed."
        )

        def changes(glyph: Any, master: str, layer: Any) -> list[Any]:
            try:
                return cursive_changes(glyph, layer, profile)
            except (ValueError, RuntimeError, TimeoutError) as error:
                return [anchor_writer.Change("cursive", "", f"{error}; layer skipped")]

        return changes

    def refresh(self) -> None:
        """Contain sample and scan errors in the tab and turn Apply off (as the original)."""
        try:
            super().refresh()
        except (ValueError, RuntimeError, TimeoutError, OSError) as error:
            self.apply_button.setEnabled(False)
            self.count.setText(str(error))

    def summary(self) -> str:
        dry = self.dry
        return f"{_shared.plural(dry.edits, 'anchor')} to add on {_shared.plural(len(dry.work), 'layer')}"

    def editor(self) -> Any:
        return _shared.AnchorEdit()


__all__ = [
    "FILTER", "TITLE", "CursivePanel", "choose_attachment", "cursive_changes", "measure_sample", "needed_connections",
    "outline_rings", "read_sample", "sample_document", "save_document", "validate_profile", "vertical_spans",
]  # fmt: skip
