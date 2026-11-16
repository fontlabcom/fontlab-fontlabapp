# this_file: tests/_component_audit_originals.py
"""The Scriptmix scripts Component Audit absorbs: file hashes and verbatim pure functions.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show 25c86b4:<path>``), not retyped.
Each entry is ``(path, sha256 of the whole file, names, source of those definitions)``; the parity tests
compare the ported bodies with these (AST equality). Scripts whose only code is their window class or a
launcher of a shared App panel have empty names; their behaviour is covered by tab tests of the reused
App calculations (``components.inspect.model``, ``components.graph``, ``masters.layers.brackets``).
"""

ORIGINALS = {
    "Components Report": (
        "Scripts/Components/Report.py",
        "dbbd09a48862c959febd88a34868d22c1037f2e3b7c5cfa24879be6ead6590fa",
        (),
        "",
    ),
    "Where Used": (
        "Scripts/Components/Where Used.py",
        "e0f97c011212d6ccedae4c14c19e6d0ae16a3d5f375d729b63e531595d6472b3",
        (),
        "",
    ),
    "Missing Bases": (
        "Scripts/Components/Missing Bases.py",
        "1fccc9cd53cef65a37cfbbb83055135b5a69225162359ce01d0c37d86ba6c3fa",
        (),
        "",
    ),
    "Nested Finder": (
        "Scripts/Components/Nested Finder.py",
        "0ae15ec6b25aefba241459e79226cc7ecce0a890a60f63a626215741a36365d9",
        ("nested_changes",),
        "def nested_changes(\n"
        "    package: Any, glyph: Any, layer: Any, master: str\n"
        ") -> list[component_writer.Change]:\n"
        '    """One row per component whose base glyph has components on this master."""\n'
        "    rows: list[component_writer.Change] = []\n"
        "    for shape in component_writer.components(layer):\n"
        "        contours, inner = component_writer.part_counts(package, shape, master)\n"
        "        if not inner:\n"
        "            continue\n"
        "        source = package.findName(component_writer.base_of(shape))\n"
        "        base = component_writer.layer_of(\n"
        "            source, shape.shapeData.componentLayer or master\n"
        "        )\n"
        "        names = (\n"
        '            " + ".join(\n'
        "                component_writer.base_of(s) for s in component_writer.components(base)\n"
        "            )\n"
        "            if base\n"
        '            else ""\n'
        "        )\n"
        "        why = component_writer.copy_problem(\n"
        "            package, (glyph.name, master), shape, master\n"
        "        )\n"
        "        if why:\n"
        "            rows.append(\n"
        "                component_writer.Change(\n"
        '                    component_writer.base_of(shape), names, "", problem=why\n'
        "                )\n"
        "            )\n"
        "            continue\n"
        "        rows.append(\n"
        "            component_writer.Change(\n"
        "                component_writer.base_of(shape),\n"
        "                names,\n"
        "                component_writer.parts_text(contours, inner),\n"
        "                shape.id,\n"
        "            )\n"
        "        )\n"
        "    return rows\n",
    ),
    "Component Graph": (
        "Scripts/Components/Component Graph.py",
        "890762f22f39f64455ec29dcd0fe3a3bd919266d6b62de3026e9daab525d4725",
        (),
        "",
    ),
    "Bracket Layers and Components": (
        "Scripts/Reports/Bracket Layers and Components.py",
        "9e1fd16e500ad842265491d162c751e258c4d66dd498adc8c54c42826b43e93f",
        (),
        "",
    ),
}
