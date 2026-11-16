# this_file: tests/_derived_glyphs_originals.py
"""The Scriptmix scripts Derived Glyphs absorbs: file hashes and verbatim pure functions.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show 25c86b4:<path>``), not retyped.
Each entry is ``(path, sha256 of the whole file, names, source of those definitions)``; the parity tests
compare the ported definitions with these (AST equality after dropping the originals' function-local
``fly`` import lines, which the ports replace with module names). Make Lower Unicase shares the
component-set writer of Set Default Figures; its own ``apply_pairs`` body equals that writer's body.
"""

ORIGINALS = {
    "Small Caps From Capitals": (
        "Scripts/Contours/Small Caps From Capitals.py",
        "f39816aa5d04c428223ff2cbb90b480e10ed8053225fc17ebc82c1a9d3de2b89",
        ("SUFFIX", "is_capital", "target_name", "naming", "survey", "prepare"),
        'SUFFIX = ".sc"\n'
        "\n"
        "\n"
        "def is_capital(name: str) -> bool:\n"
        '    """True when the base name (before the first dot) starts with a capital letter."""\n'
        '    base = name.partition(".")[0]\n'
        "    return base[:1].isupper() and base.lower() != base\n"
        "\n"
        "\n"
        "def target_name(name: str) -> str:\n"
        '    """Return the small-cap name: H -> h.sc, H.ss01 -> h.sc.ss01."""\n'
        '    base, dot, rest = name.partition(".")\n'
        '    return base.lower() + SUFFIX + (dot + rest if dot else "")\n'
        "\n"
        "\n"
        "def naming(name: str) -> tuple[str, str]:\n"
        '    """Return (new name, problem) for a selected glyph name."""\n'
        "    if not is_capital(name):\n"
        '        return "", "not a capital"\n'
        '    return target_name(name), ""\n'
        "\n"
        "\n"
        "def survey(\n"
        "    package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool = False\n"
        ") -> list[Any]:\n"
        '    """Plan one small cap per selected capital. Change nothing."""\n'
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    return glyph_copies.survey_with(package, names, naming, facts, allow_rebuild)\n"
        "\n"
        "\n"
        "def prepare(rows: Sequence[Any], x_scale: int, y_scale: int) -> list[Any]:\n"
        '    """Return the jobs: copies scaled by the percentages about the origin."""\n'
        "    import fly.ap.contours.copy as contour_copy  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402\n"
        "    from fly import qt\n"
        "\n"
        "    sx, sy = x_scale / 100, y_scale / 100\n"
        "    transform = qt.QtGui.QTransform(sx, 0, 0, sy, 0, 0)\n"
        "    return [\n"
        "        (\n"
        "            row.target,\n"
        "            [\n"
        "                (\n"
        "                    m,\n"
        "                    contour_copy.copy_contours(x, transform),\n"
        "                    glyph_copies.half_up(x.advanceWidth * sx),\n"
        "                )\n"
        "                for m, x in row.layers\n"
        "            ],\n"
        "        )\n"
        "        for row in rows\n"
        "        if not row.note\n"
        "    ]\n",
    ),
    "Superior & Inferior Figures": (
        "Scripts/Contours/Superior & Inferior Figures.py",
        "fb4d8c118e38e968a2c2390729444ca7f07de250fb36bc07711ea3b86377e823",
        ("FIGURES", "KINDS", "SIZED", "naming_for", "survey", "prepare"),
        "FIGURES = frozenset(\n"
        '    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}\n'
        ")\n"
        "\n"
        "\n"
        "KINDS = (\n"
        '    (".sups", "Superior", 350),\n'
        '    (".subs", "Inferior", -150),\n'
        ")  # suffix, label, preset shift\n"
        "\n"
        "\n"
        "SIZED = frozenset(\n"
        '    {"sups", "subs", "sinf", "numr", "dnom"}\n'
        ")  # suffixes of figures that are sized already\n"
        "\n"
        "\n"
        "def naming_for(suffix: str) -> Any:\n"
        '    """Return the naming function for ``suffix`` (".sups" or ".subs")."""\n'
        "\n"
        "    def naming(name: str) -> tuple[str, str]:\n"
        '        parts = name.split(".")\n'
        "        if parts[0] not in FIGURES:\n"
        '            return "", "not a figure"\n'
        "        if SIZED.intersection(parts[1:]):\n"
        '            return "", "already superior or inferior"\n'
        '        return name + suffix, ""\n'
        "\n"
        "    return naming\n"
        "\n"
        "\n"
        "def survey(\n"
        "    package: Any,\n"
        "    names: Sequence[str],\n"
        "    facts: Any,\n"
        '    suffix: str = ".sups",\n'
        "    allow_rebuild: bool = False,\n"
        ") -> list[Any]:\n"
        '    """Plan one sized copy per selected figure. Change nothing."""\n'
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    return glyph_copies.survey_with(\n"
        "        package, names, naming_for(suffix), facts, allow_rebuild\n"
        "    )\n"
        "\n"
        "\n"
        "def prepare(rows: Sequence[Any], scale: int, shift: int) -> list[Any]:\n"
        '    """Return the jobs: copies scaled by ``scale`` percent about the origin, then shifted up."""\n'
        "    import fly.ap.contours.copy as contour_copy  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402\n"
        "    from fly import qt\n"
        "\n"
        "    factor = scale / 100\n"
        "    transform = qt.QtGui.QTransform(factor, 0, 0, factor, 0, shift)\n"
        "    return [\n"
        "        (\n"
        "            row.target,\n"
        "            [\n"
        "                (\n"
        "                    m,\n"
        "                    contour_copy.copy_contours(x, transform),\n"
        "                    glyph_copies.half_up(x.advanceWidth * factor),\n"
        "                )\n"
        "                for m, x in row.layers\n"
        "            ],\n"
        "        )\n"
        "        for row in rows\n"
        "        if not row.note\n"
        "    ]\n",
    ),
    "Tabular Figure Copies": (
        "Scripts/Contours/Tabular Figure Copies.py",
        "b8dfa9eedfded808badf20ed2551fb9dff601af30ca9a50afd88fde13193afc2",
        (
            "SUFFIX",
            "FIGURES",
            "naming",
            "survey",
            "tabular_widths",
            "centring_shift",
            "prepare",
        ),
        'SUFFIX = ".tf"\n'
        "\n"
        "\n"
        "FIGURES = frozenset(\n"
        '    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}\n'
        ")\n"
        "\n"
        "\n"
        "def naming(name: str) -> tuple[str, str]:\n"
        '    """Return (new name, problem) for a selected glyph name."""\n'
        '    parts = name.split(".")\n'
        "    if parts[0] not in FIGURES:\n"
        '        return "", "not a figure"\n'
        '    if "tf" in parts[1:]:\n'
        '        return "", "already tabular"\n'
        '    return name + SUFFIX, ""\n'
        "\n"
        "\n"
        "def survey(\n"
        "    package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool = False\n"
        ") -> list[Any]:\n"
        '    """Plan one tabular copy per selected figure. Change nothing."""\n'
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    return glyph_copies.survey_with(package, names, naming, facts, allow_rebuild)\n"
        "\n"
        "\n"
        "def tabular_widths(rows: Sequence[Any], extra: int) -> dict[str, int]:\n"
        '    """Map each master to the widest source advance (rounded half up) plus ``extra``."""\n'
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    widths: dict[str, int] = {}\n"
        "    for row in rows:\n"
        "        if row.note:\n"
        "            continue\n"
        "        for master, layer in row.layers:\n"
        "            widths[master] = max(\n"
        "                widths.get(master, 0), glyph_copies.half_up(layer.advanceWidth)\n"
        "            )\n"
        "    return {master: width + extra for master, width in widths.items()}\n"
        "\n"
        "\n"
        "def centring_shift(layer: Any, width: int) -> int:\n"
        '    """Return the whole-unit x shift that centres the outline in ``width``.\n'
        "\n"
        "    The left side becomes (width - ink width) // 2; an odd unit goes right.\n"
        '    """\n'
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    box = layer.boundingBox\n"
        "    left = glyph_copies.half_up(box.x())\n"
        "    ink = glyph_copies.half_up(box.x() + box.width()) - left\n"
        "    return (width - ink) // 2 - left\n"
        "\n"
        "\n"
        "def prepare(rows: Sequence[Any], widths: dict[str, int]) -> list[Any]:\n"
        '    """Return the jobs: centred contour copies and the shared width per master."""\n'
        "    import fly.ap.contours.copy as contour_copy  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "    from fly import qt\n"
        "\n"
        "    jobs: list[Any] = []\n"
        "    for row in rows:\n"
        "        if row.note:\n"
        "            continue\n"
        "        layers = []\n"
        "        for master, layer in row.layers:\n"
        "            move = qt.QtGui.QTransform(\n"
        "                1, 0, 0, 1, centring_shift(layer, widths[master]), 0\n"
        "            )\n"
        "            layers.append(\n"
        "                (master, contour_copy.copy_contours(layer, move), widths[master])\n"
        "            )\n"
        "        jobs.append((row.target, layers))\n"
        "    return jobs\n",
    ),
    "Set Default Figures": (
        "Scripts/Components/Set Default Figures.py",
        "5c85f757a55663252e39bb53006b7b6db95f612374efca5f91bf32169ab26a78",
        (
            "Pair",
            "CHOICES",
            "DIGITS",
            "load_family",
            "save_family",
            "mappings",
            "group_plan",
            "validate_pairs",
            "prepare",
            "component_rows",
            "write_components",
            "apply_pairs",
        ),
        "Pair = tuple[str, str]  # target, base\n"
        "\n"
        "\n"
        "CHOICES = (\n"
        '    "Lining (.lf)",\n'
        '    "Oldstyle (.osf)",\n'
        '    "Tabular lining (.tf)",\n'
        '    "Tabular oldstyle (.tosf)",\n'
        ")\n"
        "\n"
        "\n"
        "DIGITS = (\n"
        '    "zero",\n'
        '    "one",\n'
        '    "two",\n'
        '    "three",\n'
        '    "four",\n'
        '    "five",\n'
        '    "six",\n'
        '    "seven",\n'
        '    "eight",\n'
        '    "nine",\n'
        ")\n"
        "\n"
        "\n"
        "def load_family(settings: Any) -> int:\n"
        '    """Restore the tool\'s family; absent or malformed values select lining."""\n'
        "    settings.setFallbacksEnabled(False)\n"
        "    settings.sync()\n"
        "    if settings.status() != type(settings).NoError:\n"
        '        raise RuntimeError("Figure settings could not be read.")\n'
        '    value = str(settings.value("optionFigures", 0))\n'
        '    return int(value) if value in ("0", "1", "2", "3") else 0\n'
        "\n"
        "\n"
        "def save_family(settings: Any, option: int) -> None:\n"
        '    """Save only the chosen family; report unconfirmed writes without editing fonts."""\n'
        "    if type(option) is not int or option not in range(4):\n"
        '        raise ValueError("Choose one of the four figure sets.")\n'
        "    if not settings.isWritable():\n"
        '        raise RuntimeError("Figure settings are read-only.")\n'
        '    settings.setValue("optionFigures", option)\n'
        "    settings.sync()\n"
        "    if settings.status() != type(settings).NoError:\n"
        '        raise RuntimeError("Figure settings could not be saved.")\n'
        "\n"
        "\n"
        "def mappings(package: Any, option: int = 0) -> list[Pair]:\n"
        '    """Require every source in the requested family; allow missing default cells."""\n'
        "    if option not in range(4):\n"
        '        raise ValueError("Choose one of the four figure sets.")\n'
        '    suffix = ("lf", "osf", "tf", "tosf")[option]\n'
        '    pairs = [(name, f"{name}.{suffix}") for name in DIGITS]\n'
        "    for target, base in pairs:\n"
        "        if package.findName(base) is None:\n"
        '            raise ValueError(f"Missing {target} or {base}; no figures changed.")\n'
        "    return pairs\n"
        "\n"
        "\n"
        "def group_plan(package: Any, pairs: list[Pair]) -> dict[str, dict[str, Any]]:\n"
        '    """Give targets the same per-side class memberships as their bases."""\n'
        "    desired = {}\n"
        "    for master in package.masters:\n"
        "        groups = {}\n"
        "        for name, (members, mode) in package.kerning(master).groups.items():\n"
        "            original = list(members)\n"
        '            if mode not in {"KernLeft", "KernRight", "KernBothSide"}:\n'
        "                continue\n"
        "            new = [member for member in original if member not in {t for t, _ in pairs}]\n"
        "            new.extend(\n"
        "                target\n"
        "                for target, base in pairs\n"
        "                if base in original and target not in new\n"
        "            )\n"
        "            if new != original:\n"
        "                groups[str(name)] = (new, mode)\n"
        "        desired[str(master)] = groups\n"
        "    return desired\n"
        "\n"
        "\n"
        "def validate_pairs(\n"
        "    package: Any,\n"
        "    pairs: list[Pair],\n"
        "    *,\n"
        "    facts: history.AutoFacts | None = None,\n"
        "    allow_rebuild: bool = False,\n"
        ") -> None:\n"
        '    """Check masters, layer locks, automatic owners and component cycles."""\n'
        "    if not package.masters:\n"
        '        raise ValueError("The font needs at least one master.")\n'
        "    if not pairs:\n"
        '        raise ValueError("No matching glyphs. Check the font and figure names.")\n'
        "    facts = history.scan_auto_facts(package) if facts is None else facts\n"
        "    for target, base in pairs:\n"
        '        why = history.refusal(facts, target, "geometry", allow_bases=allow_rebuild)\n'
        "        if why:\n"
        '            raise ValueError(f"{target}: {why}.")\n'
        "        for master in package.masters:\n"
        "            source = package.findName(base)\n"
        "            layer = source.findLayer(master) if source is not None else None\n"
        "            if layer is None or layer.isNull or layer.autoLayer:\n"
        '                raise ValueError(f"{base}: needs a plain layer for {master}.")\n'
        "            glyph = package.findName(target)\n"
        "            old = glyph.findLayer(master) if glyph is not None else None\n"
        "            if old is not None and not old.isNull and old.isLocked:\n"
        '                raise ValueError(f"{target} · {master}: layer is locked.")\n'
        "        # A new base must not reach the target through existing components.\n"
        "        todo, seen = [base], set()\n"
        "        while todo:\n"
        "            name = todo.pop()\n"
        "            if name == target:\n"
        '                raise ValueError(f"{target}: the new component would be circular.")\n'
        "            if name in seen:\n"
        "                continue\n"
        "            seen.add(name)\n"
        "            glyph = package.findName(name)\n"
        "            if glyph is not None:\n"
        "                todo.extend(\n"
        "                    writer.base_of(s)\n"
        "                    for layer in glyph.layers\n"
        "                    for s in writer.components(layer)\n"
        "                )\n"
        "\n"
        "\n"
        "def prepare(\n"
        "    package: Any, pairs: list[Pair], *, allow_rebuild: bool = False\n"
        ") -> list[tuple[str, str, Any, float]]:\n"
        '    """Build detached components through the App before the outline commit."""\n'
        "    facts = history.scan_auto_facts(package)\n"
        "    validate_pairs(package, pairs, facts=facts, allow_rebuild=allow_rebuild)\n"
        "    result = []\n"
        "    for target, base in pairs:\n"
        "        wanted = [\n"
        "            component_creation.NewComponent(base, str(m)) for m in package.masters\n"
        "        ]\n"
        "        components = component_creation.build_components(package, target, wanted, facts)\n"
        "        for master, component in zip(package.masters, components, strict=True):\n"
        "            layer = package.findName(base).findLayer(master)\n"
        "            result.append((target, str(master), component, float(layer.advanceWidth)))\n"
        "    return result\n"
        "\n"
        "\n"
        "def component_rows(\n"
        "    package: Any, rows: list[glyph_copies.Row], *, allow_rebuild: bool = False\n"
        ") -> list[glyph_copies.Row]:\n"
        '    """List per-target refusals without discarding other eligible targets."""\n'
        "    facts = history.scan_auto_facts(package)\n"
        "    candidates = glyph_creation.auto_candidates(\n"
        "        package,\n"
        "        facts,\n"
        "        [r.target for r in rows if r.target and package.findName(r.target) is None],\n"
        "    )\n"
        "    existing = any(not r.note and package.findName(r.target) is not None for r in rows)\n"
        "    safe = component_creation.prototype(package, facts) if existing else None\n"
        "    result = []\n"
        "    for row in rows:\n"
        "        note = row.note\n"
        "        rebuild = candidates.get(row.target, ())\n"
        "        if not note:\n"
        "            try:\n"
        "                validate_pairs(\n"
        "                    package,\n"
        "                    [(row.target, row.source)],\n"
        "                    facts=facts,\n"
        "                    allow_rebuild=allow_rebuild,\n"
        "                )\n"
        "                if package.findName(row.target) is not None:\n"
        "                    if safe is None:\n"
        '                        note = f"{row.target}: kept; {component_creation.NO_PROTOTYPE}."\n'
        "                elif rebuild and not allow_rebuild:\n"
        '                    note = f"{row.target}: kept; {glyph_creation.rebuild_note(rebuild)}"\n'
        "            except ValueError as error:\n"
        '                note = f"{row.target}: kept; {error}"\n'
        "        result.append(\n"
        "            glyph_copies.Row(row.source, row.target, note=note, rebuild=rebuild)\n"
        "        )\n"
        "    return result\n"
        "\n"
        "\n"
        "def write_components(\n"
        "    package: Any,\n"
        "    pairs: list[Pair],\n"
        "    *,\n"
        "    title: str = TITLE,\n"
        "    replace_contours: bool = False,\n"
        "    clear_anchors: bool = True,\n"
        "    allow_rebuild: bool = False,\n"
        "    unicodes: dict[str, tuple[int, ...]] | None = None,\n"
        "    kept: list[str] | None = None,\n"
        "    report: list[str] | None = None,\n"
        "    disclosure: dict[str, Any] | None = None,\n"
        ") -> int:\n"
        '    """Replace target components, widths and class memberships in one history batch."""\n'
        "    ids = edit_guards.pending_updates()\n"
        '    captured = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}\n'
        "    edit_guards.disclose(captured, disclosure if disclosure is not None else {})\n"
        "    if report is not None and ids and disclosure is None:\n"
        '        report.append(captured["pending_note"])\n'
        "    elif disclosure is None and report is None:\n"
        "        edit_guards.disclose(captured)\n"
        "    facts = history.scan_auto_facts(package)\n"
        "    rows = component_rows(\n"
        "        package,\n"
        "        [glyph_copies.Row(base, target) for target, base in pairs],\n"
        "        allow_rebuild=allow_rebuild,\n"
        "    )\n"
        "    if kept is not None:\n"
        "        kept.extend(row.note for row in rows if row.note)\n"
        "    pairs = [(r.target, r.source) for r in rows if not r.note]\n"
        "    existing = [(t, b) for t, b in pairs if package.findName(t) is not None]\n"
        "    steps = prepare(package, existing, allow_rebuild=allow_rebuild) if existing else []\n"
        "    specs = [\n"
        "        glyph_creation.NewGlyph(\n"
        "            target,\n"
        "            tuple(\n"
        "                (str(m), float(package.findName(base).findLayer(m).advanceWidth))\n"
        "                for m in package.masters\n"
        "            ),\n"
        "            (unicodes or {}).get(target, ()),\n"
        "            components=tuple(\n"
        "                glyph_creation.Part(str(m), base) for m in package.masters\n"
        "            ),\n"
        "        )\n"
        "        for target, base in pairs\n"
        "        if package.findName(target) is None\n"
        "    ]\n"
        "    groups = group_plan(package, pairs)\n"
        "    created = glyph_creation.create_glyphs(\n"
        "        package, specs, title, facts, allow_rebuild=allow_rebuild\n"
        "    )\n"
        "    names = [str(glyph.name) for glyph in created.glyphs]\n"
        '    created_text = "new glyphs that exist now: " + ", ".join(names) if names else ""\n'
        "    diagnostics = list(created.mismatches)\n"
        "    if report is not None:\n"
        "        report.extend(([created_text] if created_text else []) + diagnostics)\n"
        "    if diagnostics and not allow_rebuild:\n"
        '        raise RuntimeError("; ".join([*diagnostics, created_text, history.UNDO_HINT]))\n'
        "    if not steps and not any(groups.values()):\n"
        "        return len(specs) * len(package.masters)\n"
        "    if steps:\n"
        "        edited = list(dict.fromkeys(target for target, _, _, _ in steps))\n"
        "        glyphs = [package.findName(target) for target in edited]\n"
        "        layers = [\n"
        "            package.findName(target).findLayer(master) for target, master, _, _ in steps\n"
        "        ]\n"
        "        layers = [layer for layer in layers if layer is not None and not layer.isNull]\n"
        "    else:\n"
        "        memberships = [\n"
        "            (target, master)\n"
        "            for target, _ in pairs\n"
        "            for master, changes in groups.items()\n"
        "            if any(\n"
        "                (target in package.kerning(master).groups[name][0])\n"
        "                != (target in value[0])\n"
        "                for name, value in changes.items()\n"
        "            )\n"
        "        ]\n"
        "        edited = list(dict.fromkeys(target for target, _ in memberships))\n"
        "        glyphs = [package.findName(target) for target in edited]\n"
        "        layers = [\n"
        "            package.findName(target).findLayer(master) for target, master in memberships\n"
        "        ]\n"
        "        layers = [layer for layer in layers if layer is not None and not layer.isNull]\n"
        "    retain = [\n"
        "        item\n"
        "        for layer in layers\n"
        "        for shape in writer.components(layer)\n"
        "        for item in history.component_history(shape)\n"
        "    ]\n"
        "    container = package.kerningContainer()\n"
        "    retain.extend([package, package.mastersContainer(), container])\n"
        "    made, written = [], []\n"
        "\n"
        "    def mutate() -> list[Any]:\n"
        "        package.checkInitHistoryState(0)\n"
        "        container.checkInitHistoryState(0)\n"
        "        for target, master, component, width in steps:\n"
        "            glyph = package.findName(target)\n"
        "            if glyph is None:\n"
        '                raise ValueError(f"{target}: target changed; Preview again.")\n'
        "            layer = glyph.findLayer(master)\n"
        "            if layer is None or layer.isNull:\n"
        "                layer = glyph.findLayerCreate(master)\n"
        "                made.append(layer)\n"
        "            if replace_contours:\n"
        "                for shape in list(layer.shapes):\n"
        "                    if shape.isComponent or bool(shape.contours):\n"
        "                        layer.removeShape(shape)\n"
        "                if clear_anchors:\n"
        "                    layer.clearAnchors()\n"
        "            else:\n"
        "                for shape in list(writer.components(layer)):\n"
        "                    layer.removeShape(shape)\n"
        "            component = component_creation.add_component(layer, component)\n"
        "            writer.refreshed(component)\n"
        "            layer.advanceWidth = width\n"
        "            layer.changed()\n"
        "            if layer.update() is False:\n"
        '                raise RuntimeError(f"FontLab could not update {target} · {master}.")\n'
        "            written.append((layer, component, width))\n"
        "        for master, changes in groups.items():\n"
        "            for name, value in changes.items():\n"
        "                package.kerning(master).groups[name] = value\n"
        "        return made\n"
        "\n"
        "    def read_back() -> list[str]:\n"
        "        missed = [\n"
        "            str(layer.name)\n"
        "            for layer, component, width in written\n"
        "            if component not in layer.shapes or layer.advanceWidth != width\n"
        "        ]\n"
        "        for master, changes in groups.items():\n"
        "            now = dict(package.kerning(master).groups.items())\n"
        "            missed.extend(\n"
        '                f"{master}: class {name}"\n'
        "                for name, value in changes.items()\n"
        "                if name not in now or (list(now[name][0]), now[name][1]) != value\n"
        "            )\n"
        "        return missed\n"
        "\n"
        "    try:\n"
        "        result = history.commit(\n"
        "            title,\n"
        "            layers,\n"
        "            glyphs,\n"
        "            mutate,\n"
        '            operation="geometry" if steps else "metadata",\n'
        "            facts=history.scan_auto_facts(package),\n"
        "            allow_bases=allow_rebuild,\n"
        "            retain=retain,\n"
        "            read_back=read_back,\n"
        "        )\n"
        "    except (ValueError, RuntimeError, TimeoutError) as error:\n"
        "        if names:\n"
        "            raise history.PartialWriteError(\n"
        "                title,\n"
        "                [\n"
        "                    error,\n"
        "                    RuntimeError(created_text),\n"
        "                    *(RuntimeError(text) for text in diagnostics),\n"
        "                ],\n"
        "            ) from error\n"
        "        raise\n"
        "    if result.mismatches:\n"
        "        raise RuntimeError(\n"
        '            "; ".join(\n'
        "                [*diagnostics, *result.mismatches, created_text, history.UNDO_HINT]\n"
        "            )\n"
        "        )\n"
        "    return len(steps) + len(specs) * len(package.masters)\n"
        "\n"
        "\n"
        "def apply_pairs(\n"
        "    package: Any,\n"
        "    pairs: list[Pair],\n"
        "    *,\n"
        "    replace_contours: bool = False,\n"
        "    allow_rebuild: bool = False,\n"
        "    kept: list[str] | None = None,\n"
        "    report: list[str] | None = None,\n"
        "    disclosure: dict[str, Any] | None = None,\n"
        ") -> int:\n"
        '    """Use the single component-set writer with figure-specific preservation rules."""\n'
        "    return write_components(\n"
        "        package,\n"
        "        pairs,\n"
        "        title=TITLE,\n"
        "        replace_contours=replace_contours,\n"
        "        clear_anchors=False,\n"
        "        allow_rebuild=allow_rebuild,\n"
        "        kept=kept,\n"
        "        report=report,\n"
        "        disclosure=disclosure,\n"
        '        unicodes={name: (ord("0") + i,) for i, name in enumerate(DIGITS)},\n'
        "    )\n",
    ),
    "Make Lower Unicase": (
        "Scripts/Components/Make Lower Unicase.py",
        "9a0d8543dacea929c9e68ffa4f932a170649a68e35ec2e1701d4582bb8e2dcf8",
        (
            "survey",
            "mappings",
            "group_plan",
            "validate_pairs",
            "prepare",
            "component_rows",
            "apply_pairs",
            "plan_key",
        ),
        "def survey(package: Any) -> list[glyph_copies.Row]:\n"
        '    """Choose canonical round-trip sources first, then Unicode and glyph-name order.\n'
        "\n"
        "    For each existing uppercase glyph, the first source wins. Later candidates\n"
        "    are kept rows. Missing uppercase glyphs and multi-character case mappings\n"
        "    are kept too; this tool never guesses a capital glyph name.\n"
        '    """\n'
        "    records = catalog.capture().rows\n"
        "    owners: dict[int, list[str]] = {}\n"
        "    sources = []\n"
        "    for name, codes, _ in records:\n"
        "        for text in str(codes).split():\n"
        '            code = int(text.removeprefix("U+"), 16)\n'
        "            owners.setdefault(code, []).append(str(name))\n"
        "            char = chr(code)\n"
        "            if char.islower() and char.isalpha():\n"
        "                sources.append((char.upper().lower() != char, code, str(name)))\n"
        "    rows, chosen = [], set()\n"
        "    for _, code, source in sorted(set(sources)):\n"
        "        upper = chr(code).upper()\n"
        "        if len(upper) != 1:\n"
        "            rows.append(\n"
        '                glyph_copies.Row(source, "", note="kept: multi-character uppercase")\n'
        "            )\n"
        "            continue\n"
        "        if upper == chr(code):\n"
        "            rows.append(\n"
        '                glyph_copies.Row(source, source, note="kept: no separate uppercase")\n'
        "            )\n"
        "            continue\n"
        "        targets = sorted(owners.get(ord(upper), []))\n"
        "        if not targets:\n"
        "            rows.append(\n"
        '                glyph_copies.Row(source, "", note="kept: no existing uppercase glyph")\n'
        "            )\n"
        "            continue\n"
        "        target = targets[0]\n"
        "        if target == source or target in chosen:\n"
        "            rows.append(\n"
        "                glyph_copies.Row(\n"
        '                    source, target, note="kept: earlier source has priority"\n'
        "                )\n"
        "            )\n"
        "            continue\n"
        "        chosen.add(target)\n"
        "        rows.append(glyph_copies.Row(source, target))\n"
        "    return rows\n"
        "\n"
        "\n"
        "def mappings(package: Any) -> list[Pair]:\n"
        '    """Return only the ready pairs from the ordered, fully listed case survey."""\n'
        "    return [(row.target, row.source) for row in survey(package) if not row.note]\n"
        "\n"
        "\n"
        "def group_plan(package: Any, pairs: list[Pair]) -> dict[str, dict[str, Any]]:\n"
        '    """Give targets the same per-side class memberships as their bases."""\n'
        "    desired = {}\n"
        "    for master in package.masters:\n"
        "        groups = {}\n"
        "        for name, (members, mode) in package.kerning(master).groups.items():\n"
        "            original = list(members)\n"
        '            if mode not in {"KernLeft", "KernRight", "KernBothSide"}:\n'
        "                continue\n"
        "            new = [member for member in original if member not in {t for t, _ in pairs}]\n"
        "            new.extend(\n"
        "                target\n"
        "                for target, base in pairs\n"
        "                if base in original and target not in new\n"
        "            )\n"
        "            if new != original:\n"
        "                groups[str(name)] = (new, mode)\n"
        "        desired[str(master)] = groups\n"
        "    return desired\n"
        "\n"
        "\n"
        "def validate_pairs(\n"
        "    package: Any,\n"
        "    pairs: list[Pair],\n"
        "    *,\n"
        "    facts: history.AutoFacts | None = None,\n"
        "    allow_rebuild: bool = False,\n"
        ") -> None:\n"
        '    """Check masters, layer locks, automatic owners and component cycles."""\n'
        "    if not package.masters:\n"
        '        raise ValueError("The font needs at least one master.")\n'
        "    if not pairs:\n"
        '        raise ValueError("No matching glyphs. Check the font and figure names.")\n'
        "    facts = history.scan_auto_facts(package) if facts is None else facts\n"
        "    for target, base in pairs:\n"
        '        why = history.refusal(facts, target, "geometry", allow_bases=allow_rebuild)\n'
        "        if why:\n"
        '            raise ValueError(f"{target}: {why}.")\n'
        "        for master in package.masters:\n"
        "            source = package.findName(base)\n"
        "            layer = source.findLayer(master) if source is not None else None\n"
        "            if layer is None or layer.isNull or layer.autoLayer:\n"
        '                raise ValueError(f"{base}: needs a plain layer for {master}.")\n'
        "            glyph = package.findName(target)\n"
        "            old = glyph.findLayer(master) if glyph is not None else None\n"
        "            if old is not None and not old.isNull and old.isLocked:\n"
        '                raise ValueError(f"{target} · {master}: layer is locked.")\n'
        "        # A new base must not reach the target through existing components.\n"
        "        todo, seen = [base], set()\n"
        "        while todo:\n"
        "            name = todo.pop()\n"
        "            if name == target:\n"
        '                raise ValueError(f"{target}: the new component would be circular.")\n'
        "            if name in seen:\n"
        "                continue\n"
        "            seen.add(name)\n"
        "            glyph = package.findName(name)\n"
        "            if glyph is not None:\n"
        "                todo.extend(\n"
        "                    writer.base_of(s)\n"
        "                    for layer in glyph.layers\n"
        "                    for s in writer.components(layer)\n"
        "                )\n"
        "\n"
        "\n"
        "def prepare(\n"
        "    package: Any, pairs: list[Pair], *, allow_rebuild: bool = False\n"
        ") -> list[tuple[str, str, Any, float]]:\n"
        '    """Build detached components through the App before the outline commit."""\n'
        "    facts = history.scan_auto_facts(package)\n"
        "    validate_pairs(package, pairs, facts=facts, allow_rebuild=allow_rebuild)\n"
        "    result = []\n"
        "    for target, base in pairs:\n"
        "        wanted = [\n"
        "            component_creation.NewComponent(base, str(m)) for m in package.masters\n"
        "        ]\n"
        "        components = component_creation.build_components(package, target, wanted, facts)\n"
        "        for master, component in zip(package.masters, components, strict=True):\n"
        "            layer = package.findName(base).findLayer(master)\n"
        "            result.append((target, str(master), component, float(layer.advanceWidth)))\n"
        "    return result\n"
        "\n"
        "\n"
        "def component_rows(\n"
        "    package: Any, rows: list[glyph_copies.Row], *, allow_rebuild: bool = False\n"
        ") -> list[glyph_copies.Row]:\n"
        '    """List per-target refusals without discarding other eligible targets."""\n'
        "    facts = history.scan_auto_facts(package)\n"
        "    candidates = glyph_creation.auto_candidates(\n"
        "        package,\n"
        "        facts,\n"
        "        [r.target for r in rows if r.target and package.findName(r.target) is None],\n"
        "    )\n"
        "    existing = any(not r.note and package.findName(r.target) is not None for r in rows)\n"
        "    safe = component_creation.prototype(package, facts) if existing else None\n"
        "    result = []\n"
        "    for row in rows:\n"
        "        note = row.note\n"
        "        rebuild = candidates.get(row.target, ())\n"
        "        if not note:\n"
        "            try:\n"
        "                validate_pairs(\n"
        "                    package,\n"
        "                    [(row.target, row.source)],\n"
        "                    facts=facts,\n"
        "                    allow_rebuild=allow_rebuild,\n"
        "                )\n"
        "                if package.findName(row.target) is not None:\n"
        "                    if safe is None:\n"
        '                        note = f"{row.target}: kept; {component_creation.NO_PROTOTYPE}."\n'
        "                elif rebuild and not allow_rebuild:\n"
        '                    note = f"{row.target}: kept; {glyph_creation.rebuild_note(rebuild)}"\n'
        "            except ValueError as error:\n"
        '                note = f"{row.target}: kept; {error}"\n'
        "        result.append(\n"
        "            glyph_copies.Row(row.source, row.target, note=note, rebuild=rebuild)\n"
        "        )\n"
        "    return result\n"
        "\n"
        "\n"
        "def apply_pairs(\n"
        "    package: Any,\n"
        "    pairs: list[Pair],\n"
        "    *,\n"
        "    title: str = TITLE,\n"
        "    replace_contours: bool = True,\n"
        "    clear_anchors: bool = True,\n"
        "    allow_rebuild: bool = False,\n"
        "    unicodes: dict[str, tuple[int, ...]] | None = None,\n"
        "    kept: list[str] | None = None,\n"
        "    report: list[str] | None = None,\n"
        "    disclosure: dict[str, Any] | None = None,\n"
        ") -> int:\n"
        '    """Replace target components, widths and class memberships in one history batch."""\n'
        "    ids = edit_guards.pending_updates()\n"
        '    captured = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}\n'
        "    edit_guards.disclose(captured, disclosure if disclosure is not None else {})\n"
        "    if report is not None and ids and disclosure is None:\n"
        '        report.append(captured["pending_note"])\n'
        "    elif disclosure is None and report is None:\n"
        "        edit_guards.disclose(captured)\n"
        "    facts = history.scan_auto_facts(package)\n"
        "    rows = component_rows(\n"
        "        package,\n"
        "        [glyph_copies.Row(base, target) for target, base in pairs],\n"
        "        allow_rebuild=allow_rebuild,\n"
        "    )\n"
        "    if kept is not None:\n"
        "        kept.extend(row.note for row in rows if row.note)\n"
        "    pairs = [(r.target, r.source) for r in rows if not r.note]\n"
        "    existing = [(t, b) for t, b in pairs if package.findName(t) is not None]\n"
        "    steps = prepare(package, existing, allow_rebuild=allow_rebuild) if existing else []\n"
        "    specs = [\n"
        "        glyph_creation.NewGlyph(\n"
        "            target,\n"
        "            tuple(\n"
        "                (str(m), float(package.findName(base).findLayer(m).advanceWidth))\n"
        "                for m in package.masters\n"
        "            ),\n"
        "            (unicodes or {}).get(target, ()),\n"
        "            components=tuple(\n"
        "                glyph_creation.Part(str(m), base) for m in package.masters\n"
        "            ),\n"
        "        )\n"
        "        for target, base in pairs\n"
        "        if package.findName(target) is None\n"
        "    ]\n"
        "    groups = group_plan(package, pairs)\n"
        "    created = glyph_creation.create_glyphs(\n"
        "        package, specs, title, facts, allow_rebuild=allow_rebuild\n"
        "    )\n"
        "    names = [str(glyph.name) for glyph in created.glyphs]\n"
        '    created_text = "new glyphs that exist now: " + ", ".join(names) if names else ""\n'
        "    diagnostics = list(created.mismatches)\n"
        "    if report is not None:\n"
        "        report.extend(([created_text] if created_text else []) + diagnostics)\n"
        "    if diagnostics and not allow_rebuild:\n"
        '        raise RuntimeError("; ".join([*diagnostics, created_text, history.UNDO_HINT]))\n'
        "    if not steps and not any(groups.values()):\n"
        "        return len(specs) * len(package.masters)\n"
        "    if steps:\n"
        "        edited = list(dict.fromkeys(target for target, _, _, _ in steps))\n"
        "        glyphs = [package.findName(target) for target in edited]\n"
        "        layers = [\n"
        "            package.findName(target).findLayer(master) for target, master, _, _ in steps\n"
        "        ]\n"
        "        layers = [layer for layer in layers if layer is not None and not layer.isNull]\n"
        "    else:\n"
        "        memberships = [\n"
        "            (target, master)\n"
        "            for target, _ in pairs\n"
        "            for master, changes in groups.items()\n"
        "            if any(\n"
        "                (target in package.kerning(master).groups[name][0])\n"
        "                != (target in value[0])\n"
        "                for name, value in changes.items()\n"
        "            )\n"
        "        ]\n"
        "        edited = list(dict.fromkeys(target for target, _ in memberships))\n"
        "        glyphs = [package.findName(target) for target in edited]\n"
        "        layers = [\n"
        "            package.findName(target).findLayer(master) for target, master in memberships\n"
        "        ]\n"
        "        layers = [layer for layer in layers if layer is not None and not layer.isNull]\n"
        "    retain = [\n"
        "        item\n"
        "        for layer in layers\n"
        "        for shape in writer.components(layer)\n"
        "        for item in history.component_history(shape)\n"
        "    ]\n"
        "    container = package.kerningContainer()\n"
        "    retain.extend([package, package.mastersContainer(), container])\n"
        "    made, written = [], []\n"
        "\n"
        "    def mutate() -> list[Any]:\n"
        "        package.checkInitHistoryState(0)\n"
        "        container.checkInitHistoryState(0)\n"
        "        for target, master, component, width in steps:\n"
        "            glyph = package.findName(target)\n"
        "            if glyph is None:\n"
        '                raise ValueError(f"{target}: target changed; Preview again.")\n'
        "            layer = glyph.findLayer(master)\n"
        "            if layer is None or layer.isNull:\n"
        "                layer = glyph.findLayerCreate(master)\n"
        "                made.append(layer)\n"
        "            if replace_contours:\n"
        "                for shape in list(layer.shapes):\n"
        "                    if shape.isComponent or bool(shape.contours):\n"
        "                        layer.removeShape(shape)\n"
        "                if clear_anchors:\n"
        "                    layer.clearAnchors()\n"
        "            else:\n"
        "                for shape in list(writer.components(layer)):\n"
        "                    layer.removeShape(shape)\n"
        "            component = component_creation.add_component(layer, component)\n"
        "            writer.refreshed(component)\n"
        "            layer.advanceWidth = width\n"
        "            layer.changed()\n"
        "            if layer.update() is False:\n"
        '                raise RuntimeError(f"FontLab could not update {target} · {master}.")\n'
        "            written.append((layer, component, width))\n"
        "        for master, changes in groups.items():\n"
        "            for name, value in changes.items():\n"
        "                package.kerning(master).groups[name] = value\n"
        "        return made\n"
        "\n"
        "    def read_back() -> list[str]:\n"
        "        missed = [\n"
        "            str(layer.name)\n"
        "            for layer, component, width in written\n"
        "            if component not in layer.shapes or layer.advanceWidth != width\n"
        "        ]\n"
        "        for master, changes in groups.items():\n"
        "            now = dict(package.kerning(master).groups.items())\n"
        "            missed.extend(\n"
        '                f"{master}: class {name}"\n'
        "                for name, value in changes.items()\n"
        "                if name not in now or (list(now[name][0]), now[name][1]) != value\n"
        "            )\n"
        "        return missed\n"
        "\n"
        "    try:\n"
        "        result = history.commit(\n"
        "            title,\n"
        "            layers,\n"
        "            glyphs,\n"
        "            mutate,\n"
        '            operation="geometry" if steps else "metadata",\n'
        "            facts=history.scan_auto_facts(package),\n"
        "            allow_bases=allow_rebuild,\n"
        "            retain=retain,\n"
        "            read_back=read_back,\n"
        "        )\n"
        "    except (ValueError, RuntimeError, TimeoutError) as error:\n"
        "        if names:\n"
        "            raise history.PartialWriteError(\n"
        "                title,\n"
        "                [\n"
        "                    error,\n"
        "                    RuntimeError(created_text),\n"
        "                    *(RuntimeError(text) for text in diagnostics),\n"
        "                ],\n"
        "            ) from error\n"
        "        raise\n"
        "    if result.mismatches:\n"
        "        raise RuntimeError(\n"
        '            "; ".join(\n'
        "                [*diagnostics, *result.mismatches, created_text, history.UNDO_HINT]\n"
        "            )\n"
        "        )\n"
        "    return len(steps) + len(specs) * len(package.masters)\n"
        "\n"
        "\n"
        "def plan_key(package: Any, rows: list[glyph_copies.Row]) -> tuple:\n"
        '    """Bind Preview and confirmation to the font, rows and target shape identities."""\n'
        "    return (\n"
        "        int(package.id),\n"
        "        tuple(str(m) for m in package.masters),\n"
        "        tuple(\n"
        "            (\n"
        "                row.source,\n"
        "                row.target,\n"
        "                row.note,\n"
        "                tuple(\n"
        "                    (\n"
        "                        str(layer.name),\n"
        "                        tuple(int(shape.id) for shape in layer.shapes),\n"
        "                        len(layer.anchors),\n"
        "                    )\n"
        "                    for layer in package.findName(row.target).layers\n"
        "                )\n"
        "                if row.target and package.findName(row.target) is not None\n"
        "                else (),\n"
        "            )\n"
        "            for row in rows\n"
        "        ),\n"
        "    )\n",
    ),
    "Placeholder Glyphs": (
        "Scripts/Contours/Placeholder Glyphs.py",
        "304fb15b82621372041cf84a68a0ca332f8a99af2a40c9329b8297b8b3bf0d62",
        (
            "NAME",
            "UNI",
            "UNSAFE",
            "Entry",
            "Row",
            "check_text",
            "char_name",
            "code_of",
            "parse",
            "font_codes",
            "plan",
            "gate",
            "create",
        ),
        'NAME = re.compile(r"[A-Za-z_.][A-Za-z0-9_.-]*")\n'
        "\n"
        "\n"
        'UNI = re.compile(r"uni([0-9A-F]{4})|u([0-9A-F]{5,6})")\n'
        "\n"
        "\n"
        "UNSAFE = (\n"
        '    ("\\x00", "NUL"),\n'
        '    ("\\u00a0", "no-break space"),\n'
        '    ("\\u2028", "line separator"),\n'
        '    ("\\u2029", "paragraph separator"),\n'
        ")  # characters that FontLab's text conversion can change\n"
        "\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Entry:\n"
        '    """One typed token, the glyph name it stands for, and a parse problem (or "")."""\n'
        "\n"
        "    token: str\n"
        "    name: str\n"
        '    problem: str = ""\n'
        "\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class Row:\n"
        '    """One planned glyph: code point to assign (or None), note, problem (set: skipped).\n'
        "\n"
        "    ``rebuild``: automatic glyphs that FontLab may rebuild when the glyph\n"
        "    appears (``glyph_creation.auto_candidates``).\n"
        '    """\n'
        "\n"
        "    name: str\n"
        "    code: int | None\n"
        '    note: str = ""\n'
        '    problem: str = ""\n'
        "    rebuild: tuple[str, ...] = ()\n"
        "\n"
        "\n"
        "def check_text(text: str) -> None:\n"
        '    """Raise ValueError when ``text`` holds a character that FontLab can change."""\n'
        "    found = [label for char, label in UNSAFE if char in text]\n"
        "    if found:\n"
        "        raise ValueError(\n"
        '            "Refused: the text holds "\n'
        '            + ", ".join(found)\n'
        '            + ". FontLab\'s text conversion can change it; "\n'
        '            "remove it and type the names again."\n'
        "        )\n"
        "\n"
        "\n"
        "def char_name(char: str) -> str:\n"
        '    """Return uniXXXX for a BMP character, uXXXXX above it."""\n'
        "    code = ord(char)\n"
        '    return f"uni{code:04X}" if code <= 0xFFFF else f"u{code:X}"\n'
        "\n"
        "\n"
        "def code_of(name: str) -> int | None:\n"
        '    """Return the code point that a uniXXXX / uXXXXX name stands for, else None.\n'
        "\n"
        "    Surrogates and values above U+10FFFF are not characters: None.\n"
        '    """\n'
        "    match = UNI.fullmatch(name)\n"
        "    if match is None:\n"
        "        return None\n"
        "    code = int(match.group(1) or match.group(2), 16)\n"
        "    return None if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF else code\n"
        "\n"
        "\n"
        "def parse(text: str) -> list[Entry]:\n"
        '    """Return one Entry per token. A single non-ASCII character becomes uniXXXX."""\n'
        "    check_text(text)\n"
        "    entries: list[Entry] = []\n"
        "    seen: set[str] = set()\n"
        '    for token in re.split(r"[\\s,]+", text.strip()):\n'
        "        if not token:\n"
        "            continue\n"
        "        name = char_name(token) if len(token) == 1 and not token.isascii() else token\n"
        "        if not NAME.fullmatch(name):\n"
        '            entries.append(Entry(token, name, "invalid name"))\n'
        "        elif name in seen:\n"
        '            entries.append(Entry(token, name, "repeated"))\n'
        "        else:\n"
        "            seen.add(name)\n"
        "            entries.append(Entry(token, name))\n"
        "    return entries\n"
        "\n"
        "\n"
        "def font_codes() -> dict[int, str]:\n"
        '    """Return {code point: glyph name} from the font-owned glyph records."""\n'
        "    from fly import ap\n"
        "\n"
        "    font = ap.fontlab.CurrentFont()\n"
        "    if font is None:\n"
        "        return {}\n"
        "    return {\n"
        "        int(code): str(record.name)\n"
        "        for record in font.glyphs\n"
        "        for code in record.unicodes\n"
        "    }\n"
        "\n"
        "\n"
        "def plan(\n"
        "    entries: Sequence[Entry], exists: Callable[[str], bool], codes: dict[int, str]\n"
        ") -> list[Row]:\n"
        '    """Return one Row per entry: skip problems and existing glyphs, never reuse a code point."""\n'
        "    rows: list[Row] = []\n"
        "    for entry in entries:\n"
        "        if entry.problem:\n"
        "            rows.append(Row(entry.name, None, problem=entry.problem))\n"
        "            continue\n"
        "        if exists(entry.name):\n"
        '            rows.append(Row(entry.name, None, problem="exists"))\n'
        "            continue\n"
        "        code = code_of(entry.name)\n"
        "        if code is None:\n"
        "            rows.append(Row(entry.name, None))\n"
        "        elif code in codes:\n"
        "            rows.append(\n"
        '                Row(entry.name, None, f"U+{code:04X} is on {codes[code]}: not assigned")\n'
        "            )\n"
        "        else:\n"
        '            rows.append(Row(entry.name, code, f"U+{code:04X}"))\n'
        "    return rows\n"
        "\n"
        "\n"
        "def gate(\n"
        "    package: Any, rows: Sequence[Row], facts: Any, allow_rebuild: bool\n"
        ") -> list[Row]:\n"
        '    """Mark each ready row that can make FontLab rebuild automatic glyphs.\n'
        "\n"
        "    The row gets ``rebuild``; without ``allow_rebuild`` its problem is the\n"
        '    "may rebuild auto ..." note, so it is skipped.\n'
        '    """\n'
        "    import fly.ap.glyphs.creation as glyph_creation  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "\n"
        "    found = glyph_creation.auto_candidates(\n"
        "        package, facts, [r.name for r in rows if not r.problem]\n"
        "    )\n"
        "    gated = []\n"
        "    for row in rows:\n"
        "        owners = () if row.problem else found.get(row.name, ())\n"
        "        problem = (\n"
        "            glyph_creation.rebuild_note(owners)\n"
        "            if owners and not allow_rebuild\n"
        "            else row.problem\n"
        "        )\n"
        "        gated.append(Row(row.name, row.code, row.note, problem, owners))\n"
        "    return gated\n"
        "\n"
        "\n"
        "def create(\n"
        "    package: Any,\n"
        "    rows: Sequence[Row],\n"
        "    advance: int,\n"
        "    facts: Any,\n"
        "    allow_rebuild: bool = False,\n"
        ") -> dict[str, Any]:\n"
        '    """Create every ready row as an empty glyph on all masters with FontLab\'s Add Glyph command.\n'
        "\n"
        '    Return ``{"glyphs", "layers", "codes", "mismatches"}``. Nothing ready\n'
        "    returns zeros and makes no native call. A name or code point that is\n"
        "    taken now, an unconsented rebuild, a code point without an active Font\n"
        "    window or with an open Glyph window, queued ids are disclosed with their possible date changes. A failure after the first glyph exists\n"
        "    raises RuntimeError that names the new glyphs.\n"
        '    """\n'
        "    import fly.ap.core.edit_guards as edit_guards  # noqa: PLR0402 - fontlabapp.__getattr__ is native\n"
        "    import fly.ap.glyphs.copies as glyph_copies  # noqa: PLR0402\n"
        "    import fly.ap.glyphs.creation as glyph_creation  # noqa: PLR0402\n"
        "    from fly import ap\n"
        "\n"
        "    ready = [r for r in rows if not r.problem]\n"
        "    coded = [r for r in ready if r.code is not None]\n"
        "    masters = list(package.masters)\n"
        "    if not ready:\n"
        '        return {"pending_updates": (), "pending_note": "", "glyphs": 0, "layers": 0, "codes": 0, "mismatches": []}\n'
        "    if coded:\n"
        "        edit_guards.require_selection_window(int(package.id))\n"
        "        edit_guards.require_no_editors()\n"
        "    taken = font_codes()\n"
        "    for row in ready:\n"
        "        if row.code is not None and row.code in taken:\n"
        "            raise ValueError(\n"
        '                f"Refused: U+{row.code:04X} is on {taken[row.code]} now. Check the list again."\n'
        "            )\n"
        "    specs = [\n"
        "        glyph_creation.NewGlyph(\n"
        "            row.name,\n"
        "            tuple((m, advance) for m in masters),\n"
        "            () if row.code is None else (row.code,),\n"
        "        )\n"
        "        for row in ready\n"
        "    ]\n"
        "\n"
        "    def read_back() -> list[str]:\n"
        "        font = ap.fontlab.CurrentFont()\n"
        "        found = (\n"
        "            {int(record.id): record for record in font.glyphs}\n"
        "            if coded and font is not None\n"
        "            else {}\n"
        "        )\n"
        "        problems = []\n"
        "        for row in ready:\n"
        "            glyph = package.findName(row.name)\n"
        "            if glyph is None:\n"
        '                problems.append(f"{row.name}: missing after the write")\n'
        "                continue\n"
        "            for master in masters:\n"
        "                layer = glyph.findLayer(master)\n"
        "                width = (\n"
        "                    glyph_copies.half_up(layer.advanceWidth)\n"
        "                    if layer is not None and not layer.isNull\n"
        "                    else None\n"
        "                )\n"
        "                if width != advance:\n"
        "                    problems.append(\n"
        '                        f"{row.name} · {master}: width {width}, planned {advance}"\n'
        "                    )\n"
        "            if row.code is not None:\n"
        "                record = found.get(int(glyph.fgGlyphId))\n"
        "                codes = list(record.unicodes) if record is not None else []\n"
        "                if codes != [row.code]:\n"
        "                    problems.append(\n"
        '                        f"{row.name}: Unicode is {codes}, planned U+{row.code:04X}"\n'
        "                    )\n"
        "        return problems\n"
        "\n"
        "    done = glyph_creation.create_glyphs(\n"
        "        package, specs, TITLE, facts, read_back=read_back, allow_rebuild=allow_rebuild\n"
        "    )\n"
        '    return {"pending_note": done.pending_note, \n'
        '        "pending_updates": done.pending_updates,\n'
        '        "glyphs": len(ready),\n'
        '        "layers": len(ready) * len(masters),\n'
        '        "codes": len(coded),\n'
        '        "mismatches": list(done.mismatches),\n'
        "    }\n",
    ),
}
