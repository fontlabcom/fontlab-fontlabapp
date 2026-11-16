# this_file: tests/_font_info_records.py
"""The three Scriptmix Font Info ``glyph_records`` copies, extracted verbatim for equivalence tests.

Generated with ``ast`` from Scriptmix origin/main 25c86b4 (``git show origin/main:Scripts/Font Info/<tool>.py``),
not retyped. ``tests/test_studio_font_audit.py`` checks each body against its SHA-256 and runs it
against the same fake font as ``fontlabapp.studios._records.glyph_records``.
"""

COPIES = {
    'Calculate Vertical Metrics': (
        36,
        '17150b933eb47c4c1c86395476a835f6df3a6c22c98fb54d5811fb6a6b49e852',
        'def glyph_records(package: Any) -> Any:\n'
        '    """Read all Unicode assignments, including secondary encodings, in font order."""\n'
        '    FL = ap.FL\n'
        '\n'
        '    active = current_package()\n'
        '    if active is None or active.id != package.id:\n'
        '        msg = "Activate the original font and reopen this tool."\n'
        '        raise ValueError(msg)\n'
        '    legacy = FL.fl.font\n'
        '    return [\n'
        '        (legacy[i].name, list(package.findName(legacy[i].name).fgGlyph.unicodes))\n'
        '        for i in range(len(legacy))\n'
        '    ]'
    ),
    'Glyph Order Preview and Export': (
        48,
        '17150b933eb47c4c1c86395476a835f6df3a6c22c98fb54d5811fb6a6b49e852',
        'def glyph_records(package: Any) -> Any:\n'
        '    """Read all Unicode assignments, including secondary encodings, in font order."""\n'
        '    FL = ap.FL\n'
        '\n'
        '    active = current_package()\n'
        '    if active is None or active.id != package.id:\n'
        '        msg = "Activate the original font and reopen this tool."\n'
        '        raise ValueError(msg)\n'
        '    legacy = FL.fl.font\n'
        '    return [\n'
        '        (legacy[i].name, list(package.findName(legacy[i].name).fgGlyph.unicodes))\n'
        '        for i in range(len(legacy))\n'
        '    ]'
    ),
    'Unicode Ranges and Codepages': (
        47,
        '17150b933eb47c4c1c86395476a835f6df3a6c22c98fb54d5811fb6a6b49e852',
        'def glyph_records(package: Any) -> Any:\n'
        '    """Read all Unicode assignments, including secondary encodings, in font order."""\n'
        '    FL = ap.FL\n'
        '\n'
        '    active = current_package()\n'
        '    if active is None or active.id != package.id:\n'
        '        msg = "Activate the original font and reopen this tool."\n'
        '        raise ValueError(msg)\n'
        '    legacy = FL.fl.font\n'
        '    return [\n'
        '        (legacy[i].name, list(package.findName(legacy[i].name).fgGlyph.unicodes))\n'
        '        for i in range(len(legacy))\n'
        '    ]'
    ),
}
