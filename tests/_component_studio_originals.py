# this_file: tests/_component_studio_originals.py
"""The Scriptmix scripts Component Studio absorbs: file hashes and verbatim pure functions and classes.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show origin/main:<path>``), not retyped.
Each entry is ``(path, sha256 of the whole file, names, source of those definitions)``; the parity tests
compare the ported bodies with these (AST equality). A script with no pure function (the Dump launcher)
has empty names; its behaviour is covered by tests of the reused backend.
"""

ORIGINALS = {
    "Build From Recipes": (
        "Scripts/Components/Build From Recipes.py",
        "27c15a82f0b2714ba8aee8ef66f1d0bb4f8c219f1a2c0dfe13ab43798e5a7479",
        ("Line", "Result", "parse", "data_tool", "build", "check_lines"),
        "@dataclass(frozen=True)\n"
        "class Line:\n"
        '    """One recipe line. `problem` set: the line cannot be built."""\n'
        "\n"
        "    number: int\n"
        "    target: str\n"
        "    recipe: str\n"
        '    problem: str = ""\n'
        "\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Result:\n"
        '    """Verdict for one target layer. `adds_layer`: the glyph lacks this layer."""\n'
        "\n"
        "    target: str\n"
        "    master: str\n"
        "    recipe: str\n"
        "    ok: bool\n"
        "    message: str\n"
        "    adds_layer: bool = False\n"
        "\n"
        "\n"
        "def parse(text: str) -> list[Line]:\n"
        '    """Non-empty lines as `Line` records. \'#\' starts a comment."""\n'
        "    lines: list[Line] = []\n"
        "    for number, raw in enumerate(text.splitlines(), 1):\n"
        "        unsafe = sorted({label for char, label in UNSAFE_TEXT.items() if char in raw})\n"
        '        line = raw.split("#", 1)[0].strip()\n'
        "        if unsafe:\n"
        '            lines.append(Line(number, line, "", f"remove the {\', \'.join(unsafe)}"))\n'
        "            continue\n"
        "        if not line:\n"
        "            continue\n"
        '        if "=" not in line:\n'
        '            lines.append(Line(number, line, "", "use: target = base + mark@anchor"))\n'
        "            continue\n"
        '        target, recipe = (part.strip() for part in line.split("=", 1))\n'
        '        recipe = ATTACH.sub(lambda m: f"@{m[1]}[_{m[1]}]", re.sub(r"\\s+", "", recipe))\n'
        '        problem = ""\n'
        "        if not target or not recipe:\n"
        '            problem = "empty target or recipe"\n'
        "        elif not GLYPH_NAME.match(target):\n"
        '            problem = f"{target} is not a valid glyph name"\n'
        '        lines.append(Line(number, target, "=" + recipe if recipe else "", problem))\n'
        "    return lines\n"
        "\n"
        "\n"
        "def data_tool(tool: str, **arguments: Any) -> Any:\n"
        '    """Call one of FontLab\'s own data tools in-process (fly.pr is native fontpr)."""\n'
        "    from fly import pr\n"
        "\n"
        "    return pr.call(tool, **arguments)\n"
        "\n"
        "\n"
        "def build(\n"
        "    package: Any,\n"
        "    line: Line,\n"
        "    master: str,\n"
        "    replace: bool,\n"
        "    dry_run: bool,\n"
        ") -> tuple[bool, str]:\n"
        '    """Build (or only validate) one target layer. Returns (ok, message).\n'
        "\n"
        "    Never an auto layer: FontLab's builder notifies the glyph deeply, and an\n"
        "    auto layer there rebuilds every default-recipe auto layer in the font.\n"
        '    """\n'
        "    arguments = {\n"
        '        "font_id": scripting.font_id(package),  # fontpr finds fonts by fgId\n'
        '        "glyph_name": line.target,\n'
        '        "recipe": line.recipe,\n'
        '        "layer_name": master,\n'
        '        "replace": replace,\n'
        '        "auto_layer": False,\n'
        '        "dry_run": dry_run,\n'
        "    }\n"
        "    try:\n"
        '        result = data_tool("build_glyph", **arguments)\n'
        "    except Exception as error:  # noqa: BLE001 - FontLab's text goes to the table\n"
        "        return False, str(error).strip() or type(error).__name__\n"
        '    if not isinstance(result, dict) or result.get("status") not in {"ok", "validated"}:\n'
        "        if isinstance(result, dict):\n"
        '            return False, str(result.get("error") or result.get("message") or result)\n'
        "        return False, str(result)\n"
        '    parts = " + ".join(\n'
        '        str(c.get("glyph_name")) for c in result.get("resolved_components", [])\n'
        "    )\n"
        '    verb = "valid" if dry_run else ("created" if result.get("created") else "built")\n'
        '    return True, f"{verb}: {parts}"\n'
        "\n"
        "\n"
        "def check_lines(\n"
        "    package: Any,\n"
        "    lines: list[Line],\n"
        "    masters: list[str],\n"
        "    replace: bool,\n"
        "    facts: history.AutoFacts,\n"
        ") -> list[Result]:\n"
        '    """Dry-run every line on every master. Nothing in the font changes."""\n'
        "    results: list[Result] = []\n"
        "    for line in lines:\n"
        "        if line.problem:\n"
        '            results.append(Result(line.target, "", line.recipe, False, line.problem))\n'
        "            continue\n"
        "        glyph = package.findName(line.target)\n"
        '        why = history.refusal(facts, line.target, "geometry") if glyph else ""\n'
        "        if why:\n"
        '            results.append(Result(line.target, "", line.recipe, False, why))\n'
        "            continue\n"
        "        for index, master in enumerate(masters):\n"
        "            if glyph is None and index > 0:\n"
        '                note = f"new glyph: press Build again for {master}"\n'
        "                results.append(Result(line.target, master, line.recipe, True, note))\n"
        "                continue\n"
        "            ok, message = build(package, line, master, replace, dry_run=True)\n"
        "            adds = (\n"
        "                glyph is not None and component_writer.layer_of(glyph, master) is None\n"
        "            )\n"
        "            if adds and not ok and LAYER_MISSING in message:\n"
        '                ok, message = True, f"valid: adds layer {master} first"\n'
        "            results.append(Result(line.target, master, line.recipe, ok, message, adds))\n"
        "    return results\n",
    ),
    "Dump Component Recipes": (
        "Scripts/Components/Dump Component Recipes.py",
        "8e46590e3f3d2400156c54be82f4ef9b5855c1d2a3c92c4fb832bf5ce69d6bc5",
        (),
        "",
    ),
    "Replace Reference": (
        "Scripts/Components/Replace Reference.py",
        "917f4830be09b763e3f6adc4be813e5118d6e3e78c23ef7fb899b570c2091086",
        (
            "users_of",
            "matrix_of",
            "replace_changes",
            "replace_problem",
            "ReplaceEditor",
        ),
        "def users_of(facts: history.AutoFacts, name: str) -> set[str]:\n"
        '    """Every glyph that shows `name`, directly or through other components.\n'
        "\n"
        "    When the new base is among the users of the edited glyph, the edited glyph\n"
        "    would contain itself.\n"
        '    """\n'
        "    seen, todo = {name}, [name]\n"
        "    while todo:\n"
        "        for user in facts.users.get(todo.pop(), ()):\n"
        "            if user not in seen:\n"
        "                seen.add(user)\n"
        "                todo.append(user)\n"
        "    return seen - {name}\n"
        "\n"
        "\n"
        "def matrix_of(shape: Any) -> tuple[float, ...]:\n"
        '    """The six transform numbers, to prove that the placement did not move."""\n'
        "    m = shape.transform\n"
        "    return (m.m11(), m.m12(), m.m21(), m.m22(), m.dx(), m.dy())\n"
        "\n"
        "\n"
        "def replace_changes(\n"
        "    package: Any,\n"
        "    glyph: Any,\n"
        "    layer: Any,\n"
        "    master: str,\n"
        "    names: tuple[str, str],\n"
        "    facts: history.AutoFacts,\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per component of `old` on the layer, with its block reason if any."""\n'
        "    old, new = names\n"
        "    rows: list[component_writer.Change] = []\n"
        "    for shape in component_writer.components(layer):\n"
        "        if component_writer.base_of(shape) != old:\n"
        "            continue\n"
        "        where = component_writer.offset_text(component_writer.offset(shape))\n"
        "        problem = replace_problem(package, glyph, shape, master, new, facts)\n"
        "        if problem:\n"
        '            rows.append(component_writer.Change(old, where, "", problem=problem))\n'
        "        else:\n"
        "            rows.append(component_writer.Change(old, where, new, (shape.id, new)))\n"
        "    return rows\n"
        "\n"
        "\n"
        "def replace_problem(\n"
        "    package: Any,\n"
        "    glyph: Any,\n"
        "    shape: Any,\n"
        "    master: str,\n"
        "    new: str,\n"
        "    facts: history.AutoFacts,\n"
        ") -> str:\n"
        '    """Why `shape` cannot show `new`, or "".\n'
        "\n"
        "    The new base needs the layer the component reads: its own layer name, if\n"
        "    it names one, else the master.\n"
        '    """\n'
        "    wanted = shape.shapeData.componentLayer or master\n"
        "    target = package.findName(new)\n"
        "    if target is None or component_writer.layer_of(target, wanted) is None:\n"
        '        return f"{new} has no layer {wanted}"\n'
        "    if new == glyph.name or new in users_of(facts, glyph.name):\n"
        '        return f"{new} uses {glyph.name}: the component would show itself"\n'
        "    if int(shape.shapeData.referenceCount) > 1:\n"
        '        return "shared element data: change it in FontLab"\n'
        '    return ""\n'
        "\n"
        "\n"
        "class ReplaceEditor(component_writer.Editor):\n"
        '    """Set the base glyph name of each planned component in place."""\n'
        "\n"
        "    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:\n"
        "        steps = []\n"
        "        for shape_id, new in edits:\n"
        "            shape = layer.shapes[component_writer.shape_index(layer, shape_id)]\n"
        "            steps.append((shape, new, matrix_of(shape)))\n"
        "        return steps\n"
        "\n"
        "    def write(self, layer: Any, steps: list[Any]) -> None:\n"
        "        for shape, new, _ in steps:\n"
        "            shape.shapeData.componentGlyph = new\n"
        "            component_writer.refreshed(shape)\n"
        "\n"
        "    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:\n"
        "        missed: list[str] = []\n"
        "        for layer, steps in prepared:\n"
        "            for shape, new, matrix in steps:\n"
        "                now = matrix_of(shape)\n"
        "                moved = any(\n"
        "                    abs(a - b) >= component_writer.EPSILON\n"
        "                    for a, b in zip(now, matrix, strict=True)\n"
        "                )\n"
        "                if component_writer.base_of(shape) != new or moved:\n"
        '                    missed.append(f"{layer.name}/{new}")\n'
        "        return missed\n",
    ),
    "Decompose": (
        "Scripts/Components/Decompose.py",
        "c6d22abcc892e0c64f53d03cc44f777f45441fe13a5c7dd6a926c2ef5d55fb6d",
        ("decompose_changes",),
        "def decompose_changes(\n"
        "    package: Any, glyph: Any, layer: Any, master: str\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per component of the layer: its base and what it becomes."""\n'
        "    rows: list[component_writer.Change] = []\n"
        "    for shape in component_writer.components(layer):\n"
        "        why = component_writer.copy_problem(\n"
        "            package, (glyph.name, master), shape, master\n"
        "        )\n"
        "        if why:\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        '                    component_writer.base_of(shape), "", "", problem=why\n'
        "                )\n"
        "            )\n"
        "            continue\n"
        "        contours, inner = component_writer.part_counts(package, shape, master)\n"
        "        becomes = component_writer.parts_text(contours, inner)\n"
        "        if inner:\n"
        '            becomes += " (nested: press again)"\n'
        "        rows.append(\n"
        "            component_writer.Change(\n"
        '                component_writer.base_of(shape), "", becomes, shape.id\n'
        "            )\n"
        "        )\n"
        "    return rows\n",
    ),
    "Decompose Named Components": (
        "Scripts/Components/Decompose Named Components.py",
        "bc54acbfa9efc4c9001f61f3afd7ec906d1bdd8d8218e036a12102c1efdab84e",
        (
            "flatten_parts",
            "source_contours",
            "checked_parts",
            "NamedEditor",
            "make_plan",
        ),
        "def flatten_parts(shape: Any, depth: int = 0) -> list[Any]:\n"
        '    """Copy one subtree into detached outlines, in drawing order.\n'
        "\n"
        "    Use the public App eject helper at every level. Its native eject applies\n"
        "    placement, and its copy repair keeps flags and element metadata.\n"
        "    Bound recursion even when a component cache disagrees with the preview.\n"
        '    """\n'
        "    if depth >= component_writer.MAX_DEPTH:\n"
        '        raise ValueError("Components nest too deeply; component kept.")\n'
        "    result: list[Any] = []\n"
        "    for part in component_writer.eject(shape):\n"
        "        if part.isComponent:\n"
        "            result.extend(flatten_parts(part, depth + 1))\n"
        "        else:\n"
        "            result.append(part)\n"
        "    return result\n"
        "\n"
        "\n"
        "def source_contours(package: Any, shape: Any, master: str, depth: int = 0) -> int:\n"
        '    """Count expected contours from source layers, independently of copy caches."""\n'
        "    if depth >= component_writer.MAX_DEPTH:\n"
        '        raise ValueError("Components nest too deeply; component kept.")\n'
        "    base = package.findName(component_writer.base_of(shape))\n"
        "    layer_name = str(shape.shapeData.componentLayer) or master\n"
        "    layer = component_writer.layer_of(base, layer_name) if base is not None else None\n"
        "    if layer is None:\n"
        '        raise ValueError(f"Missing base layer {layer_name}.")\n'
        "    return sum(\n"
        "        source_contours(package, part, master, depth + 1)\n"
        "        if part.isComponent\n"
        "        else len(part.contours)\n"
        "        for part in layer.shapes\n"
        "    )\n"
        "\n"
        "\n"
        "def checked_parts(package: Any, shape: Any, master: str) -> list[Any]:\n"
        '    """Refuse detached copy loss before history can remove the occurrence."""\n'
        "    expected = source_contours(package, shape, master)\n"
        "    parts = flatten_parts(shape)\n"
        "    if sum(len(part.contours) for part in parts) != expected:\n"
        '        raise ValueError("Copied contour count differs from the source subtree.")\n'
        "    return parts\n"
        "\n"
        "\n"
        "class NamedEditor(component_writer.EjectEditor):\n"
        '    """Prepare full subtree copies; inherit retained removal and read-back."""\n'
        "\n"
        "    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:\n"
        '        """Prepare (original component, flattened parts, placed parts)."""\n'
        "        steps = []\n"
        "        for shape_id, parts in edits:\n"
        "            if parts is None:\n"
        '                raise ValueError("Prepare component copies on Apply first.")\n'
        "            shape = layer.shapes[component_writer.shape_index(layer, shape_id)]\n"
        "            if self.unlock:\n"
        "                for part in parts:\n"
        "                    part.contentLocked = False\n"
        "            steps.append((shape, parts, []))\n"
        "        return steps\n"
        "\n"
        "\n"
        "def make_plan(\n"
        "    package: Any,\n"
        "    glyphs: list[Any],\n"
        "    masters: list[str],\n"
        "    name: str,\n"
        "    facts: history.AutoFacts,\n"
        "    *,\n"
        "    copy: bool = False,\n"
        ") -> component_writer.Plan:\n"
        '    """Read counts for preview; copy only on Apply, before history opens."""\n'
        "    plan = component_writer.Plan()\n"
        '    refused = history.refusals(facts, [g.name for g in glyphs], "geometry")\n'
        "    for glyph in glyphs:\n"
        "        for master in masters:\n"
        '            label = f"{glyph.name} · {master}"\n'
        "            layer = component_writer.layer_of(glyph, master)\n"
        "            candidates = (\n"
        "                [\n"
        "                    s\n"
        "                    for s in component_writer.components(layer)\n"
        "                    if component_writer.base_of(s) == name\n"
        "                ]\n"
        "                if layer is not None\n"
        "                else []\n"
        "            )\n"
        "            if not candidates and (\n"
        "                layer is not None\n"
        "                or not any(\n"
        "                    component_writer.base_of(s) == name\n"
        "                    for other in glyph.layers\n"
        "                    for s in component_writer.components(other)\n"
        "                )\n"
        "            ):\n"
        "                continue\n"
        '            reason = refused.get(glyph.name, "")\n'
        "            if layer is None:\n"
        '                reason = "missing master layer"\n'
        "            elif (\n"
        "                layer.autoLayer\n"
        "                or layer.isLocked\n"
        "                or layer.isMaskLayer\n"
        "                or layer.isService\n"
        "            ):\n"
        '                reason = "automatic, locked or service layer"\n'
        "            if reason:\n"
        "                plan.rows.append(\n"
        '                    (label, component_writer.Change(name, "", f"kept: {reason}"))\n'
        "                )\n"
        "                plan.refused.append(label)\n"
        "                continue\n"
        "            edits = []\n"
        "            for shape in candidates:\n"
        "                reason = component_writer.copy_problem(\n"
        "                    package, (glyph.name, master), shape, master\n"
        "                )\n"
        "                parts = None\n"
        "                if not reason:\n"
        "                    try:\n"
        "                        if copy:\n"
        "                            parts = checked_parts(package, shape, master)\n"
        "                        else:\n"
        "                            source_contours(package, shape, master)\n"
        "                    except (ValueError, RuntimeError, TimeoutError) as error:\n"
        "                        reason = str(error)\n"
        "                row = component_writer.Change(\n"
        "                    name,\n"
        '                    "",\n'
        '                    f"kept: {reason}" if reason else "independent outlines",\n'
        "                    None if reason else (shape.id, parts),\n"
        "                )\n"
        "                plan.rows.append((label, row))\n"
        "                if not reason:\n"
        "                    edits.append((shape.id, parts))\n"
        "            if edits:\n"
        "                plan.work.append((glyph, layer, edits))\n"
        "    return plan\n",
    ),
    "Decompose Serif Components": (
        "Scripts/Components/Decompose Serif Components.py",
        "2b080c061236321280bbbbee21dee8a5cbcfafe4bc50861acc3f4a1d5c651bd2",
        ("changes",),
        "def changes(package: Any, glyph: Any, master: str, layer: Any) -> list[writer.Change]:\n"
        '    """Describe only Serif-prefixed components; block unsafe base copies."""\n'
        "    result = []\n"
        "    for part in writer.components(layer):\n"
        "        base = writer.base_of(part)\n"
        '        if not base.startswith("Serif"):\n'
        "            continue\n"
        "        problem = writer.copy_problem(package, (glyph.name, master), part, master)\n"
        "        result.append(\n"
        '            writer.Change(base, "component", "editable parts", part.id, problem=problem)\n'
        "        )\n"
        "    return result\n",
    ),
    "Copy Offsets Between Masters": (
        "Scripts/Components/Copy Offsets Between Masters.py",
        "ce9019d53270c6c8d070be4eb143ea0f5891dec824e07aa22a16eee2f3a56a20",
        ("offset_changes",),
        "def offset_changes(\n"
        "    source: Any, target: Any, scale: bool\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per component of the target: current and new offset.\n'
        "\n"
        "    Different component lists give one note row and no edit.\n"
        '    """\n'
        "    src, dst = component_writer.components(source), component_writer.components(target)\n"
        "    if not src:\n"
        "        return []\n"
        "    if [component_writer.base_of(s) for s in src] != [\n"
        "        component_writer.base_of(s) for s in dst\n"
        "    ]:\n"
        '        names = " + ".join(component_writer.base_of(s) for s in dst) or "none"\n'
        '        return [component_writer.Change(names, "", "different components, kept")]\n'
        "    ratio = 1.0\n"
        "    if scale and source.advanceWidth:\n"
        "        ratio = float(target.advanceWidth) / float(source.advanceWidth)\n"
        "    rows: list[component_writer.Change] = []\n"
        "    for old_shape, shape in zip(src, dst, strict=True):\n"
        "        dx, dy = component_writer.offset(old_shape)\n"
        "        new = (float(component_writer.half_up(dx * ratio)) if scale else dx, dy)\n"
        "        old = component_writer.offset(shape)\n"
        "        if all(\n"
        "            abs(new[axis] - old[axis]) < component_writer.EPSILON for axis in (0, 1)\n"
        "        ):\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        "                    component_writer.base_of(shape),\n"
        "                    component_writer.offset_text(old),\n"
        '                    "same",\n'
        "                )\n"
        "            )\n"
        "        else:\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        "                    component_writer.base_of(shape),\n"
        "                    component_writer.offset_text(old),\n"
        "                    component_writer.offset_text(new),\n"
        "                    (shape.id, new),\n"
        "                )\n"
        "            )\n"
        "    return rows\n",
    ),
    "Set Component Locations": (
        "Scripts/Components/Set Component Locations.py",
        "f33b1ce4628e23d326c3dcdeeb914097e994542de4119b0d4dedab5ab9fb5484",
        (
            "encode_location",
            "component_targets",
            "location_plan",
            "current_coordinates",
            "LocationEditor",
        ),
        "def encode_location(package: Any, values: dict[str, float]) -> str:\n"
        '    """Encode native # syntax in declared-axis order, within design bounds.\n'
        "\n"
        "    The native builder replaces # with : before decodeMasterPosition parses\n"
        "    comma-separated shortName=value pairs. Use design units, not user units.\n"
        '    """\n'
        "    axes = list(package.axes)\n"
        "    keys = [str(axis.shortName).lower() for axis in axes]\n"
        "    if (\n"
        "        not keys\n"
        "        or len(set(keys)) != len(keys)\n"
        "        or any(not key.isascii() or not key.isalnum() for key in keys)\n"
        "    ):\n"
        '        raise ValueError("Declare axes with unique short names in Font Info.")\n'
        "    if set(values) != set(keys):\n"
        '        raise ValueError("Set one coordinate for each declared font axis.")\n'
        "    pairs = []\n"
        "    for key, axis in zip(keys, axes, strict=True):\n"
        "        number = float(values[key])\n"
        "        if not math.isfinite(number) or not float(axis.designMin) <= number <= float(\n"
        "            axis.designMax\n"
        "        ):\n"
        "            raise ValueError(\n"
        '                f"{key}: choose a finite coordinate inside the design range."\n'
        "            )\n"
        "        text = str(int(number)) if number.is_integer() else repr(number)\n"
        '        pairs.append(f"{key}={text}")\n'
        '    return "#" + ",".join(pairs)\n'
        "\n"
        "\n"
        "def component_targets(\n"
        "    glyph: Any, layer: Any, selected_only: bool\n"
        ") -> list[tuple[Any, str]]:\n"
        '    """Resolve selection by position and base name; never substitute a sibling."""\n'
        "    if not selected_only:\n"
        "        source = layer if layer is not None else glyph.updateActiveLayer(False)\n"
        "        return (\n"
        "            [\n"
        '                (shape, "" if layer is not None else "missing master layer")\n'
        "                for shape in writer.components(source)\n"
        "            ]\n"
        "            if source is not None\n"
        "            else []\n"
        "        )\n"
        "    active = glyph.updateActiveLayer(False)\n"
        "    if active is None or active.isNull:\n"
        "        return []\n"
        "    targets = []\n"
        "    for index, source in enumerate(active.shapes):\n"
        "        if not source.isComponent or not source.selected:\n"
        "            continue\n"
        "        shape = (\n"
        "            layer.shapes[index]\n"
        "            if layer is not None and index < len(layer.shapes)\n"
        "            else None\n"
        "        )\n"
        "        same = (\n"
        "            shape is not None\n"
        "            and shape.isComponent\n"
        "            and writer.base_of(shape) == writer.base_of(source)\n"
        "        )\n"
        "        targets.append(\n"
        "            (\n"
        "                shape if same else source,\n"
        '                "" if same else "component position or source differs in this master",\n'
        "            )\n"
        "        )\n"
        "    return targets\n"
        "\n"
        "\n"
        "def location_plan(\n"
        "    package: Any,\n"
        "    glyphs: list[Any],\n"
        "    masters: list[str],\n"
        "    values: dict[str, dict[str, float]],\n"
        "    facts: history.AutoFacts,\n"
        "    *,\n"
        "    reset: bool = False,\n"
        '    name: str = "",\n'
        "    selected_only: bool = True,\n"
        "    row_values: dict[RowKey, dict[str, float]] | None = None,\n"
        "    changed: set[RowKey] | None = None,\n"
        "    observed: dict[RowKey, str] | None = None,\n"
        "    row_errors: dict[RowKey, str] | None = None,\n"
        ") -> writer.Plan:\n"
        '    """Preview each eligible edit or kept occurrence; a refusal stays local."""\n'
        '    if any(c in name for c in ("\\x00", "\\u00a0", "\\u2028", "\\u2029")):\n'
        "        raise ValueError(\n"
        '            "Enter a source name without control or non-breaking characters."\n'
        "        )\n"
        "    plan = writer.Plan()\n"
        '    refused = history.refusals(facts, [g.name for g in glyphs], "geometry")\n'
        "    for glyph in glyphs:\n"
        "        for master in masters:\n"
        '            label = f"{glyph.name} · {master}"\n'
        "            layer = writer.layer_of(glyph, master)\n"
        '            reason = refused.get(glyph.name, "")\n'
        "            if layer is None:\n"
        '                reason = "missing master layer"\n'
        "            elif (\n"
        "                layer.autoLayer\n"
        "                or layer.isLocked\n"
        "                or layer.isMaskLayer\n"
        "                or layer.isService\n"
        "            ):\n"
        '                reason = "automatic, locked or service layer"\n'
        "            edits = []\n"
        "            for shape, mismatch in component_targets(glyph, layer, selected_only):\n"
        "                base = writer.base_of(shape)\n"
        "                if name.strip() and base != name.strip():\n"
        "                    continue\n"
        "                why = reason or mismatch\n"
        "                if not why and int(shape.shapeData.referenceCount) != 1:\n"
        '                    why = "shared element data"\n'
        "                if not why and package.findName(base) is None:\n"
        '                    why = f"missing source glyph {base}"\n'
        "                old = str(shape.shapeData.componentLayer)\n"
        "                key = (str(glyph.name), master, shape.id)\n"
        "                location = str(layer.name) if reset and layer is not None else old\n"
        "                untouched = not reset and changed is not None and key not in changed\n"
        "                if not reset and not untouched and not why:\n"
        "                    try:\n"
        "                        coordinates = (\n"
        "                            row_values.get(key, {})\n"
        "                            if row_values is not None\n"
        "                            else values.get(master, {})\n"
        "                        )\n"
        "                        location = encode_location(package, coordinates)\n"
        '                        if "@" in old:\n'
        '                            location += old[old.index("@") :]\n'
        "                    except (ValueError, RuntimeError, TimeoutError) as error:\n"
        "                        why = str(error)\n"
        "                if not reset and observed is not None and observed.get(key) != old:\n"
        '                    why = "component location changed; reload selection"\n'
        "                if not reset and row_errors is not None and key in row_errors:\n"
        "                    why = row_errors[key]\n"
        "                edit = None if why or old == location else (shape.id, location)\n"
        '                result = f"kept: {why}" if why else (location or "current layer")\n'
        "                if not why and edit is None:\n"
        '                    result = "same, kept"\n'
        "                plan.rows.append(\n"
        "                    (\n"
        "                        label,\n"
        "                        writer.Change(\n"
        '                            base, old or "base active layer", result, edit, key=key\n'
        "                        ),\n"
        "                    )\n"
        "                )\n"
        "                if edit is not None:\n"
        "                    edits.append(edit)\n"
        "            if edits:\n"
        "                plan.work.append((glyph, layer, edits))\n"
        "    return plan\n"
        "\n"
        "\n"
        "def current_coordinates(package: Any, shape: Any, master: str) -> dict[str, float]:\n"
        '    """Read a component\'s explicit coordinates or named source-layer position.\n'
        "\n"
        "    flLocation supports key reads: the native mapping returns None for an\n"
        "    absent key, a float for a scalar and a tuple for an anisotropic value.\n"
        "    Do not iterate it or reinterpret an anisotropic position as a scalar.\n"
        '    """\n'
        '    reference = str(shape.shapeData.componentLayer).split("@", 1)[0]\n'
        '    head, marker, text = reference.partition("#")\n'
        "    position = None\n"
        "    if head in package.masters:\n"
        "        position = package.location(head)\n"
        "    elif head:\n"
        "        base = package.findName(writer.base_of(shape))\n"
        "        layer = writer.layer_of(base, head) if base is not None else None\n"
        "        if layer is None:\n"
        "            raise ValueError(\n"
        '                f"Cannot read source layer {head}; use Reset or the native instance control."\n'
        "            )\n"
        "        position = layer.getMasterPosition()\n"
        "    elif not marker:\n"
        "        base = package.findName(writer.base_of(shape))\n"
        "        layer = base.updateActiveLayer(False) if base is not None else None\n"
        "        if layer is None:\n"
        '            raise ValueError("Cannot read the base active layer; use Reset.")\n'
        "        position = layer.getMasterPosition()\n"
        "    values = {}\n"
        "    aliases = {}\n"
        "    for axis in package.axes:\n"
        "        key = str(axis.shortName).lower()\n"
        "        aliases[key] = aliases[str(axis.name).lower()] = key\n"
        "        number = position[key] if position is not None else None\n"
        "        if number is None:\n"
        "            number = float(axis.designDef)\n"
        "        if not isinstance(number, (int, float)) or not math.isfinite(number):\n"
        "            raise ValueError(\n"
        '                f"Cannot edit anisotropic or non-finite {key}; use the native instance control."\n'
        "            )\n"
        "        values[key] = float(number)\n"
        "    if marker:\n"
        '        for pair in re.split(r"[,;\\s]+", text.strip()):\n'
        "            if not pair:\n"
        "                continue\n"
        '            name, sign, value = pair.partition("=")\n'
        "            if not sign or name.lower() not in aliases:\n"
        "                raise ValueError(\n"
        '                    "Cannot read custom or bounded axis coordinates; use the native instance control."\n'
        "                )\n"
        "            values[aliases[name.lower()]] = float(value)\n"
        "    if any(not math.isfinite(value) for value in values.values()):\n"
        '        raise ValueError("Current location is non-finite; use Reset.")\n'
        "    return values\n"
        "\n"
        "\n"
        "class LocationEditor(writer.Editor):\n"
        '    """Change only the source-layer choice; no element is removed or cloned."""\n'
        "\n"
        "    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:\n"
        '        """Resolve existing shape IDs before history opens."""\n'
        "        return [\n"
        "            (layer.shapes[writer.shape_index(layer, shape_id)], location)\n"
        "            for shape_id, location in edits\n"
        "        ]\n"
        "\n"
        "    def write(self, layer: Any, steps: list[Any]) -> None:\n"
        '        """Rebuild each existing component after setting its location."""\n'
        "        for shape, location in steps:\n"
        "            shape.shapeData.componentLayer = location\n"
        "            writer.refreshed(shape)\n"
        "\n"
        "    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:\n"
        '        """Read back each stored location and its occurrence identity."""\n'
        "        return [\n"
        '            f"{layer.name}/{writer.base_of(shape)}"\n'
        "            for layer, steps in prepared\n"
        "            for shape, location in steps\n"
        "            if str(shape.shapeData.componentLayer) != location\n"
        "            or shape.id not in {part.id for part in layer.shapes}\n"
        "        ]\n",
    ),
    "Unlock Lock": (
        "Scripts/Components/Unlock Lock.py",
        "6843ba684bfaea21376959452c2dbc678fc16b75a58bced14bbbf493d62fb8fc",
        (
            "data_tool",
            "element_name",
            "explicit_locks",
            "lock_states",
            "word",
            "lock_changes",
            "LockEditor",
        ),
        "def data_tool(tool: str, **arguments: Any) -> Any:\n"
        '    """Call one of FontLab\'s own data tools in-process (fly.pr is native fontpr).\n'
        "\n"
        "    An error answer becomes RuntimeError with FontLab's text.\n"
        '    """\n'
        "    from fly import pr\n"
        "\n"
        "    result = pr.call(tool, **arguments)\n"
        "    if isinstance(result, dict) and (\n"
        '        result.get("error") or result.get("status") == "error"\n'
        "    ):\n"
        '        raise RuntimeError(str(result.get("error") or result.get("message")))\n'
        "    return result\n"
        "\n"
        "\n"
        "def element_name(element: Any) -> str:\n"
        '    """Base glyph name of a component element, \'\' for any other element."""\n'
        '    component = element.get("component") if isinstance(element, dict) else None\n'
        '    return str(component.get("glyphName", "")) if isinstance(component, dict) else ""\n'
        "\n"
        "\n"
        "def explicit_locks(package: Any, name: str) -> dict[str, Entries]:\n"
        '    """{layer name: element entries} from FontLab\'s stored glyph data."""\n'
        '    data = data_tool("get_glyph", font_id=scripting.font_id(package), glyph_name=name)\n'
        '    data = data.get("glyph", data) if isinstance(data, dict) else {}\n'
        "    found: dict[str, Entries] = {}\n"
        '    for layer in data.get("layers", None) or []:\n'
        '        elements = layer.get("elements", None) or []\n'
        '        found[str(layer.get("name"))] = [\n'
        '            (element_name(e), bool(e.get("locked", False))) for e in elements\n'
        "        ]\n"
        "    return found\n"
        "\n"
        "\n"
        "def lock_states(layer: Any, entries: Entries | None) -> list[bool | None]:\n"
        '    """Own lock flag per layer shape; all None when data and shapes differ.\n'
        "\n"
        "    The data counts only when it has one element per shape, components at the\n"
        "    same positions, with the same base names.\n"
        '    """\n'
        "    shapes = list(layer.shapes)\n"
        "    unknown: list[bool | None] = [None] * len(shapes)\n"
        "    if entries is None or len(entries) != len(shapes):\n"
        "        return unknown\n"
        "    for shape, (name, _) in zip(shapes, entries, strict=True):\n"
        "        if bool(shape.isComponent) != bool(name):\n"
        "            return unknown\n"
        "        if shape.isComponent and name != component_writer.base_of(shape):\n"
        "            return unknown\n"
        "    return [locked for _, locked in entries]\n"
        "\n"
        "\n"
        "def word(state: bool | None) -> str:\n"
        "    \"\"\"'locked', 'unlocked' or 'unknown'.\"\"\"\n"
        '    return "unknown" if state is None else ("locked" if state else "unlocked")\n'
        "\n"
        "\n"
        "def lock_changes(\n"
        "    glyph: Any, layer: Any, entries: Entries | None, locked: bool\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per component: state now and after the action."""\n'
        "    rows: list[component_writer.Change] = []\n"
        "    states = lock_states(layer, entries)\n"
        "    for shape, state in zip(layer.shapes, states, strict=True):\n"
        "        if not shape.isComponent:\n"
        "            continue\n"
        "        name, now = component_writer.base_of(shape), word(state)\n"
        "        if state is None:\n"
        '            rows.append(component_writer.Change(name, now, "unknown, kept"))\n'
        "        elif state == locked:\n"
        '            rows.append(component_writer.Change(name, now, "already " + now))\n'
        "        else:\n"
        "            edit = (shape.id, locked, glyph.name)\n"
        "            rows.append(component_writer.Change(name, now, word(locked), edit))\n"
        "    return rows\n"
        "\n"
        "\n"
        "class LockEditor(component_writer.Editor):\n"
        '    """Set the own lock flag of each planned component in place."""\n'
        "\n"
        "    def __init__(self, package: Any) -> None:\n"
        "        self.package = package\n"
        "\n"
        "    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:\n"
        "        return [\n"
        "            (layer.shapes[component_writer.shape_index(layer, shape_id)], locked, name)\n"
        "            for shape_id, locked, name in edits\n"
        "        ]\n"
        "\n"
        "    def write(self, layer: Any, steps: list[Any]) -> None:\n"
        "        for shape, locked, _ in steps:\n"
        "            shape.contentLocked = locked\n"
        "            shape.changed()\n"
        "\n"
        "    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:\n"
        "        missed: list[str] = []\n"
        "        stored: dict[str, dict[str, Entries]] = {}\n"
        "        for layer, steps in prepared:\n"
        "            for shape, locked, name in steps:\n"
        "                if name not in stored:\n"
        "                    stored[name] = explicit_locks(self.package, name)\n"
        "                states = lock_states(layer, stored[name].get(str(layer.name)))\n"
        "                if states[component_writer.shape_index(layer, shape.id)] is not locked:\n"
        "                    missed.append(\n"
        '                        f"{name}/{layer.name}/{component_writer.base_of(shape)}"\n'
        "                    )\n"
        "        return missed\n",
    ),
}
