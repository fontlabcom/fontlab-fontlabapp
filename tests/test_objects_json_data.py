# this_file: tests/test_objects_json_data.py
"""Offline tests of fontlabapp.objects.json_data (FontLab 9.1 object JSON).

The pure envelope layer runs as is. Native calls use fakes: a fake
``QByteArray`` type, a fake ``flModelProducer`` whose decode refuses anything
but that type (Python bytes crash FontLab 9.1.9812), a fake clipboard and
fake glyphs and layers. Offline results are not native FontLab acceptance.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import fontlabapp.core.history.glyphs as history
import fontlabapp.glyphs.creation as creation
from fontlabapp.objects import json_data as jd

MODULE = Path(jd.__file__)
HEAD = {"dataType": "com.fontlab.objects", "upm": 1000, "packageId": 7}


def glyph(name="o", unicode="006f", layers=(("Regular", 500),)):
    return {
        "name": name,
        "unicode": unicode,
        "lastModified": 0,
        "openTypeGlyphClass": 0,
        "colorFlag": -1,
        "layers": [
            {"name": n, "advanceWidth": w, "elements": [{"id": 1}], "flags": 0}
            for n, w in layers
        ],
    }


def envelope(**payload):
    return {**HEAD, **payload}


class QBA:
    """Fake PythonQt QByteArray."""

    def __init__(self, raw=b""):
        self.raw = bytes(raw)

    def data(self):
        return self.raw


class Producer:
    """Fake flModelProducer: decode accepts only QBA, like the safe native call."""

    def __init__(self, result=None, decoder=None):
        self.result, self.decoder, self.decoded, self.exported = result, decoder, [], []

    def getObjectsFromJsonData(self, data):  # noqa: N802 - native name
        if type(data) is not QBA:
            raise AssertionError(
                f"native decode got {type(data).__name__}, not QByteArray"
            )
        self.decoded.append(json.loads(data.raw))
        return self.decoder(data.raw) if self.decoder else self.result

    def getClipboardDataJson(self, package_id, upm, objects):  # noqa: N802 - native name
        self.exported.append((package_id, upm, objects))
        return QBA(json.dumps(envelope(glyph=glyph())).encode())


class Mime:
    def __init__(self, formats=None, text=None):
        self.formats, self.text_value = dict(formats or {}), text

    def setData(self, kind, data):  # noqa: N802
        self.formats[kind] = data

    def setText(self, text):  # noqa: N802
        self.text_value = text

    def hasFormat(self, kind):  # noqa: N802
        return kind in self.formats

    def data(self, kind):
        return self.formats[kind]

    def hasText(self):  # noqa: N802
        return self.text_value is not None

    def text(self):
        return self.text_value


class Clipboard:
    def __init__(self, mime=None):
        self.mime = mime

    def setMimeData(self, mime):  # noqa: N802
        self.mime = mime

    def mimeData(self):  # noqa: N802
        return self.mime


def fake_qt(clipboard=None):
    board = clipboard or Clipboard()
    return SimpleNamespace(
        QtCore=SimpleNamespace(QByteArray=QBA, QMimeData=Mime),
        QtGui=SimpleNamespace(QApplication=SimpleNamespace(clipboard=lambda: board)),
        board=board,
    )


class Shape:
    def __init__(self, label="s"):
        self.label, self.contours = label, []

    def addContours(self, contours, flag):  # noqa: N802
        self.contours += list(contours)


def fake_fl(producer):
    return SimpleNamespace(flModelProducer=producer, flShape=Shape)


class Layer:
    def __init__(self, name="Regular", shapes=()):
        self.name, self.shapes, self.added = name, list(shapes), []

    def addShape(self, shape):  # noqa: N802
        self.added.append(shape)


class Glyph:
    def __init__(self, name, layers=()):
        self.name, self.layers = name, list(layers)

    def findLayer(self, name):  # noqa: N802
        return next(x for x in self.layers if x.name == name)


class Package:
    def __init__(self, names=(), masters=("Regular",), codes=None):
        self.names, self.masters, self.id, self.upm = set(names), list(masters), 7, 1000
        self.codes = dict(codes or {})

    def findUnicode(self, code):  # noqa: N802
        name = self.codes.get(code)
        return None if name is None else SimpleNamespace(name=name)

    def findName(self, name):  # noqa: N802
        return object() if name in self.names else None

    def addGlyph(self, *_):  # noqa: N802
        raise AssertionError("addGlyph must never be called")


# --- envelope shapes -------------------------------------------------------


@pytest.mark.parametrize("kind", jd.KINDS)
def test_envelope_when_single_item_then_round_trips_with_singleton_key(kind) -> None:
    data = envelope(**{kind: {"name": "x"}})
    env = jd.Envelope.parse(json.dumps(data))
    assert env.items == ((kind, {"name": "x"}),)
    assert (env.upm, env.package_id) == (1000, 7)
    assert json.loads(env.to_bytes()) == data


def test_envelope_when_mixed_objects_then_round_trips_as_objects_list() -> None:
    data = envelope(
        objects=[{"glyph": glyph()}, {"layer": {"name": "Bold"}}, {"contour": {}}]
    )
    env = jd.Envelope.parse(json.dumps(data).encode())
    assert env.kinds() == ("glyph", "layer", "contour")
    assert env.glyph_names() == ("o",)
    assert jd.Envelope.parse(env.to_bytes()).to_dict() == data


def test_envelope_when_empty_then_has_no_payload_key() -> None:
    env = jd.Envelope.parse(HEAD)
    assert env.items == ()
    assert env.to_dict() == HEAD
    assert jd.describe(env) == ["No objects."]


def test_envelope_when_header_missing_and_extra_keys_then_kept() -> None:
    env = jd.Envelope.parse({"dataType": jd.DATA_TYPE, "future": 1, "glyph": glyph()})
    assert (env.upm, env.package_id) == (None, None)
    assert env.to_dict()["future"] == 1 and "upm" not in env.to_dict()
    assert jd.Envelope.parse(env) is env


def test_to_bytes_when_indent_then_pretty_utf8() -> None:
    env = jd.Envelope.parse(envelope(glyph=glyph(name="é")))
    raw = env.to_bytes(indent=2)
    assert "\n  " in raw.decode("utf-8") and "é" in raw.decode("utf-8")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\xff", "not UTF-8"),
        (b"not json", "not valid JSON"),
        ("[1]", "must be a JSON object, not list"),
        ({"dataType": "x"}, "dataType is 'x'"),
        (envelope(glyph={}, layer={}), "more than one payload key: glyph, layer"),
        (envelope(objects={}), '"objects" must be a list'),
        (envelope(objects=[{"glyph": {}, "layer": {}}]), "one key"),
        (envelope(objects=[{"font": {}}]), "kind 'font' is not one of"),
        (envelope(glyph=[]), "glyph must be a JSON object"),
        ({**envelope(glyph={}), "upm": "big"}, "upm must be a number"),
    ],
)
def test_parse_when_bad_data_then_value_error(data, message) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        jd.Envelope.parse(data)


# --- describe and edits ----------------------------------------------------


def test_describe_when_all_kinds_then_one_line_each() -> None:
    env = jd.Envelope.parse(
        envelope(
            objects=[
                {"glyph": glyph(layers=(("Regular", 500), ("Bold", 520.5)))},
                {"layer": {"name": "Bold", "advanceWidth": 600, "elements": []}},
                {"element": {"id": 3, "active": True}},
                {"contour": {"nodes": [1, 2]}},
            ]
        )
    )
    lines = jd.describe(env)
    assert (
        lines[0]
        == 'glyph "o" U+006F: "Regular" width 500, 1 element; "Bold" width 520.5, 1 element'
    )
    assert lines[1] == 'layer "Bold" width 600, 0 elements'
    assert lines[2] == "element id 3, active True"
    assert lines[3] == "contour with 2 nodes"


def test_unique_name_when_taken_then_next_free_suffix() -> None:
    assert jd.unique_name("a", set()) == "a"
    assert jd.unique_name("a", {"a", "a.1"}) == "a.2"


def test_rename_glyphs_when_mapping_or_callable_then_copies() -> None:
    env = jd.Envelope.parse(
        envelope(objects=[{"glyph": glyph("o")}, {"glyph": glyph("p")}])
    )
    mapped = jd.rename_glyphs(env, {"o": "o.alt"})
    assert mapped.glyph_names() == ("o.alt", "p")
    assert env.glyph_names() == ("o", "p"), "the original stays"
    assert jd.rename_glyphs(env, str.upper).glyph_names() == ("O", "P")


def test_unique_glyph_names_when_clash_then_renamed_and_reported() -> None:
    env = jd.Envelope.parse(
        envelope(objects=[{"glyph": glyph("o")}, {"glyph": glyph("o")}])
    )
    edited, renamed = jd.unique_glyph_names(env, {"o"})
    assert edited.glyph_names() == ("o.1", "o.2")
    assert renamed == {"o": "o.1"}


def test_filter_layers_when_names_then_keeps_only_those() -> None:
    env = jd.Envelope.parse(
        envelope(
            objects=[
                {"glyph": glyph(layers=(("A", 1), ("B", 2)))},
                {"layer": {"name": "A"}},
                {"layer": {"name": "C"}},
            ]
        )
    )
    edited = jd.filter_layers(env, ["B", "C"])
    assert [x["name"] for x in edited.items[0][1]["layers"]] == ["B"]
    assert [p["name"] for k, p in edited.items if k == "layer"] == ["C"]


def test_set_advance_width_when_named_layers_then_only_those_change() -> None:
    env = jd.Envelope.parse(
        envelope(
            objects=[
                {"glyph": glyph(layers=(("A", 1), ("B", 2)))},
                {"layer": {"name": "A", "advanceWidth": 5}},
            ]
        )
    )
    edited = jd.set_advance_width(env, 600, ["A"])
    assert [x["advanceWidth"] for x in edited.items[0][1]["layers"]] == [600, 2]
    assert edited.items[1][1]["advanceWidth"] == 600
    assert env.items[1][1]["advanceWidth"] == 5
    every = jd.set_advance_width(env, 7)
    assert [x["advanceWidth"] for x in every.items[0][1]["layers"]] == [7, 7]


def test_drop_unicodes_and_unicodes_when_hex_text_then_parsed() -> None:
    env = jd.Envelope.parse(
        envelope(objects=[{"glyph": glyph("o")}, {"glyph": glyph("p", "0070")}])
    )
    assert "unicode" not in jd.drop_unicodes(env, ["o"]).items[0][1]
    assert jd.drop_unicodes(env).items[1][1].get("unicode") is None
    assert jd.unicodes({"unicode": "006f, U+0070"}) == (0x6F, 0x70)
    assert jd.unicodes({}) == ()
    with pytest.raises(ValueError, match="unreadable unicode"):
        jd.unicodes({"name": "x", "unicode": "zz"})


def test_only_glyphs_when_mixed_then_glyph_items_remain() -> None:
    env = jd.Envelope.parse(envelope(objects=[{"glyph": glyph()}, {"layer": {}}]))
    assert jd.only_glyphs(env).kinds() == ("glyph",)


# --- native layer with fakes -----------------------------------------------


def test_available_when_api_missing_then_false_and_require_raises() -> None:
    assert jd.available(SimpleNamespace(flModelProducer=object())) is False
    assert jd.available(fake_fl(Producer())) is True
    with pytest.raises(RuntimeError, match="needs FontLab 9.1 or later"):
        jd.require_available(SimpleNamespace())


def test_available_when_outside_fontlab_then_false(monkeypatch) -> None:
    def missing(name):
        raise RuntimeError(name)

    monkeypatch.setattr(jd, "_native", missing)
    assert jd.available() is False


@pytest.mark.parametrize("data", [b"", "text", bytearray(b"x")])
def test_decode_when_python_bytes_or_text_then_wrapped_never_passed(data) -> None:
    producer = Producer(result=["g"])
    raw = (
        json.dumps(envelope(glyph=glyph()))
        if data == "text"
        else json.dumps(envelope(glyph=glyph())).encode()
    )
    payload = bytearray(raw) if isinstance(data, bytearray) else raw
    assert jd.decode(payload, fl=fake_fl(producer), qt=fake_qt()) == ["g"]
    assert producer.decoded[0]["glyph"]["name"] == "o"


def test_decode_when_envelope_dict_or_qbytearray_then_qbytearray_reaches_native() -> (
    None
):
    producer = Producer(result=("a",))
    qba = QBA(json.dumps(HEAD).encode())
    assert jd.as_qbytearray(qba, fake_qt()) is qba
    assert jd.decode(qba, fl=fake_fl(producer), qt=fake_qt()) == ["a"]
    assert jd.decode(jd.Envelope.parse(HEAD), fl=fake_fl(producer), qt=fake_qt()) == [
        "a"
    ]
    assert jd.decode(HEAD, fl=fake_fl(producer), qt=fake_qt()) == ["a"]


def test_decode_when_native_returns_none_then_value_error() -> None:
    with pytest.raises(ValueError, match="returned None"):
        jd.decode(HEAD, fl=fake_fl(Producer(result=None)), qt=fake_qt())


def test_decode_when_bad_python_data_then_value_error_before_native() -> None:
    producer = Producer(result=[])
    with pytest.raises(ValueError, match="dataType"):
        jd.decode(b'{"dataType":"x"}', fl=fake_fl(producer), qt=fake_qt())
    assert producer.decoded == []


def test_export_when_objects_then_package_id_upm_and_utf8_bytes() -> None:
    producer = Producer()
    raw = jd.export(Package(), ["g"], fl=fake_fl(producer))
    assert producer.exported == [(7, 1000, ["g"])]
    assert jd.Envelope.parse(raw).glyph_names() == ("o",)


def test_native_calls_when_fontlab_90_then_runtime_error_and_no_change() -> None:
    fl90 = SimpleNamespace(flModelProducer=SimpleNamespace())
    package = Package()
    for call in (
        lambda: jd.export(package, [], fl=fl90),
        lambda: jd.decode(HEAD, fl=fl90),
        lambda: jd.paste_glyphs(package, envelope(glyph=glyph()), facts=None, fl=fl90),
        lambda: jd.paste_shapes(
            Layer(), Glyph("o"), envelope(element={}), facts=None, fl=fl90
        ),
    ):
        with pytest.raises(RuntimeError, match=re.escape(jd.NEEDS_91)):
            call()


def test_clipboard_when_copied_then_read_back_from_our_mime_type() -> None:
    qt = fake_qt()
    data = envelope(glyph=glyph())
    jd.copy_to_clipboard(data, qt=qt)
    mime = qt.board.mime
    assert type(mime.formats[jd.MIME_TYPE]) is QBA
    assert json.loads(mime.text_value) == data
    assert json.loads(jd.read_clipboard(qt=qt)) == data


def test_read_clipboard_when_text_only_or_foreign_then_parsed_or_none() -> None:
    text = json.dumps(envelope(layer={"name": "A"}))
    assert jd.read_clipboard(qt=fake_qt(Clipboard(Mime(text=text)))) == text.encode()
    assert jd.read_clipboard(qt=fake_qt(Clipboard(Mime(text="hello")))) is None
    assert jd.read_clipboard(qt=fake_qt(Clipboard(None))) is None
    bad_mime = Mime({jd.MIME_TYPE: QBA(b"junk")}, text=text)
    assert jd.read_clipboard(qt=fake_qt(Clipboard(bad_mime))) == text.encode()


def test_read_clipboard_when_fontlab_copy_then_application_json_read() -> None:
    # FontLab 9.1's Edit > Copy offers the JSON as application/json and the
    # glyph names (here "/a") as text, next to its own vic/* formats.
    raw = json.dumps(envelope(glyph=glyph())).encode()
    native = Mime(
        {"application/json": QBA(raw), "vic/glyphs": QBA(b"symbols")}, text="/a"
    )
    assert jd.MIME_TYPE == "application/json"
    assert jd.read_clipboard(qt=fake_qt(Clipboard(native))) == raw


def test_read_clipboard_when_older_mime_type_then_still_read() -> None:
    raw = json.dumps(envelope(layer={"name": "A"})).encode()
    old = Mime({"application/x-fontlab-objects+json": QBA(raw)}, text="")
    assert jd.read_clipboard(qt=fake_qt(Clipboard(old))) == raw


def test_save_and_load_file_when_round_trip_then_pretty_and_checked(tmp_path) -> None:
    path = jd.save_file(tmp_path / "o.json", envelope(glyph=glyph()))
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n") and '\n  "dataType"' in text
    assert jd.Envelope.parse(jd.load_file(path)).glyph_names() == ("o",)
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="dataType"):
        jd.load_file(tmp_path / "bad.json")


# --- paste_glyphs ----------------------------------------------------------


def decoded_glyphs(raw):
    """Fake decoder: one detached glyph per JSON glyph, shapes labelled by layer."""
    env = jd.Envelope.parse(raw)
    out = []
    for kind, payload in env.items:
        layers = [
            Layer(x["name"], [Shape(f"{payload['name']}/{x['name']}")])
            for x in payload.get("layers", [])
        ]
        out.append(Glyph(payload["name"], layers) if kind == "glyph" else Shape(kind))
    return out


def run_paste(monkeypatch, package, data, **kwargs):
    calls = []

    def create(package_, specs, title, facts, *, fill=None, **rest):
        calls.append((specs, title, facts, rest))
        named = {s.name: Glyph(s.name, [Layer(m) for m, _ in s.layers]) for s in specs}
        fill(named)
        return ("created", named)

    monkeypatch.setattr(creation, "create_glyphs", create)
    monkeypatch.setattr(creation, "auto_candidates", lambda *a: {})
    producer = Producer(decoder=decoded_glyphs)
    pasted = jd.paste_glyphs(
        package, data, facts="facts", fl=fake_fl(producer), qt=fake_qt(), **kwargs
    )
    return pasted, calls, producer


def test_paste_glyphs_when_name_taken_then_renamed_unicode_dropped_and_filled(
    monkeypatch,
) -> None:
    data = envelope(
        objects=[{"glyph": glyph("o")}, {"glyph": glyph("p", "0070")}, {"layer": {}}]
    )
    pasted, calls, producer = run_paste(monkeypatch, Package({"o"}), data)
    ((specs, title, facts, rest),) = calls
    assert [(s.name, s.layers, s.unicodes) for s in specs] == [
        ("o.1", (("Regular", 500),), ()),
        ("p", (("Regular", 500),), (0x70,)),
    ]
    assert (title, facts, rest) == (
        "Paste JSON Glyphs",
        "facts",
        {"allow_rebuild": False},
    )
    assert pasted.created == ("o.1", "p")
    assert pasted.skipped == ("layer: not a glyph",)
    assert pasted.notes == ("o -> o.1 (Unicode dropped)",)
    named = pasted.result[1]
    assert [s.label for s in named["o.1"].findLayer("Regular").added] == ["o/Regular"]
    assert [s.label for s in named["p"].findLayer("Regular").added] == ["p/Regular"]
    assert [d["glyph"]["name"] for d in producer.decoded] == ["o", "p"], (
        "each glyph decodes once, as its own one-glyph envelope"
    )


def test_paste_glyphs_when_skip_then_taken_names_skipped(monkeypatch) -> None:
    data = envelope(objects=[{"glyph": glyph("o")}, {"glyph": glyph("q")}])
    pasted, calls, _ = run_paste(monkeypatch, Package({"o"}), data, on_conflict="skip")
    assert [s.name for s in calls[0][0]] == ["q"]
    assert pasted.skipped == ("o: exists",)


def test_paste_glyphs_when_layers_match_some_masters_then_unmatched_listed(
    monkeypatch,
) -> None:
    data = envelope(
        glyph=glyph("o", layers=(("Regular", 500), ("Black", 700), ("Bold", 520)))
    )
    package = Package(masters=("Regular", "Bold", "Light"))
    pasted, calls, _ = run_paste(monkeypatch, package, data)
    assert calls[0][0][0].layers == (("Regular", 500), ("Bold", 520))
    assert pasted.skipped == ('o: layer "Black" matches no master',)


def test_paste_glyphs_when_one_unmatched_layer_then_used_for_every_master(
    monkeypatch,
) -> None:
    data = envelope(glyph=glyph("o", layers=(("Other", 480),)))
    package = Package(masters=("Regular", "Bold"))
    pasted, calls, _ = run_paste(monkeypatch, package, data)
    assert calls[0][0][0].layers == (("Regular", 480), ("Bold", 480))
    assert pasted.notes == ('o: layer "Other" used for every master',)
    assert [s.label for s in pasted.result[1]["o"].findLayer("Bold").added] == [
        "o/Other"
    ]


def test_paste_glyphs_when_no_layer_matches_then_glyph_skipped(monkeypatch) -> None:
    data = envelope(glyph=glyph("o", layers=(("X", 1), ("Y", 2))))
    pasted, calls, _ = run_paste(monkeypatch, Package(), data)
    assert calls[0][0] == []
    assert "o: no layer matches a master" in pasted.skipped


def test_paste_glyphs_when_bad_conflict_or_native_refuses_then_nothing_created(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        creation, "create_glyphs", lambda *a, **k: pytest.fail("created")
    )
    monkeypatch.setattr(creation, "auto_candidates", lambda *a: {})
    with pytest.raises(ValueError, match="on_conflict"):
        jd.paste_glyphs(Package(), HEAD, facts=None, on_conflict="merge")
    with pytest.raises(ValueError, match="returned None"):
        jd.paste_glyphs(
            Package(),
            envelope(glyph=glyph()),
            facts=None,
            fl=fake_fl(Producer(None)),
            qt=fake_qt(),
        )


def test_paste_glyphs_when_code_in_font_or_earlier_in_paste_then_dropped_with_note(
    monkeypatch,
) -> None:
    data = envelope(
        objects=[
            {"glyph": glyph("a", "0061")},
            {"glyph": glyph("b", "0062")},
            {"glyph": glyph("b2", "0062")},
        ]
    )
    pasted, calls, _ = run_paste(monkeypatch, Package(codes={0x61: "a.ss01"}), data)
    assert [(s.name, s.unicodes) for s in calls[0][0]] == [
        ("a", ()),
        ("b", (0x62,)),
        ("b2", ()),
    ]
    assert pasted.notes == (
        "a: U+0061 already on a.ss01, dropped",
        "b2: U+0062 already on b, dropped",
    )


def test_paste_glyphs_when_layer_has_no_width_then_zero_with_note(monkeypatch) -> None:
    payload = glyph("o")
    del payload["layers"][0]["advanceWidth"]
    pasted, calls, _ = run_paste(monkeypatch, Package(), envelope(glyph=payload))
    assert calls[0][0][0].layers == (("Regular", 0),)
    assert pasted.notes == ('o: layer "Regular" has no width, 0 used',)


def test_paste_glyphs_when_no_layer_matches_then_only_summary_skip(monkeypatch) -> None:
    data = envelope(glyph=glyph("o", layers=(("X", 1), ("Y", 2))))
    pasted, _, _ = run_paste(monkeypatch, Package(), data)
    assert pasted.skipped == ("o: no layer matches a master",)


def test_glyphs_undo_text_when_compared_then_matches_creation() -> None:
    assert jd.GLYPHS_UNDO_TEXT == creation.UNDO_TEXT


# --- paste_glyphs with the real create_glyphs ------------------------------


@pytest.fixture
def real(monkeypatch):
    """The creation test doubles (fontpr, fontlab, PythonQt) behind the real create_glyphs."""
    import test_glyph_creation as tc

    tc.LOG.clear()
    package = tc.Package(
        tc.Glyph("e", [tc.Layer("L"), tc.Layer("B")]),
        tc.Glyph(
            "eacute.sc", [tc.Layer("L", 500, auto=True), tc.Layer("B", 500, auto=True)]
        ),
    )
    package.findUnicode = lambda code: tc.Glyph("e") if code == 0x65 else None
    tools = tc.FontPR(package)
    native = tc.Native()
    producer = Producer(decoder=decoded_glyphs)
    native.flModelProducer = producer
    qt = fake_qt()
    qt.QtCore.QDateTime = SimpleNamespace(currentDateTimeUtc=lambda: tc.STAMP)
    for name, module in (("fontlab", native), ("fontpr", tools), ("PythonQt", qt)):
        monkeypatch.setitem(__import__("sys").modules, name, module)
    return SimpleNamespace(
        tc=tc, package=package, tools=tools, native=native, qt=qt,
        facts=tc.facts_of(package),
    )  # fmt: skip


def two_master(name, code=None):
    return glyph(name, code, layers=(("L", 410), ("B", 430)))


def paste_real(real, data, **kwargs):
    return jd.paste_glyphs(
        real.package, data, facts=real.facts, fl=real.native, qt=real.qt, **kwargs
    )


def test_real_create_when_pasted_then_glyphs_added_through_fontpr_and_filled(
    real,
) -> None:
    data = envelope(
        objects=[{"glyph": two_master("e", "0065")}, {"glyph": two_master("x.alt")}]
    )
    pasted = paste_real(real, data)
    assert pasted.created == ("e.1", "x.alt")
    assert [c[1]["glyph_name"] for c in real.tools.calls] == ["e.1", "x.alt"]
    assert "unicodes" not in real.tools.calls[0][1]["glyph_data"]
    made = real.package.findName("e.1")
    assert [x.advanceWidth for x in made.layers] == [410, 430]
    assert [s.label for s in made.findLayer("B").shapes] == ["e/B"]
    assert (
        "notify",
        "Paste JSON Glyphs",
        ["L", "B", "L", "B", "e.1", "x.alt"],
    ) in real.tc.LOG


def test_real_create_when_name_may_rebuild_auto_then_skipped_unless_allowed(
    real,
) -> None:
    data = envelope(objects=[{"glyph": two_master("a.sc")}, {"glyph": two_master("q")}])
    pasted = paste_real(real, data)
    assert pasted.created == ("q",)
    assert pasted.skipped == (
        "a.sc: may rebuild auto eacute.sc; not created (allow_rebuild=True creates it)",
    )
    allowed = paste_real(real, envelope(glyph=two_master("b.sc")), allow_rebuild=True)
    assert allowed.created == ("b.sc",) and real.package.findName("b.sc") is not None


def test_real_create_when_fill_fails_then_partial_write_error_names_new_glyphs(
    real, monkeypatch
) -> None:
    monkeypatch.setattr(
        real.tc.Layer,
        "addShape",
        lambda self, shape: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(history.PartialWriteError) as error:
        paste_real(real, envelope(glyph=two_master("x.alt")))
    assert "x.alt" in str(error.value) and history.UNDO_HINT in str(error.value)


def test_module_source_when_scanned_then_never_calls_add_glyph() -> None:
    code = MODULE.read_text(encoding="utf-8")
    assert not re.search(r"\.addGlyph\s*\(", code), (
        "paste must go through create_glyphs, never addGlyph"
    )


# --- paste_shapes ----------------------------------------------------------


def test_paste_shapes_when_mixed_items_then_one_commit_adds_shapes(monkeypatch) -> None:
    commits = []

    def commit(title, layers, glyphs, mutate, *, operation, facts):
        commits.append((title, layers, glyphs, operation, facts))
        mutate()
        return "committed"

    monkeypatch.setattr(history, "commit", commit)
    source_layer = Layer("A", [Shape("l1"), Shape("l2")])
    objects = [Shape("e"), source_layer, "c1", "c2"]
    producer = Producer(result=objects)
    data = envelope(
        objects=[
            {"glyph": glyph()},
            {"element": {}},
            {"layer": {}},
            {"contour": {}},
            {"contour": {}},
        ]
    )
    target, live = Layer("Regular"), Glyph("o")
    pasted = jd.paste_shapes(
        target, live, data, facts="facts", fl=fake_fl(producer), qt=fake_qt()
    )
    assert commits == [("Paste JSON Shapes", [target], [live], "geometry", "facts")]
    assert [s.label for s in target.added] == ["e", "l1", "l2", "s"]
    assert target.added[-1].contours == ["c1", "c2"]
    assert pasted.created == ("4 shapes on o/Regular",)
    assert pasted.skipped == ("glyph: paste glyphs as new glyphs",)
    assert pasted.result == "committed"
    assert (
        "glyph" not in producer.decoded[0] and len(producer.decoded[0]["objects"]) == 4
    )


def test_paste_shapes_when_only_glyphs_then_nothing_decoded_or_committed(
    monkeypatch,
) -> None:
    monkeypatch.setattr(history, "commit", lambda *a, **k: pytest.fail("committed"))
    producer = Producer(result=[])
    pasted = jd.paste_shapes(
        Layer(),
        Glyph("o"),
        envelope(glyph=glyph()),
        facts=None,
        fl=fake_fl(producer),
        qt=fake_qt(),
    )
    assert pasted.created == () and producer.decoded == []


def test_paste_glyphs_when_two_glyphs_then_each_decoded_once_before_create(
    monkeypatch,
) -> None:
    order = []
    data = envelope(objects=[{"glyph": glyph("p")}, {"glyph": glyph("q")}])

    def decoder(raw):
        order.append("decode")
        name = json.loads(raw)["glyph"]["name"]
        return [Glyph(name, [Layer("Regular", [Shape(name)])])]

    def create(package, specs, title, facts, *, fill=None, allow_rebuild=False):
        order.append("create")
        return None

    monkeypatch.setattr(creation, "create_glyphs", create)
    monkeypatch.setattr(creation, "auto_candidates", lambda *a: {})
    jd.paste_glyphs(
        Package(),
        data,
        facts="facts",
        fl=fake_fl(Producer(decoder=decoder)),
        qt=fake_qt(),
    )
    assert order == ["decode", "decode", "create"]


def test_paste_glyphs_when_second_decode_fails_then_nothing_created(
    monkeypatch,
) -> None:
    calls = []

    def decoder(raw):
        calls.append(raw)
        return None if len(calls) == 2 else [Glyph("p", [Layer("Regular")])]

    monkeypatch.setattr(
        creation, "create_glyphs", lambda *a, **k: pytest.fail("created")
    )
    monkeypatch.setattr(creation, "auto_candidates", lambda *a: {})
    data = envelope(objects=[{"glyph": glyph("p")}, {"glyph": glyph("q")}])
    with pytest.raises(ValueError):
        jd.paste_glyphs(
            Package(),
            data,
            facts="facts",
            fl=fake_fl(Producer(decoder=decoder)),
            qt=fake_qt(),
        )


def test_shape_from_contours_when_called_then_one_shape_with_all_contours() -> None:
    shape = jd._shape_from_contours(fake_fl(Producer()), ["c1", "c2"])
    assert shape.contours == ["c1", "c2"]
