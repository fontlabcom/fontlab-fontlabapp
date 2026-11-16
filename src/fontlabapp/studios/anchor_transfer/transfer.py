# this_file: src/fontlabapp/studios/anchor_transfer/transfer.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor Transfer plans, dry-run snapshots and the write paths. Qt-free.

What: the planners of Copy Anchors From Glyph (``anchors.copy.model.plan``),
Mirror Across Masters, Derive Anchors From Components and Add Anchors From
File (their pure functions copied unchanged from Scriptmix), the plan of
``anchors.writer.collect`` and ``apply``: it re-plans from the live font,
refuses with "press Refresh" when the plan or a target layer differs from
the dry run, and writes exactly the shown edits through one
``AppShell.history`` call labelled ``"Anchor Transfer: <action> <subject>"``
(Issue 235 §1.3/§1.4). Coordinates are written as each original computed
them; nothing is rounded again. Copy Anchors Between Fonts writes another
font: ``fonts_preview`` plans it with ``anchors.crossfont.model.copy_layer``
and ``fonts_apply`` hands the same options to the crossfont backend, one
Undo step in the destination font with this app's label.
Used by the tabs of ``fontlabapp.studios.anchor_transfer``.
"""

import csv
import io
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any

from fontlabapp.core.scripting import anchor_transfer_backends

_backends = anchor_transfer_backends()
anchor_writer = _backends.writer
history = _backends.history
crossfont = _backends.crossfont

APP = "Anchor Transfer"
#: Shown when the live plan differs from the dry run.
STALE = "Anchors changed since the dry run; press Refresh."
#: Every partly-applied message ends with this hint (as Anchor Studio).
ROUNDING_NOTE = "Check Preferences > Rounding."
ALLOW_AUTO_LABEL = "Edit bases of auto glyphs anyway"
SAME_FONT = "Choose two different fonts: the source font cannot also be the destination."

# Copy Anchors From Glyph
MODES = ["Add and move (keep other anchors)", "Replace (remove anchors the source lacks)"]
SCALE_LABEL = "Scale x by advance-width ratio"
# Mirror Across Masters
ONLY_MISSING = "Only add missing anchors"
ONE_MASTER = "This font has one master. Nothing to mirror into."
NO_TARGETS = "Tick the masters to copy into."
# Add Anchors From File
CSV_INFO = "Coordinates round half up to font units."
CSV_FILTER = "Anchor table (*.csv)"
CSV_TITLE = "Open Anchor CSV"
# Copy Anchors Between Fonts
ALL_MASTERS = crossfont.model.ALL_MASTERS

Matrix = tuple[float, float, float, float, float, float]


# ---------------------------------------------------------------- copied unchanged from Scriptmix
def mirror_changes(
    source: Any, target: Any, scale: bool, only_missing: bool
) -> list[anchor_writer.Change]:
    """Rows to bring `target` in line with `source`. Positions round half up."""
    ratio = (
        target.advanceWidth / source.advanceWidth
        if scale and source.advanceWidth
        else 1.0
    )
    wanted = anchor_writer.duplicated(source, [pin.name for pin in source.anchors])
    if wanted:
        return anchor_writer.refusal(wanted)
    current = anchor_writer.anchor_points(target)
    changes: list[anchor_writer.Change] = []
    for name, (x, y) in anchor_writer.anchor_points(source).items():
        if only_missing and name in current:
            continue
        new = (anchor_writer.half_up(x * ratio), anchor_writer.half_up(y))
        old = current.get(name)
        if old is not None and tuple(old) == new:
            continue
        before = (
            "–"
            if old is None
            else f"{anchor_writer.fmt(old[0])}, {anchor_writer.fmt(old[1])}"
        )
        changes.append(
            anchor_writer.Change(
                name, before, f"{new[0]}, {new[1]}", ("set", name, new)
            )
        )
    clash = anchor_writer.duplicated(target, [c.name for c in changes])
    return anchor_writer.refusal(clash) if clash else changes


def attachment_in_base(
    point: tuple[float, float], mark_matrix: Matrix, base_matrix: Matrix
) -> tuple[float, float]:
    """Transform a mark point into the base's own coordinates, with a checked inverse."""
    a, b, c, d, tx, ty = mark_matrix
    x, y = point
    px, py = a * x + c * y + tx, b * x + d * y + ty
    a, b, c, d, tx, ty = base_matrix
    determinant = a * d - b * c
    if (
        not all(math.isfinite(v) for v in (*point, *mark_matrix, *base_matrix))
        or abs(determinant) < 1e-12
    ):
        raise ValueError("Component transforms must be finite and invertible.")
    px, py = px - tx, py - ty
    result = ((d * px - c * py) / determinant, (a * py - b * px) / determinant)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("Component attachment coordinates must be finite.")
    return result


def coefficients(shape: Any) -> Matrix:
    """Read Qt's six affine coefficients; refuse perspective transforms."""
    matrix = shape.transform
    if not matrix.isAffine():
        raise ValueError("Perspective components cannot supply an anchor.")
    return (
        matrix.m11(),
        matrix.m12(),
        matrix.m21(),
        matrix.m22(),
        matrix.dx(),
        matrix.dy(),
    )


def layer_evidence(
    package: Any, composite: Any, master: str, masters: list[str], deadline: float
) -> tuple[tuple[str, str] | None, dict, list[str]]:
    """Resolve one composite completely; the first mark per label supplies evidence."""
    marks, bases, messages = [], [], []
    doubtful = False
    for shape in composite.shapes:
        if monotonic() >= deadline:
            raise TimeoutError("layer time budget exceeded, skipped")
        if not shape.isComponent:
            continue
        reference = shape.shapeData
        glyph = package.findName(str(reference.componentGlyph))
        layer_name = str(reference.componentLayer) or master
        layer = anchor_writer.layer_of(glyph, layer_name) if glyph else None
        if layer is None or layer.autoLayer:
            messages.append(
                f"{reference.componentGlyph}: missing or automatic referenced layer, skipped"
            )
            doubtful = True
            continue
        pins = [pin for pin in layer.anchors if pin.name.startswith("_")]
        if len(pins) > 1:
            messages.append(f"{glyph.name}: ambiguous mark, skipped")
        elif pins:
            marks.append((shape, pins[0]))
        else:
            bases.append((shape, glyph, layer_name, layer))
    if doubtful or not marks or len(bases) != 1:
        return None, {}, messages
    base_shape, base_glyph, layer_name, base_layer = bases[0]
    if layer_name not in masters:
        return (
            None,
            {},
            messages + [f"{base_glyph.name}: non-master base reference, skipped"],
        )
    present = {pin.name for pin in base_layer.anchors}
    candidates = {}
    for mark_shape, pin in marks:
        if monotonic() >= deadline:
            raise TimeoutError("layer time budget exceeded, skipped")
        label = pin.name[1:]
        if not label or label in present or label in candidates:
            continue
        x, y = attachment_in_base(
            anchor_writer.raw_point(pin),
            coefficients(mark_shape),
            coefficients(base_shape),
        )
        candidates[label] = (anchor_writer.half_up(x), anchor_writer.half_up(y))
    return (base_glyph.name, layer_name), candidates, messages


def derived_points(
    package: Any, names: list[str], masters: list[str], notes: dict | None = None
) -> dict:
    """Keep clean evidence across all layers; doubtful evidence becomes note rows."""
    result: dict[tuple[str, str], dict[str, tuple[int, int]]] = {}
    notes = {} if notes is None else notes
    conflicts: set[tuple[str, str, str]] = set()
    for name in names:
        for master in masters:
            owner = (name, master)
            composite = anchor_writer.layer_of(package.findName(name), master)
            if composite is None or composite.autoLayer:
                continue
            try:
                target, candidates, messages = layer_evidence(
                    package, composite, master, masters, monotonic() + 1.5
                )
            except (ValueError, RuntimeError, TimeoutError) as error:
                target, candidates, messages = None, {}, [f"{error}; layer skipped"]
            for message in messages:
                notes.setdefault(owner, []).append(
                    anchor_writer.Change("components", "", message)
                )
            if target is None:
                continue
            destination = result.setdefault(target, {})
            for label, point in candidates.items():
                identity = (*target, label)
                if identity in conflicts:
                    continue
                if label in destination and destination[label] != point:
                    destination.pop(label)
                    conflicts.add(identity)
                    notes.setdefault(target, []).append(
                        anchor_writer.Change(label, "", "conflicting evidence, skipped")
                    )
                else:
                    destination[label] = point
    return result


def parse_table(text: str) -> dict[str, dict[str, tuple[float, float]]]:
    """Parse the entire CSV before planning any writes. Reject ambiguous input."""
    if any(char in text for char in ("\0", "\u00a0", "\u2028", "\u2029")):
        raise ValueError("CSV contains text that FontLab cannot preserve.")
    reader = csv.DictReader(io.StringIO(text))
    fields = [field.strip() for field in (reader.fieldnames or [])]
    reader.fieldnames = fields
    unknown = [
        field
        for field in fields
        if field not in ("name", "glyph")
        and not (field.endswith(("_x", "_y")) and len(field) > 2)
    ]
    if unknown:
        raise ValueError("Unknown CSV columns: " + ", ".join(unknown))
    if len(fields) != len(set(fields)):
        raise ValueError("CSV column names must be unique.")
    identity = "name" if "name" in fields else "glyph"
    if identity not in fields:
        raise ValueError("CSV needs a name or glyph column.")
    labels = [field[:-2] for field in fields if field.endswith("_x")]
    if not labels or any(not name or name + "_y" not in fields for name in labels):
        raise ValueError("Pair every anchor _x column with an _y column.")
    if any(field.endswith("_y") and field[:-2] not in labels for field in fields):
        raise ValueError("An anchor _y column has no _x column.")
    table: dict[str, dict[str, tuple[float, float]]] = {}
    for row in reader:
        name = (row.get(identity) or "").strip()
        if (
            not name
            or name in table
            or None in row
            or any(v is None for v in row.values())
        ):
            raise ValueError("CSV has an empty/repeated glyph name or a ragged row.")
        table[name] = {}
        for label in labels:
            cells = (row[label + "_x"].strip(), row[label + "_y"].strip())
            if cells == ("", ""):
                continue
            try:
                point = tuple(float(value) for value in cells)
            except ValueError as error:
                raise ValueError(
                    f"{name}/{label}: enter both numeric coordinates."
                ) from error
            if not all(math.isfinite(value) for value in point):
                raise ValueError(f"{name}/{label}: coordinates must be finite.")
            table[name][label] = tuple(anchor_writer.half_up(value) for value in point)
    if not table:
        raise ValueError("CSV has no glyph rows.")
    return table


def load_table(path: str) -> tuple[dict, str]:
    """Decode UTF-8 once, normalize newlines, and report only actual conversions."""
    if not path:
        raise ValueError("Choose an anchor CSV file.")
    try:
        raw = Path(path).read_bytes()
        with io.TextIOWrapper(
            io.BytesIO(raw), encoding="utf-8-sig", newline=None
        ) as stream:
            records = parse_table(stream.read())
        conversions = ["BOM removed"] if raw.startswith(b"\xef\xbb\xbf") else []
        if b"\r" in raw:
            conversions.append("CR/CRLF read as LF")
        return records, "; ".join(
            ["Coordinates round half up to font units", *conversions]
        ) + "."
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError(f"Cannot read CSV: {error}") from error


def file_table(path: str) -> dict[str, dict[str, tuple[int, int]]]:
    """Read the rounded table for callers that do not need its conversion report."""
    return load_table(path)[0]


def import_changes(
    layer: Any, values: dict[str, tuple[float, float]]
) -> list[anchor_writer.Change]:
    """Keep equal points untouched; refuse repeated target names through the writer."""
    current = anchor_writer.anchor_points(layer)
    return [
        anchor_writer.Change(
            name, str(current.get(name, "missing")), str(point), ("set", name, point)
        )
        for name, point in values.items()
        if current.get(name) != point
    ]


# ---------------------------------------------------------------- From glyph
def point_text(point: tuple[float, float] | None) -> str:
    """``"x, y"`` of a point, or "–" for none."""
    return "–" if point is None else f"{anchor_writer.fmt(point[0])}, {anchor_writer.fmt(point[1])}"


def copy_changes(source: Any, target: Any, scale: bool, replace: bool) -> list[Any]:
    """Copy Anchors From Glyph rows for one layer: ``anchors.copy.model.plan``, changes only.

    Both coordinates are rounded when read (``anchors.inspect.model``), then x
    becomes ``round(x * ratio)``, exactly as the original; a
    removal (Replace mode) is a "remove" edit.
    """
    rows = []
    for name, old, new in _backends.copy.plan(source, target, scale, replace):
        if old == new:
            continue
        edit = ("remove", name, None) if new is None else ("set", name, new)
        rows.append(anchor_writer.Change(name, point_text(old), "removed" if new is None else point_text(new), edit))
    return rows


def copy_planner(source: Any, scale: bool, replace: bool) -> Callable[..., list[Any]]:
    """Planner for ``collect``: the source glyph is skipped, missing source layers too."""

    def plan(glyph: Any, master: str, layer: Any) -> list[Any]:
        if glyph.name == source.name:
            return []
        src = anchor_writer.layer_of(source, master)
        return [] if src is None else copy_changes(src, layer, scale, replace)

    return plan


def mirror_planner(source_master: str, scale: bool, only_missing: bool) -> Callable[..., list[Any]]:
    """Mirror Across Masters planner: copy ``source_master`` into each target master."""

    def plan(glyph: Any, master: str, layer: Any) -> list[Any]:
        source = anchor_writer.layer_of(glyph, source_master)
        if source is None:
            return []
        return mirror_changes(source, layer, scale, only_missing)

    return plan


def mirror_targets(masters: list[str], ticked: Iterable[str], source_master: str) -> list[str]:
    """The ticked target masters without the source; refuse as the original did."""
    if len(masters) < 2:
        raise ValueError(ONE_MASTER)
    chosen = [m for m in masters if m in set(ticked) and m != source_master]
    if not chosen:
        raise ValueError(NO_TARGETS)
    return chosen


def derive_planner(package: Any, names: list[str], masters: list[str]) -> Callable[..., list[Any]]:
    """Derive Anchors From Components planner over the whole font and every master."""
    notes: dict[tuple[str, str], list[Any]] = {}
    inferred = derived_points(package, names, masters, notes)

    def changes(glyph: Any, master: str, layer: Any) -> list[Any]:
        return [
            anchor_writer.Change(name, "missing", str(point), ("set", name, point))
            for name, point in inferred.get((glyph.name, master), {}).items()
        ] + notes.get((glyph.name, master), [])

    return changes


def catalog_names() -> list[str]:
    """Every glyph of the current font, as Derive Anchors From Components read it."""
    return [row[0] for row in _backends.catalog.capture().rows]


def csv_planner(records: dict, glyphs: list[Any], master: str) -> Callable[..., list[Any]]:
    """Add Anchors From File planner on the current master; refuse as the original did."""
    if set(records) != {glyph.name for glyph in glyphs}:
        raise ValueError("CSV glyph rows changed; press Load.")
    for glyph in glyphs:
        if anchor_writer.layer_of(glyph, master) is None:
            raise ValueError(f"{glyph.name}: missing current master layer.")
    return lambda glyph, master, layer: import_changes(layer, records[glyph.name])


def csv_glyphs(package: Any, records: dict) -> list[Any]:
    """The glyphs of a loaded CSV; refuse "Missing glyphs: ..." as the original did."""
    missing = [name for name in records if package.findName(name) is None]
    if missing:
        raise ValueError("Missing glyphs: " + ", ".join(missing))
    return [package.findName(name) for name in records]


# ---------------------------------------------------------------- dry run
@dataclass
class Dry:
    """One dry run: exactly the ``work`` Apply writes, the shown rows and why Apply is off."""

    work: list = field(default_factory=list)
    #: ``(glyph name, master, (anchor, current, new))`` per shown row.
    rows: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    problem: str = ""
    #: Glyphs refused unless "Edit bases of auto glyphs anyway" is ticked, with the rebuild note.
    bases: frozenset = frozenset()
    note: str = ""
    shown: tuple = ()

    @property
    def anchors(self) -> int:
        return sum(len(edits) for _, _, edits in self.work)


def auto_facts(package: Any) -> Any:
    """A fresh whole-font ``core.history.glyphs.AutoFacts`` scan."""
    return history.scan_auto_facts(package)


def find_glyphs(package: Any, names: Iterable[str]) -> list[Any]:
    """The existing glyphs of ``names`` in ``package``, in order."""
    found = (package.findName(name) for name in names)
    return [glyph for glyph in found if glyph is not None and not glyph.isNull]


def subject(names: Iterable[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def fingerprint(work: list) -> tuple:
    """(glyph, layer, edits, target anchors, advance) of every planned layer."""
    return tuple(
        (glyph.name, str(layer.name), tuple(edits), tuple(sorted(anchor_writer.anchor_points(layer).items())),
         float(layer.advanceWidth))
        for glyph, layer, edits in work
    )  # fmt: skip


def rebuild_note(facts: Any, names: Iterable[str]) -> str:
    """The metrics panel's rebuild warning for the auto glyphs built on ``names``."""
    wanted = set(names)
    found = sorted({d for name in wanted for d in facts.dependants(name)} - wanted)
    if not found:
        return ""
    shown = ", ".join(found[:5]) + (f" +{len(found) - 5} more" if len(found) > 5 else "")
    return f"FontLab rebuilds auto glyphs {shown}; their anchors and locks may change and Undo does not restore them"


def dry_run(glyphs: list[Any], masters: list[str], planner: Callable[..., list[Any]], facts: Any) -> Dry:
    """Plan once with ``anchors.writer.collect`` and decide whether Apply may run.

    Auto layers are listed as skipped; a glyph that owns auto layers is
    refused; a base of auto glyphs needs the "Edit bases" tick (``bases``);
    an existing anchor moved to 0, 0 and repeated anchor names are refused by
    ``anchors.writer.require_safe`` (without its auto policy, which is above).
    """
    plan = anchor_writer.collect(glyphs, masters, planner)
    names = [glyph.name for glyph, _, _ in plan.work]
    owners = history.refusals(facts, names, "geometry", allow_bases=True)
    bases = {n for n in history.refusals(facts, names, "geometry") if n not in owners}
    problem = plan.problems[0] if plan.problems else ""
    if not problem and owners:
        reasons = [f"{name}: {why}" for name, why in owners.items()]
        problem = f"FontLab cannot undo edits to these glyphs: {anchor_writer.shown(reasons)}. Choose other glyphs."
    if not problem and plan.work:
        try:
            anchor_writer.require_safe(plan.work, history.auto_facts(()))
        except ValueError as error:
            problem = str(error)
    rows = []
    for label, change in plan.rows:
        name, _, master = label.partition(" · ")
        rows.append((name, master or None, (change.name, change.old, change.problem or change.new)))
    return Dry(plan.work, rows, plan.skipped, problem, frozenset(bases), rebuild_note(facts, bases),
               fingerprint(plan.work))  # fmt: skip


def apply(tool: Any, action: str, dry: Dry, replan: Callable[[], Dry | None], *, allow_bases: bool = False) -> bool:
    """Write exactly the edits of ``dry`` as one named Undo step.

    ``replan`` builds the same plan from the live font; when it differs from
    ``dry`` (another edit, another source or file) Apply raises
    ``ValueError(STALE)`` before any write. Return True when FontLab
    committed; a refusal leaves the shell's status text and returns False.
    """
    if not dry.work:
        raise ValueError("Nothing to change.")
    if dry.problem:
        raise ValueError(dry.problem)
    if dry.bases and not allow_bases:
        raise ValueError(f'{dry.note}. Tick "{ALLOW_AUTO_LABEL}" to go on.')
    live = replan() if tool.package is not None else None
    if live is None or live.shown != dry.shown or live.problem or live.bases != dry.bases:
        raise ValueError(STALE)
    work = live.work
    label = f"{APP}: {action} {subject(glyph.name for glyph, _, _ in work)}"
    glyphs = list({glyph.name: glyph for glyph, _, _ in work}.values())
    layers = [layer for _, layer, _ in work]
    prepared = [(layer, anchor_writer.prepare(layer, edits)) for _, layer, edits in work]
    before = [anchor_writer.anchor_points(layer) for layer in layers]

    def mutate() -> None:
        for layer, steps in prepared:
            anchor_writer.write(layer, steps)

    def read_back() -> list[str]:
        return anchor_writer.unstored(work, before)

    committed = tool.shell.history(label, glyphs, mutate, layers=layers, read_back=read_back,
                                   allow_bases=allow_bases)  # fmt: skip
    if committed is None:
        return False
    if committed.mismatches:
        tool.say(f"Partly applied: {label}. " + "; ".join(committed.mismatches) + f". {ROUNDING_NOTE}")
        return True
    plural = anchor_writer.plural
    note = f" · {plural(len(dry.skipped), 'auto layer')} skipped" if dry.skipped else ""
    note += f" · {committed.pending_note}" if committed.pending_note else ""
    tool.say(f"{label}. Changed {plural(live.anchors, 'anchor')} on {plural(len(work), 'layer')}{note}")
    return True


# ---------------------------------------------------------------- Between fonts
@dataclass
class FontsPlan:
    """A Copy Anchors Between Fonts dry run: the captured snapshot and the edits it implies."""

    args: tuple
    options: Any
    snapshot: Any
    rows: list
    names: list
    anchors: int
    problem: str = ""


def font_rows() -> tuple:
    """The open fonts as ``anchors.crossfont.capture.Font`` rows."""
    return crossfont.native.Backend().fonts()


def font_label(row: Any) -> str:
    """The original font-list text: ``"Name.vfc [#12]"``."""
    return f"{row.label or 'Untitled'} [#{row.identity}]"


def font_options(*, relative: bool = False, italic: bool = False, angle: int = 10, rename: bool = True,
                 rename_destination: bool = True, suffix: str = ".bak", specific: str | None = None) -> Any:
    """``anchors.crossfont.model.Options`` with the original defaults."""
    return crossfont.model.Options(relative, italic, angle, rename, rename_destination, suffix, specific)


def _capture(args: tuple) -> Any:
    return crossfont.capture.read(*args, monotonic() + 3)


def fonts_preview(source: int, destination: int, source_layer: str, destination_layer: str,
                  only_selected: bool, options: Any) -> FontsPlan:
    """Capture both fonts and list every edit ``copy_layer`` plans (no native name normalisation)."""
    if source == destination:
        raise ValueError(SAME_FONT)
    args = (source, destination, source_layer, destination_layer, only_selected)
    snapshot = _capture(args)
    rows, names, anchors, problem = [], [], 0, ""
    for name, left, right, src, dst in snapshot.layers:
        if src is None or dst is None:
            continue
        result = crossfont.model.copy_layer(src.pins, dst.pins, src.width, dst.width, options)
        if not result.edits:
            continue
        if dst.automatic and not problem:
            problem = "Automatic destination layers cannot safely receive copied anchors."
        names.append(name)
        for edit in result.edits:
            anchors += edit.action == "add"
            point = f"{anchor_writer.fmt(edit.pin.x)}, {anchor_writer.fmt(edit.pin.y)}"
            rows.append((name, right, (f"{left} → {right}", edit.action, edit.pin.name, point)))
    return FontsPlan(args, options, snapshot, rows, list(dict.fromkeys(names)), anchors, problem)


def fonts_apply(tool: Any, plan: FontsPlan, source_label: str) -> bool:
    """Copy exactly the previewed edits as one Undo step in the destination font.

    The fonts are captured again first; any difference from the dry run
    raises ``ValueError(STALE)``. A failure after the write started is
    "Partly applied: ...".
    """
    if plan.problem:
        raise ValueError(plan.problem)
    if not plan.rows:
        raise ValueError("Nothing to change.")
    if _capture(plan.args) != plan.snapshot:
        raise ValueError(STALE)
    label = f"{APP}: copy anchors from {source_label} to {subject(plan.names)}"
    try:
        result = crossfont.native.Backend().copy(*plan.args, plan.options, title=label)
    except crossfont.transaction.PartialWriteError as error:
        tool.say(f"Partly applied: {label}. {error}")
        return True
    lines = list(result["skipped"]) + [
        f"Zero source advance: {name}/{anchor}; used absolute x." for name, anchor in result["zero_advance"]
    ]
    summary = f"Copied {result['anchors']} anchors across {result['layers']} layers."
    if not result["anchors"]:
        summary = "Nothing to process! " + summary
    tool.say(f"{label}. {summary}" + (" " + " ".join(lines) if lines else ""))
    return True


__all__ = [
    "ALLOW_AUTO_LABEL", "ALL_MASTERS", "APP", "CSV_FILTER", "CSV_INFO", "CSV_TITLE", "MODES", "NO_TARGETS",
    "ONE_MASTER", "ONLY_MISSING", "ROUNDING_NOTE", "SAME_FONT", "SCALE_LABEL", "STALE", "Dry", "FontsPlan",
    "Matrix", "apply", "attachment_in_base", "auto_facts", "catalog_names", "coefficients", "copy_changes", "copy_planner",
    "csv_glyphs", "csv_planner", "derive_planner", "derived_points", "dry_run", "file_table", "find_glyphs",
    "fingerprint", "font_label", "font_options", "font_rows", "fonts_apply", "fonts_preview", "import_changes",
    "layer_evidence", "load_table", "mirror_changes", "mirror_planner", "mirror_targets", "parse_table",
    "point_text", "rebuild_note", "subject",
]
