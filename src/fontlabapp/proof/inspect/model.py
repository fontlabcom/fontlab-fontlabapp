# this_file: src/fontlabapp/proof/inspect/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only outline, advance-only text and word-filter helpers for Proof tools.

Native modules load only inside the access functions; importing this module is host-free."""

from typing import Any

from fontlabapp import _native
from fontlabapp.core.scripting import names_font_glyphs, names_selected_names


def layer_path(layer: Any) -> Any:
    """The layer's outline as one QPainterPath in font units (y up), components placed."""
    QtCore, QtGui = (_native("PythonQt").QtCore, _native("PythonQt").QtGui)
    path = QtGui.QPainterPath()
    path.setFillRule(QtCore.Qt.WindingFill)
    for shape in layer.shapes:
        for part in (shape.closedPath, shape.openedPath):
            if part is not None and (not part.isEmpty()):
                path.addPath(shape.transform.map(part))
    return path


def parse_text(text: str, cmap: dict[int, str], names: set[str]) -> list[str | None]:
    """[glyph name or None] for the text; '/name ' or '/name/' addresses glyphs by name."""
    out, i = ([], 0)
    while i < len(text):
        char = text[i]
        if char == "/" and i + 1 < len(text) and (text[i + 1] not in " /"):
            end = i + 1
            while end < len(text) and text[end] not in " /":
                end += 1
            name = text[i + 1 : end]
            out.append(name if name in names else None)
            i = end + 1 if end < len(text) and text[end] == " " else end
            continue
        out.append(cmap.get(ord(char)))
        i += 1
    return out


def parse_sizes(text: str) -> list[float]:
    """Keep ordered pixel sizes between 4 and 400, ignoring invalid tokens."""
    sizes = []
    for part in text.replace(",", " ").split():
        try:
            size = float(part)
        except ValueError:
            continue
        if 4 <= size <= 400:
            sizes.append(size)
    return sizes


def glyph_run(
    package: Any, glyph_names: list[str | None], master: str
) -> list[tuple[Any, float]]:
    """[(path or None, advance)] in font units for one master; None marks a missing glyph."""
    cache, out = ({}, [])
    for name in glyph_names:
        if name is None:
            out.append((None, package.upm * 0.5))
            continue
        if name not in cache:
            glyph = package.findName(name)
            layer = (
                glyph.findLayer(master)
                if glyph is not None and not glyph.isNull
                else None
            )
            cache[name] = (
                (layer_path(layer), layer.advanceWidth)
                if layer is not None and (not layer.isNull)
                else (None, package.upm * 0.5)
            )
        out.append(cache[name])
    return out


def metrics(package: Any) -> tuple[float, float]:
    """(descender, ascender) of the font; widened to the drawn outlines so accents fit."""
    return (package.descender_value, package.ascender_value)


def cased(word: str, case: str) -> str:
    """Apply the original proof case choice to one word."""
    return (
        word.upper()
        if case == "UPPERCASE"
        else word.capitalize()
        if case == "Capitalised"
        else word
    )


def find_words(
    words: list[str],
    available: set[str],
    case: str = "lowercase",
    must: str = "",
    only: str = "",
    min_len: int = 3,
    max_len: int = 12,
) -> list[str]:
    """Words (in the chosen case) that the font can set and that satisfy the letter filters."""
    must = must.lower()
    allowed = set(only.lower())
    out = []
    for word in words:
        if not min_len <= len(word) <= max_len:
            continue
        if must and (not all(letter in word for letter in must)):
            continue
        if allowed and (not set(word) <= allowed):
            continue
        text = cased(word, case)
        if all(char in available for char in text):
            out.append(text)
    return out


def font_maps() -> tuple[dict[int, str], set[str]]:
    """Read first-encoded-name wins and all unencoded names in font order."""
    cmap, names = ({}, set())
    for name, codes in names_font_glyphs():
        names.add(name)
        for code in codes:
            cmap.setdefault(code, name)
    return (cmap, names)


def character_map() -> dict[int, str]:
    """Read the current font's first-name-wins Unicode map."""
    return font_maps()[0]


def font_chars() -> set[str]:
    """Read exactly the characters encoded by the current font."""
    return {chr(code) for code in character_map()}


def selected_glyphs(package: Any) -> list[Any]:
    """Read selection in font order with current-glyph fallback; never change it."""
    if package is None:
        return []
    glyphs = [package.findName(name) for name in names_selected_names()]
    return [glyph for glyph in glyphs if glyph is not None and (not glyph.isNull)]


ENGLISH = "\nabout above across actually adjust after again against agree ahead album alive allow almost alone along already\nalways amazing amber among amount anchor ancient angle animal answer anything apart appear apple arch archive area\nargue armour around arrive artist aspect assume attack audience author autumn average avoid awake aware balance\nbanner barely basket battle beach beauty become before begin behind believe below beside better beyond bicycle\nbinary bishop black blanket blend block blossom board bold border bottle bottom bounce bracket branch brave bread\nbreeze bridge bright bring broad bronze brother brought brush bubble budget build bundle burden butter button\ncabin cactus calendar calm camera candle canvas capital captain carbon careful carpet carry castle casual catalog\ncattle caught ceiling centre century chain chalk chamber change chapter charm cheap check cheese cherry chimney\nchoice chorus circle citizen classic clever client cliff climate clock closer cloud coast coffee collect colour\ncolumn comfort common compact complex concert copper corner cotton county couple course craft crane crisp crowd\ncrystal culture current curtain curve cycle daily damage dance danger dawn debate decade decide deep define degree\ndelicate demand design detail diamond differ dinner direct dizzy doctor dolphin double dozen draft dragon drawer\ndream drift drink drive during eager early earth easily editor effort eight either elbow elegant eleven empire\nempty enable energy engine enjoy enough entire equal escape essay estate evening event every exact example excuse\nexhibit expect expert explain extra fabric factor fairly family famous fancy farmer fashion father favour feather\nfeature fellow fence fever fiction field figure final finger finish flavour flight flower fluent focus folder\nfollow forest forget formal format fortune forward fossil fountain fragile frame freedom frozen future galaxy\ngarden gather gentle giant ginger glance global glove golden grammar grape gravity grocer guitar habit hammer handle\nhappen harbour harvest health heavy height helmet hidden history hobby honest horizon humble hunger husband\niceberg ignore image impact indeed inside invite island jacket jaguar jazz jelly jewel jigsaw journey judge juice\njumble jungle junior justify kayak keeper kernel kettle keyboard kidney kingdom kitchen kitten knight knock knowledge\nlabel ladder laptop large later laughter lavender layer leader leather lemon letter level liberty light limit\nliquid little lizard lobster local logic lonely lumber luxury lyrics machine magnet maize making manner maple marble\nmarket master matter meadow medium melody memory method middle minute mirror mixture modern moment monkey mountain\nmuffin museum music mystery napkin narrow nature nearby needle nephew nervous network neutral nobody normal notice\nnovel number object obtain ocean office olive onion opinion orange orbit orchard origin outfit oxygen oyster paddle\npalace panther paper parade parcel parrot pattern peanut pencil people pepper perfect phrase piano picnic pillow\npilot planet plastic pocket poetry police polite powder prize problem public puzzle pyramid quality quantum quarter\nqueen quick quiet quilt quite quiver quote rabbit radio raven razor ready reason record region relax remote rhythm\nribbon riddle river rocket rubber rugby saddle salmon sample scarf school science season second secret seven\nshadow shelter signal silver simple sketch sleepy slogan smooth snack soccer soldier sphinx spirit square squeeze\nsquirrel stable street string studio subject sudden summer sunset survey switch symbol system table tackle talent\ntemple thank theory thirty thumb ticket timber tobacco toward travel treaty trophy truly tunnel twelve twenty\ntypical umbrella uncle under unique update upward useful vacuum valley velvet verb victory village violin virtual\nvisual vivid voice volcano voyage waffle walnut wander warmth weather welcome whisky window winter wizard wonder\nworry wrist writer yacht yellow yesterday yogurt young youth zebra zero zigzag zipper zombie zone\n"
LATIN = "\nab accusamus ad adipiscing aliqua aliquam aliquip amet animi anim aute beatae blanditiis commodo consectetur\nconsequat cupidatat culpa deserunt dicta dignissim dolor dolore dolorem duis eiusmod elit enim eos esse est\neiusmod excepteur exercitation facilis fugiat fugit harum id illum incididunt ipsa ipsum irure iusto labore\nlaboris laborum lorem magna minim mollit nam natus nemo neque nisi nostrud nulla obcaecati occaecat officia omnis\npariatur perferendis placeat porro proident quam quas qui quia quis quod ratione recusandae reprehenderit rerum\nsapiente sed sint sit sunt tempor tempora tenetur ullamco ut velit veniam vero vitae voluptate voluptas\n"
WORDS = sorted(set(ENGLISH.split()) | set(LATIN.split()))
CASES = ["lowercase", "Capitalised", "UPPERCASE"]


def path_span(path: Any, advance: float) -> tuple[float, float]:
    """Include full overhangs and the advance box in horizontal fitting."""
    left, right = (min(0.0, advance), max(0.0, advance))
    if path is not None and (not path.isEmpty()):
        box = path.boundingRect()
        left, right = (min(left, box.left()), max(right, box.right()))
    return (left, right)


def grid_scale(cells: list, frame: tuple[float, float], cell: float) -> float:
    """Use one scale for every master and fit even wide composites/overhangs."""
    widest = max(
        (
            path_span(path, advance)[1] - path_span(path, advance)[0]
            for _, row in cells
            for _, path, advance in row
        ),
        default=1.0,
    )
    return cell * 0.88 / max(1.0, frame[1] - frame[0], widest)
