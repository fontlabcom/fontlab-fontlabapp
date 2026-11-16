# this_file: tests/_mark_attachment_originals.py
"""The Scriptmix scripts this app absorbs: file hashes and verbatim pure functions and classes.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show origin/main:<path>``), not retyped.
Each entry is ``(path, sha256 of the whole file, names, source of those definitions)``; the parity tests
compare the ported bodies with these (AST equality). Scripts with no pure function (thin launchers or
dialog-only code) have empty names; their behaviour is covered by tests of the reused backend.
"""

ORIGINALS = {
    "Mark Attachment Preview": (
        "Scripts/Anchors/Mark Attachment Preview.py",
        "a42f01c194b451765ee990eab8628836e15a350e5f602ee70d875c3ca4228185",
        (),
        "",
    ),
    "Align By Anchor": (
        "Scripts/Components/Align By Anchor.py",
        "db5bfc9568c585473b2508e0f46e91d123ad7f66b2ab6228e9ac180045e8f4ab",
        ("anchor_points", "base_layer", "pairs", "align_changes", "families"),
        "def anchor_points(layer: Any | None) -> dict[str, tuple[float, float]]:\n"
        '    """{name: (x, y)} of the layer. Duplicate names: the first one wins."""\n'
        "    found: dict[str, tuple[float, float]] = {}\n"
        "    for pin in layer.anchors if layer is not None else ():\n"
        "        found.setdefault(pin.name, (float(pin.point.x()), float(pin.point.y())))\n"
        "    return found\n"
        "\n"
        "\n"
        "def base_layer(package: Any, shape: Any, master: str) -> Any | None:\n"
        '    """The layer that a component shows: its base glyph on this master."""\n'
        "    glyph = package.findName(component_writer.base_of(shape))\n"
        "    if glyph is None:\n"
        "        return None\n"
        "    return component_writer.layer_of(glyph, shape.shapeData.componentLayer or master)\n"
        "\n"
        "\n"
        "def pairs(base: dict[str, tuple[float, float]], mark: dict) -> list[str]:\n"
        '    """Anchor names X with X on the base and _X on the mark, in base order."""\n'
        '    return [n for n in base if not n.startswith("_") and "_" + n in mark]\n'
        "\n"
        "\n"
        "def align_changes(\n"
        "    package: Any, layer: Any, master: str, wanted: str | None\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per mark component: anchor pair, current and new offset.\n'
        "\n"
        "    `wanted` None takes the first shared pair. A row without `edit` is shown\n"
        "    only: no pair, a scaled component, or a mark that already sits right.\n"
        '    """\n'
        "    shapes = component_writer.components(layer)\n"
        "    if len(shapes) < 2:\n"
        "        return []\n"
        "    first = shapes[0]\n"
        "    base = anchor_points(base_layer(package, first, master))\n"
        "    bx, by = component_writer.offset(first)\n"
        "    rows: list[component_writer.Change] = []\n"
        "    for shape in shapes[1:]:\n"
        "        name, old = component_writer.base_of(shape), component_writer.offset(shape)\n"
        "        mark = anchor_points(base_layer(package, shape, master))\n"
        "        found = pairs(base, mark)\n"
        "        family = (found[0] if found else None) if wanted is None else wanted\n"
        "        if family not in found:\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        '                    name, component_writer.offset_text(old), "no matching anchors"\n'
        "                )\n"
        "            )\n"
        "            continue\n"
        "        if not component_writer.plain_move(shape) or not component_writer.plain_move(\n"
        "            first\n"
        "        ):\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        '                    name, component_writer.offset_text(old), "scaled or slanted, '
        'kept"\n'
        "                )\n"
        "            )\n"
        "            continue\n"
        '        (ax, ay), (mx, my) = base[family], mark["_" + family]\n'
        "        new = (\n"
        "            float(component_writer.half_up(bx + ax - mx)),\n"
        "            float(component_writer.half_up(by + ay - my)),\n"
        "        )\n"
        '        label = f"{name} @ {family}"\n'
        "        if all(\n"
        "            abs(new[axis] - old[axis]) < component_writer.EPSILON for axis in (0, 1)\n"
        "        ):\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        '                    label, component_writer.offset_text(old), "in place"\n'
        "                )\n"
        "            )\n"
        "        else:\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        "                    label,\n"
        "                    component_writer.offset_text(old),\n"
        "                    component_writer.offset_text(new),\n"
        "                    (shape.id, new),\n"
        "                )\n"
        "            )\n"
        "    return rows\n"
        "\n"
        "\n"
        "def families(package: Any, glyphs: Iterable[Any], master: str) -> list[str]:\n"
        '    """Anchor pairs any selected composite could use on `master`, in order."""\n'
        "    found: list[str] = []\n"
        "    for glyph in glyphs:\n"
        "        layer = component_writer.layer_of(glyph, master)\n"
        "        shapes = component_writer.components(layer) if layer is not None else []\n"
        "        if len(shapes) < 2:\n"
        "            continue\n"
        "        base = anchor_points(base_layer(package, shapes[0], master))\n"
        "        for shape in shapes[1:]:\n"
        "            mark = anchor_points(base_layer(package, shape, master))\n"
        "            found.extend(n for n in pairs(base, mark) if n not in found)\n"
        "    return found\n",
    ),
    "Auto Cursive Attachment Get Sample": (
        "Scripts/Anchors/Auto Cursive Attachment Get Sample.py",
        "8e2734d66f895b9ccba17cfbac0144b1b4b98cb443e1c03abaa5569903de285b",
        (
            "outline_rings",
            "vertical_spans",
            "measure_sample",
            "validate_profile",
            "sample_document",
            "save_document",
        ),
        "def outline_rings(layer: Any) -> Rings:\n"
        '    """Flatten transformed, closed outline shapes; keep contour '
        'winding and holes."""\n'
        "    rings: Rings = []\n"
        "    for shape in layer.shapes:\n"
        "        if (\n"
        "            shape.isComposite\n"
        "            or not shape.transform.isAffine()\n"
        "            or not shape.openedPath.isEmpty()\n"
        "        ):\n"
        '            raise ValueError("Use closed, decomposed outlines for '
        'cursive sampling.")\n'
        "        for polygon in "
        "shape.closedPath.toSubpathPolygons(shape.transform):\n"
        "            # PythonQt QPolygonF is neither iterable nor "
        "subscriptable (native probe).\n"
        "            points = (polygon.at(index) for index in "
        "range(polygon.size()))\n"
        "            ring = [(float(point.x()), float(point.y())) for point "
        "in points]\n"
        "            if len(ring) >= 3:\n"
        "                if ring[0] != ring[-1]:\n"
        "                    ring.append(ring[0])\n"
        "                if not all(math.isfinite(v) for point in ring for v "
        "in point):\n"
        '                    raise ValueError("Outline coordinates must be '
        'finite.")\n'
        "                rings.append(ring)\n"
        "    if not rings:\n"
        '        raise ValueError("No closed outline was found.")\n'
        "    return rings\n"
        "\n"
        "\n"
        "def vertical_spans(rings: Rings, x: float) -> list[tuple[float, "
        "float, float, float]]:\n"
        '    """Return filled vertical spans and their boundary angles using '
        'nonzero winding."""\n'
        "    hits: dict[float, list[tuple[int, float]]] = {}\n"
        "    for ring in rings:\n"
        "        for (ax, ay), (bx, by) in pairwise(ring):\n"
        "            if min(ax, bx) <= x < max(ax, bx):\n"
        "                y = ay + (x - ax) * (by - ay) / (bx - ax)\n"
        "                tangent = (\n"
        "                    math.atan2(by - ay, bx - ax) + math.pi / 2\n"
        "                ) % math.pi - math.pi / 2\n"
        "                hits.setdefault(y, []).append((1 if bx > ax else "
        "-1, tangent))\n"
        "    spans = []\n"
        "    winding = 0\n"
        "    lower, lower_angle = 0.0, 0.0\n"
        "    for y, values in sorted(hits.items()):\n"
        "        previous = winding\n"
        "        winding += sum(direction for direction, _ in values)\n"
        "        if previous == 0 and winding != 0:\n"
        "            lower, lower_angle = y, values[0][1]\n"
        "        if previous != 0 and winding == 0 and y > lower:\n"
        "            spans.append((lower, y, lower_angle, values[0][1]))\n"
        "    return spans\n"
        "\n"
        "\n"
        "def measure_sample(rings: Rings, points: list[Point]) -> dict[str, "
        "float]:\n"
        '    """Average thickness fractions and boundary tangents around '
        'entry/exit pins."""\n'
        "    if not points:\n"
        '        raise ValueError("Create an entry or exit anchor inside the '
        'outline first.")\n'
        "    samples = []\n"
        "    for x, y in points:\n"
        "        spans = [span for span in vertical_spans(rings, x) if "
        "span[0] <= y <= span[1]]\n"
        "        if not spans:\n"
        '            raise ValueError("Every sample anchor must lie inside '
        'closed ink.")\n'
        "        low, high, low_angle, high_angle = min(\n"
        "            spans, key=lambda span: span[1] - span[0]\n"
        "        )\n"
        "        samples.append((y - low, high - y, low_angle, high_angle))\n"
        "    count = len(samples)\n"
        "    values = [sum(sample[i] for sample in samples) / count for i in "
        "range(2)]\n"
        "    for i in (2, 3):\n"
        "        values.append(\n"
        "            math.atan2(\n"
        "                sum(math.sin(2 * s[i]) for s in samples),\n"
        "                sum(math.cos(2 * s[i]) for s in samples),\n"
        "            )\n"
        "            / 2\n"
        "        )\n"
        '    return dict(zip(("below", "above", "lower_angle", '
        '"upper_angle"), values))\n'
        "\n"
        "\n"
        "def validate_profile(data: Any) -> dict[str, float]:\n"
        '    """Require a finite, nonnegative thickness profile and two '
        'tangent angles."""\n'
        '    fields = ("below", "above", "lower_angle", "upper_angle")\n'
        "    try:\n"
        "        profile = {key: float(data[key]) for key in fields}\n"
        "    except (KeyError, TypeError, ValueError, OverflowError) as "
        "error:\n"
        '        raise ValueError("Sample needs four numeric profile '
        'values.") from error\n'
        "    if not all(math.isfinite(value) for value in "
        "profile.values()):\n"
        '        raise ValueError("Sample values must be finite.")\n'
        "    if (\n"
        '        min(profile["below"], profile["above"]) < 0\n'
        '        or profile["below"] + profile["above"] <= 0\n'
        "    ):\n"
        '        raise ValueError("Sample must have positive ink '
        'thickness.")\n'
        "    return profile\n"
        "\n"
        "\n"
        "def sample_document(layer: Any, master: str) -> dict[str, Any]:\n"
        '    """Capture the two named connection pins and package the '
        'portable profile."""\n'
        "    import fly.ap.anchors.writer as anchor_writer  # noqa: PLR0402 "
        "- Fly submodule import avoids native attribute lookup\n"
        "\n"
        '    pins = [pin for pin in layer.anchors if pin.name in ("entry", '
        '"exit")]\n'
        "    if len({pin.name for pin in pins}) != len(pins):\n"
        '        raise ValueError("Entry and exit names must be unique.")\n'
        "    profile = measure_sample(\n"
        "        outline_rings(layer), [anchor_writer.raw_point(pin) for pin "
        "in pins]\n"
        "    )\n"
        "    return {\n"
        '        "format": "fontlab-cursive-sample-1",\n'
        '        "master": master,\n'
        '        "profile": validate_profile(profile),\n'
        "    }\n"
        "\n"
        "\n"
        "def save_document(path: str, document: dict[str, Any]) -> None:\n"
        '    """Write a new UTF-8 file; leave any existing file '
        'untouched."""\n'
        "    try:\n"
        '        with open(path, "x", encoding="utf-8", newline="\\n") as '
        "stream:\n"
        "            json.dump(document, stream, ensure_ascii=True, "
        "indent=2, allow_nan=False)\n"
        '            stream.write("\\n")\n'
        "    except FileExistsError as error:\n"
        "        raise ValueError(\n"
        '            "Choose a new file name; existing sample files stay '
        'unchanged."\n'
        "        ) from error\n",
    ),
    "Auto Cursive Attachment Add Anchors": (
        "Scripts/Anchors/Auto Cursive Attachment Add Anchors.py",
        "ba86abe9be3f263c8087a14911e89c35a0e8a97334b18e15b7b8807cbbbd2229",
        (
            "outline_rings",
            "vertical_spans",
            "measure_sample",
            "validate_profile",
            "needed_connections",
            "choose_attachment",
            "read_sample",
            "cursive_changes",
        ),
        "def outline_rings(layer: Any) -> Rings:\n"
        '    """Flatten transformed, closed outline shapes; keep contour '
        'winding and holes."""\n'
        "    rings: Rings = []\n"
        "    for shape in layer.shapes:\n"
        "        if (\n"
        "            shape.isComposite\n"
        "            or not shape.transform.isAffine()\n"
        "            or not shape.openedPath.isEmpty()\n"
        "        ):\n"
        '            raise ValueError("Use closed, decomposed outlines for '
        'cursive sampling.")\n'
        "        for polygon in "
        "shape.closedPath.toSubpathPolygons(shape.transform):\n"
        "            # PythonQt QPolygonF is neither iterable nor "
        "subscriptable (native probe).\n"
        "            points = (polygon.at(index) for index in "
        "range(polygon.size()))\n"
        "            ring = [(float(point.x()), float(point.y())) for point "
        "in points]\n"
        "            if len(ring) >= 3:\n"
        "                if ring[0] != ring[-1]:\n"
        "                    ring.append(ring[0])\n"
        "                if not all(math.isfinite(v) for point in ring for "
        "v in point):\n"
        '                    raise ValueError("Outline coordinates must be '
        'finite.")\n'
        "                rings.append(ring)\n"
        "    if not rings:\n"
        '        raise ValueError("No closed outline was found.")\n'
        "    return rings\n"
        "\n"
        "\n"
        "def vertical_spans(rings: Rings, x: float) -> list[tuple[float, "
        "float, float, float]]:\n"
        '    """Return filled vertical spans and their boundary angles '
        'using nonzero winding."""\n'
        "    hits: dict[float, list[tuple[int, float]]] = {}\n"
        "    for ring in rings:\n"
        "        for (ax, ay), (bx, by) in pairwise(ring):\n"
        "            if min(ax, bx) <= x < max(ax, bx):\n"
        "                y = ay + (x - ax) * (by - ay) / (bx - ax)\n"
        "                tangent = (\n"
        "                    math.atan2(by - ay, bx - ax) + math.pi / 2\n"
        "                ) % math.pi - math.pi / 2\n"
        "                hits.setdefault(y, []).append((1 if bx > ax else "
        "-1, tangent))\n"
        "    spans = []\n"
        "    winding = 0\n"
        "    lower, lower_angle = 0.0, 0.0\n"
        "    for y, values in sorted(hits.items()):\n"
        "        previous = winding\n"
        "        winding += sum(direction for direction, _ in values)\n"
        "        if previous == 0 and winding != 0:\n"
        "            lower, lower_angle = y, values[0][1]\n"
        "        if previous != 0 and winding == 0 and y > lower:\n"
        "            spans.append((lower, y, lower_angle, values[0][1]))\n"
        "    return spans\n"
        "\n"
        "\n"
        "def measure_sample(rings: Rings, points: list[Point]) -> dict[str, "
        "float]:\n"
        '    """Average thickness fractions and boundary tangents around '
        'entry/exit pins."""\n'
        "    if not points:\n"
        '        raise ValueError("Create an entry or exit anchor inside '
        'the outline first.")\n'
        "    samples = []\n"
        "    for x, y in points:\n"
        "        spans = [span for span in vertical_spans(rings, x) if "
        "span[0] <= y <= span[1]]\n"
        "        if not spans:\n"
        '            raise ValueError("Every sample anchor must lie inside '
        'closed ink.")\n'
        "        low, high, low_angle, high_angle = min(\n"
        "            spans, key=lambda span: span[1] - span[0]\n"
        "        )\n"
        "        samples.append((y - low, high - y, low_angle, "
        "high_angle))\n"
        "    count = len(samples)\n"
        "    values = [sum(sample[i] for sample in samples) / count for i "
        "in range(2)]\n"
        "    for i in (2, 3):\n"
        "        values.append(\n"
        "            math.atan2(\n"
        "                sum(math.sin(2 * s[i]) for s in samples),\n"
        "                sum(math.cos(2 * s[i]) for s in samples),\n"
        "            )\n"
        "            / 2\n"
        "        )\n"
        '    return dict(zip(("below", "above", "lower_angle", '
        '"upper_angle"), values))\n'
        "\n"
        "\n"
        "def validate_profile(data: Any) -> dict[str, float]:\n"
        '    """Require a finite, nonnegative thickness profile and two '
        'tangent angles."""\n'
        '    fields = ("below", "above", "lower_angle", "upper_angle")\n'
        "    try:\n"
        "        profile = {key: float(data[key]) for key in fields}\n"
        "    except (KeyError, TypeError, ValueError, OverflowError) as "
        "error:\n"
        '        raise ValueError("Sample needs four numeric profile '
        'values.") from error\n'
        "    if not all(math.isfinite(value) for value in "
        "profile.values()):\n"
        '        raise ValueError("Sample values must be finite.")\n'
        "    if (\n"
        '        min(profile["below"], profile["above"]) < 0\n'
        '        or profile["below"] + profile["above"] <= 0\n'
        "    ):\n"
        '        raise ValueError("Sample must have positive ink '
        'thickness.")\n'
        "    return profile\n"
        "\n"
        "\n"
        "def needed_connections(name: str) -> list[str]:\n"
        '    """Retain the source tool\'s form-name routing without Unicode '
        'guesses."""\n'
        "    lower = name.lower()\n"
        '    return (["exit"] if "ini" in lower or "med" in lower else []) '
        "+ (\n"
        '        ["entry"] if "fin" in lower or "med" in lower else []\n'
        "    )\n"
        "\n"
        "\n"
        "def choose_attachment(\n"
        "    rings: Rings, profile: dict[str, float], candidates: "
        "list[float]\n"
        ") -> Point:\n"
        '    """Pick the first minimum of thickness and undirected '
        'boundary-angle errors."""\n'
        "    profile = validate_profile(profile)\n"
        '    thickness = profile["below"] + profile["above"]\n'
        "    best: tuple[float, Point] | None = None\n"
        "    deadline = monotonic() + 1.5\n"
        "    for x in candidates:\n"
        "        if monotonic() >= deadline:\n"
        '            raise TimeoutError("Cursive fitting exceeded its time '
        'budget.")\n'
        "        for low, high, lower_angle, upper_angle in "
        "vertical_spans(rings, x):\n"
        "            distance = high - low\n"
        "            if not 10 <= distance <= 500:\n"
        "                continue\n"
        "            errors = [\n"
        "                (actual - profile[key] + math.pi / 2) % math.pi - "
        "math.pi / 2\n"
        "                for actual, key in (\n"
        '                    (lower_angle, "lower_angle"),\n'
        '                    (upper_angle, "upper_angle"),\n'
        "                )\n"
        "            ]\n"
        "            score = (distance - thickness) ** 2 + 25 * sum(\n"
        "                error * error for error in errors\n"
        "            )\n"
        '            point = (x, low + distance * profile["below"] / '
        "thickness)\n"
        "            if best is None or score < best[0]:\n"
        "                best = (score, point)\n"
        "    if best is None:\n"
        '        raise ValueError("No suitable 10–500 unit ink span near '
        'the connection edge.")\n'
        "    return best[1]\n"
        "\n"
        "\n"
        "def read_sample(\n"
        "    path: str, master: str, conversions: list[str] | None = None\n"
        ") -> dict[str, float]:\n"
        '    """Load a portable profile; reject text loss, wrong format and '
        'master mismatch."""\n'
        "    if not path:\n"
        '        raise ValueError("Choose a sample file.")\n'
        "    try:\n"
        "        raw = Path(path).read_bytes()\n"
        "        if conversions is not None:\n"
        '            if raw.startswith(b"\\xef\\xbb\\xbf"):\n'
        '                conversions.append("BOM removed")\n'
        '            if b"\\r" in raw:\n'
        '                conversions.append("CR/CRLF read as LF")\n'
        "        with io.TextIOWrapper(\n"
        '            io.BytesIO(raw), encoding="utf-8-sig", newline=None\n'
        "        ) as stream:\n"
        "            text = stream.read()\n"
        '        if any(char in text for char in ("\\0", "\\u00a0", '
        '"\\u2028", "\\u2029")):\n'
        '            raise ValueError("Sample contains text that FontLab '
        'cannot preserve.")\n'
        "        document = json.loads(text)\n"
        "        if (\n"
        "            not isinstance(document, dict)\n"
        '            or document.get("format") != '
        '"fontlab-cursive-sample-1"\n'
        "        ):\n"
        '            raise ValueError("Choose a FontLab cursive sample JSON '
        'file.")\n'
        '        if document.get("master") != master:\n'
        '            raise ValueError("The sample master name must match '
        'the current master.")\n'
        '        return validate_profile(document.get("profile"))\n'
        "    except (OSError, UnicodeError, json.JSONDecodeError) as "
        "error:\n"
        '        raise ValueError(f"Cannot read sample: {error}") from '
        "error\n"
        "\n"
        "\n"
        "def cursive_changes(glyph: Any, layer: Any, profile: dict[str, "
        "float]) -> list[Any]:\n"
        '    """Plan missing connections only, with deterministic near-edge '
        'searches."""\n'
        "    import fly.ap.anchors.writer as anchor_writer  # noqa: PLR0402 "
        "- Fly submodule import avoids native attribute lookup\n"
        "\n"
        "    existing = {pin.name for pin in layer.anchors}\n"
        "    wanted = [name for name in needed_connections(glyph.name) if "
        "name not in existing]\n"
        "    if not wanted:\n"
        "        return []\n"
        "    rings = outline_rings(layer)\n"
        "    xs = [point[0] for ring in rings for point in ring]\n"
        "    left, right = min(xs), max(xs)\n"
        "    changes = []\n"
        "    for name in wanted:\n"
        '        start = math.floor(left) if name == "exit" else '
        "math.ceil(right) - 1\n"
        '        step = 1 if name == "exit" else -1\n'
        "        candidates = [\n"
        "            start + step * i + 0.5\n"
        "            for i in range(200)\n"
        "            if left <= start + step * i + 0.5 < right\n"
        "        ]\n"
        "        point = choose_attachment(rings, profile, candidates)\n"
        "        target = tuple(anchor_writer.half_up(value) for value in "
        "point)\n"
        "        changes.append(\n"
        '            anchor_writer.Change(name, "missing", str(target), '
        '("set", name, target))\n'
        "        )\n"
        "    return changes\n",
    ),
}
