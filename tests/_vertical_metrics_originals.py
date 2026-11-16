# this_file: tests/_vertical_metrics_originals.py
"""The Scriptmix scripts this app absorbs: file hashes and verbatim pure functions and classes.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show origin/main:<path>``), not retyped.
Each entry is ``(path, sha256 of the whole file, names, source of those definitions)``; the parity tests
compare the ported bodies with these (AST equality). Scripts with no pure function (thin launchers or
dialog-only code) have empty names; their behaviour is covered by tests of the reused backend.
"""

ORIGINALS = {
    "Calculate Vertical Metrics": (
        "Scripts/Font Info/Calculate Vertical Metrics.py",
        "171957f5d1a73eb8f5e75b7831e372754790865b6cf13f0de4ec87740c303c26",
        ("number", "enclosing_metrics", "scan_bounds", "metric_plan"),
        "def number(value: Any) -> Any:\n"
        '    """965.0 -> 965 for display."""\n'
        "    return int(value) if isinstance(value, float) and value.is_integer() "
        "else value\n"
        "\n"
        "\n"
        "def enclosing_metrics(low: float, high: float, padding: int, gap: int) -> "
        "list[float]:\n"
        '    """Round bounds outward and validate OpenType metric limits."""\n'
        "    if (\n"
        "        not all(math.isfinite(v) for v in (low, high, padding, gap))\n"
        "        or low > high\n"
        "        or not 0 <= padding <= 2000\n"
        "        or not 0 <= gap <= 32767\n"
        "    ):\n"
        '        raise ValueError("Use finite bounds, padding 0–2000 and line gap '
        '0–32767.")\n'
        "    ascent = max(0, math.ceil(high) + padding)\n"
        "    descent = min(0, math.floor(low) - padding)\n"
        "    if ascent > 32767 or descent < -32768:\n"
        '        msg = "Bounds exceed signed 16-bit typo/hhea limits."\n'
        "        raise ValueError(msg)\n"
        "    return [ascent, descent, gap, ascent, descent, gap, ascent, -descent]\n"
        "\n"
        "\n"
        "def scan_bounds(package: Any) -> dict[str, tuple[float, float, int]]:\n"
        '    """Measure all nonempty glyph bounds with an interactive deadline."""\n'
        "    records = glyph_records(package)\n"
        "    result = {}\n"
        "    deadline = time.monotonic() + 2.5\n"
        "    for master in package.masters:\n"
        "        lows, highs = [], []\n"
        "        for name, _ in records:\n"
        "            if time.monotonic() > deadline:\n"
        '                msg = "Font too large for an interactive scan; no changes '
        'made."\n'
        "                raise ValueError(\n"
        "                    msg,\n"
        "                )\n"
        "            layer = package.findName(name).findLayer(master)\n"
        "            if layer is None or layer.isNull:\n"
        "                continue\n"
        "            box = layer.boundingBox\n"
        "            if box.width() == 0 and box.height() == 0:\n"
        "                continue\n"
        "            lows.append(box.y())\n"
        "            highs.append(box.y() + box.height())\n"
        "        if lows:\n"
        "            result[master] = (min(lows), max(highs), len(lows))\n"
        "    return result\n"
        "\n"
        "\n"
        "def metric_plan(\n"
        "    package: Any,\n"
        "    bounds: Any,\n"
        "    masters: Any,\n"
        "    padding: Any,\n"
        "    gap: Any,\n"
        "    fields: Any = METRIC_FIELDS,\n"
        ") -> Any:\n"
        '    """Build selected master and metric edits while restoring the active '
        'master."""\n'
        "    original = package.master\n"
        "    changes = []\n"
        "    try:\n"
        "        for master in masters:\n"
        "            if master not in bounds:\n"
        "                continue\n"
        "            package.setMaster(master)\n"
        "            values = enclosing_metrics(*bounds[master][:2], padding, gap)\n"
        "            changes.extend(\n"
        "                (master, k, getattr(package.info, k), v)\n"
        "                for k, v in zip(METRIC_FIELDS, values, strict=False)\n"
        "                if k in fields\n"
        "            )\n"
        "    finally:\n"
        "        package.setMaster(original)\n"
        "    return changes\n",
    ),
    "Master Metrics Table": (
        "Scripts/Font Info/Master Metrics Table.py",
        "227270400c504febeb813c695b97a8c301f1dd658742f270ce2dada456f97f4f",
        ("validate_metrics",),
        "def validate_metrics(values: list[float]) -> list[float]:\n"
        '    """Require four finite ordered metrics within signed 16-bit limits."""\n'
        "    if len(values) != 4 or not all(\n"
        "        math.isfinite(v) and -32768 <= v <= 32767 for v in values\n"
        "    ):\n"
        '        msg = "Use finite metrics between −32768 and 32767."\n'
        "        raise ValueError(msg)\n"
        "    asc, desc, xheight, cap = values\n"
        "    if not desc <= 0 <= xheight <= cap <= asc:\n"
        '        msg = "Expected descender ≤ 0 ≤ x-height ≤ cap-height ≤ ascender."\n'
        "        raise ValueError(msg)\n"
        "    return values\n",
    ),
    "Suggest Zones From Overshoots": (
        "Scripts/Guides/Suggest Zones From Overshoots.py",
        "0f8890a6e7c7c6b35886ff9319db939cf78be1d72fbbbde11f1b9eb12ebfe2fc",
        (
            "Suggestion",
            "overshoot_zone",
            "suggestions",
            "missing",
            "_at",
            "_named",
            "merge",
            "measure",
            "stage",
            "preview_row",
        ),
        "class Suggestion(NamedTuple):\n"
        '    """One measured zone: its name, kind, position and outward '
        'width."""\n'
        "\n"
        "    name: str\n"
        "    top: bool\n"
        "    position: int\n"
        "    width: int\n"
        "\n"
        "\n"
        "def overshoot_zone(flat: float, curved: float, top: bool) -> tuple[int, "
        "int]:\n"
        '    """Return ``(position, width)``: the flat edge and the overshoot '
        'beyond it."""\n'
        "    width = curved - flat if top else flat - curved\n"
        "    return round(flat), max(0, round(width))\n"
        "\n"
        "\n"
        "def suggestions(extents: Mapping[str, alignment_zones.Extent]) -> "
        "list[Suggestion]:\n"
        '    """Return the zones that the extents of H, O, x and o support, in '
        "rule order.\n"
        "\n"
        "    ``extents`` maps a glyph name to its ``(bottom, top)`` or ``None``. "
        "A rule\n"
        "    whose flat or round glyph is ``None`` or absent gives no zone.\n"
        '    """\n'
        "    found = []\n"
        "    for name, flat, curved, top in RULES:\n"
        "        pair = extents.get(flat), extents.get(curved)\n"
        "        if None in pair:\n"
        "            continue\n"
        "        edge = 1 if top else 0\n"
        "        position, width = overshoot_zone(pair[0][edge], pair[1][edge], "
        "top)\n"
        "        found.append(Suggestion(name, top, position, width))\n"
        "    return found\n"
        "\n"
        "\n"
        "def missing(extents: Mapping[str, alignment_zones.Extent]) -> "
        "list[str]:\n"
        '    """Return the rule names that ``suggestions`` skips for '
        '``extents``."""\n'
        "    return [\n"
        "        name\n"
        "        for name, flat, curved, _top in RULES\n"
        "        if extents.get(flat) is None or extents.get(curved) is None\n"
        "    ]\n"
        "\n"
        "\n"
        "def _at(position: int) -> Callable[[Zone], bool]:\n"
        '    """Return a test for a zone whose rounded position is '
        '``position``."""\n'
        "    return lambda zone: round(zone.position) == position\n"
        "\n"
        "\n"
        "def _named(name: str) -> Callable[[Zone], bool]:\n"
        '    """Return a test for a zone called ``name``."""\n'
        "    return lambda zone: zone.name == name\n"
        "\n"
        "\n"
        "def merge(zones: Zones, proposed: Sequence[Suggestion]) -> tuple[Zones, "
        "list[Zone | None]]:\n"
        '    """Return ``zones`` with ``proposed`` merged in, and the zone each '
        "one replaced.\n"
        "\n"
        "    A suggestion replaces the zone of its kind at the same position, "
        "else the\n"
        "    one with the same name, else it is added. A replaced zone keeps its "
        "name\n"
        "    and, so, its source identity (tags and lock). A zone is replaced "
        "once.\n"
        '    """\n'
        "    kinds = {True: list(zones.top), False: list(zones.bottom)}\n"
        "    replaced: list[Zone | None] = []\n"
        "    for item in proposed:\n"
        "        pool = kinds[item.top]\n"
        "        old = next(\n"
        "            (z for test in (_at(item.position), _named(item.name)) for z "
        "in pool if test(z)),\n"
        "            None,\n"
        "        )\n"
        "        new = Zone(item.position, item.width, item.name)\n"
        "        if old is not None:\n"
        "            pool.remove(old)\n"
        "            new = replace(new, name=old.name or item.name)\n"
        "            if new.name == old.name:\n"
        "                new = replace(new, origin=old.origin)\n"
        "        pool.append(new)\n"
        "        replaced.append(old)\n"
        "    return Zones(tuple(kinds[True]), tuple(kinds[False])), replaced\n"
        "\n"
        "\n"
        "def measure(\n"
        "    package: Any, master: str, unreadable: dict[str, str] | None = None\n"
        ") -> dict[str, alignment_zones.Extent]:\n"
        '    """Return the vertical extent of each of ``GLYPHS`` in ``master``; '
        "reads only.\n"
        "\n"
        "    The extent comes from the outline nodes, not from FontLab's cached\n"
        "    ``boundingBox``, which can be stale after a node move (fl#8575). A "
        "glyph\n"
        "    whose outline cannot be read gets ``None``; its reason goes into\n"
        "    ``unreadable`` (glyph name to message) when that dict is given.\n"
        '    """\n'
        "    found = {}\n"
        "    for name in GLYPHS:\n"
        "        glyph = package.findName(name)\n"
        '        absent = glyph is None or getattr(glyph, "isNull", False)\n'
        "        layer = None if absent else glyph.findLayer(master)\n"
        "        if layer is None or layer.isNull:\n"
        "            found[name] = None\n"
        "            continue\n"
        "        try:\n"
        "            span = outline_extent.vertical_extent(layer)\n"
        "        except ValueError as error:\n"
        "            found[name] = None\n"
        "            if unreadable is not None:\n"
        "                unreadable[name] = str(error)\n"
        "            continue\n"
        "        found[name] = None if span is None else "
        "alignment_zones.extent(span[0], span[1] - span[0])\n"
        "    return found\n"
        "\n"
        "\n"
        "def stage(editor: Any, master: str, zones: Zones) -> Any:\n"
        '    """Return ``editor`` with ``zones`` staged for ``master``."""\n'
        "    return editor.stage(master, zone_rows.rows(zones), "
        "origins=zone_rows.origins(zones))\n"
        "\n"
        "\n"
        "def preview_row(master: str, item: Suggestion, old: Zone | None) -> "
        "list:\n"
        '    """Return one table row: master, zone, position, signed width and '
        'the replaced zone."""\n'
        '    width = f"+{item.width}" if item.top else f"-{item.width}"\n'
        "    if old is None:\n"
        '        return [master, item.name, item.position, width, "nothing: '
        'added"]\n'
        '    label = old.name or "no name"\n'
        '    return [master, item.name, item.position, width, f"{label} at '
        '{round(old.position)}, width {round(old.width)}"]\n',
    ),
    "Italic Angle": (
        "Scripts/Masters/Italic Angle.py",
        "c886ced09f78812bb00b330840870ed5f6285b6ad5ce403f7a789bec1d4ced30",
        (),
        "",
    ),
    "Alignment Zones": (
        "Scripts/Metrics/Alignment Zones.py",
        "8508a52f2e11a7fac5fcf0fd43be2ef5802c45c40f8dbeecb4b8a865c10fb746",
        (),
        "",
    ),
    "Vertical Metrics Diagram": (
        "Scripts/Metrics/Vertical Metrics Diagram.py",
        "a8f0ed78a12db894982c7b8127a5455913d65a0aacfc79743f931064777b2035",
        (
            "Frame",
            "frame",
            "line_start",
            "read_metrics",
            "outline",
            "collect",
            "Diagram",
        ),
        "@dataclass(frozen=True)\n"
        "class Frame:\n"
        '    """Map font units to widget pixels. y grows down in the widget."""\n'
        "\n"
        "    left: float  # px: x of the first column.\n"
        "    column: float  # px: width of one master column.\n"
        "    scale: float  # px per unit.\n"
        "    baseline: float  # px: y of the baseline.\n"
        "\n"
        "    def x(self, index: int, units: float) -> float:\n"
        '        """Pixel x of a unit offset inside column ``index``."""\n'
        "        return self.left + index * self.column + units * self.scale\n"
        "\n"
        "    def y(self, units: float) -> float:\n"
        '        """Pixel y of a height in units."""\n'
        "        return self.baseline - units * self.scale\n"
        "\n"
        "\n"
        "def frame(\n"
        "    width: float, height: float, metrics: list[dict[str, float]], "
        "sample_width: float\n"
        ") -> Frame:\n"
        '    """Fit all masters\' metrics and the widest sample line into the widget.\n'
        "\n"
        "    The scale is the smaller of the height fit (all lines, the baseline and\n"
        "    the margins) and the width fit (``FILL`` of a column for the widest "
        "line).\n"
        "    Vertical slack is split above and below.\n"
        '    """\n'
        "    top = max(max(values.values()) for values in metrics) + TOP_MARGIN\n"
        "    bottom = min(0, *(min(values.values()) for values in metrics)) - "
        "BOTTOM_MARGIN\n"
        "    column = (width - LABEL_WIDTH - RIGHT_PAD) / len(metrics)\n"
        "    room = height - HEAD - FOOT\n"
        "    scale = min(room / (top - bottom), column * FILL / max(sample_width, 1))\n"
        "    baseline = HEAD + max(room - (top - bottom) * scale, 0) / 2 + top * "
        "scale\n"
        "    return Frame(LABEL_WIDTH, column, scale, baseline)\n"
        "\n"
        "\n"
        "def line_start(area: Frame, line_width: float) -> float:\n"
        '    """Unit offset that centres a sample line of ``line_width`` units in a '
        'column."""\n'
        "    return (area.column / area.scale - line_width) / 2\n"
        "\n"
        "\n"
        "def read_metrics(package: Any, masters: list[str]) -> dict[str, dict[str, "
        "float]]:\n"
        '    """{master: {attribute: value}} from FontMetrics; never switches the '
        'master."""\n'
        "    found = {}\n"
        "    for master in masters:\n"
        "        values = ap.fontlab.FontMetrics(package, master)\n"
        "        found[master] = {key: float(getattr(values, key)) for _, key in "
        "FIELDS}\n"
        "    return found\n"
        "\n"
        "\n"
        "def outline(layer: Any) -> Any:\n"
        '    """The layer outline as one QPainterPath in font units; read in '
        'place."""\n'
        "    path = QtGui.QPainterPath()\n"
        "    path.setFillRule(QtCore.Qt.WindingFill)\n"
        "    for shape in layer.shapes:\n"
        "        part = QtGui.QPainterPath()\n"
        "        for contour in shape.getContours():\n"
        "            part.addPath(contour.path())\n"
        "        path.addPath(shape.transform.map(part))\n"
        "    return path\n"
        "\n"
        "\n"
        "def collect(\n"
        "    package: Any, masters: list[str]\n"
        ") -> tuple[dict[str, list[tuple[str, Any, float]]], float, list[str]]:\n"
        '    """Read the sample glyphs: ({master: [(name, path, advance)]}, widest '
        'line, notes)."""\n'
        "    samples: dict[str, list[tuple[str, Any, float]]] = {m: [] for m in "
        "masters}\n"
        "    notes: list[str] = []\n"
        "    for name in SAMPLE:\n"
        "        glyph = package.findName(name)\n"
        "        if glyph is None or glyph.isNull:\n"
        '            notes.append(f"{name}: not in this font")\n'
        "            continue\n"
        "        for master in masters:\n"
        "            layer = glyph.findLayer(master)\n"
        "            if layer is None or layer.isNull:\n"
        '                notes.append(f"{name}: no layer in {master}")\n'
        "                continue\n"
        "            samples[master].append((name, outline(layer), "
        "float(layer.advanceWidth)))\n"
        "    widest = max((sum(a for _, _, a in line) for line in samples.values()), "
        "default=0)\n"
        "    return samples, widest, notes\n"
        "\n"
        "\n"
        "class Diagram(QtGui.QWidget):\n"
        '    """One column per master: sample outlines plus labelled metric lines."""\n'
        "\n"
        "    def __init__(self, owner: Any) -> None:\n"
        '        """Keep the owner panel, which holds the data to draw."""\n'
        "        QtGui.QWidget.__init__(self)\n"
        "        self.owner = owner\n"
        '        self.paint_error = ""\n'
        "        self.setMinimumSize(560, 260)\n"
        "\n"
        "    def paintEvent(self, event: Any) -> None:\n"
        '        """Draw. An error is kept, never raised; the painter always ends."""\n'
        "        painter = QtGui.QPainter(self)\n"
        "        try:\n"
        "            self.draw(painter, self.width, self.height)\n"
        '            self.paint_error = ""\n'
        "        except Exception as error:  # noqa: BLE001 - an error escaping paint "
        "can crash FontLab\n"
        "            self.paint_error = repr(error)\n"
        "        finally:\n"
        "            painter.end()\n"
        "\n"
        "    def draw(self, painter: Any, width: float, height: float) -> None:\n"
        '        """Paint the background, then every master column."""\n'
        "        owner = self.owner\n"
        "        palette = self.palette\n"
        "        painter.fillRect(\n"
        "            QtCore.QRectF(0, 0, width, height), "
        "palette.color(QtGui.QPalette.Base)\n"
        "        )\n"
        "        masters = [m for m in owner.masters if m in owner.metrics]\n"
        "        if not masters:\n"
        "            painter.setPen(QtGui.QColor(metrics_panel.muted(self)))\n"
        "            painter.drawText(\n"
        "                QtCore.QRectF(0, 0, width, height),\n"
        "                int(QtCore.Qt.AlignCenter),\n"
        '                "No metrics to show.",\n'
        "            )\n"
        "            return\n"
        "        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)\n"
        "        area = frame(\n"
        "            width, height, [owner.metrics[m] for m in masters], "
        "owner.sample_width\n"
        "        )\n"
        "        ink = QtGui.QColor(palette.color(QtGui.QPalette.WindowText))\n"
        "        guide = QtGui.QColor(palette.color(QtGui.QPalette.Mid))\n"
        "        small = painter.font()\n"
        "        small.setPointSizeF(max(small.pointSizeF() * 0.85, 8))\n"
        "        painter.setFont(small)\n"
        "        for index, master in enumerate(masters):\n"
        "            self.draw_column(painter, area, index, master, ink, guide)\n"
        "\n"
        "    def draw_column(\n"
        "        self, painter: Any, area: Frame, index: int, master: str, ink: Any, "
        "guide: Any\n"
        "    ) -> None:\n"
        '        """Master name, metric lines, the sample outlines; line names in '
        'column 0."""\n'
        "        values = self.owner.metrics[master]\n"
        "        left = area.x(index, 0)\n"
        "        painter.setPen(ink)\n"
        "        painter.drawText(\n"
        "            QtCore.QRectF(left, 0, area.column, HEAD),\n"
        "            int(QtCore.Qt.AlignCenter),\n"
        "            master,\n"
        "        )\n"
        '        lines = [("Baseline", 0.0)] + [(label, values[key]) for label, key in '
        "FIELDS]\n"
        "        painter.setPen(QtGui.QPen(QtGui.QBrush(guide), 1.0))\n"
        "        for _, units in lines:\n"
        "            painter.drawLine(\n"
        "                QtCore.QPointF(left + 6, area.y(units)),\n"
        "                QtCore.QPointF(left + area.column - 6, area.y(units)),\n"
        "            )\n"
        "        if index == 0:\n"
        "            self.draw_labels(painter, [(area.y(u), label) for label, u in "
        "lines])\n"
        "        line = self.owner.samples.get(master, [])\n"
        "        pen = line_start(area, sum(advance for _, _, advance in line))\n"
        "        painter.setPen(QtCore.Qt.NoPen)\n"
        "        painter.setBrush(QtGui.QBrush(ink))\n"
        "        for _, path, advance in line:\n"
        "            painter.save()\n"
        "            painter.translate(area.x(index, pen), area.baseline)\n"
        "            painter.scale(area.scale, -area.scale)\n"
        "            painter.drawPath(path)\n"
        "            painter.restore()\n"
        "            pen += advance\n"
        "\n"
        "    def draw_labels(self, painter: Any, labels: list[tuple[float, str]]) -> "
        "None:\n"
        '        """Line names right-aligned in the margin, pushed apart when lines '
        'are close."""\n'
        "        painter.setPen(QtGui.QColor(metrics_panel.muted(self)))\n"
        "        last = None\n"
        "        for y, label in sorted(labels):\n"
        "            if last is not None and y < last + LABEL_GAP:\n"
        "                y = last + LABEL_GAP\n"
        "            painter.drawText(\n"
        "                QtCore.QRectF(0, y - 9, LABEL_WIDTH - 6, 18),\n"
        "                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),\n"
        "                label,\n"
        "            )\n"
        "            last = y\n",
    ),
    "Nodes Near Zones": (
        "Scripts/Reports/Nodes Near Zones.py",
        "34a607b4ae608b007dcfea051eae1c4e3d6a749e413bf7601fc4cafbd399d69b",
        ("master_metrics", "on_curve_points", "near_misses", "scan"),
        "def master_metrics(package: Any, master: Any) -> Any:\n"
        '    """[(label, y)] vertical metrics of one master."""\n'
        "    m = fontlab.FontMetrics(package, master)\n"
        "    return [\n"
        '        ("baseline", 0.0),\n'
        '        ("x-height", m.xHeight),\n'
        '        ("cap height", m.capsHeight),\n'
        '        ("ascender", m.ascender),\n'
        '        ("descender", m.descender),\n'
        "    ]\n"
        "\n"
        "\n"
        "def on_curve_points(layer: Any) -> Any:\n"
        '    """[(x, y)] of the layer\'s own on-curve nodes with each shape\'s transform '
        'applied."""\n'
        "    points = []\n"
        "    for shape in layer.shapes:\n"
        "        if shape.shapeData is not None and shape.shapeData.componentGlyph:\n"
        "            continue\n"
        "        transform = shape.transform\n"
        "        for contour in shape.getContours():\n"
        "            for node in contour.nodes():\n"
        "                if node.isOn():\n"
        "                    p = transform.map(QtCore.QPointF(node.x, node.y))\n"
        "                    points.append((p.x(), p.y()))\n"
        "    return points\n"
        "\n"
        "\n"
        "def near_misses(points: Any, metrics: Any, tolerance: Any) -> Any:\n"
        '    """[(label, metric y, node x, node y)] for points with 0 < |y - metric| <= '
        'tolerance."""\n'
        "    out = []\n"
        "    for x, y in points:\n"
        "        for label, value in metrics:\n"
        "            delta = y - value\n"
        "            if 0 < abs(delta) <= tolerance:\n"
        "                out.append((label, value, x, y))\n"
        "    return out\n"
        "\n"
        "\n"
        "def scan(package: Any, names: Any, tolerance: Any) -> Any:\n"
        '    """[(glyph, master, metric label, metric y, node x, node y)]."""\n'
        "    masters = list(package.masters)\n"
        "    metrics = {m: master_metrics(package, m) for m in masters}\n"
        "    rows = []\n"
        "    for name in names:\n"
        "        glyph = package.findName(name)\n"
        "        if glyph is None:\n"
        "            continue\n"
        "        for master in masters:\n"
        "            layer = glyph.findLayer(master)\n"
        "            if layer is None:\n"
        "                continue\n"
        "            rows.extend(\n"
        "                (name, master, *hit)\n"
        "                for hit in near_misses(\n"
        "                    on_curve_points(layer), metrics[master], tolerance\n"
        "                )\n"
        "            )\n"
        "    return rows\n",
    ),
    "Vertical Metrics Reporter": (
        "Scripts/Reports/Vertical Metrics Reporter.py",
        "19cb6ceb2b119456ddf2b30ab7666ed473b4da37d67062cf7a174fa1cc308298",
        (),
        "",
    ),
}
